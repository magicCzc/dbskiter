"""
扩展 Docker 数据库集成测试

测试 dbskiter 与 ClickHouse 和 SQL Server 的连接。
需要 Docker 环境运行相应容器。

运行方式:
    docker compose --profile=full up -d clickhouse mssql
    python -m pytest tests/integration/test_docker_db_extended.py -v
    docker compose down
"""

import os
import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("DOCKER_DB_SKIP", "").lower() in ("1", "true", "yes"),
    reason="Docker 数据库测试已跳过 (DOCKER_DB_SKIP=true)"
)


def test_clickhouse_connection():
    """测试 ClickHouse 数据库连接"""
    from dbskiter.shared.unified_connector import UnifiedConnector
    from dbskiter.shared.query_result import QueryResult

    host = os.environ.get("CLICKHOUSE_HOST", "127.0.0.1")
    port = int(os.environ.get("CLICKHOUSE_PORT", "9000"))
    database = os.environ.get("CLICKHOUSE_DB", "test")

    connector = UnifiedConnector(
        host=host,
        port=port,
        database=database,
        dialect="clickhouse",
    )

    try:
        result = connector.execute("SELECT 1 AS test_col")
        assert isinstance(result, QueryResult)
        assert result.rows is not None
        assert len(result.rows) > 0
        row = result.rows[0]
        if isinstance(row, dict):
            assert row.get("test_col") == 1
        else:
            assert row[0] == 1
        print(f"ClickHouse 连接成功: {result.rows}")
    finally:
        connector.close()


def test_clickhouse_diagnose():
    """测试 ClickHouse 诊断功能"""
    from dbskiter.shared.unified_connector import UnifiedConnector
    from dbskiter.db_diagnose import DiagnoseSkill

    host = os.environ.get("CLICKHOUSE_HOST", "127.0.0.1")
    port = int(os.environ.get("CLICKHOUSE_PORT", "9000"))
    database = os.environ.get("CLICKHOUSE_DB", "test")

    connector = UnifiedConnector(
        host=host, port=port, database=database, dialect="clickhouse",
    )

    try:
        skill = DiagnoseSkill(connector)
        result = skill.analyze_sql("SELECT 1")
        assert result is not None
        print(f"ClickHouse 诊断成功: {result.get('summary', 'OK')[:100]}")
    finally:
        connector.close()


def test_mssql_connection():
    """测试 SQL Server 数据库连接"""
    pytest.skip("SQL Server 需要 pyodbc 驱动，在 CI 中需要额外配置")

    from dbskiter.shared.unified_connector import UnifiedConnector
    from dbskiter.shared.query_result import QueryResult

    host = os.environ.get("MSSQL_HOST", "127.0.0.1")
    port = int(os.environ.get("MSSQL_PORT", "1433"))
    user = os.environ.get("MSSQL_USER", "sa")
    password = os.environ.get("MSSQL_PASSWORD", "Dbskiter123!")
    database = os.environ.get("MSSQL_DATABASE", "master")

    connector = UnifiedConnector(
        host=host, port=port, user=user, password=password,
        database=database, dialect="mssql+pyodbc",
    )

    try:
        result = connector.execute("SELECT 1 AS test_col")
        assert isinstance(result, QueryResult)
        assert result.rows is not None
        assert len(result.rows) > 0
        row = result.rows[0]
        if isinstance(row, dict):
            assert row.get("test_col") == 1
        else:
            assert row[0] == 1
        print(f"SQL Server 连接成功: {result.rows}")
    finally:
        connector.close()