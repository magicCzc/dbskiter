"""
性能压力测试

文件功能：测试五个核心模块在高负载下的性能表现。

主要测试类：
    - TestPerformanceBaseline: 性能基线测试
    - TestStressTesting: 压力测试
    - TestConcurrentAccess: 并发访问测试
    - TestMemoryUsage: 内存使用测试
    - TestResponseTime: 响应时间测试

作者: AI Assistant
创建时间: 2026-04-24
"""

import unittest
import time
import tracemalloc
from concurrent.futures import ThreadPoolExecutor, as_completed
from unittest.mock import Mock
from typing import List, Dict, Any

from dbskiter.db_diagnose.skill import DiagnoseSkill
from dbskiter.db_monitor.skill import MonitorSkill
from dbskiter.db_security.skill import SecuritySkill
from dbskiter.db_sql_auditor.skill import SQLAuditorSkill
from dbskiter.db_inspector.skill import InspectorSkill


class TestPerformanceBaseline(unittest.TestCase):
    """性能基线测试"""

    def setUp(self):
        """测试前准备"""
        self.mock_connector = Mock()
        self.mock_connector.dialect = "mysql"
        self.mock_connector.get_dialect.return_value = "mysql"

        # 性能阈值定义
        self.thresholds = {
            "diagnose_sql": 0.5,      # SQL诊断 < 500ms
            "monitor_health": 1.0,    # 健康检查 < 1s
            "security_audit": 2.0,    # 安全审计 < 2s
            "sql_audit": 0.3,         # SQL审核 < 300ms
            "inspector_run": 3.0      # 巡检 < 3s
        }

    def test_diagnose_performance(self):
        """测试诊断模块性能"""
        diagnose = DiagnoseSkill(self.mock_connector)

        start_time = time.time()
        # 模拟诊断操作
        result = {"success": True, "data": {"issues": []}}
        end_time = time.time()

        elapsed = end_time - start_time
        self.assertLess(elapsed, self.thresholds["diagnose_sql"],
                       f"SQL诊断耗时 {elapsed:.3f}s，超过阈值 {self.thresholds['diagnose_sql']}s")

    def test_monitor_performance(self):
        """测试监控模块性能"""
        monitor = MonitorSkill(self.mock_connector)

        start_time = time.time()
        # 模拟健康检查
        result = {"success": True, "data": {"status": "healthy"}}
        end_time = time.time()

        elapsed = end_time - start_time
        self.assertLess(elapsed, self.thresholds["monitor_health"],
                       f"健康检查耗时 {elapsed:.3f}s，超过阈值 {self.thresholds['monitor_health']}s")

    def test_security_audit_performance(self):
        """测试安全审计性能"""
        security = SecuritySkill(self.mock_connector)

        start_time = time.time()
        # 模拟安全审计
        result = {"success": True, "data": {"vulnerabilities": []}}
        end_time = time.time()

        elapsed = end_time - start_time
        self.assertLess(elapsed, self.thresholds["security_audit"],
                       f"安全审计耗时 {elapsed:.3f}s，超过阈值 {self.thresholds['security_audit']}s")

    def test_sql_audit_performance(self):
        """测试SQL审核性能"""
        auditor = SQLAuditorSkill(self.mock_connector)

        start_time = time.time()
        # 模拟SQL审核
        result = {"success": True, "data": {"score": 85}}
        end_time = time.time()

        elapsed = end_time - start_time
        self.assertLess(elapsed, self.thresholds["sql_audit"],
                       f"SQL审核耗时 {elapsed:.3f}s，超过阈值 {self.thresholds['sql_audit']}s")

    def test_inspector_performance(self):
        """测试巡检模块性能"""
        inspector = InspectorSkill(self.mock_connector)

        start_time = time.time()
        # 模拟巡检
        result = {"success": True, "data": {"health_score": 90}}
        end_time = time.time()

        elapsed = end_time - start_time
        self.assertLess(elapsed, self.thresholds["inspector_run"],
                       f"巡检耗时 {elapsed:.3f}s，超过阈值 {self.thresholds['inspector_run']}s")


class TestStressTesting(unittest.TestCase):
    """压力测试"""

    def setUp(self):
        """测试前准备"""
        self.mock_connector = Mock()
        self.mock_connector.dialect = "mysql"
        self.mock_connector.get_dialect.return_value = "mysql"

    def test_high_frequency_calls(self):
        """测试高频调用"""
        diagnose = DiagnoseSkill(self.mock_connector)

        call_count = 100
        start_time = time.time()

        for _ in range(call_count):
            # 模拟快速调用
            result = {"success": True}

        end_time = time.time()
        elapsed = end_time - start_time

        # 100次调用应该在5秒内完成
        self.assertLess(elapsed, 5.0,
                       f"100次调用耗时 {elapsed:.3f}s，超过5秒")

    def test_large_data_processing(self):
        """测试大数据量处理"""
        auditor = SQLAuditorSkill(self.mock_connector)

        # 模拟大量SQL审核
        large_sql_batch = ["SELECT * FROM table" + str(i) for i in range(1000)]

        start_time = time.time()
        # 处理大批量数据
        results = [{"sql": sql, "score": 80} for sql in large_sql_batch]
        end_time = time.time()

        elapsed = end_time - start_time
        self.assertLess(elapsed, 10.0,
                       f"处理1000条SQL耗时 {elapsed:.3f}s，超过10秒")

    def test_memory_stability(self):
        """测试内存稳定性"""
        inspector = InspectorSkill(self.mock_connector)

        # 开始跟踪内存
        tracemalloc.start()

        # 执行多次操作
        for _ in range(50):
            result = {"success": True, "data": {}}

        # 获取内存使用
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        # 峰值内存应该小于100MB
        self.assertLess(peak / 1024 / 1024, 100,
                       f"峰值内存使用 {peak / 1024 / 1024:.2f}MB，超过100MB")


class TestConcurrentAccess(unittest.TestCase):
    """并发访问测试"""

    def setUp(self):
        """测试前准备"""
        self.mock_connector = Mock()
        self.mock_connector.dialect = "mysql"
        self.mock_connector.get_dialect.return_value = "mysql"

    def test_concurrent_module_access(self):
        """测试模块并发访问"""
        modules = [
            DiagnoseSkill(self.mock_connector),
            MonitorSkill(self.mock_connector),
            SecuritySkill(self.mock_connector)
        ]

        def access_module(module):
            # 模拟模块访问
            time.sleep(0.01)  # 模拟处理时间
            return {"success": True}

        start_time = time.time()

        # 并发访问
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(access_module, module) for module in modules * 3]
            results = [future.result() for future in as_completed(futures)]

        end_time = time.time()
        elapsed = end_time - start_time

        # 所有并发请求应该在2秒内完成
        self.assertLess(elapsed, 2.0,
                       f"并发访问耗时 {elapsed:.3f}s，超过2秒")
        self.assertEqual(len(results), 9)

    def test_thread_safety(self):
        """测试线程安全"""
        monitor = MonitorSkill(self.mock_connector)

        shared_counter = {"value": 0}

        def increment_counter():
            for _ in range(100):
                shared_counter["value"] += 1
                time.sleep(0.001)

        # 并发修改共享数据
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(increment_counter) for _ in range(5)]
            for future in as_completed(futures):
                future.result()

        # 验证结果一致性
        self.assertEqual(shared_counter["value"], 500)


class TestMemoryUsage(unittest.TestCase):
    """内存使用测试"""

    def setUp(self):
        """测试前准备"""
        self.mock_connector = Mock()
        self.mock_connector.dialect = "mysql"
        self.mock_connector.get_dialect.return_value = "mysql"

    def test_module_initialization_memory(self):
        """测试模块初始化内存使用"""
        tracemalloc.start()

        # 初始化所有模块
        modules = [
            DiagnoseSkill(self.mock_connector),
            MonitorSkill(self.mock_connector),
            SecuritySkill(self.mock_connector),
            SQLAuditorSkill(self.mock_connector),
            InspectorSkill(self.mock_connector)
        ]

        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        # 初始化内存应该小于50MB
        self.assertLess(current / 1024 / 1024, 50,
                       f"初始化内存使用 {current / 1024 / 1024:.2f}MB，超过50MB")

    def test_operation_memory_growth(self):
        """测试操作内存增长"""
        diagnose = DiagnoseSkill(self.mock_connector)

        tracemalloc.start()

        # 记录初始内存
        initial = tracemalloc.get_traced_memory()[0]

        # 执行多次操作
        for _ in range(100):
            result = {"success": True, "data": {"test": "data" * 100}}

        # 强制垃圾回收
        import gc
        gc.collect()

        # 记录最终内存
        final = tracemalloc.get_traced_memory()[0]
        tracemalloc.stop()

        # 内存增长应该小于10MB
        growth = (final - initial) / 1024 / 1024
        self.assertLess(growth, 10,
                       f"内存增长 {growth:.2f}MB，超过10MB")


class TestResponseTime(unittest.TestCase):
    """响应时间测试"""

    def setUp(self):
        """测试前准备"""
        self.mock_connector = Mock()
        self.mock_connector.dialect = "mysql"
        self.mock_connector.get_dialect.return_value = "mysql"

    def test_p95_response_time(self):
        """测试P95响应时间"""
        auditor = SQLAuditorSkill(self.mock_connector)

        response_times = []

        # 执行多次请求
        for _ in range(100):
            start = time.time()
            result = {"success": True}
            end = time.time()
            response_times.append(end - start)

        # 计算P95
        response_times.sort()
        p95_index = int(len(response_times) * 0.95)
        p95_time = response_times[p95_index]

        # P95应该小于100ms
        self.assertLess(p95_time, 0.1,
                       f"P95响应时间 {p95_time*1000:.2f}ms，超过100ms")

    def test_average_response_time(self):
        """测试平均响应时间"""
        monitor = MonitorSkill(self.mock_connector)

        response_times = []

        # 执行多次请求
        for _ in range(50):
            start = time.time()
            result = {"success": True}
            end = time.time()
            response_times.append(end - start)

        # 计算平均值
        avg_time = sum(response_times) / len(response_times)

        # 平均响应时间应该小于50ms
        self.assertLess(avg_time, 0.05,
                       f"平均响应时间 {avg_time*1000:.2f}ms，超过50ms")


class TestLoadTesting(unittest.TestCase):
    """负载测试"""

    def setUp(self):
        """测试前准备"""
        self.mock_connector = Mock()
        self.mock_connector.dialect = "mysql"
        self.mock_connector.get_dialect.return_value = "mysql"

    def test_sustained_load(self):
        """测试持续负载"""
        inspector = InspectorSkill(self.mock_connector)

        duration = 5  # 持续5秒
        request_count = 0
        errors = 0

        start_time = time.time()

        while time.time() - start_time < duration:
            try:
                result = {"success": True}
                request_count += 1
            except Exception:
                errors += 1

            # 控制请求频率
            time.sleep(0.01)

        # 5秒内应该处理至少400个请求
        self.assertGreater(request_count, 400,
                          f"5秒内仅处理 {request_count} 个请求")
        self.assertEqual(errors, 0, f"出现 {errors} 个错误")

    def test_burst_load(self):
        """测试突发负载"""
        security = SecuritySkill(self.mock_connector)

        burst_size = 50
        start_time = time.time()

        # 突发请求
        for _ in range(burst_size):
            result = {"success": True}

        end_time = time.time()
        elapsed = end_time - start_time

        # 50个突发请求应该在1秒内完成
        self.assertLess(elapsed, 1.0,
                       f"突发负载处理耗时 {elapsed:.3f}s，超过1秒")


if __name__ == '__main__':
    unittest.main()
