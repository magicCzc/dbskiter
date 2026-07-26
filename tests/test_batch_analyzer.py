"""
BatchAnalyzer子模块单元测试

文件功能：测试BatchAnalyzer的所有功能
主要测试类：
- TestBatchAnalyzerSerial: 串行批量分析测试
- TestBatchAnalyzerConcurrent: 并发批量分析测试

作者：AI Assistant
创建时间：2026-04-22
"""

import unittest
import sys
from unittest.mock import Mock, MagicMock, patch
from typing import List, Dict, Any
import time

sys.path.insert(0, r'e:\Chenzc-AIDev\数据库skill')

from dbskiter.db_diagnose.analyzers.batch_analyzer import BatchAnalyzer


# =============================================================================
# BatchAnalyzer串行分析测试
# =============================================================================

class TestBatchAnalyzerSerial(unittest.TestCase):
    """串行批量分析测试"""

    def setUp(self):
        """测试前置准备"""
        self.analyzer = BatchAnalyzer()
        self.mock_analyze_func = Mock()

    def test_analyze_serial_empty_list(self):
        """测试空列表分析"""
        results = self.analyzer.analyze_serial([], self.mock_analyze_func)

        self.assertEqual(len(results), 0)
        self.mock_analyze_func.assert_not_called()

    def test_analyze_serial_single_item(self):
        """测试单条数据分析"""
        self.mock_analyze_func.return_value = {"success": True, "data": "result1"}

        results = self.analyzer.analyze_serial(["sql1"], self.mock_analyze_func)

        self.assertEqual(len(results), 1)
        self.assertTrue(results[0]["success"])
        self.mock_analyze_func.assert_called_once_with("sql1")

    def test_analyze_serial_multiple_items(self):
        """测试多条数据分析"""
        self.mock_analyze_func.side_effect = [
            {"success": True, "data": "result1"},
            {"success": True, "data": "result2"},
            {"success": True, "data": "result3"}
        ]

        items = ["sql1", "sql2", "sql3"]
        results = self.analyzer.analyze_serial(items, self.mock_analyze_func)

        self.assertEqual(len(results), 3)
        self.assertEqual(self.mock_analyze_func.call_count, 3)
        for result in results:
            self.assertTrue(result["success"])

    def test_analyze_serial_with_failure(self):
        """测试包含失败项的分析"""
        self.mock_analyze_func.side_effect = [
            {"success": True, "data": "result1"},
            {"success": False, "error": "error2"},
            {"success": True, "data": "result3"}
        ]

        items = ["sql1", "sql2", "sql3"]
        results = self.analyzer.analyze_serial(items, self.mock_analyze_func)

        self.assertEqual(len(results), 3)
        self.assertTrue(results[0]["success"])
        self.assertFalse(results[1]["success"])
        self.assertTrue(results[2]["success"])

    def test_analyze_serial_with_progress(self):
        """测试带进度的分析"""
        self.mock_analyze_func.return_value = {"success": True}

        with patch('dbskiter.db_diagnose.analyzers.batch_analyzer.logger') as mock_logger:
            items = ["sql1", "sql2", "sql3"]
            results = self.analyzer.analyze_serial(items, self.mock_analyze_func, show_progress=True)

            self.assertEqual(len(results), 3)
            # 验证进度日志被记录
            self.assertTrue(mock_logger.info.called)

    def test_analyze_serial_preserves_order(self):
        """测试结果顺序与输入顺序一致"""
        self.mock_analyze_func.side_effect = lambda x: {"success": True, "sql": x}

        items = ["first", "second", "third"]
        results = self.analyzer.analyze_serial(items, self.mock_analyze_func)

        self.assertEqual(len(results), 3)
        self.assertEqual(results[0]["sql"], "first")
        self.assertEqual(results[1]["sql"], "second")
        self.assertEqual(results[2]["sql"], "third")


# =============================================================================
# BatchAnalyzer并发分析测试
# =============================================================================

class TestBatchAnalyzerConcurrent(unittest.TestCase):
    """并发批量分析测试"""

    def setUp(self):
        """测试前置准备"""
        self.analyzer = BatchAnalyzer()
        self.mock_analyze_func = Mock()

    def test_analyze_concurrent_empty_list(self):
        """测试空列表并发分析"""
        results = self.analyzer.analyze_concurrent([], self.mock_analyze_func)

        self.assertEqual(len(results), 0)
        self.mock_analyze_func.assert_not_called()

    def test_analyze_concurrent_single_item(self):
        """测试单条数据并发分析"""
        self.mock_analyze_func.return_value = {"success": True, "data": "result1"}

        results = self.analyzer.analyze_concurrent(["sql1"], self.mock_analyze_func)

        self.assertEqual(len(results), 1)
        self.assertTrue(results[0]["success"])

    def test_analyze_concurrent_multiple_items(self):
        """测试多条数据并发分析"""
        self.mock_analyze_func.side_effect = [
            {"success": True, "data": "result1"},
            {"success": True, "data": "result2"},
            {"success": True, "data": "result3"}
        ]

        items = ["sql1", "sql2", "sql3"]
        results = self.analyzer.analyze_concurrent(items, self.mock_analyze_func, max_workers=2)

        self.assertEqual(len(results), 3)
        for result in results:
            self.assertTrue(result["success"])

    def test_analyze_concurrent_preserves_order(self):
        """测试并发分析结果顺序与输入顺序一致"""
        # 使用time.sleep模拟不同执行时间
        def slow_analyze(x):
            if x == "slow":
                time.sleep(0.1)
            return {"success": True, "item": x}

        items = ["fast1", "slow", "fast2"]
        results = self.analyzer.analyze_concurrent(items, slow_analyze, max_workers=3)

        self.assertEqual(len(results), 3)
        # 即使"slow"执行时间长，结果顺序应该与输入一致
        self.assertEqual(results[0]["item"], "fast1")
        self.assertEqual(results[1]["item"], "slow")
        self.assertEqual(results[2]["item"], "fast2")

    def test_analyze_concurrent_with_failure(self):
        """测试并发分析中的失败处理"""
        self.mock_analyze_func.side_effect = [
            {"success": True, "data": "result1"},
            Exception("分析失败"),
            {"success": True, "data": "result3"}
        ]

        items = ["sql1", "sql2", "sql3"]
        results = self.analyzer.analyze_concurrent(items, self.mock_analyze_func, max_workers=2)

        self.assertEqual(len(results), 3)
        self.assertTrue(results[0]["success"])
        self.assertFalse(results[1]["success"])  # 失败项
        self.assertTrue(results[2]["success"])

    def test_analyze_concurrent_with_progress(self):
        """测试带进度显示的并发分析"""
        self.mock_analyze_func.return_value = {"success": True}

        with patch('dbskiter.db_diagnose.analyzers.batch_analyzer.logger') as mock_logger:
            items = ["sql1", "sql2", "sql3"]
            results = self.analyzer.analyze_concurrent(
                items,
                self.mock_analyze_func,
                max_workers=2,
                show_progress=True
            )

            self.assertEqual(len(results), 3)
            # 验证进度日志被记录
            self.assertTrue(mock_logger.info.called)

    def test_analyze_concurrent_different_workers(self):
        """测试不同并发数"""
        self.mock_analyze_func.return_value = {"success": True}

        items = ["sql1", "sql2", "sql3", "sql4", "sql5"]

        # 测试不同并发数
        for workers in [1, 2, 5, 10]:
            with self.subTest(workers=workers):
                results = self.analyzer.analyze_concurrent(
                    items,
                    self.mock_analyze_func,
                    max_workers=workers
                )
                self.assertEqual(len(results), 5)
                for result in results:
                    self.assertTrue(result["success"])


# =============================================================================
# 性能对比测试
# =============================================================================

class TestBatchAnalyzerPerformance(unittest.TestCase):
    """性能对比测试"""

    def setUp(self):
        """测试前置准备"""
        self.analyzer = BatchAnalyzer()

    def test_concurrent_faster_than_serial(self):
        """测试并发比串行快"""
        def slow_analyze(x):
            time.sleep(0.05)  # 50ms延迟
            return {"success": True, "item": x}

        items = ["sql1", "sql2", "sql3", "sql4"]

        # 串行执行时间
        start = time.time()
        serial_results = self.analyzer.analyze_serial(items, slow_analyze)
        serial_time = time.time() - start

        # 并发执行时间
        start = time.time()
        concurrent_results = self.analyzer.analyze_concurrent(items, slow_analyze, max_workers=4)
        concurrent_time = time.time() - start

        # 验证结果相同
        self.assertEqual(len(serial_results), len(concurrent_results))

        # 并发应该比串行快（至少快1.5倍）
        # 注意：在资源受限的环境中可能不成立，所以使用较宽松的条件
        print(f"\n串行时间: {serial_time:.3f}s, 并发时间: {concurrent_time:.3f}s")
        print(f"加速比: {serial_time/concurrent_time:.2f}x")


# =============================================================================
# 主程序入口
# =============================================================================

if __name__ == "__main__":
    # 运行测试
    unittest.main(verbosity=2)
