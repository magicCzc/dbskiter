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

try:
    import sqlite3
except ImportError:
    sqlite3 = None

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
        self.storage_path = storage_path
        self.max_workers = max_workers

        # 初始化组件
        self.backup_manager = BackupManager(connector)
        self.backup_manager.default_output_dir = str(backup_dir)
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
            conn.execute("""
                CREATE TABLE IF NOT EXISTS workflows (
                    workflow_id TEXT PRIMARY KEY,
                    description TEXT,
                    tasks TEXT,
                    status TEXT,
                    created_at TEXT,
                    started_at TEXT,
                    completed_at TEXT,
                    results TEXT
                )
            """)
            conn.commit()

        # 从数据库加载现有任务和工作流
        self._load_tasks_from_db()
        self._load_workflows_from_db()

    def _load_tasks_from_db(self):
        """从数据库加载任务到内存, 过期任务重新计算 next_run"""
        try:
            with sqlite3.connect(self.storage_path) as conn:
                cursor = conn.execute("SELECT * FROM tasks")
                rows = cursor.fetchall()

                now = datetime.now()
                for row in rows:
                    task = ScheduledTask(
                        task_id=row[0],
                        name=row[1],
                        task_type=TaskType(row[2]),
                        schedule=row[3],
                        params=json.loads(row[4]) if row[4] else {},
                        enabled=bool(row[5]),
                        next_run=datetime.fromisoformat(row[7]) if row[7] else None,
                        retry_count=row[8] or 0,
                        max_retries=row[9] or 3,
                        priority=TaskPriority(row[10]) if row[10] else TaskPriority.MEDIUM,
                        timeout=row[11] or 3600,
                        created_at=datetime.fromisoformat(row[12]) if row[12] else datetime.now(),
                        updated_at=datetime.fromisoformat(row[13]) if row[13] else datetime.now()
                    )
                    # 如果 next_run 已过期, 重新计算
                    if task.next_run is None or task.next_run <= now:
                        task.next_run = CronParser.get_next_run(task.schedule, now)
                        if task.next_run:
                            self._save_task_to_db(task)
                    self._tasks[row[0]] = task

                if self._tasks:
                    logger.info(f"从数据库加载了 {len(self._tasks)} 个任务")
        except Exception as e:
            logger.warning(f"从数据库加载任务失败: {e}")

    def _load_workflows_from_db(self):
        """从数据库加载工作流到内存"""
        try:
            with sqlite3.connect(self.storage_path) as conn:
                cursor = conn.execute("SELECT * FROM workflows")
                rows = cursor.fetchall()

                for row in rows:
                    workflow = TaskGraph(
                        workflow_id=row[0],
                        description=row[1] or "",
                        status=WorkflowStatus(row[3]) if row[3] else WorkflowStatus.PENDING,
                        created_at=datetime.fromisoformat(row[4]) if row[4] else datetime.now(),
                        started_at=datetime.fromisoformat(row[5]) if row[5] else None,
                        completed_at=datetime.fromisoformat(row[6]) if row[6] else None,
                        results=json.loads(row[7]) if row[7] else {}
                    )
                    # 解析任务节点
                    if row[2]:
                        tasks_data = json.loads(row[2])
                        for task_id, task_data in tasks_data.items():
                            node = TaskNode(
                                task_id=task_data.get("task_id", task_id),
                                task_type=TaskType(task_data.get("task_type", "backup")),
                                params=task_data.get("params", {}),
                                depends_on=set(task_data.get("depends_on", [])),
                                priority=TaskPriority(task_data.get("priority", 3)),
                                timeout=task_data.get("timeout", 3600),
                                retry_count=task_data.get("retry_count", 3)
                            )
                            workflow.add_task(node)
                    self._workflows[row[0]] = workflow

                if self._workflows:
                    logger.info(f"从数据库加载了 {len(self._workflows)} 个工作流")
        except Exception as e:
            logger.warning(f"从数据库加载工作流失败: {e}")

    def _save_workflow_to_db(self, workflow: TaskGraph):
        """保存工作流到数据库"""
        try:
            with sqlite3.connect(self.storage_path) as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO workflows
                    (workflow_id, description, tasks, status, created_at, started_at, completed_at, results)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        workflow.workflow_id,
                        workflow.description,
                        json.dumps({k: v.to_dict() for k, v in workflow.tasks.items()}),
                        workflow.status.value,
                        workflow.created_at.isoformat() if workflow.created_at else None,
                        workflow.started_at.isoformat() if workflow.started_at else None,
                        workflow.completed_at.isoformat() if workflow.completed_at else None,
                        json.dumps(workflow.results) if workflow.results else "{}"
                    )
                )
                conn.commit()
        except Exception as e:
            logger.error(f"保存工作流到数据库失败: {e}")

    # =====================================================================
    # 备份功能
    # =====================================================================

    @validate_params(backup_type=Validator.one_of(["full", "incremental", "table"]))
    def backup(
        self,
        backup_type: str = "full",
        tables: Optional[List[str]] = None,
        output_dir: Optional[str] = None,
        compress: bool = True,
    ) -> Dict[str, Any]:
        """
        执行数据库备份（已接入多步骤计时）

        参数:
            backup_type: 备份类型 (full/incremental/tables)
            tables: 指定备份的表（仅tables类型需要）
            output_dir: 输出目录
            compress: 是否压缩

        返回:
            Dict: 备份结果，包含 _execution_time 步骤耗时
        """
        from dbskiter.shared.execution_timer import ExecutionTimer
        timer = ExecutionTimer().start()

        if not self.circuit_breaker.can_execute():
            return create_error_response(
                ErrorMessage.get_message(ErrorCode.BACKUP_CIRCUIT_OPEN),
                code=ErrorCode.BACKUP_CIRCUIT_OPEN
            )

        try:
            if backup_type == "incremental":
                with timer.step("backup_incremental", "执行增量备份"):
                    result = self.backup_manager.backup_incremental(
                        tables, output_dir=output_dir
                    )
            elif backup_type == "table" and tables:
                with timer.step("backup_tables", "执行多表备份"):
                    results = self.backup_manager.backup_tables(
                        tables, output_dir=output_dir
                    )
                # 多表备份返回列表, 汇总结果
                all_success = all(r.success for r in results)
                if all_success:
                    self.circuit_breaker.record_success()
                    response = create_success_response({
                        "results": [r.to_dict() for r in results],
                        "total": len(results),
                        "success_count": sum(1 for r in results if r.success),
                    })
                    response["_execution_time"] = timer.to_summary()
                    return response
                else:
                    self.circuit_breaker.record_failure()
                    errors = [r.error for r in results if not r.success and r.error]
                    return create_error_response(
                        "; ".join(errors) if errors else "部分表备份失败",
                        code=ErrorCode.BACKUP_FAILED
                    )
            else:
                with timer.step("backup_full", "执行全量备份"):
                    result = self.backup_manager.backup_full(
                        output_dir=output_dir, compress=compress
                    )

            if result.success:
                self.circuit_breaker.record_success()
                self.notification.notify(
                    f"备份成功: {result.backup_id}",
                    {"backup_type": backup_type, "file_path": result.file_path}
                )
                response = create_success_response(result.to_dict())
                response["_execution_time"] = timer.to_summary()
                return response
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
        result = self.backup_manager.verify_backup(backup_file)
        if result.success:
            return create_success_response(result.to_dict())
        else:
            return create_error_response(
                result.error or "验证失败",
                code=ErrorCode.BACKUP_FILE_CORRUPTED
            )

    def restore_backup(self, backup_file: str, target_db: Optional[str] = None) -> Dict[str, Any]:
        """从备份恢复"""
        result = self.backup_manager.restore_backup(backup_file, target_db)
        if result.success:
            return create_success_response(result.to_dict())
        else:
            return create_error_response(
                result.error or "恢复失败",
                code=ErrorCode.BACKUP_FAILED
            )

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
        with sqlite3.connect(self.storage_path) as conn:
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

    def _find_task_by_name_or_id(self, name_or_id: str) -> Optional[ScheduledTask]:
        """通过名称或ID查找任务"""
        # 先尝试作为ID查找
        if name_or_id in self._tasks:
            return self._tasks[name_or_id]
        # 再尝试作为名称查找
        for task in self._tasks.values():
            if task.name == name_or_id:
                return task
        return None

    def enable_task(self, task_id: str, enabled: bool = True) -> Dict[str, Any]:
        """启用/禁用任务"""
        with self._lock:
            task = self._find_task_by_name_or_id(task_id)
            if not task:
                return create_error_response(f"任务不存在: {task_id}")
            task.enabled = enabled
            self._save_task_to_db(task)
        return create_success_response({"task_id": task.task_id, "name": task.name, "enabled": enabled})

    def disable_task(self, task_id: str) -> Dict[str, Any]:
        """禁用任务"""
        return self.enable_task(task_id, enabled=False)

    def delete_task(self, task_id: str) -> Dict[str, Any]:
        """删除任务"""
        with self._lock:
            task = self._find_task_by_name_or_id(task_id)
            if not task:
                return create_error_response(f"任务不存在: {task_id}")
            actual_task_id = task.task_id
            del self._tasks[actual_task_id]

        with sqlite3.connect(self.storage_path) as conn:
            conn.execute("DELETE FROM tasks WHERE task_id = ?", (actual_task_id,))
            conn.commit()

        return create_success_response({"task_id": actual_task_id, "name": task.name, "deleted": True})

    def remove_task(self, task_id: str) -> Dict[str, Any]:
        """删除任务（delete_task的别名）"""
        return self.delete_task(task_id)

    def run_task_now(self, task_id: str) -> Dict[str, Any]:
        """立即执行任务"""
        with self._lock:
            task = self._find_task_by_name_or_id(task_id)
            if not task:
                return create_error_response(f"任务不存在: {task_id}")

            start_time = time.time()
            try:
                result = self._execute_task(task)
                duration = time.time() - start_time
                return create_success_response({
                    "task_id": task_id,
                    "duration_seconds": duration,
                    "result": result
                })
            except Exception as e:
                return create_error_response(f"任务执行失败: {e}")

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
        self._save_workflow_to_db(workflow)
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

    def submit_workflow_by_name(self, workflow_id: str) -> Dict[str, Any]:
        """
        通过工作流名称提交执行

        参数:
            workflow_id: 工作流ID/名称

        返回:
            Dict: 执行结果
        """
        with self._lock:
            workflow = self._workflows.get(workflow_id)

        if not workflow:
            return create_error_response(
                f"工作流不存在: {workflow_id}",
                code=ErrorCode.NOT_FOUND
            )

        return self.submit_workflow(workflow)

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

    def get_scheduler_status(self) -> Dict[str, Any]:
        """获取调度器状态"""
        enabled_tasks = sum(1 for t in self._tasks.values() if t.enabled)
        disabled_tasks = len(self._tasks) - enabled_tasks

        return create_success_response({
            "running": self._running,
            "total_tasks": len(self._tasks),
            "enabled_tasks": enabled_tasks,
            "disabled_tasks": disabled_tasks,
            "thread_alive": self._scheduler_thread.is_alive() if self._scheduler_thread else False
        })

    def _scheduler_loop(self):
        """调度器主循环

        注意事项:
        - 不在持有锁的情况下执行耗时任务
        - 每30秒检查一次, Cron 精度为分钟级
        """
        while self._running:
            try:
                now = datetime.now()
                tasks_to_run = []

                # 收集需要执行的任务, 释放锁后再执行
                with self._lock:
                    for task in self._tasks.values():
                        if not task.enabled:
                            continue
                        if task.next_run and task.next_run <= now:
                            tasks_to_run.append(task)
                            # 先更新 next_run 避免重复执行
                            task.next_run = CronParser.get_next_run(task.schedule, now)
                            task.last_run = now

                for task in tasks_to_run:
                    try:
                        self._execute_task(task)
                    except Exception as e:
                        logger.error(f"调度执行任务失败 {task.name}: {e}")
                    # 执行完成后保存状态
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

            # result 是 ExecutionResult 对象, 判断状态
            from .task_executors import ExecutionStatus
            is_success = result.status == ExecutionStatus.SUCCESS

            # 保存执行记录
            task_result = TaskResult(
                task_id=task.task_id,
                task_name=task.name,
                status=TaskStatus.SUCCESS if is_success else TaskStatus.FAILED,
                start_time=datetime.now(),
                end_time=datetime.now(),
                result=result.to_dict() if hasattr(result, 'to_dict') else result
            )
            self._save_execution(task_result)

            # 发送通知
            if is_success:
                self.notification.notify(
                    f"任务执行成功: {task.name}",
                    {"task_id": task.task_id}
                )
            else:
                raise Exception(result.error or "任务执行失败")

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
        with sqlite3.connect(self.storage_path) as conn:
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

    def get_task_logs(
        self,
        task_name: Optional[str] = None,
        limit: int = 50,
        status: str = "all"
    ) -> Dict[str, Any]:
        """
        获取任务执行日志

        参数:
            task_name: 任务名称过滤
            limit: 返回条数限制
            status: 状态过滤 (all/success/failed)

        返回:
            Dict: 标准响应格式，包含执行日志列表
        """
        try:
            db_path = self.storage_path
            import os
            if not os.path.exists(db_path):
                return create_success_response(
                    message="暂无执行日志",
                    data={"logs": [], "total": 0}
                )

            with sqlite3.connect(db_path) as conn:
                conn.row_factory = sqlite3.Row
                conditions = []
                params = []

                if task_name:
                    conditions.append("task_name = ?")
                    params.append(task_name)
                if status != "all":
                    conditions.append("status = ?")
                    params.append(status)

                where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""
                params.append(limit)

                rows = conn.execute(
                    f"SELECT * FROM execution_history{where_clause} ORDER BY start_time DESC LIMIT ?",
                    params
                ).fetchall()

                logs = []
                for row in rows:
                    logs.append({
                        "task_id": row["task_id"],
                        "task_name": row["task_name"],
                        "status": row["status"],
                        "start_time": row["start_time"],
                        "end_time": row["end_time"],
                        "result": row["result"],
                        "error": row["error"],
                    })

                return create_success_response(
                    message=f"获取到 {len(logs)} 条执行日志",
                    data={"logs": logs, "total": len(logs)}
                )
        except Exception as e:
            return create_error_response(str(e), ErrorCode.UNKNOWN_ERROR)

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

    # ==================== AI上下文构建 ====================

    def build_ai_context(
        self,
        skill_result: Dict[str, Any],
        scenario: str = "scheduler"
    ) -> Dict[str, Any]:
        """
        构建AI分析上下文

        参数:
            skill_result: Skill返回的原始结果
            scenario: 场景标识 (scheduler/backup/logs)

        返回:
            Dict[str, Any]: AI上下文
        """
        from dbskiter.shared.ai_context import AIContextBuilder

        builder = AIContextBuilder(
            dialect=self.connector.dialect if hasattr(self.connector, 'dialect') else 'unknown',
            database_name=getattr(self.connector, 'database', ''),
        )
        builder.detect_business_context(self.connector)

        data = skill_result.get("data", {})

        raw_metrics = self._extract_raw_metrics_for_ai(data, scenario)
        rule_flags = self._extract_rule_flags_for_ai(data, scenario)
        context = builder.build_database_profile(self.connector)
        reference_values = self._build_reference_values(scenario)
        ai_hints = self._build_ai_hints(scenario, data)

        inspection_trace = self._build_inspection_trace(scenario, data)

        return {
            "raw_metrics": raw_metrics,
            "rule_flags": rule_flags,
            "context": context,
            "reference_values": reference_values,
            "ai_hints": ai_hints,
            "inspection_trace": inspection_trace,
        }

    def _build_inspection_trace(
        self,
        scenario: str,
        data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        构建调度器透明度追踪信息

        参数:
            scenario: 场景标识
            data: Skill返回的data字段

        返回:
            Dict[str, Any]: 追踪信息
        """
        trace = {
            "scenario": scenario,
            "metrics_checked": [],
            "data_sources": [],
            "confidence": "high",
            "notes": []
        }

        if scenario == "scheduler":
            trace["metrics_checked"] = [
                {"name": "task_status", "description": "任务状态", "source": "调度器内部状态"},
                {"name": "schedule_config", "description": "调度配置", "source": "配置文件/数据库"},
                {"name": "execution_history", "description": "执行历史", "source": "日志表"},
            ]
            trace["data_sources"] = ["scheduler_internal", "config_file", "log_table"]

        elif scenario == "backup":
            trace["metrics_checked"] = [
                {"name": "backup_size", "description": "备份大小", "source": "文件系统"},
                {"name": "backup_duration", "description": "备份耗时", "source": "执行日志"},
                {"name": "backup_integrity", "description": "备份完整性", "source": "校验和"},
                {"name": "backup_storage", "description": "备份存储位置", "source": "配置"},
            ]
            trace["data_sources"] = ["filesystem", "execution_log", "checksum"]
            if not data.get("backup"):
                trace["confidence"] = "low"
                trace["notes"].append("未获取到备份信息，可能尚未执行过备份")

        elif scenario == "logs":
            trace["metrics_checked"] = [
                {"name": "execution_log", "description": "执行日志", "source": "日志表/文件"},
                {"name": "error_log", "description": "错误日志", "source": "错误日志表"},
                {"name": "performance_log", "description": "性能日志", "source": "性能表"},
            ]
            trace["data_sources"] = ["log_table", "error_log", "performance_table"]

        else:
            trace["metrics_checked"] = [
                {"name": "general_scheduler_status", "description": "通用调度状态", "source": "自动检测"}
            ]
            trace["data_sources"] = ["auto_detection"]
            trace["notes"].append(f"未定义场景 '{scenario}' 的详细追踪，使用通用指标")

        return trace

    def _extract_raw_metrics_for_ai(self, data: Dict[str, Any], scenario: str) -> Dict[str, Any]:
        """提取原始指标"""
        metrics = {}

        # 提取关键字段
        key_fields = ["backup", "logs", "tasks", "workflow", "schedule", "status", "result", "message"]
        for key in key_fields:
            if key in data:
                metrics[key] = data[key]

        # 场景特定提取
        if scenario == "backup":
            for key in ["backup_type", "start_time", "end_time", "size", "status", "error_message"]:
                if key in data:
                    metrics[key] = data[key]
        elif scenario == "task":
            for key in ["task_name", "task_status", "last_run", "next_run", "schedule", "enabled"]:
                if key in data:
                    metrics[key] = data[key]
        elif scenario == "logs":
            for key in ["total_logs", "failed_count", "success_count", "recent_errors"]:
                if key in data:
                    metrics[key] = data[key]

        if not metrics:
            metrics = data

        return metrics

    def _extract_rule_flags_for_ai(self, data: Dict[str, Any], scenario: str) -> Dict[str, Any]:
        """提取规则标记"""
        flags = {}

        # 备份失败标记
        if "backup" in data:
            backup = data["backup"]
            if backup.get("status") == "failed":
                flags["backup_failed"] = {"flagged": True, "level": "critical", "reason": "备份失败"}
            elif backup.get("status") == "partial":
                flags["backup_partial"] = {"flagged": True, "level": "warning", "reason": "备份部分成功"}

        # 任务失败标记
        if "tasks" in data and isinstance(data["tasks"], list):
            failed_tasks = [t for t in data["tasks"] if t.get("status") == "failed"]
            if failed_tasks:
                flags["failed_tasks"] = {"flagged": True, "level": "high", "reason": f"发现 {len(failed_tasks)} 个失败任务"}

        # 日志错误标记
        if "logs" in data and isinstance(data["logs"], list):
            error_logs = [l for l in data["logs"] if l.get("level") in ["error", "critical"]]
            if error_logs:
                flags["error_logs"] = {"flagged": True, "level": "medium", "reason": f"发现 {len(error_logs)} 条错误日志"}

        return {"_disclaimer": "规则初筛结果仅供参考", "flags": flags}

    def _build_reference_values(self, scenario: str) -> Dict[str, Any]:
        """构建参考基线"""
        refs = {
            "backup_retention": {"standard": "7-30天", "compliance": "90天+"},
            "task_timeout": {"normal": "<1小时", "warning": "1-4小时", "critical": ">4小时"},
            "log_retention": {"standard": "30天", "compliance": "90天+"},
        }
        return refs

    def _build_ai_hints(self, scenario: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """构建AI提示"""
        hints = {"focus_areas": [], "related_commands": []}
        db_name = getattr(self.connector, 'database', '')

        if scenario == "backup":
            hints["focus_areas"] = ["backup_strategy", "retention_policy", "recovery_time", "backup_verification"]
            hints["related_commands"] = [
                f"dbskiter --database={db_name} scheduler task list",
                f"dbskiter --database={db_name} scheduler logs",
            ]
        elif scenario == "task":
            hints["focus_areas"] = ["task_schedule", "execution_history", "failure_analysis"]
            hints["related_commands"] = [
                f"dbskiter --database={db_name} scheduler logs",
                f"dbskiter --database={db_name} monitor health",
            ]
        elif scenario == "logs":
            hints["focus_areas"] = ["error_analysis", "performance_trends", "failure_patterns"]
            hints["related_commands"] = [
                f"dbskiter --database={db_name} scheduler task list",
            ]

        return hints
