"""
基础诊断器

提供通用的诊断接口和基础实现
所有数据库特定诊断器都应继承此类
"""

import logging
from typing import Dict, Any, List, Optional
from abc import ABC, abstractmethod

from dbskiter.shared.unified_connector import UnifiedConnector
from dbskiter.shared.utils import format_bytes

logger = logging.getLogger(__name__)


class BaseDiagnostician(ABC):
    """
    数据库诊断器基类

    定义通用的诊断接口，具体数据库类型需要继承此类
    实现特定数据库的诊断逻辑

    属性:
        connector: 数据库连接器
        dialect: 数据库方言
    """

    def __init__(self, connector: UnifiedConnector):
        """
        初始化诊断器

        参数:
            connector: UnifiedConnector 实例
        """
        self.connector = connector
        self.dialect = connector.dialect.lower()
        logger.info(f"初始化 {self.__class__.__name__} (dialect={self.dialect})")

    @abstractmethod
    def analyze_slow_queries(
        self,
        limit: int = 20,
        min_time: float = 1.0
    ) -> Dict[str, Any]:
        """
        分析慢查询

        参数:
            limit: 返回条数限制
            min_time: 最小执行时间（秒）

        返回:
            Dict: 慢查询分析结果
        """
        pass

    @abstractmethod
    def analyze_performance_metrics(
        self,
        duration_minutes: int = 10
    ) -> Dict[str, Any]:
        """
        分析性能指标

        参数:
            duration_minutes: 采集时长（分钟）

        返回:
            Dict: 性能分析结果
        """
        pass

    @abstractmethod
    def get_database_stats(self) -> Dict[str, Any]:
        """
        获取数据库统计信息

        返回:
            Dict: 数据库统计信息
        """
        pass

    def _execute_query(self, sql: str, params: tuple = None) -> Optional[List]:
        """
        安全执行查询

        参数:
            sql: SQL语句
            params: 查询参数

        返回:
            Optional[List]: 查询结果或None
        """
        try:
            result = self.connector.execute(sql, params)
            return result.rows if result else None
        except ConnectionError as e:
            logger.warning(f"数据库连接失败: {e}")
            return None
        except PermissionError as e:
            logger.warning(f"权限不足: {e}")
            return None
        except ValueError as e:
            logger.warning(f"查询参数错误: {e}")
            return None

    def _create_result(
        self,
        success: bool,
        message: str,
        data: Dict[str, Any] = None,
        error: str = None
    ) -> Dict[str, Any]:
        """
        创建标准结果格式

        参数:
            success: 是否成功
            message: 消息
            data: 数据
            error: 错误信息

        返回:
            Dict: 标准结果格式
        """
        result = {
            "success": success,
            "message": message,
            "data": data or {},
            "dialect": self.dialect
        }
        if error:
            result["error"] = error
        return result

    def _calculate_health_score(
        self,
        items: List[Dict],
        rules: List[Dict[str, Any]]
    ) -> int:
        """
        通用健康评分计算

        统一的评分框架，避免各子类重复实现评分逻辑。
        所有评分方法最终都调用此方法。

        参数:
            items: 待评分的项目列表
            rules: 评分规则列表，每条规则格式:
                {
                    "name": "规则名称",
                    "filter": lambda item: bool,  # 匹配条件
                    "deduction": int,             # 每个匹配项扣分
                    "max_deduction": int           # 最大扣分上限，0表示不限制
                }

        返回:
            int: 健康评分(0-100)

        使用示例:
            >>> rules = [
            ...     {"name": "高优先级", "filter": lambda x: x.get("priority") == "high", "deduction": 10, "max_deduction": 30},
            ...     {"name": "中优先级", "filter": lambda x: x.get("priority") == "medium", "deduction": 5, "max_deduction": 20},
            ... ]
            >>> score = self._calculate_health_score(items, rules)
        """
        score = 100

        for rule in rules:
            matching_count = sum(1 for item in items if rule["filter"](item))
            total_deduction = matching_count * rule["deduction"]

            max_ded = rule.get("max_deduction", 0)
            if max_ded > 0:
                total_deduction = min(total_deduction, max_ded)

            score -= total_deduction

        return max(0, score)

    def _format_bytes(self, size_bytes: int) -> str:
        """
        格式化字节数为人类可读格式

        委托给 shared.utils.format_bytes 统一实现。

        参数:
            size_bytes: 字节数

        返回:
            str: 格式化后的字符串，如 "1.50 GB", "256.30 MB"
        """
        if size_bytes is None or size_bytes < 0:
            return "0 B"
        return format_bytes(size_bytes)
