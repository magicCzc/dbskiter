"""
诊断报告生成器单元测试

文件功能：测试ReportGenerator的所有功能
主要测试类：
- TestReportGenerator: 报告生成器测试

作者：AI Assistant
创建时间：2026-04-22
"""

import unittest
import sys
import json
from typing import Dict, Any, List

sys.path.insert(0, r'e:\Chenzc-AIDev\数据库skill')

from dbskiter.db_diagnose.reports.generator import ReportGenerator


# =============================================================================
# 报告生成器测试
# =============================================================================

class TestReportGenerator(unittest.TestCase):
    """ReportGenerator测试"""

    def setUp(self):
        """测试前置准备"""
        self.generator = ReportGenerator()
        self.sample_analyses = [
            {
                "success": True,
                "sql": "SELECT * FROM users WHERE email = 'test@test.com'",
                "sql_type": "SELECT",
                "cost_estimate": {"total_cost": 100.5},
                "issues": [
                    {
                        "severity": "high",
                        "description": "使用了SELECT *",
                        "table": "users"
                    },
                    {
                        "severity": "critical",
                        "description": "缺少索引",
                        "table": "users"
                    }
                ],
                "index_suggestions": [
                    {
                        "table": "users",
                        "columns": ["email"],
                        "reason": "WHERE条件使用",
                        "create_sql": "CREATE INDEX idx_users_email ON users(email)"
                    }
                ]
            },
            {
                "success": True,
                "sql": "SELECT id, name FROM orders WHERE user_id = 123",
                "sql_type": "SELECT",
                "cost_estimate": {"total_cost": 50.0},
                "issues": [
                    {
                        "severity": "medium",
                        "description": "隐式类型转换",
                        "table": "orders"
                    }
                ],
                "index_suggestions": []
            },
            {
                "success": False,
                "sql": "INVALID SQL",
                "error": "语法错误"
            }
        ]

    def test_init_basic(self):
        """测试基本初始化"""
        generator = ReportGenerator()
        self.assertIsNotNone(generator)

    def test_generate_text_report(self):
        """测试生成文本格式报告"""
        report = self.generator.generate(
            self.sample_analyses,
            report_format="text",
            include_fixes=True
        )

        self.assertIsInstance(report, str)
        self.assertIn("数据库SQL优化报告", report)
        self.assertIn("分析SQL数量: 3", report)
        self.assertIn("发现问题总数: 3", report)
        self.assertIn("严重问题: 1", report)
        self.assertIn("高危问题: 1", report)

    def test_generate_markdown_report(self):
        """测试生成Markdown格式报告"""
        report = self.generator.generate(
            self.sample_analyses,
            report_format="markdown",
            include_fixes=True
        )

        self.assertIsInstance(report, str)
        self.assertIn("# 数据库SQL优化报告", report)
        self.assertIn("## 摘要", report)
        self.assertIn("## 详细分析", report)
        self.assertIn("```sql", report)

    def test_generate_json_report(self):
        """测试生成JSON格式报告"""
        report = self.generator.generate(
            self.sample_analyses,
            report_format="json",
            include_fixes=True
        )

        self.assertIsInstance(report, str)
        # 验证是有效的JSON
        data = json.loads(report)
        self.assertIn("summary", data)
        self.assertIn("details", data)
        self.assertEqual(data["summary"]["total_sql"], 3)
        self.assertEqual(data["summary"]["total_issues"], 3)

    def test_generate_without_fixes(self):
        """测试不包含修复SQL的报告"""
        report = self.generator.generate(
            self.sample_analyses,
            report_format="text",
            include_fixes=False
        )

        self.assertIsInstance(report, str)
        # 不包含可执行的修复语句
        self.assertNotIn("可执行的索引创建语句", report)

    def test_generate_empty_analyses(self):
        """测试空分析列表"""
        report = self.generator.generate(
            [],
            report_format="text",
            include_fixes=True
        )

        self.assertIsInstance(report, str)
        self.assertIn("分析SQL数量: 0", report)
        self.assertIn("发现问题总数: 0", report)

    def test_generate_single_analysis(self):
        """测试单条分析结果"""
        single_analysis = [self.sample_analyses[0]]
        report = self.generator.generate(
            single_analysis,
            report_format="text",
            include_fixes=True
        )

        self.assertIsInstance(report, str)
        self.assertIn("分析SQL数量: 1", report)
        self.assertIn("发现问题总数: 2", report)

    def test_generate_all_failed_analyses(self):
        """测试所有分析都失败的情况"""
        failed_analyses = [
            {"success": False, "sql": "SQL1", "error": "错误1"},
            {"success": False, "sql": "SQL2", "error": "错误2"}
        ]
        report = self.generator.generate(
            failed_analyses,
            report_format="text",
            include_fixes=True
        )

        self.assertIsInstance(report, str)
        self.assertIn("分析SQL数量: 2", report)
        self.assertIn("发现问题总数: 0", report)

    def test_generate_invalid_format(self):
        """测试无效格式（默认使用text）"""
        report = self.generator.generate(
            self.sample_analyses,
            report_format="invalid",
            include_fixes=True
        )

        self.assertIsInstance(report, str)
        # 应该使用默认的text格式
        self.assertIn("数据库SQL优化报告", report)

    def test_text_report_structure(self):
        """测试文本报告结构完整性"""
        report = self.generator.generate(
            self.sample_analyses,
            report_format="text",
            include_fixes=True
        )

        # 检查报告包含所有必要部分
        self.assertIn("=" * 70, report)  # 分隔线
        self.assertIn("按表汇总:", report)
        self.assertIn("[users]:", report)
        self.assertIn("可执行的索引创建语句:", report)
        self.assertIn("CREATE INDEX", report)

    def test_markdown_report_structure(self):
        """测试Markdown报告结构完整性"""
        report = self.generator.generate(
            self.sample_analyses,
            report_format="markdown",
            include_fixes=True
        )

        # 检查Markdown格式
        self.assertIn("# 数据库SQL优化报告", report)
        self.assertIn("## 摘要", report)
        self.assertIn("## 详细分析", report)
        self.assertIn("### SQL 1", report)
        self.assertIn("**类型**:", report)
        self.assertIn("**问题**:", report)
        self.assertIn("**索引建议**:", report)

    def test_json_report_structure(self):
        """测试JSON报告结构完整性"""
        report = self.generator.generate(
            self.sample_analyses,
            report_format="json",
            include_fixes=True
        )

        data = json.loads(report)

        # 检查summary结构
        self.assertIn("total_sql", data["summary"])
        self.assertIn("total_issues", data["summary"])
        self.assertIn("critical", data["summary"])
        self.assertIn("high", data["summary"])

        # 检查details结构
        self.assertEqual(len(data["details"]), 3)


# =============================================================================
# 主程序入口
# =============================================================================

if __name__ == "__main__":
    # 运行测试
    unittest.main(verbosity=2)
