"""
tests/test_security_injection.py

SQL注入检测器核心逻辑测试
验证误报率降低、真实注入payload能检出。
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import unittest
from dbskiter.db_security.sql_injection_detector_v2 import SQLInjectionDetectorV2, RiskLevel


class TestSQLInjectionDetector(unittest.TestCase):
    """SQL注入检测器 V2 测试"""

    def setUp(self):
        self.detector = SQLInjectionDetectorV2()

    def _has_critical_or_high(self, result):
        """判断结果中是否有 CRITICAL 或 HIGH 级别的发现"""
        return any(
            f["risk_level"] in ("critical", "high")
            for f in result.get("findings", [])
        )

    def _get_max_level(self, result):
        """获取结果中的最高风险等级"""
        levels = [f["risk_level"] for f in result.get("findings", [])]
        if "critical" in levels:
            return "critical"
        if "high" in levels:
            return "high"
        if "medium" in levels:
            return "medium"
        if "low" in levels:
            return "low"
        return "none"

    # ========== 正常SQL不应误报 ==========

    def test_normal_select_no_false_positive(self):
        """正常 SELECT 不应报注入"""
        result = self.detector.analyze_sql("SELECT * FROM users WHERE id = 1")
        self.assertFalse(self._has_critical_or_high(result))

    def test_normal_or_condition_no_false_positive(self):
        """正常业务逻辑中的 OR 条件不应报注入"""
        result = self.detector.analyze_sql(
            "SELECT * FROM users WHERE status = 'active' OR status = 'pending'"
        )
        self.assertFalse(self._has_critical_or_high(result))

    def test_normal_join_no_false_positive(self):
        """正常 JOIN 不应报注入"""
        result = self.detector.analyze_sql(
            "SELECT u.name, o.amount FROM users u JOIN orders o ON u.id = o.user_id"
        )
        self.assertFalse(self._has_critical_or_high(result))

    def test_normal_union_no_false_positive(self):
        """正常的 UNION ALL 不应报注入"""
        result = self.detector.analyze_sql(
            "SELECT name FROM employees UNION ALL SELECT name FROM contractors"
        )
        self.assertFalse(self._has_critical_or_high(result))

    def test_normal_comments_no_false_positive(self):
        """正常的 SQL 注释不应报注入"""
        result = self.detector.analyze_sql(
            "SELECT * FROM users /* get all users */ WHERE status = 'active'"
        )
        self.assertFalse(self._has_critical_or_high(result))

    # ========== 真实注入payload应检出 ==========

    def test_or_tautology_with_comment_injection(self):
        """OR 1=1 加注释是经典注入"""
        result = self.detector.analyze_sql(
            "SELECT * FROM users WHERE name = 'admin' OR 1=1 -- '"
        )
        self.assertTrue(self._has_critical_or_high(result))

    def test_union_injection(self):
        """UNION SELECT 注入"""
        result = self.detector.analyze_sql(
            "SELECT * FROM users WHERE id = 1 UNION SELECT password FROM admins"
        )
        self.assertTrue(self._has_critical_or_high(result))

    def test_stacked_query_injection(self):
        """堆叠查询注入"""
        result = self.detector.analyze_sql(
            "SELECT * FROM users; DROP TABLE users"
        )
        self.assertTrue(self._has_critical_or_high(result))

    def test_param_stacked_query(self):
        """参数中包含堆叠查询"""
        result = self.detector.analyze_sql(
            "SELECT * FROM users WHERE id = %s",
            params={"id": "1; DROP TABLE users"}
        )
        self.assertTrue(self._has_critical_or_high(result))

    def test_param_union_injection(self):
        """参数中包含 UNION 注入"""
        result = self.detector.analyze_sql(
            "SELECT * FROM users WHERE id = %s",
            params={"id": "1 UNION SELECT password FROM admins"}
        )
        self.assertTrue(self._has_critical_or_high(result))

    def test_param_time_based(self):
        """参数中包含时间盲注"""
        result = self.detector.analyze_sql(
            "SELECT * FROM users WHERE id = %s",
            params={"id": "1 AND SLEEP(5)"}
        )
        self.assertTrue(self._has_critical_or_high(result))

    def test_param_boolean_blind(self):
        """参数中包含布尔盲注"""
        result = self.detector.analyze_sql(
            "SELECT * FROM users WHERE name = %s",
            params={"name": "admin' OR 1=1 -- "}
        )
        self.assertTrue(self._has_critical_or_high(result))

    # ========== 边界情况 ==========

    def test_empty_sql(self):
        """空 SQL 不应报错"""
        result = self.detector.analyze_sql("")
        self.assertEqual(result["has_injection"], False)

    def test_normal_params_no_false_positive(self):
        """正常参数值不应误报"""
        result = self.detector.analyze_sql(
            "SELECT * FROM users WHERE name = %s AND status = %s",
            params={"name": "Alice", "status": "active"}
        )
        self.assertFalse(self._has_critical_or_high(result))

    def test_param_with_select_keyword_no_false_positive(self):
        """参数中包含 SELECT 单词但无注入特征不应报 HIGH"""
        result = self.detector.analyze_sql(
            "SELECT * FROM documents WHERE title = %s",
            params={"title": "How to SELECT the best product"}
        )
        # 可能报 LOW, 但不应报 HIGH 或 CRITICAL
        self.assertNotIn(self._get_max_level(result), ("critical", "high"))


if __name__ == "__main__":
    unittest.main()
