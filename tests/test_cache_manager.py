"""
SQL缓存管理器单元测试

测试内容：
1. 基本缓存操作（get/set）
2. LRU淘汰策略
3. TTL过期机制
4. 线程安全
5. 统计信息
"""
import unittest
import time
import threading
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from dbskiter.sql_master.cache_manager import SQLCacheManager, CachedExecutor


class TestSQLCacheManager(unittest.TestCase):
    """SQLCacheManager 测试类"""
    
    def setUp(self):
        """测试准备"""
        self.cache = SQLCacheManager(max_size=10, default_ttl=60)
    
    # ==================== 基本操作测试 ====================
    
    def test_set_and_get(self):
        """测试基本的set和get"""
        self.cache.set("SELECT * FROM users", {"rows": [1, 2, 3]})
        result = self.cache.get("SELECT * FROM users")
        
        self.assertIsNotNone(result)
        self.assertEqual(result["rows"], [1, 2, 3])
    
    def test_get_nonexistent(self):
        """测试获取不存在的缓存"""
        result = self.cache.get("SELECT * FROM nonexistent")
        self.assertIsNone(result)
    
    def test_set_with_params(self):
        """测试带参数的set"""
        self.cache.set(
            "SELECT * FROM users WHERE id = %s",
            {"rows": [1]},
            params={"id": 1}
        )
        
        # 相同参数应该命中
        result = self.cache.get(
            "SELECT * FROM users WHERE id = %s",
            params={"id": 1}
        )
        self.assertIsNotNone(result)
        
        # 不同参数应该未命中
        result2 = self.cache.get(
            "SELECT * FROM users WHERE id = %s",
            params={"id": 2}
        )
        self.assertIsNone(result2)
    
    def test_set_only_cache_select(self):
        """测试只缓存SELECT语句"""
        # INSERT不应该被缓存
        result = self.cache.set("INSERT INTO users VALUES (1)", {"affected": 1})
        self.assertFalse(result)
        
        # UPDATE不应该被缓存
        result = self.cache.set("UPDATE users SET name = 'test'", {"affected": 1})
        self.assertFalse(result)
        
        # SELECT应该被缓存
        result = self.cache.set("SELECT * FROM users", {"rows": []})
        self.assertTrue(result)
    
    # ==================== TTL过期测试 ====================
    
    def test_ttl_expiration(self):
        """测试TTL过期"""
        # 设置1秒过期的缓存
        self.cache.set("SELECT * FROM users", {"rows": [1]}, ttl=1)
        
        # 立即获取应该存在
        result = self.cache.get("SELECT * FROM users")
        self.assertIsNotNone(result)
        
        # 等待2秒
        time.sleep(2)
        
        # 过期后应该不存在
        result = self.cache.get("SELECT * FROM users")
        self.assertIsNone(result)
    
    def test_clear_expired(self):
        """测试清除过期缓存"""
        self.cache.set("SELECT 1", {"rows": [1]}, ttl=1)
        self.cache.set("SELECT 2", {"rows": [2]}, ttl=60)
        
        time.sleep(2)
        
        count = self.cache.clear_expired()
        self.assertEqual(count, 1)
        
        # SELECT 1应该被清除
        self.assertIsNone(self.cache.get("SELECT 1"))
        # SELECT 2应该还在
        self.assertIsNotNone(self.cache.get("SELECT 2"))
    
    # ==================== LRU淘汰测试 ====================
    
    def test_lru_eviction(self):
        """测试LRU淘汰"""
        cache = SQLCacheManager(max_size=3, default_ttl=60)
        
        # 添加3个缓存
        cache.set("SELECT 1", {"rows": [1]})
        cache.set("SELECT 2", {"rows": [2]})
        cache.set("SELECT 3", {"rows": [3]})
        
        # 访问SELECT 1（提升优先级）
        cache.get("SELECT 1")
        
        # 添加第4个，应该淘汰SELECT 2（最少使用）
        cache.set("SELECT 4", {"rows": [4]})
        
        # SELECT 1和3应该还在
        self.assertIsNotNone(cache.get("SELECT 1"))
        self.assertIsNotNone(cache.get("SELECT 3"))
        # SELECT 2应该被淘汰
        self.assertIsNone(cache.get("SELECT 2"))
    
    # ==================== 统计信息测试 ====================
    
    def test_stats(self):
        """测试统计信息"""
        # 设置缓存
        self.cache.set("SELECT 1", {"rows": [1]})
        
        # 命中
        self.cache.get("SELECT 1")
        self.cache.get("SELECT 1")
        
        # 未命中
        self.cache.get("SELECT 2")
        
        stats = self.cache.get_stats()
        
        self.assertEqual(stats["size"], 1)
        self.assertEqual(stats["hits"], 2)
        self.assertEqual(stats["misses"], 1)
        self.assertEqual(stats["sets"], 1)
        self.assertAlmostEqual(stats["hit_rate"], 66.67, places=1)
    
    # ==================== 清除测试 ====================
    
    def test_invalidate_all(self):
        """测试清除所有缓存"""
        self.cache.set("SELECT 1", {"rows": [1]})
        self.cache.set("SELECT 2", {"rows": [2]})
        
        count = self.cache.invalidate()
        
        self.assertEqual(count, 2)
        self.assertIsNone(self.cache.get("SELECT 1"))
        self.assertIsNone(self.cache.get("SELECT 2"))
    
    # ==================== 边界情况测试 ====================
    
    def test_empty_sql(self):
        """测试空SQL - 空SQL不被缓存"""
        result = self.cache.set("", {"rows": []})
        # 空SQL不被缓存（不是SELECT）
        self.assertFalse(result)
    
    def test_very_long_sql(self):
        """测试超长SQL"""
        long_sql = "SELECT " + ", ".join([f"col{i}" for i in range(1000)])
        self.cache.set(long_sql, {"rows": []})
        result = self.cache.get(long_sql)
        self.assertIsNotNone(result)
    
    def test_sql_normalization(self):
        """测试SQL标准化（去除多余空格）"""
        self.cache.set("SELECT   *   FROM   users", {"rows": [1]})
        # 不同空格应该命中同一个缓存
        result = self.cache.get("SELECT * FROM users")
        self.assertIsNotNone(result)


class TestThreadSafety(unittest.TestCase):
    """线程安全测试"""
    
    def test_concurrent_set(self):
        """测试并发set"""
        cache = SQLCacheManager(max_size=100, default_ttl=60)
        errors = []
        
        def worker(i):
            try:
                cache.set(f"SELECT {i}", {"rows": [i]})
            except Exception as e:
                errors.append(e)
        
        threads = [threading.Thread(target=worker, args=(i,)) for i in range(50)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        self.assertEqual(len(errors), 0)
        self.assertEqual(cache.get_stats()["size"], 50)
    
    def test_concurrent_get(self):
        """测试并发get"""
        cache = SQLCacheManager(max_size=10, default_ttl=60)
        
        # 先设置缓存
        for i in range(10):
            cache.set(f"SELECT {i}", {"rows": [i]})
        
        results = []
        
        def worker():
            for i in range(10):
                result = cache.get(f"SELECT {i}")
                results.append(result is not None)
        
        threads = [threading.Thread(target=worker) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        # 所有get都应该成功
        self.assertTrue(all(results))


class TestCachedExecutor(unittest.TestCase):
    """CachedExecutor 测试类"""
    
    class MockExecutor:
        """模拟执行器"""
        def __init__(self):
            self.call_count = 0
        
        def execute(self, sql, params=None):
            self.call_count += 1
            return {"rows": [1, 2, 3], "sql": sql}
    
    def setUp(self):
        """测试准备"""
        self.mock_executor = self.MockExecutor()
        self.cached_executor = CachedExecutor(
            self.mock_executor,
            enable_cache=True
        )
    
    def test_execute_with_cache(self):
        """测试带缓存的执行"""
        # 第一次执行
        result1 = self.cached_executor.execute("SELECT * FROM users")
        self.assertEqual(self.mock_executor.call_count, 1)
        
        # 第二次执行（应该命中缓存）
        result2 = self.cached_executor.execute("SELECT * FROM users")
        self.assertEqual(self.mock_executor.call_count, 1)  # 没有增加
        
        self.assertEqual(result1, result2)
    
    def test_execute_without_cache(self):
        """测试不使用缓存"""
        # 第一次执行
        self.cached_executor.execute("SELECT * FROM users", use_cache=False)
        self.assertEqual(self.mock_executor.call_count, 1)
        
        # 第二次执行（不使用缓存）
        self.cached_executor.execute("SELECT * FROM users", use_cache=False)
        self.assertEqual(self.mock_executor.call_count, 2)
    
    def test_execute_different_params(self):
        """测试不同参数"""
        self.cached_executor.execute("SELECT * FROM users WHERE id = %s", {"id": 1})
        self.cached_executor.execute("SELECT * FROM users WHERE id = %s", {"id": 2})
        
        # 不同参数应该执行两次
        self.assertEqual(self.mock_executor.call_count, 2)
    
    def test_get_stats(self):
        """测试获取统计"""
        self.cached_executor.execute("SELECT 1")
        self.cached_executor.execute("SELECT 1")  # 命中缓存
        
        stats = self.cached_executor.get_stats()
        self.assertEqual(stats["hits"], 1)
        self.assertEqual(stats["misses"], 1)


if __name__ == "__main__":
    unittest.main()
