"""
SQL缓存失效管理器单元测试

测试内容：
1. 表名提取
2. 写操作判断
3. 缓存失效机制
4. 索引管理
"""
import unittest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from dbskiter.sql_master.cache_invalidator import (
    TableExtractor, CacheInvalidator, SmartCachedExecutor
)
from dbskiter.sql_master.cache_manager import SQLCacheManager


class TestTableExtractor(unittest.TestCase):
    """TableExtractor 测试类"""
    
    def test_extract_from_select(self):
        """测试从SELECT提取表名"""
        tables = TableExtractor.extract_tables("SELECT * FROM users")
        self.assertEqual(tables, {'USERS'})
    
    def test_extract_from_join(self):
        """测试从JOIN提取表名"""
        tables = TableExtractor.extract_tables(
            "SELECT * FROM users JOIN orders ON users.id = orders.user_id"
        )
        self.assertEqual(tables, {'USERS', 'ORDERS'})
    
    def test_extract_from_insert(self):
        """测试从INSERT提取表名"""
        tables = TableExtractor.extract_tables("INSERT INTO users (name) VALUES ('test')")
        self.assertEqual(tables, {'USERS'})
    
    def test_extract_from_update(self):
        """测试从UPDATE提取表名"""
        tables = TableExtractor.extract_tables("UPDATE users SET name = 'new' WHERE id = 1")
        self.assertEqual(tables, {'USERS'})
    
    def test_extract_from_delete(self):
        """测试从DELETE提取表名"""
        tables = TableExtractor.extract_tables("DELETE FROM users WHERE id = 1")
        self.assertEqual(tables, {'USERS'})
    
    def test_extract_empty_sql(self):
        """测试空SQL"""
        tables = TableExtractor.extract_tables("")
        self.assertEqual(tables, set())
    
    def test_is_write_operation_insert(self):
        """测试INSERT是写操作"""
        self.assertTrue(TableExtractor.is_write_operation("INSERT INTO users VALUES (1)"))
    
    def test_is_write_operation_update(self):
        """测试UPDATE是写操作"""
        self.assertTrue(TableExtractor.is_write_operation("UPDATE users SET name = 'test'"))
    
    def test_is_write_operation_delete(self):
        """测试DELETE是写操作"""
        self.assertTrue(TableExtractor.is_write_operation("DELETE FROM users WHERE id = 1"))
    
    def test_is_write_operation_select(self):
        """测试SELECT不是写操作"""
        self.assertFalse(TableExtractor.is_write_operation("SELECT * FROM users"))


class TestCacheInvalidator(unittest.TestCase):
    """CacheInvalidator 测试类"""
    
    def setUp(self):
        """测试准备"""
        self.cache_manager = SQLCacheManager(max_size=100, default_ttl=60)
        self.invalidator = CacheInvalidator(self.cache_manager)
    
    def test_track_query(self):
        """测试跟踪查询"""
        tables = self.invalidator.track_query("SELECT * FROM users", "key1")
        
        self.assertEqual(tables, {'USERS'})
        
        stats = self.invalidator.get_table_stats()
        self.assertEqual(stats['tracked_tables'], 1)
        self.assertEqual(stats['tracked_queries'], 1)
    
    def test_invalidate_table(self):
        """测试失效单个表"""
        # 设置缓存
        self.cache_manager.set("SELECT * FROM users", {"rows": [1]}, ttl=60)
        self.cache_manager.set("SELECT * FROM orders", {"rows": [2]}, ttl=60)
        
        # 获取实际的缓存键（MD5）
        import hashlib
        key1 = hashlib.md5("SELECT * FROM users".encode()).hexdigest()
        key2 = hashlib.md5("SELECT * FROM orders".encode()).hexdigest()
        
        # 跟踪查询
        self.invalidator.track_query("SELECT * FROM users", key1)
        self.invalidator.track_query("SELECT * FROM orders", key2)
        
        # 失效users表
        count = self.invalidator.invalidate_table('USERS')
        
        self.assertEqual(count, 1)
        self.assertIsNone(self.cache_manager.get("SELECT * FROM users"))
        self.assertIsNotNone(self.cache_manager.get("SELECT * FROM orders"))
    
    def test_invalidate_on_write(self):
        """测试写操作时自动失效"""
        # 设置缓存
        self.cache_manager.set("SELECT * FROM users", {"rows": [1]}, ttl=60)
        
        # 获取实际的缓存键（MD5）
        import hashlib
        key1 = hashlib.md5("SELECT * FROM users".encode()).hexdigest()
        self.invalidator.track_query("SELECT * FROM users", key1)
        
        # 执行写操作
        count = self.invalidator.invalidate_on_write("UPDATE users SET name = 'new'")
        
        self.assertEqual(count, 1)
        self.assertIsNone(self.cache_manager.get("SELECT * FROM users"))
    
    def test_invalidate_on_write_select(self):
        """测试SELECT不触发失效"""
        # 设置缓存
        self.cache_manager.set("SELECT * FROM users", {"rows": [1]}, ttl=60)
        
        # SELECT不应该触发失效
        count = self.invalidator.invalidate_on_write("SELECT * FROM orders")
        
        self.assertEqual(count, 0)
        self.assertIsNotNone(self.cache_manager.get("SELECT * FROM users"))
    
    def test_multiple_tables(self):
        """测试多表查询"""
        import hashlib
        
        sql = "SELECT * FROM users JOIN orders ON users.id = orders.user_id"
        cache_key = hashlib.md5(sql.encode()).hexdigest()
        
        # JOIN查询涉及多个表
        tables = self.invalidator.track_query(sql, cache_key)
        
        self.assertEqual(tables, {'USERS', 'ORDERS'})
        
        # 设置缓存
        self.cache_manager.set(sql, {"rows": []}, ttl=60)
        
        # 更新users表应该失效JOIN查询
        count = self.invalidator.invalidate_on_write("UPDATE users SET name = 'new'")
        self.assertEqual(count, 1)


class TestSmartCachedExecutor(unittest.TestCase):
    """SmartCachedExecutor 测试类"""
    
    class MockExecutor:
        """模拟执行器"""
        def __init__(self):
            self.call_count = 0
        
        def execute(self, sql, params=None):
            self.call_count += 1
            return {"rows": [self.call_count], "sql": sql}
    
    def setUp(self):
        """测试准备"""
        self.mock_executor = self.MockExecutor()
        self.cache_manager = SQLCacheManager(max_size=100, default_ttl=60)
        self.smart_executor = SmartCachedExecutor(
            self.mock_executor,
            self.cache_manager,
            enable_cache=True,
            enable_auto_invalidate=True
        )
    
    def test_read_use_cache(self):
        """测试读操作使用缓存"""
        # 第一次执行
        result1 = self.smart_executor.execute("SELECT * FROM users")
        self.assertEqual(self.mock_executor.call_count, 1)
        
        # 第二次执行（应该命中缓存）
        result2 = self.smart_executor.execute("SELECT * FROM users")
        self.assertEqual(self.mock_executor.call_count, 1)  # 没有增加
        
        self.assertEqual(result1, result2)
    
    def test_write_invalidate_cache(self):
        """测试写操作失效缓存"""
        # 先查询（缓存）
        self.smart_executor.execute("SELECT * FROM users")
        self.assertEqual(self.mock_executor.call_count, 1)

        # 再查询（命中缓存）
        self.smart_executor.execute("SELECT * FROM users")
        self.assertEqual(self.mock_executor.call_count, 1)

        # 执行更新（应该失效缓存，写操作本身也会执行）
        self.smart_executor.execute("UPDATE users SET name = 'new'")
        self.assertEqual(self.mock_executor.call_count, 2)  # 写操作执行

        # 再次查询（缓存已失效，需要重新执行）
        self.smart_executor.execute("SELECT * FROM users")
        self.assertEqual(self.mock_executor.call_count, 3)  # 重新查询
    
    def test_write_not_cached(self):
        """测试写操作不被缓存"""
        # 执行INSERT
        self.smart_executor.execute("INSERT INTO users VALUES (1)")
        
        # 再次执行（不应该命中缓存，写操作不缓存）
        self.smart_executor.execute("INSERT INTO users VALUES (1)")
        
        self.assertEqual(self.mock_executor.call_count, 2)


if __name__ == "__main__":
    unittest.main()
