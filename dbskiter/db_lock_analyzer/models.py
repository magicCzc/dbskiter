"""
db_lock_analyzer/models.py
db_lock_analyzer 数据模型

文件功能：定义锁分析相关的数据模型、枚举和错误码体系
主要类：
    - ErrorCode: 错误码体系
    - ErrorMessage: 错误消息
    - LockType: 锁类型枚举
    - LockMode: 锁模式枚举
    - LockInfo: 锁信息
    - DeadlockInfo: 死锁信息
    - LockWaitChain: 锁等待链

作者：AI Assistant
创建时间：2026-04-22
最后修改：2026-04-23
版本：3.0.0（模块化重构版）
"""

from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class ErrorCode:
    """
    错误码体系

    格式: LOCKXXXYYY
    - LOCK: LockAnalyzer模块标识
    - XXX: 功能代码
    - YYY: 具体错误
    """

    # 通用错误 (000)
    SUCCESS = "LOCK00000"
    UNKNOWN_ERROR = "LOCK00001"
    INVALID_PARAM = "LOCK00002"
    NOT_FOUND = "LOCK00003"
    ALREADY_EXISTS = "LOCK00004"

    # 数据库连接错误 (100)
    CONNECTION_FAILED = "LOCK10001"
    CONNECTION_TIMEOUT = "LOCK10002"
    PERMISSION_DENIED = "LOCK10003"

    # 锁分析错误 (200)
    LOCK_ANALYSIS_FAILED = "LOCK20001"
    LOCK_QUERY_FAILED = "LOCK20002"
    UNSUPPORTED_DATABASE = "LOCK20003"

    # 死锁检测错误 (300)
    DEADLOCK_DETECTION_FAILED = "LOCK30001"
    NO_DEADLOCK_FOUND = "LOCK30002"

    # 锁等待链错误 (400)
    CHAIN_ANALYSIS_FAILED = "LOCK40001"
    NO_WAIT_CHAIN_FOUND = "LOCK40002"

    # 事务操作错误 (500)
    TRANSACTION_KILL_FAILED = "LOCK50001"
    INVALID_TRANSACTION_ID = "LOCK50002"


class ErrorMessage:
    """错误消息映射"""

    MESSAGES = {
        ErrorCode.SUCCESS: "操作成功",
        ErrorCode.UNKNOWN_ERROR: "未知错误",
        ErrorCode.INVALID_PARAM: "参数无效",
        ErrorCode.NOT_FOUND: "资源不存在",
        ErrorCode.ALREADY_EXISTS: "资源已存在",
        ErrorCode.CONNECTION_FAILED: "数据库连接失败",
        ErrorCode.CONNECTION_TIMEOUT: "数据库连接超时",
        ErrorCode.PERMISSION_DENIED: "权限不足",
        ErrorCode.LOCK_ANALYSIS_FAILED: "锁分析失败",
        ErrorCode.LOCK_QUERY_FAILED: "锁查询失败",
        ErrorCode.UNSUPPORTED_DATABASE: "不支持的数据库类型",
        ErrorCode.DEADLOCK_DETECTION_FAILED: "死锁检测失败",
        ErrorCode.NO_DEADLOCK_FOUND: "未发现死锁",
        ErrorCode.CHAIN_ANALYSIS_FAILED: "锁等待链分析失败",
        ErrorCode.NO_WAIT_CHAIN_FOUND: "未发现锁等待链",
        ErrorCode.TRANSACTION_KILL_FAILED: "终止事务失败",
        ErrorCode.INVALID_TRANSACTION_ID: "无效的事务ID",
    }

    @classmethod
    def get_message(cls, error_code: str) -> str:
        """获取错误消息"""
        return cls.MESSAGES.get(error_code, f"未知错误码: {error_code}")


def create_success_response(
    data: Any = None,
    message: str = "操作成功"
) -> Dict[str, Any]:
    """
    创建成功响应

    参数:
        data: 响应数据
        message: 成功消息

    返回:
        Dict: 标准成功响应格式
    """
    return {
        "success": True,
        "error_code": ErrorCode.SUCCESS,
        "message": message,
        "data": data or {}
    }


def create_error_response(
    message: str,
    error_code: str = ErrorCode.UNKNOWN_ERROR,
    details: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    创建错误响应

    参数:
        message: 错误消息
        error_code: 错误码
        details: 详细错误信息

    返回:
        Dict: 标准错误响应格式
    """
    return {
        "success": False,
        "error_code": error_code,
        "message": message,
        "error_msg": ErrorMessage.get_message(error_code),
        "details": details or {}
    }


class LockType(str, Enum):
    """锁类型"""
    TABLE = "table"              # 表锁
    ROW = "row"                  # 行锁
    PAGE = "page"                # 页锁
    METADATA = "metadata"        # 元数据锁
    GLOBAL = "global"            # 全局锁


class LockMode(str, Enum):
    """锁模式"""
    SHARED = "shared"            # 共享锁 (S)
    EXCLUSIVE = "exclusive"      # 排他锁 (X)
    INTENTION_SHARED = "is"      # 意向共享锁 (IS)
    INTENTION_EXCLUSIVE = "ix"   # 意向排他锁 (IX)
    AUTO_INC = "auto_inc"        # 自增锁
    GAP = "gap"                  # 间隙锁
    NEXT_KEY = "next_key"        # 临键锁


class TransactionState(str, Enum):
    """事务状态"""
    ACTIVE = "active"            # 活跃
    LOCK_WAIT = "lock_wait"      # 等待锁
    RUNNING = "running"          # 运行中
    COMMITTING = "committing"    # 提交中


@dataclass
class LockInfo:
    """锁信息"""
    lock_id: str                 # 锁ID
    transaction_id: str          # 事务ID
    lock_type: LockType          # 锁类型
    lock_mode: LockMode          # 锁模式
    lock_status: str             # 锁状态: GRANTED/WAITING
    thread_id: Optional[int] = None     # 线程ID
    table_schema: Optional[str] = None  # 数据库名
    table_name: Optional[str] = None    # 表名
    index_name: Optional[str] = None    # 索引名
    lock_data: Optional[str] = None     # 锁定的数据（如主键值）
    wait_time: Optional[float] = None   # 等待时间(秒)
    query_sql: Optional[str] = None     # 正在执行的SQL
    query_time: Optional[float] = None  # 查询执行时间
    connection_id: Optional[int] = None # 连接ID
    user: Optional[str] = None          # 用户
    host: Optional[str] = None          # 主机
    started_at: Optional[datetime] = None  # 事务开始时间

    def to_dict(self) -> Dict[str, Any]:
        return {
            "lock_id": self.lock_id,
            "transaction_id": self.transaction_id,
            "thread_id": self.thread_id,
            "lock_type": self.lock_type.value,
            "lock_mode": self.lock_mode.value,
            "table_schema": self.table_schema,
            "table_name": self.table_name,
            "index_name": self.index_name,
            "lock_data": self.lock_data,
            "lock_status": self.lock_status,
            "wait_time": self.wait_time,
            "query_sql": self.query_sql[:100] if self.query_sql else None,
            "query_time": self.query_time,
            "connection_id": self.connection_id,
            "user": self.user,
            "host": self.host,
            "started_at": self.started_at.isoformat() if self.started_at else None
        }


@dataclass
class DeadlockInfo:
    """死锁信息"""
    deadlock_id: str             # 死锁ID
    detected_at: datetime        # 检测时间
    transactions: List[Dict]     # 涉及的事务列表
    victim_transaction: str      # 被牺牲的事务
    resolution: str              # 解决方案

    def to_dict(self) -> Dict[str, Any]:
        return {
            "deadlock_id": self.deadlock_id,
            "detected_at": self.detected_at.isoformat(),
            "transactions": self.transactions,
            "victim_transaction": self.victim_transaction,
            "resolution": self.resolution
        }


@dataclass
class LockWaitNode:
    """锁等待链节点"""
    transaction_id: str          # 事务ID
    connection_id: int           # 连接ID
    wait_time: float             # 等待时间
    query_sql: Optional[str] = None     # SQL
    waiting_for: Optional[str] = None   # 等待的事务ID
    blocking: List[str] = field(default_factory=list)  # 阻塞的事务ID列表


@dataclass
class LockWaitChain:
    """锁等待链"""
    chain_id: str                # 链ID
    root_transaction: str        # 根事务（阻塞源头）
    nodes: List[LockWaitNode]    # 链节点
    total_wait_time: float       # 总等待时间
    depth: int                   # 链深度

    def to_dict(self) -> Dict[str, Any]:
        return {
            "chain_id": self.chain_id,
            "root_transaction": self.root_transaction,
            "total_wait_time": self.total_wait_time,
            "depth": self.depth,
            "nodes": [
                {
                    "transaction_id": n.transaction_id,
                    "connection_id": n.connection_id,
                    "query_sql": n.query_sql[:80] if n.query_sql else None,
                    "wait_time": n.wait_time,
                    "waiting_for": n.waiting_for,
                    "blocking": n.blocking
                }
                for n in self.nodes
            ]
        }


@dataclass
class LockStatistics:
    """锁统计信息"""
    total_locks: int = 0             # 总锁数
    waiting_locks: int = 0           # 等待中的锁
    granted_locks: int = 0           # 已授予的锁
    row_locks: int = 0               # 行锁数
    table_locks: int = 0             # 表锁数
    metadata_locks: int = 0          # 元数据锁数
    max_wait_time: float = 0.0       # 最大等待时间
    avg_wait_time: float = 0.0       # 平均等待时间
    deadlock_count: int = 0          # 死锁次数

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_locks": self.total_locks,
            "waiting_locks": self.waiting_locks,
            "granted_locks": self.granted_locks,
            "row_locks": self.row_locks,
            "table_locks": self.table_locks,
            "metadata_locks": self.metadata_locks,
            "max_wait_time": self.max_wait_time,
            "avg_wait_time": self.avg_wait_time,
            "deadlock_count": self.deadlock_count
        }
