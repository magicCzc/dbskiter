"""
shared/mock_connector.py

Mock 数据库连接器

文件功能：
    - 提供无需真实数据库的演示数据
    - 支持 SQL 查询、监控指标、诊断结果等
    - 方便新手离线体验 dbskiter 功能

使用示例：
    >>> from dbskiter.shared.mock_connector import MockConnector
    >>> conn = MockConnector()
    >>> result = conn.execute("SELECT * FROM users LIMIT 5")
    >>> print(result.rows)

版本: 1.0.0
作者: Magiczc
创建时间: 2026-06-12
"""

from __future__ import annotations

import random
import time
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple

from .query_result import QueryResult


class MockConnector:
    """
    Mock 数据库连接器

    功能描述：
        模拟数据库连接，提供预设的演示数据

    使用示例：
        >>> conn = MockConnector()
        >>> result = conn.execute("SELECT * FROM users LIMIT 5")
        >>> print(result.to_dict_list())
    """

    # 模拟数据表
    TABLES: Dict[str, Dict[str, Any]] = {
        "users": {
            "columns": ["id", "username", "email", "age", "created_at", "status"],
            "rows": [
                (1, "alice", "alice@example.com", 28, "2024-01-15 09:23:00", "active"),
                (2, "bob", "bob@example.com", 34, "2024-02-20 14:15:00", "active"),
                (3, "charlie", "charlie@example.com", 22, "2024-03-10 11:45:00", "inactive"),
                (4, "diana", "diana@example.com", 31, "2024-04-05 16:30:00", "active"),
                (5, "eve", "eve@example.com", 26, "2024-05-12 08:00:00", "active"),
                (6, "frank", "frank@example.com", 45, "2023-11-01 19:20:00", "active"),
                (7, "grace", "grace@example.com", 29, "2024-01-28 10:10:00", "inactive"),
                (8, "henry", "henry@example.com", 38, "2023-09-15 13:40:00", "active"),
            ],
        },
        "orders": {
            "columns": ["order_id", "user_id", "product_id", "amount", "status", "created_at"],
            "rows": [
                (1001, 1, 101, 299.99, "completed", "2024-06-01 10:00:00"),
                (1002, 2, 102, 599.50, "pending", "2024-06-01 11:30:00"),
                (1003, 1, 103, 89.99, "completed", "2024-06-02 09:15:00"),
                (1004, 3, 101, 299.99, "cancelled", "2024-06-02 14:20:00"),
                (1005, 4, 104, 1299.00, "completed", "2024-06-03 08:45:00"),
                (1006, 5, 102, 599.50, "shipped", "2024-06-03 16:00:00"),
                (1007, 6, 105, 49.99, "completed", "2024-06-04 11:10:00"),
                (1008, 7, 101, 299.99, "pending", "2024-06-04 13:25:00"),
            ],
        },
        "products": {
            "columns": ["product_id", "name", "category", "price", "stock"],
            "rows": [
                (101, "无线耳机", "电子产品", 299.99, 500),
                (102, "机械键盘", "电子产品", 599.50, 200),
                (103, "鼠标垫", "配件", 89.99, 1000),
                (104, "显示器", "电子产品", 1299.00, 80),
                (105, "数据线", "配件", 49.99, 2000),
            ],
        },
    }

    # 模拟监控指标
    METRICS: Dict[str, List[Dict[str, Any]]] = {
        "cpu_usage": [
            {"time": "10:00", "value": 45.2},
            {"time": "10:05", "value": 52.1},
            {"time": "10:10", "value": 38.7},
            {"time": "10:15", "value": 61.3},
            {"time": "10:20", "value": 55.8},
        ],
        "memory_usage": [
            {"time": "10:00", "value": 68.5},
            {"time": "10:05", "value": 71.2},
            {"time": "10:10", "value": 69.8},
            {"time": "10:15", "value": 74.1},
            {"time": "10:20", "value": 72.3},
        ],
        "active_sessions": [
            {"time": "10:00", "value": 12},
            {"time": "10:05", "value": 15},
            {"time": "10:10", "value": 11},
            {"time": "10:15", "value": 18},
            {"time": "10:20", "value": 14},
        ],
        "qps": [
            {"time": "10:00", "value": 2450},
            {"time": "10:05", "value": 3120},
            {"time": "10:10", "value": 2890},
            {"time": "10:15", "value": 3560},
            {"time": "10:20", "value": 2980},
        ],
    }

    # 模拟慢查询
    SLOW_QUERIES: List[Dict[str, Any]] = [
        {
            "sql": "SELECT * FROM orders o JOIN users u ON o.user_id = u.id WHERE o.amount > 100",
            "exec_time": 2.35,
            "exec_count": 152,
            "rows_examined": 125000,
        },
        {
            "sql": "SELECT COUNT(*) FROM users WHERE status = 'inactive'",
            "exec_time": 1.87,
            "exec_count": 89,
            "rows_examined": 85000,
        },
        {
            "sql": "SELECT * FROM products WHERE category = '电子产品' ORDER BY price DESC",
            "exec_time": 0.95,
            "exec_count": 210,
            "rows_examined": 5000,
        },
    ]

    def __init__(self):
        """初始化 Mock 连接器"""
        self.dialect = "mock"
        self.host = "demo"
        self.port = 0
        self._connected = True

    def execute(self, sql: str, params: Optional[Tuple] = None) -> QueryResult:
        """
        执行 SQL 查询（模拟）

        参数说明：
            - sql: SQL 语句
            - params: 查询参数（可选）

        返回说明：
            - QueryResult: 查询结果
        """
        start_time = time.time()
        sql_upper = sql.strip().upper()

        # 解析简单的 SELECT 查询
        if sql_upper.startswith("SELECT"):
            result = self._handle_select(sql)
        elif sql_upper.startswith("SHOW TABLES"):
            result = self._handle_show_tables()
        elif sql_upper.startswith("DESCRIBE") or sql_upper.startswith("DESC "):
            result = self._handle_describe(sql)
        elif sql_upper.startswith("EXPLAIN"):
            result = self._handle_explain(sql)
        else:
            # 其他查询返回空结果
            result = QueryResult(
                rows=[],
                columns=[],
                row_count=0,
                execution_time_ms=0.1,
            )

        result.execution_time_ms = (time.time() - start_time) * 1000
        return result

    def _handle_select(self, sql: str) -> QueryResult:
        """处理 SELECT 查询"""
        sql_upper = sql.upper()

        # 尝试匹配表名
        table_name = None
        for name in self.TABLES:
            if name.upper() in sql_upper:
                table_name = name
                break

        if not table_name:
            # 返回模拟的系统查询结果
            if "VERSION" in sql_upper or "@@" in sql_upper:
                return QueryResult(
                    rows=[("8.0.32", "MockDB 1.0", "UTF8MB4")],
                    columns=["version", "db_version", "charset"],
                    row_count=1,
                    execution_time_ms=0.5,
                )
            return QueryResult(
                rows=[],
                columns=[],
                row_count=0,
                execution_time_ms=0.1,
            )

        table = self.TABLES[table_name]
        rows = list(table["rows"])
        columns = list(table["columns"])

        # 处理 LIMIT
        if "LIMIT" in sql_upper:
            limit_str = sql_upper.split("LIMIT")[-1].strip().split()[0]
            try:
                limit = int(limit_str)
                rows = rows[:limit]
            except ValueError:
                pass

        # 处理 COUNT(*)
        if "COUNT(*)" in sql_upper:
            return QueryResult(
                rows=[(len(table["rows"]),)],
                columns=["count(*)"],
                row_count=1,
                execution_time_ms=0.3,
            )

        return QueryResult(
            rows=rows,
            columns=columns,
            row_count=len(rows),
            execution_time_ms=0.5,
        )

    def _handle_show_tables(self) -> QueryResult:
        """处理 SHOW TABLES"""
        rows = [(name,) for name in self.TABLES.keys()]
        return QueryResult(
            rows=rows,
            columns=["Tables_in_demo"],
            row_count=len(rows),
            execution_time_ms=0.2,
        )

    def _handle_describe(self, sql: str) -> QueryResult:
        """处理 DESCRIBE 查询"""
        parts = sql.strip().split()
        if len(parts) >= 2:
            table_name = parts[1].lower().strip(";`'")
            if table_name in self.TABLES:
                columns = self.TABLES[table_name]["columns"]
                rows = []
                for col in columns:
                    col_type = "VARCHAR(255)" if col in ("username", "email", "name", "category", "status") else (
                        "INT" if col in ("id", "user_id", "product_id", "age", "stock", "order_id") else (
                        "DECIMAL(10,2)" if col == "amount" else (
                        "DATETIME" if "at" in col else "VARCHAR(100)"
                        )
                    ))
                    rows.append((col, col_type, "YES", "", None, ""))
                return QueryResult(
                    rows=rows,
                    columns=["Field", "Type", "Null", "Key", "Default", "Extra"],
                    row_count=len(rows),
                    execution_time_ms=0.2,
                )
        return QueryResult(rows=[], columns=[], row_count=0, execution_time_ms=0.1)

    def _handle_explain(self, sql: str) -> QueryResult:
        """处理 EXPLAIN 查询"""
        return QueryResult(
            rows=[
                (1, "SIMPLE", "users", None, "ALL", None, None, None, 8, 100.0, "Using where"),
            ],
            columns=["id", "select_type", "table", "partitions", "type", "possible_keys", "key", "key_len", "rows", "filtered", "Extra"],
            row_count=1,
            execution_time_ms=0.3,
        )

    def get_schema(self, table_name: str) -> Any:
        """获取表结构"""
        if table_name.lower() in self.TABLES:
            return {
                "columns": self.TABLES[table_name.lower()]["columns"],
                "row_count": len(self.TABLES[table_name.lower()]["rows"]),
            }
        return None

    def get_tables(self) -> List[str]:
        """获取所有表名"""
        return list(self.TABLES.keys())

    def table_preview(self, table: str, limit: int = 10) -> QueryResult:
        """预览表数据"""
        if table.lower() in self.TABLES:
            t = self.TABLES[table.lower()]
            rows = t["rows"][:limit]
            return QueryResult(
                rows=rows,
                columns=t["columns"],
                row_count=len(rows),
                execution_time_ms=0.2,
            )
        return QueryResult(rows=[], columns=[], row_count=0, execution_time_ms=0.1)

    def close(self) -> None:
        """关闭连接（无操作）"""
        self._connected = False

    def is_connected(self) -> bool:
        """检查连接状态"""
        return self._connected

    def get_metrics(self, metric_type: str) -> List[Dict[str, Any]]:
        """
        获取监控指标

        参数说明：
            - metric_type: 指标类型

        返回说明：
            - List[Dict]: 指标数据列表
        """
        return self.METRICS.get(metric_type, [])

    def get_slow_queries(self) -> List[Dict[str, Any]]:
        """获取慢查询列表"""
        return self.SLOW_QUERIES

    def get_health_status(self) -> Dict[str, Any]:
        """获取健康状态"""
        return {
            "score": 87.5,
            "status": "healthy",
            "checks": [
                {"name": "CPU 使用率", "status": "pass", "value": "45.2%"},
                {"name": "内存使用率", "status": "pass", "value": "68.5%"},
                {"name": "磁盘空间", "status": "warning", "value": "82.1%"},
                {"name": "活跃连接数", "status": "pass", "value": "14"},
                {"name": "慢查询数量", "status": "warning", "value": "3"},
            ],
        }
