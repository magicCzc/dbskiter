"""
表诊断分析器

文件功能：提供数据库表的健康状况诊断
主要类：
    - TableAnalyzer: 表诊断分析器

作者：AI Assistant
创建时间：2026-04-22
最后修改：2026-04-23 - 重构使用DBMetadataService
"""

import logging
import re
from typing import Dict, Any, List, Optional

from sqlalchemy.exc import SQLAlchemyError, OperationalError

from dbskiter.shared.unified_connector import UnifiedConnector
from dbskiter.shared.db_metadata import DBMetadataService
from dbskiter.shared.error_handler import create_error_response, create_success_response, handle_exception

logger = logging.getLogger(__name__)


class TableAnalyzer:
    """
    表诊断分析器

    功能：
        1. 表大小和行数统计（通过DBMetadataService）
        2. 索引信息分析
        3. 冗余索引检测
        4. 表健康状况评估

    属性：
        connector: 数据库连接器
        metadata_service: 元数据服务

    使用示例：
        >>> analyzer = TableAnalyzer(connector)
        >>> result = analyzer.analyze("users")
        >>> print(result["data"]["size_mb"])
    """

    def __init__(self, connector: UnifiedConnector):
        """
        初始化表分析器

        参数：
            connector: UnifiedConnector 实例

        示例：
            >>> analyzer = TableAnalyzer(connector)
        """
        self.connector = connector
        self.metadata_service = DBMetadataService(connector)
        logger.info(f"TableAnalyzer 初始化完成 (dialect={connector.dialect})")

    def analyze(
        self,
        table_name: str,
        include_indexes: bool = True,
        include_statistics: bool = True
    ) -> Dict[str, Any]:
        """
        诊断单表健康状况

        参数：
            table_name: 表名
            include_indexes: 是否包含索引分析
            include_statistics: 是否包含统计信息

        返回：
            Dict: 诊断结果
            {
                "success": bool,
                "message": str,
                "data": {
                    "table_name": str,
                    "dialect": str,
                    "statistics": {...},
                    "indexes": [...],
                    "issues": [...],
                    "suggestions": [...]
                }
            }

        示例：
            >>> result = analyzer.analyze("users")
            >>> print(f"表大小: {result['data']['statistics']['size_mb']} MB")
        """
        try:
            dialect = self.connector.dialect.lower()
            result_data = {
                "table_name": table_name,
                "dialect": dialect,
                "statistics": {},
                "indexes": [],
                "issues": [],
                "suggestions": []
            }

            # 验证表名安全性
            if not self._is_valid_identifier(table_name):
                return create_error_response(
                    Exception(f"无效的表名: {table_name}"),
                    context=f"analyze_table({table_name})"
                )

            # 使用元数据服务获取表统计信息
            if include_statistics:
                try:
                    size_mb = self.metadata_service.get_table_size(table_name)
                    row_count = self.metadata_service.get_table_row_count(table_name)

                    if size_mb is not None:
                        result_data["statistics"]["size_mb"] = size_mb
                    if row_count is not None:
                        result_data["statistics"]["row_count"] = row_count

                except (ConnectionError, OperationalError) as e:
                    logger.warning(f"获取表 {table_name} 统计信息时连接失败: {e}")
                    result_data["issues"].append("无法获取表统计信息（连接失败）")
                except PermissionError as e:
                    logger.warning(f"获取表 {table_name} 统计信息时权限不足: {e}")
                    result_data["issues"].append("无法获取表统计信息（权限不足）")
                except SQLAlchemyError as e:
                    logger.warning(f"获取表 {table_name} 统计信息时数据库错误: {e}")
                    result_data["issues"].append(f"无法获取表统计信息（数据库错误: {str(e)[:50]}）")

            # 使用元数据服务获取索引信息
            if include_indexes:
                try:
                    index_metadata_list = self.metadata_service.get_table_indexes(table_name)

                    indexes = {}
                    for idx in index_metadata_list:
                        indexes[idx.name] = {
                            "columns": idx.columns,
                            "is_unique": idx.is_unique,
                            "index_type": idx.index_type
                        }

                    result_data["indexes"] = [
                        {
                            "name": name,
                            "columns": info["columns"],
                            "is_unique": info["is_unique"],
                            "index_type": info.get("index_type", "BTREE")
                        }
                        for name, info in indexes.items()
                    ]

                    # 检查冗余索引
                    if indexes:
                        redundant = self._find_redundant_indexes(indexes)
                        if redundant:
                            result_data["issues"].append(f"发现 {len(redundant)} 个冗余索引")
                            result_data["suggestions"].extend(redundant)

                except (ConnectionError, OperationalError) as e:
                    logger.warning(f"获取表 {table_name} 索引信息时连接失败: {e}")
                    result_data["issues"].append("无法获取索引信息（连接失败）")
                except PermissionError as e:
                    logger.warning(f"获取表 {table_name} 索引信息时权限不足: {e}")
                    result_data["issues"].append("无法获取索引信息（权限不足）")
                except SQLAlchemyError as e:
                    logger.warning(f"获取表 {table_name} 索引信息时数据库错误: {e}")
                    result_data["issues"].append(f"无法获取索引信息（数据库错误: {str(e)[:50]}）")

            return create_success_response(
                message=f"表 {table_name} 诊断完成",
                data=result_data
            )

        except Exception as e:
            return handle_exception(e, context=f"诊断表 {table_name}")

    def _find_redundant_indexes(self, indexes: Dict[str, Any]) -> List[str]:
        """
        查找冗余索引

        参数:
            indexes: 索引字典

        返回:
            List[str]: 冗余索引描述列表

        示例:
            >>> indexes = {
            ...     "idx_name": {"columns": ["name"]},
            ...     "idx_name_age": {"columns": ["name", "age"]}
            ... }
            >>> redundant = analyzer._find_redundant_indexes(indexes)
            >>> print(redundant)
            ['索引 idx_name_age 是 idx_name 的前缀，可能冗余']
        """
        redundant = []
        index_list = list(indexes.items())

        for i, (name1, info1) in enumerate(index_list):
            for name2, info2 in index_list[i+1:]:
                # 检查前缀重复
                cols1 = info1["columns"]
                cols2 = info2["columns"]

                if len(cols1) < len(cols2) and cols2[:len(cols1)] == cols1:
                    redundant.append(f"索引 {name2} 是 {name1} 的前缀，可能冗余")
                elif len(cols2) < len(cols1) and cols1[:len(cols2)] == cols2:
                    redundant.append(f"索引 {name1} 是 {name2} 的前缀，可能冗余")

        return redundant

    def _is_valid_identifier(self, name: str) -> bool:
        """
        验证标识符是否安全（防止SQL注入）

        只允许字母、数字、下划线，且必须以字母开头

        参数:
            name: 标识符名称

        返回:
            bool: 是否有效

        示例:
            >>> analyzer._is_valid_identifier("users")
            True
            >>> analyzer._is_valid_identifier("users; DROP")
            False
        """
        if not name or len(name) > 64:  # MySQL标识符长度限制
            return False

        # 匹配有效的SQL标识符
        pattern = r'^[a-zA-Z_][a-zA-Z0-9_]*$'
        return bool(re.match(pattern, name))
