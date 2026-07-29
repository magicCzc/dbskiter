"""
db_security/models.py
数据模型和枚举定义

文件功能：集中定义所有数据类、枚举和错误码
主要类/函数：
    - ErrorCode: 错误码体系
    - RiskLevel: 风险等级枚举
    - InjectionType: 注入类型枚举
    - SensitivityLevel: 敏感度等级枚举
    - DataCategory: 数据类别枚举
    - Risk: 安全风险数据类
    - RiskReport: 风险检测报告
    - SecurityConfig: 安全配置
    - InjectionPattern: 注入模式
    - SensitiveColumn: 敏感列信息

版本: 3.0.0
作者: Magiczc
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

    格式: SECXXXYYY
    - SEC: Security模块标识
    - XXX: 功能代码
    - YYY: 具体错误
    """

    # 通用错误 (000)
    SUCCESS = "SEC000000"
    UNKNOWN_ERROR = "SEC000001"
    INVALID_PARAM = "SEC000002"
    NOT_FOUND = "SEC000003"
    ALREADY_EXISTS = "SEC000004"

    # SQL注入检测错误 (100)
    INJECTION_DETECTED = "SEC100001"
    PARSE_ERROR = "SEC100002"
    UNSUPPORTED_DIALECT = "SEC100003"

    # 敏感数据扫描错误 (200)
    SCAN_FAILED = "SEC200001"
    CONNECTION_ERROR = "SEC200002"
    PERMISSION_DENIED = "SEC200003"

    # 权限审计错误 (300)
    AUDIT_FAILED = "SEC300001"
    PRIVILEGE_ERROR = "SEC300002"

    # 配置审计错误 (400)
    CONFIG_AUDIT_FAILED = "SEC400001"


class ErrorMessage:
    """错误消息映射"""

    _messages = {
        ErrorCode.SUCCESS: "操作成功",
        ErrorCode.UNKNOWN_ERROR: "未知错误",
        ErrorCode.INVALID_PARAM: "参数无效",
        ErrorCode.NOT_FOUND: "资源不存在",
        ErrorCode.ALREADY_EXISTS: "资源已存在",
        ErrorCode.INJECTION_DETECTED: "检测到SQL注入风险",
        ErrorCode.PARSE_ERROR: "SQL解析错误",
        ErrorCode.UNSUPPORTED_DIALECT: "不支持的数据库类型",
        ErrorCode.SCAN_FAILED: "敏感数据扫描失败",
        ErrorCode.CONNECTION_ERROR: "数据库连接错误",
        ErrorCode.PERMISSION_DENIED: "权限不足",
        ErrorCode.AUDIT_FAILED: "权限审计失败",
        ErrorCode.PRIVILEGE_ERROR: "权限错误",
        ErrorCode.CONFIG_AUDIT_FAILED: "配置审计失败",
    }

    @classmethod
    def get_message(cls, code: str) -> str:
        """获取错误消息"""
        return cls._messages.get(code, f"未知错误码: {code}")


class RiskLevel(Enum):
    """风险等级"""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class InjectionType(Enum):
    """注入类型"""

    BOOLEAN_BASED = "boolean_based"
    TIME_BASED = "time_based"
    UNION_BASED = "union_based"
    ERROR_BASED = "error_based"
    STACKED_QUERY = "stacked_query"
    COMMENT_BASED = "comment_based"
    SECOND_ORDER = "second_order"


class SensitivityLevel(Enum):
    """敏感度等级"""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class DataCategory(Enum):
    """数据类别"""

    CREDENTIALS = "credentials"
    PII = "pii"
    FINANCIAL = "financial"
    HEALTH = "health"
    CONTACT = "contact"
    BUSINESS = "business"


@dataclass
class Risk:
    """安全风险

    Attributes:
        severity: 严重级别（critical/high/medium/low）
        description: 风险描述
        category: 风险分类（"password"/"permission"/"injection"/...）
        current_value: 当前配置值
        recommended_value: 推荐配置值
    """

    severity: str
    description: str
    category: str = ""
    current_value: str = ""
    recommended_value: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        result = {"severity": self.severity, "description": self.description, "category": self.category}
        if self.current_value:
            result["current_value"] = self.current_value
        if self.recommended_value:
            result["recommended_value"] = self.recommended_value
        return result


@dataclass
class RiskReport:
    """风险检测报告

    Attributes:
        total_risks: 风险总数
        critical_count: 严重风险数
        high_count: 高风险数
        medium_count: 中风险数
        low_count: 低风险数
        risks: 风险列表
        failed_modules: 检测失败的模块名列表
        generated_at: 报告生成时间（ISO 8601）
    """

    total_risks: int = 0
    critical_count: int = 0
    high_count: int = 0
    medium_count: int = 0
    low_count: int = 0
    risks: List[Risk] = field(default_factory=list)
    failed_modules: List[str] = field(default_factory=list)
    generated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "total_risks": self.total_risks,
            "critical_count": self.critical_count,
            "high_count": self.high_count,
            "medium_count": self.medium_count,
            "low_count": self.low_count,
            "risks": [r.to_dict() for r in self.risks],
            "failed_modules": self.failed_modules,
            "generated_at": self.generated_at,
        }


@dataclass
class SecurityConfig:
    """安全扫描配置

    Attributes:
        enable_sql_injection_detection: 是否启用 SQL 注入检测
        enable_sensitive_data_scan: 是否启用敏感数据扫描
        enable_permission_audit: 是否启用权限审计
        enable_config_audit: 是否启用配置审计
        sample_size: 敏感数据扫描采样行数
    """

    enable_sql_injection_detection: bool = True
    enable_sensitive_data_scan: bool = True
    enable_permission_audit: bool = True
    enable_config_audit: bool = True
    sample_size: int = 100

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "enable_sql_injection_detection": self.enable_sql_injection_detection,
            "enable_sensitive_data_scan": self.enable_sensitive_data_scan,
            "enable_permission_audit": self.enable_permission_audit,
            "enable_config_audit": self.enable_config_audit,
            "sample_size": self.sample_size,
        }


@dataclass
class InjectionPattern:
    """SQL 注入模式

    Attributes:
        pattern_type: 注入类型（UNION/TIME_BLIND/BOOLEAN_BLIND/...）
        description: 模式描述
        severity: 风险等级
        regex_patterns: 用于匹配的正则表达式列表
    """

    pattern_type: InjectionType
    description: str
    severity: RiskLevel
    regex_patterns: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "pattern_type": self.pattern_type.value,
            "description": self.description,
            "severity": self.severity.value,
            "regex_patterns": self.regex_patterns,
        }


@dataclass
class SensitiveColumn:
    """敏感列信息

    Attributes:
        table_name: 表名
        column_name: 列名
        data_type: 数据类型（VARCHAR/INT/...）
        sensitivity_level: 敏感等级（CRITICAL/HIGH/MEDIUM/LOW）
        data_category: 数据分类（PII/FINANCIAL/HEALTH/...）
        sample_data: 脱敏后的样例数据（前 5 条）
        row_count: 总行数
        confidence_score: 识别置信度（0-1）
    """

    table_name: str
    column_name: str
    data_type: str
    sensitivity_level: SensitivityLevel
    data_category: DataCategory
    sample_data: List[str] = field(default_factory=list)
    row_count: int = 0
    confidence_score: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "table_name": self.table_name,
            "column_name": self.column_name,
            "data_type": self.data_type,
            "sensitivity_level": self.sensitivity_level.value,
            "data_category": self.data_category.value,
            "sample_data": self.sample_data[:5],
            "row_count": self.row_count,
            "confidence_score": round(self.confidence_score, 2),
        }


@dataclass
class SQLInjectionResult:
    """SQL 注入检测结果

    Attributes:
        is_injection: 是否检测到注入
        risk_score: 风险评分（0-100）
        risk_level: 风险等级
        injection_type: 注入类型（None 表示未检测到）
        description: 人类可读描述
        affected_params: 受影响的参数列表
        recommendations: 修复建议
    """

    is_injection: bool
    risk_score: float
    risk_level: RiskLevel
    injection_type: Optional[InjectionType] = None
    description: str = ""
    affected_params: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "is_injection": self.is_injection,
            "risk_score": round(self.risk_score, 2),
            "risk_level": self.risk_level.value,
            "injection_type": self.injection_type.value if self.injection_type else None,
            "description": self.description,
            "affected_params": self.affected_params,
            "recommendations": self.recommendations,
        }


@dataclass
class SensitiveDataResult:
    """敏感数据扫描结果

    Attributes:
        total_tables: 扫描表总数
        total_columns: 扫描列总数
        sensitive_columns: 识别出的敏感列列表
        scan_duration: 扫描耗时（秒）
    """

    total_tables: int = 0
    total_columns: int = 0
    sensitive_columns: List[SensitiveColumn] = field(default_factory=list)
    scan_duration: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "total_tables": self.total_tables,
            "total_columns": self.total_columns,
            "sensitive_columns": [c.to_dict() for c in self.sensitive_columns],
            "scan_duration": round(self.scan_duration, 2),
        }


# 注意：create_success_response 和 create_error_response 已从 shared.error_handler 导入
# 不再在此文件中重复定义
