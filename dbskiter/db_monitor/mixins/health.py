"""
health mixin for MonitorSkill

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
from dbskiter.db_monitor.health_scorer import get_health_scorer


class HealthMixin:
    """health for MonitorSkill"""

    def assess_health(self) -> Dict[str, Any]:
        """
        评估数据库健康状况（已接入多步骤计时）

        使用基于权重的评分算法，支持不同数据库类型的差异化评分

        返回:
            Dict: 健康评估结果，包含 _execution_time 步骤耗时
        """
        from dbskiter.shared.execution_timer import ExecutionTimer
        timer = ExecutionTimer().start()

        # 如果有外部监控系统，优先使用
        if not self.collector and self.zabbix_client:
            with timer.step("prometheus_health", "从 Prometheus 获取健康评估"):
                result = self._assess_health_from_zabbix()
            result["_execution_time"] = timer.to_summary()
            return result

        if not self.collector and self.prometheus_client:
            with timer.step("prometheus_health", "从 Prometheus 获取健康评估"):
                result = self._assess_health_from_prometheus()
            result["_execution_time"] = timer.to_summary()
            return result

        if not self.collector:
            return create_error_response(
                "未提供数据库连接器",
                error_code=ErrorCode.CONNECTION_ERROR
            )

        try:
            # 采集指标
            with timer.step("collect_metrics", "采集数据库指标"):
                metrics = self.collector.collect_all_metrics()

            if not metrics:
                assessment = HealthAssessment(
                    status=HealthStatus.UNKNOWN,
                    score=0,
                    issues=["无法连接到数据库或采集指标"]
                )
                result = create_success_response(
                    message="无法采集指标",
                    data=assessment.to_dict()
                )
                result["_execution_time"] = timer.to_summary()
                return result

            # 构建指标字典
            with timer.step("build_metrics", "构建指标字典"):
                metrics_dict: Dict[MetricType, float] = {}
                metrics_summary: Dict[str, float] = {}
                max_connections = 2000.0

                for metric in metrics:
                    metrics_dict[metric.metric_type] = metric.value
                    metrics_summary[metric.metric_type.value] = round(metric.value, 2)

                    # 记录最大连接数
                    if metric.metric_type == MetricType.CONNECTIONS_MAX:
                        max_connections = metric.value

            # 使用健康评分器计算分数
            with timer.step("calculate_score", "计算健康评分"):
                scorer = get_health_scorer()
                score, status, issues = scorer.calculate_score(
                    metrics=metrics_dict,
                    db_type=self.dialect or "unknown",
                    max_connections=max_connections
                )

                assessment = HealthAssessment(
                    status=status,
                    score=score,
                    issues=issues,
                    metrics_summary=metrics_summary
                )

                result = create_success_response(
                    message=f"健康评估完成: {status.value}",
                    data=assessment.to_dict()
                )

            result["_execution_time"] = timer.to_summary()
            return result

        except Exception as e:
            logger.error(f"健康评估失败: {e}", exc_info=True)
            return create_error_response(
                "健康评估失败",
                error_code=ErrorCode.UNKNOWN_ERROR,
                details={"error": str(e)}
            )


    def _assess_health_from_prometheus(self) -> Dict[str, Any]:
        """
        从 Prometheus 获取数据进行健康评估

        返回:
            Dict: 健康评估结果
        """
        try:
            from dbskiter.shared.prometheus_client import RDSMetrics

            host_name = self._get_host_name()
            if not host_name:
                return create_error_response(
                    "无法确定实例名",
                    error_code=ErrorCode.CONFIG_INVALID
                )

            rds_metrics = RDSMetrics(self.prometheus_client)
            metrics_data = rds_metrics.get_current_metrics(host_name)

            # 获取核心指标
            metrics_summary = {}
            score = 100
            issues = []

            prom_metrics = metrics_data.get('metrics', {})

            # CPU 使用率
            cpu_info = prom_metrics.get('cpu', {})
            if cpu_info.get('value') is not None:
                cpu_value = float(cpu_info['value'])
                metrics_summary["cpu_usage"] = round(cpu_value, 2)
                if cpu_value > 80:
                    score -= 20
                    issues.append(f"CPU 使用率过高: {cpu_value:.1f}%")
                elif cpu_value > 70:
                    score -= 10
                    issues.append(f"CPU 使用率较高: {cpu_value:.1f}%")

            # 内存使用率
            memory_info = prom_metrics.get('memory', {})
            if memory_info.get('value') is not None:
                memory_value = float(memory_info['value'])
                metrics_summary["memory_usage"] = round(memory_value, 2)
                if memory_value > 90:
                    score -= 20
                    issues.append(f"内存使用率过高: {memory_value:.1f}%")
                elif memory_value > 80:
                    score -= 10
                    issues.append(f"内存使用率较高: {memory_value:.1f}%")

            # 磁盘使用率
            disk_info = prom_metrics.get('disk_util', {})
            if disk_info.get('value') is not None:
                disk_value = float(disk_info['value'])
                metrics_summary["disk_usage"] = round(disk_value, 2)
                if disk_value > 85:
                    score -= 15
                    issues.append(f"磁盘使用率过高: {disk_value:.1f}%")
                elif disk_value > 70:
                    score -= 5
                    issues.append(f"磁盘使用率较高: {disk_value:.1f}%")

            # 活跃连接数
            conn_info = prom_metrics.get('connections_active', {})
            if conn_info.get('value') is not None:
                conn_value = float(conn_info['value'])
                metrics_summary["connections_active"] = round(conn_value, 2)
                if conn_value > 1000:
                    score -= 15
                    issues.append(f"活跃连接数过多: {conn_value:.0f}")
                elif conn_value > 500:
                    score -= 5
                    issues.append(f"活跃连接数较多: {conn_value:.0f}")

            # 慢查询数
            slow_info = prom_metrics.get('slow_queries', {})
            if slow_info.get('value') is not None:
                slow_value = float(slow_info['value'])
                metrics_summary["slow_queries"] = round(slow_value, 2)
                if slow_value > 10:
                    score -= 10
                    issues.append(f"慢查询数较多: {slow_value:.0f}")

            # 磁盘 IO 使用率
            io_info = prom_metrics.get('vm_ioutils', {})
            if io_info.get('value') is not None:
                io_value = float(io_info['value'])
                metrics_summary["disk_io_util"] = round(io_value, 2)
                if io_value > 80:
                    score -= 10
                    issues.append(f"磁盘 IO 使用率过高: {io_value:.1f}%")

            # 确定状态
            if score >= 90:
                status = HealthStatus.HEALTHY
            elif score >= 70:
                status = HealthStatus.WARNING
            else:
                status = HealthStatus.CRITICAL

            assessment = HealthAssessment(
                status=status,
                score=max(0, score),
                issues=issues,
                metrics_summary=metrics_summary
            )

            return create_success_response(
                message=f"健康评估完成: {status.value}",
                data=assessment.to_dict()
            )

        except Exception as e:
            logger.error(f"Prometheus 健康评估失败: {e}")
            return create_error_response(
                "Prometheus 健康评估失败",
                error_code=ErrorCode.UNKNOWN_ERROR,
                details={"error": str(e)}
            )


    def _assess_health_from_zabbix(self) -> Dict[str, Any]:
        """
        从 Zabbix 获取数据进行健康评估

        返回:
            Dict: 健康评估结果
        """
        try:
            from dbskiter.shared.oracle_metrics import OracleHostMapping

            host_name = self._get_host_name()
            if not host_name:
                return create_error_response(
                    "无法确定主机名",
                    error_code=ErrorCode.CONFIG_INVALID
                )

            # 获取主机列表
            all_hosts = self.zabbix_client.get_hosts()

            # 判断是否为 Oracle 资产组
            if OracleHostMapping.is_oracle_group(host_name):
                group_hosts = OracleHostMapping.get_group_hosts(host_name)
                matching_hosts = [
                    h for h in all_hosts
                    if any(pattern in h.get("host", "") for pattern in group_hosts)
                ]
            else:
                # 单主机查询
                matching_hosts = [h for h in all_hosts if h.get("host") == host_name]

            if not matching_hosts:
                return create_error_response(
                    f"在 Zabbix 中未找到主机: {host_name}",
                    error_code=ErrorCode.NOT_FOUND
                )

            # 获取关键指标
            metrics_summary = {}
            score = 100
            issues = []

            # 获取 CPU 使用率
            for host in matching_hosts:
                cpu_items = self.zabbix_client.get_items(host["hostid"], "system.cpu.util")
                if cpu_items:
                    history = self.zabbix_client.get_history(cpu_items[0]["itemid"], hours=1, limit=1)
                    if history:
                        cpu_value = float(history[0].get("value", 0))
                        metrics_summary["cpu_usage"] = round(cpu_value, 2)
                        if cpu_value > 80:
                            score -= 20
                            issues.append(f"CPU 使用率过高: {cpu_value:.1f}%")
                        break

            # 获取内存使用率
            for host in matching_hosts:
                memory_items = self.zabbix_client.get_items(host["hostid"], "vm.memory.size")
                pused_items = [i for i in memory_items if "pused" in i.get("key_", "")]
                if pused_items:
                    history = self.zabbix_client.get_history(pused_items[0]["itemid"], hours=1, limit=1)
                    if history:
                        memory_value = float(history[0].get("value", 0))
                        metrics_summary["memory_usage"] = round(memory_value, 2)
                        if memory_value > 90:
                            score -= 20
                            issues.append(f"内存使用率过高: {memory_value:.1f}%")
                        break

            # 确定状态
            if score >= 90:
                status = HealthStatus.HEALTHY
            elif score >= 70:
                status = HealthStatus.WARNING
            else:
                status = HealthStatus.CRITICAL

            assessment = HealthAssessment(
                status=status,
                score=max(0, score),
                issues=issues,
                metrics_summary=metrics_summary
            )

            return create_success_response(
                message=f"健康评估完成: {status.value}",
                data=assessment.to_dict()
            )

        except Exception as e:
            logger.error(f"Zabbix 健康评估失败: {e}")
            return create_error_response(
                "Zabbix 健康评估失败",
                error_code=ErrorCode.UNKNOWN_ERROR,
                details={"error": str(e)}
            )

    # ==================== 实时监控 ====================


