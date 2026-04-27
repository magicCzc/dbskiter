"""
AAS可视化模块

文件功能：生成AAS指标的可视化图表（ASCII图表、HTML图表）
主要类：AASVisualizer - AAS可视化生成器

支持图表类型：
1. 趋势折线图 - 展示AAS随时间变化
2. 堆叠面积图 - 展示AAS分类占比
3. 柱状图 - 对比不同时间段的AAS
4. 仪表盘 - 展示当前AAS状态
5. 热力图 - 展示AAS在时间上的分布

使用示例：
    from dbskiter.shared.aas_visualizer import AASVisualizer
    from dbskiter.shared.mysql_aas_calculator import MySQLAASCalculator
    
    calculator = MySQLAASCalculator(connector)
    visualizer = AASVisualizer(calculator)
    
    # 生成趋势图
    trend_chart = visualizer.generate_trend_chart(minutes=60)
    print(trend_chart)
    
    # 生成HTML报告
    html_report = visualizer.generate_html_report()
    with open('aas_report.html', 'w') as f:
        f.write(html_report)

作者：AI Assistant
创建时间：2026-04-21
"""

import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
from collections import defaultdict
import math

logger = logging.getLogger(__name__)


@dataclass
class ChartConfig:
    """图表配置"""
    width: int = 80
    height: int = 20
    title: str = ""
    show_legend: bool = True
    show_grid: bool = True
    color_scheme: str = "default"


class AASVisualizer:
    """
    AAS可视化生成器
    
    核心功能：
    1. ASCII图表生成 - 命令行友好
    2. HTML图表生成 - 浏览器展示
    3. 多种图表类型 - 趋势、堆叠、柱状、仪表盘
    4. 实时更新支持 - 动态刷新
    
    使用示例：
        >>> visualizer = AASVisualizer(calculator)
        >>> 
        >>> # ASCII趋势图
        >>> chart = visualizer.generate_trend_chart(minutes=30)
        >>> print(chart)
        >>> 
        >>> # HTML完整报告
        >>> html = visualizer.generate_html_report()
    """
    
    # ASCII字符集
    BLOCK_CHARS = ['▁', '▂', '▃', '▄', '▅', '▆', '▇', '█']
    LINE_CHARS = {
        'horizontal': '─',
        'vertical': '│',
        'corner_tl': '┌',
        'corner_tr': '┐',
        'corner_bl': '└',
        'corner_br': '┘',
        'cross': '┼',
        't_top': '┬',
        't_bottom': '┴',
        't_left': '├',
        't_right': '┤'
    }
    
    def __init__(self, aas_calculator, config: Optional[ChartConfig] = None):
        """
        初始化可视化器
        
        参数:
            aas_calculator: AAS计算器实例
            config: 图表配置
        """
        self.calculator = aas_calculator
        self.config = config or ChartConfig()
    
    def generate_trend_chart(
        self,
        minutes: int = 60,
        metric: str = 'total'
    ) -> str:
        """
        生成AAS趋势折线图（ASCII）
        
        参数:
            minutes: 时间范围（分钟）
            metric: 指标类型（total/cpu/io/lock/network/other）
            
        返回:
            str: ASCII图表字符串
            
        示例:
            >>> chart = visualizer.generate_trend_chart(minutes=30)
            >>> print(chart)
        """
        # 获取历史数据
        history = self.calculator.get_aas_history(minutes=minutes, interval=0)
        
        if not history:
            return "暂无AAS历史数据"
        
        # 提取数据
        timestamps = [h.timestamp for h in history]
        values = self._extract_metric_values(history, metric)
        
        if not values:
            return f"无法获取指标: {metric}"
        
        # 生成图表
        return self._create_line_chart(
            timestamps=timestamps,
            values=values,
            title=f"AAS {metric.upper()} 趋势 (最近{minutes}分钟)",
            y_label="AAS",
            x_label="时间"
        )
    
    def generate_stacked_chart(self, minutes: int = 60) -> str:
        """
        生成AAS分类堆叠图（ASCII）
        
        参数:
            minutes: 时间范围（分钟）
            
        返回:
            str: ASCII堆叠图字符串
            
        示例:
            >>> chart = visualizer.generate_stacked_chart(minutes=30)
            >>> print(chart)
        """
        history = self.calculator.get_aas_history(minutes=minutes, interval=0)
        
        if not history:
            return "暂无AAS历史数据"
        
        # 简化展示：显示各类别的平均值
        avg_cpu = sum(h.cpu for h in history) / len(history)
        avg_io = sum(h.io for h in history) / len(history)
        avg_lock = sum(h.lock for h in history) / len(history)
        avg_network = sum(h.network for h in history) / len(history)
        avg_other = sum(h.other for h in history) / len(history)
        
        categories = [
            ('CPU', avg_cpu, '█'),
            ('IO', avg_io, '▓'),
            ('Lock', avg_lock, '▒'),
            ('Network', avg_network, '░'),
            ('Other', avg_other, ' ')
        ]
        
        lines = [
            f"AAS分类占比 (最近{minutes}分钟)",
            "=" * 50,
            ""
        ]
        
        max_val = max(c[1] for c in categories) or 1
        
        for name, value, char in sorted(categories, key=lambda x: x[1], reverse=True):
            bar_length = int((value / max_val) * 40)
            bar = char * bar_length
            percentage = (value / sum(c[1] for c in categories)) * 100 if sum(c[1] for c in categories) > 0 else 0
            lines.append(f"{name:8} {bar:40} {value:6.2f} ({percentage:5.1f}%)")
        
        lines.extend([
            "",
            "=" * 50
        ])
        
        return "\n".join(lines)
    
    def generate_gauge_chart(self) -> str:
        """
        生成AAS仪表盘（ASCII）
        
        返回:
            str: ASCII仪表盘字符串
            
        示例:
            >>> gauge = visualizer.generate_gauge_chart()
            >>> print(gauge)
        """
        # 获取当前AAS
        current = self.calculator.calculate_current_aas()
        
        if not current:
            return "无法获取当前AAS"
        
        vcpu = current.vcpu_count or 8
        aas_value = current.total
        
        # 计算百分比（相对于vCPU）
        percentage = min(100, (aas_value / vcpu) * 100)
        
        # 确定状态
        if percentage < 70:
            status = "健康"
        elif percentage < 100:
            status = "警告"
        else:
            status = "过载"
        
        # 生成仪表盘
        width = 40
        filled = int((percentage / 100) * width)
        bar = "█" * filled + "░" * (width - filled)
        
        lines = [
            "",
            "      AAS 仪表盘",
            "",
            f"   0% |{bar}| 100%",
            f"      {percentage:5.1f}% [{status}]",
            "",
            f"   当前AAS: {aas_value:.2f}",
            f"   vCPU数量: {vcpu}",
            f"   健康状态: {current.health_status}",
            "",
            "   分类详情:",
            f"     CPU:    {current.cpu:6.2f} ({current.cpu_percentage:5.1f}%)",
            f"     IO:     {current.io:6.2f} ({current.io_percentage:5.1f}%)",
            f"     Lock:   {current.lock:6.2f} ({current.lock_percentage:5.1f}%)",
            f"     Network:{current.network:6.2f}",
            f"     Other:  {current.other:6.2f}",
            ""
        ]
        
        return "\n".join(lines)
    
    def generate_heatmap(self, hours: int = 24) -> str:
        """
        生成AAS热力图（ASCII）
        
        参数:
            hours: 时间范围（小时）
            
        返回:
            str: ASCII热力图字符串
            
        示例:
            >>> heatmap = visualizer.generate_heatmap(hours=24)
            >>> print(heatmap)
        """
        history = self.calculator.get_aas_history(minutes=hours * 60, interval=300)
        
        if len(history) < 6:
            return "数据不足，无法生成热力图（至少需要6个数据点）"
        
        # 按小时分组
        hourly_data = defaultdict(list)
        for h in history:
            hour = h.timestamp.hour
            hourly_data[hour].append(h.total)
        
        # 计算每小时的平均值
        hourly_avg = {}
        for hour in range(24):
            if hour in hourly_data and hourly_data[hour]:
                hourly_avg[hour] = sum(hourly_data[hour]) / len(hourly_data[hour])
            else:
                hourly_avg[hour] = 0
        
        # 确定最大值用于归一化
        max_val = max(hourly_avg.values()) or 1
        
        # 热力图字符（从低到高）
        heat_chars = [' ', '░', '▒', '▓', '█']
        
        lines = [
            f"AAS热力图 (最近{hours}小时)",
            "=" * 60,
            "",
            "小时: 00 01 02 03 04 05 06 07 08 09 10 11 12 13 14 15 16 17 18 19 20 21 22 23",
            ""
        ]
        
        # 生成热力行
        heat_row = "AAS:  "
        for hour in range(24):
            val = hourly_avg[hour]
            # 归一化到0-4
            idx = min(4, int((val / max_val) * 4))
            heat_row += heat_chars[idx] + "  "
        
        lines.append(heat_row)
        lines.extend([
            "",
            "图例:  ░低  ▒中低  ▓中高  █高",
            f"最大AAS: {max_val:.2f}",
            "=" * 60
        ])
        
        return "\n".join(lines)
    
    def generate_comparison_chart(
        self,
        periods: List[Tuple[str, int]] = None
    ) -> str:
        """
        生成多时段对比图（ASCII柱状图）
        
        参数:
            periods: 时段列表 [(名称, 分钟数), ...]
            
        返回:
            str: ASCII柱状图字符串
            
        示例:
            >>> periods = [("最近1小时", 60), ("最近1天", 1440)]
            >>> chart = visualizer.generate_comparison_chart(periods)
        """
        if periods is None:
            periods = [
                ("最近15分钟", 15),
                ("最近1小时", 60),
                ("最近6小时", 360),
                ("最近24小时", 1440)
            ]
        
        lines = [
            "AAS时段对比",
            "=" * 60,
            ""
        ]
        
        data = []
        for name, minutes in periods:
            history = self.calculator.get_aas_history(minutes=minutes)
            if history:
                avg_aas = sum(h.total for h in history) / len(history)
                max_aas = max(h.total for h in history)
                data.append((name, avg_aas, max_aas))
            else:
                data.append((name, 0, 0))
        
        # 找出最大值用于缩放
        max_val = max(d[1] for d in data) or 1
        
        # 生成柱状图
        for name, avg_val, max_val_item in data:
            bar_length = int((avg_val / max_val) * 40)
            bar = "█" * bar_length
            lines.append(f"{name:12} {bar:40} 平均:{avg_val:5.2f} 最大:{max_val_item:5.2f}")
        
        lines.extend([
            "",
            "=" * 60
        ])
        
        return "\n".join(lines)
    
    def generate_html_report(self, minutes: int = 60) -> str:
        """
        生成HTML格式的完整报告
        
        参数:
            minutes: 分析时间范围（分钟）
            
        返回:
            str: HTML报告字符串
            
        示例:
            >>> html = visualizer.generate_html_report(minutes=60)
            >>> with open('report.html', 'w') as f:
            ...     f.write(html)
        """
        # 获取数据
        current = self.calculator.calculate_current_aas()
        history = self.calculator.get_aas_history(minutes=minutes)
        bottleneck = self.calculator.identify_bottleneck()
        
        # 准备图表数据（JSON格式）
        chart_data = self._prepare_chart_data(history)
        
        html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>MySQL AAS分析报告</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            margin: 20px;
            background-color: #f5f5f5;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background-color: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        h1 {{
            color: #333;
            border-bottom: 2px solid #4CAF50;
            padding-bottom: 10px;
        }}
        .metrics-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin: 20px 0;
        }}
        .metric-card {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px;
            border-radius: 8px;
            text-align: center;
        }}
        .metric-value {{
            font-size: 2em;
            font-weight: bold;
        }}
        .metric-label {{
            font-size: 0.9em;
            opacity: 0.9;
        }}
        .status-healthy {{ color: #4CAF50; }}
        .status-warning {{ color: #FF9800; }}
        .status-overloaded {{ color: #F44336; }}
        .chart-container {{
            margin: 30px 0;
            padding: 20px;
            background-color: #fafafa;
            border-radius: 8px;
        }}
        .recommendations {{
            background-color: #fff3cd;
            border-left: 4px solid #ffc107;
            padding: 15px;
            margin: 20px 0;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }}
        th, td {{
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }}
        th {{
            background-color: #4CAF50;
            color: white;
        }}
    </style>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
</head>
<body>
    <div class="container">
        <h1>MySQL AAS (Average Active Sessions) 分析报告</h1>
        <p>生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        
        <div class="metrics-grid">
            <div class="metric-card">
                <div class="metric-value">{current.total:.2f}</div>
                <div class="metric-label">总AAS</div>
            </div>
            <div class="metric-card">
                <div class="metric-value">{current.cpu:.2f}</div>
                <div class="metric-label">CPU</div>
            </div>
            <div class="metric-card">
                <div class="metric-value">{current.io:.2f}</div>
                <div class="metric-label">IO</div>
            </div>
            <div class="metric-card">
                <div class="metric-value">{current.lock:.2f}</div>
                <div class="metric-label">Lock</div>
            </div>
        </div>
        
        <div class="chart-container">
            <h2>AAS趋势图</h2>
            <canvas id="trendChart" width="400" height="200"></canvas>
        </div>
        
        <div class="chart-container">
            <h2>AAS分类占比</h2>
            <canvas id="pieChart" width="400" height="200"></canvas>
        </div>
        
        <h2>瓶颈分析</h2>
        <p><strong>主要原因:</strong> {bottleneck.primary_cause if bottleneck else 'N/A'}</p>
        <p><strong>严重程度:</strong> <span class="status-{bottleneck.severity if bottleneck else 'unknown'}">{bottleneck.severity if bottleneck else 'N/A'}</span></p>
        <p><strong>描述:</strong> {bottleneck.description if bottleneck else 'N/A'}</p>
        
        <div class="recommendations">
            <h3>优化建议</h3>
            <ul>
                {''.join(f'<li>{rec}</li>' for rec in (bottleneck.recommendations if bottleneck else []))}
            </ul>
        </div>
        
        <h2>历史数据</h2>
        <table>
            <tr>
                <th>时间</th>
                <th>总AAS</th>
                <th>CPU</th>
                <th>IO</th>
                <th>Lock</th>
                <th>状态</th>
            </tr>
            {''.join(f'''
            <tr>
                <td>{h.timestamp.strftime('%H:%M:%S')}</td>
                <td>{h.total:.2f}</td>
                <td>{h.cpu:.2f}</td>
                <td>{h.io:.2f}</td>
                <td>{h.lock:.2f}</td>
                <td class="status-{h.health_status}">{h.health_status}</td>
            </tr>
            ''' for h in history[-10:])}
        </table>
    </div>
    
    <script>
        // 趋势图
        const trendCtx = document.getElementById('trendChart').getContext('2d');
        new Chart(trendCtx, {{
            type: 'line',
            data: {{
                labels: {chart_data['timestamps']},
                datasets: [
                    {{
                        label: '总AAS',
                        data: {chart_data['total']},
                        borderColor: 'rgb(75, 192, 192)',
                        tension: 0.1
                    }},
                    {{
                        label: 'CPU',
                        data: {chart_data['cpu']},
                        borderColor: 'rgb(255, 99, 132)',
                        tension: 0.1
                    }},
                    {{
                        label: 'IO',
                        data: {chart_data['io']},
                        borderColor: 'rgb(54, 162, 235)',
                        tension: 0.1
                    }}
                ]
            }},
            options: {{
                responsive: true,
                scales: {{
                    y: {{
                        beginAtZero: true
                    }}
                }}
            }}
        }});
        
        // 饼图
        const pieCtx = document.getElementById('pieChart').getContext('2d');
        new Chart(pieCtx, {{
            type: 'doughnut',
            data: {{
                labels: ['CPU', 'IO', 'Lock', 'Network', 'Other'],
                datasets: [{{
                    data: [{current.cpu}, {current.io}, {current.lock}, {current.network}, {current.other}],
                    backgroundColor: [
                        'rgb(255, 99, 132)',
                        'rgb(54, 162, 235)',
                        'rgb(255, 205, 86)',
                        'rgb(75, 192, 192)',
                        'rgb(201, 203, 207)'
                    ]
                }}]
            }}
        }});
    </script>
</body>
</html>"""
        
        return html
    
    def _extract_metric_values(
        self,
        history: List[Any],
        metric: str
    ) -> List[float]:
        """提取指定指标的值列表"""
        metric_map = {
            'total': lambda h: h.total,
            'cpu': lambda h: h.cpu,
            'io': lambda h: h.io,
            'lock': lambda h: h.lock,
            'network': lambda h: h.network,
            'other': lambda h: h.other
        }
        
        getter = metric_map.get(metric)
        if not getter:
            return []
        
        return [getter(h) for h in history]
    
    def _create_line_chart(
        self,
        timestamps: List[datetime],
        values: List[float],
        title: str,
        y_label: str,
        x_label: str
    ) -> str:
        """创建ASCII折线图"""
        if not values:
            return "无数据"
        
        width = self.config.width
        height = self.config.height
        
        # 数据归一化
        min_val = min(values)
        max_val = max(values)
        val_range = max_val - min_val if max_val != min_val else 1
        
        normalized = [
            int(((v - min_val) / val_range) * (height - 1))
            for v in values
        ]
        
        # 采样数据点以适应宽度
        if len(normalized) > width:
            step = len(normalized) // width
            normalized = normalized[::step][:width]
        
        # 创建图表
        lines = [title, "=" * width]
        
        # Y轴和网格
        for row in range(height - 1, -1, -1):
            line = ""
            for col in range(len(normalized)):
                if normalized[col] == row:
                    line += "●"
                elif normalized[col] > row:
                    line += "│"
                else:
                    line += " "
            
            # Y轴标签
            val = min_val + (val_range * row / (height - 1))
            lines.append(f"{val:6.1f} │{line}")
        
        # X轴
        lines.append("       └" + "─" * len(normalized))
        
        # X轴标签
        if timestamps:
            start_time = timestamps[0].strftime("%H:%M")
            end_time = timestamps[-1].strftime("%H:%M")
            lines.append(f"       {start_time:>{len(normalized)//2}}{end_time:>{len(normalized)//2}}")
        
        lines.append("=" * width)
        lines.append(f"{y_label} 范围: {min_val:.2f} - {max_val:.2f}")
        
        return "\n".join(lines)
    
    def _prepare_chart_data(self, history: List[Any]) -> Dict[str, Any]:
        """准备图表数据（JSON格式）"""
        if not history:
            return {
                'timestamps': [],
                'total': [],
                'cpu': [],
                'io': [],
                'lock': []
            }
        
        return {
            'timestamps': [h.timestamp.strftime('%H:%M:%S') for h in history],
            'total': [h.total for h in history],
            'cpu': [h.cpu for h in history],
            'io': [h.io for h in history],
            'lock': [h.lock for h in history]
        }


# 便捷函数
def visualize_aas_trend(calculator, minutes: int = 60) -> str:
    """
    便捷函数：生成AAS趋势图
    
    参数:
        calculator: AAS计算器
        minutes: 时间范围（分钟）
        
    返回:
        str: ASCII趋势图
    """
    visualizer = AASVisualizer(calculator)
    return visualizer.generate_trend_chart(minutes=minutes)


def visualize_aas_gauge(calculator) -> str:
    """
    便捷函数：生成AAS仪表盘
    
    参数:
        calculator: AAS计算器
        
    返回:
        str: ASCII仪表盘
    """
    visualizer = AASVisualizer(calculator)
    return visualizer.generate_gauge_chart()
