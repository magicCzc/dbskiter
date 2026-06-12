"""
Mock 指标采集器

文件功能：为演示模式提供模拟的监控指标数据
主要类：MockMetricsCollector - Mock 指标采集器

使用示例：
    >>> from dbskiter.db_monitor.collectors import get_collector
    >>> collector = get_collector('mock', connector)
    >>> metrics = collector.collect_all_metrics()

版本: 1.0.0
作者: AI Assistant
创建时间: 2026-06-12
"""

import logging
from typing import Dict, List, Optional
from datetime import datetime

from .base import BaseMetricsCollector, MetricType, MetricPoint, MetricQuery
from dbskiter.shared.mock_connector import MockConnector

logger = logging.getLogger(__name__)


class MockMetricsCollector(BaseMetricsCollector):
    """
    Mock 指标采集器

    功能描述：
        为演示模式提供模拟的监控指标数据，无需真实数据库连接

    使用示例：
        >>> from dbskiter.db_monitor.collectors import get_collector
        >>> collector = get_collector('mock', connector)
        >>> metrics = collector.collect_all_metrics()
    """

    def __init__(self, connector: MockConnector):
        """
        初始化 Mock 采集器

        参数：
            connector: MockConnector 实例
        """
        super().__init__(connector)
        self._connector = connector

    def get_metric_queries(self) -> Dict[MetricType, MetricQuery]:
        """
        获取指标查询定义（Mock 模式不需要真实查询）

        返回：
            Dict[MetricType, MetricQuery]: 空字典，指标由 collect_all_metrics 直接生成
        """
        return {}

    def collect_all_metrics(self) -> List[MetricPoint]:
        """
        采集所有模拟指标

        返回：
            List[MetricPoint]: 模拟指标数据点列表
        """
        metrics = []
        timestamp = datetime.now()

        # 从 MockConnector 获取模拟指标
        if hasattr(self._connector, 'get_metrics'):
            mock_metrics = self._connector.get_metrics('cpu_usage')
            if mock_metrics:
                # 取最新的值
                latest = mock_metrics[-1]
                metrics.append(MetricPoint(
                    timestamp=timestamp,
                    metric_type=MetricType.CPU_USAGE,
                    value=latest.get('value', 45.0),
                    unit="%",
                    source="mock",
                    tags={"demo": True}
                ))

            mock_metrics = self._connector.get_metrics('memory_usage')
            if mock_metrics:
                latest = mock_metrics[-1]
                metrics.append(MetricPoint(
                    timestamp=timestamp,
                    metric_type=MetricType.MEMORY_USAGE,
                    value=latest.get('value', 68.5),
                    unit="%",
                    source="mock",
                    tags={"demo": True}
                ))

            mock_metrics = self._connector.get_metrics('active_sessions')
            if mock_metrics:
                latest = mock_metrics[-1]
                metrics.append(MetricPoint(
                    timestamp=timestamp,
                    metric_type=MetricType.CONNECTIONS_ACTIVE,
                    value=latest.get('value', 14),
                    unit="count",
                    source="mock",
                    tags={"demo": True}
                ))

            mock_metrics = self._connector.get_metrics('qps')
            if mock_metrics:
                latest = mock_metrics[-1]
                metrics.append(MetricPoint(
                    timestamp=timestamp,
                    metric_type=MetricType.QPS,
                    value=latest.get('value', 2980),
                    unit="qps",
                    source="mock",
                    tags={"demo": True}
                ))

        # 添加一些额外的模拟指标
        metrics.extend([
            MetricPoint(
                timestamp=timestamp,
                metric_type=MetricType.CONNECTIONS_TOTAL,
                value=24,
                unit="count",
                source="mock",
                tags={"demo": True}
            ),
            MetricPoint(
                timestamp=timestamp,
                metric_type=MetricType.SLOW_QUERIES,
                value=3,
                unit="count",
                source="mock",
                tags={"demo": True}
            ),
            MetricPoint(
                timestamp=timestamp,
                metric_type=MetricType.BUFFER_HIT_RATIO,
                value=96.5,
                unit="%",
                source="mock",
                tags={"demo": True}
            ),
            MetricPoint(
                timestamp=timestamp,
                metric_type=MetricType.DISK_USAGE,
                value=82.1,
                unit="%",
                source="mock",
                tags={"demo": True}
            ),
        ])

        logger.info(f"MockMetricsCollector 生成了 {len(metrics)} 个模拟指标")
        return metrics
