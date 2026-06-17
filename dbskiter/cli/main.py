"""
cli/main.py

CLI 主入口

负责：
- 参数解析
- 命令分发
- 全局错误处理
"""

import os
import sys
import logging
import argparse
from typing import List, Optional

try:
    import argcomplete
    HAS_ARGCOMPLETE = True
except ImportError:
    argcomplete = None
    HAS_ARGCOMPLETE = False

from .. import __version__
from .config import Config, MultiDBConfig
from .output import OutputFormatter
from .exceptions import CLIError, ConfigError
from .commands import command_registry, BaseCommand
from .error_handler import ErrorHandler
from .banner import print_banner, print_minimal_banner
from .style import get_console
from ..shared import HistoryManager


def create_parser() -> argparse.ArgumentParser:
    """
    创建参数解析器
    
    返回:
        ArgumentParser: 配置好的解析器
    """
    parser = argparse.ArgumentParser(
        prog="dbskiter",
        description="数据库 Skills CLI - 数据库监控、诊断、安全、调度、SQL执行",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
╔══════════════════════════════════════════════════════════════╗
║  常用命令                                                    ║
╠══════════════════════════════════════════════════════════════╣
║  dbskiter init              [推荐] 交互式配置向导              ║
║  dbskiter --database=jump monitor health      健康检查      ║
║  dbskiter --database=jump diagnose slow-queries 慢查询      ║
║  dbskiter --database=jump security audit       安全审计     ║
║  dbskiter shell-setup --auto     一键启用 Tab 补全          ║
╠══════════════════════════════════════════════════════════════╣
║  命令语法: dbskiter [全局选项] <命令> [子命令选项]           ║
║  全局选项（--database, --host 等）必须放在命令之前！         ║
╠══════════════════════════════════════════════════════════════╣
║  更多示例:                                                    ║
║  dbskiter --database=jump monitor anomalies --hours=6       ║
║  dbskiter --database=jump diagnose sql "SELECT ..."         ║
║  dbskiter --database=jump security score                   ║
║  dbskiter --host=192.168.1.1 --user=root --password=xxx     ║
║            monitor health                                   ║
╚══════════════════════════════════════════════════════════════╝
""",
    )
    
    # 全局参数
    parser.add_argument(
        "--version",
        "-V",
        action="store_true",
        help="显示版本信息并退出"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="输出 JSON 格式结果"
    )
    parser.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help="静默模式，只输出结果"
    )
    parser.add_argument(
        "--no-color",
        action="store_true",
        help="禁用 ANSI 颜色输出（同时支持 NO_COLOR 环境变量）"
    )
    parser.add_argument(
        "--dialect",
        help="数据库类型 (mysql, postgresql, sqlite, oracle)"
    )
    parser.add_argument(
        "--host",
        help="数据库主机"
    )
    parser.add_argument(
        "--port",
        type=int,
        help="数据库端口"
    )
    parser.add_argument(
        "--user",
        "-u",
        help="数据库用户名"
    )
    parser.add_argument(
        "--password",
        "-p",
        help="数据库密码"
    )
    parser.add_argument(
        "--password-file",
        help="从文件读取数据库密码（优先于 --password，适合生产环境安全传密）"
    )
    parser.add_argument(
        "--database", "-d",
        help="数据库别名（如 jump, chenzc）或数据库名。优先匹配 .env 中 DB_{别名}_* 配置"
    )
    parser.add_argument(
        "--config",
        "-c",
        help="配置文件路径"
    )
    parser.add_argument(
        "--profile",
        help="配置文件中的 profile 名称"
    )
    parser.add_argument(
        "--prefix",
        default="DB",
        help="环境变量前缀 (DB, ORACLE, MYSQL2 等)，默认 DB"
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="演示模式：使用内置 Mock 数据，无需真实数据库"
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="调试模式（显示详细错误信息）"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="详细模式（显示诊断/监控过程中的日志信息）"
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="WARNING",
        help="日志级别（默认WARNING）"
    )
    parser.add_argument(
        "--output-mode",
        choices=["rule", "raw", "ai"],
        default="rule",
        help="输出模式: rule=规则结论(默认), raw=原始数据, ai=AI友好格式"
    )

    # 追踪参数（同时注册在主解析器和子解析器上）
    _add_trace_args(parser)

    return parser


def _add_connection_args(parser: argparse.ArgumentParser) -> None:
    """
    添加数据库连接参数到解析器
    
    这些参数同时注册在主解析器和子解析器上，
    使用户可以在子命令前后灵活使用。
    
    参数:
        parser: 要添加参数的解析器
    """
    conn_group = parser.add_argument_group("数据库连接")
    conn_group.add_argument(
        "--dialect",
        help="数据库类型 (mysql, postgresql, sqlite, oracle)"
    )
    conn_group.add_argument(
        "--host",
        help="数据库主机"
    )
    conn_group.add_argument(
        "--port",
        type=int,
        help="数据库端口"
    )
    conn_group.add_argument(
        "--user", "-u",
        help="数据库用户名"
    )
    conn_group.add_argument(
        "--password", "-p",
        help="数据库密码"
    )
    conn_group.add_argument(
        "--password-file",
        help="从文件读取数据库密码"
    )
    conn_group.add_argument(
        "--database", "-d",
        help="数据库别名（如 jump, chenzc）或数据库名。优先匹配 .env 中 DB_{别名}_* 配置"
    )
    conn_group.add_argument(
        "--config", "-c",
        help="配置文件路径"
    )
    conn_group.add_argument(
        "--profile",
        help="配置文件中的 profile 名称"
    )


def _add_trace_args(parser: argparse.ArgumentParser) -> None:
    """
    添加追踪相关参数到解析器

    这些参数同时注册在主解析器和子解析器上，
    使用户可以在子命令前后灵活使用（如 diagnose slow-queries --show-trace）。

    参数:
        parser: 要添加参数的解析器
    """
    # 避免重复添加导致 argparse 冲突错误
    existing_dests = {a.dest for a in parser._actions if hasattr(a, "dest")}
    if "show_trace" in existing_dests:
        return

    trace_group = parser.add_argument_group("诊断追踪")
    trace_group.add_argument(
        "--show-trace",
        action="store_true",
        help="展示诊断/监控追踪信息（说明数据来源和检查指标）"
    )
    trace_group.add_argument(
        "--ai-depth",
        choices=["summary", "detail", "full"],
        default="detail",
        help="AI 分析深度（默认 detail）"
    )
    trace_group.add_argument(
        "--mask-sensitive",
        action="store_true",
        default=True,
        help="脱敏敏感数据（默认开启）"
    )
    trace_group.add_argument(
        "--no-mask",
        action="store_true",
        help="关闭敏感数据脱敏"
    )


# 需要合并的全局参数名（主解析器和子解析器都定义的参数）
# 这些参数在子命令前后都可以使用，但子解析器的默认值 None
# 会覆盖主解析器的实际值，需要特殊处理
_MERGEABLE_ARGS = [
    "dialect", "host", "port", "user", "password",
    "password_file", "database", "config", "profile",
    "show_trace", "ai_depth", "mask_sensitive", "no_mask",
]


def _merge_global_args(parsed_args, raw_args: Optional[List[str]]) -> None:
    """
    合并全局参数，修复子解析器覆盖问题

    当主解析器和子解析器都定义了同名参数时，argparse 的行为是：
    子解析器的值（包括默认值 None）会覆盖主解析器的值。

    例如：dbskiter --database=jump diagnose slow-queries
    主解析器解析到 database="jump"，但子解析器的 database=None 覆盖了它。

    解决方案：单独用主解析器解析一次全局参数，将非 None 的值回填。

    参数:
        parsed_args: 完整解析后的参数对象（会被原地修改）
        raw_args: 原始命令行参数列表
    """
    if not raw_args:
        return

    # 创建只含全局参数的解析器（不含子命令）
    global_parser = argparse.ArgumentParser(add_help=False)
    # 复用 _add_connection_args 和 _add_trace_args 注册参数，避免与 create_parser 重复定义
    _add_connection_args(global_parser)
    _add_trace_args(global_parser)

    # 只解析全局参数，忽略未知的子命令参数
    global_only_args, _ = global_parser.parse_known_args(raw_args)

    # 回填：如果全局解析有值但完整解析被覆盖为 None，则恢复全局值
    for arg_name in _MERGEABLE_ARGS:
        global_value = getattr(global_only_args, arg_name, None)
        current_value = getattr(parsed_args, arg_name, None)
        if global_value is not None and current_value is None:
            setattr(parsed_args, arg_name, global_value)


def _extract_trace_flags_from_raw_args(parsed_args, raw_args: list) -> None:
    """
    从原始命令行参数中提取追踪参数，修复 argparse 子命令后参数不识别的问题。

    argparse 在 dbskiter diagnose slow-queries --show-trace 时，
    会将 --show-trace 视为子命令后的未知参数并报错。
    本函数在 argparse 解析后，手动扫描 raw_args，将追踪参数回填到 parsed_args。

    参数:
        parsed_args: argparse 解析后的参数对象（会被原地修改）
        raw_args: 原始命令行参数列表
    """
    # --show-trace: flag 参数，只要存在就设为 True
    if "--show-trace" in raw_args:
        parsed_args.show_trace = True

    # --no-mask: flag 参数
    if "--no-mask" in raw_args:
        parsed_args.no_mask = True
        parsed_args.mask_sensitive = False

    # --ai-depth: 需要取下一个参数作为值
    if "--ai-depth" in raw_args:
        try:
            idx = raw_args.index("--ai-depth")
            if idx + 1 < len(raw_args) and not raw_args[idx + 1].startswith("-"):
                parsed_args.ai_depth = raw_args[idx + 1]
        except (ValueError, IndexError):
            pass


def add_subcommands(parser: argparse.ArgumentParser) -> None:
    """
    添加子命令
    
    参数:
        parser: 主解析器
    """
    subparsers = parser.add_subparsers(
        dest="command",
        help="可用命令",
        metavar="COMMAND"
    )
    
    # 为每个注册的命令添加子解析器
    for name, cmd_class in sorted(command_registry.items()):
        subparser = subparsers.add_parser(
            name,
            help=cmd_class.help_text,
            description=cmd_class.description
        )
        # 为子解析器也添加连接参数，支持子命令后使用
        _add_connection_args(subparser)
        # 为子解析器也添加追踪参数，支持 diagnose slow-queries --show-trace 的写法
        _add_trace_args(subparser)
        # 让命令类添加自己的参数（可能会创建更深层的子解析器，如 diagnose -> slow-queries）
        cmd_class.add_arguments(subparser)
        # 递归为所有子子解析器也添加追踪参数
        _add_trace_args_to_all_subparsers(subparser)


def _add_trace_args_to_all_subparsers(parser: argparse.ArgumentParser) -> None:
    """
    递归为 parser 下的所有子解析器添加追踪参数。

    某些命令（如 diagnose、monitor）使用多层子解析器：
    dbskiter diagnose slow-queries --show-trace
    这里的 --show-trace 需要被 slow-queries 子解析器识别。
    本函数遍历 parser 下的所有子解析器（包括孙解析器），为它们添加追踪参数。

    参数:
        parser: 要递归处理的解析器
    """
    if not hasattr(parser, "_subparsers") or parser._subparsers is None:
        return
    for action in parser._subparsers._group_actions:
        if isinstance(action, argparse._SubParsersAction):
            for name, subparser in action.choices.items():
                _add_trace_args(subparser)
                # 递归处理更深层的子解析器
                _add_trace_args_to_all_subparsers(subparser)
            break


def _check_has_config() -> bool:
    """
    检查是否已配置数据库

    返回说明：
        - bool: 是否有数据库配置
    """
    import os
    # 检查环境变量（排除 PATH/HOME/USER 等系统变量）
    for key in os.environ:
        if key.endswith(("_HOST", "_DIALECT")) and key not in ("PATH", "HOME", "USER"):
            return True
    # 检查 .env 文件
    env_path = Path.cwd() / ".env"
    if env_path.exists():
        return True
    return False


def _check_has_shell_completion() -> bool:
    """
    检查是否已配置 Shell Tab 补全

    检查 ~/.bashrc 或 ~/.zshrc 中是否包含 register-python-argcomplete dbskiter

    返回说明：
        - bool: 是否已配置补全
    """
    home = Path.home()
    rc_files = [home / ".bashrc", home / ".zshrc", home / ".config" / "fish" / "config.fish"]
    for rc in rc_files:
        if rc.exists() and "register-python-argcomplete dbskiter" in rc.read_text(encoding="utf-8"):
            return True
    # 检查全局补全是否激活
    try:
        import subprocess
        ret = subprocess.run(["activate-global-python-argcomplete", "--dest"], capture_output=True, text=True)
        if ret.returncode == 0:
            # 如果全局激活脚本存在，也认为已配置
            return True
    except (FileNotFoundError, subprocess.SubprocessError):
        pass
    return False


def main(args: Optional[List[str]] = None) -> int:
    """
    CLI 主入口
    
    参数:
        args: 命令行参数列表，None 表示使用 sys.argv
        
    返回:
        int: 程序退出码
        
    示例:
        >>> main(["monitor", "--database", "test"])
        0
    """
    # 创建解析器
    parser = create_parser()
    add_subcommands(parser)
    
    # 解析参数
    # 如果安装了 argcomplete，启用 Tab 补全（bash/zsh 需要额外配置）
    if HAS_ARGCOMPLETE and argcomplete:
        argcomplete.autocomplete(parser)
    parsed_args = parser.parse_args(args)

    # 修复 argparse 子解析器覆盖主解析器参数的问题
    # 当主解析器和子解析器都定义了同名参数（如 --database, --host）时，
    # 子解析器的默认值 None 会覆盖主解析器的实际值。
    # 解决方案：先解析一次只含全局参数的命令行，再与完整解析结果合并，
    # 优先取非 None 的值。
    # 注意：如果 args 为 None（命令行直接运行），需要 sys.argv 来恢复全局参数
    if args is None:
        args = sys.argv[1:]
    _merge_global_args(parsed_args, args)

    # 修复 argparse 不支持 "dbskiter diagnose slow-queries --show-trace" 的问题
    # argparse 会将子命令后的未知参数报错，但我们希望追踪参数可以在任意位置使用。
    # 解决方案：从原始参数中手动提取追踪参数并覆盖 parsed_args。
    _extract_trace_flags_from_raw_args(parsed_args, args)

    # 处理 --no-color（在创建 Console 前设置环境变量，确保全局生效）
    if getattr(parsed_args, 'no_color', False):
        os.environ["NO_COLOR"] = "1"

    # 处理 --version（手动控制，可用 Rich 美化）
    if getattr(parsed_args, 'version', False):
        console = get_console(quiet=False, json_mode=False)
        if console:
            print_minimal_banner(console, __version__)
        else:
            print(f"dbskiter {__version__}")
        return 0

    # 配置日志
    log_level_name = getattr(parsed_args, 'log_level', 'WARNING')
    if getattr(parsed_args, 'debug', False):
        log_level_name = 'DEBUG'
    elif getattr(parsed_args, 'verbose', False):
        log_level_name = 'INFO'
    logging.basicConfig(
        level=getattr(logging, log_level_name, logging.WARNING),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # 如果没有子命令，显示横幅 + 帮助
    if not parsed_args.command:
        console = get_console(
            quiet=getattr(parsed_args, 'quiet', False),
            json_mode=getattr(parsed_args, 'json', False)
        )
        if console and not getattr(parsed_args, 'quiet', False):
            print_banner(console, __version__)

        # 检测是否有数据库配置
        has_config = _check_has_config()
        if not has_config and console:
            console.print()
            console.print("[bold yellow]未检测到数据库配置[/bold yellow]")
            console.print()
            console.print("[bold]快速开始：[/bold]")
            console.print("  1. [cyan]dbskiter init[/cyan]         - 交互式配置向导")
            console.print("  2. [cyan]dbskiter --demo monitor[/cyan] - 演示模式（无需数据库）")
            console.print("  3. [cyan]dbskiter init --quick[/cyan]   - 生成配置模板")
            console.print()
            console.print("[dim]提示：编辑 .env 文件配置你的数据库连接信息[/dim]")
            console.print()

        # 检测是否已配置 Shell Tab 补全
        if not _check_has_shell_completion() and console:
            console.print("[bold green]Tab 补全提示：[/bold green]")
            console.print("  运行 [cyan]dbskiter shell-setup --auto[/cyan] 可一键启用 Tab 补全")
            console.print("  启用后按 Tab 键可自动补全命令和参数")
            console.print()

        parser.print_help()
        return 0
    
    # 创建输出格式化器
    output = OutputFormatter(
        json_mode=parsed_args.json,
        quiet=parsed_args.quiet
    )
    
    # 不需要数据库连接的命令列表
    NO_DB_COMMANDS = {"history", "shell-setup", "init"}
    demo_mode = getattr(parsed_args, 'demo', False)
    needs_db = parsed_args.command not in NO_DB_COMMANDS and not demo_mode

    try:
        # 加载配置（支持配置文件、别名、环境变量、命令行参数的优先级覆盖）
        # 对于不需要数据库的命令（history, shell-setup, init），跳过强制配置验证
        if needs_db:
            config = Config.from_args(parsed_args)
            config.validate()
        else:
            # 构造一个空配置，避免后续代码报错（history 等命令不需要数据库连接）
            config = Config()
        
        # 获取命令类
        cmd_class = command_registry.get(parsed_args.command)
        if not cmd_class:
            output.error(f"未知命令: {parsed_args.command}")
            return 1
        
        # 创建并执行命令（自动计时 + 历史记录）
        from ..shared import ExecutionTimer

        command = cmd_class(config, output, parsed_args)
        timer = ExecutionTimer().start()
        status_code = command.run()
        total_ms = timer.stop()

        # 提取 action（子命令）
        action = getattr(parsed_args, 'action', '') or getattr(parsed_args, 'subcommand', '')

        # 记录历史（rerun 复用时不记录，避免循环）
        if not os.environ.get("_DBSKITER_SKIP_HISTORY"):
            history = HistoryManager()
            history.record(
                args=parsed_args,
                command=parsed_args.command,
                action=action,
                database=getattr(parsed_args, 'database', '') or '',
                status_code=status_code,
                execution_time_ms=total_ms,
            )
        else:
            # 清除标志，避免影响后续正常命令
            os.environ.pop("_DBSKITER_SKIP_HISTORY", None)

        return status_code

    except Exception as e:
        # 使用统一的错误处理器
        handler = ErrorHandler(debug=getattr(parsed_args, 'debug', False))
        return handler.handle_error(e, output)


if __name__ == "__main__":
    sys.exit(main())
