"""
db_scheduler/utils.py
工具类和辅助函数模块

文件功能：提供各种工具类和辅助函数
主要类：
    - TimeoutExecutor: 支持超时控制的任务执行器
    - CircuitBreaker: 熔断器（防止级联故障）
    - CronParser: Cron表达式解析器
    - NotificationManager: 通知管理器
    - DeadLetterQueueManager: 死信队列管理器

版本: 1.0.0
作者: AI Assistant
创建时间: 2026-04-23
"""

from typing import Dict, Any, List, Optional, Callable
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, Future, TimeoutError as FutureTimeoutError
from queue import PriorityQueue
import logging
import threading
import time
import json
import sqlite3
import re
import requests

from dbskiter.shared.error_handler import create_error_response, create_success_response
from .models import (
    ErrorCode, ScheduledTask, TaskResult, TaskStatus,
    TaskPriority, PrioritizedTask
)

logger = logging.getLogger(__name__)


# =============================================================================
# 超时控制执行器
# =============================================================================

class TimeoutExecutor:
    """
    支持超时控制的任务执行器

    使用示例:
        >>> with TimeoutExecutor(timeout=30) as executor:
        ...     result = executor.execute(long_running_task, args)
    """

    def __init__(self, timeout: int = 3600, max_workers: int = 4):
        """
        初始化超时执行器

        参数:
            timeout: 默认超时时间（秒）
            max_workers: 最大工作线程数
        """
        self.timeout = timeout
        self.max_workers = max_workers
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="timeout_")
        self._running_tasks: Dict[str, Future] = {}
        self._lock = threading.RLock()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.shutdown()
        return False

    def execute(self, func: Callable, task_id: str, *args, **kwargs) -> Any:
        """
        执行函数，带超时控制

        参数:
            func: 要执行的函数
            task_id: 任务ID（用于取消）
            *args, **kwargs: 函数参数

        返回:
            函数执行结果

        异常:
            TimeoutError: 任务超时
            Exception: 函数执行异常
        """
        with self._lock:
            if task_id in self._running_tasks:
                raise ValueError(f"任务 {task_id} 已在执行中")

            future = self._executor.submit(func, *args, **kwargs)
            self._running_tasks[task_id] = future

        try:
            result = future.result(timeout=self.timeout)
            return result
        except FutureTimeoutError:
            future.cancel()
            raise TimeoutError(f"任务 {task_id} 执行超时（超过 {self.timeout} 秒）")
        except Exception as e:
            raise e
        finally:
            with self._lock:
                self._running_tasks.pop(task_id, None)

    def cancel_task(self, task_id: str) -> bool:
        """取消正在执行的任务"""
        with self._lock:
            future = self._running_tasks.get(task_id)
            if future and not future.done():
                return future.cancel()
            return False

    def is_task_running(self, task_id: str) -> bool:
        """检查任务是否正在执行"""
        with self._lock:
            future = self._running_tasks.get(task_id)
            return future is not None and not future.done()

    def shutdown(self, wait: bool = True):
        """关闭执行器"""
        with self._lock:
            for task_id, future in list(self._running_tasks.items()):
                if not future.done():
                    future.cancel()
            self._running_tasks.clear()
        self._executor.shutdown(wait=wait)


# =============================================================================
# 熔断器
# =============================================================================

class CircuitBreaker:
    """熔断器 - 防止级联故障"""

    def __init__(self, threshold: int = 5, recovery_time: int = 60):
        """
        初始化熔断器

        参数:
            threshold: 失败阈值
            recovery_time: 恢复时间（秒）
        """
        self.threshold = threshold
        self.recovery_time = recovery_time
        self.failure_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.state = "closed"
        self._lock = threading.Lock()

    def can_execute(self) -> bool:
        """检查是否可以执行"""
        with self._lock:
            if self.state == "closed":
                return True
            elif self.state == "open":
                if self.last_failure_time:
                    elapsed = (datetime.now() - self.last_failure_time).total_seconds()
                    if elapsed >= self.recovery_time:
                        self.state = "half-open"
                        return True
                return False
            else:
                return True

    def record_success(self):
        """记录成功"""
        with self._lock:
            self.failure_count = 0
            self.state = "closed"

    def record_failure(self):
        """记录失败"""
        with self._lock:
            self.failure_count += 1
            self.last_failure_time = datetime.now()
            if self.failure_count >= self.threshold:
                self.state = "open"


# =============================================================================
# Cron表达式解析器
# =============================================================================

class CronParser:
    """Cron表达式解析器（简化版）"""

    @staticmethod
    def validate(cron_expr: str) -> bool:
        """
        验证Cron表达式是否有效

        参数:
            cron_expr: Cron表达式，格式: "分 时 日 月 周"

        返回:
            bool: 是否有效
        """
        parts = cron_expr.split()
        if len(parts) != 5:
            return False

        minute, hour, day, month, weekday = parts

        try:
            CronParser._parse_field(minute, 0, 59)
            CronParser._parse_field(hour, 0, 23)
            CronParser._parse_field(day, 1, 31)
            CronParser._parse_field(month, 1, 12)
            CronParser._parse_field(weekday, 0, 6)
            return True
        except ValueError:
            return False

    @staticmethod
    def _parse_field(field: str, min_val: int, max_val: int) -> List[int]:
        """解析单个字段"""
        values = []

        for part in field.split(','):
            if '/' in part:
                range_part, step = part.split('/')
                step = int(step)
            else:
                range_part = part
                step = 1

            if range_part == '*':
                start, end = min_val, max_val
            elif '-' in range_part:
                start, end = map(int, range_part.split('-'))
                # 验证范围
                if start < min_val or end > max_val or start > end:
                    raise ValueError(f"无效范围: {start}-{end}")
            else:
                start = end = int(range_part)
                # 验证单个值
                if start < min_val or start > max_val:
                    raise ValueError(f"无效值: {start}")

            values.extend(range(start, end + 1, step))

        return values

    @staticmethod
    def get_next_run(cron_expr: str, base_time: Optional[datetime] = None) -> Optional[datetime]:
        """
        计算下次执行时间

        参数:
            cron_expr: Cron表达式
            base_time: 基准时间（默认当前时间）

        返回:
            datetime: 下次执行时间
        """
        if not CronParser.validate(cron_expr):
            return None

        base = base_time or datetime.now()
        parts = cron_expr.split()

        minutes = CronParser._parse_field(parts[0], 0, 59)
        hours = CronParser._parse_field(parts[1], 0, 23)
        days = CronParser._parse_field(parts[2], 1, 31)
        months = CronParser._parse_field(parts[3], 1, 12)
        weekdays = CronParser._parse_field(parts[4], 0, 6)

        next_time = base + timedelta(minutes=1)
        next_time = next_time.replace(second=0, microsecond=0)

        for _ in range(366 * 24 * 60):
            if (next_time.month in months and
                next_time.day in days and
                next_time.weekday() in weekdays and
                next_time.hour in hours and
                next_time.minute in minutes):
                return next_time
            next_time += timedelta(minutes=1)

        return None

    @staticmethod
    def should_run(cron_expr: str, dt: datetime = None) -> bool:
        """
        检查是否应该在当前时间执行

        参数:
            cron_expr: Cron表达式
            dt: 指定时间（默认当前时间）

        返回:
            bool: 是否应该执行
        """
        if dt is None:
            dt = datetime.now()

        if not CronParser.validate(cron_expr):
            return False

        parts = cron_expr.split()
        minutes = CronParser._parse_field(parts[0], 0, 59)
        hours = CronParser._parse_field(parts[1], 0, 23)
        days = CronParser._parse_field(parts[2], 1, 31)
        months = CronParser._parse_field(parts[3], 1, 12)
        weekdays = CronParser._parse_field(parts[4], 0, 6)

        return (
            dt.minute in minutes and
            dt.hour in hours and
            dt.day in days and
            dt.month in months and
            dt.weekday() in weekdays
        )


# =============================================================================
# 通知管理器
# =============================================================================

class NotificationManager:
    """通知管理器 - 支持Webhook和邮件"""

    def __init__(self):
        self.webhooks: List[str] = []
        self.email_config: Optional[Dict] = None
        self._executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="notify_")

    def add_webhook(self, url: str):
        """添加Webhook地址"""
        self.webhooks.append(url)

    def set_email_config(self, smtp_host: str, smtp_port: int, username: str, password: str, use_tls: bool = True):
        """
        配置邮件服务器

        参数:
            smtp_host: SMTP服务器地址
            smtp_port: SMTP端口
            username: 用户名
            password: 密码（注意：生产环境应使用加密存储）
            use_tls: 是否使用TLS
        """
        self.email_config = {
            "host": smtp_host,
            "port": smtp_port,
            "username": username,
            "password": password,
            "use_tls": use_tls
        }

    def notify(self, message: str, context: Optional[Dict] = None):
        """
        发送通知

        参数:
            message: 消息内容
            context: 上下文信息
        """
        context = context or {}

        # 异步发送Webhook
        for webhook in self.webhooks:
            self._executor.submit(self._send_webhook, webhook, message, context)

        # 异步发送邮件
        if self.email_config:
            self._executor.submit(self._send_email, message, context)

    def _send_webhook(self, url: str, message: str, context: Dict):
        """发送Webhook通知"""
        try:
            payload = {
                "message": message,
                "timestamp": datetime.now().isoformat(),
                "context": context
            }
            response = requests.post(url, json=payload, timeout=10)
            response.raise_for_status()
            logger.debug(f"Webhook通知发送成功: {url}")
        except Exception as e:
            logger.error(f"Webhook通知发送失败: {url}, 错误: {e}")

    def _send_email(self, message: str, context: Dict):
        """发送邮件通知（简化版）"""
        if not self.email_config:
            return

        try:
            import smtplib
            from email.mime.text import MIMEText

            msg = MIMEText(f"{message}\n\n上下文: {json.dumps(context, indent=2, ensure_ascii=False)}")
            msg['Subject'] = f"[DBScheduler] {message[:50]}"
            msg['From'] = self.email_config['username']
            msg['To'] = self.email_config['username']

            with smtplib.SMTP(self.email_config['host'], self.email_config['port']) as server:
                if self.email_config['use_tls']:
                    server.starttls()
                server.login(self.email_config['username'], self.email_config['password'])
                server.send_message(msg)

            logger.debug("邮件通知发送成功")
        except Exception as e:
            logger.error(f"邮件通知发送失败: {e}")

    def shutdown(self):
        """关闭通知管理器"""
        self._executor.shutdown(wait=True)


# =============================================================================
# 死信队列管理器
# =============================================================================

class DeadLetterQueueManager:
    """
    死信队列管理器

    处理重试耗尽的任务，支持手动重试和告警
    """

    def __init__(self, db_path: str, notification: NotificationManager):
        """
        初始化死信队列管理器

        参数:
            db_path: 数据库路径
            notification: 通知管理器
        """
        self.db_path = db_path
        self.notification = notification
        self._lock = threading.RLock()
        self._conn: Optional[sqlite3.Connection] = None
        self._init_table()

    def _get_connection(self) -> sqlite3.Connection:
        """获取数据库连接"""
        if self._conn is None:
            self._conn = sqlite3.connect(self.db_path)
        return self._conn

    def close(self):
        """关闭数据库连接"""
        if self._conn:
            self._conn.close()
            self._conn = None

    def _init_table(self):
        """初始化死信队列表"""
        conn = self._get_connection()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS dead_letter_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id TEXT,
                task_name TEXT,
                task_type TEXT,
                params TEXT,
                error TEXT,
                retry_count INTEGER DEFAULT 0,
                max_retries INTEGER DEFAULT 3,
                failed_at TEXT,
                last_retry_at TEXT,
                status TEXT DEFAULT 'pending',
                resolved_at TEXT,
                resolution TEXT
            )
        """)
        conn.commit()

    def add_failed_task(self, task: ScheduledTask, error: str, retry_count: int):
        """添加失败任务到死信队列"""
        with self._lock:
            conn = self._get_connection()
            conn.execute(
                """
                INSERT INTO dead_letter_queue
                (task_id, task_name, task_type, params, error, retry_count, max_retries, failed_at, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task.task_id,
                    task.name,
                    task.task_type.value,
                    json.dumps(task.params),
                    error,
                    retry_count,
                    task.max_retries,
                    datetime.now().isoformat(),
                    'pending'
                )
            )
            conn.commit()

        # 发送告警通知
        self.notification.notify(
            f"任务进入死信队列: {task.name}",
            {
                "task_id": task.task_id,
                "task_name": task.name,
                "error": error,
                "retry_count": retry_count,
                "severity": "high"
            }
        )

        logger.warning(f"任务 {task.task_id} 已进入死信队列，重试次数: {retry_count}")

    def get_pending_tasks(self, limit: int = 50) -> List[Dict]:
        """获取待处理的死信队列任务"""
        conn = self._get_connection()
        cursor = conn.execute(
            "SELECT * FROM dead_letter_queue WHERE status = 'pending' ORDER BY failed_at DESC LIMIT ?",
            (limit,)
        )
        columns = [description[0] for description in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def retry_task(self, dlq_id: int) -> Dict[str, Any]:
        """重试死信队列中的任务"""
        conn = self._get_connection()
        cursor = conn.execute(
            "SELECT * FROM dead_letter_queue WHERE id = ? AND status = 'pending'",
            (dlq_id,)
        )
        row = cursor.fetchone()
        if not row:
            return create_error_response("任务不存在或状态不允许重试")

        conn.execute(
            "UPDATE dead_letter_queue SET last_retry_at = ?, status = 'retrying' WHERE id = ?",
            (datetime.now().isoformat(), dlq_id)
        )
        conn.commit()
        return create_success_response({"dlq_id": dlq_id, "status": "retrying"})

    def resolve_task(self, dlq_id: int, resolution: str) -> Dict[str, Any]:
        """标记任务为已解决"""
        conn = self._get_connection()
        conn.execute(
            "UPDATE dead_letter_queue SET status = 'resolved', resolved_at = ?, resolution = ? WHERE id = ?",
            (datetime.now().isoformat(), resolution, dlq_id)
        )
        conn.commit()
        return create_success_response({"dlq_id": dlq_id, "status": "resolved"})

    def get_statistics(self) -> Dict[str, int]:
        """获取死信队列统计"""
        conn = self._get_connection()
        cursor = conn.execute(
            "SELECT status, COUNT(*) FROM dead_letter_queue GROUP BY status"
        )
        stats = {row[0]: row[1] for row in cursor.fetchall()}

        return {
            "pending": stats.get('pending', 0),
            "resolved": stats.get('resolved', 0),
            "retrying": stats.get('retrying', 0),
            "total": sum(stats.values())
        }
