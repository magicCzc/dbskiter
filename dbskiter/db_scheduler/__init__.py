"""
db_scheduler Skill - 统一入口
db_scheduler模块 - 任务调度与工作流管理

快速开始:
    from db_scheduler import SchedulerSkill

    skill = SchedulerSkill(connector)

    # 立即备份
    result = skill.backup()

    # 创建定时任务
    skill.schedule_task("daily_backup", "0 2 * * *", task_type="backup")

    # 创建DAG工作流
    workflow = skill.create_workflow("maintenance")
    workflow.add_task(TaskNode("backup", TaskType.BACKUP))
    workflow.add_task(TaskNode("analyze", TaskType.ANALYZE, depends_on=["backup"]))
    skill.submit_workflow(workflow)

    # 启动调度器
    skill.start_scheduler()

核心功能:
- 数据库备份 - 全量/增量/单表备份
- 定时任务 - Cron表达式调度
- DAG工作流 - 复杂任务依赖
- 智能重试 - 熔断器、指数退避、死信队列
- 任务统计 - 成功率、耗时分析、趋势报告
- 通知渠道 - Webhook、邮件通知
- 分布式锁 - Redis/数据库/文件系统多后端支持
- 依赖管理 - DAG拓扑排序与循环检测
- 监控告警 - Prometheus指标导出与告警规则

模块结构:
- models.py - 数据模型和枚举定义
- utils.py - 工具类（熔断器、Cron解析器、通知管理等）
- backup.py - 备份管理器
- task_executors.py - 任务执行器集合
- persistent_storage.py - SQLite持久化存储
- skill.py - 统一入口（SchedulerSkill）
- distributed_lock.py - 分布式锁实现
- dependency_manager.py - 任务依赖管理
- scheduler_engine.py - 调度引擎
- monitoring.py - 监控与告警
- result_cleanup.py - 结果清理策略

版本: 3.0.0（模块化重构版）
作者: AI Assistant
创建时间: 2026-04-23
"""

# 数据模型
from .models import (
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

# 工具类
from .utils import (
    TimeoutExecutor,
    CircuitBreaker,
    CronParser,
    NotificationManager,
    DeadLetterQueueManager,
)

# 备份管理
from .backup import BackupManager

# 任务执行器
from .task_executors import (
    BaseTaskExecutor,
    BackupExecutor,
    AnalyzeExecutor,
    VacuumExecutor,
    ReindexExecutor,
    CheckExecutor,
    CustomSQLExecutor,
    ExecutorFactory,
)

# 分布式锁
from .distributed_lock import (
    DistributedLock,
    RedisDistributedLock,
    DatabaseDistributedLock,
    FileDistributedLock,
    LockManager,
)

# 依赖管理
from .dependency_manager import DependencyManager

# 调度引擎
from .scheduler_engine import SchedulerEngine

# 持久化存储
from .persistent_storage import PersistentTaskStorage

# 监控告警
from .monitoring import (
    MetricsCollector,
    AlertManager,
    AlertRule,
    Alert,
    MetricType,
    AlertSeverity,
    AlertState,
)

# 主Skill类
from .skill import SchedulerSkill

__all__ = [
    # 数据模型
    "ErrorCode",
    "ErrorMessage",
    "TaskType",
    "TaskStatus",
    "TaskPriority",
    "WorkflowStatus",
    "BackupResult",
    "ScheduledTask",
    "TaskResult",
    "TaskNode",
    "TaskGraph",
    "PrioritizedTask",
    # 工具类
    "TimeoutExecutor",
    "CircuitBreaker",
    "CronParser",
    "NotificationManager",
    "DeadLetterQueueManager",
    # 备份管理
    "BackupManager",
    # 任务执行器
    "BaseTaskExecutor",
    "BackupExecutor",
    "AnalyzeExecutor",
    "VacuumExecutor",
    "ReindexExecutor",
    "CheckExecutor",
    "CustomSQLExecutor",
    "ExecutorFactory",
    # 分布式锁
    "DistributedLock",
    "RedisDistributedLock",
    "DatabaseDistributedLock",
    "FileDistributedLock",
    "LockManager",
    # 依赖管理
    "DependencyManager",
    # 调度引擎
    "SchedulerEngine",
    # 持久化存储
    "PersistentTaskStorage",
    # 监控告警
    "MetricsCollector",
    "AlertManager",
    "AlertRule",
    "Alert",
    "MetricType",
    "AlertSeverity",
    "AlertState",
    # 主Skill类
    "SchedulerSkill",
]

__version__ = "3.0.0"
