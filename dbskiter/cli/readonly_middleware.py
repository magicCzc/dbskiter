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

import os
import sys
import logging
from typing import Optional, List, Set
from functools import wraps
from pathlib import Path

from dbskiter.sql_master.sql_parser import SQLParser, SQLType
from dbskiter.shared.error_handler import DBPermissionError

logger = logging.getLogger(__name__)


def _load_dotenv_if_available():
    """
    加载.env文件中的环境变量

    确保在读取环境变量之前，.env文件已被加载
    """
    try:
        from dotenv import load_dotenv
        env_path = Path.cwd() / ".env"
        if not env_path.exists():
            env_path = Path(__file__).parent.parent.parent / ".env"
        if env_path.exists():
            load_dotenv(env_path, override=False)
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

    def __init__(self, enabled: bool = True):
        """
        初始化只读执行器

        参数:
            enabled: 是否启用只读模式
        """
        self.enabled = enabled
        self.sql_parser = SQLParser()

        if enabled:
            logger.info("只读模式已启用")

    @classmethod
    def from_config(cls) -> "ReadOnlyEnforcer":
        """
        从配置创建执行器

        检查顺序：
            1. 环境变量 DBSKITER_READ_ONLY
            2. 环境变量 DBSKITER_DEFAULT_READ_ONLY
            3. 默认配置（False）
        """
        # 确保已加载.env文件
        _load_dotenv_if_available()

        # 优先读取 DBSKITER_READ_ONLY
        enabled = os.getenv("DBSKITER_READ_ONLY", "").lower() in ("true", "1", "yes")

        # 兼容：如果未设置，尝试读取 DBSKITER_DEFAULT_READ_ONLY
        if not enabled:
            enabled = os.getenv("DBSKITER_DEFAULT_READ_ONLY", "").lower() in ("true", "1", "yes")

        return cls(enabled=enabled)

    def check(self, sql: str) -> tuple[bool, Optional[str]]:
        """
        检查SQL是否为只读

        参数:
            sql: SQL语句

        返回:
            (是否允许, 拒绝原因)
        """
        if not self.enabled:
            return True, None

        if not sql or not sql.strip():
            return False, "SQL语句不能为空"

        try:
            parsed = self.sql_parser.parse(sql)
        except Exception as e:
            # 解析失败时，保守起见拒绝执行
            logger.warning(f"SQL解析失败，拒绝执行: {sql}, 错误: {e}")
            return False, f"SQL解析失败，为了安全起见拒绝执行: {str(e)}"

        # 检查SQL类型
        if parsed.sql_type in self.READ_ONLY_TYPES:
            return True, None

        # 未知或非只读类型，保守拒绝
        return False, f"只读模式：禁止执行 {parsed.sql_type.value} 类型的SQL语句"

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
        # 获取SQL参数（通常是第一个位置参数或sql关键字参数）
        sql = kwargs.get('sql')
        if not sql and args:
            sql = args[0]

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
