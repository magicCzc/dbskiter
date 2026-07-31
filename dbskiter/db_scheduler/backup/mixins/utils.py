"""
utils backup mixin for BackupManager

Auto-extracted from manager.py.
"""

import logging
import hashlib
import os
import re
import shutil
logger = logging.getLogger(__name__)
from datetime import date, datetime
from typing import List, Dict, Any, Optional

from dbskiter.db_scheduler.backup.models import BackupInfo, BackupResult


class BackupUtilsMixin:
    """utils backup methods for BackupManager"""

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
    def _safe_qualified_table_name(
        table: str,
    ) -> str:
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
    def _safe_filename(
        name: str,
    ) -> str:
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
    def _has_native_tool(
        tool_name: str,
    ) -> bool:
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
    def _compute_sha256(
        file_path: str,
    ) -> str:
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
    def _read_checksum(
        file_path: str,
    ) -> Optional[str]:
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
    def _human_size(
        size_bytes: int,
    ) -> str:
        """字节大小转人类可读格式"""
        for unit in ("B", "KB", "MB", "GB", "TB"):
            if size_bytes < 1024:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.1f} PB"


    @staticmethod
    def _split_sql_statements(
        sql_content: str,
    ) -> List[str]:
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


