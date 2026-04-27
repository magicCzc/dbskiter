"""
dbskiter/cli.py

兼容性保留文件

此文件保留用于向后兼容，内部转发到新的模块化 CLI。
新代码建议直接使用 dbskiter.cli 模块。

旧用法（仍支持）:
    from dbskiter.cli import main
    main()

新用法（推荐）:
    from dbskiter.cli import main
    main()
    
    或
    
    from dbskiter.cli.main import main
    main()
"""

# 转发到新的模块化实现
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

# 保持原有的命令函数兼容性 - 使用简化版命令
def cmd_monitor(args):
    """兼容性：monitor 命令"""
    from dbskiter.cli.commands import MonitorCommand
    from dbskiter.cli import Config, OutputFormatter
    
    config = Config.from_args(args)
    config.validate()
    output = OutputFormatter(json_mode=getattr(args, 'json', False))
    
    cmd = MonitorCommand(config, output, args)
    return cmd.run()


def cmd_diagnose(args):
    """兼容性：diagnose 命令"""
    from dbskiter.cli.commands import DiagnoseCommand
    from dbskiter.cli import Config, OutputFormatter
    
    config = Config.from_args(args)
    config.validate()
    output = OutputFormatter(json_mode=getattr(args, 'json', False))
    
    cmd = DiagnoseCommand(config, output, args)
    return cmd.run()


def cmd_security(args):
    """兼容性：security 命令"""
    from dbskiter.cli.commands import SecurityCommand
    from dbskiter.cli import Config, OutputFormatter
    
    config = Config.from_args(args)
    config.validate()
    output = OutputFormatter(json_mode=getattr(args, 'json', False))
    
    cmd = SecurityCommand(config, output, args)
    return cmd.run()


def cmd_scheduler(args):
    """兼容性：scheduler 命令"""
    from dbskiter.cli.commands import SchedulerCommand
    from dbskiter.cli import Config, OutputFormatter
    
    config = Config.from_args(args)
    config.validate()
    output = OutputFormatter(json_mode=getattr(args, 'json', False))
    
    cmd = SchedulerCommand(config, output, args)
    return cmd.run()
