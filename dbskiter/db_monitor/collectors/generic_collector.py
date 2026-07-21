"""
Generic 通用指标采集器

文件功能：为任意 JDBC 兼容数据库提供基础指标采集能力
主要类：GenericMetricsCollector - 通用指标采集器

设计思路：
    借鉴 DBeaver Generic Driver 模式，通过标准 JDBC API 和
    INFORMATION_SCHEMA 获取基础元数据和性能指标，无需为每个
    数据库编写定制采集器。

支持的数据库（理论上所有 JDBC 兼容数据库）：
    - Trino / Presto
    - DuckDB
    - Apache Derby
    - H2
    - HSQLDB
    - MariaDB（复用 MySQL 采集器）
    - 任何支持 JDBC 4.0+ 的数据库

采集指标：
    - 连接状态：活跃连接数（通过连接池或会话查询）
    - 元数据：表数量、索引数量、schema 数量
    - 存储：数据库大小（如果支持）
    - 基础性能：事务状态、锁等待（如果支持标准视图）

使用示例：
    >>> from dbskiter.db_monitor.collectors import get_collector
    >>> collector = get_collector('generic', connector)
    >>> metrics = collector.collect_all_metrics()

版本: 1.0.0
作者: Magiczc
创建时间: 2026-06-05
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from .base import BaseMetricsCollector, MetricType, MetricPoint, MetricQuery
from dbskiter.shared.unified_connector import UnifiedConnector

logger = logging.getLogger(__name__)


class GenericMetricsCollector(BaseMetricsCollector):
    """
    通用指标采集器

    通过标准 SQL 和 JDBC DatabaseMetaData 获取基础指标，
    适用于任何支持标准 JDBC API 的数据库。

    特性：
        - 自动探测数据库能力（支持哪些系统视图）
        - 优雅降级：不支持的功能返回 None 而不是报错
        - 元数据缓存：避免重复查询 catalog
    """

    def __init__(self, connector: UnifiedConnector):
        """
        初始化通用采集器

        参数：
            connector: UnifiedConnector 实例
        """
        super().__init__(connector)
        self._capabilities: Optional[Dict[str, bool]] = None
        self._metadata_cache: Optional[Dict[str, Any]] = None

    def _detect_capabilities(self) -> Dict[str, bool]:
        """
        探测目标数据库支持的功能

        通过尝试查询各类系统视图，确定数据库支持哪些指标采集。
        结果会缓存，避免重复探测。

        返回：
            Dict[str, bool]: 功能支持状态映射
                - information_schema: 是否支持 INFORMATION_SCHEMA
                - pg_stat_activity: 是否支持 PostgreSQL 风格会话视图
                - performance_schema: 是否支持 MySQL 风格性能视图
                - v$session: 是否支持 Oracle 风格会话视图
                - sys.dm_exec_sessions: 是否支持 SQL Server 风格视图
                - pragma: 是否支持 SQLite PRAGMA
        """
        if self._capabilities is not None:
            return self._capabilities

        capabilities = {
            "information_schema": False,
            "pg_stat_activity": False,
            "performance_schema": False,
            "v$session": False,
            "sys.dm_exec_sessions": False,
            "pragma": False,
        }

        # 测试 INFORMATION_SCHEMA
        try:
            result = self.connector.execute(
                "SELECT 1 FROM INFORMATION_SCHEMA.TABLES LIMIT 1"
            )
            if result and result.rows:
                capabilities["information_schema"] = True
                logger.info("数据库支持 INFORMATION_SCHEMA")
        except Exception:
            pass

        # 测试 PostgreSQL 风格
        try:
            result = self.connector.execute(
                "SELECT 1 FROM pg_stat_activity LIMIT 0"
            )
            capabilities["pg_stat_activity"] = True
            logger.info("数据库支持 pg_stat_activity")
        except Exception:
            pass

        # 测试 MySQL 风格 performance_schema
        try:
            result = self.connector.execute(
                "SELECT 1 FROM performance_schema.threads LIMIT 0"
            )
            capabilities["performance_schema"] = True
            logger.info("数据库支持 performance_schema")
        except Exception:
            pass

        # 测试 Oracle 风格
        try:
            result = self.connector.execute("SELECT 1 FROM v$session WHERE ROWNUM = 0")
            capabilities["v$session"] = True
            logger.info("数据库支持 v$session")
        except Exception:
            pass

        # 测试 SQL Server 风格
        try:
            result = self.connector.execute(
                "SELECT 1 FROM sys.dm_exec_sessions WHERE 1=0"
            )
            capabilities["sys.dm_exec_sessions"] = True
            logger.info("数据库支持 sys.dm_exec_sessions")
        except Exception:
            pass

        # 测试 PRAGMA（SQLite 风格）
        try:
            result = self.connector.execute("PRAGMA page_count")
            if result and result.rows:
                capabilities["pragma"] = True
                logger.info("数据库支持 PRAGMA")
        except Exception:
            pass

        self._capabilities = capabilities
        logger.info(f"数据库能力探测完成: {capabilities}")
        return capabilities

    def _get_connection_count(self) -> Optional[float]:
        """
        获取活跃连接数

        根据数据库能力选择最合适的查询方式。

        返回：
            Optional[float]: 活跃连接数，不支持返回 None
        """
        caps = self._detect_capabilities()

        # 优先使用 pg_stat_activity（PostgreSQL 及兼容数据库）
        if caps["pg_stat_activity"]:
            try:
                result = self.connector.execute(
                    "SELECT COUNT(*) FROM pg_stat_activity WHERE state = 'active'"
                )
                if result and result.rows:
                    return float(result.rows[0][0])
            except Exception as e:
                logger.debug(f"pg_stat_activity 查询失败: {e}")

        # 尝试 performance_schema（MySQL 及兼容数据库）
        if caps["performance_schema"]:
            try:
                result = self.connector.execute(
                    "SELECT COUNT(*) FROM performance_schema.threads WHERE NAME LIKE '%/connection%'"
                )
                if result and result.rows:
                    return float(result.rows[0][0])
            except Exception as e:
                logger.debug(f"performance_schema 查询失败: {e}")

        # 尝试 v$session（Oracle）
        if caps["v$session"]:
            try:
                result = self.connector.execute(
                    "SELECT COUNT(*) FROM v$session WHERE STATUS = 'ACTIVE' AND TYPE = 'USER'"
                )
                if result and result.rows:
                    return float(result.rows[0][0])
            except Exception as e:
                logger.debug(f"v$session 查询失败: {e}")

        # 尝试 sys.dm_exec_sessions（SQL Server）
        if caps["sys.dm_exec_sessions"]:
            try:
                result = self.connector.execute(
                    "SELECT COUNT(*) FROM sys.dm_exec_sessions WHERE status = 'running' AND is_user_process = 1"
                )
                if result and result.rows:
                    return float(result.rows[0][0])
            except Exception as e:
                logger.debug(f"sys.dm_exec_sessions 查询失败: {e}")

        # 尝试 INFORMATION_SCHEMA（通用）
        if caps["information_schema"]:
            # 某些数据库在 INFORMATION_SCHEMA 中有 PROCESSLIST 或 SESSIONS
            queries = [
                "SELECT COUNT(*) FROM INFORMATION_SCHEMA.PROCESSLIST WHERE COMMAND != 'Sleep'",
                "SELECT COUNT(*) FROM INFORMATION_SCHEMA.SESSION_STATUS WHERE VARIABLE_NAME = 'THREADS_CONNECTED'",
            ]
            for sql in queries:
                try:
                    result = self.connector.execute(sql)
                    if result and result.rows:
                        return float(result.rows[0][0])
                except Exception:
                    continue

        logger.warning("当前数据库不支持连接数查询")
        return None

    def _get_table_count(self) -> Optional[float]:
        """
        获取表数量

        返回：
            Optional[float]: 表数量，不支持返回 None
        """
        caps = self._detect_capabilities()

        if caps["information_schema"]:
            try:
                result = self.connector.execute(
                    "SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_TYPE = 'BASE TABLE'"
                )
                if result and result.rows:
                    return float(result.rows[0][0])
            except Exception as e:
                logger.debug(f"INFORMATION_SCHEMA 表数量查询失败: {e}")

        # 尝试 pg_class（PostgreSQL）
        if caps["pg_stat_activity"]:
            try:
                result = self.connector.execute(
                    "SELECT COUNT(*) FROM pg_class WHERE relkind = 'r'"
                )
                if result and result.rows:
                    return float(result.rows[0][0])
            except Exception as e:
                logger.debug(f"pg_class 查询失败: {e}")

        logger.warning("当前数据库不支持表数量查询")
        return None

    def _get_index_count(self) -> Optional[float]:
        """
        获取索引数量

        返回：
            Optional[float]: 索引数量，不支持返回 None
        """
        caps = self._detect_capabilities()

        if caps["information_schema"]:
            try:
                result = self.connector.execute(
                    "SELECT COUNT(*) FROM INFORMATION_SCHEMA.STATISTICS"
                )
                if result and result.rows:
                    return float(result.rows[0][0])
            except Exception as e:
                logger.debug(f"INFORMATION_SCHEMA 索引查询失败: {e}")

        # 尝试 pg_class（PostgreSQL）
        if caps["pg_stat_activity"]:
            try:
                result = self.connector.execute(
                    "SELECT COUNT(*) FROM pg_class WHERE relkind = 'i'"
                )
                if result and result.rows:
                    return float(result.rows[0][0])
            except Exception as e:
                logger.debug(f"pg_class 索引查询失败: {e}")

        logger.warning("当前数据库不支持索引数量查询")
        return None

    def _get_database_size(self) -> Optional[float]:
        """
        获取数据库大小（MB）

        返回：
            Optional[float]: 数据库大小 MB，不支持返回 None
        """
        caps = self._detect_capabilities()

        # PostgreSQL
        if caps["pg_stat_activity"]:
            try:
                result = self.connector.execute(
                    "SELECT pg_database_size(current_database()) / 1024.0 / 1024.0"
                )
                if result and result.rows:
                    return float(result.rows[0][0])
            except Exception as e:
                logger.debug(f"pg_database_size 查询失败: {e}")

        # MySQL
        if caps["performance_schema"]:
            try:
                result = self.connector.execute(
                    "SELECT SUM(data_length + index_length) / 1024.0 / 1024.0 "
                    "FROM information_schema.tables WHERE table_schema = DATABASE()"
                )
                if result and result.rows:
                    return float(result.rows[0][0])
            except Exception as e:
                logger.debug(f"MySQL 数据库大小查询失败: {e}")

        # SQLite
        if caps["pragma"]:
            try:
                result = self.connector.execute(
                    "SELECT page_count * page_size / 1024.0 / 1024.0 FROM pragma_page_count(), pragma_page_size()"
                )
                if result and result.rows:
                    return float(result.rows[0][0])
            except Exception:
                # 某些 SQLite 版本不支持上述语法，尝试分开查询
                try:
                    page_count = self.connector.execute("PRAGMA page_count")
                    page_size = self.connector.execute("PRAGMA page_size")
                    if page_count and page_count.rows and page_size and page_size.rows:
                        return float(page_count.rows[0][0]) * float(page_size.rows[0][0]) / 1024.0 / 1024.0
                except Exception as e2:
                    logger.debug(f"SQLite 数据库大小查询失败: {e2}")

        logger.warning("当前数据库不支持数据库大小查询")
        return None

    def get_metric_queries(self) -> Dict[MetricType, MetricQuery]:
        """
        获取通用指标查询定义

        注意：通用采集器不使用静态查询定义，
        而是在 collect_all_metrics 中动态探测和执行。

        返回：
            Dict[MetricType, MetricQuery]: 空字典
        """
        return {}

    def collect_all_metrics(self) -> List[MetricPoint]:
        """
        采集所有支持的通用指标

        根据数据库能力动态选择可采集的指标，
        不支持的指标会被跳过而不是报错。

        返回：
            List[MetricPoint]: 成功采集的指标列表
        """
        metrics = []
        timestamp = datetime.now()

        # 探测数据库能力
        caps = self._detect_capabilities()
        logger.info(f"开始通用采集，数据库能力: {caps}")
        try:
            from dbskiter.shared.sql_utils import build_capabilities_display
            logger.info(build_capabilities_display(caps))
        except ImportError:
            pass

        # 采集连接数
        connections = self._get_connection_count()
        if connections is not None:
            metrics.append(MetricPoint(
                timestamp=timestamp,
                metric_type=MetricType.CONNECTIONS_ACTIVE,
                value=connections,
                unit="count",
                source="generic",
                tags={"method": "auto_detect"}
            ))

        # 采集表数量
        table_count = self._get_table_count()
        if table_count is not None:
            metrics.append(MetricPoint(
                timestamp=timestamp,
                metric_type=MetricType.CONNECTIONS_TOTAL,  # 复用作为对象数量指标
                value=table_count,
                unit="count",
                source="generic",
                tags={"method": "information_schema", "object_type": "table"}
            ))

        # 采集索引数量
        index_count = self._get_index_count()
        if index_count is not None:
            metrics.append(MetricPoint(
                timestamp=timestamp,
                metric_type=MetricType.CONNECTIONS_TOTAL,
                value=index_count,
                unit="count",
                source="generic",
                tags={"method": "information_schema", "object_type": "index"}
            ))

        # 采集数据库大小
        db_size = self._get_database_size()
        if db_size is not None:
            metrics.append(MetricPoint(
                timestamp=timestamp,
                metric_type=MetricType.DISK_USAGE,
                value=db_size,
                unit="MB",
                source="generic",
                tags={"method": "auto_detect"}
            ))

        logger.info(f"通用采集完成，成功采集 {len(metrics)} 个指标")
        return metrics

    def collect_metric(self, metric_type: MetricType) -> Optional[MetricPoint]:
        """
        采集单个指标

        参数：
            metric_type: 指标类型

        返回：
            Optional[MetricPoint]: 指标数据点，不支持返回 None
        """
        timestamp = datetime.now()

        if metric_type == MetricType.CONNECTIONS_ACTIVE:
            value = self._get_connection_count()
            if value is not None:
                return MetricPoint(
                    timestamp=timestamp,
                    metric_type=metric_type,
                    value=value,
                    unit="count",
                    source="generic"
                )

        elif metric_type == MetricType.DISK_USAGE:
            value = self._get_database_size()
            if value is not None:
                return MetricPoint(
                    timestamp=timestamp,
                    metric_type=metric_type,
                    value=value,
                    unit="MB",
                    source="generic"
                )

        logger.warning(f"通用采集器不支持指标类型: {metric_type.value}")
        return None
