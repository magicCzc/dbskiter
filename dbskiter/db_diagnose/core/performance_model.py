"""
统一性能分析模型

文件功能：提供跨数据库的统一性能分析抽象层
主要类：
    - PerformanceModel: 性能数据模型
    - PerformanceAnalyzer: 性能分析器基类
    - PerformanceMetrics: 性能指标定义

设计原则：
    1. 统一抽象：不同数据库使用相同的性能模型
    2. 可扩展性：支持新的数据库类型
    3. 生产安全：内置超时、限流、降级机制
    4. 准确性：多维度指标关联分析

作者: AI Assistant
创建时间: 2026-04-24
版本: 1.0.0
"""

import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union

from dbskiter.shared.unified_connector import UnifiedConnector

logger = logging.getLogger(__name__)


class MetricCategory(Enum):
    """指标类别"""
    CPU = "cpu"                    # CPU相关
    IO = "io"                      # IO相关
    MEMORY = "memory"              # 内存相关
    CONCURRENCY = "concurrency"    # 并发相关
    LOCK = "lock"                  # 锁相关
    NETWORK = "network"            # 网络相关


class SeverityLevel(Enum):
    """严重程度级别"""
    CRITICAL = "critical"      # 严重
    HIGH = "high"              # 高
    MEDIUM = "medium"          # 中
    LOW = "low"                # 低
    INFO = "info"              # 信息


@dataclass
class PerformanceMetric:
    """
    性能指标数据类

    属性:
        name: 指标名称
        value: 指标值
        unit: 单位
        category: 指标类别
        threshold_warning: 警告阈值
        threshold_critical: 严重阈值
        higher_is_better: 是否值越高越好（如命中率）
        timestamp: 采集时间
        source: 数据来源
    """
    name: str
    value: float
    unit: str = ""
    category: MetricCategory = MetricCategory.CPU
    threshold_warning: Optional[float] = None
    threshold_critical: Optional[float] = None
    higher_is_better: bool = False  # 默认越低越好（如CPU使用率）
    timestamp: datetime = field(default_factory=datetime.now)
    source: str = ""

    def get_severity(self) -> SeverityLevel:
        """根据阈值判断严重程度"""
        if self.higher_is_better:
            # 越高越好的指标（如命中率）：低于阈值才告警
            if self.threshold_critical is not None and self.value <= self.threshold_critical:
                return SeverityLevel.CRITICAL
            if self.threshold_warning is not None and self.value <= self.threshold_warning:
                return SeverityLevel.HIGH
            return SeverityLevel.INFO
        else:
            # 越低越好的指标（如CPU使用率）：高于阈值才告警
            if self.threshold_critical is not None and self.value >= self.threshold_critical:
                return SeverityLevel.CRITICAL
            if self.threshold_warning is not None and self.value >= self.threshold_warning:
                return SeverityLevel.HIGH
            return SeverityLevel.INFO

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "name": self.name,
            "value": round(self.value, 2),
            "unit": self.unit,
            "category": self.category.value,
            "severity": self.get_severity().value,
            "threshold_warning": self.threshold_warning,
            "threshold_critical": self.threshold_critical,
            "higher_is_better": self.higher_is_better,
            "timestamp": self.timestamp.isoformat(),
            "source": self.source
        }


@dataclass
class SlowQueryInfo:
    """
    慢查询信息

    属性:
        sql_text: SQL文本
        sql_id: SQL标识
        execution_count: 执行次数
        total_time_ms: 总执行时间(ms)
        avg_time_ms: 平均执行时间(ms)
        max_time_ms: 最大执行时间(ms)
        rows_examined: 扫描行数
        rows_sent: 返回行数
        database: 数据库名
        first_seen: 首次出现时间
        last_seen: 最后出现时间
    """
    sql_text: str
    sql_id: Optional[str] = None
    execution_count: int = 0
    total_time_ms: float = 0.0
    avg_time_ms: float = 0.0
    max_time_ms: float = 0.0
    rows_examined: int = 0
    rows_sent: int = 0
    database: Optional[str] = None
    first_seen: Optional[datetime] = None
    last_seen: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "sql_text": self.sql_text[:200] if self.sql_text else None,
            "sql_id": self.sql_id,
            "execution_count": self.execution_count,
            "total_time_ms": round(self.total_time_ms, 2),
            "avg_time_ms": round(self.avg_time_ms, 2),
            "max_time_ms": round(self.max_time_ms, 2),
            "rows_examined": self.rows_examined,
            "rows_sent": self.rows_sent,
            "database": self.database,
            "first_seen": self.first_seen.isoformat() if self.first_seen else None,
            "last_seen": self.last_seen.isoformat() if self.last_seen else None
        }


@dataclass
class PerformanceSnapshot:
    """
    性能快照

    属性:
        timestamp: 快照时间
        metrics: 指标列表
        slow_queries: 慢查询列表
        active_sessions: 活跃会话数
        total_sessions: 总会话数
        wait_events: 等待事件统计
    """
    timestamp: datetime
    metrics: List[PerformanceMetric] = field(default_factory=list)
    slow_queries: List[SlowQueryInfo] = field(default_factory=list)
    active_sessions: int = 0
    total_sessions: int = 0
    wait_events: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "timestamp": self.timestamp.isoformat(),
            "metrics": [m.to_dict() for m in self.metrics],
            "slow_queries": [q.to_dict() for q in self.slow_queries],
            "active_sessions": self.active_sessions,
            "total_sessions": self.total_sessions,
            "wait_events": self.wait_events
        }


class PerformanceAnalyzer(ABC):
    """
    性能分析器基类

    所有数据库特定的性能分析器都应继承此类
    """

    # 默认超时时间(秒)
    DEFAULT_TIMEOUT = 30

    # 默认采样间隔(秒)
    DEFAULT_SAMPLE_INTERVAL = 5

    def __init__(self, connector: UnifiedConnector, timeout: int = DEFAULT_TIMEOUT):
        """
        初始化性能分析器

        参数:
            connector: 数据库连接器
            timeout: 查询超时时间(秒)
        """
        self.connector = connector
        self.dialect = connector.dialect.lower()
        self.timeout = timeout
        self._check_permissions()

    def _check_permissions(self):
        """检查必要权限"""
        try:
            # 根据数据库类型使用不同的测试SQL
            if 'oracle' in self.dialect:
                test_sql = "SELECT 1 FROM DUAL"
            else:
                test_sql = "SELECT 1"
            self._execute_with_timeout(test_sql, timeout=5)
            logger.info(f"权限检查通过: {self.dialect}")
        except Exception as e:
            logger.warning(f"权限检查失败: {e}")
            raise PermissionError(f"数据库连接或权限不足: {e}")

    def _execute_with_timeout(self, sql: str, params: Optional[Union[Tuple, Dict]] = None,
                              timeout: Optional[int] = None) -> Optional[List]:
        """
        带超时控制的SQL执行

        参数:
            sql: SQL语句
            params: 查询参数（元组或字典）
            timeout: 超时时间(秒)

        返回:
            查询结果或None
        """
        timeout = timeout or self.timeout

        import concurrent.futures

        def execute():
            try:
                result = self.connector.execute(sql, params)
                return result.rows if result else None
            except Exception as e:
                err_msg = str(e).split('\n')[0][:120]
                logger.warning(f"SQL执行失败 [{type(e).__name__}]: {err_msg}, SQL: {sql[:100]}")
                raise

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(execute)
            try:
                return future.result(timeout=timeout)
            except concurrent.futures.TimeoutError:
                logger.warning(f"SQL执行超时({timeout}秒): {sql[:100]}")
                raise TimeoutError(f"查询执行超时({timeout}秒)")

    @abstractmethod
    def collect_metrics(self) -> List[PerformanceMetric]:
        """
        采集性能指标

        返回:
            性能指标列表
        """
        pass

    @abstractmethod
    def collect_slow_queries(self, limit: int = 20,
                            min_time_ms: float = 1000) -> List[SlowQueryInfo]:
        """
        采集慢查询

        参数:
            limit: 返回条数限制
            min_time_ms: 最小执行时间(毫秒)

        返回:
            慢查询列表
        """
        pass

    @abstractmethod
    def get_active_sessions(self) -> Tuple[int, int]:
        """
        获取会话信息

        返回:
            (活跃会话数, 总会话数)
        """
        pass

    def take_snapshot(self) -> PerformanceSnapshot:
        """
        采集性能快照

        返回:
            性能快照
        """
        start_time = time.time()

        try:
            metrics = self.collect_metrics()
        except Exception as e:
            logger.error(f"指标采集失败: {e}")
            metrics = []

        try:
            slow_queries = self.collect_slow_queries()
        except Exception as e:
            logger.error(f"慢查询采集失败: {e}")
            slow_queries = []

        try:
            active, total = self.get_active_sessions()
        except Exception as e:
            logger.error(f"会话信息采集失败: {e}")
            active, total = 0, 0

        elapsed = time.time() - start_time
        logger.info(f"性能快照采集完成，耗时: {elapsed:.2f}秒")

        return PerformanceSnapshot(
            timestamp=datetime.now(),
            metrics=metrics,
            slow_queries=slow_queries,
            active_sessions=active,
            total_sessions=total
        )

    def analyze_bottleneck(self, snapshot: PerformanceSnapshot) -> List[Dict[str, Any]]:
        """
        分析性能瓶颈

        参数:
            snapshot: 性能快照

        返回:
            瓶颈列表
        """
        bottlenecks = []

        # 按类别分组分析
        category_metrics: Dict[MetricCategory, List[PerformanceMetric]] = {}
        for metric in snapshot.metrics:
            if metric.category not in category_metrics:
                category_metrics[metric.category] = []
            category_metrics[metric.category].append(metric)

        # 分析每个类别的瓶颈
        for category, metrics in category_metrics.items():
            high_severity = [m for m in metrics
                           if m.get_severity() in (SeverityLevel.CRITICAL, SeverityLevel.HIGH)]

            if high_severity:
                bottlenecks.append({
                    "category": category.value,
                    "severity": "high",
                    "metrics": [m.to_dict() for m in high_severity],
                    "suggestion": self._get_suggestion(category, high_severity)
                })

        # 分析活跃会话
        if snapshot.total_sessions > 0:
            active_ratio = snapshot.active_sessions / snapshot.total_sessions
            if active_ratio > 0.8:
                bottlenecks.append({
                    "category": "concurrency",
                    "severity": "high",
                    "description": f"活跃会话比例过高: {active_ratio*100:.1f}%",
                    "suggestion": "考虑增加连接池大小或优化慢查询"
                })

        return bottlenecks

    def _get_suggestion(self, category: MetricCategory,
                       metrics: List[PerformanceMetric]) -> str:
        """获取优化建议"""
        suggestions = {
            MetricCategory.CPU: "检查高CPU消耗的SQL，考虑优化或增加CPU资源",
            MetricCategory.IO: "IO负载高，考虑增加缓存或优化磁盘访问",
            MetricCategory.MEMORY: "内存使用率过高，考虑增加内存或优化缓存配置",
            MetricCategory.CONCURRENCY: "并发压力大，考虑优化连接池或增加实例",
            MetricCategory.LOCK: "锁竞争严重，检查事务逻辑和索引设计",
            MetricCategory.NETWORK: "网络延迟高，检查网络配置或就近部署"
        }
        return suggestions.get(category, "建议进一步分析具体原因")


# 统一的性能指标阈值定义
DEFAULT_THRESHOLDS = {
    # CPU相关
    "cpu_usage": {"warning": 70, "critical": 90, "unit": "%"},
    "cpu_time_ratio": {"warning": 60, "critical": 80, "unit": "%"},

    # IO相关
    "io_wait_ratio": {"warning": 30, "critical": 50, "unit": "%"},
    "disk_read_latency": {"warning": 10, "critical": 20, "unit": "ms"},
    "disk_write_latency": {"warning": 10, "critical": 20, "unit": "ms"},

    # 内存相关
    "memory_usage": {"warning": 80, "critical": 95, "unit": "%"},
    "buffer_hit_ratio": {"warning": 95, "critical": 90, "unit": "%"},

    # 并发相关
    "connection_usage": {"warning": 80, "critical": 95, "unit": "%"},
    "active_session_ratio": {"warning": 70, "critical": 90, "unit": "%"},

    # 锁相关
    "lock_wait_ratio": {"warning": 5, "critical": 10, "unit": "%"},
    "deadlock_count": {"warning": 1, "critical": 5, "unit": "count/h"},
}


def get_threshold(metric_name: str) -> Dict[str, Any]:
    """获取指标阈值"""
    return DEFAULT_THRESHOLDS.get(metric_name, {"warning": None, "critical": None, "unit": ""})
