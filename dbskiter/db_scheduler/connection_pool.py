"""
数据库连接池管理模块

文件功能：提供高效、可靠的数据库连接池管理
主要功能：
    - 连接池生命周期管理（创建、借用、归还、销毁）
    - 连接健康检查与自动恢复
    - 连接池监控与统计
    - 多数据库类型支持（MySQL、Oracle、PostgreSQL）
    - 连接泄漏检测与防护

设计特点：
    - 线程安全：使用RLock保护连接池状态
    - 懒加载：按需创建连接
    - 动态扩容：根据负载自动调整池大小
    - 连接保活：定期ping保持连接活跃

使用示例：
    >>> pool = ConnectionPool(
    ...     db_type="mysql",
    ...     host="localhost",
    ...     port=3306,
    ...     database="test",
    ...     user="root",
    ...     password="password",
    ...     min_connections=5,
    ...     max_connections=20
    ... )
    >>> 
    >>> # 获取连接
    >>> with pool.get_connection() as conn:
    ...     cursor = conn.cursor()
    ...     cursor.execute("SELECT 1")
    ... 
    >>> # 关闭连接池
    >>> pool.close()

作者：AI Assistant
创建时间：2026-04-21
"""

import threading
import time
import logging
import queue
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, field
from contextlib import contextmanager
import weakref

# 配置日志
logger = logging.getLogger(__name__)


# =============================================================================
# 数据类和枚举
# =============================================================================

class ConnectionState(Enum):
    """连接状态"""
    IDLE = "idle"           # 空闲
    BUSY = "busy"           # 使用中
    CLOSED = "closed"       # 已关闭
    UNHEALTHY = "unhealthy" # 不健康


class PoolState(Enum):
    """连接池状态"""
    INITIALIZING = "initializing"  # 初始化中
    READY = "ready"                # 就绪
    CLOSING = "closing"            # 关闭中
    CLOSED = "closed"              # 已关闭


@dataclass
class ConnectionStats:
    """
    连接统计信息
    
    属性:
        total_connections: 总连接数
        idle_connections: 空闲连接数
        busy_connections: 使用中连接数
        waiting_requests: 等待连接的请求数
        total_requests: 总请求数
        total_hits: 缓存命中次数
        total_misses: 缓存未命中次数
        avg_wait_time_ms: 平均等待时间（毫秒）
        max_wait_time_ms: 最大等待时间（毫秒）
        created_at: 创建时间
        last_check: 最后检查时间
    """
    total_connections: int = 0
    idle_connections: int = 0
    busy_connections: int = 0
    waiting_requests: int = 0
    total_requests: int = 0
    total_hits: int = 0
    total_misses: int = 0
    avg_wait_time_ms: float = 0.0
    max_wait_time_ms: float = 0.0
    created_at: datetime = field(default_factory=datetime.now)
    last_check: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "total_connections": self.total_connections,
            "idle_connections": self.idle_connections,
            "busy_connections": self.busy_connections,
            "waiting_requests": self.waiting_requests,
            "total_requests": self.total_requests,
            "total_hits": self.total_hits,
            "total_misses": self.total_misses,
            "avg_wait_time_ms": round(self.avg_wait_time_ms, 2),
            "max_wait_time_ms": round(self.max_wait_time_ms, 2),
            "created_at": self.created_at.isoformat(),
            "last_check": self.last_check.isoformat()
        }


@dataclass
class PoolConfig:
    """
    连接池配置
    
    属性:
        db_type: 数据库类型（mysql/oracle/postgresql）
        host: 主机地址
        port: 端口
        database: 数据库名
        user: 用户名
        password: 密码
        min_connections: 最小连接数
        max_connections: 最大连接数
        connection_timeout: 连接超时（秒）
        idle_timeout: 空闲超时（秒）
        max_lifetime: 连接最大生命周期（秒）
        health_check_interval: 健康检查间隔（秒）
        connection_retry: 连接重试次数
        connection_retry_delay: 连接重试延迟（秒）
        enable_leak_detection: 是否启用连接泄漏检测
        leak_detection_threshold: 泄漏检测阈值（秒）
        enable_statistics: 是否启用统计
    """
    db_type: str = "mysql"
    host: str = "localhost"
    port: int = 3306
    database: str = ""
    user: str = ""
    password: str = ""
    min_connections: int = 5
    max_connections: int = 20
    connection_timeout: int = 30
    idle_timeout: int = 300
    max_lifetime: int = 3600
    health_check_interval: int = 60
    connection_retry: int = 3
    connection_retry_delay: float = 1.0
    enable_leak_detection: bool = True
    leak_detection_threshold: int = 300
    enable_statistics: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典（隐藏密码）"""
        return {
            "db_type": self.db_type,
            "host": self.host,
            "port": self.port,
            "database": self.database,
            "user": self.user,
            "min_connections": self.min_connections,
            "max_connections": self.max_connections,
            "connection_timeout": self.connection_timeout,
            "idle_timeout": self.idle_timeout,
            "max_lifetime": self.max_lifetime,
            "health_check_interval": self.health_check_interval,
            "connection_retry": self.connection_retry,
            "enable_leak_detection": self.enable_leak_detection,
            "leak_detection_threshold": self.leak_detection_threshold,
            "enable_statistics": self.enable_statistics
        }


# =============================================================================
# 连接包装类
# =============================================================================

class PooledConnection:
    """
    连接池中的连接包装类
    
    功能：
        - 包装原始数据库连接
        - 跟踪连接状态和使用情况
        - 自动健康检查
        - 泄漏检测
    
    使用示例：
        >>> conn = PooledConnection(raw_conn, pool)
        >>> conn.mark_busy()
        >>> # 使用连接...
        >>> conn.mark_idle()
    """
    
    def __init__(self, raw_connection: Any, pool: 'ConnectionPool'):
        """
        初始化连接包装
        
        参数:
            raw_connection: 原始数据库连接
            pool: 所属的连接池
        """
        self.raw_connection = raw_connection
        self.pool = weakref.ref(pool)
        self.state = ConnectionState.IDLE
        self.created_at = datetime.now()
        self.last_used_at = datetime.now()
        self.borrow_count = 0
        self.borrowed_at: Optional[datetime] = None
        self.borrowed_by: Optional[str] = None  # 借用者标识（线程名）
        self.health_check_failures = 0
        self._lock = threading.RLock()
        
        logger.debug(f"创建连接: {self}")
    
    def mark_busy(self, borrower: str = None):
        """
        标记连接为使用中
        
        参数:
            borrower: 借用者标识
        """
        with self._lock:
            self.state = ConnectionState.BUSY
            self.borrowed_at = datetime.now()
            self.borrowed_by = borrower or threading.current_thread().name
            self.borrow_count += 1
            self.last_used_at = datetime.now()
            logger.debug(f"连接被借用: {self}, 借用者: {self.borrowed_by}")
    
    def mark_idle(self):
        """标记连接为空闲"""
        with self._lock:
            self.state = ConnectionState.IDLE
            self.borrowed_at = None
            self.borrowed_by = None
            self.last_used_at = datetime.now()
            logger.debug(f"连接归还: {self}")
    
    def mark_unhealthy(self):
        """标记连接为不健康"""
        with self._lock:
            self.state = ConnectionState.UNHEALTHY
            self.health_check_failures += 1
            logger.warning(f"连接标记为不健康: {self}")
    
    def close(self):
        """关闭连接"""
        with self._lock:
            try:
                if self.raw_connection:
                    self.raw_connection.close()
                    logger.debug(f"连接关闭: {self}")
            except Exception as e:
                logger.warning(f"关闭连接时出错: {e}")
            finally:
                self.state = ConnectionState.CLOSED
                self.raw_connection = None
    
    def is_healthy(self) -> bool:
        """
        检查连接是否健康
        
        返回:
            bool: 连接是否健康
        """
        try:
            if self.state == ConnectionState.CLOSED:
                return False
            
            if not self.raw_connection:
                return False
            
            # 执行ping检查
            pool = self.pool()
            if pool:
                return pool._ping_connection(self.raw_connection)
            
            return True
        except Exception as e:
            logger.debug(f"健康检查失败: {e}")
            return False
    
    def is_expired(self, max_lifetime: int) -> bool:
        """
        检查连接是否过期
        
        参数:
            max_lifetime: 最大生命周期（秒）
            
        返回:
            bool: 是否过期
        """
        age = (datetime.now() - self.created_at).total_seconds()
        return age > max_lifetime
    
    def is_idle_timeout(self, idle_timeout: int) -> bool:
        """
        检查连接是否空闲超时
        
        参数:
            idle_timeout: 空闲超时（秒）
            
        返回:
            bool: 是否空闲超时
        """
        if self.state != ConnectionState.IDLE:
            return False
        
        idle_time = (datetime.now() - self.last_used_at).total_seconds()
        return idle_time > idle_timeout
    
    def is_leaked(self, threshold: int) -> bool:
        """
        检查连接是否泄漏
        
        参数:
            threshold: 泄漏阈值（秒）
            
        返回:
            bool: 是否泄漏
        """
        if self.state != ConnectionState.BUSY or not self.borrowed_at:
            return False
        
        borrow_time = (datetime.now() - self.borrowed_at).total_seconds()
        return borrow_time > threshold
    
    def __repr__(self):
        return f"PooledConnection(id={id(self)}, state={self.state.value}, borrow_count={self.borrow_count})"
    
    def __enter__(self):
        """上下文管理器入口"""
        return self.raw_connection
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        pool = self.pool()
        if pool:
            pool.release_connection(self)


# =============================================================================
# 连接池管理器
# =============================================================================

class ConnectionPool:
    """
    数据库连接池
    
    功能：
        - 管理数据库连接的创建、借用、归还
        - 连接健康检查和自动恢复
        - 连接泄漏检测
        - 性能统计和监控
    
    线程安全：
        所有公共方法都是线程安全的
    
    使用示例：
        >>> pool = ConnectionPool(
        ...     db_type="mysql",
        ...     host="localhost",
        ...     user="root",
        ...     password="password",
        ...     database="test"
        ... )
        >>> 
        >>> # 使用上下文管理器
        >>> with pool.get_connection() as conn:
        ...     cursor = conn.cursor()
        ...     cursor.execute("SELECT 1")
        ... 
        >>> # 手动管理
        >>> conn = pool.get_connection()
        >>> try:
        ...     # 使用连接...
        ... finally:
        ...     pool.release_connection(conn)
        >>> 
        >>> pool.close()
    """
    
    def __init__(self, config: PoolConfig = None, **kwargs):
        """
        初始化连接池
        
        参数:
            config: 连接池配置对象
            **kwargs: 配置参数（如果config为None）
        """
        self.config = config or PoolConfig(**kwargs)
        self.state = PoolState.INITIALIZING
        
        # 连接存储
        self._connections: Set[PooledConnection] = set()
        self._idle_connections: queue.Queue[PooledConnection] = queue.Queue()
        self._busy_connections: Set[PooledConnection] = set()
        
        # 线程同步
        self._lock = threading.RLock()
        self._condition = threading.Condition(self._lock)
        
        # 统计信息
        self._stats = ConnectionStats()
        self._wait_times: List[float] = []  # 等待时间历史
        
        # 后台线程
        self._health_check_thread: Optional[threading.Thread] = None
        self._leak_detection_thread: Optional[threading.Thread] = None
        self._running = False
        
        # 等待队列
        self._waiting_count = 0
        
        # 初始化
        self._initialize()
        
        logger.info(f"连接池初始化完成: {self.config.host}:{self.config.port}/{self.config.database}")
    
    def _initialize(self):
        """初始化连接池"""
        try:
            # 创建最小连接数
            for _ in range(self.config.min_connections):
                conn = self._create_connection()
                if conn:
                    self._add_connection(conn)
            
            self.state = PoolState.READY
            self._running = True
            
            # 启动后台线程
            self._start_background_threads()
            
        except Exception as e:
            logger.error(f"连接池初始化失败: {e}")
            self.state = PoolState.CLOSED
            raise
    
    def _create_connection(self) -> Optional[PooledConnection]:
        """
        创建新连接
        
        返回:
            PooledConnection: 新连接，失败返回None
        """
        for attempt in range(self.config.connection_retry):
            try:
                raw_conn = self._do_create_connection()
                if raw_conn:
                    return PooledConnection(raw_conn, self)
            except Exception as e:
                logger.warning(f"创建连接失败（尝试 {attempt + 1}/{self.config.connection_retry}）: {e}")
                if attempt < self.config.connection_retry - 1:
                    time.sleep(self.config.connection_retry_delay)
        
        return None
    
    def _do_create_connection(self) -> Any:
        """
        实际创建数据库连接
        
        返回:
            Any: 原始数据库连接
        """
        db_type = self.config.db_type.lower()
        
        if db_type == "mysql":
            return self._create_mysql_connection()
        elif db_type == "oracle":
            return self._create_oracle_connection()
        elif db_type == "postgresql":
            return self._create_postgresql_connection()
        else:
            # 通用数据库支持：尝试使用 SQLAlchemy 创建连接
            return self._create_generic_connection()
    
    def _create_generic_connection(self) -> Any:
        """
        创建通用数据库连接（通过 SQLAlchemy）
        
        适用于任何 SQLAlchemy 支持的数据库驱动。
        
        返回:
            Any: 原始数据库连接
            
        异常:
            ImportError: 未安装 sqlalchemy
            ValueError: 连接参数不足
        """
        try:
            from sqlalchemy import create_engine
            from urllib.parse import quote_plus
            
            # 构建通用连接 URL
            password = quote_plus(self.config.password) if self.config.password else ""
            if self.config.host and self.config.port:
                url = (
                    f"{self.config.db_type}://{self.config.user}:{password}"
                    f"@{self.config.host}:{self.config.port}/{self.config.database}"
                )
            elif self.config.database:
                url = f"{self.config.db_type}:///{self.config.database}"
            else:
                url = f"{self.config.db_type}://"
            
            engine = create_engine(url, connect_args={"connect_timeout": self.config.connection_timeout})
            return engine.raw_connection()
        except ImportError:
            logger.error("未安装 sqlalchemy，无法创建通用数据库连接")
            raise
        except Exception as e:
            logger.error(f"创建通用数据库连接失败: {e}")
            raise
    
    def _create_mysql_connection(self) -> Any:
        """创建MySQL连接"""
        try:
            import pymysql
            return pymysql.connect(
                host=self.config.host,
                port=self.config.port,
                database=self.config.database,
                user=self.config.user,
                password=self.config.password,
                connect_timeout=self.config.connection_timeout,
                charset='utf8mb4'
            )
        except ImportError:
            logger.error("未安装pymysql，请执行: pip install pymysql")
            raise
    
    def _create_oracle_connection(self) -> Any:
        """创建Oracle连接"""
        try:
            import cx_Oracle
            dsn = cx_Oracle.makedsn(
                self.config.host,
                self.config.port,
                service_name=self.config.database
            )
            return cx_Oracle.connect(
                user=self.config.user,
                password=self.config.password,
                dsn=dsn,
                timeout=self.config.connection_timeout
            )
        except ImportError:
            logger.error("未安装cx_Oracle，请执行: pip install cx_Oracle")
            raise
    
    def _create_postgresql_connection(self) -> Any:
        """创建PostgreSQL连接"""
        try:
            import psycopg2
            return psycopg2.connect(
                host=self.config.host,
                port=self.config.port,
                database=self.config.database,
                user=self.config.user,
                password=self.config.password,
                connect_timeout=self.config.connection_timeout
            )
        except ImportError:
            logger.error("未安装psycopg2，请执行: pip install psycopg2")
            raise
    
    def _ping_connection(self, raw_connection: Any) -> bool:
        """
        Ping连接检查健康状态
        
        参数:
            raw_connection: 原始连接
            
        返回:
            bool: 连接是否健康
        """
        try:
            db_type = self.config.db_type.lower()
            
            if db_type == "mysql":
                raw_connection.ping(reconnect=False)
                return True
            elif db_type == "oracle":
                cursor = raw_connection.cursor()
                cursor.execute("SELECT 1 FROM DUAL")
                cursor.close()
                return True
            elif db_type == "postgresql":
                cursor = raw_connection.cursor()
                cursor.execute("SELECT 1")
                cursor.close()
                return True
            else:
                # 通用数据库支持：尝试执行标准 SELECT 1
                try:
                    cursor = raw_connection.cursor()
                    cursor.execute("SELECT 1")
                    cursor.close()
                    return True
                except Exception:
                    # 某些数据库可能不支持 SELECT 1，尝试 ping 方法
                    if hasattr(raw_connection, 'ping'):
                        raw_connection.ping()
                        return True
                    return False
        except Exception as e:
            logger.debug(f"Ping失败: {e}")
            return False
    
    def _add_connection(self, conn: PooledConnection):
        """添加连接到池"""
        with self._lock:
            self._connections.add(conn)
            self._idle_connections.put(conn)
            self._stats.total_connections += 1
            self._stats.idle_connections += 1
    
    def _remove_connection(self, conn: PooledConnection):
        """从池中移除连接"""
        with self._lock:
            conn.close()
            self._connections.discard(conn)
            self._busy_connections.discard(conn)
            self._stats.total_connections -= 1
            
            if conn.state == ConnectionState.IDLE:
                self._stats.idle_connections -= 1
            elif conn.state == ConnectionState.BUSY:
                self._stats.busy_connections -= 1
    
    def _start_background_threads(self):
        """启动后台线程"""
        # 健康检查线程
        if self.config.health_check_interval > 0:
            self._health_check_thread = threading.Thread(
                target=self._health_check_loop,
                name="ConnectionPool-HealthCheck",
                daemon=True
            )
            self._health_check_thread.start()
        
        # 泄漏检测线程
        if self.config.enable_leak_detection:
            self._leak_detection_thread = threading.Thread(
                target=self._leak_detection_loop,
                name="ConnectionPool-LeakDetection",
                daemon=True
            )
            self._leak_detection_thread.start()
    
    def _health_check_loop(self):
        """健康检查循环"""
        while self._running:
            try:
                time.sleep(self.config.health_check_interval)
                self._perform_health_check()
            except Exception as e:
                logger.error(f"健康检查异常: {e}")
    
    def _perform_health_check(self):
        """执行健康检查"""
        with self._lock:
            connections_to_remove = []
            
            for conn in list(self._connections):
                # 检查连接是否过期
                if conn.is_expired(self.config.max_lifetime):
                    logger.debug(f"连接过期: {conn}")
                    connections_to_remove.append(conn)
                    continue
                
                # 检查空闲连接是否超时
                if conn.is_idle_timeout(self.config.idle_timeout):
                    # 保持最小连接数
                    if self._stats.total_connections > self.config.min_connections:
                        logger.debug(f"连接空闲超时: {conn}")
                        connections_to_remove.append(conn)
                        continue
                
                # 检查空闲连接健康
                if conn.state == ConnectionState.IDLE:
                    if not conn.is_healthy():
                        logger.debug(f"连接不健康: {conn}")
                        connections_to_remove.append(conn)
            
            # 移除不健康的连接
            for conn in connections_to_remove:
                self._remove_connection(conn)
            
            # 补充最小连接数
            while (self._stats.total_connections < self.config.min_connections and 
                   self._running):
                new_conn = self._create_connection()
                if new_conn:
                    self._add_connection(new_conn)
                else:
                    break
            
            self._stats.last_check = datetime.now()
    
    def _leak_detection_loop(self):
        """泄漏检测循环"""
        while self._running:
            try:
                time.sleep(60)  # 每分钟检查一次
                self._perform_leak_detection()
            except Exception as e:
                logger.error(f"泄漏检测异常: {e}")
    
    def _perform_leak_detection(self):
        """执行泄漏检测"""
        with self._lock:
            leaked_connections = []
            
            for conn in self._busy_connections:
                if conn.is_leaked(self.config.leak_detection_threshold):
                    logger.warning(
                        f"检测到连接泄漏: {conn}, "
                        f"借用者: {conn.borrowed_by}, "
                        f"借用时间: {conn.borrowed_at}"
                    )
                    leaked_connections.append(conn)
            
            # 强制回收泄漏的连接
            for conn in leaked_connections:
                logger.warning(f"强制回收泄漏连接: {conn}")
                conn.mark_idle()
                self._busy_connections.discard(conn)
                self._idle_connections.put(conn)
                self._stats.busy_connections -= 1
                self._stats.idle_connections += 1
    
    # =====================================================================
    # 公共API
    # =====================================================================
    
    @contextmanager
    def get_connection(self, timeout: Optional[int] = None) -> Any:
        """
        获取连接（上下文管理器）
        
        参数:
            timeout: 等待超时（秒），None表示使用配置值
            
        使用示例：
            >>> with pool.get_connection() as conn:
            ...     cursor = conn.cursor()
            ...     cursor.execute("SELECT 1")
        
        返回:
            Any: 数据库连接
        """
        conn = None
        start_time = time.time()
        
        try:
            conn = self._borrow_connection(timeout)
            yield conn.raw_connection
        finally:
            if conn:
                self.release_connection(conn)
                
                # 记录等待时间
                if self.config.enable_statistics:
                    wait_time = (time.time() - start_time) * 1000
                    self._wait_times.append(wait_time)
                    # 保留最近100条记录
                    if len(self._wait_times) > 100:
                        self._wait_times.pop(0)
    
    def _borrow_connection(self, timeout: Optional[int] = None) -> PooledConnection:
        """
        借用连接
        
        参数:
            timeout: 等待超时（秒）
            
        返回:
            PooledConnection: 连接包装对象
            
        异常:
            TimeoutError: 等待超时
            RuntimeError: 连接池已关闭
        """
        if self.state != PoolState.READY:
            raise RuntimeError(f"连接池未就绪: {self.state.value}")
        
        timeout = timeout or self.config.connection_timeout
        start_time = time.time()
        
        with self._condition:
            self._stats.total_requests += 1
            self._waiting_count += 1
            self._stats.waiting_requests = self._waiting_count
            
            try:
                while True:
                    # 尝试获取空闲连接
                    try:
                        conn = self._idle_connections.get_nowait()
                        
                        # 检查连接健康
                        if conn.is_healthy():
                            conn.mark_busy()
                            self._busy_connections.add(conn)
                            self._stats.idle_connections -= 1
                            self._stats.busy_connections += 1
                            self._stats.total_hits += 1
                            return conn
                        else:
                            # 连接不健康，移除
                            self._remove_connection(conn)
                    except queue.Empty:
                        pass
                    
                    # 检查是否可以创建新连接
                    if self._stats.total_connections < self.config.max_connections:
                        conn = self._create_connection()
                        if conn:
                            self._connections.add(conn)
                            self._busy_connections.add(conn)
                            conn.mark_busy()
                            self._stats.total_connections += 1
                            self._stats.busy_connections += 1
                            self._stats.total_misses += 1
                            return conn
                    
                    # 等待可用连接
                    elapsed = time.time() - start_time
                    if elapsed >= timeout:
                        raise TimeoutError(f"获取连接超时（{timeout}秒）")
                    
                    self._condition.wait(timeout - elapsed)
            
            finally:
                self._waiting_count -= 1
                self._stats.waiting_requests = self._waiting_count
    
    def release_connection(self, conn: PooledConnection):
        """
        归还连接
        
        参数:
            conn: 连接包装对象
        """
        if not conn or conn.state != ConnectionState.BUSY:
            return
        
        with self._condition:
            conn.mark_idle()
            self._busy_connections.discard(conn)
            self._idle_connections.put(conn)
            self._stats.busy_connections -= 1
            self._stats.idle_connections += 1
            
            # 通知等待的线程
            self._condition.notify()
    
    def get_stats(self) -> Dict[str, Any]:
        """
        获取连接池统计
        
        返回:
            Dict: 统计信息
        """
        with self._lock:
            stats = self._stats.to_dict()
            stats["pool_state"] = self.state.value
            stats["config"] = self.config.to_dict()
            
            # 计算平均等待时间
            if self._wait_times:
                stats["avg_wait_time_ms"] = round(sum(self._wait_times) / len(self._wait_times), 2)
                stats["max_wait_time_ms"] = round(max(self._wait_times), 2)
            
            return stats
    
    def close(self, timeout: int = 30):
        """
        关闭连接池
        
        参数:
            timeout: 等待连接归还的超时（秒）
        """
        logger.info("开始关闭连接池...")
        self.state = PoolState.CLOSING
        self._running = False
        
        # 等待所有连接归还
        start_time = time.time()
        while self._busy_connections and (time.time() - start_time) < timeout:
            logger.info(f"等待 {len(self._busy_connections)} 个连接归还...")
            time.sleep(1)
        
        # 关闭所有连接
        with self._lock:
            for conn in list(self._connections):
                self._remove_connection(conn)
            
            self._connections.clear()
            self._busy_connections.clear()
            
            # 清空空闲队列
            while not self._idle_connections.empty():
                try:
                    self._idle_connections.get_nowait()
                except queue.Empty:
                    break
        
        self.state = PoolState.CLOSED
        logger.info("连接池已关闭")
    
    def __enter__(self):
        """上下文管理器入口"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        self.close()


# =============================================================================
# 连接池管理器（多池管理）
# =============================================================================

class ConnectionPoolManager:
    """
    连接池管理器
    
    管理多个数据库的连接池，支持按名称获取连接池
    
    使用示例：
        >>> manager = ConnectionPoolManager()
        >>> manager.create_pool("main_db", db_type="mysql", host="localhost", ...)
        >>> 
        >>> with manager.get_pool("main_db").get_connection() as conn:
        ...     # 使用连接
        ... 
        >>> manager.close_all()
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        """单例模式"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._pools: Dict[str, ConnectionPool] = {}
        self._lock = threading.RLock()
        self._initialized = True
        
        logger.info("连接池管理器初始化完成")
    
    def create_pool(self, name: str, config: PoolConfig = None, **kwargs) -> ConnectionPool:
        """
        创建连接池
        
        参数:
            name: 连接池名称
            config: 连接池配置
            **kwargs: 配置参数
            
        返回:
            ConnectionPool: 连接池实例
        """
        with self._lock:
            if name in self._pools:
                logger.warning(f"连接池已存在: {name}")
                return self._pools[name]
            
            pool = ConnectionPool(config, **kwargs)
            self._pools[name] = pool
            logger.info(f"创建连接池: {name}")
            return pool
    
    def get_pool(self, name: str) -> Optional[ConnectionPool]:
        """
        获取连接池
        
        参数:
            name: 连接池名称
            
        返回:
            ConnectionPool: 连接池实例，不存在返回None
        """
        with self._lock:
            return self._pools.get(name)
    
    def remove_pool(self, name: str):
        """
        移除连接池
        
        参数:
            name: 连接池名称
        """
        with self._lock:
            if name in self._pools:
                pool = self._pools.pop(name)
                pool.close()
                logger.info(f"移除连接池: {name}")
    
    def get_all_stats(self) -> Dict[str, Dict[str, Any]]:
        """
        获取所有连接池统计
        
        返回:
            Dict: 各连接池的统计信息
        """
        with self._lock:
            return {name: pool.get_stats() for name, pool in self._pools.items()}
    
    def close_all(self):
        """关闭所有连接池"""
        with self._lock:
            for name, pool in list(self._pools.items()):
                pool.close()
            self._pools.clear()
            logger.info("所有连接池已关闭")


# =============================================================================
# 便捷函数
# =============================================================================

def create_pool(**kwargs) -> ConnectionPool:
    """
    创建连接池的便捷函数
    
    参数:
        **kwargs: 连接池配置参数
        
    返回:
        ConnectionPool: 连接池实例
        
    使用示例：
        >>> pool = create_pool(
        ...     db_type="mysql",
        ...     host="localhost",
        ...     user="root",
        ...     password="password",
        ...     database="test"
        ... )
    """
    return ConnectionPool(**kwargs)


def get_pool_manager() -> ConnectionPoolManager:
    """
    获取连接池管理器单例
    
    返回:
        ConnectionPoolManager: 连接池管理器实例
    """
    return ConnectionPoolManager()
