"""
SQL解析器模块

文件功能：提供健壮的SQL解析功能，替代正则表达式匹配
主要类：
    - SQLParser: SQL解析器
    - ParsedSQL: 解析后的SQL对象
    - SQLType: SQL类型枚举

解析能力：
    1. 识别SQL类型（SELECT/INSERT/UPDATE/DELETE等）
    2. 提取表名
    3. 识别WHERE子句
    4. 识别JOIN操作
    5. 识别子查询

作者：Security Team
创建时间：2026-05-20
最后修改：2026-05-20
"""

import logging
import re
from typing import Dict, Any, Optional, List, Set
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class SQLType(Enum):
    """SQL类型枚举"""
    SELECT = "SELECT"
    INSERT = "INSERT"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    DROP = "DROP"
    TRUNCATE = "TRUNCATE"
    ALTER = "ALTER"
    CREATE = "CREATE"
    REPLACE = "REPLACE"
    MERGE = "MERGE"
    CALL = "CALL"
    EXPLAIN = "EXPLAIN"
    SHOW = "SHOW"
    DESCRIBE = "DESCRIBE"
    DESC = "DESC"
    UNKNOWN = "UNKNOWN"


class SQLDialect(Enum):
    """SQL方言枚举"""
    MYSQL = "mysql"
    POSTGRESQL = "postgresql"
    ORACLE = "oracle"
    SQLSERVER = "sqlserver"
    SQLITE = "sqlite"
    GENERIC = "generic"


@dataclass
class ParsedSQL:
    """
    解析后的SQL对象
    
    属性：
        original_sql: 原始SQL语句
        sql_type: SQL类型
        tables: 涉及的表名列表
        has_where: 是否有WHERE子句
        has_join: 是否有JOIN操作
        has_subquery: 是否有子查询
        where_clause: WHERE子句内容
        is_read_only: 是否为只读操作
        dialect: SQL方言
    """
    original_sql: str
    sql_type: SQLType
    tables: List[str] = field(default_factory=list)
    has_where: bool = False
    has_join: bool = False
    has_subquery: bool = False
    where_clause: Optional[str] = None
    is_read_only: bool = False
    dialect: SQLDialect = SQLDialect.GENERIC
    
    def get_main_table(self) -> Optional[str]:
        """获取主表名"""
        if self.tables:
            return self.tables[0]
        return None
    
    def is_dangerous_without_where(self) -> bool:
        """判断是否是无条件的危险操作"""
        dangerous_types = {SQLType.DELETE, SQLType.UPDATE}
        return self.sql_type in dangerous_types and not self.has_where


class SQLParser:
    """
    SQL解析器
    
    提供健壮的SQL解析功能，不依赖外部库
    
    使用示例：
        parser = SQLParser()
        parsed = parser.parse("SELECT * FROM users WHERE id = 1")
        print(parsed.sql_type)  # SQLType.SELECT
        print(parsed.tables)    # ['users']
        print(parsed.has_where) # True
    """
    
    # SQL关键字
    KEYWORDS = {
        'SELECT', 'INSERT', 'UPDATE', 'DELETE', 'DROP', 'TRUNCATE',
        'ALTER', 'CREATE', 'REPLACE', 'MERGE', 'CALL', 'EXPLAIN',
        'SHOW', 'DESCRIBE', 'DESC', 'FROM', 'WHERE', 'JOIN',
        'INNER', 'OUTER', 'LEFT', 'RIGHT', 'FULL', 'CROSS',
        'ON', 'AND', 'OR', 'NOT', 'NULL', 'TRUE', 'FALSE',
        'ORDER', 'GROUP', 'HAVING', 'LIMIT', 'OFFSET',
        'UNION', 'INTERSECT', 'EXCEPT', 'ALL', 'DISTINCT'
    }
    
    def __init__(self, dialect: SQLDialect = SQLDialect.GENERIC):
        """
        初始化解析器
        
        参数：
            dialect: SQL方言，默认通用
        """
        self.dialect = dialect
        self._init_patterns()
    
    def _init_patterns(self):
        """初始化正则表达式模式"""
        # 注释模式
        self.comment_patterns = [
            re.compile(r'/\*.*?\*/', re.DOTALL),  # /* */ 注释
            re.compile(r'--.*?$', re.MULTILINE),   # -- 注释
            re.compile(r'#.*?$', re.MULTILINE),    # # 注释（MySQL）
        ]
        
        # 字符串模式
        self.string_patterns = [
            re.compile(r"'(?:[^']|'')*'"),         # 单引号字符串
            re.compile(r'"(?:[^"]|"")*"'),         # 双引号字符串
            re.compile(r'`[^`]*`'),                # 反引号标识符（MySQL）
        ]
        
        # 子查询模式
        self.subquery_pattern = re.compile(
            r'\(\s*SELECT\s+',
            re.IGNORECASE
        )
        
        # JOIN模式
        self.join_pattern = re.compile(
            r'\b(INNER|OUTER|LEFT|RIGHT|FULL|CROSS)?\s*JOIN\b',
            re.IGNORECASE
        )
    
    def parse(self, sql: str) -> ParsedSQL:
        """
        解析SQL语句
        
        参数：
            sql: SQL语句
            
        返回：
            ParsedSQL: 解析结果
        """
        if not sql or not sql.strip():
            return ParsedSQL(
                original_sql="",
                sql_type=SQLType.UNKNOWN,
                is_read_only=False
            )
        
        original_sql = sql.strip()
        normalized_sql = self._normalize_sql(original_sql)
        sql_upper = normalized_sql.upper()
        
        # 识别SQL类型
        sql_type = self._identify_sql_type(sql_upper)
        
        # 提取表名
        tables = self._extract_tables(normalized_sql, sql_type)
        
        # 检查WHERE子句
        has_where, where_clause = self._extract_where(normalized_sql)
        
        # 检查JOIN
        has_join = self._has_join(normalized_sql)
        
        # 检查子查询
        has_subquery = self._has_subquery(normalized_sql)
        
        # 判断是否只读
        is_read_only = self._is_read_only(sql_type)
        
        return ParsedSQL(
            original_sql=original_sql,
            sql_type=sql_type,
            tables=tables,
            has_where=has_where,
            has_join=has_join,
            has_subquery=has_subquery,
            where_clause=where_clause,
            is_read_only=is_read_only,
            dialect=self.dialect
        )
    
    def _normalize_sql(self, sql: str) -> str:
        """
        标准化SQL语句
        
        移除注释，但保留字符串
        """
        # 先替换字符串为占位符
        strings = []
        def replace_string(match):
            strings.append(match.group(0))
            return f"__STRING_{len(strings)-1}__"
        
        normalized = sql
        for pattern in self.string_patterns:
            normalized = pattern.sub(replace_string, normalized)
        
        # 移除注释
        for pattern in self.comment_patterns:
            normalized = pattern.sub(' ', normalized)
        
        # 还原字符串
        for i, s in enumerate(strings):
            normalized = normalized.replace(f"__STRING_{i}__", s)
        
        # 规范化空白
        normalized = ' '.join(normalized.split())
        
        return normalized
    
    def _identify_sql_type(self, sql_upper: str) -> SQLType:
        """识别SQL类型"""
        # 按优先级检查
        type_patterns = [
            (r'^\s*SELECT\s+', SQLType.SELECT),
            (r'^\s*INSERT\s+', SQLType.INSERT),
            (r'^\s*UPDATE\s+', SQLType.UPDATE),
            (r'^\s*DELETE\s+', SQLType.DELETE),
            (r'^\s*DROP\s+', SQLType.DROP),
            (r'^\s*TRUNCATE\s+', SQLType.TRUNCATE),
            (r'^\s*ALTER\s+', SQLType.ALTER),
            (r'^\s*CREATE\s+', SQLType.CREATE),
            (r'^\s*REPLACE\s+', SQLType.REPLACE),
            (r'^\s*MERGE\s+', SQLType.MERGE),
            (r'^\s*CALL\s+', SQLType.CALL),
            (r'^\s*EXPLAIN\s+', SQLType.EXPLAIN),
            (r'^\s*SHOW\s+', SQLType.SHOW),
            (r'^\s*DESCRIBE\s+', SQLType.DESCRIBE),
            (r'^\s*DESC\s+', SQLType.DESC),
        ]
        
        for pattern, sql_type in type_patterns:
            if re.match(pattern, sql_upper, re.IGNORECASE):
                return sql_type
        
        return SQLType.UNKNOWN
    
    def _extract_tables(self, sql: str, sql_type: SQLType) -> List[str]:
        """提取表名"""
        tables = []
        sql_upper = sql.upper()
        
        if sql_type == SQLType.SELECT:
            tables = self._extract_select_tables(sql)
        elif sql_type == SQLType.INSERT:
            tables = self._extract_insert_tables(sql)
        elif sql_type == SQLType.UPDATE:
            tables = self._extract_update_tables(sql)
        elif sql_type == SQLType.DELETE:
            tables = self._extract_delete_tables(sql)
        elif sql_type in (SQLType.DROP, SQLType.TRUNCATE, SQLType.ALTER):
            tables = self._extract_ddl_tables(sql, sql_type)
        
        # 去重并保持顺序
        seen = set()
        unique_tables = []
        for t in tables:
            # 清理所有引号和方括号
            t_clean = t.replace('`', '').replace('"', '').replace('[', '').replace(']', '')
            if t_clean and t_clean.upper() not in seen:
                seen.add(t_clean.upper())
                unique_tables.append(t_clean)

        return unique_tables
    
    def _extract_select_tables(self, sql: str) -> List[str]:
        """提取SELECT语句的表名"""
        tables = []

        # 匹配 FROM 子句 - 支持带点的表名如 db.table，支持反引号/方括号包裹的标识符
        from_pattern = re.compile(
            r"\bFROM\s+((?:[`\"\[][^`\"\]]+[`\"\]]|\w+)(?:\.(?:[`\"\[][^`\"\]]+[`\"\]]|\w+))*(?:\s*,\s*(?:[`\"\[][^`\"\]]+[`\"\]]|\w+)(?:\.(?:[`\"\[][^`\"\]]+[`\"\]]|\w+))*)*)",
            re.IGNORECASE
        )

        for match in from_pattern.finditer(sql):
            table_list = match.group(1)
            # 分割多个表
            for table in re.split(r'\s*,\s*', table_list):
                tables.append(table.strip())

        # 匹配 JOIN 子句 - 支持带点的表名
        join_pattern = re.compile(
            r"\b(?:INNER|OUTER|LEFT|RIGHT|FULL|CROSS)?\s*JOIN\s+((?:[`\"\[][^`\"\]]+[`\"\]]|\w+)(?:\.(?:[`\"\[][^`\"\]]+[`\"\]]|\w+))*)",
            re.IGNORECASE
        )

        for match in join_pattern.finditer(sql):
            tables.append(match.group(1).strip())

        return tables

    def _extract_insert_tables(self, sql: str) -> List[str]:
        """提取INSERT语句的表名"""
        pattern = re.compile(
            r"\bINSERT\s+(?:INTO\s+)?((?:[`\"\[][^`\"\]]+[`\"\]]|\w+)(?:\.(?:[`\"\[][^`\"\]]+[`\"\]]|\w+))*)",
            re.IGNORECASE
        )

        match = pattern.search(sql)
        if match:
            return [match.group(1).strip()]
        return []
    
    def _extract_update_tables(self, sql: str) -> List[str]:
        """提取UPDATE语句的表名"""
        pattern = re.compile(
            r"\bUPDATE\s+((?:[`\"\[][^`\"\]]+[`\"\]]|\w+)(?:\.(?:[`\"\[][^`\"\]]+[`\"\]]|\w+))*)",
            re.IGNORECASE
        )

        match = pattern.search(sql)
        if match:
            return [match.group(1).strip()]
        return []
    
    def _extract_delete_tables(self, sql: str) -> List[str]:
        """提取DELETE语句的表名"""
        # DELETE FROM table
        pattern1 = re.compile(
            r"\bDELETE\s+FROM\s+((?:[`\"\[][^`\"\]]+[`\"\]]|\w+)(?:\.(?:[`\"\[][^`\"\]]+[`\"\]]|\w+))*)",
            re.IGNORECASE
        )

        # DELETE table (MySQL语法)
        pattern2 = re.compile(
            r"\bDELETE\s+((?:[`\"\[][^`\"\]]+[`\"\]]|\w+)(?:\.(?:[`\"\[][^`\"\]]+[`\"\]]|\w+))*)\s+(?:FROM|WHERE)",
            re.IGNORECASE
        )

        match = pattern1.search(sql) or pattern2.search(sql)
        if match:
            return [match.group(1).strip()]
        return []
    
    def _extract_ddl_tables(self, sql: str, sql_type: SQLType) -> List[str]:
        """提取DDL语句的表名"""
        type_str = sql_type.value
        pattern = re.compile(
            rf"\b{type_str}\s+(?:TABLE\s+)?((?:[`\"\[][^`\"\]]+[`\"\]]|\w+)(?:\.(?:[`\"\[][^`\"\]]+[`\"\]]|\w+))*)",
            re.IGNORECASE
        )

        match = pattern.search(sql)
        if match:
            return [match.group(1).strip()]
        return []
    
    def _extract_where(self, sql: str) -> tuple:
        """提取WHERE子句"""
        pattern = re.compile(
            r'\bWHERE\b(.+?)(?:\bORDER\s+BY\b|\bGROUP\s+BY\b|\bHAVING\b|\bLIMIT\b|\bUNION\b|$)',
            re.IGNORECASE
        )
        
        match = pattern.search(sql)
        if match:
            where_clause = match.group(1).strip()
            # 检查WHERE子句是否有效（不只是空白或1=1）
            if where_clause and not re.match(r'^\s*(1\s*=\s*1|TRUE)\s*$', where_clause, re.IGNORECASE):
                return True, where_clause
        
        return False, None
    
    def _has_join(self, sql: str) -> bool:
        """检查是否有JOIN"""
        return bool(self.join_pattern.search(sql))
    
    def _has_subquery(self, sql: str) -> bool:
        """检查是否有子查询"""
        return bool(self.subquery_pattern.search(sql))
    
    def _is_read_only(self, sql_type: SQLType) -> bool:
        """判断是否为只读操作"""
        read_only_types = {
            SQLType.SELECT,
            SQLType.EXPLAIN,
            SQLType.SHOW,
            SQLType.DESCRIBE,
            SQLType.DESC
        }
        return sql_type in read_only_types
    
    def validate_syntax(self, sql: str) -> tuple:
        """
        简单语法验证
        
        返回：
            (is_valid: bool, error_message: Optional[str])
        """
        if not sql or not sql.strip():
            return False, "SQL语句不能为空"
        
        sql_clean = sql.strip()
        
        # 检查基本语法错误
        open_parens = sql_clean.count('(')
        close_parens = sql_clean.count(')')
        if open_parens != close_parens:
            return False, f"括号不匹配: 左括号{open_parens}个，右括号{close_parens}个"
        
        open_brackets = sql_clean.count('[')
        close_brackets = sql_clean.count(']')
        if open_brackets != close_brackets:
            return False, f"方括号不匹配"
        
        # 检查是否有SQL类型
        parsed = self.parse(sql)
        if parsed.sql_type == SQLType.UNKNOWN:
            return False, "无法识别SQL类型"
        
        return True, None


# 全局解析器实例
_default_parser = SQLParser()


def parse_sql(sql: str, dialect: SQLDialect = SQLDialect.GENERIC) -> ParsedSQL:
    """
    解析SQL的便捷函数
    
    参数：
        sql: SQL语句
        dialect: SQL方言
        
    返回：
        ParsedSQL: 解析结果
    """
    parser = SQLParser(dialect)
    return parser.parse(sql)


def is_read_only(sql: str) -> bool:
    """
    检查SQL是否为只读操作的便捷函数
    
    参数：
        sql: SQL语句
        
    返回：
        bool: 是否为只读操作
    """
    parsed = _default_parser.parse(sql)
    return parsed.is_read_only


def is_dangerous_without_where(sql: str) -> bool:
    """
    检查SQL是否为无条件的危险操作
    
    参数：
        sql: SQL语句
        
    返回：
        bool: 是否为危险操作
    """
    parsed = _default_parser.parse(sql)
    return parsed.is_dangerous_without_where()


# 导出公共接口
__all__ = [
    "SQLType",
    "SQLDialect",
    "ParsedSQL",
    "SQLParser",
    "parse_sql",
    "is_read_only",
    "is_dangerous_without_where",
]
