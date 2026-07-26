"""
db_sql_auditor/test_utils.py
工具类单元测试

测试范围:
    - SQLParser SQL解析器
    - RuleEngine 规则引擎
    - ScoreCalculator 评分计算器
    - IssueAggregator 问题聚合器
    - SQLNormalizer SQL标准化器
    - AuditReporter 审核报告生成器

版本: 1.0.0
作者: AI Assistant
创建时间: 2026-04-23
"""

import unittest

from dbskiter.db_sql_auditor.utils import (
    SQLParser,
    RuleEngine,
    ScoreCalculator,
    IssueAggregator,
    SQLNormalizer,
    AuditReporter,
)
from dbskiter.db_sql_auditor.models import (
    AuditLevel,
    AuditType,
    SQLType,
    AuditIssue,
    AuditResult,
)


class TestSQLParser(unittest.TestCase):
    """测试SQL解析器"""

    def test_detect_select(self):
        """测试检测SELECT"""
        sql = "SELECT * FROM users"
        sql_type = SQLParser.detect_sql_type(sql)
        self.assertEqual(sql_type, SQLType.SELECT)

    def test_detect_insert(self):
        """测试检测INSERT"""
        sql = "INSERT INTO users (name) VALUES ('test')"
        sql_type = SQLParser.detect_sql_type(sql)
        self.assertEqual(sql_type, SQLType.INSERT)

    def test_detect_update(self):
        """测试检测UPDATE"""
        sql = "UPDATE users SET name = 'test'"
        sql_type = SQLParser.detect_sql_type(sql)
        self.assertEqual(sql_type, SQLType.UPDATE)

    def test_detect_unknown(self):
        """测试检测未知类型"""
        sql = ""
        sql_type = SQLParser.detect_sql_type(sql)
        self.assertEqual(sql_type, SQLType.UNKNOWN)

    def test_extract_tables_from_select(self):
        """测试从SELECT提取表名"""
        sql = "SELECT * FROM users JOIN orders ON users.id = orders.user_id"
        tables = SQLParser.extract_tables(sql)

        self.assertIn("users", tables)
        self.assertIn("orders", tables)

    def test_extract_tables_from_update(self):
        """测试从UPDATE提取表名"""
        sql = "UPDATE users SET name = 'test'"
        tables = SQLParser.extract_tables(sql)

        self.assertIn("users", tables)

    def test_has_where_clause(self):
        """测试检测WHERE子句"""
        sql_with_where = "SELECT * FROM users WHERE id = 1"
        sql_without_where = "SELECT * FROM users"

        self.assertTrue(SQLParser.has_where_clause(sql_with_where))
        self.assertFalse(SQLParser.has_where_clause(sql_without_where))

    def test_has_limit_clause(self):
        """测试检测LIMIT子句"""
        sql_with_limit = "SELECT * FROM users LIMIT 10"
        sql_without_limit = "SELECT * FROM users"

        self.assertTrue(SQLParser.has_limit_clause(sql_with_limit))
        self.assertFalse(SQLParser.has_limit_clause(sql_without_limit))


class TestRuleEngine(unittest.TestCase):
    """测试规则引擎"""

    def test_init_builtin_rules(self):
        """测试初始化内置规则"""
        engine = RuleEngine()
        rules = engine.get_all_rules()

        self.assertGreater(len(rules), 0)

    def test_get_rule_exists(self):
        """测试获取存在的规则"""
        engine = RuleEngine()
        rule = engine.get_rule("PERF-001")

        self.assertIsNotNone(rule)
        self.assertEqual(rule.rule_id, "PERF-001")

    def test_get_rule_not_exists(self):
        """测试获取不存在的规则"""
        engine = RuleEngine()
        rule = engine.get_rule("NON-EXISTENT")

        self.assertIsNone(rule)

    def test_enable_disable_rule(self):
        """测试启用禁用规则"""
        engine = RuleEngine()

        # 禁用规则
        success = engine.disable_rule("PERF-001")
        self.assertTrue(success)

        rule = engine.get_rule("PERF-001")
        self.assertFalse(rule.enabled)

        # 启用规则
        success = engine.enable_rule("PERF-001")
        self.assertTrue(success)

        rule = engine.get_rule("PERF-001")
        self.assertTrue(rule.enabled)

    def test_execute_rule_select_star(self):
        """测试执行SELECT *规则"""
        engine = RuleEngine()
        issue = engine.execute_rule("PERF-001", "SELECT * FROM users")

        self.assertIsNotNone(issue)
        self.assertEqual(issue.rule_id, "PERF-001")

    def test_execute_rule_no_issue(self):
        """测试执行无问题的规则"""
        engine = RuleEngine()
        issue = engine.execute_rule("PERF-001", "SELECT id FROM users")

        self.assertIsNone(issue)


class TestScoreCalculator(unittest.TestCase):
    """测试评分计算器"""

    def test_calculate_score_no_issues(self):
        """测试无问题评分"""
        calculator = ScoreCalculator()
        score = calculator.calculate_score([])

        self.assertEqual(score, 100.0)

    def test_calculate_score_with_critical(self):
        """测试有严重问题评分"""
        calculator = ScoreCalculator()
        issues = [
            AuditIssue(
                rule_id="SEC-001",
                rule_name="测试",
                audit_type=AuditType.SECURITY,
                level=AuditLevel.CRITICAL,
                message="测试",
                suggestion="测试"
            )
        ]
        score = calculator.calculate_score(issues)

        self.assertEqual(score, 70.0)  # 100 - 30

    def test_calculate_pass_status(self):
        """测试通过状态计算"""
        calculator = ScoreCalculator()

        # 通过：分数>=80且无严重问题
        self.assertTrue(calculator.calculate_pass_status(85, 0))

        # 不通过：分数<80
        self.assertFalse(calculator.calculate_pass_status(75, 0))

        # 不通过：有严重问题
        self.assertFalse(calculator.calculate_pass_status(85, 1))


class TestIssueAggregator(unittest.TestCase):
    """测试问题聚合器"""

    def test_aggregate_results(self):
        """测试聚合结果"""
        from datetime import datetime
        results = [
            AuditResult(
                audit_id="1",
                sql_content="SELECT * FROM users",
                sql_type=SQLType.SELECT,
                audit_time=datetime.now(),
                total_issues=2,
                high_count=1,
                low_count=1
            ),
            AuditResult(
                audit_id="2",
                sql_content="SELECT * FROM orders",
                sql_type=SQLType.SELECT,
                audit_time=datetime.now(),
                total_issues=1,
                medium_count=1
            )
        ]

        aggregated = IssueAggregator.aggregate_results(results)

        self.assertEqual(aggregated["total_sqls"], 2)
        self.assertEqual(aggregated["total_issues"], 3)


class TestSQLNormalizer(unittest.TestCase):
    """测试SQL标准化器"""

    def test_normalize_basic(self):
        """测试基本标准化"""
        sql = "SELECT   *   FROM   users"
        normalized = SQLNormalizer.normalize(sql)

        self.assertNotIn("  ", normalized)

    def test_normalize_removes_constants(self):
        """测试移除常量"""
        sql1 = "SELECT * FROM users WHERE id = 123"
        sql2 = "SELECT * FROM users WHERE id = 456"

        norm1 = SQLNormalizer.normalize(sql1)
        norm2 = SQLNormalizer.normalize(sql2)

        self.assertEqual(norm1, norm2)

    def test_generate_fingerprint(self):
        """测试生成指纹"""
        sql = "SELECT * FROM users"
        fingerprint = SQLNormalizer.generate_fingerprint(sql)

        self.assertIsInstance(fingerprint, str)
        self.assertEqual(len(fingerprint), 16)


class TestAuditReporter(unittest.TestCase):
    """测试审核报告生成器"""

    def test_generate_summary(self):
        """测试生成汇总"""
        from datetime import datetime
        results = [
            AuditResult(
                audit_id="1",
                sql_content="SELECT * FROM users",
                sql_type=SQLType.SELECT,
                audit_time=datetime.now(),
                total_issues=2,
                passed=False
            )
        ]

        summary = AuditReporter.generate_summary(results)

        self.assertIn("SQL审核报告", summary)
        self.assertIn("审核SQL数", summary)

    def test_generate_summary_empty(self):
        """测试空结果汇总"""
        summary = AuditReporter.generate_summary([])

        self.assertIn("没有审核结果", summary)


if __name__ == "__main__":
    unittest.main()
