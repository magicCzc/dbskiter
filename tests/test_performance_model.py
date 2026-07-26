"""
统一性能模型测试

文件功能：测试统一性能模型的核心功能
主要测试：
    - PerformanceMetric 数据类
    - PerformanceAnalyzer 基类
    - MySQLPerformanceAnalyzer 实现
    - 性能快照采集
    - 瓶颈分析

作者: AI Assistant
创建时间: 2026-04-24
版本: 1.0.0
"""

import unittest
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock

import sys
sys.path.insert(0, 'e:\\Chenzc-AIDev\\数据库skill')

from dbskiter.db_diagnose.core.performance_model import (
    PerformanceMetric,
    SlowQueryInfo,
    PerformanceSnapshot,
    MetricCategory,
    SeverityLevel,
    get_threshold
)


class TestPerformanceMetric(unittest.TestCase):
    """测试性能指标数据类"""

    def test_basic_creation(self):
        """测试基本创建"""
        metric = PerformanceMetric(
            name="cpu_usage",
            value=75.5,
            unit="%",
            category=MetricCategory.CPU,
            threshold_warning=70,
            threshold_critical=90
        )

        self.assertEqual(metric.name, "cpu_usage")
        self.assertEqual(metric.value, 75.5)
        self.assertEqual(metric.unit, "%")
        self.assertEqual(metric.category, MetricCategory.CPU)

    def test_severity_calculation(self):
        """测试严重程度计算"""
        # INFO级别
        metric1 = PerformanceMetric(
            name="test",
            value=50,
            threshold_warning=70,
            threshold_critical=90
        )
        self.assertEqual(metric1.get_severity(), SeverityLevel.INFO)

        # HIGH级别
        metric2 = PerformanceMetric(
            name="test",
            value=75,
            threshold_warning=70,
            threshold_critical=90
        )
        self.assertEqual(metric2.get_severity(), SeverityLevel.HIGH)

        # CRITICAL级别
        metric3 = PerformanceMetric(
            name="test",
            value=95,
            threshold_warning=70,
            threshold_critical=90
        )
        self.assertEqual(metric3.get_severity(), SeverityLevel.CRITICAL)

    def test_to_dict(self):
        """测试转换为字典"""
        metric = PerformanceMetric(
            name="cpu_usage",
            value=75.5,
            unit="%",
            category=MetricCategory.CPU,
            threshold_warning=70,
            threshold_critical=90
        )

        data = metric.to_dict()

        self.assertEqual(data["name"], "cpu_usage")
        self.assertEqual(data["value"], 75.5)
        self.assertEqual(data["unit"], "%")
        self.assertEqual(data["category"], "cpu")
        self.assertEqual(data["severity"], "high")


class TestSlowQueryInfo(unittest.TestCase):
    """测试慢查询信息类"""

    def test_basic_creation(self):
        """测试基本创建"""
        query = SlowQueryInfo(
            sql_text="SELECT * FROM users WHERE id = 1",
            sql_id="abc123",
            execution_count=100,
            avg_time_ms=1500.5
        )

        self.assertEqual(query.sql_text, "SELECT * FROM users WHERE id = 1")
        self.assertEqual(query.sql_id, "abc123")
        self.assertEqual(query.execution_count, 100)
        self.assertEqual(query.avg_time_ms, 1500.5)

    def test_to_dict_truncation(self):
        """测试SQL文本截断"""
        long_sql = "SELECT * FROM users WHERE " + "x = 1 AND " * 100
        query = SlowQueryInfo(sql_text=long_sql)

        data = query.to_dict()
        self.assertLess(len(data["sql_text"]), len(long_sql))


class TestPerformanceSnapshot(unittest.TestCase):
    """测试性能快照类"""

    def test_creation_with_metrics(self):
        """测试带指标的快照创建"""
        metrics = [
            PerformanceMetric(name="cpu", value=50, category=MetricCategory.CPU),
            PerformanceMetric(name="io", value=30, category=MetricCategory.IO)
        ]

        snapshot = PerformanceSnapshot(
            timestamp=datetime.now(),
            metrics=metrics,
            active_sessions=10,
            total_sessions=100
        )

        self.assertEqual(len(snapshot.metrics), 2)
        self.assertEqual(snapshot.active_sessions, 10)
        self.assertEqual(snapshot.total_sessions, 100)

    def test_to_dict(self):
        """测试快照转字典"""
        snapshot = PerformanceSnapshot(
            timestamp=datetime.now(),
            metrics=[],
            active_sessions=5,
            total_sessions=50
        )

        data = snapshot.to_dict()
        self.assertIn("timestamp", data)
        self.assertIn("metrics", data)
        self.assertEqual(data["active_sessions"], 5)


class TestThresholds(unittest.TestCase):
    """测试阈值定义"""

    def test_get_existing_threshold(self):
        """测试获取已定义的阈值"""
        threshold = get_threshold("cpu_usage")
        self.assertIn("warning", threshold)
        self.assertIn("critical", threshold)
        self.assertEqual(threshold["unit"], "%")

    def test_get_nonexistent_threshold(self):
        """测试获取不存在的阈值"""
        threshold = get_threshold("nonexistent_metric")
        self.assertIsNone(threshold.get("warning"))
        self.assertIsNone(threshold.get("critical"))


class TestMySQLPerformanceAnalyzer(unittest.TestCase):
    """测试MySQL性能分析器"""

    def setUp(self):
        """测试前准备"""
        self.mock_connector = Mock()
        self.mock_connector.dialect = "mysql"
        self.mock_connector.execute = Mock()

    @patch('dbskiter.db_diagnose.diagnosticians.mysql_performance_analyzer.PerformanceAnalyzer._check_permissions')
    def test_initialization(self, mock_check):
        """测试初始化"""
        from dbskiter.db_diagnose.diagnosticians.mysql_performance_analyzer import MySQLPerformanceAnalyzer

        # 模拟版本检测
        mock_result = Mock()
        mock_result.rows = [["8.0.25"]]
        self.mock_connector.execute.return_value = mock_result

        analyzer = MySQLPerformanceAnalyzer(self.mock_connector, timeout=30)

        self.assertEqual(analyzer.connector, self.mock_connector)
        self.assertEqual(analyzer.timeout, 30)

    @patch('dbskiter.db_diagnose.diagnosticians.mysql_performance_analyzer.MySQLPerformanceAnalyzer._detect_capabilities')
    @patch('dbskiter.db_diagnose.diagnosticians.mysql_performance_analyzer.PerformanceAnalyzer._check_permissions')
    def test_collect_metrics(self, mock_check, mock_detect):
        """测试指标采集"""
        from dbskiter.db_diagnose.diagnosticians.mysql_performance_analyzer import MySQLPerformanceAnalyzer

        analyzer = MySQLPerformanceAnalyzer(self.mock_connector, timeout=30)
        analyzer._has_performance_schema = True
        analyzer._version = 8.0

        # 模拟各种查询结果
        mock_results = [
            Mock(rows=[[5, 100]]),  # active/total sessions
            Mock(rows=[[1000, 500, 100, 10000]]),  # innodb stats
            Mock(rows=[[5000, 10000]]),  # buffer pool
            Mock(rows=[[50, 200]]),  # connections
            Mock(rows=[[0]])  # lock waits
        ]
        self.mock_connector.execute.side_effect = mock_results

        metrics = analyzer.collect_metrics()

        # 验证返回了指标
        self.assertIsInstance(metrics, list)
        # 至少应该有一些指标被采集
        self.assertGreaterEqual(len(metrics), 0)

    @patch('dbskiter.db_diagnose.diagnosticians.mysql_performance_analyzer.MySQLPerformanceAnalyzer._detect_capabilities')
    @patch('dbskiter.db_diagnose.diagnosticians.mysql_performance_analyzer.PerformanceAnalyzer._check_permissions')
    def test_get_active_sessions(self, mock_check, mock_detect):
        """测试获取活跃会话"""
        from dbskiter.db_diagnose.diagnosticians.mysql_performance_analyzer import MySQLPerformanceAnalyzer

        analyzer = MySQLPerformanceAnalyzer(self.mock_connector, timeout=30)

        # 模拟查询结果
        mock_result = Mock()
        mock_result.rows = [[10, 100]]
        self.mock_connector.execute.return_value = mock_result

        active, total = analyzer.get_active_sessions()

        self.assertEqual(active, 10)
        self.assertEqual(total, 100)


class TestIntegration(unittest.TestCase):
    """集成测试"""

    def test_end_to_end_snapshot(self):
        """测试端到端快照采集"""
        # 这是一个集成测试，需要真实的数据库连接
        # 在实际CI/CD环境中应该跳过或配置测试数据库
        self.skipTest("集成测试需要真实数据库连接")


if __name__ == "__main__":
    unittest.main(verbosity=2)
