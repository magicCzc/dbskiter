"""
sqlite backup mixin for BackupManager

Auto-extracted from manager.py.
"""

import logging
import os
import shutil
logger = logging.getLogger(__name__)
from datetime import date, datetime
from typing import List, Dict, Any, Optional

from dbskiter.db_scheduler.backup.models import BackupInfo, BackupResult


class SQLiteBackupMixin:
    """sqlite backup methods for BackupManager"""

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

    @staticmethod
    def _escape_sqlite_value(
        value: Any,
    ) -> str:
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


