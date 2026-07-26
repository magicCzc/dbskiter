"""
tests/unit/shared/test_ai_context.py
AI Context 单元测试
"""

from unittest.mock import MagicMock

from dbskiter.shared.ai_context import AIOutput, AIEnvelope, AutoContextDetector


def make_mock_connector(dialect="mysql+pymysql", database="test_db", version="8.0.32"):
    conn = MagicMock()
    conn.dialect = dialect
    conn.database = database
    conn.version = version
    conn.host = "localhost"
    conn.port = 3306
    result = MagicMock()
    result.rows = [["test_table"]]
    conn.execute.return_value = result
    return conn


class TestAIOutput:
    def test_to_dict(self):
        output = AIOutput(
            raw_metrics={"cpu": 85.2},
            rule_flags={"cpu_high": {"flagged": True}},
            context={"database_type": "mysql"},
        )
        d = output.to_dict()
        assert d["raw_metrics"]["cpu"] == 85.2
        assert d["context"]["database_type"] == "mysql"

    def test_to_dict_defaults(self):
        output = AIOutput()
        d = output.to_dict()
        assert d["raw_metrics"] == {}
        assert d["rule_flags"] == {}
        assert d["ai_hints"] == {}


class TestAIEnvelope:
    def test_to_dict(self):
        envelope = AIEnvelope(
            schema_version="1.0",
            collected_at="2026-01-01T00:00:00",
            instance_id="mysql-prod-01",
            data_source={"type": "direct", "dialect": "mysql"},
            data=AIOutput(raw_metrics={"cpu": 85.2}),
        )
        d = envelope.to_dict()
        assert d["schema_version"] == "1.0"
        assert d["instance_id"] == "mysql-prod-01"


class TestAutoContextDetector:
    def test_init(self):
        conn = make_mock_connector()
        detector = AutoContextDetector(conn)
        assert detector.connector is conn

    def test_detect_mysql(self):
        conn = make_mock_connector("mysql+pymysql")
        detector = AutoContextDetector(conn)
        result = detector.detect()
        assert isinstance(result, dict)
        # Returns context dict with keys like database_type, top_tables, etc.
        assert "top_tables" in result or "connection_pattern" in result

    def test_detect_oracle(self):
        conn = make_mock_connector("oracle+jdbc")
        detector = AutoContextDetector(conn)
        result = detector.detect()
        assert isinstance(result, dict)

    def test_detect_postgres(self):
        conn = make_mock_connector("postgresql+psycopg2")
        detector = AutoContextDetector(conn)
        result = detector.detect()
        assert isinstance(result, dict)

    def test_detect_mysql_workload(self):
        conn = make_mock_connector("mysql+pymysql")
        detector = AutoContextDetector(conn)
        workload = detector._detect_mysql_workload()
        assert isinstance(workload, str)

    def test_detect_top_tables_mysql(self):
        conn = make_mock_connector("mysql+pymysql")
        detector = AutoContextDetector(conn)
        tables = detector._detect_top_tables(limit=5)
        assert isinstance(tables, list)

    def test_detect_connection_pattern(self):
        conn = make_mock_connector()
        detector = AutoContextDetector(conn)
        pattern = detector._detect_connection_pattern()
        assert isinstance(pattern, str)

    def test_detect_qps(self):
        conn = make_mock_connector()
        detector = AutoContextDetector(conn)
        qps = detector._detect_qps()
        assert qps is None or isinstance(qps, int)

    def test_detect_buffer_pool_usage(self):
        conn = make_mock_connector()
        detector = AutoContextDetector(conn)
        result = detector._detect_buffer_pool_usage()
        assert result is None or isinstance(result, dict)

    def test_handle_exception(self):
        conn = MagicMock()
        conn.execute.side_effect = Exception("DB error")
        conn.dialect = "mysql+pymysql"
        detector = AutoContextDetector(conn)
        # Should not raise, should return with error info
        result = detector.detect()
        assert isinstance(result, dict)
        assert "error" in result or len(result) > 0