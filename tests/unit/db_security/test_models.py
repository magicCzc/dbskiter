"""
db_security/test_models.py
数据模型单元测试

测试范围:
    - ErrorCode错误码体系
    - ErrorMessage错误消息
    - 所有枚举类型
    - 数据类转换

版本: 1.0.0
作者: AI Assistant
创建时间: 2026-04-23
"""

import unittest
from datetime import datetime

from dbskiter.db_security.models import (
    ErrorCode,
    ErrorMessage,
    RiskLevel,
    InjectionType,
    SensitivityLevel,
    DataCategory,
    Risk,
    RiskReport,
    SecurityConfig,
    SQLInjectionResult,
    SensitiveDataResult,
    create_success_response,
    create_error_response,
)


class TestErrorCode(unittest.TestCase):
    """测试错误码体系"""

    def test_error_code_format(self):
        """测试错误码格式正确"""
        error_codes = [
            ErrorCode.SUCCESS,
            ErrorCode.UNKNOWN_ERROR,
            ErrorCode.INJECTION_DETECTED,
            ErrorCode.SCAN_FAILED,
            ErrorCode.AUDIT_FAILED,
        ]

        for code in error_codes:
            self.assertTrue(code.startswith("SEC"))
            self.assertEqual(len(code), 9)

    def test_error_code_uniqueness(self):
        """测试错误码唯一性"""
        error_codes = [
            ErrorCode.SUCCESS,
            ErrorCode.UNKNOWN_ERROR,
            ErrorCode.INVALID_PARAM,
            ErrorCode.INJECTION_DETECTED,
            ErrorCode.SCAN_FAILED,
            ErrorCode.AUDIT_FAILED,
        ]

        self.assertEqual(len(error_codes), len(set(error_codes)))


class TestErrorMessage(unittest.TestCase):
    """测试错误消息映射"""

    def test_get_message_exists(self):
        """测试获取存在的错误消息"""
        msg = ErrorMessage.get_message(ErrorCode.SUCCESS)
        self.assertEqual(msg, "操作成功")

        msg = ErrorMessage.get_message(ErrorCode.INJECTION_DETECTED)
        self.assertEqual(msg, "检测到SQL注入风险")

    def test_get_message_not_exists(self):
        """测试获取不存在的错误消息"""
        msg = ErrorMessage.get_message("SEC999999")
        self.assertIn("未知错误码", msg)


class TestRiskLevel(unittest.TestCase):
    """测试风险等级枚举"""

    def test_risk_level_values(self):
        """测试风险等级值"""
        self.assertEqual(RiskLevel.CRITICAL.value, "critical")
        self.assertEqual(RiskLevel.HIGH.value, "high")
        self.assertEqual(RiskLevel.MEDIUM.value, "medium")
        self.assertEqual(RiskLevel.LOW.value, "low")


class TestInjectionType(unittest.TestCase):
    """测试注入类型枚举"""

    def test_injection_type_values(self):
        """测试注入类型值"""
        self.assertEqual(InjectionType.BOOLEAN_BASED.value, "boolean_based")
        self.assertEqual(InjectionType.TIME_BASED.value, "time_based")
        self.assertEqual(InjectionType.UNION_BASED.value, "union_based")


class TestSensitivityLevel(unittest.TestCase):
    """测试敏感度等级枚举"""

    def test_sensitivity_level_values(self):
        """测试敏感度等级值"""
        self.assertEqual(SensitivityLevel.CRITICAL.value, "critical")
        self.assertEqual(SensitivityLevel.HIGH.value, "high")
        self.assertEqual(SensitivityLevel.MEDIUM.value, "medium")
        self.assertEqual(SensitivityLevel.LOW.value, "low")


class TestDataCategory(unittest.TestCase):
    """测试数据类别枚举"""

    def test_data_category_values(self):
        """测试数据类别值"""
        self.assertEqual(DataCategory.CREDENTIALS.value, "credentials")
        self.assertEqual(DataCategory.PII.value, "pii")
        self.assertEqual(DataCategory.FINANCIAL.value, "financial")


class TestRisk(unittest.TestCase):
    """测试风险数据类"""

    def test_risk_creation(self):
        """测试创建风险"""
        risk = Risk(
            severity="high",
            description="SQL注入风险",
            category="sql_injection"
        )

        self.assertEqual(risk.severity, "high")
        self.assertEqual(risk.description, "SQL注入风险")

    def test_risk_to_dict(self):
        """测试风险转字典"""
        risk = Risk(
            severity="critical",
            description="严重漏洞",
            category="injection"
        )

        data = risk.to_dict()
        self.assertIsInstance(data, dict)
        self.assertEqual(data["severity"], "critical")


class TestRiskReport(unittest.TestCase):
    """测试风险报告"""

    def test_risk_report_creation(self):
        """测试创建风险报告"""
        report = RiskReport(
            total_risks=5,
            critical_count=1,
            high_count=2,
            medium_count=1,
            low_count=1
        )

        self.assertEqual(report.total_risks, 5)
        self.assertEqual(report.critical_count, 1)

    def test_risk_report_to_dict(self):
        """测试风险报告转字典"""
        report = RiskReport(
            total_risks=3,
            risks=[Risk(severity="high", description="测试")]
        )

        data = report.to_dict()
        self.assertIsInstance(data, dict)
        self.assertEqual(data["total_risks"], 3)


class TestSecurityConfig(unittest.TestCase):
    """测试安全配置"""

    def test_default_config(self):
        """测试默认配置"""
        config = SecurityConfig()

        self.assertTrue(config.enable_sql_injection_detection)
        self.assertTrue(config.enable_sensitive_data_scan)
        self.assertEqual(config.sample_size, 100)

    def test_custom_config(self):
        """测试自定义配置"""
        config = SecurityConfig(
            enable_sql_injection_detection=False,
            sample_size=200
        )

        self.assertFalse(config.enable_sql_injection_detection)
        self.assertEqual(config.sample_size, 200)

    def test_config_to_dict(self):
        """测试配置转字典"""
        config = SecurityConfig()
        data = config.to_dict()

        self.assertIsInstance(data, dict)
        self.assertIn("enable_sql_injection_detection", data)


class TestSQLInjectionResult(unittest.TestCase):
    """测试SQL注入结果"""

    def test_result_creation(self):
        """测试创建结果"""
        result = SQLInjectionResult(
            is_injection=True,
            risk_score=85.5,
            risk_level=RiskLevel.HIGH,
            description="发现注入"
        )

        self.assertTrue(result.is_injection)
        self.assertEqual(result.risk_score, 85.5)

    def test_result_to_dict(self):
        """测试结果转字典"""
        result = SQLInjectionResult(
            is_injection=False,
            risk_score=10.0,
            risk_level=RiskLevel.LOW
        )

        data = result.to_dict()
        self.assertIsInstance(data, dict)
        self.assertFalse(data["is_injection"])


class TestSensitiveDataResult(unittest.TestCase):
    """测试敏感数据结果"""

    def test_result_creation(self):
        """测试创建结果"""
        result = SensitiveDataResult(
            total_tables=10,
            total_columns=50,
            scan_duration=5.5
        )

        self.assertEqual(result.total_tables, 10)
        self.assertEqual(result.scan_duration, 5.5)

    def test_result_to_dict(self):
        """测试结果转字典"""
        result = SensitiveDataResult(total_tables=5)
        data = result.to_dict()

        self.assertIsInstance(data, dict)
        self.assertEqual(data["total_tables"], 5)


class TestResponseFunctions(unittest.TestCase):
    """测试响应辅助函数"""

    def test_create_success_response(self):
        """测试创建成功响应"""
        response = create_success_response({"id": 1}, "操作成功")

        self.assertTrue(response["success"])
        self.assertEqual(response["data"]["id"], 1)
        self.assertIn("timestamp", response)

    def test_create_error_response(self):
        """测试创建错误响应"""
        response = create_error_response(
            "操作失败",
            error_code=ErrorCode.INVALID_PARAM,
            details={"field": "name"}
        )

        self.assertFalse(response["success"])
        self.assertEqual(response["error"]["code"], ErrorCode.INVALID_PARAM)
        self.assertEqual(response["error"]["details"]["field"], "name")
        self.assertIn("timestamp", response)


if __name__ == "__main__":
    unittest.main()
