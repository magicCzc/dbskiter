"""
历史命令模块

文件功能：
    - 列出命令执行历史
    - 搜索历史记录
    - 清空历史记录
    - 复用历史命令（rerun）

主要类：
    - HistoryCommand: 历史管理命令

版本: 1.0.0
作者: dbskiter team
创建时间: 2026-06-16
最后修改: 2026-06-16
"""

import sys
from typing import Dict, Any, Optional
from datetime import datetime

from .base import BaseCommand
from ..style import ThemeColor
from ...shared import HistoryManager


class HistoryCommand(BaseCommand):
    """
    历史管理命令

    支持查看、搜索、清空和复用命令历史。

    属性:
        name: 命令名 "history"
        help_text: 帮助文本
        description: 详细描述
    """

    name = "history"
    help_text = "查看和管理命令历史"
    description = "列出、搜索、清空和复用之前执行过的命令"

    @classmethod
    def add_arguments(cls, parser) -> None:
        """
        添加历史命令参数

        参数:
            parser: 子命令解析器
        """
        subparsers = parser.add_subparsers(
            dest="action",
            help="历史操作",
            metavar="ACTION"
        )

        # list 子命令（默认）
        list_parser = subparsers.add_parser(
            "list",
            help="列出历史记录（默认）"
        )
        list_parser.add_argument(
            "--limit", "-n",
            type=int,
            default=20,
            help="最多显示条数（默认 20）"
        )
        list_parser.add_argument(
            "--filter-db",
            help="按数据库别名过滤"
        )
        list_parser.add_argument(
            "--filter-cmd",
            help="按主命令过滤（如 diagnose, monitor）"
        )

        # search 子命令
        search_parser = subparsers.add_parser(
            "search",
            help="搜索历史记录"
        )
        search_parser.add_argument(
            "keyword",
            help="搜索关键词"
        )
        search_parser.add_argument(
            "--limit", "-n",
            type=int,
            default=20,
            help="最多显示条数"
        )

        # clear 子命令
        subparsers.add_parser(
            "clear",
            help="清空历史记录"
        )

        # rerun 子命令
        rerun_parser = subparsers.add_parser(
            "rerun",
            help="复用历史命令"
        )
        rerun_parser.add_argument(
            "index",
            type=int,
            help="历史记录索引（1=最新，可用 history list 查看）"
        )

        # 为 parser 本身也添加 --limit，支持直接 `history --limit 5`
        # 注意：--database 已由全局连接参数提供，此处不再重复添加
        parser.add_argument(
            "--limit", "-n",
            type=int,
            default=20,
            help="最多显示条数（默认 20）"
        )
        parser.add_argument(
            "--filter-db",
            help="按数据库别名过滤"
        )
        parser.add_argument(
            "--filter-cmd",
            help="按主命令过滤"
        )

    def execute(self) -> int:
        """
        执行历史命令

        返回:
            int: 退出码
        """
        action = getattr(self.args, "action", None)
        history = HistoryManager()

        # 如果没有子命令，默认执行 list
        if not action:
            return self._list_history(history)

        if action == "list":
            return self._list_history(history)
        elif action == "search":
            return self._search_history(history)
        elif action == "clear":
            return self._clear_history(history)
        elif action == "rerun":
            return self._rerun_history(history)
        else:
            self.output.error(f"未知操作: {action}")
            return 1

    def _list_history(self, history: HistoryManager) -> int:
        """
        列出历史记录

        参数:
            history: 历史管理器实例

        返回:
            int: 退出码
        """
        limit = getattr(self.args, "limit", 20)
        database = getattr(self.args, "filter_db", None)
        command = getattr(self.args, "filter_cmd", None)

        entries = history.list(
            limit=limit,
            database=database,
            command=command,
        )

        if not entries:
            self.output.rich_print("[dim]暂无历史记录[/dim]")
            return 0

        if self.output.json_mode:
            import json
            self.output.print(
                json.dumps([e.to_dict() for e in entries], ensure_ascii=False, indent=2),
                force=True
            )
            return 0

        # Rich Table 展示
        if self.output.console:
            from rich.table import Table as RichTable
            from rich.text import Text

            table = RichTable(
                title="命令历史",
                show_header=True,
                header_style=f"bold {ThemeColor.PRIMARY_BRIGHT}",
                border_style=ThemeColor.BORDER,
                padding=(0, 1),
            )
            table.add_column("#", style=f"bold {ThemeColor.PRIMARY}", min_width=3, justify="right")
            table.add_column("时间", min_width=16)
            table.add_column("命令", min_width=15)
            table.add_column("数据库", style=ThemeColor.INFO, min_width=12)
            table.add_column("耗时", min_width=8, justify="right")
            table.add_column("状态", min_width=6, justify="center")
            table.add_column("可复用命令", min_width=30)

            for idx, entry in enumerate(entries, 1):
                time_str = entry.timestamp[:16].replace("T", " ") if entry.timestamp else ""
                status = "✓" if entry.status_code == 0 else f"✗({entry.status_code})"
                status_style = ThemeColor.SUCCESS if entry.status_code == 0 else ThemeColor.ERROR
                time_ms = f"{entry.execution_time_ms:.0f}ms" if entry.execution_time_ms else "-"
                cli_str = entry.to_cli_string()
                # 截断过长命令
                if len(cli_str) > 40:
                    cli_str = cli_str[:37] + "..."

                table.add_row(
                    str(idx),
                    time_str,
                    f"{entry.command} {entry.action}".strip(),
                    entry.database or "-",
                    time_ms,
                    Text(status, style=status_style),
                    cli_str,
                )

            self.output.rich_print(table)
            self.output.print("")
            self.output.rich_print("[dim]提示: 使用 [cyan]dbskiter history rerun <索引>[/cyan] 复用命令[/dim]")
        else:
            # 纯文本降级
            self.output.print(f"{'#':>3} {'时间':16} {'命令':20} {'数据库':12} {'耗时':>8} {'状态':6} 命令")
            self.output.print("-" * 80)
            for idx, entry in enumerate(entries, 1):
                time_str = entry.timestamp[:16].replace("T", " ") if entry.timestamp else ""
                status = "OK" if entry.status_code == 0 else f"ERR({entry.status_code})"
                time_ms = f"{entry.execution_time_ms:.0f}ms" if entry.execution_time_ms else "-"
                cmd_str = f"{entry.command} {entry.action}".strip()
                self.output.print(
                    f"{idx:>3} {time_str:16} {cmd_str:20} "
                    f"{entry.database or '-':12} {time_ms:>8} {status:6} {entry.to_cli_string()}"
                )

        return 0

    def _search_history(self, history: HistoryManager) -> int:
        """
        搜索历史记录

        参数:
            history: 历史管理器实例

        返回:
            int: 退出码
        """
        keyword = getattr(self.args, "keyword", "")
        limit = getattr(self.args, "limit", 20)

        if not keyword:
            self.output.error("请提供搜索关键词")
            return 1

        entries = history.search(keyword, limit=limit)

        if not entries:
            self.output.rich_print(f"[dim]未找到包含 '{keyword}' 的历史记录[/dim]")
            return 0

        self.output.print(f"找到 {len(entries)} 条匹配记录:\n")
        return self._list_history(history)

    def _clear_history(self, history: HistoryManager) -> int:
        """
        清空历史记录

        参数:
            history: 历史管理器实例

        返回:
            int: 退出码
        """
        if history.clear():
            self.output.rich_print(f"[bold {ThemeColor.SUCCESS}]历史记录已清空[/bold {ThemeColor.SUCCESS}]")
            return 0
        else:
            self.output.error("清空历史记录失败")
            return 1

    def _rerun_history(self, history: HistoryManager) -> int:
        """
        复用历史命令

        参数:
            history: 历史管理器实例

        返回:
            int: 退出码
        """
        index = getattr(self.args, "index", 0)

        if index <= 0:
            self.output.error("请提供有效的历史索引（正整数）")
            return 1

        entry = history.get(index)
        if not entry:
            self.output.error(f"未找到索引为 {index} 的历史记录")
            self.output.rich_print("[dim]使用 [cyan]dbskiter history list[/cyan] 查看可用索引[/dim]")
            return 1

        cli_args = entry.to_cli_string().replace("dbskiter ", "").split()

        self.output.print(f"复用命令 #{index}: [cyan]{entry.to_cli_string()}[/cyan]")
        self.output.print("")

        # 递归调用 main，跳过本次历史记录（避免 rerun 自身被记录导致循环）
        import os
        os.environ["_DBSKITER_SKIP_HISTORY"] = "1"

        from ..main import main
        return main(cli_args)
