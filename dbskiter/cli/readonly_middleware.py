"""
CLI只读模式中间件

文件功能：在CLI层面强制执行只读模式
主要类：
    - ReadOnlyMiddleware: 只读模式中间件
    - ReadOnlyEnforcer: 只读强制执行器

使用方式：
    1. 环境变量：DBSKITER_READ_ONLY=true
    2. 命令行参数：--read-only
    3. 配置文件：read_only: true

作者：Security Team
创建时间：2026-05-20
最后修改：2026-05-20
"""

from __future__ import annotations

import inspect
import os
import sys
import logging
import threading
from typing import Optional, List, Set
from functools import wraps
from pathlib import Path

from dbskiter.sql_master.sql_parser import SQLParser, SQLType
from dbskiter.sql_master.security_checker import SQLInjectionDetector
from dbskiter.sql_master.audit_logger import AuditLogger, OperationStatus, StorageBackend
from dbskiter.shared.error_handler import DBPermissionError

logger = logging.getLogger(__name__)

# 模块级单例缓存，避免重复加载 .env 和创建 SQLParser 实例
_readonly_enforcer_instance: Optional[ReadOnlyEnforcer] = None
_readonly_lock = threading.Lock()


def _load_dotenv_if_available():
    """
    加载.env文件中的环境变量

    使用 _load_env_values 避免重复解析和 load_dotenv 副作用
    """
    try:
        from dbskiter.cli.config import _load_env_values
        _load_env_values()
    except ImportError:
        pass


class ReadOnlyEnforcer:
    """
    只读强制执行器

    在CLI层面拦截所有写操作
    """

    # 允许的只读操作
    READ_ONLY_TYPES: Set[SQLType] = {
        SQLType.SELECT,
        SQLType.EXPLAIN,
        SQLType.SHOW,
        SQLType.DESCRIBE,
    }

    # 禁止的操作类型
    WRITE_OPERATIONS: Set[str] = {
        "DELETE", "UPDATE", "INSERT", "REPLACE",
        "DROP", "TRUNCATE", "ALTER", "CREATE",
        "GRANT", "REVOKE", "MERGE", "CALL"
    }

    def __init__(self, enabled: bool = True, audit_logger: Optional[AuditLogger] = None):
        """
        初始化只读执行器

        参数:
            enabled: 是否启用只读模式
            audit_logger: 可选的审计日志记录器（None则使用默认配置）
        """
        self.enabled = enabled
        self.sql_parser = SQLParser()
        self.injection_detector = SQLInjectionDetector()

        # 初始化审计日志
        if audit_logger:
            self.audit_logger = audit_logger
        else:
            self.audit_logger = self._create_default_audit_logger()

        if enabled:
            logger.info("只读模式已启用")

    def _create_default_audit_logger(self) -> Optional[AuditLogger]:
        """创建默认审计日志记录器"""
        try:
            audit_path = os.getenv("DBSKITER_AUDIT_PATH", str(Path.home() / ".dbskiter" / "audit" / "audit.db"))
            # 确保父目录存在
            Path(audit_path).parent.mkdir(parents=True, exist_ok=True)
            backend_str = os.getenv("DBSKITER_AUDIT_BACKEND", "sqlite")
            backend = StorageBackend(backend_str)
            return AuditLogger(backend=backend, storage_path=audit_path)
        except Exception as e:
            logger.warning(f"审计日志初始化失败: {e}")
            return None

    def _record_interception(
        self, sql: str, reason: str, sql_type: str = "UNKNOWN", user: Optional[str] = None
    ) -> None:
        """记录拦截操作到审计日志（失败不抛异常，避免阻断安全流程）"""
        if not self.audit_logger:
            return
        try:
            self.audit_logger.log(
                sql=sql,
                database=os.getenv("DBSKITER_CURRENT_DATABASE", "unknown"),
                risk_level="CRITICAL",
                status=OperationStatus.BLOCKED,
                sql_type=sql_type,
                blocked_reason=reason,
                user=user or os.getenv("USER", "anonymous"),
                metadata={"source": "readonly_interceptor", "reason": reason}
            )
            # 安全拦截记录立即落盘，防止缓冲丢失
            self.audit_logger._flush()
        except Exception as e:
            logger.error(f"审计日志记录失败: {e}")

    @classmethod
    def from_config(cls) -> "ReadOnlyEnforcer":
        """
        从配置创建执行器（使用模块级单例缓存，线程安全）

        检查顺序：
            1. 环境变量 DBSKITER_READ_ONLY
            2. 环境变量 DBSKITER_DEFAULT_READ_ONLY
            3. 默认配置（False）
        """
        global _readonly_enforcer_instance
        if _readonly_enforcer_instance is not None:
            return _readonly_enforcer_instance

        with _readonly_lock:
            if _readonly_enforcer_instance is not None:
                return _readonly_enforcer_instance

            # 确保已加载.env文件
            _load_dotenv_if_available()

            # 优先读取 DBSKITER_READ_ONLY
            enabled = os.getenv("DBSKITER_READ_ONLY", "").lower() in ("true", "1", "yes")

            # 兼容：如果未设置，尝试读取 DBSKITER_DEFAULT_READ_ONLY
            if not enabled:
                enabled = os.getenv("DBSKITER_DEFAULT_READ_ONLY", "").lower() in ("true", "1", "yes")

            _readonly_enforcer_instance = cls(enabled=enabled)
            return _readonly_enforcer_instance

    def check(self, sql: str) -> tuple[bool, Optional[str]]:
        """
        检查SQL是否为只读（含注入检测和危险SELECT子句拦截）

        参数:
            sql: SQL语句

        返回:
            (是否允许, 拒绝原因)
        """
        if not self.enabled:
            return True, None

        if not sql or not sql.strip():
            self._record_interception(sql, "SQL语句不能为空", "UNKNOWN")
            return False, "SQL语句不能为空"

        # 注入检测：即使只读模式也禁止注入攻击
        try:
            injection_result = self.injection_detector.detect(sql)
            if injection_result.is_injection:
                reason = f"检测到SQL注入: {injection_result.description}"
                self._record_interception(sql, reason, "UNKNOWN")
                return False, reason
        except Exception as e:
            logger.warning(f"注入检测失败: {e}")

        try:
            parsed = self.sql_parser.parse(sql)
        except Exception as e:
            # 解析失败时，保守起见拒绝执行
            reason = f"SQL解析失败，为了安全起见拒绝执行: {str(e)}"
            self._record_interception(sql, reason, "UNKNOWN")
            return False, reason

        # 检查SQL类型
        if parsed.sql_type in self.READ_ONLY_TYPES:
            # 对SELECT进一步检查危险子句
            if parsed.sql_type == SQLType.SELECT:
                if parsed.has_into_outfile:
                    reason = "只读模式：禁止 SELECT INTO OUTFILE/DUMPFILE（可能泄露数据到文件系统）"
                    self._record_interception(sql, reason, "SELECT")
                    return False, reason
                if parsed.has_for_update:
                    reason = "只读模式：禁止 SELECT FOR UPDATE（会加行锁，影响业务）"
                    self._record_interception(sql, reason, "SELECT")
                    return False, reason
            return True, None

        # 未知或非只读类型，保守拒绝
        reason = f"只读模式：禁止执行 {parsed.sql_type.value} 类型的SQL语句"
        self._record_interception(sql, reason, parsed.sql_type.value)
        return False, reason

    def enforce(self, sql: str) -> None:
        """
        强制执行只读检查

        如果检查失败，抛出异常

        参数:
            sql: SQL语句

        异常:
            DBPermissionError: 当SQL不是只读时
        """
        allowed, reason = self.check(sql)
        if not allowed:
            logger.warning(f"只读模式拦截: {reason}, SQL: {sql[:100]}")
            raise DBPermissionError(reason)

    def get_status(self) -> dict:
        """获取只读模式状态"""
        return {
            "enabled": self.enabled,
            "read_only_types": [t.value for t in self.READ_ONLY_TYPES],
            "write_operations": list(self.WRITE_OPERATIONS)
        }


def readonly_protect(func):
    """
    只读保护装饰器

    用于装饰CLI命令函数，自动检查SQL是否为只读

    使用示例:
        @readonly_protect
        def execute_sql(sql, database):
            # 这里只会接收到只读SQL
            pass
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        # 使用 inspect 精确定位 sql 参数，避免位置参数误取
        sig = inspect.signature(func)
        bound = sig.bind_partial(*args, **kwargs)
        bound.apply_defaults()
        sql = bound.arguments.get('sql')

        if sql:
            enforcer = ReadOnlyEnforcer.from_config()
            enforcer.enforce(sql)

        return func(*args, **kwargs)
    return wrapper


class ReadOnlyMiddleware:
    """
    只读模式中间件（用于CLI框架）

    可以在命令执行前自动拦截写操作
    """

    def __init__(self):
        self.enforcer = ReadOnlyEnforcer.from_config()

    def process_command(self, command: str, sql: Optional[str] = None) -> tuple[bool, Optional[str]]:
        """
        处理命令

        参数:
            command: 命令名称
            sql: SQL语句（如果有）

        返回:
            (是否继续执行, 拒绝原因)
        """
        # 检查全局只读模式
        if not self.enforcer.enabled:
            return True, None

        # 如果是执行SQL的命令，检查SQL
        if sql and command in ("sql", "execute", "query"):
            allowed, reason = self.enforcer.check(sql)
            if not allowed:
                return False, reason

        # 检查命令本身是否被禁止
        write_commands = {"delete", "update", "insert", "drop", "truncate", "alter"}
        if command.lower() in write_commands:
            return False, f"只读模式：禁止执行 '{command}' 命令"

        return True, None


def check_readonly_before_execute(sql: str) -> None:
    """
    执行前检查只读模式的便捷函数

    参数:
        sql: SQL语句

    异常:
        DBPermissionError: 当处于只读模式且SQL不是只读时
    """
    enforcer = ReadOnlyEnforcer.from_config()
    enforcer.enforce(sql)


def is_readonly_mode() -> bool:
    """
    检查是否处于只读模式

    检查顺序：
        1. DBSKITER_READ_ONLY
        2. DBSKITER_DEFAULT_READ_ONLY
        任一为true即返回true
    """
    # 确保已加载.env文件
    _load_dotenv_if_available()

    if os.getenv("DBSKITER_READ_ONLY", "").lower() in ("true", "1", "yes"):
        return True
    if os.getenv("DBSKITER_DEFAULT_READ_ONLY", "").lower() in ("true", "1", "yes"):
        return True
    return False


def get_readonly_warning() -> str:
    """获取只读模式警告信息"""
    if is_readonly_mode():
        return """
警告：当前处于只读模式

允许的操作：
  - SELECT 查询
  - EXPLAIN 分析
  - SHOW 查看
  - DESCRIBE 表结构

禁止的操作：
  - DELETE 删除
  - UPDATE 更新
  - INSERT 插入
  - DROP 删除表/库
  - TRUNCATE 清空表
  - ALTER 修改结构

如需执行写操作，请：
  1. 设置环境变量 DBSKITER_READ_ONLY=false
  2. 或使用 --no-read-only 参数（需要管理员权限）
"""
    return ""


__all__ = [
    "ReadOnlyEnforcer",
    "ReadOnlyMiddleware",
    "readonly_protect",
    "check_readonly_before_execute",
    "is_readonly_mode",
    "get_readonly_warning",
]
