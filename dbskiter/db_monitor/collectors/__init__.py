"""
db_monitor collectors 包 - 多数据库指标采集器

文件功能：提供多数据库指标采集器的工厂函数和导出
主要类/函数：
    - get_collector: 根据数据库方言获取对应的采集器
    - BaseMetricsCollector: 采集器基类
    - MySQLMetricsCollector: MySQL指标采集器
    - OracleMetricsCollector: Oracle指标采集器
    - PostgreSQLMetricsCollector: PostgreSQL指标采集器
    - MSSQLMetricsCollector: SQL Server指标采集器
    - ClickHouseMetricsCollector: ClickHouse指标采集器
    - GenericMetricsCollector: 通用指标采集器（支持任意JDBC数据库）

使用示例：
    from db_monitor.collectors import get_collector

    collector = get_collector('mysql', connector)
    metrics = collector.collect_all_metrics()

    # 未知数据库类型自动回退到通用采集器
    generic = get_collector('trino', connector)

作者：AI Assistant
创建时间：2026-04-23
最后修改：2026-06-05（新增GenericMetricsCollector）
"""

import logging

from .base import BaseMetricsCollector, MetricPoint, MetricType
from .mysql_collector import MySQLMetricsCollector
from .oracle_collector import OracleMetricsCollector
from .postgresql_collector import PostgreSQLMetricsCollector
from .mssql_collector import MSSQLMetricsCollector
from .clickhouse_collector import ClickHouseMetricsCollector
from .sqlite_collector import SQLiteMetricsCollector
from .generic_collector import GenericMetricsCollector
from .mock_collector import MockMetricsCollector

__all__ = [
    'BaseMetricsCollector',
    'MySQLMetricsCollector',
    'OracleMetricsCollector',
    'PostgreSQLMetricsCollector',
    'MSSQLMetricsCollector',
    'ClickHouseMetricsCollector',
    'SQLiteMetricsCollector',
    'GenericMetricsCollector',
    'MockMetricsCollector',
    'get_collector',
    'MetricPoint',
    'MetricType',
]

# 已知方言到采集器的映射
# 注意：新增数据库类型时，优先在此注册专用采集器
# 未注册的方言自动回退到 GenericMetricsCollector
KNOWN_COLLECTORS = {
    'mysql': MySQLMetricsCollector,
    'mysql+pymysql': MySQLMetricsCollector,
    'oracle': OracleMetricsCollector,
    'oracle+cx_oracle': OracleMetricsCollector,
    'postgresql': PostgreSQLMetricsCollector,
    'postgresql+psycopg2': PostgreSQLMetricsCollector,
    'mssql': MSSQLMetricsCollector,
    'mssql+pyodbc': MSSQLMetricsCollector,
    'sqlserver': MSSQLMetricsCollector,
    'clickhouse': ClickHouseMetricsCollector,
    'clickhouse+native': ClickHouseMetricsCollector,
    'sqlite': SQLiteMetricsCollector,
    'sqlite+pysqlite': SQLiteMetricsCollector,
    'mock': MockMetricsCollector,
}


def get_collector(dialect: str, connector):
    """
    根据数据库类型获取对应的指标采集器

    参数:
        dialect: 数据库方言，如'mysql', 'oracle', 'postgresql', 'mssql'
        connector: 数据库连接器

    返回:
        BaseMetricsCollector: 对应数据库的采集器实例

    匹配逻辑:
        1. 精确匹配已知方言 -> 返回专用采集器
        2. 前缀匹配（如 'mysql+xxx'）-> 返回对应基础采集器
        3. 未匹配 -> 返回 GenericMetricsCollector（通用采集器）

    示例:
        >>> collector = get_collector('mysql', connector)
        >>> metrics = collector.collect_all_metrics()
        >>> generic = get_collector('trino', connector)  # 通用采集器
    """
    dialect = dialect.lower()

    # 1. 精确匹配
    if dialect in KNOWN_COLLECTORS:
        return KNOWN_COLLECTORS[dialect](connector)

    # 2. 前缀匹配（处理 mysql+pymysql 等变体）
    for known_dialect, collector_class in KNOWN_COLLECTORS.items():
        if dialect.startswith(known_dialect + '+'):
            return collector_class(connector)

    # 3. 子串匹配（处理包含数据库名称的方言字符串）
    if 'mysql' in dialect:
        return MySQLMetricsCollector(connector)
    elif 'oracle' in dialect:
        return OracleMetricsCollector(connector)
    elif 'postgresql' in dialect or 'postgres' in dialect:
        return PostgreSQLMetricsCollector(connector)
    elif 'mssql' in dialect or 'sqlserver' in dialect:
        return MSSQLMetricsCollector(connector)
    elif 'clickhouse' in dialect:
        return ClickHouseMetricsCollector(connector)
    elif 'sqlite' in dialect:
        return SQLiteMetricsCollector(connector)

    # 4. 回退到通用采集器
    logger = logging.getLogger(__name__)
    logger.info(
        f"方言 '{dialect}' 未找到专用采集器，"
        f"回退到 GenericMetricsCollector"
    )
    return GenericMetricsCollector(connector)
