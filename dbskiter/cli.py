"""
dbskiter/cli.py

兼容性保留文件

此文件保留用于向后兼容，内部转发到新的模块化 CLI。
所有实际逻辑在 dbskiter.cli 包中实现。
"""

from dbskiter.cli import main, Config, get_db_config
from dbskiter.cli.output import OutputFormatter, TableFormatter
from dbskiter.cli.exceptions import CLIError, ConfigError, CommandError

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
