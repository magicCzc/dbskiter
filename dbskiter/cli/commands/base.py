"""
cli/commands/base.py

命令基类

提供统一的命令接口和自动注册机制
"""

from abc import ABCMeta, abstractmethod
from argparse import ArgumentParser, Namespace
from typing import Dict, Type, Any, Optional

from ..config import Config
from ..output import OutputFormatter
from ..exceptions import CommandError


# 全局命令注册表
command_registry: Dict[str, Type["BaseCommand"]] = {}


class CommandMeta(ABCMeta):
    """
    命令元类
    
    自动注册命令到注册表（继承 ABCMeta 避免元类冲突）
    """
    def __new__(mcs, name, bases, namespace):
        cls = super().__new__(mcs, name, bases, namespace)
        # 不注册基类
        if name != "BaseCommand" and hasattr(cls, "name") and cls.name:
            command_registry[cls.name] = cls
        return cls


class BaseCommand(metaclass=CommandMeta):
    """
    命令基类
    
    所有 CLI 命令的基类，定义统一接口
    
    属性:
        name: 命令名称
        description: 命令描述
        help_text: 帮助文本
    
    用法:
        >>> class MyCommand(BaseCommand):
        ...     name = "mycommand"
        ...     description = "My command"
        ...     
        ...     def add_arguments(self, parser):
        ...         parser.add_argument("--option")
        ...     
        ...     def execute(self):
        ...         self.output.print("Hello!")
    """
    
    name: str = ""
    description: str = ""
    help_text: str = ""
    
    def __init__(self, config: Config, output: OutputFormatter, args: Namespace):
        """
        初始化命令
        
        参数:
            config: 配置对象
            output: 输出格式化器
            args: 解析后的参数
        """
        self.config = config
        self.output = output
        self.args = args
        self._connector = None
    
    @property
    def connector(self):
        """
        获取数据库连接器（延迟加载）
        
        返回:
            UnifiedConnector: 统一数据库连接器（支持 SQLAlchemy 和 JDBC）
        """
        if self._connector is None:
            from dbskiter.shared.unified_connector import UnifiedConnector
            
            # 使用配置中的数据库连接信息（支持--database参数覆盖）
            # 传递 extra 参数（包含 Oracle service_name 和 jdbc_driver_path 等）
            self._connector = UnifiedConnector(
                dialect=self.config.dialect,
                host=self.config.host,
                port=self.config.port,
                username=self.config.username,
                password=self.config.password,
                database=self.config.database,
                **self.config.extra
            )
            
        return self._connector
    
    @classmethod
    def add_arguments(cls, parser: ArgumentParser) -> None:
        """
        添加命令参数
        
        子类可重写此方法添加自定义参数
        
        参数:
            parser: 参数解析器
        """
        pass
    
    @abstractmethod
    def execute(self) -> int:
        """
        执行命令
        
        子类必须实现此方法
        
        返回:
            int: 退出码，0 表示成功
        """
        raise NotImplementedError
    
    def run(self) -> int:
        """
        运行命令（包装 execute）
        
        处理异常和清理资源
        
        返回:
            int: 退出码
        """
        try:
            return self.execute()
        except CommandError as e:
            self.output.error(e.message)
            return e.exit_code
        except Exception as e:
            self.output.error(f"命令执行失败: {e}")
            return 1
        finally:
            self.cleanup()
    
    def cleanup(self) -> None:
        """
        清理资源
        
        子类可重写此方法进行资源清理
        """
        if self._connector:
            try:
                self._connector.close()
            except Exception:
                pass
    
    def print_header(self, title: str) -> None:
        """打印命令头"""
        self.output.header(f"{self.description} - {self.config.database}")
    
    def require_connector(self) -> None:
        """
        确保数据库连接可用
        
        异常:
            CommandError: 连接失败时抛出
        """
        try:
            # 触发连接测试
            _ = self.connector
        except Exception as e:
            raise CommandError(f"数据库连接失败: {e}")
