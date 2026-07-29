"""
sql_master/models.py
数据模型和枚举定义

文件功能：集中定义所有数据类、枚举和错误码
主要类/函数：
    - ErrorCode: 错误码体系
    - SQLType: SQL类型枚举
    - OptimizationLevel: 优化级别枚举
    - SQLOptimizationReport: SQL优化报告
    - SQLMasterConfig: SQL Master配置
    - SQLAnalysisResult: SQL分析结果
    - CacheStats: 缓存统计

版本: 3.0.0
作者: Magiczc
创建时间: 2026-04-23
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List


class ErrorCode:
    """
    错误码体系

    格式: SQLXXXYYY
    - SQL: SQL Master模块标识
    - XXX: 功能代码
    - YYY: 具体错误
    """

    # 通用错误 (000)
    SUCCESS = "SQL000000"
    UNKNOWN_ERROR = "SQL000001"
    INVALID_PARAM = "SQL000002"
    NOT_FOUND = "SQL000003"
    ALREADY_EXISTS = "SQL000004"

    # 执行错误 (100)
    EXECUTION_FAILED = "SQL100001"
    SYNTAX_ERROR = "SQL100002"
    TIMEOUT_ERROR = "SQL100003"
    CONNECTION_ERROR = "SQL100004"
    READ_ONLY_VIOLATION = "SQL100005"  # 只读模式违规
    DANGEROUS_OPERATION = "SQL100006"  # 危险操作被拦截
    FORCE_REQUIRED = "SQL100007"  # 需要force参数
    PERMISSION_DENIED = "SQL100008"  # 权限不足

    # 重写错误 (200)
    REWRITE_FAILED = "SQL200001"
    UNSUPPORTED_SQL = "SQL200002"

    # 分析错误 (300)
    ANALYSIS_FAILED = "SQL300001"
    INVALID_DATA = "SQL300002"

    # 缓存错误 (400)
    CACHE_ERROR = "SQL400001"
    CACHE_FULL = "SQL400002"


class ErrorMessage:
    """错误消息映射"""

    _messages = {
        ErrorCode.SUCCESS: "操作成功",
        ErrorCode.UNKNOWN_ERROR: "未知错误",
        ErrorCode.INVALID_PARAM: "参数无效",
        ErrorCode.NOT_FOUND: "资源不存在",
        ErrorCode.ALREADY_EXISTS: "资源已存在",
        ErrorCode.EXECUTION_FAILED: "SQL执行失败",
        ErrorCode.SYNTAX_ERROR: "SQL语法错误",
        ErrorCode.TIMEOUT_ERROR: "执行超时",
        ErrorCode.CONNECTION_ERROR: "数据库连接错误",
        ErrorCode.READ_ONLY_VIOLATION: "只读模式下不允许执行写操作",
        ErrorCode.DANGEROUS_OPERATION: "危险操作被拦截",
        ErrorCode.FORCE_REQUIRED: "此操作需要 --force 参数强制执行",
        ErrorCode.PERMISSION_DENIED: "权限不足",
        ErrorCode.REWRITE_FAILED: "SQL重写失败",
        ErrorCode.UNSUPPORTED_SQL: "不支持的SQL类型",
        ErrorCode.ANALYSIS_FAILED: "数据分析失败",
        ErrorCode.INVALID_DATA: "无效数据",
        ErrorCode.CACHE_ERROR: "缓存错误",
        ErrorCode.CACHE_FULL: "缓存已满",
    }

    @classmethod
    def get_message(cls, code: str) -> str:
        """获取错误消息"""
        return cls._messages.get(code, f"未知错误码: {code}")


class SQLType(Enum):
    """SQL类型"""

    SELECT = "select"
    INSERT = "insert"
    UPDATE = "update"
    DELETE = "delete"
    CREATE = "create"
    ALTER = "alter"
    DROP = "drop"
    UNKNOWN = "unknown"


class OptimizationLevel(Enum):
    """优化级别"""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    NONE = "none"


@dataclass
class SQLOptimizationReport:
    """SQL 优化报告

    Attributes:
        total_sqls: 待优化 SQL 总数
        can_optimize: 可优化数量
        total_suggestions: 优化建议总数
        high_impact: 高影响建议数
        medium_impact: 中影响建议数
        low_impact: 低影响建议数
        optimized_sqls: 优化后的 SQL 详情列表
    """

    total_sqls: int = 0
    can_optimize: int = 0
    total_suggestions: int = 0
    high_impact: int = 0
    medium_impact: int = 0
    low_impact: int = 0
    optimized_sqls: List[Dict[str, Any]] = field(default_factory=list)
    generated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "total_sqls": self.total_sqls,
            "can_optimize": self.can_optimize,
            "total_suggestions": self.total_suggestions,
            "high_impact": self.high_impact,
            "medium_impact": self.medium_impact,
            "low_impact": self.low_impact,
            "optimized_sqls": self.optimized_sqls,
            "generated_at": self.generated_at,
        }


@dataclass
class SQLMasterConfig:
    """SQL Master 配置

    Attributes:
        enable_rewriter: 启用 SQL 重写器
        enable_analyzer: 启用 SQL 分析器
        enable_intellisense: 启用智能补全
        enable_cache: 启用结果缓存
        max_rows: 单次返回最大行数
        cache_size: 缓存容量
        cache_ttl: 缓存过期时间（秒）
    """

    enable_rewriter: bool = True
    enable_analyzer: bool = True
    enable_intellisense: bool = True
    enable_cache: bool = True
    max_rows: int = 1000
    cache_size: int = 1000
    cache_ttl: int = 300

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "enable_rewriter": self.enable_rewriter,
            "enable_analyzer": self.enable_analyzer,
            "enable_intellisense": self.enable_intellisense,
            "enable_cache": self.enable_cache,
            "max_rows": self.max_rows,
            "cache_size": self.cache_size,
            "cache_ttl": self.cache_ttl,
        }


@dataclass
class SQLAnalysisResult:
    """SQL 分析结果

    Attributes:
        sql: 被分析的 SQL 文本
        sql_type: SQL 类型（SELECT/INSERT/...）
        score: 质量评分（0-100）
        issues: 发现的问题列表
        suggestions: 优化建议列表
        complexity: 复杂度（"low"/"medium"/"high"）
    """

    sql: str = ""
    sql_type: SQLType = SQLType.UNKNOWN
    score: float = 0.0
    issues: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)
    complexity: str = "low"

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "sql": self.sql,
            "sql_type": self.sql_type.value,
            "score": round(self.score, 2),
            "issues": self.issues,
            "suggestions": self.suggestions,
            "complexity": self.complexity,
        }


@dataclass
class CacheStats:
    """缓存统计

    Attributes:
        total_entries: 当前缓存条目数
        hit_count: 总命中次数
        miss_count: 总未命中次数
        hit_rate: 命中率（0-1）
        memory_usage: 内存占用（字节）
    """

    total_entries: int = 0
    hit_count: int = 0
    miss_count: int = 0
    hit_rate: float = 0.0
    memory_usage: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "total_entries": self.total_entries,
            "hit_count": self.hit_count,
            "miss_count": self.miss_count,
            "hit_rate": round(self.hit_rate, 2),
            "memory_usage": self.memory_usage,
        }


@dataclass
class ExecutionResult:
    """SQL 执行结果

    Attributes:
        success: 是否成功
        row_count: 返回行数
        columns: 列名列表
        rows: 行数据（二维数组）
        execution_time: 执行耗时（秒）
        cached: 是否来自缓存
    """

    success: bool = True
    row_count: int = 0
    columns: List[str] = field(default_factory=list)
    rows: List[List[Any]] = field(default_factory=list)
    execution_time: float = 0.0
    cached: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "success": self.success,
            "row_count": self.row_count,
            "columns": self.columns,
            "rows": self.rows,
            "execution_time": round(self.execution_time, 4),
            "cached": self.cached,
        }


@dataclass
class RewriteSuggestion:
    """SQL 重写建议

    Attributes:
        original_sql: 原始 SQL
        optimized_sql: 优化后的 SQL
        reason: 重写理由
        impact: 影响程度（"low"/"medium"/"high"）
    """

    original_sql: str = ""
    optimized_sql: str = ""
    reason: str = ""
    impact: str = "low"

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "original_sql": self.original_sql,
            "optimized_sql": self.optimized_sql,
            "reason": self.reason,
            "impact": self.impact,
        }


# 注意：create_success_response 和 create_error_response 已从 shared.error_handler 导入
# 不再在此文件中重复定义
from dbskiter.shared.error_handler import create_success_response, create_error_response  # noqa: F401
