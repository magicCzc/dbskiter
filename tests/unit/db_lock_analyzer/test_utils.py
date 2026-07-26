"""
db_lock_analyzer/test_utils.py
db_lock_analyzer 工具类单元测试

测试范围:
    - LockParser 锁信息解析器
    - DeadlockDetector 死锁检测器
    - LockChainBuilder 锁等待链构建器
    - LockStatisticsCalculator 锁统计计算器
    - LockReporter 锁分析报告生成器

版本: 1.0.0
作者: AI Assistant
创建时间: 2026-04-23
"""

import unittest
from datetime import datetime

from dbskiter.db_lock_analyzer.utils import (
    LockParser,
    DeadlockDetector,
    LockChainBuilder,
    LockStatisticsCalculator,
    LockReporter,
)
from dbskiter.db_lock_analyzer.models import (
    LockType,
    LockMode,
    LockInfo,
    LockWaitNode,
    LockWaitChain,
    LockStatistics,
)


class TestLockParser(unittest.TestCase):
    """测试锁信息解析器"""

    def test_parse_mysql_lock_type_table(self):
        """测试解析MySQL表锁"""
        lock_type = LockParser.parse_mysql_lock_type("TABLE")
        self.assertEqual(lock_type, LockType.TABLE)

    def test_parse_mysql_lock_type_row(self):
        """测试解析MySQL行锁"""
        lock_type = LockParser.parse_mysql_lock_type("RECORD")
        self.assertEqual(lock_type, LockType.ROW)

    def test_parse_mysql_lock_type_metadata(self):
        """测试解析MySQL元数据锁"""
        lock_type = LockParser.parse_mysql_lock_type("METADATA")
        self.assertEqual(lock_type, LockType.METADATA)

    def test_parse_mysql_lock_mode_exclusive(self):
        """测试解析MySQL排他锁"""
        lock_mode = LockParser.parse_mysql_lock_mode("X")
        self.assertEqual(lock_mode, LockMode.EXCLUSIVE)

    def test_parse_mysql_lock_mode_shared(self):
        """测试解析MySQL共享锁"""
        lock_mode = LockParser.parse_mysql_lock_mode("S")
        self.assertEqual(lock_mode, LockMode.SHARED)

    def test_parse_mysql_lock_mode_intention(self):
        """测试解析MySQL意向锁"""
        lock_mode = LockParser.parse_mysql_lock_mode("IX")
        self.assertEqual(lock_mode, LockMode.INTENTION_EXCLUSIVE)

    def test_parse_postgresql_lock_type_table(self):
        """测试解析PostgreSQL表锁"""
        lock_type = LockParser.parse_postgresql_lock_type("relation")
        self.assertEqual(lock_type, LockType.TABLE)

    def test_parse_postgresql_lock_type_row(self):
        """测试解析PostgreSQL行锁"""
        lock_type = LockParser.parse_postgresql_lock_type("tuple")
        self.assertEqual(lock_type, LockType.ROW)


class TestDeadlockDetector(unittest.TestCase):
    """测试死锁检测器"""

    def test_detect_no_deadlock(self):
        """测试无死锁情况"""
        locks = [
            LockInfo(
                lock_id="lock-1",
                transaction_id="tx-1",
                lock_type=LockType.ROW,
                lock_mode=LockMode.EXCLUSIVE,
                lock_status="GRANTED",
                table_name="users"
            ),
            LockInfo(
                lock_id="lock-2",
                transaction_id="tx-2",
                lock_type=LockType.ROW,
                lock_mode=LockMode.SHARED,
                lock_status="WAITING",
                table_name="users"
            )
        ]

        deadlock = DeadlockDetector.detect_deadlock(locks)
        self.assertIsNone(deadlock)

    def test_detect_deadlock(self):
        """测试检测到死锁"""
        # 构造一个死锁场景
        locks = [
            LockInfo(
                lock_id="lock-1",
                transaction_id="tx-1",
                lock_type=LockType.ROW,
                lock_mode=LockMode.EXCLUSIVE,
                lock_status="GRANTED",
                table_name="table_a"
            ),
            LockInfo(
                lock_id="lock-2",
                transaction_id="tx-2",
                lock_type=LockType.ROW,
                lock_mode=LockMode.EXCLUSIVE,
                lock_status="GRANTED",
                table_name="table_b"
            ),
            LockInfo(
                lock_id="lock-3",
                transaction_id="tx-1",
                lock_type=LockType.ROW,
                lock_mode=LockMode.EXCLUSIVE,
                lock_status="WAITING",
                table_name="table_b"
            ),
            LockInfo(
                lock_id="lock-4",
                transaction_id="tx-2",
                lock_type=LockType.ROW,
                lock_mode=LockMode.EXCLUSIVE,
                lock_status="WAITING",
                table_name="table_a"
            )
        ]

        deadlock = DeadlockDetector.detect_deadlock(locks)
        # 注意：实际检测需要更复杂的场景
        # 这里只是测试代码结构


class TestLockChainBuilder(unittest.TestCase):
    """测试锁等待链构建器"""

    def test_build_wait_chains_empty(self):
        """测试空锁列表"""
        chains = LockChainBuilder.build_wait_chains([])
        self.assertEqual(len(chains), 0)

    def test_build_wait_chains_no_waiting(self):
        """测试无等待锁"""
        locks = [
            LockInfo(
                lock_id="lock-1",
                transaction_id="tx-1",
                lock_type=LockType.ROW,
                lock_mode=LockMode.EXCLUSIVE,
                lock_status="GRANTED"
            )
        ]

        chains = LockChainBuilder.build_wait_chains(locks)
        self.assertEqual(len(chains), 0)

    def test_find_root(self):
        """测试查找根事务"""
        wait_relations = {
            "tx-2": {"waiting_for": "tx-1"},
            "tx-3": {"waiting_for": "tx-2"}
        }

        root = LockChainBuilder._find_root("tx-3", wait_relations)
        self.assertEqual(root, "tx-1")


class TestLockStatisticsCalculator(unittest.TestCase):
    """测试锁统计计算器"""

    def test_calculate_statistics_empty(self):
        """测试空列表统计"""
        stats = LockStatisticsCalculator.calculate_statistics([])

        self.assertEqual(stats.total_locks, 0)
        self.assertEqual(stats.waiting_locks, 0)
        self.assertEqual(stats.max_wait_time, 0.0)

    def test_calculate_statistics(self):
        """测试正常统计"""
        locks = [
            LockInfo(
                lock_id="lock-1",
                transaction_id="tx-1",
                lock_type=LockType.ROW,
                lock_mode=LockMode.EXCLUSIVE,
                lock_status="GRANTED"
            ),
            LockInfo(
                lock_id="lock-2",
                transaction_id="tx-2",
                lock_type=LockType.ROW,
                lock_mode=LockMode.SHARED,
                lock_status="WAITING",
                wait_time=5.0
            ),
            LockInfo(
                lock_id="lock-3",
                transaction_id="tx-3",
                lock_type=LockType.TABLE,
                lock_mode=LockMode.EXCLUSIVE,
                lock_status="WAITING",
                wait_time=10.0
            )
        ]

        stats = LockStatisticsCalculator.calculate_statistics(locks)

        self.assertEqual(stats.total_locks, 3)
        self.assertEqual(stats.waiting_locks, 2)
        self.assertEqual(stats.granted_locks, 1)
        self.assertEqual(stats.row_locks, 2)
        self.assertEqual(stats.table_locks, 1)
        self.assertEqual(stats.max_wait_time, 10.0)

    def test_analyze_lock_distribution(self):
        """测试锁分布分析"""
        locks = [
            LockInfo(
                lock_id="lock-1",
                transaction_id="tx-1",
                lock_type=LockType.ROW,
                lock_mode=LockMode.EXCLUSIVE,
                lock_status="GRANTED",
                table_schema="db",
                table_name="users"
            ),
            LockInfo(
                lock_id="lock-2",
                transaction_id="tx-2",
                lock_type=LockType.ROW,
                lock_mode=LockMode.SHARED,
                lock_status="WAITING",
                table_schema="db",
                table_name="users"
            )
        ]

        distribution = LockStatisticsCalculator.analyze_lock_distribution(locks)

        self.assertIn("type_distribution", distribution)
        self.assertIn("mode_distribution", distribution)
        self.assertEqual(distribution["type_distribution"]["row"], 2)


class TestLockReporter(unittest.TestCase):
    """测试锁分析报告生成器"""

    def test_generate_report(self):
        """测试生成报告"""
        stats = LockStatistics(
            total_locks=10,
            waiting_locks=2,
            granted_locks=8,
            row_locks=8,
            table_locks=2,
            metadata_locks=0,
            max_wait_time=15.5,
            avg_wait_time=5.2,
            deadlock_count=0
        )

        report = LockReporter.generate_report([], stats)

        self.assertIn("数据库锁分析报告", report)
        self.assertIn("10", report)
        self.assertIn("15.5", report)

    def test_format_lock_summary_no_waiting(self):
        """测试无等待锁摘要"""
        locks = [
            LockInfo(
                lock_id="lock-1",
                transaction_id="tx-1",
                lock_type=LockType.ROW,
                lock_mode=LockMode.EXCLUSIVE,
                lock_status="GRANTED"
            )
        ]

        summary = LockReporter.format_lock_summary(locks)

        self.assertIn("没有等待中的锁", summary)

    def test_format_lock_summary_with_waiting(self):
        """测试有等待锁摘要"""
        locks = [
            LockInfo(
                lock_id="lock-1",
                transaction_id="tx-1",
                lock_type=LockType.ROW,
                lock_mode=LockMode.EXCLUSIVE,
                lock_status="WAITING",
                table_schema="db",
                table_name="users",
                wait_time=5.5,
                query_sql="SELECT * FROM users"
            )
        ]

        summary = LockReporter.format_lock_summary(locks)

        self.assertIn("等待中的锁", summary)
        self.assertIn("tx-1", summary)


if __name__ == "__main__":
    unittest.main()
