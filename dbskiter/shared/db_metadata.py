"""
数据库元数据服务 - 统一的数据库元数据查询接口

文件功能：提供跨模块的数据库元数据查询服务
主要类：
    - TableMetadata: 表元数据
    - DBMetadataService: 数据库元数据服务

使用示例：
    from dbskiter.shared.db_metadata import DBMetadataService

    service = DBMetadataService(connector)
    size = service.get_table_size("users")
    rows = service.get_table_row_count("users")
    indexes = service.get_table_indexes("users")

作者：AI Assistant
创建时间：2026-04-23
"""

import logging
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class TableMetadata:
    """表元数据"""
    name: str
    size_mb: Optional[float] = None
    row_count: Optional[int] = None
    data_mb: Optional[float] = None
    index_mb: Optional[float] = None
    engine: Optional[str] = None
    charset: Optional[str] = None
    create_time: Optional[str] = None
    update_time: Optional[str] = None


@dataclass
class IndexMetadata:
    """索引元数据"""
    name: str
    table_name: str
    columns: List[str] = field(default_factory=list)
    is_unique: bool = False
    is_primary: bool = False
    cardinality: Optional[int] = None
    index_type: str = "BTREE"  # 默认索引类型


class BaseMetadataProvider(ABC):
    """元数据提供者基类"""

    def __init__(self, connector):
        self.connector = connector

    @abstractmethod
    def get_table_size(self, table_name: str) -> Optional[float]:
        """获取表大小（MB）"""
        pass

    @abstractmethod
    def get_table_row_count(self, table_name: str) -> Optional[int]:
        """获取表行数"""
        pass

    @abstractmethod
    def get_table_indexes(self, table_name: str) -> List[IndexMetadata]:
        """获取表索引列表"""
        pass

    def _is_valid_identifier(self, name: str) -> bool:
        """验证标识符是否安全"""
        if not name or len(name) > 64:
            return False
        pattern = r'^[a-zA-Z_][a-zA-Z0-9_]*$'
        return bool(re.match(pattern, name))


class MySQLMetadataProvider(BaseMetadataProvider):
    """MySQL元数据提供者"""

    def get_table_size(self, table_name: str) -> Optional[float]:
        """获取MySQL表大小（MB）"""
        if not self._is_valid_identifier(table_name):
            logger.warning(f"无效的表名: {table_name}")
            return None

        try:
            result = self.connector.execute("""
                SELECT ROUND((data_length + index_length) / 1024 / 1024, 2)
                FROM information_schema.tables
                WHERE table_schema = DATABASE()
                AND table_name = :table_name
            """, {"table_name": table_name})

            if result.rows and result.rows[0][0]:
                return float(result.rows[0][0])
            return None
        except ConnectionError:
            logger.warning(f"获取表 {table_name} 大小时连接失败")
            return None
        except PermissionError:
            logger.warning(f"获取表 {table_name} 大小时权限不足")
            return None
        except (ValueError, TypeError) as e:
            logger.warning(f"获取表 {table_name} 大小时数据解析错误: {e}")
            return None

    def get_table_row_count(self, table_name: str) -> Optional[int]:
        """获取MySQL表行数"""
        if not self._is_valid_identifier(table_name):
            logger.warning(f"无效的表名: {table_name}")
            return None

        try:
            # 小表直接COUNT
            result = self.connector.execute(f"""
                SELECT COUNT(*)
                FROM {table_name}
                LIMIT 1000001
            """)

            if result.rows:
                count = int(result.rows[0][0])
                if count >= 1000000:
                    # 大表使用估算值
                    result = self.connector.execute("""
                        SELECT table_rows
                        FROM information_schema.tables
                        WHERE table_schema = DATABASE()
                        AND table_name = :table_name
                    """, {"table_name": table_name})
                    if result.rows and result.rows[0][0]:
                        return int(result.rows[0][0])
                return count
            return None
        except ConnectionError:
            logger.warning(f"获取表 {table_name} 行数时连接失败")
            return None
        except PermissionError:
            logger.warning(f"获取表 {table_name} 行数时权限不足")
            return None
        except (ValueError, TypeError) as e:
            logger.warning(f"获取表 {table_name} 行数时数据解析错误: {e}")
            return None

    def get_table_indexes(self, table_name: str) -> List[IndexMetadata]:
        """获取MySQL表索引"""
        if not self._is_valid_identifier(table_name):
            logger.warning(f"无效的表名: {table_name}")
            return []

        try:
            result = self.connector.execute("""
                SELECT
                    index_name,
                    column_name,
                    cardinality,
                    non_unique
                FROM information_schema.statistics
                WHERE table_schema = DATABASE()
                AND table_name = :table_name
                ORDER BY index_name, seq_in_index
            """, {"table_name": table_name})

            indexes = {}
            for row in result.rows:
                idx_name = row[0]
                if idx_name not in indexes:
                    indexes[idx_name] = {
                        "columns": [],
                        "cardinality": row[2],
                        "is_unique": row[3] == 0,
                        "is_primary": idx_name == "PRIMARY"
                    }
                indexes[idx_name]["columns"].append(row[1])

            return [
                IndexMetadata(
                    name=name,
                    table_name=table_name,
                    columns=info["columns"],
                    is_unique=info["is_unique"],
                    is_primary=info["is_primary"],
                    cardinality=info["cardinality"]
                )
                for name, info in indexes.items()
            ]
        except ConnectionError:
            logger.warning(f"获取表 {table_name} 索引时连接失败")
            return []
        except PermissionError:
            logger.warning(f"获取表 {table_name} 索引时权限不足")
            return []
        except ValueError as e:
            logger.warning(f"获取表 {table_name} 索引时数据错误: {e}")
            return []

    def get_table_metadata(self, table_name: str) -> Optional[TableMetadata]:
        """获取完整的MySQL表元数据"""
        if not self._is_valid_identifier(table_name):
            logger.warning(f"无效的表名: {table_name}")
            return None

        try:
            result = self.connector.execute("""
                SELECT
                    table_name,
                    ROUND((data_length + index_length) / 1024 / 1024, 2) as size_mb,
                    table_rows,
                    ROUND(data_length / 1024 / 1024, 2) as data_mb,
                    ROUND(index_length / 1024 / 1024, 2) as index_mb,
                    engine,
                    table_collation,
                    create_time,
                    update_time
                FROM information_schema.tables
                WHERE table_schema = DATABASE()
                AND table_name = :table_name
            """, {"table_name": table_name})

            if result.rows:
                row = result.rows[0]
                return TableMetadata(
                    name=row[0],
                    size_mb=row[1],
                    row_count=row[2],
                    data_mb=row[3],
                    index_mb=row[4],
                    engine=row[5],
                    charset=row[6],
                    create_time=str(row[7]) if row[7] else None,
                    update_time=str(row[8]) if row[8] else None
                )
            return None
        except ConnectionError:
            logger.warning(f"获取表 {table_name} 元数据时连接失败")
            return None
        except PermissionError:
            logger.warning(f"获取表 {table_name} 元数据时权限不足")
            return None
        except (ValueError, TypeError) as e:
            logger.warning(f"获取表 {table_name} 元数据时数据解析错误: {e}")
            return None


class OracleMetadataProvider(BaseMetadataProvider):
    """Oracle元数据提供者"""

    def get_table_size(self, table_name: str) -> Optional[float]:
        """获取Oracle表大小（MB）"""
        if not self._is_valid_identifier(table_name):
            logger.warning(f"无效的表名: {table_name}")
            return None

        try:
            # 首先尝试user_segments
            result = self.connector.execute("""
                SELECT ROUND(SUM(bytes) / 1024 / 1024, 2)
                FROM user_segments
                WHERE segment_name = UPPER(:1)
            """, (table_name,))

            if result.rows and result.rows[0][0]:
                return float(result.rows[0][0])

            # 尝试dba_segments
            result = self.connector.execute("""
                SELECT ROUND(SUM(bytes) / 1024 / 1024, 2)
                FROM dba_segments
                WHERE segment_name = UPPER(:1)
            """, (table_name,))

            if result.rows and result.rows[0][0]:
                return float(result.rows[0][0])
            return None
        except ConnectionError:
            logger.warning(f"获取表 {table_name} 大小时连接失败")
            return None
        except PermissionError:
            logger.warning(f"获取表 {table_name} 大小时权限不足")
            return None
        except (ValueError, TypeError) as e:
            logger.warning(f"获取表 {table_name} 大小时数据解析错误: {e}")
            return None

    def get_table_row_count(self, table_name: str) -> Optional[int]:
        """获取Oracle表行数"""
        if not self._is_valid_identifier(table_name):
            logger.warning(f"无效的表名: {table_name}")
            return None

        try:
            # 首先尝试统计信息
            result = self.connector.execute("""
                SELECT num_rows
                FROM user_tables
                WHERE table_name = UPPER(:1)
            """, (table_name,))

            if result.rows and result.rows[0][0]:
                return int(result.rows[0][0])

            # 小表直接COUNT
            result = self.connector.execute(f"""
                SELECT COUNT(*)
                FROM {table_name}
                WHERE ROWNUM <= 1000001
            """)

            if result.rows:
                count = int(result.rows[0][0])
                if count >= 1000000:
                    return None  # 大表不精确计数
                return count
            return None
        except ConnectionError:
            logger.warning(f"获取表 {table_name} 行数时连接失败")
            return None
        except PermissionError:
            logger.warning(f"获取表 {table_name} 行数时权限不足")
            return None
        except (ValueError, TypeError) as e:
            logger.warning(f"获取表 {table_name} 行数时数据解析错误: {e}")
            return None

    def get_table_indexes(self, table_name: str) -> List[IndexMetadata]:
        """获取Oracle表索引"""
        if not self._is_valid_identifier(table_name):
            logger.warning(f"无效的表名: {table_name}")
            return []

        try:
            result = self.connector.execute("""
                SELECT
                    index_name,
                    column_name,
                    uniqueness
                FROM user_ind_columns uic
                JOIN user_indexes ui ON uic.index_name = ui.index_name
                WHERE uic.table_name = UPPER(:1)
                ORDER BY uic.index_name, uic.column_position
            """, (table_name,))

            indexes = {}
            for row in result.rows:
                idx_name = row[0]
                if idx_name not in indexes:
                    indexes[idx_name] = {
                        "columns": [],
                        "is_unique": row[2] == "UNIQUE",
                        "is_primary": idx_name.endswith("_PK")
                    }
                indexes[idx_name]["columns"].append(row[1])

            return [
                IndexMetadata(
                    name=name,
                    table_name=table_name,
                    columns=info["columns"],
                    is_unique=info["is_unique"],
                    is_primary=info["is_primary"]
                )
                for name, info in indexes.items()
            ]
        except ConnectionError:
            logger.warning(f"获取表 {table_name} 索引时连接失败")
            return []
        except PermissionError:
            logger.warning(f"获取表 {table_name} 索引时权限不足")
            return []
        except ValueError as e:
            logger.warning(f"获取表 {table_name} 索引时数据错误: {e}")
            return []


class PostgreSQLMetadataProvider(BaseMetadataProvider):
    """PostgreSQL元数据提供者"""

    def get_table_size(self, table_name: str) -> Optional[float]:
        """获取PostgreSQL表大小（MB）"""
        if not self._is_valid_identifier(table_name):
            logger.warning(f"无效的表名: {table_name}")
            return None

        try:
            result = self.connector.execute("""
                SELECT ROUND((pg_total_relation_size(c.oid) / 1024.0 / 1024.0)::numeric, 2)
                FROM pg_class c
                JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE c.relname = :table_name
                AND n.nspname = 'public'
            """, {"table_name": table_name})

            if result.rows and result.rows[0][0]:
                return float(result.rows[0][0])
            return None
        except ConnectionError:
            logger.warning(f"获取表 {table_name} 大小时连接失败")
            return None
        except PermissionError:
            logger.warning(f"获取表 {table_name} 大小时权限不足")
            return None
        except (ValueError, TypeError) as e:
            logger.warning(f"获取表 {table_name} 大小时数据解析错误: {e}")
            return None

    def get_table_row_count(self, table_name: str) -> Optional[int]:
        """获取PostgreSQL表行数"""
        if not self._is_valid_identifier(table_name):
            logger.warning(f"无效的表名: {table_name}")
            return None

        try:
            # 首先尝试统计信息
            result = self.connector.execute("""
                SELECT n_live_tup
                FROM pg_stat_user_tables
                WHERE relname = :table_name
            """, {"table_name": table_name})

            if result.rows and result.rows[0][0]:
                return int(result.rows[0][0])

            # 小表直接COUNT
            result = self.connector.execute(f"""
                SELECT COUNT(*)
                FROM {table_name}
                LIMIT 1000001
            """)

            if result.rows:
                count = int(result.rows[0][0])
                if count >= 1000000:
                    return None
                return count
            return None
        except ConnectionError:
            logger.warning(f"获取表 {table_name} 行数时连接失败")
            return None
        except PermissionError:
            logger.warning(f"获取表 {table_name} 行数时权限不足")
            return None
        except (ValueError, TypeError) as e:
            logger.warning(f"获取表 {table_name} 行数时数据解析错误: {e}")
            return None

    def get_table_indexes(self, table_name: str) -> List[IndexMetadata]:
        """获取PostgreSQL表索引"""
        if not self._is_valid_identifier(table_name):
            logger.warning(f"无效的表名: {table_name}")
            return []

        try:
            result = self.connector.execute("""
                SELECT
                    indexname,
                    indexdef
                FROM pg_indexes
                WHERE tablename = :table_name
            """, {"table_name": table_name})

            indexes = []
            for row in result.rows:
                idx_name = row[0]
                idx_def = row[1]

                # 解析索引定义
                is_unique = "UNIQUE" in idx_def.upper()
                is_primary = idx_name.endswith("_pkey")

                indexes.append(IndexMetadata(
                    name=idx_name,
                    table_name=table_name,
                    is_unique=is_unique,
                    is_primary=is_primary
                ))

            return indexes
        except ConnectionError:
            logger.warning(f"获取表 {table_name} 索引时连接失败")
            return []
        except PermissionError:
            logger.warning(f"获取表 {table_name} 索引时权限不足")
            return []
        except ValueError as e:
            logger.warning(f"获取表 {table_name} 索引时数据错误: {e}")
            return []


class MSSQLMetadataProvider(BaseMetadataProvider):
    """SQL Server元数据提供者"""

    def get_table_size(self, table_name: str) -> Optional[float]:
        """获取SQL Server表大小（MB）"""
        if not self._is_valid_identifier(table_name):
            logger.warning(f"无效的表名: {table_name}")
            return None

        try:
            result = self.connector.execute("""
                SELECT
                    ROUND(SUM(a.total_pages) * 8.0 / 1024, 2) AS size_mb
                FROM sys.tables t
                INNER JOIN sys.indexes i ON t.object_id = i.object_id
                INNER JOIN sys.partitions p ON i.object_id = p.object_id AND i.index_id = p.index_id
                INNER JOIN sys.allocation_units a ON p.partition_id = a.container_id
                WHERE t.name = ?
                GROUP BY t.name
            """, (table_name,))

            if result.rows and result.rows[0][0]:
                return float(result.rows[0][0])
            return None
        except ConnectionError:
            logger.warning(f"获取表 {table_name} 大小时连接失败")
            return None
        except PermissionError:
            logger.warning(f"获取表 {table_name} 大小时权限不足")
            return None
        except (ValueError, TypeError) as e:
            logger.warning(f"获取表 {table_name} 大小时数据解析错误: {e}")
            return None

    def get_table_row_count(self, table_name: str) -> Optional[int]:
        """获取SQL Server表行数"""
        if not self._is_valid_identifier(table_name):
            logger.warning(f"无效的表名: {table_name}")
            return None

        try:
            # 使用sys.dm_db_partition_stats获取行数
            result = self.connector.execute("""
                SELECT SUM(p.rows)
                FROM sys.tables t
                INNER JOIN sys.indexes i ON t.object_id = i.object_id
                INNER JOIN sys.partitions p ON i.object_id = p.object_id AND i.index_id = p.index_id
                WHERE t.name = ?
                AND i.index_id IN (0, 1)
            """, (table_name,))

            if result.rows and result.rows[0][0]:
                return int(result.rows[0][0])
            return None
        except ConnectionError:
            logger.warning(f"获取表 {table_name} 行数时连接失败")
            return None
        except PermissionError:
            logger.warning(f"获取表 {table_name} 行数时权限不足")
            return None
        except (ValueError, TypeError) as e:
            logger.warning(f"获取表 {table_name} 行数时数据解析错误: {e}")
            return None

    def get_table_indexes(self, table_name: str) -> List[IndexMetadata]:
        """获取SQL Server表索引"""
        if not self._is_valid_identifier(table_name):
            logger.warning(f"无效的表名: {table_name}")
            return []

        try:
            result = self.connector.execute("""
                SELECT
                    i.name AS index_name,
                    c.name AS column_name,
                    i.is_unique,
                    i.is_primary_key,
                    ic.key_ordinal
                FROM sys.tables t
                INNER JOIN sys.indexes i ON t.object_id = i.object_id
                INNER JOIN sys.index_columns ic ON i.object_id = ic.object_id AND i.index_id = ic.index_id
                INNER JOIN sys.columns c ON ic.object_id = c.object_id AND ic.column_id = c.column_id
                WHERE t.name = ?
                ORDER BY i.name, ic.key_ordinal
            """, (table_name,))

            indexes = {}
            for row in result.rows:
                idx_name = row[0]
                column_name = row[1]
                is_unique = row[2]
                is_primary = row[3]

                if idx_name not in indexes:
                    indexes[idx_name] = {
                        "columns": [],
                        "is_unique": is_unique,
                        "is_primary": is_primary
                    }
                indexes[idx_name]["columns"].append(column_name)

            return [
                IndexMetadata(
                    name=name,
                    table_name=table_name,
                    columns=info["columns"],
                    is_unique=info["is_unique"],
                    is_primary=info["is_primary"]
                )
                for name, info in indexes.items()
            ]
        except ConnectionError:
            logger.warning(f"获取表 {table_name} 索引时连接失败")
            return []
        except PermissionError:
            logger.warning(f"获取表 {table_name} 索引时权限不足")
            return []
        except ValueError as e:
            logger.warning(f"获取表 {table_name} 索引时数据错误: {e}")
            return []


class ClickHouseMetadataProvider(BaseMetadataProvider):
    """ClickHouse元数据提供者"""

    def get_table_size(self, table_name: str) -> Optional[float]:
        """获取ClickHouse表大小（MB）"""
        if not self._is_valid_identifier(table_name):
            logger.warning(f"无效的表名: {table_name}")
            return None

        try:
            result = self.connector.execute(f"""
                SELECT ROUND(sum(bytes) / 1024 / 1024, 2)
                FROM system.parts
                WHERE table = '{table_name}'
                AND active = 1
            """)

            if result.rows and result.rows[0][0]:
                return float(result.rows[0][0])
            return None
        except Exception as e:
            logger.warning(f"获取表 {table_name} 大小时失败: {e}")
            return None

    def get_table_row_count(self, table_name: str) -> Optional[int]:
        """获取ClickHouse表行数"""
        if not self._is_valid_identifier(table_name):
            logger.warning(f"无效的表名: {table_name}")
            return None

        try:
            result = self.connector.execute(f"""
                SELECT sum(rows)
                FROM system.parts
                WHERE table = '{table_name}'
                AND active = 1
            """)

            if result.rows and result.rows[0][0]:
                return int(result.rows[0][0])
            return None
        except Exception as e:
            logger.warning(f"获取表 {table_name} 行数时失败: {e}")
            return None

    def get_table_indexes(self, table_name: str) -> List[IndexMetadata]:
        """获取ClickHouse表索引"""
        if not self._is_valid_identifier(table_name):
            logger.warning(f"无效的表名: {table_name}")
            return []

        try:
            result = self.connector.execute(f"""
                SELECT name, type
                FROM system.data_skipping_indices
                WHERE table = '{table_name}'
            """)

            indexes = []
            for row in result.rows:
                indexes.append(IndexMetadata(
                    name=row[0],
                    table_name=table_name,
                    index_type=row[1]
                ))

            return indexes
        except Exception as e:
            logger.warning(f"获取表 {table_name} 索引时失败: {e}")
            return []


class SQLiteMetadataProvider(BaseMetadataProvider):
    """SQLite元数据提供者"""

    def get_table_size(self, table_name: str) -> Optional[float]:
        """获取SQLite表大小（MB）"""
        if not self._is_valid_identifier(table_name):
            logger.warning(f"无效的表名: {table_name}")
            return None

        try:
            result = self.connector.execute(f"""
                SELECT ROUND((pgsize * (SELECT COUNT(*) FROM "{table_name}")) / 1024.0 / 1024.0, 2)
            """)

            if result.rows and result.rows[0][0]:
                return float(result.rows[0][0])
            return None
        except Exception as e:
            logger.warning(f"获取表 {table_name} 大小时失败: {e}")
            return None

    def get_table_row_count(self, table_name: str) -> Optional[int]:
        """获取SQLite表行数"""
        if not self._is_valid_identifier(table_name):
            logger.warning(f"无效的表名: {table_name}")
            return None

        try:
            result = self.connector.execute(f"""
                SELECT COUNT(*)
                FROM "{table_name}"
            """)

            if result.rows and result.rows[0][0]:
                return int(result.rows[0][0])
            return None
        except Exception as e:
            logger.warning(f"获取表 {table_name} 行数时失败: {e}")
            return None

    def get_table_indexes(self, table_name: str) -> List[IndexMetadata]:
        """获取SQLite表索引"""
        if not self._is_valid_identifier(table_name):
            logger.warning(f"无效的表名: {table_name}")
            return []

        try:
            result = self.connector.execute(f"""
                SELECT name, sql
                FROM sqlite_master
                WHERE type = 'index'
                AND tbl_name = '{table_name}'
            """)

            indexes = []
            for row in result.rows:
                idx_name = row[0]
                sql = row[1] or ""
                is_unique = "UNIQUE" in sql.upper()

                indexes.append(IndexMetadata(
                    name=idx_name,
                    table_name=table_name,
                    is_unique=is_unique
                ))

            return indexes
        except Exception as e:
            logger.warning(f"获取表 {table_name} 索引时失败: {e}")
            return []


class GenericMetadataProvider(BaseMetadataProvider):
    """
    通用元数据提供者

    通过标准 SQL 和 INFORMATION_SCHEMA 为任意 JDBC 兼容数据库
    提供基础元数据查询能力。

    使用示例：
        >>> provider = GenericMetadataProvider(connector)
        >>> size = provider.get_table_size("users")
        >>> rows = provider.get_table_row_count("users")
    """

    def get_table_size(self, table_name: str) -> Optional[float]:
        """获取表大小（MB）（通用实现）"""
        if not self._is_valid_identifier(table_name):
            logger.warning(f"无效的表名: {table_name}")
            return None

        queries = [
            # PostgreSQL 风格
            ("SELECT pg_total_relation_size(quote_ident($1)) / 1024.0 / 1024.0",
             (table_name,)),
            # MySQL 风格
            ("SELECT (data_length + index_length) / 1024.0 / 1024.0 "
             "FROM information_schema.tables "
             "WHERE table_schema = DATABASE() AND table_name = ?",
             (table_name,)),
            # 通用回退
            (f"SELECT COUNT(*) * 0.001 FROM {table_name}", ()),
        ]

        for sql, params in queries:
            try:
                result = self.connector.execute(sql, params)
                if result.rows and result.rows[0][0] is not None:
                    return float(result.rows[0][0])
            except Exception:
                continue

        return None

    def get_table_row_count(self, table_name: str) -> Optional[int]:
        """获取表行数（通用实现）"""
        if not self._is_valid_identifier(table_name):
            logger.warning(f"无效的表名: {table_name}")
            return None

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

    def get_table_indexes(self, table_name: str) -> List[IndexMetadata]:
        """获取表索引（通用实现）"""
        if not self._is_valid_identifier(table_name):
            logger.warning(f"无效的表名: {table_name}")
            return []

        try:
            result = self.connector.execute(
                "SELECT index_name FROM information_schema.statistics "
                "WHERE table_name = ?",
                (table_name,)
            )
            if result.rows:
                return [
                    IndexMetadata(
                        name=row[0],
                        table_name=table_name,
                        is_unique=False
                    )
                    for row in result.rows
                ]
        except Exception:
            pass

        return []


class DBMetadataService:
    """
    数据库元数据服务

    提供统一的数据库元数据查询接口，自动根据数据库方言选择对应的提供者

    使用示例：
        >>> service = DBMetadataService(connector)
        >>> size = service.get_table_size("users")
        >>> rows = service.get_table_row_count("users")
        >>> indexes = service.get_table_indexes("users")
    """

    def __init__(self, connector):
        """
        初始化元数据服务

        参数:
            connector: 数据库连接器
        """
        self.connector = connector
        self.dialect = connector.dialect.lower()
        self._provider = self._create_provider()
        logger.info(f"DBMetadataService 初始化完成 (dialect={self.dialect})")

    def _create_provider(self) -> BaseMetadataProvider:
        """创建对应数据库的元数据提供者"""
        if 'mysql' in self.dialect:
            return MySQLMetadataProvider(self.connector)
        elif 'oracle' in self.dialect:
            return OracleMetadataProvider(self.connector)
        elif 'postgresql' in self.dialect:
            return PostgreSQLMetadataProvider(self.connector)
        elif 'mssql' in self.dialect or 'sqlserver' in self.dialect:
            return MSSQLMetadataProvider(self.connector)
        elif 'clickhouse' in self.dialect:
            return ClickHouseMetadataProvider(self.connector)
        elif 'sqlite' in self.dialect:
            return SQLiteMetadataProvider(self.connector)
        else:
            logger.info(
                f"方言 '{self.dialect}' 未找到专用元数据提供者，"
                f"回退到 GenericMetadataProvider"
            )
            return GenericMetadataProvider(self.connector)

    def get_table_size(self, table_name: str) -> Optional[float]:
        """获取表大小（MB）"""
        return self._provider.get_table_size(table_name)

    def get_table_row_count(self, table_name: str) -> Optional[int]:
        """获取表行数"""
        return self._provider.get_table_row_count(table_name)

    def get_table_indexes(self, table_name: str) -> List[IndexMetadata]:
        """获取表索引列表"""
        return self._provider.get_table_indexes(table_name)

    def get_table_metadata(self, table_name: str) -> Optional[TableMetadata]:
        """获取完整的表元数据"""
        if hasattr(self._provider, 'get_table_metadata'):
            return self._provider.get_table_metadata(table_name)

        # 兼容处理
        size = self.get_table_size(table_name)
        rows = self.get_table_row_count(table_name)

        if size is not None or rows is not None:
            return TableMetadata(
                name=table_name,
                size_mb=size,
                row_count=rows
            )
        return None
