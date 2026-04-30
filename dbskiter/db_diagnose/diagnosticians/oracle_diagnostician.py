"""
Oracle诊断器

提供Oracle数据库的专项诊断能力
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from dbskiter.shared.unified_connector import UnifiedConnector
from .base import BaseDiagnostician

logger = logging.getLogger(__name__)


class OracleDiagnostician(BaseDiagnostician):
    """
    Oracle数据库诊断器

    提供Oracle特有的诊断能力：
    - 慢查询分析（AWR/v$sql）
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
        min_time: float = 1.0,
        use_awr: bool = True
    ) -> Dict[str, Any]:
        """
        分析Oracle慢SQL（增强版）

        支持两种模式：
        1. AWR历史数据分析（默认）
        2. 实时v$sql分析

        参数:
            limit: 返回条数限制
            min_time: 最小执行时间（秒）
            use_awr: 是否使用AWR历史数据

        返回:
            Dict: 慢查询分析结果，包含：
                - summary: 汇总统计
                - top_patterns: TOP查询模式
                - recommendations: 优化建议
        """
        try:
            from .oracle_slow_query_analyzer import OracleSlowQueryAnalyzer

            analyzer = OracleSlowQueryAnalyzer(self.connector)

            if use_awr:
                # 优先使用AWR历史数据
                report = analyzer.analyze_awr_history(
                    hours=24,
                    limit=limit,
                    min_time=min_time
                )
            else:
                # 使用实时数据
                report = analyzer.analyze_realtime(
                    limit=limit,
                    min_time=min_time
                )

            # 转换为标准响应格式
            return self._create_result(
                success=True,
                message=f"成功分析 {report.total_queries} 个慢SQL，"
                       f"发现 {report.unique_patterns} 个查询模式",
                data=report.to_dict()
            )

        except Exception as e:
            logger.error(f"慢SQL分析失败: {e}")
            return self._create_result(
                success=False,
                message="慢SQL分析失败",
                error=str(e)
            )

    def analyze_performance_metrics(
        self,
        duration_minutes: int = 10
    ) -> Dict[str, Any]:
        """
        分析Oracle性能指标

        参数:
            duration_minutes: 采集时长（分钟）

        返回:
            Dict: 性能分析结果
        """
        try:
            metrics = {}

            # 获取数据库时间模型统计
            result = self._execute_query("""
                SELECT
                    stat_name,
                    ROUND(value / 1000000, 2) as value_sec
                FROM v$sys_time_model
                WHERE stat_name IN (
                    'DB time',
                    'DB CPU',
                    'sql execute elapsed time',
                    'parse time elapsed'
                )
            """)

            if result:
                for row in result:
                    metrics[row[0].lower().replace(' ', '_')] = row[1]

            # 获取等待事件统计
            result = self._execute_query("""
                SELECT * FROM (
                    SELECT
                        event,
                        total_waits,
                        ROUND(total_timeouts / 100, 2) as total_timeouts,
                        ROUND(time_waited / 100, 2) as time_waited_sec
                    FROM v$system_event
                    WHERE wait_class != 'Idle'
                    ORDER BY time_waited DESC
                ) WHERE ROWNUM <= 10
            """)

            if result:
                metrics["top_wait_events"] = [
                    {
                        "event": row[0],
                        "total_waits": row[1],
                        "total_timeouts": row[2],
                        "time_waited_sec": row[3]
                    }
                    for row in result
                ]

            # 获取当前活动会话数
            result = self._execute_query("""
                SELECT COUNT(*) FROM v$session WHERE status = 'ACTIVE' AND type = 'USER'
            """)
            if result:
                metrics["active_sessions"] = result[0][0]

            # 获取系统统计信息
            result = self._execute_query("""
                SELECT
                    (SELECT value FROM v$sysstat WHERE name = 'user commits'),
                    (SELECT value FROM v$sysstat WHERE name = 'user rollbacks'),
                    (SELECT value FROM v$sysstat WHERE name = 'physical reads'),
                    (SELECT value FROM v$sysstat WHERE name = 'physical writes'),
                    (SELECT value FROM v$sysstat WHERE name = 'parse count (total)'),
                    (SELECT value FROM v$sysstat WHERE name = 'parse count (hard)')
                FROM dual
            """)

            if result:
                metrics["user_commits"] = result[0][0]
                metrics["user_rollbacks"] = result[0][1]
                metrics["physical_reads"] = result[0][2]
                metrics["physical_writes"] = result[0][3]
                metrics["parse_count_total"] = result[0][4]
                metrics["parse_count_hard"] = result[0][5]

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
        获取Oracle数据库统计信息

        返回:
            Dict: 数据库统计信息
        """
        try:
            stats = {
                "database_type": "Oracle",
                "timestamp": datetime.now().isoformat()
            }

            # 获取版本
            result = self._execute_query("SELECT * FROM v$version WHERE rownum = 1")
            if result:
                stats["version"] = result[0][0]

            # 获取实例名
            result = self._execute_query("SELECT instance_name FROM v$instance")
            if result:
                stats["instance_name"] = result[0][0]

            # 获取数据库名
            result = self._execute_query("SELECT name FROM v$database")
            if result:
                stats["database_name"] = result[0][0]

            # 获取当前会话数
            result = self._execute_query("SELECT COUNT(*) FROM v$session")
            if result:
                stats["current_sessions"] = result[0][0]

            # 获取最大会话数
            result = self._execute_query("SELECT value FROM v$parameter WHERE name = 'sessions'")
            if result:
                stats["max_sessions"] = int(result[0][0])

            # 获取数据库大小
            result = self._execute_query("""
                SELECT ROUND(SUM(bytes) / 1024 / 1024 / 1024, 2)
                FROM dba_data_files
            """)
            if result:
                stats["total_size_gb"] = result[0][0] or 0

            # 获取表数量
            result = self._execute_query("""
                SELECT COUNT(*) FROM dba_tables WHERE owner NOT IN ('SYS', 'SYSTEM', 'OUTLN', 'DBSNMP')
            """)
            if result:
                stats["table_count"] = result[0][0]

            # 获取SGA信息
            result = self._execute_query("""
                SELECT
                    ROUND(SUM(bytes) / 1024 / 1024 / 1024, 2)
                FROM v$sgainfo
                WHERE name IN ('Fixed SGA Size', 'Redo Buffers', 'Buffer Cache Size', 'Shared Pool Size', 'Large Pool Size', 'Java Pool Size')
            """)
            if result:
                stats["sga_size_gb"] = result[0][0]

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
                    COUNT(*) AS total,
                    SUM(CASE WHEN status = 'ACTIVE' THEN 1 ELSE 0 END) AS active,
                    SUM(CASE WHEN last_call_et > 5 AND status = 'ACTIVE' THEN 1 ELSE 0 END) AS slow
                FROM v$session
                WHERE type != 'BACKGROUND'
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
            result = self._execute_query("""
                SELECT * FROM (
                    SELECT
                        sql_id,
                        SUBSTR(sql_text, 1, 500) AS sql_text,
                        executions,
                        ROUND(elapsed_time / 1000000, 2) AS total_elapsed_sec,
                        ROUND(cpu_time / 1000000, 2) AS total_cpu_sec,
                        CASE
                            WHEN executions > 0
                            THEN ROUND(elapsed_time / executions / 1000000, 2)
                            ELSE ROUND(elapsed_time / 1000000, 2)
                        END AS avg_elapsed,
                        CASE
                            WHEN executions > 0
                            THEN ROUND(cpu_time / executions / 1000000, 2)
                            ELSE ROUND(cpu_time / 1000000, 2)
                        END AS avg_cpu,
                        buffer_gets,
                        disk_reads
                    FROM v$sql
                    WHERE executions > 0
                    AND elapsed_time / executions / 1000000 >= %s
                    AND sql_text NOT LIKE '%%v$%%'
                    AND sql_text NOT LIKE '%%dba_%%'
                    ORDER BY avg_elapsed DESC
                )
                WHERE ROWNUM <= %s
            """, (threshold, limit))

            queries = []
            for row in result:
                queries.append({
                    "sql_id": row[0],
                    "sql": row[1] if row[1] else "",
                    "executions": int(row[2]) if row[2] else 0,
                    "exec_time": float(row[6]) if row[6] else 0,
                    "total_time": float(row[3]) if row[3] else 0,
                    "cpu_time": float(row[7]) if row[7] else 0,
                    "buffer_gets": int(row[8]) if row[8] else 0,
                    "disk_reads": int(row[9]) if row[9] else 0
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
                    w.sid AS waiting_sid,
                    w.type AS lock_type,
                    w.ctime AS wait_seconds,
                    h.sid AS holding_sid,
                    SUBSTR(s_w.username, 1, 20) AS waiting_user,
                    SUBSTR(s_h.username, 1, 20) AS holding_user
                FROM v$lock w
                JOIN v$lock h ON w.id1 = h.id1 AND w.id2 = h.id2 AND h.sid != w.sid
                JOIN v$session s_w ON w.sid = s_w.sid
                JOIN v$session s_h ON h.sid = s_h.sid
                WHERE w.request > 0
                AND h.lmode > 0
                AND w.ctime > 1
                ORDER BY w.ctime DESC
            """)

            lock_waits = []
            for row in result:
                lock_waits.append({
                    "waiting_sid": int(row[0]) if row[0] else 0,
                    "lock_type": str(row[1]) if row[1] else "",
                    "wait_seconds": int(row[2]) if row[2] else 0,
                    "holding_sid": int(row[3]) if row[3] else 0,
                    "waiting_user": str(row[4]) if row[4] else "",
                    "holding_user": str(row[5]) if row[5] else ""
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
