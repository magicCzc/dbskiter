"""
db_diagnose/test_generic_diagnostician.py
GenericDiagnostician 通用诊断器单元测试

测试范围：
    - 能力探测逻辑（9种标志位）
    - 慢查询分析（pg_stat_statements、pg_stat_activity、PROCESSLIST、无数据源）
    - 性能指标分析（连接数、事务统计、缓存命中率等）
    - 数据库统计（版本、连接数、大小、表数、索引数）
    - 辅助方法（_get_connection_count、_get_database_size_mb、_get_index_count）
    - 集成测试：完整诊断生命周期

设计说明：
    使用 unittest.mock 模拟 UnifiedConnector.execute 返回值，
    避免依赖真实数据库连接。

版本: 1.0.0
作者: AI Assistant
创建时间: 2026-06-05
"""

import unittest
from unittest.mock import MagicMock
from typing import List, Optional

from dbskiter.db_diagnose.diagnosticians.generic_diagnostician import GenericDiagnostician


class MockResult:
    """
    模拟 QueryResult 对象

    属性：
        rows: 行数据列表，每行为一个 tuple
    """

    def __init__(self, rows: Optional[List[tuple]] = None):
        self.rows = rows


def make_mock_connector(dialect: str = "trino", execute_side_effect: Optional[list] = None):
    """
    创建模拟的 UnifiedConnector

    参数：
        dialect: 数据库方言
        execute_side_effect: execute 方法的 side_effect 列表

    返回：
        MagicMock: 模拟的连接器对象
    """
    connector = MagicMock()
    connector.dialect = dialect
    connector.host = "localhost"
    connector.port = 8080
    connector.database = "test_db"
    connector.username = "test_user"
    connector.password = ""

    if execute_side_effect is not None:
        connector.execute.side_effect = execute_side_effect

    return connector


class TestGenericDiagnosticianInit(unittest.TestCase):
    """测试初始化"""

    def test_init_default(self):
        """测试默认初始化"""
        connector = make_mock_connector(dialect="trino")
        d = GenericDiagnostician(connector)

        self.assertEqual(d.dialect, "trino")
        self.assertIsNone(d._capabilities)
        self.assertIsNone(d._version_cache)


class TestGenericDiagnosticianDetectCapabilities(unittest.TestCase):
    """测试能力探测"""

    def test_detect_postgresql_full(self):
        """测试 PostgreSQL 全能力探测"""
        connector = make_mock_connector(dialect="postgresql")
        side_effects = [
            MockResult([(1,)]),          # INFORMATION_SCHEMA
            MockResult([(1,)]),          # pg_stat_activity
            MockResult([(1,)]),          # pg_stat_statements
            MockResult([(1,)]),          # pg_stat_database
            Exception("not found"),      # performance_schema
            Exception("not found"),      # v$session
            Exception("not found"),      # sys.dm_exec_sessions
            Exception("not found"),      # PRAGMA
            MockResult([("14.5",)]),     # VERSION()
        ]
        connector.execute.side_effect = side_effects

        d = GenericDiagnostician(connector)
        caps = d._detect_capabilities()

        self.assertTrue(caps["information_schema"])
        self.assertTrue(caps["pg_stat_activity"])
        self.assertTrue(caps["pg_stat_statements"])
        self.assertTrue(caps["pg_stat_database"])
        self.assertFalse(caps["performance_schema"])
        self.assertFalse(caps["v$session"])
        self.assertFalse(caps["sys.dm_exec_sessions"])
        self.assertFalse(caps["pragma"])
        self.assertTrue(caps["version_query"])
        self.assertEqual(d._version_cache, "14.5")

    def test_detect_trino_minimal(self):
        """测试 Trino 最小能力探测"""
        connector = make_mock_connector(dialect="trino")
        side_effects = [
            MockResult([(1,)]),          # INFORMATION_SCHEMA
            Exception("not found"),      # pg_stat_activity
            Exception("not found"),      # pg_stat_statements
            Exception("not found"),      # pg_stat_database
            Exception("not found"),      # performance_schema
            Exception("not found"),      # v$session
            Exception("not found"),      # sys.dm_exec_sessions
            Exception("not found"),      # PRAGMA
            MockResult([("Trino 400",)]),  # VERSION()
        ]
        connector.execute.side_effect = side_effects

        d = GenericDiagnostician(connector)
        caps = d._detect_capabilities()

        self.assertTrue(caps["information_schema"])
        self.assertFalse(caps["pg_stat_activity"])
        self.assertFalse(caps["pg_stat_statements"])
        self.assertFalse(caps["pg_stat_database"])
        self.assertTrue(caps["version_query"])

    def test_detect_cache(self):
        """测试能力探测缓存"""
        connector = make_mock_connector(dialect="mysql")
        side_effects = [
            MockResult([(1,)]),          # INFORMATION_SCHEMA
            Exception("not found"),      # pg_stat_activity
            Exception("not found"),      # pg_stat_statements
            Exception("not found"),      # pg_stat_database
            Exception("not found"),      # performance_schema
            Exception("not found"),      # v$session
            Exception("not found"),      # sys.dm_exec_sessions
            Exception("not found"),      # PRAGMA
            MockResult([("8.0",)]),      # VERSION()
        ]
        connector.execute.side_effect = side_effects

        d = GenericDiagnostician(connector)
        caps1 = d._detect_capabilities()
        caps2 = d._detect_capabilities()

        self.assertEqual(caps1, caps2)
        self.assertEqual(connector.execute.call_count, 9)


class TestGenericDiagnosticianSlowQueries(unittest.TestCase):
    """测试慢查询分析"""

    def test_analyze_slow_queries_pg_stat_statements(self):
        """测试通过 pg_stat_statements 获取慢查询"""
        connector = make_mock_connector(dialect="postgresql")
        d = GenericDiagnostician(connector)
        d._capabilities = {
            "information_schema": True,
            "pg_stat_activity": True,
            "pg_stat_statements": True,
            "pg_stat_database": True,
            "performance_schema": False,
            "v$session": False,
            "sys.dm_exec_sessions": False,
            "pragma": False,
            "version_query": True,
        }
        d._version_cache = "14.5"

        connector.execute.return_value = MockResult([
            (12345, "SELECT * FROM users", 100, 2500.0, 5000.0),
            (12346, "SELECT * FROM orders", 50, 1800.0, 3000.0),
        ])

        result = d.analyze_slow_queries(limit=10, min_time=1.0)

        self.assertTrue(result["success"])
        self.assertEqual(result["data"]["total_queries"], 2)
        self.assertEqual(result["data"]["source"], "pg_stat_statements")
        self.assertEqual(len(result["data"]["queries"]), 2)

    def test_analyze_slow_queries_pg_activity(self):
        """测试通过 pg_stat_activity 获取慢查询（pg_stat_statements 不可用）"""
        connector = make_mock_connector(dialect="postgresql")
        d = GenericDiagnostician(connector)
        d._capabilities = {
            "information_schema": True,
            "pg_stat_activity": True,
            "pg_stat_statements": False,
            "pg_stat_database": True,
            "performance_schema": False,
            "v$session": False,
            "sys.dm_exec_sessions": False,
            "pragma": False,
            "version_query": True,
        }

        # pg_stat_statements 为 False 不进入，pg_stat_activity 直接获取数据
        connector.execute.side_effect = [
            MockResult([
                (1001, "SELECT * FROM users", "active", 5.5),
            ]),  # pg_stat_activity 查询
        ]

        result = d.analyze_slow_queries(limit=10, min_time=1.0)

        self.assertTrue(result["success"])
        self.assertEqual(result["data"]["total_queries"], 1)
        self.assertEqual(result["data"]["source"], "pg_stat_activity")

    def test_analyze_slow_queries_processlist(self):
        """测试通过 INFORMATION_SCHEMA.PROCESSLIST 获取慢查询"""
        connector = make_mock_connector(dialect="mysql")
        d = GenericDiagnostician(connector)
        d._capabilities = {
            "information_schema": True,
            "pg_stat_activity": False,
            "pg_stat_statements": False,
            "pg_stat_database": False,
            "performance_schema": False,
            "v$session": False,
            "sys.dm_exec_sessions": False,
            "pragma": False,
            "version_query": True,
        }

        connector.execute.return_value = MockResult([
            (101, "SELECT * FROM users", "Query", 10),
            (102, "UPDATE orders SET status='done'", "Query", 5),
        ])

        result = d.analyze_slow_queries(limit=10, min_time=1.0)

        self.assertTrue(result["success"])
        self.assertEqual(result["data"]["total_queries"], 2)
        self.assertEqual(result["data"]["source"], "information_schema.processlist")

    def test_analyze_slow_queries_no_source(self):
        """测试没有任何慢查询数据源可用"""
        connector = make_mock_connector(dialect="trino")
        d = GenericDiagnostician(connector)
        d._capabilities = {
            "information_schema": True,
            "pg_stat_activity": False,
            "pg_stat_statements": False,
            "pg_stat_database": False,
            "performance_schema": False,
            "v$session": False,
            "sys.dm_exec_sessions": False,
            "pragma": False,
            "version_query": True,
        }

        connector.execute.return_value = None

        result = d.analyze_slow_queries(limit=10, min_time=1.0)

        self.assertTrue(result["success"])
        self.assertEqual(result["data"]["total_queries"], 0)
        self.assertIn("note", result["data"])


class TestGenericDiagnosticianPerformanceMetrics(unittest.TestCase):
    """测试性能指标分析"""

    def test_analyze_performance_postgresql(self):
        """测试 PostgreSQL 风格性能指标"""
        connector = make_mock_connector(dialect="postgresql")
        d = GenericDiagnostician(connector)
        d._capabilities = {
            "information_schema": True,
            "pg_stat_activity": True,
            "pg_stat_statements": False,
            "pg_stat_database": True,
            "performance_schema": False,
            "v$session": False,
            "sys.dm_exec_sessions": False,
            "pragma": False,
            "version_query": True,
        }

        # _get_connection_count -> pg_stat_activity
        # connection_states -> pg_stat_activity
        # pg_stat_database
        # _get_database_size_mb -> pg_database_size
        # table_count -> information_schema
        # _get_index_count -> pg_class
        # long_running_queries -> pg_stat_activity
        side_effects = [
            MockResult([(15,)]),          # active_connections
            MockResult([                   # connection_states
                ("active", 15),
                ("idle", 5),
            ]),
            MockResult([                   # pg_stat_database
                (10000, 50, 1000, 9000, 0),
            ]),
            MockResult([(2048.0,)]),      # database_size
            MockResult([(42,)]),          # table_count
            MockResult([(150,)]),         # index_count
            MockResult([                   # long_running_queries
                (1001, "admin", "active", 65.5, "SELECT * FROM big_table"),
            ]),
        ]
        connector.execute.side_effect = side_effects

        result = d.analyze_performance_metrics()

        self.assertTrue(result["success"])
        data = result["data"]
        self.assertEqual(data["active_connections"], 15)
        self.assertEqual(data["connection_states"]["active"], 15)
        self.assertEqual(data["transactions_committed"], 10000)
        self.assertAlmostEqual(data["cache_hit_ratio"], 90.0, places=1)
        self.assertEqual(data["table_count"], 42)
        self.assertEqual(data["index_count"], 150)
        self.assertEqual(len(data["long_running_queries"]), 1)

    def test_analyze_performance_minimal(self):
        """测试最小能力集下的性能指标"""
        connector = make_mock_connector(dialect="trino")
        d = GenericDiagnostician(connector)
        d._capabilities = {
            "information_schema": True,
            "pg_stat_activity": False,
            "pg_stat_statements": False,
            "pg_stat_database": False,
            "performance_schema": False,
            "v$session": False,
            "sys.dm_exec_sessions": False,
            "pragma": False,
            "version_query": True,
        }

        # _get_connection_count -> 全部失败
        # _get_database_size_mb -> 全部失败
        # table_count -> information_schema
        # _get_index_count -> information_schema
        side_effects = [
            Exception("not supported"),   # connection: processlist
            Exception("not supported"),   # connection: session_status
            Exception("not supported"),   # size: mysql info_schema
            MockResult([(28,)]),          # table_count
            MockResult([(45,)]),          # index_count
        ]
        connector.execute.side_effect = side_effects

        result = d.analyze_performance_metrics()

        self.assertTrue(result["success"])
        data = result["data"]
        self.assertNotIn("active_connections", data)
        self.assertEqual(data["table_count"], 28)
        self.assertEqual(data["index_count"], 45)


class TestGenericDiagnosticianDatabaseStats(unittest.TestCase):
    """测试数据库统计"""

    def test_get_database_stats_full(self):
        """测试完整数据库统计"""
        connector = make_mock_connector(dialect="postgresql")
        d = GenericDiagnostician(connector)
        d._capabilities = {
            "information_schema": True,
            "pg_stat_activity": True,
            "pg_stat_statements": False,
            "pg_stat_database": False,
            "performance_schema": False,
            "v$session": False,
            "sys.dm_exec_sessions": False,
            "pragma": False,
            "version_query": True,
        }
        d._version_cache = "14.5"

        # current_database, connection_count, size, table_count, index_count, user
        side_effects = [
            MockResult([("test_db",)]),   # current_database
            MockResult([(25,)]),          # connection_count
            MockResult([(1024.0,)]),      # size
            MockResult([(42,)]),          # table_count
            MockResult([(150,)]),         # index_count
            MockResult([("admin",)]),     # current_user
        ]
        connector.execute.side_effect = side_effects

        result = d.get_database_stats()

        self.assertTrue(result["success"])
        data = result["data"]
        self.assertEqual(data["version"], "14.5")
        self.assertEqual(data["database_name"], "test_db")
        self.assertEqual(data["current_connections"], 25)
        self.assertEqual(data["database_size_mb"], 1024.0)
        self.assertEqual(data["table_count"], 42)
        self.assertEqual(data["index_count"], 150)
        self.assertEqual(data["current_user"], "admin")

    def test_get_database_stats_no_capabilities(self):
        """测试无能力时的数据库统计"""
        connector = make_mock_connector(dialect="unknown_db")
        d = GenericDiagnostician(connector)
        d._capabilities = {
            "information_schema": False,
            "pg_stat_activity": False,
            "pg_stat_statements": False,
            "pg_stat_database": False,
            "performance_schema": False,
            "v$session": False,
            "sys.dm_exec_sessions": False,
            "pragma": False,
            "version_query": False,
        }

        # 所有查询都失败
        connector.execute.side_effect = Exception("not supported")

        result = d.get_database_stats()

        self.assertTrue(result["success"])
        data = result["data"]
        self.assertEqual(data["database_type"], "unknown_db")
        self.assertNotIn("version", data)


class TestGenericDiagnosticianHelperMethods(unittest.TestCase):
    """测试辅助方法"""

    def test_get_connection_count_pg(self):
        """测试 PostgreSQL 风格连接数"""
        connector = make_mock_connector(dialect="postgresql")
        d = GenericDiagnostician(connector)
        caps = {"pg_stat_activity": True}
        connector.execute.return_value = MockResult([(20,)])

        count = d._get_connection_count(caps)
        self.assertEqual(count, 20)

    def test_get_connection_count_none(self):
        """测试无法获取连接数"""
        connector = make_mock_connector(dialect="trino")
        d = GenericDiagnostician(connector)
        caps = {
            "pg_stat_activity": False,
            "performance_schema": False,
            "v$session": False,
            "sys.dm_exec_sessions": False,
            "information_schema": False,
        }

        count = d._get_connection_count(caps)
        self.assertIsNone(count)

    def test_get_database_size_mb_pg(self):
        """测试 PostgreSQL 风格数据库大小"""
        connector = make_mock_connector(dialect="postgresql")
        d = GenericDiagnostician(connector)
        caps = {"pg_stat_activity": True}
        connector.execute.return_value = MockResult([(5120.0,)])

        size = d._get_database_size_mb(caps)
        self.assertEqual(size, 5120.0)

    def test_get_database_size_mb_sqlite(self):
        """测试 SQLite 风格数据库大小"""
        connector = make_mock_connector(dialect="sqlite")
        d = GenericDiagnostician(connector)
        caps = {"pragma": True, "pg_stat_activity": False, "information_schema": False}

        connector.execute.side_effect = [
            MockResult([(1000,)]),    # PRAGMA page_count
            MockResult([(4096,)]),    # PRAGMA page_size
        ]

        size = d._get_database_size_mb(caps)
        # 1000 * 4096 / 1024 / 1024 = 3.91 MB
        self.assertAlmostEqual(size, 3.91, places=1)

    def test_get_index_count_none(self):
        """测试无法获取索引数"""
        connector = make_mock_connector(dialect="trino")
        d = GenericDiagnostician(connector)
        caps = {"information_schema": False, "pg_stat_activity": False}

        count = d._get_index_count(caps)
        self.assertIsNone(count)


class TestGenericDiagnosticianIntegration(unittest.TestCase):
    """集成测试"""

    def test_full_diagnose_lifecycle_postgresql(self):
        """测试 PostgreSQL 完整诊断生命周期"""
        connector = make_mock_connector(dialect="postgresql")
        d = GenericDiagnostician(connector)
        d._capabilities = {
            "information_schema": True,
            "pg_stat_activity": True,
            "pg_stat_statements": True,
            "pg_stat_database": True,
            "performance_schema": False,
            "v$session": False,
            "sys.dm_exec_sessions": False,
            "pragma": False,
            "version_query": True,
        }
        d._version_cache = "14.5"

        # 慢查询
        connector.execute.side_effect = [
            MockResult([                   # pg_stat_statements
                (12345, "SELECT * FROM users", 100, 2500.0, 5000.0),
            ]),
        ]

        slow = d.analyze_slow_queries()
        self.assertTrue(slow["success"])

        # 重置 mock
        connector.reset_mock()
        side_effects = [
            MockResult([(15,)]),          # connection_count
            MockResult([("active", 15), ("idle", 5)]),  # connection_states
            MockResult([(10000, 50, 1000, 9000, 0)]),  # pg_stat_database
            MockResult([(2048.0,)]),      # size
            MockResult([(42,)]),          # table_count
            MockResult([(150,)]),         # index_count
            MockResult([]),               # long_running_queries (空)
        ]
        connector.execute.side_effect = side_effects

        perf = d.analyze_performance_metrics()
        self.assertTrue(perf["success"])

        # 重置 mock
        connector.reset_mock()
        side_effects = [
            MockResult([("test_db",)]),   # database_name
            MockResult([(15,)]),          # connection_count
            MockResult([(2048.0,)]),      # size
            MockResult([(42,)]),          # table_count
            MockResult([(150,)]),         # index_count
            MockResult([("admin",)]),     # user
        ]
        connector.execute.side_effect = side_effects

        stats = d.get_database_stats()
        self.assertTrue(stats["success"])
        self.assertEqual(stats["data"]["version"], "14.5")


if __name__ == "__main__":
    unittest.main()
