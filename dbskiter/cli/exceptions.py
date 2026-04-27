"""
cli/exceptions.py

CLI 异常定义

提供统一的异常层次结构，便于错误处理和用户提示
"""


class CLIError(Exception):
    """
    CLI 基础异常
    
    所有 CLI 异常的基类
    
    属性:
        exit_code: 程序退出码
        message: 错误信息
    """
    exit_code = 1
    
    def __init__(self, message: str, exit_code: int = None):
        super().__init__(message)
        self.message = message
        if exit_code is not None:
            self.exit_code = exit_code


class ConfigError(CLIError):
    """
    配置错误
    
    数据库配置、环境变量等问题
    
    示例:
        raise ConfigError("缺少必要的数据库配置: DB_HOST")
    """
    exit_code = 2


class CommandError(CLIError):
    """
    命令执行错误
    
    命令执行过程中发生的错误
    
    示例:
        raise CommandError("数据库连接失败")
    """
    exit_code = 3


class ValidationError(CLIError):
    """
    参数验证错误
    
    用户输入参数不合法
    
    示例:
        raise ValidationError("端口号必须是 1-65535 之间的整数")
    """
    exit_code = 4


class DatabaseError(CLIError):
    """
    数据库操作错误
    
    数据库连接、查询等操作失败
    
    示例:
        raise DatabaseError("查询执行超时")
    """
    exit_code = 5


class OutputError(CLIError):
    """
    输出格式化错误
    
    结果输出、格式化失败
    
    示例:
        raise OutputError("JSON 序列化失败")
    """
    exit_code = 6
