"""
通用数据库巡检器

为任意 JDBC 兼容数据库提供基础巡检能力。
借鉴 GenericMetricsCollector 的能力探测模式，通过标准 SQL 和
INFORMATION_SCHEMA 获取基础元数据，生成有实际意义的巡检结果。

功能特性：
    - 自动探测数据库能力（支持哪些系统视图）
    - 优雅降级：不支持的功能返回 INFO 级别的提示而非 skip
    - 元数据缓存：避免重复查询系统视图
    - 与 db_monitor 的 GenericMetricsCollector 共享能力探测逻辑

支持的数据库（理论上所有 JDBC 兼容数据库）：
    - Trino / Presto
    - DuckDB
    - Apache Derby
    - H2
    - HSQLDB
    - 任何支持 JDBC 4.0+ 和 INFORMATION_SCHEMA 的数据库

使用示例：
    >>> from dbskiter.db_inspector.inspectors import get_inspector
    >>> inspector = get_inspector('trino', connector)
    >>> items = inspector.inspect_configuration()
    >>> items = inspector.inspect_storage()

版本: 1.0.0
作者: Magiczc
创建时间: 2026-06-05
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

from dbskiter.shared.unified_connector import UnifiedConnector
from .base import BaseInspector
from ..models import InspectionItem, InspectionType, RiskLevel

logger = logging.getLogger(__name__)


class GenericInspector(BaseInspector):
    """
    通用数据库巡检器

    通过标准 SQL 和 INFORMATION_SCHEMA 获取基础巡检指标，
    适用于任何支持标准 JDBC API 的数据库。当某个功能不支持时，
    返回 INFO 级别的提示而非直接 skip，确保巡检报告有参考价值。

    属性：
        connector: UnifiedConnector 实例
        dialect: 数据库方言
        _capabilities: 能力探测结果缓存
    """

    def __init__(self, connector: UnifiedConnector):
        """
        初始化通用巡检器

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

        通过尝试查询各类系统视图，确定数据库支持哪些巡检指标采集。
        结果会缓存，避免重复探测。逻辑与 GenericMetricsCollector
        保持一致，确保整个系统的能力探测结果统一。

        返回：
            Dict[str, bool]: 功能支持状态映射
                - information_schema: 是否支持 INFORMATION_SCHEMA
                - pg_stat_activity: 是否支持 PostgreSQL 风格会话视图
                - performance_schema: 是否支持 MySQL 风格性能视图
                - v$session: 是否支持 Oracle 风格会话视图
                - sys.dm_exec_sessions: 是否支持 SQL Server 风格视图
                - pragma: 是否支持 SQLite PRAGMA
                - version_query: 是否支持版本查询
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
            "version_query": False,
        }

        # 测试 INFORMATION_SCHEMA
        rows = self._execute_query(
            "SELECT 1 FROM INFORMATION_SCHEMA.TABLES LIMIT 1"
        )
        if rows:
            capabilities["information_schema"] = True
            logger.info("数据库支持 INFORMATION_SCHEMA")

        # 测试 PostgreSQL 风格
        rows = self._execute_query(
            "SELECT 1 FROM pg_stat_activity LIMIT 0"
        )
        if rows is not None:
            capabilities["pg_stat_activity"] = True
            logger.info("数据库支持 pg_stat_activity")

        # 测试 MySQL 风格 performance_schema
        rows = self._execute_query(
            "SELECT 1 FROM performance_schema.threads LIMIT 0"
        )
        if rows is not None:
            capabilities["performance_schema"] = True
            logger.info("数据库支持 performance_schema")

        # 测试 Oracle 风格
        rows = self._execute_query(
            "SELECT 1 FROM v$session WHERE ROWNUM = 0"
        )
        if rows is not None:
            capabilities["v$session"] = True
            logger.info("数据库支持 v$session")

        # 测试 SQL Server 风格
        rows = self._execute_query(
            "SELECT 1 FROM sys.dm_exec_sessions WHERE 1=0"
        )
        if rows is not None:
            capabilities["sys.dm_exec_sessions"] = True
            logger.info("数据库支持 sys.dm_exec_sessions")

        # 测试 PRAGMA（SQLite 风格）
        rows = self._execute_query("PRAGMA page_count")
        if rows and len(rows) > 0:
            capabilities["pragma"] = True
            logger.info("数据库支持 PRAGMA")

        # 测试版本查询
        for sql in ["SELECT VERSION()", "SELECT version()", "SELECT @@version"]:
            rows = self._execute_query(sql)
            if rows and len(rows) > 0 and rows[0][0]:
                capabilities["version_query"] = True
                self._version_cache = str(rows[0][0])
                break

        self._capabilities = capabilities
        logger.info(f"数据库能力探测完成: {capabilities}")
        return capabilities

    # ==================== 基本信息 ====================

    def get_instance_info(self) -> Dict[str, Any]:
        """
        获取实例基本信息（增强版）

        通过能力探测获取数据库版本等信息，而非返回固定值。

        返回：
            Dict[str, Any]: 实例信息字典
        """
        info = super().get_instance_info()
        caps = self._detect_capabilities()

        # 使用能力探测时缓存的版本信息
        if caps["version_query"] and self._version_cache:
            info["version"] = self._version_cache

        # 记录能力探测结果到实例信息
        info["capabilities"] = caps
        return info

    # ==================== 配置检查 ====================

    def inspect_configuration(self) -> List[InspectionItem]:
        """
        检查数据库配置（通用实现）

        通过 INFORMATION_SCHEMA 等标准视图获取数据库基本信息，
        检查数据库类型、版本、schema 数量等元数据信息。

        返回：
            List[InspectionItem]: 配置检查项列表
        """
        items = []
        caps = self._detect_capabilities()

        # 1. 数据库类型和版本（使用能力探测缓存的版本信息）
        version = self._version_cache if self._version_cache else "未知"

        items.append(self._create_item(
            name="数据库类型与版本",
            insp_type=InspectionType.CONFIGURATION,
            risk_level=RiskLevel.INFO if "未知" not in version else RiskLevel.MEDIUM,
            status="pass" if "未知" not in version else "warning",
            description=f"数据库类型: {self.dialect}, 版本: {version}",
            actual_value=version,
            suggestion=None if "未知" not in version else "无法获取数据库版本信息，请检查连接配置"
        ))

        # 2. 数据库/schema 数量
        schema_count = None
        if caps["information_schema"]:
            rows = self._execute_query(
                "SELECT COUNT(DISTINCT TABLE_SCHEMA) FROM INFORMATION_SCHEMA.TABLES"
            )
            if rows and rows[0][0] is not None:
                schema_count = int(rows[0][0])

        if schema_count is not None:
            items.append(self._create_item(
                name="Schema 数量",
                insp_type=InspectionType.CONFIGURATION,
                risk_level=RiskLevel.INFO,
                status="pass",
                description=f"当前数据库共有 {schema_count} 个 Schema",
                actual_value=str(schema_count)
            ))
        else:
            items.append(self._create_item(
                name="Schema 数量",
                insp_type=InspectionType.CONFIGURATION,
                risk_level=RiskLevel.INFO,
                status="warning",
                description=f"数据库 {self.dialect} 不支持通过标准视图查询 Schema 数量",
                suggestion="部分数据库无 Schema 概念（如 MySQL 将 Schema 等同于 Database）"
            ))

        # 3. 表总数
        table_count = None
        if caps["information_schema"]:
            rows = self._execute_query(
                "SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_TYPE = 'BASE TABLE'"
            )
            if rows and rows[0][0] is not None:
                table_count = int(rows[0][0])

        if table_count is not None:
            status = "pass"
            risk = RiskLevel.INFO
            suggestion = None
            if table_count > self.TABLE_COUNT_THRESHOLD:
                status = "warning"
                risk = RiskLevel.MEDIUM
                suggestion = (
                    f"表数量 {table_count} 超过建议阈值 {self.TABLE_COUNT_THRESHOLD}，"
                    "建议定期清理无用的表，或考虑分库分表"
                )

            items.append(self._create_item(
                name="表总数",
                insp_type=InspectionType.CONFIGURATION,
                risk_level=risk,
                status=status,
                description=f"当前数据库共有 {table_count} 张表",
                actual_value=str(table_count),
                reference=f"建议不超过 {self.TABLE_COUNT_THRESHOLD}",
                suggestion=suggestion
            ))
        else:
            items.append(self._create_item(
                name="表总数",
                insp_type=InspectionType.CONFIGURATION,
                risk_level=RiskLevel.INFO,
                status="warning",
                description=f"数据库 {self.dialect} 不支持通过标准视图查询表数量",
                suggestion="没有 INFORMATION_SCHEMA 或 pg_class 等系统视图可用"
            ))

        # 4. 数据库引擎信息（如果有）
        engine_info = "未知"
        if caps["information_schema"]:
            rows = self._execute_query(
                "SELECT DISTINCT ENGINE FROM INFORMATION_SCHEMA.TABLES WHERE ENGINE IS NOT NULL LIMIT 5"
            )
            if rows and len(rows) > 0:
                engines = [str(r[0]) for r in rows if r[0]]
                if engines:
                    engine_info = ", ".join(engines)

        items.append(self._create_item(
            name="数据库引擎/方言",
            insp_type=InspectionType.CONFIGURATION,
            risk_level=RiskLevel.INFO,
            status="pass" if engine_info != "未知" else "warning",
            description=f"数据库方言: {self.dialect}, 引擎: {engine_info}",
            actual_value=engine_info,
            suggestion=(
                "该数据库类型使用通用巡检器，部分针对特定数据库的优化检查可能不可用"
                if engine_info == "未知" else None
            )
        ))

        return items

    # ==================== 性能检查 ====================

    def inspect_performance(self) -> List[InspectionItem]:
        """
        检查性能指标（通用实现）

        获取活跃连接数、表大小分布等基础性能指标。

        返回：
            List[InspectionItem]: 性能检查项列表
        """
        items = []
        caps = self._detect_capabilities()

        # 1. 活跃连接数
        connection_count = self._get_connection_count(caps)
        if connection_count is not None:
            status = "pass"
            risk = RiskLevel.INFO
            suggestion = None

            if connection_count > self.CONNECTION_USAGE_CRITICAL:
                status = "fail"
                risk = RiskLevel.CRITICAL
                suggestion = (
                    f"活跃连接数 {connection_count} 超过严重阈值 "
                    f"{self.CONNECTION_USAGE_CRITICAL}，建议检查是否有连接泄漏，"
                    "或增加最大连接数配置"
                )
            elif connection_count > self.CONNECTION_USAGE_THRESHOLD:
                status = "warning"
                risk = RiskLevel.MEDIUM
                suggestion = (
                    f"活跃连接数 {connection_count} 超过建议阈值 "
                    f"{self.CONNECTION_USAGE_THRESHOLD}，请关注连接池使用情况"
                )

            items.append(self._create_item(
                name="活跃连接数",
                insp_type=InspectionType.PERFORMANCE,
                risk_level=risk,
                status=status,
                description=f"当前活跃连接数: {connection_count}",
                actual_value=str(connection_count),
                reference=f"建议 < {self.CONNECTION_USAGE_THRESHOLD}",
                suggestion=suggestion
            ))
        else:
            items.append(self._create_item(
                name="活跃连接数",
                insp_type=InspectionType.PERFORMANCE,
                risk_level=RiskLevel.INFO,
                status="warning",
                description=f"数据库 {self.dialect} 不支持通过标准视图查询活跃连接数",
                suggestion=(
                    "当前数据库没有 pg_stat_activity / v$session / "
                    "sys.dm_exec_sessions / SHOW PROCESSLIST 等会话视图"
                )
            ))

        # 2. 大表检查 - 通过 INFORMATION_SCHEMA 获取前 10 大表
        if caps["information_schema"]:
            try:
                rows = self.connector.execute(
                    "SELECT TABLE_SCHEMA, TABLE_NAME, TABLE_ROWS "
                    "FROM INFORMATION_SCHEMA.TABLES "
                    "WHERE TABLE_TYPE = 'BASE TABLE' AND TABLE_ROWS IS NOT NULL "
                    "ORDER BY TABLE_ROWS DESC LIMIT 10"
                )
                if rows and rows.rows:
                    top_tables = [
                        f"{r[0]}.{r[1]}({r[2]}行)"
                        for r in rows.rows
                    ]
                    items.append(self._create_item(
                        name="TOP 大表",
                        insp_type=InspectionType.PERFORMANCE,
                        risk_level=RiskLevel.INFO,
                        status="pass",
                        description="前 10 大表: " + ", ".join(top_tables),
                        actual_value=str(len(rows.rows)) + " 张表"
                    ))
                else:
                    items.append(self._create_item(
                        name="TOP 大表",
                        insp_type=InspectionType.PERFORMANCE,
                        risk_level=RiskLevel.INFO,
                        status="pass",
                        description="当前数据库没有行数统计信息",
                        suggestion="部分数据库（如 Trino）的 INFORMATION_SCHEMA 不提供 TABLE_ROWS"
                    ))
            except Exception as e:
                logger.debug(f"大表查询失败（非关键路径）: {e}")

        # 3. 总体连接使用率评估
        if connection_count is not None:
            connection_info = f"活跃连接数 {connection_count}"
        else:
            connection_info = "无法获取"

        items.append(self._create_item(
            name="性能综述",
            insp_type=InspectionType.PERFORMANCE,
            risk_level=RiskLevel.INFO,
            status="pass",
            description=(
                f"通用性能检查完成。{connection_info}。"
                f"数据库方言 {self.dialect} 的部分深度性能指标需要专用采集器"
            ),
            suggestion=(
                f"如需更详细的性能指标，建议使用 db_monitor 模块的 "
                f"GenericMetricsCollector 进行指标采集"
            )
        ))

        return items

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
                "SELECT COUNT(*) FROM pg_stat_activity WHERE state = 'active'"
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

    # ==================== 存储检查 ====================

    def inspect_storage(self) -> List[InspectionItem]:
        """
        检查存储使用情况（通用实现）

        获取数据库大小、表空间使用等基础存储指标。

        返回：
            List[InspectionItem]: 存储检查项列表
        """
        items = []
        caps = self._detect_capabilities()

        # 1. 数据库大小
        db_size_mb = self._get_database_size_mb(caps)
        if db_size_mb is not None:
            size_str = self._format_size_mb(db_size_mb)
            items.append(self._create_item(
                name="数据库总大小",
                insp_type=InspectionType.STORAGE,
                risk_level=RiskLevel.INFO,
                status="pass",
                description=f"当前数据库总大小: {size_str}",
                actual_value=f"{db_size_mb:.1f} MB"
            ))
        else:
            items.append(self._create_item(
                name="数据库总大小",
                insp_type=InspectionType.STORAGE,
                risk_level=RiskLevel.INFO,
                status="warning",
                description=f"数据库 {self.dialect} 不支持通过标准视图查询数据库大小",
                suggestion=(
                    "没有 pg_database_size / information_schema.tables(data_length) "
                    "/ PRAGMA page_count 等存储信息查询方式"
                )
            ))

        # 2. 表数量检查
        if caps["information_schema"]:
            rows = self._execute_query(
                "SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES "
                "WHERE TABLE_TYPE = 'BASE TABLE'"
            )
            if rows and rows[0][0] is not None:
                table_count = int(rows[0][0])
                items.append(self._create_item(
                    name="表数量",
                    insp_type=InspectionType.STORAGE,
                    risk_level=RiskLevel.INFO,
                    status="pass" if table_count < self.TABLE_COUNT_THRESHOLD else "warning",
                    description=f"当前数据库共有 {table_count} 张表",
                    actual_value=str(table_count),
                    reference=f"建议不超过 {self.TABLE_COUNT_THRESHOLD}",
                    suggestion=(
                        f"表数量 {table_count} 较大，建议关注表数量增长趋势"
                        if table_count >= self.TABLE_COUNT_THRESHOLD else None
                    )
                ))

        # 3. 索引数量
        index_count = self._get_index_count(caps)
        if index_count is not None:
            items.append(self._create_item(
                name="索引数量",
                insp_type=InspectionType.STORAGE,
                risk_level=RiskLevel.INFO,
                status="pass",
                description=f"当前数据库共有 {index_count} 个索引",
                actual_value=str(index_count),
                suggestion="建议定期检查索引使用率，清理无用索引" if index_count > 100 else None
            ))

        return items

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
                "SELECT pg_database_size(current_database()) / 1024.0 / 1024.0"
            )
            if rows and rows[0][0] is not None:
                return float(rows[0][0])

        # MySQL 风格（通过 information_schema）
        if caps["information_schema"]:
            rows = self._execute_query(
                "SELECT SUM(data_length + index_length) / 1024.0 / 1024.0 "
                "FROM information_schema.tables WHERE table_schema = DATABASE()"
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

    def _format_size_mb(self, size_mb: float) -> str:
        """
        格式化大小显示

        参数：
            size_mb: 大小（MB）

        返回：
            str: 可读的大小字符串
        """
        if size_mb < 1:
            return f"{size_mb * 1024:.1f} KB"
        elif size_mb < 1024:
            return f"{size_mb:.1f} MB"
        else:
            return f"{size_mb / 1024:.2f} GB"

    # ==================== 安全检查 ====================

    def inspect_security(self) -> List[InspectionItem]:
        """
        检查安全配置（通用实现）

        目前通用数据库不支持深度安全检查，返回基础安全信息。

        返回：
            List[InspectionItem]: 安全检查项列表
        """
        items = []
        caps = self._detect_capabilities()

        # 1. 用户/角色信息（如果支持）
        user_info = "未知"
        # 尝试多种方式获取当前用户
        queries = [
            "SELECT CURRENT_USER",
            "SELECT current_user",
            "SELECT USER()",
            "SELECT SESSION_USER",
        ]
        for sql in queries:
            rows = self._execute_query(sql)
            if rows and len(rows) > 0 and rows[0][0]:
                user_info = str(rows[0][0])
                break

        items.append(self._create_item(
            name="数据库用户",
            insp_type=InspectionType.SECURITY,
            risk_level=RiskLevel.INFO,
            status="pass" if user_info != "未知" else "warning",
            description=f"当前数据库用户: {user_info}",
            actual_value=user_info,
            suggestion=(
                "无法获取当前用户信息，请确认连接的用户权限"
                if user_info == "未知" else None
            )
        ))

        # 2. 安全检查说明
        items.append(self._create_item(
            name="安全审计",
            insp_type=InspectionType.SECURITY,
            risk_level=RiskLevel.INFO,
            status="warning",
            description=(
                f"数据库 {self.dialect} 的专项安全审计尚未实现。"
                f"当前仅能获取基础用户信息。"
            ),
            suggestion=(
                f"如需完整安全审计，可使用 db_security 模块。"
                f"数据库 {self.dialect} 将使用通用安全检测规则"
            )
        ))

        return items

    # ==================== 容量检查 ====================

    def inspect_capacity(self) -> List[InspectionItem]:
        """
        检查容量使用情况（通用实现）

        获取数据库大小、表数量、索引数量等基础容量指标。

        返回：
            List[InspectionItem]: 容量检查项列表
        """
        items = []
        caps = self._detect_capabilities()

        # 1. 数据库容量
        db_size_mb = self._get_database_size_mb(caps)
        if db_size_mb is not None:
            size_str = self._format_size_mb(db_size_mb)
            items.append(self._create_item(
                name="数据库容量",
                insp_type=InspectionType.CAPACITY,
                risk_level=RiskLevel.INFO,
                status="pass",
                description=f"当前数据库总容量: {size_str}",
                actual_value=f"{db_size_mb:.1f} MB"
            ))
        else:
            items.append(self._create_item(
                name="数据库容量",
                insp_type=InspectionType.CAPACITY,
                risk_level=RiskLevel.INFO,
                status="warning",
                description=f"数据库 {self.dialect} 不支持通过标准视图查询容量",
                suggestion="无法获取存储容量信息，请通过操作系统层面监控磁盘使用"
            ))

        # 2. 容量规划建议
        items.append(self._create_item(
            name="容量规划建议",
            insp_type=InspectionType.CAPACITY,
            risk_level=RiskLevel.INFO,
            status="pass",
            description=(
                f"数据库 {self.dialect} 的容量规划建议。"
                f"如需容量趋势预测，建议启用 db_monitor 的持久化存储功能"
            ),
            suggestion=(
                f"使用 db_monitor 定期采集指标数据，"
                f"结合 CapacityPredictor 进行趋势预测和阈值预警"
            )
        ))

        return items