"""
高级容量预测器 - 基于时间序列分析

文件功能：提供多种预测算法，支持复杂场景的容量预测
主要类：
    - AdvancedCapacityPredictor: 高级容量预测器
    - TrendAnalyzer: 趋势分析器
    - SeasonalityDetector: 季节性检测器

算法支持：
    1. 线性回归 - 简单趋势预测
    2. 移动平均 - 平滑短期波动
    3. 指数平滑 - 加权近期数据
    4. 多项式拟合 - 非线性趋势

作者: AI Assistant
创建时间: 2026-04-24
版本: 1.0.0
"""

import logging
import statistics
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import numpy as np


logger = logging.getLogger(__name__)


@dataclass
class PredictionResult:
    """预测结果数据类"""
    metric: str
    algorithm: str
    current_value: float
    predictions: Dict[str, float]
    confidence: float
    growth_rate: float
    trend_direction: str
    days_to_threshold: Optional[int]
    threshold: float
    recommendation: str
    urgency: str


class PredictionAlgorithm(ABC):
    """预测算法抽象基类"""

    @abstractmethod
    def predict(
        self,
        timestamps: List[datetime],
        values: List[float],
        days_ahead: int
    ) -> Tuple[Dict[str, float], float]:
        """
        执行预测

        参数:
            timestamps: 时间戳列表
            values: 数值列表
            days_ahead: 预测天数

        返回:
            Tuple[Dict[str, float], float]: (预测结果, 置信度)
        """
        pass

    @abstractmethod
    def get_name(self) -> str:
        """获取算法名称"""
        pass


class LinearRegressionAlgorithm(PredictionAlgorithm):
    """线性回归预测算法"""

    def get_name(self) -> str:
        return "linear_regression"

    def predict(
        self,
        timestamps: List[datetime],
        values: List[float],
        days_ahead: int
    ) -> Tuple[Dict[str, float], float]:
        """
        使用线性回归预测

        公式: y = a + b*x
        其中 b = Cov(x,y) / Var(x), a = mean(y) - b*mean(x)
        """
        if len(values) < 2:
            return {}, 0.0

        # 转换为天数（相对于第一个数据点）
        base_time = timestamps[0]
        x = np.array([(t - base_time).days for t in timestamps])
        y = np.array(values)

        # 计算线性回归参数
        n = len(x)
        x_mean = np.mean(x)
        y_mean = np.mean(y)

        # 计算协方差和方差
        cov_xy = np.sum((x - x_mean) * (y - y_mean))
        var_x = np.sum((x - x_mean) ** 2)

        if var_x == 0:
            return {}, 0.0

        slope = cov_xy / var_x
        intercept = y_mean - slope * x_mean

        # 计算R²（决定系数）作为置信度
        y_pred = slope * x + intercept
        ss_res = np.sum((y - y_pred) ** 2)
        ss_tot = np.sum((y - y_mean) ** 2)
        r_squared = 1 - (ss_res / ss_tot) if ss_tot != 0 else 0

        # 预测未来值
        last_day = x[-1]
        predictions = {}
        for days in [7, 30, 90]:
            future_day = last_day + days
            pred_value = slope * future_day + intercept
            predictions[f"{days}d"] = max(0.0, min(100.0, pred_value))

        return predictions, max(0.0, r_squared)


class MovingAverageAlgorithm(PredictionAlgorithm):
    """移动平均预测算法"""

    def __init__(self, window_size: int = 7):
        self.window_size = window_size

    def get_name(self) -> str:
        return f"moving_average_{self.window_size}"

    def predict(
        self,
        timestamps: List[datetime],
        values: List[float],
        days_ahead: int
    ) -> Tuple[Dict[str, float], float]:
        """使用移动平均预测"""
        if len(values) < self.window_size:
            return {}, 0.0

        # 计算移动平均
        recent_values = values[-self.window_size:]
        avg = statistics.mean(recent_values)

        # 计算趋势（最近3个窗口的平均变化）
        if len(values) >= self.window_size * 3:
            window1 = statistics.mean(values[-self.window_size*3:-self.window_size*2])
            window2 = statistics.mean(values[-self.window_size*2:-self.window_size])
            window3 = statistics.mean(values[-self.window_size:])
            trend = (window3 - window1) / 2
        else:
            trend = 0

        # 预测
        predictions = {}
        for days in [7, 30, 90]:
            # 假设趋势继续
            pred_value = avg + trend * (days / self.window_size)
            predictions[f"{days}d"] = max(0.0, min(100.0, pred_value))

        # 置信度基于数据稳定性
        std = statistics.stdev(recent_values) if len(recent_values) > 1 else 0
        confidence = max(0.0, 1.0 - (std / 100.0))  # 标准差越小，置信度越高

        return predictions, confidence


class ExponentialSmoothingAlgorithm(PredictionAlgorithm):
    """指数平滑预测算法"""

    def __init__(self, alpha: float = 0.3):
        """
        初始化

        参数:
            alpha: 平滑系数 (0-1)，越大越重视近期数据
        """
        self.alpha = alpha

    def get_name(self) -> str:
        return f"exponential_smoothing_{self.alpha}"

    def predict(
        self,
        timestamps: List[datetime],
        values: List[float],
        days_ahead: int
    ) -> Tuple[Dict[str, float], float]:
        """使用指数平滑预测"""
        if len(values) < 2:
            return {}, 0.0

        # 计算平滑值
        smoothed = [values[0]]
        for value in values[1:]:
            smoothed.append(self.alpha * value + (1 - self.alpha) * smoothed[-1])

        # 计算趋势
        trend = smoothed[-1] - smoothed[-2] if len(smoothed) >= 2 else 0

        # 预测
        predictions = {}
        current = smoothed[-1]
        for days in [7, 30, 90]:
            # 趋势外推
            pred_value = current + trend * (days / len(timestamps))
            predictions[f"{days}d"] = max(0.0, min(100.0, pred_value))

        # 置信度基于平滑程度
        raw_std = statistics.stdev(values) if len(values) > 1 else 0
        smoothed_std = statistics.stdev(smoothed) if len(smoothed) > 1 else 0
        confidence = 0.7 if smoothed_std < raw_std else 0.5

        return predictions, confidence


class PolynomialRegressionAlgorithm(PredictionAlgorithm):
    """多项式回归预测算法 - 用于非线性趋势"""

    def __init__(self, degree: int = 2):
        """
        初始化

        参数:
            degree: 多项式次数，默认2（二次曲线）
        """
        self.degree = degree

    def get_name(self) -> str:
        return f"polynomial_{self.degree}"

    def predict(
        self,
        timestamps: List[datetime],
        values: List[float],
        days_ahead: int
    ) -> Tuple[Dict[str, float], float]:
        """使用多项式回归预测"""
        if len(values) < self.degree + 1:
            return {}, 0.0

        # 转换为天数
        base_time = timestamps[0]
        x = np.array([(t - base_time).days for t in timestamps])
        y = np.array(values)

        try:
            # 多项式拟合
            coeffs = np.polyfit(x, y, self.degree)
            poly = np.poly1d(coeffs)

            # 计算R²
            y_pred = poly(x)
            y_mean = np.mean(y)
            ss_res = np.sum((y - y_pred) ** 2)
            ss_tot = np.sum((y - y_mean) ** 2)
            r_squared = 1 - (ss_res / ss_tot) if ss_tot != 0 else 0

            # 预测
            last_day = x[-1]
            predictions = {}
            for days in [7, 30, 90]:
                future_day = last_day + days
                pred_value = poly(future_day)
                predictions[f"{days}d"] = max(0.0, min(100.0, pred_value))

            return predictions, max(0.0, r_squared)

        except Exception as e:
            logger.warning(f"多项式拟合失败: {e}")
            return {}, 0.0


class AdvancedCapacityPredictor:
    """
    高级容量预测器

    支持多种预测算法，自动选择最佳算法

    使用示例:
        >>> predictor = AdvancedCapacityPredictor()
        >>> result = predictor.predict("disk_usage", historical_data)
        >>> print(f"预测结果: {result.predictions}")
    """

    # 默认阈值配置
    DEFAULT_THRESHOLDS = {
        "cpu_usage": 80.0,
        "memory_usage": 85.0,
        "disk_usage": 90.0,
        "connections_active": 80.0,
        "buffer_pool_usage": 90.0,
        "qps": 10000.0,
        "tps": 1000.0,
    }

    def __init__(self, thresholds: Optional[Dict[str, float]] = None):
        """
        初始化高级容量预测器

        参数:
            thresholds: 自定义阈值配置
        """
        self.thresholds = thresholds or self.DEFAULT_THRESHOLDS

        # 初始化所有算法
        self.algorithms: List[PredictionAlgorithm] = [
            LinearRegressionAlgorithm(),
            MovingAverageAlgorithm(window_size=7),
            MovingAverageAlgorithm(window_size=14),
            ExponentialSmoothingAlgorithm(alpha=0.3),
            ExponentialSmoothingAlgorithm(alpha=0.5),
            PolynomialRegressionAlgorithm(degree=2),
        ]

    def predict(
        self,
        metric: str,
        historical_data: List[Tuple[datetime, float]],
        days_ahead: int = 30
    ) -> PredictionResult:
        """
        执行容量预测

        参数:
            metric: 指标名称
            historical_data: [(timestamp, value), ...] 历史数据
            days_ahead: 预测天数

        返回:
            PredictionResult: 预测结果
        """
        if len(historical_data) < 3:
            return self._create_insufficient_data_result(metric)

        # 提取数据
        timestamps = [t for t, _ in historical_data]
        values = [v for _, v in historical_data]
        current_value = values[-1]

        # 使用所有算法进行预测，选择最佳结果
        best_result = None
        best_confidence = -1

        for algorithm in self.algorithms:
            try:
                predictions, confidence = algorithm.predict(
                    timestamps, values, days_ahead
                )

                if predictions and confidence > best_confidence:
                    best_confidence = confidence
                    best_result = (algorithm.get_name(), predictions, confidence)

            except Exception as e:
                logger.warning(f"算法 {algorithm.get_name()} 预测失败: {e}")
                continue

        if not best_result:
            return self._create_insufficient_data_result(metric)

        algorithm_name, predictions, confidence = best_result

        # 计算增长率
        growth_rate = self._calculate_growth_rate(values)
        trend_direction = self._determine_trend_direction(growth_rate)

        # 计算达到阈值的时间
        threshold = self.thresholds.get(metric, 90.0)
        days_to_threshold = self._calculate_days_to_threshold(
            current_value, predictions, threshold
        )

        # 生成建议
        urgency, recommendation = self._generate_recommendation(
            metric, current_value, days_to_threshold, trend_direction, confidence
        )

        return PredictionResult(
            metric=metric,
            algorithm=algorithm_name,
            current_value=current_value,
            predictions=predictions,
            confidence=confidence,
            growth_rate=growth_rate,
            trend_direction=trend_direction,
            days_to_threshold=days_to_threshold,
            threshold=threshold,
            recommendation=recommendation,
            urgency=urgency
        )

    def _create_insufficient_data_result(self, metric: str) -> PredictionResult:
        """创建数据不足的结果"""
        return PredictionResult(
            metric=metric,
            algorithm="none",
            current_value=0.0,
            predictions={},
            confidence=0.0,
            growth_rate=0.0,
            trend_direction="unknown",
            days_to_threshold=None,
            threshold=self.thresholds.get(metric, 90.0),
            recommendation="历史数据不足（至少需要3个数据点），无法预测",
            urgency="low"
        )

    def _calculate_growth_rate(self, values: List[float]) -> float:
        """计算日增长率"""
        if len(values) < 2:
            return 0.0

        total_change = values[-1] - values[0]
        num_days = len(values) - 1
        return total_change / num_days if num_days > 0 else 0.0

    def _determine_trend_direction(self, growth_rate: float) -> str:
        """确定趋势方向"""
        if growth_rate > 0.5:
            return "up"
        elif growth_rate < -0.5:
            return "down"
        else:
            return "stable"

    def _calculate_days_to_threshold(
        self,
        current_value: float,
        predictions: Dict[str, float],
        threshold: float
    ) -> Optional[int]:
        """计算达到阈值的天数"""
        if current_value >= threshold:
            return 0

        # 按时间顺序检查预测值
        for days_str, value in predictions.items():
            if value >= threshold:
                days = int(days_str.replace("d", ""))
                # 线性插值估算更精确的天数
                if days > 7:
                    prev_days = 7
                    prev_value = predictions.get("7d", current_value)
                else:
                    prev_days = 0
                    prev_value = current_value

                if value > prev_value:
                    ratio = (threshold - prev_value) / (value - prev_value)
                    return int(prev_days + (days - prev_days) * ratio)

        return None

    def _generate_recommendation(
        self,
        metric: str,
        current_value: float,
        days_to_threshold: Optional[int],
        trend_direction: str,
        confidence: float
    ) -> Tuple[str, str]:
        """生成容量规划建议"""
        if trend_direction == "stable":
            return "low", "容量使用稳定，无需特别关注"

        if trend_direction == "down":
            return "low", "容量使用呈下降趋势，资源充足"

        # 上升趋势
        if days_to_threshold is None:
            if confidence < 0.5:
                return "low", "预测置信度较低，建议继续观察"
            return "low", "容量增长缓慢，暂无需扩容"

        if days_to_threshold < 7:
            return (
                "critical",
                f"{metric} 将在{days_to_threshold}天内达到阈值，建议立即扩容"
            )
        elif days_to_threshold < 30:
            return (
                "high",
                f"{metric} 将在{days_to_threshold}天内达到阈值，建议本周内规划扩容"
            )
        elif days_to_threshold < 90:
            return (
                "medium",
                f"{metric} 将在{days_to_threshold}天内达到阈值，建议本月内规划扩容"
            )
        else:
            return (
                "low",
                f"{metric} 预计{days_to_threshold}天后达到阈值，可纳入长期规划"
            )

    def batch_predict(
        self,
        metrics_data: Dict[str, List[Tuple[datetime, float]]]
    ) -> Dict[str, PredictionResult]:
        """
        批量预测多个指标

        参数:
            metrics_data: {metric_name: [(timestamp, value), ...]}

        返回:
            Dict[str, PredictionResult]: 预测结果字典
        """
        results = {}
        for metric, data in metrics_data.items():
            results[metric] = self.predict(metric, data)
        return results
