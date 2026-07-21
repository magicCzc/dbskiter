"""
database_connector.py
数据库连接执行层 - 支持 SQLite / MySQL / PostgreSQL / SQL Server / ClickHouse / Oracle
提供统一的连接管理、SQL 执行、事务控制能力

优化点：
1. 使用连接池替代每次创建引擎
2. 统一错误处理
3. 添加连接健康检查
4. 支持上下文管理器
5. 使用统一的QueryResult
"""

from __future__ import annotations

import os
import re
import time
import logging
from typing import Optional, Dict, Any, List, Tuple, Union
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import quote_plus

import pandas as pd
from sqlalchemy import create_engine, text, Engine
from sqlalchemy.pool import QueuePool
from sqlalchemy.exc import SQLAlchemyError

# 导入统一的QueryResult
from .query_result import QueryResult
from .sql_dialect import SQLDialectManager

logger = logging.getLogger(__name__)


class DatabaseConnector:
    """
    统一数据库连接器
    
    支持: SQLite, MySQL, PostgreSQL, SQL Server, ClickHouse, Oracle
    
    特性:
    - 连接池管理
    - 自动重连
    - 参数化查询防注入
    - 连接健康检查
    
    Example:
        >>> conn = DatabaseConnector(dialect="mysql", host="localhost", 
        ...                          database="test", username="root", password="pass")
        >>> with conn.connect() as session:
        ...     result = conn.execute("SELECT * FROM users WHERE id > %s", (1,))
        >>> print(result.df)
    """

    # 连接池默认配置（可通过 kwargs 或环境变量覆盖）
    POOL_SIZE = 5
    POOL_MAX_OVERFLOW = 10
    POOL_TIMEOUT = 30
    POOL_RECYCLE = 3600  # 1小时回收连接

    def __init__(
        self,
        dialect: str = "sqlite",
        host: str = "localhost",
        port: int = 3306,
        username: str = "",
        password: str = "",
        database: str = "",
        filename: str = "",
        **kwargs
    ):
        """
        初始化数据库连接器

        连接池配置（可通过 kwargs 传入，也可通过对应环境变量设置）：
            pool_size: 池大小（默认5，环境变量 DB_POOL_SIZE）
            pool_max_overflow: 最大溢出（默认10，环境变量 DB_POOL_MAX_OVERFLOW）
            pool_timeout: 超时秒数（默认30，环境变量 DB_POOL_TIMEOUT）
            pool_recycle: 回收秒数（默认3600，环境变量 DB_POOL_RECYCLE）

        Args:
            dialect: 数据库类型 (sqlite/mysql/postgresql/sqlserver/oracle/clickhouse)
            host: 主机地址
            port: 端口号
            username: 用户名
            password: 密码
            database: 数据库名
            filename: SQLite 文件路径
            **kwargs: 额外参数（含连接池覆盖配置）
        """
        self.dialect = dialect.lower()
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.database = database
        self.filename = filename
        self.kwargs = kwargs

        # 从 kwargs 读取连接池配置（支持运行时覆盖）
        import os as _os
        self._pool_size = int(kwargs.get("pool_size",
                            _os.getenv("DB_POOL_SIZE", self.POOL_SIZE)))
        self._pool_max_overflow = int(kwargs.get("pool_max_overflow",
                                      _os.getenv("DB_POOL_MAX_OVERFLOW", self.POOL_MAX_OVERFLOW)))
        self._pool_timeout = int(kwargs.get("pool_timeout",
                                 _os.getenv("DB_POOL_TIMEOUT", self.POOL_TIMEOUT)))
        self._pool_recycle = int(kwargs.get("pool_recycle",
                                  _os.getenv("DB_POOL_RECYCLE", self.POOL_RECYCLE)))

        self._engine: Optional[Engine] = None
        self._engine_url: Optional[str] = None

        self._init_engine()

    @classmethod
    def from_env(cls, prefix: str = "DB") -> "DatabaseConnector":
        """
        从环境变量创建数据库连接器

        优先从 _load_env_values() 读取 .env 文件配置，
        其次从 os.environ 读取系统环境变量。

        参数:
            prefix: 环境变量前缀 (默认: DB)

        支持的环境变量:
            - {prefix}_HOST: 主机地址
            - {prefix}_PORT: 端口号
            - {prefix}_USER: 用户名
            - {prefix}_PASSWORD: 密码
            - {prefix}_NAME: 数据库名
            - {prefix}_DIALECT: 数据库类型
            - {prefix}_SERVICE: Oracle 服务名

        示例:
            >>> # 从 DB_* 环境变量创建
            >>> conn = DatabaseConnector.from_env("DB")
            >>> # 从 ORACLE_* 环境变量创建
            >>> conn = DatabaseConnector.from_env("ORACLE")
        """
        # 优先从 _load_env_values() 读取 .env 文件配置
        try:
            from dbskiter.cli.config import _load_env_values
            env_values = _load_env_values()
        except ImportError:
            env_values = {}

        def _get_env(key: str, default: str = "") -> str:
            """优先从 .env 缓存读取，其次从 os.environ 读取"""
            value = env_values.get(key)
            if value is not None:
                return value
            return os.getenv(key, default)

        host = _get_env(f"{prefix}_HOST", "localhost")
        port_str = _get_env(f"{prefix}_PORT", "3306")
        try:
            port = int(port_str)
        except (ValueError, TypeError):
            port = 3306
        username = _get_env(f"{prefix}_USER", "")
        password = _get_env(f"{prefix}_PASSWORD", "")
        database = _get_env(f"{prefix}_NAME", "")
        dialect = _get_env(f"{prefix}_DIALECT", "mysql+pymysql")

        # Oracle 特殊处理
        kwargs = {}
        if "oracle" in dialect.lower():
            service = _get_env(f"{prefix}_SERVICE", database)
            kwargs["service_name"] = service
            # Oracle 默认端口
            if port == 3306:
                port = 1521

        return cls(
            dialect=dialect,
            host=host,
            port=port,
            username=username,
            password=password,
            database=database,
            **kwargs
        )

    def _convert_positional_to_named(self, sql: str, params: Union[tuple, list]) -> tuple:
        """
        将位置参数(%s)转换为命名参数(:param1)

        SQLAlchemy 2.0+ 要求使用命名参数格式

        参数:
            sql: 包含 %s 的 SQL 语句
            params: 位置参数元组或列表

        返回:
            tuple: (新SQL, 参数字典)
        """
        import re

        new_params = {}
        param_index = 0

        def replace_param(match):
            nonlocal param_index
            param_name = f"param{param_index + 1}"
            new_params[param_name] = params[param_index]
            param_index += 1
            return f":{param_name}"

        # 替换所有 %s 为 :paramN
        new_sql = re.sub(r'%s', replace_param, sql)

        return new_sql, new_params

    def _init_engine(self) -> None:
        """初始化 SQLAlchemy 引擎(连接池)"""
        self._engine_url = self._build_connection_url()

        try:
            self._engine = create_engine(
                self._engine_url,
                poolclass=QueuePool,
                pool_size=self._pool_size,
                max_overflow=self._pool_max_overflow,
                pool_timeout=self._pool_timeout,
                pool_recycle=self._pool_recycle,
                echo=False,
                pool_pre_ping=True,
            )
            logger.info(f"数据库引擎初始化成功: {self.dialect}")
        except Exception as e:
            logger.error(f"数据库引擎初始化失败: {e}")
            raise

    def _build_connection_url(self) -> str:
        """构建数据库连接 URL"""
        if self.dialect in ("sqlite", "sqlite3"):
            return self._build_sqlite_url()
        elif self.dialect in ("mysql", "mysql+pymysql"):
            return self._build_mysql_url()
        elif "postgresql" in self.dialect:
            return self._build_postgresql_url()
        elif "sqlserver" in self.dialect or "mssql" in self.dialect:
            return self._build_sqlserver_url()
        elif self.dialect in ("oracle", "oracle+cx_oracle", "oracle+oracledb"):
            return self._build_oracle_url()
        elif "clickhouse" in self.dialect:
            return self._build_clickhouse_url()
        else:
            # 通用 JDBC URL 构建（适用于 Trino/DuckDB/H2/Derby 等）
            logger.info(
                f"方言 '{self.dialect}' 使用通用 JDBC URL 格式"
            )
            return self._build_generic_url()

    def _build_generic_url(self) -> str:
        """
        构建通用数据库连接 URL

        适用于任何支持 SQLAlchemy 的 JDBC 数据库。
        使用标准格式：dialect://user:pass@host:port/database

        返回：
            str: 通用连接 URL
        """
        encoded_password = quote_plus(self.password) if self.password else ""
        if self.host and self.port:
            return (
                f"{self.dialect}://{self.username}:{encoded_password}"
                f"@{self.host}:{self.port}/{self.database}"
            )
        elif self.database:
            return f"{self.dialect}:///{self.database}"
        else:
            return f"{self.dialect}://"

    def _build_sqlite_url(self) -> str:
        """构建 SQLite URL"""
        if self.filename == ":memory:" or self.database == ":memory:":
            return "sqlite:///:memory:"
        
        db_path = self.filename or self.database
        if not os.path.exists(db_path) and not db_path.endswith(".db"):
            db_path = f"{db_path}.db"
        
        # 确保目录存在
        db_dir = os.path.dirname(db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)
        
        return f"sqlite:///{db_path}"

    def _build_mysql_url(self) -> str:
        """构建 MySQL URL"""
        # URL encode password to handle special characters like @
        encoded_password = quote_plus(self.password) if self.password else ""
        return (
            f"mysql+pymysql://{self.username}:{encoded_password}"
            f"@{self.host}:{self.port}/{self.database}"
        )

    def _build_postgresql_url(self) -> str:
        """构建 PostgreSQL URL"""
        encoded_password = quote_plus(self.password) if self.password else ""
        return (
            f"postgresql://{self.username}:{encoded_password}"
            f"@{self.host}:{self.port}/{self.database}"
        )

    def _build_sqlserver_url(self) -> str:
        """构建 SQL Server URL"""
        encoded_password = quote_plus(self.password) if self.password else ""
        return (
            f"mssql+pyodbc://{self.username}:{encoded_password}"
            f"@{self.host}:{self.port}/{self.database}"
        )

    def _build_oracle_url(self) -> str:
        """构建 Oracle URL"""
        # 使用本地变量，不修改实例属性（避免多线程竞态）
        port = self.port
        if port == 3306:
            port = 1521

        service_name = self.kwargs.get("service_name", self.database)
        encoded_password = quote_plus(self.password) if self.password else ""

        # 根据 dialect 选择驱动
        if "oracledb" in self.dialect:
            driver = "oracledb"
            # 尝试初始化 thick 模式（支持旧版本 Oracle）
            try:
                import oracledb
                oracledb.init_oracle_client()
                logger.info("Oracle thick 模式已启用")
            except Exception as e:
                logger.warning(f"无法启用 Oracle thick 模式: {e}，将使用 thin 模式")
        else:
            driver = "cx_oracle"

        if service_name:
            return (
                f"oracle+{driver}://{self.username}:{encoded_password}"
                f"@{self.host}:{port}/{service_name}"
            )
        else:
            return (
                f"oracle+{driver}://{self.username}:{encoded_password}"
                f"@{self.host}:{port}"
            )

    def _build_clickhouse_url(self) -> str:
        """构建 ClickHouse URL"""
        encoded_password = quote_plus(self.password) if self.password else ""
        return (
            f"clickhouse+native://{self.username}:{encoded_password}"
            f"@{self.host}:{self.port}/{self.database}"
        )

    @contextmanager
    def connect(self):
        """
        上下文管理器，自动管理连接
        
        Yields:
            SQLAlchemy Connection 对象
            
        Example:
            >>> with conn.connect() as session:
            ...     result = session.execute(text("SELECT 1"))
        """
        if self._engine is None:
            raise RuntimeError("数据库引擎未初始化")
        
        conn = self._engine.connect()
        try:
            yield conn
        finally:
            conn.close()

    def execute(self, sql: str, params: Optional[Union[tuple, dict]] = None) -> QueryResult:
        """
        执行 SQL 查询
        
        Args:
            sql: SQL 语句(使用 %s 或 :name 作为占位符)
            params: 查询参数(用于防注入)
            
        Returns:
            QueryResult 对象
            
        Raises:
            SQLAlchemyError: SQL 执行错误
            
        Example:
            >>> result = conn.execute("SELECT * FROM users WHERE id > %s", (1,))
            >>> print(result.df)
        """
        if self._engine is None:
            raise RuntimeError("数据库引擎未初始化")
        
        start_time = time.time()
        
        try:
            with self._engine.connect() as conn, conn.begin():
                # 参数化查询
                if params:
                    # SQLAlchemy 2.0+ 对参数格式有严格要求
                    # 需要将 %s 转换为 :param1, :param2 格式
                    if isinstance(params, (list, tuple)):
                        # 转换位置参数为命名参数
                        new_sql, new_params = self._convert_positional_to_named(sql, params)
                        result = conn.execute(text(new_sql), new_params)
                    elif isinstance(params, dict):
                        # 使用命名参数 :name 格式
                        result = conn.execute(text(sql), params)
                    else:
                        result = conn.execute(text(sql), params)
                else:
                    result = conn.execute(text(sql))
                
                # 获取结果
                if result.returns_rows:
                    rows = result.fetchall()
                    columns = list(result.keys())
                    rowcount = len(rows)
                    rows_data = [tuple(row) for row in rows]
                else:
                    rows_data = []
                    columns = []
                    rowcount = 0
                
                # conn.begin() 上下文管理器自动处理 commit/rollback
                # 查询语句的事务会自动回滚（无数据变更），非查询语句成功则自动提交
                # 避免手动 conn.commit() 在 Ctrl+C 中断时导致事务残留
                
                execution_time_ms = (time.time() - start_time) * 1000
                
                return QueryResult(
                    columns=columns,
                    rows=rows_data,
                    row_count=rowcount,
                    execution_time_ms=execution_time_ms,
                    affected_rows=result.rowcount if hasattr(result, 'rowcount') else 0
                )
                
        except SQLAlchemyError as e:
            # 使用warning而非error，因为调用方会根据业务场景自行处理
            # 例如锁分析查询系统视图时权限不足是预期内的
            # 只记录错误类型和简短信息，不记录完整SQL（由调用方处理）
            err_msg = str(e).split('\n')[0][:120]
            logger.warning(f"SQL 执行失败 [{type(e).__name__}]: {err_msg}")
            raise
        except Exception as e:
            logger.error(f"执行异常 [{type(e).__name__}]: {e}")
            raise

    def execute_many(self, sql: str, params_list: List[Union[tuple, dict]]) -> int:
        """
        批量执行 SQL
        
        Args:
            sql: SQL 语句
            params_list: 参数列表
            
        Returns:
            受影响的行数
        """
        if self._engine is None:
            raise RuntimeError("数据库引擎未初始化")
        
        try:
            with self._engine.connect() as conn:
                with conn.begin():
                    result = conn.execute(text(sql), params_list)
                    return result.rowcount if hasattr(result, 'rowcount') else 0
        except SQLAlchemyError as e:
            logger.error(f"批量执行失败: {e}\nSQL: {sql[:200]}")
            raise

    def health_check(self) -> Dict[str, Any]:
        """
        连接健康检查
        
        Returns:
            健康状态字典
        """
        if self._engine is None:
            return {"healthy": False, "error": "引擎未初始化"}
        
        try:
            start = time.time()
            with self._engine.connect() as conn:
                # 根据数据库类型使用不同的健康检查SQL
                if 'oracle' in self.dialect:
                    health_sql = "SELECT 1 FROM DUAL"
                else:
                    health_sql = "SELECT 1"
                conn.execute(text(health_sql))
            latency_ms = (time.time() - start) * 1000
            
            return {
                "healthy": True,
                "latency_ms": round(latency_ms, 2),
                "dialect": self.dialect,
                "pool_size": self.POOL_SIZE
            }
        except Exception as e:
            return {
                "healthy": False,
                "error": str(e),
                "dialect": self.dialect
            }

    def _validate_table_name(self, table: str) -> str:
        """
        验证表名安全性
        
        Args:
            table: 表名
            
        Returns:
            安全的表名
            
        Raises:
            ValueError: 表名不合法
        """
        if not table:
            raise ValueError("表名不能为空")
        
        # 只允许字母、数字、下划线
        if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', table):
            raise ValueError(f"非法表名: {table}")
        
        return table

    def get_tables(self) -> List[str]:
        """
        获取所有表名
        
        Returns:
            表名列表
        """
        queries = {
            "sqlite": "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'",
            "sqlite3": "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'",
            "mysql": "SHOW TABLES",
            "mysql+pymysql": "SHOW TABLES",
            "postgresql": "SELECT tablename FROM pg_tables WHERE schemaname = 'public'",
            "oracle": "SELECT table_name FROM user_tables ORDER BY table_name",
            "oracle+cx_oracle": "SELECT table_name FROM user_tables ORDER BY table_name",
            "oracle+oracledb": "SELECT table_name FROM user_tables ORDER BY table_name",
            "sqlserver": "SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_TYPE = 'BASE TABLE'",
            "clickhouse": "SELECT name FROM system.tables WHERE database = currentDatabase()",
        }
        
        sql = queries.get(self.dialect, 
            "SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_TYPE = 'BASE TABLE'")
        
        result = self.execute(sql)
        return [row[0] for row in result.rows]

    def get_schema(self, table: str) -> pd.DataFrame:
        """
        获取表结构信息
        
        Args:
            table: 表名
            
        Returns:
            表结构 DataFrame
        """
        safe_table = self._validate_table_name(table)
        
        schema_queries = {
            "sqlite": (f"PRAGMA table_info({safe_table})", 
                      ["cid", "name", "type", "notnull", "dflt_value", "pk"]),
            "sqlite3": (f"PRAGMA table_info({safe_table})", 
                       ["cid", "name", "type", "notnull", "dflt_value", "pk"]),
            "mysql": (f"DESCRIBE `{safe_table}`", 
                     ["Field", "Type", "Null", "Key", "Default", "Extra"]),
            "mysql+pymysql": (f"DESCRIBE `{safe_table}`", 
                             ["Field", "Type", "Null", "Key", "Default", "Extra"]),
        }
        
        if self.dialect in schema_queries:
            sql, columns = schema_queries[self.dialect]
            result = self.execute(sql)
            df = result.df
            df.columns = columns
            return df
        
        # 其他数据库使用参数化查询
        if self.dialect in ("postgresql", "sqlserver"):
            sql = """
                SELECT column_name, data_type, is_nullable, column_default
                FROM information_schema.columns
                WHERE table_name = :table_name
                ORDER BY ordinal_position
            """
            result = self.execute(sql, {"table_name": safe_table})
            df = result.df
            df.columns = ["name", "type", "nullable", "default"]
            return df
        
        if self.dialect in ("oracle", "oracle+cx_oracle", "oracle+oracledb"):
            sql = """
                SELECT column_name, data_type, nullable, data_default
                FROM user_tab_columns
                WHERE table_name = UPPER(:table_name)
                ORDER BY column_id
            """
            result = self.execute(sql, {"table_name": safe_table.upper()})
            df = result.df
            df.columns = ["name", "type", "nullable", "default"]
            return df
        
        # 默认: 查询空结果获取列名
        result = self.execute(f"SELECT * FROM {safe_table} WHERE 1=0")
        return pd.DataFrame(columns=result.columns)

    def table_preview(self, table: str, limit: int = 10) -> pd.DataFrame:
        """
        预览表数据
        
        Args:
            table: 表名
            limit: 返回行数
            
        Returns:
            数据 DataFrame
        """
        safe_table = self._validate_table_name(table)
        limit = int(limit)  # 防止注入
        
        # 使用方言管理器生成限制SQL
        dialect_mgr = SQLDialectManager(self.dialect)
        sql = dialect_mgr.get_limit_sql(f"SELECT * FROM {safe_table}", limit)
        result = self.execute(sql)
        return result.df

    def close(self) -> None:
        """关闭连接池"""
        if self._engine:
            self._engine.dispose()
            self._engine = None
            logger.info("数据库连接池已关闭")

    def __enter__(self):
        """上下文管理器入口"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        self.close()
        return False

    def __repr__(self) -> str:
        return f"<DatabaseConnector dialect={self.dialect} host={self.host}>"
