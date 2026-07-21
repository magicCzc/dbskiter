"""
通用工具函数模块

文件功能：提供各模块共用的工具函数，避免重复实现
主要函数：
    - format_bytes: 格式化字节数为人类可读格式
    - format_duration: 格式化秒数为人类可读格式
    - truncate_text: 截断文本并添加省略号

版本: 1.0.0
作者: Magiczc
创建时间: 2026-05-09
"""


def format_bytes(size_bytes: int) -> str:
    """
    格式化字节数为人类可读格式

    参数:
        size_bytes: int - 字节数

    返回:
        str - 格式化后的字符串，如 "1.50 GB", "256.30 MB"

    使用示例:
        >>> format_bytes(1024)
        '1.00 KB'
        >>> format_bytes(1073741824)
        '1.00 GB'
    """
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.2f} PB"


def format_duration(seconds: float) -> str:
    """
    格式化秒数为人类可读格式

    参数:
        seconds: float - 秒数

    返回:
        str - 格式化后的字符串，如 "1h 30m 15s", "45s"

    使用示例:
        >>> format_duration(90)
        '1m 30s'
        >>> format_duration(3661)
        '1h 1m 1s'
    """
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes}m {secs}s"
    else:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        return f"{hours}h {minutes}m {secs}s"


def truncate_text(text: str, max_length: int = 200, suffix: str = "...") -> str:
    """
    截断文本并添加省略号

    参数:
        text: str - 原始文本
        max_length: int - 最大长度，默认200
        suffix: str - 省略号后缀，默认 "..."

    返回:
        str - 截断后的文本

    使用示例:
        >>> truncate_text("a very long text", 10)
        'a very lo...'
    """
    if len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix
