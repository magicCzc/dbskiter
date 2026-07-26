"""
slow_queries mixin for DiagnoseSkill

Auto-extracted from skill.py.
"""

import logging
logger = logging.getLogger(__name__)
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


class SlowQueriesMixin:
    """slow_queries for DiagnoseSkill"""

    def analyze_slow_queries(
        self,
        limit: int = 20,
        min_time: float = 1.0,
        log_file: Optional[str] = None,
        since: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        分析慢查询（多数据库支持，增强版，已接入多步骤计时）

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
                - _execution_time: 步骤耗时（自动注入）
        """
        from dbskiter.shared.execution_timer import ExecutionTimer
        timer = ExecutionTimer().start()

        try:
            if log_file:
                # 日志文件模式
                with timer.step("load_log_file", "加载慢查询日志文件"):
                    from .core.slow_query_analyzer import SlowQueryAnalyzer
                    analyzer = SlowQueryAnalyzer(self.connector)

                with timer.step("parse_log", "解析日志内容"):
                    report = analyzer.analyze_log_file(
                        file_path=log_file,
                        since=since,
                        min_time=min_time
                    )

                result = create_success_response(
                    report.to_dict(),
                    f"日志分析完成: {log_file}"
                )
            else:
                # 实时模式
                with timer.step("db_query", "从数据库采集慢查询"):
                    result = self._diagnostician.analyze_slow_queries(
                        limit=limit,
                        min_time=min_time
                    )

                with timer.step("process_data", "处理并封装结果"):
                    if not isinstance(result, dict):
                        result = {"data": result}
                    if "success" not in result:
                        result = create_success_response(
                            result.get("data", result),
                            "慢查询分析完成"
                        )

            # 注入多步骤耗时
            result["_execution_time"] = timer.to_summary()
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


