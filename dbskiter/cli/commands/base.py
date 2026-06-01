"""
cli/commands/base.py

命令基类

提供统一的命令接口和自动注册机制
"""

from abc import ABCMeta, abstractmethod
from argparse import ArgumentParser, Namespace
from typing import Dict, Type, Any, Optional
import json

from ..config import Config
from ..output import OutputFormatter
from ..exceptions import CommandError


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
    
    @property
    def connector(self):
        """
        获取数据库连接器（延迟加载）
        
        返回:
            UnifiedConnector: 统一数据库连接器（支持 SQLAlchemy 和 JDBC）
        """
        if self._connector is None:
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
        
        处理异常和清理资源
        
        返回:
            int: 退出码
        """
        try:
            return self.execute()
        except CommandError as e:
            self.output.error(e.message)
            return e.exit_code
        except Exception as e:
            self.output.error(f"命令执行失败: {e}")
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

    def _execute_ai_mode(
        self,
        skill,
        action: str,
        method_map: Dict[str, Any],
        scenario_map: Optional[Dict[str, str]] = None,
    ) -> int:
        """
        通用AI/Raw模式执行

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
        handler = method_map.get(action)
        if not handler:
            self.output.error(f"不支持的操作: {action}")
            return 1

        result = handler()
        if result is None:
            self.output.error(f"操作返回空结果: {action}")
            return 1

        if not result.get("success"):
            self.output.error(f"操作失败: {self._extract_error_message(result)}")
            return 1

        if self.output_mode == "raw":
            data = result.get("data", {})
            self.output.print(json.dumps(data, indent=2, ensure_ascii=False, default=str))
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

        self.output.print(json.dumps(envelope, indent=2, ensure_ascii=False, default=str))
        return 0
