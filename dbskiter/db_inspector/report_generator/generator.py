"""
db_inspector/report_generator/generator.py
数据库巡检报告生成器（增强版）- 核心生成逻辑

文件功能：提供可视化、交互式的巡检报告生成功能
主要类：
    - EnhancedReportGenerator: 增强型报告生成器
    - RiskPrioritizer: 风险优先级排序器
    - CategoryAnalyzer: 分类分析器

ChartGenerator 在 charts.py 中定义，通过 from .charts import ChartGenerator
from .templates import HTML_TEMPLATE 引用
"""

import logging
import math
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from collections import Counter

from ..models import (
    RiskLevel,
    InspectionType,
    InspectionItem,
    InspectionReport,
)

from .charts import ChartGenerator
from .templates import HTML_TEMPLATE

logger = logging.getLogger(__name__)

INSPECTION_TYPE_META = {
    InspectionType.CONFIGURATION: {
        'label': '配置检查',
        'icon': 'settings',
        'color': '#3b82f6',
        'description': '检查数据库参数配置是否符合生产环境最佳实践'
    },
    InspectionType.PERFORMANCE: {
        'label': '性能检查',
        'icon': 'speed',
        'color': '#8b5cf6',
        'description': '检查数据库运行性能指标是否在合理范围内'
    },
    InspectionType.SECURITY: {
        'label': '安全检查',
        'icon': 'shield',
        'color': '#ef476f',
        'description': '检查数据库安全配置是否存在风险隐患'
    },
    InspectionType.STORAGE: {
        'label': '存储检查',
        'icon': 'database',
        'color': '#06d6a0',
        'description': '检查数据库存储空间使用和表结构是否合理'
    },
    InspectionType.REPLICATION: {
        'label': '复制检查',
        'icon': 'sync',
        'color': '#fd7e14',
        'description': '检查数据库主从复制状态是否正常'
    },
    InspectionType.BACKUP: {
        'label': '备份检查',
        'icon': 'archive',
        'color': '#4cc9f0',
        'description': '检查数据库备份策略是否完善'
    },
    InspectionType.CAPACITY: {
        'label': '容量检查',
        'icon': 'chart',
        'color': '#ffd166',
        'description': '检查数据库容量使用情况和增长趋势'
    },
}


class RiskPrioritizer:
    """
    风险优先级排序器

    功能：
        - 按风险等级对巡检项进行排序
        - 支持自定义排序规则
        - 提供风险分组功能
    """

    RISK_WEIGHTS = {
        RiskLevel.CRITICAL: 100,
        RiskLevel.HIGH: 75,
        RiskLevel.MEDIUM: 50,
        RiskLevel.LOW: 25,
        RiskLevel.INFO: 0
    }

    STATUS_WEIGHTS = {
        'fail': 100,
        'warning': 50,
        'pass': 0,
        'skip': -1
    }

    @classmethod
    def prioritize_items(cls, items: List[InspectionItem]) -> List[InspectionItem]:
        """
        对巡检项按风险优先级排序

        排序规则：
            1. 风险等级（严重 > 高危 > 中危 > 低危 > 信息）
            2. 状态（失败 > 警告 > 通过）
            3. 检查项名称（字母顺序）

        参数:
            items: 巡检项列表

        返回:
            List[InspectionItem]: 排序后的巡检项列表
        """
        def get_priority(item: InspectionItem) -> Tuple[int, int, str]:
            risk_level = item.risk_level
            if isinstance(risk_level, str):
                try:
                    risk_level = RiskLevel(risk_level)
                except ValueError:
                    risk_level = RiskLevel.INFO

            risk_weight = cls.RISK_WEIGHTS.get(risk_level, 0)
            status_weight = cls.STATUS_WEIGHTS.get(item.status, 0)

            return (-risk_weight, -status_weight, item.name)

        return sorted(items, key=get_priority)

    @classmethod
    def get_high_priority_items(
        cls,
        items: List[InspectionItem],
        min_risk_level: RiskLevel = RiskLevel.MEDIUM
    ) -> List[InspectionItem]:
        """
        获取高优先级巡检项

        参数:
            items: 巡检项列表
            min_risk_level: 最低风险等级

        返回:
            List[InspectionItem]: 高优先级巡检项
        """
        min_weight = cls.RISK_WEIGHTS.get(min_risk_level, 0)

        high_priority = []
        for item in items:
            risk_level = item.risk_level
            if isinstance(risk_level, str):
                try:
                    risk_level = RiskLevel(risk_level)
                except ValueError:
                    continue

            item_weight = cls.RISK_WEIGHTS.get(risk_level, 0)
            if item_weight >= min_weight and item.status != 'pass':
                high_priority.append(item)

        return cls.prioritize_items(high_priority)


class CategoryAnalyzer:
    """
    分类分析器

    功能：
        - 按巡检类型分组统计
        - 计算各类别通过率
        - 识别各类别风险分布
    """

    @staticmethod
    def analyze_by_type(items: List[InspectionItem]) -> Dict[str, List[InspectionItem]]:
        """
        按巡检类型分组

        参数:
            items: 巡检项列表

        返回:
            Dict[str, List[InspectionItem]]: 按类型分组的巡检项
        """
        groups: Dict[str, List[InspectionItem]] = {}
        for item in items:
            type_key = item.inspection_type.value
            if isinstance(item.inspection_type, InspectionType):
                type_key = item.inspection_type.value
            if type_key not in groups:
                groups[type_key] = []
            groups[type_key].append(item)
        return groups

    @staticmethod
    def get_category_stats(items: List[InspectionItem]) -> Dict[str, Dict[str, Any]]:
        """
        获取各类别统计信息

        参数:
            items: 巡检项列表

        返回:
            Dict[str, Dict[str, Any]]: 各类别统计
        """
        groups = CategoryAnalyzer.analyze_by_type(items)
        stats = {}

        for type_key, type_items in groups.items():
            total = len(type_items)
            pass_count = sum(1 for i in type_items if i.status == 'pass')
            warning_count = sum(1 for i in type_items if i.status == 'warning')
            fail_count = sum(1 for i in type_items if i.status == 'fail')

            risk_counts = Counter()
            for item in type_items:
                rl = item.risk_level
                if isinstance(rl, RiskLevel):
                    rl = rl.value
                risk_counts[rl] += 1

            pass_rate = (pass_count / total * 100) if total > 0 else 0

            suggestions = []
            for item in type_items:
                if item.suggestion and item.status != 'pass':
                    rl_val = item.risk_level
                    if isinstance(rl_val, RiskLevel):
                        rl_val = rl_val.value
                    suggestions.append({
                        'name': item.name,
                        'suggestion': item.suggestion,
                        'risk_level': rl_val,
                        'status': item.status
                    })

            stats[type_key] = {
                'total': total,
                'pass_count': pass_count,
                'warning_count': warning_count,
                'fail_count': fail_count,
                'pass_rate': pass_rate,
                'risk_counts': dict(risk_counts),
                'suggestions': suggestions,
                'items': type_items
            }

        return stats


class EnhancedReportGenerator:
    """
    增强型报告生成器

    功能：
        - 生成可视化HTML报告
        - 按风险等级排序展示
        - 提供交互式图表
        - 支持多种报告格式
    """

    

    @staticmethod
    def _get_risk_level_value(item: InspectionItem) -> str:
        """
        获取风险等级的字符串值

        参数:
            item: 巡检项

        返回:
            str: 风险等级字符串
        """
        if isinstance(item.risk_level, RiskLevel):
            return item.risk_level.value
        return str(item.risk_level)

    @staticmethod
    def _get_status_display(status: str) -> str:
        """
        获取状态显示文本

        参数:
            status: 状态值

        返回:
            str: 中文状态文本
        """
        return '通过' if status == 'pass' else '告警' if status == 'warning' else '失败'

    @staticmethod
    def _get_insp_type_enum(item: InspectionItem) -> Optional[InspectionType]:
        """
        获取巡检类型的枚举值

        参数:
            item: 巡检项

        返回:
            Optional[InspectionType]: 巡检类型枚举
        """
        for it in InspectionType:
            if isinstance(item.inspection_type, InspectionType):
                if it.value == item.inspection_type.value:
                    return it
            elif it.value == item.inspection_type:
                return it
        return None

    @staticmethod
    def _build_item_value_html(item: InspectionItem) -> str:
        """
        构建巡检项实际值的HTML

        参数:
            item: 巡检项

        返回:
            str: HTML代码
        """
        if item.actual_value:
            return f'<div class="cat-item-value" title="{item.actual_value}">实际: {item.actual_value}</div>'
        return ''

    @staticmethod
    def _build_item_suggestion_html(item: InspectionItem) -> str:
        """
        构建巡检项建议的HTML

        参数:
            item: 巡检项

        返回:
            str: HTML代码
        """
        if item.suggestion and item.status != 'pass':
            return f'<div class="cat-item-suggestion" title="{item.suggestion}">{item.suggestion}</div>'
        return ''

    @staticmethod
    def generate_html_report(report: InspectionReport) -> str:
        """
        生成增强版HTML报告

        参数:
            report: 巡检报告

        返回:
            str: HTML格式报告
        """
        db_type = report.database_type
        if 'mysql' in db_type.lower():
            db_type_display = 'MySQL'
        elif 'oracle' in db_type.lower():
            db_type_display = 'Oracle'
        elif 'postgresql' in db_type.lower():
            db_type_display = 'PostgreSQL'
        else:
            db_type_display = db_type

        category_stats = CategoryAnalyzer.get_category_stats(report.items)

        nav = EnhancedReportGenerator._generate_nav(category_stats)
        header = EnhancedReportGenerator._generate_header(
            report.instance_name,
            db_type_display,
            report.database_version,
            report.inspection_time,
            report.duration_seconds,
            report.health_score
        )
        summary = EnhancedReportGenerator._generate_executive_summary(
            report, db_type_display, category_stats
        )
        stats = EnhancedReportGenerator._generate_stats_row(
            report.critical_count,
            report.high_count,
            report.medium_count,
            report.low_count,
            report.info_count
        )
        charts = EnhancedReportGenerator._generate_charts(
            report.health_score,
            report.critical_count,
            report.high_count,
            report.medium_count,
            report.low_count,
            report.info_count,
            report.pass_count,
            report.warning_count,
            report.fail_count,
            category_stats
        )
        high_risk = EnhancedReportGenerator._generate_high_risk_section(report.items)
        categories = EnhancedReportGenerator._generate_category_sections(
            report.items, category_stats
        )
        recommendations = EnhancedReportGenerator._generate_recommendations(report.items)
        details = EnhancedReportGenerator._generate_details_section(report.items)
        footer = EnhancedReportGenerator._generate_footer()

        content = (
            nav + header + summary + stats + charts + high_risk
            + categories + recommendations + details + footer
        )

        return HTML_TEMPLATE.format(
            instance_name=report.instance_name,
            content=content
        )

    @staticmethod
    def _generate_header(
        instance_name: str,
        db_type: str,
        db_version: str,
        inspection_time: datetime,
        duration: float,
        health_score: float
    ) -> str:
        """生成报告头部"""
        return f'''
        <div class="report-header">
            <div class="header-top">
                <div>
                    <div class="header-title">数据库巡检报告</div>
                    <div class="header-subtitle">{instance_name}</div>
                </div>
                <div class="header-badge">健康评分 {health_score:.1f}</div>
            </div>
            <div class="header-meta">
                <div class="meta-item">
                    <div class="meta-label">实例标识</div>
                    <div class="meta-value">{instance_name}</div>
                </div>
                <div class="meta-item">
                    <div class="meta-label">数据库类型</div>
                    <div class="meta-value">{db_type}</div>
                </div>
                <div class="meta-item">
                    <div class="meta-label">数据库版本</div>
                    <div class="meta-value">{db_version}</div>
                </div>
                <div class="meta-item">
                    <div class="meta-label">巡检时间</div>
                    <div class="meta-value">{inspection_time.strftime("%Y-%m-%d %H:%M")}</div>
                </div>
                <div class="meta-item">
                    <div class="meta-label">巡检耗时</div>
                    <div class="meta-value">{duration:.2f} 秒</div>
                </div>
            </div>
        </div>
        '''

    @staticmethod
    def _generate_nav(
        category_stats: Dict[str, Dict[str, Any]]
    ) -> str:
        """
        生成导航栏

        参数:
            category_stats: 分类统计数据

        返回:
            str: HTML代码
        """
        nav_links = [
            '<a class="nav-link" href="#summary">执行摘要</a>',
            '<a class="nav-link" href="#charts">图表分析</a>',
            '<a class="nav-link" href="#high-risk">重点关注</a>',
        ]

        type_order = [
            InspectionType.CONFIGURATION,
            InspectionType.PERFORMANCE,
            InspectionType.SECURITY,
            InspectionType.STORAGE,
            InspectionType.REPLICATION,
            InspectionType.BACKUP,
            InspectionType.CAPACITY,
        ]

        for insp_type in type_order:
            if insp_type.value in category_stats:
                meta = INSPECTION_TYPE_META.get(insp_type, {})
                label = meta.get('label', insp_type.value)
                nav_links.append(
                    f'<a class="nav-link" href="#cat-{insp_type.value}">{label}</a>'
                )

        nav_links.append('<a class="nav-link" href="#recommendations">建议汇总</a>')
        nav_links.append('<a class="nav-link" href="#details">详细列表</a>')

        return f'''
        <nav class="report-nav">
            <span class="nav-label">快速导航</span>
            {''.join(nav_links)}
        </nav>
        '''

    @staticmethod
    def _generate_executive_summary(
        report: InspectionReport,
        db_type_display: str,
        category_stats: Dict[str, Dict[str, Any]]
    ) -> str:
        """
        生成执行摘要

        参数:
            report: 巡检报告
            db_type_display: 数据库类型显示名
            category_stats: 分类统计

        返回:
            str: HTML代码
        """
        total = report.total_items
        pass_count = report.pass_count
        warning_count = report.warning_count
        fail_count = report.fail_count
        critical = report.critical_count
        high = report.high_count
        health = report.health_score

        # 评估标准：健康(>=90) 亚健康(80-89) 风险(60-79) 高危(<60)
        if health >= 90:
            overall_assessment = '整体运行状况健康'
            assessment_detail = '数据库各项指标正常，继续保持当前运维策略'
        elif health >= 80:
            overall_assessment = '整体运行状况亚健康，存在轻微问题'
            assessment_detail = '数据库存在少量可优化项，建议在合适时机处理'
        elif health >= 60:
            overall_assessment = '整体运行状况存在风险，需要关注'
            assessment_detail = '数据库存在若干配置或性能问题，建议按优先级逐步处理'
        else:
            overall_assessment = '整体运行状况高危，需立即处理'
            assessment_detail = '数据库存在严重风险，建议立即采取措施'

        problem_categories = []
        for type_key, stats in category_stats.items():
            if stats['warning_count'] + stats['fail_count'] > 0:
                insp_type = None
                for it in InspectionType:
                    if it.value == type_key:
                        insp_type = it
                        break
                meta = INSPECTION_TYPE_META.get(insp_type, {})
                label = meta.get('label', type_key)
                problem_count = stats['warning_count'] + stats['fail_count']
                problem_categories.append(f'{label}({problem_count}项)')

        problem_text = '、'.join(problem_categories) if problem_categories else '无'

        summary_text = (
            f'本次巡检对 <strong>{report.instance_name}</strong> '
            f'({db_type_display} {report.database_version}) 进行了全面检查，'
            f'共执行 <strong>{total}</strong> 项检查，'
            f'其中 <strong>{pass_count}</strong> 项通过、'
            f'<strong>{warning_count}</strong> 项告警、'
            f'<strong>{fail_count}</strong> 项失败。'
            f'{overall_assessment}。'
            f'存在问题的检查类别：{problem_text}。'
            f'{assessment_detail}。'
        )

        return f'''
        <div class="executive-summary section-anchor" id="summary">
            <div class="card-header">
                <div class="card-title">执行摘要</div>
            </div>
            <div class="summary-text">{summary_text}</div>
            <div class="summary-highlights">
                <div class="highlight-item">
                    <div class="highlight-icon score">{health:.0f}</div>
                    <div class="highlight-content">
                        <div class="highlight-value">{health:.1f}</div>
                        <div class="highlight-label">健康评分</div>
                    </div>
                </div>
                <div class="highlight-item">
                    <div class="highlight-icon critical">{critical + high}</div>
                    <div class="highlight-content">
                        <div class="highlight-value">{critical + high}</div>
                        <div class="highlight-label">高危及以上问题</div>
                    </div>
                </div>
                <div class="highlight-item">
                    <div class="highlight-icon warning">{warning_count}</div>
                    <div class="highlight-content">
                        <div class="highlight-value">{warning_count}</div>
                        <div class="highlight-label">告警项</div>
                    </div>
                </div>
                <div class="highlight-item">
                    <div class="highlight-icon pass">{pass_count / max(total, 1) * 100:.0f}%</div>
                    <div class="highlight-content">
                        <div class="highlight-value">{pass_count / max(total, 1) * 100:.1f}%</div>
                        <div class="highlight-label">检查通过率</div>
                    </div>
                </div>
            </div>
        </div>
        '''

    @staticmethod
    def _generate_stats_row(
        critical: int,
        high: int,
        medium: int,
        low: int,
        info: int
    ) -> str:
        """生成统计卡片行"""
        return f'''
        <div class="stats-row">
            <div class="stat-card critical">
                <div class="stat-num">{critical}</div>
                <div class="stat-label">严重风险</div>
            </div>
            <div class="stat-card high">
                <div class="stat-num">{high}</div>
                <div class="stat-label">高危风险</div>
            </div>
            <div class="stat-card medium">
                <div class="stat-num">{medium}</div>
                <div class="stat-label">中危风险</div>
            </div>
            <div class="stat-card low">
                <div class="stat-num">{low}</div>
                <div class="stat-label">低危风险</div>
            </div>
            <div class="stat-card info">
                <div class="stat-num">{info}</div>
                <div class="stat-label">信息项</div>
            </div>
        </div>
        '''

    @staticmethod
    def _generate_charts(
        health_score: float,
        critical: int,
        high: int,
        medium: int,
        low: int,
        info: int,
        pass_count: int,
        warning_count: int,
        fail_count: int,
        category_stats: Dict[str, Dict[str, Any]]
    ) -> str:
        """生成图表区域"""
        donut = ChartGenerator.generate_health_donut(health_score)
        risk_chart = ChartGenerator.generate_risk_distribution_chart(
            critical, high, medium, low, info
        )
        status_chart = ChartGenerator.generate_status_chart(
            pass_count, warning_count, fail_count
        )
        category_chart = ChartGenerator.generate_category_pass_rate_chart(
            category_stats
        )

        total = pass_count + warning_count + fail_count
        pass_rate = pass_count / max(total, 1) * 100
        problem_rate = (warning_count + fail_count) / max(total, 1) * 100
        high_risk_rate = (critical + high) / max(critical + high + medium + low + info, 1) * 100

        return f'''
        <div class="charts-grid section-anchor" id="charts">
            <div class="card">
                <div class="card-header">
                    <div class="card-title">健康评分</div>
                </div>
                {donut}
            </div>
            <div class="card">
                <div class="card-header">
                    <div class="card-title">风险等级分布</div>
                </div>
                {risk_chart}
            </div>
            <div class="card">
                <div class="card-header">
                    <div class="card-title">检查状态统计</div>
                </div>
                {status_chart}
            </div>
            <div class="card">
                <div class="card-header">
                    <div class="card-title">分类通过率</div>
                </div>
                {category_chart}
            </div>
            <div class="card" style="grid-column: 1 / -1;">
                <div class="card-header">
                    <div class="card-title">巡检概要</div>
                </div>
                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 24px;">
                    <div>
                        <div style="display: flex; justify-content: space-between; margin-bottom: 6px;">
                            <span style="color: var(--text-secondary); font-size: 13px;">检查通过率</span>
                            <span style="color: var(--pass); font-size: 13px; font-weight: 600;">{pass_rate:.1f}%</span>
                        </div>
                        <div style="height: 8px; background: rgba(255,255,255,0.05); border-radius: 4px; overflow: hidden;">
                            <div style="height: 100%; width: {pass_rate:.1f}%; background: var(--pass); border-radius: 4px; transition: width 1s ease;"></div>
                        </div>
                    </div>
                    <div>
                        <div style="display: flex; justify-content: space-between; margin-bottom: 6px;">
                            <span style="color: var(--text-secondary); font-size: 13px;">问题发现率</span>
                            <span style="color: var(--fail); font-size: 13px; font-weight: 600;">{problem_rate:.1f}%</span>
                        </div>
                        <div style="height: 8px; background: rgba(255,255,255,0.05); border-radius: 4px; overflow: hidden;">
                            <div style="height: 100%; width: {problem_rate:.1f}%; background: var(--fail); border-radius: 4px; transition: width 1s ease;"></div>
                        </div>
                    </div>
                    <div>
                        <div style="display: flex; justify-content: space-between; margin-bottom: 6px;">
                            <span style="color: var(--text-secondary); font-size: 13px;">高危问题占比</span>
                            <span style="color: var(--high); font-size: 13px; font-weight: 600;">{high_risk_rate:.1f}%</span>
                        </div>
                        <div style="height: 8px; background: rgba(255,255,255,0.05); border-radius: 4px; overflow: hidden;">
                            <div style="height: 100%; width: {high_risk_rate:.1f}%; background: var(--high); border-radius: 4px; transition: width 1s ease;"></div>
                        </div>
                    </div>
                    <div style="border-top: 1px solid var(--border-color); padding-top: 16px; grid-column: 1 / -1;">
                        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 12px; font-size: 13px;">
                            <div style="display: flex; justify-content: space-between;">
                                <span style="color: var(--text-muted);">总检查项</span>
                                <span style="color: var(--text-primary); font-weight: 600;">{total}</span>
                            </div>
                            <div style="display: flex; justify-content: space-between;">
                                <span style="color: var(--text-muted);">通过</span>
                                <span style="color: var(--pass); font-weight: 600;">{pass_count}</span>
                            </div>
                            <div style="display: flex; justify-content: space-between;">
                                <span style="color: var(--text-muted);">告警</span>
                                <span style="color: var(--warning); font-weight: 600;">{warning_count}</span>
                            </div>
                            <div style="display: flex; justify-content: space-between;">
                                <span style="color: var(--text-muted);">失败</span>
                                <span style="color: var(--fail); font-weight: 600;">{fail_count}</span>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        '''

    @staticmethod
    def _generate_high_risk_section(items: List[InspectionItem]) -> str:
        """生成高风险区域"""
        high_priority_items = RiskPrioritizer.get_high_priority_items(
            items, min_risk_level=RiskLevel.MEDIUM
        )

        if not high_priority_items:
            return '''
            <div class="high-risk-section">
                <div class="card-header">
                    <div class="card-title">重点关注问题</div>
                </div>
                <div class="empty-state">
                    <div class="empty-icon">OK</div>
                    <div>未发现高风险问题，系统运行良好</div>
                </div>
            </div>
            '''

        risk_cards = []
        for item in high_priority_items[:10]:
            risk_class = EnhancedReportGenerator._get_risk_level_value(item)

            meta_items = [
                f'<span>类型: {item.inspection_type.value}</span>',
                f'<span>状态: {item.status}</span>'
            ]
            if item.actual_value:
                meta_items.append(f'<span>实际值: {item.actual_value}</span>')
            if item.reference:
                meta_items.append(f'<span>参考值: {item.reference}</span>')

            suggestion_html = f'<div class="risk-item-suggestion">{item.suggestion}</div>' if item.suggestion else ''

            risk_cards.append(f'''
                <div class="risk-item {risk_class}">
                    <div class="risk-item-top">
                        <div class="risk-item-name">{item.name}</div>
                        <span class="level-tag {risk_class}">{risk_class.upper()}</span>
                    </div>
                    <div class="risk-item-desc">{item.description}</div>
                    <div class="risk-item-meta">
                        {''.join(meta_items)}
                    </div>
                    {suggestion_html}
                </div>
            ''')

        total_high_risk = len(high_priority_items)
        show_more = total_high_risk > 10

        show_more_html = f'<div class="show-more">还有 {total_high_risk - 10} 个问题，请查看详细列表</div>' if show_more else ''

        return f'''
        <div class="high-risk-section">
            <div class="card-header">
                <div class="card-title">重点关注问题（需优先处理）</div>
                <span class="risk-count-badge">{total_high_risk} 项</span>
            </div>
            {''.join(risk_cards)}
            {show_more_html}
        </div>
        '''

    @staticmethod
    def _generate_category_sections(
        items: List[InspectionItem],
        category_stats: Dict[str, Dict[str, Any]]
    ) -> str:
        """
        生成分类展示区域

        参数:
            items: 巡检项列表
            category_stats: 分类统计

        返回:
            str: HTML代码
        """
        type_order = [
            InspectionType.CONFIGURATION,
            InspectionType.PERFORMANCE,
            InspectionType.SECURITY,
            InspectionType.STORAGE,
            InspectionType.REPLICATION,
            InspectionType.BACKUP,
            InspectionType.CAPACITY,
        ]

        sections = []
        for insp_type in type_order:
            type_key = insp_type.value
            if type_key not in category_stats:
                continue

            stats = category_stats[type_key]
            meta = INSPECTION_TYPE_META.get(insp_type, {})
            label = meta.get('label', type_key)
            color = meta.get('color', '#3b82f6')
            desc = meta.get('description', '')

            total = stats['total']
            pass_count = stats['pass_count']
            warning_count = stats['warning_count']
            fail_count = stats['fail_count']
            pass_rate = stats['pass_rate']

            rate_color = '#06d6a0' if pass_rate >= 80 else '#ffd166' if pass_rate >= 60 else '#ef476f'

            risk_counts = stats['risk_counts']
            critical_count = risk_counts.get('critical', 0)
            high_count = risk_counts.get('high', 0)

            sorted_items = RiskPrioritizer.prioritize_items(stats['items'])

            max_display = 5
            display_items = sorted_items[:max_display]
            hidden_count = len(sorted_items) - max_display

            item_rows = []
            for item in display_items:
                status_class = item.status
                value_text = EnhancedReportGenerator._build_item_value_html(item)
                suggestion_text = EnhancedReportGenerator._build_item_suggestion_html(item)
                status_display = EnhancedReportGenerator._get_status_display(status_class)

                item_rows.append(f'''
                    <div class="cat-item">
                        <div>
                            <div class="cat-item-name">{item.name}</div>
                            <div class="cat-item-desc">{item.description}</div>
                        </div>
                        {value_text}
                        {suggestion_text}
                        <span class="status-tag {status_class}">{status_display}</span>
                    </div>
                ''')

            expand_btn = ''
            hidden_items_html = ''
            if hidden_count > 0:
                expand_btn = f'<button class="toggle-btn" id="cat-{type_key}-btn" onclick="toggleCategory(\'cat-{type_key}-hidden\')">展开全部 ({hidden_count}项)</button>'

                hidden_rows = []
                for item in sorted_items[max_display:]:
                    status_class = item.status
                    value_text = EnhancedReportGenerator._build_item_value_html(item)
                    suggestion_text = EnhancedReportGenerator._build_item_suggestion_html(item)
                    status_display = EnhancedReportGenerator._get_status_display(status_class)

                    hidden_rows.append(f'''
                        <div class="cat-item">
                            <div>
                                <div class="cat-item-name">{item.name}</div>
                                <div class="cat-item-desc">{item.description}</div>
                            </div>
                            {value_text}
                            {suggestion_text}
                            <span class="status-tag {status_class}">{status_display}</span>
                        </div>
                    ''')

                hidden_items_html = f'<div id="cat-{type_key}-hidden" class="collapsed">{''.join(hidden_rows)}</div>'

            high_risk_badge = ''
            if critical_count + high_count > 0:
                high_risk_badge = f'<span class="risk-count-badge" style="background: rgba(253,126,20,0.15); color: var(--high);">{critical_count + high_count} 高危</span>'

            sections.append(f'''
            <div class="category-section section-anchor" id="cat-{type_key}">
                <div class="category-section-header">
                    <div class="category-title">
                        <span class="category-dot" style="background: {color};"></span>
                        {label}
                        {high_risk_badge}
                    </div>
                    <span style="font-size: 13px; color: var(--text-muted);">通过率 {pass_rate:.0f}%</span>
                </div>
                <div class="category-desc">{desc}</div>
                <div class="category-stats-bar">
                    <div class="cat-stat">
                        <span class="cat-stat-label">检查项:</span>
                        <span class="cat-stat-value">{total}</span>
                    </div>
                    <div class="cat-stat">
                        <span class="cat-stat-label">通过:</span>
                        <span class="cat-stat-value pass">{pass_count}</span>
                    </div>
                    <div class="cat-stat">
                        <span class="cat-stat-label">告警:</span>
                        <span class="cat-stat-value warning">{warning_count}</span>
                    </div>
                    <div class="cat-stat">
                        <span class="cat-stat-label">失败:</span>
                        <span class="cat-stat-value fail">{fail_count}</span>
                    </div>
                </div>
                <div class="category-pass-bar">
                    <div class="category-pass-fill" style="width: {pass_rate:.1f}%; background: {rate_color};"></div>
                </div>
                <div class="category-items">
                    {''.join(item_rows)}
                </div>
                {hidden_items_html}
                {expand_btn}
            </div>
            ''')

        return ''.join(sections)

    @staticmethod
    def _generate_recommendations(items: List[InspectionItem]) -> str:
        """
        生成建议汇总区域

        参数:
            items: 巡检项列表

        返回:
            str: HTML代码
        """
        problem_items = [
            item for item in items
            if item.suggestion and item.status != 'pass'
        ]

        sorted_problems = RiskPrioritizer.prioritize_items(problem_items)

        if not sorted_problems:
            return '''
            <div class="recommendations-section section-anchor" id="recommendations">
                <div class="card-header">
                    <div class="card-title">建议汇总</div>
                </div>
                <div class="empty-state">
                    <div>未发现需要处理的问题</div>
                </div>
            </div>
            '''

        rec_items = []
        for idx, item in enumerate(sorted_problems[:15], 1):
            risk_class = EnhancedReportGenerator._get_risk_level_value(item)

            if risk_class in ('critical', 'high'):
                priority_class = 'p1'
                priority_label = 'P1'
            elif risk_class == 'medium':
                priority_class = 'p2'
                priority_label = 'P2'
            else:
                priority_class = 'p3'
                priority_label = 'P3'

            insp_type = EnhancedReportGenerator._get_insp_type_enum(item)
            type_meta = INSPECTION_TYPE_META.get(insp_type, {})
            type_label = type_meta.get('label', str(item.inspection_type))

            detail_parts = []
            if item.actual_value:
                detail_parts.append(f'当前值: {item.actual_value}')
            if item.reference:
                detail_parts.append(f'建议值: {item.reference}')
            detail_text = ' | '.join(detail_parts) if detail_parts else ''

            rec_items.append(f'''
                <div class="rec-item">
                    <div class="rec-priority {priority_class}">{priority_label}</div>
                    <div class="rec-content">
                        <div class="rec-title">{item.name}</div>
                        <div class="rec-detail">{item.suggestion}</div>
                        <div class="rec-meta">
                            <span>{type_label}</span>
                            <span>{risk_class.upper()}</span>
                            {f'<span>{detail_text}</span>' if detail_text else ''}
                        </div>
                    </div>
                </div>
            ''')

        remaining = len(sorted_problems) - 15
        remaining_html = ''
        if remaining > 0:
            remaining_html = f'<div style="text-align: center; color: var(--text-muted); font-size: 13px; padding: 12px;">还有 {remaining} 条建议，请查看详细列表</div>'

        return f'''
        <div class="recommendations-section section-anchor" id="recommendations">
            <div class="card-header">
                <div class="card-title">建议汇总（按优先级排列）</div>
                <span class="risk-count-badge" style="background: rgba(59,130,246,0.15); color: var(--accent);">{len(sorted_problems)} 条</span>
            </div>
            {''.join(rec_items)}
            {remaining_html}
        </div>
        '''

    @staticmethod
    def _generate_details_section(items: List[InspectionItem]) -> str:
        """
        生成详细列表区域（带分页功能）

        参数:
            items: 巡检项列表

        返回:
            str: HTML代码
        """
        sorted_items = RiskPrioritizer.prioritize_items(items)
        total_items = len(sorted_items)

        # 分页配置
        items_per_page = 20
        total_pages = max(1, (total_items + items_per_page - 1) // items_per_page)

        # 生成所有页面的行数据
        all_page_rows = []
        for page in range(total_pages):
            start_idx = page * items_per_page
            end_idx = min(start_idx + items_per_page, total_items)
            page_items = sorted_items[start_idx:end_idx]

            rows = []
            for item in page_items:
                status_class = f"status-{item.status}"
                risk_level = EnhancedReportGenerator._get_risk_level_value(item)

                rows.append(f'''
                    <tr>
                        <td>{item.name}</td>
                        <td>{item.inspection_type.value}</td>
                        <td>{risk_level.upper()}</td>
                        <td><span class="status-tag {status_class}">{item.status.upper()}</span></td>
                        <td>{item.description}</td>
                        <td>{item.actual_value or '-'}</td>
                        <td>{item.reference or '-'}</td>
                        <td>{item.suggestion or '-'}</td>
                    </tr>
                ''')
            all_page_rows.append(''.join(rows))

        # 生成页码按钮
        page_buttons = []
        for i in range(total_pages):
            active_class = 'active' if i == 0 else ''
            page_buttons.append(
                f'<button class="page-btn {active_class}" data-page="{i}" onclick="goToPage({i})">{i + 1}</button>'
            )

        # 生成各页面的tbody
        page_bodies = []
        for i, page_rows in enumerate(all_page_rows):
            display = 'table-row-group' if i == 0 else 'none'
            page_bodies.append(
                f'<tbody id="page-{i}" class="page-content" style="display: {display};">{page_rows}</tbody>'
            )

        # 分页信息
        pagination_info = f'共 {total_items} 条，{total_pages} 页'

        return f'''
        <div class="details-section section-anchor" id="details">
            <div class="card-header">
                <div class="card-title">详细检查结果</div>
                <span style="font-size: 13px; color: var(--text-muted);">{pagination_info}</span>
            </div>
            <button class="toggle-btn" id="toggle-btn" onclick="toggleDetails()">展开详细列表</button>
            <div id="full-details" class="collapsed">
                <table class="details-table">
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
                    {''.join(page_bodies)}
                </table>
                <div class="pagination">
                    <button class="page-btn" onclick="prevPage()" id="prev-btn" disabled>上一页</button>
                    <div class="page-numbers">
                        {''.join(page_buttons)}
                    </div>
                    <button class="page-btn" onclick="nextPage()" id="next-btn">下一页</button>
                    <span class="page-info">第 <span id="current-page">1</span> / {total_pages} 页</span>
                </div>
            </div>
        </div>
        '''

    @staticmethod
    def _generate_footer() -> str:
        """生成页脚"""
        return f'''
        <div class="report-footer">
            <p>本报告由数据库巡检系统自动生成</p>
            <p>生成时间：{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
        </div>
        '''

    @staticmethod
    def generate_markdown_report(report: InspectionReport) -> str:
        """
        生成增强版Markdown报告

        参数:
            report: 巡检报告

        返回:
            str: Markdown格式报告
        """
        db_type = report.database_type
        if 'mysql' in db_type.lower():
            db_type_display = 'MySQL'
        elif 'oracle' in db_type.lower():
            db_type_display = 'Oracle'
        elif 'postgresql' in db_type.lower():
            db_type_display = 'PostgreSQL'
        else:
            db_type_display = db_type

        # 评分等级标准：健康(>=90) 亚健康(80-89) 风险(60-79) 高危(<60)
        if report.health_score >= 90:
            grade = '健康'
        elif report.health_score >= 80:
            grade = '亚健康'
        elif report.health_score >= 60:
            grade = '风险'
        else:
            grade = '高危'

        md = f"""# 数据库巡检报告

## 报告概览

| 项目 | 值 |
|------|-----|
| 实例标识 | {report.instance_name} |
| 数据库类型 | {db_type_display} |
| 数据库版本 | {report.database_version} |
| 巡检时间 | {report.inspection_time.strftime('%Y-%m-%d %H:%M:%S')} |
| 耗时 | {report.duration_seconds:.2f} 秒 |
| 健康评分 | **{report.health_score:.1f}** ({grade}) |

## 风险统计

| 风险等级 | 数量 |
|----------|------|
| 严重 | {report.critical_count} |
| 高危 | {report.high_count} |
| 中危 | {report.medium_count} |
| 低危 | {report.low_count} |
| 信息 | {report.info_count} |

## 检查状态统计

| 状态 | 数量 |
|------|------|
| 通过 | {report.pass_count} |
| 警告 | {report.warning_count} |
| 失败 | {report.fail_count} |
| **总计** | **{report.total_items}** |

## 重点关注问题

"""

        high_priority_items = RiskPrioritizer.get_high_priority_items(
            report.items, min_risk_level=RiskLevel.MEDIUM
        )

        if high_priority_items:
            for i, item in enumerate(high_priority_items[:10], 1):
                risk_level = EnhancedReportGenerator._get_risk_level_value(item)
                md += f"""### {i}. {item.name}

- **风险等级**: {risk_level.upper()}
- **检查类型**: {item.inspection_type.value}
- **状态**: {item.status}
- **问题描述**: {item.description}
- **实际值**: {item.actual_value or 'N/A'}
- **参考值**: {item.reference or 'N/A'}
- **处理建议**: {item.suggestion or '无'}

---

"""
        else:
            md += "未发现高风险问题，系统运行良好。\n\n"

        md += """## 详细检查结果

| 检查项 | 类型 | 风险等级 | 状态 | 描述 | 实际值 | 参考值 | 建议 |
|--------|------|----------|------|------|--------|--------|------|
"""

        sorted_items = RiskPrioritizer.prioritize_items(report.items)
        for item in sorted_items:
            risk_level = EnhancedReportGenerator._get_risk_level_value(item)
            md += f"| {item.name} | {item.inspection_type.value} | {risk_level} | {item.status} | {item.description} | {item.actual_value or '-'} | {item.reference or '-'} | {item.suggestion or '-'} |\n"

        md += f"""

---

*本报告由数据库巡检系统自动生成*
*生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*
"""

        return md

