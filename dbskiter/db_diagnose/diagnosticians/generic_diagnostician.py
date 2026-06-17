"""
通用数据库诊断器（增强版）

为任意 JDBC 兼容数据库提供基础诊断能力。
借鉴 GenericMetricsCollector 和 GenericInspector 的能力探测模式，
通过标准 SQL 和 INFORMATION_SCHEMA 获取基础诊断指标，
生成有实际意义的诊断结果而非空提示。

功能特性：
    - 自动探测数据库能力（支持哪些系统视图）
    - 优雅降级：不支持的功能返回提示信息而非报错
    - 与 db_monitor/db_inspector 共享能力探测逻辑

支持的数据库（理论上所有 JDBC 兼容数据库）：
    - Trino / Presto
    - DuckDB
    - Apache Derby
    - H2
    - HSQLDB
    - 任何支持 JDBC 4.0+ 和 INFORMATION_SCHEMA 的数据库

使用示例：
    >>> from dbskiter.db_diagnose.diagnosticians import get_diagnostician
    >>> d = get_diagnostician('trino', connector)
    >>> result = d.analyze_slow_queries()
    >>> result = d.analyze_performance_metrics()
    >>> result = d.get_database_stats()

版本: 2.0.0
作者: AI Assistant
创建时间: 2026-06-05
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from dbskiter.shared.sql_utils import build_capabilities_display

from dbskiter.shared.unified_connector import UnifiedConnector
from .base import BaseDiagnostician

logger = logging.getLogger(__name__)


class GenericDiagnostician(BaseDiagnostician):
    """
    通用数据库诊断器

    通过标准 SQL 和 INFORMATION_SCHEMA 获取基础诊断指标，
    适用于任何支持标准 JDBC API 的数据库。

    属性：
        connector: UnifiedConnector 实例
        dialect: 数据库方言
        _capabilities: 能力探测结果缓存
    """

    def __init__(self, connector: UnifiedConnector):
        """
        初始化通用诊断器

        参数：
            connector: UnifiedConnector 实例
        """
        super().__init__(connector)
        self._capabilities: Optional[Dict[str, bool]] = None
        self._version_cache: Optional[str] = None

    # ==================== 能力探测 ====================

    def _detect_capabilities(self) -> Dict[str, bool]:
        """
        探测目标数据库支持的功能

        与 GenericMetricsCollector/GenericInspector 保持一致的能力探测逻辑，
        结果会缓存，避免重复探测。

        返回：
            Dict[str, bool]: 功能支持状态映射
        """
        if self._capabilities is not None:
            return self._capabilities

        capabilities = {
            "information_schema": False,
            "pg_stat_activity": False,
            "pg_stat_statements": False,
            "pg_stat_database": False,
            "performance_schema": False,
            "v$session": False,
            "sys.dm_exec_sessions": False,
            "pragma": False,
            "version_query": False,
        }

        # 测试 INFORMATION_SCHEMA
        rows = self._execute_query(
            "SELECT 1 FROM INFORMATION_SCHEMA.TABLES LIMIT 1"
        )
        if rows:
            capabilities["information_schema"] = True

        # 测试 PostgreSQL 风格
        rows = self._execute_query(
            "SELECT 1 FROM pg_stat_activity LIMIT 0"
        )
        if rows is not None:
            capabilities["pg_stat_activity"] = True

        # 测试 pg_stat_statements
        rows = self._execute_query(
            "SELECT 1 FROM pg_stat_statements LIMIT 0"
        )
        if rows is not None:
            capabilities["pg_stat_statements"] = True

        # 测试 pg_stat_database
        rows = self._execute_query(
            "SELECT 1 FROM pg_stat_database LIMIT 0"
        )
        if rows is not None:
            capabilities["pg_stat_database"] = True

        # 测试 MySQL 风格 performance_schema
        rows = self._execute_query(
            "SELECT 1 FROM performance_schema.threads LIMIT 0"
        )
        if rows is not None:
            capabilities["performance_schema"] = True

        # 测试 Oracle 风格
        rows = self._execute_query(
            "SELECT 1 FROM v$session WHERE ROWNUM = 0"
        )
        if rows is not None:
            capabilities["v$session"] = True

        # 测试 SQL Server 风格
        rows = self._execute_query(
            "SELECT 1 FROM sys.dm_exec_sessions WHERE 1=0"
        )
        if rows is not None:
            capabilities["sys.dm_exec_sessions"] = True

        # 测试 PRAGMA（SQLite 风格）
        rows = self._execute_query("PRAGMA page_count")
        if rows and len(rows) > 0:
            capabilities["pragma"] = True

        # 测试版本查询
        for sql in ["SELECT VERSION()", "SELECT version()", "SELECT @@version"]:
            rows = self._execute_query(sql)
            if rows and len(rows) > 0 and rows[0][0]:
                capabilities["version_query"] = True
                self._version_cache = str(rows[0][0])
                break

        self._capabilities = capabilities
        logger.info(f"诊断能力探测完成: {capabilities}")
        return capabilities

    @staticmethod
    def _build_capabilities_display(caps: Dict[str, bool]) -> str:
        """
        构建能力探测结果的可读摘要
        (委托至 shared.sql_utils.build_capabilities_display)

        参数说明：
            - caps: 能力探测结果字典

        返回说明：
            - str: 格式化后的能力摘要
        """
        return build_capabilities_display(caps)

    # ==================== 慢查询分析 ====================

    def analyze_slow_queries(
        self,
        limit: int = 20,
        min_time: float = 1.0
    ) -> Dict[str, Any]:
        """
        分析慢查询（通用实现）

        尝试通过数据库系统视图获取慢查询信息：
        1. pg_stat_statements（PostgreSQL 风格，最详细的统计）
        2. pg_stat_activity（PostgreSQL 风格，当前活跃查询）
        3. INFORMATION_SCHEMA.PROCESSLIST（MySQL/通用风格）
        4. sys.dm_exec_requests（SQL Server 风格）

        参数：
            limit: 返回条数限制
            min_time: 最小执行时间（秒）

        返回：
            Dict: 慢查询分析结果
        """
        caps = self._detect_capabilities()
        queries = []
        source = None

        try:
            # 1. PostgreSQL pg_stat_statements（最佳数据源）
            if caps["pg_stat_statements"]:
                result = self._execute_query(
                    "SELECT queryid, query, calls, "
                    "round(mean_exec_time::numeric, 2), "
                    "round(max_exec_time::numeric, 2) "
                    "FROM pg_stat_statements "
                    "WHERE mean_exec_time >= %s * 1000 "
                    "ORDER BY mean_exec_time DESC "
                    "LIMIT %s",
                    (min_time, limit)
                )
                if result:
                    source = "pg_stat_statements"
                    for row in result:
                        queries.append({
                            "query_id": str(row[0]) if row[0] else None,
                            "query": row[1][:500] if row[1] else None,
                            "calls": row[2],
                            "avg_time_ms": float(row[3]) if row[3] else 0,
                            "max_time_ms": float(row[4]) if row[4] else 0,
                            "source": source
                        })

            # 2. PostgreSQL pg_stat_activity（活跃查询）
            if not queries and caps["pg_stat_activity"]:
                result = self._execute_query(
                    "SELECT pid, LEFT(query, 500), state, "
                    "EXTRACT(EPOCH FROM (now() - query_start))::numeric(10,2) "
                    "FROM pg_stat_activity "
                    "WHERE state = 'active' "
                    "AND query_start IS NOT NULL "
                    "AND EXTRACT(EPOCH FROM (now() - query_start)) >= %s "
                    "ORDER BY query_start "
                    "LIMIT %s",
                    (min_time, limit)
                )
                if result:
                    source = "pg_stat_activity"
                    for row in result:
                        queries.append({
                            "query_id": str(row[0]),
                            "query": row[1],
                            "state": row[2],
                            "exec_time_sec": float(row[3]) if row[3] else 0,
                            "source": source
                        })

            # 3. MySQL PROCESSLIST
            if not queries and caps["information_schema"]:
                result = self._execute_query(
                    "SELECT ID, INFO, COMMAND, TIME "
                    "FROM INFORMATION_SCHEMA.PROCESSLIST "
                    "WHERE COMMAND != 'Sleep' "
                    "AND TIME >= %s "
                    "ORDER BY TIME DESC "
                    "LIMIT %s",
                    (min_time, limit)
                )
                if result:
                    source = "information_schema.processlist"
                    for row in result:
                        queries.append({
                            "query_id": str(row[0]),
                            "query": row[1][:500] if row[1] else None,
                            "command": row[2],
                            "exec_time_sec": row[3],
                            "source": source
                        })

            # 4. SQL Server dm_exec_requests
            if not queries and caps["sys.dm_exec_sessions"]:
                result = self._execute_query(
                    "SELECT session_id, text, status, "
                    "DATEDIFF(second, start_time, GETDATE()) "
                    "FROM sys.dm_exec_requests r "
                    "CROSS APPLY sys.dm_exec_sql_text(r.sql_handle) "
                    "WHERE status = 'running' "
                    "AND DATEDIFF(second, start_time, GETDATE()) >= %s "
                    "ORDER BY start_time "
                    "LIMIT %s",
                    (min_time, limit)
                )
                if result:
                    source = "sys.dm_exec_requests"
                    for row in result:
                        queries.append({
                            "query_id": str(row[0]),
                            "query": row[1][:500] if row[1] else None,
                            "status": row[2],
                            "exec_time_sec": row[3],
                            "source": source
                        })

            if queries:
                return self._create_result(
                    success=True,
                    message=(
                        f"从 {source} 获取到 {len(queries)} 个慢查询/活跃查询"
                    ),
                    data={
                        "total_queries": len(queries),
                        "source": source,
                        "queries": queries,
                        "note": (
                            "该数据库类型使用通用诊断器，"
                            "慢查询分析可能不如专用诊断器完整"
                        )
                    }
                )

            # 没有任何数据源可用
            return self._create_result(
                success=True,
                message=f"{self.dialect} 数据库未找到慢查询或无法获取查询信息",
                data={
                    "total_queries": 0,
                    "queries": [],
                    "note": (
                        "该数据库类型使用通用诊断器。"
                        "未检测到 pg_stat_statements、pg_stat_activity、"
                        "INFORMATION_SCHEMA.PROCESSLIST 或 sys.dm_exec_requests 等视图。"
                        "如需慢查询分析，请确保数据库启用了相关性能监控扩展或视图。"
                    )
                }
            )

        except Exception as e:
            logger.error(f"通用慢查询分析失败: {e}")
            return self._create_result(
                success=False,
                message="通用慢查询分析失败",
                error=str(e),
                data={"total_queries": 0, "queries": []}
            )

    # ==================== 性能指标分析 ====================

    def analyze_performance_metrics(
        self,
        duration_minutes: int = 10
    ) -> Dict[str, Any]:
        """
        分析性能指标（通用实现）

        获取活跃连接数、事务统计、缓存命中率等基础性能指标。

        参数：
            duration_minutes: 采集时长（分钟），通用诊断器忽略此参数

        返回：
            Dict: 性能指标分析结果
        """
        caps = self._detect_capabilities()
        metrics: Dict[str, Any] = {}

        try:
            # 1. 活跃连接数
            connection_count = self._get_connection_count(caps)
            if connection_count is not None:
                metrics["active_connections"] = connection_count

            # 2. 连接状态分布（PostgreSQL 风格）
            if caps["pg_stat_activity"]:
                result = self._execute_query(
                    "SELECT state, COUNT(*) FROM pg_stat_activity "
                    "GROUP BY state"
                )
                if result:
                    metrics["connection_states"] = {
                        row[0]: row[1] for row in result
                    }

            # 3. 数据库事务统计（PostgreSQL 风格）
            if caps["pg_stat_database"]:
                result = self._execute_query(
                    "SELECT xact_commit, xact_rollback, "
                    "blks_read, blks_hit, deadlocks "
                    "FROM pg_stat_database "
                    "WHERE datname = current_database()"
                )
                if result:
                    row = result[0]
                    metrics["transactions_committed"] = row[0]
                    metrics["transactions_rolled_back"] = row[1]
                    metrics["blocks_read"] = row[2]
                    metrics["blocks_hit"] = row[3]
                    metrics["deadlocks"] = row[4]
                    if row[2] + row[3] > 0:
                        metrics["cache_hit_ratio"] = round(
                            row[3] / (row[2] + row[3]) * 100, 2
                        )

            # 4. 数据库大小
            db_size_mb = self._get_database_size_mb(caps)
            if db_size_mb is not None:
                metrics["database_size_mb"] = round(db_size_mb, 2)

            # 5. 表数量
            if caps["information_schema"]:
                result = self._execute_query(
                    "SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES "
                    "WHERE TABLE_TYPE = 'BASE TABLE'"
                )
                if result and result[0][0] is not None:
                    metrics["table_count"] = int(result[0][0])

            # 6. 索引数量
            index_count = self._get_index_count(caps)
            if index_count is not None:
                metrics["index_count"] = index_count

            # 7. 长时间运行的查询（pg_stat_activity）
            if caps["pg_stat_activity"]:
                result = self._execute_query(
                    "SELECT pid, usename, state, "
                    "EXTRACT(EPOCH FROM (now() - query_start))::numeric(10,2), "
                    "LEFT(query, 200) "
                    "FROM pg_stat_activity "
                    "WHERE state = 'active' "
                    "AND query_start < now() - interval '1 minute' "
                    "ORDER BY query_start"
                )
                if result:
                    metrics["long_running_queries"] = [
                        {
                            "pid": row[0],
                            "user": row[1],
                            "state": row[2],
                            "duration_sec": float(row[3]) if row[3] else 0,
                            "query": row[4]
                        }
                        for row in result
                    ]

            return self._create_result(
                success=True,
                message="通用性能指标分析完成",
                data=metrics,
                error=None
            )

        except Exception as e:
            logger.error(f"通用性能指标分析失败: {e}")
            return self._create_result(
                success=False,
                message="通用性能指标分析失败",
                error=str(e),
                data=metrics
            )

    # ==================== 数据库统计 ====================

    def get_database_stats(self) -> Dict[str, Any]:
        """
        获取数据库统计信息（通用实现）

        获取版本、连接数、大小、表数、索引数等基础统计信息。

        返回：
            Dict: 数据库统计信息
        """
        caps = self._detect_capabilities()
        stats = {
            "database_type": self.dialect,
            "timestamp": datetime.now().isoformat(),
            "capabilities_summary": self._build_capabilities_display(caps),
        }

        try:
            # 1. 版本
            version = self._version_cache
            if not version and caps["version_query"]:
                for sql in [
                    "SELECT VERSION()",
                    "SELECT version()",
                    "SELECT @@version",
                    "SELECT sqlite_version()",
                ]:
                    rows = self._execute_query(sql)
                    if rows and len(rows) > 0 and rows[0][0]:
                        version = str(rows[0][0])
                        break
            if version:
                stats["version"] = version

            # 2. 当前数据库名
            for sql in [
                "SELECT current_database()",
                "SELECT DATABASE()",
                "SELECT db_name()",
            ]:
                rows = self._execute_query(sql)
                if rows and len(rows) > 0 and rows[0][0]:
                    stats["database_name"] = str(rows[0][0])
                    break

            # 3. 当前连接数
            connection_count = self._get_connection_count(caps)
            if connection_count is not None:
                stats["current_connections"] = connection_count

            # 4. 数据库大小
            db_size_mb = self._get_database_size_mb(caps)
            if db_size_mb is not None:
                stats["database_size_mb"] = round(db_size_mb, 2)

            # 5. 表数量
            if caps["information_schema"]:
                result = self._execute_query(
                    "SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES "
                    "WHERE TABLE_TYPE = 'BASE TABLE'"
                )
                if result and result[0][0] is not None:
                    stats["table_count"] = int(result[0][0])

            # 6. 索引数量
            index_count = self._get_index_count(caps)
            if index_count is not None:
                stats["index_count"] = index_count

            # 7. 当前用户
            for sql in [
                "SELECT CURRENT_USER",
                "SELECT current_user",
                "SELECT USER()",
                "SELECT SESSION_USER",
            ]:
                rows = self._execute_query(sql)
                if rows and len(rows) > 0 and rows[0][0]:
                    stats["current_user"] = str(rows[0][0])
                    break

            return self._create_result(
                success=True,
                message=f"{self.dialect} 数据库统计信息获取完成",
                data=stats
            )

        except Exception as e:
            logger.error(f"获取数据库统计信息失败: {e}")
            return self._create_result(
                success=False,
                message="获取数据库统计信息失败",
                error=str(e),
                data=stats
            )

    # ==================== 内部辅助方法 ====================

    def _get_connection_count(self, caps: Dict[str, bool]) -> Optional[int]:
        """
        获取活跃连接数

        参数：
            caps: 能力探测结果

        返回：
            Optional[int]: 活跃连接数，不支持返回 None
        """
        # PostgreSQL 风格
        if caps["pg_stat_activity"]:
            rows = self._execute_query(
                "SELECT COUNT(*) FROM pg_stat_activity "
                "WHERE state = 'active'"
            )
            if rows and rows[0][0] is not None:
                return int(rows[0][0])

        # performance_schema
        if caps["performance_schema"]:
            rows = self._execute_query(
                "SELECT COUNT(*) FROM performance_schema.threads "
                "WHERE NAME LIKE '%/connection%'"
            )
            if rows and rows[0][0] is not None:
                return int(rows[0][0])

        # Oracle 风格
        if caps["v$session"]:
            rows = self._execute_query(
                "SELECT COUNT(*) FROM v$session "
                "WHERE STATUS = 'ACTIVE' AND TYPE = 'USER'"
            )
            if rows and rows[0][0] is not None:
                return int(rows[0][0])

        # SQL Server 风格
        if caps["sys.dm_exec_sessions"]:
            rows = self._execute_query(
                "SELECT COUNT(*) FROM sys.dm_exec_sessions "
                "WHERE status = 'running' AND is_user_process = 1"
            )
            if rows and rows[0][0] is not None:
                return int(rows[0][0])

        # INFORMATION_SCHEMA 通用查询
        if caps["information_schema"]:
            queries = [
                "SELECT COUNT(*) FROM INFORMATION_SCHEMA.PROCESSLIST "
                "WHERE COMMAND != 'Sleep'",
                "SELECT COUNT(*) FROM INFORMATION_SCHEMA.SESSION_STATUS "
                "WHERE VARIABLE_NAME = 'THREADS_CONNECTED'",
            ]
            for sql in queries:
                rows = self._execute_query(sql)
                if rows and rows[0][0] is not None:
                    return int(rows[0][0])

        return None

    # ==================== 通用诊断方法（Mock / 未知数据库兼容） ====================

    def get_realtime_connections(self) -> Dict[str, Any]:
        """
        获取实时连接信息（通用降级实现）

        当目标数据库不支持专用会话视图时，返回空结果而非报错。

        返回:
            Dict: 连接统计（所有指标归零）
        """
        from dbskiter.shared.error_handler import create_success_response
        return create_success_response(
            {
                "total": 0,
                "active": 0,
                "idle": 0,
                "max": 0,
                "slow_count": 0,
                "connections": [],
                "note": "通用诊断器：数据库不支持专用会话视图，连接信息不可用",
            },
            "实时连接信息（通用降级）",
        )

    def get_top_sql(
        self, limit: int = 10, threshold: int = 0
    ) -> Dict[str, Any]:
        """
        获取TOP SQL（通用降级实现）

        当目标数据库不支持专用 SQL 统计视图时，返回空结果而非报错。

        参数:
            limit: 返回条数限制
            threshold: 执行时间阈值（秒）

        返回:
            Dict: TOP SQL 列表（空列表）
        """
        from dbskiter.shared.error_handler import create_success_response
        return create_success_response(
            {
                "top_sqls": [],
                "total_count": 0,
                "note": "通用诊断器：数据库不支持专用 SQL 统计视图，TOP SQL 信息不可用",
            },
            "TOP SQL信息（通用降级）",
        )

    def get_lock_waits(self) -> Dict[str, Any]:
        """
        获取锁等待信息（通用降级实现）

        当目标数据库不支持专用锁视图时，返回空结果而非报错。

        返回:
            Dict: 锁等待统计（空结果）
        """
        from dbskiter.shared.error_handler import create_success_response
        return create_success_response(
            {
                "total_locks": 0,
                "waiting_locks": 0,
                "granted_locks": 0,
                "lock_waits": [],
                "deadlocks": [],
                "note": "通用诊断器：数据库不支持专用锁视图，锁信息不可用",
            },
            "锁等待信息（通用降级）",
        )

    def _get_database_size_mb(self, caps: Dict[str, bool]) -> Optional[float]:
        """
        获取数据库大小（MB）

        参数：
            caps: 能力探测结果

        返回：
            Optional[float]: 数据库大小 MB，不支持返回 None
        """
        # PostgreSQL 风格
        if caps["pg_stat_activity"]:
            rows = self._execute_query(
                "SELECT pg_database_size(current_database()) "
                "/ 1024.0 / 1024.0"
            )
            if rows and rows[0][0] is not None:
                return float(rows[0][0])

        # MySQL 风格
        if caps["information_schema"]:
            rows = self._execute_query(
                "SELECT SUM(data_length + index_length) / 1024.0 / 1024.0 "
                "FROM information_schema.tables "
                "WHERE table_schema = DATABASE()"
            )
            if rows and rows[0][0] is not None:
                return float(rows[0][0])

        # SQLite 风格
        if caps["pragma"]:
            try:
                rows = self._execute_query("PRAGMA page_count")
                rows2 = self._execute_query("PRAGMA page_size")
                if (rows and rows[0][0] is not None
                        and rows2 and rows2[0][0] is not None):
                    return (float(rows[0][0]) * float(rows2[0][0])
                            / 1024.0 / 1024.0)
            except Exception:
                pass

        return None

    def _get_index_count(self, caps: Dict[str, bool]) -> Optional[int]:
        """
        获取索引数量

        参数：
            caps: 能力探测结果

        返回：
            Optional[int]: 索引数量，不支持返回 None
        """
        if caps["information_schema"]:
            rows = self._execute_query(
                "SELECT COUNT(*) FROM INFORMATION_SCHEMA.STATISTICS"
            )
            if rows and rows[0][0] is not None:
                return int(rows[0][0])

        if caps["pg_stat_activity"]:
            rows = self._execute_query(
                "SELECT COUNT(*) FROM pg_class WHERE relkind = 'i'"
            )
            if rows and rows[0][0] is not None:
                return int(rows[0][0])

        return None