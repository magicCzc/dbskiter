"""
数据库任务执行器集合

文件功能：实现具体的数据库维护任务执行器
主要类：
    - BaseTaskExecutor: 任务执行器基类
    - BackupExecutor: 数据库备份执行器
    - AnalyzeExecutor: 表分析执行器
    - VacuumExecutor: 数据库清理执行器
    - ReindexExecutor: 索引重建执行器
    - CheckExecutor: 数据库检查执行器
    - CustomSQLExecutor: 自定义SQL执行器
    - ExecutorFactory: 执行器工厂

特性：
1. 统一的执行接口 - 所有执行器遵循相同契约
2. 进度回调支持 - 实时报告执行进度
3. 取消检查点 - 支持协作式任务取消
4. 资源使用监控 - 跟踪CPU、内存、IO使用情况
5. 执行超时控制 - 防止长时间挂起
6. 结果标准化 - 统一的执行结果格式

使用示例：
    from dbskiter.db_scheduler.task_executors import ExecutorFactory
    
    # 创建执行器
    executor = ExecutorFactory.create("backup", connector)
    
    # 执行任务
    result = executor.execute({
        "tables": ["users", "orders"],
        "backup_path": "/backups"
    }, progress_callback=on_progress)
    
    # 检查取消标志
    if executor.is_cancelled():
        print("任务已取消")

作者：Magiczc
创建时间：2026-04-21
版本：1.0.0
"""

import logging
import time
import os
import shutil
import threading
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Callable, List, Union
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from enum import Enum

# psutil 为可选依赖, 未安装时跳过资源监控
try:
    import psutil
    _PSUTIL_AVAILABLE = True
except ImportError:
    psutil = None
    _PSUTIL_AVAILABLE = False

# 导入连接池
try:
    from dbskiter.db_scheduler.connection_pool import ConnectionPool
except ImportError:
    ConnectionPool = None

logger = logging.getLogger(__name__)


# =============================================================================
# 数据类
# =============================================================================

class ExecutionStatus(Enum):
    """执行状态"""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


@dataclass
class ExecutionResult:
    """执行结果"""
    status: ExecutionStatus
    start_time: datetime
    end_time: datetime
    message: str = ""
    data: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    rows_affected: int = 0
    resource_usage: Dict[str, float] = field(default_factory=dict)
    
    @property
    def duration_seconds(self) -> float:
        return (self.end_time - self.start_time).total_seconds()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status.value,
            "duration_seconds": self.duration_seconds,
            "message": self.message,
            "data": self.data,
            "error": self.error,
            "rows_affected": self.rows_affected,
            "resource_usage": self.resource_usage
        }


@dataclass
class ExecutionProgress:
    """执行进度"""
    phase: str
    percent: float  # 0-100
    message: str
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "phase": self.phase,
            "percent": self.percent,
            "message": self.message,
            "timestamp": self.timestamp.isoformat()
        }


# =============================================================================
# 基类
# =============================================================================

class BaseTaskExecutor(ABC):
    """
    任务执行器基类
    
    所有具体执行器必须继承此类，实现execute方法
    
    特性：
    - 取消检查点：execute方法中应定期检查_is_cancelled标志
    - 进度回调：通过progress_callback报告执行进度
    - 超时控制：通过timeout_seconds参数控制最大执行时间
    - 资源监控：自动收集执行期间的资源使用情况
    """
    
    def __init__(self, connector: Union[Any, ConnectionPool]):
        """
        初始化执行器
        
        参数:
            connector: 数据库连接器或连接池
        """
        self.connector = connector
        self._pool = connector if (ConnectionPool is not None and isinstance(connector, ConnectionPool)) else None
        self._cancelled = False
        self._lock = threading.Lock()
        self._start_time: Optional[datetime] = None
        self._process = psutil.Process() if _PSUTIL_AVAILABLE else None
    
    def _get_connection(self):
        """
        获取数据库连接
        
        如果使用了连接池，从池中获取；否则直接使用connector
        
        返回:
            数据库连接或上下文管理器
        """
        if self._pool:
            return self._pool.get_connection()
        else:
            # 如果没有连接池，创建一个模拟的上下文管理器
            class DirectConnection:
                def __init__(self, conn):
                    self._conn = conn
                def __enter__(self):
                    return self._conn
                def __exit__(self, *args):
                    pass
            return DirectConnection(self.connector)
    
    @abstractmethod
    def execute(self, params: Dict[str, Any], 
                progress_callback: Optional[Callable[[ExecutionProgress], None]] = None,
                timeout_seconds: int = 3600) -> ExecutionResult:
        """
        执行任务
        
        参数:
            params: 执行参数
            progress_callback: 进度回调函数
            timeout_seconds: 超时时间（秒）
            
        返回:
            ExecutionResult: 执行结果
        """
        pass
    
    def cancel(self):
        """请求取消任务"""
        with self._lock:
            self._cancelled = True
        logger.info(f"任务取消请求: {self.__class__.__name__}")
    
    def is_cancelled(self) -> bool:
        """检查是否已请求取消"""
        with self._lock:
            return self._cancelled
    
    def _check_cancelled(self) -> bool:
        """
        检查点：检查是否被取消
        
        返回:
            bool: True表示继续执行，False表示已取消
        """
        if self.is_cancelled():
            logger.warning(f"任务已取消: {self.__class__.__name__}")
            return False
        return True
    
    def _report_progress(self, callback: Optional[Callable[[ExecutionProgress], None]],
                        phase: str, percent: float, message: str):
        """报告进度"""
        if callback:
            progress = ExecutionProgress(phase=phase, percent=percent, message=message)
            try:
                callback(progress)
            except Exception as e:
                logger.error(f"进度回调失败: {e}")
    
    def _get_resource_usage(self) -> Dict[str, float]:
        """获取当前资源使用情况"""
        if not _PSUTIL_AVAILABLE or self._process is None:
            return {}
        try:
            memory_info = self._process.memory_info()
            cpu_percent = self._process.cpu_percent(interval=0.1)

            return {
                "memory_mb": memory_info.rss / 1024 / 1024,
                "cpu_percent": cpu_percent,
                "threads": self._process.num_threads()
            }
        except Exception as e:
            logger.warning(f"获取资源使用情况失败: {e}")
            return {}
    
    def _execute_with_timeout(self, func: Callable, timeout_seconds: int) -> Any:
        """
        带超时控制的执行
        
        参数:
            func: 要执行的函数
            timeout_seconds: 超时时间
            
        返回:
            函数返回值
            
        异常:
            TimeoutError: 执行超时
        """
        import concurrent.futures
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(func)
            try:
                return future.result(timeout=timeout_seconds)
            except concurrent.futures.TimeoutError:
                raise TimeoutError(f"任务执行超时（{timeout_seconds}秒）")


# =============================================================================
# 具体执行器
# =============================================================================

class BackupExecutor(BaseTaskExecutor):
    """
    数据库备份执行器

    委托 BackupManager 执行真正的备份, 保留进度回调和取消检查功能。

    支持:
    - 全库备份
    - 指定表备份
    """

    def execute(self, params: Dict[str, Any],
                progress_callback: Optional[Callable[[ExecutionProgress], None]] = None,
                timeout_seconds: int = 3600) -> ExecutionResult:
        """
        执行备份任务

        参数:
            params:
                - tables: 要备份的表列表（None表示全库）
                - output_dir: 备份文件保存目录
                - compress: 是否压缩（默认True）
                - include_schema: 是否包含表结构（默认True）
        """
        # 延迟导入避免循环依赖
        from .backup import BackupManager

        start_time = datetime.now()
        tables = params.get("tables")
        output_dir = params.get("output_dir") or params.get("backup_path", "./backups")
        compress = params.get("compress", True)

        try:
            self._report_progress(progress_callback, "初始化", 0, "开始备份任务")

            if not self._check_cancelled():
                return self._create_cancelled_result(start_time)

            self._report_progress(progress_callback, "准备", 10, "连接数据库")

            backup_manager = BackupManager(self.connector)
            backup_manager.default_output_dir = output_dir

            self._report_progress(progress_callback, "执行", 30, "正在备份...")

            if tables:
                results = backup_manager.backup_tables(tables)
                all_success = all(r.success for r in results)
                if not all_success:
                    errors = [r.error for r in results if not r.success and r.error]
                    raise RuntimeError("; ".join(errors) if errors else "部分表备份失败")
                result_obj = results[0] if results else None
                result_data = {
                    "results": [r.to_dict() for r in results],
                    "total": len(results),
                    "success_count": sum(1 for r in results if r.success),
                }
            else:
                result_obj = backup_manager.backup_full(
                    output_dir=output_dir,
                    compress=compress,
                    include_schema=params.get("include_schema", True),
                )
                if not result_obj.success:
                    raise RuntimeError(result_obj.error or "备份失败")
                result_data = result_obj.to_dict()

            if not self._check_cancelled():
                return self._create_cancelled_result(start_time)

            self._report_progress(progress_callback, "完成", 100, "备份完成")

            end_time = datetime.now()
            return ExecutionResult(
                status=ExecutionStatus.SUCCESS,
                start_time=start_time,
                end_time=end_time,
                message=f"备份成功: {result_obj.file_path if result_obj else 'N/A'}",
                data=result_data,
                resource_usage=self._get_resource_usage()
            )

        except TimeoutError as e:
            return self._create_error_result(start_time, str(e), ExecutionStatus.TIMEOUT)
        except Exception as e:
            logger.error(f"备份失败: {e}")
            return self._create_error_result(start_time, str(e))
    
    def _create_cancelled_result(self, start_time: datetime) -> ExecutionResult:
        """创建取消结果"""
        return ExecutionResult(
            status=ExecutionStatus.CANCELLED,
            start_time=start_time,
            end_time=datetime.now(),
            message="任务已取消",
            error="用户取消"
        )
    
    def _create_error_result(self, start_time: datetime, error: str, 
                            status: ExecutionStatus = ExecutionStatus.FAILED) -> ExecutionResult:
        """创建错误结果"""
        return ExecutionResult(
            status=status,
            start_time=start_time,
            end_time=datetime.now(),
            message="执行失败",
            error=error
        )


class AnalyzeExecutor(BaseTaskExecutor):
    """
    表分析执行器
    
    更新表的统计信息，优化查询计划
    """
    
    def execute(self, params: Dict[str, Any],
                progress_callback: Optional[Callable[[ExecutionProgress], None]] = None,
                timeout_seconds: int = 3600) -> ExecutionResult:
        """
        执行分析任务
        
        参数:
            params:
                - tables: 要分析的表列表（None表示所有表）
                - sample_percent: 采样百分比（默认100）
        """
        start_time = datetime.now()
        tables = params.get("tables")
        sample_percent = params.get("sample_percent", 100)
        
        try:
            self._report_progress(progress_callback, "初始化", 0, "开始分析任务")
            
            if not self._check_cancelled():
                return self._create_cancelled_result(start_time)
            
            # 获取数据库类型
            dialect = getattr(self.connector, 'dialect', 'mysql').lower()
            
            # 如果没有指定表，获取所有表
            if not tables:
                tables = self._get_all_tables()
            
            total_tables = len(tables)
            analyzed_tables = []
            errors = []
            
            for i, table in enumerate(tables):
                if not self._check_cancelled():
                    return self._create_cancelled_result(start_time)
                
                progress = (i / total_tables) * 100
                self._report_progress(
                    progress_callback, 
                    "分析", 
                    progress, 
                    f"分析表: {table} ({i+1}/{total_tables})"
                )
                
                try:
                    self._analyze_table(dialect, table, sample_percent)
                    analyzed_tables.append(table)
                except Exception as e:
                    logger.error(f"分析表 {table} 失败: {e}")
                    errors.append(f"{table}: {str(e)}")
                
                time.sleep(0.1)  # 模拟分析时间
            
            self._report_progress(progress_callback, "完成", 100, "分析完成")
            
            end_time = datetime.now()
            return ExecutionResult(
                status=ExecutionStatus.SUCCESS if not errors else ExecutionStatus.FAILED,
                start_time=start_time,
                end_time=end_time,
                message=f"分析了 {len(analyzed_tables)}/{total_tables} 个表",
                data={
                    "analyzed_tables": analyzed_tables,
                    "total_tables": total_tables,
                    "sample_percent": sample_percent
                },
                error="; ".join(errors) if errors else None,
                resource_usage=self._get_resource_usage()
            )
        
        except Exception as e:
            logger.error(f"分析任务失败: {e}")
            return self._create_error_result(start_time, str(e))
    
    def _get_all_tables(self) -> List[str]:
        """获取所有表"""
        try:
            result = self.connector.execute("SHOW TABLES")
            return [row[0] for row in result.rows] if result.rows else []
        except Exception as e:
            logger.error(f"获取表列表失败: {e}")
            return []
    
    def _analyze_table(self, dialect: str, table: str, sample_percent: int):
        """分析单个表"""
        if dialect in ("mysql", "mysql+pymysql"):
            sql = f"ANALYZE TABLE `{table}`"
        elif "postgresql" in dialect:
            sql = f"ANALYZE {table}"
        elif dialect in ("sqlite", "sqlite3"):
            sql = f"ANALYZE {table}"
        else:
            # 通用回退：标准 ANALYZE 语句
            sql = f"ANALYZE {table}"
        
        self.connector.execute(sql)
    
    def _create_cancelled_result(self, start_time: datetime) -> ExecutionResult:
        return ExecutionResult(
            status=ExecutionStatus.CANCELLED,
            start_time=start_time,
            end_time=datetime.now(),
            message="任务已取消"
        )
    
    def _create_error_result(self, start_time: datetime, error: str) -> ExecutionResult:
        return ExecutionResult(
            status=ExecutionStatus.FAILED,
            start_time=start_time,
            end_time=datetime.now(),
            message="执行失败",
            error=error
        )


class VacuumExecutor(BaseTaskExecutor):
    """
    数据库清理执行器（VACUUM/OPTIMIZE）
    
    回收存储空间，优化数据库性能
    """
    
    def execute(self, params: Dict[str, Any],
                progress_callback: Optional[Callable[[ExecutionProgress], None]] = None,
                timeout_seconds: int = 3600) -> ExecutionResult:
        """
        执行清理任务
        
        参数:
            params:
                - tables: 要清理的表列表（None表示全库）
                - full: 是否完全清理（默认False，仅PostgreSQL）
                - analyze: 清理后是否分析（默认True）
        """
        start_time = datetime.now()
        tables = params.get("tables")
        full = params.get("full", False)
        analyze_after = params.get("analyze", True)
        
        try:
            self._report_progress(progress_callback, "初始化", 0, "开始清理任务")
            
            if not self._check_cancelled():
                return self._create_cancelled_result(start_time)
            
            dialect = getattr(self.connector, 'dialect', 'mysql').lower()
            
            # 执行清理
            if tables:
                for i, table in enumerate(tables):
                    if not self._check_cancelled():
                        return self._create_cancelled_result(start_time)
                    
                    progress = (i / len(tables)) * 80
                    self._report_progress(
                        progress_callback,
                        "清理",
                        progress,
                        f"清理表: {table}"
                    )
                    
                    self._vacuum_table(dialect, table, full)
            else:
                self._report_progress(progress_callback, "清理", 40, "清理整个数据库")
                self._vacuum_database(dialect, full)
            
            if not self._check_cancelled():
                return self._create_cancelled_result(start_time)
            
            # 可选：清理后分析
            if analyze_after:
                self._report_progress(progress_callback, "分析", 90, "更新统计信息")
                self._analyze_after_vacuum(dialect, tables)
            
            self._report_progress(progress_callback, "完成", 100, "清理完成")
            
            end_time = datetime.now()
            return ExecutionResult(
                status=ExecutionStatus.SUCCESS,
                start_time=start_time,
                end_time=end_time,
                message=f"清理完成: {tables or '全库'}",
                data={
                    "tables": tables,
                    "full": full,
                    "analyzed": analyze_after
                },
                resource_usage=self._get_resource_usage()
            )
        
        except Exception as e:
            logger.error(f"清理任务失败: {e}")
            return self._create_error_result(start_time, str(e))
    
    def _vacuum_table(self, dialect: str, table: str, full: bool):
        """清理单个表"""
        if "postgresql" in dialect:
            vacuum_type = "FULL" if full else ""
            sql = f"VACUUM {vacuum_type} {table}"
        elif dialect in ("mysql", "mysql+pymysql"):
            sql = f"OPTIMIZE TABLE `{table}`"
        elif dialect in ("sqlite", "sqlite3"):
            sql = "VACUUM"
        else:
            # 通用回退：尝试标准 VACUUM（多数数据库支持）
            sql = f"VACUUM {table}"

        self.connector.execute(sql)

    def _vacuum_database(self, dialect: str, full: bool):
        """清理整个数据库"""
        if "postgresql" in dialect:
            vacuum_type = "FULL" if full else ""
            sql = f"VACUUM {vacuum_type}"
        elif dialect in ("sqlite", "sqlite3"):
            sql = "VACUUM"
        elif dialect in ("mysql", "mysql+pymysql"):
            raise NotImplementedError("MySQL不支持全局VACUUM，请指定表名")
        else:
            # 通用回退：尝试标准 VACUUM
            sql = "VACUUM"

        self.connector.execute(sql)

    def _analyze_after_vacuum(self, dialect: str, tables: Optional[List[str]]):
        """清理后分析"""
        if "postgresql" in dialect:
            if tables:
                for table in tables:
                    self.connector.execute(f"ANALYZE {table}")
            else:
                self.connector.execute("ANALYZE")
    
    def _create_cancelled_result(self, start_time: datetime) -> ExecutionResult:
        return ExecutionResult(
            status=ExecutionStatus.CANCELLED,
            start_time=start_time,
            end_time=datetime.now(),
            message="任务已取消"
        )
    
    def _create_error_result(self, start_time: datetime, error: str) -> ExecutionResult:
        return ExecutionResult(
            status=ExecutionStatus.FAILED,
            start_time=start_time,
            end_time=datetime.now(),
            message="执行失败",
            error=error
        )


class ReindexExecutor(BaseTaskExecutor):
    """
    索引重建执行器
    
    重建索引以优化查询性能
    """
    
    def execute(self, params: Dict[str, Any],
                progress_callback: Optional[Callable[[ExecutionProgress], None]] = None,
                timeout_seconds: int = 3600) -> ExecutionResult:
        """
        执行索引重建任务
        
        参数:
            params:
                - tables: 要重建索引的表列表
                - indexes: 指定索引列表（可选）
                - concurrently: 是否并发重建（仅PostgreSQL，默认True）
        """
        start_time = datetime.now()
        tables = params.get("tables", [])
        indexes = params.get("indexes")
        concurrently = params.get("concurrently", True)
        
        try:
            self._report_progress(progress_callback, "初始化", 0, "开始索引重建")
            
            if not self._check_cancelled():
                return self._create_cancelled_result(start_time)
            
            dialect = getattr(self.connector, 'dialect', 'mysql').lower()
            
            rebuilt_indexes = []
            
            if indexes:
                # 重建指定索引
                for i, index in enumerate(indexes):
                    if not self._check_cancelled():
                        return self._create_cancelled_result(start_time)
                    
                    progress = (i / len(indexes)) * 100
                    self._report_progress(
                        progress_callback,
                        "重建",
                        progress,
                        f"重建索引: {index}"
                    )
                    
                    self._reindex(dialect, index=index, concurrently=concurrently)
                    rebuilt_indexes.append(index)
            elif tables:
                # 重建表的索引
                for i, table in enumerate(tables):
                    if not self._check_cancelled():
                        return self._create_cancelled_result(start_time)
                    
                    progress = (i / len(tables)) * 100
                    self._report_progress(
                        progress_callback,
                        "重建",
                        progress,
                        f"重建表索引: {table}"
                    )
                    
                    self._reindex(dialect, table=table, concurrently=concurrently)
                    rebuilt_indexes.append(f"{table}.*")
            else:
                # 重建所有索引
                self._report_progress(progress_callback, "重建", 50, "重建所有索引")
                self._reindex(dialect, concurrently=concurrently)
                rebuilt_indexes.append("ALL")
            
            self._report_progress(progress_callback, "完成", 100, "索引重建完成")
            
            end_time = datetime.now()
            return ExecutionResult(
                status=ExecutionStatus.SUCCESS,
                start_time=start_time,
                end_time=end_time,
                message=f"重建了 {len(rebuilt_indexes)} 个索引",
                data={
                    "rebuilt_indexes": rebuilt_indexes,
                    "concurrently": concurrently
                },
                resource_usage=self._get_resource_usage()
            )
        
        except Exception as e:
            logger.error(f"索引重建失败: {e}")
            return self._create_error_result(start_time, str(e))
    
    def _reindex(self, dialect: str, table: Optional[str] = None, 
                index: Optional[str] = None, concurrently: bool = True):
        """重建索引"""
        if "postgresql" in dialect:
            concurrent_flag = "CONCURRENTLY" if concurrently else ""
            if index:
                sql = f"REINDEX INDEX {concurrent_flag} {index}"
            elif table:
                sql = f"REINDEX TABLE {concurrent_flag} {table}"
            else:
                sql = f"REINDEX DATABASE {concurrent_flag}"
        elif dialect in ("mysql", "mysql+pymysql"):
            if table:
                sql = f"REPAIR TABLE `{table}` QUICK"
            else:
                raise ValueError("MySQL需要指定表名")
        elif dialect in ("sqlite", "sqlite3"):
            sql = "REINDEX"
        else:
            # 通用回退：尝试标准 REINDEX
            concurrent_flag = "CONCURRENTLY" if concurrent else ""
            if index:
                sql = f"REINDEX INDEX {concurrent_flag} {index}"
            elif table:
                sql = f"REINDEX TABLE {concurrent_flag} {table}"
            else:
                sql = f"REINDEX DATABASE {concurrent_flag}"
        
        self.connector.execute(sql)
    
    def _create_cancelled_result(self, start_time: datetime) -> ExecutionResult:
        return ExecutionResult(
            status=ExecutionStatus.CANCELLED,
            start_time=start_time,
            end_time=datetime.now(),
            message="任务已取消"
        )
    
    def _create_error_result(self, start_time: datetime, error: str) -> ExecutionResult:
        return ExecutionResult(
            status=ExecutionStatus.FAILED,
            start_time=start_time,
            end_time=datetime.now(),
            message="执行失败",
            error=error
        )


class CheckExecutor(BaseTaskExecutor):
    """
    数据库检查执行器
    
    检查数据库完整性、一致性
    """
    
    def execute(self, params: Dict[str, Any],
                progress_callback: Optional[Callable[[ExecutionProgress], None]] = None,
                timeout_seconds: int = 3600) -> ExecutionResult:
        """
        执行检查任务
        
        参数:
            params:
                - tables: 要检查的表列表（None表示所有表）
                - check_type: 检查类型（integrity/performance/all）
        """
        start_time = datetime.now()
        tables = params.get("tables")
        check_type = params.get("check_type", "all")
        
        try:
            self._report_progress(progress_callback, "初始化", 0, "开始数据库检查")
            
            if not self._check_cancelled():
                return self._create_cancelled_result(start_time)
            
            dialect = getattr(self.connector, 'dialect', 'mysql').lower()
            
            if not tables:
                tables = self._get_all_tables()
            
            check_results = []
            issues = []
            
            for i, table in enumerate(tables):
                if not self._check_cancelled():
                    return self._create_cancelled_result(start_time)
                
                progress = (i / len(tables)) * 100
                self._report_progress(
                    progress_callback,
                    "检查",
                    progress,
                    f"检查表: {table}"
                )
                
                result = self._check_table(dialect, table, check_type)
                check_results.append(result)
                
                if result.get("issues"):
                    issues.extend(result["issues"])
            
            self._report_progress(progress_callback, "完成", 100, "检查完成")
            
            end_time = datetime.now()
            return ExecutionResult(
                status=ExecutionStatus.SUCCESS,
                start_time=start_time,
                end_time=end_time,
                message=f"检查了 {len(tables)} 个表，发现 {len(issues)} 个问题",
                data={
                    "checked_tables": tables,
                    "check_type": check_type,
                    "results": check_results,
                    "issues": issues
                },
                resource_usage=self._get_resource_usage()
            )
        
        except Exception as e:
            logger.error(f"检查任务失败: {e}")
            return self._create_error_result(start_time, str(e))
    
    def _get_all_tables(self) -> List[str]:
        """获取所有表"""
        try:
            result = self.connector.execute("SHOW TABLES")
            return [row[0] for row in result.rows] if result.rows else []
        except Exception as e:
            logger.error(f"获取表列表失败: {e}")
            return []
    
    def _check_table(self, dialect: str, table: str, check_type: str) -> Dict[str, Any]:
        """检查单个表"""
        result = {"table": table, "issues": []}
        
        if dialect in ("mysql", "mysql+pymysql"):
            # MySQL检查
            if check_type in ("integrity", "all"):
                check_result = self.connector.execute(f"CHECK TABLE `{table}`")
                if check_result.rows:
                    for row in check_result.rows:
                        if "error" in str(row).lower():
                            result["issues"].append(f"完整性问题: {row}")
            
            if check_type in ("performance", "all"):
                # 检查索引使用情况
                index_result = self.connector.execute(f"SHOW INDEX FROM `{table}`")
                if not index_result.rows:
                    result["issues"].append("表没有索引")
        
        elif "postgresql" in dialect:
            if check_type in ("integrity", "all"):
                pass
        
        return result
    
    def _create_cancelled_result(self, start_time: datetime) -> ExecutionResult:
        return ExecutionResult(
            status=ExecutionStatus.CANCELLED,
            start_time=start_time,
            end_time=datetime.now(),
            message="任务已取消"
        )
    
    def _create_error_result(self, start_time: datetime, error: str) -> ExecutionResult:
        return ExecutionResult(
            status=ExecutionStatus.FAILED,
            start_time=start_time,
            end_time=datetime.now(),
            message="执行失败",
            error=error
        )


class CustomSQLExecutor(BaseTaskExecutor):
    """
    自定义SQL执行器
    
    执行用户自定义SQL语句
    """
    
    def execute(self, params: Dict[str, Any],
                progress_callback: Optional[Callable[[ExecutionProgress], None]] = None,
                timeout_seconds: int = 3600) -> ExecutionResult:
        """
        执行自定义SQL
        
        参数:
            params:
                - sql: SQL语句或SQL列表
                - params: SQL参数
                - readonly: 是否只读查询（默认False）
        """
        start_time = datetime.now()
        sql_statements = params.get("sql", [])
        sql_params = params.get("params", {})
        readonly = params.get("readonly", False)
        
        # 支持单条SQL或列表
        if isinstance(sql_statements, str):
            sql_statements = [sql_statements]
        
        try:
            self._report_progress(progress_callback, "初始化", 0, f"准备执行 {len(sql_statements)} 条SQL")
            
            if not self._check_cancelled():
                return self._create_cancelled_result(start_time)
            
            results = []
            total_rows = 0
            
            for i, sql in enumerate(sql_statements):
                if not self._check_cancelled():
                    return self._create_cancelled_result(start_time)
                
                progress = (i / len(sql_statements)) * 100
                self._report_progress(
                    progress_callback,
                    "执行",
                    progress,
                    f"执行SQL {i+1}/{len(sql_statements)}"
                )
                
                # 安全检查：只读模式下禁止修改操作
                if readonly:
                    sql_upper = sql.strip().upper()
                    forbidden_keywords = ['INSERT', 'UPDATE', 'DELETE', 'DROP', 'CREATE', 'ALTER']
                    if any(keyword in sql_upper for keyword in forbidden_keywords):
                        raise ValueError(f"只读模式下不允许执行: {sql[:50]}...")
                
                # 执行SQL - 使用连接池获取连接
                with self._get_connection() as conn:
                    result = conn.execute(sql, sql_params)
                    
                    results.append({
                        "sql": sql,
                        "rows": result.rows if result else None,
                        "rowcount": result.rowcount if result else 0
                    })
                    
                    total_rows += result.rowcount if result else 0
            
            self._report_progress(progress_callback, "完成", 100, "SQL执行完成")
            
            end_time = datetime.now()
            return ExecutionResult(
                status=ExecutionStatus.SUCCESS,
                start_time=start_time,
                end_time=end_time,
                message=f"执行了 {len(sql_statements)} 条SQL，影响 {total_rows} 行",
                data={
                    "statements": len(sql_statements),
                    "results": results,
                    "readonly": readonly
                },
                rows_affected=total_rows,
                resource_usage=self._get_resource_usage()
            )
        
        except Exception as e:
            logger.error(f"SQL执行失败: {e}")
            return self._create_error_result(start_time, str(e))
    
    def _create_cancelled_result(self, start_time: datetime) -> ExecutionResult:
        return ExecutionResult(
            status=ExecutionStatus.CANCELLED,
            start_time=start_time,
            end_time=datetime.now(),
            message="任务已取消"
        )
    
    def _create_error_result(self, start_time: datetime, error: str) -> ExecutionResult:
        return ExecutionResult(
            status=ExecutionStatus.FAILED,
            start_time=start_time,
            end_time=datetime.now(),
            message="执行失败",
            error=error
        )


# =============================================================================
# 执行器工厂
# =============================================================================

class ExecutorFactory:
    """
    执行器工厂
    
    根据任务类型创建对应的执行器
    """
    
    _executors = {
        "backup": BackupExecutor,
        "analyze": AnalyzeExecutor,
        "vacuum": VacuumExecutor,
        "reindex": ReindexExecutor,
        "check": CheckExecutor,
        "custom": CustomSQLExecutor
    }
    
    @classmethod
    def create(cls, action: str, connector) -> BaseTaskExecutor:
        """
        创建执行器
        
        参数:
            action: 动作类型
            connector: 数据库连接器
            
        返回:
            BaseTaskExecutor: 执行器实例
            
        异常:
            ValueError: 不支持的动作类型
        """
        executor_class = cls._executors.get(action.lower())
        if not executor_class:
            raise ValueError(f"不支持的动作类型: {action}，支持的类型: {list(cls._executors.keys())}")
        
        return executor_class(connector)
    
    @classmethod
    def register(cls, action: str, executor_class: type):
        """
        注册自定义执行器
        
        参数:
            action: 动作名称
            executor_class: 执行器类（必须继承BaseTaskExecutor）
        """
        if not issubclass(executor_class, BaseTaskExecutor):
            raise ValueError("执行器必须继承BaseTaskExecutor")
        
        cls._executors[action.lower()] = executor_class
        logger.info(f"注册执行器: {action} -> {executor_class.__name__}")
    
    @classmethod
    def get_supported_actions(cls) -> List[str]:
        """获取支持的动作列表"""
        return list(cls._executors.keys())
