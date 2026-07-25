"""
mssql backup mixin for BackupManager

Auto-extracted from manager.py.
"""

import logging
from datetime import datetime
from typing import List, Dict, Any, Optional

from dbskiter.db_scheduler.backup.models import BackupInfo, BackupResult


class MSSQLBackupMixin:
    """mssql backup methods for BackupManager"""

    def _mssql_full_backup(
        self,
        output_dir: str,
        backup_id: str,
        timestamp: str,
        compress: bool,
        include_schema: bool,
    ) -> BackupResult:
        """SQL Server 全量备份"""
        output_file = os.path.join(output_dir, f"{backup_id}.sql")

        if self._has_native_tool("sqlcmd"):
            return self._mssql_native_dump(
                output_file, backup_id, include_schema, compress
            )

        logger.warning(
            "sqlcmd 不可用, 使用分页降级方案。"
            "大数据量备份建议安装 SQL Server Command Line Tools。"
        )
        return self._mssql_fallback_dump(
            output_file, backup_id, include_schema, compress
        )


    def _mssql_table_backup(
        self,
        table: str,
        output_dir: str,
        backup_id: str,
        timestamp: str,
        include_schema: bool,
    ) -> BackupResult:
        """SQL Server 单表备份"""
        output_file = os.path.join(output_dir, f"{backup_id}.sql")

        if self._has_native_tool("bcp"):
            return self._mssql_native_dump(
                output_file, backup_id, include_schema, False, tables=[table]
            )

        return self._mssql_fallback_dump(
            output_file, backup_id, include_schema, False, tables=[table]
        )


    def _mssql_native_dump(
        self,
        output_file: str,
        backup_id: str,
        include_schema: bool,
        compress: bool,
        tables: Optional[List[str]] = None,
    ) -> BackupResult:
        """使用 sqlcmd/bcp 工具执行 SQL Server 备份"""
        start_time = datetime.now()
        host = self.connector.host
        port = self.connector.port or 1433
        user = self.connector.username
        password = self.connector.password
        database = self.connector.database

        try:
            if tables:
                # 使用 bcp 导出单表
                for table in tables:
                    safe_table = self._quote_mssql_table(table)
                    bcp_cmd = [
                        "bcp",
                        f"SELECT * FROM {safe_table}",
                        database,
                        "-S", f"{host},{port}",
                        "-U", user,
                        "-P", password,
                        "-c",  # 字符模式
                        "-t,",  # 逗号分隔
                        "-o", output_file,
                    ]
                    result = subprocess.run(
                        bcp_cmd, capture_output=True, text=True, timeout=self.backup_timeout
                    )
                    if result.returncode != 0:
                        return self._error(
                            backup_id,
                            f"bcp 备份失败: {result.stderr or result.stdout}"
                        )
            else:
                # 使用 sqlcmd 导出整个数据库
                sqlcmd_cmd = [
                    "sqlcmd",
                    "-S", f"{host},{port}",
                    "-U", user,
                    "-P", password,
                    "-d", database,
                    "-Q", (
                        "SELECT 'CREATE TABLE [' + TABLE_NAME + '] (' + "
                        "STUFF((SELECT ', [' + COLUMN_NAME + '] ' + DATA_TYPE "
                        "FOR XML PATH('')), 1, 2, '') + ');' "
                        "FROM INFORMATION_SCHEMA.TABLES "
                        "WHERE TABLE_TYPE = 'BASE TABLE'"
                    ),
                    "-o", output_file,
                    "-h-1",  # 无标题
                ]
                result = subprocess.run(
                    sqlcmd_cmd, capture_output=True, text=True, timeout=self.backup_timeout
                )
                if result.returncode != 0:
                    return self._error(
                        backup_id,
                        f"sqlcmd 备份失败: {result.stderr or result.stdout}"
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
            return self._error(backup_id, "SQL Server 备份工具超时")
        except FileNotFoundError:
            return self._error(
                backup_id,
                "SQL Server 命令行工具未找到。请安装 sqlcmd / bcp。"
            )


    def _mssql_fallback_dump(
        self,
        output_file: str,
        backup_id: str,
        include_schema: bool,
        compress: bool,
        tables: Optional[List[str]] = None,
    ) -> BackupResult:
        """SQL Server 分页降级备份"""
        start_time = datetime.now()

        if not tables:
            try:
                result = self.connector.execute(
                    "SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES "
                    "WHERE TABLE_TYPE = 'BASE TABLE' ORDER BY TABLE_NAME"
                )
                if result and result.rows:
                    tables = [
                        row[0] if not isinstance(row, dict) else row.get("TABLE_NAME", "")
                        for row in result.rows
                    ]
            except Exception:
                tables = []

        if not tables:
            return self._error(backup_id, "SQL Server 未找到可备份的表")

        try:
            with open(output_file, "w", encoding="utf-8") as f:
                if include_schema:
                    f.write("-- SQL Server Backup Generated by dbskiter\n")
                    f.write(f"-- Date: {datetime.now().isoformat()}\n\n")

                for table in tables:
                    if include_schema:
                        f.write(self._get_mssql_table_schema(table) + "\n\n")
                    rows_written = self._write_mssql_table_data(f, table)
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
            return self._error(backup_id, f"SQL Server 备份异常: {exc}")


    def _write_mssql_table_data(
        self, file_handle, table: str
    ) -> int:
        """使用分页查询写入 SQL Server 表数据"""
        safe_table = self._quote_mssql_table(table)
        offset = 0
        batch_size = 1000
        total_rows = 0

        while True:
            query = (
                f"SELECT * FROM {safe_table} "
                f"ORDER BY (SELECT NULL) OFFSET {offset} ROWS FETCH NEXT {batch_size} ROWS ONLY"
            )
            result = self.connector.execute(query)
            if not result or not result.rows:
                break

            for row in result.rows:
                values = [self._escape_mssql_value(v) for v in row]
                file_handle.write(
                    f"INSERT INTO {safe_table} VALUES ({', '.join(values)});\n"
                )
                total_rows += 1

            offset += batch_size

        return total_rows


    def _mssql_restore(
        self,
        backup_file: str,
        backup_id: str,
        start_time: datetime,
    ) -> BackupResult:
        """SQL Server 恢复"""
        try:
            if backup_file.endswith(".gz"):
                uncompressed = backup_file[:-3]
                self._gunzip_file(backup_file, uncompressed)
                backup_file = uncompressed

            host = self.connector.host
            port = self.connector.port or 1433
            user = self.connector.username
            password = self.connector.password
            database = self.connector.database

            cmd = [
                "sqlcmd",
                "-S", f"{host},{port}",
                "-U", user,
                "-P", password,
                "-d", database,
                "-i", backup_file,
            ]
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=self.backup_timeout
            )
            if result.returncode != 0:
                return self._error(
                    backup_id,
                    f"sqlcmd 恢复失败: {result.stderr or result.stdout}"
                )

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

        except FileNotFoundError:
            return self._error(
                backup_id, "sqlcmd 工具未找到。请安装 SQL Server Command Line Tools。"
            )
        except Exception as exc:
            return self._error(backup_id, f"SQL Server 恢复失败: {exc}")


    def _get_mssql_table_schema(self, table: str) -> str:
        """获取 SQL Server 表 DDL"""
        try:
            safe_table = self._safe_table_name(table)
            result = self.connector.execute(
                f"SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE "
                f"FROM INFORMATION_SCHEMA.COLUMNS "
                f"WHERE TABLE_NAME = '{safe_table}' "
                f"ORDER BY ORDINAL_POSITION"
            )
            if result and result.rows:
                cols = []
                for row in result.rows:
                    if isinstance(row, dict):
                        col_name = row.get("COLUMN_NAME", "")
                        data_type = row.get("DATA_TYPE", "")
                        nullable = "NULL" if row.get("IS_NULLABLE") == "YES" else "NOT NULL"
                    else:
                        col_name, data_type, nullable = row[0], row[1], (
                            "NULL" if row[2] == "YES" else "NOT NULL"
                        )
                    cols.append(f"[{col_name}] {data_type} {nullable}")
                cols_str = ", ".join(cols)
                return f"CREATE TABLE [{safe_table}] ({cols_str});"
        except Exception:
            pass
        return f"-- SQL Server DDL for {table}"


    def _quote_mssql_table(table: str) -> str:
        """SQL Server 表名加方括号"""
        return f"[{table}]"


    def _escape_mssql_value(value: Any) -> str:
        """SQL Server 值转义"""
        if value is None:
            return "NULL"
        if isinstance(value, bool):
            return "1" if value else "0"
        if isinstance(value, (int, float)):
            return str(value)
        if isinstance(value, (datetime, date)):
            return f"'{value}'"
        if isinstance(value, bytes):
            return "0x" + value.hex()
        # 字符串 - 替换单引号
        escaped = str(value).replace("'", "''")
        return f"'{escaped}'"


