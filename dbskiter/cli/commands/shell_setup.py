"""
cli/commands/shell_setup.py

Shell Tab 补全配置命令

功能：
    - 一键配置 bash/zsh 的 Tab 补全
    - 支持全局激活（所有用户）或用户级注册（仅当前用户）
    - 自动检测 shell 类型

使用示例：
    dbskiter shell-setup           # 交互式配置
    dbskiter shell-setup --auto    # 自动检测并配置（推荐）
    dbskiter shell-setup --global  # 全局激活（需要 sudo）
"""

from __future__ import annotations

import os
import sys
import shutil
import subprocess
from argparse import ArgumentParser
from pathlib import Path
from typing import Optional

from .base import BaseCommand


class ShellSetupCommand(BaseCommand):
    """
    Shell Tab 补全配置命令

    功能描述：
        一键配置 dbskiter 的 bash/zsh Tab 补全，无需手动编辑 .bashrc

    使用示例：
        >>> dbskiter shell-setup
        >>> dbskiter shell-setup --auto
        >>> dbskiter shell-setup --global
    """

    name = "shell-setup"
    description = "一键配置 Shell Tab 补全（bash/zsh）"
    help_text = "自动配置 argcomplete 补全，无需手动编辑 .bashrc"

    @classmethod
    def add_arguments(cls, parser: ArgumentParser) -> None:
        """
        添加 shell-setup 命令参数
        """
        parser.add_argument(
            "--auto",
            action="store_true",
            help="自动检测 shell 并配置（推荐，首次使用）"
        )
        parser.add_argument(
            "--global",
            dest="global_mode",
            action="store_true",
            help="全局激活（需要 sudo，对所有用户生效）"
        )
        parser.add_argument(
            "--bash",
            action="store_true",
            help="强制配置 bash 补全"
        )
        parser.add_argument(
            "--zsh",
            action="store_true",
            help="强制配置 zsh 补全"
        )
        parser.add_argument(
            "--fish",
            action="store_true",
            help="强制配置 fish 补全"
        )

    def execute(self) -> int:
        """
        执行 Shell 补全配置

        返回说明：
            - int: 退出码，0 表示成功，1 表示失败或取消
        """
        output = self.output
        args = self.args

        output.print("")
        output.print("=" * 60)
        output.print("  DBSKiter Shell Tab 补全配置")
        output.print("=" * 60)
        output.print("")

        # 1. 检查 argcomplete 是否安装
        try:
            import argcomplete
            output.success("argcomplete 已安装")
        except ImportError:
            output.error("argcomplete 未安装，正在安装...")
            ret = subprocess.run(
                [sys.executable, "-m", "pip", "install", "argcomplete"],
                capture_output=True
            )
            if ret.returncode != 0:
                output.error("安装失败，请手动运行: pip install argcomplete")
                return 1
            output.success("argcomplete 安装成功")

        # 2. 检测 shell 类型
        shell = self._detect_shell(args)
        if not shell:
            output.error("无法检测 shell 类型，请手动指定 --bash / --zsh / --fish")
            return 1
        output.info(f"检测到 shell: {shell}")

        # 3. 选择配置模式
        if getattr(args, "global_mode", False):
            return self._setup_global(output, shell)
        elif getattr(args, "auto", False):
            return self._setup_user(output, shell, auto=True)
        else:
            # 交互式
            output.print("")
            output.print("配置方式:")
            output.print("  [1] 用户级（推荐）- 只影响当前用户，写入 ~/.bashrc")
            output.print("  [2] 全局激活 - 所有用户生效，需要 sudo")
            output.print("  [3] 只打印命令，手动执行")
            output.print("")
            choice = input("  选择 [1/2/3] (默认 1): ").strip() or "1"

            if choice == "1":
                return self._setup_user(output, shell)
            elif choice == "2":
                return self._setup_global(output, shell)
            elif choice == "3":
                return self._print_manual(output, shell)
            else:
                output.error("无效选择，已取消")
                return 1

    def _detect_shell(self, args) -> Optional[str]:
        """
        检测当前 shell 类型

        检测顺序：
            1. 命令行参数（--bash / --zsh / --fish）
            2. 环境变量 $SHELL
            3. 父进程名

        返回说明：
            - Optional[str]: 'bash', 'zsh', 'fish' 或 None
        """
        if getattr(args, "bash", False):
            return "bash"
        if getattr(args, "zsh", False):
            return "zsh"
        if getattr(args, "fish", False):
            return "fish"

        shell_path = os.environ.get("SHELL", "")
        if "bash" in shell_path:
            return "bash"
        if "zsh" in shell_path:
            return "zsh"
        if "fish" in shell_path:
            return "fish"

        # 尝试通过 ps 检测父进程
        try:
            import psutil
            parent = psutil.Process().parent()
            if parent:
                name = parent.name().lower()
                if "bash" in name:
                    return "bash"
                if "zsh" in name:
                    return "zsh"
                if "fish" in name:
                    return "fish"
        except ImportError:
            pass

        return None

    def _setup_user(self, output, shell: str, auto: bool = False) -> int:
        """
        用户级配置：写入 ~/.bashrc 或 ~/.zshrc

        参数说明：
            - output: 输出格式化器
            - shell: shell 类型
            - auto: 是否自动模式（不询问确认）

        返回说明：
            - int: 退出码
        """
        home = Path.home()
        rc_file = home / f".{shell}rc"
        if shell == "zsh":
            rc_file = home / ".zshrc"
        elif shell == "fish":
            rc_file = home / ".config/fish/config.fish"

        if not rc_file.parent.exists():
            rc_file.parent.mkdir(parents=True, exist_ok=True)

        # 生成补全命令
        register_cmd = f'eval "$(register-python-argcomplete dbskiter)"'
        if shell == "fish":
            register_cmd = "register-python-argcomplete --shell fish dbskiter | source"

        # 检查是否已配置
        if rc_file.exists():
            content = rc_file.read_text(encoding="utf-8")
            if "register-python-argcomplete dbskiter" in content:
                output.success(f"Tab 补全已配置: {rc_file}")
                output.info("配置已生效，重新打开终端或运行:")
                output.print(f"  source {rc_file}")
                return 0

        if not auto:
            output.print(f"\n  将写入配置到: {rc_file}")
            confirm = input("  确认? [Y/n]: ").strip().lower() or "y"
            if confirm != "y":
                output.info("已取消")
                return 0

        # 写入配置
        with open(rc_file, "a", encoding="utf-8") as f:
            f.write(f"\n# DBSKiter Tab 补全\n")
            f.write(f"{register_cmd}\n")

        output.success(f"配置已写入: {rc_file}")
        output.print("")
        output.info("配置已生效，请重新打开终端或运行:")
        output.print(f"  source {rc_file}")
        output.print("")
        output.info("现在可以按 Tab 补全命令:")
        output.print("  dbskiter mo<TAB>        -> monitor")
        output.print("  dbskiter monitor h<TAB> -> health")
        output.print("  dbskiter --dat<TAB>     -> --database")
        return 0

    def _setup_global(self, output, shell: str) -> int:
        """
        全局激活：使用 activate-global-python-argcomplete

        参数说明：
            - output: 输出格式化器
            - shell: shell 类型

        返回说明：
            - int: 退出码
        """
        cmd = ["activate-global-python-argcomplete"]
        if shell == "fish":
            cmd.append("--shell=fish")

        output.info(f"正在运行: {' '.join(cmd)}")
        ret = subprocess.run(cmd, capture_output=True, text=True)

        if ret.returncode == 0:
            output.success("全局 Tab 补全已激活！")
            output.info("所有用户都可以使用 Tab 补全")
            return 0
        else:
            output.error("全局激活失败，可能需要 sudo")
            output.print("")
            output.info("请手动运行:")
            output.print(f"  sudo {' '.join(cmd)}")
            if ret.stderr:
                output.print(f"\n错误信息: {ret.stderr.strip()}")
            return 1

    def _print_manual(self, output, shell: str) -> int:
        """
        只打印手动配置命令

        参数说明：
            - output: 输出格式化器
            - shell: shell 类型

        返回说明：
            - int: 退出码
        """
        output.print("")
        output.info("手动配置方法:")
        output.print("")

        if shell == "bash":
            output.print("1. 用户级（推荐）:")
            output.print('   eval "$(register-python-argcomplete dbskiter)"')
            output.print("   # 将上面这行添加到 ~/.bashrc")
            output.print("")
            output.print("2. 全局激活:")
            output.print("   sudo activate-global-python-argcomplete")
        elif shell == "zsh":
            output.print("1. 用户级（推荐）:")
            output.print('   eval "$(register-python-argcomplete dbskiter)"')
            output.print("   # 将上面这行添加到 ~/.zshrc")
            output.print("")
            output.print("2. 全局激活:")
            output.print("   sudo activate-global-python-argcomplete")
        elif shell == "fish":
            output.print("1. 用户级:")
            output.print("   register-python-argcomplete --shell fish dbskiter | source")
            output.print("   # 将上面这行添加到 ~/.config/fish/config.fish")
            output.print("")
            output.print("2. 全局激活:")
            output.print("   sudo activate-global-python-argcomplete --shell fish")

        output.print("")
        output.info("配置后重新打开终端或 source 配置文件即可生效")
        return 0
