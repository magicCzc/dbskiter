"""
mysql backup mixin for BackupManager

Auto-extracted from manager.py.
"""

import logging
from datetime import datetime
from typing import List, Dict, Any, Optional

from dbskiter.db_scheduler.backup.models import BackupInfo, BackupResult


class MySQLBackupMixin:
    """mysql backup methods for BackupManager"""

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


