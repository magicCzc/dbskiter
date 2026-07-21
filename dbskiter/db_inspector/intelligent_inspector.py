"""
智能巡检分析器

文件功能：提供智能巡检分析能力，包括：
    - 异常模式识别
    - 根因分析
    - 预测性巡检
    - 智能建议生成
    - 巡检结果关联分析

主要类：
    - AnomalyPatternDetector: 异常模式检测器
    - RootCauseAnalyzer: 根因分析器
    - PredictiveInspector: 预测性巡检器
    - SmartRecommendationEngine: 智能建议引擎
    - CorrelationAnalyzer: 关联分析器
    - IntelligentInspector: 智能巡检器统一入口

作者: Magiczc
创建时间: 2026-04-24
版本: 1.0.0
"""

from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class AnomalyPattern(Enum):
    """异常模式类型"""
    SUDDEN_SPIKE = "sudden_spike"           # 突然飙升
    GRADUAL_INCREASE = "gradual_increase"   # 逐渐增长
    CYCLICAL_ANOMALY = "cyclical_anomaly"   # 周期性异常
    BASELINE_DEVIATION = "baseline_deviation"  # 基线偏离
    CORRELATED_FAILURE = "correlated_failure"  # 关联故障


class RiskPrediction(Enum):
    """风险预测等级"""
    CRITICAL = "critical"      # 严重风险
    HIGH = "high"              # 高风险
    MEDIUM = "medium"          # 中等风险
    LOW = "low"                # 低风险
    NONE = "none"              # 无风险


@dataclass
class AnomalyEvent:
    """异常事件"""
    event_id: str
    pattern: AnomalyPattern
    metric_name: str
    metric_value: float
    threshold: float
    severity: str
    timestamp: datetime
    description: str
    related_metrics: List[str] = field(default_factory=list)


@dataclass
class RootCause:
    """根因分析结果"""
    cause_id: str
    category: str
    description: str
    confidence: float  # 0-100
    evidence: List[str]
    suggested_actions: List[str]
    impact_scope: List[str]


@dataclass
class RiskForecast:
    """风险预测"""
    forecast_id: str
    risk_type: str
    prediction: RiskPrediction
    probability: float  # 0-100
    time_horizon: str  # 24h, 7d, 30d
    affected_components: List[str]
    mitigation_suggestions: List[str]


@dataclass
class SmartRecommendation:
    """智能建议"""
    recommendation_id: str
    category: str
    priority: int  # 1-10
    title: str
    description: str
    implementation_steps: List[str]
    expected_benefit: str
    risk_if_not_addressed: str
    estimated_effort: str


@dataclass
class CorrelationInsight:
    """关联洞察"""
    insight_id: str
    primary_metric: str
    correlated_metrics: List[Tuple[str, float]]  # (metric, correlation_coefficient)
    relationship_type: str  # positive, negative, causal
    strength: str  # strong, moderate, weak
    explanation: str


class AnomalyPatternDetector:
    """
    异常模式检测器

    功能：
    1. 检测突然飙升模式
    2. 检测逐渐增长趋势
    3. 检测周期性异常
    4. 检测基线偏离

    使用示例：
        >>> detector = AnomalyPatternDetector()
        >>> events = detector.detect_patterns(metrics_history)
    """

    def __init__(self):
        """初始化异常模式检测器"""
        self.detection_rules = {
            AnomalyPattern.SUDDEN_SPIKE: self._detect_sudden_spike,
            AnomalyPattern.GRADUAL_INCREASE: self._detect_gradual_increase,
            AnomalyPattern.CYCLICAL_ANOMALY: self._detect_cyclical_anomaly,
            AnomalyPattern.BASELINE_DEVIATION: self._detect_baseline_deviation,
        }

    def detect_patterns(
        self,
        metrics: Dict[str, List[Dict[str, Any]]],
        thresholds: Optional[Dict[str, float]] = None
    ) -> List[AnomalyEvent]:
        """
        检测异常模式

        参数:
            metrics: 指标历史数据 {metric_name: [{timestamp, value}, ...]}
            thresholds: 阈值配置 {metric_name: threshold}

        返回:
            List[AnomalyEvent]: 异常事件列表
        """
        events = []

        if not metrics:
            return events

        for metric_name, data_points in metrics.items():
            if not data_points or len(data_points) < 3:
                continue

            threshold = thresholds.get(metric_name, 0) if thresholds else 0

            for pattern_type, detector in self.detection_rules.items():
                try:
                    event = detector(metric_name, data_points, threshold)
                    if event:
                        events.append(event)
                except Exception as e:
                    logger.warning(f"检测模式 {pattern_type} 失败: {e}")

        return events

    def _detect_sudden_spike(
        self,
        metric_name: str,
        data_points: List[Dict],
        threshold: float
    ) -> Optional[AnomalyEvent]:
        """检测突然飙升"""
        if len(data_points) < 2:
            return None

        # 计算最近两个点的变化率
        recent = data_points[-1]['value']
        previous = data_points[-2]['value']

        if previous == 0:
            return None

        change_rate = (recent - previous) / previous

        # 变化率超过100%视为突然飙升
        if change_rate > 1.0:
            return AnomalyEvent(
                event_id=f"spike_{metric_name}_{datetime.now().timestamp()}",
                pattern=AnomalyPattern.SUDDEN_SPIKE,
                metric_name=metric_name,
                metric_value=recent,
                threshold=previous * 2,
                severity="HIGH",
                timestamp=datetime.now(),
                description=f"{metric_name}突然飙升{change_rate*100:.1f}%",
                related_metrics=[]
            )

        return None

    def _detect_gradual_increase(
        self,
        metric_name: str,
        data_points: List[Dict],
        threshold: float
    ) -> Optional[AnomalyEvent]:
        """检测逐渐增长"""
        if len(data_points) < 5:
            return None

        # 计算趋势线
        values = [dp['value'] for dp in data_points[-5:]]
        first_avg = sum(values[:2]) / 2
        last_avg = sum(values[-2:]) / 2

        if first_avg == 0:
            return None

        growth_rate = (last_avg - first_avg) / first_avg

        # 5个周期内增长超过50%视为逐渐增长
        if growth_rate > 0.5:
            return AnomalyEvent(
                event_id=f"growth_{metric_name}_{datetime.now().timestamp()}",
                pattern=AnomalyPattern.GRADUAL_INCREASE,
                metric_name=metric_name,
                metric_value=values[-1],
                threshold=first_avg * 1.5,
                severity="MEDIUM",
                timestamp=datetime.now(),
                description=f"{metric_name}持续增长{growth_rate*100:.1f}%",
                related_metrics=[]
            )

        return None

    def _detect_cyclical_anomaly(
        self,
        metric_name: str,
        data_points: List[Dict],
        threshold: float
    ) -> Optional[AnomalyEvent]:
        """检测周期性异常"""
        if len(data_points) < 10:
            return None

        # 简单检测：检查是否有规律的峰值
        values = [dp['value'] for dp in data_points]
        mean_val = sum(values) / len(values)

        # 检测偏离均值超过2倍标准差的点
        variance = sum((v - mean_val) ** 2 for v in values) / len(values)
        std_dev = variance ** 0.5

        recent_values = values[-3:]
        anomalies = [v for v in recent_values if abs(v - mean_val) > 2 * std_dev]

        if len(anomalies) >= 2:
            return AnomalyEvent(
                event_id=f"cyclical_{metric_name}_{datetime.now().timestamp()}",
                pattern=AnomalyPattern.CYCLICAL_ANOMALY,
                metric_name=metric_name,
                metric_value=recent_values[-1],
                threshold=mean_val + 2 * std_dev,
                severity="MEDIUM",
                timestamp=datetime.now(),
                description=f"{metric_name}出现周期性异常波动",
                related_metrics=[]
            )

        return None

    def _detect_baseline_deviation(
        self,
        metric_name: str,
        data_points: List[Dict],
        threshold: float
    ) -> Optional[AnomalyEvent]:
        """检测基线偏离"""
        if not threshold or len(data_points) < 3:
            return None

        recent_value = data_points[-1]['value']

        if recent_value > threshold:
            deviation_percent = (recent_value - threshold) / threshold * 100

            return AnomalyEvent(
                event_id=f"baseline_{metric_name}_{datetime.now().timestamp()}",
                pattern=AnomalyPattern.BASELINE_DEVIATION,
                metric_name=metric_name,
                metric_value=recent_value,
                threshold=threshold,
                severity="HIGH" if deviation_percent > 50 else "MEDIUM",
                timestamp=datetime.now(),
                description=f"{metric_name}偏离基线{deviation_percent:.1f}%",
                related_metrics=[]
            )

        return None


class RootCauseAnalyzer:
    """
    根因分析器

    功能：
    1. 基于规则分析根因
    2. 关联多个异常事件
    3. 生成解决建议

    使用示例：
        >>> analyzer = RootCauseAnalyzer()
        >>> causes = analyzer.analyze(anomaly_events, inspection_results)
    """

    def __init__(self):
        """初始化根因分析器"""
        self.cause_rules = [
            self._analyze_cpu_spike,
            self._analyze_memory_growth,
            self._analyze_slow_queries,
            self._analyze_connection_issues,
        ]

    def analyze(
        self,
        anomaly_events: List[AnomalyEvent],
        inspection_results: Dict[str, Any]
    ) -> List[RootCause]:
        """
        分析根因

        参数:
            anomaly_events: 异常事件列表
            inspection_results: 巡检结果

        返回:
            List[RootCause]: 根因分析结果
        """
        causes = []

        for rule in self.cause_rules:
            try:
                cause = rule(anomaly_events, inspection_results)
                if cause:
                    causes.append(cause)
            except Exception as e:
                logger.warning(f"根因规则 {rule.__name__} 失败: {e}")

        return causes

    def _analyze_cpu_spike(
        self,
        events: List[AnomalyEvent],
        results: Dict[str, Any]
    ) -> Optional[RootCause]:
        """分析CPU飙升根因"""
        cpu_events = [e for e in events if 'cpu' in e.metric_name.lower()]

        if not cpu_events:
            return None

        # 查找相关指标
        evidence = []
        suggested_actions = []

        # 检查是否有慢查询
        slow_queries = results.get('performance', {}).get('slow_queries', [])
        if slow_queries:
            evidence.append(f"发现{len(slow_queries)}个慢查询")
            suggested_actions.append("优化慢查询")

        # 检查连接数
        connections = results.get('performance', {}).get('connections', {})
        if connections.get('current', 0) > connections.get('max', 100) * 0.8:
            evidence.append("连接数接近上限")
            suggested_actions.append("增加连接池大小或优化连接使用")

        if evidence:
            return RootCause(
                cause_id=f"cpu_spike_{datetime.now().timestamp()}",
                category="PERFORMANCE",
                description="CPU使用率飙升",
                confidence=80.0,
                evidence=evidence,
                suggested_actions=suggested_actions,
                impact_scope=["查询性能", "响应时间"]
            )

        return None

    def _analyze_memory_growth(
        self,
        events: List[AnomalyEvent],
        results: Dict[str, Any]
    ) -> Optional[RootCause]:
        """分析内存增长根因"""
        memory_events = [e for e in events if 'memory' in e.metric_name.lower()]

        if not memory_events:
            return None

        evidence = []
        suggested_actions = []

        # 检查缓存配置
        cache_config = results.get('configuration', {}).get('cache_settings', {})
        if cache_config.get('buffer_pool_size', 0) > 0:
            evidence.append(f"缓冲池大小: {cache_config['buffer_pool_size']}MB")

        # 检查长连接
        long_connections = results.get('performance', {}).get('long_connections', [])
        if long_connections:
            evidence.append(f"发现{len(long_connections)}个长连接")
            suggested_actions.append("检查并关闭不必要的长连接")

        if evidence:
            return RootCause(
                cause_id=f"memory_growth_{datetime.now().timestamp()}",
                category="RESOURCE",
                description="内存使用持续增长",
                confidence=75.0,
                evidence=evidence,
                suggested_actions=suggested_actions + ["优化内存配置", "检查内存泄漏"],
                impact_scope=["系统稳定性", "OOM风险"]
            )

        return None

    def _analyze_slow_queries(
        self,
        events: List[AnomalyEvent],
        results: Dict[str, Any]
    ) -> Optional[RootCause]:
        """分析慢查询根因"""
        slow_queries = results.get('performance', {}).get('slow_queries', [])

        if not slow_queries:
            return None

        evidence = []
        suggested_actions = []

        # 分析慢查询类型
        full_scan_queries = [q for q in slow_queries if 'ALL' in q.get('explain', '')]
        if full_scan_queries:
            evidence.append(f"{len(full_scan_queries)}个查询存在全表扫描")
            suggested_actions.append("为相关表添加索引")

        join_queries = [q for q in slow_queries if 'JOIN' in q.get('sql', '')]
        if join_queries:
            evidence.append(f"{len(join_queries)}个慢查询涉及JOIN操作")
            suggested_actions.append("优化JOIN条件和顺序")

        if evidence:
            return RootCause(
                cause_id=f"slow_query_{datetime.now().timestamp()}",
                category="QUERY",
                description="慢查询影响性能",
                confidence=85.0,
                evidence=evidence,
                suggested_actions=suggested_actions,
                impact_scope=["查询性能", "用户体验"]
            )

        return None

    def _analyze_connection_issues(
        self,
        events: List[AnomalyEvent],
        results: Dict[str, Any]
    ) -> Optional[RootCause]:
        """分析连接问题根因"""
        connections = results.get('performance', {}).get('connections', {})

        if connections.get('current', 0) < connections.get('max', 100) * 0.5:
            return None

        evidence = []
        suggested_actions = []

        connection_ratio = connections.get('current', 0) / connections.get('max', 100)

        if connection_ratio > 0.9:
            evidence.append(f"连接数使用率: {connection_ratio*100:.1f}%")
            suggested_actions.append("立即增加最大连接数限制")
        elif connection_ratio > 0.7:
            evidence.append(f"连接数使用率: {connection_ratio*100:.1f}%")
            suggested_actions.append("监控连接数增长趋势")

        # 检查空闲连接
        idle_connections = results.get('performance', {}).get('idle_connections', 0)
        if idle_connections > connections.get('current', 0) * 0.5:
            evidence.append(f"空闲连接占比: {idle_connections/connections['current']*100:.1f}%")
            suggested_actions.append("优化连接池配置，减少空闲连接")

        if evidence:
            return RootCause(
                cause_id=f"connection_{datetime.now().timestamp()}",
                category="CONNECTION",
                description="数据库连接数接近上限",
                confidence=70.0,
                evidence=evidence,
                suggested_actions=suggested_actions,
                impact_scope=["新连接建立", "应用可用性"]
            )

        return None


class PredictiveInspector:
    """
    预测性巡检器

    功能：
    1. 基于历史趋势预测未来风险
    2. 容量预测
    3. 性能退化预测

    使用示例：
        >>> predictor = PredictiveInspector()
        >>> forecasts = predictor.predict_risks(metrics_history, time_horizon="7d")
    """

    def __init__(self):
        """初始化预测性巡检器"""
        pass

    def predict_risks(
        self,
        metrics_history: Dict[str, List[Dict[str, Any]]],
        time_horizon: str = "7d"
    ) -> List[RiskForecast]:
        """
        预测风险

        参数:
            metrics_history: 指标历史数据
            time_horizon: 预测时间范围 (24h, 7d, 30d)

        返回:
            List[RiskForecast]: 风险预测列表
        """
        forecasts = []

        # 容量风险预测
        capacity_forecast = self._predict_capacity_risk(metrics_history, time_horizon)
        if capacity_forecast:
            forecasts.append(capacity_forecast)

        # 性能退化预测
        performance_forecast = self._predict_performance_degradation(metrics_history, time_horizon)
        if performance_forecast:
            forecasts.append(performance_forecast)

        return forecasts

    def _predict_capacity_risk(
        self,
        metrics: Dict[str, List[Dict]],
        time_horizon: str
    ) -> Optional[RiskForecast]:
        """预测容量风险"""
        # 检查存储增长趋势
        storage_metrics = metrics.get('storage_usage', [])
        if len(storage_metrics) < 7:
            return None

        # 计算每日增长率
        recent_values = [m['value'] for m in storage_metrics[-7:]]
        if len(recent_values) < 2:
            return None

        daily_growth = (recent_values[-1] - recent_values[0]) / len(recent_values)
        current_usage = recent_values[-1]

        # 预测达到阈值的时间
        threshold = 90.0  # 90%为警告阈值
        if daily_growth > 0 and current_usage < threshold:
            days_to_threshold = (threshold - current_usage) / daily_growth

            if days_to_threshold < 30:
                return RiskForecast(
                    forecast_id=f"capacity_{datetime.now().timestamp()}",
                    risk_type="CAPACITY",
                    prediction=RiskPrediction.HIGH if days_to_threshold < 7 else RiskPrediction.MEDIUM,
                    probability=min(90, 100 - days_to_threshold),
                    time_horizon=time_horizon,
                    affected_components=["存储空间"],
                    mitigation_suggestions=[
                        f"预计{days_to_threshold:.0f}天后存储达到{threshold}%",
                        "清理无用数据",
                        "考虑扩容"
                    ]
                )

        return None

    def _predict_performance_degradation(
        self,
        metrics: Dict[str, List[Dict]],
        time_horizon: str
    ) -> Optional[RiskForecast]:
        """预测性能退化"""
        # 检查查询响应时间趋势
        response_metrics = metrics.get('avg_response_time', [])
        if len(response_metrics) < 7:
            return None

        recent_values = [m['value'] for m in response_metrics[-7:]]
        if len(recent_values) < 2:
            return None

        # 检测上升趋势
        first_avg = sum(recent_values[:3]) / 3
        last_avg = sum(recent_values[-3:]) / 3

        if first_avg > 0 and last_avg > first_avg * 1.3:  # 增长超过30%
            degradation_percent = (last_avg - first_avg) / first_avg * 100

            return RiskForecast(
                forecast_id=f"performance_{datetime.now().timestamp()}",
                risk_type="PERFORMANCE",
                prediction=RiskPrediction.MEDIUM,
                probability=70.0,
                time_horizon=time_horizon,
                affected_components=["查询性能", "用户体验"],
                mitigation_suggestions=[
                    f"响应时间已增长{degradation_percent:.1f}%",
                    "检查慢查询日志",
                    "优化热点查询"
                ]
            )

        return None


class SmartRecommendationEngine:
    """
    智能建议引擎

    功能：
    1. 基于巡检结果生成建议
    2. 优先级排序
    3. 实施步骤生成

    使用示例：
        >>> engine = SmartRecommendationEngine()
        >>> recommendations = engine.generate_recommendations(inspection_results, root_causes)
    """

    def __init__(self):
        """初始化智能建议引擎"""
        self.recommendation_templates = {
            "CPU_HIGH": {
                "category": "PERFORMANCE",
                "title": "优化CPU使用",
                "description": "数据库CPU使用率过高，需要优化",
                "steps": ["分析慢查询", "优化查询语句", "考虑读写分离"],
                "benefit": "降低CPU负载，提升响应速度",
                "risk": "系统响应变慢，影响用户体验"
            },
            "MEMORY_HIGH": {
                "category": "RESOURCE",
                "title": "优化内存配置",
                "description": "内存使用接近上限，需要优化配置",
                "steps": ["调整缓冲池大小", "检查长连接", "优化查询缓存"],
                "benefit": "避免OOM，提升稳定性",
                "risk": "系统OOM，导致服务中断"
            },
            "STORAGE_FULL": {
                "category": "CAPACITY",
                "title": "扩容存储空间",
                "description": "存储空间即将耗尽，需要扩容",
                "steps": ["清理无用数据", "归档历史数据", "申请扩容"],
                "benefit": "确保数据正常写入",
                "risk": "无法写入新数据，服务中断"
            },
            "SLOW_QUERY": {
                "category": "QUERY",
                "title": "优化慢查询",
                "description": "存在慢查询影响性能",
                "steps": ["分析执行计划", "添加索引", "重写查询"],
                "benefit": "提升查询性能",
                "risk": "持续影响用户体验"
            },
            "CONNECTION_HIGH": {
                "category": "CONNECTION",
                "title": "优化连接管理",
                "description": "连接数接近上限",
                "steps": ["增加连接限制", "优化连接池", "检查连接泄漏"],
                "benefit": "支持更多并发连接",
                "risk": "新连接无法建立"
            },
        }

    def generate_recommendations(
        self,
        inspection_results: Dict[str, Any],
        root_causes: List[RootCause]
    ) -> List[SmartRecommendation]:
        """
        生成智能建议

        参数:
            inspection_results: 巡检结果
            root_causes: 根因分析结果

        返回:
            List[SmartRecommendation]: 建议列表
        """
        recommendations = []

        # 基于根因生成建议
        for cause in root_causes:
            rec = self._create_recommendation_from_cause(cause)
            if rec:
                recommendations.append(rec)

        # 基于巡检结果生成建议
        recs_from_inspection = self._create_recommendations_from_inspection(inspection_results)
        recommendations.extend(recs_from_inspection)

        # 按优先级排序
        recommendations.sort(key=lambda r: r.priority, reverse=True)

        return recommendations

    def _create_recommendation_from_cause(
        self,
        cause: RootCause
    ) -> Optional[SmartRecommendation]:
        """基于根因创建建议"""
        template_key = None

        if "CPU" in cause.description:
            template_key = "CPU_HIGH"
        elif "内存" in cause.description or "memory" in cause.description.lower():
            template_key = "MEMORY_HIGH"
        elif "慢查询" in cause.description:
            template_key = "SLOW_QUERY"
        elif "连接" in cause.description:
            template_key = "CONNECTION_HIGH"

        if not template_key or template_key not in self.recommendation_templates:
            return None

        template = self.recommendation_templates[template_key]

        return SmartRecommendation(
            recommendation_id=f"rec_{cause.cause_id}",
            category=template["category"],
            priority=int(cause.confidence / 10),
            title=template["title"],
            description=template["description"],
            implementation_steps=template["steps"],
            expected_benefit=template["benefit"],
            risk_if_not_addressed=template["risk"],
            estimated_effort="2-4小时"
        )

    def _create_recommendations_from_inspection(
        self,
        results: Dict[str, Any]
    ) -> List[SmartRecommendation]:
        """基于巡检结果创建建议"""
        recommendations = []

        # 检查存储
        storage = results.get('storage', {})
        if storage.get('usage_percent', 0) > 80:
            template = self.recommendation_templates["STORAGE_FULL"]
            recommendations.append(SmartRecommendation(
                recommendation_id=f"rec_storage_{datetime.now().timestamp()}",
                category=template["category"],
                priority=8 if storage['usage_percent'] > 90 else 6,
                title=template["title"],
                description=f"当前存储使用率: {storage['usage_percent']}%",
                implementation_steps=template["steps"],
                expected_benefit=template["benefit"],
                risk_if_not_addressed=template["risk"],
                estimated_effort="1-2天"
            ))

        return recommendations


class CorrelationAnalyzer:
    """
    关联分析器

    功能：
    1. 分析指标间关联性
    2. 识别因果链
    3. 发现隐藏模式

    使用示例：
        >>> analyzer = CorrelationAnalyzer()
        >>> insights = analyzer.analyze_correlations(metrics_data)
    """

    def __init__(self):
        """初始化关联分析器"""
        pass

    def analyze_correlations(
        self,
        metrics_data: Dict[str, List[Dict[str, Any]]]
    ) -> List[CorrelationInsight]:
        """
        分析指标关联

        参数:
            metrics_data: 多指标数据

        返回:
            List[CorrelationInsight]: 关联洞察列表
        """
        insights = []

        metric_names = list(metrics_data.keys())

        for i, primary in enumerate(metric_names):
            for secondary in metric_names[i+1:]:
                correlation = self._calculate_correlation(
                    metrics_data[primary],
                    metrics_data[secondary]
                )

                if abs(correlation) > 0.5:  # 相关系数阈值
                    insight = CorrelationInsight(
                        insight_id=f"corr_{primary}_{secondary}_{datetime.now().timestamp()}",
                        primary_metric=primary,
                        correlated_metrics=[(secondary, correlation)],
                        relationship_type="positive" if correlation > 0 else "negative",
                        strength="strong" if abs(correlation) > 0.8 else "moderate",
                        explanation=f"{primary}与{secondary}存在{'正' if correlation > 0 else '负'}相关关系"
                    )
                    insights.append(insight)

        return insights

    def _calculate_correlation(
        self,
        data1: List[Dict],
        data2: List[Dict]
    ) -> float:
        """计算相关系数"""
        # 简化实现：使用皮尔逊相关系数
        values1 = [d['value'] for d in data1[-10:]]  # 取最近10个值
        values2 = [d['value'] for d in data2[-10:]]

        if len(values1) != len(values2) or len(values1) < 2:
            return 0.0

        n = len(values1)
        mean1 = sum(values1) / n
        mean2 = sum(values2) / n

        numerator = sum((values1[i] - mean1) * (values2[i] - mean2) for i in range(n))
        denominator = (sum((v - mean1) ** 2 for v in values1) * sum((v - mean2) ** 2 for v in values2)) ** 0.5

        if denominator == 0:
            return 0.0

        return numerator / denominator


class IntelligentInspector:
    """
    智能巡检器 - 统一入口

    整合异常检测、根因分析、风险预测、智能建议、关联分析功能

    使用示例:
        >>> inspector = IntelligentInspector()
        >>> result = inspector.perform_intelligent_inspection(metrics, inspection_results)
        >>> print(result['root_causes'])
        >>> print(result['recommendations'])
    """

    def __init__(self):
        """初始化智能巡检器"""
        self.anomaly_detector = AnomalyPatternDetector()
        self.root_cause_analyzer = RootCauseAnalyzer()
        self.predictive_inspector = PredictiveInspector()
        self.recommendation_engine = SmartRecommendationEngine()
        self.correlation_analyzer = CorrelationAnalyzer()

    def perform_intelligent_inspection(
        self,
        metrics_history: Dict[str, List[Dict[str, Any]]],
        inspection_results: Dict[str, Any],
        thresholds: Optional[Dict[str, float]] = None
    ) -> Dict[str, Any]:
        """
        执行智能巡检

        参数:
            metrics_history: 指标历史数据
            inspection_results: 基础巡检结果
            thresholds: 阈值配置

        返回:
            Dict: 智能巡检结果
        """
        result = {
            "inspection_time": datetime.now().isoformat(),
            "anomaly_events": [],
            "root_causes": [],
            "risk_forecasts": [],
            "recommendations": [],
            "correlation_insights": [],
            "summary": {}
        }

        # 1. 异常模式检测
        result["anomaly_events"] = self.anomaly_detector.detect_patterns(
            metrics_history, thresholds
        )

        # 2. 根因分析
        if result["anomaly_events"]:
            result["root_causes"] = self.root_cause_analyzer.analyze(
                result["anomaly_events"], inspection_results
            )

        # 3. 风险预测
        result["risk_forecasts"] = self.predictive_inspector.predict_risks(
            metrics_history
        )

        # 4. 生成智能建议
        result["recommendations"] = self.recommendation_engine.generate_recommendations(
            inspection_results, result["root_causes"]
        )

        # 5. 关联分析
        if len(metrics_history) >= 2:
            result["correlation_insights"] = self.correlation_analyzer.analyze_correlations(
                metrics_history
            )

        # 6. 生成摘要
        result["summary"] = self._generate_summary(result)

        return result

    def _generate_summary(self, result: Dict) -> Dict[str, Any]:
        """生成摘要"""
        return {
            "total_anomalies": len(result["anomaly_events"]),
            "root_causes_identified": len(result["root_causes"]),
            "risks_predicted": len(result["risk_forecasts"]),
            "recommendations": len(result["recommendations"]),
            "correlations_found": len(result["correlation_insights"]),
            "overall_status": self._determine_overall_status(result)
        }

    def _determine_overall_status(self, result: Dict) -> str:
        """确定整体状态"""
        critical_anomalies = sum(
            1 for e in result["anomaly_events"]
            if e.severity == "CRITICAL"
        )
        high_risks = sum(
            1 for r in result["risk_forecasts"]
            if r.prediction in [RiskPrediction.CRITICAL, RiskPrediction.HIGH]
        )

        if critical_anomalies > 0 or high_risks > 0:
            return "CRITICAL"
        elif len(result["anomaly_events"]) > 2:
            return "WARNING"
        else:
            return "HEALTHY"

    def get_inspection_summary_text(self, result: Dict) -> str:
        """
        获取巡检摘要文本

        参数:
            result: 智能巡检结果

        返回:
            str: 摘要文本
        """
        lines = ["智能巡检报告", "=" * 40]

        summary = result.get("summary", {})
        lines.append(f"整体状态: {summary.get('overall_status', 'UNKNOWN')}")
        lines.append(f"异常事件: {summary.get('total_anomalies', 0)}个")
        lines.append(f"根因分析: {summary.get('root_causes_identified', 0)}个")
        lines.append(f"风险预测: {summary.get('risks_predicted', 0)}个")
        lines.append(f"优化建议: {summary.get('recommendations', 0)}个")

        if result.get("root_causes"):
            lines.append("\n主要根因:")
            for cause in result["root_causes"][:3]:
                lines.append(f"  - {cause.description} (置信度: {cause.confidence}%)")

        if result.get("recommendations"):
            lines.append("\n优先建议:")
            for rec in result["recommendations"][:3]:
                lines.append(f"  - [{rec.category}] {rec.title} (优先级: {rec.priority})")

        return "\n".join(lines)
