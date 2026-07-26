"""
窗口函数替换测试
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dbskiter.shared.sql_fingerprint import SQLFingerprinter

def test_window_func():
    fp = SQLFingerprinter()
    
    # 测试1: 基本窗口函数
    sql1 = 'SELECT ROW_NUMBER() OVER (PARTITION BY dept_id ORDER BY salary DESC) as rn FROM employees'
    result1 = fp._replace_window_functions(sql1)
    print('Test 1 - Basic:', result1)
    assert '<window_func>' in result1
    
    # 测试2: 嵌套括号
    sql2 = 'SELECT SUM(x) OVER (PARTITION BY (a + b)) FROM t'
    result2 = fp._replace_window_functions(sql2)
    print('Test 2 - Nested:', result2)
    assert '<window_func>' in result2
    
    # 测试3: 多个窗口函数
    sql3 = 'SELECT ROW_NUMBER() OVER (ORDER BY a), RANK() OVER (ORDER BY b) FROM t'
    result3 = fp._replace_window_functions(sql3)
    print('Test 3 - Multiple:', result3)
    assert result3.count('<window_func>') == 2
    
    # 测试4: 完整指纹生成
    sql4 = 'SELECT id, ROW_NUMBER() OVER (PARTITION BY dept ORDER BY salary) as rn FROM employees'
    result4 = fp.fingerprint(sql4)
    print('Test 4 - Full fingerprint:', result4.fingerprint)
    assert '<window_func>' in result4.fingerprint
    
    print('\nAll tests passed!')

if __name__ == '__main__':
    test_window_func()
