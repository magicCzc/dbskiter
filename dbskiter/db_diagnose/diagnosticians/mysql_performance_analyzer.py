"""
MySQL性能分析器 - 基于统一性能模型

文件功能：使用统一性能模型分析MySQL数据库性能
主要类：MySQLPerformanceAnalyzer

特性：
    1. 统一接口：遵循PerformanceAnalyzer基类
    2. 生产安全：内置超时、降级机制
    3. 多版本兼容：支持MySQL 5.7/8.0
    4. 权限感知：自动检测可用数据源

作者: Magiczc
创建时间: 2026-04-24
版本: 1.0.0
"""

import logging
from typing import List, Optional, Tuple

from dbskiter.shared.unified_connector import UnifiedConnector
from ..core.performance_model import (
    PerformanceAnalyzer,
    PerformanceMetric,
    SlowQueryInfo,
    MetricCategory,
    get_threshold
)

logger = logging.getLogger(__name__)


class MySQLPerformanceAnalyzer(PerformanceAnalyzer):
    """
    MySQL性能分析器

    使用统一性能模型分析MySQL性能，支持：
    - 多版本MySQL (5.7/8.0)
    - 自动降级（performance_schema -> information_schema -> SHOW STATUS）
    - 生产安全（超时控制、权限检查）
    """

    def __init__(self, connector: UnifiedConnector, timeout: int = 30):
        """
        初始化MySQL性能分析器

        参数:
            connector: 数据库连接器
            timeout: 查询超时时间(秒)
        """
        super().__init__(connector, timeout)
        self._version: Optional[float] = None
        self._has_performance_schema: bool = False
        self._has_sys_schema: bool = False
        self._has_innodb_tables: bool = False
        self._database_name: Optional[str] = None
        self._detect_capabilities()

    def _detect_capabilities(self):
        """检测数据库能力"""
        try:
            # 检测版本
            result = self._execute_with_timeout("SELECT VERSION()", timeout=5)
            if result:
                version_str = str(result[0][0])
                parts = version_str.split('.')
                self._version = float(f"{parts[0]}.{parts[1]}")
                logger.info(f"MySQL版本: {self._version}")

            # 检测performance_schema
            result = self._execute_with_timeout(
                "SELECT COUNT(*) FROM information_schema.schemata WHERE schema_name = 'performance_schema'",
                timeout=5
            )
            self._has_performance_schema = result and result[0][0] > 0
            logger.info(f"performance_schema可用: {self._has_performance_schema}")

            # 检测sys schema (MySQL 5.7+)
            if self._version and self._version >= 5.7:
                result = self._execute_with_timeout(
                    "SELECT COUNT(*) FROM information_schema.schemata WHERE schema_name = 'sys'",
                    timeout=5
                )
                self._has_sys_schema = result and result[0][0] > 0
                logger.info(f"sys schema可用: {self._has_sys_schema}")

            # 检测InnoDB相关表是否存在
            try:
                result = self._execute_with_timeout("""
                    SELECT COUNT(*) FROM information_schema.TABLES
                    WHERE TABLE_SCHEMA = 'information_schema'
                    AND TABLE_NAME IN ('innodb_lock_waits', 'innodb_trx')
                """, timeout=5)
                self._has_innodb_tables = result and result[0][0] >= 2
                logger.info(f"InnoDB表可用: {self._has_innodb_tables}")
            except Exception:
                self._has_innodb_tables = False
                logger.info("InnoDB表检测失败，假设不可用")

        except Exception as e:
            logger.warning(f"能力检测失败: {str(e).split(chr(10))[0][:120]}")

    def collect_metrics(self) -> List[PerformanceMetric]:
        """
        采集MySQL性能指标

        返回:
            性能指标列表
        """
        metrics = []

        # 采集各类指标
        metrics.extend(self._collect_cpu_metrics())
        metrics.extend(self._collect_io_metrics())
        metrics.extend(self._collect_memory_metrics())
        metrics.extend(self._collect_concurrency_metrics())
        metrics.extend(self._collect_lock_metrics())

        return metrics

    def _collect_cpu_metrics(self) -> List[PerformanceMetric]:
        """采集CPU相关指标"""
        metrics = []

        try:
            # 获取活跃会话数
            result_active = self._execute_with_timeout("""
                SELECT COUNT(*) as active
                FROM information_schema.processlist
                WHERE command != 'Sleep'
            """)
            active = result_active[0][0] if result_active else 0

            # 获取总会话数
            if self._has_performance_schema:
                result_total = self._execute_with_timeout("""
                    SELECT VARIABLE_VALUE
                    FROM performance_schema.global_status
                    WHERE VARIABLE_NAME = 'Threads_connected'
                """)
                total = int(result_total[0][0]) if result_total and result_total[0] else 1
            else:
                result_total = self._execute_with_timeout("""
                    SELECT COUNT(*) as total
                    FROM information_schema.processlist
                """)
                total = result_total[0][0] if result_total else 1

            ratio = (active / total) * 100 if total > 0 else 0

            threshold = get_threshold("cpu_time_ratio")
            metrics.append(PerformanceMetric(
                name="active_session_ratio",
                value=ratio,
                unit="%",
                category=MetricCategory.CPU,
                threshold_warning=threshold.get("warning"),
                threshold_critical=threshold.get("critical"),
                source="processlist"
            ))

        except Exception as e:
            logger.warning(f"CPU指标采集失败: {str(e).split(chr(10))[0][:120]}")

        return metrics

    def _collect_io_metrics(self) -> List[PerformanceMetric]:
        """采集IO相关指标"""
        metrics = []

        try:
            if self._has_performance_schema:
                # 获取InnoDB IO相关指标
                # 使用 SHOW GLOBAL STATUS 获取指标（兼容性更好）
                result = self._execute_with_timeout("""
                    SELECT VARIABLE_NAME, VARIABLE_VALUE
                    FROM performance_schema.global_status
                    WHERE VARIABLE_NAME IN (
                        'Innodb_data_reads',
                        'Innodb_data_writes',
                        'Innodb_buffer_pool_reads',
                        'Innodb_buffer_pool_read_requests'
                    )
                """)

                # 转换为字典
                status_dict = {row[0]: row[1] for row in result} if result else {}

                buffer_reads = int(status_dict.get('Innodb_buffer_pool_reads', 0) or 0)
                buffer_requests = int(status_dict.get('Innodb_buffer_pool_read_requests', 0) or 0)

                if buffer_requests > 0:
                    hit_ratio = (1 - buffer_reads / buffer_requests) * 100

                    threshold = get_threshold("buffer_hit_ratio")
                    metrics.append(PerformanceMetric(
                        name="buffer_pool_hit_ratio",
                        value=hit_ratio,
                        unit="%",
                        category=MetricCategory.IO,
                        threshold_warning=threshold.get("warning"),
                        threshold_critical=threshold.get("critical"),
                        higher_is_better=True,  # 命中率越高越好
                        source="innodb_status"
                    ))

        except Exception as e:
            logger.warning(f"IO指标采集失败: {str(e).split(chr(10))[0][:120]}")

        return metrics

    def _collect_memory_metrics(self) -> List[PerformanceMetric]:
        """采集内存相关指标"""
        metrics = []

        try:
            # 获取缓冲池使用率
            if self._has_performance_schema:
                # 使用 WHERE IN 代替子查询（兼容性更好）
                result = self._execute_with_timeout("""
                    SELECT VARIABLE_NAME, VARIABLE_VALUE
                    FROM performance_schema.global_status
                    WHERE VARIABLE_NAME IN (
                        'Innodb_buffer_pool_pages_data',
                        'Innodb_buffer_pool_pages_total'
                    )
                """)

                # 转换为字典
                status_dict = {row[0]: row[1] for row in result} if result else {}
                data_pages = int(status_dict.get('Innodb_buffer_pool_pages_data', 0) or 0)
                total_pages = int(status_dict.get('Innodb_buffer_pool_pages_total', 0) or 0)

                if total_pages > 0:
                    usage_ratio = (data_pages / total_pages) * 100

                    threshold = get_threshold("memory_usage")
                    metrics.append(PerformanceMetric(
                        name="buffer_pool_usage",
                        value=usage_ratio,
                        unit="%",
                        category=MetricCategory.MEMORY,
                        threshold_warning=threshold.get("warning"),
                        threshold_critical=threshold.get("critical"),
                        source="innodb_status"
                    ))

        except Exception as e:
            logger.warning(f"内存指标采集失败: {str(e).split(chr(10))[0][:120]}")

        return metrics

    def _collect_concurrency_metrics(self) -> List[PerformanceMetric]:
        """采集并发相关指标"""
        metrics = []

        try:
            # 获取连接使用率
            # MySQL 5.7+ 使用 performance_schema.global_status
            # 使用 WHERE IN 代替子查询（兼容性更好）
            result = self._execute_with_timeout("""
                SELECT VARIABLE_NAME, VARIABLE_VALUE
                FROM performance_schema.global_status
                WHERE VARIABLE_NAME = 'Threads_connected'
            """)

            connected = int(result[0][1] or 0) if result and result[0] else 0

            # 获取最大连接数
            result_max = self._execute_with_timeout("""
                SELECT VARIABLE_NAME, VARIABLE_VALUE
                FROM performance_schema.global_variables
                WHERE VARIABLE_NAME = 'max_connections'
            """)

            max_conn = int(result_max[0][1] or 0) if result_max and result_max[0] else 1

            if max_conn > 0:
                usage_ratio = (connected / max_conn) * 100

                threshold = get_threshold("connection_usage")
                metrics.append(PerformanceMetric(
                    name="connection_usage",
                    value=usage_ratio,
                    unit="%",
                    category=MetricCategory.CONCURRENCY,
                    threshold_warning=threshold.get("warning"),
                    threshold_critical=threshold.get("critical"),
                    source="connection_status"
                ))

        except Exception as e:
            logger.warning(f"并发指标采集失败: {str(e).split(chr(10))[0][:120]}")

        return metrics

    def _collect_lock_metrics(self) -> List[PerformanceMetric]:
        """采集锁相关指标"""
        metrics = []

        try:
            # 获取锁等待情况
            # 优先使用InnoDB专用表（如果可用）
            if self._has_innodb_tables:
                result = self._execute_with_timeout("""
                    SELECT COUNT(*) FROM information_schema.innodb_lock_waits
                """)
            else:
                # 降级到processlist
                result = self._execute_with_timeout("""
                    SELECT COUNT(*) FROM information_schema.processlist
                    WHERE state LIKE '%lock%'
                """)

            if result:
                lock_waits = result[0][0]

                # 获取总事务数用于计算比例
                if self._has_innodb_tables:
                    result = self._execute_with_timeout("""
                        SELECT COUNT(*) FROM information_schema.innodb_trx
                    """)
                    total_trx = result[0][0] if result else 1
                else:
                    total_trx = 1  # 降级时无法获取准确事务数

                wait_ratio = (lock_waits / total_trx) * 100 if total_trx > 0 else 0

                threshold = get_threshold("lock_wait_ratio")
                metrics.append(PerformanceMetric(
                    name="lock_wait_ratio",
                    value=wait_ratio,
                    unit="%",
                    category=MetricCategory.LOCK,
                    threshold_warning=threshold.get("warning"),
                    threshold_critical=threshold.get("critical"),
                    source="lock_status"
                ))

        except Exception as e:
            logger.warning(f"锁指标采集失败: {str(e).split(chr(10))[0][:120]}")

        return metrics

    def _get_text_column(self) -> str:
        """
        动态检测 performance_schema.events_statements_summary_by_digest 表的文本列名

        不再依赖硬编码的版本号，而是直接查询 information_schema

        返回:
            str: 实际存在的列名（'DIGEST_TEXT' 或 'SQL_TEXT'）
        """
        try:
            # 查询表结构，检测哪个列存在
            result = self._execute_with_timeout("""
                SELECT COLUMN_NAME
                FROM information_schema.COLUMNS
                WHERE TABLE_SCHEMA = 'performance_schema'
                AND TABLE_NAME = 'events_statements_summary_by_digest'
                AND COLUMN_NAME IN ('DIGEST_TEXT', 'SQL_TEXT')
                ORDER BY CASE COLUMN_NAME
                    WHEN 'DIGEST_TEXT' THEN 1
                    WHEN 'SQL_TEXT' THEN 2
                END
                LIMIT 1
            """)

            if result and len(result) > 0:
                column = result[0][0]
                logger.info(f"检测到文本列名: {column}")
                return column

        except Exception as e:
            logger.warning(f"列名检测失败: {str(e).split(chr(10))[0][:120]}")

        # 默认回退到 DIGEST_TEXT（MySQL 5.7+ 标准）
        logger.warning("无法检测列名，默认使用 DIGEST_TEXT")
        return "DIGEST_TEXT"

    def _get_database_name(self) -> Optional[str]:
        """获取当前数据库名称"""
        if self._database_name is None:
            try:
                result = self._execute_with_timeout("SELECT DATABASE()")
                if result and result[0][0]:
                    self._database_name = result[0][0]
                    logger.info(f"检测到当前数据库: {self._database_name}")
                elif self.connector.database:
                    # 如果SELECT DATABASE()返回NULL，使用连接时指定的数据库
                    self._database_name = self.connector.database
                    logger.info(f"使用连接配置的数据库: {self._database_name}")
                else:
                    logger.warning("无法确定数据库名称")
            except Exception as e:
                logger.warning(f"获取数据库名称失败: {str(e).split(chr(10))[0][:120]}")
                # 出错时使用连接配置的数据库
                if self.connector.database:
                    self._database_name = self.connector.database
                    logger.info(f"使用连接配置的数据库: {self._database_name}")
        return self._database_name

    def _is_query_in_database(self, sql_text: str, database: str) -> bool:
        """
        检查SQL查询是否只在指定数据库中执行

        参数:
            sql_text: SQL语句
            database: 数据库名称

        返回:
            bool: 如果SQL只访问指定数据库的表则返回True
        """
        if not sql_text:
            return True

        import re

        # 查找所有数据库引用模式
        # 模式1: `db`.`table`
        pattern1 = r'`(\w+)`\s*\.\s*`(\w+)`'
        matches1 = re.findall(pattern1, sql_text)

        # 模式2: db.table (不带反引号)
        pattern2 = r'(?<![`\w])(\w+)\s*\.\s*`?(\w+)`?(?![\w`])'
        matches2 = re.findall(pattern2, sql_text)

        # 模式3: `db` table (数据库名带反引号，表名不带，用空格分隔，可能是别名)
        pattern3 = r'`(\w+)`\s+`?(\w+)`?(?:\s+(?:AS\s+)?`?\w+`?)?(?:\s*,|\s+FROM|\s+JOIN|\s+INTO|\s+UPDATE|\s+DELETE|\s+WHERE|\s+GROUP|\s+ORDER|\s+LIMIT|\s*;)'
        matches3 = re.findall(pattern3, sql_text, re.IGNORECASE)

        all_matches = matches1 + matches2 + matches3

        if not all_matches:
            # 如果没有显式指定数据库，认为是当前数据库的查询
            return True

        # 检查所有引用的数据库是否都是目标数据库
        for db, table in all_matches:
            if db.upper() != database.upper():
                logger.debug(f"SQL引用了其他数据库: {db}.{table}")
                return False

        return True

    def collect_slow_queries(self, limit: int = 20,
                            min_time_ms: float = 1000) -> List[SlowQueryInfo]:
        """
        采集MySQL慢查询

        参数:
            limit: 返回条数限制
            min_time_ms: 最小执行时间(毫秒)

        返回:
            慢查询列表
        """
        queries = []

        # 获取当前数据库名称
        database = self._get_database_name()

        try:
            # 优先从performance_schema获取
            if self._has_performance_schema:
                # 动态检测列名，不依赖硬编码版本号
                text_column = self._get_text_column()

                # 构建SQL，添加数据库过滤
                sql = f"""
                    SELECT
                        {text_column} as sql_text,
                        DIGEST as sql_id,
                        COUNT_STAR as exec_count,
                        SUM_TIMER_WAIT/1000000000 as total_time_ms,
                        AVG_TIMER_WAIT/1000000000 as avg_time_ms,
                        MAX_TIMER_WAIT/1000000000 as max_time_ms,
                        SUM_ROWS_EXAMINED as rows_examined,
                        SUM_ROWS_SENT as rows_sent,
                        FIRST_SEEN,
                        LAST_SEEN
                    FROM performance_schema.events_statements_summary_by_digest
                    WHERE AVG_TIMER_WAIT/1000000000 >= :min_time_ms
                """
                params = {"min_time_ms": min_time_ms, "limit_val": limit}

                # 添加数据库过滤
                if database:
                    sql += " AND SCHEMA_NAME = :database"
                    params["database"] = database

                sql += " ORDER BY AVG_TIMER_WAIT DESC LIMIT :limit_val"

                result = self._execute_with_timeout(sql, params)

                if result:
                    for row in result:
                        sql_text = row[0] if row[0] else ''

                        # 严格数据库隔离：排除访问其他数据库的查询
                        if database and not self._is_query_in_database(sql_text, database):
                            logger.debug(f"跳过访问其他数据库的查询: {sql_text[:50]}...")
                            continue

                        queries.append(SlowQueryInfo(
                            sql_text=sql_text,
                            sql_id=row[1],
                            execution_count=row[2],
                            total_time_ms=row[3],
                            avg_time_ms=row[4],
                            max_time_ms=row[5],
                            rows_examined=row[6],
                            rows_sent=row[7]
                        ))

            # 降级到processlist
            if not queries:
                sql = """
                    SELECT
                        ID,
                        USER,
                        HOST,
                        DB,
                        COMMAND,
                        TIME,
                        STATE,
                        INFO
                    FROM information_schema.processlist
                    WHERE COMMAND != 'Sleep'
                    AND TIME >= :min_time_sec
                """
                params = {"min_time_sec": min_time_ms / 1000, "limit_val": limit}

                # 添加数据库过滤
                if database:
                    sql += " AND DB = :database"
                    params["database"] = database

                sql += " ORDER BY TIME DESC LIMIT :limit_val"

                result = self._execute_with_timeout(sql, params)

                if result:
                    for row in result:
                        queries.append(SlowQueryInfo(
                            sql_text=row[7] or f"{row[4]} from {row[2]}",
                            sql_id=str(row[0]),
                            execution_count=1,
                            total_time_ms=row[5] * 1000,
                            avg_time_ms=row[5] * 1000,
                            max_time_ms=row[5] * 1000,
                            database=row[3]
                        ))

        except Exception as e:
            logger.error(f"慢查询采集失败: {e}")

        return queries

    def get_active_sessions(self) -> Tuple[int, int]:
        """
        获取MySQL会话信息

        返回:
            (活跃会话数, 总会话数)
        """
        try:
            result = self._execute_with_timeout("""
                SELECT
                    SUM(CASE WHEN command != 'Sleep' THEN 1 ELSE 0 END) as active,
                    COUNT(*) as total
                FROM information_schema.processlist
            """)

            if result:
                return result[0][0] or 0, result[0][1] or 0

        except Exception as e:
            logger.error(f"会话信息采集失败: {e}")

        return 0, 0
