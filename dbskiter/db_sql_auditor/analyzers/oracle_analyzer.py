"""
Oracle DDL影响分析器

文件功能：提供Oracle特有的DDL影响分析
主要类：OracleDDLAnalyzer - Oracle DDL分析器

作者：Magiczc
创建时间：2026-04-23
"""

import logging
from typing import List

from .base import BaseDDLAnalyzer, DDLImpact

logger = logging.getLogger(__name__)


class OracleDDLAnalyzer(BaseDDLAnalyzer):
    """
    Oracle DDL影响分析器

    提供Oracle特有的DDL影响分析，包括：
    - 表大小和行数（通过元数据服务）
    - 依赖对象分析（触发器、物化视图等）
    - Oracle特有DDL建议（DBMS_REDEFINITION等）

    属性:
        connector: 数据库连接器
        dialect: 数据库方言（oracle）
        metadata_service: 元数据服务
    """

    def analyze_impact(self, ddl_sql: str) -> DDLImpact:
        """
        分析Oracle DDL变更影响

        参数:
            ddl_sql: DDL语句

        返回:
            DDLImpact: 影响分析结果

        示例:
            >>> analyzer = OracleDDLAnalyzer(connector)
            >>> impact = analyzer.analyze_impact("ALTER TABLE users ADD age NUMBER")
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
            # 查找触发器
            result = self.connector.execute("""
                SELECT trigger_name
                FROM user_triggers
                WHERE table_name = UPPER(:1)
            """, (table_name,))

            if result.rows:
                for row in result.rows:
                    dependents.append(f"触发器: {row[0]}")

            # 查找物化视图
            result = self.connector.execute("""
                SELECT mview_name
                FROM user_mviews
                WHERE query LIKE '%' || UPPER(:1) || '%'
            """, (table_name,))

            if result.rows:
                for row in result.rows:
                    dependents.append(f"物化视图: {row[0]}")

            # 查找外键约束
            result = self.connector.execute("""
                SELECT
                    table_name,
                    constraint_name
                FROM user_constraints
                WHERE r_constraint_name IN (
                    SELECT constraint_name
                    FROM user_constraints
                    WHERE table_name = UPPER(:1)
                    AND constraint_type = 'P'
                )
            """, (table_name,))

            if result.rows:
                for row in result.rows:
                    dependents.append(f"外键: {row[0]}.{row[1]}")

            # 查找同义词
            result = self.connector.execute("""
                SELECT synonym_name
                FROM user_synonyms
                WHERE table_name = UPPER(:1)
            """, (table_name,))

            if result.rows:
                for row in result.rows:
                    dependents.append(f"同义词: {row[0]}")

        except ConnectionError as e:
            logger.warning(f"获取依赖对象时连接失败: {e}")
        except PermissionError as e:
            logger.warning(f"获取依赖对象时权限不足: {e}")
        except ValueError as e:
            logger.warning(f"获取依赖对象时数据错误: {e}")

        return dependents

    def _generate_suggestions(
        self,
        operation: str,
        table_size_mb: float,
        dialect: str
    ) -> List[str]:
        """
        生成Oracle特有的DDL执行建议

        参数:
            operation: 操作类型
            table_size_mb: 表大小（MB）
            dialect: 数据库方言

        返回:
            List[str]: 建议列表
        """
        suggestions = super()._generate_suggestions(
            operation, table_size_mb, dialect
        )

        # Oracle特有的大表DDL建议
        if table_size_mb and table_size_mb > 1000:
            suggestions.append("考虑使用DBMS_REDEFINITION进行在线重定义")
            suggestions.append("确保有足够的UNDO表空间")
            suggestions.append("检查并调整DDL操作的并行度")

        # 添加列建议
        if operation == "ADD_COLUMN":
            suggestions.append("考虑使用DEFAULT值避免全表更新")
            suggestions.append("如果是NOT NULL列，确保提供默认值")

        return suggestions
