"""
tests/unit/shared/test_utils.py
shared/utils 单元测试
"""

import pytest

from dbskiter.shared.utils import format_bytes, format_duration, truncate_text


class TestFormatBytes:
    """format_bytes 测试"""

    def test_bytes(self):
        """字节"""
        assert format_bytes(0) == "0.00 B"
        assert format_bytes(512) == "512.00 B"

    def test_kilobytes(self):
        """KB"""
        assert format_bytes(1024) == "1.00 KB"
        assert format_bytes(2048) == "2.00 KB"

    def test_megabytes(self):
        """MB"""
        assert format_bytes(1024 * 1024) == "1.00 MB"
        assert format_bytes(5 * 1024 * 1024) == "5.00 MB"

    def test_gigabytes(self):
        """GB"""
        assert format_bytes(1024 * 1024 * 1024) == "1.00 GB"
        assert format_bytes(2.5 * 1024 * 1024 * 1024) == "2.50 GB"

    def test_terabytes(self):
        """TB"""
        assert format_bytes(1024 ** 4) == "1.00 TB"

    def test_petabytes(self):
        """PB (largest unit)"""
        assert format_bytes(1024 ** 5) == "1.00 PB"

    def test_zero(self):
        """零字节"""
        assert format_bytes(0) == "0.00 B"


class TestFormatDuration:
    """format_duration 测试"""

    def test_seconds(self):
        """秒"""
        assert format_duration(0) == "0.0s"
        assert format_duration(45) == "45.0s"

    def test_minutes(self):
        """分钟"""
        assert format_duration(60) == "1m 0s"
        assert format_duration(90) == "1m 30s"
        assert format_duration(125) == "2m 5s"

    def test_hours(self):
        """小时"""
        assert format_duration(3600) == "1h 0m 0s"
        assert format_duration(3661) == "1h 1m 1s"
        assert format_duration(7325) == "2h 2m 5s"

    def test_fractional_seconds(self):
        """小数秒"""
        assert format_duration(1.5) == "1.5s"
        assert format_duration(30.7) == "30.7s"

    def test_large_value(self):
        """大值"""
        # 1 day
        assert format_duration(86400) == "24h 0m 0s"


class TestTruncateText:
    """truncate_text 测试"""

    def test_no_truncation_needed(self):
        """不需要截断"""
        assert truncate_text("short", 100) == "short"

    def test_truncate_with_default_max(self):
        """默认 max_length"""
        result = truncate_text("a" * 300)
        # max_length=200, suffix="..." (3 chars), so first 197 chars + "..." = 200
        assert len(result) == 200
        assert result.endswith("...")

    def test_truncate_with_custom_max(self):
        """自定义 max_length"""
        result = truncate_text("hello world", 5)
        # max=5, suffix=3 chars, so first 2 chars + "..." = 5
        assert result == "he..."

    def test_truncate_with_custom_suffix(self):
        """自定义 suffix"""
        result = truncate_text("hello world", 5, suffix=">>")
        # max=5, suffix=2 chars, so first 3 chars + ">>" = 5
        assert result == "hel>>"

    def test_exact_length(self):
        """刚好等于 max_length"""
        text = "a" * 100
        assert truncate_text(text, 100) == text

    def test_truncate_preserves_start(self):
        """截断保留开头"""
        text = "abcdefghij"
        result = truncate_text(text, 5)
        assert result.startswith("ab")
        assert len(result) == 5

    def test_truncate_chinese(self):
        """截断中文（按字符数）"""
        text = "你好世界这是测试字符串"
        result = truncate_text(text, 5)
        # 5 个字符 + "..." = 6
        assert "..." in result
        # 总字符数
        assert len(result) <= 6

    def test_truncate_empty(self):
        """空字符串"""
        assert truncate_text("", 100) == ""