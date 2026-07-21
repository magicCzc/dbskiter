"""
tests/unit/shared/test_slow_log_parser.py
SlowLogParser 单元测试
"""

import gzip
import os
import tempfile
from datetime import datetime

import pytest

from dbskiter.shared.slow_log_parser import (
    MySQLSlowLogParser,
    ParsedSlowQuery,
    QueryPattern,
    SlowLogParser,
)


SAMPLE_LOG = """# Time: 2026-04-29T10:00:00.000000Z
# User@Host: root[root] @ localhost []
# Query_time: 2.500000  Lock_time: 0.000100 Rows_sent: 1  Rows_examined: 100000
SET timestamp=1714389600;
SELECT * FROM users WHERE status = 'active';
# Time: 2026-04-29T10:05:00.000000Z
# User@Host: app[app] @ 10.0.0.1 []
# Query_time: 5.000000  Lock_time: 0.000200 Rows_sent: 0  Rows_examined: 50000
SET timestamp=1714389900;
SELECT * FROM orders WHERE created_at < '2026-01-01';
# Time: 2026-04-29T10:10:00.000000Z
# User@Host: root[root] @ localhost []
# Query_time: 1.000000  Lock_time: 0.000100 Rows_sent: 1  Rows_examined: 100000
SET timestamp=1714390200;
SELECT * FROM users WHERE status = 'active';
"""


class TestParsedSlowQuery:
    """ParsedSlowQuery 数据类测试"""

    def test_create_basic(self):
        """创建基本数据类"""
        q = ParsedSlowQuery(
            sql="SELECT 1",
            query_time=1.0,
            lock_time=0.001,
            rows_sent=1,
            rows_examined=100,
            timestamp=datetime.now(),
        )
        assert q.sql == "SELECT 1"
        assert q.query_time == 1.0
        assert q.lock_time == 0.001
        assert q.rows_sent == 1
        assert q.rows_examined == 100

    def test_defaults(self):
        """默认值"""
        q = ParsedSlowQuery(
            sql="SELECT 1",
            query_time=1.0,
            timestamp=datetime.now(),
        )
        assert q.lock_time == 0.0
        assert q.rows_sent == 0
        assert q.rows_examined == 0


class TestQueryPattern:
    """QueryPattern 数据类测试"""

    def test_create_pattern(self):
        """创建模式"""
        p = QueryPattern(fingerprint="abc123", sql_pattern="SELECT * FROM users")
        assert p.fingerprint == "abc123"
        assert p.sql_pattern == "SELECT * FROM users"
        assert p.count == 0
        assert p.total_time == 0.0

    def test_pattern_defaults(self):
        """默认字段"""
        p = QueryPattern(fingerprint="abc", sql_pattern="SELECT 1")
        assert p.avg_time == 0.0
        assert p.max_time == 0.0
        assert p.min_time == float("inf")


class TestSlowLogParserBase:
    """基类测试"""

    def test_init_defaults(self):
        """默认初始化"""
        parser = MySQLSlowLogParser()
        assert parser.encoding == "utf-8"
        assert parser.errors == "replace"
        assert parser._parsed_count == 0
        assert parser._error_count == 0

    def test_init_custom(self):
        """自定义编码"""
        parser = MySQLSlowLogParser(encoding="gbk", errors="ignore")
        assert parser.encoding == "gbk"
        assert parser.errors == "ignore"

    def test_get_stats(self):
        """获取统计"""
        parser = MySQLSlowLogParser()
        stats = parser.get_stats()
        assert stats == {"parsed_count": 0, "error_count": 0}

    def test_get_stats_after_parse(self):
        """解析后统计更新"""
        parser = MySQLSlowLogParser()
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".log", delete=False, encoding="utf-8"
        ) as f:
            f.write(SAMPLE_LOG)
            tmpfile = f.name
        try:
            queries = list(parser.parse_file(tmpfile))
            assert len(queries) >= 1
            stats = parser.get_stats()
            assert stats["parsed_count"] >= 1
        finally:
            os.unlink(tmpfile)


class TestMySQLSlowLogParser:
    """MySQL 慢查询日志解析器测试"""

    def setup_method(self):
        self.parser = MySQLSlowLogParser()

    def test_parse_file(self):
        """解析文件"""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".log", delete=False, encoding="utf-8"
        ) as f:
            f.write(SAMPLE_LOG)
            tmpfile = f.name
        try:
            queries = list(self.parser.parse_file(tmpfile))
            assert len(queries) == 3
            assert queries[0].sql == "SELECT * FROM users WHERE status = 'active';"
            assert queries[0].query_time == 2.5
            assert queries[0].rows_examined == 100000
        finally:
            os.unlink(tmpfile)

    def test_parse_file_with_time_filter(self):
        """按时间过滤"""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".log", delete=False, encoding="utf-8"
        ) as f:
            f.write(SAMPLE_LOG)
            tmpfile = f.name
        try:
            # since = 10:03:00 之后（Unix 时间戳 1714389780 = 2026-04-29 10:03:00）
            since = datetime.fromtimestamp(1714389780)
            queries = list(self.parser.parse_file(tmpfile, since=since))
            # 至少一条匹配
            assert len(queries) >= 1
        finally:
            os.unlink(tmpfile)

    def test_parse_file_gzip(self):
        """解析 gzip 压缩文件"""
        with tempfile.NamedTemporaryFile(
            suffix=".gz", delete=False
        ) as f:
            tmpfile = f.name
        try:
            with gzip.open(tmpfile, "wt", encoding="utf-8") as gf:
                gf.write(SAMPLE_LOG)
            queries = list(self.parser.parse_file(tmpfile))
            assert len(queries) == 3
        finally:
            os.unlink(tmpfile)

    def test_parse_empty_file(self):
        """空文件"""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".log", delete=False, encoding="utf-8"
        ) as f:
            tmpfile = f.name
        try:
            queries = list(self.parser.parse_file(tmpfile))
            assert queries == []
        finally:
            os.unlink(tmpfile)

    def test_parse_extracts_user_host(self):
        """提取 User@Host"""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".log", delete=False, encoding="utf-8"
        ) as f:
            f.write(SAMPLE_LOG)
            tmpfile = f.name
        try:
            queries = list(self.parser.parse_file(tmpfile))
            assert queries[0].user == "root"
            assert queries[0].host == "localhost"
            assert queries[1].user == "app"
        finally:
            os.unlink(tmpfile)

    def test_parse_extracts_timestamp(self):
        """提取时间戳"""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".log", delete=False, encoding="utf-8"
        ) as f:
            f.write(SAMPLE_LOG)
            tmpfile = f.name
        try:
            queries = list(self.parser.parse_file(tmpfile))
            assert queries[0].timestamp is not None
            # Unix 时间戳 1714389600 是 2024 年
            # 仅验证时间戳被提取
            assert isinstance(queries[0].timestamp, datetime)
        finally:
            os.unlink(tmpfile)

    def test_parse_counts_parsed(self):
        """解析计数增加"""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".log", delete=False, encoding="utf-8"
        ) as f:
            f.write(SAMPLE_LOG)
            tmpfile = f.name
        try:
            list(self.parser.parse_file(tmpfile))
            assert self.parser._parsed_count >= 1
        finally:
            os.unlink(tmpfile)


class TestSlowLogParserAbstract:
    """抽象基类测试"""

    def test_cannot_instantiate_base(self):
        """基类不能直接实例化"""
        with pytest.raises(TypeError):
            SlowLogParser()  # type: ignore[abstract]

    def test_subclass_must_implement_parse(self):
        """子类必须实现 parse_file"""
        class IncompleteParser(SlowLogParser):
            pass

        with pytest.raises(TypeError):
            IncompleteParser()  # type: ignore[abstract]