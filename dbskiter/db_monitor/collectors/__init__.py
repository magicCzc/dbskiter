"""
db_monitor collectors 包 - 多数据库指标采集器

文件功能：提供多数据库指标采集器的工厂函数和导出
主要类/函数：
    - get_collector: 根据数据库方言获取对应的采集器
    - BaseMetricsCollector: 采集器基类
    - MySQLMetricsCollector: MySQL指标采集器
    - OracleMetricsCollector: Oracle指标采集器
    - PostgreSQLMetricsCollector: PostgreSQL指标采集器

使用示例：
    from db_monitor.collectors import get_collector

    collector = get_collector('mysql', connector)
    metrics = collector.collect_all_metrics()

作者：AI Assistant
创建时间：2026-04-23
"""

from .base import BaseMetricsCollector, MetricPoint, MetricType
from .mysql_collector import MySQLMetricsCollector
from .oracle_collector import OracleMetricsCollector
from .postgresql_collector import PostgreSQLMetricsCollector

__all__ = [
    'BaseMetricsCollector',
    'MySQLMetricsCollector',
    'OracleMetricsCollector',
    'PostgreSQLMetricsCollector',
    'get_collector',
    'MetricPoint',
    'MetricType',
]


def get_collector(dialect: str, connector):
    """
    根据数据库类型获取对应的指标采集器

    参数:
        dialect: 数据库方言，如'mysql', 'oracle', 'postgresql'
        connector: 数据库连接器

    返回:
        BaseMetricsCollector: 对应数据库的采集器实例

    示例:
        >>> collector = get_collector('mysql', connector)
        >>> metrics = collector.collect_all_metrics()
    """
    dialect = dialect.lower()

    if 'mysql' in dialect:
        return MySQLMetricsCollector(connector)
    elif 'oracle' in dialect:
        return OracleMetricsCollector(connector)
    elif 'postgresql' in dialect:
        return PostgreSQLMetricsCollector(connector)
    else:
        raise ValueError(f"不支持的数据库方言: {dialect}")
