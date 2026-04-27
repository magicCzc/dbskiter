"""
通用巡检器

为不支持的数据库类型提供基础巡检能力
"""

import logging
from typing import List, Dict, Any

from dbskiter.shared.unified_connector import UnifiedConnector
from .base import BaseInspector
from ..models import InspectionItem, InspectionType, RiskLevel

logger = logging.getLogger(__name__)


class GenericInspector(BaseInspector):
    """
    通用数据库巡检器

    为不支持的数据库类型提供基础巡检能力
    只执行通用的、不依赖特定数据库的查询
    """

    def get_instance_info(self) -> Dict[str, Any]:
        """获取实例基本信息"""
        return super().get_instance_info()

    def inspect_configuration(self) -> List[InspectionItem]:
        """检查配置（通用实现）"""
        items = []

        items.append(self._create_item(
            name="数据库类型检查",
            insp_type=InspectionType.CONFIGURATION,
            risk_level=RiskLevel.INFO,
            status="pass",
            description=f"当前数据库类型: {self.dialect}",
            suggestion="该数据库类型的专项巡检尚未实现"
        ))

        return items

    def inspect_performance(self) -> List[InspectionItem]:
        """检查性能（通用实现）"""
        items = []

        items.append(self._create_item(
            name="性能检查",
            insp_type=InspectionType.PERFORMANCE,
            risk_level=RiskLevel.INFO,
            status="skip",
            description=f"{self.dialect} 数据库的性能检查尚未实现",
            suggestion="请使用数据库原生工具进行性能检查"
        ))

        return items

    def inspect_storage(self) -> List[InspectionItem]:
        """检查存储（通用实现）"""
        items = []

        items.append(self._create_item(
            name="存储检查",
            insp_type=InspectionType.STORAGE,
            risk_level=RiskLevel.INFO,
            status="skip",
            description=f"{self.dialect} 数据库的存储检查尚未实现",
            suggestion="请使用数据库原生工具进行存储检查"
        ))

        return items

    def inspect_security(self) -> List[InspectionItem]:
        """检查安全（通用实现）"""
        items = []

        items.append(self._create_item(
            name="安全检查",
            insp_type=InspectionType.SECURITY,
            risk_level=RiskLevel.INFO,
            status="skip",
            description=f"{self.dialect} 数据库的安全检查尚未实现",
            suggestion="请使用数据库原生工具进行安全检查"
        ))

        return items

    def inspect_capacity(self) -> List[InspectionItem]:
        """检查容量（通用实现）"""
        items = []

        items.append(self._create_item(
            name="容量检查",
            insp_type=InspectionType.CAPACITY,
            risk_level=RiskLevel.INFO,
            status="skip",
            description=f"{self.dialect} 数据库的容量检查尚未实现",
            suggestion="请使用数据库原生工具进行容量检查"
        ))

        return items
