"""
clickhouse backup mixin for BackupManager

Auto-extracted from manager.py.
"""

import logging
import os
logger = logging.getLogger(__name__)
from datetime import date, datetime
from typing import List, Dict, Any, Optional

from dbskiter.db_scheduler.backup.models import BackupInfo, BackupResult


class ClickHouseBackupMixin:
    """clickhouse backup methods for BackupManager"""

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

    # ============================================================
    # Oracle 备份方法
    # ============================================================


    @staticmethod
    def _escape_clickhouse_value(
        value: Any,
    ) -> str:
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


