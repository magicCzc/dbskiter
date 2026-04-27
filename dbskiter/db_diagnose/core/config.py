"""
诊断配置模块

文件功能：提供诊断功能的配置类
主要类：
    - DiagnoseConfig: 诊断配置数据类

作者：AI Assistant
创建时间：2026-04-22
"""

from dataclasses import dataclass


@dataclass
class DiagnoseConfig:
    """
    诊断配置

    属性说明：
        enable_deep_analysis: 是否启用深度分析
        enable_index_suggestion: 是否启用索引建议
        enable_sql_rewrite: 是否启用SQL重写建议
        enable_fingerprint: 是否启用SQL指纹
        enable_aas_analysis: 是否启用AAS分析（MySQL）
        min_slow_query_time: 慢查询最小时间（秒）
        max_analysis_results: 最大分析结果数

    使用示例：
        >>> config = DiagnoseConfig(
        ...     enable_deep_analysis=True,
        ...     min_slow_query_time=2.0
        ... )
        >>> print(config.enable_index_suggestion)
        True
    """
    enable_deep_analysis: bool = True
    enable_index_suggestion: bool = True
    enable_sql_rewrite: bool = True
    enable_fingerprint: bool = True
    enable_aas_analysis: bool = True
    min_slow_query_time: float = 1.0
    max_analysis_results: int = 100
