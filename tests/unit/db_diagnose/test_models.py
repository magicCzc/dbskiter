"""
db_diagnose/test_models.py
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

try:
    from dbskiter.shared.error_handler import ErrorCode as SharedErrorCode
except ImportError:
    from shared.error_handler import ErrorCode as SharedErrorCode

from dbskiter.db_diagnose.models import (
    ErrorCode,
    ErrorMessage,
    DiagnoseLevel,
    DiagnoseType,
    DatabaseType,
    DiagnoseConfig,
    DiagnoseResult,
    IndexSuggestion,
    SlowQuery,
    PerformanceMetrics,
    TableDiagnoseResult,
    DiagnoseReport,
)
from dbskiter.shared.error_handler import create_success_response, create_error_response


class TestErrorCode(unittest.TestCase):
    """测试错误码体系"""

    def test_error_code_format(self):
        """测试错误码格式正确"""
        error_codes = [
            ErrorCode.SUCCESS,
            ErrorCode.UNKNOWN_ERROR,
            ErrorCode.ANALYSIS_FAILED,
            ErrorCode.PERF_ANALYSIS_FAILED,
            ErrorCode.SLOW_QUERY_FAILED,
        ]

        for code in error_codes:
            self.assertTrue(code.startswith("DIA"))
            self.assertEqual(len(code), 9)

    def test_error_code_uniqueness(self):
        """测试错误码唯一性"""
        error_codes = [
            ErrorCode.SUCCESS,
            ErrorCode.UNKNOWN_ERROR,
            ErrorCode.INVALID_PARAM,
            ErrorCode.ANALYSIS_FAILED,
            ErrorCode.PERF_ANALYSIS_FAILED,
            ErrorCode.SLOW_QUERY_FAILED,
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
        msg = ErrorMessage.get_message("DIA999999")
        self.assertIn("未知错误码", msg)


class TestDiagnoseLevel(unittest.TestCase):
    """测试诊断级别枚举"""

    def test_level_values(self):
        """测试级别值"""
        self.assertEqual(DiagnoseLevel.CRITICAL.value, "critical")
        self.assertEqual(DiagnoseLevel.HIGH.value, "high")
        self.assertEqual(DiagnoseLevel.MEDIUM.value, "medium")
        self.assertEqual(DiagnoseLevel.LOW.value, "low")


class TestDiagnoseType(unittest.TestCase):
    """测试诊断类型枚举"""

    def test_type_values(self):
        """测试类型值"""
        self.assertEqual(DiagnoseType.SQL_ANALYSIS.value, "sql_analysis")
        self.assertEqual(DiagnoseType.PERFORMANCE.value, "performance")


class TestDatabaseType(unittest.TestCase):
    """测试数据库类型枚举"""

    def test_database_values(self):
        """测试数据库类型值"""
        self.assertEqual(DatabaseType.MYSQL.value, "mysql")
        self.assertEqual(DatabaseType.ORACLE.value, "oracle")
        self.assertEqual(DatabaseType.POSTGRESQL.value, "postgresql")


class TestDiagnoseConfig(unittest.TestCase):
    """测试诊断配置"""

    def test_default_config(self):
        """测试默认配置"""
        config = DiagnoseConfig()

        self.assertTrue(config.enable_deep_analysis)
        self.assertTrue(config.enable_index_suggestion)
        self.assertEqual(config.slow_query_threshold, 1.0)
        self.assertEqual(config.max_slow_queries, 20)

    def test_custom_config(self):
        """测试自定义配置"""
        config = DiagnoseConfig(
            enable_deep_analysis=False,
            slow_query_threshold=2.0
        )

        self.assertFalse(config.enable_deep_analysis)
        self.assertEqual(config.slow_query_threshold, 2.0)

    def test_config_to_dict(self):
        """测试配置转字典"""
        config = DiagnoseConfig(enable_performance_analysis=False)
        data = config.to_dict()

        self.assertFalse(data["enable_performance_analysis"])
        self.assertEqual(data["max_slow_queries"], 20)


class TestDiagnoseResult(unittest.TestCase):
    """测试诊断结果"""

    def test_result_creation(self):
        """测试结果创建"""
        result = DiagnoseResult(
            sql="SELECT * FROM users",
            score=85.5,
            summary="分析完成"
        )

        self.assertEqual(result.sql, "SELECT * FROM users")
        self.assertEqual(result.score, 85.5)

    def test_result_to_dict(self):
        """测试转换为字典"""
        result = DiagnoseResult(
            sql="SELECT * FROM users",
            score=85.5,
            issues=[{"type": "warning"}],
            suggestions=[{"action": "add_index"}]
        )

        data = result.to_dict()
        self.assertEqual(data["sql"], "SELECT * FROM users")
        self.assertEqual(data["score"], 85.5)
        self.assertEqual(len(data["issues"]), 1)


class TestIndexSuggestion(unittest.TestCase):
    """测试索引建议"""

    def test_suggestion_creation(self):
        """测试创建建议"""
        suggestion = IndexSuggestion(
            table="users",
            columns=["email"],
            reason="提高查询性能"
        )

        self.assertEqual(suggestion.table, "users")
        self.assertEqual(suggestion.columns, ["email"])

    def test_suggestion_to_dict(self):
        """测试转换为字典"""
        suggestion = IndexSuggestion(
            table="users",
            columns=["email"],
            index_type="btree",
            priority="high"
        )

        data = suggestion.to_dict()
        self.assertEqual(data["table"], "users")
        self.assertEqual(data["index_type"], "btree")


class TestSlowQuery(unittest.TestCase):
    """测试慢查询"""

    def test_query_creation(self):
        """测试创建慢查询"""
        query = SlowQuery(
            sql="SELECT * FROM users",
            execution_time=5.5,
            execution_count=100
        )

        self.assertEqual(query.sql, "SELECT * FROM users")
        self.assertEqual(query.execution_time, 5.5)

    def test_query_to_dict(self):
        """测试转换为字典"""
        query = SlowQuery(
            execution_time=3.5,
            rows_examined=10000
        )

        data = query.to_dict()
        self.assertEqual(data["execution_time"], 3.5)
        self.assertEqual(data["rows_examined"], 10000)


class TestPerformanceMetrics(unittest.TestCase):
    """测试性能指标"""

    def test_metrics_creation(self):
        """测试创建指标"""
        metrics = PerformanceMetrics(
            cpu_usage=75.5,
            memory_usage=60.0,
            connections=50
        )

        self.assertEqual(metrics.cpu_usage, 75.5)
        self.assertEqual(metrics.connections, 50)

    def test_metrics_to_dict(self):
        """测试转换为字典"""
        metrics = PerformanceMetrics(qps=1000.5, tps=500.0)
        data = metrics.to_dict()

        self.assertEqual(data["qps"], 1000.5)
        self.assertEqual(data["tps"], 500.0)


class TestTableDiagnoseResult(unittest.TestCase):
    """测试表诊断结果"""

    def test_result_creation(self):
        """测试结果创建"""
        result = TableDiagnoseResult(
            table_name="users",
            row_count=10000,
            size_mb=50.5
        )

        self.assertEqual(result.table_name, "users")
        self.assertEqual(result.row_count, 10000)

    def test_result_to_dict(self):
        """测试转换为字典"""
        result = TableDiagnoseResult(
            index_count=5,
            issues=[{"type": "missing_index"}]
        )

        data = result.to_dict()
        self.assertEqual(data["index_count"], 5)


class TestDiagnoseReport(unittest.TestCase):
    """测试诊断报告"""

    def test_report_creation(self):
        """测试创建报告"""
        report = DiagnoseReport(
            title="测试报告",
            total_sqls=10,
            total_issues=5
        )

        self.assertEqual(report.title, "测试报告")
        self.assertEqual(report.total_sqls, 10)

    def test_report_to_dict(self):
        """测试转换为字典"""
        report = DiagnoseReport(
            critical_count=2,
            high_count=3,
            medium_count=5
        )

        data = report.to_dict()
        self.assertEqual(data["critical_count"], 2)
        self.assertEqual(data["high_count"], 3)


class TestResponseFunctions(unittest.TestCase):
    """测试响应函数"""

    def test_create_success_response(self):
        """测试创建成功响应"""
        response = create_success_response(
            data={"rows": 10},
            message="查询成功"
        )

        self.assertTrue(response["success"])
        self.assertEqual(response["message"], "查询成功")
        self.assertIn("timestamp", response)

    def test_create_error_response(self):
        """测试创建错误响应"""
        # 使用 shared.error_handler.ErrorCode 测试
        response = create_error_response(
            "执行失败",
            error_code=SharedErrorCode.QUERY_FAILED
        )

        self.assertFalse(response["success"])
        self.assertEqual(response["error"]["code"], "2001")


if __name__ == "__main__":
    unittest.main()
