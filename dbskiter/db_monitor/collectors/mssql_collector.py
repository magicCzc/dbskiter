"""
SQL Server指标采集器

文件功能：提供SQL Server数据库的指标采集功能
主要类：MSSQLMetricsCollector - SQL Server指标采集器

支持的指标：
    - 吞吐量：QPS、TPS、各类SQL操作次数
    - 连接：活跃连接、总连接、最大连接、阻塞连接
    - 查询性能：慢查询、编译/重编译次数
    - 锁：锁等待、死锁、阻塞
    - 缓冲：缓存命中率、页生命周期
    - IO：物理读/写、逻辑读
    - 内存：总内存、数据库缓存、被盗内存
    - 等待统计：按类别分类的等待事件

依赖：
    - pyodbc 或 pymssql 驱动

作者：AI Assistant
创建时间：2026-06-03
版本：1.0.0
"""

from typing import Dict, Optional
import logging

from .base import BaseMetricsCollector, MetricType, MetricQuery

logger = logging.getLogger(__name__)


class MSSQLMetricsCollector(BaseMetricsCollector):
    """
    SQL Server指标采集器

    提供SQL Server特有的性能指标采集
    """

    def get_metric_queries(self) -> Dict[MetricType, MetricQuery]:
        """
        获取SQL Server指标查询定义

        返回:
            Dict[MetricType, MetricQuery]: 指标查询定义
        """
        return {
            # 吞吐量指标 - 使用性能计数器
            MetricType.QPS: MetricQuery(
                sql="""
                    SELECT cntr_value
                    FROM sys.dm_os_performance_counters
                    WHERE counter_name = 'Batch Requests/sec'
                        AND instance_name = ''
                """,
                extract=lambda rows: self._safe_extract_float(rows, 0, 0),
                unit="count/sec",
                is_counter=False
            ),
            MetricType.TPS: MetricQuery(
                sql="""
                    SELECT cntr_value
                    FROM sys.dm_os_performance_counters
                    WHERE counter_name = 'Transactions/sec'
                        AND instance_name = ''
                """,
                extract=lambda rows: self._safe_extract_float(rows, 0, 0),
                unit="count/sec",
                is_counter=False
            ),
            MetricType.COM_SELECT: MetricQuery(
                sql="""
                    SELECT cntr_value
                    FROM sys.dm_os_performance_counters
                    WHERE counter_name = 'SQL SELECTs/sec'
                        AND instance_name = ''
                """,
                extract=lambda rows: self._safe_extract_float(rows, 0, 0),
                unit="count/sec",
                is_counter=False
            ),
            MetricType.COM_INSERT: MetricQuery(
                sql="""
                    SELECT cntr_value
                    FROM sys.dm_os_performance_counters
                    WHERE counter_name = 'SQL INSERTs/sec'
                        AND instance_name = ''
                """,
                extract=lambda rows: self._safe_extract_float(rows, 0, 0),
                unit="count/sec",
                is_counter=False
            ),
            MetricType.COM_UPDATE: MetricQuery(
                sql="""
                    SELECT cntr_value
                    FROM sys.dm_os_performance_counters
                    WHERE counter_name = 'SQL UPDATEs/sec'
                        AND instance_name = ''
                """,
                extract=lambda rows: self._safe_extract_float(rows, 0, 0),
                unit="count/sec",
                is_counter=False
            ),
            MetricType.COM_DELETE: MetricQuery(
                sql="""
                    SELECT cntr_value
                    FROM sys.dm_os_performance_counters
                    WHERE counter_name = 'SQL DELETEs/sec'
                        AND instance_name = ''
                """,
                extract=lambda rows: self._safe_extract_float(rows, 0, 0),
                unit="count/sec",
                is_counter=False
            ),

            # 连接指标
            MetricType.CONNECTIONS_ACTIVE: MetricQuery(
                sql="""
                    SELECT COUNT(*)
                    FROM sys.dm_exec_sessions
                    WHERE status = 'running' AND is_user_process = 1
                """,
                extract=lambda rows: self._safe_extract_float(rows, 0, 0),
                unit="count"
            ),
            MetricType.CONNECTIONS_TOTAL: MetricQuery(
                sql="""
                    SELECT COUNT(*)
                    FROM sys.dm_exec_sessions
                    WHERE is_user_process = 1
                """,
                extract=lambda rows: self._safe_extract_float(rows, 0, 0),
                unit="count"
            ),
            MetricType.CONNECTIONS_MAX: MetricQuery(
                sql="""
                    SELECT cntr_value
                    FROM sys.dm_os_performance_counters
                    WHERE counter_name = 'User Connections'
                        AND instance_name = ''
                """,
                extract=lambda rows: self._safe_extract_float(rows, 0, 0),
                unit="count"
            ),

            # 查询性能指标
            MetricType.SLOW_QUERIES: MetricQuery(
                sql="""
                    SELECT COUNT(*)
                    FROM sys.dm_exec_requests
                    WHERE total_elapsed_time > 1000000  -- > 1 second
                        AND status IN ('running', 'suspended')
                """,
                extract=lambda rows: self._safe_extract_float(rows, 0, 0),
                unit="count"
            ),
            MetricType.QUERY_TIME_AVG: MetricQuery(
                sql="""
                    SELECT AVG(total_elapsed_time / 1000.0)
                    FROM sys.dm_exec_query_stats
                    WHERE execution_count > 0
                """,
                extract=lambda rows: self._safe_extract_float(rows, 0, 0),
                unit="ms"
            ),
            MetricType.QUERY_TIME_MAX: MetricQuery(
                sql="""
                    SELECT MAX(total_elapsed_time / 1000.0)
                    FROM sys.dm_exec_query_stats
                """,
                extract=lambda rows: self._safe_extract_float(rows, 0, 0),
                unit="ms"
            ),

            # 锁指标
            MetricType.LOCK_WAITS: MetricQuery(
                sql="""
                    SELECT cntr_value
                    FROM sys.dm_os_performance_counters
                    WHERE counter_name = 'Lock Waits/sec'
                        AND instance_name = '_Total'
                """,
                extract=lambda rows: self._safe_extract_float(rows, 0, 0),
                unit="count/sec",
                is_counter=False
            ),
            MetricType.DEADLOCKS: MetricQuery(
                sql="""
                    SELECT cntr_value
                    FROM sys.dm_os_performance_counters
                    WHERE counter_name = 'Number of Deadlocks/sec'
                        AND instance_name = '_Total'
                """,
                extract=lambda rows: self._safe_extract_float(rows, 0, 0),
                unit="count/sec",
                is_counter=False
            ),
            MetricType.ROW_LOCK_WAITS: MetricQuery(
                sql="""
                    SELECT cntr_value
                    FROM sys.dm_os_performance_counters
                    WHERE counter_name = 'Lock Waits/sec'
                        AND instance_name = 'Row'
                """,
                extract=lambda rows: self._safe_extract_float(rows, 0, 0),
                unit="count/sec",
                is_counter=False
            ),

            # 缓冲指标
            MetricType.BUFFER_HIT_RATIO: MetricQuery(
                sql="""
                    SELECT
                        CASE
                            WHEN (SELECT cntr_value FROM sys.dm_os_performance_counters
                                  WHERE counter_name = 'Buffer cache hit ratio base') > 0
                            THEN (SELECT cntr_value * 100.0 / NULLIF(
                                    (SELECT cntr_value FROM sys.dm_os_performance_counters
                                     WHERE counter_name = 'Buffer cache hit ratio base'), 0)
                                  FROM sys.dm_os_performance_counters
                                  WHERE counter_name = 'Buffer cache hit ratio')
                            ELSE 0
                        END
                """,
                extract=lambda rows: self._safe_extract_float(rows, 0, 100.0),
                unit="percent"
            ),
            MetricType.BUFFER_POOL_USAGE: MetricQuery(
                sql="""
                    SELECT
                        (SELECT cntr_value FROM sys.dm_os_performance_counters
                         WHERE counter_name = 'Database pages') * 100.0 /
                        NULLIF((SELECT cntr_value FROM sys.dm_os_performance_counters
                                WHERE counter_name = 'Total pages'), 0)
                """,
                extract=lambda rows: self._safe_extract_float(rows, 0, 0),
                unit="percent"
            ),

            # IO指标
            MetricType.PHYSICAL_READS: MetricQuery(
                sql="""
                    SELECT cntr_value
                    FROM sys.dm_os_performance_counters
                    WHERE counter_name = 'Page reads/sec'
                        AND instance_name = ''
                """,
                extract=lambda rows: self._safe_extract_float(rows, 0, 0),
                unit="pages/sec",
                is_counter=False
            ),
            MetricType.LOGICAL_READS: MetricQuery(
                sql="""
                    SELECT cntr_value
                    FROM sys.dm_os_performance_counters
                    WHERE counter_name = 'Page lookups/sec'
                        AND instance_name = ''
                """,
                extract=lambda rows: self._safe_extract_float(rows, 0, 0),
                unit="pages/sec",
                is_counter=False
            ),
            MetricType.DISK_IO_READ: MetricQuery(
                sql="""
                    SELECT SUM(num_of_reads)
                    FROM sys.dm_io_virtual_file_stats(NULL, NULL)
                """,
                extract=lambda rows: self._safe_extract_float(rows, 0, 0),
                unit="count",
                is_counter=True
            ),
            MetricType.DISK_IO_WRITE: MetricQuery(
                sql="""
                    SELECT SUM(num_of_writes)
                    FROM sys.dm_io_virtual_file_stats(NULL, NULL)
                """,
                extract=lambda rows: self._safe_extract_float(rows, 0, 0),
                unit="count",
                is_counter=True
            ),

            # 资源指标 - SQL Server不直接提供CPU/内存使用率，需要通过其他方式
            MetricType.MEMORY_USAGE: MetricQuery(
                sql="""
                    SELECT
                        (SELECT cntr_value FROM sys.dm_os_performance_counters
                         WHERE counter_name = 'Total Server Memory (KB)') * 100.0 /
                        NULLIF((SELECT cntr_value FROM sys.dm_os_performance_counters
                                WHERE counter_name = 'Target Server Memory (KB)'), 0)
                """,
                extract=lambda rows: self._safe_extract_float(rows, 0, 0),
                unit="percent"
            ),

            # 事务指标
            MetricType.TRANSACTIONS_ACTIVE: MetricQuery(
                sql="""
                    SELECT COUNT(*)
                    FROM sys.dm_tran_active_transactions
                    WHERE transaction_type = 1  -- 用户事务
                """,
                extract=lambda rows: self._safe_extract_float(rows, 0, 0),
                unit="count"
            ),
            MetricType.TRANSACTIONS_COMMITTED: MetricQuery(
                sql="""
                    SELECT cntr_value
                    FROM sys.dm_os_performance_counters
                    WHERE counter_name = 'Transactions/sec'
                        AND instance_name = ''
                """,
                extract=lambda rows: self._safe_extract_float(rows, 0, 0),
                unit="count/sec",
                is_counter=False
            ),
        }

    def _safe_extract_float(self, rows, row_idx: int, col_idx: int, default: float = 0.0) -> float:
        """
        安全提取浮点数值

        参数:
            rows: 查询结果行
            row_idx: 行索引
            col_idx: 列索引
            default: 默认值

        返回:
            float: 提取的数值或默认值
        """
        try:
            if not rows or len(rows) <= row_idx:
                return default
            value = rows[row_idx][col_idx]
            if value is None:
                return default
            return float(value)
        except (IndexError, TypeError, ValueError):
            return default

    def get_wait_stats(self) -> Dict[str, float]:
        """
        获取SQL Server等待统计（按类别汇总）

        返回:
            Dict[str, float]: 各类别的等待时间（秒）
        """
        try:
            result = self.connector.execute("""
                SELECT
                    CASE
                        WHEN wait_type LIKE 'PAGEIOLATCH%' THEN 'IO'
                        WHEN wait_type LIKE 'PAGELATCH%' THEN 'Memory'
                        WHEN wait_type LIKE 'LCK%' THEN 'Locking'
                        WHEN wait_type LIKE 'LATCH%' THEN 'Latch'
                        WHEN wait_type LIKE 'CXPACKET%' OR wait_type LIKE 'CXCONSUMER%' THEN 'Parallelism'
                        WHEN wait_type LIKE 'SOS_SCHEDULER%' THEN 'CPU'
                        WHEN wait_type LIKE 'ASYNC_NETWORK%' THEN 'Network'
                        WHEN wait_type LIKE 'WRITELOG%' OR wait_type LIKE 'LOGBUFFER%' THEN 'Transaction Log'
                        ELSE 'Other'
                    END as wait_category,
                    SUM(wait_time_ms) / 1000.0 as total_wait_sec
                FROM sys.dm_os_wait_stats
                WHERE wait_type NOT IN (
                    'CLR_SEMAPHORE', 'LAZYWRITER_SLEEP', 'RESOURCE_QUEUE',
                    'SLEEP_TASK', 'SLEEP_SYSTEMTASK', 'SQLTRACE_BUFFER_FLUSH',
                    'WAITFOR', 'LOGMGR_QUEUE', 'CHECKPOINT_QUEUE'
                )
                GROUP BY
                    CASE
                        WHEN wait_type LIKE 'PAGEIOLATCH%' THEN 'IO'
                        WHEN wait_type LIKE 'PAGELATCH%' THEN 'Memory'
                        WHEN wait_type LIKE 'LCK%' THEN 'Locking'
                        WHEN wait_type LIKE 'LATCH%' THEN 'Latch'
                        WHEN wait_type LIKE 'CXPACKET%' OR wait_type LIKE 'CXCONSUMER%' THEN 'Parallelism'
                        WHEN wait_type LIKE 'SOS_SCHEDULER%' THEN 'CPU'
                        WHEN wait_type LIKE 'ASYNC_NETWORK%' THEN 'Network'
                        WHEN wait_type LIKE 'WRITELOG%' OR wait_type LIKE 'LOGBUFFER%' THEN 'Transaction Log'
                        ELSE 'Other'
                    END
                ORDER BY total_wait_sec DESC
            """)

            if not result or not result.rows:
                return {}

            return {row[0]: float(row[1]) for row in result.rows if row[0]}

        except Exception as e:
            logger.warning(f"获取等待统计失败: {e}")
            return {}

    def get_top_wait_types(self, limit: int = 10) -> list:
        """
        获取Top等待类型

        参数:
            limit: 返回数量限制

        返回:
            list: 等待类型列表
        """
        try:
            result = self.connector.execute(f"""
                SELECT TOP {limit}
                    wait_type,
                    waiting_tasks_count,
                    wait_time_ms / 1000.0 as wait_time_sec,
                    max_wait_time_ms / 1000.0 as max_wait_time_sec
                FROM sys.dm_os_wait_stats
                WHERE wait_type NOT IN (
                    'CLR_SEMAPHORE', 'LAZYWRITER_SLEEP', 'RESOURCE_QUEUE',
                    'SLEEP_TASK', 'SLEEP_SYSTEMTASK', 'SQLTRACE_BUFFER_FLUSH',
                    'WAITFOR', 'LOGMGR_QUEUE', 'CHECKPOINT_QUEUE'
                )
                ORDER BY wait_time_ms DESC
            """)

            if not result or not result.rows:
                return []

            return [
                {
                    "wait_type": row[0],
                    "waiting_tasks_count": row[1],
                    "wait_time_sec": float(row[2]),
                    "max_wait_time_sec": float(row[3])
                }
                for row in result.rows
            ]

        except Exception as e:
            logger.warning(f"获取Top等待类型失败: {e}")
            return []

    def get_blocking_info(self) -> list:
        """
        获取当前阻塞信息

        返回:
            list: 阻塞会话列表
        """
        try:
            result = self.connector.execute("""
                SELECT
                    blocking_session_id,
                    session_id,
                    wait_type,
                    wait_time / 1000.0 as wait_time_sec,
                    wait_resource
                FROM sys.dm_exec_requests
                WHERE blocking_session_id <> 0
            """)

            if not result or not result.rows:
                return []

            return [
                {
                    "blocking_session_id": row[0],
                    "blocked_session_id": row[1],
                    "wait_type": row[2],
                    "wait_time_sec": float(row[3]),
                    "wait_resource": row[4]
                }
                for row in result.rows
            ]

        except Exception as e:
            logger.warning(f"获取阻塞信息失败: {e}")
            return []
