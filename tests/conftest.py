"""
tests/conftest.py

Pytest 配置和标记定义

文件功能：定义 pytest 全局配置、标记和收集忽略规则
"""

collect_ignore = [
    "run_tests.py",
    "benchmark_sql_fingerprint.py",
    "benchmark_sql_master.py",
]


def pytest_configure(config):
    """注册自定义标记"""
    config.addinivalue_line("markers", "integration: 集成测试标记")
    config.addinivalue_line("markers", "benchmark: 性能基准测试标记")
