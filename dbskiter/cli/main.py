"""
cli/main.py

CLI 主入口

负责：
- 参数解析
- 命令分发
- 全局错误处理
"""

import sys
import argparse
from typing import List, Optional

from .config import Config, MultiDBConfig
from .output import OutputFormatter
from .exceptions import CLIError, ConfigError
from .commands import command_registry, BaseCommand
from .error_handler import ErrorHandler


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
使用示例:
  dbskiter monitor --database=jump
  dbskiter diagnose --database=jump --sql="SELECT * FROM users"
  dbskiter security --database=jump
  dbskiter scheduler backup --type=full
  dbskiter sql "SELECT * FROM users LIMIT 10"
  python -m dbskiter monitor  # 使用模块方式运行

环境变量:
  DB_DIALECT, DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME

更多信息:
  dbskiter <command> --help
        """
    )
    
    # 全局参数
    parser.add_argument(
        "--version",
        action="version",
        version="%(prog)s 2.0.0"
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
        "--database",
        "-d",
        help="数据库名称"
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
        "--debug",
        action="store_true",
        help="调试模式（显示详细错误信息）"
    )
    parser.add_argument(
        "--output-mode",
        choices=["rule", "raw", "ai"],
        default="rule",
        help="输出模式: rule=规则结论(默认), raw=原始数据, ai=AI友好格式"
    )
    parser.add_argument(
        "--ai-depth",
        choices=["summary", "detail", "full"],
        default="detail",
        help="AI输出详细程度: summary=摘要, detail=详细(默认), full=完整"
    )
    parser.add_argument(
        "--mask-sensitive",
        action="store_true",
        default=True,
        help="脱敏敏感信息（默认开启）"
    )
    parser.add_argument(
        "--no-mask",
        action="store_true",
        help="不脱敏敏感信息（仅限安全环境）"
    )
    
    return parser


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
        # 让命令类添加自己的参数
        cmd_class.add_arguments(subparser)


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
    parsed_args = parser.parse_args(args)
    
    # 如果没有子命令，显示帮助
    if not parsed_args.command:
        parser.print_help()
        return 0
    
    # 创建输出格式化器
    output = OutputFormatter(
        json_mode=parsed_args.json,
        quiet=parsed_args.quiet
    )
    
    try:
        # 加载配置（支持别名选择数据库）
        database_alias = getattr(parsed_args, 'database', None)

        # 如果指定了数据库别名，尝试通过 MultiDBConfig 查找对应配置
        if database_alias:
            multi_config = MultiDBConfig()
            # 首先尝试作为别名查找
            config = multi_config.get_config_by_alias(database_alias.lower())
            if config:
                config.prefix = f"DB_{database_alias.upper()}"
            else:
                # 向后兼容：尝试通过数据库名查找
                config = multi_config.find_config_by_database(database_alias)
                if config:
                    alias = multi_config.get_alias_by_database(database_alias)
                    config.prefix = f"DB_{alias.upper()}" if alias else "DB"
                else:
                    # 如果没找到，使用默认配置
                    config = Config.from_env(prefix="DB")
                    config.prefix = "DB"
                    config.database = database_alias
        else:
            # 使用默认配置
            config = Config.from_env(prefix="DB")
            config.prefix = "DB"

        # 用命令行参数覆盖（优先级最高）
        # 注意：--database参数用于指定数据库别名/配置，不是直接设置数据库名
        # 数据库名应该从配置中读取，只有在明确指定--database作为连接参数时才覆盖
        if hasattr(parsed_args, "dialect") and parsed_args.dialect:
            config.dialect = parsed_args.dialect
        if hasattr(parsed_args, "host") and parsed_args.host:
            config.host = parsed_args.host
        if hasattr(parsed_args, "port") and parsed_args.port:
            config.port = parsed_args.port
        if hasattr(parsed_args, "user") and parsed_args.user:
            config.username = parsed_args.user
        if hasattr(parsed_args, "password") and parsed_args.password:
            config.password = parsed_args.password
        # 只有在没有通过别名找到配置时，才将--database作为数据库名使用
        if hasattr(parsed_args, "database") and parsed_args.database:
            multi_config = MultiDBConfig()
            if not multi_config.get_config_by_alias(parsed_args.database.lower()):
                # 没有找到对应别名配置，才将参数作为数据库名
                config.database = parsed_args.database
        
        config.validate()
        
        # 获取命令类
        cmd_class = command_registry.get(parsed_args.command)
        if not cmd_class:
            output.error(f"未知命令: {parsed_args.command}")
            return 1
        
        # 创建并执行命令
        command = cmd_class(config, output, parsed_args)
        return command.run()
        
    except Exception as e:
        # 使用统一的错误处理器
        handler = ErrorHandler(debug=getattr(parsed_args, 'debug', False))
        return handler.handle_error(e, output)


if __name__ == "__main__":
    sys.exit(main())
