"""
db_inspector/test_utils.py
db_inspector 工具类单元测试

测试范围:
    - HealthScoreCalculator 健康评分计算器
    - ReportFormatter 报告格式化器
    - BaselineManager 基线管理器
    - InspectionAggregator 巡检结果聚合器
    - TrendAnalyzer 趋势分析器

版本: 1.0.0
作者: AI Assistant
创建时间: 2026-04-23
"""

import unittest
from datetime import datetime, timedelta

from dbskiter.db_inspector.utils import (
    HealthScoreCalculator,
    ReportFormatter,
    BaselineManager,
    InspectionAggregator,
    TrendAnalyzer,
)
from dbskiter.db_inspector.models import (
    RiskLevel,
    InspectionType,
    InspectionItem,
    InspectionReport,
)


class TestHealthScoreCalculator(unittest.TestCase):
    """测试健康评分计算器"""

    def test_calculate_score_no_issues(self):
        """测试无问题评分"""
        calculator = HealthScoreCalculator()
        items = []
        score = calculator.calculate_score(items)

        self.assertEqual(score, 100.0)

    def test_calculate_score_with_critical(self):
        """测试有严重问题评分"""
        calculator = HealthScoreCalculator()
        items = [
            InspectionItem(
                name="test",
                inspection_type=InspectionType.CONFIGURATION,
                risk_level=RiskLevel.CRITICAL,
                status="fail",
                description="测试"
            )
        ]
        score = calculator.calculate_score(items)

        # CRITICAL: 12分基准, fail状态1.0系数, CONFIGURATION权重0.20
        # 实际扣分 = 12 * 1.0 = 12分 (在分类上限18分内)
        self.assertEqual(score, 88.0)  # 100 - 12

    def test_calculate_category_score(self):
        """测试类别评分"""
        calculator = HealthScoreCalculator()
        items = [
            InspectionItem(
                name="test1",
                inspection_type=InspectionType.PERFORMANCE,
                risk_level=RiskLevel.HIGH,
                status="warning",
                description="测试"
            ),
            InspectionItem(
                name="test2",
                inspection_type=InspectionType.CONFIGURATION,
                risk_level=RiskLevel.LOW,
                status="pass",
                description="测试"
            )
        ]

        perf_score = calculator.calculate_category_score(items, InspectionType.PERFORMANCE)
        config_score = calculator.calculate_category_score(items, InspectionType.CONFIGURATION)

        # HIGH: 6分基准, warning状态0.7系数, PERFORMANCE权重0.30
        # 实际扣分 = 6 * 0.7 = 4.2分
        self.assertAlmostEqual(perf_score, 95.8, places=1)  # 100 - 4.2
        self.assertEqual(config_score, 100.0)  # 无问题

    def test_get_score_grade(self):
        """测试评分等级"""
        calculator = HealthScoreCalculator()

        self.assertEqual(calculator.get_score_grade(95), "healthy")
        self.assertEqual(calculator.get_score_grade(85), "subhealthy")
        self.assertEqual(calculator.get_score_grade(70), "risk")
        self.assertEqual(calculator.get_score_grade(50), "danger")
        self.assertEqual(calculator.get_score_grade(30), "danger")


class TestReportFormatter(unittest.TestCase):
    """测试报告格式化器"""

    def test_format_html(self):
        """测试HTML格式化"""
        report = InspectionReport(
            report_id="test-001",
            instance_name="test-db",
            database_type="mysql",
            database_version="8.0",
            inspection_time=datetime.now(),
            duration_seconds=10.0,
            health_score=85.0
        )

        html = ReportFormatter.format_html(report)

        self.assertIn("<!DOCTYPE html>", html)
        self.assertIn("test-db", html)
        self.assertIn("85.0", html)

    def test_format_markdown(self):
        """测试Markdown格式化"""
        report = InspectionReport(
            report_id="test-001",
            instance_name="test-db",
            database_type="mysql",
            database_version="8.0",
            inspection_time=datetime.now(),
            duration_seconds=10.0,
            health_score=85.0
        )

        md = ReportFormatter.format_markdown(report)

        self.assertIn("# 数据库巡检报告", md)
        self.assertIn("test-db", md)

    def test_format_json(self):
        """测试JSON格式化"""
        report = InspectionReport(
            report_id="test-001",
            instance_name="test-db",
            database_type="mysql",
            database_version="8.0",
            inspection_time=datetime.now(),
            duration_seconds=10.0
        )

        json_str = ReportFormatter.format_json(report)

        self.assertIn("test-001", json_str)
        self.assertIn("test-db", json_str)


class TestBaselineManager(unittest.TestCase):
    """测试基线管理器"""

    def test_create_baseline(self):
        """测试创建基线"""
        manager = BaselineManager()
        report = InspectionReport(
            report_id="test-001",
            instance_name="test-db",
            database_type="mysql",
            database_version="8.0",
            inspection_time=datetime.now(),
            duration_seconds=10.0,
            health_score=90.0
        )

        baseline = manager.create_baseline(report, "test_baseline")

        self.assertIsNotNone(baseline.baseline_id)
        self.assertEqual(baseline.instance_name, "test-db")

    def test_get_baseline(self):
        """测试获取基线"""
        manager = BaselineManager()
        report = InspectionReport(
            report_id="test-001",
            instance_name="test-db",
            database_type="mysql",
            database_version="8.0",
            inspection_time=datetime.now(),
            duration_seconds=10.0
        )

        baseline = manager.create_baseline(report)
        retrieved = manager.get_baseline(baseline.baseline_id)

        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.baseline_id, baseline.baseline_id)

    def test_list_baselines(self):
        """测试列出基线"""
        manager = BaselineManager()
        report = InspectionReport(
            report_id="test-001",
            instance_name="test-db",
            database_type="mysql",
            database_version="8.0",
            inspection_time=datetime.now(),
            duration_seconds=10.0
        )

        manager.create_baseline(report, "baseline1")
        baselines = manager.list_baselines()

        self.assertEqual(len(baselines), 1)


class TestInspectionAggregator(unittest.TestCase):
    """测试巡检结果聚合器"""

    def test_aggregate_reports(self):
        """测试聚合报告"""
        reports = [
            InspectionReport(
                report_id="1",
                instance_name="db1",
                database_type="mysql",
                database_version="8.0",
                inspection_time=datetime.now(),
                duration_seconds=10.0,
                total_items=10,
                pass_count=8,
                warning_count=2
            ),
            InspectionReport(
                report_id="2",
                instance_name="db2",
                database_type="postgresql",
                database_version="14.0",
                inspection_time=datetime.now(),
                duration_seconds=15.0,
                total_items=12,
                pass_count=10,
                fail_count=2
            )
        ]

        aggregated = InspectionAggregator.aggregate_reports(reports)

        self.assertEqual(aggregated["total_reports"], 2)
        self.assertEqual(aggregated["total_items"], 22)

    def test_get_top_issues(self):
        """测试获取Top问题"""
        report = InspectionReport(
            report_id="test-001",
            instance_name="test-db",
            database_type="mysql",
            database_version="8.0",
            inspection_time=datetime.now(),
            duration_seconds=10.0,
            items=[
                InspectionItem(
                    name="critical_issue",
                    inspection_type=InspectionType.CONFIGURATION,
                    risk_level=RiskLevel.CRITICAL,
                    status="fail",
                    description="严重问题"
                ),
                InspectionItem(
                    name="high_issue",
                    inspection_type=InspectionType.PERFORMANCE,
                    risk_level=RiskLevel.HIGH,
                    status="warning",
                    description="高危问题"
                ),
                InspectionItem(
                    name="low_issue",
                    inspection_type=InspectionType.SECURITY,
                    risk_level=RiskLevel.LOW,
                    status="pass",
                    description="低危问题"
                )
            ]
        )

        issues = InspectionAggregator.get_top_issues(report, limit=2)

        self.assertEqual(len(issues), 2)
        self.assertEqual(issues[0].name, "critical_issue")


class TestTrendAnalyzer(unittest.TestCase):
    """测试趋势分析器"""

    def test_analyze_score_trend_improving(self):
        """测试改善趋势"""
        reports = [
            InspectionReport(
                report_id="1",
                instance_name="test-db",
                database_type="mysql",
                database_version="8.0",
                inspection_time=datetime.now() - timedelta(days=2),
                duration_seconds=10.0,
                health_score=70.0
            ),
            InspectionReport(
                report_id="2",
                instance_name="test-db",
                database_type="mysql",
                database_version="8.0",
                inspection_time=datetime.now() - timedelta(days=1),
                duration_seconds=10.0,
                health_score=80.0
            ),
            InspectionReport(
                report_id="3",
                instance_name="test-db",
                database_type="mysql",
                database_version="8.0",
                inspection_time=datetime.now(),
                duration_seconds=10.0,
                health_score=90.0
            )
        ]

        trend = TrendAnalyzer.analyze_score_trend(reports)

        self.assertEqual(trend["trend"], "improving")
        self.assertEqual(trend["score_change"], 20.0)

    def test_analyze_score_trend_degrading(self):
        """测试恶化趋势"""
        reports = [
            InspectionReport(
                report_id="1",
                instance_name="test-db",
                database_type="mysql",
                database_version="8.0",
                inspection_time=datetime.now() - timedelta(days=2),
                duration_seconds=10.0,
                health_score=90.0
            ),
            InspectionReport(
                report_id="2",
                instance_name="test-db",
                database_type="mysql",
                database_version="8.0",
                inspection_time=datetime.now(),
                duration_seconds=10.0,
                health_score=75.0
            )
        ]

        trend = TrendAnalyzer.analyze_score_trend(reports)

        self.assertEqual(trend["trend"], "degrading")

    def test_detect_anomalies(self):
        """测试检测异常"""
        reports = [
            InspectionReport(
                report_id="1",
                instance_name="test-db",
                database_type="mysql",
                database_version="8.0",
                inspection_time=datetime.now() - timedelta(days=2),
                duration_seconds=10.0,
                health_score=85.0
            ),
            InspectionReport(
                report_id="2",
                instance_name="test-db",
                database_type="mysql",
                database_version="8.0",
                inspection_time=datetime.now(),
                duration_seconds=10.0,
                health_score=60.0  # 下降25分，超过阈值
            )
        ]

        anomalies = TrendAnalyzer.detect_anomalies(reports, threshold=15.0)

        self.assertEqual(len(anomalies), 1)
        self.assertEqual(anomalies[0]["type"], "degradation")


if __name__ == "__main__":
    unittest.main()
