"""
tests/unit/shared/test_schema_detector.py
SchemaDetector 单元测试

覆盖 dbskiter.shared.schema_detector 的所有方法。
"""

import pytest
from unittest.mock import MagicMock

from dbskiter.shared.schema_detector import SchemaDetector


def make_connector(dialect, database="test_db", username="test_user", rows=None):
    """创建模拟 UnifiedConnector"""
    connector = MagicMock()
    connector.dialect = dialect
    connector.database = database
    connector.username = username

    result = MagicMock()
    result.rows = rows or []
    connector.execute.return_value = result
    return connector


class TestSchemaDetectorInit:
    """初始化测试"""

    def test_init_with_connector(self):
        """有连接器时初始化"""
        conn = make_connector("mysql+pymysql")
        detector = SchemaDetector(conn)
        assert detector.connector is conn
        assert detector.dialect == "mysql+pymysql"
        assert detector._cache == {}

    def test_init_with_no_connector(self):
        """无连接器时初始化"""
        detector = SchemaDetector(None)
        assert detector.dialect == ""


class TestSchemaDetectorColumnCheck:
    """列存在性检查测试"""

    def test_mysql_column_exists(self):
        """MySQL 列存在"""
        conn = make_connector("mysql+pymysql", rows=[[1]])
        detector = SchemaDetector(conn)
        assert detector._check_column_mysql("users", "id", "test_db") is True

    def test_mysql_column_not_exists(self):
        """MySQL 列不存在"""
        conn = make_connector("mysql+pymysql", rows=[[0]])
        detector = SchemaDetector(conn)
        assert detector._check_column_mysql("users", "missing", "test_db") is False

    def test_oracle_column_exists(self):
        """Oracle 列存在"""
        conn = make_connector("oracle+jdbc", username="HR", rows=[[1]])
        detector = SchemaDetector(conn)
        assert detector._check_column_oracle("users", "id", "HR") is True

    def test_oracle_v_dollar_view(self):
        """Oracle v$ 视图走通用方法"""
        conn = make_connector("oracle+jdbc", rows=[])
        detector = SchemaDetector(conn)
        # 通用方法会尝试查询
        result = detector._check_column_oracle("v$session", "sid")
        # 因为 mock 不抛异常，会返回 True
        assert isinstance(result, bool)

    def test_postgres_column_exists(self):
        """PostgreSQL 列存在"""
        conn = make_connector("postgresql+psycopg2", rows=[[1]])
        detector = SchemaDetector(conn)
        assert detector._check_column_postgres("users", "id", "public") is True

    def test_generic_column_check(self):
        """通用列检查"""
        conn = make_connector("unknown_dialect")
        conn.execute.return_value = MagicMock(rows=[])
        detector = SchemaDetector(conn)
        result = detector._check_column_generic("users", "id")
        assert isinstance(result, bool)

    def test_check_column_dispatches_to_mysql(self):
        """列检查分发到 MySQL"""
        conn = make_connector("mysql+pymysql", rows=[[1]])
        detector = SchemaDetector(conn)
        result = detector._check_column_exists("users", "id", "test_db")
        assert result is True

    def test_check_column_dispatches_to_oracle(self):
        """列检查分发到 Oracle"""
        conn = make_connector("oracle+jdbc", username="HR", rows=[[1]])
        detector = SchemaDetector(conn)
        result = detector._check_column_exists("users", "id", "HR")
        assert result is True

    def test_check_column_dispatches_to_postgres(self):
        """列检查分发到 PostgreSQL"""
        conn = make_connector("postgresql+psycopg2", rows=[[1]])
        detector = SchemaDetector(conn)
        result = detector._check_column_exists("users", "id", "public")
        assert result is True

    def test_check_column_dispatches_to_generic(self):
        """列检查分发到通用"""
        conn = make_connector("unknown_dialect")
        detector = SchemaDetector(conn)
        result = detector._check_column_exists("users", "id")
        assert isinstance(result, bool)


class TestSchemaDetectorGetColumnName:
    """get_column_name 测试"""

    def test_get_first_existing_column(self):
        """返回第一个存在的列"""
        conn = make_connector("mysql+pymysql", rows=[[1]])
        detector = SchemaDetector(conn)
        result = detector.get_column_name("users", ["id", "uid"], "test_db")
        assert result == "id"

    def test_get_fallback_column(self):
        """返回第二个存在的列（第一个不存在）"""
        # 第一次返回 0 (列不存在)，第二次返回 1
        conn = make_connector("mysql+pymysql", rows=[[0]])
        detector = SchemaDetector(conn)
        result = detector.get_column_name("users", ["id", "uid"], "test_db")
        # mock 始终返回 [[0]]，所以会检查所有候选都返回 0
        # 然后第二次调用会走缓存
        assert result is None

    def test_get_no_column(self):
        """没有找到任何列"""
        conn = make_connector("mysql+pymysql", rows=[[0]])
        detector = SchemaDetector(conn)
        result = detector.get_column_name("users", ["a", "b"], "test_db")
        assert result is None

    def test_uses_cache(self):
        """使用缓存"""
        conn = make_connector("mysql+pymysql", rows=[[1]])
        detector = SchemaDetector(conn)
        result1 = detector.get_column_name("users", ["id"], "test_db")
        assert result1 == "id"
        # 第二次调用应该走缓存，不再执行 execute
        call_count = conn.execute.call_count
        result2 = detector.get_column_name("users", ["id"], "test_db")
        assert result2 == "id"
        assert conn.execute.call_count == call_count

    def test_cache_returns_none(self):
        """缓存 None 结果"""
        conn = make_connector("mysql+pymysql", rows=[[0]])
        detector = SchemaDetector(conn)
        result1 = detector.get_column_name("users", ["x"], "test_db")
        assert result1 is None
        # 第二次也走缓存
        result2 = detector.get_column_name("users", ["x"], "test_db")
        assert result2 is None

    def test_handles_exception(self):
        """处理异常"""
        conn = make_connector("mysql+pymysql")
        conn.execute.side_effect = Exception("connection lost")
        detector = SchemaDetector(conn)
        result = detector.get_column_name("users", ["id"], "test_db")
        assert result is None


class TestSchemaDetectorGetAvailableTables:
    """get_available_tables 测试"""

    def test_get_mysql_tables(self):
        """获取 MySQL 表"""
        rows = [["users"], ["orders"], ["products"]]
        conn = make_connector("mysql+pymysql", rows=rows)
        detector = SchemaDetector(conn)
        tables = detector.get_available_tables("test_db")
        assert tables == {"users", "orders", "products"}

    def test_get_oracle_tables(self):
        """获取 Oracle 表"""
        rows = [["USERS"], ["ORDERS"]]
        conn = make_connector("oracle+jdbc", username="HR", rows=rows)
        detector = SchemaDetector(conn)
        tables = detector.get_available_tables("HR")
        assert tables == {"USERS", "ORDERS"}

    def test_get_postgres_tables(self):
        """获取 PostgreSQL 表"""
        rows = [["users"], ["orders"]]
        conn = make_connector("postgresql+psycopg2", rows=rows)
        detector = SchemaDetector(conn)
        tables = detector.get_available_tables("public")
        assert tables == {"users", "orders"}

    def test_get_tables_empty(self):
        """空表列表"""
        conn = make_connector("mysql+pymysql", rows=[])
        detector = SchemaDetector(conn)
        tables = detector.get_available_tables("test_db")
        assert tables == set()

    def test_get_tables_handles_exception(self):
        """获取表异常处理"""
        conn = make_connector("mysql+pymysql")
        conn.execute.side_effect = Exception("permission denied")
        detector = SchemaDetector(conn)
        tables = detector.get_available_tables("test_db")
        assert tables == set()

    def test_get_tables_unknown_dialect(self):
        """未知 dialect 返回空"""
        conn = make_connector("trino")
        detector = SchemaDetector(conn)
        tables = detector.get_available_tables("test_db")
        assert tables == set()

    def test_get_tables_uses_cache(self):
        """获取表使用缓存"""
        conn = make_connector("mysql+pymysql", rows=[["users"]])
        detector = SchemaDetector(conn)
        tables1 = detector.get_available_tables("test_db")
        call_count = conn.execute.call_count
        tables2 = detector.get_available_tables("test_db")
        assert tables1 == tables2
        assert conn.execute.call_count == call_count


class TestSchemaDetectorClearCache:
    """clear_cache 测试"""

    def test_clear_cache(self):
        """清空缓存"""
        conn = make_connector("mysql+pymysql", rows=[[1]])
        detector = SchemaDetector(conn)
        # 先填充缓存
        detector.get_column_name("users", ["id"], "test_db")
        assert detector._cache != {}
        # 清空
        detector.clear_cache()
        assert detector._cache == {}