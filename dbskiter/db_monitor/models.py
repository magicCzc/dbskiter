"""
db_monitor/models.py
数据模型定义模块

文件功能：
    - 定义监控模块所有数据模型和枚举
    - 提供统一的数据结构
    - 与db-scheduler保持一致的代码风格

主要类：
    - ErrorCode/ErrorMessage: 错误码体系
    - HealthStatus/AnomalyType/Severity: 状态枚举
    - MetricPoint: 指标数据点
    - AnomalyAlert: 异常告警
    - MonitorConfig: 监控配置
    - HealthAssessment: 健康评估结果

版本: 3.0.0
作者: AI Assistant
创建时间: 2026-04-23
"""

from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Any, List, Optional
import json

# 从shared模块导入标准响应函数
from dbskiter.shared.error_handler import create_success_response, create_error_response


# =============================================================================
# 错误码体系
# =============================================================================

class ErrorCode:
    """
    错误码体系

    格式: MONXXXYYY
    - MON: Monitor模块标识
    - XXX: 功能代码
    - YYY: 具体错误
    """

    # 通用错误 (000)
    SUCCESS = "MON000000"
    UNKNOWN_ERROR = "MON000001"
    INVALID_PARAM = "MON000002"
    NOT_FOUND = "MON000003"
    ALREADY_EXISTS = "MON000004"

    # 采集错误 (100)
    COLLECTION_FAILED = "MON100001"
    COLLECTION_TIMEOUT = "MON100002"
    CONNECTION_ERROR = "MON100003"
    PERMISSION_DENIED = "MON100004"

    # 检测错误 (200)
    DETECTION_FAILED = "MON200001"
    INSUFFICIENT_DATA = "MON200002"
    INVALID_METRIC_TYPE = "MON200003"

    # 存储错误 (300)
    STORAGE_ERROR = "MON300001"
    STORAGE_FULL = "MON300002"
    STORAGE_CORRUPTED = "MON300003"

    # 预测错误 (400)
    PREDICTION_FAILED = "MON400001"
    INSUFFICIENT_HISTORY = "MON400002"

    # 配置错误 (500)
    CONFIG_INVALID = "MON500001"
    CONFIG_MISSING = "MON500002"


class ErrorMessage:
    """错误消息映射"""

    MESSAGES = {
        ErrorCode.SUCCESS: "操作成功",
        ErrorCode.UNKNOWN_ERROR: "未知错误",
        ErrorCode.INVALID_PARAM: "参数无效",
        ErrorCode.NOT_FOUND: "资源不存在",
        ErrorCode.ALREADY_EXISTS: "资源已存在",
        ErrorCode.COLLECTION_FAILED: "指标采集失败",
        ErrorCode.COLLECTION_TIMEOUT: "采集超时",
        ErrorCode.CONNECTION_ERROR: "数据库连接错误",
        ErrorCode.PERMISSION_DENIED: "权限不足",
        ErrorCode.DETECTION_FAILED: "异常检测失败",
        ErrorCode.INSUFFICIENT_DATA: "数据不足",
        ErrorCode.INVALID_METRIC_TYPE: "无效的指标类型",
        ErrorCode.STORAGE_ERROR: "存储错误",
        ErrorCode.STORAGE_FULL: "存储空间已满",
        ErrorCode.STORAGE_CORRUPTED: "存储数据损坏",
        ErrorCode.PREDICTION_FAILED: "容量预测失败",
        ErrorCode.INSUFFICIENT_HISTORY: "历史数据不足",
    }

    @classmethod
    def get_message(cls, code: str) -> str:
        """获取错误消息"""
        return cls.MESSAGES.get(code, f"未知错误码: {code}")


# =============================================================================
# 枚举定义
# =============================================================================

class HealthStatus(str, Enum):
    """健康状态枚举"""
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


class AnomalyType(str, Enum):
    """异常类型枚举"""
    SPIKE = "spike"           # 突增
    DROP = "drop"             # 突降
    TREND_UP = "trend_up"     # 上升趋势
    TREND_DOWN = "trend_down" # 下降趋势
    SEASONAL = "seasonal"     # 季节性异常
    THRESHOLD = "threshold"   # 阈值超限
    ML_ANOMALY = "ml_anomaly" # 机器学习检测异常


class Severity(str, Enum):
    """严重级别枚举"""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class MetricType(str, Enum):
    """指标类型枚举"""
    # 吞吐量指标
    QPS = "qps"
    TPS = "tps"
    COM_SELECT = "com_select"
    COM_INSERT = "com_insert"
    COM_UPDATE = "com_update"
    COM_DELETE = "com_delete"

    # 连接指标
    CONNECTIONS_ACTIVE = "connections_active"
    CONNECTIONS_TOTAL = "connections_total"
    CONNECTIONS_MAX = "connections_max"
    CONNECTIONS_ABORTED = "connections_aborted"

    # 查询性能指标
    SLOW_QUERIES = "slow_queries"
    QUERY_TIME_AVG = "query_time_avg"
    QUERY_TIME_MAX = "query_time_max"
    FULL_SCAN_COUNT = "full_scan_count"

    # 锁指标
    LOCK_WAITS = "lock_waits"
    LOCK_WAIT_TIME = "lock_wait_time"
    DEADLOCKS = "deadlocks"
    ROW_LOCK_WAITS = "row_lock_waits"

    # 缓冲/缓存指标
    BUFFER_HIT_RATIO = "buffer_hit_ratio"
    BUFFER_POOL_USAGE = "buffer_pool_usage"
    CACHE_HIT_RATIO = "cache_hit_ratio"
    SHARED_BUFFER_USAGE = "shared_buffer_usage"

    # IO指标
    ROWS_READ = "rows_read"
    ROWS_CHANGED = "rows_changed"
    PHYSICAL_READS = "physical_reads"
    LOGICAL_READS = "logical_reads"
    DISK_IO_READ = "disk_io_read"
    DISK_IO_WRITE = "disk_io_write"
    DISK_IO_WAIT = "disk_io_wait"

    # 资源指标
    CPU_USAGE = "cpu_usage"
    MEMORY_USAGE = "memory_usage"
    DISK_USAGE = "disk_usage"
    TEMP_SPACE_USAGE = "temp_space_usage"

    # 复制/同步指标
    REPLICATION_LAG = "replication_lag"
    REPLICATION_IO = "replication_io"
    REPLICATION_SQL = "replication_sql"

    # 临时表指标
    TEMP_TABLES_DISK = "temp_tables_disk"
    TEMP_TABLES_MEMORY = "temp_tables_memory"

    # 表缓存指标
    TABLE_OPEN_CACHE = "table_open_cache"
    TABLE_DEFINITIONS_CACHE = "table_definitions_cache"

    # 事务指标
    TRANSACTIONS_ACTIVE = "transactions_active"
    TRANSACTIONS_COMMITTED = "transactions_committed"
    TRANSACTIONS_ROLLED_BACK = "transactions_rolled_back"


# =============================================================================
# 数据类
# =============================================================================

@dataclass
class MetricPoint:
    """指标数据点"""
    timestamp: datetime
    metric_type: MetricType
    value: float
    unit: str = ""
    tags: Dict[str, str] = field(default_factory=dict)
    source: str = "direct"

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "timestamp": self.timestamp.isoformat(),
            "metric_type": self.metric_type.value,
            "value": round(self.value, 4),
            "unit": self.unit,
            "tags": self.tags,
            "source": self.source
        }


@dataclass
class AnomalyAlert:
    """异常告警"""
    alert_id: str
    anomaly_type: AnomalyType
    severity: Severity
    metric_type: MetricType
    current_value: float
    expected_value: Optional[float]
    deviation_percent: float
    message: str
    timestamp: datetime
    tags: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "alert_id": self.alert_id,
            "anomaly_type": self.anomaly_type.value,
            "severity": self.severity.value,
            "metric_type": self.metric_type.value,
            "current_value": round(self.current_value, 2),
            "expected_value": round(self.expected_value, 2) if self.expected_value else None,
            "deviation_percent": round(self.deviation_percent, 2),
            "message": self.message,
            "timestamp": self.timestamp.isoformat(),
            "tags": self.tags
        }


@dataclass
class MonitorConfig:
    """监控配置"""
    collection_interval: int = 60              # 采集间隔(秒)
    max_history_size: int = 10080             # 最大历史数据点数(7天)
    max_alerts: int = 1000                     # 最大告警数
    enable_prediction: bool = True             # 启用容量预测
    enable_persistent_storage: bool = True     # 启用持久化存储
    storage_path: str = "./runtime_data/monitor"       # 存储路径
    alert_cooldown: int = 300                  # 告警冷却时间(秒)
    anomaly_threshold: float = 2.0             # 异常检测阈值(Z-score)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "collection_interval": self.collection_interval,
            "max_history_size": self.max_history_size,
            "max_alerts": self.max_alerts,
            "enable_prediction": self.enable_prediction,
            "enable_persistent_storage": self.enable_persistent_storage,
            "storage_path": self.storage_path,
            "alert_cooldown": self.alert_cooldown,
            "anomaly_threshold": self.anomaly_threshold
        }


@dataclass
class HealthAssessment:
    """健康评估结果"""
    status: HealthStatus
    score: int                                 # 0-100
    issues: List[str] = field(default_factory=list)
    metrics_summary: Dict[str, float] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "status": self.status.value,
            "score": self.score,
            "issues": self.issues,
            "metrics_summary": self.metrics_summary,
            "timestamp": self.timestamp.isoformat()
        }


@dataclass
class CapacityPrediction:
    """容量预测结果"""
    metric: str
    current_value: float
    current_time: datetime
    predictions: Dict[str, float]             # {"7d": 75.5, "30d": 82.3}
    days_to_threshold: Optional[int]
    threshold: float
    growth_rate_daily: float
    trend_direction: str                       # "up", "down", "stable"
    confidence: float                          # 0-1
    recommendation: str
    urgency: str                               # "low", "medium", "high", "critical"
    predictable: bool = True

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "metric": self.metric,
            "current_value": round(self.current_value, 2),
            "current_time": self.current_time.isoformat(),
            "predictions": {k: round(v, 2) for k, v in self.predictions.items()},
            "days_to_threshold": self.days_to_threshold,
            "threshold": self.threshold,
            "growth_rate_daily": round(self.growth_rate_daily, 4),
            "trend_direction": self.trend_direction,
            "confidence": round(self.confidence, 2),
            "recommendation": self.recommendation,
            "urgency": self.urgency,
            "predictable": self.predictable
        }


# =============================================================================
# 响应辅助函数
# =============================================================================

# 注意：create_success_response 和 create_error_response 已从 shared.error_handler 导入
# 不再在此文件中重复定义
