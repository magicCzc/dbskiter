"""
db_inspector/test_models.py
db_inspector 数据模型单元测试

测试范围:
    - ErrorCode错误码
    - ErrorMessage错误消息
    - 枚举类型
    - 数据类

版本: 1.0.0
作者: AI Assistant
创建时间: 2026-04-23
"""

import unittest

from dbskiter.db_inspector.models import (
    ErrorCode,
    ErrorMessage,
    RiskLevel,
    InspectionType,
    InspectionItem,
    InspectionReport,
    PerformanceBaseline,
)
from dbskiter.shared.error_handler import create_success_response, create_error_response


class TestErrorCode(unittest.TestCase):
    """测试错误码体系"""

    def test_error_code_format(self):
        """测试错误码格式正确"""
        error_codes = [
            ErrorCode.SUCCESS,
            ErrorCode.UNKNOWN_ERROR,
            ErrorCode.INSPECTION_FAILED,
            ErrorCode.BASELINE_NOT_FOUND,
        ]

        for code in error_codes:
            self.assertTrue(code.startswith("INSP"))
            self.assertEqual(len(code), 9)

    def test_error_code_uniqueness(self):
        """测试错误码唯一性"""
        error_codes = [
            ErrorCode.SUCCESS,
            ErrorCode.UNKNOWN_ERROR,
            ErrorCode.INVALID_PARAM,
            ErrorCode.CONNECTION_FAILED,
            ErrorCode.INSPECTION_FAILED,
        ]

        self.assertEqual(len(error_codes), len(set(error_codes)))


class TestErrorMessage(unittest.TestCase):
    """测试错误消息"""

    def test_get_message_exists(self):
        """测试获取存在的错误消息"""
        msg = ErrorMessage.get_message(ErrorCode.SUCCESS)
        self.assertEqual(msg, "操作成功")

    def test_get_message_not_exists(self):
        """测试获取不存在的错误消息"""
        msg = ErrorMessage.get_message("INSP99999")
        self.assertIn("未知错误码", msg)


class TestRiskLevel(unittest.TestCase):
    """测试风险等级枚举"""

    def test_level_values(self):
        """测试级别值"""
        self.assertEqual(RiskLevel.CRITICAL.value, "critical")
        self.assertEqual(RiskLevel.HIGH.value, "high")
        self.assertEqual(RiskLevel.MEDIUM.value, "medium")
        self.assertEqual(RiskLevel.LOW.value, "low")
        self.assertEqual(RiskLevel.INFO.value, "info")


class TestInspectionType(unittest.TestCase):
    """测试巡检类型枚举"""

    def test_type_values(self):
        """测试类型值"""
        self.assertEqual(InspectionType.CONFIGURATION.value, "configuration")
        self.assertEqual(InspectionType.PERFORMANCE.value, "performance")
        self.assertEqual(InspectionType.SECURITY.value, "security")


class TestInspectionItem(unittest.TestCase):
    """测试巡检项"""

    def test_item_creation(self):
        """测试巡检项创建"""
        item = InspectionItem(
            name="test_item",
            inspection_type=InspectionType.CONFIGURATION,
            risk_level=RiskLevel.HIGH,
            status="pass",
            description="测试描述"
        )

        self.assertEqual(item.name, "test_item")
        self.assertEqual(item.status, "pass")

    def test_item_to_dict(self):
        """测试转换为字典"""
        item = InspectionItem(
            name="test_item",
            inspection_type=InspectionType.PERFORMANCE,
            risk_level=RiskLevel.MEDIUM,
            status="warning",
            description="测试描述",
            suggestion="测试建议"
        )

        data = item.to_dict()
        self.assertEqual(data["name"], "test_item")
        self.assertEqual(data["status"], "warning")


class TestInspectionReport(unittest.TestCase):
    """测试巡检报告"""

    def test_report_creation(self):
        """测试报告创建"""
        from datetime import datetime
        report = InspectionReport(
            report_id="test-001",
            instance_name="test-db",
            database_type="mysql",
            database_version="8.0",
            inspection_time=datetime.now(),
            duration_seconds=10.5
        )

        self.assertEqual(report.report_id, "test-001")
        self.assertEqual(report.health_score, 100.0)

    def test_report_to_dict(self):
        """测试转换为字典"""
        from datetime import datetime
        report = InspectionReport(
            report_id="test-001",
            instance_name="test-db",
            database_type="mysql",
            database_version="8.0",
            inspection_time=datetime.now(),
            duration_seconds=10.5,
            health_score=85.5
        )

        data = report.to_dict()
        self.assertEqual(data["health_score"], 85.5)
        self.assertIn("statistics", data)

    def test_generate_summary(self):
        """测试生成摘要"""
        from datetime import datetime
        report = InspectionReport(
            report_id="test-001",
            instance_name="test-db",
            database_type="mysql",
            database_version="8.0",
            inspection_time=datetime.now(),
            duration_seconds=10.5,
            total_items=10,
            pass_count=8,
            warning_count=2
        )

        summary = report.generate_summary()
        self.assertIn("数据库巡检报告", summary)
        self.assertIn("test-db", summary)


class TestPerformanceBaseline(unittest.TestCase):
    """测试性能基线"""

    def test_baseline_creation(self):
        """测试基线创建"""
        from datetime import datetime
        baseline = PerformanceBaseline(
            baseline_id="base-001",
            instance_name="test-db",
            created_at=datetime.now()
        )

        self.assertEqual(baseline.baseline_id, "base-001")

    def test_baseline_to_dict(self):
        """测试转换为字典"""
        from datetime import datetime
        baseline = PerformanceBaseline(
            baseline_id="base-001",
            instance_name="test-db",
            created_at=datetime.now(),
            metrics={"qps": 1000.0}
        )

        data = baseline.to_dict()
        self.assertEqual(data["baseline_id"], "base-001")
        self.assertEqual(data["metrics"]["qps"], 1000.0)


class TestResponseFunctions(unittest.TestCase):
    """测试响应函数"""

    def test_create_success_response(self):
        """测试创建成功响应"""
        response = create_success_response(
            data={"score": 85},
            message="巡检成功"
        )

        self.assertTrue(response["success"])
        self.assertEqual(response["data"], {"score": 85})
        self.assertEqual(response["message"], "巡检成功")
        self.assertIn("timestamp", response)

    def test_create_error_response(self):
        """测试创建错误响应"""
        response = create_error_response(
            "巡检失败",
            error_code=ErrorCode.INSPECTION_FAILED,
            details={"instance": "test"}
        )

        self.assertFalse(response["success"])
        self.assertEqual(response["error"]["code"], ErrorCode.INSPECTION_FAILED)


if __name__ == "__main__":
    unittest.main()
