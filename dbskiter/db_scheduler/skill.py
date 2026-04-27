"""
db_scheduler/skill.py
统一入口模块（精简重构版）

文件功能：提供SchedulerSkill统一入口，整合所有子模块
主要类：
    - SchedulerSkill: 调度技能统一入口

依赖模块:
    - models.py - 数据模型
    - utils.py - 工具类
    - backup.py - 备份管理
    - task_executors.py - 任务执行器

使用示例:
    >>> from db_scheduler import SchedulerSkill
    >>> skill = SchedulerSkill(connector)
    >>> result = skill.backup()
    >>> skill.schedule_task("daily", "0 2 * * *")

版本: 3.0.0（模块化重构版）
作者: AI Assistant
创建时间: 2026-04-23
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
from pathlib import Path
import logging
import threading
import time
import json
import sqlite3

from dbskiter.shared.unified_connector import UnifiedConnector
from dbskiter.shared.error_handler import (
    create_error_response, create_success_response, handle_exception
)
from dbskiter.shared.validators import validate_params, Validator

# 导入子模块
from .models import (
    ErrorCode, TaskType, TaskStatus, TaskPriority, WorkflowStatus,
    BackupResult, ScheduledTask, TaskResult, TaskNode, TaskGraph
)
from .utils import (
    TimeoutExecutor, CircuitBreaker, CronParser,
    NotificationManager, DeadLetterQueueManager
)
from .backup import BackupManager
from .task_executors import ExecutorFactory

logger = logging.getLogger(__name__)


class SchedulerSkill:
    """
    数据库调度 Skill - 统一入口（模块化重构版）

    整合所有子模块功能：
    - 备份管理（backup.py）
    - 任务执行（task_executors.py）
    - 工具类（utils.py）
    - 数据模型（models.py）

    使用示例:
        >>> skill = SchedulerSkill(connector)
        >>> result = skill.backup()
        >>> skill.schedule_task("daily_backup", "0 2 * * *")
    """

    def __init__(
        self,
        connector: UnifiedConnector,
        backup_dir: str = "./backups",
        storage_path: str = "./runtime_data/scheduler/scheduler.db",
        max_workers: int = 4
    ):
        """
        初始化调度 Skill

        参数:
            connector: 数据库连接器
            backup_dir: 备份目录
            storage_path: 任务存储路径
            max_workers: 最大并发数
        """
        self.connector = connector
        self.backup_dir = Path(backup_dir)
        self.max_workers = max_workers

        # 初始化组件
        self.backup_manager = BackupManager(connector, backup_dir)
        self.circuit_breaker = CircuitBreaker(threshold=5)
        self.notification = NotificationManager()
        self.timeout_executor = TimeoutExecutor(timeout=3600, max_workers=max_workers)
        self.dlq_manager = DeadLetterQueueManager(storage_path, self.notification)

        # 任务状态
        self._tasks: Dict[str, ScheduledTask] = {}
        self._workflows: Dict[str, TaskGraph] = {}
        self._running = False
        self._scheduler_thread: Optional[threading.Thread] = None
        self._lock = threading.RLock()

        # 初始化存储
        self._init_storage(storage_path)

        logger.info("SchedulerSkill 初始化完成")

    def _init_storage(self, storage_path: str):
        """初始化存储数据库"""
        with sqlite3.connect(storage_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    task_id TEXT PRIMARY KEY,
                    name TEXT,
                    task_type TEXT,
                    schedule TEXT,
                    params TEXT,
                    enabled INTEGER DEFAULT 1,
                    last_run TEXT,
                    next_run TEXT,
                    retry_count INTEGER DEFAULT 0,
                    max_retries INTEGER DEFAULT 3,
                    priority INTEGER DEFAULT 3,
                    timeout INTEGER DEFAULT 3600,
                    created_at TEXT,
                    updated_at TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS execution_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT,
                    task_name TEXT,
                    status TEXT,
                    start_time TEXT,
                    end_time TEXT,
                    result TEXT,
                    error TEXT
                )
            """)
            conn.commit()

    # =====================================================================
    # 备份功能
    # =====================================================================

    @validate_params(backup_type=Validator.one_of(["full", "incremental", "tables"]))
    def backup(self, backup_type: str = "full", tables: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        执行数据库备份

        参数:
            backup_type: 备份类型 (full/incremental/tables)
            tables: 指定备份的表（仅tables类型需要）

        返回:
            Dict: 备份结果
        """
        if not self.circuit_breaker.can_execute():
            return create_error_response(
                ErrorMessage.get_message(ErrorCode.BACKUP_CIRCUIT_OPEN),
                code=ErrorCode.BACKUP_CIRCUIT_OPEN
            )

        try:
            if backup_type == "incremental":
                result = self.backup_manager.backup_incremental(tables)
            elif backup_type == "tables" and tables:
                result = self.backup_manager.backup_tables(tables)
            else:
                result = self.backup_manager.backup_full()

            if result.success:
                self.circuit_breaker.record_success()
                self.notification.notify(
                    f"备份成功: {result.backup_id}",
                    {"backup_type": backup_type, "file_path": result.file_path}
                )
                return create_success_response(result.to_dict())
            else:
                self.circuit_breaker.record_failure()
                return create_error_response(
                    result.error or "备份失败",
                    code=ErrorCode.BACKUP_FAILED
                )

        except Exception as e:
            self.circuit_breaker.record_failure()
            return handle_exception(e, "备份执行失败")

    def list_backups(self) -> List[Dict[str, Any]]:
        """列出所有备份"""
        return self.backup_manager.list_backups()

    def verify_backup(self, backup_file: str) -> Dict[str, Any]:
        """验证备份文件"""
        return self.backup_manager.verify_backup(backup_file)

    def restore_backup(self, backup_file: str, target_db: Optional[str] = None) -> Dict[str, Any]:
        """从备份恢复"""
        return self.backup_manager.restore_backup(backup_file, target_db)

    # =====================================================================
    # 定时任务功能
    # =====================================================================

    def schedule_task(
        self,
        name: str,
        schedule: str,
        task_type: str = "backup",
        params: Optional[Dict[str, Any]] = None,
        priority: str = "medium",
        enabled: bool = True
    ) -> Dict[str, Any]:
        """
        创建定时任务

        参数:
            name: 任务名称
            schedule: Cron表达式
            task_type: 任务类型
            params: 任务参数
            priority: 优先级 (critical/high/medium/low)
            enabled: 是否启用

        返回:
            Dict: 创建结果
        """
        try:
            if not CronParser.validate(schedule):
                return create_error_response(
                    f"无效的Cron表达式: {schedule}",
                    code=ErrorCode.TASK_SCHEDULE_INVALID
                )

            task_id = f"task_{int(time.time())}_{name}"
            next_run = CronParser.get_next_run(schedule)

            if not next_run:
                return create_error_response("无法计算下次执行时间")

            task = ScheduledTask(
                task_id=task_id,
                name=name,
                task_type=TaskType(task_type),
                schedule=schedule,
                params=params or {},
                enabled=enabled,
                next_run=next_run,
                priority=TaskPriority[priority.upper()]
            )

            # 保存到内存和数据库
            with self._lock:
                self._tasks[task_id] = task

            self._save_task_to_db(task)

            return create_success_response({
                "task_id": task_id,
                "name": name,
                "schedule": schedule,
                "next_run": next_run.isoformat()
            })

        except Exception as e:
            return handle_exception(e, "创建定时任务失败")

    def _save_task_to_db(self, task: ScheduledTask):
        """保存任务到数据库"""
        with sqlite3.connect("./runtime_data/scheduler/scheduler.db") as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO tasks
                (task_id, name, task_type, schedule, params, enabled, next_run,
                 retry_count, max_retries, priority, timeout, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task.task_id, task.name, task.task_type.value, task.schedule,
                    json.dumps(task.params), int(task.enabled),
                    task.next_run.isoformat() if task.next_run else None,
                    task.retry_count, task.max_retries, task.priority.value,
                    task.timeout, task.created_at.isoformat(), task.updated_at.isoformat()
                )
            )
            conn.commit()

    def list_tasks(self) -> List[Dict[str, Any]]:
        """列出所有定时任务"""
        with self._lock:
            return [task.to_dict() for task in self._tasks.values()]

    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """获取任务详情"""
        with self._lock:
            task = self._tasks.get(task_id)
            return task.to_dict() if task else None

    def enable_task(self, task_id: str) -> Dict[str, Any]:
        """启用任务"""
        with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                return create_error_response(f"任务不存在: {task_id}")
            task.enabled = True
            self._save_task_to_db(task)
        return create_success_response({"task_id": task_id, "enabled": True})

    def disable_task(self, task_id: str) -> Dict[str, Any]:
        """禁用任务"""
        with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                return create_error_response(f"任务不存在: {task_id}")
            task.enabled = False
            self._save_task_to_db(task)
        return create_success_response({"task_id": task_id, "enabled": False})

    def delete_task(self, task_id: str) -> Dict[str, Any]:
        """删除任务"""
        with self._lock:
            if task_id not in self._tasks:
                return create_error_response(f"任务不存在: {task_id}")
            del self._tasks[task_id]

        with sqlite3.connect("./runtime_data/scheduler/scheduler.db") as conn:
            conn.execute("DELETE FROM tasks WHERE task_id = ?", (task_id,))
            conn.commit()

        return create_success_response({"task_id": task_id, "deleted": True})

    # =====================================================================
    # 工作流功能
    # =====================================================================

    def create_workflow(self, workflow_id: str, description: str = "") -> TaskGraph:
        """
        创建工作流

        参数:
            workflow_id: 工作流ID
            description: 工作流描述

        返回:
            TaskGraph: 工作流图对象
        """
        workflow = TaskGraph(workflow_id=workflow_id, description=description)
        with self._lock:
            self._workflows[workflow_id] = workflow
        return workflow

    def submit_workflow(self, workflow: TaskGraph) -> Dict[str, Any]:
        """
        提交工作流执行

        参数:
            workflow: 工作流图

        返回:
            Dict: 执行结果
        """
        try:
            if not workflow.validate():
                return create_error_response(
                    "工作流验证失败：存在循环依赖",
                    code=ErrorCode.WORKFLOW_CYCLE_DETECTED
                )

            # 执行工作流
            results = {}
            workflow.status = WorkflowStatus.RUNNING
            workflow.started_at = datetime.now()

            while True:
                ready_tasks = workflow.get_ready_tasks()
                if not ready_tasks:
                    break

                for node in ready_tasks:
                    # 创建执行器
                    executor = ExecutorFactory.create(
                        node.task_type.value,
                        self.connector
                    )

                    # 执行任务
                    result = executor.execute(node.params)
                    results[node.task_id] = result

                    if not result.get("success", False):
                        workflow.status = WorkflowStatus.FAILED
                        workflow.completed_at = datetime.now()
                        workflow.results = results
                        return create_error_response(
                            f"工作流节点执行失败: {node.task_id}",
                            code=ErrorCode.WORKFLOW_NODE_FAILED,
                            details={"node_id": node.task_id, "error": result.get("error")}
                        )

            workflow.status = WorkflowStatus.COMPLETED
            workflow.completed_at = datetime.now()
            workflow.results = results

            return create_success_response({
                "workflow_id": workflow.workflow_id,
                "status": workflow.status.value,
                "results": results
            })

        except Exception as e:
            workflow.status = WorkflowStatus.FAILED
            return handle_exception(e, "工作流执行失败")

    # =====================================================================
    # 调度器控制
    # =====================================================================

    def start_scheduler(self) -> Dict[str, Any]:
        """启动调度器"""
        if self._running:
            return create_error_response("调度器已在运行")

        self._running = True
        self._scheduler_thread = threading.Thread(target=self._scheduler_loop, daemon=True)
        self._scheduler_thread.start()

        logger.info("调度器已启动")
        return create_success_response({"status": "started"})

    def stop_scheduler(self) -> Dict[str, Any]:
        """停止调度器"""
        if not self._running:
            return create_error_response("调度器未运行")

        self._running = False

        if self._scheduler_thread:
            self._scheduler_thread.join(timeout=10)

        logger.info("调度器已停止")
        return create_success_response({"status": "stopped"})

    def _scheduler_loop(self):
        """调度器主循环"""
        while self._running:
            try:
                now = datetime.now()

                with self._lock:
                    for task in self._tasks.values():
                        if not task.enabled:
                            continue

                        if task.next_run and task.next_run <= now:
                            self._execute_task(task)
                            task.last_run = now
                            task.next_run = CronParser.get_next_run(task.schedule, now)
                            self._save_task_to_db(task)

                time.sleep(30)

            except Exception as e:
                logger.error(f"调度循环出错: {e}")
                time.sleep(30)

    def _execute_task(self, task: ScheduledTask):
        """执行单个任务"""
        logger.info(f"执行任务: {task.name} ({task.task_id})")

        try:
            # 创建执行器
            executor = ExecutorFactory.create(task.task_type.value, self.connector)

            # 使用超时控制执行
            def do_execute():
                return executor.execute(task.params)

            if task.timeout > 0:
                result = self.timeout_executor.execute(do_execute, task.task_id)
            else:
                result = do_execute()

            # 保存执行记录
            task_result = TaskResult(
                task_id=task.task_id,
                task_name=task.name,
                status=TaskStatus.SUCCESS if result.get("success") else TaskStatus.FAILED,
                start_time=datetime.now(),
                end_time=datetime.now(),
                result=result
            )
            self._save_execution(task_result)

            # 发送通知
            if result.get("success"):
                self.notification.notify(
                    f"任务执行成功: {task.name}",
                    {"task_id": task.task_id}
                )
            else:
                raise Exception(result.get("error", "Unknown error"))

        except TimeoutError:
            logger.error(f"任务执行超时: {task.name}")
            self._handle_task_failure(task, "任务执行超时", ErrorCode.TASK_TIMEOUT)

        except Exception as e:
            logger.error(f"任务执行失败: {task.name}, 错误: {e}")
            self._handle_task_failure(task, str(e), ErrorCode.TASK_EXECUTION_FAILED)

    def _handle_task_failure(self, task: ScheduledTask, error: str, error_code: str):
        """处理任务失败"""
        task.retry_count += 1

        if task.retry_count >= task.max_retries:
            self.dlq_manager.add_failed_task(task, error, task.retry_count)
            logger.warning(f"任务 {task.task_id} 进入死信队列")
        else:
            self.notification.notify(
                f"任务执行失败: {task.name}",
                {"task_id": task.task_id, "error": error, "retry_count": task.retry_count}
            )

    def _save_execution(self, result: TaskResult):
        """保存执行记录"""
        with sqlite3.connect("./runtime_data/scheduler/scheduler.db") as conn:
            conn.execute(
                """
                INSERT INTO execution_history
                (task_id, task_name, status, start_time, end_time, result, error)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    result.task_id, result.task_name, result.status.value,
                    result.start_time.isoformat(), result.end_time.isoformat(),
                    json.dumps(result.result) if result.result else None,
                    result.error
                )
            )
            conn.commit()

    # =====================================================================
    # 死信队列管理
    # =====================================================================

    def get_dlq_tasks(self, status: Optional[str] = None, limit: int = 50) -> List[Dict]:
        """获取死信队列任务列表"""
        if status:
            return self.dlq_manager.get_pending_tasks(limit)
        return []

    def retry_dlq_task(self, dlq_id: int) -> Dict[str, Any]:
        """重试死信队列中的任务"""
        return self.dlq_manager.retry_task(dlq_id)

    def resolve_dlq_task(self, dlq_id: int, resolution: str) -> Dict[str, Any]:
        """标记死信队列任务为已解决"""
        return self.dlq_manager.resolve_task(dlq_id, resolution)

    def get_dlq_statistics(self) -> Dict[str, int]:
        """获取死信队列统计信息"""
        return self.dlq_manager.get_statistics()

    # =====================================================================
    # 通知配置
    # =====================================================================

    def add_webhook(self, url: str):
        """添加Webhook通知地址"""
        self.notification.add_webhook(url)

    def set_email_config(self, smtp_host: str, smtp_port: int, username: str, password: str, use_tls: bool = True):
        """
        配置邮件通知

        参数:
            smtp_host: SMTP服务器地址
            smtp_port: SMTP端口
            username: 用户名
            password: 密码
            use_tls: 是否使用TLS
        """
        self.notification.set_email_config(smtp_host, smtp_port, username, password, use_tls)

    # =====================================================================
    # 资源释放
    # =====================================================================

    def close(self):
        """关闭调度器"""
        self.stop_scheduler()
        self.notification.shutdown()
        self.timeout_executor.shutdown()
        logger.info("SchedulerSkill 已关闭")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False
