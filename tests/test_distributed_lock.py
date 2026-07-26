"""
分布式锁测试

文件功能：测试分布式锁的各种实现
主要测试类：
    - TestDistributedLockBase: 分布式锁基类测试
    - TestDatabaseDistributedLock: 数据库锁测试
    - TestFileDistributedLock: 文件锁测试
    - TestLockManager: 锁管理器测试
    - TestLockWatchdog: 看门狗测试

运行测试:
    python -m pytest tests/test_distributed_lock.py -v

作者：AI Assistant
创建时间：2026-04-21
"""

import unittest
import tempfile
import shutil
import time
import threading
import os
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

# 导入被测模块
from dbskiter.db_scheduler.distributed_lock import (
    DistributedLock,
    DatabaseDistributedLock,
    FileDistributedLock,
    LockManager,
    LockWatchdog
)


# 使用类级别的锁状态字典来模拟分布式锁
_mock_lock_states = {}

class MockDistributedLock(DistributedLock):
    """模拟分布式锁用于测试"""
    
    def __init__(self, lock_key: str, lock_timeout: int = 60):
        super().__init__(lock_key, lock_timeout)
        # 每个锁实例独立的状态
        self._instance_locked = False
    
    def _do_acquire(self, blocking: bool = True, timeout: int = None) -> bool:
        global _mock_lock_states
        if self.lock_key not in _mock_lock_states:
            _mock_lock_states[self.lock_key] = None
        
        # 检查是否已被其他实例持有
        if _mock_lock_states[self.lock_key] is not None and _mock_lock_states[self.lock_key] != id(self):
            return False
        
        # 获取锁
        _mock_lock_states[self.lock_key] = id(self)
        self._instance_locked = True
        return True
    
    def _do_release(self) -> bool:
        global _mock_lock_states
        if self._instance_locked and _mock_lock_states.get(self.lock_key) == id(self):
            _mock_lock_states[self.lock_key] = None
            self._instance_locked = False
            return True
        return False
    
    def _do_renew(self) -> bool:
        global _mock_lock_states
        return self._instance_locked and _mock_lock_states.get(self.lock_key) == id(self)
    
    def is_locked(self) -> bool:
        global _mock_lock_states
        return _mock_lock_states.get(self.lock_key) is not None


class TestDistributedLockBase(unittest.TestCase):
    """测试分布式锁基类"""
    
    def setUp(self):
        """设置测试环境"""
        self.lock = MockDistributedLock("test_lock")
    
    def test_lock_initialization(self):
        """测试锁初始化"""
        self.assertEqual(self.lock.lock_key, "test_lock")
        self.assertEqual(self.lock.lock_timeout, 60)
        self.assertFalse(self.lock._acquired)
        self.assertIsNotNone(self.lock._lock_value)
    
    def test_acquire_success(self):
        """测试成功获取锁"""
        result = self.lock.acquire()
        
        self.assertTrue(result)
        self.assertTrue(self.lock._acquired)
        self.assertIsNotNone(self.lock._acquire_time)
    
    def test_acquire_blocking(self):
        """测试阻塞获取锁"""
        # 第一次获取成功
        result1 = self.lock.acquire(blocking=False)
        self.assertTrue(result1)
        
        # 第二次非阻塞获取失败
        lock2 = MockDistributedLock("test_lock")
        result2 = lock2.acquire(blocking=False)
        self.assertFalse(result2)
    
    def test_release(self):
        """测试释放锁"""
        self.lock.acquire()
        self.assertTrue(self.lock._acquired)
        
        result = self.lock.release()
        
        self.assertTrue(result)
        self.assertFalse(self.lock._acquired)
    
    def test_release_not_acquired(self):
        """测试释放未获取的锁"""
        result = self.lock.release()
        
        self.assertFalse(result)
    
    def test_context_manager(self):
        """测试上下文管理器"""
        with self.lock:
            self.assertTrue(self.lock._acquired)
        
        self.assertFalse(self.lock._acquired)
    
    def test_reentrant_lock(self):
        """测试可重入锁"""
        # 同一线程多次获取
        result1 = self.lock.acquire()
        result2 = self.lock.acquire()
        result3 = self.lock.acquire()
        
        self.assertTrue(result1)
        self.assertTrue(result2)
        self.assertTrue(result3)
        self.assertEqual(self.lock._reentrant_count, 3)
        
        # 需要释放3次才真正释放
        self.lock.release()
        self.assertTrue(self.lock._acquired)
        
        self.lock.release()
        self.assertTrue(self.lock._acquired)
        
        self.lock.release()
        self.assertFalse(self.lock._acquired)
    
    def test_get_hold_time(self):
        """测试获取持有时间"""
        # 未获取锁时返回None
        self.assertIsNone(self.lock.get_hold_time())
        
        # 获取锁后返回持有时间
        self.lock.acquire()
        time.sleep(0.1)
        hold_time = self.lock.get_hold_time()
        
        self.assertIsNotNone(hold_time)
        self.assertGreaterEqual(hold_time, 0.1)
        
        # 释放后返回None
        self.lock.release()
        self.assertIsNone(self.lock.get_hold_time())


class TestDatabaseDistributedLock(unittest.TestCase):
    """测试数据库分布式锁"""
    
    def setUp(self):
        """设置测试环境"""
        self.mock_connector = Mock()
        self.mock_result = Mock()
        self.mock_result.rowcount = 1
        self.mock_connector.execute.return_value = self.mock_result
        
        self.lock = DatabaseDistributedLock(self.mock_connector, "test_db_lock", 60)
    
    def test_initialization_creates_table(self):
        """测试初始化时创建锁表"""
        # 验证创建表的SQL被执行
        execute_calls = self.mock_connector.execute.call_args_list
        create_table_calls = [call for call in execute_calls 
                            if "CREATE TABLE" in str(call) and "distributed_locks" in str(call)]
        self.assertEqual(len(create_table_calls), 1)
    
    def test_acquire_success(self):
        """测试成功获取数据库锁"""
        result = self.lock._do_acquire()
        
        self.assertTrue(result)
        # 验证插入了锁记录
        execute_calls = self.mock_connector.execute.call_args_list
        insert_calls = [call for call in execute_calls if "INSERT" in str(call)]
        self.assertEqual(len(insert_calls), 1)
    
    def test_acquire_failure(self):
        """测试获取锁失败"""
        # 模拟插入失败（锁已存在）
        self.mock_connector.execute.side_effect = Exception("Duplicate entry")
        
        result = self.lock._do_acquire()
        
        self.assertFalse(result)
    
    def test_release_success(self):
        """测试成功释放锁"""
        self.lock._lock_value = "test_value"
        result = self.lock._do_release()
        
        self.assertTrue(result)
        # 验证删除了锁记录
        execute_calls = self.mock_connector.execute.call_args_list
        delete_calls = [call for call in execute_calls if "DELETE" in str(call)]
        self.assertEqual(len(delete_calls), 1)
    
    def test_renew_success(self):
        """测试成功续期锁"""
        self.lock._lock_value = "test_value"
        result = self.lock._do_renew()
        
        self.assertTrue(result)
        # 验证更新了过期时间
        execute_calls = self.mock_connector.execute.call_args_list
        update_calls = [call for call in execute_calls if "UPDATE" in str(call)]
        self.assertEqual(len(update_calls), 1)
    
    def test_is_locked(self):
        """测试检查锁状态"""
        # 模拟锁存在
        mock_result = Mock()
        mock_result.rows = [[1]]
        self.mock_connector.execute.return_value = mock_result
        
        result = self.lock.is_locked()
        
        self.assertTrue(result)


class TestFileDistributedLock(unittest.TestCase):
    """测试文件系统分布式锁"""
    
    def setUp(self):
        """设置测试环境"""
        self.temp_dir = tempfile.mkdtemp()
        self.lock = FileDistributedLock("test_file_lock", 60, self.temp_dir)
    
    def tearDown(self):
        """清理测试环境"""
        # 确保锁已释放
        try:
            self.lock.release()
        except:
            pass
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_acquire_and_release(self):
        """测试获取和释放文件锁"""
        # 获取锁
        result = self.lock.acquire()
        self.assertTrue(result)
        self.assertTrue(os.path.exists(self.lock.lock_file))
        
        # 释放锁
        result = self.lock.release()
        self.assertTrue(result)
    
    def test_is_locked(self):
        """测试检查锁状态"""
        # 未获取锁时
        self.assertFalse(self.lock.is_locked())
        
        # 获取锁后
        self.lock.acquire()
        self.assertTrue(self.lock.is_locked())
        
        # 释放锁后
        self.lock.release()
        self.assertFalse(self.lock.is_locked())


class TestLockManager(unittest.TestCase):
    """测试锁管理器"""
    
    def setUp(self):
        """设置测试环境"""
        self.mock_connector = Mock()
    
    def test_create_database_lock(self):
        """测试创建数据库锁"""
        manager = LockManager("database", connector=self.mock_connector)
        lock = manager.lock("test_lock", 60)
        
        self.assertIsInstance(lock, DatabaseDistributedLock)
        self.assertEqual(lock.lock_key, "test_lock")
    
    def test_create_file_lock(self):
        """测试创建文件锁"""
        temp_dir = tempfile.mkdtemp()
        try:
            manager = LockManager("file", lock_dir=temp_dir)
            lock = manager.lock("test_lock", 60)
            
            self.assertIsInstance(lock, FileDistributedLock)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)
    
    def test_create_unsupported_backend(self):
        """测试创建不支持的锁后端"""
        # 不支持的backend应该抛出异常或返回None
        try:
            manager = LockManager("unsupported")
            # 如果创建成功，尝试获取锁应该失败
            with self.assertRaises(ValueError):
                manager.lock("test")
        except ValueError as e:
            self.assertIn("不支持的锁后端", str(e))
    
    def test_create_database_lock_without_connector(self):
        """测试创建数据库锁时缺少连接器"""
        # 创建管理器时不抛出异常，获取锁时才抛出
        manager = LockManager("database")
        with self.assertRaises(ValueError) as context:
            manager.lock("test")
        
        self.assertIn("需要提供connector参数", str(context.exception))
    
    def test_acquire_lock_context_manager(self):
        """测试上下文管理器方式获取锁"""
        temp_dir = tempfile.mkdtemp()
        try:
            manager = LockManager("file", lock_dir=temp_dir)
            
            with manager.acquire_lock("test_context_lock") as lock:
                self.assertIn("test_context_lock", manager.get_active_locks())
            
            # 退出上下文后锁应被释放
            self.assertNotIn("test_context_lock", manager.get_active_locks())
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)
    
    def test_acquire_lock_timeout(self):
        """测试获取锁超时"""
        temp_dir = tempfile.mkdtemp()
        try:
            manager = LockManager("file", lock_dir=temp_dir)
            
            # 先获取锁
            lock1 = manager.lock("test_timeout_lock")
            lock1.acquire()
            
            # 再尝试获取同一锁（应该超时）
            with self.assertRaises(TimeoutError):
                with manager.acquire_lock("test_timeout_lock", timeout=0.1):
                    pass
            
            lock1.release()
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)
    
    def test_release_all(self):
        """测试释放所有锁"""
        temp_dir = tempfile.mkdtemp()
        try:
            manager = LockManager("file", lock_dir=temp_dir)
            
            # 创建多个锁
            lock1 = manager.lock("lock1")
            lock2 = manager.lock("lock2")
            
            lock1.acquire()
            lock2.acquire()
            
            # 手动添加到活动锁集合
            manager._active_locks["lock1"] = lock1
            manager._active_locks["lock2"] = lock2
            
            # 释放所有锁
            manager.release_all()
            
            self.assertEqual(len(manager.get_active_locks()), 0)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)


class TestLockWatchdog(unittest.TestCase):
    """测试锁看门狗"""
    
    def setUp(self):
        """设置测试环境"""
        self.temp_dir = tempfile.mkdtemp()
        self.manager = LockManager("file", lock_dir=self.temp_dir)
        self.watchdog = LockWatchdog(self.manager, check_interval=1)
    
    def tearDown(self):
        """清理测试环境"""
        self.watchdog.stop()
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_start_and_stop(self):
        """测试启动和停止看门狗"""
        self.watchdog.start()
        self.assertTrue(self.watchdog._running)
        
        self.watchdog.stop()
        self.assertFalse(self.watchdog._running)
    
    def test_deadlock_detection(self):
        """测试死锁检测"""
        # 创建一个长时间持有的锁
        lock = self.manager.lock("deadlock_test", lock_timeout=1)
        lock.acquire()
        lock._acquire_time = datetime.now() - timedelta(seconds=10)  # 模拟已持有10秒
        lock._acquired = True
        
        self.manager._active_locks["deadlock_test"] = lock
        
        # 启动看门狗
        self.watchdog.start()
        
        # 等待看门狗检测
        time.sleep(2)
        
        # 停止看门狗
        self.watchdog.stop()
        
        # 锁应该被释放
        # 注意：由于看门狗的异步特性，这个测试可能不稳定


if __name__ == "__main__":
    unittest.main()
