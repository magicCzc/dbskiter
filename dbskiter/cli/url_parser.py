"""
URL 连接字符串解析器

解析 SQLAlchemy 风格的连接字符串：
    dialect+driver://user:password@host:port/database?param=value

使用 SQLAlchemy 的 make_url() 替代手写 urlparse 解析器，
避免边界 case 处理遗漏（如无端口、特殊编码、SQLite 路径等）。

示例:
    mysql+pymysql://root:pass@localhost:3306/test
    postgresql://user@host:5432/db?sslmode=require
    sqlite:///path/to/db.sqlite3
"""

from typing import Any, Dict

from sqlalchemy.engine.url import make_url as _sa_make_url
from sqlalchemy.exc import ArgumentError


def parse_url(url: str) -> Dict[str, Any]:
    """
    解析数据库连接字符串（委托给 SQLAlchemy make_url）

    参数:
        url: 连接字符串，如 mysql+pymysql://root:pass@localhost:3306/test

    返回:
        Dict: 包含 dialect, host, port, user, password, database, query 的字典

    示例:
        >>> parse_url("mysql+pymysql://root:pass@localhost:3306/test")
        {'dialect': 'mysql+pymysql', 'user': 'root', 'password': 'pass',
         'host': 'localhost', 'port': 3306, 'database': 'test'}
    """
    if not url or "://" not in url:
        return {"error": f"无效的连接字符串: {url}"}

    try:
        parsed = _sa_make_url(url)

        result: Dict[str, Any] = {"dialect": parsed.drivername}
        if parsed.username:
            result["user"] = parsed.username
        if parsed.password:
            result["password"] = parsed.password
        if parsed.host:
            result["host"] = parsed.host
        if parsed.port is not None:
            result["port"] = parsed.port
        if parsed.database:
            result["database"] = parsed.database
        if parsed.query:
            result["query"] = dict(parsed.query)

        return result

    except ArgumentError as e:
        return {"error": f"解析连接字符串失败: {e}"}
    except Exception as e:
        return {"error": f"解析连接字符串时发生意外错误: {e}"}


def normalize_dialect(url_or_dialect: str) -> str:
    """
    规范化 dialect 名称

    将常见的缩写映射到完整的 SQLAlchemy dialect 名称。

    示例:
        >>> normalize_dialect("mysql")
        'mysql+pymysql'
        >>> normalize_dialect("postgres")
        'postgresql'
        >>> normalize_dialect("mysql+pymysql")
        'mysql+pymysql'
    """
    dialect_map = {
        "mysql": "mysql+pymysql",
        "postgres": "postgresql",
        "postgresql": "postgresql",
        "pg": "postgresql",
        "oracle": "oracle+oracledb",
        "mssql": "mssql+pyodbc",
        "sqlserver": "mssql+pyodbc",
        "sqlite": "sqlite",
        "clickhouse": "clickhouse",
        "trino": "trino",
        "presto": "presto",
        "duckdb": "duckdb",
    }
    return dialect_map.get(url_or_dialect.lower(), url_or_dialect)