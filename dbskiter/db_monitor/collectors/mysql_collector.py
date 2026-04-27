"""
MySQL指标采集器

文件功能：提供MySQL数据库的指标采集功能
主要类：MySQLMetricsCollector - MySQL指标采集器

支持的指标：
    - 吞吐量：QPS、TPS、各类SQL操作次数
    - 连接：活跃连接、总连接、最大连接、异常连接
    - 查询性能：慢查询、全表扫描
    - 锁：锁等待、死锁、行锁等待
    - InnoDB：缓冲命中率、缓冲池使用率、行操作
    - 临时表：磁盘临时表、内存临时表
    - 表缓存：表缓存使用率

作者：AI Assistant
创建时间：2026-04-23
"""

from typing import Dict
import logging

from .base import BaseMetricsCollector, MetricType, MetricQuery

logger = logging.getLogger(__name__)


class MySQLMetricsCollector(BaseMetricsCollector):
    """
    MySQL指标采集器

    提供MySQL特有的性能指标采集
    """

    def get_metric_queries(self) -> Dict[MetricType, MetricQuery]:
        """
        获取MySQL指标查询定义

        返回:
            Dict[MetricType, MetricQuery]: 指标查询定义
        """
        return {
            # 吞吐量指标
            MetricType.QPS: MetricQuery(
                sql="SHOW STATUS LIKE 'Queries'",
                extract=lambda rows: self._safe_extract_float(rows, 0, 1),
                unit="count",
                is_counter=True
            ),
            MetricType.COM_SELECT: MetricQuery(
                sql="SHOW STATUS LIKE 'Com_select'",
                extract=lambda rows: self._safe_extract_float(rows, 0, 1),
                unit="count",
                is_counter=True
            ),
            MetricType.COM_INSERT: MetricQuery(
                sql="SHOW STATUS LIKE 'Com_insert'",
                extract=lambda rows: self._safe_extract_float(rows, 0, 1),
                unit="count",
                is_counter=True
            ),
            MetricType.COM_UPDATE: MetricQuery(
                sql="SHOW STATUS LIKE 'Com_update'",
                extract=lambda rows: self._safe_extract_float(rows, 0, 1),
                unit="count",
                is_counter=True
            ),
            MetricType.COM_DELETE: MetricQuery(
                sql="SHOW STATUS LIKE 'Com_delete'",
                extract=lambda rows: self._safe_extract_float(rows, 0, 1),
                unit="count",
                is_counter=True
            ),

            # 连接指标
            MetricType.CONNECTIONS_ACTIVE: MetricQuery(
                sql="SHOW STATUS LIKE 'Threads_connected'",
                extract=lambda rows: self._safe_extract_float(rows, 0, 1),
                unit="count"
            ),
            MetricType.CONNECTIONS_TOTAL: MetricQuery(
                sql="SHOW STATUS LIKE 'Threads_running'",
                extract=lambda rows: self._safe_extract_float(rows, 0, 1),
                unit="count"
            ),
            MetricType.CONNECTIONS_MAX: MetricQuery(
                sql="SHOW STATUS LIKE 'Max_used_connections'",
                extract=lambda rows: self._safe_extract_float(rows, 0, 1),
                unit="count"
            ),
            MetricType.CONNECTIONS_ABORTED: MetricQuery(
                sql="SHOW STATUS LIKE 'Aborted_connects'",
                extract=lambda rows: self._safe_extract_float(rows, 0, 1),
                unit="count",
                is_counter=True
            ),

            # 查询性能指标
            MetricType.SLOW_QUERIES: MetricQuery(
                sql="SHOW STATUS LIKE 'Slow_queries'",
                extract=lambda rows: self._safe_extract_float(rows, 0, 1),
                unit="count",
                is_counter=True
            ),
            MetricType.FULL_SCAN_COUNT: MetricQuery(
                sql="SHOW STATUS LIKE 'Select_scan'",
                extract=lambda rows: self._safe_extract_float(rows, 0, 1),
                unit="count",
                is_counter=True
            ),

            # 锁指标
            MetricType.LOCK_WAITS: MetricQuery(
                sql="SHOW STATUS LIKE 'Table_locks_waited'",
                extract=lambda rows: self._safe_extract_float(rows, 0, 1),
                unit="count",
                is_counter=True
            ),
            MetricType.DEADLOCKS: MetricQuery(
                sql="SHOW STATUS LIKE 'Innodb_deadlocks'",
                extract=lambda rows: self._safe_extract_float(rows, 0, 1),
                unit="count",
                is_counter=True
            ),
            MetricType.ROW_LOCK_WAITS: MetricQuery(
                sql="SHOW STATUS LIKE 'Innodb_row_lock_waits'",
                extract=lambda rows: self._safe_extract_float(rows, 0, 1),
                unit="count",
                is_counter=True
            ),

            # InnoDB缓冲指标
            MetricType.BUFFER_HIT_RATIO: MetricQuery(
                sql="""
                    SELECT
                        CASE
                            WHEN (SELECT VARIABLE_VALUE FROM performance_schema.global_status
                                  WHERE VARIABLE_NAME = 'Innodb_buffer_pool_read_requests') > 0
                            THEN (1 - (SELECT VARIABLE_VALUE FROM performance_schema.global_status
                                       WHERE VARIABLE_NAME = 'Innodb_buffer_pool_reads') /
                                  (SELECT VARIABLE_VALUE FROM performance_schema.global_status
                                   WHERE VARIABLE_NAME = 'Innodb_buffer_pool_read_requests')) * 100
                            ELSE 100
                        END
                """,
                extract=lambda rows: self._safe_extract_float(rows, 100.0),
                unit="percent"
            ),
            MetricType.BUFFER_POOL_USAGE: MetricQuery(
                sql="""
                    SELECT
                        (SELECT VARIABLE_VALUE FROM performance_schema.global_status
                         WHERE VARIABLE_NAME = 'Innodb_buffer_pool_pages_data') /
                        NULLIF((SELECT VARIABLE_VALUE FROM performance_schema.global_status
                         WHERE VARIABLE_NAME = 'Innodb_buffer_pool_pages_total'), 0) * 100
                """,
                extract=lambda rows: self._safe_extract_float(rows, 0.0),
                unit="percent"
            ),
            MetricType.ROWS_READ: MetricQuery(
                sql="SHOW STATUS LIKE 'Innodb_rows_read'",
                extract=lambda rows: self._safe_extract_float(rows, 0, 1),
                unit="count/sec",
                is_counter=True
            ),
            MetricType.ROWS_CHANGED: MetricQuery(
                sql="""
                    SELECT
                        (SELECT VARIABLE_VALUE FROM performance_schema.global_status WHERE VARIABLE_NAME = 'Innodb_rows_inserted') +
                        (SELECT VARIABLE_VALUE FROM performance_schema.global_status WHERE VARIABLE_NAME = 'Innodb_rows_updated') +
                        (SELECT VARIABLE_VALUE FROM performance_schema.global_status WHERE VARIABLE_NAME = 'Innodb_rows_deleted')
                """,
                extract=lambda rows: self._safe_extract_float(rows, 0.0),
                unit="count/sec",
                is_counter=True
            ),

            # 临时表指标
            MetricType.TEMP_TABLES_DISK: MetricQuery(
                sql="SHOW STATUS LIKE 'Created_tmp_disk_tables'",
                extract=lambda rows: self._safe_extract_float(rows, 0, 1),
                unit="count",
                is_counter=True
            ),
            MetricType.TEMP_TABLES_MEMORY: MetricQuery(
                sql="SHOW STATUS LIKE 'Created_tmp_tables'",
                extract=lambda rows: self._safe_extract_float(rows, 0, 1),
                unit="count",
                is_counter=True
            ),

            # 表缓存指标
            MetricType.TABLE_OPEN_CACHE: MetricQuery(
                sql="""
                    SELECT
                        (SELECT VARIABLE_VALUE FROM performance_schema.global_status WHERE VARIABLE_NAME = 'Open_tables') /
                        NULLIF((SELECT VARIABLE_VALUE FROM performance_schema.global_variables WHERE VARIABLE_NAME = 'table_open_cache'), 0) * 100
                """,
                extract=lambda rows: self._safe_extract_float(rows, 0.0),
                unit="percent"
            ),

            # 磁盘使用率（通过查询数据目录大小估算）
            # 注意：MySQL 不直接提供磁盘使用率，这里返回的是数据文件大小（GB）
            MetricType.DISK_USAGE: MetricQuery(
                sql="""
                    SELECT SUM(data_length + index_length) / 1024 / 1024 / 1024
                    FROM information_schema.tables
                    WHERE table_schema NOT IN ('information_schema', 'mysql', 'performance_schema', 'sys')
                """,
                extract=lambda rows: self._safe_extract_float(rows, 0.0),
                unit="GB"
            ),
        }
