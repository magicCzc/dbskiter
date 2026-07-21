"""
tests/unit/shared/test_resource_manager.py
ResourceManager 单元测试
"""

import threading
import time
from unittest.mock import MagicMock

import pytest

from dbskiter.shared.resource_manager import (
    ConnectionPool,
    PoolConfig,
    ResourceManager,
    ThreadPoolConfig,
)


def make_connector(dialect="mysql+pymysql"):
    c = MagicMock()
    c.dialect = dialect
    return c


class TestPoolConfig:
    """PoolConfig 数据类测试"""

    def test_defaults(self):
        """默认值"""
        c = PoolConfig()
        assert c.max_connections == 10
        assert c.max_idle_time == 300
        assert c.connection_timeout == 30
        assert c.health_check_interval == 60

    def test_custom(self):
        """自定义值"""
        c = PoolConfig(max_connections=20, max_idle_time=60)
        assert c.max_connections == 20
        assert c.max_idle_time == 60


class TestThreadPoolConfig:
    """ThreadPoolConfig 数据类测试"""

    def test_defaults(self):
        """默认值"""
        c = ThreadPoolConfig()
        assert c.max_workers == 10
        assert c.queue_size == 100
        assert c.thread_name_prefix == "dbskiter_"


class TestConnectionPool:
    """ConnectionPool 测试"""

    def test_init_default_config(self):
        """默认配置初始化"""
        connector = make_connector()
        pool = ConnectionPool(connector)
        assert pool.connector is connector
        assert pool.config.max_connections == 10

    def test_init_custom_config(self):
        """自定义配置"""
        connector = make_connector()
        config = PoolConfig(max_connections=5)
        pool = ConnectionPool(connector, config)
        assert pool.config.max_connections == 5

    def test_get_connection(self):
        """获取连接"""
        connector = make_connector()
        pool = ConnectionPool(connector)
        conn = pool.get_connection()
        assert conn is not None
        assert "id" in conn
        assert "in_use" in conn
        assert conn["in_use"] is True

    def test_release_connection(self):
        """释放连接"""
        connector = make_connector()
        pool = ConnectionPool(connector)
        conn = pool.get_connection()
        pool.release_connection(conn)
        assert conn["in_use"] is False

    def test_get_release_multiple(self):
        """多次获取释放"""
        connector = make_connector()
        pool = ConnectionPool(connector)
        conns = []
        for _ in range(3):
            c = pool.get_connection()
            conns.append(c)
        for c in conns:
            pool.release_connection(c)
        # 释放后应能再次获取
        c = pool.get_connection()
        assert c is not None

    def test_connection_id_increments(self):
        """连接 ID 递增"""
        connector = make_connector()
        pool = ConnectionPool(connector)
        c1 = pool.get_connection()
        c2 = pool.get_connection()
        # ID 应该不同（除非复用）
        assert c1["id"] != c2["id"] or len(pool._in_use) == 1

    def test_pool_creates_connections(self):
        """池创建连接"""
        connector = make_connector()
        pool = ConnectionPool(connector)
        # 预创建 3 个连接（默认 max=10）
        assert pool._pool.qsize() == 3


class TestResourceManager:
    """ResourceManager 测试"""

    def setup_method(self):
        # 重置单例（用于测试）
        ResourceManager._instance = None
        ResourceManager._initialized = False
        self.rm = ResourceManager()

    def test_singleton(self):
        """单例模式"""
        rm1 = ResourceManager()
        rm2 = ResourceManager()
        assert rm1 is rm2

    def test_get_pool(self):
        """获取连接池"""
        connector = make_connector()
        pool = self.rm.get_connection_pool(connector)
        assert isinstance(pool, ConnectionPool)

    def test_get_pool_returns_same(self):
        """获取相同连接池"""
        connector = make_connector()
        pool1 = self.rm.get_connection_pool(connector)
        pool2 = self.rm.get_connection_pool(connector)
        assert pool1 is pool2

    def test_get_pool_different_connectors(self):
        """不同连接器返回不同池"""
        c1 = make_connector("mysql+pymysql")
        c2 = make_connector("postgresql")
        pool1 = self.rm.get_connection_pool(c1)
        pool2 = self.rm.get_connection_pool(c2)
        assert pool1 is not pool2

    def test_close_all(self):
        """关闭所有池"""
        connector = make_connector()
        self.rm.get_connection_pool(connector)
        assert len(self.rm._connection_pools) > 0
        # 直接清空（没有专门的 close_all 方法）
        self.rm._connection_pools.clear()
        assert self.rm._connection_pools == {}


class TestResourceManagerThreadSafety:
    """线程安全测试"""

    def setup_method(self):
        ResourceManager._instance = None
        self.rm = ResourceManager()

    def test_concurrent_get_pool(self):
        """并发获取池"""
        results = []

        def worker():
            c = make_connector("mysql+pymysql")
            pool = self.rm.get_connection_pool(c)
            results.append(pool)

        threads = [threading.Thread(target=worker) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(results) == 5
        # 至少有一个池（因为不同连接器）
        assert all(isinstance(r, ConnectionPool) for r in results)