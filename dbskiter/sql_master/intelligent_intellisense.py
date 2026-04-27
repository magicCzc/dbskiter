"""
智能 SQL 提示 - 基于语义理解

文件功能：
1. 语义理解 - 理解 SQL 上下文和意图
2. 智能补全 - 基于上下文的智能建议
3. 错误预防 - 提前发现潜在问题
4. 最佳实践 - 推荐优化写法

作者：Trae AI
创建时间：2026-04-17
"""

import re
from typing import Dict, List, Any, Optional, Tuple, Set
from dataclasses import dataclass
from enum import Enum


class SuggestionType(Enum):
    """建议类型"""
    COMPLETION = "completion"       # 补全
    CORRECTION = "correction"       # 纠正
    OPTIMIZATION = "optimization"   # 优化
    BEST_PRACTICE = "best_practice" # 最佳实践
    WARNING = "warning"             # 警告


class SQLContext(Enum):
    """SQL 上下文"""
    SELECT = "select"
    FROM = "from"
    WHERE = "where"
    JOIN = "join"
    GROUP_BY = "group_by"
    ORDER_BY = "order_by"
    INSERT = "insert"
    UPDATE = "update"
    DELETE = "delete"
    CREATE = "create"
    UNKNOWN = "unknown"


@dataclass
class SemanticSuggestion:
    """语义建议"""
    type: SuggestionType
    text: str
    description: str
    reason: str  # 为什么给出这个建议
    confidence: float  # 置信度
    priority: int  # 优先级（1-10，数字越小越优先）
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        # 将 SuggestionType 映射为中文类型名
        type_mapping = {
            "completion": "补全",
            "correction": "纠正",
            "optimization": "优化",
            "best_practice": "最佳实践",
            "warning": "警告"
        }
        type_name = type_mapping.get(self.type.value, "其他")
        
        return {
            "type": type_name,
            "text": self.text,
            "description": self.description,
            "reason": self.reason,
            "confidence": self.confidence,
            "priority": self.priority
        }


@dataclass
class SQLParseResult:
    """SQL 解析结果"""
    context: SQLContext
    tables: List[str]
    columns: List[str]
    aliases: Dict[str, str]  # 别名映射
    where_conditions: List[str]
    join_conditions: List[str]
    is_complete: bool  # SQL 是否完整
    potential_issues: List[str]


class SQLIntelliSense:
    """
    智能 SQL 提示
    
    不同于简单前缀匹配，这个提示器会：
    1. 理解 SQL 语义上下文
    2. 基于表关系智能推荐 JOIN
    3. 检测潜在问题（如 SELECT *）
    4. 推荐最佳实践
    
    使用示例：
        sense = IntelligentSQLIntelliSense(schema_cache)
        
        # 简单补全
        suggestions = sense.get_suggestions('SELECT * FROM ZABB', cursor_pos=18)
        
        # 语义分析
        analysis = sense.analyze_sql('SELECT * FROM users WHERE id = 1')
        # 返回: 建议使用具体列名而不是 *
    """
    
    SQL_KEYWORDS = [
        'SELECT', 'FROM', 'WHERE', 'AND', 'OR', 'NOT', 'NULL',
        'INSERT', 'INTO', 'VALUES', 'UPDATE', 'SET', 'DELETE',
        'CREATE', 'TABLE', 'INDEX', 'DROP', 'ALTER',
        'JOIN', 'LEFT', 'RIGHT', 'INNER', 'OUTER', 'ON', 'CROSS',
        'GROUP', 'BY', 'ORDER', 'ASC', 'DESC',
        'LIMIT', 'OFFSET', 'HAVING', 'UNION', 'ALL', 'DISTINCT',
        'COUNT', 'SUM', 'AVG', 'MAX', 'MIN',
        'AS', 'BETWEEN', 'LIKE', 'IN', 'EXISTS', 'IS',
        'CASE', 'WHEN', 'THEN', 'ELSE', 'END'
    ]
    
    # 常见 SQL 反模式
    ANTI_PATTERNS = {
        r'SELECT\s+\*': {
            'issue': '使用 SELECT * 会影响性能',
            'suggestion': '建议明确指定需要的列名',
            'severity': 'warning'
        },
        r'WHERE\s+\w+\s*=\s*NULL': {
            'issue': '使用 = NULL 永远不会匹配',
            'suggestion': '应该使用 IS NULL',
            'severity': 'error'
        },
        r'ORDER\s+BY\s+RAND\s*\(': {
            'issue': 'ORDER BY RAND() 性能极差',
            'suggestion': '考虑使用其他随机化方法',
            'severity': 'warning'
        },
        r'INSERT\s+INTO\s+\w+\s+VALUES': {
            'issue': '未指定列名的 INSERT 容易出错',
            'suggestion': '建议明确指定列名: INSERT INTO table (col1, col2) VALUES',
            'severity': 'warning'
        }
    }
    
    def __init__(self, schema_cache):
        """
        初始化智能 SQL 提示
        
        参数：
            schema_cache: Schema 缓存实例
        """
        self.schema_cache = schema_cache
        self._table_relationships: Dict[str, List[str]] = {}
    
    def analyze_sql(self, sql: str) -> SQLParseResult:
        """
        深度分析 SQL
        
        参数：
            sql: SQL 语句
            
        返回：
            SQL 解析结果
        """
        sql_upper = sql.upper().strip()
        
        # 1. 识别上下文
        context = self._detect_context(sql_upper)
        
        # 2. 提取表名
        tables = self._extract_tables(sql_upper)
        
        # 3. 提取列名
        columns = self._extract_columns(sql_upper)
        
        # 4. 提取别名
        aliases = self._extract_aliases(sql_upper)
        
        # 5. 提取 WHERE 条件
        where_conditions = self._extract_where_conditions(sql_upper)
        
        # 6. 检测潜在问题
        potential_issues = self._detect_issues(sql)
        
        # 7. 检查 SQL 完整性
        is_complete = self._check_completeness(sql_upper, context)
        
        return SQLParseResult(
            context=context,
            tables=tables,
            columns=columns,
            aliases=aliases,
            where_conditions=where_conditions,
            join_conditions=[],
            is_complete=is_complete,
            potential_issues=potential_issues
        )
    
    def get_suggestions(
        self,
        sql: str,
        cursor_pos: int,
        context: Optional[Dict] = None
    ) -> List[SemanticSuggestion]:
        """
        获取智能建议
        
        参数：
            sql: 当前 SQL 语句
            cursor_pos: 光标位置
            context: 上下文信息
            
        返回：
            语义建议列表
        """
        suggestions = []
        
        # 1. 分析当前 SQL
        parse_result = self.analyze_sql(sql[:cursor_pos])
        
        # 2. 检测反模式
        anti_pattern_suggestions = self._check_anti_patterns(sql)
        suggestions.extend(anti_pattern_suggestions)
        
        # 3. 基于上下文提供建议
        context_suggestions = self._get_context_suggestions(parse_result, sql, cursor_pos)
        suggestions.extend(context_suggestions)
        
        # 4. 提供最佳实践建议
        best_practice_suggestions = self._get_best_practice_suggestions(parse_result)
        suggestions.extend(best_practice_suggestions)
        
        # 5. 按优先级排序
        suggestions.sort(key=lambda x: (x.priority, -x.confidence))
        
        return suggestions
    
    def _detect_context(self, sql_upper: str) -> SQLContext:
        """检测 SQL 上下文"""
        if sql_upper.startswith('SELECT'):
            if ' WHERE ' in sql_upper:
                return SQLContext.WHERE
            elif ' FROM ' in sql_upper:
                if ' JOIN ' in sql_upper:
                    return SQLContext.JOIN
                return SQLContext.FROM
            elif ' GROUP ' in sql_upper:
                return SQLContext.GROUP_BY
            elif ' ORDER ' in sql_upper:
                return SQLContext.ORDER_BY
            return SQLContext.SELECT
        elif sql_upper.startswith('INSERT'):
            return SQLContext.INSERT
        elif sql_upper.startswith('UPDATE'):
            return SQLContext.UPDATE
        elif sql_upper.startswith('DELETE'):
            return SQLContext.DELETE
        elif sql_upper.startswith('CREATE'):
            return SQLContext.CREATE
        
        return SQLContext.UNKNOWN
    
    def _extract_tables(self, sql_upper: str) -> List[str]:
        """提取表名"""
        tables = []
        
        # FROM 子句
        from_match = re.findall(r'FROM\s+(\w+)', sql_upper)
        tables.extend(from_match)
        
        # JOIN 子句
        join_match = re.findall(r'JOIN\s+(\w+)', sql_upper)
        tables.extend(join_match)
        
        # INTO 子句 (INSERT)
        into_match = re.findall(r'INTO\s+(\w+)', sql_upper)
        tables.extend(into_match)
        
        return list(set(tables))
    
    def _extract_columns(self, sql_upper: str) -> List[str]:
        """提取列名"""
        columns = []
        
        # SELECT 列
        select_match = re.search(r'SELECT\s+(.+?)\s+FROM', sql_upper, re.DOTALL)
        if select_match:
            cols = select_match.group(1)
            # 分割列名
            col_list = [c.strip() for c in cols.split(',')]
            for col in col_list:
                # 去除别名
                col = col.split()[-1]
                # 去除表名前缀
                if '.' in col:
                    col = col.split('.')[-1]
                if col != '*':
                    columns.append(col)
        
        # WHERE 条件中的列
        where_match = re.findall(r'WHERE\s+(\w+)', sql_upper)
        columns.extend(where_match)
        
        return list(set(columns))
    
    def _extract_aliases(self, sql_upper: str) -> Dict[str, str]:
        """提取表别名"""
        aliases = {}
        
        # 匹配 "table_name alias" 或 "table_name AS alias"
        pattern = r'(\w+)\s+(?:AS\s+)?(\w+)(?:\s+|$)'
        matches = re.findall(pattern, sql_upper)
        
        for table, alias in matches:
            # 如果 alias 是 SQL 关键字，可能不是别名
            if alias not in self.SQL_KEYWORDS:
                aliases[alias] = table
        
        return aliases
    
    def _extract_where_conditions(self, sql_upper: str) -> List[str]:
        """提取 WHERE 条件"""
        conditions = []
        
        where_match = re.search(r'WHERE\s+(.+?)(?:\s+ORDER|\s+GROUP|\s+LIMIT|$)', 
                                sql_upper, re.DOTALL)
        if where_match:
            where_clause = where_match.group(1)
            # 简单分割 AND/OR
            for cond in re.split(r'\s+AND\s+|\s+OR\s+', where_clause):
                conditions.append(cond.strip())
        
        return conditions
    
    def _detect_issues(self, sql: str) -> List[str]:
        """检测潜在问题"""
        issues = []
        sql_upper = sql.upper()
        
        for pattern, info in self.ANTI_PATTERNS.items():
            if re.search(pattern, sql_upper):
                issues.append(f"[{info['severity'].upper()}] {info['issue']}")
        
        return issues
    
    def _check_completeness(self, sql_upper: str, context: SQLContext) -> bool:
        """检查 SQL 完整性"""
        if context == SQLContext.SELECT:
            return 'FROM' in sql_upper
        elif context == SQLContext.INSERT:
            return 'VALUES' in sql_upper or 'SELECT' in sql_upper
        elif context == SQLContext.UPDATE:
            return 'SET' in sql_upper
        elif context == SQLContext.DELETE:
            return 'FROM' in sql_upper
        
        return True
    
    def _check_anti_patterns(self, sql: str) -> List[SemanticSuggestion]:
        """检查 SQL 反模式"""
        suggestions = []
        sql_upper = sql.upper()
        
        for pattern, info in self.ANTI_PATTERNS.items():
            if re.search(pattern, sql_upper):
                suggestion_type = SuggestionType.WARNING if info['severity'] == 'warning' else SuggestionType.CORRECTION
                priority = 1 if info['severity'] == 'error' else 3
                
                suggestions.append(SemanticSuggestion(
                    type=suggestion_type,
                    text=info['suggestion'],
                    description=info['issue'],
                    reason=f"检测到 {info['severity']} 级问题",
                    confidence=0.95,
                    priority=priority
                ))
        
        return suggestions
    
    def _get_context_suggestions(
        self,
        parse_result: SQLParseResult,
        sql: str,
        cursor_pos: int
    ) -> List[SemanticSuggestion]:
        """基于上下文获取建议"""
        suggestions = []
        
        # 获取光标前的文本
        before_cursor = sql[:cursor_pos].upper()
        
        # 1. 如果在 FROM 后，推荐表名
        if before_cursor.rstrip().endswith('FROM'):
            tables = self.schema_cache.get_tables()
            for table in tables[:5]:
                suggestions.append(SemanticSuggestion(
                    type=SuggestionType.COMPLETION,
                    text=table,
                    description='数据库表',
                    reason='FROM 子句后应该跟表名',
                    confidence=0.9,
                    priority=2
                ))
        
        # 2. 如果在 JOIN 后，推荐相关表
        elif ' JOIN ' in before_cursor and not re.search(r'JOIN\s+\w+\s+ON', before_cursor):
            # 基于已有表推荐 JOIN 表
            if parse_result.tables:
                current_table = parse_result.tables[-1]
                related_tables = self._get_related_tables(current_table)
                
                for related_table in related_tables[:3]:
                    suggestions.append(SemanticSuggestion(
                        type=SuggestionType.COMPLETION,
                        text=f'{related_table} ON ',
                        description=f'与 {current_table} 关联的表',
                        reason='基于表关系推荐 JOIN',
                        confidence=0.8,
                        priority=2
                    ))
        
        # 3. 如果在 SELECT 后且是 *，推荐具体列
        elif 'SELECT *' in before_cursor:
            if parse_result.tables:
                table = parse_result.tables[0]
                columns = self.schema_cache.get_columns(table)
                
                if columns:
                    col_list = ', '.join(columns[:5])
                    suggestions.append(SemanticSuggestion(
                        type=SuggestionType.OPTIMIZATION,
                        text=f'SELECT {col_list}',
                        description=f'明确指定列名，而不是使用 *',
                        reason='减少数据传输，提高性能',
                        confidence=0.85,
                        priority=3
                    ))
        
        return suggestions
    
    def _get_best_practice_suggestions(
        self,
        parse_result: SQLParseResult
    ) -> List[SemanticSuggestion]:
        """获取最佳实践建议"""
        suggestions = []
        
        # 1. 如果没有 WHERE 的 DELETE/UPDATE，警告
        if parse_result.context in [SQLContext.DELETE, SQLContext.UPDATE]:
            if not parse_result.where_conditions:
                suggestions.append(SemanticSuggestion(
                    type=SuggestionType.WARNING,
                    text='添加 WHERE 条件',
                    description='没有 WHERE 的 DELETE/UPDATE 会影响所有行',
                    reason='防止误操作',
                    confidence=0.95,
                    priority=1
                ))
        
        # 2. 如果有多表 JOIN，建议检查索引
        if len(parse_result.tables) >= 3:
            suggestions.append(SemanticSuggestion(
                type=SuggestionType.BEST_PRACTICE,
                text='检查 JOIN 字段索引',
                description='多表 JOIN 需要确保关联字段有索引',
                reason='避免全表扫描，提高 JOIN 性能',
                confidence=0.8,
                priority=4
            ))
        
        # 3. 如果查询大表，建议加 LIMIT
        if parse_result.tables:
            for table in parse_result.tables:
                table_info = self.schema_cache.get_table_info(table)
                if table_info and table_info.row_count > 10000:
                    if 'LIMIT' not in str(parse_result.where_conditions):
                        suggestions.append(SemanticSuggestion(
                            type=SuggestionType.BEST_PRACTICE,
                            text='添加 LIMIT 限制',
                            description=f'{table} 是大表（{table_info.row_count} 行）',
                            reason='防止返回过多数据',
                            confidence=0.75,
                            priority=5
                        ))
                        break
        
        return suggestions
    
    def _get_related_tables(self, table_name: str) -> List[str]:
        """获取相关表（基于外键关系）"""
        # 简化实现：返回其他表
        all_tables = self.schema_cache.get_tables()
        return [t for t in all_tables if t != table_name][:5]
    
    def format_suggestions(
        self,
        suggestions: List[SemanticSuggestion],
        max_count: int = 10
    ) -> str:
        """
        格式化建议输出
        
        参数：
            suggestions: 建议列表
            max_count: 最大显示数量
            
        返回：
            格式化字符串
        """
        if not suggestions:
            return "暂无建议"
        
        lines = ["智能 SQL 建议:", "=" * 50]
        
        for i, sug in enumerate(suggestions[:max_count], 1):
            icon = {
                SuggestionType.COMPLETION: "[+]",
                SuggestionType.CORRECTION: "[!]",
                SuggestionType.OPTIMIZATION: "[*]",
                SuggestionType.BEST_PRACTICE: "[^]",
                SuggestionType.WARNING: "[?]"
            }.get(sug.type, "[?]")
            
            lines.append(f"\n{i}. {icon} [{sug.type.value}] {sug.text}")
            lines.append(f"   描述: {sug.description}")
            lines.append(f"   原因: {sug.reason}")
            lines.append(f"   置信度: {sug.confidence:.0%}")
        
        return "\n".join(lines)


# 向后兼容
SQLIntelliSenseV2 = SQLIntelliSense
