"""
PostgreSQL性能分析器 - 基于统一性能模型

文件功能：使用统一性能模型分析PostgreSQL数据库性能
主要类：PostgreSQLPerformanceAnalyzer

特性：
    1. 统一接口：遵循PerformanceAnalyzer基类
    2. 生产安全：内置超时、降级机制
    3. 多版本兼容：支持PostgreSQL 10/11/12/13/14/15/16
    4. pg_stat_statements集成：利用PostgreSQL原生统计功能

作者: Magiczc
创建时间: 2026-04-24
版本: 1.0.0
"""

import logging
from typing import List, Optional, Tuple

from dbskiter.shared.unified_connector import UnifiedConnector
from ..core.performance_model import (
    PerformanceAnalyzer,
    PerformanceMetric,
    SlowQueryInfo,
    MetricCategory,
    get_threshold
)

logger = logging.getLogger(__name__)


class PostgreSQLPerformanceAnalyzer(PerformanceAnalyzer):
    """
    PostgreSQL性能分析器

    使用统一性能模型分析PostgreSQL性能，支持：
    - 多版本PostgreSQL (10-16)
    - pg_stat_statements扩展集成
    - 自动降级（pg_stat_statements -> pg_stat_*视图）
    - 生产安全（超时控制、权限检查）
    """

    def __init__(self, connector: UnifiedConnector, timeout: int = 30):
        """
        初始化PostgreSQL性能分析器

        参数:
            connector: 数据库连接器
            timeout: 查询超时时间(秒)
        """
        super().__init__(connector, timeout)
        self._version: Optional[str] = None
        self._has_pg_stat_statements: bool = False
        self._has_pg_stat_kcache: bool = False
        self._detect_capabilities()

    def _detect_capabilities(self):
        """检测数据库能力"""
        try:
            # 检测版本
            result = self._execute_with_timeout(
                "SELECT version()",
                timeout=5
            )
            if result:
                version_str = str(result[0][0])
                # 提取版本号
                import re
                match = re.search(r'PostgreSQL\s+(\d+\.?\d*)', version_str)
                if match:
                    self._version = match.group(1)
                    logger.info(f"PostgreSQL版本: {self._version}")

            # 检测pg_stat_statements扩展
            result = self._execute_with_timeout(
                "SELECT COUNT(*) FROM pg_extension WHERE extname = 'pg_stat_statements'",
                timeout=5
            )
            self._has_pg_stat_statements = result and result[0][0] > 0
            logger.info(f"pg_stat_statements可用: {self._has_pg_stat_statements}")

            # 检测pg_stat_kcache扩展（可选，提供CPU/IO统计）
            try:
                result = self._execute_with_timeout(
                    "SELECT COUNT(*) FROM pg_extension WHERE extname = 'pg_stat_kcache'",
                    timeout=5
                )
                self._has_pg_stat_kcache = result and result[0][0] > 0
                logger.info(f"pg_stat_kcache可用: {self._has_pg_stat_kcache}")
            except Exception:
                self._has_pg_stat_kcache = False

        except Exception as e:
            logger.warning(f"能力检测失败: {e}")

    def collect_metrics(self) -> List[PerformanceMetric]:
        """
        采集PostgreSQL性能指标

        返回:
            性能指标列表
        """
        metrics = []

        # 采集各类指标
        metrics.extend(self._collect_cpu_metrics())
        metrics.extend(self._collect_io_metrics())
        metrics.extend(self._collect_memory_metrics())
        metrics.extend(self._collect_concurrency_metrics())
        metrics.extend(self._collect_lock_metrics())

        return metrics

    def _collect_cpu_metrics(self) -> List[PerformanceMetric]:
        """采集CPU相关指标"""
        metrics = []

        try:
            # 获取活跃会话比例
            result = self._execute_with_timeout("""
                SELECT
                    count(*) filter (where state = 'active') as active,
                    count(*) as total
                FROM pg_stat_activity
                WHERE backend_type = 'client backend'
            """)

            if result:
                active = result[0][0] or 0
                total = result[0][1] or 1
                ratio = (active / total) * 100 if total > 0 else 0

                threshold = get_threshold("cpu_time_ratio")
                metrics.append(PerformanceMetric(
                    name="active_session_ratio",
                    value=ratio,
                    unit="%",
                    category=MetricCategory.CPU,
                    threshold_warning=threshold.get("warning"),
                    threshold_critical=threshold.get("critical"),
                    source="pg_stat_activity"
                ))

            # 如果有pg_stat_kcache，获取CPU时间
            if self._has_pg_stat_kcache:
                result = self._execute_with_timeout("""
                    SELECT
                        sum(user_time) as user_time,
                        sum(system_time) as system_time
                    FROM pg_stat_kcache
                """)

                if result and result[0][0] is not None:
                    user_time = result[0][0]
                    system_time = result[0][1] or 0
                    total_cpu = user_time + system_time

                    metrics.append(PerformanceMetric(
                        name="total_cpu_time",
                        value=total_cpu,
                        unit="ms",
                        category=MetricCategory.CPU,
                        source="pg_stat_kcache"
                    ))

        except Exception as e:
            logger.warning(f"CPU指标采集失败: {e}")

        return metrics

    def _collect_io_metrics(self) -> List[PerformanceMetric]:
        """采集IO相关指标"""
        metrics = []

        try:
            # 获取Buffer Cache命中率
            result = self._execute_with_timeout("""
                SELECT
                    round(
                        (blks_hit::numeric / nullif(blks_hit + blks_read, 0)) * 100,
                        2
                    ) as cache_hit_ratio
                FROM pg_stat_database
                WHERE datname = current_database()
            """)

            if result and result[0][0] is not None:
                hit_ratio = float(result[0][0])
                threshold = get_threshold("buffer_hit_ratio")
                metrics.append(PerformanceMetric(
                    name="buffer_cache_hit_ratio",
                    value=hit_ratio,
                    unit="%",
                    category=MetricCategory.IO,
                    threshold_warning=threshold.get("warning"),
                    threshold_critical=threshold.get("critical"),
                    higher_is_better=True,  # 命中率越高越好
                    source="pg_stat_database"
                ))

            # 获取数据库IO统计
            result = self._execute_with_timeout("""
                SELECT
                    blks_read,
                    blks_hit,
                    temp_files,
                    round(temp_bytes::numeric / 1024 / 1024, 2) as temp_mb
                FROM pg_stat_database
                WHERE datname = current_database()
            """)

            if result:
                blks_read = result[0][0] or 0
                temp_files = result[0][2] or 0
                temp_mb = result[0][3] or 0

                metrics.append(PerformanceMetric(
                    name="blocks_read",
                    value=blks_read,
                    unit="blocks",
                    category=MetricCategory.IO,
                    source="pg_stat_database"
                ))

                if temp_files > 0:
                    metrics.append(PerformanceMetric(
                        name="temp_files",
                        value=temp_files,
                        unit="files",
                        category=MetricCategory.IO,
                        threshold_warning=10,
                        threshold_critical=100,
                        source="pg_stat_database"
                    ))

                    metrics.append(PerformanceMetric(
                        name="temp_size",
                        value=temp_mb,
                        unit="MB",
                        category=MetricCategory.IO,
                        source="pg_stat_database"
                    ))

        except Exception as e:
            logger.warning(f"IO指标采集失败: {e}")

        return metrics

    def _collect_memory_metrics(self) -> List[PerformanceMetric]:
        """采集内存相关指标"""
        metrics = []

        try:
            # 获取共享内存使用情况（兼容PostgreSQL 15及以下版本）
            # pg_total_memory_usage()是PostgreSQL 14+的函数，使用替代方案
            result = self._execute_with_timeout("""
                SELECT
                    pg_size_pretty(
                        (SELECT setting::bigint * 8192 FROM pg_settings WHERE name = 'shared_buffers') +
                        (SELECT count(*) * 4096 FROM pg_stat_activity)
                    ) as total_used,
                    pg_size_pretty(
                        (SELECT setting::bigint * 8192 FROM pg_settings WHERE name = 'work_mem') * 
                        (SELECT count(*) FROM pg_stat_activity WHERE state = 'active')
                    ) as backend_used
            """)

            # 获取连接使用的内存（如果版本支持backend_memory_usage列）
            # backend_memory_usage是PostgreSQL 17+的列
            try:
                result = self._execute_with_timeout("""
                    SELECT
                        count(*) as connection_count,
                        sum(backend_memory_usage) as total_backend_memory
                    FROM pg_stat_activity
                    WHERE backend_memory_usage IS NOT NULL
                """)

                if result and result[0][1] is not None:
                    total_memory = result[0][1]
                    metrics.append(PerformanceMetric(
                        name="backend_memory",
                        value=total_memory,
                        unit="bytes",
                        category=MetricCategory.MEMORY,
                        source="pg_stat_activity"
                    ))
            except Exception:
                # 列不存在，跳过此指标
                pass

        except Exception as e:
            logger.warning(f"内存指标采集失败: {e}")

        return metrics

    def _collect_concurrency_metrics(self) -> List[PerformanceMetric]:
        """采集并发相关指标"""
        metrics = []

        try:
            # 获取连接统计
            result = self._execute_with_timeout("""
                SELECT
                    count(*) as current_connections,
                    (SELECT setting::int FROM pg_settings WHERE name = 'max_connections') as max_connections,
                    count(*) filter (where wait_event_type = 'Lock') as waiting_on_lock
                FROM pg_stat_activity
            """)

            if result:
                current = result[0][0] or 0
                max_conn = result[0][1] or 100
                waiting = result[0][2] or 0

                usage_ratio = (current / max_conn) * 100 if max_conn > 0 else 0

                threshold = get_threshold("connection_usage")
                metrics.append(PerformanceMetric(
                    name="connection_usage",
                    value=usage_ratio,
                    unit="%",
                    category=MetricCategory.CONCURRENCY,
                    threshold_warning=threshold.get("warning"),
                    threshold_critical=threshold.get("critical"),
                    source="pg_stat_activity"
                ))

                if waiting > 0:
                    metrics.append(PerformanceMetric(
                        name="waiting_connections",
                        value=waiting,
                        unit="count",
                        category=MetricCategory.CONCURRENCY,
                        threshold_warning=5,
                        threshold_critical=20,
                        source="pg_stat_activity"
                    ))

            # 获取事务统计
            result = self._execute_with_timeout("""
                SELECT
                    count(*) filter (where state = 'idle in transaction') as idle_in_transaction,
                    count(*) filter (where state = 'active') as active,
                    max(extract(epoch from (now() - xact_start))) filter (where xact_start IS NOT NULL) as longest_xact_sec
                FROM pg_stat_activity
                WHERE backend_type = 'client backend'
            """)

            if result:
                idle_in_trx = result[0][0] or 0
                longest_xact = result[0][2] or 0

                if idle_in_trx > 0:
                    metrics.append(PerformanceMetric(
                        name="idle_in_transaction",
                        value=idle_in_trx,
                        unit="count",
                        category=MetricCategory.CONCURRENCY,
                        threshold_warning=5,
                        threshold_critical=20,
                        source="pg_stat_activity"
                    ))

                if longest_xact > 60:  # 超过1分钟
                    metrics.append(PerformanceMetric(
                        name="longest_transaction_sec",
                        value=longest_xact,
                        unit="sec",
                        category=MetricCategory.CONCURRENCY,
                        threshold_warning=60,
                        threshold_critical=300,
                        source="pg_stat_activity"
                    ))

        except Exception as e:
            logger.warning(f"并发指标采集失败: {e}")

        return metrics

    def _collect_lock_metrics(self) -> List[PerformanceMetric]:
        """采集锁相关指标"""
        metrics = []

        try:
            # 获取锁等待情况
            result = self._execute_with_timeout("""
                SELECT
                    count(*) as lock_waits,
                    count(*) filter (where granted = false) as waiting_locks
                FROM pg_locks l
                JOIN pg_stat_activity a ON l.pid = a.pid
                WHERE l.locktype != 'virtualxid'
            """)

            if result:
                lock_waits = result[0][0] or 0
                waiting_locks = result[0][1] or 0

                # 获取总事务数用于计算比例
                result_trx = self._execute_with_timeout("""
                    SELECT count(*) FROM pg_stat_activity WHERE xact_start IS NOT NULL
                """)
                total_trx = result_trx[0][0] if result_trx else 1

                wait_ratio = (waiting_locks / total_trx) * 100 if total_trx > 0 else 0

                threshold = get_threshold("lock_wait_ratio")
                metrics.append(PerformanceMetric(
                    name="lock_wait_ratio",
                    value=wait_ratio,
                    unit="%",
                    category=MetricCategory.LOCK,
                    threshold_warning=threshold.get("warning"),
                    threshold_critical=threshold.get("critical"),
                    source="pg_locks"
                ))

            # 获取死锁统计
            result = self._execute_with_timeout("""
                SELECT
                    deadlocks
                FROM pg_stat_database
                WHERE datname = current_database()
            """)

            if result:
                deadlocks = result[0][0] or 0

                if deadlocks > 0:
                    metrics.append(PerformanceMetric(
                        name="deadlock_count",
                        value=deadlocks,
                        unit="count",
                        category=MetricCategory.LOCK,
                        threshold_warning=1,
                        threshold_critical=5,
                        source="pg_stat_database"
                    ))

        except Exception as e:
            logger.warning(f"锁指标采集失败: {e}")

        return metrics

    def collect_slow_queries(self, limit: int = 20,
                            min_time_ms: float = 1000) -> List[SlowQueryInfo]:
        """
        采集PostgreSQL慢查询

        参数:
            limit: 返回条数限制
            min_time_ms: 最小执行时间(毫秒)

        返回:
            慢查询列表
        """
        queries = []

        try:
            # 优先从pg_stat_statements获取
            if self._has_pg_stat_statements:
                result = self._execute_with_timeout(f"""
                    SELECT
                        queryid,
                        query,
                        calls,
                        round(total_exec_time::numeric, 2) as total_time_ms,
                        round(mean_exec_time::numeric, 2) as avg_time_ms,
                        round(max_exec_time::numeric, 2) as max_time_ms,
                        rows,
                        shared_blks_hit + shared_blks_read as blocks
                    FROM pg_stat_statements
                    WHERE mean_exec_time >= %s
                    ORDER BY mean_exec_time DESC
                    LIMIT %s
                """, (min_time_ms, limit))

                if result:
                    for row in result:
                        queries.append(SlowQueryInfo(
                            sql_text=row[1],
                            sql_id=str(row[0]),
                            execution_count=row[2],
                            total_time_ms=row[3],
                            avg_time_ms=row[4],
                            max_time_ms=row[5],
                            rows_examined=row[7]
                        ))

            # 降级到pg_stat_activity（只能看到当前执行的）
            if not queries:
                result = self._execute_with_timeout(f"""
                    SELECT
                        pid,
                        usename,
                        client_addr,
                        datname,
                        state,
                        extract(epoch from (now() - query_start)) * 1000 as query_time_ms,
                        left(query, 500) as query_text
                    FROM pg_stat_activity
                    WHERE state = 'active'
                    AND query_start IS NOT NULL
                    AND extract(epoch from (now() - query_start)) * 1000 >= %s
                    ORDER BY query_start
                    LIMIT %s
                """, (min_time_ms, limit))

                if result:
                    for row in result:
                        query_time_ms = row[5] or 0
                        queries.append(SlowQueryInfo(
                            sql_text=row[6] or f"{row[4]} from {row[2]}",
                            sql_id=str(row[0]),
                            execution_count=1,
                            total_time_ms=query_time_ms,
                            avg_time_ms=query_time_ms,
                            max_time_ms=query_time_ms,
                            database=row[3]
                        ))

        except Exception as e:
            logger.error(f"慢查询采集失败: {e}")

        return queries

    def get_active_sessions(self) -> Tuple[int, int]:
        """
        获取PostgreSQL会话信息

        返回:
            (活跃会话数, 总会话数)
        """
        try:
            result = self._execute_with_timeout("""
                SELECT
                    count(*) filter (where state = 'active') as active,
                    count(*) as total
                FROM pg_stat_activity
                WHERE backend_type = 'client backend'
            """)

            if result:
                return result[0][0] or 0, result[0][1] or 0

        except Exception as e:
            logger.error(f"会话信息采集失败: {e}")

        return 0, 0
