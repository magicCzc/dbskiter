"""
db_scheduler/backup.py
数据库备份管理器
支持 MySQL / PostgreSQL / SQLite
"""

from dataclasses import dataclass
from datetime import datetime
from typing import List, Dict, Any, Optional
import os
import shutil

from dbskiter.shared.unified_connector import UnifiedConnector


@dataclass
class BackupInfo:
    """备份信息"""
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
    """备份结果"""
    success: bool
    backup_id: str
    file_path: str
    file_size: int
    duration_ms: int
    error: Optional[str] = None


class BackupManager:
    """
    数据库备份管理器

    用法:
        manager = BackupManager(connector)
        result = manager.backup_full(output_dir="/backups")
        print(result.file_path)
    """

    BACKUP_TYPE_FULL = "full"
    BACKUP_TYPE_INCREMENTAL = "incremental"
    BACKUP_TYPE_DIFFERENTIAL = "differential"
    BACKUP_TYPE_TABLE = "table"

    def _safe_table_name(self, table: str) -> str:
        """安全验证表名"""
        if hasattr(self.connector, '_validate_table_name'):
            return self.connector._validate_table_name(table)
        import re
        if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', table):
            raise ValueError(f"非法表名: {table}")
        return table

    def __init__(self, connector: UnifiedConnector):
        self.connector = connector
        self.dialect = connector.dialect.lower()
        self.default_output_dir = "./backups"

    def backup_full(
        self,
        output_dir: str = None,
        compress: bool = True,
        include_schema: bool = True
    ) -> BackupResult:
        """
        全量备份
        """
        output_dir = output_dir or self.default_output_dir
        os.makedirs(output_dir, exist_ok=True)

        backup_id = f"full_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

        if self.dialect in ("mysql", "mysql+pymysql"):
            return self._mysql_full_backup(output_dir, backup_id, timestamp, compress, include_schema)
        elif self.dialect == "postgresql":
            return self._postgresql_full_backup(output_dir, backup_id, timestamp, compress)
        elif self.dialect in ("sqlite", "sqlite3"):
            return self._sqlite_full_backup(output_dir, backup_id, timestamp, compress)
        else:
            return BackupResult(False, backup_id, "", 0, 0, f"Unsupported dialect: {self.dialect}")

    def backup_table(
        self,
        table: str,
        output_dir: str = None,
        include_schema: bool = True
    ) -> BackupResult:
        """
        单表备份
        """
        output_dir = output_dir or self.default_output_dir
        os.makedirs(output_dir, exist_ok=True)

        backup_id = f"table_{table}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

        if self.dialect in ("mysql", "mysql+pymysql"):
            return self._mysql_table_backup(table, output_dir, backup_id, timestamp, include_schema)
        elif self.dialect == "postgresql":
            return self._postgresql_table_backup(table, output_dir, backup_id, timestamp)
        elif self.dialect in ("sqlite", "sqlite3"):
            return self._sqlite_table_backup(table, output_dir, backup_id, timestamp)
        else:
            return BackupResult(False, backup_id, "", 0, 0, f"Unsupported dialect: {self.dialect}")

    def backup_tables(
        self,
        tables: List[str],
        output_dir: str = None,
        include_schema: bool = True
    ) -> List[BackupResult]:
        """
        多表备份
        """
        results = []
        for table in tables:
            result = self.backup_table(table, output_dir, include_schema)
            results.append(result)
        return results

    def list_backups(self, output_dir: str = None) -> List[BackupInfo]:
        """
        列出备份文件
        """
        output_dir = output_dir or self.default_output_dir

        if not os.path.exists(output_dir):
            return []

        backups = []
        for filename in os.listdir(output_dir):
            filepath = os.path.join(output_dir, filename)
            if os.path.isfile(filepath):
                stat = os.stat(filepath)
                backups.append(BackupInfo(
                    backup_id=filename,
                    backup_type="unknown",
                    file_path=filepath,
                    file_size=stat.st_size,
                    created_at=datetime.fromtimestamp(stat.st_mtime),
                    tables=[],
                    checksum=None,
                    status="archived"
                ))

        return sorted(backups, key=lambda x: x.created_at, reverse=True)

    def restore_backup(
        self,
        backup_file: str,
        target_database: str = None
    ) -> BackupResult:
        """
        恢复备份
        """
        if not os.path.exists(backup_file):
            return BackupResult(False, "", "", 0, 0, "Backup file not found")

        start_time = datetime.now()
        backup_id = os.path.basename(backup_file)

        if self.dialect in ("mysql", "mysql+pymysql"):
            return self._mysql_restore(backup_file, target_database, backup_id, start_time)
        elif self.dialect == "postgresql":
            return self._postgresql_restore(backup_file, target_database, backup_id, start_time)
        elif self.dialect in ("sqlite", "sqlite3"):
            return self._sqlite_restore(backup_file, backup_id, start_time)
        else:
            return BackupResult(False, backup_id, "", 0, 0, f"Unsupported dialect: {self.dialect}")

    def delete_backup(self, backup_file: str) -> bool:
        """删除备份"""
        try:
            if os.path.exists(backup_file):
                os.remove(backup_file)
                return True
        except Exception:
            pass
        return False

    def _mysql_full_backup(
        self,
        output_dir: str,
        backup_id: str,
        timestamp: str,
        compress: bool,
        include_schema: bool
    ) -> BackupResult:
        """MySQL 全量备份"""
        start_time = datetime.now()

        try:
            tables = self.connector.get_tables()
            output_file = os.path.join(output_dir, f"{backup_id}.sql")

            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(f"-- MySQL Backup: {backup_id}\n")
                f.write(f"-- Generated: {timestamp}\n\n")

                if include_schema:
                    for table in tables:
                        try:
                            safe_table = self._safe_table_name(table)
                            result = self.connector.execute(f"SHOW CREATE TABLE `{safe_table}`")
                            if result.rows:
                                f.write(f"\n-- Table: {safe_table}\n")
                                f.write(f"DROP TABLE IF EXISTS `{safe_table}`;\n")
                                f.write(result.rows[0][1] + ";\n\n")
                        except Exception:
                            pass

                for table in tables:
                    try:
                        safe_table = self._safe_table_name(table)
                        result = self.connector.execute(f"SELECT * FROM `{safe_table}`")
                        f.write(f"\n-- Data: {safe_table} ({len(result.rows)} rows)\n")
                        for row in result.rows:
                            values = []
                            for val in row:
                                if val is None:
                                    values.append("NULL")
                                elif isinstance(val, str):
                                    values.append(f"'{val.replace('\'', '\'\'')}'")
                                else:
                                    values.append(str(val))
                            f.write(f"INSERT INTO `{safe_table}` VALUES ({', '.join(values)});\n")
                    except Exception:
                        pass

            file_size = os.path.getsize(output_file)
            end_time = datetime.now()

            if compress:
                compressed_file = output_file + ".gz"
                import gzip
                with open(output_file, 'rb') as f_in:
                    with gzip.open(compressed_file, 'wb') as f_out:
                        shutil.copyfileobj(f_in, f_out)
                os.remove(output_file)
                output_file = compressed_file
                file_size = os.path.getsize(output_file)

            return BackupResult(True, backup_id, output_file, file_size, int((end_time - start_time).total_seconds() * 1000))

        except Exception as e:
            return BackupResult(False, backup_id, "", 0, 0, str(e))

    def _postgresql_full_backup(
        self,
        output_dir: str,
        backup_id: str,
        timestamp: str,
        compress: bool
    ) -> BackupResult:
        """PostgreSQL 全量备份"""
        start_time = datetime.now()

        try:
            tables = self.connector.get_tables()
            output_file = os.path.join(output_dir, f"{backup_id}.sql")

            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(f"-- PostgreSQL Backup: {backup_id}\n")
                f.write(f"-- Generated: {timestamp}\n\n")

                for table in tables:
                    try:
                        safe_table = self._safe_table_name(table)
                        result = self.connector.execute(f"SELECT * FROM {safe_table}")
                        f.write(f"\n-- Data: {safe_table}\n")
                        for row in result.rows:
                            values = []
                            for val in row:
                                if val is None:
                                    values.append("NULL")
                                elif isinstance(val, str):
                                    values.append(f"'{val.replace('\'', '\'\'')}'")
                                else:
                                    values.append(str(val))
                            f.write(f"INSERT INTO {safe_table} VALUES ({', '.join(values)});\n")
                    except Exception:
                        pass

            file_size = os.path.getsize(output_file)
            end_time = datetime.now()

            return BackupResult(True, backup_id, output_file, file_size, int((end_time - start_time).total_seconds() * 1000))

        except Exception as e:
            return BackupResult(False, backup_id, "", 0, 0, str(e))

    def _sqlite_full_backup(
        self,
        output_dir: str,
        backup_id: str,
        timestamp: str,
        compress: bool
    ) -> BackupResult:
        """SQLite 全量备份"""
        start_time = datetime.now()

        try:
            db_path = self.connector.connection.engine.url.database
            output_file = os.path.join(output_dir, f"{backup_id}.db")

            shutil.copy2(db_path, output_file)

            file_size = os.path.getsize(output_file)
            end_time = datetime.now()

            if compress:
                compressed_file = output_file + ".gz"
                import gzip
                with open(output_file, 'rb') as f_in:
                    with gzip.open(compressed_file, 'wb') as f_out:
                        shutil.copyfileobj(f_in, f_out)
                os.remove(output_file)
                output_file = compressed_file
                file_size = os.path.getsize(output_file)

            return BackupResult(True, backup_id, output_file, file_size, int((end_time - start_time).total_seconds() * 1000))

        except Exception as e:
            return BackupResult(False, backup_id, "", 0, 0, str(e))

    def _mysql_table_backup(
        self,
        table: str,
        output_dir: str,
        backup_id: str,
        timestamp: str,
        include_schema: bool
    ) -> BackupResult:
        """MySQL 单表备份"""
        start_time = datetime.now()

        try:
            safe_table = self._safe_table_name(table)
            output_file = os.path.join(output_dir, f"{backup_id}.sql")

            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(f"-- MySQL Table Backup: {safe_table}\n")
                f.write(f"-- Generated: {timestamp}\n\n")

                if include_schema:
                    result = self.connector.execute(f"SHOW CREATE TABLE `{safe_table}`")
                    if result.rows:
                        f.write(f"DROP TABLE IF EXISTS `{safe_table}`;\n")
                        f.write(result.rows[0][1] + ";\n\n")

                result = self.connector.execute(f"SELECT * FROM `{safe_table}`")
                f.write(f"-- Data: {safe_table} ({len(result.rows)} rows)\n")
                for row in result.rows:
                    values = []
                    for val in row:
                        if val is None:
                            values.append("NULL")
                        elif isinstance(val, str):
                            values.append(f"'{val.replace('\'', '\'\'')}'")
                        else:
                            values.append(str(val))
                    f.write(f"INSERT INTO `{safe_table}` VALUES ({', '.join(values)});\n")

            file_size = os.path.getsize(output_file)
            end_time = datetime.now()

            return BackupResult(True, backup_id, output_file, file_size, int((end_time - start_time).total_seconds() * 1000))

        except Exception as e:
            return BackupResult(False, backup_id, "", 0, 0, str(e))

    def _postgresql_table_backup(
        self,
        table: str,
        output_dir: str,
        backup_id: str,
        timestamp: str
    ) -> BackupResult:
        """PostgreSQL 单表备份"""
        start_time = datetime.now()

        try:
            safe_table = self._safe_table_name(table)
            output_file = os.path.join(output_dir, f"{backup_id}.sql")

            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(f"-- PostgreSQL Table Backup: {safe_table}\n")
                f.write(f"-- Generated: {timestamp}\n\n")

                result = self.connector.execute(f"SELECT * FROM {safe_table}")
                for row in result.rows:
                    values = []
                    for val in row:
                        if val is None:
                            values.append("NULL")
                        elif isinstance(val, str):
                            values.append(f"'{val.replace('\'', '\'\'')}'")
                        else:
                            values.append(str(val))
                    f.write(f"INSERT INTO {safe_table} VALUES ({', '.join(values)});\n")

            file_size = os.path.getsize(output_file)
            end_time = datetime.now()

            return BackupResult(True, backup_id, output_file, file_size, int((end_time - start_time).total_seconds() * 1000))

        except Exception as e:
            return BackupResult(False, backup_id, "", 0, 0, str(e))

    def _sqlite_table_backup(
        self,
        table: str,
        output_dir: str,
        backup_id: str,
        timestamp: str
    ) -> BackupResult:
        """SQLite 单表备份"""
        start_time = datetime.now()

        try:
            safe_table = self._safe_table_name(table)
            output_file = os.path.join(output_dir, f"{backup_id}.sql")

            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(f"-- SQLite Table Backup: {safe_table}\n")
                f.write(f"-- Generated: {timestamp}\n\n")

                result = self.connector.execute(f"SELECT * FROM `{safe_table}`")
                for row in result.rows:
                    values = []
                    for val in row:
                        if val is None:
                            values.append("NULL")
                        elif isinstance(val, str):
                            values.append(f"'{val.replace('\'', '\'\'')}'")
                        else:
                            values.append(str(val))
                    f.write(f"INSERT INTO `{safe_table}` VALUES ({', '.join(values)});\n")

            file_size = os.path.getsize(output_file)
            end_time = datetime.now()

            return BackupResult(True, backup_id, output_file, file_size, int((end_time - start_time).total_seconds() * 1000))

        except Exception as e:
            return BackupResult(False, backup_id, "", 0, 0, str(e))

    def _mysql_restore(
        self,
        backup_file: str,
        target_db: str,
        backup_id: str,
        start_time: datetime
    ) -> BackupResult:
        """MySQL 恢复"""
        try:
            if backup_file.endswith('.gz'):
                import gzip
                temp_file = backup_file[:-3]
                with gzip.open(backup_file, 'rb') as f_in:
                    with open(temp_file, 'wb') as f_out:
                        shutil.copyfileobj(f_in, f_out)
                backup_file = temp_file

            with open(backup_file, 'r', encoding='utf-8') as f:
                sql_content = f.read()

            statements = [s.strip() for s in sql_content.split(';') if s.strip()]

            for stmt in statements:
                if stmt and not stmt.startswith('--'):
                    try:
                        self.connector.execute(stmt)
                    except Exception:
                        pass

            end_time = datetime.now()
            return BackupResult(True, backup_id, backup_file, os.path.getsize(backup_file), int((end_time - start_time).total_seconds() * 1000))

        except Exception as e:
            return BackupResult(False, backup_id, backup_file, 0, 0, str(e))

    def _postgresql_restore(
        self,
        backup_file: str,
        target_db: str,
        backup_id: str,
        start_time: datetime
    ) -> BackupResult:
        """PostgreSQL 恢复"""
        try:
            with open(backup_file, 'r', encoding='utf-8') as f:
                sql_content = f.read()

            statements = [s.strip() for s in sql_content.split(';') if s.strip()]

            for stmt in statements:
                if stmt and not stmt.startswith('--'):
                    try:
                        self.connector.execute(stmt)
                    except Exception:
                        pass

            end_time = datetime.now()
            return BackupResult(True, backup_id, backup_file, os.path.getsize(backup_file), int((end_time - start_time).total_seconds() * 1000))

        except Exception as e:
            return BackupResult(False, backup_id, backup_file, 0, 0, str(e))

    def _sqlite_restore(
        self,
        backup_file: str,
        backup_id: str,
        start_time: datetime
    ) -> BackupResult:
        """SQLite 恢复"""
        try:
            if backup_file.endswith('.db'):
                db_path = self.connector.connection.engine.url.database
                shutil.copy2(backup_file, db_path)
            else:
                with open(backup_file, 'r', encoding='utf-8') as f:
                    sql_content = f.read()

                statements = [s.strip() for s in sql_content.split(';') if s.strip()]

                for stmt in statements:
                    if stmt and not stmt.startswith('--'):
                        try:
                            self.connector.execute(stmt)
                        except Exception:
                            pass

            end_time = datetime.now()
            return BackupResult(True, backup_id, backup_file, os.path.getsize(backup_file), int((end_time - start_time).total_seconds() * 1000))

        except Exception as e:
            return BackupResult(False, backup_id, backup_file, 0, 0, str(e))
