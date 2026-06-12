"""
审计日志模块

文件功能：提供完整的审计日志记录和查询功能
主要类：
    - AuditLogEntry: 审计日志条目
    - AuditLogger: 审计日志记录器
    - AuditLogQuery: 审计日志查询器

功能：
    1. 记录所有SQL操作
    2. 支持多种存储后端（文件、数据库、内存）
    3. 提供日志查询和统计功能
    4. 支持日志轮转和归档
    5. 支持实时告警

作者：Security Team
创建时间：2026-05-20
最后修改：2026-05-20
"""

import os
import json
import logging
import threading
from datetime import datetime, timedelta

try:
    import sqlite3
except ImportError:
    sqlite3 = None
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, asdict
from pathlib import Path
from enum import Enum

logger = logging.getLogger(__name__)


class StorageBackend(Enum):
    """存储后端类型"""
    FILE = "file"           # 文件存储
    SQLITE = "sqlite"       # SQLite数据库存储
    MEMORY = "memory"       # 内存存储（仅用于测试）


class OperationStatus(Enum):
    """操作状态"""
    PENDING = "pending"     # 等待确认
    ALLOWED = "allowed"     # 允许执行
    BLOCKED = "blocked"     # 被阻止
    EXECUTED = "executed"   # 执行成功
    FAILED = "failed"       # 执行失败


@dataclass
class AuditLogEntry:
    """
    审计日志条目
    
    属性：
        id: 日志ID
        timestamp: 时间戳
        sql: SQL语句
        sql_type: SQL类型
        database: 数据库名
        tables: 涉及的表
        risk_level: 风险等级
        status: 操作状态
        force_used: 是否使用了force参数
        user: 操作用户
        client_ip: 客户端IP
        row_count: 影响行数
        execution_time_ms: 执行时间（毫秒）
        error_message: 错误信息
        blocked_reason: 阻止原因
        requires_confirmation: 是否需要确认
        confirmed: 是否已确认
        metadata: 额外元数据
    """
    id: str
    timestamp: datetime
    sql: str
    sql_type: str
    database: str
    tables: List[str]
    risk_level: str
    status: str
    force_used: bool = False
    user: Optional[str] = None
    client_ip: Optional[str] = None
    row_count: int = 0
    execution_time_ms: float = 0.0
    error_message: Optional[str] = None
    blocked_reason: Optional[str] = None
    requires_confirmation: bool = False
    confirmed: bool = False
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AuditLogEntry':
        """从字典创建"""
        data = data.copy()
        if isinstance(data.get('timestamp'), str):
            data['timestamp'] = datetime.fromisoformat(data['timestamp'])
        return cls(**data)


class AuditLogger:
    """
    审计日志记录器
    
    负责记录所有SQL操作到持久化存储
    
    使用示例：
        # 文件存储
        audit_logger = AuditLogger(
            backend=StorageBackend.FILE,
            storage_path="/var/log/dbskiter/audit.log"
        )
        
        # SQLite存储
        audit_logger = AuditLogger(
            backend=StorageBackend.SQLITE,
            storage_path="/var/lib/dbskiter/audit.db"
        )
        
        # 记录日志
        entry = audit_logger.log(
            sql="DELETE FROM users WHERE id=1",
            database="prod_db",
            risk_level="MEDIUM",
            status=OperationStatus.EXECUTED,
            row_count=1
        )
    """
    
    def __init__(
        self,
        backend: StorageBackend = StorageBackend.FILE,
        storage_path: Optional[str] = None,
        max_file_size: int = 100 * 1024 * 1024,  # 100MB
        max_files: int = 10,
        batch_size: int = 100,
        flush_interval: int = 5
    ):
        """
        初始化审计日志记录器
        
        参数：
            backend: 存储后端类型
            storage_path: 存储路径
            max_file_size: 单个文件最大大小（字节）
            max_files: 最大文件数量
            batch_size: 批量写入大小
            flush_interval: 自动刷新间隔（秒）
        """
        self.backend = backend
        self.storage_path = storage_path or self._get_default_path()
        self.max_file_size = max_file_size
        self.max_files = max_files
        self.batch_size = batch_size
        self.flush_interval = flush_interval
        
        self._lock = threading.RLock()
        self._buffer: List[AuditLogEntry] = []
        self._last_flush = datetime.now()
        self._entry_count = 0
        
        # 告警回调
        self._alert_callbacks: List[Callable[[AuditLogEntry], None]] = []
        
        # 初始化存储
        self._init_storage()
    
    def _get_default_path(self) -> str:
        """获取默认存储路径"""
        home_dir = Path.home()
        base_dir = home_dir / ".dbskiter" / "audit"
        base_dir.mkdir(parents=True, exist_ok=True)
        
        if self.backend == StorageBackend.FILE:
            return str(base_dir / "audit.log")
        elif self.backend == StorageBackend.SQLITE:
            return str(base_dir / "audit.db")
        else:
            return str(base_dir)
    
    def _init_storage(self):
        """初始化存储"""
        if self.backend == StorageBackend.SQLITE:
            self._init_sqlite()
        elif self.backend == StorageBackend.FILE:
            self._init_file()
    
    def _init_sqlite(self):
        """初始化SQLite数据库"""
        conn = sqlite3.connect(self.storage_path)
        try:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS audit_logs (
                    id TEXT PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    sql TEXT NOT NULL,
                    sql_type TEXT,
                    database TEXT,
                    tables TEXT,
                    risk_level TEXT,
                    status TEXT,
                    force_used INTEGER,
                    user TEXT,
                    client_ip TEXT,
                    row_count INTEGER,
                    execution_time_ms REAL,
                    error_message TEXT,
                    blocked_reason TEXT,
                    requires_confirmation INTEGER,
                    confirmed INTEGER,
                    metadata TEXT
                )
            ''')
            
            # 创建索引
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_timestamp 
                ON audit_logs(timestamp)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_risk_level 
                ON audit_logs(risk_level)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_status 
                ON audit_logs(status)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_user 
                ON audit_logs(user)
            ''')
            
            conn.commit()
        finally:
            conn.close()
    
    def _init_file(self):
        """初始化文件存储"""
        log_dir = Path(self.storage_path).parent
        log_dir.mkdir(parents=True, exist_ok=True)
    
    def log(
        self,
        sql: str,
        database: str,
        risk_level: str,
        status: OperationStatus,
        sql_type: str = "UNKNOWN",
        tables: Optional[List[str]] = None,
        force_used: bool = False,
        user: Optional[str] = None,
        client_ip: Optional[str] = None,
        row_count: int = 0,
        execution_time_ms: float = 0.0,
        error_message: Optional[str] = None,
        blocked_reason: Optional[str] = None,
        requires_confirmation: bool = False,
        confirmed: bool = False,
        metadata: Optional[Dict[str, Any]] = None
    ) -> AuditLogEntry:
        """
        记录审计日志
        
        参数：
            sql: SQL语句
            database: 数据库名
            risk_level: 风险等级
            status: 操作状态
            sql_type: SQL类型
            tables: 涉及的表
            force_used: 是否使用了force参数
            user: 操作用户
            client_ip: 客户端IP
            row_count: 影响行数
            execution_time_ms: 执行时间
            error_message: 错误信息
            blocked_reason: 阻止原因
            requires_confirmation: 是否需要确认
            confirmed: 是否已确认
            metadata: 额外元数据
            
        返回：
            AuditLogEntry: 日志条目
        """
        entry = AuditLogEntry(
            id=self._generate_id(),
            timestamp=datetime.now(),
            sql=sql,
            sql_type=sql_type,
            database=database,
            tables=tables or [],
            risk_level=risk_level,
            status=status.value,
            force_used=force_used,
            user=user,
            client_ip=client_ip,
            row_count=row_count,
            execution_time_ms=execution_time_ms,
            error_message=error_message,
            blocked_reason=blocked_reason,
            requires_confirmation=requires_confirmation,
            confirmed=confirmed,
            metadata=metadata or {}
        )
        
        with self._lock:
            self._buffer.append(entry)
            self._entry_count += 1
            
            # 检查是否需要刷新
            should_flush = (
                len(self._buffer) >= self.batch_size or
                (datetime.now() - self._last_flush).seconds >= self.flush_interval
            )
            
            if should_flush:
                self._flush()
        
        # 触发告警回调
        self._trigger_alert(entry)
        
        return entry
    
    def _generate_id(self) -> str:
        """生成唯一ID"""
        import uuid
        return str(uuid.uuid4())
    
    def _flush(self):
        """刷新缓冲区到存储"""
        if not self._buffer:
            return
        
        entries = self._buffer.copy()
        self._buffer = []
        self._last_flush = datetime.now()
        
        try:
            if self.backend == StorageBackend.FILE:
                self._write_to_file(entries)
            elif self.backend == StorageBackend.SQLITE:
                self._write_to_sqlite(entries)
            elif self.backend == StorageBackend.MEMORY:
                pass  # 内存模式不持久化
        except Exception as e:
            logger.error(f"审计日志写入失败: {str(e)}")
            # 写回缓冲区，避免丢失
            with self._lock:
                self._buffer = entries + self._buffer
    
    def _write_to_file(self, entries: List[AuditLogEntry]):
        """写入文件"""
        with open(self.storage_path, 'a', encoding='utf-8') as f:
            for entry in entries:
                f.write(json.dumps(entry.to_dict(), ensure_ascii=False) + '\n')
        
        # 检查文件大小，触发轮转
        self._check_rotation()
    
    def _write_to_sqlite(self, entries: List[AuditLogEntry]):
        """写入SQLite"""
        conn = sqlite3.connect(self.storage_path)
        try:
            cursor = conn.cursor()
            for entry in entries:
                cursor.execute('''
                    INSERT INTO audit_logs VALUES (
                        ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                    )
                ''', (
                    entry.id,
                    entry.timestamp.isoformat(),
                    entry.sql,
                    entry.sql_type,
                    entry.database,
                    json.dumps(entry.tables),
                    entry.risk_level,
                    entry.status,
                    int(entry.force_used),
                    entry.user,
                    entry.client_ip,
                    entry.row_count,
                    entry.execution_time_ms,
                    entry.error_message,
                    entry.blocked_reason,
                    int(entry.requires_confirmation),
                    int(entry.confirmed),
                    json.dumps(entry.metadata)
                ))
            conn.commit()
        finally:
            conn.close()
    
    def _check_rotation(self):
        """检查并执行日志轮转"""
        if not os.path.exists(self.storage_path):
            return
        
        file_size = os.path.getsize(self.storage_path)
        if file_size < self.max_file_size:
            return
        
        # 执行轮转
        base_path = Path(self.storage_path)
        base_name = base_path.stem
        suffix = base_path.suffix
        parent = base_path.parent
        
        # 删除最旧的文件
        oldest_file = parent / f"{base_name}.{self.max_files}{suffix}"
        if oldest_file.exists():
            oldest_file.unlink()
        
        # 重命名现有文件
        for i in range(self.max_files - 1, 0, -1):
            old_file = parent / f"{base_name}.{i}{suffix}"
            new_file = parent / f"{base_name}.{i + 1}{suffix}"
            if old_file.exists():
                old_file.rename(new_file)
        
        # 重命名当前文件
        base_path.rename(parent / f"{base_name}.1{suffix}")
    
    def _trigger_alert(self, entry: AuditLogEntry):
        """触发告警"""
        for callback in self._alert_callbacks:
            try:
                callback(entry)
            except Exception as e:
                logger.error(f"告警回调执行失败: {str(e)}")
    
    def add_alert_callback(self, callback: Callable[[AuditLogEntry], None]):
        """添加告警回调"""
        self._alert_callbacks.append(callback)
    
    def close(self):
        """关闭记录器，刷新缓冲区"""
        with self._lock:
            self._flush()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


class AuditLogQuery:
    """
    审计日志查询器
    
    提供日志查询和统计功能
    
    使用示例：
        query = AuditLogQuery(audit_logger)
        
        # 查询最近24小时的高风险操作
        entries = query.query(
            start_time=datetime.now() - timedelta(hours=24),
            risk_levels=["HIGH", "CRITICAL"]
        )
        
        # 统计信息
        stats = query.get_statistics()
    """
    
    def __init__(self, audit_logger: AuditLogger):
        """
        初始化查询器
        
        参数：
            audit_logger: 审计日志记录器
        """
        self.audit_logger = audit_logger
    
    def query(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        databases: Optional[List[str]] = None,
        tables: Optional[List[str]] = None,
        risk_levels: Optional[List[str]] = None,
        statuses: Optional[List[str]] = None,
        users: Optional[List[str]] = None,
        force_used: Optional[bool] = None,
        limit: int = 1000,
        offset: int = 0
    ) -> List[AuditLogEntry]:
        """
        查询审计日志
        
        参数：
            start_time: 开始时间
            end_time: 结束时间
            databases: 数据库名列表
            tables: 表名列表
            risk_levels: 风险等级列表
            statuses: 状态列表
            users: 用户列表
            force_used: 是否使用了force参数
            limit: 返回数量限制
            offset: 偏移量
            
        返回：
            List[AuditLogEntry]: 日志条目列表
        """
        if self.audit_logger.backend == StorageBackend.SQLITE:
            return self._query_sqlite(
                start_time, end_time, databases, tables,
                risk_levels, statuses, users, force_used, limit, offset
            )
        elif self.audit_logger.backend == StorageBackend.FILE:
            return self._query_file(
                start_time, end_time, databases, tables,
                risk_levels, statuses, users, force_used, limit, offset
            )
        else:
            return []
    
    def _query_sqlite(
        self, start_time, end_time, databases, tables,
        risk_levels, statuses, users, force_used, limit, offset
    ) -> List[AuditLogEntry]:
        """SQLite查询"""
        conn = sqlite3.connect(self.audit_logger.storage_path)
        try:
            cursor = conn.cursor()
            
            conditions = []
            params = []
            
            if start_time:
                conditions.append("timestamp >= ?")
                params.append(start_time.isoformat())
            if end_time:
                conditions.append("timestamp <= ?")
                params.append(end_time.isoformat())
            if databases:
                conditions.append(f"database IN ({','.join(['?']*len(databases))})")
                params.extend(databases)
            if risk_levels:
                conditions.append(f"risk_level IN ({','.join(['?']*len(risk_levels))})")
                params.extend(risk_levels)
            if statuses:
                conditions.append(f"status IN ({','.join(['?']*len(statuses))})")
                params.extend(statuses)
            if users:
                conditions.append(f"user IN ({','.join(['?']*len(users))})")
                params.extend(users)
            if force_used is not None:
                conditions.append("force_used = ?")
                params.append(int(force_used))
            
            where_clause = " AND ".join(conditions) if conditions else "1=1"
            
            cursor.execute(f'''
                SELECT * FROM audit_logs
                WHERE {where_clause}
                ORDER BY timestamp DESC
                LIMIT ? OFFSET ?
            ''', params + [limit, offset])
            
            rows = cursor.fetchall()
            return [self._row_to_entry(row) for row in rows]
        finally:
            conn.close()
    
    def _query_file(
        self, start_time, end_time, databases, tables,
        risk_levels, statuses, users, force_used, limit, offset
    ) -> List[AuditLogEntry]:
        """文件查询"""
        entries = []
        
        # 读取所有日志文件
        log_files = [self.audit_logger.storage_path]
        base_path = Path(self.audit_logger.storage_path)
        for i in range(1, self.audit_logger.max_files + 1):
            rotated = base_path.parent / f"{base_path.stem}.{i}{base_path.suffix}"
            if rotated.exists():
                log_files.append(str(rotated))
        
        for log_file in log_files:
            if not os.path.exists(log_file):
                continue
            
            with open(log_file, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        data = json.loads(line.strip())
                        entry = AuditLogEntry.from_dict(data)
                        
                        # 应用过滤条件
                        if start_time and entry.timestamp < start_time:
                            continue
                        if end_time and entry.timestamp > end_time:
                            continue
                        if databases and entry.database not in databases:
                            continue
                        if risk_levels and entry.risk_level not in risk_levels:
                            continue
                        if statuses and entry.status not in statuses:
                            continue
                        if users and entry.user not in users:
                            continue
                        if force_used is not None and entry.force_used != force_used:
                            continue
                        
                        entries.append(entry)
                    except Exception as e:
                        logger.error(f"解析日志行失败: {str(e)}")
        
        # 排序和分页
        entries.sort(key=lambda x: x.timestamp, reverse=True)
        return entries[offset:offset + limit]
    
    def _row_to_entry(self, row) -> AuditLogEntry:
        """数据库行转换为条目"""
        return AuditLogEntry(
            id=row[0],
            timestamp=datetime.fromisoformat(row[1]),
            sql=row[2],
            sql_type=row[3],
            database=row[4],
            tables=json.loads(row[5]) if row[5] else [],
            risk_level=row[6],
            status=row[7],
            force_used=bool(row[8]),
            user=row[9],
            client_ip=row[10],
            row_count=row[11],
            execution_time_ms=row[12],
            error_message=row[13],
            blocked_reason=row[14],
            requires_confirmation=bool(row[15]),
            confirmed=bool(row[16]),
            metadata=json.loads(row[17]) if row[17] else {}
        )
    
    def get_statistics(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        获取统计信息
        
        参数：
            start_time: 开始时间
            end_time: 结束时间
            
        返回：
            Dict: 统计信息
        """
        entries = self.query(
            start_time=start_time,
            end_time=end_time,
            limit=100000
        )
        
        stats = {
            "total_operations": len(entries),
            "by_risk_level": {},
            "by_status": {},
            "by_sql_type": {},
            "by_database": {},
            "force_used_count": 0,
            "blocked_count": 0,
            "high_risk_count": 0
        }
        
        for entry in entries:
            # 按风险等级统计
            stats["by_risk_level"][entry.risk_level] = \
                stats["by_risk_level"].get(entry.risk_level, 0) + 1
            
            # 按状态统计
            stats["by_status"][entry.status] = \
                stats["by_status"].get(entry.status, 0) + 1
            
            # 按SQL类型统计
            stats["by_sql_type"][entry.sql_type] = \
                stats["by_sql_type"].get(entry.sql_type, 0) + 1
            
            # 按数据库统计
            stats["by_database"][entry.database] = \
                stats["by_database"].get(entry.database, 0) + 1
            
            # Force使用次数
            if entry.force_used:
                stats["force_used_count"] += 1
            
            # 被阻止次数
            if entry.status == OperationStatus.BLOCKED.value:
                stats["blocked_count"] += 1
            
            # 高风险操作次数
            if entry.risk_level in ["HIGH", "CRITICAL"]:
                stats["high_risk_count"] += 1
        
        return stats


# 导出公共接口
__all__ = [
    "StorageBackend",
    "OperationStatus",
    "AuditLogEntry",
    "AuditLogger",
    "AuditLogQuery",
]
