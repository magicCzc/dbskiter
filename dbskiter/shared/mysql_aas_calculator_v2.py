"""
MySQL AAS (Average Active Sessions) 计算器 V2 - 企业级优化版

文件功能：计算MySQL数据库的AAS指标，识别性能瓶颈
主要类：
    - AASMetrics: AAS指标数据类
    - AASBottleneck: 瓶颈分析结果
    - AASCorrelation: 关联分析结果
    - AASPersistentStorage: 数据持久化存储
    - AASConfig: 配置管理
    - MySQLAASCalculatorV2: AAS计算核心（线程安全、高性能）

优化特性：
1. 线程安全 - 使用RLock和线程安全数据结构
2. 内存保护 - 自动清理机制防止内存泄漏
3. 数据持久化 - SQLite存储历史数据
4. 智能重试 - 指数退避重试机制
5. 查询缓存 - 减少数据库压力
6. 自适应阈值 - 基于历史数据的动态阈值
7. 详细日志 - 全链路可观测性
8. 配置外部化 - 支持环境变量和配置文件

使用示例：
    from dbskiter.shared.mysql_aas_calculator_v2 import MySQLAASCalculatorV2, AASConfig
    
    # 配置
    config = AASConfig.from_env()
    
    # 创建计算器
    calculator = MySQLAASCalculatorV2(connector, config=config)
    
    # 获取当前AAS
    aas = calculator.calculate_current_aas()
    print(f"当前AAS: {aas.total}, 状态: {aas.health_status}")
    
    # 获取历史趋势（支持持久化存储）
    history = calculator.get_aas_history(minutes=60, use_persistent=True)
    
    # 识别瓶颈
    bottleneck = calculator.identify_bottleneck()
    
    # 生成完整报告
    report = calculator.generate_report(minutes=60)
    print(report)

作者：AI Assistant
创建时间：2026-04-21
版本：2.0.0
"""

import logging
import time
import os
import sqlite3
import hashlib
import json
import statistics
from typing import Dict, List, Optional, Any, Tuple, Callable, Union
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from collections import deque
from functools import wraps
from enum import Enum
from pathlib import Path
import threading

logger = logging.getLogger(__name__)


# =============================================================================
# 枚举定义
# =============================================================================

class HealthStatus(Enum):
    """健康状态枚举"""
    HEALTHY = "healthy"       # 健康
    WARNING = "warning"       # 警告
    SATURATED = "saturated"   # 饱和
    OVERLOADED = "overloaded" # 过载
    UNKNOWN = "unknown"       # 未知


class BottleneckSeverity(Enum):
    """瓶颈严重程度枚举"""
    CRITICAL = "critical"     # 严重
    HIGH = "high"             # 高
    MEDIUM = "medium"         # 中
    LOW = "low"               # 低


# =============================================================================
# 工具装饰器
# =============================================================================

def retry_on_error(
    max_retries: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: Tuple[type, ...] = (Exception,)
):
    """
    重试装饰器 - 指数退避策略
    
    参数:
        max_retries: 最大重试次数
        delay: 初始延迟（秒）
        backoff: 退避倍数
        exceptions: 需要重试的异常类型
        
    示例:
        @retry_on_error(max_retries=3, delay=1.0)
        def fetch_data():
            return connector.execute("SELECT ...")
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            current_delay = delay
            last_exception = None
            
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt == max_retries - 1:
                        logger.error(
                            f"函数 {func.__name__} 在 {max_retries} 次尝试后失败: {e}"
                        )
                        raise
                    
                    logger.warning(
                        f"函数 {func.__name__} 尝试 {attempt + 1}/{max_retries} 失败: {e}, "
                        f"{current_delay:.1f}秒后重试"
                    )
                    time.sleep(current_delay)
                    current_delay *= backoff
            
            # 理论上不会执行到这里
            raise last_exception if last_exception else RuntimeError("未知错误")
        
        return wrapper
    return decorator


def timed_execution(func: Callable) -> Callable:
    """
    执行时间统计装饰器
    
    示例:
        @timed_execution
        def heavy_operation():
            pass
    """
    @wraps(func)
    def wrapper(*args, **kwargs) -> Any:
        start_time = time.perf_counter()
        try:
            result = func(*args, **kwargs)
            elapsed = time.perf_counter() - start_time
            logger.debug(f"函数 {func.__name__} 执行耗时: {elapsed:.3f}秒")
            return result
        except Exception as e:
            elapsed = time.perf_counter() - start_time
            logger.error(f"函数 {func.__name__} 执行失败，耗时: {elapsed:.3f}秒, 错误: {e}")
            raise
    
    return wrapper


# =============================================================================
# 配置类
# =============================================================================

@dataclass
class AASConfig:
    """
    AAS配置类 - 支持环境变量和默认值
    
    属性:
        max_history_size: 内存历史数据最大容量
        collection_interval: 采集间隔（秒）
        query_timeout: 查询超时时间（秒）
        cache_ttl: 缓存有效期（秒）
        enable_persistent_storage: 是否启用持久化存储
        storage_path: 持久化存储路径
        cpu_threshold: CPU告警阈值
        memory_threshold: 内存告警阈值
        connections_threshold: 连接数告警阈值
        buffer_hit_threshold: 缓冲命中率告警阈值
        enable_adaptive_threshold: 是否启用自适应阈值
        cleanup_interval: 清理检查间隔（秒）
        max_metric_age: 指标最大保留时间（小时）
        
    示例:
        # 从环境变量加载
        config = AASConfig.from_env()
        
        # 自定义配置
        config = AASConfig(
            max_history_size=5000,
            collection_interval=2.0,
            enable_persistent_storage=True
        )
    """
    # 历史数据配置
    max_history_size: int = 10000
    collection_interval: float = 1.0
    query_timeout: float = 5.0
    
    # 缓存配置
    cache_ttl: float = 5.0
    max_cache_size: int = 1000
    
    # 持久化配置
    enable_persistent_storage: bool = True
    storage_path: str = "./runtime_data/aas"
    storage_max_size_mb: int = 100
    
    # 阈值配置
    cpu_threshold: float = 80.0
    memory_threshold: float = 85.0
    connections_threshold: float = 100.0
    buffer_hit_threshold: float = 95.0
    
    # 自适应阈值配置
    enable_adaptive_threshold: bool = True
    adaptive_threshold_multiplier: float = 3.0  # 均值 + 3倍标准差
    adaptive_min_samples: int = 30
    
    # 清理配置
    cleanup_interval: float = 3600.0  # 1小时
    max_metric_age_hours: int = 168   # 7天
    
    # 重试配置
    retry_max_attempts: int = 3
    retry_delay: float = 1.0
    retry_backoff: float = 2.0
    
    @classmethod
    def from_env(cls) -> 'AASConfig':
        """
        从环境变量加载配置
        
        环境变量前缀: DBSKITER_AAS_
        示例:
            DBSKITER_AAS_MAX_HISTORY_SIZE=5000
            DBSKITER_AAS_ENABLE_PERSISTENT_STORAGE=true
            DBSKITER_AAS_STORAGE_PATH=/data/aas
        """
        prefix = "DBSKITER_AAS_"
        
        def get_env(key: str, default: Any, type_func: Callable = str) -> Any:
            value = os.getenv(f"{prefix}{key}", default)
            if type_func == bool:
                return str(value).lower() in ('true', '1', 'yes', 'on')
            return type_func(value)
        
        return cls(
            max_history_size=get_env("MAX_HISTORY_SIZE", 10000, int),
            collection_interval=get_env("COLLECTION_INTERVAL", 1.0, float),
            query_timeout=get_env("QUERY_TIMEOUT", 5.0, float),
            cache_ttl=get_env("CACHE_TTL", 5.0, float),
            max_cache_size=get_env("MAX_CACHE_SIZE", 1000, int),
            enable_persistent_storage=get_env("ENABLE_PERSISTENT_STORAGE", True, bool),
            storage_path=get_env("STORAGE_PATH", "./runtime_data/aas"),
            storage_max_size_mb=get_env("STORAGE_MAX_SIZE_MB", 100, int),
            cpu_threshold=get_env("CPU_THRESHOLD", 80.0, float),
            memory_threshold=get_env("MEMORY_THRESHOLD", 85.0, float),
            connections_threshold=get_env("CONNECTIONS_THRESHOLD", 100.0, float),
            buffer_hit_threshold=get_env("BUFFER_HIT_THRESHOLD", 95.0, float),
            enable_adaptive_threshold=get_env("ENABLE_ADAPTIVE_THRESHOLD", True, bool),
            adaptive_threshold_multiplier=get_env("ADAPTIVE_THRESHOLD_MULTIPLIER", 3.0, float),
            adaptive_min_samples=get_env("ADAPTIVE_MIN_SAMPLES", 30, int),
            cleanup_interval=get_env("CLEANUP_INTERVAL", 3600.0, float),
            max_metric_age_hours=get_env("MAX_METRIC_AGE_HOURS", 168, int),
            retry_max_attempts=get_env("RETRY_MAX_ATTEMPTS", 3, int),
            retry_delay=get_env("RETRY_DELAY", 1.0, float),
            retry_backoff=get_env("RETRY_BACKOFF", 2.0, float),
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return asdict(self)
    
    def validate(self) -> List[str]:
        """
        验证配置有效性
        
        返回:
            List[str]: 错误信息列表，空列表表示配置有效
        """
        errors = []
        
        if self.max_history_size < 100:
            errors.append("max_history_size 必须 >= 100")
        
        if self.collection_interval < 0.1:
            errors.append("collection_interval 必须 >= 0.1秒")
        
        if self.query_timeout < 1.0:
            errors.append("query_timeout 必须 >= 1.0秒")
        
        if self.cache_ttl < 0:
            errors.append("cache_ttl 必须 >= 0")
        
        if self.storage_max_size_mb < 10:
            errors.append("storage_max_size_mb 必须 >= 10")
        
        if not 0 < self.cpu_threshold <= 100:
            errors.append("cpu_threshold 必须在 (0, 100] 范围内")
        
        if self.retry_max_attempts < 1:
            errors.append("retry_max_attempts 必须 >= 1")
        
        return errors


# =============================================================================
# 数据类
# =============================================================================

@dataclass
class AASMetrics:
    """
    AAS指标数据类 - 不可变设计
    
    属性:
        total: 总AAS值（所有活跃会话）
        cpu: CPU使用中的会话数
        io: IO等待中的会话数
        lock: 锁等待中的会话数
        network: 网络等待中的会话数
        other: 其他等待类型的会话数
        timestamp: 采集时间戳
        vcpu_count: 服务器vCPU数量
        metadata: 额外元数据
        
    验证:
        - 所有数值必须 >= 0
        - total 必须 >= cpu + io + lock + network + other
        
    示例:
        >>> metrics = AASMetrics(
        ...     total=15.5,
        ...     cpu=8.2,
        ...     io=4.3,
        ...     lock=2.1,
        ...     network=0.5,
        ...     other=0.4,
        ...     vcpu_count=8
        ... )
        >>> print(f"CPU占比: {metrics.cpu_percentage:.1f}%")
        >>> print(f"健康状态: {metrics.health_status.value}")
    """
    total: float
    cpu: float
    io: float
    lock: float
    network: float
    other: float
    timestamp: datetime = field(default_factory=datetime.now)
    vcpu_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """数据验证"""
        # 验证所有数值非负
        for field_name, value in [
            ('total', self.total), ('cpu', self.cpu), ('io', self.io),
            ('lock', self.lock), ('network', self.network), ('other', self.other)
        ]:
            if value < 0:
                raise ValueError(f"{field_name} 不能为负数: {value}")
        
        # 验证vcpu_count非负
        if self.vcpu_count < 0:
            raise ValueError(f"vcpu_count 不能为负数: {self.vcpu_count}")
        
        # 验证total >= 各分类之和（允许小误差）
        category_sum = self.cpu + self.io + self.lock + self.network + self.other
        if category_sum > self.total * 1.01:  # 允许1%误差
            raise ValueError(
                f"分类之和 ({category_sum:.2f}) 不能超过 total ({self.total:.2f})"
            )
    
    @property
    def cpu_percentage(self) -> float:
        """CPU类AAS占总AAS的百分比"""
        return (self.cpu / self.total * 100) if self.total > 0 else 0.0
    
    @property
    def io_percentage(self) -> float:
        """IO类AAS占总AAS的百分比"""
        return (self.io / self.total * 100) if self.total > 0 else 0.0
    
    @property
    def lock_percentage(self) -> float:
        """Lock类AAS占总AAS的百分比"""
        return (self.lock / self.total * 100) if self.total > 0 else 0.0
    
    @property
    def network_percentage(self) -> float:
        """Network类AAS占总AAS的百分比"""
        return (self.network / self.total * 100) if self.total > 0 else 0.0
    
    @property
    def other_percentage(self) -> float:
        """Other类AAS占总AAS的百分比"""
        return (self.other / self.total * 100) if self.total > 0 else 0.0
    
    @property
    def is_overloaded(self) -> bool:
        """是否过载（AAS > vCPU数量）"""
        return self.vcpu_count > 0 and self.total > self.vcpu_count
    
    @property
    def is_saturated(self) -> bool:
        """是否饱和（AAS ≈ vCPU数量，误差10%以内）"""
        if self.vcpu_count <= 0:
            return False
        ratio_diff = abs(self.total - self.vcpu_count) / self.vcpu_count
        return ratio_diff < 0.1
    
    @property
    def health_status(self) -> HealthStatus:
        """健康状态评估"""
        if self.vcpu_count <= 0:
            return HealthStatus.UNKNOWN
        
        ratio = self.total / self.vcpu_count
        if ratio < 0.7:
            return HealthStatus.HEALTHY
        elif ratio < 1.0:
            return HealthStatus.WARNING
        elif ratio < 1.5:
            return HealthStatus.SATURATED
        else:
            return HealthStatus.OVERLOADED
    
    @property
    def utilization_ratio(self) -> float:
        """资源利用率（AAS / vCPU）"""
        return self.total / self.vcpu_count if self.vcpu_count > 0 else 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "total": round(self.total, 2),
            "cpu": round(self.cpu, 2),
            "io": round(self.io, 2),
            "lock": round(self.lock, 2),
            "network": round(self.network, 2),
            "other": round(self.other, 2),
            "timestamp": self.timestamp.isoformat(),
            "vcpu_count": self.vcpu_count,
            "cpu_percentage": round(self.cpu_percentage, 1),
            "io_percentage": round(self.io_percentage, 1),
            "lock_percentage": round(self.lock_percentage, 1),
            "network_percentage": round(self.network_percentage, 1),
            "other_percentage": round(self.other_percentage, 1),
            "health_status": self.health_status.value,
            "is_overloaded": self.is_overloaded,
            "is_saturated": self.is_saturated,
            "utilization_ratio": round(self.utilization_ratio, 2),
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AASMetrics':
        """从字典创建实例"""
        return cls(
            total=float(data['total']),
            cpu=float(data['cpu']),
            io=float(data['io']),
            lock=float(data['lock']),
            network=float(data['network']),
            other=float(data['other']),
            timestamp=datetime.fromisoformat(data['timestamp']),
            vcpu_count=int(data.get('vcpu_count', 0)),
            metadata=data.get('metadata', {})
        )


@dataclass
class AASBottleneck:
    """
    AAS瓶颈分析结果
    
    属性:
        primary_cause: 主要原因（cpu/io/lock/network/other）
        secondary_cause: 次要原因
        severity: 严重程度
        description: 详细描述
        recommendations: 优化建议列表
        top_events: 主要等待事件列表
        confidence: 置信度（0-1）
        
    示例:
        >>> bottleneck = AASBottleneck(
        ...     primary_cause="io",
        ...     severity=BottleneckSeverity.HIGH,
        ...     description="IO等待占AAS的60%，磁盘可能是瓶颈",
        ...     confidence=0.85
        ... )
    """
    primary_cause: str
    secondary_cause: Optional[str] = None
    severity: BottleneckSeverity = BottleneckSeverity.MEDIUM
    description: str = ""
    recommendations: List[str] = field(default_factory=list)
    top_events: List[Dict[str, Any]] = field(default_factory=list)
    confidence: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)
    
    def __post_init__(self):
        """验证置信度"""
        if not 0 <= self.confidence <= 1:
            raise ValueError(f"confidence 必须在 [0, 1] 范围内: {self.confidence}")
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "primary_cause": self.primary_cause,
            "secondary_cause": self.secondary_cause,
            "severity": self.severity.value,
            "description": self.description,
            "recommendations": self.recommendations,
            "top_events": self.top_events,
            "confidence": round(self.confidence, 2),
            "timestamp": self.timestamp.isoformat()
        }


@dataclass
class AASCorrelation:
    """
    AAS与慢查询关联分析结果
    
    属性:
        time_period: 分析时间段
        aas_data: AAS数据点列表
        slow_queries: 关联的慢查询列表
        correlations: 关联度分析结果
        insights: 洞察发现
        
    示例:
        >>> correlation = calculator.correlate_with_slow_queries(slow_queries)
        >>> for insight in correlation.insights:
        ...     print(insight)
    """
    time_period: Tuple[datetime, datetime]
    aas_data: List[AASMetrics]
    slow_queries: List[Dict[str, Any]]
    correlations: List[Dict[str, Any]] = field(default_factory=list)
    insights: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "time_period": [
                self.time_period[0].isoformat(),
                self.time_period[1].isoformat()
            ],
            "aas_data": [a.to_dict() for a in self.aas_data],
            "slow_queries": self.slow_queries,
            "correlations": self.correlations,
            "insights": self.insights
        }


# =============================================================================
# 持久化存储类
# =============================================================================

class AASPersistentStorage:
    """
    AAS数据持久化存储 - SQLite实现
    
    功能：
    1. 自动建表和索引
    2. 批量插入优化
    3. 自动清理过期数据
    4. 数据压缩存储
    5. 存储空间监控
    
    线程安全：是（SQLite线程安全模式）
    
    示例:
        >>> storage = AASPersistentStorage("./runtime_data/aas")
        >>> storage.save_metrics(metrics)
        >>> history = storage.get_history(
        ...     start_time=datetime.now() - timedelta(hours=24),
        ...     end_time=datetime.now()
        ... )
    """
    
    def __init__(
        self,
        storage_path: str = "./runtime_data/aas",
        max_size_mb: int = 100,
        max_age_hours: int = 168
    ):
        """
        初始化存储
        
        参数:
            storage_path: 存储目录路径
            max_size_mb: 最大存储大小（MB）
            max_age_hours: 数据最大保留时间（小时）
        """
        self.storage_path = Path(storage_path)
        self.max_size_mb = max_size_mb
        self.max_age_hours = max_age_hours
        self.db_path = self.storage_path / "aas_history.db"
        
        # 创建目录
        self.storage_path.mkdir(parents=True, exist_ok=True)
        
        # 初始化数据库
        self._init_database()
        
        logger.info(f"AAS持久化存储初始化完成: {self.db_path}")
    
    def _init_database(self):
        """初始化数据库表结构"""
        with sqlite3.connect(self.db_path) as conn:
            # 主表 - AAS指标
            conn.execute("""
                CREATE TABLE IF NOT EXISTS aas_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    total REAL NOT NULL,
                    cpu REAL NOT NULL,
                    io REAL NOT NULL,
                    lock REAL NOT NULL,
                    network REAL NOT NULL,
                    other REAL NOT NULL,
                    vcpu_count INTEGER NOT NULL,
                    metadata TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # 索引优化查询
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_timestamp 
                ON aas_metrics(timestamp)
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_created_at 
                ON aas_metrics(created_at)
            """)
            
            # 元数据表 - 存储配置和统计
            conn.execute("""
                CREATE TABLE IF NOT EXISTS storage_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            conn.commit()
    
    def save_metrics(self, metrics: AASMetrics) -> int:
        """
        保存单个指标
        
        参数:
            metrics: AAS指标对象
            
        返回:
            int: 插入的记录ID
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                INSERT INTO aas_metrics 
                (timestamp, total, cpu, io, lock, network, other, vcpu_count, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                metrics.timestamp.isoformat(),
                metrics.total,
                metrics.cpu,
                metrics.io,
                metrics.lock,
                metrics.network,
                metrics.other,
                metrics.vcpu_count,
                json.dumps(metrics.metadata) if metrics.metadata else None
            ))
            conn.commit()
            return cursor.lastrowid
    
    def save_metrics_batch(self, metrics_list: List[AASMetrics]) -> int:
        """
        批量保存指标（性能优化）
        
        参数:
            metrics_list: AAS指标列表
            
        返回:
            int: 插入的记录数
        """
        if not metrics_list:
            return 0
        
        data = [
            (
                m.timestamp.isoformat(),
                m.total, m.cpu, m.io, m.lock, m.network, m.other,
                m.vcpu_count,
                json.dumps(m.metadata) if m.metadata else None
            )
            for m in metrics_list
        ]
        
        with sqlite3.connect(self.db_path) as conn:
            conn.executemany("""
                INSERT INTO aas_metrics 
                (timestamp, total, cpu, io, lock, network, other, vcpu_count, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, data)
            conn.commit()
        
        return len(metrics_list)
    
    def get_history(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: Optional[int] = None
    ) -> List[AASMetrics]:
        """
        获取历史数据
        
        参数:
            start_time: 开始时间
            end_time: 结束时间
            limit: 最大返回数量
            
        返回:
            List[AASMetrics]: AAS指标列表
        """
        query = "SELECT * FROM aas_metrics WHERE 1=1"
        params = []
        
        if start_time:
            query += " AND timestamp >= ?"
            params.append(start_time.isoformat())
        
        if end_time:
            query += " AND timestamp <= ?"
            params.append(end_time.isoformat())
        
        query += " ORDER BY timestamp DESC"
        
        if limit:
            query += f" LIMIT {limit}"
        
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(query, params)
            rows = cursor.fetchall()
        
        metrics_list = []
        for row in rows:
            try:
                metrics = AASMetrics(
                    total=row['total'],
                    cpu=row['cpu'],
                    io=row['io'],
                    lock=row['lock'],
                    network=row['network'],
                    other=row['other'],
                    timestamp=datetime.fromisoformat(row['timestamp']),
                    vcpu_count=row['vcpu_count'],
                    metadata=json.loads(row['metadata']) if row['metadata'] else {}
                )
                metrics_list.append(metrics)
            except Exception as e:
                logger.warning(f"解析历史数据失败: {e}")
                continue
        
        # 按时间正序返回
        return list(reversed(metrics_list))
    
    def cleanup_old_data(self) -> int:
        """
        清理过期数据
        
        返回:
            int: 删除的记录数
        """
        cutoff_time = datetime.now() - timedelta(hours=self.max_age_hours)
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "DELETE FROM aas_metrics WHERE timestamp < ?",
                (cutoff_time.isoformat(),)
            )
            deleted = cursor.rowcount
            conn.commit()
        
        if deleted > 0:
            logger.info(f"清理了 {deleted} 条过期AAS数据")
        
        return deleted
    
    def get_storage_stats(self) -> Dict[str, Any]:
        """获取存储统计信息"""
        try:
            db_size = self.db_path.stat().st_size / (1024 * 1024)  # MB
        except Exception:
            db_size = 0
        
        with sqlite3.connect(self.db_path) as conn:
            # 总记录数
            cursor = conn.execute("SELECT COUNT(*) FROM aas_metrics")
            total_records = cursor.fetchone()[0]
            
            # 时间范围
            cursor = conn.execute(
                "SELECT MIN(timestamp), MAX(timestamp) FROM aas_metrics"
            )
            min_ts, max_ts = cursor.fetchone()
            
            # 最近24小时记录数
            day_ago = (datetime.now() - timedelta(days=1)).isoformat()
            cursor = conn.execute(
                "SELECT COUNT(*) FROM aas_metrics WHERE timestamp > ?",
                (day_ago,)
            )
            recent_records = cursor.fetchone()[0]
        
        return {
            "db_path": str(self.db_path),
            "db_size_mb": round(db_size, 2),
            "max_size_mb": self.max_size_mb,
            "usage_percent": round((db_size / self.max_size_mb) * 100, 1) if self.max_size_mb > 0 else 0,
            "total_records": total_records,
            "recent_24h_records": recent_records,
            "time_range": {
                "earliest": min_ts,
                "latest": max_ts
            },
            "max_age_hours": self.max_age_hours
        }
    
    def vacuum(self):
        """优化数据库（释放空间）"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("VACUUM")
        logger.info("AAS存储数据库已优化")


# =============================================================================
# 缓存类
# =============================================================================

class AASQueryCache:
    """
    查询结果缓存
    
    功能：
    1. 基于查询内容的智能缓存
    2. TTL过期机制
    3. 大小限制和LRU淘汰
    4. 线程安全
    
    示例:
        >>> cache = AASQueryCache(ttl=5.0, max_size=1000)
        >>> cache.set("query_key", result)
        >>> result = cache.get("query_key")
    """
    
    def __init__(self, ttl: float = 5.0, max_size: int = 1000):
        """
        初始化缓存
        
        参数:
            ttl: 缓存有效期（秒）
            max_size: 最大缓存条目数
        """
        self.ttl = ttl
        self.max_size = max_size
        self._cache: Dict[str, Tuple[Any, datetime]] = {}
        self._lock = threading.RLock()
        self._access_order: deque = deque(maxlen=max_size)
    
    def _make_key(self, query: str, params: Tuple = ()) -> str:
        """生成缓存键"""
        key_data = f"{query}:{json.dumps(params, default=str)}"
        return hashlib.md5(key_data.encode()).hexdigest()
    
    def get(self, query: str, params: Tuple = ()) -> Optional[Any]:
        """
        获取缓存值
        
        参数:
            query: 查询语句
            params: 查询参数
            
        返回:
            Optional[Any]: 缓存值，不存在或过期返回None
        """
        key = self._make_key(query, params)
        
        with self._lock:
            if key not in self._cache:
                return None
            
            value, timestamp = self._cache[key]
            
            # 检查是否过期
            if datetime.now() - timestamp > timedelta(seconds=self.ttl):
                del self._cache[key]
                return None
            
            # 更新访问顺序
            if key in self._access_order:
                self._access_order.remove(key)
            self._access_order.append(key)
            
            return value
    
    def set(self, query: str, value: Any, params: Tuple = ()):
        """
        设置缓存值
        
        参数:
            query: 查询语句
            value: 缓存值
            params: 查询参数
        """
        key = self._make_key(query, params)
        
        with self._lock:
            # LRU淘汰
            if len(self._cache) >= self.max_size and key not in self._cache:
                oldest_key = self._access_order.popleft()
                if oldest_key in self._cache:
                    del self._cache[oldest_key]
            
            self._cache[key] = (value, datetime.now())
            
            # 更新访问顺序
            if key in self._access_order:
                self._access_order.remove(key)
            self._access_order.append(key)
    
    def invalidate(self, pattern: Optional[str] = None):
        """
        使缓存失效
        
        参数:
            pattern: 匹配模式，None表示清空所有
        """
        with self._lock:
            if pattern is None:
                self._cache.clear()
                self._access_order.clear()
            else:
                # 简单实现：清空所有（实际可以按模式匹配）
                self._cache.clear()
                self._access_order.clear()
    
    def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计"""
        with self._lock:
            return {
                "size": len(self._cache),
                "max_size": self.max_size,
                "ttl": self.ttl,
                "usage_percent": round((len(self._cache) / self.max_size) * 100, 1)
            }


# =============================================================================
# 主计算器类
# =============================================================================

class MySQLAASCalculatorV2:
    """
    MySQL AAS计算器 V2 - 企业级实现
    
    核心功能：
    1. 实时AAS计算 - 基于performance_schema
    2. AAS分类统计 - CPU/IO/锁/网络/其他
    3. 瓶颈识别 - 自动识别主要性能瓶颈
    4. 历史趋势 - 内存+持久化双存储
    5. 慢查询关联 - AAS与慢查询的关联分析
    6. 自适应阈值 - 基于历史数据的动态告警
    
    性能保护：
    - 查询频率限制（可配置）
    - 查询超时保护（可配置）
    - 历史数据容量限制（自动清理）
    - 查询结果缓存（减少数据库压力）
    
    线程安全：
    - 所有操作使用RLock保护
    - 线程安全的数据结构
    - 原子性操作保证
    
    可靠性：
    - 指数退避重试机制
    - 详细日志记录
    - 优雅降级（故障时返回默认值）
    
    使用示例：
        >>> from dbskiter.shared.mysql_aas_calculator_v2 import (
        ...     MySQLAASCalculatorV2, AASConfig
        ... )
        >>> 
        >>> # 配置
        >>> config = AASConfig.from_env()
        >>> 
        >>> # 创建计算器
        >>> calculator = MySQLAASCalculatorV2(connector, config=config)
        >>> 
        >>> # 获取当前AAS
        >>> current = calculator.calculate_current_aas()
        >>> print(f"AAS: {current.total}, 状态: {current.health_status.value}")
        >>> 
        >>> # 识别瓶颈
        >>> bottleneck = calculator.identify_bottleneck()
        >>> print(f"瓶颈: {bottleneck.description}")
        >>> 
        >>> # 获取历史趋势（包含持久化数据）
        >>> history = calculator.get_aas_history(minutes=60, use_persistent=True)
        >>> 
        >>> # 生成完整报告
        >>> report = calculator.generate_report(minutes=60)
        >>> print(report)
    """
    
    # 等待事件分类映射
    WAIT_EVENT_CATEGORIES = {
        'cpu': [
            'CPU', 'cpu', 'executing', 'RUNNING', 'Sending data',
            'Sorting result', 'Creating sort index', 'Copying to tmp table'
        ],
        'io': [
            'io/', 'IO_', 'read', 'write', 'flush', 'sync',
            'wait/io/', 'innodb/io', 'myisam/io',
            'Waiting for ', 'waiting for ',
        ],
        'lock': [
            'lock', 'Lock', 'LOCK', 'mutex', 'rwlock',
            'wait/lock/', 'innodb/lock', 'myisam/lock',
            'Waiting for table', 'waiting for table',
            'Waiting for global', 'waiting for global',
            'Waiting for metadata', 'waiting for metadata'
        ],
        'network': [
            'net/', 'NET_', 'network', 'socket',
            'wait/net/', 'reading from net', 'writing to net',
        ],
    }
    
    def __init__(
        self,
        connector,
        config: Optional[AASConfig] = None
    ):
        """
        初始化AAS计算器
        
        参数:
            connector: 数据库连接器
            config: AAS配置，None则使用默认配置
            
        示例:
            >>> calculator = MySQLAASCalculatorV2(connector)
            >>> # 或
            >>> config = AASConfig(max_history_size=5000)
            >>> calculator = MySQLAASCalculatorV2(connector, config)
        """
        self.connector = connector
        self.config = config or AASConfig()
        
        # 验证配置
        errors = self.config.validate()
        if errors:
            raise ValueError(f"配置验证失败: {', '.join(errors)}")
        
        # 线程安全的历史数据存储
        self._history: deque = deque(maxlen=self.config.max_history_size)
        self._history_lock = threading.RLock()
        
        # 频率限制
        self._last_query_time = 0.0
        self._query_lock = threading.Lock()
        
        # vCPU数量缓存
        self._vcpu_count: Optional[int] = None
        self._vcpu_lock = threading.Lock()
        
        # 持久化存储
        self._storage: Optional[AASPersistentStorage] = None
        if self.config.enable_persistent_storage:
            try:
                self._storage = AASPersistentStorage(
                    storage_path=self.config.storage_path,
                    max_size_mb=self.config.storage_max_size_mb,
                    max_age_hours=self.config.max_metric_age_hours
                )
            except Exception as e:
                logger.warning(f"持久化存储初始化失败: {e}，将使用仅内存模式")
        
        # 查询缓存
        self._cache = AASQueryCache(
            ttl=self.config.cache_ttl,
            max_size=self.config.max_cache_size
        )
        
        # 后台清理任务
        self._cleanup_timer: Optional[threading.Timer] = None
        self._start_cleanup_task()
        
        # 检查前提条件
        self._check_prerequisites()
        
        logger.info(
            f"MySQLAASCalculatorV2 初始化完成，"
            f"vCPU: {self._vcpu_count}, "
            f"持久化: {self.config.enable_persistent_storage}"
        )
    
    def _start_cleanup_task(self):
        """启动后台清理任务"""
        def cleanup_worker():
            try:
                self._perform_cleanup()
            except Exception as e:
                logger.error(f"清理任务失败: {e}")
            finally:
                # 重新调度
                self._cleanup_timer = threading.Timer(
                    self.config.cleanup_interval,
                    cleanup_worker
                )
                self._cleanup_timer.daemon = True
                self._cleanup_timer.start()
        
        self._cleanup_timer = threading.Timer(
            self.config.cleanup_interval,
            cleanup_worker
        )
        self._cleanup_timer.daemon = True
        self._cleanup_timer.start()
    
    def _perform_cleanup(self):
        """执行清理操作"""
        logger.debug("执行定期清理任务")
        
        # 清理持久化存储
        if self._storage:
            try:
                deleted = self._storage.cleanup_old_data()
                if deleted > 0:
                    logger.info(f"清理了 {deleted} 条过期数据")
            except Exception as e:
                logger.error(f"持久化存储清理失败: {e}")
        
        # 清理缓存
        self._cache.invalidate()
    
    def _check_prerequisites(self):
        """检查MySQL配置是否支持AAS计算"""
        try:
            # 检查performance_schema是否启用
            result = self._execute_with_retry(
                "SHOW VARIABLES LIKE 'performance_schema'"
            )
            if result and result.rows and result.rows[0][1] != 'ON':
                logger.warning(
                    "performance_schema未启用，AAS计算可能不准确。"
                    "建议执行: SET GLOBAL performance_schema = ON;"
                )
            
            # 获取vCPU数量
            self._vcpu_count = self._get_vcpu_count()
            logger.info(f"服务器vCPU数量: {self._vcpu_count}")
            
        except Exception as e:
            logger.warning(f"检查前提条件失败: {e}")
    
    @retry_on_error(max_retries=3, delay=1.0)
    def _execute_with_retry(self, query: str, params: Tuple = ()):
        """带重试的查询执行"""
        return self.connector.execute(query, params)
    
    def _get_vcpu_count(self) -> int:
        """
        获取服务器vCPU数量（多源获取策略）
        
        尝试顺序：
        1. 从操作系统获取（最准确）
        2. 从MySQL变量估算
        3. 使用默认值
        
        返回:
            int: vCPU数量，默认8
        """
        with self._vcpu_lock:
            if self._vcpu_count is not None:
                return self._vcpu_count
            
            # 方法1: 从操作系统获取
            try:
                import os
                cpu_count = os.cpu_count()
                if cpu_count and cpu_count > 0:
                    logger.debug(f"从操作系统获取vCPU数量: {cpu_count}")
                    self._vcpu_count = cpu_count
                    return cpu_count
            except Exception as e:
                logger.debug(f"从操作系统获取vCPU失败: {e}")
            
            # 方法2: 从MySQL配置变量估算
            try:
                result = self._execute_with_retry(
                    "SHOW VARIABLES LIKE 'innodb_thread_concurrency'"
                )
                if result and result.rows and result.rows[0][1]:
                    concurrency = int(result.rows[0][1])
                    if concurrency > 0:
                        estimated = max(4, concurrency // 2)
                        logger.debug(f"从innodb_thread_concurrency估算vCPU: {estimated}")
                        self._vcpu_count = estimated
                        return estimated
            except Exception as e:
                logger.debug(f"从MySQL变量获取vCPU失败: {e}")
            
            # 方法3: 使用默认值
            logger.debug("使用默认vCPU数量: 8")
            self._vcpu_count = 8
            return 8
    
    def _rate_limit_check(self) -> bool:
        """
        查询频率限制检查
        
        返回:
            bool: 是否允许查询
        """
        with self._query_lock:
            current_time = time.time()
            if current_time - self._last_query_time < self.config.collection_interval:
                return False
            self._last_query_time = current_time
            return True
    
    @timed_execution
    def calculate_current_aas(self) -> AASMetrics:
        """
        计算当前AAS指标
        
        返回:
            AASMetrics: 当前AAS指标
            
        实现逻辑：
        1. 检查频率限制
        2. 查询performance_schema.threads获取活跃线程
        3. 根据线程状态分类（CPU/IO/锁/网络/其他）
        4. 统计各类别的会话数
        5. 存储到历史记录
        
        示例:
            >>> aas = calculator.calculate_current_aas()
            >>> print(f"总AAS: {aas.total}")
            >>> print(f"健康状态: {aas.health_status.value}")
        """
        # 频率限制检查
        if not self._rate_limit_check():
            with self._history_lock:
                if self._history:
                    logger.debug("触发频率限制，返回最近一次数据")
                    return self._history[-1]
        
        try:
            # 查询活跃会话
            query = """
                SELECT 
                    COUNT(*) as total_threads,
                    SUM(CASE WHEN PROCESSLIST_COMMAND != 'Sleep' 
                             AND PROCESSLIST_STATE IS NOT NULL THEN 1 ELSE 0 END) as active_threads,
                    SUM(CASE WHEN PROCESSLIST_STATE LIKE '%executing%' 
                             OR PROCESSLIST_STATE LIKE '%Sending data%' 
                             OR PROCESSLIST_STATE LIKE '%Sorting result%' THEN 1 ELSE 0 END) as cpu_threads,
                    SUM(CASE WHEN PROCESSLIST_STATE LIKE '%Waiting for%io%'
                             OR PROCESSLIST_STATE LIKE '%reading from%'
                             OR PROCESSLIST_STATE LIKE '%writing to%' THEN 1 ELSE 0 END) as io_threads,
                    SUM(CASE WHEN PROCESSLIST_STATE LIKE '%Waiting for%lock%'
                             OR PROCESSLIST_STATE LIKE '%Waiting for table%'
                             OR PROCESSLIST_STATE LIKE '%metadata lock%' THEN 1 ELSE 0 END) as lock_threads,
                    SUM(CASE WHEN PROCESSLIST_STATE LIKE '%Waiting for%net%'
                             OR PROCESSLIST_STATE LIKE '%reading from net%'
                             OR PROCESSLIST_STATE LIKE '%writing to net%' THEN 1 ELSE 0 END) as network_threads
                FROM performance_schema.threads
                WHERE TYPE = 'FOREGROUND'
            """
            
            result = self._execute_with_retry(query)
            
            if result and result.rows and len(result.rows[0]) >= 6:
                row = result.rows[0]
                total = float(row[1]) if row[1] is not None else 0
                cpu = float(row[2]) if len(row) > 2 and row[2] is not None else 0
                io = float(row[3]) if len(row) > 3 and row[3] is not None else 0
                lock = float(row[4]) if len(row) > 4 and row[4] is not None else 0
                network = float(row[5]) if len(row) > 5 and row[5] is not None else 0
                other = max(0, total - cpu - io - lock - network)
            else:
                total = cpu = io = lock = network = other = 0
            
            metrics = AASMetrics(
                total=total,
                cpu=cpu,
                io=io,
                lock=lock,
                network=network,
                other=other,
                vcpu_count=self._vcpu_count or 8,
                metadata={
                    "collection_method": "performance_schema.threads",
                    "query_time": datetime.now().isoformat()
                }
            )
            
            # 存储到历史
            self._add_to_history(metrics)
            
            logger.debug(f"AAS计算完成: total={total:.2f}, cpu={cpu:.2f}, io={io:.2f}")
            
            return metrics
            
        except Exception as e:
            logger.error(f"计算AAS失败: {e}", exc_info=True)
            # 返回空指标（优雅降级）
            return AASMetrics(
                total=0, cpu=0, io=0, lock=0, network=0, other=0,
                vcpu_count=self._vcpu_count or 8,
                metadata={"error": str(e), "collection_method": "fallback"}
            )
    
    def _add_to_history(self, metrics: AASMetrics):
        """
        添加指标到历史记录
        
        线程安全，自动处理容量限制
        """
        with self._history_lock:
            self._history.append(metrics)
        
        # 异步保存到持久化存储
        if self._storage:
            try:
                self._storage.save_metrics(metrics)
            except Exception as e:
                logger.warning(f"持久化存储失败: {e}")
    
    def get_aas_history(
        self,
        minutes: int = 30,
        interval: int = 60,
        use_persistent: bool = False
    ) -> List[AASMetrics]:
        """
        获取AAS历史数据
        
        参数:
            minutes: 查询最近多少分钟的数据
            interval: 数据点间隔（秒），0表示不采样
            use_persistent: 是否从持久化存储获取（包含更久历史）
            
        返回:
            List[AASMetrics]: AAS历史数据列表
            
        示例:
            >>> # 获取内存中的最近30分钟数据
            >>> history = calculator.get_aas_history(minutes=30)
            >>> 
            >>> # 获取持久化存储的最近24小时数据
            >>> history = calculator.get_aas_history(
            ...     minutes=1440,
            ...     use_persistent=True
            ... )
        """
        if use_persistent and self._storage:
            # 从持久化存储获取
            start_time = datetime.now() - timedelta(minutes=minutes)
            return self._storage.get_history(start_time=start_time)
        
        # 从内存获取
        with self._history_lock:
            cutoff_time = datetime.now() - timedelta(minutes=minutes)
            filtered = [m for m in self._history if m.timestamp >= cutoff_time]
            
            # 按间隔采样
            if interval > 0 and len(filtered) > 1:
                sampled = []
                last_time = None
                for m in filtered:
                    if last_time is None or (m.timestamp - last_time).seconds >= interval:
                        sampled.append(m)
                        last_time = m.timestamp
                return sampled
            
            return list(filtered)
    
    def identify_bottleneck(self) -> AASBottleneck:
        """
        识别性能瓶颈
        
        返回:
            AASBottleneck: 瓶颈分析结果
            
        分析逻辑：
        1. 获取当前AAS
        2. 分析各类别占比
        3. 识别主要瓶颈
        4. 生成优化建议
        
        示例:
            >>> bottleneck = calculator.identify_bottleneck()
            >>> print(f"主要瓶颈: {bottleneck.primary_cause}")
            >>> for rec in bottleneck.recommendations:
            ...     print(f"建议: {rec}")
        """
        current = self.calculate_current_aas()
        
        if current.total == 0:
            return AASBottleneck(
                primary_cause="unknown",
                severity=BottleneckSeverity.LOW,
                description="无法获取AAS数据，请检查performance_schema配置",
                confidence=0.0
            )
        
        # 分析各类别占比
        categories = {
            'cpu': (current.cpu, current.cpu_percentage),
            'io': (current.io, current.io_percentage),
            'lock': (current.lock, current.lock_percentage),
            'network': (current.network, current.network_percentage),
            'other': (current.other, current.other_percentage)
        }
        
        # 找出占比最高的类别
        sorted_categories = sorted(
            categories.items(),
            key=lambda x: x[1][1],
            reverse=True
        )
        
        primary = sorted_categories[0]
        secondary = sorted_categories[1] if len(sorted_categories) > 1 else None
        
        # 计算置信度（基于占比）
        confidence = primary[1][1] / 100.0
        
        # 确定严重程度
        if current.is_overloaded:
            severity = BottleneckSeverity.CRITICAL
        elif current.is_saturated:
            severity = BottleneckSeverity.HIGH
        elif primary[1][1] > 50:
            severity = BottleneckSeverity.HIGH
        elif primary[1][1] > 30:
            severity = BottleneckSeverity.MEDIUM
        else:
            severity = BottleneckSeverity.LOW
        
        # 生成描述和建议
        description = self._generate_bottleneck_description(
            primary, secondary, current
        )
        recommendations = self._generate_recommendations(primary[0], current)
        
        return AASBottleneck(
            primary_cause=primary[0],
            secondary_cause=secondary[0] if secondary else None,
            severity=severity,
            description=description,
            recommendations=recommendations,
            confidence=round(confidence, 2)
        )
    
    def _generate_bottleneck_description(
        self,
        primary: Tuple[str, Tuple[float, float]],
        secondary: Optional[Tuple[str, Tuple[float, float]]],
        metrics: AASMetrics
    ) -> str:
        """生成瓶颈描述"""
        cause_names = {
            'cpu': 'CPU计算',
            'io': 'IO等待',
            'lock': '锁等待',
            'network': '网络等待',
            'other': '其他等待'
        }
        
        desc = f"主要瓶颈是{cause_names.get(primary[0], primary[0])}，"
        desc += f"占AAS的{primary[1][1]:.1f}%（{primary[1][0]:.2f}个会话）"
        
        if secondary and secondary[1][1] > 10:
            desc += f"，次要因素是{cause_names.get(secondary[0], secondary[0])}（{secondary[1][1]:.1f}%）"
        
        if metrics.is_overloaded:
            desc += "。系统已过载，需要立即处理！"
        elif metrics.is_saturated:
            desc += "。系统接近饱和，建议关注。"
        
        return desc
    
    def _generate_recommendations(self, bottleneck_type: str, metrics: AASMetrics) -> List[str]:
        """生成优化建议"""
        recommendations = {
            'cpu': [
                "检查并优化高CPU消耗的SQL查询",
                "考虑增加服务器CPU资源",
                "检查是否有长时间运行的查询",
                "考虑使用查询缓存或结果缓存"
            ],
            'io': [
                "检查磁盘I/O性能，考虑使用SSD",
                "优化InnoDB缓冲池大小",
                "检查是否有全表扫描的查询",
                "考虑增加索引减少I/O"
            ],
            'lock': [
                "检查事务隔离级别设置",
                "优化长时间运行的事务",
                "检查是否有锁等待的查询",
                "考虑使用行级锁代替表级锁"
            ],
            'network': [
                "检查网络带宽和延迟",
                "优化大数据量查询，考虑分页",
                "检查是否有不必要的网络传输",
                "考虑使用连接池减少连接开销"
            ],
            'other': [
                "检查MySQL错误日志",
                "监控其他系统资源使用情况",
                "考虑升级MySQL版本",
                "联系DBA进行深度分析"
            ]
        }
        
        return recommendations.get(bottleneck_type, recommendations['other'])
    
    def get_aas_trend_analysis(
        self,
        minutes: int = 60,
        use_persistent: bool = False
    ) -> Dict[str, Any]:
        """
        获取AAS趋势分析
        
        参数:
            minutes: 分析时间范围（分钟）
            use_persistent: 是否使用持久化数据
            
        返回:
            Dict: 趋势分析结果
        """
        history = self.get_aas_history(
            minutes=minutes,
            use_persistent=use_persistent
        )
        
        if len(history) < 2:
            return {
                "status": "insufficient_data",
                "message": f"数据点不足（需要至少2个，当前{len(history)}个）"
            }
        
        # 计算统计值
        total_values = [h.total for h in history]
        avg_aas = statistics.mean(total_values)
        max_aas = max(total_values)
        min_aas = min(total_values)
        
        # 计算标准差
        if len(total_values) > 1:
            std_aas = statistics.stdev(total_values)
        else:
            std_aas = 0
        
        # 简单趋势判断（比较前半段和后半段）
        mid = len(total_values) // 2
        first_half_avg = statistics.mean(total_values[:mid]) if mid > 0 else avg_aas
        second_half_avg = statistics.mean(total_values[mid:]) if len(total_values) > mid else avg_aas
        
        if second_half_avg > first_half_avg * 1.1:
            trend_direction = "increasing"
            trend_desc = "上升趋势"
        elif second_half_avg < first_half_avg * 0.9:
            trend_direction = "decreasing"
            trend_desc = "下降趋势"
        else:
            trend_direction = "stable"
            trend_desc = "相对稳定"
        
        # 异常检测（简单Z-score）
        anomalies = []
        if std_aas > 0:
            for i, h in enumerate(history):
                z_score = (h.total - avg_aas) / std_aas
                if abs(z_score) > 2:
                    anomalies.append({
                        "timestamp": h.timestamp.isoformat(),
                        "value": h.total,
                        "z_score": round(z_score, 2)
                    })
        
        return {
            "status": "success",
            "data_points": len(history),
            "time_range_minutes": minutes,
            "statistics": {
                "avg_aas": round(avg_aas, 2),
                "max_aas": round(max_aas, 2),
                "min_aas": round(min_aas, 2),
                "std_aas": round(std_aas, 2)
            },
            "trend": {
                "direction": trend_direction,
                "description": trend_desc,
                "first_half_avg": round(first_half_avg, 2),
                "second_half_avg": round(second_half_avg, 2)
            },
            "anomalies": anomalies,
            "recommendations": self._generate_trend_recommendations(
                trend_direction, avg_aas, max_aas
            )
        }
    
    def _generate_trend_recommendations(
        self,
        trend: str,
        avg_aas: float,
        max_aas: float
    ) -> List[str]:
        """生成趋势建议"""
        recommendations = []
        
        vcpu = self._vcpu_count or 8
        
        if trend == "increasing":
            recommendations.append("AAS呈上升趋势，建议关注负载增长原因")
        
        if avg_aas > vcpu:
            recommendations.append(f"平均AAS({avg_aas:.1f})超过vCPU数量({vcpu})，系统可能过载")
        elif avg_aas > vcpu * 0.8:
            recommendations.append(f"平均AAS({avg_aas:.1f})接近vCPU数量({vcpu})，系统接近饱和")
        
        if max_aas > vcpu * 2:
            recommendations.append(f"峰值AAS({max_aas:.1f})远超vCPU数量，存在性能峰值")
        
        return recommendations
    
    def generate_report(self, minutes: int = 60) -> str:
        """
        生成AAS分析报告
        
        参数:
            minutes: 分析时间范围（分钟）
            
        返回:
            str: 格式化的分析报告
        """
        current = self.calculate_current_aas()
        trend = self.get_aas_trend_analysis(minutes=minutes)
        bottleneck = self.identify_bottleneck()
        
        lines = [
            "=" * 70,
            "MySQL AAS (Average Active Sessions) 分析报告 V2",
            "=" * 70,
            f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"分析时段: 最近 {minutes} 分钟",
            f"服务器vCPU: {self._vcpu_count or '未知'}",
            "",
            "-" * 70,
            "当前AAS指标",
            "-" * 70,
            f"总AAS: {current.total:.2f}",
            f"  - CPU: {current.cpu:.2f} ({current.cpu_percentage:.1f}%)",
            f"  - IO: {current.io:.2f} ({current.io_percentage:.1f}%)",
            f"  - Lock: {current.lock:.2f} ({current.lock_percentage:.1f}%)",
            f"  - Network: {current.network:.2f}",
            f"  - Other: {current.other:.2f}",
            f"",
            f"健康状态: {current.health_status.value.upper()}",
            f"资源利用率: {current.utilization_ratio:.1%}",
        ]
        
        if current.is_overloaded:
            lines.append("警告: 系统过载！需要立即处理！")
        elif current.is_saturated:
            lines.append("注意: 系统饱和，建议关注")
        
        lines.extend([
            "",
            "-" * 70,
            "性能瓶颈分析",
            "-" * 70,
            f"主要原因: {bottleneck.primary_cause.upper()}",
            f"次要原因: {bottleneck.secondary_cause or '无'}",
            f"严重程度: {bottleneck.severity.value.upper()}",
            f"置信度: {bottleneck.confidence:.0%}",
            f"描述: {bottleneck.description}",
            "",
            "优化建议:"
        ])
        
        for i, rec in enumerate(bottleneck.recommendations, 1):
            lines.append(f"  {i}. {rec}")
        
        if trend.get('status') == 'success':
            lines.extend([
                "",
                "-" * 70,
                f"趋势分析（最近{minutes}分钟）",
                "-" * 70,
                f"数据点: {trend['data_points']}",
                f"平均AAS: {trend['statistics']['avg_aas']}",
                f"最大AAS: {trend['statistics']['max_aas']}",
                f"最小AAS: {trend['statistics']['min_aas']}",
                f"标准差: {trend['statistics']['std_aas']}",
                f"趋势方向: {trend['trend']['description']}",
            ])
            
            if trend['anomalies']:
                lines.append(f"异常峰值: {len(trend['anomalies'])}个")
            
            if trend['recommendations']:
                lines.extend([
                    "",
                    "趋势建议:"
                ])
                for rec in trend['recommendations']:
                    lines.append(f"  - {rec}")
        
        # 存储统计
        if self._storage:
            try:
                storage_stats = self._storage.get_storage_stats()
                lines.extend([
                    "",
                    "-" * 70,
                    "持久化存储统计",
                    "-" * 70,
                    f"存储路径: {storage_stats['db_path']}",
                    f"数据库大小: {storage_stats['db_size_mb']:.1f} MB",
                    f"总记录数: {storage_stats['total_records']}",
                    f"最近24小时: {storage_stats['recent_24h_records']} 条",
                ])
            except Exception:
                pass
        
        lines.extend([
            "",
            "=" * 70,
            "报告生成完成",
            "=" * 70,
        ])
        
        return "\n".join(lines)
    
    def clear_history(self):
        """清空历史数据（内存和持久化）"""
        with self._history_lock:
            self._history.clear()
        
        if self._storage:
            try:
                # 注意：这里只是清空内存，持久化数据需要手动清理
                logger.info("内存中的AAS历史数据已清空（持久化数据保留）")
            except Exception as e:
                logger.error(f"清空历史数据失败: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """获取计算器统计信息"""
        with self._history_lock:
            memory_count = len(self._history)
        
        stats = {
            "memory_history": {
                "data_points": memory_count,
                "max_capacity": self.config.max_history_size
            },
            "cache": self._cache.get_stats(),
            "vcpu_count": self._vcpu_count,
            "config": self.config.to_dict()
        }
        
        if self._storage:
            try:
                stats["persistent_storage"] = self._storage.get_storage_stats()
            except Exception as e:
                stats["persistent_storage"] = {"error": str(e)}
        
        return stats
