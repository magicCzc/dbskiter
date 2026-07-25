"""
tests/test_backup_skill_split.py

验证 db_scheduler/backup/manager.py 拆分后的 Mixin 架构完整性
"""

from dbskiter.db_scheduler.backup import BackupManager
from dbskiter.db_scheduler.backup.mixins import (
    MySQLBackupMixin, PostgreSQLBackupMixin, SQLiteBackupMixin,
    ClickHouseBackupMixin, OracleBackupMixin, MSSQLBackupMixin,
    GenericBackupMixin, BackupUtilsMixin,
)


class TestBackupManagerMixinArchitecture:
    """验证 BackupManager Mixin 架构完整性"""

    def test_inherits_all_mixins(self):
        mro = [c.__name__ for c in BackupManager.__mro__]
        assert "MySQLBackupMixin" in mro
        assert "PostgreSQLBackupMixin" in mro
        assert "SQLiteBackupMixin" in mro
        assert "ClickHouseBackupMixin" in mro
        assert "OracleBackupMixin" in mro
        assert "MSSQLBackupMixin" in mro
        assert "GenericBackupMixin" in mro
        assert "BackupUtilsMixin" in mro

    def test_mixin_imports(self):
        assert MySQLBackupMixin.__name__ == "MySQLBackupMixin"
        assert PostgreSQLBackupMixin.__name__ == "PostgreSQLBackupMixin"
        assert SQLiteBackupMixin.__name__ == "SQLiteBackupMixin"
        assert OracleBackupMixin.__name__ == "OracleBackupMixin"


class TestBackupMethods:
    """验证关键方法可访问"""

    def test_core_methods(self):
        assert hasattr(BackupManager, "backup_full")
        assert hasattr(BackupManager, "backup_table")
        assert hasattr(BackupManager, "list_backups")
        assert hasattr(BackupManager, "verify_backup")
        assert hasattr(BackupManager, "restore_backup")
        assert hasattr(BackupManager, "delete_backup")

    def test_mysql_methods(self):
        assert hasattr(BackupManager, "_mysql_full_backup")
        assert hasattr(BackupManager, "_mysql_restore")
        assert hasattr(BackupManager, "_escape_mysql_value")

    def test_pg_methods(self):
        assert hasattr(BackupManager, "_pg_full_backup")
        assert hasattr(BackupManager, "_pg_restore")

    def test_utils_methods(self):
        assert hasattr(BackupManager, "_safe_table_name")
        assert hasattr(BackupManager, "_gzip_file")
        assert hasattr(BackupManager, "_human_size")
        assert hasattr(BackupManager, "_compute_sha256")