"""
postgresql backup mixin for BackupManager

Auto-extracted from manager.py.
"""

import logging
logger = logging.getLogger(__name__)
from datetime import datetime
from typing import List, Dict, Any, Optional

from dbskiter.db_scheduler.backup.models import BackupInfo, BackupResult


class PostgreSQLBackupMixin:
    """postgresql backup methods for BackupManager"""

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


