"""
test_query_result.py

shared/query_result 模块单元测试

测试覆盖：
- QueryResult 创建和验证
- to_dict_list 转换
- df 属性
- to_json / to_csv 导出
"""

import pytest
from dbskiter.shared.query_result import QueryResult


class TestQueryResultCreation:
    """QueryResult 创建测试"""

    def test_basic_creation(self):
        result = QueryResult(
            rows=[(1, "Alice"), (2, "Bob")],
            columns=["id", "name"],
            row_count=2,
            execution_time_ms=12.5
        )
        assert result.row_count == 2
        assert len(result.rows) == 2
        assert result.execution_time_ms == 12.5

    def test_empty_result(self):
        result = QueryResult(
            rows=[],
            columns=["id", "name"],
            row_count=0
        )
        assert result.row_count == 0

    def test_affected_rows(self):
        result = QueryResult(
            rows=[],
            columns=[],
            row_count=0,
            affected_rows=5
        )
        assert result.affected_rows == 5


class TestQueryResultConversion:
    """QueryResult 数据转换测试"""

    def test_to_dict_list(self):
        result = QueryResult(
            rows=[(1, "Alice"), (2, "Bob")],
            columns=["id", "name"],
            row_count=2
        )
        dict_list = result.to_dict_list()
        assert len(dict_list) == 2
        assert dict_list[0] == {"id": 1, "name": "Alice"}
        assert dict_list[1] == {"id": 2, "name": "Bob"}

    def test_to_dict_list_empty(self):
        result = QueryResult(
            rows=[],
            columns=["id"],
            row_count=0
        )
        assert result.to_dict_list() == []

    def test_df_property(self):
        result = QueryResult(
            rows=[(1, "Alice"), (2, "Bob")],
            columns=["id", "name"],
            row_count=2
        )
        df = result.df
        assert len(df) == 2
        assert list(df.columns) == ["id", "name"]
        assert df.iloc[0]["name"] == "Alice"

    def test_df_cached(self):
        result = QueryResult(
            rows=[(1, "test")],
            columns=["id", "val"],
            row_count=1
        )
        df1 = result.df
        df2 = result.df
        assert df1 is df2


class TestQueryResultExport:
    """QueryResult 导出测试"""

    def test_to_json_string(self):
        result = QueryResult(
            rows=[(1, "Alice")],
            columns=["id", "name"],
            row_count=1
        )
        json_str = result.to_json()
        assert "Alice" in json_str
        assert "id" in json_str

    def test_to_csv_string(self):
        import tempfile
        import os
        result = QueryResult(
            rows=[(1, "Alice"), (2, "Bob")],
            columns=["id", "name"],
            row_count=2
        )
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            path = f.name
        try:
            result.to_csv(path)
            with open(path, 'r') as f:
                csv_str = f.read()
            assert "id,name" in csv_str
            assert "Alice" in csv_str
        finally:
            os.unlink(path)
