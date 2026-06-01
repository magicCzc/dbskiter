"""
PostgreSQL诊断器

提供PostgreSQL数据库的专项诊断能力
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from dbskiter.shared.unified_connector import UnifiedConnector
from .base import BaseDiagnostician

logger = logging.getLogger(__name__)


class PostgreSQLDiagnostician(BaseDiagnostician):
    """
    PostgreSQL数据库诊断器

    提供PostgreSQL特有的诊断能力：
    - 慢查询分析（pg_stat_statements/pg_stat_activity）
    - 性能指标分析
    - 实时连接监控
    - TOP SQL查询
    - 锁等待分析
    - 数据库统计信息
    - VACUUM状态分析（死元组、自动清理）
    - 索引使用分析（未使用索引、缺失索引）
    - 表膨胀分析（MVCC膨胀检测）
    - 复制状态分析（流复制、逻辑复制）
    """

    def __init__(self, connector: UnifiedConnector):
        super().__init__(connector)

    def analyze_slow_queries(
        self,
        limit: int = 20,
        min_time: float = 1.0
    ) -> Dict[str, Any]:
        """
        分析PostgreSQL慢查询（从pg_stat_statements获取）

        参数:
            limit: 返回条数限制
            min_time: 最小执行时间（秒）

        返回:
            Dict: 慢查询分析结果
        """
        try:
            # 检查pg_stat_statements是否可用
            result = self._execute_query("""
                SELECT COUNT(*) FROM pg_extension WHERE extname = 'pg_stat_statements'
            """)

            if not result or result[0][0] == 0:
                # pg_stat_statements未启用，降级到pg_stat_activity查询当前活跃慢查询
                logger.warning("pg_stat_statements扩展未启用，降级到pg_stat_activity查询")
                return self._analyze_slow_queries_from_activity(limit, min_time)

            # 获取慢查询
            result = self._execute_query("""
                SELECT
                    queryid,
                    query,
                    calls,
                    round(total_exec_time::numeric, 2) as total_time_ms,
                    round(mean_exec_time::numeric, 2) as avg_time_ms,
                    round(max_exec_time::numeric, 2) as max_time_ms,
                    rows
                FROM pg_stat_statements
                WHERE mean_exec_time >= %s * 1000
                ORDER BY mean_exec_time DESC
                LIMIT %s
            """, (min_time, limit))

            if not result:
                return self._create_result(
                    success=True,
                    message="未找到慢查询",
                    data={
                        "total_queries": 0,
                        "queries": []
                    }
                )

            queries = []
            for row in result:
                queries.append({
                    "query_id": row[0],
                    "query": row[1][:500] if row[1] else None,
                    "calls": row[2],
                    "total_time_ms": row[3],
                    "avg_time_ms": row[4],
                    "max_time_ms": row[5],
                    "rows": row[6]
                })

            return self._create_result(
                success=True,
                message=f"成功分析 {len(queries)} 个慢查询",
                data={
                    "total_queries": len(queries),
                    "queries": queries
                }
            )

        except Exception as e:
            logger.error(f"慢查询分析失败: {e}")
            return self._create_result(
                success=False,
                message="慢查询分析失败",
                error=str(e)
            )

    def _analyze_slow_queries_from_activity(
        self,
        limit: int = 20,
        min_time: float = 1.0
    ) -> Dict[str, Any]:
        """
        从pg_stat_activity分析当前活跃慢查询（降级方案）

        参数:
            limit: 返回条数限制
            min_time: 最小执行时间（秒）

        返回:
            Dict: 慢查询分析结果
        """
        try:
            result = self._execute_query("""
                SELECT
                    pid,
                    LEFT(query, 500) AS query_text,
                    state,
                    EXTRACT(EPOCH FROM (now() - query_start))::numeric(10,2) AS exec_seconds,
                    datname,
                    usename,
                    client_addr
                FROM pg_stat_activity
                WHERE state = 'active'
                AND query NOT LIKE '%pg_stat%'
                AND backend_type = 'client backend'
                AND query_start IS NOT NULL
                AND EXTRACT(EPOCH FROM (now() - query_start)) >= %s
                ORDER BY exec_seconds DESC
                LIMIT %s
            """, (min_time, limit))

            queries = []
            for row in result or []:
                queries.append({
                    "query_id": row[0],
                    "query": row[1],
                    "state": row[2],
                    "exec_time_sec": row[3],
                    "database": row[4],
                    "user": row[5],
                    "client": str(row[6]) if row[6] else None,
                    "calls": 1,
                    "total_time_ms": row[3] * 1000 if row[3] else 0,
                    "avg_time_ms": row[3] * 1000 if row[3] else 0,
                    "max_time_ms": row[3] * 1000 if row[3] else 0,
                    "rows": 0
                })

            return self._create_result(
                success=True,
                message=f"从pg_stat_activity获取到 {len(queries)} 个活跃慢查询",
                data={
                    "total_queries": len(queries),
                    "queries": queries,
                    "note": "pg_stat_statements扩展未启用，仅显示当前活跃查询"
                }
            )

        except Exception as e:
            logger.error(f"从pg_stat_activity分析慢查询失败: {e}")
            return self._create_result(
                success=False,
                message="慢查询分析失败",
                error=str(e)
            )

    def analyze_performance_metrics(
        self,
        duration_minutes: int = 10
    ) -> Dict[str, Any]:
        """
        分析PostgreSQL性能指标

        参数:
            duration_minutes: 采集时长（分钟）

        返回:
            Dict: 性能分析结果
        """
        try:
            metrics = {}

            # 获取数据库统计信息
            result = self._execute_query("""
                SELECT
                    numbackends,
                    xact_commit,
                    xact_rollback,
                    blks_read,
                    blks_hit,
                    tup_returned,
                    tup_fetched,
                    tup_inserted,
                    tup_updated,
                    tup_deleted,
                    conflicts,
                    temp_files,
                    temp_bytes,
                    deadlocks
                FROM pg_stat_database
                WHERE datname = current_database()
            """)

            if result:
                row = result[0]
                metrics["numbackends"] = row[0]
                metrics["xact_commit"] = row[1]
                metrics["xact_rollback"] = row[2]
                metrics["blks_read"] = row[3]
                metrics["blks_hit"] = row[4]
                metrics["tup_returned"] = row[5]
                metrics["tup_fetched"] = row[6]
                metrics["tup_inserted"] = row[7]
                metrics["tup_updated"] = row[8]
                metrics["tup_deleted"] = row[9]
                metrics["conflicts"] = row[10]
                metrics["temp_files"] = row[11]
                metrics["temp_bytes"] = row[12]
                metrics["deadlocks"] = row[13]

                # 计算缓存命中率
                if row[3] + row[4] > 0:
                    metrics["cache_hit_ratio"] = round(
                        row[4] / (row[3] + row[4]) * 100, 2
                    )

            # 获取当前活动连接
            result = self._execute_query("""
                SELECT
                    state,
                    COUNT(*)
                FROM pg_stat_activity
                GROUP BY state
            """)

            if result:
                metrics["connection_states"] = {
                    row[0]: row[1] for row in result
                }

            # 获取长时间运行的查询
            result = self._execute_query("""
                SELECT
                    pid,
                    usename,
                    application_name,
                    state,
                    EXTRACT(EPOCH FROM (now() - query_start)) as query_duration_sec,
                    query
                FROM pg_stat_activity
                WHERE state = 'active'
                AND query_start < now() - interval '1 minute'
                ORDER BY query_start
            """)

            if result:
                metrics["long_running_queries"] = [
                    {
                        "pid": row[0],
                        "username": row[1],
                        "application": row[2],
                        "state": row[3],
                        "duration_sec": round(float(row[4]), 2),
                        "query": row[5][:200] if row[5] else None
                    }
                    for row in result
                ]

            # 获取锁等待信息
            result = self._execute_query("""
                SELECT
                    blocked_locks.pid AS blocked_pid,
                    blocked_activity.usename AS blocked_user,
                    blocking_locks.pid AS blocking_pid,
                    blocking_activity.usename AS blocking_user,
                    blocked_activity.query AS blocked_statement,
                    blocking_activity.query AS blocking_statement
                FROM pg_catalog.pg_locks blocked_locks
                JOIN pg_catalog.pg_stat_activity blocked_activity ON blocked_activity.pid = blocked_locks.pid
                JOIN pg_catalog.pg_locks blocking_locks
                    ON blocking_locks.locktype = blocked_locks.locktype
                    AND blocking_locks.relation = blocked_locks.relation
                    AND blocking_locks.pid != blocked_locks.pid
                JOIN pg_catalog.pg_stat_activity blocking_activity ON blocking_activity.pid = blocking_locks.pid
                WHERE NOT blocked_locks.granted
            """)

            if result:
                metrics["lock_waits"] = [
                    {
                        "blocked_pid": row[0],
                        "blocked_user": row[1],
                        "blocking_pid": row[2],
                        "blocking_user": row[3],
                        "blocked_statement": row[4][:200] if row[4] else None,
                        "blocking_statement": row[5][:200] if row[5] else None
                    }
                    for row in result
                ]

            return self._create_result(
                success=True,
                message="成功获取性能指标",
                data=metrics
            )

        except Exception as e:
            logger.error(f"性能分析失败: {e}")
            return self._create_result(
                success=False,
                message="性能分析失败",
                error=str(e)
            )

    def get_database_stats(self) -> Dict[str, Any]:
        """
        获取PostgreSQL数据库统计信息

        返回:
            Dict: 数据库统计信息
        """
        try:
            stats = {
                "database_type": "PostgreSQL",
                "timestamp": datetime.now().isoformat()
            }

            # 获取版本
            result = self._execute_query("SELECT version()")
            if result:
                stats["version"] = result[0][0]

            # 获取数据库名
            result = self._execute_query("SELECT current_database()")
            if result:
                stats["database_name"] = result[0][0]

            # 获取当前连接数
            result = self._execute_query("SELECT COUNT(*) FROM pg_stat_activity")
            if result:
                stats["current_connections"] = result[0][0]

            # 获取最大连接数
            result = self._execute_query("SHOW max_connections")
            if result:
                stats["max_connections"] = int(result[0][0])

            # 获取数据库大小
            result = self._execute_query("""
                SELECT pg_size_pretty(pg_database_size(current_database()))
            """)
            if result:
                stats["database_size"] = result[0][0]

            # 获取表数量
            result = self._execute_query("""
                SELECT COUNT(*) FROM information_schema.tables
                WHERE table_schema NOT IN ('pg_catalog', 'information_schema')
            """)
            if result:
                stats["table_count"] = result[0][0]

            # 获取共享缓冲区大小
            result = self._execute_query("SHOW shared_buffers")
            if result:
                stats["shared_buffers"] = result[0][0]

            # 获取WAL位置
            result = self._execute_query("SELECT pg_current_wal_lsn()")
            if result:
                stats["current_wal_lsn"] = str(result[0][0])

            return self._create_result(
                success=True,
                message="成功获取数据库统计信息",
                data=stats
            )

        except Exception as e:
            logger.error(f"获取数据库统计信息失败: {e}")
            return self._create_result(
                success=False,
                message="获取数据库统计信息失败",
                error=str(e)
            )

    def get_realtime_connections(self) -> Dict[str, Any]:
        """
        获取实时连接信息

        返回:
            Dict: 连接统计信息
        """
        try:
            result = self._execute_query("""
                SELECT 
                    count(*) as total,
                    count(*) FILTER (WHERE state = 'active') as active,
                    count(*) FILTER (WHERE state = 'active' AND now() - query_start > interval '5 seconds') as slow
                FROM pg_stat_activity
                WHERE backend_type = 'client backend'
            """)

            row = result[0] if result else (0, 0, 0)

            return self._create_result(
                success=True,
                message="实时连接信息获取成功",
                data={
                    "total": int(row[0]) if row[0] else 0,
                    "active": int(row[1]) if row[1] else 0,
                    "slow_count": int(row[2]) if row[2] else 0
                }
            )
        except Exception as e:
            logger.error(f"获取实时连接失败: {e}")
            return self._create_result(
                success=False,
                message="获取实时连接失败",
                error=str(e)
            )

    def get_top_sql(self, limit: int = 10, threshold: int = 0) -> Dict[str, Any]:
        """
        获取TOP SQL

        参数:
            limit: 返回条数
            threshold: 执行时间阈值(秒)

        返回:
            Dict: TOP SQL列表
        """
        try:
            # 检查pg_stat_statements是否可用
            has_pgss = False
            try:
                check = self._execute_query("""
                    SELECT COUNT(*) FROM pg_extension WHERE extname = 'pg_stat_statements'
                """)
                has_pgss = check and check[0][0] > 0
            except Exception:
                pass

            queries = []

            if has_pgss:
                result = self._execute_query("""
                    SELECT
                        queryid,
                        query,
                        calls,
                        ROUND(total_exec_time::numeric, 2) AS total_time_ms,
                        ROUND(mean_exec_time::numeric, 2) AS avg_time_ms,
                        ROUND(max_exec_time::numeric, 2) AS max_time_ms,
                        rows,
                        shared_blks_hit + shared_blks_read AS blocks
                    FROM pg_stat_statements
                    WHERE mean_exec_time >= %s * 1000
                    AND query NOT LIKE '%%pg_stat%%'
                    AND query NOT LIKE '%%pg_catalog%%'
                    ORDER BY mean_exec_time DESC
                    LIMIT %s
                """, (threshold, limit))

                if result is None:
                    result = []

                for row in result:
                    queries.append({
                        "sql_id": str(row[0]),
                        "sql": row[1][:500] if row[1] else "",
                        "executions": int(row[2]) if row[2] else 0,
                        "exec_time": float(row[4]) if row[4] else 0,
                        "total_time": float(row[3]) if row[3] else 0,
                        "max_time": float(row[5]) if row[5] else 0,
                        "rows": int(row[6]) if row[6] else 0,
                        "buffer_gets": int(row[7]) if row[7] else 0,
                        "state": "completed"
                    })
            else:
                # 降级到pg_stat_activity
                result = self._execute_query("""
                    SELECT
                        pid,
                        LEFT(query, 500) AS sql_text,
                        state,
                        EXTRACT(EPOCH FROM (now() - query_start))::numeric(10,2) AS exec_seconds,
                        datname
                    FROM pg_stat_activity
                    WHERE state = 'active'
                    AND query NOT LIKE '%%pg_stat%%'
                    AND backend_type = 'client backend'
                    AND EXTRACT(EPOCH FROM (now() - query_start)) >= %s
                    ORDER BY exec_seconds DESC
                    LIMIT %s
                """, (threshold, limit))

                if result is None:
                    result = []

                for row in result:
                    queries.append({
                        "sql_id": str(row[0]),
                        "sql": row[1] if row[1] else "",
                        "state": str(row[2]) if row[2] else "",
                        "exec_time": float(row[3]) if row[3] else 0,
                        "database": str(row[4]) if row[4] else "",
                        "executions": 1,
                        "total_time": float(row[3]) if row[3] else 0,
                        "max_time": float(row[3]) if row[3] else 0,
                        "rows": 0,
                        "buffer_gets": 0
                    })

            return self._create_result(
                success=True,
                message=f"获取到 {len(queries)} 条TOP SQL",
                data={"queries": queries}
            )
        except Exception as e:
            logger.error(f"获取TOP SQL失败: {e}")
            return self._create_result(
                success=False,
                message="获取TOP SQL失败",
                error=str(e)
            )

    def get_lock_waits(self) -> Dict[str, Any]:
        """
        获取锁等待信息

        返回:
            Dict: 锁等待列表
        """
        try:
            result = self._execute_query("""
                SELECT
                    blocked.pid AS waiting_pid,
                    blocked.locktype,
                    blocked.mode AS wait_mode,
                    EXTRACT(EPOCH FROM (now() - blocked_activity.query_start))::numeric(10,2) AS wait_seconds,
                    blocking.pid AS holding_pid,
                    blocked_activity.query AS waiting_query,
                    blocking_activity.query AS blocking_query
                FROM pg_locks blocked
                JOIN pg_locks blocking ON (
                    blocked.locktype = blocking.locktype
                    AND blocked.database IS NOT DISTINCT FROM blocking.database
                    AND blocked.relation IS NOT DISTINCT FROM blocking.relation
                )
                JOIN pg_stat_activity blocked_activity ON blocked.pid = blocked_activity.pid
                JOIN pg_stat_activity blocking_activity ON blocking.pid = blocking_activity.pid
                WHERE NOT blocked.granted
                AND blocking.granted
            """)

            if result is None:
                result = []

            lock_waits = []
            for row in result:
                lock_waits.append({
                    "waiting_pid": int(row[0]) if row[0] else 0,
                    "lock_type": str(row[1]) if row[1] else "",
                    "wait_mode": str(row[2]) if row[2] else "",
                    "wait_seconds": float(row[3]) if row[3] else 0,
                    "holding_pid": int(row[4]) if row[4] else 0,
                    "waiting_query": str(row[5])[:200] if row[5] else "",
                    "blocking_query": str(row[6])[:200] if row[6] else ""
                })

            return self._create_result(
                success=True,
                message=f"获取到 {len(lock_waits)} 个锁等待",
                data={"lock_waits": lock_waits}
            )
        except Exception as e:
            logger.warning(f"获取锁等待失败: {e}")
            return self._create_result(
                success=True,
                message="锁等待信息获取完成",
                data={"lock_waits": []}
            )

    def analyze_vacuum_status(self) -> Dict[str, Any]:
        """
        分析PostgreSQL VACUUM状态

        检查表的自动清理状态和膨胀情况，这是PostgreSQL特有的维护需求。
        提供详细的统计信息、健康度评估和具体的维护建议。

        返回:
            Dict: VACUUM状态分析结果，包含：
                - tables_needing_vacuum: 需要VACUUM的表列表
                - autovacuum_settings: autovacuum配置
                - vacuum_statistics: VACUUM统计信息
                - health_score: 健康评分(0-100)
                - suggestions: 维护建议列表
                - actionable_commands: 可执行的VACUUM命令
        """
        try:
            # 获取需要VACUUM的表
            result = self._execute_query("""
                SELECT
                    schemaname,
                    relname,
                    n_live_tup,
                    n_dead_tup,
                    CASE WHEN n_live_tup > 0
                        THEN ROUND((n_dead_tup::numeric / n_live_tup) * 100, 2)
                        ELSE 0
                    END AS dead_ratio,
                    last_vacuum,
                    last_autovacuum,
                    last_analyze,
                    last_autoanalyze,
                    pg_size_pretty(pg_total_relation_size(schemaname || '.' || relname)) as total_size,
                    pg_total_relation_size(schemaname || '.' || relname) as size_bytes
                FROM pg_stat_user_tables
                WHERE n_dead_tup > 1000
                ORDER BY n_dead_tup DESC
                LIMIT 20
            """)

            tables_needing_vacuum = []
            total_wasted_space = 0
            for row in result or []:
                # 跳过schema或表名为空的数据
                if not row[0] or not row[1]:
                    continue
                size_bytes = row[10] or 0
                dead_ratio = float(row[4]) if row[4] else 0
                # 估算浪费的空间（死元组比例 * 表大小）
                wasted_space = int(size_bytes * dead_ratio / 100)
                total_wasted_space += wasted_space

                tables_needing_vacuum.append({
                    "schema": row[0],
                    "table": row[1],
                    "live_tuples": row[2] or 0,
                    "dead_tuples": row[3] or 0,
                    "dead_ratio": dead_ratio,
                    "last_vacuum": row[5].isoformat() if row[5] else None,
                    "last_autovacuum": row[6].isoformat() if row[6] else None,
                    "last_analyze": row[7].isoformat() if row[7] else None,
                    "last_autoanalyze": row[8].isoformat() if row[8] else None,
                    "total_size": row[9],
                    "size_bytes": size_bytes,
                    "wasted_space_bytes": wasted_space,
                    "priority": self._calculate_vacuum_priority(dead_ratio, row[3] or 0)
                })

            # 获取autovacuum配置
            autovacuum_settings = {}
            settings_to_check = [
                'autovacuum',
                'autovacuum_max_workers',
                'autovacuum_naptime',
                'autovacuum_vacuum_threshold',
                'autovacuum_vacuum_scale_factor',
                'autovacuum_analyze_threshold',
                'autovacuum_analyze_scale_factor',
                'autovacuum_vacuum_cost_limit',
                'autovacuum_vacuum_cost_delay'
            ]

            for setting in settings_to_check:
                try:
                    result = self._execute_query(f"SHOW {setting}")
                    if result:
                        autovacuum_settings[setting] = result[0][0]
                except Exception:
                    pass

            # 获取VACUUM统计信息
            vacuum_stats = self._get_vacuum_statistics()

            # 计算健康评分
            health_score = self._calculate_vacuum_health_score(
                tables_needing_vacuum, autovacuum_settings, vacuum_stats
            )

            # 生成建议和可执行命令
            suggestions = []
            actionable_commands = []

            if tables_needing_vacuum:
                # 按优先级排序
                high_priority = [t for t in tables_needing_vacuum if t["priority"] == "high"]
                medium_priority = [t for t in tables_needing_vacuum if t["priority"] == "medium"]

                if high_priority:
                    suggestions.append({
                        "type": "critical",
                        "message": f"发现 {len(high_priority)} 个表需要立即执行VACUUM",
                        "impact": f"预计可回收 {self._format_bytes(sum(t['wasted_space_bytes'] for t in high_priority))} 空间",
                        "tables": [f"{t['schema']}.{t['table']}" for t in high_priority[:5]]
                    })
                    # 生成高优先级表的VACUUM命令
                    for t in high_priority[:3]:
                        actionable_commands.append({
                            "priority": "high",
                            "table": f"{t['schema']}.{t['table']}",
                            "command": f"VACUUM (VERBOSE, ANALYZE) {t['schema']}.{t['table']};",
                            "description": f"清理死元组，预计可回收 {self._format_bytes(t['wasted_space_bytes'])}",
                            "estimated_dead_tuples": t["dead_tuples"],
                            "dead_ratio": t["dead_ratio"]
                        })

                if medium_priority:
                    suggestions.append({
                        "type": "warning",
                        "message": f"发现 {len(medium_priority)} 个表建议在维护窗口执行VACUUM",
                        "tables": [f"{t['schema']}.{t['table']}" for t in medium_priority[:5]]
                    })

                # 检查长时间未VACUUM的表
                no_recent_vacuum = [t for t in tables_needing_vacuum
                                   if not t["last_autovacuum"] and not t["last_vacuum"]]
                if no_recent_vacuum:
                    suggestions.append({
                        "type": "info",
                        "message": f"发现 {len(no_recent_vacuum)} 个表从未执行过VACUUM",
                        "note": "建议检查autovacuum配置或手动执行VACUUM",
                        "tables": [f"{t['schema']}.{t['table']}" for t in no_recent_vacuum[:5]]
                    })

            # 检查autovacuum配置
            if autovacuum_settings.get('autovacuum') != 'on':
                suggestions.append({
                    "type": "critical",
                    "message": "autovacuum未启用，建议立即开启",
                    "fix_command": "ALTER SYSTEM SET autovacuum = on; SELECT pg_reload_conf();",
                    "impact": "关闭autovacuum会导致表膨胀和性能下降"
                })

            return self._create_result(
                success=True,
                message=f"VACUUM状态分析完成，健康评分: {health_score}/100",
                data={
                    "tables_needing_vacuum": tables_needing_vacuum,
                    "autovacuum_settings": autovacuum_settings,
                    "vacuum_statistics": vacuum_stats,
                    "health_score": health_score,
                    "total_wasted_space": self._format_bytes(total_wasted_space),
                    "total_wasted_space_bytes": total_wasted_space,
                    "suggestions": suggestions,
                    "actionable_commands": actionable_commands
                }
            )

        except Exception as e:
            logger.error(f"VACUUM状态分析失败: {e}")
            return self._create_result(
                success=False,
                message="VACUUM状态分析失败",
                error=str(e)
            )

    def _calculate_vacuum_priority(self, dead_ratio: float, dead_tuples: int) -> str:
        """
        计算VACUUM优先级

        参数:
            dead_ratio: 死元组比例
            dead_tuples: 死元组数量

        返回:
            str: 优先级 (high/medium/low)
        """
        if dead_ratio > 30 or dead_tuples > 100000:
            return "high"
        elif dead_ratio > 15 or dead_tuples > 50000:
            return "medium"
        else:
            return "low"

    def _get_vacuum_statistics(self) -> Dict[str, Any]:
        """获取VACUUM相关统计信息"""
        stats = {}
        try:
            # 获取数据库级别的统计
            result = self._execute_query("""
                SELECT
                    SUM(n_dead_tup) as total_dead_tuples,
                    SUM(n_live_tup) as total_live_tuples,
                    COUNT(*) as total_tables
                FROM pg_stat_user_tables
            """)
            if result and result[0]:
                stats["total_dead_tuples"] = result[0][0] or 0
                stats["total_live_tuples"] = result[0][1] or 0
                stats["total_tables"] = result[0][2] or 0
                if stats["total_live_tuples"] > 0:
                    stats["overall_dead_ratio"] = round(
                        stats["total_dead_tuples"] / stats["total_live_tuples"] * 100, 2
                    )
                else:
                    stats["overall_dead_ratio"] = 0
        except Exception as e:
            logger.warning(f"获取VACUUM统计失败: {e}")

        return stats

    def _calculate_vacuum_health_score(
        self,
        tables: List[Dict],
        settings: Dict[str, Any],
        stats: Dict[str, Any]
    ) -> int:
        """
        计算VACUUM健康评分

        评分标准:
        - 基础分: 100分
        - 高优先级表: -20分/个（最多-40分）
        - 中优先级表: -10分/个（最多-20分）
        - autovacuum关闭: -30分
        - 整体死元组比例: >20% -20分, >10% -10分

        返回:
            int: 健康评分(0-100)
        """
        rules = [
            {
                "name": "高优先级表",
                "filter": lambda x: x.get("priority") == "high",
                "deduction": 20,
                "max_deduction": 40
            },
            {
                "name": "中优先级表",
                "filter": lambda x: x.get("priority") == "medium",
                "deduction": 10,
                "max_deduction": 20
            }
        ]
        score = self._calculate_health_score(tables, rules)

        if settings.get('autovacuum') != 'on':
            score -= 30

        overall_ratio = stats.get("overall_dead_ratio", 0)
        if overall_ratio > 20:
            score -= 20
        elif overall_ratio > 10:
            score -= 10

        return max(0, score)

    def analyze_index_usage(self) -> Dict[str, Any]:
        """
        分析PostgreSQL索引使用情况

        识别未使用或低效的索引，以及可能缺少索引的表。
        提供详细的索引分析、健康评分和具体的优化建议。

        返回:
            Dict: 索引使用分析结果，包含：
                - unused_indexes: 未使用的索引列表
                - hot_indexes: 高频使用索引列表
                - tables_missing_index: 可能缺少索引的表列表
                - duplicate_indexes: 重复索引列表
                - health_score: 健康评分(0-100)
                - suggestions: 优化建议
                - actionable_commands: 可执行的SQL命令
        """
        try:
            # 获取未使用的索引
            unused_indexes = []
            total_unused_size = 0
            result = self._execute_query("""
                SELECT
                    schemaname,
                    relname,
                    indexrelname,
                    idx_scan,
                    pg_size_pretty(pg_relation_size(indexrelid)) as index_size,
                    pg_relation_size(indexrelid) as size_bytes
                FROM pg_stat_user_indexes
                WHERE idx_scan = 0
                AND indexrelname NOT LIKE 'pg_toast_%'
                AND indexrelname NOT LIKE '%_pkey'
                ORDER BY pg_relation_size(indexrelid) DESC
                LIMIT 20
            """)

            for row in result or []:
                size_bytes = row[5] or 0
                total_unused_size += size_bytes
                unused_indexes.append({
                    "schema": row[0],
                    "table": row[1],
                    "index": row[2],
                    "scans": row[3],
                    "size": row[4],
                    "size_bytes": size_bytes,
                    "priority": "high" if size_bytes > 10 * 1024 * 1024 else "medium"  # >10MB为高优先级
                })

            # 获取高频使用索引
            hot_indexes = []
            result = self._execute_query("""
                SELECT
                    schemaname,
                    relname,
                    indexrelname,
                    idx_scan,
                    idx_tup_read,
                    idx_tup_fetch,
                    pg_size_pretty(pg_relation_size(indexrelid)) as index_size,
                    pg_relation_size(indexrelid) as size_bytes
                FROM pg_stat_user_indexes
                WHERE idx_scan > 0
                ORDER BY idx_scan DESC
                LIMIT 20
            """)

            for row in result or []:
                hot_indexes.append({
                    "schema": row[0],
                    "table": row[1],
                    "index": row[2],
                    "scans": row[3],
                    "tuples_read": row[4],
                    "tuples_fetch": row[5],
                    "size": row[6],
                    "size_bytes": row[7] or 0
                })

            # 获取可能缺少索引的表（全表扫描多）
            tables_missing_index = []
            result = self._execute_query("""
                SELECT
                    schemaname,
                    relname,
                    seq_scan,
                    seq_tup_read,
                    idx_scan,
                    CASE WHEN seq_scan > 0
                        THEN ROUND((idx_scan::numeric / seq_scan), 2)
                        ELSE 0
                    END as idx_to_seq_ratio,
                    n_live_tup
                FROM pg_stat_user_tables
                WHERE seq_scan > 100
                AND (idx_scan IS NULL OR seq_scan > idx_scan * 10)
                ORDER BY seq_scan DESC
                LIMIT 20
            """)

            for row in result or []:
                # 跳过schema或表名为空的数据
                if not row[0] or not row[1]:
                    continue
                seq_scans = row[2] or 0
                live_tuples = row[6] or 0
                tables_missing_index.append({
                    "schema": row[0],
                    "table": row[1],
                    "seq_scans": seq_scans,
                    "seq_tuples_read": row[3] or 0,
                    "idx_scans": row[4] or 0,
                    "idx_to_seq_ratio": float(row[5]) if row[5] else 0,
                    "live_tuples": live_tuples,
                    "priority": "high" if seq_scans > 10000 and live_tuples > 10000 else "medium"
                })

            # 检查重复索引
            duplicate_indexes = self._find_duplicate_indexes()

            # 计算健康评分
            health_score = self._calculate_index_health_score(
                unused_indexes, tables_missing_index, duplicate_indexes
            )

            # 生成建议和可执行命令
            suggestions = []
            actionable_commands = []

            if unused_indexes:
                high_priority_unused = [idx for idx in unused_indexes if idx["priority"] == "high"]
                if high_priority_unused:
                    wasted = sum(idx.get("size_bytes", 0) for idx in high_priority_unused)
                    suggestions.append({
                        "type": "warning",
                        "message": f"发现 {len(high_priority_unused)} 个大体积未使用索引(>10MB)",
                        "impact": f"可回收约 {self._format_bytes(wasted)} 空间",
                        "indexes": [f"{idx['table']}.{idx['index']}" for idx in high_priority_unused[:5]]
                    })
                    # 生成删除命令
                    for idx in high_priority_unused[:3]:
                        actionable_commands.append({
                            "priority": "high",
                            "type": "drop_index",
                            "index": f"{idx['schema']}.{idx['index']}",
                            "commands": [
                                f"-- 删除未使用的大索引",
                                f"DROP INDEX CONCURRENTLY IF EXISTS {idx['schema']}.{idx['index']};",
                            ],
                            "description": f"索引大小 {idx['size']}，从未被使用",
                            "warning": "请先在测试环境验证，确认无影响后再执行"
                        })

                if len(unused_indexes) > len(high_priority_unused):
                    suggestions.append({
                        "type": "info",
                        "message": f"还有 {len(unused_indexes) - len(high_priority_unused)} 个小体积未使用索引",
                        "note": "虽然占用空间不大，但会影响写入性能，建议评估后删除"
                    })

            if tables_missing_index:
                high_priority_missing = [t for t in tables_missing_index if t["priority"] == "high"]
                if high_priority_missing:
                    suggestions.append({
                        "type": "critical",
                        "message": f"发现 {len(high_priority_missing)} 个表严重缺少索引",
                        "impact": "大量全表扫描导致查询性能低下",
                        "tables": [f"{t['schema']}.{t['table']}" for t in high_priority_missing[:5]]
                    })
                    for t in high_priority_missing[:3]:
                        actionable_commands.append({
                            "priority": "high",
                            "type": "create_index",
                            "table": f"{t['schema']}.{t['table']}",
                            "commands": [
                                f"-- 为表 {t['schema']}.{t['table']} 创建索引",
                                f"-- 建议步骤:",
                                f"-- 1. 分析慢查询日志，找出常用查询条件",
                                f"-- 2. 使用 EXPLAIN ANALYZE 验证索引效果",
                                f"-- 3. 创建索引 (使用CONCURRENTLY避免锁表):",
                                f"-- CREATE INDEX CONCURRENTLY idx_{t['table']}_xxx ON {t['schema']}.{t['table']}(column_name);",
                            ],
                            "description": f"表有 {t['seq_scans']} 次全表扫描，{t['live_tuples']} 行数据"
                        })

                medium_priority_missing = [t for t in tables_missing_index if t["priority"] == "medium"]
                if medium_priority_missing:
                    suggestions.append({
                        "type": "info",
                        "message": f"发现 {len(medium_priority_missing)} 个表可能缺少索引",
                        "tables": [f"{t['schema']}.{t['table']}" for t in medium_priority_missing[:5]]
                    })

            if duplicate_indexes:
                suggestions.append({
                    "type": "warning",
                    "message": f"发现 {len(duplicate_indexes)} 组重复索引",
                    "note": "重复索引浪费空间且影响写入性能，建议删除冗余索引"
                })
                for dup in duplicate_indexes[:2]:
                    actionable_commands.append({
                        "priority": "medium",
                        "type": "drop_duplicate_index",
                        "table": dup["table"],
                        "commands": [
                            f"-- 删除重复索引: {dup['redundant_index']}",
                            f"-- 保留索引: {dup['kept_index']}",
                            f"DROP INDEX CONCURRENTLY IF EXISTS {dup['schema']}.{dup['redundant_index']};",
                        ],
                        "description": f"索引 {dup['redundant_index']} 被 {dup['kept_index']} 包含"
                    })

            return self._create_result(
                success=True,
                message=f"索引使用分析完成，健康评分: {health_score}/100",
                data={
                    "unused_indexes": unused_indexes,
                    "hot_indexes": hot_indexes,
                    "tables_missing_index": tables_missing_index,
                    "duplicate_indexes": duplicate_indexes,
                    "health_score": health_score,
                    "total_unused_index_size": self._format_bytes(total_unused_size),
                    "total_unused_index_bytes": total_unused_size,
                    "suggestions": suggestions,
                    "actionable_commands": actionable_commands
                }
            )

        except Exception as e:
            logger.error(f"索引使用分析失败: {e}")
            return self._create_result(
                success=False,
                message="索引使用分析失败",
                error=str(e)
            )

    def _find_duplicate_indexes(self) -> List[Dict]:
        """
        查找重复索引

        通过比较索引定义来识别可能重复的索引

        返回:
            List[Dict]: 重复索引列表
        """
        try:
            # 获取所有索引定义
            result = self._execute_query("""
                SELECT
                    schemaname,
                    tablename,
                    indexname,
                    indexdef
                FROM pg_indexes
                WHERE schemaname NOT IN ('pg_catalog', 'information_schema')
                ORDER BY tablename, indexname
            """)

            # 按表分组索引
            table_indexes = {}
            for row in result or []:
                schema, table, index_name, index_def = row
                key = f"{schema}.{table}"
                if key not in table_indexes:
                    table_indexes[key] = []
                table_indexes[key].append({
                    "schema": schema,
                    "table": table,
                    "index": index_name,
                    "definition": index_def
                })

            duplicates = []

            # 检查每个表的索引
            for table_key, indexes in table_indexes.items():
                if len(indexes) < 2:
                    continue

                # 比较索引定义
                for i, idx1 in enumerate(indexes):
                    for j, idx2 in enumerate(indexes):
                        if i >= j:
                            continue

                        def1 = idx1.get("definition", "")
                        def2 = idx2.get("definition", "")

                        if not def1 or not def2:
                            continue

                        # 提取索引列定义（简化处理）
                        # 检查一个索引定义是否包含另一个
                        if def1 in def2 or def2 in def1:
                            # 确定哪个是冗余的（通常是更具体的那个）
                            if len(def1) > len(def2):
                                redundant, kept = idx1, idx2
                            else:
                                redundant, kept = idx2, idx1

                            duplicates.append({
                                "schema": redundant["schema"],
                                "table": redundant["table"],
                                "redundant_index": redundant["index"],
                                "kept_index": kept["index"],
                                "reason": "索引定义重复或包含"
                            })

            return duplicates[:10]  # 限制返回数量

        except Exception as e:
            logger.warning(f"查找重复索引失败: {e}")
            return []

    def _calculate_index_health_score(
        self,
        unused_indexes: List[Dict],
        tables_missing_index: List[Dict],
        duplicate_indexes: List[Dict]
    ) -> int:
        """
        计算索引健康评分

        评分标准:
        - 基础分: 100分
        - 高优先级未使用索引: -10分/个（最多-30分）
        - 高优先级缺少索引: -15分/个（最多-45分）
        - 重复索引: -5分/组（最多-15分）

        返回:
            int: 健康评分(0-100)
        """
        all_items = unused_indexes + tables_missing_index + duplicate_indexes
        rules = [
            {
                "name": "高优先级未使用索引",
                "filter": lambda x: x.get("priority") == "high" and x.get("size_bytes") is not None,
                "deduction": 10,
                "max_deduction": 30
            },
            {
                "name": "高优先级缺少索引",
                "filter": lambda x: x.get("priority") == "high" and x.get("seq_scan") is not None,
                "deduction": 15,
                "max_deduction": 45
            },
            {
                "name": "重复索引",
                "filter": lambda x: x.get("duplicate_of") is not None,
                "deduction": 5,
                "max_deduction": 15
            }
        ]
        return self._calculate_health_score(all_items, rules)

    def analyze_table_bloat(self, threshold: int = 30) -> Dict[str, Any]:
        """
        分析PostgreSQL表膨胀情况

        表膨胀是PostgreSQL特有的问题，由MVCC机制导致。
        提供详细的膨胀分析、健康评分和具体的维护建议。

        参数:
            threshold: 膨胀率阈值（百分比），超过此值的表会被标记为严重膨胀

        返回:
            Dict: 表膨胀分析结果，包含：
                - bloated_tables: 膨胀表列表
                - severely_bloated_count: 严重膨胀表数量
                - has_pgstattuple: 是否安装了pgstattuple扩展
                - health_score: 健康评分(0-100)
                - total_wasted_space: 总浪费空间
                - suggestions: 维护建议
                - actionable_commands: 可执行的维护命令
        """
        try:
            # 使用pgstattuple扩展（如果可用）获取准确的膨胀率
            has_pgstattuple = False
            try:
                result = self._execute_query("""
                    SELECT COUNT(*) FROM pg_extension WHERE extname = 'pgstattuple'
                """)
                has_pgstattuple = result and result[0][0] > 0
            except Exception:
                pass

            bloated_tables = []
            total_wasted_space = 0

            if has_pgstattuple:
                # 使用pgstattuple获取准确的膨胀信息
                result = self._execute_query("""
                    SELECT
                        schemaname,
                        relname,
                        pg_size_pretty(pg_total_relation_size(schemaname || '.' || relname)) as total_size,
                        pg_size_pretty(pg_relation_size(schemaname || '.' || relname)) as table_size,
                        pg_total_relation_size(schemaname || '.' || relname) as size_bytes
                    FROM pg_stat_user_tables
                    ORDER BY pg_total_relation_size(schemaname || '.' || relname) DESC
                    LIMIT 50
                """)

                for row in result or []:
                    try:
                        # 尝试获取膨胀信息（使用参数化查询防止SQL注入）
                        table_fullname = f"{row[0]}.{row[1]}"
                        bloat_result = self._execute_query("""
                            SELECT
                                table_len,
                                tuple_count,
                                dead_tuple_count,
                                free_space,
                                ROUND(dead_tuple_len::numeric / NULLIF(table_len, 0) * 100, 2) as bloat_ratio
                            FROM pgstattuple(%s)
                        """, (table_fullname,))

                        if bloat_result:
                            bloat_ratio = float(bloat_result[0][4]) if bloat_result[0][4] else 0
                            size_bytes = row[4] or 0
                            wasted = int(size_bytes * bloat_ratio / 100)
                            total_wasted_space += wasted

                            bloated_tables.append({
                                "schema": row[0],
                                "table": row[1],
                                "total_size": row[2],
                                "table_size": row[3],
                                "size_bytes": size_bytes,
                                "tuple_count": bloat_result[0][1],
                                "dead_tuples": bloat_result[0][2],
                                "bloat_ratio": bloat_ratio,
                                "wasted_space_bytes": wasted,
                                "priority": self._calculate_bloat_priority(bloat_ratio)
                            })
                    except Exception as e:
                        logger.warning(f"获取表 {row[0]}.{row[1]} 膨胀信息失败: {e}")
                        continue
            else:
                # 降级方案：基于统计信息估算
                result = self._execute_query("""
                    SELECT
                        schemaname,
                        relname,
                        n_live_tup,
                        n_dead_tup,
                        CASE WHEN n_live_tup > 0
                            THEN ROUND((n_dead_tup::numeric / n_live_tup) * 100, 2)
                            ELSE 0
                        END AS estimated_bloat_ratio,
                        pg_size_pretty(pg_total_relation_size(schemaname || '.' || relname)) as total_size,
                        pg_size_pretty(pg_relation_size(schemaname || '.' || relname)) as table_size,
                        pg_total_relation_size(schemaname || '.' || relname) as size_bytes
                    FROM pg_stat_user_tables
                    WHERE n_dead_tup > 1000
                    ORDER BY n_dead_tup DESC
                    LIMIT 30
                """)

                for row in result or []:
                    estimated_ratio = float(row[4]) if row[4] else 0
                    size_bytes = row[7] or 0
                    wasted = int(size_bytes * estimated_ratio / 100)
                    total_wasted_space += wasted

                    bloated_tables.append({
                        "schema": row[0],
                        "table": row[1],
                        "live_tuples": row[2],
                        "dead_tuples": row[3],
                        "estimated_bloat_ratio": estimated_ratio,
                        "total_size": row[5],
                        "table_size": row[6],
                        "size_bytes": size_bytes,
                        "wasted_space_bytes": wasted,
                        "priority": self._calculate_bloat_priority(estimated_ratio)
                    })

            # 按膨胀率排序
            bloated_tables.sort(
                key=lambda x: x.get("bloat_ratio", 0) or x.get("estimated_bloat_ratio", 0),
                reverse=True
            )

            # 识别严重膨胀的表（使用传入的阈值）
            severely_bloated = [t for t in bloated_tables
                               if t.get("bloat_ratio", 0) > threshold or t.get("estimated_bloat_ratio", 0) > threshold]

            # 计算健康评分
            health_score = self._calculate_bloat_health_score(bloated_tables, severely_bloated, has_pgstattuple)

            # 生成建议和可执行命令
            suggestions = []
            actionable_commands = []

            if severely_bloated:
                high_priority = [t for t in severely_bloated if t["priority"] == "high"]
                if high_priority:
                    wasted = sum(t.get("wasted_space_bytes", 0) for t in high_priority)
                    suggestions.append({
                        "type": "critical",
                        "message": f"发现 {len(high_priority)} 个表严重膨胀，需要立即处理",
                        "impact": f"预计可回收 {self._format_bytes(wasted)} 空间",
                        "tables": [f"{t['schema']}.{t['table']}" for t in high_priority[:5]]
                    })
                    # 生成高优先级表的维护命令
                    for t in high_priority[:3]:
                        actionable_commands.append({
                            "priority": "high",
                            "table": f"{t['schema']}.{t['table']}",
                            "commands": [
                                f"-- 方法1: VACUUM FULL (锁表，最彻底)",
                                f"VACUUM FULL {t['schema']}.{t['table']};",
                                f"",
                                f"-- 方法2: 使用pg_repack (在线，推荐)",
                                f"pg_repack -t {t['schema']}.{t['table']} -d your_database",
                            ],
                            "description": f"表膨胀率 {t.get('bloat_ratio', t.get('estimated_bloat_ratio', 0)):.1f}%，预计可回收 {self._format_bytes(t.get('wasted_space_bytes', 0))}"
                        })

                medium_priority = [t for t in severely_bloated if t["priority"] == "medium"]
                if medium_priority:
                    suggestions.append({
                        "type": "warning",
                        "message": f"发现 {len(medium_priority)} 个表中度膨胀，建议在维护窗口处理",
                        "tables": [f"{t['schema']}.{t['table']}" for t in medium_priority[:5]]
                    })

            if not has_pgstattuple:
                suggestions.append({
                    "type": "info",
                    "message": "建议安装pgstattuple扩展以获取更准确的膨胀分析",
                    "install_sql": "CREATE EXTENSION IF NOT EXISTS pgstattuple;",
                    "note": "安装后可以获得更精确的膨胀率数据"
                })

            return self._create_result(
                success=True,
                message=f"表膨胀分析完成，健康评分: {health_score}/100",
                data={
                    "bloated_tables": bloated_tables,
                    "severely_bloated_count": len(severely_bloated),
                    "has_pgstattuple": has_pgstattuple,
                    "health_score": health_score,
                    "total_wasted_space": self._format_bytes(total_wasted_space),
                    "total_wasted_space_bytes": total_wasted_space,
                    "suggestions": suggestions,
                    "actionable_commands": actionable_commands
                }
            )

        except Exception as e:
            logger.error(f"表膨胀分析失败: {e}")
            return self._create_result(
                success=False,
                message="表膨胀分析失败",
                error=str(e)
            )

    def _calculate_bloat_priority(self, bloat_ratio: float) -> str:
        """
        计算膨胀处理优先级

        参数:
            bloat_ratio: 膨胀率

        返回:
            str: 优先级 (high/medium/low)
        """
        if bloat_ratio > 50:
            return "high"
        elif bloat_ratio > 30:
            return "medium"
        else:
            return "low"

    def _calculate_bloat_health_score(
        self,
        bloated_tables: List[Dict],
        severely_bloated: List[Dict],
        has_pgstattuple: bool
    ) -> int:
        """
        计算膨胀健康评分

        评分标准:
        - 基础分: 100分
        - 高优先级膨胀表: -15分/个（最多-45分）
        - 中优先级膨胀表: -8分/个（最多-24分）
        - 未安装pgstattuple: -10分

        返回:
            int: 健康评分(0-100)
        """
        rules = [
            {
                "name": "高优先级膨胀表",
                "filter": lambda x: x.get("priority") == "high",
                "deduction": 15,
                "max_deduction": 45
            },
            {
                "name": "中优先级膨胀表",
                "filter": lambda x: x.get("priority") == "medium",
                "deduction": 8,
                "max_deduction": 24
            }
        ]
        score = self._calculate_health_score(bloated_tables, rules)

        if not has_pgstattuple:
            score -= 10

        return max(0, score)

    def analyze_replication_status(self) -> Dict[str, Any]:
        """
        分析PostgreSQL复制状态

        支持物理复制和逻辑复制的状态检查

        返回:
            Dict: 复制状态分析结果
        """
        try:
            # 检查是否是备库
            result = self._execute_query("SELECT pg_is_in_recovery()")
            is_standby = result and result[0][0] if result else False

            replication_info = {
                "is_standby": is_standby,
                "replication_mode": None,
                "lag_seconds": 0,
                "replication_slots": [],
                "replication_connections": []
            }

            if is_standby:
                # 备库：检查复制延迟
                replication_info["replication_mode"] = "physical_standby"

                # 获取WAL接收和应用位置
                result = self._execute_query("""
                    SELECT
                        pg_last_wal_receive_lsn(),
                        pg_last_wal_replay_lsn(),
                        pg_last_xact_replay_timestamp()
                """)

                if result:
                    receive_lsn, replay_lsn, replay_timestamp = result[0]
                    replication_info["receive_lsn"] = str(receive_lsn) if receive_lsn else None
                    replication_info["replay_lsn"] = str(replay_lsn) if replay_lsn else None
                    replication_info["replay_timestamp"] = replay_timestamp.isoformat() if replay_timestamp else None

                # 计算延迟
                result = self._execute_query("""
                    SELECT
                        CASE
                            WHEN pg_last_wal_receive_lsn() = pg_last_wal_replay_lsn()
                            THEN 0
                            ELSE EXTRACT(EPOCH FROM (now() - pg_last_xact_replay_timestamp()))
                        END
                """)

                if result and result[0][0]:
                    replication_info["lag_seconds"] = float(result[0][0])

            else:
                # 主库：检查复制连接和slot
                replication_info["replication_mode"] = "primary"

                # 获取复制连接
                result = self._execute_query("""
                    SELECT
                        client_addr,
                        state,
                        sent_lsn,
                        write_lsn,
                        flush_lsn,
                        replay_lsn,
                        EXTRACT(EPOCH FROM (now() - backend_start)) as connected_seconds
                    FROM pg_stat_replication
                """)

                for row in result or []:
                    replication_info["replication_connections"].append({
                        "client_addr": str(row[0]) if row[0] else None,
                        "state": row[1],
                        "sent_lsn": str(row[2]) if row[2] else None,
                        "write_lsn": str(row[3]) if row[3] else None,
                        "flush_lsn": str(row[4]) if row[4] else None,
                        "replay_lsn": str(row[5]) if row[5] else None,
                        "connected_seconds": float(row[6]) if row[6] else 0
                    })

                # 获取复制slot
                result = self._execute_query("""
                    SELECT
                        slot_name,
                        plugin,
                        slot_type,
                        active,
                        restart_lsn,
                        confirmed_flush_lsn
                    FROM pg_replication_slots
                """)

                for row in result or []:
                    replication_info["replication_slots"].append({
                        "slot_name": row[0],
                        "plugin": row[1],
                        "slot_type": row[2],
                        "active": row[3],
                        "restart_lsn": str(row[4]) if row[4] else None,
                        "confirmed_flush_lsn": str(row[5]) if row[5] else None
                    })

            # 生成建议
            suggestions = []
            if is_standby and replication_info["lag_seconds"] > 300:
                suggestions.append({
                    "type": "warning",
                    "message": f"复制延迟超过5分钟（{replication_info['lag_seconds']:.1f}秒），请检查网络或主库负载",
                    "lag_seconds": replication_info["lag_seconds"]
                })

            if not is_standby and not replication_info["replication_connections"]:
                suggestions.append({
                    "type": "info",
                    "message": "当前没有活跃的复制连接，如果是主库请检查备库状态"
                })

            return self._create_result(
                success=True,
                message="复制状态分析完成",
                data=replication_info
            )

        except Exception as e:
            logger.error(f"复制状态分析失败: {e}")
            return self._create_result(
                success=False,
                message="复制状态分析失败",
                error=str(e)
            )
