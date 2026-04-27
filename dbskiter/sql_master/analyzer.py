"""
sql_master/analyzer.py
数据分析器 - 基于查询结果的数据分析
"""

from typing import List, Dict, Any, Optional

import pandas as pd
import numpy as np

from dbskiter.shared.models import PipelineResult


class DataAnalyzer:
    """
    数据分析器

    功能:
    - 描述性统计
    - 分组聚合
    - 趋势分析
    - TOP N 分析
    """

    def __init__(self, df: pd.DataFrame):
        self.df = df

    @staticmethod
    def from_query_result(result) -> "DataAnalyzer":
        """从 QueryResult 创建分析器"""
        return DataAnalyzer(result.df)

    def describe(self) -> Dict[str, Any]:
        """描述性统计"""
        desc = self.df.describe().to_dict()
        nulls = self.df.isnull().sum().to_dict()
        dtypes = self.df.dtypes.astype(str).to_dict()
        return {
            "statistics": desc,
            "null_counts": nulls,
            "data_types": dtypes,
            "shape": self.df.shape
        }

    def group_by(self, column: str, agg_col: str, func: str = "sum") -> pd.DataFrame:
        """分组聚合"""
        if func == "sum":
            return self.df.groupby(column)[agg_col].sum().reset_index()
        elif func == "mean":
            return self.df.groupby(column)[agg_col].mean().reset_index()
        elif func == "count":
            return self.df.groupby(column)[agg_col].count().reset_index()
        elif func == "max":
            return self.df.groupby(column)[agg_col].max().reset_index()
        elif func == "min":
            return self.df.groupby(column)[agg_col].min().reset_index()
        return self.df

    def top_n(self, column: str, n: int = 10, ascending: bool = False) -> pd.DataFrame:
        """TOP N 分析"""
        return self.df.nlargest(n, column) if not ascending else self.df.nsmallest(n, column)

    def correlation(self) -> pd.DataFrame:
        """相关性分析"""
        numeric_df = self.df.select_dtypes(include=[np.number])
        if numeric_df.empty:
            return pd.DataFrame()
        return numeric_df.corr()

    def distribution(self, column: str) -> Dict[str, Any]:
        """分布分析"""
        col = self.df[column]
        return {
            "mean": col.mean(),
            "median": col.median(),
            "std": col.std(),
            "min": col.min(),
            "max": col.max(),
            "skew": col.skew(),
            "kurtosis": col.kurtosis(),
            "null_count": col.isnull().sum()
        }
