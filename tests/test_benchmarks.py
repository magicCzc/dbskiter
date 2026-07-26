"""
性能基准测试（pytest 封装）

将现有的 benchmark 脚本包装为 pytest 测试用例，
便于在 CI 中追踪性能变化。
"""

import pytest
from .benchmark_sql_fingerprint import PerformanceBenchmark as FingerprintBenchmark


class TestBenchmarkSQLFingerprint:
    """SQL指纹生成性能基准测试"""

    @pytest.mark.benchmark
    def test_simple_sql(self):
        """简单SQL: < 5ms"""
        bm = FingerprintBenchmark()
        bm.benchmark_simple_sql(iterations=1000)
        result = bm.results[-1]
        assert result["avg_time_ms"] < 5.0, f"简单SQL耗时 {result['avg_time_ms']:.3f}ms"

    @pytest.mark.benchmark
    def test_complex_sql(self):
        """复杂SQL: < 20ms"""
        bm = FingerprintBenchmark()
        bm.benchmark_complex_sql(iterations=500)
        result = bm.results[-1]
        assert result["avg_time_ms"] < 20.0, f"复杂SQL耗时 {result['avg_time_ms']:.3f}ms"

    @pytest.mark.benchmark
    def test_long_sql(self):
        """长SQL: < 50ms"""
        bm = FingerprintBenchmark()
        bm.benchmark_long_sql()
        result = bm.results[-1]
        assert result["avg_time_ms"] < 50.0, f"长SQL耗时 {result['avg_time_ms']:.3f}ms"

    @pytest.mark.benchmark
    def test_batch_aggregation(self):
        """批量聚合: < 5s"""
        bm = FingerprintBenchmark()
        bm.benchmark_batch_aggregation()
        result = bm.results[-1]
        assert result["total_time"] < 5.0, f"批量聚合耗时 {result['total_time']:.3f}s"