"""
tests/test_scheduler_engine.py

调度引擎与任务执行器测试
验证 BackupExecutor 调用真正的 BackupManager, skill 层任务管理功能正常。
"""

import os
import sys
import unittest
import tempfile
import shutil
import time
import sqlite3
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dbskiter.shared.unified_connector import UnifiedConnector
from dbskiter.db_scheduler.skill import SchedulerSkill
from dbskiter.db_scheduler.task_executors import (
    BackupExecutor, ExecutorFactory, ExecutionStatus
)


class TestBackupExecutorReal(unittest.TestCase):
    """验证 BackupExecutor 调用真正的 BackupManager, 而非模拟逻辑。"""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.connector = UnifiedConnector(
            dialect="sqlite",
            database=":memory:",
        )
        # 创建测试表
        self.connector.execute(
            "CREATE TABLE test_users (id INTEGER PRIMARY KEY, name TEXT)"
        )
        self.connector.execute(
            "INSERT INTO test_users (name) VALUES ('alice'), ('bob')"
        )

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_full_backup_creates_real_file(self):
        """全量备份应生成包含真实数据的 SQL 文件, 而非模拟文件。"""
        executor = BackupExecutor(self.connector)
        result = executor.execute({
            "output_dir": self.test_dir,
            "compress": False,
        })

        self.assertEqual(result.status, ExecutionStatus.SUCCESS)
        self.assertIn("file_path", result.data)

        file_path = result.data["file_path"]
        self.assertTrue(os.path.exists(file_path))

        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        # 真实备份文件应包含 CREATE TABLE 和 INSERT
        self.assertIn("CREATE TABLE", content)
        self.assertIn("INSERT INTO", content)
        self.assertIn("'alice'", content)

    def test_table_backup_creates_real_file(self):
        """单表备份也应生成真实数据文件。"""
        executor = BackupExecutor(self.connector)
        result = executor.execute({
            "tables": ["test_users"],
            "output_dir": self.test_dir,
            "compress": False,
        })

        self.assertEqual(result.status, ExecutionStatus.SUCCESS)
        self.assertIn("results", result.data)

        for item in result.data["results"]:
            self.assertTrue(os.path.exists(item["file_path"]))


class TestSkillTaskManagement(unittest.TestCase):
    """验证 SchedulerSkill 任务管理功能。"""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.storage_path = os.path.join(self.test_dir, "scheduler.db")
        self.connector = UnifiedConnector(
            dialect="sqlite",
            database=":memory:",
        )
        self.skill = SchedulerSkill(
            self.connector,
            backup_dir=self.test_dir,
            storage_path=self.storage_path,
        )

    def tearDown(self):
        self.skill.close()
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_schedule_and_list_task(self):
        """添加任务后应能在列表中查到。"""
        result = self.skill.schedule_task(
            "daily_backup",
            "0 2 * * *",
            task_type="backup",
            params={"output_dir": self.test_dir},
        )
        self.assertTrue(result.get("success"))
        self.assertEqual(result["data"]["name"], "daily_backup")

        tasks = self.skill.list_tasks()
        names = [t["name"] for t in tasks]
        self.assertIn("daily_backup", names)

    def test_task_persisted_to_db(self):
        """任务应持久化到 SQLite, 重新加载后能恢复。"""
        self.skill.schedule_task(
            "weekly_cleanup",
            "0 0 * * 0",
            task_type="vacuum",
        )

        # 创建新 skill 实例, 模拟重启
        skill2 = SchedulerSkill(
            self.connector,
            backup_dir=self.test_dir,
            storage_path=self.storage_path,
        )
        tasks = skill2.list_tasks()
        names = [t["name"] for t in tasks]
        self.assertIn("weekly_cleanup", names)
        skill2.close()

    def test_enable_disable_task(self):
        """禁用/启用任务应生效。"""
        self.skill.schedule_task("test_task", "0 * * * *")

        result = self.skill.disable_task("test_task")
        self.assertTrue(result.get("success"))

        result = self.skill.enable_task("test_task")
        self.assertTrue(result.get("success"))

    def test_delete_task(self):
        """删除任务后列表中不应再出现。"""
        self.skill.schedule_task("to_delete", "0 * * * *")
        self.skill.delete_task("to_delete")

        tasks = self.skill.list_tasks()
        names = [t["name"] for t in tasks]
        self.assertNotIn("to_delete", names)

    def test_run_backup_task_now(self):
        """立即执行备份任务应成功并生成备份文件。"""
        self.skill.schedule_task(
            "immediate_backup",
            "0 2 * * *",
            task_type="backup",
            params={"output_dir": self.test_dir, "compress": False},
        )

        result = self.skill.run_task_now("immediate_backup")
        self.assertTrue(result.get("success"))

        # 检查是否生成了备份文件
        backups = os.listdir(self.test_dir)
        sql_files = [f for f in backups if f.endswith(".sql")]
        self.assertTrue(len(sql_files) > 0, "备份文件未生成")

    def test_invalid_cron_rejected(self):
        """无效的 Cron 表达式应被拒绝。"""
        result = self.skill.schedule_task("bad", "invalid cron")
        self.assertFalse(result.get("success"))


class TestSchedulerLoop(unittest.TestCase):
    """验证调度循环行为。"""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.storage_path = os.path.join(self.test_dir, "scheduler.db")
        self.connector = UnifiedConnector(
            dialect="sqlite",
            database=":memory:",
        )
        # 创建表用于备份
        self.connector.execute(
            "CREATE TABLE test_data (id INTEGER PRIMARY KEY)"
        )
        self.skill = SchedulerSkill(
            self.connector,
            backup_dir=self.test_dir,
            storage_path=self.storage_path,
        )
        # 确保没有残留任务
        for t in list(self.skill.list_tasks()):
            try:
                self.skill.delete_task(t["name"])
            except Exception:
                pass

    def tearDown(self):
        self.skill.stop_scheduler()
        self.skill.close()
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_scheduler_start_stop(self):
        """调度器应能正常启动和停止。"""
        result = self.skill.start_scheduler()
        self.assertTrue(result.get("success"))
        self.assertTrue(self.skill._running)

        result = self.skill.stop_scheduler()
        self.assertTrue(result.get("success"))
        self.assertFalse(self.skill._running)

    def test_scheduler_status(self):
        """状态查询应返回正确信息。"""
        self.skill.schedule_task("task1", "0 * * * *", enabled=True)
        self.skill.schedule_task("task2", "0 * * * *", enabled=False)

        result = self.skill.get_scheduler_status()
        self.assertTrue(result.get("success"))
        data = result["data"]
        self.assertEqual(data["total_tasks"], 2)
        self.assertEqual(data["enabled_tasks"], 1)
        self.assertEqual(data["disabled_tasks"], 1)

    def test_overdue_task_next_run_recalculated(self):
        """过期任务的 next_run 应在加载时重新计算。"""
        # 创建一个过期任务(next_run 为过去时间)
        from datetime import datetime, timedelta
        from dbskiter.db_scheduler.models import (
            ScheduledTask, TaskType, TaskPriority
        )

        past_time = datetime.now() - timedelta(hours=1)
        task = ScheduledTask(
            task_id="old_task",
            name="old_task",
            task_type=TaskType.BACKUP,
            schedule="0 * * * *",
            next_run=past_time,
        )
        self.skill._tasks["old_task"] = task
        self.skill._save_task_to_db(task)

        # 创建新实例重新加载
        skill2 = SchedulerSkill(
            self.connector,
            backup_dir=self.test_dir,
            storage_path=self.storage_path,
        )

        loaded = skill2._tasks.get("old_task")
        self.assertIsNotNone(loaded)
        self.assertIsNotNone(loaded.next_run)
        # next_run 应被更新为未来的时间
        self.assertGreater(loaded.next_run, datetime.now())
        skill2.close()


class TestExecutorFactory(unittest.TestCase):
    """验证执行器工厂。"""

    def test_create_backup_executor(self):
        """工厂应正确创建 BackupExecutor。"""
        connector = UnifiedConnector(dialect="sqlite", database=":memory:")
        executor = ExecutorFactory.create("backup", connector)
        self.assertIsInstance(executor, BackupExecutor)


if __name__ == "__main__":
    unittest.main()
