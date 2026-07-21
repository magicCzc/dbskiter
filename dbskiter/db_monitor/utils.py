"""
db_monitor/utils.py
工具类模块

文件功能：
    - 提供监控模块的工具类
    - 异常检测算法实现
    - 容量预测算法实现
    - 与db-scheduler保持一致的代码风格

主要类：
    - AnomalyDetector: 异常检测器
    - CapacityPredictor: 容量预测器
    - AlertManager: 告警管理器

版本: 3.0.0
作者: Magiczc
创建时间: 2026-04-23
"""

import statistics
import time
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
from collections import defaultdict, deque

from dbskiter.db_monitor.models import (
    MetricPoint, MetricType, AnomalyAlert, AnomalyType, Severity,
    CapacityPrediction,
)

logger = logging.getLogger(__name__)


# =============================================================================
# 异常检测器
# =============================================================================

class AnomalyDetector:
    """
    异常检测器 - 支持多种检测算法

    支持算法:
        - Z-score: 基于标准差的统计检测
        - IQR: 基于四分位距的检测
        - Threshold: 简单阈值检测

    使用示例:
        >>> detector = AnomalyDetector(threshold=2.0)
        >>> for metric in metrics:
        ...     alert = detector.detect(metric)
        ...     if alert:
        ...         print(f"异常: {alert.message}")
    """

    def __init__(self, threshold: float = 2.0, history_size: int = 1008):
        """
        初始化异常检测器

        参数:
            threshold: Z-score阈值，默认2.0(约95%置信区间)
            history_size: 历史数据保留数量，默认1008(约7天，每小时采集一次)
        """
        self.threshold = threshold
        self.history_size = history_size
        self.history: Dict[MetricType, deque] = defaultdict(
            lambda: deque(maxlen=history_size)
        )

    def detect(self, metric: MetricPoint) -> Optional[AnomalyAlert]:
        """
        检测单个指标是否异常

        参数:
            metric: 指标数据点

        返回:
            AnomalyAlert: 如果检测到异常则返回告警，否则返回None
        """
        history = self.history[metric.metric_type]
        history.append(metric.value)

        # 数据不足时不进行检测
        if len(history) < 10:
            return None

        # 按优先级尝试不同检测算法
        # 1. Z-score检测(最常用)
        alert = self._detect_zscore(metric, list(history))
        if alert:
            return alert

        # 2. IQR检测(对异常值更鲁棒)
        alert = self._detect_iqr(metric, list(history))
        if alert:
            return alert

        return None

    def _detect_zscore(self, metric: MetricPoint, history: List[float]) -> Optional[AnomalyAlert]:
        """
        Z-score异常检测

        算法说明:
            Z = (X - mean) / std
            当 |Z| > threshold 时判定为异常

        参数:
            metric: 当前指标
            history: 历史数据列表

        返回:
            AnomalyAlert: 异常告警或None
        """
        mean = statistics.mean(history)
        std = statistics.stdev(history) if len(history) > 1 else 0

        if std == 0:
            return None

        zscore = (metric.value - mean) / std

        if abs(zscore) > self.threshold:
            deviation = ((metric.value - mean) / mean * 100) if mean != 0 else 0
            severity = self._calculate_severity(abs(zscore))

            return AnomalyAlert(
                alert_id=f"{metric.metric_type.value}_{int(time.time())}",
                anomaly_type=AnomalyType.SPIKE if zscore > 0 else AnomalyType.DROP,
                severity=severity,
                metric_type=metric.metric_type,
                current_value=metric.value,
                expected_value=mean,
                deviation_percent=deviation,
                message=(
                    f"{metric.metric_type.value} 异常: "
                    f"当前 {metric.value:.2f}, 期望 {mean:.2f} (Z-score: {zscore:.2f})"
                ),
                timestamp=metric.timestamp,
                tags={"algorithm": "z_score", "zscore": str(round(zscore, 2))}
            )

        return None

    def _detect_iqr(self, metric: MetricPoint, history: List[float]) -> Optional[AnomalyAlert]:
        """
        IQR(四分位距)异常检测

        算法说明:
            Q1 = 第25百分位数
            Q3 = 第75百分位数
            IQR = Q3 - Q1
            正常范围 = [Q1 - 1.5*IQR, Q3 + 1.5*IQR]

        参数:
            metric: 当前指标
            history: 历史数据列表

        返回:
            AnomalyAlert: 异常告警或None
        """
        sorted_history = sorted(history)
        n = len(sorted_history)

        q1 = sorted_history[n // 4]
        q3 = sorted_history[3 * n // 4]
        iqr = q3 - q1

        lower_bound = q1 - 1.5 * iqr
        upper_bound = q3 + 1.5 * iqr

        if metric.value < lower_bound or metric.value > upper_bound:
            mean = statistics.mean(history)
            deviation = ((metric.value - mean) / mean * 100) if mean != 0 else 0

            return AnomalyAlert(
                alert_id=f"{metric.metric_type.value}_{int(time.time())}",
                anomaly_type=AnomalyType.THRESHOLD,
                severity=Severity.HIGH,
                metric_type=metric.metric_type,
                current_value=metric.value,
                expected_value=mean,
                deviation_percent=deviation,
                message=(
                    f"{metric.metric_type.value} 超出正常范围: "
                    f"[{lower_bound:.2f}, {upper_bound:.2f}]"
                ),
                timestamp=metric.timestamp,
                tags={
                    "algorithm": "iqr",
                    "lower": str(round(lower_bound, 2)),
                    "upper": str(round(upper_bound, 2))
                }
            )

        return None

    def _calculate_severity(self, zscore: float) -> Severity:
        """
        根据Z-score计算严重级别

        参数:
            zscore: Z-score绝对值

        返回:
            Severity: 严重级别
        """
        if zscore > 4:
            return Severity.CRITICAL
        elif zscore > 3:
            return Severity.HIGH
        elif zscore > 2:
            return Severity.MEDIUM
        else:
            return Severity.LOW

    def clear_history(self, metric_type: Optional[MetricType] = None):
        """
        清除历史数据

        参数:
            metric_type: 指定指标类型，None表示清除所有
        """
        if metric_type:
            self.history[metric_type].clear()
        else:
            self.history.clear()


# =============================================================================
# 容量预测器
# =============================================================================

class CapacityPredictor:
    """
    容量预测器 - 基于趋势预测未来容量需求

    支持功能:
        - 线性趋势预测
        - 多场景预测(乐观/中性/悲观)
        - 容量达到阈值时间计算
        - 容量规划建议

    使用示例:
        >>> predictor = CapacityPredictor()
        >>> result = predictor.predict("disk_usage", historical_data, days=30)
        >>> print(f"30天后预测值: {result.predictions['30d']}%")
    """

    # 默认阈值配置
    THRESHOLDS = {
        "cpu_usage": 80.0,
        "memory_usage": 85.0,
        "disk_usage": 90.0,
        "connections_active": 80.0,
        "buffer_pool_usage": 90.0,
    }

    def __init__(self, thresholds: Optional[Dict[str, float]] = None):
        """
        初始化容量预测器

        参数:
            thresholds: 自定义阈值配置
        """
        self.thresholds = thresholds or self.THRESHOLDS

    def predict(
        self,
        metric: str,
        historical_data: List[tuple],
        days_ahead: int = 30
    ) -> CapacityPrediction:
        """
        预测未来容量

        参数:
            metric: 指标名称
            historical_data: [(timestamp, value), ...] 历史数据
            days_ahead: 预测天数

        返回:
            CapacityPrediction: 预测结果
        """
        if len(historical_data) < 3:
            return CapacityPrediction(
                metric=metric,
                current_value=0.0,
                current_time=datetime.now(),
                predictions={},
                days_to_threshold=None,
                threshold=0.0,
                growth_rate_daily=0.0,
                trend_direction="unknown",
                confidence=0.0,
                recommendation="数据不足，无法预测",
                urgency="low",
                predictable=False
            )

        # 提取数值
        values = [v for _, v in historical_data]
        current_value = values[-1]
        current_time = historical_data[-1][0]

        # 计算日增长率(简单线性回归)
        if len(values) >= 2:
            # 计算平均日增长
            total_change = values[-1] - values[0]
            num_days = max(1, len(values) - 1)
            growth_rate = total_change / num_days
        else:
            growth_rate = 0

        # 确定趋势方向
        if growth_rate > 0.01:
            trend_direction = "up"
        elif growth_rate < -0.01:
            trend_direction = "down"
        else:
            trend_direction = "stable"

        # 预测未来值
        predictions = {}
        for days in [7, 30, 90]:
            predicted = current_value + growth_rate * days
            # 限制在合理范围内(0-100%)
            predictions[f"{days}d"] = max(0.0, min(100.0, predicted))

        # 计算达到阈值的时间
        threshold = self.thresholds.get(metric, 90.0)
        days_to_threshold = None

        if growth_rate > 0:
            remaining = threshold - current_value
            if remaining > 0:
                days_to_threshold = int(remaining / growth_rate)
            else:
                days_to_threshold = 0

        # 确定紧急度和建议
        urgency, recommendation = self._generate_recommendation(
            metric, current_value, days_to_threshold, trend_direction
        )

        # 计算置信度(基于数据量)
        confidence = min(1.0, len(values) / 30.0)  # 30天数据为100%置信度

        return CapacityPrediction(
            metric=metric,
            current_value=current_value,
            current_time=current_time,
            predictions=predictions,
            days_to_threshold=days_to_threshold,
            threshold=threshold,
            growth_rate_daily=growth_rate,
            trend_direction=trend_direction,
            confidence=confidence,
            recommendation=recommendation,
            urgency=urgency,
            predictable=True
        )

    def _generate_recommendation(
        self,
        metric: str,
        current_value: float,
        days_to_threshold: Optional[int],
        trend_direction: str
    ) -> tuple:
        """
        生成容量规划建议

        参数:
            metric: 指标名称
            current_value: 当前值
            days_to_threshold: 距离达到阈值的天数
            trend_direction: 趋势方向

        返回:
            tuple: (urgency, recommendation)
        """
        if trend_direction == "stable":
            return "low", "容量使用稳定，无需特别关注"

        if trend_direction == "down":
            return "low", "容量使用呈下降趋势，资源充足"

        # 上升趋势
        if days_to_threshold is None:
            return "low", "容量增长缓慢，暂无需扩容"

        if days_to_threshold < 7:
            return (
                "critical",
                f"{metric} 将在{days_to_threshold}天内达到阈值，建议立即扩容"
            )
        elif days_to_threshold < 30:
            return (
                "high",
                f"{metric} 将在{days_to_threshold}天内达到阈值，建议尽快规划扩容"
            )
        elif days_to_threshold < 90:
            return (
                "medium",
                f"{metric} 将在{days_to_threshold}天内达到阈值，建议关注容量增长"
            )
        else:
            return "low", f"{metric} 容量充足，预计{days_to_threshold}天后达到阈值"


# =============================================================================
# 告警管理器
# =============================================================================

class AlertManager:
    """
    告警管理器 - 告警去重、抑制和聚合

    功能:
        - 告警冷却(避免重复告警)
        - 告警聚合(相同类型告警合并)
        - 告警级别管理

    使用示例:
        >>> manager = AlertManager(cooldown=300)
        >>> if manager.should_alert(alert_id):
        ...     send_alert(alert)
    """

    def __init__(self, cooldown: int = 300):
        """
        初始化告警管理器

        参数:
            cooldown: 告警冷却时间(秒)，默认5分钟
        """
        self.cooldown = cooldown
        self._last_alert_time: Dict[str, datetime] = {}
        self._alert_count: Dict[str, int] = defaultdict(int)

    def should_alert(self, alert_id: str) -> bool:
        """
        检查是否应该发送告警(考虑冷却期)

        参数:
            alert_id: 告警ID

        返回:
            bool: 是否应该发送
        """
        now = datetime.now()
        last_time = self._last_alert_time.get(alert_id)

        if last_time and (now - last_time).total_seconds() < self.cooldown:
            return False

        self._last_alert_time[alert_id] = now
        self._alert_count[alert_id] += 1
        return True

    def get_alert_count(self, alert_id: str) -> int:
        """获取告警触发次数"""
        return self._alert_count.get(alert_id, 0)

    def reset(self, alert_id: Optional[str] = None):
        """
        重置告警状态

        参数:
            alert_id: 指定告警ID，None表示重置所有
        """
        if alert_id:
            self._last_alert_time.pop(alert_id, None)
            self._alert_count.pop(alert_id, None)
        else:
            self._last_alert_time.clear()
            self._alert_count.clear()

    def get_stats(self) -> Dict[str, Any]:
        """获取告警统计信息"""
        return {
            "total_alerts": len(self._alert_count),
            "total_triggers": sum(self._alert_count.values()),
            "cooldown_seconds": self.cooldown
        }
