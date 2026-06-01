"""
db_monitor Skill - 统一入口（模块化重构版）
数据库监控模块 - 多数据源采集与智能异常检测

快速开始:
    from dbskiter.db_monitor import MonitorSkill

    # 初始化
    skill = MonitorSkill(connector)

    # 采集指标
    metrics = skill.collect_metrics()

    # 异常检测
    anomalies = skill.detect_anomalies()

    # 健康评估
    health = skill.assess_health()

    # 容量预测
    prediction = skill.predict_capacity("disk_usage", days=30)

    # 启动实时监控
    skill.start_monitoring(callback=on_alert)

模块结构:
    - models.py - 数据模型和枚举（ErrorCode, MetricPoint, AnomalyAlert等）
    - utils.py - 工具类（AnomalyDetector, CapacityPredictor, AlertManager）
    - storage.py - 数据持久化存储（MetricsStorage）
    - skill.py - 统一入口（MonitorSkill）
    - collectors/ - 多数据库指标采集器

核心功能:
- 多数据库指标采集 - MySQL/Oracle/PostgreSQL
- 智能异常检测 - Z-score/IQR/阈值检测
- 容量预测 - 趋势预测，容量规划
- 健康评估 - 综合健康评分
- 实时监控 - 持续监控与告警
- 持久化存储 - SQLite存储历史数据

版本: 3.0.0（模块化重构版）
"""

# 数据模型
from .models import (
    ErrorCode,
    ErrorMessage,
    HealthStatus,
    AnomalyType,
    Severity,
    MetricType,
    MetricPoint,
    AnomalyAlert,
    MonitorConfig,
    HealthAssessment,
    CapacityPrediction,)

# 响应函数（从shared模块导入）
from dbskiter.shared.error_handler import create_success_response, create_error_response

# 工具类
from .utils import (
    AnomalyDetector,
    CapacityPredictor,
    AlertManager,
)

# 存储
from .storage import MetricsStorage

# 采集器
from .collectors import (
    BaseMetricsCollector,
    MySQLMetricsCollector,
    OracleMetricsCollector,
    PostgreSQLMetricsCollector,
    get_collector,
    MetricType as CollectorMetricType,
)

# 主Skill类
from .skill import MonitorSkill

__all__ = [
    # 数据模型
    "ErrorCode",
    "ErrorMessage",
    "HealthStatus",
    "AnomalyType",
    "Severity",
    "MetricType",
    "MetricPoint",
    "AnomalyAlert",
    "MonitorConfig",
    "HealthAssessment",
    "CapacityPrediction",
    "create_success_response",
    "create_error_response",
    # 工具类
    "AnomalyDetector",
    "CapacityPredictor",
    "AlertManager",
    # 存储
    "MetricsStorage",
    # 采集器
    "BaseMetricsCollector",
    "MySQLMetricsCollector",
    "OracleMetricsCollector",
    "PostgreSQLMetricsCollector",
    "get_collector",
    # 主Skill类
    "MonitorSkill",
]

__version__ = "3.0.0"
