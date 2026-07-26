"""
sql_master/test_models.py
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

from dbskiter.sql_master.models import (
    ErrorCode,
    ErrorMessage,
    SQLType,
    OptimizationLevel,
    SQLOptimizationReport,
    SQLMasterConfig,
    SQLAnalysisResult,
    CacheStats,
    ExecutionResult,
    RewriteSuggestion,
)
from dbskiter.shared.error_handler import create_success_response, create_error_response


class TestErrorCode(unittest.TestCase):
    """测试错误码体系"""

    def test_error_code_format(self):
        """测试错误码格式正确"""
        error_codes = [
            ErrorCode.SUCCESS,
            ErrorCode.UNKNOWN_ERROR,
            ErrorCode.EXECUTION_FAILED,
            ErrorCode.REWRITE_FAILED,
            ErrorCode.ANALYSIS_FAILED,
        ]

        for code in error_codes:
            self.assertTrue(code.startswith("SQL"))
            self.assertEqual(len(code), 9)

    def test_error_code_uniqueness(self):
        """测试错误码唯一性"""
        error_codes = [
            ErrorCode.SUCCESS,
            ErrorCode.UNKNOWN_ERROR,
            ErrorCode.INVALID_PARAM,
            ErrorCode.EXECUTION_FAILED,
            ErrorCode.REWRITE_FAILED,
            ErrorCode.ANALYSIS_FAILED,
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
        msg = ErrorMessage.get_message("SQL999999")
        self.assertIn("未知错误码", msg)


class TestSQLType(unittest.TestCase):
    """测试SQL类型枚举"""

    def test_sql_type_values(self):
        """测试SQL类型值"""
        self.assertEqual(SQLType.SELECT.value, "select")
        self.assertEqual(SQLType.INSERT.value, "insert")
        self.assertEqual(SQLType.UPDATE.value, "update")
        self.assertEqual(SQLType.DELETE.value, "delete")


class TestOptimizationLevel(unittest.TestCase):
    """测试优化级别枚举"""

    def test_optimization_level_values(self):
        """测试优化级别值"""
        self.assertEqual(OptimizationLevel.HIGH.value, "high")
        self.assertEqual(OptimizationLevel.MEDIUM.value, "medium")
        self.assertEqual(OptimizationLevel.LOW.value, "low")


class TestSQLOptimizationReport(unittest.TestCase):
    """测试SQL优化报告"""

    def test_report_creation(self):
        """测试创建报告"""
        report = SQLOptimizationReport(
            total_sqls=10,
            can_optimize=5,
            total_suggestions=15
        )

        self.assertEqual(report.total_sqls, 10)
        self.assertEqual(report.can_optimize, 5)
        self.assertEqual(report.total_suggestions, 15)

    def test_report_to_dict(self):
        """测试转换为字典"""
        report = SQLOptimizationReport(
            total_sqls=10,
            can_optimize=5,
            high_impact=3
        )

        data = report.to_dict()
        self.assertEqual(data["total_sqls"], 10)
        self.assertEqual(data["can_optimize"], 5)
        self.assertEqual(data["high_impact"], 3)


class TestSQLMasterConfig(unittest.TestCase):
    """测试SQL Master配置"""

    def test_default_config(self):
        """测试默认配置"""
        config = SQLMasterConfig()

        self.assertTrue(config.enable_rewriter)
        self.assertTrue(config.enable_analyzer)
        self.assertTrue(config.enable_cache)
        self.assertEqual(config.max_rows, 1000)

    def test_custom_config(self):
        """测试自定义配置"""
        config = SQLMasterConfig(
            enable_rewriter=False,
            max_rows=500
        )

        self.assertFalse(config.enable_rewriter)
        self.assertEqual(config.max_rows, 500)

    def test_config_to_dict(self):
        """测试配置转字典"""
        config = SQLMasterConfig(enable_cache=False)
        data = config.to_dict()

        self.assertFalse(data["enable_cache"])
        self.assertEqual(data["max_rows"], 1000)


class TestSQLAnalysisResult(unittest.TestCase):
    """测试SQL分析结果"""

    def test_result_creation(self):
        """测试结果创建"""
        result = SQLAnalysisResult(
            sql="SELECT * FROM users",
            score=85.5,
            complexity="medium"
        )

        self.assertEqual(result.sql, "SELECT * FROM users")
        self.assertEqual(result.score, 85.5)

    def test_result_to_dict(self):
        """测试转换为字典"""
        result = SQLAnalysisResult(
            sql="SELECT * FROM users",
            score=85.5,
            issues=["issue1"],
            suggestions=["suggestion1"]
        )

        data = result.to_dict()
        self.assertEqual(data["sql"], "SELECT * FROM users")
        self.assertEqual(data["score"], 85.5)
        self.assertEqual(len(data["issues"]), 1)


class TestCacheStats(unittest.TestCase):
    """测试缓存统计"""

    def test_stats_creation(self):
        """测试创建统计"""
        stats = CacheStats(
            total_entries=100,
            hit_count=80,
            miss_count=20
        )

        self.assertEqual(stats.total_entries, 100)
        self.assertEqual(stats.hit_rate, 0.0)  # 需要手动计算

    def test_stats_to_dict(self):
        """测试转换为字典"""
        stats = CacheStats(total_entries=50)
        data = stats.to_dict()

        self.assertEqual(data["total_entries"], 50)


class TestExecutionResult(unittest.TestCase):
    """测试执行结果"""

    def test_result_creation(self):
        """测试结果创建"""
        result = ExecutionResult(
            success=True,
            row_count=10,
            columns=["id", "name"]
        )

        self.assertTrue(result.success)
        self.assertEqual(result.row_count, 10)

    def test_result_to_dict(self):
        """测试转换为字典"""
        result = ExecutionResult(
            row_count=5,
            execution_time=0.123
        )

        data = result.to_dict()
        self.assertEqual(data["row_count"], 5)
        self.assertEqual(data["execution_time"], 0.123)


class TestRewriteSuggestion(unittest.TestCase):
    """测试重写建议"""

    def test_suggestion_creation(self):
        """测试创建建议"""
        suggestion = RewriteSuggestion(
            original_sql="SELECT * FROM users",
            optimized_sql="SELECT id, name FROM users",
            reason="避免SELECT *"
        )

        self.assertEqual(suggestion.original_sql, "SELECT * FROM users")
        self.assertEqual(suggestion.reason, "避免SELECT *")

    def test_suggestion_to_dict(self):
        """测试转换为字典"""
        suggestion = RewriteSuggestion(
            original_sql="SELECT * FROM users",
            impact="high"
        )

        data = suggestion.to_dict()
        self.assertEqual(data["impact"], "high")


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
        self.assertEqual(response["data"]["rows"], 10)

    def test_create_error_response(self):
        """测试创建错误响应"""
        response = create_error_response(
            "执行失败",
            error_code=ErrorCode.EXECUTION_FAILED,
            details={"sql": "SELECT"}
        )

        self.assertFalse(response["success"])
        self.assertEqual(response["error"]["code"], ErrorCode.EXECUTION_FAILED)
        self.assertEqual(response["error"]["message"], "执行失败")
        self.assertEqual(response["error"]["details"]["sql"], "SELECT")


if __name__ == "__main__":
    unittest.main()
