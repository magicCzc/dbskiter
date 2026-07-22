"""
URL 连接字符串解析器

解析 SQLAlchemy 风格的连接字符串：
    dialect+driver://user:password@host:port/database?param=value

示例:
    mysql+pymysql://root:pass@localhost:3306/test
    postgresql://user@host:5432/db?sslmode=require
    sqlite:///path/to/db.sqlite3
"""

import re
from typing import Dict, Optional, Tuple
from urllib.parse import unquote, urlparse


def parse_url(url: str) -> Dict[str, any]:
    """
    解析数据库连接字符串

    参数:
        url: 连接字符串

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
        parsed = urlparse(url)

        # 解析 dialect
        dialect = parsed.scheme or ""

        # 解析认证信息
        username = unquote(parsed.username) if parsed.username else None
        password = unquote(parsed.password) if parsed.password else None

        # 解析主机和端口
        hostname = parsed.hostname or ""
        port = parsed.port

        # 解析数据库名
        database = parsed.path.lstrip("/") if parsed.path else None
        if database and "/" in database:
            database = database.split("/")[0]

        # 解析查询参数
        query_params = {}
        if parsed.query:
            for part in parsed.query.split("&"):
                if "=" in part:
                    k, v = part.split("=", 1)
                    query_params[k] = unquote(v)

        result = {"dialect": dialect}
        if username:
            result["user"] = username
        if password:
            result["password"] = password
        if hostname:
            result["host"] = hostname
        if port:
            result["port"] = port
        if database:
            result["database"] = database
        if query_params:
            result["query"] = query_params

        return result

    except Exception as e:
        return {"error": f"解析连接字符串失败: {e}"}


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