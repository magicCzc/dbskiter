"""
test_validators.py

shared/validators 模块单元测试

测试覆盖：
- Validator 各静态验证方法
- validate_params 装饰器
- sanitize_sql 脱敏函数
- 修复验证：valid_limit 不再重复定义
"""

import pytest
from dbskiter.shared.validators import Validator, validate_params, sanitize_sql


class TestValidatorBasic:
    """Validator 基础验证方法测试"""

    def test_not_none_with_value(self):
        assert Validator.not_none("hello") is True

    def test_not_none_with_none(self):
        assert Validator.not_none(None) is False

    def test_not_empty_string_valid(self):
        assert Validator.not_empty_string("hello") is True

    def test_not_empty_string_empty(self):
        assert Validator.not_empty_string("") is False

    def test_not_empty_string_whitespace(self):
        assert Validator.not_empty_string("   ") is False

    def test_not_empty_string_non_string(self):
        assert Validator.not_empty_string(123) is False

    def test_positive_int_valid(self):
        assert Validator.positive_int(1) is True
        assert Validator.positive_int(100) is True

    def test_positive_int_zero(self):
        assert Validator.positive_int(0) is False

    def test_positive_int_negative(self):
        assert Validator.positive_int(-1) is False

    def test_positive_int_non_int(self):
        assert Validator.positive_int(1.5) is False

    def test_non_negative_int_valid(self):
        assert Validator.non_negative_int(0) is True
        assert Validator.non_negative_int(10) is True

    def test_non_negative_int_negative(self):
        assert Validator.non_negative_int(-1) is False

    def test_not_empty_list_valid(self):
        assert Validator.not_empty_list([1, 2]) is True

    def test_not_empty_list_empty(self):
        assert Validator.not_empty_list([]) is False

    def test_not_empty_list_non_list(self):
        assert Validator.not_empty_list("not a list") is False

    def test_list_not_empty_alias(self):
        """list_not_empty 是 not_empty_list 的别名"""
        assert Validator.list_not_empty([1]) is True
        assert Validator.list_not_empty([]) is False


class TestValidatorLimitAndTimeout:
    """valid_limit 和 valid_timeout 测试 - 验证不再有重复定义"""

    def test_valid_limit_normal(self):
        assert Validator.valid_limit(100) is True

    def test_valid_limit_boundary_low(self):
        assert Validator.valid_limit(1) is True

    def test_valid_limit_boundary_high(self):
        assert Validator.valid_limit(10000) is True

    def test_valid_limit_zero(self):
        assert Validator.valid_limit(0) is False

    def test_valid_limit_over_max(self):
        assert Validator.valid_limit(10001) is False

    def test_valid_limit_none_pass(self):
        """None 应该通过验证（表示不限制）"""
        assert Validator.valid_limit(None) is True

    def test_valid_limit_non_int(self):
        assert Validator.valid_limit("10") is False

    def test_valid_timeout_normal(self):
        assert Validator.valid_timeout(30) is True

    def test_valid_timeout_boundary_low(self):
        assert Validator.valid_timeout(1) is True

    def test_valid_timeout_boundary_high(self):
        assert Validator.valid_timeout(3600) is True

    def test_valid_timeout_over_max(self):
        assert Validator.valid_timeout(3601) is False

    def test_valid_timeout_zero(self):
        assert Validator.valid_timeout(0) is False


class TestValidatorIdentifiers:
    """SQL 标识符验证测试"""

    def test_valid_table_name_normal(self):
        assert Validator.valid_table_name("users") is True

    def test_valid_table_name_with_underscore(self):
        assert Validator.valid_table_name("user_orders") is True

    def test_valid_table_name_with_digit(self):
        assert Validator.valid_table_name("tbl_123") is True

    def test_valid_table_name_start_with_digit(self):
        assert Validator.valid_table_name("123table") is False

    def test_valid_table_name_with_special_char(self):
        assert Validator.valid_table_name("user-table") is False

    def test_valid_table_name_non_string(self):
        assert Validator.valid_table_name(123) is False

    def test_valid_column_name_same_as_table(self):
        """列名验证与表名规则一致"""
        assert Validator.valid_column_name("col_name") is True
        assert Validator.valid_column_name("123col") is False

    def test_valid_sql_identifier_normal(self):
        assert Validator.valid_sql_identifier("users") is True

    def test_valid_sql_identifier_with_semicolon(self):
        """包含分号的标识符应被拒绝"""
        assert Validator.valid_sql_identifier("users; DROP TABLE") is False

    def test_valid_sql_identifier_with_comment(self):
        """包含注释的标识符应被拒绝"""
        assert Validator.valid_sql_identifier("users--comment") is False

    def test_valid_sql_identifier_with_drop(self):
        """包含 DROP 的标识符应被拒绝"""
        assert Validator.valid_sql_identifier("drop table") is False


class TestValidatorComposable:
    """可组合验证器测试"""

    def test_in_range_valid(self):
        validator = Validator.in_range(0, 100)
        assert validator(50) is True

    def test_in_range_boundary(self):
        validator = Validator.in_range(0, 100)
        assert validator(0) is True
        assert validator(100) is True

    def test_in_range_out(self):
        validator = Validator.in_range(0, 100)
        assert validator(-1) is False
        assert validator(101) is False

    def test_one_of_valid(self):
        validator = Validator.one_of(["a", "b", "c"])
        assert validator("a") is True

    def test_one_of_invalid(self):
        validator = Validator.one_of(["a", "b", "c"])
        assert validator("d") is False


class TestValidateParamsDecorator:
    """validate_params 装饰器测试"""

    def test_pass_validation(self):
        @validate_params(name=Validator.not_empty_string)
        def greet(name: str):
            return {"success": True, "name": name}

        result = greet("world")
        assert result["success"] is True
        assert result["name"] == "world"

    def test_fail_validation(self):
        @validate_params(name=Validator.not_empty_string)
        def greet(name: str):
            return {"success": True, "name": name}

        result = greet("")
        assert result["success"] is False

    def test_multiple_validators(self):
        @validate_params(
            table=Validator.not_empty_string,
            limit=Validator.positive_int
        )
        def query(table: str, limit: int):
            return {"success": True}

        result = query("users", 10)
        assert result["success"] is True

    def test_multiple_validators_partial_fail(self):
        @validate_params(
            table=Validator.not_empty_string,
            limit=Validator.positive_int
        )
        def query(table: str, limit: int):
            return {"success": True}

        result = query("users", -1)
        assert result["success"] is False


class TestSanitizeSql:
    """SQL 脱敏函数测试"""

    def test_sanitize_password(self):
        sql = "SELECT * FROM users WHERE password = 'secret123'"
        result = sanitize_sql(sql)
        assert "secret123" not in result
        assert "'***'" in result

    def test_sanitize_token(self):
        sql = "UPDATE config SET token = 'abc123def'"
        result = sanitize_sql(sql)
        assert "abc123def" not in result

    def test_sanitize_empty(self):
        assert sanitize_sql("") == ""

    def test_sanitize_none(self):
        assert sanitize_sql(None) == ""

    def test_sanitize_normal_sql(self):
        sql = "SELECT id, name FROM users WHERE age > 18"
        result = sanitize_sql(sql)
        assert result == sql
