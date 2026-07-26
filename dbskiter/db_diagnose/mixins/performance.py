"""
performance mixin for DiagnoseSkill

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


class PerformanceMixin:
    """performance for DiagnoseSkill"""

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
        elif 'clickhouse' in self.dialect:
            return ClickHousePerformanceAnalyzer(self.connector, timeout=30)
        elif 'sqlite' in self.dialect:
            return SQLitePerformanceAnalyzer(self.connector, timeout=30)
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


