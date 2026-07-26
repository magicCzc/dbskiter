"""
db_monitor/test_models.py
数据模型单元测试

测试范围:
    - ErrorCode错误码体系
    - ErrorMessage错误消息
    - 所有枚举类型
    - 数据类转换

版本: 1.0.0
作者: AI Assistant
创建时间: 2026-04-23
"""

import unittest
from datetime import datetime, timedelta

from dbskiter.db_monitor.models import (
    ErrorCode,
    ErrorMessage,
    HealthStatus,
    AnomalyType,
    Severity,
    MetricType,
    MetricPoint,
    AnomalyAlert,
    MonitorConfig,
    HealthAssessment,
    CapacityPrediction,
)
from dbskiter.shared.error_handler import create_success_response, create_error_response


class TestErrorCode(unittest.TestCase):
    """测试错误码体系"""

    def test_error_code_format(self):
        """测试错误码格式正确"""
        error_codes = [
            ErrorCode.SUCCESS,
            ErrorCode.UNKNOWN_ERROR,
            ErrorCode.COLLECTION_FAILED,
            ErrorCode.DETECTION_FAILED,
            ErrorCode.STORAGE_ERROR,
        ]

        for code in error_codes:
            self.assertTrue(code.startswith("MON"))
            self.assertEqual(len(code), 9)  # MON000000格式

    def test_error_code_uniqueness(self):
        """测试错误码唯一性"""
        error_codes = [
            ErrorCode.SUCCESS,
            ErrorCode.UNKNOWN_ERROR,
            ErrorCode.INVALID_PARAM,
            ErrorCode.COLLECTION_FAILED,
            ErrorCode.DETECTION_FAILED,
            ErrorCode.PREDICTION_FAILED,
        ]

        self.assertEqual(len(error_codes), len(set(error_codes)))


class TestErrorMessage(unittest.TestCase):
    """测试错误消息映射"""

    def test_get_message_exists(self):
        """测试获取存在的错误消息"""
        msg = ErrorMessage.get_message(ErrorCode.SUCCESS)
        self.assertEqual(msg, "操作成功")

        msg = ErrorMessage.get_message(ErrorCode.COLLECTION_FAILED)
        self.assertEqual(msg, "指标采集失败")

    def test_get_message_not_exists(self):
        """测试获取不存在的错误消息"""
        msg = ErrorMessage.get_message("MON999999")
        self.assertIn("未知错误码", msg)


class TestHealthStatus(unittest.TestCase):
    """测试健康状态枚举"""

    def test_health_status_values(self):
        """测试健康状态值"""
        self.assertEqual(HealthStatus.HEALTHY.value, "healthy")
        self.assertEqual(HealthStatus.WARNING.value, "warning")
        self.assertEqual(HealthStatus.CRITICAL.value, "critical")
        self.assertEqual(HealthStatus.UNKNOWN.value, "unknown")


class TestAnomalyType(unittest.TestCase):
    """测试异常类型枚举"""

    def test_anomaly_type_values(self):
        """测试异常类型值"""
        self.assertEqual(AnomalyType.SPIKE.value, "spike")
        self.assertEqual(AnomalyType.DROP.value, "drop")
        self.assertEqual(AnomalyType.TREND_UP.value, "trend_up")
        self.assertEqual(AnomalyType.THRESHOLD.value, "threshold")


class TestSeverity(unittest.TestCase):
    """测试严重级别枚举"""

    def test_severity_order(self):
        """测试严重级别顺序"""
        severities = [
            Severity.CRITICAL,
            Severity.HIGH,
            Severity.MEDIUM,
            Severity.LOW,
            Severity.INFO,
        ]

        # 确保所有级别都有值
        for sev in severities:
            self.assertIsNotNone(sev.value)


class TestMetricType(unittest.TestCase):
    """测试指标类型枚举"""

    def test_metric_type_values(self):
        """测试指标类型值"""
        self.assertEqual(MetricType.QPS.value, "qps")
        self.assertEqual(MetricType.CONNECTIONS_ACTIVE.value, "connections_active")
        self.assertEqual(MetricType.CPU_USAGE.value, "cpu_usage")
        self.assertEqual(MetricType.DISK_USAGE.value, "disk_usage")


class TestMetricPoint(unittest.TestCase):
    """测试指标数据点"""

    def test_metric_point_creation(self):
        """测试创建指标数据点"""
        point = MetricPoint(
            timestamp=datetime.now(),
            metric_type=MetricType.CPU_USAGE,
            value=75.5,
            unit="%",
            tags={"host": "localhost"}
        )

        self.assertEqual(point.metric_type, MetricType.CPU_USAGE)
        self.assertEqual(point.value, 75.5)
        self.assertEqual(point.unit, "%")

    def test_metric_point_to_dict(self):
        """测试指标数据点转字典"""
        now = datetime.now()
        point = MetricPoint(
            timestamp=now,
            metric_type=MetricType.MEMORY_USAGE,
            value=80.0,
            unit="%",
            source="test"
        )

        data = point.to_dict()
        self.assertIsInstance(data, dict)
        self.assertEqual(data["metric_type"], "memory_usage")
        self.assertEqual(data["value"], 80.0)
        self.assertEqual(data["unit"], "%")


class TestAnomalyAlert(unittest.TestCase):
    """测试异常告警"""

    def test_anomaly_alert_creation(self):
        """测试创建异常告警"""
        alert = AnomalyAlert(
            alert_id="alert_001",
            anomaly_type=AnomalyType.SPIKE,
            severity=Severity.HIGH,
            metric_type=MetricType.QPS,
            current_value=150.0,
            expected_value=100.0,
            deviation_percent=50.0,
            message="QPS突增",
            timestamp=datetime.now()
        )

        self.assertEqual(alert.alert_id, "alert_001")
        self.assertEqual(alert.severity, Severity.HIGH)

    def test_anomaly_alert_to_dict(self):
        """测试异常告警转字典"""
        alert = AnomalyAlert(
            alert_id="alert_002",
            anomaly_type=AnomalyType.DROP,
            severity=Severity.MEDIUM,
            metric_type=MetricType.CONNECTIONS_ACTIVE,
            current_value=10.0,
            expected_value=50.0,
            deviation_percent=-80.0,
            message="连接数骤降",
            timestamp=datetime.now(),
            tags={"reason": "test"}
        )

        data = alert.to_dict()
        self.assertIsInstance(data, dict)
        self.assertEqual(data["alert_id"], "alert_002")
        self.assertEqual(data["severity"], "medium")
        self.assertIn("tags", data)


class TestMonitorConfig(unittest.TestCase):
    """测试监控配置"""

    def test_default_config(self):
        """测试默认配置"""
        config = MonitorConfig()

        self.assertEqual(config.collection_interval, 60)
        self.assertEqual(config.max_history_size, 10080)
        self.assertTrue(config.enable_prediction)
        self.assertTrue(config.enable_persistent_storage)

    def test_custom_config(self):
        """测试自定义配置"""
        config = MonitorConfig(
            collection_interval=30,
            anomaly_threshold=3.0,
            storage_path="./custom_path"
        )

        self.assertEqual(config.collection_interval, 30)
        self.assertEqual(config.anomaly_threshold, 3.0)
        self.assertEqual(config.storage_path, "./custom_path")

    def test_config_to_dict(self):
        """测试配置转字典"""
        config = MonitorConfig()
        data = config.to_dict()

        self.assertIsInstance(data, dict)
        self.assertIn("collection_interval", data)
        self.assertIn("enable_prediction", data)


class TestHealthAssessment(unittest.TestCase):
    """测试健康评估结果"""

    def test_health_assessment_creation(self):
        """测试创建健康评估"""
        assessment = HealthAssessment(
            status=HealthStatus.HEALTHY,
            score=95,
            issues=[],
            metrics_summary={"cpu": 50.0}
        )

        self.assertEqual(assessment.status, HealthStatus.HEALTHY)
        self.assertEqual(assessment.score, 95)

    def test_health_assessment_to_dict(self):
        """测试健康评估转字典"""
        assessment = HealthAssessment(
            status=HealthStatus.WARNING,
            score=75,
            issues=["连接数较高"],
            metrics_summary={"connections": 80}
        )

        data = assessment.to_dict()
        self.assertIsInstance(data, dict)
        self.assertEqual(data["status"], "warning")
        self.assertEqual(data["score"], 75)
        self.assertEqual(len(data["issues"]), 1)


class TestCapacityPrediction(unittest.TestCase):
    """测试容量预测结果"""

    def test_capacity_prediction_creation(self):
        """测试创建容量预测"""
        prediction = CapacityPrediction(
            metric="disk_usage",
            current_value=70.0,
            current_time=datetime.now(),
            predictions={"7d": 75.0, "30d": 85.0},
            days_to_threshold=60,
            threshold=90.0,
            growth_rate_daily=0.5,
            trend_direction="up",
            confidence=0.85,
            recommendation="建议关注磁盘增长",
            urgency="medium"
        )

        self.assertEqual(prediction.metric, "disk_usage")
        self.assertEqual(prediction.predictable, True)

    def test_capacity_prediction_to_dict(self):
        """测试容量预测转字典"""
        prediction = CapacityPrediction(
            metric="cpu_usage",
            current_value=60.0,
            current_time=datetime.now(),
            predictions={"7d": 65.0},
            days_to_threshold=None,
            threshold=80.0,
            growth_rate_daily=0.1,
            trend_direction="stable",
            confidence=0.9,
            recommendation="容量充足",
            urgency="low"
        )

        data = prediction.to_dict()
        self.assertIsInstance(data, dict)
        self.assertEqual(data["metric"], "cpu_usage")
        self.assertEqual(data["trend_direction"], "stable")


class TestResponseFunctions(unittest.TestCase):
    """测试响应辅助函数"""

    def test_create_success_response(self):
        """测试创建成功响应"""
        response = create_success_response({"id": 1}, "操作成功")

        self.assertTrue(response["success"])
        self.assertEqual(response["message"], "操作成功")
        self.assertEqual(response["data"]["id"], 1)
        self.assertIn("timestamp", response)

    def test_create_error_response(self):
        """测试创建错误响应"""
        response = create_error_response(
            "操作失败",
            error_code=ErrorCode.INVALID_PARAM,
            details={"field": "name"}
        )

        self.assertFalse(response["success"])
        self.assertEqual(response["error"]["code"], ErrorCode.INVALID_PARAM)
        self.assertEqual(response["error"]["message"], "操作失败")
        self.assertEqual(response["error"]["details"]["field"], "name")
        self.assertIn("timestamp", response)


if __name__ == "__main__":
    unittest.main()
