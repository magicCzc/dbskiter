"""
SQL Server DDL影响分析器

文件功能：提供SQL Server特有的DDL影响分析
主要类：MSSQLDDLAnalyzer - SQL Server DDL分析器

作者：AI Assistant
创建时间：2026-06-03
"""

import logging
from typing import List

from .base import BaseDDLAnalyzer, DDLImpact

logger = logging.getLogger(__name__)


class MSSQLDDLAnalyzer(BaseDDLAnalyzer):
    """
    SQL Server DDL影响分析器

    提供SQL Server特有的DDL影响分析，包括：
    - 表大小和行数（通过元数据服务）
    - 依赖对象分析
    - SQL Server特有DDL工具建议
    - 在线DDL支持评估（SQL Server 2016+）

    属性:
        connector: 数据库连接器
        dialect: 数据库方言（mssql）
        metadata_service: 元数据服务
    """

    def analyze_impact(self, ddl_sql: str) -> DDLImpact:
        """
        分析SQL Server DDL变更影响

        参数:
            ddl_sql: DDL语句

        返回:
            DDLImpact: 影响分析结果

        示例:
            >>> analyzer = MSSQLDDLAnalyzer(connector)
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
            operation, impact.table_size_mb, table_name
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
            # 查询依赖该表的存储过程、函数、视图
            result = self.connector.execute("""
                SELECT DISTINCT
                    o.name AS object_name,
                    o.type_desc AS object_type
                FROM sys.sql_expression_dependencies d
                JOIN sys.objects o ON d.referencing_id = o.object_id
                WHERE d.referenced_entity_name = ?
                AND o.type IN ('P', 'V', 'FN', 'IF', 'TF')
            """, (table_name,))

            for row in result.rows if result else []:
                obj_type = self._get_object_type_desc(row[1])
                dependents.append(f"{row[0]} ({obj_type})")

        except ConnectionError as e:
            logger.warning(f"获取依赖对象时连接失败: {e}")
        except PermissionError as e:
            logger.warning(f"获取依赖对象时权限不足: {e}")
        except Exception as e:
            logger.warning(f"获取依赖对象失败: {e}")

        return dependents

    def _get_object_type_desc(self, type_desc: str) -> str:
        """
        获取对象类型描述

        参数:
            type_desc: 类型描述

        返回:
            str: 对象类型中文描述
        """
        type_map = {
            'SQL_STORED_PROCEDURE': '存储过程',
            'VIEW': '视图',
            'SQL_SCALAR_FUNCTION': '标量函数',
            'SQL_INLINE_TABLE_VALUED_FUNCTION': '内联表值函数',
            'SQL_TABLE_VALUED_FUNCTION': '表值函数',
            'CLR_STORED_PROCEDURE': 'CLR存储过程',
            'CLR_FUNCTION': 'CLR函数',
        }
        return type_map.get(type_desc, type_desc)

    def _estimate_execution_time(self, table_size_mb: float) -> str:
        """
        预估SQL Server DDL执行时间

        SQL Server DDL执行时间受以下因素影响：
        - 表大小
        - 是否有在线DDL支持（SQL Server 2016+）
        - 系统资源
        - 并发负载

        参数:
            table_size_mb: 表大小（MB）

        返回:
            str: 预估执行时间描述
        """
        if table_size_mb is None:
            return "未知"

        if table_size_mb < 100:
            return "几秒到几分钟"
        elif table_size_mb < 1000:
            return "几分钟到十几分钟"
        elif table_size_mb < 10000:
            return "十几分钟到一小时"
        else:
            return "一小时以上"

    def _assess_risks(self, operation: str, table_size_mb: float) -> List[str]:
        """
        评估SQL Server DDL风险

        参数:
            operation: 操作类型
            table_size_mb: 表大小（MB）

        返回:
            List[str]: 风险列表
        """
        risks = []

        # 大表DDL风险
        if table_size_mb and table_size_mb > 1000:
            risks.append("大表DDL可能导致长时间锁表，影响业务")
            risks.append("可能需要大量日志空间")

        # 超大表风险
        if table_size_mb and table_size_mb > 10000:
            risks.append("超大表DDL可能需要数小时，建议在维护窗口执行")

        # DROP操作风险
        if operation in ["DROP_TABLE", "DROP_COLUMN", "TRUNCATE_TABLE"]:
            risks.append("DROP/TRUNCATE操作不可逆，请确保已备份")

        # DROP COLUMN风险
        if operation == "DROP_COLUMN":
            risks.append("删除列可能导致依赖该列的索引、约束、视图出错")

        # MODIFY COLUMN风险
        if operation == "MODIFY_COLUMN":
            risks.append("修改列类型可能导致数据截断或转换错误")
            risks.append("可能需要重建索引")

        # ADD COLUMN风险
        if operation == "ADD_COLUMN":
            risks.append("添加非空列可能需要更新所有行")

        # ADD INDEX风险
        if operation == "ADD_INDEX":
            risks.append("创建索引可能消耗大量I/O和CPU资源")

        return risks

    def _generate_suggestions(
        self,
        operation: str,
        table_size_mb: float,
        table_name: str
    ) -> List[str]:
        """
        生成SQL Server DDL执行建议

        参数:
            operation: 操作类型
            table_size_mb: 表大小（MB）
            table_name: 表名

        返回:
            List[str]: 建议列表
        """
        suggestions = []

        # 大表DDL建议
        if table_size_mb and table_size_mb > 1000:
            suggestions.append("使用ONLINE=ON选项进行在线DDL，减少锁表时间")
            suggestions.append("考虑使用低峰期执行")
            suggestions.append("确保事务日志有足够的空间")

            # 超大表建议
            if table_size_mb > 10000:
                suggestions.append("考虑分批执行或使用分区表策略")
                suggestions.append("建议在维护窗口执行，并通知业务方")

        # DROP操作建议
        if operation in ["DROP_TABLE", "DROP_COLUMN", "TRUNCATE_TABLE"]:
            suggestions.append("执行前确认备份已创建")
            suggestions.append("确认没有应用程序依赖该对象")
            suggestions.append("检查是否有外键约束依赖")

        # ADD COLUMN建议
        if operation == "ADD_COLUMN":
            suggestions.append("如添加非空列，考虑先添加允许NULL的列，再更新数据，最后添加约束")
            suggestions.append("评估默认值对现有数据的影响")

        # ADD INDEX建议
        if operation == "ADD_INDEX":
            suggestions.append("使用ONLINE=ON创建索引，避免锁表")
            suggestions.append("考虑索引的填充因子(FILLFACTOR)设置")
            suggestions.append("评估索引对写操作性能的影响")

        # MODIFY COLUMN建议
        if operation == "MODIFY_COLUMN":
            suggestions.append("先在测试环境验证数据转换")
            suggestions.append("检查是否有依赖该列的计算列或索引")

        # 通用建议
        suggestions.append("执行前在测试环境验证")
        suggestions.append("监控DDL执行过程中的系统资源")
        suggestions.append("确保有回滚计划")

        return suggestions
