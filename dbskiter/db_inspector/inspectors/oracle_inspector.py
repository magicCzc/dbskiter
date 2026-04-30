"""
Oracle巡检器

提供Oracle数据库的专项巡检能力
"""

import logging
from typing import List, Dict, Any

from dbskiter.shared.unified_connector import UnifiedConnector
from .base import BaseInspector
from ..models import InspectionItem, InspectionType, RiskLevel

logger = logging.getLogger(__name__)


class OracleInspector(BaseInspector):
    """
    Oracle数据库巡检器

    提供Oracle特有的配置、性能、存储、安全检查
    """

    # Oracle配置检查标准
    CONFIG_STANDARDS = {
        'processes': {
            'min': 150,
            'description': '最大进程数'
        },
        'sessions': {
            'min': 200,
            'description': '最大会话数'
        },
        'open_cursors': {
            'min': 300,
            'description': '最大打开游标数'
        },
        'db_cache_size': {
            'min': '100M',
            'description': '数据库缓存大小'
        },
        'shared_pool_size': {
            'min': '100M',
            'description': '共享池大小'
        },
        'pga_aggregate_target': {
            'min': '100M',
            'description': 'PGA聚合目标'
        }
    }

    # 性能阈值
    BUFFER_CACHE_HIT_RATIO_THRESHOLD = 95.0
    BUFFER_CACHE_HIT_RATIO_CRITICAL = 90.0
    LIBRARY_CACHE_HIT_RATIO_THRESHOLD = 95.0

    def get_instance_info(self) -> Dict[str, Any]:
        """获取Oracle实例信息"""
        info = super().get_instance_info()

        try:
            # 获取版本
            result = self._execute_query("SELECT * FROM v$version WHERE rownum = 1")
            if result:
                info['version'] = result[0][0]

            # 获取实例名
            result = self._execute_query("SELECT instance_name FROM v$instance")
            if result:
                info['instance_name'] = result[0][0]

            # 获取数据库名
            result = self._execute_query("SELECT name FROM v$database")
            if result:
                info['database_name'] = result[0][0]

        except Exception as e:
            logger.warning(f"获取Oracle实例信息失败: {e}")

        return info

    def inspect_configuration(self) -> List[InspectionItem]:
        """检查Oracle配置"""
        items = []

        for param_name, standard in self.CONFIG_STANDARDS.items():
            try:
                # 使用 f-string 避免参数绑定兼容性问题
                result = self._execute_query(
                    f"SELECT value FROM v$parameter WHERE name = '{param_name}'"
                )
                actual_value = result[0][0] if result else None

                if actual_value is None:
                    continue

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
                    actual_value=str(actual_value),
                    reference=f">= {standard.get('min', 'N/A')}",
                    suggestion=suggestion
                ))

            except Exception as e:
                logger.warning(f"检查配置项 {param_name} 失败: {e}")

        return items

    def inspect_performance(self) -> List[InspectionItem]:
        """检查Oracle性能"""
        items = []

        try:
            # 检查Buffer Cache命中率
            result = self._execute_query("""
                SELECT 
                    ROUND((1 - (physical_reads / NULLIF(db_block_gets + consistent_gets, 0))) * 100, 2)
                FROM v$buffer_pool_statistics
                WHERE name = 'DEFAULT'
            """)
            hit_ratio = float(result[0][0]) if result and result[0][0] else 0

            if hit_ratio < self.BUFFER_CACHE_HIT_RATIO_THRESHOLD:
                items.append(self._create_item(
                    name="Buffer Cache命中率",
                    insp_type=InspectionType.PERFORMANCE,
                    risk_level=RiskLevel.HIGH if hit_ratio < self.BUFFER_CACHE_HIT_RATIO_CRITICAL else RiskLevel.MEDIUM,
                    status="warning",
                    description=f"Buffer Cache命中率低于{self.BUFFER_CACHE_HIT_RATIO_THRESHOLD}%",
                    actual_value=f"{hit_ratio:.2f}%",
                    reference=f">= {self.BUFFER_CACHE_HIT_RATIO_THRESHOLD}%",
                    suggestion="考虑增加db_cache_size"
                ))
            else:
                items.append(self._create_item(
                    name="Buffer Cache命中率",
                    insp_type=InspectionType.PERFORMANCE,
                    risk_level=RiskLevel.INFO,
                    status="pass",
                    description="Buffer Cache命中率正常",
                    actual_value=f"{hit_ratio:.2f}%",
                    reference=f">= {self.BUFFER_CACHE_HIT_RATIO_THRESHOLD}%"
                ))

            # 检查Library Cache命中率
            result = self._execute_query("""
                SELECT ROUND(100 * (1 - SUM(reloads) / NULLIF(SUM(pins), 0)), 2)
                FROM v$librarycache
            """)
            lib_cache_hit = float(result[0][0]) if result and result[0][0] else 0

            if lib_cache_hit < self.LIBRARY_CACHE_HIT_RATIO_THRESHOLD:
                items.append(self._create_item(
                    name="Library Cache命中率",
                    insp_type=InspectionType.PERFORMANCE,
                    risk_level=RiskLevel.MEDIUM,
                    status="warning",
                    description=f"Library Cache命中率低于{self.LIBRARY_CACHE_HIT_RATIO_THRESHOLD}%",
                    actual_value=f"{lib_cache_hit:.2f}%",
                    reference=f">= {self.LIBRARY_CACHE_HIT_RATIO_THRESHOLD}%",
                    suggestion="考虑增加shared_pool_size"
                ))
            else:
                items.append(self._create_item(
                    name="Library Cache命中率",
                    insp_type=InspectionType.PERFORMANCE,
                    risk_level=RiskLevel.INFO,
                    status="pass",
                    description="Library Cache命中率正常",
                    actual_value=f"{lib_cache_hit:.2f}%",
                    reference=f">= {self.LIBRARY_CACHE_HIT_RATIO_THRESHOLD}%"
                ))

            # 检查活动会话数
            result = self._execute_query("""
                SELECT COUNT(*) FROM v$session WHERE status = 'ACTIVE' AND type = 'USER'
            """)
            active_sessions = result[0][0] if result else 0

            # 获取最大会话数
            result = self._execute_query("SELECT value FROM v$parameter WHERE name = 'sessions'")
            max_sessions = int(result[0][0]) if result else 1
            usage_rate = (active_sessions / max_sessions) * 100

            if usage_rate > self.CONNECTION_USAGE_THRESHOLD:
                items.append(self._create_item(
                    name="活动会话使用率",
                    insp_type=InspectionType.PERFORMANCE,
                    risk_level=RiskLevel.HIGH if usage_rate > self.CONNECTION_USAGE_CRITICAL else RiskLevel.MEDIUM,
                    status="warning",
                    description=f"活动会话使用率过高: {usage_rate:.1f}%",
                    actual_value=f"{active_sessions}/{max_sessions} ({usage_rate:.1f}%)",
                    reference=f"< {self.CONNECTION_USAGE_THRESHOLD}%",
                    suggestion="检查并优化长时间运行的会话"
                ))
            else:
                items.append(self._create_item(
                    name="活动会话使用率",
                    insp_type=InspectionType.PERFORMANCE,
                    risk_level=RiskLevel.INFO,
                    status="pass",
                    description=f"活动会话使用率正常: {usage_rate:.1f}%",
                    actual_value=f"{active_sessions}/{max_sessions} ({usage_rate:.1f}%)",
                    reference=f"< {self.CONNECTION_USAGE_THRESHOLD}%"
                ))

        except Exception as e:
            logger.warning(f"性能检查失败: {e}")

        return items

    def inspect_storage(self) -> List[InspectionItem]:
        """检查Oracle存储"""
        items = []

        try:
            # 检查表空间使用情况
            result = self._execute_query("""
                SELECT 
                    df.tablespace_name,
                    ROUND(df.bytes / 1024 / 1024 / 1024, 2) AS total_gb,
                    ROUND(NVL(fs.bytes, 0) / 1024 / 1024 / 1024, 2) AS free_gb,
                    ROUND((df.bytes - NVL(fs.bytes, 0)) / df.bytes * 100, 2) AS used_pct
                FROM (
                    SELECT tablespace_name, SUM(bytes) bytes
                    FROM dba_data_files
                    GROUP BY tablespace_name
                ) df
                LEFT JOIN (
                    SELECT tablespace_name, SUM(bytes) bytes
                    FROM dba_free_space
                    GROUP BY tablespace_name
                ) fs ON df.tablespace_name = fs.tablespace_name
                ORDER BY used_pct DESC
            """)

            if result:
                for row in result:
                    tablespace_name = row[0]
                    total_gb = row[1]
                    free_gb = row[2]
                    used_pct = row[3]

                    if used_pct > 90:
                        risk_level = RiskLevel.HIGH
                        status = "warning"
                    elif used_pct > 80:
                        risk_level = RiskLevel.MEDIUM
                        status = "warning"
                    else:
                        risk_level = RiskLevel.INFO
                        status = "pass"

                    items.append(self._create_item(
                        name=f"表空间: {tablespace_name}",
                        insp_type=InspectionType.STORAGE,
                        risk_level=risk_level,
                        status=status,
                        description=f"表空间 {tablespace_name} 使用情况",
                        actual_value=f"已用{used_pct}% ({total_gb - free_gb:.2f}GB / {total_gb}GB)",
                        reference="< 80%",
                        suggestion="考虑增加数据文件或清理数据" if used_pct > 80 else None
                    ))

            # 检查大表
            # 使用 f-string 避免参数绑定兼容性问题
            result = self._execute_query(f"""
                SELECT * FROM (
                    SELECT owner, segment_name, segment_type,
                           ROUND(bytes / 1024 / 1024, 2) AS size_mb
                    FROM dba_segments
                    WHERE segment_type IN ('TABLE', 'TABLE PARTITION')
                    AND bytes > {self.TABLE_SIZE_THRESHOLD_MB} * 1024 * 1024
                    ORDER BY bytes DESC
                ) WHERE ROWNUM <= 10
            """)

            if result:
                for row in result:
                    items.append(self._create_item(
                        name=f"大表检查: {row[0]}.{row[1]}",
                        insp_type=InspectionType.STORAGE,
                        risk_level=RiskLevel.MEDIUM,
                        status="warning",
                        description=f"表大小超过阈值 {self.TABLE_SIZE_THRESHOLD_MB}MB",
                        actual_value=f"{row[3]}MB",
                        reference=f"< {self.TABLE_SIZE_THRESHOLD_MB}MB",
                        suggestion="考虑归档历史数据或分区"
                    ))

        except Exception as e:
            logger.warning(f"存储检查失败: {e}")

        return items

    def inspect_security(self) -> List[InspectionItem]:
        """检查Oracle安全"""
        items = []

        try:
            # 检查具有DBA角色的用户
            result = self._execute_query("""
                SELECT grantee, COUNT(*) 
                FROM dba_role_privs 
                WHERE granted_role = 'DBA'
                GROUP BY grantee
            """)

            if result:
                for row in result:
                    if row[0] not in ['SYS', 'SYSTEM']:
                        items.append(self._create_item(
                            name=f"DBA权限检查: {row[0]}",
                            insp_type=InspectionType.SECURITY,
                            risk_level=RiskLevel.HIGH,
                            status="warning",
                            description=f"用户 {row[0]} 具有DBA角色",
                            suggestion="审查DBA权限分配，遵循最小权限原则"
                        ))

            # 检查默认密码的用户
            result = self._execute_query("""
                SELECT username FROM dba_users
                WHERE password = 'EXTERNAL'
                OR password IS NULL
            """)

            if result:
                for row in result:
                    items.append(self._create_item(
                        name=f"空密码检查: {row[0]}",
                        insp_type=InspectionType.SECURITY,
                        risk_level=RiskLevel.CRITICAL,
                        status="warning",
                        description=f"用户 {row[0]} 密码为空或外部认证",
                        suggestion="为所有用户设置强密码"
                    ))

            # 检查审计是否启用
            result = self._execute_query("SELECT value FROM v$parameter WHERE name = 'audit_trail'")
            audit_trail = result[0][0] if result else 'NONE'

            if audit_trail == 'NONE':
                items.append(self._create_item(
                    name="审计检查",
                    insp_type=InspectionType.SECURITY,
                    risk_level=RiskLevel.MEDIUM,
                    status="warning",
                    description="数据库审计未启用",
                    actual_value=audit_trail,
                    reference="DB或XML",
                    suggestion="建议启用审计功能以追踪关键操作"
                ))
            else:
                items.append(self._create_item(
                    name="审计检查",
                    insp_type=InspectionType.SECURITY,
                    risk_level=RiskLevel.INFO,
                    status="pass",
                    description="数据库审计已启用",
                    actual_value=audit_trail
                ))

        except Exception as e:
            logger.warning(f"安全检查失败: {e}")

        return items

    def inspect_capacity(self) -> List[InspectionItem]:
        """检查Oracle容量"""
        items = []

        try:
            # 检查数据库总大小
            result = self._execute_query("""
                SELECT ROUND(SUM(bytes) / 1024 / 1024 / 1024, 2)
                FROM dba_data_files
            """)

            if result:
                total_size_gb = result[0][0]
                items.append(self._create_item(
                    name="数据库总容量",
                    insp_type=InspectionType.CAPACITY,
                    risk_level=RiskLevel.INFO,
                    status="pass",
                    description="数据库数据文件总大小",
                    actual_value=f"{total_size_gb}GB"
                ))

            # 检查归档日志使用情况
            result = self._execute_query("""
                SELECT ROUND(SUM(blocks * block_size) / 1024 / 1024 / 1024, 2)
                FROM v$archived_log
                WHERE deleted = 'NO'
            """)

            if result and result[0][0]:
                archivelog_size_gb = result[0][0]
                items.append(self._create_item(
                    name="归档日志容量",
                    insp_type=InspectionType.CAPACITY,
                    risk_level=RiskLevel.INFO,
                    status="pass",
                    description="未删除的归档日志总大小",
                    actual_value=f"{archivelog_size_gb}GB",
                    suggestion="定期清理过期归档日志"
                ))

        except Exception as e:
            logger.warning(f"容量检查失败: {e}")

        return items
