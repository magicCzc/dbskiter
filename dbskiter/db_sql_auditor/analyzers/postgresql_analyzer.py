"""
PostgreSQL DDL影响分析器

文件功能：提供PostgreSQL特有的DDL影响分析
主要类：PostgreSQLDDLAnalyzer - PostgreSQL DDL分析器

作者：AI Assistant
创建时间：2026-04-23
"""

import logging
from typing import List

from .base import BaseDDLAnalyzer, DDLImpact

logger = logging.getLogger(__name__)


class PostgreSQLDDLAnalyzer(BaseDDLAnalyzer):
    """
    PostgreSQL DDL影响分析器

    提供PostgreSQL特有的DDL影响分析，包括：
    - 表大小和行数（通过元数据服务）
    - 依赖对象分析（视图、函数、外键等）
    - PostgreSQL特有DDL建议（pg_repack等）

    属性:
        connector: 数据库连接器
        dialect: 数据库方言（postgresql）
        metadata_service: 元数据服务
    """

    def analyze_impact(self, ddl_sql: str) -> DDLImpact:
        """
        分析PostgreSQL DDL变更影响

        参数:
            ddl_sql: DDL语句

        返回:
            DDLImpact: 影响分析结果

        示例:
            >>> analyzer = PostgreSQLDDLAnalyzer(connector)
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
            # 查找视图依赖
            result = self.connector.execute("""
                SELECT
                    dependent_ns.nspname || '.' || dependent_view.relname
                FROM pg_depend
                JOIN pg_rewrite ON pg_depend.objid = pg_rewrite.oid
                JOIN pg_class AS dependent_view ON pg_rewrite.ev_class = dependent_view.oid
                JOIN pg_class AS source_table ON pg_depend.refobjid = source_table.oid
                JOIN pg_namespace dependent_ns ON dependent_ns.oid = dependent_view.relnamespace
                WHERE source_table.relname = %s
                AND dependent_view.relkind = 'v'
            """, (table_name,))

            if result.rows:
                for row in result.rows:
                    dependents.append(f"视图: {row[0]}")

            # 查找外键依赖
            result = self.connector.execute("""
                SELECT
                    tc.table_name,
                    tc.constraint_name
                FROM information_schema.table_constraints tc
                JOIN information_schema.constraint_column_usage ccu
                    ON tc.constraint_name = ccu.constraint_name
                WHERE ccu.table_name = %s
                AND tc.constraint_type = 'FOREIGN KEY'
            """, (table_name,))

            if result.rows:
                for row in result.rows:
                    dependents.append(f"外键: {row[0]}.{row[1]}")

            # 查找函数依赖
            result = self.connector.execute("""
                SELECT
                    p.proname
                FROM pg_proc p
                JOIN pg_depend d ON p.oid = d.objid
                JOIN pg_class c ON d.refobjid = c.oid
                WHERE c.relname = %s
                AND d.deptype = 'n'
            """, (table_name,))

            if result.rows:
                for row in result.rows:
                    dependents.append(f"函数: {row[0]}")

            # 查找触发器
            result = self.connector.execute("""
                SELECT
                    trigger_name
                FROM information_schema.triggers
                WHERE event_object_table = %s
            """, (table_name,))

            if result.rows:
                for row in result.rows:
                    dependents.append(f"触发器: {row[0]}")

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
        生成PostgreSQL特有的DDL执行建议

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

        # PostgreSQL特有的大表DDL建议
        if table_size_mb and table_size_mb > 1000:
            suggestions.append("考虑使用pg_repack减少锁表时间")
            suggestions.append("检查maintenance_work_mem设置是否足够")
            suggestions.append("确保有足够的磁盘空间用于临时文件")

        # 添加列建议
        if operation == "ADD_COLUMN":
            suggestions.append("PostgreSQL 11+支持非空列快速添加（带默认值）")
            suggestions.append("考虑分批次添加列以减少锁表时间")

        # 索引建议
        if operation == "ADD_INDEX":
            suggestions.append("使用CONCURRENTLY选项创建索引以避免锁表")
            suggestions.append("检查shared_buffers和work_mem设置")

        return suggestions
