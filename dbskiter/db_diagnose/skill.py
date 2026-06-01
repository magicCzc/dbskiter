"""
db_diagnose/skill.py
数据库诊断 Skill 统一入口

文件功能：提供统一的SQL诊断API，支持MySQL/Oracle/PostgreSQL
主要类：DiagnoseSkill - 诊断Skill统一入口

支持的数据库：
    - MySQL: 慢查询分析、AAS分析、执行计划分析
    - Oracle: 慢SQL分析(AWR)、性能指标分析、执行计划分析
    - PostgreSQL: 慢查询分析(pg_stat_statements)、性能分析、执行计划分析

核心功能：
1. 深度SQL分析 - 使用SQLAnalyzer子模块
2. 智能索引建议 - 使用SQLAnalyzer子模块
3. SQL指纹聚合 - 识别相似查询模式
4. 性能指标分析 - 使用多数据库诊断器
5. 慢查询分析 - 使用多数据库诊断器
6. 批量诊断 - 使用BatchAnalyzer子模块
7. 优化报告生成 - 使用ReportGenerator子模块
8. 表诊断 - 使用TableAnalyzer子模块

使用示例：
    >>> skill = DiagnoseSkill(connector)
    >>> result = skill.analyze_sql("SELECT * FROM users WHERE email = 'test@example.com'")
    >>> slow_queries = skill.analyze_slow_queries(limit=20)

版本: 3.0.0（模块化重构版）
作者: AI Assistant
创建时间: 2026-04-23
"""

import logging
from typing import List, Dict, Any, Optional

from dbskiter.shared.unified_connector import UnifiedConnector, detect_connector_type
from dbskiter.shared.validators import validate_params, Validator

from dbskiter.shared.error_handler import create_success_response, create_error_response

# 导入数据模型
from .models import (
    ErrorCode,
    DiagnoseConfig,
)

# 导入工具类
from .utils import (
    SQLFingerprint,
    IssueClassifier,
    ScoreCalculator,
    PrioritySorter,
    MetricsAggregator,
    QueryExtractor,
)

# 导入子模块
from .analyzers.table_analyzer import TableAnalyzer
from .analyzers.sql_analyzer import SQLAnalyzer
from .analyzers.batch_analyzer import BatchAnalyzer
from .analyzers.plan_analyzer import ExecutionPlanAnalyzer
from .reports.generator import ReportGenerator
from .diagnosticians import get_diagnostician

logger = logging.getLogger(__name__)


class DiagnoseSkill:
    """
    数据库诊断 Skill 统一入口（模块化重构版）

    整合深度分析能力和多数据库支持，提供生产级的SQL诊断能力

    核心组件:
        connector: 数据库连接器
        dialect: 数据库方言
        plan_analyzer: 执行计划分析器
        sql_analyzer: SQL分析器
        batch_analyzer: 批量分析器
        table_analyzer: 表诊断分析器
        diagnostician: 数据库特定诊断器
        report_generator: 报告生成器

    支持的数据库:
        - MySQL / MariaDB
        - Oracle
        - PostgreSQL
    """

    def __init__(
        self,
        connector: UnifiedConnector,
        config: Optional[DiagnoseConfig] = None
    ):
        """
        初始化诊断 Skill

        参数:
            connector: UnifiedConnector 实例
            config: 诊断配置，None使用默认配置
        """
        self.connector = connector
        self.config = config or DiagnoseConfig()
        self.dialect = connector.dialect.lower()

        # 初始化工具类
        self.fingerprinter = SQLFingerprint()
        self.issue_classifier = IssueClassifier()
        self.score_calculator = ScoreCalculator()
        self.priority_sorter = PrioritySorter()
        self.metrics_aggregator = MetricsAggregator()
        self.query_extractor = QueryExtractor()

        # 初始化核心分析器
        self.plan_analyzer = ExecutionPlanAnalyzer(connector)
        self._sql_analyzer = SQLAnalyzer(connector)
        self._batch_analyzer = BatchAnalyzer()
        self._table_analyzer = TableAnalyzer(connector)
        self._report_generator = ReportGenerator()

        # 初始化多数据库诊断器
        self._diagnostician = get_diagnostician(self.dialect, connector)

        # 检测连接器类型
        connector_type = detect_connector_type(self.dialect)
        self._is_jdbc = (connector_type == "jdbc")
        self._is_unified = True

        logger.info(f"DiagnoseSkill 初始化完成 (dialect={self.dialect})")

    # ==================== 核心诊断API ====================

    @validate_params(sql=Validator.not_empty_string)
    def analyze_sql(
        self,
        sql: str,
        params: Optional[Dict[str, Any]] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """深度分析SQL语句"""
        try:
            result = self._sql_analyzer.analyze(sql, params, context)
            return create_success_response(result, "SQL分析完成")
        except Exception as e:
            logger.error(f"SQL分析失败: {e}")
            return create_error_response(
                str(e),
                ErrorCode.ANALYSIS_FAILED,
                {"sql": sql}
            )

    def analyze_sql_batch(
        self,
        sqls: List[str],
        show_progress: bool = False
    ) -> List[Dict[str, Any]]:
        """批量分析SQL语句"""
        return self._batch_analyzer.analyze_serial(
            sqls,
            self._sql_analyzer.analyze,
            show_progress=show_progress
        )

    def get_index_suggestions(
        self,
        sql: str,
        min_priority: str = "medium"
    ) -> List[Dict[str, Any]]:
        """获取索引建议"""
        return self._sql_analyzer.get_index_suggestions(sql, min_priority)

    def get_executable_fixes(self, sql: str) -> List[str]:
        """获取可执行的修复SQL"""
        return self._sql_analyzer.get_executable_fixes(sql)

    # ==================== 多数据库诊断功能 ====================

    def analyze_slow_queries(
        self,
        limit: int = 20,
        min_time: float = 1.0,
        log_file: Optional[str] = None,
        since: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        分析慢查询（多数据库支持，增强版）

        支持两种模式：
        1. 实时模式：从数据库采集当前慢查询
        2. 日志模式：解析慢查询日志文件

        参数:
            limit: 返回条数限制
            min_time: 最小执行时间（秒）
            log_file: 日志文件路径（可选，指定则使用日志模式）
            since: 时间范围（如'24h'表示最近24小时，仅日志模式有效）

        返回:
            Dict: 慢查询分析结果，包含：
                - summary: 汇总统计
                - top_patterns: TOP查询模式
                - recommendations: 优化建议
        """
        try:
            if log_file:
                # 日志文件模式
                from .core.slow_query_analyzer import SlowQueryAnalyzer
                analyzer = SlowQueryAnalyzer(self.connector)
                report = analyzer.analyze_log_file(
                    file_path=log_file,
                    since=since,
                    min_time=min_time
                )
                return create_success_response(
                    report.to_dict(),
                    f"日志分析完成: {log_file}"
                )
            else:
                # 实时模式
                result = self._diagnostician.analyze_slow_queries(
                    limit=limit,
                    min_time=min_time
                )
                return result
        except Exception as e:
            logger.error(f"慢查询分析失败: {e}")
            return create_error_response(
                str(e),
                ErrorCode.SLOW_QUERY_FAILED
            )

    def analyze_performance_metrics(
        self,
        duration_minutes: int = 10
    ) -> Dict[str, Any]:
        """
        分析性能指标（多数据库支持）

        参数:
            duration_minutes: 采集时长（分钟）

        返回:
            Dict: 性能指标分析结果
        """
        try:
            # diagnostician已经返回标准格式，直接使用
            result = self._diagnostician.analyze_performance_metrics(
                duration_minutes=duration_minutes
            )
            return result
        except Exception as e:
            logger.error(f"性能指标分析失败: {e}")
            return create_error_response(
                str(e),
                ErrorCode.PERF_ANALYSIS_FAILED
            )

    def get_database_stats(self) -> Dict[str, Any]:
        """
        获取数据库统计信息（多数据库支持）

        返回:
            Dict: 数据库统计信息
        """
        try:
            # diagnostician已经返回标准格式，直接使用
            result = self._diagnostician.get_database_stats()
            return result
        except Exception as e:
            logger.error(f"获取数据库统计信息失败: {e}")
            return create_error_response(
                str(e),
                ErrorCode.METRICS_ERROR
            )

    # ==================== 向后兼容方法 ====================

    def analyze_aas(
        self,
        duration_minutes: int = 10,
        interval_seconds: int = 10
    ) -> Dict[str, Any]:
        """AAS分析（MySQL专用，向后兼容）"""
        if 'mysql' not in self.dialect:
            return create_error_response(
                f"AAS分析仅支持MySQL数据库，当前方言: {self.dialect}",
                ErrorCode.UNSUPPORTED_SQL,
                {"suggestion": "请使用 analyze_performance_metrics() 方法获取性能指标"}
            )

        return self.analyze_performance_metrics(duration_minutes=duration_minutes)

    def _convert_diagnostician_result(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """
        转换diagnostician结果格式为skill标准格式

        diagnostician格式: {"success": bool, "message": str, "data": dict, "dialect": str, "error": str}
        skill格式: {"success": bool, "message": str, "data": dict} 或错误响应格式

        参数:
            result: diagnostician返回的结果

        返回:
            Dict: skill标准格式的结果
        """
        if not result:
            return create_error_response("无返回结果", ErrorCode.UNKNOWN_ERROR)

        success = result.get("success", False)
        message = result.get("message", "")
        data = result.get("data", {})
        error = result.get("error")

        if success:
            return create_success_response(data=data, message=message)
        else:
            return create_error_response(error or message, ErrorCode.UNKNOWN_ERROR, data)

    # ==================== 表和Schema诊断 ====================

    def diagnose_table(
        self,
        table_name: str,
        include_indexes: bool = True,
        include_statistics: bool = True
    ) -> Dict[str, Any]:
        """诊断单表健康状况"""
        try:
            # table_analyzer.analyze 已经返回标准响应格式，直接返回
            return self._table_analyzer.analyze(
                table_name=table_name,
                include_indexes=include_indexes,
                include_statistics=include_statistics
            )
        except Exception as e:
            logger.error(f"表诊断失败: {e}")
            return create_error_response(
                str(e),
                ErrorCode.TABLE_DIAGNOSE_FAILED,
                {"table_name": table_name}
            )

    # ==================== 报告生成 ====================

    def generate_report(
        self,
        sqls: List[str],
        report_title: str = "SQL诊断报告",
        report_format: str = "json"
    ) -> Dict[str, Any]:
        """
        生成诊断报告

        参数:
            sqls: SQL语句列表
            report_title: 报告标题
            report_format: 报告格式 (json/markdown/text)

        返回:
            Dict: 诊断报告
        """
        try:
            # 1. 分析所有SQL
            analyses = []
            for sql in sqls:
                analysis_result = self._sql_analyzer.analyze(sql)
                if analysis_result.get("success"):
                    analyses.append(analysis_result.get("data", {}))

            # 2. 生成报告
            report_content = self._report_generator.generate(
                analyses=analyses,
                report_format=report_format
            )

            # 3. 如果是JSON格式，解析为字典
            if report_format == "json":
                import json
                report_data = json.loads(report_content)
            else:
                report_data = {"content": report_content}

            return create_success_response(
                data=report_data,
                message=f"诊断报告生成完成，分析了 {len(analyses)} 条SQL"
            )
        except Exception as e:
            logger.error(f"生成诊断报告失败: {e}")
            return create_error_response(
                str(e),
                ErrorCode.UNKNOWN_ERROR
            )

    # ==================== SQL重写 ====================

    def rewrite_sql(self, sql: str, optimization_type: str = "auto") -> Dict[str, Any]:
        """SQL重写优化"""
        try:
            result = self._sql_analyzer.rewrite(sql, optimization_type)
            return create_success_response(result, "SQL重写完成")
        except Exception as e:
            logger.error(f"SQL重写失败: {e}")
            return create_error_response(
                str(e),
                ErrorCode.ANALYSIS_FAILED
            )

    def analyze_sql_quality(self, sql: str) -> Dict[str, Any]:
        """分析SQL质量"""
        try:
            result = self._sql_analyzer.analyze_quality(sql)
            return create_success_response(result, "SQL质量分析完成")
        except Exception as e:
            logger.error(f"SQL质量分析失败: {e}")
            return create_error_response(
                str(e),
                ErrorCode.ANALYSIS_FAILED
            )

    # ==================== 工具方法 ====================

    def get_sql_fingerprint(self, sql: str) -> str:
        """获取SQL指纹"""
        return self.fingerprinter.generate(sql)

    def classify_issue(self, issue_text: str) -> Dict[str, Any]:
        """分类问题"""
        return self.issue_classifier.classify(issue_text)

    def extract_query_info(self, sql: str) -> Dict[str, Any]:
        """提取查询信息"""
        return {
            "tables": self.query_extractor.extract_tables(sql),
            "columns": self.query_extractor.extract_columns(sql),
            "conditions": self.query_extractor.extract_where_conditions(sql),
            "fingerprint": self.fingerprinter.generate(sql)
        }

    # ==================== AI上下文构建 ====================

    def build_ai_context(
        self,
        skill_result: Dict[str, Any],
        scenario: str = "diagnose"
    ) -> Dict[str, Any]:
        """
        构建AI分析上下文

        将Skill返回的规则结果转换为AI友好的结构化上下文，
        包含原始数据、规则标记、业务上下文和AI提示

        参数:
            skill_result: Skill返回的原始结果
            scenario: 场景标识 (diagnose/slow_query/sql_analysis/index_recommend)

        返回:
            Dict[str, Any]: AI上下文，包含 raw_metrics / rule_flags / context / reference_values / ai_hints

        使用示例:
            >>> result = skill.analyze_slow_queries(limit=10)
            >>> ai_ctx = skill.build_ai_context(result, scenario="slow_query")
            >>> print(ai_ctx["ai_hints"]["focus_areas"])
        """
        from dbskiter.shared.ai_context import AIContextBuilder

        builder = AIContextBuilder(
            dialect=self.dialect,
            database_name=getattr(self.connector, 'database', ''),
        )
        builder.detect_business_context(self.connector)

        data = skill_result.get("data", {})

        raw_metrics = self._extract_raw_metrics_for_ai(data, scenario)
        rule_flags = self._extract_rule_flags_for_ai(data, scenario)
        context = self._build_context_for_ai(builder, data)
        reference_values = self._build_reference_values(scenario)
        ai_hints = self._build_ai_hints(scenario, data)

        return {
            "raw_metrics": raw_metrics,
            "rule_flags": rule_flags,
            "context": context,
            "reference_values": reference_values,
            "ai_hints": ai_hints,
        }

    def _extract_raw_metrics_for_ai(
        self,
        data: Dict[str, Any],
        scenario: str
    ) -> Dict[str, Any]:
        """
        从Skill结果中提取原始指标数据

        参数:
            data: Skill返回的data字段
            scenario: 场景标识

        返回:
            Dict[str, Any]: 原始指标字典
        """
        metrics = {}

        # 慢查询场景
        if scenario == "slow_query":
            # 从data中提取慢查询数据（支持多种字段名）
            slow_queries = data.get("queries", data.get("slow_queries", []))
            metrics["slow_queries"] = slow_queries
            metrics["slow_queries_count"] = data.get("total_queries", len(slow_queries) if isinstance(slow_queries, list) else 0)
            metrics["unique_patterns"] = data.get("unique_patterns", 0)
            if isinstance(slow_queries, list) and slow_queries:
                times = [q.get("query_time", q.get("execution_time", 0)) for q in slow_queries if isinstance(q, dict)]
                numeric_times = [float(t) for t in times if t]
                if numeric_times:
                    metrics["avg_query_time"] = round(sum(numeric_times) / len(numeric_times), 2)
                    metrics["max_query_time"] = max(numeric_times)

        # SQL分析场景
        elif scenario == "sql_analysis":
            if "execution_plan" in data:
                metrics["execution_plan"] = data["execution_plan"]
            if "issues" in data:
                metrics["issues_raw"] = data["issues"]
            if "score" in data:
                metrics["score"] = data["score"]

        # 索引推荐场景
        elif scenario == "index_recommend":
            metrics["database"] = data.get("database", "")
            metrics["table"] = data.get("table", "")
            metrics["suggestions"] = data.get("suggestions", [])
            metrics["summary"] = data.get("summary", {})

        # 实时诊断场景 - 综合数据
        elif scenario == "realtime":
            metrics.update(data)

        # TOP SQL场景
        elif scenario == "top_sql":
            queries = data.get("queries", [])
            metrics["top_queries"] = queries
            metrics["top_queries_count"] = len(queries)

        # 锁分析场景
        elif scenario == "locks":
            metrics["lock_waits"] = data.get("lock_waits", [])
            metrics["deadlocks"] = data.get("deadlocks", [])
            metrics["statistics"] = data.get("statistics", {})

        # 空间诊断场景
        elif scenario == "space":
            metrics["large_tables"] = data.get("large_tables", [])
            metrics["total_space"] = data.get("total_space", {})
            metrics["suggestions"] = data.get("suggestions", [])

        # 连接分析场景
        elif scenario == "connections":
            metrics["statistics"] = data.get("statistics", {})
            metrics["idle_connections"] = data.get("idle_connections", [])

        # 复制诊断场景
        elif scenario == "replication":
            metrics["status"] = data.get("status", {})
            metrics["slave_status"] = data.get("slave_status", {})

        # 性能快照场景
        elif scenario == "performance_snapshot":
            metrics["snapshot"] = data.get("snapshot", {})
            metrics["bottlenecks"] = data.get("bottlenecks", [])
            metrics["summary"] = data.get("summary", {})

        # 瓶颈分析场景
        elif scenario == "bottleneck":
            metrics["bottlenecks"] = data.get("bottlenecks", [])
            metrics["severity_summary"] = data.get("severity_summary", {})
            metrics["recommendations"] = data.get("recommendations", [])

        # 表诊断场景
        elif scenario == "table":
            metrics["table_name"] = data.get("table_name", "")
            metrics["statistics"] = data.get("statistics", {})
            metrics["indexes"] = data.get("indexes", [])
            metrics["issues"] = data.get("issues", [])
            metrics["suggestions"] = data.get("suggestions", [])

        # 报告场景
        elif scenario == "report":
            metrics["summary"] = data.get("summary", {})
            metrics["details"] = data.get("details", [])

        # 默认：返回所有数据
        else:
            metrics = data

        return metrics

    def _extract_rule_flags_for_ai(
        self,
        data: Dict[str, Any],
        scenario: str
    ) -> Dict[str, Any]:
        """
        从Skill结果中提取规则初筛标记

        参数:
            data: Skill返回的data字段
            scenario: 场景标识

        返回:
            Dict[str, Any]: 规则标记字典
        """
        flags = {}
        issues = data.get("issues", [])

        for issue in issues:
            name = issue.get("name", issue.get("type", "unknown"))
            flags[name] = {
                "flagged": True,
                "level": issue.get("level", issue.get("severity", "unknown")),
                "reason": issue.get("reason", issue.get("description", "")),
            }

        if "bottlenecks" in data:
            for bp in data["bottlenecks"]:
                bp_name = bp.get("category", "bottleneck")
                flags[f"bottleneck_{bp_name}"] = {
                    "flagged": True,
                    "level": bp.get("severity", "high"),
                    "reason": bp.get("description", bp.get("suggestion", "")),
                }

        return {
            "_disclaimer": "规则初筛结果仅供参考，请结合上下文判断是否为真正问题",
            "flags": flags,
        } if flags else {"_disclaimer": "规则初筛结果仅供参考", "flags": {}}

    def _build_context_for_ai(
        self,
        builder: "AIContextBuilder",
        data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        构建业务上下文

        参数:
            builder: AI上下文构建器
            data: Skill返回的data字段

        返回:
            Dict[str, Any]: 上下文字典
        """
        ctx = builder.build_database_profile(self.connector)

        if "table_metadata" in data:
            ctx["table_metadata"] = data["table_metadata"]
        if "workload_context" in data:
            ctx["workload_context"] = data["workload_context"]

        return ctx

    def _build_reference_values(self, scenario: str) -> Dict[str, Any]:
        """
        构建参考基线

        参数:
            scenario: 场景标识

        返回:
            Dict[str, Any]: 参考值字典
        """
        references = {}

        # 慢查询相关场景
        if scenario in ("slow_query", "diagnose"):
            if "mysql" in self.dialect:
                references["mysql_oltp_recommended"] = {
                    "long_query_time": "1.0-2.0秒",
                    "slow_queries_per_hour": "< 50",
                }
                references["industry_standard"] = {
                    "long_query_time": "1.0秒",
                }
            elif "oracle" in self.dialect:
                references["oracle_recommended"] = {
                    "avg_execution_time": "< 0.5秒",
                }
            elif "postgresql" in self.dialect:
                references["postgresql_recommended"] = {
                    "log_min_duration_statement": "1000ms",
                }

        # 索引相关场景
        if scenario in ("index_recommend", "diagnose"):
            references["index_best_practices"] = {
                "selectivity_threshold": "0.1 (选择性低于10%不建议加索引)",
                "redundant_index_overlap": "> 80% 列重叠视为冗余",
            }

        # 连接相关场景
        if scenario == "connections":
            references["connection_standards"] = {
                "max_connections_usage": "< 80%",
                "idle_connection_timeout": "建议设置wait_timeout为600秒",
            }

        # 锁相关场景
        if scenario == "locks":
            references["lock_standards"] = {
                "lock_wait_timeout": "innodb_lock_wait_timeout默认50秒",
                "deadlock_threshold": "每小时死锁次数应<5",
            }

        # 空间相关场景
        if scenario == "space":
            references["space_standards"] = {
                "table_size_warning": "> 1GB需要关注",
                "fragmentation_threshold": "> 30%需要优化",
            }

        # 复制相关场景
        if scenario == "replication":
            references["replication_standards"] = {
                "max_replication_lag": "< 10秒",
                "io_thread_running": "必须为Yes",
                "sql_thread_running": "必须为Yes",
            }

        # 性能快照场景
        if scenario == "performance_snapshot":
            references["performance_standards"] = {
                "cpu_usage_warning": "> 70%",
                "memory_usage_warning": "> 80%",
                "io_wait_warning": "> 20%",
            }

        # 瓶颈分析场景
        if scenario == "bottleneck":
            references["bottleneck_standards"] = {
                "critical_threshold": "立即处理",
                "high_threshold": "24小时内处理",
                "medium_threshold": "一周内处理",
            }

        return references

    def _build_ai_hints(
        self,
        scenario: str,
        data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        构建AI分析提示

        参数:
            scenario: 场景标识
            data: Skill返回的data字段

        返回:
            Dict[str, Any]: AI提示字典
        """
        hints: Dict[str, Any] = {
            "focus_areas": [],
            "related_commands": [],
        }

        db_name = getattr(self.connector, 'database', '')

        if scenario in ("slow_query", "diagnose"):
            hints["focus_areas"] = ["slow_query_patterns", "query_performance", "index_coverage"]
            hints["related_commands"] = [
                f"dbskiter --database={db_name} diagnose slow-queries",
                f"dbskiter --database={db_name} diagnose recommend-indexes",
                f"dbskiter --database={db_name} monitor health",
            ]

        if scenario == "sql_analysis":
            hints["focus_areas"] = ["execution_plan_efficiency", "full_table_scan_risk", "implicit_cast"]
            hints["related_commands"] = [
                f"dbskiter --database={db_name} diagnose recommend-indexes",
                f"dbskiter --database={db_name} sql rewrite <sql>",
            ]

        if scenario == "index_recommend":
            hints["focus_areas"] = ["missing_indexes", "redundant_indexes", "unused_indexes"]
            hints["related_commands"] = [
                f"dbskiter --database={db_name} diagnose slow-queries",
                f"dbskiter --database={db_name} diagnose table <table_name>",
            ]

        if scenario == "realtime":
            hints["focus_areas"] = ["active_connections", "lock_waits", "top_sql"]
            hints["related_commands"] = [
                f"dbskiter --database={db_name} diagnose locks",
                f"dbskiter --database={db_name} diagnose top",
            ]

        if scenario == "connections":
            hints["focus_areas"] = ["connection_pool_usage", "idle_connections", "max_connections"]
            hints["related_commands"] = [
                f"dbskiter --database={db_name} diagnose realtime",
                f"dbskiter --database={db_name} monitor health",
            ]

        if scenario == "top_sql":
            hints["focus_areas"] = ["high_cpu_queries", "long_running_queries", "frequent_queries"]
            hints["related_commands"] = [
                f"dbskiter --database={db_name} diagnose sql <sql>",
                f"dbskiter --database={db_name} diagnose recommend-indexes",
            ]

        if scenario == "locks":
            hints["focus_areas"] = ["lock_waits", "deadlocks", "blocking_transactions"]
            hints["related_commands"] = [
                f"dbskiter --database={db_name} diagnose realtime",
                f"dbskiter --database={db_name} diagnose top",
            ]

        if scenario == "space":
            hints["focus_areas"] = ["large_tables", "table_fragmentation", "storage_growth"]
            hints["related_commands"] = [
                f"dbskiter --database={db_name} diagnose table <table_name>",
                f"dbskiter --database={db_name} monitor capacity",
            ]

        if scenario == "replication":
            hints["focus_areas"] = ["replication_lag", "io_thread_status", "sql_thread_status"]
            hints["related_commands"] = [
                f"dbskiter --database={db_name} diagnose realtime",
                f"dbskiter --database={db_name} monitor health",
            ]

        if scenario == "performance_snapshot":
            hints["focus_areas"] = ["cpu_usage", "memory_usage", "io_wait", "qps_tps"]
            hints["related_commands"] = [
                f"dbskiter --database={db_name} diagnose bottleneck",
                f"dbskiter --database={db_name} monitor health",
            ]

        if scenario == "bottleneck":
            hints["focus_areas"] = ["cpu_bottleneck", "io_bottleneck", "lock_bottleneck", "memory_bottleneck"]
            hints["related_commands"] = [
                f"dbskiter --database={db_name} diagnose performance-snapshot",
                f"dbskiter --database={db_name} diagnose top",
            ]

        if scenario == "table":
            hints["focus_areas"] = ["table_structure", "index_efficiency", "table_statistics"]
            hints["related_commands"] = [
                f"dbskiter --database={db_name} diagnose recommend-indexes",
                f"dbskiter --database={db_name} diagnose space",
            ]

        if scenario == "report":
            hints["focus_areas"] = ["overall_health", "performance_summary", "optimization_opportunities"]
            hints["related_commands"] = [
                f"dbskiter --database={db_name} diagnose realtime",
                f"dbskiter --database={db_name} diagnose performance-snapshot",
            ]

        issues = data.get("issues", [])
        if issues:
            hints["additional_notes"] = [
                f"规则检测到 {len(issues)} 个潜在问题，请结合上下文判断严重程度"
            ]

        return hints

    def close(self):
        """关闭Skill，释放资源"""
        logger.info("关闭 DiagnoseSkill...")
        logger.info("DiagnoseSkill 已关闭")


    # ==================== 新增: 实时诊断方法 (P0高频场景) ====================

    def realtime_diagnose(self, threshold: int = 5) -> Dict[str, Any]:
        """
        实时综合诊断 - 分析数据库当前性能问题

        功能：
            1. 检查活跃连接数
            2. 检查锁等待情况
            3. 检查TOP SQL（慢查询）
            4. 给出诊断建议

        参数:
            threshold: 慢查询阈值（秒，默认5）

        返回:
            Dict: 综合诊断结果
        """
        try:
            # 1. 获取连接信息
            conn_result = self.get_realtime_connections()
            conn_data = conn_result.get('data', {}) if conn_result.get('success') else {}

            # 2. 获取锁等待信息
            lock_result = self.get_lock_waits()
            lock_data = lock_result.get('data', {}) if lock_result.get('success') else {}

            # 3. 获取TOP SQL
            top_sql_result = self.get_top_sql(limit=5, threshold=threshold)
            top_sql_data = top_sql_result.get('data', {}) if top_sql_result.get('success') else {}

            # 4. 分析并生成建议
            suggestions = []
            issues = []

            # 分析连接数
            total_conn = conn_data.get('total', 0)
            active_conn = conn_data.get('active', 0)
            slow_count = conn_data.get('slow_count', 0)

            if total_conn > 100:
                issues.append(f"连接数过多: {total_conn}")
                suggestions.append("考虑优化连接池配置或检查连接泄漏")

            if active_conn > 20:
                issues.append(f"活跃连接数高: {active_conn}")
                suggestions.append("检查是否有长事务或慢查询占用连接")

            # 分析锁等待
            lock_waits = lock_data.get('lock_waits', [])
            if lock_waits:
                issues.append(f"存在锁等待: {len(lock_waits)}个")
                suggestions.append("检查锁等待链，考虑优化事务或添加索引")

            # 分析慢查询
            queries = top_sql_data.get('queries', [])
            if queries:
                issues.append(f"发现慢查询: {len(queries)}个（>{threshold}秒）")
                suggestions.append("执行 'diagnose slow-queries' 查看详细慢查询信息")
                suggestions.append("执行 'diagnose top' 查看资源消耗最高的SQL")

            # 如果没有问题，给出正常提示
            if not issues:
                suggestions.append("数据库运行正常，暂无性能问题")

            return create_success_response(
                message="实时诊断完成",
                data={
                    "connections": conn_data,
                    "lock_waits": lock_data,
                    "top_sql": top_sql_data,
                    "issues": issues,
                    "suggestions": suggestions,
                    "threshold": threshold
                }
            )

        except Exception as e:
            logger.error(f"实时诊断失败: {e}")
            return create_error_response(str(e), ErrorCode.UNKNOWN_ERROR)

    def get_realtime_connections(self) -> Dict[str, Any]:
        """
        获取实时连接信息

        返回:
            Dict: 连接统计信息
        """
        try:
            if self._diagnostician:
                result = self._diagnostician.get_realtime_connections()
                return self._convert_diagnostician_result(result)
            else:
                return create_error_response(
                    f"实时连接分析暂不支持 {self.dialect}",
                    ErrorCode.UNSUPPORTED_SQL
                )
        except Exception as e:
            logger.error(f"获取实时连接失败: {e}")
            return create_error_response(str(e), ErrorCode.UNKNOWN_ERROR)

    def get_top_sql(self, limit: int = 10, threshold: int = 0,
                    order_by: str = "time") -> Dict[str, Any]:
        """
        获取TOP SQL

        参数:
            limit: 返回条数
            threshold: 执行时间阈值(秒)
            order_by: 排序依据(time/cpu/io/rows)

        返回:
            Dict: TOP SQL列表
        """
        try:
            if self._diagnostician:
                result = self._diagnostician.get_top_sql(limit, threshold)
                return self._convert_diagnostician_result(result)
            else:
                return create_error_response(
                    f"TOP SQL分析暂不支持 {self.dialect}",
                    ErrorCode.UNSUPPORTED_SQL
                )
        except Exception as e:
            logger.error(f"获取TOP SQL失败: {e}")
            return create_error_response(str(e), ErrorCode.UNKNOWN_ERROR)

    def get_lock_waits(self) -> Dict[str, Any]:
        """
        获取锁等待信息

        返回:
            Dict: 锁等待列表
        """
        try:
            if self._diagnostician:
                result = self._diagnostician.get_lock_waits()
                return self._convert_diagnostician_result(result)
            else:
                return create_error_response(
                    f"锁等待分析暂不支持 {self.dialect}",
                    ErrorCode.UNSUPPORTED_SQL
                )
        except Exception as e:
            logger.error(f"获取锁等待失败: {e}")
            return create_error_response(str(e), ErrorCode.UNKNOWN_ERROR)

    def analyze_locks(self) -> Dict[str, Any]:
        """
        综合分析锁情况

        返回:
            Dict: 锁分析结果
        """
        try:
            if 'mysql' in self.dialect:
                return self._analyze_mysql_locks()
            elif 'oracle' in self.dialect:
                return self._analyze_oracle_locks()
            elif 'postgresql' in self.dialect:
                return self._analyze_postgresql_locks()
            else:
                return create_error_response(
                    f"锁分析暂不支持 {self.dialect}",
                    ErrorCode.UNSUPPORTED_SQL
                )
        except Exception as e:
            logger.error(f"锁分析失败: {e}")
            return create_error_response(str(e), ErrorCode.UNKNOWN_ERROR)

    def _analyze_mysql_locks(self) -> Dict[str, Any]:
        """MySQL锁分析"""
        try:
            # 获取锁等待
            lock_waits_result = self._diagnostician.get_lock_waits()
            lock_waits = lock_waits_result.get('data', {}).get('lock_waits', [])

            # 获取事务统计
            result = self.connector.execute("""
                SELECT 
                    COUNT(*) as trx_count,
                    SUM(CASE WHEN trx_state = 'RUNNING' THEN 1 ELSE 0 END) as running
                FROM information_schema.INNODB_TRX
            """)

            row = result.rows[0] if result.rows else (0, 0)

            return create_success_response(
                message="锁分析完成",
                data={
                    "lock_waits": lock_waits,
                    "deadlocks": [],  # 需要查询performance_schema
                    "statistics": {
                        "trx_count": row[0],
                        "running_trx": row[1],
                        "lock_waits_count": len(lock_waits)
                    }
                }
            )
        except Exception as e:
            return create_error_response(str(e), ErrorCode.UNKNOWN_ERROR)

    def _analyze_oracle_locks(self) -> Dict[str, Any]:
        """Oracle锁分析"""
        try:
            lock_waits_result = self._diagnostician.get_lock_waits()
            lock_waits = lock_waits_result.get('data', {}).get('lock_waits', [])

            # 获取事务统计
            result2 = self.connector.execute("""
                SELECT
                    COUNT(*) AS total_trx,
                    SUM(CASE WHEN status = 'ACTIVE' THEN 1 ELSE 0 END) AS active_trx
                FROM v$transaction
            """)

            row = result2.rows[0] if result2.rows else (0, 0)

            # 检测死锁（基于alert日志或v$lock循环等待）
            deadlocks = []
            try:
                result3 = self.connector.execute("""
                    SELECT COUNT(*) FROM v$lock
                    WHERE request > 0 AND ctime > 60
                """)
                long_wait_count = int(str(result3.rows[0][0])) if result3.rows else 0
                if long_wait_count > 0:
                    deadlocks.append({
                        "type": "long_lock_wait",
                        "description": f"发现 {long_wait_count} 个等待超过60秒的锁请求",
                        "suggestion": "检查是否存在阻塞事务，考虑终止或优化"
                    })
            except Exception:
                pass

            return create_success_response(
                message="锁分析完成",
                data={
                    "lock_waits": lock_waits,
                    "deadlocks": deadlocks,
                    "statistics": {
                        "trx_count": int(str(row[0])) if row[0] else 0,
                        "running_trx": int(str(row[1])) if row[1] else 0,
                        "lock_waits_count": len(lock_waits)
                    }
                }
            )
        except Exception as e:
            return create_error_response(str(e), ErrorCode.UNKNOWN_ERROR)

    def analyze_space(self, top_n: int = 20, min_size_mb: int = 100, database: Optional[str] = None) -> Dict[str, Any]:
        """
        空间诊断

        参数:
            top_n: TOP N大表
            min_size_mb: 最小表大小(MB)
            database: 指定数据库名（可选，默认使用当前连接的数据库）

        返回:
            Dict: 空间分析结果
        """
        try:
            if 'mysql' in self.dialect:
                return self._analyze_mysql_space(top_n, min_size_mb, database)
            elif 'oracle' in self.dialect:
                return self._analyze_oracle_space(top_n, min_size_mb)
            elif 'postgresql' in self.dialect:
                return self._analyze_postgresql_space(top_n, min_size_mb)
            else:
                return create_error_response(
                    f"空间分析暂不支持 {self.dialect}",
                    ErrorCode.UNSUPPORTED_SQL
                )
        except Exception as e:
            logger.error(f"空间分析失败: {e}")
            return create_error_response(str(e), ErrorCode.UNKNOWN_ERROR)

    def _analyze_mysql_space(self, top_n: int, min_size_mb: int, database: Optional[str] = None) -> Dict[str, Any]:
        """MySQL空间分析"""
        try:
            # 获取数据库名（优先使用参数传入的数据库名）
            if database:
                current_db = database
                logger.info(f"使用指定数据库进行空间分析: {current_db}")
            else:
                # 获取当前数据库名
                db_result = self.connector.execute("SELECT DATABASE()")
                current_db = db_result.rows[0][0] if db_result.rows and db_result.rows[0][0] else None
                logger.info(f"使用当前连接的数据库进行空间分析: {current_db}")

            if not current_db:
                return create_error_response(
                    "无法获取当前数据库名",
                    ErrorCode.UNKNOWN_ERROR
                )

            # 获取表空间信息
            result = self.connector.execute("""
                SELECT 
                    table_name,
                    ROUND(data_length / 1024 / 1024, 2) as data_mb,
                    ROUND(index_length / 1024 / 1024, 2) as index_mb,
                    ROUND((data_length + index_length) / 1024 / 1024, 2) as total_mb,
                    table_rows,
                    engine
                FROM information_schema.TABLES
                WHERE table_schema = :db
                    AND (data_length + index_length) / 1024 / 1024 >= :min_size
                ORDER BY (data_length + index_length) DESC
                LIMIT :limit
            """, {"db": current_db, "min_size": min_size_mb, "limit": top_n})

            tables = []
            total_data = 0
            total_index = 0

            for row in result.rows:
                tables.append({
                    "table": row[0],
                    "data_mb": row[1],
                    "index_mb": row[2],
                    "size_mb": row[3],
                    "rows": row[4],
                    "engine": row[5],
                    "fragmentation": 0  # 需要额外计算
                })
                total_data += row[1] or 0
                total_index += row[2] or 0

            return create_success_response(
                message=f"获取到 {len(tables)} 个大表",
                data={
                    "total_space": {
                        "total_gb": round((total_data + total_index) / 1024, 2),
                        "data_gb": round(total_data / 1024, 2),
                        "index_gb": round(total_index / 1024, 2)
                    },
                    "large_tables": tables,
                    "suggestions": []
                }
            )
        except Exception as e:
            return create_error_response(str(e), ErrorCode.UNKNOWN_ERROR)

    def _analyze_oracle_space(self, top_n: int = 20, min_size_mb: int = 100) -> Dict[str, Any]:
        """
        Oracle空间分析

        分析维度：
        1. 表空间使用率（总量、已用、空闲、使用率）
        2. 大段分析（表/索引大小TOP N）
        3. 数据文件信息

        参数:
            top_n: TOP N大段
            min_size_mb: 最小段大小(MB)

        返回:
            Dict: 空间分析结果
        """
        try:
            # 1. 表空间使用率分析
            tablespaces = []
            try:
                result = self.connector.execute("""
                    SELECT
                        df.tablespace_name,
                        ROUND(df.total_bytes / 1024 / 1024 / 1024, 3) AS total_gb,
                        ROUND(NVL(fs.free_bytes, 0) / 1024 / 1024 / 1024, 3) AS free_gb,
                        ROUND((df.total_bytes - NVL(fs.free_bytes, 0)) / 1024 / 1024 / 1024, 3) AS used_gb,
                        ROUND((df.total_bytes - NVL(fs.free_bytes, 0)) / df.total_bytes * 100, 2) AS used_pct,
                        df.file_count
                    FROM (
                        SELECT tablespace_name, SUM(bytes) total_bytes, COUNT(*) file_count
                        FROM dba_data_files
                        GROUP BY tablespace_name
                    ) df
                    LEFT JOIN (
                        SELECT tablespace_name, SUM(bytes) free_bytes
                        FROM dba_free_space
                        GROUP BY tablespace_name
                    ) fs ON df.tablespace_name = fs.tablespace_name
                    ORDER BY used_pct DESC
                """)

                for row in result.rows:
                    total_gb = float(str(row[1])) if row[1] else 0
                    free_gb = float(str(row[2])) if row[2] else 0
                    used_gb = float(str(row[3])) if row[3] else 0
                    used_pct = float(str(row[4])) if row[4] else 0
                    file_count = int(str(row[5])) if row[5] else 0

                    warning = None
                    if used_pct > 95:
                        warning = "表空间即将满，请立即扩容"
                    elif used_pct > 85:
                        warning = "表空间使用率较高，建议尽快扩容"

                    tablespaces.append({
                        "tablespace_name": row[0],
                        "total_gb": total_gb,
                        "used_gb": used_gb,
                        "free_gb": free_gb,
                        "used_pct": used_pct,
                        "file_count": file_count,
                        "warning": warning
                    })
            except Exception as e:
                logger.warning(f"查询表空间信息失败（可能没有DBA权限）: {e}")
                # 使用user级别查询
                try:
                    result = self.connector.execute("""
                        SELECT
                            tablespace_name,
                            ROUND(SUM(bytes) / 1024 / 1024 / 1024, 3) AS total_gb,
                            0 AS free_gb,
                            ROUND(SUM(bytes) / 1024 / 1024 / 1024, 3) AS used_gb,
                            100 AS used_pct,
                            COUNT(*) AS file_count
                        FROM user_data_files
                        GROUP BY tablespace_name
                        ORDER BY total_gb DESC
                    """)

                    for row in result.rows:
                        tablespaces.append({
                            "tablespace_name": row[0],
                            "total_gb": float(str(row[1])) if row[1] else 0,
                            "used_gb": float(str(row[3])) if row[3] else 0,
                            "free_gb": 0,
                            "used_pct": float(str(row[4])) if row[4] else 0,
                            "file_count": int(str(row[5])) if row[5] else 0,
                            "warning": None
                        })
                except Exception as e2:
                    logger.warning(f"user级别表空间查询也失败: {e2}")

            # 2. 大段分析（表和索引）
            large_segments = []
            try:
                result = self.connector.execute(f"""
                    SELECT * FROM (
                        SELECT
                            segment_name,
                            segment_type,
                            tablespace_name,
                            ROUND(bytes / 1024 / 1024, 2) AS size_mb,
                            blocks
                        FROM user_segments
                        WHERE bytes / 1024 / 1024 >= {min_size_mb}
                        ORDER BY bytes DESC
                    )
                    WHERE ROWNUM <= {top_n}
                """)

                for row in result.rows:
                    large_segments.append({
                        "segment_name": row[0],
                        "segment_type": row[1],
                        "tablespace": row[2],
                        "size_mb": float(str(row[3])) if row[3] else 0,
                        "blocks": int(str(row[4])) if row[4] else 0
                    })
            except Exception as e:
                logger.warning(f"查询大段信息失败: {e}")

            # 3. 汇总计算
            total_used_gb = sum(ts['used_gb'] for ts in tablespaces)
            total_alloc_gb = sum(ts['total_gb'] for ts in tablespaces)

            # 4. 生成建议
            space_suggestions = []
            for ts in tablespaces:
                if ts.get('warning'):
                    space_suggestions.append({
                        "type": "tablespace_space",
                        "priority": "high" if ts['used_pct'] > 95 else "medium",
                        "tablespace": ts['tablespace_name'],
                        "used_pct": ts['used_pct'],
                        "free_gb": ts['free_gb'],
                        "suggestion": ts['warning']
                    })

            for seg in large_segments[:5]:
                if seg['size_mb'] > 1024:
                    space_suggestions.append({
                        "type": "large_segment",
                        "priority": "low",
                        "segment": f"{seg['segment_type']}: {seg['segment_name']}",
                        "size_mb": seg['size_mb'],
                        "suggestion": "考虑归档历史数据或进行分区"
                    })

            return create_success_response(
                message=f"Oracle空间分析完成",
                data={
                    "total_space": {
                        "total_gb": round(total_alloc_gb, 3),
                        "used_gb": round(total_used_gb, 3),
                        "free_gb": round(total_alloc_gb - total_used_gb, 3)
                    },
                    "tablespaces": tablespaces,
                    "large_segments": large_segments,
                    "suggestions": space_suggestions
                }
            )

        except Exception as e:
            logger.error(f"Oracle空间分析失败: {e}")
            return create_error_response(str(e), ErrorCode.UNKNOWN_ERROR)

    def analyze_connections(self, show_idle: bool = False) -> Dict[str, Any]:
        """
        连接分析

        参数:
            show_idle: 是否显示空闲连接

        返回:
            Dict: 连接分析结果
        """
        try:
            if 'mysql' in self.dialect:
                return self._analyze_mysql_connections(show_idle)
            elif 'oracle' in self.dialect:
                return self._analyze_oracle_connections(show_idle)
            elif 'postgresql' in self.dialect:
                return self._analyze_postgresql_connections(show_idle)
            else:
                return create_error_response(
                    f"连接分析暂不支持 {self.dialect}",
                    ErrorCode.UNSUPPORTED_SQL
                )
        except Exception as e:
            logger.error(f"连接分析失败: {e}")
            return create_error_response(str(e), ErrorCode.UNKNOWN_ERROR)

    def _analyze_mysql_connections(self, show_idle: bool) -> Dict[str, Any]:
        """MySQL连接分析"""
        try:
            # 获取连接统计
            result = self.connector.execute("""
                SELECT 
                    @@max_connections as max_conn,
                    COUNT(*) as current,
                    SUM(CASE WHEN COMMAND != 'Sleep' THEN 1 ELSE 0 END) as active,
                    SUM(CASE WHEN COMMAND = 'Sleep' THEN 1 ELSE 0 END) as idle
                FROM information_schema.PROCESSLIST
                WHERE USER != 'system user'
            """)

            row = result.rows[0] if result.rows else (100, 0, 0, 0)
            max_conn, current, active, idle = row
            usage_pct = (current / max_conn * 100) if max_conn > 0 else 0

            data = {
                "statistics": {
                    "max_connections": max_conn,
                    "current": current,
                    "active": active,
                    "idle": idle,
                    "usage_percent": round(usage_pct, 1)
                }
            }

            # 获取空闲连接详情
            if show_idle:
                result = self.connector.execute("""
                    SELECT 
                        ID,
                        USER,
                        HOST,
                        TIME as idle_time
                    FROM information_schema.PROCESSLIST
                    WHERE COMMAND = 'Sleep'
                        AND USER != 'system user'
                    ORDER BY TIME DESC
                    LIMIT 20
                """)

                idle_conns = []
                for row in result.rows:
                    idle_conns.append({
                        "id": row[0],
                        "user": row[1],
                        "host": row[2],
                        "idle_time": row[3]
                    })
                data["idle_connections"] = idle_conns

            return create_success_response(
                message="连接分析完成",
                data=data
            )
        except Exception as e:
            return create_error_response(str(e), ErrorCode.UNKNOWN_ERROR)

    def _analyze_oracle_connections(self, show_idle: bool) -> Dict[str, Any]:
        """
        Oracle连接分析

        参数:
            show_idle: 是否显示空闲连接

        返回:
            Dict: 连接分析结果
        """
        try:
            # 获取连接统计
            # 分两步查询避免CROSS JOIN + GROUP BY兼容性问题
            max_sessions = 100
            result = self.connector.execute(
                "SELECT value FROM v$parameter WHERE name = 'sessions'"
            )
            if result.rows:
                max_sessions = int(str(result.rows[0][0])) if result.rows[0][0] else 100

            result = self.connector.execute("""
                SELECT
                    COUNT(*) AS total_count,
                    SUM(CASE WHEN status = 'ACTIVE' THEN 1 ELSE 0 END) AS active_count,
                    SUM(CASE WHEN status = 'INACTIVE' THEN 1 ELSE 0 END) AS idle_count
                FROM v$session
                WHERE type != 'BACKGROUND'
            """)

            if result.rows:
                row = result.rows[0]
                current = int(str(row[0])) if row[0] else 0
                active = int(str(row[1])) if row[1] else 0
                idle = int(str(row[2])) if row[2] else 0
            else:
                current = active = idle = 0

            usage_pct = (current / max_sessions * 100) if max_sessions > 0 else 0

            data = {
                "statistics": {
                    "max_connections": max_sessions,
                    "current": current,
                    "active": active,
                    "idle": idle,
                    "usage_percent": round(usage_pct, 1)
                }
            }

            # 获取空闲连接详情
            if show_idle:
                result = self.connector.execute("""
                    SELECT * FROM (
                        SELECT
                            vs.sid,
                            vs.serial#,
                            vs.username,
                            vs.machine,
                            vs.program,
                            vs.last_call_et / 60 AS idle_minutes
                        FROM v$session vs
                        WHERE vs.status = 'INACTIVE'
                        AND vs.type != 'BACKGROUND'
                        AND vs.username IS NOT NULL
                        ORDER BY vs.last_call_et DESC
                    )
                    WHERE ROWNUM <= 20
                """)

                idle_conns = []
                for row in result.rows:
                    idle_conns.append({
                        "sid": row[0],
                        "serial": row[1],
                        "user": row[2],
                        "machine": row[3],
                        "program": row[4],
                        "idle_minutes": round(float(str(row[5])) if row[5] else 0, 1)
                    })
                data["idle_connections"] = idle_conns

            return create_success_response(
                message="连接分析完成",
                data=data
            )
        except Exception as e:
            return create_error_response(str(e), ErrorCode.UNKNOWN_ERROR)

    def analyze_replication(self) -> Dict[str, Any]:
        """
        复制诊断

        返回:
            Dict: 复制状态
        """
        try:
            if 'mysql' in self.dialect:
                return self._analyze_mysql_replication()
            elif 'oracle' in self.dialect:
                return self._analyze_oracle_replication()
            elif 'postgresql' in self.dialect:
                return self._analyze_postgresql_replication()
            else:
                return create_error_response(
                    f"复制分析暂不支持 {self.dialect}",
                    ErrorCode.UNSUPPORTED_SQL
                )
        except Exception as e:
            logger.error(f"复制分析失败: {e}")
            return create_error_response(str(e), ErrorCode.UNKNOWN_ERROR)

    def _analyze_mysql_replication(self) -> Dict[str, Any]:
        """MySQL复制分析"""
        try:
            data = {"status": {}}

            result = self.connector.execute("SHOW MASTER STATUS")
            is_master = len(result.rows) > 0
            data["status"]["is_master"] = is_master

            if is_master:
                data["status"]["binlog_enabled"] = True
                data["status"]["slave_count"] = 0

            try:
                result = self.connector.execute("SHOW SLAVE STATUS")
                is_slave = len(result.rows) > 0
                data["status"]["is_slave"] = is_slave

                if is_slave and result.rows:
                    row = result.rows[0]
                    data["slave_status"] = {
                        "io_running": row[10] if len(row) > 10 else "No",
                        "sql_running": row[11] if len(row) > 11 else "No",
                        "delay_seconds": row[32] if len(row) > 32 else 0
                    }
            except Exception:
                data["status"]["is_slave"] = False

            return create_success_response(
                message="复制分析完成",
                data=data
            )
        except Exception as e:
            return create_error_response(str(e), ErrorCode.UNKNOWN_ERROR)

    def _analyze_oracle_replication(self) -> Dict[str, Any]:
        """Oracle Data Guard复制分析"""
        try:
            data = {"status": {}}

            try:
                result = self.connector.execute("""
                    SELECT COUNT(*) FROM v$dataguard_config
                """)
                has_dataguard = result.rows and result.rows[0][0] > 0
            except Exception:
                has_dataguard = False

            data["status"]["dataguard_enabled"] = has_dataguard

            if has_dataguard:
                try:
                    result = self.connector.execute("""
                        SELECT
                            name,
                            database_role,
                            open_mode,
                            protection_mode,
                            switchover_status
                        FROM v$database
                    """)
                    if result.rows:
                        row = result.rows[0]
                        data["status"]["database_role"] = str(row[1] or "UNKNOWN")
                        data["status"]["open_mode"] = str(row[2] or "UNKNOWN")
                        data["status"]["protection_mode"] = str(row[3] or "UNKNOWN")
                        data["status"]["switchover_status"] = str(row[4] or "UNKNOWN")
                except Exception as e:
                    logger.warning(f"查询v$database失败: {e}")

                try:
                    result = self.connector.execute("""
                        SELECT
                            dest_name,
                            status,
                            recovery_mode,
                            gap_status,
                            transmit_mode
                        FROM v$archive_dest_status
                        WHERE status != 'INACTIVE'
                        AND dest_name IS NOT NULL
                    """)
                    destinations = []
                    for row in result.rows:
                        destinations.append({
                            "dest_name": str(row[0] or ""),
                            "status": str(row[1] or ""),
                            "recovery_mode": str(row[2] or ""),
                            "gap_status": str(row[3] or ""),
                            "transmit_mode": str(row[4] or "")
                        })
                    data["archive_destinations"] = destinations
                except Exception as e:
                    logger.warning(f"查询v$archive_dest_status失败: {e}")

                try:
                    result = self.connector.execute("""
                        SELECT
                            name,
                            value,
                            unit,
                            time_computed
                        FROM v$dataguard_stats
                        WHERE name IN ('transport lag', 'apply lag', 'apply finish time')
                    """)
                    stats = {}
                    for row in result.rows:
                        stats[str(row[0])] = {
                            "value": str(row[1] or ""),
                            "unit": str(row[2] or ""),
                            "time": str(row[3] or "")
                        }
                    data["dataguard_stats"] = stats

                    apply_lag = stats.get("apply lag", {}).get("value", "0")
                    transport_lag = stats.get("transport lag", {}).get("value", "0")
                    try:
                        apply_lag_sec = float(str(apply_lag).split()[0]) if apply_lag else 0
                        transport_lag_sec = float(str(transport_lag).split()[0]) if transport_lag else 0
                    except (ValueError, IndexError):
                        apply_lag_sec = 0
                        transport_lag_sec = 0

                    if apply_lag_sec > 300:
                        data["warning"] = f"应用延迟过高: {apply_lag_sec}秒"
                    elif transport_lag_sec > 60:
                        data["warning"] = f"传输延迟过高: {transport_lag_sec}秒"
                except Exception as e:
                    logger.warning(f"查询v$dataguard_stats失败: {e}")
            else:
                data["status"]["database_role"] = "PRIMARY"
                data["message"] = "未配置Data Guard"

            return create_success_response(
                message="Oracle复制分析完成",
                data=data
            )
        except Exception as e:
            return create_error_response(str(e), ErrorCode.UNKNOWN_ERROR)

    # ==================== PostgreSQL诊断方法 ====================

    def _analyze_postgresql_locks(self) -> Dict[str, Any]:
        """PostgreSQL锁分析"""
        try:
            lock_waits_result = self._diagnostician.get_lock_waits()
            lock_waits = lock_waits_result.get('data', {}).get('lock_waits', [])

            deadlocks = 0
            try:
                result = self.connector.execute("""
                    SELECT deadlocks
                    FROM pg_stat_database
                    WHERE datname = current_database()
                """)
                if result.rows:
                    deadlocks = int(str(result.rows[0][0])) if result.rows[0][0] else 0
            except Exception:
                pass

            active_trx = 0
            try:
                result = self.connector.execute("""
                    SELECT COUNT(*)
                    FROM pg_stat_activity
                    WHERE xact_start IS NOT NULL
                    AND backend_type = 'client backend'
                """)
                if result.rows:
                    active_trx = int(str(result.rows[0][0])) if result.rows[0][0] else 0
            except Exception:
                pass

            return create_success_response(
                message="锁分析完成",
                data={
                    "lock_waits": lock_waits,
                    "deadlocks": [{"count": deadlocks}] if deadlocks > 0 else [],
                    "statistics": {
                        "trx_count": active_trx,
                        "running_trx": active_trx,
                        "lock_waits_count": len(lock_waits),
                        "deadlock_count": deadlocks
                    }
                }
            )
        except Exception as e:
            return create_error_response(str(e), ErrorCode.UNKNOWN_ERROR)

    def _analyze_postgresql_space(self, top_n: int = 20, min_size_mb: int = 100) -> Dict[str, Any]:
        """PostgreSQL空间分析"""
        try:
            result = self.connector.execute(f"""
                SELECT
                    schemaname || '.' || relname AS table_name,
                    pg_size_pretty(pg_total_relation_size(quote_ident(schemaname) || '.' || quote_ident(relname))) AS total_size,
                    pg_total_relation_size(quote_ident(schemaname) || '.' || quote_ident(relname)) / 1024 / 1024 AS total_mb,
                    pg_relation_size(quote_ident(schemaname) || '.' || quote_ident(relname)) / 1024 / 1024 AS data_mb,
                    (pg_total_relation_size(quote_ident(schemaname) || '.' || quote_ident(relname))
                        - pg_relation_size(quote_ident(schemaname) || '.' || quote_ident(relname))) / 1024 / 1024 AS index_mb,
                    n_live_tup AS row_count
                FROM pg_stat_user_tables
                    WHERE pg_total_relation_size(quote_ident(schemaname) || '.' || quote_ident(relname)) / 1024 / 1024 >= {min_size_mb}
                ORDER BY pg_total_relation_size(quote_ident(schemaname) || '.' || quote_ident(relname)) DESC
                LIMIT {top_n}
            """)

            tables = []
            total_data = 0
            total_index = 0
            for row in result.rows:
                data_mb = float(str(row[3])) if row[3] else 0
                index_mb = float(str(row[4])) if row[4] else 0
                tables.append({
                    "table": str(row[0]),
                    "size_pretty": str(row[1]),
                    "size_mb": float(str(row[2])) if row[2] else 0,
                    "data_mb": data_mb,
                    "index_mb": index_mb,
                    "rows": int(str(row[5])) if row[5] else 0
                })
                total_data += data_mb
                total_index += index_mb

            total_db_mb = 0
            try:
                db_result = self.connector.execute("""
                    SELECT pg_database_size(current_database()) / 1024 / 1024
                """)
                if db_result.rows:
                    total_db_mb = float(str(db_result.rows[0][0])) if db_result.rows[0][0] else 0
            except Exception:
                pass

            return create_success_response(
                message=f"获取到 {len(tables)} 个大表",
                data={
                    "total_space": {
                        "total_mb": round(total_db_mb, 2),
                        "data_mb": round(total_data, 2),
                        "index_mb": round(total_index, 2)
                    },
                    "large_tables": tables,
                    "suggestions": []
                }
            )
        except Exception as e:
            return create_error_response(str(e), ErrorCode.UNKNOWN_ERROR)

    def _analyze_postgresql_connections(self, show_idle: bool) -> Dict[str, Any]:
        """PostgreSQL连接分析"""
        try:
            max_conn = 100
            try:
                result = self.connector.execute(
                    "SELECT setting::int FROM pg_settings WHERE name = 'max_connections'"
                )
                if result.rows:
                    max_conn = int(str(result.rows[0][0])) if result.rows[0][0] else 100
            except Exception:
                pass

            result = self.connector.execute("""
                SELECT
                    COUNT(*) AS total,
                    COUNT(*) FILTER (WHERE state = 'active') AS active,
                    COUNT(*) FILTER (WHERE state = 'idle') AS idle,
                    COUNT(*) FILTER (WHERE state = 'idle in transaction') AS idle_in_trx
                FROM pg_stat_activity
                WHERE backend_type = 'client backend'
            """)

            row = result.rows[0] if result.rows else (0, 0, 0, 0)
            current = int(str(row[0])) if row[0] else 0
            active = int(str(row[1])) if row[1] else 0
            idle = int(str(row[2])) if row[2] else 0
            idle_in_trx = int(str(row[3])) if row[3] else 0
            usage_pct = (current / max_conn * 100) if max_conn > 0 else 0

            data = {
                "statistics": {
                    "max_connections": max_conn,
                    "current": current,
                    "active": active,
                    "idle": idle,
                    "idle_in_transaction": idle_in_trx,
                    "usage_percent": round(usage_pct, 1)
                }
            }

            if show_idle:
                result = self.connector.execute("""
                    SELECT
                        pid,
                        usename,
                        application_name,
                        client_addr,
                        EXTRACT(EPOCH FROM (now() - state_change))::numeric(10,2) / 60 AS idle_minutes,
                        state,
                        LEFT(query, 200) AS last_query
                    FROM pg_stat_activity
                    WHERE state IN ('idle', 'idle in transaction')
                    AND backend_type = 'client backend'
                    ORDER BY state_change ASC
                    LIMIT 20
                """)
                idle_conns = []
                for row in result.rows:
                    idle_conns.append({
                        "pid": row[0],
                        "user": str(row[1]) if row[1] else "",
                        "application": str(row[2]) if row[2] else "",
                        "client_addr": str(row[3]) if row[3] else "",
                        "idle_minutes": round(float(str(row[4])) if row[4] else 0, 1),
                        "state": str(row[5]) if row[5] else "",
                        "last_query": str(row[6]) if row[6] else ""
                    })
                data["idle_connections"] = idle_conns

            return create_success_response(
                message="连接分析完成",
                data=data
            )
        except Exception as e:
            return create_error_response(str(e), ErrorCode.UNKNOWN_ERROR)

    def _analyze_postgresql_replication(self) -> Dict[str, Any]:
        """PostgreSQL复制分析(流复制/逻辑复制)"""
        try:
            data = {"status": {}}

            is_primary = False
            try:
                result = self.connector.execute("""
                    SELECT pg_is_in_recovery()
                """)
                is_primary = not (result.rows and result.rows[0][0])
            except Exception:
                pass

            data["status"]["is_primary"] = is_primary

            if is_primary:
                data["status"]["database_role"] = "PRIMARY"
                try:
                    result = self.connector.execute("""
                        SELECT
                            client_addr,
                            state,
                            sent_lsn,
                            replay_lsn,
                            replay_lag
                        FROM pg_stat_replication
                    """)
                    replicas = []
                    for row in result.rows:
                        lag = str(row[4]) if row[4] else "0"
                        replicas.append({
                            "client_addr": str(row[0]) if row[0] else "",
                            "state": str(row[1]) if row[1] else "",
                            "sent_lsn": str(row[2]) if row[2] else "",
                            "replay_lsn": str(row[3]) if row[3] else "",
                            "replay_lag": lag
                        })
                    data["replicas"] = replicas
                    data["status"]["replica_count"] = len(replicas)
                except Exception as e:
                    logger.warning(f"查询pg_stat_replication失败: {e}")
                    data["status"]["replica_count"] = 0
            else:
                data["status"]["database_role"] = "STANDBY"
                try:
                    result = self.connector.execute("""
                        SELECT
                            status,
                            sender_host,
                            sender_port,
                            received_lsn,
                            latest_end_lsn
                        FROM pg_stat_wal_receiver
                    """)
                    if result.rows:
                        row = result.rows[0]
                        data["receiver_status"] = {
                            "status": str(row[0]) if row[0] else "",
                            "sender_host": str(row[1]) if row[1] else "",
                            "sender_port": int(str(row[2])) if row[2] else 0,
                            "received_lsn": str(row[3]) if row[3] else "",
                            "latest_end_lsn": str(row[4]) if row[4] else ""
                        }
                except Exception as e:
                    logger.warning(f"查询pg_stat_wal_receiver失败: {e}")

            return create_success_response(
                message="PostgreSQL复制分析完成",
                data=data
            )
        except Exception as e:
            return create_error_response(str(e), ErrorCode.UNKNOWN_ERROR)

    def _recommend_postgresql_indexes(self, table: str = None) -> Dict[str, Any]:
        """PostgreSQL索引建议"""
        try:
            if table and not table.replace('.', '').replace('_', '').replace('-', '').isalnum():
                return create_error_response(
                    f"无效的表名: {table}",
                    ErrorCode.INVALID_PARAM
                )
            suggestions = []
            current_db = None
            try:
                result = self.connector.execute("SELECT current_database()")
                if result.rows:
                    current_db = result.rows[0][0]
            except Exception:
                pass

            table_filter = f" AND schemaname || '.' || relname = '{table}'" if table else ""

            try:
                result = self.connector.execute(f"""
                    SELECT
                        schemaname || '.' || relname AS table_name,
                        COALESCE(idx_scan, 0) AS index_scans,
                        COALESCE(seq_scan, 0) AS seq_scans,
                        CASE WHEN seq_scan > 0
                            THEN ROUND((seq_scan::numeric / (seq_scan + idx_scan + 1)) * 100, 1)
                            ELSE 0
                        END AS seq_scan_pct,
                        n_live_tup AS row_count
                    FROM pg_stat_user_tables
                    WHERE seq_scan > 100
                    AND (idx_scan IS NULL OR seq_scan > idx_scan * 2)
                    {table_filter}
                    ORDER BY seq_scan DESC
                    LIMIT 20
                """)
                for row in result.rows:
                    suggestions.append({
                        "type": "missing_index",
                        "priority": "high" if int(str(row[3])) > 80 else "medium",
                        "table": str(row[0]),
                        "description": f"表 {row[0]} 全表扫描比例 {row[3]}%",
                        "seq_scans": int(str(row[2])) if row[2] else 0,
                        "index_scans": int(str(row[1])) if row[1] else 0,
                        "suggestion": f"检查表 {row[0]} 的WHERE条件列，添加合适索引",
                        "reason": f"顺序扫描 {row[2]} 次，索引扫描仅 {row[1]} 次"
                    })
            except Exception as e:
                logger.warning(f"分析缺失索引失败: {e}")

            try:
                result = self.connector.execute(f"""
                    SELECT
                        schemaname || '.' || relname AS table_name,
                        indexrelname AS index_name,
                        idx_scan AS index_scans
                    FROM pg_stat_user_indexes
                    WHERE idx_scan = 0
                    AND schemaname NOT IN ('pg_catalog', 'information_schema')
                    {table_filter}
                    ORDER BY relname
                    LIMIT 20
                """)
                for row in result.rows:
                    suggestions.append({
                        "type": "unused_index",
                        "priority": "low",
                        "table": str(row[0]),
                        "index": str(row[1]),
                        "description": f"索引 {row[1]} 从未被使用",
                        "suggestion": f"DROP INDEX {row[1]};",
                        "reason": "该索引自服务器启动以来从未被使用"
                    })
            except Exception as e:
                logger.warning(f"分析未使用索引失败: {e}")

            # 分析冗余索引（被其他索引完全包含）
            try:
                redundant_indexes = self._analyze_redundant_indexes_postgresql(table)
                suggestions.extend(redundant_indexes)
            except Exception as e:
                logger.warning(f"分析冗余索引失败: {e}")

            # 分析低基数索引
            try:
                low_cardinality = self._analyze_low_cardinality_indexes_postgresql(table)
                suggestions.extend(low_cardinality)
            except Exception as e:
                logger.warning(f"分析低基数索引失败: {e}")

            priority_order = {"high": 0, "medium": 1, "low": 2}
            suggestions.sort(
                key=lambda x: priority_order.get(x.get("priority", "low"), 2)
            )

            return create_success_response(
                message=f"发现 {len(suggestions)} 个索引建议",
                data={
                    "database": current_db,
                    "table": table,
                    "suggestions": suggestions,
                    "summary": {
                        "total": len(suggestions),
                        "high_priority": len([s for s in suggestions if s.get("priority") == "high"]),
                        "medium_priority": len([s for s in suggestions if s.get("priority") == "medium"]),
                        "low_priority": len([s for s in suggestions if s.get("priority") == "low"])
                    }
                }
            )
        except Exception as e:
            return create_error_response(str(e), ErrorCode.UNKNOWN_ERROR)

    def recommend_indexes(self, table: str = None) -> Dict[str, Any]:
        """
        索引建议

        参数:
            table: 指定表名(可选，默认分析全库)

        返回:
            Dict: 索引建议列表
        """
        try:
            if 'mysql' in self.dialect:
                return self._recommend_mysql_indexes(table)
            elif 'oracle' in self.dialect:
                return self._recommend_oracle_indexes(table)
            elif 'postgresql' in self.dialect:
                return self._recommend_postgresql_indexes(table)
            else:
                return create_error_response(
                    f"索引建议暂不支持 {self.dialect}",
                    ErrorCode.UNSUPPORTED_SQL
                )
        except Exception as e:
            logger.error(f"索引建议失败: {e}")
            return create_error_response(str(e), ErrorCode.UNKNOWN_ERROR)

    def _recommend_mysql_indexes(self, table: str = None) -> Dict[str, Any]:
        """
        MySQL索引建议

        分析维度：
        1. 缺失索引（基于慢查询和WHERE条件）
        2. 冗余索引（重复索引、前缀索引）
        3. 未使用索引（基于performance_schema）
        4. 低基数索引（索引选择性差）

        参数:
            table: 指定表名

        返回:
            Dict: 索引建议结果
        """
        try:
            # 表名安全验证
            if table and not self._is_valid_table_name(table):
                return create_error_response(
                    f"无效的表名: {table}",
                    ErrorCode.INVALID_PARAM
                )

            suggestions = []
            current_db = None

            # 获取当前数据库名
            try:
                result = self.connector.execute("SELECT DATABASE()")
                if result.rows:
                    current_db = result.rows[0][0]
            except Exception:
                pass

            if not current_db:
                return create_error_response(
                    "无法获取当前数据库名",
                    ErrorCode.UNKNOWN_ERROR
                )

            # 1. 分析缺失索引（基于performance_schema.table_io_waits_summary_by_index_usage）
            try:
                missing_indexes = self._analyze_missing_indexes_mysql(current_db, table)
                suggestions.extend(missing_indexes)
            except Exception as e:
                logger.warning(f"分析缺失索引失败: {e}")

            # 2. 分析冗余索引
            try:
                redundant_indexes = self._analyze_redundant_indexes_mysql(current_db, table)
                suggestions.extend(redundant_indexes)
            except Exception as e:
                logger.warning(f"分析冗余索引失败: {e}")

            # 3. 分析未使用索引
            try:
                unused_indexes = self._analyze_unused_indexes_mysql(current_db, table)
                suggestions.extend(unused_indexes)
            except Exception as e:
                logger.warning(f"分析未使用索引失败: {e}")

            # 4. 分析低基数索引
            try:
                low_cardinality = self._analyze_low_cardinality_indexes_mysql(current_db, table)
                suggestions.extend(low_cardinality)
            except Exception as e:
                logger.warning(f"分析低基数索引失败: {e}")

            # 按优先级排序
            priority_order = {"high": 0, "medium": 1, "low": 2}
            suggestions.sort(
                key=lambda x: priority_order.get(x.get("priority", "low"), 2)
            )

            return create_success_response(
                message=f"发现 {len(suggestions)} 个索引建议",
                data={
                    "database": current_db,
                    "table": table,
                    "suggestions": suggestions,
                    "summary": {
                        "total": len(suggestions),
                        "high_priority": len([s for s in suggestions if s.get("priority") == "high"]),
                        "medium_priority": len([s for s in suggestions if s.get("priority") == "medium"]),
                        "low_priority": len([s for s in suggestions if s.get("priority") == "low"])
                    }
                }
            )

        except Exception as e:
            return create_error_response(str(e), ErrorCode.UNKNOWN_ERROR)

    def _analyze_missing_indexes_mysql(self, database: str, table: str = None) -> List[Dict[str, Any]]:
        """
        分析缺失索引（基于全表扫描次数）

        参数:
            database: 数据库名
            table: 表名(可选)

        返回:
            List[Dict]: 缺失索引建议列表
        """
        suggestions = []

        # 查询全表扫描次数较多的表
        query = """
            SELECT
                OBJECT_SCHEMA as db,
                OBJECT_NAME as table_name,
                COUNT_READ as total_reads,
                SUM_TIMER_WAIT / 1000000000000 as total_latency_ms
            FROM performance_schema.table_io_waits_summary_by_table
            WHERE OBJECT_SCHEMA = :db
                AND COUNT_READ > 1000
        """
        params = {"db": database}

        if table:
            query += " AND OBJECT_NAME = :table"
            params["table"] = table

        query += " ORDER BY COUNT_READ DESC LIMIT 20"

        try:
            result = self.connector.execute(query, params)

            for row in result.rows:
                table_name = row[1]
                total_reads = row[2]
                latency_ms = round(row[3] or 0, 2)

                # 检查该表是否有主键
                pk_result = self.connector.execute("""
                    SELECT COUNT(*)
                    FROM information_schema.TABLE_CONSTRAINTS
                    WHERE TABLE_SCHEMA = :db
                        AND TABLE_NAME = :table
                        AND CONSTRAINT_TYPE = 'PRIMARY KEY'
                """, {"db": database, "table": table_name})

                has_pk = pk_result.rows[0][0] > 0 if pk_result.rows else False

                if not has_pk:
                    suggestions.append({
                        "type": "missing_primary_key",
                        "priority": "high",
                        "table": table_name,
                        "description": f"表 {table_name} 缺少主键，建议添加自增主键",
                        "impact": f"全表扫描 {total_reads} 次，延迟 {latency_ms}ms",
                        "suggestion": f"ALTER TABLE {table_name} ADD COLUMN id INT AUTO_INCREMENT PRIMARY KEY;",
                        "reason": "无主键的表在查询和更新时性能较差"
                    })

        except Exception as e:
            logger.warning(f"查询全表扫描统计失败: {e}")

        return suggestions

    def _analyze_redundant_indexes_mysql(self, database: str, table: str = None) -> List[Dict[str, Any]]:
        """
        分析冗余索引

        参数:
            database: 数据库名
            table: 表名(可选)

        返回:
            List[Dict]: 冗余索引建议列表
        """
        suggestions = []

        # 查询可能的冗余索引（前缀重复）
        query = """
            SELECT
                t.TABLE_NAME,
                t.INDEX_NAME,
                t.COLUMN_NAME,
                t.SEQ_IN_INDEX,
                t2.INDEX_NAME as redundant_to,
                t2.COLUMN_NAME as redundant_col
            FROM information_schema.STATISTICS t
            JOIN information_schema.STATISTICS t2
                ON t.TABLE_SCHEMA = t2.TABLE_SCHEMA
                AND t.TABLE_NAME = t2.TABLE_NAME
                AND t.COLUMN_NAME = t2.COLUMN_NAME
                AND t.SEQ_IN_INDEX = t2.SEQ_IN_INDEX
                AND t.INDEX_NAME != t2.INDEX_NAME
            WHERE t.TABLE_SCHEMA = :db
                AND t.NON_UNIQUE = 1
        """
        params = {"db": database}

        if table:
            query += " AND t.TABLE_NAME = :table"
            params["table"] = table

        try:
            result = self.connector.execute(query, params)

            seen = set()
            for row in result.rows:
                table_name = row[0]
                index_name = row[1]
                redundant_to = row[4]
                key = (table_name, index_name, redundant_to)

                if key not in seen:
                    seen.add(key)
                    suggestions.append({
                        "type": "redundant_index",
                        "priority": "medium",
                        "table": table_name,
                        "index": index_name,
                        "description": f"索引 {index_name} 可能是冗余的",
                        "suggestion": f"DROP INDEX {index_name} ON {table_name};",
                        "reason": f"该索引与 {redundant_to} 有重复前缀",
                        "note": "请先确认该索引确实未被使用后再删除"
                    })

        except Exception as e:
            logger.warning(f"查询冗余索引失败: {e}")

        return suggestions

    def _analyze_unused_indexes_mysql(self, database: str, table: str = None) -> List[Dict[str, Any]]:
        """
        分析未使用索引

        参数:
            database: 数据库名
            table: 表名(可选)

        返回:
            List[Dict]: 未使用索引建议列表
        """
        suggestions = []

        # 查询未使用的索引（需要开启performance_schema）
        query = """
            SELECT
                OBJECT_SCHEMA,
                OBJECT_NAME,
                INDEX_NAME,
                COUNT_FETCH,
                COUNT_INSERT,
                COUNT_UPDATE,
                COUNT_DELETE
            FROM performance_schema.table_io_waits_summary_by_index_usage
            WHERE OBJECT_SCHEMA = :db
                AND INDEX_NAME IS NOT NULL
                AND COUNT_FETCH = 0
                AND COUNT_INSERT = 0
                AND COUNT_UPDATE = 0
                AND COUNT_DELETE = 0
        """
        params = {"db": database}

        if table:
            query += " AND OBJECT_NAME = :table"
            params["table"] = table

        query += " LIMIT 20"

        try:
            result = self.connector.execute(query, params)

            for row in result.rows:
                table_name = row[1]
                index_name = row[2]

                # 排除主键
                if index_name == 'PRIMARY':
                    continue

                suggestions.append({
                    "type": "unused_index",
                    "priority": "low",
                    "table": table_name,
                    "index": index_name,
                    "description": f"索引 {index_name} 从未被使用",
                    "suggestion": f"DROP INDEX {index_name} ON {table_name};",
                    "reason": "该索引自服务器启动以来从未被使用",
                    "note": "建议观察一段时间后再删除，避免误删周期性使用的索引"
                })

        except Exception as e:
            logger.warning(f"查询未使用索引失败: {e}")

        return suggestions

    def _analyze_low_cardinality_indexes_mysql(self, database: str, table: str = None) -> List[Dict[str, Any]]:
        """
        分析低基数索引（选择性差的索引）

        参数:
            database: 数据库名
            table: 表名(可选)

        返回:
            List[Dict]: 低基数索引建议列表
        """
        suggestions = []

        # 获取所有索引及其基数信息
        query = """
            SELECT
                TABLE_NAME,
                INDEX_NAME,
                COLUMN_NAME,
                CARDINALITY
            FROM information_schema.STATISTICS
            WHERE TABLE_SCHEMA = :db
                AND NON_UNIQUE = 1
                AND CARDINALITY IS NOT NULL
                AND CARDINALITY < 10
        """
        params = {"db": database}

        if table:
            query += " AND TABLE_NAME = :table"
            params["table"] = table

        try:
            result = self.connector.execute(query, params)

            for row in result.rows:
                table_name = row[0]
                index_name = row[1]
                column_name = row[2]
                cardinality = row[3]

                suggestions.append({
                    "type": "low_cardinality",
                    "priority": "low",
                    "table": table_name,
                    "index": index_name,
                    "column": column_name,
                    "description": f"索引 {index_name} 选择性较差",
                    "cardinality": cardinality,
                    "reason": f"基数仅为 {cardinality}，索引效果不佳",
                    "note": "考虑是否需要该索引，或者使用复合索引"
                })

        except Exception as e:
            logger.warning(f"查询低基数索引失败: {e}")

        return suggestions

    # ==================== Oracle索引推荐方法 ====================

    def _recommend_oracle_indexes(self, table: str = None) -> Dict[str, Any]:
        """
        Oracle索引建议

        分析维度：
        1. 缺失索引（基于AWR和v$sql）
        2. 冗余索引（重复索引、包含索引）
        3. 未使用索引（基于v$object_usage）
        4. 低选择性索引（索引选择性差）

        参数:
            table: 指定表名

        返回:
            Dict: 索引建议结果
        """
        try:
            # 表名安全验证
            if table and not self._is_valid_table_name(table):
                return create_error_response(
                    f"无效的表名: {table}",
                    ErrorCode.INVALID_PARAM
                )

            suggestions = []

            # 获取当前用户
            current_user = None
            try:
                result = self.connector.execute("SELECT USER FROM DUAL")
                if result.rows:
                    current_user = result.rows[0][0]
            except Exception:
                pass

            if not current_user:
                return create_error_response(
                    "无法获取当前用户",
                    ErrorCode.UNKNOWN_ERROR
                )

            # 1. 分析缺失索引（基于AWR）
            try:
                missing_indexes = self._analyze_missing_indexes_oracle(current_user, table)
                suggestions.extend(missing_indexes)
            except Exception as e:
                logger.warning(f"分析缺失索引失败: {e}")

            # 2. 分析冗余索引
            try:
                redundant_indexes = self._analyze_redundant_indexes_oracle(current_user, table)
                suggestions.extend(redundant_indexes)
            except Exception as e:
                logger.warning(f"分析冗余索引失败: {e}")

            # 3. 分析未使用索引
            try:
                unused_indexes = self._analyze_unused_indexes_oracle(current_user, table)
                suggestions.extend(unused_indexes)
            except Exception as e:
                logger.warning(f"分析未使用索引失败: {e}")

            # 4. 分析低选择性索引
            try:
                low_selectivity = self._analyze_low_selectivity_indexes_oracle(current_user, table)
                suggestions.extend(low_selectivity)
            except Exception as e:
                logger.warning(f"分析低选择性索引失败: {e}")

            # 按优先级排序
            priority_order = {"high": 0, "medium": 1, "low": 2}
            suggestions.sort(
                key=lambda x: priority_order.get(x.get("priority", "low"), 2)
            )

            return create_success_response(
                message=f"发现 {len(suggestions)} 个索引建议",
                data={
                    "database": current_user,
                    "user": current_user,
                    "table": table,
                    "suggestions": suggestions,
                    "summary": {
                        "total": len(suggestions),
                        "high_priority": len([s for s in suggestions if s.get("priority") == "high"]),
                        "medium_priority": len([s for s in suggestions if s.get("priority") == "medium"]),
                        "low_priority": len([s for s in suggestions if s.get("priority") == "low"])
                    }
                }
            )

        except Exception as e:
            logger.error(f"Oracle索引建议失败: {e}")
            return create_error_response(str(e), ErrorCode.UNKNOWN_ERROR)

    def _analyze_missing_indexes_oracle(self, user: str, table: str = None) -> List[Dict[str, Any]]:
        """
        分析Oracle缺失索引（基于AWR）

        参数:
            user: 用户名
            table: 表名(可选)

        返回:
            List[Dict]: 缺失索引建议列表
        """
        suggestions = []

        try:
            # 检查AWR是否可用
            result = self.connector.execute("""
                SELECT COUNT(*) FROM dba_hist_snapshot WHERE ROWNUM = 1
            """)
            has_awr = result and result.rows and result.rows[0][0] > 0

            if has_awr:
                # 使用AWR分析高成本SQL
                query = """
                    SELECT * FROM (
                        SELECT
                            s.sql_id,
                            t.sql_text,
                            s.executions_delta,
                            s.elapsed_time_delta / 1000000 as elapsed_sec,
                            s.buffer_gets_delta,
                            s.disk_reads_delta
                        FROM dba_hist_sqlstat s
                        JOIN dba_hist_sqltext t ON s.sql_id = t.sql_id
                        WHERE s.snap_id IN (
                            SELECT snap_id FROM dba_hist_snapshot
                            WHERE begin_interval_time >= SYSDATE - 1
                        )
                        AND s.elapsed_time_delta / 1000000 > 1.0
                        AND t.sql_text LIKE '%SELECT%'
                        ORDER BY s.elapsed_time_delta DESC
                    )
                    WHERE ROWNUM <= 20
                """
            else:
                # 使用v$sql分析（elapsed_time是累积总时间，需除以executions得到平均时间）
                query = """
                    SELECT * FROM (
                        SELECT
                            sql_id,
                            sql_text,
                            executions,
                            elapsed_time / 1000000 as total_elapsed_sec,
                            CASE
                                WHEN executions > 0
                                THEN ROUND(elapsed_time / executions / 1000000, 2)
                                ELSE ROUND(elapsed_time / 1000000, 2)
                            END AS avg_elapsed_sec,
                            buffer_gets,
                            disk_reads
                        FROM v$sql
                        WHERE executions > 0
                        AND elapsed_time / executions / 1000000 > 1.0
                        AND sql_text LIKE '%SELECT%'
                        ORDER BY avg_elapsed_sec DESC
                    )
                    WHERE ROWNUM <= 20
                """

            result = self.connector.execute(query)

            for row in result.rows:
                sql_text = row[1]
                executions = int(str(row[2])) if row[2] else 0
                total_elapsed = float(str(row[3])) if row[3] else 0
                avg_elapsed = float(str(row[4])) if row[4] else 0

                if 'WHERE' in sql_text.upper():
                    suggestions.append({
                        "type": "missing_index",
                        "priority": "high" if avg_elapsed > 10 else "medium",
                        "sql_id": row[0],
                        "sql_preview": sql_text[:100] + "..." if len(sql_text) > 100 else sql_text,
                        "executions": executions,
                        "elapsed_sec": avg_elapsed,
                        "total_elapsed_sec": round(total_elapsed, 2),
                        "description": "高成本查询可能需要索引优化",
                        "reason": f"该查询平均耗时 {avg_elapsed:.2f} 秒（总耗时 {total_elapsed:.0f} 秒，执行 {executions} 次），建议分析执行计划",
                        "suggestion": "使用EXPLAIN PLAN分析SQL执行计划，考虑在WHERE条件列上创建索引"
                    })

        except Exception as e:
            logger.warning(f"分析缺失索引失败: {e}")

        return suggestions

    def _analyze_redundant_indexes_oracle(self, user: str, table: str = None) -> List[Dict[str, Any]]:
        """
        分析Oracle冗余索引

        参数:
            user: 用户名
            table: 表名(可选)

        返回:
            List[Dict]: 冗余索引建议列表
        """
        suggestions = []

        try:
            # 查找重复索引（相同列组合）
            query = """
                SELECT
                    t.table_name,
                    t.index_name,
                    t.column_name,
                    t.column_position
                FROM user_ind_columns t
                WHERE t.table_name NOT LIKE 'BIN$%'
                ORDER BY t.table_name, t.column_name, t.column_position
            """

            if table:
                query = f"""
                    SELECT
                        t.table_name,
                        t.index_name,
                        t.column_name,
                        t.column_position
                    FROM user_ind_columns t
                    WHERE t.table_name = '{table.upper()}'
                    ORDER BY t.table_name, t.column_name, t.column_position
                """

            result = self.connector.execute(query)

            # 构建索引列映射（按表分组）
            table_indexes = {}
            for row in result.rows:
                table_name = row[0]
                index_name = row[1]
                column_name = row[2]
                position = int(str(row[3])) if row[3] else 0

                if table_name not in table_indexes:
                    table_indexes[table_name] = {}
                key = f"{table_name}.{index_name}"
                if key not in table_indexes[table_name]:
                    table_indexes[table_name][key] = []
                table_indexes[table_name][key].append((position, column_name))

            # 在同一张表内查找重复索引和前缀索引
            for table_name, indexes in table_indexes.items():
                # 构建列组合映射
                seen_columns = {}
                for key, columns in indexes.items():
                    columns.sort(key=lambda x: x[0])
                    column_str = ','.join([c[1] for c in columns])

                    # 检查完全重复
                    if column_str in seen_columns:
                        _, index_name = key.split('.', 1)
                        duplicate_key = seen_columns[column_str]
                        _, dup_index_name = duplicate_key.split('.', 1)
                        suggestions.append({
                            "type": "redundant_index",
                            "priority": "medium",
                            "table": table_name,
                            "index": index_name,
                            "columns": column_str,
                            "description": f"索引 {index_name} 与 {dup_index_name} 重复",
                            "reason": "两个索引包含相同的列组合",
                            "suggestion": f"考虑删除索引 {index_name}，保留 {dup_index_name}"
                        })
                    else:
                        seen_columns[column_str] = key

                # 检查前缀索引（索引A的列是索引B的前缀）
                sorted_keys = sorted(seen_columns.items(), key=lambda x: len(x[0]))
                for i, (col_str_a, key_a) in enumerate(sorted_keys):
                    for col_str_b, key_b in sorted_keys[i+1:]:
                        if col_str_b.startswith(col_str_a + ','):
                            _, idx_name_a = key_a.split('.', 1)
                            _, idx_name_b = key_b.split('.', 1)
                            # 跳过主键索引和唯一约束索引
                            if idx_name_a.startswith('PK_') or idx_name_a.startswith('SYS_C'):
                                continue
                            suggestions.append({
                                "type": "redundant_index",
                                "priority": "low",
                                "table": table_name,
                                "index": idx_name_a,
                                "columns": col_str_a,
                                "description": f"索引 {idx_name_a} 是 {idx_name_b} 的前缀索引",
                                "reason": f"索引 {idx_name_a} 的列是 {idx_name_b} 的前缀，后者可替代前者",
                                "suggestion": f"评估是否可以删除索引 {idx_name_a}，保留 {idx_name_b}"
                            })

        except Exception as e:
            logger.warning(f"分析冗余索引失败: {e}")

        return suggestions

    def _analyze_unused_indexes_oracle(self, user: str, table: str = None) -> List[Dict[str, Any]]:
        """
        分析Oracle未使用索引

        参数:
            user: 用户名
            table: 表名(可选)

        返回:
            List[Dict]: 未使用索引建议列表
        """
        suggestions = []

        try:
            # 查询未使用索引（v$object_usage自动记录索引使用情况）
            query = """
                SELECT
                    io.table_name,
                    io.index_name,
                    io.monitoring,
                    io.used,
                    io.start_monitoring,
                    io.end_monitoring
                FROM v$object_usage io
                WHERE io.used = 'NO'
                AND io.monitoring = 'YES'
            """

            if table:
                query += f" AND io.table_name = '{table.upper()}'"

            result = self.connector.execute(query)

            for row in result.rows:
                table_name = row[0]
                index_name = row[1]
                start_monitoring = row[4]

                suggestions.append({
                    "type": "unused_index",
                    "priority": "low",
                    "table": table_name,
                    "index": index_name,
                    "description": f"索引 {index_name} 未被使用",
                    "monitoring_start": str(start_monitoring) if start_monitoring else None,
                    "reason": "自监控开始以来，该索引从未被使用",
                    "suggestion": "如果确认不需要该索引，可以考虑删除以节省空间和维护成本"
                })

        except Exception as e:
            logger.warning(f"分析未使用索引失败: {e}")

        return suggestions

    def _analyze_low_selectivity_indexes_oracle(self, user: str, table: str = None) -> List[Dict[str, Any]]:
        """
        分析Oracle低选择性索引

        参数:
            user: 用户名
            table: 表名(可选)

        返回:
            List[Dict]: 低选择性索引建议列表
        """
        suggestions = []

        try:
            # 查询索引选择性
            query = """
                SELECT
                    t.table_name,
                    t.index_name,
                    t.distinct_keys,
                    t.num_rows,
                    CASE
                        WHEN t.num_rows > 0 THEN ROUND(t.distinct_keys / t.num_rows * 100, 2)
                        ELSE 0
                    END as selectivity
                FROM user_ind_statistics t
                WHERE t.num_rows > 1000
                AND t.distinct_keys > 0
            """

            if table:
                query += f" AND t.table_name = '{table.upper()}'"

            query += " ORDER BY selectivity ASC"

            result = self.connector.execute(query)

            for row in result.rows:
                table_name = row[0]
                index_name = row[1]
                distinct_keys = int(str(row[2])) if row[2] else 0
                num_rows = int(str(row[3])) if row[3] else 0
                selectivity = float(str(row[4])) if row[4] else 0

                # 选择性低于1%认为是不好的索引
                if selectivity < 1.0:
                    suggestions.append({
                        "type": "low_selectivity",
                        "priority": "low",
                        "table": table_name,
                        "index": index_name,
                        "distinct_keys": distinct_keys,
                        "total_rows": num_rows,
                        "selectivity_percent": selectivity,
                        "description": f"索引 {index_name} 选择性较差",
                        "reason": f"选择性仅为 {selectivity}%，索引效果不佳",
                        "suggestion": "考虑是否需要该索引，或者使用位图索引（如果是数据仓库）"
                    })

        except Exception as e:
            logger.warning(f"分析低选择性索引失败: {e}")

        return suggestions

    def _analyze_redundant_indexes_postgresql(self, table: str = None) -> List[Dict[str, Any]]:
        """
        分析PostgreSQL冗余索引

        检测以下冗余情况：
        1. 完全重复的索引（相同列、相同顺序）
        2. 前缀冗余（索引A的列是索引B列的前缀）

        参数:
            table: 指定表名(可选)

        返回:
            List[Dict]: 冗余索引建议列表
        """
        suggestions = []

        try:
            table_filter = f" AND n.nspname || '.' || t.relname = '{table}'" if table else ""

            # 查询所有索引及其列信息
            result = self.connector.execute(f"""
                SELECT
                    n.nspname || '.' || t.relname AS table_name,
                    i.relname AS index_name,
                    array_agg(a.attname ORDER BY array_position(ix.indkey, a.attnum)) AS columns,
                    ix.indisunique AS is_unique,
                    ix.indisprimary AS is_primary
                FROM pg_index ix
                JOIN pg_class t ON t.oid = ix.indrelid
                JOIN pg_class i ON i.oid = ix.indexrelid
                JOIN pg_namespace n ON n.oid = t.relnamespace
                JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = ANY(ix.indkey)
                WHERE n.nspname NOT IN ('pg_catalog', 'information_schema', 'pg_toast')
                {table_filter}
                GROUP BY n.nspname, t.relname, i.relname, ix.indisunique, ix.indisprimary
                ORDER BY table_name, index_name
            """)

            # 按表分组分析
            indexes_by_table = {}
            for row in result.rows if result else []:
                table_name = str(row[0])
                index_name = str(row[1])
                columns = row[2] if row[2] else []
                is_unique = row[3] if row[3] else False
                is_primary = row[4] if row[4] else False

                if table_name not in indexes_by_table:
                    indexes_by_table[table_name] = []
                indexes_by_table[table_name].append({
                    'name': index_name,
                    'columns': columns,
                    'is_unique': is_unique,
                    'is_primary': is_primary
                })

            # 检测冗余
            for table_name, indexes in indexes_by_table.items():
                for i, idx1 in enumerate(indexes):
                    for j, idx2 in enumerate(indexes):
                        if i >= j:
                            continue

                        # 跳过主键和唯一索引
                        if idx1['is_primary'] or idx2['is_primary']:
                            continue

                        cols1 = idx1['columns']
                        cols2 = idx2['columns']

                        # 检测完全重复
                        if cols1 == cols2:
                            # 保留唯一索引，删除普通索引
                            if idx1['is_unique'] and not idx2['is_unique']:
                                redundant = idx2
                                keeper = idx1
                            elif idx2['is_unique'] and not idx1['is_unique']:
                                redundant = idx1
                                keeper = idx2
                            else:
                                # 都非唯一，保留名称较短的
                                redundant = idx1 if len(idx1['name']) > len(idx2['name']) else idx2
                                keeper = idx2 if redundant == idx1 else idx1

                            suggestions.append({
                                "type": "redundant_index",
                                "priority": "medium",
                                "table": table_name,
                                "index": redundant['name'],
                                "description": f"索引 {redundant['name']} 与 {keeper['name']} 完全重复",
                                "columns": cols1,
                                "suggestion": f"DROP INDEX {redundant['name']};",
                                "reason": f"与索引 {keeper['name']} 列完全相同，可以删除"
                            })

                        # 检测前缀冗余（idx1是idx2的前缀）
                        elif len(cols1) < len(cols2) and cols2[:len(cols1)] == cols1:
                            # idx1是idx2的前缀，idx1可能是冗余的
                            if not idx1['is_unique']:  # 不删除唯一索引
                                suggestions.append({
                                    "type": "prefix_redundant",
                                    "priority": "low",
                                    "table": table_name,
                                    "index": idx1['name'],
                                    "description": f"索引 {idx1['name']} 是 {idx2['name']} 的前缀",
                                    "columns": cols1,
                                    "suggestion": f"考虑删除 {idx1['name']}，因为 {idx2['name']} 可以覆盖",
                                    "reason": f"{idx2['name']} 包含相同的列前缀，可以替代此索引"
                                })

                        # 检测前缀冗余（idx2是idx1的前缀）
                        elif len(cols2) < len(cols1) and cols1[:len(cols2)] == cols2:
                            if not idx2['is_unique']:
                                suggestions.append({
                                    "type": "prefix_redundant",
                                    "priority": "low",
                                    "table": table_name,
                                    "index": idx2['name'],
                                    "description": f"索引 {idx2['name']} 是 {idx1['name']} 的前缀",
                                    "columns": cols2,
                                    "suggestion": f"考虑删除 {idx2['name']}，因为 {idx1['name']} 可以覆盖",
                                    "reason": f"{idx1['name']} 包含相同的列前缀，可以替代此索引"
                                })

        except Exception as e:
            logger.warning(f"分析冗余索引失败: {e}")

        return suggestions

    def _analyze_low_cardinality_indexes_postgresql(self, table: str = None) -> List[Dict[str, Any]]:
        """
        分析PostgreSQL低基数索引

        检测基数很低的索引（如性别、状态等只有几个值的列）
        这类索引通常效果不佳，因为选择性太差

        参数:
            table: 指定表名(可选)

        返回:
            List[Dict]: 低基数索引建议列表
        """
        suggestions = []

        try:
            table_filter = f" AND schemaname || '.' || relname = '{table}'" if table else ""

            # 查询索引统计信息
            result = self.connector.execute(f"""
                SELECT
                    schemaname || '.' || t.relname AS table_name,
                    i.relname AS index_name,
                    a.attname AS column_name,
                    t.reltuples::bigint AS table_rows,
                    s.n_distinct AS distinct_values,
                    s.null_frac AS null_fraction,
                    CASE
                        WHEN s.n_distinct > 0 THEN s.n_distinct
                        WHEN s.n_distinct < 0 THEN ABS(s.n_distinct) * t.reltuples
                        ELSE 0
                    END AS estimated_distinct
                FROM pg_stats s
                JOIN pg_class t ON t.relname = s.tablename
                JOIN pg_namespace n ON n.oid = t.relnamespace AND n.nspname = s.schemaname
                JOIN pg_index ix ON ix.indrelid = t.oid
                JOIN pg_class i ON i.oid = ix.indexrelid
                JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = ANY(ix.indkey)
                WHERE s.schemaname NOT IN ('pg_catalog', 'information_schema', 'pg_toast')
                AND array_position(ix.indkey, a.attnum) = 0  -- 只考虑索引的第一列
                AND t.reltuples > 1000  -- 只分析大表
                {table_filter}
                ORDER BY table_name, index_name
            """)

            for row in result.rows if result else []:
                table_name = str(row[0])
                index_name = str(row[1])
                column_name = str(row[2])
                table_rows = int(str(row[3])) if row[3] else 0
                distinct_values = float(str(row[6])) if row[6] else 0
                null_fraction = float(str(row[5])) if row[5] else 0

                # 计算选择性
                if table_rows > 0:
                    selectivity = (distinct_values / table_rows) * 100
                else:
                    selectivity = 0

                # 选择性低于1%认为是低基数索引
                if selectivity < 1.0 and distinct_values < 10:
                    suggestions.append({
                        "type": "low_cardinality",
                        "priority": "low",
                        "table": table_name,
                        "index": index_name,
                        "column": column_name,
                        "distinct_values": int(distinct_values),
                        "total_rows": table_rows,
                        "selectivity_percent": round(selectivity, 2),
                        "description": f"索引 {index_name} 列 {column_name} 基数很低",
                        "reason": f"只有 {int(distinct_values)} 个不同值，选择性 {selectivity:.2f}%",
                        "suggestion": "考虑使用位图索引（如果适用）或重新评估索引必要性"
                    })

        except Exception as e:
            logger.warning(f"分析低基数索引失败: {e}")

        return suggestions

    # ==================== 统一性能模型诊断方法 ====================

    def _get_performance_analyzer(self):
        """
        获取对应数据库的性能分析器

        返回:
            PerformanceAnalyzer实例或None
        """
        if 'mysql' in self.dialect:
            from .diagnosticians.mysql_performance_analyzer import MySQLPerformanceAnalyzer
            return MySQLPerformanceAnalyzer(self.connector, timeout=30)
        elif 'oracle' in self.dialect:
            from .diagnosticians.oracle_performance_analyzer import OraclePerformanceAnalyzer
            return OraclePerformanceAnalyzer(self.connector, timeout=30)
        elif 'postgresql' in self.dialect:
            from .diagnosticians.postgresql_performance_analyzer import PostgreSQLPerformanceAnalyzer
            return PostgreSQLPerformanceAnalyzer(self.connector, timeout=30)
        else:
            return None

    def take_performance_snapshot(self) -> Dict[str, Any]:
        """
        采集性能快照（基于统一性能模型）

        返回:
            Dict: 性能快照数据
        """
        try:
            analyzer = self._get_performance_analyzer()

            if not analyzer:
                return create_error_response(
                    f"统一性能模型暂不支持 {self.dialect}",
                    ErrorCode.UNSUPPORTED_SQL
                )

            snapshot = analyzer.take_snapshot()
            bottlenecks = analyzer.analyze_bottleneck(snapshot)

            return create_success_response(
                message="性能快照采集完成",
                data={
                    "snapshot": snapshot.to_dict(),
                    "bottlenecks": bottlenecks,
                    "summary": {
                        "total_metrics": len(snapshot.metrics),
                        "total_slow_queries": len(snapshot.slow_queries),
                        "active_sessions": snapshot.active_sessions,
                        "total_sessions": snapshot.total_sessions
                    }
                }
            )

        except Exception as e:
            logger.error(f"性能快照采集失败: {e}")
            return create_error_response(str(e), ErrorCode.PERF_ANALYSIS_FAILED)

    def analyze_performance_bottleneck(self) -> Dict[str, Any]:
        """
        分析性能瓶颈（基于统一性能模型）

        返回:
            Dict: 瓶颈分析结果
        """
        try:
            analyzer = self._get_performance_analyzer()

            if not analyzer:
                return create_error_response(
                    f"性能瓶颈分析暂不支持 {self.dialect}",
                    ErrorCode.UNSUPPORTED_SQL
                )

            snapshot = analyzer.take_snapshot()
            bottlenecks = analyzer.analyze_bottleneck(snapshot)

            return create_success_response(
                message=f"发现 {len(bottlenecks)} 个性能瓶颈",
                data={
                    "bottlenecks": bottlenecks,
                    "severity_summary": self._summarize_severity(bottlenecks),
                    "recommendations": self._generate_recommendations(bottlenecks)
                }
            )

        except Exception as e:
            logger.error(f"性能瓶颈分析失败: {e}")
            return create_error_response(str(e), ErrorCode.PERF_ANALYSIS_FAILED)

    def _summarize_severity(self, bottlenecks: List[Dict]) -> Dict[str, int]:
        """汇总严重程度"""
        summary = {"critical": 0, "high": 0, "medium": 0, "low": 0}
        for b in bottlenecks:
            severity = b.get("severity", "low")
            if severity in summary:
                summary[severity] += 1
        return summary

    def _generate_recommendations(self, bottlenecks: List[Dict]) -> List[str]:
        """生成优化建议"""
        recommendations = []

        for bottleneck in bottlenecks:
            category = bottleneck.get("category", "")
            suggestion = bottleneck.get("suggestion", "")

            if suggestion:
                recommendations.append(f"[{category}] {suggestion}")

        return recommendations

    def _is_valid_table_name(self, table: str) -> bool:
        """
        验证表名是否合法（防止SQL注入）

        参数:
            table: 表名

        返回:
            bool: 是否合法

        验证规则:
            - 只允许字母、数字、下划线、点号、美元符号
            - 不允许连续的点号
            - 不允许以点号开头或结尾
        """
        if not table:
            return True  # 空表名视为有效（表示不指定表）

        # 清理后检查是否只包含合法字符
        # 支持schema.table格式和Oracle的$符号
        cleaned = table.replace('.', '').replace('_', '').replace('-', '').replace('$', '')
        if not cleaned.isalnum():
            return False

        # 检查点号使用是否合法
        if '..' in table:
            return False
        if table.startswith('.') or table.endswith('.'):
            return False

        return True

    # ==================== PostgreSQL特有诊断方法 ====================

    def analyze_vacuum(self) -> Dict[str, Any]:
        """
        分析PostgreSQL VACUUM状态

        检查表的自动清理状态和死元组情况

        返回:
            Dict: VACUUM状态分析结果
        """
        try:
            if 'postgresql' not in self.dialect:
                return create_error_response(
                    f"VACUUM分析仅支持PostgreSQL，当前数据库: {self.dialect}",
                    ErrorCode.UNSUPPORTED_SQL
                )

            if self._diagnostician:
                result = self._diagnostician.analyze_vacuum_status()
                return self._convert_diagnostician_result(result)
            else:
                return create_error_response(
                    "VACUUM分析需要PostgreSQL诊断器",
                    ErrorCode.UNKNOWN_ERROR
                )
        except Exception as e:
            logger.error(f"VACUUM分析失败: {e}")
            return create_error_response(str(e), ErrorCode.UNKNOWN_ERROR)

    def analyze_bloat(self, threshold: int = 30) -> Dict[str, Any]:
        """
        分析表膨胀/碎片情况

        PostgreSQL: 检测MVCC导致的表膨胀
        MySQL: 检测InnoDB表碎片
        Oracle: 检测表空间碎片

        参数:
            threshold: 膨胀率阈值（百分比，默认30）

        返回:
            Dict: 表膨胀/碎片分析结果，统一包含以下字段:
                - tables: 需要关注的表/表空间列表（标准化格式）
                - health_score: 健康评分(0-100)
                - total_wasted_space_mb: 总浪费空间
                - suggestions: 优化建议
                - actionable_commands: 可执行的维护命令
                - db_type: 数据库类型标签
        """
        try:
            if self._diagnostician:
                if 'postgresql' in self.dialect:
                    result = self._diagnostician.analyze_table_bloat(threshold=threshold)
                    db_label = "PostgreSQL"
                elif 'mysql' in self.dialect:
                    result = self._diagnostician.analyze_table_fragmentation()
                    db_label = "MySQL"
                elif 'oracle' in self.dialect:
                    result = self._diagnostician.analyze_tablespace_fragmentation()
                    db_label = "Oracle"
                else:
                    return create_error_response(
                        f"膨胀/碎片分析暂不支持 {self.dialect}",
                        ErrorCode.UNSUPPORTED_SQL
                    )

                standardized = self._convert_diagnostician_result(result)

                # 标准化数据字段名，统一为CLI可解析的格式
                if standardized.get("success") and standardized.get("data"):
                    data = standardized["data"]
                    data["db_type"] = db_label

                    # 将不同数据库的字段名统一为 bloated_tables
                    if "fragmented_tables" in data and "bloated_tables" not in data:
                        data["bloated_tables"] = data["fragmented_tables"]
                    if "fragmented_tablespaces" in data and "bloated_tables" not in data:
                        data["bloated_tables"] = data["fragmented_tablespaces"]

                    # 统一 total_wasted_space 字段
                    if "total_wasted_space_mb" in data and "total_wasted_space" not in data:
                        wasted_mb = data["total_wasted_space_mb"]
                        if isinstance(wasted_mb, (int, float)):
                            if wasted_mb >= 1024:
                                data["total_wasted_space"] = f"{wasted_mb / 1024:.2f} GB"
                            else:
                                data["total_wasted_space"] = f"{wasted_mb:.2f} MB"
                        else:
                            data["total_wasted_space"] = str(wasted_mb)

                    # 统一 severely_bloated_count
                    if "severely_bloated_count" not in data:
                        data["severely_bloated_count"] = sum(
                            1 for t in data.get("bloated_tables", [])
                            if t.get("priority") == "high"
                        )

                return standardized
            else:
                return create_error_response(
                    "膨胀/碎片分析需要诊断器",
                    ErrorCode.UNKNOWN_ERROR
                )
        except Exception as e:
            logger.error(f"膨胀/碎片分析失败: {e}")
            return create_error_response(str(e), ErrorCode.UNKNOWN_ERROR)

    def analyze_index_usage(self) -> Dict[str, Any]:
        """
        分析索引使用情况

        识别未使用或低效的索引，以及可能缺少索引的表

        返回:
            Dict: 索引使用分析结果
        """
        try:
            if self._diagnostician:
                result = self._diagnostician.analyze_index_usage()
                standardized = self._convert_diagnostician_result(result)

                # 添加数据库类型标签
                if standardized.get("success") and standardized.get("data"):
                    db_label = self.dialect.split('+')[0].title()
                    standardized["data"]["db_type"] = db_label

                return standardized
            else:
                return create_error_response(
                    "索引使用分析需要诊断器",
                    ErrorCode.UNKNOWN_ERROR
                )
        except Exception as e:
            logger.error(f"索引使用分析失败: {e}")
            return create_error_response(str(e), ErrorCode.UNKNOWN_ERROR)

    def analyze_tablespace_fragmentation(self) -> Dict[str, Any]:
        """
        分析Oracle表空间碎片情况

        仅支持Oracle数据库

        返回:
            Dict: 表空间碎片分析结果
        """
        try:
            if 'oracle' not in self.dialect:
                return create_error_response(
                    f"表空间碎片分析仅支持Oracle，当前数据库: {self.dialect}",
                    ErrorCode.UNSUPPORTED_SQL
                )

            if self._diagnostician:
                result = self._diagnostician.analyze_tablespace_fragmentation()
                return self._convert_diagnostician_result(result)
            else:
                return create_error_response(
                    "表空间碎片分析需要Oracle诊断器",
                    ErrorCode.UNKNOWN_ERROR
                )
        except Exception as e:
            logger.error(f"表空间碎片分析失败: {e}")
            return create_error_response(str(e), ErrorCode.UNKNOWN_ERROR)


