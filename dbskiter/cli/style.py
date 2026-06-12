"""
cli/style.py

终端样式统一配置

功能说明：
- 定义 DBSKiter CLI 的配色方案
- 提供 Console 实例工厂（自动处理 NO_COLOR、quiet、json 模式）
- 统一所有 Rich 样式标签，避免各处硬编码颜色

主要组件：
- ThemeColor: 配色常量
- get_console(): 获取适合当前模式的 Console 实例
- make_style(): 便捷样式字符串构造

作者：MagiCzc
创建时间：2026-06-12
最后修改：2026-06-12
"""

import os
import sys
from typing import Optional

from rich.console import Console
from rich.theme import Theme


# ──────────────────────────────────────────────
# 配色方案（DBSKiter 品牌色）
# ──────────────────────────────────────────────
class ThemeColor:
    """
    DBSKiter CLI 品牌配色
    
    设计原则：
    - 专业克制，避免高饱和刺眼色
    - 语义清晰，颜色即含义
    - 兼顾亮色/暗色终端背景
    """

    # 品牌主色（数据库蓝）
    PRIMARY = "#2563EB"       # 命令名、主标题
    PRIMARY_BRIGHT = "#3B82F6"  # 高亮强调
    PRIMARY_DIM = "#1D4ED8"   # 次要强调

    # 状态色
    SUCCESS = "#10B981"       # 成功、正常指标
    WARNING = "#F59E0B"       # 警告、慢查询、锁等待
    ERROR = "#EF4444"         # 错误、死锁、注入风险
    INFO = "#06B6D4"          # 信息提示

    # 中性色
    MUTED = "#6B7280"         # 元信息、时间戳、版本号
    TEXT = "#E5E7EB"          # 主文本（暗色终端）
    BORDER = "#4B5563"        # 边框、分隔线

    # 数据展示色（用于表格/图表区分）
    CYAN = "#22D3EE"
    MAGENTA = "#E879F9"
    YELLOW = "#FACC15"
    GREEN = "#4ADE80"
    RED = "#F87171"


# ──────────────────────────────────────────────
# Rich 自定义主题
# ──────────────────────────────────────────────
DBSKITER_THEME = Theme({
    "primary": f"bold {ThemeColor.PRIMARY}",
    "primary.dim": ThemeColor.PRIMARY_DIM,
    "success": f"bold {ThemeColor.SUCCESS}",
    "warning": f"bold {ThemeColor.WARNING}",
    "error": f"bold {ThemeColor.ERROR}",
    "info": ThemeColor.INFO,
    "muted": ThemeColor.MUTED,
    "border": ThemeColor.BORDER,
    "title": f"bold {ThemeColor.PRIMARY_BRIGHT}",
    "header": f"bold underline {ThemeColor.PRIMARY}",
    "metric.good": f"bold {ThemeColor.SUCCESS}",
    "metric.warn": f"bold {ThemeColor.WARNING}",
    "metric.bad": f"bold {ThemeColor.ERROR}",
    "sql.keyword": f"bold {ThemeColor.MAGENTA}",
    "sql.table": f"bold {ThemeColor.CYAN}",
    "sql.string": ThemeColor.YELLOW,
})


# ──────────────────────────────────────────────
# Console 工厂函数
# ──────────────────────────────────────────────
def should_disable_color() -> bool:
    """
    判断是否应禁用颜色输出
    
    检查优先级：
    1. NO_COLOR 环境变量（行业标配）
    2. 不是 TTY（管道/重定向）
    3. TERM=dumb
    
    返回:
        bool: True 表示禁用颜色
    """
    if os.environ.get("NO_COLOR", "").strip():
        return True
    if os.environ.get("TERM", "").strip().lower() == "dumb":
        return True
    if not sys.stdout.isatty():
        return True
    return False


def get_console(
    quiet: bool = False,
    json_mode: bool = False,
    force_color: bool = False,
    width: Optional[int] = None,
) -> Optional[Console]:
    """
    获取配置好的 Rich Console 实例
    
    参数说明：
    - quiet: 静默模式 → 返回 None，调用方应不输出装饰
    - json_mode: JSON 模式 → 返回 None，只输出结构化数据
    - force_color: 强制启用颜色（覆盖 NO_COLOR，测试用）
    - width: 指定终端宽度，None 表示自动检测
    
    返回:
        Console 实例，或在 quiet/json 模式下返回 None
    
    使用示例:
        >>> console = get_console(quiet=args.quiet, json_mode=args.json)
        >>> if console:
        ...     console.print("[success]操作成功[/success]")
    """
    if quiet or json_mode:
        return None

    color_system = "auto"
    if not force_color and should_disable_color():
        color_system = None  # 完全禁用 ANSI 颜色

    return Console(
        theme=DBSKITER_THEME,
        color_system=color_system,
        width=width,
        stderr=False,
        highlight=False,  # 我们自己控制高亮，避免误伤 SQL 输出
    )


def get_stderr_console(force_color: bool = False) -> Console:
    """
    获取错误输出用的 Console 实例
    
    错误信息始终可以带颜色（除非 NO_COLOR），不受 quiet 影响
    
    使用示例:
        >>> err_console = get_stderr_console()
        >>> err_console.print("[error]连接失败[/error]", style="error")
    """
    color_system = "auto"
    if not force_color and should_disable_color():
        color_system = None

    return Console(
        theme=DBSKITER_THEME,
        color_system=color_system,
        stderr=True,
        highlight=False,
    )


# ──────────────────────────────────────────────
# 便捷样式构造
# ──────────────────────────────────────────────
def make_style(text: str, style: str = "primary") -> str:
    """
    给文本包裹 Rich 样式标签
    
    参数:
        text: 原始文本
        style: 样式名（对应 DBSKITER_THEME 中的键）
        
    返回:
        str: 带样式标签的文本，如 "[success]完成[/success]"
    
    使用示例:
        >>> print(make_style("数据库连接正常", "success"))
        [success]数据库连接正常[/success]
    """
    return f"[{style}]{text}[/{style}]"


# ──────────────────────────────────────────────
# 公共样式快捷方式
# ──────────────────────────────────────────────
STYLES = {
    "title": lambda t: f"[title]{t}[/title]",
    "header": lambda t: f"[header]{t}[/header]",
    "success": lambda t: f"[success]{t}[/success]",
    "warning": lambda t: f"[warning]{t}[/warning]",
    "error": lambda t: f"[error]{t}[/error]",
    "info": lambda t: f"[info]{t}[/info]",
    "muted": lambda t: f"[muted]{t}[/muted]",
    "primary": lambda t: f"[primary]{t}[/primary]",
}
