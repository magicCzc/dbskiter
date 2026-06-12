"""
ClickHouse监控指标采集器

提供ClickHouse数据库的监控指标采集能力

文件功能：ClickHouse数据库监控指标采集器实现
主要类：ClickHouseMetricsCollector - ClickHouse监控指标采集器

支持的指标：
    - 吞吐量指标：QPS、查询类型分布
    - 连接指标：活跃连接数
    - 查询性能：慢查询数、平均查询时间
    - 资源指标：内存使用、磁盘使用
    - MergeTree指标：活跃parts数、总行数
    - 复制指标：复制延迟、队列大小

依赖：
    - clickhouse-driver 或 clickhouse-connect 驱动
    - ClickHouse 20.0+

作者：AI Assistant
创建时间：2026-06-03
版本：1.0.0
"""

import logging
from datetime import datetime
from typing import Dict, Any, List, Optional

from .base import BaseMetricsCollector, MetricType, MetricPoint, MetricQuery
from dbskiter.shared.unified_connector import UnifiedConnector

logger = logging.getLogger(__name__)


class ClickHouseMetricsCollector(BaseMetricsCollector):
    """
    ClickHouse监控指标采集器

    提供ClickHouse特有的监控指标采集：
    - 查询吞吐量（基于system.query_log）
    - 活跃连接数（system.processes）
    - 慢查询统计
    - 内存使用
    - MergeTree统计
    - 复制状态（Replicated表）

    特性：
    - 自动降级：query_log不可用时使用processes
    - 支持分布式表监控
    - 支持Replicated表复制监控
    """

    def __init__(self, connector: UnifiedConnector):
        """
        初始化ClickHouse采集器

        参数：
            connector: UnifiedConnector实例
        """
        super().__init__(connector)
        self._has_query_log = None

    def _check_query_log_available(self) -> bool:
        """
        检查query_log是否可用

        返回：
            bool: query_log是否可用
        """
        if self._has_query_log is None:
            try:
                result = self.connector.execute("""
                    SELECT count()
                    FROM system.tables
                    WHERE database = 'system' AND name = 'query_log'
                """)
                self._has_query_log = result.rows[0][0] > 0 if result else False
            except Exception as e:
                logger.warning(f"检查query_log失败: {e}")
                self._has_query_log = False
        return self._has_query_log

    def get_metric_queries(self) -> Dict[MetricType, MetricQuery]:
        """
        获取ClickHouse指标查询定义

        返回：
            Dict[MetricType, MetricQuery]: 指标类型到查询定义的映射
        """
        queries = {}

        # QPS - 每秒查询数
        if self._check_query_log_available():
            queries[MetricType.QPS] = MetricQuery(
                sql="""
                    SELECT count() / 60.0
                    FROM system.query_log
                    WHERE type = 'QueryFinish'
                    AND event_time >= now() - INTERVAL 1 MINUTE
                """,
                extract=lambda rows: float(rows[0][0]) if rows and rows[0][0] else 0.0,
                unit="queries/sec",
                is_counter=False
            )
        else:
            queries[MetricType.QPS] = MetricQuery(
                sql="SELECT count() FROM system.processes",
                extract=lambda rows: float(rows[0][0]) if rows else 0.0,
                unit="queries",
                is_counter=False
            )

        # 活跃连接数
        queries[MetricType.CONNECTIONS_ACTIVE] = MetricQuery(
            sql="SELECT count() FROM system.processes",
            extract=lambda rows: int(rows[0][0]) if rows else 0,
            unit="connections",
            is_counter=False
        )

        # 慢查询数（过去1小时，超过1秒）
        if self._check_query_log_available():
            queries[MetricType.SLOW_QUERIES] = MetricQuery(
                sql="""
                    SELECT count()
                    FROM system.query_log
                    WHERE type = 'QueryFinish'
                    AND query_duration_ms >= 1000
                    AND event_time >= now() - INTERVAL 1 HOUR
                """,
                extract=lambda rows: int(rows[0][0]) if rows else 0,
                unit="queries",
                is_counter=False
            )

            # 平均查询时间
            queries[MetricType.QUERY_TIME_AVG] = MetricQuery(
                sql="""
                    SELECT avg(query_duration_ms)
                    FROM system.query_log
                    WHERE type = 'QueryFinish'
                    AND event_time >= now() - INTERVAL 1 HOUR
                """,
                extract=lambda rows: float(rows[0][0]) if rows and rows[0][0] else 0.0,
                unit="ms",
                is_counter=False
            )

            # 最大查询时间
            queries[MetricType.QUERY_TIME_MAX] = MetricQuery(
                sql="""
                    SELECT max(query_duration_ms)
                    FROM system.query_log
                    WHERE type = 'QueryFinish'
                    AND event_time >= now() - INTERVAL 1 HOUR
                """,
                extract=lambda rows: float(rows[0][0]) if rows and rows[0][0] else 0.0,
                unit="ms",
                is_counter=False
            )

        # 内存使用
        queries[MetricType.MEMORY_USAGE] = MetricQuery(
            sql="""
                SELECT sum(memory_usage)
                FROM system.processes
            """,
            extract=lambda rows: int(rows[0][0]) if rows and rows[0][0] else 0,
            unit="bytes",
            is_counter=False
        )

        # MergeTree活跃parts数
        queries[MetricType.TABLE_OPEN_CACHE] = MetricQuery(
            sql="""
                SELECT count()
                FROM system.parts
                WHERE active
            """,
            extract=lambda rows: int(rows[0][0]) if rows else 0,
            unit="parts",
            is_counter=False
        )

        # 读取行数（过去1小时）
        if self._check_query_log_available():
            queries[MetricType.ROWS_READ] = MetricQuery(
                sql="""
                    SELECT sum(read_rows)
                    FROM system.query_log
                    WHERE type = 'QueryFinish'
                    AND event_time >= now() - INTERVAL 1 HOUR
                """,
                extract=lambda rows: int(rows[0][0]) if rows and rows[0][0] else 0,
                unit="rows",
                is_counter=False
            )

        return queries

    def collect_replication_metrics(self) -> List[MetricPoint]:
        """
        采集复制相关指标（Replicated表）

        返回：
            List[MetricPoint]: 复制指标数据点列表
        """
        metrics = []
        timestamp = datetime.now()

        try:
            # 检查是否有Replicated表
            result = self.connector.execute("""
                SELECT count()
                FROM system.tables
                WHERE engine LIKE 'Replicated%'
            """)
            has_replicated = result.rows[0][0] > 0 if result else False

            if not has_replicated:
                return metrics

            # 复制队列大小
            result = self.connector.execute("""
                SELECT
                    sum(queue_size) as total_queue,
                    max(queue_size) as max_queue
                FROM system.replicas
            """)

            if result and result.rows:
                total_queue = int(result.rows[0][0]) if result.rows[0][0] else 0
                max_queue = int(result.rows[0][1]) if result.rows[0][1] else 0

                metrics.append(MetricPoint(
                    timestamp=timestamp,
                    metric_type=MetricType.REPLICATION_LAG,
                    value=float(total_queue),
                    unit="tasks",
                    tags={"type": "total_queue"}
                ))

                metrics.append(MetricPoint(
                    timestamp=timestamp,
                    metric_type=MetricType.REPLICATION_LAG,
                    value=float(max_queue),
                    unit="tasks",
                    tags={"type": "max_queue"}
                ))

        except Exception as e:
            logger.warning(f"采集复制指标失败: {e}")

        return metrics

    def collect_mergetree_metrics(self) -> List[MetricPoint]:
        """
        采集MergeTree相关指标

        返回：
            List[MetricPoint]: MergeTree指标数据点列表
        """
        metrics = []
        timestamp = datetime.now()

        try:
            # 获取MergeTree统计
            result = self.connector.execute("""
                SELECT
                    count() as parts,
                    sum(rows) as total_rows,
                    sum(bytes_on_disk) as total_bytes
                FROM system.parts
                WHERE active
            """)

            if result and result.rows:
                row = result.rows[0]
                metrics.append(MetricPoint(
                    timestamp=timestamp,
                    metric_type=MetricType.TABLE_OPEN_CACHE,
                    value=float(row[0]) if row[0] else 0.0,
                    unit="parts",
                    tags={"type": "active_parts"}
                ))

                metrics.append(MetricPoint(
                    timestamp=timestamp,
                    metric_type=MetricType.ROWS_READ,
                    value=float(row[1]) if row[1] else 0.0,
                    unit="rows",
                    tags={"type": "total_rows", "source": "mergetree"}
                ))

                metrics.append(MetricPoint(
                    timestamp=timestamp,
                    metric_type=MetricType.DISK_USAGE,
                    value=float(row[2]) if row[2] else 0.0,
                    unit="bytes",
                    tags={"type": "mergetree_size"}
                ))

        except Exception as e:
            logger.warning(f"采集MergeTree指标失败: {e}")

        return metrics

    def collect_all_metrics(self) -> List[MetricPoint]:
        """
        采集所有指标（包括基础指标、复制指标、MergeTree指标）

        返回：
            List[MetricPoint]: 所有指标数据点列表
        """
        # 采集基础指标
        metrics = super().collect_all_metrics()

        # 采集复制指标
        metrics.extend(self.collect_replication_metrics())

        # 采集MergeTree指标
        metrics.extend(self.collect_mergetree_metrics())

        logger.info(f"ClickHouse共采集 {len(metrics)} 个指标")
        return metrics

    def get_health_status(self) -> Dict[str, Any]:
        """
        获取ClickHouse健康状态

        返回：
            Dict[str, Any]: 健康状态信息
        """
        status = {
            "status": "healthy",
            "checks": {}
        }

        # 检查查询日志
        try:
            has_query_log = self._check_query_log_available()
            status["checks"]["query_log"] = "available" if has_query_log else "unavailable"
        except Exception as e:
            status["checks"]["query_log"] = f"error: {str(e)}"

        # 检查当前连接数
        try:
            result = self.connector.execute("SELECT count() FROM system.processes")
            connections = int(result.rows[0][0]) if result else 0
            status["checks"]["connections"] = connections
            if connections > 100:
                status["status"] = "warning"
        except Exception as e:
            status["checks"]["connections"] = f"error: {str(e)}"

        # 检查复制状态
        try:
            result = self.connector.execute("""
                SELECT count()
                FROM system.tables
                WHERE engine LIKE 'Replicated%'
            """)
            has_replicated = result.rows[0][0] > 0 if result else False
            status["checks"]["replication"] = "enabled" if has_replicated else "disabled"

            if has_replicated:
                result = self.connector.execute("""
                    SELECT max(queue_size) FROM system.replicas
                """)
                max_queue = int(result.rows[0][0]) if result and result.rows[0][0] else 0
                status["checks"]["replication_queue"] = max_queue
                if max_queue > 1000:
                    status["status"] = "critical"
        except Exception as e:
            status["checks"]["replication"] = f"error: {str(e)}"

        return status
