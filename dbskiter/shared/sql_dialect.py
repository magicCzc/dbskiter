"""
SQL方言管理器

文件功能：统一管理不同数据库的SQL方言差异
主要类：
    - SQLDialect: SQL方言枚举
    - SQLDialectManager: SQL方言管理器

作者：Magiczc
创建时间：2026-04-28
"""

from enum import Enum
from typing import Dict, Optional, Callable
import logging

logger = logging.getLogger(__name__)


class SQLDialect(Enum):
    """SQL方言枚举"""
    MYSQL = "mysql"
    POSTGRESQL = "postgresql"
    ORACLE = "oracle"
    SQLITE = "sqlite"
    SQLSERVER = "sqlserver"


class SQLDialectManager:
    """
    SQL方言管理器

    统一管理不同数据库的SQL语法差异，包括：
    - 限制子句（LIMIT/FETCH FIRST/ROWNUM/TOP）
    - 版本查询
    - 日期函数
    - 字符串函数

    使用示例:
        >>> dialect = SQLDialectManager.detect_dialect("mysql+pymysql")
        >>> limit_sql = dialect.get_limit_sql("SELECT * FROM users", 10)
        >>> print(limit_sql)  # SELECT * FROM users LIMIT 10
    """

    def __init__(self, dialect: str):
        """
        初始化方言管理器

        参数:
            dialect: 数据库方言字符串
        """
        self.dialect = self._normalize_dialect(dialect)
        self._handlers: Dict[str, Callable] = {
            "mysql": self._mysql_handler,
            "postgresql": self._postgresql_handler,
            "oracle": self._oracle_handler,
            "sqlite": self._sqlite_handler,
            "sqlserver": self._sqlserver_handler,
        }

    def _normalize_dialect(self, dialect: str) -> str:
        """规范化方言名称"""
        dialect = dialect.lower()
        if "mysql" in dialect:
            return "mysql"
        elif "postgresql" in dialect:
            return "postgresql"
        elif "oracle" in dialect:
            return "oracle"
        elif "sqlite" in dialect:
            return "sqlite"
        elif "sqlserver" in dialect or "mssql" in dialect:
            return "sqlserver"
        return dialect

    def get_limit_sql(self, base_sql: str, limit: int, offset: Optional[int] = None) -> str:
        """
        获取带限制的SQL

        参数:
            base_sql: 基础SQL（不含限制子句）
            limit: 限制数量
            offset: 偏移量（可选）

        返回:
            str: 完整的SQL语句
        """
        handler = self._handlers.get(self.dialect, self._mysql_handler)
        return handler(base_sql, limit, offset)

    def _mysql_handler(self, sql: str, limit: int, offset: Optional[int]) -> str:
        """MySQL限制子句处理"""
        if offset is not None:
            return f"{sql} LIMIT {offset}, {limit}"
        return f"{sql} LIMIT {limit}"

    def _postgresql_handler(self, sql: str, limit: int, offset: Optional[int]) -> str:
        """PostgreSQL限制子句处理"""
        if offset is not None:
            return f"{sql} LIMIT {limit} OFFSET {offset}"
        return f"{sql} LIMIT {limit}"

    def _oracle_handler(self, sql: str, limit: int, offset: Optional[int]) -> str:
        """Oracle限制子句处理（使用ROWNUM兼容旧版本）"""
        sql = sql.strip()
        if offset is not None:
            # Oracle 12c+ 支持 OFFSET FETCH，但为了兼容性使用ROWNUM
            return f"""
                SELECT * FROM (
                    SELECT t.*, ROWNUM as rnum FROM (
                        {sql}
                    ) t WHERE ROWNUM <= {offset + limit}
                ) WHERE rnum > {offset}
            """.strip()
        # 简单的ROWNUM限制
        if "ORDER BY" in sql.upper():
            return f"""
                SELECT * FROM (
                    {sql}
                ) WHERE ROWNUM <= {limit}
            """.strip()
        return f"{sql} WHERE ROWNUM <= {limit}"

    def _sqlite_handler(self, sql: str, limit: int, offset: Optional[int]) -> str:
        """SQLite限制子句处理"""
        if offset is not None:
            return f"{sql} LIMIT {limit} OFFSET {offset}"
        return f"{sql} LIMIT {limit}"

    def _sqlserver_handler(self, sql: str, limit: int, offset: Optional[int]) -> str:
        """SQL Server限制子句处理"""
        if offset is not None:
            return f"{sql} OFFSET {offset} ROWS FETCH NEXT {limit} ROWS ONLY"
        # SQL Server 使用 TOP
        if sql.upper().startswith("SELECT "):
            return f"SELECT TOP {limit} {sql[7:]}"
        return sql

    def get_version_sql(self) -> str:
        """获取版本查询SQL"""
        version_sqls = {
            "mysql": "SELECT VERSION()",
            "postgresql": "SELECT version()",
            "oracle": "SELECT banner FROM v$version WHERE banner LIKE 'Oracle%' AND ROWNUM = 1",
            "sqlite": "SELECT sqlite_version()",
            "sqlserver": "SELECT @@VERSION",
        }
        return version_sqls.get(self.dialect, "SELECT VERSION()")

    def get_current_database_sql(self) -> str:
        """获取当前数据库名SQL"""
        database_sqls = {
            "mysql": "SELECT DATABASE()",
            "postgresql": "SELECT current_database()",
            "oracle": "SELECT SYS_CONTEXT('USERENV', 'CURRENT_SCHEMA') FROM dual",
            "sqlite": "SELECT 'main'",
            "sqlserver": "SELECT DB_NAME()",
        }
        return database_sqls.get(self.dialect, "SELECT DATABASE()")

    def get_current_user_sql(self) -> str:
        """获取当前用户SQL"""
        user_sqls = {
            "mysql": "SELECT CURRENT_USER()",
            "postgresql": "SELECT current_user",
            "oracle": "SELECT USER FROM dual",
            "sqlite": "SELECT 'sqlite_user'",
            "sqlserver": "SELECT SUSER_SNAME()",
        }
        return user_sqls.get(self.dialect, "SELECT CURRENT_USER()")

    def quote_identifier(self, identifier: str) -> str:
        """
        引用标识符（表名、列名等）

        参数:
            identifier: 标识符

        返回:
            str: 引用后的标识符
        """
        quotes = {
            "mysql": "`",
            "postgresql": '"',
            "oracle": '"',
            "sqlite": '"',
            "sqlserver": "[",
        }
        quote = quotes.get(self.dialect, "")
        if "sqlserver" in self.dialect:
            return f"[{identifier}]"
        return f"{quote}{identifier}{quote}"

    def get_date_format_sql(self, column: str, format_str: str) -> str:
        """
        获取日期格式化SQL

        参数:
            column: 日期列名
            format_str: 格式字符串

        返回:
            str: 格式化SQL
        """
        date_formats = {
            "mysql": f"DATE_FORMAT({column}, '{format_str}')",
            "postgresql": f"TO_CHAR({column}, '{format_str}')",
            "oracle": f"TO_CHAR({column}, '{format_str}')",
            "sqlite": f"strftime('{format_str}', {column})",
            "sqlserver": f"FORMAT({column}, '{format_str}')",
        }
        return date_formats.get(self.dialect, column)

    @classmethod
    def detect_dialect(cls, connection_string: str) -> "SQLDialectManager":
        """
        从连接字符串检测方言

        参数:
            connection_string: 连接字符串或方言标识

        返回:
            SQLDialectManager: 方言管理器实例
        """
        return cls(connection_string)


# 便捷函数
def get_dialect_manager(dialect: str) -> SQLDialectManager:
    """
    获取方言管理器实例

    参数:
        dialect: 数据库方言

    返回:
        SQLDialectManager: 方言管理器实例
    """
    return SQLDialectManager(dialect)
