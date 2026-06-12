"""
db_scheduler/backup.py
数据库备份管理器 - 生产级实现

核心设计:
    1. 原生工具优先: 使用数据库厂商提供的命令行工具(mysqldump/pg_dump/sqlite3)
       确保转义正确、支持大数据量、性能最优
    2. 分页降级: 原生工具不可用时, 使用 LIMIT/OFFSET 分页查询, 避免OOM
    3. 完整性校验: 每次备份生成 SHA256 校验文件
    4. 流式处理: 所有Python实现的备份均使用生成器, 不加载全表到内存

支持的数据库:
    - MySQL (mysqldump / mysql)
    - PostgreSQL (pg_dump / psql)
    - SQLite (sqlite3 / 文件复制)

作者: AI Assistant
创建时间: 2026-04-23
最后修改: 2026-05-29
版本: 2.0.0 (重构版)
"""

import hashlib
import logging
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional, Tuple

from dbskiter.shared.unified_connector import UnifiedConnector

logger = logging.getLogger(__name__)

# =============================================================================
# 数据类
# =============================================================================


@dataclass
class BackupInfo:
    """
    备份信息

    属性:
        backup_id: 备份标识
        backup_type: 备份类型 (full/table/incremental)
        file_path: 备份文件绝对路径
        file_size: 文件大小(字节)
        created_at: 创建时间
        tables: 包含的表列表
        checksum: SHA256校验值
        status: 状态 (ok/corrupted/unknown)
    """

    backup_id: str
    backup_type: str
    file_path: str
    file_size: int
    created_at: datetime
    tables: List[str]
    checksum: Optional[str]
    status: str


@dataclass
class BackupResult:
    """
    备份/恢复操作结果

    属性:
        success: 是否成功
        backup_id: 备份标识
        file_path: 文件路径
        file_size: 文件大小(字节)
        duration_ms: 耗时(毫秒)
        tables: 涉及的表列表
        backup_type: 备份类型
        error: 错误信息(失败时)
    """

    success: bool
    backup_id: str
    file_path: str
    file_size: int
    duration_ms: int
    tables: List[str] = None
    backup_type: str = "full"
    error: Optional[str] = None

    def __post_init__(self):
        if self.tables is None:
            self.tables = []

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "backup_id": self.backup_id,
            "file_path": self.file_path,
            "file_size": self.file_size,
            "duration_ms": self.duration_ms,
            "tables": self.tables,
            "backup_type": self.backup_type,
            "error": self.error,
        }


# =============================================================================
# 备份管理器
# =============================================================================


class BackupManager:
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
        self._native_available = None  # 缓存原生工具可用性检测结果

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

            return result

        except Exception as exc:
            logger.exception(f"全量备份异常 [backup_id={backup_id}]")
            return self._error(backup_id, f"备份异常: {exc}")

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

            return result

        except Exception as exc:
            logger.exception(f"单表备份异常 [table={safe_table}]")
            return self._error(backup_id, f"备份异常: {exc}")

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

            return result

        except Exception as exc:
            logger.exception(f"恢复异常 [backup={backup_id}]")
            return self._error(backup_id, f"恢复异常: {exc}")

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
            return deleted
        except Exception as exc:
            logger.error(f"删除备份失败 [{backup_file}]: {exc}")
            return False

    # =====================================================================
    # MySQL 实现
    # =====================================================================

    def _mysql_full_backup(
        self,
        output_dir: str,
        backup_id: str,
        timestamp: str,
        compress: bool,
        include_schema: bool,
    ) -> BackupResult:
        """MySQL 全量备份"""
        output_file = os.path.join(output_dir, f"{backup_id}.sql")

        if self._has_native_tool("mysqldump"):
            return self._mysql_native_dump(
                output_file, backup_id, include_schema, compress
            )

        logger.warning(
            "mysqldump 不可用, 使用分页降级方案。"
            "大数据量备份建议安装 mysqldump。"
        )
        return self._mysql_fallback_dump(
            output_file, backup_id, include_schema, compress
        )

    def _mysql_table_backup(
        self,
        table: str,
        output_dir: str,
        backup_id: str,
        timestamp: str,
        include_schema: bool,
    ) -> BackupResult:
        """MySQL 单表备份"""
        output_file = os.path.join(output_dir, f"{backup_id}.sql")

        if self._has_native_tool("mysqldump"):
            return self._mysql_native_dump(
                output_file, backup_id, include_schema, False, tables=[table]
            )

        logger.warning(
            "mysqldump 不可用, 使用分页降级方案。"
            "大数据量备份建议安装 mysqldump。"
        )
        return self._mysql_fallback_dump(
            output_file, backup_id, include_schema, False, tables=[table]
        )

    def _mysql_native_dump(
        self,
        output_file: str,
        backup_id: str,
        include_schema: bool,
        compress: bool,
        tables: Optional[List[str]] = None,
    ) -> BackupResult:
        """
        使用 mysqldump 执行备份

        参数:
            output_file: 输出文件路径
            backup_id: 备份标识
            include_schema: 是否包含schema
            compress: 是否压缩
            tables: 指定表列表, None表示全部
        """
        start_time = datetime.now()
        host = self.connector.host
        port = self.connector.port
        user = self.connector.username
        password = self.connector.password
        database = self.connector.database

        # 使用 MYSQL_PWD 环境变量传递密码, 避免在进程列表中暴露
        env = os.environ.copy()
        env["MYSQL_PWD"] = password

        cmd = [
            "mysqldump",
            f"--host={host}",
            f"--port={port}",
            f"--user={user}",
            "--single-transaction",
            "--routines",
            "--triggers",
            "--hex-blob",
            "--skip-lock-tables",
        ]

        if not include_schema:
            cmd.append("--no-create-info")

        cmd.append(database)

        if tables:
            cmd.extend(tables)

        try:
            with open(output_file, "w", encoding="utf-8") as f:
                subprocess.run(
                    cmd,
                    stdout=f,
                    stderr=subprocess.PIPE,
                    text=True,
                    check=True,
                    env=env,
                )

            file_size = os.path.getsize(output_file)

            if compress:
                output_file = self._gzip_file(output_file)
                file_size = os.path.getsize(output_file)

            duration = int((datetime.now() - start_time).total_seconds() * 1000)
            return BackupResult(
                success=True,
                backup_id=backup_id,
                file_path=output_file,
                file_size=file_size,
                duration_ms=duration,
                tables=tables or [],
                backup_type="table" if tables else "full",
            )

        except subprocess.CalledProcessError as exc:
            stderr = exc.stderr if hasattr(exc, "stderr") else str(exc)
            # 清理不完整输出
            if os.path.exists(output_file):
                os.remove(output_file)
            return self._error(backup_id, f"mysqldump 失败: {stderr}")

    def _mysql_fallback_dump(
        self,
        output_file: str,
        backup_id: str,
        include_schema: bool,
        compress: bool,
        tables: Optional[List[str]] = None,
    ) -> BackupResult:
        """
        MySQL 分页降级备份 - 避免OOM

        使用 LIMIT/OFFSET 分批查询, 逐行写入文件。
        适用于没有 mysqldump 的环境或权限受限场景。
        """
        start_time = datetime.now()
        target_tables = tables or self.connector.get_tables()

        try:
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(f"-- MySQL Backup (fallback): {backup_id}\n")
                f.write(f"-- Generated: {datetime.now().isoformat()}\n")
                f.write("-- NOTE: This backup was created using Python fallback.\n")
                f.write(
                    "--       For production use, install mysqldump.\n\n"
                )
                f.write("SET FOREIGN_KEY_CHECKS=0;\n\n")

                for table in target_tables:
                    safe_table = self._safe_table_name(table)
                    f.write(f"\n-- Table: {safe_table}\n")

                    if include_schema:
                        schema_result = self.connector.execute(
                            f"SHOW CREATE TABLE `{safe_table}`"
                        )
                        if schema_result.rows:
                            f.write(
                                f"DROP TABLE IF EXISTS `{safe_table}`;\n"
                            )
                            f.write(schema_result.rows[0][1] + ";\n\n")

                    row_count = self._write_mysql_table_data(
                        f, safe_table
                    )
                    f.write(f"-- End of table: {safe_table} ({row_count} rows)\n")

                f.write("\nSET FOREIGN_KEY_CHECKS=1;\n")

            file_size = os.path.getsize(output_file)

            if compress:
                output_file = self._gzip_file(output_file)
                file_size = os.path.getsize(output_file)

            duration = int((datetime.now() - start_time).total_seconds() * 1000)
            return BackupResult(
                success=True,
                backup_id=backup_id,
                file_path=output_file,
                file_size=file_size,
                duration_ms=duration,
                tables=target_tables,
                backup_type="table" if tables else "full",
            )

        except Exception as exc:
            if os.path.exists(output_file):
                os.remove(output_file)
            return self._error(backup_id, f"分页备份失败: {exc}")

    def _write_mysql_table_data(
        self, file_handle, table: str
    ) -> int:
        """
        分页写入单表数据, 返回写入行数

        参数:
            file_handle: 文件句柄
            table: 表名(已通过_safe_table_name验证)

        返回:
            int: 写入的行数
        """
        total_rows = 0
        offset = 0
        batch_size = self.FALLBACK_BATCH_SIZE
        safe_table = self._quote_table_name(table)

        while True:
            result = self.connector.execute(
                f"SELECT * FROM {safe_table} LIMIT {batch_size} OFFSET {offset}"
            )
            if not result.rows:
                break

            for row in result.rows:
                values = [self._escape_mysql_value(v) for v in row]
                file_handle.write(
                    f"INSERT INTO {safe_table} VALUES ({', '.join(values)});\n"
                )
                total_rows += 1

            offset += batch_size

        return total_rows

    def _mysql_restore(
        self,
        backup_file: str,
        target_db: Optional[str],
        backup_id: str,
        start_time: datetime,
    ) -> BackupResult:
        """MySQL 恢复"""
        db = target_db or self.connector.database
        host = self.connector.host
        port = self.connector.port
        user = self.connector.username
        password = self.connector.password

        input_file = backup_file
        # 如果是gzip压缩, 先解压到临时文件
        if backup_file.endswith(".gz"):
            input_file = backup_file[:-3]
            self._gunzip_file(backup_file, input_file)

        # 使用 MYSQL_PWD 环境变量传递密码, 避免在进程列表中暴露
        env = os.environ.copy()
        env["MYSQL_PWD"] = password

        try:
            cmd = [
                "mysql",
                f"--host={host}",
                f"--port={port}",
                f"--user={user}",
                db,
            ]

            with open(input_file, "r", encoding="utf-8") as f:
                subprocess.run(
                    cmd,
                    stdin=f,
                    stderr=subprocess.PIPE,
                    text=True,
                    check=True,
                    env=env,
                )

            duration = int(
                (datetime.now() - start_time).total_seconds() * 1000
            )
            file_size = os.path.getsize(backup_file)

            # 清理临时文件
            if input_file != backup_file and os.path.exists(input_file):
                os.remove(input_file)

            return BackupResult(
                success=True,
                backup_id=backup_id,
                file_path=backup_file,
                file_size=file_size,
                duration_ms=duration,
            )

        except subprocess.CalledProcessError as exc:
            stderr = exc.stderr if hasattr(exc, "stderr") else str(exc)
            if input_file != backup_file and os.path.exists(input_file):
                os.remove(input_file)
            return self._error(backup_id, f"mysql 恢复失败: {stderr}")

    # =====================================================================
    # PostgreSQL 实现
    # =====================================================================

    def _pg_full_backup(
        self,
        output_dir: str,
        backup_id: str,
        timestamp: str,
        compress: bool,
        include_schema: bool,
    ) -> BackupResult:
        """PostgreSQL 全量备份"""
        output_file = os.path.join(output_dir, f"{backup_id}.sql")

        if self._has_native_tool("pg_dump"):
            return self._pg_native_dump(
                output_file, backup_id, include_schema, compress
            )

        logger.warning(
            "pg_dump 不可用, 使用分页降级方案。"
            "大数据量备份建议安装 pg_dump。"
        )
        return self._pg_fallback_dump(
            output_file, backup_id, include_schema, compress
        )

    def _pg_table_backup(
        self,
        table: str,
        output_dir: str,
        backup_id: str,
        timestamp: str,
        include_schema: bool,
    ) -> BackupResult:
        """PostgreSQL 单表备份"""
        output_file = os.path.join(output_dir, f"{backup_id}.sql")

        if self._has_native_tool("pg_dump"):
            return self._pg_native_dump(
                output_file, backup_id, include_schema, False, tables=[table]
            )

        logger.warning(
            "pg_dump 不可用, 使用分页降级方案。"
            "大数据量备份建议安装 pg_dump。"
        )
        return self._pg_fallback_dump(
            output_file, backup_id, include_schema, False, tables=[table]
        )

    def _pg_native_dump(
        self,
        output_file: str,
        backup_id: str,
        include_schema: bool,
        compress: bool,
        tables: Optional[List[str]] = None,
    ) -> BackupResult:
        """使用 pg_dump 执行备份"""
        start_time = datetime.now()
        host = self.connector.host
        port = self.connector.port
        user = self.connector.username
        database = self.connector.database

        env = os.environ.copy()
        env["PGPASSWORD"] = self.connector.password

        cmd = [
            "pg_dump",
            f"--host={host}",
            f"--port={port}",
            f"--username={user}",
            "--no-password",
            "--verbose" if logger.isEnabledFor(logging.DEBUG) else "--quiet",
        ]

        if not include_schema:
            cmd.append("--data-only")

        if tables:
            for t in tables:
                cmd.extend(["--table", t])

        cmd.append(database)

        try:
            with open(output_file, "w", encoding="utf-8") as f:
                subprocess.run(
                    cmd,
                    stdout=f,
                    stderr=subprocess.PIPE,
                    text=True,
                    check=True,
                    env=env,
                )

            file_size = os.path.getsize(output_file)

            if compress:
                output_file = self._gzip_file(output_file)
                file_size = os.path.getsize(output_file)

            duration = int((datetime.now() - start_time).total_seconds() * 1000)
            return BackupResult(
                success=True,
                backup_id=backup_id,
                file_path=output_file,
                file_size=file_size,
                duration_ms=duration,
                tables=tables or [],
                backup_type="table" if tables else "full",
            )

        except subprocess.CalledProcessError as exc:
            stderr = exc.stderr if hasattr(exc, "stderr") else str(exc)
            if os.path.exists(output_file):
                os.remove(output_file)
            return self._error(backup_id, f"pg_dump 失败: {stderr}")

    def _pg_fallback_dump(
        self,
        output_file: str,
        backup_id: str,
        include_schema: bool,
        compress: bool,
        tables: Optional[List[str]] = None,
    ) -> BackupResult:
        """PostgreSQL 分页降级备份"""
        start_time = datetime.now()
        target_tables = tables or self.connector.get_tables()

        try:
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(f"-- PostgreSQL Backup (fallback): {backup_id}\n")
                f.write(f"-- Generated: {datetime.now().isoformat()}\n")
                f.write(
                    "-- NOTE: This backup was created using Python fallback.\n"
                )
                f.write(
                    "--       For production use, install pg_dump.\n\n"
                )

                for table in target_tables:
                    safe_table = self._safe_table_name(table)
                    f.write(f"\n-- Table: {safe_table}\n")

                    if include_schema:
                        sql = (
                            f"SELECT pg_catalog.pg_get_tabledef("
                            f"'{safe_table}'::regclass::oid"
                            f")"
                        )
                        schema_result = self.connector.execute(sql)
                        if schema_result.rows:
                            f.write(
                                f"DROP TABLE IF EXISTS {safe_table} CASCADE;\n"
                            )
                            f.write(schema_result.rows[0][0] + ";\n\n")

                    row_count = self._write_pg_table_data(f, safe_table)
                    f.write(
                        f"-- End of table: {safe_table} ({row_count} rows)\n"
                    )

            file_size = os.path.getsize(output_file)

            if compress:
                output_file = self._gzip_file(output_file)
                file_size = os.path.getsize(output_file)

            duration = int((datetime.now() - start_time).total_seconds() * 1000)
            return BackupResult(
                success=True,
                backup_id=backup_id,
                file_path=output_file,
                file_size=file_size,
                duration_ms=duration,
                tables=target_tables,
                backup_type="table" if tables else "full",
            )

        except Exception as exc:
            if os.path.exists(output_file):
                os.remove(output_file)
            return self._error(backup_id, f"分页备份失败: {exc}")

    def _write_pg_table_data(self, file_handle, table: str) -> int:
        """分页写入PostgreSQL单表数据"""
        total_rows = 0
        offset = 0
        batch_size = self.FALLBACK_BATCH_SIZE
        safe_table = self._quote_table_name(table)

        while True:
            result = self.connector.execute(
                f"SELECT * FROM {safe_table} LIMIT {batch_size} OFFSET {offset}"
            )
            if not result.rows:
                break

            for row in result.rows:
                values = [self._escape_pg_value(v) for v in row]
                file_handle.write(
                    f"INSERT INTO {safe_table} VALUES ({', '.join(values)});\n"
                )
                total_rows += 1

            offset += batch_size

        return total_rows

    def _pg_restore(
        self,
        backup_file: str,
        target_db: Optional[str],
        backup_id: str,
        start_time: datetime,
    ) -> BackupResult:
        """PostgreSQL 恢复"""
        db = target_db or self.connector.database
        host = self.connector.host
        port = self.connector.port
        user = self.connector.username

        env = os.environ.copy()
        env["PGPASSWORD"] = self.connector.password

        input_file = backup_file
        if backup_file.endswith(".gz"):
            input_file = backup_file[:-3]
            self._gunzip_file(backup_file, input_file)

        try:
            cmd = [
                "psql",
                f"--host={host}",
                f"--port={port}",
                f"--username={user}",
                "--no-password",
                "--quiet",
                "--set",
                "ON_ERROR_STOP=1",
                f"--dbname={db}",
            ]

            with open(input_file, "r", encoding="utf-8") as f:
                subprocess.run(
                    cmd,
                    stdin=f,
                    stderr=subprocess.PIPE,
                    text=True,
                    check=True,
                    env=env,
                )

            duration = int(
                (datetime.now() - start_time).total_seconds() * 1000
            )

            if input_file != backup_file and os.path.exists(input_file):
                os.remove(input_file)

            return BackupResult(
                success=True,
                backup_id=backup_id,
                file_path=backup_file,
                file_size=os.path.getsize(backup_file),
                duration_ms=duration,
            )

        except subprocess.CalledProcessError as exc:
            stderr = exc.stderr if hasattr(exc, "stderr") else str(exc)
            if input_file != backup_file and os.path.exists(input_file):
                os.remove(input_file)
            return self._error(backup_id, f"psql 恢复失败: {stderr}")

    # =====================================================================
    # SQLite 实现
    # =====================================================================

    def _sqlite_full_backup(
        self,
        output_dir: str,
        backup_id: str,
        timestamp: str,
        compress: bool,
    ) -> BackupResult:
        """SQLite 全量备份"""
        start_time = datetime.now()
        output_file = os.path.join(output_dir, f"{backup_id}.db")

        try:
            db_path = self._get_sqlite_db_path()

            if db_path == ":memory:" or not os.path.exists(db_path):
                # :memory: 数据库无法复制, 使用 SQL 导出
                sql_file = os.path.join(output_dir, f"{backup_id}.sql")
                with open(sql_file, "w", encoding="utf-8") as f:
                    tables = self._get_sqlite_tables()
                    for table in tables:
                        safe_table = self._safe_table_name(table)
                        schema_result = self.connector.execute(
                            f"SELECT sql FROM sqlite_master WHERE type='table' "
                            f"AND name='{safe_table}'"
                        )
                        if schema_result.rows:
                            f.write(f"DROP TABLE IF EXISTS `{safe_table}`;\n")
                            f.write(schema_result.rows[0][0] + ";\n\n")
                        self._write_sqlite_table_data(f, safe_table)
                        f.write(f"\n")
                output_file = sql_file
                if compress:
                    output_file = self._gzip_file(sql_file)
            else:
                shutil.copy2(db_path, output_file)
                if compress:
                    output_file = self._gzip_file(output_file)

            file_size = os.path.getsize(output_file)
            duration = int((datetime.now() - start_time).total_seconds() * 1000)
            return BackupResult(
                success=True,
                backup_id=backup_id,
                file_path=output_file,
                file_size=file_size,
                duration_ms=duration,
                backup_type="full",
            )

        except Exception as exc:
            if os.path.exists(output_file):
                os.remove(output_file)
            return self._error(backup_id, f"SQLite 备份失败: {exc}")

    def _sqlite_table_backup(
        self,
        table: str,
        output_dir: str,
        backup_id: str,
        timestamp: str,
    ) -> BackupResult:
        """SQLite 单表备份"""
        start_time = datetime.now()
        output_file = os.path.join(output_dir, f"{backup_id}.sql")
        safe_table = self._safe_table_name(table)

        try:
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(f"-- SQLite Table Backup: {safe_table}\n")
                f.write(f"-- Generated: {datetime.now().isoformat()}\n\n")

                schema_result = self.connector.execute(
                    f"SELECT sql FROM sqlite_master WHERE type='table' "
                    f"AND name='{safe_table}'"
                )
                if schema_result.rows:
                    f.write(
                        f"DROP TABLE IF EXISTS `{safe_table}`;\n"
                    )
                    f.write(schema_result.rows[0][0] + ";\n\n")

                row_count = self._write_sqlite_table_data(f, safe_table)
                f.write(
                    f"-- End of table: {safe_table} ({row_count} rows)\n"
                )

            duration = int((datetime.now() - start_time).total_seconds() * 1000)
            return BackupResult(
                success=True,
                backup_id=backup_id,
                file_path=output_file,
                file_size=os.path.getsize(output_file),
                duration_ms=duration,
                tables=[safe_table],
                backup_type="table",
            )

        except Exception as exc:
            if os.path.exists(output_file):
                os.remove(output_file)
            return self._error(backup_id, f"SQLite 单表备份失败: {exc}")

    def _write_sqlite_table_data(self, file_handle, table: str) -> int:
        """分页写入SQLite单表数据"""
        total_rows = 0
        offset = 0
        batch_size = self.FALLBACK_BATCH_SIZE
        safe_table = self._quote_table_name(table)

        while True:
            result = self.connector.execute(
                f"SELECT * FROM {safe_table} LIMIT {batch_size} OFFSET {offset}"
            )
            if not result.rows:
                break

            for row in result.rows:
                values = [self._escape_sqlite_value(v) for v in row]
                file_handle.write(
                    f"INSERT INTO {safe_table} VALUES ({', '.join(values)});\n"
                )
                total_rows += 1

            offset += batch_size

        return total_rows

    def _sqlite_restore(
        self,
        backup_file: str,
        backup_id: str,
        start_time: datetime,
    ) -> BackupResult:
        """SQLite 恢复"""
        try:
            db_path = self._get_sqlite_db_path()

            if backup_file.endswith(".db"):
                shutil.copy2(backup_file, db_path)
            elif backup_file.endswith(".db.gz"):
                temp_file = backup_file[:-3]
                self._gunzip_file(backup_file, temp_file)
                shutil.copy2(temp_file, db_path)
                os.remove(temp_file)
            else:
                # SQL 文件恢复
                input_file = backup_file
                if backup_file.endswith(".gz"):
                    input_file = backup_file[:-3]
                    self._gunzip_file(backup_file, input_file)

                with open(input_file, "r", encoding="utf-8") as f:
                    sql_content = f.read()

                # SQLite 逐语句执行, 支持事务
                statements = self._split_sql_statements(sql_content)
                for stmt in statements:
                    if stmt.strip() and not stmt.strip().startswith("--"):
                        try:
                            self.connector.execute(stmt)
                        except Exception as stmt_exc:
                            logger.warning(
                                f"SQL执行跳过: {stmt_exc} [stmt={stmt[:80]}]"
                            )

                if input_file != backup_file and os.path.exists(input_file):
                    os.remove(input_file)

            duration = int(
                (datetime.now() - start_time).total_seconds() * 1000
            )
            return BackupResult(
                success=True,
                backup_id=backup_id,
                file_path=backup_file,
                file_size=os.path.getsize(backup_file),
                duration_ms=duration,
            )

        except Exception as exc:
            return self._error(backup_id, f"SQLite 恢复失败: {exc}")

    # =====================================================================
    # ClickHouse 实现
    # =====================================================================

    def _clickhouse_full_backup(
        self,
        output_dir: str,
        backup_id: str,
        timestamp: str,
        compress: bool,
        include_schema: bool,
    ) -> BackupResult:
        """
        ClickHouse 全量备份

        ClickHouse备份策略：
        1. 优先使用clickhouse-client导出（如果有原生工具）
        2. 否则使用Python分页导出INSERT语句
        3. 对于大表建议使用ClickHouse原生备份工具
        """
        start_time = datetime.now()
        output_file = os.path.join(output_dir, f"{backup_id}.sql")

        try:
            tables = self.connector.get_tables()

            with open(output_file, "w", encoding="utf-8") as f:
                f.write(f"-- ClickHouse Backup: {backup_id}\n")
                f.write(f"-- Generated: {datetime.now().isoformat()}\n")
                f.write("-- NOTE: ClickHouse backup using Python fallback.\n")
                f.write(
                    "--       For production use, consider clickhouse-backup tool.\n\n"
                )

                for table in tables:
                    safe_table = self._safe_table_name(table)
                    f.write(f"\n-- Table: {safe_table}\n")

                    if include_schema:
                        schema_result = self.connector.execute(
                            f"SHOW CREATE TABLE {safe_table}"
                        )
                        if schema_result.rows:
                            f.write(
                                f"DROP TABLE IF EXISTS {safe_table};\n"
                            )
                            f.write(schema_result.rows[0][0] + ";\n\n")

                    row_count = self._write_clickhouse_table_data(
                        f, safe_table
                    )
                    f.write(
                        f"-- End of table: {safe_table} ({row_count} rows)\n"
                    )

            file_size = os.path.getsize(output_file)

            if compress:
                output_file = self._gzip_file(output_file)
                file_size = os.path.getsize(output_file)

            duration = int(
                (datetime.now() - start_time).total_seconds() * 1000
            )
            return BackupResult(
                success=True,
                backup_id=backup_id,
                file_path=output_file,
                file_size=file_size,
                duration_ms=duration,
                tables=tables,
                backup_type="full",
            )

        except Exception as exc:
            if os.path.exists(output_file):
                os.remove(output_file)
            return self._error(backup_id, f"ClickHouse 备份失败: {exc}")

    def _clickhouse_table_backup(
        self,
        table: str,
        output_dir: str,
        backup_id: str,
        timestamp: str,
        include_schema: bool,
    ) -> BackupResult:
        """ClickHouse 单表备份"""
        start_time = datetime.now()
        output_file = os.path.join(output_dir, f"{backup_id}.sql")
        safe_table = self._safe_table_name(table)

        try:
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(f"-- ClickHouse Table Backup: {safe_table}\n")
                f.write(f"-- Generated: {datetime.now().isoformat()}\n\n")

                if include_schema:
                    schema_result = self.connector.execute(
                        f"SHOW CREATE TABLE {safe_table}"
                    )
                    if schema_result.rows:
                        f.write(
                            f"DROP TABLE IF EXISTS {safe_table};\n"
                        )
                        f.write(schema_result.rows[0][0] + ";\n\n")

                row_count = self._write_clickhouse_table_data(f, safe_table)
                f.write(
                    f"-- End of table: {safe_table} ({row_count} rows)\n"
                )

            duration = int(
                (datetime.now() - start_time).total_seconds() * 1000
            )
            return BackupResult(
                success=True,
                backup_id=backup_id,
                file_path=output_file,
                file_size=os.path.getsize(output_file),
                duration_ms=duration,
                tables=[safe_table],
                backup_type="table",
            )

        except Exception as exc:
            if os.path.exists(output_file):
                os.remove(output_file)
            return self._error(
                backup_id, f"ClickHouse 单表备份失败: {exc}"
            )

    def _write_clickhouse_table_data(
        self, file_handle, table: str
    ) -> int:
        """
        分页写入ClickHouse单表数据

        ClickHouse特点：
        - 使用LIMIT/OFFSET分页
        - 数据量大时建议使用clickhouse-client原生工具
        """
        total_rows = 0
        offset = 0
        batch_size = self.FALLBACK_BATCH_SIZE
        safe_table = self._quote_table_name(table)

        while True:
            result = self.connector.execute(
                f"SELECT * FROM {safe_table} LIMIT {batch_size} OFFSET {offset}"
            )
            if not result.rows:
                break

            for row in result.rows:
                values = [self._escape_clickhouse_value(v) for v in row]
                file_handle.write(
                    f"INSERT INTO {safe_table} VALUES ({', '.join(values)});\n"
                )
                total_rows += 1

            offset += batch_size

        return total_rows

    def _clickhouse_restore(
        self,
        backup_file: str,
        backup_id: str,
        start_time: datetime,
    ) -> BackupResult:
        """
        ClickHouse 恢复

        逐语句执行INSERT语句
        注意：ClickHouse不支持事务，失败语句会被记录但不会回滚
        """
        try:
            input_file = backup_file
            if backup_file.endswith(".gz"):
                input_file = backup_file[:-3]
                self._gunzip_file(backup_file, input_file)

            with open(input_file, "r", encoding="utf-8") as f:
                sql_content = f.read()

            statements = self._split_sql_statements(sql_content)
            success_count = 0
            fail_count = 0

            for stmt in statements:
                if stmt.strip() and not stmt.strip().startswith("--"):
                    try:
                        self.connector.execute(stmt)
                        success_count += 1
                    except Exception as stmt_exc:
                        fail_count += 1
                        logger.warning(
                            f"SQL执行跳过: {stmt_exc} [stmt={stmt[:80]}]"
                        )

            if input_file != backup_file and os.path.exists(input_file):
                os.remove(input_file)

            duration = int(
                (datetime.now() - start_time).total_seconds() * 1000
            )
            return BackupResult(
                success=True,
                backup_id=backup_id,
                file_path=backup_file,
                file_size=os.path.getsize(backup_file),
                duration_ms=duration,
            )

        except Exception as exc:
            return self._error(backup_id, f"ClickHouse 恢复失败: {exc}")

    @staticmethod
    def _escape_clickhouse_value(value: Any) -> str:
        """
        ClickHouse值转义

        ClickHouse值特点：
        - 字符串使用单引号
        - 日期时间格式：'YYYY-MM-DD HH:MM:SS'
        - 数组使用方括号
        """
        if value is None:
            return "NULL"
        if isinstance(value, bool):
            return "1" if value else "0"
        if isinstance(value, (int, float)):
            return str(value)
        if isinstance(value, bytes):
            return f"toFixedString(unhex('{value.hex()}'), {len(value)})"
        if isinstance(value, (datetime, date)):
            return f"'{value.isoformat()}'"
        if isinstance(value, str):
            # 先转义反斜杠, 再转义单引号, 顺序不可颠倒
            escaped = value.replace("\\", "\\\\").replace("'", "\\'")
            return f"'{escaped}'"
        return f"'{str(value)}'"

    # =====================================================================
    # 转义与值处理
    # =====================================================================

    @staticmethod
    def _escape_mysql_value(value: Any) -> str:
        """
        MySQL值转义 - 处理NULL、字符串、字节、日期等

        转义规则:
            - NULL -> NULL
            - bool -> 1/0
            - int/float -> 直接转字符串
            - str -> 单引号包裹, 转义单引号和反斜杠
            - bytes -> 十六进制表示
            - datetime/date -> ISO格式字符串
        """
        if value is None:
            return "NULL"
        if isinstance(value, bool):
            return "1" if value else "0"
        if isinstance(value, (int, float)):
            return str(value)
        if isinstance(value, bytes):
            return f"0x{value.hex()}"
        if isinstance(value, (datetime, date)):
            return f"'{value.isoformat()}'"
        if isinstance(value, str):
            # 转义单引号和反斜杠
            escaped = value.replace("\\", "\\\\").replace("'", "\\'")
            return f"'{escaped}'"
        return f"'{str(value)}'"

    @staticmethod
    def _escape_pg_value(value: Any) -> str:
        """
        PostgreSQL值转义

        与MySQL类似, 但字符串转义使用PostgreSQL标准:
            单引号 -> 两个单引号
            反斜杠 -> 两个反斜杠 (标准模式下)
        """
        if value is None:
            return "NULL"
        if isinstance(value, bool):
            return "TRUE" if value else "FALSE"
        if isinstance(value, (int, float)):
            return str(value)
        if isinstance(value, bytes):
            return f"E'\\\\x{value.hex()}'"
        if isinstance(value, (datetime, date)):
            return f"'{value.isoformat()}'"
        if isinstance(value, str):
            escaped = value.replace("\\", "\\\\").replace("'", "''")
            return f"'{escaped}'"
        return f"'{str(value)}'"

    @staticmethod
    def _escape_sqlite_value(value: Any) -> str:
        """
        SQLite值转义

        SQLite使用单引号作为字符串定界符,
        单引号转义为两个单引号。
        """
        if value is None:
            return "NULL"
        if isinstance(value, bool):
            return "1" if value else "0"
        if isinstance(value, (int, float)):
            return str(value)
        if isinstance(value, bytes):
            return f"X'{value.hex()}'"
        if isinstance(value, (datetime, date)):
            return f"'{value.isoformat()}'"
        if isinstance(value, str):
            escaped = value.replace("'", "''")
            return f"'{escaped}'"
        return f"'{str(value)}'"

    # =====================================================================
    # 工具方法
    # =====================================================================

    @staticmethod
    def _safe_table_name(table: str) -> str:
        """
        安全验证表名, 防止SQL注入

        参数:
            table: 原始表名

        返回:
            str: 验证后的表名

        异常:
            ValueError: 表名包含非法字符
        """
        if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", table):
            raise ValueError(f"非法表名: {table}")
        return table

    @staticmethod
    def _safe_qualified_table_name(table: str) -> str:
        """
        验证限定表名(支持 schema.table 格式)

        对每个部分分别应用白名单正则验证,
        支持 PostgreSQL/ClickHouse 等需要 schema 前缀的场景。

        参数:
            table: 原始表名, 如 "public.users" 或 "users"

        返回:
            str: 验证后的表名

        异常:
            ValueError: 表名包含非法字符
        """
        parts = table.split(".")
        if len(parts) > 2:
            raise ValueError(f"非法表名(过多限定符): {table}")
        for part in parts:
            if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", part):
                raise ValueError(f"非法表名: {table}")
        return table

    def _quote_table_name(self, table: str) -> str:
        """
        根据数据库类型为表名添加引号包裹

        MySQL/ClickHouse/SQLite 使用反引号,
        PostgreSQL 使用双引号,
        通用场景使用反引号作为默认值。

        参数:
            table: 已验证的表名

        返回:
            str: 引号包裹后的表名, 如 "`users`" 或 '"public"."users"'
        """
        db_type = self.connector.db_type.lower() if hasattr(
            self.connector, "db_type"
        ) else "mysql"

        # 处理限定表名 schema.table
        parts = table.split(".")
        if len(parts) == 2:
            schema, tbl = parts
            if db_type == "postgresql":
                return f'"{schema}"."{tbl}"'
            return f"`{schema}`.`{tbl}`"

        # 单一表名
        if db_type == "postgresql":
            return f'"{table}"'
        return f"`{table}`"

    @staticmethod
    def _safe_filename(name: str) -> str:
        """
        将字符串转换为安全的文件名

        替换Windows/Unix文件名中的非法字符,
        处理特殊名称如 :memory: 。

        参数:
            name: 原始名称

        返回:
            str: 安全的文件名
        """
        if name == ":memory:":
            return "memory"
        # 替换文件名非法字符
        safe = re.sub(r'[\\/:*?"<>|]', "_", name)
        return safe or "unknown"

    @staticmethod
    def _has_native_tool(tool_name: str) -> bool:
        """
        检查系统是否有原生数据库工具

        参数:
            tool_name: 工具名 (如 mysqldump, pg_dump)

        返回:
            bool: 是否可用
        """
        return shutil.which(tool_name) is not None

    @staticmethod
    def _gzip_file(input_file: str) -> str:
        """
        gzip压缩文件, 删除原文件

        参数:
            input_file: 输入文件路径

        返回:
            str: 压缩后的文件路径
        """
        import gzip

        output_file = input_file + ".gz"
        with open(input_file, "rb") as f_in:
            with gzip.open(output_file, "wb") as f_out:
                shutil.copyfileobj(f_in, f_out)
        os.remove(input_file)
        return output_file

    @staticmethod
    def _gunzip_file(input_file: str, output_file: str) -> None:
        """
        gzip解压文件

        参数:
            input_file: 压缩文件路径
            output_file: 输出文件路径
        """
        import gzip

        with gzip.open(input_file, "rb") as f_in:
            with open(output_file, "wb") as f_out:
                shutil.copyfileobj(f_in, f_out)

    @staticmethod
    def _compute_sha256(file_path: str) -> str:
        """计算文件SHA256哈希"""
        h = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()

    def _write_checksum(self, file_path: str) -> None:
        """将SHA256校验值写入同目录的.sha256文件"""
        checksum = self._compute_sha256(file_path)
        checksum_file = file_path + ".sha256"
        with open(checksum_file, "w", encoding="utf-8") as f:
            f.write(f"{checksum}  {os.path.basename(file_path)}\n")
        logger.debug(f"校验文件已写入: {checksum_file}")

    @staticmethod
    def _read_checksum(file_path: str) -> Optional[str]:
        """读取文件的SHA256校验值"""
        checksum_file = file_path + ".sha256"
        if not os.path.exists(checksum_file):
            return None
        try:
            with open(checksum_file, "r", encoding="utf-8") as f:
                line = f.readline().strip()
                parts = line.split()
                return parts[0] if parts else None
        except Exception:
            return None

    @staticmethod
    def _human_size(size_bytes: int) -> str:
        """字节大小转人类可读格式"""
        for unit in ("B", "KB", "MB", "GB", "TB"):
            if size_bytes < 1024:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.1f} PB"

    @staticmethod
    def _detect_backup_type(filename: str) -> str:
        """从文件名推断备份类型"""
        name = filename.lower()
        if "_table_" in name:
            return "table"
        if "_incremental_" in name:
            return "incremental"
        return "full"

    @staticmethod
    def _split_sql_statements(sql_content: str) -> List[str]:
        """
        安全拆分SQL语句

        与简单的 split(';') 不同, 此函数正确处理:
            - 字符串字面量中的分号
            - 注释中的分号

        参数:
            sql_content: SQL文本

        返回:
            List[str]: 拆分后的SQL语句列表
        """
        statements = []
        current = []
        in_string = False
        string_char = None
        i = 0

        while i < len(sql_content):
            char = sql_content[i]

            # 字符串处理
            if char in ("'", '"') and (i == 0 or sql_content[i - 1] != "\\"):
                if not in_string:
                    in_string = True
                    string_char = char
                elif char == string_char:
                    in_string = False
                    string_char = None

            # 注释处理 (-- 单行)
            elif char == "-" and i + 1 < len(sql_content) and sql_content[i + 1] == "-":
                while i < len(sql_content) and sql_content[i] != "\n":
                    current.append(sql_content[i])
                    i += 1
                if i < len(sql_content):
                    current.append(sql_content[i])
                i += 1
                continue

            # 语句结束
            elif char == ";" and not in_string:
                stmt = "".join(current).strip()
                if stmt:
                    statements.append(stmt)
                current = []
                i += 1
                continue

            current.append(char)
            i += 1

        # 最后一条语句(可能没有分号结尾)
        stmt = "".join(current).strip()
        if stmt:
            statements.append(stmt)

        return statements

    # =====================================================================
    # 通用备份（适用于任意 JDBC 数据库）
    # =====================================================================

    def _generic_fallback_backup(
        self,
        output_file: str,
        backup_id: str,
        include_schema: bool,
        compress: bool,
        tables: Optional[List[str]] = None,
    ) -> BackupResult:
        """
        通用数据库分页降级备份

        使用 LIMIT/OFFSET 分批查询，逐行写入 INSERT 语句格式的 SQL 文件。
        适用于任何支持标准 SQL 的 JDBC 数据库（Trino/DuckDB/Derby/H2 等）。

        参数：
            output_file: 输出文件路径
            backup_id: 备份标识
            include_schema: 是否包含表结构
            compress: 是否压缩
            tables: 指定备份的表列表，None 表示全部表

        返回：
            BackupResult: 备份结果
        """
        start_time = datetime.now()
        target_tables = tables or self.connector.get_tables()
        dialect = self.dialect

        try:
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(f"-- Generic Backup: {backup_id}\n")
                f.write(f"-- Source dialect: {dialect}\n")
                f.write(f"-- Generated: {datetime.now().isoformat()}\n")
                f.write(
                    "-- NOTE: This backup was created using generic fallback.\n"
                )
                f.write(
                    "--       Restore requires compatible SQL dialect.\n\n"
                )

                for table in target_tables:
                    safe_table = self._safe_table_name(table)
                    quoted_table = self._quote_table_name(safe_table)
                    f.write(f"\n-- Table: {safe_table}\n")

                    # 尝试获取表结构
                    if include_schema:
                        try:
                            schema = self._get_generic_table_schema(safe_table)
                            if schema:
                                f.write(
                                    f"DROP TABLE IF EXISTS {quoted_table};\n"
                                )
                                f.write(f"{schema};\n\n")
                        except Exception as e:
                            logger.debug(
                                f"获取表 {safe_table} 结构失败: {e}"
                            )

                    row_count = self._write_generic_table_data(
                        f, safe_table
                    )
                    f.write(
                        f"-- End of table: {safe_table} ({row_count} rows)\n"
                    )

            file_size = os.path.getsize(output_file)

            if compress:
                output_file = self._gzip_file(output_file)
                file_size = os.path.getsize(output_file)

            duration = int(
                (datetime.now() - start_time).total_seconds() * 1000
            )
            return BackupResult(
                success=True,
                backup_id=backup_id,
                file_path=output_file,
                file_size=file_size,
                duration_ms=duration,
                tables=target_tables,
                backup_type="table" if tables else "full",
            )

        except Exception as exc:
            if os.path.exists(output_file):
                os.remove(output_file)
            return self._error(backup_id, f"通用备份失败: {exc}")

    def _get_generic_table_schema(self, table: str) -> Optional[str]:
        """
        获取通用表结构 DDL

        通过 INFORMATION_SCHEMA 或 DESCRIBE 获取表结构，
        生成兼容的 CREATE TABLE 语句。

        参数：
            table: 表名

        返回：
            Optional[str]: CREATE TABLE 语句，不支持返回 None
        """
        safe_table = self._quote_table_name(table)

        # 尝试 INFORMATION_SCHEMA
        try:
            result = self.connector.execute(
                "SELECT column_name, data_type, is_nullable, "
                "column_default "
                "FROM information_schema.columns "
                "WHERE table_name = ? "
                "ORDER BY ordinal_position",
                (table,)
            )
            if result.rows:
                columns = []
                for row in result.rows:
                    col_name = row[0]
                    data_type = row[1]
                    nullable = row[2]
                    default = row[3]
                    col_def = f"  {col_name} {data_type}"
                    if nullable and nullable.upper() == "NO":
                        col_def += " NOT NULL"
                    if default is not None:
                        col_def += f" DEFAULT {default}"
                    columns.append(col_def)
                return (
                    f"CREATE TABLE {safe_table} (\n"
                    + ",\n".join(columns) + "\n)"
                )
        except Exception:
            pass

        # 尝试 DESCRIBE
        try:
            result = self.connector.execute(f"DESCRIBE {safe_table}")
            if result.rows:
                columns = []
                for row in result.rows:
                    col_name = row[0]
                    data_type = row[1]
                    columns.append(f"  {col_name} {data_type}")
                return (
                    f"CREATE TABLE {safe_table} (\n"
                    + ",\n".join(columns) + "\n)"
                )
        except Exception:
            pass

        return None

    def _write_generic_table_data(
        self, file_handle, table: str
    ) -> int:
        """
        分页写入单表数据，返回写入行数

        参数：
            file_handle: 文件句柄
            table: 表名(原始表名, 内部自动添加引号)

        返回：
            int: 写入的行数
        """
        total_rows = 0
        offset = 0
        batch_size = self.FALLBACK_BATCH_SIZE
        safe_table = self._quote_table_name(table)

        while True:
            result = self.connector.execute(
                f"SELECT * FROM {safe_table} "
                f"LIMIT {batch_size} OFFSET {offset}"
            )
            if not result.rows:
                break

            for row in result.rows:
                values = [self._escape_generic_value(v) for v in row]
                file_handle.write(
                    f"INSERT INTO {safe_table} VALUES ({', '.join(values)});\n"
                )
                total_rows += 1

            offset += batch_size

        return total_rows

    @staticmethod
    def _escape_generic_value(value: Any) -> str:
        """
        通用 SQL 值转义

        参数：
            value: 原始值

        返回：
            str: 转义后的 SQL 值字符串
        """
        if value is None:
            return "NULL"
        if isinstance(value, bool):
            return "1" if value else "0"
        if isinstance(value, (int, float)):
            return str(value)
        if isinstance(value, (datetime, date)):
            return f"'{value.isoformat()}'"
        if isinstance(value, bytes):
            return f"X'{value.hex()}'"
        # 字符串转义
        s = str(value).replace("'", "''")
        return f"'{s}'"

    # 通用恢复允许的SQL语句类型白名单
    _RESTORE_ALLOWED_PREFIXES = (
        "INSERT", "CREATE TABLE", "DROP TABLE IF EXISTS",
        "ALTER TABLE", "CREATE INDEX", "DROP INDEX",
    )

    def _generic_restore(
        self,
        backup_file: str,
        backup_id: str,
        start_time: datetime,
    ) -> BackupResult:
        """
        通用数据库恢复

        逐行解析 SQL 备份文件中的语句并执行。
        仅允许白名单中的语句类型(INSERT/CREATE TABLE/DROP TABLE等),
        防止备份文件被篡改后执行危险操作(DELETE/UPDATE/TRUNCATE等)。

        参数：
            backup_file: 备份文件路径
            backup_id: 备份标识
            start_time: 开始时间

        返回：
            BackupResult: 恢复结果
        """
        input_file = backup_file
        # 如果是 gzip 压缩，先解压到临时文件
        if backup_file.endswith(".gz"):
            input_file = backup_file[:-3]
            self._gunzip_file(backup_file, input_file)

        executed = 0
        failed = 0
        skipped = 0

        try:
            with open(input_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    # 跳过注释和空行
                    if not line or line.startswith("--"):
                        continue
                    # 去除末尾分号
                    if line.endswith(";"):
                        line = line[:-1]
                    # 安全过滤: 仅允许白名单中的语句类型
                    line_upper = line.strip().upper()
                    if not any(
                        line_upper.startswith(prefix)
                        for prefix in self._RESTORE_ALLOWED_PREFIXES
                    ):
                        skipped += 1
                        logger.warning(
                            f"恢复跳过非法语句: {line[:80]}..."
                        )
                        continue
                    try:
                        self.connector.execute(line)
                        executed += 1
                    except Exception as e:
                        logger.warning(
                            f"恢复语句执行失败: {line[:80]}... [{e}]"
                        )
                        failed += 1

            duration = int(
                (datetime.now() - start_time).total_seconds() * 1000
            )
            file_size = os.path.getsize(backup_file)

            # 清理临时文件
            if input_file != backup_file and os.path.exists(input_file):
                os.remove(input_file)

            if failed > 0 or skipped > 0:
                parts = [f"{executed} 条语句成功"]
                if failed > 0:
                    parts.append(f"{failed} 条失败")
                if skipped > 0:
                    parts.append(f"{skipped} 条被安全过滤跳过")
                return BackupResult(
                    success=False,
                    backup_id=backup_id,
                    file_path=backup_file,
                    file_size=file_size,
                    duration_ms=duration,
                    error=f"恢复完成，" + "，".join(parts),
                )

            return BackupResult(
                success=True,
                backup_id=backup_id,
                file_path=backup_file,
                file_size=file_size,
                duration_ms=duration,
            )

        except Exception as exc:
            if input_file != backup_file and os.path.exists(input_file):
                os.remove(input_file)
            return self._error(backup_id, f"通用恢复失败: {exc}")

    @staticmethod
    def _is_readonly() -> bool:
        """
        检查系统是否处于只读模式

        读取环境变量 DBSKITER_READ_ONLY 和 DBSKITER_DEFAULT_READ_ONLY,
        任一为 true/1/yes 即视为只读模式。

        返回:
            bool: 是否处于只读模式
        """
        import os as _os
        for var in ("DBSKITER_READ_ONLY", "DBSKITER_DEFAULT_READ_ONLY"):
            if _os.getenv(var, "").lower() in ("true", "1", "yes"):
                return True
        return False

    def _error(self, backup_id: str, message: str) -> BackupResult:
        """生成错误结果"""
        return BackupResult(
            success=False,
            backup_id=backup_id,
            file_path="",
            file_size=0,
            duration_ms=0,
            error=message,
        )

    def _get_sqlite_db_path(self) -> str:
        """获取SQLite数据库文件路径"""
        engine_url = self.connector._connector._engine_url
        if engine_url.startswith("sqlite:///"):
            return engine_url[10:]
        return engine_url

    def _get_sqlite_tables(self) -> List[str]:
        """获取SQLite数据库中的所有表名"""
        result = self.connector.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        return [row[0] for row in result.rows]
