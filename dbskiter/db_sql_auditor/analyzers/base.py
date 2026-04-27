"""
db_sql_auditor analyzers 基类模块

文件功能：定义DDL影响分析器的抽象基类和通用数据类型
主要类：
    - DDLImpact: DDL影响分析结果
    - BaseDDLAnalyzer: DDL分析器基类

作者：AI Assistant
创建时间：2026-04-23
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
import logging
import re

from dbskiter.shared.db_metadata import DBMetadataService

logger = logging.getLogger(__name__)


@dataclass
class DDLImpact:
    """DDL变更影响分析"""
    ddl_sql: str                 # DDL语句
    table_name: str              # 表名
    operation: str               # 操作类型

    # 影响评估
    execution_time_estimate: str = "未知"  # 预估执行时间
    table_size_mb: Optional[float] = None  # 表大小
    rows_estimate: Optional[int] = None    # 预估影响行数

    # 风险点
    risks: List[str] = field(default_factory=list)

    # 建议
    suggestions: List[str] = field(default_factory=list)

    # 依赖关系
    dependent_objects: List[str] = field(default_factory=list)  # 依赖对象

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "ddl_sql": self.ddl_sql,
            "table_name": self.table_name,
            "operation": self.operation,
            "execution_time_estimate": self.execution_time_estimate,
            "table_size_mb": self.table_size_mb,
            "rows_estimate": self.rows_estimate,
            "risks": self.risks,
            "suggestions": self.suggestions,
            "dependent_objects": self.dependent_objects
        }


class BaseDDLAnalyzer(ABC):
    """
    DDL影响分析器基类

    定义通用的DDL影响分析接口，具体数据库类型需要继承此类
    实现特定数据库的DDL影响分析逻辑

    属性:
        connector: 数据库连接器
        dialect: 数据库方言
        metadata_service: 元数据服务
    """

    def __init__(self, connector):
        """
        初始化DDL分析器

        参数:
            connector: 数据库连接器
        """
        self.connector = connector
        self.dialect = connector.dialect.lower()
        self.metadata_service = DBMetadataService(connector)
        logger.info(f"初始化 {self.__class__.__name__} (dialect={self.dialect})")

    @abstractmethod
    def analyze_impact(self, ddl_sql: str) -> DDLImpact:
        """
        分析DDL变更影响

        参数:
            ddl_sql: DDL语句

        返回:
            DDLImpact: 影响分析结果
        """
        pass

    def _extract_table_name(self, ddl_sql: str) -> str:
        """
        从DDL语句中提取表名

        参数:
            ddl_sql: DDL语句

        返回:
            str: 表名
        """
        # 匹配 ALTER TABLE table_name
        match = re.search(r'ALTER\s+TABLE\s+(\w+)', ddl_sql, re.IGNORECASE)
        if match:
            return match.group(1)

        # 匹配 CREATE TABLE table_name
        match = re.search(r'CREATE\s+TABLE\s+(\w+)', ddl_sql, re.IGNORECASE)
        if match:
            return match.group(1)

        # 匹配 DROP TABLE table_name
        match = re.search(r'DROP\s+TABLE\s+(\w+)', ddl_sql, re.IGNORECASE)
        if match:
            return match.group(1)

        return "unknown"

    def _detect_operation(self, ddl_sql: str) -> str:
        """
        检测DDL操作类型

        参数:
            ddl_sql: DDL语句

        返回:
            str: 操作类型
        """
        sql_upper = ddl_sql.upper()

        if 'ADD COLUMN' in sql_upper:
            return "ADD_COLUMN"
        elif 'DROP COLUMN' in sql_upper:
            return "DROP_COLUMN"
        elif 'MODIFY' in sql_upper or 'ALTER COLUMN' in sql_upper:
            return "MODIFY_COLUMN"
        elif 'ADD INDEX' in sql_upper or 'CREATE INDEX' in sql_upper:
            return "ADD_INDEX"
        elif 'DROP INDEX' in sql_upper:
            return "DROP_INDEX"
        elif 'ADD CONSTRAINT' in sql_upper:
            return "ADD_CONSTRAINT"
        elif 'DROP CONSTRAINT' in sql_upper:
            return "DROP_CONSTRAINT"
        elif sql_upper.startswith('CREATE'):
            return "CREATE_TABLE"
        elif sql_upper.startswith('DROP'):
            return "DROP_TABLE"
        elif sql_upper.startswith('TRUNCATE'):
            return "TRUNCATE_TABLE"
        else:
            return "ALTER"

    def _estimate_execution_time(self, table_size_mb: Optional[float]) -> str:
        """
        预估DDL执行时间

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
        else:
            return "十几分钟到几小时"

    def _assess_risks(
        self,
        operation: str,
        table_size_mb: Optional[float]
    ) -> List[str]:
        """
        评估DDL风险

        参数:
            operation: 操作类型
            table_size_mb: 表大小（MB）

        返回:
            List[str]: 风险列表
        """
        risks = []

        # 大表DDL风险
        if table_size_mb and table_size_mb > 1000:
            risks.append("大表DDL可能导致长时间锁表")

        # DROP操作风险
        if operation in ["DROP_TABLE", "DROP_COLUMN", "TRUNCATE_TABLE"]:
            risks.append("DROP/TRUNCATE操作不可逆，请确保已备份")

        # DROP COLUMN风险
        if operation == "DROP_COLUMN":
            risks.append("删除列可能导致依赖该列的应用程序出错")

        # MODIFY COLUMN风险
        if operation == "MODIFY_COLUMN":
            risks.append("修改列类型可能导致数据截断或转换错误")

        return risks

    def _generate_suggestions(
        self,
        operation: str,
        table_size_mb: Optional[float],
        dialect: str
    ) -> List[str]:
        """
        生成DDL执行建议

        参数:
            operation: 操作类型
            table_size_mb: 表大小（MB）
            dialect: 数据库方言

        返回:
            List[str]: 建议列表
        """
        suggestions = []

        # 大表DDL建议
        if table_size_mb and table_size_mb > 1000:
            if 'mysql' in dialect:
                suggestions.append("建议使用pt-online-schema-change或gh-ost进行在线DDL")
            elif 'postgresql' in dialect:
                suggestions.append("考虑使用pg_repack减少锁表时间")
            suggestions.append("在低峰期执行DDL操作")
            suggestions.append("确保有足够的磁盘空间")

        # DROP操作建议
        if operation in ["DROP_TABLE", "DROP_COLUMN", "TRUNCATE_TABLE"]:
            suggestions.append("执行前确认备份已创建")
            suggestions.append("确认没有应用程序依赖该对象")

        # 通用建议
        suggestions.append("执行前在测试环境验证")
        suggestions.append("监控DDL执行过程中的系统资源")

        return suggestions
