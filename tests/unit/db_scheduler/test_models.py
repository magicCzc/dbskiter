"""
db_scheduler/test_models.py
数据模型单元测试

测试范围:
    - ErrorCode错误码体系
    - ErrorMessage错误消息
    - 所有数据类(BackupResult, ScheduledTask等)
    - 枚举类型验证

版本: 1.0.0
作者: AI Assistant
创建时间: 2026-04-23
"""

import unittest
from datetime import datetime, timedelta
from typing import Dict, Any

from dbskiter.db_scheduler.models import (
    ErrorCode,
    ErrorMessage,
    TaskType,
    TaskStatus,
    TaskPriority,
    WorkflowStatus,
    BackupResult,
    ScheduledTask,
    TaskResult,
    TaskNode,
    TaskGraph,
    PrioritizedTask,
)


class TestErrorCode(unittest.TestCase):
    """测试错误码体系"""

    def test_error_code_format(self):
        """测试错误码格式正确"""
        # 所有错误码应该以SCH开头
        error_codes = [
            ErrorCode.SUCCESS,
            ErrorCode.UNKNOWN_ERROR,
            ErrorCode.BACKUP_FAILED,
            ErrorCode.TASK_TIMEOUT,
            ErrorCode.WORKFLOW_INVALID,
        ]

        for code in error_codes:
            self.assertTrue(code.startswith("SCH"))
            self.assertEqual(len(code), 9)  # SCH000000格式

    def test_error_code_uniqueness(self):
        """测试错误码唯一性"""
        error_codes = [
            ErrorCode.SUCCESS,
            ErrorCode.UNKNOWN_ERROR,
            ErrorCode.INVALID_PARAM,
            ErrorCode.BACKUP_FAILED,
            ErrorCode.BACKUP_TIMEOUT,
            ErrorCode.TASK_EXECUTION_FAILED,
            ErrorCode.WORKFLOW_CYCLE_DETECTED,
        ]

        self.assertEqual(len(error_codes), len(set(error_codes)))


class TestErrorMessage(unittest.TestCase):
    """测试错误消息映射"""

    def test_get_message_exists(self):
        """测试获取存在的错误消息"""
        msg = ErrorMessage.get_message(ErrorCode.SUCCESS)
        self.assertEqual(msg, "操作成功")

        msg = ErrorMessage.get_message(ErrorCode.BACKUP_FAILED)
        self.assertEqual(msg, "备份失败")

    def test_get_message_not_exists(self):
        """测试获取不存在的错误消息"""
        msg = ErrorMessage.get_message("SCH999999")
        self.assertIn("未知错误码", msg)


class TestTaskType(unittest.TestCase):
    """测试任务类型枚举"""

    def test_task_type_values(self):
        """测试任务类型值"""
        self.assertEqual(TaskType.BACKUP.value, "backup")
        self.assertEqual(TaskType.BACKUP_INCREMENTAL.value, "backup_incremental")
        self.assertEqual(TaskType.VACUUM.value, "vacuum")
        self.assertEqual(TaskType.ANALYZE.value, "analyze")
        self.assertEqual(TaskType.REINDEX.value, "reindex")


class TestTaskStatus(unittest.TestCase):
    """测试任务状态枚举"""

    def test_task_status_values(self):
        """测试任务状态值"""
        self.assertEqual(TaskStatus.PENDING.value, "pending")
        self.assertEqual(TaskStatus.RUNNING.value, "running")
        self.assertEqual(TaskStatus.SUCCESS.value, "success")
        self.assertEqual(TaskStatus.FAILED.value, "failed")
        self.assertEqual(TaskStatus.TIMEOUT.value, "timeout")


class TestTaskPriority(unittest.TestCase):
    """测试任务优先级枚举"""

    def test_priority_order(self):
        """测试优先级顺序(数值越小优先级越高)"""
        self.assertLess(TaskPriority.CRITICAL.value, TaskPriority.HIGH.value)
        self.assertLess(TaskPriority.HIGH.value, TaskPriority.MEDIUM.value)
        self.assertLess(TaskPriority.MEDIUM.value, TaskPriority.LOW.value)


class TestBackupResult(unittest.TestCase):
    """测试备份结果数据类"""

    def test_backup_result_success(self):
        """测试成功的备份结果"""
        result = BackupResult(
            success=True,
            backup_id="backup_123",
            file_path="/backups/backup_123.sql",
            file_size=1024,
            duration_ms=1000,
            tables=["users", "orders"],
            backup_type="full"
        )

        self.assertTrue(result.success)
        self.assertEqual(result.backup_id, "backup_123")
        self.assertEqual(result.file_size, 1024)

    def test_backup_result_failure(self):
        """测试失败的备份结果"""
        result = BackupResult(
            success=False,
            backup_id="backup_456",
            file_path="",
            file_size=0,
            duration_ms=0,
            error="磁盘空间不足"
        )

        self.assertFalse(result.success)
        self.assertIsNotNone(result.error)

    def test_backup_result_to_dict(self):
        """测试备份结果转字典"""
        result = BackupResult(
            success=True,
            backup_id="backup_789",
            file_path="/backups/test.sql",
            file_size=2048,
            duration_ms=2000,
            tables=["table1"],
            backup_type="incremental"
        )

        data = result.to_dict()
        self.assertIsInstance(data, dict)
        self.assertEqual(data["backup_id"], "backup_789")
        self.assertEqual(data["backup_type"], "incremental")


class TestScheduledTask(unittest.TestCase):
    """测试定时任务数据类"""

    def test_scheduled_task_creation(self):
        """测试创建定时任务"""
        task = ScheduledTask(
            task_id="task_001",
            name="daily_backup",
            task_type=TaskType.BACKUP,
            schedule="0 2 * * *",
            params={"backup_type": "full"},
            priority=TaskPriority.HIGH
        )

        self.assertEqual(task.task_id, "task_001")
        self.assertEqual(task.name, "daily_backup")
        self.assertEqual(task.task_type, TaskType.BACKUP)
        self.assertTrue(task.enabled)
        self.assertEqual(task.retry_count, 0)
        self.assertEqual(task.max_retries, 3)

    def test_scheduled_task_to_dict(self):
        """测试定时任务转字典"""
        now = datetime.now()
        task = ScheduledTask(
            task_id="task_002",
            name="hourly_check",
            task_type=TaskType.CHECK,
            schedule="0 * * * *",
            next_run=now,
            created_at=now
        )

        data = task.to_dict()
        self.assertIsInstance(data, dict)
        self.assertEqual(data["task_id"], "task_002")
        self.assertEqual(data["task_type"], "check")
        self.assertIn("created_at", data)


class TestTaskResult(unittest.TestCase):
    """测试任务执行结果数据类"""

    def test_task_result_success(self):
        """测试成功的任务结果"""
        start = datetime.now()
        end = start + timedelta(seconds=5)

        result = TaskResult(
            task_id="task_003",
            task_name="test_task",
            status=TaskStatus.SUCCESS,
            start_time=start,
            end_time=end,
            result={"data": "test"},
            error_code=ErrorCode.SUCCESS
        )

        self.assertEqual(result.status, TaskStatus.SUCCESS)
        self.assertEqual(result.duration_ms, 5000)
        self.assertEqual(result.error_code, ErrorCode.SUCCESS)

    def test_task_result_failure(self):
        """测试失败的任务结果"""
        start = datetime.now()
        end = start + timedelta(seconds=2)

        result = TaskResult(
            task_id="task_004",
            task_name="failed_task",
            status=TaskStatus.FAILED,
            start_time=start,
            end_time=end,
            error="执行失败",
            error_code=ErrorCode.TASK_EXECUTION_FAILED
        )

        self.assertEqual(result.status, TaskStatus.FAILED)
        self.assertEqual(result.error, "执行失败")

    def test_task_result_to_dict(self):
        """测试任务结果转字典"""
        start = datetime.now()
        end = start + timedelta(seconds=3)

        result = TaskResult(
            task_id="task_005",
            task_name="dict_test",
            status=TaskStatus.SUCCESS,
            start_time=start,
            end_time=end,
            error_code=ErrorCode.SUCCESS
        )

        data = result.to_dict()
        self.assertIsInstance(data, dict)
        self.assertEqual(data["error_code"], ErrorCode.SUCCESS)
        self.assertIn("error_message", data)


class TestTaskNode(unittest.TestCase):
    """测试DAG任务节点"""

    def test_task_node_creation(self):
        """测试创建任务节点"""
        node = TaskNode(
            task_id="node_1",
            task_type=TaskType.BACKUP,
            params={"tables": ["users"]},
            priority=TaskPriority.HIGH
        )

        self.assertEqual(node.task_id, "node_1")
        self.assertEqual(len(node.depends_on), 0)

    def test_task_node_dependency(self):
        """测试任务节点依赖"""
        node = TaskNode(
            task_id="node_2",
            task_type=TaskType.ANALYZE
        )

        node.add_dependency("node_1")
        self.assertIn("node_1", node.depends_on)

        node.add_dependency("node_1")  # 重复添加
        self.assertEqual(len(node.depends_on), 1)  # 集合去重


class TestTaskGraph(unittest.TestCase):
    """测试工作流任务图"""

    def test_task_graph_creation(self):
        """测试创建工作流图"""
        graph = TaskGraph(
            workflow_id="wf_001",
            description="测试工作流"
        )

        self.assertEqual(graph.workflow_id, "wf_001")
        self.assertEqual(graph.description, "测试工作流")
        self.assertEqual(len(graph.tasks), 0)

    def test_task_graph_add_task(self):
        """测试添加任务到工作流"""
        graph = TaskGraph(workflow_id="wf_002")

        node1 = TaskNode(task_id="task_1", task_type=TaskType.BACKUP)
        node2 = TaskNode(task_id="task_2", task_type=TaskType.ANALYZE)

        graph.add_task(node1)
        graph.add_task(node2)

        self.assertEqual(len(graph.tasks), 2)
        self.assertIn("task_1", graph.tasks)

    def test_task_graph_validate_no_cycle(self):
        """测试验证无循环依赖"""
        graph = TaskGraph(workflow_id="wf_003")

        node1 = TaskNode(task_id="task_a", task_type=TaskType.BACKUP)
        node2 = TaskNode(task_id="task_b", task_type=TaskType.ANALYZE)
        node2.add_dependency("task_a")

        graph.add_task(node1)
        graph.add_task(node2)

        self.assertTrue(graph.validate())

    def test_task_graph_validate_with_cycle(self):
        """测试验证有循环依赖"""
        graph = TaskGraph(workflow_id="wf_004")

        node1 = TaskNode(task_id="task_x", task_type=TaskType.BACKUP)
        node2 = TaskNode(task_id="task_y", task_type=TaskType.ANALYZE)

        node1.add_dependency("task_y")
        node2.add_dependency("task_x")

        graph.add_task(node1)
        graph.add_task(node2)

        self.assertFalse(graph.validate())

    def test_task_graph_get_ready_tasks(self):
        """测试获取可执行任务"""
        graph = TaskGraph(workflow_id="wf_005")

        node1 = TaskNode(task_id="task_1", task_type=TaskType.BACKUP)
        node2 = TaskNode(task_id="task_2", task_type=TaskType.ANALYZE)
        node2.add_dependency("task_1")

        graph.add_task(node1)
        graph.add_task(node2)

        # 初始时只有task_1可以执行
        ready = graph.get_ready_tasks()
        self.assertEqual(len(ready), 1)
        self.assertEqual(ready[0].task_id, "task_1")

        # 模拟task_1完成
        graph.results["task_1"] = {"success": True}

        # 现在task_2也可以执行
        ready = graph.get_ready_tasks()
        self.assertEqual(len(ready), 1)
        self.assertEqual(ready[0].task_id, "task_2")


class TestPrioritizedTask(unittest.TestCase):
    """测试带优先级的任务"""

    def test_prioritized_task_comparison(self):
        """测试优先级比较"""
        import heapq

        now = datetime.now()

        task1 = PrioritizedTask(
            priority=1,
            scheduled_time=now,
            task_id="high_priority",
            task=None
        )

        task2 = PrioritizedTask(
            priority=2,
            scheduled_time=now,
            task_id="low_priority",
            task=None
        )

        # 优先级高的应该排在前面
        self.assertLess(task1, task2)

        # 测试堆排序
        heap = [task2, task1]
        heapq.heapify(heap)

        first = heapq.heappop(heap)
        self.assertEqual(first.task_id, "high_priority")


class TestWorkflowStatus(unittest.TestCase):
    """测试工作流状态枚举"""

    def test_workflow_status_values(self):
        """测试工作流状态值"""
        self.assertEqual(WorkflowStatus.PENDING.value, "pending")
        self.assertEqual(WorkflowStatus.RUNNING.value, "running")
        self.assertEqual(WorkflowStatus.COMPLETED.value, "completed")
        self.assertEqual(WorkflowStatus.FAILED.value, "failed")


if __name__ == "__main__":
    unittest.main()
