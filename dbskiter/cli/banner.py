"""
cli/banner.py

启动横幅模块

功能说明：
- 提供静态 ASCII 品牌横幅
- 只在 --help / --version / 无命令时显示
- 日常命令执行不显示，避免噪音

设计原则：
- 零动画，零延迟
- 专业简洁，不抢眼
- 适配不同终端宽度（自动截断或居中）

作者：MagiCzc
创建时间：2026-06-12
最后修改：2026-06-12
"""

from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.align import Align

from .style import ThemeColor


# ──────────────────────────────────────────────
# ASCII 艺术字（使用 FIGlet 风格的字符画）
# 为避免依赖 pyfiglet，直接内联简化版
# ──────────────────────────────────────────────
LOGO_LINES = [
    r"  ___  ___  ___  _  _____ _           _   ",
    r"  |  \/  |/ _ \| |/ / __(_)___ _ __ | |_ ",
    r"  | .  . | (_) | ' <| _|| / __| '  \|  _|",
    r"  |_|  |_|\___/|_|\_\_| |_\___|_|_|_|\__|",
]


def build_banner_text(version: str) -> Text:
    """
    构建横幅文本对象
    
    参数:
        version: 版本号字符串
        
    返回:
        Text: 带样式的 Rich Text 对象
    
    使用示例:
        >>> text = build_banner_text("3.0.0")
        >>> print(text.plain)
    """
    # Logo 部分：品牌蓝色
    logo_text = Text("\n".join(LOGO_LINES), style=f"bold {ThemeColor.PRIMARY}")

    # 副标题： muted 灰色
    subtitle = Text(
        f"\n  数据库 AIOps 运维助手  v{version}",
        style=f"{ThemeColor.MUTED}"
    )

    # 能力标签：彩色高亮（使用 Text.from_markup 解析 Rich 标签）
    capabilities = Text.from_markup(
        f"\n  [bold {ThemeColor.PRIMARY_BRIGHT}]8 Skills[/bold {ThemeColor.PRIMARY_BRIGHT}]"
        f"  |  [bold {ThemeColor.SUCCESS}]6 数据库[/bold {ThemeColor.SUCCESS}]"
        f"  |  [bold {ThemeColor.INFO}]73+ 命令[/bold {ThemeColor.INFO}]"
    )

    # 组合
    combined = Text.assemble(logo_text, subtitle, capabilities)
    return combined


def print_banner(console: Console, version: str, center: bool = True) -> None:
    """
    打印启动横幅
    
    参数:
        console: Rich Console 实例
        version: 版本号
        center: 是否居中对齐
    
    使用示例:
        >>> from rich.console import Console
        >>> print_banner(Console(), "3.0.0")
    """
    text = build_banner_text(version)

    panel = Panel(
        Align.center(text) if center else text,
        border_style=f"{ThemeColor.BORDER}",
        padding=(1, 2),
        width=min(console.width, 72),
    )

    console.print(panel)
    console.print()  # 空行分隔


def print_minimal_banner(console: Console, version: str) -> None:
    """
    打印极简横幅（用于版本号输出等紧凑场景）
    
    参数:
        console: Rich Console 实例
        version: 版本号
    
    使用示例:
        >>> print_minimal_banner(Console(), "3.0.0")
        # 输出: DBSKiter v3.0.0 — 数据库 AIOps 运维助手
    """
    text = Text.assemble(
        Text("DBSKiter", style=f"bold {ThemeColor.PRIMARY}"),
        Text(f" v{version}", style=f"{ThemeColor.MUTED}"),
        Text(" — 数据库 AIOps 运维助手", style=f"{ThemeColor.MUTED}"),
    )
    console.print(text)
