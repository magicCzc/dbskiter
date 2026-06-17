"""
cli/output.py

输出格式化模块

功能说明：
- 表格格式化输出（兼容原有自研 TableFormatter）
- JSON 格式化输出
- 彩色终端输出（基于 Rich，自动适配 NO_COLOR/quiet/json）
- 进度显示（基于 Rich Progress/Status）
- 完全向后兼容原有接口

作者：MagiCzc
创建时间：2026-04-16
最后修改：2026-06-12
"""

import json
import shutil
from typing import List, Dict, Any, Optional, Union
from dataclasses import dataclass

from rich.console import Console
from rich.table import Table as RichTable
from rich.panel import Panel
from rich.text import Text
from rich.align import Align

from .exceptions import OutputError
from .style import (
    ThemeColor,
    get_console,
    get_stderr_console,
    make_style,
)


# ──────────────────────────────────────────────
# 表格格式化器（原有实现，保留兼容）
# ──────────────────────────────────────────────
@dataclass
class TableColumn:
    """表格列定义"""
    name: str
    width: int = 20
    align: str = "left"  # left, center, right


class TableFormatter:
    """
    表格格式化器（兼容版）

    将数据格式化为美观的表格输出。
    此为自研实现，不依赖 Rich，适合 JSON/quiet 模式或作为数据载体。

    用法:
        >>> formatter = TableFormatter()
        >>> formatter.add_column("Name", width=15)
        >>> formatter.add_column("Score", width=10, align="right")
        >>> formatter.add_row(["Alice", "95"])
        >>> print(formatter.render())
    """

    def __init__(self, max_width: int = None):
        """
        初始化表格格式化器

        参数:
            max_width: 最大宽度，默认自动检测终端宽度
        """
        self.columns: List[TableColumn] = []
        self.rows: List[List[str]] = []
        self.max_width = max_width or self._get_terminal_width()

    @staticmethod
    def _get_terminal_width() -> int:
        """获取终端宽度"""
        try:
            return shutil.get_terminal_size().columns
        except Exception:
            return 80

    def add_column(self, name: str, width: int = 20, align: str = "left") -> "TableFormatter":
        """
        添加列

        参数:
            name: 列名
            width: 列宽
            align: 对齐方式 (left, center, right)

        返回:
            self: 支持链式调用
        """
        self.columns.append(TableColumn(name, width, align))
        return self

    def add_row(self, row: List[Any]) -> "TableFormatter":
        """
        添加行

        参数:
            row: 行数据列表

        返回:
            self: 支持链式调用
        """
        str_row = []
        for i, value in enumerate(row):
            if i < len(self.columns):
                width = self.columns[i].width
                str_value = str(value) if value is not None else ""
                if len(str_value) > width - 1:
                    str_value = str_value[:width - 4] + "..."
                str_row.append(str_value)
            else:
                str_row.append(str(value) if value is not None else "")
        self.rows.append(str_row)
        return self

    def add_rows(self, rows: List[List[Any]]) -> "TableFormatter":
        """
        批量添加行

        参数:
            rows: 行数据列表的列表

        返回:
            self: 支持链式调用
        """
        for row in rows:
            self.add_row(row)
        return self

    def _format_cell(self, value: str, width: int, align: str) -> str:
        """格式化单元格"""
        if align == "center":
            return value.center(width)
        elif align == "right":
            return value.rjust(width)
        else:
            return value.ljust(width)

    def render(self) -> str:
        """
        渲染表格

        返回:
            str: 格式化后的表格字符串
        """
        if not self.columns:
            return ""

        lines = []
        total_width = sum(col.width for col in self.columns) + 3 * (len(self.columns) - 1) + 4
        lines.append("┌" + "─" * (total_width - 2) + "┐")

        header_cells = []
        for col in self.columns:
            header_cells.append(self._format_cell(col.name, col.width, "center"))
        lines.append("│ " + " │ ".join(header_cells) + " │")

        separator_cells = []
        for col in self.columns:
            separator_cells.append("─" * col.width)
        lines.append("├" + "─┼".join(separator_cells) + "┤")

        for row in self.rows:
            row_cells = []
            for i, value in enumerate(row):
                if i < len(self.columns):
                    col = self.columns[i]
                    row_cells.append(self._format_cell(value, col.width, col.align))
                else:
                    row_cells.append(str(value))
            while len(row_cells) < len(self.columns):
                row_cells.append("" * self.columns[len(row_cells)].width)
            lines.append("│ " + " │ ".join(row_cells[:len(self.columns)]) + " │")

        lines.append("└" + "─" * (total_width - 2) + "┘")
        return "\n".join(lines)

    def __str__(self) -> str:
        return self.render()

    def to_rich_table(self, title: Optional[str] = None) -> RichTable:
        """
        转换为 Rich Table（用于美化输出）

        参数:
            title: 表格标题

        返回:
            RichTable: Rich 表格对象

        使用示例:
            >>> formatter = TableFormatter()
            >>> # ... 添加列和数据
            >>> rich_tbl = formatter.to_rich_table("查询结果")
            >>> console.print(rich_tbl)
        """
        table = RichTable(
            title=Text(title, style=f"bold {ThemeColor.PRIMARY}") if title else None,
            border_style=ThemeColor.BORDER,
            header_style=f"bold {ThemeColor.PRIMARY_BRIGHT}",
            row_styles=["", f"{ThemeColor.MUTED}"],  # 斑马纹
            padding=(0, 1),
        )
        for col in self.columns:
            justify = "left"
            if col.align == "center":
                justify = "center"
            elif col.align == "right":
                justify = "right"
            table.add_column(col.name, justify=justify, min_width=min(col.width, 12))
        for row in self.rows:
            table.add_row(*[str(c) for c in row])
        return table


# ──────────────────────────────────────────────
# 输出格式化器（增强版，集成 Rich）
# ──────────────────────────────────────────────
class OutputFormatter:
    """
    输出格式化器（Rich 增强版）

    统一处理所有输出格式，完全向后兼容原有接口。
    在非 quiet/json 模式下自动使用 Rich 美化。

    用法:
        >>> formatter = OutputFormatter(json_mode=True)
        >>> formatter.output({"key": "value"})
        >>>
        >>> formatter2 = OutputFormatter(quiet=False, json_mode=False)
        >>> formatter2.success("备份完成")
    """

    def __init__(self, json_mode: bool = False, quiet: bool = False):
        """
        初始化输出格式化器

        参数:
            json_mode: 是否输出 JSON 格式（默认自动检测：管道/重定向时自动启用）
            quiet: 是否静默模式（只输出结果）
        """
        # 自动检测：如果 stdout 不是 TTY（管道/重定向/文件），自动切换到 JSON 模式
        if not json_mode and not quiet:
            import sys
            if not sys.stdout.isatty():
                json_mode = True

        self.json_mode = json_mode
        self.quiet = quiet
        # 懒加载 Rich Console，避免在 json/quiet 模式下无意义初始化
        self._console: Optional[Console] = None
        self._stderr_console: Optional[Console] = None

    @property
    def console(self) -> Optional[Console]:
        """获取标准输出 Console（懒加载）"""
        if self._console is None and not self.quiet and not self.json_mode:
            self._console = get_console(quiet=self.quiet, json_mode=self.json_mode)
        return self._console

    @property
    def stderr_console(self) -> Console:
        """获取错误输出 Console（始终可用，不受 quiet 影响）"""
        if self._stderr_console is None:
            self._stderr_console = get_stderr_console()
        return self._stderr_console

    # ── 基础输出 ──
    def print(self, message: str, force: bool = False) -> None:
        """
        打印消息（向后兼容）

        参数:
            message: 消息内容
            force: 是否强制输出（忽略 quiet 模式）
        """
        if not self.quiet or force:
            if self.console:
                self.console.print(message)
            else:
                print(message)

    # ── 结构化输出 ──
    def header(self, title: str, width: int = 60) -> None:
        """
        打印标题头（Rich Panel 美化）

        参数:
            title: 标题
            width: 宽度（Rich 模式下作为参考）
        """
        if self.json_mode:
            return
        if self.console:
            panel = Panel(
                Text(title, style=f"bold {ThemeColor.PRIMARY_BRIGHT}"),
                border_style=ThemeColor.PRIMARY,
                width=min(width, self.console.width - 4),
            )
            self.console.print(panel)
        else:
            self.print("=" * width)
            self.print(title.center(width))
            self.print("=" * width)

    def section(self, title: str) -> None:
        """
        打印章节标题

        参数:
            title: 标题
        """
        if self.json_mode:
            return
        if self.console:
            self.console.print(f"\n[header]{title}[/header]")
        else:
            self.print(f"\n{title}:")

    def item(self, label: str, value: Any, indent: int = 2) -> None:
        """
        打印列表项

        参数:
            label: 标签
            value: 值
            indent: 缩进空格数
        """
        if self.json_mode:
            return
        prefix = " " * indent
        if self.console:
            self.console.print(
                f"{prefix}[primary]{label}:[/primary] [info]{value}[/info]"
            )
        else:
            self.print(f"{prefix}- {label}: {value}")

    # ── 状态消息 ──
    def success(self, message: str) -> None:
        """打印成功消息"""
        if not self.json_mode:
            if self.console:
                self.console.print(f"[success]✔[/success] {message}")
            else:
                self.print(f"成功: {message}")

    def warning(self, message: str) -> None:
        """打印警告消息"""
        if not self.json_mode:
            if self.console:
                self.console.print(f"[warning]⚠[/warning] {message}")
            else:
                self.print(f"警告: {message}")

    def error(self, message: str) -> None:
        """打印错误消息"""
        if not self.json_mode:
            # 错误始终输出，使用 stderr_console
            self.stderr_console.print(f"[error]✖[/error] {message}")
        else:
            self.print(f"错误: {message}", force=True)

    def info(self, message: str) -> None:
        """打印信息消息"""
        if not self.json_mode:
            if self.console:
                self.console.print(f"[info]ℹ[/info] {message}")
            else:
                self.print(f"信息: {message}")

    # ── 高级 Rich 输出（新增）──
    def rich_print(self, *args, **kwargs) -> None:
        """
        直接调用 Rich Console.print（仅在非 quiet/json 模式下生效）

        使用示例:
            >>> formatter.rich_print("[success]完成[/success]")
            >>> formatter.rich_print(Panel("内容", title="面板"))
        """
        if self.console:
            self.console.print(*args, **kwargs)

    def rich_panel(self, content: str, title: Optional[str] = None, style: str = "") -> None:
        """
        打印 Rich Panel

        参数:
            content: 面板内容
            title: 面板标题
            style: 额外样式
        """
        if self.console:
            panel = Panel(
                content,
                title=Text(title, style=f"bold {ThemeColor.PRIMARY}") if title else None,
                border_style=ThemeColor.BORDER,
                padding=(1, 2),
            )
            self.console.print(panel)

    def rich_table(self, formatter: TableFormatter, title: Optional[str] = None) -> None:
        """
        输出 Rich 美化表格（自动降级到纯文本）

        参数:
            formatter: 表格格式化器
            title: 表格标题
        """
        if self.json_mode:
            return
        if self.console:
            self.console.print(formatter.to_rich_table(title))
        else:
            self.print(formatter.render())

    # ── 数据输出 ──
    def output_json(self, data: Dict[str, Any]) -> None:
        """
        输出 JSON 格式结果

        参数:
            data: 要输出的数据字典
        """
        try:
            json_str = json.dumps(data, ensure_ascii=False, indent=2, default=str)
            if self.json_mode:
                print(json_str)
            else:
                if self.console:
                    self.console.print(Panel(
                        json_str,
                        title=Text("JSON OUTPUT", style=f"bold {ThemeColor.MUTED}"),
                        border_style=ThemeColor.BORDER,
                    ))
                else:
                    self.print("\n" + "=" * 60)
                    self.print("JSON_OUTPUT:")
                    print(json_str)
                    self.print("=" * 60)
        except Exception as e:
            raise OutputError(f"JSON 序列化失败: {e}")

    def output_table(self, formatter: TableFormatter) -> None:
        """
        输出表格（自动选择 Rich 或纯文本）

        参数:
            formatter: 表格格式化器
        """
        if not self.json_mode:
            self.rich_table(formatter)

    def result(self, data: Dict[str, Any], table: TableFormatter = None) -> None:
        """
        输出结果（自动选择格式）

        参数:
            data: 数据字典
            table: 可选的表格格式化器
        """
        if self.json_mode:
            self.output_json(data)
        elif table:
            self.output_table(table)


# ──────────────────────────────────────────────
# 便捷函数（保留兼容）
# ──────────────────────────────────────────────
def print_table(data: List[Dict[str, Any]], columns: List[str] = None) -> None:
    """
    快速打印表格（Rich 增强版）

    参数:
        data: 字典列表
        columns: 指定列，None 表示使用所有键
    """
    if not data:
        print("(无数据)")
        return

    if columns is None:
        columns = list(data[0].keys())

    formatter = TableFormatter()
    for col in columns:
        formatter.add_column(col, width=max(15, len(col) + 2))

    for row in data:
        formatter.add_row([row.get(col, "") for col in columns])

    # 尝试用 Rich 输出，失败回退到纯文本
    console = get_console(quiet=False, json_mode=False)
    if console:
        console.print(formatter.to_rich_table())
    else:
        print(formatter.render())


def print_json(data: Any) -> None:
    """快速打印 JSON"""
    print(json.dumps(data, ensure_ascii=False, indent=2, default=str))
