"""
sql_master/schema_aware.py
Schema 感知模块 - 智能 SQL 辅助功能

功能：
1. Schema 缓存 - 缓存表结构信息，加速查询
2. 智能提示 - 表名/字段名补全
3. SQL 限制 - 防止大查询，自动加 LIMIT
4. 结果解释 - 生成自然语言摘要

作者：Magiczc
创建时间：2026-04-17
"""

import logging
import re
import time
from typing import Dict, List, Any, Optional, Tuple, Set
from dataclasses import dataclass, field
from collections import defaultdict

logger = logging.getLogger(__name__)


@dataclass
class ColumnInfo:
    """列信息"""
    name: str
    data_type: str
    is_nullable: bool = True
    default_value: Any = None
    is_primary_key: bool = False
    is_foreign_key: bool = False
    comment: str = ""
    max_length: Optional[int] = None


@dataclass
class TableInfo:
    """表信息"""
    name: str
    columns: Dict[str, ColumnInfo] = field(default_factory=dict)
    primary_key: List[str] = field(default_factory=list)
    indexes: List[Dict[str, Any]] = field(default_factory=list)
    row_count: int = 0
    size_mb: float = 0.0
    comment: str = ""
    last_updated: float = field(default_factory=time.time)


@dataclass
class SQLSuggestion:
    """SQL 建议"""
    type: str  # 'completion', 'correction', 'optimization'
    text: str
    description: str
    confidence: float = 1.0


class SchemaCache:
    """
    Schema 缓存管理器
    
    功能：
    1. 缓存数据库 Schema 信息
    2. 支持定时刷新
    3. 前缀树索引加速查询
    
    使用示例：
        cache = SchemaCache(connector)
        cache.refresh()  # 刷新缓存
        tables = cache.get_tables()  # 获取所有表
        columns = cache.get_columns('users')  # 获取表字段
    """
    
    def __init__(self, connector, cache_ttl: int = 300):
        """
        初始化 Schema 缓存
        
        参数：
            connector: 数据库连接器
            cache_ttl: 缓存有效期（秒），默认 5 分钟
        """
        self.connector = connector
        self.cache_ttl = cache_ttl
        self._tables: Dict[str, TableInfo] = {}
        self._last_refresh = 0
        self._prefix_index: Dict[str, Set[str]] = defaultdict(set)
        self.dialect = connector.dialect.lower() if hasattr(connector, 'dialect') else 'mysql'
    
    def refresh(self, force: bool = False) -> bool:
        """
        刷新 Schema 缓存
        
        参数：
            force: 是否强制刷新，忽略缓存有效期
            
        返回：
            bool: 是否成功刷新
        """
        now = time.time()
        
        # 检查是否需要刷新
        if not force and now - self._last_refresh < self.cache_ttl:
            return False
        
        try:
            self._load_schema()
            self._last_refresh = now
            return True
        except Exception as e:
            logger.error(f"Schema 刷新失败: {e}")
            return False
    
    def _load_schema(self):
        """加载 Schema 信息"""
        self._tables = {}
        self._prefix_index = defaultdict(set)

        if 'oracle' in self.dialect:
            self._load_oracle_schema()
            return

        self._load_mysql_schema()

    def _load_mysql_schema(self):
        """加载MySQL Schema信息"""
        # 获取所有表
        tables_result = self.connector.execute("""
            SELECT 
                TABLE_NAME,
                TABLE_COMMENT,
                TABLE_ROWS,
                ROUND((DATA_LENGTH + INDEX_LENGTH) / 1024 / 1024, 2) as size_mb
            FROM information_schema.TABLES
            WHERE TABLE_SCHEMA = DATABASE()
        """)
        
        for row in tables_result.rows:
            table_name, comment, row_count, size_mb = row
            
            table_info = TableInfo(
                name=table_name,
                comment=comment or "",
                row_count=row_count or 0,
                size_mb=size_mb or 0.0
            )
            
            # 获取列信息
            self._load_columns(table_info)
            
            # 获取索引信息
            self._load_indexes(table_info)
            
            self._tables[table_name] = table_info
            
            # 构建前缀索引
            self._add_to_prefix_index(table_name)
            for col_name in table_info.columns:
                self._add_to_prefix_index(col_name)
    
    def _load_columns(self, table_info: TableInfo):
        """加载表的列信息"""
        if 'oracle' in self.dialect:
            self._load_oracle_columns(table_info)
            return

        result = self.connector.execute(f"""
            SELECT 
                COLUMN_NAME,
                DATA_TYPE,
                IS_NULLABLE,
                COLUMN_DEFAULT,
                COLUMN_COMMENT,
                CHARACTER_MAXIMUM_LENGTH
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
            AND TABLE_NAME = '{table_info.name}'
            ORDER BY ORDINAL_POSITION
        """)
        
        for row in result.rows:
            col_name, data_type, is_nullable, default, comment, max_len = row
            
            column = ColumnInfo(
                name=col_name,
                data_type=data_type,
                is_nullable=is_nullable == 'YES',
                default_value=default,
                comment=comment or "",
                max_length=max_len
            )
            
            table_info.columns[col_name] = column
        
        # 获取主键信息
        pk_result = self.connector.execute(f"""
            SELECT COLUMN_NAME
            FROM information_schema.KEY_COLUMN_USAGE
            WHERE TABLE_SCHEMA = DATABASE()
            AND TABLE_NAME = '{table_info.name}'
            AND CONSTRAINT_NAME = 'PRIMARY'
            ORDER BY ORDINAL_POSITION
        """)
        
        table_info.primary_key = [row[0] for row in pk_result.rows]
        
        # 标记主键列
        for pk_col in table_info.primary_key:
            if pk_col in table_info.columns:
                table_info.columns[pk_col].is_primary_key = True
    
    def _load_indexes(self, table_info: TableInfo):
        """加载表的索引信息"""
        if 'oracle' in self.dialect:
            self._load_oracle_indexes(table_info)
            return

        result = self.connector.execute(f"""
            SELECT 
                INDEX_NAME,
                COLUMN_NAME,
                NON_UNIQUE
            FROM information_schema.STATISTICS
            WHERE TABLE_SCHEMA = DATABASE()
            AND TABLE_NAME = '{table_info.name}'
            ORDER BY INDEX_NAME, SEQ_IN_INDEX
        """)
        
        indexes = defaultdict(lambda: {'columns': [], 'unique': False})
        
        for row in result.rows:
            idx_name, col_name, non_unique = row
            indexes[idx_name]['columns'].append(col_name)
            indexes[idx_name]['unique'] = (non_unique == 0)
        
        table_info.indexes = [
            {
                'name': name,
                'columns': info['columns'],
                'unique': info['unique']
            }
            for name, info in indexes.items()
        ]

    def _load_oracle_schema(self):
        """加载Oracle Schema信息（批量查询优化）"""
        tables_result = self.connector.execute("""
            SELECT
                t.TABLE_NAME,
                c.COMMENTS,
                NVL(t.NUM_ROWS, 0),
                ROUND(NVL(s.BYTES, 0) / 1024 / 1024, 2)
            FROM USER_TABLES t
            LEFT JOIN USER_TAB_COMMENTS c ON t.TABLE_NAME = c.TABLE_NAME
            LEFT JOIN USER_SEGMENTS s ON t.TABLE_NAME = s.SEGMENT_NAME AND s.SEGMENT_TYPE = 'TABLE'
            ORDER BY t.TABLE_NAME
        """)

        # 批量预加载所有列信息
        all_columns = defaultdict(list)
        try:
            col_result = self.connector.execute("""
                SELECT
                    TABLE_NAME, COLUMN_NAME, DATA_TYPE,
                    NULLABLE, DATA_DEFAULT, CHAR_LENGTH
                FROM USER_TAB_COLUMNS
                ORDER BY TABLE_NAME, COLUMN_ID
            """)
            for row in col_result.rows:
                tbl = str(row[0])
                all_columns[tbl].append(row)
        except Exception:
            pass

        # 批量预加载主键
        all_pks = defaultdict(list)
        try:
            pk_result = self.connector.execute("""
                SELECT cc.TABLE_NAME, cc.COLUMN_NAME
                FROM USER_CONSTRAINTS c
                JOIN USER_CONS_COLUMNS cc ON c.CONSTRAINT_NAME = cc.CONSTRAINT_NAME
                WHERE c.CONSTRAINT_TYPE = 'P'
                ORDER BY cc.TABLE_NAME, cc.POSITION
            """)
            for row in pk_result.rows:
                all_pks[str(row[0])].append(str(row[1]))
        except Exception:
            pass

        # 批量预加载索引
        all_indexes = defaultdict(lambda: defaultdict(lambda: {'columns': [], 'unique': False}))
        try:
            idx_result = self.connector.execute("""
                SELECT
                    i.TABLE_NAME, i.INDEX_NAME,
                    ic.COLUMN_NAME, i.UNIQUENESS
                FROM USER_INDEXES i
                JOIN USER_IND_COLUMNS ic ON i.INDEX_NAME = ic.INDEX_NAME
                ORDER BY i.TABLE_NAME, i.INDEX_NAME, ic.COLUMN_POSITION
            """)
            for row in idx_result.rows:
                tbl = str(row[0])
                idx_name = str(row[1])
                col_name = str(row[2])
                uniqueness = str(row[3])
                all_indexes[tbl][idx_name]['columns'].append(col_name)
                all_indexes[tbl][idx_name]['unique'] = (uniqueness == 'UNIQUE')
        except Exception:
            pass

        # 组装到各表
        for row in tables_result.rows:
            table_name = str(row[0])
            comment = str(row[1]) if row[1] else ""
            row_count = int(str(row[2])) if row[2] else 0
            size_mb = float(str(row[3])) if row[3] else 0.0

            table_info = TableInfo(
                name=table_name,
                comment=comment,
                row_count=row_count,
                size_mb=size_mb
            )

            # 从预加载数据中分配列
            for col_row in all_columns.get(table_name, []):
                col_name = str(col_row[1])
                data_type = str(col_row[2])
                is_nullable = str(col_row[3]) == 'Y'
                default = col_row[4]
                max_len = col_row[5]

                column = ColumnInfo(
                    name=col_name,
                    data_type=data_type,
                    is_nullable=is_nullable,
                    default_value=str(default) if default else None,
                    comment="",
                    max_length=int(str(max_len)) if max_len else None
                )
                table_info.columns[col_name] = column

            # 分配主键
            table_info.primary_key = all_pks.get(table_name, [])
            for pk_col in table_info.primary_key:
                if pk_col in table_info.columns:
                    table_info.columns[pk_col].is_primary_key = True

            # 分配索引
            tbl_indexes = all_indexes.get(table_name, {})
            table_info.indexes = [
                {
                    'name': name,
                    'columns': info['columns'],
                    'unique': info['unique']
                }
                for name, info in tbl_indexes.items()
            ]

            self._tables[table_name] = table_info

            self._add_to_prefix_index(table_name)
            for col_name in table_info.columns:
                self._add_to_prefix_index(col_name)

    def _load_oracle_columns(self, table_info: TableInfo):
        """加载Oracle表的列信息"""
        result = self.connector.execute(f"""
            SELECT
                COLUMN_NAME,
                DATA_TYPE,
                NULLABLE,
                DATA_DEFAULT,
                CHAR_LENGTH
            FROM USER_TAB_COLUMNS
            WHERE TABLE_NAME = '{table_info.name}'
            ORDER BY COLUMN_ID
        """)

        for row in result.rows:
            col_name = str(row[0])
            data_type = str(row[1])
            is_nullable = str(row[2]) == 'Y'
            default = row[3]
            max_len = row[4]

            column = ColumnInfo(
                name=col_name,
                data_type=data_type,
                is_nullable=is_nullable,
                default_value=str(default) if default else None,
                comment="",
                max_length=int(str(max_len)) if max_len else None
            )

            table_info.columns[col_name] = column

        # 获取主键
        try:
            pk_result = self.connector.execute(f"""
                SELECT cc.COLUMN_NAME
                FROM USER_CONSTRAINTS c
                JOIN USER_CONS_COLUMNS cc ON c.CONSTRAINT_NAME = cc.CONSTRAINT_NAME
                WHERE c.TABLE_NAME = '{table_info.name}'
                AND c.CONSTRAINT_TYPE = 'P'
                ORDER BY cc.POSITION
            """)
            table_info.primary_key = [str(row[0]) for row in pk_result.rows]
            for pk_col in table_info.primary_key:
                if pk_col in table_info.columns:
                    table_info.columns[pk_col].is_primary_key = True
        except Exception:
            table_info.primary_key = []

    def _load_oracle_indexes(self, table_info: TableInfo):
        """加载Oracle表的索引信息"""
        try:
            result = self.connector.execute(f"""
                SELECT
                    i.INDEX_NAME,
                    ic.COLUMN_NAME,
                    i.UNIQUENESS
                FROM USER_INDEXES i
                JOIN USER_IND_COLUMNS ic ON i.INDEX_NAME = ic.INDEX_NAME
                WHERE i.TABLE_NAME = '{table_info.name}'
                ORDER BY i.INDEX_NAME, ic.COLUMN_POSITION
            """)

            indexes = defaultdict(lambda: {'columns': [], 'unique': False})
            for row in result.rows:
                idx_name = str(row[0])
                col_name = str(row[1])
                uniqueness = str(row[2])
                indexes[idx_name]['columns'].append(col_name)
                indexes[idx_name]['unique'] = (uniqueness == 'UNIQUE')

            table_info.indexes = [
                {
                    'name': name,
                    'columns': info['columns'],
                    'unique': info['unique']
                }
                for name, info in indexes.items()
            ]
        except Exception:
            table_info.indexes = []
    
    def _add_to_prefix_index(self, text: str):
        """添加到前缀索引"""
        text_lower = text.lower()
        for i in range(1, len(text_lower) + 1):
            prefix = text_lower[:i]
            self._prefix_index[prefix].add(text)
    
    def get_tables(self) -> List[str]:
        """获取所有表名"""
        self.refresh()
        return list(self._tables.keys())
    
    def get_table_info(self, table_name: str) -> Optional[TableInfo]:
        """获取表信息"""
        refreshed = self.refresh()
        if not refreshed and not self._tables:
            # 刷新失败且没有缓存数据
            raise Exception("Schema 缓存刷新失败，无法获取表信息")
        return self._tables.get(table_name)
    
    def get_columns(self, table_name: str) -> List[str]:
        """获取表的列名列表"""
        table = self.get_table_info(table_name)
        if table:
            return list(table.columns.keys())
        return []
    
    def get_column_info(self, table_name: str, column_name: str) -> Optional[ColumnInfo]:
        """获取列信息"""
        table = self.get_table_info(table_name)
        if table:
            return table.columns.get(column_name)
        return None
    
    def search_tables(self, prefix: str) -> List[str]:
        """根据前缀搜索表名"""
        self.refresh()
        prefix_lower = prefix.lower()
        matches = self._prefix_index.get(prefix_lower, set())
        return [t for t in matches if t in self._tables]
    
    def search_columns(self, prefix: str, table_name: Optional[str] = None) -> List[Tuple[str, str]]:
        """
        根据前缀搜索列名
        
        参数：
            prefix: 前缀
            table_name: 指定表名，None 则搜索所有表
            
        返回：
            List[(table, column)]: 匹配的表和列
        """
        self.refresh()
        prefix_lower = prefix.lower()
        matches = self._prefix_index.get(prefix_lower, set())
        
        results = []
        for match in matches:
            if table_name and match != table_name and match not in self._tables.get(table_name, TableInfo(name='')).columns:
                continue
            
            if match in self._tables:
                # 匹配到表名，返回该表的所有列
                if not table_name or match == table_name:
                    for col in self._tables[match].columns:
                        results.append((match, col))
            else:
                # 匹配到列名，找到包含该列的表
                for t_name, t_info in self._tables.items():
                    if match in t_info.columns:
                        if not table_name or t_name == table_name:
                            results.append((t_name, match))
        
        return list(set(results))


class SQLIntelliSense:
    """
    SQL 智能提示
    
    功能：
    1. 表名补全
    2. 字段名补全
    3. SQL 关键字补全
    4. 语法错误提示
    
    使用示例：
        sense = SQLIntelliSense(schema_cache)
        suggestions = sense.get_suggestions('SELECT * FROM ZABB', cursor_pos=18)
        # 返回: ['ZABBIX', 'ZABBIX_TEST']
    """
    
    SQL_KEYWORDS = [
        'SELECT', 'FROM', 'WHERE', 'AND', 'OR', 'NOT', 'NULL',
        'INSERT', 'INTO', 'VALUES', 'UPDATE', 'SET', 'DELETE',
        'CREATE', 'TABLE', 'INDEX', 'DROP', 'ALTER',
        'JOIN', 'LEFT', 'RIGHT', 'INNER', 'OUTER', 'ON',
        'GROUP', 'BY', 'ORDER', 'ASC', 'DESC',
        'LIMIT', 'OFFSET', 'HAVING', 'UNION', 'ALL',
        'COUNT', 'SUM', 'AVG', 'MAX', 'MIN',
        'AS', 'DISTINCT', 'BETWEEN', 'LIKE', 'IN', 'EXISTS'
    ]
    
    def __init__(self, schema_cache: SchemaCache):
        """
        初始化智能提示
        
        参数：
            schema_cache: Schema 缓存实例
        """
        self.schema_cache = schema_cache
    
    def get_suggestions(
        self,
        sql: str,
        cursor_pos: int,
        context: Optional[Dict] = None
    ) -> List[SQLSuggestion]:
        """
        获取 SQL 补全建议
        
        参数：
            sql: 当前 SQL 语句
            cursor_pos: 光标位置
            context: 上下文信息
            
        返回：
            List[SQLSuggestion]: 建议列表
        """
        suggestions = []
        
        # 解析当前上下文
        context_info = self._parse_context(sql, cursor_pos)
        
        # 根据上下文提供建议
        if context_info['type'] == 'table':
            # 表名补全
            prefix = context_info['prefix']
            tables = self.schema_cache.search_tables(prefix)
            for table in tables:
                suggestions.append(SQLSuggestion(
                    type='completion',
                    text=table,
                    description=f'表: {table}',
                    confidence=1.0
                ))
        
        elif context_info['type'] == 'column':
            # 字段名补全
            prefix = context_info['prefix']
            table_hint = context_info.get('table')
            columns = self.schema_cache.search_columns(prefix, table_hint)
            
            for table, col in columns[:10]:  # 最多10个
                col_info = self.schema_cache.get_column_info(table, col)
                desc = f'{table}.{col}'
                if col_info:
                    desc += f' ({col_info.data_type})'
                
                suggestions.append(SQLSuggestion(
                    type='completion',
                    text=col,
                    description=desc,
                    confidence=0.9 if table == table_hint else 0.7
                ))
        
        elif context_info['type'] == 'keyword':
            # SQL 关键字补全
            prefix = context_info['prefix'].upper()
            for keyword in self.SQL_KEYWORDS:
                if keyword.startswith(prefix):
                    suggestions.append(SQLSuggestion(
                        type='completion',
                        text=keyword,
                        description='SQL 关键字',
                        confidence=0.8
                    ))
        
        return suggestions
    
    def _parse_context(self, sql: str, cursor_pos: int) -> Dict[str, Any]:
        """解析 SQL 上下文"""
        # 获取光标前的文本
        before_cursor = sql[:cursor_pos]
        
        # 获取当前词
        words = re.findall(r'[\w\.]+', before_cursor)
        current_word = words[-1] if words else ''
        
        # 判断上下文类型
        sql_upper = before_cursor.upper()
        
        # 检查是否在 FROM/JOIN 后
        if re.search(r'\b(FROM|JOIN)\s+\w*$', sql_upper):
            return {'type': 'table', 'prefix': current_word}
        
        # 检查是否在 SELECT/WHERE/ORDER BY 后
        if re.search(r'\b(SELECT|WHERE|AND|OR|ORDER BY|GROUP BY)\s+.*$', sql_upper):
            # 检查是否有表上下文
            tables = re.findall(r'\bFROM\s+(\w+)', sql_upper)
            return {
                'type': 'column',
                'prefix': current_word,
                'table': tables[-1] if tables else None
            }
        
        # 默认关键字补全
        return {'type': 'keyword', 'prefix': current_word}


class SQLGuardian:
    """
    SQL 守卫 - 防止危险操作和大查询
    
    功能：
    1. 自动添加 LIMIT
    2. 检测危险操作
    3. 估算查询成本
    
    使用示例：
        guardian = SQLGuardian(max_rows=1000)
        safe_sql = guardian.guard('SELECT * FROM big_table')
        # 返回: 'SELECT * FROM big_table LIMIT 1000'
    """
    
    DANGEROUS_PATTERNS = [
        (r'\bDROP\s+(DATABASE|TABLE)\b', '删除操作'),
        (r'\bTRUNCATE\s+TABLE\b', '清空表'),
        (r'\bDELETE\s+FROM\b', '删除数据'),
        (r'\bUPDATE\s+\w+\s+SET\b', '更新数据'),
        (r'\bALTER\s+TABLE\s+\w+\s+DROP\b', '删除列'),
    ]
    
    def __init__(self, max_rows: int = 1000, allow_dangerous: bool = False):
        """
        初始化 SQL 守卫
        
        参数：
            max_rows: 最大返回行数
            allow_dangerous: 是否允许危险操作
        """
        self.max_rows = max_rows
        self.allow_dangerous = allow_dangerous
    
    def guard(self, sql: str) -> Tuple[str, List[str]]:
        """
        保护 SQL 语句
        
        参数：
            sql: 原始 SQL
            
        返回：
            Tuple[安全SQL, 警告列表]
        """
        warnings = []
        modified_sql = sql.strip()
        
        # 检测危险操作
        if not self.allow_dangerous:
            for pattern, desc in self.DANGEROUS_PATTERNS:
                if re.search(pattern, modified_sql, re.IGNORECASE):
                    warnings.append(f'[危险] 检测到{desc}，请谨慎操作')
        
        # 自动添加 LIMIT
        modified_sql = self._add_limit(modified_sql)
        
        return modified_sql, warnings
    
    def _add_limit(self, sql: str) -> str:
        """自动添加 LIMIT"""
        # 检查是否已有 LIMIT
        if re.search(r'\bLIMIT\s+\d+', sql, re.IGNORECASE):
            return sql
        
        # 检查是否是 SELECT 语句
        if not re.match(r'^\s*SELECT', sql, re.IGNORECASE):
            return sql
        
        # 添加 LIMIT
        return f"{sql} LIMIT {self.max_rows}"
    
    def estimate_cost(self, sql: str, schema_cache: SchemaCache) -> Dict[str, Any]:
        """
        估算查询成本
        
        参数：
            sql: SQL 语句
            schema_cache: Schema 缓存
            
        返回：
            Dict: 成本估算结果
        """
        cost = {
            'estimated_rows': None,
            'estimated_time_ms': None,
            'warnings': [],
            'risk_level': 'low'
        }
        
        # 提取表名
        tables = re.findall(r'\bFROM\s+(\w+)', sql, re.IGNORECASE)
        
        total_rows = 0
        for table_name in tables:
            table_info = schema_cache.get_table_info(table_name)
            if table_info:
                total_rows += table_info.row_count
        
        if total_rows > 0:
            cost['estimated_rows'] = total_rows
            
            # 简单估算：每 1000 行 1ms
            cost['estimated_time_ms'] = total_rows / 1000
            
            # 风险评估
            if total_rows > 1000000:
                cost['risk_level'] = 'high'
                cost['warnings'].append(f'涉及大表，预计扫描 {total_rows} 行')
            elif total_rows > 100000:
                cost['risk_level'] = 'medium'
        
        return cost


class ResultExplainer:
    """
    查询结果解释器
    
    功能：
    1. 生成自然语言摘要
    2. 识别数据特征
    3. 提供洞察建议
    
    使用示例：
        explainer = ResultExplainer()
        explanation = explainer.explain(result_df, 'SELECT * FROM orders')
        print(explanation.summary)
    """
    
    def explain(self, result, sql: str) -> Dict[str, Any]:
        """
        解释查询结果
        
        参数：
            result: QueryResult 或 DataFrame
            sql: 原始 SQL
            
        返回：
            Dict: 解释结果
        """
        if hasattr(result, 'df'):
            df = result.df
        else:
            df = result
        
        row_count = len(df)
        col_count = len(df.columns)
        
        explanation = {
            'summary': '',
            'row_count': row_count,
            'column_count': col_count,
            'columns': list(df.columns),
            'insights': [],
            'suggestions': []
        }
        
        # 生成摘要
        explanation['summary'] = self._generate_summary(row_count, col_count, sql)
        
        # 数据特征分析
        if row_count > 0:
            explanation['insights'] = self._analyze_data(df)
        
        # 提供建议
        explanation['suggestions'] = self._generate_suggestions(df, sql)
        
        return explanation
    
    def _generate_summary(self, row_count: int, col_count: int, sql: str) -> str:
        """生成摘要"""
        # 提取操作类型
        operation = '查询'
        sql_upper = sql.upper()
        
        if 'COUNT' in sql_upper:
            operation = '计数'
        elif 'SUM' in sql_upper or 'AVG' in sql_upper:
            operation = '聚合'
        elif 'GROUP BY' in sql_upper:
            operation = '分组统计'
        
        return f"{operation}结果: 返回 {row_count} 行数据，共 {col_count} 个字段"
    
    def _analyze_data(self, df) -> List[str]:
        """分析数据特征"""
        insights = []
        
        # 检查空值
        null_counts = df.isnull().sum()
        if null_counts.any():
            cols_with_null = null_counts[null_counts > 0]
            insights.append(f"发现 {len(cols_with_null)} 个字段存在空值")
        
        # 检查数值列
        numeric_cols = df.select_dtypes(include=['number']).columns
        for col in numeric_cols[:3]:  # 最多分析3个
            min_val = df[col].min()
            max_val = df[col].max()
            mean_val = df[col].mean()
            insights.append(f"{col}: 范围 [{min_val:.2f}, {max_val:.2f}], 平均值 {mean_val:.2f}")
        
        return insights
    
    def _generate_suggestions(self, df, sql: str) -> List[str]:
        """生成建议"""
        suggestions = []
        
        row_count = len(df)
        
        if row_count == 0:
            suggestions.append("查询结果为空，请检查查询条件")
        elif row_count == 1000 and 'LIMIT 1000' in sql:
            suggestions.append("结果已达到 LIMIT 上限，可能需要添加更精确的过滤条件")
        elif row_count > 10000:
            suggestions.append("返回数据量较大，建议使用分页或导出功能")
        
        return suggestions


class SchemaAwareOptimizer:
    """
    Schema感知优化器 - 基于Schema信息优化SQL
    
    功能：
    1. 获取表结构信息
    2. 分析索引使用情况
    3. 提供优化建议
    
    使用示例：
        optimizer = SchemaAwareOptimizer(connector)
        schema = optimizer.get_schema_info('users')
        print(schema)
    """
    
    def __init__(self, connector):
        """
        初始化优化器
        
        参数：
            connector: 数据库连接器
        """
        self.connector = connector
        self.schema_cache = SchemaCache(connector)
    
    def get_table_schema(self, table_name: str) -> Dict[str, Any]:
        """
        获取指定表的Schema信息
        
        参数：
            table_name: 表名
            
        返回：
            Dict: Schema信息
        """
        try:
            table_info = self.schema_cache.get_table_info(table_name)
            if not table_info:
                return {"status": "error", "error": f"表 {table_name} 不存在"}
            
            return {
                "status": "success",
                "success": True,
                "table": table_name,
                "columns": [
                    {
                        "name": col.name,
                        "type": col.data_type,
                        "nullable": col.is_nullable,
                        "default": col.default_value,
                        "comment": col.comment
                    }
                    for col in table_info.columns.values()
                ],
                "indexes": table_info.indexes,
                "primary_key": table_info.primary_key,
                "row_count": table_info.row_count,
                "size_mb": table_info.size_mb,
                "comment": table_info.comment
            }
        except Exception as e:
            return {"status": "error", "success": False, "error": str(e)}
    
    def get_schema_info(self, table_name: Optional[str] = None) -> Dict[str, Any]:
        """
        获取Schema信息
        
        参数：
            table_name: 表名，None则返回所有表
            
        返回：
            Dict: Schema信息
        """
        try:
            if table_name:
                table_info = self.schema_cache.get_table_info(table_name)
                if not table_info:
                    return {"status": "error", "success": False, "error": f"表 {table_name} 不存在"}
                
                return {
                    "status": "success",
                    "success": True,
                    "table": table_name,
                    "columns": [
                        {
                            "name": col.name,
                            "type": col.data_type,
                            "nullable": col.is_nullable,
                            "default": col.default_value,
                            "comment": col.comment
                        }
                        for col in table_info.columns.values()
                    ],
                    "indexes": table_info.indexes,
                    "primary_key": table_info.primary_key,
                    "row_count": table_info.row_count,
                    "size_mb": table_info.size_mb
                }
            else:
                tables = self.schema_cache.get_tables()
                return {
                    "status": "success",
                    "success": True,
                    "tables": tables,
                    "count": len(tables)
                }
        except Exception as e:
            return {"status": "error", "success": False, "error": str(e)}
    
    def analyze_index_usage(self, sql: str) -> Dict[str, Any]:
        """
        分析SQL的索引使用情况
        
        参数：
            sql: SQL语句
            
        返回：
            Dict: 索引分析结果
        """
        # 简化实现，实际应该解析SQL并分析索引
        return {
            "status": "success",
            "sql": sql,
            "suggested_indexes": [],
            "existing_indexes": [],
            "message": "索引分析功能需要完整的数据库连接"
        }
    
    def list_tables(self) -> List[str]:
        """
        列出数据库中的所有表
        
        返回：
            List[str]: 表名列表
        """
        try:
            result = self.get_schema_info()
            if result.get("status") == "success":
                return result.get("tables", [])
            return []
        except Exception as e:
            logger.error(f"获取表列表失败: {e}")
            return []
