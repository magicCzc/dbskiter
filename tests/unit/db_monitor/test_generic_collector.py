"""
db_monitor/test_generic_collector.py
GenericMetricsCollector 单元测试

测试范围:
    - GenericMetricsCollector 初始化
    - 数据库能力探测
    - 连接数查询（多种数据库风格）
    - 表数量查询
    - 索引数量查询
    - 数据库大小查询
    - 指标采集流程

版本: 1.0.0
作者: AI Assistant
创建时间: 2026-06-05
"""

import unittest
from datetime import datetime
from unittest.mock import MagicMock, patch, call

from dbskiter.db_monitor.collectors.generic_collector import (
    GenericMetricsCollector, MetricType, MetricPoint
)


class MockResult:
    """模拟查询结果"""

    def __init__(self, rows=None):
        self.rows = rows or []


class TestGenericMetricsCollector(unittest.TestCase):
    """测试 GenericMetricsCollector"""

    def setUp(self):
        """测试前置：创建模拟连接器"""
        self.mock_connector = MagicMock()
        self.mock_connector.dialect = "trino"
        self.collector = GenericMetricsCollector(self.mock_connector)

    def test_init(self):
        """测试初始化"""
        self.assertEqual(self.collector.dialect, "trino")
        self.assertIsNone(self.collector._capabilities)
        self.assertIsNone(self.collector._metadata_cache)

    def test_detect_capabilities_information_schema(self):
        """测试探测 INFORMATION_SCHEMA 支持"""
        # 模拟只支持 INFORMATION_SCHEMA
        self.mock_connector.execute.side_effect = [
            MockResult([(1,)]),  # INFORMATION_SCHEMA 测试成功
            Exception("not found"),  # pg_stat_activity 失败
            Exception("not found"),  # performance_schema 失败
            Exception("not found"),  # v$session 失败
            Exception("not found"),  # sys.dm_exec_sessions 失败
            Exception("not found"),  # PRAGMA 失败
        ]

        caps = self.collector._detect_capabilities()

        self.assertTrue(caps["information_schema"])
        self.assertFalse(caps["pg_stat_activity"])
        self.assertFalse(caps["performance_schema"])
        self.assertFalse(caps["v$session"])
        self.assertFalse(caps["sys.dm_exec_sessions"])
        self.assertFalse(caps["pragma"])

    def test_detect_capabilities_postgresql(self):
        """测试探测 PostgreSQL 风格支持"""
        self.mock_connector.execute.side_effect = [
            Exception("not found"),  # INFORMATION_SCHEMA 失败
            MockResult([(1,)]),  # pg_stat_activity 成功
            Exception("not found"),  # performance_schema 失败
            Exception("not found"),  # v$session 失败
            Exception("not found"),  # sys.dm_exec_sessions 失败
            Exception("not found"),  # PRAGMA 失败
        ]

        caps = self.collector._detect_capabilities()

        self.assertFalse(caps["information_schema"])
        self.assertTrue(caps["pg_stat_activity"])

    def test_detect_capabilities_mysql(self):
        """测试探测 MySQL 风格支持"""
        self.mock_connector.execute.side_effect = [
            Exception("not found"),  # INFORMATION_SCHEMA 失败
            Exception("not found"),  # pg_stat_activity 失败
            MockResult([(1,)]),  # performance_schema 成功
            Exception("not found"),  # v$session 失败
            Exception("not found"),  # sys.dm_exec_sessions 失败
            Exception("not found"),  # PRAGMA 失败
        ]

        caps = self.collector._detect_capabilities()

        self.assertFalse(caps["information_schema"])
        self.assertFalse(caps["pg_stat_activity"])
        self.assertTrue(caps["performance_schema"])

    def test_detect_capabilities_sqlite(self):
        """测试探测 SQLite PRAGMA 支持"""
        self.mock_connector.execute.side_effect = [
            Exception("not found"),  # INFORMATION_SCHEMA 失败
            Exception("not found"),  # pg_stat_activity 失败
            Exception("not found"),  # performance_schema 失败
            Exception("not found"),  # v$session 失败
            Exception("not found"),  # sys.dm_exec_sessions 失败
            MockResult([(1000,)]),  # PRAGMA 成功
        ]

        caps = self.collector._detect_capabilities()

        self.assertFalse(caps["information_schema"])
        self.assertTrue(caps["pragma"])

    def test_detect_capabilities_caching(self):
        """测试能力探测结果缓存"""
        # 第一次探测
        self.mock_connector.execute.side_effect = [
            MockResult([(1,)]),  # INFORMATION_SCHEMA
            Exception("not found"),
            Exception("not found"),
            Exception("not found"),
            Exception("not found"),
            Exception("not found"),
        ]

        caps1 = self.collector._detect_capabilities()
        call_count_1 = self.mock_connector.execute.call_count

        # 第二次应该直接返回缓存
        caps2 = self.collector._detect_capabilities()
        call_count_2 = self.mock_connector.execute.call_count

        self.assertEqual(caps1, caps2)
        self.assertEqual(call_count_1, call_count_2)  # 没有额外调用

    def test_get_connection_count_postgresql(self):
        """测试 PostgreSQL 风格连接数查询"""
        self.collector._capabilities = {
            "information_schema": False,
            "pg_stat_activity": True,
            "performance_schema": False,
            "v$session": False,
            "sys.dm_exec_sessions": False,
            "pragma": False,
        }
        self.mock_connector.execute.return_value = MockResult([(5,)])

        result = self.collector._get_connection_count()

        self.assertEqual(result, 5.0)
        self.mock_connector.execute.assert_called_once()
        call_sql = self.mock_connector.execute.call_args[0][0]
        self.assertIn("pg_stat_activity", call_sql)

    def test_get_connection_count_mysql(self):
        """测试 MySQL 风格连接数查询"""
        self.collector._capabilities = {
            "information_schema": False,
            "pg_stat_activity": False,
            "performance_schema": True,
            "v$session": False,
            "sys.dm_exec_sessions": False,
            "pragma": False,
        }
        self.mock_connector.execute.return_value = MockResult([(10,)])

        result = self.collector._get_connection_count()

        self.assertEqual(result, 10.0)
        call_sql = self.mock_connector.execute.call_args[0][0]
        self.assertIn("performance_schema", call_sql)

    def test_get_connection_count_oracle(self):
        """测试 Oracle 风格连接数查询"""
        self.collector._capabilities = {
            "information_schema": False,
            "pg_stat_activity": False,
            "performance_schema": False,
            "v$session": True,
            "sys.dm_exec_sessions": False,
            "pragma": False,
        }
        self.mock_connector.execute.return_value = MockResult([(20,)])

        result = self.collector._get_connection_count()

        self.assertEqual(result, 20.0)
        call_sql = self.mock_connector.execute.call_args[0][0]
        self.assertIn("v$session", call_sql)

    def test_get_connection_count_sqlserver(self):
        """测试 SQL Server 风格连接数查询"""
        self.collector._capabilities = {
            "information_schema": False,
            "pg_stat_activity": False,
            "performance_schema": False,
            "v$session": False,
            "sys.dm_exec_sessions": True,
            "pragma": False,
        }
        self.mock_connector.execute.return_value = MockResult([(15,)])

        result = self.collector._get_connection_count()

        self.assertEqual(result, 15.0)
        call_sql = self.mock_connector.execute.call_args[0][0]
        self.assertIn("dm_exec_sessions", call_sql)

    def test_get_connection_count_unsupported(self):
        """测试不支持的数据库返回 None"""
        self.collector._capabilities = {
            "information_schema": False,
            "pg_stat_activity": False,
            "performance_schema": False,
            "v$session": False,
            "sys.dm_exec_sessions": False,
            "pragma": False,
        }

        result = self.collector._get_connection_count()

        self.assertIsNone(result)

    def test_get_table_count_information_schema(self):
        """测试 INFORMATION_SCHEMA 表数量查询"""
        self.collector._capabilities = {
            "information_schema": True,
            "pg_stat_activity": False,
        }
        self.mock_connector.execute.return_value = MockResult([(100,)])

        result = self.collector._get_table_count()

        self.assertEqual(result, 100.0)

    def test_get_table_count_postgresql(self):
        """测试 PostgreSQL 表数量查询"""
        self.collector._capabilities = {
            "information_schema": False,
            "pg_stat_activity": True,
        }
        self.mock_connector.execute.return_value = MockResult([(50,)])

        result = self.collector._get_table_count()

        self.assertEqual(result, 50.0)

    def test_get_index_count_information_schema(self):
        """测试 INFORMATION_SCHEMA 索引数量查询"""
        self.collector._capabilities = {
            "information_schema": True,
            "pg_stat_activity": False,
        }
        self.mock_connector.execute.return_value = MockResult([(200,)])

        result = self.collector._get_index_count()

        self.assertEqual(result, 200.0)

    def test_get_database_size_postgresql(self):
        """测试 PostgreSQL 数据库大小查询"""
        self.collector._capabilities = {
            "pg_stat_activity": True,
            "performance_schema": False,
            "pragma": False,
        }
        self.mock_connector.execute.return_value = MockResult([(1024.5,)])

        result = self.collector._get_database_size()

        self.assertEqual(result, 1024.5)
        call_sql = self.mock_connector.execute.call_args[0][0]
        self.assertIn("pg_database_size", call_sql)

    def test_get_database_size_mysql(self):
        """测试 MySQL 数据库大小查询"""
        self.collector._capabilities = {
            "pg_stat_activity": False,
            "performance_schema": True,
            "pragma": False,
        }
        self.mock_connector.execute.return_value = MockResult([(512.0,)])

        result = self.collector._get_database_size()

        self.assertEqual(result, 512.0)

    def test_get_database_size_sqlite(self):
        """测试 SQLite 数据库大小查询"""
        self.collector._capabilities = {
            "pg_stat_activity": False,
            "performance_schema": False,
            "pragma": True,
        }
        # 第一个查询尝试新语法，失败
        # 第二个查询尝试分开查询
        self.mock_connector.execute.side_effect = [
            Exception("syntax error"),
            MockResult([(1000,)]),  # page_count
            MockResult([(4096,)]),  # page_size
        ]

        result = self.collector._get_database_size()

        expected_size = 1000.0 * 4096.0 / 1024.0 / 1024.0
        self.assertAlmostEqual(result, expected_size, places=4)

    def test_collect_all_metrics(self):
        """测试完整采集流程

        模拟一个只支持 INFORMATION_SCHEMA 的数据库：
        - 支持表数量、索引数量
        - 不支持连接数（PROCESSLIST 失败）
        - 不支持数据库大小（需要 pg_stat_activity/performance_schema/pragma）
        """
        # 模拟能力探测
        self.mock_connector.execute.side_effect = [
            # _detect_capabilities 调用（缓存后不再调用）
            MockResult([(1,)]),  # INFORMATION_SCHEMA
            Exception("not found"),
            Exception("not found"),
            Exception("not found"),
            Exception("not found"),
            Exception("not found"),
            # _get_connection_count（INFORMATION_SCHEMA PROCESSLIST 失败）
            Exception("no processlist"),
            Exception("no session_status"),
            # _get_table_count（INFORMATION_SCHEMA）
            MockResult([(42,)]),
            # _get_index_count（INFORMATION_SCHEMA）
            MockResult([(150,)]),
            # _get_database_size（不支持，返回 None）
            # 无需 mock 调用
        ]

        metrics = self.collector.collect_all_metrics()

        # 应该采集到 3 个指标：表数、索引数
        # 连接数不支持（INFORMATION_SCHEMA PROCESSLIST 失败）
        # 数据库大小不支持（需要 pg_stat_activity/performance_schema/pragma）
        self.assertEqual(len(metrics), 2)

        # 验证指标类型
        metric_types = [m.metric_type for m in metrics]
        self.assertIn(MetricType.CONNECTIONS_TOTAL, metric_types)  # 表数量复用此类型

        # 验证所有指标都有时间戳
        for metric in metrics:
            self.assertIsInstance(metric.timestamp, datetime)
            self.assertEqual(metric.source, "generic")

    def test_collect_all_metrics_partial_support(self):
        """测试部分支持的数据库（只返回部分指标）"""
        self.mock_connector.execute.side_effect = [
            # _detect_capabilities: 只支持 INFORMATION_SCHEMA
            MockResult([(1,)]),
            Exception("not found"),
            Exception("not found"),
            Exception("not found"),
            Exception("not found"),
            Exception("not found"),
            # _get_connection_count: INFORMATION_SCHEMA 方式失败
            Exception("no processlist"),
            Exception("no session_status"),
            # _get_table_count: 成功
            MockResult([(30,)]),
            # _get_index_count: 成功
            MockResult([(90,)]),
            # _get_database_size: 不支持（返回 None）
            None,
        ]

        metrics = self.collector.collect_all_metrics()

        # 至少应该有表数量和索引数量
        self.assertGreaterEqual(len(metrics), 2)

    def test_collect_metric_connections(self):
        """测试采集单个连接数指标"""
        self.collector._capabilities = {
            "information_schema": True,
            "pg_stat_activity": False,
            "performance_schema": False,
            "v$session": False,
            "sys.dm_exec_sessions": False,
            "pragma": False,
        }
        self.mock_connector.execute.return_value = MockResult([(12,)])

        result = self.collector.collect_metric(MetricType.CONNECTIONS_ACTIVE)

        self.assertIsNotNone(result)
        self.assertEqual(result.metric_type, MetricType.CONNECTIONS_ACTIVE)
        self.assertEqual(result.value, 12.0)

    def test_collect_metric_disk_usage(self):
        """测试采集单个磁盘使用指标"""
        self.collector._capabilities = {
            "pg_stat_activity": True,
            "performance_schema": False,
            "pragma": False,
        }
        self.mock_connector.execute.return_value = MockResult([(1024.0,)])

        result = self.collector.collect_metric(MetricType.DISK_USAGE)

        self.assertIsNotNone(result)
        self.assertEqual(result.metric_type, MetricType.DISK_USAGE)
        self.assertEqual(result.value, 1024.0)

    def test_collect_metric_unsupported(self):
        """测试采集不支持的指标返回 None"""
        result = self.collector.collect_metric(MetricType.QPS)

        self.assertIsNone(result)

    def test_get_metric_queries(self):
        """测试 get_metric_queries 返回空字典"""
        queries = self.collector.get_metric_queries()

        self.assertEqual(queries, {})


class TestGenericMetricsCollectorIntegration(unittest.TestCase):
    """
    GenericMetricsCollector 集成测试

    使用真实 SQLite 数据库测试通用采集器
    """

    def setUp(self):
        """创建真实 SQLite 连接"""
        import tempfile
        import os

        self.temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.temp_db.close()

        from dbskiter.shared.unified_connector import UnifiedConnector

        self.connector = UnifiedConnector(
            dialect="sqlite",
            database=self.temp_db.name
        )
        self.collector = GenericMetricsCollector(self.connector)

    def tearDown(self):
        """清理临时数据库"""
        import os
        import time
        self.connector.close()
        # 等待文件句柄释放
        time.sleep(0.5)
        try:
            os.unlink(self.temp_db.name)
        except PermissionError:
            # Windows 下文件可能被占用，忽略
            pass

    def test_real_sqlite_capabilities(self):
        """测试真实 SQLite 数据库能力探测"""
        caps = self.collector._detect_capabilities()

        # SQLite 应该支持 PRAGMA
        self.assertTrue(caps["pragma"])

    def test_real_sqlite_collect_metrics(self):
        """测试真实 SQLite 数据库指标采集"""
        # 创建测试表
        self.connector.execute("CREATE TABLE test_table (id INTEGER PRIMARY KEY, name TEXT)")
        self.connector.execute("CREATE INDEX test_index ON test_table(name)")

        metrics = self.collector.collect_all_metrics()

        # 应该能采集到数据库大小
        disk_metrics = [m for m in metrics if m.metric_type == MetricType.DISK_USAGE]
        self.assertEqual(len(disk_metrics), 1)
        self.assertGreater(disk_metrics[0].value, 0)


if __name__ == "__main__":
    unittest.main()
