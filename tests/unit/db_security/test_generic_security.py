"""
db_security/test_generic_security.py
SecurityAuditor 通用安全审计单元测试

测试范围：
    - _audit_generic_permissions: 通用权限审计
    - _audit_generic_config: 通用配置审计
    - audit_permissions 对未知方言调用通用路径
    - audit_config 对未知方言调用通用路径

版本: 1.0.0
作者: AI Assistant
创建时间: 2026-06-05
"""

import unittest
from unittest.mock import MagicMock
from typing import List, Optional

from dbskiter.db_security.utils import SecurityAuditor


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


class TestGenericPermissions(unittest.TestCase):
    """测试通用权限审计"""

    def test_generic_permissions_table_privileges(self):
        """测试通过 TABLE_PRIVILEGES 获取权限"""
        connector = make_connector("trino")
        connector.execute.side_effect = [
            MockResult([(25,)]),          # TABLE_PRIVILEGES count
            MockResult([("admin",)]),     # CURRENT_USER
            MockResult([(10,)]),          # public schema tables
        ]

        auditor = SecurityAuditor(connector)
        result = auditor._audit_generic_permissions()

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["total_users"], 25)
        self.assertEqual(result["risks_found"], 2)  # 超过20用户 + public schema

    def test_generic_permissions_no_data(self):
        """测试没有任何权限数据源可用"""
        connector = make_connector("unknown_db")
        connector.execute.side_effect = Exception("not supported")

        auditor = SecurityAuditor(connector)
        result = auditor._audit_generic_permissions()

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["total_users"], 0)
        self.assertEqual(result["risks_found"], 0)
        self.assertIn("通用权限审计器", result["message"])

    def test_generic_permissions_current_user_only(self):
        """测试仅通过当前用户查询获取信息"""
        connector = make_connector("trino")
        connector.execute.side_effect = [
            Exception("not found"),       # TABLE_PRIVILEGES
            MockResult([("admin",)]),     # CURRENT_USER
            Exception("not found"),       # pg_stat_activity
            Exception("not found"),       # processlist
            Exception("not found"),       # dm_exec_sessions
            MockResult([(5,)]),           # public schema tables
        ]

        auditor = SecurityAuditor(connector)
        result = auditor._audit_generic_permissions()

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["total_users"], 0)

    def test_audit_permissions_unknown_dialect(self):
        """测试未知方言调用通用权限审计"""
        connector = make_connector("duckdb")
        connector.execute.side_effect = [
            MockResult([(3,)]),           # TABLE_PRIVILEGES count
            MockResult([("admin",)]),     # CURRENT_USER
            MockResult([(2,)]),           # public schema tables
        ]

        auditor = SecurityAuditor(connector)
        result = auditor.audit_permissions()

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["total_users"], 3)


class TestGenericConfig(unittest.TestCase):
    """测试通用配置审计"""

    def test_generic_config_full(self):
        """测试完整的通用配置审计"""
        connector = make_connector("trino")
        connector.execute.side_effect = [
            MockResult([("Trino 400",)]),  # VERSION()
            MockResult([("test_db",)]),    # current_database
            MockResult([(5120.0,)]),       # 数据库大小
            MockResult([(42,)]),           # 表数量
        ]

        auditor = SecurityAuditor(connector)
        result = auditor._audit_generic_config()

        self.assertEqual(result["status"], "success")
        self.assertGreater(result["total_checks"], 0)

    def test_generic_config_no_data(self):
        """测试没有任何配置信息可用"""
        connector = make_connector("unknown_db")
        connector.execute.side_effect = Exception("not supported")

        auditor = SecurityAuditor(connector)
        result = auditor._audit_generic_config()

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["total_checks"], 0)
        self.assertIn("通用配置审计器", result["message"])

    def test_generic_config_large_db(self):
        """测试大数据库容量警告"""
        connector = make_connector("trino")
        connector.execute.side_effect = [
            MockResult([("Trino 400",)]),  # VERSION()
            MockResult([("test_db",)]),    # current_database
            MockResult([(15000.0,)]),      # 数据库大小 > 10000MB
            MockResult([(42,)]),           # 表数量
        ]

        auditor = SecurityAuditor(connector)
        result = auditor._audit_generic_config()

        self.assertEqual(result["status"], "success")
        self.assertGreater(result["risks_found"], 0)

    def test_generic_config_many_tables(self):
        """测试大量表警告"""
        connector = make_connector("trino")
        connector.execute.side_effect = [
            MockResult([("Trino 400",)]),  # VERSION()
            MockResult([("test_db",)]),    # current_database
            MockResult([(100.0,)]),        # 数据库大小正常
            MockResult([(600,)]),          # 表数量 > 500
        ]

        auditor = SecurityAuditor(connector)
        result = auditor._audit_generic_config()

        self.assertEqual(result["status"], "success")
        self.assertGreater(result["risks_found"], 0)

    def test_audit_config_unknown_dialect(self):
        """测试未知方言调用通用配置审计"""
        connector = make_connector("duckdb")
        connector.execute.side_effect = [
            MockResult([("DuckDB v0.10",)]),  # VERSION()
            MockResult([("test_db",)]),       # current_database
            MockResult([(100.0,)]),           # 数据库大小
            MockResult([(42,)]),              # 表数量
        ]

        auditor = SecurityAuditor(connector)
        result = auditor.audit_config()

        self.assertEqual(result["status"], "success")
        self.assertGreater(result["total_checks"], 0)


class TestDialectRouting(unittest.TestCase):
    """测试方言路由"""

    def test_mysql_dialect_uses_mysql_path(self):
        """测试 MySQL 方言使用专用路径"""
        connector = make_connector("mysql")
        connector.execute.return_value = MockResult([
            ("root", "localhost", "Y", "Y", "Y", "Y", "Y", "Y", "Y", "Y", "Y", "Y", "Y"),
        ])

        auditor = SecurityAuditor(connector)
        result = auditor.audit_permissions()

        self.assertEqual(result["status"], "success")
        # 验证调用了 mysql.user 查询
        call_args = connector.execute.call_args[0][0]
        self.assertIn("mysql.user", call_args)

    def test_postgresql_dialect_uses_pg_path(self):
        """测试 PostgreSQL 方言使用专用路径"""
        connector = make_connector("postgresql")
        connector.execute.side_effect = [
            MockResult([
                ("admin", "t", "t", "t", "t", "t"),
            ]),  # pg_roles
            MockResult([]),  # role_routine_grants
        ]

        auditor = SecurityAuditor(connector)
        result = auditor.audit_permissions()

        self.assertEqual(result["status"], "success")
        # 验证调用了 pg_roles 查询
        call_args = connector.execute.call_args_list[0][0][0]
        self.assertIn("pg_roles", call_args)


if __name__ == "__main__":
    unittest.main()
