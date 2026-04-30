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
    健康评分计算器 - 扣分制算法

    功能：
        - 基于风险等级和分类维度的扣分制评分
        - 支持分类权重配置和单项扣分上限控制
        - 符合行业主流云厂商评分标准

    算法说明：
        1. 起始分数100分，逐项扣分
        2. 不同风险等级有不同基准扣分值
        3. 按巡检类型分类，各分类有权重系数
        4. 设置分类扣分上限防止过度扣分
        5. 保留最低10分基础分

    参考标准：
        - 阿里云DAS：分类加权扣分制
        - 腾讯云DBbrain：复合扣分公式
        - 火山引擎DBW：权重占比分配
    """

    # 分类维度配置
    # 权重总和为1.0，用于分配扣分额度
    CATEGORY_CONFIG = {
        InspectionType.CONFIGURATION: {
            'weight': 0.20,
            'label': '配置规范',
            'max_deduction_ratio': 0.90  # 该分类最高扣分类权重的90%
        },
        InspectionType.PERFORMANCE: {
            'weight': 0.30,
            'label': '性能指标',
            'max_deduction_ratio': 0.90
        },
        InspectionType.SECURITY: {
            'weight': 0.25,
            'label': '安全配置',
            'max_deduction_ratio': 0.95  # 安全类问题更严重，允许扣更多
        },
        InspectionType.STORAGE: {
            'weight': 0.15,
            'label': '存储空间',
            'max_deduction_ratio': 0.90
        },
        InspectionType.CAPACITY: {
            'weight': 0.10,
            'label': '容量规划',
            'max_deduction_ratio': 0.90
        },
    }

    # 风险等级基准扣分值
    # 参考行业实践：严重问题扣分适中，避免单项过度影响
    BASE_DEDUCTION = {
        RiskLevel.CRITICAL: 12,   # 严重问题扣12分
        RiskLevel.HIGH: 6,        # 高危问题扣6分
        RiskLevel.MEDIUM: 2,      # 中等问题扣2分
        RiskLevel.LOW: 0.5,       # 低危问题扣0.5分
        RiskLevel.INFO: 0         # 信息项不扣分
    }

    # 状态调整系数
    # 警告状态按一定比例扣分，而非直接打对折
    STATUS_FACTOR = {
        'pass': 0.0,      # 通过不扣分
        'warning': 0.7,   # 警告扣70%（比原来的50%更合理）
        'fail': 1.0,      # 失败扣100%
        'skip': 0.0       # 跳过不计算
    }

    # 总扣分上限（保留最低10分）
    MAX_TOTAL_DEDUCTION = 90

    # 最低保留分数
    MIN_SCORE = 10

    def __init__(self, category_config: Optional[Dict] = None,
                 base_deduction: Optional[Dict] = None):
        """
        初始化评分计算器

        参数:
            category_config: 自定义分类配置
            base_deduction: 自定义风险等级扣分值
        """
        self.category_config = category_config or self.CATEGORY_CONFIG.copy()
        self.base_deduction = base_deduction or self.BASE_DEDUCTION.copy()

    def calculate_score(self, items: List[InspectionItem]) -> float:
        """
        计算健康评分 - 扣分制算法

        计算步骤：
            1. 按巡检类型分组统计
            2. 计算各分类的扣分
            3. 应用分类扣分上限
            4. 汇总总扣分并应用总上限
            5. 计算最终得分

        参数:
            items: 巡检项列表

        返回:
            float: 健康评分(0-100)
        """
        if not items:
            return 100.0

        # 过滤掉跳过的项
        valid_items = [item for item in items if item.status != 'skip']

        if not valid_items:
            return 100.0

        # 按巡检类型分组
        category_items = self._group_by_category(valid_items)

        # 计算各分类扣分
        category_deductions = {}
        for category, cat_items in category_items.items():
            deduction = self._calculate_category_deduction(category, cat_items)
            category_deductions[category] = deduction

        # 汇总总扣分
        total_deduction = sum(category_deductions.values())

        # 应用总扣分上限
        final_deduction = min(total_deduction, self.MAX_TOTAL_DEDUCTION)

        # 计算最终得分
        final_score = 100 - final_deduction

        return max(self.MIN_SCORE, final_score)

    def _group_by_category(self, items: List[InspectionItem]) -> Dict[InspectionType, List[InspectionItem]]:
        """
        按巡检类型分组

        参数:
            items: 巡检项列表

        返回:
            Dict: 按类型分组的字典
        """
        groups = {}
        for item in items:
            category = item.inspection_type
            if isinstance(category, str):
                try:
                    category = InspectionType(category)
                except ValueError:
                    continue

            if category not in groups:
                groups[category] = []
            groups[category].append(item)

        return groups

    def _calculate_category_deduction(self, category: InspectionType,
                                       items: List[InspectionItem]) -> float:
        """
        计算单个分类的扣分

        参数:
            category: 巡检类型
            items: 该类型的巡检项列表

        返回:
            float: 分类扣分值
        """
        # 获取分类配置
        config = self.category_config.get(category, {
            'weight': 0.20,
            'max_deduction_ratio': 0.90
        })

        category_weight = config['weight']
        max_ratio = config['max_deduction_ratio']

        # 计算该分类的原始扣分
        raw_deduction = 0.0
        for item in items:
            if item.status == 'pass':
                continue

            # 处理风险等级
            risk_level = item.risk_level
            if isinstance(risk_level, str):
                try:
                    risk_level = RiskLevel(risk_level)
                except ValueError:
                    continue

            # 获取基准扣分和状态系数
            base = self.base_deduction.get(risk_level, 0)
            status_factor = self.STATUS_FACTOR.get(item.status, 0.5)

            # 计算单项扣分
            item_deduction = base * status_factor
            raw_deduction += item_deduction

        # 分类扣分上限 = 分类权重 * 100 * 最大扣分比例
        # 例如：安全配置权重0.25，最多扣 0.25 * 100 * 0.95 = 23.75分
        max_category_deduction = category_weight * 100 * max_ratio

        # 应用分类扣分上限
        actual_deduction = min(raw_deduction, max_category_deduction)

        return actual_deduction

    def calculate_category_score(self, items: List[InspectionItem],
                                  inspection_type: InspectionType) -> float:
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

        deduction = self._calculate_category_deduction(inspection_type, category_items)
        return max(self.MIN_SCORE, 100 - deduction)

    def get_score_grade(self, score: float) -> str:
        """
        获取评分等级 - 符合行业标准分级

        等级定义：
            - healthy(健康): >= 90分
            - subhealthy(亚健康): 80-89分
            - risk(风险): 60-79分
            - danger(高危): < 60分

        参数:
            score: 健康评分

        返回:
            str: 评分等级(healthy/subhealthy/risk/danger)
        """
        if score >= 90:
            return "healthy"
        elif score >= 80:
            return "subhealthy"
        elif score >= 60:
            return "risk"
        else:
            return "danger"

    def get_score_grade_label(self, score: float) -> str:
        """
        获取评分等级的中文标签

        参数:
            score: 健康评分

        返回:
            str: 等级中文标签
        """
        grade = self.get_score_grade(score)
        labels = {
            'healthy': '健康',
            'subhealthy': '亚健康',
            'risk': '风险',
            'danger': '高危'
        }
        return labels.get(grade, '未知')

    def get_score_details(self, items: List[InspectionItem]) -> Dict[str, Any]:
        """
        获取详细的评分计算信息

        参数:
            items: 巡检项列表

        返回:
            Dict: 评分详情，包含各分类扣分明细
        """
        if not items:
            return {
                'total_score': 100.0,
                'total_deduction': 0.0,
                'category_details': {},
                'grade': 'healthy',
                'grade_label': '健康'
            }

        valid_items = [item for item in items if item.status != 'skip']
        category_items = self._group_by_category(valid_items)

        category_details = {}
        for category, cat_items in category_items.items():
            config = self.category_config.get(category, {
                'weight': 0.20,
                'label': '未分类'
            })

            deduction = self._calculate_category_deduction(category, cat_items)
            category_details[category.value] = {
                'label': config['label'],
                'weight': config['weight'],
                'deduction': round(deduction, 2),
                'item_count': len(cat_items),
                'score': round(max(self.MIN_SCORE, 100 - deduction), 1)
            }

        total_deduction = sum(d['deduction'] for d in category_details.values())
        final_deduction = min(total_deduction, self.MAX_TOTAL_DEDUCTION)
        final_score = max(self.MIN_SCORE, 100 - final_deduction)

        return {
            'total_score': round(final_score, 1),
            'total_deduction': round(final_deduction, 2),
            'category_details': category_details,
            'grade': self.get_score_grade(final_score),
            'grade_label': self.get_score_grade_label(final_score)
        }


class ReportFormatter:
    """
    报告格式化器

    功能：
        - 生成多种格式的巡检报告
        - 支持HTML/Markdown/JSON格式
        - 提供报告模板定制
        - 集成增强型报告生成器（可视化图表、风险优先级排序）
    """

    @staticmethod
    def format_html(report: InspectionReport) -> str:
        """
        格式化为HTML报告（使用增强型报告生成器）

        参数:
            report: 巡检报告

        返回:
            str: HTML格式报告
        """
        # 使用增强型报告生成器
        from .report_generator import EnhancedReportGenerator
        return EnhancedReportGenerator.generate_html_report(report)

    @staticmethod
    def format_markdown(report: InspectionReport) -> str:
        """
        格式化为Markdown报告（使用增强型报告生成器）

        参数:
            report: 巡检报告

        返回:
            str: Markdown格式报告
        """
        # 使用增强型报告生成器
        from .report_generator import EnhancedReportGenerator
        return EnhancedReportGenerator.generate_markdown_report(report)

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
