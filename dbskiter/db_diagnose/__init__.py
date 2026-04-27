"""
db_diagnose Skill - 统一入口（模块化重构版）
数据库诊断模块 - 深度SQL分析与优化

统一入口: DiagnoseSkill

快速开始:
    from db_diagnose import DiagnoseSkill

    skill = DiagnoseSkill(connector)
    result = skill.analyze_sql("SELECT * FROM users WHERE email = 'test@example.com'")
    print(result["summary"])

核心功能:
- 深度SQL分析 (analyze_sql)
- 批量SQL分析 (analyze_sql_batch)
- 索引建议 (get_index_suggestions)
- 慢查询分析 (analyze_slow_queries)
- 性能指标分析 (analyze_performance_metrics)
- 表诊断 (diagnose_table)
- SQL重写 (rewrite_sql)
- SQL质量分析 (analyze_sql_quality)
- 诊断报告生成 (generate_report)

版本: 3.0.0（模块化重构版）
"""

# 数据模型
from .models import (
    ErrorCode,
    ErrorMessage,
    DiagnoseLevel,
    DiagnoseType,
    DatabaseType,
    DiagnoseConfig,
    DiagnoseResult,
    IndexSuggestion,
    SlowQuery,
    PerformanceMetrics,
    TableDiagnoseResult,
    DiagnoseReport,
    create_success_response,
    create_error_response,
)

# 工具类
from .utils import (
    SQLFingerprint,
    IssueClassifier,
    ScoreCalculator,
    PrioritySorter,
    MetricsAggregator,
    QueryExtractor,
)

# 统一入口
from .skill import DiagnoseSkill

__all__ = [
    # 数据模型
    "ErrorCode",
    "ErrorMessage",
    "DiagnoseLevel",
    "DiagnoseType",
    "DatabaseType",
    "DiagnoseConfig",
    "DiagnoseResult",
    "IndexSuggestion",
    "SlowQuery",
    "PerformanceMetrics",
    "TableDiagnoseResult",
    "DiagnoseReport",
    "create_success_response",
    "create_error_response",
    # 工具类
    "SQLFingerprint",
    "IssueClassifier",
    "ScoreCalculator",
    "PrioritySorter",
    "MetricsAggregator",
    "QueryExtractor",
    # 主要入口
    "DiagnoseSkill",
]

__version__ = "3.0.0"
