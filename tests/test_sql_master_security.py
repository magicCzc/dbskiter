"""
tests/test_sql_master_security.py

验证sql_master的SecurityChecker复用db_security检测器
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import unittest
from dbskiter.sql_master.security_checker import SQLInjectionDetector


class TestSQLMasterSecurity(unittest.TestCase):

    def setUp(self):
        self.detector = SQLInjectionDetector()

    def test_normal_sql_no_false_positive(self):
        """正常业务SQL不应误报"""
        result = self.detector.detect(
            "SELECT * FROM users WHERE status = 'active' OR status = 'pending'"
        )
        self.assertFalse(result.is_injection)

    def test_injection_detected(self):
        """真实注入应被检出"""
        result = self.detector.detect(
            "SELECT * FROM users WHERE name = 'admin' OR 1=1 -- '"
        )
        self.assertTrue(result.is_injection)

    def test_union_injection(self):
        """UNION注入应被检出"""
        result = self.detector.detect(
            "SELECT * FROM users WHERE id = 1 UNION SELECT password FROM admins"
        )
        self.assertTrue(result.is_injection)

    def test_stacked_query_injection(self):
        """堆叠查询注入应被检出"""
        result = self.detector.detect(
            "SELECT * FROM users; DROP TABLE users"
        )
        self.assertTrue(result.is_injection)


if __name__ == "__main__":
    unittest.main()
