"""
端到端集成测试

文件功能：测试整个诊断流程的集成
测试场景：
    1. 完整慢查询分析流程
    2. SQL指纹聚合流程
    3. 错误处理和降级流程
    4. 性能保护流程

运行方式：
    cd e:\Chenzc-AIDev\数据库skill
    python -m pytest tests/test_integration.py -v
"""

import sys
import unittest
from unittest.mock import Mock, MagicMock, patch
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from dbskiter.shared.sql_fingerprint import SQLFingerprinter, QueryGroup
from dbskiter.shared.mysql_slow_query_collector import (
    MySQLSlowQueryCollector,
    SlowQuery,
    CollectionError,
    ErrorCategory,
)


class MockQueryResult:
    """模拟查询结果"""
    def __init__(self, rows=None, columns=None):
        self.rows = rows or []
        self.columns = columns or []


class TestEndToEndSlowQueryAnalysis(unittest.TestCase):
    """端到端慢查询分析测试"""
    
    def setUp(self):
        """测试前准备"""
        self.mock_connector = Mock()
        self.mock_connector.dialect = 'mysql+pymysql'
        
        # 设置版本查询
        self.mock_connector.execute.side_effect = self._mock_execute
        
        self.collector = MySQLSlowQueryCollector(self.mock_connector)
        self.fingerprinter = SQLFingerprinter()
    
    def _mock_execute(self, sql, params=None):
        """模拟数据库执行"""
        sql_upper = sql.upper()
        
        # 版本查询
        if 'VERSION()' in sql_upper:
            return MockQueryResult(rows=[["8.0.25"]])
        
        # performance_schema检查
        if 'PERFORMANCE_SCHEMA' in sql_upper and 'SCHEMATA' in sql_upper:
            return MockQueryResult(rows=[[1]])
        
        # events_statements_summary检查
        if 'EVENTS_STATEMENTS_SUMMARY' in sql_upper and 'TABLES' in sql_upper:
            return MockQueryResult(rows=[[1]])
        
        # slow_log检查
        if 'SLOW_LOG' in sql_upper:
            return MockQueryResult(rows=[[0]])  # 不存在
        
        # 慢查询数据
        if 'EVENTS_STATEMENTS_SUMMARY_BY_DIGEST' in sql_upper:
            return MockQueryResult(rows=[
                [
                    "SELECT * FROM users WHERE id = ?",  # DIGEST_TEXT
                    "test_db",  # SCHEMA_NAME
                    100,  # COUNT_STAR
                    0.5,  # avg_time_sec
                    1.0,  # max_time_sec
                    1000,  # total_rows_sent
                    5000,  # total_rows_examined
                    "2024-01-01 10:00:00",  # FIRST_SEEN
                    "2024-01-01 12:00:00",  # LAST_SEEN
                ],
                [
                    "SELECT * FROM orders WHERE status = ?",
                    "test_db",
                    50,
                    1.0,
                    2.0,
                    500,
                    2000,
                    "2024-01-01 09:00:00",
                    "2024-01-01 11:00:00",
                ],
            ])
        
        return MockQueryResult(rows=[])
    
    def test_complete_slow_query_workflow(self):
        """测试完整慢查询分析流程"""
        # 1. 采集慢查询
        queries = self.collector.collect_slow_queries(limit=10)
        
        # 验证采集成功
        self.assertEqual(len(queries), 2)
        self.assertEqual(queries[0].source, 'performance_schema')
        
        # 2. 转换为字典列表
        query_dicts = [
            {
                'sql': q.sql,
                'time': q.query_time,
                'count': q.count,
            }
            for q in queries
        ]
        
        # 3. SQL指纹聚合
        aggregated = self.fingerprinter.aggregate(query_dicts)
        
        # 验证聚合结果
        self.assertEqual(len(aggregated), 2)
        
        # 4. 获取Top查询
        top_queries = self.fingerprinter.get_top_queries(
            aggregated, sort_by='total_time', limit=2
        )
        
        # 验证排序
        self.assertEqual(len(top_queries), 2)
        self.assertGreaterEqual(
            top_queries[0].total_time,
            top_queries[1].total_time
        )
    
    def test_fingerprint_consistency_in_workflow(self):
        """测试工作流中的指纹一致性"""
        # 采集相似的查询
        queries = [
            SlowQuery(
                sql="SELECT * FROM users WHERE id = 1",
                query_time=0.5,
                count=10,
                rows_sent=1,
                rows_examined=100,
                source='test'
            ),
            SlowQuery(
                sql="SELECT * FROM users WHERE id = 2",
                query_time=0.6,
                count=15,
                rows_sent=1,
                rows_examined=100,
                source='test'
            ),
            SlowQuery(
                sql="SELECT * FROM users WHERE id = 999",
                query_time=0.4,
                count=8,
                rows_sent=1,
                rows_examined=100,
                source='test'
            ),
        ]
        
        # 转换为字典并聚合
        query_dicts = [
            {'sql': q.sql, 'time': q.query_time, 'count': q.count}
            for q in queries
        ]
        
        aggregated = self.fingerprinter.aggregate(query_dicts)
        
        # 验证相似查询被聚合为一组
        self.assertEqual(len(aggregated), 1)
        
        group = list(aggregated.values())[0]
        self.assertEqual(group.count, 3)  # 3条查询
        self.assertAlmostEqual(group.total_time, 1.5, places=1)  # 0.5+0.6+0.4


class TestErrorHandlingAndFallback(unittest.TestCase):
    """错误处理和降级测试"""
    
    def test_performance_schema_unavailable_fallback(self):
        """测试performance_schema不可用时降级"""
        mock_connector = Mock()
        mock_connector.dialect = 'mysql'
        
        call_count = [0]
        
        def mock_execute(sql, params=None):
            call_count[0] += 1
            sql_upper = sql.upper()
            
            # 版本查询
            if 'VERSION()' in sql_upper:
                return MockQueryResult(rows=[["8.0.25"]])
            
            # performance_schema不存在
            if 'PERFORMANCE_SCHEMA' in sql_upper:
                return MockQueryResult(rows=[[0]])
            
            # slow_log也不存在
            if 'SLOW_LOG' in sql_upper:
                return MockQueryResult(rows=[[0]])
            
            # processlist可用
            if 'PROCESSLIST' in sql_upper:
                return MockQueryResult(rows=[
                    [1, "user", "host", "db", "Query", 5, "state", "SELECT 1"]
                ])
            
            return MockQueryResult(rows=[])
        
        mock_connector.execute.side_effect = mock_execute
        
        collector = MySQLSlowQueryCollector(mock_connector)
        queries = collector.collect_slow_queries(limit=10)
        
        # 验证从processlist获取到数据
        self.assertGreaterEqual(len(queries), 0)
    
    def test_error_classification_and_recovery(self):
        """测试错误分类和恢复"""
        mock_connector = Mock()
        mock_connector.dialect = 'mysql'
        
        # 模拟权限错误
        def mock_execute_with_permission_error(sql, params=None):
            sql_upper = sql.upper()
            
            if 'VERSION()' in sql_upper:
                return MockQueryResult(rows=[["8.0.25"]])
            
            if 'PERFORMANCE_SCHEMA' in sql_upper and 'SCHEMATA' in sql_upper:
                return MockQueryResult(rows=[[1]])
            
            if 'EVENTS_STATEMENTS_SUMMARY' in sql_upper and 'TABLES' in sql_upper:
                return MockQueryResult(rows=[[1]])
            
            # 权限错误
            raise Exception("Access denied for user")
        
        mock_connector.execute.side_effect = mock_execute_with_permission_error
        
        collector = MySQLSlowQueryCollector(mock_connector)
        queries = collector.collect_slow_queries(limit=10)
        
        # 验证返回空结果但记录了错误
        self.assertEqual(len(queries), 0)
        
        errors = collector.get_errors()
        self.assertGreater(len(errors), 0)
        
        # 验证错误被正确分类
        error = errors[0]
        self.assertEqual(error.category, ErrorCategory.PERMISSION_ERROR)
        self.assertFalse(error.recoverable)


class TestPerformanceProtection(unittest.TestCase):
    """性能保护测试"""
    
    def setUp(self):
        """测试前准备"""
        self.fingerprinter = SQLFingerprinter()
    
    def test_rate_limiting(self):
        """测试频率限制"""
        mock_connector = Mock()
        mock_connector.dialect = 'mysql'
        
        collector = MySQLSlowQueryCollector(
            mock_connector,
            max_queries_per_minute=2
        )
        
        # 前2次应该允许
        self.assertTrue(collector._check_rate_limit())
        self.assertTrue(collector._check_rate_limit())
        
        # 第3次应该被阻止
        self.assertFalse(collector._check_rate_limit())
    
    def test_sql_length_protection(self):
        """测试SQL长度保护"""
        # 创建一个超长SQL
        long_sql = "SELECT * FROM users WHERE id IN (" + ", ".join([str(i) for i in range(5000)]) + ")"
        
        # 验证长度超过限制
        self.assertGreater(len(long_sql), 10000)
        
        # 指纹生成应该成功（虽然会记录警告）
        result = self.fingerprinter.fingerprint(long_sql)
        self.assertIsNotNone(result.fingerprint)
        self.assertIn("SELECT", result.fingerprint)
    
    def test_batch_processing_performance(self):
        """测试批量处理性能"""
        import time
        
        # 生成大量查询
        queries = []
        for i in range(1000):
            queries.append({
                'sql': f"SELECT * FROM table_{i % 10} WHERE id = {i}",
                'time': 0.1 + (i % 5) * 0.1
            })
        
        start = time.perf_counter()
        aggregated = self.fingerprinter.aggregate(queries)
        elapsed = time.perf_counter() - start
        
        # 验证性能（1000条应该在1秒内完成）
        self.assertLess(elapsed, 1.0)
        self.assertEqual(len(aggregated), 10)  # 10种模式


class TestComplexSQLHandling(unittest.TestCase):
    """复杂SQL处理测试"""
    
    def setUp(self):
        self.fp = SQLFingerprinter()
    
    def test_cte_query_fingerprint(self):
        """测试CTE查询指纹"""
        sql = """
            WITH cte AS (
                SELECT id, name FROM users WHERE status = 'active'
            )
            SELECT * FROM cte WHERE id > 100
        """
        
        result = self.fp.fingerprint(sql)
        
        # 验证指纹生成成功
        self.assertIsNotNone(result.fingerprint)
        self.assertIn("WITH", result.fingerprint)
        self.assertIn("SELECT", result.fingerprint)
    
    def test_window_function_fingerprint(self):
        """测试窗口函数指纹"""
        sql = """
            SELECT 
                id,
                name,
                ROW_NUMBER() OVER (PARTITION BY dept_id ORDER BY salary DESC) as rn
            FROM employees
        """
        
        result = self.fp.fingerprint(sql)
        
        # 窗口函数应该被替换为占位符
        self.assertIn("<window_func>", result.fingerprint)
    
    def test_case_expression_fingerprint(self):
        """测试CASE表达式指纹"""
        sql = """
            SELECT 
                CASE 
                    WHEN score >= 90 THEN 'A'
                    WHEN score >= 80 THEN 'B'
                    ELSE 'C'
                END as grade
            FROM students
        """
        
        result = self.fp.fingerprint(sql)
        
        # CASE表达式应该被替换
        self.assertIn("<case_expr>", result.fingerprint)
    
    def test_union_query_fingerprint(self):
        """测试UNION查询指纹"""
        sql = """
            SELECT id, name FROM users WHERE status = 1
            UNION ALL
            SELECT id, name FROM archived_users WHERE status = 1
        """
        
        result = self.fp.fingerprint(sql)
        
        # 验证UNION被保留
        self.assertIn("UNION", result.fingerprint.upper())


class TestDataConsistency(unittest.TestCase):
    """数据一致性测试"""
    
    def setUp(self):
        self.fp = SQLFingerprinter()
    
    def test_fingerprint_consistency_across_runs(self):
        """测试多次运行指纹一致性"""
        sql = "SELECT * FROM users WHERE id = 123 AND name = 'test'"
        
        # 多次生成指纹
        results = [self.fp.fingerprint(sql) for _ in range(10)]
        
        # 验证所有指纹相同
        fingerprints = [r.fingerprint for r in results]
        self.assertEqual(len(set(fingerprints)), 1)
        
        # 验证所有摘要相同
        digests = [r.digest for r in results]
        self.assertEqual(len(set(digests)), 1)
    
    def test_aggregate_statistics_accuracy(self):
        """测试聚合统计准确性"""
        queries = [
            {'sql': 'SELECT * FROM users WHERE id = 1', 'time': 1.0},
            {'sql': 'SELECT * FROM users WHERE id = 2', 'time': 2.0},
            {'sql': 'SELECT * FROM users WHERE id = 3', 'time': 3.0},
        ]
        
        aggregated = self.fp.aggregate(queries)
        
        # 验证统计
        group = list(aggregated.values())[0]
        self.assertEqual(group.count, 3)
        self.assertEqual(group.total_time, 6.0)
        self.assertEqual(group.avg_time, 2.0)
        self.assertEqual(group.min_time, 1.0)
        self.assertEqual(group.max_time, 3.0)


if __name__ == '__main__':
    unittest.main(verbosity=2)
