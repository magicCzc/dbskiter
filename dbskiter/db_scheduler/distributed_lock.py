"""
分布式锁实现

文件功能：提供多种分布式锁实现，支持多节点任务调度协调
主要类：
    - DistributedLock: 分布式锁基类
    - RedisDistributedLock: 基于Redis的分布式锁
    - DatabaseDistributedLock: 基于数据库的分布式锁
    - FileDistributedLock: 基于文件系统的分布式锁（单节点多进程）
    - LockManager: 锁管理器

特性：
1. 多后端支持 - Redis/Database/File
2. 自动续期 - 防止长时间任务锁过期
3. 可重入 - 同一线程可多次获取同一锁
4. 阻塞/非阻塞 - 支持多种获取锁策略
5. 看门狗机制 - 自动检测死锁并释放

使用示例：
    from dbskiter.db_scheduler.distributed_lock import RedisDistributedLock
    
    # 创建锁
    lock = RedisDistributedLock(redis_client, lock_key="task_backup")
    
    # 获取锁
    if lock.acquire(blocking=True, timeout=30):
        try:
            # 执行任务
            execute_backup()
        finally:
            lock.release()
    
    # 使用上下文管理器
    with LockManager(redis_client).lock("task_backup", timeout=30):
        execute_backup()

作者：AI Assistant
创建时间：2026-04-21
版本：1.0.0
"""

import logging
import time
import threading
import uuid
import hashlib
from abc import ABC, abstractmethod
from typing import Optional, Any, Dict, Set
from datetime import datetime, timedelta
from contextlib import contextmanager

logger = logging.getLogger(__name__)


# =============================================================================
# 基类
# =============================================================================

class DistributedLock(ABC):
    """
    分布式锁基类
    
    所有分布式锁实现必须继承此类
    
    特性：
    - 自动续期：长时间运行的任务自动续期锁
    - 可重入：同一线程可多次获取同一锁
    - 看门狗：检测死锁并自动释放
    """
    
    def __init__(self, lock_key: str, lock_timeout: int = 60):
        """
        初始化锁
        
        参数:
            lock_key: 锁的唯一标识
            lock_timeout: 锁超时时间（秒）
        """
        self.lock_key = lock_key
        self.lock_timeout = lock_timeout
        self._lock_value = self._generate_lock_value()
        self._acquired = False
        self._acquire_time: Optional[datetime] = None
        self._renewal_thread: Optional[threading.Thread] = None
        self._stop_renewal = threading.Event()
        self._lock = threading.RLock()
        self._reentrant_count = 0
    
    def _generate_lock_value(self) -> str:
        """生成锁值（唯一标识）"""
        return f"{uuid.uuid4().hex}_{threading.current_thread().ident}_{int(time.time())}"
    
    @abstractmethod
    def _do_acquire(self, blocking: bool = True, timeout: Optional[int] = None) -> bool:
        """
        实际获取锁的实现
        
        参数:
            blocking: 是否阻塞等待
            timeout: 等待超时时间（秒）
            
        返回:
            bool: 是否成功获取锁
        """
        pass
    
    @abstractmethod
    def _do_release(self) -> bool:
        """
        实际释放锁的实现
        
        返回:
            bool: 是否成功释放锁
        """
        pass
    
    @abstractmethod
    def _do_renew(self) -> bool:
        """
        实际续期锁的实现
        
        返回:
            bool: 是否成功续期
        """
        pass
    
    @abstractmethod
    def is_locked(self) -> bool:
        """
        检查锁是否被持有
        
        返回:
            bool: 锁是否被持有
        """
        pass
    
    def acquire(self, blocking: bool = True, timeout: Optional[int] = None) -> bool:
        """
        获取锁
        
        参数:
            blocking: 是否阻塞等待
            timeout: 等待超时时间（秒）
            
        返回:
            bool: 是否成功获取锁
        """
        with self._lock:
            # 可重入检查
            if self._acquired and self._reentrant_count > 0:
                self._reentrant_count += 1
                logger.debug(f"锁可重入: {self.lock_key}, 重入次数: {self._reentrant_count}")
                return True
            
            # 尝试获取锁
            start_time = time.time()
            while True:
                result = self._do_acquire(blocking=False, timeout=None)
                
                if result:
                    self._acquired = True
                    self._acquire_time = datetime.now()
                    self._reentrant_count = 1
                    
                    # 启动续期线程
                    self._start_renewal_thread()
                    
                    logger.info(f"获取锁成功: {self.lock_key}")
                    return True
                
                if not blocking:
                    return False
                
                if timeout and (time.time() - start_time) >= timeout:
                    logger.warning(f"获取锁超时: {self.lock_key}")
                    return False
                
                # 等待后重试
                time.sleep(0.1)
    
    def release(self) -> bool:
        """
        释放锁
        
        返回:
            bool: 是否成功释放锁
        """
        with self._lock:
            if not self._acquired:
                logger.warning(f"尝试释放未持有的锁: {self.lock_key}")
                return False
            
            # 可重入计数减一
            self._reentrant_count -= 1
            if self._reentrant_count > 0:
                logger.debug(f"锁可重入释放: {self.lock_key}, 剩余重入次数: {self._reentrant_count}")
                return True
            
            # 停止续期线程
            self._stop_renewal.set()
            if self._renewal_thread and self._renewal_thread.is_alive():
                self._renewal_thread.join(timeout=5)
            
            # 释放锁
            result = self._do_release()
            
            if result:
                self._acquired = False
                self._acquire_time = None
                self._reentrant_count = 0
                logger.info(f"释放锁成功: {self.lock_key}")
            else:
                logger.error(f"释放锁失败: {self.lock_key}")
            
            return result
    
    def _start_renewal_thread(self):
        """启动锁续期线程"""
        self._stop_renewal.clear()
        self._renewal_thread = threading.Thread(target=self._renewal_loop, daemon=True)
        self._renewal_thread.start()
    
    def _renewal_loop(self):
        """锁续期循环"""
        # 在锁超时前1/3时间开始续期
        renewal_interval = self.lock_timeout / 3
        
        while not self._stop_renewal.wait(timeout=renewal_interval):
            if not self._acquired:
                break
            
            try:
                success = self._do_renew()
                if success:
                    logger.debug(f"锁续期成功: {self.lock_key}")
                else:
                    logger.error(f"锁续期失败: {self.lock_key}")
                    break
            except Exception as e:
                logger.error(f"锁续期异常: {self.lock_key}, 错误: {e}")
                break
    
    def __enter__(self):
        """上下文管理器入口"""
        self.acquire()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        self.release()
    
    def get_hold_time(self) -> Optional[float]:
        """
        获取锁持有时间
        
        返回:
            float: 持有时间（秒），如果未持有则返回None
        """
        if self._acquired and self._acquire_time:
            return (datetime.now() - self._acquire_time).total_seconds()
        return None


# =============================================================================
# Redis分布式锁
# =============================================================================

class RedisDistributedLock(DistributedLock):
    """
    基于Redis的分布式锁（Redlock算法简化版）
    
    使用Redis的SET命令实现原子性加锁
    """
    
    def __init__(self, redis_client, lock_key: str, lock_timeout: int = 60):
        """
        初始化Redis锁
        
        参数:
            redis_client: Redis客户端实例
            lock_key: 锁的唯一标识
            lock_timeout: 锁超时时间（秒）
        """
        super().__init__(lock_key, lock_timeout)
        self.redis = redis_client
        self._redis_key = f"distributed_lock:{lock_key}"
    
    def _do_acquire(self, blocking: bool = True, timeout: Optional[int] = None) -> bool:
        """使用SET NX EX实现原子加锁"""
        try:
            result = self.redis.set(
                self._redis_key,
                self._lock_value,
                nx=True,  # 仅当key不存在时才设置
                ex=self.lock_timeout  # 设置过期时间
            )
            return result is True
        except Exception as e:
            logger.error(f"Redis加锁失败: {self.lock_key}, 错误: {e}")
            return False
    
    def _do_release(self) -> bool:
        """使用Lua脚本原子释放锁"""
        try:
            # Lua脚本：仅当值匹配时才删除（防止误删其他客户端的锁）
            lua_script = """
            if redis.call("get", KEYS[1]) == ARGV[1] then
                return redis.call("del", KEYS[1])
            else
                return 0
            end
            """
            result = self.redis.eval(lua_script, 1, self._redis_key, self._lock_value)
            return result == 1
        except Exception as e:
            logger.error(f"Redis释放锁失败: {self.lock_key}, 错误: {e}")
            return False
    
    def _do_renew(self) -> bool:
        """续期锁"""
        try:
            # Lua脚本：仅当值匹配时才续期
            lua_script = """
            if redis.call("get", KEYS[1]) == ARGV[1] then
                return redis.call("expire", KEYS[1], ARGV[2])
            else
                return 0
            end
            """
            result = self.redis.eval(lua_script, 1, self._redis_key, 
                                    self._lock_value, str(self.lock_timeout))
            return result == 1
        except Exception as e:
            logger.error(f"Redis续期锁失败: {self.lock_key}, 错误: {e}")
            return False
    
    def is_locked(self) -> bool:
        """检查锁是否被持有"""
        try:
            value = self.redis.get(self._redis_key)
            return value is not None
        except Exception as e:
            logger.error(f"检查锁状态失败: {self.lock_key}, 错误: {e}")
            return False


# =============================================================================
# 数据库分布式锁
# =============================================================================

class DatabaseDistributedLock(DistributedLock):
    """
    基于数据库的分布式锁
    
    使用数据库表实现锁，适用于没有Redis的环境
    """
    
    def __init__(self, connector, lock_key: str, lock_timeout: int = 60):
        """
        初始化数据库锁
        
        参数:
            connector: 数据库连接器
            lock_key: 锁的唯一标识
            lock_timeout: 锁超时时间（秒）
        """
        super().__init__(lock_key, lock_timeout)
        self.connector = connector
        self._ensure_lock_table()
    
    def _ensure_lock_table(self):
        """确保锁表存在"""
        try:
            # 创建锁表
            create_table_sql = """
            CREATE TABLE IF NOT EXISTS distributed_locks (
                lock_key VARCHAR(255) PRIMARY KEY,
                lock_value VARCHAR(255) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP NOT NULL
            )
            """
            self.connector.execute(create_table_sql)
            
            # 创建索引
            try:
                self.connector.execute("""
                    CREATE INDEX idx_locks_expires ON distributed_locks(expires_at)
                """)
            except:
                pass  # 索引可能已存在
            
            logger.debug("分布式锁表已就绪")
        except Exception as e:
            logger.error(f"创建锁表失败: {e}")
    
    def _do_acquire(self, blocking: bool = True, timeout: Optional[int] = None) -> bool:
        """尝试获取锁"""
        try:
            # 清理过期锁
            self._cleanup_expired_locks()
            
            # 尝试插入锁记录
            expires_at = datetime.now() + timedelta(seconds=self.lock_timeout)
            
            insert_sql = """
            INSERT INTO distributed_locks (lock_key, lock_value, expires_at)
            VALUES (%s, %s, %s)
            """
            
            try:
                self.connector.execute(insert_sql, (self.lock_key, self._lock_value, expires_at))
                return True
            except Exception as e:
                # 插入失败，锁已被其他客户端持有
                return False
        
        except Exception as e:
            logger.error(f"数据库加锁失败: {self.lock_key}, 错误: {e}")
            return False
    
    def _do_release(self) -> bool:
        """释放锁"""
        try:
            delete_sql = """
            DELETE FROM distributed_locks
            WHERE lock_key = %s AND lock_value = %s
            """
            result = self.connector.execute(delete_sql, (self.lock_key, self._lock_value))
            return result.rowcount > 0 if result else False
        except Exception as e:
            logger.error(f"数据库释放锁失败: {self.lock_key}, 错误: {e}")
            return False
    
    def _do_renew(self) -> bool:
        """续期锁"""
        try:
            expires_at = datetime.now() + timedelta(seconds=self.lock_timeout)
            
            update_sql = """
            UPDATE distributed_locks
            SET expires_at = %s
            WHERE lock_key = %s AND lock_value = %s
            """
            result = self.connector.execute(update_sql, (expires_at, self.lock_key, self._lock_value))
            return result.rowcount > 0 if result else False
        except Exception as e:
            logger.error(f"数据库续期锁失败: {self.lock_key}, 错误: {e}")
            return False
    
    def _cleanup_expired_locks(self):
        """清理过期锁"""
        try:
            delete_sql = """
            DELETE FROM distributed_locks
            WHERE expires_at < NOW()
            """
            self.connector.execute(delete_sql)
        except Exception as e:
            logger.warning(f"清理过期锁失败: {e}")
    
    def is_locked(self) -> bool:
        """检查锁是否被持有"""
        try:
            select_sql = """
            SELECT 1 FROM distributed_locks
            WHERE lock_key = %s AND expires_at > NOW()
            """
            result = self.connector.execute(select_sql, (self.lock_key,))
            return result.rows is not None and len(result.rows) > 0
        except Exception as e:
            logger.error(f"检查锁状态失败: {self.lock_key}, 错误: {e}")
            return False


# =============================================================================
# 文件系统分布式锁（单节点多进程）
# =============================================================================

class FileDistributedLock(DistributedLock):
    """
    基于文件系统的锁（跨平台实现）
    
    适用于单节点多进程场景
    Windows使用文件存在性检查，Linux/Mac使用fcntl
    """
    
    def __init__(self, lock_key: str, lock_timeout: int = 60, 
                 lock_dir: str = "/tmp/distributed_locks"):
        """
        初始化文件锁
        
        参数:
            lock_key: 锁的唯一标识
            lock_timeout: 锁超时时间（秒）
            lock_dir: 锁文件存放目录
        """
        super().__init__(lock_key, lock_timeout)
        import os
        import sys
        
        self.lock_dir = lock_dir
        self.lock_file = os.path.join(lock_dir, f"{hashlib.md5(lock_key.encode()).hexdigest()}.lock")
        self._file_handle = None
        self._is_windows = sys.platform.startswith('win')
        
        # 确保目录存在
        os.makedirs(lock_dir, exist_ok=True)
    
    def _do_acquire(self, blocking: bool = True, timeout: Optional[int] = None) -> bool:
        """获取文件锁"""
        try:
            # 检查锁文件是否过期
            self._cleanup_expired_lock()
            
            if self._is_windows:
                # Windows实现：使用文件存在性和内容检查
                return self._acquire_windows(blocking, timeout)
            else:
                # Unix/Linux/Mac实现：使用fcntl
                return self._acquire_unix(blocking, timeout)
        
        except Exception as e:
            logger.error(f"文件加锁失败: {self.lock_key}, 错误: {e}")
            if self._file_handle:
                self._file_handle.close()
                self._file_handle = None
            return False
    
    def _acquire_windows(self, blocking: bool, timeout: Optional[int]) -> bool:
        """Windows下的锁获取"""
        import os
        import msvcrt
        
        start_time = time.time()
        
        while True:
            try:
                # 尝试创建锁文件（独占模式）
                if os.path.exists(self.lock_file):
                    # 检查锁是否过期
                    try:
                        with open(self.lock_file, 'r') as f:
                            content = f.read().strip().split('\n')
                            if len(content) >= 2:
                                lock_time = int(content[1])
                                if time.time() - lock_time < self.lock_timeout:
                                    # 锁未过期，获取失败
                                    if not blocking:
                                        return False
                                    # 等待后重试
                                    time.sleep(0.1)
                                    if timeout and (time.time() - start_time) > timeout:
                                        return False
                                    continue
                    except:
                        pass
                
                # 创建或覆盖锁文件
                self._file_handle = open(self.lock_file, 'w')
                
                # 尝试锁定文件（Windows使用msvcrt）
                try:
                    msvcrt.locking(self._file_handle.fileno(), msvcrt.LK_NBLCK, 1)
                    # 如果成功，重新锁定为独占
                    self._file_handle.seek(0)
                    msvcrt.locking(self._file_handle.fileno(), msvcrt.LK_LOCK, 1)
                except IOError:
                    self._file_handle.close()
                    self._file_handle = None
                    if not blocking:
                        return False
                    time.sleep(0.1)
                    if timeout and (time.time() - start_time) > timeout:
                        return False
                    continue
                
                # 写入锁信息
                lock_info = f"{self._lock_value}\n{int(time.time())}\n{self.lock_timeout}"
                self._file_handle.write(lock_info)
                self._file_handle.flush()
                
                return True
                
            except Exception as e:
                logger.error(f"Windows锁获取失败: {e}")
                if self._file_handle:
                    self._file_handle.close()
                    self._file_handle = None
                return False
    
    def _acquire_unix(self, blocking: bool, timeout: Optional[int]) -> bool:
        """Unix/Linux/Mac下的锁获取"""
        import fcntl
        
        try:
            # 打开或创建锁文件
            self._file_handle = open(self.lock_file, 'w')
            
            # 尝试获取文件锁
            lock_flags = fcntl.LOCK_EX
            if not blocking:
                lock_flags |= fcntl.LOCK_NB
            
            try:
                fcntl.flock(self._file_handle.fileno(), lock_flags)
            except IOError:
                # 获取锁失败
                self._file_handle.close()
                self._file_handle = None
                return False
            
            # 写入锁信息
            lock_info = f"{self._lock_value}\n{int(time.time())}\n{self.lock_timeout}"
            self._file_handle.write(lock_info)
            self._file_handle.flush()
            
            return True
        
        except Exception as e:
            logger.error(f"Unix锁获取失败: {e}")
            if self._file_handle:
                self._file_handle.close()
                self._file_handle = None
            return False
    
    def _do_release(self) -> bool:
        """释放文件锁"""
        try:
            if self._file_handle:
                if self._is_windows:
                    import msvcrt
                    try:
                        self._file_handle.seek(0)
                        msvcrt.locking(self._file_handle.fileno(), msvcrt.LK_UNLCK, 1)
                    except:
                        pass
                else:
                    import fcntl
                    try:
                        fcntl.flock(self._file_handle.fileno(), fcntl.LOCK_UN)
                    except:
                        pass
                
                self._file_handle.close()
                self._file_handle = None
                
                # 尝试删除锁文件
                try:
                    import os
                    os.remove(self.lock_file)
                except:
                    pass
                
                return True
            return False
        except Exception as e:
            logger.error(f"文件释放锁失败: {self.lock_key}, 错误: {e}")
            return False
    
    def _do_renew(self) -> bool:
        """续期文件锁"""
        try:
            if self._file_handle:
                # 更新锁文件中的时间戳
                lock_info = f"{self._lock_value}\n{int(time.time())}\n{self.lock_timeout}"
                self._file_handle.seek(0)
                self._file_handle.write(lock_info)
                self._file_handle.truncate()
                self._file_handle.flush()
                
                return True
            return False
        except Exception as e:
            logger.error(f"文件续期锁失败: {self.lock_key}, 错误: {e}")
            return False
    
    def _cleanup_expired_lock(self):
        """清理过期锁文件"""
        import os
        
        try:
            if os.path.exists(self.lock_file):
                with open(self.lock_file, 'r') as f:
                    lines = f.readlines()
                    if len(lines) >= 2:
                        try:
                            lock_time = int(lines[1].strip())
                            lock_timeout = int(lines[2].strip()) if len(lines) > 2 else 60
                            
                            if time.time() - lock_time > lock_timeout:
                                # 锁已过期，删除文件
                                os.remove(self.lock_file)
                                logger.debug(f"清理过期锁文件: {self.lock_file}")
                        except:
                            pass
        except Exception as e:
            logger.warning(f"清理过期锁文件失败: {e}")
    
    def is_locked(self) -> bool:
        """检查锁是否被持有"""
        import os
        
        if not os.path.exists(self.lock_file):
            return False
        
        # 检查锁是否过期
        try:
            with open(self.lock_file, 'r') as f:
                lines = f.readlines()
                if len(lines) >= 2:
                    try:
                        lock_time = int(lines[1].strip())
                        lock_timeout = int(lines[2].strip()) if len(lines) > 2 else 60
                        
                        if time.time() - lock_time > lock_timeout:
                            # 锁已过期
                            return False
                    except:
                        pass
        except:
            pass
        
        return True


# =============================================================================
# 锁管理器
# =============================================================================

class LockManager:
    """
    锁管理器
    
    统一管理分布式锁的创建和生命周期
    """
    
    def __init__(self, backend: str = "database", **kwargs):
        """
        初始化锁管理器
        
        参数:
            backend: 锁后端类型 (redis/database/file)
            **kwargs: 后端特定参数
                - redis: redis_client
                - database: connector
                - file: lock_dir
        """
        self.backend = backend
        self.kwargs = kwargs
        self._active_locks: Dict[str, DistributedLock] = {}
        self._lock = threading.RLock()
    
    def lock(self, lock_key: str, lock_timeout: int = 60) -> DistributedLock:
        """
        创建锁
        
        参数:
            lock_key: 锁的唯一标识
            lock_timeout: 锁超时时间（秒）
            
        返回:
            DistributedLock: 锁实例
        """
        with self._lock:
            if self.backend == "redis":
                redis_client = self.kwargs.get("redis_client")
                if not redis_client:
                    raise ValueError("Redis后端需要提供redis_client参数")
                return RedisDistributedLock(redis_client, lock_key, lock_timeout)
            
            elif self.backend == "database":
                connector = self.kwargs.get("connector")
                if not connector:
                    raise ValueError("Database后端需要提供connector参数")
                return DatabaseDistributedLock(connector, lock_key, lock_timeout)
            
            elif self.backend == "file":
                lock_dir = self.kwargs.get("lock_dir", "/tmp/distributed_locks")
                return FileDistributedLock(lock_key, lock_timeout, lock_dir)
            
            else:
                raise ValueError(f"不支持的锁后端: {self.backend}")
    
    @contextmanager
    def acquire_lock(self, lock_key: str, lock_timeout: int = 60, 
                     blocking: bool = True, timeout: Optional[int] = None):
        """
        上下文管理器方式获取锁
        
        使用示例：
            with lock_manager.acquire_lock("task_backup"):
                execute_backup()
        
        参数:
            lock_key: 锁的唯一标识
            lock_timeout: 锁超时时间（秒）
            blocking: 是否阻塞等待
            timeout: 等待超时时间（秒）
        """
        lock = self.lock(lock_key, lock_timeout)
        try:
            acquired = lock.acquire(blocking=blocking, timeout=timeout)
            if not acquired:
                raise TimeoutError(f"获取锁超时: {lock_key}")
            
            with self._lock:
                self._active_locks[lock_key] = lock
            
            yield lock
        finally:
            lock.release()
            with self._lock:
                self._active_locks.pop(lock_key, None)
    
    def get_active_locks(self) -> Dict[str, DistributedLock]:
        """获取当前活动的锁"""
        with self._lock:
            return self._active_locks.copy()
    
    def release_all(self):
        """释放所有活动的锁"""
        with self._lock:
            for lock_key, lock in list(self._active_locks.items()):
                try:
                    lock.release()
                    logger.info(f"释放锁: {lock_key}")
                except Exception as e:
                    logger.error(f"释放锁失败: {lock_key}, 错误: {e}")
            
            self._active_locks.clear()


# =============================================================================
# 看门狗（死锁检测）
# =============================================================================

class LockWatchdog:
    """
    锁看门狗
    
    定期检测死锁并自动释放
    """
    
    def __init__(self, lock_manager: LockManager, check_interval: int = 60):
        """
        初始化看门狗
        
        参数:
            lock_manager: 锁管理器
            check_interval: 检查间隔（秒）
        """
        self.lock_manager = lock_manager
        self.check_interval = check_interval
        self._running = False
        self._watchdog_thread: Optional[threading.Thread] = None
    
    def start(self):
        """启动看门狗"""
        if self._running:
            return
        
        self._running = True
        self._watchdog_thread = threading.Thread(target=self._watchdog_loop, daemon=True)
        self._watchdog_thread.start()
        
        logger.info("锁看门狗已启动")
    
    def stop(self):
        """停止看门狗"""
        self._running = False
        
        if self._watchdog_thread:
            self._watchdog_thread.join(timeout=5)
        
        logger.info("锁看门狗已停止")
    
    def _watchdog_loop(self):
        """看门狗主循环"""
        while self._running:
            try:
                self._check_deadlocks()
            except Exception as e:
                logger.error(f"死锁检测异常: {e}")
            
            # 等待下一次检查
            for _ in range(self.check_interval):
                if not self._running:
                    break
                time.sleep(1)
    
    def _check_deadlocks(self):
        """检查死锁"""
        # 获取所有活动锁
        active_locks = self.lock_manager.get_active_locks()
        
        for lock_key, lock in active_locks.items():
            try:
                hold_time = lock.get_hold_time()
                if hold_time and hold_time > lock.lock_timeout * 2:
                    # 锁持有时间超过2倍超时时间，可能是死锁
                    logger.warning(f"检测到可能的死锁: {lock_key}, 持有时间: {hold_time}秒")
                    
                    # 强制释放锁
                    try:
                        lock.release()
                        logger.info(f"已强制释放死锁: {lock_key}")
                    except Exception as e:
                        logger.error(f"强制释放死锁失败: {lock_key}, 错误: {e}")
            
            except Exception as e:
                logger.error(f"检查锁状态失败: {lock_key}, 错误: {e}")
