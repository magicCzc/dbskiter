"""
趋势分析器测试

文件功能：测试趋势分析器的核心功能
主要测试：
    - 趋势方向判断
    - 历史数据统计
    - 基线对比
    - 性能退化检测
    - 与db-diagnose集成

作者: AI Assistant
创建时间: 2026-04-24
版本: 1.0.0
"""

import unittest
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock

import sys
sys.path.insert(0, 'e:\\Chenzc-AIDev\\数据库skill')

from dbskiter.db_monitor.trend_analyzer import (
    TrendAnalyzer,
    TrendDirection,
    TrendAnalysis,
    PerformanceComparison,
    StorageBasedDataProvider
)
from dbskiter.db_monitor.collectors.base import MetricType, MetricPoint


class MockDataProvider:
    """模拟数据提供者"""

    def __init__(self, mock_data=None):
        self.mock_data = mock_data or {}
        self.mock_baseline = None

    def get_metric_history(self, metric_type, days=7):
        return self.mock_data.get(metric_type, [])

    def get_baseline(self, metric_type, baseline_date=None):
        return self.mock_baseline


class TestTrendAnalyzer(unittest.TestCase):
    """测试趋势分析器"""

    def setUp(self):
        self.provider = MockDataProvider()
        self.analyzer = TrendAnalyzer(self.provider)

    def _create_metric_points(
        self,
        values,
        start_time=None
    ):
        """创建指标数据点"""
        if start_time is None:
            start_time = datetime.now() - timedelta(days=len(values))

        points = []
        for i, value in enumerate(values):
            timestamp = start_time + timedelta(hours=i)
            points.append(MetricPoint(
                timestamp=timestamp,
                metric_type=MetricType.CPU_USAGE,
                value=value,
                unit="%"
            ))
        return points

    def test_analyze_trend_improving(self):
        """测试改善趋势"""
        # 创建改善数据（值下降）
        values = [80, 78, 75, 72, 70, 68, 65, 62, 60, 58]
        self.provider.mock_data[MetricType.CPU_USAGE] = self._create_metric_points(values)

        analysis = self.analyzer.analyze_trend(MetricType.CPU_USAGE, days=7)

        self.assertIsNotNone(analysis)
        self.assertEqual(analysis.trend_direction, TrendDirection.IMPROVING)
        self.assertLess(analysis.change_percent, 0)
        self.assertIn("改善", analysis.recommendation)

    def test_analyze_trend_degrading(self):
        """测试恶化趋势"""
        # 创建恶化数据（值上升）
        values = [50, 52, 55, 58, 60, 63, 66, 70, 73, 77]
        self.provider.mock_data[MetricType.CPU_USAGE] = self._create_metric_points(values)

        analysis = self.analyzer.analyze_trend(MetricType.CPU_USAGE, days=7)

        self.assertIsNotNone(analysis)
        self.assertEqual(analysis.trend_direction, TrendDirection.DEGRADING)
        self.assertGreater(analysis.change_percent, 0)
        self.assertIn("恶化", analysis.recommendation)

    def test_analyze_trend_stable(self):
        """测试稳定趋势"""
        # 创建稳定数据
        values = [60, 61, 60, 62, 61, 60, 61, 62, 60, 61]
        self.provider.mock_data[MetricType.CPU_USAGE] = self._create_metric_points(values)

        analysis = self.analyzer.analyze_trend(MetricType.CPU_USAGE, days=7)

        self.assertIsNotNone(analysis)
        self.assertEqual(analysis.trend_direction, TrendDirection.STABLE)
        self.assertAlmostEqual(analysis.change_percent, 0, delta=5)

    def test_analyze_trend_volatile(self):
        """测试波动趋势"""
        # 创建波动数据
        values = [50, 80, 45, 85, 40, 90, 35, 95, 30, 100]
        self.provider.mock_data[MetricType.CPU_USAGE] = self._create_metric_points(values)

        analysis = self.analyzer.analyze_trend(MetricType.CPU_USAGE, days=7)

        self.assertIsNotNone(analysis)
        self.assertEqual(analysis.trend_direction, TrendDirection.VOLATILE)
        self.assertIn("波动", analysis.recommendation)

    def test_analyze_trend_insufficient_data(self):
        """测试数据不足"""
        # 只有2个数据点
        values = [50, 52]
        self.provider.mock_data[MetricType.CPU_USAGE] = self._create_metric_points(values)

        analysis = self.analyzer.analyze_trend(MetricType.CPU_USAGE, days=7)

        self.assertIsNone(analysis)

    def test_statistics_calculation(self):
        """测试统计值计算"""
        values = [60, 65, 70, 75, 80, 75, 70, 65, 60, 55]
        self.provider.mock_data[MetricType.CPU_USAGE] = self._create_metric_points(values)

        analysis = self.analyzer.analyze_trend(MetricType.CPU_USAGE, days=7)

        self.assertIsNotNone(analysis)
        self.assertEqual(analysis.historical_min, 55)
        self.assertEqual(analysis.historical_max, 80)
        self.assertAlmostEqual(analysis.historical_avg, 67.5, delta=1)
        self.assertEqual(analysis.current_value, 55)
        self.assertEqual(analysis.data_points, 10)


class TestBaselineComparison(unittest.TestCase):
    """测试基线对比"""

    def setUp(self):
        self.provider = MockDataProvider()
        self.analyzer = TrendAnalyzer(self.provider)

    def test_compare_significant_improvement(self):
        """测试显著改善"""
        baseline = MetricPoint(
            timestamp=datetime.now() - timedelta(days=30),
            metric_type=MetricType.QPS,
            value=1000,
            unit="qps"
        )
        self.provider.mock_baseline = baseline

        comparison = self.analyzer.compare_with_baseline(
            MetricType.QPS, current_value=1300
        )

        self.assertIsNotNone(comparison)
        self.assertEqual(comparison.change_percent, 30.0)
        self.assertTrue(comparison.is_significant)
        # QPS是正向指标，增加是改善，所以severity应该是normal
        self.assertEqual(comparison.severity, "normal")

    def test_compare_significant_degradation(self):
        """测试显著退化"""
        baseline = MetricPoint(
            timestamp=datetime.now() - timedelta(days=30),
            metric_type=MetricType.CPU_USAGE,
            value=50,
            unit="%"
        )
        self.provider.mock_baseline = baseline

        comparison = self.analyzer.compare_with_baseline(
            MetricType.CPU_USAGE, current_value=70
        )

        self.assertIsNotNone(comparison)
        self.assertEqual(comparison.change_percent, 40.0)
        self.assertTrue(comparison.is_significant)
        self.assertEqual(comparison.severity, "critical")

    def test_compare_no_baseline(self):
        """测试无基线数据"""
        self.provider.mock_baseline = None

        comparison = self.analyzer.compare_with_baseline(
            MetricType.CPU_USAGE, current_value=70
        )

        self.assertIsNone(comparison)

    def test_compare_minor_change(self):
        """测试微小变化"""
        baseline = MetricPoint(
            timestamp=datetime.now() - timedelta(days=7),
            metric_type=MetricType.MEMORY_USAGE,
            value=60,
            unit="%"
        )
        self.provider.mock_baseline = baseline

        comparison = self.analyzer.compare_with_baseline(
            MetricType.MEMORY_USAGE, current_value=63
        )

        self.assertIsNotNone(comparison)
        self.assertEqual(comparison.change_percent, 5.0)
        self.assertFalse(comparison.is_significant)
        self.assertEqual(comparison.severity, "normal")


class TestPerformanceDegradationDetection(unittest.TestCase):
    """测试性能退化检测"""

    def setUp(self):
        self.provider = MockDataProvider()
        self.analyzer = TrendAnalyzer(self.provider)

    def test_detect_degradation(self):
        """测试检测退化"""
        # 设置基线
        baseline_cpu = MetricPoint(
            timestamp=datetime.now() - timedelta(days=30),
            metric_type=MetricType.CPU_USAGE,
            value=50,
            unit="%"
        )
        baseline_qps = MetricPoint(
            timestamp=datetime.now() - timedelta(days=30),
            metric_type=MetricType.QPS,
            value=1000,
            unit="qps"
        )

        # 使用side_effect返回不同的基线
        def mock_get_baseline(metric_type, baseline_date=None):
            if metric_type == MetricType.CPU_USAGE:
                return baseline_cpu
            elif metric_type == MetricType.QPS:
                return baseline_qps
            return None

        self.provider.get_baseline = mock_get_baseline

        # 当前值：CPU恶化，QPS恶化（QPS下降才是恶化）
        current_metrics = {
            MetricType.CPU_USAGE: 75,  # 恶化（增加）
            MetricType.QPS: 800        # 恶化（减少）
        }

        degradations = self.analyzer.detect_performance_degradation(
            current_metrics, days=30
        )

        # 应该检测到两个退化
        self.assertEqual(len(degradations), 2)
        metric_types = [d.metric_type for d in degradations]
        self.assertIn(MetricType.CPU_USAGE, metric_types)
        self.assertIn(MetricType.QPS, metric_types)

    def test_no_degradation(self):
        """测试无退化"""
        baseline = MetricPoint(
            timestamp=datetime.now() - timedelta(days=30),
            metric_type=MetricType.CPU_USAGE,
            value=50,
            unit="%"
        )
        self.provider.mock_baseline = baseline

        def mock_get_baseline(metric_type, baseline_date=None):
            return baseline if metric_type == MetricType.CPU_USAGE else None

        self.provider.get_baseline = mock_get_baseline

        # 当前值改善
        current_metrics = {
            MetricType.CPU_USAGE: 40  # 改善
        }

        degradations = self.analyzer.detect_performance_degradation(
            current_metrics, days=30
        )

        self.assertEqual(len(degradations), 0)

    def test_multiple_degradations(self):
        """测试多个退化"""
        baselines = {
            MetricType.CPU_USAGE: MetricPoint(
                timestamp=datetime.now() - timedelta(days=30),
                metric_type=MetricType.CPU_USAGE,
                value=50,
                unit="%"
            ),
            MetricType.MEMORY_USAGE: MetricPoint(
                timestamp=datetime.now() - timedelta(days=30),
                metric_type=MetricType.MEMORY_USAGE,
                value=60,
                unit="%"
            ),
            MetricType.QPS: MetricPoint(
                timestamp=datetime.now() - timedelta(days=30),
                metric_type=MetricType.QPS,
                value=1000,
                unit="qps"
            )
        }

        def mock_get_baseline(metric_type, baseline_date=None):
            return baselines.get(metric_type)

        self.provider.get_baseline = mock_get_baseline

        # 多个指标恶化
        current_metrics = {
            MetricType.CPU_USAGE: 80,      # 恶化
            MetricType.MEMORY_USAGE: 85,   # 恶化
            MetricType.QPS: 800            # 恶化（QPS下降也是问题）
        }

        degradations = self.analyzer.detect_performance_degradation(
            current_metrics, days=30
        )

        # 应该检测到所有退化
        self.assertGreaterEqual(len(degradations), 2)


class TestBatchAnalysis(unittest.TestCase):
    """测试批量分析"""

    def setUp(self):
        self.provider = MockDataProvider()
        self.analyzer = TrendAnalyzer(self.provider)

    def test_batch_analyze_trends(self):
        """测试批量趋势分析"""
        # 为不同指标创建数据
        cpu_values = [50, 52, 55, 58, 60, 63, 66]
        memory_values = [60, 60, 61, 60, 61, 60, 60]

        self.provider.mock_data[MetricType.CPU_USAGE] = [
            MetricPoint(
                timestamp=datetime.now() - timedelta(hours=i),
                metric_type=MetricType.CPU_USAGE,
                value=v,
                unit="%"
            )
            for i, v in enumerate(cpu_values)
        ]

        self.provider.mock_data[MetricType.MEMORY_USAGE] = [
            MetricPoint(
                timestamp=datetime.now() - timedelta(hours=i),
                metric_type=MetricType.MEMORY_USAGE,
                value=v,
                unit="%"
            )
            for i, v in enumerate(memory_values)
        ]

        results = self.analyzer.batch_analyze_trends(
            [MetricType.CPU_USAGE, MetricType.MEMORY_USAGE],
            days=7
        )

        self.assertEqual(len(results), 2)
        self.assertIn(MetricType.CPU_USAGE, results)
        self.assertIn(MetricType.MEMORY_USAGE, results)

        # CPU应该是恶化趋势
        self.assertEqual(results[MetricType.CPU_USAGE].trend_direction, TrendDirection.DEGRADING)

        # 内存应该是稳定趋势
        self.assertEqual(results[MetricType.MEMORY_USAGE].trend_direction, TrendDirection.STABLE)


class TestEdgeCases(unittest.TestCase):
    """测试边界情况"""

    def setUp(self):
        self.provider = MockDataProvider()
        self.analyzer = TrendAnalyzer(self.provider)

    def test_zero_baseline(self):
        """测试基线为0"""
        baseline = MetricPoint(
            timestamp=datetime.now() - timedelta(days=30),
            metric_type=MetricType.SLOW_QUERIES,
            value=0,
            unit="count"
        )
        self.provider.mock_baseline = baseline

        comparison = self.analyzer.compare_with_baseline(
            MetricType.SLOW_QUERIES, current_value=10
        )

        # 基线为0时应该能正常处理
        self.assertIsNotNone(comparison)

    def test_negative_change(self):
        """测试负值变化"""
        baseline = MetricPoint(
            timestamp=datetime.now() - timedelta(days=30),
            metric_type=MetricType.QPS,
            value=1000,
            unit="qps"
        )
        self.provider.mock_baseline = baseline

        comparison = self.analyzer.compare_with_baseline(
            MetricType.QPS, current_value=800
        )

        self.assertIsNotNone(comparison)
        self.assertEqual(comparison.change_percent, -20.0)

    def test_empty_history(self):
        """测试空历史数据"""
        self.provider.mock_data[MetricType.CPU_USAGE] = []

        analysis = self.analyzer.analyze_trend(MetricType.CPU_USAGE, days=7)

        self.assertIsNone(analysis)


if __name__ == "__main__":
    unittest.main(verbosity=2)
