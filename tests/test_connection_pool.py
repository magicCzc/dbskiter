"""
连接池管理模块测试

文件功能：测试连接池的各种功能
主要测试类：
    - TestPoolConfig: 连接池配置测试
    - TestConnectionStats: 连接统计测试
    - TestPooledConnection: 连接包装类测试
    - TestConnectionPool: 连接池核心功能测试
    - TestConnectionPoolManager: 连接池管理器测试

运行测试:
    python -m pytest tests/test_connection_pool.py -v

作者：AI Assistant
创建时间：2026-04-21
"""

import unittest
import threading
import time
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

# 导入被测模块
from dbskiter.db_scheduler.connection_pool import (
    ConnectionState,
    PoolState,
    PoolConfig,
    ConnectionStats,
    PooledConnection,
    ConnectionPool,
    ConnectionPoolManager,
    create_pool,
    get_pool_manager
)


class TestPoolConfig(unittest.TestCase):
    """测试连接池配置"""
    
    def test_default_config(self):
        """测试默认配置"""
        config = PoolConfig()
        
        self.assertEqual(config.db_type, "mysql")
        self.assertEqual(config.host, "localhost")
        self.assertEqual(config.port, 3306)
        self.assertEqual(config.min_connections, 5)
        self.assertEqual(config.max_connections, 20)
        self.assertEqual(config.connection_timeout, 30)
        self.assertEqual(config.idle_timeout, 300)
    
    def test_custom_config(self):
        """测试自定义配置"""
        config = PoolConfig(
            db_type="postgresql",
            host="192.168.1.100",
            port=5432,
            database="test_db",
            user="admin",
            password="secret",
            min_connections=10,
            max_connections=50
        )
        
        self.assertEqual(config.db_type, "postgresql")
        self.assertEqual(config.host, "192.168.1.100")
        self.assertEqual(config.port, 5432)
        self.assertEqual(config.min_connections, 10)
        self.assertEqual(config.max_connections, 50)
    
    def test_config_to_dict(self):
        """测试配置转字典（密码隐藏）"""
        config = PoolConfig(password="secret123")
        data = config.to_dict()
        
        self.assertNotIn("password", data)
        self.assertEqual(data["host"], "localhost")
        self.assertEqual(data["db_type"], "mysql")


class TestConnectionStats(unittest.TestCase):
    """测试连接统计"""
    
    def test_stats_creation(self):
        """测试创建统计"""
        stats = ConnectionStats()
        
        self.assertEqual(stats.total_connections, 0)
        self.assertEqual(stats.idle_connections, 0)
        self.assertEqual(stats.busy_connections, 0)
        self.assertIsNotNone(stats.created_at)
    
    def test_stats_to_dict(self):
        """测试统计转字典"""
        stats = ConnectionStats(
            total_connections=10,
            idle_connections=5,
            busy_connections=5,
            total_requests=100
        )
        
        data = stats.to_dict()
        
        self.assertEqual(data["total_connections"], 10)
        self.assertEqual(data["idle_connections"], 5)
        self.assertEqual(data["busy_connections"], 5)
        self.assertEqual(data["total_requests"], 100)
        self.assertIn("created_at", data)


class TestPooledConnection(unittest.TestCase):
    """测试连接包装类"""
    
    def setUp(self):
        """设置测试环境"""
        self.mock_raw_conn = Mock()
        self.mock_pool = Mock()
        self.mock_pool.return_value = Mock()
        
        self.conn = PooledConnection(self.mock_raw_conn, self.mock_pool)
    
    def test_connection_initialization(self):
        """测试连接初始化"""
        self.assertEqual(self.conn.raw_connection, self.mock_raw_conn)
        self.assertEqual(self.conn.state, ConnectionState.IDLE)
        self.assertIsNotNone(self.conn.created_at)
        self.assertEqual(self.conn.borrow_count, 0)
    
    def test_mark_busy(self):
        """测试标记为使用中"""
        self.conn.mark_busy("test_thread")
        
        self.assertEqual(self.conn.state, ConnectionState.BUSY)
        self.assertEqual(self.conn.borrowed_by, "test_thread")
        self.assertEqual(self.conn.borrow_count, 1)
        self.assertIsNotNone(self.conn.borrowed_at)
    
    def test_mark_idle(self):
        """测试标记为空闲"""
        self.conn.mark_busy()
        self.conn.mark_idle()
        
        self.assertEqual(self.conn.state, ConnectionState.IDLE)
        self.assertIsNone(self.conn.borrowed_by)
        self.assertIsNone(self.conn.borrowed_at)
    
    def test_is_expired(self):
        """测试连接过期检查"""
        # 新连接未过期
        self.assertFalse(self.conn.is_expired(3600))
        
        # 修改创建时间为很久以前
        self.conn.created_at = datetime.now() - timedelta(seconds=4000)
        self.assertTrue(self.conn.is_expired(3600))
    
    def test_is_idle_timeout(self):
        """测试空闲超时检查"""
        # 使用中连接不检查空闲超时
        self.conn.mark_busy()
        self.assertFalse(self.conn.is_idle_timeout(60))
        
        # 空闲连接检查
        self.conn.mark_idle()
        self.conn.last_used_at = datetime.now() - timedelta(seconds=100)
        self.assertTrue(self.conn.is_idle_timeout(60))
    
    def test_is_leaked(self):
        """测试连接泄漏检查"""
        # 空闲连接不泄漏
        self.assertFalse(self.conn.is_leaked(60))
        
        # 使用中连接检查
        self.conn.mark_busy()
        self.conn.borrowed_at = datetime.now() - timedelta(seconds=100)
        self.assertTrue(self.conn.is_leaked(60))
    
    def test_close(self):
        """测试关闭连接"""
        self.conn.close()
        
        self.assertEqual(self.conn.state, ConnectionState.CLOSED)
        self.mock_raw_conn.close.assert_called_once()


class TestConnectionPool(unittest.TestCase):
    """测试连接池"""
    
    def setUp(self):
        """设置测试环境"""
        self.config = PoolConfig(
            db_type="mysql",
            host="localhost",
            port=3306,
            database="test",
            user="root",
            password="password",
            min_connections=2,
            max_connections=5,
            health_check_interval=0,  # 禁用健康检查线程
            enable_leak_detection=False  # 禁用泄漏检测
        )
    
    @patch.object(ConnectionPool, '_create_mysql_connection')
    def test_pool_initialization(self, mock_create):
        """测试连接池初始化"""
        mock_conn = Mock()
        mock_conn.ping.return_value = True
        mock_create.return_value = mock_conn
        
        pool = ConnectionPool(self.config)
        
        self.assertEqual(pool.state, PoolState.READY)
        self.assertEqual(pool._stats.total_connections, 2)  # 最小连接数
        
        pool.close()
    
    @patch.object(ConnectionPool, '_create_mysql_connection')
    def test_get_connection(self, mock_create):
        """测试获取连接"""
        mock_conn = Mock()
        mock_conn.ping.return_value = True
        mock_create.return_value = mock_conn
        
        pool = ConnectionPool(self.config)
        
        # 获取连接
        with pool.get_connection() as conn:
            self.assertIsNotNone(conn)
            self.assertEqual(pool._stats.busy_connections, 1)
            self.assertEqual(pool._stats.idle_connections, 1)
        
        # 归还后
        self.assertEqual(pool._stats.busy_connections, 0)
        self.assertEqual(pool._stats.idle_connections, 2)
        
        pool.close()
    
    @patch.object(ConnectionPool, '_create_mysql_connection')
    def test_connection_timeout(self, mock_create):
        """测试连接超时"""
        mock_conn = Mock()
        mock_conn.ping.return_value = True
        mock_create.return_value = mock_conn
        
        # 设置很小的最大连接数
        self.config.max_connections = 1
        self.config.min_connections = 1
        
        pool = ConnectionPool(self.config)
        
        # 占用唯一连接
        conn1 = pool._borrow_connection()
        
        # 再次获取应该超时
        with self.assertRaises(TimeoutError):
            with pool.get_connection(timeout=0.1) as conn:
                pass
        
        pool.release_connection(conn1)
        pool.close()
    
    @patch.object(ConnectionPool, '_create_mysql_connection')
    def test_pool_stats(self, mock_create):
        """测试连接池统计"""
        mock_conn = Mock()
        mock_conn.ping.return_value = True
        mock_create.return_value = mock_conn
        
        pool = ConnectionPool(self.config)
        
        # 获取统计
        stats = pool.get_stats()
        
        self.assertEqual(stats["total_connections"], 2)
        self.assertEqual(stats["idle_connections"], 2)
        self.assertEqual(stats["busy_connections"], 0)
        self.assertEqual(stats["pool_state"], "ready")
        
        pool.close()
    
    @patch.object(ConnectionPool, '_create_mysql_connection')
    def test_pool_close(self, mock_create):
        """测试关闭连接池"""
        mock_conn = Mock()
        mock_conn.ping.return_value = True
        mock_create.return_value = mock_conn
        
        pool = ConnectionPool(self.config)
        pool.close()
        
        self.assertEqual(pool.state, PoolState.CLOSED)
        # 验证所有连接已关闭
        self.assertEqual(len(pool._connections), 0)


class TestConnectionPoolManager(unittest.TestCase):
    """测试连接池管理器"""
    
    def setUp(self):
        """设置测试环境"""
        self.manager = get_pool_manager()
        # 清理之前的连接池
        self.manager.close_all()
    
    def tearDown(self):
        """清理测试环境"""
        self.manager.close_all()
    
    @patch.object(ConnectionPool, '_create_mysql_connection')
    def test_create_pool(self, mock_create):
        """测试创建连接池"""
        mock_conn = Mock()
        mock_conn.ping.return_value = True
        mock_create.return_value = mock_conn
        
        config = PoolConfig(min_connections=1, max_connections=2)
        pool = self.manager.create_pool("test_pool", config)
        
        self.assertIsNotNone(pool)
        self.assertIs(self.manager.get_pool("test_pool"), pool)
        
        pool.close()
    
    @patch.object(ConnectionPool, '_create_mysql_connection')
    def test_get_nonexistent_pool(self, mock_create):
        """测试获取不存在的连接池"""
        pool = self.manager.get_pool("nonexistent")
        self.assertIsNone(pool)
    
    @patch.object(ConnectionPool, '_create_mysql_connection')
    def test_remove_pool(self, mock_create):
        """测试移除连接池"""
        mock_conn = Mock()
        mock_conn.ping.return_value = True
        mock_create.return_value = mock_conn
        
        config = PoolConfig(min_connections=1, max_connections=2)
        pool = self.manager.create_pool("remove_test", config)
        
        self.manager.remove_pool("remove_test")
        
        self.assertIsNone(self.manager.get_pool("remove_test"))
    
    @patch.object(ConnectionPool, '_create_mysql_connection')
    def test_get_all_stats(self, mock_create):
        """测试获取所有统计"""
        mock_conn = Mock()
        mock_conn.ping.return_value = True
        mock_create.return_value = mock_conn
        
        config = PoolConfig(min_connections=1, max_connections=2)
        pool1 = self.manager.create_pool("pool1", config)
        pool2 = self.manager.create_pool("pool2", config)
        
        stats = self.manager.get_all_stats()
        
        self.assertIn("pool1", stats)
        self.assertIn("pool2", stats)
        
        pool1.close()
        pool2.close()


class TestHelperFunctions(unittest.TestCase):
    """测试辅助函数"""
    
    @patch.object(ConnectionPool, '_create_mysql_connection')
    def test_create_pool(self, mock_create):
        """测试create_pool函数"""
        mock_conn = Mock()
        mock_conn.ping.return_value = True
        mock_create.return_value = mock_conn
        
        pool = create_pool(
            db_type="mysql",
            host="localhost",
            min_connections=1,
            max_connections=2
        )
        
        self.assertIsInstance(pool, ConnectionPool)
        pool.close()
    
    def test_get_pool_manager_singleton(self):
        """测试连接池管理器单例"""
        manager1 = get_pool_manager()
        manager2 = get_pool_manager()
        
        self.assertIs(manager1, manager2)


if __name__ == "__main__":
    unittest.main()
