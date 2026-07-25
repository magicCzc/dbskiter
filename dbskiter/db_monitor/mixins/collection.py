"""
collection mixin for MonitorSkill

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


class CollectionMixin:
    """collection for MonitorSkill"""

    def collect_metrics(
        self,
        metric_types: Optional[List[str]] = None,
        source: str = "auto"
    ) -> Dict[str, Any]:
        """
        采集数据库指标

        参数:
            metric_types: 指定指标类型列表，None表示全部
            source: 数据来源 (auto/internal/zabbix/prometheus)

        返回:
            Dict: 指标数据

        示例:
            >>> result = skill.collect_metrics()
            >>> print(result["data"]["metrics"]["connections_active"]["value"])
        """
        # 如果指定了外部监控源或没有数据库连接，尝试使用外部监控
        if source in ["zabbix", "prometheus"] or (not self.collector and source == "auto"):
            if self.zabbix_client and source in ["auto", "zabbix"]:
                return self._collect_from_zabbix(metric_types)
            elif self.prometheus_client and source in ["auto", "prometheus"]:
                return self._collect_from_prometheus(metric_types)

        if not self.collector:
            return create_error_response(
                "未提供数据库连接器",
                error_code=ErrorCode.CONNECTION_ERROR,
                details={"solution": "初始化时传入connector参数，或配置Zabbix/Prometheus环境变量"}
            )

        try:
            metrics = self.collector.collect_all_metrics()

            # 过滤指定指标
            if metric_types:
                metrics = [
                    m for m in metrics
                    if m.metric_type.value in metric_types
                ]

            # 保存到存储
            if self.storage:
                for metric in metrics:
                    self.storage.save_metric(metric)

            # 转换为字典
            metrics_dict = {
                m.metric_type.value: {
                    "value": m.value,
                    "unit": m.unit,
                    "timestamp": m.timestamp.isoformat(),
                    "source": m.source
                }
                for m in metrics
            }

            return create_success_response(
                message=f"成功采集 {len(metrics)} 个指标",
                data={
                    "timestamp": datetime.now().isoformat(),
                    "dialect": self.dialect,
                    "metrics": metrics_dict
                }
            )

        except Exception as e:
            logger.error(f"采集指标失败: {e}")
            return create_error_response(
                "采集指标失败",
                error_code=ErrorCode.COLLECTION_FAILED,
                details={"error": str(e)}
            )

    @validate_params(metric_type=Validator.not_empty_string)

    def get_metric_history(
        self,
        metric_type: str,
        hours: int = 24
    ) -> Dict[str, Any]:
        """
        获取指标历史数据

        参数:
            metric_type: 指标类型
            hours: 查询小时数

        返回:
            Dict: 历史数据
        """
        if not self.storage:
            return create_error_response(
                "未启用持久化存储",
                error_code=ErrorCode.STORAGE_ERROR
            )

        try:
            metric_enum = MetricType(metric_type)
            history = self.storage.get_metric_history(metric_enum, hours)

            return create_success_response(
                message=f"获取到 {len(history)} 个历史数据点",
                data={
                    "metric_type": metric_type,
                    "hours": hours,
                    "data_points": [m.to_dict() for m in history]
                }
            )
        except ValueError:
            return create_error_response(
                f"未知的指标类型: {metric_type}",
                error_code=ErrorCode.INVALID_METRIC_TYPE
            )
        except Exception as e:
            logger.error(f"获取历史数据失败: {e}")
            return create_error_response(
                "获取历史数据失败",
                error_code=ErrorCode.STORAGE_ERROR,
                details={"error": str(e)}
            )

    # ==================== 异常检测 ====================

    @validate_params()

    def _collect_from_zabbix(self, metric_types: Optional[List[str]] = None) -> Dict[str, Any]:
        """从 Zabbix 采集指标"""
        try:
            from dbskiter.shared.zabbix_client import ZabbixOracleMetrics
            from dbskiter.shared.oracle_metrics import OracleHostMapping

            host_name = self._get_host_name()
            if not host_name:
                return create_error_response(
                    "无法确定主机名",
                    error_code=ErrorCode.CONFIG_INVALID
                )

            all_hosts = self.zabbix_client.get_hosts()
            is_oracle_group = OracleHostMapping.is_oracle_group(host_name)

            if is_oracle_group:
                # Oracle 资产组查询
                zabbix_oracle = ZabbixOracleMetrics(self.zabbix_client)
                group_metrics = zabbix_oracle.get_group_metrics(host_name, all_hosts)

                if "error" in group_metrics:
                    return create_error_response(
                        f"获取指标失败: {group_metrics['error']}",
                        error_code=ErrorCode.NOT_FOUND
                    )

                aggregated = group_metrics.get("aggregated", {})

                # 构建指标字典
                metrics_dict = {}
                metric_mapping = {
                    "cpu": ("cpu_usage", "%", "CPU使用率"),
                    "memory": ("memory_usage", "%", "内存使用率"),
                    "disk_used_percent": ("disk_usage", "%", "磁盘使用率"),
                    "sessions": ("connections_active", "", "活跃连接数"),
                    "processes": ("processes", "", "进程数"),
                    "iops": ("iops", "", "IOPS"),
                    "tps": ("tps", "", "TPS"),
                    "qps": ("qps", "", "QPS"),
                }

                for key, (metric_id, unit, description) in metric_mapping.items():
                    value = aggregated.get(key)
                    if value is not None:
                        metrics_dict[metric_id] = {
                            "value": value,
                            "unit": unit,
                            "description": description,
                            "timestamp": datetime.now().isoformat(),
                            "source": "zabbix"
                        }

                return create_success_response(
                    message=f"成功从 Zabbix 采集 {len(metrics_dict)} 个指标",
                    data={
                        "timestamp": datetime.now().isoformat(),
                        "host": host_name,
                        "source": "zabbix",
                        "metrics": metrics_dict
                    }
                )
            else:
                # 普通主机查询
                return create_error_response(
                    "非资产组主机的 Zabbix 指标采集暂未实现",
                    error_code=ErrorCode.NOT_IMPLEMENTED
                )

        except Exception as e:
            logger.error(f"从 Zabbix 采集指标失败: {e}")
            return create_error_response(
                "从 Zabbix 采集指标失败",
                error_code=ErrorCode.COLLECTION_FAILED,
                details={"error": str(e)}
            )


    def _collect_from_prometheus(self, metric_types: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        从 Prometheus 采集指标
        
        参数:
            metric_types: 指定指标类型列表，None表示全部
        
        返回:
            Dict: 指标数据
        """
        if not self.prometheus_client:
            return create_error_response(
                "Prometheus 客户端未初始化",
                error_code=ErrorCode.CONNECTION_ERROR,
                details={"solution": "请设置 PROMETHEUS_URL 环境变量"}
            )
        
        try:
            from dbskiter.shared.prometheus_client import RDSMetrics
            
            host_name = self._get_host_name()
            if not host_name:
                return create_error_response(
                    "无法确定实例名",
                    error_code=ErrorCode.CONFIG_INVALID
                )
            
            rds_metrics = RDSMetrics(self.prometheus_client)
            
            # 获取指标数据
            metrics_data = rds_metrics.get_current_metrics(host_name)
            
            # 转换为标准格式
            metrics_dict = {}
            for metric_name, metric_info in metrics_data.get('metrics', {}).items():
                value = metric_info.get('value')
                if value is not None:
                    metrics_dict[metric_name] = {
                        "value": value,
                        "unit": metric_info.get('unit', ''),
                        "timestamp": datetime.now().isoformat(),
                        "source": "prometheus"
                    }
            
            return create_success_response(
                message=f"从 Prometheus 采集到 {len(metrics_dict)} 个指标",
                data={
                    "timestamp": datetime.now().isoformat(),
                    "instance": host_name,
                    "metrics": metrics_dict
                }
            )
        
        except Exception as e:
            logger.error(f"Prometheus 指标采集失败: {e}")
            return create_error_response(
                "Prometheus 指标采集失败",
                error_code=ErrorCode.COLLECTION_FAILED,
                details={"error": str(e)}
            )


