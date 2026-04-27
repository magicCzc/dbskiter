"""
cli/output.py

输出格式化模块

提供：
- 表格格式化输出
- JSON 格式化输出
- 彩色终端输出
- 进度显示
"""

import json
import shutil
from typing import List, Dict, Any, Optional, Union
from dataclasses import dataclass

from .exceptions import OutputError


@dataclass
class TableColumn:
    """表格列定义"""
    name: str
    width: int = 20
    align: str = "left"  # left, center, right


class TableFormatter:
    """
    表格格式化器
    
    将数据格式化为美观的表格输出
    
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
        # 转换为字符串并截断
        str_row = []
        for i, value in enumerate(row):
            if i < len(self.columns):
                width = self.columns[i].width
                str_value = str(value) if value is not None else ""
                # 截断长文本
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
        else:  # left
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
        
        # 顶部边框
        total_width = sum(col.width for col in self.columns) + 3 * (len(self.columns) - 1) + 4
        lines.append("┌" + "─" * (total_width - 2) + "┐")
        
        # 表头
        header_cells = []
        for col in self.columns:
            header_cells.append(self._format_cell(col.name, col.width, "center"))
        lines.append("│ " + " │ ".join(header_cells) + " │")
        
        # 分隔线
        separator_cells = []
        for col in self.columns:
            separator_cells.append("─" * col.width)
        lines.append("├" + "─┼".join(separator_cells) + "┤")
        
        # 数据行
        for row in self.rows:
            row_cells = []
            for i, value in enumerate(row):
                if i < len(self.columns):
                    col = self.columns[i]
                    row_cells.append(self._format_cell(value, col.width, col.align))
                else:
                    row_cells.append(str(value))
            # 补齐缺失的列
            while len(row_cells) < len(self.columns):
                row_cells.append("" * self.columns[len(row_cells)].width)
            lines.append("│ " + " │ ".join(row_cells[:len(self.columns)]) + " │")
        
        # 底部边框
        lines.append("└" + "─" * (total_width - 2) + "┘")
        
        return "\n".join(lines)
    
    def __str__(self) -> str:
        return self.render()


class OutputFormatter:
    """
    输出格式化器
    
    统一处理所有输出格式
    
    用法:
        >>> formatter = OutputFormatter(json_mode=True)
        >>> formatter.output({"key": "value"})
    """
    
    def __init__(self, json_mode: bool = False, quiet: bool = False):
        """
        初始化输出格式化器
        
        参数:
            json_mode: 是否输出 JSON 格式
            quiet: 是否静默模式（只输出结果）
        """
        self.json_mode = json_mode
        self.quiet = quiet
    
    def print(self, message: str, force: bool = False) -> None:
        """
        打印消息
        
        参数:
            message: 消息内容
            force: 是否强制输出（忽略 quiet 模式）
        """
        if not self.quiet or force:
            print(message)
    
    def header(self, title: str, width: int = 60) -> None:
        """
        打印标题头
        
        参数:
            title: 标题
            width: 宽度
        """
        if self.json_mode:
            return
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
        self.print(f"{prefix}- {label}: {value}")
    
    def success(self, message: str) -> None:
        """打印成功消息"""
        if not self.json_mode:
            self.print(f"成功: {message}")
    
    def warning(self, message: str) -> None:
        """打印警告消息"""
        if not self.json_mode:
            self.print(f"警告: {message}")
    
    def error(self, message: str) -> None:
        """打印错误消息"""
        if not self.json_mode:
            self.print(f"错误: {message}")

    def info(self, message: str) -> None:
        """打印信息消息"""
        if not self.json_mode:
            self.print(f"信息: {message}")
    
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
                self.print("\n" + "=" * 60)
                self.print("JSON_OUTPUT:")
                print(json_str)
                self.print("=" * 60)
        except Exception as e:
            raise OutputError(f"JSON 序列化失败: {e}")
    
    def output_table(self, formatter: TableFormatter) -> None:
        """
        输出表格
        
        参数:
            formatter: 表格格式化器
        """
        if not self.json_mode:
            self.print(formatter.render())
    
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


# 便捷函数
def print_table(data: List[Dict[str, Any]], columns: List[str] = None) -> None:
    """
    快速打印表格
    
    参数:
        data: 字典列表
        columns: 指定列，None 表示使用所有键
    """
    if not data:
        print("(无数据)")
        return
    
    # 获取列名
    if columns is None:
        columns = list(data[0].keys())
    
    # 创建格式化器
    formatter = TableFormatter()
    for col in columns:
        formatter.add_column(col, width=max(15, len(col) + 2))
    
    # 添加数据
    for row in data:
        formatter.add_row([row.get(col, "") for col in columns])
    
    print(formatter.render())


def print_json(data: Any) -> None:
    """快速打印 JSON"""
    print(json.dumps(data, ensure_ascii=False, indent=2, default=str))
