"""
SQL Server诊断器

提供SQL Server数据库的专项诊断能力

文件功能：SQL Server数据库诊断器实现
主要类：MSSQLDiagnostician - SQL Server数据库诊断器

支持的诊断功能：
    - 慢查询分析（Query Store / sys.dm_exec_query_stats）
    - 性能指标分析（等待统计、执行统计）
    - 索引使用分析（缺失索引、未使用索引）
    - 阻塞和死锁分析
    - 数据库统计信息
    - 内存和缓存分析

依赖：
    - pyodbc 或 pymssql 驱动
    - SQL Server 2016+（支持Query Store）

作者：Magiczc
创建时间：2026-06-03
版本：1.0.0
"""

import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field

from dbskiter.shared.unified_connector import UnifiedConnector
from dbskiter.shared.sql_fingerprint import SQLFingerprinter
from .base import BaseDiagnostician

logger = logging.getLogger(__name__)


@dataclass
class SlowQueryRecord:
    """SQL Server慢查询记录"""
    query_hash: str
    query_plan_hash: str
    sql_text: str
    execution_count: int
    total_duration_ms: float
    avg_duration_ms: float
    max_duration_ms: float
    total_logical_reads: int
    avg_logical_reads: int
    total_physical_reads: int
    total_rows: int
    last_execution_time: datetime
    database_name: str


@dataclass
class WaitStatsRecord:
    """等待统计记录"""
    wait_type: str
    waiting_tasks_count: int
    wait_time_ms: float
    max_wait_time_ms: float
    signal_wait_time_ms: float
    wait_category: str


@dataclass
class IndexUsageRecord:
    """索引使用记录"""
    database_name: str
    table_name: str
    index_name: str
    index_type: str
    user_seeks: int
    user_scans: int
    user_lookups: int
    user_updates: int
    last_user_seek: Optional[datetime]
    last_user_scan: Optional[datetime]
    last_user_lookup: Optional[datetime]
    last_user_update: Optional[datetime]


@dataclass
class MissingIndexRecord:
    """缺失索引记录"""
    database_name: str
    table_name: str
    equality_columns: str
    inequality_columns: str
    included_columns: str
    user_seeks: int
    user_scans: int
    avg_total_user_cost: float
    avg_user_impact: float
    impact_score: float


class MSSQLDiagnostician(BaseDiagnostician):
    """
    SQL Server数据库诊断器

    提供SQL Server特有的诊断能力：
    - 慢查询分析（Query Store / DMV）
    - 等待统计和性能指标
    - 索引使用分析
    - 阻塞和死锁检测
    - 内存和缓存分析
    - 数据库统计信息
    """

    def __init__(self, connector: UnifiedConnector):
        """
        初始化SQL Server诊断器

        参数:
            connector: UnifiedConnector实例
        """
        super().__init__(connector)
        self.fingerprinter = SQLFingerprinter()
        self._query_store_enabled: Optional[bool] = None
        self._database_name: Optional[str] = None

    def _get_database_name(self) -> Optional[str]:
        """获取当前数据库名称"""
        if self._database_name is None:
            if hasattr(self.connector, 'database') and self.connector.database:
                self._database_name = self.connector.database
            else:
                try:
                    result = self.connector.execute("SELECT DB_NAME()")
                    if result and result.rows:
                        self._database_name = result.rows[0][0]
                except Exception as e:
                    logger.warning(f"获取数据库名称失败: {e}")
        return self._database_name

    def _is_query_store_enabled(self) -> bool:
        """检查Query Store是否启用"""
        if self._query_store_enabled is None:
            try:
                db_name = self._get_database_name()
                if not db_name:
                    self._query_store_enabled = False
                    return False

                result = self._execute_query("""
                    SELECT actual_state_desc
                    FROM sys.database_query_store_options
                    WHERE actual_state_desc IN ('ON', 'READ_ONLY')
                """)
                self._query_store_enabled = bool(result and len(result) > 0)
            except Exception as e:
                logger.warning(f"检查Query Store状态失败: {e}")
                self._query_store_enabled = False

        return self._query_store_enabled

    def analyze_slow_queries(
        self,
        limit: int = 20,
        min_time: float = 1.0
    ) -> Dict[str, Any]:
        """
        分析SQL Server慢查询

        优先使用Query Store数据，如未启用则使用DMV

        参数:
            limit: 返回条数限制
            min_time: 最小执行时间（秒）

        返回:
            Dict: 慢查询分析结果
        """
        try:
            if self._is_query_store_enabled():
                return self._analyze_slow_queries_from_query_store(limit, min_time)
            else:
                return self._analyze_slow_queries_from_dmv(limit, min_time)

        except Exception as e:
            logger.error(f"慢查询分析失败: {e}")
            return self._create_result(
                success=False,
                message="慢查询分析失败",
                error=str(e)
            )

    def _analyze_slow_queries_from_query_store(
        self,
        limit: int,
        min_time_ms: float
    ) -> Dict[str, Any]:
        """从Query Store分析慢查询"""
        min_time_ms = min_time_ms * 1000  # 转换为毫秒

        result = self._execute_query(f"""
            SELECT TOP {limit}
                q.query_hash,
                q.query_plan_hash,
                qt.query_sql_text,
                rs.count_executions,
                rs.avg_duration / 1000.0 as avg_duration_ms,
                rs.max_duration / 1000.0 as max_duration_ms,
                rs.stdev_duration / 1000.0 as stdev_duration_ms,
                rs.avg_logical_io_reads,
                rs.avg_physical_io_reads,
                rs.avg_rowcount,
                rs.last_execution_time,
                DB_NAME(qt.dbid) as database_name
            FROM sys.query_store_query q
            INNER JOIN sys.query_store_query_text qt ON q.query_text_id = qt.query_text_id
            INNER JOIN sys.query_store_plan p ON q.query_id = p.query_id
            INNER JOIN sys.query_store_runtime_stats rs ON p.plan_id = rs.plan_id
            WHERE rs.avg_duration >= {min_time_ms}
                AND rs.last_execution_time >= DATEADD(hour, -24, GETUTCDATE())
            ORDER BY rs.avg_duration DESC
        """)

        if not result:
            return self._create_result(
                success=True,
                message="未找到慢查询",
                data={"total_queries": 0, "queries": [], "patterns": []}
            )

        queries = []
        for row in result:
            queries.append({
                "query_hash": row[0],
                "query_plan_hash": row[1],
                "sql_text": row[2],
                "sql_short": row[2][:200] + "..." if len(row[2]) > 200 else row[2],
                "execution_count": row[3],
                "avg_duration_ms": row[4],
                "max_duration_ms": row[5],
                "stdev_duration_ms": row[6],
                "avg_logical_reads": row[7],
                "avg_physical_reads": row[8],
                "avg_rowcount": row[9],
                "last_execution_time": row[10].isoformat() if row[10] else None,
                "database_name": row[11]
            })

        # SQL指纹聚合
        patterns = self._aggregate_query_patterns(queries)

        return self._create_result(
            success=True,
            message=f"成功分析 {len(queries)} 个慢查询（Query Store）",
            data={
                "total_queries": len(queries),
                "unique_patterns": len(patterns),
                "queries": queries,
                "patterns": patterns,
                "source": "query_store"
            }
        )

    def _analyze_slow_queries_from_dmv(
        self,
        limit: int,
        min_time_ms: float
    ) -> Dict[str, Any]:
        """从DMV分析慢查询（Query Store未启用时）"""
        min_time_ms = min_time_ms * 1000

        result = self._execute_query(f"""
            SELECT TOP {limit}
                qs.query_hash,
                qs.query_plan_hash,
                st.text as sql_text,
                qs.execution_count,
                qs.total_elapsed_time / qs.execution_count / 1000.0 as avg_duration_ms,
                qs.max_elapsed_time / 1000.0 as max_duration_ms,
                qs.total_logical_reads / qs.execution_count as avg_logical_reads,
                qs.total_physical_reads / qs.execution_count as avg_physical_reads,
                qs.total_rows / qs.execution_count as avg_rows,
                qs.last_execution_time,
                DB_NAME(st.dbid) as database_name
            FROM sys.dm_exec_query_stats qs
            CROSS APPLY sys.dm_exec_sql_text(qs.sql_handle) st
            WHERE qs.total_elapsed_time / qs.execution_count >= {min_time_ms}
                AND qs.last_execution_time >= DATEADD(hour, -24, GETUTCDATE())
            ORDER BY avg_duration_ms DESC
        """)

        if not result:
            return self._create_result(
                success=True,
                message="未找到慢查询",
                data={"total_queries": 0, "queries": [], "patterns": []}
            )

        queries = []
        for row in result:
            sql_text = row[2]
            # 去除存储过程调用时的额外文本
            if sql_text and "CREATE PROC" in sql_text.upper():
                sql_text = sql_text[:500]

            queries.append({
                "query_hash": row[0],
                "query_plan_hash": row[1],
                "sql_text": sql_text,
                "sql_short": sql_text[:200] + "..." if len(sql_text) > 200 else sql_text,
                "execution_count": row[3],
                "avg_duration_ms": row[4],
                "max_duration_ms": row[5],
                "avg_logical_reads": row[6],
                "avg_physical_reads": row[7],
                "avg_rows": row[8],
                "last_execution_time": row[9].isoformat() if row[9] else None,
                "database_name": row[10]
            })

        patterns = self._aggregate_query_patterns(queries)

        return self._create_result(
            success=True,
            message=f"成功分析 {len(queries)} 个慢查询（DMV）",
            data={
                "total_queries": len(queries),
                "unique_patterns": len(patterns),
                "queries": queries,
                "patterns": patterns,
                "source": "dmv"
            }
        )

    def _aggregate_query_patterns(self, queries: List[Dict]) -> List[Dict]:
        """聚合查询模式"""
        patterns = {}

        for q in queries:
            sql_text = q.get("sql_text", "")
            fp_result = self.fingerprinter.fingerprint(sql_text)
            fp = fp_result.fingerprint if hasattr(fp_result, 'fingerprint') else str(fp_result)

            if fp not in patterns:
                patterns[fp] = {
                    "fingerprint": fp,
                    "sql_pattern": sql_text[:200] if sql_text else "",
                    "count": 0,
                    "total_executions": 0,
                    "total_duration_ms": 0.0,
                    "max_duration_ms": 0.0,
                    "databases": set()
                }

            patterns[fp]["count"] += 1
            patterns[fp]["total_executions"] += q.get("execution_count", 1)
            patterns[fp]["total_duration_ms"] += q.get("avg_duration_ms", 0) * q.get("execution_count", 1)
            patterns[fp]["max_duration_ms"] = max(
                patterns[fp]["max_duration_ms"],
                q.get("max_duration_ms", 0)
            )
            if q.get("database_name"):
                patterns[fp]["databases"].add(q["database_name"])

        # 转换为列表并计算平均值
        result = []
        for fp, data in patterns.items():
            data["avg_duration_ms"] = (
                data["total_duration_ms"] / data["total_executions"]
                if data["total_executions"] > 0 else 0
            )
            data["databases"] = list(data["databases"])
            result.append(data)

        # 按总持续时间排序
        result.sort(key=lambda x: x["total_duration_ms"], reverse=True)
        return result[:10]

    def analyze_performance_metrics(
        self,
        duration_minutes: int = 10
    ) -> Dict[str, Any]:
        """
        分析SQL Server性能指标

        参数:
            duration_minutes: 采集时长（分钟）

        返回:
            Dict: 性能分析结果
        """
        try:
            metrics = {}

            # 1. 获取等待统计
            wait_stats = self._get_wait_stats()
            metrics["wait_stats"] = wait_stats

            # 2. 获取执行统计
            exec_stats = self._get_execution_stats()
            metrics["execution_stats"] = exec_stats

            # 3. 获取缓存命中率
            cache_stats = self._get_cache_stats()
            metrics["cache_stats"] = cache_stats

            # 4. 获取连接统计
            connection_stats = self._get_connection_stats()
            metrics["connection_stats"] = connection_stats

            # 5. 获取内存使用
            memory_stats = self._get_memory_stats()
            metrics["memory_stats"] = memory_stats

            # 6. 获取IO统计
            io_stats = self._get_io_stats()
            metrics["io_stats"] = io_stats

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

    def _get_wait_stats(self) -> List[Dict]:
        """获取等待统计"""
        result = self._execute_query("""
            SELECT TOP 20
                wait_type,
                waiting_tasks_count,
                wait_time_ms / 1000.0 as wait_time_sec,
                max_wait_time_ms / 1000.0 as max_wait_time_sec,
                signal_wait_time_ms / 1000.0 as signal_wait_time_sec,
                CASE
                    WHEN wait_type LIKE 'PAGEIOLATCH%' THEN 'IO'
                    WHEN wait_type LIKE 'PAGELATCH%' THEN 'Memory'
                    WHEN wait_type LIKE 'LCK%' THEN 'Locking'
                    WHEN wait_type LIKE 'LATCH%' THEN 'Latch'
                    WHEN wait_type LIKE 'CXPACKET%' OR wait_type LIKE 'CXCONSUMER%' THEN 'Parallelism'
                    WHEN wait_type LIKE 'SOS_SCHEDULER%' THEN 'CPU'
                    WHEN wait_type LIKE 'ASYNC_NETWORK%' THEN 'Network'
                    WHEN wait_type LIKE 'WRITELOG%' OR wait_type LIKE 'LOGBUFFER%' THEN 'Transaction Log'
                    ELSE 'Other'
                END as wait_category
            FROM sys.dm_os_wait_stats
            WHERE wait_type NOT IN (
                'CLR_SEMAPHORE', 'LAZYWRITER_SLEEP', 'RESOURCE_QUEUE',
                'SLEEP_TASK', 'SLEEP_SYSTEMTASK', 'SQLTRACE_BUFFER_FLUSH',
                'WAITFOR', 'LOGMGR_QUEUE', 'CHECKPOINT_QUEUE', 'REQUEST_FOR_DEADLOCK_SEARCH'
            )
            ORDER BY wait_time_ms DESC
        """)

        if not result:
            return []

        return [
            {
                "wait_type": row[0],
                "waiting_tasks_count": row[1],
                "wait_time_sec": row[2],
                "max_wait_time_sec": row[3],
                "signal_wait_time_sec": row[4],
                "wait_category": row[5]
            }
            for row in result
        ]

    def _get_execution_stats(self) -> Dict:
        """获取执行统计"""
        result = self._execute_query("""
            SELECT
                (SELECT SUM(cntr_value) FROM sys.dm_os_performance_counters
                 WHERE counter_name = 'Batch Requests/sec') as batch_requests,
                (SELECT SUM(cntr_value) FROM sys.dm_os_performance_counters
                 WHERE counter_name = 'SQL Compilations/sec') as sql_compilations,
                (SELECT SUM(cntr_value) FROM sys.dm_os_performance_counters
                 WHERE counter_name = 'SQL Re-Compilations/sec') as sql_recompilations,
                (SELECT SUM(cntr_value) FROM sys.dm_os_performance_counters
                 WHERE counter_name = 'Transactions/sec') as transactions
        """)

        if result and result[0]:
            return {
                "batch_requests": result[0][0],
                "sql_compilations": result[0][1],
                "sql_recompilations": result[0][2],
                "transactions": result[0][3]
            }
        return {}

    def _get_cache_stats(self) -> Dict:
        """获取缓存统计"""
        result = self._execute_query("""
            SELECT
                (SELECT cntr_value * 100.0 / NULLIF((SELECT cntr_value
                    FROM sys.dm_os_performance_counters
                    WHERE counter_name = 'Buffer cache hit ratio base'), 0)
                 FROM sys.dm_os_performance_counters
                 WHERE counter_name = 'Buffer cache hit ratio') as buffer_cache_hit_ratio,
                (SELECT cntr_value FROM sys.dm_os_performance_counters
                 WHERE counter_name = 'Page life expectancy') as page_life_expectancy,
                (SELECT cntr_value FROM sys.dm_os_performance_counters
                 WHERE counter_name = 'Procedure cache hit ratio') as procedure_cache_hit_ratio
        """)

        if result and result[0]:
            return {
                "buffer_cache_hit_ratio": result[0][0],
                "page_life_expectancy_sec": result[0][1],
                "procedure_cache_hit_ratio": result[0][2]
            }
        return {}

    def _get_connection_stats(self) -> Dict:
        """获取连接统计"""
        result = self._execute_query("""
            SELECT
                (SELECT COUNT(*) FROM sys.dm_exec_sessions WHERE status = 'sleeping') as sleeping_sessions,
                (SELECT COUNT(*) FROM sys.dm_exec_sessions WHERE status = 'running') as running_sessions,
                (SELECT COUNT(*) FROM sys.dm_exec_sessions WHERE status = 'suspended') as suspended_sessions,
                (SELECT COUNT(*) FROM sys.dm_exec_sessions WHERE is_user_process = 1) as user_connections,
                (SELECT COUNT(*) FROM sys.dm_exec_sessions) as total_sessions
        """)

        if result and result[0]:
            return {
                "sleeping_sessions": result[0][0],
                "running_sessions": result[0][1],
                "suspended_sessions": result[0][2],
                "user_connections": result[0][3],
                "total_sessions": result[0][4]
            }
        return {}

    def _get_memory_stats(self) -> Dict:
        """获取内存统计"""
        result = self._execute_query("""
            SELECT
                (SELECT cntr_value / 1024.0 FROM sys.dm_os_performance_counters
                 WHERE counter_name = 'Total Server Memory (KB)') as total_server_memory_mb,
                (SELECT cntr_value / 1024.0 FROM sys.dm_os_performance_counters
                 WHERE counter_name = 'Target Server Memory (KB)') as target_server_memory_mb,
                (SELECT cntr_value / 1024.0 FROM sys.dm_os_performance_counters
                 WHERE counter_name = 'Database Cache Memory (KB)') as database_cache_memory_mb,
                (SELECT cntr_value / 1024.0 FROM sys.dm_os_performance_counters
                 WHERE counter_name = 'Stolen Server Memory (KB)') as stolen_memory_mb
        """)

        if result and result[0]:
            return {
                "total_server_memory_mb": result[0][0],
                "target_server_memory_mb": result[0][1],
                "database_cache_memory_mb": result[0][2],
                "stolen_memory_mb": result[0][3]
            }
        return {}

    def _get_io_stats(self) -> Dict:
        """获取IO统计"""
        result = self._execute_query("""
            SELECT
                DB_NAME(database_id) as database_name,
                SUM(num_of_reads) as total_reads,
                SUM(num_of_writes) as total_writes,
                SUM(num_of_bytes_read / 1024.0 / 1024.0) as read_mb,
                SUM(num_of_bytes_written / 1024.0 / 1024.0) as write_mb,
                SUM(io_stall_read_ms) as read_stall_ms,
                SUM(io_stall_write_ms) as write_stall_ms
            FROM sys.dm_io_virtual_file_stats(NULL, NULL)
            GROUP BY database_id
            ORDER BY SUM(num_of_reads + num_of_writes) DESC
        """)

        if not result:
            return {}

        return [
            {
                "database_name": row[0],
                "total_reads": row[1],
                "total_writes": row[2],
                "read_mb": round(row[3], 2),
                "write_mb": round(row[4], 2),
                "read_stall_ms": row[5],
                "write_stall_ms": row[6]
            }
            for row in result
        ]

    def analyze_index_usage(self) -> Dict[str, Any]:
        """
        分析SQL Server索引使用情况

        返回:
            Dict: 索引使用分析结果
        """
        try:
            # 1. 获取索引使用统计
            index_usage = self._get_index_usage_stats()

            # 2. 获取缺失索引建议
            missing_indexes = self._get_missing_indexes()

            # 3. 获取未使用索引
            unused_indexes = self._get_unused_indexes()

            # 4. 计算健康评分
            health_score = self._calculate_index_health_score(
                index_usage, missing_indexes, unused_indexes
            )

            # 5. 生成建议
            suggestions = self._generate_index_suggestions(
                missing_indexes, unused_indexes
            )

            return self._create_result(
                success=True,
                message=f"索引分析完成，健康评分: {health_score}",
                data={
                    "health_score": health_score,
                    "index_usage": index_usage,
                    "missing_indexes": missing_indexes,
                    "unused_indexes": unused_indexes,
                    "suggestions": suggestions
                }
            )

        except Exception as e:
            logger.error(f"索引分析失败: {e}")
            return self._create_result(
                success=False,
                message="索引分析失败",
                error=str(e)
            )

    def _get_index_usage_stats(self) -> List[Dict]:
        """获取索引使用统计"""
        result = self._execute_query("""
            SELECT TOP 100
                DB_NAME(s.database_id) as database_name,
                OBJECT_NAME(s.object_id, s.database_id) as table_name,
                i.name as index_name,
                i.type_desc as index_type,
                s.user_seeks,
                s.user_scans,
                s.user_lookups,
                s.user_updates,
                s.last_user_seek,
                s.last_user_scan,
                s.last_user_lookup,
                s.last_user_update
            FROM sys.dm_db_index_usage_stats s
            INNER JOIN sys.indexes i ON s.object_id = i.object_id AND s.index_id = i.index_id
            WHERE s.database_id = DB_ID()
                AND i.name IS NOT NULL
            ORDER BY (s.user_seeks + s.user_scans + s.user_lookups) DESC
        """)

        if not result:
            return []

        return [
            {
                "database_name": row[0],
                "table_name": row[1],
                "index_name": row[2],
                "index_type": row[3],
                "user_seeks": row[4],
                "user_scans": row[5],
                "user_lookups": row[6],
                "user_updates": row[7],
                "last_user_seek": row[8].isoformat() if row[8] else None,
                "last_user_scan": row[9].isoformat() if row[9] else None,
                "last_user_lookup": row[10].isoformat() if row[10] else None,
                "last_user_update": row[11].isoformat() if row[11] else None
            }
            for row in result
        ]

    def _get_missing_indexes(self) -> List[Dict]:
        """获取缺失索引建议"""
        result = self._execute_query("""
            SELECT TOP 20
                DB_NAME(mid.database_id) as database_name,
                OBJECT_NAME(mid.object_id, mid.database_id) as table_name,
                mid.equality_columns,
                mid.inequality_columns,
                mid.included_columns,
                migs.user_seeks,
                migs.user_scans,
                migs.avg_total_user_cost,
                migs.avg_user_impact,
                (migs.user_seeks + migs.user_scans) * migs.avg_total_user_cost * migs.avg_user_impact / 100.0 as impact_score
            FROM sys.dm_db_missing_index_groups mig
            INNER JOIN sys.dm_db_missing_index_group_stats migs ON mig.index_group_handle = migs.group_handle
            INNER JOIN sys.dm_db_missing_index_details mid ON mig.index_handle = mid.index_handle
            WHERE mid.database_id = DB_ID()
            ORDER BY impact_score DESC
        """)

        if not result:
            return []

        return [
            {
                "database_name": row[0],
                "table_name": row[1],
                "equality_columns": row[2],
                "inequality_columns": row[3],
                "included_columns": row[4],
                "user_seeks": row[5],
                "user_scans": row[6],
                "avg_total_user_cost": row[7],
                "avg_user_impact": row[8],
                "impact_score": round(row[9], 2)
            }
            for row in result
        ]

    def _get_unused_indexes(self) -> List[Dict]:
        """获取未使用索引"""
        result = self._execute_query("""
            SELECT
                DB_NAME(s.database_id) as database_name,
                OBJECT_NAME(s.object_id, s.database_id) as table_name,
                i.name as index_name,
                i.type_desc as index_type,
                s.user_updates,
                s.last_user_update
            FROM sys.dm_db_index_usage_stats s
            INNER JOIN sys.indexes i ON s.object_id = i.object_id AND s.index_id = i.index_id
            WHERE s.database_id = DB_ID()
                AND i.name IS NOT NULL
                AND i.is_primary_key = 0
                AND i.is_unique_constraint = 0
                AND s.user_seeks = 0
                AND s.user_scans = 0
                AND s.user_lookups = 0
                AND s.user_updates > 100
            ORDER BY s.user_updates DESC
        """)

        if not result:
            return []

        return [
            {
                "database_name": row[0],
                "table_name": row[1],
                "index_name": row[2],
                "index_type": row[3],
                "user_updates": row[4],
                "last_user_update": row[5].isoformat() if row[5] else None
            }
            for row in result
        ]

    def _calculate_index_health_score(
        self,
        index_usage: List[Dict],
        missing_indexes: List[Dict],
        unused_indexes: List[Dict]
    ) -> int:
        """计算索引健康评分"""
        score = 100

        # 缺失索引扣分
        if missing_indexes:
            high_impact = sum(1 for mi in missing_indexes if mi.get("impact_score", 0) > 1000)
            score -= min(high_impact * 5, 30)

        # 未使用索引扣分
        if unused_indexes:
            score -= min(len(unused_indexes) * 2, 20)

        return max(0, score)

    def _generate_index_suggestions(
        self,
        missing_indexes: List[Dict],
        unused_indexes: List[Dict]
    ) -> List[str]:
        """生成索引优化建议"""
        suggestions = []

        # 缺失索引建议
        for mi in missing_indexes[:5]:
            if mi.get("impact_score", 0) > 1000:
                cols = mi.get("equality_columns", "") or mi.get("inequality_columns", "")
                suggestions.append(
                    f"建议在表 {mi['table_name']} 的列 ({cols}) 上创建索引，"
                    f"预计影响评分: {mi['impact_score']}"
                )

        # 未使用索引建议
        for ui in unused_indexes[:5]:
            suggestions.append(
                f"考虑删除表 {ui['table_name']} 上的未使用索引 {ui['index_name']}，"
                f"已产生 {ui['user_updates']} 次更新开销"
            )

        return suggestions

    def analyze_blocking(self) -> Dict[str, Any]:
        """
        分析SQL Server阻塞情况

        返回:
            Dict: 阻塞分析结果
        """
        try:
            # 获取当前阻塞信息
            blocking_info = self._get_blocking_info()

            # 获取死锁历史
            deadlocks = self._get_deadlock_history()

            return self._create_result(
                success=True,
                message=f"阻塞分析完成，发现 {len(blocking_info)} 个阻塞，{len(deadlocks)} 个历史死锁",
                data={
                    "current_blocking": blocking_info,
                    "deadlock_history": deadlocks
                }
            )

        except Exception as e:
            logger.error(f"阻塞分析失败: {e}")
            return self._create_result(
                success=False,
                message="阻塞分析失败",
                error=str(e)
            )

    def _get_blocking_info(self) -> List[Dict]:
        """获取当前阻塞信息"""
        result = self._execute_query("""
            SELECT
                blocking_session_id,
                session_id,
                wait_type,
                wait_time / 1000.0 as wait_time_sec,
                wait_resource,
                t.text as sql_text
            FROM sys.dm_exec_requests r
            CROSS APPLY sys.dm_exec_sql_text(r.sql_handle) t
            WHERE blocking_session_id <> 0
        """)

        if not result:
            return []

        return [
            {
                "blocking_session_id": row[0],
                "blocked_session_id": row[1],
                "wait_type": row[2],
                "wait_time_sec": row[3],
                "wait_resource": row[4],
                "sql_text": row[5][:200] if row[5] else None
            }
            for row in result
        ]

    def _get_deadlock_history(self) -> List[Dict]:
        """获取死锁历史（如果配置了扩展事件）"""
        try:
            result = self._execute_query("""
                SELECT TOP 10
                    name,
                    timestamp_utc,
                    xml_data
                FROM sys.dm_xe_session_targets xst
                INNER JOIN sys.dm_xe_sessions xs ON xst.event_session_address = xs.address
                CROSS APPLY (SELECT CAST(xst.target_data AS XML)) AS target_data_xml(xml_data)
                WHERE xs.name = 'system_health'
                ORDER BY timestamp_utc DESC
            """)

            if not result:
                return []

            return [
                {
                    "name": row[0],
                    "timestamp": row[1].isoformat() if row[1] else None,
                    "has_xml_data": bool(row[2])
                }
                for row in result
            ]
        except Exception as e:
            logger.warning(f"获取死锁历史失败: {e}")
            return []

    def get_database_stats(self) -> Dict[str, Any]:
        """
        获取SQL Server数据库统计信息

        返回:
            Dict: 数据库统计信息
        """
        try:
            stats = {}

            # 1. 数据库基本信息
            db_info = self._get_database_info()
            stats["database_info"] = db_info

            # 2. 文件使用情况
            file_stats = self._get_file_stats()
            stats["file_stats"] = file_stats

            # 3. 表统计信息
            table_stats = self._get_table_stats()
            stats["table_stats"] = table_stats

            # 4. 版本信息
            version_info = self._get_version_info()
            stats["version_info"] = version_info

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

    def _get_database_info(self) -> Dict:
        """获取数据库基本信息"""
        result = self._execute_query("""
            SELECT
                name,
                database_id,
                create_date,
                compatibility_level,
                collation_name,
                user_access_desc,
                state_desc,
                recovery_model_desc
            FROM sys.databases
            WHERE name = DB_NAME()
        """)

        if result and result[0]:
            return {
                "name": result[0][0],
                "database_id": result[0][1],
                "create_date": result[0][2].isoformat() if result[0][2] else None,
                "compatibility_level": result[0][3],
                "collation_name": result[0][4],
                "user_access": result[0][5],
                "state": result[0][6],
                "recovery_model": result[0][7]
            }
        return {}

    def _get_file_stats(self) -> List[Dict]:
        """获取数据库文件统计"""
        result = self._execute_query("""
            SELECT
                DB_NAME(database_id) as database_name,
                name as file_name,
                type_desc as file_type,
                physical_name,
                size * 8.0 / 1024.0 as size_mb,
                max_size * 8.0 / 1024.0 as max_size_mb,
                growth * 8.0 / 1024.0 as growth_mb,
                is_percent_growth
            FROM sys.master_files
            WHERE database_id = DB_ID()
        """)

        if not result:
            return []

        return [
            {
                "database_name": row[0],
                "file_name": row[1],
                "file_type": row[2],
                "physical_name": row[3],
                "size_mb": round(row[4], 2),
                "max_size_mb": round(row[5], 2) if row[5] > 0 else "Unlimited",
                "growth_mb": round(row[6], 2),
                "is_percent_growth": bool(row[7])
            }
            for row in result
        ]

    def _get_table_stats(self) -> List[Dict]:
        """获取表统计信息"""
        result = self._execute_query("""
            SELECT TOP 50
                t.name as table_name,
                p.rows as row_count,
                SUM(a.total_pages) * 8.0 / 1024.0 as total_space_mb,
                SUM(a.used_pages) * 8.0 / 1024.0 as used_space_mb,
                SUM(a.data_pages) * 8.0 / 1024.0 as data_space_mb
            FROM sys.tables t
            INNER JOIN sys.indexes i ON t.object_id = i.object_id
            INNER JOIN sys.partitions p ON i.object_id = p.object_id AND i.index_id = p.index_id
            INNER JOIN sys.allocation_units a ON p.partition_id = a.container_id
            WHERE t.is_ms_shipped = 0
                AND i.object_id > 255
            GROUP BY t.name, p.rows
            ORDER BY total_space_mb DESC
        """)

        if not result:
            return []

        return [
            {
                "table_name": row[0],
                "row_count": row[1],
                "total_space_mb": round(row[2], 2),
                "used_space_mb": round(row[3], 2),
                "data_space_mb": round(row[4], 2)
            }
            for row in result
        ]

    def _get_version_info(self) -> Dict:
        """获取SQL Server版本信息"""
        result = self._execute_query("""
            SELECT
                @@VERSION as version_string,
                @@SERVERNAME as server_name,
                SERVERPROPERTY('ProductVersion') as product_version,
                SERVERPROPERTY('ProductLevel') as product_level,
                SERVERPROPERTY('Edition') as edition,
                SERVERPROPERTY('EngineEdition') as engine_edition
        """)

        if result and result[0]:
            return {
                "version_string": result[0][0],
                "server_name": result[0][1],
                "product_version": result[0][2],
                "product_level": result[0][3],
                "edition": result[0][4],
                "engine_edition": result[0][5]
            }
        return {}
