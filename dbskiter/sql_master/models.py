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
作者: AI Assistant
创建时间: 2026-04-23
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

# 从shared模块导入标准响应函数
from dbskiter.shared.error_handler import create_success_response, create_error_response


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
    """SQL优化报告"""
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
            "generated_at": self.generated_at
        }


@dataclass
class SQLMasterConfig:
    """SQL Master配置"""
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
            "cache_ttl": self.cache_ttl
        }


@dataclass
class SQLAnalysisResult:
    """SQL分析结果"""
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
            "complexity": self.complexity
        }


@dataclass
class CacheStats:
    """缓存统计"""
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
            "memory_usage": self.memory_usage
        }


@dataclass
class ExecutionResult:
    """执行结果"""
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
            "cached": self.cached
        }


@dataclass
class RewriteSuggestion:
    """重写建议"""
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
            "impact": self.impact
        }


# 注意：create_success_response 和 create_error_response 已从 shared.error_handler 导入
# 不再在此文件中重复定义
