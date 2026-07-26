"""
db_lock_analyzer/test_models.py
db_lock_analyzer 数据模型单元测试

测试范围:
    - ErrorCode错误码
    - ErrorMessage错误消息
    - 枚举类型
    - 数据类

版本: 1.0.0
作者: AI Assistant
创建时间: 2026-04-23
"""

import unittest
from datetime import datetime

from dbskiter.db_lock_analyzer.models import (
    ErrorCode,
    ErrorMessage,
    LockType,
    LockMode,
    LockInfo,
    DeadlockInfo,
    LockWaitNode,
    LockWaitChain,
    LockStatistics,
)
from dbskiter.shared.error_handler import create_success_response, create_error_response


class TestErrorCode(unittest.TestCase):
    """测试错误码体系"""

    def test_error_code_format(self):
        """测试错误码格式正确"""
        error_codes = [
            ErrorCode.SUCCESS,
            ErrorCode.UNKNOWN_ERROR,
            ErrorCode.LOCK_ANALYSIS_FAILED,
            ErrorCode.DEADLOCK_DETECTION_FAILED,
        ]

        for code in error_codes:
            self.assertTrue(code.startswith("LOCK"))
            self.assertEqual(len(code), 9)

    def test_error_code_uniqueness(self):
        """测试错误码唯一性"""
        error_codes = [
            ErrorCode.SUCCESS,
            ErrorCode.UNKNOWN_ERROR,
            ErrorCode.INVALID_PARAM,
            ErrorCode.CONNECTION_FAILED,
            ErrorCode.LOCK_ANALYSIS_FAILED,
        ]

        self.assertEqual(len(error_codes), len(set(error_codes)))


class TestErrorMessage(unittest.TestCase):
    """测试错误消息"""

    def test_get_message_exists(self):
        """测试获取存在的错误消息"""
        msg = ErrorMessage.get_message(ErrorCode.SUCCESS)
        self.assertEqual(msg, "操作成功")

    def test_get_message_not_exists(self):
        """测试获取不存在的错误消息"""
        msg = ErrorMessage.get_message("LOCK99999")
        self.assertIn("未知错误码", msg)


class TestLockType(unittest.TestCase):
    """测试锁类型枚举"""

    def test_type_values(self):
        """测试类型值"""
        self.assertEqual(LockType.TABLE.value, "table")
        self.assertEqual(LockType.ROW.value, "row")
        self.assertEqual(LockType.METADATA.value, "metadata")


class TestLockMode(unittest.TestCase):
    """测试锁模式枚举"""

    def test_mode_values(self):
        """测试模式值"""
        self.assertEqual(LockMode.SHARED.value, "shared")
        self.assertEqual(LockMode.EXCLUSIVE.value, "exclusive")
        self.assertEqual(LockMode.INTENTION_SHARED.value, "is")


class TestLockInfo(unittest.TestCase):
    """测试锁信息"""

    def test_lock_info_creation(self):
        """测试锁信息创建"""
        lock = LockInfo(
            lock_id="lock-001",
            transaction_id="tx-001",
            lock_type=LockType.ROW,
            lock_mode=LockMode.EXCLUSIVE,
            lock_status="GRANTED"
        )

        self.assertEqual(lock.lock_id, "lock-001")
        self.assertEqual(lock.lock_status, "GRANTED")

    def test_lock_info_to_dict(self):
        """测试转换为字典"""
        lock = LockInfo(
            lock_id="lock-001",
            transaction_id="tx-001",
            lock_type=LockType.TABLE,
            lock_mode=LockMode.SHARED,
            lock_status="WAITING",
            query_sql="SELECT * FROM users"
        )

        data = lock.to_dict()
        self.assertEqual(data["lock_id"], "lock-001")
        self.assertEqual(data["lock_status"], "WAITING")


class TestDeadlockInfo(unittest.TestCase):
    """测试死锁信息"""

    def test_deadlock_info_creation(self):
        """测试死锁信息创建"""
        deadlock = DeadlockInfo(
            deadlock_id="dl-001",
            detected_at=datetime.now(),
            transactions=[{"tx": "tx-1"}],
            victim_transaction="tx-1",
            resolution="建议重启"
        )

        self.assertEqual(deadlock.deadlock_id, "dl-001")

    def test_deadlock_info_to_dict(self):
        """测试转换为字典"""
        deadlock = DeadlockInfo(
            deadlock_id="dl-001",
            detected_at=datetime.now(),
            transactions=[],
            victim_transaction="",
            resolution=""
        )

        data = deadlock.to_dict()
        self.assertEqual(data["deadlock_id"], "dl-001")


class TestLockWaitNode(unittest.TestCase):
    """测试锁等待节点"""

    def test_node_creation(self):
        """测试节点创建"""
        node = LockWaitNode(
            transaction_id="tx-001",
            connection_id=123,
            wait_time=5.5,
            waiting_for="tx-002"
        )

        self.assertEqual(node.transaction_id, "tx-001")
        self.assertEqual(node.wait_time, 5.5)


class TestLockWaitChain(unittest.TestCase):
    """测试锁等待链"""

    def test_chain_creation(self):
        """测试链创建"""
        node = LockWaitNode(
            transaction_id="tx-001",
            connection_id=123,
            wait_time=5.0,
            waiting_for=None
        )

        chain = LockWaitChain(
            chain_id="chain-001",
            root_transaction="tx-001",
            nodes=[node],
            total_wait_time=5.0,
            depth=1
        )

        self.assertEqual(chain.chain_id, "chain-001")

    def test_chain_to_dict(self):
        """测试转换为字典"""
        node = LockWaitNode(
            transaction_id="tx-001",
            connection_id=123,
            wait_time=5.0,
            waiting_for=None
        )

        chain = LockWaitChain(
            chain_id="chain-001",
            root_transaction="tx-001",
            nodes=[node],
            total_wait_time=5.0,
            depth=1
        )

        data = chain.to_dict()
        self.assertEqual(data["chain_id"], "chain-001")
        self.assertEqual(data["depth"], 1)


class TestLockStatistics(unittest.TestCase):
    """测试锁统计信息"""

    def test_statistics_creation(self):
        """测试统计信息创建"""
        stats = LockStatistics(
            total_locks=100,
            waiting_locks=10,
            granted_locks=90,
            max_wait_time=30.5,
            avg_wait_time=5.2
        )

        self.assertEqual(stats.total_locks, 100)
        self.assertEqual(stats.waiting_locks, 10)

    def test_statistics_to_dict(self):
        """测试转换为字典"""
        stats = LockStatistics(
            total_locks=100,
            waiting_locks=10,
            granted_locks=90,
            row_locks=80,
            table_locks=20,
            max_wait_time=30.5,
            avg_wait_time=5.2,
            deadlock_count=0
        )

        data = stats.to_dict()
        self.assertEqual(data["total_locks"], 100)
        self.assertEqual(data["max_wait_time"], 30.5)


class TestResponseFunctions(unittest.TestCase):
    """测试响应函数"""

    def test_create_success_response(self):
        """测试创建成功响应"""
        response = create_success_response(
            data={"locks": []},
            message="获取成功"
        )

        self.assertTrue(response["success"])
        self.assertEqual(response["data"], {"locks": []})
        self.assertEqual(response["message"], "获取成功")

    def test_create_error_response(self):
        """测试创建错误响应"""
        response = create_error_response(
            "获取失败",
            error_code=ErrorCode.LOCK_ANALYSIS_FAILED,
            details={"reason": "timeout"}
        )

        self.assertFalse(response["success"])
        self.assertEqual(response["error"]["code"], ErrorCode.LOCK_ANALYSIS_FAILED)


if __name__ == "__main__":
    unittest.main()
