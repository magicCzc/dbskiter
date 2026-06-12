"""
SQL Server巡检器

提供SQL Server数据库的专项巡检能力

文件功能：SQL Server特有的配置、性能、存储、安全检查
主要类：MSSQLInspector - SQL Server数据库巡检器

作者：AI Assistant
创建时间：2026-06-03
"""

import logging
from typing import List, Dict, Any, Optional

from dbskiter.shared.unified_connector import UnifiedConnector
from .base import BaseInspector
from ..models import InspectionItem, InspectionType, RiskLevel

logger = logging.getLogger(__name__)


class MSSQLInspector(BaseInspector):
    """
    SQL Server数据库巡检器

    提供SQL Server特有的配置、性能、存储、安全检查：
    - 配置检查：最大内存、最大并行度、恢复模式等
    - 性能检查：缓冲区命中率、编译比率、等待统计等
    - 存储检查：数据库大小、日志大小、文件增长设置等
    - 安全检查：登录认证、权限配置、审计设置等
    - 容量检查：磁盘空间、数据增长趋势等
    """

    # SQL Server配置检查标准
    CONFIG_STANDARDS = {
        'max server memory (MB)': {
            'description': '最大服务器内存',
            'recommend': '物理内存的70-80%，预留2-4GB给操作系统',
            'check_type': 'memory_ratio'
        },
        'max degree of parallelism': {
            'description': '最大并行度',
            'recommend': 'OLTP建议0或1，OLAP可适当提高',
            'check_type': 'value_range',
            'oltp_max': 1,
            'olap_max': 8
        },
        'cost threshold for parallelism': {
            'description': '并行度成本阈值',
            'recommend': '建议25-50',
            'check_type': 'value_range',
            'min': 25,
            'max': 50
        },
        'remote access': {
            'description': '远程访问',
            'expected': 0,
            'suggestion': '如无必要建议禁用远程访问'
        },
        'xp_cmdshell': {
            'description': 'xp_cmdshell扩展存储过程',
            'expected': 0,
            'suggestion': '安全风险，建议禁用'
        },
        'clr enabled': {
            'description': 'CLR集成',
            'expected': 0,
            'suggestion': '如不使用CLR，建议禁用'
        },
        'Ole Automation Procedures': {
            'description': 'OLE自动化过程',
            'expected': 0,
            'suggestion': '安全风险，建议禁用'
        }
    }

    # 性能阈值
    BUFFER_CACHE_HIT_RATIO_THRESHOLD = 95.0
    BUFFER_CACHE_HIT_RATIO_CRITICAL = 90.0
    PROC_CACHE_HIT_RATIO_THRESHOLD = 90.0
    BATCH_REQUESTS_PER_SEC_THRESHOLD = 1000
    COMPILATIONS_PER_SEC_THRESHOLD = 100
    RECOMPILATIONS_RATIO_THRESHOLD = 10.0

    def __init__(self, connector: UnifiedConnector):
        """
        初始化SQL Server巡检器

        参数:
            connector: 数据库连接器
        """
        super().__init__(connector)
        self._version_info = None
        self._edition = None

    def _get_version_info(self) -> Dict[str, Any]:
        """
        获取SQL Server版本信息

        返回:
            Dict: 版本信息字典
        """
        if self._version_info is not None:
            return self._version_info

        try:
            result = self.connector.execute("""
                SELECT
                    @@VERSION AS version,
                    SERVERPROPERTY('ProductVersion') AS product_version,
                    SERVERPROPERTY('ProductLevel') AS product_level,
                    SERVERPROPERTY('Edition') AS edition,
                    SERVERPROPERTY('EngineEdition') AS engine_edition
            """)

            if result.rows:
                row = result.rows[0]
                self._version_info = {
                    'version': row[0],
                    'product_version': row[1],
                    'product_level': row[2],
                    'edition': row[3],
                    'engine_edition': row[4]
                }
                self._edition = row[3]
            else:
                self._version_info = {}
        except Exception as e:
            logger.error(f"获取版本信息失败: {e}")
            self._version_info = {}

        return self._version_info

    def _get_configuration_value(self, name: str) -> Optional[Any]:
        """
        获取配置项值

        参数:
            name: 配置项名称

        返回:
            Optional[Any]: 配置值或None
        """
        try:
            result = self.connector.execute("""
                SELECT value, value_in_use
                FROM sys.configurations
                WHERE name = ?
            """, (name,))

            if result.rows:
                return {
                    'value': result.rows[0][0],
                    'value_in_use': result.rows[0][1]
                }
        except Exception as e:
            logger.error(f"获取配置 {name} 失败: {e}")

        return None

    def inspect_configuration(self) -> List[InspectionItem]:
        """
        检查SQL Server配置

        返回:
            List[InspectionItem]: 配置检查项列表
        """
        items = []

        # 1. 检查最大内存设置
        memory_config = self._get_configuration_value('max server memory (MB)')
        if memory_config:
            memory_mb = memory_config['value_in_use']
            # 获取物理内存
            try:
                result = self.connector.execute("""
                    SELECT physical_memory_kb / 1024 AS physical_memory_mb
                    FROM sys.dm_os_sys_memory
                """)
                physical_memory = result.rows[0][0] if result.rows else 0

                if physical_memory > 0:
                    memory_ratio = (memory_mb / physical_memory) * 100

                    if memory_ratio > 90:
                        items.append(InspectionItem(
                            name="最大服务器内存设置",
                            inspection_type=InspectionType.CONFIGURATION,
                            risk_level=RiskLevel.HIGH,
                            description=f"最大内存设置为 {memory_mb}MB，占物理内存 {memory_ratio:.1f}%",
                            current_value=f"{memory_mb}MB ({memory_ratio:.1f}%)",
                            recommended_value=f"建议设置为物理内存的70-80% (约 {int(physical_memory * 0.75)}MB)",
                            suggestion="内存设置过高可能导致操作系统内存不足"
                        ))
                    elif memory_ratio < 50:
                        items.append(InspectionItem(
                            name="最大服务器内存设置",
                            inspection_type=InspectionType.CONFIGURATION,
                            risk_level=RiskLevel.MEDIUM,
                            description=f"最大内存设置为 {memory_mb}MB，占物理内存 {memory_ratio:.1f}%",
                            current_value=f"{memory_mb}MB ({memory_ratio:.1f}%)",
                            recommended_value=f"建议设置为物理内存的70-80% (约 {int(physical_memory * 0.75)}MB)",
                            suggestion="内存设置过低可能影响数据库性能"
                        ))
            except Exception as e:
                logger.warning(f"检查内存配置失败: {e}")

        # 2. 检查最大并行度
        maxdop_config = self._get_configuration_value('max degree of parallelism')
        if maxdop_config:
            maxdop = maxdop_config['value_in_use']
            # 检查是否为OLTP环境（简单判断：如果有大量短查询）
            try:
                result = self.connector.execute("""
                    SELECT COUNT(*) FROM sys.dm_exec_query_stats
                    WHERE total_elapsed_time / execution_count < 1000
                """)
                short_queries = result.rows[0][0] if result.rows else 0

                is_oltp = short_queries > 1000

                if is_oltp and maxdop > 1:
                    items.append(InspectionItem(
                        name="最大并行度设置",
                        inspection_type=InspectionType.CONFIGURATION,
                        risk_level=RiskLevel.MEDIUM,
                        description=f"当前MAXDOP设置为 {maxdop}，检测到可能是OLTP环境",
                        current_value=str(maxdop),
                        recommended_value="0或1",
                        suggestion="OLTP环境建议设置MAXDOP为0或1，避免并行查询开销"
                    ))
            except Exception as e:
                logger.warning(f"检查MAXDOP失败: {e}")

        # 3. 检查安全相关配置
        security_configs = [
            ('xp_cmdshell', 'xp_cmdshell扩展存储过程'),
            ('Ole Automation Procedures', 'OLE自动化过程'),
            ('clr enabled', 'CLR集成')
        ]

        for config_name, description in security_configs:
            config = self._get_configuration_value(config_name)
            if config and config['value_in_use'] == 1:
                items.append(InspectionItem(
                    name=description,
                    inspection_type=InspectionType.SECURITY,
                    risk_level=RiskLevel.MEDIUM,
                    description=f"{description}已启用",
                    current_value="启用",
                    recommended_value="禁用",
                    suggestion=f"如无必要，建议禁用{description}以降低安全风险"
                ))

        # 4. 检查恢复模式
        try:
            result = self.connector.execute("""
                SELECT name, recovery_model_desc
                FROM sys.databases
                WHERE name NOT IN ('master', 'tempdb', 'model', 'msdb')
            """)

            for row in result.rows:
                db_name, recovery_model = row[0], row[1]
                if recovery_model == 'FULL':
                    # 检查是否有日志备份
                    backup_result = self.connector.execute(f"""
                        SELECT MAX(backup_finish_date)
                        FROM msdb.dbo.backupset
                        WHERE database_name = '{db_name}'
                        AND type = 'L'
                    """)
                    last_log_backup = backup_result.rows[0][0] if backup_result.rows else None

                    if not last_log_backup:
                        items.append(InspectionItem(
                            name=f"数据库 {db_name} 日志备份",
                            inspection_type=InspectionType.CONFIGURATION,
                            risk_level=RiskLevel.HIGH,
                            description=f"数据库 {db_name} 为完整恢复模式，但未配置日志备份",
                            current_value="无日志备份",
                            recommended_value="配置定期日志备份",
                            suggestion="完整恢复模式需要日志备份来截断日志，否则日志文件会无限增长"
                        ))
        except Exception as e:
            logger.warning(f"检查恢复模式失败: {e}")

        return items

    def inspect_performance(self) -> List[InspectionItem]:
        """
        检查SQL Server性能指标

        返回:
            List[InspectionItem]: 性能检查项列表
        """
        items = []

        # 1. 检查缓冲区命中率
        try:
            result = self.connector.execute("""
                SELECT
                    (a.cntr_value * 1.0 / b.cntr_value) * 100.0 AS buffer_cache_hit_ratio
                FROM sys.dm_os_performance_counters a
                JOIN sys.dm_os_performance_counters b
                    ON a.object_name = b.object_name
                WHERE a.counter_name = 'Buffer cache hit ratio'
                AND b.counter_name = 'Buffer cache hit ratio base'
            """)

            if result.rows:
                hit_ratio = result.rows[0][0]

                if hit_ratio < self.BUFFER_CACHE_HIT_RATIO_CRITICAL:
                    items.append(InspectionItem(
                        name="缓冲区命中率",
                        inspection_type=InspectionType.PERFORMANCE,
                        risk_level=RiskLevel.CRITICAL,
                        description=f"缓冲区命中率为 {hit_ratio:.2f}%，低于临界值 {self.BUFFER_CACHE_HIT_RATIO_CRITICAL}%",
                        current_value=f"{hit_ratio:.2f}%",
                        recommended_value=f">= {self.BUFFER_CACHE_HIT_RATIO_THRESHOLD}%",
                        suggestion="考虑增加内存或优化查询以减少磁盘IO"
                    ))
                elif hit_ratio < self.BUFFER_CACHE_HIT_RATIO_THRESHOLD:
                    items.append(InspectionItem(
                        name="缓冲区命中率",
                        inspection_type=InspectionType.PERFORMANCE,
                        risk_level=RiskLevel.HIGH,
                        description=f"缓冲区命中率为 {hit_ratio:.2f}%，低于推荐值 {self.BUFFER_CACHE_HIT_RATIO_THRESHOLD}%",
                        current_value=f"{hit_ratio:.2f}%",
                        recommended_value=f">= {self.BUFFER_CACHE_HIT_RATIO_THRESHOLD}%",
                        suggestion="监控内存使用情况，考虑优化查询"
                    ))
        except Exception as e:
            logger.warning(f"检查缓冲区命中率失败: {e}")

        # 2. 检查过程缓存命中率
        try:
            result = self.connector.execute("""
                SELECT
                    (a.cntr_value * 1.0 / NULLIF(b.cntr_value, 0)) * 100.0 AS proc_cache_hit_ratio
                FROM sys.dm_os_performance_counters a
                JOIN sys.dm_os_performance_counters b
                    ON a.object_name = b.object_name
                WHERE a.counter_name = 'Cache Hit Ratio'
                AND a.instance_name = '_Total'
                AND b.counter_name = 'Cache Hit Ratio Base'
                AND b.instance_name = '_Total'
            """)

            if result.rows:
                proc_hit_ratio = result.rows[0][0]

                if proc_hit_ratio < self.PROC_CACHE_HIT_RATIO_THRESHOLD:
                    items.append(InspectionItem(
                        name="过程缓存命中率",
                        inspection_type=InspectionType.PERFORMANCE,
                        risk_level=RiskLevel.MEDIUM,
                        description=f"过程缓存命中率为 {proc_hit_ratio:.2f}%",
                        current_value=f"{proc_hit_ratio:.2f}%",
                        recommended_value=f">= {self.PROC_CACHE_HIT_RATIO_THRESHOLD}%",
                        suggestion="考虑使用参数化查询以提高计划重用率"
                    ))
        except Exception as e:
            logger.warning(f"检查过程缓存命中率失败: {e}")

        # 3. 检查编译/重编译比率
        try:
            result = self.connector.execute("""
                SELECT
                    (a.cntr_value * 1.0 / NULLIF(b.cntr_value, 0)) * 100.0 AS recompile_ratio
                FROM sys.dm_os_performance_counters a
                JOIN sys.dm_os_performance_counters b
                    ON a.object_name = b.object_name
                WHERE a.counter_name = 'SQL Re-Compilations/sec'
                AND b.counter_name = 'SQL Compilations/sec'
            """)

            if result.rows:
                recompile_ratio = result.rows[0][0]

                if recompile_ratio > self.RECOMPILATIONS_RATIO_THRESHOLD:
                    items.append(InspectionItem(
                        name="重编译比率",
                        inspection_type=InspectionType.PERFORMANCE,
                        risk_level=RiskLevel.MEDIUM,
                        description=f"SQL重编译比率为 {recompile_ratio:.2f}%",
                        current_value=f"{recompile_ratio:.2f}%",
                        recommended_value=f"< {self.RECOMPILATIONS_RATIO_THRESHOLD}%",
                        suggestion="高重编译率可能由架构变更或统计信息更新引起，检查是否有频繁的对象修改"
                    ))
        except Exception as e:
            logger.warning(f"检查重编译比率失败: {e}")

        # 4. 检查等待统计
        try:
            result = self.connector.execute("""
                SELECT TOP 5
                    wait_type,
                    wait_time_ms / 1000.0 AS wait_time_sec,
                    waiting_tasks_count
                FROM sys.dm_os_wait_stats
                WHERE wait_type NOT IN (
                    'CLR_SEMAPHORE', 'LAZYWRITER_SLEEP', 'RESOURCE_QUEUE',
                    'SLEEP_TASK', 'SLEEP_SYSTEMTASK', 'SQLTRACE_BUFFER_FLUSH',
                    'WAITFOR', 'LOGMGR_QUEUE', 'CHECKPOINT_QUEUE', 'REQUEST_FOR_DEADLOCK_SEARCH',
                    'XE_TIMER_EVENT', 'BROKER_TO_FLUSH', 'BROKER_TASK_STOP',
                    'CLR_MANUAL_EVENT', 'CLR_AUTO_EVENT', 'DISPATCHER_QUEUE_SEMAPHORE',
                    'FT_IFTS_SCHEDULER_IDLE_WAIT', 'XE_DISPATCHER_WAIT', 'XE_DISPATCHER_JOIN'
                )
                ORDER BY wait_time_ms DESC
            """)

            for row in result.rows:
                wait_type, wait_time_sec, task_count = row[0], row[1], row[2]

                if wait_time_sec > 300:  # 超过5分钟
                    items.append(InspectionItem(
                        name=f"等待统计 - {wait_type}",
                        inspection_type=InspectionType.PERFORMANCE,
                        risk_level=RiskLevel.HIGH,
                        description=f"等待类型 {wait_type} 累计等待 {wait_time_sec:.0f} 秒",
                        current_value=f"{wait_time_sec:.0f}秒 ({task_count}次)",
                        recommended_value="< 300秒",
                        suggestion=f"需要分析 {wait_type} 等待类型的根本原因"
                    ))
        except Exception as e:
            logger.warning(f"检查等待统计失败: {e}")

        return items

    def inspect_storage(self) -> List[InspectionItem]:
        """
        检查SQL Server存储使用情况

        返回:
            List[InspectionItem]: 存储检查项列表
        """
        items = []

        # 1. 检查数据库文件大小和增长设置
        try:
            result = self.connector.execute("""
                SELECT
                    DB_NAME(database_id) AS database_name,
                    name AS logical_name,
                    physical_name,
                    size * 8.0 / 1024 AS size_mb,
                    max_size * 8.0 / 1024 AS max_size_mb,
                    growth,
                    is_percent_growth,
                    type_desc
                FROM sys.master_files
                WHERE database_id > 4  -- 排除系统数据库
            """)

            for row in result.rows:
                db_name, logical_name, physical_name = row[0], row[1], row[2]
                size_mb, max_size_mb = row[3], row[4]
                growth, is_percent_growth, type_desc = row[5], row[6], row[7]

                # 检查文件大小
                if size_mb > 10240:  # 超过10GB
                    items.append(InspectionItem(
                        name=f"数据库文件 {db_name}.{logical_name}",
                        inspection_type=InspectionType.STORAGE,
                        risk_level=RiskLevel.MEDIUM,
                        description=f"数据文件大小为 {size_mb:.0f}MB",
                        current_value=f"{size_mb:.0f}MB",
                        recommended_value="考虑分区或归档",
                        suggestion="大文件可能影响备份和恢复性能"
                    ))

                # 检查增长设置
                if is_percent_growth and growth > 10:
                    items.append(InspectionItem(
                        name=f"文件增长设置 {db_name}.{logical_name}",
                        inspection_type=InspectionType.STORAGE,
                        risk_level=RiskLevel.MEDIUM,
                        description=f"文件使用百分比增长 ({growth}%)",
                        current_value=f"{growth}%",
                        recommended_value="固定大小增长 (如100MB)",
                        suggestion="百分比增长在大文件时会导致增长量过大，建议使用固定大小增长"
                    ))
        except Exception as e:
            logger.warning(f"检查存储失败: {e}")

        # 2. 检查日志文件大小
        try:
            result = self.connector.execute("""
                SELECT
                    DB_NAME(database_id) AS database_name,
                    name AS logical_name,
                    size * 8.0 / 1024 AS size_mb
                FROM sys.master_files
                WHERE type_desc = 'LOG'
                AND database_id > 4
            """)

            for row in result.rows:
                db_name, logical_name, size_mb = row[0], row[1], row[2]

                if size_mb > 10240:  # 超过10GB
                    items.append(InspectionItem(
                        name=f"日志文件 {db_name}.{logical_name}",
                        inspection_type=InspectionType.STORAGE,
                        risk_level=RiskLevel.HIGH,
                        description=f"日志文件大小为 {size_mb:.0f}MB",
                        current_value=f"{size_mb:.0f}MB",
                        recommended_value="配置日志备份",
                        suggestion="日志文件过大，检查是否配置了日志备份"
                    ))
        except Exception as e:
            logger.warning(f"检查日志文件失败: {e}")

        return items

    def inspect_security(self) -> List[InspectionItem]:
        """
        检查SQL Server安全配置

        返回:
            List[InspectionItem]: 安全检查项列表
        """
        items = []

        # 1. 检查SQL Server认证模式
        try:
            result = self.connector.execute("""
                SELECT SERVERPROPERTY('IsIntegratedSecurityOnly') AS is_windows_only
            """)

            if result.rows:
                is_windows_only = result.rows[0][0]

                if not is_windows_only:
                    items.append(InspectionItem(
                        name="SQL Server认证模式",
                        inspection_type=InspectionType.SECURITY,
                        risk_level=RiskLevel.MEDIUM,
                        description="SQL Server使用混合模式认证（SQL Server和Windows）",
                        current_value="混合模式",
                        recommended_value="Windows身份验证模式",
                        suggestion="如可能，建议使用Windows身份验证模式以提高安全性"
                    ))
        except Exception as e:
            logger.warning(f"检查认证模式失败: {e}")

        # 2. 检查具有sysadmin角色的用户
        try:
            result = self.connector.execute("""
                SELECT l.name AS login_name, l.type_desc
                FROM sys.server_role_members rm
                JOIN sys.server_principals r ON rm.role_principal_id = r.principal_id
                JOIN sys.server_principals l ON rm.member_principal_id = l.principal_id
                WHERE r.name = 'sysadmin'
                AND l.name NOT LIKE 'NT %'
                AND l.name NOT LIKE '##%'
            """)

            sysadmin_count = len(result.rows)
            if sysadmin_count > 5:
                items.append(InspectionItem(
                    name="sysadmin角色成员",
                    inspection_type=InspectionType.SECURITY,
                    risk_level=RiskLevel.MEDIUM,
                    description=f"有 {sysadmin_count} 个登录名具有sysadmin权限",
                    current_value=f"{sysadmin_count}个",
                    recommended_value="<= 5个",
                    suggestion="sysadmin权限过高，建议遵循最小权限原则"
                ))
        except Exception as e:
            logger.warning(f"检查sysadmin失败: {e}")

        # 3. 检查sa账户状态
        try:
            result = self.connector.execute("""
                SELECT is_disabled, create_date, modify_date
                FROM sys.sql_logins
                WHERE name = 'sa'
            """)

            if result.rows:
                is_disabled = result.rows[0][0]
                if not is_disabled:
                    items.append(InspectionItem(
                        name="sa账户状态",
                        inspection_type=InspectionType.SECURITY,
                        risk_level=RiskLevel.HIGH,
                        description="sa账户已启用",
                        current_value="启用",
                        recommended_value="禁用",
                        suggestion="sa账户是SQL Server的超级管理员，建议禁用并使用具有最小权限的专用账户"
                    ))
        except Exception as e:
            logger.warning(f"检查sa账户失败: {e}")

        # 4. 检查密码策略
        try:
            result = self.connector.execute("""
                SELECT name, is_policy_checked, is_expiration_checked
                FROM sys.sql_logins
                WHERE is_policy_checked = 0 OR is_expiration_checked = 0
            """)

            for row in result.rows:
                login_name = row[0]
                is_policy_checked = row[1]
                is_expiration_checked = row[2]

                if not is_policy_checked:
                    items.append(InspectionItem(
                        name=f"登录名 {login_name} 密码策略",
                        inspection_type=InspectionType.SECURITY,
                        risk_level=RiskLevel.MEDIUM,
                        description=f"登录名 {login_name} 未强制密码策略",
                        current_value="未强制",
                        recommended_value="强制密码策略",
                        suggestion="建议启用Windows密码策略以增强安全性"
                    ))
        except Exception as e:
            logger.warning(f"检查密码策略失败: {e}")

        return items

    def inspect_capacity(self) -> List[InspectionItem]:
        """
        检查SQL Server容量使用情况

        返回:
            List[InspectionItem]: 容量检查项列表
        """
        items = []

        # 1. 检查磁盘空间
        try:
            result = self.connector.execute("""
                SELECT DISTINCT
                    SUBSTRING(physical_name, 1, 1) AS drive_letter,
                    volume_mount_point,
                    total_bytes / 1024 / 1024 / 1024 AS total_gb,
                    available_bytes / 1024 / 1024 / 1024 AS available_gb
                FROM sys.master_files mf
                CROSS APPLY sys.dm_os_volume_stats(mf.database_id, mf.file_id)
            """)

            for row in result.rows:
                drive_letter = row[0]
                volume_mount_point = row[1]
                total_gb = row[2]
                available_gb = row[3]

                usage_ratio = ((total_gb - available_gb) / total_gb) * 100 if total_gb > 0 else 0

                if usage_ratio > 90:
                    items.append(InspectionItem(
                        name=f"磁盘空间 {volume_mount_point}",
                        inspection_type=InspectionType.CAPACITY,
                        risk_level=RiskLevel.CRITICAL,
                        description=f"磁盘 {volume_mount_point} 使用率 {usage_ratio:.1f}%",
                        current_value=f"已用 {total_gb - available_gb:.0f}GB / 总计 {total_gb:.0f}GB",
                        recommended_value="< 90%",
                        suggestion="磁盘空间严重不足，需要立即清理或扩容"
                    ))
                elif usage_ratio > 80:
                    items.append(InspectionItem(
                        name=f"磁盘空间 {volume_mount_point}",
                        inspection_type=InspectionType.CAPACITY,
                        risk_level=RiskLevel.HIGH,
                        description=f"磁盘 {volume_mount_point} 使用率 {usage_ratio:.1f}%",
                        current_value=f"已用 {total_gb - available_gb:.0f}GB / 总计 {total_gb:.0f}GB",
                        recommended_value="< 80%",
                        suggestion="磁盘空间紧张，建议规划扩容"
                    ))
        except Exception as e:
            logger.warning(f"检查磁盘空间失败: {e}")

        # 2. 检查数据库增长趋势
        try:
            result = self.connector.execute("""
                SELECT
                    DB_NAME(database_id) AS database_name,
                    SUM(size * 8.0 / 1024 / 1024) AS total_size_gb
                FROM sys.master_files
                WHERE database_id > 4
                GROUP BY database_id
                ORDER BY total_size_gb DESC
            """)

            for row in result.rows:
                db_name, total_size_gb = row[0], row[1]

                if total_size_gb > 100:  # 超过100GB
                    items.append(InspectionItem(
                        name=f"数据库 {db_name} 大小",
                        inspection_type=InspectionType.CAPACITY,
                        risk_level=RiskLevel.MEDIUM,
                        description=f"数据库 {db_name} 总大小为 {total_size_gb:.1f}GB",
                        current_value=f"{total_size_gb:.1f}GB",
                        recommended_value="考虑分区或归档",
                        suggestion="大型数据库需要考虑分区策略和归档方案"
                    ))
        except Exception as e:
            logger.warning(f"检查数据库大小失败: {e}")

        return items

    def get_instance_info(self) -> Dict[str, Any]:
        """
        获取SQL Server实例基本信息

        返回:
            Dict[str, Any]: 实例信息字典
        """
        version_info = self._get_version_info()

        try:
            # 获取数据库数量
            db_result = self.connector.execute("""
                SELECT COUNT(*) FROM sys.databases WHERE state = 0
            """)
            database_count = db_result.rows[0][0] if db_result.rows else 0

            # 获取总大小
            size_result = self.connector.execute("""
                SELECT SUM(size * 8.0 / 1024 / 1024) FROM sys.master_files
            """)
            total_size_gb = size_result.rows[0][0] if size_result.rows else 0

            return {
                'version': version_info.get('product_version', 'Unknown'),
                'edition': version_info.get('edition', 'Unknown'),
                'databases': database_count,
                'total_size_gb': round(total_size_gb, 2),
                'uptime': self._get_uptime(),
                'dialect': 'mssql'
            }
        except Exception as e:
            logger.error(f"获取实例信息失败: {e}")
            return {
                'version': version_info.get('product_version', 'Unknown'),
                'edition': version_info.get('edition', 'Unknown'),
                'databases': 0,
                'total_size_gb': 0,
                'uptime': 'Unknown',
                'dialect': 'mssql'
            }

    def _get_uptime(self) -> str:
        """
        获取SQL Server运行时间

        返回:
            str: 运行时间字符串
        """
        try:
            result = self.connector.execute("""
                SELECT DATEDIFF(HOUR, sqlserver_start_time, GETDATE())
                FROM sys.dm_os_sys_info
            """)

            if result.rows:
                hours = result.rows[0][0]
                days = hours // 24
                remaining_hours = hours % 24
                return f"{days}天 {remaining_hours}小时"
        except Exception as e:
            logger.warning(f"获取运行时间失败: {e}")

        return "Unknown"
