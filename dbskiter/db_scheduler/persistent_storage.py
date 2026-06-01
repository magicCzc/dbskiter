"""
持久化存储模块 - 简化版

文件功能：提供 SQLite 持久化存储
主要类：PersistentTaskStorage - SQLite 任务存储
"""
from typing import List, Optional
from datetime import datetime
import sqlite3
import json
import logging

logger = logging.getLogger(__name__)


class PersistentTaskStorage:
    """SQLite 持久化任务存储"""
    
    def __init__(self, db_path: str = "./runtime_data/scheduler/scheduler.db"):
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self) -> None:
        """初始化数据库"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    task_id TEXT PRIMARY KEY,
                    name TEXT,
                    schedule TEXT,
                    task_type TEXT,
                    params TEXT,
                    created_at TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS execution_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT,
                    status TEXT,
                    result TEXT,
                    executed_at TEXT
                )
            """)
            conn.commit()
    
    def save_task(self, task_id: str, task_data: dict) -> bool:
        """保存任务"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO tasks 
                    (task_id, name, schedule, task_type, params, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    task_id,
                    task_data.get('name', ''),
                    task_data.get('schedule', ''),
                    task_data.get('task_type', ''),
                    json.dumps(task_data.get('params', {})),
                    datetime.now().isoformat()
                ))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"保存任务失败: {e}")
            return False
    
    def get_task(self, task_id: str) -> Optional[dict]:
        """获取任务"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    "SELECT * FROM tasks WHERE task_id = ?", (task_id,)
                )
                row = cursor.fetchone()
                if row:
                    return {
                        'task_id': row[0],
                        'name': row[1],
                        'schedule': row[2],
                        'task_type': row[3],
                        'params': json.loads(row[4]) if row[4] else {},
                        'created_at': row[5]
                    }
                return None
        except Exception as e:
            logger.error(f"获取任务失败: {e}")
            return None
    
    def get_all_tasks(self) -> List[dict]:
        """获取所有任务"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("SELECT * FROM tasks")
                rows = cursor.fetchall()
                return [
                    {
                        'task_id': row[0],
                        'name': row[1],
                        'schedule': row[2],
                        'task_type': row[3],
                        'params': json.loads(row[4]) if row[4] else {},
                        'created_at': row[5]
                    }
                    for row in rows
                ]
        except Exception as e:
            logger.error(f"获取所有任务失败: {e}")
            return []
    
    def delete_task(self, task_id: str) -> bool:
        """删除任务"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("DELETE FROM tasks WHERE task_id = ?", (task_id,))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"删除任务失败: {e}")
            return False
    
    def save_execution(self, execution_data: dict) -> bool:
        """保存执行记录"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT INTO execution_history 
                    (task_id, status, result, executed_at)
                    VALUES (?, ?, ?, ?)
                """, (
                    execution_data.get('task_id', ''),
                    execution_data.get('status', ''),
                    json.dumps(execution_data.get('result', {})),
                    datetime.now().isoformat()
                ))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"保存执行记录失败: {e}")
            return False
    
    def get_execution_history(self, limit: int = 100) -> List[dict]:
        """获取执行历史"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    "SELECT * FROM execution_history ORDER BY id DESC LIMIT ?",
                    (limit,)
                )
                rows = cursor.fetchall()
                return [
                    {
                        'id': row[0],
                        'task_id': row[1],
                        'status': row[2],
                        'result': json.loads(row[3]) if row[3] else {},
                        'executed_at': row[4]
                    }
                    for row in rows
                ]
        except Exception as e:
            logger.error(f"获取执行历史失败: {e}")
            return []
