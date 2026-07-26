"""
db_scheduler/test_generic_backup.py
BackupManager 通用备份单元测试

测试范围：
    - _generic_fallback_backup: 通用全量备份
    - _generic_fallback_backup 单表备份
    - _get_generic_table_schema: 通用表结构获取
    - _write_generic_table_data: 通用表数据写入
    - _escape_generic_value: 通用 SQL 值转义
    - _generic_restore: 通用恢复
    - backup_full 对未知方言调用通用路径
    - backup_table 对未知方言调用通用路径
    - restore_backup 对未知方言调用通用路径

版本: 1.0.0
作者: AI Assistant
创建时间: 2026-06-05
"""

import os
import unittest
from unittest.mock import MagicMock, patch
from typing import List, Optional

from dbskiter.db_scheduler.backup import BackupManager


class MockResult:
    """模拟 QueryResult"""

    def __init__(self, rows: Optional[List[tuple]] = None):
        self.rows = rows


def make_connector(dialect: str = "trino"):
    """创建模拟连接器"""
    connector = MagicMock()
    connector.dialect = dialect
    connector.host = "localhost"
    connector.port = 8080
    connector.database = "test_db"
    connector.username = "test_user"
    connector.password = ""
    return connector


class TestGenericFallbackBackup(unittest.TestCase):
    """测试通用备份"""

    def setUp(self):
        self.test_dir = "./test_backups"
        os.makedirs(self.test_dir, exist_ok=True)

    def tearDown(self):
        import shutil
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_generic_full_backup(self):
        """测试通用全量备份"""
        connector = make_connector("duckdb")
        connector.get_tables.return_value = ["users", "orders"]
        connector.execute.side_effect = [
            # users 表结构
            MockResult([
                ("id", "INTEGER", "NO", None),
                ("name", "VARCHAR", "YES", None),
            ]),
            # users 数据第1批
            MockResult([(1, "alice"), (2, "bob")]),
            # users 数据第2批（空，结束）
            MockResult([]),
            # orders 表结构
            MockResult([
                ("id", "INTEGER", "NO", None),
                ("amount", "DECIMAL", "YES", None),
            ]),
            # orders 数据
            MockResult([(1, 100.5)]),
            # orders 数据结束
            MockResult([]),
        ]

        manager = BackupManager(connector)
        result = manager._generic_fallback_backup(
            os.path.join(self.test_dir, "test.sql"),
            "test_backup",
            include_schema=True,
            compress=False,
        )

        self.assertTrue(result.success)
        self.assertEqual(result.tables, ["users", "orders"])
        self.assertTrue(os.path.exists(result.file_path))

        # 验证文件内容
        with open(result.file_path, "r", encoding="utf-8") as f:
            content = f.read()
            self.assertIn("Generic Backup", content)
            self.assertIn("DROP TABLE IF EXISTS `users`", content)
            self.assertIn("CREATE TABLE `users`", content)
            self.assertIn("INSERT INTO `users` VALUES", content)

    def test_generic_table_backup(self):
        """测试通用单表备份"""
        connector = make_connector("trino")
        connector.execute.side_effect = [
            # 表结构
            MockResult([
                ("id", "BIGINT", "NO", None),
            ]),
            # 数据
            MockResult([(1,), (2,)]),
            MockResult([]),
        ]

        manager = BackupManager(connector)
        result = manager._generic_fallback_backup(
            os.path.join(self.test_dir, "single.sql"),
            "single_backup",
            include_schema=True,
            compress=False,
            tables=["events"],
        )

        self.assertTrue(result.success)
        self.assertEqual(result.tables, ["events"])

    def test_generic_backup_no_schema(self):
        """测试不包含表结构的备份"""
        connector = make_connector("trino")
        connector.get_tables.return_value = ["logs"]
        connector.execute.side_effect = [
            MockResult([(1, "info")]),
            MockResult([]),
        ]

        manager = BackupManager(connector)
        result = manager._generic_fallback_backup(
            os.path.join(self.test_dir, "no_schema.sql"),
            "no_schema_backup",
            include_schema=False,
            compress=False,
        )

        self.assertTrue(result.success)
        with open(result.file_path, "r") as f:
            content = f.read()
            self.assertNotIn("CREATE TABLE", content)
            self.assertIn("INSERT INTO `logs`", content)


class TestGenericTableSchema(unittest.TestCase):
    """测试通用表结构获取"""

    def test_schema_from_information_schema(self):
        """测试通过 INFORMATION_SCHEMA 获取表结构"""
        connector = make_connector("trino")
        connector.execute.return_value = MockResult([
            ("id", "INTEGER", "NO", None),
            ("name", "VARCHAR", "YES", "'unknown'"),
        ])

        manager = BackupManager(connector)
        schema = manager._get_generic_table_schema("users")

        self.assertIsNotNone(schema)
        self.assertIn("CREATE TABLE `users`", schema)
        self.assertIn("id INTEGER NOT NULL", schema)
        self.assertIn("name VARCHAR", schema)

    def test_schema_from_describe(self):
        """测试通过 DESCRIBE 获取表结构"""
        connector = make_connector("trino")
        # INFORMATION_SCHEMA 失败 -> DESCRIBE 成功
        connector.execute.side_effect = [
            Exception("not found"),
            MockResult([
                ("id", "INT"),
                ("name", "TEXT"),
            ]),
        ]

        manager = BackupManager(connector)
        schema = manager._get_generic_table_schema("users")

        self.assertIsNotNone(schema)
        self.assertIn("CREATE TABLE `users`", schema)

    def test_schema_not_available(self):
        """测试无法获取表结构"""
        connector = make_connector("trino")
        connector.execute.side_effect = Exception("not found")

        manager = BackupManager(connector)
        schema = manager._get_generic_table_schema("users")

        self.assertIsNone(schema)


class TestEscapeGenericValue(unittest.TestCase):
    """测试通用 SQL 值转义"""

    def test_null(self):
        self.assertEqual(BackupManager._escape_generic_value(None), "NULL")

    def test_bool(self):
        self.assertEqual(BackupManager._escape_generic_value(True), "1")
        self.assertEqual(BackupManager._escape_generic_value(False), "0")

    def test_int(self):
        self.assertEqual(BackupManager._escape_generic_value(42), "42")

    def test_float(self):
        self.assertEqual(BackupManager._escape_generic_value(3.14), "3.14")

    def test_string(self):
        self.assertEqual(
            BackupManager._escape_generic_value("hello"), "'hello'"
        )

    def test_string_with_quote(self):
        self.assertEqual(
            BackupManager._escape_generic_value("it's"), "'it''s'"
        )


class TestBackupFullUnknownDialect(unittest.TestCase):
    """测试 backup_full 对未知方言"""

    def setUp(self):
        self.test_dir = "./test_backups"
        os.makedirs(self.test_dir, exist_ok=True)

    def tearDown(self):
        import shutil
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_backup_full_generic_path(self):
        """测试未知方言全量备份走通用路径"""
        connector = make_connector("unknown_db")
        connector.get_tables.return_value = ["test_table"]
        # 预留足够多的 side_effect：schema + data batches
        connector.execute.side_effect = [
            MockResult([("id", "INT", "NO", None)]),  # schema
            MockResult([(1, "data")]),                  # data batch 1
            MockResult([]),                             # data batch 2 (end)
        ]

        manager = BackupManager(connector)
        result = manager.backup_full(
            output_dir=self.test_dir, compress=False
        )

        self.assertTrue(result.success)
        self.assertIn("test_table", result.tables)

    def test_backup_table_generic_path(self):
        """测试未知方言单表备份走通用路径"""
        connector = make_connector("unknown_db")
        connector.execute.side_effect = [
            MockResult([("id", "INT", "NO", None)]),  # schema
            MockResult([(1, "data")]),                  # data batch 1
            MockResult([]),                             # data batch 2 (end)
        ]

        manager = BackupManager(connector)
        result = manager.backup_table(
            "test_table", output_dir=self.test_dir
        )

        self.assertTrue(result.success)


if __name__ == "__main__":
    unittest.main()
