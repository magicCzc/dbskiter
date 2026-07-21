"""
通用 DDL 影响分析器

为任意 JDBC 兼容数据库提供基础 DDL 影响分析能力。
通过标准 SQL 和 INFORMATION_SCHEMA 获取表元数据，
评估 DDL 变更的潜在影响。

支持分析：
    - ALTER TABLE ADD/DROP/MODIFY COLUMN
    - CREATE TABLE
    - DROP TABLE
    - TRUNCATE TABLE
    - CREATE/DROP INDEX

使用示例：
    >>> from dbskiter.db_sql_auditor.analyzers import get_ddl_analyzer
    >>> analyzer = get_ddl_analyzer('trino', connector)
    >>> impact = analyzer.analyze_impact("ALTER TABLE users ADD COLUMN age INT")
    >>> print(impact.risks)

版本: 1.0.0
作者: Magiczc
创建时间: 2026-06-05
"""

import logging
from typing import Dict, Any, List, Optional

from .base import BaseDDLAnalyzer, DDLImpact

logger = logging.getLogger(__name__)


class GenericDDLAnalyzer(BaseDDLAnalyzer):
    """
    通用 DDL 影响分析器

    通过 INFORMATION_SCHEMA 获取表大小、行数、索引等元数据，
    评估 DDL 变更的潜在影响和风险。

    属性：
        connector: UnifiedConnector 实例
        dialect: 数据库方言
        metadata_service: 元数据服务
    """

    def analyze_impact(self, ddl_sql: str) -> DDLImpact:
        """
        分析 DDL 变更影响（通用实现）

        分析步骤：
        1. 提取表名和操作类型
        2. 通过 INFORMATION_SCHEMA 获取表大小和行数
        3. 获取表上的索引和外键
        4. 评估风险和执行时间

        参数：
            ddl_sql: DDL 语句

        返回：
            DDLImpact: 影响分析结果
        """
        table_name = self._extract_table_name(ddl_sql)
        operation = self._detect_operation(ddl_sql)

        # 获取表元数据
        table_size_mb = self._get_table_size_mb(table_name)
        row_count = self._get_row_count(table_name)
        indexes = self._get_table_indexes(table_name)
        dependent_objects = self._get_dependent_objects(table_name)

        # 评估执行时间
        execution_time = self._estimate_execution_time(table_size_mb)

        # 评估风险
        risks = self._assess_risks(operation, table_size_mb)

        # 添加通用风险
        if operation in ["ADD_COLUMN", "MODIFY_COLUMN"]:
            if indexes:
                risks.append(
                    f"表上有 {len(indexes)} 个索引，"
                    "DDL 可能需要重建索引"
                )

        if operation == "DROP_COLUMN":
            if dependent_objects:
                risks.append(
                    f"有 {len(dependent_objects)} 个对象可能依赖该表，"
                    "删除列可能影响这些对象"
                )

        # 生成建议
        suggestions = self._generate_suggestions(
            operation, table_size_mb, self.dialect
        )

        # 通用建议
        if table_size_mb and table_size_mb > 100:
            suggestions.append(
                "大表 DDL 建议在维护窗口执行，并监控磁盘 I/O"
            )

        suggestions.append(
            "该数据库类型使用通用 DDL 分析器，"
            "建议在生产环境执行前进行充分测试"
        )

        return DDLImpact(
            ddl_sql=ddl_sql,
            table_name=table_name,
            operation=operation,
            execution_time_estimate=execution_time,
            table_size_mb=round(table_size_mb, 2) if table_size_mb else None,
            rows_estimate=row_count,
            risks=risks,
            suggestions=suggestions,
            dependent_objects=dependent_objects
        )

    def _get_table_size_mb(self, table_name: str) -> Optional[float]:
        """
        获取表大小（MB）

        通过 INFORMATION_SCHEMA 获取表大小，
        不同数据库的实现方式不同，这里使用通用查询。

        参数：
            table_name: 表名

        返回：
            Optional[float]: 表大小 MB，不支持返回 None
        """
        # 尝试多种方式获取表大小
        queries = [
            # 标准 INFORMATION_SCHEMA（MySQL/MariaDB 风格）
            (
                "SELECT (data_length + index_length) / 1024.0 / 1024.0 "
                "FROM information_schema.tables "
                "WHERE table_name = ? AND table_schema = DATABASE()",
                (table_name,)
            ),
            # PostgreSQL 风格
            (
                "SELECT pg_total_relation_size(quote_ident($1)) / 1024.0 / 1024.0",
                (table_name,)
            ),
            # 通用行数估算（作为大小的代理）
            (
                "SELECT COUNT(*) * 0.001 FROM " + table_name,
                ()
            ),
        ]

        for sql, params in queries:
            try:
                result = self.connector.execute(sql, params)
                if result.rows and result.rows[0][0] is not None:
                    return float(result.rows[0][0])
            except Exception:
                continue

        return None

    def _get_row_count(self, table_name: str) -> Optional[int]:
        """
        获取表行数

        参数：
            table_name: 表名

        返回：
            Optional[int]: 行数，不支持返回 None
        """
        try:
            result = self.connector.execute(
                f"SELECT COUNT(*) FROM {table_name}"
            )
            if result.rows and result.rows[0][0] is not None:
                return int(result.rows[0][0])
        except Exception:
            pass

        # 尝试 INFORMATION_SCHEMA
        try:
            result = self.connector.execute(
                "SELECT table_rows FROM information_schema.tables "
                "WHERE table_name = ?",
                (table_name,)
            )
            if result.rows and result.rows[0][0] is not None:
                return int(result.rows[0][0])
        except Exception:
            pass

        return None

    def _get_table_indexes(self, table_name: str) -> List[str]:
        """
        获取表上的索引列表

        参数：
            table_name: 表名

        返回：
            List[str]: 索引名列表
        """
        try:
            result = self.connector.execute(
                "SELECT index_name FROM information_schema.statistics "
                "WHERE table_name = ?",
                (table_name,)
            )
            if result.rows:
                return [row[0] for row in result.rows]
        except Exception:
            pass

        return []

    def _get_dependent_objects(self, table_name: str) -> List[str]:
        """
        获取依赖该表的对象列表

        通过 INFORMATION_SCHEMA 查询外键约束、视图等依赖关系。

        参数：
            table_name: 表名

        返回：
            List[str]: 依赖对象名列表
        """
        dependent = []

        # 查询外键约束
        try:
            result = self.connector.execute(
                "SELECT constraint_name FROM information_schema.table_constraints "
                "WHERE constraint_type = 'FOREIGN KEY' "
                "AND referenced_table_name = ?",
                (table_name,)
            )
            if result.rows:
                dependent.extend(
                    [f"FK:{row[0]}" for row in result.rows]
                )
        except Exception:
            pass

        # 查询引用该表的视图
        try:
            result = self.connector.execute(
                "SELECT table_name FROM information_schema.views "
                "WHERE view_definition LIKE ?",
                (f"%{table_name}%",)
            )
            if result.rows:
                dependent.extend(
                    [f"VIEW:{row[0]}" for row in result.rows]
                )
        except Exception:
            pass

        return dependent
