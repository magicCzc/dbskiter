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

    def analyze_index_usage(self) -> Dict[str, Any]:
        """
        分析Oracle索引使用情况

        识别未使用或低效的索引，以及可能缺少索引的表。
        提供详细的索引分析、健康评分和具体的优化建议。

        返回:
            Dict: 索引使用分析结果，包含：
                - unused_indexes: 未使用的索引列表
                - hot_indexes: 高频使用索引列表
                - invalid_indexes: 无效索引列表
                - health_score: 健康评分(0-100)
                - suggestions: 优化建议
                - actionable_commands: 可执行的SQL命令
        """
        try:
            # 获取未使用的索引
            unused_indexes = []
            total_unused_size = 0

            result = self._execute_query("""
                SELECT * FROM (
                    SELECT
                        o.owner,
                        o.table_name,
                        o.index_name,
                        s.tablespace_name,
                        ROUND(SUM(s.bytes) / 1024 / 1024, 2) as size_mb
                    FROM dba_objects o
                    JOIN dba_segments s ON o.owner = s.owner AND o.index_name = s.segment_name
                    LEFT JOIN v$object_usage u ON o.index_name = u.index_name AND o.owner = u.owner
                    WHERE o.object_type = 'INDEX'
                    AND o.owner NOT IN ('SYS', 'SYSTEM', 'OUTLN', 'DBSNMP')
                    AND (u.used = 'NO' OR u.used IS NULL)
                    GROUP BY o.owner, o.table_name, o.index_name, s.tablespace_name
                    ORDER BY size_mb DESC
                ) WHERE ROWNUM <= 30
            """)

            for row in result or []:
                size_mb = row[4] or 0
                total_unused_size += size_mb

                unused_indexes.append({
                    "schema": row[0],
                    "table": row[1],
                    "index": row[2],
                    "tablespace": row[3],
                    "size_mb": size_mb,
                    "priority": "high" if size_mb > 10 else "medium"
                })

            # 获取高频使用索引
            hot_indexes = []
            result = self._execute_query("""
                SELECT * FROM (
                    SELECT
                        object_owner,
                        object_name,
                        object_name as index_name,
                        COUNT(*) as usage_count
                    FROM v$sql_plan
                    WHERE object_type = 'INDEX'
                    AND object_owner NOT IN ('SYS', 'SYSTEM')
                    GROUP BY object_owner, object_name
                    ORDER BY usage_count DESC
                ) WHERE ROWNUM <= 20
            """)

            for row in result or []:
                hot_indexes.append({
                    "schema": row[0],
                    "table": row[1],
                    "index": row[2],
                    "usage_count": row[3]
                })

            # 获取无效索引
            invalid_indexes = []
            result = self._execute_query("""
                SELECT * FROM (
                    SELECT
                        owner,
                        table_name,
                        index_name,
                        status
                    FROM dba_indexes
                    WHERE status != 'VALID'
                    AND owner NOT IN ('SYS', 'SYSTEM', 'OUTLN', 'DBSNMP')
                    ORDER BY owner, table_name
                ) WHERE ROWNUM <= 20
            """)

            for row in result or []:
                invalid_indexes.append({
                    "schema": row[0],
                    "table": row[1],
                    "index": row[2],
                    "status": row[3]
                })

            # 计算健康评分
            health_score = self._calculate_oracle_index_health_score(
                unused_indexes, invalid_indexes
            )

            # 生成建议和可执行命令
            suggestions = []
            actionable_commands = []

            if unused_indexes:
                high_priority_unused = [idx for idx in unused_indexes if idx["priority"] == "high"]
                if high_priority_unused:
                    wasted_mb = sum(idx.get("size_mb", 0) for idx in high_priority_unused)
                    suggestions.append({
                        "type": "warning",
                        "message": f"发现 {len(high_priority_unused)} 个大体积未使用索引(>10MB)",
                        "impact": f"可回收约 {wasted_mb:.2f} MB 空间",
                        "indexes": [f"{idx['schema']}.{idx['index']}" for idx in high_priority_unused[:5]]
                    })
                    for idx in high_priority_unused[:3]:
                        actionable_commands.append({
                            "priority": "high",
                            "type": "drop_index",
                            "index": f"{idx['schema']}.{idx['table']}.{idx['index']}",
                            "commands": [
                                f"-- 删除未使用的大索引",
                                f"DROP INDEX {idx['schema']}.{idx['index']};",
                            ],
                            "description": f"索引大小 {idx['size_mb']:.2f} MB，从未被使用",
                            "warning": "请先在测试环境验证，确认无影响后再执行"
                        })

            if invalid_indexes:
                suggestions.append({
                    "type": "critical",
                    "message": f"发现 {len(invalid_indexes)} 个无效索引",
                    "impact": "无效索引会导致查询失败或性能问题",
                    "indexes": [f"{idx['schema']}.{idx['index']}" for idx in invalid_indexes[:5]]
                })
                for idx in invalid_indexes[:3]:
                    actionable_commands.append({
                        "priority": "high",
                        "type": "rebuild_index",
                        "index": f"{idx['schema']}.{idx['table']}.{idx['index']}",
                        "commands": [
                            f"-- 重建无效索引",
                            f"ALTER INDEX {idx['schema']}.{idx['index']} REBUILD;",
                        ],
                        "description": f"索引状态为 {idx['status']}，需要重建"
                    })

            return self._create_result(
                success=True,
                message=f"索引使用分析完成，健康评分: {health_score}/100",
                data={
                    "unused_indexes": unused_indexes,
                    "hot_indexes": hot_indexes,
                    "invalid_indexes": invalid_indexes,
                    "health_score": health_score,
                    "total_unused_index_size_mb": round(total_unused_size, 2),
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

    def _calculate_oracle_index_health_score(
        self,
        unused_indexes: List[Dict],
        invalid_indexes: List[Dict]
    ) -> int:
        """
        计算Oracle索引健康评分

        评分标准:
        - 基础分: 100分
        - 高优先级未使用索引: -10分/个（最多-30分）
        - 无效索引: -20分/个（最多-40分）

        返回:
            int: 健康评分(0-100)
        """
        all_items = unused_indexes + invalid_indexes
        rules = [
            {
                "name": "高优先级未使用索引",
                "filter": lambda x: x.get("priority") == "high" and x.get("size_mb") is not None,
                "deduction": 10,
                "max_deduction": 30
            },
            {
                "name": "无效索引",
                "filter": lambda x: x.get("status") is not None and x.get("status") != "VALID",
                "deduction": 20,
                "max_deduction": 40
            }
        ]
        return self._calculate_health_score(all_items, rules)

    def analyze_tablespace_fragmentation(self) -> Dict[str, Any]:
        """
        分析Oracle表空间碎片情况

        Oracle表空间在频繁分配和释放空间后会产生碎片，影响空间使用效率。
        提供详细的碎片分析、健康评分和具体的优化建议。

        返回:
            Dict: 表空间碎片分析结果，包含：
                - fragmented_tablespaces: 碎片表空间列表
                - health_score: 健康评分(0-100)
                - total_wasted_space_mb: 总浪费空间(MB)
                - suggestions: 优化建议
                - actionable_commands: 可执行的SQL命令
        """
        try:
            # 获取表空间碎片信息
            fragmented_tablespaces = []
            total_wasted_space = 0

            result = self._execute_query("""
                SELECT * FROM (
                    SELECT
                        fs.tablespace_name,
                        ROUND(SUM(fs.bytes) / 1024 / 1024, 2) as free_space_mb,
                        COUNT(*) as free_extents,
                        ROUND(AVG(fs.bytes) / 1024 / 1024, 2) as avg_extent_mb,
                        MAX(fs.bytes) / 1024 / 1024 as max_extent_mb,
                        df.total_mb,
                        ROUND((SUM(fs.bytes) / df.total_mb / 1024 / 1024) * 100, 2) as free_pct
                    FROM dba_free_space fs
                    JOIN (
                        SELECT tablespace_name, SUM(bytes) as total_mb
                        FROM dba_data_files
                        GROUP BY tablespace_name
                    ) df ON fs.tablespace_name = df.tablespace_name
                    WHERE fs.tablespace_name NOT IN ('SYSTEM', 'SYSAUX')
                    GROUP BY fs.tablespace_name, df.total_mb
                    HAVING COUNT(*) > 10
                    ORDER BY COUNT(*) DESC
                ) WHERE ROWNUM <= 20
            """)

            for row in result or []:
                tablespace = row[0]
                free_mb = row[1] or 0
                free_extents = row[2] or 0
                avg_extent = row[3] or 0
                max_extent = row[4] or 0
                total_mb = row[5] or 0
                free_pct = row[6] or 0

                # 计算碎片率（碎片越多，avg_extent越小）
                frag_ratio = 0
                if max_extent > 0:
                    frag_ratio = (1 - (avg_extent / max_extent)) * 100

                total_wasted_space += free_mb

                # 计算优先级
                if frag_ratio > 50 and free_mb > 100:
                    priority = "high"
                elif frag_ratio > 30 or free_mb > 50:
                    priority = "medium"
                else:
                    priority = "low"

                fragmented_tablespaces.append({
                    "tablespace": tablespace,
                    "free_space_mb": free_mb,
                    "free_extents": free_extents,
                    "avg_extent_mb": avg_extent,
                    "max_extent_mb": max_extent,
                    "total_mb": total_mb,
                    "free_percentage": free_pct,
                    "fragmentation_ratio": round(frag_ratio, 2),
                    "priority": priority
                })

            # 计算健康评分
            health_score = self._calculate_tablespace_health_score(fragmented_tablespaces)

            # 生成建议和可执行命令
            suggestions = []
            actionable_commands = []

            if fragmented_tablespaces:
                high_priority = [t for t in fragmented_tablespaces if t["priority"] == "high"]
                if high_priority:
                    wasted = sum(t.get("free_space_mb", 0) for t in high_priority)
                    suggestions.append({
                        "type": "warning",
                        "message": f"发现 {len(high_priority)} 个表空间严重碎片化",
                        "impact": f"可回收约 {wasted:.2f} MB 空间",
                        "tablespaces": [t['tablespace'] for t in high_priority[:5]]
                    })
                    for t in high_priority[:3]:
                        actionable_commands.append({
                            "priority": "high",
                            "type": "coalesce_tablespace",
                            "tablespace": t['tablespace'],
                            "commands": [
                                f"-- 整理表空间 {t['tablespace']} 碎片",
                                f"-- 方法1: 导出导入表数据（推荐）",
                                f"-- expdp/impdp 或使用数据泵",
                                f"",
                                f"-- 方法2: 移动表到新的表空间",
                                f"-- ALTER TABLE schema.table MOVE TABLESPACE new_ts;",
                                f"",
                                f"-- 方法3: 收缩数据文件（需要空闲空间连续）",
                                f"-- ALTER DATABASE DATAFILE '...' RESIZE new_size;",
                            ],
                            "description": f"碎片率 {t['fragmentation_ratio']:.1f}%，有 {t['free_extents']} 个碎片",
                            "warning": "表空间整理需要维护窗口，建议在业务低峰期执行"
                        })

            return self._create_result(
                success=True,
                message=f"表空间碎片分析完成，健康评分: {health_score}/100",
                data={
                    "fragmented_tablespaces": fragmented_tablespaces,
                    "health_score": health_score,
                    "total_wasted_space_mb": round(total_wasted_space, 2),
                    "suggestions": suggestions,
                    "actionable_commands": actionable_commands
                }
            )

        except Exception as e:
            logger.error(f"表空间碎片分析失败: {e}")
            return self._create_result(
                success=False,
                message="表空间碎片分析失败",
                error=str(e)
            )

    def _calculate_tablespace_health_score(self, fragmented_tablespaces: List[Dict]) -> int:
        """
        计算表空间健康评分

        评分标准:
        - 基础分: 100分
        - 高优先级碎片表空间: -15分/个（最多-45分）
        - 中优先级碎片表空间: -8分/个（最多-24分）

        返回:
            int: 健康评分(0-100)
        """
        rules = [
            {
                "name": "高优先级碎片表空间",
                "filter": lambda x: x.get("priority") == "high",
                "deduction": 15,
                "max_deduction": 45
            },
            {
                "name": "中优先级碎片表空间",
                "filter": lambda x: x.get("priority") == "medium",
                "deduction": 8,
                "max_deduction": 24
            }
        ]
        return self._calculate_health_score(fragmented_tablespaces, rules)
