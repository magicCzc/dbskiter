"""
资源管理器 - 统一管理数据库连接池和线程池

文件功能：提供连接池和线程池管理，防止资源耗尽
主要类：ResourceManager - 资源管理器

使用示例:
    from shared.resource_manager import ResourceManager

    # 获取资源管理器实例
    rm = ResourceManager()

    # 执行数据库操作（自动管理连接）
    with rm.get_connection(connector) as conn:
        result = conn.execute("SELECT 1")

    # 提交异步任务（自动管理线程）
    future = rm.submit_task(my_function, arg1, arg2)
    result = future.result()

作者：AI Assistant
创建时间：2026-04-22
"""

import logging
import threading
import queue
from typing import Dict, Optional, Any, Callable, List
from concurrent.futures import ThreadPoolExecutor, Future
from contextlib import contextmanager
from dataclasses import dataclass
import time

from dbskiter.shared.unified_connector import UnifiedConnector

logger = logging.getLogger(__name__)


@dataclass
class PoolConfig:
    """连接池配置"""
    max_connections: int = 10
    max_idle_time: int = 300  # 5分钟
    connection_timeout: int = 30
    health_check_interval: int = 60


@dataclass
class ThreadPoolConfig:
    """线程池配置"""
    max_workers: int = 10
    queue_size: int = 100
    thread_name_prefix: str = "dbskiter_"


class ConnectionPool:
    """数据库连接池"""

    def __init__(self, connector: UnifiedConnector, config: PoolConfig = None):
        self.connector = connector
        self.config = config or PoolConfig()
        self._pool: queue.Queue = queue.Queue(maxsize=self.config.max_connections)
        self._in_use: set = set()
        self._lock = threading.RLock()
        self._last_used: Dict[str, float] = {}
        self._connection_id = 0

        # 预创建连接
        self._initialize_pool()

        # 启动健康检查线程
        self._health_check_thread = threading.Thread(target=self._health_check, daemon=True)
        self._health_check_thread.start()

    def _initialize_pool(self):
        """初始化连接池"""
        initial_size = min(3, self.config.max_connections)
        for _ in range(initial_size):
            try:
                conn = self._create_connection()
                self._pool.put(conn)
            except Exception as e:
                logger.error(f"创建初始连接失败: {e}")

    def _create_connection(self) -> Dict[str, Any]:
        """创建新连接（深拷贝 UnifiedConnector，共享底层连接池但不共享对象）"""
        self._connection_id += 1
        # 创建新连接对象（深拷贝参数而非 connector 实例本身）
        new_connector = self.connector.__class__(
            dialect=self.connector.dialect,
            host=self.connector.host,
            port=self.connector.port,
            username=self.connector.username,
            password=self.connector.password,
            database=self.connector.database,
        )
        return {
            "id": self._connection_id,
            "connector": new_connector,
            "created_at": time.time(),
            "last_used": time.time(),
            "in_use": False
        }

    def get_connection(self, timeout: int = None) -> Dict[str, Any]:
        """获取连接"""
        timeout = timeout or self.config.connection_timeout

        try:
            conn = self._pool.get(timeout=timeout)
            conn["last_used"] = time.time()
            conn["in_use"] = True

            with self._lock:
                self._in_use.add(conn["id"])

            return conn

        except queue.Empty:
            # 如果池已满但还有容量，创建新连接
            with self._lock:
                current_size = self._pool.qsize() + len(self._in_use)
                if current_size < self.config.max_connections:
                    return self._create_connection()

            raise TimeoutError("获取连接超时，连接池已满")

    def release_connection(self, conn: Dict[str, Any]):
        """释放连接回池"""
        conn["in_use"] = False
        conn["last_used"] = time.time()

        with self._lock:
            self._in_use.discard(conn["id"])

        try:
            self._pool.put_nowait(conn)
        except queue.Full:
            # 池已满，关闭连接
            logger.debug(f"连接池已满，关闭连接 {conn['id']}")

    def _health_check(self):
        """健康检查线程"""
        while True:
            time.sleep(self.config.health_check_interval)

            try:
                current_time = time.time()
                idle_connections = []

                # 检查空闲连接
                while not self._pool.empty():
                    try:
                        conn = self._pool.get_nowait()
                        idle_time = current_time - conn["last_used"]

                        if idle_time > self.config.max_idle_time:
                            # 关闭过期连接
                            logger.debug(f"关闭过期连接 {conn['id']}")
                        else:
                            idle_connections.append(conn)
                    except queue.Empty:
                        break

                # 将有效连接放回池
                for conn in idle_connections:
                    try:
                        self._pool.put_nowait(conn)
                    except queue.Full:
                        break

            except Exception as e:
                logger.error(f"健康检查失败: {e}")


class ResourceManager:
    """资源管理器 - 单例模式"""

    _instance: Optional['ResourceManager'] = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._connection_pools: Dict[str, ConnectionPool] = {}
        self._thread_pool: Optional[ThreadPoolExecutor] = None
        self._pool_lock = threading.RLock()
        self._initialized = True

        # 初始化线程池
        self._init_thread_pool()

    def _init_thread_pool(self, config: ThreadPoolConfig = None):
        """初始化线程池"""
        config = config or ThreadPoolConfig()

        if self._thread_pool:
            self._thread_pool.shutdown(wait=True)

        self._thread_pool = ThreadPoolExecutor(
            max_workers=config.max_workers,
            thread_name_prefix=config.thread_name_prefix
        )

        logger.info(f"线程池初始化完成，最大线程数: {config.max_workers}")

    def get_connection_pool(self, connector: UnifiedConnector) -> ConnectionPool:
        """获取或创建连接池"""
        pool_key = f"{connector.dialect}_{id(connector)}"

        with self._pool_lock:
            if pool_key not in self._connection_pools:
                self._connection_pools[pool_key] = ConnectionPool(connector)
                logger.info(f"创建连接池: {pool_key}")

            return self._connection_pools[pool_key]

    @contextmanager
    def get_connection(self, connector: UnifiedConnector, timeout: int = 30):
        """上下文管理器获取连接"""
        pool = self.get_connection_pool(connector)
        conn = None

        try:
            conn = pool.get_connection(timeout=timeout)
            yield conn["connector"]
        finally:
            if conn:
                pool.release_connection(conn)

    def submit_task(self, fn: Callable, *args, **kwargs) -> Future:
        """提交异步任务"""
        if not self._thread_pool:
            raise RuntimeError("线程池未初始化")

        return self._thread_pool.submit(fn, *args, **kwargs)

    def map_tasks(self, fn: Callable, iterables: List[Any]) -> List[Any]:
        """批量提交任务"""
        if not self._thread_pool:
            raise RuntimeError("线程池未初始化")

        return list(self._thread_pool.map(fn, iterables))

    def get_pool_status(self) -> Dict[str, Any]:
        """获取资源池状态"""
        with self._pool_lock:
            connection_status = {
                key: {
                    "size": pool._pool.qsize(),
                    "in_use": len(pool._in_use),
                    "max": pool.config.max_connections
                }
                for key, pool in self._connection_pools.items()
            }

        return {
            "connection_pools": connection_status,
            "thread_pool": {
                "max_workers": self._thread_pool._max_workers if self._thread_pool else 0,
                "active": len(self._thread_pool._threads) if self._thread_pool else 0
            }
        }

    def shutdown(self):
        """关闭所有资源"""
        logger.info("正在关闭资源管理器...")

        # 关闭线程池
        if self._thread_pool:
            self._thread_pool.shutdown(wait=True)
            self._thread_pool = None

        # 关闭连接池
        with self._pool_lock:
            self._connection_pools.clear()

        logger.info("资源管理器已关闭")


# 便捷函数
def get_resource_manager() -> ResourceManager:
    """获取资源管理器实例"""
    return ResourceManager()
