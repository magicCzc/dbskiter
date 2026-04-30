"""
PostgreSQL巡检器

提供PostgreSQL数据库的专项巡检能力
"""

import logging
from typing import List, Dict, Any

from dbskiter.shared.unified_connector import UnifiedConnector
from .base import BaseInspector
from ..models import InspectionItem, InspectionType, RiskLevel

logger = logging.getLogger(__name__)


class PostgreSQLInspector(BaseInspector):
    """
    PostgreSQL数据库巡检器

    提供PostgreSQL特有的配置、性能、存储、安全检查
    """

    # PostgreSQL配置检查标准
    CONFIG_STANDARDS = {
        'max_connections': {
            'min': 100,
            'max': 1000,
            'description': '最大连接数'
        },
        'shared_buffers': {
            'min': '128MB',
            'recommend': '物理内存的25%',
            'description': '共享缓冲区大小'
        },
        'effective_cache_size': {
            'min': '1GB',
            'recommend': '物理内存的50-75%',
            'description': '有效缓存大小'
        },
        'work_mem': {
            'min': '4MB',
            'recommend': '根据并发连接数调整',
            'description': '工作内存'
        },
        'maintenance_work_mem': {
            'min': '64MB',
            'description': '维护工作内存'
        },
        'checkpoint_completion_target': {
            'min': 0.7,
            'max': 0.9,
            'description': '检查点完成目标'
        },
        'wal_buffers': {
            'min': '16MB',
            'description': 'WAL缓冲区大小'
        },
        'default_statistics_target': {
            'min': 100,
            'description': '默认统计目标'
        },
        'random_page_cost': {
            'min': 1.0,
            'max': 4.0,
            'description': '随机页成本'
        },
        'effective_io_concurrency': {
            'min': 1,
            'description': '有效IO并发数'
        }
    }

    # 性能阈值
    CACHE_HIT_RATIO_THRESHOLD = 99.0
    CACHE_HIT_RATIO_CRITICAL = 95.0

    def get_instance_info(self) -> Dict[str, Any]:
        """获取PostgreSQL实例信息"""
        info = super().get_instance_info()

        try:
            # 获取版本
            result = self._execute_query("SELECT version()")
            if result:
                info['version'] = result[0][0]

            # 获取数据库名
            result = self._execute_query("SELECT current_database()")
            if result:
                info['database_name'] = result[0][0]
                info['instance_name'] = f"postgresql-{self.connector.host}-{result[0][0]}"

        except Exception as e:
            logger.warning(f"获取PostgreSQL实例信息失败: {e}")

        return info

    def inspect_configuration(self) -> List[InspectionItem]:
        """检查PostgreSQL配置"""
        items = []

        for param_name, standard in self.CONFIG_STANDARDS.items():
            try:
                result = self._execute_query(
                    "SELECT setting, unit FROM pg_settings WHERE name = %s",
                    (param_name,)
                )

                if not result:
                    continue

                actual_value = result[0][0]
                unit = result[0][1] or ''
                display_value = f"{actual_value}{unit}" if unit else actual_value

                status = 'pass'
                risk_level = RiskLevel.INFO
                suggestion = None

                # 数值类型检查
                if 'min' in standard and isinstance(standard['min'], int):
                    try:
                        if int(actual_value) < standard['min']:
                            status = 'warning'
                            risk_level = RiskLevel.MEDIUM
                            suggestion = f"建议设置为 >= {standard['min']}"
                    except ValueError:
                        pass

                items.append(self._create_item(
                    name=f"配置检查: {param_name}",
                    insp_type=InspectionType.CONFIGURATION,
                    risk_level=risk_level,
                    status=status,
                    description=standard['description'],
                    actual_value=display_value,
                    reference=standard.get('recommend') or f">= {standard.get('min', 'N/A')}",
                    suggestion=suggestion
                ))

            except Exception as e:
                logger.warning(f"检查配置项 {param_name} 失败: {e}")

        return items

    def inspect_performance(self) -> List[InspectionItem]:
        """检查PostgreSQL性能"""
        items = []

        try:
            # 检查缓存命中率
            result = self._execute_query("""
                SELECT
                    ROUND((100.0 * sum(heap_blks_hit) / NULLIF(sum(heap_blks_hit) + sum(heap_blks_read), 0))::numeric, 2)
                FROM pg_statio_user_tables
            """)
            hit_ratio = float(result[0][0]) if result and result[0][0] else 0

            if hit_ratio < self.CACHE_HIT_RATIO_THRESHOLD:
                items.append(self._create_item(
                    name="缓存命中率",
                    insp_type=InspectionType.PERFORMANCE,
                    risk_level=RiskLevel.HIGH if hit_ratio < self.CACHE_HIT_RATIO_CRITICAL else RiskLevel.MEDIUM,
                    status="warning",
                    description=f"缓存命中率低于{self.CACHE_HIT_RATIO_THRESHOLD}%",
                    actual_value=f"{hit_ratio:.2f}%",
                    reference=f">= {self.CACHE_HIT_RATIO_THRESHOLD}%",
                    suggestion="考虑增加shared_buffers"
                ))
            else:
                items.append(self._create_item(
                    name="缓存命中率",
                    insp_type=InspectionType.PERFORMANCE,
                    risk_level=RiskLevel.INFO,
                    status="pass",
                    description="缓存命中率正常",
                    actual_value=f"{hit_ratio:.2f}%",
                    reference=f">= {self.CACHE_HIT_RATIO_THRESHOLD}%"
                ))

            # 检查连接数使用率
            result = self._execute_query("""
                SELECT 
                    (SELECT count(*) FROM pg_stat_activity),
                    (SELECT setting::int FROM pg_settings WHERE name = 'max_connections')
            """)

            if result:
                connected = result[0][0]
                max_conn = result[0][1]
                usage_rate = (connected / max_conn) * 100

                if usage_rate > self.CONNECTION_USAGE_THRESHOLD:
                    items.append(self._create_item(
                        name="连接数使用率",
                        insp_type=InspectionType.PERFORMANCE,
                        risk_level=RiskLevel.HIGH if usage_rate > self.CONNECTION_USAGE_CRITICAL else RiskLevel.MEDIUM,
                        status="warning",
                        description=f"连接数使用率过高: {usage_rate:.1f}%",
                        actual_value=f"{connected}/{max_conn} ({usage_rate:.1f}%)",
                        reference=f"< {self.CONNECTION_USAGE_THRESHOLD}%",
                        suggestion="考虑增加max_connections或优化连接池配置"
                    ))
                else:
                    items.append(self._create_item(
                        name="连接数使用率",
                        insp_type=InspectionType.PERFORMANCE,
                        risk_level=RiskLevel.INFO,
                        status="pass",
                        description=f"连接数使用率正常: {usage_rate:.1f}%",
                        actual_value=f"{connected}/{max_conn} ({usage_rate:.1f}%)",
                        reference=f"< {self.CONNECTION_USAGE_THRESHOLD}%"
                    ))

            # 检查长时间运行的查询
            result = self._execute_query("""
                SELECT count(*) FROM pg_stat_activity
                WHERE state = 'active'
                AND query_start < now() - interval '5 minutes'
            """)

            long_queries = result[0][0] if result else 0
            if long_queries > 0:
                items.append(self._create_item(
                    name="长时间运行查询",
                    insp_type=InspectionType.PERFORMANCE,
                    risk_level=RiskLevel.MEDIUM,
                    status="warning",
                    description=f"发现 {long_queries} 个运行超过5分钟的查询",
                    suggestion="检查并优化长时间运行的查询"
                ))

            # 检查锁等待
            result = self._execute_query("""
                SELECT count(*) FROM pg_locks WHERE NOT granted
            """)

            lock_waits = result[0][0] if result else 0
            if lock_waits > 0:
                items.append(self._create_item(
                    name="锁等待",
                    insp_type=InspectionType.PERFORMANCE,
                    risk_level=RiskLevel.HIGH,
                    status="warning",
                    description=f"发现 {lock_waits} 个锁等待",
                    suggestion="检查并解决锁冲突"
                ))

        except Exception as e:
            logger.warning(f"性能检查失败: {e}")

        return items

    def inspect_storage(self) -> List[InspectionItem]:
        """检查PostgreSQL存储"""
        items = []

        try:
            # 检查数据库大小
            result = self._execute_query("""
                SELECT
                    datname,
                    ROUND((pg_database_size(datname) / 1024.0 / 1024 / 1024)::numeric, 2) AS size_gb
                FROM pg_database
                WHERE datallowconn = true
                ORDER BY pg_database_size(datname) DESC
            """)

            if result:
                for row in result:
                    items.append(self._create_item(
                        name=f"数据库大小: {row[0]}",
                        insp_type=InspectionType.STORAGE,
                        risk_level=RiskLevel.INFO,
                        status="pass",
                        description=f"数据库 {row[0]} 大小",
                        actual_value=f"{row[1]}GB"
                    ))

            # 检查大表
            result = self._execute_query("""
                SELECT
                    schemaname,
                    relname,
                    ROUND((pg_total_relation_size(relid) / 1024.0 / 1024)::numeric, 2) AS size_mb
                FROM pg_stat_user_tables
                WHERE pg_total_relation_size(relid) > %s * 1024 * 1024
                ORDER BY pg_total_relation_size(relid) DESC
                LIMIT 10
            """, (self.TABLE_SIZE_THRESHOLD_MB,))

            if result:
                for row in result:
                    items.append(self._create_item(
                        name=f"大表检查: {row[0]}.{row[1]}",
                        insp_type=InspectionType.STORAGE,
                        risk_level=RiskLevel.MEDIUM,
                        status="warning",
                        description=f"表大小超过阈值 {self.TABLE_SIZE_THRESHOLD_MB}MB",
                        actual_value=f"{row[2]}MB",
                        reference=f"< {self.TABLE_SIZE_THRESHOLD_MB}MB",
                        suggestion="考虑归档历史数据或分区"
                    ))

            # 检查膨胀表
            result = self._execute_query("""
                SELECT
                    schemaname,
                    relname,
                    ROUND((100 * (n_dead_tup::float / NULLIF(n_live_tup + n_dead_tup, 0)))::numeric, 2) AS dead_pct
                FROM pg_stat_user_tables
                WHERE n_dead_tup > 1000
                AND (n_dead_tup::float / NULLIF(n_live_tup + n_dead_tup, 0)) > 0.2
                ORDER BY n_dead_tup DESC
                LIMIT 10
            """)

            if result:
                for row in result:
                    items.append(self._create_item(
                        name=f"表膨胀检查: {row[0]}.{row[1]}",
                        insp_type=InspectionType.STORAGE,
                        risk_level=RiskLevel.MEDIUM,
                        status="warning",
                        description=f"表膨胀严重，死元组比例 {row[2]}%",
                        actual_value=f"{row[2]}%",
                        reference="< 20%",
                        suggestion="执行VACUUM或VACUUM FULL"
                    ))

        except Exception as e:
            logger.warning(f"存储检查失败: {e}")

        return items

    def inspect_security(self) -> List[InspectionItem]:
        """检查PostgreSQL安全"""
        items = []

        try:
            # 检查超级用户
            result = self._execute_query("""
                SELECT rolname FROM pg_roles WHERE rolsuper = true
            """)

            if result:
                for row in result:
                    if row[0] != 'postgres':
                        items.append(self._create_item(
                            name=f"超级用户检查: {row[0]}",
                            insp_type=InspectionType.SECURITY,
                            risk_level=RiskLevel.HIGH,
                            status="warning",
                            description=f"用户 {row[0]} 具有超级用户权限",
                            suggestion="审查超级用户权限分配，遵循最小权限原则"
                        ))

            # 检查无密码用户
            result = self._execute_query("""
                SELECT rolname FROM pg_roles 
                WHERE rolpassword IS NULL
                AND rolcanlogin = true
            """)

            if result:
                for row in result:
                    items.append(self._create_item(
                        name=f"无密码用户检查: {row[0]}",
                        insp_type=InspectionType.SECURITY,
                        risk_level=RiskLevel.CRITICAL,
                        status="warning",
                        description=f"用户 {row[0]} 没有设置密码",
                        suggestion="为所有用户设置强密码"
                    ))

            # 检查SSL配置
            result = self._execute_query("SHOW ssl")
            ssl_enabled = result[0][0] if result else 'off'

            if ssl_enabled.lower() != 'on':
                items.append(self._create_item(
                    name="SSL配置检查",
                    insp_type=InspectionType.SECURITY,
                    risk_level=RiskLevel.MEDIUM,
                    status="warning",
                    description="SSL未启用",
                    actual_value=ssl_enabled,
                    reference="on",
                    suggestion="建议启用SSL加密连接"
                ))
            else:
                items.append(self._create_item(
                    name="SSL配置检查",
                    insp_type=InspectionType.SECURITY,
                    risk_level=RiskLevel.INFO,
                    status="pass",
                    description="SSL已启用",
                    actual_value=ssl_enabled
                ))

        except Exception as e:
            logger.warning(f"安全检查失败: {e}")

        return items

    def inspect_capacity(self) -> List[InspectionItem]:
        """检查PostgreSQL容量"""
        items = []

        try:
            # 检查表空间使用情况
            result = self._execute_query("""
                SELECT 
                    spcname,
                    pg_size_pretty(pg_tablespace_size(oid))
                FROM pg_tablespace
                ORDER BY pg_tablespace_size(oid) DESC
            """)

            if result:
                for row in result:
                    items.append(self._create_item(
                        name=f"表空间: {row[0]}",
                        insp_type=InspectionType.CAPACITY,
                        risk_level=RiskLevel.INFO,
                        status="pass",
                        description=f"表空间 {row[0]} 大小",
                        actual_value=row[1]
                    ))

            # 检查WAL文件数量
            result = self._execute_query("""
                SELECT count(*) FROM pg_ls_waldir()
                WHERE name ~ '^[0-9A-F]{24}$'
            """)

            if result:
                wal_count = result[0][0]
                items.append(self._create_item(
                    name="WAL文件数量",
                    insp_type=InspectionType.CAPACITY,
                    risk_level=RiskLevel.INFO,
                    status="pass",
                    description="WAL文件数量",
                    actual_value=str(wal_count),
                    suggestion="定期归档和清理WAL文件"
                ))

        except Exception as e:
            logger.warning(f"容量检查失败: {e}")

        return items
