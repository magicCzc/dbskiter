"""
文件功能：SQL 工具函数共享模块

将跨模块重复的 SQL 解析、类型检测、表名提取等工具函数统一到此模块，
避免 sql_master.utils、db_sql_auditor.utils、db_diagnose.utils 之间的重复实现。

主要类/函数：
    - extract_tables: 从 SQL 中提取表名
    - extract_columns: 从 SQL 中提取列名
    - SQLTypeDetector: SQL 类型检测器（统一版本）

作者：Magiczc
创建时间：2026-06-08
最后修改：2026-06-08
"""

import re
from typing import List, Dict, Pattern, Optional
from enum import Enum


class SQLType(str, Enum):
    """SQL 操作类型枚举"""
    SELECT = "SELECT"
    INSERT = "INSERT"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    CREATE = "CREATE"
    ALTER = "ALTER"
    DROP = "DROP"
    TRUNCATE = "TRUNCATE"
    UNKNOWN = "UNKNOWN"


# ==================== SQL 类型检测 ====================

class SQLTypeDetector:
    """
    SQL 类型检测器（统一版本）

    替换 sql_master.utils.SQLTypeDetector 和 db_sql_auditor.utils.SQLParser.detect_sql_type。

    使用示例：
        >>> SQLTypeDetector.detect("SELECT * FROM users")
        <SQLType.SELECT: 'SELECT'>
        >>> SQLTypeDetector.detect("INSERT INTO users VALUES (1)")
        <SQLType.INSERT: 'INSERT'>
    """

    # SQL 类型正则模式
    PATTERNS: Dict[SQLType, Pattern] = {
        SQLType.SELECT: re.compile(r'^\s*SELECT\s+', re.IGNORECASE),
        SQLType.INSERT: re.compile(r'^\s*INSERT\s+INTO\s+', re.IGNORECASE),
        SQLType.UPDATE: re.compile(r'^\s*UPDATE\s+', re.IGNORECASE),
        SQLType.DELETE: re.compile(r'^\s*DELETE\s+FROM\s+', re.IGNORECASE),
        SQLType.CREATE: re.compile(r'^\s*CREATE\s+(TABLE|INDEX|VIEW)', re.IGNORECASE),
        SQLType.ALTER: re.compile(r'^\s*ALTER\s+(TABLE|INDEX)\s+', re.IGNORECASE),
        SQLType.DROP: re.compile(r'^\s*DROP\s+(TABLE|INDEX|VIEW)', re.IGNORECASE),
        SQLType.TRUNCATE: re.compile(r'^\s*TRUNCATE\s+TABLE\s+', re.IGNORECASE),
    }

    @staticmethod
    def detect(sql: str) -> SQLType:
        """
        检测 SQL 类型

        参数说明：
            - sql: str - SQL 语句

        返回说明：
            - SQLType - SQL 类型枚举值

        使用示例：
            >>> SQLTypeDetector.detect("SELECT 1")
            SQLType.SELECT
            >>> SQLTypeDetector.detect("")
            SQLType.UNKNOWN

        异常情况：
            - 不会抛出异常，非法输入返回 UNKNOWN
        """
        if not sql or not isinstance(sql, str):
            return SQLType.UNKNOWN
        sql_stripped = sql.strip()
        if not sql_stripped:
            return SQLType.UNKNOWN
        for sql_type, pattern in SQLTypeDetector.PATTERNS.items():
            if pattern.match(sql_stripped):
                return sql_type
        return SQLType.UNKNOWN

    @staticmethod
    def is_read_only(sql: str) -> bool:
        """
        判断是否为只读 SQL

        参数说明：
            - sql: str - SQL 语句

        返回说明：
            - bool - True 表示只读（SELECT）, False 表示有写操作
        """
        return SQLTypeDetector.detect(sql) == SQLType.SELECT

    @staticmethod
    def is_ddl(sql: str) -> bool:
        """
        判断是否为 DDL 语句

        参数说明：
            - sql: str - SQL 语句

        返回说明：
            - bool - True 表示 DDL（CREATE/ALTER/DROP/TRUNCATE）
        """
        detected = SQLTypeDetector.detect(sql)
        return detected in (SQLType.CREATE, SQLType.ALTER, SQLType.DROP, SQLType.TRUNCATE)


# ==================== 表名提取 ====================

def extract_tables(sql: str) -> List[str]:
    """
    从 SQL 中提取表名

    替换 sql_master.utils.QueryBuilder.extract_tables、
    db_sql_auditor.utils.SQLParser.extract_tables、
    db_diagnose.utils.extract_tables 三处重复实现。

    参数说明：
        - sql: str - SQL 语句

    返回说明：
        - List[str] - 提取到的表名列表（去重、排序、小写）

    使用示例：
        >>> extract_tables("SELECT * FROM users JOIN orders ON users.id = orders.user_id")
        ['orders', 'users']
        >>> extract_tables("INSERT INTO logs VALUES (1)")
        ['logs']
        >>> extract_tables("")
        []

    异常情况：
        - 输入为空或非字符串，返回空列表
    """
    if not sql:
        return []

    tables: set = set()
    # 按长度降序匹配, 避免 FROM 匹配到 INTO 的情况
    # FROM 子句
    from_pattern = re.compile(r'\bFROM\s+(\w+)', re.IGNORECASE)
    for match in from_pattern.finditer(sql):
        tables.add(match.group(1).lower())
    # JOIN 子句
    join_pattern = re.compile(r'\bJOIN\s+(\w+)', re.IGNORECASE)
    for match in join_pattern.finditer(sql):
        tables.add(match.group(1).lower())
    # UPDATE 子句
    update_pattern = re.compile(r'\bUPDATE\s+(\w+)', re.IGNORECASE)
    for match in update_pattern.finditer(sql):
        tables.add(match.group(1).lower())
    # INTO 子句
    into_pattern = re.compile(r'\bINTO\s+(\w+)', re.IGNORECASE)
    for match in into_pattern.finditer(sql):
        tables.add(match.group(1).lower())
    return sorted(list(tables))


# ==================== 列名提取 ====================

def extract_columns(sql: str) -> List[str]:
    """
    从 SQL 中提取列名

    参数说明：
        - sql: str - SQL 语句

    返回说明：
        - List[str] - 提取到的列名列表

    使用示例：
        >>> extract_columns("SELECT id, name FROM users")
        ['id', 'name']
    """
    if not sql:
        return []
    columns: set = set()
    # SELECT 后的列名
    select_match = re.search(
        r'SELECT\s+(.*?)\s+FROM', sql, re.IGNORECASE | re.DOTALL
    )
    if select_match:
        col_part = select_match.group(1).strip()
        # 去除 DISTINCT、函数调用等
        col_part = re.sub(r'\bDISTINCT\b', '', col_part, flags=re.IGNORECASE)
        for col in col_part.split(','):
            col = col.strip()
            # 跳过函数调用和表达式
            if col and col != '*' and '(' not in col and ' ' not in col:
                columns.add(col.lower())
    return sorted(list(columns))


# ==================== Generic 驱动能力探测显示 ====================

def build_capabilities_display(caps: Dict[str, bool]) -> str:
    """
    构建 Generic 驱动能力探测结果的可读摘要

    供 generic_diagnostician、generic_collector、generic_inspector 统一使用。

    参数说明：
        - caps: 能力探测结果字典

    返回说明：
        - str: 格式化后的能力摘要

    使用示例：
        >>> build_capabilities_display({"information_schema": True, "version_query": False})
        '[Generic驱动] 能力探测: 版本查询(不支持), 可用视图: INFORMATION_SCHEMA'
    """
    version_checked = "版本查询" if caps.get("version_query") else "版本查询(不支持)"
    available_views = []
    view_names = [
        ("information_schema", "INFORMATION_SCHEMA"),
        ("pg_stat_activity", "pg_stat_activity"),
        ("pg_stat_statements", "pg_stat_statements"),
        ("pg_stat_database", "pg_stat_database"),
        ("performance_schema", "performance_schema"),
        ("v$session", "v$session"),
        ("sys.dm_exec_sessions", "sys.dm_exec_sessions"),
        ("pragma", "PRAGMA"),
    ]
    for key, display_name in view_names:
        if caps.get(key):
            available_views.append(display_name)
    view_info = ", ".join(available_views) if available_views else "无专用系统视图"
    return f"[Generic驱动] 能力探测: {version_checked}, 可用视图: {view_info}"
