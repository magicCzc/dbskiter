"""
run_tests.py

运行所有 V2 测试
"""

import sys
import os
from pathlib import Path

# 添加父目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

# V2 测试列表
V2_TESTS = [
    "test_monitor_v2.py",
    "test_diagnose_v2.py",
    "test_security_v2.py",
    "test_scheduler_v2.py",
    "test_sql_master_v2.py",
]


def run_v2_tests():
    """运行所有 V2 测试"""
    print("=" * 70)
    print("运行数据库 Skills V2 测试")
    print("=" * 70)
    
    results = []
    
    for test_file in V2_TESTS:
        print(f"\n{'='*70}")
        print(f"运行: {test_file}")
        print("=" * 70)
        
        test_path = Path(__file__).parent / test_file
        if not test_path.exists():
            print(f"[SKIP] 测试文件不存在: {test_file}")
            continue
        
        # 使用 exec 运行测试文件
        try:
            with open(test_path, 'r', encoding='utf-8') as f:
                code = f.read()
            
            # 在独立命名空间执行
            namespace = {
                '__file__': str(test_path),
                '__name__': '__main__',
            }
            exec(code, namespace)
            results.append((test_file, True, None))
            
        except Exception as e:
            print(f"[FAIL] {test_file}: {e}")
            results.append((test_file, False, str(e)))
    
    # 打印汇总
    print("\n" + "=" * 70)
    print("测试汇总")
    print("=" * 70)
    
    passed = sum(1 for _, success, _ in results if success)
    failed = sum(1 for _, success, _ in results if not success)
    
    for test_file, success, error in results:
        status = "[PASS]" if success else "[FAIL]"
        print(f"{status} {test_file}")
        if error:
            print(f"       错误: {error}")
    
    print("-" * 70)
    print(f"总计: {len(results)} 个测试")
    print(f"通过: {passed}")
    print(f"失败: {failed}")
    print("=" * 70)
    
    return failed == 0


def run_single_test(test_file: str):
    """运行单个测试文件"""
    test_path = Path(__file__).parent / test_file
    
    if not test_path.exists():
        print(f"测试文件不存在: {test_file}")
        return False
    
    print(f"运行: {test_file}")
    print("=" * 70)
    
    try:
        with open(test_path, 'r', encoding='utf-8') as f:
            code = f.read()
        
        namespace = {
            '__file__': str(test_path),
            '__name__': '__main__',
        }
        exec(code, namespace)
        return True
        
    except Exception as e:
        print(f"[FAIL] {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="运行数据库 Skills V2 测试")
    parser.add_argument(
        "--test",
        type=str,
        help="运行特定测试文件 (如: test_monitor_v2.py)"
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="列出所有可用测试"
    )
    
    args = parser.parse_args()
    
    if args.list:
        print("可用 V2 测试:")
        for test in V2_TESTS:
            print(f"  - {test}")
    elif args.test:
        success = run_single_test(args.test)
        sys.exit(0 if success else 1)
    else:
        success = run_v2_tests()
        sys.exit(0 if success else 1)
