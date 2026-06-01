"""
db_sql_auditor/models.py
SQL审核数据模型

文件功能：定义SQL审核相关的数据模型、枚举和错误码体系
主要类/函数：
    - ErrorCode: 错误码体系
    - ErrorMessage: 错误消息管理
    - AuditLevel: 审核级别枚举
    - AuditType: 审核类型枚举
    - SQLType: SQL类型枚举
    - AuditIssue: 审核问题
    - AuditResult: 审核结果
    - AuditRule: 审核规则
    - DDLImpact: DDL影响分析
    - AuditConfig: 审核配置

版本: 3.0.0（模块化重构版）
作者: AI Assistant
创建时间: 2026-04-23
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

# 从shared模块导入标准响应函数
from dbskiter.shared.error_handler import create_success_response, create_error_response


# =============================================================================
# 错误码体系
# =============================================================================

class ErrorCode:
    """
    错误码体系

    格式: AUDXXXYYY
    - AUD: Auditor模块标识
    - XXX: 功能代码
    - YYY: 具体错误
    """

    # 通用错误 (000)
    SUCCESS = "AUD000000"
    UNKNOWN_ERROR = "AUD000001"
    INVALID_PARAM = "AUD000002"
    NOT_FOUND = "AUD000003"
    ALREADY_EXISTS = "AUD000004"

    # SQL解析错误 (100)
    PARSE_ERROR = "AUD100001"
    UNSUPPORTED_SQL = "AUD100002"
    INVALID_SYNTAX = "AUD100003"

    # 审核错误 (200)
    AUDIT_FAILED = "AUD200001"
    RULE_NOT_FOUND = "AUD200002"
    RULE_EXECUTION_ERROR = "AUD200003"

    # DDL分析错误 (300)
    DDL_ANALYSIS_FAILED = "AUD300001"
    TABLE_NOT_FOUND = "AUD300002"
    PERMISSION_DENIED = "AUD300003"

    # 批量审核错误 (400)
    BATCH_AUDIT_FAILED = "AUD400001"
    PARTIAL_SUCCESS = "AUD400002"


class ErrorMessage:
    """错误消息管理"""

    _messages = {
        ErrorCode.SUCCESS: "操作成功",
        ErrorCode.UNKNOWN_ERROR: "未知错误",
        ErrorCode.INVALID_PARAM: "参数无效",
        ErrorCode.NOT_FOUND: "资源不存在",
        ErrorCode.ALREADY_EXISTS: "资源已存在",
        ErrorCode.PARSE_ERROR: "SQL解析失败",
        ErrorCode.UNSUPPORTED_SQL: "不支持的SQL类型",
        ErrorCode.INVALID_SYNTAX: "SQL语法错误",
        ErrorCode.AUDIT_FAILED: "SQL审核失败",
        ErrorCode.RULE_NOT_FOUND: "审核规则不存在",
        ErrorCode.RULE_EXECUTION_ERROR: "规则执行错误",
        ErrorCode.DDL_ANALYSIS_FAILED: "DDL影响分析失败",
        ErrorCode.TABLE_NOT_FOUND: "表不存在",
        ErrorCode.PERMISSION_DENIED: "权限不足",
        ErrorCode.BATCH_AUDIT_FAILED: "批量审核失败",
        ErrorCode.PARTIAL_SUCCESS: "部分成功",
    }

    @classmethod
    def get_message(cls, code: str) -> str:
        """获取错误消息"""
        return cls._messages.get(code, f"未知错误码: {code}")


# =============================================================================
# 响应函数
# =============================================================================

class AuditLevel(str, Enum):
    """
    审核级别

    级别说明:
        CRITICAL: 严重 - 必须修复，否则可能导致系统故障
        HIGH: 高危 - 强烈建议修复，可能导致性能或安全问题
        MEDIUM: 中危 - 建议修复，存在潜在风险
        LOW: 低危 - 可选修复，编码风格问题
        INFO: 信息 - 仅供参考，不影响功能
    """
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class AuditType(str, Enum):
    """
    审核类型

    类型说明:
        SYNTAX: 语法规范检查
        PERFORMANCE: 性能规范检查
        SECURITY: 安全规范检查
        STYLE: 编码风格检查
        DDL: DDL规范检查
        DML: DML规范检查
    """
    SYNTAX = "syntax"
    PERFORMANCE = "performance"
    SECURITY = "security"
    STYLE = "style"
    DDL = "ddl"
    DML = "dml"


class SQLType(str, Enum):
    """
    SQL类型

    支持的SQL类型:
        SELECT/INSERT/UPDATE/DELETE: DML操作
        CREATE/ALTER/DROP/TRUNCATE: DDL操作
        UNKNOWN: 未知类型
    """
    SELECT = "SELECT"
    INSERT = "INSERT"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    CREATE = "CREATE"
    ALTER = "ALTER"
    DROP = "DROP"
    TRUNCATE = "TRUNCATE"
    UNKNOWN = "UNKNOWN"


# =============================================================================
# 数据类定义
# =============================================================================

@dataclass
class AuditConfig:
    """
    审核配置

    属性:
        enable_syntax_check: 是否启用语法检查
        enable_performance_check: 是否启用性能检查
        enable_security_check: 是否启用安全检查
        enable_style_check: 是否启用风格检查
        enable_ddl_check: 是否启用DDL检查
        min_audit_level: 最小审核级别
        max_issues_per_sql: 单SQL最大问题数
        custom_rules: 自定义规则配置
    """
    enable_syntax_check: bool = True
    enable_performance_check: bool = True
    enable_security_check: bool = True
    enable_style_check: bool = True
    enable_ddl_check: bool = True
    min_audit_level: AuditLevel = AuditLevel.INFO
    max_issues_per_sql: int = 50
    custom_rules: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "enable_syntax_check": self.enable_syntax_check,
            "enable_performance_check": self.enable_performance_check,
            "enable_security_check": self.enable_security_check,
            "enable_style_check": self.enable_style_check,
            "enable_ddl_check": self.enable_ddl_check,
            "min_audit_level": self.min_audit_level.value,
            "max_issues_per_sql": self.max_issues_per_sql,
            "custom_rules": self.custom_rules,
        }


@dataclass
class AuditIssue:
    """
    审核发现的问题

    属性:
        rule_id: 规则ID
        rule_name: 规则名称
        audit_type: 审核类型
        level: 问题级别
        message: 问题描述
        suggestion: 修复建议
        line_number: 行号（可选）
        column_position: 列位置（可选）
        sql_fragment: 相关SQL片段（可选）
    """
    rule_id: str
    rule_name: str
    audit_type: AuditType
    level: AuditLevel
    message: str
    suggestion: str
    line_number: Optional[int] = None
    column_position: Optional[int] = None
    sql_fragment: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "rule_id": self.rule_id,
            "rule_name": self.rule_name,
            "audit_type": self.audit_type.value,
            "level": self.level.value,
            "message": self.message,
            "suggestion": self.suggestion,
            "line_number": self.line_number,
            "column_position": self.column_position,
            "sql_fragment": self.sql_fragment,
        }


@dataclass
class AuditResult:
    """
    审核结果

    属性:
        audit_id: 审核ID
        sql_content: SQL内容
        sql_type: SQL类型
        audit_time: 审核时间
        total_issues: 总问题数
        critical_count: 严重问题数
        high_count: 高危问题数
        medium_count: 中危问题数
        low_count: 低危问题数
        issues: 问题列表
        score: 审核评分(0-100)
        passed: 是否通过
        estimated_cost: 预估成本（可选）
        estimated_rows: 预估扫描行数（可选）
    """
    audit_id: str
    sql_content: str
    sql_type: SQLType
    audit_time: datetime

    # 统计
    total_issues: int = 0
    critical_count: int = 0
    high_count: int = 0
    medium_count: int = 0
    low_count: int = 0

    # 问题列表
    issues: List[AuditIssue] = field(default_factory=list)

    # 评分
    score: float = 100.0
    passed: bool = True

    # 性能评估
    estimated_cost: Optional[float] = None
    estimated_rows: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "audit_id": self.audit_id,
            "sql_type": self.sql_type.value,
            "audit_time": self.audit_time.isoformat(),
            "statistics": {
                "total_issues": self.total_issues,
                "critical_count": self.critical_count,
                "high_count": self.high_count,
                "medium_count": self.medium_count,
                "low_count": self.low_count,
            },
            "score": round(self.score, 2),
            "passed": self.passed,
            "estimated_cost": self.estimated_cost,
            "estimated_rows": self.estimated_rows,
            "issues": [issue.to_dict() for issue in self.issues],
        }


@dataclass
class AuditRule:
    """
    审核规则

    属性:
        rule_id: 规则ID
        rule_name: 规则名称
        audit_type: 审核类型
        level: 默认级别
        description: 规则描述
        enabled: 是否启用
        custom_config: 自定义配置
    """
    rule_id: str
    rule_name: str
    audit_type: AuditType
    level: AuditLevel
    description: str
    enabled: bool = True
    custom_config: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "rule_id": self.rule_id,
            "rule_name": self.rule_name,
            "audit_type": self.audit_type.value,
            "level": self.level.value,
            "description": self.description,
            "enabled": self.enabled,
            "custom_config": self.custom_config,
        }


@dataclass
class DDLImpact:
    """
    DDL变更影响分析

    属性:
        ddl_sql: DDL语句
        table_name: 表名
        operation: 操作类型
        execution_time_estimate: 预估执行时间
        table_size_mb: 表大小（可选）
        rows_estimate: 预估影响行数（可选）
        risks: 风险点列表
        suggestions: 建议列表
        dependent_objects: 依赖对象列表
    """
    ddl_sql: str
    table_name: str
    operation: str
    execution_time_estimate: str
    table_size_mb: Optional[float] = None
    rows_estimate: Optional[int] = None
    risks: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)
    dependent_objects: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "ddl_sql": self.ddl_sql,
            "table_name": self.table_name,
            "operation": self.operation,
            "execution_time_estimate": self.execution_time_estimate,
            "table_size_mb": self.table_size_mb,
            "rows_estimate": self.rows_estimate,
            "risks": self.risks,
            "suggestions": self.suggestions,
            "dependent_objects": self.dependent_objects,
        }


@dataclass
class BatchAuditResult:
    """
    批量审核结果

    属性:
        batch_id: 批次ID
        total_count: 总SQL数
        success_count: 成功数
        failed_count: 失败数
        results: 审核结果列表
        summary: 汇总信息
        audit_time: 审核时间
    """
    batch_id: str
    total_count: int
    success_count: int = 0
    failed_count: int = 0
    results: List[AuditResult] = field(default_factory=list)
    summary: Dict[str, Any] = field(default_factory=dict)
    audit_time: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "batch_id": self.batch_id,
            "total_count": self.total_count,
            "success_count": self.success_count,
            "failed_count": self.failed_count,
            "summary": self.summary,
            "audit_time": self.audit_time.isoformat(),
            "results": [result.to_dict() for result in self.results],
        }
