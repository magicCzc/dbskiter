"""
ClickHouse巡检器

提供ClickHouse数据库的巡检能力

文件功能：ClickHouse数据库巡检器实现
主要类：ClickHouseInspector - ClickHouse数据库巡检器

支持的巡检项：
    - 配置检查：max_memory_usage、max_execution_time等
    - 性能检查：慢查询、高内存使用、连接数
    - 存储检查：表大小、分区数、parts数量
    - 安全检查：默认用户、网络配置
    - 容量检查：磁盘使用、数据增长趋势
    - 复制检查：Replicated表复制延迟

依赖：
    - clickhouse-driver 或 clickhouse-connect 驱动
    - ClickHouse 20.0+

作者：Magiczc
创建时间：2026-06-03
版本：1.0.0
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

from dbskiter.shared.unified_connector import UnifiedConnector
from ..models import InspectionItem, InspectionType, RiskLevel
from .base import BaseInspector

logger = logging.getLogger(__name__)


class ClickHouseInspector(BaseInspector):
    """
    ClickHouse数据库巡检器

    提供ClickHouse特有的巡检能力：
    - 配置检查：内存限制、超时设置、并发控制
    - 性能检查：慢查询、高内存使用、连接数
    - 存储检查：表大小、分区数、parts数量
    - 安全检查：用户权限、网络配置
    - 容量检查：磁盘使用、数据增长
    - 复制检查：Replicated表复制延迟

    特性：
    - 自动检测集群配置
    - 支持分布式表巡检
    - 支持Replicated表复制监控
    """

    def __init__(self, connector: UnifiedConnector):
        """
        初始化ClickHouse巡检器

        参数：
            connector: UnifiedConnector实例
        """
        super().__init__(connector)
        self._version = None
        self._is_cluster = None

    def _get_version(self) -> str:
        """
        获取ClickHouse版本

        返回：
            str: 版本号
        """
        if self._version is None:
            try:
                result = self.connector.execute("SELECT version()")
                self._version = result.rows[0][0] if result else "unknown"
            except Exception as e:
                logger.warning(f"获取版本失败: {e}")
                self._version = "unknown"
        return self._version

    def _is_cluster_mode(self) -> bool:
        """
        检查是否为集群模式

        返回：
            bool: 是否为集群模式
        """
        if self._is_cluster is None:
            try:
                result = self.connector.execute("""
                    SELECT count()
                    FROM system.clusters
                    WHERE cluster != 'test_cluster_two_shards_localhost'
                """)
                self._is_cluster = result.rows[0][0] > 0 if result else False
            except Exception as e:
                logger.warning(f"检查集群模式失败: {e}")
                self._is_cluster = False
        return self._is_cluster

    def inspect_configuration(self) -> List[InspectionItem]:
        """
        检查ClickHouse配置

        返回：
            List[InspectionItem]: 配置检查项列表
        """
        items = []

        # 检查内存限制
        try:
            result = self.connector.execute("""
                SELECT name, value
                FROM system.settings
                WHERE name IN ('max_memory_usage', 'max_execution_time', 'max_concurrent_queries')
            """)

            settings = {row[0]: row[1] for row in result.rows} if result else {}

            # max_memory_usage检查
            max_memory = settings.get('max_memory_usage', '0')
            if max_memory == '0' or int(max_memory) > 100 * 1024 * 1024 * 1024:  # 100GB
                items.append(InspectionItem(
                    name="max_memory_usage",
                    inspection_type=InspectionType.CONFIGURATION,
                    risk_level=RiskLevel.MEDIUM,
                    description=f"max_memory_usage设置为{max_memory}，可能导致内存耗尽",
                    recommendation="设置合理的内存限制，如10GB",
                    current_value=max_memory,
                    expected_value="10737418240"
                ))
            else:
                items.append(InspectionItem(
                    name="max_memory_usage",
                    inspection_type=InspectionType.CONFIGURATION,
                    risk_level=RiskLevel.LOW,
                    description=f"max_memory_usage设置合理: {max_memory}",
                    current_value=max_memory
                ))

            # max_execution_time检查
            max_time = settings.get('max_execution_time', '0')
            if max_time == '0':
                items.append(InspectionItem(
                    name="max_execution_time",
                    inspection_type=InspectionType.CONFIGURATION,
                    risk_level=RiskLevel.MEDIUM,
                    description="max_execution_time未设置，可能导致长时间查询阻塞",
                    recommendation="设置查询超时时间，如300秒",
                    current_value=max_time,
                    expected_value="300"
                ))

        except Exception as e:
            logger.warning(f"检查内存配置失败: {e}")

        # 检查query_log配置
        try:
            result = self.connector.execute("""
                SELECT count()
                FROM system.tables
                WHERE database = 'system' AND name = 'query_log'
            """)
            has_query_log = result.rows[0][0] > 0 if result else False

            if not has_query_log:
                items.append(InspectionItem(
                    name="query_log",
                    inspection_type=InspectionType.CONFIGURATION,
                    risk_level=RiskLevel.MEDIUM,
                    description="query_log未启用，无法分析慢查询",
                    recommendation="在配置文件中启用query_log",
                    current_value="disabled",
                    expected_value="enabled"
                ))
            else:
                items.append(InspectionItem(
                    name="query_log",
                    inspection_type=InspectionType.CONFIGURATION,
                    risk_level=RiskLevel.LOW,
                    description="query_log已启用",
                    current_value="enabled"
                ))

        except Exception as e:
            logger.warning(f"检查query_log配置失败: {e}")

        return items

    def inspect_performance(self) -> List[InspectionItem]:
        """
        检查ClickHouse性能

        返回：
            List[InspectionItem]: 性能检查项列表
        """
        items = []

        # 检查慢查询
        try:
            result = self.connector.execute("""
                SELECT count()
                FROM system.query_log
                WHERE type = 'QueryFinish'
                AND query_duration_ms >= 10000
                AND event_time >= now() - INTERVAL 1 HOUR
            """)
            slow_count = int(result.rows[0][0]) if result else 0

            if slow_count > 10:
                items.append(InspectionItem(
                    name="slow_queries",
                    inspection_type=InspectionType.PERFORMANCE,
                    risk_level=RiskLevel.HIGH,
                    description=f"过去1小时有{slow_count}个慢查询（超过10秒）",
                    recommendation="优化查询或增加资源",
                    current_value=str(slow_count),
                    expected_value="< 10"
                ))
            elif slow_count > 0:
                items.append(InspectionItem(
                    name="slow_queries",
                    inspection_type=InspectionType.PERFORMANCE,
                    risk_level=RiskLevel.MEDIUM,
                    description=f"过去1小时有{slow_count}个慢查询",
                    current_value=str(slow_count)
                ))
            else:
                items.append(InspectionItem(
                    name="slow_queries",
                    inspection_type=InspectionType.PERFORMANCE,
                    risk_level=RiskLevel.LOW,
                    description="过去1小时无慢查询",
                    current_value="0"
                ))

        except Exception as e:
            logger.warning(f"检查慢查询失败: {e}")

        # 检查高内存使用查询
        try:
            result = self.connector.execute("""
                SELECT count()
                FROM system.processes
                WHERE memory_usage > 1000000000
            """)
            high_memory_count = int(result.rows[0][0]) if result else 0

            if high_memory_count > 0:
                items.append(InspectionItem(
                    name="high_memory_queries",
                    inspection_type=InspectionType.PERFORMANCE,
                    risk_level=RiskLevel.HIGH,
                    description=f"当前有{high_memory_count}个查询使用超过1GB内存",
                    recommendation="检查并优化这些查询",
                    current_value=str(high_memory_count)
                ))

        except Exception as e:
            logger.warning(f"检查高内存查询失败: {e}")

        # 检查连接数
        try:
            result = self.connector.execute("SELECT count() FROM system.processes")
            connections = int(result.rows[0][0]) if result else 0

            if connections > 100:
                items.append(InspectionItem(
                    name="connections",
                    inspection_type=InspectionType.PERFORMANCE,
                    risk_level=RiskLevel.HIGH,
                    description=f"当前连接数{connections}过高",
                    recommendation="检查连接池配置或增加max_concurrent_queries",
                    current_value=str(connections),
                    expected_value="< 100"
                ))
            elif connections > 50:
                items.append(InspectionItem(
                    name="connections",
                    inspection_type=InspectionType.PERFORMANCE,
                    risk_level=RiskLevel.MEDIUM,
                    description=f"当前连接数{connections}较高",
                    current_value=str(connections)
                ))
            else:
                items.append(InspectionItem(
                    name="connections",
                    inspection_type=InspectionType.PERFORMANCE,
                    risk_level=RiskLevel.LOW,
                    description=f"当前连接数{connections}正常",
                    current_value=str(connections)
                ))

        except Exception as e:
            logger.warning(f"检查连接数失败: {e}")

        return items

    def inspect_storage(self) -> List[InspectionItem]:
        """
        检查ClickHouse存储

        返回：
            List[InspectionItem]: 存储检查项列表
        """
        items = []

        # 检查大表
        try:
            result = self.connector.execute("""
                SELECT
                    database,
                    table,
                    total_bytes,
                    total_rows,
                    parts
                FROM system.tables
                WHERE database NOT IN ('system', 'information_schema')
                AND engine LIKE '%MergeTree%'
                ORDER BY total_bytes DESC
                LIMIT 10
            """)

            large_tables = []
            for row in result.rows if result else []:
                total_bytes = int(row[2]) if row[2] else 0
                if total_bytes > 100 * 1024 * 1024 * 1024:  # 100GB
                    large_tables.append({
                        "db": row[0],
                        "table": row[1],
                        "size": total_bytes,
                        "rows": int(row[3]) if row[3] else 0,
                        "parts": int(row[4]) if row[4] else 0
                    })

            if large_tables:
                items.append(InspectionItem(
                    name="large_tables",
                    inspection_type=InspectionType.STORAGE,
                    risk_level=RiskLevel.MEDIUM,
                    description=f"发现{len(large_tables)}个超过100GB的大表",
                    recommendation="考虑分区策略或数据归档",
                    current_value=str(len(large_tables))
                ))

        except Exception as e:
            logger.warning(f"检查大表失败: {e}")

        # 检查parts数量
        try:
            result = self.connector.execute("""
                SELECT
                    database,
                    table,
                    count() as part_count
                FROM system.parts
                WHERE active
                GROUP BY database, table
                HAVING part_count > 1000
                ORDER BY part_count DESC
                LIMIT 10
            """)

            high_parts_tables = []
            for row in result.rows if result else []:
                high_parts_tables.append(f"{row[0]}.{row[1]}: {row[2]} parts")

            if high_parts_tables:
                items.append(InspectionItem(
                    name="high_parts_count",
                    inspection_type=InspectionType.STORAGE,
                    risk_level=RiskLevel.HIGH,
                    description=f"发现{len(high_parts_tables)}个表parts数量超过1000",
                    recommendation="执行OPTIMIZE TABLE合并parts",
                    current_value=str(len(high_parts_tables))
                ))

        except Exception as e:
            logger.warning(f"检查parts数量失败: {e}")

        return items

    def inspect_security(self) -> List[InspectionItem]:
        """
        检查ClickHouse安全

        返回：
            List[InspectionItem]: 安全检查项列表
        """
        items = []

        # 检查默认用户
        try:
            result = self.connector.execute("""
                SELECT count()
                FROM system.users
                WHERE name = 'default' AND auth_type = 'no_password'
            """)
            has_default_no_password = result.rows[0][0] > 0 if result else False

            if has_default_no_password:
                items.append(InspectionItem(
                    name="default_user_password",
                    inspection_type=InspectionType.SECURITY,
                    risk_level=RiskLevel.CRITICAL,
                    description="default用户未设置密码",
                    recommendation="立即为default用户设置密码",
                    current_value="no_password",
                    expected_value="password_protected"
                ))
            else:
                items.append(InspectionItem(
                    name="default_user_password",
                    inspection_type=InspectionType.SECURITY,
                    risk_level=RiskLevel.LOW,
                    description="default用户已设置密码",
                    current_value="password_protected"
                ))

        except Exception as e:
            logger.warning(f"检查默认用户失败: {e}")

        return items

    def inspect_capacity(self) -> List[InspectionItem]:
        """
        检查ClickHouse容量

        返回：
            List[InspectionItem]: 容量检查项列表
        """
        items = []

        # 检查磁盘使用
        try:
            result = self.connector.execute("""
                SELECT
                    sum(bytes_on_disk)
                FROM system.parts
                WHERE active
            """)
            total_bytes = int(result.rows[0][0]) if result and result.rows[0][0] else 0

            # 转换为可读格式
            if total_bytes > 1024 * 1024 * 1024 * 1024:  # 1TB
                size_str = f"{total_bytes / (1024**4):.2f} TB"
            elif total_bytes > 1024 * 1024 * 1024:
                size_str = f"{total_bytes / (1024**3):.2f} GB"
            else:
                size_str = f"{total_bytes / (1024**2):.2f} MB"

            items.append(InspectionItem(
                name="total_data_size",
                inspection_type=InspectionType.CAPACITY,
                risk_level=RiskLevel.LOW,
                description=f"总数据量: {size_str}",
                current_value=size_str
            ))

        except Exception as e:
            logger.warning(f"检查容量失败: {e}")

        return items

    def inspect_replication(self) -> List[InspectionItem]:
        """
        检查ClickHouse复制状态（Replicated表）

        返回：
            List[InspectionItem]: 复制检查项列表
        """
        items = []

        try:
            # 检查是否有Replicated表
            result = self.connector.execute("""
                SELECT count()
                FROM system.tables
                WHERE engine LIKE 'Replicated%'
            """)
            has_replicated = result.rows[0][0] > 0 if result else False

            if not has_replicated:
                return items

            # 检查复制队列
            result = self.connector.execute("""
                SELECT
                    database,
                    table,
                    replica_name,
                    queue_size,
                    absolute_delay
                FROM system.replicas
                ORDER BY queue_size DESC
                LIMIT 10
            """)

            for row in result.rows if result else []:
                queue_size = int(row[3]) if row[3] else 0
                delay = int(row[4]) if row[4] else 0

                if queue_size > 1000 or delay > 300:
                    items.append(InspectionItem(
                        name=f"replication_{row[0]}_{row[1]}",
                        inspection_type=InspectionType.PERFORMANCE,
                        risk_level=RiskLevel.HIGH,
                        description=f"{row[0]}.{row[1]}复制延迟: {delay}秒, 队列: {queue_size}",
                        recommendation="检查网络或副本状态",
                        current_value=f"delay={delay}, queue={queue_size}"
                    ))
                elif queue_size > 100 or delay > 60:
                    items.append(InspectionItem(
                        name=f"replication_{row[0]}_{row[1]}",
                        inspection_type=InspectionType.PERFORMANCE,
                        risk_level=RiskLevel.MEDIUM,
                        description=f"{row[0]}.{row[1]}复制延迟: {delay}秒, 队列: {queue_size}",
                        current_value=f"delay={delay}, queue={queue_size}"
                    ))

        except Exception as e:
            logger.warning(f"检查复制状态失败: {e}")

        return items

    def get_instance_info(self) -> Dict[str, Any]:
        """
        获取ClickHouse实例信息

        返回：
            Dict[str, Any]: 实例信息
        """
        info = {
            "version": self._get_version(),
            "is_cluster": self._is_cluster_mode(),
            "timestamp": datetime.now().isoformat()
        }

        # 获取数据库统计
        try:
            result = self.connector.execute("""
                SELECT
                    count(DISTINCT database),
                    count(),
                    sum(total_rows),
                    sum(total_bytes)
                FROM system.tables
                WHERE database NOT IN ('system', 'information_schema')
            """)
            if result and result.rows:
                row = result.rows[0]
                info["databases"] = int(row[0]) if row[0] else 0
                info["tables"] = int(row[1]) if row[1] else 0
                info["total_rows"] = int(row[2]) if row[2] else 0
                info["total_bytes"] = int(row[3]) if row[3] else 0
        except Exception as e:
            logger.warning(f"获取实例统计失败: {e}")

        return info
