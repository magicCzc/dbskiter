"""
数据库巡检策略模块

提供多数据库支持的巡检策略实现
"""

from .base import BaseInspector
from .mysql_inspector import MySQLInspector
from .oracle_inspector import OracleInspector
from .postgresql_inspector import PostgreSQLInspector
from .generic_inspector import GenericInspector

__all__ = [
    'BaseInspector',
    'MySQLInspector',
    'OracleInspector',
    'PostgreSQLInspector',
    'GenericInspector',
]


def get_inspector(dialect: str, connector):
    """
    根据数据库类型获取对应的巡检器

    参数:
        dialect: 数据库方言，如'mysql', 'oracle', 'postgresql'
        connector: 数据库连接器

    返回:
        BaseInspector: 对应数据库的巡检器实例

    示例:
        >>> inspector = get_inspector('mysql', connector)
        >>> items = inspector.inspect_configuration()
    """
    dialect = dialect.lower()

    if 'mysql' in dialect:
        return MySQLInspector(connector)
    elif 'oracle' in dialect:
        return OracleInspector(connector)
    elif 'postgresql' in dialect:
        return PostgreSQLInspector(connector)
    else:
        # 默认使用通用巡检器
        return GenericInspector(connector)
