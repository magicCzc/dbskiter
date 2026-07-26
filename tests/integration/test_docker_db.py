"""
Docker 数据库集成测试

测试 dbskiter 与真实数据库的连接和基本操作。
需要 Docker 环境运行 MySQL 和 PostgreSQL 容器。

运行方式:
    docker compose --profile=test up -d
    python -m pytest tests/integration/test_docker_db.py -v
    docker compose down
"""

import os
import pytest

# 如果 DOCKER_DB_SKIP 设置，跳过所有 Docker 数据库测试
pytestmark = pytest.mark.skipif(
    os.environ.get("DOCKER_DB_SKIP", "").lower() in ("1", "true", "yes"),
    reason="Docker 数据库测试已跳过 (DOCKER_DB_SKIP=true)"
)


def test_mysql_connection():
    """测试 MySQL 数据库连接"""
    from dbskiter.shared.unified_connector import UnifiedConnector
    from dbskiter.shared.query_result import QueryResult

    host = os.environ.get("MYSQL_HOST", "127.0.0.1")
    port = int(os.environ.get("MYSQL_PORT", "3307"))
    user = os.environ.get("MYSQL_USER", "root")
    password = os.environ.get("MYSQL_PASSWORD", "root")
    database = os.environ.get("MYSQL_DATABASE", "test")

    connector = UnifiedConnector(
        host=host,
        port=port,
        user=user,
        password=password,
        database=database,
        dialect="mysql+pymysql",
    )

    try:
        result = connector.execute("SELECT 1 AS test_col")
        assert isinstance(result, QueryResult)
        assert result.rows is not None
        assert len(result.rows) > 0
        # 检查结果值 (可能是 tuple 或 dict)
        row = result.rows[0]
        if isinstance(row, dict):
            assert row.get("test_col") == 1
        else:
            assert row[0] == 1
        print(f"MySQL 连接成功: {result.rows}")
    finally:
        connector.close()


def test_postgres_connection():
    """测试 PostgreSQL 数据库连接"""
    from dbskiter.shared.unified_connector import UnifiedConnector
    from dbskiter.shared.query_result import QueryResult

    host = os.environ.get("PG_HOST", "127.0.0.1")
    port = int(os.environ.get("PG_PORT", "5433"))
    user = os.environ.get("PG_USER", "postgres")
    password = os.environ.get("PG_PASSWORD", "postgres")
    database = os.environ.get("PG_DATABASE", "test")

    connector = UnifiedConnector(
        host=host,
        port=port,
        user=user,
        password=password,
        database=database,
        dialect="postgresql",
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
        print(f"PostgreSQL 连接成功: {result.rows}")
    finally:
        connector.close()


def test_mysql_diagnose():
    """测试 MySQL 诊断功能"""
    from dbskiter.shared.unified_connector import UnifiedConnector
    from dbskiter.db_diagnose import DiagnoseSkill

    host = os.environ.get("MYSQL_HOST", "127.0.0.1")
    port = int(os.environ.get("MYSQL_PORT", "3307"))
    user = os.environ.get("MYSQL_USER", "root")
    password = os.environ.get("MYSQL_PASSWORD", "root")
    database = os.environ.get("MYSQL_DATABASE", "test")

    connector = UnifiedConnector(
        host=host, port=port, user=user, password=password,
        database=database, dialect="mysql+pymysql",
    )

    try:
        skill = DiagnoseSkill(connector)
        # 分析简单 SQL
        result = skill.analyze_sql("SELECT 1")
        assert result is not None
        assert result.get("status") == "success" or "summary" in result
        print(f"MySQL 诊断成功: {result.get('summary', 'OK')[:100]}")
    finally:
        connector.close()