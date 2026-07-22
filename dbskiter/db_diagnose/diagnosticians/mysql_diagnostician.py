"""
MySQL诊断器

提供MySQL数据库的专项诊断能力
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from dbskiter.shared.unified_connector import UnifiedConnector
from dbskiter.shared.mysql_slow_query_collector import MySQLSlowQueryCollector
from dbskiter.shared.mysql_aas_calculator import MySQLAASCalculator
from dbskiter.shared.sql_fingerprint import SQLFingerprinter
from .base import BaseDiagnostician

logger = logging.getLogger(__name__)


class MySQLDiagnostician(BaseDiagnostician):
    """
    MySQL数据库诊断器

    提供MySQL特有的诊断能力：
    - 慢查询分析
    - AAS分析
    - 性能指标分析
    - 实时连接监控
    - TOP SQL查询
    - 锁等待分析
    - 数据库统计信息
    """

    def __init__(self, connector: UnifiedConnector):
        super().__init__(connector)
        self.slow_query_collector = MySQLSlowQueryCollector(connector)
        self.aas_calculator = MySQLAASCalculator(connector)
        self.fingerprinter = SQLFingerprinter()
        self._database_name = None

    def _get_database_name(self) -> Optional[str]:
        """获取当前数据库名称"""
        if self._database_name is None:
            # 优先使用connector配置的数据库名
            if hasattr(self.connector, 'database') and self.connector.database:
                self._database_name = self.connector.database
                logger.info(f"使用connector配置的数据库: {self._database_name}")
            else:
                # 回退到执行SELECT DATABASE()
                try:
                    result = self.connector.execute("SELECT DATABASE()")
                    if result and result.rows:
                        self._database_name = result.rows[0][0]
                        logger.info(f"通过SELECT DATABASE()获取数据库: {self._database_name}")
                except Exception as e:
                    logger.warning(f"获取数据库名称失败: {e}")
        return self._database_name

    def analyze_slow_queries(
        self,
        limit: int = 20,
        min_time: float = 1.0
    ) -> Dict[str, Any]:
        """
        分析MySQL慢查询

        参数:
            limit: 返回条数限制
            min_time: 最小执行时间（秒）

        返回:
            Dict: 慢查询分析结果
        """
        try:
            # 获取当前数据库名称
            database = self._get_database_name()

            # 采集慢查询（只采集当前数据库的）
            slow_queries = self.slow_query_collector.collect_slow_queries(
                limit=limit,
                min_time=min_time,
                database=database
            )

            if not slow_queries:
                # 获取采集过程中的错误信息
                errors = self.slow_query_collector.get_errors()
                if errors:
                    error_msgs = [f"[{e.category.value}] {e.message}" for e in errors[:3]]
                    message = f"慢查询采集失败: {'; '.join(error_msgs)}"
                else:
                    message = "未采集到慢查询（可能是当前没有慢查询或配置未启用）"

                return self._create_result(
                    success=True,
                    message=message,
                    data={
                        "total_queries": 0,
                        "unique_patterns": 0,
                        "queries": []
                    }
                )

            # SQL指纹聚合
            fingerprints = {}
            for query in slow_queries:
                # SlowQuery 使用 sql 属性，不是 sql_text
                sql_text = getattr(query, 'sql', None) or getattr(query, 'sql_text', '')
                fp_result = self.fingerprinter.fingerprint(sql_text)
                # 使用指纹字符串作为key
                fp = fp_result.fingerprint if hasattr(fp_result, 'fingerprint') else str(fp_result)
                if fp not in fingerprints:
                    fingerprints[fp] = {
                        "fingerprint": fp,
                        "sql_pattern": sql_text[:200] if sql_text else '',
                        "count": 0,
                        "total_time": 0.0,
                        "avg_time": 0.0,
                        "max_time": 0.0
                    }
                fingerprints[fp]["count"] += 1
                fingerprints[fp]["total_time"] += query.query_time
                fingerprints[fp]["max_time"] = max(fingerprints[fp]["max_time"], query.query_time)

            # 计算平均时间
            for fp in fingerprints:
                if fingerprints[fp]["count"] > 0:
                    fingerprints[fp]["avg_time"] = (
                        fingerprints[fp]["total_time"] / fingerprints[fp]["count"]
                    )

            # 排序
            sorted_patterns = sorted(
                fingerprints.values(),
                key=lambda x: x["total_time"],
                reverse=True
            )

            # 构建查询列表（保留完整SQL）
            queries_list = []
            for q in slow_queries[:limit]:
                sql_full = getattr(q, 'sql', None) or getattr(q, 'sql_text', '')
                queries_list.append({
                    "sql": sql_full,
                    "sql_short": sql_full[:200] + "..." if len(sql_full) > 200 else sql_full,
                    "query_time": q.query_time,
                    "lock_time": getattr(q, 'lock_time', 0.0),
                    "rows_examined": q.rows_examined,
                    "rows_sent": q.rows_sent,
                    "timestamp": getattr(q, 'timestamp', None).isoformat() if getattr(q, 'timestamp', None) else None
                })

            return self._create_result(
                success=True,
                message=f"成功分析 {len(slow_queries)} 个慢查询",
                data={
                    "total_queries": len(slow_queries),
                    "unique_patterns": len(fingerprints),
                    "queries": queries_list,
                    "patterns": sorted_patterns[:10]
                }
            )

        except ConnectionError as e:
            logger.error(f"数据库连接失败: {e}")
            return self._create_result(
                success=False,
                message="数据库连接失败",
                error=str(e)
            )
        except PermissionError as e:
            logger.error(f"权限不足: {e}")
            return self._create_result(
                success=False,
                message="权限不足",
                error=str(e)
            )
        except ValueError as e:
            logger.error(f"数据解析错误: {e}")
            return self._create_result(
                success=False,
                message="数据解析错误",
                error=str(e)
            )

    def analyze_index_usage(self) -> Dict[str, Any]:
        """
        分析MySQL索引使用情况

        识别未使用或低效的索引，以及可能缺少索引的表。
        提供详细的索引分析、健康评分和具体的优化建议。

        返回:
            Dict: 索引使用分析结果，包含：
                - unused_indexes: 未使用的索引列表
                - hot_indexes: 高频使用索引列表
                - tables_missing_index: 可能缺少索引的表列表
                - redundant_indexes: 冗余索引列表
                - health_score: 健康评分(0-100)
                - suggestions: 优化建议
                - actionable_commands: 可执行的SQL命令
        """
        try:
            # 检查performance_schema是否启用
            has_performance_schema = False
            try:
                result = self._execute_query("""
                    SELECT COUNT(*) FROM information_schema.tables
                    WHERE table_schema = 'performance_schema'
                    AND table_name = 'table_io_waits_summary_by_index_usage'
                """)
                has_performance_schema = result and result[0][0] > 0
            except Exception:
                pass

            unused_indexes = []
            total_unused_size = 0

            if has_performance_schema:
                # 获取未使用的索引
                result = self._execute_query("""
                    SELECT
                        OBJECT_SCHEMA,
                        OBJECT_NAME,
                        INDEX_NAME,
                        COUNT_FETCH,
                        COUNT_INSERT,
                        COUNT_UPDATE,
                        COUNT_DELETE
                    FROM performance_schema.table_io_waits_summary_by_index_usage
                    WHERE INDEX_NAME IS NOT NULL
                    AND INDEX_NAME != 'PRIMARY'
                    AND COUNT_FETCH = 0
                    AND COUNT_INSERT = 0
                    AND COUNT_UPDATE = 0
                    AND COUNT_DELETE = 0
                    ORDER BY OBJECT_SCHEMA, OBJECT_NAME
                    LIMIT 50
                """)

                for row in result or []:
                    # 获取索引大小
                    size_result = self._execute_query("""
                        SELECT ROUND(SUM(stat_value * @@innodb_page_size) / 1024 / 1024, 2)
                        FROM mysql.innodb_index_stats
                        WHERE database_name = %s
                        AND table_name = %s
                        AND index_name = %s
                        AND stat_name = 'size'
                    """, (row[0], row[1], row[2]))

                    size_mb = size_result[0][0] if size_result and size_result[0][0] else 0
                    total_unused_size += size_mb

                    unused_indexes.append({
                        "schema": row[0],
                        "table": row[1],
                        "index": row[2],
                        "fetches": row[3],
                        "inserts": row[4],
                        "updates": row[5],
                        "deletes": row[6],
                        "size_mb": size_mb,
                        "priority": "high" if size_mb > 10 else "medium"  # >10MB为高优先级
                    })

            # 获取高频使用索引
            hot_indexes = []
            if has_performance_schema:
                result = self._execute_query("""
                    SELECT
                        OBJECT_SCHEMA,
                        OBJECT_NAME,
                        INDEX_NAME,
                        SUM(COUNT_FETCH) as total_fetches,
                        SUM(COUNT_INSERT) as total_inserts,
                        SUM(COUNT_UPDATE) as total_updates,
                        SUM(COUNT_DELETE) as total_deletes
                    FROM performance_schema.table_io_waits_summary_by_index_usage
                    WHERE INDEX_NAME IS NOT NULL
                    AND COUNT_FETCH > 0
                    GROUP BY OBJECT_SCHEMA, OBJECT_NAME, INDEX_NAME
                    ORDER BY total_fetches DESC
                    LIMIT 20
                """)

                for row in result or []:
                    hot_indexes.append({
                        "schema": row[0],
                        "table": row[1],
                        "index": row[2],
                        "fetches": row[3],
                        "inserts": row[4],
                        "updates": row[5],
                        "deletes": row[6]
                    })

            # 获取可能缺少索引的表（全表扫描多）
            tables_missing_index = []
            if has_performance_schema:
                result = self._execute_query("""
                    SELECT
                        OBJECT_SCHEMA,
                        OBJECT_NAME,
                        COUNT_READ,
                        COUNT_WRITE,
                        SUM_TIMER_WAIT
                    FROM performance_schema.table_io_waits_summary_by_table
                    WHERE OBJECT_SCHEMA NOT IN ('mysql', 'information_schema', 'performance_schema', 'sys')
                    AND COUNT_READ > 1000
                    ORDER BY COUNT_READ DESC
                    LIMIT 20
                """)

                for row in result or []:
                    tables_missing_index.append({
                        "schema": row[0],
                        "table": row[1],
                        "reads": row[2],
                        "writes": row[3],
                        "priority": "high" if row[2] > 100000 else "medium"
                    })

            # 检查冗余索引（使用sys schema）
            redundant_indexes = []
            try:
                result = self._execute_query("""
                    SELECT
                        table_schema,
                        table_name,
                        redundant_index_name,
                        redundant_index_columns,
                        dominant_index_name,
                        dominant_index_columns
                    FROM sys.schema_redundant_indexes
                    LIMIT 20
                """)

                for row in result or []:
                    redundant_indexes.append({
                        "schema": row[0],
                        "table": row[1],
                        "redundant_index": row[2],
                        "redundant_columns": row[3],
                        "dominant_index": row[4],
                        "dominant_columns": row[5]
                    })
            except Exception as e:
                logger.warning(f"获取冗余索引失败(可能sys schema不可用): {e}")

            # 计算健康评分
            health_score = self._calculate_mysql_index_health_score(
                unused_indexes, tables_missing_index, redundant_indexes
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
                        "indexes": [f"{idx['table']}.{idx['index']}" for idx in high_priority_unused[:5]]
                    })
                    # 生成删除命令
                    for idx in high_priority_unused[:3]:
                        actionable_commands.append({
                            "priority": "high",
                            "type": "drop_index",
                            "index": f"{idx['schema']}.{idx['table']}.{idx['index']}",
                            "commands": [
                                f"-- 删除未使用的大索引",
                                f"ALTER TABLE {idx['schema']}.{idx['table']} DROP INDEX {idx['index']};",
                            ],
                            "description": f"索引大小 {idx['size_mb']:.2f} MB，从未被使用",
                            "warning": "请先在测试环境验证，确认无影响后再执行"
                        })

                if len(unused_indexes) > len(high_priority_unused):
                    suggestions.append({
                        "type": "info",
                        "message": f"还有 {len(unused_indexes) - len(high_priority_unused)} 个小体积未使用索引",
                        "note": "虽然占用空间不大，但会影响写入性能，建议评估后删除"
                    })

            if tables_missing_index:
                high_priority_missing = [t for t in tables_missing_index if t["priority"] == "high"]
                if high_priority_missing:
                    suggestions.append({
                        "type": "critical",
                        "message": f"发现 {len(high_priority_missing)} 个表可能严重缺少索引",
                        "impact": "大量全表扫描导致查询性能低下",
                        "tables": [f"{t['schema']}.{t['table']}" for t in high_priority_missing[:5]]
                    })
                    for t in high_priority_missing[:3]:
                        actionable_commands.append({
                            "priority": "high",
                            "type": "create_index",
                            "table": f"{t['schema']}.{t['table']}",
                            "commands": [
                                f"-- 为表 {t['schema']}.{t['table']} 创建索引",
                                f"-- 建议步骤:",
                                f"-- 1. 分析慢查询日志，找出常用查询条件",
                                f"-- 2. 使用 EXPLAIN 验证索引效果",
                                f"-- 3. 创建索引 (Online DDL，MySQL 5.6+):",
                                f"-- ALTER TABLE {t['schema']}.{t['table']} ADD INDEX idx_xxx (column_name);",
                            ],
                            "description": f"表有 {t['reads']} 次读取操作，可能缺少索引"
                        })

            if redundant_indexes:
                suggestions.append({
                    "type": "warning",
                    "message": f"发现 {len(redundant_indexes)} 组冗余索引",
                    "note": "冗余索引浪费空间且影响写入性能，建议删除"
                })
                for idx in redundant_indexes[:2]:
                    actionable_commands.append({
                        "priority": "medium",
                        "type": "drop_redundant_index",
                        "table": f"{idx['schema']}.{idx['table']}",
                        "commands": [
                            f"-- 删除冗余索引: {idx['redundant_index']}",
                            f"-- 保留索引: {idx['dominant_index']} (列: {idx['dominant_columns']})",
                            f"ALTER TABLE {idx['schema']}.{idx['table']} DROP INDEX {idx['redundant_index']};",
                        ],
                        "description": f"索引 {idx['redundant_index']} 被 {idx['dominant_index']} 包含"
                    })

            if not has_performance_schema:
                suggestions.append({
                    "type": "info",
                    "message": "performance_schema未启用或不可用，索引使用统计可能不完整",
                    "fix_command": "SET GLOBAL performance_schema = ON; (需要重启MySQL)",
                    "note": "启用后可获得更准确的索引使用统计"
                })

            return self._create_result(
                success=True,
                message=f"索引使用分析完成，健康评分: {health_score}/100",
                data={
                    "unused_indexes": unused_indexes,
                    "hot_indexes": hot_indexes,
                    "tables_missing_index": tables_missing_index,
                    "redundant_indexes": redundant_indexes,
                    "health_score": health_score,
                    "total_unused_index_size_mb": round(total_unused_size, 2),
                    "has_performance_schema": has_performance_schema,
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

    def _calculate_mysql_index_health_score(
        self,
        unused_indexes: List[Dict],
        tables_missing_index: List[Dict],
        redundant_indexes: List[Dict]
    ) -> int:
        """
        计算MySQL索引健康评分

        评分标准:
        - 基础分: 100分
        - 高优先级未使用索引: -10分/个（最多-30分）
        - 高优先级缺少索引: -15分/个（最多-45分）
        - 冗余索引: -5分/组（最多-15分）

        返回:
            int: 健康评分(0-100)
        """
        all_items = unused_indexes + tables_missing_index + redundant_indexes
        rules = [
            {
                "name": "高优先级未使用索引",
                "filter": lambda x: x.get("priority") == "high" and x.get("size_mb") is not None,
                "deduction": 10,
                "max_deduction": 30
            },
            {
                "name": "高优先级缺少索引",
                "filter": lambda x: x.get("priority") == "high" and x.get("reads") is not None,
                "deduction": 15,
                "max_deduction": 45
            },
            {
                "name": "冗余索引",
                "filter": lambda x: x.get("redundant_index") is not None,
                "deduction": 5,
                "max_deduction": 15
            }
        ]
        return self._calculate_health_score(all_items, rules)

    def analyze_table_fragmentation(self) -> Dict[str, Any]:
        """
        分析MySQL表碎片情况

        MySQL InnoDB表在频繁更新删除后会产生碎片，影响性能和空间使用。
        提供详细的碎片分析、健康评分和具体的优化建议。

        返回:
            Dict: 表碎片分析结果，包含：
                - fragmented_tables: 碎片表列表
                - health_score: 健康评分(0-100)
                - total_wasted_space_mb: 总浪费空间(MB)
                - suggestions: 优化建议
                - actionable_commands: 可执行的SQL命令
        """
        try:
            # 获取表碎片信息
            fragmented_tables = []
            total_wasted_space = 0

            result = self._execute_query("""
                SELECT
                    table_schema,
                    table_name,
                    engine,
                    table_rows,
                    data_length,
                    index_length,
                    data_free,
                    ROUND(data_free / (data_length + index_length + data_free) * 100, 2) as frag_ratio
                FROM information_schema.tables
                WHERE table_schema NOT IN ('information_schema', 'performance_schema', 'mysql', 'sys')
                AND engine = 'InnoDB'
                AND data_free > 10485760  -- 大于10MB碎片
                ORDER BY data_free DESC
                LIMIT 30
            """)

            for row in result or []:
                schema = row[0]
                table = row[1]
                engine = row[2]
                table_rows = row[3] or 0
                data_length = row[4] or 0
                index_length = row[5] or 0
                data_free = row[6] or 0
                frag_ratio = row[7] or 0

                total_size = data_length + index_length
                wasted_mb = data_free / (1024 * 1024)
                total_wasted_space += wasted_mb

                # 计算优先级
                if frag_ratio > 50 and wasted_mb > 100:
                    priority = "high"
                elif frag_ratio > 30 or wasted_mb > 50:
                    priority = "medium"
                else:
                    priority = "low"

                fragmented_tables.append({
                    "schema": schema,
                    "table": table,
                    "engine": engine,
                    "rows": table_rows,
                    "data_size_mb": round(data_length / (1024 * 1024), 2),
                    "index_size_mb": round(index_length / (1024 * 1024), 2),
                    "wasted_space_mb": round(wasted_mb, 2),
                    "fragmentation_ratio": frag_ratio,
                    "priority": priority
                })

            # 计算健康评分
            health_score = self._calculate_fragmentation_health_score(fragmented_tables)

            # 生成建议和可执行命令
            suggestions = []
            actionable_commands = []

            if fragmented_tables:
                high_priority = [t for t in fragmented_tables if t["priority"] == "high"]
                if high_priority:
                    wasted = sum(t.get("wasted_space_mb", 0) for t in high_priority)
                    suggestions.append({
                        "type": "critical",
                        "message": f"发现 {len(high_priority)} 个表严重碎片化，需要立即优化",
                        "impact": f"预计可回收 {wasted:.2f} MB 空间",
                        "tables": [f"{t['schema']}.{t['table']}" for t in high_priority[:5]]
                    })
                    # 生成优化命令
                    for t in high_priority[:3]:
                        actionable_commands.append({
                            "priority": "high",
                            "type": "optimize_table",
                            "table": f"{t['schema']}.{t['table']}",
                            "commands": [
                                f"-- 优化表 {t['schema']}.{t['table']}",
                                f"-- 方法1: OPTIMIZE TABLE (会锁表)",
                                f"OPTIMIZE TABLE {t['schema']}.{t['table']};",
                                f"",
                                f"-- 方法2: 使用pt-online-schema-change (在线，推荐)",
                                f"pt-online-schema-change --alter 'ENGINE=InnoDB' --execute D={t['schema']},t={t['table']}",
                            ],
                            "description": f"碎片率 {t['fragmentation_ratio']:.1f}%，浪费 {t['wasted_space_mb']:.2f} MB",
                            "warning": "生产环境建议使用pt-online-schema-change进行在线优化"
                        })

                medium_priority = [t for t in fragmented_tables if t["priority"] == "medium"]
                if medium_priority:
                    suggestions.append({
                        "type": "warning",
                        "message": f"发现 {len(medium_priority)} 个表中度碎片化，建议在维护窗口优化",
                        "tables": [f"{t['schema']}.{t['table']}" for t in medium_priority[:5]]
                    })

            return self._create_result(
                success=True,
                message=f"表碎片分析完成，健康评分: {health_score}/100",
                data={
                    "fragmented_tables": fragmented_tables,
                    "health_score": health_score,
                    "total_wasted_space_mb": round(total_wasted_space, 2),
                    "suggestions": suggestions,
                    "actionable_commands": actionable_commands
                }
            )

        except Exception as e:
            logger.error(f"表碎片分析失败: {e}")
            return self._create_result(
                success=False,
                message="表碎片分析失败",
                error=str(e)
            )

    def _calculate_fragmentation_health_score(self, fragmented_tables: List[Dict]) -> int:
        """
        计算表碎片健康评分

        评分标准:
        - 基础分: 100分
        - 高优先级碎片表: -15分/个（最多-45分）
        - 中优先级碎片表: -8分/个（最多-24分）

        返回:
            int: 健康评分(0-100)
        """
        rules = [
            {
                "name": "高优先级碎片表",
                "filter": lambda x: x.get("priority") == "high",
                "deduction": 15,
                "max_deduction": 45
            },
            {
                "name": "中优先级碎片表",
                "filter": lambda x: x.get("priority") == "medium",
                "deduction": 8,
                "max_deduction": 24
            }
        ]
        return self._calculate_health_score(fragmented_tables, rules)

    def get_realtime_connections(self) -> Dict[str, Any]:
        """
        获取实时连接信息

        返回:
            Dict: 连接统计信息
        """
        try:
            result = self._execute_query("""
                SELECT 
                    COUNT(*) as total,
                    SUM(CASE WHEN COMMAND != 'Sleep' THEN 1 ELSE 0 END) as active,
                    SUM(CASE WHEN TIME > 5 THEN 1 ELSE 0 END) as slow
                FROM information_schema.PROCESSLIST
                WHERE USER != 'system user'
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
                SELECT 
                    ID,
                    USER,
                    HOST,
                    DB,
                    COMMAND,
                    TIME as exec_time,
                    STATE,
                    LEFT(INFO, 500) as sql_text
                FROM information_schema.PROCESSLIST
                WHERE COMMAND != 'Sleep'
                    AND INFO IS NOT NULL
                    AND TIME >= %s
                ORDER BY TIME DESC
                LIMIT %s
            """, (threshold, limit))

            queries = []
            for row in result or []:
                queries.append({
                    "id": row[0],
                    "user": row[1],
                    "host": row[2],
                    "db": row[3],
                    "command": row[4],
                    "exec_time": row[5],
                    "state": row[6],
                    "sql": row[7] if row[7] else ""
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
                    r.trx_id as waiting_trx_id,
                    r.trx_mysql_thread_id as waiting_thread,
                    b.trx_id as blocking_trx_id,
                    b.trx_mysql_thread_id as blocking_thread,
                    b.trx_query as blocking_query
                FROM information_schema.INNODB_LOCK_WAITS w
                JOIN information_schema.INNODB_TRX b ON b.trx_id = w.blocking_trx_id
                JOIN information_schema.INNODB_TRX r ON r.trx_id = w.requesting_trx_id
                LIMIT 10
            """)

            waits = []
            for row in result or []:
                waits.append({
                    "waiting_trx": row[0],
                    "waiting_thread": row[1],
                    "blocking_trx": row[2],
                    "blocking_thread": row[3],
                    "sql": row[4] if row[4] else ""
                })

            return self._create_result(
                success=True,
                message=f"获取到 {len(waits)} 个锁等待",
                data={"lock_waits": waits}
            )
        except Exception as e:
            logger.warning(f"获取锁等待失败(可能INNODB_LOCK_WAITS表不存在): {e}")
            return self._create_result(
                success=True,
                message="锁等待信息获取完成",
                data={"lock_waits": []}
            )

    def analyze_performance_metrics(
        self,
        duration_minutes: int = 10
    ) -> Dict[str, Any]:
        """
        分析MySQL性能指标（AAS）

        参数:
            duration_minutes: 采集时长（分钟）

        返回:
            Dict: AAS分析结果
        """
        try:
            import time

            # 采集AAS指标
            samples = []
            interval_seconds = 10
            total_samples = (duration_minutes * 60) // interval_seconds

            for i in range(total_samples):
                current = self.aas_calculator.calculate_current_aas()
                samples.append(current)
                if i < total_samples - 1:
                    time.sleep(interval_seconds)

            if not samples:
                return self._create_result(
                    success=False,
                    message="未采集到AAS数据",
                    error="采样失败"
                )

            # 计算统计值
            avg_aas = sum(s.total for s in samples) / len(samples)
            max_aas = max(s.total for s in samples)
            avg_cpu = sum(s.cpu for s in samples) / len(samples)
            avg_io = sum(s.io for s in samples) / len(samples)
            avg_lock = sum(s.lock for s in samples) / len(samples)

            # 识别瓶颈
            bottleneck = self.aas_calculator.identify_bottleneck()

            return self._create_result(
                success=True,
                message=f"成功采集 {len(samples)} 个AAS样本",
                data={
                    "aas_average": round(avg_aas, 2),
                    "aas_max": round(max_aas, 2),
                    "cpu_average": round(avg_cpu, 2),
                    "io_average": round(avg_io, 2),
                    "lock_average": round(avg_lock, 2),
                    "bottleneck": bottleneck,
                    "sample_count": len(samples),
                    "duration_minutes": duration_minutes
                }
            )

        except ConnectionError as e:
            logger.error(f"数据库连接失败: {e}")
            return self._create_result(
                success=False,
                message="数据库连接失败",
                error=str(e)
            )
        except PermissionError as e:
            logger.error(f"权限不足: {e}")
            return self._create_result(
                success=False,
                message="权限不足",
                error=str(e)
            )
        except TimeoutError as e:
            logger.error(f"采集超时: {e}")
            return self._create_result(
                success=False,
                message="采集超时",
                error=str(e)
            )

    def get_database_stats(self) -> Dict[str, Any]:
        """
        获取MySQL数据库统计信息

        返回:
            Dict: 数据库统计信息
        """
        try:
            stats = {
                "database_type": "MySQL",
                "timestamp": datetime.now().isoformat()
            }

            # 获取版本
            result = self._execute_query("SELECT VERSION()")
            if result:
                stats["version"] = result[0][0]

            # 获取连接数
            result = self._execute_query(
                "SELECT COUNT(*) FROM information_schema.processlist"
            )
            if result:
                stats["current_connections"] = result[0][0]

            # 获取最大连接数
            result = self._execute_query(
                "SHOW VARIABLES LIKE 'max_connections'"
            )
            if result:
                stats["max_connections"] = int(result[0][1])

            # 获取数据库大小
            result = self._execute_query("""
                SELECT ROUND(SUM(data_length + index_length) / 1024 / 1024 / 1024, 2)
                FROM information_schema.tables
                WHERE table_schema NOT IN ('information_schema', 'performance_schema', 'mysql', 'sys')
            """)
            if result:
                stats["total_size_gb"] = result[0][0] or 0

            # 获取表数量
            result = self._execute_query("""
                SELECT COUNT(*) FROM information_schema.tables
                WHERE table_schema NOT IN ('information_schema', 'performance_schema', 'mysql', 'sys')
            """)
            if result:
                stats["table_count"] = result[0][0]

            # 获取QPS（Questions / Uptime）
            # 使用 WHERE IN 代替子查询（兼容性更好）
            result = self._execute_query("""
                SELECT VARIABLE_NAME, VARIABLE_VALUE
                FROM performance_schema.global_status
                WHERE VARIABLE_NAME IN ('Questions', 'Uptime')
            """)

            # 转换为字典
            status_dict = {row[0]: row[1] for row in result} if result else {}
            questions = int(status_dict.get('Questions', 0) or 0)
            uptime = int(status_dict.get('Uptime', 0) or 0)

            if uptime > 0:
                qps = questions / uptime
                stats["qps"] = round(qps, 2)

            return self._create_result(
                success=True,
                message="成功获取数据库统计信息",
                data=stats
            )

        except ConnectionError as e:
            logger.error(f"数据库连接失败: {e}")
            return self._create_result(
                success=False,
                message="数据库连接失败",
                error=str(e)
            )
        except PermissionError as e:
            logger.error(f"权限不足: {e}")
            return self._create_result(
                success=False,
                message="权限不足",
                error=str(e)
            )
        except ValueError as e:
            logger.error(f"数据解析错误: {e}")
            return self._create_result(
                success=False,
                message="数据解析错误",
                error=str(e)
            )
