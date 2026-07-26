"""
test_sql_dialect.py

shared/sql_dialect 模块单元测试

测试覆盖：
- SQLDialectManager 方言检测
- LIMIT 子句生成
- 不同数据库的语法差异处理
"""

import pytest
from dbskiter.shared.sql_dialect import SQLDialectManager, SQLDialect


class TestSQLDialectDetection:
    """方言检测测试"""

    def test_detect_mysql(self):
        manager = SQLDialectManager("mysql+pymysql")
        assert manager.dialect == "mysql"

    def test_detect_postgresql(self):
        manager = SQLDialectManager("postgresql+psycopg2")
        assert manager.dialect == "postgresql"

    def test_detect_oracle(self):
        manager = SQLDialectManager("oracle+oracledb")
        assert manager.dialect == "oracle"

    def test_detect_sqlite(self):
        manager = SQLDialectManager("sqlite")
        assert manager.dialect == "sqlite"

    def test_detect_sqlserver(self):
        manager = SQLDialectManager("mssql+pyodbc")
        assert manager.dialect == "sqlserver"


class TestLimitSQL:
    """LIMIT 子句生成测试"""

    def test_mysql_limit(self):
        manager = SQLDialectManager("mysql")
        result = manager.get_limit_sql("SELECT * FROM users", 10)
        assert result == "SELECT * FROM users LIMIT 10"

    def test_mysql_limit_with_offset(self):
        manager = SQLDialectManager("mysql")
        result = manager.get_limit_sql("SELECT * FROM users", 10, offset=5)
        assert result == "SELECT * FROM users LIMIT 5, 10"

    def test_postgresql_limit(self):
        manager = SQLDialectManager("postgresql")
        result = manager.get_limit_sql("SELECT * FROM users", 10)
        assert result == "SELECT * FROM users LIMIT 10"

    def test_postgresql_limit_with_offset(self):
        manager = SQLDialectManager("postgresql")
        result = manager.get_limit_sql("SELECT * FROM users", 10, offset=5)
        assert result == "SELECT * FROM users LIMIT 10 OFFSET 5"

    def test_sqlite_limit(self):
        manager = SQLDialectManager("sqlite")
        result = manager.get_limit_sql("SELECT * FROM users", 10)
        assert result == "SELECT * FROM users LIMIT 10"


class TestSQLDialectEnum:
    """SQLDialect 枚举测试"""

    def test_all_dialects_exist(self):
        assert SQLDialect.MYSQL.value == "mysql"
        assert SQLDialect.POSTGRESQL.value == "postgresql"
        assert SQLDialect.ORACLE.value == "oracle"
        assert SQLDialect.SQLITE.value == "sqlite"
        assert SQLDialect.SQLSERVER.value == "sqlserver"
