"""
任务结果清理机制

文件功能：自动清理过期的任务结果，防止内存和存储无限增长
主要类：
    - CleanupPolicy: 清理策略
    - ResultCleanupManager: 结果清理管理器
    - StorageCleanupManager: 存储清理管理器

特性：
1. 多维度清理 - 按数量、时间、状态清理
2. 归档支持 - 清理前可归档重要结果
3. 定时调度 - 支持自动定时清理
4. 保护机制 - 保护最近运行的任务不被清理
5. 统计报告 - 清理操作统计和报告

使用示例：
    from dbskiter.db_scheduler.result_cleanup import ResultCleanupManager, CleanupPolicy
    
    # 配置清理策略
    policy = CleanupPolicy(
        max_results_per_task=100,
        max_age_days=30,
        keep_failed=True
    )
    
    # 创建清理管理器
    cleanup = ResultCleanupManager(scheduler, policy=policy)
    
    # 手动清理
    stats = cleanup.cleanup()
    print(f"清理完成: 删除{stats.deleted_count}条记录")
    
    # 启动自动清理
    cleanup.start_auto_cleanup(interval_hours=24)

作者：AI Assistant
创建时间：2026-04-21
版本：1.0.0
"""

import logging
import time
import threading
import json
import shutil
from typing import Dict, List, Optional, Set, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from enum import Enum

logger = logging.getLogger(__name__)


# =============================================================================
# 数据类
# =============================================================================

class CleanupStrategy(Enum):
    """清理策略类型"""
    BY_COUNT = "by_count"           # 按数量清理
    BY_AGE = "by_age"               # 按时间清理
    BY_STATUS = "by_status"         # 按状态清理
    COMPREHENSIVE = "comprehensive" # 综合清理


@dataclass
class CleanupPolicy:
    """
    清理策略配置
    
    属性:
        strategy: 清理策略类型
        max_results_per_task: 每个任务保留的最大结果数
        max_age_days: 结果最大保留天数
        protected_statuses: 保护的状态（不清除）
        keep_failed: 是否保留失败结果
        keep_success: 是否保留成功结果
        archive_before_delete: 删除前是否归档
        archive_path: 归档路径
        min_free_space_gb: 最小剩余空间（GB），低于此值触发紧急清理
    """
    strategy: CleanupStrategy = CleanupStrategy.COMPREHENSIVE
    max_results_per_task: int = 100
    max_age_days: int = 30
    protected_statuses: Set[str] = field(default_factory=lambda: {"running", "pending"})
    keep_failed: bool = True
    keep_success: bool = False
    archive_before_delete: bool = False
    archive_path: str = "./archived_results"
    min_free_space_gb: float = 1.0
    
    def should_protect(self, status: str) -> bool:
        """检查状态是否受保护"""
        return status.lower() in self.protected_statuses


@dataclass
class CleanupStats:
    """清理统计"""
    start_time: datetime
    end_time: Optional[datetime] = None
    scanned_count: int = 0
    deleted_count: int = 0
    archived_count: int = 0
    protected_count: int = 0
    errors: List[str] = field(default_factory=list)
    
    @property
    def duration_seconds(self) -> float:
        if self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_seconds": self.duration_seconds,
            "scanned_count": self.scanned_count,
            "deleted_count": self.deleted_count,
            "archived_count": self.archived_count,
            "protected_count": self.protected_count,
            "errors": self.errors
        }


# =============================================================================
# 结果清理管理器
# =============================================================================

class ResultCleanupManager:
    """
    结果清理管理器
    
    管理任务执行结果的自动清理
    """
    
    def __init__(self, scheduler, policy: Optional[CleanupPolicy] = None):
        """
        初始化清理管理器
        
        参数:
            scheduler: 任务调度器实例
            policy: 清理策略
        """
        self.scheduler = scheduler
        self.policy = policy or CleanupPolicy()
        
        # 自动清理线程
        self._cleanup_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._running = False
        self._lock = threading.RLock()
        
        # 清理历史
        self._cleanup_history: List[CleanupStats] = []
        self._max_history_size = 100
    
    def cleanup(self, force: bool = False) -> CleanupStats:
        """
        执行清理
        
        参数:
            force: 是否强制清理（忽略保护状态）
            
        返回:
            CleanupStats: 清理统计
        """
        stats = CleanupStats(start_time=datetime.now())
        
        try:
            logger.info(f"开始清理任务结果，策略: {self.policy.strategy.value}")
            
            with self._lock:
                # 根据策略执行清理
                if self.policy.strategy == CleanupStrategy.BY_COUNT:
                    self._cleanup_by_count(stats, force)
                elif self.policy.strategy == CleanupStrategy.BY_AGE:
                    self._cleanup_by_age(stats, force)
                elif self.policy.strategy == CleanupStrategy.BY_STATUS:
                    self._cleanup_by_status(stats, force)
                else:  # COMPREHENSIVE
                    self._cleanup_comprehensive(stats, force)
                
                # 检查磁盘空间
                self._check_disk_space(stats)
            
            stats.end_time = datetime.now()
            self._add_to_history(stats)
            
            logger.info(f"清理完成: 扫描{stats.scanned_count}条，删除{stats.deleted_count}条，"
                       f"归档{stats.archived_count}条，保护{stats.protected_count}条")
            
            return stats
        
        except Exception as e:
            logger.error(f"清理过程异常: {e}")
            stats.errors.append(str(e))
            stats.end_time = datetime.now()
            return stats
    
    def _cleanup_by_count(self, stats: CleanupStats, force: bool):
        """按数量清理"""
        # 按任务分组统计结果
        task_results: Dict[str, List[str]] = {}
        
        for task_id, result in self.scheduler.task_results.items():
            stats.scanned_count += 1
            
            if task_id not in task_results:
                task_results[task_id] = []
            task_results[task_id].append(task_id)
        
        # 对每个任务，保留最新的N个结果
        for task_id, result_ids in task_results.items():
            if len(result_ids) > self.policy.max_results_per_task:
                # 按时间排序（假设task_id包含时间信息）
                sorted_ids = sorted(result_ids, reverse=True)
                to_delete = sorted_ids[self.policy.max_results_per_task:]
                
                for result_id in to_delete:
                    if self._can_delete(result_id, force):
                        self._delete_result(result_id, stats)
    
    def _cleanup_by_age(self, stats: CleanupStats, force: bool):
        """按时间清理"""
        cutoff_time = datetime.now() - timedelta(days=self.policy.max_age_days)
        
        for task_id, result in list(self.scheduler.task_results.items()):
            stats.scanned_count += 1
            
            # 检查结果年龄
            result_time = getattr(result, 'end_time', None)
            if result_time and result_time < cutoff_time:
                if self._can_delete(task_id, force):
                    self._delete_result(task_id, stats)
    
    def _cleanup_by_status(self, stats: CleanupStats, force: bool):
        """按状态清理"""
        for task_id, result in list(self.scheduler.task_results.items()):
            stats.scanned_count += 1
            
            status = getattr(result, 'status', None)
            if status:
                status_value = status.value if hasattr(status, 'value') else str(status)
                
                # 根据配置决定是否删除
                should_delete = False
                if status_value == "success" and not self.policy.keep_success:
                    should_delete = True
                elif status_value == "failed" and not self.policy.keep_failed:
                    should_delete = True
                
                if should_delete and self._can_delete(task_id, force):
                    self._delete_result(task_id, stats)
    
    def _cleanup_comprehensive(self, stats: CleanupStats, force: bool):
        """综合清理"""
        cutoff_time = datetime.now() - timedelta(days=self.policy.max_age_days)
        
        # 按任务分组
        task_results: Dict[str, List[tuple]] = {}
        
        for task_id, result in self.scheduler.task_results.items():
            stats.scanned_count += 1
            
            # 获取任务ID（去掉时间戳部分）
            base_task_id = task_id.split('_')[0] if '_' in task_id else task_id
            
            if base_task_id not in task_results:
                task_results[base_task_id] = []
            
            result_time = getattr(result, 'end_time', datetime.now())
            task_results[base_task_id].append((task_id, result, result_time))
        
        # 对每个任务进行清理
        for base_task_id, results in task_results.items():
            # 按时间排序（最新的在前）
            sorted_results = sorted(results, key=lambda x: x[2], reverse=True)
            
            for i, (task_id, result, result_time) in enumerate(sorted_results):
                should_delete = False
                
                # 检查数量限制
                if i >= self.policy.max_results_per_task:
                    should_delete = True
                
                # 检查时间限制
                if result_time < cutoff_time:
                    should_delete = True
                
                # 检查状态
                status = getattr(result, 'status', None)
                if status:
                    status_value = status.value if hasattr(status, 'value') else str(status)
                    if status_value == "success" and not self.policy.keep_success:
                        should_delete = True
                    elif status_value == "failed" and not self.policy.keep_failed:
                        should_delete = True
                
                if should_delete and self._can_delete(task_id, force):
                    self._delete_result(task_id, stats)
    
    def _can_delete(self, task_id: str, force: bool) -> bool:
        """检查是否可以删除"""
        if force:
            return True
        
        # 检查任务当前状态
        task_status = self.scheduler.get_task_status(task_id)
        if task_status:
            status_value = task_status.value if hasattr(task_status, 'value') else str(task_status)
            if self.policy.should_protect(status_value):
                return False
        
        return True
    
    def _delete_result(self, task_id: str, stats: CleanupStats):
        """删除结果"""
        try:
            # 先归档（如果启用）
            if self.policy.archive_before_delete:
                if self._archive_result(task_id):
                    stats.archived_count += 1
            
            # 从内存中删除
            if task_id in self.scheduler.task_results:
                del self.scheduler.task_results[task_id]
            
            # 从已完成集合中移除
            if task_id in self.scheduler.completed_tasks:
                self.scheduler.completed_tasks.remove(task_id)
            
            stats.deleted_count += 1
            logger.debug(f"删除结果: {task_id}")
        
        except Exception as e:
            logger.error(f"删除结果失败: {task_id}, 错误: {e}")
            stats.errors.append(f"删除{task_id}失败: {e}")
    
    def _archive_result(self, task_id: str) -> bool:
        """归档结果"""
        try:
            result = self.scheduler.task_results.get(task_id)
            if not result:
                return False
            
            # 创建归档目录
            archive_dir = Path(self.policy.archive_path)
            archive_dir.mkdir(parents=True, exist_ok=True)
            
            # 生成归档文件名
            timestamp = datetime.now().strftime("%Y%m%d")
            archive_file = archive_dir / f"{task_id}_{timestamp}.json"
            
            # 保存结果
            with open(archive_file, 'w', encoding='utf-8') as f:
                json.dump(result.to_dict() if hasattr(result, 'to_dict') else str(result), 
                         f, ensure_ascii=False, indent=2)
            
            logger.debug(f"归档结果: {task_id} -> {archive_file}")
            return True
        
        except Exception as e:
            logger.error(f"归档结果失败: {task_id}, 错误: {e}")
            return False
    
    def _check_disk_space(self, stats: CleanupStats):
        """检查磁盘空间，必要时进行紧急清理"""
        try:
            import shutil
            
            # 获取存储路径的磁盘使用情况
            storage_path = Path(self.scheduler.config.storage_path)
            if not storage_path.exists():
                return
            
            disk_usage = shutil.disk_usage(storage_path)
            free_space_gb = disk_usage.free / (1024 ** 3)
            
            if free_space_gb < self.policy.min_free_space_gb:
                logger.warning(f"磁盘空间不足: {free_space_gb:.2f}GB < {self.policy.min_free_space_gb}GB，"
                              f"触发紧急清理")
                
                # 紧急清理：删除所有非保护状态的结果
                emergency_deleted = 0
                for task_id in list(self.scheduler.task_results.keys()):
                    if self._can_delete(task_id, force=False):
                        self._delete_result(task_id, stats)
                        emergency_deleted += 1
                
                logger.info(f"紧急清理完成: 删除{emergency_deleted}条记录")
        
        except Exception as e:
            logger.error(f"检查磁盘空间失败: {e}")
    
    def _add_to_history(self, stats: CleanupStats):
        """添加到历史记录"""
        self._cleanup_history.append(stats)
        
        # 限制历史记录大小
        if len(self._cleanup_history) > self._max_history_size:
            self._cleanup_history = self._cleanup_history[-self._max_history_size:]
    
    def start_auto_cleanup(self, interval_hours: int = 24):
        """
        启动自动清理
        
        参数:
            interval_hours: 清理间隔（小时）
        """
        if self._running:
            logger.warning("自动清理已在运行")
            return
        
        self._running = True
        self._stop_event.clear()
        
        def cleanup_loop():
            while not self._stop_event.is_set():
                try:
                    # 执行清理
                    self.cleanup()
                except Exception as e:
                    logger.error(f"自动清理异常: {e}")
                
                # 等待下一次清理
                # 使用小间隔检查停止信号
                for _ in range(interval_hours * 3600):
                    if self._stop_event.is_set():
                        break
                    time.sleep(1)
        
        self._cleanup_thread = threading.Thread(target=cleanup_loop, daemon=True)
        self._cleanup_thread.start()
        
        logger.info(f"自动清理已启动，间隔: {interval_hours}小时")
    
    def stop_auto_cleanup(self):
        """停止自动清理"""
        if not self._running:
            return
        
        self._running = False
        self._stop_event.set()
        
        if self._cleanup_thread:
            self._cleanup_thread.join(timeout=10)
        
        logger.info("自动清理已停止")
    
    def get_cleanup_history(self, limit: int = 10) -> List[CleanupStats]:
        """
        获取清理历史
        
        参数:
            limit: 返回最近N条记录
            
        返回:
            List[CleanupStats]: 清理历史
        """
        return self._cleanup_history[-limit:]
    
    def get_storage_stats(self) -> Dict[str, Any]:
        """
        获取存储统计
        
        返回:
            Dict: 存储统计信息
        """
        total_results = len(self.scheduler.task_results)
        completed_tasks = len(self.scheduler.completed_tasks)
        
        # 按状态统计
        status_count = {}
        for result in self.scheduler.task_results.values():
            status = getattr(result, 'status', 'unknown')
            status_value = status.value if hasattr(status, 'value') else str(status)
            status_count[status_value] = status_count.get(status_value, 0) + 1
        
        # 计算存储大小
        storage_size_mb = 0
        try:
            import os
            storage_path = Path(self.scheduler.config.storage_path)
            if storage_path.exists():
                total_size = sum(
                    f.stat().st_size for f in storage_path.rglob('*') if f.is_file()
                )
                storage_size_mb = total_size / (1024 * 1024)
        except Exception as e:
            logger.warning(f"计算存储大小失败: {e}")
        
        return {
            "total_results": total_results,
            "completed_tasks": completed_tasks,
            "status_distribution": status_count,
            "storage_size_mb": round(storage_size_mb, 2),
            "policy": {
                "max_results_per_task": self.policy.max_results_per_task,
                "max_age_days": self.policy.max_age_days,
                "keep_failed": self.policy.keep_failed,
                "keep_success": self.policy.keep_success
            }
        }


# =============================================================================
# 存储清理管理器
# =============================================================================

class StorageCleanupManager:
    """
    存储清理管理器
    
    专门清理持久化存储中的过期数据
    """
    
    def __init__(self, storage, policy: Optional[CleanupPolicy] = None):
        """
        初始化存储清理管理器
        
        参数:
            storage: 存储实例
            policy: 清理策略
        """
        self.storage = storage
        self.policy = policy or CleanupPolicy()
    
    def cleanup_storage(self) -> CleanupStats:
        """
        清理存储
        
        返回:
            CleanupStats: 清理统计
        """
        stats = CleanupStats(start_time=datetime.now())
        
        try:
            # 清理过期的任务结果
            self._cleanup_task_results(stats)
            
            # 清理过期的任务记录
            self._cleanup_task_records(stats)
            
            # 清理孤儿记录
            self._cleanup_orphan_records(stats)
            
            stats.end_time = datetime.now()
            
            logger.info(f"存储清理完成: 扫描{stats.scanned_count}条，删除{stats.deleted_count}条")
            
            return stats
        
        except Exception as e:
            logger.error(f"存储清理异常: {e}")
            stats.errors.append(str(e))
            stats.end_time = datetime.now()
            return stats
    
    def _cleanup_task_results(self, stats: CleanupStats):
        """清理任务结果表"""
        try:
            import sqlite3
            
            cutoff_time = datetime.now() - timedelta(days=self.policy.max_age_days)
            cutoff_str = cutoff_time.isoformat()
            
            with sqlite3.connect(self.storage.db_path) as conn:
                # 统计要删除的记录
                cursor = conn.execute(
                    "SELECT COUNT(*) FROM task_results WHERE end_time < ?",
                    (cutoff_str,)
                )
                count = cursor.fetchone()[0]
                
                # 删除过期记录
                conn.execute(
                    "DELETE FROM task_results WHERE end_time < ?",
                    (cutoff_str,)
                )
                conn.commit()
                
                stats.scanned_count += count
                stats.deleted_count += count
                
                logger.debug(f"清理任务结果: {count}条")
        
        except Exception as e:
            logger.error(f"清理任务结果失败: {e}")
            stats.errors.append(f"清理任务结果失败: {e}")
    
    def _cleanup_task_records(self, stats: CleanupStats):
        """清理任务记录表"""
        try:
            import sqlite3
            
            # 清理已取消或已完成的过期任务
            cutoff_time = datetime.now() - timedelta(days=self.policy.max_age_days)
            cutoff_str = cutoff_time.isoformat()
            
            with sqlite3.connect(self.storage.db_path) as conn:
                cursor = conn.execute(
                    """DELETE FROM tasks 
                       WHERE status IN ('cancelled', 'success', 'failed') 
                       AND completed_at < ?""",
                    (cutoff_str,)
                )
                deleted = cursor.rowcount
                conn.commit()
                
                stats.deleted_count += deleted
                
                logger.debug(f"清理任务记录: {deleted}条")
        
        except Exception as e:
            logger.error(f"清理任务记录失败: {e}")
            stats.errors.append(f"清理任务记录失败: {e}")
    
    def _cleanup_orphan_records(self, stats: CleanupStats):
        """清理孤儿记录（结果没有对应的任务）"""
        try:
            import sqlite3
            
            with sqlite3.connect(self.storage.db_path) as conn:
                # 删除没有对应任务的结果记录
                cursor = conn.execute("""
                    DELETE FROM task_results
                    WHERE task_id NOT IN (SELECT task_id FROM tasks)
                """)
                deleted = cursor.rowcount
                conn.commit()
                
                if deleted > 0:
                    stats.deleted_count += deleted
                    logger.debug(f"清理孤儿记录: {deleted}条")
        
        except Exception as e:
            logger.error(f"清理孤儿记录失败: {e}")
            stats.errors.append(f"清理孤儿记录失败: {e}")
    
    def vacuum_storage(self):
        """压缩存储（回收空间）"""
        try:
            import sqlite3
            
            with sqlite3.connect(self.storage.db_path) as conn:
                conn.execute("VACUUM")
                conn.commit()
            
            logger.info("存储压缩完成")
        
        except Exception as e:
            logger.error(f"存储压缩失败: {e}")
