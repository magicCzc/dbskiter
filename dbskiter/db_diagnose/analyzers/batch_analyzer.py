"""
批量SQL分析器模块

文件功能：提供批量SQL分析功能，支持串行和并发执行
主要类：
    - BatchAnalyzer: 批量分析器

作者：AI Assistant
创建时间：2026-04-22
"""

import logging
from typing import List, Dict, Any, Callable
from concurrent.futures import ThreadPoolExecutor, as_completed

from dbskiter.shared.error_handler import create_error_response

logger = logging.getLogger(__name__)


class BatchAnalyzer:
    """
    批量SQL分析器

    功能：
        1. 串行批量分析
        2. 并发批量分析
        3. 进度显示

    使用示例：
        >>> analyzer = BatchAnalyzer()
        >>> results = analyzer.analyze_concurrent(sqls, analyze_func, max_workers=4)
    """

    def __init__(self):
        """初始化批量分析器"""
        logger.info("BatchAnalyzer 初始化完成")

    def analyze_serial(
        self,
        items: List[Any],
        analyze_func: Callable[[Any], Dict[str, Any]],
        show_progress: bool = False
    ) -> List[Dict[str, Any]]:
        """
        串行批量分析

        参数：
            items: 待分析项目列表
            analyze_func: 分析函数
            show_progress: 是否显示进度

        返回：
            List[Dict]: 分析结果列表

        示例：
            >>> results = analyzer.analyze_serial(sqls, lambda sql: skill.analyze_sql(sql))
        """
        results = []
        total = len(items)

        for i, item in enumerate(items):
            if show_progress:
                logger.info(f"分析进度: {i+1}/{total}")

            result = analyze_func(item)
            results.append(result)

        return results

    def analyze_concurrent(
        self,
        items: List[Any],
        analyze_func: Callable[[Any], Dict[str, Any]],
        max_workers: int = 4,
        show_progress: bool = False
    ) -> List[Dict[str, Any]]:
        """
        并发批量分析

        参数：
            items: 待分析项目列表
            analyze_func: 分析函数
            max_workers: 最大并发数
            show_progress: 是否显示进度

        返回：
            List[Dict]: 分析结果列表

        示例：
            >>> results = analyzer.analyze_concurrent(
            ...     sqls,
            ...     lambda sql: skill.analyze_sql(sql),
            ...     max_workers=4
            ... )
        """
        results = [None] * len(items)
        total = len(items)
        completed = 0

        def analyze_with_index(args):
            idx, item = args
            return idx, analyze_func(item)

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(analyze_with_index, (i, item)): i
                for i, item in enumerate(items)
            }

            for future in as_completed(futures):
                try:
                    idx, result = future.result()
                    results[idx] = result
                    completed += 1

                    if show_progress:
                        logger.info(f"分析进度: {completed}/{total} ({completed/total*100:.1f}%)")

                except Exception as e:
                    logger.error(f"分析任务失败: {e}")
                    idx = futures[future]
                    results[idx] = create_error_response(
                        Exception(str(e)),
                        context="analyze_concurrent"
                    )

        return results
