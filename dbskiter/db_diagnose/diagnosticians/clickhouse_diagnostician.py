"""
ClickHouse诊断器

提供ClickHouse数据库的专项诊断能力

文件功能：ClickHouse数据库诊断器实现
主要类：ClickHouseDiagnostician - ClickHouse数据库诊断器

支持的诊断功能：
    - 慢查询分析（system.query_log）
    - 性能指标分析（查询统计、资源使用）
    - 表统计信息分析
    - 分区分析
    - 复制状态分析（Replicated表）
    - 内存使用分析

依赖：
    - clickhouse-driver 或 clickhouse-connect 驱动
    - ClickHouse 20.0+（支持query_log）

作者：Magiczc
创建时间：2026-06-03
版本：1.0.0
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass, field

from dbskiter.shared.unified_connector import UnifiedConnector
from dbskiter.shared.sql_fingerprint import SQLFingerprinter
from .base import BaseDiagnostician

logger = logging.getLogger(__name__)


@dataclass
class ClickHouseSlowQueryRecord:
    """ClickHouse慢查询记录"""
    query_id: str
    query: str
    user: str
    query_duration_ms: float
    read_rows: int
    read_bytes: int
    result_rows: int
    result_bytes: int
    memory_usage: int
    event_time: datetime
    exception: Optional[str] = None


class ClickHouseDiagnostician(BaseDiagnostician):
    """
    ClickHouse数据库诊断器

    提供ClickHouse特有的诊断能力：
    - 慢查询分析（基于system.query_log）
    - 性能指标分析
    - 表统计信息
    - 分区分析
    - 复制状态分析
    - 内存使用分析

    特性：
    - 自动降级：query_log -> 实时查询统计
    - 支持分布式表分析
    - 支持Replicated表复制延迟检测
    """

    def __init__(self, connector: UnifiedConnector):
        """
        初始化ClickHouse诊断器

        参数：
            connector: UnifiedConnector实例
        """
        super().__init__(connector)
        self.fingerprinter = SQLFingerprinter()
        self._database_name = None
        self._has_query_log = None

    def _get_database_name(self) -> Optional[str]:
        """
        获取当前数据库名称

        返回：
            Optional[str]: 数据库名称或None
        """
        if self._database_name is None:
            if hasattr(self.connector, 'database') and self.connector.database:
                self._database_name = self.connector.database
            else:
                try:
                    result = self.connector.execute("SELECT currentDatabase()")
                    if result and result.rows:
                        self._database_name = result.rows[0][0]
                except Exception as e:
                    logger.warning(f"获取数据库名称失败: {e}")
        return self._database_name

    def _check_query_log_available(self) -> bool:
        """
        检查query_log是否可用

        返回：
            bool: query_log是否可用
        """
        if self._has_query_log is None:
            try:
                result = self.connector.execute("""
                    SELECT count()
                    FROM system.tables
                    WHERE database = 'system' AND name = 'query_log'
                """)
                self._has_query_log = result.rows[0][0] > 0 if result else False
            except Exception as e:
                logger.warning(f"检查query_log失败: {e}")
                self._has_query_log = False
        return self._has_query_log

    def analyze_slow_queries(
        self,
        limit: int = 20,
        min_time: float = 1.0
    ) -> Dict[str, Any]:
        """
        分析ClickHouse慢查询

        参数：
            limit: 返回条数限制
            min_time: 最小执行时间（秒）

        返回：
            Dict: 慢查询分析结果
        """
        try:
            if self._check_query_log_available():
                return self._analyze_from_query_log(limit, min_time)
            else:
                return self._analyze_from_processes(limit, min_time)
        except Exception as e:
            logger.error(f"慢查询分析失败: {e}")
            return self._create_result(
                success=False,
                message=f"慢查询分析失败: {str(e)}",
                error=str(e)
            )

    def _analyze_from_query_log(
        self,
        limit: int,
        min_time: float
    ) -> Dict[str, Any]:
        """
        从query_log分析慢查询

        参数：
            limit: 返回条数限制
            min_time: 最小执行时间（秒）

        返回：
            Dict: 慢查询分析结果
        """
        min_ms = int(min_time * 1000)

        try:
            result = self.connector.execute("""
                SELECT
                    query_id,
                    query,
                    user,
                    query_duration_ms,
                    read_rows,
                    read_bytes,
                    result_rows,
                    result_bytes,
                    memory_usage,
                    event_time,
                    exception
                FROM system.query_log
                WHERE type = 'QueryFinish'
                AND query_duration_ms >= %(min_ms)s
                AND event_time >= now() - INTERVAL 24 HOUR
                ORDER BY query_duration_ms DESC
                LIMIT %(limit)s
            """, {"min_ms": min_ms, "limit": limit})

            queries = []
            fingerprints = {}

            for row in result.rows if result else []:
                record = ClickHouseSlowQueryRecord(
                    query_id=row[0],
                    query=row[1],
                    user=row[2],
                    query_duration_ms=float(row[3]),
                    read_rows=int(row[4]) if row[4] else 0,
                    read_bytes=int(row[5]) if row[5] else 0,
                    result_rows=int(row[6]) if row[6] else 0,
                    result_bytes=int(row[7]) if row[7] else 0,
                    memory_usage=int(row[8]) if row[8] else 0,
                    event_time=row[9],
                    exception=row[10]
                )
                queries.append(record)

                # SQL指纹聚合
                fp_result = self.fingerprinter.fingerprint(record.query)
                fp = fp_result.fingerprint if hasattr(fp_result, 'fingerprint') else str(fp_result)

                if fp not in fingerprints:
                    fingerprints[fp] = {
                        "fingerprint": fp,
                        "sql_pattern": record.query[:200],
                        "count": 0,
                        "total_duration_ms": 0.0,
                        "avg_duration_ms": 0.0,
                        "max_duration_ms": 0.0,
                        "total_read_rows": 0,
                        "total_read_bytes": 0
                    }

                fingerprints[fp]["count"] += 1
                fingerprints[fp]["total_duration_ms"] += record.query_duration_ms
                fingerprints[fp]["max_duration_ms"] = max(
                    fingerprints[fp]["max_duration_ms"],
                    record.query_duration_ms
                )
                fingerprints[fp]["total_read_rows"] += record.read_rows
                fingerprints[fp]["total_read_bytes"] += record.read_bytes

            # 计算平均值
            for fp in fingerprints:
                if fingerprints[fp]["count"] > 0:
                    fingerprints[fp]["avg_duration_ms"] = (
                        fingerprints[fp]["total_duration_ms"] / fingerprints[fp]["count"]
                    )

            # 排序
            sorted_patterns = sorted(
                fingerprints.values(),
                key=lambda x: x["total_duration_ms"],
                reverse=True
            )

            # 构建查询列表
            queries_list = []
            for q in queries[:limit]:
                queries_list.append({
                    "query_id": q.query_id,
                    "sql": q.query,
                    "sql_short": q.query[:200] + "..." if len(q.query) > 200 else q.query,
                    "user": q.user,
                    "duration_ms": q.query_duration_ms,
                    "duration_sec": round(q.query_duration_ms / 1000, 3),
                    "read_rows": q.read_rows,
                    "read_bytes": q.read_bytes,
                    "read_bytes_pretty": self._format_bytes(q.read_bytes),
                    "result_rows": q.result_rows,
                    "memory_usage": q.memory_usage,
                    "memory_usage_pretty": self._format_bytes(q.memory_usage),
                    "event_time": q.event_time.isoformat() if q.event_time else None,
                    "has_error": q.exception is not None
                })

            return self._create_result(
                success=True,
                message=f"从query_log获取到 {len(queries)} 条慢查询，聚合为 {len(fingerprints)} 个模式",
                data={
                    "source": "query_log",
                    "total_queries": len(queries),
                    "unique_patterns": len(fingerprints),
                    "patterns": sorted_patterns[:10],
                    "queries": queries_list
                }
            )

        except Exception as e:
            logger.warning(f"从query_log分析失败: {e}，尝试从processes获取")
            return self._analyze_from_processes(limit, min_time)

    def _analyze_from_processes(
        self,
        limit: int,
        min_time: float
    ) -> Dict[str, Any]:
        """
        从processes分析当前运行查询

        参数：
            limit: 返回条数限制
            min_time: 最小执行时间（秒）

        返回：
            Dict: 查询分析结果
        """
        try:
            result = self.connector.execute("""
                SELECT
                    query_id,
                    query,
                    user,
                    elapsed,
                    read_rows,
                    read_bytes,
                    memory_usage
                FROM system.processes
                WHERE query NOT LIKE '%%system.processes%%'
                AND elapsed >= %(min_time)s
                ORDER BY elapsed DESC
                LIMIT %(limit)s
            """, {"min_time": min_time, "limit": limit})

            queries = []
            for row in result.rows if result else []:
                queries.append({
                    "query_id": row[0],
                    "sql": row[1],
                    "sql_short": row[1][:200] + "..." if len(row[1]) > 200 else row[1],
                    "user": row[2],
                    "elapsed_sec": float(row[3]),
                    "read_rows": int(row[4]) if row[4] else 0,
                    "read_bytes": int(row[5]) if row[5] else 0,
                    "memory_usage": int(row[6]) if row[6] else 0,
                    "source": "processes"
                })

            return self._create_result(
                success=True,
                message=f"从processes获取到 {len(queries)} 条运行中查询",
                data={
                    "source": "processes",
                    "total_queries": len(queries),
                    "queries": queries
                }
            )

        except Exception as e:
            return self._create_result(
                success=False,
                message=f"查询分析失败: {str(e)}",
                error=str(e)
            )

    def analyze_performance_metrics(
        self,
        duration_minutes: int = 10
    ) -> Dict[str, Any]:
        """
        分析ClickHouse性能指标

        参数：
            duration_minutes: 采集时长（分钟）

        返回：
            Dict: 性能分析结果
        """
        try:
            metrics = {}

            # 查询统计
            try:
                result = self.connector.execute("""
                    SELECT
                        count(),
                        avg(query_duration_ms),
                        max(query_duration_ms),
                        sum(read_rows),
                        sum(read_bytes)
                    FROM system.query_log
                    WHERE type = 'QueryFinish'
                    AND event_time >= now() - INTERVAL 1 HOUR
                """)
                if result and result.rows:
                    row = result.rows[0]
                    metrics["query_stats"] = {
                        "total_queries_1h": int(row[0]) if row[0] else 0,
                        "avg_duration_ms": float(row[1]) if row[1] else 0,
                        "max_duration_ms": float(row[2]) if row[2] else 0,
                        "total_read_rows": int(row[3]) if row[3] else 0,
                        "total_read_bytes": int(row[4]) if row[4] else 0,
                        "total_read_bytes_pretty": self._format_bytes(int(row[4])) if row[4] else "0 B"
                    }
            except Exception as e:
                logger.warning(f"获取查询统计失败: {e}")
                metrics["query_stats"] = {"error": str(e)}

            # 当前连接数
            try:
                result = self.connector.execute("SELECT count() FROM system.processes")
                metrics["current_connections"] = int(result.rows[0][0]) if result else 0
            except Exception as e:
                logger.warning(f"获取连接数失败: {e}")
                metrics["current_connections"] = -1

            # 内存使用
            try:
                result = self.connector.execute("""
                    SELECT
                        formatReadableSize(sum(memory_usage))
                    FROM system.processes
                """)
                metrics["memory_usage"] = result.rows[0][0] if result and result.rows else "N/A"
            except Exception as e:
                logger.warning(f"获取内存使用失败: {e}")
                metrics["memory_usage"] = "N/A"

            # MergeTree统计
            try:
                result = self.connector.execute("""
                    SELECT
                        count(),
                        sum(total_rows),
                        sum(total_bytes)
                    FROM system.parts
                    WHERE active
                """)
                if result and result.rows:
                    row = result.rows[0]
                    metrics["mergetree_stats"] = {
                        "active_parts": int(row[0]) if row[0] else 0,
                        "total_rows": int(row[1]) if row[1] else 0,
                        "total_bytes": int(row[2]) if row[2] else 0,
                        "total_bytes_pretty": self._format_bytes(int(row[2])) if row[2] else "0 B"
                    }
            except Exception as e:
                logger.warning(f"获取MergeTree统计失败: {e}")
                metrics["mergetree_stats"] = {"error": str(e)}

            return self._create_result(
                success=True,
                message="性能指标采集完成",
                data=metrics
            )

        except Exception as e:
            logger.error(f"性能指标分析失败: {e}")
            return self._create_result(
                success=False,
                message=f"性能指标分析失败: {str(e)}",
                error=str(e)
            )

    def get_database_stats(self) -> Dict[str, Any]:
        """
        获取ClickHouse数据库统计信息

        返回：
            Dict: 数据库统计信息
        """
        try:
            stats = {}

            # 数据库列表
            try:
                result = self.connector.execute("""
                    SELECT
                        name,
                        engine,
                        tables,
                        partitions,
                        parts
                    FROM system.databases
                    WHERE name NOT IN ('system', 'information_schema', 'INFORMATION_SCHEMA')
                """)
                databases = []
                for row in result.rows if result else []:
                    databases.append({
                        "name": row[0],
                        "engine": row[1],
                        "tables": int(row[2]) if row[2] else 0,
                        "partitions": int(row[3]) if row[3] else 0,
                        "parts": int(row[4]) if row[4] else 0
                    })
                stats["databases"] = databases
            except Exception as e:
                logger.warning(f"获取数据库列表失败: {e}")
                stats["databases"] = []

            # 表统计
            try:
                result = self.connector.execute("""
                    SELECT
                        database,
                        table,
                        engine,
                        total_rows,
                        total_bytes,
                        partitions,
                        parts
                    FROM system.tables
                    WHERE database NOT IN ('system', 'information_schema', 'INFORMATION_SCHEMA')
                    AND engine LIKE '%MergeTree%'
                    ORDER BY total_bytes DESC
                    LIMIT 20
                """)
                tables = []
                for row in result.rows if result else []:
                    tables.append({
                        "database": row[0],
                        "table": row[1],
                        "engine": row[2],
                        "total_rows": int(row[3]) if row[3] else 0,
                        "total_bytes": int(row[4]) if row[4] else 0,
                        "total_bytes_pretty": self._format_bytes(int(row[4])) if row[4] else "0 B",
                        "partitions": int(row[5]) if row[5] else 0,
                        "parts": int(row[6]) if row[6] else 0
                    })
                stats["tables"] = tables
            except Exception as e:
                logger.warning(f"获取表统计失败: {e}")
                stats["tables"] = []

            return self._create_result(
                success=True,
                message=f"获取到 {len(stats.get('databases', []))} 个数据库，{len(stats.get('tables', []))} 个表",
                data=stats
            )

        except Exception as e:
            logger.error(f"数据库统计获取失败: {e}")
            return self._create_result(
                success=False,
                message=f"数据库统计获取失败: {str(e)}",
                error=str(e)
            )

    def analyze_partitions(self, database: str = None, table: str = None) -> Dict[str, Any]:
        """
        分析ClickHouse分区情况

        参数：
            database: 数据库名（可选）
            table: 表名（可选）

        返回：
            Dict: 分区分析结果
        """
        try:
            conditions = ["active"]
            if database:
                conditions.append("database = %(database)s")
            if table:
                conditions.append("table = %(table)s")

            where_clause = "WHERE " + " AND ".join(conditions)

            sql = f"""
                SELECT
                    database,
                    table,
                    partition,
                    count() as parts,
                    sum(rows) as rows,
                    sum(bytes_on_disk) as bytes_on_disk,
                    min(min_time) as min_time,
                    max(max_time) as max_time
                FROM system.parts
                {where_clause}
                GROUP BY database, table, partition
                ORDER BY bytes_on_disk DESC
                LIMIT 50
            """

            params = {}
            if database:
                params["database"] = database
            if table:
                params["table"] = table

            result = self.connector.execute(sql, params or None)

            partitions = []
            for row in result.rows if result else []:
                partitions.append({
                    "database": row[0],
                    "table": row[1],
                    "partition": row[2],
                    "parts": int(row[3]) if row[3] else 0,
                    "rows": int(row[4]) if row[4] else 0,
                    "bytes_on_disk": int(row[5]) if row[5] else 0,
                    "bytes_on_disk_pretty": self._format_bytes(int(row[5])) if row[5] else "0 B",
                    "min_time": row[6].isoformat() if row[6] else None,
                    "max_time": row[7].isoformat() if row[7] else None
                })

            return self._create_result(
                success=True,
                message=f"获取到 {len(partitions)} 个分区",
                data={
                    "partitions": partitions,
                    "total_partitions": len(partitions)
                }
            )

        except Exception as e:
            logger.error(f"分区分析失败: {e}")
            return self._create_result(
                success=False,
                message=f"分区分析失败: {str(e)}",
                error=str(e)
            )

    def analyze_replication(self) -> Dict[str, Any]:
        """
        分析ClickHouse复制状态（Replicated表）

        返回：
            Dict: 复制状态分析结果
        """
        try:
            # 检查是否有复制表
            result = self.connector.execute("""
                SELECT count()
                FROM system.tables
                WHERE engine LIKE 'Replicated%'
            """)
            has_replicated = result.rows[0][0] > 0 if result else False

            if not has_replicated:
                return self._create_result(
                    success=True,
                    message="没有Replicated表，无需复制监控",
                    data={"has_replication": False}
                )

            # 获取复制队列状态
            try:
                result = self.connector.execute("""
                    SELECT
                        database,
                        table,
                        replica_name,
                        position,
                        queue_size,
                        inserts_in_queue,
                        merges_in_queue
                    FROM system.replicas
                    ORDER BY queue_size DESC
                """)

                replicas = []
                for row in result.rows if result else []:
                    replicas.append({
                        "database": row[0],
                        "table": row[1],
                        "replica_name": row[2],
                        "position": row[3],
                        "queue_size": int(row[4]) if row[4] else 0,
                        "inserts_in_queue": int(row[5]) if row[5] else 0,
                        "merges_in_queue": int(row[6]) if row[6] else 0
                    })

                return self._create_result(
                    success=True,
                    message=f"获取到 {len(replicas)} 个复制副本",
                    data={
                        "has_replication": True,
                        "replicas": replicas,
                        "total_replicas": len(replicas)
                    }
                )

            except Exception as e:
                logger.warning(f"获取复制状态失败: {e}")
                return self._create_result(
                    success=True,
                    message="复制表存在但无法获取详细状态",
                    data={"has_replication": True, "error": str(e)}
                )

        except Exception as e:
            logger.error(f"复制分析失败: {e}")
            return self._create_result(
                success=False,
                message=f"复制分析失败: {str(e)}",
                error=str(e)
            )

    def analyze_index_usage(self) -> Dict[str, Any]:
        """
        分析ClickHouse索引使用情况

        ClickHouse索引类型:
        - 主键索引(ORDER BY): 稀疏索引，默认生效
        - 跳数索引: minmax, set, ngrambf_v1等
        - 投影(Projections): 预聚合索引

        返回:
            Dict: 索引使用分析结果
        """
        try:
            # 获取所有MergeTree表的索引信息
            result = self.connector.execute("""
                SELECT
                    database,
                    table,
                    name,
                    type,
                    expr,
                    granularity
                FROM system.data_skipping_indices
                WHERE database NOT IN ('system', 'information_schema', 'INFORMATION_SCHEMA')
            """)

            indexes = []
            for row in result.rows if result else []:
                indexes.append({
                    "database": row[0],
                    "table": row[1],
                    "name": row[2],
                    "type": row[3],
                    "expr": row[4],
                    "granularity": int(row[5]) if row[5] else 1
                })

            # 获取没有跳数索引的大表
            missing_indexes = []
            try:
                result = self.connector.execute("""
                    SELECT
                        database,
                        table,
                        engine,
                        total_rows,
                        total_bytes
                    FROM system.tables
                    WHERE database NOT IN ('system', 'information_schema', 'INFORMATION_SCHEMA')
                    AND engine LIKE '%MergeTree%'
                    AND total_rows > 1000000
                    ORDER BY total_rows DESC
                    LIMIT 50
                """)

                for row in result.rows if result else []:
                    db_name = row[0]
                    table_name = row[1]
                    engine = row[2]
                    total_rows = int(row[3]) if row[3] else 0
                    total_bytes = int(row[4]) if row[4] else 0

                    # 检查是否有跳数索引
                    idx_result = self.connector.execute("""
                        SELECT count()
                        FROM system.data_skipping_indices
                        WHERE database = %(db_name)s AND table = %(table_name)s
                    """, {"db_name": db_name, "table_name": table_name})
                    idx_count = int(idx_result.rows[0][0]) if idx_result and idx_result.rows else 0

                    if idx_count == 0:
                        missing_indexes.append({
                            "database": db_name,
                            "table": table_name,
                            "engine": engine,
                            "total_rows": total_rows,
                            "total_bytes": total_bytes,
                            "total_bytes_pretty": self._format_bytes(total_bytes),
                            "issue": "大表缺少跳数索引"
                        })
            except Exception as e:
                logger.warning(f"检测缺少索引的表失败: {e}")

            # 获取主键设计信息
            pk_issues = []
            try:
                result = self.connector.execute("""
                    SELECT
                        database,
                        table,
                        engine,
                        sorting_key,
                        primary_key,
                        partition_key,
                        total_rows
                    FROM system.tables
                    WHERE database NOT IN ('system', 'information_schema', 'INFORMATION_SCHEMA')
                    AND engine LIKE '%MergeTree%'
                    ORDER BY total_rows DESC
                    LIMIT 50
                """)

                for row in result.rows if result else []:
                    db_name = row[0]
                    table_name = row[1]
                    engine = row[2]
                    sorting_key = row[3] or ""
                    primary_key = row[4] or ""
                    partition_key = row[5] or ""
                    total_rows = int(row[6]) if row[6] else 0

                    # 检测缺失主键
                    if not primary_key and total_rows > 1000000:
                        pk_issues.append({
                            "database": db_name,
                            "table": table_name,
                            "engine": engine,
                            "issue": "缺少显式主键",
                            "total_rows": total_rows,
                            "suggestion": f"建议添加主键: ALTER TABLE {table_name} MODIFY ORDER BY (column1, column2)"
                        })

                    # 检测主键字段过多
                    pk_fields = [f.strip() for f in primary_key.split(",") if f.strip()]
                    if len(pk_fields) > 3:
                        pk_issues.append({
                            "database": db_name,
                            "table": table_name,
                            "engine": engine,
                            "issue": f"主键字段过多({len(pk_fields)}个)",
                            "total_rows": total_rows,
                            "suggestion": "建议减少主键字段数量，通常1-3个字段即可"
                        })

                    # 检测缺失分区键
                    if not partition_key and total_rows > 10000000:
                        pk_issues.append({
                            "database": db_name,
                            "table": table_name,
                            "engine": engine,
                            "issue": "大表缺少分区键",
                            "total_rows": total_rows,
                            "suggestion": f"建议添加分区键: PARTITION BY toYYYYMMDD(date_column)"
                        })
            except Exception as e:
                logger.warning(f"检测主键设计问题失败: {e}")

            # 计算健康评分
            health_score = 100
            if missing_indexes:
                health_score -= min(len(missing_indexes) * 5, 30)
            if pk_issues:
                health_score -= min(len(pk_issues) * 3, 20)
            health_score = max(health_score, 0)

            return self._create_result(
                success=True,
                message=f"发现 {len(indexes)} 个跳数索引，{len(missing_indexes)} 个表可能缺少索引，{len(pk_issues)} 个主键设计问题",
                data={
                    "indexes": indexes,
                    "missing_indexes": missing_indexes,
                    "pk_issues": pk_issues,
                    "total_indexes": len(indexes),
                    "missing_count": len(missing_indexes),
                    "pk_issue_count": len(pk_issues),
                    "health_score": health_score,
                    "db_type": "ClickHouse"
                }
            )

        except Exception as e:
            logger.error(f"索引使用分析失败: {e}")
            return self._create_result(
                success=False,
                message=f"索引使用分析失败: {str(e)}",
                error=str(e)
            )
