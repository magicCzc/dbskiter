"""
shared - 共享模块

文件功能：所有 Skill 共用的基础设施
主要导出:
    - UnifiedConnector: 统一数据库连接器
    - QueryResult: 统一查询结果封装
    - error_handler: 错误处理模块
    - validators: 验证工具

使用示例:
    >>> from dbskiter.shared import UnifiedConnector, QueryResult
    >>> from dbskiter.shared.error_handler import create_success_response
    >>> from dbskiter.shared.validators import validate_sql

版本: 2.0.0
作者: AI Assistant
创建时间: 2026-04-24
"""

# 核心连接器
from .unified_connector import UnifiedConnector, detect_connector_type
from .query_result import QueryResult

# 通用工具函数
from .utils import format_bytes, format_duration, truncate_text

# 数据模型
from .models import (
    PipelineStep,
    PipelineResult,
    UnifiedPipelineResult
)

# 错误处理
from .error_handler import (
    ErrorCode,
    SkillError,
    ConnectionError,
    QueryError,
    ConfigError,
    DBPermissionError,
    ValidationError,
    DBTimeoutError,
    ResourceExhaustedError,
    create_error_response,
    create_success_response,
    handle_exception
)

__all__ = [
    # 连接器
    "UnifiedConnector",
    "detect_connector_type",
    "QueryResult",
    # 工具函数
    "format_bytes",
    "format_duration",
    "truncate_text",
    # 数据模型
    "PipelineStep",
    "PipelineResult",
    "UnifiedPipelineResult",
    # 错误处理
    "ErrorCode",
    "SkillError",
    "ConnectionError",
    "QueryError",
    "ConfigError",
    "DBPermissionError",
    "ValidationError",
    "DBTimeoutError",
    "ResourceExhaustedError",
    "create_error_response",
    "create_success_response",
    "handle_exception"
]
