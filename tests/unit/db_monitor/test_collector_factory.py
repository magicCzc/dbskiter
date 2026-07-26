"""
db_monitor/test_collector_factory.py
采集器工厂函数单元测试

测试范围:
    - get_collector 精确匹配
    - get_collector 前缀匹配（方言变体）
    - get_collector 子串匹配
    - get_collector 回退到 GenericMetricsCollector
    - 所有已知方言的映射

版本: 1.0.0
作者: AI Assistant
创建时间: 2026-06-05
"""

import unittest
from unittest.mock import MagicMock

from dbskiter.db_monitor.collectors import (
    get_collector,
    MySQLMetricsCollector,
    OracleMetricsCollector,
    PostgreSQLMetricsCollector,
    MSSQLMetricsCollector,
    ClickHouseMetricsCollector,
    SQLiteMetricsCollector,
    GenericMetricsCollector,
)


class TestGetCollector(unittest.TestCase):
    """测试 get_collector 工厂函数"""

    def setUp(self):
        """创建模拟连接器"""
        self.mock_connector = MagicMock()

    def test_exact_match_mysql(self):
        """测试精确匹配 mysql"""
        collector = get_collector("mysql", self.mock_connector)
        self.assertIsInstance(collector, MySQLMetricsCollector)

    def test_exact_match_mysql_pymysql(self):
        """测试精确匹配 mysql+pymysql"""
        collector = get_collector("mysql+pymysql", self.mock_connector)
        self.assertIsInstance(collector, MySQLMetricsCollector)

    def test_exact_match_oracle(self):
        """测试精确匹配 oracle"""
        collector = get_collector("oracle", self.mock_connector)
        self.assertIsInstance(collector, OracleMetricsCollector)

    def test_exact_match_postgresql(self):
        """测试精确匹配 postgresql"""
        collector = get_collector("postgresql", self.mock_connector)
        self.assertIsInstance(collector, PostgreSQLMetricsCollector)

    def test_exact_match_mssql(self):
        """测试精确匹配 mssql"""
        collector = get_collector("mssql", self.mock_connector)
        self.assertIsInstance(collector, MSSQLMetricsCollector)

    def test_exact_match_clickhouse(self):
        """测试精确匹配 clickhouse"""
        collector = get_collector("clickhouse", self.mock_connector)
        self.assertIsInstance(collector, ClickHouseMetricsCollector)

    def test_exact_match_sqlite(self):
        """测试精确匹配 sqlite"""
        collector = get_collector("sqlite", self.mock_connector)
        self.assertIsInstance(collector, SQLiteMetricsCollector)

    def test_prefix_match_mysql_variant(self):
        """测试前缀匹配 mysql+未知驱动"""
        collector = get_collector("mysql+mysqlconnector", self.mock_connector)
        self.assertIsInstance(collector, MySQLMetricsCollector)

    def test_prefix_match_postgresql_variant(self):
        """测试前缀匹配 postgresql+未知驱动"""
        collector = get_collector("postgresql+pg8000", self.mock_connector)
        self.assertIsInstance(collector, PostgreSQLMetricsCollector)

    def test_substring_match_postgres(self):
        """测试子串匹配 postgres（非 postgresql）"""
        collector = get_collector("postgres", self.mock_connector)
        self.assertIsInstance(collector, PostgreSQLMetricsCollector)

    def test_substring_match_sqlserver(self):
        """测试子串匹配 sqlserver"""
        collector = get_collector("sqlserver", self.mock_connector)
        self.assertIsInstance(collector, MSSQLMetricsCollector)

    def test_fallback_generic_trino(self):
        """测试未知方言 trino 回退到 Generic"""
        collector = get_collector("trino", self.mock_connector)
        self.assertIsInstance(collector, GenericMetricsCollector)

    def test_fallback_generic_duckdb(self):
        """测试未知方言 duckdb 回退到 Generic"""
        collector = get_collector("duckdb", self.mock_connector)
        self.assertIsInstance(collector, GenericMetricsCollector)

    def test_fallback_generic_h2(self):
        """测试未知方言 h2 回退到 Generic"""
        collector = get_collector("h2", self.mock_connector)
        self.assertIsInstance(collector, GenericMetricsCollector)

    def test_fallback_generic_unknown(self):
        """测试完全未知方言回退到 Generic"""
        collector = get_collector("some_unknown_db", self.mock_connector)
        self.assertIsInstance(collector, GenericMetricsCollector)

    def test_case_insensitive(self):
        """测试大小写不敏感"""
        collector1 = get_collector("MySQL", self.mock_connector)
        collector2 = get_collector("MYSQL", self.mock_connector)
        collector3 = get_collector("mysql", self.mock_connector)

        self.assertIsInstance(collector1, MySQLMetricsCollector)
        self.assertIsInstance(collector2, MySQLMetricsCollector)
        self.assertIsInstance(collector3, MySQLMetricsCollector)

    def test_all_known_dialects(self):
        """测试所有已知方言都能正确映射"""
        from dbskiter.db_monitor.collectors import KNOWN_COLLECTORS

        for dialect, expected_class in KNOWN_COLLECTORS.items():
            with self.subTest(dialect=dialect):
                collector = get_collector(dialect, self.mock_connector)
                self.assertIsInstance(
                    collector, expected_class,
                    f"方言 {dialect} 应该映射到 {expected_class.__name__}"
                )


if __name__ == "__main__":
    unittest.main()
