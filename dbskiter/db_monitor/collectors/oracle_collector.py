"""
Oracle指标采集器

文件功能：提供Oracle数据库的指标采集功能
主要类：OracleMetricsCollector - Oracle指标采集器

支持的指标：
    - 吞吐量：QPS、事务数、各类SQL操作
    - 连接：活跃连接、总连接数
    - 查询性能：平均执行时间、物理读、逻辑读
    - 锁：锁等待、死锁
    - 缓冲：缓冲区命中率
    - IO：物理读、逻辑读
    - 资源：CPU使用率、临时空间使用率
    - 事务：活跃事务、提交/回滚数

作者：AI Assistant
创建时间：2026-04-23
"""

from typing import Dict
import logging

from .base import BaseMetricsCollector, MetricType, MetricQuery

logger = logging.getLogger(__name__)


class OracleMetricsCollector(BaseMetricsCollector):
    """
    Oracle指标采集器

    提供Oracle特有的性能指标采集
    """

    def get_metric_queries(self) -> Dict[MetricType, MetricQuery]:
        """
        获取Oracle指标查询定义

        返回:
            Dict[MetricType, MetricQuery]: 指标查询定义
        """
        return {
            # 吞吐量指标
            MetricType.QPS: MetricQuery(
                sql="""
                    SELECT value FROM v$sysstat WHERE name = 'execute count'
                """,
                extract=lambda rows: self._safe_extract_float(rows, 0),
                unit="count",
                is_counter=True
            ),
            MetricType.COM_SELECT: MetricQuery(
                sql="""
                    SELECT value FROM v$sysstat WHERE name = 'user calls'
                """,
                extract=lambda rows: self._safe_extract_float(rows, 0),
                unit="count",
                is_counter=True
            ),

            # 连接指标
            MetricType.CONNECTIONS_ACTIVE: MetricQuery(
                sql="""
                    SELECT COUNT(*) FROM v$session WHERE status = 'ACTIVE' AND type = 'USER'
                """,
                extract=lambda rows: self._safe_extract_float(rows, 0),
                unit="count"
            ),
            MetricType.CONNECTIONS_TOTAL: MetricQuery(
                sql="""
                    SELECT COUNT(*) FROM v$session WHERE type = 'USER'
                """,
                extract=lambda rows: self._safe_extract_float(rows, 0),
                unit="count"
            ),
            MetricType.CONNECTIONS_MAX: MetricQuery(
                sql="""
                    SELECT value FROM v$parameter WHERE name = 'processes'
                """,
                extract=lambda rows: self._safe_extract_float(rows, 0),
                unit="count"
            ),

            # 查询性能指标
            MetricType.QUERY_TIME_AVG: MetricQuery(
                sql="""
                    SELECT AVG(elapsed_time / 1000000)
                    FROM v$sql
                    WHERE executions > 0
                """,
                extract=lambda rows: self._safe_extract_float(rows, 0),
                unit="seconds"
            ),
            MetricType.SLOW_QUERIES: MetricQuery(
                sql="""
                    SELECT COUNT(*)
                    FROM v$sql
                    WHERE elapsed_time / executions / 1000000 > 1
                    AND executions > 0
                """,
                extract=lambda rows: self._safe_extract_float(rows, 0),
                unit="count"
            ),

            # 锁指标（使用 v$sysstat 替代 v$lock，避免锁竞争导致的查询挂起）
            MetricType.LOCK_WAITS: MetricQuery(
                sql="""
                    SELECT value FROM v$sysstat WHERE name = 'enqueue waits'
                """,
                extract=lambda rows: self._safe_extract_float(rows, 0),
                unit="count",
                is_counter=True
            ),
            MetricType.DEADLOCKS: MetricQuery(
                sql="""
                    SELECT value FROM v$sysstat WHERE name = 'enqueue deadlocks'
                """,
                extract=lambda rows: self._safe_extract_float(rows, 0),
                unit="count",
                is_counter=True
            ),

            # 缓冲指标
            MetricType.BUFFER_HIT_RATIO: MetricQuery(
                sql="""
                    SELECT
                        CASE
                            WHEN (SELECT value FROM v$sysstat WHERE name = 'db block gets') +
                                 (SELECT value FROM v$sysstat WHERE name = 'consistent gets') > 0
                            THEN (1 - (SELECT value FROM v$sysstat WHERE name = 'physical reads') /
                                  ((SELECT value FROM v$sysstat WHERE name = 'db block gets') +
                                   (SELECT value FROM v$sysstat WHERE name = 'consistent gets'))) * 100
                            ELSE 100
                        END
                    FROM dual
                """,
                extract=lambda rows: self._safe_extract_float(rows, 100.0),
                unit="percent"
            ),

            # IO指标
            MetricType.PHYSICAL_READS: MetricQuery(
                sql="""
                    SELECT value FROM v$sysstat WHERE name = 'physical reads'
                """,
                extract=lambda rows: self._safe_extract_float(rows, 0),
                unit="count",
                is_counter=True
            ),
            MetricType.LOGICAL_READS: MetricQuery(
                sql="""
                    SELECT (SELECT value FROM v$sysstat WHERE name = 'db block gets') +
                           (SELECT value FROM v$sysstat WHERE name = 'consistent gets')
                    FROM dual
                """,
                extract=lambda rows: self._safe_extract_float(rows, 0),
                unit="count",
                is_counter=True
            ),

            # 资源指标
            MetricType.CPU_USAGE: MetricQuery(
                sql="""
                    SELECT value FROM v$sysmetric
                    WHERE metric_name = 'Host CPU Utilization (%)'
                    AND rownum = 1
                """,
                extract=lambda rows: self._safe_extract_float(rows, 0),
                unit="percent"
            ),
            MetricType.TEMP_SPACE_USAGE: MetricQuery(
                sql="""
                    SELECT NVL(SUM(bytes) / 1024 / 1024 / 1024, 0)
                    FROM v$tempfile
                """,
                extract=lambda rows: self._safe_extract_float(rows, 0),
                unit="GB"
            ),

            # 事务指标
            MetricType.TRANSACTIONS_ACTIVE: MetricQuery(
                sql="""
                    SELECT COUNT(*) FROM v$transaction
                """,
                extract=lambda rows: self._safe_extract_float(rows, 0),
                unit="count"
            ),
            MetricType.TRANSACTIONS_COMMITTED: MetricQuery(
                sql="""
                    SELECT value FROM v$sysstat WHERE name = 'user commits'
                """,
                extract=lambda rows: self._safe_extract_float(rows, 0),
                unit="count",
                is_counter=True
            ),
            MetricType.TRANSACTIONS_ROLLED_BACK: MetricQuery(
                sql="""
                    SELECT value FROM v$sysstat WHERE name = 'user rollbacks'
                """,
                extract=lambda rows: self._safe_extract_float(rows, 0),
                unit="count",
                is_counter=True
            ),

            # 表空间使用率（使用 user_tablespaces 替代 dba_tablespace_usage_metrics，避免权限问题）
            MetricType.DISK_USAGE: MetricQuery(
                sql="""
                    SELECT COUNT(*) FROM user_tablespaces
                """,
                extract=lambda rows: self._safe_extract_float(rows, 0),
                unit="count"
            ),
        }
