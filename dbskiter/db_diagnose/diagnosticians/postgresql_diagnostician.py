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

    提供PostgreSQL特有的慢查询分析、性能分析、统计信息获取
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
                return self._create_result(
                    success=False,
                    message="pg_stat_statements扩展未启用",
                    error="请安装并启用pg_stat_statements扩展",
                    data={"total_queries": 0, "queries": []}
                )

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
