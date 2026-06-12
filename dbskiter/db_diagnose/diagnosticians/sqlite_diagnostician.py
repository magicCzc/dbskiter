"""
SQLite诊断器

提供SQLite数据库的专项诊断能力

文件功能：SQLite数据库诊断器实现
主要类：SQLiteDiagnostician - SQLite数据库诊断器

支持的诊断功能：
    - 慢查询分析（基于sqlite3的query planner）
    - 表统计信息分析
    - 索引使用分析
    - 数据库文件大小分析
    - 碎片分析
    - 完整性检查

依赖：
    - sqlite3 标准库
    - SQLite 3.8+

作者：AI Assistant
创建时间：2026-06-03
版本：1.0.0
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from dbskiter.shared.unified_connector import UnifiedConnector
from .base import BaseDiagnostician

logger = logging.getLogger(__name__)


class SQLiteDiagnostician(BaseDiagnostician):
    """
    SQLite数据库诊断器

    提供SQLite特有的诊断能力：
    - 慢查询分析（基于EXPLAIN QUERY PLAN）
    - 表统计信息
    - 索引使用分析
    - 数据库文件大小
    - 碎片分析
    - 完整性检查

    特性：
    - 利用SQLite内置统计表（sqlite_stat1）
    - 支持EXPLAIN QUERY PLAN分析
    - 支持PRAGMA命令获取元数据
    """

    def __init__(self, connector: UnifiedConnector):
        """
        初始化SQLite诊断器

        参数：
            connector: UnifiedConnector实例
        """
        super().__init__(connector)
        self._database_path = None

    def _get_database_path(self) -> Optional[str]:
        """
        获取数据库文件路径

        返回：
            Optional[str]: 数据库文件路径或None
        """
        if self._database_path is None:
            try:
                result = self.connector.execute("PRAGMA database_list")
                if result and result.rows:
                    for row in result.rows:
                        if row[1] == 'main':
                            self._database_path = row[2]
                            break
            except Exception as e:
                logger.warning(f"获取数据库路径失败: {e}")
        return self._database_path

    def analyze_slow_queries(
        self,
        limit: int = 20,
        min_time: float = 1.0
    ) -> Dict[str, Any]:
        """
        分析SQLite慢查询

        SQLite没有内置慢查询日志，通过分析查询计划识别潜在慢查询

        参数：
            limit: 返回条数限制
            min_time: 最小执行时间（秒）

        返回：
            Dict: 慢查询分析结果
        """
        try:
            # 获取所有表
            result = self.connector.execute("""
                SELECT name
                FROM sqlite_master
                WHERE type = 'table'
                AND name NOT LIKE 'sqlite_%'
            """)

            tables = [row[0] for row in result.rows] if result else []

            # 分析每个表的查询计划
            slow_queries = []
            for table in tables[:limit]:
                try:
                    # 分析全表扫描风险
                    result = self.connector.execute(f"""
                        EXPLAIN QUERY PLAN SELECT * FROM "{table}"
                    """)

                    plan_lines = []
                    uses_index = False
                    for row in result.rows if result else []:
                        plan_line = row[3] if len(row) > 3 else str(row)
                        plan_lines.append(plan_line)
                        if 'INDEX' in str(plan_line).upper():
                            uses_index = True

                    if not uses_index:
                        slow_queries.append({
                            "table": table,
                            "issue": "全表扫描风险",
                            "plan": "\n".join(plan_lines),
                            "recommendation": f"考虑为表 {table} 添加索引"
                        })

                except Exception as e:
                    logger.warning(f"分析表 {table} 失败: {e}")

            return self._create_result(
                success=True,
                message=f"分析了 {len(tables)} 个表，发现 {len(slow_queries)} 个潜在慢查询",
                data={
                    "total_tables": len(tables),
                    "slow_queries": slow_queries,
                    "tables_without_index": len(slow_queries)
                }
            )

        except Exception as e:
            logger.error(f"慢查询分析失败: {e}")
            return self._create_result(
                success=False,
                message=f"慢查询分析失败: {str(e)}",
                error=str(e)
            )

    def analyze_performance_metrics(
        self,
        duration_minutes: int = 10
    ) -> Dict[str, Any]:
        """
        分析SQLite性能指标

        参数：
            duration_minutes: 采集时长（分钟）

        返回：
            Dict: 性能分析结果
        """
        try:
            metrics = {}

            # 缓存命中率
            try:
                result = self.connector.execute("PRAGMA cache_size")
                cache_size = int(result.rows[0][0]) if result else 0
                metrics["cache_size_pages"] = cache_size
            except Exception as e:
                logger.warning(f"获取缓存大小失败: {e}")
                metrics["cache_size_pages"] = -1

            # 页面大小
            try:
                result = self.connector.execute("PRAGMA page_size")
                page_size = int(result.rows[0][0]) if result else 0
                metrics["page_size"] = page_size
            except Exception as e:
                logger.warning(f"获取页面大小失败: {e}")
                metrics["page_size"] = -1

            # 数据库大小
            try:
                result = self.connector.execute("PRAGMA page_count")
                page_count = int(result.rows[0][0]) if result else 0
                metrics["page_count"] = page_count
                metrics["database_size_bytes"] = page_count * page_size if page_size > 0 else 0
                metrics["database_size_pretty"] = self._format_bytes(
                    metrics["database_size_bytes"]
                )
            except Exception as e:
                logger.warning(f"获取页面数失败: {e}")
                metrics["page_count"] = -1

            # 空闲页面数
            try:
                result = self.connector.execute("PRAGMA freelist_count")
                freelist_count = int(result.rows[0][0]) if result else 0
                metrics["freelist_count"] = freelist_count
                metrics["freelist_bytes"] = freelist_count * page_size if page_size > 0 else 0
            except Exception as e:
                logger.warning(f"获取空闲页面数失败: {e}")
                metrics["freelist_count"] = -1

            # 日志模式
            try:
                result = self.connector.execute("PRAGMA journal_mode")
                metrics["journal_mode"] = result.rows[0][0] if result else "unknown"
            except Exception as e:
                logger.warning(f"获取日志模式失败: {e}")
                metrics["journal_mode"] = "unknown"

            # 同步模式
            try:
                result = self.connector.execute("PRAGMA synchronous")
                sync_value = int(result.rows[0][0]) if result else -1
                sync_modes = {0: "OFF", 1: "NORMAL", 2: "FULL", 3: "EXTRA"}
                metrics["synchronous"] = sync_modes.get(sync_value, f"UNKNOWN({sync_value})")
            except Exception as e:
                logger.warning(f"获取同步模式失败: {e}")
                metrics["synchronous"] = "unknown"

            return self._create_result(
                success=True,
                message="性能指标采集完成",
                data=metrics
            )

        except Exception as e:
            logger.error(f"性能指标分析失败: {e}")
            return self._create_result(
                success=False,
                message=f"性能指标分析失败: {str(e)}",
                error=str(e)
            )

    def get_database_stats(self) -> Dict[str, Any]:
        """
        获取SQLite数据库统计信息

        返回：
            Dict: 数据库统计信息
        """
        try:
            stats = {}

            # 表统计
            try:
                result = self.connector.execute("""
                    SELECT
                        name,
                        sql
                    FROM sqlite_master
                    WHERE type = 'table'
                    AND name NOT LIKE 'sqlite_%'
                """)

                tables = []
                for row in result.rows if result else []:
                    table_name = row[0]

                    # 获取行数
                    try:
                        count_result = self.connector.execute(
                            f'SELECT count(*) FROM "{table_name}"'
                        )
                        row_count = int(count_result.rows[0][0]) if count_result else 0
                    except Exception:
                        row_count = 0

                    # 获取列数
                    try:
                        pragma_result = self.connector.execute(
                            f'PRAGMA table_info("{table_name}")'
                        )
                        col_count = len(pragma_result.rows) if pragma_result else 0
                    except Exception:
                        col_count = 0

                    tables.append({
                        "name": table_name,
                        "row_count": row_count,
                        "column_count": col_count
                    })

                stats["tables"] = tables
                stats["table_count"] = len(tables)
            except Exception as e:
                logger.warning(f"获取表统计失败: {e}")
                stats["tables"] = []
                stats["table_count"] = 0

            # 索引统计
            try:
                result = self.connector.execute("""
                    SELECT
                        name,
                        tbl_name,
                        sql
                    FROM sqlite_master
                    WHERE type = 'index'
                    AND name NOT LIKE 'sqlite_%'
                """)

                indexes = []
                for row in result.rows if result else []:
                    indexes.append({
                        "name": row[0],
                        "table": row[1],
                        "sql": row[2]
                    })

                stats["indexes"] = indexes
                stats["index_count"] = len(indexes)
            except Exception as e:
                logger.warning(f"获取索引统计失败: {e}")
                stats["indexes"] = []
                stats["index_count"] = 0

            # 数据库文件信息
            db_path = self._get_database_path()
            if db_path and db_path != ':memory:':
                import os
                try:
                    file_size = os.path.getsize(db_path)
                    stats["file_size"] = file_size
                    stats["file_size_pretty"] = self._format_bytes(file_size)
                except Exception as e:
                    logger.warning(f"获取文件大小失败: {e}")

            return self._create_result(
                success=True,
                message=f"获取到 {stats.get('table_count', 0)} 个表，{stats.get('index_count', 0)} 个索引",
                data=stats
            )

        except Exception as e:
            logger.error(f"数据库统计获取失败: {e}")
            return self._create_result(
                success=False,
                message=f"数据库统计获取失败: {str(e)}",
                error=str(e)
            )

    def analyze_indexes(self) -> Dict[str, Any]:
        """
        分析SQLite索引使用情况

        返回：
            Dict: 索引分析结果
        """
        try:
            # 获取所有索引
            result = self.connector.execute("""
                SELECT
                    name,
                    tbl_name,
                    sql
                FROM sqlite_master
                WHERE type = 'index'
                AND name NOT LIKE 'sqlite_%'
            """)

            indexes = []
            missing_indexes = []

            # 分析每个表的索引覆盖
            tables_result = self.connector.execute("""
                SELECT name
                FROM sqlite_master
                WHERE type = 'table'
                AND name NOT LIKE 'sqlite_%'
            """)

            tables = [row[0] for row in tables_result.rows] if tables_result else []

            for table in tables:
                try:
                    # 获取表的索引
                    index_result = self.connector.execute(f"""
                        SELECT name
                        FROM sqlite_master
                        WHERE type = 'index'
                        AND tbl_name = '{table}'
                        AND name NOT LIKE 'sqlite_%'
                    """)

                    table_indexes = [row[0] for row in index_result.rows] if index_result else []

                    if not table_indexes:
                        # 获取行数判断是否需要索引
                        count_result = self.connector.execute(
                            f'SELECT count(*) FROM "{table}"'
                        )
                        row_count = int(count_result.rows[0][0]) if count_result else 0

                        if row_count > 1000:
                            missing_indexes.append({
                                "table": table,
                                "row_count": row_count,
                                "issue": "大表缺少索引"
                            })

                except Exception as e:
                    logger.warning(f"分析表 {table} 索引失败: {e}")

            for row in result.rows if result else []:
                indexes.append({
                    "name": row[0],
                    "table": row[1],
                    "sql": row[2]
                })

            return self._create_result(
                success=True,
                message=f"发现 {len(indexes)} 个索引，{len(missing_indexes)} 个表可能缺少索引",
                data={
                    "indexes": indexes,
                    "missing_indexes": missing_indexes,
                    "total_indexes": len(indexes),
                    "missing_count": len(missing_indexes)
                }
            )

        except Exception as e:
            logger.error(f"索引分析失败: {e}")
            return self._create_result(
                success=False,
                message=f"索引分析失败: {str(e)}",
                error=str(e)
            )

    def check_integrity(self) -> Dict[str, Any]:
        """
        检查SQLite数据库完整性

        返回：
            Dict: 完整性检查结果
        """
        try:
            result = self.connector.execute("PRAGMA integrity_check")

            if result and result.rows:
                status = result.rows[0][0]
                is_ok = status == 'ok'

                return self._create_result(
                    success=True,
                    message=f"完整性检查: {status}",
                    data={
                        "status": status,
                        "is_ok": is_ok
                    }
                )
            else:
                return self._create_result(
                    success=False,
                    message="完整性检查无结果",
                    error="no result"
                )

        except Exception as e:
            logger.error(f"完整性检查失败: {e}")
            return self._create_result(
                success=False,
                message=f"完整性检查失败: {str(e)}",
                error=str(e)
            )

    def analyze_fragmentation(self) -> Dict[str, Any]:
        """
        分析SQLite数据库碎片

        返回：
            Dict: 碎片分析结果
        """
        try:
            # 获取页面统计
            result = self.connector.execute("PRAGMA page_count")
            page_count = int(result.rows[0][0]) if result else 0

            result = self.connector.execute("PRAGMA freelist_count")
            freelist_count = int(result.rows[0][0]) if result else 0

            # 计算碎片率
            if page_count > 0:
                fragmentation_rate = (freelist_count / page_count) * 100
            else:
                fragmentation_rate = 0

            return self._create_result(
                success=True,
                message=f"碎片率: {fragmentation_rate:.2f}%",
                data={
                    "page_count": page_count,
                    "freelist_count": freelist_count,
                    "fragmentation_rate": round(fragmentation_rate, 2),
                    "needs_vacuum": fragmentation_rate > 20
                }
            )

        except Exception as e:
            logger.error(f"碎片分析失败: {e}")
            return self._create_result(
                success=False,
                message=f"碎片分析失败: {str(e)}",
                error=str(e)
            )

    def analyze_index_usage(self) -> Dict[str, Any]:
        """
        分析SQLite索引使用情况

        SQLite索引类型:
        - 普通索引: CREATE INDEX
        - 唯一索引: UNIQUE INDEX
        - 主键索引: INTEGER PRIMARY KEY (行ID别名)
        - 部分索引: 带WHERE条件的索引

        返回:
            Dict: 索引使用分析结果
        """
        try:
            # 获取所有索引
            result = self.connector.execute("""
                SELECT
                    name,
                    tbl_name,
                    sql,
                    origin
                FROM sqlite_master
                WHERE type = 'index'
                AND name NOT LIKE 'sqlite_%'
            """)

            indexes = []
            for row in result.rows if result else []:
                indexes.append({
                    "name": row[0],
                    "table": row[1],
                    "sql": row[2],
                    "origin": row[3] or "c"
                })

            # 检测冗余索引(完全重复的索引)
            redundant_indexes = []
            try:
                # 获取索引的列信息
                index_columns = {}
                for idx in indexes:
                    idx_name = idx["name"]
                    table_name = idx["table"]
                    try:
                        col_result = self.connector.execute(
                            f'PRAGMA index_info("{idx_name}")'
                        )
                        columns = [row[2] for row in col_result.rows] if col_result else []
                        key = (table_name, tuple(columns))
                        if key in index_columns:
                            redundant_indexes.append({
                                "table": table_name,
                                "redundant_index": idx_name,
                                "kept_index": index_columns[key],
                                "columns": columns
                            })
                        else:
                            index_columns[key] = idx_name
                    except Exception as e:
                        logger.warning(f"获取索引 {idx_name} 列信息失败: {e}")
            except Exception as e:
                logger.warning(f"检测冗余索引失败: {e}")

            # 检测缺少主键的表
            missing_pk = []
            try:
                result = self.connector.execute("""
                    SELECT name
                    FROM sqlite_master
                    WHERE type = 'table'
                    AND name NOT LIKE 'sqlite_%'
                """)

                for row in result.rows if result else []:
                    table_name = row[0]
                    try:
                        # 检查是否有INTEGER PRIMARY KEY
                        col_result = self.connector.execute(
                            f'PRAGMA table_info("{table_name}")'
                        )
                        has_pk = False
                        row_count = 0

                        for col in col_result.rows if col_result else []:
                            if col[5] == 1:  # pk column
                                has_pk = True
                                break

                        # 获取行数
                        count_result = self.connector.execute(
                            f'SELECT count(*) FROM "{table_name}"'
                        )
                        row_count = int(count_result.rows[0][0]) if count_result else 0

                        if not has_pk and row_count > 1000:
                            missing_pk.append({
                                "table": table_name,
                                "row_count": row_count,
                                "issue": "表缺少显式主键",
                                "suggestion": f"建议添加 INTEGER PRIMARY KEY: ALTER TABLE {table_name} ADD COLUMN id INTEGER PRIMARY KEY AUTOINCREMENT"
                            })
                    except Exception as e:
                        logger.warning(f"分析表 {table_name} 主键失败: {e}")
            except Exception as e:
                logger.warning(f"检测缺少主键的表失败: {e}")

            # 检测可能缺少索引的表(基于行数和查询模式)
            missing_indexes = []
            try:
                result = self.connector.execute("""
                    SELECT name
                    FROM sqlite_master
                    WHERE type = 'table'
                    AND name NOT LIKE 'sqlite_%'
                """)

                for row in result.rows if result else []:
                    table_name = row[0]
                    try:
                        # 获取表的索引数量
                        idx_result = self.connector.execute(
                            f'PRAGMA index_list("{table_name}")'
                        )
                        idx_count = len(idx_result.rows) if idx_result else 0

                        # 获取行数
                        count_result = self.connector.execute(
                            f'SELECT count(*) FROM "{table_name}"'
                        )
                        row_count = int(count_result.rows[0][0]) if count_result else 0

                        # 大表缺少索引
                        if row_count > 10000 and idx_count == 0:
                            missing_indexes.append({
                                "table": table_name,
                                "row_count": row_count,
                                "index_count": idx_count,
                                "issue": "大表缺少任何索引"
                            })
                    except Exception as e:
                        logger.warning(f"分析表 {table_name} 索引覆盖失败: {e}")
            except Exception as e:
                logger.warning(f"检测缺少索引的表失败: {e}")

            # 计算健康评分
            health_score = 100
            if redundant_indexes:
                health_score -= min(len(redundant_indexes) * 5, 20)
            if missing_pk:
                health_score -= min(len(missing_pk) * 3, 15)
            if missing_indexes:
                health_score -= min(len(missing_indexes) * 5, 25)
            health_score = max(health_score, 0)

            return self._create_result(
                success=True,
                message=f"发现 {len(indexes)} 个索引，{len(redundant_indexes)} 个冗余索引，{len(missing_pk)} 个表缺少主键，{len(missing_indexes)} 个表缺少索引",
                data={
                    "indexes": indexes,
                    "redundant_indexes": redundant_indexes,
                    "missing_pk": missing_pk,
                    "missing_indexes": missing_indexes,
                    "total_indexes": len(indexes),
                    "redundant_count": len(redundant_indexes),
                    "missing_pk_count": len(missing_pk),
                    "missing_count": len(missing_indexes),
                    "health_score": health_score,
                    "db_type": "SQLite"
                }
            )

        except Exception as e:
            logger.error(f"索引使用分析失败: {e}")
            return self._create_result(
                success=False,
                message=f"索引使用分析失败: {str(e)}",
                error=str(e)
            )
