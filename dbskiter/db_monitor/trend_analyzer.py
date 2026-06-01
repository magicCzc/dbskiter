"""
历史趋势分析器 - 与db-diagnose集成

文件功能：提供历史趋势分析能力，支持db-diagnose的性能快照
主要类：
    - TrendAnalyzer: 趋势分析器
    - HistoricalDataProvider: 历史数据提供者

集成点：
    - 为db-diagnose提供历史趋势数据
    - 支持性能对比分析（当前vs历史）
    - 检测性能退化

作者: AI Assistant
创建时间: 2026-04-24
版本: 1.0.0
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from enum import Enum

from dbskiter.db_monitor.storage import MetricsStorage
from dbskiter.db_monitor.models import MetricPoint, MetricType

logger = logging.getLogger(__name__)


class TrendDirection(Enum):
    """趋势方向枚举"""
    IMPROVING = "improving"      # 性能改善
    DEGRADING = "degrading"      # 性能退化
    STABLE = "stable"            # 性能稳定
    VOLATILE = "volatile"        # 波动较大


@dataclass
class TrendAnalysis:
    """趋势分析结果"""
    metric_type: MetricType
    current_value: float
    historical_avg: float
    historical_min: float
    historical_max: float
    change_percent: float
    trend_direction: TrendDirection
    confidence: float
    analysis_period_days: int
    data_points: int
    recommendation: str


@dataclass
class PerformanceComparison:
    """性能对比结果"""
    metric_type: MetricType
    current_value: float
    baseline_value: float
    baseline_time: datetime
    change_percent: float
    is_significant: bool
    severity: str  # "normal", "warning", "critical"
    message: str


class HistoricalDataProvider(ABC):
    """历史数据提供者抽象基类"""

    @abstractmethod
    def get_metric_history(
        self,
        metric_type: MetricType,
        days: int = 7
    ) -> List[MetricPoint]:
        """
        获取指标历史数据

        参数:
            metric_type: 指标类型
            days: 查询天数

        返回:
            List[MetricPoint]: 历史数据点列表
        """
        pass

    @abstractmethod
    def get_baseline(
        self,
        metric_type: MetricType,
        baseline_date: Optional[datetime] = None
    ) -> Optional[MetricPoint]:
        """
        获取基线数据

        参数:
            metric_type: 指标类型
            baseline_date: 基线日期，None表示使用最早的记录

        返回:
            Optional[MetricPoint]: 基线数据点
        """
        pass


class StorageBasedDataProvider(HistoricalDataProvider):
    """基于存储的历史数据提供者"""

    def __init__(self, storage: MetricsStorage):
        """
        初始化

        参数:
            storage: 指标存储实例
        """
        self.storage = storage

    def get_metric_history(
        self,
        metric_type: MetricType,
        days: int = 7
    ) -> List[MetricPoint]:
        """从存储获取历史数据"""
        try:
            end_time = datetime.now()
            start_time = end_time - timedelta(days=days)

            return self.storage.query_metrics(
                metric_type=metric_type,
                start_time=start_time,
                end_time=end_time
            )
        except Exception as e:
            logger.error(f"获取历史数据失败: {e}")
            return []

    def get_baseline(
        self,
        metric_type: MetricType,
        baseline_date: Optional[datetime] = None
    ) -> Optional[MetricPoint]:
        """获取基线数据"""
        try:
            if baseline_date:
                # 获取指定日期的数据
                start_time = baseline_date.replace(hour=0, minute=0, second=0)
                end_time = baseline_date.replace(hour=23, minute=59, second=59)

                points = self.storage.query_metrics(
                    metric_type=metric_type,
                    start_time=start_time,
                    end_time=end_time
                )

                if points:
                    # 返回平均值
                    avg_value = sum(p.value for p in points) / len(points)
                    return MetricPoint(
                        timestamp=baseline_date,
                        metric_type=metric_type,
                        value=avg_value,
                        unit=points[0].unit if points else ""
                    )
            else:
                # 获取最早的记录
                return self.storage.get_earliest_metric(metric_type)

        except Exception as e:
            logger.error(f"获取基线数据失败: {e}")
            return None


class TrendAnalyzer:
    """
    趋势分析器

    提供历史趋势分析能力，支持：
    - 趋势方向判断
    - 性能对比分析
    - 异常波动检测

    使用示例:
        >>> analyzer = TrendAnalyzer(data_provider)
        >>> trend = analyzer.analyze_trend(MetricType.CPU_USAGE, days=7)
        >>> comparison = analyzer.compare_with_baseline(MetricType.QPS)
    """

    # 显著变化阈值（百分比）
    SIGNIFICANT_CHANGE_THRESHOLD = 15.0

    # 性能退化阈值（百分比）
    DEGRADATION_THRESHOLD = 20.0

    def __init__(self, data_provider: HistoricalDataProvider):
        """
        初始化趋势分析器

        参数:
            data_provider: 历史数据提供者
        """
        self.data_provider = data_provider

    def analyze_trend(
        self,
        metric_type: MetricType,
        days: int = 7
    ) -> Optional[TrendAnalysis]:
        """
        分析指标趋势

        参数:
            metric_type: 指标类型
            days: 分析天数

        返回:
            Optional[TrendAnalysis]: 趋势分析结果
        """
        # 获取历史数据
        history = self.data_provider.get_metric_history(metric_type, days)

        if len(history) < 3:
            logger.warning(f"{metric_type.value} 历史数据不足，无法分析趋势")
            return None

        # 提取数值
        values = [p.value for p in history]
        current_value = values[-1]

        # 计算统计值
        historical_avg = sum(values) / len(values)
        historical_min = min(values)
        historical_max = max(values)

        # 计算变化百分比
        if historical_avg != 0:
            change_percent = ((current_value - historical_avg) / historical_avg) * 100
        else:
            change_percent = 0.0

        # 判断趋势方向
        trend_direction = self._determine_trend_direction(values, change_percent)

        # 计算置信度（基于数据量）
        confidence = min(1.0, len(values) / 30.0)

        # 生成建议
        recommendation = self._generate_recommendation(
            metric_type, trend_direction, change_percent, confidence
        )

        return TrendAnalysis(
            metric_type=metric_type,
            current_value=current_value,
            historical_avg=historical_avg,
            historical_min=historical_min,
            historical_max=historical_max,
            change_percent=change_percent,
            trend_direction=trend_direction,
            confidence=confidence,
            analysis_period_days=days,
            data_points=len(history),
            recommendation=recommendation
        )

    def compare_with_baseline(
        self,
        metric_type: MetricType,
        current_value: float,
        baseline_date: Optional[datetime] = None
    ) -> Optional[PerformanceComparison]:
        """
        与基线对比

        参数:
            metric_type: 指标类型
            current_value: 当前值
            baseline_date: 基线日期

        返回:
            Optional[PerformanceComparison]: 对比结果
        """
        # 获取基线数据
        baseline = self.data_provider.get_baseline(metric_type, baseline_date)

        if not baseline:
            logger.warning(f"{metric_type.value} 无法获取基线数据")
            return None

        baseline_value = baseline.value

        # 计算变化
        if baseline_value != 0:
            change_percent = ((current_value - baseline_value) / baseline_value) * 100
        else:
            change_percent = 0.0

        # 判断是否显著变化
        is_significant = abs(change_percent) > self.SIGNIFICANT_CHANGE_THRESHOLD

        # 确定严重程度
        severity = self._determine_severity(change_percent, metric_type)

        # 生成消息
        message = self._generate_comparison_message(
            metric_type, current_value, baseline_value, change_percent, severity
        )

        return PerformanceComparison(
            metric_type=metric_type,
            current_value=current_value,
            baseline_value=baseline_value,
            baseline_time=baseline.timestamp,
            change_percent=change_percent,
            is_significant=is_significant,
            severity=severity,
            message=message
        )

    def detect_performance_degradation(
        self,
        metrics: Dict[MetricType, float],
        days: int = 7
    ) -> List[PerformanceComparison]:
        """
        检测性能退化

        参数:
            metrics: 当前指标值字典 {metric_type: value}
            days: 对比天数

        返回:
            List[PerformanceComparison]: 退化指标列表
        """
        degradations = []

        # 正向指标（值增加是改善）
        positive_metrics = [
            MetricType.QPS, MetricType.TPS,
            MetricType.COM_SELECT, MetricType.COM_INSERT,
            MetricType.COM_UPDATE, MetricType.COM_DELETE,
            MetricType.BUFFER_HIT_RATIO, MetricType.CACHE_HIT_RATIO
        ]

        for metric_type, current_value in metrics.items():
            comparison = self.compare_with_baseline(
                metric_type, current_value
            )

            if comparison and comparison.severity in ["warning", "critical"]:
                is_positive = metric_type in positive_metrics

                # 判断是否为退化
                if is_positive:
                    # 正向指标：减少是退化
                    if comparison.change_percent < 0:
                        degradations.append(comparison)
                else:
                    # 负向指标：增加是退化
                    if comparison.change_percent > 0:
                        degradations.append(comparison)

        # 按严重程度排序
        severity_order = {"critical": 0, "warning": 1, "normal": 2}
        degradations.sort(key=lambda x: severity_order.get(x.severity, 3))

        return degradations

    def batch_analyze_trends(
        self,
        metric_types: List[MetricType],
        days: int = 7
    ) -> Dict[MetricType, Optional[TrendAnalysis]]:
        """
        批量分析多个指标趋势

        参数:
            metric_types: 指标类型列表
            days: 分析天数

        返回:
            Dict[MetricType, Optional[TrendAnalysis]]: 趋势分析结果字典
        """
        results = {}
        for metric_type in metric_types:
            results[metric_type] = self.analyze_trend(metric_type, days)
        return results

    def _determine_trend_direction(
        self,
        values: List[float],
        change_percent: float
    ) -> TrendDirection:
        """判断趋势方向"""
        if len(values) < 2:
            return TrendDirection.STABLE

        # 计算标准差判断波动性
        if len(values) > 1:
            import statistics
            try:
                std = statistics.stdev(values)
                mean = statistics.mean(values)
                cv = std / mean if mean != 0 else 0  # 变异系数

                if cv > 0.3:  # 变异系数大于30%认为波动较大
                    return TrendDirection.VOLATILE
            except statistics.StatisticsError:
                pass

        # 根据变化百分比判断
        if abs(change_percent) < 5:
            return TrendDirection.STABLE
        elif change_percent > 0:
            return TrendDirection.DEGRADING  # 值增加通常是退化
        else:
            return TrendDirection.IMPROVING

    def _determine_severity(
        self,
        change_percent: float,
        metric_type: MetricType
    ) -> str:
        """确定严重程度"""
        abs_change = abs(change_percent)

        # 判断是否为正向指标（值增加是改善）
        positive_metrics = [
            MetricType.QPS, MetricType.TPS,
            MetricType.COM_SELECT, MetricType.COM_INSERT,
            MetricType.COM_UPDATE, MetricType.COM_DELETE,
            MetricType.BUFFER_HIT_RATIO, MetricType.CACHE_HIT_RATIO
        ]

        is_positive = metric_type in positive_metrics

        # 对于正向指标，增加是正常的；对于负向指标，增加是退化
        if is_positive and change_percent > 0:
            # 正向指标增加是改善
            if abs_change > self.DEGRADATION_THRESHOLD:
                return "normal"  # 大幅改善不算问题
            elif abs_change > self.SIGNIFICANT_CHANGE_THRESHOLD:
                return "normal"
            else:
                return "normal"
        elif not is_positive and change_percent < 0:
            # 负向指标减少是改善
            return "normal"
        else:
            # 退化情况
            if abs_change > self.DEGRADATION_THRESHOLD:
                return "critical"
            elif abs_change > self.SIGNIFICANT_CHANGE_THRESHOLD:
                return "warning"
            else:
                return "normal"

    def _generate_recommendation(
        self,
        metric_type: MetricType,
        trend_direction: TrendDirection,
        change_percent: float,
        confidence: float
    ) -> str:
        """生成建议"""
        if confidence < 0.3:
            return "数据不足，建议继续观察"

        if trend_direction == TrendDirection.VOLATILE:
            return f"{metric_type.value} 波动较大，建议检查是否有周期性负载或异常"

        if trend_direction == TrendDirection.DEGRADING:
            if change_percent > 50:
                return f"{metric_type.value} 严重恶化（+{change_percent:.1f}%），建议立即调查原因"
            else:
                return f"{metric_type.value} 呈恶化趋势（+{change_percent:.1f}%），建议关注"

        if trend_direction == TrendDirection.IMPROVING:
            return f"{metric_type.value} 持续改善（{change_percent:.1f}%），优化措施有效"

        return f"{metric_type.value} 表现稳定"

    def _generate_comparison_message(
        self,
        metric_type: MetricType,
        current_value: float,
        baseline_value: float,
        change_percent: float,
        severity: str
    ) -> str:
        """生成对比消息"""
        direction = "上升" if change_percent > 0 else "下降"

        if severity == "critical":
            return (
                f"{metric_type.value} 较基线{direction} {abs(change_percent):.1f}%，"
                f"当前 {current_value:.2f}，基线 {baseline_value:.2f}，需要立即处理"
            )
        elif severity == "warning":
            return (
                f"{metric_type.value} 较基线{direction} {abs(change_percent):.1f}%，"
                f"当前 {current_value:.2f}，基线 {baseline_value:.2f}，建议关注"
            )
        else:
            return (
                f"{metric_type.value} 较基线{direction} {abs(change_percent):.1f}%，"
                f"在正常范围内"
            )


# 便捷函数，用于与db-diagnose集成
def create_trend_analyzer_with_storage(storage_path: str) -> TrendAnalyzer:
    """
    使用存储路径创建趋势分析器

    参数:
        storage_path: 存储路径

    返回:
        TrendAnalyzer: 趋势分析器实例
    """
    storage = MetricsStorage(storage_path)
    provider = StorageBasedDataProvider(storage)
    return TrendAnalyzer(provider)
