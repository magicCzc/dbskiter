"""
lock_analyzer mixin for DiagnoseSkill

Auto-extracted from skill.py.
"""

import logging
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


class LockAnalyzerMixin:
    """lock_analyzer for DiagnoseSkill"""

    def get_lock_waits(self) -> Dict[str, Any]:
        """
        获取锁等待信息

        返回:
            Dict: 锁等待列表
        """
        try:
            if self._diagnostician:
                result = self._diagnostician.get_lock_waits()
                return self._convert_diagnostician_result(result)
            else:
                return create_error_response(
                    f"锁等待分析暂不支持 {self.dialect}",
                    ErrorCode.UNSUPPORTED_SQL
                )
        except Exception as e:
            logger.error(f"获取锁等待失败: {e}")
            return create_error_response(str(e), ErrorCode.UNKNOWN_ERROR)


    def analyze_locks(self) -> Dict[str, Any]:
        """
        综合分析锁情况（已接入多步骤计时）

        返回:
            Dict: 锁分析结果，包含 _execution_time 步骤耗时
        """
        from dbskiter.shared.execution_timer import ExecutionTimer
        timer = ExecutionTimer().start()

        try:
            with timer.step("select_engine", "选择数据库引擎适配"):
                if 'mysql' in self.dialect:
                    result = self._analyze_mysql_locks()
                elif 'oracle' in self.dialect:
                    result = self._analyze_oracle_locks()
                elif 'postgresql' in self.dialect:
                    result = self._analyze_postgresql_locks()
                elif 'mssql' in self.dialect or 'sqlserver' in self.dialect:
                    result = self._analyze_mssql_locks()
                elif 'clickhouse' in self.dialect:
                    result = self._analyze_clickhouse_locks()
                elif 'sqlite' in self.dialect:
                    result = self._analyze_sqlite_locks()
                else:
                    result = create_error_response(
                        f"锁分析暂不支持 {self.dialect}",
                        ErrorCode.UNSUPPORTED_SQL
                    )

            with timer.step("format_result", "转换并封装结果"):
                if isinstance(result, dict) and "_execution_time" not in result:
                    pass

            result["_execution_time"] = timer.to_summary()
            return result
        except Exception as e:
            logger.error(f"锁分析失败: {e}")
            return create_error_response(str(e), ErrorCode.UNKNOWN_ERROR)


    def _analyze_mysql_locks(self) -> Dict[str, Any]:
        """MySQL锁分析"""
        try:
            # 获取锁等待
            lock_waits_result = self._diagnostician.get_lock_waits()
            lock_waits = lock_waits_result.get('data', {}).get('lock_waits', [])

            # 获取事务统计
            result = self.connector.execute("""
                SELECT 
                    COUNT(*) as trx_count,
                    SUM(CASE WHEN trx_state = 'RUNNING' THEN 1 ELSE 0 END) as running
                FROM information_schema.INNODB_TRX
            """)

            row = result.rows[0] if result.rows else (0, 0)

            return create_success_response(
                message="锁分析完成",
                data={
                    "lock_waits": lock_waits,
                    "deadlocks": [],  # 需要查询performance_schema
                    "statistics": {
                        "trx_count": row[0],
                        "running_trx": row[1],
                        "lock_waits_count": len(lock_waits)
                    }
                }
            )
        except Exception as e:
            return create_error_response(str(e), ErrorCode.UNKNOWN_ERROR)


    def _analyze_oracle_locks(self) -> Dict[str, Any]:
        """Oracle锁分析"""
        try:
            lock_waits_result = self._diagnostician.get_lock_waits()
            lock_waits = lock_waits_result.get('data', {}).get('lock_waits', [])

            # 获取事务统计
            result2 = self.connector.execute("""
                SELECT
                    COUNT(*) AS total_trx,
                    SUM(CASE WHEN status = 'ACTIVE' THEN 1 ELSE 0 END) AS active_trx
                FROM v$transaction
            """)

            row = result2.rows[0] if result2.rows else (0, 0)

            # 检测死锁（基于alert日志或v$lock循环等待）
            deadlocks = []
            try:
                result3 = self.connector.execute("""
                    SELECT COUNT(*) FROM v$lock
                    WHERE request > 0 AND ctime > 60
                """)
                long_wait_count = int(str(result3.rows[0][0])) if result3.rows else 0
                if long_wait_count > 0:
                    deadlocks.append({
                        "type": "long_lock_wait",
                        "description": f"发现 {long_wait_count} 个等待超过60秒的锁请求",
                        "suggestion": "检查是否存在阻塞事务，考虑终止或优化"
                    })
            except Exception:
                pass

            return create_success_response(
                message="锁分析完成",
                data={
                    "lock_waits": lock_waits,
                    "deadlocks": deadlocks,
                    "statistics": {
                        "trx_count": int(str(row[0])) if row[0] else 0,
                        "running_trx": int(str(row[1])) if row[1] else 0,
                        "lock_waits_count": len(lock_waits)
                    }
                }
            )
        except Exception as e:
            return create_error_response(str(e), ErrorCode.UNKNOWN_ERROR)


    def _analyze_postgresql_locks(self) -> Dict[str, Any]:
        """PostgreSQL锁分析"""
        try:
            lock_waits_result = self._diagnostician.get_lock_waits()
            lock_waits = lock_waits_result.get('data', {}).get('lock_waits', [])

            deadlocks = 0
            try:
                result = self.connector.execute("""
                    SELECT deadlocks
                    FROM pg_stat_database
                    WHERE datname = current_database()
                """)
                if result.rows:
                    deadlocks = int(str(result.rows[0][0])) if result.rows[0][0] else 0
            except Exception:
                pass

            active_trx = 0
            try:
                result = self.connector.execute("""
                    SELECT COUNT(*)
                    FROM pg_stat_activity
                    WHERE xact_start IS NOT NULL
                    AND backend_type = 'client backend'
                """)
                if result.rows:
                    active_trx = int(str(result.rows[0][0])) if result.rows[0][0] else 0
            except Exception:
                pass

            return create_success_response(
                message="锁分析完成",
                data={
                    "lock_waits": lock_waits,
                    "deadlocks": [{"count": deadlocks}] if deadlocks > 0 else [],
                    "statistics": {
                        "trx_count": active_trx,
                        "running_trx": active_trx,
                        "lock_waits_count": len(lock_waits),
                        "deadlock_count": deadlocks
                    }
                }
            )
        except Exception as e:
            return create_error_response(str(e), ErrorCode.UNKNOWN_ERROR)


    def _analyze_mssql_locks(self) -> Dict[str, Any]:
        """SQL Server锁分析"""
        try:
            # 获取锁等待信息
            lock_waits = []
            try:
                result = self.connector.execute("""
                    SELECT
                        r.session_id AS waiting_session,
                        r.blocking_session_id AS blocking_session,
                        r.wait_type,
                        r.wait_time / 1000.0 AS wait_seconds,
                        DB_NAME(r.database_id) AS database_name,
                        t.text AS sql_text,
                        s.login_name,
                        s.host_name
                    FROM sys.dm_exec_requests r
                    JOIN sys.dm_exec_sessions s ON r.session_id = s.session_id
                    CROSS APPLY sys.dm_exec_sql_text(r.sql_handle) t
                    WHERE r.blocking_session_id IS NOT NULL
                    AND r.blocking_session_id <> 0
                    ORDER BY r.wait_time DESC
                """)
                for row in result.rows if result else []:
                    lock_waits.append({
                        "waiting_session": row[0],
                        "blocking_session": row[1],
                        "wait_type": row[2],
                        "wait_seconds": row[3],
                        "database": row[4],
                        "sql_preview": row[5][:200] if row[5] else None,
                        "login": row[6],
                        "host": row[7]
                    })
            except Exception as e:
                logger.warning(f"获取SQL Server锁等待信息失败: {e}")

            # 获取死锁信息
            deadlocks = []
            try:
                result = self.connector.execute("""
                    SELECT TOP 10
                        xml_deadlock_report,
                        deadlock_graph,
                        creation_time
                    FROM sys.dm_xe_session_targets t
                    JOIN sys.dm_xe_sessions s ON t.event_session_address = s.address
                    JOIN sys.dm_xe_session_events e ON s.address = e.event_session_address
                    WHERE s.name = 'system_health'
                    AND e.package_name = 'sqlserver'
                    AND e.event_name = 'xml_deadlock_report'
                    AND t.target_name = 'ring_buffer'
                    ORDER BY creation_time DESC
                """)
                for row in result.rows if result else []:
                    deadlocks.append({
                        "report": row[0],
                        "time": row[2]
                    })
            except Exception as e:
                logger.warning(f"获取SQL Server死锁信息失败: {e}")

            # 获取活动事务统计
            active_trx = 0
            try:
                result = self.connector.execute("""
                    SELECT COUNT(*)
                    FROM sys.dm_tran_active_transactions
                    WHERE transaction_begin_time < DATEADD(SECOND, -5, GETDATE())
                """)
                if result.rows:
                    active_trx = int(result.rows[0][0]) if result.rows[0][0] else 0
            except Exception:
                pass

            return create_success_response(
                message="锁分析完成",
                data={
                    "lock_waits": lock_waits,
                    "deadlocks": deadlocks,
                    "statistics": {
                        "trx_count": active_trx,
                        "running_trx": active_trx,
                        "lock_waits_count": len(lock_waits),
                        "deadlock_count": len(deadlocks)
                    }
                }
            )
        except Exception as e:
            return create_error_response(str(e), ErrorCode.UNKNOWN_ERROR)


    def _analyze_clickhouse_locks(self) -> Dict[str, Any]:
        """
        ClickHouse锁分析

        ClickHouse锁模型简单，主要关注:
        1. 正在执行的mutation（异步ALTER操作）
        2. 长时间运行的查询
        3. 复制队列阻塞

        返回:
            Dict: 锁分析结果
        """
        try:
            lock_waits = []
            deadlocks = []

            # 获取正在执行的mutation（ALTER操作）
            try:
                result = self.connector.execute("""
                    SELECT
                        database,
                        table,
                        mutation_id,
                        command,
                        create_time,
                        parts_to_do
                    FROM system.mutations
                    WHERE is_done = 0
                    ORDER BY create_time DESC
                """)
                for row in result.rows if result else []:
                    lock_waits.append({
                        "type": "mutation",
                        "database": str(row[0]) if row[0] else "",
                        "table": str(row[1]) if row[1] else "",
                        "mutation_id": str(row[2]) if row[2] else "",
                        "command": str(row[3])[:100] if row[3] else "",
                        "create_time": str(row[4]) if row[4] else "",
                        "parts_to_do": int(row[5]) if row[5] else 0
                    })
            except Exception as e:
                logger.warning(f"获取ClickHouse mutation信息失败: {e}")

            # 获取长时间运行的查询
            try:
                result = self.connector.execute("""
                    SELECT
                        query_id,
                        user,
                        query,
                        elapsed,
                        read_rows,
                        memory_usage
                    FROM system.processes
                    WHERE elapsed > 60
                    ORDER BY elapsed DESC
                """)
                for row in result.rows if result else []:
                    deadlocks.append({
                        "type": "long_running_query",
                        "query_id": str(row[0]) if row[0] else "",
                        "user": str(row[1]) if row[1] else "",
                        "query_preview": str(row[2])[:100] if row[2] else "",
                        "elapsed_seconds": float(row[3]) if row[3] else 0,
                        "read_rows": int(row[4]) if row[4] else 0,
                        "memory_usage": int(row[5]) if row[5] else 0
                    })
            except Exception as e:
                logger.warning(f"获取ClickHouse长时间运行查询失败: {e}")

            # 获取replicated_fetches状态（副本间数据fetch）
            try:
                result = self.connector.execute("""
                    SELECT
                        database,
                        table,
                        source_replica,
                        source_replica_path,
                        part_name,
                        total_size,
                        bytes_size,
                        elapsed
                    FROM system.replicated_fetches
                    ORDER BY elapsed DESC
                    LIMIT 20
                """)
                replicated_fetches = []
                for row in result.rows if result else []:
                    replicated_fetches.append({
                        "type": "replicated_fetch",
                        "database": str(row[0]) if row[0] else "",
                        "table": str(row[1]) if row[1] else "",
                        "source_replica": str(row[2]) if row[2] else "",
                        "source_path": str(row[3]) if row[3] else "",
                        "part_name": str(row[4]) if row[4] else "",
                        "total_size": int(row[5]) if row[5] else 0,
                        "bytes_fetched": int(row[6]) if row[6] else 0,
                        "elapsed_seconds": float(row[7]) if row[7] else 0
                    })

                if replicated_fetches:
                    lock_waits.extend(replicated_fetches)
            except Exception as e:
                logger.warning(f"获取ClickHouse replicated_fetches失败: {e}")

            # 获取merge状态
            try:
                result = self.connector.execute("""
                    SELECT
                        database,
                        table,
                        elapsed,
                        progress,
                        num_parts,
                        result_part_name,
                        total_size_bytes_compressed
                    FROM system.merges
                    ORDER BY elapsed DESC
                    LIMIT 20
                """)
                merges = []
                for row in result.rows if result else []:
                    merges.append({
                        "type": "merge",
                        "database": str(row[0]) if row[0] else "",
                        "table": str(row[1]) if row[1] else "",
                        "elapsed_seconds": float(row[2]) if row[2] else 0,
                        "progress": float(row[3]) if row[3] else 0,
                        "num_parts": int(row[4]) if row[4] else 0,
                        "result_part": str(row[5]) if row[5] else "",
                        "total_size_bytes": int(row[6]) if row[6] else 0
                    })

                if merges:
                    lock_waits.extend(merges)
            except Exception as e:
                logger.warning(f"获取ClickHouse merges失败: {e}")

            return create_success_response(
                message="ClickHouse锁分析完成",
                data={
                    "lock_waits": lock_waits,
                    "deadlocks": deadlocks,
                    "statistics": {
                        "trx_count": len(lock_waits),
                        "running_trx": len(lock_waits),
                        "lock_waits_count": len(lock_waits),
                        "deadlock_count": len(deadlocks)
                    }
                }
            )
        except Exception as e:
            return create_error_response(str(e), ErrorCode.UNKNOWN_ERROR)


    def _analyze_sqlite_locks(self) -> Dict[str, Any]:
        """
        SQLite锁分析

        SQLite使用文件级锁，主要关注:
        1. 当前锁状态（通过PRAGMA lock_status）
        2. 长时间运行的事务

        返回:
            Dict: 锁分析结果
        """
        try:
            lock_waits = []
            deadlocks = []

            # 获取锁状态
            try:
                result = self.connector.execute("PRAGMA lock_status")
                for row in result.rows if result else []:
                    lock_waits.append({
                        "type": "file_lock",
                        "database": str(row[0]) if row[0] else "main",
                        "lock_type": str(row[1]) if len(row) > 1 else "unknown"
                    })
            except Exception as e:
                logger.warning(f"获取SQLite锁状态失败: {e}")

            return create_success_response(
                message="SQLite锁分析完成",
                data={
                    "lock_waits": lock_waits,
                    "deadlocks": deadlocks,
                    "statistics": {
                        "trx_count": 0,
                        "running_trx": 0,
                        "lock_waits_count": len(lock_waits),
                        "deadlock_count": 0
                    }
                }
            )
        except Exception as e:
            return create_error_response(str(e), ErrorCode.UNKNOWN_ERROR)


