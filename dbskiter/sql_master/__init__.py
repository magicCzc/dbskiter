"""
sql_master Skill 统一入口（模块化重构版）
SQL 执行 + 重写 + 数据分析核心模块

统一入口: SQLMasterSkill

快速开始:
    from sql_master import SQLMasterSkill

    skill = SQLMasterSkill(connector)

    # SQL执行
    result = skill.execute("SELECT * FROM users LIMIT 10")

    # SQL重写优化
    rewrite_result = skill.rewrite_sql("SELECT * FROM users WHERE id = 1")

    # 分析SQL质量
    quality = skill.analyze_sql_quality("SELECT * FROM users")

    # 数据分析
    analysis = skill.analyze_data("SELECT * FROM orders")

    # 智能提示
    suggestions = skill.get_suggestions("SELECT * FROM ")

    # Schema信息
    schema = skill.get_schema_info("users")

    # 生成优化报告
    report = skill.generate_optimization_report([sql1, sql2, sql3])

功能:
- SQL执行 (execute)
- 批量执行 (execute_batch)
- SQL重写优化 (rewrite_sql)
- 批量重写 (rewrite_batch)
- SQL质量分析 (analyze_sql_quality)
- 数据分析 (analyze_data)
- 智能提示 (get_suggestions)
- Schema信息 (get_schema_info)
- 优化报告 (generate_optimization_report)
- 缓存统计 (get_cache_stats)
- 清除缓存 (clear_cache)

版本: 3.0.0（模块化重构版）
"""

# 数据模型
from .models import (
    ErrorCode,
    ErrorMessage,
    SQLType,
    OptimizationLevel,
    SQLOptimizationReport,
    SQLMasterConfig,
    SQLAnalysisResult,
    CacheStats,
    ExecutionResult,
    RewriteSuggestion,
    create_success_response,
    create_error_response,
)

# 工具类
from .utils import (
    SQLTypeDetector,
    SQLFormatter,
    QueryBuilder,
    ResultProcessor,
    PerformanceTimer,
    SQLAnalyzer,
)

# 统一入口
from .skill import SQLMasterSkill

# 导出核心组件（供高级用户使用）
from .executor import SQLExecutor
from .analyzer import DataAnalyzer
from .sql_rewriter_v2 import SQLRewriterV2, RewriteResult, RewriteSuggestion as RewriteResultSuggestion
from .cache_manager import SQLCacheManager
from .cache_invalidator import SmartCachedExecutor

__all__ = [
    # 数据模型
    "ErrorCode",
    "ErrorMessage",
    "SQLType",
    "OptimizationLevel",
    "SQLOptimizationReport",
    "SQLMasterConfig",
    "SQLAnalysisResult",
    "CacheStats",
    "ExecutionResult",
    "RewriteSuggestion",
    "create_success_response",
    "create_error_response",
    # 工具类
    "SQLTypeDetector",
    "SQLFormatter",
    "QueryBuilder",
    "ResultProcessor",
    "PerformanceTimer",
    "SQLAnalyzer",
    # 主要入口
    "SQLMasterSkill",
    # 高级组件
    "SQLExecutor",
    "DataAnalyzer",
    "SQLRewriterV2",
    "RewriteResult",
    "RewriteResultSuggestion",
    "SQLCacheManager",
    "SmartCachedExecutor",
]

__version__ = "3.0.0"
