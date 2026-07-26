"""
监控告警模块测试

文件功能：测试监控告警的各种功能
主要测试类：
    - TestCounter: 计数器测试
    - TestGauge: 仪表盘测试
    - TestHistogram: 直方图测试
    - TestMetricsCollector: 指标收集器测试
    - TestAlertManager: 告警管理器测试
    - TestHealthChecker: 健康检查器测试

运行测试:
    python -m pytest tests/test_monitoring.py -v

作者：AI Assistant
创建时间：2026-04-21
"""

import unittest
import threading
import time
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

# 导入被测模块
from dbskiter.db_scheduler.monitoring import (
    MetricType,
    AlertSeverity,
    AlertState,
    HealthStatus,
    MetricValue,
    AlertRule,
    Alert,
    HealthCheck,
    Counter,
    Gauge,
    Histogram,
    MetricsCollector,
    AlertManager,
    LoggingNotifier,
    HealthChecker,
    create_metrics_collector,
    create_alert_manager,
    create_health_checker
)


class TestCounter(unittest.TestCase):
    """测试计数器"""
    
    def test_counter_initialization(self):
        """测试计数器初始化"""
        counter = Counter("test_counter", {"label1": "value1"}, "Test description")
        
        self.assertEqual(counter.name, "test_counter")
        self.assertEqual(counter.labels, {"label1": "value1"})
        self.assertEqual(counter.description, "Test description")
        self.assertEqual(counter.get(), 0.0)
    
    def test_counter_inc(self):
        """测试计数器增加"""
        counter = Counter("test_counter")
        
        counter.inc()
        self.assertEqual(counter.get(), 1.0)
        
        counter.inc(5)
        self.assertEqual(counter.get(), 6.0)
    
    def test_counter_thread_safety(self):
        """测试计数器线程安全"""
        counter = Counter("test_counter")
        
        def increment():
            for _ in range(100):
                counter.inc()
        
        threads = [threading.Thread(target=increment) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        self.assertEqual(counter.get(), 1000.0)
    
    def test_counter_to_prometheus(self):
        """测试导出Prometheus格式"""
        counter = Counter("requests_total", {"method": "GET"}, "Total requests")
        counter.inc(10)
        
        output = counter.to_prometheus()
        
        self.assertIn("# HELP requests_total Total requests", output)
        self.assertIn("# TYPE requests_total counter", output)
        self.assertIn('requests_total{method="GET"} 10.0', output)


class TestGauge(unittest.TestCase):
    """测试仪表盘"""
    
    def test_gauge_initialization(self):
        """测试仪表盘初始化"""
        gauge = Gauge("test_gauge")
        
        self.assertEqual(gauge.get(), 0.0)
    
    def test_gauge_set(self):
        """测试设置值"""
        gauge = Gauge("test_gauge")
        
        gauge.set(100)
        self.assertEqual(gauge.get(), 100.0)
        
        gauge.set(50.5)
        self.assertEqual(gauge.get(), 50.5)
    
    def test_gauge_inc_dec(self):
        """测试增减"""
        gauge = Gauge("test_gauge")
        
        gauge.set(100)
        gauge.inc(10)
        self.assertEqual(gauge.get(), 110.0)
        
        gauge.dec(20)
        self.assertEqual(gauge.get(), 90.0)
    
    def test_gauge_to_prometheus(self):
        """测试导出Prometheus格式"""
        gauge = Gauge("active_connections", {}, "Active connections")
        gauge.set(15)
        
        output = gauge.to_prometheus()
        
        self.assertIn("# HELP active_connections Active connections", output)
        self.assertIn("# TYPE active_connections gauge", output)
        self.assertIn("active_connections 15", output)


class TestHistogram(unittest.TestCase):
    """测试直方图"""
    
    def test_histogram_initialization(self):
        """测试直方图初始化"""
        histogram = Histogram("test_histogram")
        
        self.assertEqual(histogram._count, 0)
        self.assertEqual(histogram._sum, 0.0)
    
    def test_histogram_observe(self):
        """测试观察值"""
        histogram = Histogram("request_duration")
        
        histogram.observe(0.05)
        histogram.observe(0.1)
        histogram.observe(0.5)
        
        self.assertEqual(histogram._count, 3)
        self.assertEqual(histogram._sum, 0.65)
    
    def test_histogram_to_prometheus(self):
        """测试导出Prometheus格式"""
        histogram = Histogram("request_duration", {}, [0.1, 0.5, 1.0], "Request duration")
        histogram.observe(0.05)
        histogram.observe(0.3)
        histogram.observe(0.8)
        
        output = histogram.to_prometheus()
        
        self.assertIn("# HELP request_duration Request duration", output)
        self.assertIn("# TYPE request_duration histogram", output)
        self.assertIn("request_duration_bucket{le=\"0.1\"} 1", output)
        self.assertIn("request_duration_bucket{le=\"0.5\"} 2", output)
        self.assertIn("request_duration_bucket{le=\"1.0\"} 3", output)
        self.assertIn("request_duration_sum 1.15", output)
        self.assertIn("request_duration_count 3", output)


class TestMetricsCollector(unittest.TestCase):
    """测试指标收集器"""
    
    def setUp(self):
        """设置测试环境"""
        self.collector = MetricsCollector()
    
    def test_counter_creation(self):
        """测试创建计数器"""
        counter = self.collector.counter("requests_total", {"method": "GET"})
        
        self.assertIsInstance(counter, Counter)
        self.assertEqual(counter.name, "requests_total")
    
    def test_gauge_creation(self):
        """测试创建仪表盘"""
        gauge = self.collector.gauge("active_tasks")
        
        self.assertIsInstance(gauge, Gauge)
        self.assertEqual(gauge.name, "active_tasks")
    
    def test_histogram_creation(self):
        """测试创建直方图"""
        histogram = self.collector.histogram("task_duration")
        
        self.assertIsInstance(histogram, Histogram)
        self.assertEqual(histogram.name, "task_duration")
    
    def test_metric_reuse(self):
        """测试指标复用"""
        counter1 = self.collector.counter("test_counter", {"label": "value"})
        counter2 = self.collector.counter("test_counter", {"label": "value"})
        
        self.assertIs(counter1, counter2)
    
    def test_record_and_get_history(self):
        """测试记录和获取历史"""
        metric = MetricValue("test_metric", 100.0, {"label": "value"})
        self.collector.record(metric)
        
        history = self.collector.get_history(name="test_metric")
        
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0].name, "test_metric")
        self.assertEqual(history[0].value, 100.0)
    
    def test_to_prometheus(self):
        """测试导出Prometheus格式"""
        self.collector.counter("requests_total").inc(10)
        self.collector.gauge("active_tasks").set(5)
        self.collector.histogram("duration").observe(0.5)
        
        output = self.collector.to_prometheus()
        
        self.assertIn("requests_total", output)
        self.assertIn("active_tasks", output)
        self.assertIn("duration", output)
    
    def test_to_dict(self):
        """测试导出为字典"""
        self.collector.counter("counter1").inc(10)
        self.collector.gauge("gauge1").set(20)
        
        data = self.collector.to_dict()
        
        self.assertIn("counters", data)
        self.assertIn("gauges", data)
        self.assertIn("histograms", data)


class TestAlertManager(unittest.TestCase):
    """测试告警管理器"""
    
    def setUp(self):
        """设置测试环境"""
        self.manager = AlertManager()
    
    def test_add_rule(self):
        """测试添加规则"""
        rule = AlertRule(
            name="high_error_rate",
            description="Error rate is high",
            condition="error_rate > 0.1",
            severity=AlertSeverity.CRITICAL
        )
        
        self.manager.add_rule(rule)
        
        self.assertIn("high_error_rate", self.manager._rules)
    
    def test_remove_rule(self):
        """测试移除规则"""
        rule = AlertRule(name="test_rule", description="Test", condition="true")
        self.manager.add_rule(rule)
        
        self.manager.remove_rule("test_rule")
        
        self.assertNotIn("test_rule", self.manager._rules)
    
    def test_evaluate_trigger_alert(self):
        """测试评估触发告警"""
        rule = AlertRule(
            name="high_cpu",
            description="CPU usage is high",
            condition="cpu > 80",
            severity=AlertSeverity.WARNING
        )
        self.manager.add_rule(rule)
        
        # 触发告警
        self.manager.evaluate({"cpu": 90})
        
        alerts = self.manager.get_active_alerts()
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0].rule_name, "high_cpu")
    
    def test_evaluate_resolve_alert(self):
        """测试评估恢复告警"""
        rule = AlertRule(
            name="high_cpu",
            description="CPU usage is high",
            condition="cpu > 80",
            severity=AlertSeverity.WARNING
        )
        self.manager.add_rule(rule)
        
        # 触发告警
        self.manager.evaluate({"cpu": 90})
        
        # 恢复告警
        self.manager.evaluate({"cpu": 50})
        
        alerts = self.manager.get_active_alerts()
        self.assertEqual(len(alerts), 0)
    
    def test_silence_alert(self):
        """测试静默告警"""
        rule = AlertRule(
            name="test_alert",
            description="Test",
            condition="true"
        )
        self.manager.add_rule(rule)
        
        # 触发告警（条件为"true"会触发）
        self.manager.evaluate({"true": 1})
        
        # 获取所有告警（包括pending状态）
        alerts = list(self.manager._alerts.values())
        self.assertGreater(len(alerts), 0)
        
        alert_id = alerts[0].id
        
        self.manager.silence_alert(alert_id, 3600)
        
        alert = self.manager._alerts[alert_id]
        self.assertEqual(alert.state, AlertState.SILENCED)


class TestHealthChecker(unittest.TestCase):
    """测试健康检查器"""
    
    def setUp(self):
        """设置测试环境"""
        self.checker = HealthChecker()
    
    def test_register_check(self):
        """测试注册检查"""
        def check_func():
            return HealthCheck("test_check", HealthStatus.HEALTHY, "OK")
        
        self.checker.register_check("test_check", check_func)
        
        self.assertIn("test_check", self.checker._checks)
    
    def test_check_all_healthy(self):
        """测试全部健康"""
        self.checker.register_check(
            "check1",
            lambda: HealthCheck("check1", HealthStatus.HEALTHY, "OK")
        )
        self.checker.register_check(
            "check2",
            lambda: HealthCheck("check2", HealthStatus.HEALTHY, "OK")
        )
        
        result = self.checker.check_all()
        
        self.assertEqual(result["status"], "healthy")
        self.assertEqual(len(result["checks"]), 2)
    
    def test_check_all_unhealthy(self):
        """测试存在不健康"""
        self.checker.register_check(
            "check1",
            lambda: HealthCheck("check1", HealthStatus.HEALTHY, "OK")
        )
        self.checker.register_check(
            "check2",
            lambda: HealthCheck("check2", HealthStatus.UNHEALTHY, "Failed")
        )
        
        result = self.checker.check_all()
        
        self.assertEqual(result["status"], "unhealthy")
    
    def test_check_with_exception(self):
        """测试检查异常"""
        def failing_check():
            raise Exception("Check failed")
        
        self.checker.register_check("failing_check", failing_check)
        
        result = self.checker.check_all()
        
        self.assertEqual(result["status"], "unhealthy")
        self.assertIn("failing_check", result["checks"])


class TestHelperFunctions(unittest.TestCase):
    """测试辅助函数"""
    
    def test_create_metrics_collector(self):
        """测试创建指标收集器"""
        collector = create_metrics_collector()
        
        self.assertIsInstance(collector, MetricsCollector)
    
    def test_create_alert_manager(self):
        """测试创建告警管理器"""
        manager = create_alert_manager()
        
        self.assertIsInstance(manager, AlertManager)
    
    def test_create_health_checker(self):
        """测试创建健康检查器"""
        checker = create_health_checker()
        
        self.assertIsInstance(checker, HealthChecker)


if __name__ == "__main__":
    unittest.main()
