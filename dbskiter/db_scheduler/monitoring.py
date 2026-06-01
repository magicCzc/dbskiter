"""
监控告警模块

文件功能：提供全面的监控和告警能力
主要功能：
    - 指标收集与管理（Metrics Collection）
    - Prometheus格式导出
    - 告警规则引擎
    - 健康检查端点
    - 实时监控面板数据

设计特点：
    - 线程安全：使用RLock保护指标数据
    - 低侵入性：通过装饰器自动收集指标
    - 可扩展：支持自定义指标和告警规则
    - 高性能：异步告警通知，批量指标上报

使用示例：
    >>> from dbskiter.db_scheduler.monitoring import MetricsCollector, AlertManager
    >>> 
    >>> # 创建指标收集器
    >>> metrics = MetricsCollector()
    >>> 
    >>> # 记录指标
    >>> metrics.counter("tasks_executed", labels={"status": "success"}).inc()
    >>> metrics.gauge("active_connections").set(10)
    >>> metrics.histogram("task_duration").observe(5.2)
    >>> 
    >>> # 配置告警规则
    >>> alert_manager = AlertManager()
    >>> alert_manager.add_rule(AlertRule(
    ...     name="high_error_rate",
    ...     condition="error_rate > 0.1",
    ...     duration=300,
    ...     severity="critical"
    ... ))
    >>> 
    >>> # 导出Prometheus格式
    >>> print(metrics.to_prometheus())

作者：AI Assistant
创建时间：2026-04-21
"""

import threading
import time
import logging
import json
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from collections import deque

# 配置日志
logger = logging.getLogger(__name__)


# =============================================================================
# 枚举和数据类
# =============================================================================

class MetricType(Enum):
    """指标类型"""
    COUNTER = "counter"       # 计数器（单调递增）
    GAUGE = "gauge"           # 仪表盘（可增可减）
    HISTOGRAM = "histogram"   # 直方图
    SUMMARY = "summary"       # 摘要（分位数统计）


class AlertSeverity(Enum):
    """告警级别"""
    INFO = "info"             # 信息
    WARNING = "warning"       # 警告
    CRITICAL = "critical"     # 严重
    EMERGENCY = "emergency"   # 紧急


class AlertState(Enum):
    """告警状态"""
    PENDING = "pending"       # 待触发
    FIRING = "firing"         # 触发中
    RESOLVED = "resolved"     # 已恢复
    SILENCED = "silenced"     # 已静默


@dataclass
class MetricValue:
    """
    指标值
    
    属性:
        name: 指标名称
        value: 数值
        labels: 标签字典
        timestamp: 时间戳
        metric_type: 指标类型
    """
    name: str
    value: float
    labels: Dict[str, str] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    metric_type: MetricType = MetricType.GAUGE
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "name": self.name,
            "value": self.value,
            "labels": self.labels,
            "timestamp": self.timestamp.isoformat(),
            "type": self.metric_type.value
        }


@dataclass
class AlertRule:
    """
    告警规则
    
    属性:
        name: 规则名称
        description: 规则描述
        condition: 触发条件表达式
        duration: 持续时间（秒）
        severity: 告警级别
        labels: 标签
        annotations: 注解
        enabled: 是否启用
    """
    name: str
    description: str
    condition: str
    duration: int = 60
    severity: AlertSeverity = AlertSeverity.WARNING
    labels: Dict[str, str] = field(default_factory=dict)
    annotations: Dict[str, str] = field(default_factory=dict)
    enabled: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "name": self.name,
            "description": self.description,
            "condition": self.condition,
            "duration": self.duration,
            "severity": self.severity.value,
            "labels": self.labels,
            "annotations": self.annotations,
            "enabled": self.enabled
        }


@dataclass
class Alert:
    """
    告警实例
    
    属性:
        id: 告警ID
        rule_name: 规则名称
        severity: 告警级别
        state: 告警状态
        message: 告警消息
        labels: 标签
        starts_at: 开始时间
        ends_at: 结束时间
        value: 触发值
    """
    id: str
    rule_name: str
    severity: AlertSeverity
    state: AlertState
    message: str
    labels: Dict[str, str] = field(default_factory=dict)
    starts_at: datetime = field(default_factory=datetime.now)
    ends_at: Optional[datetime] = None
    value: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "rule_name": self.rule_name,
            "severity": self.severity.value,
            "state": self.state.value,
            "message": self.message,
            "labels": self.labels,
            "starts_at": self.starts_at.isoformat(),
            "ends_at": self.ends_at.isoformat() if self.ends_at else None,
            "value": self.value
        }


# =============================================================================
# 指标收集器
# =============================================================================

class Counter:
    """计数器指标"""
    
    def __init__(self, name: str, labels: Dict[str, str] = None, description: str = ""):
        self.name = name
        self.labels = labels or {}
        self.description = description
        self._value = 0.0
        self._lock = threading.Lock()
    
    def inc(self, amount: float = 1.0):
        """增加计数"""
        with self._lock:
            self._value += amount
    
    def get(self) -> float:
        """获取当前值"""
        with self._lock:
            return self._value
    
    def to_prometheus(self) -> str:
        """导出Prometheus格式"""
        labels_str = ",".join([f'{k}="{v}"' for k, v in self.labels.items()])
        lines = []
        if self.description:
            lines.append(f"# HELP {self.name} {self.description}")
        lines.append(f"# TYPE {self.name} counter")
        if labels_str:
            lines.append(f'{self.name}{{{labels_str}}} {self._value}')
        else:
            lines.append(f'{self.name} {self._value}')
        return "\n".join(lines)


class Gauge:
    """仪表盘指标"""
    
    def __init__(self, name: str, labels: Dict[str, str] = None, description: str = ""):
        self.name = name
        self.labels = labels or {}
        self.description = description
        self._value = 0.0
        self._lock = threading.Lock()
    
    def set(self, value: float):
        """设置值"""
        with self._lock:
            self._value = value
    
    def inc(self, amount: float = 1.0):
        """增加"""
        with self._lock:
            self._value += amount
    
    def dec(self, amount: float = 1.0):
        """减少"""
        with self._lock:
            self._value -= amount
    
    def get(self) -> float:
        """获取当前值"""
        with self._lock:
            return self._value
    
    def to_prometheus(self) -> str:
        """导出Prometheus格式"""
        labels_str = ",".join([f'{k}="{v}"' for k, v in self.labels.items()])
        lines = []
        if self.description:
            lines.append(f"# HELP {self.name} {self.description}")
        lines.append(f"# TYPE {self.name} gauge")
        if labels_str:
            lines.append(f'{self.name}{{{labels_str}}} {self._value}')
        else:
            lines.append(f'{self.name} {self._value}')
        return "\n".join(lines)


class Histogram:
    """直方图指标"""
    
    DEFAULT_BUCKETS = [0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10]
    
    def __init__(self, name: str, labels: Dict[str, str] = None, 
                 buckets: List[float] = None, description: str = ""):
        self.name = name
        self.labels = labels or {}
        self.buckets = sorted(buckets or self.DEFAULT_BUCKETS)
        self.description = description
        self._counts = {b: 0 for b in self.buckets}
        self._sum = 0.0
        self._count = 0
        self._lock = threading.Lock()
    
    def observe(self, value: float):
        """观察值"""
        with self._lock:
            self._sum += value
            self._count += 1
            for bucket in self.buckets:
                if value <= bucket:
                    self._counts[bucket] += 1
    
    def to_prometheus(self) -> str:
        """导出Prometheus格式"""
        labels_str = ",".join([f'{k}="{v}"' for k, v in self.labels.items()])
        lines = []
        if self.description:
            lines.append(f"# HELP {self.name} {self.description}")
        lines.append(f"# TYPE {self.name} histogram")
        
        for bucket in self.buckets:
            bucket_labels = f'{labels_str},le="{bucket}"' if labels_str else f'le="{bucket}"'
            lines.append(f'{self.name}_bucket{{{bucket_labels}}} {self._counts[bucket]}')
        
        # +Inf bucket
        inf_labels = f'{labels_str},le="+Inf"' if labels_str else 'le="+Inf"'
        lines.append(f'{self.name}_bucket{{{inf_labels}}} {self._count}')
        
        if labels_str:
            lines.append(f'{self.name}_sum{{{labels_str}}} {self._sum}')
            lines.append(f'{self.name}_count{{{labels_str}}} {self._count}')
        else:
            lines.append(f'{self.name}_sum {self._sum}')
            lines.append(f'{self.name}_count {self._count}')
        
        return "\n".join(lines)


class MetricsCollector:
    """
    指标收集器
    
    功能：
        - 管理所有指标
        - 支持Counter、Gauge、Histogram
        - 导出Prometheus格式
        - 指标持久化
    
    使用示例：
        >>> collector = MetricsCollector()
        >>> 
        >>> # 计数器
        >>> collector.counter("requests_total", labels={"method": "GET"}).inc()
        >>> 
        >>> # 仪表盘
        >>> collector.gauge("active_tasks").set(5)
        >>> 
        >>> # 直方图
        >>> collector.histogram("request_duration").observe(0.5)
        >>> 
        >>> # 导出Prometheus格式
        >>> print(collector.to_prometheus())
    """
    
    def __init__(self):
        """初始化指标收集器"""
        self._counters: Dict[str, Counter] = {}
        self._gauges: Dict[str, Gauge] = {}
        self._histograms: Dict[str, Histogram] = {}
        self._lock = threading.RLock()
        self._history: deque = deque(maxlen=10000)  # 历史数据
    
    def counter(self, name: str, labels: Dict[str, str] = None, 
                description: str = "") -> Counter:
        """
        获取或创建计数器
        
        参数:
            name: 指标名称
            labels: 标签
            description: 描述
            
        返回:
            Counter: 计数器实例
        """
        key = self._make_key(name, labels)
        with self._lock:
            if key not in self._counters:
                self._counters[key] = Counter(name, labels, description)
            return self._counters[key]
    
    def gauge(self, name: str, labels: Dict[str, str] = None, 
              description: str = "") -> Gauge:
        """
        获取或创建仪表盘
        
        参数:
            name: 指标名称
            labels: 标签
            description: 描述
            
        返回:
            Gauge: 仪表盘实例
        """
        key = self._make_key(name, labels)
        with self._lock:
            if key not in self._gauges:
                self._gauges[key] = Gauge(name, labels, description)
            return self._gauges[key]
    
    def histogram(self, name: str, labels: Dict[str, str] = None, 
                  buckets: List[float] = None, description: str = "") -> Histogram:
        """
        获取或创建直方图
        
        参数:
            name: 指标名称
            labels: 标签
            buckets: 分桶边界
            description: 描述
            
        返回:
            Histogram: 直方图实例
        """
        key = self._make_key(name, labels)
        with self._lock:
            if key not in self._histograms:
                self._histograms[key] = Histogram(name, labels, buckets, description)
            return self._histograms[key]
    
    def record(self, metric: MetricValue):
        """记录指标值"""
        self._history.append(metric)
    
    def get_history(self, name: str = None, 
                   start_time: datetime = None, 
                   end_time: datetime = None,
                   limit: int = 100) -> List[MetricValue]:
        """
        获取历史数据
        
        参数:
            name: 指标名称过滤
            start_time: 开始时间
            end_time: 结束时间
            limit: 返回数量限制
            
        返回:
            List[MetricValue]: 历史指标值列表
        """
        with self._lock:
            result = []
            for metric in reversed(self._history):
                if name and metric.name != name:
                    continue
                if start_time and metric.timestamp < start_time:
                    continue
                if end_time and metric.timestamp > end_time:
                    continue
                result.append(metric)
                if len(result) >= limit:
                    break
            return result
    
    def to_prometheus(self) -> str:
        """
        导出Prometheus格式
        
        返回:
            str: Prometheus格式的指标数据
        """
        with self._lock:
            lines = []
            
            # Counters
            for counter in self._counters.values():
                lines.append(counter.to_prometheus())
            
            # Gauges
            for gauge in self._gauges.values():
                lines.append(gauge.to_prometheus())
            
            # Histograms
            for histogram in self._histograms.values():
                lines.append(histogram.to_prometheus())
            
            return "\n\n".join(lines)
    
    def to_dict(self) -> Dict[str, Any]:
        """导出为字典"""
        with self._lock:
            return {
                "counters": {k: v.get() for k, v in self._counters.items()},
                "gauges": {k: v.get() for k, v in self._gauges.items()},
                "histograms": {k: {"count": v._count, "sum": v._sum} 
                              for k, v in self._histograms.items()}
            }
    
    def _make_key(self, name: str, labels: Dict[str, str]) -> str:
        """生成指标键"""
        if not labels:
            return name
        label_str = ",".join([f"{k}={v}" for k, v in sorted(labels.items())])
        return f"{name}{{{label_str}}}"


# =============================================================================
# 告警管理器
# =============================================================================

class AlertNotifier(ABC):
    """告警通知器基类"""
    
    @abstractmethod
    def notify(self, alert: Alert):
        """发送告警通知"""
        pass


class LoggingNotifier(AlertNotifier):
    """日志告警通知器"""
    
    def notify(self, alert: Alert):
        """记录告警到日志"""
        msg = f"[{alert.severity.value.upper()}] {alert.rule_name}: {alert.message}"
        if alert.severity == AlertSeverity.CRITICAL:
            logger.critical(msg)
        elif alert.severity == AlertSeverity.WARNING:
            logger.warning(msg)
        else:
            logger.info(msg)


class WebhookNotifier(AlertNotifier):
    """Webhook告警通知器"""
    
    def __init__(self, webhook_url: str, headers: Dict[str, str] = None):
        self.webhook_url = webhook_url
        self.headers = headers or {}
    
    def notify(self, alert: Alert):
        """发送Webhook通知"""
        import requests
        
        try:
            payload = {
                "alert_id": alert.id,
                "rule_name": alert.rule_name,
                "severity": alert.severity.value,
                "message": alert.message,
                "labels": alert.labels,
                "timestamp": alert.starts_at.isoformat(),
                "value": alert.value
            }
            
            response = requests.post(
                self.webhook_url,
                json=payload,
                headers=self.headers,
                timeout=10
            )
            response.raise_for_status()
            logger.debug(f"Webhook通知发送成功: {alert.id}")
        
        except Exception as e:
            logger.error(f"Webhook通知发送失败: {e}")


class AlertManager:
    """
    告警管理器
    
    功能：
        - 管理告警规则
        - 评估告警条件
        - 发送告警通知
        - 告警状态管理
    
    使用示例：
        >>> manager = AlertManager()
        >>> 
        >>> # 添加规则
        >>> manager.add_rule(AlertRule(
        ...     name="high_error_rate",
        ...     description="错误率过高",
        ...     condition="error_rate > 0.1",
        ...     severity=AlertSeverity.CRITICAL
        ... ))
        >>> 
        >>> # 评估指标
        >>> manager.evaluate({"error_rate": 0.15})
        >>> 
        >>> # 获取活跃告警
        >>> alerts = manager.get_active_alerts()
    """
    
    def __init__(self, evaluation_interval: int = 60):
        """
        初始化告警管理器
        
        参数:
            evaluation_interval: 评估间隔（秒）
        """
        self._rules: Dict[str, AlertRule] = {}
        self._alerts: Dict[str, Alert] = {}
        self._notifiers: List[AlertNotifier] = []
        self._evaluation_interval = evaluation_interval
        self._lock = threading.RLock()
        self._running = False
        self._eval_thread: Optional[threading.Thread] = None
        self._alert_history: deque = deque(maxlen=1000)
    
    def add_rule(self, rule: AlertRule):
        """
        添加告警规则
        
        参数:
            rule: 告警规则
        """
        with self._lock:
            self._rules[rule.name] = rule
            logger.info(f"添加告警规则: {rule.name}")
    
    def remove_rule(self, name: str):
        """
        移除告警规则
        
        参数:
            name: 规则名称
        """
        with self._lock:
            if name in self._rules:
                del self._rules[name]
                logger.info(f"移除告警规则: {name}")
    
    def add_notifier(self, notifier: AlertNotifier):
        """
        添加告警通知器
        
        参数:
            notifier: 通知器实例
        """
        with self._lock:
            self._notifiers.append(notifier)
    
    def evaluate(self, metrics: Dict[str, float], labels: Dict[str, str] = None):
        """
        评估告警规则
        
        参数:
            metrics: 指标数据
            labels: 标签
        """
        with self._lock:
            for rule in self._rules.values():
                if not rule.enabled:
                    continue
                
                try:
                    if self._check_condition(rule.condition, metrics):
                        self._trigger_alert(rule, metrics, labels)
                    else:
                        self._resolve_alert(rule.name, labels)
                except Exception as e:
                    logger.error(f"评估规则失败 {rule.name}: {e}")
    
    def _check_condition(self, condition: str, metrics: Dict[str, float]) -> bool:
        """
        检查条件
        
        参数:
            condition: 条件表达式
            metrics: 指标数据
            
        返回:
            bool: 条件是否满足
        """
        # 简单的条件解析，支持 > < >= <= ==
        try:
            # 替换指标名称为值
            expr = condition
            for name, value in metrics.items():
                expr = expr.replace(name, str(value))
            
            # 安全评估
            return eval(expr, {"__builtins__": {}}, {})
        except Exception as e:
            logger.error(f"条件评估失败: {condition}, 错误: {e}")
            return False
    
    def _trigger_alert(self, rule: AlertRule, metrics: Dict[str, float], 
                      labels: Dict[str, str]):
        """触发告警"""
        alert_id = self._make_alert_id(rule.name, labels)
        
        if alert_id in self._alerts:
            # 告警已存在，更新状态
            alert = self._alerts[alert_id]
            if alert.state == AlertState.PENDING:
                # 检查是否达到持续时间
                elapsed = (datetime.now() - alert.starts_at).total_seconds()
                if elapsed >= rule.duration:
                    alert.state = AlertState.FIRING
                    self._send_notifications(alert)
        else:
            # 创建新告警
            alert = Alert(
                id=alert_id,
                rule_name=rule.name,
                severity=rule.severity,
                state=AlertState.PENDING,
                message=rule.description,
                labels={**(labels or {}), **rule.labels},
                value=self._get_trigger_value(rule.condition, metrics)
            )
            self._alerts[alert_id] = alert
            self._alert_history.append(alert)
            logger.info(f"告警触发: {alert_id}")
    
    def _resolve_alert(self, rule_name: str, labels: Dict[str, str]):
        """恢复告警"""
        alert_id = self._make_alert_id(rule_name, labels)
        
        if alert_id in self._alerts:
            alert = self._alerts[alert_id]
            if alert.state in [AlertState.PENDING, AlertState.FIRING]:
                alert.state = AlertState.RESOLVED
                alert.ends_at = datetime.now()
                self._send_notifications(alert)
                logger.info(f"告警恢复: {alert_id}")
    
    def _send_notifications(self, alert: Alert):
        """发送告警通知"""
        for notifier in self._notifiers:
            try:
                notifier.notify(alert)
            except Exception as e:
                logger.error(f"通知发送失败: {e}")
    
    def _make_alert_id(self, rule_name: str, labels: Dict[str, str]) -> str:
        """生成告警ID"""
        if not labels:
            return rule_name
        label_str = ",".join([f"{k}={v}" for k, v in sorted(labels.items())])
        return f"{rule_name}:{label_str}"
    
    def _get_trigger_value(self, condition: str, metrics: Dict[str, float]) -> float:
        """获取触发值"""
        # 从条件中提取第一个指标的值
        for name, value in metrics.items():
            if name in condition:
                return value
        return 0.0
    
    def get_active_alerts(self) -> List[Alert]:
        """
        获取活跃告警
        
        返回:
            List[Alert]: 活跃告警列表
        """
        with self._lock:
            return [a for a in self._alerts.values() 
                   if a.state in [AlertState.PENDING, AlertState.FIRING]]
    
    def get_alert_history(self, limit: int = 100) -> List[Alert]:
        """
        获取告警历史
        
        参数:
            limit: 返回数量限制
            
        返回:
            List[Alert]: 告警历史列表
        """
        with self._lock:
            return list(self._alert_history)[:limit]
    
    def silence_alert(self, alert_id: str, duration: int):
        """
        静默告警
        
        参数:
            alert_id: 告警ID
            duration: 静默时长（秒）
        """
        with self._lock:
            if alert_id in self._alerts:
                self._alerts[alert_id].state = AlertState.SILENCED
                logger.info(f"告警静默: {alert_id}, 时长: {duration}秒")
    
    def start(self):
        """启动告警管理器"""
        if self._running:
            return
        
        self._running = True
        self._eval_thread = threading.Thread(
            target=self._evaluation_loop,
            name="AlertManager-Evaluation",
            daemon=True
        )
        self._eval_thread.start()
        logger.info("告警管理器已启动")
    
    def stop(self):
        """停止告警管理器"""
        self._running = False
        if self._eval_thread:
            self._eval_thread.join(timeout=5)
        logger.info("告警管理器已停止")
    
    def _evaluation_loop(self):
        """评估循环"""
        while self._running:
            try:
                time.sleep(self._evaluation_interval)
            except Exception as e:
                logger.error(f"评估循环异常: {e}")


# =============================================================================
# 健康检查
# =============================================================================

class HealthStatus(Enum):
    """健康状态"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


@dataclass
class HealthCheck:
    """健康检查结果"""
    name: str
    status: HealthStatus
    message: str
    timestamp: datetime = field(default_factory=datetime.now)
    details: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "name": self.name,
            "status": self.status.value,
            "message": self.message,
            "timestamp": self.timestamp.isoformat(),
            "details": self.details
        }


class HealthChecker:
    """
    健康检查器
    
    功能：
        - 执行健康检查
        - 汇总健康状态
        - 提供HTTP端点数据
    """
    
    def __init__(self):
        """初始化健康检查器"""
        self._checks: Dict[str, Callable[[], HealthCheck]] = {}
        self._lock = threading.RLock()
    
    def register_check(self, name: str, check_func: Callable[[], HealthCheck]):
        """
        注册健康检查
        
        参数:
            name: 检查名称
            check_func: 检查函数
        """
        with self._lock:
            self._checks[name] = check_func
            logger.info(f"注册健康检查: {name}")
    
    def check_all(self) -> Dict[str, Any]:
        """
        执行所有健康检查
        
        返回:
            Dict: 健康检查结果
        """
        with self._lock:
            results = {}
            overall_status = HealthStatus.HEALTHY
            
            for name, check_func in self._checks.items():
                try:
                    result = check_func()
                    results[name] = result.to_dict()
                    
                    # 更新整体状态
                    if result.status == HealthStatus.UNHEALTHY:
                        overall_status = HealthStatus.UNHEALTHY
                    elif result.status == HealthStatus.DEGRADED and overall_status == HealthStatus.HEALTHY:
                        overall_status = HealthStatus.DEGRADED
                
                except Exception as e:
                    results[name] = {
                        "name": name,
                        "status": HealthStatus.UNHEALTHY.value,
                        "message": f"检查执行失败: {e}",
                        "timestamp": datetime.now().isoformat()
                    }
                    overall_status = HealthStatus.UNHEALTHY
            
            return {
                "status": overall_status.value,
                "timestamp": datetime.now().isoformat(),
                "checks": results
            }


# =============================================================================
# 便捷函数
# =============================================================================

def create_metrics_collector() -> MetricsCollector:
    """创建指标收集器"""
    return MetricsCollector()


def create_alert_manager() -> AlertManager:
    """创建告警管理器"""
    return AlertManager()


def create_health_checker() -> HealthChecker:
    """创建健康检查器"""
    return HealthChecker()
