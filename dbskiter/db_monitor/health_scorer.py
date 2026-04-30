"""
健康评分器模块

文件功能：提供基于权重的数据库健康评分算法
主要类：HealthScorer - 健康评分器

设计原则：
    1. 权重可配置：支持不同数据库类型的权重配置
    2. 阈值分层：支持警告、严重等不同级别的阈值
    3. 评分算法：基于权重和偏离度的综合评分
    4. 可扩展性：支持自定义评分规则和指标

评分算法：
    基础分：100分
    扣分 = 权重 × 偏离度 × 严重程度系数
    最终分 = max(60, 100 - 总扣分)

作者：AI Assistant
创建时间：2026-04-29
"""

from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, field
from enum import Enum
import logging

from dbskiter.db_monitor.models import MetricType, HealthStatus

logger = logging.getLogger(__name__)


class SeverityLevel(Enum):
    """严重程度级别"""
    INFO = "info"           # 信息提示，不扣分
    WARNING = "warning"     # 警告，轻微扣分
    CRITICAL = "critical"   # 严重，大幅扣分


@dataclass
class MetricThreshold:
    """
    指标阈值配置
    
    属性:
        warning: 警告阈值
        critical: 严重阈值
        direction: 阈值方向（above/below）
    """
    warning: float
    critical: float
    direction: str = "above"  # above: 超过阈值告警, below: 低于阈值告警
    
    def check(self, value: float) -> tuple[SeverityLevel, float]:
        """
        检查指标值是否超过阈值
        
        参数:
            value: 指标值
            
        返回:
            tuple: (严重程度, 偏离度)
        """
        if self.direction == "above":
            if value >= self.critical:
                deviation = (value - self.critical) / self.critical if self.critical > 0 else 1.0
                return SeverityLevel.CRITICAL, min(deviation, 2.0)
            elif value >= self.warning:
                deviation = (value - self.warning) / self.warning if self.warning > 0 else 0.5
                return SeverityLevel.WARNING, min(deviation, 1.0)
        else:  # below
            if value <= self.critical:
                deviation = (self.critical - value) / self.critical if self.critical > 0 else 1.0
                return SeverityLevel.CRITICAL, min(deviation, 2.0)
            elif value <= self.warning:
                deviation = (self.warning - value) / self.warning if self.warning > 0 else 0.5
                return SeverityLevel.WARNING, min(deviation, 1.0)
        
        return SeverityLevel.INFO, 0.0


@dataclass
class MetricWeight:
    """
    指标权重配置
    
    属性:
        metric_type: 指标类型
        weight: 权重（0-100）
        threshold: 阈值配置
        description: 指标描述
    """
    metric_type: MetricType
    weight: float
    threshold: MetricThreshold
    description: str = ""


@dataclass
class DatabaseTypeConfig:
    """
    数据库类型配置
    
    属性:
        db_type: 数据库类型（oracle/mysql/postgresql）
        metrics: 指标权重列表
        base_score: 基础分数
        min_score: 最低分数
    """
    db_type: str
    metrics: Dict[MetricType, MetricWeight] = field(default_factory=dict)
    base_score: float = 100.0
    min_score: float = 60.0
    
    def get_metric_weight(self, metric_type: MetricType) -> Optional[MetricWeight]:
        """获取指标权重配置"""
        return self.metrics.get(metric_type)


class HealthScorer:
    """
    健康评分器
    
    提供基于权重的数据库健康评分功能
    """
    
    # 默认配置
    DEFAULT_CONFIGS: Dict[str, DatabaseTypeConfig] = {}
    
    def __init__(self):
        """初始化评分器"""
        self._init_default_configs()
    
    def _init_default_configs(self):
        """初始化默认配置"""
        # Oracle配置
        oracle_config = DatabaseTypeConfig(
            db_type="oracle",
            metrics={
                MetricType.CONNECTIONS_ACTIVE: MetricWeight(
                    metric_type=MetricType.CONNECTIONS_ACTIVE,
                    weight=15.0,
                    threshold=MetricThreshold(
                        warning=60.0,  # 连接数超过60%警告
                        critical=80.0  # 超过80%严重
                    ),
                    description="活跃连接数使用率"
                ),
                MetricType.BUFFER_HIT_RATIO: MetricWeight(
                    metric_type=MetricType.BUFFER_HIT_RATIO,
                    weight=20.0,
                    threshold=MetricThreshold(
                        warning=90.0,  # 低于90%警告
                        critical=85.0,  # 低于85%严重
                        direction="below"
                    ),
                    description="缓冲命中率"
                ),
                MetricType.SLOW_QUERIES: MetricWeight(
                    metric_type=MetricType.SLOW_QUERIES,
                    weight=10.0,
                    threshold=MetricThreshold(
                        warning=10.0,  # 超过10个慢查询警告
                        critical=50.0  # 超过50个严重
                    ),
                    description="慢查询数量"
                ),
                MetricType.LOCK_WAITS: MetricWeight(
                    metric_type=MetricType.LOCK_WAITS,
                    weight=15.0,
                    threshold=MetricThreshold(
                        warning=5.0,  # 超过5次/秒警告
                        critical=20.0  # 超过20次/秒严重
                    ),
                    description="锁等待频率"
                ),
                MetricType.DEADLOCKS: MetricWeight(
                    metric_type=MetricType.DEADLOCKS,
                    weight=25.0,
                    threshold=MetricThreshold(
                        warning=0.1,  # 超过0.1次/秒警告
                        critical=1.0  # 超过1次/秒严重
                    ),
                    description="死锁频率"
                ),
                MetricType.QUERY_TIME_AVG: MetricWeight(
                    metric_type=MetricType.QUERY_TIME_AVG,
                    weight=10.0,
                    threshold=MetricThreshold(
                        warning=1.0,  # 超过1秒警告
                        critical=5.0  # 超过5秒严重
                    ),
                    description="平均查询时间"
                ),
                MetricType.CPU_USAGE: MetricWeight(
                    metric_type=MetricType.CPU_USAGE,
                    weight=5.0,
                    threshold=MetricThreshold(
                        warning=70.0,  # 超过70%警告
                        critical=90.0  # 超过90%严重
                    ),
                    description="CPU使用率"
                ),
            }
        )
        
        # MySQL配置
        mysql_config = DatabaseTypeConfig(
            db_type="mysql",
            metrics={
                MetricType.CONNECTIONS_ACTIVE: MetricWeight(
                    metric_type=MetricType.CONNECTIONS_ACTIVE,
                    weight=15.0,
                    threshold=MetricThreshold(
                        warning=60.0,
                        critical=80.0
                    ),
                    description="活跃连接数使用率"
                ),
                MetricType.BUFFER_HIT_RATIO: MetricWeight(
                    metric_type=MetricType.BUFFER_HIT_RATIO,
                    weight=20.0,
                    threshold=MetricThreshold(
                        warning=95.0,  # MySQL要求更高
                        critical=90.0,
                        direction="below"
                    ),
                    description="缓冲命中率"
                ),
                MetricType.SLOW_QUERIES: MetricWeight(
                    metric_type=MetricType.SLOW_QUERIES,
                    weight=10.0,
                    threshold=MetricThreshold(
                        warning=20.0,
                        critical=100.0
                    ),
                    description="慢查询数量"
                ),
                MetricType.LOCK_WAITS: MetricWeight(
                    metric_type=MetricType.LOCK_WAITS,
                    weight=15.0,
                    threshold=MetricThreshold(
                        warning=10.0,
                        critical=50.0
                    ),
                    description="锁等待频率"
                ),
                MetricType.DEADLOCKS: MetricWeight(
                    metric_type=MetricType.DEADLOCKS,
                    weight=25.0,
                    threshold=MetricThreshold(
                        warning=0.1,
                        critical=1.0
                    ),
                    description="死锁频率"
                ),
                MetricType.QUERY_TIME_AVG: MetricWeight(
                    metric_type=MetricType.QUERY_TIME_AVG,
                    weight=10.0,
                    threshold=MetricThreshold(
                        warning=1.0,
                        critical=5.0
                    ),
                    description="平均查询时间"
                ),
                MetricType.CPU_USAGE: MetricWeight(
                    metric_type=MetricType.CPU_USAGE,
                    weight=5.0,
                    threshold=MetricThreshold(
                        warning=70.0,
                        critical=90.0
                    ),
                    description="CPU使用率"
                ),
            }
        )
        
        self.DEFAULT_CONFIGS["oracle"] = oracle_config
        self.DEFAULT_CONFIGS["mysql"] = mysql_config
        self.DEFAULT_CONFIGS["postgresql"] = mysql_config  # PostgreSQL使用类似MySQL的配置
    
    def get_config(self, db_type: str) -> DatabaseTypeConfig:
        """
        获取数据库类型配置
        
        参数:
            db_type: 数据库类型
            
        返回:
            DatabaseTypeConfig: 数据库配置
        """
        db_type_lower = db_type.lower()
        
        # 处理oracle+jdbc等情况
        if "oracle" in db_type_lower:
            return self.DEFAULT_CONFIGS["oracle"]
        elif "mysql" in db_type_lower:
            return self.DEFAULT_CONFIGS["mysql"]
        elif "postgresql" in db_type_lower:
            return self.DEFAULT_CONFIGS["postgresql"]
        
        # 默认返回MySQL配置
        logger.warning(f"未知的数据库类型: {db_type}，使用默认配置")
        return self.DEFAULT_CONFIGS["mysql"]
    
    def calculate_score(
        self,
        metrics: Dict[MetricType, float],
        db_type: str,
        max_connections: float = 2000.0
    ) -> tuple[float, HealthStatus, List[str]]:
        """
        计算健康评分
        
        评分算法：
            基础分：100分
            扣分 = 权重 × 偏离度 × 严重程度系数
            严重程度系数：WARNING=1.0, CRITICAL=2.0
            最终分 = max(最低分, 100 - 总扣分)
        
        参数:
            metrics: 指标值字典
            db_type: 数据库类型
            max_connections: 最大连接数（用于计算连接百分比）
            
        返回:
            tuple: (分数, 状态, 问题列表)
        """
        config = self.get_config(db_type)
        base_score = config.base_score
        min_score = config.min_score
        
        total_deduction = 0.0
        issues = []
        
        for metric_type, value in metrics.items():
            metric_config = config.get_metric_weight(metric_type)
            if not metric_config:
                continue
            
            # 特殊处理连接数指标
            if metric_type == MetricType.CONNECTIONS_ACTIVE:
                value = (value / max_connections * 100) if max_connections > 0 else 0
            
            # 检查阈值
            severity, deviation = metric_config.threshold.check(value)
            
            if severity == SeverityLevel.INFO:
                continue
            
            # 计算扣分
            # 严重程度系数：WARNING=1.0, CRITICAL=2.0
            severity_factor = 2.0 if severity == SeverityLevel.CRITICAL else 1.0
            deduction = metric_config.weight * deviation * severity_factor
            
            total_deduction += deduction
            
            # 记录问题
            severity_label = "严重" if severity == SeverityLevel.CRITICAL else "警告"
            issues.append(
                f"{metric_config.description}: {value:.2f} ({severity_label})"
            )
        
        # 计算最终分数
        final_score = max(min_score, base_score - total_deduction)
        
        # 确定状态
        if final_score >= 85:
            status = HealthStatus.HEALTHY
        elif final_score >= 70:
            status = HealthStatus.WARNING
        else:
            status = HealthStatus.CRITICAL
        
        return round(final_score, 1), status, issues
    
    def get_metric_advice(
        self,
        metric_type: MetricType,
        value: float,
        db_type: str
    ) -> Optional[str]:
        """
        获取指标优化建议
        
        参数:
            metric_type: 指标类型
            value: 指标值
            db_type: 数据库类型
            
        返回:
            Optional[str]: 优化建议
        """
        config = self.get_config(db_type)
        metric_config = config.get_metric_weight(metric_type)
        
        if not metric_config:
            return None
        
        severity, _ = metric_config.threshold.check(value)
        
        if severity == SeverityLevel.INFO:
            return None
        
        # 根据指标类型提供建议
        advice_map = {
            MetricType.CONNECTIONS_ACTIVE: "建议检查连接池配置，考虑增加最大连接数或优化连接使用",
            MetricType.BUFFER_HIT_RATIO: "建议增加缓冲池大小或优化SQL查询以减少物理IO",
            MetricType.SLOW_QUERIES: "建议分析慢查询日志，优化慢SQL或添加索引",
            MetricType.LOCK_WAITS: "建议检查锁竞争情况，优化事务设计或调整锁超时时间",
            MetricType.DEADLOCKS: "建议检查事务顺序，确保资源访问顺序一致",
            MetricType.QUERY_TIME_AVG: "建议优化SQL查询性能，检查执行计划",
            MetricType.CPU_USAGE: "建议检查高CPU消耗的SQL，考虑优化或扩容",
        }
        
        return advice_map.get(metric_type)


# 全局评分器实例
_health_scorer: Optional[HealthScorer] = None


def get_health_scorer() -> HealthScorer:
    """
    获取全局健康评分器实例（单例模式）
    
    返回:
        HealthScorer: 健康评分器实例
    """
    global _health_scorer
    if _health_scorer is None:
        _health_scorer = HealthScorer()
    return _health_scorer
