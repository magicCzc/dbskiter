"""
数据库诊断策略模块

提供多数据库支持的诊断策略实现
"""

from .base import BaseDiagnostician
from .mysql_diagnostician import MySQLDiagnostician
from .oracle_diagnostician import OracleDiagnostician
from .postgresql_diagnostician import PostgreSQLDiagnostician
from .mssql_diagnostician import MSSQLDiagnostician
from .clickhouse_diagnostician import ClickHouseDiagnostician
from .sqlite_diagnostician import SQLiteDiagnostician
from .generic_diagnostician import GenericDiagnostician

__all__ = [
    'BaseDiagnostician',
    'MySQLDiagnostician',
    'OracleDiagnostician',
    'PostgreSQLDiagnostician',
    'MSSQLDiagnostician',
    'ClickHouseDiagnostician',
    'SQLiteDiagnostician',
    'GenericDiagnostician',
]


def get_diagnostician(dialect: str, connector):
    """
    根据数据库类型获取对应的诊断器

    参数:
        dialect: 数据库方言，如'mysql', 'oracle', 'postgresql', 'mssql'
        connector: 数据库连接器

    返回:
        BaseDiagnostician: 对应数据库的诊断器实例

    示例:
        >>> diagnostician = get_diagnostician('mysql', connector)
        >>> result = diagnostician.analyze_slow_queries()
    """
    dialect = dialect.lower()

    if 'mysql' in dialect:
        return MySQLDiagnostician(connector)
    elif 'oracle' in dialect:
        return OracleDiagnostician(connector)
    elif 'postgresql' in dialect:
        return PostgreSQLDiagnostician(connector)
    elif 'mssql' in dialect or 'sqlserver' in dialect:
        return MSSQLDiagnostician(connector)
    elif 'clickhouse' in dialect:
        return ClickHouseDiagnostician(connector)
    elif 'sqlite' in dialect:
        return SQLiteDiagnostician(connector)
    else:
        # 默认使用通用诊断器
        return GenericDiagnostician(connector)
