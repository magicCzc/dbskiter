"""
tests/test_scheduler_backup.py
db_scheduler/backup.py 测试套件

测试策略:
    - 单元测试: 不依赖外部数据库, 测试工具方法
    - 集成测试: 使用 SQLite 内存数据库测试完整备份恢复流程

运行方式:
    pytest tests/test_scheduler_backup.py -v
"""

import hashlib
import os
import tempfile
from datetime import date, datetime

import pytest

from dbskiter.db_scheduler.backup import BackupInfo, BackupManager, BackupResult
from dbskiter.shared.unified_connector import UnifiedConnector


# =============================================================================
# 单元测试 - 工具方法
# =============================================================================


class TestSafeTableName:
    """表名安全验证测试"""

    def test_valid_table_name(self):
        assert BackupManager._safe_table_name("users") == "users"
        assert BackupManager._safe_table_name("_users") == "_users"
        assert BackupManager._safe_table_name("users_123") == "users_123"

    def test_invalid_table_name_injection(self):
        with pytest.raises(ValueError, match="非法表名"):
            BackupManager._safe_table_name("users; DROP TABLE users")

    def test_invalid_table_name_comment(self):
        with pytest.raises(ValueError, match="非法表名"):
            BackupManager._safe_table_name("users--")

    def test_invalid_table_name_special_chars(self):
        with pytest.raises(ValueError, match="非法表名"):
            BackupManager._safe_table_name("users@!")


class TestEscapeMysqlValue:
    """MySQL值转义测试"""

    def test_null(self):
        assert BackupManager._escape_mysql_value(None) == "NULL"

    def test_bool(self):
        assert BackupManager._escape_mysql_value(True) == "1"
        assert BackupManager._escape_mysql_value(False) == "0"

    def test_int(self):
        assert BackupManager._escape_mysql_value(42) == "42"
        assert BackupManager._escape_mysql_value(-100) == "-100"

    def test_float(self):
        assert BackupManager._escape_mysql_value(3.14) == "3.14"

    def test_string_simple(self):
        assert BackupManager._escape_mysql_value("hello") == "'hello'"

    def test_string_with_quote(self):
        result = BackupManager._escape_mysql_value("O'Reilly")
        assert result == "'O\\'Reilly'"

    def test_string_with_backslash(self):
        result = BackupManager._escape_mysql_value("C:\\Users")
        assert "\\\\" in result

    def test_bytes(self):
        result = BackupManager._escape_mysql_value(b"\x00\xff")
        assert result == "0x00ff"

    def test_datetime(self):
        dt = datetime(2024, 1, 15, 10, 30, 0)
        result = BackupManager._escape_mysql_value(dt)
        assert "2024-01-15T10:30:00" in result


class TestEscapePgValue:
    """PostgreSQL值转义测试"""

    def test_null(self):
        assert BackupManager._escape_pg_value(None) == "NULL"

    def test_bool(self):
        assert BackupManager._escape_pg_value(True) == "TRUE"
        assert BackupManager._escape_pg_value(False) == "FALSE"

    def test_string_with_quote(self):
        result = BackupManager._escape_pg_value("it's")
        assert result == "'it''s'"


class TestEscapeSqliteValue:
    """SQLite值转义测试"""

    def test_null(self):
        assert BackupManager._escape_sqlite_value(None) == "NULL"

    def test_bool(self):
        assert BackupManager._escape_sqlite_value(True) == "1"
        assert BackupManager._escape_sqlite_value(False) == "0"

    def test_string_with_quote(self):
        result = BackupManager._escape_sqlite_value("it's")
        assert result == "'it''s'"

    def test_bytes(self):
        result = BackupManager._escape_sqlite_value(b"\x01\x02")
        assert result == "'X'0102''" or "X'0102'" in result


class TestChecksum:
    """校验和计算测试"""

    def test_compute_sha256_empty(self):
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
            f.write("")
            path = f.name
        try:
            result = BackupManager._compute_sha256(path)
            expected = hashlib.sha256(b"").hexdigest()
            assert result == expected
        finally:
            os.remove(path)

    def test_compute_sha256_known_content(self):
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
            f.write("hello world")
            path = f.name
        try:
            result = BackupManager._compute_sha256(path)
            expected = hashlib.sha256(b"hello world").hexdigest()
            assert result == expected
        finally:
            os.remove(path)

    def test_write_and_read_checksum(self):
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
            f.write("test content")
            path = f.name

        try:
            # 模拟写入校验
            manager = BackupManager.__new__(BackupManager)
            manager._write_checksum(path)

            checksum_path = path + ".sha256"
            assert os.path.exists(checksum_path)

            read = BackupManager._read_checksum(path)
            expected = hashlib.sha256(b"test content").hexdigest()
            assert read == expected

            os.remove(checksum_path)
        finally:
            os.remove(path)


class TestSqlStatementSplit:
    """SQL语句拆分测试"""

    def test_simple_statements(self):
        sql = "SELECT 1; SELECT 2; SELECT 3;"
        result = BackupManager._split_sql_statements(sql)
        assert len(result) == 3
        assert result[0] == "SELECT 1"
        assert result[1] == "SELECT 2"

    def test_semicolon_in_string(self):
        sql = "INSERT INTO t VALUES ('a;b'); SELECT 1;"
        result = BackupManager._split_sql_statements(sql)
        assert len(result) == 2
        assert "'a;b'" in result[0]
        assert result[1] == "SELECT 1"

    def test_comment_preserved(self):
        sql = "-- header\nSELECT 1;"
        result = BackupManager._split_sql_statements(sql)
        assert len(result) == 1
        assert "-- header" in result[0]

    def test_no_trailing_semicolon(self):
        sql = "SELECT 1"
        result = BackupManager._split_sql_statements(sql)
        assert len(result) == 1
        assert result[0] == "SELECT 1"


class TestBackupTypeDetection:
    """备份类型推断测试"""

    def test_full_backup(self):
        assert BackupManager._detect_backup_type("db_full_20240101_120000.sql") == "full"

    def test_table_backup(self):
        assert BackupManager._detect_backup_type("db_table_users_20240101_120000.sql") == "table"

    def test_incremental_backup(self):
        assert BackupManager._detect_backup_type("db_incremental_20240101_120000.sql") == "incremental"


class TestHumanSize:
    """人类可读大小测试"""

    def test_bytes(self):
        assert BackupManager._human_size(512) == "512.0 B"

    def test_kilobytes(self):
        result = BackupManager._human_size(1536)
        assert "KB" in result

    def test_megabytes(self):
        result = BackupManager._human_size(5 * 1024 * 1024)
        assert "MB" in result


class TestNativeToolDetection:
    """原生工具检测测试"""

    def test_detect_existing_tool(self):
        # python 一定存在
        assert BackupManager._has_native_tool("python") is True

    def test_detect_nonexistent_tool(self):
        # 假设这个工具不存在
        assert BackupManager._has_native_tool("nonexistent_tool_xyz") is False


# =============================================================================
# 集成测试 - SQLite 备份恢复
# =============================================================================


@pytest.fixture
def sqlite_connector():
    """创建SQLite内存数据库连接器"""
    conn = UnifiedConnector(
        dialect="sqlite",
        host="localhost",
        database=":memory:",
    )
    # 创建测试表和数据
    conn.execute("""
        CREATE TABLE users (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT,
            created_at TEXT
        )
    """)
    conn.execute("INSERT INTO users (id, name, email, created_at) VALUES (1, 'Alice', 'alice@example.com', '2024-01-01')")
    conn.execute("INSERT INTO users (id, name, email, created_at) VALUES (2, 'Bob', 'bob@example.com', '2024-01-02')")
    conn.execute("INSERT INTO users (id, name, email, created_at) VALUES (3, 'Charlie', NULL, '2024-01-03')")
    yield conn
    conn.close()


@pytest.fixture
def backup_manager(sqlite_connector):
    """创建备份管理器"""
    return BackupManager(sqlite_connector)


class TestSqliteIntegration:
    """SQLite 备份恢复集成测试"""

    def test_full_backup(self, backup_manager):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = backup_manager.backup_full(output_dir=tmpdir, compress=False)
            assert result.success is True
            assert os.path.exists(result.file_path)
            assert result.file_size > 0
            assert result.backup_type == "full"

    def test_full_backup_with_checksum(self, backup_manager):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = backup_manager.backup_full(output_dir=tmpdir, compress=False)
            checksum_file = result.file_path + ".sha256"
            assert os.path.exists(checksum_file)

    def test_full_backup_verify(self, backup_manager):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = backup_manager.backup_full(output_dir=tmpdir, compress=False)
            verify = backup_manager.verify_backup(result.file_path)
            assert verify.success is True

    def test_table_backup(self, backup_manager):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = backup_manager.backup_table("users", output_dir=tmpdir)
            assert result.success is True
            assert result.backup_type == "table"
            assert "users" in result.backup_id

    def test_list_backups(self, backup_manager):
        with tempfile.TemporaryDirectory() as tmpdir:
            backup_manager.backup_full(output_dir=tmpdir, compress=False)
            backup_manager.backup_table("users", output_dir=tmpdir)

            backups = backup_manager.list_backups(tmpdir)
            assert len(backups) == 2
            # 按时间倒序
            assert backups[0].created_at >= backups[1].created_at

    def test_delete_backup(self, backup_manager):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = backup_manager.backup_full(output_dir=tmpdir, compress=False)
            checksum_file = result.file_path + ".sha256"

            assert os.path.exists(result.file_path)
            deleted = backup_manager.delete_backup(result.file_path)
            assert deleted is True
            assert not os.path.exists(result.file_path)
            assert not os.path.exists(checksum_file)

    def test_backup_result_to_dict(self, backup_manager):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = backup_manager.backup_full(output_dir=tmpdir, compress=False)
            d = result.to_dict()
            assert d["success"] is True
            assert "backup_id" in d
            assert "file_path" in d
            assert "file_size" in d


# =============================================================================
# Oracle / MSSQL 备份测试
# =============================================================================


class MockConnector:
    """用于 Oracle/MSSQL 备份测试的模拟连接器"""
    def __init__(self, dialect):
        self.dialect = dialect
        self.host = "localhost"
        self.port = 1521 if "oracle" in dialect else 1433
        self.user = "test"
        self.username = "test"
        self.password = "test"
        self.database = "test"
        self.service = "ORCL"
        self.execute_calls = []

    def execute(self, sql, params=None):
        self.execute_calls.append(sql)
        return None  # 模拟无返回


class TestOracleBackup:
    """Oracle 备份测试"""

    def test_oracle_dialect_detection(self):
        """测试 Oracle 方言识别"""
        connector = MockConnector("oracle+jdbc")
        manager = BackupManager(connector)
        assert "oracle" in manager.dialect

    def test_oracle_quote_table_name(self):
        """测试 Oracle 表名加双引号"""
        result = BackupManager._quote_oracle_table("users")
        assert result == '"users"'

    def test_oracle_escape_value_string(self):
        """测试 Oracle 字符串转义"""
        result = BackupManager._escape_oracle_value("hello'world")
        assert "''" in result

    def test_oracle_escape_value_none(self):
        """测试 Oracle NULL 转义"""
        assert BackupManager._escape_oracle_value(None) == "NULL"

    def test_oracle_escape_value_number(self):
        """测试 Oracle 数字转义"""
        assert BackupManager._escape_oracle_value(123) == "123"
        assert BackupManager._escape_oracle_value(1.5) == "1.5"

    def test_oracle_escape_value_bool(self):
        """测试 Oracle 布尔转义"""
        assert BackupManager._escape_oracle_value(True) == "1"
        assert BackupManager._escape_oracle_value(False) == "0"

    def test_oracle_escape_value_datetime(self):
        """测试 Oracle 日期转义"""
        dt = datetime(2026, 1, 15, 10, 30, 0)
        result = BackupManager._escape_oracle_value(dt)
        assert "TO_DATE" in result

    def test_oracle_full_backup_fallback(self):
        """测试 Oracle 全量备份（无 exp 工具时降级）"""
        connector = MockConnector("oracle+jdbc")
        manager = BackupManager(connector)
        # _has_native_tool 默认返回 False，所以会走 fallback
        with tempfile.TemporaryDirectory() as tmpdir:
            result = manager._oracle_full_backup(
                tmpdir, "test_full", "20260101_000000", False, True
            )
            # fallback 会尝试获取表列表，Mock 无数据则返回错误结果
            assert isinstance(result, BackupResult)
            # 文件可能不存在（因为表列表为空），但返回结构正确
            assert result.backup_id == "test_full"

    def test_oracle_table_backup_fallback(self):
        """测试 Oracle 单表备份降级"""
        connector = MockConnector("oracle+jdbc")
        manager = BackupManager(connector)
        with tempfile.TemporaryDirectory() as tmpdir:
            result = manager._oracle_table_backup(
                "users", tmpdir, "test_table", "20260101_000000", True
            )
            assert isinstance(result, BackupResult)
            assert result.backup_id == "test_table"

    def test_oracle_get_tables_empty(self):
        """测试 Oracle 获取表列表（空数据库）"""
        connector = MockConnector("oracle+jdbc")
        manager = BackupManager(connector)
        tables = manager._get_oracle_tables()
        assert tables == []

    def test_oracle_get_table_schema_fallback(self):
        """测试 Oracle 表 DDL 获取失败时降级"""
        connector = MockConnector("oracle+jdbc")
        manager = BackupManager(connector)
        schema = manager._get_oracle_table_schema("users")
        assert "users" in schema

    def test_oracle_restore_no_tool(self):
        """测试 Oracle 恢复无工具时失败"""
        connector = MockConnector("oracle+jdbc")
        manager = BackupManager(connector)
        with tempfile.TemporaryDirectory() as tmpdir:
            fake_file = os.path.join(tmpdir, "test.sql")
            with open(fake_file, "w") as f:
                f.write("-- empty")
            result = manager._oracle_restore(
                fake_file, "test_restore", datetime.now()
            )
            assert isinstance(result, BackupResult)
            # 没有 imp 工具会失败
            assert result.success is False or result.file_path == fake_file

    def test_oracle_native_dump_no_tool(self):
        """测试 Oracle 原生 dump 无工具时"""
        connector = MockConnector("oracle+jdbc")
        manager = BackupManager(connector)
        with tempfile.TemporaryDirectory() as tmpdir:
            output_file = os.path.join(tmpdir, "test.dmp")
            result = manager._oracle_native_dump(
                output_file, "test", True, False
            )
            # exp 不可用，FileNotFoundError
            assert result.success is False


class TestMSSQLBackup:
    """MSSQL 备份测试"""

    def test_mssql_dialect_detection(self):
        """测试 MSSQL 方言识别"""
        for dialect in ("mssql+pyodbc", "sqlserver", "mssql"):
            connector = MockConnector(dialect)
            manager = BackupManager(connector)
            assert "mssql" in manager.dialect or "sqlserver" in manager.dialect

    def test_mssql_quote_table_name(self):
        """测试 MSSQL 表名加方括号"""
        result = BackupManager._quote_mssql_table("users")
        assert result == "[users]"

    def test_mssql_escape_value_string(self):
        """测试 MSSQL 字符串转义"""
        result = BackupManager._escape_mssql_value("hello'world")
        assert "''" in result

    def test_mssql_escape_value_none(self):
        """测试 MSSQL NULL 转义"""
        assert BackupManager._escape_mssql_value(None) == "NULL"

    def test_mssql_escape_value_number(self):
        """测试 MSSQL 数字转义"""
        assert BackupManager._escape_mssql_value(42) == "42"

    def test_mssql_escape_value_bool(self):
        """测试 MSSQL 布尔转义"""
        assert BackupManager._escape_mssql_value(True) == "1"

    def test_mssql_escape_value_datetime(self):
        """测试 MSSQL 日期转义"""
        dt = datetime(2026, 1, 15, 10, 30, 0)
        result = BackupManager._escape_mssql_value(dt)
        assert "2026" in result

    def test_mssql_escape_value_bytes(self):
        """测试 MSSQL 字节转义"""
        result = BackupManager._escape_mssql_value(b"abc")
        assert result.startswith("0x")

    def test_mssql_get_table_schema_fallback(self):
        """测试 MSSQL 表 DDL 获取失败时降级"""
        connector = MockConnector("mssql+pyodbc")
        manager = BackupManager(connector)
        schema = manager._get_mssql_table_schema("users")
        assert "users" in schema

    def test_mssql_full_backup_fallback(self):
        """测试 MSSQL 全量备份降级"""
        connector = MockConnector("mssql+pyodbc")
        manager = BackupManager(connector)
        with tempfile.TemporaryDirectory() as tmpdir:
            result = manager._mssql_full_backup(
                tmpdir, "test_full", "20260101_000000", False, True
            )
            assert isinstance(result, BackupResult)

    def test_mssql_table_backup_fallback(self):
        """测试 MSSQL 单表备份降级"""
        connector = MockConnector("mssql+pyodbc")
        manager = BackupManager(connector)
        with tempfile.TemporaryDirectory() as tmpdir:
            result = manager._mssql_table_backup(
                "users", tmpdir, "test_table", "20260101_000000", True
            )
            assert isinstance(result, BackupResult)

    def test_mssql_restore_no_tool(self):
        """测试 MSSQL 恢复无工具时"""
        connector = MockConnector("mssql+pyodbc")
        manager = BackupManager(connector)
        with tempfile.TemporaryDirectory() as tmpdir:
            fake_file = os.path.join(tmpdir, "test.sql")
            with open(fake_file, "w") as f:
                f.write("-- empty")
            result = manager._mssql_restore(
                fake_file, "test_restore", datetime.now()
            )
            assert isinstance(result, BackupResult)

    def test_mssql_native_dump_no_tool(self):
        """测试 MSSQL 原生 dump 无工具时"""
        connector = MockConnector("mssql+pyodbc")
        manager = BackupManager(connector)
        with tempfile.TemporaryDirectory() as tmpdir:
            output_file = os.path.join(tmpdir, "test.bcp")
            result = manager._mssql_native_dump(
                output_file, "test", True, False
            )
            assert result.success is False


class TestBackupDispatch:
    """测试备份调度逻辑"""

    def test_oracle_dispatch_in_backup_full(self):
        """测试 backup_full 调度到 Oracle"""
        connector = MockConnector("oracle+jdbc")
        manager = BackupManager(connector)
        with tempfile.TemporaryDirectory() as tmpdir:
            result = manager.backup_full(output_dir=tmpdir, compress=False)
            assert isinstance(result, BackupResult)
            # 应该执行了 Oracle 备份路径

    def test_mssql_dispatch_in_backup_full(self):
        """测试 backup_full 调度到 MSSQL"""
        connector = MockConnector("mssql+pyodbc")
        manager = BackupManager(connector)
        with tempfile.TemporaryDirectory() as tmpdir:
            result = manager.backup_full(output_dir=tmpdir, compress=False)
            assert isinstance(result, BackupResult)

    def test_oracle_dispatch_in_backup_table(self):
        """测试 backup_table 调度到 Oracle"""
        connector = MockConnector("oracle+jdbc")
        manager = BackupManager(connector)
        with tempfile.TemporaryDirectory() as tmpdir:
            result = manager.backup_table("users", output_dir=tmpdir)
            assert isinstance(result, BackupResult)

    def test_mssql_dispatch_in_backup_table(self):
        """测试 backup_table 调度到 MSSQL"""
        connector = MockConnector("mssql+pyodbc")
        manager = BackupManager(connector)
        with tempfile.TemporaryDirectory() as tmpdir:
            result = manager.backup_table("users", output_dir=tmpdir)
            assert isinstance(result, BackupResult)
