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

    提供Oracle特有的慢查询分析、性能分析、统计信息获取
    """

    def __init__(self, connector: UnifiedConnector):
        super().__init__(connector)

    def analyze_slow_queries(
        self,
        limit: int = 20,
        min_time: float = 1.0
    ) -> Dict[str, Any]:
        """
        分析Oracle慢SQL（从AWR/ASH获取）

        参数:
            limit: 返回条数限制
            min_time: 最小执行时间（秒）

        返回:
            Dict: 慢查询分析结果
        """
        try:
            # 从AWR获取慢SQL
            result = self._execute_query("""
                SELECT
                    sql_id,
                    sql_text,
                    executions,
                    elapsed_time / 1000000 as elapsed_time_sec,
                    cpu_time / 1000000 as cpu_time_sec,
                    buffer_gets,
                    disk_reads,
                    rows_processed
                FROM (
                    SELECT
                        sql_id,
                        sql_text,
                        executions,
                        elapsed_time,
                        cpu_time,
                        buffer_gets,
                        disk_reads,
                        rows_processed,
                        ROW_NUMBER() OVER (ORDER BY elapsed_time DESC) as rn
                    FROM v$sql
                    WHERE elapsed_time / 1000000 >= {min_time}
                    AND executions > 0
                )
                WHERE rn <= {limit}
            """)

            if not result:
                return self._create_result(
                    success=True,
                    message="未找到慢SQL",
                    data={
                        "total_queries": 0,
                        "queries": []
                    }
                )

            queries = []
            for row in result:
                queries.append({
                    "sql_id": row[0],
                    "sql_text": row[1][:500] if row[1] else None,
                    "executions": row[2],
                    "elapsed_time_sec": round(row[3], 2),
                    "cpu_time_sec": round(row[4], 2),
                    "buffer_gets": row[5],
                    "disk_reads": row[6],
                    "rows_processed": row[7],
                    "avg_time_sec": round(row[3] / row[2], 2) if row[2] > 0 else 0
                })

            return self._create_result(
                success=True,
                message=f"成功分析 {len(queries)} 个慢SQL",
                data={
                    "total_queries": len(queries),
                    "queries": queries
                }
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
                SELECT
                    event,
                    total_waits,
                    ROUND(total_timeouts / 100, 2) as total_timeouts,
                    ROUND(time_waited / 100, 2) as time_waited_sec
                FROM v$system_event
                WHERE wait_class != 'Idle'
                ORDER BY time_waited DESC
                FETCH FIRST 10 ROWS ONLY
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
