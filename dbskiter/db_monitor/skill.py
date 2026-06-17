"""
db_monitor/skill.py
数据库监控 Skill - 统一入口（模块化重构版）

文件功能：
    - 整合所有子模块功能
    - 提供统一的监控API
    - 与db-scheduler保持一致的架构风格

整合模块:
    - models.py - 数据模型和枚举
    - utils.py - 工具类(AnomalyDetector, CapacityPredictor等)
    - storage.py - 数据持久化存储
    - collectors/ - 多数据库指标采集器

使用示例:
    >>> from dbskiter.db_monitor import MonitorSkill
    >>> skill = MonitorSkill(connector)
    >>> result = skill.collect_metrics()
    >>> anomalies = skill.detect_anomalies()
    >>> health = skill.assess_health()

版本: 3.0.0（模块化重构版）
作者: AI Assistant
创建时间: 2026-04-23
"""

import logging
import threading
import time
from typing import Dict, Any, List, Optional, Callable, Union
from datetime import datetime

from dbskiter.shared.unified_connector import UnifiedConnector
from dbskiter.shared.validators import validate_params, Validator

# 导入外部监控系统客户端（可选）
try:
    from dbskiter.shared.prometheus_client import PrometheusClient, RDSMetrics
    from dbskiter.shared.zabbix_client import ZabbixClient, ZabbixMySQLMetrics
    EXTERNAL_MONITORING_AVAILABLE = True
except ImportError:
    EXTERNAL_MONITORING_AVAILABLE = False

# 导入子模块
from dbskiter.db_monitor.models import (
    ErrorCode,
    HealthStatus, MetricType,
    AnomalyAlert, MonitorConfig, HealthAssessment,
)
from dbskiter.shared.error_handler import create_success_response, create_error_response
from dbskiter.db_monitor.utils import (
    AnomalyDetector, CapacityPredictor, AlertManager
)
from dbskiter.db_monitor.storage import MetricsStorage
from dbskiter.db_monitor.collectors import get_collector
from dbskiter.db_monitor.health_scorer import get_health_scorer

# 导入高级预测器和趋势分析器（新增）
try:
    from dbskiter.db_monitor.advanced_predictor import AdvancedCapacityPredictor
    from dbskiter.db_monitor.trend_analyzer import (
        TrendAnalyzer, StorageBasedDataProvider,
    )
    ADVANCED_FEATURES_AVAILABLE = True
except ImportError as e:
    logger.warning(f"高级功能不可用: {e}")
    ADVANCED_FEATURES_AVAILABLE = False

logger = logging.getLogger(__name__)


class MonitorSkill:
    """
    数据库监控 Skill - 统一入口（模块化重构版）

    整合所有子模块功能：
    - 指标采集（collectors/）
    - 异常检测（utils.py）
    - 容量预测（utils.py）
    - 数据存储（storage.py）

    使用示例:
        >>> skill = MonitorSkill(connector)
        >>> result = skill.collect_metrics()
        >>> anomalies = skill.detect_anomalies()
        >>> health = skill.assess_health()
        >>> skill.start_monitoring(callback=on_alert)
    """

    def __init__(
        self,
        connector: Optional[UnifiedConnector] = None,
        config: Optional[MonitorConfig] = None,
        host_name: Optional[Union[str, List[str]]] = None
    ):
        """
        初始化监控 Skill

        参数:
            connector: 数据库连接器（用于直接采集）
            config: 监控配置
            host_name: 外部监控查询用的主机名（可以是字符串或列表）
        """
        self.connector = connector
        self.config = config or MonitorConfig()
        self.dialect = connector.dialect.lower() if connector else None
        self._host_name = host_name  # 外部监控查询用的主机名（支持列表）

        # 初始化采集器
        self.collector = None
        if connector:
            self.collector = get_collector(self.dialect, connector)

        # 初始化工具组件
        self.detector = AnomalyDetector(threshold=self.config.anomaly_threshold)
        self.predictor = CapacityPredictor()
        self.alert_manager = AlertManager(cooldown=self.config.alert_cooldown)
        self.storage: Optional[MetricsStorage] = None

        if self.config.enable_persistent_storage:
            self.storage = MetricsStorage(self.config.storage_path)

        # 初始化高级预测器和趋势分析器（新增）
        self.advanced_predictor: Optional[AdvancedCapacityPredictor] = None
        self.trend_analyzer: Optional[TrendAnalyzer] = None

        if ADVANCED_FEATURES_AVAILABLE:
            self.advanced_predictor = AdvancedCapacityPredictor()
            if self.storage:
                provider = StorageBasedDataProvider(self.storage)
                self.trend_analyzer = TrendAnalyzer(provider)

        # 监控状态
        self._monitoring_thread: Optional[threading.Thread] = None
        self._is_monitoring = False
        self._alert_handlers: List[Callable[[AnomalyAlert], None]] = []

        # 初始化外部监控系统客户端
        self.prometheus_client: Optional[PrometheusClient] = None
        self.zabbix_client: Optional[ZabbixClient] = None

        if EXTERNAL_MONITORING_AVAILABLE:
            self._init_external_monitoring()

        logger.info(f"MonitorSkill 初始化完成 (dialect={self.dialect}, host={self._host_name})")

    def _init_external_monitoring(self):
        """初始化外部监控系统客户端"""
        import os

        # 初始化 Prometheus 客户端
        prometheus_url = os.getenv("PROMETHEUS_URL")
        if prometheus_url:
            try:
                self.prometheus_client = PrometheusClient(prometheus_url)
                logger.info(f"Prometheus 客户端初始化成功: {prometheus_url}")
            except Exception as e:
                logger.warning(f"Prometheus 客户端初始化失败: {e}")

        # 初始化 Zabbix 客户端
        zabbix_url = os.getenv("ZABBIX_URL")
        zabbix_user = os.getenv("ZABBIX_USER")
        zabbix_password = os.getenv("ZABBIX_PASSWORD")

        if zabbix_url and zabbix_user and zabbix_password:
            try:
                self.zabbix_client = ZabbixClient(zabbix_url)
                if self.zabbix_client.login(zabbix_user, zabbix_password):
                    logger.info(f"Zabbix 客户端初始化成功: {zabbix_url}")
                else:
                    logger.warning("Zabbix 登录失败")
                    self.zabbix_client = None
            except Exception as e:
                logger.warning(f"Zabbix 客户端初始化失败: {e}")

    # ==================== 指标采集 ====================

    @validate_params()
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

    def _get_instance_name(self) -> Optional[str]:
        """获取 Prometheus 实例名"""
        import os
        # 优先从环境变量获取
        instance = os.getenv("PROMETHEUS_INSTANCE_NAME")
        if instance:
            return instance
        # 尝试从数据库连接信息推断
        if self.connector:
            # 使用主机名或IP作为实例名
            host = getattr(self.connector, 'host', None)
            if host:
                return f"rds-{host.replace('.', '-')}"
        return None

    def _get_host_name(self) -> Optional[str]:
        """
        获取 Zabbix/Prometheus 主机名

        支持 host_name 列表，返回第一个有效的主机名
        """
        import os
        from typing import List

        # 1. 优先使用传入的 host_name（CLI --database 参数）
        if self._host_name:
            # 如果是列表，尝试每个主机名，返回第一个存在的
            if isinstance(self._host_name, list):
                return self._find_first_valid_host(self._host_name)
            return self._host_name

        # 2. 从环境变量获取
        host = os.getenv("ZABBIX_HOST_NAME") or os.getenv("PROMETHEUS_INSTANCE_NAME")
        if host:
            return host

        # 3. 尝试从数据库连接信息推断
        if self.connector:
            # 获取数据库名（如 z18）
            db_name = getattr(self.connector, 'database', None)
            if db_name:
                # Z系列数据库直接使用 Z 名称
                # 例如：z18 -> Z18（数据库服务器 Z18-160）
                if db_name.lower().startswith('z'):
                    return db_name.upper()
                return db_name
            # 回退到使用主机名
            host = getattr(self.connector, 'host', None)
            if host:
                return host
        return None

    def _find_first_valid_host(self, host_names: List[str]) -> Optional[str]:
        """
        从 host_name 列表中找到第一个有效的主机

        支持前缀匹配（如 "Z18-" 匹配 "Z18-80", "Z18-160"）

        参数:
            host_names: 主机名列表（可以是完整主机名或前缀）

        返回:
            第一个存在的主机名，或 None
        """
        if not self.zabbix_client:
            # 如果没有 Zabbix 客户端，返回第一个
            return host_names[0] if host_names else None

        try:
            # 获取所有主机
            all_hosts = self.zabbix_client.get_hosts()
            host_name_set = {h['host'] for h in all_hosts}

            # 找到第一个存在的主机（支持前缀匹配）
            for pattern in host_names:
                # 如果是前缀（以 - 或 _ 结尾），进行前缀匹配
                if pattern.endswith('-') or pattern.endswith('_'):
                    for host_name in host_name_set:
                        if host_name.startswith(pattern):
                            logger.info(f"找到有效主机: {host_name} (匹配前缀 {pattern})")
                            return host_name
                else:
                    # 完整匹配
                    if pattern in host_name_set:
                        logger.info(f"找到有效主机: {pattern}")
                        return pattern

            logger.warning(f"列表中所有主机都不存在: {host_names}")
            return host_names[0] if host_names else None  # 返回第一个，让后续报错
        except Exception as e:
            logger.warning(f"查找主机失败: {e}")
            return host_names[0] if host_names else None

    # ==================== 健康评估 ====================

    @validate_params()
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

    def start_monitoring(
        self,
        callback: Optional[Callable[[AnomalyAlert], None]] = None,
        interval: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        启动实时监控

        参数:
            callback: 异常告警回调函数
            interval: 采集间隔（秒），默认使用配置值

        返回:
            Dict: 启动结果
        """
        if self._is_monitoring:
            return create_error_response(
                "监控已在运行中",
                error_code=ErrorCode.ALREADY_EXISTS
            )

        if not self.collector:
            return create_error_response(
                "未提供数据库连接器",
                error_code=ErrorCode.CONNECTION_ERROR
            )

        # 添加回调
        if callback:
            self._alert_handlers.append(callback)

        self._is_monitoring = True
        interval = interval or self.config.collection_interval

        def monitoring_loop():
            """监控循环"""
            while self._is_monitoring:
                try:
                    # 采集指标
                    metrics = self.collector.collect_all_metrics()

                    # 保存到存储
                    if self.storage:
                        for metric in metrics:
                            self.storage.save_metric(metric)

                    # 检测异常
                    for metric in metrics:
                        alert = self.detector.detect(metric)
                        if alert and self.alert_manager.should_alert(alert.alert_id):
                            # 保存告警
                            if self.storage:
                                self.storage.save_alert(alert)

                            # 触发回调
                            for handler in self._alert_handlers:
                                try:
                                    handler(alert)
                                except Exception as e:
                                    logger.error(f"告警处理器执行失败: {e}")

                except Exception as e:
                    logger.error(f"监控循环执行失败: {e}")

                # 等待下一次采集
                time.sleep(interval)

        # 启动监控线程
        self._monitoring_thread = threading.Thread(
            target=monitoring_loop,
            name="MonitorThread",
            daemon=True
        )
        self._monitoring_thread.start()

        logger.info(f"实时监控已启动，间隔: {interval}秒")

        return create_success_response(
            message="实时监控已启动",
            data={
                "interval": interval,
                "storage_enabled": self.storage is not None,
                "dialect": self.dialect
            }
        )

    def stop_monitoring(self) -> Dict[str, Any]:
        """
        停止实时监控

        返回:
            Dict: 停止结果
        """
        if not self._is_monitoring:
            return create_error_response(
                "监控未在运行",
                error_code=ErrorCode.NOT_FOUND
            )

        self._is_monitoring = False

        if self._monitoring_thread:
            self._monitoring_thread.join(timeout=5)
            self._monitoring_thread = None

        logger.info("实时监控已停止")
        return create_success_response(message="实时监控已停止")

    def add_alert_handler(self, handler: Callable[[AnomalyAlert], None]):
        """添加告警处理器"""
        self._alert_handlers.append(handler)

    # ==================== 告警管理 ====================

    @validate_params()
    def get_alerts(
        self,
        hours: int = 24,
        acknowledged: Optional[bool] = None
    ) -> Dict[str, Any]:
        """
        获取告警历史

        参数:
            hours: 查询小时数
            acknowledged: 是否已确认

        返回:
            Dict: 告警列表
        """
        if not self.storage:
            return create_error_response(
                "未启用持久化存储",
                error_code=ErrorCode.STORAGE_ERROR
            )

        try:
            alerts = self.storage.get_alerts(hours, acknowledged)

            return create_success_response(
                message=f"获取到 {len(alerts)} 条告警",
                data={"alerts": alerts}
            )
        except Exception as e:
            logger.error(f"获取告警失败: {e}")
            return create_error_response(
                "获取告警失败",
                error_code=ErrorCode.STORAGE_ERROR,
                details={"error": str(e)}
            )

    def acknowledge_alert(self, alert_id: str) -> Dict[str, Any]:
        """确认告警"""
        if not self.storage:
            return create_error_response(
                "未启用持久化存储",
                error_code=ErrorCode.STORAGE_ERROR
            )
        return self.storage.acknowledge_alert(alert_id)

    def get_storage_stats(self) -> Dict[str, Any]:
        """获取存储统计"""
        if not self.storage:
            return create_error_response(
                "未启用持久化存储",
                error_code=ErrorCode.STORAGE_ERROR
            )
        return create_success_response(
            message="获取存储统计成功",
            data=self.storage.get_statistics()
        )

    def cleanup_storage(self, days: int = 30) -> Dict[str, Any]:
        """清理过期数据"""
        if not self.storage:
            return create_error_response(
                "未启用持久化存储",
                error_code=ErrorCode.STORAGE_ERROR
            )
        return self.storage.cleanup_old_data(days)

    # ==================== 资源释放 ====================

    def close(self):
        """关闭Skill，释放资源"""
        logger.info("关闭 MonitorSkill...")

        # 停止监控线程
        if self._is_monitoring:
            self._is_monitoring = False
            if self._monitoring_thread:
                self._monitoring_thread.join(timeout=5)
                self._monitoring_thread = None
            logger.info("监控线程已停止")

        # 关闭存储
        if self.storage:
            self.storage.close()
            logger.info("存储已关闭")

        # 清理告警处理器
        self._alert_handlers.clear()
        self.alert_manager.reset()

        logger.info("MonitorSkill 已关闭")


    # ==================== 高级功能（新增）====================

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


