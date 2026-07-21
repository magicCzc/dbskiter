"""
shared/query_result.py
统一查询结果封装模块

文件功能：提供标准化的查询结果封装，支持多种数据导出格式
主要类：QueryResult - 统一查询结果封装

使用示例：
    >>> from dbskiter.shared.query_result import QueryResult
    >>> result = QueryResult(
    ...     rows=[(1, 'test'), (2, 'demo')],
    ...     columns=['id', 'name'],
    ...     row_count=2,
    ...     execution_time_ms=15.5
    ... )
    >>> df = result.df
    >>> dict_list = result.to_dict_list()

版本: 1.0.0
作者: Magiczc
创建时间: 2026-04-24
"""

import os
import json
import logging
from typing import List, Dict, Any, Tuple, Optional, Union
from dataclasses import dataclass, field
from pathlib import Path

try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class QueryResult:
    """
    统一查询结果封装

    提供标准化的查询结果结构，支持多种数据格式转换和导出

    属性:
        rows: 数据行列表，每行是一个元组
        columns: 列名列表
        row_count: 总行数
        execution_time_ms: 执行时间(毫秒)
        affected_rows: 受影响的行数(用于DML操作)
        _df: 缓存的pandas DataFrame对象

    使用示例:
        >>> result = QueryResult(
        ...     rows=[(1, 'Alice'), (2, 'Bob')],
        ...     columns=['id', 'name'],
        ...     row_count=2,
        ...     execution_time_ms=12.5
        ... )
        >>> print(result.summary())
        >>> df = result.df
    """
    rows: List[Tuple]
    columns: List[str]
    row_count: int
    execution_time_ms: float = 0.0
    affected_rows: int = 0
    _df: Optional[Any] = field(default=None, repr=False)

    def __post_init__(self):
        """初始化后的验证"""
        if self.rows and self.columns:
            # 验证每行数据与列数匹配
            expected_cols = len(self.columns)
            for i, row in enumerate(self.rows):
                if len(row) != expected_cols:
                    logger.warning(
                        f"第{i}行数据列数不匹配: 期望{expected_cols}, 实际{len(row)}"
                    )

    @property
    def df(self) -> Any:
        """
        获取 pandas DataFrame

        返回:
            pd.DataFrame: 查询结果的数据框表示

        注意:
            首次访问时会创建DataFrame并缓存，后续访问直接返回缓存对象
        """
        if not PANDAS_AVAILABLE:
            raise ImportError("pandas is required for DataFrame conversion")

        if self._df is None:
            self._df = pd.DataFrame(self.rows, columns=self.columns)
        return self._df

    def to_dict_list(self) -> List[Dict[str, Any]]:
        """
        转换为字典列表

        返回:
            List[Dict[str, Any]]: 每条记录是一个字典

        示例:
            >>> result.to_dict_list()
            [{'id': 1, 'name': 'Alice'}, {'id': 2, 'name': 'Bob'}]
        """
        return [
            {col: row[i] for i, col in enumerate(self.columns)}
            for row in self.rows
        ]

    def to_dict(self, orient: str = "records") -> Union[List[Dict], Dict]:
        """
        转换为字典格式

        参数:
            orient: 输出格式，可选 'records', 'dict', 'list', 'split', 'index'

        返回:
            Union[List[Dict], Dict]: 根据orient参数返回不同格式

        示例:
            >>> result.to_dict("records")  # 记录列表
            >>> result.to_dict("dict")     # 列名为键的字典
        """
        if not PANDAS_AVAILABLE:
            if orient == "records":
                return self.to_dict_list()
            raise ImportError("pandas is required for other orient formats")

        return self.df.to_dict(orient=orient)

    def to_json(self, path: Optional[str] = None, **kwargs) -> str:
        """
        导出为 JSON

        参数:
            path: 文件路径，为None时返回JSON字符串
            **kwargs: 传递给json.dumps或DataFrame.to_json的参数

        返回:
            str: JSON字符串或文件绝对路径

        示例:
            >>> json_str = result.to_json()
            >>> result.to_json("/tmp/output.json")
        """
        if path:
            abs_path = os.path.abspath(path)
            if PANDAS_AVAILABLE:
                self.df.to_json(abs_path, orient="records", force_ascii=False, **kwargs)
            else:
                with open(abs_path, 'w', encoding='utf-8') as f:
                    json.dump(self.to_dict_list(), f, ensure_ascii=False, **kwargs)
            return abs_path
        else:
            if PANDAS_AVAILABLE:
                return self.df.to_json(orient="records", force_ascii=False)
            return json.dumps(self.to_dict_list(), ensure_ascii=False)

    def to_csv(self, path: str, **kwargs) -> str:
        """
        导出为 CSV

        参数:
            path: 文件路径
            **kwargs: 传递给DataFrame.to_csv的参数

        返回:
            str: 文件绝对路径

        示例:
            >>> result.to_csv("/tmp/output.csv")
        """
        if not PANDAS_AVAILABLE:
            raise ImportError("pandas is required for CSV export")

        abs_path = os.path.abspath(path)
        self.df.to_csv(abs_path, index=False, **kwargs)
        return abs_path

    def to_excel(self, path: str, **kwargs) -> str:
        """
        导出为 Excel

        参数:
            path: 文件路径
            **kwargs: 传递给DataFrame.to_excel的参数

        返回:
            str: 文件绝对路径

        示例:
            >>> result.to_excel("/tmp/output.xlsx")
        """
        if not PANDAS_AVAILABLE:
            raise ImportError("pandas is required for Excel export")

        abs_path = os.path.abspath(path)
        self.df.to_excel(abs_path, index=False, engine='openpyxl', **kwargs)
        return abs_path

    def summary(self) -> str:
        """
        结果摘要

        返回:
            str: 格式化的摘要信息

        示例:
            >>> print(result.summary())
            [QueryResult] 100 rows x 5 cols | 执行: 15.5ms
        """
        base_info = f"[QueryResult] {self.row_count} rows x {len(self.columns)} cols | 执行: {self.execution_time_ms:.1f}ms"

        if PANDAS_AVAILABLE and self.rows:
            try:
                dtypes = self.df.dtypes.value_counts().to_dict()
                return f"{base_info} | 列类型: {dtypes}"
            except Exception:
                pass

        return base_info

    def first(self) -> Optional[Tuple]:
        """
        获取第一条记录

        返回:
            Optional[Tuple]: 第一条记录，如果没有数据则返回None
        """
        return self.rows[0] if self.rows else None

    def first_value(self, column: Optional[str] = None) -> Any:
        """
        获取第一个值

        参数:
            column: 列名，为None时返回第一列的值

        返回:
            Any: 第一个值，如果没有数据则返回None
        """
        if not self.rows:
            return None

        if column:
            if column not in self.columns:
                raise ValueError(f"列 '{column}' 不存在")
            col_idx = self.columns.index(column)
            return self.rows[0][col_idx]
        else:
            return self.rows[0][0] if self.rows[0] else None

    def is_empty(self) -> bool:
        """
        检查结果是否为空

        返回:
            bool: 如果没有数据返回True
        """
        return self.row_count == 0 or len(self.rows) == 0

    def __len__(self) -> int:
        """返回行数"""
        return self.row_count

    def __iter__(self):
        """迭代行数据"""
        return iter(self.rows)

    def __repr__(self) -> str:
        """字符串表示"""
        return f"QueryResult(rows={self.row_count}, cols={len(self.columns)}, time={self.execution_time_ms:.1f}ms)"
