"""
db_inspector/__init__.py
db_inspector - 数据库实例巡检与报告生成

文件功能：提供数据库实例健康巡检、报告生成、趋势分析能力
主要类：
    - InspectorSkill: 巡检技能统一入口

功能特性：
1. 实例健康巡检 - 全面检查数据库健康状态
2. 巡检报告生成 - 生成详细巡检报告（文本/HTML/Markdown/JSON）
3. 配置检查 - 检查数据库配置是否合理
4. 性能基线 - 建立性能基线并对比
5. 趋势分析 - 分析历史趋势变化
6. 风险预警 - 识别潜在风险点

使用示例：
    from dbskiter.db_inspector import InspectorSkill, ErrorCode

    skill = InspectorSkill(connector)

    # 执行完整巡检
    result = skill.inspect()
    if result["success"]:
        report = result["data"]
        print(f"健康评分: {report['health_score']}")

    # 生成HTML报告
    html_result = skill.generate_html_report(report)

    # 创建性能基线
    baseline_result = skill.create_baseline("production_baseline")

    # 对比基线
    comparison = skill.compare_with_baseline(report)

作者：Magiczc
创建时间：2026-04-22
最后修改：2026-04-23
版本：3.0.0（模块化重构版）
"""

# 数据模型
from .models import (
    ErrorCode,
    ErrorMessage,
    RiskLevel,
    InspectionType,
    InspectionItem,
    InspectionReport,
    PerformanceBaseline,)

# 响应函数（从shared模块导入）
from dbskiter.shared.error_handler import create_success_response, create_error_response

# 工具类
from .utils import (
    HealthScoreCalculator,
    ReportFormatter,
    BaselineManager,
    InspectionAggregator,
    TrendAnalyzer,
)

# 统一入口
from .skill import InspectorSkill

__all__ = [
    # 数据模型
    "ErrorCode",
    "ErrorMessage",
    "RiskLevel",
    "InspectionType",
    "InspectionItem",
    "InspectionReport",
    "PerformanceBaseline",
    "create_success_response",
    "create_error_response",
    # 工具类
    "HealthScoreCalculator",
    "ReportFormatter",
    "BaselineManager",
    "InspectionAggregator",
    "TrendAnalyzer",
    # 主要入口
    "InspectorSkill",
]
