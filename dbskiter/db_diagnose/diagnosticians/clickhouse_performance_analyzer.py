"""
ClickHouse性能分析器 - 基于统一性能模型

文件功能：使用统一性能模型分析ClickHouse数据库性能
主要类：ClickHousePerformanceAnalyzer

特性：
    1. 统一接口：遵循PerformanceAnalyzer基类
    2. 生产安全：内置超时、降级机制
    3. 系统表查询：基于system.*表获取性能指标

作者: Magiczc
创建时间: 2026-06-04
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


class ClickHousePerformanceAnalyzer(PerformanceAnalyzer):
    """
    ClickHouse性能分析器

    使用统一性能模型分析ClickHouse性能，支持：
    - 系统表查询（system.processes, system.metrics等）
    - 生产安全（超时控制）
    """

    def __init__(self, connector: UnifiedConnector, timeout: int = 30):
        """
        初始化ClickHouse性能分析器

        参数:
            connector: 数据库连接器
            timeout: 查询超时时间(秒)
        """
        super().__init__(connector, timeout)

    def collect_metrics(self) -> List[PerformanceMetric]:
        """
        采集ClickHouse性能指标

        返回:
            性能指标列表
        """
        metrics = []

        # 采集各类指标
        metrics.extend(self._collect_cpu_metrics())
        metrics.extend(self._collect_memory_metrics())
        metrics.extend(self._collect_io_metrics())
        metrics.extend(self._collect_concurrency_metrics())

        return metrics

    def _collect_cpu_metrics(self) -> List[PerformanceMetric]:
        """采集CPU相关指标"""
        metrics = []

        try:
            # 获取活跃查询数
            result = self._execute_with_timeout("""
                SELECT COUNT(*)
                FROM system.processes
            """)
            active = result[0][0] if result else 0

            # 获取最大并发查询数
            result = self._execute_with_timeout("""
                SELECT value
                FROM system.settings
                WHERE name = 'max_concurrent_queries'
            """)
            max_queries = int(result[0][0]) if result and result[0] else 100

            ratio = (active / max_queries) * 100 if max_queries > 0 else 0

            threshold = get_threshold("cpu_time_ratio")
            metrics.append(PerformanceMetric(
                name="active_query_ratio",
                value=ratio,
                unit="%",
                category=MetricCategory.CPU,
                threshold_warning=threshold.get("warning"),
                threshold_critical=threshold.get("critical"),
                source="system.processes"
            ))

        except Exception as e:
            logger.warning(f"CPU指标采集失败: {str(e).split(chr(10))[0][:120]}")

        return metrics

    def _collect_memory_metrics(self) -> List[PerformanceMetric]:
        """采集内存相关指标"""
        metrics = []

        try:
            # 获取内存使用指标
            result = self._execute_with_timeout("""
                SELECT
                    metric,
                    value
                FROM system.metrics
                WHERE metric IN (
                    'MemoryTracking',
                    'MemoryTrackingForMerges'
                )
            """)

            memory_dict = {row[0]: row[1] for row in result} if result else {}
            memory_usage = int(memory_dict.get('MemoryTracking', 0))
            memory_merges = int(memory_dict.get('MemoryTrackingForMerges', 0))

            # 转换为MB
            memory_mb = memory_usage / 1024 / 1024

            threshold = get_threshold("memory_usage")
            metrics.append(PerformanceMetric(
                name="memory_tracking_mb",
                value=round(memory_mb, 2),
                unit="MB",
                category=MetricCategory.MEMORY,
                threshold_warning=threshold.get("warning"),
                threshold_critical=threshold.get("critical"),
                source="system.metrics"
            ))

            # Merge内存
            merge_mb = memory_merges / 1024 / 1024
            metrics.append(PerformanceMetric(
                name="memory_merges_mb",
                value=round(merge_mb, 2),
                unit="MB",
                category=MetricCategory.MEMORY,
                source="system.metrics"
            ))

        except Exception as e:
            logger.warning(f"内存指标采集失败: {str(e).split(chr(10))[0][:120]}")

        return metrics

    def _collect_io_metrics(self) -> List[PerformanceMetric]:
        """采集IO相关指标"""
        metrics = []

        try:
            # 获取异步读取指标
            result = self._execute_with_timeout("""
                SELECT
                    event,
                    value
                FROM system.events
                WHERE event IN (
                    'ReadBufferFromFileDescriptorBytes',
                    'WriteBufferFromFileDescriptorBytes'
                )
            """)

            io_dict = {row[0]: row[1] for row in result} if result else {}
            read_bytes = int(io_dict.get('ReadBufferFromFileDescriptorBytes', 0))
            write_bytes = int(io_dict.get('WriteBufferFromFileDescriptorBytes', 0))

            metrics.append(PerformanceMetric(
                name="disk_read_bytes",
                value=read_bytes,
                unit="bytes",
                category=MetricCategory.IO,
                source="system.events"
            ))

            metrics.append(PerformanceMetric(
                name="disk_write_bytes",
                value=write_bytes,
                unit="bytes",
                category=MetricCategory.IO,
                source="system.events"
            ))

        except Exception as e:
            logger.warning(f"IO指标采集失败: {str(e).split(chr(10))[0][:120]}")

        # 采集MergeTree分区健康指标
        try:
            metrics.extend(self._collect_parts_health_metrics())
        except Exception as e:
            logger.warning(f"分区健康指标采集失败: {str(e).split(chr(10))[0][:120]}")

        return metrics

    def _collect_parts_health_metrics(self) -> List[PerformanceMetric]:
        """
        采集MergeTree分区健康指标

        检测分区数量是否超过阈值:
        - parts_to_delay_insert (默认1000): 开始延迟插入
        - parts_to_throw_insert (默认3000): 拒绝插入

        返回:
            List[PerformanceMetric]: 分区健康指标列表
        """
        metrics = []

        try:
            # 获取最大分区数阈值
            result = self._execute_with_timeout("""
                SELECT name, value
                FROM system.settings
                WHERE name IN ('parts_to_delay_insert', 'parts_to_throw_insert')
            """)

            settings_dict = {row[0]: int(row[1]) for row in result} if result else {}
            delay_threshold = settings_dict.get('parts_to_delay_insert', 1000)
            throw_threshold = settings_dict.get('parts_to_throw_insert', 3000)

            # 获取各表的分区数量
            result = self._execute_with_timeout("""
                SELECT
                    database,
                    table,
                    COUNT() as part_count
                FROM system.parts
                WHERE active = 1
                GROUP BY database, table
                ORDER BY part_count DESC
                LIMIT 20
            """)

            max_parts = 0
            max_parts_table = ""
            tables_over_delay = 0
            tables_over_throw = 0

            for row in result if result else []:
                part_count = int(row[2]) if row[2] else 0
                if part_count > max_parts:
                    max_parts = part_count
                    max_parts_table = f"{row[0]}.{row[1]}"

                if part_count > delay_threshold:
                    tables_over_delay += 1
                if part_count > throw_threshold:
                    tables_over_throw += 1

            # 最大分区数指标
            metrics.append(PerformanceMetric(
                name="max_parts_count",
                value=max_parts,
                unit="count",
                category=MetricCategory.IO,
                source="system.parts"
            ))

            # 超过延迟阈值的表数量
            if tables_over_delay > 0:
                metrics.append(PerformanceMetric(
                    name="tables_over_delay_threshold",
                    value=tables_over_delay,
                    unit="count",
                    category=MetricCategory.IO,
                    threshold_warning=1,
                    threshold_critical=5,
                    source="system.parts"
                ))

            # 超过拒绝阈值的表数量
            if tables_over_throw > 0:
                metrics.append(PerformanceMetric(
                    name="tables_over_throw_threshold",
                    value=tables_over_throw,
                    unit="count",
                    category=MetricCategory.IO,
                    threshold_warning=1,
                    threshold_critical=1,
                    source="system.parts"
                ))

            # 记录详细信息
            if max_parts > delay_threshold:
                logger.warning(
                    f"表 {max_parts_table} 分区数量({max_parts})超过延迟阈值({delay_threshold})"
                )

        except Exception as e:
            logger.warning(f"分区健康检查失败: {str(e).split(chr(10))[0][:120]}")

        return metrics

    def _collect_concurrency_metrics(self) -> List[PerformanceMetric]:
        """采集并发相关指标"""
        metrics = []

        try:
            # 获取当前连接数
            result = self._execute_with_timeout("""
                SELECT COUNT(*)
                FROM system.processes
            """)
            current_conn = result[0][0] if result else 0

            # 获取最大连接数
            result = self._execute_with_timeout("""
                SELECT value
                FROM system.settings
                WHERE name = 'max_concurrent_queries'
            """)
            max_conn = int(result[0][0]) if result and result[0] else 100

            usage_pct = (current_conn / max_conn) * 100 if max_conn > 0 else 0

            threshold = get_threshold("connection_usage")
            metrics.append(PerformanceMetric(
                name="connection_usage",
                value=round(usage_pct, 2),
                unit="%",
                category=MetricCategory.CONCURRENCY,
                threshold_warning=threshold.get("warning"),
                threshold_critical=threshold.get("critical"),
                source="system.processes"
            ))

        except Exception as e:
            logger.warning(f"并发指标采集失败: {str(e).split(chr(10))[0][:120]}")

        return metrics

    def collect_slow_queries(self, limit: int = 20,
                            min_time_ms: float = 1000) -> List[SlowQueryInfo]:
        """
        采集慢查询

        ClickHouse慢查询采集策略:
        1. 优先查询system.query_log获取历史慢查询（推荐）
        2. 降级查询system.processes获取当前运行查询

        参数:
            limit: 返回条数限制
            min_time_ms: 最小执行时间(毫秒)

        返回:
            慢查询列表
        """
        slow_queries = []

        # 策略1: 查询system.query_log获取历史慢查询
        try:
            result = self._execute_with_timeout(f"""
                SELECT
                    query_id,
                    query,
                    user,
                    query_duration_ms,
                    read_rows,
                    memory_usage
                FROM system.query_log
                WHERE type = 'QueryFinish'
                    AND query_duration_ms >= {min_time_ms}
                    AND event_time > now() - INTERVAL 1 HOUR
                ORDER BY query_duration_ms DESC
                LIMIT {limit}
            """)

            for row in result if result else []:
                slow_queries.append(SlowQueryInfo(
                    sql_text=str(row[1]) if row[1] else "",
                    sql_id=str(row[0]) if row[0] else None,
                    total_time_ms=float(row[3]) if row[3] else 0,
                    avg_time_ms=float(row[3]) if row[3] else 0,
                    rows_examined=int(row[4]) if row[4] else 0,
                    database=None
                ))

            if slow_queries:
                logger.info(f"从system.query_log采集到 {len(slow_queries)} 条慢查询")
                return slow_queries

        except Exception as e:
            logger.warning(f"从system.query_log采集慢查询失败: {str(e).split(chr(10))[0][:120]}")

        # 策略2: 降级查询system.processes获取当前运行查询
        try:
            min_time_sec = min_time_ms / 1000

            result = self._execute_with_timeout(f"""
                SELECT
                    query_id,
                    query,
                    user,
                    elapsed,
                    read_rows,
                    memory_usage
                FROM system.processes
                WHERE elapsed >= {min_time_sec}
                ORDER BY elapsed DESC
                LIMIT {limit}
            """)

            for row in result if result else []:
                slow_queries.append(SlowQueryInfo(
                    sql_text=str(row[1]) if row[1] else "",
                    sql_id=str(row[0]) if row[0] else None,
                    total_time_ms=float(row[3]) * 1000 if row[3] else 0,
                    avg_time_ms=float(row[3]) * 1000 if row[3] else 0,
                    rows_examined=int(row[4]) if row[4] else 0,
                    database=None
                ))

            if slow_queries:
                logger.info(f"从system.processes采集到 {len(slow_queries)} 条慢查询")

        except Exception as e:
            logger.warning(f"从system.processes采集慢查询失败: {str(e).split(chr(10))[0][:120]}")

        return slow_queries

    def get_active_sessions(self) -> Tuple[int, int]:
        """
        获取会话信息

        返回:
            (活跃会话数, 总会话数)
        """
        try:
            result = self._execute_with_timeout("""
                SELECT COUNT(*)
                FROM system.processes
            """)
            active = result[0][0] if result else 0

            # ClickHouse没有传统连接池概念，使用最大并发查询数
            result = self._execute_with_timeout("""
                SELECT value
                FROM system.settings
                WHERE name = 'max_concurrent_queries'
            """)
            max_conn = int(result[0][0]) if result and result[0] else 100

            return active, max_conn

        except Exception as e:
            logger.warning(f"会话信息采集失败: {str(e).split(chr(10))[0][:120]}")
            return 0, 0
