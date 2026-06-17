"""
cli/commands/config_cmd.py

配置管理命令

负责：
- 展示当前配置溯源（config describe）
- 验证配置有效性（config validate）
"""

from argparse import ArgumentParser
from typing import Dict, Any

from .base import BaseCommand
from ..config import Config
from ..exceptions import ValidationError


class ConfigCommand(BaseCommand):
    """
    配置管理命令

    提供配置查看、验证、溯源等功能
    """

    name = "config"
    description = "配置管理：查看、验证、溯源当前数据库配置"
    help_text = "管理数据库配置"

    @classmethod
    def add_arguments(cls, parser: ArgumentParser) -> None:
        """添加命令参数"""
        subparsers = parser.add_subparsers(dest="config_action", help="配置子命令")

        # describe 子命令
        describe_parser = subparsers.add_parser(
            "describe",
            help="展示当前配置的完整溯源信息",
            description="显示每个配置字段的来源（CLI参数/配置文件/.env/环境变量/默认值）"
        )
        describe_parser.add_argument(
            "--show-password", action="store_true",
            help="显示密码（默认隐藏）"
        )

        # validate 子命令
        validate_parser = subparsers.add_parser(
            "validate",
            help="验证当前配置是否有效",
            description="检查配置是否能成功连接到数据库"
        )

        # list 子命令
        list_parser = subparsers.add_parser(
            "list",
            help="列出所有可用的数据库别名",
            description="显示配置文件和 .env 中定义的数据库别名"
        )

        # show-alias 子命令
        show_parser = subparsers.add_parser(
            "show-alias",
            help="展示指定别名的详细配置",
            description="显示某个数据库别名的完整配置信息"
        )
        show_parser.add_argument(
            "alias",
            help="数据库别名"
        )
        show_parser.add_argument(
            "--show-password", action="store_true",
            help="显示密码（默认隐藏）"
        )

    def execute(self) -> int:
        """执行配置命令"""
        action = getattr(self.args, "config_action", None)

        if action == "describe":
            return self._describe_config()
        elif action == "validate":
            return self._validate_config()
        elif action == "list":
            return self._list_aliases()
        elif action == "show-alias":
            return self._show_alias()
        else:
            self.output.error("请指定子命令: describe, validate, list, show-alias")
            self.output.print("\n示例:")
            self.output.print("  dbskiter config describe        # 查看配置溯源")
            self.output.print("  dbskiter config validate        # 验证配置有效性")
            self.output.print("  dbskiter config list            # 列出所有别名")
            self.output.print("  dbskiter config show-alias jump # 查看 jump 别名配置")
            return 1

    def _describe_config(self) -> int:
        """展示配置溯源信息"""
        try:
            config = Config.from_args(self.args)
        except Exception as e:
            self.output.error(f"加载配置失败: {e}")
            return 1

        show_password = getattr(self.args, "show_password", False)

        # 构建展示数据
        fields = [
            ("dialect", "数据库方言", config.dialect),
            ("host", "主机地址", config.host),
            ("port", "端口", str(config.port)),
            ("username", "用户名", config.username),
            ("password", "密码", config.password if show_password else "***"),
            ("database", "数据库名", config.database),
        ]

        self.output.rich_print("\n[bold cyan][配置溯源][/bold cyan]")
        self.output.print("─" * 60)

        for field_key, field_name, value in fields:
            source = config.source_map.get(field_key, "unknown")
            source_display = self._format_source(source)
            self.output.rich_print(
                f"  {field_name:12s}: {value:20s}  ← {source_display}"
            )

        self.output.print("─" * 60)

        # 额外信息
        if config.extra:
            self.output.rich_print("\n[bold cyan][额外配置][/bold cyan]")
            for key, value in config.extra.items():
                self.output.print(f"  {key}: {value}")

        # 配置优先级说明
        self.output.rich_print("\n[bold cyan][优先级规则][/bold cyan]")
        self.output.print("  1. CLI 参数（--host, --user 等）")
        self.output.print("  2. 配置文件（--config 指定）")
        self.output.print("  3. .env 文件（当前目录）")
        self.output.print("  4. 环境变量（DB_HOST 等）")
        self.output.print("  5. 内置默认值")

        return 0

    def _validate_config(self) -> int:
        """验证配置有效性"""
        try:
            config = Config.from_args(self.args)
            config.validate()
        except ValidationError as e:
            self.output.error(f"配置验证失败: {e}")
            return 1
        except Exception as e:
            self.output.error(f"加载配置失败: {e}")
            return 1

        self.output.success("配置验证通过")
        self.output.print(f"\n  方言: {config.dialect}")
        self.output.print(f"  主机: {config.host}:{config.port}")
        self.output.print(f"  数据库: {config.database}")
        self.output.print(f"  用户: {config.username}")

        # 尝试连接测试（可选）
        self.output.rich_print("\n  [dim]尝试连接数据库...[/dim]")
        try:
            connector = self.connector
            if connector:
                self.output.success("  数据库连接成功")
            else:
                self.output.warning("  连接器初始化失败")
        except Exception as e:
            self.output.error(f"  连接失败: {e}")
            return 1

        return 0

    @staticmethod
    def _format_source(source: str) -> str:
        """格式化来源显示"""
        source_map = {
            "cli": "[green]CLI 参数[/green]",
            "config_file": "[blue]配置文件[/blue]",
            ".env": "[yellow].env 文件[/yellow]",
            "env": "[yellow]环境变量[/yellow]",
            "default": "[dim]默认值[/dim]",
        }
        if source.startswith("alias:"):
            alias = source.split(":", 1)[1]
            return f"[magenta]别名 ({alias})[/magenta]"
        if source.startswith("yaml_alias:"):
            alias = source.split(":", 1)[1]
            return f"[magenta]YAML 别名 ({alias})[/magenta]"
        if source.startswith("password_file:"):
            path = source.split(":", 1)[1]
            return f"[cyan]密码文件 ({path})[/cyan]"
        if source == "cli(--database)":
            return "[green]--database 参数[/green]"
        return source_map.get(source, f"[dim]{source}[/dim]")

    def _list_aliases(self) -> int:
        """列出所有可用的数据库别名"""
        # 从 .env 获取别名
        from ..config import MultiDBConfig
        multi_config = MultiDBConfig()
        env_aliases = multi_config.list_aliases()

        # 从 YAML 配置文件获取别名
        yaml_aliases = []
        try:
            from ..config_file import ConfigFileManager
            manager = ConfigFileManager()
            yaml_aliases = manager.list_databases()
        except Exception:
            pass

        self.output.rich_print("\n[bold cyan][数据库别名列表][/bold cyan]")
        self.output.print("─" * 50)

        if env_aliases:
            self.output.print("\n  .env 环境变量别名:")
            for alias in env_aliases:
                self.output.print(f"    • {alias}")

        if yaml_aliases:
            self.output.print("\n  配置文件别名:")
            for alias in yaml_aliases:
                self.output.print(f"    • {alias}")

        if not env_aliases and not yaml_aliases:
            self.output.print("  未找到任何别名配置")
            self.output.print("\n  提示:")
            self.output.print("    在 .env 中定义: DB_JUMP_HOST=192.168.1.1")
            self.output.print("    在 dbskiter.yaml 中定义:")
            self.output.print("      databases:")
            self.output.print("        - name: jump")
            self.output.print("          host: 192.168.1.1")

        self.output.print("─" * 50)
        return 0

    def _show_alias(self) -> int:
        """展示指定别名的详细配置"""
        alias = getattr(self.args, "alias", None)
        if not alias:
            self.output.error("请指定别名")
            return 1

        alias_lower = alias.lower()

        # 尝试从 .env 获取
        from ..config import MultiDBConfig
        multi_config = MultiDBConfig()
        env_config = multi_config.get_config_by_alias(alias_lower)

        # 尝试从 YAML 获取
        yaml_config = None
        try:
            from ..config_file import ConfigFileManager
            manager = ConfigFileManager()
            yaml_config = manager.get_database_config(alias_lower)
        except Exception:
            pass

        if not env_config and not yaml_config:
            self.output.error(f"未找到别名 '{alias}' 的配置")
            return 1

        show_password = getattr(self.args, "show_password", False)

        self.output.rich_print(f"\n[bold cyan][别名配置: {alias}][/bold cyan]")
        self.output.print("─" * 50)

        if env_config:
            self.output.print("\n  来源: .env 环境变量")
            self.output.print(f"    方言: {env_config.dialect}")
            self.output.print(f"    主机: {env_config.host}:{env_config.port}")
            self.output.print(f"    数据库: {env_config.database}")
            self.output.print(f"    用户名: {env_config.username}")
            password = env_config.password if show_password else "***"
            self.output.print(f"    密码: {password}")

        if yaml_config:
            self.output.print("\n  来源: 配置文件")
            self.output.print(f"    方言: {yaml_config.dialect}")
            self.output.print(f"    主机: {yaml_config.host}:{yaml_config.port}")
            self.output.print(f"    数据库: {yaml_config.database}")
            self.output.print(f"    用户名: {yaml_config.username}")
            password = yaml_config.password if show_password else "***"
            self.output.print(f"    密码: {password}")

        self.output.print("─" * 50)
        return 0
