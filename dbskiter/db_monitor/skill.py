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
作者: Magiczc
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
    HealthStatus,
    MetricType,
    AnomalyAlert,
    MonitorConfig,
    HealthAssessment,
)
from dbskiter.shared.error_handler import create_success_response, create_error_response
from dbskiter.db_monitor.utils import AnomalyDetector, CapacityPredictor, AlertManager
from dbskiter.db_monitor.storage import MetricsStorage
from dbskiter.db_monitor.collectors import get_collector
from dbskiter.db_monitor.health_scorer import get_health_scorer

from dbskiter.db_monitor.mixins import (
    HealthMixin,
    MonitoringMixin,
    CollectionMixin,
    AnomalyMixin,
    CapacityMixin,
    TrendMixin,
    MonitorAIContextMixin,
    MonitorUtilsMixin,
)

# 导入高级预测器和趋势分析器（新增）
try:
    from dbskiter.db_monitor.advanced_predictor import AdvancedCapacityPredictor
    from dbskiter.db_monitor.trend_analyzer import (
        TrendAnalyzer,
        StorageBasedDataProvider,
    )

    ADVANCED_FEATURES_AVAILABLE = True
except ImportError as e:
    logger.warning(f"高级功能不可用: {e}")
    ADVANCED_FEATURES_AVAILABLE = False

logger = logging.getLogger(__name__)


class MonitorSkill(
    HealthMixin,
    MonitoringMixin,
    CollectionMixin,
    AnomalyMixin,
    CapacityMixin,
    TrendMixin,
    MonitorAIContextMixin,
    MonitorUtilsMixin,
):
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
        host_name: Optional[Union[str, List[str]]] = None,
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
