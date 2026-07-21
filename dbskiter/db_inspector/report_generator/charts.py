import math
from typing import Dict, Any, List, Optional


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


