"""
cli/command_aliases.py

扁平化命令别名系统

功能：将常用深层命令映射到顶层，降低新手记忆成本。

示例：
    dbskiter health          →  dbskiter monitor health
    dbskiter top             →  dbskiter diagnose top
    dbskiter slow            →  dbskiter diagnose slow-queries
    dbskiter locks           →  dbskiter lock analyze
    dbskiter audit           →  dbskiter security audit
    dbskiter report          →  dbskiter inspector report
    dbskiter welcome         →  新手引导（无需数据库）
"""

from typing import Dict, List, Tuple, Optional


# 顶层命令别名映射
# 格式: alias → (目标命令, [目标子命令参数])
COMMAND_ALIASES: Dict[str, Tuple[str, List[str]]] = {
    # 高频监控（每天使用）
    "health":       ("monitor", ["health"]),
    "health-all":   ("monitor", ["health-all"]),
    "anomalies":    ("monitor", ["anomalies"]),
    "capacity":     ("monitor", ["capacity"]),

    # 高频诊断（每天使用）
    "top":          ("diagnose", ["top"]),
    "slow":         ("diagnose", ["slow-queries"]),
    "slowlog":      ("diagnose", ["slow-queries"]),
    "slow-queries": ("diagnose", ["slow-queries"]),
    "realtime":     ("diagnose", ["realtime"]),
    "locks":        ("lock", ["analyze"]),
    "deadlocks":    ("lock", ["deadlocks"]),
    "space":        ("diagnose", ["space"]),
    "connections":  ("diagnose", ["connections"]),

    # 高频安全/巡检（每周使用）
    "audit":        ("security", ["audit"]),
    "score":        ("security", ["score"]),
    "permissions":  ("security", ["permissions"]),
    "report":       ("inspector", ["report"]),
    "inspect":      ("inspector", ["run"]),

    # 高频 SQL 相关（sql 本身已是命令名，不需要别名）
    "explain":      ("sql", ["explain"]),

    # 高频调度
    "backup":       ("scheduler", ["backup"]),
    "restore":      ("scheduler", ["restore"]),

    # 新手引导
    "welcome":      ("_welcome", []),
    "hello":        ("_welcome", []),
    "start":        ("_welcome", []),
    "guide":        ("_welcome", []),
}


def expand_alias(raw_args: List[str]) -> List[str]:
    """
    展开命令别名

    支持选项在前、命令在后的场景（如 --debug health）。
    也支持 --database chenzc audit 这种选项值分开的场景。

    参数说明:
        - raw_args: 原始命令行参数（不含程序名）

    返回说明:
        - List[str]: 展开后的参数列表

    使用示例:
        >>> expand_alias(["health", "--database", "jump"])
        ['monitor', 'health', '--database', 'jump']
        >>> expand_alias(["--debug", "health"])
        ['--debug', 'monitor', 'health']
        >>> expand_alias(["--database", "chenzc", "audit"])
        ['--database', 'chenzc', 'security', 'audit']
        >>> expand_alias(["top", "--limit", "20"])
        ['diagnose', 'top', '--limit', '20']
    """
    if not raw_args:
        return raw_args

    # 需要值的选项列表（遇到这些选项时跳过它们的值）
    VALUE_OPTIONS = {
        "--database", "-d",
        "--host", "-H",
        "--port", "-P",
        "--user", "-u",
        "--password", "-p",
        "--config", "-c",
        "--log-level",
        "--output-mode",
    }

    i = 0
    while i < len(raw_args):
        arg = raw_args[i]
        if arg.startswith("-"):
            # 检查是否是需要值的选项（且未使用 = 形式）
            if "=" not in arg:
                if arg in VALUE_OPTIONS and i + 1 < len(raw_args) and not raw_args[i + 1].startswith("-"):
                    i += 2  # 跳过选项和值
                    continue
            i += 1
        else:
            if arg in COMMAND_ALIASES:
                target_cmd, target_subargs = COMMAND_ALIASES[arg]
                return raw_args[:i] + [target_cmd] + target_subargs + raw_args[i + 1:]
            # 第一个非选项参数不是别名，说明用户用的是原始命令，不展开
            break

    return raw_args


def is_alias(cmd: str) -> bool:
    """
    检查命令是否为别名

    参数说明:
        - cmd: 命令名称

    返回说明:
        - bool: 是否为别名
    """
    return cmd in COMMAND_ALIASES


def get_alias_help() -> str:
    """
    生成别名帮助文本

    返回说明:
        - str: 格式化的别名帮助文本
    """
    lines = [
        "",
        "快捷命令（别名）:",
        "",
    ]

    groups = [
        ("监控", ["health", "health-all", "anomalies", "capacity"]),
        ("诊断", ["top", "slow", "slowlog", "realtime", "locks", "space", "connections"]),
        ("安全/巡检", ["audit", "score", "report", "inspect"]),
        ("SQL", ["sql", "explain"]),
        ("新手", ["welcome", "hello", "start"]),
    ]

    for group_name, aliases in groups:
        lines.append(f"  {group_name}:")
        for alias in aliases:
            target_cmd, target_subargs = COMMAND_ALIASES[alias]
            full_target = f"{target_cmd} {' '.join(target_subargs)}".strip()
            lines.append(f"    {alias:15s} →  {full_target}")
        lines.append("")

    return "\n".join(lines)
