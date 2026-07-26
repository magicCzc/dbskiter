"""
db_diagnose/test_utils.py
工具类单元测试

测试范围:
    - SQLFingerprint SQL指纹
    - IssueClassifier 问题分类器
    - ScoreCalculator 评分计算器
    - PrioritySorter 优先级排序器
    - MetricsAggregator 指标聚合器
    - QueryExtractor 查询提取器

版本: 1.0.0
作者: AI Assistant
创建时间: 2026-04-23
"""

import unittest

from dbskiter.db_diagnose.utils import (
    SQLFingerprint,
    IssueClassifier,
    ScoreCalculator,
    PrioritySorter,
    MetricsAggregator,
    QueryExtractor,
)
from dbskiter.db_diagnose.models import DiagnoseLevel


class TestSQLFingerprint(unittest.TestCase):
    """测试SQL指纹生成器"""

    def test_normalize_basic(self):
        """测试基本标准化"""
        sql = "SELECT * FROM users WHERE id = 123"
        normalized = SQLFingerprint.normalize(sql)

        self.assertIn("select", normalized)
        self.assertIn("from", normalized)
        self.assertIn("where", normalized)

    def test_normalize_removes_constants(self):
        """测试移除常量"""
        sql1 = "SELECT * FROM users WHERE id = 123"
        sql2 = "SELECT * FROM users WHERE id = 456"

        norm1 = SQLFingerprint.normalize(sql1)
        norm2 = SQLFingerprint.normalize(sql2)

        self.assertEqual(norm1, norm2)

    def test_normalize_removes_whitespace(self):
        """测试移除多余空白"""
        sql = "SELECT   *   FROM   users"
        normalized = SQLFingerprint.normalize(sql)

        self.assertNotIn("  ", normalized)

    def test_generate_fingerprint(self):
        """测试生成指纹"""
        sql = "SELECT * FROM users"
        fingerprint = SQLFingerprint.generate(sql)

        self.assertIsInstance(fingerprint, str)
        self.assertEqual(len(fingerprint), 16)

    def test_similarity_identical(self):
        """测试相同SQL相似度"""
        sql = "SELECT * FROM users WHERE id = 1"

        similarity = SQLFingerprint.similarity(sql, sql)
        self.assertEqual(similarity, 1.0)

    def test_similarity_different(self):
        """测试不同SQL相似度"""
        sql1 = "SELECT * FROM users"
        sql2 = "DELETE FROM orders"

        similarity = SQLFingerprint.similarity(sql1, sql2)
        self.assertLess(similarity, 1.0)


class TestIssueClassifier(unittest.TestCase):
    """测试问题分类器"""

    def test_classify_full_table_scan(self):
        """测试全表扫描分类"""
        result = IssueClassifier.classify("full table scan detected")

        self.assertEqual(result["type"], "full_table_scan")
        self.assertEqual(result["category"], "performance")

    def test_classify_missing_index(self):
        """测试缺失索引分类"""
        result = IssueClassifier.classify("missing index on column")

        self.assertEqual(result["type"], "missing_index")
        self.assertEqual(result["category"], "index")

    def test_classify_select_star(self):
        """测试SELECT *分类"""
        result = IssueClassifier.classify("SELECT * detected")

        self.assertEqual(result["type"], "select_star")
        self.assertEqual(result["category"], "best_practice")

    def test_classify_unknown(self):
        """测试未知问题分类"""
        result = IssueClassifier.classify("some random issue")

        self.assertEqual(result["type"], "unknown")

    def test_get_level_score(self):
        """测试级别分数"""
        self.assertEqual(IssueClassifier.get_level_score(DiagnoseLevel.CRITICAL), 100)
        self.assertEqual(IssueClassifier.get_level_score(DiagnoseLevel.HIGH), 50)
        self.assertEqual(IssueClassifier.get_level_score(DiagnoseLevel.MEDIUM), 20)
        self.assertEqual(IssueClassifier.get_level_score(DiagnoseLevel.LOW), 5)


class TestScoreCalculator(unittest.TestCase):
    """测试评分计算器"""

    def test_calculate_sql_score_no_issues(self):
        """测试无问题SQL分数"""
        score = ScoreCalculator.calculate_sql_score([])
        self.assertEqual(score, 100.0)

    def test_calculate_sql_score_with_issues(self):
        """测试有问题SQL分数"""
        issues = [
            {"level": "high"},
            {"level": "low"}
        ]
        score = ScoreCalculator.calculate_sql_score(issues)

        self.assertLess(score, 100.0)
        self.assertGreaterEqual(score, 0.0)

    def test_calculate_health_score_high_cpu(self):
        """测试高CPU健康分数"""
        metrics = {"cpu_usage": 85.0, "memory_usage": 50.0}
        score = ScoreCalculator.calculate_health_score(metrics)

        self.assertLess(score, 100.0)

    def test_calculate_health_score_normal(self):
        """测试正常健康分数"""
        metrics = {"cpu_usage": 30.0, "memory_usage": 40.0}
        score = ScoreCalculator.calculate_health_score(metrics)

        self.assertEqual(score, 100.0)


class TestPrioritySorter(unittest.TestCase):
    """测试优先级排序器"""

    def test_sort_by_priority(self):
        """测试按优先级排序"""
        items = [
            {"name": "low", "priority": "low"},
            {"name": "critical", "priority": "critical"},
            {"name": "high", "priority": "high"},
        ]

        sorted_items = PrioritySorter.sort_by_priority(items)

        self.assertEqual(sorted_items[0]["name"], "critical")
        self.assertEqual(sorted_items[1]["name"], "high")
        self.assertEqual(sorted_items[2]["name"], "low")

    def test_filter_by_min_priority(self):
        """测试按最小优先级筛选"""
        items = [
            {"name": "critical", "priority": "critical"},
            {"name": "high", "priority": "high"},
            {"name": "low", "priority": "low"},
        ]

        filtered = PrioritySorter.filter_by_min_priority(items, "high")

        self.assertEqual(len(filtered), 2)
        self.assertNotIn("low", [item["name"] for item in filtered])


class TestMetricsAggregator(unittest.TestCase):
    """测试指标聚合器"""

    def test_aggregate_issues(self):
        """测试聚合问题"""
        results = [
            {
                "issues": [
                    {"level": "high", "category": "performance"},
                    {"level": "low", "category": "style"}
                ]
            },
            {
                "issues": [
                    {"level": "high", "category": "performance"}
                ]
            }
        ]

        aggregated = MetricsAggregator.aggregate_issues(results)

        self.assertEqual(aggregated["total_issues"], 3)
        self.assertEqual(aggregated["level_counts"]["high"], 2)

    def test_calculate_averages(self):
        """测试计算平均值"""
        metrics_list = [
            {"cpu": 50.0, "memory": 60.0},
            {"cpu": 70.0, "memory": 80.0}
        ]

        averages = MetricsAggregator.calculate_averages(metrics_list)

        self.assertEqual(averages["cpu"], 60.0)
        self.assertEqual(averages["memory"], 70.0)


class TestQueryExtractor(unittest.TestCase):
    """测试查询提取器"""

    def test_extract_tables_from_select(self):
        """测试从SELECT提取表名"""
        sql = "SELECT * FROM users JOIN orders ON users.id = orders.user_id"
        tables = QueryExtractor.extract_tables(sql)

        self.assertIn("users", tables)
        self.assertIn("orders", tables)

    def test_extract_tables_from_update(self):
        """测试从UPDATE提取表名"""
        sql = "UPDATE users SET name = 'test' WHERE id = 1"
        tables = QueryExtractor.extract_tables(sql)

        self.assertIn("users", tables)

    def test_extract_columns(self):
        """测试提取列名"""
        sql = "SELECT id, name, email FROM users"
        columns = QueryExtractor.extract_columns(sql)

        self.assertIn("id", columns)
        self.assertIn("name", columns)
        self.assertIn("email", columns)

    def test_extract_where_conditions(self):
        """测试提取WHERE条件"""
        sql = "SELECT * FROM users WHERE id = 1 AND status = 'active'"
        conditions = QueryExtractor.extract_where_conditions(sql)

        self.assertEqual(len(conditions), 2)

    def test_extract_empty_sql(self):
        """测试空SQL"""
        tables = QueryExtractor.extract_tables("")
        self.assertEqual(tables, [])


if __name__ == "__main__":
    unittest.main()
