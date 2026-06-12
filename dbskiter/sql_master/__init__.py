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

import logging

logger = logging.getLogger(__name__)

# 数据模型
try:
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
    )
except ImportError as _e:
    logger.debug("sql_master.models 导入失败: %s", _e)

# 响应函数（从shared模块导入）
try:
    from dbskiter.shared.error_handler import create_success_response, create_error_response
except ImportError as _e:
    logger.debug("shared.error_handler 导入失败: %s", _e)

# 工具类
try:
    from .utils import (
        SQLTypeDetector,
        SQLFormatter,
        QueryBuilder,
        ResultProcessor,
        PerformanceTimer,
        SQLAnalyzer,
    )
except ImportError as _e:
    logger.debug("sql_master.utils 导入失败: %s", _e)

# 统一入口
try:
    from .skill import SQLMasterSkill
except ImportError as _e:
    logger.debug("sql_master.skill 导入失败: %s", _e)

# 导出核心组件（供高级用户使用）
try:
    from .executor import SQLExecutor
    from .analyzer import DataAnalyzer
    from .sql_rewriter_v2 import SQLRewriterV2, RewriteResult, RewriteSuggestion as RewriteResultSuggestion
    from .cache_manager import SQLCacheManager
    from .cache_invalidator import SmartCachedExecutor
except ImportError as _e:
    logger.debug("sql_master 核心组件导入失败: %s", _e)

# 安全执行组件
try:
    from .security_executor_v2 import SecurityExecutorV2, ExecutionContext, SecurityCheckResult
    from .security_checker import (
        SecurityChecker,
        SQLInjectionDetector,
        InjectionCheckResult,
        RateLimiter,
        RateLimitStatus,
        check_sql,
    )
except ImportError as _e:
    logger.debug("sql_master 安全组件导入失败: %s", _e)

# SQL解析器
try:
    from .sql_parser import (
        SQLType,
        SQLDialect,
        ParsedSQL,
        SQLParser,
        parse_sql,
        is_read_only,
        is_dangerous_without_where,
    )
except ImportError as _e:
    logger.debug("sql_master.sql_parser 导入失败: %s", _e)

# 审计日志
try:
    from .audit_logger import (
        StorageBackend,
        OperationStatus,
        AuditLogEntry,
        AuditLogger,
        AuditLogQuery,
    )
except ImportError as _e:
    logger.debug("sql_master.audit_logger 导入失败: %s", _e)

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
    # 安全执行组件
    "SecurityExecutorV2",
    "ExecutionContext",
    "SecurityCheckResult",
    "SecurityChecker",
    "SQLInjectionDetector",
    "InjectionCheckResult",
    "RateLimiter",
    "RateLimitStatus",
    "check_sql",
    # SQL解析器
    "SQLDialect",
    "ParsedSQL",
    "SQLParser",
    "parse_sql",
    "is_read_only",
    "is_dangerous_without_where",
    # 审计日志
    "StorageBackend",
    "OperationStatus",
    "AuditLogEntry",
    "AuditLogger",
    "AuditLogQuery",
]

__version__ = "3.0.0"
