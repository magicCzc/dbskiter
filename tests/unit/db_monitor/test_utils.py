"""
db_monitor/test_utils.py
工具类单元测试

测试范围:
    - AnomalyDetector异常检测器
    - CapacityPredictor容量预测器
    - AlertManager告警管理器

版本: 1.0.0
作者: AI Assistant
创建时间: 2026-04-23
"""

import unittest
import time
from datetime import datetime, timedelta

from dbskiter.db_monitor.models import (
    MetricPoint, MetricType, AnomalyType, Severity
)
from dbskiter.db_monitor.utils import (
    AnomalyDetector,
    CapacityPredictor,
    AlertManager,
)


class TestAnomalyDetector(unittest.TestCase):
    """测试异常检测器"""

    def setUp(self):
        self.detector = AnomalyDetector(threshold=2.0)

    def test_detect_normal_data(self):
        """测试正常数据不触发异常"""
        # 添加正常历史数据
        for i in range(20):
            point = MetricPoint(
                timestamp=datetime.now(),
                metric_type=MetricType.CPU_USAGE,
                value=50.0 + i * 0.1,  # 平稳增长
                unit="%"
            )
            alert = self.detector.detect(point)

        # 正常值不应触发异常
        normal_point = MetricPoint(
            timestamp=datetime.now(),
            metric_type=MetricType.CPU_USAGE,
            value=52.0,
            unit="%"
        )
        alert = self.detector.detect(normal_point)
        self.assertIsNone(alert)

    def test_detect_anomaly_spike(self):
        """测试检测突增异常"""
        # 添加正常历史数据
        for i in range(20):
            point = MetricPoint(
                timestamp=datetime.now(),
                metric_type=MetricType.QPS,
                value=100.0,
                unit="qps"
            )
            self.detector.detect(point)

        # 突增值应触发异常
        spike_point = MetricPoint(
            timestamp=datetime.now(),
            metric_type=MetricType.QPS,
            value=200.0,  # 显著高于历史均值
            unit="qps"
        )
        alert = self.detector.detect(spike_point)

        self.assertIsNotNone(alert)
        self.assertEqual(alert.anomaly_type, AnomalyType.SPIKE)

    def test_detect_anomaly_drop(self):
        """测试检测突降异常"""
        # 添加正常历史数据
        for i in range(20):
            point = MetricPoint(
                timestamp=datetime.now(),
                metric_type=MetricType.CONNECTIONS_ACTIVE,
                value=50.0,
                unit="count"
            )
            self.detector.detect(point)

        # 突降值应触发异常
        drop_point = MetricPoint(
            timestamp=datetime.now(),
            metric_type=MetricType.CONNECTIONS_ACTIVE,
            value=5.0,  # 显著低于历史均值
            unit="count"
        )
        alert = self.detector.detect(drop_point)

        self.assertIsNotNone(alert)
        self.assertEqual(alert.anomaly_type, AnomalyType.DROP)

    def test_insufficient_data(self):
        """测试数据不足时不检测"""
        # 只添加少量数据
        for i in range(5):
            point = MetricPoint(
                timestamp=datetime.now(),
                metric_type=MetricType.MEMORY_USAGE,
                value=50.0,
                unit="%"
            )
            self.detector.detect(point)

        # 数据不足，不应触发异常
        anomaly_point = MetricPoint(
            timestamp=datetime.now(),
            metric_type=MetricType.MEMORY_USAGE,
            value=200.0,
            unit="%"
        )
        alert = self.detector.detect(anomaly_point)
        self.assertIsNone(alert)

    def test_clear_history(self):
        """测试清除历史数据"""
        # 添加数据
        for i in range(20):
            point = MetricPoint(
                timestamp=datetime.now(),
                metric_type=MetricType.DISK_USAGE,
                value=50.0,
                unit="%"
            )
            self.detector.detect(point)

        # 清除历史
        self.detector.clear_history(MetricType.DISK_USAGE)

        # 再次检测应因数据不足返回None
        point = MetricPoint(
            timestamp=datetime.now(),
            metric_type=MetricType.DISK_USAGE,
            value=200.0,
            unit="%"
        )
        alert = self.detector.detect(point)
        self.assertIsNone(alert)


class TestCapacityPredictor(unittest.TestCase):
    """测试容量预测器"""

    def setUp(self):
        self.predictor = CapacityPredictor()

    def test_predict_insufficient_data(self):
        """测试数据不足时的预测"""
        historical_data = [
            (datetime.now() - timedelta(days=1), 50.0),
        ]

        result = self.predictor.predict("disk_usage", historical_data, days_ahead=30)

        self.assertFalse(result.predictable)
        self.assertEqual(result.recommendation, "数据不足，无法预测")

    def test_predict_upward_trend(self):
        """测试上升趋势预测"""
        # 创建上升趋势数据（从早到晚）
        historical_data = [
            (datetime.now() - timedelta(days=30-i), 50.0 + i * 0.5)
            for i in range(31)
        ]

        result = self.predictor.predict("disk_usage", historical_data, days_ahead=30)

        self.assertTrue(result.predictable)
        self.assertEqual(result.trend_direction, "up")
        self.assertGreater(result.growth_rate_daily, 0)

    def test_predict_downward_trend(self):
        """测试下降趋势预测"""
        # 创建下降趋势数据（从早到晚）
        historical_data = [
            (datetime.now() - timedelta(days=30-i), 80.0 - i * 0.5)
            for i in range(31)
        ]

        result = self.predictor.predict("cpu_usage", historical_data, days_ahead=30)

        self.assertTrue(result.predictable)
        self.assertEqual(result.trend_direction, "down")
        self.assertLess(result.growth_rate_daily, 0)

    def test_predict_stable_trend(self):
        """测试稳定趋势预测"""
        # 创建稳定数据（从早到晚）
        historical_data = [
            (datetime.now() - timedelta(days=30-i), 50.0)
            for i in range(31)
        ]

        result = self.predictor.predict("memory_usage", historical_data, days_ahead=30)

        self.assertTrue(result.predictable)
        self.assertEqual(result.trend_direction, "stable")

    def test_days_to_threshold(self):
        """测试达到阈值天数计算"""
        # 创建快速增长数据（从早到晚）
        historical_data = [
            (datetime.now() - timedelta(days=30-i), 50.0 + i * 1.0)
            for i in range(31)
        ]

        result = self.predictor.predict("disk_usage", historical_data, days_ahead=30)

        self.assertTrue(result.predictable)
        self.assertIsNotNone(result.days_to_threshold)
        self.assertGreater(result.days_to_threshold, 0)

    def test_urgency_levels(self):
        """测试紧急度分级"""
        # 临界情况：即将达到阈值（从早到晚）
        historical_data_critical = [
            (datetime.now() - timedelta(days=10-i), 85.0 + i * 1.0)
            for i in range(11)
        ]
        result_critical = self.predictor.predict("disk_usage", historical_data_critical, days_ahead=30)
        self.assertEqual(result_critical.urgency, "critical")

        # 高优先级：30天内达到阈值（从早到晚）
        historical_data_high = [
            (datetime.now() - timedelta(days=30-i), 50.0 + i * 0.8)
            for i in range(31)
        ]
        result_high = self.predictor.predict("disk_usage", historical_data_high, days_ahead=30)
        self.assertEqual(result_high.urgency, "high")


class TestAlertManager(unittest.TestCase):
    """测试告警管理器"""

    def setUp(self):
        self.manager = AlertManager(cooldown=2)  # 2秒冷却

    def test_should_alert_first_time(self):
        """测试首次告警"""
        result = self.manager.should_alert("alert_001")
        self.assertTrue(result)

    def test_should_alert_cooldown(self):
        """测试告警冷却"""
        # 首次告警
        self.manager.should_alert("alert_002")

        # 冷却期内再次告警应被抑制
        result = self.manager.should_alert("alert_002")
        self.assertFalse(result)

    def test_should_alert_after_cooldown(self):
        """测试冷却结束后可再次告警"""
        # 首次告警
        self.manager.should_alert("alert_003")

        # 等待冷却结束
        time.sleep(2.1)

        # 冷却结束后可再次告警
        result = self.manager.should_alert("alert_003")
        self.assertTrue(result)

    def test_get_alert_count(self):
        """测试获取告警次数"""
        alert_id = "alert_004"

        # 初始次数为0
        self.assertEqual(self.manager.get_alert_count(alert_id), 0)

        # 触发多次告警（等待冷却）
        self.manager.should_alert(alert_id)
        time.sleep(2.1)
        self.manager.should_alert(alert_id)

        self.assertEqual(self.manager.get_alert_count(alert_id), 2)

    def test_reset_single_alert(self):
        """测试重置单个告警"""
        alert_id = "alert_005"
        self.manager.should_alert(alert_id)

        # 重置
        self.manager.reset(alert_id)

        # 重置后可立即告警
        result = self.manager.should_alert(alert_id)
        self.assertTrue(result)

    def test_reset_all_alerts(self):
        """测试重置所有告警"""
        self.manager.should_alert("alert_006")
        self.manager.should_alert("alert_007")

        # 重置所有
        self.manager.reset()

        # 所有告警都可立即触发
        self.assertTrue(self.manager.should_alert("alert_006"))
        self.assertTrue(self.manager.should_alert("alert_007"))

    def test_get_stats(self):
        """测试获取统计信息"""
        self.manager.should_alert("alert_008")
        self.manager.should_alert("alert_009")

        stats = self.manager.get_stats()

        self.assertEqual(stats["total_alerts"], 2)
        self.assertEqual(stats["total_triggers"], 2)
        self.assertEqual(stats["cooldown_seconds"], 2)


if __name__ == "__main__":
    unittest.main()
