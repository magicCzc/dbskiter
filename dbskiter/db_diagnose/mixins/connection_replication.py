"""
connection_replication mixin for DiagnoseSkill

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


class ConnectionReplicationMixin:
    """connection_replication for DiagnoseSkill"""

    def analyze_connections(self, show_idle: bool = False) -> Dict[str, Any]:
        """
        连接分析

        参数:
            show_idle: 是否显示空闲连接

        返回:
            Dict: 连接分析结果
        """
        try:
            if 'mysql' in self.dialect:
                return self._analyze_mysql_connections(show_idle)
            elif 'oracle' in self.dialect:
                return self._analyze_oracle_connections(show_idle)
            elif 'postgresql' in self.dialect:
                return self._analyze_postgresql_connections(show_idle)
            elif 'clickhouse' in self.dialect:
                return self._analyze_clickhouse_connections(show_idle)
            elif 'sqlite' in self.dialect:
                return self._analyze_sqlite_connections(show_idle)
            else:
                return create_error_response(
                    f"连接分析暂不支持 {self.dialect}",
                    ErrorCode.UNSUPPORTED_SQL
                )
        except Exception as e:
            logger.error(f"连接分析失败: {e}")
            return create_error_response(str(e), ErrorCode.UNKNOWN_ERROR)


    def _analyze_mysql_connections(self, show_idle: bool) -> Dict[str, Any]:
        """MySQL连接分析"""
        try:
            # 获取连接统计
            result = self.connector.execute("""
                SELECT 
                    @@max_connections as max_conn,
                    COUNT(*) as current,
                    SUM(CASE WHEN COMMAND != 'Sleep' THEN 1 ELSE 0 END) as active,
                    SUM(CASE WHEN COMMAND = 'Sleep' THEN 1 ELSE 0 END) as idle
                FROM information_schema.PROCESSLIST
                WHERE USER != 'system user'
            """)

            row = result.rows[0] if result.rows else (100, 0, 0, 0)
            max_conn, current, active, idle = row
            usage_pct = (current / max_conn * 100) if max_conn > 0 else 0

            data = {
                "statistics": {
                    "max_connections": max_conn,
                    "current": current,
                    "active": active,
                    "idle": idle,
                    "usage_percent": round(usage_pct, 1)
                }
            }

            # 获取空闲连接详情
            if show_idle:
                result = self.connector.execute("""
                    SELECT 
                        ID,
                        USER,
                        HOST,
                        TIME as idle_time
                    FROM information_schema.PROCESSLIST
                    WHERE COMMAND = 'Sleep'
                        AND USER != 'system user'
                    ORDER BY TIME DESC
                    LIMIT 20
                """)

                idle_conns = []
                for row in result.rows:
                    idle_conns.append({
                        "id": row[0],
                        "user": row[1],
                        "host": row[2],
                        "idle_time": row[3]
                    })
                data["idle_connections"] = idle_conns

            return create_success_response(
                message="连接分析完成",
                data=data
            )
        except Exception as e:
            return create_error_response(str(e), ErrorCode.UNKNOWN_ERROR)


    def _analyze_oracle_connections(self, show_idle: bool) -> Dict[str, Any]:
        """
        Oracle连接分析

        参数:
            show_idle: 是否显示空闲连接

        返回:
            Dict: 连接分析结果
        """
        try:
            # 获取连接统计
            # 分两步查询避免CROSS JOIN + GROUP BY兼容性问题
            max_sessions = 100
            result = self.connector.execute(
                "SELECT value FROM v$parameter WHERE name = 'sessions'"
            )
            if result.rows:
                max_sessions = int(str(result.rows[0][0])) if result.rows[0][0] else 100

            result = self.connector.execute("""
                SELECT
                    COUNT(*) AS total_count,
                    SUM(CASE WHEN status = 'ACTIVE' THEN 1 ELSE 0 END) AS active_count,
                    SUM(CASE WHEN status = 'INACTIVE' THEN 1 ELSE 0 END) AS idle_count
                FROM v$session
                WHERE type != 'BACKGROUND'
            """)

            if result.rows:
                row = result.rows[0]
                current = int(str(row[0])) if row[0] else 0
                active = int(str(row[1])) if row[1] else 0
                idle = int(str(row[2])) if row[2] else 0
            else:
                current = active = idle = 0

            usage_pct = (current / max_sessions * 100) if max_sessions > 0 else 0

            data = {
                "statistics": {
                    "max_connections": max_sessions,
                    "current": current,
                    "active": active,
                    "idle": idle,
                    "usage_percent": round(usage_pct, 1)
                }
            }

            # 获取空闲连接详情
            if show_idle:
                result = self.connector.execute("""
                    SELECT * FROM (
                        SELECT
                            vs.sid,
                            vs.serial#,
                            vs.username,
                            vs.machine,
                            vs.program,
                            vs.last_call_et / 60 AS idle_minutes
                        FROM v$session vs
                        WHERE vs.status = 'INACTIVE'
                        AND vs.type != 'BACKGROUND'
                        AND vs.username IS NOT NULL
                        ORDER BY vs.last_call_et DESC
                    )
                    WHERE ROWNUM <= 20
                """)

                idle_conns = []
                for row in result.rows:
                    idle_conns.append({
                        "sid": row[0],
                        "serial": row[1],
                        "user": row[2],
                        "machine": row[3],
                        "program": row[4],
                        "idle_minutes": round(float(str(row[5])) if row[5] else 0, 1)
                    })
                data["idle_connections"] = idle_conns

            return create_success_response(
                message="连接分析完成",
                data=data
            )
        except Exception as e:
            return create_error_response(str(e), ErrorCode.UNKNOWN_ERROR)


    def _analyze_postgresql_connections(self, show_idle: bool) -> Dict[str, Any]:
        """PostgreSQL连接分析"""
        try:
            max_conn = 100
            try:
                result = self.connector.execute(
                    "SELECT setting::int FROM pg_settings WHERE name = 'max_connections'"
                )
                if result.rows:
                    max_conn = int(str(result.rows[0][0])) if result.rows[0][0] else 100
            except Exception:
                pass

            result = self.connector.execute("""
                SELECT
                    COUNT(*) AS total,
                    COUNT(*) FILTER (WHERE state = 'active') AS active,
                    COUNT(*) FILTER (WHERE state = 'idle') AS idle,
                    COUNT(*) FILTER (WHERE state = 'idle in transaction') AS idle_in_trx
                FROM pg_stat_activity
                WHERE backend_type = 'client backend'
            """)

            row = result.rows[0] if result.rows else (0, 0, 0, 0)
            current = int(str(row[0])) if row[0] else 0
            active = int(str(row[1])) if row[1] else 0
            idle = int(str(row[2])) if row[2] else 0
            idle_in_trx = int(str(row[3])) if row[3] else 0
            usage_pct = (current / max_conn * 100) if max_conn > 0 else 0

            data = {
                "statistics": {
                    "max_connections": max_conn,
                    "current": current,
                    "active": active,
                    "idle": idle,
                    "idle_in_transaction": idle_in_trx,
                    "usage_percent": round(usage_pct, 1)
                }
            }

            if show_idle:
                result = self.connector.execute("""
                    SELECT
                        pid,
                        usename,
                        application_name,
                        client_addr,
                        EXTRACT(EPOCH FROM (now() - state_change))::numeric(10,2) / 60 AS idle_minutes,
                        state,
                        LEFT(query, 200) AS last_query
                    FROM pg_stat_activity
                    WHERE state IN ('idle', 'idle in transaction')
                    AND backend_type = 'client backend'
                    ORDER BY state_change ASC
                    LIMIT 20
                """)
                idle_conns = []
                for row in result.rows:
                    idle_conns.append({
                        "pid": row[0],
                        "user": str(row[1]) if row[1] else "",
                        "application": str(row[2]) if row[2] else "",
                        "client_addr": str(row[3]) if row[3] else "",
                        "idle_minutes": round(float(str(row[4])) if row[4] else 0, 1),
                        "state": str(row[5]) if row[5] else "",
                        "last_query": str(row[6]) if row[6] else ""
                    })
                data["idle_connections"] = idle_conns

            return create_success_response(
                message="连接分析完成",
                data=data
            )
        except Exception as e:
            return create_error_response(str(e), ErrorCode.UNKNOWN_ERROR)


    def _analyze_clickhouse_connections(self, show_idle: bool) -> Dict[str, Any]:
        """
        ClickHouse连接分析

        分析维度:
        1. 当前连接数
        2. 最大连接数限制
        3. 连接来源统计
        4. 长时间连接

        参数:
            show_idle: 是否显示空闲连接

        返回:
            Dict: 连接分析结果
        """
        try:
            # 获取当前连接
            result = self.connector.execute("""
                SELECT
                    COUNT(*) as current_conn,
                    COUNT(DISTINCT user) as user_count,
                    COUNT(DISTINCT client_address) as client_count
                FROM system.processes
            """)

            current_conn = 0
            user_count = 0
            client_count = 0
            if result.rows:
                current_conn = int(result.rows[0][0]) if result.rows[0][0] else 0
                user_count = int(result.rows[0][1]) if result.rows[0][1] else 0
                client_count = int(result.rows[0][2]) if result.rows[0][2] else 0

            # 获取最大连接数
            max_conn = 100
            try:
                result = self.connector.execute(
                    "SELECT value FROM system.settings WHERE name = 'max_concurrent_queries'"
                )
                if result.rows:
                    max_conn = int(result.rows[0][0]) if result.rows[0][0] else 100
            except Exception:
                pass

            usage_pct = round(current_conn / max_conn * 100, 1) if max_conn > 0 else 0

            data = {
                "summary": {
                    "max_connections": max_conn,
                    "current_connections": current_conn,
                    "usage_percent": usage_pct,
                    "available": max_conn - current_conn,
                    "user_count": user_count,
                    "client_count": client_count
                },
                "active_connections": [],
                "idle_connections": [],
                "user_distribution": [],
                "client_distribution": []
            }

            # 获取用户分布统计
            try:
                result = self.connector.execute("""
                    SELECT
                        user,
                        COUNT(*) as conn_count,
                        ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER(), 1) as pct
                    FROM system.processes
                    GROUP BY user
                    ORDER BY conn_count DESC
                    LIMIT 10
                """)
                for row in result.rows if result else []:
                    data["user_distribution"].append({
                        "user": str(row[0]) if row[0] else "",
                        "connections": int(row[1]) if row[1] else 0,
                        "percentage": float(row[2]) if row[2] else 0.0
                    })
            except Exception as e:
                logger.warning(f"获取ClickHouse用户分布失败: {e}")

            # 获取客户端地址分布统计
            try:
                result = self.connector.execute("""
                    SELECT
                        client_address,
                        COUNT(*) as conn_count,
                        ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER(), 1) as pct
                    FROM system.processes
                    WHERE client_address != ''
                    GROUP BY client_address
                    ORDER BY conn_count DESC
                    LIMIT 10
                """)
                for row in result.rows if result else []:
                    data["client_distribution"].append({
                        "client_address": str(row[0]) if row[0] else "",
                        "connections": int(row[1]) if row[1] else 0,
                        "percentage": float(row[2]) if row[2] else 0.0
                    })
            except Exception as e:
                logger.warning(f"获取ClickHouse客户端分布失败: {e}")

            # 获取活跃连接详情
            try:
                result = self.connector.execute("""
                    SELECT
                        query_id,
                        user,
                        client_address,
                        elapsed,
                        query
                    FROM system.processes
                    ORDER BY elapsed DESC
                    LIMIT 20
                """)
                for row in result.rows if result else []:
                    data["active_connections"].append({
                        "query_id": str(row[0]) if row[0] else "",
                        "user": str(row[1]) if row[1] else "",
                        "client": str(row[2]) if row[2] else "",
                        "elapsed_seconds": round(float(row[3]) if row[3] else 0, 2),
                        "query_preview": str(row[4])[:100] if row[4] else ""
                    })
            except Exception as e:
                logger.warning(f"获取ClickHouse活跃连接失败: {e}")

            # 获取长时间运行的查询（作为idle_connections）
            if show_idle:
                try:
                    result = self.connector.execute("""
                        SELECT
                            query_id,
                            user,
                            client_address,
                            elapsed,
                            query
                        FROM system.processes
                        WHERE elapsed > 300
                        ORDER BY elapsed DESC
                        LIMIT 20
                    """)
                    for row in result.rows if result else []:
                        data["idle_connections"].append({
                            "query_id": str(row[0]) if row[0] else "",
                            "user": str(row[1]) if row[1] else "",
                            "client": str(row[2]) if row[2] else "",
                            "elapsed_seconds": round(float(row[3]) if row[3] else 0, 2),
                            "query_preview": str(row[4])[:100] if row[4] else ""
                        })
                except Exception as e:
                    logger.warning(f"获取ClickHouse长时间查询失败: {e}")

            suggestions = []
            if usage_pct > 80:
                suggestions.append({
                    "type": "high_usage",
                    "priority": "high",
                    "message": f"连接使用率 {usage_pct}% 过高，建议增加max_concurrent_queries或优化查询"
                })

            # 检测单一用户连接过多
            if data["user_distribution"]:
                top_user = data["user_distribution"][0]
                if top_user["percentage"] > 80:
                    suggestions.append({
                        "type": "user_imbalance",
                        "priority": "medium",
                        "message": f"用户 {top_user['user']} 占用 {top_user['percentage']}% 连接，建议检查是否有连接泄露"
                    })

            data["suggestions"] = suggestions

            return create_success_response(
                message="ClickHouse连接分析完成",
                data=data
            )
        except Exception as e:
            return create_error_response(str(e), ErrorCode.UNKNOWN_ERROR)


    def _analyze_sqlite_connections(self, show_idle: bool) -> Dict[str, Any]:
        """
        SQLite连接分析

        SQLite是单连接数据库（通常），分析维度:
        1. 当前连接信息（有限）
        2. 事务状态
        3. 锁定状态

        参数:
            show_idle: 是否显示空闲连接（SQLite不适用）

        返回:
            Dict: 连接分析结果
        """
        try:
            data = {
                "summary": {
                    "max_connections": 1,
                    "current_connections": 1,
                    "usage_percent": 100.0,
                    "available": 0,
                    "user_count": 1,
                    "client_count": 1
                },
                "active_connections": [],
                "idle_connections": []
            }

            # 获取事务状态
            try:
                result = self.connector.execute("PRAGMA lock_status")
                for row in result.rows if result else []:
                    data["active_connections"].append({
                        "database": str(row[0]) if row[0] else "main",
                        "lock_type": str(row[1]) if len(row) > 1 else "unknown"
                    })
            except Exception as e:
                logger.warning(f"获取SQLite锁状态失败: {e}")

            # 获取编译选项
            try:
                result = self.connector.execute("PRAGMA compile_options")
                compile_options = []
                for row in result.rows if result else []:
                    compile_options.append(str(row[0]) if row[0] else "")
                data["compile_options"] = compile_options
            except Exception:
                pass

            suggestions = []
            if "THREADSAFE=0" in str(data.get("compile_options", [])):
                suggestions.append({
                    "type": "threadsafe",
                    "priority": "medium",
                    "message": "SQLite编译为单线程模式(THREADSAFE=0)，不支持多连接并发"
                })

            data["suggestions"] = suggestions

            return create_success_response(
                message="SQLite连接分析完成（SQLite为单连接数据库）",
                data=data
            )
        except Exception as e:
            return create_error_response(str(e), ErrorCode.UNKNOWN_ERROR)


    def analyze_replication(self) -> Dict[str, Any]:
        """
        复制诊断

        返回:
            Dict: 复制状态
        """
        try:
            if 'mysql' in self.dialect:
                return self._analyze_mysql_replication()
            elif 'oracle' in self.dialect:
                return self._analyze_oracle_replication()
            elif 'postgresql' in self.dialect:
                return self._analyze_postgresql_replication()
            elif 'clickhouse' in self.dialect:
                return self._analyze_clickhouse_replication()
            elif 'sqlite' in self.dialect:
                return self._analyze_sqlite_replication()
            else:
                return create_error_response(
                    f"复制分析暂不支持 {self.dialect}",
                    ErrorCode.UNSUPPORTED_SQL
                )
        except Exception as e:
            logger.error(f"复制分析失败: {e}")
            return create_error_response(str(e), ErrorCode.UNKNOWN_ERROR)


    def _analyze_mysql_replication(self) -> Dict[str, Any]:
        """MySQL复制分析"""
        try:
            data = {"status": {}}

            result = self.connector.execute("SHOW MASTER STATUS")
            is_master = len(result.rows) > 0
            data["status"]["is_master"] = is_master

            if is_master:
                data["status"]["binlog_enabled"] = True
                data["status"]["slave_count"] = 0

            try:
                result = self.connector.execute("SHOW SLAVE STATUS")
                is_slave = len(result.rows) > 0
                data["status"]["is_slave"] = is_slave

                if is_slave and result.rows:
                    row = result.rows[0]
                    data["slave_status"] = {
                        "io_running": row[10] if len(row) > 10 else "No",
                        "sql_running": row[11] if len(row) > 11 else "No",
                        "delay_seconds": row[32] if len(row) > 32 else 0
                    }
            except Exception:
                data["status"]["is_slave"] = False

            return create_success_response(
                message="复制分析完成",
                data=data
            )
        except Exception as e:
            return create_error_response(str(e), ErrorCode.UNKNOWN_ERROR)


    def _analyze_oracle_replication(self) -> Dict[str, Any]:
        """Oracle Data Guard复制分析"""
        try:
            data = {"status": {}}

            try:
                result = self.connector.execute("""
                    SELECT COUNT(*) FROM v$dataguard_config
                """)
                has_dataguard = result.rows and result.rows[0][0] > 0
            except Exception:
                has_dataguard = False

            data["status"]["dataguard_enabled"] = has_dataguard

            if has_dataguard:
                try:
                    result = self.connector.execute("""
                        SELECT
                            name,
                            database_role,
                            open_mode,
                            protection_mode,
                            switchover_status
                        FROM v$database
                    """)
                    if result.rows:
                        row = result.rows[0]
                        data["status"]["database_role"] = str(row[1] or "UNKNOWN")
                        data["status"]["open_mode"] = str(row[2] or "UNKNOWN")
                        data["status"]["protection_mode"] = str(row[3] or "UNKNOWN")
                        data["status"]["switchover_status"] = str(row[4] or "UNKNOWN")
                except Exception as e:
                    logger.warning(f"查询v$database失败: {e}")

                try:
                    result = self.connector.execute("""
                        SELECT
                            dest_name,
                            status,
                            recovery_mode,
                            gap_status,
                            transmit_mode
                        FROM v$archive_dest_status
                        WHERE status != 'INACTIVE'
                        AND dest_name IS NOT NULL
                    """)
                    destinations = []
                    for row in result.rows:
                        destinations.append({
                            "dest_name": str(row[0] or ""),
                            "status": str(row[1] or ""),
                            "recovery_mode": str(row[2] or ""),
                            "gap_status": str(row[3] or ""),
                            "transmit_mode": str(row[4] or "")
                        })
                    data["archive_destinations"] = destinations
                except Exception as e:
                    logger.warning(f"查询v$archive_dest_status失败: {e}")

                try:
                    result = self.connector.execute("""
                        SELECT
                            name,
                            value,
                            unit,
                            time_computed
                        FROM v$dataguard_stats
                        WHERE name IN ('transport lag', 'apply lag', 'apply finish time')
                    """)
                    stats = {}
                    for row in result.rows:
                        stats[str(row[0])] = {
                            "value": str(row[1] or ""),
                            "unit": str(row[2] or ""),
                            "time": str(row[3] or "")
                        }
                    data["dataguard_stats"] = stats

                    apply_lag = stats.get("apply lag", {}).get("value", "0")
                    transport_lag = stats.get("transport lag", {}).get("value", "0")
                    try:
                        apply_lag_sec = float(str(apply_lag).split()[0]) if apply_lag else 0
                        transport_lag_sec = float(str(transport_lag).split()[0]) if transport_lag else 0
                    except (ValueError, IndexError):
                        apply_lag_sec = 0
                        transport_lag_sec = 0

                    if apply_lag_sec > 300:
                        data["warning"] = f"应用延迟过高: {apply_lag_sec}秒"
                    elif transport_lag_sec > 60:
                        data["warning"] = f"传输延迟过高: {transport_lag_sec}秒"
                except Exception as e:
                    logger.warning(f"查询v$dataguard_stats失败: {e}")
            else:
                data["status"]["database_role"] = "PRIMARY"
                data["message"] = "未配置Data Guard"

            return create_success_response(
                message="Oracle复制分析完成",
                data=data
            )
        except Exception as e:
            return create_error_response(str(e), ErrorCode.UNKNOWN_ERROR)

    # ==================== PostgreSQL诊断方法 ====================


    def _analyze_postgresql_replication(self) -> Dict[str, Any]:
        """PostgreSQL复制分析(流复制/逻辑复制)"""
        try:
            data = {"status": {}}

            is_primary = False
            try:
                result = self.connector.execute("""
                    SELECT pg_is_in_recovery()
                """)
                is_primary = not (result.rows and result.rows[0][0])
            except Exception:
                pass

            data["status"]["is_primary"] = is_primary

            if is_primary:
                data["status"]["database_role"] = "PRIMARY"
                try:
                    result = self.connector.execute("""
                        SELECT
                            client_addr,
                            state,
                            sent_lsn,
                            replay_lsn,
                            replay_lag
                        FROM pg_stat_replication
                    """)
                    replicas = []
                    for row in result.rows:
                        lag = str(row[4]) if row[4] else "0"
                        replicas.append({
                            "client_addr": str(row[0]) if row[0] else "",
                            "state": str(row[1]) if row[1] else "",
                            "sent_lsn": str(row[2]) if row[2] else "",
                            "replay_lsn": str(row[3]) if row[3] else "",
                            "replay_lag": lag
                        })
                    data["replicas"] = replicas
                    data["status"]["replica_count"] = len(replicas)
                except Exception as e:
                    logger.warning(f"查询pg_stat_replication失败: {e}")
                    data["status"]["replica_count"] = 0
            else:
                data["status"]["database_role"] = "STANDBY"
                try:
                    result = self.connector.execute("""
                        SELECT
                            status,
                            sender_host,
                            sender_port,
                            received_lsn,
                            latest_end_lsn
                        FROM pg_stat_wal_receiver
                    """)
                    if result.rows:
                        row = result.rows[0]
                        data["receiver_status"] = {
                            "status": str(row[0]) if row[0] else "",
                            "sender_host": str(row[1]) if row[1] else "",
                            "sender_port": int(str(row[2])) if row[2] else 0,
                            "received_lsn": str(row[3]) if row[3] else "",
                            "latest_end_lsn": str(row[4]) if row[4] else ""
                        }
                except Exception as e:
                    logger.warning(f"查询pg_stat_wal_receiver失败: {e}")

            return create_success_response(
                message="PostgreSQL复制分析完成",
                data=data
            )
        except Exception as e:
            return create_error_response(str(e), ErrorCode.UNKNOWN_ERROR)


    def _analyze_clickhouse_replication(self) -> Dict[str, Any]:
        """
        ClickHouse复制分析

        ClickHouse支持两种复制:
        1. ReplicatedMergeTree表引擎（基于ZooKeeper/Keeper）
        2. 分布式表（Distributed）

        分析维度:
        1. 复制表状态
        2. ZooKeeper/Keeper连接状态
        3. 复制队列积压
        4. 分布式表状态

        返回:
            Dict: 复制分析结果
        """
        try:
            data = {"status": {}}

            # 检查是否有复制表
            replicated_tables = []
            try:
                result = self.connector.execute("""
                    SELECT
                        database,
                        table,
                        engine
                    FROM system.tables
                    WHERE engine LIKE 'Replicated%'
                """)
                for row in result.rows if result else []:
                    replicated_tables.append({
                        "database": str(row[0]) if row[0] else "",
                        "table": str(row[1]) if row[1] else "",
                        "engine": str(row[2]) if row[2] else ""
                    })
            except Exception as e:
                logger.warning(f"获取ClickHouse复制表失败: {e}")

            data["status"]["replicated_tables_count"] = len(replicated_tables)
            data["status"]["has_replication"] = len(replicated_tables) > 0
            data["replicated_tables"] = replicated_tables

            # 获取复制队列信息
            replication_queue = []
            try:
                result = self.connector.execute("""
                    SELECT
                        database,
                        table,
                        type,
                        source_replica,
                        parts_to_merge,
                        new_part_name,
                        create_time,
                        last_attempt_time,
                        num_tries,
                        last_exception
                    FROM system.replication_queue
                    ORDER BY create_time DESC
                    LIMIT 50
                """)
                for row in result.rows if result else []:
                    replication_queue.append({
                        "database": str(row[0]) if row[0] else "",
                        "table": str(row[1]) if row[1] else "",
                        "type": str(row[2]) if row[2] else "",
                        "source_replica": str(row[3]) if row[3] else "",
                        "parts_to_merge": int(row[4]) if row[4] else 0,
                        "new_part_name": str(row[5]) if row[5] else "",
                        "create_time": str(row[6]) if row[6] else "",
                        "last_attempt_time": str(row[7]) if row[7] else "",
                        "num_tries": int(row[8]) if row[8] else 0,
                        "last_exception": str(row[9])[:200] if row[9] else ""
                    })
            except Exception as e:
                logger.warning(f"获取ClickHouse复制队列失败: {e}")

            data["replication_queue"] = replication_queue
            data["status"]["queue_length"] = len(replication_queue)

            # 获取ZooKeeper/Keeper状态
            zk_status = {}
            try:
                result = self.connector.execute("""
                    SELECT
                        name,
                        value
                    FROM system.zookeeper
                    WHERE path = '/clickhouse'
                    LIMIT 1
                """)
                zk_status["connected"] = True
            except Exception:
                zk_status["connected"] = False

            data["zookeeper_status"] = zk_status

            # 获取分布式表信息
            distributed_tables = []
            try:
                result = self.connector.execute("""
                    SELECT
                        database,
                        table,
                        engine,
                        create_table_query
                    FROM system.tables
                    WHERE engine = 'Distributed'
                """)
                for row in result.rows if result else []:
                    distributed_tables.append({
                        "database": str(row[0]) if row[0] else "",
                        "table": str(row[1]) if row[1] else "",
                        "engine": str(row[2]) if row[2] else ""
                    })
            except Exception as e:
                logger.warning(f"获取ClickHouse分布式表失败: {e}")

            data["distributed_tables"] = distributed_tables
            data["status"]["distributed_tables_count"] = len(distributed_tables)

            suggestions = []
            if len(replication_queue) > 100:
                suggestions.append({
                    "type": "replication_lag",
                    "priority": "high",
                    "message": f"复制队列积压严重({len(replication_queue)}个任务)，请检查ZooKeeper/Keeper连接和副本状态"
                })

            if not zk_status.get("connected") and len(replicated_tables) > 0:
                suggestions.append({
                    "type": "zookeeper_disconnected",
                    "priority": "critical",
                    "message": "ZooKeeper/Keeper连接异常，复制功能可能受影响"
                })

            data["suggestions"] = suggestions

            return create_success_response(
                message=f"ClickHouse复制分析完成，发现{len(replicated_tables)}个复制表",
                data=data
            )
        except Exception as e:
            return create_error_response(str(e), ErrorCode.UNKNOWN_ERROR)


    def _analyze_sqlite_replication(self) -> Dict[str, Any]:
        """
        SQLite复制分析

        SQLite本身不支持原生复制，但可以通过以下方式实现:
        1. SQLite Replication (第三方扩展)
        2. WAL模式下的读取副本
        3. 文件级复制

        返回:
            Dict: 复制分析结果（SQLite原生不支持复制）
        """
        try:
            data = {
                "status": {
                    "has_replication": False,
                    "database_role": "STANDALONE",
                    "note": "SQLite原生不支持复制功能"
                },
                "replication_methods": [
                    {
                        "method": "WAL模式",
                        "description": "开启WAL模式后支持一个写入者和多个读取者",
                        "supported": True
                    },
                    {
                        "method": "文件复制",
                        "description": "通过文件系统级复制实现备份",
                        "supported": True
                    },
                    {
                        "method": "第三方扩展",
                        "description": "如SQLite-Rsync、Litestream等",
                        "supported": False
                    }
                ]
            }

            # 检查WAL模式
            try:
                result = self.connector.execute("PRAGMA journal_mode")
                if result.rows:
                    journal_mode = str(result.rows[0][0]).upper() if result.rows[0][0] else "DELETE"
                    data["status"]["journal_mode"] = journal_mode
                    data["status"]["wal_enabled"] = journal_mode == "WAL"
            except Exception as e:
                logger.warning(f"获取SQLite日志模式失败: {e}")

            suggestions = []
            if not data["status"].get("wal_enabled", False):
                suggestions.append({
                    "type": "wal_mode",
                    "priority": "low",
                    "message": "建议开启WAL模式(PRAGMA journal_mode=WAL)以支持并发读取"
                })

            data["suggestions"] = suggestions

            return create_success_response(
                message="SQLite复制分析完成（SQLite原生不支持复制）",
                data=data
            )
        except Exception as e:
            return create_error_response(str(e), ErrorCode.UNKNOWN_ERROR)



