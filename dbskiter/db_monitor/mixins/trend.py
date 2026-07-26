"""
trend mixin for MonitorSkill

Auto-extracted from skill.py.
"""

import logging
logger = logging.getLogger(__name__)
from typing import List, Dict, Any, Optional, Callable, Set
from datetime import datetime

from dbskiter.db_monitor.models import (
    MetricType, MetricPoint, AnomalyAlert, MonitorConfig,
    HealthAssessment, CapacityPrediction, HealthStatus,
    AnomalyType, Severity, ErrorCode,
)
from dbskiter.shared.error_handler import create_success_response, create_error_response
from dbskiter.shared.validators import validate_params, Validator


class TrendMixin:
    """trend for MonitorSkill"""

    def analyze_trend(
        self,
        metric: str,
        days: int = 7
    ) -> Dict[str, Any]:
        """
        分析指标趋势（与db-diagnose集成）

        参数:
            metric: 指标名称
            days: 分析天数

        返回:
            Dict: 趋势分析结果
        """
        if not ADVANCED_FEATURES_AVAILABLE:
            return create_error_response(
                "趋势分析功能不可用",
                error_code=ErrorCode.NOT_IMPLEMENTED
            )

        if not self.trend_analyzer:
            return create_error_response(
                "趋势分析需要启用持久化存储",
                error_code=ErrorCode.STORAGE_ERROR
            )

        try:
            metric_enum = MetricType(metric)
            analysis = self.trend_analyzer.analyze_trend(metric_enum, days)

            if not analysis:
                return create_error_response(
                    "历史数据不足，无法分析趋势",
                    error_code=ErrorCode.INSUFFICIENT_HISTORY
                )

            return create_success_response(
                message=f"趋势分析完成: {analysis.trend_direction.value}",
                data={
                    "metric_type": analysis.metric_type.value,
                    "current_value": round(analysis.current_value, 2),
                    "historical_avg": round(analysis.historical_avg, 2),
                    "historical_min": round(analysis.historical_min, 2),
                    "historical_max": round(analysis.historical_max, 2),
                    "change_percent": round(analysis.change_percent, 2),
                    "trend_direction": analysis.trend_direction.value,
                    "confidence": round(analysis.confidence, 2),
                    "analysis_period_days": analysis.analysis_period_days,
                    "data_points": analysis.data_points,
                    "recommendation": analysis.recommendation
                }
            )

        except ValueError:
            return create_error_response(
                f"未知的指标类型: {metric}",
                error_code=ErrorCode.INVALID_METRIC_TYPE
            )
        except Exception as e:
            logger.error(f"趋势分析失败: {e}")
            return create_error_response(
                "趋势分析失败",
                error_code=ErrorCode.UNKNOWN_ERROR,
                details={"error": str(e)}
            )


    def compare_with_baseline(
        self,
        metric: str,
        current_value: float,
        baseline_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        与基线对比（与db-diagnose集成）

        参数:
            metric: 指标名称
            current_value: 当前值
            baseline_date: 基线日期（ISO格式），None表示使用最早记录

        返回:
            Dict: 对比结果
        """
        if not ADVANCED_FEATURES_AVAILABLE:
            return create_error_response(
                "基线对比功能不可用",
                error_code=ErrorCode.NOT_IMPLEMENTED
            )

        if not self.trend_analyzer:
            return create_error_response(
                "基线对比需要启用持久化存储",
                error_code=ErrorCode.STORAGE_ERROR
            )

        try:
            metric_enum = MetricType(metric)

            # 解析基线日期
            baseline_dt = None
            if baseline_date:
                baseline_dt = datetime.fromisoformat(baseline_date)

            comparison = self.trend_analyzer.compare_with_baseline(
                metric_enum, current_value, baseline_dt
            )

            if not comparison:
                return create_error_response(
                    "无法获取基线数据",
                    error_code=ErrorCode.NOT_FOUND
                )

            return create_success_response(
                message=comparison.message,
                data={
                    "metric_type": comparison.metric_type.value,
                    "current_value": round(comparison.current_value, 2),
                    "baseline_value": round(comparison.baseline_value, 2),
                    "baseline_time": comparison.baseline_time.isoformat(),
                    "change_percent": round(comparison.change_percent, 2),
                    "is_significant": comparison.is_significant,
                    "severity": comparison.severity
                }
            )

        except ValueError as e:
            return create_error_response(
                f"参数错误: {e}",
                error_code=ErrorCode.INVALID_PARAMS
            )
        except Exception as e:
            logger.error(f"基线对比失败: {e}")
            return create_error_response(
                "基线对比失败",
                error_code=ErrorCode.UNKNOWN_ERROR,
                details={"error": str(e)}
            )


