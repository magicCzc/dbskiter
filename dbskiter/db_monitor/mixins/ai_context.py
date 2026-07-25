"""
ai_context mixin for MonitorSkill

Auto-extracted from skill.py.
"""

import logging
from typing import List, Dict, Any, Optional, Callable, Set
from datetime import datetime

from dbskiter.db_monitor.models import (
    MetricType, MetricPoint, AnomalyAlert, MonitorConfig,
    HealthAssessment, CapacityPrediction, HealthStatus,
    AnomalyType, Severity, ErrorCode,
)
from dbskiter.shared.error_handler import create_success_response, create_error_response
from dbskiter.shared.validators import validate_params, Validator


class MonitorAIContextMixin:
    """ai_context for MonitorSkill"""

    def build_ai_context(
        self,
        skill_result: Dict[str, Any],
        scenario: str = "monitor"
    ) -> Dict[str, Any]:
        """
        构建AI分析上下文

        参数:
            skill_result: Skill返回的原始结果
            scenario: 场景标识 (monitor/anomaly_detection/capacity/metrics_collection/metrics_history/capacity_advanced/trend_analysis/baseline_comparison)

        返回:
            Dict[str, Any]: AI上下文
        """
        from dbskiter.shared.ai_context import AIContextBuilder

        builder = AIContextBuilder(
            dialect=self.connector.dialect if hasattr(self.connector, 'dialect') else 'unknown',
            database_name=getattr(self.connector, 'database', ''),
        )
        builder.detect_business_context(self.connector)

        data = skill_result.get("data", {})

        raw_metrics = self._extract_raw_metrics_for_ai(data, scenario)
        rule_flags = self._extract_rule_flags_for_ai(data, scenario)
        context = builder.build_database_profile(self.connector)
        reference_values = self._build_reference_values(scenario)
        ai_hints = self._build_ai_hints(scenario, data)

        inspection_trace = self._build_inspection_trace(scenario, data)

        return {
            "raw_metrics": raw_metrics,
            "rule_flags": rule_flags,
            "context": context,
            "reference_values": reference_values,
            "ai_hints": ai_hints,
            "inspection_trace": inspection_trace,
        }


    def _build_inspection_trace(
        self,
        scenario: str,
        data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        构建监控透明度追踪信息

        参数:
            scenario: 场景标识
            data: Skill返回的data字段

        返回:
            Dict[str, Any]: 追踪信息
        """
        trace = {
            "scenario": scenario,
            "metrics_checked": [],
            "data_sources": [],
            "confidence": "high",
            "notes": []
        }

        # 判断监控数据源
        monitor_source = "直连数据库"
        if self._has_external_monitor():
            monitor_source = self._get_monitor_source()

        if scenario == "monitor":
            trace["metrics_checked"] = [
                {"name": "health_score", "description": "健康评分", "source": monitor_source},
                {"name": "qps", "description": "每秒查询数", "source": monitor_source},
                {"name": "active_connections", "description": "活跃连接数", "source": monitor_source},
                {"name": "cpu_usage", "description": "CPU使用率", "source": monitor_source},
                {"name": "memory_usage", "description": "内存使用", "source": monitor_source},
            ]
            trace["data_sources"] = [monitor_source]

        elif scenario == "anomaly_detection":
            trace["metrics_checked"] = [
                {"name": "metric_baselines", "description": "指标基线", "source": monitor_source},
                {"name": "deviation_analysis", "description": "偏差分析", "source": "统计模型"},
                {"name": "anomaly_patterns", "description": "异常模式识别", "source": "时序分析"},
            ]
            trace["data_sources"] = [monitor_source, "statistical_model"]

        elif scenario in ("capacity", "capacity_advanced"):
            trace["metrics_checked"] = [
                {"name": "disk_usage", "description": "磁盘使用趋势", "source": monitor_source},
                {"name": "growth_rate", "description": "增长率", "source": "历史数据"},
                {"name": "forecast", "description": "容量预测", "source": "趋势外推"},
            ]
            trace["data_sources"] = [monitor_source, "historical_data", "trend_extrapolation"]

        elif scenario == "metrics_collection":
            trace["metrics_checked"] = [
                {"name": "all_available_metrics", "description": "全量指标采集", "source": monitor_source},
            ]
            trace["data_sources"] = [monitor_source]

        elif scenario == "metrics_history":
            trace["metrics_checked"] = [
                {"name": "historical_metrics", "description": "历史指标", "source": monitor_source},
            ]
            trace["data_sources"] = [monitor_source]
            if not data.get("history") and not data.get("metrics"):
                trace["confidence"] = "low"
                trace["notes"].append("未获取到历史数据，可能监控未启用或历史数据已过期")

        elif scenario == "trend_analysis":
            trace["metrics_checked"] = [
                {"name": "metric_trend", "description": "指标趋势", "source": monitor_source},
                {"name": "slope", "description": "变化斜率", "source": "线性回归"},
                {"name": "seasonality", "description": "周期性", "source": "时序分解"},
            ]
            trace["data_sources"] = [monitor_source, "linear_regression", "seasonal_decomposition"]

        elif scenario == "baseline_comparison":
            trace["metrics_checked"] = [
                {"name": "current_value", "description": "当前值", "source": monitor_source},
                {"name": "baseline_value", "description": "基线值", "source": "基线存储"},
                {"name": "deviation", "description": "偏差", "source": "对比计算"},
            ]
            trace["data_sources"] = [monitor_source, "baseline_storage"]

        else:
            trace["metrics_checked"] = [
                {"name": "general_metrics", "description": "通用监控指标", "source": monitor_source}
            ]
            trace["data_sources"] = [monitor_source]
            trace["notes"].append(f"未定义场景 '{scenario}' 的详细追踪，使用通用指标")

        if monitor_source != "直连数据库":
            trace["notes"].append(f"使用外部监控源: {monitor_source}")

        return trace


    def _has_external_monitor(self) -> bool:
        """检查是否使用了外部监控源"""
        # 简化的检测逻辑
        return False


    def _get_monitor_source(self) -> str:
        """获取当前使用的监控源名称"""
        return "直连数据库"


    def _extract_raw_metrics_for_ai(self, data: Dict[str, Any], scenario: str) -> Dict[str, Any]:
        """提取原始指标"""
        metrics = {}

        # 提取关键字段
        key_fields = ["health", "anomalies", "predictions", "trends", "recommendations", "history", "metrics", "summary"]
        for key in key_fields:
            if key in data:
                metrics[key] = data[key]

        # 场景特定提取
        if scenario == "monitor":
            for key in ["health", "score", "status", "metrics", "timestamp"]:
                if key in data:
                    metrics[key] = data[key]
        elif scenario == "anomaly_detection":
            for key in ["anomalies", "anomaly_count", "affected_metrics", "detection_time"]:
                if key in data:
                    metrics[key] = data[key]
        elif scenario in ("capacity", "capacity_advanced"):
            for key in ["predictions", "trends", "recommendations", "current_usage", "forecast_date", "days_until_full"]:
                if key in data:
                    metrics[key] = data[key]
        elif scenario == "metrics_history":
            for key in ["history", "metric_name", "time_range", "data_points", "statistics"]:
                if key in data:
                    metrics[key] = data[key]
        elif scenario == "trend_analysis":
            for key in ["trends", "trend_direction", "growth_rate", "seasonality", "forecast"]:
                if key in data:
                    metrics[key] = data[key]
        elif scenario == "baseline_compare":
            for key in ["comparison", "deviations", "baseline_date", "current_values"]:
                if key in data:
                    metrics[key] = data[key]

        if not metrics:
            metrics = data

        return metrics


    def _extract_rule_flags_for_ai(self, data: Dict[str, Any], scenario: str) -> Dict[str, Any]:
        """提取规则标记"""
        flags = {}

        # 健康评分标记
        health = data.get("health", {})
        if isinstance(health, dict):
            score = health.get("score", 100)
            if isinstance(score, (int, float)):
                if score < 60:
                    flags["poor_health"] = {"flagged": True, "level": "critical", "reason": f"健康评分过低: {score}"}
                elif score < 80:
                    flags["fair_health"] = {"flagged": True, "level": "medium", "reason": f"健康评分一般: {score}"}

        # 异常标记
        anomalies = data.get("anomalies", [])
        if isinstance(anomalies, list) and len(anomalies) > 0:
            critical_anomalies = [a for a in anomalies if a.get("severity") == "critical"]
            if critical_anomalies:
                flags["critical_anomalies"] = {"flagged": True, "level": "critical", "reason": f"发现 {len(critical_anomalies)} 个严重异常"}
            else:
                flags["has_anomalies"] = {"flagged": True, "level": "high", "reason": f"发现 {len(anomalies)} 个异常"}

        # 容量预警标记
        predictions = data.get("predictions", [])
        if isinstance(predictions, list):
            for pred in predictions:
                if isinstance(pred, dict):
                    risk_level = pred.get("risk_level", "")
                    if risk_level == "critical":
                        flags["critical_capacity"] = {"flagged": True, "level": "critical", "reason": "容量即将耗尽"}
                    elif risk_level == "high":
                        flags["high_capacity"] = {"flagged": True, "level": "high", "reason": "容量紧张"}

        # 趋势偏离标记
        trends = data.get("trends", [])
        if isinstance(trends, list):
            for trend in trends:
                if isinstance(trend, dict) and trend.get("deviation") == "significant":
                    flags["significant_deviation"] = {"flagged": True, "level": "high", "reason": "指标显著偏离正常范围"}

        return {"_disclaimer": "规则初筛结果仅供参考", "flags": flags}


    def _build_reference_values(self, scenario: str) -> Dict[str, Any]:
        """构建参考基线"""
        refs = {
            "health_score": {"excellent": "90-100", "good": "80-89", "fair": "60-79", "poor": "<60"},
            "capacity_threshold": {"normal": "<70%", "warning": "70-85%", "critical": ">85%"},
            "anomaly_severity": {"info": "信息", "warning": "警告", "critical": "严重"},
            "trend_deviation": {"normal": "<10%", "warning": "10-30%", "critical": ">30%"},
        }
        return refs


    def _build_ai_hints(self, scenario: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """构建AI提示"""
        hints = {"focus_areas": [], "related_commands": []}
        db_name = getattr(self.connector, 'database', '')

        health = data.get("health", {})
        anomalies = data.get("anomalies", [])
        score = health.get("score", 100) if isinstance(health, dict) else 100

        if scenario == "monitor":
            hints["focus_areas"] = ["health_trends", "resource_utilization", "performance_metrics"]

            if isinstance(score, (int, float)):
                if score >= 90:
                    hints["focus_areas"].append("maintain_excellent_health")
                elif score >= 80:
                    hints["focus_areas"].append("minor_optimizations")
                elif score >= 60:
                    hints["focus_areas"].append("performance_improvements")
                else:
                    hints["focus_areas"].append("urgent_attention_required")

            hints["related_commands"] = [
                f"dbskiter --database={db_name} monitor anomalies",
                f"dbskiter --database={db_name} diagnose realtime",
            ]

        elif scenario == "anomaly_detection":
            hints["focus_areas"] = ["anomaly_patterns", "root_cause_analysis", "correlation_analysis"]

            if isinstance(anomalies, list) and anomalies:
                hints["focus_areas"].append("immediate_investigation")

            hints["related_commands"] = [
                f"dbskiter --database={db_name} inspector root-cause --issue='性能异常'",
                f"dbskiter --database={db_name} diagnose top",
            ]

        elif scenario == "capacity":
            hints["focus_areas"] = ["growth_trends", "resource_planning", "scaling_needs"]

            predictions = data.get("predictions", [])
            if isinstance(predictions, list):
                for pred in predictions:
                    if isinstance(pred, dict) and pred.get("days_until_full", 999) < 30:
                        hints["focus_areas"].append("urgent_capacity_planning")

            hints["related_commands"] = [
                f"dbskiter --database={db_name} monitor capacity-advanced",
                f"dbskiter --database={db_name} inspector run --type capacity",
            ]

        elif scenario == "trend_analysis":
            hints["focus_areas"] = ["trend_patterns", "seasonality", "forecast_accuracy"]
            hints["related_commands"] = [
                f"dbskiter --database={db_name} monitor compare",
            ]

        elif scenario == "baseline_compare":
            hints["focus_areas"] = ["performance_deviation", "configuration_drift", "workload_changes"]

        return hints



