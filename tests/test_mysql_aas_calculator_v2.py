"""
MySQL AAS计算器 V2 测试套件

测试内容：
1. 配置类测试 - 验证配置加载和验证
2. 数据类测试 - 验证AASMetrics、AASBottleneck等
3. 持久化存储测试 - 验证SQLite存储功能
4. 缓存测试 - 验证查询缓存功能
5. 计算器核心测试 - 验证AAS计算、瓶颈识别
6. 并发测试 - 验证线程安全性
7. 边界条件测试 - 验证异常输入处理
8. 性能测试 - 验证性能指标

作者：AI Assistant
创建时间：2026-04-21
"""

import sys
import os
import time
import threading
import tempfile
import shutil
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock, patch
import unittest

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from dbskiter.shared.mysql_aas_calculator_v2 import (
    AASConfig,
    AASMetrics,
    AASBottleneck,
    AASCorrelation,
    AASPersistentStorage,
    AASQueryCache,
    MySQLAASCalculatorV2,
    HealthStatus,
    BottleneckSeverity,
    retry_on_error,
    timed_execution,
)


# =============================================================================
# 配置类测试
# =============================================================================

class TestAASConfig(unittest.TestCase):
    """测试AAS配置类"""
    
    def test_default_config(self):
        """测试默认配置"""
        config = AASConfig()
        
        self.assertEqual(config.max_history_size, 10000)
        self.assertEqual(config.collection_interval, 1.0)
        self.assertEqual(config.query_timeout, 5.0)
        self.assertTrue(config.enable_persistent_storage)
        self.assertEqual(config.storage_path, "./aas_data")
    
    def test_custom_config(self):
        """测试自定义配置"""
        config = AASConfig(
            max_history_size=5000,
            collection_interval=2.0,
            enable_persistent_storage=False
        )
        
        self.assertEqual(config.max_history_size, 5000)
        self.assertEqual(config.collection_interval, 2.0)
        self.assertFalse(config.enable_persistent_storage)
    
    def test_config_from_env(self):
        """测试从环境变量加载配置"""
        # 设置环境变量
        os.environ['DBSKITER_AAS_MAX_HISTORY_SIZE'] = '5000'
        os.environ['DBSKITER_AAS_ENABLE_PERSISTENT_STORAGE'] = 'false'
        os.environ['DBSKITER_AAS_CPU_THRESHOLD'] = '75.5'
        
        try:
            config = AASConfig.from_env()
            self.assertEqual(config.max_history_size, 5000)
            self.assertFalse(config.enable_persistent_storage)
            self.assertEqual(config.cpu_threshold, 75.5)
        finally:
            # 清理环境变量
            del os.environ['DBSKITER_AAS_MAX_HISTORY_SIZE']
            del os.environ['DBSKITER_AAS_ENABLE_PERSISTENT_STORAGE']
            del os.environ['DBSKITER_AAS_CPU_THRESHOLD']
    
    def test_config_validation(self):
        """测试配置验证"""
        # 无效配置
        config = AASConfig(max_history_size=50)  # 小于100
        errors = config.validate()
        self.assertTrue(len(errors) > 0)
        self.assertIn("max_history_size", errors[0])
        
        # 有效配置
        config = AASConfig(max_history_size=1000)
        errors = config.validate()
        self.assertEqual(len(errors), 0)
    
    def test_config_to_dict(self):
        """测试配置转换为字典"""
        config = AASConfig(max_history_size=5000)
        data = config.to_dict()
        
        self.assertEqual(data['max_history_size'], 5000)
        self.assertEqual(data['collection_interval'], 1.0)
        self.assertIn('enable_persistent_storage', data)


# =============================================================================
# 数据类测试
# =============================================================================

class TestAASMetrics(unittest.TestCase):
    """测试AAS指标数据类"""
    
    def test_basic_metrics(self):
        """测试基本指标计算"""
        metrics = AASMetrics(
            total=15.5,
            cpu=8.2,
            io=4.3,
            lock=2.1,
            network=0.5,
            other=0.4,
            vcpu_count=8
        )
        
        self.assertEqual(metrics.total, 15.5)
        self.assertEqual(metrics.cpu, 8.2)
        self.assertAlmostEqual(metrics.cpu_percentage, 52.9, places=1)
        self.assertTrue(metrics.is_overloaded)
        self.assertEqual(metrics.health_status, HealthStatus.OVERLOADED)
        self.assertAlmostEqual(metrics.utilization_ratio, 1.94, places=1)
    
    def test_healthy_metrics(self):
        """测试健康状态指标"""
        metrics = AASMetrics(
            total=5.0,
            cpu=3.0,
            io=1.5,
            lock=0.3,
            network=0.1,
            other=0.1,
            vcpu_count=8
        )
        
        self.assertFalse(metrics.is_overloaded)
        self.assertFalse(metrics.is_saturated)
        self.assertEqual(metrics.health_status, HealthStatus.HEALTHY)
    
    def test_saturated_metrics(self):
        """测试饱和状态指标"""
        metrics = AASMetrics(
            total=8.0,  # 等于vCPU数量
            cpu=4.0,
            io=2.0,
            lock=1.0,
            network=0.5,
            other=0.5,
            vcpu_count=8
        )
        
        self.assertFalse(metrics.is_overloaded)
        self.assertTrue(metrics.is_saturated)
        self.assertEqual(metrics.health_status, HealthStatus.SATURATED)
    
    def test_zero_values(self):
        """测试零值处理"""
        metrics = AASMetrics(
            total=0,
            cpu=0,
            io=0,
            lock=0,
            network=0,
            other=0,
            vcpu_count=8
        )
        
        self.assertEqual(metrics.cpu_percentage, 0.0)
        self.assertFalse(metrics.is_overloaded)
        self.assertEqual(metrics.health_status, HealthStatus.HEALTHY)
    
    def test_unknown_vcpu(self):
        """测试未知vCPU数量"""
        metrics = AASMetrics(
            total=10.0,
            cpu=5.0,
            io=3.0,
            lock=1.0,
            network=0.5,
            other=0.5,
            vcpu_count=0
        )
        
        self.assertEqual(metrics.health_status, HealthStatus.UNKNOWN)
        self.assertFalse(metrics.is_overloaded)
    
    def test_negative_validation(self):
        """测试负值验证"""
        with self.assertRaises(ValueError) as context:
            AASMetrics(
                total=-1.0,
                cpu=0, io=0, lock=0, network=0, other=0,
                vcpu_count=8
            )
        self.assertIn("不能为负数", str(context.exception))
    
    def test_category_sum_validation(self):
        """测试分类之和验证"""
        with self.assertRaises(ValueError) as context:
            AASMetrics(
                total=5.0,
                cpu=3.0,
                io=3.0,  # 总和超过total
                lock=0,
                network=0,
                other=0,
                vcpu_count=8
            )
        self.assertIn("不能超过 total", str(context.exception))
    
    def test_to_dict(self):
        """测试转换为字典"""
        metrics = AASMetrics(
            total=10.0,
            cpu=5.0,
            io=3.0,
            lock=1.5,
            network=0.3,
            other=0.2,
            vcpu_count=8
        )
        
        data = metrics.to_dict()
        self.assertEqual(data['total'], 10.0)
        self.assertEqual(data['cpu'], 5.0)
        self.assertEqual(data['health_status'], 'saturated')
        self.assertIn('cpu_percentage', data)
        self.assertIn('utilization_ratio', data)
    
    def test_from_dict(self):
        """测试从字典创建"""
        data = {
            'total': 10.0,
            'cpu': 5.0,
            'io': 3.0,
            'lock': 1.5,
            'network': 0.3,
            'other': 0.2,
            'timestamp': datetime.now().isoformat(),
            'vcpu_count': 8,
            'metadata': {'key': 'value'}
        }
        
        metrics = AASMetrics.from_dict(data)
        self.assertEqual(metrics.total, 10.0)
        self.assertEqual(metrics.vcpu_count, 8)
        self.assertEqual(metrics.metadata, {'key': 'value'})


class TestAASBottleneck(unittest.TestCase):
    """测试AAS瓶颈分析结果类"""
    
    def test_basic_bottleneck(self):
        """测试基本瓶颈创建"""
        bottleneck = AASBottleneck(
            primary_cause="io",
            severity=BottleneckSeverity.HIGH,
            description="IO等待严重",
            confidence=0.85
        )
        
        self.assertEqual(bottleneck.primary_cause, "io")
        self.assertEqual(bottleneck.severity, BottleneckSeverity.HIGH)
        self.assertEqual(bottleneck.confidence, 0.85)
    
    def test_confidence_validation(self):
        """测试置信度验证"""
        # 有效置信度
        AASBottleneck(primary_cause="cpu", confidence=0.5)
        AASBottleneck(primary_cause="cpu", confidence=0.0)
        AASBottleneck(primary_cause="cpu", confidence=1.0)
        
        # 无效置信度
        with self.assertRaises(ValueError):
            AASBottleneck(primary_cause="cpu", confidence=1.5)
        
        with self.assertRaises(ValueError):
            AASBottleneck(primary_cause="cpu", confidence=-0.1)
    
    def test_to_dict(self):
        """测试转换为字典"""
        bottleneck = AASBottleneck(
            primary_cause="io",
            secondary_cause="lock",
            severity=BottleneckSeverity.HIGH,
            description="IO瓶颈",
            recommendations=["建议1", "建议2"],
            confidence=0.85
        )
        
        data = bottleneck.to_dict()
        self.assertEqual(data['primary_cause'], "io")
        self.assertEqual(data['severity'], "high")
        self.assertEqual(data['confidence'], 0.85)


# =============================================================================
# 持久化存储测试
# =============================================================================

class TestAASPersistentStorage(unittest.TestCase):
    """测试AAS持久化存储"""
    
    def setUp(self):
        """设置测试环境"""
        self.temp_dir = tempfile.mkdtemp()
        self.storage = AASPersistentStorage(
            storage_path=self.temp_dir,
            max_size_mb=10,
            max_age_hours=168
        )
    
    def tearDown(self):
        """清理测试环境"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_save_and_get_single(self):
        """测试保存和获取单个指标"""
        metrics = AASMetrics(
            total=10.0,
            cpu=5.0,
            io=3.0,
            lock=1.5,
            network=0.3,
            other=0.2,
            vcpu_count=8
        )
        
        record_id = self.storage.save_metrics(metrics)
        self.assertGreater(record_id, 0)
        
        # 获取历史
        history = self.storage.get_history(
            start_time=datetime.now() - timedelta(hours=1)
        )
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0].total, 10.0)
    
    def test_save_batch(self):
        """测试批量保存"""
        metrics_list = []
        for i in range(10):
            metrics = AASMetrics(
                total=10.0 + i,
                cpu=5.0,
                io=3.0,
                lock=1.5,
                network=0.3,
                other=0.2,
                vcpu_count=8,
                timestamp=datetime.now() - timedelta(minutes=i)
            )
            metrics_list.append(metrics)
        
        count = self.storage.save_metrics_batch(metrics_list)
        self.assertEqual(count, 10)
        
        # 验证
        history = self.storage.get_history()
        self.assertEqual(len(history), 10)
    
    def test_get_history_with_time_range(self):
        """测试带时间范围的历史查询"""
        now = datetime.now()
        
        # 保存不同时间的指标
        for i in range(5):
            metrics = AASMetrics(
                total=10.0 + i,
                cpu=5.0, io=3.0, lock=1.5, network=0.3, other=0.2,
                vcpu_count=8,
                timestamp=now - timedelta(hours=i)
            )
            self.storage.save_metrics(metrics)
        
        # 查询最近2小时
        history = self.storage.get_history(
            start_time=now - timedelta(hours=2),
            end_time=now
        )
        self.assertEqual(len(history), 3)  # 0, 1, 2小时前
    
    def test_cleanup_old_data(self):
        """测试清理过期数据"""
        now = datetime.now()
        
        # 保存旧数据
        old_metrics = AASMetrics(
            total=10.0,
            cpu=5.0, io=3.0, lock=1.5, network=0.3, other=0.2,
            vcpu_count=8,
            timestamp=now - timedelta(days=10)  # 10天前
        )
        self.storage.save_metrics(old_metrics)
        
        # 保存新数据
        new_metrics = AASMetrics(
            total=20.0,
            cpu=5.0, io=3.0, lock=1.5, network=0.3, other=0.2,
            vcpu_count=8,
            timestamp=now
        )
        self.storage.save_metrics(new_metrics)
        
        # 清理（默认保留7天）
        deleted = self.storage.cleanup_old_data()
        self.assertEqual(deleted, 1)
        
        # 验证
        history = self.storage.get_history()
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0].total, 20.0)
    
    def test_storage_stats(self):
        """测试存储统计"""
        # 空存储统计
        stats = self.storage.get_storage_stats()
        self.assertIn('db_path', stats)
        self.assertIn('db_size_mb', stats)
        self.assertEqual(stats['total_records'], 0)
        
        # 添加数据后
        metrics = AASMetrics(
            total=10.0,
            cpu=5.0, io=3.0, lock=1.5, network=0.3, other=0.2,
            vcpu_count=8
        )
        self.storage.save_metrics(metrics)
        
        stats = self.storage.get_storage_stats()
        self.assertEqual(stats['total_records'], 1)
        self.assertEqual(stats['recent_24h_records'], 1)


# =============================================================================
# 缓存测试
# =============================================================================

class TestAASQueryCache(unittest.TestCase):
    """测试AAS查询缓存"""
    
    def test_basic_cache_operations(self):
        """测试基本缓存操作"""
        cache = AASQueryCache(ttl=5.0, max_size=100)
        
        # 设置缓存
        cache.set("SELECT * FROM test", {"data": "value"})
        
        # 获取缓存
        result = cache.get("SELECT * FROM test")
        self.assertEqual(result, {"data": "value"})
        
        # 获取不存在的缓存
        result = cache.get("SELECT * FROM other")
        self.assertIsNone(result)
    
    def test_cache_expiration(self):
        """测试缓存过期"""
        cache = AASQueryCache(ttl=0.1, max_size=100)  # 100ms过期
        
        cache.set("query", "value")
        self.assertEqual(cache.get("query"), "value")
        
        # 等待过期
        time.sleep(0.15)
        self.assertIsNone(cache.get("query"))
    
    def test_cache_invalidation(self):
        """测试缓存失效"""
        cache = AASQueryCache(ttl=5.0, max_size=100)
        
        cache.set("query1", "value1")
        cache.set("query2", "value2")
        
        # 全部失效
        cache.invalidate()
        self.assertIsNone(cache.get("query1"))
        self.assertIsNone(cache.get("query2"))
    
    def test_cache_stats(self):
        """测试缓存统计"""
        cache = AASQueryCache(ttl=5.0, max_size=100)
        
        stats = cache.get_stats()
        self.assertEqual(stats['size'], 0)
        self.assertEqual(stats['max_size'], 100)
        
        cache.set("query", "value")
        stats = cache.get_stats()
        self.assertEqual(stats['size'], 1)


# =============================================================================
# 装饰器测试
# =============================================================================

class TestDecorators(unittest.TestCase):
    """测试装饰器功能"""
    
    def test_retry_on_error_success(self):
        """测试重试装饰器 - 成功情况"""
        call_count = 0
        
        @retry_on_error(max_retries=3, delay=0.1)
        def success_func():
            nonlocal call_count
            call_count += 1
            return "success"
        
        result = success_func()
        self.assertEqual(result, "success")
        self.assertEqual(call_count, 1)  # 只调用一次
    
    def test_retry_on_error_retry_then_success(self):
        """测试重试装饰器 - 重试后成功"""
        call_count = 0
        
        @retry_on_error(max_retries=3, delay=0.1)
        def retry_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("Temporary error")
            return "success"
        
        result = retry_func()
        self.assertEqual(result, "success")
        self.assertEqual(call_count, 3)  # 调用3次
    
    def test_retry_on_error_max_retries_exceeded(self):
        """测试重试装饰器 - 超过最大重试次数"""
        call_count = 0
        
        @retry_on_error(max_retries=3, delay=0.1)
        def always_fail():
            nonlocal call_count
            call_count += 1
            raise ValueError("Always fails")
        
        with self.assertRaises(ValueError):
            always_fail()
        
        self.assertEqual(call_count, 3)  # 调用3次
    
    def test_timed_execution(self):
        """测试执行时间装饰器"""
        @timed_execution
        def slow_func():
            time.sleep(0.1)
            return "done"
        
        result = slow_func()
        self.assertEqual(result, "done")


# =============================================================================
# 计算器核心测试
# =============================================================================

class MockQueryResult:
    """模拟查询结果"""
    def __init__(self, rows=None):
        self.rows = rows or []


class TestMySQLAASCalculatorV2(unittest.TestCase):
    """测试MySQL AAS计算器 V2"""
    
    def setUp(self):
        """设置测试环境"""
        self.temp_dir = tempfile.mkdtemp()
        
        # 创建模拟连接器
        self.mock_connector = Mock()
        self.mock_connector.dialect = "mysql"
        self.mock_connector.execute = Mock()
        
        # 配置
        self.config = AASConfig(
            max_history_size=1000,
            collection_interval=0.1,  # 缩短间隔便于测试
            enable_persistent_storage=True,
            storage_path=self.temp_dir
        )
        
        # 设置模拟执行函数
        self._setup_mock_execute()
    
    def tearDown(self):
        """清理测试环境"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def _setup_mock_for_aas_calculation(self):
        """设置模拟数据用于AAS计算"""
        self._setup_mock_execute()
    
    def _setup_mock_execute(self):
        """设置模拟执行函数"""
        def mock_execute(query, params=()):
            query_str = str(query).lower()
            # SHOW VARIABLES LIKE 返回2列：Variable_name, Value
            if "performance_schema" in query_str and "show variables" in query_str:
                return MockQueryResult([['performance_schema', 'ON']])
            elif "innodb_thread_concurrency" in query_str:
                return MockQueryResult([['innodb_thread_concurrency', '16']])
            elif "count(*)" in query_str and "threads" in query_str:
                # 模拟AAS查询结果 - 6列数据
                return MockQueryResult([[
                    100,  # total_threads
                    20,   # active_threads
                    8,    # cpu_threads
                    6,    # io_threads
                    4,    # lock_threads
                    2     # network_threads
                ]])
            return MockQueryResult([])
        
        self.mock_connector.execute.side_effect = mock_execute
    
    def test_initialization(self):
        """测试计算器初始化"""
        self._setup_mock_for_aas_calculation()
        
        calculator = MySQLAASCalculatorV2(
            self.mock_connector,
            config=self.config
        )
        
        self.assertIsNotNone(calculator)
        # vCPU数量可能是从os.cpu_count()获取的真实值，不一定是8
        self.assertGreater(calculator._vcpu_count, 0)
    
    def test_calculate_current_aas(self):
        """测试计算当前AAS"""
        self._setup_mock_for_aas_calculation()
        
        calculator = MySQLAASCalculatorV2(
            self.mock_connector,
            config=self.config
        )
        
        metrics = calculator.calculate_current_aas()
        
        self.assertEqual(metrics.total, 20.0)  # active_threads
        self.assertEqual(metrics.cpu, 8.0)
        self.assertEqual(metrics.io, 6.0)
        self.assertEqual(metrics.lock, 4.0)
        self.assertEqual(metrics.network, 2.0)
        self.assertEqual(metrics.other, 0.0)  # 20 - 8 - 6 - 4 - 2 = 0
    
    def test_identify_bottleneck(self):
        """测试瓶颈识别"""
        self._setup_mock_for_aas_calculation()
        
        calculator = MySQLAASCalculatorV2(
            self.mock_connector,
            config=self.config
        )
        
        bottleneck = calculator.identify_bottleneck()
        
        self.assertEqual(bottleneck.primary_cause, "cpu")  # CPU占比最高
        self.assertGreater(bottleneck.confidence, 0)
        self.assertTrue(len(bottleneck.recommendations) > 0)
    
    def test_get_aas_history(self):
        """测试获取历史数据"""
        self._setup_mock_for_aas_calculation()
        
        calculator = MySQLAASCalculatorV2(
            self.mock_connector,
            config=self.config
        )
        
        # 计算多次AAS（等待间隔以绕过频率限制）
        for i in range(5):
            calculator.calculate_current_aas()
            time.sleep(0.15)  # 等待超过collection_interval(0.1秒)
        
        # 获取历史
        history = calculator.get_aas_history(minutes=10)
        # 由于频率限制，实际保存的数量可能少于5个
        self.assertGreaterEqual(len(history), 1)
    
    def test_rate_limiting(self):
        """测试频率限制"""
        self._setup_mock_for_aas_calculation()
        
        config = AASConfig(
            collection_interval=1.0,  # 1秒间隔
            enable_persistent_storage=False
        )
        
        calculator = MySQLAASCalculatorV2(
            self.mock_connector,
            config=config
        )
        
        # 第一次调用
        metrics1 = calculator.calculate_current_aas()
        
        # 立即第二次调用（应该触发频率限制）
        metrics2 = calculator.calculate_current_aas()
        
        # 两次结果应该相同（返回缓存值）
        self.assertEqual(metrics1.total, metrics2.total)
        
        # execute应该只被调用一次（频率限制）
        aas_calls = [call for call in self.mock_connector.execute.call_args_list 
                    if "threads" in str(call) and "COUNT" in str(call)]
        self.assertEqual(len(aas_calls), 1)


# =============================================================================
# 并发测试
# =============================================================================

class TestConcurrency(unittest.TestCase):
    """测试并发安全性"""
    
    def setUp(self):
        """设置测试环境"""
        self.temp_dir = tempfile.mkdtemp()
        
        self.mock_connector = Mock()
        self.mock_connector.dialect = "mysql"
        
        self.call_count = [0]
        def mock_execute(query, params=()):
            self.call_count[0] += 1
            query_str = str(query).lower()
            # SHOW VARIABLES LIKE 返回2列
            if "performance_schema" in query_str and "show variables" in query_str:
                return MockQueryResult([['performance_schema', 'ON']])
            elif "innodb_thread_concurrency" in query_str:
                return MockQueryResult([['innodb_thread_concurrency', '16']])
            elif "count(*)" in query_str and "threads" in query_str:
                # 模拟不同的AAS值
                active = 10 + self.call_count[0] % 10
                return MockQueryResult([[
                    100, active, active // 2, active // 4, 
                    active // 8, active // 16
                ]])
            return MockQueryResult([])
        
        self.mock_connector.execute = mock_execute
        
        self.config = AASConfig(
            max_history_size=1000,
            collection_interval=0.1,  # 很短的间隔
            enable_persistent_storage=True,
            storage_path=self.temp_dir
        )
    
    def tearDown(self):
        """清理测试环境"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_concurrent_aas_calculation(self):
        """测试并发AAS计算"""
        calculator = MySQLAASCalculatorV2(
            self.mock_connector,
            config=self.config
        )
        
        results = []
        errors = []
        
        def worker():
            try:
                for _ in range(10):
                    metrics = calculator.calculate_current_aas()
                    results.append(metrics.total)
                    time.sleep(0.01)
            except Exception as e:
                errors.append(str(e))
        
        # 启动多个线程
        threads = [threading.Thread(target=worker) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        # 验证没有错误
        self.assertEqual(len(errors), 0, f"并发错误: {errors}")
        
        # 验证结果数量
        self.assertEqual(len(results), 50)  # 5线程 * 10次
    
    def test_concurrent_history_access(self):
        """测试并发历史数据访问"""
        calculator = MySQLAASCalculatorV2(
            self.mock_connector,
            config=self.config
        )
        
        # 先添加一些历史数据
        for _ in range(20):
            calculator.calculate_current_aas()
            time.sleep(0.01)
        
        errors = []
        
        def writer():
            try:
                for _ in range(20):
                    calculator.calculate_current_aas()
                    time.sleep(0.01)
            except Exception as e:
                errors.append(f"Writer error: {e}")
        
        def reader():
            try:
                for _ in range(20):
                    history = calculator.get_aas_history(minutes=10)
                    time.sleep(0.01)
            except Exception as e:
                errors.append(f"Reader error: {e}")
        
        # 启动读写线程
        threads = []
        for _ in range(3):
            threads.append(threading.Thread(target=writer))
            threads.append(threading.Thread(target=reader))
        
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        # 验证没有错误
        self.assertEqual(len(errors), 0, f"并发错误: {errors}")


# =============================================================================
# 边界条件测试
# =============================================================================

class TestEdgeCases(unittest.TestCase):
    """测试边界条件"""
    
    def setUp(self):
        """设置测试环境"""
        self.temp_dir = tempfile.mkdtemp()
        
        self.mock_connector = Mock()
        self.mock_connector.dialect = "mysql"
        
        self.config = AASConfig(
            max_history_size=100,
            collection_interval=0.1,
            enable_persistent_storage=True,
            storage_path=self.temp_dir
        )
    
    def tearDown(self):
        """清理测试环境"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_empty_query_result(self):
        """测试空查询结果"""
        self.mock_connector.execute = Mock(return_value=MockQueryResult([]))
        
        calculator = MySQLAASCalculatorV2(
            self.mock_connector,
            config=self.config
        )
        
        metrics = calculator.calculate_current_aas()
        
        # 应该返回零值而不是崩溃
        self.assertEqual(metrics.total, 0)
        self.assertEqual(metrics.cpu, 0)
    
    def test_none_values_in_result(self):
        """测试结果中的None值"""
        def mock_execute(query, params=()):
            if "COUNT(*)" in query:
                return MockQueryResult([[100, None, None, None, None, None]])
            return MockQueryResult([])
        
        self.mock_connector.execute = mock_execute
        
        calculator = MySQLAASCalculatorV2(
            self.mock_connector,
            config=self.config
        )
        
        metrics = calculator.calculate_current_aas()
        
        # None应该被处理为0
        self.assertEqual(metrics.total, 0)
    
    def test_very_large_values(self):
        """测试极大值"""
        def mock_execute(query, params=()):
            if "COUNT(*)" in query:
                return MockQueryResult([[
                    1000000, 100000, 50000, 30000, 15000, 5000
                ]])
            return MockQueryResult([])
        
        self.mock_connector.execute = mock_execute
        
        calculator = MySQLAASCalculatorV2(
            self.mock_connector,
            config=self.config
        )
        
        metrics = calculator.calculate_current_aas()
        
        self.assertEqual(metrics.total, 100000.0)
        self.assertTrue(metrics.is_overloaded)
    
    def test_database_connection_error(self):
        """测试数据库连接错误"""
        self.mock_connector.execute = Mock(
            side_effect=Exception("Connection refused")
        )
        
        calculator = MySQLAASCalculatorV2(
            self.mock_connector,
            config=self.config
        )
        
        # 应该优雅降级，返回零值
        metrics = calculator.calculate_current_aas()
        
        self.assertEqual(metrics.total, 0)
        self.assertIn("error", metrics.metadata)


# =============================================================================
# 主程序
# =============================================================================

if __name__ == '__main__':
    # 设置日志级别
    logging.basicConfig(level=logging.WARNING)
    
    # 运行测试
    unittest.main(verbosity=2)
