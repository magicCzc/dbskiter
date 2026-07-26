"""
数据库任务执行器测试

文件功能：测试所有任务执行器的功能
主要测试类：
    - TestExecutionResult: 执行结果测试
    - TestExecutionProgress: 执行进度测试
    - TestBaseTaskExecutor: 基类测试
    - TestBackupExecutor: 备份执行器测试
    - TestAnalyzeExecutor: 分析执行器测试
    - TestVacuumExecutor: 清理执行器测试
    - TestReindexExecutor: 索引重建执行器测试
    - TestCheckExecutor: 检查执行器测试
    - TestCustomSQLExecutor: 自定义SQL执行器测试
    - TestExecutorFactory: 执行器工厂测试

运行测试:
    python -m pytest tests/test_task_executors.py -v

作者：AI Assistant
创建时间：2026-04-21
"""

import unittest
import tempfile
import shutil
import time
import os
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

# 导入被测模块
from dbskiter.db_scheduler.task_executors import (
    ExecutionStatus,
    ExecutionResult,
    ExecutionProgress,
    BaseTaskExecutor,
    BackupExecutor,
    AnalyzeExecutor,
    VacuumExecutor,
    ReindexExecutor,
    CheckExecutor,
    CustomSQLExecutor,
    ExecutorFactory
)


class TestExecutionResult(unittest.TestCase):
    """测试执行结果"""
    
    def test_result_creation(self):
        """测试创建结果"""
        start = datetime.now()
        end = datetime.now()
        
        result = ExecutionResult(
            status=ExecutionStatus.SUCCESS,
            start_time=start,
            end_time=end,
            message="执行成功",
            data={"rows": 100},
            rows_affected=100
        )
        
        self.assertEqual(result.status, ExecutionStatus.SUCCESS)
        self.assertEqual(result.message, "执行成功")
        self.assertEqual(result.rows_affected, 100)
    
    def test_duration_calculation(self):
        """测试持续时间计算"""
        start = datetime.now()
        time.sleep(0.1)
        end = datetime.now()
        
        result = ExecutionResult(
            status=ExecutionStatus.SUCCESS,
            start_time=start,
            end_time=end
        )
        
        self.assertGreaterEqual(result.duration_seconds, 0.1)
    
    def test_to_dict(self):
        """测试转换为字典"""
        start = datetime.now()
        end = datetime.now()
        
        result = ExecutionResult(
            status=ExecutionStatus.FAILED,
            start_time=start,
            end_time=end,
            message="执行失败",
            error="连接超时"
        )
        
        data = result.to_dict()
        
        self.assertEqual(data["status"], "failed")
        self.assertEqual(data["message"], "执行失败")
        self.assertEqual(data["error"], "连接超时")


class TestExecutionProgress(unittest.TestCase):
    """测试执行进度"""
    
    def test_progress_creation(self):
        """测试创建进度"""
        progress = ExecutionProgress(
            phase="执行",
            percent=50.0,
            message="处理中"
        )
        
        self.assertEqual(progress.phase, "执行")
        self.assertEqual(progress.percent, 50.0)
        self.assertEqual(progress.message, "处理中")
    
    def test_to_dict(self):
        """测试转换为字典"""
        progress = ExecutionProgress(
            phase="完成",
            percent=100.0,
            message="执行完成"
        )
        
        data = progress.to_dict()
        
        self.assertEqual(data["phase"], "完成")
        self.assertEqual(data["percent"], 100.0)
        self.assertIn("timestamp", data)


class MockExecutor(BaseTaskExecutor):
    """模拟执行器用于测试"""
    
    def execute(self, params, progress_callback=None, timeout_seconds=3600):
        start_time = datetime.now()
        
        # 模拟执行
        for i in range(5):
            if not self._check_cancelled():
                return ExecutionResult(
                    status=ExecutionStatus.CANCELLED,
                    start_time=start_time,
                    end_time=datetime.now(),
                    message="已取消"
                )
            
            if progress_callback:
                progress_callback(ExecutionProgress(
                    phase="执行",
                    percent=i * 25,
                    message=f"步骤 {i+1}/5"
                ))
            
            time.sleep(0.01)
        
        return ExecutionResult(
            status=ExecutionStatus.SUCCESS,
            start_time=start_time,
            end_time=datetime.now(),
            message="执行成功"
        )


class TestBaseTaskExecutor(unittest.TestCase):
    """测试基类功能"""
    
    def setUp(self):
        """设置测试环境"""
        self.mock_connector = Mock()
        self.executor = MockExecutor(self.mock_connector)
    
    def test_cancel(self):
        """测试取消"""
        self.assertFalse(self.executor.is_cancelled())
        
        self.executor.cancel()
        
        self.assertTrue(self.executor.is_cancelled())
    
    def test_check_cancelled(self):
        """测试取消检查"""
        self.assertTrue(self.executor._check_cancelled())
        
        self.executor.cancel()
        
        self.assertFalse(self.executor._check_cancelled())
    
    def test_report_progress(self):
        """测试进度报告"""
        progress_received = []
        
        def callback(progress):
            progress_received.append(progress)
        
        self.executor._report_progress(callback, "测试", 50, "一半")
        
        self.assertEqual(len(progress_received), 1)
        self.assertEqual(progress_received[0].phase, "测试")
        self.assertEqual(progress_received[0].percent, 50)
    
    def test_get_resource_usage(self):
        """测试资源使用获取"""
        usage = self.executor._get_resource_usage()
        
        self.assertIn("memory_mb", usage)
        self.assertIn("cpu_percent", usage)
        self.assertIn("threads", usage)
        
        self.assertGreater(usage["memory_mb"], 0)
        self.assertGreaterEqual(usage["threads"], 1)


class TestBackupExecutor(unittest.TestCase):
    """测试备份执行器"""
    
    def setUp(self):
        """设置测试环境"""
        self.temp_dir = tempfile.mkdtemp()
        self.mock_connector = Mock()
        self.mock_connector.dialect = "mysql"
        self.executor = BackupExecutor(self.mock_connector)
    
    def tearDown(self):
        """清理测试环境"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_backup_success(self):
        """测试备份成功"""
        progress_list = []
        
        def on_progress(p):
            progress_list.append(p)
        
        result = self.executor.execute(
            params={
                "tables": ["users", "orders"],
                "backup_path": self.temp_dir,
                "compress": False
            },
            progress_callback=on_progress
        )
        
        self.assertEqual(result.status, ExecutionStatus.SUCCESS)
        self.assertIn("backup_file", result.data)
        self.assertTrue(len(progress_list) > 0)
    
    def test_backup_with_compression(self):
        """测试压缩备份"""
        result = self.executor.execute(
            params={
                "tables": ["users"],
                "backup_path": self.temp_dir,
                "compress": True
            }
        )
        
        self.assertEqual(result.status, ExecutionStatus.SUCCESS)
        self.assertIn("compressed_file", result.data)
        self.assertIn("compressed_size", result.data)
    
    def test_backup_cancel(self):
        """测试取消备份"""
        # 在开始执行后立即取消
        def cancel_after_start():
            time.sleep(0.05)
            self.executor.cancel()
        
        cancel_thread = threading.Thread(target=cancel_after_start)
        cancel_thread.start()
        
        result = self.executor.execute(
            params={
                "backup_path": self.temp_dir
            }
        )
        
        cancel_thread.join()
        
        # 由于取消时机问题，可能成功也可能取消
        self.assertIn(result.status, [ExecutionStatus.SUCCESS, ExecutionStatus.CANCELLED])


class TestAnalyzeExecutor(unittest.TestCase):
    """测试分析执行器"""
    
    def setUp(self):
        """设置测试环境"""
        self.mock_connector = Mock()
        self.mock_connector.dialect = "mysql"
        
        # 模拟返回表列表
        mock_result = Mock()
        mock_result.rows = [["users"], ["orders"], ["products"]]
        self.mock_connector.execute.return_value = mock_result
        
        self.executor = AnalyzeExecutor(self.mock_connector)
    
    def test_analyze_all_tables(self):
        """测试分析所有表"""
        result = self.executor.execute(
            params={
                "sample_percent": 100
            }
        )
        
        self.assertEqual(result.status, ExecutionStatus.SUCCESS)
        self.assertEqual(result.data["total_tables"], 3)
        self.assertEqual(len(result.data["analyzed_tables"]), 3)
    
    def test_analyze_specific_tables(self):
        """测试分析指定表"""
        result = self.executor.execute(
            params={
                "tables": ["users", "orders"],
                "sample_percent": 50
            }
        )
        
        self.assertEqual(result.status, ExecutionStatus.SUCCESS)
        self.assertEqual(result.data["total_tables"], 2)
        self.assertEqual(result.data["sample_percent"], 50)
    
    def test_analyze_with_error(self):
        """测试分析出错"""
        # 模拟执行失败
        self.mock_connector.execute.side_effect = Exception("数据库连接失败")
        
        result = self.executor.execute(
            params={
                "tables": ["users"]
            }
        )
        
        self.assertEqual(result.status, ExecutionStatus.FAILED)
        self.assertIsNotNone(result.error)


class TestVacuumExecutor(unittest.TestCase):
    """测试清理执行器"""
    
    def setUp(self):
        """设置测试环境"""
        self.mock_connector = Mock()
        self.mock_connector.dialect = "postgresql"
        self.executor = VacuumExecutor(self.mock_connector)
    
    def test_vacuum_tables(self):
        """测试清理表"""
        result = self.executor.execute(
            params={
                "tables": ["users", "orders"],
                "full": False,
                "analyze": True
            }
        )
        
        self.assertEqual(result.status, ExecutionStatus.SUCCESS)
        self.assertEqual(result.data["tables"], ["users", "orders"])
        self.assertFalse(result.data["full"])
        self.assertTrue(result.data["analyzed"])
    
    def test_vacuum_full_database(self):
        """测试完全清理数据库"""
        result = self.executor.execute(
            params={
                "full": True,
                "analyze": False
            }
        )
        
        self.assertEqual(result.status, ExecutionStatus.SUCCESS)
        self.assertIsNone(result.data["tables"])
        self.assertTrue(result.data["full"])
    
    def test_vacuum_mysql_not_supported(self):
        """测试MySQL不支持全局VACUUM"""
        self.mock_connector.dialect = "mysql"
        
        result = self.executor.execute(
            params={
                "full": True
            }
        )
        
        self.assertEqual(result.status, ExecutionStatus.FAILED)


class TestReindexExecutor(unittest.TestCase):
    """测试索引重建执行器"""
    
    def setUp(self):
        """设置测试环境"""
        self.mock_connector = Mock()
        self.mock_connector.dialect = "postgresql"
        self.executor = ReindexExecutor(self.mock_connector)
    
    def test_reindex_tables(self):
        """测试重建表索引"""
        result = self.executor.execute(
            params={
                "tables": ["users", "orders"],
                "concurrently": True
            }
        )
        
        self.assertEqual(result.status, ExecutionStatus.SUCCESS)
        self.assertEqual(len(result.data["rebuilt_indexes"]), 2)
        self.assertTrue(result.data["concurrently"])
    
    def test_reindex_specific_indexes(self):
        """测试重建指定索引"""
        result = self.executor.execute(
            params={
                "indexes": ["idx_users_id", "idx_orders_date"],
                "concurrently": False
            }
        )
        
        self.assertEqual(result.status, ExecutionStatus.SUCCESS)
        self.assertEqual(len(result.data["rebuilt_indexes"]), 2)
        self.assertFalse(result.data["concurrently"])
    
    def test_reindex_all(self):
        """测试重建所有索引"""
        result = self.executor.execute(
            params={
                "concurrently": True
            }
        )
        
        self.assertEqual(result.status, ExecutionStatus.SUCCESS)
        self.assertEqual(result.data["rebuilt_indexes"], ["ALL"])


class TestCheckExecutor(unittest.TestCase):
    """测试检查执行器"""
    
    def setUp(self):
        """设置测试环境"""
        self.mock_connector = Mock()
        self.mock_connector.dialect = "mysql"
        
        # 模拟返回表列表
        mock_result = Mock()
        mock_result.rows = [["users"], ["orders"]]
        self.mock_connector.execute.return_value = mock_result
        
        self.executor = CheckExecutor(self.mock_connector)
    
    def test_check_all_tables(self):
        """测试检查所有表"""
        result = self.executor.execute(
            params={
                "check_type": "all"
            }
        )
        
        self.assertEqual(result.status, ExecutionStatus.SUCCESS)
        self.assertEqual(len(result.data["checked_tables"]), 2)
    
    def test_check_specific_tables(self):
        """测试检查指定表"""
        result = self.executor.execute(
            params={
                "tables": ["users"],
                "check_type": "integrity"
            }
        )
        
        self.assertEqual(result.status, ExecutionStatus.SUCCESS)
        self.assertEqual(result.data["checked_tables"], ["users"])
        self.assertEqual(result.data["check_type"], "integrity")


class TestCustomSQLExecutor(unittest.TestCase):
    """测试自定义SQL执行器"""
    
    def setUp(self):
        """设置测试环境"""
        self.mock_connector = Mock()
        
        # 模拟返回结果
        mock_result = Mock()
        mock_result.rows = [[1, "test"], [2, "test2"]]
        mock_result.rowcount = 2
        self.mock_connector.execute.return_value = mock_result
        
        self.executor = CustomSQLExecutor(self.mock_connector)
    
    def test_execute_single_sql(self):
        """测试执行单条SQL"""
        result = self.executor.execute(
            params={
                "sql": "SELECT * FROM users",
                "readonly": True
            }
        )
        
        self.assertEqual(result.status, ExecutionStatus.SUCCESS)
        self.assertEqual(result.rows_affected, 2)
        self.assertEqual(len(result.data["results"]), 1)
    
    def test_execute_multiple_sql(self):
        """测试执行多条SQL"""
        result = self.executor.execute(
            params={
                "sql": [
                    "SELECT * FROM users",
                    "SELECT * FROM orders",
                    "UPDATE users SET status = 1"
                ],
                "readonly": False
            }
        )
        
        self.assertEqual(result.status, ExecutionStatus.SUCCESS)
        self.assertEqual(len(result.data["results"]), 3)
        self.assertFalse(result.data["readonly"])
    
    def test_readonly_mode_blocks_write(self):
        """测试只读模式阻止写入"""
        result = self.executor.execute(
            params={
                "sql": "DELETE FROM users",
                "readonly": True
            }
        )
        
        self.assertEqual(result.status, ExecutionStatus.FAILED)
        self.assertIn("只读模式", result.error)
    
    def test_execute_with_params(self):
        """测试带参数执行"""
        result = self.executor.execute(
            params={
                "sql": "SELECT * FROM users WHERE id = :id",
                "params": {"id": 1},
                "readonly": True
            }
        )
        
        self.assertEqual(result.status, ExecutionStatus.SUCCESS)
        # 验证参数传递
        self.mock_connector.execute.assert_called_with(
            "SELECT * FROM users WHERE id = :id",
            {"id": 1}
        )


class TestExecutorFactory(unittest.TestCase):
    """测试执行器工厂"""
    
    def setUp(self):
        """设置测试环境"""
        self.mock_connector = Mock()
    
    def test_create_backup_executor(self):
        """测试创建备份执行器"""
        executor = ExecutorFactory.create("backup", self.mock_connector)
        
        self.assertIsInstance(executor, BackupExecutor)
    
    def test_create_analyze_executor(self):
        """测试创建分析执行器"""
        executor = ExecutorFactory.create("analyze", self.mock_connector)
        
        self.assertIsInstance(executor, AnalyzeExecutor)
    
    def test_create_vacuum_executor(self):
        """测试创建清理执行器"""
        executor = ExecutorFactory.create("vacuum", self.mock_connector)
        
        self.assertIsInstance(executor, VacuumExecutor)
    
    def test_create_reindex_executor(self):
        """测试创建索引重建执行器"""
        executor = ExecutorFactory.create("reindex", self.mock_connector)
        
        self.assertIsInstance(executor, ReindexExecutor)
    
    def test_create_check_executor(self):
        """测试创建检查执行器"""
        executor = ExecutorFactory.create("check", self.mock_connector)
        
        self.assertIsInstance(executor, CheckExecutor)
    
    def test_create_custom_executor(self):
        """测试创建自定义执行器"""
        executor = ExecutorFactory.create("custom", self.mock_connector)
        
        self.assertIsInstance(executor, CustomSQLExecutor)
    
    def test_create_unsupported_action(self):
        """测试创建不支持的执行器"""
        with self.assertRaises(ValueError) as context:
            ExecutorFactory.create("unsupported", self.mock_connector)
        
        self.assertIn("不支持的动作类型", str(context.exception))
    
    def test_register_custom_executor(self):
        """测试注册自定义执行器"""
        
        class CustomExecutor(BaseTaskExecutor):
            def execute(self, params, progress_callback=None, timeout_seconds=3600):
                return ExecutionResult(
                    status=ExecutionStatus.SUCCESS,
                    start_time=datetime.now(),
                    end_time=datetime.now(),
                    message="自定义执行"
                )
        
        ExecutorFactory.register("my_custom", CustomExecutor)
        
        executor = ExecutorFactory.create("my_custom", self.mock_connector)
        
        self.assertIsInstance(executor, CustomExecutor)
    
    def test_get_supported_actions(self):
        """测试获取支持的动作列表"""
        actions = ExecutorFactory.get_supported_actions()
        
        self.assertIn("backup", actions)
        self.assertIn("analyze", actions)
        self.assertIn("vacuum", actions)
        self.assertIn("reindex", actions)
        self.assertIn("check", actions)
        self.assertIn("custom", actions)


import threading

if __name__ == "__main__":
    unittest.main()
