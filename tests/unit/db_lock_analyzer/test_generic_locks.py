"""
db_lock_analyzer/test_generic_locks.py
LockAnalyzerSkill._get_generic_locks 单元测试

测试范围：
    - 通过 pg_locks 获取锁（PostgreSQL 风格）
    - 通过 innodb_trx 获取锁（MySQL 5.7 风格）
    - 通过 data_locks 获取锁（MySQL 8.0 风格）
    - 通过 dm_tran_locks 获取锁（SQL Server 风格）
    - 通过 system.processes 获取锁（ClickHouse 风格）
    - 全部视图不可用返回空列表
    - analyze_current_locks 对未知方言调用通用路径

版本: 1.0.0
作者: AI Assistant
创建时间: 2026-06-05
"""

import unittest
from unittest.mock import MagicMock, patch
from typing import List, Optional

from dbskiter.db_lock_analyzer.skill import LockAnalyzerSkill
from dbskiter.db_lock_analyzer.models import LockInfo, LockType, LockMode


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


class TestGenericLocksPgLocks(unittest.TestCase):
    """测试通过 pg_locks 获取锁"""

    def test_get_generic_locks_pg_locks(self):
        """测试 PostgreSQL pg_locks 路径成功"""
        connector = make_connector("trino")
        connector.execute.side_effect = [
            MockResult([                   # pg_locks 查询成功
                (
                    "relation",            # locktype
                    "public.users",        # relation::regclass
                    "RowExclusiveLock",    # mode
                    False,                 # granted
                    12345,                 # pid
                    "admin",               # usename
                    "192.168.1.1",         # client_addr
                    "UPDATE users SET ...", # query
                    None,                   # query_start
                    5.5,                    # wait_seconds
                ),
            ]),
        ]

        skill = LockAnalyzerSkill(connector)
        locks = skill._get_generic_locks()

        self.assertEqual(len(locks), 1)
        self.assertEqual(locks[0].lock_id, "PG-12345")
        self.assertEqual(locks[0].lock_status, "WAITING")
        self.assertEqual(locks[0].lock_mode, LockMode.EXCLUSIVE)

    def test_get_generic_locks_pg_locks_granted(self):
        """测试 pg_locks 返回已授予锁"""
        connector = make_connector("trino")
        connector.execute.side_effect = [
            MockResult([
                (
                    "relation",
                    "public.orders",
                    "AccessShareLock",
                    True,                   # granted = true
                    12346,
                    "readonly",
                    None,
                    "SELECT * FROM orders",
                    None,
                    None,
                ),
            ]),
        ]

        skill = LockAnalyzerSkill(connector)
        locks = skill._get_generic_locks()

        self.assertEqual(len(locks), 1)
        self.assertEqual(locks[0].lock_status, "GRANTED")
        self.assertEqual(locks[0].lock_mode, LockMode.SHARED)


class TestGenericLocksInnodbTrx(unittest.TestCase):
    """测试通过 innodb_trx 获取锁"""

    def test_get_generic_locks_innodb_trx(self):
        """测试 MySQL 5.7 innodb_trx 路径成功（pg_locks 失败后）"""
        connector = make_connector("trino")
        # pg_locks 失败 -> innodb_trx 成功
        connector.execute.side_effect = [
            Exception("relation not found"),  # pg_locks
            MockResult([                      # innodb_trx
                (
                    "TRX123",               # trx_id
                    101,                    # trx_mysql_thread_id
                    "RUNNING",              # trx_state
                    2,                      # trx_tables_locked
                    50,                     # trx_rows_locked
                    None,                    # trx_started
                    "X",                    # lock_mode
                    "RECORD",               # lock_type
                    "`test`.`users`",       # lock_table
                    "PRIMARY",              # lock_index
                    "1001",                 # lock_data
                    "TRX123",               # requesting_trx_id
                    None,                    # blocking_trx_id
                    10,                     # trx_seconds
                ),
            ]),
        ]

        skill = LockAnalyzerSkill(connector)
        locks = skill._get_generic_locks()

        self.assertEqual(len(locks), 1)
        self.assertEqual(locks[0].transaction_id, "TRX123")
        self.assertEqual(locks[0].thread_id, 101)
        self.assertEqual(locks[0].lock_status, "WAITING")


class TestGenericLocksDmTranLocks(unittest.TestCase):
    """测试通过 dm_tran_locks 获取锁"""

    def test_get_generic_locks_dm_tran_locks(self):
        """测试 SQL Server dm_tran_locks 路径成功"""
        connector = make_connector("trino")
        # pg_locks 失败 -> innodb_trx 失败 -> data_locks 失败 -> dm_tran_locks 成功
        connector.execute.side_effect = [
            Exception("not found"),       # pg_locks
            Exception("not found"),       # innodb_trx
            Exception("not found"),       # data_locks
            MockResult([                   # dm_tran_locks
                (
                    55,                 # request_session_id
                    "OBJECT",           # resource_type
                    "X",                # request_mode
                    "GRANT",            # request_status
                    "WORKSTATION1",     # host_name
                    "sa",               # login_name
                    None,               # wait_time
                    "UPDATE users ...", # sql_text
                ),
            ]),
        ]

        skill = LockAnalyzerSkill(connector)
        locks = skill._get_generic_locks()

        self.assertEqual(len(locks), 1)
        self.assertEqual(locks[0].lock_id, "MSSQL-55-OBJECT")
        self.assertEqual(locks[0].lock_status, "GRANTED")

    def test_get_generic_locks_dm_tran_wait(self):
        """测试 dm_tran_locks 返回等待状态"""
        connector = make_connector("trino")
        connector.execute.side_effect = [
            Exception("not found"),
            Exception("not found"),
            Exception("not found"),
            MockResult([
                (
                    56,
                    "PAGE",
                    "S",
                    "WAIT",              # WAIT 状态
                    "WORKSTATION2",
                    "app_user",
                    5000,                # wait_time ms
                    "SELECT * FROM big_table",
                ),
            ]),
        ]

        skill = LockAnalyzerSkill(connector)
        locks = skill._get_generic_locks()

        self.assertEqual(len(locks), 1)
        self.assertEqual(locks[0].lock_status, "WAITING")
        self.assertAlmostEqual(locks[0].wait_time, 5.0, places=1)


class TestGenericLocksClickHouse(unittest.TestCase):
    """测试通过 system.processes 获取锁"""

    def test_get_generic_locks_clickhouse(self):
        """测试 ClickHouse system.processes 路径成功"""
        connector = make_connector("trino")
        connector.execute.side_effect = [
            Exception("not found"),       # pg_locks
            Exception("not found"),       # innodb_trx
            Exception("not found"),       # data_locks
            Exception("not found"),       # dm_tran_locks
            MockResult([                   # system.processes
                (
                    "query-abc-123",    # query_id
                    "default",          # user
                    "INSERT INTO logs...",  # query
                    12.5,               # elapsed
                    1000000,            # read_rows
                    500000,             # written_rows (有写入 = EXCLUSIVE)
                    1024000,            # memory_usage
                    False,              # is_cancelled
                ),
            ]),
        ]

        skill = LockAnalyzerSkill(connector)
        locks = skill._get_generic_locks()

        self.assertEqual(len(locks), 1)
        self.assertEqual(locks[0].lock_id, "CH-query-ab")
        self.assertEqual(locks[0].lock_mode, LockMode.EXCLUSIVE)
        self.assertEqual(locks[0].lock_status, "RUNNING")

    def test_get_generic_locks_clickhouse_readonly(self):
        """测试 ClickHouse 只读查询（SHARED 锁模式）"""
        connector = make_connector("trino")
        connector.execute.side_effect = [
            Exception("not found"),
            Exception("not found"),
            Exception("not found"),
            Exception("not found"),
            MockResult([
                (
                    "query-def-456",
                    "readonly",
                    "SELECT * FROM events",
                    3.2,
                    500000,
                    0,                  # written_rows = 0 = SHARED
                    512000,
                    False,
                ),
            ]),
        ]

        skill = LockAnalyzerSkill(connector)
        locks = skill._get_generic_locks()

        self.assertEqual(len(locks), 1)
        self.assertEqual(locks[0].lock_mode, LockMode.SHARED)


class TestGenericLocksFallback(unittest.TestCase):
    """测试回退到空列表"""

    def test_get_generic_locks_all_failed(self):
        """测试所有视图都不可用，返回空列表"""
        connector = make_connector("trino")
        connector.execute.side_effect = [
            Exception("not found"),
            Exception("not found"),
            Exception("not found"),
            Exception("not found"),
            Exception("not found"),
        ]

        skill = LockAnalyzerSkill(connector)
        locks = skill._get_generic_locks()

        self.assertEqual(len(locks), 0)


class TestAnalyzeCurrentLocksGeneric(unittest.TestCase):
    """测试 analyze_current_locks 调用通用路径"""

    def test_analyze_unknown_dialect(self):
        """测试未知方言调用通用锁分析"""
        connector = make_connector("trino")
        connector.execute.side_effect = [
            Exception("not found"),
            Exception("not found"),
            Exception("not found"),
            Exception("not found"),
            Exception("not found"),
        ]

        skill = LockAnalyzerSkill(connector)
        result = skill.analyze_current_locks()

        self.assertTrue(result["success"])
        self.assertEqual(result["data"]["count"], 0)
        self.assertIn("note", result["data"])

    def test_analyze_unknown_dialect_with_locks(self):
        """测试未知方言通过通用路径获取到锁"""
        connector = make_connector("unknown_db")
        connector.execute.side_effect = [
            MockResult([                   # pg_locks 成功
                (
                    "relation",
                    "public.users",
                    "RowExclusiveLock",
                    False,
                    12345,
                    "admin",
                    None,
                    "UPDATE users SET ...",
                    None,
                    2.5,
                ),
            ]),
        ]

        skill = LockAnalyzerSkill(connector)
        result = skill.analyze_current_locks()

        self.assertTrue(result["success"])
        self.assertEqual(result["data"]["count"], 1)
        self.assertEqual(len(result["data"]["locks"]), 1)


if __name__ == "__main__":
    unittest.main()
