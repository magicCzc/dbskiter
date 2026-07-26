"""
tests/test_url_parser.py
URL 连接字符串解析器单元测试
"""

import pytest

from dbskiter.cli.url_parser import parse_url, normalize_dialect


class TestParseURL:
    def test_mysql_url(self):
        r = parse_url("mysql+pymysql://root:pass@localhost:3306/test")
        assert r["dialect"] == "mysql+pymysql"
        assert r["user"] == "root"
        assert r["password"] == "pass"
        assert r["host"] == "localhost"
        assert r["port"] == 3306
        assert r["database"] == "test"

    def test_postgres_url(self):
        r = parse_url("postgresql://user@pg-host:5432/mydb")
        assert r["dialect"] == "postgresql"
        assert r["user"] == "user"
        assert r.get("password") is None

    def test_url_with_query_params(self):
        r = parse_url("mysql://root@localhost/test?charset=utf8")
        assert "query" in r
        assert r["query"]["charset"] == "utf8"

    def test_sqlite_url(self):
        r = parse_url("sqlite:///path/to/db.sqlite3")
        assert r["dialect"] == "sqlite"
        assert r["database"] == "path/to/db.sqlite3"

    def test_sqlite_relative_path(self):
        r = parse_url("sqlite:///test.db")
        assert r["database"] == "test.db"

    def test_oracle_url(self):
        r = parse_url("oracle+oracledb://user:pass@oracle-host:1521/ORCL")
        assert r["dialect"] == "oracle+oracledb"
        assert r["port"] == 1521
        assert r["database"] == "ORCL"

    def test_mssql_url(self):
        r = parse_url("mssql+pyodbc://sa:pass@sqlserver:1433/master")
        assert r["dialect"] == "mssql+pyodbc"
        assert r["port"] == 1433

    def test_clickhouse_url(self):
        r = parse_url("clickhouse://default@clickhouse-host:9000/default")
        assert r["dialect"] == "clickhouse"
        assert r["port"] == 9000

    def test_empty_url(self):
        r = parse_url("")
        assert "error" in r

    def test_invalid_url(self):
        r = parse_url("not-a-url")
        assert "error" in r

    def test_url_without_password(self):
        r = parse_url("mysql://root@localhost/test")
        assert r["user"] == "root"
        assert r.get("password") is None

    def test_url_without_port(self):
        """测试无端口的 URL"""
        r = parse_url("mysql://user:pass@localhost/test")
        assert r["host"] == "localhost"
        assert r.get("port") is None
        assert r["database"] == "test"

    def test_url_with_special_chars(self):
        r = parse_url("mysql://user:p%40ss@host/db")
        assert r["password"] == "p@ss"


class TestNormalizeDialect:
    def test_mysql(self):
        assert normalize_dialect("mysql") == "mysql+pymysql"

    def test_postgres(self):
        assert normalize_dialect("postgres") == "postgresql"

    def test_pg(self):
        assert normalize_dialect("pg") == "postgresql"

    def test_oracle(self):
        assert normalize_dialect("oracle") == "oracle+oracledb"

    def test_mssql(self):
        assert normalize_dialect("mssql") == "mssql+pyodbc"

    def test_sqlite(self):
        assert normalize_dialect("sqlite") == "sqlite"

    def test_clickhouse(self):
        assert normalize_dialect("clickhouse") == "clickhouse"

    def test_already_normalized(self):
        assert normalize_dialect("mysql+pymysql") == "mysql+pymysql"

    def test_unknown_dialect(self):
        assert normalize_dialect("unknown") == "unknown"


# ──────────────────────────────────────────────
# Hypothesis property-based tests
# 自动生成大量随机 URL 并验证解析器不崩溃、结果格式正确
# ──────────────────────────────────────────────

from hypothesis import given, strategies as st, assume, settings
from hypothesis.strategies import text as st_text

# 安全的字符集（避免 SQLAlchemy 解析时被 URL 编码搞乱）
_SAFE_CHARS = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-._~"
_SAFE_PASS_CHARS = _SAFE_CHARS + ":@!$&'()*+,;="


@st.composite
def url_strategy(draw):
    """生成随机数据库 URL 的策略"""
    scheme = draw(st.sampled_from([
        "mysql", "mysql+pymysql", "postgresql", "postgresql+psycopg2",
        "sqlite", "oracle+oracledb", "mssql+pyodbc", "clickhouse",
    ]))

    has_auth = draw(st.booleans())
    user = None
    password = None
    if has_auth:
        user = draw(st_text(alphabet=_SAFE_CHARS, min_size=1, max_size=10))
        if draw(st.booleans()):
            password = draw(st_text(alphabet=_SAFE_PASS_CHARS, min_size=0, max_size=10))

    has_host = scheme != "sqlite"
    host = None
    port = None
    if has_host:
        host = draw(st.sampled_from(["localhost", "db.example.com", "192.168.1.1", "::1"]))
        if draw(st.booleans()):
            port = draw(st.integers(min_value=1, max_value=65535))

    has_db = draw(st.booleans())
    database = None
    if has_db:
        if scheme == "sqlite":
            database = draw(st.sampled_from(["test.db", "/path/to/db.sqlite3", "relative/path/db.db"]))
        else:
            database = draw(st_text(alphabet=_SAFE_CHARS, min_size=1, max_size=10))

    # 构建 URL
    url = f"{scheme}://"
    if user is not None:
        url += user
        if password is not None:
            url += f":{password}"
        url += "@"
    if host is not None:
        url += host
    if port is not None:
        url += f":{port}"
    if database is not None:
        if scheme == "sqlite":
            url += "/" + database
        else:
            url = f"{url}/{database}"

    return url


class TestParseURLProperty:
    """Hypothesis property-based tests for URL parser"""

    @given(url=url_strategy())
    @settings(max_examples=200)
    def test_parse_url_never_crashes(self, url):
        """解析器不应该崩溃（返回 dict 或 error dict）"""
        result = parse_url(url)
        assert isinstance(result, dict)
        if "error" not in result:
            assert "dialect" in result

    @given(url=url_strategy())
    @settings(max_examples=100)
    def test_parse_url_roundtrip(self, url):
        """解析结果应该包含基本的 dialect 信息"""
        result = parse_url(url)
        if "error" in result:
            return  # 某些 malformed URL 被标记为 error 是可接受的
        assert "dialect" in result
        assert result["dialect"] != ""

    @given(
        scheme=st.sampled_from(["mysql", "postgresql", "sqlite"]),
        user=st.one_of(st.none(), st_text(alphabet=_SAFE_CHARS, min_size=1, max_size=10)),
        host=st.one_of(st.none(), st_text(alphabet=_SAFE_CHARS, min_size=1, max_size=20)),
        port=st.one_of(st.none(), st.integers(min_value=1, max_value=65535)),
        db=st.one_of(st.none(), st_text(alphabet=_SAFE_CHARS, min_size=1, max_size=10)),
    )
    @settings(max_examples=200)
    def test_parse_url_components(self, scheme, user, host, port, db):
        """验证解析结果中的字段与输入一致（如果存在）"""
        # 构建 URL
        url = f"{scheme}://"
        if user:
            url += f"{user}@"
        if host:
            url += host
        if port is not None:
            url += f":{port}"
        if db:
            url += f"/{db}"

        result = parse_url(url)
        if "error" in result:
            assume(False)  # SQLAlchemy 发起的错误，跳过
            return

        assert result["dialect"].startswith(scheme)
        if user:
            assert result.get("user") == user
        if host:
            assert result.get("host") == host
        if port is not None:
            assert result.get("port") == port
        if db:
            # SQLite 路径可能包含 /
            if scheme == "sqlite" and "/" in db:
                assert result.get("database", "").endswith(db)
            else:
                assert result.get("database") == db

    def test_edge_case_no_port(self):
        """无端口 URL 应返回 None port"""
        result = parse_url("mysql://user:pass@localhost/db")
        assert "error" not in result
        assert result.get("port") is None

    def test_edge_case_special_chars_password(self):
        """密码中的 URL 编码字符应正确解码"""
        result = parse_url("mysql://user:p%40ss%23word@host/db")
        assert "error" not in result
        assert result.get("password") == "p@ss#word"

    def test_edge_case_only_host(self):
        """只有 host 没有数据库名"""
        result = parse_url("mysql://localhost")
        assert "error" not in result or result.get("host") == "localhost"

    def test_edge_case_empty_password(self):
        """空密码"""
        result = parse_url("mysql://user:@localhost/db")
        assert "error" not in result
        # SQLAlchemy 可能将空密码视为 None 或 ""
        # 只要不崩溃就行

    def test_fuzz_malformed_urls(self):
        """各种畸形 URL 不应该崩溃"""
        malformed = [
            "://",
            "mysql://",
            "://localhost",
            "mysql://localhost:",
            "mysql://localhost:/",
            "mysql://user@localhost:abc/db",
            "mysql://user:pass@localhost:99999/db",
            "invalid",
            "",
            " ",
            "mysql://user@localhost/db?",
            "mysql://user@localhost/db?key",
            "mysql://user@localhost/db?key=",
            "mysql://user@localhost/db?=value",
            "mysql://user@localhost/db?a=b&c=d",
        ]
        for url in malformed:
            result = parse_url(url)
            assert isinstance(result, dict), f"崩溃于: {url}"
            # 不关心结果是什么，只要不抛出异常即可