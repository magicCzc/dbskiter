"""
MySQL巡检器

提供MySQL数据库的专项巡检能力
"""

import logging
from typing import List, Dict, Any, Optional

from dbskiter.shared.unified_connector import UnifiedConnector
from .base import BaseInspector
from ..models import InspectionItem, InspectionType, RiskLevel

logger = logging.getLogger(__name__)


class MySQLInspector(BaseInspector):
    """
    MySQL数据库巡检器

    提供MySQL特有的配置、性能、存储、安全检查
    """

    # MySQL配置检查标准 - 扩充到20+项
    CONFIG_STANDARDS = {
        'innodb_buffer_pool_size': {
            'min': '1G',
            'recommend': '物理内存的50-70%',
            'description': 'InnoDB缓冲池大小'
        },
        'max_connections': {
            'min': 100,
            'max': 10000,
            'recommend': '根据业务需求设置',
            'description': '最大连接数'
        },
        'innodb_log_file_size': {
            'min': '48M',
            'recommend': '128M-1G',
            'description': 'InnoDB日志文件大小'
        },
        'slow_query_log': {
            'expected': 'ON',
            'description': '慢查询日志'
        },
        'long_query_time': {
            'max': 2,
            'recommend': '1-2秒',
            'description': '慢查询阈值'
        },
        'binlog_format': {
            'expected': 'ROW',
            'description': '二进制日志格式'
        },
        'innodb_flush_log_at_trx_commit': {
            'expected': '1',
            'description': 'InnoDB事务日志刷盘策略',
            'suggestion': '生产环境建议设置为1，确保数据安全'
        },
        'sync_binlog': {
            'expected': '1',
            'description': 'Binlog同步策略',
            'suggestion': '生产环境建议设置为1，确保数据安全'
        },
        'innodb_flush_method': {
            'expected': 'O_DIRECT',
            'description': 'InnoDB刷盘方式',
            'suggestion': '建议使用O_DIRECT，避免双重缓存'
        },
        'character_set_server': {
            'expected': 'utf8mb4',
            'description': '服务器默认字符集',
            'suggestion': '建议使用utf8mb4，支持完整的Unicode字符'
        },
        'collation_server': {
            'expected': 'utf8mb4_unicode_ci',
            'description': '服务器默认排序规则',
            'suggestion': '建议使用utf8mb4_unicode_ci'
        },
        'log_bin': {
            'expected': 'ON',
            'description': '二进制日志开关',
            'suggestion': '建议开启binlog，用于数据恢复和复制'
        },
        'expire_logs_days': {
            'min': 7,
            'recommend': '7-30天',
            'description': 'Binlog过期天数',
            'suggestion': '建议设置合理的过期天数，避免磁盘空间不足'
        },
        'innodb_file_per_table': {
            'expected': 'ON',
            'description': '独立表空间',
            'suggestion': '建议开启，便于表空间管理'
        },
        'query_cache_type': {
            'expected': 'OFF',
            'description': '查询缓存',
            'suggestion': 'MySQL 5.7+建议关闭，8.0已移除'
        },
        'thread_cache_size': {
            'min': 16,
            'recommend': '根据连接数调整',
            'description': '线程缓存大小',
            'suggestion': '建议根据并发连接数调整'
        },
        'table_open_cache': {
            'min': 2000,
            'recommend': '根据表数量调整',
            'description': '表缓存数量',
            'suggestion': '建议根据数据库表数量调整'
        },
        'innodb_read_io_threads': {
            'min': 4,
            'recommend': '4-8',
            'description': 'InnoDB读IO线程数'
        },
        'innodb_write_io_threads': {
            'min': 4,
            'recommend': '4-8',
            'description': 'InnoDB写IO线程数'
        }
    }

    # 性能阈值
    BUFFER_POOL_HIT_RATE_THRESHOLD = 95.0
    BUFFER_POOL_HIT_RATE_CRITICAL = 90.0
    THREAD_CACHE_HIT_RATE_THRESHOLD = 90.0
    TABLE_CACHE_HIT_RATE_THRESHOLD = 85.0
    TEMP_TABLE_DISK_RATIO_THRESHOLD = 10.0
    SORT_MERGE_PASSES_THRESHOLD = 1000

    def __init__(self, connector: UnifiedConnector):
        super().__init__(connector)
        self._check_performance_schema()

    def _escape_db_name(self, db_name: str) -> str:
        """
        安全地转义数据库名，防止SQL注入

        参数:
            db_name: 原始数据库名

        返回:
            str: 转义后的数据库名（带单引号）
        """
        if not db_name:
            return "''"

        # 只允许字母、数字、下划线
        # 移除所有其他字符
        import re
        safe_name = re.sub(r"[^a-zA-Z0-9_]", "", db_name)

        # 返回带单引号的字符串
        return f"'{safe_name}'"

    def _check_performance_schema(self):
        """检查performance_schema是否可用"""
        try:
            result = self._execute_query(
                "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'performance_schema'"
            )
            self._performance_schema_available = result and result[0][0] > 0
        except Exception:
            self._performance_schema_available = False

    def get_instance_info(self) -> Dict[str, Any]:
        """获取MySQL实例信息"""
        info = super().get_instance_info()

        try:
            # 获取版本
            result = self._execute_query("SELECT VERSION()")
            if result:
                info['version'] = result[0][0]

            # 获取实例ID
            result = self._execute_query("SELECT @@server_id")
            if result:
                info['server_id'] = result[0][0]

            # 获取数据库名
            result = self._execute_query("SELECT DATABASE()")
            if result and result[0][0]:
                info['database_name'] = result[0][0]
            else:
                info['database_name'] = self.connector.database

            # 构建清晰的实例名称: 数据库名@主机:端口
            db_name = info.get('database_name', 'unknown')
            host = self.connector.host
            port = self.connector.port
            info['instance_name'] = f"{db_name}@{host}:{port}"

        except Exception as e:
            logger.warning(f"获取MySQL实例信息失败: {e}")

        return info

    def inspect_configuration(self) -> List[InspectionItem]:
        """检查MySQL配置"""
        items = []

        for var_name, standard in self.CONFIG_STANDARDS.items():
            try:
                result = self._execute_query(
                    f"SHOW VARIABLES LIKE '{var_name}'"
                )
                actual_value = result[0][1] if result else None

                if actual_value is None:
                    continue

                status = 'pass'
                risk_level = RiskLevel.INFO
                suggestion = None

                if 'expected' in standard:
                    if str(actual_value).upper() != standard['expected'].upper():
                        status = 'warning'
                        risk_level = RiskLevel.MEDIUM
                        suggestion = f"建议设置为 {standard['expected']}"

                items.append(self._create_item(
                    name=f"配置检查: {var_name}",
                    insp_type=InspectionType.CONFIGURATION,
                    risk_level=risk_level,
                    status=status,
                    description=standard['description'],
                    actual_value=str(actual_value),
                    reference=standard.get('expected') or standard.get('recommend'),
                    suggestion=suggestion
                ))

            except Exception as e:
                logger.warning(f"检查配置项 {var_name} 失败: {e}")

        return items

    def inspect_performance(self) -> List[InspectionItem]:
        """检查MySQL性能 - 扩充到15+项"""
        items = []

        try:
            # 1. 检查缓冲池命中率
            result = self._execute_query("""
                SELECT
                    (1 - (SELECT VARIABLE_VALUE FROM performance_schema.global_status
                          WHERE VARIABLE_NAME = 'Innodb_buffer_pool_reads') /
                    NULLIF((SELECT VARIABLE_VALUE FROM performance_schema.global_status
                            WHERE VARIABLE_NAME = 'Innodb_buffer_pool_read_requests'), 0)) * 100
            """)
            hit_rate = float(result[0][0]) if result and result[0][0] else 0

            if hit_rate < self.BUFFER_POOL_HIT_RATE_THRESHOLD:
                items.append(self._create_item(
                    name="InnoDB缓冲池命中率",
                    insp_type=InspectionType.PERFORMANCE,
                    risk_level=RiskLevel.HIGH if hit_rate < self.BUFFER_POOL_HIT_RATE_CRITICAL else RiskLevel.MEDIUM,
                    status="warning",
                    description=f"InnoDB缓冲池命中率低于{self.BUFFER_POOL_HIT_RATE_THRESHOLD}%",
                    actual_value=f"{hit_rate:.2f}%",
                    reference=f">= {self.BUFFER_POOL_HIT_RATE_THRESHOLD}%",
                    suggestion="考虑增加innodb_buffer_pool_size"
                ))
            else:
                items.append(self._create_item(
                    name="InnoDB缓冲池命中率",
                    insp_type=InspectionType.PERFORMANCE,
                    risk_level=RiskLevel.INFO,
                    status="pass",
                    description="InnoDB缓冲池命中率正常",
                    actual_value=f"{hit_rate:.2f}%",
                    reference=f">= {self.BUFFER_POOL_HIT_RATE_THRESHOLD}%"
                ))

            # 2. 检查连接数使用率
            result = self._execute_query("""
                SELECT
                    (SELECT VARIABLE_VALUE FROM performance_schema.global_status WHERE VARIABLE_NAME = 'Threads_connected'),
                    (SELECT VARIABLE_VALUE FROM performance_schema.global_variables WHERE VARIABLE_NAME = 'max_connections')
            """)
            if result:
                connected = float(result[0][0] or 0)
                max_conn = float(result[0][1] or 1)
                usage_rate = (connected / max_conn) * 100

                if usage_rate > self.CONNECTION_USAGE_THRESHOLD:
                    items.append(self._create_item(
                        name="连接数使用率",
                        insp_type=InspectionType.PERFORMANCE,
                        risk_level=RiskLevel.HIGH if usage_rate > self.CONNECTION_USAGE_CRITICAL else RiskLevel.MEDIUM,
                        status="warning",
                        description=f"连接数使用率过高: {usage_rate:.1f}%",
                        actual_value=f"{usage_rate:.1f}%",
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
                        actual_value=f"{usage_rate:.1f}%",
                        reference=f"< {self.CONNECTION_USAGE_THRESHOLD}%"
                    ))

            # 3. 检查线程缓存命中率
            result = self._execute_query("""
                SELECT 
                    (1 - (SELECT VARIABLE_VALUE FROM performance_schema.global_status WHERE VARIABLE_NAME = 'Threads_created') /
                    NULLIF((SELECT VARIABLE_VALUE FROM performance_schema.global_status WHERE VARIABLE_NAME = 'Connections'), 0)) * 100
            """)
            thread_cache_hit = float(result[0][0]) if result and result[0][0] else 0
            
            if thread_cache_hit < self.THREAD_CACHE_HIT_RATE_THRESHOLD:
                items.append(self._create_item(
                    name="线程缓存命中率",
                    insp_type=InspectionType.PERFORMANCE,
                    risk_level=RiskLevel.MEDIUM,
                    status="warning",
                    description=f"线程缓存命中率低于{self.THREAD_CACHE_HIT_RATE_THRESHOLD}%",
                    actual_value=f"{thread_cache_hit:.2f}%",
                    reference=f">= {self.THREAD_CACHE_HIT_RATE_THRESHOLD}%",
                    suggestion="考虑增加thread_cache_size"
                ))
            else:
                items.append(self._create_item(
                    name="线程缓存命中率",
                    insp_type=InspectionType.PERFORMANCE,
                    risk_level=RiskLevel.INFO,
                    status="pass",
                    description="线程缓存命中率正常",
                    actual_value=f"{thread_cache_hit:.2f}%",
                    reference=f">= {self.THREAD_CACHE_HIT_RATE_THRESHOLD}%"
                ))

            # 4. 检查表缓存命中率
            # 使用正确的计算公式：hits / (hits + misses) * 100
            result = self._execute_query("""
                SELECT 
                    (SELECT VARIABLE_VALUE FROM performance_schema.global_status WHERE VARIABLE_NAME = 'Table_open_cache_hits'),
                    (SELECT VARIABLE_VALUE FROM performance_schema.global_status WHERE VARIABLE_NAME = 'Table_open_cache_misses')
            """)

            if result and result[0]:
                hits = float(result[0][0] or 0)
                misses = float(result[0][1] or 0)
                total = hits + misses

                if total > 0:
                    table_cache_hit = (hits / total) * 100
                else:
                    table_cache_hit = 100.0  # 如果没有数据，假设命中率为100%

                # 确保命中率在合理范围内
                table_cache_hit = max(0.0, min(100.0, table_cache_hit))

                if table_cache_hit < self.TABLE_CACHE_HIT_RATE_THRESHOLD:
                    items.append(self._create_item(
                        name="表缓存命中率",
                        insp_type=InspectionType.PERFORMANCE,
                        risk_level=RiskLevel.MEDIUM,
                        status="warning",
                        description=f"表缓存命中率低于{self.TABLE_CACHE_HIT_RATE_THRESHOLD}%",
                        actual_value=f"{table_cache_hit:.2f}%",
                        reference=f">= {self.TABLE_CACHE_HIT_RATE_THRESHOLD}%",
                        suggestion="考虑增加table_open_cache"
                    ))
                else:
                    items.append(self._create_item(
                        name="表缓存命中率",
                        insp_type=InspectionType.PERFORMANCE,
                        risk_level=RiskLevel.INFO,
                        status="pass",
                        description="表缓存命中率正常",
                        actual_value=f"{table_cache_hit:.2f}%",
                        reference=f">= {self.TABLE_CACHE_HIT_RATE_THRESHOLD}%"
                    ))
            else:
                # 如果无法获取数据，跳过此项
                pass

            # 5. 检查临时表磁盘使用率
            result = self._execute_query("""
                SELECT 
                    (SELECT VARIABLE_VALUE FROM performance_schema.global_status WHERE VARIABLE_NAME = 'Created_tmp_disk_tables'),
                    (SELECT VARIABLE_VALUE FROM performance_schema.global_status WHERE VARIABLE_NAME = 'Created_tmp_tables')
            """)
            if result:
                tmp_disk = float(result[0][0] or 0)
                tmp_total = float(result[0][1] or 1)
                tmp_disk_ratio = (tmp_disk / tmp_total) * 100 if tmp_total > 0 else 0
                
                if tmp_disk_ratio > self.TEMP_TABLE_DISK_RATIO_THRESHOLD:
                    items.append(self._create_item(
                        name="临时表磁盘使用率",
                        insp_type=InspectionType.PERFORMANCE,
                        risk_level=RiskLevel.HIGH,
                        status="warning",
                        description=f"磁盘临时表比例过高: {tmp_disk_ratio:.2f}%",
                        actual_value=f"{tmp_disk_ratio:.2f}%",
                        reference=f"< {self.TEMP_TABLE_DISK_RATIO_THRESHOLD}%",
                        suggestion="优化查询，避免使用BLOB/TEXT字段或增加tmp_table_size"
                    ))
                else:
                    items.append(self._create_item(
                        name="临时表磁盘使用率",
                        insp_type=InspectionType.PERFORMANCE,
                        risk_level=RiskLevel.INFO,
                        status="pass",
                        description="临时表磁盘使用率正常",
                        actual_value=f"{tmp_disk_ratio:.2f}%",
                        reference=f"< {self.TEMP_TABLE_DISK_RATIO_THRESHOLD}%"
                    ))

            # 6. 检查锁等待情况
            result = self._execute_query("""
                SELECT 
                    (SELECT VARIABLE_VALUE FROM performance_schema.global_status WHERE VARIABLE_NAME = 'Table_locks_waited'),
                    (SELECT VARIABLE_VALUE FROM performance_schema.global_status WHERE VARIABLE_NAME = 'Table_locks_immediate')
            """)
            if result:
                locks_waited = float(result[0][0] or 0)
                locks_immediate = float(result[0][1] or 1)
                lock_ratio = (locks_waited / (locks_waited + locks_immediate)) * 100 if (locks_waited + locks_immediate) > 0 else 0
                
                if lock_ratio > 1.0:
                    items.append(self._create_item(
                        name="表锁等待率",
                        insp_type=InspectionType.PERFORMANCE,
                        risk_level=RiskLevel.HIGH,
                        status="warning",
                        description=f"表锁等待率过高: {lock_ratio:.2f}%",
                        actual_value=f"{lock_ratio:.2f}%",
                        reference="< 1%",
                        suggestion="优化查询，减少表锁竞争"
                    ))
                else:
                    items.append(self._create_item(
                        name="表锁等待率",
                        insp_type=InspectionType.PERFORMANCE,
                        risk_level=RiskLevel.INFO,
                        status="pass",
                        description="表锁等待率正常",
                        actual_value=f"{lock_ratio:.2f}%",
                        reference="< 1%"
                    ))

            # 7. 检查行锁等待
            result = self._execute_query("""
                SELECT VARIABLE_VALUE FROM performance_schema.global_status 
                WHERE VARIABLE_NAME = 'Innodb_row_lock_waits'
            """)
            row_lock_waits = int(result[0][0]) if result else 0
            
            if row_lock_waits > 100:
                items.append(self._create_item(
                    name="InnoDB行锁等待次数",
                    insp_type=InspectionType.PERFORMANCE,
                    risk_level=RiskLevel.HIGH,
                    status="warning",
                    description=f"行锁等待次数过多: {row_lock_waits}",
                    actual_value=str(row_lock_waits),
                    reference="< 100",
                    suggestion="检查并优化长事务，减少锁竞争"
                ))
            else:
                items.append(self._create_item(
                    name="InnoDB行锁等待次数",
                    insp_type=InspectionType.PERFORMANCE,
                    risk_level=RiskLevel.INFO,
                    status="pass",
                    description="行锁等待次数正常",
                    actual_value=str(row_lock_waits),
                    reference="< 100"
                ))

            # 8. 检查排序合并次数
            result = self._execute_query("""
                SELECT VARIABLE_VALUE FROM performance_schema.global_status 
                WHERE VARIABLE_NAME = 'Sort_merge_passes'
            """)
            sort_merge_passes = int(result[0][0]) if result else 0
            
            if sort_merge_passes > self.SORT_MERGE_PASSES_THRESHOLD:
                items.append(self._create_item(
                    name="排序合并次数",
                    insp_type=InspectionType.PERFORMANCE,
                    risk_level=RiskLevel.MEDIUM,
                    status="warning",
                    description=f"排序合并次数过多: {sort_merge_passes}",
                    actual_value=str(sort_merge_passes),
                    reference=f"< {self.SORT_MERGE_PASSES_THRESHOLD}",
                    suggestion="考虑增加sort_buffer_size"
                ))
            else:
                items.append(self._create_item(
                    name="排序合并次数",
                    insp_type=InspectionType.PERFORMANCE,
                    risk_level=RiskLevel.INFO,
                    status="pass",
                    description="排序合并次数正常",
                    actual_value=str(sort_merge_passes),
                    reference=f"< {self.SORT_MERGE_PASSES_THRESHOLD}"
                ))

            # 9. 检查QPS（每秒查询数）
            result = self._execute_query("""
                SELECT VARIABLE_VALUE FROM performance_schema.global_status 
                WHERE VARIABLE_NAME = 'Queries'
            """)
            queries = int(result[0][0]) if result else 0
            
            items.append(self._create_item(
                name="总查询次数",
                insp_type=InspectionType.PERFORMANCE,
                risk_level=RiskLevel.INFO,
                status="pass",
                description="数据库总查询次数",
                actual_value=str(queries),
                reference="N/A"
            ))

            # 10. 检查活跃线程数
            result = self._execute_query("""
                SELECT VARIABLE_VALUE FROM performance_schema.global_status 
                WHERE VARIABLE_NAME = 'Threads_running'
            """)
            threads_running = int(result[0][0]) if result else 0
            
            if threads_running > 50:
                items.append(self._create_item(
                    name="活跃线程数",
                    insp_type=InspectionType.PERFORMANCE,
                    risk_level=RiskLevel.MEDIUM,
                    status="warning",
                    description=f"活跃线程数过多: {threads_running}",
                    actual_value=str(threads_running),
                    reference="< 50",
                    suggestion="检查是否有慢查询或锁等待"
                ))
            else:
                items.append(self._create_item(
                    name="活跃线程数",
                    insp_type=InspectionType.PERFORMANCE,
                    risk_level=RiskLevel.INFO,
                    status="pass",
                    description="活跃线程数正常",
                    actual_value=str(threads_running),
                    reference="< 50"
                ))

        except Exception as e:
            logger.warning(f"性能检查失败: {e}")

        return items

    def inspect_storage(self) -> List[InspectionItem]:
        """检查MySQL存储 - 扩充到10+项"""
        items = []

        try:
            # 获取当前数据库名
            result = self._execute_query("SELECT DATABASE()")
            current_db = result[0][0] if result and result[0][0] else self.connector.database

            if not current_db:
                items.append(self._create_item(
                    name="存储检查",
                    insp_type=InspectionType.STORAGE,
                    risk_level=RiskLevel.MEDIUM,
                    status="fail",
                    description="无法确定当前数据库",
                    suggestion="未选择数据库，无法检查存储"
                ))
                return items

            # 安全转义数据库名
            safe_db_name = self._escape_db_name(current_db)

            # 1. 检查当前数据库的大表
            threshold_bytes = self.TABLE_SIZE_THRESHOLD_MB * 1024 * 1024
            result = self._execute_query(f"""
                SELECT table_name, table_schema,
                       ROUND(data_length / 1024 / 1024, 2) as size_mb
                FROM information_schema.tables
                WHERE table_schema = {safe_db_name}
                AND data_length > {threshold_bytes}
                ORDER BY data_length DESC
                LIMIT 10
            """)

            if result:
                for row in result:
                    items.append(self._create_item(
                        name=f"大表检查: {row[0]}",
                        insp_type=InspectionType.STORAGE,
                        risk_level=RiskLevel.MEDIUM,
                        status="warning",
                        description=f"表 {row[0]} 大小超过阈值 {self.TABLE_SIZE_THRESHOLD_MB}MB",
                        actual_value=f"{row[2]}MB",
                        reference=f"< {self.TABLE_SIZE_THRESHOLD_MB}MB",
                        suggestion="考虑归档历史数据或分区"
                    ))

            # 2. 检查当前数据库的表数量
            result = self._execute_query(f"""
                SELECT COUNT(*) FROM information_schema.tables
                WHERE table_schema = {safe_db_name}
            """)

            if result:
                table_count = result[0][0]
                if table_count > self.TABLE_COUNT_THRESHOLD:
                    items.append(self._create_item(
                        name="表数量检查",
                        insp_type=InspectionType.STORAGE,
                        risk_level=RiskLevel.MEDIUM,
                        status="warning",
                        description=f"表数量过多: {table_count}",
                        actual_value=str(table_count),
                        reference=f"< {self.TABLE_COUNT_THRESHOLD}",
                        suggestion="考虑清理无用表或分库"
                    ))
                else:
                    items.append(self._create_item(
                        name="表数量检查",
                        insp_type=InspectionType.STORAGE,
                        risk_level=RiskLevel.INFO,
                        status="pass",
                        description=f"表数量正常: {table_count}",
                        actual_value=str(table_count),
                        reference=f"< {self.TABLE_COUNT_THRESHOLD}"
                    ))

            # 3. 检查表碎片率
            result = self._execute_query(f"""
                SELECT table_name, 
                       ROUND(data_free / 1024 / 1024, 2) as free_mb,
                       ROUND(data_length / 1024 / 1024, 2) as data_mb
                FROM information_schema.tables
                WHERE table_schema = {safe_db_name}
                AND data_free > 104857600
                ORDER BY data_free DESC
                LIMIT 5
            """)
            
            if result:
                for row in result:
                    frag_ratio = (row[1] / (row[1] + row[2])) * 100 if (row[1] + row[2]) > 0 else 0
                    if frag_ratio > 20:
                        items.append(self._create_item(
                            name=f"表碎片检查: {row[0]}",
                            insp_type=InspectionType.STORAGE,
                            risk_level=RiskLevel.MEDIUM,
                            status="warning",
                            description=f"表 {row[0]} 碎片率过高: {frag_ratio:.1f}%",
                            actual_value=f"{frag_ratio:.1f}%",
                            reference="< 20%",
                            suggestion="执行OPTIMIZE TABLE整理碎片"
                        ))

            # 4. 检查大字段表 - 合并为一个信息项
            result = self._execute_query(f"""
                SELECT table_name, column_name, data_type
                FROM information_schema.columns
                WHERE table_schema = {safe_db_name}
                AND data_type IN ('blob', 'text', 'longblob', 'longtext')
                LIMIT 10
            """)

            if result:
                # 合并为一个信息项
                table_field_map = {}
                for row in result:
                    if row[0] not in table_field_map:
                        table_field_map[row[0]] = []
                    table_field_map[row[0]].append(f"{row[1]}({row[2]})")

                table_count = len(table_field_map)
                field_count = len(result)
                items.append(self._create_item(
                    name="大字段检查",
                    insp_type=InspectionType.STORAGE,
                    risk_level=RiskLevel.INFO,
                    status="pass",
                    description=f"发现 {field_count} 个大字段分布在 {table_count} 个表中",
                    actual_value=f"{field_count}个字段/{table_count}个表",
                    suggestion="大字段可能影响性能，建议单独存储或压缩"
                ))

            # 5. 检查存储引擎分布
            result = self._execute_query(f"""
                SELECT engine, COUNT(*) as count
                FROM information_schema.tables
                WHERE table_schema = {safe_db_name}
                GROUP BY engine
            """)
            
            if result:
                for row in result:
                    engine = row[0] or 'NULL'
                    count = row[1]
                    if engine.lower() == 'myisam':
                        items.append(self._create_item(
                            name=f"存储引擎检查: MyISAM",
                            insp_type=InspectionType.STORAGE,
                            risk_level=RiskLevel.HIGH,
                            status="warning",
                            description=f"发现 {count} 个MyISAM表",
                            actual_value=str(count),
                            suggestion="MyISAM不支持事务，建议迁移到InnoDB"
                        ))
                    elif engine.lower() == 'innodb':
                        items.append(self._create_item(
                            name=f"存储引擎检查: InnoDB",
                            insp_type=InspectionType.STORAGE,
                            risk_level=RiskLevel.INFO,
                            status="pass",
                            description=f"InnoDB表数量: {count}",
                            actual_value=str(count)
                        ))

        except Exception as e:
            logger.warning(f"存储检查失败: {e}")

        return items

    def inspect_security(self) -> List[InspectionItem]:
        """检查MySQL安全 - 扩充到10+项"""
        items = []

        try:
            # 1. 检查空密码用户
            result = self._execute_query("""
                SELECT COUNT(*) FROM mysql.user WHERE user = ''
            """)
            if result and result[0][0] > 0:
                items.append(self._create_item(
                    name="空用户名检查",
                    insp_type=InspectionType.SECURITY,
                    risk_level=RiskLevel.HIGH,
                    status="warning",
                    description=f"发现 {result[0][0]} 个空用户名",
                    suggestion="删除空用户名用户"
                ))
            else:
                items.append(self._create_item(
                    name="空用户名检查",
                    insp_type=InspectionType.SECURITY,
                    risk_level=RiskLevel.INFO,
                    status="pass",
                    description="未发现空用户名用户",
                    actual_value="0"
                ))

            # 2. 检查无密码用户
            result = self._execute_query("""
                SELECT COUNT(*) FROM mysql.user WHERE authentication_string = ''
            """)
            if result and result[0][0] > 0:
                items.append(self._create_item(
                    name="无密码用户检查",
                    insp_type=InspectionType.SECURITY,
                    risk_level=RiskLevel.CRITICAL,
                    status="warning",
                    description=f"发现 {result[0][0]} 个无密码用户",
                    suggestion="为所有用户设置强密码"
                ))
            else:
                items.append(self._create_item(
                    name="无密码用户检查",
                    insp_type=InspectionType.SECURITY,
                    risk_level=RiskLevel.INFO,
                    status="pass",
                    description="未发现无密码用户",
                    actual_value="0"
                ))

            # 3. 检查具有SUPER权限的用户
            result = self._execute_query("""
                SELECT COUNT(*) FROM mysql.user WHERE Super_priv = 'Y'
            """)
            if result and result[0][0] > 0:
                super_count = result[0][0]
                items.append(self._create_item(
                    name="SUPER权限用户检查",
                    insp_type=InspectionType.SECURITY,
                    risk_level=RiskLevel.HIGH,
                    status="warning" if super_count > 2 else "pass",
                    description=f"发现 {super_count} 个具有SUPER权限的用户",
                    actual_value=str(super_count),
                    suggestion="SUPER权限应仅限于管理员，建议审查权限分配"
                ))

            # 4. 检查远程root访问
            result = self._execute_query("""
                SELECT COUNT(*) FROM mysql.user 
                WHERE user = 'root' AND host NOT IN ('localhost', '127.0.0.1', '::1')
            """)
            if result and result[0][0] > 0:
                items.append(self._create_item(
                    name="远程root访问检查",
                    insp_type=InspectionType.SECURITY,
                    risk_level=RiskLevel.CRITICAL,
                    status="warning",
                    description=f"发现 {result[0][0]} 个允许远程访问的root用户",
                    suggestion="禁止root用户远程访问，使用普通用户+sudo方式"
                ))
            else:
                items.append(self._create_item(
                    name="远程root访问检查",
                    insp_type=InspectionType.SECURITY,
                    risk_level=RiskLevel.INFO,
                    status="pass",
                    description="root用户仅限本地访问",
                    actual_value="0"
                ))

            # 5. 检查匿名用户
            result = self._execute_query("""
                SELECT user, host FROM mysql.user WHERE user = ''
            """)
            if result and len(result) > 0:
                items.append(self._create_item(
                    name="匿名用户检查",
                    insp_type=InspectionType.SECURITY,
                    risk_level=RiskLevel.HIGH,
                    status="warning",
                    description=f"发现 {len(result)} 个匿名用户",
                    suggestion="删除匿名用户，使用命名用户"
                ))
            else:
                items.append(self._create_item(
                    name="匿名用户检查",
                    insp_type=InspectionType.SECURITY,
                    risk_level=RiskLevel.INFO,
                    status="pass",
                    description="未发现匿名用户",
                    actual_value="0"
                ))

            # 6. 检查test数据库
            result = self._execute_query("""
                SELECT COUNT(*) FROM information_schema.schemata WHERE schema_name = 'test'
            """)
            if result and result[0][0] > 0:
                items.append(self._create_item(
                    name="test数据库检查",
                    insp_type=InspectionType.SECURITY,
                    risk_level=RiskLevel.MEDIUM,
                    status="warning",
                    description="发现test数据库",
                    suggestion="删除test数据库，避免安全风险"
                ))
            else:
                items.append(self._create_item(
                    name="test数据库检查",
                    insp_type=InspectionType.SECURITY,
                    risk_level=RiskLevel.INFO,
                    status="pass",
                    description="未发现test数据库",
                    actual_value="0"
                ))

            # 7. 检查SSL连接
            result = self._execute_query("""
                SHOW VARIABLES LIKE 'have_ssl'
            """)
            if result:
                ssl_status = result[0][1]
                if ssl_status != 'YES':
                    items.append(self._create_item(
                        name="SSL连接检查",
                        insp_type=InspectionType.SECURITY,
                        risk_level=RiskLevel.MEDIUM,
                        status="warning",
                        description=f"SSL状态: {ssl_status}",
                        suggestion="建议启用SSL加密连接"
                    ))
                else:
                    items.append(self._create_item(
                        name="SSL连接检查",
                        insp_type=InspectionType.SECURITY,
                        risk_level=RiskLevel.INFO,
                        status="pass",
                        description="SSL已启用",
                        actual_value="YES"
                    ))

        except Exception as e:
            logger.warning(f"安全检查失败: {e}")
            items.append(self._create_item(
                name="安全检查",
                insp_type=InspectionType.SECURITY,
                risk_level=RiskLevel.MEDIUM,
                status="fail",
                description=f"安全检查执行失败: {str(e)}",
                suggestion="请检查相关配置和权限"
            ))

        return items

    def inspect_capacity(self) -> List[InspectionItem]:
        """检查MySQL容量"""
        items = []

        try:
            # 获取当前数据库名
            result = self._execute_query("SELECT DATABASE()")
            current_db = result[0][0] if result and result[0][0] else self.connector.database

            if not current_db:
                items.append(self._create_item(
                    name="数据库容量检查",
                    insp_type=InspectionType.CAPACITY,
                    risk_level=RiskLevel.MEDIUM,
                    status="fail",
                    description="无法确定当前数据库",
                    suggestion="未选择数据库，无法检查容量"
                ))
                return items

            # 安全转义数据库名
            safe_db_name = self._escape_db_name(current_db)

            # 只检查当前数据库的大小
            result = self._execute_query(f"""
                SELECT table_schema,
                       ROUND(SUM(data_length + index_length) / 1024 / 1024 / 1024, 2) AS size_gb
                FROM information_schema.tables
                WHERE table_schema = {safe_db_name}
                GROUP BY table_schema
            """)

            if result:
                row = result[0]
                db_name = row[0]
                size_gb = row[1]
                items.append(self._create_item(
                    name=f"数据库容量: {db_name}",
                    insp_type=InspectionType.CAPACITY,
                    risk_level=RiskLevel.INFO,
                    status="pass",
                    description=f"数据库 {db_name} 占用 {size_gb} GB 存储空间",
                    actual_value=f"{size_gb}GB"
                ))
            else:
                # 数据库存在但没有表
                items.append(self._create_item(
                    name=f"数据库容量: {current_db}",
                    insp_type=InspectionType.CAPACITY,
                    risk_level=RiskLevel.INFO,
                    status="pass",
                    description=f"数据库 {current_db} 暂无数据",
                    actual_value="0GB"
                ))

        except Exception as e:
            logger.warning(f"容量检查失败: {e}")
            items.append(self._create_item(
                name="数据库容量检查",
                insp_type=InspectionType.CAPACITY,
                risk_level=RiskLevel.MEDIUM,
                status="fail",
                description=f"容量检查失败: {str(e)}",
                suggestion="请检查相关配置和权限"
            ))

        return items

    def inspect_table_structure(self) -> List[InspectionItem]:
        """检查表结构 - 新增检查类别"""
        items = []

        try:
            # 获取当前数据库名
            result = self._execute_query("SELECT DATABASE()")
            current_db = result[0][0] if result and result[0][0] else self.connector.database

            if not current_db:
                return items

            # 安全转义数据库名
            safe_db_name = self._escape_db_name(current_db)

            # 1. 检查无主键的表
            result = self._execute_query(f"""
                SELECT t.table_name
                FROM information_schema.tables t
                LEFT JOIN information_schema.key_column_usage k
                ON t.table_name = k.table_name AND t.table_schema = k.table_schema
                AND k.constraint_name = 'PRIMARY'
                WHERE t.table_schema = {safe_db_name}
                AND t.table_type = 'BASE TABLE'
                AND k.column_name IS NULL
                LIMIT 10
            """)
            
            if result:
                for row in result:
                    items.append(self._create_item(
                        name=f"无主键表检查: {row[0]}",
                        insp_type=InspectionType.STORAGE,
                        risk_level=RiskLevel.HIGH,
                        status="warning",
                        description=f"表 {row[0]} 没有主键",
                        suggestion="所有表都应该有主键，建议添加自增ID主键"
                    ))

            # 2. 检查使用UTF8（非utf8mb4）的表 - 改为INFO级别，不扣分
            result = self._execute_query(f"""
                SELECT table_name, table_collation
                FROM information_schema.tables
                WHERE table_schema = {safe_db_name}
                AND table_collation LIKE 'utf8_%'
                AND table_collation NOT LIKE 'utf8mb4_%'
                LIMIT 10
            """)

            if result:
                # 合并为一个信息项，避免过多警告
                table_names = [row[0] for row in result]
                items.append(self._create_item(
                    name="字符集检查",
                    insp_type=InspectionType.CONFIGURATION,
                    risk_level=RiskLevel.INFO,
                    status="pass",
                    description=f"发现 {len(result)} 个表使用旧版UTF8字符集",
                    actual_value=f"{len(result)}个表",
                    suggestion=f"建议迁移到utf8mb4以支持完整Unicode。涉及表: {', '.join(table_names[:5])}{'等' if len(table_names) > 5 else ''}"
                ))

            # 3. 检查大表行数
            result = self._execute_query(f"""
                SELECT table_name, table_rows
                FROM information_schema.tables
                WHERE table_schema = {safe_db_name}
                AND table_rows > 10000000
                ORDER BY table_rows DESC
                LIMIT 5
            """)
            
            if result:
                for row in result:
                    items.append(self._create_item(
                        name=f"大表行数检查: {row[0]}",
                        insp_type=InspectionType.STORAGE,
                        risk_level=RiskLevel.INFO,
                        status="pass",
                        description=f"表 {row[0]} 行数: {row[1]}",
                        actual_value=str(row[1]),
                        suggestion="大表需要考虑分区或归档策略"
                    ))

        except Exception as e:
            logger.warning(f"表结构检查失败: {e}")

        return items

    def inspect_indexes(self) -> List[InspectionItem]:
        """检查索引 - 新增检查类别"""
        items = []

        try:
            # 获取当前数据库名
            result = self._execute_query("SELECT DATABASE()")
            current_db = result[0][0] if result and result[0][0] else self.connector.database

            if not current_db:
                return items

            # 安全转义数据库名
            safe_db_name = self._escape_db_name(current_db)

            # 1. 检查冗余索引（同一列上的重复索引）- 合并为一个检查项
            result = self._execute_query(f"""
                SELECT table_name, column_name, COUNT(*) as idx_count
                FROM information_schema.statistics
                WHERE table_schema = {safe_db_name}
                AND seq_in_index = 1
                GROUP BY table_name, column_name
                HAVING COUNT(*) > 1
                LIMIT 10
            """)

            if result:
                # 合并为一个检查项
                table_count = len(set(row[0] for row in result))
                total_redundant = sum(row[2] - 1 for row in result)  # 计算冗余索引数量
                table_names = [row[0] for row in result[:5]]  # 取前5个表名

                items.append(self._create_item(
                    name="冗余索引检查",
                    insp_type=InspectionType.PERFORMANCE,
                    risk_level=RiskLevel.MEDIUM,
                    status="warning",
                    description=f"发现 {table_count} 个表存在冗余索引，共 {total_redundant} 个冗余索引",
                    actual_value=f"{table_count}个表/{total_redundant}个索引",
                    suggestion=f"删除冗余索引以减少维护开销。涉及表: {', '.join(table_names)}{'等' if len(result) > 5 else ''}"
                ))

            # 2. 检查无索引的大表 - 合并为一个检查项
            result = self._execute_query(f"""
                SELECT t.table_name, t.table_rows
                FROM information_schema.tables t
                LEFT JOIN information_schema.statistics s
                ON t.table_name = s.table_name AND t.table_schema = s.table_schema
                WHERE t.table_schema = {safe_db_name}
                AND t.table_type = 'BASE TABLE'
                AND t.table_rows > 10000
                AND s.index_name IS NULL
                LIMIT 5
            """)

            if result:
                # 合并为一个检查项
                table_count = len(result)
                total_rows = sum(row[1] for row in result)
                table_names = [row[0] for row in result]

                items.append(self._create_item(
                    name="无索引大表检查",
                    insp_type=InspectionType.PERFORMANCE,
                    risk_level=RiskLevel.HIGH,
                    status="warning",
                    description=f"发现 {table_count} 个大表没有索引，总行数: {total_rows:,}",
                    actual_value=f"{table_count}个表",
                    suggestion=f"为大表添加适当的索引以提高查询性能。涉及表: {', '.join(table_names)}"
                ))

        except Exception as e:
            logger.warning(f"索引检查失败: {e}")

        return items

    def inspect_slow_queries(self) -> List[InspectionItem]:
        """检查慢查询 - 新增检查类别"""
        items = []

        try:
            # 1. 检查慢查询日志状态
            result = self._execute_query("SHOW VARIABLES LIKE 'slow_query_log'")
            slow_log_enabled = result[0][1] if result else 'OFF'
            
            if slow_log_enabled != 'ON':
                items.append(self._create_item(
                    name="慢查询日志检查",
                    insp_type=InspectionType.PERFORMANCE,
                    risk_level=RiskLevel.MEDIUM,
                    status="warning",
                    description="慢查询日志未启用",
                    suggestion="启用slow_query_log以捕获慢查询"
                ))
            else:
                # 2. 检查慢查询数量
                result = self._execute_query("""
                    SHOW GLOBAL STATUS LIKE 'Slow_queries'
                """)
                slow_count = int(result[0][1]) if result else 0
                
                items.append(self._create_item(
                    name="慢查询统计",
                    insp_type=InspectionType.PERFORMANCE,
                    risk_level=RiskLevel.INFO if slow_count < 100 else RiskLevel.MEDIUM,
                    status="pass" if slow_count < 100 else "warning",
                    description=f"累计慢查询数量: {slow_count}",
                    actual_value=str(slow_count),
                    reference="< 100",
                    suggestion="定期分析慢查询日志并优化" if slow_count >= 100 else None
                ))

            # 3. 检查长查询时间阈值
            result = self._execute_query("SHOW VARIABLES LIKE 'long_query_time'")
            long_query_time = float(result[0][1]) if result else 10.0
            
            if long_query_time > 2.0:
                items.append(self._create_item(
                    name="慢查询阈值检查",
                    insp_type=InspectionType.CONFIGURATION,
                    risk_level=RiskLevel.MEDIUM,
                    status="warning",
                    description=f"慢查询阈值设置过高: {long_query_time}秒",
                    actual_value=f"{long_query_time}s",
                    reference="<= 2s",
                    suggestion="建议设置long_query_time为1-2秒"
                ))
            else:
                items.append(self._create_item(
                    name="慢查询阈值检查",
                    insp_type=InspectionType.CONFIGURATION,
                    risk_level=RiskLevel.INFO,
                    status="pass",
                    description=f"慢查询阈值设置合理: {long_query_time}秒",
                    actual_value=f"{long_query_time}s",
                    reference="<= 2s"
                ))

        except Exception as e:
            logger.warning(f"慢查询检查失败: {e}")

        return items

    def inspect_replication(self) -> List[InspectionItem]:
        """检查复制状态 - 新增检查类别"""
        items = []

        try:
            # 1. 检查是否配置了复制
            result = self._execute_query("SHOW SLAVE STATUS")
            
            if result:
                # 是Slave节点，检查复制状态
                slave_io = result[0][10] if len(result[0]) > 10 else 'No'
                slave_sql = result[0][11] if len(result[0]) > 11 else 'No'
                seconds_behind = result[0][32] if len(result[0]) > 32 else None
                
                if slave_io == 'Yes' and slave_sql == 'Yes':
                    # 复制正常运行
                    delay = int(seconds_behind) if seconds_behind and seconds_behind != 'NULL' else 0
                    
                    if delay > 60:
                        items.append(self._create_item(
                            name="复制延迟检查",
                            insp_type=InspectionType.REPLICATION,
                            risk_level=RiskLevel.HIGH,
                            status="warning",
                            description=f"复制延迟过高: {delay}秒",
                            actual_value=f"{delay}s",
                            reference="< 60s",
                            suggestion="检查网络状况或从库性能"
                        ))
                    else:
                        items.append(self._create_item(
                            name="复制延迟检查",
                            insp_type=InspectionType.REPLICATION,
                            risk_level=RiskLevel.INFO,
                            status="pass",
                            description=f"复制延迟正常: {delay}秒",
                            actual_value=f"{delay}s",
                            reference="< 60s"
                        ))
                    
                    items.append(self._create_item(
                        name="复制状态检查",
                        insp_type=InspectionType.REPLICATION,
                        risk_level=RiskLevel.INFO,
                        status="pass",
                        description="主从复制运行正常",
                        actual_value="IO: Yes, SQL: Yes"
                    ))
                else:
                    items.append(self._create_item(
                        name="复制状态检查",
                        insp_type=InspectionType.REPLICATION,
                        risk_level=RiskLevel.CRITICAL,
                        status="fail",
                        description=f"复制异常 - IO: {slave_io}, SQL: {slave_sql}",
                        suggestion="检查复制错误日志并修复"
                    ))
            else:
                # 不是Slave节点，检查是否是Master
                result = self._execute_query("SHOW MASTER STATUS")
                if result:
                    items.append(self._create_item(
                        name="复制角色检查",
                        insp_type=InspectionType.REPLICATION,
                        risk_level=RiskLevel.INFO,
                        status="pass",
                        description="当前节点是Master节点",
                        actual_value="Master"
                    ))
                else:
                    items.append(self._create_item(
                        name="复制角色检查",
                        insp_type=InspectionType.REPLICATION,
                        risk_level=RiskLevel.INFO,
                        status="pass",
                        description="当前节点未配置复制",
                        actual_value="Standalone"
                    ))

        except Exception as e:
            logger.warning(f"复制检查失败: {e}")

        return items
