"""
SQL语法验证测试
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dbskiter.shared.sql_fingerprint import SQLFingerprinter

def test_sql_validation():
    fp = SQLFingerprinter()
    
    # 测试1: 有效SQL
    valid_sqls = [
        "SELECT * FROM users WHERE id = 1",
        "INSERT INTO users (name) VALUES ('test')",
        "UPDATE users SET name = 'test' WHERE id = 1",
        "DELETE FROM users WHERE id = 1",
        "WITH cte AS (SELECT * FROM t) SELECT * FROM cte",
    ]
    
    for sql in valid_sqls:
        is_valid, error = fp._validate_sql_syntax(sql)
        print(f"Valid SQL: {sql[:50]}... -> {is_valid}")
        assert is_valid, f"Should be valid: {error}"
    
    # 测试2: 括号不匹配
    invalid_sqls = [
        ("SELECT * FROM (users", "括号不匹配"),
        ("SELECT * FROM users WHERE id = (1", "括号不匹配"),
        ("SELECT * FROM users) WHERE id = 1", "多余的右括号"),
    ]
    
    for sql, expected_error in invalid_sqls:
        is_valid, error = fp._validate_sql_syntax(sql)
        print(f"Invalid SQL: {sql[:50]}... -> {is_valid}, error: {error}")
        assert not is_valid, "Should be invalid"
        assert expected_error in error, f"Expected '{expected_error}' in '{error}'"
    
    # 测试3: 引号不匹配
    quote_sqls = [
        ("SELECT * FROM users WHERE name = 'test", "字符串未闭合"),
        ('SELECT * FROM users WHERE name = "test', "字符串未闭合"),
    ]
    
    for sql, expected_error in quote_sqls:
        is_valid, error = fp._validate_sql_syntax(sql)
        print(f"Quote error: {sql[:50]}... -> {is_valid}, error: {error}")
        assert not is_valid, "Should be invalid"
        assert expected_error in error, f"Expected '{expected_error}' in '{error}'"
    
    # 测试4: 无效关键字
    invalid_start = [
        ("INVALID * FROM users", "无效的SQL起始关键字"),
        ("", "SQL为空"),
    ]
    
    for sql, expected_error in invalid_start:
        is_valid, error = fp._validate_sql_syntax(sql)
        print(f"Invalid start: '{sql}' -> {is_valid}, error: {error}")
        assert not is_valid, "Should be invalid"
        assert expected_error in error, f"Expected '{expected_error}' in '{error}'"
    
    # 测试5: 完整指纹生成（带验证）
    result = fp.fingerprint("SELECT * FROM users WHERE id = 123")
    print(f"\nFingerprint with validation: {result.fingerprint}")
    assert "SELECT * FROM users WHERE id=?" == result.fingerprint
    
    print('\nAll validation tests passed!')

if __name__ == '__main__':
    test_sql_validation()
