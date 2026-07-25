"""
capacity mixin for MonitorSkill

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


class CapacityMixin:
    """capacity for MonitorSkill"""

    def predict_capacity(
        self,
        metric: str,
        days: int = 30,
        source: str = "auto"
    ) -> Dict[str, Any]:
        """
        预测容量趋势

        参数:
            metric: 指标名称（cpu/memory/disk/connections等）
            days: 预测天数
            source: 数据来源（auto/prometheus/zabbix/internal）

        返回:
            Dict: 预测结果
        """
        # 资源名称到 MetricType 的映射
        resource_to_metric = {
            "disk": "disk_usage",
            "memory": "memory_usage",
            "cpu": "cpu_usage",
            "connections": "connections_active",
        }
        # 转换资源名称为指标名称
        metric_name = resource_to_metric.get(metric, metric)

        # 尝试从外部监控系统获取数据
        if source in ("auto", "prometheus") and self.prometheus_client:
            result = self._predict_from_prometheus(metric_name, days)
            # 如果 Prometheus 成功，直接返回；否则回退到 internal
            if result.get('success'):
                return result
            # 仅在debug模式下记录详细信息
            logger.debug(f"Prometheus 预测不可用，使用 internal: {result.get('message')}")

        if source in ("auto", "zabbix") and self.zabbix_client:
            result = self._predict_from_zabbix(metric_name, days)
            # 如果 Zabbix 成功，直接返回；否则回退到 internal
            if result.get('success'):
                return result
            # 仅在debug模式下记录详细信息
            logger.debug(f"Zabbix 预测不可用，使用 internal: {result.get('message')}")

        # 使用内部存储的数据（或直接从数据库采集）
        return self._predict_from_internal(metric_name, days)


    def predict_capacity_advanced(
        self,
        metric: str,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        使用高级算法进行容量预测

        参数:
            metric: 指标名称
            days: 预测天数

        返回:
            Dict: 预测结果（包含算法选择、置信度等）
        """
        if not ADVANCED_FEATURES_AVAILABLE:
            return create_error_response(
                "高级预测功能不可用（缺少numpy依赖）",
                error_code=ErrorCode.NOT_IMPLEMENTED,
                details={"solution": "安装numpy: pip install numpy"}
            )

        if not self.storage:
            return create_error_response(
                "高级预测需要启用持久化存储",
                error_code=ErrorCode.STORAGE_ERROR
            )

        try:
            # 资源名称到 MetricType 的映射
            resource_to_metric = {
                "disk": "disk_usage",
                "memory": "memory_usage",
                "cpu": "cpu_usage",
                "connections": "connections_active",
                "qps": "qps",
            }
            # 转换资源名称为指标名称
            metric_name = resource_to_metric.get(metric, metric)

            # 获取历史数据
            metric_enum = MetricType(metric_name)
            history = self.storage.get_metric_history(metric_enum, hours=24*30)

            if len(history) < 3:
                return create_error_response(
                    "历史数据不足",
                    error_code=ErrorCode.INSUFFICIENT_HISTORY,
                    details={"current_points": len(history), "required": 3}
                )

            # 准备数据
            historical_data = [(m.timestamp, m.value) for m in history]

            # 使用高级预测器
            result = self.advanced_predictor.predict(metric, historical_data, days)

            return create_success_response(
                message=f"高级容量预测完成（使用算法: {result.algorithm}）",
                data={
                    "metric": result.metric,
                    "algorithm": result.algorithm,
                    "current_value": result.current_value,
                    "predictions": result.predictions,
                    "confidence": round(result.confidence, 2),
                    "growth_rate": round(result.growth_rate, 4),
                    "trend_direction": result.trend_direction,
                    "days_to_threshold": result.days_to_threshold,
                    "threshold": result.threshold,
                    "recommendation": result.recommendation,
                    "urgency": result.urgency
                }
            )

        except ValueError:
            return create_error_response(
                f"未知的指标类型: {metric}",
                error_code=ErrorCode.INVALID_METRIC_TYPE
            )
        except Exception as e:
            logger.error(f"高级容量预测失败: {e}")
            return create_error_response(
                "高级容量预测失败",
                error_code=ErrorCode.PREDICTION_FAILED,
                details={"error": str(e)}
            )


    def _predict_from_prometheus(self, metric: str, days: int) -> Dict[str, Any]:
        """从 Prometheus 获取数据进行容量预测"""
        try:
            from dbskiter.shared.prometheus_metrics import MySQLRDSMetrics

            # 获取实例名（从配置或连接器）
            instance_name = self._get_instance_name()
            if not instance_name:
                return create_error_response(
                    "无法确定实例名",
                    error_code=ErrorCode.CONFIG_INVALID,
                    details={"solution": "请配置 PROMETHEUS_INSTANCE_NAME 环境变量"}
                )

            # 获取指标历史数据
            rds_metrics = RDSMetrics(self.prometheus_client)
            history = rds_metrics.get_metric_history(instance_name, metric, hours=24*7)

            if len(history) < 3:
                return create_error_response(
                    "Prometheus 历史数据不足",
                    error_code=ErrorCode.INSUFFICIENT_HISTORY,
                    details={"current_points": len(history), "required": 3}
                )

            # 准备数据并预测
            historical_data = [
                (datetime.fromisoformat(h["timestamp"]), h["value"])
                for h in history
            ]
            prediction = self.predictor.predict(metric, historical_data, days)

            return create_success_response(
                message="容量预测完成（数据来源：Prometheus）",
                data=prediction.to_dict()
            )

        except Exception as e:
            logger.error(f"Prometheus 容量预测失败: {e}")
            return create_error_response(
                "Prometheus 容量预测失败",
                error_code=ErrorCode.PREDICTION_FAILED,
                details={"error": str(e)}
            )


    def _predict_from_zabbix(self, metric: str, days: int) -> Dict[str, Any]:
        """从 Zabbix 获取数据进行容量预测"""
        try:
            from dbskiter.shared.zabbix_client import ZabbixOracleMetrics

            # 获取主机名
            host_name = self._get_host_name()
            if not host_name:
                return create_error_response(
                    "无法确定主机名",
                    error_code=ErrorCode.CONFIG_INVALID,
                    details={"solution": "请配置 ZABBIX_HOST_NAME 环境变量"}
                )

            # 判断是否为 Oracle 资产组（如 Z18, Z5 等）
            from dbskiter.shared.oracle_metrics import OracleHostMapping
            is_oracle_group = OracleHostMapping.is_oracle_group(host_name)

            # 获取对应监控项的 key
            # 支持两种 metric 名称格式：简写（disk）和完整（disk_usage）
            metric_key_map = {
                "disk": "vfs.fs.size",
                "disk_usage": "vfs.fs.size",
                "memory": "vm.memory.size",
                "memory_usage": "vm.memory.size",
                "cpu": "system.cpu.util",
                "cpu_usage": "system.cpu.util"
            }
            key_search = metric_key_map.get(metric, metric)

            if is_oracle_group:
                # Oracle 资产组查询 - 获取所有主机的历史数据
                all_hosts = self.zabbix_client.get_hosts()
                group_hosts = OracleHostMapping.get_group_hosts(host_name)

                # 找到匹配的主机
                matching_hosts = []
                for host in all_hosts:
                    host_host = host.get("host", "")
                    for pattern in group_hosts:
                        if pattern in host_host:
                            matching_hosts.append(host)
                            break

                if not matching_hosts:
                    return create_error_response(
                        f"在 Zabbix 中未找到资产组主机: {host_name}",
                        error_code=ErrorCode.NOT_FOUND
                    )

                # 获取所有主机的历史数据
                all_history = []
                for host in matching_hosts:
                    items = self.zabbix_client.get_items(host["hostid"], key_search)
                    if items:
                        # 优先使用百分比指标（pused）
                        # 内存: vm.memory.size[pused]
                        # 磁盘: vfs.fs.size[/path,pused]
                        pused_items = [item for item in items if "pused" in item.get("key_", "")]
                        if pused_items:
                            item_id = pused_items[0]["itemid"]
                            logger.debug(f"使用 pused 指标: {pused_items[0].get('name')} ({pused_items[0].get('key_')})")
                        else:
                            item_id = items[0]["itemid"]
                            logger.debug(f"使用第一个指标: {items[0].get('name')} ({items[0].get('key_')})")

                        history = self.zabbix_client.get_history(item_id, hours=24*7, limit=1000)
                        logger.debug(f"主机 {host.get('host')} 获取到 {len(history)} 条历史数据")
                        all_history.extend(history)

                if len(all_history) < 3:
                    return create_error_response(
                        "Zabbix 历史数据不足",
                        error_code=ErrorCode.INSUFFICIENT_HISTORY,
                        details={"current_points": len(all_history), "required": 3}
                    )

                # 按时间聚合数据（取最大值）
                from collections import defaultdict
                time_values = defaultdict(list)
                for h in all_history:
                    ts = h.get("timestamp", "")
                    value = h.get("value", 0)
                    if ts:
                        # 按小时聚合
                        hour_key = ts[:13]  # 精确到小时
                        time_values[hour_key].append(value)

                # 计算每小时的平均值
                aggregated_history = []
                for hour_key, values in sorted(time_values.items()):
                    avg_value = sum(values) / len(values)
                    # 构造时间戳
                    ts = f"{hour_key}:00:00"
                    aggregated_history.append((datetime.fromisoformat(ts), avg_value))

                # 获取当前值
                zabbix_oracle = ZabbixOracleMetrics(self.zabbix_client)
                group_metrics = zabbix_oracle.get_group_metrics(host_name, all_hosts)
                aggregated = group_metrics.get("aggregated", {})
                metric_map = {"disk": "disk_used_percent", "memory": "memory", "cpu": "cpu"}
                metric_key = metric_map.get(metric, metric)
                current_value = aggregated.get(metric_key, 0)

                # 执行预测
                if len(aggregated_history) >= 3:
                    prediction = self.predictor.predict(metric, aggregated_history, days)
                    prediction_data = prediction.to_dict()
                    prediction_data["current_usage"] = current_value
                    return create_success_response(
                        message="容量预测完成（数据来源：Zabbix Oracle资产组）",
                        data=prediction_data
                    )
                else:
                    return create_success_response(
                        message="容量查询完成（数据来源：Zabbix Oracle资产组，历史数据不足无法预测）",
                        data={
                            "current_usage": current_value,
                            "predicted_usage": current_value,
                            "threshold": 80,
                            "days_to_threshold": 999,
                            "risk_level": "unknown",
                            "recommendation": f"{host_name} 资产组当前{metric}使用率: {current_value}%（历史数据不足，无法预测趋势）"
                        }
                    )

            else:
                # 普通 MySQL 主机查询
                zabbix_mysql = ZabbixMySQLMetrics(self.zabbix_client)
                host = zabbix_mysql.find_host_by_name(host_name)
                if not host:
                    return create_error_response(
                        f"在 Zabbix 中未找到主机: {host_name}",
                        error_code=ErrorCode.NOT_FOUND
                    )

                items = self.zabbix_client.get_items(host["hostid"], key_search)
                if not items:
                    return create_error_response(
                        f"未找到指标: {metric}",
                        error_code=ErrorCode.NOT_FOUND
                    )

                # 获取历史数据
                item_id = items[0]["itemid"]
                history = self.zabbix_client.get_history(item_id, hours=24*7, limit=1000)

                if len(history) < 3:
                    return create_error_response(
                        "Zabbix 历史数据不足",
                        error_code=ErrorCode.INSUFFICIENT_HISTORY,
                        details={"current_points": len(history), "required": 3}
                    )

                # 准备数据并预测
                historical_data = [
                    (datetime.fromisoformat(h["timestamp"]), h["value"])
                    for h in history
                ]
                prediction = self.predictor.predict(metric, historical_data, days)

                return create_success_response(
                    message="容量预测完成（数据来源：Zabbix）",
                    data=prediction.to_dict()
                )

        except Exception as e:
            logger.error(f"Zabbix 容量预测失败: {e}")
            return create_error_response(
                "Zabbix 容量预测失败",
                error_code=ErrorCode.PREDICTION_FAILED,
                details={"error": str(e)}
            )


    def _predict_from_internal(self, metric: str, days: int) -> Dict[str, Any]:
        """
        从内部存储获取数据进行容量预测，如果没有存储则直接采集当前值

        逻辑：
            1. 优先从历史存储获取数据
            2. 如果没有历史数据，直接采集当前值
            3. 返回当前值和预测结果（如果有足够历史数据）
        """
        try:
            # 获取历史数据
            historical_data = []
            if self.storage:
                try:
                    metric_enum = MetricType(metric)
                    history = self.storage.get_metric_history(metric_enum, hours=24*7)
                    historical_data = [(m.timestamp, m.value) for m in history]
                except (ValueError, Exception) as e:
                    logger.warning(f"从存储获取历史数据失败: {e}")

            # 尝试采集当前值
            current_value = None
            if self.collector:
                try:
                    metric_enum = MetricType(metric)
                    metric_point = self.collector.collect_metric(metric_enum)
                    if metric_point:
                        current_value = metric_point.value
                        # 将当前值加入历史数据
                        historical_data.append((metric_point.timestamp, metric_point.value))
                except Exception as e:
                    logger.warning(f"直接采集指标失败: {e}")

            # 如果有足够历史数据，执行预测
            if len(historical_data) >= 3:
                prediction = self.predictor.predict(metric, historical_data, days)
                return create_success_response(
                    message="容量预测完成（数据来源：内部存储）",
                    data=prediction.to_dict()
                )

            # 如果没有足够历史数据，但采集到了当前值，返回当前值
            if current_value is not None:
                from dbskiter.db_monitor.models import CapacityPrediction
                prediction = CapacityPrediction(
                    metric=metric,
                    current_value=current_value,
                    current_time=datetime.now(),
                    predictions={
                        "current": current_value,
                        "7d": current_value,
                        "30d": current_value
                    },
                    days_to_threshold=999,
                    threshold=self.predictor.thresholds.get(metric, 90.0),
                    growth_rate_daily=0.0,
                    trend_direction="unknown",
                    confidence=0.0,
                    recommendation=f"当前{metric}使用率: {current_value:.2f}%（历史数据不足，无法预测趋势）",
                    urgency="low",
                    predictable=False
                )
                return create_success_response(
                    message="容量查询完成（仅当前值，无历史趋势）",
                    data=prediction.to_dict()
                )

            # 没有任何数据
            return create_error_response(
                "无法进行容量预测：没有历史数据且无法采集当前指标",
                error_code=ErrorCode.INSUFFICIENT_DATA,
                details={
                    "solution": "1. 启用持久化存储\n"
                               "2. 配置 Prometheus/Zabbix 外部监控\n"
                               "3. 确保数据库连接正常"
                }
            )

        except Exception as e:
            logger.error(f"容量预测失败: {e}")
            return create_error_response(
                "容量预测失败",
                error_code=ErrorCode.PREDICTION_FAILED,
                details={"error": str(e)}
            )


