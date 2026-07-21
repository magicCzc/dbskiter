"""
db_scheduler/models.py
数据模型定义模块

文件功能：定义所有数据类和枚举类型
主要类：
    - ErrorCode: 错误码体系
    - ErrorMessage: 错误消息映射
    - TaskType: 任务类型枚举
    - TaskStatus: 任务状态枚举
    - TaskPriority: 任务优先级枚举
    - WorkflowStatus: 工作流状态枚举
    - BackupResult: 备份结果数据类
    - ScheduledTask: 定时任务数据类
    - TaskResult: 任务执行结果数据类
    - TaskNode: DAG任务节点数据类
    - TaskGraph: 工作流图数据类

版本: 1.0.0
作者: Magiczc
创建时间: 2026-04-23
"""

from typing import Dict, Any, List, Optional, Set
from datetime import datetime
from enum import Enum
from dataclasses import dataclass, field


# =============================================================================
# 错误码体系
# =============================================================================

class ErrorCode:
    """
    错误码体系

    格式: SCHXXXYYY
    - SCH: Scheduler模块标识
    - XXX: 功能代码
    - YYY: 具体错误
    """

    # 通用错误 (000)
    SUCCESS = "SCH000000"
    UNKNOWN_ERROR = "SCH000001"
    INVALID_PARAM = "SCH000002"
    NOT_FOUND = "SCH000003"
    ALREADY_EXISTS = "SCH000004"

    # 备份错误 (100)
    BACKUP_FAILED = "SCH100001"
    BACKUP_TIMEOUT = "SCH100002"
    BACKUP_CIRCUIT_OPEN = "SCH100003"
    BACKUP_INVALID_TYPE = "SCH100004"
    BACKUP_STORAGE_FULL = "SCH100005"
    BACKUP_FILE_CORRUPTED = "SCH100006"

    # 任务调度错误 (200)
    TASK_SCHEDULE_INVALID = "SCH200001"
    TASK_EXECUTION_FAILED = "SCH200002"
    TASK_TIMEOUT = "SCH200003"
    TASK_CANCELLED = "SCH200004"
    TASK_RETRY_EXHAUSTED = "SCH200005"
    TASK_DLQ_FULL = "SCH200006"

    # 工作流错误 (300)
    WORKFLOW_INVALID = "SCH300001"
    WORKFLOW_EXECUTION_FAILED = "SCH300002"
    WORKFLOW_CYCLE_DETECTED = "SCH300003"
    WORKFLOW_NODE_FAILED = "SCH300004"

    # 数据库错误 (400)
    DB_CONNECTION_FAILED = "SCH400001"
    DB_QUERY_FAILED = "SCH400002"
    DB_LOCK_TIMEOUT = "SCH400003"

    # 通知错误 (500)
    NOTIFICATION_FAILED = "SCH500001"
    WEBHOOK_INVALID = "SCH500002"
    EMAIL_SEND_FAILED = "SCH500003"


class ErrorMessage:
    """错误消息映射"""

    _messages = {
        ErrorCode.SUCCESS: "操作成功",
        ErrorCode.UNKNOWN_ERROR: "未知错误",
        ErrorCode.INVALID_PARAM: "参数无效",
        ErrorCode.NOT_FOUND: "资源不存在",
        ErrorCode.ALREADY_EXISTS: "资源已存在",

        ErrorCode.BACKUP_FAILED: "备份失败",
        ErrorCode.BACKUP_TIMEOUT: "备份超时",
        ErrorCode.BACKUP_CIRCUIT_OPEN: "熔断器已打开，暂时无法执行备份",
        ErrorCode.BACKUP_INVALID_TYPE: "无效的备份类型",
        ErrorCode.BACKUP_STORAGE_FULL: "存储空间不足",
        ErrorCode.BACKUP_FILE_CORRUPTED: "备份文件已损坏",

        ErrorCode.TASK_SCHEDULE_INVALID: "无效的任务调度表达式",
        ErrorCode.TASK_EXECUTION_FAILED: "任务执行失败",
        ErrorCode.TASK_TIMEOUT: "任务执行超时",
        ErrorCode.TASK_CANCELLED: "任务已取消",
        ErrorCode.TASK_RETRY_EXHAUSTED: "任务重试次数已耗尽",
        ErrorCode.TASK_DLQ_FULL: "死信队列已满",

        ErrorCode.WORKFLOW_INVALID: "无效的工作流",
        ErrorCode.WORKFLOW_EXECUTION_FAILED: "工作流执行失败",
        ErrorCode.WORKFLOW_CYCLE_DETECTED: "工作流中存在循环依赖",
        ErrorCode.WORKFLOW_NODE_FAILED: "工作流节点执行失败",

        ErrorCode.DB_CONNECTION_FAILED: "数据库连接失败",
        ErrorCode.DB_QUERY_FAILED: "数据库查询失败",
        ErrorCode.DB_LOCK_TIMEOUT: "数据库锁超时",

        ErrorCode.NOTIFICATION_FAILED: "通知发送失败",
        ErrorCode.WEBHOOK_INVALID: "无效的Webhook地址",
        ErrorCode.EMAIL_SEND_FAILED: "邮件发送失败",
    }

    @classmethod
    def get_message(cls, code: str) -> str:
        """获取错误消息"""
        return cls._messages.get(code, f"未知错误码: {code}")


# =============================================================================
# 枚举定义
# =============================================================================

class TaskType(str, Enum):
    """任务类型"""
    BACKUP = "backup"
    BACKUP_INCREMENTAL = "backup_incremental"
    VACUUM = "vacuum"
    ANALYZE = "analyze"
    REINDEX = "reindex"
    CHECK = "check"
    CUSTOM = "custom"


class TaskStatus(str, Enum):
    """任务状态"""
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


class TaskPriority(int, Enum):
    """任务优先级（数值越小优先级越高）"""
    CRITICAL = 1
    HIGH = 2
    MEDIUM = 3
    LOW = 4


class WorkflowStatus(str, Enum):
    """工作流状态"""
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


# =============================================================================
# 数据类定义
# =============================================================================

@dataclass
class BackupResult:
    """备份结果"""
    success: bool
    backup_id: str
    file_path: str
    file_size: int
    duration_ms: int
    tables: List[str] = field(default_factory=list)
    backup_type: str = "full"
    error: Optional[str] = None

    def to_dict(self) -> Dict:
        return {
            "success": self.success,
            "backup_id": self.backup_id,
            "file_path": self.file_path,
            "file_size": self.file_size,
            "duration_ms": self.duration_ms,
            "tables": self.tables,
            "backup_type": self.backup_type,
            "error": self.error
        }


@dataclass
class ScheduledTask:
    """定时任务"""
    task_id: str
    name: str
    task_type: TaskType
    schedule: str
    params: Dict[str, Any] = field(default_factory=dict)
    enabled: bool = True
    last_run: Optional[datetime] = None
    next_run: Optional[datetime] = None
    status: TaskStatus = TaskStatus.PENDING
    retry_count: int = 0
    max_retries: int = 3
    priority: TaskPriority = TaskPriority.MEDIUM
    timeout: int = 3600
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict:
        return {
            "task_id": self.task_id,
            "name": self.name,
            "task_type": self.task_type.value,
            "schedule": self.schedule,
            "params": self.params,
            "enabled": self.enabled,
            "last_run": self.last_run.isoformat() if self.last_run else None,
            "next_run": self.next_run.isoformat() if self.next_run else None,
            "status": self.status.value,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "priority": self.priority.value,
            "timeout": self.timeout,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }


@dataclass
class TaskResult:
    """任务执行结果（支持错误码）"""
    task_id: str
    task_name: str
    status: TaskStatus
    start_time: datetime
    end_time: datetime
    result: Any = None
    error: Optional[str] = None
    error_code: str = ErrorCode.SUCCESS
    retry_count: int = 0

    @property
    def duration_ms(self) -> int:
        return int((self.end_time - self.start_time).total_seconds() * 1000)

    def to_dict(self) -> Dict:
        return {
            "task_id": self.task_id,
            "task_name": self.task_name,
            "status": self.status.value,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat(),
            "duration_ms": self.duration_ms,
            "result": self.result,
            "error": self.error,
            "error_code": self.error_code,
            "error_message": ErrorMessage.get_message(self.error_code),
            "retry_count": self.retry_count
        }


@dataclass
class TaskNode:
    """DAG任务节点"""
    task_id: str
    task_type: TaskType
    params: Dict[str, Any] = field(default_factory=dict)
    depends_on: Set[str] = field(default_factory=set)
    priority: TaskPriority = TaskPriority.MEDIUM
    timeout: int = 3600
    retry_count: int = 3

    def add_dependency(self, task_id: str):
        """添加依赖"""
        self.depends_on.add(task_id)

    def to_dict(self) -> Dict:
        return {
            "task_id": self.task_id,
            "task_type": self.task_type.value,
            "params": self.params,
            "depends_on": list(self.depends_on),
            "priority": self.priority.value,
            "timeout": self.timeout,
            "retry_count": self.retry_count
        }


@dataclass
class TaskGraph:
    """工作流任务图（DAG）"""
    workflow_id: str
    description: str = ""
    tasks: Dict[str, TaskNode] = field(default_factory=dict)
    status: WorkflowStatus = WorkflowStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    results: Dict[str, Any] = field(default_factory=dict)

    def add_task(self, node: TaskNode):
        """添加任务节点"""
        self.tasks[node.task_id] = node

    def get_ready_tasks(self) -> List[TaskNode]:
        """获取可以执行的任务（依赖已满足）"""
        completed = set(self.results.keys())
        ready = []

        for task_id, node in self.tasks.items():
            if task_id not in self.results and task_id not in [t.task_id for t in ready]:
                if node.depends_on.issubset(completed):
                    ready.append(node)

        return ready

    def validate(self) -> bool:
        """验证DAG无循环依赖"""
        visited = set()
        temp_mark = set()

        def has_cycle(node_id: str) -> bool:
            if node_id in temp_mark:
                return True
            if node_id in visited:
                return False

            temp_mark.add(node_id)
            node = self.tasks.get(node_id)
            if node:
                for dep_id in node.depends_on:
                    if has_cycle(dep_id):
                        return True
            temp_mark.remove(node_id)
            visited.add(node_id)
            return False

        for task_id in self.tasks:
            if has_cycle(task_id):
                return False
        return True

    def to_dict(self) -> Dict:
        return {
            "workflow_id": self.workflow_id,
            "description": self.description,
            "tasks": {k: v.to_dict() for k, v in self.tasks.items()},
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "results": self.results
        }


@dataclass
class PrioritizedTask:
    """带优先级的任务（用于优先队列）"""
    priority: int
    scheduled_time: datetime
    task_id: str
    task: ScheduledTask

    def __lt__(self, other):
        """优先级比较（数值小的优先）"""
        if self.priority != other.priority:
            return self.priority < other.priority
        return self.scheduled_time < other.scheduled_time
