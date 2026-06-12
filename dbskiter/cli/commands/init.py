"""
cli/commands/init.py

交互式配置向导命令

功能：
    - 引导新手完成数据库配置
    - 生成 .env 配置文件
    - 创建示例配置文件
    - 测试连接

使用示例：
    dbskiter init              # 交互式配置向导
    dbskiter init --quick      # 快速模式，只生成 .env 模板
    dbskiter init --demo       # 生成带 mock 数据的演示配置
"""

from __future__ import annotations

import os
import re
import sys
from argparse import ArgumentParser
from pathlib import Path
from typing import Dict, Any, Optional

from .base import BaseCommand
from dbskiter.cli.exceptions import ConfigError


class InitCommand(BaseCommand):
    """
    交互式配置向导命令

    功能描述：
        引导用户完成数据库环境配置，生成 .env 文件

    使用示例：
        >>> dbskiter init
        >>> dbskiter init --quick
        >>> dbskiter init --demo
    """

    name = "init"
    description = "交互式配置向导 - 帮助新手快速配置数据库连接"
    help_text = "生成 .env 配置文件，引导完成数据库配置"

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
        """添加 init 命令参数"""
        parser.add_argument(
            "--quick",
            action="store_true",
            help="快速模式：只生成 .env 模板，不交互"
        )
        parser.add_argument(
            "--demo",
            action="store_true",
            help="演示模式：生成带 mock 数据的配置"
        )
        parser.add_argument(
            "--output",
            "-o",
            default=".env",
            help="输出文件路径（默认 .env）"
        )
        parser.add_argument(
            "--prefix",
            default="DB",
            help="环境变量前缀（默认 DB，多库时用 ORACLE、PG 等）"
        )

    def execute(self) -> int:
        """
        执行配置向导

        返回说明：
            - int: 退出码，0 表示成功
        """
        output = self.output
        args = self.args

        # 演示模式
        if getattr(args, "demo", False):
            return self._run_demo_mode()

        # 快速模式
        if getattr(args, "quick", False):
            return self._run_quick_mode()

        # 交互式模式
        return self._run_interactive_mode()

    def _run_demo_mode(self) -> int:
        """
        演示模式：生成带 mock 数据的配置

        返回说明：
            - int: 退出码
        """
        output = self.output
        output.success("正在生成演示配置...")

        env_content = self._generate_demo_env()
        output_path = Path(getattr(self.args, "output", ".env"))

        # 检查文件是否存在
        if output_path.exists():
            output.warning(f"文件 {output_path} 已存在")
            if not self._confirm("是否覆盖?"):
                output.info("已取消")
                return 0

        output_path.write_text(env_content, encoding="utf-8")
        output.success(f"演示配置已保存到: {output_path.absolute()}")
        output.print("")
        output.info("演示数据库包含以下表：")
        output.print("  - users (1000 条用户数据)")
        output.print("  - orders (5000 条订单数据)")
        output.print("  - products (200 条商品数据)")
        output.print("")
        output.info("使用方法：")
        output.print("  dbskiter --demo monitor health")
        output.print("  dbskiter --demo sql execute \"SELECT * FROM users LIMIT 10\"")
        output.print("  dbskiter --demo diagnose top")
        return 0

    def _run_quick_mode(self) -> int:
        """
        快速模式：生成 .env 模板

        返回说明：
            - int: 退出码
        """
        output = self.output
        output.success("正在生成配置模板...")

        env_content = self._generate_template_env()
        output_path = Path(getattr(self.args, "output", ".env"))

        if output_path.exists():
            output.warning(f"文件 {output_path} 已存在")
            if not self._confirm("是否覆盖?"):
                output.info("已取消")
                return 0

        output_path.write_text(env_content, encoding="utf-8")
        output.success(f"配置模板已保存到: {output_path.absolute()}")
        output.print("")
        output.info("下一步：")
        output.print("  1. 编辑 .env 文件，填入你的数据库连接信息")
        output.print("  2. 运行 dbskiter --help 查看可用命令")
        output.print("  3. 运行 dbskiter monitor 开始监控")
        return 0

    def _run_interactive_mode(self) -> int:
        """
        交互式配置向导

        返回说明：
            - int: 退出码
        """
        output = self.output

        output.print("")
        output.print("=" * 60)
        output.print("  DBSKiter 数据库配置向导")
        output.print("=" * 60)
        output.print("")
        output.print("本向导将帮助你生成数据库连接配置文件 (.env)")
        output.print("")

        # 步骤1：选择数据库类型
        db_type = self._choose_database_type()
        if not db_type:
            output.error("未选择数据库类型，已取消")
            return 1

        template = self.DB_TEMPLATES[db_type]
        prefix = getattr(self.args, "prefix", "DB")

        # 步骤2：输入连接信息
        config = self._collect_connection_info(db_type, template)
        if not config:
            output.error("配置信息不完整，已取消")
            return 1

        # 步骤3：生成 .env 内容
        env_content = self._generate_env_content(prefix, config)

        # 步骤4：保存文件
        output.print("")
        output_path = Path(getattr(self.args, "output", ".env"))

        if output_path.exists():
            output.warning(f"文件 {output_path} 已存在")
            if not self._confirm("是否覆盖现有配置?"):
                output.info("已取消，你的配置如下：")
                output.print("")
                output.print(env_content)
                return 0

        output_path.write_text(env_content, encoding="utf-8")
        output.success(f"配置已保存到: {output_path.absolute()}")
        output.print("")
        output.info("配置预览：")
        for line in env_content.strip().split("\n"):
            if line.startswith(f"{prefix}_PASSWORD="):
                output.print(f"{prefix}_PASSWORD=********")
            else:
                output.print(f"  {line}")

        output.print("")
        output.info("快速开始：")
        output.print(f"  dbskiter --database={prefix.lower()} monitor health")
        output.print(f"  dbskiter --database={prefix.lower()} diagnose top")
        output.print("")
        output.info("提示：")
        output.print("  - 使用 dbskiter init --demo 可以体验演示模式（无需数据库）")
        output.print("  - 使用 --database 参数切换不同数据库实例")

        return 0

    def _choose_database_type(self) -> Optional[str]:
        """
        选择数据库类型

        返回说明：
            - Optional[str]: 选中的数据库类型，或 None
        """
        output = self.output
        output.print("请选择数据库类型：")
        output.print("")

        types = list(self.DB_TEMPLATES.keys())
        for i, db_type in enumerate(types, 1):
            template = self.DB_TEMPLATES[db_type]
            output.print(f"  {i}. {db_type.upper():12s} (默认端口: {template['port']})")

        output.print("")
        raw_choice = input("请输入序号 (1-6): ").strip()
        # 清理输入中的 ANSI 转义序列和非数字字符
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
        """
        收集连接信息

        参数说明：
            - db_type: 数据库类型
            - template: 数据库模板

        返回说明：
            - Optional[Dict]: 配置字典，或 None
        """
        output = self.output
        config: Dict[str, Any] = {
            "dialect": template["dialect"],
        }

        output.print("")
        output.print(f"--- {db_type.upper()} 连接配置 ---")
        output.print("")

        # Host
        host_hint = template.get("host_hint", "数据库主机地址")
        host = input(f"  主机地址 [{host_hint}]: ").strip()
        if not host and db_type != "sqlite":
            host = "localhost"
        config["host"] = host

        # Port
        if db_type != "sqlite":
            port = input(f"  端口 [{template['port']}]: ").strip()
            config["port"] = int(port) if port else template["port"]
        else:
            config["port"] = template["port"]

        # User
        user = input(f"  用户名 [{template['user']}]: ").strip()
        config["user"] = user if user else template["user"]

        # Password
        password = input("  密码: ").strip()
        config["password"] = password

        # Database / Service
        if db_type == "oracle":
            service = input("  Service Name [ORCL]: ").strip()
            config["database"] = service if service else "ORCL"
            jdbc_driver = input("  JDBC 驱动路径 [ojdbc8.jar]: ").strip()
            config["jdbc_driver"] = jdbc_driver if jdbc_driver else "ojdbc8.jar"
        elif db_type == "sqlite":
            config["database"] = config["host"]  # SQLite 的 host 就是文件路径
        else:
            db_name = input("  数据库名 [test]: ").strip()
            config["database"] = db_name if db_name else "test"

        return config

    def _generate_env_content(
        self, prefix: str, config: Dict[str, Any]
    ) -> str:
        """
        生成 .env 文件内容

        参数说明：
            - prefix: 环境变量前缀
            - config: 配置字典

        返回说明：
            - str: .env 文件内容
        """
        lines = [
            "# DBSKiter 数据库配置文件",
            "# 生成时间: 由 init 向导生成",
            "",
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
            "# 连接池配置（可选）",
            f"{prefix}_POOL_SIZE=5",
            "",
            "# 只读模式（可选，防止误操作）",
            "# DBSKITER_READ_ONLY=true",
        ])

        return "\n".join(lines) + "\n"

    def _generate_template_env(self) -> str:
        """
        生成模板 .env 内容

        返回说明：
            - str: 模板内容
        """
        return """# DBSKiter 数据库配置文件
# 1. 复制此文件为 .env 并填入实际值
# 2. 确保 .env 已添加到 .gitignore

# ============================================================
# MySQL 配置示例
# ============================================================
DB_DIALECT=mysql+pymysql
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=your_password
DB_NAME=your_database
DB_POOL_SIZE=5

# ============================================================
# 多数据库支持（可选）
# 使用 --database=别名 切换
# ============================================================
# ORACLE_DIALECT=oracle+jdbc
# ORACLE_HOST=192.168.1.100
# ORACLE_PORT=1521
# ORACLE_USER=system
# ORACLE_PASSWORD=your_password
# ORACLE_SERVICE=ORCL

# PG_DIALECT=postgresql+psycopg2
# PG_HOST=localhost
# PG_PORT=5432
# PG_USER=postgres
# PG_PASSWORD=your_password
# PG_NAME=your_database

# ============================================================
# 安全策略
# ============================================================
# DBSKITER_READ_ONLY=true
"""

    def _generate_demo_env(self) -> str:
        """
        生成演示模式 .env 内容

        返回说明：
            - str: 演示配置内容
        """
        return """# DBSKiter 演示配置文件
# 此配置使用内置 Mock 数据，无需真实数据库

DB_DIALECT=mock
DB_HOST=demo
DB_PORT=0
DB_USER=demo
DB_PASSWORD=demo
DB_NAME=demo

# 演示模式标志
DBSKITER_DEMO_MODE=true
"""

    def _confirm(self, message: str) -> bool:
        """
        确认对话框

        参数说明：
            - message: 提示信息

        返回说明：
            - bool: 用户是否确认
        """
        choice = input(f"{message} [y/N]: ").strip().lower()
        return choice in ("y", "yes")
