"""
index_advisor mixin for DiagnoseSkill

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


class IndexAdvisorMixin:
    """index_advisor for DiagnoseSkill"""

    def recommend_indexes(self, table: str = None) -> Dict[str, Any]:
        """
        索引建议

        参数:
            table: 指定表名(可选，默认分析全库)

        返回:
            Dict: 索引建议列表
        """
        try:
            if 'mysql' in self.dialect:
                return self._recommend_mysql_indexes(table)
            elif 'oracle' in self.dialect:
                return self._recommend_oracle_indexes(table)
            elif 'postgresql' in self.dialect:
                return self._recommend_postgresql_indexes(table)
            elif 'clickhouse' in self.dialect:
                return self._recommend_clickhouse_indexes(table)
            elif 'sqlite' in self.dialect:
                return self._recommend_sqlite_indexes(table)
            else:
                return create_error_response(
                    f"索引建议暂不支持 {self.dialect}",
                    ErrorCode.UNSUPPORTED_SQL
                )
        except Exception as e:
            logger.error(f"索引建议失败: {e}")
            return create_error_response(str(e), ErrorCode.UNKNOWN_ERROR)


    def _recommend_postgresql_indexes(self, table: str = None) -> Dict[str, Any]:
        """PostgreSQL索引建议"""
        try:
            if table and not table.replace('.', '').replace('_', '').replace('-', '').isalnum():
                return create_error_response(
                    f"无效的表名: {table}",
                    ErrorCode.INVALID_PARAM
                )
            suggestions = []
            current_db = None
            try:
                result = self.connector.execute("SELECT current_database()")
                if result.rows:
                    current_db = result.rows[0][0]
            except Exception:
                pass

            table_filter = f" AND schemaname || '.' || relname = '{table}'" if table else ""

            try:
                result = self.connector.execute(f"""
                    SELECT
                        schemaname || '.' || relname AS table_name,
                        COALESCE(idx_scan, 0) AS index_scans,
                        COALESCE(seq_scan, 0) AS seq_scans,
                        CASE WHEN seq_scan > 0
                            THEN ROUND((seq_scan::numeric / (seq_scan + idx_scan + 1)) * 100, 1)
                            ELSE 0
                        END AS seq_scan_pct,
                        n_live_tup AS row_count
                    FROM pg_stat_user_tables
                    WHERE seq_scan > 100
                    AND (idx_scan IS NULL OR seq_scan > idx_scan * 2)
                    {table_filter}
                    ORDER BY seq_scan DESC
                    LIMIT 20
                """)
                for row in result.rows:
                    suggestions.append({
                        "type": "missing_index",
                        "priority": "high" if int(str(row[3])) > 80 else "medium",
                        "table": str(row[0]),
                        "description": f"表 {row[0]} 全表扫描比例 {row[3]}%",
                        "seq_scans": int(str(row[2])) if row[2] else 0,
                        "index_scans": int(str(row[1])) if row[1] else 0,
                        "suggestion": f"检查表 {row[0]} 的WHERE条件列，添加合适索引",
                        "reason": f"顺序扫描 {row[2]} 次，索引扫描仅 {row[1]} 次"
                    })
            except Exception as e:
                logger.warning(f"分析缺失索引失败: {e}")

            try:
                result = self.connector.execute(f"""
                    SELECT
                        schemaname || '.' || relname AS table_name,
                        indexrelname AS index_name,
                        idx_scan AS index_scans
                    FROM pg_stat_user_indexes
                    WHERE idx_scan = 0
                    AND schemaname NOT IN ('pg_catalog', 'information_schema')
                    {table_filter}
                    ORDER BY relname
                    LIMIT 20
                """)
                for row in result.rows:
                    suggestions.append({
                        "type": "unused_index",
                        "priority": "low",
                        "table": str(row[0]),
                        "index": str(row[1]),
                        "description": f"索引 {row[1]} 从未被使用",
                        "suggestion": f"DROP INDEX {row[1]};",
                        "reason": "该索引自服务器启动以来从未被使用"
                    })
            except Exception as e:
                logger.warning(f"分析未使用索引失败: {e}")

            # 分析冗余索引（被其他索引完全包含）
            try:
                redundant_indexes = self._analyze_redundant_indexes_postgresql(table)
                suggestions.extend(redundant_indexes)
            except Exception as e:
                logger.warning(f"分析冗余索引失败: {e}")

            # 分析低基数索引
            try:
                low_cardinality = self._analyze_low_cardinality_indexes_postgresql(table)
                suggestions.extend(low_cardinality)
            except Exception as e:
                logger.warning(f"分析低基数索引失败: {e}")

            priority_order = {"high": 0, "medium": 1, "low": 2}
            suggestions.sort(
                key=lambda x: priority_order.get(x.get("priority", "low"), 2)
            )

            return create_success_response(
                message=f"发现 {len(suggestions)} 个索引建议",
                data={
                    "database": current_db,
                    "table": table,
                    "suggestions": suggestions,
                    "summary": {
                        "total": len(suggestions),
                        "high_priority": len([s for s in suggestions if s.get("priority") == "high"]),
                        "medium_priority": len([s for s in suggestions if s.get("priority") == "medium"]),
                        "low_priority": len([s for s in suggestions if s.get("priority") == "low"])
                    }
                }
            )
        except Exception as e:
            return create_error_response(str(e), ErrorCode.UNKNOWN_ERROR)


    def _recommend_mysql_indexes(self, table: str = None) -> Dict[str, Any]:
        """
        MySQL索引建议

        分析维度：
        1. 缺失索引（基于慢查询和WHERE条件）
        2. 冗余索引（重复索引、前缀索引）
        3. 未使用索引（基于performance_schema）
        4. 低基数索引（索引选择性差）

        参数:
            table: 指定表名

        返回:
            Dict: 索引建议结果
        """
        try:
            # 表名安全验证
            if table and not self._is_valid_table_name(table):
                return create_error_response(
                    f"无效的表名: {table}",
                    ErrorCode.INVALID_PARAM
                )

            suggestions = []
            current_db = None

            # 获取当前数据库名
            try:
                result = self.connector.execute("SELECT DATABASE()")
                if result.rows:
                    current_db = result.rows[0][0]
            except Exception:
                pass

            if not current_db:
                return create_error_response(
                    "无法获取当前数据库名",
                    ErrorCode.UNKNOWN_ERROR
                )

            # 1. 分析缺失索引（基于performance_schema.table_io_waits_summary_by_index_usage）
            try:
                missing_indexes = self._analyze_missing_indexes_mysql(current_db, table)
                suggestions.extend(missing_indexes)
            except Exception as e:
                logger.warning(f"分析缺失索引失败: {e}")

            # 2. 分析冗余索引
            try:
                redundant_indexes = self._analyze_redundant_indexes_mysql(current_db, table)
                suggestions.extend(redundant_indexes)
            except Exception as e:
                logger.warning(f"分析冗余索引失败: {e}")

            # 3. 分析未使用索引
            try:
                unused_indexes = self._analyze_unused_indexes_mysql(current_db, table)
                suggestions.extend(unused_indexes)
            except Exception as e:
                logger.warning(f"分析未使用索引失败: {e}")

            # 4. 分析低基数索引
            try:
                low_cardinality = self._analyze_low_cardinality_indexes_mysql(current_db, table)
                suggestions.extend(low_cardinality)
            except Exception as e:
                logger.warning(f"分析低基数索引失败: {e}")

            # 按优先级排序
            priority_order = {"high": 0, "medium": 1, "low": 2}
            suggestions.sort(
                key=lambda x: priority_order.get(x.get("priority", "low"), 2)
            )

            return create_success_response(
                message=f"发现 {len(suggestions)} 个索引建议",
                data={
                    "database": current_db,
                    "table": table,
                    "suggestions": suggestions,
                    "summary": {
                        "total": len(suggestions),
                        "high_priority": len([s for s in suggestions if s.get("priority") == "high"]),
                        "medium_priority": len([s for s in suggestions if s.get("priority") == "medium"]),
                        "low_priority": len([s for s in suggestions if s.get("priority") == "low"])
                    }
                }
            )

        except Exception as e:
            return create_error_response(str(e), ErrorCode.UNKNOWN_ERROR)


    def _analyze_missing_indexes_mysql(self, database: str, table: str = None) -> List[Dict[str, Any]]:
        """
        分析缺失索引（基于全表扫描次数）

        参数:
            database: 数据库名
            table: 表名(可选)

        返回:
            List[Dict]: 缺失索引建议列表
        """
        suggestions = []

        # 查询全表扫描次数较多的表
        query = """
            SELECT
                OBJECT_SCHEMA as db,
                OBJECT_NAME as table_name,
                COUNT_READ as total_reads,
                SUM_TIMER_WAIT / 1000000000000 as total_latency_ms
            FROM performance_schema.table_io_waits_summary_by_table
            WHERE OBJECT_SCHEMA = :db
                AND COUNT_READ > 1000
        """
        params = {"db": database}

        if table:
            query += " AND OBJECT_NAME = :table"
            params["table"] = table

        query += " ORDER BY COUNT_READ DESC LIMIT 20"

        try:
            result = self.connector.execute(query, params)

            for row in result.rows:
                table_name = row[1]
                total_reads = row[2]
                latency_ms = round(row[3] or 0, 2)

                # 检查该表是否有主键
                pk_result = self.connector.execute("""
                    SELECT COUNT(*)
                    FROM information_schema.TABLE_CONSTRAINTS
                    WHERE TABLE_SCHEMA = :db
                        AND TABLE_NAME = :table
                        AND CONSTRAINT_TYPE = 'PRIMARY KEY'
                """, {"db": database, "table": table_name})

                has_pk = pk_result.rows[0][0] > 0 if pk_result.rows else False

                if not has_pk:
                    suggestions.append({
                        "type": "missing_primary_key",
                        "priority": "high",
                        "table": table_name,
                        "description": f"表 {table_name} 缺少主键，建议添加自增主键",
                        "impact": f"全表扫描 {total_reads} 次，延迟 {latency_ms}ms",
                        "suggestion": f"ALTER TABLE {table_name} ADD COLUMN id INT AUTO_INCREMENT PRIMARY KEY;",
                        "reason": "无主键的表在查询和更新时性能较差"
                    })

        except Exception as e:
            logger.warning(f"查询全表扫描统计失败: {e}")

        return suggestions


    def _analyze_redundant_indexes_mysql(self, database: str, table: str = None) -> List[Dict[str, Any]]:
        """
        分析冗余索引

        参数:
            database: 数据库名
            table: 表名(可选)

        返回:
            List[Dict]: 冗余索引建议列表
        """
        suggestions = []

        # 查询可能的冗余索引（前缀重复）
        query = """
            SELECT
                t.TABLE_NAME,
                t.INDEX_NAME,
                t.COLUMN_NAME,
                t.SEQ_IN_INDEX,
                t2.INDEX_NAME as redundant_to,
                t2.COLUMN_NAME as redundant_col
            FROM information_schema.STATISTICS t
            JOIN information_schema.STATISTICS t2
                ON t.TABLE_SCHEMA = t2.TABLE_SCHEMA
                AND t.TABLE_NAME = t2.TABLE_NAME
                AND t.COLUMN_NAME = t2.COLUMN_NAME
                AND t.SEQ_IN_INDEX = t2.SEQ_IN_INDEX
                AND t.INDEX_NAME != t2.INDEX_NAME
            WHERE t.TABLE_SCHEMA = :db
                AND t.NON_UNIQUE = 1
        """
        params = {"db": database}

        if table:
            query += " AND t.TABLE_NAME = :table"
            params["table"] = table

        try:
            result = self.connector.execute(query, params)

            seen = set()
            for row in result.rows:
                table_name = row[0]
                index_name = row[1]
                redundant_to = row[4]
                key = (table_name, index_name, redundant_to)

                if key not in seen:
                    seen.add(key)
                    suggestions.append({
                        "type": "redundant_index",
                        "priority": "medium",
                        "table": table_name,
                        "index": index_name,
                        "description": f"索引 {index_name} 可能是冗余的",
                        "suggestion": f"DROP INDEX {index_name} ON {table_name};",
                        "reason": f"该索引与 {redundant_to} 有重复前缀",
                        "note": "请先确认该索引确实未被使用后再删除"
                    })

        except Exception as e:
            logger.warning(f"查询冗余索引失败: {e}")

        return suggestions


    def _analyze_unused_indexes_mysql(self, database: str, table: str = None) -> List[Dict[str, Any]]:
        """
        分析未使用索引

        参数:
            database: 数据库名
            table: 表名(可选)

        返回:
            List[Dict]: 未使用索引建议列表
        """
        suggestions = []

        # 查询未使用的索引（需要开启performance_schema）
        query = """
            SELECT
                OBJECT_SCHEMA,
                OBJECT_NAME,
                INDEX_NAME,
                COUNT_FETCH,
                COUNT_INSERT,
                COUNT_UPDATE,
                COUNT_DELETE
            FROM performance_schema.table_io_waits_summary_by_index_usage
            WHERE OBJECT_SCHEMA = :db
                AND INDEX_NAME IS NOT NULL
                AND COUNT_FETCH = 0
                AND COUNT_INSERT = 0
                AND COUNT_UPDATE = 0
                AND COUNT_DELETE = 0
        """
        params = {"db": database}

        if table:
            query += " AND OBJECT_NAME = :table"
            params["table"] = table

        query += " LIMIT 20"

        try:
            result = self.connector.execute(query, params)

            for row in result.rows:
                table_name = row[1]
                index_name = row[2]

                # 排除主键
                if index_name == 'PRIMARY':
                    continue

                suggestions.append({
                    "type": "unused_index",
                    "priority": "low",
                    "table": table_name,
                    "index": index_name,
                    "description": f"索引 {index_name} 从未被使用",
                    "suggestion": f"DROP INDEX {index_name} ON {table_name};",
                    "reason": "该索引自服务器启动以来从未被使用",
                    "note": "建议观察一段时间后再删除，避免误删周期性使用的索引"
                })

        except Exception as e:
            logger.warning(f"查询未使用索引失败: {e}")

        return suggestions


    def _analyze_low_cardinality_indexes_mysql(self, database: str, table: str = None) -> List[Dict[str, Any]]:
        """
        分析低基数索引（选择性差的索引）

        参数:
            database: 数据库名
            table: 表名(可选)

        返回:
            List[Dict]: 低基数索引建议列表
        """
        suggestions = []

        # 获取所有索引及其基数信息
        query = """
            SELECT
                TABLE_NAME,
                INDEX_NAME,
                COLUMN_NAME,
                CARDINALITY
            FROM information_schema.STATISTICS
            WHERE TABLE_SCHEMA = :db
                AND NON_UNIQUE = 1
                AND CARDINALITY IS NOT NULL
                AND CARDINALITY < 10
        """
        params = {"db": database}

        if table:
            query += " AND TABLE_NAME = :table"
            params["table"] = table

        try:
            result = self.connector.execute(query, params)

            for row in result.rows:
                table_name = row[0]
                index_name = row[1]
                column_name = row[2]
                cardinality = row[3]

                suggestions.append({
                    "type": "low_cardinality",
                    "priority": "low",
                    "table": table_name,
                    "index": index_name,
                    "column": column_name,
                    "description": f"索引 {index_name} 选择性较差",
                    "cardinality": cardinality,
                    "reason": f"基数仅为 {cardinality}，索引效果不佳",
                    "note": "考虑是否需要该索引，或者使用复合索引"
                })

        except Exception as e:
            logger.warning(f"查询低基数索引失败: {e}")

        return suggestions

    # ==================== Oracle索引推荐方法 ====================


    def _recommend_oracle_indexes(self, table: str = None) -> Dict[str, Any]:
        """
        Oracle索引建议

        分析维度：
        1. 缺失索引（基于AWR和v$sql）
        2. 冗余索引（重复索引、包含索引）
        3. 未使用索引（基于v$object_usage）
        4. 低选择性索引（索引选择性差）

        参数:
            table: 指定表名

        返回:
            Dict: 索引建议结果
        """
        try:
            # 表名安全验证
            if table and not self._is_valid_table_name(table):
                return create_error_response(
                    f"无效的表名: {table}",
                    ErrorCode.INVALID_PARAM
                )

            suggestions = []

            # 获取当前用户
            current_user = None
            try:
                result = self.connector.execute("SELECT USER FROM DUAL")
                if result.rows:
                    current_user = result.rows[0][0]
            except Exception:
                pass

            if not current_user:
                return create_error_response(
                    "无法获取当前用户",
                    ErrorCode.UNKNOWN_ERROR
                )

            # 1. 分析缺失索引（基于AWR）
            try:
                missing_indexes = self._analyze_missing_indexes_oracle(current_user, table)
                suggestions.extend(missing_indexes)
            except Exception as e:
                logger.warning(f"分析缺失索引失败: {e}")

            # 2. 分析冗余索引
            try:
                redundant_indexes = self._analyze_redundant_indexes_oracle(current_user, table)
                suggestions.extend(redundant_indexes)
            except Exception as e:
                logger.warning(f"分析冗余索引失败: {e}")

            # 3. 分析未使用索引
            try:
                unused_indexes = self._analyze_unused_indexes_oracle(current_user, table)
                suggestions.extend(unused_indexes)
            except Exception as e:
                logger.warning(f"分析未使用索引失败: {e}")

            # 4. 分析低选择性索引
            try:
                low_selectivity = self._analyze_low_selectivity_indexes_oracle(current_user, table)
                suggestions.extend(low_selectivity)
            except Exception as e:
                logger.warning(f"分析低选择性索引失败: {e}")

            # 按优先级排序
            priority_order = {"high": 0, "medium": 1, "low": 2}
            suggestions.sort(
                key=lambda x: priority_order.get(x.get("priority", "low"), 2)
            )

            return create_success_response(
                message=f"发现 {len(suggestions)} 个索引建议",
                data={
                    "database": current_user,
                    "user": current_user,
                    "table": table,
                    "suggestions": suggestions,
                    "summary": {
                        "total": len(suggestions),
                        "high_priority": len([s for s in suggestions if s.get("priority") == "high"]),
                        "medium_priority": len([s for s in suggestions if s.get("priority") == "medium"]),
                        "low_priority": len([s for s in suggestions if s.get("priority") == "low"])
                    }
                }
            )

        except Exception as e:
            logger.error(f"Oracle索引建议失败: {e}")
            return create_error_response(str(e), ErrorCode.UNKNOWN_ERROR)


    def _analyze_missing_indexes_oracle(self, user: str, table: str = None) -> List[Dict[str, Any]]:
        """
        分析Oracle缺失索引（基于AWR）

        参数:
            user: 用户名
            table: 表名(可选)

        返回:
            List[Dict]: 缺失索引建议列表
        """
        suggestions = []

        try:
            # 检查AWR是否可用
            result = self.connector.execute("""
                SELECT COUNT(*) FROM dba_hist_snapshot WHERE ROWNUM = 1
            """)
            has_awr = result and result.rows and result.rows[0][0] > 0

            if has_awr:
                # 使用AWR分析高成本SQL
                query = """
                    SELECT * FROM (
                        SELECT
                            s.sql_id,
                            t.sql_text,
                            s.executions_delta,
                            s.elapsed_time_delta / 1000000 as elapsed_sec,
                            s.buffer_gets_delta,
                            s.disk_reads_delta
                        FROM dba_hist_sqlstat s
                        JOIN dba_hist_sqltext t ON s.sql_id = t.sql_id
                        WHERE s.snap_id IN (
                            SELECT snap_id FROM dba_hist_snapshot
                            WHERE begin_interval_time >= SYSDATE - 1
                        )
                        AND s.elapsed_time_delta / 1000000 > 1.0
                        AND t.sql_text LIKE '%SELECT%'
                        ORDER BY s.elapsed_time_delta DESC
                    )
                    WHERE ROWNUM <= 20
                """
            else:
                # 使用v$sql分析（elapsed_time是累积总时间，需除以executions得到平均时间）
                query = """
                    SELECT * FROM (
                        SELECT
                            sql_id,
                            sql_text,
                            executions,
                            elapsed_time / 1000000 as total_elapsed_sec,
                            CASE
                                WHEN executions > 0
                                THEN ROUND(elapsed_time / executions / 1000000, 2)
                                ELSE ROUND(elapsed_time / 1000000, 2)
                            END AS avg_elapsed_sec,
                            buffer_gets,
                            disk_reads
                        FROM v$sql
                        WHERE executions > 0
                        AND elapsed_time / executions / 1000000 > 1.0
                        AND sql_text LIKE '%SELECT%'
                        ORDER BY avg_elapsed_sec DESC
                    )
                    WHERE ROWNUM <= 20
                """

            result = self.connector.execute(query)

            for row in result.rows:
                sql_text = row[1]
                executions = int(str(row[2])) if row[2] else 0
                total_elapsed = float(str(row[3])) if row[3] else 0
                avg_elapsed = float(str(row[4])) if row[4] else 0

                if 'WHERE' in sql_text.upper():
                    suggestions.append({
                        "type": "missing_index",
                        "priority": "high" if avg_elapsed > 10 else "medium",
                        "sql_id": row[0],
                        "sql_preview": sql_text[:100] + "..." if len(sql_text) > 100 else sql_text,
                        "executions": executions,
                        "elapsed_sec": avg_elapsed,
                        "total_elapsed_sec": round(total_elapsed, 2),
                        "description": "高成本查询可能需要索引优化",
                        "reason": f"该查询平均耗时 {avg_elapsed:.2f} 秒（总耗时 {total_elapsed:.0f} 秒，执行 {executions} 次），建议分析执行计划",
                        "suggestion": "使用EXPLAIN PLAN分析SQL执行计划，考虑在WHERE条件列上创建索引"
                    })

        except Exception as e:
            logger.warning(f"分析缺失索引失败: {e}")

        return suggestions


    def _analyze_redundant_indexes_oracle(self, user: str, table: str = None) -> List[Dict[str, Any]]:
        """
        分析Oracle冗余索引

        参数:
            user: 用户名
            table: 表名(可选)

        返回:
            List[Dict]: 冗余索引建议列表
        """
        suggestions = []

        try:
            # 查找重复索引（相同列组合）
            query = """
                SELECT
                    t.table_name,
                    t.index_name,
                    t.column_name,
                    t.column_position
                FROM user_ind_columns t
                WHERE t.table_name NOT LIKE 'BIN$%'
                ORDER BY t.table_name, t.column_name, t.column_position
            """

            if table:
                query = f"""
                    SELECT
                        t.table_name,
                        t.index_name,
                        t.column_name,
                        t.column_position
                    FROM user_ind_columns t
                    WHERE t.table_name = '{table.upper()}'
                    ORDER BY t.table_name, t.column_name, t.column_position
                """

            result = self.connector.execute(query)

            # 构建索引列映射（按表分组）
            table_indexes = {}
            for row in result.rows:
                table_name = row[0]
                index_name = row[1]
                column_name = row[2]
                position = int(str(row[3])) if row[3] else 0

                if table_name not in table_indexes:
                    table_indexes[table_name] = {}
                key = f"{table_name}.{index_name}"
                if key not in table_indexes[table_name]:
                    table_indexes[table_name][key] = []
                table_indexes[table_name][key].append((position, column_name))

            # 在同一张表内查找重复索引和前缀索引
            for table_name, indexes in table_indexes.items():
                # 构建列组合映射
                seen_columns = {}
                for key, columns in indexes.items():
                    columns.sort(key=lambda x: x[0])
                    column_str = ','.join([c[1] for c in columns])

                    # 检查完全重复
                    if column_str in seen_columns:
                        _, index_name = key.split('.', 1)
                        duplicate_key = seen_columns[column_str]
                        _, dup_index_name = duplicate_key.split('.', 1)
                        suggestions.append({
                            "type": "redundant_index",
                            "priority": "medium",
                            "table": table_name,
                            "index": index_name,
                            "columns": column_str,
                            "description": f"索引 {index_name} 与 {dup_index_name} 重复",
                            "reason": "两个索引包含相同的列组合",
                            "suggestion": f"考虑删除索引 {index_name}，保留 {dup_index_name}"
                        })
                    else:
                        seen_columns[column_str] = key

                # 检查前缀索引（索引A的列是索引B的前缀）
                sorted_keys = sorted(seen_columns.items(), key=lambda x: len(x[0]))
                for i, (col_str_a, key_a) in enumerate(sorted_keys):
                    for col_str_b, key_b in sorted_keys[i+1:]:
                        if col_str_b.startswith(col_str_a + ','):
                            _, idx_name_a = key_a.split('.', 1)
                            _, idx_name_b = key_b.split('.', 1)
                            # 跳过主键索引和唯一约束索引
                            if idx_name_a.startswith('PK_') or idx_name_a.startswith('SYS_C'):
                                continue
                            suggestions.append({
                                "type": "redundant_index",
                                "priority": "low",
                                "table": table_name,
                                "index": idx_name_a,
                                "columns": col_str_a,
                                "description": f"索引 {idx_name_a} 是 {idx_name_b} 的前缀索引",
                                "reason": f"索引 {idx_name_a} 的列是 {idx_name_b} 的前缀，后者可替代前者",
                                "suggestion": f"评估是否可以删除索引 {idx_name_a}，保留 {idx_name_b}"
                            })

        except Exception as e:
            logger.warning(f"分析冗余索引失败: {e}")

        return suggestions


    def _analyze_unused_indexes_oracle(self, user: str, table: str = None) -> List[Dict[str, Any]]:
        """
        分析Oracle未使用索引

        参数:
            user: 用户名
            table: 表名(可选)

        返回:
            List[Dict]: 未使用索引建议列表
        """
        suggestions = []

        try:
            # 查询未使用索引（v$object_usage自动记录索引使用情况）
            query = """
                SELECT
                    io.table_name,
                    io.index_name,
                    io.monitoring,
                    io.used,
                    io.start_monitoring,
                    io.end_monitoring
                FROM v$object_usage io
                WHERE io.used = 'NO'
                AND io.monitoring = 'YES'
            """

            if table:
                query += f" AND io.table_name = '{table.upper()}'"

            result = self.connector.execute(query)

            for row in result.rows:
                table_name = row[0]
                index_name = row[1]
                start_monitoring = row[4]

                suggestions.append({
                    "type": "unused_index",
                    "priority": "low",
                    "table": table_name,
                    "index": index_name,
                    "description": f"索引 {index_name} 未被使用",
                    "monitoring_start": str(start_monitoring) if start_monitoring else None,
                    "reason": "自监控开始以来，该索引从未被使用",
                    "suggestion": "如果确认不需要该索引，可以考虑删除以节省空间和维护成本"
                })

        except Exception as e:
            logger.warning(f"分析未使用索引失败: {e}")

        return suggestions


    def _analyze_low_selectivity_indexes_oracle(self, user: str, table: str = None) -> List[Dict[str, Any]]:
        """
        分析Oracle低选择性索引

        参数:
            user: 用户名
            table: 表名(可选)

        返回:
            List[Dict]: 低选择性索引建议列表
        """
        suggestions = []

        try:
            # 查询索引选择性
            query = """
                SELECT
                    t.table_name,
                    t.index_name,
                    t.distinct_keys,
                    t.num_rows,
                    CASE
                        WHEN t.num_rows > 0 THEN ROUND(t.distinct_keys / t.num_rows * 100, 2)
                        ELSE 0
                    END as selectivity
                FROM user_ind_statistics t
                WHERE t.num_rows > 1000
                AND t.distinct_keys > 0
            """

            if table:
                query += f" AND t.table_name = '{table.upper()}'"

            query += " ORDER BY selectivity ASC"

            result = self.connector.execute(query)

            for row in result.rows:
                table_name = row[0]
                index_name = row[1]
                distinct_keys = int(str(row[2])) if row[2] else 0
                num_rows = int(str(row[3])) if row[3] else 0
                selectivity = float(str(row[4])) if row[4] else 0

                # 选择性低于1%认为是不好的索引
                if selectivity < 1.0:
                    suggestions.append({
                        "type": "low_selectivity",
                        "priority": "low",
                        "table": table_name,
                        "index": index_name,
                        "distinct_keys": distinct_keys,
                        "total_rows": num_rows,
                        "selectivity_percent": selectivity,
                        "description": f"索引 {index_name} 选择性较差",
                        "reason": f"选择性仅为 {selectivity}%，索引效果不佳",
                        "suggestion": "考虑是否需要该索引，或者使用位图索引（如果是数据仓库）"
                    })

        except Exception as e:
            logger.warning(f"分析低选择性索引失败: {e}")

        return suggestions


    def _analyze_redundant_indexes_postgresql(self, table: str = None) -> List[Dict[str, Any]]:
        """
        分析PostgreSQL冗余索引

        检测以下冗余情况：
        1. 完全重复的索引（相同列、相同顺序）
        2. 前缀冗余（索引A的列是索引B列的前缀）

        参数:
            table: 指定表名(可选)

        返回:
            List[Dict]: 冗余索引建议列表
        """
        suggestions = []

        try:
            table_filter = f" AND n.nspname || '.' || t.relname = '{table}'" if table else ""

            # 查询所有索引及其列信息
            result = self.connector.execute(f"""
                SELECT
                    n.nspname || '.' || t.relname AS table_name,
                    i.relname AS index_name,
                    array_agg(a.attname ORDER BY array_position(ix.indkey, a.attnum)) AS columns,
                    ix.indisunique AS is_unique,
                    ix.indisprimary AS is_primary
                FROM pg_index ix
                JOIN pg_class t ON t.oid = ix.indrelid
                JOIN pg_class i ON i.oid = ix.indexrelid
                JOIN pg_namespace n ON n.oid = t.relnamespace
                JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = ANY(ix.indkey)
                WHERE n.nspname NOT IN ('pg_catalog', 'information_schema', 'pg_toast')
                {table_filter}
                GROUP BY n.nspname, t.relname, i.relname, ix.indisunique, ix.indisprimary
                ORDER BY table_name, index_name
            """)

            # 按表分组分析
            indexes_by_table = {}
            for row in result.rows if result else []:
                table_name = str(row[0])
                index_name = str(row[1])
                columns = row[2] if row[2] else []
                is_unique = row[3] if row[3] else False
                is_primary = row[4] if row[4] else False

                if table_name not in indexes_by_table:
                    indexes_by_table[table_name] = []
                indexes_by_table[table_name].append({
                    'name': index_name,
                    'columns': columns,
                    'is_unique': is_unique,
                    'is_primary': is_primary
                })

            # 检测冗余
            for table_name, indexes in indexes_by_table.items():
                for i, idx1 in enumerate(indexes):
                    for j, idx2 in enumerate(indexes):
                        if i >= j:
                            continue

                        # 跳过主键和唯一索引
                        if idx1['is_primary'] or idx2['is_primary']:
                            continue

                        cols1 = idx1['columns']
                        cols2 = idx2['columns']

                        # 检测完全重复
                        if cols1 == cols2:
                            # 保留唯一索引，删除普通索引
                            if idx1['is_unique'] and not idx2['is_unique']:
                                redundant = idx2
                                keeper = idx1
                            elif idx2['is_unique'] and not idx1['is_unique']:
                                redundant = idx1
                                keeper = idx2
                            else:
                                # 都非唯一，保留名称较短的
                                redundant = idx1 if len(idx1['name']) > len(idx2['name']) else idx2
                                keeper = idx2 if redundant == idx1 else idx1

                            suggestions.append({
                                "type": "redundant_index",
                                "priority": "medium",
                                "table": table_name,
                                "index": redundant['name'],
                                "description": f"索引 {redundant['name']} 与 {keeper['name']} 完全重复",
                                "columns": cols1,
                                "suggestion": f"DROP INDEX {redundant['name']};",
                                "reason": f"与索引 {keeper['name']} 列完全相同，可以删除"
                            })

                        # 检测前缀冗余（idx1是idx2的前缀）
                        elif len(cols1) < len(cols2) and cols2[:len(cols1)] == cols1:
                            # idx1是idx2的前缀，idx1可能是冗余的
                            if not idx1['is_unique']:  # 不删除唯一索引
                                suggestions.append({
                                    "type": "prefix_redundant",
                                    "priority": "low",
                                    "table": table_name,
                                    "index": idx1['name'],
                                    "description": f"索引 {idx1['name']} 是 {idx2['name']} 的前缀",
                                    "columns": cols1,
                                    "suggestion": f"考虑删除 {idx1['name']}，因为 {idx2['name']} 可以覆盖",
                                    "reason": f"{idx2['name']} 包含相同的列前缀，可以替代此索引"
                                })

                        # 检测前缀冗余（idx2是idx1的前缀）
                        elif len(cols2) < len(cols1) and cols1[:len(cols2)] == cols2:
                            if not idx2['is_unique']:
                                suggestions.append({
                                    "type": "prefix_redundant",
                                    "priority": "low",
                                    "table": table_name,
                                    "index": idx2['name'],
                                    "description": f"索引 {idx2['name']} 是 {idx1['name']} 的前缀",
                                    "columns": cols2,
                                    "suggestion": f"考虑删除 {idx2['name']}，因为 {idx1['name']} 可以覆盖",
                                    "reason": f"{idx1['name']} 包含相同的列前缀，可以替代此索引"
                                })

        except Exception as e:
            logger.warning(f"分析冗余索引失败: {e}")

        return suggestions


    def _analyze_low_cardinality_indexes_postgresql(self, table: str = None) -> List[Dict[str, Any]]:
        """
        分析PostgreSQL低基数索引

        检测基数很低的索引（如性别、状态等只有几个值的列）
        这类索引通常效果不佳，因为选择性太差

        参数:
            table: 指定表名(可选)

        返回:
            List[Dict]: 低基数索引建议列表
        """
        suggestions = []

        try:
            table_filter = f" AND schemaname || '.' || relname = '{table}'" if table else ""

            # 查询索引统计信息
            result = self.connector.execute(f"""
                SELECT
                    schemaname || '.' || t.relname AS table_name,
                    i.relname AS index_name,
                    a.attname AS column_name,
                    t.reltuples::bigint AS table_rows,
                    s.n_distinct AS distinct_values,
                    s.null_frac AS null_fraction,
                    CASE
                        WHEN s.n_distinct > 0 THEN s.n_distinct
                        WHEN s.n_distinct < 0 THEN ABS(s.n_distinct) * t.reltuples
                        ELSE 0
                    END AS estimated_distinct
                FROM pg_stats s
                JOIN pg_class t ON t.relname = s.tablename
                JOIN pg_namespace n ON n.oid = t.relnamespace AND n.nspname = s.schemaname
                JOIN pg_index ix ON ix.indrelid = t.oid
                JOIN pg_class i ON i.oid = ix.indexrelid
                JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = ANY(ix.indkey)
                WHERE s.schemaname NOT IN ('pg_catalog', 'information_schema', 'pg_toast')
                AND array_position(ix.indkey, a.attnum) = 0  -- 只考虑索引的第一列
                AND t.reltuples > 1000  -- 只分析大表
                {table_filter}
                ORDER BY table_name, index_name
            """)

            for row in result.rows if result else []:
                table_name = str(row[0])
                index_name = str(row[1])
                column_name = str(row[2])
                table_rows = int(str(row[3])) if row[3] else 0
                distinct_values = float(str(row[6])) if row[6] else 0
                null_fraction = float(str(row[5])) if row[5] else 0

                # 计算选择性
                if table_rows > 0:
                    selectivity = (distinct_values / table_rows) * 100
                else:
                    selectivity = 0

                # 选择性低于1%认为是低基数索引
                if selectivity < 1.0 and distinct_values < 10:
                    suggestions.append({
                        "type": "low_cardinality",
                        "priority": "low",
                        "table": table_name,
                        "index": index_name,
                        "column": column_name,
                        "distinct_values": int(distinct_values),
                        "total_rows": table_rows,
                        "selectivity_percent": round(selectivity, 2),
                        "description": f"索引 {index_name} 列 {column_name} 基数很低",
                        "reason": f"只有 {int(distinct_values)} 个不同值，选择性 {selectivity:.2f}%",
                        "suggestion": "考虑使用位图索引（如果适用）或重新评估索引必要性"
                    })

        except Exception as e:
            logger.warning(f"分析低基数索引失败: {e}")

        return suggestions


    def _recommend_clickhouse_indexes(self, table: str = None) -> Dict[str, Any]:
        """
        ClickHouse索引建议

        ClickHouse索引机制与传统数据库不同:
        1. 主键/排序键（ORDER BY）决定数据物理排序
        2. 跳数索引（data skipping indices）用于快速过滤
        3. 没有传统B-tree索引

        分析维度:
        1. 缺少跳数索引的大表
        2. 低基数字段适合跳数索引
        3. 主键设计建议

        参数:
            table: 指定表名(可选)

        返回:
            Dict: 索引建议列表
        """
        try:
            suggestions = []

            # 获取表列表
            table_filter = f" AND table = '{table}'" if table else ""

            # 分析缺少跳数索引的大表
            try:
                result = self.connector.execute(f"""
                    SELECT
                        database,
                        table,
                        engine,
                        total_rows,
                        ROUND(total_bytes / 1024 / 1024 / 1024, 2) AS size_gb
                    FROM system.tables
                    WHERE engine LIKE '%MergeTree%'
                    AND total_rows > 1000000
                    {table_filter}
                    ORDER BY total_rows DESC
                    LIMIT 20
                """)

                for row in result.rows if result else []:
                    db_name = str(row[0]) if row[0] else ""
                    table_name = str(row[1]) if row[1] else ""
                    engine = str(row[2]) if row[2] else ""
                    total_rows = int(row[3]) if row[3] else 0
                    size_gb = float(row[4]) if row[4] else 0

                    # 检查是否已有跳数索引
                    idx_result = self.connector.execute(f"""
                        SELECT COUNT(*)
                        FROM system.data_skipping_indices
                        WHERE database = '{db_name}'
                        AND table = '{table_name}'
                    """)
                    idx_count = int(idx_result.rows[0][0]) if idx_result and idx_result.rows else 0

                    if idx_count == 0 and total_rows > 10000000:
                        suggestions.append({
                            "type": "missing_skipping_index",
                            "priority": "medium",
                            "table": f"{db_name}.{table_name}",
                            "engine": engine,
                            "rows": total_rows,
                            "size_gb": size_gb,
                            "description": f"表 {table_name} 数据量大但无跳数索引",
                            "reason": f"该表有 {total_rows} 行数据({size_gb}GB)，缺少跳数索引会导致全分区扫描",
                            "suggestion": f"考虑在低基数字段上添加跳数索引，如: ALTER TABLE {table_name} ADD INDEX idx_name (column) TYPE minmax GRANULARITY 4"
                        })
            except Exception as e:
                logger.warning(f"分析ClickHouse缺少跳数索引失败: {e}")

            # 分析主键/排序键设计
            try:
                result = self.connector.execute(f"""
                    SELECT
                        database,
                        table,
                        engine,
                        sorting_key,
                        primary_key,
                        partition_key,
                        total_rows
                    FROM system.tables
                    WHERE engine LIKE '%MergeTree%'
                    {table_filter}
                    ORDER BY total_rows DESC
                    LIMIT 20
                """)

                for row in result.rows if result else []:
                    db_name = str(row[0]) if row[0] else ""
                    table_name = str(row[1]) if row[1] else ""
                    engine = str(row[2]) if row[2] else ""
                    sorting_key = str(row[3]) if row[3] else ""
                    primary_key = str(row[4]) if row[4] else ""
                    partition_key = str(row[5]) if row[5] else ""
                    total_rows = int(row[6]) if row[6] else 0

                    # 检测主键设计问题
                    if not primary_key and total_rows > 1000000:
                        suggestions.append({
                            "type": "missing_primary_key",
                            "priority": "high",
                            "table": f"{db_name}.{table_name}",
                            "engine": engine,
                            "rows": total_rows,
                            "description": f"表 {table_name} 缺少显式主键",
                            "reason": "MergeTree表没有显式主键会导致数据排序不佳，影响查询性能",
                            "suggestion": f"建议添加主键: ALTER TABLE {table_name} MODIFY ORDER BY (column1, column2)"
                        })

                    # 检测分区键设计问题
                    if not partition_key and total_rows > 10000000:
                        suggestions.append({
                            "type": "missing_partition_key",
                            "priority": "medium",
                            "table": f"{db_name}.{table_name}",
                            "engine": engine,
                            "rows": total_rows,
                            "description": f"表 {table_name} 缺少分区键",
                            "reason": "大表缺少分区键会导致数据管理困难，影响查询和备份效率",
                            "suggestion": f"建议添加分区: ALTER TABLE {table_name} MODIFY PARTITION BY toYYYYMMDD(date_column)"
                        })

                    # 检测主键字段数量过多
                    if primary_key:
                        pk_columns = [c.strip() for c in primary_key.split(",")]
                        if len(pk_columns) > 5:
                            suggestions.append({
                                "type": "too_many_primary_key_columns",
                                "priority": "low",
                                "table": f"{db_name}.{table_name}",
                                "engine": engine,
                                "primary_key": primary_key,
                                "column_count": len(pk_columns),
                                "description": f"表 {table_name} 主键字段过多({len(pk_columns)}个)",
                                "reason": "主键字段过多会降低数据压缩率并增加排序开销",
                                "suggestion": "建议将主键精简为3-4个最关键字段，其他字段放入ORDER BY"
                            })

            except Exception as e:
                logger.warning(f"分析ClickHouse主键设计失败: {e}")

            # 分析已有跳数索引
            try:
                result = self.connector.execute("""
                    SELECT
                        database,
                        table,
                        name,
                        type,
                        expr
                    FROM system.data_skipping_indices
                    ORDER BY database, table
                    LIMIT 50
                """)

                for row in result.rows if result else []:
                    suggestions.append({
                        "type": "existing_skipping_index",
                        "priority": "info",
                        "table": f"{row[0]}.{row[1]}",
                        "index_name": str(row[2]) if row[2] else "",
                        "index_type": str(row[3]) if row[3] else "",
                        "expression": str(row[4]) if row[4] else "",
                        "description": f"表 {row[1]} 已有跳数索引 {row[2]}",
                        "suggestion": "检查跳数索引类型是否适合查询模式"
                    })
            except Exception as e:
                logger.warning(f"分析ClickHouse已有跳数索引失败: {e}")

            priority_order = {"high": 0, "medium": 1, "low": 2, "info": 3}
            suggestions.sort(
                key=lambda x: priority_order.get(x.get("priority", "low"), 2)
            )

            return create_success_response(
                message=f"发现 {len(suggestions)} 个ClickHouse索引建议",
                data={
                    "database": "clickhouse",
                    "table": table,
                    "suggestions": suggestions,
                    "summary": {
                        "total": len(suggestions),
                        "high_priority": len([s for s in suggestions if s.get("priority") == "high"]),
                        "medium_priority": len([s for s in suggestions if s.get("priority") == "medium"]),
                        "low_priority": len([s for s in suggestions if s.get("priority") == "low"])
                    }
                }
            )
        except Exception as e:
            return create_error_response(str(e), ErrorCode.UNKNOWN_ERROR)


    def _recommend_sqlite_indexes(self, table: str = None) -> Dict[str, Any]:
        """
        SQLite索引建议

        SQLite使用B-tree索引，分析维度:
        1. 缺少索引的大表（基于EXPLAIN QUERY PLAN）
        2. 未使用的索引
        3. 冗余索引

        参数:
            table: 指定表名(可选)

        返回:
            Dict: 索引建议列表
        """
        try:
            suggestions = []

            # 获取表列表
            if table:
                tables = [(table,)]
            else:
                result = self.connector.execute("""
                    SELECT name
                    FROM sqlite_master
                    WHERE type = 'table'
                    AND name NOT LIKE 'sqlite_%'
                """)
                tables = result.rows if result else []

            for row in tables:
                table_name = row[0]

                # 获取表行数
                row_count = 0
                try:
                    count_result = self.connector.execute(f'SELECT COUNT(*) FROM "{table_name}"')
                    if count_result.rows:
                        row_count = int(count_result.rows[0][0]) if count_result.rows[0][0] else 0
                except Exception:
                    continue

                if row_count < 1000:
                    continue

                # 获取现有索引
                existing_indexes = []
                try:
                    idx_result = self.connector.execute(f"""
                        SELECT name, sql
                        FROM sqlite_master
                        WHERE type = 'index'
                        AND tbl_name = '{table_name}'
                    """)
                    for idx_row in idx_result.rows if idx_result else []:
                        existing_indexes.append({
                            "name": str(idx_row[0]) if idx_row[0] else "",
                            "sql": str(idx_row[1]) if idx_row[1] else ""
                        })
                except Exception:
                    pass

                # 检查是否有主键索引
                has_primary_key = False
                try:
                    pk_result = self.connector.execute(f"PRAGMA table_info({table_name})")
                    for pk_row in pk_result.rows if pk_result else []:
                        if len(pk_row) > 5 and pk_row[5] == 1:
                            has_primary_key = True
                            break
                except Exception:
                    pass

                if not has_primary_key and row_count > 10000:
                    suggestions.append({
                        "type": "missing_primary_key",
                        "priority": "high",
                        "table": table_name,
                        "rows": row_count,
                        "description": f"表 {table_name} 无主键",
                        "reason": f"该表有 {row_count} 行数据，缺少主键会影响查询性能和数据完整性",
                        "suggestion": f"ALTER TABLE {table_name} ADD COLUMN id INTEGER PRIMARY KEY AUTOINCREMENT"
                    })

                # 检查索引数量
                if len(existing_indexes) == 0 and row_count > 10000:
                    suggestions.append({
                        "type": "missing_index",
                        "priority": "medium",
                        "table": table_name,
                        "rows": row_count,
                        "description": f"表 {table_name} 无任何索引",
                        "reason": f"该表有 {row_count} 行数据，缺少索引会导致全表扫描",
                        "suggestion": f"根据查询模式在常用WHERE条件列上创建索引: CREATE INDEX idx_{table_name}_col ON {table_name}(column)"
                    })

            # 分析冗余索引
            try:
                result = self.connector.execute("""
                    SELECT
                        tbl_name,
                        name,
                        sql
                    FROM sqlite_master
                    WHERE type = 'index'
                    AND sql IS NOT NULL
                    ORDER BY tbl_name, name
                """)

                indexes_by_table = {}
                for row in result.rows if result else []:
                    tbl = str(row[0])
                    idx_name = str(row[1])
                    sql = str(row[2])

                    # 提取索引列
                    import re
                    match = re.search(r'\(([^)]+)\)', sql)
                    if match:
                        columns = match.group(1).replace(' ', '').lower()
                        key = f"{tbl}:{columns}"
                        if key in indexes_by_table:
                            suggestions.append({
                                "type": "redundant_index",
                                "priority": "low",
                                "table": tbl,
                                "index": idx_name,
                                "columns": columns,
                                "description": f"索引 {idx_name} 与 {indexes_by_table[key]} 重复",
                                "reason": "两个索引包含相同的列",
                                "suggestion": f"考虑删除索引 {idx_name}"
                            })
                        else:
                            indexes_by_table[key] = idx_name
            except Exception as e:
                logger.warning(f"分析SQLite冗余索引失败: {e}")

            priority_order = {"high": 0, "medium": 1, "low": 2}
            suggestions.sort(
                key=lambda x: priority_order.get(x.get("priority", "low"), 2)
            )

            return create_success_response(
                message=f"发现 {len(suggestions)} 个SQLite索引建议",
                data={
                    "database": "sqlite",
                    "table": table,
                    "suggestions": suggestions,
                    "summary": {
                        "total": len(suggestions),
                        "high_priority": len([s for s in suggestions if s.get("priority") == "high"]),
                        "medium_priority": len([s for s in suggestions if s.get("priority") == "medium"]),
                        "low_priority": len([s for s in suggestions if s.get("priority") == "low"])
                    }
                }
            )
        except Exception as e:
            return create_error_response(str(e), ErrorCode.UNKNOWN_ERROR)

    # ==================== 统一性能模型诊断方法 ====================


