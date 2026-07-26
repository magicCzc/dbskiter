"""
sql_master/test_utils.py
工具类单元测试

测试范围:
    - SQLTypeDetector SQL类型检测器
    - SQLFormatter SQL格式化器
    - QueryBuilder 查询构建器
    - ResultProcessor 结果处理器
    - PerformanceTimer 性能计时器
    - SQLAnalyzer SQL分析器

版本: 1.0.0
作者: AI Assistant
创建时间: 2026-04-23
"""

import time
import unittest

from dbskiter.sql_master.models import SQLType
from dbskiter.sql_master.utils import (
    SQLTypeDetector,
    SQLFormatter,
    QueryBuilder,
    ResultProcessor,
    PerformanceTimer,
    SQLAnalyzer,
)


class TestSQLTypeDetector(unittest.TestCase):
    """测试SQL类型检测器"""

    def test_detect_select(self):
        """测试检测SELECT"""
        sql_type = SQLTypeDetector.detect("SELECT * FROM users")
        self.assertEqual(sql_type, SQLType.SELECT)

    def test_detect_insert(self):
        """测试检测INSERT"""
        sql_type = SQLTypeDetector.detect("INSERT INTO users VALUES (1)")
        self.assertEqual(sql_type, SQLType.INSERT)

    def test_detect_update(self):
        """测试检测UPDATE"""
        sql_type = SQLTypeDetector.detect("UPDATE users SET name='test'")
        self.assertEqual(sql_type, SQLType.UPDATE)

    def test_detect_delete(self):
        """测试检测DELETE"""
        sql_type = SQLTypeDetector.detect("DELETE FROM users WHERE id=1")
        self.assertEqual(sql_type, SQLType.DELETE)

    def test_detect_unknown(self):
        """测试检测未知类型"""
        sql_type = SQLTypeDetector.detect("INVALID SQL")
        self.assertEqual(sql_type, SQLType.UNKNOWN)

    def test_detect_empty(self):
        """测试检测空字符串"""
        sql_type = SQLTypeDetector.detect("")
        self.assertEqual(sql_type, SQLType.UNKNOWN)

    def test_is_read_only_true(self):
        """测试只读判断为真"""
        self.assertTrue(SQLTypeDetector.is_read_only("SELECT * FROM users"))

    def test_is_read_only_false(self):
        """测试只读判断为假"""
        self.assertFalse(SQLTypeDetector.is_read_only("INSERT INTO users VALUES (1)"))

    def test_is_ddl_true(self):
        """测试DDL判断为真"""
        self.assertTrue(SQLTypeDetector.is_ddl("CREATE TABLE test (id INT)"))

    def test_is_ddl_false(self):
        """测试DDL判断为假"""
        self.assertFalse(SQLTypeDetector.is_ddl("SELECT * FROM users"))


class TestSQLFormatter(unittest.TestCase):
    """测试SQL格式化器"""

    def test_format_basic(self):
        """测试基本格式化"""
        formatted = SQLFormatter.format("  SELECT   *  FROM   users  ")
        self.assertIn("SELECT", formatted)
        self.assertIn("FROM", formatted)

    def test_format_uppercase(self):
        """测试关键字大写"""
        formatted = SQLFormatter.format("select * from users", uppercase_keywords=True)
        self.assertIn("SELECT", formatted)
        self.assertIn("FROM", formatted)

    def test_extract_tables_from(self):
        """测试从FROM提取表名"""
        tables = SQLFormatter.extract_tables("SELECT * FROM users")
        self.assertIn("users", tables)

    def test_extract_tables_join(self):
        """测试从JOIN提取表名"""
        tables = SQLFormatter.extract_tables("SELECT * FROM users JOIN orders ON users.id = orders.user_id")
        self.assertIn("users", tables)
        self.assertIn("orders", tables)

    def test_extract_tables_empty(self):
        """测试提取空SQL"""
        tables = SQLFormatter.extract_tables("")
        self.assertEqual(tables, [])

    def test_normalize(self):
        """测试标准化SQL"""
        normalized = SQLFormatter.normalize("  SELECT  *  FROM  users  ")
        self.assertEqual(normalized, "select * from users")

    def test_normalize_with_comments(self):
        """测试移除注释"""
        normalized = SQLFormatter.normalize("SELECT * FROM users -- comment")
        self.assertNotIn("--", normalized)


class TestQueryBuilder(unittest.TestCase):
    """测试查询构建器"""

    def test_build_select_basic(self):
        """测试构建基本SELECT"""
        sql, params = QueryBuilder.build_select("users")
        self.assertIn("SELECT", sql)
        self.assertIn("FROM users", sql)
        self.assertEqual(params, [])

    def test_build_select_with_columns(self):
        """测试构建带列名的SELECT"""
        sql, params = QueryBuilder.build_select("users", columns=["id", "name"])
        self.assertIn("id, name", sql)

    def test_build_select_with_where(self):
        """测试构建带WHERE的SELECT"""
        sql, params = QueryBuilder.build_select(
            "users",
            where={"id": 1, "name": "test"}
        )
        self.assertIn("WHERE", sql)
        self.assertEqual(len(params), 2)

    def test_build_select_with_limit(self):
        """测试构建带LIMIT的SELECT"""
        sql, params = QueryBuilder.build_select("users", limit=10)
        self.assertIn("LIMIT 10", sql)

    def test_build_count(self):
        """测试构建COUNT查询"""
        sql, params = QueryBuilder.build_count("users")
        self.assertIn("COUNT(*)", sql)
        self.assertIn("FROM users", sql)


class TestResultProcessor(unittest.TestCase):
    """测试结果处理器"""

    def test_to_dict_list(self):
        """测试转换为字典列表"""
        columns = ["id", "name"]
        rows = [[1, "Alice"], [2, "Bob"]]
        result = ResultProcessor.to_dict_list(columns, rows)

        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["id"], 1)
        self.assertEqual(result[0]["name"], "Alice")

    def test_paginate(self):
        """测试分页"""
        rows = [[i] for i in range(20)]
        result = ResultProcessor.paginate(rows, page=1, page_size=10)

        self.assertEqual(result["total"], 20)
        self.assertEqual(result["page"], 1)
        self.assertEqual(result["page_size"], 10)
        self.assertEqual(len(result["data"]), 10)

    def test_paginate_second_page(self):
        """测试第二页"""
        rows = [[i] for i in range(20)]
        result = ResultProcessor.paginate(rows, page=2, page_size=10)

        self.assertEqual(result["page"], 2)
        self.assertEqual(len(result["data"]), 10)

    def test_summarize(self):
        """测试汇总"""
        rows = [[1], [2], [3]]
        columns = ["id"]
        result = ResultProcessor.summarize(rows, columns)

        self.assertEqual(result["row_count"], 3)
        self.assertEqual(result["column_count"], 1)


class TestPerformanceTimer(unittest.TestCase):
    """测试性能计时器"""

    def test_timer_start_stop(self):
        """测试开始和停止"""
        timer = PerformanceTimer()
        timer.start()
        time.sleep(0.01)
        elapsed = timer.stop()

        self.assertGreater(elapsed, 0)

    def test_timer_context_manager(self):
        """测试上下文管理器"""
        with PerformanceTimer() as timer:
            time.sleep(0.01)

        self.assertGreater(timer.elapsed, 0)

    def test_timer_elapsed_while_running(self):
        """测试运行中获取时间"""
        timer = PerformanceTimer()
        timer.start()
        time.sleep(0.01)
        elapsed = timer.elapsed

        self.assertGreater(elapsed, 0)
        timer.stop()


class TestSQLAnalyzer(unittest.TestCase):
    """测试SQL分析器"""

    def test_analyze_complexity_simple(self):
        """测试简单SQL复杂度"""
        result = SQLAnalyzer.analyze_complexity("SELECT * FROM users")

        self.assertEqual(result["level"], "low")
        self.assertEqual(result["score"], 0)

    def test_analyze_complexity_with_join(self):
        """测试带JOIN的复杂度"""
        result = SQLAnalyzer.analyze_complexity(
            "SELECT * FROM users JOIN orders ON users.id = orders.user_id"
        )

        self.assertGreater(result["score"], 0)
        self.assertIn("JOIN", str(result["factors"]))

    def test_analyze_complexity_with_group_by(self):
        """测试带GROUP BY的复杂度"""
        result = SQLAnalyzer.analyze_complexity(
            "SELECT department, COUNT(*) FROM employees GROUP BY department"
        )

        self.assertGreater(result["score"], 0)

    def test_estimate_cost_low(self):
        """测试低成本估算"""
        result = SQLAnalyzer.estimate_cost("SELECT * FROM users")

        self.assertEqual(result["complexity"], "low")
        self.assertEqual(result["estimated_cost"]["cpu"], "low")

    def test_estimate_cost_high(self):
        """测试高成本估算"""
        # 复杂查询
        sql = """
            SELECT * FROM users
            JOIN orders ON users.id = orders.user_id
            JOIN products ON orders.product_id = products.id
            WHERE users.status = 'active'
            GROUP BY users.id
            ORDER BY users.created_at DESC
        """
        result = SQLAnalyzer.estimate_cost(sql)

        self.assertIn(result["complexity"], ["medium", "high"])


if __name__ == "__main__":
    unittest.main()
