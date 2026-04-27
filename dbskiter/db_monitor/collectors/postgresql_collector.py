"""
PostgreSQL指标采集器

文件功能：提供PostgreSQL数据库的指标采集功能
主要类：PostgreSQLMetricsCollector - PostgreSQL指标采集器

支持的指标：
    - 吞吐量：QPS、事务数
    - 连接：活跃连接、总连接、空闲连接
    - 查询性能：慢查询、缓存命中率
    - 锁：锁等待数
    - 缓冲：共享缓冲区命中率
    - IO：块读取数、临时文件数
    - 事务：提交数、回滚数
    - 复制：复制延迟

作者：AI Assistant
创建时间：2026-04-23
"""

from typing import Dict
import logging

from .base import BaseMetricsCollector, MetricType, MetricQuery

logger = logging.getLogger(__name__)


class PostgreSQLMetricsCollector(BaseMetricsCollector):
    """
    PostgreSQL指标采集器

    提供PostgreSQL特有的性能指标采集
    """

    def get_metric_queries(self) -> Dict[MetricType, MetricQuery]:
        """
        获取PostgreSQL指标查询定义

        返回:
            Dict[MetricType, MetricQuery]: 指标查询定义
        """
        return {
            # 连接指标
            MetricType.CONNECTIONS_ACTIVE: MetricQuery(
                sql="SELECT count(*) FROM pg_stat_activity WHERE state = 'active'",
                extract=lambda rows: self._safe_extract_float(rows, 0),
                unit="count"
            ),
            MetricType.CONNECTIONS_TOTAL: MetricQuery(
                sql="SELECT count(*) FROM pg_stat_activity",
                extract=lambda rows: self._safe_extract_float(rows, 0),
                unit="count"
            ),
            MetricType.CONNECTIONS_MAX: MetricQuery(
                sql="SELECT setting::int FROM pg_settings WHERE name = 'max_connections'",
                extract=lambda rows: self._safe_extract_float(rows, 0),
                unit="count"
            ),

            # 查询性能指标
            MetricType.QPS: MetricQuery(
                sql="""
                    SELECT COALESCE(SUM(calls), 0)
                    FROM pg_stat_statements
                    WHERE calls > 0
                """,
                extract=lambda rows: self._safe_extract_float(rows, 0),
                unit="count",
                is_counter=True
            ),

            # 锁指标
            MetricType.LOCK_WAITS: MetricQuery(
                sql="SELECT count(*) FROM pg_locks WHERE NOT granted",
                extract=lambda rows: self._safe_extract_float(rows, 0),
                unit="count"
            ),
            MetricType.DEADLOCKS: MetricQuery(
                sql="SELECT deadlocks FROM pg_stat_database WHERE datname = current_database()",
                extract=lambda rows: self._safe_extract_float(rows, 0),
                unit="count",
                is_counter=True
            ),

            # 缓冲指标
            MetricType.BUFFER_HIT_RATIO: MetricQuery(
                sql="""
                    SELECT
                        CASE
                            WHEN (blks_hit + blks_read) > 0
                            THEN (blks_hit::float / (blks_hit + blks_read)) * 100
                            ELSE 100
                        END
                    FROM pg_stat_database
                    WHERE datname = current_database()
                """,
                extract=lambda rows: self._safe_extract_float(rows, 100.0),
                unit="percent"
            ),
            MetricType.SHARED_BUFFER_USAGE: MetricQuery(
                sql="""
                    SELECT
                        ROUND(
                            (SELECT count(*) * 8192 FROM pg_buffercache WHERE usagecount > 0)::numeric /
                            (SELECT setting::bigint * 8192 FROM pg_settings WHERE name = 'shared_buffers') * 100,
                            2
                        )
                """,
                extract=lambda rows: self._safe_extract_float(rows, 0),
                unit="percent"
            ),

            # IO指标
            MetricType.PHYSICAL_READS: MetricQuery(
                sql="""
                    SELECT blks_read FROM pg_stat_database
                    WHERE datname = current_database()
                """,
                extract=lambda rows: self._safe_extract_float(rows, 0),
                unit="count",
                is_counter=True
            ),
            MetricType.LOGICAL_READS: MetricQuery(
                sql="""
                    SELECT blks_hit FROM pg_stat_database
                    WHERE datname = current_database()
                """,
                extract=lambda rows: self._safe_extract_float(rows, 0),
                unit="count",
                is_counter=True
            ),

            # 临时文件
            MetricType.TEMP_TABLES_DISK: MetricQuery(
                sql="""
                    SELECT temp_files FROM pg_stat_database
                    WHERE datname = current_database()
                """,
                extract=lambda rows: self._safe_extract_float(rows, 0),
                unit="count",
                is_counter=True
            ),

            # 事务指标
            MetricType.TRANSACTIONS_COMMITTED: MetricQuery(
                sql="""
                    SELECT xact_commit FROM pg_stat_database
                    WHERE datname = current_database()
                """,
                extract=lambda rows: self._safe_extract_float(rows, 0),
                unit="count",
                is_counter=True
            ),
            MetricType.TRANSACTIONS_ROLLED_BACK: MetricQuery(
                sql="""
                    SELECT xact_rollback FROM pg_stat_database
                    WHERE datname = current_database()
                """,
                extract=lambda rows: self._safe_extract_float(rows, 0),
                unit="count",
                is_counter=True
            ),

            # 活跃事务
            MetricType.TRANSACTIONS_ACTIVE: MetricQuery(
                sql="""
                    SELECT count(*) FROM pg_stat_activity
                    WHERE state = 'active' AND xact_start IS NOT NULL
                """,
                extract=lambda rows: self._safe_extract_float(rows, 0),
                unit="count"
            ),

            # 复制延迟
            MetricType.REPLICATION_LAG: MetricQuery(
                sql="""
                    SELECT
                        CASE
                            WHEN pg_last_wal_receive_lsn() = pg_last_wal_replay_lsn()
                            THEN 0
                            ELSE EXTRACT(EPOCH FROM (now() - pg_last_xact_replay_timestamp()))
                        END
                    WHERE pg_is_in_recovery()
                """,
                extract=lambda rows: self._safe_extract_float(rows, 0),
                unit="seconds"
            ),

            # 表统计
            MetricType.ROWS_READ: MetricQuery(
                sql="""
                    SELECT COALESCE(SUM(seq_tup_read + idx_tup_fetch), 0)
                    FROM pg_stat_user_tables
                """,
                extract=lambda rows: self._safe_extract_float(rows, 0),
                unit="count",
                is_counter=True
            ),

            # 数据库大小
            MetricType.DISK_USAGE: MetricQuery(
                sql="""
                    SELECT pg_database_size(current_database()) / 1024.0 / 1024.0 / 1024.0
                """,
                extract=lambda rows: self._safe_extract_float(rows, 0),
                unit="GB"
            ),
        }
