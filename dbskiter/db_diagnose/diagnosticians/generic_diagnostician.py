"""
通用诊断器

为不支持的数据库类型提供基础诊断能力

继承说明:
    本类继承自BaseDiagnostician，使用父类提供的_create_result方法
    构建标准响应格式。具体数据库诊断器应继承BaseDiagnostician并
    实现抽象方法。

使用示例:
    >>> from dbskiter.db_diagnose.diagnosticians import get_diagnostician
    >>> diagnostician = get_diagnostician('unknown_db', connector)
    >>> result = diagnostician.analyze_slow_queries()
"""

import logging
from typing import Dict, Any

from dbskiter.shared.unified_connector import UnifiedConnector
from .base import BaseDiagnostician

logger = logging.getLogger(__name__)


class GenericDiagnostician(BaseDiagnostician):
    """
    通用数据库诊断器

    为不支持的数据库类型提供基础诊断能力。
    继承自BaseDiagnostician，使用父类的_create_result方法构建响应。

    注意:
        本类仅提供占位实现，返回提示信息说明该数据库类型暂不支持。
        如需支持新的数据库类型，应创建继承BaseDiagnostician的子类。
    """

    def analyze_slow_queries(
        self,
        limit: int = 20,
        min_time: float = 1.0
    ) -> Dict[str, Any]:
        """
        分析慢查询（通用实现）

        参数:
            limit: 返回条数限制
            min_time: 最小执行时间（秒）

        返回:
            Dict: 慢查询分析结果
        """
        return self._create_result(
            success=False,
            message=f"{self.dialect} 数据库的慢查询分析尚未实现",
            error="请使用数据库原生工具进行慢查询分析",
            data={
                "total_queries": 0,
                "queries": []
            }
        )

    def analyze_performance_metrics(
        self,
        duration_minutes: int = 10
    ) -> Dict[str, Any]:
        """
        分析性能指标（通用实现）

        参数:
            duration_minutes: 采集时长（分钟）

        返回:
            Dict: 性能分析结果
        """
        return self._create_result(
            success=False,
            message=f"{self.dialect} 数据库的性能分析尚未实现",
            error="请使用数据库原生工具进行性能分析",
            data={}
        )

    def get_database_stats(self) -> Dict[str, Any]:
        """
        获取数据库统计信息（通用实现）

        返回:
            Dict: 数据库统计信息
        """
        return self._create_result(
            success=True,
            message=f"{self.dialect} 数据库的基础统计信息",
            data={
                "database_type": self.dialect,
                "note": "该数据库类型的专项诊断尚未实现"
            }
        )
