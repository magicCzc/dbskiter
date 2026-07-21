"""
cli/error_handler.py

错误处理模块

提供统一的错误处理、日志记录和用户友好的错误提示
"""

from __future__ import annotations

import sys
import traceback
from typing import Optional, Callable, Any
from functools import wraps

from .exceptions import CLIError, ConfigError, CommandError, DatabaseError
from .output import OutputFormatter
from dbskiter.shared.error_handler import DBPermissionError, DBTimeoutError


class ErrorHandler:
    """
    错误处理器
    
    统一管理错误处理和用户提示
    
    用法:
        >>> handler = ErrorHandler()
        >>> handler.handle_error(e, output)
    """
    
    def __init__(self, debug: bool = False):
        """
        初始化错误处理器
        
        参数:
            debug: 是否启用调试模式（显示完整堆栈）
        """
        self.debug = debug
        self.error_counts = {
            "config": 0,
            "database": 0,
            "command": 0,
            "validation": 0,
            "other": 0,
        }
    
    def handle_error(self, error: Exception, output: OutputFormatter) -> int:
        """
        处理错误
        
        参数:
            error: 异常对象
            output: 输出格式化器
            
        返回:
            int: 退出码
        """
        # 分类统计
        self._categorize_error(error)
        
        # 获取错误信息
        exit_code, user_message = self._get_error_info(error)
        
        # 显示错误
        output.error(user_message)
        
        # 调试模式显示堆栈
        if self.debug:
            output.print("\n[DEBUG] 详细错误信息:")
            output.print(traceback.format_exc())
        
        # JSON 输出错误
        if output.json_mode:
            output.output_json({
                "success": False,
                "error": user_message,
                "error_type": type(error).__name__,
                "exit_code": exit_code
            })
        
        return exit_code
    
    def _categorize_error(self, error: Exception) -> None:
        """分类统计错误"""
        if isinstance(error, ConfigError):
            self.error_counts["config"] += 1
        elif isinstance(error, DatabaseError):
            self.error_counts["database"] += 1
        elif isinstance(error, CommandError):
            self.error_counts["command"] += 1
        elif isinstance(error, CLIError):
            self.error_counts["validation"] += 1
        else:
            self.error_counts["other"] += 1
    
    def _get_error_info(self, error: Exception) -> tuple[int, str]:
        """
        获取错误信息

        返回:
            tuple: (退出码, 用户友好消息)
        """
        # 配置错误 - 给出更友好的引导提示（ConfigError 继承自 CLIError，必须先检查）
        if isinstance(error, ConfigError):
            msg = str(error)
            # 检测配置缺失场景，添加引导
            if "未找到数据库配置" in msg or "未找到默认数据库配置" in msg or "请设置" in msg or "但检测到以下别名" in msg:
                friendly = f"""{msg}

┌──────────────────────────────────────────────┐
│  如何解决？                                   │
├──────────────────────────────────────────────┤
│  1. 交互式配置向导: dbskiter init               │
│  2. 快速生成模板: dbskiter init --quick        │
│  3. 演示模式体验: dbskiter --demo health       │
│  4. 查看帮助: dbskiter welcome                 │
└──────────────────────────────────────────────┘"""
                return error.exit_code, friendly
            return error.exit_code, msg

        # CLI 异常（ConfigError 之外的 CLI 错误）
        if isinstance(error, CLIError):
            return error.exit_code, error.message

        # 常见 Python 异常
        if isinstance(error, KeyboardInterrupt):
            return 130, "操作已取消"
        
        if isinstance(error, FileNotFoundError):
            return 2, f"文件未找到: {error.filename or str(error)}"
        
        if isinstance(error, PermissionError):
            return 13, f"权限不足: {error.filename or str(error)}"

        if isinstance(error, DBPermissionError):
            return 13, f"数据库权限不足: {error.message}"

        if isinstance(error, ConnectionError):
            return 5, f"连接失败: {error}"

        if isinstance(error, TimeoutError):
            return 124, f"操作超时: {error}"

        if isinstance(error, DBTimeoutError):
            return 124, f"数据库操作超时: {error.message}"
        
        # 未知异常
        if self.debug:
            return 1, f"{type(error).__name__}: {error}"
        else:
            return 1, f"发生错误: {error}"
    
    def get_error_summary(self) -> dict:
        """获取错误统计摘要"""
        total = sum(self.error_counts.values())
        return {
            "total": total,
            **self.error_counts
        }


def with_error_handling(debug: bool = False):
    """
    错误处理装饰器
    
    自动捕获和处理异常
    
    用法:
        >>> @with_error_handling(debug=True)
        ... def my_command():
        ...     raise ValueError("test")
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            handler = ErrorHandler(debug=debug)
            output = OutputFormatter()
            
            try:
                return func(*args, **kwargs)
            except Exception as e:
                return handler.handle_error(e, output)
        
        return wrapper
    return decorator


class RetryHandler:
    """
    重试处理器
    
    处理可重试的操作
    
    用法:
        >>> handler = RetryHandler(max_retries=3)
        >>> result = handler.retry(lambda: db.query())
    """
    
    def __init__(self, max_retries: int = 3, delay: float = 1.0, 
                 exceptions: tuple = (Exception,)):
        """
        初始化重试处理器
        
        参数:
            max_retries: 最大重试次数
            delay: 重试间隔（秒）
            exceptions: 需要重试的异常类型
        """
        self.max_retries = max_retries
        self.delay = delay
        self.exceptions = exceptions
        self.attempt = 0
    
    def retry(self, func: Callable, *args, **kwargs) -> Any:
        """
        执行带重试的操作
        
        参数:
            func: 要执行的函数
            *args, **kwargs: 函数参数
            
        返回:
            Any: 函数返回值
            
        异常:
            Exception: 重试耗尽后抛出最后一次异常
        """
        last_error = None
        
        for attempt in range(self.max_retries + 1):
            self.attempt = attempt
            
            try:
                return func(*args, **kwargs)
            except self.exceptions as e:
                last_error = e
                
                if attempt < self.max_retries:
                    import time
                    time.sleep(self.delay * (attempt + 1))  # 指数退避
                
        raise last_error


# 便捷函数
def format_error_for_user(error: Exception) -> str:
    """
    格式化错误为用户友好消息
    
    参数:
        error: 异常对象
        
    返回:
        str: 用户友好消息
    """
    handler = ErrorHandler()
    _, message = handler._get_error_info(error)
    return message


def get_exit_code(error: Exception) -> int:
    """
    获取错误对应的退出码
    
    参数:
        error: 异常对象
        
    返回:
        int: 退出码
    """
    handler = ErrorHandler()
    exit_code, _ = handler._get_error_info(error)
    return exit_code
