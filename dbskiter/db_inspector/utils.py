"""
db_inspector/utils.py
db_inspector 工具类

文件功能：提供巡检相关的工具类和辅助函数
主要类：
    - HealthScoreCalculator: 健康评分计算器
    - ReportFormatter: 报告格式化器
    - BaselineManager: 基线管理器
    - InspectionAggregator: 巡检结果聚合器
    - TrendAnalyzer: 趋势分析器

作者：AI Assistant
创建时间：2026-04-23
版本：3.0.0（模块化重构版）
"""

import json
import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import asdict

from .models import (
    RiskLevel,
    InspectionType,
    InspectionItem,
    InspectionReport,
    PerformanceBaseline,
)

logger = logging.getLogger(__name__)


class HealthScoreCalculator:
    """
    健康评分计算器

    功能：
        - 基于风险等级计算健康评分
        - 支持自定义权重配置
        - 提供评分趋势分析
    """

    # 默认风险权重配置 - 使用加权平均算法
    # 每个风险等级的问题有不同的权重分数
    DEFAULT_WEIGHTS = {
        RiskLevel.CRITICAL: 100,  # 严重问题权重100
        RiskLevel.HIGH: 50,       # 高风险问题权重50
        RiskLevel.MEDIUM: 20,     # 中风险问题权重20
        RiskLevel.LOW: 5,         # 低风险问题权重5
        RiskLevel.INFO: 0         # 信息项权重0
    }

    # 状态权重倍数
    STATUS_MULTIPLIERS = {
        'pass': 1.0,      # 通过得满分
        'warning': 0.5,   # 警告得50%
        'fail': 0.0,      # 失败得0分
        'skip': 0         # 跳过的项不计算
    }

    def __init__(self, weights: Optional[Dict[RiskLevel, int]] = None):
        """
        初始化评分计算器

        参数:
            weights: 自定义风险权重，None使用默认权重
        """
        self.weights = weights or self.DEFAULT_WEIGHTS.copy()

    def calculate_score(self, items: List[InspectionItem]) -> float:
        """
        计算健康评分 - 使用加权平均算法

        算法说明:
            - 每个检查项根据其风险等级有不同的权重
            - 通过状态得满分，警告得50%，失败得0分
            - 最终得分为加权平均分

        参数:
            items: 巡检项列表

        返回:
            float: 健康评分(0-100)
        """
        if not items:
            return 100.0

        # 过滤掉跳过的项和INFO级别的项
        valid_items = [
            item for item in items
            if item.status != 'skip' and item.risk_level != RiskLevel.INFO
        ]

        if not valid_items:
            return 100.0

        total_score = 0.0
        total_weight = 0.0

        for item in valid_items:
            # 处理 risk_level 可能是字符串或枚举的情况
            risk_level = item.risk_level
            if isinstance(risk_level, str):
                try:
                    risk_level = RiskLevel(risk_level)
                except ValueError:
                    risk_level = RiskLevel.INFO

            # 获取权重
            weight = self.weights.get(risk_level, 0)
            if weight == 0:
                continue

            # 根据状态计算得分
            status_multiplier = self.STATUS_MULTIPLIERS.get(item.status, 0.5)
            item_score = 100.0 * status_multiplier

            total_score += item_score * weight
            total_weight += weight

        if total_weight == 0:
            return 100.0

        # 计算加权平均分
        final_score = total_score / total_weight

        return max(0.0, min(100.0, final_score))

    def calculate_category_score(
        self,
        items: List[InspectionItem],
        inspection_type: InspectionType
    ) -> float:
        """
        计算特定类别的健康评分

        参数:
            items: 巡检项列表
            inspection_type: 巡检类型

        返回:
            float: 类别健康评分
        """
        category_items = [
            item for item in items
            if item.inspection_type == inspection_type
        ]

        if not category_items:
            return 100.0

        return self.calculate_score(category_items)

    def get_score_grade(self, score: float) -> str:
        """
        获取评分等级

        参数:
            score: 健康评分

        返回:
            str: 评分等级(excellent/good/warning/poor/critical)
        """
        if score >= 90:
            return "excellent"
        elif score >= 80:
            return "good"
        elif score >= 60:
            return "warning"
        elif score >= 40:
            return "poor"
        else:
            return "critical"


class ReportFormatter:
    """
    报告格式化器

    功能：
        - 生成多种格式的巡检报告
        - 支持HTML/Markdown/JSON格式
        - 提供报告模板定制
    """

    # HTML报告模板
    HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>数据库巡检报告 - {instance_name}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }}
        .container {{ max-width: 1200px; margin: 0 auto; background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        h1 {{ color: #333; border-bottom: 2px solid #007bff; padding-bottom: 10px; }}
        h2 {{ color: #555; margin-top: 30px; }}
        .summary {{ background: #f8f9fa; padding: 15px; border-radius: 5px; margin: 20px 0; }}
        .score {{ font-size: 24px; font-weight: bold; }}
        .score-good {{ color: #28a745; }}
        .score-warning {{ color: #ffc107; }}
        .score-danger {{ color: #dc3545; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
        th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }}
        th {{ background: #007bff; color: white; }}
        tr:hover {{ background: #f5f5f5; }}
        .badge {{ padding: 4px 8px; border-radius: 4px; font-size: 12px; font-weight: bold; }}
        .badge-pass {{ background: #d4edda; color: #155724; }}
        .badge-warning {{ background: #fff3cd; color: #856404; }}
        .badge-fail {{ background: #f8d7da; color: #721c24; }}
        .badge-critical {{ background: #dc3545; color: white; }}
        .badge-high {{ background: #fd7e14; color: white; }}
        .badge-medium {{ background: #ffc107; color: black; }}
        .badge-low {{ background: #17a2b8; color: white; }}
        .badge-info {{ background: #6c757d; color: white; }}
        .suggestion {{ color: #666; font-style: italic; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>数据库巡检报告</h1>
        {content}
    </div>
</body>
</html>
"""

    @staticmethod
    def format_html(report: InspectionReport) -> str:
        """
        格式化为HTML报告

        参数:
            report: 巡检报告

        返回:
            str: HTML格式报告
        """
        score_class = (
            "score-good" if report.health_score >= 80
            else "score-warning" if report.health_score >= 60
            else "score-danger"
        )

        # 格式化数据库类型显示
        db_type = report.database_type
        if 'mysql' in db_type.lower():
            db_type_display = 'MySQL'
        elif 'oracle' in db_type.lower():
            db_type_display = 'Oracle'
        elif 'postgres' in db_type.lower():
            db_type_display = 'PostgreSQL'
        else:
            db_type_display = db_type

        summary_html = f"""
        <div class="summary">
            <h2>报告概览</h2>
            <p><strong>实例标识:</strong> {report.instance_name}</p>
            <p><strong>数据库类型:</strong> {db_type_display}</p>
            <p><strong>数据库版本:</strong> {report.database_version}</p>
            <p><strong>巡检时间:</strong> {report.inspection_time.strftime('%Y-%m-%d %H:%M:%S')}</p>
            <p><strong>耗时:</strong> {report.duration_seconds}秒</p>
            <p><strong>健康评分:</strong>
                <span class="score {score_class}">{report.health_score:.1f}</span>
            </p>
            <p><strong>统计:</strong>
                总计 {report.total_items} 项 |
                通过 {report.pass_count} 项 |
                警告 {report.warning_count} 项 |
                失败 {report.fail_count} 项
            </p>
        </div>
        """

        items_html = ReportFormatter._format_items_html(report.items)

        content = summary_html + items_html

        return ReportFormatter.HTML_TEMPLATE.format(
            instance_name=report.instance_name,
            content=content
        )

    @staticmethod
    def _format_items_html(items: List[InspectionItem]) -> str:
        """格式化巡检项为HTML表格"""
        html = """
        <h2>详细检查结果</h2>
        <table>
            <thead>
                <tr>
                    <th>检查项</th>
                    <th>类型</th>
                    <th>风险等级</th>
                    <th>状态</th>
                    <th>描述</th>
                    <th>实际值</th>
                    <th>参考值</th>
                    <th>建议</th>
                </tr>
            </thead>
            <tbody>
        """

        for item in items:
            status_class = f"badge-{item.status}"
            risk_class = f"badge-{item.risk_level.value}"

            html += f"""
                <tr>
                    <td>{item.name}</td>
                    <td>{item.inspection_type.value}</td>
                    <td><span class="badge {risk_class}">{item.risk_level.value.upper()}</span></td>
                    <td><span class="badge {status_class}">{item.status.upper()}</span></td>
                    <td>{item.description}</td>
                    <td>{item.actual_value or '-'}</td>
                    <td>{item.reference or '-'}</td>
                    <td class="suggestion">{item.suggestion or '-'}</td>
                </tr>
            """

        html += """
            </tbody>
        </table>
        """

        return html

    @staticmethod
    def format_markdown(report: InspectionReport) -> str:
        """
        格式化为Markdown报告

        参数:
            report: 巡检报告

        返回:
            str: Markdown格式报告
        """
        # 格式化数据库类型显示
        db_type = report.database_type
        if 'mysql' in db_type.lower():
            db_type_display = 'MySQL'
        elif 'oracle' in db_type.lower():
            db_type_display = 'Oracle'
        elif 'postgres' in db_type.lower():
            db_type_display = 'PostgreSQL'
        else:
            db_type_display = db_type

        md = f"""# 数据库巡检报告

## 报告概览

| 项目 | 值 |
|------|-----|
| 实例标识 | {report.instance_name} |
| 数据库类型 | {db_type_display} |
| 数据库版本 | {report.database_version} |
| 巡检时间 | {report.inspection_time.strftime('%Y-%m-%d %H:%M:%S')} |
| 耗时 | {report.duration_seconds}秒 |
| 健康评分 | {report.health_score:.1f}/100 |

## 统计信息

- 总计: {report.total_items} 项
- 通过: {report.pass_count} 项
- 警告: {report.warning_count} 项
- 失败: {report.fail_count} 项
- 严重: {report.critical_count} 项
- 高危: {report.high_count} 项
- 中危: {report.medium_count} 项
- 低危: {report.low_count} 项

## 详细检查结果

| 检查项 | 类型 | 风险等级 | 状态 | 描述 | 实际值 | 参考值 | 建议 |
|--------|------|----------|------|------|--------|--------|------|
"""

        for item in report.items:
            md += f"| {item.name} | {item.inspection_type.value} | {item.risk_level.value} | {item.status} | {item.description} | {item.actual_value or '-'} | {item.reference or '-'} | {item.suggestion or '-'} |\n"

        return md

    @staticmethod
    def format_json(report: InspectionReport) -> str:
        """
        格式化为JSON报告

        参数:
            report: 巡检报告

        返回:
            str: JSON格式报告
        """
        return json.dumps(report.to_dict(), indent=2, ensure_ascii=False)


class BaselineManager:
    """
    基线管理器

    功能：
        - 创建性能基线
        - 对比当前状态与基线
        - 管理多个基线版本
    """

    def __init__(self):
        """初始化基线管理器"""
        self._baselines: Dict[str, PerformanceBaseline] = {}
        self._current_baseline_id: Optional[str] = None

    def create_baseline(
        self,
        report: InspectionReport,
        name: Optional[str] = None
    ) -> PerformanceBaseline:
        """
        从巡检报告创建性能基线

        参数:
            report: 巡检报告
            name: 基线名称

        返回:
            PerformanceBaseline: 性能基线
        """
        import uuid

        baseline_id = str(uuid.uuid4())[:8]
        baseline_name = name or f"baseline-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

        # 提取关键性能指标
        metrics = {}
        for item in report.items:
            if item.inspection_type == InspectionType.PERFORMANCE:
                if item.actual_value:
                    try:
                        # 尝试转换为数值
                        metrics[item.name] = float(item.actual_value)
                    except (ValueError, TypeError):
                        metrics[item.name] = item.actual_value

        baseline = PerformanceBaseline(
            baseline_id=baseline_id,
            instance_name=report.instance_name,
            created_at=datetime.now(),
            metrics=metrics
        )

        self._baselines[baseline_id] = baseline
        self._current_baseline_id = baseline_id

        logger.info(f"基线创建成功: {baseline_id}")

        return baseline

    def get_baseline(self, baseline_id: str) -> Optional[PerformanceBaseline]:
        """
        获取指定基线

        参数:
            baseline_id: 基线ID

        返回:
            PerformanceBaseline: 基线对象，不存在返回None
        """
        return self._baselines.get(baseline_id)

    def get_current_baseline(self) -> Optional[PerformanceBaseline]:
        """
        获取当前基线

        返回:
            PerformanceBaseline: 当前基线，未设置返回None
        """
        if self._current_baseline_id:
            return self._baselines.get(self._current_baseline_id)
        return None

    def set_current_baseline(self, baseline_id: str) -> bool:
        """
        设置当前基线

        参数:
            baseline_id: 基线ID

        返回:
            bool: 是否设置成功
        """
        if baseline_id in self._baselines:
            self._current_baseline_id = baseline_id
            return True
        return False

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
            Dict: 对比结果
        """
        baseline = None
        if baseline_id:
            baseline = self._baselines.get(baseline_id)
        else:
            baseline = self.get_current_baseline()

        if not baseline:
            return {
                "error": "基线不存在",
                "available_baselines": list(self._baselines.keys())
            }

        comparison = {
            "baseline_id": baseline.baseline_id,
            "baseline_time": baseline.created_at.isoformat(),
            "current_time": report.inspection_time.isoformat(),
            "health_score_change": report.health_score - 100.0,  # 基线默认为100
            "improved_items": [],
            "degraded_items": [],
            "unchanged_items": [],
            "new_items": []
        }

        # 对比各项指标
        current_metrics = {}
        for item in report.items:
            if item.actual_value:
                try:
                    current_metrics[item.name] = float(item.actual_value)
                except (ValueError, TypeError):
                    current_metrics[item.name] = item.actual_value

        for name, baseline_value in baseline.metrics.items():
            if name in current_metrics:
                current_value = current_metrics[name]

                if isinstance(baseline_value, (int, float)) and isinstance(current_value, (int, float)):
                    change_pct = ((current_value - baseline_value) / baseline_value * 100) if baseline_value != 0 else 0

                    if change_pct < -10:  # 改善超过10%
                        comparison["improved_items"].append({
                            "name": name,
                            "baseline": baseline_value,
                            "current": current_value,
                            "change_pct": round(change_pct, 2)
                        })
                    elif change_pct > 10:  # 恶化超过10%
                        comparison["degraded_items"].append({
                            "name": name,
                            "baseline": baseline_value,
                            "current": current_value,
                            "change_pct": round(change_pct, 2)
                        })
                    else:
                        comparison["unchanged_items"].append({
                            "name": name,
                            "baseline": baseline_value,
                            "current": current_value,
                            "change_pct": round(change_pct, 2)
                        })

        # 找出新增项
        for name in current_metrics:
            if name not in baseline.metrics:
                comparison["new_items"].append({
                    "name": name,
                    "current": current_metrics[name]
                })

        return comparison

    def list_baselines(self) -> List[Dict[str, Any]]:
        """
        列出所有基线

        返回:
            List: 基线列表
        """
        return [
            {
                "baseline_id": b.baseline_id,
                "instance_name": b.instance_name,
                "created_at": b.created_at.isoformat(),
                "is_current": b.baseline_id == self._current_baseline_id
            }
            for b in self._baselines.values()
        ]


class InspectionAggregator:
    """
    巡检结果聚合器

    功能：
        - 聚合多个巡检结果
        - 生成统计摘要
        - 识别常见问题
    """

    @staticmethod
    def aggregate_reports(reports: List[InspectionReport]) -> Dict[str, Any]:
        """
        聚合多个巡检报告

        参数:
            reports: 巡检报告列表

        返回:
            Dict: 聚合结果
        """
        if not reports:
            return {
                "total_reports": 0,
                "message": "没有巡检报告"
            }

        aggregation = {
            "total_reports": len(reports),
            "instances": list(set(r.instance_name for r in reports)),
            "database_types": list(set(r.database_type for r in reports)),
            "time_range": {
                "start": min(r.inspection_time for r in reports).isoformat(),
                "end": max(r.inspection_time for r in reports).isoformat()
            },
            "average_health_score": sum(r.health_score for r in reports) / len(reports),
            "total_items": sum(r.total_items for r in reports),
            "total_pass": sum(r.pass_count for r in reports),
            "total_warning": sum(r.warning_count for r in reports),
            "total_fail": sum(r.fail_count for r in reports),
            "risk_distribution": {
                "critical": sum(r.critical_count for r in reports),
                "high": sum(r.high_count for r in reports),
                "medium": sum(r.medium_count for r in reports),
                "low": sum(r.low_count for r in reports)
            },
            "failed_items_summary": InspectionAggregator._summarize_failed_items(reports)
        }

        return aggregation

    @staticmethod
    def _summarize_failed_items(reports: List[InspectionReport]) -> List[Dict[str, Any]]:
        """汇总失败的巡检项"""
        failed_items: Dict[str, Dict[str, Any]] = {}

        for report in reports:
            for item in report.items:
                if item.status in ['warning', 'fail']:
                    key = f"{item.name}:{item.inspection_type.value}"

                    if key not in failed_items:
                        failed_items[key] = {
                            "name": item.name,
                            "type": item.inspection_type.value,
                            "risk_level": item.risk_level.value,
                            "count": 0,
                            "instances": set()
                        }

                    failed_items[key]["count"] += 1
                    failed_items[key]["instances"].add(report.instance_name)

        # 转换为列表并排序
        result = []
        for item in failed_items.values():
            result.append({
                "name": item["name"],
                "type": item["type"],
                "risk_level": item["risk_level"],
                "count": item["count"],
                "instances": list(item["instances"])
            })

        # 按出现次数降序排序
        result.sort(key=lambda x: x["count"], reverse=True)

        return result[:10]  # 返回前10个最常见问题

    @staticmethod
    def get_top_issues(
        report: InspectionReport,
        risk_level: Optional[RiskLevel] = None,
        limit: int = 10
    ) -> List[InspectionItem]:
        """
        获取Top问题

        参数:
            report: 巡检报告
            risk_level: 风险等级过滤
            limit: 返回数量限制

        返回:
            List: 问题列表
        """
        items = report.items

        if risk_level:
            items = [item for item in items if item.risk_level == risk_level]

        # 按风险等级和状态排序
        risk_order = {
            RiskLevel.CRITICAL: 0,
            RiskLevel.HIGH: 1,
            RiskLevel.MEDIUM: 2,
            RiskLevel.LOW: 3,
            RiskLevel.INFO: 4
        }

        status_order = {'fail': 0, 'warning': 1, 'pass': 2}

        items.sort(key=lambda x: (
            risk_order.get(x.risk_level, 5),
            status_order.get(x.status, 3)
        ))

        return items[:limit]


class TrendAnalyzer:
    """
    趋势分析器

    功能：
        - 分析历史巡检趋势
        - 预测未来趋势
        - 识别异常变化
    """

    @staticmethod
    def analyze_score_trend(reports: List[InspectionReport]) -> Dict[str, Any]:
        """
        分析健康评分趋势

        参数:
            reports: 历史巡检报告列表

        返回:
            Dict: 趋势分析结果
        """
        if len(reports) < 2:
            return {
                "trend": "insufficient_data",
                "message": "数据不足，需要至少2次巡检记录"
            }

        # 按时间排序
        sorted_reports = sorted(reports, key=lambda r: r.inspection_time)

        scores = [r.health_score for r in sorted_reports]
        times = [r.inspection_time for r in sorted_reports]

        # 计算趋势
        first_score = scores[0]
        last_score = scores[-1]
        score_change = last_score - first_score

        # 计算平均变化率
        if len(scores) > 1:
            avg_change = score_change / (len(scores) - 1)
        else:
            avg_change = 0

        # 判断趋势方向
        if score_change > 5:
            trend = "improving"
        elif score_change < -5:
            trend = "degrading"
        else:
            trend = "stable"

        return {
            "trend": trend,
            "score_change": round(score_change, 2),
            "average_change_per_inspection": round(avg_change, 2),
            "first_score": first_score,
            "last_score": last_score,
            "min_score": min(scores),
            "max_score": max(scores),
            "average_score": round(sum(scores) / len(scores), 2),
            "inspection_count": len(reports),
            "time_span_days": (times[-1] - times[0]).days if len(times) > 1 else 0
        }

    @staticmethod
    def detect_anomalies(
        reports: List[InspectionReport],
        threshold: float = 10.0
    ) -> List[Dict[str, Any]]:
        """
        检测异常变化

        参数:
            reports: 历史巡检报告列表
            threshold: 异常阈值（分数变化超过此值视为异常）

        返回:
            List: 异常列表
        """
        if len(reports) < 2:
            return []

        sorted_reports = sorted(reports, key=lambda r: r.inspection_time)
        anomalies = []

        for i in range(1, len(sorted_reports)):
            prev_report = sorted_reports[i - 1]
            curr_report = sorted_reports[i]

            score_change = curr_report.health_score - prev_report.health_score

            if abs(score_change) > threshold:
                anomalies.append({
                    "timestamp": curr_report.inspection_time.isoformat(),
                    "report_id": curr_report.report_id,
                    "score_change": round(score_change, 2),
                    "previous_score": prev_report.health_score,
                    "current_score": curr_report.health_score,
                    "type": "improvement" if score_change > 0 else "degradation"
                })

        return anomalies
