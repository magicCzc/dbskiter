"""
高级容量预测器测试

文件功能：测试高级容量预测器的各种算法
主要测试：
    - 线性回归算法
    - 移动平均算法
    - 指数平滑算法
    - 多项式回归算法
    - 自动算法选择
    - 批量预测

作者: AI Assistant
创建时间: 2026-04-24
版本: 1.0.0
"""

import unittest
from datetime import datetime, timedelta
from typing import List, Tuple

import sys
sys.path.insert(0, 'e:\\Chenzc-AIDev\\数据库skill')

import numpy as np

from dbskiter.db_monitor.advanced_predictor import (
    LinearRegressionAlgorithm,
    MovingAverageAlgorithm,
    ExponentialSmoothingAlgorithm,
    PolynomialRegressionAlgorithm,
    AdvancedCapacityPredictor,
    PredictionResult
)


class TestLinearRegressionAlgorithm(unittest.TestCase):
    """测试线性回归算法"""

    def setUp(self):
        self.algorithm = LinearRegressionAlgorithm()

    def test_linear_growth(self):
        """测试线性增长数据"""
        # 创建线性增长数据: y = 10 + 2*x
        base_time = datetime.now()
        timestamps = [base_time + timedelta(days=i) for i in range(10)]
        values = [10 + 2*i for i in range(10)]  # [10, 12, 14, ..., 28]

        predictions, confidence = self.algorithm.predict(timestamps, values, 30)

        self.assertIn("7d", predictions)
        self.assertIn("30d", predictions)
        self.assertIn("90d", predictions)
        self.assertGreater(confidence, 0.9)  # 线性数据应该有高置信度

        # 验证预测值接近真实趋势
        self.assertGreater(predictions["30d"], values[-1])

    def test_linear_decline(self):
        """测试线性下降数据"""
        base_time = datetime.now()
        timestamps = [base_time + timedelta(days=i) for i in range(10)]
        values = [50 - 3*i for i in range(10)]  # 线性下降

        predictions, confidence = self.algorithm.predict(timestamps, values, 30)

        self.assertLess(predictions["30d"], values[-1])  # 预测值应该下降
        self.assertGreater(confidence, 0.9)

    def test_insufficient_data(self):
        """测试数据不足"""
        base_time = datetime.now()
        timestamps = [base_time, base_time + timedelta(days=1)]
        values = [10, 12]

        predictions, confidence = self.algorithm.predict(timestamps, values, 30)

        # 只有2个数据点，线性回归仍然可以进行，但置信度可能较低
        self.assertIn("7d", predictions)
        self.assertIn("30d", predictions)

    def test_constant_data(self):
        """测试恒定数据"""
        base_time = datetime.now()
        timestamps = [base_time + timedelta(days=i) for i in range(10)]
        values = [50] * 10  # 恒定值

        predictions, confidence = self.algorithm.predict(timestamps, values, 30)

        # 恒定数据可以完美预测，预测值应该接近恒定值
        self.assertAlmostEqual(predictions["30d"], 50, delta=1)


class TestMovingAverageAlgorithm(unittest.TestCase):
    """测试移动平均算法"""

    def setUp(self):
        self.algorithm = MovingAverageAlgorithm(window_size=3)

    def test_basic_prediction(self):
        """测试基本预测"""
        base_time = datetime.now()
        timestamps = [base_time + timedelta(days=i) for i in range(10)]
        values = [10, 12, 11, 13, 12, 14, 13, 15, 14, 16]  # 有波动但上升

        predictions, confidence = self.algorithm.predict(timestamps, values, 30)

        self.assertIn("7d", predictions)
        self.assertIn("30d", predictions)
        self.assertGreaterEqual(confidence, 0.0)
        self.assertLessEqual(confidence, 1.0)

    def test_trend_detection(self):
        """测试趋势检测"""
        base_time = datetime.now()
        timestamps = [base_time + timedelta(days=i) for i in range(10)]
        # 明显上升趋势
        values = list(range(10, 20))

        predictions, confidence = self.algorithm.predict(timestamps, values, 30)

        # 预测值应该继续上升
        self.assertGreater(predictions["30d"], values[-1])

    def test_different_window_sizes(self):
        """测试不同窗口大小"""
        base_time = datetime.now()
        timestamps = [base_time + timedelta(days=i) for i in range(20)]
        values = [10 + i + (i % 3) for i in range(20)]  # 带噪声的线性增长

        # 小窗口
        algo_small = MovingAverageAlgorithm(window_size=3)
        pred_small, _ = algo_small.predict(timestamps, values, 30)

        # 大窗口
        algo_large = MovingAverageAlgorithm(window_size=7)
        pred_large, _ = algo_large.predict(timestamps, values, 30)

        # 两种窗口都应该产生预测
        self.assertIn("30d", pred_small)
        self.assertIn("30d", pred_large)


class TestExponentialSmoothingAlgorithm(unittest.TestCase):
    """测试指数平滑算法"""

    def setUp(self):
        self.algorithm = ExponentialSmoothingAlgorithm(alpha=0.3)

    def test_basic_prediction(self):
        """测试基本预测"""
        base_time = datetime.now()
        timestamps = [base_time + timedelta(days=i) for i in range(10)]
        values = [10, 11, 12, 13, 14, 15, 16, 17, 18, 19]

        predictions, confidence = self.algorithm.predict(timestamps, values, 30)

        self.assertIn("7d", predictions)
        self.assertIn("30d", predictions)
        self.assertGreaterEqual(confidence, 0.0)

    def test_alpha_effect(self):
        """测试不同alpha值的影响"""
        base_time = datetime.now()
        timestamps = [base_time + timedelta(days=i) for i in range(10)]
        # 近期有突变的数据
        values = [10, 10, 10, 10, 10, 20, 20, 20, 20, 20]

        # 高alpha（更重视近期）
        algo_high = ExponentialSmoothingAlgorithm(alpha=0.7)
        pred_high, _ = algo_high.predict(timestamps, values, 30)

        # 低alpha（更重视历史）
        algo_low = ExponentialSmoothingAlgorithm(alpha=0.1)
        pred_low, _ = algo_low.predict(timestamps, values, 30)

        # 高alpha应该预测更高值（因为近期值高）
        self.assertGreater(pred_high["30d"], pred_low["30d"])


class TestPolynomialRegressionAlgorithm(unittest.TestCase):
    """测试多项式回归算法"""

    def setUp(self):
        self.algorithm = PolynomialRegressionAlgorithm(degree=2)

    def test_quadratic_trend(self):
        """测试二次趋势数据"""
        base_time = datetime.now()
        timestamps = [base_time + timedelta(days=i) for i in range(10)]
        # 二次增长: y = x^2
        values = [i**2 for i in range(10)]

        predictions, confidence = self.algorithm.predict(timestamps, values, 30)

        self.assertIn("7d", predictions)
        self.assertIn("30d", predictions)
        # 二次数据应该有较高置信度
        self.assertGreater(confidence, 0.8)

    def test_linear_data_with_polynomial(self):
        """测试用多项式拟合线性数据"""
        base_time = datetime.now()
        timestamps = [base_time + timedelta(days=i) for i in range(10)]
        values = [10 + 2*i for i in range(10)]  # 线性

        predictions, confidence = self.algorithm.predict(timestamps, values, 30)

        # 应该仍然能拟合，但可能不如线性回归精确
        self.assertIn("30d", predictions)
        self.assertGreater(confidence, 0.5)

    def test_insufficient_data(self):
        """测试数据不足"""
        base_time = datetime.now()
        timestamps = [base_time + timedelta(days=i) for i in range(2)]
        values = [10, 12]

        predictions, confidence = self.algorithm.predict(timestamps, values, 30)

        # 二次回归需要至少3个数据点
        self.assertEqual(len(predictions), 0)


class TestAdvancedCapacityPredictor(unittest.TestCase):
    """测试高级容量预测器"""

    def setUp(self):
        self.predictor = AdvancedCapacityPredictor()

    def _create_test_data(
        self,
        days: int = 30,
        trend: str = "up"
    ) -> List[Tuple[datetime, float]]:
        """创建测试数据"""
        base_time = datetime.now() - timedelta(days=days)
        data = []

        for i in range(days):
            timestamp = base_time + timedelta(days=i)
            if trend == "up":
                value = 50 + i * 0.5  # 每天增长0.5
            elif trend == "down":
                value = 80 - i * 0.3
            else:  # stable
                value = 60 + (i % 5) * 0.1  # 几乎不变

            data.append((timestamp, value))

        return data

    def test_predict_linear_growth(self):
        """测试线性增长预测"""
        data = self._create_test_data(days=30, trend="up")

        result = self.predictor.predict("cpu_usage", data, days_ahead=30)

        self.assertEqual(result.metric, "cpu_usage")
        self.assertIn(result.algorithm, [
            "linear_regression",
            "moving_average_7",
            "moving_average_14",
            "exponential_smoothing_0.3",
            "exponential_smoothing_0.5",
            "polynomial_2"
        ])
        self.assertIn("7d", result.predictions)
        self.assertIn("30d", result.predictions)
        self.assertIn("90d", result.predictions)
        self.assertGreater(result.growth_rate, 0)  # 增长趋势

    def test_predict_stable(self):
        """测试稳定数据预测"""
        data = self._create_test_data(days=30, trend="stable")

        result = self.predictor.predict("memory_usage", data, days_ahead=30)

        self.assertEqual(result.metric, "memory_usage")
        # 稳定数据应该识别为stable趋势
        self.assertEqual(result.trend_direction, "stable")
        self.assertAlmostEqual(result.growth_rate, 0, delta=0.1)

    def test_days_to_threshold_calculation(self):
        """测试达到阈值天数计算"""
        # 创建快速增长数据，将在30天内达到阈值
        base_time = datetime.now() - timedelta(days=20)
        data = []
        for i in range(20):
            timestamp = base_time + timedelta(days=i)
            value = 70 + i * 1.5  # 从70开始，每天增长1.5
            data.append((timestamp, value))

        result = self.predictor.predict("disk_usage", data, days_ahead=30)

        # 验证预测结果
        self.assertIsNotNone(result.days_to_threshold)
        # 如果当前值已经超过阈值，days_to_threshold应该是0
        # 否则应该大于等于0

    def test_insufficient_data(self):
        """测试数据不足处理"""
        base_time = datetime.now()
        data = [
            (base_time, 50),
            (base_time + timedelta(days=1), 51)
        ]

        result = self.predictor.predict("cpu_usage", data, days_ahead=30)

        self.assertEqual(result.algorithm, "none")
        self.assertEqual(len(result.predictions), 0)
        self.assertIn("数据不足", result.recommendation)

    def test_batch_predict(self):
        """测试批量预测"""
        metrics_data = {
            "cpu_usage": self._create_test_data(days=30, trend="up"),
            "memory_usage": self._create_test_data(days=30, trend="stable"),
            "disk_usage": self._create_test_data(days=30, trend="up")
        }

        results = self.predictor.batch_predict(metrics_data)

        self.assertEqual(len(results), 3)
        self.assertIn("cpu_usage", results)
        self.assertIn("memory_usage", results)
        self.assertIn("disk_usage", results)

        for metric, result in results.items():
            self.assertIsInstance(result, PredictionResult)
            self.assertEqual(result.metric, metric)

    def test_recommendation_generation(self):
        """测试建议生成"""
        # 快速增长数据
        base_time = datetime.now() - timedelta(days=30)
        data = []
        for i in range(30):
            timestamp = base_time + timedelta(days=i)
            value = 50 + i * 2  # 快速增长
            data.append((timestamp, value))

        result = self.predictor.predict("cpu_usage", data, days_ahead=30)

        # 快速增长应该有紧急建议
        self.assertIn(result.urgency, ["high", "critical"])
        self.assertIn("扩容", result.recommendation)


class TestEdgeCases(unittest.TestCase):
    """测试边界情况"""

    def test_empty_data(self):
        """测试空数据"""
        predictor = AdvancedCapacityPredictor()
        result = predictor.predict("cpu_usage", [], days_ahead=30)

        self.assertEqual(result.algorithm, "none")
        self.assertIn("数据不足", result.recommendation)

    def test_single_data_point(self):
        """测试单数据点"""
        predictor = AdvancedCapacityPredictor()
        data = [(datetime.now(), 50)]
        result = predictor.predict("cpu_usage", data, days_ahead=30)

        self.assertEqual(result.algorithm, "none")

    def test_negative_values(self):
        """测试负值处理"""
        predictor = AdvancedCapacityPredictor()
        base_time = datetime.now() - timedelta(days=10)
        data = [(base_time + timedelta(days=i), -10 + i) for i in range(10)]

        result = predictor.predict("test_metric", data, days_ahead=30)

        # 预测值应该被限制在0-100范围内
        if result.predictions:
            for pred_value in result.predictions.values():
                self.assertGreaterEqual(pred_value, 0)
                self.assertLessEqual(pred_value, 100)

    def test_values_over_100(self):
        """测试超过100的值"""
        predictor = AdvancedCapacityPredictor()
        base_time = datetime.now() - timedelta(days=10)
        data = [(base_time + timedelta(days=i), 90 + i*2) for i in range(10)]

        result = predictor.predict("test_metric", data, days_ahead=30)

        # 预测值应该被限制在0-100范围内
        if result.predictions:
            for pred_value in result.predictions.values():
                self.assertGreaterEqual(pred_value, 0)
                self.assertLessEqual(pred_value, 100)


if __name__ == "__main__":
    unittest.main(verbosity=2)
