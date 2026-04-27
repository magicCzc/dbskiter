"""
MySQL AAS分析器模块

文件功能：提供MySQL AAS（Average Active Sessions）分析功能
主要类：
    - AASAnalyzer: AAS分析器

作者：AI Assistant
创建时间：2026-04-22
"""

import logging
from typing import Dict, Any, Optional, List

from dbskiter.shared.unified_connector import UnifiedConnector
from dbskiter.shared.error_handler import create_success_response, handle_exception
from dbskiter.shared.mysql_aas_calculator_v2 import MySQLAASCalculatorV2 as MySQLAASCalculator

logger = logging.getLogger(__name__)


class AASAnalyzer:
    """
    MySQL AAS分析器

    功能：
        1. AAS指标采集
        2. 瓶颈识别
        3. 与慢查询关联分析

    属性：
        connector: 数据库连接器
        calculator: AAS计算器

    使用示例：
        >>> analyzer = AASAnalyzer(connector)
        >>> result = analyzer.analyze(duration_minutes=5)
        >>> print(f"平均AAS: {result['data']['aas_average']:.2f}")
    """

    def __init__(self, connector: UnifiedConnector):
        """
        初始化AAS分析器

        参数：
            connector: UnifiedConnector 实例

        示例：
            >>> analyzer = AASAnalyzer(connector)
        """
        self.connector = connector
        self.calculator = MySQLAASCalculator(connector)
        logger.info("AASAnalyzer 初始化完成")

    def analyze(
        self,
        duration_minutes: int = 10,
        interval_seconds: int = 10
    ) -> Dict[str, Any]:
        """
        AAS（Average Active Sessions）分析

        参数：
            duration_minutes: 采集时长（分钟）
            interval_seconds: 采样间隔（秒）

        返回：
            Dict: AAS分析结果

        示例：
            >>> result = analyzer.analyze(duration_minutes=5)
            >>> print(f"瓶颈: {result['data']['bottleneck']}")
        """
        try:
            import time

            # 采集AAS指标（多次采样）
            samples = []
            total_samples = (duration_minutes * 60) // interval_seconds

            for _ in range(total_samples):
                current = self.calculator.calculate_current_aas()
                samples.append(current)
                time.sleep(interval_seconds)

            # 计算平均AAS
            if samples:
                avg_aas = sum(s.total for s in samples) / len(samples)
                max_aas = max(s.total for s in samples)
                avg_cpu = sum(s.cpu for s in samples) / len(samples)
                avg_io = sum(s.io for s in samples) / len(samples)
                avg_lock = sum(s.lock for s in samples) / len(samples)
                avg_network = sum(s.network for s in samples) / len(samples)
                avg_other = sum(s.other for s in samples) / len(samples)
            else:
                avg_aas = max_aas = avg_cpu = avg_io = avg_lock = avg_network = avg_other = 0

            # 识别瓶颈
            bottleneck = self.calculator.identify_bottleneck()

            return create_success_response(
                message=f"AAS分析完成，平均AAS: {avg_aas:.2f}",
                data={
                    "aas_average": avg_aas,
                    "aas_max": max_aas,
                    "cpu_avg": avg_cpu,
                    "io_avg": avg_io,
                    "lock_avg": avg_lock,
                    "network_avg": avg_network,
                    "other_avg": avg_other,
                    "bottleneck": {
                        "type": bottleneck.bottleneck_type,
                        "severity": bottleneck.severity,
                        "description": bottleneck.description,
                        "primary_cause": bottleneck.primary_cause,
                        "recommendations": bottleneck.recommendations
                    },
                    "collection_duration": duration_minutes,
                    "sample_count": len(samples)
                }
            )

        except Exception as e:
            return handle_exception(e, context="AAS分析")

    def analyze_with_slow_queries(
        self,
        slow_query_analyzer,
        duration_minutes: int = 10
    ) -> Dict[str, Any]:
        """
        AAS与慢查询关联分析

        参数：
            slow_query_analyzer: 慢查询分析器
            duration_minutes: 采集时长（分钟）

        返回：
            Dict: 关联分析结果

        示例：
            >>> result = analyzer.analyze_with_slow_queries(slow_analyzer)
        """
        try:
            # 采集AAS
            aas_result = self.analyze(duration_minutes=duration_minutes)

            # 采集慢查询
            slow_result = slow_query_analyzer.analyze(
                limit=50,
                min_time=1.0,
                use_fingerprint=True
            )

            # 关联分析
            correlations = slow_query_analyzer.analyze_with_aas_correlation(
                aas_result.get("data", {})
            )

            return create_success_response(
                message="AAS与慢查询关联分析完成",
                data={
                    "aas_analysis": aas_result.get("data", {}),
                    "slow_queries": slow_result.get("data", {}),
                    "correlations": correlations
                }
            )

        except Exception as e:
            return handle_exception(e, context="AAS与慢查询关联分析")
