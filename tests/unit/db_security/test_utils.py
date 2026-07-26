"""
db_security/test_utils.py
工具类单元测试

测试范围:
    - PatternMatcher模式匹配器
    - EntropyCalculator熵计算器
    - RiskScorer风险评分器
    - ReportFormatter报告格式化器

版本: 1.0.0
作者: AI Assistant
创建时间: 2026-04-23
"""

import unittest

from dbskiter.db_security.models import Risk, RiskLevel
from dbskiter.db_security.utils import (
    PatternMatcher,
    EntropyCalculator,
    RiskScorer,
    ReportFormatter,
)


class TestPatternMatcher(unittest.TestCase):
    """测试模式匹配器"""

    def setUp(self):
        self.matcher = PatternMatcher()
        self.matcher.add_patterns("sql_injection", [
            r"(\%27)|(\')|(\-\-)|(\%23)|(#)",
            r"((\%3D)|(=))[^\n]*((\%27)|(\')|(\-\-)|(\%3B)|(;))",
        ])

    def test_add_patterns(self):
        """测试添加模式"""
        self.matcher.add_patterns("test", [r"test\d+"])
        results = self.matcher.match("test123", "test")
        self.assertEqual(len(results), 1)

    def test_match_found(self):
        """测试匹配成功"""
        results = self.matcher.match("' OR '1'='1")
        self.assertGreater(len(results), 0)

    def test_match_not_found(self):
        """测试匹配失败"""
        results = self.matcher.match("SELECT * FROM users")
        self.assertEqual(len(results), 0)

    def test_has_match_true(self):
        """测试有匹配"""
        self.assertTrue(self.matcher.has_match("' OR 1=1 --"))

    def test_has_match_false(self):
        """测试无匹配"""
        self.assertFalse(self.matcher.has_match("SELECT id FROM table"))


class TestEntropyCalculator(unittest.TestCase):
    """测试熵计算器"""

    def test_calculate_empty(self):
        """测试空字符串熵"""
        entropy = EntropyCalculator.calculate("")
        self.assertEqual(entropy, 0.0)

    def test_calculate_uniform(self):
        """测试均匀分布熵"""
        # "abcd" 每个字符出现一次，熵为 log2(4) = 2
        entropy = EntropyCalculator.calculate("abcd")
        self.assertAlmostEqual(entropy, 2.0, places=1)

    def test_calculate_repeated(self):
        """测试重复字符熵"""
        # "aaaa" 只有一个字符，熵为 0
        entropy = EntropyCalculator.calculate("aaaa")
        self.assertEqual(entropy, 0.0)

    def test_is_likely_encrypted_true(self):
        """测试判断为加密数据"""
        # 随机字符串应该有高熵（使用更多不同字符）
        random_str = "a8f3k9m2p5q7r4s1t6u8v9w0x1y2z3"
        self.assertTrue(EntropyCalculator.is_likely_encrypted(random_str))

    def test_is_likely_encrypted_false(self):
        """测试判断为非加密数据"""
        normal_str = "hello world"
        self.assertFalse(EntropyCalculator.is_likely_encrypted(normal_str))

    def test_get_entropy_level_low(self):
        """测试低熵级别"""
        level = EntropyCalculator.get_entropy_level("aaaa")
        self.assertEqual(level, "low")

    def test_get_entropy_level_medium(self):
        """测试中熵级别"""
        level = EntropyCalculator.get_entropy_level("hello world test")
        self.assertEqual(level, "medium")

    def test_get_entropy_level_high(self):
        """测试高熵级别"""
        # 使用更多不同类型的字符来获得高熵
        level = EntropyCalculator.get_entropy_level("a8f3k9m2p5q7r4s1t6u8v9w0x1y2z3A4B5C6D7E8F9G0!@#$%^&*()")
        self.assertEqual(level, "high")


class TestRiskScorer(unittest.TestCase):
    """测试风险评分器"""

    def test_calculate_score_no_risks(self):
        """测试无风险评分"""
        score, grade, deductions = RiskScorer.calculate_score([])
        self.assertEqual(score, 100.0)
        self.assertEqual(grade, "A")
        self.assertEqual(len(deductions), 0)

    def test_calculate_score_with_risks(self):
        """测试有风险评分"""
        risks = [
            Risk(severity="high", description="高风险1"),
            Risk(severity="medium", description="中风险1"),
        ]
        score, grade, deductions = RiskScorer.calculate_score(risks)
        self.assertLess(score, 100.0)
        self.assertEqual(len(deductions), 2)

    def test_calculate_score_critical(self):
        """测试严重风险评分"""
        risks = [
            Risk(severity="critical", description="严重风险"),
        ]
        score, grade, deductions = RiskScorer.calculate_score(risks)
        # CRITICAL权重15分，实际扣分 = 15分
        self.assertEqual(score, 85.0)  # 100 - 15

    def test_get_risk_level_critical(self):
        """测试获取严重风险等级"""
        level = RiskScorer.get_risk_level(90)
        self.assertEqual(level, RiskLevel.CRITICAL)

    def test_get_risk_level_high(self):
        """测试获取高风险等级"""
        level = RiskScorer.get_risk_level(70)
        self.assertEqual(level, RiskLevel.HIGH)

    def test_get_risk_level_medium(self):
        """测试获取中风险等级"""
        level = RiskScorer.get_risk_level(50)
        self.assertEqual(level, RiskLevel.MEDIUM)

    def test_get_risk_level_low(self):
        """测试获取低风险等级"""
        level = RiskScorer.get_risk_level(30)
        self.assertEqual(level, RiskLevel.LOW)


class TestReportFormatter(unittest.TestCase):
    """测试报告格式化器"""

    def setUp(self):
        self.formatter = ReportFormatter()

    def test_format_text_report(self):
        """测试格式化文本报告"""
        risks = [
            Risk(severity="high", description="测试风险1"),
            Risk(severity="medium", description="测试风险2"),
        ]
        report = self.formatter.format_text_report(
            title="测试报告",
            score=75.5,
            grade="C",
            risks=risks
        )

        self.assertIn("测试报告", report)
        self.assertIn("75.5", report)
        self.assertIn("C", report)
        self.assertIn("测试风险1", report)

    def test_format_text_report_no_risks(self):
        """测试无风险报告"""
        report = self.formatter.format_text_report(
            title="安全报告",
            score=100.0,
            grade="A",
            risks=[]
        )

        self.assertIn("安全报告", report)
        self.assertIn("未发现明显安全风险", report)

    def test_format_summary(self):
        """测试格式化摘要"""
        summary = self.formatter.format_summary(
            score=85.0,
            grade="B",
            deductions=["风险1", "风险2"],
            checked_at="2026-04-23T10:00:00"
        )

        self.assertIn("85.0", summary)
        self.assertIn("B", summary)
        self.assertIn("风险1", summary)
        self.assertIn("2026-04-23", summary)

    def test_format_summary_no_deductions(self):
        """测试无扣分项摘要"""
        summary = self.formatter.format_summary(
            score=100.0,
            grade="A",
            deductions=[],
            checked_at="2026-04-23T10:00:00"
        )

        self.assertIn("100.0", summary)
        self.assertIn("未发现明显安全风险", summary)


if __name__ == "__main__":
    unittest.main()
