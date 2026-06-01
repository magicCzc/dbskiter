"""
统一错误处理模块

文件功能：提供标准化的错误处理机制和错误响应格式
主要类/函数：
    - ErrorCode: 错误码枚举
    - SkillError: 基础异常类
    - handle_exception: 统一异常处理函数
    - create_error_response: 创建标准错误响应

使用示例：
    from dbskiter.shared.error_handler import handle_exception, create_error_response
    
    try:
        result = some_operation()
    except Exception as e:
        return handle_exception(e, context="执行操作")
"""

import builtins
from typing import Dict, Any, Optional, Type
from datetime import datetime
from enum import Enum
import logging
import traceback

logger = logging.getLogger(__name__)


class ErrorCode(Enum):
    """
    错误码枚举
    
    错误码格式：CATEGORY_NUMBER
    - 1xxx: 连接错误
    - 2xxx: 查询错误
    - 3xxx: 配置错误
    - 4xxx: 权限错误
    - 5xxx: 系统错误
    - 9xxx: 未知错误
    """
    # 连接错误 (1xxx)
    CONNECTION_FAILED = "1001"
    CONNECTION_TIMEOUT = "1002"
    CONNECTION_CLOSED = "1003"
    AUTHENTICATION_FAILED = "1004"
    
    # 查询错误 (2xxx)
    QUERY_FAILED = "2001"
    QUERY_TIMEOUT = "2002"
    INVALID_SQL = "2003"
    TABLE_NOT_FOUND = "2004"
    COLUMN_NOT_FOUND = "2005"
    
    # 配置错误 (3xxx)
    CONFIG_INVALID = "3001"
    CONFIG_MISSING = "3002"
    CONFIG_DEPRECATED = "3003"
    
    # 权限错误 (4xxx)
    PERMISSION_DENIED = "4001"
    INSUFFICIENT_PRIVILEGE = "4002"
    
    # 系统错误 (5xxx)
    SYSTEM_ERROR = "5001"
    RESOURCE_EXHAUSTED = "5002"
    OPERATION_CANCELLED = "5003"
    
    # 未知错误 (9xxx)
    UNKNOWN_ERROR = "9999"


class SkillError(Exception):
    """
    Skill 基础异常类
    
    所有 Skill 相关的异常都应该继承此类
    
    属性:
        code: 错误码
        message: 错误消息
        details: 详细错误信息
        timestamp: 错误发生时间
    
    使用示例：
        raise SkillError(
            code=ErrorCode.CONNECTION_FAILED,
            message="数据库连接失败",
            details={"host": "localhost", "port": 3306}
        )
    """
    
    def __init__(
        self,
        code: ErrorCode,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None
    ):
        """
        初始化 SkillError
        
        参数:
            code: ErrorCode - 错误码枚举值
            message: str - 错误消息
            details: Optional[Dict[str, Any]] - 详细错误信息，默认为None
            cause: Optional[Exception] - 原始异常，默认为None
        
        返回:
            无返回值
        
        使用示例：
            raise SkillError(
                code=ErrorCode.QUERY_FAILED,
                message="查询执行失败",
                details={"sql": "SELECT * FROM users"}
            )
        """
        self.code = code
        self.message = message
        self.details = details or {}
        self.cause = cause
        self.timestamp = datetime.now().isoformat()
        
        # 构建完整的错误消息
        full_message = f"[{code.value}] {message}"
        if cause:
            full_message += f" (caused by: {type(cause).__name__}: {cause})"
        
        super().__init__(full_message)
    
    def to_dict(self) -> Dict[str, Any]:
        """
        转换为字典格式
        
        返回:
            Dict[str, Any] - 包含错误信息的字典
        
        使用示例：
            >>> error = SkillError(code=ErrorCode.CONNECTION_FAILED, message="连接失败")
            >>> error.to_dict()
            {'code': '1001', 'message': '连接失败', ...}
        """
        return {
            "code": self.code.value,
            "message": self.message,
            "details": self.details,
            "timestamp": self.timestamp,
            "exception_type": type(self.cause).__name__ if self.cause else None
        }


class ConnectionError(SkillError):
    """连接错误"""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None, cause: Optional[Exception] = None):
        super().__init__(ErrorCode.CONNECTION_FAILED, message, details, cause)


class QueryError(SkillError):
    """查询错误"""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None, cause: Optional[Exception] = None):
        super().__init__(ErrorCode.QUERY_FAILED, message, details, cause)


class ConfigError(SkillError):
    """配置错误"""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None, cause: Optional[Exception] = None):
        super().__init__(ErrorCode.CONFIG_INVALID, message, details, cause)


class DBPermissionError(SkillError):
    """数据库权限错误"""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None, cause: Optional[Exception] = None):
        super().__init__(ErrorCode.PERMISSION_DENIED, message, details, cause)


class ValidationError(SkillError):
    """参数验证错误"""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None, cause: Optional[Exception] = None):
        super().__init__(ErrorCode.CONFIG_INVALID, message, details, cause)


class DBTimeoutError(SkillError):
    """数据库超时错误"""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None, cause: Optional[Exception] = None):
        super().__init__(ErrorCode.CONNECTION_TIMEOUT, message, details, cause)


class ResourceExhaustedError(SkillError):
    """资源耗尽错误"""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None, cause: Optional[Exception] = None):
        super().__init__(ErrorCode.RESOURCE_EXHAUSTED, message, details, cause)


def create_error_response(
    error: Any,
    context: Optional[Any] = None,
    include_traceback: bool = False,
    error_code: Optional[Any] = None,
    details: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    创建标准错误响应

    统一的错误响应格式，所有 Skill 都应该使用此函数创建错误响应

    支持多种调用方式：
    方式1（异常对象）：create_error_response(exception, context="操作")
    方式2（消息+错误码字符串）：create_error_response("错误消息", "MON000001")
    方式3（消息+error_code参数+details）：create_error_response("错误消息", error_code="MON000001", details={...})

    参数:
        error: Exception 或 str - 异常对象或错误消息
        context: Optional[str] 或 str - 错误上下文或错误码字符串
        include_traceback: bool - 是否包含堆栈跟踪，默认为False
        error_code: Optional[str] - 错误码字符串（方式3使用）
        details: Optional[Dict] - 详细错误信息

    返回:
        Dict[str, Any] - 标准格式的错误响应字典

    使用示例：
        >>> # 方式1：异常对象
        >>> try:
        ...     result = execute_query(sql)
        ... except Exception as e:
        ...     return create_error_response(e, context="执行SQL查询")

        >>> # 方式2：消息+错误码字符串
        >>> return create_error_response("参数错误", "DIA000002")

        >>> # 方式3：消息+error_code参数+details
        >>> return create_error_response("连接失败", error_code="MON100003", details={"host": "localhost"})
    """
    timestamp = datetime.now().isoformat()

    if isinstance(error, Exception):
        if isinstance(error, SkillError):
            code_str = error.code.value if hasattr(error.code, 'value') else str(error.code)
            error_info = {
                "code": code_str,
                "type": type(error).__name__,
                "message": error.message,
                "context": context if isinstance(context, str) else None,
                "details": error.details,
                "timestamp": error.timestamp
            }
        else:
            mapped_code = _map_exception_to_code(error)
            error_info = {
                "code": mapped_code.value,
                "type": type(error).__name__,
                "message": str(error),
                "context": context if isinstance(context, str) else None,
                "details": details or {},
                "timestamp": timestamp
            }

        if include_traceback:
            error_info["traceback"] = traceback.format_exc()

        response = {
            "success": False,
            "error": error_info,
            "timestamp": timestamp
        }

        log_level = logging.ERROR if str(error_info.get("code", "")).startswith("5") else logging.WARNING
        logger.log(log_level, f"[{error_info['code']}] {context}: {error_info['message']}")

        return response
    else:
        message = str(error)

        if error_code is not None:
            final_error_code = error_code.value if hasattr(error_code, 'value') else str(error_code)
        elif isinstance(context, str) and not context.startswith("DB_"):
            final_error_code = str(context) if context else "9999"
        else:
            final_error_code = "9999"

        return {
            "success": False,
            "error": {
                "code": final_error_code,
                "message": message,
                "context": context if isinstance(context, str) else None,
                "details": details or {},
                "timestamp": timestamp
            },
            "timestamp": timestamp
        }


def handle_exception(
    error: Exception,
    context: Optional[str] = None,
    fallback_value: Any = None,
    reraise: bool = False
) -> Dict[str, Any]:
    """
    统一异常处理函数
    
    捕获异常并返回标准错误响应，可选重新抛出或返回默认值
    
    参数:
        error: Exception - 捕获的异常
        context: Optional[str] - 错误上下文
        fallback_value: Any - 如果不重新抛出，返回的默认值
        reraise: bool - 是否重新抛出异常，默认为False
    
    返回:
        Dict[str, Any] - 错误响应或fallback_value
    
    使用示例：
        >>> try:
        ...     result = risky_operation()
        ...     return {'success': True, 'data': result}
        ... except Exception as e:
        ...     return handle_exception(e, context="风险操作")
    """
    response = create_error_response(error, context)
    
    if reraise:
        raise
    
    if fallback_value is not None:
        return fallback_value
    
    return response


def _map_exception_to_code(error: Exception) -> ErrorCode:
    """
    将异常类型映射到错误码
    
    参数:
        error: Exception - 异常对象
    
    返回:
        ErrorCode - 对应的错误码
    
    使用示例：
        >>> _map_exception_to_code(ConnectionRefusedError())
        <ErrorCode.CONNECTION_FAILED: '1001'>
    """
    exception_map = {
        # 连接错误
        ConnectionRefusedError: ErrorCode.CONNECTION_FAILED,
        ConnectionResetError: ErrorCode.CONNECTION_CLOSED,
        builtins.TimeoutError: ErrorCode.CONNECTION_TIMEOUT,

        # 查询错误
        SyntaxError: ErrorCode.INVALID_SQL,
        KeyError: ErrorCode.COLUMN_NOT_FOUND,

        # 权限错误
        builtins.PermissionError: ErrorCode.PERMISSION_DENIED,
    }
    
    error_type = type(error)
    return exception_map.get(error_type, ErrorCode.UNKNOWN_ERROR)


# 便捷函数：成功响应
def create_success_response(
    data: Any = None,
    message: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    创建标准成功响应
    
    参数:
        data: Any - 响应数据
        message: Optional[str] - 成功消息
        metadata: Optional[Dict[str, Any]] - 元数据
    
    返回:
        Dict[str, Any] - 标准格式的成功响应
    
    使用示例：
        >>> create_success_response(data=result, message="查询成功")
        {
            'success': True,
            'data': {...},
            'message': '查询成功',
            'timestamp': '2025-01-21T10:30:00'
        }
    """
    response = {
        "success": True,
        "timestamp": datetime.now().isoformat()
    }
    
    if data is not None:
        response["data"] = data
    
    if message:
        response["message"] = message
    
    if metadata:
        response["metadata"] = metadata
    
    return response
