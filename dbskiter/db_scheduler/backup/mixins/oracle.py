"""
oracle backup mixin for BackupManager

Auto-extracted from manager.py.
"""

import logging
from datetime import datetime
from typing import List, Dict, Any, Optional

from dbskiter.db_scheduler.backup.models import BackupInfo, BackupResult


class OracleBackupMixin:
    """oracle backup methods for BackupManager"""

    def _oracle_full_backup(
        self,
        output_dir: str,
        backup_id: str,
        timestamp: str,
        compress: bool,
        include_schema: bool,
    ) -> BackupResult:
        """Oracle 全量备份"""
        output_file = os.path.join(output_dir, f"{backup_id}.sql")

        if self._has_native_tool("exp"):
            return self._oracle_native_dump(
                output_file, backup_id, include_schema, compress
            )

        logger.warning(
            "Oracle exp 不可用, 使用分页降级方案。"
            "大数据量备份建议安装 Oracle Client。"
        )
        return self._oracle_fallback_dump(
            output_file, backup_id, include_schema, compress
        )


    def _oracle_table_backup(
        self,
        table: str,
        output_dir: str,
        backup_id: str,
        timestamp: str,
        include_schema: bool,
    ) -> BackupResult:
        """Oracle 单表备份"""
        output_file = os.path.join(output_dir, f"{backup_id}.sql")

        if self._has_native_tool("exp"):
            return self._oracle_native_dump(
                output_file, backup_id, include_schema, False, tables=[table]
            )

        logger.warning(
            "Oracle exp 不可用, 使用分页降级方案。"
            "大数据量备份建议安装 Oracle Client。"
        )
        return self._oracle_fallback_dump(
            output_file, backup_id, include_schema, False, tables=[table]
        )


    def _oracle_restore(
        self,
        backup_file: str,
        backup_id: str,
        start_time: datetime,
    ) -> BackupResult:
        """Oracle 恢复"""
        try:
            # 解压
            if backup_file.endswith(".gz"):
                uncompressed = backup_file[:-3]
                self._gunzip_file(backup_file, uncompressed)
                backup_file = uncompressed

            host = self.connector.host
            port = self.connector.port or 1521
            user = self.connector.username
            password = self.connector.password
            service = getattr(self.connector, "service", None) or self.connector.database
            tns = f"//{host}:{port}/{service}"

            # 使用 imp 工具
            cmd = [
                "imp",
                f"{user}/{password}@{tns}",
                "FILE=" + backup_file,
                "FULL=Y",
                "IGNORE=Y",
            ]
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.backup_timeout,
            )

            if result.returncode != 0:
                return self._error(
                    backup_id,
                    f"Oracle imp 恢复失败: {result.stderr or result.stdout}"
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
                backup_id, "Oracle imp 工具未找到。请安装 Oracle Client。"
            )
        except Exception as exc:
            return self._error(backup_id, f"Oracle 恢复失败: {exc}")


    def _get_oracle_tables(self) -> List[str]:
        """获取 Oracle 数据库所有表名"""
        try:
            result = self.connector.execute(
                "SELECT table_name FROM user_tables ORDER BY table_name"
            )
            if result and result.rows:
                return [row[0] if not isinstance(row, dict) else row.get("table_name", "")
                        for row in result.rows]
        except Exception:
            pass
        return []


    def _get_oracle_table_schema(self, table: str) -> str:
        """获取 Oracle 表 DDL"""
        try:
            safe_table = self._safe_table_name(table)
            result = self.connector.execute(
                f"SELECT DBMS_METADATA.GET_DDL('TABLE', '{safe_table}') FROM DUAL"
            )
            if result and result.rows:
                row = result.rows[0]
                ddl = row[0] if not isinstance(row, dict) else row.get(
                    "DBMS_METADATA.GET_DDL('TABLE', '" + safe_table + "')", ""
                )
                return ddl or f"-- Oracle DDL for {table} unavailable"
        except Exception:
            pass
        return f"-- Oracle DDL for {table}"


    def _quote_oracle_table(table: str) -> str:
        """Oracle 表名加双引号"""
        return f'"{table}"'


    def _escape_oracle_value(value: Any) -> str:
        """Oracle 值转义"""
        if value is None:
            return "NULL"
        if isinstance(value, bool):
            return "1" if value else "0"
        if isinstance(value, (int, float)):
            return str(value)
        if isinstance(value, (datetime, date)):
            return f"TO_DATE('{value}', 'YYYY-MM-DD HH24:MI:SS')"
        if isinstance(value, bytes):
            return "EMPTY_BLOB()"
        # 字符串 - 替换单引号
        escaped = str(value).replace("'", "''")
        return f"'{escaped}'"

    # ============================================================
    # SQL Server 备份方法
    # ============================================================


