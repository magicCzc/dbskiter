"""
Oracle性能分析器 - 基于统一性能模型

文件功能：使用统一性能模型分析Oracle数据库性能
主要类：OraclePerformanceAnalyzer

特性：
    1. 统一接口：遵循PerformanceAnalyzer基类
    2. 生产安全：内置超时、降级机制
    3. 多版本兼容：支持Oracle 11g/12c/19c/21c
    4. AWR/ASH集成：利用Oracle原生诊断能力

作者: AI Assistant
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


class OraclePerformanceAnalyzer(PerformanceAnalyzer):
    """
    Oracle性能分析器

    使用统一性能模型分析Oracle性能，支持：
    - 多版本Oracle (11g/12c/19c/21c)
    - AWR/ASH报告集成
    - 自动降级（AWR -> V$视图 -> 基础统计）
    - 生产安全（超时控制、权限检查）
    """

    def __init__(self, connector: UnifiedConnector, timeout: int = 30):
        """
        初始化Oracle性能分析器

        参数:
            connector: 数据库连接器
            timeout: 查询超时时间(秒)
        """
        super().__init__(connector, timeout)
        self._version: Optional[str] = None
        self._has_awr: bool = False
        self._has_ash: bool = False
        self._is_rac: bool = False
        self._detect_capabilities()

    def _detect_capabilities(self):
        """检测数据库能力"""
        try:
            # 检测版本
            result = self._execute_with_timeout(
                "SELECT * FROM v$version WHERE banner LIKE 'Oracle%'",
                timeout=5
            )
            if result:
                version_str = str(result[0][0])
                self._version = version_str
                logger.info(f"Oracle版本: {self._version}")

            # 检测AWR可用性（需要Diagnostic Pack许可）
            try:
                result = self._execute_with_timeout(
                    "SELECT COUNT(*) FROM dba_hist_snapshot WHERE rownum = 1",
                    timeout=5
                )
                self._has_awr = result is not None
                logger.info(f"AWR可用: {self._has_awr}")
            except Exception:
                self._has_awr = False
                logger.info("AWR不可用（可能需要Diagnostic Pack许可）")

            # 检测ASH可用性
            try:
                result = self._execute_with_timeout(
                    "SELECT COUNT(*) FROM v$active_session_history WHERE rownum = 1",
                    timeout=5
                )
                self._has_ash = result is not None
                logger.info(f"ASH可用: {self._has_ash}")
            except Exception:
                self._has_ash = False

            # 检测是否为RAC
            try:
                result = self._execute_with_timeout(
                    "SELECT COUNT(*) FROM gv$instance",
                    timeout=5
                )
                self._is_rac = result and result[0][0] > 1
                logger.info(f"RAC环境: {self._is_rac}")
            except Exception:
                self._is_rac = False

        except Exception as e:
            logger.warning(f"能力检测失败: {e}")

    def collect_metrics(self) -> List[PerformanceMetric]:
        """
        采集Oracle性能指标

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
            # 获取DB Time和DB CPU
            result = self._execute_with_timeout("""
                SELECT
                    stat_name,
                    ROUND(value / 1000000, 2) as value_sec
                FROM v$sys_time_model
                WHERE stat_name IN ('DB time', 'DB CPU')
            """)

            if result:
                for row in result:
                    stat_name = row[0]
                    value = row[1]

                    if stat_name == 'DB time':
                        threshold = get_threshold("cpu_time_ratio")
                        metrics.append(PerformanceMetric(
                            name="db_time_sec",
                            value=value,
                            unit="sec",
                            category=MetricCategory.CPU,
                            threshold_warning=threshold.get("warning"),
                            threshold_critical=threshold.get("critical"),
                            source="v$sys_time_model"
                        ))
                    elif stat_name == 'DB CPU':
                        metrics.append(PerformanceMetric(
                            name="db_cpu_sec",
                            value=value,
                            unit="sec",
                            category=MetricCategory.CPU,
                            source="v$sys_time_model"
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
                    ROUND(
                        (1 - (physical_reads / (db_block_gets + consistent_gets))) * 100,
                        2
                    ) as cache_hit_ratio
                FROM v$buffer_pool_statistics
                WHERE db_block_gets + consistent_gets > 0
                AND ROWNUM = 1
            """)

            if result and result[0][0] is not None:
                hit_ratio = result[0][0]
                threshold = get_threshold("buffer_hit_ratio")
                metrics.append(PerformanceMetric(
                    name="buffer_cache_hit_ratio",
                    value=hit_ratio,
                    unit="%",
                    category=MetricCategory.IO,
                    threshold_warning=threshold.get("warning"),
                    threshold_critical=threshold.get("critical"),
                    higher_is_better=True,  # 命中率越高越好
                    source="v$buffer_pool_statistics"
                ))

            # 获取物理IO统计
            result = self._execute_with_timeout("""
                SELECT
                    SUM(CASE WHEN name = 'physical reads' THEN value ELSE 0 END) as physical_reads,
                    SUM(CASE WHEN name = 'physical writes' THEN value ELSE 0 END) as physical_writes
                FROM v$sysstat
                WHERE name IN ('physical reads', 'physical writes')
            """)

            if result:
                physical_reads = result[0][0] or 0
                physical_writes = result[0][1] or 0

                metrics.append(PerformanceMetric(
                    name="physical_reads",
                    value=physical_reads,
                    unit="count",
                    category=MetricCategory.IO,
                    source="v$sysstat"
                ))

                metrics.append(PerformanceMetric(
                    name="physical_writes",
                    value=physical_writes,
                    unit="count",
                    category=MetricCategory.IO,
                    source="v$sysstat"
                ))

        except Exception as e:
            logger.warning(f"IO指标采集失败: {e}")

        return metrics

    def _collect_memory_metrics(self) -> List[PerformanceMetric]:
        """采集内存相关指标"""
        metrics = []

        try:
            # 获取SGA使用率
            result = self._execute_with_timeout("""
                SELECT
                    ROUND(
                        (SELECT SUM(bytes) FROM v$sgastat) /
                        (SELECT value FROM v$sga WHERE name = 'Total SGA Maximum') * 100,
                        2
                    ) as sga_usage_pct
                FROM dual
            """)

            if result and result[0][0] is not None:
                sga_usage = result[0][0]
                threshold = get_threshold("memory_usage")
                metrics.append(PerformanceMetric(
                    name="sga_usage",
                    value=sga_usage,
                    unit="%",
                    category=MetricCategory.MEMORY,
                    threshold_warning=threshold.get("warning"),
                    threshold_critical=threshold.get("critical"),
                    source="v$sga/v$sgastat"
                ))

            # 获取PGA使用率
            result = self._execute_with_timeout("""
                SELECT
                    ROUND(
                        (SELECT SUM(pga_used_mem) FROM v$process) /
                        (SELECT value FROM v$pgastat WHERE name = 'maximum PGA allocated') * 100,
                        2
                    ) as pga_usage_pct
                FROM dual
            """)

            if result and result[0][0] is not None:
                pga_usage = result[0][0]
                metrics.append(PerformanceMetric(
                    name="pga_usage",
                    value=pga_usage,
                    unit="%",
                    category=MetricCategory.MEMORY,
                    threshold_warning=threshold.get("warning"),
                    threshold_critical=threshold.get("critical"),
                    source="v$process/v$pgastat"
                ))

        except Exception as e:
            logger.warning(f"内存指标采集失败: {e}")

        return metrics

    def _collect_concurrency_metrics(self) -> List[PerformanceMetric]:
        """采集并发相关指标"""
        metrics = []

        try:
            # 获取当前会话数
            result = self._execute_with_timeout("""
                SELECT
                    COUNT(*) as total_sessions,
                    SUM(CASE WHEN status = 'ACTIVE' THEN 1 ELSE 0 END) as active_sessions
                FROM v$session
                WHERE type = 'USER'
            """)

            if result:
                total = result[0][0] or 0
                active = result[0][1] or 0

                # 获取最大会话数配置
                result_max = self._execute_with_timeout("""
                    SELECT value FROM v$parameter WHERE name = 'sessions'
                """)
                max_sessions = int(result_max[0][0]) if result_max and result_max[0][0] else 100

                usage_ratio = (total / max_sessions) * 100 if max_sessions > 0 else 0

                threshold = get_threshold("connection_usage")
                metrics.append(PerformanceMetric(
                    name="session_usage",
                    value=usage_ratio,
                    unit="%",
                    category=MetricCategory.CONCURRENCY,
                    threshold_warning=threshold.get("warning"),
                    threshold_critical=threshold.get("critical"),
                    source="v$session"
                ))

                metrics.append(PerformanceMetric(
                    name="active_session_ratio",
                    value=(active / total * 100) if total > 0 else 0,
                    unit="%",
                    category=MetricCategory.CONCURRENCY,
                    source="v$session"
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
                SELECT COUNT(*) as lock_waits
                FROM v$lock l1, v$lock l2
                WHERE l1.block = 1
                AND l2.request > 0
                AND l1.id1 = l2.id1
                AND l1.id2 = l2.id2
            """)

            if result:
                lock_waits = result[0][0]

                # 获取总事务数
                result_trx = self._execute_with_timeout("""
                    SELECT COUNT(*) FROM v$transaction
                """)
                total_trx = result_trx[0][0] if result_trx else 1

                wait_ratio = (lock_waits / total_trx) * 100 if total_trx > 0 else 0

                threshold = get_threshold("lock_wait_ratio")
                metrics.append(PerformanceMetric(
                    name="lock_wait_ratio",
                    value=wait_ratio,
                    unit="%",
                    category=MetricCategory.LOCK,
                    threshold_warning=threshold.get("warning"),
                    threshold_critical=threshold.get("critical"),
                    source="v$lock"
                ))

            # 获取死锁统计
            result = self._execute_with_timeout("""
                SELECT value FROM v$sysstat WHERE name = 'enqueue deadlocks'
            """)

            if result:
                deadlock_count = result[0][0] or 0
                metrics.append(PerformanceMetric(
                    name="deadlock_count",
                    value=deadlock_count,
                    unit="count",
                    category=MetricCategory.LOCK,
                    source="v$sysstat"
                ))

        except Exception as e:
            logger.warning(f"锁指标采集失败: {e}")

        return metrics

    def collect_slow_queries(self, limit: int = 20,
                            min_time_ms: float = 1000) -> List[SlowQueryInfo]:
        """
        采集Oracle慢查询

        参数:
            limit: 返回条数限制
            min_time_ms: 最小执行时间(毫秒)

        返回:
            慢查询列表
        """
        queries = []

        try:
            # 优先从AWR获取（如果有许可）
            if self._has_awr:
                result = self._execute_with_timeout(f"""
                    SELECT
                        sql_id,
                        sql_text,
                        executions,
                        elapsed_time_total / 1000000 as total_time_sec,
                        elapsed_time_total / executions / 1000000 as avg_time_sec,
                        cpu_time_total / 1000000 as cpu_time_sec,
                        buffer_gets_total,
                        disk_reads_total,
                        rows_processed_total
                    FROM (
                        SELECT
                            sql_id,
                            sql_text,
                            executions_total as executions,
                            elapsed_time_total,
                            cpu_time_total,
                            buffer_gets_total,
                            disk_reads_total,
                            rows_processed_total,
                            ROW_NUMBER() OVER (ORDER BY elapsed_time_total DESC) as rn
                        FROM dba_hist_sqlstat s
                        JOIN dba_hist_sqltext t ON s.sql_id = t.sql_id
                        WHERE elapsed_time_total / executions_total / 1000000 >= :min_time_sec
                        AND snap_id IN (SELECT MAX(snap_id) FROM dba_hist_snapshot)
                    )
                    WHERE rn <= :limit
                """, (min_time_ms / 1000, limit))

                if result:
                    for row in result:
                        queries.append(SlowQueryInfo(
                            sql_text=row[1],
                            sql_id=row[0],
                            execution_count=row[2],
                            total_time_ms=row[3] * 1000,
                            avg_time_ms=row[4] * 1000,
                            rows_examined=row[7]
                        ))

            # 降级到V$SQL
            if not queries:
                result = self._execute_with_timeout(f"""
                    SELECT
                        sql_id,
                        sql_text,
                        executions,
                        elapsed_time / 1000000 as total_time_sec,
                        cpu_time / 1000000 as cpu_time_sec,
                        buffer_gets,
                        disk_reads,
                        rows_processed
                    FROM (
                        SELECT
                            sql_id,
                            sql_text,
                            executions,
                            elapsed_time,
                            cpu_time,
                            buffer_gets,
                            disk_reads,
                            rows_processed,
                            ROW_NUMBER() OVER (ORDER BY elapsed_time / executions DESC) as rn
                        FROM v$sql
                        WHERE executions > 0
                        AND elapsed_time / executions / 1000000 >= :min_time_sec
                    )
                    WHERE rn <= :limit
                """, (min_time_ms / 1000, limit))

                if result:
                    for row in result:
                        queries.append(SlowQueryInfo(
                            sql_text=row[1],
                            sql_id=row[0],
                            execution_count=row[2],
                            total_time_ms=row[3] * 1000,
                            avg_time_ms=(row[3] * 1000 / row[2]) if row[2] > 0 else 0,
                            rows_examined=row[6]
                        ))

        except Exception as e:
            logger.error(f"慢查询采集失败: {e}")

        return queries

    def get_active_sessions(self) -> Tuple[int, int]:
        """
        获取Oracle会话信息

        返回:
            (活跃会话数, 总会话数)
        """
        try:
            result = self._execute_with_timeout("""
                SELECT
                    SUM(CASE WHEN status = 'ACTIVE' THEN 1 ELSE 0 END) as active,
                    COUNT(*) as total
                FROM v$session
                WHERE type = 'USER'
            """)

            if result:
                return result[0][0] or 0, result[0][1] or 0

        except Exception as e:
            logger.error(f"会话信息采集失败: {e}")

        return 0, 0
