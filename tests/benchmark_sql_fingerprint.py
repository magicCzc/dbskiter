"""
SQL指纹模块性能基准测试

文件功能：测试SQL指纹生成器的性能表现
测试内容：
    1. 基础SQL指纹生成性能
    2. 复杂SQL指纹生成性能
    3. 批量聚合性能
    4. 长SQL处理性能
    5. 内存占用测试

运行方式：
    cd e:\Chenzc-AIDev\数据库skill
    python tests/benchmark_sql_fingerprint.py

性能指标：
    - 简单SQL: < 1ms
    - 复杂SQL: < 5ms
    - 批量1000条: < 1s
    - 内存增长: < 10%
"""

import sys
import time
import tracemalloc
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from dbskiter.shared.sql_fingerprint import SQLFingerprinter


class PerformanceBenchmark:
    """性能基准测试类"""
    
    def __init__(self):
        self.fp = SQLFingerprinter()
        self.results = []
    
    def benchmark_simple_sql(self, iterations: int = 10000):
        """
        测试简单SQL指纹生成性能
        
        参数:
            iterations: 迭代次数
        """
        sql = "SELECT * FROM users WHERE id = 123 AND name = 'John'"
        
        # 预热
        for _ in range(100):
            self.fp.fingerprint(sql)
        
        # 正式测试
        start = time.perf_counter()
        for _ in range(iterations):
            self.fp.fingerprint(sql)
        elapsed = time.perf_counter() - start
        
        avg_time = (elapsed / iterations) * 1000  # 转换为ms
        
        self.results.append({
            'test': '简单SQL指纹生成',
            'iterations': iterations,
            'total_time': elapsed,
            'avg_time_ms': avg_time,
            'status': '通过' if avg_time < 1.0 else '警告'
        })
        
        return avg_time
    
    def benchmark_complex_sql(self, iterations: int = 1000):
        """
        测试复杂SQL指纹生成性能
        
        参数:
            iterations: 迭代次数
        """
        sql = """
            WITH cte AS (
                SELECT 
                    id,
                    name,
                    ROW_NUMBER() OVER (PARTITION BY dept_id ORDER BY salary DESC) as rn
                FROM employees
                WHERE hire_date > '2020-01-01'
            )
            SELECT 
                c.id,
                c.name,
                CASE 
                    WHEN c.rn = 1 THEN 'Top'
                    WHEN c.rn <= 3 THEN 'High'
                    ELSE 'Normal'
                END as level,
                d.department_name
            FROM cte c
            JOIN departments d ON c.id = d.manager_id
            WHERE c.rn <= 5
            UNION ALL
            SELECT 
                0 as id,
                'Total' as name,
                'Summary' as level,
                COUNT(*) as department_name
            FROM cte
            LIMIT 100
        """
        
        # 预热
        for _ in range(10):
            self.fp.fingerprint(sql)
        
        # 正式测试
        start = time.perf_counter()
        for _ in range(iterations):
            self.fp.fingerprint(sql)
        elapsed = time.perf_counter() - start
        
        avg_time = (elapsed / iterations) * 1000
        
        self.results.append({
            'test': '复杂SQL指纹生成',
            'iterations': iterations,
            'total_time': elapsed,
            'avg_time_ms': avg_time,
            'status': '通过' if avg_time < 5.0 else '警告'
        })
        
        return avg_time
    
    def benchmark_batch_aggregation(self, batch_sizes: list = None):
        """
        测试批量聚合性能
        
        参数:
            batch_sizes: 批量大小列表
        """
        if batch_sizes is None:
            batch_sizes = [100, 500, 1000]
        
        # 生成测试数据
        base_queries = [
            "SELECT * FROM users WHERE id = {}",
            "SELECT * FROM orders WHERE status = '{}'",
            "UPDATE products SET price = {} WHERE id = {}",
            "INSERT INTO logs (msg) VALUES ('{}')",
        ]
        
        for batch_size in batch_sizes:
            queries = []
            for i in range(batch_size):
                template = base_queries[i % len(base_queries)]
                # 计算模板需要的参数数量
                param_count = template.count('{}')
                if param_count == 1:
                    sql = template.format(i)
                elif param_count == 2:
                    sql = template.format(i, i + 1)
                else:
                    sql = template
                queries.append({
                    'sql': sql,
                    'time': 0.5 + (i % 10) * 0.1
                })
            
            start = time.perf_counter()
            aggregated = self.fp.aggregate(queries)
            elapsed = time.perf_counter() - start
            
            self.results.append({
                'test': f'批量聚合 ({batch_size}条)',
                'iterations': batch_size,
                'total_time': elapsed,
                'avg_time_ms': (elapsed / batch_size) * 1000,
                'unique_patterns': len(aggregated),
                'status': '通过' if elapsed < 1.0 else '警告'
            })
    
    def benchmark_long_sql(self, lengths: list = None):
        """
        测试长SQL处理性能
        
        参数:
            lengths: SQL长度列表
        """
        if lengths is None:
            lengths = [1000, 5000, 10000]
        
        for length in lengths:
            # 生成指定长度的SQL
            base = "SELECT * FROM users WHERE id IN ("
            values = ", ".join([str(i) for i in range((length - len(base) - 2) // 3)])
            sql = base + values + ")"
            
            # 确保长度正确
            while len(sql) < length:
                sql = sql[:-1] + ", 1)"
            
            start = time.perf_counter()
            result = self.fp.fingerprint(sql)
            elapsed = time.perf_counter() - start
            
            self.results.append({
                'test': f'长SQL处理 ({length}字符)',
                'iterations': 1,
                'total_time': elapsed,
                'avg_time_ms': elapsed * 1000,
                'sql_length': len(sql),
                'status': '通过' if elapsed < 0.1 else '警告'
            })
    
    def benchmark_memory_usage(self, iterations: int = 10000):
        """
        测试内存占用
        
        参数:
            iterations: 迭代次数
        """
        sql = "SELECT * FROM users WHERE id = {}"
        
        # 开始跟踪内存
        tracemalloc.start()
        
        # 记录初始内存
        snapshot1 = tracemalloc.take_snapshot()
        
        # 执行测试
        for i in range(iterations):
            self.fp.fingerprint(sql.format(i))
        
        # 记录最终内存
        snapshot2 = tracemalloc.take_snapshot()
        
        # 计算内存增长
        top_stats = snapshot2.compare_to(snapshot1, 'lineno')
        total_growth = sum(stat.size_diff for stat in top_stats if stat.size_diff > 0)
        
        tracemalloc.stop()
        
        avg_growth = total_growth / iterations
        
        self.results.append({
            'test': '内存占用测试',
            'iterations': iterations,
            'total_growth_bytes': total_growth,
            'avg_growth_bytes': avg_growth,
            'status': '通过' if avg_growth < 1000 else '警告'
        })
    
    def run_all_benchmarks(self):
        """运行所有基准测试"""
        print("=" * 70)
        print("SQL指纹模块性能基准测试")
        print("=" * 70)
        print()
        
        print("1. 测试简单SQL指纹生成性能...")
        self.benchmark_simple_sql()
        print(f"   完成: {self.results[-1]['avg_time_ms']:.3f} ms/次")
        print()
        
        print("2. 测试复杂SQL指纹生成性能...")
        self.benchmark_complex_sql()
        print(f"   完成: {self.results[-1]['avg_time_ms']:.3f} ms/次")
        print()
        
        print("3. 测试批量聚合性能...")
        self.benchmark_batch_aggregation()
        for result in self.results[-3:]:
            print(f"   {result['test']}: {result['total_time']:.3f}s, "
                  f"{result['unique_patterns']}种模式")
        print()
        
        print("4. 测试长SQL处理性能...")
        self.benchmark_long_sql()
        for result in self.results[-3:]:
            print(f"   {result['test']}: {result['avg_time_ms']:.3f} ms")
        print()
        
        print("5. 测试内存占用...")
        self.benchmark_memory_usage()
        print(f"   平均每次内存增长: {self.results[-1]['avg_growth_bytes']:.0f} bytes")
        print()
    
    def print_report(self):
        """打印测试报告"""
        print("=" * 70)
        print("性能测试报告")
        print("=" * 70)
        print()
        
        for result in self.results:
            print(f"测试项目: {result['test']}")
            print(f"  迭代次数: {result.get('iterations', 'N/A')}")
            
            if 'avg_time_ms' in result:
                print(f"  平均耗时: {result['avg_time_ms']:.3f} ms")
            if 'total_time' in result:
                print(f"  总耗时: {result['total_time']:.3f} s")
            if 'unique_patterns' in result:
                print(f"  唯一模式: {result['unique_patterns']}")
            if 'avg_growth_bytes' in result:
                print(f"  平均内存增长: {result['avg_growth_bytes']:.0f} bytes")
            
            status = result.get('status', '未知')
            status_symbol = '[OK]' if status == '通过' else '[WARN]'
            print(f"  状态: {status_symbol} {status}")
            print()
        
        # 统计
        passed = sum(1 for r in self.results if r.get('status') == '通过')
        warning = sum(1 for r in self.results if r.get('status') == '警告')
        
        print("=" * 70)
        print(f"总计: {passed}项通过, {warning}项警告")
        print("=" * 70)


def main():
    """主函数"""
    benchmark = PerformanceBenchmark()
    benchmark.run_all_benchmarks()
    benchmark.print_report()


if __name__ == '__main__':
    main()
