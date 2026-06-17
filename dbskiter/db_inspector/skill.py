"""
db_inspector/skill.py
db_inspector Skill - 数据库实例巡检与报告生成（模块化重构版）

文件功能：提供完整的数据库实例巡检能力，支持MySQL/Oracle/PostgreSQL
主要类：
    - InspectorSkill: 巡检技能统一入口（模块化重构版）

作者：AI Assistant
创建时间：2026-04-22
最后修改：2026-04-23
版本：3.0.0（模块化重构版）
"""

import logging
import uuid
from typing import Dict, Any, List, Optional
from datetime import datetime
from time import time

from dbskiter.shared.unified_connector import UnifiedConnector
from dbskiter.shared.error_handler import create_success_response, create_error_response

from .models import (
    ErrorCode,
    RiskLevel,
    InspectionType,
    InspectionItem,
    InspectionReport,
)
from .utils import (
    HealthScoreCalculator,
    ReportFormatter,
    BaselineManager,
    InspectionAggregator,
)
from .inspectors import get_inspector
from .intelligent_inspector import IntelligentInspector

logger = logging.getLogger(__name__)


class InspectorSkill:
    """
    数据库巡检 Skill（模块化重构版）

    功能：
        1. 实例健康巡检 - 全面检查数据库健康状态
        2. 配置检查 - 检查数据库配置是否合理
        3. 性能检查 - 检查性能指标是否异常
        4. 存储检查 - 检查存储使用情况
        5. 安全检查 - 检查安全相关配置
        6. 报告生成 - 生成多种格式的巡检报告
        7. 基线管理 - 建立和对比性能基线
        8. 趋势分析 - 分析历史趋势变化

    支持的数据库：
        - MySQL
        - Oracle
        - PostgreSQL

    使用示例：
        >>> skill = InspectorSkill(connector)
        >>> result = skill.inspect()
        >>> if result["success"]:
        ...     report = result["data"]
        ...     print(f"健康评分: {report['health_score']}")
        >>> html_result = skill.generate_html_report(report)
    """

    # 健康评分通过阈值
    HEALTH_SCORE_PASS_THRESHOLD = 80.0

    def __init__(self, connector: UnifiedConnector):
        """
        初始化巡检 Skill

        参数:
            connector: UnifiedConnector 实例
        """
        self.connector = connector
        self.dialect = connector.dialect.lower()
        self._inspector = get_inspector(self.dialect, connector)

        # 初始化工具类
        self._score_calculator = HealthScoreCalculator()
        self._baseline_manager = BaselineManager()

        # 初始化智能巡检器
        self._intelligent_inspector = IntelligentInspector()

        logger.info(f"InspectorSkill 初始化完成 (dialect={self.dialect})")

    def inspect(
        self,
        inspection_types: Optional[List[InspectionType]] = None
    ) -> Dict[str, Any]:
        """
        执行完整巡检

        参数:
            inspection_types: 指定巡检类型，None表示全部

        返回:
            Dict: 标准响应格式，包含巡检报告
        """
        start_time = time()
        report_id = str(uuid.uuid4())[:8]

        logger.info(f"开始巡检 [report_id={report_id}, dialect={self.dialect}]")

        try:
            # 获取实例信息
            instance_info = self._inspector.get_instance_info()

            # 初始化报告
            report = InspectionReport(
                report_id=report_id,
                instance_name=instance_info.get('instance_name', 'unknown'),
                database_type=instance_info.get('database_type', self.dialect),
                database_version=instance_info.get('version', 'unknown'),
                inspection_time=datetime.now(),
                duration_seconds=0.0
            )

            # 确定巡检类型
            types_to_inspect = inspection_types or list(InspectionType)

            # 执行各类巡检
            for insp_type in types_to_inspect:
                logger.info(f"执行巡检: {insp_type.value}")

                try:
                    if insp_type == InspectionType.CONFIGURATION:
                        items = self._inspector.inspect_configuration()
                        # 同时执行慢查询配置检查（属于配置类别）
                        if hasattr(self._inspector, 'inspect_slow_queries'):
                            slow_query_items = self._inspector.inspect_slow_queries()
                            # 只保留配置相关的慢查询检查项
                            for item in slow_query_items:
                                if item.inspection_type == InspectionType.CONFIGURATION:
                                    items.append(item)
                    elif insp_type == InspectionType.PERFORMANCE:
                        items = self._inspector.inspect_performance()
                        # 同时执行索引检查和慢查询检查（性能相关）
                        if hasattr(self._inspector, 'inspect_indexes'):
                            index_items = self._inspector.inspect_indexes()
                            items.extend(index_items)
                        if hasattr(self._inspector, 'inspect_slow_queries'):
                            slow_query_items = self._inspector.inspect_slow_queries()
                            # 只保留性能相关的慢查询检查项
                            for item in slow_query_items:
                                if item.inspection_type == InspectionType.PERFORMANCE:
                                    items.append(item)
                    elif insp_type == InspectionType.STORAGE:
                        items = self._inspector.inspect_storage()
                        # 同时执行表结构检查（存储相关）
                        if hasattr(self._inspector, 'inspect_table_structure'):
                            structure_items = self._inspector.inspect_table_structure()
                            items.extend(structure_items)
                    elif insp_type == InspectionType.SECURITY:
                        items = self._inspector.inspect_security()
                    elif insp_type == InspectionType.CAPACITY:
                        items = self._inspector.inspect_capacity()
                    elif insp_type == InspectionType.REPLICATION:
                        # 复制检查
                        if hasattr(self._inspector, 'inspect_replication'):
                            items = self._inspector.inspect_replication()
                        else:
                            items = []
                    elif insp_type == InspectionType.BACKUP:
                        # 备份检查 - 检查binlog配置作为备份策略的一部分
                        items = []
                        if hasattr(self._inspector, 'inspect_configuration'):
                            # 从配置检查中提取与备份相关的项
                            config_items = self._inspector.inspect_configuration()
                            for item in config_items:
                                if item.name in ['log_bin', 'expire_logs_days', 'binlog_format']:
                                    items.append(item)
                    else:
                        continue

                    report.items.extend(items)
                except Exception as e:
                    logger.warning(f"巡检类型 {insp_type.value} 执行失败: {e}")
                    import traceback
                    logger.debug(f"巡检类型 {insp_type.value} 错误详情: {traceback.format_exc()}")
                    # 记录失败但不中断其他巡检
                    report.items.append(InspectionItem(
                        name=f"{insp_type.value}_inspection",
                        inspection_type=insp_type,
                        risk_level=RiskLevel.MEDIUM,
                        status="warning",
                        description=f"巡检执行失败: {str(e)}",
                        suggestion="请检查相关配置和权限"
                    ))

            # 计算统计信息
            self._calculate_statistics(report)

            # 计算健康评分
            report.health_score = self._score_calculator.calculate_score(report.items)

            # 生成摘要
            report.summary = report.generate_summary()

            report.duration_seconds = round(time() - start_time, 2)

            logger.info(f"巡检完成 [report_id={report_id}, duration={report.duration_seconds}s, score={report.health_score:.1f}]")

            return create_success_response(
                data=report.to_dict(),
                message="巡检完成"
            )

        except ConnectionError as e:
            logger.error(f"数据库连接失败: {e}")
            return create_error_response(
                message=f"数据库连接失败: {str(e)}",
                error_code=ErrorCode.CONNECTION_FAILED,
                details={"report_id": report_id}
            )
        except PermissionError as e:
            logger.error(f"权限不足: {e}")
            return create_error_response(
                message=f"权限不足: {str(e)}",
                error_code=ErrorCode.PERMISSION_DENIED,
                details={"report_id": report_id}
            )
        except Exception as e:
            logger.error(f"巡检失败: {e}")
            return create_error_response(
                message=f"巡检执行失败: {str(e)}",
                error_code=ErrorCode.INSPECTION_FAILED,
                details={"report_id": report_id}
            )

    def _calculate_statistics(self, report: InspectionReport):
        """计算统计信息"""
        report.total_items = len(report.items)
        report.pass_count = sum(1 for item in report.items if item.status == 'pass')
        report.warning_count = sum(1 for item in report.items if item.status == 'warning')
        report.fail_count = sum(1 for item in report.items if item.status == 'fail')

        # 按风险等级统计
        report.critical_count = sum(1 for item in report.items if item.risk_level == RiskLevel.CRITICAL)
        report.high_count = sum(1 for item in report.items if item.risk_level == RiskLevel.HIGH)
        report.medium_count = sum(1 for item in report.items if item.risk_level == RiskLevel.MEDIUM)
        report.low_count = sum(1 for item in report.items if item.risk_level == RiskLevel.LOW)
        report.info_count = sum(1 for item in report.items if item.risk_level == RiskLevel.INFO)

    def generate_html_report(self, report: InspectionReport) -> Dict[str, Any]:
        """
        生成HTML格式报告

        参数:
            report: 巡检报告

        返回:
            Dict: 标准响应格式，包含HTML报告
        """
        try:
            html = ReportFormatter.format_html(report)
            return create_success_response(
                data={"html": html},
                message="HTML报告生成成功"
            )
        except Exception as e:
            logger.error(f"HTML报告生成失败: {e}")
            return create_error_response(
                message=f"HTML报告生成失败: {str(e)}",
                error_code=ErrorCode.REPORT_GENERATION_FAILED
            )

    def generate_markdown_report(self, report: InspectionReport) -> Dict[str, Any]:
        """
        生成Markdown格式报告

        参数:
            report: 巡检报告

        返回:
            Dict: 标准响应格式，包含Markdown报告
        """
        try:
            md = ReportFormatter.format_markdown(report)
            return create_success_response(
                data={"markdown": md},
                message="Markdown报告生成成功"
            )
        except Exception as e:
            logger.error(f"Markdown报告生成失败: {e}")
            return create_error_response(
                message=f"Markdown报告生成失败: {str(e)}",
                error_code=ErrorCode.REPORT_GENERATION_FAILED
            )

    def generate_json_report(self, report: InspectionReport) -> Dict[str, Any]:
        """
        生成JSON格式报告

        参数:
            report: 巡检报告

        返回:
            Dict: 标准响应格式，包含JSON报告
        """
        try:
            json_str = ReportFormatter.format_json(report)
            return create_success_response(
                data={"json": json_str},
                message="JSON报告生成成功"
            )
        except Exception as e:
            logger.error(f"JSON报告生成失败: {e}")
            return create_error_response(
                message=f"JSON报告生成失败: {str(e)}",
                error_code=ErrorCode.REPORT_GENERATION_FAILED
            )

    def create_baseline(self, name: Optional[str] = None) -> Dict[str, Any]:
        """
        创建性能基线

        参数:
            name: 基线名称

        返回:
            Dict: 标准响应格式，包含基线信息
        """
        try:
            # 执行巡检获取当前状态
            result = self.inspect()

            if not result["success"]:
                return create_error_response(
                    message="创建基线失败：无法获取当前状态",
                    error_code=ErrorCode.BASELINE_CREATE_FAILED,
                    details={"inspect_error": result.get("message")}
                )

            report_data = result["data"]
            report = InspectionReport(
                report_id=report_data["report_id"],
                instance_name=report_data["instance_name"],
                database_type=report_data["database_type"],
                database_version=report_data.get("database_version", ""),
                inspection_time=datetime.fromisoformat(report_data["inspection_time"]),
                duration_seconds=report_data["duration_seconds"],
                health_score=report_data["health_score"]
            )

            baseline = self._baseline_manager.create_baseline(report, name)

            return create_success_response(
                data=baseline.to_dict(),
                message="性能基线创建成功"
            )

        except Exception as e:
            logger.error(f"基线创建失败: {e}")
            return create_error_response(
                message=f"基线创建失败: {str(e)}",
                error_code=ErrorCode.BASELINE_CREATE_FAILED
            )

    def compare_with_baseline(
        self,
        report: InspectionReport,
        baseline_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        对比当前报告与基线

        参数:
            report: 当前巡检报告
            baseline_id: 基线ID，None使用当前基线

        返回:
            Dict: 标准响应格式，包含对比结果
        """
        try:
            comparison = self._baseline_manager.compare_with_baseline(report, baseline_id)

            if "error" in comparison:
                return create_error_response(
                    message=comparison["error"],
                    error_code=ErrorCode.BASELINE_NOT_FOUND
                )

            return create_success_response(
                data=comparison,
                message="基线对比完成"
            )

        except Exception as e:
            logger.error(f"基线对比失败: {e}")
            return create_error_response(
                message=f"基线对比失败: {str(e)}",
                error_code=ErrorCode.BASELINE_COMPARE_FAILED
            )

    def get_top_issues(
        self,
        report: InspectionReport,
        risk_level: Optional[RiskLevel] = None,
        limit: int = 10
    ) -> Dict[str, Any]:
        """
        获取Top问题

        参数:
            report: 巡检报告
            risk_level: 风险等级过滤
            limit: 返回数量限制

        返回:
            Dict: 标准响应格式，包含问题列表
        """
        try:
            issues = InspectionAggregator.get_top_issues(report, risk_level, limit)

            return create_success_response(
                data={
                    "issues": [issue.to_dict() for issue in issues],
                    "count": len(issues)
                },
                message=f"获取Top {len(issues)} 问题成功"
            )

        except Exception as e:
            logger.error(f"获取Top问题失败: {e}")
            return create_error_response(
                message=f"获取Top问题失败: {str(e)}",
                error_code=ErrorCode.UNKNOWN_ERROR
            )

    # ==================== 智能巡检API ====================

    def intelligent_inspect(
        self,
        metrics_history: Dict[str, List[Dict[str, Any]]],
        thresholds: Optional[Dict[str, float]] = None
    ) -> Dict[str, Any]:
        """
        执行智能巡检

        参数:
            metrics_history: 指标历史数据
            thresholds: 阈值配置

        返回:
            Dict: 智能巡检结果
        """
        try:
            # 先执行基础巡检
            base_result = self.inspect()
            if not base_result["success"]:
                return base_result

            inspection_results = base_result["data"]

            # 执行智能分析
            intelligent_result = self._intelligent_inspector.perform_intelligent_inspection(
                metrics_history=metrics_history,
                inspection_results=inspection_results,
                thresholds=thresholds
            )

            # 合并结果
            result = {
                "base_inspection": inspection_results,
                "intelligent_analysis": intelligent_result,
                "summary": {
                    "health_score": inspection_results.get("health_score", 0),
                    "overall_status": intelligent_result["summary"]["overall_status"],
                    "total_anomalies": intelligent_result["summary"]["total_anomalies"],
                    "root_causes": intelligent_result["summary"]["root_causes_identified"],
                    "recommendations": intelligent_result["summary"]["recommendations"]
                }
            }

            return create_success_response(
                data=result,
                message=f"智能巡检完成，发现{intelligent_result['summary']['total_anomalies']}个异常，"
                        f"{intelligent_result['summary']['root_causes_identified']}个根因"
            )

        except Exception as e:
            logger.error(f"智能巡检失败: {e}")
            return create_error_response(
                message=f"智能巡检失败: {str(e)}",
                error_code=ErrorCode.UNKNOWN_ERROR
            )

    def detect_anomalies(
        self,
        metrics: Dict[str, List[Dict[str, Any]]],
        thresholds: Optional[Dict[str, float]] = None
    ) -> Dict[str, Any]:
        """
        检测异常模式（已接入多步骤计时）

        参数:
            metrics: 指标历史数据
            thresholds: 阈值配置

        返回:
            Dict: 异常检测结果，包含 _execution_time 步骤耗时
        """
        from dbskiter.shared.execution_timer import ExecutionTimer
        timer = ExecutionTimer().start()

        try:
            with timer.step("detect_patterns", "检测异常模式"):
                events = self._intelligent_inspector.anomaly_detector.detect_patterns(
                    metrics, thresholds
                )

            with timer.step("build_result", "构建结果数据"):
                result = create_success_response(
                    data={
                        "anomalies": [
                            {
                                "event_id": e.event_id,
                                "pattern": e.pattern.value,
                                "metric": e.metric_name,
                                "value": e.metric_value,
                                "severity": e.severity,
                                "description": e.description,
                                "timestamp": e.timestamp.isoformat()
                            }
                            for e in events
                        ],
                        "total": len(events)
                    },
                    message=f"检测到{len(events)}个异常模式"
                )

            result["_execution_time"] = timer.to_summary()
            return result

        except Exception as e:
            logger.error(f"异常检测失败: {e}")
            return create_error_response(
                message=f"检测失败: {str(e)}",
                error_code=ErrorCode.UNKNOWN_ERROR
            )

    def analyze_root_causes(
        self,
        anomaly_events: List[Dict[str, Any]],
        inspection_results: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        分析根因

        参数:
            anomaly_events: 异常事件列表
            inspection_results: 巡检结果

        返回:
            Dict: 根因分析结果
        """
        try:
            # 转换事件格式
            from .intelligent_inspector import AnomalyEvent, AnomalyPattern

            events = []
            for e in anomaly_events:
                event = AnomalyEvent(
                    event_id=e.get("event_id", ""),
                    pattern=AnomalyPattern(e.get("pattern", "baseline_deviation")),
                    metric_name=e.get("metric", ""),
                    metric_value=e.get("value", 0),
                    threshold=e.get("threshold", 0),
                    severity=e.get("severity", "MEDIUM"),
                    timestamp=datetime.fromisoformat(e.get("timestamp", datetime.now().isoformat())),
                    description=e.get("description", "")
                )
                events.append(event)

            causes = self._intelligent_inspector.root_cause_analyzer.analyze(
                events, inspection_results
            )

            return create_success_response(
                data={
                    "root_causes": [
                        {
                            "cause_id": c.cause_id,
                            "category": c.category,
                            "description": c.description,
                            "confidence": c.confidence,
                            "evidence": c.evidence,
                            "suggested_actions": c.suggested_actions,
                            "impact_scope": c.impact_scope
                        }
                        for c in causes
                    ],
                    "total": len(causes)
                },
                message=f"识别{len(causes)}个根因"
            )

        except Exception as e:
            logger.error(f"根因分析失败: {e}")
            return create_error_response(
                message=f"分析失败: {str(e)}",
                error_code=ErrorCode.UNKNOWN_ERROR
            )

    def predict_risks(
        self,
        metrics_history: Dict[str, List[Dict[str, Any]]],
        time_horizon: str = "7d"
    ) -> Dict[str, Any]:
        """
        预测风险

        参数:
            metrics_history: 指标历史数据
            time_horizon: 预测时间范围

        返回:
            Dict: 风险预测结果
        """
        try:
            forecasts = self._intelligent_inspector.predictive_inspector.predict_risks(
                metrics_history, time_horizon
            )

            return create_success_response(
                data={
                    "forecasts": [
                        {
                            "forecast_id": f.forecast_id,
                            "risk_type": f.risk_type,
                            "prediction": f.prediction.value,
                            "probability": f.probability,
                            "time_horizon": f.time_horizon,
                            "affected_components": f.affected_components,
                            "mitigation_suggestions": f.mitigation_suggestions
                        }
                        for f in forecasts
                    ],
                    "total": len(forecasts)
                },
                message=f"预测到{len(forecasts)}个风险"
            )

        except Exception as e:
            logger.error(f"风险预测失败: {e}")
            return create_error_response(
                message=f"预测失败: {str(e)}",
                error_code=ErrorCode.UNKNOWN_ERROR
            )

    def generate_smart_recommendations(
        self,
        inspection_results: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        生成智能建议

        参数:
            inspection_results: 巡检结果

        返回:
            Dict: 建议列表
        """
        try:
            recommendations = self._intelligent_inspector.recommendation_engine.generate_recommendations(
                inspection_results, []
            )

            return create_success_response(
                data={
                    "recommendations": [
                        {
                            "id": r.recommendation_id,
                            "category": r.category,
                            "priority": r.priority,
                            "title": r.title,
                            "description": r.description,
                            "steps": r.implementation_steps,
                            "benefit": r.expected_benefit,
                            "risk": r.risk_if_not_addressed,
                            "effort": r.estimated_effort
                        }
                        for r in recommendations
                    ],
                    "total": len(recommendations)
                },
                message=f"生成{len(recommendations)}条建议"
            )

        except Exception as e:
            logger.error(f"建议生成失败: {e}")
            return create_error_response(
                message=f"生成失败: {str(e)}",
                error_code=ErrorCode.UNKNOWN_ERROR
            )

    def analyze_correlations(
        self,
        metrics_data: Dict[str, List[Dict[str, Any]]]
    ) -> Dict[str, Any]:
        """
        分析指标关联

        参数:
            metrics_data: 多指标数据

        返回:
            Dict: 关联分析结果
        """
        try:
            insights = self._intelligent_inspector.correlation_analyzer.analyze_correlations(
                metrics_data
            )

            return create_success_response(
                data={
                    "insights": [
                        {
                            "insight_id": i.insight_id,
                            "primary_metric": i.primary_metric,
                            "correlated_metrics": i.correlated_metrics,
                            "relationship_type": i.relationship_type,
                            "strength": i.strength,
                            "explanation": i.explanation
                        }
                        for i in insights
                    ],
                    "total": len(insights)
                },
                message=f"发现{len(insights)}个指标关联"
            )

        except Exception as e:
            logger.error(f"关联分析失败: {e}")
            return create_error_response(
                message=f"分析失败: {str(e)}",
                error_code=ErrorCode.UNKNOWN_ERROR
            )

    def generate_html_report_from_data(self, report_data: dict) -> str:
        """
        从字典数据生成HTML格式报告

        参数:
            report_data: 巡检报告数据字典

        返回:
            str: HTML格式报告
        """
        try:
            from .utils import ReportFormatter
            from .models import InspectionReport, InspectionItem

            # 从字典重建 InspectionReport 对象
            report = self._dict_to_report(report_data)
            return ReportFormatter.format_html(report)
        except Exception as e:
            logger.error(f"HTML报告生成失败: {e}")
            return f"<html><body><h1>报告生成失败</h1><p>{e}</p></body></html>"

    def generate_markdown_report_from_data(self, report_data: dict) -> str:
        """
        从字典数据生成Markdown格式报告

        参数:
            report_data: 巡检报告数据字典

        返回:
            str: Markdown格式报告
        """
        try:
            from .utils import ReportFormatter
            from .models import InspectionReport, InspectionItem

            # 从字典重建 InspectionReport 对象
            report = self._dict_to_report(report_data)
            return ReportFormatter.format_markdown(report)
        except Exception as e:
            logger.error(f"Markdown报告生成失败: {e}")
            return f"# 报告生成失败\n\n{e}"

    def _dict_to_report(self, data: dict) -> InspectionReport:
        """将字典转换为 InspectionReport 对象"""
        from .models import InspectionReport, InspectionItem, InspectionType, RiskLevel

        report = InspectionReport(
            report_id=data.get('report_id', ''),
            instance_name=data.get('instance_name', ''),
            database_type=data.get('database_type', ''),
            database_version=data.get('database_version', ''),
            inspection_time=datetime.fromisoformat(data.get('inspection_time', datetime.now().isoformat())),
            duration_seconds=data.get('duration_seconds', 0),
            health_score=data.get('health_score', 0),
            summary=data.get('summary', '')
        )

        # 设置统计信息
        stats = data.get('statistics', {})
        report.total_items = stats.get('total_items', 0)
        report.pass_count = stats.get('pass_count', 0)
        report.warning_count = stats.get('warning_count', 0)
        report.fail_count = stats.get('fail_count', 0)
        report.critical_count = stats.get('critical_count', 0)
        report.high_count = stats.get('high_count', 0)
        report.medium_count = stats.get('medium_count', 0)
        report.low_count = stats.get('low_count', 0)

        # 转换巡检项
        for item_data in data.get('items', []):
            # to_dict()返回的是'type'而不是'inspection_type'
            type_value = item_data.get('type') or item_data.get('inspection_type', 'configuration')
            item = InspectionItem(
                name=item_data.get('name', ''),
                inspection_type=InspectionType(type_value),
                risk_level=RiskLevel(item_data.get('risk_level', 'info')),
                status=item_data.get('status', 'pass'),
                description=item_data.get('description', ''),
                actual_value=item_data.get('actual_value'),
                reference=item_data.get('reference'),
                suggestion=item_data.get('suggestion')
            )
            report.items.append(item)

        return report

    def close(self):
        """关闭Skill，释放资源"""
        logger.info("关闭 InspectorSkill...")
        logger.info("InspectorSkill 已关闭")

    # ==================== AI上下文构建 ====================

    def build_ai_context(
        self,
        skill_result: Dict[str, Any],
        scenario: str = "inspection"
    ) -> Dict[str, Any]:
        """
        构建AI分析上下文

        参数:
            skill_result: Skill返回的原始结果
            scenario: 场景标识 (inspection/intelligent/anomaly_detection/root_cause/risks)

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
        构建巡检透明度追踪信息

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

        if scenario == "inspection":
            trace["metrics_checked"] = [
                {"name": "configuration_check", "description": "配置合规性检查", "source": "系统变量"},
                {"name": "performance_check", "description": "性能指标检查", "source": "performance_schema"},
                {"name": "security_check", "description": "安全配置检查", "source": "系统变量/权限表"},
                {"name": "health_score", "description": "健康评分", "source": "综合计算"},
            ]
            trace["data_sources"] = ["system_variables", "performance_schema", "information_schema"]

        elif scenario == "intelligent":
            trace["metrics_checked"] = [
                {"name": "baseline_comparison", "description": "基线对比", "source": "历史基线"},
                {"name": "anomaly_detection", "description": "异常检测", "source": "统计模型"},
                {"name": "trend_analysis", "description": "趋势分析", "source": "时序数据"},
                {"name": "correlation_analysis", "description": "关联分析", "source": "多指标关联"},
            ]
            trace["data_sources"] = ["historical_baseline", "statistical_model", "time_series_data"]

        elif scenario == "anomaly_detection":
            trace["metrics_checked"] = [
                {"name": "metric_deviation", "description": "指标偏差", "source": "实时监控"},
                {"name": "threshold_violation", "description": "阈值违规", "source": "规则引擎"},
                {"name": "pattern_anomaly", "description": "模式异常", "source": "机器学习模型"},
            ]
            trace["data_sources"] = ["real_time_monitoring", "rule_engine", "ml_model"]

        elif scenario == "root_cause":
            trace["metrics_checked"] = [
                {"name": "causal_chain", "description": "因果链分析", "source": "事件关联"},
                {"name": "impact_analysis", "description": "影响分析", "source": "依赖图谱"},
                {"name": "timeline_reconstruction", "description": "时间线重构", "source": "审计日志"},
            ]
            trace["data_sources"] = ["event_correlation", "dependency_graph", "audit_log"]
            if not data.get("root_causes"):
                trace["confidence"] = "medium"
                trace["notes"].append("根因分析基于当前可获取数据，可能遗漏历史上下文")

        elif scenario == "risks":
            trace["metrics_checked"] = [
                {"name": "risk_factors", "description": "风险因素识别", "source": "配置+性能+安全"},
                {"name": "probability_assessment", "description": "概率评估", "source": "历史数据+趋势"},
                {"name": "impact_assessment", "description": "影响评估", "source": "业务依赖分析"},
            ]
            trace["data_sources"] = ["configuration", "performance_metrics", "security_audit"]

        else:
            trace["metrics_checked"] = [
                {"name": "general_inspection", "description": "通用巡检指标", "source": "自动检测"}
            ]
            trace["data_sources"] = ["auto_detection"]
            trace["notes"].append(f"未定义场景 '{scenario}' 的详细追踪，使用通用指标")

        return trace

    def _extract_raw_metrics_for_ai(self, data: Dict[str, Any], scenario: str) -> Dict[str, Any]:
        """提取原始指标"""
        metrics = {}

        # 提取健康评分和统计信息
        if "health_score" in data:
            metrics["health_score"] = data["health_score"]
        if "statistics" in data:
            metrics["statistics"] = data["statistics"]
        if "summary" in data:
            metrics["summary"] = data["summary"]

        # 提取巡检项详情
        if "items" in data:
            metrics["items"] = data["items"]

        # 提取各类问题
        if "issues" in data:
            metrics["issues"] = data["issues"]
        if "anomalies" in data:
            metrics["anomalies"] = data["anomalies"]
        if "risks" in data:
            metrics["risks"] = data["risks"]
        if "recommendations" in data:
            metrics["recommendations"] = data["recommendations"]

        if not metrics:
            metrics = data

        return metrics

    def _extract_rule_flags_for_ai(self, data: Dict[str, Any], scenario: str) -> Dict[str, Any]:
        """提取规则标记"""
        flags = {}

        if "issues" in data:
            issues = data["issues"]
            critical = [i for i in issues if i.get("severity") == "critical"]
            high = [i for i in issues if i.get("severity") == "high"]
            if critical:
                flags["critical_issues"] = {"flagged": True, "level": "critical", "reason": f"发现 {len(critical)} 个严重问题"}
            if high:
                flags["high_issues"] = {"flagged": True, "level": "high", "reason": f"发现 {len(high)} 个高危问题"}

        return {"_disclaimer": "规则初筛结果仅供参考", "flags": flags}

    def _build_reference_values(self, scenario: str) -> Dict[str, Any]:
        """构建参考基线"""
        return {"issue_severity": {"critical": "立即处理", "high": "尽快处理", "medium": "建议处理", "low": "可接受"}}

    def _build_ai_hints(self, scenario: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """构建AI提示"""
        hints = {"focus_areas": [], "related_commands": []}
        db_name = getattr(self.connector, 'database', '')

        # 获取健康评分
        health_score = data.get("health_score", 100)
        statistics = data.get("statistics", {})

        if scenario == "inspection":
            # 根据健康评分和统计信息动态生成关注重点
            focus_areas = []

            # 根据评分等级确定关注重点
            if health_score >= 90:
                focus_areas.append("overall_healthy")
            elif health_score >= 80:
                focus_areas.append("minor_issues_to_optimize")
            elif health_score >= 60:
                focus_areas.append("issues_need_attention")
            else:
                focus_areas.append("critical_issues_urgent")

            # 根据统计信息添加具体关注点
            critical_count = statistics.get("critical_count", 0)
            high_count = statistics.get("high_count", 0)
            warning_count = statistics.get("warning_count", 0)

            if critical_count > 0:
                focus_areas.append("critical_security_issues")
            if high_count > 0:
                focus_areas.append("high_risk_configurations")
            if warning_count > 0:
                focus_areas.append("warning_items_review")

            # 如果没有特定问题，添加通用关注点
            if not focus_areas or (critical_count == 0 and high_count == 0):
                focus_areas.extend(["configuration_issues", "performance_bottlenecks", "security_gaps"])

            hints["focus_areas"] = focus_areas

            # 添加相关命令建议
            related_commands = []
            if critical_count > 0 or high_count > 0:
                related_commands.append(f"dbskiter --database={db_name} inspector run --type security")
            if warning_count > 0:
                related_commands.append(f"dbskiter --database={db_name} inspector report --output report.html")

            hints["related_commands"] = related_commands

        elif scenario == "risks":
            hints["focus_areas"] = ["risk_mitigation", "preventive_measures"]

        return hints


