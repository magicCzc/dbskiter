"""
space_analyzer mixin for DiagnoseSkill

Auto-extracted from skill.py.
"""

import logging
logger = logging.getLogger(__name__)
from typing import List, Dict, Any, Optional, Set, Tuple

from dbskiter.db_diagnose.models import (
    ErrorCode,
    DiagnoseLevel,
    DiagnoseType,
    DatabaseType,
    DiagnoseConfig,
    DiagnoseResult,
    IndexSuggestion,
    SlowQuery,
    PerformanceMetrics,
    TableDiagnoseResult,
    DiagnoseReport,
)
from dbskiter.shared.error_handler import (
    create_success_response,
    create_error_response,
)


class SpaceAnalyzerMixin:
    """space_analyzer for DiagnoseSkill"""

    def analyze_space(self, top_n: int = 20, min_size_mb: int = 100, database: Optional[str] = None) -> Dict[str, Any]:
        """
        空间诊断（已接入多步骤计时）

        参数:
            top_n: TOP N大表
            min_size_mb: 最小表大小(MB)
            database: 指定数据库名（可选，默认使用当前连接的数据库）

        返回:
            Dict: 空间分析结果，包含 _execution_time 步骤耗时
        """
        from dbskiter.shared.execution_timer import ExecutionTimer
        timer = ExecutionTimer().start()

        try:
            with timer.step("select_engine", "选择数据库引擎适配"):
                if 'mysql' in self.dialect:
                    result = self._analyze_mysql_space(top_n, min_size_mb, database)
                elif 'oracle' in self.dialect:
                    result = self._analyze_oracle_space(top_n, min_size_mb)
                elif 'postgresql' in self.dialect:
                    result = self._analyze_postgresql_space(top_n, min_size_mb)
                elif 'mssql' in self.dialect or 'sqlserver' in self.dialect:
                    result = self._analyze_mssql_space(top_n, min_size_mb)
                elif 'clickhouse' in self.dialect:
                    result = self._analyze_clickhouse_space(top_n, min_size_mb)
                elif 'sqlite' in self.dialect:
                    result = self._analyze_sqlite_space(top_n, min_size_mb)
                else:
                    result = create_error_response(
                        f"空间分析暂不支持 {self.dialect}",
                        ErrorCode.UNSUPPORTED_SQL
                    )

            with timer.step("format_result", "转换并封装结果"):
                if isinstance(result, dict) and "_execution_time" not in result:
                    pass

            result["_execution_time"] = timer.to_summary()
            return result
        except Exception as e:
            logger.error(f"空间分析失败: {e}")
            return create_error_response(str(e), ErrorCode.UNKNOWN_ERROR)


    def _analyze_mysql_space(self, top_n: int, min_size_mb: int, database: Optional[str] = None) -> Dict[str, Any]:
        """MySQL空间分析"""
        try:
            # 获取数据库名（优先使用参数传入的数据库名）
            if database:
                current_db = database
                logger.info(f"使用指定数据库进行空间分析: {current_db}")
            else:
                # 获取当前数据库名
                db_result = self.connector.execute("SELECT DATABASE()")
                current_db = db_result.rows[0][0] if db_result.rows and db_result.rows[0][0] else None
                logger.info(f"使用当前连接的数据库进行空间分析: {current_db}")

            if not current_db:
                return create_error_response(
                    "无法获取当前数据库名",
                    ErrorCode.UNKNOWN_ERROR
                )

            # 获取表空间信息
            result = self.connector.execute("""
                SELECT 
                    table_name,
                    ROUND(data_length / 1024 / 1024, 2) as data_mb,
                    ROUND(index_length / 1024 / 1024, 2) as index_mb,
                    ROUND((data_length + index_length) / 1024 / 1024, 2) as total_mb,
                    table_rows,
                    engine
                FROM information_schema.TABLES
                WHERE table_schema = :db
                    AND (data_length + index_length) / 1024 / 1024 >= :min_size
                ORDER BY (data_length + index_length) DESC
                LIMIT :limit
            """, {"db": current_db, "min_size": min_size_mb, "limit": top_n})

            tables = []
            total_data = 0
            total_index = 0

            for row in result.rows:
                tables.append({
                    "table": row[0],
                    "data_mb": row[1],
                    "index_mb": row[2],
                    "size_mb": row[3],
                    "rows": row[4],
                    "engine": row[5],
                    "fragmentation": 0  # 需要额外计算
                })
                total_data += row[1] or 0
                total_index += row[2] or 0

            return create_success_response(
                message=f"获取到 {len(tables)} 个大表",
                data={
                    "total_space": {
                        "total_gb": round((total_data + total_index) / 1024, 2),
                        "data_gb": round(total_data / 1024, 2),
                        "index_gb": round(total_index / 1024, 2)
                    },
                    "large_tables": tables,
                    "suggestions": []
                }
            )
        except Exception as e:
            return create_error_response(str(e), ErrorCode.UNKNOWN_ERROR)


    def _analyze_oracle_space(self, top_n: int = 20, min_size_mb: int = 100) -> Dict[str, Any]:
        """
        Oracle空间分析

        分析维度：
        1. 表空间使用率（总量、已用、空闲、使用率）
        2. 大段分析（表/索引大小TOP N）
        3. 数据文件信息

        参数:
            top_n: TOP N大段
            min_size_mb: 最小段大小(MB)

        返回:
            Dict: 空间分析结果
        """
        try:
            # 1. 表空间使用率分析
            tablespaces = []
            try:
                result = self.connector.execute("""
                    SELECT
                        df.tablespace_name,
                        ROUND(df.total_bytes / 1024 / 1024 / 1024, 3) AS total_gb,
                        ROUND(NVL(fs.free_bytes, 0) / 1024 / 1024 / 1024, 3) AS free_gb,
                        ROUND((df.total_bytes - NVL(fs.free_bytes, 0)) / 1024 / 1024 / 1024, 3) AS used_gb,
                        ROUND((df.total_bytes - NVL(fs.free_bytes, 0)) / df.total_bytes * 100, 2) AS used_pct,
                        df.file_count
                    FROM (
                        SELECT tablespace_name, SUM(bytes) total_bytes, COUNT(*) file_count
                        FROM dba_data_files
                        GROUP BY tablespace_name
                    ) df
                    LEFT JOIN (
                        SELECT tablespace_name, SUM(bytes) free_bytes
                        FROM dba_free_space
                        GROUP BY tablespace_name
                    ) fs ON df.tablespace_name = fs.tablespace_name
                    ORDER BY used_pct DESC
                """)

                for row in result.rows:
                    total_gb = float(str(row[1])) if row[1] else 0
                    free_gb = float(str(row[2])) if row[2] else 0
                    used_gb = float(str(row[3])) if row[3] else 0
                    used_pct = float(str(row[4])) if row[4] else 0
                    file_count = int(str(row[5])) if row[5] else 0

                    warning = None
                    if used_pct > 95:
                        warning = "表空间即将满，请立即扩容"
                    elif used_pct > 85:
                        warning = "表空间使用率较高，建议尽快扩容"

                    tablespaces.append({
                        "tablespace_name": row[0],
                        "total_gb": total_gb,
                        "used_gb": used_gb,
                        "free_gb": free_gb,
                        "used_pct": used_pct,
                        "file_count": file_count,
                        "warning": warning
                    })
            except Exception as e:
                logger.warning(f"查询表空间信息失败（可能没有DBA权限）: {e}")
                # 使用user级别查询
                try:
                    result = self.connector.execute("""
                        SELECT
                            tablespace_name,
                            ROUND(SUM(bytes) / 1024 / 1024 / 1024, 3) AS total_gb,
                            0 AS free_gb,
                            ROUND(SUM(bytes) / 1024 / 1024 / 1024, 3) AS used_gb,
                            100 AS used_pct,
                            COUNT(*) AS file_count
                        FROM user_data_files
                        GROUP BY tablespace_name
                        ORDER BY total_gb DESC
                    """)

                    for row in result.rows:
                        tablespaces.append({
                            "tablespace_name": row[0],
                            "total_gb": float(str(row[1])) if row[1] else 0,
                            "used_gb": float(str(row[3])) if row[3] else 0,
                            "free_gb": 0,
                            "used_pct": float(str(row[4])) if row[4] else 0,
                            "file_count": int(str(row[5])) if row[5] else 0,
                            "warning": None
                        })
                except Exception as e2:
                    logger.warning(f"user级别表空间查询也失败: {e2}")

            # 2. 大段分析（表和索引）
            large_segments = []
            try:
                result = self.connector.execute(f"""
                    SELECT * FROM (
                        SELECT
                            segment_name,
                            segment_type,
                            tablespace_name,
                            ROUND(bytes / 1024 / 1024, 2) AS size_mb,
                            blocks
                        FROM user_segments
                        WHERE bytes / 1024 / 1024 >= {min_size_mb}
                        ORDER BY bytes DESC
                    )
                    WHERE ROWNUM <= {top_n}
                """)

                for row in result.rows:
                    large_segments.append({
                        "segment_name": row[0],
                        "segment_type": row[1],
                        "tablespace": row[2],
                        "size_mb": float(str(row[3])) if row[3] else 0,
                        "blocks": int(str(row[4])) if row[4] else 0
                    })
            except Exception as e:
                logger.warning(f"查询大段信息失败: {e}")

            # 3. 汇总计算
            total_used_gb = sum(ts['used_gb'] for ts in tablespaces)
            total_alloc_gb = sum(ts['total_gb'] for ts in tablespaces)

            # 4. 生成建议
            space_suggestions = []
            for ts in tablespaces:
                if ts.get('warning'):
                    space_suggestions.append({
                        "type": "tablespace_space",
                        "priority": "high" if ts['used_pct'] > 95 else "medium",
                        "tablespace": ts['tablespace_name'],
                        "used_pct": ts['used_pct'],
                        "free_gb": ts['free_gb'],
                        "suggestion": ts['warning']
                    })

            for seg in large_segments[:5]:
                if seg['size_mb'] > 1024:
                    space_suggestions.append({
                        "type": "large_segment",
                        "priority": "low",
                        "segment": f"{seg['segment_type']}: {seg['segment_name']}",
                        "size_mb": seg['size_mb'],
                        "suggestion": "考虑归档历史数据或进行分区"
                    })

            return create_success_response(
                message=f"Oracle空间分析完成",
                data={
                    "total_space": {
                        "total_gb": round(total_alloc_gb, 3),
                        "used_gb": round(total_used_gb, 3),
                        "free_gb": round(total_alloc_gb - total_used_gb, 3)
                    },
                    "tablespaces": tablespaces,
                    "large_segments": large_segments,
                    "suggestions": space_suggestions
                }
            )

        except Exception as e:
            logger.error(f"Oracle空间分析失败: {e}")
            return create_error_response(str(e), ErrorCode.UNKNOWN_ERROR)


    def _analyze_postgresql_space(self, top_n: int = 20, min_size_mb: int = 100) -> Dict[str, Any]:
        """PostgreSQL空间分析"""
        try:
            result = self.connector.execute(f"""
                SELECT
                    schemaname || '.' || relname AS table_name,
                    pg_size_pretty(pg_total_relation_size(quote_ident(schemaname) || '.' || quote_ident(relname))) AS total_size,
                    pg_total_relation_size(quote_ident(schemaname) || '.' || quote_ident(relname)) / 1024 / 1024 AS total_mb,
                    pg_relation_size(quote_ident(schemaname) || '.' || quote_ident(relname)) / 1024 / 1024 AS data_mb,
                    (pg_total_relation_size(quote_ident(schemaname) || '.' || quote_ident(relname))
                        - pg_relation_size(quote_ident(schemaname) || '.' || quote_ident(relname))) / 1024 / 1024 AS index_mb,
                    n_live_tup AS row_count
                FROM pg_stat_user_tables
                    WHERE pg_total_relation_size(quote_ident(schemaname) || '.' || quote_ident(relname)) / 1024 / 1024 >= {min_size_mb}
                ORDER BY pg_total_relation_size(quote_ident(schemaname) || '.' || quote_ident(relname)) DESC
                LIMIT {top_n}
            """)

            tables = []
            total_data = 0
            total_index = 0
            for row in result.rows:
                data_mb = float(str(row[3])) if row[3] else 0
                index_mb = float(str(row[4])) if row[4] else 0
                tables.append({
                    "table": str(row[0]),
                    "size_pretty": str(row[1]),
                    "size_mb": float(str(row[2])) if row[2] else 0,
                    "data_mb": data_mb,
                    "index_mb": index_mb,
                    "rows": int(str(row[5])) if row[5] else 0
                })
                total_data += data_mb
                total_index += index_mb

            total_db_mb = 0
            try:
                db_result = self.connector.execute("""
                    SELECT pg_database_size(current_database()) / 1024 / 1024
                """)
                if db_result.rows:
                    total_db_mb = float(str(db_result.rows[0][0])) if db_result.rows[0][0] else 0
            except Exception:
                pass

            return create_success_response(
                message=f"获取到 {len(tables)} 个大表",
                data={
                    "total_space": {
                        "total_mb": round(total_db_mb, 2),
                        "data_mb": round(total_data, 2),
                        "index_mb": round(total_index, 2)
                    },
                    "large_tables": tables,
                    "suggestions": []
                }
            )
        except Exception as e:
            return create_error_response(str(e), ErrorCode.UNKNOWN_ERROR)


    def _analyze_mssql_space(self, top_n: int = 20, min_size_mb: int = 100) -> Dict[str, Any]:
        """SQL Server空间分析"""
        try:
            result = self.connector.execute(f"""
                SELECT TOP {top_n}
                    t.name AS table_name,
                    s.name AS schema_name,
                    CAST(ROUND(SUM(a.total_pages) * 8.0 / 1024, 2) AS DECIMAL(10,2)) AS total_mb,
                    CAST(ROUND(SUM(CASE WHEN a.type_desc = 'IN_ROW_DATA' THEN a.used_pages ELSE 0 END) * 8.0 / 1024, 2) AS DECIMAL(10,2)) AS data_mb,
                    CAST(ROUND((SUM(a.used_pages) - SUM(CASE WHEN a.type_desc = 'IN_ROW_DATA' THEN a.used_pages ELSE 0 END)) * 8.0 / 1024, 2) AS DECIMAL(10,2)) AS index_mb,
                    SUM(p.rows) AS row_count
                FROM sys.tables t
                INNER JOIN sys.indexes i ON t.object_id = i.object_id
                INNER JOIN sys.partitions p ON i.object_id = p.object_id AND i.index_id = p.index_id
                INNER JOIN sys.allocation_units a ON p.partition_id = a.container_id
                INNER JOIN sys.schemas s ON t.schema_id = s.schema_id
                WHERE i.index_id IN (0, 1)
                GROUP BY t.name, s.name
                HAVING ROUND(SUM(a.total_pages) * 8.0 / 1024, 2) >= {min_size_mb}
                ORDER BY SUM(a.total_pages) DESC
            """)

            tables = []
            total_data = 0
            total_index = 0
            for row in result.rows if result else []:
                table_name = f"{row[1]}.{row[0]}"
                total_mb = float(row[2]) if row[2] else 0
                data_mb = float(row[3]) if row[3] else 0
                index_mb = float(row[4]) if row[4] else 0
                row_count = int(row[5]) if row[5] else 0

                tables.append({
                    "table": table_name,
                    "size_pretty": f"{total_mb} MB",
                    "size_mb": total_mb,
                    "data_mb": data_mb,
                    "index_mb": index_mb,
                    "rows": row_count
                })
                total_data += data_mb
                total_index += index_mb

            # 获取数据库总大小
            total_db_mb = 0
            try:
                db_result = self.connector.execute("""
                    SELECT SUM(size * 8.0 / 1024)
                    FROM sys.database_files
                    WHERE type_desc = 'ROWS'
                """)
                if db_result.rows:
                    total_db_mb = float(db_result.rows[0][0]) if db_result.rows[0][0] else 0
            except Exception:
                pass

            return create_success_response(
                message=f"获取到 {len(tables)} 个大表",
                data={
                    "total_space": {
                        "total_mb": round(total_db_mb, 2),
                        "data_mb": round(total_data, 2),
                        "index_mb": round(total_index, 2)
                    },
                    "large_tables": tables,
                    "suggestions": []
                }
            )
        except Exception as e:
            return create_error_response(str(e), ErrorCode.UNKNOWN_ERROR)


    def _analyze_clickhouse_space(self, top_n: int = 20, min_size_mb: int = 100) -> Dict[str, Any]:
        """
        ClickHouse空间分析

        分析维度:
        1. 表大小（数据+索引）
        2. 分区大小
        3. 数据库总大小

        参数:
            top_n: TOP N大表
            min_size_mb: 最小表大小(MB)

        返回:
            Dict: 空间分析结果
        """
        try:
            # 获取表空间信息
            result = self.connector.execute(f"""
                SELECT
                    database,
                    table,
                    ROUND(SUM(bytes) / 1024 / 1024, 2) AS size_mb,
                    ROUND(SUM(data_compressed_bytes) / 1024 / 1024, 2) AS data_mb,
                    ROUND(SUM(data_uncompressed_bytes) / 1024 / 1024, 2) AS uncompressed_mb,
                    SUM(rows) AS row_count,
                    COUNT() AS parts_count
                FROM system.parts
                WHERE active = 1
                GROUP BY database, table
                HAVING size_mb >= {min_size_mb}
                ORDER BY size_mb DESC
                LIMIT {top_n}
            """)

            tables = []
            total_data = 0
            total_compressed = 0

            for row in result.rows if result else []:
                size_mb = float(row[2]) if row[2] else 0
                data_mb = float(row[3]) if row[3] else 0
                uncompressed_mb = float(row[4]) if row[4] else 0
                row_count = int(row[5]) if row[5] else 0
                parts_count = int(row[6]) if row[6] else 0

                compression_ratio = round(uncompressed_mb / data_mb, 2) if data_mb > 0 else 0

                tables.append({
                    "table": f"{row[0]}.{row[1]}",
                    "size_mb": size_mb,
                    "data_mb": data_mb,
                    "uncompressed_mb": uncompressed_mb,
                    "compression_ratio": compression_ratio,
                    "rows": row_count,
                    "parts_count": parts_count
                })
                total_data += data_mb
                total_compressed += size_mb

            # 获取数据库总大小
            total_db_mb = 0
            try:
                db_result = self.connector.execute("""
                    SELECT ROUND(SUM(bytes) / 1024 / 1024, 2)
                    FROM system.parts
                    WHERE active = 1
                """)
                if db_result.rows:
                    total_db_mb = float(db_result.rows[0][0]) if db_result.rows[0][0] else 0
            except Exception:
                pass

            suggestions = []
            for t in tables:
                if t["parts_count"] > 100:
                    suggestions.append({
                        "type": "too_many_parts",
                        "priority": "medium",
                        "table": t["table"],
                        "parts_count": t["parts_count"],
                        "suggestion": f"表 {t['table']} 分区过多({t['parts_count']}个)，建议执行OPTIMIZE TABLE合并分区"
                    })

            return create_success_response(
                message=f"获取到 {len(tables)} 个大表",
                data={
                    "total_space": {
                        "total_mb": round(total_db_mb, 2),
                        "data_mb": round(total_data, 2),
                        "compressed_mb": round(total_compressed, 2)
                    },
                    "large_tables": tables,
                    "suggestions": suggestions
                }
            )
        except Exception as e:
            return create_error_response(str(e), ErrorCode.UNKNOWN_ERROR)


    def _analyze_sqlite_space(self, top_n: int = 20, min_size_mb: int = 100) -> Dict[str, Any]:
        """
        SQLite空间分析

        分析维度:
        1. 表大小估算（基于行数和页大小）
        2. 数据库文件总大小
        3. 空闲页面数

        参数:
            top_n: TOP N大表
            min_size_mb: 最小表大小(MB)

        返回:
            Dict: 空间分析结果
        """
        try:
            # 获取页大小
            page_size = 4096
            try:
                result = self.connector.execute("PRAGMA page_size")
                if result.rows:
                    page_size = int(result.rows[0][0]) if result.rows[0][0] else 4096
            except Exception:
                pass

            # 获取表信息
            result = self.connector.execute("""
                SELECT
                    name,
                    (SELECT COUNT(*) FROM sqlite_master WHERE type = 'table' AND name = t.name) as exists_flag
                FROM sqlite_master t
                WHERE type = 'table'
                AND name NOT LIKE 'sqlite_%'
            """)

            tables = []
            total_data = 0

            for row in result.rows if result else []:
                table_name = row[0]

                # 获取表行数
                row_count = 0
                try:
                    count_result = self.connector.execute(f'SELECT COUNT(*) FROM "{table_name}"')
                    if count_result.rows:
                        row_count = int(count_result.rows[0][0]) if count_result.rows[0][0] else 0
                except Exception:
                    continue

                # 估算表大小
                # 使用更精确的方法：通过sqlite_master和页统计信息
                estimated_mb = self._estimate_sqlite_table_size(table_name, page_size, row_count)

                if estimated_mb >= min_size_mb:
                    tables.append({
                        "table": table_name,
                        "size_mb": estimated_mb,
                        "estimated": True,
                        "rows": row_count
                    })
                    total_data += estimated_mb

            # 按大小排序
            tables.sort(key=lambda x: x["size_mb"], reverse=True)
            tables = tables[:top_n]

            # 获取数据库文件总大小和空闲页面
            total_db_mb = 0
            free_pages = 0
            try:
                result = self.connector.execute("PRAGMA page_count")
                if result.rows:
                    page_count = int(result.rows[0][0]) if result.rows[0][0] else 0
                    total_db_mb = round(page_count * page_size / 1024 / 1024, 2)

                result = self.connector.execute("PRAGMA freelist_count")
                if result.rows:
                    free_pages = int(result.rows[0][0]) if result.rows[0][0] else 0
            except Exception:
                pass

            free_mb = round(free_pages * page_size / 1024 / 1024, 2)

            suggestions = []
            if free_pages > 100:
                suggestions.append({
                    "type": "free_pages",
                    "priority": "low",
                    "free_pages": free_pages,
                    "free_mb": free_mb,
                    "suggestion": f"数据库有 {free_pages} 个空闲页面({free_mb}MB)，建议执行VACUUM释放空间"
                })

            return create_success_response(
                message=f"获取到 {len(tables)} 个大表",
                data={
                    "total_space": {
                        "total_mb": total_db_mb,
                        "data_mb": round(total_data, 2),
                        "free_mb": free_mb
                    },
                    "large_tables": tables,
                    "suggestions": suggestions
                }
            )
        except Exception as e:
            return create_error_response(str(e), ErrorCode.UNKNOWN_ERROR)


    def _estimate_sqlite_table_size(self, table_name: str, page_size: int, row_count: int) -> float:
        """
        估算SQLite表大小

        使用更精确的方法：
        1. 尝试获取表的索引和列信息来估算平均行大小
        2. 回退到基于页大小的估算

        参数:
            table_name: 表名
            page_size: 数据库页大小(字节)
            row_count: 表行数

        返回:
            float: 估算的表大小(MB)
        """
        try:
            # 方法1: 通过PRAGMA table_info获取列信息估算
            result = self.connector.execute(f'PRAGMA table_info("{table_name}")')
            columns = result.rows if result else []

            if not columns:
                # 回退到简单估算
                return round(row_count * 200 / 1024 / 1024, 2)

            # 估算每行平均字节数
            avg_row_size = 0
            for col in columns:
                col_type = str(col[2]).upper() if len(col) > 2 and col[2] else "TEXT"
                if "INT" in col_type:
                    avg_row_size += 8
                elif "REAL" in col_type or "FLOAT" in col_type or "DOUBLE" in col_type:
                    avg_row_size += 8
                elif "BLOB" in col_type:
                    avg_row_size += 100  # 假设平均BLOB大小
                elif "TEXT" in col_type or "VARCHAR" in col_type or "CHAR" in col_type:
                    avg_row_size += 50  # 假设平均字符串长度
                else:
                    avg_row_size += 32  # 默认值

            # 添加行头开销(约4字节)
            avg_row_size += 4

            # 计算总字节数
            total_bytes = row_count * avg_row_size

            # 考虑B-tree页开销（约填充率70%）
            estimated_pages = total_bytes / (page_size * 0.7)
            estimated_bytes = estimated_pages * page_size

            return round(estimated_bytes / 1024 / 1024, 2)

        except Exception:
            # 回退到简单估算
            return round(row_count * 200 / 1024 / 1024, 2)


