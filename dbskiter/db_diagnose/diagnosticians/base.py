"""
基础诊断器

提供通用的诊断接口和基础实现
所有数据库特定诊断器都应继承此类
"""

import logging
from typing import Dict, Any, List, Optional
from abc import ABC, abstractmethod

from dbskiter.shared.unified_connector import UnifiedConnector

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
