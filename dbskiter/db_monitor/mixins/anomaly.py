"""
anomaly mixin for MonitorSkill

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


class AnomalyMixin:
    """anomaly for MonitorSkill"""

    def detect_anomalies(
        self,
        metric_types: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        执行异常检测（已接入多步骤计时）

        参数:
            metric_types: 指定指标类型，None表示全部

        返回:
            Dict: 检测到的异常列表，包含 _execution_time 步骤耗时
        """
        from dbskiter.shared.execution_timer import ExecutionTimer
        timer = ExecutionTimer().start()

        if not self.collector:
            return create_error_response(
                "未提供数据库连接器",
                error_code=ErrorCode.CONNECTION_ERROR
            )

        try:
            # 采集当前指标
            with timer.step("collect_metrics", "采集当前指标"):
                metrics = self.collector.collect_all_metrics()

            # 过滤指定指标
            with timer.step("filter_metrics", "过滤指定指标"):
                if metric_types:
                    metrics = [
                        m for m in metrics
                        if m.metric_type.value in metric_types
                    ]

            # 检测异常
            with timer.step("detect_anomalies", "检测异常模式"):
                anomalies = []
                for metric in metrics:
                    alert = self.detector.detect(metric)
                    if alert:
                        # 检查告警冷却
                        if self.alert_manager.should_alert(alert.alert_id):
                            anomalies.append(alert)

                            # 保存告警
                            if self.storage:
                                self.storage.save_alert(alert)

                            # 触发处理器
                            for handler in self._alert_handlers:
                                try:
                                    handler(alert)
                                except Exception as e:
                                    logger.error(f"告警处理器执行失败: {e}")

            # 构建指标列表（包含当前值和状态）
            with timer.step("build_result", "构建结果数据"):
                metrics_list = []
                for metric in metrics:
                    # 检查该指标是否有异常
                    has_anomaly = any(
                        a.metric_type == metric.metric_type
                        for a in anomalies
                    )
                    metrics_list.append({
                        "name": metric.metric_type.value,
                        "value": round(metric.value, 2),
                        "unit": metric.unit,
                        "status": "anomaly" if has_anomaly else "normal"
                    })

                result = create_success_response(
                    message=f"检测到 {len(anomalies)} 个异常",
                    data={
                        "anomalies": [a.to_dict() for a in anomalies],
                        "total_checked": len(metrics),
                        "metrics": metrics_list
                    }
                )

            result["_execution_time"] = timer.to_summary()
            return result

        except Exception as e:
            logger.error(f"异常检测失败: {e}")
            return create_error_response(
                "异常检测失败",
                error_code=ErrorCode.DETECTION_FAILED,
                details={"error": str(e)}
            )

    # ==================== 容量预测 ====================

    @validate_params(metric=Validator.not_empty_string)

    def detect_performance_degradation(
        self,
        metrics: Dict[str, float],
        days: int = 7
    ) -> Dict[str, Any]:
        """
        检测性能退化（与db-diagnose集成）

        参数:
            metrics: 当前指标值字典 {metric_name: value}
            days: 对比天数

        返回:
            Dict: 退化指标列表
        """
        if not ADVANCED_FEATURES_AVAILABLE:
            return create_error_response(
                "性能退化检测功能不可用",
                error_code=ErrorCode.NOT_IMPLEMENTED
            )

        if not self.trend_analyzer:
            return create_error_response(
                "性能退化检测需要启用持久化存储",
                error_code=ErrorCode.STORAGE_ERROR
            )

        try:
            # 转换指标类型
            metrics_enum = {}
            for metric_name, value in metrics.items():
                metrics_enum[MetricType(metric_name)] = value

            degradations = self.trend_analyzer.detect_performance_degradation(
                metrics_enum, days
            )

            return create_success_response(
                message=f"检测到 {len(degradations)} 个性能退化指标",
                data={
                    "degradation_count": len(degradations),
                    "degradations": [
                        {
                            "metric_type": d.metric_type.value,
                            "current_value": round(d.current_value, 2),
                            "baseline_value": round(d.baseline_value, 2),
                            "change_percent": round(d.change_percent, 2),
                            "severity": d.severity,
                            "message": d.message
                        }
                        for d in degradations
                    ]
                }
            )

        except ValueError as e:
            return create_error_response(
                f"参数错误: {e}",
                error_code=ErrorCode.INVALID_PARAMS
            )
        except Exception as e:
            logger.error(f"性能退化检测失败: {e}")
            return create_error_response(
                "性能退化检测失败",
                error_code=ErrorCode.UNKNOWN_ERROR,
                details={"error": str(e)}
            )

    # ==================== AI上下文构建 ====================


