"""
ai_context mixin for DiagnoseSkill

Auto-extracted from skill.py.
"""

import logging
from typing import List, Dict, Any, Optional, Set, Tuple

from dbskiter.db_diagnose.models import (
    ErrorCode,
    DiagnoseLevel,
    DiagnoseType,
    DatabaseType,
    DiagnoseConfig,
    DiagnoseResult,
    IndexSuggestion,
    SlowQuery,
    PerformanceMetrics,
    TableDiagnoseResult,
    DiagnoseReport,
)
from dbskiter.shared.error_handler import (
    create_success_response,
    create_error_response,
)


class AiContextMixin:
    """ai_context for DiagnoseSkill"""

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

        inspection_trace = self._build_inspection_trace(scenario, data)

        return {
            "raw_metrics": raw_metrics,
            "rule_flags": rule_flags,
            "context": context,
            "reference_values": reference_values,
            "ai_hints": ai_hints,
            "inspection_trace": inspection_trace,
        }


    def _build_inspection_trace(
        self,
        scenario: str,
        data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        构建诊断透明度追踪信息

        让用户/AI清楚知道本次诊断查了哪些指标、数据来源是什么

        参数:
            scenario: 场景标识
            data: Skill返回的data字段

        返回:
            Dict[str, Any]: 追踪信息，包含 metrics_checked / data_sources / confidence
        """
        trace = {
            "scenario": scenario,
            "metrics_checked": [],
            "data_sources": [],
            "confidence": "high",
            "notes": []
        }

        if scenario == "slow_query":
            trace["metrics_checked"] = [
                {"name": "slow_queries", "description": "执行时间超过阈值的SQL", "source": "performance_schema / slow log"},
                {"name": "query_time", "description": "SQL执行耗时", "source": "performance_schema.events_statements_history_long"},
                {"name": "execution_plan", "description": "执行计划分析", "source": "EXPLAIN 输出"},
            ]
            trace["data_sources"] = ["performance_schema", "slow_query_log"]
            if not data.get("queries") and not data.get("slow_queries"):
                trace["confidence"] = "low"
                trace["notes"].append("未找到慢查询数据，可能未开启慢查询日志或performance_schema")

        elif scenario == "sql_analysis":
            trace["metrics_checked"] = [
                {"name": "sql_text", "description": "SQL语句文本", "source": "用户输入"},
                {"name": "execution_plan", "description": "执行计划", "source": "EXPLAIN"},
                {"name": "index_usage", "description": "索引使用情况", "source": "EXPLAIN / SHOW INDEX"},
            ]
            trace["data_sources"] = ["user_input", "EXPLAIN"]

        elif scenario == "index_recommend":
            trace["metrics_checked"] = [
                {"name": "table_statistics", "description": "表统计信息", "source": "information_schema"},
                {"name": "existing_indexes", "description": "现有索引", "source": "SHOW INDEX"},
                {"name": "column_cardinality", "description": "列基数", "source": "information_schema.statistics"},
            ]
            trace["data_sources"] = ["information_schema", "SHOW INDEX"]

        elif scenario == "bottleneck":
            trace["metrics_checked"] = [
                {"name": "cpu_usage", "description": "CPU使用率", "source": "监控采集器"},
                {"name": "memory_usage", "description": "内存使用", "source": "监控采集器"},
                {"name": "disk_io", "description": "磁盘IO", "source": "监控采集器"},
                {"name": "connection_count", "description": "连接数", "source": "performance_schema / 直连"},
            ]
            trace["data_sources"] = ["monitor_collector", "performance_schema"]
            if self._has_external_monitor():
                trace["notes"].append(f"使用了外部监控源: {self._get_monitor_source()}")
            else:
                trace["notes"].append("使用直连数据库采集指标")

        elif scenario == "realtime":
            trace["metrics_checked"] = [
                {"name": "qps", "description": "每秒查询数", "source": "performance_schema / 状态变量"},
                {"name": "active_connections", "description": "活跃连接数", "source": "performance_schema.threads"},
                {"name": "lock_waits", "description": "锁等待", "source": "performance_schema.metadata_locks"},
            ]
            trace["data_sources"] = ["performance_schema", "status_variables"]

        else:
            trace["metrics_checked"] = [
                {"name": "general_status", "description": "通用状态指标", "source": "自动检测"}
            ]
            trace["data_sources"] = ["auto_detection"]
            trace["notes"].append(f"未定义场景 '{scenario}' 的详细追踪，使用通用指标")

        return trace


    def _has_external_monitor(self) -> bool:
        """检查是否使用了外部监控源"""
        # 简化的检测逻辑，实际可根据配置判断
        return False


    def _get_monitor_source(self) -> str:
        """获取当前使用的监控源名称"""
        return "直连数据库"


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
        # 关闭子组件（如有 close 方法）
        for attr in ('fingerprinter', 'issue_classifier', 'table_analyzer', 'sql_analyzer'):
            comp = getattr(self, attr, None)
            if comp and hasattr(comp, 'close'):
                try:
                    comp.close()
                except Exception as e:
                    logger.debug(f"关闭 {attr} 失败: {e}")
        # 关闭底层连接器
        if self.connector and hasattr(self.connector, 'close'):
            try:
                self.connector.close()
            except Exception as e:
                logger.debug(f"关闭 connector 失败: {e}")
        logger.info("DiagnoseSkill 已关闭")


    # ==================== 新增: 实时诊断方法 (P0高频场景) ====================


