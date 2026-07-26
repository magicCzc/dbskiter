"""
SQL Master 性能基准测试

测试内容：
1. 缓存命中率测试
2. 执行时间对比（有缓存 vs 无缓存）
3. 并发性能测试
"""
import time
import unittest
import threading
import statistics
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from dbskiter.sql_master.cache_manager import SQLCacheManager, CachedExecutor


class MockExecutor:
    """模拟数据库执行器"""
    def __init__(self, delay=0.01):
        self.delay = delay
        self.call_count = 0
    
    def execute(self, sql, params=None):
        """模拟执行，带延迟"""
        self.call_count += 1
        time.sleep(self.delay)  # 模拟数据库延迟
        return {
            "rows": [{"id": i, "name": f"user_{i}"} for i in range(100)],
            "columns": ["id", "name"],
            "execution_time": self.delay
        }


class TestCachePerformance(unittest.TestCase):
    """缓存性能测试"""
    
    def test_cache_hit_performance(self):
        """测试缓存命中性能提升"""
        print("\n" + "="*60)
        print("缓存性能基准测试")
        print("="*60)
        
        # 创建执行器（模拟10ms延迟）
        mock_executor = MockExecutor(delay=0.01)
        cache_manager = SQLCacheManager(max_size=1000, default_ttl=60)
        cached_executor = CachedExecutor(mock_executor, cache_manager)
        
        # 测试SQL
        sql = "SELECT * FROM users WHERE status = 'active'"
        
        # 第一次执行（无缓存）
        start = time.time()
        result1 = cached_executor.execute(sql)
        time_no_cache = time.time() - start
        
        # 第二次执行（有缓存）
        start = time.time()
        result2 = cached_executor.execute(sql)
        time_with_cache = time.time() - start
        
        # 计算性能提升
        speedup = time_no_cache / time_with_cache if time_with_cache > 0 else float('inf')
        
        print(f"\n1. 单次查询性能对比:")
        print(f"   无缓存执行时间: {time_no_cache*1000:.2f} ms")
        print(f"   有缓存执行时间: {time_with_cache*1000:.2f} ms")
        print(f"   性能提升: {speedup:.1f}x")
        
        # 验证结果一致
        self.assertEqual(result1, result2)
        self.assertGreater(speedup, 5)  # 至少提升5倍
    
    def test_cache_hit_rate(self):
        """测试缓存命中率"""
        print("\n2. 缓存命中率测试:")
        
        mock_executor = MockExecutor(delay=0.001)
        cache_manager = SQLCacheManager(max_size=100, default_ttl=60)
        cached_executor = CachedExecutor(mock_executor, cache_manager)
        
        # 模拟100次查询，其中20个不同SQL，每个执行5次
        sqls = [f"SELECT * FROM users WHERE id = {i}" for i in range(20)]
        
        for _ in range(5):  # 每轮执行所有SQL
            for sql in sqls:
                cached_executor.execute(sql)
        
        # 检查统计
        stats = cache_manager.get_stats()
        total_requests = stats['hits'] + stats['misses']
        hit_rate = stats['hit_rate']
        
        print(f"   总请求数: {total_requests}")
        print(f"   缓存命中: {stats['hits']}")
        print(f"   缓存未命中: {stats['misses']}")
        print(f"   命中率: {hit_rate:.1f}%")
        
        # 期望命中率约80% (100次中20次miss，80次hit)
        self.assertGreater(hit_rate, 70)
    
    def test_lru_eviction_performance(self):
        """测试LRU淘汰性能"""
        print("\n3. LRU淘汰性能测试:")
        
        mock_executor = MockExecutor(delay=0.001)
        cache_manager = SQLCacheManager(max_size=10, default_ttl=60)  # 小缓存
        cached_executor = CachedExecutor(mock_executor, cache_manager)
        
        # 插入20个不同SQL（超过缓存容量）
        start = time.time()
        for i in range(20):
            sql = f"SELECT * FROM users WHERE id = {i}"
            cached_executor.execute(sql)
        insert_time = time.time() - start
        
        stats = cache_manager.get_stats()
        print(f"   插入20条缓存耗时: {insert_time*1000:.2f} ms")
        print(f"   当前缓存大小: {stats['size']}")
        print(f"   淘汰次数: {stats['evictions']}")
        
        # 验证LRU工作正常
        self.assertEqual(stats['size'], 10)  # 不超过最大容量
        self.assertEqual(stats['evictions'], 10)  # 淘汰了10条


class TestConcurrentPerformance(unittest.TestCase):
    """并发性能测试"""
    
    def test_concurrent_read(self):
        """测试并发读性能"""
        print("\n4. 并发读性能测试:")
        
        mock_executor = MockExecutor(delay=0.005)
        cache_manager = SQLCacheManager(max_size=100, default_ttl=60)
        cached_executor = CachedExecutor(mock_executor, cache_manager)
        
        # 先填充缓存
        for i in range(10):
            cached_executor.execute(f"SELECT * FROM users WHERE id = {i}")
        
        # 并发读取
        num_threads = 10
        requests_per_thread = 20
        
        def worker():
            for _ in range(requests_per_thread):
                sql = f"SELECT * FROM users WHERE id = {_ % 10}"
                cached_executor.execute(sql)
        
        start = time.time()
        threads = [threading.Thread(target=worker) for _ in range(num_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        total_time = time.time() - start
        
        total_requests = num_threads * requests_per_thread
        qps = total_requests / total_time
        
        print(f"   并发线程数: {num_threads}")
        print(f"   每线程请求数: {requests_per_thread}")
        print(f"   总请求数: {total_requests}")
        print(f"   总耗时: {total_time:.2f} s")
        print(f"   QPS: {qps:.0f}")
        
        stats = cache_manager.get_stats()
        print(f"   命中率: {stats['hit_rate']:.1f}%")
        
        # QPS应该很高（因为大部分命中缓存）
        self.assertGreater(qps, 500)


class TestCacheInvalidationPerformance(unittest.TestCase):
    """缓存失效性能测试"""
    
    def test_invalidation_performance(self):
        """测试缓存失效性能"""
        print("\n5. 缓存失效性能测试:")
        
        from dbskiter.sql_master.cache_invalidator import CacheInvalidator
        
        mock_executor = MockExecutor(delay=0.001)
        cache_manager = SQLCacheManager(max_size=1000, default_ttl=60)
        invalidator = CacheInvalidator(cache_manager)
        cached_executor = CachedExecutor(mock_executor, cache_manager)
        
        # 填充缓存（100条不同SQL）
        import hashlib
        for i in range(100):
            sql = f"SELECT * FROM users WHERE id = {i}"
            cached_executor.execute(sql)
            cache_key = hashlib.md5(sql.encode()).hexdigest()
            invalidator.track_query(sql, cache_key)
        
        print(f"   缓存条目数: 100")
        
        # 测试失效性能
        start = time.time()
        count = invalidator.invalidate_table('USERS')
        invalidation_time = time.time() - start
        
        print(f"   失效耗时: {invalidation_time*1000:.2f} ms")
        print(f"   失效条目数: {count}")
        
        # 失效应该很快（<10ms）
        self.assertLess(invalidation_time, 0.01)


def run_benchmark():
    """运行所有基准测试"""
    print("\n" + "="*60)
    print("SQL Master 性能基准测试")
    print("="*60)
    
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # 添加所有测试
    suite.addTests(loader.loadTestsFromTestCase(TestCachePerformance))
    suite.addTests(loader.loadTestsFromTestCase(TestConcurrentPerformance))
    suite.addTests(loader.loadTestsFromTestCase(TestCacheInvalidationPerformance))
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    print("\n" + "="*60)
    print("测试完成!")
    print("="*60)
    
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_benchmark()
    sys.exit(0 if success else 1)
