"""
db_inspector/test_generic_inspector.py
GenericInspector 通用巡检器单元测试

测试范围：
    - 能力探测逻辑（各种数据库风格）
    - 配置检查（版本、schema、表数、引擎）
    - 性能检查（活跃连接数、大表）
    - 存储检查（数据库大小、索引数）
    - 安全检查（当前用户）
    - 容量检查（数据库容量）
    - 实例信息获取
    - 边界情况：所有查询失败、无 INFORMATION_SCHEMA

设计说明：
    使用 unittest.mock 模拟 UnifiedConnector.execute 返回值，
    避免依赖真实数据库连接。每个测试方法覆盖一个独立场景。

版本: 1.0.0
作者: AI Assistant
创建时间: 2026-06-05
"""

import unittest
from unittest.mock import MagicMock, patch, call
from typing import List, Optional

from dbskiter.db_inspector.inspectors.generic_inspector import GenericInspector
from dbskiter.db_inspector.models import InspectionItem, InspectionType, RiskLevel


class MockResult:
    """
    模拟 QueryResult 对象

    属性：
        rows: 行数据列表，每行为一个 tuple
    """

    def __init__(self, rows: Optional[List[tuple]] = None):
        self.rows = rows or []


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


class TestGenericInspectorInit(unittest.TestCase):
    """测试 GenericInspector 初始化"""

    def test_init_default(self):
        """测试默认初始化"""
        connector = make_mock_connector(dialect="trino")
        inspector = GenericInspector(connector)

        self.assertEqual(inspector.dialect, "trino")
        self.assertIsNone(inspector._capabilities)


class TestGenericInspectorDetectCapabilities(unittest.TestCase):
    """测试能力探测"""

    def setUp(self):
        """每个测试前重置"""
        super().setUp()
        # 重置能力探测缓存，避免跨测试影响
        self.addCleanup(GenericInspector._detect_capabilities.cache_clear if hasattr(
            GenericInspector._detect_capabilities, 'cache_clear') else lambda: None)

    def test_detect_all_capabilities(self):
        """
        测试所有能力都支持

        模拟一个 PostgreSQL 风格的数据库，所有系统视图均可查询。
        """
        connector = make_mock_connector(dialect="postgresql")
        # 每个 execute 调用返回一个 MockResult
        side_effects = [
            MockResult([(1,)]),          # INFORMATION_SCHEMA
            MockResult([(1,)]),          # pg_stat_activity
            MockResult([(1,)]),          # performance_schema
            MockResult([(1,)]),          # v$session
            MockResult([(1,)]),          # sys.dm_exec_sessions
            MockResult([(1,)]),          # PRAGMA page_count
            MockResult([("14.5",)]),     # VERSION()
        ]
        connector.execute.side_effect = side_effects

        inspector = GenericInspector(connector)
        caps = inspector._detect_capabilities()

        self.assertTrue(caps["information_schema"])
        self.assertTrue(caps["pg_stat_activity"])
        self.assertTrue(caps["performance_schema"])
        self.assertTrue(caps["v$session"])
        self.assertTrue(caps["sys.dm_exec_sessions"])
        self.assertTrue(caps["pragma"])
        self.assertTrue(caps["version_query"])

    def test_detect_only_information_schema(self):
        """
        测试仅支持 INFORMATION_SCHEMA

        模拟 Trino/Presto 风格数据库，只有 INFORMATION_SCHEMA 可用。
        """
        connector = make_mock_connector(dialect="trino")
        side_effects = [
            MockResult([(1,)]),          # INFORMATION_SCHEMA 成功
            Exception("relation not found"),  # pg_stat_activity 失败
            Exception("table not found"),      # performance_schema 失败
            Exception("table not found"),      # v$session 失败
            Exception("table not found"),      # sys.dm_exec_sessions 失败
            Exception("not available"),        # PRAGMA 失败
            MockResult([("Trino 400",)]),      # VERSION() 成功
        ]
        connector.execute.side_effect = side_effects

        inspector = GenericInspector(connector)
        caps = inspector._detect_capabilities()

        self.assertTrue(caps["information_schema"])
        self.assertFalse(caps["pg_stat_activity"])
        self.assertFalse(caps["performance_schema"])
        self.assertFalse(caps["v$session"])
        self.assertFalse(caps["sys.dm_exec_sessions"])
        self.assertFalse(caps["pragma"])
        self.assertTrue(caps["version_query"])

    def test_detect_nothing(self):
        """
        测试没有任何能力

        模拟一个完全陌生的数据库，所有查询都失败。
        """
        connector = make_mock_connector(dialect="unknown_db")
        side_effects = [
            Exception("not found"),            # INFORMATION_SCHEMA
            Exception("not found"),            # pg_stat_activity
            Exception("not found"),            # performance_schema
            Exception("not found"),            # v$session
            Exception("not found"),            # sys.dm_exec_sessions
            Exception("not found"),            # PRAGMA
            Exception("not found"),            # VERSION() 第一次
            Exception("not found"),            # version() 第二次
            Exception("not found"),            # @@version 第三次
        ]
        connector.execute.side_effect = side_effects

        inspector = GenericInspector(connector)
        caps = inspector._detect_capabilities()

        for key, value in caps.items():
            self.assertFalse(value, f"能力 {key} 应为 False")

    def test_detect_cache(self):
        """
        测试能力探测缓存

        第二次调用不应再次执行 SQL 查询。
        """
        connector = make_mock_connector(dialect="mysql")
        side_effects = [
            MockResult([(1,)]),          # INFORMATION_SCHEMA
            Exception("not found"),      # pg_stat_activity
            Exception("not found"),      # performance_schema
            Exception("not found"),      # v$session
            Exception("not found"),      # sys.dm_exec_sessions
            Exception("not found"),      # PRAGMA
            MockResult([("8.0",)]),      # VERSION()
        ]
        connector.execute.side_effect = side_effects

        inspector = GenericInspector(connector)

        # 第一次调用
        caps1 = inspector._detect_capabilities()
        self.assertTrue(caps1["information_schema"])

        # 第二次调用 - 应使用缓存
        caps2 = inspector._detect_capabilities()
        self.assertEqual(caps1, caps2)

        # execute 应只被调用 7 次（首次探测）
        self.assertEqual(connector.execute.call_count, 7)

    def test_detect_version_various_syntax(self):
        """
        测试版本查询的多种语法

        当 SELECT VERSION() 失败时，应尝试 SELECT version() 和 SELECT @@version。
        """
        connector = make_mock_connector(dialect="mssql")
        side_effects = [
            MockResult([(1,)]),          # INFORMATION_SCHEMA
            Exception("not found"),      # pg_stat_activity
            Exception("not found"),      # performance_schema
            Exception("not found"),      # v$session
            MockResult([(1,)]),          # sys.dm_exec_sessions 成功
            Exception("not found"),      # PRAGMA
            Exception("not supported"),  # VERSION() 大写失败
            MockResult([(1,)]),          # version() 小写成功(仅探测用)
            MockResult([("16.0",)]),     # @@version 成功
        ]
        connector.execute.side_effect = side_effects

        inspector = GenericInspector(connector)
        caps = inspector._detect_capabilities()

        self.assertTrue(caps["version_query"])


class TestGenericInspectorGetInstanceInfo(unittest.TestCase):
    """测试获取实例信息"""

    def test_get_instance_info_with_version(self):
        """
        测试获取实例信息（有版本）

        当版本查询可用时，实例信息应包含版本号。
        """
        connector = make_mock_connector(dialect="mysql")
        side_effects = [
            MockResult([(1,)]),          # INFORMATION_SCHEMA
            Exception("not found"),      # pg_stat_activity
            Exception("not found"),      # performance_schema
            Exception("not found"),      # v$session
            Exception("not found"),      # sys.dm_exec_sessions
            Exception("not found"),      # PRAGMA
            MockResult([("8.0.32",)]),   # VERSION()
        ]
        connector.execute.side_effect = side_effects

        inspector = GenericInspector(connector)
        info = inspector.get_instance_info()

        self.assertEqual(info["version"], "8.0.32")
        self.assertEqual(info["database_type"], "mysql")
        self.assertIn("capabilities", info)

    def test_get_instance_info_without_version(self):
        """
        测试获取实例信息（无版本）

        当版本查询不可用时，版本应为 "unknown"。
        """
        connector = make_mock_connector(dialect="trino")
        side_effects = [
            MockResult([(1,)]),          # INFORMATION_SCHEMA
            Exception("not found"),      # pg_stat_activity
            Exception("not found"),      # performance_schema
            Exception("not found"),      # v$session
            Exception("not found"),      # sys.dm_exec_sessions
            Exception("not found"),      # PRAGMA
            Exception("not supported"),  # VERSION()
            Exception("not supported"),  # version()
            Exception("not supported"),  # @@version
        ]
        connector.execute.side_effect = side_effects

        inspector = GenericInspector(connector)
        info = inspector.get_instance_info()

        self.assertEqual(info["version"], "unknown")


class TestGenericInspectorConfiguration(unittest.TestCase):
    """测试配置检查"""

    def test_inspect_configuration_full(self):
        """
        测试完整配置检查

        所有能力都支持，应返回完整的配置检查项。
        """
        connector = make_mock_connector(dialect="mysql")
        side_effects = [
            MockResult([(1,)]),          # 能力探测：INFORMATION_SCHEMA
            Exception("not found"),      # pg_stat_activity
            Exception("not found"),      # performance_schema
            Exception("not found"),      # v$session
            Exception("not found"),      # sys.dm_exec_sessions
            Exception("not found"),      # PRAGMA
            MockResult([("8.0.32",)]),   # VERSION()（缓存到 _version_cache）
            # 配置检查实际查询（使用 _version_cache，不再重新查询版本）
            MockResult([(5,)]),          # Schema 数量
            MockResult([(42,)]),         # 表总数
            MockResult([(1,)]),          # ENGINE 查询
        ]
        connector.execute.side_effect = side_effects

        inspector = GenericInspector(connector)
        items = inspector.inspect_configuration()

        # 应返回 4 个配置项
        self.assertEqual(len(items), 4)

        # 检查各配置项名称
        item_names = [item.name for item in items]
        self.assertIn("数据库类型与版本", item_names)
        self.assertIn("Schema 数量", item_names)
        self.assertIn("表总数", item_names)
        self.assertIn("数据库引擎/方言", item_names)

        # 验证类型与版本
        version_item = items[0]
        self.assertEqual(version_item.status, "pass")
        self.assertIn("8.0.32", version_item.description)

    def test_inspect_configuration_no_information_schema(self):
        """
        测试无 INFORMATION_SCHEMA 的配置检查

        当 INFORMATION_SCHEMA 不可用时，应返回基础信息但标记为 warning。
        """
        connector = make_mock_connector(dialect="unknown_db")
        side_effects = [
            Exception("not found"),            # INFORMATION_SCHEMA
            Exception("not found"),            # pg_stat_activity
            Exception("not found"),            # performance_schema
            Exception("not found"),            # v$session
            Exception("not found"),            # sys.dm_exec_sessions
            Exception("not found"),            # PRAGMA
            Exception("not found"),            # VERSION()
            Exception("not found"),            # version()
            Exception("not found"),            # @@version
            # 配置检查（缓存命中后不再执行能力探测SQL）
        ]
        connector.execute.side_effect = side_effects

        inspector = GenericInspector(connector)
        items = inspector.inspect_configuration()

        # 所有项应为 warning
        for item in items:
            self.assertEqual(item.status, "warning",
                             f"配置项 {item.name} 应为 warning")

    def test_inspect_configuration_high_table_count(self):
        """
        测试表数量超过阈值

        当表数量超过 TABLE_COUNT_THRESHOLD(10000) 时，应标记为 warning。
        """
        connector = make_mock_connector(dialect="mysql")
        side_effects = [
            MockResult([(1,)]),          # INFORMATION_SCHEMA
            Exception("not found"),      # pg_stat_activity
            Exception("not found"),      # performance_schema
            Exception("not found"),      # v$session
            Exception("not found"),      # sys.dm_exec_sessions
            Exception("not found"),      # PRAGMA
            MockResult([("8.0",)]),      # VERSION()（缓存到 _version_cache）
            # 配置检查（使用 _version_cache，不再重新查询版本）
            MockResult([(5,)]),          # Schema 数量
            MockResult([(15000,)]),      # 表总数（超过阈值）
            MockResult([(1,)]),          # ENGINE
        ]
        connector.execute.side_effect = side_effects

        inspector = GenericInspector(connector)
        items = inspector.inspect_configuration()

        # 找表总数配置项
        table_item = next(item for item in items if item.name == "表总数")
        self.assertEqual(table_item.status, "warning")
        self.assertEqual(table_item.risk_level, RiskLevel.MEDIUM)


class TestGenericInspectorPerformance(unittest.TestCase):
    """测试性能检查"""

    def test_inspect_performance_with_connections(self):
        """
        测试性能检查（有连接数）

        PostgreSQL 风格，通过 pg_stat_activity 获取活跃连接数。
        """
        connector = make_mock_connector(dialect="postgresql")
        side_effects = [
            MockResult([(1,)]),          # INFORMATION_SCHEMA（能力探测）
            MockResult([(1,)]),          # pg_stat_activity
            Exception("not found"),      # performance_schema
            Exception("not found"),      # v$session
            Exception("not found"),      # sys.dm_exec_sessions
            Exception("not found"),      # PRAGMA
            MockResult([("14.5",)]),     # VERSION()
            # 性能检查
            MockResult([(25,)]),         # 活跃连接数
            MockResult([                 # TOP 大表
                ("public", "users", 100000),
                ("public", "orders", 50000),
            ]),
        ]
        connector.execute.side_effect = side_effects

        inspector = GenericInspector(connector)
        items = inspector.inspect_performance()

        # 应包含活跃连接数和 TOP 大表
        item_names = [item.name for item in items]
        self.assertIn("活跃连接数", item_names)
        self.assertIn("TOP 大表", item_names)
        self.assertIn("性能综述", item_names)

        # 验证活跃连接数值
        conn_item = next(item for item in items if item.name == "活跃连接数")
        self.assertEqual(conn_item.status, "pass")
        self.assertIn("25", conn_item.description)

    def test_inspect_performance_high_connections(self):
        """
        测试性能检查（连接数过高）

        当连接数超过 CRITICAL 阈值(90) 时，应标记为 fail。
        """
        connector = make_mock_connector(dialect="postgresql")
        side_effects = [
            MockResult([(1,)]),          # INFORMATION_SCHEMA
            MockResult([(1,)]),          # pg_stat_activity
            Exception("not found"),      # performance_schema
            Exception("not found"),      # v$session
            Exception("not found"),      # sys.dm_exec_sessions
            Exception("not found"),      # PRAGMA
            MockResult([("14.5",)]),     # VERSION()
            # 性能检查
            MockResult([(95,)]),         # 活跃连接数（超过CRITICAL）
        ]
        connector.execute.side_effect = side_effects

        inspector = GenericInspector(connector)
        items = inspector.inspect_performance()

        conn_item = next(item for item in items if item.name == "活跃连接数")
        self.assertEqual(conn_item.status, "fail")
        self.assertEqual(conn_item.risk_level, RiskLevel.CRITICAL)

    def test_inspect_performance_no_connections(self):
        """
        测试性能检查（无连接数查询能力）

        当数据库不支持任何会话视图时，应返回 warning 描述。
        """
        connector = make_mock_connector(dialect="trino")
        side_effects = [
            MockResult([(1,)]),          # 仅 INFORMATION_SCHEMA
            Exception("not found"),      # pg_stat_activity
            Exception("not found"),      # performance_schema
            Exception("not found"),      # v$session
            Exception("not found"),      # sys.dm_exec_sessions
            Exception("not found"),      # PRAGMA
            Exception("not found"),      # VERSION()
            Exception("not found"),      # version()
            Exception("not found"),      # @@version
            # 性能检查
            MockResult([]),              # TOP 大表（空结果）
        ]
        connector.execute.side_effect = side_effects

        inspector = GenericInspector(connector)
        items = inspector.inspect_performance()

        conn_item = next(item for item in items if item.name == "活跃连接数")
        self.assertEqual(conn_item.status, "warning")
        self.assertIn("不支持通过标准视图查询", conn_item.description)


class TestGenericInspectorStorage(unittest.TestCase):
    """测试存储检查"""

    def test_inspect_storage_postgresql(self):
        """
        测试存储检查（PostgreSQL）

        通过 pg_database_size 获取数据库大小。
        """
        connector = make_mock_connector(dialect="postgresql")
        side_effects = [
            MockResult([(1,)]),          # INFORMATION_SCHEMA
            MockResult([(1,)]),          # pg_stat_activity
            Exception("not found"),      # performance_schema
            Exception("not found"),      # v$session
            Exception("not found"),      # sys.dm_exec_sessions
            Exception("not found"),      # PRAGMA
            MockResult([("14.5",)]),     # VERSION()
            # 存储检查
            MockResult([(2048.0,)]),     # 数据库大小 2GB
            MockResult([(42,)]),         # 表数量
            MockResult([(150,)]),        # 索引数量
        ]
        connector.execute.side_effect = side_effects

        inspector = GenericInspector(connector)
        items = inspector.inspect_storage()

        item_names = [item.name for item in items]
        self.assertIn("数据库总大小", item_names)
        self.assertIn("表数量", item_names)
        self.assertIn("索引数量", item_names)

        # 验证大小
        size_item = next(item for item in items if item.name == "数据库总大小")
        self.assertEqual(size_item.status, "pass")
        self.assertIn("2.00 GB", size_item.description)

    def test_inspect_storage_sqlite(self):
        """
        测试存储检查（SQLite）

        通过 PRAGMA page_count 和 PRAGMA page_size 获取数据库大小。
        """
        connector = make_mock_connector(dialect="sqlite")
        side_effects = [
            MockResult([(1,)]),          # INFORMATION_SCHEMA
            Exception("not found"),      # pg_stat_activity
            Exception("not found"),      # performance_schema
            Exception("not found"),      # v$session
            Exception("not found"),      # sys.dm_exec_sessions
            MockResult([(1000,)]),       # PRAGMA page_count
            Exception("not found"),      # VERSION()
            Exception("not found"),      # version()
            MockResult([("3.45.0",)]),   # @@version
            # 存储检查
            MockResult([(1000,)]),       # PRAGMA page_count（存储检查）
            MockResult([(4096,)]),       # PRAGMA page_size
        ]
        connector.execute.side_effect = side_effects

        inspector = GenericInspector(connector)
        items = inspector.inspect_storage()

        size_item = next(item for item in items if item.name == "数据库总大小")
        self.assertEqual(size_item.status, "pass")
        # 1000 pages * 4096 bytes = 4,096,000 bytes = 3.91 MB
        self.assertIn("MB", size_item.description)

    def test_inspect_storage_no_size(self):
        """
        测试存储检查（无法获取大小）

        当数据库不支持任何存储查询时，应返回 warning。
        """
        connector = make_mock_connector(dialect="trino")
        side_effects = [
            MockResult([(1,)]),          # 仅 INFORMATION_SCHEMA
            Exception("not found"),      # pg_stat_activity
            Exception("not found"),      # performance_schema
            Exception("not found"),      # v$session
            Exception("not found"),      # sys.dm_exec_sessions
            Exception("not found"),      # PRAGMA
            Exception("not found"),      # VERSION()
            Exception("not found"),      # version()
            Exception("not found"),      # @@version
            # 存储检查
            Exception("not supported"),  # _get_database_size_mb MySQL 路径失败
            MockResult([(15,)]),         # 表数量
        ]
        connector.execute.side_effect = side_effects

        inspector = GenericInspector(connector)
        items = inspector.inspect_storage()

        size_item = next(item for item in items if item.name == "数据库总大小")
        self.assertEqual(size_item.status, "warning")


class TestGenericInspectorSecurity(unittest.TestCase):
    """测试安全检查"""

    def test_inspect_security_with_user(self):
        """
        测试安全检查（有用户信息）

        通过 CURRENT_USER 获取当前用户。
        """
        connector = make_mock_connector(dialect="mysql")
        side_effects = [
            MockResult([(1,)]),          # INFORMATION_SCHEMA
            Exception("not found"),      # pg_stat_activity
            Exception("not found"),      # performance_schema
            Exception("not found"),      # v$session
            Exception("not found"),      # sys.dm_exec_sessions
            Exception("not found"),      # PRAGMA
            MockResult([("8.0",)]),      # VERSION()
            # 安全检查
            MockResult([("admin@localhost",)]),  # CURRENT_USER
        ]
        connector.execute.side_effect = side_effects

        inspector = GenericInspector(connector)
        items = inspector.inspect_security()

        self.assertEqual(len(items), 2)

        user_item = next(item for item in items if item.name == "数据库用户")
        self.assertEqual(user_item.status, "pass")
        self.assertIn("admin@localhost", user_item.description)

    def test_inspect_security_no_user(self):
        """
        测试安全检查（无用户信息）

        当所有用户查询都失败时，应返回 warning。
        """
        connector = make_mock_connector(dialect="trino")
        side_effects = [
            MockResult([(1,)]),          # INFORMATION_SCHEMA
            Exception("not found"),      # pg_stat_activity
            Exception("not found"),      # performance_schema
            Exception("not found"),      # v$session
            Exception("not found"),      # sys.dm_exec_sessions
            Exception("not found"),      # PRAGMA
            Exception("not found"),      # VERSION()
            Exception("not found"),      # version()
            Exception("not found"),      # @@version
            # 安全检查
            Exception("not supported"),  # CURRENT_USER
            Exception("not supported"),  # current_user
            Exception("not supported"),  # USER()
            Exception("not supported"),  # SESSION_USER
        ]
        connector.execute.side_effect = side_effects

        inspector = GenericInspector(connector)
        items = inspector.inspect_security()

        user_item = next(item for item in items if item.name == "数据库用户")
        self.assertEqual(user_item.status, "warning")
        self.assertIn("未知", user_item.description)


class TestGenericInspectorCapacity(unittest.TestCase):
    """测试容量检查"""

    def test_inspect_capacity_with_size(self):
        """
        测试容量检查（有大小）

        获取数据库大小并返回容量评估。
        """
        connector = make_mock_connector(dialect="postgresql")
        side_effects = [
            MockResult([(1,)]),          # INFORMATION_SCHEMA
            MockResult([(1,)]),          # pg_stat_activity
            Exception("not found"),      # performance_schema
            Exception("not found"),      # v$session
            Exception("not found"),      # sys.dm_exec_sessions
            Exception("not found"),      # PRAGMA
            MockResult([("14.5",)]),     # VERSION()
            # 容量检查
            MockResult([(5120.0,)]),     # 数据库大小 5GB
        ]
        connector.execute.side_effect = side_effects

        inspector = GenericInspector(connector)
        items = inspector.inspect_capacity()

        self.assertEqual(len(items), 2)

        cap_item = next(item for item in items if item.name == "数据库容量")
        self.assertEqual(cap_item.status, "pass")
        self.assertIn("5.00 GB", cap_item.description)

    def test_inspect_capacity_no_size(self):
        """
        测试容量检查（无法获取大小）

        当无法获取数据库大小时，容量检查项为 warning。
        """
        connector = make_mock_connector(dialect="trino")
        side_effects = [
            MockResult([(1,)]),          # 仅 INFORMATION_SCHEMA
            Exception("not found"),      # pg_stat_activity
            Exception("not found"),      # performance_schema
            Exception("not found"),      # v$session
            Exception("not found"),      # sys.dm_exec_sessions
            Exception("not found"),      # PRAGMA
            Exception("not found"),      # VERSION()
            Exception("not found"),      # version()
            Exception("not found"),      # @@version
        ]
        connector.execute.side_effect = side_effects

        inspector = GenericInspector(connector)
        items = inspector.inspect_capacity()

        cap_item = next(item for item in items if item.name == "数据库容量")
        self.assertEqual(cap_item.status, "warning")


class TestGenericInspectorHelperMethods(unittest.TestCase):
    """测试辅助方法"""

    def test_format_size_mb_small(self):
        """测试小尺寸格式化（KB）"""
        connector = make_mock_connector()
        inspector = GenericInspector(connector)

        result = inspector._format_size_mb(0.5)
        self.assertEqual(result, "512.0 KB")

    def test_format_size_mb_medium(self):
        """测试中等尺寸格式化（MB）"""
        connector = make_mock_connector()
        inspector = GenericInspector(connector)

        result = inspector._format_size_mb(100.0)
        self.assertEqual(result, "100.0 MB")

    def test_format_size_mb_large(self):
        """测试大尺寸格式化（GB）"""
        connector = make_mock_connector()
        inspector = GenericInspector(connector)

        result = inspector._format_size_mb(2048.0)
        self.assertEqual(result, "2.00 GB")

    def test_get_connection_count_postgresql(self):
        """测试获取 PostgreSQL 连接数"""
        connector = make_mock_connector(dialect="postgresql")
        inspector = GenericInspector(connector)

        caps = {
            "information_schema": True,
            "pg_stat_activity": True,
            "performance_schema": False,
            "v$session": False,
            "sys.dm_exec_sessions": False,
            "pragma": False,
            "version_query": True,
        }
        # 提前设置缓存，避免触发完整探测
        inspector._capabilities = caps

        connector.execute.return_value = MockResult([(15,)])
        count = inspector._get_connection_count(caps)

        self.assertEqual(count, 15)

    def test_get_connection_count_fallback(self):
        """
        测试连接数查询回退

        pg_stat_activity 不可用，回退到 performance_schema。
        """
        connector = make_mock_connector(dialect="mysql")
        inspector = GenericInspector(connector)

        caps = {
            "information_schema": True,
            "pg_stat_activity": False,
            "performance_schema": True,
            "v$session": False,
            "sys.dm_exec_sessions": False,
            "pragma": False,
            "version_query": True,
        }
        inspector._capabilities = caps

        connector.execute.return_value = MockResult([(30,)])
        count = inspector._get_connection_count(caps)

        self.assertEqual(count, 30)
        # 应调用 performance_schema 查询
        connector.execute.assert_called_once()
        self.assertIn("performance_schema", connector.execute.call_args[0][0])

    def test_get_connection_count_none(self):
        """测试连接数查询全部失败"""
        connector = make_mock_connector(dialect="trino")
        inspector = GenericInspector(connector)

        caps = {
            "information_schema": True,
            "pg_stat_activity": False,
            "performance_schema": False,
            "v$session": False,
            "sys.dm_exec_sessions": False,
            "pragma": False,
            "version_query": False,
        }
        inspector._capabilities = caps

        connector.execute.return_value = None
        count = inspector._get_connection_count(caps)

        self.assertIsNone(count)

    def test_get_database_size_mb_none(self):
        """测试获取数据库大小全部失败"""
        connector = make_mock_connector(dialect="trino")
        inspector = GenericInspector(connector)

        caps = {
            "information_schema": True,
            "pg_stat_activity": False,
            "performance_schema": False,
            "v$session": False,
            "sys.dm_exec_sessions": False,
            "pragma": False,
            "version_query": False,
        }
        inspector._capabilities = caps

        connector.execute.side_effect = Exception("not supported")
        size = inspector._get_database_size_mb(caps)

        self.assertIsNone(size)

    def test_get_index_count_none(self):
        """测试获取索引数量全部失败"""
        connector = make_mock_connector(dialect="trino")
        inspector = GenericInspector(connector)

        caps = {
            "information_schema": True,
            "pg_stat_activity": False,
            "performance_schema": False,
            "v$session": False,
            "sys.dm_exec_sessions": False,
            "pragma": False,
            "version_query": False,
        }
        inspector._capabilities = caps

        connector.execute.side_effect = Exception("not supported")
        count = inspector._get_index_count(caps)

        self.assertIsNone(count)


class TestGenericInspectorIntegration(unittest.TestCase):
    """
    集成测试：模拟完整巡检流程

    模拟一个真实的数据库（Trino），测试完整巡检流程。
    """

    def test_full_inspection_lifecycle(self):
        """
        测试完整巡检生命周期

        模拟 Trino 数据库的完整巡检流程。
        预先设置能力探测缓存，跳过 SQL 探测阶段。
        """
        connector = make_mock_connector(dialect="trino")
        inspector = GenericInspector(connector)

        # 预先设定能力探测缓存，跳过 SQL 探测阶段
        inspector._capabilities = {
            "information_schema": True,
            "pg_stat_activity": False,
            "performance_schema": False,
            "v$session": False,
            "sys.dm_exec_sessions": False,
            "pragma": False,
            "version_query": True,
        }
        inspector._version_cache = "Trino 400"

        # 配置所有查询的返回值（信息较全的路径）
        # _get_connection_count -> information_schema 路径会尝试 2 个查询
        # _get_database_size_mb -> information_schema 路径 1 个查询
        # _get_index_count -> information_schema 路径 1 个查询
        side_effects = [
            # ---- inspect_configuration (3 queries) ----
            MockResult([(3,)]),              # Schema 数量
            MockResult([(28,)]),             # 表总数
            MockResult([]),                  # ENGINE（Trino 无 ENGINE 信息）
            # ---- inspect_performance ----
            # _get_connection_count 的 2 个 INFORMATION_SCHEMA 查询
            Exception("not supported"),      # PROCESSLIST 路径
            Exception("not supported"),      # SESSION_STATUS 路径
            # TOP 大表查询
            Exception("not supported"),      # Trino TABLE_ROWS 不可用
            # ---- inspect_storage ----
            Exception("not supported"),      # _get_database_size_mb MySQL 路径
            MockResult([(28,)]),             # 表数量
            MockResult([(45,)]),             # 索引数量
            # ---- inspect_security (1 query) ----
            MockResult([("trino_user",)]),   # CURRENT_USER
            # ---- inspect_capacity (1 query) ----
            Exception("not supported"),      # _get_database_size_mb 路径
        ]
        connector.execute.side_effect = side_effects

        # 1. 配置检查
        config_items = inspector.inspect_configuration()
        self.assertGreaterEqual(len(config_items), 3,
                                "配置检查应返回至少 3 个检查项")

        # 2. 性能检查
        perf_items = inspector.inspect_performance()
        self.assertGreaterEqual(len(perf_items), 2,
                                "性能检查应返回至少 2 个检查项")

        # 3. 存储检查
        storage_items = inspector.inspect_storage()
        self.assertGreaterEqual(len(storage_items), 2,
                                "存储检查应返回至少 2 个检查项")

        # 4. 安全检查
        sec_items = inspector.inspect_security()
        self.assertEqual(len(sec_items), 2,
                         "安全检查应返回 2 个检查项")

        # 5. 容量检查
        cap_items = inspector.inspect_capacity()
        self.assertEqual(len(cap_items), 2,
                         "容量检查应返回 2 个检查项")

        # 所有检查项合计应不少于 11 项
        total_items = (
            len(config_items)
            + len(perf_items)
            + len(storage_items)
            + len(sec_items)
            + len(cap_items)
        )
        self.assertGreaterEqual(total_items, 11,
                                f"全部检查项合计应 >= 11，实际 {total_items}")


if __name__ == "__main__":
    unittest.main()