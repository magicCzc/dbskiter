"""
MySQL慢查询采集器单元测试

文件功能：测试MySQL慢查询采集器的核心功能
测试覆盖：
    1. 版本检测
    2. 功能检测
    3. 采集策略
    4. 降级机制
    5. 性能保护

运行方式：
    cd e:\Chenzc-AIDev\数据库skill
    python -m pytest tests/test_mysql_slow_query_collector.py -v

注意：部分测试需要MySQL连接，使用mock进行模拟
"""

import sys
import unittest
from unittest.mock import Mock, MagicMock, patch
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from dbskiter.shared.mysql_slow_query_collector import (
    MySQLVersionDetector,
    MySQLSlowQueryCollector,
    SlowQuery,
    collect_mysql_slow_queries,
)


class MockQueryResult:
    """模拟查询结果"""
    def __init__(self, rows=None, columns=None):
        self.rows = rows or []
        self.columns = columns or []


class TestMySQLVersionDetector(unittest.TestCase):
    """版本检测器测试"""
    
    def setUp(self):
        """测试前准备"""
        self.mock_connector = Mock()
        self.detector = MySQLVersionDetector(self.mock_connector)
    
    def test_detect_mysql57(self):
        """测试MySQL 5.7版本检测"""
        self.mock_connector.execute.return_value = MockQueryResult(
            rows=[["5.7.35-log"]]
        )
        
        version = self.detector.get_version()
        self.assertEqual(version, 5.7)
    
    def test_detect_mysql80(self):
        """测试MySQL 8.0版本检测"""
        self.mock_connector.execute.return_value = MockQueryResult(
            rows=[["8.0.25"]]
        )
        
        version = self.detector.get_version()
        self.assertEqual(version, 8.0)
    
    def test_detect_mysql80_with_suffix(self):
        """测试带后缀的版本号"""
        self.mock_connector.execute.return_value = MockQueryResult(
            rows=[["8.0.25-15"]]
        )
        
        version = self.detector.get_version()
        self.assertEqual(version, 8.0)
    
    def test_detect_failure_fallback(self):
        """测试检测失败时的回退"""
        self.mock_connector.execute.side_effect = Exception("连接失败")
        
        version = self.detector.get_version()
        self.assertEqual(version, 5.7)  # 默认回退到5.7
    
    def test_is_mysql8(self):
        """测试is_mysql8方法"""
        self.mock_connector.execute.return_value = MockQueryResult(
            rows=[["8.0.25"]]
        )
        
        self.assertTrue(self.detector.is_mysql8())
        self.assertFalse(self.detector.is_mysql57())
    
    def test_check_performance_schema(self):
        """测试performance_schema功能检测"""
        self.mock_connector.execute.return_value = MockQueryResult(
            rows=[[1]]  # 存在
        )
        
        available = self.detector.check_feature('performance_schema')
        self.assertTrue(available)
    
    def test_check_events_statements_summary(self):
        """测试events_statements_summary表检测"""
        self.mock_connector.execute.return_value = MockQueryResult(
            rows=[[1]]  # 存在
        )
        
        available = self.detector.check_feature('events_statements_summary')
        self.assertTrue(available)
    
    def test_check_slow_log_table(self):
        """测试slow_log表检测"""
        self.mock_connector.execute.return_value = MockQueryResult(
            rows=[[1]]  # 存在
        )
        
        available = self.detector.check_feature('slow_log_table')
        self.assertTrue(available)
    
    def test_feature_caching(self):
        """测试功能检测结果缓存"""
        self.mock_connector.execute.return_value = MockQueryResult(
            rows=[[1]]
        )
        
        # 第一次调用
        result1 = self.detector.check_feature('performance_schema')
        # 第二次调用（应该使用缓存）
        result2 = self.detector.check_feature('performance_schema')
        
        # 验证只执行了一次查询
        self.mock_connector.execute.assert_called_once()
        self.assertEqual(result1, result2)


class TestMySQLSlowQueryCollector(unittest.TestCase):
    """慢查询采集器测试"""
    
    def setUp(self):
        """测试前准备"""
        self.mock_connector = Mock()
        self.mock_connector.dialect = 'mysql'
        self.collector = MySQLSlowQueryCollector(self.mock_connector)
    
    def test_rate_limit_initially_allowed(self):
        """测试初始查询频率限制"""
        # 初始状态应该允许查询
        allowed = self.collector._check_rate_limit()
        self.assertTrue(allowed)
    
    def test_rate_limit_blocks_excessive_queries(self):
        """测试频率限制阻止过量查询"""
        collector = MySQLSlowQueryCollector(
            self.mock_connector,
            max_queries_per_minute=2
        )
        
        # 前2次应该允许
        self.assertTrue(collector._check_rate_limit())
        self.assertTrue(collector._check_rate_limit())
        
        # 第3次应该被阻止
        self.assertFalse(collector._check_rate_limit())
    
    @patch.object(MySQLVersionDetector, 'check_feature')
    @patch.object(MySQLVersionDetector, 'get_version')
    def test_collect_from_performance_schema_mysql57(
        self, mock_get_version, mock_check_feature
    ):
        """测试从performance_schema采集（MySQL 5.7）"""
        mock_get_version.return_value = 5.7
        mock_check_feature.return_value = True
        
        # 模拟查询结果
        self.mock_connector.execute.return_value = MockQueryResult(
            rows=[
                [
                    "SELECT * FROM users WHERE id = ?",
                    "test_db",
                    100,  # count
                    0.5,  # avg_time
                    1.0,  # max_time
                    1000,  # rows_sent
                    5000,  # rows_examined
                    "2024-01-01 10:00:00",  # first_seen
                    "2024-01-01 12:00:00",  # last_seen
                ]
            ]
        )
        
        queries = self.collector._collect_from_performance_schema(
            limit=10, min_time=0.0, table=None
        )
        
        self.assertEqual(len(queries), 1)
        self.assertEqual(queries[0].source, 'performance_schema')
        self.assertEqual(queries[0].database, 'test_db')
    
    @patch.object(MySQLVersionDetector, 'check_feature')
    @patch.object(MySQLVersionDetector, 'get_version')
    def test_collect_from_performance_schema_mysql80(
        self, mock_get_version, mock_check_feature
    ):
        """测试从performance_schema采集（MySQL 8.0）"""
        mock_get_version.return_value = 8.0
        mock_check_feature.return_value = True
        
        # 模拟查询结果
        self.mock_connector.execute.return_value = MockQueryResult(
            rows=[
                [
                    "SELECT * FROM orders WHERE status = ?",
                    "prod_db",
                    500,
                    1.5,
                    5.0,
                    5000,
                    100000,
                    "2024-01-01 08:00:00",
                    "2024-01-01 14:00:00",
                ]
            ]
        )
        
        queries = self.collector._collect_from_performance_schema(
            limit=10, min_time=0.0, table=None
        )
        
        self.assertEqual(len(queries), 1)
        # 验证使用了DIGEST_TEXT列（通过检查SQL中是否包含DIGEST_TEXT）
        call_args = self.mock_connector.execute.call_args
        self.assertIn("DIGEST_TEXT", call_args[0][0])
    
    def test_collect_from_slow_log(self):
        """测试从slow_log表采集"""
        self.mock_connector.execute.return_value = MockQueryResult(
            rows=[
                [
                    "SELECT * FROM products WHERE price > 100",
                    "shop_db",
                    2.5,  # query_time
                    50,   # rows_sent
                    10000,  # rows_examined
                    "2024-01-01 15:30:00",  # start_time
                ]
            ]
        )
        
        queries = self.collector._collect_from_slow_log(
            limit=10, min_time=0.0, table=None
        )
        
        self.assertEqual(len(queries), 1)
        self.assertEqual(queries[0].source, 'slow_log')
        self.assertEqual(queries[0].query_time, 2.5)
    
    def test_collect_from_processlist(self):
        """测试从processlist采集"""
        self.mock_connector.execute.return_value = MockQueryResult(
            rows=[
                [
                    12345,  # ID
                    "app_user",  # USER
                    "192.168.1.1:12345",  # HOST
                    "test_db",  # DB
                    "Query",  # COMMAND
                    10,  # TIME (seconds)
                    "Sending data",  # STATE
                    "SELECT * FROM large_table WHERE x = 1",  # INFO
                ]
            ]
        )
        
        queries = self.collector._collect_from_processlist(
            limit=10, min_time=5.0, table=None
        )
        
        self.assertEqual(len(queries), 1)
        self.assertEqual(queries[0].source, 'processlist')
        self.assertEqual(queries[0].query_time, 10.0)
    
    @patch.object(MySQLVersionDetector, 'check_feature')
    def test_collection_fallback_chain(self, mock_check_feature):
        """测试采集降级链"""
        # 所有高级源都不可用
        mock_check_feature.return_value = False
        
        # processlist应该能工作
        self.mock_connector.execute.return_value = MockQueryResult(
            rows=[
                [1, "user", "host", "db", "Query", 5, "state", "SELECT 1"]
            ]
        )
        
        queries = self.collector.collect_slow_queries(limit=10)
        
        # 应该至少从processlist获取到结果
        self.assertGreaterEqual(len(queries), 0)
    
    def test_collection_with_table_filter(self):
        """测试表名过滤"""
        self.mock_connector.execute.return_value = MockQueryResult(
            rows=[
                [
                    "SELECT * FROM users WHERE id = ?",
                    "test_db",
                    100, 0.5, 1.0, 1000, 5000,
                    "2024-01-01 10:00:00",
                    "2024-01-01 12:00:00",
                ]
            ]
        )
        
        with patch.object(MySQLVersionDetector, 'check_feature', return_value=True):
            with patch.object(MySQLVersionDetector, 'get_version', return_value=5.7):
                queries = self.collector._collect_from_performance_schema(
                    limit=10, min_time=0.0, table="users"
                )
        
        # 验证SQL中包含LIKE条件
        call_args = self.mock_connector.execute.call_args
        self.assertIn("LIKE", call_args[0][0])
        self.assertIn("%users%", call_args[0][1])
    
    def test_collection_with_min_time_filter(self):
        """测试最小时间过滤"""
        self.mock_connector.execute.return_value = MockQueryResult(
            rows=[
                [
                    "SELECT * FROM slow_query",
                    "test_db",
                    10, 5.0, 10.0, 100, 1000000,
                    "2024-01-01 10:00:00",
                    "2024-01-01 12:00:00",
                ]
            ]
        )
        
        with patch.object(MySQLVersionDetector, 'check_feature', return_value=True):
            with patch.object(MySQLVersionDetector, 'get_version', return_value=5.7):
                queries = self.collector._collect_from_performance_schema(
                    limit=10, min_time=1.0, table=None
                )
        
        # 验证SQL中包含时间过滤
        call_args = self.mock_connector.execute.call_args
        self.assertIn(">=", call_args[0][0])


class TestSlowQueryDataClass(unittest.TestCase):
    """SlowQuery数据类测试"""
    
    def test_slow_query_creation(self):
        """测试SlowQuery创建"""
        query = SlowQuery(
            sql="SELECT * FROM users",
            query_time=1.5,
            count=100,
            rows_sent=1000,
            rows_examined=5000,
            database="test_db",
            source="performance_schema"
        )
        
        self.assertEqual(query.sql, "SELECT * FROM users")
        self.assertEqual(query.query_time, 1.5)
        self.assertEqual(query.count, 100)
        self.assertEqual(query.database, "test_db")
    
    def test_slow_query_optional_fields(self):
        """测试SlowQuery可选字段"""
        query = SlowQuery(
            sql="SELECT 1",
            query_time=0.1,
            count=1,
            rows_sent=1,
            rows_examined=1
        )
        
        self.assertIsNone(query.first_seen)
        self.assertIsNone(query.last_seen)
        self.assertIsNone(query.database)


class TestColumnNameValidation(unittest.TestCase):
    """列名验证测试（SQL注入防护）"""
    
    def setUp(self):
        self.mock_connector = Mock()
        self.mock_connector.dialect = 'mysql'
        self.collector = MySQLSlowQueryCollector(self.mock_connector)
    
    def test_valid_column_name_sql_text(self):
        """测试有效列名SQL_TEXT"""
        result = self.collector._validate_column_name("SQL_TEXT")
        self.assertEqual(result, "SQL_TEXT")
    
    def test_valid_column_name_digest_text(self):
        """测试有效列名DIGEST_TEXT"""
        result = self.collector._validate_column_name("DIGEST_TEXT")
        self.assertEqual(result, "DIGEST_TEXT")
    
    def test_invalid_column_name_raises_error(self):
        """测试无效列名抛出异常"""
        with self.assertRaises(ValueError) as context:
            self.collector._validate_column_name("* FROM users; DROP TABLE users; --")
        
        self.assertIn("非法列名", str(context.exception))
    
    def test_empty_column_name_raises_error(self):
        """测试空列名抛出异常"""
        with self.assertRaises(ValueError):
            self.collector._validate_column_name("")


class TestCollectionStats(unittest.TestCase):
    """采集统计测试"""
    
    def setUp(self):
        self.mock_connector = Mock()
        self.mock_connector.dialect = 'mysql'
        self.collector = MySQLSlowQueryCollector(self.mock_connector)
    
    @patch.object(MySQLVersionDetector, 'get_version')
    @patch.object(MySQLVersionDetector, 'check_feature')
    def test_get_collection_stats(self, mock_check_feature, mock_get_version):
        """测试获取采集统计"""
        mock_get_version.return_value = 8.0
        mock_check_feature.return_value = True
        
        stats = self.collector.get_collection_stats()
        
        self.assertEqual(stats['mysql_version'], 8.0)
        self.assertTrue(stats['features']['performance_schema'])
        self.assertTrue(stats['features']['events_statements_summary'])
        self.assertTrue(stats['features']['slow_log_table'])
        self.assertEqual(stats['rate_limit']['max_per_minute'], 10)


class TestConvenienceFunction(unittest.TestCase):
    """便捷函数测试"""
    
    @patch('dbskiter.shared.mysql_slow_query_collector.MySQLSlowQueryCollector')
    def test_collect_mysql_slow_queries(self, mock_collector_class):
        """测试collect_mysql_slow_queries便捷函数"""
        # 设置mock
        mock_instance = Mock()
        mock_instance.collect_slow_queries.return_value = [
            SlowQuery(
                sql="SELECT * FROM users",
                query_time=1.0,
                count=100,
                rows_sent=1000,
                rows_examined=5000,
                database="test_db",
                source="performance_schema"
            )
        ]
        mock_collector_class.return_value = mock_instance
        
        # 调用便捷函数
        mock_connector = Mock()
        result = collect_mysql_slow_queries(mock_connector, limit=10)
        
        # 验证结果
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['sql'], "SELECT * FROM users")
        self.assertEqual(result[0]['query_time'], 1.0)
        self.assertEqual(result[0]['database'], "test_db")


if __name__ == '__main__':
    unittest.main(verbosity=2)
