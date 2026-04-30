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
