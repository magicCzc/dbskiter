"""
调度引擎模块 - 简化版

文件功能：提供 Cron 调度和任务执行引擎
主要类：SchedulerEngine - 调度引擎
"""
from typing import Dict, List, Optional, Callable
from datetime import datetime
import threading
import time
import logging

from .utils import CronParser

logger = logging.getLogger(__name__)


class SchedulerEngine:
    """调度引擎"""
    
    def __init__(self):
        self.tasks: Dict[str, Dict] = {}
        self.handlers: Dict[str, Callable] = {}
        self.running = False
        self.thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
    
    def register_handler(self, task_type: str, handler: Callable):
        """注册任务处理器"""
        self.handlers[task_type] = handler
        logger.info(f"注册任务处理器: {task_type}")
    
    def add_task(self, task_id: str, cron_expr: str, callback: Callable, **kwargs) -> bool:
        """添加任务"""
        with self._lock:
            self.tasks[task_id] = {
                'cron': cron_expr,
                'callback': callback,
                'kwargs': kwargs,
                'last_run': None
            }
        logger.info(f"添加任务: {task_id}, Cron: {cron_expr}")
        return True
    
    def remove_task(self, task_id: str) -> bool:
        """移除任务"""
        with self._lock:
            if task_id in self.tasks:
                del self.tasks[task_id]
                return True
        return False
    
    def start(self) -> None:
        """启动调度器"""
        if self.running:
            return
        
        self.running = True
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()
        logger.info("调度引擎已启动")
    
    def stop(self) -> None:
        """停止调度器"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
        logger.info("调度引擎已停止")
    
    def _run_loop(self) -> None:
        """主循环"""
        while self.running:
            try:
                now = datetime.now()
                
                with self._lock:
                    tasks_copy = dict(self.tasks)
                
                for task_id, task in tasks_copy.items():
                    if CronParser.should_run(task['cron'], now):
                        if task['last_run'] is None or task['last_run'].minute != now.minute:
                            self._execute_task(task_id, task)
                
                time.sleep(30)  # 每 30 秒检查一次
                
            except Exception as e:
                logger.error(f"调度循环错误: {e}")
                time.sleep(60)
    
    def _execute_task(self, task_id: str, task: Dict) -> None:
        """执行任务"""
        logger.info(f"执行任务: {task_id}")
        task['last_run'] = datetime.now()
        
        try:
            callback = task['callback']
            kwargs = task['kwargs']
            callback(**kwargs)
        except Exception as e:
            logger.error(f"任务执行失败 {task_id}: {e}")
    
    def get_task_list(self) -> List[Dict]:
        """获取任务列表"""
        with self._lock:
            return [
                {
                    'task_id': tid,
                    'cron': task['cron'],
                    'last_run': task['last_run']
                }
                for tid, task in self.tasks.items()
            ]
