"""
数据库表结构动态检测工具

文件功能：提供动态检测数据库表结构的能力，避免硬编码版本依赖
主要类：SchemaDetector

特性：
    1. 动态列名检测：自动检测表中存在的列
    2. 动态表检测：自动检测可访问的表和视图
    3. 缓存机制：避免重复查询
    4. 多数据库支持：MySQL、Oracle、PostgreSQL

作者: AI Assistant
创建时间: 2026-04-27
"""

import logging
from typing import List, Optional, Dict, Set
from functools import lru_cache

from dbskiter.shared.unified_connector import UnifiedConnector

logger = logging.getLogger(__name__)


class SchemaDetector:
    """
    数据库表结构动态检测器

    自动检测数据库表结构，避免硬编码版本依赖
    """

    def __init__(self, connector: UnifiedConnector):
        """
        初始化检测器

        参数:
            connector: 数据库连接器
        """
        self.connector = connector
        self.dialect = connector.dialect.lower() if connector else ""
        self._cache: Dict[str, any] = {}

    def get_column_name(self, table: str, candidates: List[str],
                       schema: Optional[str] = None) -> Optional[str]:
        """
        动态检测表中存在的列名

        参数:
            table: 表名
            candidates: 候选列名列表（按优先级排序）
            schema: 数据库/schema名（可选）

        返回:
            第一个存在的列名，或 None

        示例:
            >>> detector.get_column_name(
            ...     'events_statements_summary_by_digest',
            ...     ['DIGEST_TEXT', 'SQL_TEXT'],
            ...     'performance_schema'
            ... )
            'DIGEST_TEXT'
        """
        cache_key = f"column:{schema or 'default'}.{table}:{','.join(candidates)}"

        if cache_key in self._cache:
            result = self._cache[cache_key]
            return result if result else None

        try:
            for column in candidates:
                if self._check_column_exists(table, column, schema):
                    self._cache[cache_key] = column
                    logger.info(f"检测到列名: {schema}.{table}.{column}" if schema else f"检测到列名: {table}.{column}")
                    return column

            self._cache[cache_key] = None
            logger.warning(f"未找到候选列: {table}.{candidates}")
            return None

        except Exception as e:
            logger.warning(f"列名检测失败: {e}")
            self._cache[cache_key] = None
            return None

    def _check_column_exists(self, table: str, column: str,
                            schema: Optional[str] = None) -> bool:
        """
        检查列是否存在

        参数:
            table: 表名
            column: 列名
            schema: 数据库/schema名

        返回:
            列是否存在
        """
        try:
            if "mysql" in self.dialect:
                return self._check_column_mysql(table, column, schema)
            elif "oracle" in self.dialect:
                return self._check_column_oracle(table, column, schema)
            elif "postgresql" in self.dialect:
                return self._check_column_postgres(table, column, schema)
            else:
                # 通用方法：尝试查询
                return self._check_column_generic(table, column, schema)

        except Exception as e:
            logger.debug(f"检查列存在失败: {e}")
            return False

    def _check_column_mysql(self, table: str, column: str,
                           schema: Optional[str] = None) -> bool:
        """MySQL 列检测"""
        schema = schema or self.connector.database

        result = self.connector.execute("""
            SELECT COUNT(*) FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = %s
            AND TABLE_NAME = %s
            AND COLUMN_NAME = %s
        """, (schema, table, column))

        return result.rows and result.rows[0][0] > 0

    def _check_column_oracle(self, table: str, column: str,
                            schema: Optional[str] = None) -> bool:
        """Oracle 列检测"""
        schema = schema or self.connector.username.upper()

        # Oracle 表名可能是 v$ 视图，需要特殊处理
        if table.startswith('v$') or table.startswith('gv$'):
            # 对于 v$ 视图，直接尝试查询
            return self._check_column_generic(table, column, schema)

        result = self.connector.execute("""
            SELECT COUNT(*) FROM all_tab_columns
            WHERE owner = :owner
            AND table_name = :table_name
            AND column_name = :column_name
        """, {"owner": schema.upper(), "table_name": table.upper(), "column_name": column.upper()})

        return result.rows and result.rows[0][0] > 0

    def _check_column_postgres(self, table: str, column: str,
                              schema: Optional[str] = None) -> bool:
        """PostgreSQL 列检测"""
        schema = schema or 'public'

        result = self.connector.execute("""
            SELECT COUNT(*) FROM information_schema.columns
            WHERE table_schema = %s
            AND table_name = %s
            AND column_name = %s
        """, (schema, table, column))

        return result.rows and result.rows[0][0] > 0

    def _check_column_generic(self, table: str, column: str,
                             schema: Optional[str] = None) -> bool:
        """通用列检测（尝试查询）"""
        try:
            full_table = f"{schema}.{table}" if schema else table
            result = self.connector.execute(
                f"SELECT {column} FROM {full_table} WHERE ROWNUM = 0"
            )
            return True
        except Exception:
            return False

    def get_available_tables(self, schema: Optional[str] = None) -> Set[str]:
        """
        获取可用的表列表

        参数:
            schema: 数据库/schema名

        返回:
            表名集合
        """
        cache_key = f"tables:{schema or 'default'}"

        if cache_key in self._cache:
            return self._cache[cache_key]

        tables = set()

        try:
            if "mysql" in self.dialect:
                tables = self._get_tables_mysql(schema)
            elif "oracle" in self.dialect:
                tables = self._get_tables_oracle(schema)
            elif "postgresql" in self.dialect:
                tables = self._get_tables_postgres(schema)

        except Exception as e:
            logger.warning(f"获取表列表失败: {e}")

        self._cache[cache_key] = tables
        return tables

    def _get_tables_mysql(self, schema: Optional[str] = None) -> Set[str]:
        """MySQL 表列表"""
        schema = schema or self.connector.database

        result = self.connector.execute("""
            SELECT TABLE_NAME FROM information_schema.TABLES
            WHERE TABLE_SCHEMA = %s
        """, (schema,))

        return {row[0] for row in result.rows} if result.rows else set()

    def _get_tables_oracle(self, schema: Optional[str] = None) -> Set[str]:
        """Oracle 表列表"""
        schema = schema or self.connector.username.upper()

        result = self.connector.execute("""
            SELECT table_name FROM all_tables WHERE owner = :owner
            UNION
            SELECT view_name FROM all_views WHERE owner = :owner
        """, {"owner": schema.upper()})

        return {row[0] for row in result.rows} if result.rows else set()

    def _get_tables_postgres(self, schema: Optional[str] = None) -> Set[str]:
        """PostgreSQL 表列表"""
        schema = schema or 'public'

        result = self.connector.execute("""
            SELECT table_name FROM information_schema.tables
            WHERE table_schema = %s
        """, (schema,))

        return {row[0] for row in result.rows} if result.rows else set()

    def clear_cache(self):
        """清除缓存"""
        self._cache.clear()
        logger.info("SchemaDetector 缓存已清除")
