"""
SQLite DDL影响分析器

文件功能：提供SQLite特有的DDL影响分析
主要类：SQLiteDDLAnalyzer - SQLite DDL分析器

SQLite DDL特性：
    - 支持有限的ALTER TABLE（RENAME TABLE, ADD COLUMN, RENAME COLUMN）
    - 不支持DROP COLUMN（需要重建表）
    - ALTER TABLE是立即执行的（非异步）
    - 复杂ALTER需要重建表

作者：Magiczc
创建时间：2026-06-03
"""

import logging
from typing import List

from .base import BaseDDLAnalyzer, DDLImpact

logger = logging.getLogger(__name__)


class SQLiteDDLAnalyzer(BaseDDLAnalyzer):
    """
    SQLite DDL影响分析器

    提供SQLite特有的DDL影响分析，包括：
    - 有限ALTER TABLE支持检测
    - 重建表风险评估
    - 外键约束影响
    - 事务支持评估

    属性:
        connector: 数据库连接器
        dialect: 数据库方言（sqlite）
        metadata_service: 元数据服务
    """

    def analyze_impact(self, ddl_sql: str) -> DDLImpact:
        """
        分析SQLite DDL变更影响

        SQLite DDL特点：
        1. ALTER TABLE支持有限：RENAME TABLE, ADD COLUMN, RENAME COLUMN
        2. DROP COLUMN不支持，需要重建表
        3. ALTER TABLE在事务中执行
        4. 重建表需要复制所有数据

        参数:
            ddl_sql: DDL语句

        返回:
            DDLImpact: 影响分析结果

        示例:
            >>> analyzer = SQLiteDDLAnalyzer(connector)
            >>> impact = analyzer.analyze_impact("ALTER TABLE users ADD COLUMN age INT")
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

        # 评估执行时间
        impact.execution_time_estimate = self._estimate_sqlite_execution_time(
            operation, impact.table_size_mb
        )

        # 评估风险
        impact.risks = self._assess_sqlite_risks(operation, ddl_sql)

        # 生成建议
        impact.suggestions = self._generate_sqlite_suggestions(
            operation, ddl_sql, table_name
        )

        return impact

    def _estimate_sqlite_execution_time(
        self,
        operation: str,
        table_size_mb: float
    ) -> str:
        """
        预估SQLite DDL执行时间

        参数:
            operation: 操作类型
            table_size_mb: 表大小（MB）

        返回:
            str: 预估执行时间描述
        """
        if table_size_mb is None:
            return "未知"

        if operation == 'ADD_COLUMN':
            return "很快（秒级），SQLite添加列不重写表"
        elif operation == 'DROP_COLUMN':
            return "需要重建表，取决于数据量"
        elif operation == 'RENAME_TABLE':
            return "很快（秒级）"
        elif operation == 'MODIFY_COLUMN':
            return "需要重建表，取决于数据量"
        elif 'INDEX' in operation:
            return "取决于数据量和索引复杂度"
        elif table_size_mb < 100:
            return "几秒到几分钟"
        elif table_size_mb < 1000:
            return "几分钟"
        else:
            return "较长时间（需要重建表）"

    def _assess_sqlite_risks(self, operation: str, ddl_sql: str) -> List[str]:
        """
        评估SQLite DDL风险

        参数:
            operation: 操作类型
            ddl_sql: DDL语句

        返回:
            List[str]: 风险列表
        """
        risks = []
        sql_upper = ddl_sql.upper()

        # SQLite不支持DROP COLUMN
        if 'DROP COLUMN' in sql_upper:
            risks.append(
                "SQLite原生不支持DROP COLUMN，需要重建表"
            )
            risks.append(
                "重建表需要：创建新表 -> 复制数据 -> 删除旧表 -> 重命名"
            )

        # 修改列类型需要重建表
        if 'ALTER COLUMN' in sql_upper or 'MODIFY' in sql_upper:
            risks.append(
                "SQLite不支持直接修改列类型，需要重建表"
            )

        # DROP TABLE风险
        if 'DROP TABLE' in sql_upper:
            risks.append(
                "DROP TABLE会永久删除表结构和数据，无法恢复"
            )

        # 外键约束影响
        if 'FOREIGN KEY' in sql_upper:
            risks.append(
                "修改外键约束可能影响关联表的数据完整性"
            )

        # 大表重建风险
        if 'DROP COLUMN' in sql_upper or 'MODIFY' in sql_upper:
            risks.append(
                "重建表期间需要双倍磁盘空间（旧表+新表）"
            )

        return risks

    def _generate_sqlite_suggestions(
        self,
        operation: str,
        ddl_sql: str,
        table_name: str
    ) -> List[str]:
        """
        生成SQLite DDL建议

        参数:
            operation: 操作类型
            ddl_sql: DDL语句
            table_name: 表名

        返回:
            List[str]: 建议列表
        """
        suggestions = []
        sql_upper = ddl_sql.upper()

        if 'DROP COLUMN' in sql_upper:
            suggestions.append(
                "使用以下步骤安全删除列："
            )
            suggestions.append(
                f"1. BEGIN TRANSACTION;"
            )
            suggestions.append(
                f"2. CREATE TABLE {table_name}_new AS SELECT ... FROM {table_name};"
            )
            suggestions.append(
                f"3. DROP TABLE {table_name};"
            )
            suggestions.append(
                f"4. ALTER TABLE {table_name}_new RENAME TO {table_name};"
            )
            suggestions.append(
                f"5. COMMIT;"
            )

        if 'ALTER COLUMN' in sql_upper or 'MODIFY' in sql_upper:
            suggestions.append(
                "SQLite修改列需要重建表，建议："
            )
            suggestions.append(
                "1. 创建新表（包含修改后的列定义）"
            )
            suggestions.append(
                "2. 复制数据（使用INSERT INTO ... SELECT）"
            )
            suggestions.append(
                "3. 删除旧表并重命名新表"
            )

        if 'ADD COLUMN' in sql_upper:
            suggestions.append(
                "SQLite ADD COLUMN支持：NULL默认值、字面量默认值、CURRENT_TIMESTAMP"
            )
            suggestions.append(
                "不支持：UNIQUE约束、PRIMARY KEY、FOREIGN KEY（需重建表）"
            )

        # 备份建议
        suggestions.append(
            f"执行前建议备份: sqlite3 {table_name}.db \".backup backup.db\""
        )

        # 事务建议
        suggestions.append(
            "建议在事务中执行DDL操作以保证原子性"
        )

        # PRAGMA建议
        suggestions.append(
            "执行前检查: PRAGMA foreign_keys; PRAGMA journal_mode;"
        )

        return suggestions
