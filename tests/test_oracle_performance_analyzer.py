"""
Oracle性能分析器测试

文件功能：测试Oracle性能分析器的核心功能
主要测试：
    - OraclePerformanceAnalyzer 初始化
    - 能力检测（AWR/ASH/RAC）
    - 指标采集
    - 慢查询采集
    - 降级机制

作者: AI Assistant
创建时间: 2026-04-24
版本: 1.0.0
"""

import unittest
from unittest.mock import Mock, patch, MagicMock

import sys
sys.path.insert(0, 'e:\\Chenzc-AIDev\\数据库skill')

from dbskiter.db_diagnose.diagnosticians.oracle_performance_analyzer import OraclePerformanceAnalyzer
from dbskiter.db_diagnose.core.performance_model import MetricCategory, SeverityLevel


class TestOraclePerformanceAnalyzer(unittest.TestCase):
    """测试Oracle性能分析器"""

    def setUp(self):
        """测试前准备"""
        self.mock_connector = Mock()
        self.mock_connector.dialect = "oracle"
        self.mock_connector.execute = Mock()

    @patch('dbskiter.db_diagnose.diagnosticians.oracle_performance_analyzer.PerformanceAnalyzer._check_permissions')
    def test_initialization(self, mock_check):
        """测试初始化"""
        # 模拟版本检测
        mock_result = Mock()
        mock_result.rows = [["Oracle Database 19c Enterprise Edition"]]
        self.mock_connector.execute.return_value = mock_result

        analyzer = OraclePerformanceAnalyzer(self.mock_connector, timeout=30)

        self.assertEqual(analyzer.connector, self.mock_connector)
        self.assertEqual(analyzer.timeout, 30)

    @patch('dbskiter.db_diagnose.diagnosticians.oracle_performance_analyzer.PerformanceAnalyzer._check_permissions')
    def test_awr_detection(self, mock_check):
        """测试AWR可用性检测"""
        # 模拟AWR可用
        mock_results = [
            Mock(rows=[["Oracle Database 19c"]]),  # 版本
            Mock(rows=[[1]]),  # AWR可用
            Mock(rows=[[1]]),  # ASH可用
            Mock(rows=[[1]]),  # 非RAC
        ]
        self.mock_connector.execute.side_effect = mock_results

        analyzer = OraclePerformanceAnalyzer(self.mock_connector, timeout=30)

        self.assertTrue(analyzer._has_awr)
        self.assertTrue(analyzer._has_ash)
        self.assertFalse(analyzer._is_rac)

    @patch('dbskiter.db_diagnose.diagnosticians.oracle_performance_analyzer.PerformanceAnalyzer._check_permissions')
    def test_awr_unavailable_fallback(self, mock_check):
        """测试AWR不可用时降级"""
        # 模拟AWR不可用
        mock_results = [
            Mock(rows=[["Oracle Database 19c"]]),  # 版本
            Exception("ORA-00942: table or view does not exist"),  # AWR不可用
            Mock(rows=[[1]]),  # ASH可用
            Mock(rows=[[1]]),  # 非RAC
        ]
        self.mock_connector.execute.side_effect = mock_results

        analyzer = OraclePerformanceAnalyzer(self.mock_connector, timeout=30)

        self.assertFalse(analyzer._has_awr)

    @patch('dbskiter.db_diagnose.diagnosticians.oracle_performance_analyzer.PerformanceAnalyzer._check_permissions')
    def test_collect_cpu_metrics(self, mock_check):
        """测试CPU指标采集"""
        analyzer = OraclePerformanceAnalyzer(self.mock_connector, timeout=30)
        analyzer._has_awr = True
        analyzer._version = "19c"

        # 模拟CPU指标查询
        mock_result = Mock()
        mock_result.rows = [
            ['DB time', 150.5],
            ['DB CPU', 120.3]
        ]
        self.mock_connector.execute.return_value = mock_result

        metrics = analyzer._collect_cpu_metrics()

        self.assertIsInstance(metrics, list)
        self.assertEqual(len(metrics), 2)
        self.assertEqual(metrics[0].name, "db_time_sec")
        self.assertEqual(metrics[0].category, MetricCategory.CPU)

    @patch('dbskiter.db_diagnose.diagnosticians.oracle_performance_analyzer.PerformanceAnalyzer._check_permissions')
    def test_collect_io_metrics(self, mock_check):
        """测试IO指标采集"""
        analyzer = OraclePerformanceAnalyzer(self.mock_connector, timeout=30)

        # 模拟IO指标查询
        mock_results = [
            Mock(rows=[[95.5]]),  # Buffer Cache命中率
            Mock(rows=[[1000, 500]]),  # 物理读写
        ]
        self.mock_connector.execute.side_effect = mock_results

        metrics = analyzer._collect_io_metrics()

        self.assertIsInstance(metrics, list)
        self.assertTrue(any(m.name == "buffer_cache_hit_ratio" for m in metrics))

    @patch('dbskiter.db_diagnose.diagnosticians.oracle_performance_analyzer.PerformanceAnalyzer._check_permissions')
    def test_collect_slow_queries_with_awr(self, mock_check):
        """测试从AWR采集慢查询"""
        analyzer = OraclePerformanceAnalyzer(self.mock_connector, timeout=30)
        analyzer._has_awr = True
        analyzer._version = "19c"

        # 模拟AWR慢查询
        mock_result = Mock()
        mock_result.rows = [
            ['sql1', 'SELECT * FROM users', 100, 150.5, 1.5, 120.3, 1000, 50, 100],
            ['sql2', 'SELECT * FROM orders', 50, 80.2, 1.6, 60.1, 500, 30, 50]
        ]
        self.mock_connector.execute.return_value = mock_result

        queries = analyzer.collect_slow_queries(limit=10, min_time_ms=1000)

        self.assertIsInstance(queries, list)
        self.assertEqual(len(queries), 2)
        self.assertEqual(queries[0].sql_id, 'sql1')

    @patch('dbskiter.db_diagnose.diagnosticians.oracle_performance_analyzer.PerformanceAnalyzer._check_permissions')
    def test_collect_slow_queries_fallback_to_vsql(self, mock_check):
        """测试AWR不可用时降级到V$SQL"""
        analyzer = OraclePerformanceAnalyzer(self.mock_connector, timeout=30)
        analyzer._has_awr = False
        analyzer._version = "19c"

        # 模拟V$SQL慢查询
        mock_result = Mock()
        mock_result.rows = [
            ['sql1', 'SELECT * FROM users', 100, 150500000, 120300000, 1000, 50, 100],
        ]
        self.mock_connector.execute.return_value = mock_result

        queries = analyzer.collect_slow_queries(limit=10, min_time_ms=1000)

        self.assertIsInstance(queries, list)
        self.assertEqual(len(queries), 1)

    @patch('dbskiter.db_diagnose.diagnosticians.oracle_performance_analyzer.PerformanceAnalyzer._check_permissions')
    def test_get_active_sessions(self, mock_check):
        """测试获取活跃会话"""
        analyzer = OraclePerformanceAnalyzer(self.mock_connector, timeout=30)

        # 模拟会话查询
        mock_result = Mock()
        mock_result.rows = [[10, 100]]
        self.mock_connector.execute.return_value = mock_result

        active, total = analyzer.get_active_sessions()

        self.assertEqual(active, 10)
        self.assertEqual(total, 100)

    @patch('dbskiter.db_diagnose.diagnosticians.oracle_performance_analyzer.PerformanceAnalyzer._check_permissions')
    def test_rac_detection(self, mock_check):
        """测试RAC环境检测"""
        # 模拟RAC环境
        mock_results = [
            Mock(rows=[["Oracle Database 19c"]]),  # 版本
            Mock(rows=[[1]]),  # AWR可用
            Mock(rows=[[1]]),  # ASH可用
            Mock(rows=[[3]]),  # RAC（3个实例）
        ]
        self.mock_connector.execute.side_effect = mock_results

        analyzer = OraclePerformanceAnalyzer(self.mock_connector, timeout=30)

        self.assertTrue(analyzer._is_rac)


class TestOraclePerformanceAnalyzerIntegration(unittest.TestCase):
    """Oracle性能分析器集成测试"""

    def test_end_to_end(self):
        """测试端到端场景"""
        # 这是一个集成测试，需要真实的Oracle数据库
        self.skipTest("集成测试需要真实Oracle数据库")


if __name__ == "__main__":
    unittest.main(verbosity=2)
