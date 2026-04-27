"""
SQL缓存失效管理模块

文件功能：提供表级缓存失效机制，数据变更时自动清除相关缓存
主要类：CacheInvalidator - 缓存失效管理器
"""
from typing import Dict, Any, List, Optional, Set
import re
import logging

logger = logging.getLogger(__name__)


class TableExtractor:
    """
    SQL表名提取器
    
    从SQL语句中提取涉及的表名
    """
    
    # SQL表名提取正则模式
    TABLE_PATTERNS = {
        'SELECT': [
            r'FROM\s+(\w+)',           # FROM table
            r'JOIN\s+(\w+)',           # JOIN table
        ],
        'INSERT': [
            r'INTO\s+(\w+)',           # INSERT INTO table
        ],
        'UPDATE': [
            r'UPDATE\s+(\w+)',         # UPDATE table
        ],
        'DELETE': [
            r'FROM\s+(\w+)',           # DELETE FROM table
        ],
        'CREATE': [
            r'TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(\w+)',  # CREATE TABLE
        ],
        'DROP': [
            r'TABLE\s+(?:IF\s+EXISTS\s+)?(\w+)',        # DROP TABLE
        ],
        'ALTER': [
            r'TABLE\s+(\w+)',          # ALTER TABLE
        ],
        'TRUNCATE': [
            r'TABLE\s+(\w+)',          # TRUNCATE TABLE
        ]
    }
    
    @classmethod
    def extract_tables(cls, sql: str) -> Set[str]:
        """
        从SQL中提取表名
        
        参数:
            sql: SQL语句
            
        返回:
            Set[str]: 表名集合
            
        示例:
            >>> TableExtractor.extract_tables("SELECT * FROM users JOIN orders ON users.id = orders.user_id")
            {'users', 'orders'}
        """
        if not sql:
            return set()
        
        tables = set()
        sql_upper = sql.upper()
        
        # 确定SQL类型
        sql_type = None
        for stmt_type in cls.TABLE_PATTERNS.keys():
            if sql_upper.startswith(stmt_type):
                sql_type = stmt_type
                break
        
        if not sql_type:
            return tables
        
        # 应用对应类型的正则
        patterns = cls.TABLE_PATTERNS.get(sql_type, [])
        for pattern in patterns:
            matches = re.findall(pattern, sql_upper)
            tables.update(matches)
        
        return tables
    
    @classmethod
    def is_write_operation(cls, sql: str) -> bool:
        """
        判断是否为写操作
        
        参数:
            sql: SQL语句
            
        返回:
            bool: 是否为写操作
        """
        if not sql:
            return False
        
        write_operations = {'INSERT', 'UPDATE', 'DELETE', 'CREATE', 'DROP', 'ALTER', 'TRUNCATE'}
        first_word = sql.strip().split()[0].upper()
        
        return first_word in write_operations


class CacheInvalidator:
    """
    缓存失效管理器
    
    管理SQL与表的映射关系，数据变更时自动失效相关缓存
    
    特性：
    1. 自动提取SQL涉及的表
    2. 建立表到缓存键的索引
    3. 写操作时自动失效相关缓存
    4. 支持手动失效指定表
    
    使用示例：
        >>> invalidator = CacheInvalidator(cache_manager)
        >>> invalidator.track_query("SELECT * FROM users", cache_key)
        >>> invalidator.invalidate_on_write("UPDATE users SET name = 'new'")
        # 自动清除users表相关的所有缓存
    """
    
    def __init__(self, cache_manager):
        """
        初始化缓存失效管理器
        
        参数:
            cache_manager: SQLCacheManager实例
        """
        self.cache_manager = cache_manager
        # 表到缓存键的映射: {table_name: set(cache_keys)}
        self._table_index: Dict[str, Set[str]] = {}
        # 缓存键到表的映射: {cache_key: set(table_names)}
        self._key_to_tables: Dict[str, Set[str]] = {}
    
    def track_query(self, sql: str, cache_key: str) -> Set[str]:
        """
        跟踪查询，建立表到缓存的映射
        
        参数:
            sql: SQL语句
            cache_key: 缓存键
            
        返回:
            Set[str]: 涉及的表名
        """
        tables = TableExtractor.extract_tables(sql)
        
        if not tables:
            return tables
        
        # 更新索引
        for table in tables:
            if table not in self._table_index:
                self._table_index[table] = set()
            self._table_index[table].add(cache_key)
        
        # 反向索引
        self._key_to_tables[cache_key] = tables
        
        logger.debug(f"跟踪查询: {cache_key[:16]}... 涉及表: {tables}")
        return tables
    
    def invalidate_on_write(self, sql: str) -> int:
        """
        写操作时失效相关缓存
        
        参数:
            sql: 写操作SQL
            
        返回:
            int: 失效的缓存数量
        """
        if not TableExtractor.is_write_operation(sql):
            return 0
        
        tables = TableExtractor.extract_tables(sql)
        return self.invalidate_tables(tables)
    
    def invalidate_tables(self, tables: Set[str]) -> int:
        """
        失效指定表的所有缓存
        
        参数:
            tables: 表名集合
            
        返回:
            int: 失效的缓存数量
        """
        keys_to_remove = set()
        
        for table in tables:
            if table in self._table_index:
                keys_to_remove.update(self._table_index[table])
                logger.info(f"失效表 '{table}' 的缓存: {len(self._table_index[table])} 条")
                del self._table_index[table]
        
        # 从缓存中删除
        count = 0
        for key in keys_to_remove:
            # 从缓存管理器中删除
            if hasattr(self.cache_manager, '_cache') and key in self.cache_manager._cache:
                del self.cache_manager._cache[key]
                count += 1
            
            # 清理反向索引
            if key in self._key_to_tables:
                del self._key_to_tables[key]
        
        if count > 0:
            logger.info(f"共失效 {count} 条缓存")
        
        return count
    
    def invalidate_table(self, table: str) -> int:
        """
        失效单个表的所有缓存
        
        参数:
            table: 表名
            
        返回:
            int: 失效的缓存数量
        """
        return self.invalidate_tables({table})
    
    def get_table_stats(self) -> Dict[str, Any]:
        """
        获取表级缓存统计
        
        返回:
            Dict: 统计信息
        """
        return {
            "tracked_tables": len(self._table_index),
            "tracked_queries": len(self._key_to_tables),
            "table_details": {
                table: len(keys)
                for table, keys in self._table_index.items()
            }
        }
    
    def clear_index(self):
        """清除所有索引"""
        self._table_index.clear()
        self._key_to_tables.clear()
        logger.info("缓存失效索引已清除")


class SmartCachedExecutor:
    """
    智能缓存执行器（带自动失效）
    
    在执行写操作时自动失效相关缓存
    """
    
    def __init__(
        self,
        executor,
        cache_manager,
        enable_cache: bool = True,
        enable_auto_invalidate: bool = True
    ):
        self.executor = executor
        self.cache_manager = cache_manager
        self.enable_cache = enable_cache
        self.enable_auto_invalidate = enable_auto_invalidate
        
        if enable_auto_invalidate:
            self.invalidator = CacheInvalidator(cache_manager)
        else:
            self.invalidator = None
    
    def execute(
        self,
        sql: str,
        params: Optional[Dict] = None,
        use_cache: bool = True
    ) -> Any:
        """
        执行SQL（带智能缓存）
        
        参数:
            sql: SQL语句
            params: SQL参数
            use_cache: 是否使用缓存
        """
        # 写操作：先失效缓存，再执行
        if self.enable_auto_invalidate and TableExtractor.is_write_operation(sql):
            invalidated = self.invalidator.invalidate_on_write(sql)
            if invalidated > 0:
                logger.info(f"写操作前失效 {invalidated} 条缓存")
        
        # 读操作：使用缓存
        if self.enable_cache and use_cache and not TableExtractor.is_write_operation(sql):
            cache_key = self._generate_cache_key(sql, params)
            
            # 尝试从缓存获取
            cached_result = self.cache_manager.get(sql, params)
            if cached_result is not None:
                return cached_result
            
            # 执行并缓存
            result = self.executor.execute(sql, params)
            self.cache_manager.set(sql, result, params)
            
            # 跟踪查询（用于后续失效）
            if self.invalidator:
                self.invalidator.track_query(sql, cache_key)
            
            return result
        
        # 直接执行（写操作或不使用缓存）
        return self.executor.execute(sql, params)
    
    def _generate_cache_key(self, sql: str, params: Optional[Dict] = None) -> str:
        """生成缓存键"""
        import hashlib
        normalized_sql = " ".join(sql.split())
        if params:
            key_str = f"{normalized_sql}:{sorted(params.items())}"
        else:
            key_str = normalized_sql
        return hashlib.md5(key_str.encode()).hexdigest()
    
    def get_invalidator_stats(self) -> Dict[str, Any]:
        """获取失效器统计"""
        if self.invalidator:
            return self.invalidator.get_table_stats()
        return {"status": "disabled"}
