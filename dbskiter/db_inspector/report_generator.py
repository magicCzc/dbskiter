"""
db_inspector/report_generator.py
数据库巡检报告生成器（增强版）

文件功能：提供可视化、交互式的巡检报告生成功能
主要类：
    - EnhancedReportGenerator: 增强型报告生成器
    - ChartGenerator: 图表生成器
    - RiskPrioritizer: 风险优先级排序器
    - CategoryAnalyzer: 分类分析器

作者：AI Assistant
创建时间：2026-04-28
最后修改：2026-04-28
版本：6.0.0（内容完整性重构版）
"""

import logging
import math
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from collections import Counter

from .models import (
    RiskLevel,
    InspectionType,
    InspectionItem,
    InspectionReport,
)

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


class ChartGenerator:
    """
    图表生成器

    功能：
        - 生成健康评分环形图
        - 生成风险分布图
        - 生成状态统计图
    """

    @staticmethod
    def generate_health_donut(score: float) -> str:
        """
        生成健康评分环形图（SVG）

        参数:
            score: 健康评分(0-100)

        返回:
            str: SVG HTML代码
        """
        # 评分等级标准：健康(>=90) 亚健康(80-89) 风险(60-79) 高危(<60)
        if score >= 90:
            color = '#06d6a0'
            grade = '健康'
            grade_color = '#06d6a0'
        elif score >= 80:
            color = '#4cc9f0'
            grade = '亚健康'
            grade_color = '#4cc9f0'
        elif score >= 60:
            color = '#ffd166'
            grade = '风险'
            grade_color = '#ffd166'
        else:
            color = '#ef476f'
            grade = '高危'
            grade_color = '#ef476f'

        radius = 70
        circumference = 2 * math.pi * radius
        dash_offset = circumference * (1 - score / 100)

        return f'''
        <div class="donut-chart">
            <svg viewBox="0 0 200 200" class="donut-svg">
                <circle cx="100" cy="100" r="{radius}" fill="none"
                        stroke="#2a2a3e" stroke-width="16"/>
                <circle cx="100" cy="100" r="{radius}" fill="none"
                        stroke="{color}" stroke-width="16"
                        stroke-linecap="round"
                        stroke-dasharray="{circumference:.2f}"
                        stroke-dashoffset="{dash_offset:.2f}"
                        transform="rotate(-90 100 100)"
                        class="donut-progress"/>
                <text x="100" y="92" text-anchor="middle"
                      class="donut-score" fill="{color}">{score:.1f}</text>
                <text x="100" y="118" text-anchor="middle"
                      class="donut-grade" fill="{grade_color}">{grade}</text>
            </svg>
        </div>
        '''

    @staticmethod
    def generate_risk_distribution_chart(
        critical: int,
        high: int,
        medium: int,
        low: int,
        info: int
    ) -> str:
        """
        生成风险分布水平条形图

        参数:
            critical: 严重风险数量
            high: 高风险数量
            medium: 中风险数量
            low: 低风险数量
            info: 信息项数量

        返回:
            str: HTML代码
        """
        total = critical + high + medium + low + info
        if total == 0:
            return '<div class="chart-empty">暂无数据</div>'

        data = [
            ('严重', critical, '#ef476f'),
            ('高危', high, '#fd7e14'),
            ('中危', medium, '#ffd166'),
            ('低危', low, '#06d6a0'),
            ('信息', info, '#4cc9f0')
        ]

        max_val = max(critical, high, medium, low, info, 1)

        bars = []
        for label, value, color in data:
            if value > 0:
                width = (value / max_val) * 100
                percentage = (value / total) * 100
                bars.append(f'''
                    <div class="bar-row">
                        <div class="bar-label">{label}</div>
                        <div class="bar-track">
                            <div class="bar-fill" style="width: {width}%; background: {color};"></div>
                        </div>
                        <div class="bar-num">{value}</div>
                        <div class="bar-pct">{percentage:.1f}%</div>
                    </div>
                ''')
            else:
                bars.append(f'''
                    <div class="bar-row">
                        <div class="bar-label">{label}</div>
                        <div class="bar-track">
                            <div class="bar-fill" style="width: 0%; background: {color};"></div>
                        </div>
                        <div class="bar-num">0</div>
                        <div class="bar-pct">0.0%</div>
                    </div>
                ''')

        return f'''
        <div class="risk-chart">
            {''.join(bars)}
        </div>
        '''

    @staticmethod
    def generate_status_chart(
        pass_count: int,
        warning_count: int,
        fail_count: int
    ) -> str:
        """
        生成状态统计垂直柱状图

        参数:
            pass_count: 通过数量
            warning_count: 警告数量
            fail_count: 失败数量

        返回:
            str: HTML代码
        """
        total = pass_count + warning_count + fail_count
        if total == 0:
            return '<div class="chart-empty">暂无数据</div>'

        data = [
            ('通过', pass_count, '#06d6a0'),
            ('警告', warning_count, '#ffd166'),
            ('失败', fail_count, '#ef476f')
        ]

        max_val = max(pass_count, warning_count, fail_count, 1)

        bars = []
        for label, value, color in data:
            height = (value / max_val) * 100
            percentage = (value / total) * 100 if total > 0 else 0
            bars.append(f'''
                <div class="vbar-item">
                    <div class="vbar-val">{value}</div>
                    <div class="vbar-track">
                        <div class="vbar-fill" style="height: {height}%; background: {color};"></div>
                    </div>
                    <div class="vbar-label">{label}</div>
                    <div class="vbar-pct">{percentage:.1f}%</div>
                </div>
            ''')

        return f'''
        <div class="status-chart">
            {''.join(bars)}
        </div>
        '''

    @staticmethod
    def generate_category_pass_rate_chart(
        category_stats: Dict[str, Dict[str, Any]]
    ) -> str:
        """
        生成分类通过率水平条形图

        参数:
            category_stats: 分类统计数据

        返回:
            str: HTML代码
        """
        if not category_stats:
            return '<div class="chart-empty">暂无数据</div>'

        sorted_cats = sorted(
            category_stats.items(),
            key=lambda x: x[1]['pass_rate']
        )

        bars = []
        for type_key, stats in sorted_cats:
            insp_type = None
            for it in InspectionType:
                if it.value == type_key:
                    insp_type = it
                    break

            meta = INSPECTION_TYPE_META.get(insp_type, {})
            label = meta.get('label', type_key)
            color = meta.get('color', '#3b82f6')
            pass_rate = stats['pass_rate']
            total = stats['total']
            pass_count = stats['pass_count']

            rate_color = '#06d6a0' if pass_rate >= 80 else '#ffd166' if pass_rate >= 60 else '#ef476f'

            bars.append(f'''
                <div class="cat-bar-row">
                    <div class="cat-bar-label" style="color: {color};">{label}</div>
                    <div class="cat-bar-track">
                        <div class="cat-bar-fill" style="width: {pass_rate:.1f}%; background: {rate_color};"></div>
                    </div>
                    <div class="cat-bar-info">
                        <span class="cat-bar-rate" style="color: {rate_color};">{pass_rate:.0f}%</span>
                        <span class="cat-bar-detail">{pass_count}/{total}</span>
                    </div>
                </div>
            ''')

        return f'''
        <div class="category-chart">
            {''.join(bars)}
        </div>
        '''


class EnhancedReportGenerator:
    """
    增强型报告生成器

    功能：
        - 生成可视化HTML报告
        - 按风险等级排序展示
        - 提供交互式图表
        - 支持多种报告格式
    """

    HTML_TEMPLATE = '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>数据库巡检报告 - {instance_name}</title>
    <style>
        :root {{
            --bg-primary: #0f172a;
            --bg-secondary: #1e293b;
            --bg-card: #1e293b;
            --bg-card-hover: #263348;
            --bg-input: #0f172a;
            --border-color: #334155;
            --border-hover: #475569;
            --text-primary: #f1f5f9;
            --text-secondary: #94a3b8;
            --text-muted: #64748b;
            --accent: #3b82f6;
            --accent-hover: #2563eb;
            --critical: #ef476f;
            --high: #fd7e14;
            --medium: #ffd166;
            --low: #06d6a0;
            --info: #4cc9f0;
            --pass: #06d6a0;
            --warning: #ffd166;
            --fail: #ef476f;
            --shadow-sm: 0 1px 3px rgba(0,0,0,0.3);
            --shadow-md: 0 4px 12px rgba(0,0,0,0.4);
            --shadow-lg: 0 8px 30px rgba(0,0,0,0.5);
            --radius: 12px;
            --radius-sm: 8px;
        }}

        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC',
                         'Hiragino Sans GB', 'Microsoft YaHei', sans-serif;
            background: var(--bg-primary);
            color: var(--text-primary);
            line-height: 1.6;
            -webkit-font-smoothing: antialiased;
        }}

        .container {{
            max-width: 1400px;
            margin: 0 auto;
            padding: 24px;
        }}

        /* ========== Header ========== */
        .report-header {{
            background: linear-gradient(135deg, #1e3a5f 0%, #0f172a 50%, #1a1a3e 100%);
            border: 1px solid var(--border-color);
            border-radius: var(--radius);
            padding: 40px;
            margin-bottom: 24px;
            position: relative;
            overflow: hidden;
        }}

        .report-header::before {{
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 3px;
            background: linear-gradient(90deg, var(--accent), #8b5cf6, var(--critical));
        }}

        .header-top {{
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            margin-bottom: 30px;
        }}

        .header-title {{
            font-size: 28px;
            font-weight: 700;
            letter-spacing: -0.5px;
        }}

        .header-subtitle {{
            font-size: 14px;
            color: var(--text-secondary);
            margin-top: 6px;
        }}

        .header-badge {{
            background: rgba(59, 130, 246, 0.15);
            border: 1px solid rgba(59, 130, 246, 0.3);
            color: var(--accent);
            padding: 6px 16px;
            border-radius: 20px;
            font-size: 13px;
            font-weight: 600;
        }}

        .header-meta {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 16px;
        }}

        .meta-item {{
            background: rgba(255,255,255,0.04);
            border: 1px solid rgba(255,255,255,0.06);
            border-radius: var(--radius-sm);
            padding: 14px 16px;
        }}

        .meta-label {{
            font-size: 11px;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 4px;
        }}

        .meta-value {{
            font-size: 16px;
            font-weight: 600;
            color: var(--text-primary);
        }}

        /* ========== Stats Row ========== */
        .stats-row {{
            display: grid;
            grid-template-columns: repeat(5, 1fr);
            gap: 16px;
            margin-bottom: 24px;
        }}

        @media (max-width: 900px) {{
            .stats-row {{
                grid-template-columns: repeat(3, 1fr);
            }}
        }}

        @media (max-width: 600px) {{
            .stats-row {{
                grid-template-columns: repeat(2, 1fr);
            }}
        }}

        .stat-card {{
            background: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: var(--radius);
            padding: 20px;
            text-align: center;
            transition: all 0.3s ease;
            position: relative;
            overflow: hidden;
        }}

        .stat-card::after {{
            content: '';
            position: absolute;
            bottom: 0;
            left: 0;
            right: 0;
            height: 3px;
        }}

        .stat-card.critical::after {{ background: var(--critical); }}
        .stat-card.high::after {{ background: var(--high); }}
        .stat-card.medium::after {{ background: var(--medium); }}
        .stat-card.low::after {{ background: var(--low); }}
        .stat-card.info::after {{ background: var(--info); }}

        .stat-card:hover {{
            transform: translateY(-3px);
            border-color: var(--border-hover);
            box-shadow: var(--shadow-md);
        }}

        .stat-num {{
            font-size: 36px;
            font-weight: 700;
            line-height: 1;
            margin-bottom: 6px;
        }}

        .stat-card.critical .stat-num {{ color: var(--critical); }}
        .stat-card.high .stat-num {{ color: var(--high); }}
        .stat-card.medium .stat-num {{ color: var(--medium); }}
        .stat-card.low .stat-num {{ color: var(--low); }}
        .stat-card.info .stat-num {{ color: var(--info); }}

        .stat-label {{
            font-size: 13px;
            color: var(--text-secondary);
        }}

        /* ========== Card ========== */
        .card {{
            background: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: var(--radius);
            padding: 28px;
            margin-bottom: 24px;
        }}

        .card-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 24px;
        }}

        .card-title {{
            font-size: 18px;
            font-weight: 600;
            color: var(--text-primary);
            display: flex;
            align-items: center;
            gap: 10px;
        }}

        .card-title::before {{
            content: '';
            display: inline-block;
            width: 4px;
            height: 20px;
            background: var(--accent);
            border-radius: 2px;
        }}

        /* ========== Charts Grid ========== */
        .charts-grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 24px;
            margin-bottom: 24px;
        }}

        @media (max-width: 900px) {{
            .charts-grid {{
                grid-template-columns: 1fr;
            }}
        }}

        /* ========== Donut Chart ========== */
        .donut-chart {{
            display: flex;
            justify-content: center;
            align-items: center;
            padding: 10px 0;
        }}

        .donut-svg {{
            width: 200px;
            height: 200px;
        }}

        .donut-progress {{
            transition: stroke-dashoffset 1.5s ease;
        }}

        .donut-score {{
            font-size: 42px;
            font-weight: 700;
        }}

        .donut-grade {{
            font-size: 16px;
            font-weight: 500;
        }}

        /* ========== Risk Bar Chart ========== */
        .risk-chart {{
            padding: 8px 0;
        }}

        .bar-row {{
            display: flex;
            align-items: center;
            gap: 12px;
            margin-bottom: 14px;
        }}

        .bar-label {{
            width: 48px;
            font-size: 13px;
            color: var(--text-secondary);
            text-align: right;
            flex-shrink: 0;
        }}

        .bar-track {{
            flex: 1;
            height: 22px;
            background: rgba(255,255,255,0.05);
            border-radius: 4px;
            overflow: hidden;
        }}

        .bar-fill {{
            height: 100%;
            border-radius: 4px;
            transition: width 1s ease;
            min-width: 2px;
        }}

        .bar-num {{
            width: 32px;
            font-size: 14px;
            font-weight: 600;
            color: var(--text-primary);
            text-align: right;
            flex-shrink: 0;
        }}

        .bar-pct {{
            width: 52px;
            font-size: 12px;
            color: var(--text-muted);
            text-align: right;
            flex-shrink: 0;
        }}

        /* ========== Status Vertical Bar Chart ========== */
        .status-chart {{
            display: flex;
            justify-content: space-around;
            align-items: flex-end;
            height: 220px;
            padding: 20px 10px 0;
        }}

        .vbar-item {{
            text-align: center;
            flex: 1;
            max-width: 80px;
            display: flex;
            flex-direction: column;
            align-items: center;
        }}

        .vbar-val {{
            font-size: 20px;
            font-weight: 700;
            color: var(--text-primary);
            margin-bottom: 8px;
        }}

        .vbar-track {{
            width: 44px;
            height: 120px;
            background: rgba(255,255,255,0.05);
            border-radius: 6px;
            display: flex;
            align-items: flex-end;
            overflow: hidden;
        }}

        .vbar-fill {{
            width: 100%;
            border-radius: 6px 6px 0 0;
            transition: height 1s ease;
            min-height: 4px;
        }}

        .vbar-label {{
            font-size: 13px;
            color: var(--text-secondary);
            margin-top: 10px;
        }}

        .vbar-pct {{
            font-size: 11px;
            color: var(--text-muted);
            margin-top: 2px;
        }}

        /* ========== High Risk Section ========== */
        .high-risk-section {{
            background: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: var(--radius);
            padding: 28px;
            margin-bottom: 24px;
            border-left: 4px solid var(--critical);
        }}

        .risk-count-badge {{
            background: rgba(239, 71, 111, 0.15);
            color: var(--critical);
            padding: 4px 14px;
            border-radius: 16px;
            font-size: 13px;
            font-weight: 600;
        }}

        .risk-item {{
            background: rgba(255,255,255,0.03);
            border: 1px solid var(--border-color);
            border-radius: var(--radius-sm);
            padding: 20px;
            margin-bottom: 12px;
            border-left: 4px solid;
            transition: all 0.25s ease;
        }}

        .risk-item:hover {{
            background: var(--bg-card-hover);
            border-color: var(--border-hover);
        }}

        .risk-item.critical {{ border-left-color: var(--critical); }}
        .risk-item.high {{ border-left-color: var(--high); }}
        .risk-item.medium {{ border-left-color: var(--medium); }}
        .risk-item.low {{ border-left-color: var(--low); }}

        .risk-item-top {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 10px;
        }}

        .risk-item-name {{
            font-size: 15px;
            font-weight: 600;
            color: var(--text-primary);
        }}

        .level-tag {{
            padding: 3px 10px;
            border-radius: 4px;
            font-size: 11px;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}

        .level-tag.critical {{ background: rgba(239,71,111,0.2); color: var(--critical); }}
        .level-tag.high {{ background: rgba(253,126,20,0.2); color: var(--high); }}
        .level-tag.medium {{ background: rgba(255,209,102,0.2); color: var(--medium); }}
        .level-tag.low {{ background: rgba(6,214,160,0.2); color: var(--low); }}

        .risk-item-desc {{
            color: var(--text-secondary);
            font-size: 14px;
            margin-bottom: 10px;
            line-height: 1.5;
        }}

        .risk-item-meta {{
            display: flex;
            gap: 16px;
            font-size: 12px;
            color: var(--text-muted);
            margin-bottom: 10px;
            flex-wrap: wrap;
        }}

        .risk-item-suggestion {{
            background: rgba(59, 130, 246, 0.08);
            border: 1px solid rgba(59, 130, 246, 0.15);
            border-radius: 6px;
            padding: 12px 14px;
            font-size: 13px;
            color: #93c5fd;
            line-height: 1.5;
        }}

        .empty-state {{
            text-align: center;
            padding: 50px 20px;
            color: var(--text-muted);
        }}

        .empty-icon {{
            font-size: 40px;
            margin-bottom: 12px;
            color: var(--pass);
        }}

        .show-more {{
            text-align: center;
            color: var(--accent);
            margin-top: 16px;
            font-size: 13px;
            cursor: pointer;
            padding: 10px;
            border-radius: var(--radius-sm);
            transition: all 0.25s ease;
        }}

        .show-more:hover {{
            background: rgba(59, 130, 246, 0.08);
        }}

        /* ========== Details Section ========== */
        .details-section {{
            background: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: var(--radius);
            padding: 28px;
            margin-bottom: 24px;
        }}

        .toggle-btn {{
            background: rgba(59, 130, 246, 0.12);
            color: var(--accent);
            border: 1px solid rgba(59, 130, 246, 0.25);
            padding: 10px 22px;
            border-radius: var(--radius-sm);
            cursor: pointer;
            font-size: 13px;
            font-weight: 600;
            transition: all 0.25s ease;
        }}

        .toggle-btn:hover {{
            background: rgba(59, 130, 246, 0.2);
            border-color: rgba(59, 130, 246, 0.4);
        }}

        .collapsed {{
            display: none;
        }}

        .details-table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 20px;
            font-size: 13px;
        }}

        .details-table th {{
            background: rgba(255,255,255,0.04);
            padding: 12px 14px;
            text-align: left;
            font-weight: 600;
            color: var(--text-secondary);
            border-bottom: 1px solid var(--border-color);
            font-size: 12px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            position: sticky;
            top: 0;
        }}

        .details-table td {{
            padding: 12px 14px;
            border-bottom: 1px solid rgba(255,255,255,0.04);
            color: var(--text-primary);
        }}

        .details-table tr:hover td {{
            background: rgba(255,255,255,0.02);
        }}

        /* ========== Pagination ========== */
        .pagination {{
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 12px;
            margin-top: 24px;
            padding-top: 20px;
            border-top: 1px solid var(--border-color);
        }}

        .page-numbers {{
            display: flex;
            gap: 6px;
        }}

        .page-btn {{
            background: rgba(255,255,255,0.04);
            color: var(--text-secondary);
            border: 1px solid var(--border-color);
            padding: 8px 14px;
            border-radius: var(--radius-sm);
            cursor: pointer;
            font-size: 13px;
            font-weight: 500;
            transition: all 0.2s ease;
            min-width: 36px;
        }}

        .page-btn:hover:not(:disabled) {{
            background: rgba(59, 130, 246, 0.12);
            color: var(--accent);
            border-color: rgba(59, 130, 246, 0.3);
        }}

        .page-btn.active {{
            background: rgba(59, 130, 246, 0.2);
            color: var(--accent);
            border-color: var(--accent);
        }}

        .page-btn:disabled {{
            opacity: 0.4;
            cursor: not-allowed;
        }}

        .page-info {{
            color: var(--text-muted);
            font-size: 13px;
            margin-left: 12px;
        }}

        .status-tag {{
            display: inline-block;
            padding: 2px 8px;
            border-radius: 4px;
            font-size: 11px;
            font-weight: 600;
        }}

        .status-tag.pass {{ background: rgba(6,214,160,0.15); color: var(--pass); }}
        .status-tag.warning {{ background: rgba(255,209,102,0.15); color: var(--warning); }}
        .status-tag.fail {{ background: rgba(239,71,111,0.15); color: var(--fail); }}

        /* ========== Footer ========== */
        .report-footer {{
            text-align: center;
            padding: 30px;
            color: var(--text-muted);
            font-size: 12px;
            border-top: 1px solid var(--border-color);
            margin-top: 10px;
        }}

        .chart-empty {{
            text-align: center;
            padding: 50px 20px;
            color: var(--text-muted);
            font-size: 14px;
        }}

        /* ========== Nav ========== */
        .report-nav {{
            background: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: var(--radius);
            padding: 16px 24px;
            margin-bottom: 24px;
            position: sticky;
            top: 12px;
            z-index: 100;
            display: flex;
            gap: 8px;
            flex-wrap: wrap;
            align-items: center;
        }}

        .nav-label {{
            font-size: 12px;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-right: 8px;
        }}

        .nav-link {{
            padding: 6px 14px;
            border-radius: 6px;
            font-size: 13px;
            color: var(--text-secondary);
            text-decoration: none;
            transition: all 0.2s ease;
            border: 1px solid transparent;
        }}

        .nav-link:hover {{
            background: rgba(59, 130, 246, 0.1);
            color: var(--accent);
            border-color: rgba(59, 130, 246, 0.2);
        }}

        /* ========== Executive Summary ========== */
        .executive-summary {{
            background: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: var(--radius);
            padding: 28px;
            margin-bottom: 24px;
        }}

        .summary-text {{
            font-size: 15px;
            color: var(--text-secondary);
            line-height: 1.8;
            margin-bottom: 20px;
        }}

        .summary-text strong {{
            color: var(--text-primary);
        }}

        .summary-highlights {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 16px;
        }}

        .highlight-item {{
            background: rgba(255,255,255,0.03);
            border: 1px solid var(--border-color);
            border-radius: var(--radius-sm);
            padding: 16px;
            display: flex;
            align-items: center;
            gap: 14px;
        }}

        .highlight-icon {{
            width: 40px;
            height: 40px;
            border-radius: 10px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 18px;
            font-weight: 700;
            flex-shrink: 0;
        }}

        .highlight-icon.score {{ background: rgba(59,130,246,0.15); color: var(--accent); }}
        .highlight-icon.critical {{ background: rgba(239,71,111,0.15); color: var(--critical); }}
        .highlight-icon.warning {{ background: rgba(255,209,102,0.15); color: var(--warning); }}
        .highlight-icon.pass {{ background: rgba(6,214,160,0.15); color: var(--pass); }}

        .highlight-content {{
            flex: 1;
        }}

        .highlight-value {{
            font-size: 20px;
            font-weight: 700;
            color: var(--text-primary);
        }}

        .highlight-label {{
            font-size: 12px;
            color: var(--text-muted);
        }}

        /* ========== Category Pass Rate Chart ========== */
        .category-chart {{
            padding: 8px 0;
        }}

        .cat-bar-row {{
            display: flex;
            align-items: center;
            gap: 12px;
            margin-bottom: 12px;
        }}

        .cat-bar-label {{
            width: 72px;
            font-size: 13px;
            font-weight: 600;
            text-align: right;
            flex-shrink: 0;
        }}

        .cat-bar-track {{
            flex: 1;
            height: 20px;
            background: rgba(255,255,255,0.05);
            border-radius: 4px;
            overflow: hidden;
        }}

        .cat-bar-fill {{
            height: 100%;
            border-radius: 4px;
            transition: width 1s ease;
            min-width: 2px;
        }}

        .cat-bar-info {{
            width: 80px;
            display: flex;
            align-items: center;
            gap: 6px;
            flex-shrink: 0;
        }}

        .cat-bar-rate {{
            font-size: 14px;
            font-weight: 700;
        }}

        .cat-bar-detail {{
            font-size: 11px;
            color: var(--text-muted);
        }}

        /* ========== Category Section ========== */
        .category-section {{
            background: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: var(--radius);
            padding: 28px;
            margin-bottom: 24px;
        }}

        .category-section-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
            padding-bottom: 16px;
            border-bottom: 1px solid var(--border-color);
        }}

        .category-title {{
            font-size: 17px;
            font-weight: 600;
            color: var(--text-primary);
            display: flex;
            align-items: center;
            gap: 10px;
        }}

        .category-dot {{
            width: 10px;
            height: 10px;
            border-radius: 50%;
            display: inline-block;
        }}

        .category-desc {{
            font-size: 13px;
            color: var(--text-muted);
            margin-bottom: 20px;
        }}

        .category-stats-bar {{
            display: flex;
            gap: 20px;
            margin-bottom: 20px;
            flex-wrap: wrap;
        }}

        .cat-stat {{
            display: flex;
            align-items: center;
            gap: 6px;
            font-size: 13px;
        }}

        .cat-stat-label {{
            color: var(--text-muted);
        }}

        .cat-stat-value {{
            font-weight: 600;
        }}

        .cat-stat-value.pass {{ color: var(--pass); }}
        .cat-stat-value.warning {{ color: var(--warning); }}
        .cat-stat-value.fail {{ color: var(--fail); }}

        .category-pass-bar {{
            height: 6px;
            background: rgba(255,255,255,0.05);
            border-radius: 3px;
            overflow: hidden;
            margin-bottom: 20px;
        }}

        .category-pass-fill {{
            height: 100%;
            border-radius: 3px;
            transition: width 1s ease;
        }}

        .category-items {{
            display: grid;
            gap: 10px;
        }}

        .cat-item {{
            display: grid;
            grid-template-columns: 1fr auto auto auto;
            gap: 16px;
            align-items: center;
            padding: 14px 16px;
            background: rgba(255,255,255,0.02);
            border: 1px solid rgba(255,255,255,0.04);
            border-radius: var(--radius-sm);
            font-size: 13px;
            transition: all 0.2s ease;
        }}

        .cat-item:hover {{
            background: rgba(255,255,255,0.04);
            border-color: var(--border-color);
        }}

        .cat-item-name {{
            font-weight: 500;
            color: var(--text-primary);
        }}

        .cat-item-desc {{
            color: var(--text-muted);
            font-size: 12px;
            margin-top: 4px;
        }}

        .cat-item-value {{
            color: var(--text-secondary);
            font-size: 12px;
            text-align: right;
            max-width: 160px;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }}

        .cat-item-suggestion {{
            color: #93c5fd;
            font-size: 12px;
            max-width: 200px;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }}

        /* ========== Recommendations Section ========== */
        .recommendations-section {{
            background: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: var(--radius);
            padding: 28px;
            margin-bottom: 24px;
            border-left: 4px solid var(--accent);
        }}

        .rec-item {{
            display: flex;
            gap: 16px;
            padding: 16px;
            background: rgba(255,255,255,0.02);
            border: 1px solid rgba(255,255,255,0.04);
            border-radius: var(--radius-sm);
            margin-bottom: 10px;
            transition: all 0.2s ease;
        }}

        .rec-item:hover {{
            background: rgba(255,255,255,0.04);
            border-color: var(--border-color);
        }}

        .rec-priority {{
            width: 32px;
            height: 32px;
            border-radius: 8px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 14px;
            font-weight: 700;
            flex-shrink: 0;
        }}

        .rec-priority.p1 {{ background: rgba(239,71,111,0.2); color: var(--critical); }}
        .rec-priority.p2 {{ background: rgba(253,126,20,0.2); color: var(--high); }}
        .rec-priority.p3 {{ background: rgba(255,209,102,0.2); color: var(--medium); }}

        .rec-content {{
            flex: 1;
        }}

        .rec-title {{
            font-size: 14px;
            font-weight: 600;
            color: var(--text-primary);
            margin-bottom: 4px;
        }}

        .rec-detail {{
            font-size: 13px;
            color: var(--text-secondary);
            line-height: 1.5;
        }}

        .rec-meta {{
            display: flex;
            gap: 12px;
            margin-top: 6px;
            font-size: 11px;
            color: var(--text-muted);
        }}

        /* ========== Section Anchor Offset ========== */
        .section-anchor {{
            scroll-margin-top: 80px;
        }}

        /* ========== Animations ========== */
        @keyframes fadeInUp {{
            from {{
                opacity: 0;
                transform: translateY(16px);
            }}
            to {{
                opacity: 1;
                transform: translateY(0);
            }}
        }}

        .animate-in {{
            animation: fadeInUp 0.5s ease forwards;
            opacity: 0;
        }}
    </style>
</head>
<body>
    <div class="container">
        {content}
    </div>

    <script>
        function toggleDetails() {{
            var details = document.getElementById('full-details');
            var btn = document.getElementById('toggle-btn');
            if (details.classList.contains('collapsed')) {{
                details.classList.remove('collapsed');
                btn.textContent = '收起详细列表';
            }} else {{
                details.classList.add('collapsed');
                btn.textContent = '展开详细列表';
            }}
        }}

        function toggleCategory(catId) {{
            var items = document.getElementById(catId);
            var btn = document.getElementById(catId + '-btn');
            if (items.classList.contains('collapsed')) {{
                items.classList.remove('collapsed');
                btn.textContent = '收起';
            }} else {{
                items.classList.add('collapsed');
                btn.textContent = '展开全部';
            }}
        }}

        // 分页功能
        var currentPage = 0;
        var totalPages = document.querySelectorAll('.page-content').length;

        function goToPage(page) {{
            if (page < 0 || page >= totalPages) return;

            // 隐藏所有页面
            var pages = document.querySelectorAll('.page-content');
            pages.forEach(function(p) {{
                p.style.display = 'none';
            }});

            // 显示目标页面
            var targetPage = document.getElementById('page-' + page);
            if (targetPage) {{
                targetPage.style.display = 'table-row-group';
            }}

            // 更新页码按钮状态
            var pageBtns = document.querySelectorAll('.page-numbers .page-btn');
            pageBtns.forEach(function(btn) {{
                btn.classList.remove('active');
                if (parseInt(btn.getAttribute('data-page')) === page) {{
                    btn.classList.add('active');
                }}
            }});

            // 更新上一页/下一页按钮状态
            var prevBtn = document.getElementById('prev-btn');
            var nextBtn = document.getElementById('next-btn');
            if (prevBtn) prevBtn.disabled = page === 0;
            if (nextBtn) nextBtn.disabled = page === totalPages - 1;

            // 更新当前页显示
            var currentPageSpan = document.getElementById('current-page');
            if (currentPageSpan) currentPageSpan.textContent = page + 1;

            currentPage = page;
        }}

        function prevPage() {{
            goToPage(currentPage - 1);
        }}

        function nextPage() {{
            goToPage(currentPage + 1);
        }}

        document.addEventListener('DOMContentLoaded', function() {{
            var cards = document.querySelectorAll('.stat-card, .risk-item, .rec-item');
            cards.forEach(function(card, index) {{
                card.classList.add('animate-in');
                card.style.animationDelay = (index * 60) + 'ms';
            }});

            var bars = document.querySelectorAll('.bar-fill, .cat-bar-fill');
            bars.forEach(function(bar) {{
                var finalWidth = bar.style.width;
                bar.style.width = '0';
                setTimeout(function() {{
                    bar.style.width = finalWidth;
                }}, 400);
            }});

            var vbars = document.querySelectorAll('.vbar-fill');
            vbars.forEach(function(vbar) {{
                var finalHeight = vbar.style.height;
                vbar.style.height = '0';
                setTimeout(function() {{
                    vbar.style.height = finalHeight;
                }}, 400);
            }});

            var progress = document.querySelector('.donut-progress');
            if (progress) {{
                var finalOffset = progress.getAttribute('stroke-dashoffset');
                var circumference = progress.getAttribute('stroke-dasharray');
                progress.setAttribute('stroke-dashoffset', circumference);
                setTimeout(function() {{
                    progress.setAttribute('stroke-dashoffset', finalOffset);
                }}, 400);
            }}

            var passFills = document.querySelectorAll('.category-pass-fill');
            passFills.forEach(function(fill) {{
                var finalWidth = fill.style.width;
                fill.style.width = '0';
                setTimeout(function() {{
                    fill.style.width = finalWidth;
                }}, 500);
            }});
        }});
    </script>
</body>
</html>'''

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

        return EnhancedReportGenerator.HTML_TEMPLATE.format(
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
