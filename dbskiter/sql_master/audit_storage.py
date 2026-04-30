"""
sql_master/audit_storage.py
SQL审计日志存储模块

文件功能：
    - 审计日志持久化存储
    - 支持SQLite数据库存储
    - 提供查询和统计接口
    - 自动清理过期日志

主要类：
    - SQLAuditStorage: 审计日志存储管理器

版本: 1.0.0
作者: AI Assistant
创建时间: 2026-04-28
"""

import sqlite3
import json
import logging
import threading
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)


class SQLAuditRecord:
    """
    SQL审计记录数据类
    
    属性:
        id: 记录ID
        timestamp: 操作时间
        operation: 操作类型
        sql_fingerprint: SQL指纹
        sql_preview: SQL预览
        risk_level: 风险等级
        risk_description: 风险描述
        force_used: 是否使用force
        read_only_mode: 是否为只读模式
        dialect: 数据库类型
        success: 是否成功
        error: 错误信息
        execution_time_ms: 执行耗时(毫秒)
        row_count: 影响行数
    """
    
    def __init__(
        self,
        timestamp: str,
        operation: str,
        sql_fingerprint: str,
        sql_preview: str,
        risk_level: str = "SAFE",
        risk_description: Optional[str] = None,
        force_used: bool = False,
        read_only_mode: bool = False,
        dialect: str = "unknown",
        success: bool = True,
        error: Optional[str] = None,
        execution_time_ms: Optional[float] = None,
        row_count: Optional[int] = None,
        record_id: Optional[int] = None
    ):
        self.id = record_id
        self.timestamp = timestamp
        self.operation = operation
        self.sql_fingerprint = sql_fingerprint
        self.sql_preview = sql_preview
        self.risk_level = risk_level
        self.risk_description = risk_description
        self.force_used = force_used
        self.read_only_mode = read_only_mode
        self.dialect = dialect
        self.success = success
        self.error = error
        self.execution_time_ms = execution_time_ms
        self.row_count = row_count
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "timestamp": self.timestamp,
            "operation": self.operation,
            "sql_fingerprint": self.sql_fingerprint,
            "sql_preview": self.sql_preview,
            "risk_level": self.risk_level,
            "risk_description": self.risk_description,
            "force_used": self.force_used,
            "read_only_mode": self.read_only_mode,
            "dialect": self.dialect,
            "success": self.success,
            "error": self.error,
            "execution_time_ms": self.execution_time_ms,
            "row_count": self.row_count,
        }
    
    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "SQLAuditRecord":
        """从数据库行创建记录"""
        return cls(
            record_id=row["id"],
            timestamp=row["timestamp"],
            operation=row["operation"],
            sql_fingerprint=row["sql_fingerprint"],
            sql_preview=row["sql_preview"],
            risk_level=row["risk_level"],
            risk_description=row["risk_description"],
            force_used=bool(row["force_used"]),
            read_only_mode=bool(row["read_only_mode"]),
            dialect=row["dialect"],
            success=bool(row["success"]),
            error=row["error"],
            execution_time_ms=row["execution_time_ms"],
            row_count=row["row_count"],
        )


class SQLAuditStorage:
    """
    SQL审计日志存储管理器
    
    功能:
        - 审计日志持久化存储
        - 支持按条件查询
        - 提供统计分析接口
        - 自动清理过期数据
    
    使用示例:
        >>> storage = SQLAuditStorage("./runtime_data/sql_master")
        >>> storage.save_audit_record(record)
        >>> records = storage.query_records(risk_level="HIGH", hours=24)
        >>> stats = storage.get_statistics(days=7)
    """
    
    def __init__(self, storage_path: str = "./runtime_data/sql_master"):
        """
        初始化存储管理器
        
        参数:
            storage_path: 存储目录路径
        """
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self.db_path = self.storage_path / "audit.db"
        self._lock = threading.RLock()
        self._conn: Optional[sqlite3.Connection] = None
        self._init_db()
    
    def _get_connection(self) -> sqlite3.Connection:
        """获取数据库连接"""
        if self._conn is None:
            self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
        return self._conn
    
    def close(self):
        """关闭数据库连接"""
        with self._lock:
            if self._conn:
                self._conn.close()
                self._conn = None
                logger.info("SQLAuditStorage 数据库连接已关闭")
    
    def _init_db(self):
        """初始化数据库表结构"""
        conn = self._get_connection()
        
        # 审计日志表
        conn.execute("""
            CREATE TABLE IF NOT EXISTS audit_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                operation TEXT NOT NULL,
                sql_fingerprint TEXT NOT NULL,
                sql_preview TEXT NOT NULL,
                risk_level TEXT NOT NULL,
                risk_description TEXT,
                force_used INTEGER DEFAULT 0,
                read_only_mode INTEGER DEFAULT 0,
                dialect TEXT,
                success INTEGER DEFAULT 1,
                error TEXT,
                execution_time_ms REAL,
                row_count INTEGER
            )
        """)
        
        # 创建索引
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_audit_timestamp 
            ON audit_records(timestamp)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_audit_risk_level 
            ON audit_records(risk_level)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_audit_fingerprint 
            ON audit_records(sql_fingerprint)
        """)
        
        conn.commit()
        logger.info("SQLAuditStorage 数据库初始化完成")
    
    def save_record(self, record: SQLAuditRecord) -> int:
        """
        保存审计记录
        
        参数:
            record: 审计记录
            
        返回:
            int: 记录ID
        """
        with self._lock:
            conn = self._get_connection()
            cursor = conn.execute(
                """
                INSERT INTO audit_records (
                    timestamp, operation, sql_fingerprint, sql_preview,
                    risk_level, risk_description, force_used, read_only_mode,
                    dialect, success, error, execution_time_ms, row_count
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.timestamp,
                    record.operation,
                    record.sql_fingerprint,
                    record.sql_preview,
                    record.risk_level,
                    record.risk_description,
                    int(record.force_used),
                    int(record.read_only_mode),
                    record.dialect,
                    int(record.success),
                    record.error,
                    record.execution_time_ms,
                    record.row_count,
                )
            )
            conn.commit()
            record.id = cursor.lastrowid
            logger.debug(f"审计记录已保存: ID={record.id}")
            return record.id
    
    def query_records(
        self,
        risk_level: Optional[str] = None,
        operation: Optional[str] = None,
        success: Optional[bool] = None,
        hours: Optional[int] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[SQLAuditRecord]:
        """
        查询审计记录
        
        参数:
            risk_level: 风险等级筛选
            operation: 操作类型筛选
            success: 是否成功筛选
            hours: 最近多少小时
            limit: 返回数量限制
            offset: 偏移量
            
        返回:
            List[SQLAuditRecord]: 审计记录列表
        """
        with self._lock:
            conn = self._get_connection()
            
            # 构建查询条件
            conditions = []
            params = []
            
            if risk_level:
                conditions.append("risk_level = ?")
                params.append(risk_level)
            
            if operation:
                conditions.append("operation = ?")
                params.append(operation)
            
            if success is not None:
                conditions.append("success = ?")
                params.append(int(success))
            
            if hours:
                since = (datetime.now() - timedelta(hours=hours)).isoformat()
                conditions.append("timestamp >= ?")
                params.append(since)
            
            # 构建SQL
            sql = "SELECT * FROM audit_records"
            if conditions:
                sql += " WHERE " + " AND ".join(conditions)
            sql += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])
            
            cursor = conn.execute(sql, params)
            rows = cursor.fetchall()
            
            return [SQLAuditRecord.from_row(row) for row in rows]
    
    def get_statistics(self, days: int = 7) -> Dict[str, Any]:
        """
        获取审计统计信息
        
        参数:
            days: 统计最近多少天
            
        返回:
            Dict: 统计信息
        """
        with self._lock:
            conn = self._get_connection()
            
            since = (datetime.now() - timedelta(days=days)).isoformat()
            
            # 总记录数
            cursor = conn.execute(
                "SELECT COUNT(*) FROM audit_records WHERE timestamp >= ?",
                (since,)
            )
            total_count = cursor.fetchone()[0]
            
            # 按风险等级统计
            cursor = conn.execute(
                """
                SELECT risk_level, COUNT(*) as count 
                FROM audit_records 
                WHERE timestamp >= ?
                GROUP BY risk_level
                """,
                (since,)
            )
            risk_stats = {row["risk_level"]: row["count"] for row in cursor.fetchall()}
            
            # 按操作类型统计
            cursor = conn.execute(
                """
                SELECT operation, COUNT(*) as count 
                FROM audit_records 
                WHERE timestamp >= ?
                GROUP BY operation
                """,
                (since,)
            )
            operation_stats = {row["operation"]: row["count"] for row in cursor.fetchall()}
            
            # 成功率统计
            cursor = conn.execute(
                """
                SELECT 
                    SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as success_count,
                    COUNT(*) as total
                FROM audit_records 
                WHERE timestamp >= ?
                """,
                (since,)
            )
            row = cursor.fetchone()
            success_rate = row["success_count"] / row["total"] * 100 if row["total"] > 0 else 0
            
            # force使用统计
            cursor = conn.execute(
                """
                SELECT COUNT(*) as count 
                FROM audit_records 
                WHERE timestamp >= ? AND force_used = 1
                """,
                (since,)
            )
            force_count = cursor.fetchone()[0]
            
            return {
                "period_days": days,
                "total_records": total_count,
                "risk_level_distribution": risk_stats,
                "operation_distribution": operation_stats,
                "success_rate": round(success_rate, 2),
                "force_used_count": force_count,
            }
    
    def cleanup_old_records(self, days: int = 30) -> int:
        """
        清理过期审计记录
        
        参数:
            days: 保留最近多少天的记录
            
        返回:
            int: 删除的记录数
        """
        with self._lock:
            conn = self._get_connection()
            
            cutoff = (datetime.now() - timedelta(days=days)).isoformat()
            
            cursor = conn.execute(
                "DELETE FROM audit_records WHERE timestamp < ?",
                (cutoff,)
            )
            conn.commit()
            
            deleted_count = cursor.rowcount
            logger.info(f"清理审计记录: 删除了 {deleted_count} 条过期记录")
            return deleted_count
    
    def get_record_by_id(self, record_id: int) -> Optional[SQLAuditRecord]:
        """
        根据ID获取审计记录
        
        参数:
            record_id: 记录ID
            
        返回:
            Optional[SQLAuditRecord]: 审计记录或None
        """
        with self._lock:
            conn = self._get_connection()
            
            cursor = conn.execute(
                "SELECT * FROM audit_records WHERE id = ?",
                (record_id,)
            )
            row = cursor.fetchone()
            
            if row:
                return SQLAuditRecord.from_row(row)
            return None
