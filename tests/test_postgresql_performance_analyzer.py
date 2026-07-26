"""
PostgreSQL性能分析器测试

文件功能：测试PostgreSQL性能分析器的核心功能
主要测试：
    - PostgreSQLPerformanceAnalyzer 初始化
    - 能力检测（pg_stat_statements/pg_stat_kcache）
    - 指标采集
    - 慢查询采集
    - 降级机制

作者: AI Assistant
创建时间: 2026-04-24
版本: 1.0.0
"""

import unittest
from unittest.mock import Mock, patch

import sys
sys.path.insert(0, 'e:\\Chenzc-AIDev\\数据库skill')

from dbskiter.db_diagnose.diagnosticians.postgresql_performance_analyzer import PostgreSQLPerformanceAnalyzer
from dbskiter.db_diagnose.core.performance_model import MetricCategory


class TestPostgreSQLPerformanceAnalyzer(unittest.TestCase):
    """测试PostgreSQL性能分析器"""

    def setUp(self):
        """测试前准备"""
        self.mock_connector = Mock()
        self.mock_connector.dialect = "postgresql"
        self.mock_connector.execute = Mock()

    @patch('dbskiter.db_diagnose.diagnosticians.postgresql_performance_analyzer.PerformanceAnalyzer._check_permissions')
    def test_initialization(self, mock_check):
        """测试初始化"""
        # 模拟版本检测
        mock_results = [
            Mock(rows=[["PostgreSQL 14.2 on x86_64-pc-linux-gnu"]]),
            Mock(rows=[[1]]),  # pg_stat_statements可用
            Mock(rows=[[0]]),  # pg_stat_kcache不可用
        ]
        self.mock_connector.execute.side_effect = mock_results

        analyzer = PostgreSQLPerformanceAnalyzer(self.mock_connector, timeout=30)

        self.assertEqual(analyzer.connector, self.mock_connector)
        self.assertEqual(analyzer.timeout, 30)
        self.assertEqual(analyzer._version, "14.2")

    @patch('dbskiter.db_diagnose.diagnosticians.postgresql_performance_analyzer.PerformanceAnalyzer._check_permissions')
    def test_pg_stat_statements_detection(self, mock_check):
        """测试pg_stat_statements检测"""
        mock_results = [
            Mock(rows=[["PostgreSQL 14.2"]]),
            Mock(rows=[[1]]),  # 可用
            Mock(rows=[[0]]),  # kcache不可用
        ]
        self.mock_connector.execute.side_effect = mock_results

        analyzer = PostgreSQLPerformanceAnalyzer(self.mock_connector, timeout=30)

        self.assertTrue(analyzer._has_pg_stat_statements)
        self.assertFalse(analyzer._has_pg_stat_kcache)

    @patch('dbskiter.db_diagnose.diagnosticians.postgresql_performance_analyzer.PerformanceAnalyzer._check_permissions')
    def test_collect_cpu_metrics(self, mock_check):
        """测试CPU指标采集"""
        analyzer = PostgreSQLPerformanceAnalyzer(self.mock_connector, timeout=30)
        analyzer._has_pg_stat_kcache = False
        analyzer._version = "14.2"

        # 模拟活跃会话查询
        mock_result = Mock()
        mock_result.rows = [[5, 100]]
        self.mock_connector.execute.return_value = mock_result

        metrics = analyzer._collect_cpu_metrics()

        self.assertIsInstance(metrics, list)
        self.assertTrue(any(m.name == "active_session_ratio" for m in metrics))
        self.assertEqual(metrics[0].category, MetricCategory.CPU)

    @patch('dbskiter.db_diagnose.diagnosticians.postgresql_performance_analyzer.PerformanceAnalyzer._check_permissions')
    def test_collect_io_metrics(self, mock_check):
        """测试IO指标采集"""
        analyzer = PostgreSQLPerformanceAnalyzer(self.mock_connector, timeout=30)

        # 模拟IO指标查询
        mock_result = Mock()
        mock_result.rows = [[98.5, 100, 10000, 0, 0]]
        self.mock_connector.execute.return_value = mock_result

        metrics = analyzer._collect_io_metrics()

        self.assertIsInstance(metrics, list)
        self.assertTrue(any(m.name == "buffer_cache_hit_ratio" for m in metrics))

    @patch('dbskiter.db_diagnose.diagnosticians.postgresql_performance_analyzer.PerformanceAnalyzer._check_permissions')
    def test_collect_concurrency_metrics(self, mock_check):
        """测试并发指标采集"""
        analyzer = PostgreSQLPerformanceAnalyzer(self.mock_connector, timeout=30)

        # 模拟并发指标查询
        mock_results = [
            Mock(rows=[[50, 200, 2]]),  # 连接统计
            Mock(rows=[[3, 45, 120.5]]),  # 事务统计
        ]
        self.mock_connector.execute.side_effect = mock_results

        metrics = analyzer._collect_concurrency_metrics()

        self.assertIsInstance(metrics, list)
        self.assertTrue(any(m.name == "connection_usage" for m in metrics))

    @patch('dbskiter.db_diagnose.diagnosticians.postgresql_performance_analyzer.PerformanceAnalyzer._check_permissions')
    def test_collect_lock_metrics(self, mock_check):
        """测试锁指标采集"""
        analyzer = PostgreSQLPerformanceAnalyzer(self.mock_connector, timeout=30)

        # 模拟锁指标查询
        mock_results = [
            Mock(rows=[[10, 2]]),  # 锁等待
            Mock(rows=[[0]]),  # 死锁
        ]
        self.mock_connector.execute.side_effect = mock_results

        metrics = analyzer._collect_lock_metrics()

        self.assertIsInstance(metrics, list)

    @patch('dbskiter.db_diagnose.diagnosticians.postgresql_performance_analyzer.PerformanceAnalyzer._check_permissions')
    def test_collect_slow_queries_with_pg_stat_statements(self, mock_check):
        """测试从pg_stat_statements采集慢查询"""
        analyzer = PostgreSQLPerformanceAnalyzer(self.mock_connector, timeout=30)
        analyzer._has_pg_stat_statements = True
        analyzer._version = "14.2"

        # 模拟pg_stat_statements慢查询
        mock_result = Mock()
        mock_result.rows = [
            [12345, 'SELECT * FROM users WHERE id = $1', 100, 150000.5, 1500.5, 5000.5, 100, 50],
        ]
        self.mock_connector.execute.return_value = mock_result

        queries = analyzer.collect_slow_queries(limit=10, min_time_ms=1000)

        self.assertIsInstance(queries, list)
        self.assertEqual(len(queries), 1)
        self.assertEqual(queries[0].sql_id, "12345")

    @patch('dbskiter.db_diagnose.diagnosticians.postgresql_performance_analyzer.PerformanceAnalyzer._check_permissions')
    def test_collect_slow_queries_fallback_to_activity(self, mock_check):
        """测试pg_stat_statements不可用时降级到pg_stat_activity"""
        analyzer = PostgreSQLPerformanceAnalyzer(self.mock_connector, timeout=30)
        analyzer._has_pg_stat_statements = False
        analyzer._version = "14.2"

        # 模拟pg_stat_activity慢查询
        mock_result = Mock()
        mock_result.rows = [
            [12345, 'postgres', '192.168.1.1', 'mydb', 'active', 2500.5, 'SELECT * FROM large_table'],
        ]
        self.mock_connector.execute.return_value = mock_result

        queries = analyzer.collect_slow_queries(limit=10, min_time_ms=1000)

        self.assertIsInstance(queries, list)
        self.assertEqual(len(queries), 1)

    @patch('dbskiter.db_diagnose.diagnosticians.postgresql_performance_analyzer.PerformanceAnalyzer._check_permissions')
    def test_get_active_sessions(self, mock_check):
        """测试获取活跃会话"""
        analyzer = PostgreSQLPerformanceAnalyzer(self.mock_connector, timeout=30)

        # 模拟会话查询
        mock_result = Mock()
        mock_result.rows = [[15, 100]]
        self.mock_connector.execute.return_value = mock_result

        active, total = analyzer.get_active_sessions()

        self.assertEqual(active, 15)
        self.assertEqual(total, 100)


class TestPostgreSQLPerformanceAnalyzerIntegration(unittest.TestCase):
    """PostgreSQL性能分析器集成测试"""

    def test_end_to_end(self):
        """测试端到端场景"""
        # 这是一个集成测试，需要真实的PostgreSQL数据库
        self.skipTest("集成测试需要真实PostgreSQL数据库")


if __name__ == "__main__":
    unittest.main(verbosity=2)
