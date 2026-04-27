"""
MySQL功能检查器

文件功能：检查MySQL特有功能的可用性
主要类：
    - MySQLFeatureChecker: MySQL功能检查器

作者：AI Assistant
创建时间：2026-04-22
"""

import logging
from typing import Dict, Any, Optional

from dbskiter.shared.unified_connector import UnifiedConnector
from dbskiter.shared.error_handler import create_error_response

logger = logging.getLogger(__name__)


class MySQLFeatureChecker:
    """
    MySQL功能检查器

    功能：
        1. 检查是否为MySQL数据库
        2. 检查MySQL特有功能是否可用
        3. 提供统一的错误响应

    属性：
        connector: 数据库连接器
        is_mysql: 是否为MySQL数据库

    使用示例：
        >>> checker = MySQLFeatureChecker(connector)
        >>> if checker.is_mysql:
        ...     result = checker.check_feature("slow_query")
        ... else:
        ...     error = checker.get_not_supported_error("slow_query")
    """

    def __init__(self, connector: UnifiedConnector):
        """
        初始化MySQL功能检查器

        参数：
            connector: UnifiedConnector 实例

        示例：
            >>> checker = MySQLFeatureChecker(connector)
        """
        self.connector = connector
        self.is_mysql = 'mysql' in connector.dialect.lower()
        logger.info(f"MySQLFeatureChecker 初始化完成 (is_mysql={self.is_mysql})")

    def check_feature(self, feature_name: str) -> Dict[str, Any]:
        """
        检查特定功能是否可用

        参数：
            feature_name: 功能名称 (slow_query/aas/etc.)

        返回：
            Dict: 检查结果
            {
                "available": bool,
                "message": str
            }

        示例：
            >>> result = checker.check_feature("slow_query")
            >>> if result["available"]:
            ...     print("慢查询功能可用")
        """
        if not self.is_mysql:
            return {
                "available": False,
                "message": f"{feature_name} 功能仅支持MySQL数据库"
            }

        # 可以添加更多功能特定的检查
        return {
            "available": True,
            "message": f"{feature_name} 功能可用"
        }

    def get_not_supported_error(self, feature_name: str, context: Optional[str] = None) -> Dict[str, Any]:
        """
        获取功能不支持的错误响应

        参数：
            feature_name: 功能名称
            context: 错误上下文

        返回：
            Dict: 标准错误响应

        示例：
            >>> error = checker.get_not_supported_error("AAS分析")
            >>> print(error["error"]["message"])
        """
        return create_error_response(
            Exception(f"{feature_name} 功能仅支持MySQL数据库，当前方言: {self.connector.dialect}"),
            context=context or feature_name
        )

    def require_mysql(self, feature_name: str) -> Optional[Dict[str, Any]]:
        """
        要求必须是MySQL数据库，否则返回错误

        参数：
            feature_name: 功能名称

        返回：
            Optional[Dict]: 如果不是MySQL返回错误响应，否则返回None

        示例：
            >>> error = checker.require_mysql("慢查询分析")
            >>> if error:
            ...     return error
        """
        if not self.is_mysql:
            return self.get_not_supported_error(feature_name)
        return None
