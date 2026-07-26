"""
generic backup mixin for BackupManager

Auto-extracted from manager.py.
"""

import logging
logger = logging.getLogger(__name__)
from datetime import datetime
from typing import List, Dict, Any, Optional

from dbskiter.db_scheduler.backup.models import BackupInfo, BackupResult


class GenericBackupMixin:
    """generic backup methods for BackupManager"""

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


    def _detect_backup_type(filename: str) -> str:
        """从文件名推断备份类型"""
        name = filename.lower()
        if "_table_" in name:
            return "table"
        if "_incremental_" in name:
            return "incremental"
        return "full"


