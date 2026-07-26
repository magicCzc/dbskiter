"""
表诊断分析器单元测试

文件功能：测试TableAnalyzer的所有功能
主要测试类：
- TestTableAnalyzer: 表分析器测试
- TestTableAnalyzerMySQL: MySQL表分析测试
- TestTableAnalyzerPostgreSQL: PostgreSQL表分析测试

作者：AI Assistant
创建时间：2026-04-22
"""

import unittest
import sys
from unittest.mock import Mock, MagicMock, patch
from typing import Dict, Any

sys.path.insert(0, r'e:\Chenzc-AIDev\数据库skill')

from dbskiter.db_diagnose.analyzers.table_analyzer import TableAnalyzer


# =============================================================================
# Mock连接器
# =============================================================================

class MockConnector:
    """模拟数据库连接器"""

    def __init__(self, dialect="mysql"):
        self.dialect = dialect

    def execute(self, sql: str, params=None):
        """模拟执行SQL"""
        normalized_sql = sql.strip().lower()

        if "information_schema.tables" in normalized_sql:
            return MockResult([[10.5, 1000, 8.0, 2.5]])
        elif "information_schema.statistics" in normalized_sql:
            return MockResult([
                ["PRIMARY", "id", 1000, 0],
                ["idx_name", "name", 500, 1],
                ["idx_name_age", "name", 400, 1],
                ["idx_name_age", "age", 400, 1]
            ])
        elif "pg_total_relation_size" in normalized_sql:
            return MockResult([["10 MB", 10485760]])
        elif "pg_indexes" in normalized_sql:
            return MockResult([
                ["users_pkey", "CREATE UNIQUE INDEX users_pkey ON users USING btree (id)"],
                ["idx_name", "CREATE INDEX idx_name ON users USING btree (name)"]
            ])

        return MockResult([])


class MockResult:
    """模拟查询结果"""

    def __init__(self, rows):
        self.rows = rows
        self.columns = [f"col_{i}" for i in range(len(rows[0]) if rows else 0)]


# =============================================================================
# 表分析器基础测试
# =============================================================================

class TestTableAnalyzer(unittest.TestCase):
    """TableAnalyzer基础测试"""

    def setUp(self):
        """测试前置准备"""
        self.mysql_connector = MockConnector("mysql")
        self.pg_connector = MockConnector("postgresql")
        self.mysql_analyzer = TableAnalyzer(self.mysql_connector)
        self.pg_analyzer = TableAnalyzer(self.pg_connector)

    def test_init_basic(self):
        """测试基本初始化"""
        self.assertEqual(self.mysql_analyzer.connector, self.mysql_connector)
        self.assertEqual(self.pg_analyzer.connector, self.pg_connector)

    def test_is_valid_identifier_valid(self):
        """测试有效标识符验证"""
        valid_names = ["users", "user_profiles", "table123", "_private"]
        for name in valid_names:
            with self.subTest(name=name):
                self.assertTrue(
                    self.mysql_analyzer._is_valid_identifier(name),
                    f"{name} 应该是有效的标识符"
                )

    def test_is_valid_identifier_invalid(self):
        """测试无效标识符验证"""
        invalid_names = [
            "",  # 空字符串
            "users; DROP",  # SQL注入
            "123table",  # 数字开头
            "table-name",  # 连字符
            "table name",  # 空格
            "a" * 65,  # 过长
        ]
        for name in invalid_names:
            with self.subTest(name=name):
                self.assertFalse(
                    self.mysql_analyzer._is_valid_identifier(name),
                    f"{name} 应该是无效的标识符"
                )


# =============================================================================
# MySQL表分析测试
# =============================================================================

class TestTableAnalyzerMySQL(unittest.TestCase):
    """MySQL表分析测试"""

    def setUp(self):
        """测试前置准备"""
        self.connector = MockConnector("mysql")
        self.analyzer = TableAnalyzer(self.connector)

    def test_analyze_success(self):
        """测试MySQL表分析成功"""
        result = self.analyzer.analyze("users")

        self.assertTrue(result["success"])
        self.assertIn("data", result)
        self.assertEqual(result["data"]["table_name"], "users")
        self.assertEqual(result["data"]["dialect"], "mysql")

    def test_analyze_with_statistics(self):
        """测试包含统计信息的表分析"""
        result = self.analyzer.analyze("users", include_statistics=True)

        self.assertTrue(result["success"])
        self.assertIn("statistics", result["data"])
        stats = result["data"]["statistics"]
        self.assertEqual(stats["size_mb"], 10.5)
        self.assertEqual(stats["row_count"], 1000)

    def test_analyze_without_statistics(self):
        """测试不包含统计信息的表分析"""
        result = self.analyzer.analyze("users", include_statistics=False)

        self.assertTrue(result["success"])
        self.assertEqual(result["data"]["statistics"], {})

    def test_analyze_with_indexes(self):
        """测试包含索引信息的表分析"""
        result = self.analyzer.analyze("users", include_indexes=True)

        self.assertTrue(result["success"])
        self.assertIn("indexes", result["data"])
        indexes = result["data"]["indexes"]
        self.assertGreater(len(indexes), 0)

        # 验证索引结构
        primary_idx = next((i for i in indexes if i["name"] == "PRIMARY"), None)
        self.assertIsNotNone(primary_idx)
        self.assertTrue(primary_idx["is_unique"])

    def test_analyze_without_indexes(self):
        """测试不包含索引信息的表分析"""
        result = self.analyzer.analyze("users", include_indexes=False)

        self.assertTrue(result["success"])
        self.assertEqual(result["data"]["indexes"], [])

    def test_analyze_invalid_table_name(self):
        """测试无效表名处理"""
        result = self.analyzer.analyze("users; DROP TABLE users")

        self.assertFalse(result["success"])
        self.assertIn("error", result)

    def test_find_redundant_indexes(self):
        """测试冗余索引检测"""
        indexes = {
            "idx_name": {"columns": ["name"]},
            "idx_name_age": {"columns": ["name", "age"]},
            "idx_email": {"columns": ["email"]}
        }

        redundant = self.analyzer._find_redundant_indexes(indexes)

        self.assertEqual(len(redundant), 1)
        self.assertIn("idx_name_age", redundant[0])
        self.assertIn("idx_name", redundant[0])

    def test_find_redundant_indexes_none(self):
        """测试无冗余索引情况"""
        indexes = {
            "idx_name": {"columns": ["name"]},
            "idx_email": {"columns": ["email"]}
        }

        redundant = self.analyzer._find_redundant_indexes(indexes)

        self.assertEqual(len(redundant), 0)


# =============================================================================
# PostgreSQL表分析测试
# =============================================================================

class TestTableAnalyzerPostgreSQL(unittest.TestCase):
    """PostgreSQL表分析测试"""

    def setUp(self):
        """测试前置准备"""
        self.connector = MockConnector("postgresql")
        self.analyzer = TableAnalyzer(self.connector)

    def test_analyze_success(self):
        """测试PostgreSQL表分析成功"""
        result = self.analyzer.analyze("users")

        self.assertTrue(result["success"])
        self.assertIn("data", result)
        self.assertEqual(result["data"]["table_name"], "users")
        self.assertEqual(result["data"]["dialect"], "postgresql")

    def test_analyze_with_statistics(self):
        """测试包含统计信息的PostgreSQL表分析"""
        result = self.analyzer.analyze("users", include_statistics=True)

        self.assertTrue(result["success"])
        self.assertIn("statistics", result["data"])
        stats = result["data"]["statistics"]
        self.assertEqual(stats["size_pretty"], "10 MB")
        self.assertEqual(stats["size_bytes"], 10485760)

    def test_analyze_with_indexes(self):
        """测试包含索引信息的PostgreSQL表分析"""
        result = self.analyzer.analyze("users", include_indexes=True)

        self.assertTrue(result["success"])
        self.assertIn("indexes", result["data"])
        indexes = result["data"]["indexes"]
        self.assertEqual(len(indexes), 2)

        # 验证索引结构
        pkey_idx = next((i for i in indexes if i["name"] == "users_pkey"), None)
        self.assertIsNotNone(pkey_idx)
        self.assertIn("UNIQUE", pkey_idx["definition"])


# =============================================================================
# 主程序入口
# =============================================================================

if __name__ == "__main__":
    # 运行测试
    unittest.main(verbosity=2)
