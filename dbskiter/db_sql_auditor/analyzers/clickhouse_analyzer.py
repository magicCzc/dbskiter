"""
ClickHouse DDL影响分析器

文件功能：提供ClickHouse特有的DDL影响分析
主要类：ClickHouseDDLAnalyzer - ClickHouse DDL分析器

ClickHouse DDL特性：
    - ALTER操作是异步的，通过mutation执行
    - 支持轻量级DELETE/UPDATE（ALTER TABLE ... DELETE）
    - 不支持事务性DDL
    - 分布式表DDL需要ON CLUSTER

作者：Magiczc
创建时间：2026-06-03
"""

import logging
from typing import List

from .base import BaseDDLAnalyzer, DDLImpact

logger = logging.getLogger(__name__)


class ClickHouseDDLAnalyzer(BaseDDLAnalyzer):
    """
    ClickHouse DDL影响分析器

    提供ClickHouse特有的DDL影响分析，包括：
    - 异步mutation影响评估
    - 分布式表ON CLUSTER建议
    - 表引擎特性影响（MergeTree系列）
    - 轻量级DELETE/UPDATE影响

    属性:
        connector: 数据库连接器
        dialect: 数据库方言（clickhouse）
        metadata_service: 元数据服务
    """

    def analyze_impact(self, ddl_sql: str) -> DDLImpact:
        """
        分析ClickHouse DDL变更影响

        ClickHouse DDL特点：
        1. ALTER TABLE是异步的，通过mutation队列执行
        2. 分布式表需要ON CLUSTER语法
        3. 轻量级DELETE/UPDATE是ALTER操作
        4. 某些引擎不支持ALTER（如Log、TinyLog）

        参数:
            ddl_sql: DDL语句

        返回:
            DDLImpact: 影响分析结果

        示例:
            >>> analyzer = ClickHouseDDLAnalyzer(connector)
            >>> impact = analyzer.analyze_impact("ALTER TABLE users DELETE WHERE id = 1")
            >>> print(f"预估时间: {impact.execution_time_estimate}")
        """
        table_name = self._extract_table_name(ddl_sql)
        operation = self._detect_operation(ddl_sql)

        impact = DDLImpact(
            ddl_sql=ddl_sql,
            table_name=table_name,
            operation=operation
        )

        # 获取表信息
        try:
            impact.table_size_mb = self.metadata_service.get_table_size(table_name)
            impact.rows_estimate = self.metadata_service.get_table_row_count(table_name)
        except Exception as e:
            logger.warning(f"获取表 {table_name} 信息失败: {e}")

        # 评估执行时间（ClickHouse ALTER是异步的）
        impact.execution_time_estimate = self._estimate_clickhouse_execution_time(
            operation, impact.table_size_mb
        )

        # 评估风险
        impact.risks = self._assess_clickhouse_risks(operation, ddl_sql)

        # 生成建议
        impact.suggestions = self._generate_clickhouse_suggestions(
            operation, ddl_sql, table_name
        )

        return impact

    def _estimate_clickhouse_execution_time(
        self,
        operation: str,
        table_size_mb: float
    ) -> str:
        """
        预估ClickHouse DDL执行时间

        ClickHouse ALTER是异步的，通过mutation执行

        参数:
            operation: 操作类型
            table_size_mb: 表大小（MB）

        返回:
            str: 预估执行时间描述
        """
        if table_size_mb is None:
            return "未知（异步执行）"

        # ClickHouse ALTER是异步的
        if operation in ('DELETE', 'UPDATE', 'LIGHTWEIGHT_DELETE'):
            return "异步执行，取决于数据量和parts数量"
        elif operation == 'ADD_COLUMN':
            return "通常很快（秒级），异步完成"
        elif operation == 'DROP_COLUMN':
            return "异步执行，取决于数据量"
        elif operation == 'MODIFY_COLUMN':
            return "异步执行，可能需要重写数据"
        elif 'INDEX' in operation:
            return "异步构建，取决于数据量"
        else:
            return "异步执行"

    def _assess_clickhouse_risks(self, operation: str, ddl_sql: str) -> List[str]:
        """
        评估ClickHouse DDL风险

        参数:
            operation: 操作类型
            ddl_sql: DDL语句

        返回:
            List[str]: 风险列表
        """
        risks = []
        sql_upper = ddl_sql.upper()

        # 检查是否缺少ON CLUSTER（分布式表）
        if 'DISTRIBUTED' not in sql_upper and 'ON CLUSTER' not in sql_upper:
            risks.append(
                "如果是分布式表，建议添加ON CLUSTER子句"
            )

        if operation in ('DELETE', 'UPDATE', 'LIGHTWEIGHT_DELETE'):
            risks.append(
                "ClickHouse的DELETE/UPDATE是异步mutation，不会立即生效"
            )
            risks.append(
                "频繁的轻量级DELETE/UPDATE会影响性能，考虑使用ReplacingMergeTree"
            )

        if 'DROP' in operation or 'TRUNCATE' in operation:
            risks.append(
                "ClickHouse DROP/TRUNCATE操作不可逆，数据无法恢复"
            )

        if 'ALTER' in sql_upper and 'MATERIALIZED VIEW' in sql_upper:
            risks.append(
                "修改物化视图可能需要重建，影响查询性能"
            )

        return risks

    def _generate_clickhouse_suggestions(
        self,
        operation: str,
        ddl_sql: str,
        table_name: str
    ) -> List[str]:
        """
        生成ClickHouse DDL建议

        参数:
            operation: 操作类型
            ddl_sql: DDL语句
            table_name: 表名

        返回:
            List[str]: 建议列表
        """
        suggestions = []
        sql_upper = ddl_sql.upper()

        # 分布式表建议
        if 'ON CLUSTER' not in sql_upper:
            suggestions.append(
                "如果是集群部署，建议使用: ALTER TABLE ... ON CLUSTER cluster_name"
            )

        if operation in ('DELETE', 'UPDATE'):
            suggestions.append(
                "考虑使用ReplacingMergeTree或CollapsingMergeTree替代频繁DELETE"
            )
            suggestions.append(
                "使用SELECT ... FINAL查询获取最新数据，避免物理删除"
            )

        if operation == 'ADD_COLUMN':
            suggestions.append(
                "ClickHouse添加列是轻量级操作，不需要重写数据"
            )

        if 'INDEX' in operation and 'ADD' in operation:
            suggestions.append(
                "新索引是异步构建的，构建期间查询性能可能受影响"
            )
            suggestions.append(
                "考虑使用主键和ORDER BY替代二级索引"
            )

        if 'PARTITION' in sql_upper:
            suggestions.append(
                "分区操作可能影响大量数据，建议在低峰期执行"
            )

        # 检查mutation队列
        suggestions.append(
            "执行后检查system.mutations表监控进度"
        )

        return suggestions
