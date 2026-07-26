"""
db_sql_auditor/test_models.py
数据模型单元测试

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

from dbskiter.db_sql_auditor.models import (
    ErrorCode,
    ErrorMessage,
    AuditLevel,
    AuditType,
    SQLType,
    AuditConfig,
    AuditIssue,
    AuditResult,
    AuditRule,
    DDLImpact,
    BatchAuditResult,
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
            ErrorCode.AUDIT_FAILED,
            ErrorCode.DDL_ANALYSIS_FAILED,
        ]

        for code in error_codes:
            self.assertTrue(code.startswith("AUD"))
            self.assertEqual(len(code), 9)

    def test_error_code_uniqueness(self):
        """测试错误码唯一性"""
        error_codes = [
            ErrorCode.SUCCESS,
            ErrorCode.UNKNOWN_ERROR,
            ErrorCode.INVALID_PARAM,
            ErrorCode.AUDIT_FAILED,
            ErrorCode.DDL_ANALYSIS_FAILED,
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
        msg = ErrorMessage.get_message("AUD999999")
        self.assertIn("未知错误码", msg)


class TestAuditLevel(unittest.TestCase):
    """测试审核级别枚举"""

    def test_level_values(self):
        """测试级别值"""
        self.assertEqual(AuditLevel.CRITICAL.value, "critical")
        self.assertEqual(AuditLevel.HIGH.value, "high")
        self.assertEqual(AuditLevel.MEDIUM.value, "medium")
        self.assertEqual(AuditLevel.LOW.value, "low")


class TestAuditType(unittest.TestCase):
    """测试审核类型枚举"""

    def test_type_values(self):
        """测试类型值"""
        self.assertEqual(AuditType.SYNTAX.value, "syntax")
        self.assertEqual(AuditType.PERFORMANCE.value, "performance")
        self.assertEqual(AuditType.SECURITY.value, "security")


class TestSQLType(unittest.TestCase):
    """测试SQL类型枚举"""

    def test_sql_type_values(self):
        """测试SQL类型值"""
        self.assertEqual(SQLType.SELECT.value, "SELECT")
        self.assertEqual(SQLType.INSERT.value, "INSERT")
        self.assertEqual(SQLType.UPDATE.value, "UPDATE")


class TestAuditConfig(unittest.TestCase):
    """测试审核配置"""

    def test_default_config(self):
        """测试默认配置"""
        config = AuditConfig()

        self.assertTrue(config.enable_syntax_check)
        self.assertTrue(config.enable_performance_check)
        self.assertTrue(config.enable_security_check)
        self.assertEqual(config.max_issues_per_sql, 50)

    def test_custom_config(self):
        """测试自定义配置"""
        config = AuditConfig(
            enable_syntax_check=False,
            max_issues_per_sql=100
        )

        self.assertFalse(config.enable_syntax_check)
        self.assertEqual(config.max_issues_per_sql, 100)

    def test_config_to_dict(self):
        """测试配置转字典"""
        config = AuditConfig(enable_style_check=False)
        data = config.to_dict()

        self.assertFalse(data["enable_style_check"])
        self.assertEqual(data["max_issues_per_sql"], 50)


class TestAuditIssue(unittest.TestCase):
    """测试审核问题"""

    def test_issue_creation(self):
        """测试问题创建"""
        issue = AuditIssue(
            rule_id="PERF-001",
            rule_name="测试规则",
            audit_type=AuditType.PERFORMANCE,
            level=AuditLevel.HIGH,
            message="测试消息",
            suggestion="测试建议"
        )

        self.assertEqual(issue.rule_id, "PERF-001")
        self.assertEqual(issue.level, AuditLevel.HIGH)

    def test_issue_to_dict(self):
        """测试转换为字典"""
        issue = AuditIssue(
            rule_id="PERF-001",
            rule_name="测试规则",
            audit_type=AuditType.PERFORMANCE,
            level=AuditLevel.HIGH,
            message="测试消息",
            suggestion="测试建议",
            line_number=10
        )

        data = issue.to_dict()
        self.assertEqual(data["rule_id"], "PERF-001")
        self.assertEqual(data["line_number"], 10)


class TestAuditResult(unittest.TestCase):
    """测试审核结果"""

    def test_result_creation(self):
        """测试结果创建"""
        from datetime import datetime
        result = AuditResult(
            audit_id="test-001",
            sql_content="SELECT * FROM users",
            sql_type=SQLType.SELECT,
            audit_time=datetime.now()
        )

        self.assertEqual(result.audit_id, "test-001")
        self.assertEqual(result.score, 100.0)

    def test_result_to_dict(self):
        """测试转换为字典"""
        from datetime import datetime
        result = AuditResult(
            audit_id="test-001",
            sql_content="SELECT * FROM users",
            sql_type=SQLType.SELECT,
            audit_time=datetime.now(),
            score=85.5,
            passed=False
        )

        data = result.to_dict()
        self.assertEqual(data["score"], 85.5)
        self.assertFalse(data["passed"])


class TestAuditRule(unittest.TestCase):
    """测试审核规则"""

    def test_rule_creation(self):
        """测试规则创建"""
        rule = AuditRule(
            rule_id="PERF-001",
            rule_name="测试规则",
            audit_type=AuditType.PERFORMANCE,
            level=AuditLevel.HIGH,
            description="测试描述"
        )

        self.assertEqual(rule.rule_id, "PERF-001")
        self.assertTrue(rule.enabled)

    def test_rule_to_dict(self):
        """测试转换为字典"""
        rule = AuditRule(
            rule_id="PERF-001",
            rule_name="测试规则",
            audit_type=AuditType.PERFORMANCE,
            level=AuditLevel.HIGH,
            description="测试描述",
            enabled=False
        )

        data = rule.to_dict()
        self.assertFalse(data["enabled"])


class TestDDLImpact(unittest.TestCase):
    """测试DDL影响分析"""

    def test_impact_creation(self):
        """测试创建影响分析"""
        impact = DDLImpact(
            ddl_sql="ALTER TABLE users ADD COLUMN age INT",
            table_name="users",
            operation="ADD_COLUMN",
            execution_time_estimate="1-2分钟"
        )

        self.assertEqual(impact.table_name, "users")

    def test_impact_to_dict(self):
        """测试转换为字典"""
        impact = DDLImpact(
            ddl_sql="ALTER TABLE users ADD COLUMN age INT",
            table_name="users",
            operation="ADD_COLUMN",
            execution_time_estimate="1-2分钟",
            risks=["锁表风险"]
        )

        data = impact.to_dict()
        self.assertEqual(data["table_name"], "users")
        self.assertEqual(len(data["risks"]), 1)


class TestResponseFunctions(unittest.TestCase):
    """测试响应函数"""

    def test_create_success_response(self):
        """测试创建成功响应"""
        response = create_success_response(
            data={"score": 85},
            message="审核成功"
        )

        self.assertTrue(response["success"])
        self.assertEqual(response["data"], {"score": 85})
        self.assertEqual(response["message"], "审核成功")

    def test_create_error_response(self):
        """测试创建错误响应"""
        response = create_error_response(
            "审核失败",
            error_code=ErrorCode.AUDIT_FAILED,
            details={"sql": "SELECT"}
        )

        self.assertFalse(response["success"])
        self.assertEqual(response["error"]["code"], ErrorCode.AUDIT_FAILED)


if __name__ == "__main__":
    unittest.main()
