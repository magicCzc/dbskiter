"""
安全执行器V2

文件功能：提供安全的SQL执行环境，包含多层安全防护
主要类：
    - ExecutionContext: 执行上下文
    - SecurityCheckResult: 安全检查结果
    - SecurityExecutorV2: 安全执行器

安全防护层级：
    1. SQL注入检测
    2. 速率限制检查
    3. 风险等级评估
    4. 表级权限控制
    5. 操作拦截
    6. 影响预览（参数化查询）
    7. 确认机制
    8. force参数检查
    9. 审计日志
    10. 事务保护

作者：Security Team
创建时间：2026-05-20
最后修改：2026-05-20
"""
import warnings
warnings.warn(
    'This module is deprecated. Use the non-v2 version instead.',
    DeprecationWarning,
    stacklevel=2,
)



import uuid
import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from dbskiter.sql_master.sql_parser import SQLParser, SQLType, ParsedSQL
from dbskiter.sql_master.audit_logger import (
    AuditLogger, AuditLogEntry, OperationStatus, StorageBackend
)
from dbskiter.sql_master.security_checker import (
    SecurityChecker, SQLInjectionDetector, RateLimiter
)
from dbskiter.config.security_config import (
    SecurityLevel, SecurityPolicy, get_security_policy
)
from dbskiter.shared.unified_connector import UnifiedConnector
from dbskiter.shared.error_handler import ErrorCode, create_error_response

logger = logging.getLogger(__name__)


class OperationType(Enum):
    """操作类型"""
    SELECT = "SELECT"
    INSERT = "INSERT"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    DROP = "DROP"
    TRUNCATE = "TRUNCATE"
    ALTER = "ALTER"
    CREATE = "CREATE"
    OTHER = "OTHER"


@dataclass
class ExecutionContext:
    """
    执行上下文

    记录执行环境信息，用于安全检查和审计
    """
    execution_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=datetime.now)
    user: str = "anonymous"
    client_ip: Optional[str] = None
    database: str = ""
    session_id: Optional[str] = None


@dataclass
class SecurityCheckResult:
    """
    安全检查结果

    属性说明：
        passed: 是否通过检查
        risk_level: 风险等级
        risk_description: 风险描述
        requires_confirmation: 是否需要确认
        requires_force: 是否需要force参数
        is_blocked: 是否被拦截
        message: 检查消息
        details: 详细信息
    """
    passed: bool
    risk_level: SecurityLevel
    risk_description: str
    requires_confirmation: bool
    requires_force: bool
    is_blocked: bool
    message: str
    details: Dict[str, Any] = field(default_factory=dict)


class SecurityExecutorV2:
    """
    安全执行器V2

    提供10层安全防护的SQL执行环境：

    使用示例：
        executor = SecurityExecutorV2(connector)

        # 简单查询（自动执行）
        result = executor.execute(
            sql="SELECT * FROM users WHERE id = 1",
            database="mydb"
        )

        # 危险操作（需要确认）
        result = executor.execute(
            sql="DELETE FROM users WHERE id = 1",
            database="mydb",
            confirmed=True  # 用户已确认
        )

        # 极高风险操作（需要force）
        result = executor.execute(
            sql="DROP TABLE users",
            database="mydb",
            confirmed=True,
            force=True  # 强制执行
        )
    """

    def __init__(
        self,
        connector: UnifiedConnector,
        policy: Optional[SecurityPolicy] = None,
        audit_logger: Optional[AuditLogger] = None,
        enable_injection_detection: bool = True,
        enable_rate_limiting: bool = True
    ):
        """
        初始化安全执行器

        参数：
            connector: 数据库连接器
            policy: 安全策略（None则使用全局配置）
            audit_logger: 审计日志记录器
            enable_injection_detection: 是否启用注入检测
            enable_rate_limiting: 是否启用速率限制
        """
        self.connector = connector
        self.policy = policy or get_security_policy()
        self.sql_parser = SQLParser()

        # 安全检查器
        self.security_checker = SecurityChecker(
            enable_injection_detection=enable_injection_detection,
            enable_rate_limiting=enable_rate_limiting
        )

        # 审计日志
        if audit_logger:
            self.audit_logger = audit_logger
        elif self.policy.enable_audit:
            self.audit_logger = self._create_default_audit_logger()
        else:
            self.audit_logger = None

        logger.info("安全执行器V2初始化完成")

    def _create_default_audit_logger(self) -> AuditLogger:
        """创建默认审计日志记录器"""
        import os
        audit_path = os.getenv("DBSKITER_AUDIT_PATH", "./logs/audit.db")
        backend_str = os.getenv("DBSKITER_AUDIT_BACKEND", "sqlite")

        try:
            backend = StorageBackend(backend_str)
        except ValueError:
            backend = StorageBackend.SQLITE

        return AuditLogger(backend=backend, storage_path=audit_path)

    def execute(
        self,
        sql: str,
        database: str,
        force: bool = False,
        confirmed: bool = False,
        user: Optional[str] = None,
        client_ip: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        安全执行SQL

        执行流程：
            1. 基础验证
            2. SQL注入检测
            3. 速率限制检查
            4. 风险等级评估
            5. 表级权限检查
            6. 操作拦截检查
            7. 影响预览
            8. 确认机制
            9. force参数检查
            10. 执行并审计

        参数：
            sql: SQL语句
            database: 数据库名称
            force: 是否强制执行（用于极高风险操作）
            confirmed: 用户是否已确认
            user: 用户名
            client_ip: 客户端IP
            **kwargs: 其他参数

        返回：
            Dict: 执行结果
        """
        # 创建执行上下文
        context = ExecutionContext(
            user=user or "anonymous",
            client_ip=client_ip,
            database=database
        )

        # 1. 基础验证
        if not sql or not sql.strip():
            return create_error_response(
                ErrorCode.INVALID_SQL,
                "SQL语句不能为空"
            )

        # 2-5. 统一安全检查
        check_result = self.security_checker.check(
            sql=sql,
            user_id=context.user,
            whitelist_tables=self.policy.whitelist_tables,
            blacklist_tables=self.policy.blacklist_tables
        )

        if not check_result["passed"]:
            # 记录被拦截的操作
            self._log_blocked_operation(context, sql, check_result)

            return create_error_response(
                ErrorCode.PERMISSION_DENIED,
                check_result["reason"],
                details={
                    "risk_level": check_result["risk_level"].value,
                    "execution_id": context.execution_id
                }
            )

        # 解析SQL
        parsed = check_result["parsed_sql"]
        risk_level = check_result["risk_level"]

        # 6. 检查是否被策略拦截
        operation_type = self._get_operation_type(parsed)
        if self.policy.is_blocked(operation_type):
            self._log_blocked_operation(context, sql, check_result)

            return create_error_response(
                ErrorCode.PERMISSION_DENIED,
                f"操作 '{operation_type}' 被安全策略禁止",
                details={
                    "blocked_operation": operation_type,
                    "execution_id": context.execution_id
                }
            )

        # 7. 影响预览
        impact_preview = None
        if self.policy.enable_impact_preview:
            impact_preview = self._preview_impact(context, parsed)

        # 8. 确认机制
        requires_confirmation = self.policy.requires_confirmation(risk_level)
        if requires_confirmation and not confirmed:
            return {
                "success": False,
                "requires_confirmation": True,
                "risk_level": risk_level.value,
                "risk_description": check_result["risk_description"],
                "impact_preview": impact_preview,
                "message": f"{check_result['risk_description']}，请确认是否继续",
                "sql": sql,
                "execution_id": context.execution_id
            }

        # 9. force参数检查（含二次验证）
        requires_force = self.policy.requires_force(risk_level)
        if requires_force and not force:
            return create_error_response(
                ErrorCode.PERMISSION_DENIED,
                f"{check_result['risk_description']}，必须使用 --force 参数强制执行",
                details={
                    "risk_level": risk_level.value,
                    "requires_force": True,
                    "execution_id": context.execution_id
                }
            )

        # 对 CRITICAL 级别的操作增加环境变量守卫
        # 即使传了 --force，还需要 DBSKITER_FORCE_CONFIRMED=true 才能执行
        # 防止脚本被篡改后自动执行高危操作
        if requires_force and risk_level == SecurityLevel.CRITICAL:
            import os
            if os.getenv("DBSKITER_FORCE_CONFIRMED", "").lower() not in ("true", "1", "yes"):
                return create_error_response(
                    ErrorCode.PERMISSION_DENIED,
                    f"极高风险操作需要额外的环境变量确认。"
                    f"请设置 DBSKITER_FORCE_CONFIRMED=true 后重试，"
                    f"以防止脚本误触发。",
                    details={
                        "risk_level": risk_level.value,
                        "requires_force": True,
                        "message": "这是最后一道安全栅栏，防止自动化脚本意外执行 CRITICAL 操作",
                        "execution_id": context.execution_id
                    }
                )

        # 10. 执行并审计
        try:
            execution_result = self._do_execute(sql, database)

            # 记录审计日志
            if self.audit_logger:
                self._record_audit(
                    context=context,
                    sql=sql,
                    parsed=parsed,
                    risk_level=risk_level,
                    result=execution_result,
                    force=force
                )

            # 添加安全信息到结果
            execution_result["security"] = {
                "risk_level": risk_level.value,
                "execution_id": context.execution_id,
                "confirmed": confirmed,
                "force": force
            }

            return execution_result

        except Exception as e:
            logger.error(f"SQL执行失败: {sql}, 错误: {str(e)}")

            # 记录失败审计
            if self.audit_logger:
                self._record_audit(
                    context=context,
                    sql=sql,
                    parsed=parsed,
                    risk_level=risk_level,
                    result=None,
                    force=force,
                    failed=True,
                    error_message=str(e)
                )

            return create_error_response(
                ErrorCode.QUERY_FAILED,
                f"SQL执行失败: {str(e)}",
                details={
                    "sql": sql,
                    "execution_id": context.execution_id
                }
            )

    def _get_operation_type(self, parsed: ParsedSQL) -> str:
        """获取操作类型字符串"""
        if parsed.sql_type == SQLType.DROP:
            sql_upper = parsed.original_sql.upper()
            if "DATABASE" in sql_upper or "SCHEMA" in sql_upper:
                return "DROP_DATABASE"
            return "DROP_TABLE"
        return parsed.sql_type.value

    def _preview_impact(
        self,
        context: ExecutionContext,
        parsed: ParsedSQL
    ) -> Optional[Dict[str, Any]]:
        """
        预览影响范围

        使用参数化查询防止SQL注入
        """
        if not self.policy.enable_impact_preview:
            return None

        try:
            if parsed.sql_type == SQLType.DELETE:
                return self._preview_delete_impact(context, parsed)
            elif parsed.sql_type == SQLType.UPDATE:
                return self._preview_update_impact(context, parsed)
            elif parsed.sql_type == SQLType.INSERT:
                return self._preview_insert_impact(context, parsed)
        except Exception as e:
            logger.warning(f"影响预览失败: {str(e)}")

        return None

    def _preview_delete_impact(
        self,
        context: ExecutionContext,
        parsed: ParsedSQL
    ) -> Dict[str, Any]:
        """预览DELETE影响（使用参数化查询）"""
        table = parsed.get_main_table()
        if not table:
            return {"error": "无法识别表名"}

        # 安全地转义表名
        safe_table = self._escape_identifier(table)

        try:
            # 使用SELECT COUNT(*)预览影响
            # 注意：这里不使用WHERE子句，只统计表的总行数
            # 因为WHERE子句可能包含用户输入，存在注入风险
            count_sql = f"SELECT COUNT(*) FROM {safe_table}"

            result = self._do_execute(count_sql, context.database)
            total_rows = result.get("rows", [[0]])[0][0] if result.get("rows") else 0

            # 估算影响行数（保守估计）
            if parsed.has_where:
                # 有WHERE子句，无法准确预估，返回提示
                return {
                    "operation": "DELETE",
                    "table": table,
                    "total_rows": total_rows,
                    "has_where": True,
                    "warning": f"表共有 {total_rows} 行数据，WHERE条件将影响其中部分数据",
                    "note": "实际影响行数取决于WHERE条件"
                }
            else:
                # 无WHERE子句，将删除所有数据
                return {
                    "operation": "DELETE",
                    "table": table,
                    "affected_rows": total_rows,
                    "has_where": False,
                    "warning": f"将删除全部 {total_rows} 行数据",
                    "risk": "极高风险：无WHERE子句"
                }

        except Exception as e:
            return {"error": f"无法预览影响: {str(e)}"}

    def _preview_update_impact(
        self,
        context: ExecutionContext,
        parsed: ParsedSQL
    ) -> Dict[str, Any]:
        """预览UPDATE影响"""
        table = parsed.get_main_table()
        if not table:
            return {"error": "无法识别表名"}

        safe_table = self._escape_identifier(table)

        try:
            count_sql = f"SELECT COUNT(*) FROM {safe_table}"
            result = self._do_execute(count_sql, context.database)
            total_rows = result.get("rows", [[0]])[0][0] if result.get("rows") else 0

            if parsed.has_where:
                return {
                    "operation": "UPDATE",
                    "table": table,
                    "total_rows": total_rows,
                    "has_where": True,
                    "warning": f"表共有 {total_rows} 行数据，WHERE条件将影响其中部分数据"
                }
            else:
                return {
                    "operation": "UPDATE",
                    "table": table,
                    "affected_rows": total_rows,
                    "has_where": False,
                    "warning": f"将更新全部 {total_rows} 行数据",
                    "risk": "极高风险：无WHERE子句"
                }

        except Exception as e:
            return {"error": f"无法预览影响: {str(e)}"}

    def _preview_insert_impact(
        self,
        context: ExecutionContext,
        parsed: ParsedSQL
    ) -> Dict[str, Any]:
        """预览INSERT影响"""
        table = parsed.get_main_table()
        if not table:
            return {"error": "无法识别表名"}

        # 估算插入行数
        sql_upper = parsed.original_sql.upper()
        values_count = sql_upper.count("VALUES")

        return {
            "operation": "INSERT",
            "table": table,
            "estimated_rows": values_count if values_count > 0 else 1,
            "warning": f"将向表 {table} 插入数据"
        }

    def _escape_identifier(self, identifier: str) -> str:
        """
        安全地转义SQL标识符

        防止标识符注入攻击
        """
        # 移除危险字符
        dangerous_chars = [';', '--', '/*', '*/', "'", '"']
        result = identifier
        for char in dangerous_chars:
            result = result.replace(char, '')

        # 只允许字母数字下划线
        import re
        result = re.sub(r'[^\w]', '', result)

        if not result:
            raise ValueError(f"无效的标识符: {identifier}")

        return result

    def _do_execute(self, sql: str, database: str) -> Dict[str, Any]:
        """实际执行SQL"""
        return self.connector.execute(sql, database=database)

    def _log_blocked_operation(
        self,
        context: ExecutionContext,
        sql: str,
        check_result: Dict[str, Any]
    ):
        """记录被拦截的操作"""
        if not self.audit_logger:
            return

        try:
            self.audit_logger.log(
                execution_id=context.execution_id,
                sql=sql,
                database=context.database,
                sql_type="BLOCKED",
                tables=[],
                risk_level=check_result["risk_level"].value,
                status=OperationStatus.BLOCKED,
                blocked_reason=check_result["reason"],
                user=context.user,
                client_ip=context.client_ip
            )
        except Exception as e:
            logger.error(f"记录审计日志失败: {str(e)}")

    def _record_audit(
        self,
        context: ExecutionContext,
        sql: str,
        parsed: ParsedSQL,
        risk_level: SecurityLevel,
        result: Optional[Dict[str, Any]],
        force: bool,
        failed: bool = False,
        error_message: str = ""
    ):
        """记录审计日志"""
        if not self.audit_logger:
            return

        try:
            status = OperationStatus.FAILED if failed else OperationStatus.EXECUTED

            self.audit_logger.log(
                execution_id=context.execution_id,
                sql=sql,
                database=context.database,
                sql_type=parsed.sql_type.value,
                tables=parsed.tables,
                risk_level=risk_level.value,
                status=status,
                row_count=result.get("row_count", 0) if result else 0,
                execution_time_ms=result.get("execution_time", 0) * 1000 if result else 0,
                user=context.user,
                client_ip=context.client_ip,
                force_used=force,
                error_message=error_message if failed else None
            )
        except Exception as e:
            logger.error(f"记录审计日志失败: {str(e)}")


__all__ = [
    "SecurityExecutorV2",
    "ExecutionContext",
    "SecurityCheckResult",
    "OperationType",
]
