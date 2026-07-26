"""
test_error_handler.py

shared/error_handler 模块单元测试

测试覆盖：
- ErrorCode 枚举完整性
- SkillError 异常类
- create_error_response 多种调用方式
- create_success_response
- handle_exception
"""

import pytest
from dbskiter.shared.error_handler import (
    ErrorCode,
    SkillError,
    ConnectionError,
    QueryError,
    ConfigError,
    ValidationError,
    create_error_response,
    create_success_response,
    handle_exception,
)


class TestErrorCode:
    """ErrorCode 枚举测试"""

    def test_all_codes_are_strings(self):
        for code in ErrorCode:
            assert isinstance(code.value, str)

    def test_connection_codes(self):
        assert ErrorCode.CONNECTION_FAILED.value == "1001"
        assert ErrorCode.CONNECTION_TIMEOUT.value == "1002"
        assert ErrorCode.AUTHENTICATION_FAILED.value == "1004"

    def test_query_codes(self):
        assert ErrorCode.QUERY_FAILED.value == "2001"
        assert ErrorCode.INVALID_SQL.value == "2003"

    def test_config_codes(self):
        assert ErrorCode.CONFIG_INVALID.value == "3001"

    def test_unknown_code(self):
        assert ErrorCode.UNKNOWN_ERROR.value == "9999"


class TestSkillError:
    """SkillError 异常类测试"""

    def test_basic_creation(self):
        err = SkillError(ErrorCode.CONNECTION_FAILED, "连接失败")
        assert err.code == ErrorCode.CONNECTION_FAILED
        assert err.message == "连接失败"
        assert err.details == {}

    def test_with_details(self):
        err = SkillError(
            ErrorCode.QUERY_FAILED,
            "查询出错",
            details={"sql": "SELECT 1"}
        )
        assert err.details == {"sql": "SELECT 1"}

    def test_to_dict(self):
        err = SkillError(ErrorCode.CONNECTION_FAILED, "连接失败")
        d = err.to_dict()
        assert d["code"] == "1001"
        assert d["message"] == "连接失败"
        assert "timestamp" in d

    def test_string_representation(self):
        err = SkillError(ErrorCode.CONNECTION_FAILED, "连接失败")
        assert "1001" in str(err)
        assert "连接失败" in str(err)


class TestSubExceptions:
    """子异常类测试"""

    def test_connection_error(self):
        err = ConnectionError("连接被拒绝")
        assert isinstance(err, SkillError)
        assert err.code == ErrorCode.CONNECTION_FAILED

    def test_query_error(self):
        err = QueryError("语法错误")
        assert isinstance(err, SkillError)
        assert err.code == ErrorCode.QUERY_FAILED

    def test_config_error(self):
        err = ConfigError("缺少配置")
        assert isinstance(err, SkillError)
        assert err.code == ErrorCode.CONFIG_INVALID

    def test_validation_error(self):
        err = ValidationError("参数不合法")
        assert isinstance(err, SkillError)


class TestCreateErrorResponse:
    """create_error_response 测试"""

    def test_with_exception(self):
        try:
            raise ConnectionError("连接被拒绝")
        except Exception as e:
            result = create_error_response(e, context="数据库连接")
        assert result["success"] is False
        assert "error" in result
        assert result["error"]["message"] == "连接被拒绝"

    def test_with_skill_error(self):
        err = SkillError(ErrorCode.QUERY_FAILED, "查询失败", details={"sql": "SELECT 1"})
        result = create_error_response(err)
        assert result["success"] is False
        assert result["error"]["code"] == "2001"

    def test_with_string_message(self):
        result = create_error_response("参数错误", error_code="DIA000002")
        assert result["success"] is False
        assert result["error"]["message"] == "参数错误"
        assert result["error"]["code"] == "DIA000002"

    def test_with_string_message_and_details(self):
        result = create_error_response(
            "连接失败",
            error_code="MON100003",
            details={"host": "localhost"}
        )
        assert result["success"] is False
        assert result["error"]["details"]["host"] == "localhost"

    def test_with_module_error_code(self):
        """支持各模块自定义错误码字符串"""
        result = create_error_response("锁分析失败", error_code="LOCK20001")
        assert result["error"]["code"] == "LOCK20001"


class TestCreateSuccessResponse:
    """create_success_response 测试"""

    def test_basic(self):
        result = create_success_response(data={"count": 10}, message="查询成功")
        assert result["success"] is True
        assert result["data"]["count"] == 10
        assert result["message"] == "查询成功"

    def test_no_data(self):
        result = create_success_response()
        assert result["success"] is True

    def test_with_metadata(self):
        result = create_success_response(
            data=[1, 2, 3],
            message="列表",
            metadata={"total": 3}
        )
        assert result["metadata"]["total"] == 3


class TestHandleException:
    """handle_exception 测试"""

    def test_returns_error_response(self):
        try:
            raise ValueError("测试异常")
        except Exception as e:
            result = handle_exception(e, context="测试操作")
        assert result["success"] is False

    def test_fallback_value(self):
        try:
            raise ValueError("测试异常")
        except Exception as e:
            result = handle_exception(e, fallback_value={"default": True})
        assert result["default"] is True

    def test_reraise(self):
        with pytest.raises(ValueError):
            try:
                raise ValueError("测试异常")
            except Exception as e:
                handle_exception(e, reraise=True)
