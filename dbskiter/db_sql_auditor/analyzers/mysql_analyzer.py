"""
MySQL DDL影响分析器

文件功能：提供MySQL特有的DDL影响分析
主要类：MySQLDDLAnalyzer - MySQL DDL分析器

作者：Magiczc
创建时间：2026-04-23
"""

import logging
from typing import List

from .base import BaseDDLAnalyzer, DDLImpact

logger = logging.getLogger(__name__)


class MySQLDDLAnalyzer(BaseDDLAnalyzer):
    """
    MySQL DDL影响分析器

    提供MySQL特有的DDL影响分析，包括：
    - 表大小和行数（通过元数据服务）
    - 依赖对象分析
    - MySQL特有DDL工具建议（pt-online-schema-change, gh-ost）

    属性:
        connector: 数据库连接器
        dialect: 数据库方言（mysql）
        metadata_service: 元数据服务
    """

    def analyze_impact(self, ddl_sql: str) -> DDLImpact:
        """
        分析MySQL DDL变更影响

        参数:
            ddl_sql: DDL语句

        返回:
            DDLImpact: 影响分析结果

        示例:
            >>> analyzer = MySQLDDLAnalyzer(connector)
            >>> impact = analyzer.analyze_impact("ALTER TABLE users ADD COLUMN age INT")
            >>> print(f"表大小: {impact.table_size_mb}MB")
            >>> print(f"预估时间: {impact.execution_time_estimate}")
        """
        # 解析DDL
        table_name = self._extract_table_name(ddl_sql)
        operation = self._detect_operation(ddl_sql)

        impact = DDLImpact(
            ddl_sql=ddl_sql,
            table_name=table_name,
            operation=operation
        )

        # 通过元数据服务获取表信息
        try:
            impact.table_size_mb = self.metadata_service.get_table_size(table_name)
            impact.rows_estimate = self.metadata_service.get_table_row_count(table_name)
        except ConnectionError as e:
            logger.warning(f"获取表 {table_name} 信息时连接失败: {e}")
        except PermissionError as e:
            logger.warning(f"获取表 {table_name} 信息时权限不足: {e}")
        except ValueError as e:
            logger.warning(f"获取表 {table_name} 信息时数据错误: {e}")

        # 评估执行时间
        impact.execution_time_estimate = self._estimate_execution_time(
            impact.table_size_mb
        )

        # 评估风险
        impact.risks = self._assess_risks(operation, impact.table_size_mb)

        # 生成建议
        impact.suggestions = self._generate_suggestions(
            operation, impact.table_size_mb, self.dialect
        )

        # 获取依赖对象
        impact.dependent_objects = self._get_dependent_objects(table_name)

        logger.info(
            f"DDL影响分析完成: {table_name}, "
            f"大小={impact.table_size_mb}MB, 操作={operation}"
        )

        return impact

    def _get_dependent_objects(self, table_name: str) -> List[str]:
        """
        获取依赖该表的对象

        参数:
            table_name: 表名

        返回:
            List[str]: 依赖对象列表
        """
        dependents = []

        try:
            # 查找外键依赖
            result = self.connector.execute("""
                SELECT
                    table_name,
                    constraint_name
                FROM information_schema.key_column_usage
                WHERE referenced_table_name = %s
                AND table_schema = DATABASE()
            """, (table_name,))

            if result.rows:
                for row in result.rows:
                    dependents.append(f"外键: {row[0]}.{row[1]}")

            # 查找视图依赖
            result = self.connector.execute("""
                SELECT
                    table_name
                FROM information_schema.views
                WHERE view_definition LIKE %s
                AND table_schema = DATABASE()
            """, (f"%{table_name}%",))

            if result.rows:
                for row in result.rows:
                    dependents.append(f"视图: {row[0]}")

            # 查找存储过程依赖
            result = self.connector.execute("""
                SELECT
                    routine_name,
                    routine_type
                FROM information_schema.routines
                WHERE routine_definition LIKE %s
                AND routine_schema = DATABASE()
            """, (f"%{table_name}%",))

            if result.rows:
                for row in result.rows:
                    dependents.append(f"{row[1]}: {row[0]}")

        except ConnectionError as e:
            logger.warning(f"获取依赖对象时连接失败: {e}")
        except PermissionError as e:
            logger.warning(f"获取依赖对象时权限不足: {e}")
        except ValueError as e:
            logger.warning(f"获取依赖对象时数据错误: {e}")

        return dependents
