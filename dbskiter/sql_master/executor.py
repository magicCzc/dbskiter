"""
sql_master/executor.py
SQL 执行器 - 核心执行能力
"""

from typing import Optional, Any, List

from dbskiter.shared.unified_connector import UnifiedConnector
from dbskiter.shared.database_connector import DatabaseConnector, QueryResult


class SQLExecutor:
    """
    SQL 执行器

    用法:
        executor = SQLExecutor()
        executor.connect(dialect="sqlite", database="mydb.db")
        result = executor.execute("SELECT * FROM users")
        print(result.df)
    """

    def __init__(self, connector: Optional[UnifiedConnector] = None):
        self._connector = connector

    def connect(
        self,
        dialect: str = "sqlite",
        host: str = "localhost",
        port: int = 3306,
        username: str = "",
        password: str = "",
        database: str = "",
        filename: str = ""
    ) -> "SQLExecutor":
        """建立数据库连接"""
        self._connector = DatabaseConnector(
            dialect=dialect,
            host=host,
            port=port,
            username=username,
            password=password,
            database=database,
            filename=filename
        )
        return self

    def connect_sqlite(self, db_path: str = ":memory:") -> "SQLExecutor":
        """快速连接 SQLite"""
        self._connector = connect_sqlite(db_path)
        return self

    def connect_mysql(
        self,
        host: str = "localhost",
        port: int = 3306,
        username: str = "root",
        password: str = "",
        database: str = ""
    ) -> "SQLExecutor":
        """快速连接 MySQL"""
        self._connector = connect_mysql(host, port, username, password, database)
        return self

    def execute(self, sql: str, params: tuple = None) -> QueryResult:
        """
        执行 SQL 查询

        Args:
            sql: SQL 语句
            params: 参数（防注入）
        """
        if not self._connector:
            raise RuntimeError("请先调用 connect() 建立连接")
        return self._connector.execute(sql, params)

    def query(self, sql: str, params: tuple = None) -> QueryResult:
        """查询别名"""
        return self.execute(sql, params)

    def get_tables(self) -> List[str]:
        """获取所有表"""
        if not self._connector:
            raise RuntimeError("请先调用 connect() 建立连接")
        return self._connector.get_tables()

    def get_schema(self, table: str) -> Any:
        """获取表结构"""
        if not self._connector:
            raise RuntimeError("请先调用 connect() 建立连接")
        return self._connector.get_schema(table)

    def preview(self, table: str, limit: int = 10) -> Any:
        """预览表数据"""
        if not self._connector:
            raise RuntimeError("请先调用 connect() 建立连接")
        return self._connector.table_preview(table, limit)

    def close(self):
        """关闭连接"""
        if self._connector:
            self._connector.close()

    @property
    def connector(self) -> Optional[UnifiedConnector]:
        return self._connector
