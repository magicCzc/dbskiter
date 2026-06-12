"""
基础巡检器

提供通用的巡检接口和基础实现
所有数据库特定巡检器都应继承此类
"""

import logging
from typing import List, Dict, Any, Optional
from abc import ABC, abstractmethod

from dbskiter.shared.unified_connector import UnifiedConnector
from ..models import InspectionItem, InspectionType, RiskLevel

logger = logging.getLogger(__name__)


class BaseInspector(ABC):
    """
    数据库巡检器基类

    定义通用的巡检接口，具体数据库类型需要继承此类
    实现特定数据库的检查逻辑

    属性:
        connector: 数据库连接器
        dialect: 数据库方言
    """

    # 通用阈值常量
    CONNECTION_USAGE_THRESHOLD = 80.0
    CONNECTION_USAGE_CRITICAL = 90.0
    TABLE_SIZE_THRESHOLD_MB = 1024
    TABLE_COUNT_THRESHOLD = 10000

    def __init__(self, connector: UnifiedConnector):
        """
        初始化巡检器

        参数:
            connector: UnifiedConnector 实例
        """
        self.connector = connector
        self.dialect = connector.dialect.lower()
        logger.info(f"初始化 {self.__class__.__name__} (dialect={self.dialect})")

    @abstractmethod
    def inspect_configuration(self) -> List[InspectionItem]:
        """
        检查数据库配置

        返回:
            List[InspectionItem]: 配置检查项列表
        """
        pass

    @abstractmethod
    def inspect_performance(self) -> List[InspectionItem]:
        """
        检查性能指标

        返回:
            List[InspectionItem]: 性能检查项列表
        """
        pass

    @abstractmethod
    def inspect_storage(self) -> List[InspectionItem]:
        """
        检查存储使用情况

        返回:
            List[InspectionItem]: 存储检查项列表
        """
        pass

    @abstractmethod
    def inspect_security(self) -> List[InspectionItem]:
        """
        检查安全配置

        返回:
            List[InspectionItem]: 安全检查项列表
        """
        pass

    @abstractmethod
    def inspect_capacity(self) -> List[InspectionItem]:
        """
        检查容量使用情况

        返回:
            List[InspectionItem]: 容量检查项列表
        """
        pass

    def get_instance_info(self) -> Dict[str, Any]:
        """
        获取实例基本信息

        返回:
            Dict[str, Any]: 实例信息字典
        """
        try:
            return {
                'instance_name': f"{self.dialect}-{self.connector.host}",
                'database_type': self.dialect,
                'host': self.connector.host,
                'port': self.connector.port,
                'version': 'unknown'
            }
        except AttributeError as e:
            logger.warning(f"连接器缺少必要属性: {e}")
            return {
                'instance_name': f"{self.dialect}-unknown",
                'database_type': self.dialect,
                'version': 'unknown'
            }

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
        except Exception as e:
            # 防御性编程：任何未预料到的异常都应安全返回 None
            # 而不是中断巡检流程。记录 warning 级别日志便于排查。
            logger.warning(f"查询执行异常 [{type(e).__name__}]: {e}")
            return None

    def _create_item(self, name: str, insp_type: InspectionType,
                     risk_level: RiskLevel, status: str,
                     description: str, actual_value: str = None,
                     reference: str = None, suggestion: str = None) -> InspectionItem:
        """
        创建检查项

        参数:
            name: 检查项名称
            insp_type: 检查类型
            risk_level: 风险等级
            status: 状态
            description: 描述
            actual_value: 实际值
            reference: 参考值
            suggestion: 建议

        返回:
            InspectionItem: 检查项
        """
        return InspectionItem(
            name=name,
            inspection_type=insp_type,
            risk_level=risk_level,
            status=status,
            description=description,
            actual_value=actual_value,
            reference=reference,
            suggestion=suggestion
        )
