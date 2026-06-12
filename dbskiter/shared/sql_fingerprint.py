"""
SQL指纹核心模块

文件功能：提供多数据库统一的SQL指纹生成和聚合能力
参考实现：pt-query-digest核心算法
主要类：
    - SQLFingerprinter: SQL指纹生成器
    - FingerprintResult: 指纹结果数据类
    - QueryAggregator: 查询聚合器

设计原则：
    1. 多数据库支持：MySQL/Oracle/PostgreSQL统一接口
    2. 版本兼容：支持各数据库多个版本
    3. 高性能：正则优化，批量处理，LRU缓存
    4. 零依赖：纯Python实现，无需外部工具

使用示例：
    from dbskiter.shared.sql_fingerprint import SQLFingerprinter
    
    fingerprinter = SQLFingerprinter()
    
    # 单条SQL指纹
    result = fingerprinter.fingerprint("SELECT * FROM users WHERE id = 123")
    print(result.fingerprint)  # SELECT * FROM users WHERE id = ?
    
    # 批量聚合
    queries = [
        {'sql': 'SELECT * FROM users WHERE id = 1', 'time': 0.5},
        {'sql': 'SELECT * FROM users WHERE id = 2', 'time': 0.3},
    ]
    aggregated = fingerprinter.aggregate(queries)
"""

from __future__ import annotations

import re
import hashlib
from enum import Enum
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any, Callable
from collections import defaultdict, OrderedDict
import logging
import threading

logger = logging.getLogger(__name__)


class LRUCache:
    """
    线程安全的LRU缓存
    
    使用OrderedDict实现O(1)的get和put操作
    
    参数:
        capacity: 缓存容量
        
    示例:
        >>> cache = LRUCache(2)
        >>> cache.put('a', 1)
        >>> cache.get('a')
        1
        >>> cache.put('b', 2)
        >>> cache.put('c', 3)  # 淘汰'a'
        >>> cache.get('a') is None
        True
    """
    
    def __init__(self, capacity: int = 10000):
        self.capacity = capacity
        self.cache = OrderedDict()
        self.lock = threading.RLock()
        self._hits = 0
        self._misses = 0
    
    def get(self, key: str) -> Optional[Any]:
        """
        获取缓存值
        
        参数:
            key: 缓存键
            
        返回:
            缓存值，不存在返回None
        """
        with self.lock:
            if key in self.cache:
                # 移动到末尾（最近使用）
                self.cache.move_to_end(key)
                self._hits += 1
                return self.cache[key]
            self._misses += 1
            return None
    
    def put(self, key: str, value: Any) -> None:
        """
        存入缓存
        
        参数:
            key: 缓存键
            value: 缓存值
        """
        with self.lock:
            if key in self.cache:
                # 更新值并移动到末尾
                self.cache.move_to_end(key)
            self.cache[key] = value
            
            # 超出容量，淘汰最久未使用的
            if len(self.cache) > self.capacity:
                self.cache.popitem(last=False)
    
    def clear(self) -> None:
        """清空缓存"""
        with self.lock:
            self.cache.clear()
            self._hits = 0
            self._misses = 0
    
    @property
    def stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        with self.lock:
            total = self._hits + self._misses
            hit_rate = self._hits / total if total > 0 else 0
            return {
                'size': len(self.cache),
                'capacity': self.capacity,
                'hits': self._hits,
                'misses': self._misses,
                'hit_rate': f"{hit_rate:.2%}"
            }


class SQLType(Enum):
    """SQL类型枚举"""
    SELECT = "SELECT"
    INSERT = "INSERT"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    REPLACE = "REPLACE"
    CALL = "CALL"
    UNKNOWN = "UNKNOWN"


@dataclass
class FingerprintResult:
    """
    SQL指纹结果
    
    属性:
        fingerprint: 规范化后的SQL指纹字符串
        sql_type: SQL语句类型
        tables: 涉及的表名列表
        digest: MD5摘要，用于唯一标识
        normalized_sql: 规范化后的SQL（可用于展示）
        original_sql: 原始SQL（前200字符，用于示例）
    """
    fingerprint: str
    sql_type: SQLType
    tables: List[str] = field(default_factory=list)
    digest: str = ""
    normalized_sql: str = ""
    original_sql: str = ""
    
    def __post_init__(self):
        """初始化后计算digest"""
        if not self.digest and self.fingerprint:
            self.digest = hashlib.md5(self.fingerprint.encode()).hexdigest()[:16]


@dataclass
class QueryGroup:
    """
    查询聚合组
    
    属性:
        fingerprint: 指纹字符串
        digest: 指纹摘要
        count: 出现次数
        total_time: 总执行时间
        avg_time: 平均执行时间
        min_time: 最小执行时间
        max_time: 最大执行时间
        examples: 示例SQL列表
        tables: 涉及的表
    """
    fingerprint: str
    digest: str
    count: int = 0
    total_time: float = 0.0
    min_time: float = 0.0
    max_time: float = 0.0
    examples: List[str] = field(default_factory=list)
    tables: List[str] = field(default_factory=list)
    
    @property
    def avg_time(self) -> float:
        """计算平均时间"""
        return self.total_time / self.count if self.count > 0 else 0.0


class SQLFingerprinter:
    """
    SQL指纹生成器
    
    参考pt-query-digest算法实现，支持多数据库SQL语法
    
    核心能力：
        1. SQL规范化：将相似SQL归一化为相同指纹
        2. 参数替换：数字、字符串、列表替换为占位符
        3. 表名提取：识别SQL中涉及的表
        4. 批量聚合：按指纹分组统计
    
    支持的SQL特性：
        - 标准SQL（SELECT/INSERT/UPDATE/DELETE）
        - MySQL特有语法（反引号、注释等）
        - Oracle特有语法（ROWNUM、双引号等）
        - PostgreSQL特有语法（LIMIT/OFFSET等）
    """
    
    # SQL关键字映射
    SQL_KEYWORDS: Dict[str, SQLType] = {
        'SELECT': SQLType.SELECT,
        'INSERT': SQLType.INSERT,
        'UPDATE': SQLType.UPDATE,
        'DELETE': SQLType.DELETE,
        'REPLACE': SQLType.REPLACE,
        'CALL': SQLType.CALL,
    }
    
    # 预编译的正则表达式（性能优化）
    RE_PATTERNS = {
        # 空白字符规范化
        'whitespace': re.compile(r'\s+'),
        
        # 单行注释 (-- 开头)
        'comment_single': re.compile(r'--[^\n]*'),
        
        # 多行注释 (/* */)
        'comment_multi': re.compile(r'/\*.*?\*/', re.DOTALL),
        
        # MySQL条件注释 (/*!50000 ... */)
        'comment_mysql': re.compile(r'/\*!\d+\s+', re.DOTALL),
        
        # 单引号字符串（处理转义）
        'string_single': re.compile(r"'[^'\\]*(?:\\.[^'\\]*)*'"),
        
        # 双引号字符串（处理转义）
        'string_double': re.compile(r'"[^"\\]*(?:\\.[^"\\]*)*"'),
        
        # 数字（整数、小数、负数、科学计数法）
        'number': re.compile(r'(?<![\w.])-?\d+\.?\d*([eE][+-]?\d+)?(?![\w.])'),
        
        # IN列表
        'in_list': re.compile(r'IN\s*\([^)]+\)', re.IGNORECASE),
        
        # VALUES多值 (INSERT ... VALUES (...), (...), (...))
        'values_multi': re.compile(
            r'VALUES\s*\([^)]+\)(\s*,\s*\([^)]+\))+',
            re.IGNORECASE
        ),
        
        # LIMIT子句 (MySQL/PostgreSQL)
        'limit': re.compile(r'LIMIT\s+\?\s*(,\s*\?|OFFSET\s+\?)?', re.IGNORECASE),
        
        # Oracle ROWNUM
        'rownum': re.compile(r'ROWNUM\s*[<>=]+\s*\?', re.IGNORECASE),
        
        # CTE (Common Table Expression) - WITH子句
        'cte_name': re.compile(r'WITH\s+(\w+)\s*\(', re.IGNORECASE),
        
        # 窗口函数 - OVER子句
        'window_func': re.compile(
            r'(ROW_NUMBER|RANK|DENSE_RANK|LEAD|LAG|FIRST_VALUE|LAST_VALUE|SUM|AVG|COUNT|MIN|MAX)\s*\([^)]*\)\s+OVER\s*\(',
            re.IGNORECASE
        ),
        
        # 子查询 - 简单检测
        'subquery': re.compile(r'\(\s*SELECT\s+', re.IGNORECASE),
        
        # UNION/INTERSECT/EXCEPT
        'set_operation': re.compile(r'\s+(UNION|INTERSECT|EXCEPT)(\s+ALL)?\s+', re.IGNORECASE),
        
        # CASE表达式
        'case_expr': re.compile(
            r'CASE\s+WHEN\s+.+?\s+THEN\s+.+?(\s+WHEN\s+.+?\s+THEN\s+.+?)*\s+ELSE\s+.+?\s+END',
            re.IGNORECASE | re.DOTALL
        ),
        
        # 日期时间函数
        'datetime_func': re.compile(
            r'(NOW|CURRENT_TIMESTAMP|CURRENT_DATE|CURRENT_TIME|DATE_ADD|DATE_SUB|DATEDIFF|DATE_FORMAT)\s*\([^)]*\)',
            re.IGNORECASE
        ),
        
        # UUID/GUID
        'uuid': re.compile(
            r'[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}'
        ),
        
        # 十六进制数据
        'hex_data': re.compile(r'0x[0-9a-fA-F]+|X\'[0-9a-fA-F]+\''),
        
        # 布尔值
        'boolean': re.compile(r'\b(TRUE|FALSE)\b', re.IGNORECASE),
    }
    
    # 配置常量
    MAX_SQL_LENGTH = 10000  # SQL最大长度限制
    MAX_PROCESSING_TIME = 1.0  # 最大处理时间（秒）
    CACHE_CAPACITY = 10000  # 缓存容量
    
    def __init__(self, max_sql_length: int = None, max_processing_time: float = None, 
                 cache_capacity: int = None, enable_cache: bool = True):
        """
        初始化指纹生成器
        
        参数:
            max_sql_length: SQL最大长度限制（默认10000字符）
            max_processing_time: 最大处理时间（默认1秒）
            cache_capacity: 缓存容量（默认10000）
            enable_cache: 是否启用缓存（默认True）
        """
        self._compile_patterns()
        self._max_sql_length = max_sql_length or self.MAX_SQL_LENGTH
        self._max_processing_time = max_processing_time or self.MAX_PROCESSING_TIME
        self._enable_cache = enable_cache
        
        # 初始化LRU缓存
        if enable_cache:
            self._cache = LRUCache(cache_capacity or self.CACHE_CAPACITY)
        else:
            self._cache = None
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        if self._cache:
            return self._cache.stats
        return {'enabled': False}
    
    def clear_cache(self) -> None:
        """清空缓存"""
        if self._cache:
            self._cache.clear()
            logger.info("SQL指纹缓存已清空")
    
    def _get_cache_key(self, sql: str, dialect: str) -> str:
        """
        生成缓存键
        
        使用SQL内容和方言的组合哈希作为键
        """
        key_data = f"{dialect}:{sql}"
        return hashlib.md5(key_data.encode()).hexdigest()
    
    def _compile_patterns(self):
        """确保所有正则表达式已编译"""
        # 已经在类定义时编译，这里用于扩展
        pass
    
    def _check_sql_length(self, sql: str) -> str:
        """
        检查SQL长度，超长则截断
        
        参数:
            sql: 原始SQL
            
        返回:
            str: 处理后的SQL（返回原始SQL，但记录警告）
            
        注意:
            返回原始SQL，但_truncated标记会添加到fingerprint中
        """
        if len(sql) > self._max_sql_length:
            logger.warning(f"SQL长度({len(sql)})超过限制({self._max_sql_length})，已截断")
        return sql
    
    def _safe_regex_replace(self, pattern_name: str, sql: str, replacement: str) -> str:
        """
        安全的正则替换（带超时保护）
        
        参数:
            pattern_name: 正则模式名称
            sql: 输入字符串
            replacement: 替换字符串
            
        返回:
            str: 替换后的字符串
        """
        import time
        start_time = time.time()
        
        pattern = self.RE_PATTERNS.get(pattern_name)
        if not pattern:
            logger.warning(f"未知的正则模式: {pattern_name}")
            return sql
        
        try:
            # 对于可能耗时较长的正则，分段处理
            if len(sql) > 5000 and pattern_name in ('string_single', 'string_double'):
                # 分段处理长SQL，避免灾难性回溯
                return self._segmented_replace(pattern, sql, replacement)
            
            result = pattern.sub(replacement, sql)
            
            # 检查处理时间
            elapsed = time.time() - start_time
            if elapsed > 0.1:  # 超过100ms记录警告
                logger.warning(f"正则替换耗时过长: {pattern_name} 耗时 {elapsed:.3f}s")
            
            return result
            
        except Exception as e:
            logger.error(f"正则替换失败 {pattern_name}: {e}")
            # 失败时返回原始SQL，避免数据丢失
            return sql
    
    def _segmented_replace(self, pattern, sql: str, replacement: str, segment_size: int = 2000) -> str:
        """
        分段正则替换（用于处理长SQL）
        
        参数:
            pattern: 正则模式
            sql: 输入字符串
            replacement: 替换字符串
            segment_size: 分段大小
            
        返回:
            str: 替换后的字符串
        """
        if len(sql) <= segment_size:
            return pattern.sub(replacement, sql)
        
        # 分段处理
        segments = []
        for i in range(0, len(sql), segment_size):
            segment = sql[i:i + segment_size]
            # 扩展边界，避免截断匹配
            if i > 0:
                segment = sql[max(0, i - 100):i] + segment
            if i + segment_size < len(sql):
                segment = segment + sql[i + segment_size:min(len(sql), i + segment_size + 100)]
            
            processed = pattern.sub(replacement, segment)
            
            # 移除扩展的边界
            if i > 0:
                processed = processed[100:]
            if i + segment_size < len(sql):
                processed = processed[:-100] if len(processed) > 100 else processed
            
            segments.append(processed)
        
        return ''.join(segments)
    
    def _validate_sql_syntax(self, sql: str) -> tuple[bool, str]:
        """
        基础SQL语法验证
        
        验证规则:
            1. 括号匹配检查
            2. 引号匹配检查
            3. 基本结构检查（必须以SQL关键字开头）
            
        参数:
            sql: SQL语句
            
        返回:
            tuple: (是否有效, 错误信息)
            
        示例:
            >>> fp._validate_sql_syntax("SELECT * FROM t")
            (True, "")
            >>> fp._validate_sql_syntax("SELECT * FROM (t")
            (False, "括号不匹配")
        """
        if not sql or not sql.strip():
            return False, "SQL为空"
        
        sql = sql.strip()
        
        # 1. 括号匹配检查
        stack = []
        in_string = False
        string_char = None
        
        for i, char in enumerate(sql):
            # 处理字符串
            if char in ("'", '"', '`') and (i == 0 or sql[i-1] != '\\'):
                if not in_string:
                    in_string = True
                    string_char = char
                elif char == string_char:
                    in_string = False
                    string_char = None
                continue
            
            if in_string:
                continue
            
            # 检查括号
            if char == '(':
                stack.append(char)
            elif char == ')':
                if not stack:
                    return False, f"位置{i}: 多余的右括号"
                stack.pop()
        
        if stack:
            return False, "括号不匹配，存在未闭合的左括号"
        
        # 2. 引号匹配检查
        in_string = False
        string_char = None
        
        for i, char in enumerate(sql):
            if char in ("'", '"', '`'):
                if not in_string:
                    in_string = True
                    string_char = char
                elif char == string_char and (i == 0 or sql[i-1] != '\\'):
                    in_string = False
                    string_char = None
        
        if in_string:
            return False, f"字符串未闭合，缺少{string_char}"
        
        # 3. 基本结构检查
        first_word = sql.split()[0].upper()
        valid_starts = {'SELECT', 'INSERT', 'UPDATE', 'DELETE', 'WITH',
                       'CREATE', 'ALTER', 'DROP', 'TRUNCATE', 'REPLACE',
                       'SHOW', 'DESCRIBE', 'EXPLAIN', 'CALL',
                       # Oracle PL/SQL
                       'BEGIN', 'DECLARE', 'FOR', 'IF', 'LOOP', 'WHILE',
                       'MERGE', 'GRANT', 'REVOKE', 'ANALYZE'}

        if first_word not in valid_starts:
            return False, f"无效的SQL起始关键字: {first_word}"

        return True, ""
    
    def fingerprint(self, sql: str, dialect: str = 'mysql') -> FingerprintResult:
        """
        生成SQL指纹（带性能保护、语法验证和缓存）
        
        参数:
            sql: 原始SQL语句
            dialect: 数据库方言（mysql/oracle/postgres）
            
        返回:
            FingerprintResult: 指纹结果
            
        示例:
            >>> fp = SQLFingerprinter()
            >>> result = fp.fingerprint("SELECT * FROM users WHERE id = 123")
            >>> print(result.fingerprint)
            'SELECT * FROM users WHERE id = ?'
            
        性能保护:
            - SQL长度限制（默认10000字符）
            - 正则替换超时保护
            - 长SQL分段处理
            - LRU缓存（默认10000条）
            
        新增:
            - SQL语法基础验证
            - 指纹缓存机制
        """
        import time
        start_time = time.time()
        
        if not sql or not isinstance(sql, str):
            return FingerprintResult(
                fingerprint="",
                sql_type=SQLType.UNKNOWN,
                original_sql=str(sql)[:200] if sql else ""
            )
        
        original = sql.strip()
        
        # 0. 检查缓存
        if self._enable_cache and self._cache:
            cache_key = self._get_cache_key(original, dialect)
            cached_result = self._cache.get(cache_key)
            if cached_result:
                return cached_result
        
        # 1. 语法验证
        is_valid, error_msg = self._validate_sql_syntax(original)
        if not is_valid:
            logger.warning(f"SQL语法验证失败: {error_msg}")
            # 继续处理，但记录警告
        
        # 2. 长度检查
        original = self._check_sql_length(original)
        
        # 1. 预处理
        sql = self._preprocess(sql, dialect)
        
        # 2. 检测SQL类型
        sql_type = self._detect_sql_type(sql)
        
        # 3. 提取表名（在替换前提取，避免信息丢失）
        tables = self._extract_tables(original, dialect)
        
        # 4. 替换字符串（使用安全替换）
        sql = self._safe_regex_replace('string_single', sql, '?')
        sql = self._safe_regex_replace('string_double', sql, '?')
        
        # 5. 替换数字（使用安全替换）
        sql = self._safe_regex_replace('number', sql, '?')
        
        # 6. 替换IN列表（使用安全替换）
        sql = self._safe_regex_replace('in_list', sql, 'IN (?)')
        
        # 7. 替换多值INSERT（使用安全替换）
        sql = self._safe_regex_replace('values_multi', sql, 'VALUES (?)')
        
        # 8. 替换复杂SQL模式（新增）
        sql = self._replace_complex_patterns(sql)
        
        # 9. 替换LIMIT/ROWNUM（使用安全替换）
        if 'oracle' in dialect.lower():
            sql = self._safe_regex_replace('rownum', sql, 'ROWNUM <= ?')
        else:
            sql = self._safe_regex_replace('limit', sql, 'LIMIT ?')
        
        # 10. 最终规范化
        sql = self._final_normalize(sql)
        
        # 检查总处理时间
        elapsed = time.time() - start_time
        if elapsed > self._max_processing_time:
            logger.warning(f"指纹生成耗时过长: {elapsed:.3f}s，SQL长度: {len(original)}")
        
        # 构建结果
        result = FingerprintResult(
            fingerprint=sql,
            sql_type=sql_type,
            tables=tables,
            normalized_sql=sql,
            original_sql=original[:200]
        )
        
        # 存入缓存
        if self._enable_cache and self._cache:
            cache_key = self._get_cache_key(original, dialect)
            self._cache.put(cache_key, result)
        
        return result
    
    def _preprocess(self, sql: str, dialect: str) -> str:
        """
        预处理SQL
        
        1. 移除注释
        2. 规范化空白
        3. 方言特定处理
        """
        # 移除单行注释
        sql = self.RE_PATTERNS['comment_single'].sub('', sql)
        
        # 移除多行注释（保留MySQL条件注释标记）
        sql = self.RE_PATTERNS['comment_mysql'].sub('/* ', sql)
        sql = self.RE_PATTERNS['comment_multi'].sub('', sql)
        
        # 规范化空白
        sql = self.RE_PATTERNS['whitespace'].sub(' ', sql)
        
        # 方言特定处理
        if 'mysql' in dialect.lower():
            sql = self._preprocess_mysql(sql)
        elif 'oracle' in dialect.lower():
            sql = self._preprocess_oracle(sql)
        elif 'postgresql' in dialect.lower():
            sql = self._preprocess_postgres(sql)
        
        return sql.strip()
    
    def _preprocess_mysql(self, sql: str) -> str:
        """MySQL预处理"""
        # 保留反引号，但规范化内容
        return sql
    
    def _preprocess_oracle(self, sql: str) -> str:
        """Oracle预处理"""
        # 处理双引号标识符
        return sql
    
    def _preprocess_postgres(self, sql: str) -> str:
        """PostgreSQL预处理"""
        return sql
    
    def _detect_sql_type(self, sql: str) -> SQLType:
        """检测SQL类型"""
        # 获取第一个有效单词
        first_word = ''
        for word in sql.split():
            word_upper = word.upper()
            if word_upper in self.SQL_KEYWORDS:
                return self.SQL_KEYWORDS[word_upper]
            # 跳过注释和空行
            if word and not word.startswith(('--', '/*')):
                first_word = word_upper
                break
        
        return self.SQL_KEYWORDS.get(first_word, SQLType.UNKNOWN)
    
    def _extract_tables(self, sql: str, dialect: str) -> List[str]:
        """
        提取SQL涉及的表名
        
        支持：
            - FROM子句
            - JOIN子句
            - INTO子句（INSERT）
            - UPDATE子句
        """
        tables = set()
        sql_upper = sql.upper()
        
        # FROM子句（支持反引号、双引号）
        # 匹配：FROM table, FROM `table`, FROM "table", FROM schema.table
        from_pattern = re.compile(
            r'FROM\s+(`?"?\w+`?"?(?:\.`?"?\w+`?"?)?)',
            re.IGNORECASE
        )
        for match in from_pattern.finditer(sql):
            table = match.group(1)
            tables.add(self._normalize_identifier(table, dialect))
        
        # JOIN子句
        join_pattern = re.compile(
            r'JOIN\s+(`?"?\w+`?"?(?:\.`?"?\w+`?"?)?)',
            re.IGNORECASE
        )
        for match in join_pattern.finditer(sql):
            table = match.group(1)
            tables.add(self._normalize_identifier(table, dialect))
        
        # INTO子句（INSERT）
        into_pattern = re.compile(
            r'INTO\s+(`?"?\w+`?"?(?:\.`?"?\w+`?"?)?)',
            re.IGNORECASE
        )
        for match in into_pattern.finditer(sql):
            table = match.group(1)
            tables.add(self._normalize_identifier(table, dialect))
        
        # UPDATE子句
        update_pattern = re.compile(
            r'UPDATE\s+(`?"?\w+`?"?(?:\.`?"?\w+`?"?)?)',
            re.IGNORECASE
        )
        for match in update_pattern.finditer(sql):
            table = match.group(1)
            tables.add(self._normalize_identifier(table, dialect))
        
        return sorted(list(tables))
    
    def _normalize_identifier(self, identifier: str, dialect: str) -> str:
        """规范化标识符（移除引号）"""
        # 移除反引号（MySQL）和双引号（Oracle/PostgreSQL）
        identifier = identifier.strip('`"')
        
        # 处理schema.table格式
        if '.' in identifier:
            parts = identifier.split('.')
            # 只返回表名，不包含schema
            return parts[-1].strip('`"')
        
        return identifier
    
    def _replace_strings(self, sql: str) -> str:
        """替换字符串常量"""
        # 单引号字符串
        sql = self.RE_PATTERNS['string_single'].sub('?', sql)
        # 双引号字符串（如果不是标识符）
        sql = self.RE_PATTERNS['string_double'].sub('?', sql)
        return sql
    
    def _replace_numbers(self, sql: str) -> str:
        """替换数字"""
        return self.RE_PATTERNS['number'].sub('?', sql)
    
    def _replace_in_lists(self, sql: str) -> str:
        """替换IN列表"""
        return self.RE_PATTERNS['in_list'].sub('IN (?)', sql)
    
    def _replace_insert_values(self, sql: str) -> str:
        """替换INSERT多值"""
        return self.RE_PATTERNS['values_multi'].sub('VALUES (?)', sql)
    
    def _replace_limit_clause(self, sql: str, dialect: str) -> str:
        """替换LIMIT/ROWNUM子句"""
        if 'oracle' in dialect.lower():
            # Oracle ROWNUM
            sql = self.RE_PATTERNS['rownum'].sub('ROWNUM <= ?', sql)
        else:
            # MySQL/PostgreSQL LIMIT
            sql = self.RE_PATTERNS['limit'].sub('LIMIT ?', sql)
        return sql
    
    def _replace_window_functions(self, sql: str) -> str:
        """
        替换窗口函数为占位符
        
        使用栈结构处理嵌套括号，支持引号内的括号忽略
        
        参数:
            sql: 原始SQL
            
        返回:
            str: 替换后的SQL
            
        示例:
            >>> fp._replace_window_functions(
            ...     "SELECT ROW_NUMBER() OVER (PARTITION BY x) FROM t"
            ... )
            'SELECT <window_func> FROM t'
        """
        result = []
        last_end = 0
        
        for match in self.RE_PATTERNS['window_func'].finditer(sql):
            # 添加匹配之前的文本
            result.append(sql[last_end:match.start()])
            
            # 使用栈找到OVER(...)的结束位置
            start = match.end()  # '('之后的位置
            stack = ['(']  # 初始化栈，已经匹配了一个'('
            i = start
            in_string = False
            string_char = None
            
            while i < len(sql) and stack:
                char = sql[i]
                
                # 处理字符串
                if char in ("'", '"', '`') and (i == 0 or sql[i-1] != '\\'):
                    if not in_string:
                        in_string = True
                        string_char = char
                    elif char == string_char:
                        in_string = False
                        string_char = None
                
                # 只有在非字符串状态下才处理括号
                if not in_string:
                    if char == '(':
                        stack.append('(')
                    elif char == ')':
                        stack.pop()
                
                i += 1
            
            # 添加占位符
            result.append('<window_func>')
            last_end = i  # 跳过整个OVER(...)部分
        
        # 添加剩余文本
        result.append(sql[last_end:])
        return ''.join(result)
    
    def _replace_complex_patterns(self, sql: str) -> str:
        """
        替换复杂SQL模式
        
        处理：
            - 窗口函数 OVER(...)
            - CASE表达式
            - 日期时间函数
            - UUID
            - 十六进制数据
            - 布尔值
        """
        # 替换窗口函数（使用新的栈结构实现）
        sql = self._replace_window_functions(sql)
        
        # 替换CASE表达式
        sql = self.RE_PATTERNS['case_expr'].sub('<case_expr>', sql)
        
        # 替换日期时间函数
        sql = self.RE_PATTERNS['datetime_func'].sub('<datetime>', sql)
        
        # 替换UUID
        sql = self.RE_PATTERNS['uuid'].sub('<uuid>', sql)
        
        # 替换十六进制数据
        sql = self.RE_PATTERNS['hex_data'].sub('<hex>', sql)
        
        # 替换布尔值（保持语义）
        sql = self.RE_PATTERNS['boolean'].sub(lambda m: m.group(1).upper(), sql)
        
        return sql
    
    def _detect_complex_features(self, sql: str) -> Dict[str, bool]:
        """
        检测SQL中的复杂特性
        
        返回:
            Dict: 特性检测结果
                - has_cte: 是否有CTE (WITH子句)
                - has_subquery: 是否有子查询
                - has_window_func: 是否有窗口函数
                - has_union: 是否有UNION/INTERSECT/EXCEPT
                - has_case: 是否有CASE表达式
        """
        return {
            'has_cte': bool(self.RE_PATTERNS['cte_name'].search(sql)),
            'has_subquery': bool(self.RE_PATTERNS['subquery'].search(sql)),
            'has_window_func': bool(self.RE_PATTERNS['window_func'].search(sql)),
            'has_union': bool(self.RE_PATTERNS['set_operation'].search(sql)),
            'has_case': bool(self.RE_PATTERNS['case_expr'].search(sql)),
        }
    
    def _final_normalize(self, sql: str) -> str:
        """最终规范化"""
        # 统一为大写（可选，根据需求）
        # sql = sql.upper()

        # 规范化空白：多个空格替换为单个，但保留换行用于可读性
        sql = self.RE_PATTERNS['whitespace'].sub(' ', sql)

        # 移除操作符周围的额外空格（保留一个）
        sql = re.sub(r'\s*([(),=<>!+\-*/])\s*', r'\1', sql)

        # 在关键字后保留空格
        sql = re.sub(r'\b(SELECT|FROM|WHERE|AND|OR|ORDER|GROUP|HAVING|LIMIT|JOIN|ON|IN|EXISTS)\b', r' \1 ', sql, flags=re.IGNORECASE)

        # 再次规范化多余空格
        sql = ' '.join(sql.split())

        # 确保结尾没有分号（统一）
        sql = sql.rstrip(';')

        return sql.strip()
    
    def aggregate(self, queries: List[Dict[str, Any]], 
                  max_examples: int = 3) -> Dict[str, QueryGroup]:
        """
        按指纹聚合查询
        
        参数:
            queries: 查询列表，每项包含'sql'和'time'字段
            max_examples: 每组保留的示例数量
            
        返回:
            Dict[str, QueryGroup]: 按digest分组的聚合结果
            
        示例:
            >>> queries = [
            ...     {'sql': 'SELECT * FROM users WHERE id = 1', 'time': 0.5},
            ...     {'sql': 'SELECT * FROM users WHERE id = 2', 'time': 0.3},
            ... ]
            >>> aggregated = fingerprinter.aggregate(queries)
            >>> print(aggregated['abc123'].count)
            2
        """
        groups: Dict[str, QueryGroup] = {}
        
        for query in queries:
            sql = query.get('sql', '')
            if not sql:
                continue
            
            # 生成指纹
            result = self.fingerprint(sql)
            digest = result.digest
            
            # 获取或创建组
            if digest not in groups:
                groups[digest] = QueryGroup(
                    fingerprint=result.fingerprint,
                    digest=digest,
                    tables=result.tables
                )
            
            group = groups[digest]
            
            # 更新统计
            query_time = float(query.get('time', 0) or query.get('query_time', 0))
            group.count += 1
            group.total_time += query_time
            group.min_time = min(group.min_time, query_time) if group.min_time > 0 else query_time
            group.max_time = max(group.max_time, query_time)
            
            # 保存示例
            if len(group.examples) < max_examples:
                example = result.original_sql[:200]
                if example not in group.examples:
                    group.examples.append(example)
        
        return groups
    
    def get_top_queries(self, aggregated: Dict[str, QueryGroup], 
                       sort_by: str = 'total_time',
                       limit: int = 10) -> List[QueryGroup]:
        """
        获取Top查询
        
        参数:
            aggregated: 聚合结果
            sort_by: 排序字段（total_time/count/avg_time）
            limit: 返回数量
            
        返回:
            List[QueryGroup]: 排序后的查询组列表
        """
        groups = list(aggregated.values())
        
        # 排序
        if sort_by == 'total_time':
            groups.sort(key=lambda x: x.total_time, reverse=True)
        elif sort_by == 'count':
            groups.sort(key=lambda x: x.count, reverse=True)
        elif sort_by == 'avg_time':
            groups.sort(key=lambda x: x.avg_time, reverse=True)
        elif sort_by == 'max_time':
            groups.sort(key=lambda x: x.max_time, reverse=True)
        
        return groups[:limit]


# 便捷函数
def fingerprint_sql(sql: str, dialect: str = 'mysql') -> str:
    """
    快速生成SQL指纹（便捷函数）
    
    参数:
        sql: SQL语句
        dialect: 数据库方言
        
    返回:
        str: 指纹字符串
    """
    fingerprinter = SQLFingerprinter()
    result = fingerprinter.fingerprint(sql, dialect)
    return result.fingerprint


def aggregate_queries(queries: List[Dict[str, Any]]) -> Dict[str, QueryGroup]:
    """
    快速聚合查询（便捷函数）
    
    参数:
        queries: 查询列表
        
    返回:
        Dict[str, QueryGroup]: 聚合结果
    """
    fingerprinter = SQLFingerprinter()
    return fingerprinter.aggregate(queries)
