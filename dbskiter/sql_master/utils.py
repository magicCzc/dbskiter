"""
sql_master/utils.py
工具类定义

文件功能：提供SQL处理相关的通用工具类
主要类/函数：
    - SQLTypeDetector: SQL类型检测器
    - SQLFormatter: SQL格式化器
    - QueryBuilder: 查询构建器
    - ResultProcessor: 结果处理器
    - PerformanceTimer: 性能计时器

版本: 3.0.0
作者: AI Assistant
创建时间: 2026-04-23
"""

import re
import time
from typing import Any, Dict, List, Optional, Tuple

from dbskiter.sql_master.models import SQLType


class SQLTypeDetector:
    """
    SQL类型检测器

    功能:
        - 检测SQL语句类型
        - 提取SQL关键信息
    """

    # SQL类型正则模式
    PATTERNS = {
        SQLType.SELECT: re.compile(r'^\s*SELECT\s+', re.IGNORECASE),
        SQLType.INSERT: re.compile(r'^\s*INSERT\s+INTO\s+', re.IGNORECASE),
        SQLType.UPDATE: re.compile(r'^\s*UPDATE\s+', re.IGNORECASE),
        SQLType.DELETE: re.compile(r'^\s*DELETE\s+FROM\s+', re.IGNORECASE),
        SQLType.CREATE: re.compile(r'^\s*CREATE\s+(TABLE|INDEX|VIEW)\s+', re.IGNORECASE),
        SQLType.ALTER: re.compile(r'^\s*ALTER\s+(TABLE|INDEX)\s+', re.IGNORECASE),
        SQLType.DROP: re.compile(r'^\s*DROP\s+(TABLE|INDEX|VIEW)\s+', re.IGNORECASE),
    }

    @staticmethod
    def detect(sql: str) -> SQLType:
        """
        检测SQL类型

        参数:
            sql: SQL语句

        返回:
            SQLType: SQL类型
        """
        if not sql or not isinstance(sql, str):
            return SQLType.UNKNOWN

        for sql_type, pattern in SQLTypeDetector.PATTERNS.items():
            if pattern.match(sql):
                return sql_type

        return SQLType.UNKNOWN

    @staticmethod
    def is_read_only(sql: str) -> bool:
        """
        判断是否为只读SQL

        参数:
            sql: SQL语句

        返回:
            bool: 是否为只读
        """
        sql_type = SQLTypeDetector.detect(sql)
        return sql_type == SQLType.SELECT

    @staticmethod
    def is_ddl(sql: str) -> bool:
        """
        判断是否为DDL语句

        参数:
            sql: SQL语句

        返回:
            bool: 是否为DDL
        """
        sql_type = SQLTypeDetector.detect(sql)
        return sql_type in [SQLType.CREATE, SQLType.ALTER, SQLType.DROP]


class SQLFormatter:
    """
    SQL格式化器

    功能:
        - 格式化SQL语句
        - 提取表名
        - 标准化SQL
    """

    @staticmethod
    def format(sql: str, uppercase_keywords: bool = True) -> str:
        """
        格式化SQL

        参数:
            sql: 原始SQL
            uppercase_keywords: 是否大写关键字

        返回:
            str: 格式化后的SQL
        """
        if not sql:
            return ""

        # 移除多余空白
        sql = re.sub(r'\s+', ' ', sql.strip())

        if uppercase_keywords:
            # 关键字大写
            keywords = [
                'SELECT', 'FROM', 'WHERE', 'AND', 'OR', 'NOT',
                'INSERT', 'INTO', 'VALUES', 'UPDATE', 'SET',
                'DELETE', 'CREATE', 'TABLE', 'INDEX', 'VIEW',
                'ALTER', 'DROP', 'JOIN', 'LEFT', 'RIGHT', 'INNER', 'OUTER',
                'ON', 'GROUP', 'BY', 'ORDER', 'HAVING', 'LIMIT',
                'UNION', 'ALL', 'DISTINCT', 'AS', 'ASC', 'DESC'
            ]
            for keyword in keywords:
                pattern = re.compile(r'\b' + keyword + r'\b', re.IGNORECASE)
                sql = pattern.sub(keyword, sql)

        return sql

    @staticmethod
    def extract_tables(sql: str) -> List[str]:
        """
        提取SQL中的表名

        参数:
            sql: SQL语句

        返回:
            List[str]: 表名列表
        """
        if not sql:
            return []

        tables = set()

        # FROM 子句
        from_pattern = re.compile(r'\bFROM\s+(\w+)', re.IGNORECASE)
        for match in from_pattern.finditer(sql):
            tables.add(match.group(1).lower())

        # JOIN 子句
        join_pattern = re.compile(r'\bJOIN\s+(\w+)', re.IGNORECASE)
        for match in join_pattern.finditer(sql):
            tables.add(match.group(1).lower())

        # INTO 子句
        into_pattern = re.compile(r'\bINTO\s+(\w+)', re.IGNORECASE)
        for match in into_pattern.finditer(sql):
            tables.add(match.group(1).lower())

        # UPDATE 子句
        update_pattern = re.compile(r'\bUPDATE\s+(\w+)', re.IGNORECASE)
        for match in update_pattern.finditer(sql):
            tables.add(match.group(1).lower())

        return sorted(list(tables))

    @staticmethod
    def normalize(sql: str) -> str:
        """
        标准化SQL（用于缓存键）

        参数:
            sql: SQL语句

        返回:
            str: 标准化后的SQL
        """
        if not sql:
            return ""

        # 转小写
        sql = sql.lower()
        # 移除多余空白
        sql = re.sub(r'\s+', ' ', sql.strip())
        # 移除注释
        sql = re.sub(r'--[^\n]*', '', sql)
        sql = re.sub(r'/\*.*?\*/', '', sql, flags=re.DOTALL)

        return sql.strip()


class QueryBuilder:
    """
    查询构建器

    功能:
        - 构建安全查询
        - 参数绑定
    """

    @staticmethod
    def build_select(
        table: str,
        columns: Optional[List[str]] = None,
        where: Optional[Dict[str, Any]] = None,
        limit: Optional[int] = None
    ) -> Tuple[str, List[Any]]:
        """
        构建SELECT查询

        参数:
            table: 表名
            columns: 列名列表
            where: WHERE条件
            limit: 限制行数

        返回:
            Tuple[str, List[Any]]: (SQL, 参数列表)
        """
        cols = ', '.join(columns) if columns else '*'
        sql = f"SELECT {cols} FROM {table}"
        params = []

        if where:
            conditions = []
            for key, value in where.items():
                conditions.append(f"{key} = ?")
                params.append(value)
            sql += " WHERE " + " AND ".join(conditions)

        if limit:
            sql += f" LIMIT {limit}"

        return sql, params

    @staticmethod
    def build_count(table: str, where: Optional[Dict[str, Any]] = None) -> Tuple[str, List[Any]]:
        """
        构建COUNT查询

        参数:
            table: 表名
            where: WHERE条件

        返回:
            Tuple[str, List[Any]]: (SQL, 参数列表)
        """
        sql = f"SELECT COUNT(*) FROM {table}"
        params = []

        if where:
            conditions = []
            for key, value in where.items():
                conditions.append(f"{key} = ?")
                params.append(value)
            sql += " WHERE " + " AND ".join(conditions)

        return sql, params


class ResultProcessor:
    """
    结果处理器

    功能:
        - 格式化查询结果
        - 数据转换
    """

    @staticmethod
    def to_dict_list(columns: List[str], rows: List[List[Any]]) -> List[Dict[str, Any]]:
        """
        转换为字典列表

        参数:
            columns: 列名列表
            rows: 数据行

        返回:
            List[Dict[str, Any]]: 字典列表
        """
        return [dict(zip(columns, row)) for row in rows]

    @staticmethod
    def paginate(
        rows: List[List[Any]],
        page: int = 1,
        page_size: int = 10
    ) -> Dict[str, Any]:
        """
        分页处理

        参数:
            rows: 数据行
            page: 页码（从1开始）
            page_size: 每页大小

        返回:
            Dict[str, Any]: 分页结果
        """
        total = len(rows)
        start = (page - 1) * page_size
        end = start + page_size
        paginated_rows = rows[start:end]

        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size,
            "data": paginated_rows
        }

    @staticmethod
    def summarize(rows: List[List[Any]], columns: List[str]) -> Dict[str, Any]:
        """
        汇总统计

        参数:
            rows: 数据行
            columns: 列名列表

        返回:
            Dict[str, Any]: 汇总信息
        """
        return {
            "row_count": len(rows),
            "column_count": len(columns),
            "columns": columns
        }


class PerformanceTimer:
    """
    性能计时器

    功能:
        - 测量执行时间
        - 性能统计
    """

    def __init__(self):
        self._start_time: Optional[float] = None
        self._elapsed: float = 0.0

    def start(self) -> 'PerformanceTimer':
        """开始计时"""
        self._start_time = time.time()
        return self

    def stop(self) -> float:
        """停止计时"""
        if self._start_time is None:
            return 0.0
        self._elapsed = time.time() - self._start_time
        self._start_time = None
        return self._elapsed

    @property
    def elapsed(self) -> float:
        """获取已用时间"""
        if self._start_time is not None:
            return time.time() - self._start_time
        return self._elapsed

    def __enter__(self) -> 'PerformanceTimer':
        """上下文管理器入口"""
        self.start()
        return self

    def __exit__(self, *args) -> None:
        """上下文管理器出口"""
        self.stop()


class SQLAnalyzer:
    """
    SQL分析器

    功能:
        - 分析SQL复杂度
        - 评估性能风险
    """

    @staticmethod
    def analyze_complexity(sql: str) -> Dict[str, Any]:
        """
        分析SQL复杂度

        参数:
            sql: SQL语句

        返回:
            Dict[str, Any]: 复杂度分析结果
        """
        if not sql:
            return {"level": "unknown", "score": 0}

        sql_upper = sql.upper()
        score = 0
        factors = []

        # JOIN复杂度
        join_count = sql_upper.count(' JOIN ')
        if join_count > 0:
            score += join_count * 10
            factors.append(f"{join_count}个JOIN")

        # 子查询
        subquery_count = sql_upper.count('SELECT') - 1
        if subquery_count > 0:
            score += subquery_count * 15
            factors.append(f"{subquery_count}个子查询")

        # WHERE条件复杂度
        where_count = sql_upper.count(' AND ') + sql_upper.count(' OR ')
        if where_count > 0:
            score += where_count * 5
            factors.append(f"{where_count}个WHERE条件")

        # GROUP BY
        if 'GROUP BY' in sql_upper:
            score += 10
            factors.append("包含GROUP BY")

        # ORDER BY
        if 'ORDER BY' in sql_upper:
            score += 5
            factors.append("包含ORDER BY")

        # 确定等级
        if score >= 50:
            level = "high"
        elif score >= 20:
            level = "medium"
        else:
            level = "low"

        return {
            "level": level,
            "score": score,
            "factors": factors
        }

    @staticmethod
    def estimate_cost(sql: str) -> Dict[str, Any]:
        """
        估算执行成本

        参数:
            sql: SQL语句

        返回:
            Dict[str, Any]: 成本估算
        """
        complexity = SQLAnalyzer.analyze_complexity(sql)

        # 基于复杂度估算成本
        cost_map = {
            "low": {"cpu": "low", "io": "low", "memory": "low"},
            "medium": {"cpu": "medium", "io": "medium", "memory": "medium"},
            "high": {"cpu": "high", "io": "high", "memory": "high"},
            "unknown": {"cpu": "unknown", "io": "unknown", "memory": "unknown"},
        }

        return {
            "complexity": complexity["level"],
            "estimated_cost": cost_map.get(complexity["level"], cost_map["unknown"]),
            "risk_level": complexity["level"]
        }
