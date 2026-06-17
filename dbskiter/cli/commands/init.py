"""
cli/commands/init.py

交互式配置向导命令（增强版）

功能：
    - 引导新手完成数据库配置
    - 生成 .env 或 YAML 配置文件
    - 支持一次性配置多数据库
    - 测试连接

使用示例：
    dbskiter init              # 交互式配置向导
    dbskiter init --quick      # 快速模式，只生成 .env 模板
    dbskiter init --demo       # 生成带 mock 数据的演示配置
    dbskiter init --format yaml # 生成 YAML 格式配置
    dbskiter init add          # 添加新数据库别名到现有配置
    dbskiter init list         # 列出已配置的数据库
"""

from __future__ import annotations

import os
import re
from argparse import ArgumentParser
from pathlib import Path
from typing import Dict, Any, Optional, List

from .base import BaseCommand
from dbskiter.cli.exceptions import ConfigError


class InitCommand(BaseCommand):
    """
    交互式配置向导命令（增强版）

    功能描述：
        引导用户完成数据库环境配置，支持 .env 和 YAML 格式
        支持多数据库别名配置，适合开发、测试、生产环境

    使用示例：
        >>> dbskiter init
        >>> dbskiter init --quick
        >>> dbskiter init --demo
        >>> dbskiter init --format yaml
        >>> dbskiter init add        # 添加新数据库
        >>> dbskiter init list       # 列出已配置的数据库
    """

    name = "init"
    description = "交互式配置向导 - 帮助新手快速配置数据库连接"
    help_text = "生成 .env / YAML 配置文件，支持多数据库别名"

    # 预设的数据库模板
    DB_TEMPLATES: Dict[str, Dict[str, Any]] = {
        "mysql": {
            "dialect": "mysql+pymysql",
            "port": 3306,
            "user": "root",
        },
        "postgresql": {
            "dialect": "postgresql+psycopg2",
            "port": 5432,
            "user": "postgres",
        },
        "oracle": {
            "dialect": "oracle+jdbc",
            "port": 1521,
            "user": "system",
            "extra": ["service", "jdbc_driver"],
        },
        "mssql": {
            "dialect": "mssql+pyodbc",
            "port": 1433,
            "user": "sa",
        },
        "clickhouse": {
            "dialect": "clickhouse+http",
            "port": 8123,
            "user": "default",
        },
        "sqlite": {
            "dialect": "sqlite+pysqlite",
            "port": 0,
            "user": "",
            "host_hint": "数据库文件路径，如 ./demo.db",
        },
    }

    @classmethod
    def add_arguments(cls, parser: ArgumentParser) -> None:
        """
        添加 init 命令参数

        支持子命令：add, list
        支持全局参数：--quick, --demo, --format, --output, --force
        """
        subparsers = parser.add_subparsers(
            dest="init_action",
            help="init 子命令",
            metavar="ACTION"
        )

        # ====== add 子命令：添加新数据库 ======
        add_parser = subparsers.add_parser(
            "add",
            help="添加新数据库别名到现有配置"
        )
        add_parser.add_argument(
            "--format",
            choices=["env", "yaml"],
            default="env",
            help="配置格式（默认 env）"
        )
        add_parser.add_argument(
            "--output",
            "-o",
            default=".env",
            help="输出文件路径（默认 .env）"
        )

        # ====== list 子命令：列出已配置数据库 ======
        list_parser = subparsers.add_parser(
            "list",
            help="列出已配置的数据库别名"
        )
        list_parser.add_argument(
            "--format",
            choices=["env", "yaml"],
            default="env",
            help="配置格式（默认 env）"
        )
        list_parser.add_argument(
            "--output",
            "-o",
            default=".env",
            help="配置文件路径（默认 .env）"
        )

        # ====== 全局参数 ======
        parser.epilog = """
示例:
  dbskiter init                           # 交互式配置向导
  dbskiter init --quick                   # 快速生成 .env 模板
  dbskiter init --demo                    # 生成演示配置（Mock数据）
  dbskiter init --format yaml --output dbskiter.yaml  # 生成 YAML 格式
  dbskiter init add                       # 添加新数据库别名
  dbskiter init list                      # 列出已配置的数据库
        """
        parser.add_argument(
            "--quick",
            action="store_true",
            help="快速模式：只生成配置模板，不交互"
        )
        parser.add_argument(
            "--demo",
            action="store_true",
            help="演示模式：生成带 mock 数据的配置"
        )
        parser.add_argument(
            "--format",
            choices=["env", "yaml"],
            default="env",
            help="配置格式（默认 env，支持 yaml）"
        )
        parser.add_argument(
            "--output",
            "-o",
            default=".env",
            help="输出文件路径（默认 .env）"
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="强制覆盖已存在的配置文件"
        )

    def execute(self) -> int:
        """
        执行配置向导

        根据 init_action 分发到不同子命令处理。
        """
        output = self.output
        args = self.args
        action = getattr(args, "init_action", None)

        # 子命令分发
        if action == "add":
            return self._run_add_mode()
        elif action == "list":
            return self._run_list_mode()

        # 无子命令：处理 --demo, --quick, 或默认交互式
        if getattr(args, "demo", False):
            return self._run_demo_mode()

        if getattr(args, "quick", False):
            return self._run_quick_mode()

        return self._run_interactive_mode()

    # ======== 子命令：add ========
    def _run_add_mode(self) -> int:
        """
        add 子命令：交互式添加新数据库别名到现有配置

        返回说明：
            - int: 退出码，0 表示成功
        """
        output = self.output
        args = self.args
        fmt = getattr(args, "format", "env")
        output_path = Path(getattr(args, "output", ".env"))

        output.print("")
        output.print("=" * 60)
        output.print("  DBSKiter 添加新数据库配置")
        output.print("=" * 60)
        output.print("")

        # 对于 YAML 格式，确定正确的配置文件路径
        if fmt == "yaml":
            if output_path.name == ".env" or not output_path.exists():
                for fallback in [Path("dbskiter.yaml"), Path("dbskiter.yml")]:
                    if fallback.exists():
                        output_path = fallback
                        break

        # 为别名设置输入一个有意义的名字
        alias = input("  数据库别名（如 jump, prod, dev）：").strip()
        if not alias:
            output.error("别名不能为空，已取消")
            return 1
        # 清理别名（只允许字母数字下划线）
        alias = re.sub(r'[^a-zA-Z0-9_]', '_', alias)
        prefix = f"DB_{alias.upper()}"

        # 选择数据库类型
        db_type = self._choose_database_type()
        if not db_type:
            output.error("未选择数据库类型，已取消")
            return 1

        template = self.DB_TEMPLATES[db_type]

        # 收集连接信息
        config = self._collect_connection_info(db_type, template)
        if not config:
            output.error("配置信息不完整，已取消")
            return 1

        # 生成并追加配置
        new_config = self._generate_env_content(prefix, config)

        if fmt == "yaml":
            new_config = self._generate_yaml_content(alias, config)
            # YAML 需要读取现有文件，在 databases 列表追加
            existing = self._read_existing_yaml(output_path)
            existing["databases"].append(new_config)
            self._write_yaml(output_path, existing)
        else:
            # .env 模式：直接追加
            if output_path.exists():
                existing = output_path.read_text(encoding="utf-8")
                # 检查是否已存在该别名
                if f"{prefix}_HOST=" in existing:
                    output.warning(f"别名 '{alias}' 已存在于配置中")
                    if not self._confirm("是否覆盖现有配置?"):
                        output.info("已取消")
                        return 0
                # 移除旧配置块
                existing = self._remove_alias_from_env(existing, prefix)
                new_config = existing.rstrip() + "\n\n" + new_config
            output_path.write_text(new_config, encoding="utf-8")

        output.success(f"配置已追加到: {output_path.absolute()}")
        output.print("")
        output.info(f"快速开始：")
        output.print(f"  dbskiter --database={alias} monitor health")
        output.print(f"  dbskiter --database={alias} diagnose top")
        return 0

    # ======== 子命令：list ========
    def _run_list_mode(self) -> int:
        """
        list 子命令：列出已配置的数据库别名

        返回说明：
            - int: 退出码，0 表示成功
        """
        output = self.output
        args = self.args
        fmt = getattr(args, "format", "env")
        output_path = Path(getattr(args, "output", ".env"))

        output.print("")
        output.print("=" * 60)
        output.print("  DBSKiter 已配置数据库列表")
        output.print("=" * 60)
        output.print("")

        # 对于 YAML 格式，确定正确的配置文件路径
        # 如果用户指定了 --output，使用指定路径；否则默认查找 dbskiter.yaml
        if fmt == "yaml":
            if output_path.name == ".env" or not output_path.exists():
                for fallback in [Path("dbskiter.yaml"), Path("dbskiter.yml")]:
                    if fallback.exists():
                        output_path = fallback
                        break

        if not output_path.exists():
            output.warning(f"配置文件不存在: {output_path}")
            output.print("提示：运行 `dbskiter init` 创建配置")
            return 0

        if fmt == "yaml":
            data = self._read_existing_yaml(output_path)
            databases = data.get("databases", [])
            if not databases:
                output.info("未配置任何数据库")
                return 0
            for db in databases:
                output.print(f"  - {db['name']} ({db.get('driver', '?')})")
                output.print(f"    host: {db.get('host', 'localhost')}")
                output.print(f"    db:   {db.get('db', 'unknown')}")
        else:
            # .env 模式：用正则扫描 DB_{ALIAS}_HOST 模式
            content = output_path.read_text(encoding="utf-8")
            aliases = self._scan_env_aliases(content)
            if not aliases:
                output.info("未配置任何数据库别名")
                return 0
            for alias in aliases:
                prefix = f"DB_{alias.upper()}"
                host = self._extract_env_value(content, f"{prefix}_HOST")
                db_name = self._extract_env_value(content, f"{prefix}_NAME")
                output.print(f"  {alias}")
                output.print(f"    host: {host or '?'}")
                output.print(f"    db:   {db_name or '?'}")
                output.print("")

        return 0

    # ======== 原有模式：demo, quick, interactive ========
    def _run_demo_mode(self) -> int:
        """演示模式：生成带 mock 数据的配置"""
        output = self.output
        args = self.args
        fmt = getattr(args, "format", "env")
        output_path = Path(getattr(args, "output", ".env"))

        if fmt == "yaml":
            # YAML 默认输出为 dbskiter.yaml
            if output_path.name == ".env" or output_path.name == ".env.yaml":
                output_path = Path("dbskiter.yaml")
            data = {
                "databases": [
                    {
                        "name": "demo",
                        "driver": "mock",
                        "host": "demo",
                        "port": 0,
                        "user": "demo",
                        "password": "demo",
                        "db": "demo"
                    }
                ]
            }
            self._write_yaml(output_path, data)
        else:
            output_path = output_path.with_suffix(".env")
            env_content = self._generate_demo_env()
            output_path.write_text(env_content, encoding="utf-8")

        output.success(f"演示配置已保存到: {output_path.absolute()}")
        output.print("")
        output.info("使用方法：")
        output.print("  dbskiter --demo monitor health")
        output.print("  dbskiter --demo sql execute \"SELECT * FROM users LIMIT 10\"")
        output.print("  dbskiter --demo diagnose top")
        return 0

    def _run_quick_mode(self) -> int:
        """快速模式：生成配置模板"""
        output = self.output
        args = self.args
        fmt = getattr(args, "format", "env")
        output_path = Path(getattr(args, "output", ".env"))

        if fmt == "yaml":
            # YAML 默认输出为 dbskiter.yaml
            if output_path.name == ".env" or output_path.name == ".env.yaml":
                output_path = Path("dbskiter.yaml")
            data = self._create_yaml_template()
            self._write_yaml(output_path, data)
        else:
            output_path = output_path.with_suffix(".env")
            env_content = self._generate_template_env()
            output_path.write_text(env_content, encoding="utf-8")

        output.success(f"配置模板已保存到: {output_path.absolute()}")
        output.print("")
        output.info("下一步：")
        output.print(f"  1. 编辑 {output_path.name} 文件，填入你的数据库连接信息")
        output.print("  2. 运行 dbskiter --help 查看可用命令")
        output.print("  3. 运行 dbskiter monitor 开始监控")
        return 0

    def _run_interactive_mode(self) -> int:
        """交互式配置向导（支持多数据库）"""
        output = self.output
        args = self.args
        fmt = getattr(args, "format", "env")
        output_path = Path(getattr(args, "output", ".env"))

        if fmt == "yaml":
            # YAML 默认输出为 dbskiter.yaml
            if output_path.name == ".env" or output_path.name == ".env.yaml":
                output_path = Path("dbskiter.yaml")

        output.print("")
        output.print("=" * 60)
        output.print(f"  DBSKiter 数据库配置向导 ({fmt.upper()} 格式)")
        output.print("=" * 60)
        output.print("")

        all_configs: List[Dict[str, Any]] = []
        first_db = True

        while True:
            if not first_db:
                output.print("")
                if not self._confirm("是否继续添加更多数据库?"):
                    break

            # 步骤1：选择数据库类型
            db_type = self._choose_database_type()
            if not db_type:
                if first_db:
                    output.error("未选择数据库类型，已取消")
                    return 1
                break

            template = self.DB_TEMPLATES[db_type]

            # 步骤2：为别名命名
            if first_db:
                output.print("")
                output.print("第一个数据库将作为默认配置（无前缀）")
                alias = "default"
                prefix = "DB"
            else:
                alias = input("  数据库别名（如 jump, prod, test）：").strip()
                if not alias:
                    alias = f"db_{len(all_configs) + 1}"
                alias = re.sub(r'[^a-zA-Z0-9_]', '_', alias)
                prefix = f"DB_{alias.upper()}"

            # 步骤3：收集连接信息
            config = self._collect_connection_info(db_type, template)
            if not config:
                if first_db:
                    output.error("配置信息不完整，已取消")
                    return 1
                break

            all_configs.append({
                "alias": alias,
                "prefix": prefix,
                "config": config,
                "db_type": db_type,
            })
            first_db = False

        if not all_configs:
            output.error("没有配置任何数据库，已取消")
            return 1

        # 步骤4：生成并保存配置
        if fmt == "yaml":
            yaml_data = self._configs_to_yaml(all_configs)
            if output_path.exists():
                output.warning(f"文件 {output_path} 已存在")
                if not self._confirm("是否覆盖?"):
                    output.info("已取消")
                    return 0
            self._write_yaml(output_path, yaml_data)
        else:
            env_lines = []
            for item in all_configs:
                env_lines.append(self._generate_env_content(item["prefix"], item["config"]))
            env_content = "\n".join(env_lines)

            if output_path.exists():
                output.warning(f"文件 {output_path} 已存在")
                if not self._confirm("是否覆盖?"):
                    output.info("已取消，你的配置如下：")
                    output.print("")
                    output.print(env_content)
                    return 0

            output_path.write_text(env_content, encoding="utf-8")

        output.success(f"配置已保存到: {output_path.absolute()}")
        output.print("")
        output.info("配置预览：")
        for item in all_configs:
            alias = item["alias"]
            prefix = item["prefix"]
            cfg = item["config"]
            output.print(f"  [{alias}] {cfg['dialect']}")
            output.print(f"    host: {cfg['host']}")
            output.print(f"    db:   {cfg['database']}")
            output.print("")

        output.info("快速开始：")
        for item in all_configs:
            alias = item["alias"]
            if alias == "default":
                output.print(f"  dbskiter monitor health")
            else:
                output.print(f"  dbskiter --database={alias} monitor health")
        output.print("")
        output.info("提示：")
        output.print("  - 使用 `dbskiter init add` 添加更多数据库")
        output.print("  - 使用 `dbskiter init list` 查看已配置的数据库")

        return 0

    # ======== 核心工具方法 ========
    def _choose_database_type(self) -> Optional[str]:
        """选择数据库类型"""
        output = self.output
        output.print("请选择数据库类型：")
        output.print("")
        types = list(self.DB_TEMPLATES.keys())
        for i, db_type in enumerate(types, 1):
            template = self.DB_TEMPLATES[db_type]
            output.print(f"  {i}. {db_type.upper():12s} (默认端口: {template['port']})")
        output.print("")
        raw_choice = input("请输入序号 (1-6): ").strip()
        choice = re.sub(r'[^0-9]', '', raw_choice)
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(types):
                return types[idx]
        except ValueError:
            pass
        return None

    def _collect_connection_info(
        self, db_type: str, template: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """收集连接信息"""
        output = self.output
        config: Dict[str, Any] = {"dialect": template["dialect"]}

        output.print("")
        output.print(f"--- {db_type.upper()} 连接配置 ---")
        output.print("")

        host_hint = template.get("host_hint", "数据库主机地址")
        host = input(f"  主机地址 [{host_hint}]: ").strip()
        if not host and db_type != "sqlite":
            host = "localhost"
        config["host"] = host

        if db_type != "sqlite":
            port = input(f"  端口 [{template['port']}]: ").strip()
            config["port"] = int(port) if port else template["port"]
        else:
            config["port"] = template["port"]

        user = input(f"  用户名 [{template['user']}]: ").strip()
        config["user"] = user if user else template["user"]

        password = input("  密码: ").strip()
        config["password"] = password

        if db_type == "oracle":
            service = input("  Service Name [ORCL]: ").strip()
            config["database"] = service if service else "ORCL"
            jdbc_driver = input("  JDBC 驱动路径 [ojdbc8.jar]: ").strip()
            config["jdbc_driver"] = jdbc_driver if jdbc_driver else "ojdbc8.jar"
        elif db_type == "sqlite":
            config["database"] = config["host"]
        else:
            db_name = input("  数据库名 [test]: ").strip()
            config["database"] = db_name if db_name else "test"

        return config

    def _generate_env_content(self, prefix: str, config: Dict[str, Any]) -> str:
        """生成 .env 文件内容片段"""
        lines = [
            f"# {prefix} 数据库配置",
            f"{prefix}_DIALECT={config['dialect']}",
            f"{prefix}_HOST={config['host']}",
            f"{prefix}_PORT={config['port']}",
            f"{prefix}_USER={config['user']}",
            f"{prefix}_PASSWORD={config['password']}",
            f"{prefix}_NAME={config['database']}",
        ]
        if "jdbc_driver" in config:
            lines.append(f"{prefix}_JDBC_DRIVER={config['jdbc_driver']}")
        lines.extend([
            "",
        ])
        return "\n".join(lines)

    def _generate_yaml_content(self, name: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """生成 YAML 配置字典"""
        return {
            "name": name,
            "driver": config["dialect"],
            "host": config["host"],
            "port": config["port"],
            "user": config["user"],
            "password": config["password"],
            "db": config["database"],
        }

    def _configs_to_yaml(self, all_configs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """将多配置转换为完整 YAML 数据"""
        databases = []
        for item in all_configs:
            databases.append(self._generate_yaml_content(item["alias"], item["config"]))
        return {
            "databases": databases,
            "settings": {
                "default_database": all_configs[0]["alias"] if all_configs else None,
                "default_output_format": "table",
            }
        }

    def _create_yaml_template(self) -> Dict[str, Any]:
        """创建 YAML 模板"""
        return {
            "databases": [
                {
                    "name": "default",
                    "driver": "mysql+pymysql",
                    "host": "localhost",
                    "port": 3306,
                    "user": "root",
                    "password": "${DB_PASSWORD}",
                    "db": "your_database"
                }
            ],
            "settings": {
                "default_database": "default",
                "default_output_format": "table",
            }
        }

    def _write_yaml(self, path: Path, data: Dict[str, Any]) -> None:
        """写入 YAML 文件"""
        try:
            import yaml
            path.parent.mkdir(parents=True, exist_ok=True)
            yaml_content = yaml.dump(
                data,
                default_flow_style=False,
                allow_unicode=True,
                sort_keys=False,
            )
            path.write_text(yaml_content, encoding="utf-8")
        except ImportError:
            self.output.error("需要 PyYAML 才能生成 YAML 配置: pip install pyyaml")
            raise ConfigError("缺少 PyYAML 依赖")

    def _read_existing_yaml(self, path: Path) -> Dict[str, Any]:
        """读取现有 YAML 配置"""
        if not path.exists():
            return {"databases": []}
        try:
            import yaml
            content = path.read_text(encoding="utf-8")
            data = yaml.safe_load(content) or {"databases": []}
            if "databases" not in data:
                data["databases"] = []
            return data
        except ImportError:
            self.output.error("需要 PyYAML 才能读取 YAML 配置: pip install pyyaml")
            return {"databases": []}
        except Exception:
            return {"databases": []}

    def _scan_env_aliases(self, content: str) -> List[str]:
        """扫描 .env 内容中的 DB_{ALIAS}_HOST 模式，返回别名列表"""
        aliases = set()
        for line in content.splitlines():
            match = re.match(r'^DB_([A-Z0-9_]+)_HOST=', line)
            if match:
                alias = match.group(1).lower()
                if alias != '':  # 排除 DB_HOST 本身
                    aliases.add(alias)
        return sorted(aliases)

    def _extract_env_value(self, content: str, key: str) -> Optional[str]:
        """从 .env 内容中提取指定 key 的值"""
        for line in content.splitlines():
            if line.startswith(f"{key}="):
                return line[len(f"{key}="):].strip()
        return None

    def _remove_alias_from_env(self, content: str, prefix: str) -> str:
        """从 .env 内容中移除指定 prefix 的配置块"""
        lines = content.splitlines()
        result = []
        skip = False
        for line in lines:
            if line.startswith(f"# {prefix} ") or line.startswith(f"{prefix}_"):
                skip = True
                continue
            if skip and line.startswith("#"):
                skip = False
            if not skip:
                result.append(line)
        return "\n".join(result)

    def _generate_template_env(self) -> str:
        """生成 .env 模板"""
        return """# DBSKiter 数据库配置文件
# 1. 复制此文件并填入实际值
# 2. 确保已添加到 .gitignore

# ============================================================
# MySQL 配置示例
# ============================================================
DB_DIALECT=mysql+pymysql
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=your_password
DB_NAME=your_database

# ============================================================
# 多数据库支持（可选）
# 使用 --database=别名 切换
# ============================================================
# DB_JUMP_DIALECT=mysql+pymysql
# DB_JUMP_HOST=192.168.1.100
# DB_JUMP_PORT=3306
# DB_JUMP_USER=root
# DB_JUMP_PASSWORD=your_password
# DB_JUMP_NAME=jump

# ORACLE_DIALECT=oracle+jdbc
# ORACLE_HOST=192.168.1.100
# ORACLE_PORT=1521
# ORACLE_USER=system
# ORACLE_PASSWORD=your_password
# ORACLE_SERVICE=ORCL
"""

    def _generate_demo_env(self) -> str:
        """生成演示 .env"""
        return """# DBSKiter 演示配置文件
DB_DIALECT=mock
DB_HOST=demo
DB_PORT=0
DB_USER=demo
DB_PASSWORD=demo
DB_NAME=demo
DBSKITER_DEMO_MODE=true
"""

    def _confirm(self, message: str) -> bool:
        """确认对话框"""
        choice = input(f"{message} [y/N]: ").strip().lower()
        return choice in ("y", "yes")
