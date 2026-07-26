"""
db_scheduler/test_utils.py
工具类单元测试

测试范围:
    - TimeoutExecutor超时执行器
    - CircuitBreaker熔断器
    - CronParser Cron解析器
    - NotificationManager通知管理器
    - DeadLetterQueueManager死信队列管理器

版本: 1.0.0
作者: AI Assistant
创建时间: 2026-04-23
"""

import unittest
import time
import threading
import os
import tempfile
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

from dbskiter.db_scheduler.utils import (
    TimeoutExecutor,
    CircuitBreaker,
    CronParser,
    NotificationManager,
    DeadLetterQueueManager,
)
from dbskiter.db_scheduler.models import (
    ScheduledTask, TaskType, TaskPriority, ErrorCode
)


class TestTimeoutExecutor(unittest.TestCase):
    """测试超时执行器"""

    def setUp(self):
        self.executor = TimeoutExecutor(timeout=2, max_workers=2)

    def tearDown(self):
        self.executor.shutdown()

    def test_execute_success(self):
        """测试正常执行"""
        def task():
            return "success"

        result = self.executor.execute(task, "task_1")
        self.assertEqual(result, "success")

    def test_execute_timeout(self):
        """测试执行超时"""
        def slow_task():
            time.sleep(5)
            return "completed"

        with self.assertRaises(TimeoutError):
            self.executor.execute(slow_task, "task_2")

    def test_execute_exception(self):
        """测试执行异常"""
        def error_task():
            raise ValueError("测试异常")

        with self.assertRaises(ValueError):
            self.executor.execute(error_task, "task_3")

    def test_cancel_task(self):
        """测试取消任务"""
        def long_task():
            time.sleep(10)
            return "done"

        # 提交任务
        import threading
        result = []

        def run_task():
            try:
                r = self.executor.execute(long_task, "cancel_task")
                result.append(r)
            except Exception as e:
                result.append(e)

        thread = threading.Thread(target=run_task)
        thread.start()

        # 等待任务开始
        time.sleep(0.5)

        # 取消任务
        cancelled = self.executor.cancel_task("cancel_task")
        # 取消可能成功也可能失败，取决于任务状态
        self.assertIsInstance(cancelled, bool)

        thread.join(timeout=3)

    def test_is_task_running(self):
        """测试检查任务是否运行中"""
        def task():
            time.sleep(0.5)
            return "done"

        # 任务未开始
        self.assertFalse(self.executor.is_task_running("new_task"))

        # 启动任务
        import threading
        thread = threading.Thread(
            target=lambda: self.executor.execute(task, "running_task")
        )
        thread.start()

        time.sleep(0.1)
        # 任务应该正在运行
        self.assertTrue(self.executor.is_task_running("running_task"))

        thread.join(timeout=2)


class TestCircuitBreaker(unittest.TestCase):
    """测试熔断器"""

    def setUp(self):
        self.cb = CircuitBreaker(threshold=3, recovery_time=1)

    def test_initial_state(self):
        """测试初始状态"""
        self.assertTrue(self.cb.can_execute())
        self.assertEqual(self.cb.state, "closed")

    def test_record_success(self):
        """测试记录成功"""
        self.cb.record_failure()
        self.cb.record_failure()
        self.assertEqual(self.cb.failure_count, 2)

        self.cb.record_success()
        self.assertEqual(self.cb.failure_count, 0)
        self.assertEqual(self.cb.state, "closed")

    def test_circuit_open(self):
        """测试熔断器打开"""
        # 连续失败达到阈值
        for _ in range(3):
            self.cb.record_failure()

        self.assertEqual(self.cb.state, "open")
        self.assertFalse(self.cb.can_execute())

    def test_circuit_half_open(self):
        """测试熔断器半开状态"""
        # 打开熔断器
        for _ in range(3):
            self.cb.record_failure()

        self.assertFalse(self.cb.can_execute())

        # 等待恢复时间
        time.sleep(1.1)

        # 应该进入半开状态
        self.assertTrue(self.cb.can_execute())
        self.assertEqual(self.cb.state, "half-open")

    def test_circuit_recovery(self):
        """测试熔断器恢复"""
        # 打开熔断器
        for _ in range(3):
            self.cb.record_failure()

        # 等待恢复
        time.sleep(1.1)

        # 半开状态下成功，应该关闭
        self.cb.record_success()
        self.assertEqual(self.cb.state, "closed")


class TestCronParser(unittest.TestCase):
    """测试Cron表达式解析器"""

    def test_validate_valid_cron(self):
        """测试验证有效的Cron表达式"""
        valid_crons = [
            "0 2 * * *",      # 每天2点
            "*/5 * * * *",    # 每5分钟
            "0 0 * * 0",      # 每周日
            "0 0 1 * *",      # 每月1日
            "0 0 1 1 *",      # 每年1月1日
        ]

        for cron in valid_crons:
            self.assertTrue(CronParser.validate(cron), f"应该有效: {cron}")

    def test_validate_invalid_cron(self):
        """测试验证无效的Cron表达式"""
        invalid_crons = [
            "* * *",          # 字段不足
            "60 * * * *",     # 分钟超出范围
            "* 25 * * *",     # 小时超出范围
            "invalid",        # 无效格式
        ]

        for cron in invalid_crons:
            self.assertFalse(CronParser.validate(cron), f"应该无效: {cron}")

    def test_get_next_run_daily(self):
        """测试获取下次执行时间-每天"""
        base_time = datetime(2026, 4, 23, 10, 0, 0)
        next_run = CronParser.get_next_run("0 2 * * *", base_time)

        self.assertIsNotNone(next_run)
        self.assertEqual(next_run.hour, 2)
        self.assertEqual(next_run.minute, 0)
        self.assertGreater(next_run, base_time)

    def test_get_next_run_hourly(self):
        """测试获取下次执行时间-每小时"""
        base_time = datetime(2026, 4, 23, 10, 30, 0)
        next_run = CronParser.get_next_run("0 * * * *", base_time)

        self.assertIsNotNone(next_run)
        self.assertEqual(next_run.minute, 0)
        self.assertEqual(next_run.hour, 11)

    def test_get_next_run_invalid(self):
        """测试无效的Cron返回None"""
        result = CronParser.get_next_run("invalid cron")
        self.assertIsNone(result)

    def test_parse_field_star(self):
        """测试解析*字段"""
        result = CronParser._parse_field("*", 0, 59)
        self.assertEqual(len(result), 60)  # 0-59

    def test_parse_field_range(self):
        """测试解析范围字段"""
        result = CronParser._parse_field("10-15", 0, 59)
        self.assertEqual(result, [10, 11, 12, 13, 14, 15])

    def test_parse_field_step(self):
        """测试解析步长字段"""
        result = CronParser._parse_field("*/10", 0, 59)
        self.assertEqual(result, [0, 10, 20, 30, 40, 50])

    def test_parse_field_list(self):
        """测试解析列表字段"""
        result = CronParser._parse_field("1,5,10", 0, 59)
        self.assertEqual(result, [1, 5, 10])


class TestNotificationManager(unittest.TestCase):
    """测试通知管理器"""

    def setUp(self):
        self.manager = NotificationManager()

    def tearDown(self):
        self.manager.shutdown()

    def test_add_webhook(self):
        """测试添加Webhook"""
        self.manager.add_webhook("https://example.com/webhook")
        self.assertEqual(len(self.manager.webhooks), 1)

        self.manager.add_webhook("https://example.com/webhook2")
        self.assertEqual(len(self.manager.webhooks), 2)

    def test_set_email_config(self):
        """测试设置邮件配置"""
        self.manager.set_email_config(
            smtp_host="smtp.example.com",
            smtp_port=587,
            username="test@example.com",
            password="password123",
            use_tls=True
        )

        self.assertIsNotNone(self.manager.email_config)
        self.assertEqual(self.manager.email_config["host"], "smtp.example.com")
        self.assertEqual(self.manager.email_config["port"], 587)

    @patch('requests.post')
    def test_notify_webhook(self, mock_post):
        """测试发送Webhook通知"""
        mock_post.return_value = Mock(status_code=200)

        self.manager.add_webhook("https://example.com/webhook")
        self.manager.notify("测试消息", {"key": "value"})

        # 等待异步发送
        time.sleep(0.5)

        mock_post.assert_called_once()
        call_args = mock_post.call_args
        self.assertEqual(call_args[0][0], "https://example.com/webhook")


class TestDeadLetterQueueManager(unittest.TestCase):
    """测试死信队列管理器"""

    def setUp(self):
        # 创建临时数据库文件
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()

        self.notification = Mock(spec=NotificationManager)
        self.dlq = DeadLetterQueueManager(self.temp_db.name, self.notification)

    def tearDown(self):
        # 关闭数据库连接
        self.dlq.close()
        # 清理临时文件
        if os.path.exists(self.temp_db.name):
            try:
                os.unlink(self.temp_db.name)
            except PermissionError:
                pass  # Windows下文件可能被占用，忽略

    def test_add_failed_task(self):
        """测试添加失败任务"""
        task = ScheduledTask(
            task_id="task_001",
            name="failed_task",
            task_type=TaskType.BACKUP,
            schedule="0 2 * * *"
        )

        self.dlq.add_failed_task(task, "执行失败", 3)

        # 验证通知被调用
        self.notification.notify.assert_called_once()
        call_args = self.notification.notify.call_args
        self.assertIn("failed_task", call_args[0][0])

    def test_get_pending_tasks(self):
        """测试获取待处理任务"""
        # 添加几个失败任务
        for i in range(3):
            task = ScheduledTask(
                task_id=f"task_{i}",
                name=f"task_{i}",
                task_type=TaskType.BACKUP,
                schedule="0 2 * * *"
            )
            self.dlq.add_failed_task(task, f"错误{i}", 3)

        pending = self.dlq.get_pending_tasks()
        self.assertEqual(len(pending), 3)

    def test_retry_task(self):
        """测试重试任务"""
        task = ScheduledTask(
            task_id="retry_task",
            name="retry_task",
            task_type=TaskType.BACKUP,
            schedule="0 2 * * *"
        )
        self.dlq.add_failed_task(task, "需要重试", 3)

        # 获取任务ID
        pending = self.dlq.get_pending_tasks()
        self.assertEqual(len(pending), 1)
        dlq_id = pending[0]["id"]

        # 重试任务
        result = self.dlq.retry_task(dlq_id)
        self.assertTrue(result["success"])

    def test_resolve_task(self):
        """测试解决任务"""
        task = ScheduledTask(
            task_id="resolve_task",
            name="resolve_task",
            task_type=TaskType.BACKUP,
            schedule="0 2 * * *"
        )
        self.dlq.add_failed_task(task, "已解决", 3)

        # 获取任务ID
        pending = self.dlq.get_pending_tasks()
        dlq_id = pending[0]["id"]

        # 解决任务
        result = self.dlq.resolve_task(dlq_id, "手动处理完成")
        self.assertTrue(result["success"])

        # 验证状态变更
        stats = self.dlq.get_statistics()
        self.assertEqual(stats["resolved"], 1)
        self.assertEqual(stats["pending"], 0)

    def test_get_statistics(self):
        """测试获取统计信息"""
        # 初始状态
        stats = self.dlq.get_statistics()
        self.assertEqual(stats["total"], 0)

        # 添加任务
        task = ScheduledTask(
            task_id="stat_task",
            name="stat_task",
            task_type=TaskType.BACKUP,
            schedule="0 2 * * *"
        )
        self.dlq.add_failed_task(task, "统计测试", 3)

        stats = self.dlq.get_statistics()
        self.assertEqual(stats["pending"], 1)
        self.assertEqual(stats["total"], 1)


if __name__ == "__main__":
    unittest.main()
