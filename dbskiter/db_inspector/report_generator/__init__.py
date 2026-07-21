"""
db_inspector/report_generator/__init__.py
数据库巡检报告生成器包 - 统一入口

保持向后兼容：所有类从包级别可直接导入
"""

from .generator import (
    INSPECTION_TYPE_META,
    RiskPrioritizer,
    CategoryAnalyzer,
    EnhancedReportGenerator,
)
from .charts import ChartGenerator

__all__ = [
    "INSPECTION_TYPE_META",
    "RiskPrioritizer",
    "CategoryAnalyzer",
    "ChartGenerator",
    "EnhancedReportGenerator",
]