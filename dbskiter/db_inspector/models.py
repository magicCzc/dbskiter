"""
db_inspector/models.py
db_inspector 数据模型

文件功能：定义巡检相关的数据模型、枚举和错误码体系
主要类：
    - ErrorCode: 错误码体系
    - ErrorMessage: 错误消息
    - RiskLevel: 风险等级枚举
    - InspectionType: 巡检类型枚举
    - InspectionItem: 巡检项
    - InspectionReport: 巡检报告
    - PerformanceBaseline: 性能基线

作者：AI Assistant
创建时间：2026-04-22
最后修改：2026-04-23
版本：3.0.0（模块化重构版）
"""

from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class ErrorCode:
    """
    错误码体系

    格式: INSPXXXYYY
    - INSP: Inspector模块标识
    - XXX: 功能代码
    - YYY: 具体错误
    """

    # 通用错误 (000)
    SUCCESS = "INSP00000"
    UNKNOWN_ERROR = "INSP00001"
    INVALID_PARAM = "INSP00002"
    NOT_FOUND = "INSP00003"
    ALREADY_EXISTS = "INSP00004"

    # 数据库连接错误 (100)
    CONNECTION_FAILED = "INSP10001"
    CONNECTION_TIMEOUT = "INSP10002"
    AUTHENTICATION_FAILED = "INSP10003"
    PERMISSION_DENIED = "INSP10004"

    # 巡检执行错误 (200)
    INSPECTION_FAILED = "INSP20001"
    INSPECTION_TIMEOUT = "INSP20002"
    PARTIAL_INSPECTION = "INSP20003"

    # 报告生成错误 (300)
    REPORT_GENERATION_FAILED = "INSP30001"
    INVALID_REPORT_FORMAT = "INSP30002"

    # 基线管理错误 (400)
    BASELINE_NOT_FOUND = "INSP40001"
    BASELINE_CREATE_FAILED = "INSP40002"
    BASELINE_COMPARE_FAILED = "INSP40003"


class ErrorMessage:
    """错误消息映射"""

    MESSAGES = {
        ErrorCode.SUCCESS: "操作成功",
        ErrorCode.UNKNOWN_ERROR: "未知错误",
        ErrorCode.INVALID_PARAM: "参数无效",
        ErrorCode.NOT_FOUND: "资源不存在",
        ErrorCode.ALREADY_EXISTS: "资源已存在",
        ErrorCode.CONNECTION_FAILED: "数据库连接失败",
        ErrorCode.CONNECTION_TIMEOUT: "数据库连接超时",
        ErrorCode.AUTHENTICATION_FAILED: "数据库认证失败",
        ErrorCode.PERMISSION_DENIED: "权限不足",
        ErrorCode.INSPECTION_FAILED: "巡检执行失败",
        ErrorCode.INSPECTION_TIMEOUT: "巡检执行超时",
        ErrorCode.PARTIAL_INSPECTION: "部分巡检失败",
        ErrorCode.REPORT_GENERATION_FAILED: "报告生成失败",
        ErrorCode.INVALID_REPORT_FORMAT: "无效的报告格式",
        ErrorCode.BASELINE_NOT_FOUND: "基线不存在",
        ErrorCode.BASELINE_CREATE_FAILED: "基线创建失败",
        ErrorCode.BASELINE_COMPARE_FAILED: "基线对比失败",
    }

    @classmethod
    def get_message(cls, error_code: str) -> str:
        """获取错误消息"""
        return cls.MESSAGES.get(error_code, f"未知错误码: {error_code}")


def create_success_response(
    data: Any = None,
    message: str = "操作成功"
) -> Dict[str, Any]:
    """
    创建成功响应

    参数:
        data: 响应数据
        message: 成功消息

    返回:
        Dict: 标准成功响应格式
    """
    return {
        "success": True,
        "error_code": ErrorCode.SUCCESS,
        "message": message,
        "data": data or {}
    }


def create_error_response(
    message: str,
    error_code: str = ErrorCode.UNKNOWN_ERROR,
    details: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    创建错误响应

    参数:
        message: 错误消息
        error_code: 错误码
        details: 详细错误信息

    返回:
        Dict: 标准错误响应格式
    """
    return {
        "success": False,
        "error_code": error_code,
        "message": message,
        "error_msg": ErrorMessage.get_message(error_code),
        "details": details or {}
    }


class RiskLevel(str, Enum):
    """风险等级"""
    CRITICAL = "critical"    # 严重 - 需要立即处理
    HIGH = "high"            # 高危 - 需要尽快处理
    MEDIUM = "medium"        # 中危 - 建议处理
    LOW = "low"              # 低危 - 可选处理
    INFO = "info"            # 信息 - 仅供参考


class InspectionType(str, Enum):
    """巡检类型"""
    CONFIGURATION = "configuration"      # 配置检查
    PERFORMANCE = "performance"          # 性能检查
    SECURITY = "security"                # 安全检查
    STORAGE = "storage"                  # 存储检查
    REPLICATION = "replication"          # 复制检查
    BACKUP = "backup"                    # 备份检查
    CAPACITY = "capacity"                # 容量检查


@dataclass
class InspectionItem:
    """巡检项"""
    name: str                            # 巡检项名称
    inspection_type: InspectionType      # 巡检类型
    risk_level: RiskLevel                # 风险等级
    status: str                          # 状态: pass/warning/fail
    description: str                     # 描述
    details: Dict[str, Any] = field(default_factory=dict)  # 详细信息
    suggestion: Optional[str] = None     # 建议
    reference: Optional[str] = None      # 参考值
    actual_value: Optional[str] = None   # 实际值

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "type": self.inspection_type.value,
            "risk_level": self.risk_level.value,
            "status": self.status,
            "description": self.description,
            "details": self.details,
            "suggestion": self.suggestion,
            "reference": self.reference,
            "actual_value": self.actual_value
        }


@dataclass
class InspectionReport:
    """巡检报告"""
    report_id: str                       # 报告ID
    instance_name: str                   # 实例名称
    database_type: str                   # 数据库类型
    database_version: str                # 数据库版本
    inspection_time: datetime            # 巡检时间
    duration_seconds: float              # 巡检耗时

    # 统计信息
    total_items: int = 0                 # 总巡检项
    pass_count: int = 0                  # 通过数
    warning_count: int = 0               # 警告数
    fail_count: int = 0                  # 失败数

    # 风险统计
    critical_count: int = 0              # 严重风险数
    high_count: int = 0                  # 高危风险数
    medium_count: int = 0                # 中危风险数
    low_count: int = 0                   # 低危风险数
    info_count: int = 0                  # 信息项数

    # 巡检项
    items: List[InspectionItem] = field(default_factory=list)

    # 健康评分
    health_score: float = 100.0          # 健康评分(0-100)

    # 摘要
    summary: str = ""                    # 报告摘要

    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_id": self.report_id,
            "instance_name": self.instance_name,
            "database_type": self.database_type,
            "database_version": self.database_version,
            "inspection_time": self.inspection_time.isoformat(),
            "duration_seconds": self.duration_seconds,
            "statistics": {
                "total_items": self.total_items,
                "pass_count": self.pass_count,
                "warning_count": self.warning_count,
                "fail_count": self.fail_count,
                "critical_count": self.critical_count,
                "high_count": self.high_count,
                "medium_count": self.medium_count,
                "low_count": self.low_count,
                "info_count": self.info_count
            },
            "health_score": self.health_score,
            "summary": self.summary,
            "items": [item.to_dict() for item in self.items]
        }

    def get_health_grade(self) -> str:
        """
        获取健康等级

        等级定义：
            - healthy: >= 90分 (健康)
            - subhealthy: 80-89分 (亚健康)
            - risk: 60-79分 (风险)
            - danger: < 60分 (高危)

        返回:
            str: 健康等级标识
        """
        if self.health_score >= 90:
            return "healthy"
        elif self.health_score >= 80:
            return "subhealthy"
        elif self.health_score >= 60:
            return "risk"
        else:
            return "danger"

    def get_health_grade_label(self) -> str:
        """
        获取健康等级中文标签

        返回:
            str: 健康等级中文标签
        """
        grade_labels = {
            'healthy': '健康',
            'subhealthy': '亚健康',
            'risk': '风险',
            'danger': '高危'
        }
        return grade_labels.get(self.get_health_grade(), '未知')

    def get_pass_rate(self) -> float:
        """
        获取通过率

        返回:
            float: 通过率(0-1)
        """
        if self.total_items == 0:
            return 1.0
        return self.pass_count / self.total_items

    def generate_summary(self) -> str:
        """
        生成报告摘要

        返回:
            str: 格式化的报告摘要
        """
        grade_label = self.get_health_grade_label()
        pass_rate = self.get_pass_rate() * 100

        lines = [
            f"数据库巡检报告 - {self.instance_name}",
            f"巡检时间: {self.inspection_time.strftime('%Y-%m-%d %H:%M:%S')}",
            f"数据库: {self.database_type} {self.database_version}",
            f"",
            f"巡检统计:",
            f"  总巡检项: {self.total_items}",
            f"  通过: {self.pass_count} ({pass_rate:.1f}%)",
            f"  警告: {self.warning_count}",
            f"  失败: {self.fail_count}",
            f"",
            f"风险分布:",
            f"  严重: {self.critical_count}",
            f"  高危: {self.high_count}",
            f"  中危: {self.medium_count}",
            f"  低危: {self.low_count}",
            f"  信息: {self.info_count}",
            f"",
            f"健康评分: {self.health_score:.1f}/100 ({grade_label})",
        ]

        if self.critical_count > 0:
            lines.append(f"")
            lines.append(f"警告: 发现 {self.critical_count} 个严重风险，需要立即处理!")

        return "\n".join(lines)


@dataclass
class PerformanceBaseline:
    """性能基线"""
    baseline_id: str                     # 基线ID
    instance_name: str                   # 实例名称
    created_at: datetime                 # 创建时间
    metrics: Dict[str, float] = field(default_factory=dict)  # 指标基线值

    # 关键指标基线
    qps_baseline: Optional[float] = None
    tps_baseline: Optional[float] = None
    connection_baseline: Optional[float] = None
    query_time_baseline: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "baseline_id": self.baseline_id,
            "instance_name": self.instance_name,
            "created_at": self.created_at.isoformat(),
            "metrics": self.metrics,
            "qps_baseline": self.qps_baseline,
            "tps_baseline": self.tps_baseline,
            "connection_baseline": self.connection_baseline,
            "query_time_baseline": self.query_time_baseline
        }
