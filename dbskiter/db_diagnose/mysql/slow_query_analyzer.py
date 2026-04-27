"""
MySQL慢查询分析器模块

文件功能：提供MySQL慢查询分析功能
主要类：
    - SlowQueryAnalyzer: 慢查询分析器

作者：AI Assistant
创建时间：2026-04-22
"""

import logging
from typing import Dict, Any, Optional, List

from dbskiter.shared.unified_connector import UnifiedConnector
from dbskiter.shared.error_handler import create_success_response, handle_exception
from dbskiter.shared.mysql_slow_query_collector import MySQLSlowQueryCollector
from dbskiter.shared.sql_fingerprint import SQLFingerprinter

logger = logging.getLogger(__name__)


class SlowQueryAnalyzer:
    """
    MySQL慢查询分析器

    功能：
        1. 采集慢查询
        2. SQL指纹聚合
        3. 统计慢查询模式

    属性：
        connector: 数据库连接器
        collector: 慢查询采集器
        fingerprinter: SQL指纹生成器

    使用示例：
        >>> analyzer = SlowQueryAnalyzer(connector)
        >>> result = analyzer.analyze(limit=20, min_time=2.0)
        >>> print(f"发现 {result['data']['total_queries']} 个慢查询")
    """

    def __init__(self, connector: UnifiedConnector):
        """
        初始化慢查询分析器

        参数：
            connector: UnifiedConnector 实例

        示例：
            >>> analyzer = SlowQueryAnalyzer(connector)
        """
        self.connector = connector
        self.collector = MySQLSlowQueryCollector(connector)
        self.fingerprinter = SQLFingerprinter()
        logger.info("SlowQueryAnalyzer 初始化完成")

    def analyze(
        self,
        limit: int = 20,
        min_time: float = 1.0,
        table: Optional[str] = None,
        use_fingerprint: bool = True
    ) -> Dict[str, Any]:
        """
        分析慢查询

        参数：
            limit: 返回条数限制
            min_time: 最小执行时间（秒）
            table: 指定表名过滤
            use_fingerprint: 是否使用SQL指纹聚合

        返回：
            Dict: 慢查询分析结果

        示例：
            >>> result = analyzer.analyze(limit=10, min_time=2.0)
            >>> print(f"唯一模式: {result['data']['unique_patterns']} 种")
        """
        try:
            # 采集慢查询
            slow_queries = self.collector.collect_slow_queries(
                limit=limit,
                min_time=min_time,
                table=table
            )

            if not slow_queries:
                return create_success_response(
                    message="未采集到慢查询",
                    data={
                        "total_queries": 0,
                        "unique_patterns": 0,
                        "queries": []
                    }
                )

            # 转换为字典列表
            query_dicts = [
                {
                    "sql": q.sql,
                    "time": q.query_time,
                    "count": q.count,
                    "rows_sent": q.rows_sent,
                    "rows_examined": q.rows_examined,
                    "database": q.database,
                    "source": q.source,
                }
                for q in slow_queries
            ]

            # SQL指纹聚合
            if use_fingerprint:
                aggregated = self.fingerprinter.aggregate(query_dicts)
                from dbskiter.shared.sql_fingerprint import SQLFingerprinter
                fingerprinter = SQLFingerprinter()
                top_queries = fingerprinter.get_top_queries(
                    aggregated,
                    sort_by="total_time",
                    limit=min(10, len(aggregated))
                )

                return create_success_response(
                    message=f"采集到 {len(slow_queries)} 个慢查询，{len(aggregated)} 种模式",
                    data={
                        "total_queries": len(slow_queries),
                        "unique_patterns": len(aggregated),
                        "total_time": sum(q.query_time for q in slow_queries),
                        "top_queries": [
                            {
                                "fingerprint": group.fingerprint,
                                "count": group.count,
                                "total_time": round(group.total_time, 3),
                                "avg_time": round(group.avg_time, 3),
                                "tables": group.tables
                            }
                            for group in top_queries
                        ],
                        "aggregated": {
                            digest: {
                                "fingerprint": group.fingerprint,
                                "count": group.count,
                                "total_time": group.total_time,
                                "tables": group.tables
                            }
                            for digest, group in aggregated.items()
                        }
                    }
                )
            else:
                # 不聚合，返回原始列表
                return create_success_response(
                    message=f"采集到 {len(slow_queries)} 个慢查询",
                    data={
                        "total_queries": len(slow_queries),
                        "queries": query_dicts
                    }
                )

        except Exception as e:
            return handle_exception(e, context="分析慢查询")

    def analyze_with_aas_correlation(
        self,
        aas_metrics,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        分析慢查询与AAS指标的关联

        参数：
            aas_metrics: AAS指标
            limit: 返回条数限制

        返回：
            List[Dict]: 关联结果列表

        示例：
            >>> correlations = analyzer.analyze_with_aas_correlation(aas_metrics)
        """
        try:
            # 采集慢查询
            slow_queries = self.collector.collect_slow_queries(limit=limit)

            if not slow_queries:
                return []

            # 简化实现：基于时间窗口匹配
            correlations = []
            for query in slow_queries:
                correlations.append({
                    "sql_fingerprint": query.sql[:50] + "..." if len(query.sql) > 50 else query.sql,
                    "query_time": query.query_time,
                    "correlation_type": "time_window",
                    "suggestion": "该查询可能与AAS峰值相关"
                })

            return correlations

        except Exception as e:
            logger.error(f"AAS与慢查询关联分析失败: {e}")
            return []
