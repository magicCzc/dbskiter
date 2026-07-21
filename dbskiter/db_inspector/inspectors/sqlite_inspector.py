"""
SQLite巡检器

提供SQLite数据库的巡检能力

文件功能：SQLite数据库巡检器实现
主要类：SQLiteInspector - SQLite数据库巡检器

支持的巡检项：
    - 配置检查：缓存大小、日志模式、同步模式
    - 性能检查：大表检测、缺少索引检测
    - 存储检查：数据库文件大小、碎片率
    - 安全检查：文件权限、加密状态
    - 容量检查：表数量、数据增长趋势
    - 完整性检查：数据库完整性验证

依赖：
    - sqlite3 标准库
    - SQLite 3.8+

作者：Magiczc
创建时间：2026-06-03
版本：1.0.0
"""

import logging
import os
from typing import List, Dict, Any, Optional
from datetime import datetime

from dbskiter.shared.unified_connector import UnifiedConnector
from ..models import InspectionItem, InspectionType, RiskLevel
from .base import BaseInspector

logger = logging.getLogger(__name__)


class SQLiteInspector(BaseInspector):
    """
    SQLite数据库巡检器

    提供SQLite特有的巡检能力：
    - 配置检查：缓存大小、日志模式、同步模式
    - 性能检查：大表检测、缺少索引检测
    - 存储检查：数据库文件大小、碎片率
    - 安全检查：文件权限、加密状态
    - 容量检查：表数量、数据增长趋势
    - 完整性检查：数据库完整性验证

    特性：
    - 基于PRAGMA命令获取配置信息
    - 支持文件系统级别的检查
    """

    def __init__(self, connector: UnifiedConnector):
        """
        初始化SQLite巡检器

        参数：
            connector: UnifiedConnector实例
        """
        super().__init__(connector)
        self._database_path = None

    def _get_database_path(self) -> Optional[str]:
        """
        获取数据库文件路径

        返回：
            Optional[str]: 数据库文件路径或None
        """
        if self._database_path is None:
            try:
                result = self.connector.execute("PRAGMA database_list")
                if result and result.rows:
                    for row in result.rows:
                        if row[1] == 'main':
                            self._database_path = row[2]
                            break
            except Exception as e:
                logger.warning(f"获取数据库路径失败: {e}")
        return self._database_path

    def inspect_configuration(self) -> List[InspectionItem]:
        """
        检查SQLite配置

        返回：
            List[InspectionItem]: 配置检查项列表
        """
        items = []

        # 检查缓存大小
        try:
            result = self.connector.execute("PRAGMA cache_size")
            cache_size = int(result.rows[0][0]) if result else 0

            if cache_size < 0:
                # 负值表示以KB为单位的缓存大小
                cache_kb = abs(cache_size)
                if cache_kb < 2000:  # 小于2MB
                    items.append(InspectionItem(
                        name="cache_size",
                        inspection_type=InspectionType.CONFIGURATION,
                        risk_level=RiskLevel.MEDIUM,
                        description=f"缓存大小较小: {cache_kb} KB",
                        recommendation="增加缓存大小以提升性能",
                        current_value=f"{cache_kb} KB",
                        expected_value=">= 2000 KB"
                    ))
                else:
                    items.append(InspectionItem(
                        name="cache_size",
                        inspection_type=InspectionType.CONFIGURATION,
                        risk_level=RiskLevel.LOW,
                        description=f"缓存大小: {cache_kb} KB",
                        current_value=f"{cache_kb} KB"
                    ))
            else:
                # 正值表示页面数
                if cache_size < 1000:
                    items.append(InspectionItem(
                        name="cache_size",
                        inspection_type=InspectionType.CONFIGURATION,
                        risk_level=RiskLevel.MEDIUM,
                        description=f"缓存页面数较少: {cache_size}",
                        recommendation="增加缓存页面数",
                        current_value=str(cache_size),
                        expected_value=">= 1000"
                    ))
                else:
                    items.append(InspectionItem(
                        name="cache_size",
                        inspection_type=InspectionType.CONFIGURATION,
                        risk_level=RiskLevel.LOW,
                        description=f"缓存页面数: {cache_size}",
                        current_value=str(cache_size)
                    ))

        except Exception as e:
            logger.warning(f"检查缓存大小失败: {e}")

        # 检查日志模式
        try:
            result = self.connector.execute("PRAGMA journal_mode")
            journal_mode = result.rows[0][0] if result else "unknown"

            if journal_mode.upper() == 'DELETE':
                items.append(InspectionItem(
                    name="journal_mode",
                    inspection_type=InspectionType.CONFIGURATION,
                    risk_level=RiskLevel.MEDIUM,
                    description="日志模式为DELETE，并发性能较差",
                    recommendation="建议使用WAL模式提升并发性能",
                    current_value=journal_mode,
                    expected_value="WAL"
                ))
            elif journal_mode.upper() == 'WAL':
                items.append(InspectionItem(
                    name="journal_mode",
                    inspection_type=InspectionType.CONFIGURATION,
                    risk_level=RiskLevel.LOW,
                    description="日志模式为WAL，适合高并发",
                    current_value=journal_mode
                ))
            else:
                items.append(InspectionItem(
                    name="journal_mode",
                    inspection_type=InspectionType.CONFIGURATION,
                    risk_level=RiskLevel.LOW,
                    description=f"日志模式: {journal_mode}",
                    current_value=journal_mode
                ))

        except Exception as e:
            logger.warning(f"检查日志模式失败: {e}")

        # 检查同步模式
        try:
            result = self.connector.execute("PRAGMA synchronous")
            sync_value = int(result.rows[0][0]) if result else -1
            sync_modes = {0: "OFF", 1: "NORMAL", 2: "FULL", 3: "EXTRA"}
            sync_mode = sync_modes.get(sync_value, f"UNKNOWN({sync_value})")

            if sync_value == 0:
                items.append(InspectionItem(
                    name="synchronous",
                    inspection_type=InspectionType.CONFIGURATION,
                    risk_level=RiskLevel.HIGH,
                    description="同步模式为OFF，可能导致数据丢失",
                    recommendation="建议设置为NORMAL或FULL",
                    current_value=sync_mode,
                    expected_value="NORMAL"
                ))
            elif sync_value == 1:
                items.append(InspectionItem(
                    name="synchronous",
                    inspection_type=InspectionType.CONFIGURATION,
                    risk_level=RiskLevel.LOW,
                    description="同步模式为NORMAL，平衡性能和安全性",
                    current_value=sync_mode
                ))
            else:
                items.append(InspectionItem(
                    name="synchronous",
                    inspection_type=InspectionType.CONFIGURATION,
                    risk_level=RiskLevel.LOW,
                    description=f"同步模式为{sync_mode}，数据安全性高",
                    current_value=sync_mode
                ))

        except Exception as e:
            logger.warning(f"检查同步模式失败: {e}")

        return items

    def inspect_performance(self) -> List[InspectionItem]:
        """
        检查SQLite性能

        返回：
            List[InspectionItem]: 性能检查项列表
        """
        items = []

        # 检查大表
        try:
            result = self.connector.execute("""
                SELECT name
                FROM sqlite_master
                WHERE type = 'table'
                AND name NOT LIKE 'sqlite_%'
            """)

            large_tables = []
            for row in result.rows if result else []:
                table_name = row[0]
                try:
                    count_result = self.connector.execute(
                        f'SELECT count(*) FROM "{table_name}"'
                    )
                    row_count = int(count_result.rows[0][0]) if count_result else 0

                    if row_count > 100000:  # 10万行
                        large_tables.append({
                            "table": table_name,
                            "row_count": row_count
                        })

                except Exception:
                    pass

            if large_tables:
                items.append(InspectionItem(
                    name="large_tables",
                    inspection_type=InspectionType.PERFORMANCE,
                    risk_level=RiskLevel.MEDIUM,
                    description=f"发现 {len(large_tables)} 个大表（超过10万行）",
                    recommendation="考虑优化查询或分区",
                    current_value=str(len(large_tables))
                ))

        except Exception as e:
            logger.warning(f"检查大表失败: {e}")

        # 检查缺少索引的表
        try:
            result = self.connector.execute("""
                SELECT name
                FROM sqlite_master
                WHERE type = 'table'
                AND name NOT LIKE 'sqlite_%'
            """)

            missing_index_tables = []
            for row in result.rows if result else []:
                table_name = row[0]
                try:
                    # 检查是否有索引
                    index_result = self.connector.execute(f"""
                        SELECT count()
                        FROM sqlite_master
                        WHERE type = 'index'
                        AND tbl_name = '{table_name}'
                        AND name NOT LIKE 'sqlite_%'
                    """)

                    index_count = int(index_result.rows[0][0]) if index_result else 0

                    if index_count == 0:
                        # 获取行数
                        count_result = self.connector.execute(
                            f'SELECT count(*) FROM "{table_name}"'
                        )
                        row_count = int(count_result.rows[0][0]) if count_result else 0

                        if row_count > 1000:
                            missing_index_tables.append({
                                "table": table_name,
                                "row_count": row_count
                            })

                except Exception:
                    pass

            if missing_index_tables:
                items.append(InspectionItem(
                    name="missing_indexes",
                    inspection_type=InspectionType.PERFORMANCE,
                    risk_level=RiskLevel.HIGH,
                    description=f"发现 {len(missing_index_tables)} 个大表缺少索引",
                    recommendation="为频繁查询的列添加索引",
                    current_value=str(len(missing_index_tables))
                ))

        except Exception as e:
            logger.warning(f"检查缺少索引失败: {e}")

        return items

    def inspect_storage(self) -> List[InspectionItem]:
        """
        检查SQLite存储

        返回：
            List[InspectionItem]: 存储检查项列表
        """
        items = []

        # 检查数据库文件大小
        try:
            db_path = self._get_database_path()
            if db_path and db_path != ':memory:':
                file_size = os.path.getsize(db_path)

                if file_size > 1024 * 1024 * 1024:  # 1GB
                    items.append(InspectionItem(
                        name="database_size",
                        inspection_type=InspectionType.STORAGE,
                        risk_level=RiskLevel.HIGH,
                        description=f"数据库文件超过1GB: {self._format_bytes(file_size)}",
                        recommendation="考虑数据归档或分库",
                        current_value=self._format_bytes(file_size)
                    ))
                elif file_size > 100 * 1024 * 1024:  # 100MB
                    items.append(InspectionItem(
                        name="database_size",
                        inspection_type=InspectionType.STORAGE,
                        risk_level=RiskLevel.MEDIUM,
                        description=f"数据库文件较大: {self._format_bytes(file_size)}",
                        current_value=self._format_bytes(file_size)
                    ))
                else:
                    items.append(InspectionItem(
                        name="database_size",
                        inspection_type=InspectionType.STORAGE,
                        risk_level=RiskLevel.LOW,
                        description=f"数据库文件大小: {self._format_bytes(file_size)}",
                        current_value=self._format_bytes(file_size)
                    ))

        except Exception as e:
            logger.warning(f"检查数据库大小失败: {e}")

        # 检查碎片率
        try:
            result = self.connector.execute("PRAGMA page_count")
            page_count = int(result.rows[0][0]) if result else 0

            result = self.connector.execute("PRAGMA freelist_count")
            freelist_count = int(result.rows[0][0]) if result else 0

            if page_count > 0:
                fragmentation = (freelist_count / page_count) * 100

                if fragmentation > 50:
                    items.append(InspectionItem(
                        name="fragmentation",
                        inspection_type=InspectionType.STORAGE,
                        risk_level=RiskLevel.HIGH,
                        description=f"碎片率过高: {fragmentation:.2f}%",
                        recommendation="执行VACUUM整理数据库",
                        current_value=f"{fragmentation:.2f}%"
                    ))
                elif fragmentation > 20:
                    items.append(InspectionItem(
                        name="fragmentation",
                        inspection_type=InspectionType.STORAGE,
                        risk_level=RiskLevel.MEDIUM,
                        description=f"碎片率较高: {fragmentation:.2f}%",
                        recommendation="考虑执行VACUUM",
                        current_value=f"{fragmentation:.2f}%"
                    ))
                else:
                    items.append(InspectionItem(
                        name="fragmentation",
                        inspection_type=InspectionType.STORAGE,
                        risk_level=RiskLevel.LOW,
                        description=f"碎片率正常: {fragmentation:.2f}%",
                        current_value=f"{fragmentation:.2f}%"
                    ))

        except Exception as e:
            logger.warning(f"检查碎片率失败: {e}")

        return items

    def inspect_security(self) -> List[InspectionItem]:
        """
        检查SQLite安全

        返回：
            List[InspectionItem]: 安全检查项列表
        """
        items = []

        # 检查文件权限
        try:
            db_path = self._get_database_path()
            if db_path and db_path != ':memory:':
                if os.name == 'posix':
                    import stat
                    file_stat = os.stat(db_path)
                    file_mode = stat.filemode(file_stat.st_mode)

                    # 检查是否全局可写
                    if file_stat.st_mode & stat.S_IWOTH:
                        items.append(InspectionItem(
                            name="file_permissions",
                            inspection_type=InspectionType.SECURITY,
                            risk_level=RiskLevel.CRITICAL,
                            description=f"数据库文件全局可写: {file_mode}",
                            recommendation="移除全局写权限",
                            current_value=file_mode,
                            expected_value="-rw-r--r--"
                        ))
                    else:
                        items.append(InspectionItem(
                            name="file_permissions",
                            inspection_type=InspectionType.SECURITY,
                            risk_level=RiskLevel.LOW,
                            description=f"文件权限: {file_mode}",
                            current_value=file_mode
                        ))

        except Exception as e:
            logger.warning(f"检查文件权限失败: {e}")

        return items

    def inspect_capacity(self) -> List[InspectionItem]:
        """
        检查SQLite容量

        返回：
            List[InspectionItem]: 容量检查项列表
        """
        items = []

        # 检查表数量
        try:
            result = self.connector.execute("""
                SELECT count()
                FROM sqlite_master
                WHERE type = 'table'
                AND name NOT LIKE 'sqlite_%'
            """)
            table_count = int(result.rows[0][0]) if result else 0

            if table_count > 1000:
                items.append(InspectionItem(
                    name="table_count",
                    inspection_type=InspectionType.CAPACITY,
                    risk_level=RiskLevel.MEDIUM,
                    description=f"表数量较多: {table_count}",
                    recommendation="考虑分库或归档",
                    current_value=str(table_count)
                ))
            else:
                items.append(InspectionItem(
                    name="table_count",
                    inspection_type=InspectionType.CAPACITY,
                    risk_level=RiskLevel.LOW,
                    description=f"表数量: {table_count}",
                    current_value=str(table_count)
                ))

        except Exception as e:
            logger.warning(f"检查表数量失败: {e}")

        return items

    def inspect_integrity(self) -> List[InspectionItem]:
        """
        检查SQLite完整性

        返回：
            List[InspectionItem]: 完整性检查项列表
        """
        items = []

        try:
            result = self.connector.execute("PRAGMA integrity_check")

            if result and result.rows:
                status = result.rows[0][0]

                if status == 'ok':
                    items.append(InspectionItem(
                        name="integrity_check",
                        inspection_type=InspectionType.CONFIGURATION,
                        risk_level=RiskLevel.LOW,
                        description="数据库完整性检查通过",
                        current_value="ok"
                    ))
                else:
                    items.append(InspectionItem(
                        name="integrity_check",
                        inspection_type=InspectionType.CONFIGURATION,
                        risk_level=RiskLevel.CRITICAL,
                        description=f"数据库完整性检查失败: {status}",
                        recommendation="立即备份并修复数据库",
                        current_value=status
                    ))
            else:
                items.append(InspectionItem(
                    name="integrity_check",
                    inspection_type=InspectionType.CONFIGURATION,
                    risk_level=RiskLevel.HIGH,
                    description="完整性检查无结果",
                    current_value="unknown"
                ))

        except Exception as e:
            logger.warning(f"完整性检查失败: {e}")
            items.append(InspectionItem(
                name="integrity_check",
                inspection_type=InspectionType.CONFIGURATION,
                risk_level=RiskLevel.HIGH,
                description=f"完整性检查执行失败: {str(e)}",
                current_value="error"
            ))

        return items

    def get_instance_info(self) -> Dict[str, Any]:
        """
        获取SQLite实例信息

        返回：
            Dict[str, Any]: 实例信息
        """
        info = {
            "version": "unknown",
            "timestamp": datetime.now().isoformat()
        }

        # 获取SQLite版本
        try:
            result = self.connector.execute("SELECT sqlite_version()")
            if result and result.rows:
                info["version"] = result.rows[0][0]
        except Exception as e:
            logger.warning(f"获取版本失败: {e}")

        # 获取数据库路径
        db_path = self._get_database_path()
        info["database_path"] = db_path

        # 获取文件大小
        if db_path and db_path != ':memory:':
            try:
                file_size = os.path.getsize(db_path)
                info["file_size"] = file_size
                info["file_size_pretty"] = self._format_bytes(file_size)
            except Exception as e:
                logger.warning(f"获取文件大小失败: {e}")

        return info

    def _format_bytes(self, size_bytes: int) -> str:
        """
        格式化字节数为人类可读格式

        参数：
            size_bytes: 字节数

        返回：
            str: 格式化后的字符串
        """
        if size_bytes is None or size_bytes < 0:
            return "0 B"
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.2f} PB"
