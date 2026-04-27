"""
dbskiter.cli

CLI 模块 - 数据库 Skills 统一命令行入口

重构记录：
- 2026-04-16: 从单文件 cli.py 重构为模块化结构
- 支持命令自动注册和插件扩展

用法:
    from dbskiter.cli import main
    main()
"""

from .main import main
from .config import Config, get_db_config
from .output import OutputFormatter, TableFormatter
from .exceptions import CLIError, ConfigError, CommandError

__all__ = [
    "main",
    "Config",
    "get_db_config",
    "OutputFormatter",
    "TableFormatter",
    "CLIError",
    "ConfigError",
    "CommandError",
]
