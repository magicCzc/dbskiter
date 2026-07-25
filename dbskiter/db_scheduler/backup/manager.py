"""
db_scheduler/backup/manager.py
数据库备份管理器 - 生产级实现

BackupManager 主类，提供多数据库备份/恢复功能。
数据模型（BackupInfo, BackupResult）在 models.py 中定义。
"""

import hashlib
import logging
import os
import re
import shutil
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional, Tuple

from dbskiter.shared.unified_connector import UnifiedConnector

from .models import BackupInfo, BackupResult

from dbskiter.db_scheduler.backup.mixins import (
    MySQLBackupMixin,
    PostgreSQLBackupMixin,
    SQLiteBackupMixin,
    ClickHouseBackupMixin,
    OracleBackupMixin,
    MSSQLBackupMixin,
    GenericBackupMixin,
    BackupUtilsMixin,
)

logger = logging.getLogger(__name__)

# 审计支持（可选导入，失败不阻断）
try:
    from dbskiter.sql_master.audit_logger import AuditLogger, OperationStatus, StorageBackend
    _HAS_AUDIT = True
except ImportError:
    _HAS_AUDIT = False
    AuditLogger = None
    OperationStatus = None
    StorageBackend = None


# =============================================================================
# 备份管理器
# =============================================================================


class BackupManager(
    MySQLBackupMixin,
    PostgreSQLBackupMixin,
    SQLiteBackupMixin,
    ClickHouseBackupMixin,
    OracleBackupMixin,
    MSSQLBackupMixin,
    GenericBackupMixin,
    BackupUtilsMixin,
):
    """
    数据库备份管理器 - 生产级实现

    实现策略:
        - 全量备份: 优先调用原生dump工具, 不可用时分页导出
        - 单表备份: 优先调用原生dump工具指定表, 不可用时分页导出
        - 恢复: 优先调用原生客户端工具, 不可用时逐语句执行
        - 校验: 基于SHA256哈希校验文件完整性

    使用示例:
        >>> manager = BackupManager(connector)
        >>> result = manager.backup_full(output_dir="/backups")
        >>> if result.success:
        ...     print(f"备份成功: {result.file_path}")
        >>> verify = manager.verify_backup(result.file_path)
        >>> restore = manager.restore_backup(result.file_path)
    """

    BACKUP_TYPE_FULL = "full"
    BACKUP_TYPE_TABLE = "table"
    BACKUP_TYPE_INCREMENTAL = "incremental"

    # 分页降级时的批次大小
    FALLBACK_BATCH_SIZE = 1000

    def __init__(self, connector: UnifiedConnector):
        """
        初始化备份管理器

        参数:
            connector: UnifiedConnector 实例, 提供数据库连接信息
        """
        self.connector = connector
        self.dialect = connector.dialect.lower()
        self.default_output_dir = "./backups"
        self.backup_timeout = 3600  # 默认备份超时 1 小时
        # 审计日志（备份操作独立审计）
        self._audit_logger = self._init_audit_logger()

    def _init_audit_logger(self):
        """初始化审计日志（失败不阻断）"""
        if not _HAS_AUDIT:
            return None
        try:
            audit_path = os.getenv(
                "DBSKITER_AUDIT_PATH",
                str(Path.home() / ".dbskiter" / "audit" / "audit.db")
            )
            Path(audit_path).parent.mkdir(parents=True, exist_ok=True)
            backend_str = os.getenv("DBSKITER_AUDIT_BACKEND", "sqlite")
            backend = StorageBackend(backend_str)
            return AuditLogger(backend=backend, storage_path=audit_path)
        except Exception:
            return None

    def _record_backup_audit(
        self,
        operation: str,
        backup_id: str,
        status: str,
        file_path: str = "",
        file_size: int = 0,
        error: str = "",
    ) -> None:
        """记录备份操作审计（失败不阻断）"""
        if not self._audit_logger:
            return
        try:
            self._audit_logger.log(
                sql="",
                database=getattr(self.connector, "database", "unknown") or "unknown",
                risk_level="HIGH" if operation in ("restore", "delete") else "MEDIUM",
                status=OperationStatus(status),
                sql_type="BACKUP",
                user=os.getenv("USER", "anonymous"),
                metadata={
                    "operation": operation,
                    "backup_id": backup_id,
                    "file_path": file_path,
                    "file_size": file_size,
                    "error": error,
                    "dialect": self.dialect,
                }
            )
        except Exception:
            pass

    # =====================================================================
    # 公共接口
    # =====================================================================

    def backup_full(
        self,
        output_dir: Optional[str] = None,
        compress: bool = True,
        include_schema: bool = True,
    ) -> BackupResult:
        """
        执行全量备份

        参数:
            output_dir: 输出目录, 默认 ./backups
            compress: 是否gzip压缩
            include_schema: 是否包含建表语句

        返回:
            BackupResult: 备份结果
        """
        output_dir = output_dir or self.default_output_dir
        os.makedirs(output_dir, exist_ok=True)

        raw_db_name = getattr(self.connector, "database", "unknown") or "unknown"
        db_name = self._safe_filename(raw_db_name)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_id = f"{db_name}_full_{timestamp}"

        logger.info(
            f"开始全量备份 [dialect={self.dialect}, backup_id={backup_id}]"
        )

        try:
            if self.dialect in ("mysql", "mysql+pymysql"):
                result = self._mysql_full_backup(
                    output_dir, backup_id, timestamp, compress, include_schema
                )
            elif "postgresql" in self.dialect:
                result = self._pg_full_backup(
                    output_dir, backup_id, timestamp, compress, include_schema
                )
            elif self.dialect in ("sqlite", "sqlite3"):
                result = self._sqlite_full_backup(
                    output_dir, backup_id, timestamp, compress
                )
            elif "clickhouse" in self.dialect:
                result = self._clickhouse_full_backup(
                    output_dir, backup_id, timestamp, compress, include_schema
                )
            elif "oracle" in self.dialect:
                result = self._oracle_full_backup(
                    output_dir, backup_id, timestamp, compress, include_schema
                )
            elif "mssql" in self.dialect or "sqlserver" in self.dialect:
                result = self._mssql_full_backup(
                    output_dir, backup_id, timestamp, compress, include_schema
                )
            else:
                # 通用回退：使用 SQL 分页查询备份
                output_file = os.path.join(
                    output_dir, f"{backup_id}.sql"
                )
                result = self._generic_fallback_backup(
                    output_file, backup_id, include_schema, compress
                )

            if result.success:
                self._write_checksum(result.file_path)
                logger.info(
                    f"全量备份完成 [backup_id={backup_id}, "
                    f"size={self._human_size(result.file_size)}]"
                )
            else:
                logger.error(
                    f"全量备份失败 [backup_id={backup_id}, error={result.error}]"
                )

            self._record_backup_audit(
                "backup_full", backup_id,
                "EXECUTED" if result.success else "FAILED",
                result.file_path, result.file_size, result.error or ""
            )
            return result

        except Exception as exc:
            logger.exception(f"全量备份异常 [backup_id={backup_id}]")
            err_result = self._error(backup_id, f"备份异常: {exc}")
            self._record_backup_audit(
                "backup_full", backup_id, "FAILED", "", 0, str(exc)
            )
            return err_result

    def backup_table(
        self,
        table: str,
        output_dir: Optional[str] = None,
        include_schema: bool = True,
    ) -> BackupResult:
        """
        执行单表备份

        参数:
            table: 表名
            output_dir: 输出目录
            include_schema: 是否包含建表语句

        返回:
            BackupResult: 备份结果
        """
        output_dir = output_dir or self.default_output_dir
        os.makedirs(output_dir, exist_ok=True)

        safe_table = self._safe_table_name(table)
        raw_db_name = getattr(self.connector, "database", "unknown") or "unknown"
        db_name = self._safe_filename(raw_db_name)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_id = f"{db_name}_table_{safe_table}_{timestamp}"

        logger.info(
            f"开始单表备份 [table={safe_table}, backup_id={backup_id}]"
        )

        try:
            if self.dialect in ("mysql", "mysql+pymysql"):
                result = self._mysql_table_backup(
                    safe_table, output_dir, backup_id, timestamp, include_schema
                )
            elif "postgresql" in self.dialect:
                result = self._pg_table_backup(
                    safe_table, output_dir, backup_id, timestamp, include_schema
                )
            elif self.dialect in ("sqlite", "sqlite3"):
                result = self._sqlite_table_backup(
                    safe_table, output_dir, backup_id, timestamp
                )
            elif "clickhouse" in self.dialect:
                result = self._clickhouse_table_backup(
                    safe_table, output_dir, backup_id, timestamp, include_schema
                )
            elif "oracle" in self.dialect:
                result = self._oracle_table_backup(
                    safe_table, output_dir, backup_id, timestamp, include_schema
                )
            elif "mssql" in self.dialect or "sqlserver" in self.dialect:
                result = self._mssql_table_backup(
                    safe_table, output_dir, backup_id, timestamp, include_schema
                )
            else:
                # 通用回退：使用 SQL 分页查询备份单表
                output_file = os.path.join(
                    output_dir, f"{backup_id}.sql"
                )
                result = self._generic_fallback_backup(
                    output_file, backup_id, include_schema, True, [safe_table]
                )

            if result.success:
                self._write_checksum(result.file_path)
                logger.info(
                    f"单表备份完成 [table={safe_table}, backup_id={backup_id}]"
                )
            else:
                logger.error(
                    f"单表备份失败 [table={safe_table}, backup_id={backup_id}, "
                    f"error={result.error}]"
                )

            self._record_backup_audit(
                "backup_table", backup_id,
                "EXECUTED" if result.success else "FAILED",
                result.file_path, result.file_size, result.error or ""
            )
            return result

        except Exception as exc:
            logger.exception(f"单表备份异常 [table={safe_table}]")
            err_result = self._error(backup_id, f"备份异常: {exc}")
            self._record_backup_audit(
                "backup_table", backup_id, "FAILED", "", 0, str(exc)
            )
            return err_result

    def backup_tables(
        self,
        tables: List[str],
        output_dir: Optional[str] = None,
        include_schema: bool = True,
    ) -> List[BackupResult]:
        """
        多表备份 - 顺序执行, 任一失败不影响后续

        参数:
            tables: 表名列表
            output_dir: 输出目录
            include_schema: 是否包含建表语句

        返回:
            List[BackupResult]: 每个表的备份结果
        """
        results = []
        for table in tables:
            result = self.backup_table(table, output_dir, include_schema)
            results.append(result)
        return results

    def list_backups(self, output_dir: Optional[str] = None) -> List[BackupInfo]:
        """
        列出备份目录中的所有备份文件

        参数:
            output_dir: 备份目录

        返回:
            List[BackupInfo]: 备份信息列表, 按时间倒序
        """
        output_dir = output_dir or self.default_output_dir
        path = Path(output_dir)

        if not path.exists():
            return []

        backups = []
        for file_path in path.iterdir():
            if not file_path.is_file():
                continue
            if file_path.suffix == ".sha256":
                continue

            stat = file_path.stat()
            checksum = self._read_checksum(str(file_path))
            backups.append(
                BackupInfo(
                    backup_id=file_path.stem,
                    backup_type=self._detect_backup_type(file_path.name),
                    file_path=str(file_path.absolute()),
                    file_size=stat.st_size,
                    created_at=datetime.fromtimestamp(stat.st_mtime),
                    tables=[],
                    checksum=checksum,
                    status="ok" if checksum else "unknown",
                )
            )

        backups.sort(key=lambda x: x.created_at, reverse=True)
        return backups

    def verify_backup(self, backup_file: str) -> BackupResult:
        """
        验证备份文件完整性

        参数:
            backup_file: 备份文件路径

        返回:
            BackupResult: 验证结果, success=True表示文件完好
        """
        if not os.path.exists(backup_file):
            return self._error(
                os.path.basename(backup_file), "备份文件不存在"
            )

        checksum_file = backup_file + ".sha256"
        if not os.path.exists(checksum_file):
            logger.warning(f"备份文件缺少校验值: {backup_file}")
            return BackupResult(
                success=True,
                backup_id=os.path.basename(backup_file),
                file_path=backup_file,
                file_size=os.path.getsize(backup_file),
                duration_ms=0,
                backup_type=self._detect_backup_type(backup_file),
            )

        expected_checksum = self._read_checksum(backup_file)
        actual_checksum = self._compute_sha256(backup_file)

        if expected_checksum and actual_checksum == expected_checksum:
            return BackupResult(
                success=True,
                backup_id=os.path.basename(backup_file),
                file_path=backup_file,
                file_size=os.path.getsize(backup_file),
                duration_ms=0,
                backup_type=self._detect_backup_type(backup_file),
            )

        return self._error(
            os.path.basename(backup_file),
            f"校验失败: 期望 {expected_checksum}, 实际 {actual_checksum}",
        )

    def restore_backup(
        self,
        backup_file: str,
        target_database: Optional[str] = None,
    ) -> BackupResult:
        """
        从备份文件恢复数据库

        警告:
            恢复操作会覆盖目标数据库中的数据。生产环境执行前请确认。
            如果系统处于只读模式, 恢复操作将被拒绝。

        参数:
            backup_file: 备份文件路径
            target_database: 目标数据库名, None表示使用原数据库

        返回:
            BackupResult: 恢复结果
        """
        # 只读模式检查: 恢复操作涉及写操作, 必须在非只读模式下执行
        if self._is_readonly():
            return self._error(
                os.path.basename(backup_file),
                "当前处于只读模式, 恢复操作被拒绝。"
                "如需执行恢复, 请先关闭只读模式。"
            )

        if not os.path.exists(backup_file):
            return self._error(
                os.path.basename(backup_file), "备份文件不存在"
            )

        backup_id = os.path.basename(backup_file)
        start_time = datetime.now()

        logger.warning(
            f"开始恢复数据库 [backup={backup_id}, "
            f"target={target_database or 'default'}]"
        )

        try:
            if self.dialect in ("mysql", "mysql+pymysql"):
                result = self._mysql_restore(
                    backup_file, target_database, backup_id, start_time
                )
            elif "postgresql" in self.dialect:
                result = self._pg_restore(
                    backup_file, target_database, backup_id, start_time
                )
            elif self.dialect in ("sqlite", "sqlite3"):
                result = self._sqlite_restore(
                    backup_file, backup_id, start_time
                )
            elif "clickhouse" in self.dialect:
                result = self._clickhouse_restore(
                    backup_file, backup_id, start_time
                )
            elif "oracle" in self.dialect:
                result = self._oracle_restore(
                    backup_file, backup_id, start_time
                )
            elif "mssql" in self.dialect or "sqlserver" in self.dialect:
                result = self._mssql_restore(
                    backup_file, backup_id, start_time
                )
            else:
                # 通用回退：逐行执行 SQL 文件中的语句
                result = self._generic_restore(
                    backup_file, backup_id, start_time
                )

            if result.success:
                logger.info(f"恢复完成 [backup={backup_id}]")
            else:
                logger.error(
                    f"恢复失败 [backup={backup_id}, error={result.error}]"
                )

            self._record_backup_audit(
                "restore", backup_id,
                "EXECUTED" if result.success else "FAILED",
                backup_file, result.file_size, result.error or ""
            )
            return result

        except Exception as exc:
            logger.exception(f"恢复异常 [backup={backup_id}]")
            err_result = self._error(backup_id, f"恢复异常: {exc}")
            self._record_backup_audit(
                "restore", backup_id, "FAILED", backup_file, 0, str(exc)
            )
            return err_result

    def delete_backup(self, backup_file: str) -> bool:
        """
        删除备份文件及其校验文件

        参数:
            backup_file: 备份文件路径

        返回:
            bool: 是否成功删除
        """
        try:
            deleted = False
            if os.path.exists(backup_file):
                os.remove(backup_file)
                deleted = True
            checksum_file = backup_file + ".sha256"
            if os.path.exists(checksum_file):
                os.remove(checksum_file)
                deleted = True
            if deleted:
                logger.info(f"备份已删除: {backup_file}")
            self._record_backup_audit(
                "delete", os.path.basename(backup_file),
                "EXECUTED" if deleted else "FAILED",
                backup_file, 0, "" if deleted else "文件不存在"
            )
            return deleted
        except Exception as exc:
            logger.error(f"删除备份失败 [{backup_file}]: {exc}")
            self._record_backup_audit(
                "delete", os.path.basename(backup_file), "FAILED", backup_file, 0, str(exc)
            )
            return False

    # =====================================================================
    # MySQL 实现
    # =====================================================================

    def _oracle_native_dump(
        self,
        output_file: str,
        backup_id: str,
        include_schema: bool,
        compress: bool,
        tables: Optional[List[str]] = None,
    ) -> BackupResult:
        """使用 Oracle exp 工具执行备份"""
        start_time = datetime.now()
        host = self.connector.host
        port = self.connector.port or 1521
        user = self.connector.username
        password = self.connector.password
        service = getattr(self.connector, "service", None) or self.connector.database

        # Oracle exp 工具使用 TNS 连接字符串
        tns = f"//{host}:{port}/{service}"

        cmd = [
            "exp",
            f"{user}/{password}@{tns}",
            "FILE=" + output_file,
            "LOG=" + output_file + ".log",
        ]
        if tables:
            cmd.append(f"TABLES={','.join(tables)}")
        else:
            cmd.append("FULL=Y")
        if not include_schema:
            cmd.append("ROWS=Y")
        if compress:
            cmd.append("COMPRESS=Y")

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.backup_timeout,
            )

            if result.returncode != 0:
                return self._error(
                    backup_id,
                    f"Oracle exp 备份失败: {result.stderr or result.stdout}"
                )

            duration = int(
                (datetime.now() - start_time).total_seconds() * 1000
            )
            self._write_checksum(output_file)
            return BackupResult(
                success=True,
                backup_id=backup_id,
                file_path=output_file,
                file_size=os.path.getsize(output_file),
                duration_ms=duration,
            )

        except subprocess.TimeoutExpired:
            return self._error(backup_id, "Oracle exp 备份超时")
        except FileNotFoundError:
            return self._error(
                backup_id, "Oracle exp 工具未找到。请安装 Oracle Client。"
            )

    def _oracle_fallback_dump(
        self,
        output_file: str,
        backup_id: str,
        include_schema: bool,
        compress: bool,
        tables: Optional[List[str]] = None,
    ) -> BackupResult:
        """Oracle 分页降级备份（使用 SQL 查询）"""
        start_time = datetime.now()

        if tables is None:
            tables = self._get_generic_table_schema.__wrapped__(self) if hasattr(
                self._get_generic_table_schema, "__wrapped__"
            ) else self._get_oracle_tables()
        elif not tables:
            tables = self._get_oracle_tables()

        if not tables:
            return self._error(backup_id, "Oracle 未找到可备份的表")

        try:
            target_tables = tables if not tables else tables[:]
            if isinstance(target_tables, str):
                target_tables = [target_tables]

            with open(output_file, "w", encoding="utf-8") as f:
                if include_schema:
                    f.write("-- Oracle Backup Generated by dbskiter\n")
                    f.write(f"-- Date: {datetime.now().isoformat()}\n\n")

                for table in target_tables:
                    if include_schema:
                        f.write(self._get_oracle_table_schema(table) + "\n\n")
                    rows_written = self._write_oracle_table_data(f, table)
                    f.write(f"-- Table {table}: {rows_written} rows\n\n")

            if compress:
                compressed = self._gzip_file(output_file)
                output_file = compressed

            duration = int(
                (datetime.now() - start_time).total_seconds() * 1000
            )
            self._write_checksum(output_file)
            return BackupResult(
                success=True,
                backup_id=backup_id,
                file_path=output_file,
                file_size=os.path.getsize(output_file),
                duration_ms=duration,
            )

        except Exception as exc:
            return self._error(backup_id, f"Oracle 备份异常: {exc}")

    def _write_oracle_table_data(
        self, file_handle, table: str
    ) -> int:
        """使用分页查询写入 Oracle 表数据"""
        safe_table = self._quote_oracle_table(table)
        offset = 0
        batch_size = 1000
        total_rows = 0

        while True:
            query = (
                f"SELECT * FROM {safe_table} "
                f"OFFSET {offset} ROWS FETCH NEXT {batch_size} ROWS ONLY"
            )
            result = self.connector.execute(query)
            if not result or not result.rows:
                break

            for row in result.rows:
                values = [self._escape_oracle_value(v) for v in row]
                file_handle.write(
                    f"INSERT INTO {safe_table} VALUES ({', '.join(values)});\n"
                )
                total_rows += 1

            offset += batch_size

        return total_rows

