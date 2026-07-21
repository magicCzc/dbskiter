"""
cli/commands/base.py

命令基类

提供统一的命令接口和自动注册机制
"""

from abc import ABCMeta, abstractmethod
from argparse import ArgumentParser, Namespace
from typing import Dict, Type, Any, Optional
import json
import os
import time
from datetime import datetime
from pathlib import Path

from ..config import Config
from ..output import OutputFormatter
from ..exceptions import CommandError


try:
    from dbskiter.sql_master.audit_logger import AuditLogger, OperationStatus, StorageBackend
    _HAS_AUDIT = True
except ImportError:
    _HAS_AUDIT = False

# 全局命令注册表
command_registry: Dict[str, Type["BaseCommand"]] = {}


class CommandMeta(ABCMeta):
    """
    命令元类
    
    自动注册命令到注册表（继承 ABCMeta 避免元类冲突）
    """
    def __new__(mcs, name, bases, namespace):
        cls = super().__new__(mcs, name, bases, namespace)
        # 不注册基类
        if name != "BaseCommand" and hasattr(cls, "name") and cls.name:
            command_registry[cls.name] = cls
        return cls


class BaseCommand(metaclass=CommandMeta):
    """
    命令基类
    
    所有 CLI 命令的基类，定义统一接口
    
    属性:
        name: 命令名称
        description: 命令描述
        help_text: 帮助文本
    
    用法:
        >>> class MyCommand(BaseCommand):
        ...     name = "mycommand"
        ...     description = "My command"
        ...     
        ...     def add_arguments(self, parser):
        ...         parser.add_argument("--option")
        ...     
        ...     def execute(self):
        ...         self.output.print("Hello!")
    """
    
    name: str = ""
    description: str = ""
    help_text: str = ""
    
    def __init__(self, config: Config, output: OutputFormatter, args: Namespace):
        """
        初始化命令

        参数:
            config: 配置对象
            output: 输出格式化器
            args: 解析后的参数
        """
        self.config = config
        self.output = output
        self.args = args
        self._connector = None
        self._last_skill_result: Optional[Dict[str, Any]] = None
        # 初始化审计日志（所有命令统一审计）
        self._audit_logger = self._init_audit_logger()
        self._audit_start_time: Optional[float] = None

    def _init_audit_logger(self) -> Optional[Any]:
        """初始化审计日志记录器（失败不阻断命令执行）"""
        if not _HAS_AUDIT:
            return None
        try:
            audit_path = os.getenv(
                "DBSKITER_AUDIT_PATH",
                str(Path.home() / ".dbskiter" / "audit" / "audit.db")
            )
            Path(audit_path).parent.mkdir(parents=True, exist_ok=True)
            backend_str = os.getenv("DBSKITER_AUDIT_BACKEND", "sqlite")
            backend = StorageBackend(backend_str)
            return AuditLogger(backend=backend, storage_path=audit_path)
        except Exception:
            return None

    def _record_audit(
        self,
        status: str,
        error_message: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """记录命令执行审计日志（失败不阻断）"""
        if not self._audit_logger:
            return
        try:
            # 收集命令执行参数（排除敏感信息）
            safe_args = {}
            if self.args:
                for attr in dir(self.args):
                    if attr.startswith("_") or attr in ("password", "password_file"):
                        continue
                    val = getattr(self.args, attr, None)
                    if val is not None and not callable(val):
                        safe_args[attr] = str(val)[:200]  # 截断防注入

            # 计算执行耗时
            duration_ms = 0.0
            if self._audit_start_time is not None:
                duration_ms = round((time.time() - self._audit_start_time) * 1000, 2)

            self._audit_logger.log(
                sql="",
                database=getattr(self.config, "database", "unknown") or "unknown",
                risk_level="SAFE" if status == "EXECUTED" else "HIGH",
                status=OperationStatus(status),
                sql_type="COMMAND",
                user=os.getenv("USER", "anonymous"),
                metadata={
                    "command": self.name,
                    "args": safe_args,
                    "exit_code": 0 if status == "EXECUTED" else 1,
                    "error_message": error_message,
                    "execution_time_ms": duration_ms,
                    **(metadata or {})
                }
            )
        except Exception:
            pass
    
    @property
    def connector(self):
        """
        获取数据库连接器（延迟加载）
        
        返回:
            UnifiedConnector 或 MockConnector: 数据库连接器
        """
        if self._connector is None:
            # Demo/Mock 模式
            if getattr(self.args, "demo", False) or self.config.dialect == "mock":
                from dbskiter.shared.mock_connector import MockConnector
                self._connector = MockConnector()
            else:
                from dbskiter.shared.unified_connector import UnifiedConnector
                
                # 使用配置中的数据库连接信息（支持--database参数覆盖）
                # 传递 extra 参数（包含 Oracle service_name 和 jdbc_driver_path 等）
                self._connector = UnifiedConnector(
                    dialect=self.config.dialect,
                    host=self.config.host,
                    port=self.config.port,
                    username=self.config.username,
                    password=self.config.password,
                    database=self.config.database,
                    **self.config.extra
                )
            
        return self._connector
    
    @classmethod
    def add_arguments(cls, parser: ArgumentParser) -> None:
        """
        添加命令参数
        
        子类可重写此方法添加自定义参数
        
        参数:
            parser: 参数解析器
        """
        pass
    
    @abstractmethod
    def execute(self) -> int:
        """
        执行命令
        
        子类必须实现此方法
        
        返回:
            int: 退出码，0 表示成功
        """
        raise NotImplementedError
    
    def run(self) -> int:
        """
        运行命令（包装 execute）

        处理异常和清理资源，并记录审计日志。
        若用户指定了 --show-trace 且 execute() 中保存了 _last_skill_result，
        则在命令结束后统一展示诊断追踪信息（支持 rule / raw / ai 全模式）。

        返回:
            int: 退出码
        """
        self._audit_start_time = time.time()
        self._record_audit("PENDING")

        try:
            exit_code = self.execute()
            # rule 模式下若指定了 --show-trace，统一展示追踪信息
            if self.show_trace and self._last_skill_result is not None:
                self._print_inspection_trace(self._last_skill_result)
            self._record_audit("EXECUTED")
            return exit_code
        except CommandError as e:
            self.output.error(e.message)
            self._record_audit("FAILED", error_message=e.message)
            return e.exit_code
        except Exception as e:
            self.output.error(f"命令执行失败: {e}")
            self._record_audit("FAILED", error_message=str(e))
            return 1
        finally:
            self.cleanup()
    
    def cleanup(self) -> None:
        """
        清理资源
        
        子类可重写此方法进行资源清理
        """
        if self._connector:
            try:
                self._connector.close()
            except Exception:
                pass
    
    def print_header(self, title: str) -> None:
        """打印命令头"""
        self.output.header(f"{self.description} - {self.config.database}")
    
    def require_connector(self) -> None:
        """
        确保数据库连接可用
        
        异常:
            CommandError: 连接失败时抛出
        """
        try:
            _ = self.connector
        except Exception as e:
            raise CommandError(f"数据库连接失败: {e}")

    @property
    def output_mode(self) -> str:
        """
        获取输出模式

        返回:
            str: 输出模式 (rule/raw/ai)
        """
        return getattr(self.args, 'output_mode', 'rule')

    @property
    def ai_depth(self) -> str:
        """
        获取AI输出详细程度

        返回:
            str: 详细程度 (summary/detail/full)
        """
        return getattr(self.args, 'ai_depth', 'detail')

    @property
    def show_trace(self) -> bool:
        """
        是否展示诊断追踪信息

        返回:
            bool: True=展示追踪信息
        """
        return getattr(self.args, 'show_trace', False)

    @property
    def mask_sensitive(self) -> bool:
        """
        是否脱敏敏感信息

        返回:
            bool: True表示脱敏
        """
        if getattr(self.args, 'no_mask', False):
            return False
        return getattr(self.args, 'mask_sensitive', True)

    def _extract_error_message(self, result: Dict[str, Any]) -> str:
        """
        从Skill返回结果中提取错误消息

        兼容两种错误响应格式:
        - 格式1: {"success": False, "message": "错误消息"}（diagnostician格式）
        - 格式2: {"success": False, "error": {"message": "错误消息"}}（create_error_response格式）

        参数:
            result: Skill返回的结果字典

        返回:
            str: 错误消息
        """
        if isinstance(result.get('error'), dict):
            return result['error'].get('message', '未知错误')
        return result.get('message', '未知错误')

    def format_ai_output(
        self,
        skill_result: Dict[str, Any],
        context_builder=None,
    ) -> int:
        """
        根据输出模式格式化并输出结果

        rule模式: 保持原有行为不变
        raw模式: 只输出原始数据
        ai模式: 输出AI友好的完整上下文

        参数:
            skill_result: Skill返回的原始结果
            context_builder: AI上下文构建器（可选）

        返回:
            int: 退出码
        """
        mode = self.output_mode

        if mode == "rule":
            # rule 模式下输出简要结论，避免完全静默
            # 详细格式化由各命令的 execute() 自行处理，此处仅兜底输出核心信息
            success = skill_result.get("success", False)
            message = skill_result.get("message", "")
            if message:
                if success:
                    self.output.success(message)
                else:
                    self.output.error(message)

            # 如果指定了 --show-trace，展示诊断追踪信息
            if self.show_trace:
                self._print_inspection_trace(skill_result)

            return 0

        if mode == "raw":
            data = skill_result.get("data", {})
            raw = data.get("raw_metrics", data)
            self.output.print(json.dumps(raw, indent=2, ensure_ascii=False, default=str))
            return 0

        if mode == "ai":
            from dbskiter.shared.ai_context import AIOutputFormatter

            formatter = AIOutputFormatter(
                dialect=self.config.dialect,
                database_name=self.config.database,
                ai_depth=self.ai_depth,
                mask_sensitive=self.mask_sensitive,
            )
            envelope = formatter.format_from_skill_result(
                skill_result=skill_result,
                context_builder=context_builder,
                connector=self._connector,
            )
            self.output.print(json.dumps(envelope, indent=2, ensure_ascii=False, default=str))
            return 0

        return 0

    def _inject_execution_time(
        self,
        skill_result: Dict[str, Any],
        action: str,
        total_ms: float,
    ) -> None:
        """
        将执行耗时注入 inspection_trace，并合并 Skill 内部的多步骤计时

        在 _execute_ai_mode 中自动调用，将计时结果融入 inspection_trace，
        供 _print_inspection_trace 展示。
        如果 Skill 返回了 _execution_time（多步骤计时），则将其步骤合并到
        inspection_trace 的 steps 中。

        参数:
            skill_result: Skill返回的原始结果
            action: 子命令名称
            total_ms: 总耗时（毫秒）
        """
        # 提取 Skill 内部的多步骤计时（如果存在）
        skill_steps: List[Dict[str, Any]] = []
        skill_exec = skill_result.get("_execution_time")
        if isinstance(skill_exec, dict):
            skill_steps = skill_exec.get("steps", [])

        # 定位 inspection_trace
        trace = skill_result.get("inspection_trace")
        if not trace:
            data = skill_result.get("data", {})
            trace = data.get("inspection_trace")

        if trace:
            trace["execution_time_ms"] = round(total_ms, 2)
            # 构建合并后的 steps：总览 + Skill 内部步骤 + 已有步骤
            merged_steps: List[Dict[str, Any]] = [{
                "name": "total",
                "description": "总执行时间（含 CLI 层开销）",
                "elapsed_ms": round(total_ms, 2),
            }]
            # 添加 Skill 内部步骤（如 db_query、format_result）
            if skill_steps:
                merged_steps.extend(skill_steps)
            # 保留 inspection_trace 中已有的步骤（如 diagnose 子命令的细分）
            if "steps" in trace:
                existing_names = {s["name"] for s in skill_steps}
                for step in trace["steps"]:
                    if step.get("name") not in existing_names:
                        merged_steps.append(step)
            trace["steps"] = merged_steps
        else:
            # 如果 Skill 没有返回 inspection_trace，创建一个简化版
            steps = [{
                "name": action,
                "description": f"执行 {action}",
                "elapsed_ms": round(total_ms, 2),
            }]
            if skill_steps:
                steps.extend(skill_steps)
            skill_result["inspection_trace"] = {
                "scenario": action,
                "metrics_checked": [],
                "data_sources": [],
                "confidence": "unknown",
                "notes": ["自动生成的执行追踪（Skill 未提供 inspection_trace）"],
                "execution_time_ms": round(total_ms, 2),
                "steps": steps,
            }

    def _assess_dynamic_confidence(
        self,
        declared_confidence: str,
        skill_result: Dict[str, Any]
    ) -> tuple:
        """
        根据实际数据质量动态评估可信度

        将 Skill 声明的可信度与实际数据质量交叉验证，
        生成最终可信度评级和动态备注。

        参数:
            declared_confidence: Skill 声明的可信度
            skill_result: Skill返回的原始结果

        返回:
            tuple: (final_confidence, dynamic_notes)
                - final_confidence: 最终可信度 (high/medium/low)
                - dynamic_notes: 动态生成的备注列表
        """
        data = skill_result.get("data", {})
        notes = []

        # 规则1：如果 data 完全为空，可信度最多 medium
        if not data:
            if declared_confidence == "high":
                notes.append("数据体为空，可信度已从 high 自动降级")
            return "low", notes + ["未获取到任何数据，建议检查配置或权限"]

        # 规则2：检查关键字段是否为空
        empty_key_count = 0
        total_key_count = len(data)

        for key, value in data.items():
            if value is None:
                empty_key_count += 1
            elif isinstance(value, (list, dict)) and len(value) == 0:
                empty_key_count += 1
            elif isinstance(value, str) and value.strip() == "":
                empty_key_count += 1

        empty_ratio = empty_key_count / total_key_count if total_key_count > 0 else 0

        if empty_ratio >= 0.5:
            if declared_confidence == "high":
                notes.append(f"超过 50% 的数据字段为空 ({empty_key_count}/{total_key_count})，可信度降级")
            return "low", notes
        elif empty_ratio >= 0.3:
            if declared_confidence == "high":
                notes.append(f"部分数据字段为空 ({empty_key_count}/{total_key_count})，可信度降级")
            return "medium", notes

        # 规则3：检查列表型数据量是否充足
        for key, value in data.items():
            if isinstance(value, list) and len(value) == 0:
                notes.append(f"'{key}' 结果为空列表，该维度分析可能不完整")
            elif isinstance(value, list) and len(value) < 3:
                notes.append(f"'{key}' 样本量较少 ({len(value)} 条)，结论可能不具代表性")

        # 规则4：检查 success 状态
        if not skill_result.get("success", True):
            notes.append("Skill 执行未完全成功，结果可能不完整")
            return "low", notes

        return declared_confidence, notes

    def _print_inspection_trace(self, skill_result: Dict[str, Any]) -> None:
        """
        打印诊断/监控/安全追踪信息（Rich Table 美化版 + 动态可信度评估 + 耗时分解）

        当用户指定 --show-trace 时调用，展示数据来源、检查指标和执行耗时。
        兼容 ai 模式（inspection_trace）和 rule 模式（_execution_time）两种数据源。

        参数:
            skill_result: Skill返回的原始结果
        """
        # 从 skill_result 或 data 中提取 inspection_trace
        trace = skill_result.get("inspection_trace")
        if not trace:
            data = skill_result.get("data", {})
            trace = data.get("inspection_trace")

        # 如果 rule 模式未返回 inspection_trace，但有 _execution_time（Skill 内部计时），
        # 则生成一个简化的 inspection_trace 用于展示步骤耗时
        if not trace:
            exec_time = skill_result.get("_execution_time") or data.get("_execution_time")
            if isinstance(exec_time, dict):
                trace = {
                    "scenario": "rule_mode",
                    "metrics_checked": [],
                    "data_sources": [],
                    "confidence": "unknown",
                    "notes": ["rule 模式自动追踪（Skill 内部步骤）"],
                    "execution_time_ms": exec_time.get("total_ms", 0),
                    "steps": exec_time.get("steps", []),
                }

        if not trace:
            return

        scenario = trace.get("scenario", "unknown")
        metrics = trace.get("metrics_checked", [])
        sources = trace.get("data_sources", [])
        declared_confidence = trace.get("confidence", "unknown")
        static_notes = trace.get("notes", [])
        execution_time_ms = trace.get("execution_time_ms")
        steps = trace.get("steps", [])

        # 动态可信度评估
        final_confidence, dynamic_notes = self._assess_dynamic_confidence(
            declared_confidence, skill_result
        )
        all_notes = static_notes + dynamic_notes

        # 使用 Rich Table 展示（如果 console 可用）
        if self.output.console and not self.output.json_mode:
            from rich.table import Table as RichTable
            from rich.text import Text
            from ..style import ThemeColor

            # 标题面板（含耗时）
            self.output.print("")
            confidence_color = {
                "high": ThemeColor.SUCCESS,
                "medium": ThemeColor.WARNING,
                "low": ThemeColor.ERROR,
            }.get(final_confidence, ThemeColor.INFO)

            title_text = Text(f"诊断追踪 | 场景: {scenario} | 可信度: ")
            title_text.append(final_confidence.upper(), style=f"bold {confidence_color}")
            if final_confidence != declared_confidence:
                title_text.append(f" (原声明: {declared_confidence})", style="dim")
            if execution_time_ms is not None:
                time_text = f" | 耗时: {execution_time_ms}ms"
                title_text.append(time_text, style=f"bold {ThemeColor.INFO}")
            self.output.rich_print(title_text)

            # 执行步骤耗时表格（如果有步骤数据）
            if steps:
                step_table = RichTable(
                    title="执行步骤耗时分解",
                    show_header=True,
                    header_style=f"bold {ThemeColor.PRIMARY_BRIGHT}",
                    border_style=ThemeColor.BORDER,
                    padding=(0, 1),
                )
                step_table.add_column("步骤", style=f"bold {ThemeColor.PRIMARY}", min_width=20)
                step_table.add_column("说明", min_width=30)
                step_table.add_column("耗时", style=ThemeColor.INFO, min_width=10, justify="right")

                for s in steps:
                    elapsed = s.get("elapsed_ms", 0)
                    # 根据耗时给颜色提示
                    time_style = ThemeColor.SUCCESS if elapsed < 200 else (
                        ThemeColor.WARNING if elapsed < 1000 else ThemeColor.ERROR
                    )
                    step_table.add_row(
                        s.get("name", ""),
                        s.get("description", ""),
                        Text(f"{elapsed}ms", style=time_style),
                    )
                self.output.rich_print(step_table)

            # 指标表格
            if metrics:
                table = RichTable(
                    title="检查指标",
                    show_header=True,
                    header_style=f"bold {ThemeColor.PRIMARY_BRIGHT}",
                    border_style=ThemeColor.BORDER,
                    padding=(0, 1),
                )
                table.add_column("指标名", style=f"bold {ThemeColor.PRIMARY}", min_width=15)
                table.add_column("说明", min_width=25)
                table.add_column("数据来源", style=ThemeColor.INFO, min_width=20)

                for m in metrics:
                    table.add_row(
                        m.get("name", ""),
                        m.get("description", ""),
                        m.get("source", ""),
                    )
                self.output.rich_print(table)

            # 数据来源
            if sources:
                sources_text = Text(f"数据来源: {', '.join(sources)}")
                sources_text.stylize(ThemeColor.INFO)
                self.output.rich_print(sources_text)

            # 备注
            if all_notes:
                for note in all_notes:
                    note_text = Text(f"⚠ {note}")
                    note_text.stylize(ThemeColor.WARNING)
                    self.output.rich_print(note_text)
        else:
            # 降级到纯文本（JSON/quiet 模式或 console 不可用时）
            self.output.print("")
            time_str = f" | 耗时: {execution_time_ms}ms" if execution_time_ms is not None else ""
            self.output.print(f"[诊断追踪] 场景: {scenario} | 可信度: {final_confidence} (声明: {declared_confidence}){time_str}")
            if steps:
                self.output.print("执行步骤:")
                for s in steps:
                    self.output.print(f"  • {s.get('name', '')}: {s.get('description', '')} ({s.get('elapsed_ms', 0)}ms)")
            if sources:
                self.output.print(f"数据来源: {', '.join(sources)}")
            if metrics:
                self.output.print("检查指标:")
                for m in metrics:
                    self.output.print(f"  • {m.get('name', '')}: {m.get('description', '')} [{m.get('source', '')}]")
            if all_notes:
                for note in all_notes:
                    self.output.print(f"  ⚠ {note}")

    def _execute_ai_mode(
        self,
        skill,
        action: str,
        method_map: Dict[str, Any],
        scenario_map: Optional[Dict[str, str]] = None,
    ) -> int:
        """
        通用AI/Raw模式执行（自动计时 + inspection_trace 注入）

        各命令模块在execute()中检测output_mode != "rule"时，
        构建method_map后调用此方法完成AI/Raw模式输出

        参数:
            skill: Skill实例
            action: 子命令名称
            method_map: action -> callable 的映射，每个callable返回标准结果dict
            scenario_map: action -> scenario 的映射（可选，用于AI上下文场景标识）

        返回:
            int: 退出码

        使用示例:
            >>> method_map = {
            ...     "health": lambda: skill.assess_health(),
            ...     "anomalies": lambda: skill.detect_anomalies(),
            ... }
            >>> scenario_map = {"health": "monitor", "anomalies": "monitor"}
            >>> return self._execute_ai_mode(skill, action, method_map, scenario_map)
        """
        from dbskiter.shared import ExecutionTimer

        handler = method_map.get(action)
        if not handler:
            self.output.error(f"不支持的操作: {action}")
            return 1

        # 自动计时
        timer = ExecutionTimer().start()
        result = handler()
        total_ms = timer.stop()

        if result is None:
            self.output.error(f"操作返回空结果: {action}")
            return 1

        if not result.get("success"):
            self.output.error(f"操作失败: {self._extract_error_message(result)}")
            return 1

        # 将耗时注入 inspection_trace
        self._inject_execution_time(result, action, total_ms)

        # 保存结果供 run() 中 --show-trace 统一展示
        self._last_skill_result = result

        if self.output_mode == "raw":
            data = result.get("data", {})
            self.output.print(json.dumps(data, indent=2, ensure_ascii=False, default=str), force=True)
            return 0

        from dbskiter.shared.ai_context import AIOutputFormatter

        formatter = AIOutputFormatter(
            dialect=self.config.dialect,
            database_name=self.config.database,
            ai_depth=self.ai_depth,
            mask_sensitive=self.mask_sensitive,
        )

        if hasattr(skill, "build_ai_context"):
            scenario = (scenario_map or {}).get(action, "general")
            ai_context = skill.build_ai_context(result, scenario=scenario)
            envelope = formatter.format_envelope(
                raw_metrics=ai_context.get("raw_metrics", {}),
                rule_flags=ai_context.get("rule_flags", {}),
                context=ai_context.get("context", {}),
                reference_values=ai_context.get("reference_values", {}),
                ai_hints=ai_context.get("ai_hints", {}),
                connector=self._connector,
            )
        else:
            envelope = formatter.format_from_skill_result(
                skill_result=result,
                connector=self._connector,
            )

        self.output.print(json.dumps(envelope, indent=2, ensure_ascii=False, default=str), force=True)
        return 0
