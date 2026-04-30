"""
db_sql_auditor analyzers 包 - DDL影响分析器

文件功能：提供多数据库DDL影响分析器的工厂函数和导出
主要类/函数：
    - get_ddl_analyzer: 根据数据库方言获取对应的DDL分析器
    - BaseDDLAnalyzer: DDL分析器基类
    - MySQLDDLAnalyzer: MySQL DDL分析器
    - OracleDDLAnalyzer: Oracle DDL分析器
    - PostgreSQLDDLAnalyzer: PostgreSQL DDL分析器

使用示例：
    from db_sql_auditor.analyzers import get_ddl_analyzer

    analyzer = get_ddl_analyzer('mysql', connector)
    impact = analyzer.analyze_impact("ALTER TABLE users ADD COLUMN age INT")

作者：AI Assistant
创建时间：2026-04-23
"""

from .base import BaseDDLAnalyzer, DDLImpact
from .mysql_analyzer import MySQLDDLAnalyzer
from .oracle_analyzer import OracleDDLAnalyzer
from .postgresql_analyzer import PostgreSQLDDLAnalyzer

__all__ = [
    'BaseDDLAnalyzer',
    'MySQLDDLAnalyzer',
    'OracleDDLAnalyzer',
    'PostgreSQLDDLAnalyzer',
    'get_ddl_analyzer',
    'DDLImpact',
]


def get_ddl_analyzer(dialect: str, connector):
    """
    根据数据库类型获取对应的DDL分析器

    参数:
        dialect: 数据库方言，如'mysql', 'oracle', 'postgresql'
        connector: 数据库连接器

    返回:
        BaseDDLAnalyzer: 对应数据库的DDL分析器实例

    示例:
        >>> analyzer = get_ddl_analyzer('mysql', connector)
        >>> impact = analyzer.analyze_impact("ALTER TABLE users ADD COLUMN age INT")
    """
    dialect = dialect.lower()

    if 'mysql' in dialect:
        return MySQLDDLAnalyzer(connector)
    elif 'oracle' in dialect:
        return OracleDDLAnalyzer(connector)
    elif 'postgresql' in dialect:
        return PostgreSQLDDLAnalyzer(connector)
    else:
        raise ValueError(f"不支持的数据库方言: {dialect}")
