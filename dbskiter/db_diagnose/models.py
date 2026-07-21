"""
db_diagnose/models.py
数据模型和枚举定义

文件功能：集中定义所有数据类、枚举和错误码
主要类/函数：
    - ErrorCode: 错误码体系
    - DiagnoseLevel: 诊断级别枚举
    - DiagnoseType: 诊断类型枚举
    - DatabaseType: 数据库类型枚举
    - DiagnoseConfig: 诊断配置
    - DiagnoseResult: 诊断结果
    - IndexSuggestion: 索引建议
    - SlowQuery: 慢查询
    - PerformanceMetrics: 性能指标

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

    格式: DIAXXXYYY
    - DIA: Diagnose模块标识
    - XXX: 功能代码
    - YYY: 具体错误
    """

    # 通用错误 (000)
    SUCCESS = "DIA000000"
    UNKNOWN_ERROR = "DIA000001"
    INVALID_PARAM = "DIA000002"
    NOT_FOUND = "DIA000003"
    ALREADY_EXISTS = "DIA000004"

    # SQL分析错误 (100)
    ANALYSIS_FAILED = "DIA100001"
    PARSE_ERROR = "DIA100002"
    UNSUPPORTED_SQL = "DIA100003"

    # 性能分析错误 (200)
    PERF_ANALYSIS_FAILED = "DIA200001"
    METRICS_ERROR = "DIA200002"

    # 慢查询错误 (300)
    SLOW_QUERY_FAILED = "DIA300001"
    NO_SLOW_QUERIES = "DIA300002"

    # 表诊断错误 (400)
    TABLE_DIAGNOSE_FAILED = "DIA400001"
    TABLE_NOT_FOUND = "DIA400002"


class ErrorMessage:
    """错误消息映射"""

    _messages = {
        ErrorCode.SUCCESS: "操作成功",
        ErrorCode.UNKNOWN_ERROR: "未知错误",
        ErrorCode.INVALID_PARAM: "参数无效",
        ErrorCode.NOT_FOUND: "资源不存在",
        ErrorCode.ALREADY_EXISTS: "资源已存在",
        ErrorCode.ANALYSIS_FAILED: "SQL分析失败",
        ErrorCode.PARSE_ERROR: "SQL解析错误",
        ErrorCode.UNSUPPORTED_SQL: "不支持的SQL类型",
        ErrorCode.PERF_ANALYSIS_FAILED: "性能分析失败",
        ErrorCode.METRICS_ERROR: "性能指标错误",
        ErrorCode.SLOW_QUERY_FAILED: "慢查询分析失败",
        ErrorCode.NO_SLOW_QUERIES: "未发现慢查询",
        ErrorCode.TABLE_DIAGNOSE_FAILED: "表诊断失败",
        ErrorCode.TABLE_NOT_FOUND: "表不存在",
    }

    @classmethod
    def get_message(cls, code: str) -> str:
        """获取错误消息"""
        return cls._messages.get(code, f"未知错误码: {code}")


class DiagnoseLevel(Enum):
    """诊断级别"""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class DiagnoseType(Enum):
    """诊断类型"""
    SQL_ANALYSIS = "sql_analysis"
    PERFORMANCE = "performance"
    SLOW_QUERY = "slow_query"
    TABLE_DIAGNOSE = "table_diagnose"
    INDEX_SUGGESTION = "index_suggestion"


class DatabaseType(Enum):
    """数据库类型"""
    MYSQL = "mysql"
    ORACLE = "oracle"
    POSTGRESQL = "postgresql"
    UNKNOWN = "unknown"


@dataclass
class DiagnoseConfig:
    """诊断配置"""
    enable_deep_analysis: bool = True
    enable_index_suggestion: bool = True
    enable_performance_analysis: bool = True
    slow_query_threshold: float = 1.0  # 秒
    max_slow_queries: int = 20
    min_priority: str = "medium"

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "enable_deep_analysis": self.enable_deep_analysis,
            "enable_index_suggestion": self.enable_index_suggestion,
            "enable_performance_analysis": self.enable_performance_analysis,
            "slow_query_threshold": self.slow_query_threshold,
            "max_slow_queries": self.max_slow_queries,
            "min_priority": self.min_priority,
        }


@dataclass
class DiagnoseResult:
    """诊断结果"""
    sql: str = ""
    sql_type: str = ""
    score: float = 0.0
    issues: List[Dict[str, Any]] = field(default_factory=list)
    suggestions: List[Dict[str, Any]] = field(default_factory=list)
    summary: str = ""
    diagnosed_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "sql": self.sql,
            "sql_type": self.sql_type,
            "score": round(self.score, 2),
            "issues": self.issues,
            "suggestions": self.suggestions,
            "summary": self.summary,
            "diagnosed_at": self.diagnosed_at,
        }


@dataclass
class IndexSuggestion:
    """索引建议"""
    table: str = ""
    columns: List[str] = field(default_factory=list)
    index_type: str = "btree"
    reason: str = ""
    priority: str = "medium"
    create_sql: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "table": self.table,
            "columns": self.columns,
            "index_type": self.index_type,
            "reason": self.reason,
            "priority": self.priority,
            "create_sql": self.create_sql,
        }


@dataclass
class SlowQuery:
    """慢查询"""
    sql: str = ""
    execution_time: float = 0.0
    execution_count: int = 0
    avg_time: float = 0.0
    max_time: float = 0.0
    rows_examined: int = 0
    rows_sent: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "sql": self.sql,
            "execution_time": round(self.execution_time, 4),
            "execution_count": self.execution_count,
            "avg_time": round(self.avg_time, 4),
            "max_time": round(self.max_time, 4),
            "rows_examined": self.rows_examined,
            "rows_sent": self.rows_sent,
        }


@dataclass
class PerformanceMetrics:
    """性能指标"""
    cpu_usage: float = 0.0
    memory_usage: float = 0.0
    disk_io: float = 0.0
    connections: int = 0
    active_queries: int = 0
    qps: float = 0.0
    tps: float = 0.0
    collected_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "cpu_usage": round(self.cpu_usage, 2),
            "memory_usage": round(self.memory_usage, 2),
            "disk_io": round(self.disk_io, 2),
            "connections": self.connections,
            "active_queries": self.active_queries,
            "qps": round(self.qps, 2),
            "tps": round(self.tps, 2),
            "collected_at": self.collected_at,
        }


@dataclass
class TableDiagnoseResult:
    """表诊断结果"""
    table_name: str = ""
    row_count: int = 0
    size_mb: float = 0.0
    index_count: int = 0
    issues: List[Dict[str, Any]] = field(default_factory=list)
    suggestions: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "table_name": self.table_name,
            "row_count": self.row_count,
            "size_mb": round(self.size_mb, 2),
            "index_count": self.index_count,
            "issues": self.issues,
            "suggestions": self.suggestions,
        }


@dataclass
class DiagnoseReport:
    """诊断报告"""
    title: str = "SQL诊断报告"
    total_sqls: int = 0
    total_issues: int = 0
    critical_count: int = 0
    high_count: int = 0
    medium_count: int = 0
    low_count: int = 0
    results: List[Dict[str, Any]] = field(default_factory=list)
    generated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "title": self.title,
            "total_sqls": self.total_sqls,
            "total_issues": self.total_issues,
            "critical_count": self.critical_count,
            "high_count": self.high_count,
            "medium_count": self.medium_count,
            "low_count": self.low_count,
            "results": self.results,
            "generated_at": self.generated_at,
        }


# 注意：create_success_response 和 create_error_response 从 shared.error_handler 导入
# 通过 re-export 保持向后兼容
from dbskiter.shared.error_handler import create_success_response, create_error_response
