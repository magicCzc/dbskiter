"""
cli/commands/__init__.py

命令模块（简化版）

所有 CLI 命令的集合 - 只保留核心功能
"""

from .base import BaseCommand, command_registry
from .monitor import MonitorCommand
from .diagnose import DiagnoseCommand
from .security import SecurityCommand
from .scheduler import SchedulerCommand
from .sql import SQLCommand
from .inspector import InspectorCommand
from .lock import LockCommand
from .audit import AuditCommand
from .init import InitCommand
from .shell_setup import ShellSetupCommand
from .config_cmd import ConfigCommand
from .history_cmd import HistoryCommand

__all__ = [
    "BaseCommand",
    "command_registry",
    "MonitorCommand",
    "DiagnoseCommand",
    "SecurityCommand",
    "SchedulerCommand",
    "SQLCommand",
    "InspectorCommand",
    "LockCommand",
    "AuditCommand",
    "InitCommand",
    "ShellSetupCommand",
    "ConfigCommand",
    "HistoryCommand",
]
