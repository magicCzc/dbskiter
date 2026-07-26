"""
LRU缓存测试
"""
import sys
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dbskiter.shared.sql_fingerprint import SQLFingerprinter

def test_lru_cache():
    # 测试1: 基本缓存功能
    print("Test 1: Basic cache functionality")
    fp = SQLFingerprinter(cache_capacity=100)
    
    sql = "SELECT * FROM users WHERE id = 123"
    
    # 第一次生成（未缓存）
    result1 = fp.fingerprint(sql)
    stats1 = fp.get_cache_stats()
    print(f"  First call - Cache stats: {stats1}")
    
    # 第二次生成（已缓存）
    result2 = fp.fingerprint(sql)
    stats2 = fp.get_cache_stats()
    print(f"  Second call - Cache stats: {stats2}")
    
    assert result1.fingerprint == result2.fingerprint
    assert stats2['hits'] == 1, f"Expected 1 hit, got {stats2['hits']}"
    print("  [OK] Cache hit works")
    
    # 测试2: 缓存命中率
    print("\nTest 2: Cache hit rate")
    fp2 = SQLFingerprinter(cache_capacity=1000)
    
    # 生成100个不同SQL
    for i in range(100):
        fp2.fingerprint(f"SELECT * FROM users WHERE id = {i}")
    
    # 重复生成相同的SQL
    for i in range(100):
        fp2.fingerprint(f"SELECT * FROM users WHERE id = {i % 50}")  # 只有50个不同
    
    stats = fp2.get_cache_stats()
    print(f"  Cache stats: {stats}")
    assert stats['hit_rate'] == '50.00%', f"Expected 50% hit rate, got {stats['hit_rate']}"
    print("  [OK] Cache hit rate correct")
    
    # 测试3: 缓存淘汰
    print("\nTest 3: Cache eviction")
    fp3 = SQLFingerprinter(cache_capacity=10)
    
    # 生成20个SQL（超过容量）
    for i in range(20):
        fp3.fingerprint(f"SELECT * FROM table_{i}")
    
    stats = fp3.get_cache_stats()
    print(f"  Cache stats after 20 inserts: {stats}")
    assert stats['size'] == 10, f"Expected size 10, got {stats['size']}"
    print("  [OK] Cache eviction works")
    
    # 测试4: 禁用缓存
    print("\nTest 4: Disable cache")
    fp4 = SQLFingerprinter(enable_cache=False)
    fp4.fingerprint("SELECT * FROM users")
    stats = fp4.get_cache_stats()
    assert stats['enabled'] == False
    print("  [OK] Cache disabled")
    
    # 测试5: 缓存清空
    print("\nTest 5: Clear cache")
    fp5 = SQLFingerprinter(cache_capacity=100)
    for i in range(10):
        fp5.fingerprint(f"SELECT * FROM users WHERE id = {i}")
    
    stats_before = fp5.get_cache_stats()
    print(f"  Before clear: {stats_before}")
    
    fp5.clear_cache()
    stats_after = fp5.get_cache_stats()
    print(f"  After clear: {stats_after}")
    
    assert stats_after['size'] == 0
    assert stats_after['hits'] == 0
    print("  [OK] Cache cleared")
    
    # 测试6: 性能提升
    print("\nTest 6: Performance improvement")
    fp6 = SQLFingerprinter(cache_capacity=1000)
    
    # 预热缓存
    for i in range(100):
        fp6.fingerprint(f"SELECT * FROM users WHERE id = {i}")
    
    # 测试缓存命中性能
    start = time.perf_counter()
    for i in range(1000):
        fp6.fingerprint(f"SELECT * FROM users WHERE id = {i % 100}")
    cached_time = time.perf_counter() - start
    
    # 测试无缓存性能
    fp7 = SQLFingerprinter(enable_cache=False)
    start = time.perf_counter()
    for i in range(1000):
        fp7.fingerprint(f"SELECT * FROM users WHERE id = {i % 100}")
    no_cache_time = time.perf_counter() - start
    
    print(f"  With cache: {cached_time:.3f}s")
    print(f"  Without cache: {no_cache_time:.3f}s")
    print(f"  Speedup: {no_cache_time/cached_time:.1f}x")
    
    stats = fp6.get_cache_stats()
    print(f"  Cache stats: {stats}")
    
    print("\n[OK] All cache tests passed!")

if __name__ == '__main__':
    test_lru_cache()
