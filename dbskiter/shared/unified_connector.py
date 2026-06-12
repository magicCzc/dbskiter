"""
shared/unified_connector.py
统一数据库连接器

文件功能：支持多种数据库连接方式，自动选择合适的连接驱动
主要类：UnifiedConnector - 统一数据库连接器

支持的连接方式:
    - SQLAlchemy (mysql, postgresql, oracle+oracledb)
    - JDBC (oracle+jdbc for 旧版本 Oracle)

自动根据 dialect 选择合适的连接方式

使用示例:
    >>> from dbskiter.shared.unified_connector import UnifiedConnector
    >>> # MySQL - 使用 SQLAlchemy
    >>> conn = UnifiedConnector.from_env("DB")
    >>> # Oracle 旧版本 - 使用 JDBC
    >>> conn = UnifiedConnector.from_env("ORACLE")
    >>> result = conn.execute("SELECT * FROM dual")

版本: 2.0.0
作者: AI Assistant
创建时间: 2026-04-24
"""

import os
import logging
from typing import List, Dict, Any, Optional, Tuple, Union

# 导入统一的QueryResult
from .query_result import QueryResult

logger = logging.getLogger(__name__)


class UnifiedConnector:
    """
    统一数据库连接器

    自动选择连接方式:
    - mysql/postgresql: 使用 SQLAlchemy
    - oracle+oracledb: 使用 SQLAlchemy
    - oracle+jdbc: 使用 JayDeBeApi + JDBC

    参数:
        dialect: 数据库类型
        host: 主机地址
        port: 端口号
        username: 用户名
        password: 密码
        database: 数据库名/服务名
        **kwargs: 额外参数

    使用示例:
        >>> conn = UnifiedConnector(
        ...     dialect="mysql",
        ...     host="localhost",
        ...     port=3306,
        ...     username="root",
        ...     password="password",
        ...     database="test"
        ... )
        >>> result = conn.execute("SELECT * FROM users")
        >>> print(result.summary())
    """

    def __init__(
        self,
        dialect: str = "mysql",
        host: str = "localhost",
        port: int = 3306,
        username: str = "",
        password: str = "",
        database: str = "",
        **kwargs
    ):
        self.dialect = dialect.lower()
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.database = database
        self.kwargs = kwargs

        # 内部连接器
        self._connector = None
        self._connector_type = None

        # 初始化
        self._init_connector()

    def _init_connector(self):
        """初始化合适的连接器"""
        # 优先根据 dialect 判断连接方式
        if "oracle+jdbc" in self.dialect:
            # 明确指定使用 JDBC
            self._init_jdbc_connector()
        elif "oracle+oracledb" in self.dialect:
            # 明确指定使用 oracledb
            self._init_sqlalchemy_connector()
        elif "oracle" in self.dialect:
            # 只指定了 oracle，根据环境和配置自动选择
            # 如果配置了 JDBC 驱动路径，优先使用 JDBC（支持旧版本 Oracle）
            if self._has_jdbc_driver():
                self._init_jdbc_connector()
            else:
                self._init_sqlalchemy_connector()
        else:
            # 其他数据库使用 SQLAlchemy
            self._init_sqlalchemy_connector()

    def _has_jdbc_driver(self) -> bool:
        """检查是否配置了 JDBC 驱动"""
        return bool(self.kwargs.get("jdbc_driver_path") or os.getenv("ORACLE_JDBC_DRIVER"))

    def _init_jdbc_connector(self):
        """初始化 JDBC 连接器"""
        try:
            from .oracle_jdbc_connector import OracleJDBCConnector

            # 获取 JDBC 驱动路径
            driver_path = self.kwargs.get("jdbc_driver_path") or os.getenv("ORACLE_JDBC_DRIVER")

            self._connector = OracleJDBCConnector(
                host=self.host,
                port=self.port,
                username=self.username,
                password=self.password,
                service=self.database or self.kwargs.get("service_name", ""),
                jdbc_driver_path=driver_path
            )
            self._connector_type = "jdbc"
            logger.info(f"使用 JDBC 连接 Oracle: {self.host}:{self.port}/{self.database}")
        except Exception as e:
            logger.error(f"JDBC 连接器初始化失败: {e}")
            raise

    def _init_sqlalchemy_connector(self):
        """初始化 SQLAlchemy 连接器"""
        try:
            from .database_connector import DatabaseConnector

            self._connector = DatabaseConnector(
                dialect=self.dialect,
                host=self.host,
                port=self.port,
                username=self.username,
                password=self.password,
                database=self.database,
                **self.kwargs
            )
            self._connector_type = "sqlalchemy"
            logger.info(f"使用 SQLAlchemy 连接: {self.dialect}")
        except Exception as e:
            logger.error(f"SQLAlchemy 连接器初始化失败: {e}")
            raise

    def execute(self, sql: str, params: Optional[Tuple] = None) -> QueryResult:
        """
        执行 SQL 查询

        参数:
            sql: SQL 语句
            params: 查询参数

        返回:
            QueryResult 对象

        使用示例:
            >>> result = conn.execute("SELECT * FROM users WHERE id = %s", (1,))
            >>> print(f"返回 {result.row_count} 行")
        """
        result = self._connector.execute(sql, params)

        # 统一转换为标准QueryResult
        if self._connector_type == "jdbc":
            return QueryResult(
                rows=result.rows,
                columns=result.columns,
                row_count=result.row_count,
                execution_time_ms=result.execution_time_ms
            )
        else:
            # SQLAlchemy connector 返回的 QueryResult
            return QueryResult(
                rows=result.rows,
                columns=result.columns if hasattr(result, 'columns') else [],
                row_count=result.row_count if hasattr(result, 'row_count') else len(result.rows),
                execution_time_ms=result.execution_time_ms if hasattr(result, 'execution_time_ms') else 0,
                affected_rows=result.affected_rows if hasattr(result, 'affected_rows') else 0
            )

    def get_schema(self, table_name: str) -> Any:
        """
        获取表结构

        参数:
            table_name: 表名

        返回:
            DataFrame: 包含列信息的DataFrame
        """
        if self._connector_type == "jdbc":
            # JDBC 方式获取表结构
            return self._get_schema_jdbc(table_name)
        else:
            # SQLAlchemy 方式
            return self._connector.get_schema(table_name)

    def _get_schema_jdbc(self, table_name: str) -> Any:
        """
        JDBC 方式获取表结构（通用实现）

        优先使用 INFORMATION_SCHEMA，失败后回退到 SELECT * WHERE 1=0
        """
        import pandas as pd

        # 1. 尝试 INFORMATION_SCHEMA（适用于大多数 JDBC 数据库）
        try:
            result = self.execute(
                "SELECT column_name, data_type, is_nullable "
                "FROM information_schema.columns "
                "WHERE table_name = ? "
                "ORDER BY ordinal_position",
                (table_name,)
            )
            if result.rows:
                df = pd.DataFrame(
                    result.rows,
                    columns=["column_name", "data_type", "nullable"]
                )
                return df
        except Exception:
            pass

        # 2. 尝试 Oracle 风格（兼容旧版本 Oracle JDBC）
        try:
            result = self.execute("""
                SELECT column_name, data_type, data_length, nullable
                FROM user_tab_columns
                WHERE table_name = :table_name
                ORDER BY column_id
            """, {"table_name": table_name.upper()})
            if result.rows:
                df = pd.DataFrame(
                    result.rows,
                    columns=["column_name", "data_type", "data_length", "nullable"]
                )
                return df
        except Exception:
            pass

        # 3. 回退：执行空查询获取列名
        result = self.execute(f"SELECT * FROM {table_name} WHERE 1=0")
        df = pd.DataFrame(columns=result.columns)
        return df

    def get_tables(self) -> List[str]:
        """
        获取所有表名

        返回:
            List[str]: 表名列表

        实现委托给底层 connector, 支持所有方言的完整查询语句。
        """
        if hasattr(self._connector, 'get_tables'):
            return self._connector.get_tables()
        # fallback: 按方言分别处理
        if "oracle" in self.dialect:
            result = self.execute("SELECT table_name FROM user_tables ORDER BY table_name")
        elif "postgresql" in self.dialect:
            result = self.execute("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
        elif "sqlite" in self.dialect:
            result = self.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
        elif "mssql" in self.dialect:
            result = self.execute("SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_TYPE = 'BASE TABLE' ORDER BY TABLE_NAME")
        else:
            # 通用回退：使用 INFORMATION_SCHEMA（适用于 Trino/DuckDB/Derby/H2 等）
            result = self.execute(
                "SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES "
                "WHERE TABLE_TYPE = 'BASE TABLE' ORDER BY TABLE_NAME"
            )
        return [row[0] for row in result.rows]

    def close(self):
        """关闭连接"""
        if self._connector_type == "jdbc":
            self._connector.disconnect()
        else:
            # SQLAlchemy 方式：调用底层 DatabaseConnector.close()
            if hasattr(self._connector, 'close'):
                self._connector.close()

    def table_preview(self, table: str, limit: int = 10) -> Any:
        """
        预览表数据（委托给底层连接器）

        参数:
            table: 表名
            limit: 最大返回行数

        返回:
            DataFrame: 数据预览
        """
        if self._connector_type == "jdbc":
            result = self.execute(f"SELECT * FROM {table} LIMIT {int(limit)}")
            import pandas as pd
            if result.columns:
                return pd.DataFrame(result.rows, columns=result.columns)
            return pd.DataFrame()
        else:
            # SQLAlchemy 方式
            if hasattr(self._connector, 'table_preview'):
                return self._connector.table_preview(table, limit)
            # 回退
            result = self.execute(f"SELECT * FROM {table} LIMIT {int(limit)}")
            import pandas as pd
            if result.columns:
                return pd.DataFrame(result.rows, columns=result.columns)
            return pd.DataFrame()

    @classmethod
    def from_env(cls, prefix: str = "DB") -> "UnifiedConnector":
        """
        从环境变量创建连接器

        参数:
            prefix: 环境变量前缀

        支持的环境变量:
            - {prefix}_HOST: 主机地址
            - {prefix}_PORT: 端口号
            - {prefix}_USER: 用户名
            - {prefix}_PASSWORD: 密码
            - {prefix}_NAME: 数据库名
            - {prefix}_DIALECT: 数据库类型
            - {prefix}_SERVICE: Oracle 服务名
            - {prefix}_JDBC_DRIVER: JDBC 驱动路径

        使用示例:
            >>> # 使用 DB_* 环境变量
            >>> conn = UnifiedConnector.from_env("DB")
            >>> # 使用 ORACLE_* 环境变量
            >>> conn = UnifiedConnector.from_env("ORACLE")
        """
        host = os.getenv(f"{prefix}_HOST", "localhost")
        port = int(os.getenv(f"{prefix}_PORT", "3306"))
        username = os.getenv(f"{prefix}_USER", "")
        password = os.getenv(f"{prefix}_PASSWORD", "")
        database = os.getenv(f"{prefix}_NAME", "")
        dialect = os.getenv(f"{prefix}_DIALECT", "mysql+pymysql")

        kwargs = {}

        # Oracle 特殊处理
        if "oracle" in dialect.lower():
            service = os.getenv(f"{prefix}_SERVICE", database)
            kwargs["service_name"] = service
            kwargs["jdbc_driver_path"] = os.getenv(f"{prefix}_JDBC_DRIVER")
            if port == 3306:
                port = 1521

        # SQL Server 特殊处理
        if "mssql" in dialect.lower():
            if port == 3306:
                port = 1433

        return cls(
            dialect=dialect,
            host=host,
            port=port,
            username=username,
            password=password,
            database=database,
            **kwargs
        )


def detect_connector_type(dialect: str) -> str:
    """
    检测连接器类型

    参数:
        dialect: 数据库方言

    返回:
        str: 连接器类型 ("sqlalchemy" 或 "jdbc")

    使用示例:
        >>> detect_connector_type("mysql")
        'sqlalchemy'
        >>> detect_connector_type("oracle+jdbc")
        'jdbc'
    """
    if "oracle+jdbc" in dialect.lower():
        return "jdbc"
    return "sqlalchemy"
