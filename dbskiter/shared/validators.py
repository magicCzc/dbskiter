"""
输入验证模块

文件功能：提供参数验证装饰器和验证函数
主要类/函数：
    - validate_params: 参数验证装饰器
    - Validator: 验证器类
    - sanitize_sql: SQL脱敏函数

使用示例：
    from dbskiter.shared.validators import validate_params, Validator
    
    @validate_params(
        table_name=Validator.not_empty_string,
        sample_size=Validator.positive_int
    )
    def scan_table(self, table_name: str, sample_size: int = 100):
        ...
"""

from typing import Dict, Any, Optional, Callable, List, Union
from functools import wraps
import re
import logging

from dbskiter.shared.error_handler import ValidationError, create_error_response

logger = logging.getLogger(__name__)


class Validator:
    """
    验证器类
    
    提供常用的参数验证函数
    
    使用示例：
        >>> Validator.not_empty_string("users")
        True
        >>> Validator.not_empty_string("")
        False
        >>> Validator.positive_int(100)
        True
        >>> Validator.positive_int(-1)
        False
    """
    
    @staticmethod
    def not_none(value: Any) -> bool:
        """验证值不为None"""
        return value is not None
    
    @staticmethod
    def not_empty_string(value: Any) -> bool:
        """验证非空字符串"""
        return isinstance(value, str) and len(value.strip()) > 0
    
    @staticmethod
    def positive_int(value: Any) -> bool:
        """验证正整数"""
        return isinstance(value, int) and value > 0
    
    @staticmethod
    def non_negative_int(value: Any) -> bool:
        """验证非负整数"""
        return isinstance(value, int) and value >= 0

    @staticmethod
    def not_empty_list(value: Any) -> bool:
        """验证非空列表"""
        return isinstance(value, list) and len(value) > 0

    @staticmethod
    def valid_limit(value: Any) -> bool:
        """验证有效的LIMIT值"""
        return isinstance(value, int) and 0 < value <= 10000

    @staticmethod
    def valid_table_name(value: Any) -> bool:
        """验证有效的表名"""
        if not isinstance(value, str):
            return False
        # 表名不能包含特殊字符
        return re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', value) is not None
    
    @staticmethod
    def valid_column_name(value: Any) -> bool:
        """验证有效的列名"""
        if not isinstance(value, str):
            return False
        # 列名不能包含特殊字符
        return re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', value) is not None
    
    @staticmethod
    def valid_sql_identifier(value: Any) -> bool:
        """验证有效的SQL标识符"""
        if not isinstance(value, str):
            return False
        # 防止SQL注入：不能包含多个语句或注释
        dangerous_patterns = [
            r';.*',  # 多语句
            r'--',   # 单行注释
            r'/\*',  # 多行注释开始
            r'\*/',  # 多行注释结束
            r'xp_',  # 扩展存储过程
            r'sp_',  # 存储过程
            r'drop\s+',  # DROP语句
            r'delete\s+',  # DELETE语句
            r'insert\s+',  # INSERT语句
            r'update\s+',  # UPDATE语句
        ]
        for pattern in dangerous_patterns:
            if re.search(pattern, value, re.IGNORECASE):
                return False
        return True
    
    @staticmethod
    def in_range(min_val: Union[int, float], max_val: Union[int, float]) -> Callable:
        """验证数值在范围内"""
        def validator(value: Any) -> bool:
            return isinstance(value, (int, float)) and min_val <= value <= max_val
        return validator
    
    @staticmethod
    def one_of(choices: List[Any]) -> Callable:
        """验证值在可选列表中"""
        def validator(value: Any) -> bool:
            return value in choices
        return validator
    
    @staticmethod
    def list_not_empty(value: Any) -> bool:
        """验证非空列表"""
        return isinstance(value, list) and len(value) > 0
    
    @staticmethod
    def valid_limit(value: Any) -> bool:
        """验证有效的LIMIT值（1-10000），None表示不验证"""
        if value is None:
            return True
        return isinstance(value, int) and 1 <= value <= 10000
    
    @staticmethod
    def valid_timeout(value: Any) -> bool:
        """验证有效的超时值（1-3600秒）"""
        return isinstance(value, (int, float)) and 1 <= value <= 3600


def validate_params(**validators: Callable) -> Callable:
    """
    参数验证装饰器
    
    在函数执行前验证参数，验证失败返回错误响应
    
    参数:
        **validators: 参数名到验证函数的映射
    
    返回:
        Callable: 装饰器函数
    
    使用示例：
        >>> @validate_params(
        ...     table_name=Validator.not_empty_string,
        ...     sample_size=Validator.positive_int
        ... )
        ... def scan_table(self, table_name: str, sample_size: int = 100):
        ...     return {"status": "success"}
        
        >>> scan_table("users", 100)  # 通过
        {'status': 'success'}
        
        >>> scan_table("", 100)  # 失败
        {'success': False, 'error': {...}}
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # 获取参数名和值
            import inspect
            sig = inspect.signature(func)
            bound_args = sig.bind(*args, **kwargs)
            bound_args.apply_defaults()
            
            # 验证每个参数
            for param_name, validator in validators.items():
                if param_name in bound_args.arguments:
                    value = bound_args.arguments[param_name]
                    if not validator(value):
                        error_msg = f"参数 '{param_name}' 验证失败，值: {value}"
                        logger.warning(f"[验证失败] {func.__name__}: {error_msg}")
                        return create_error_response(
                            ValidationError(error_msg, details={"param": param_name, "value": value}),
                            context=f"{func.__name__} 参数验证"
                        )
            
            # 验证通过，执行原函数
            return func(*args, **kwargs)
        return wrapper
    return decorator


def sanitize_sql(sql: str, max_length: int = 200) -> str:
    """
    SQL脱敏函数
    
    移除SQL中的敏感信息（如密码、密钥等），用于日志记录
    
    参数:
        sql: str - 原始SQL语句
        max_length: int - 最大长度，默认为200
    
    返回:
        str - 脱敏后的SQL
    
    使用示例：
        >>> sanitize_sql("SELECT * FROM users WHERE password = 'secret123'")
        "SELECT * FROM users WHERE password = '***'"
        
        >>> sanitize_sql("INSERT INTO users (name, ssn) VALUES ('John', '123-45-6789')")
        "INSERT INTO users (name, ssn) VALUES ('John', '***')"
    """
    if not sql:
        return ""
    
    # 敏感字段模式
    sensitive_patterns = [
        # 密码相关
        (r"(password\s*=\s*)['\"][^'\"]*['\"]", r"\1'***'"),
        (r"(passwd\s*=\s*)['\"][^'\"]*['\"]", r"\1'***'"),
        (r"(pwd\s*=\s*)['\"][^'\"]*['\"]", r"\1'***'"),
        
        # 密钥相关
        (r"(secret\s*=\s*)['\"][^'\"]*['\"]", r"\1'***'"),
        (r"(key\s*=\s*)['\"][^'\"]*['\"]", r"\1'***'"),
        (r"(token\s*=\s*)['\"][^'\"]*['\"]", r"\1'***'"),
        (r"(api_key\s*=\s*)['\"][^'\"]*['\"]", r"\1'***'"),
        
        # 个人信息
        (r"(ssn\s*=\s*)['\"][^'\"]*['\"]", r"\1'***'"),
        (r"(social_security\s*=\s*)['\"][^'\"]*['\"]", r"\1'***'"),
        (r"(credit_card\s*=\s*)['\"][^'\"]*['\"]", r"\1'***'"),
        (r"(card_number\s*=\s*)['\"][^'\"]*['\"]", r"\1'***'"),
        
        # 邮箱（保留域名）
        (r"['\"][\w\.-]+@[\w\.-]+\.\w+['\"]", r"'***@***.***'"),
        
        # 手机号
        (r"['\"]\d{3}-\d{3}-\d{4}['\"]", r"'***-***-****'"),
        (r"['\"]\d{11}['\"]", r"'***********'"),
    ]
    
    sanitized = sql
    for pattern, replacement in sensitive_patterns:
        sanitized = re.sub(pattern, replacement, sanitized, flags=re.IGNORECASE)
    
    # 截断长度
    if len(sanitized) > max_length:
        sanitized = sanitized[:max_length] + "..."
    
    return sanitized


def sanitize_dict(data: Dict[str, Any], sensitive_keys: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    字典脱敏函数
    
    对字典中的敏感字段进行脱敏
    
    参数:
        data: Dict[str, Any] - 原始字典
        sensitive_keys: Optional[List[str]] - 敏感字段列表，默认使用常见敏感字段
    
    返回:
        Dict[str, Any] - 脱敏后的字典
    
    使用示例：
        >>> sanitize_dict({"name": "John", "password": "secret123"})
        {"name": "John", "password": "***"}
    """
    if sensitive_keys is None:
        sensitive_keys = [
            "password", "passwd", "pwd", "secret", "key", "token",
            "api_key", "ssn", "social_security", "credit_card",
            "card_number", "phone", "email", "mobile"
        ]
    
    result = {}
    for key, value in data.items():
        if any(sk in key.lower() for sk in sensitive_keys):
            result[key] = "***"
        elif isinstance(value, dict):
            result[key] = sanitize_dict(value, sensitive_keys)
        elif isinstance(value, list):
            result[key] = [
                sanitize_dict(item, sensitive_keys) if isinstance(item, dict) else item
                for item in value
            ]
        else:
            result[key] = value
    
    return result


# 便捷验证函数
def validate_table_name(table_name: str) -> Optional[str]:
    """
    验证表名
    
    参数:
        table_name: str - 表名
    
    返回:
        Optional[str] - 错误消息，验证通过返回None
    
    使用示例：
        >>> validate_table_name("users")
        None
        >>> validate_table_name("")
        "表名不能为空"
        >>> validate_table_name("123table")
        "表名格式无效"
    """
    if not table_name:
        return "表名不能为空"
    if not isinstance(table_name, str):
        return "表名必须是字符串"
    if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', table_name):
        return "表名格式无效，只能包含字母、数字和下划线，且不能以数字开头"
    if len(table_name) > 64:
        return "表名长度不能超过64个字符"
    return None


def validate_limit(limit: int, max_limit: int = 10000) -> Optional[str]:
    """
    验证LIMIT值
    
    参数:
        limit: int - LIMIT值
        max_limit: int - 最大值，默认为10000
    
    返回:
        Optional[str] - 错误消息，验证通过返回None
    """
    if not isinstance(limit, int):
        return "LIMIT必须是整数"
    if limit < 1:
        return "LIMIT必须大于0"
    if limit > max_limit:
        return f"LIMIT不能超过{max_limit}"
    return None


def validate_timeout(timeout: float, max_timeout: float = 3600) -> Optional[str]:
    """
    验证超时值
    
    参数:
        timeout: float - 超时值（秒）
        max_timeout: float - 最大超时值，默认为3600
    
    返回:
        Optional[str] - 错误消息，验证通过返回None
    """
    if not isinstance(timeout, (int, float)):
        return "超时值必须是数字"
    if timeout < 1:
        return "超时值必须大于0秒"
    if timeout > max_timeout:
        return f"超时值不能超过{max_timeout}秒"
    return None
