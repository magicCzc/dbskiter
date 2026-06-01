"""
任务存储模块 - 简化版

文件功能：提供内存中的任务存储
主要类：TaskStorage - 内存任务存储
"""
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


class TaskStorage:
    """内存任务存储"""
    
    def __init__(self):
        self.tasks: Dict[str, dict] = {}
        self.history: List[dict] = []
    
    def save_task(self, task_id: str, task_data: dict) -> bool:
        """保存任务"""
        self.tasks[task_id] = task_data
        return True
    
    def get_task(self, task_id: str) -> Optional[dict]:
        """获取任务"""
        return self.tasks.get(task_id)
    
    def get_all_tasks(self) -> List[dict]:
        """获取所有任务"""
        return list(self.tasks.values())
    
    def delete_task(self, task_id: str) -> bool:
        """删除任务"""
        if task_id in self.tasks:
            del self.tasks[task_id]
            return True
        return False
    
    def save_execution(self, execution_data: dict) -> bool:
        """保存执行记录"""
        self.history.append(execution_data)
        return True
    
    def get_execution_history(self, limit: int = 100) -> List[dict]:
        """获取执行历史"""
        return self.history[-limit:]
