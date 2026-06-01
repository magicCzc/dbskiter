"""
MCP工具集成模块

文件功能：提供MCP（Model Context Protocol）工具的安全集成
主要类：
    - MCPSecurityWrapper: MCP安全包装器
    - SecureSQLTool: 安全SQL执行工具

集成说明：
    1. 所有SQL操作都经过安全执行器检查
    2. 支持风险等级评估和拦截
    3. 支持审计日志记录
    4. 支持强制确认机制

使用示例：
    wrapper = MCPSecurityWrapper(connector)
    result = wrapper.execute_sql(
        sql="DELETE FROM users WHERE id=1",
        database="prod_db",
        force=False
    )

作者：Security Team
创建时间：2026-05-20
最后修改：2026-05-20
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime

from dbskiter.shared.unified_connector import UnifiedConnector
from dbskiter.sql_master.security_executor_v2 import SecurityExecutorV2
from dbskiter.sql_master.sql_parser import SQLParser, is_dangerous_without_where
from dbskiter.config.security_config import SecurityLevel, get_security_policy
from dbskiter.cli.readonly_middleware import ReadOnlyEnforcer, is_readonly_mode

logger = logging.getLogger(__name__)


class MCPSecurityWrapper:
    """
    MCP安全包装器
    
    为MCP工具提供统一的安全控制层
    
    属性：
        connector: 数据库连接器
        security_executor: 安全执行器
        sql_parser: SQL解析器
    
    使用示例：
        wrapper = MCPSecurityWrapper(connector)
        
        # 执行SQL（自动安全检查）
        result = wrapper.execute_sql(
            sql="SELECT * FROM users",
            database="mydb"
        )
        
        # 危险操作（需要force参数）
        result = wrapper.execute_sql(
            sql="DELETE FROM users WHERE id=1",
            database="mydb",
            force=True
        )
    """
    
    def __init__(
        self,
        connector: UnifiedConnector,
        enable_audit: bool = True
    ):
        """
        初始化MCP安全包装器
        
        参数：
            connector: 数据库连接器
            enable_audit: 是否启用审计日志
        """
        self.connector = connector
        self.security_executor = SecurityExecutorV2(
            connector=connector
        )
        self.sql_parser = SQLParser()
        self.enable_audit = enable_audit
        
        logger.info("MCPSecurityWrapper 初始化完成")
    
    def execute_sql(
        self,
        sql: str,
        database: str,
        force: bool = False,
        confirmed: bool = False,
        user: Optional[str] = None,
        client_ip: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        安全执行SQL（MCP工具入口）
        
        这是MCP工具执行SQL的统一入口，所有SQL操作都会经过：
        1. SQL解析和验证
        2. 风险等级评估
        3. 安全检查（只读模式、行数限制等）
        4. 影响预览
        5. 确认机制
        6. 审计日志记录
        
        参数：
            sql: SQL语句
            database: 数据库名
            force: 是否强制执行危险操作
            confirmed: 是否已确认（用于二次调用）
            user: 操作用户
            client_ip: 客户端IP
            
        返回：
            Dict: 执行结果
            
        返回格式：
            成功：
            {
                "success": True,
                "data": {
                    "sql": "SELECT * FROM users",
                    "row_count": 10,
                    "columns": ["id", "name"],
                    "rows": [...],
                    "execution_time": 0.123
                }
            }
            
            需要确认：
            {
                "success": False,
                "requires_confirmation": True,
                "risk_level": "HIGH",
                "risk_description": "DELETE操作将永久删除数据",
                "impact_preview": {"affected_rows": 100},
                "message": "请确认是否执行此操作"
            }
            
            被阻止：
            {
                "success": False,
                "error": "操作被禁止",
                "risk_level": "CRITICAL",
                "blocked_reason": "DELETE语句缺少WHERE子句"
            }
        """
        # 1. 基础验证
        if not sql or not sql.strip():
            return {
                "success": False,
                "error": "SQL语句不能为空"
            }
        
        sql = sql.strip()
        
        # 2. 只读模式检查（CLI层防护）
        if is_readonly_mode():
            enforcer = ReadOnlyEnforcer(enabled=True)
            allowed, reason = enforcer.check(sql)
            if not allowed:
                logger.warning(f"MCP只读模式拦截: {reason}, SQL: {sql[:100]}")
                return {
                    "success": False,
                    "error": reason,
                    "risk_level": "HIGH",
                    "blocked_by": "readonly_middleware"
                }
        
        # 3. 解析SQL
        try:
            parsed = self.sql_parser.parse(sql)
        except Exception as e:
            logger.error(f"SQL解析失败: {sql}, 错误: {str(e)}")
            return {
                "success": False,
                "error": f"SQL解析失败: {str(e)}"
            }
        
        # 3. 使用安全执行器执行
        result = self.security_executor.execute(
            sql=sql,
            database=database,
            force=force,
            confirmed=confirmed,
            user=user,
            client_ip=client_ip
        )
        
        return result
    
    def validate_sql(
        self,
        sql: str,
        database: str
    ) -> Dict[str, Any]:
        """
        验证SQL（不执行）
        
        用于在执行前检查SQL的安全性和影响范围
        
        参数：
            sql: SQL语句
            database: 数据库名
            
        返回：
            Dict: 验证结果
        """
        if not sql or not sql.strip():
            return {
                "valid": False,
                "error": "SQL语句不能为空"
            }
        
        sql = sql.strip()
        
        # 解析SQL
        try:
            parsed = self.sql_parser.parse(sql)
        except Exception as e:
            return {
                "valid": False,
                "error": f"SQL解析失败: {str(e)}"
            }
        
        # 评估风险
        is_dangerous = parsed.is_dangerous_without_where()
        
        # 获取策略
        policy = get_security_policy()
        
        # 构建验证结果
        result = {
            "valid": True,
            "sql_type": parsed.sql_type.value,
            "tables": parsed.tables,
            "is_read_only": parsed.is_read_only,
            "has_where": parsed.has_where,
            "is_dangerous": is_dangerous,
            "risk_level": "HIGH" if is_dangerous else "MEDIUM" if not parsed.is_read_only else "SAFE",
            "requires_force": is_dangerous,
            "requires_confirmation": not parsed.is_read_only and not is_dangerous,
            "message": "SQL验证通过"
        }
        
        if is_dangerous:
            result["warning"] = "此SQL缺少WHERE子句，将操作整张表"
            result["suggestion"] = "请添加WHERE条件限制操作范围"
        
        return result
    
    def get_security_status(self) -> Dict[str, Any]:
        """
        获取安全状态
        
        返回当前安全策略配置和状态
        
        返回：
            Dict: 安全状态
        """
        policy = get_security_policy()
        
        return {
            "environment": self._get_environment(),
            "default_read_only": policy.default_read_only,
            "max_delete_rows": policy.max_delete_rows,
            "max_update_rows": policy.max_update_rows,
            "enable_audit": policy.enable_audit,
            "blocked_operations": list(policy.blocked_operations),
            "whitelist_tables": list(policy.whitelist_tables) if policy.whitelist_tables else [],
            "blacklist_tables": list(policy.blacklist_tables) if policy.blacklist_tables else []
        }
    
    def _get_environment(self) -> str:
        """获取当前环境"""
        import os
        return os.getenv("DBSKITER_ENV", "production")
    
    def close(self):
        """关闭资源"""
        if self.security_executor:
            self.security_executor.close()
        logger.info("MCPSecurityWrapper 已关闭")
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


class SecureSQLTool:
    """
    安全SQL工具
    
    为MCP Server提供的标准SQL工具实现
    
    使用示例：
        tool = SecureSQLTool(connector)
        
        # MCP工具调用
        result = tool.execute(
            database="mydb",
            sql="SELECT * FROM users LIMIT 10"
        )
    """
    
    def __init__(self, connector: UnifiedConnector):
        """
        初始化安全SQL工具
        
        参数：
            connector: 数据库连接器
        """
        self.wrapper = MCPSecurityWrapper(connector)
    
    def execute(
        self,
        database: str,
        sql: str,
        force: bool = False,
        confirmed: bool = False
    ) -> Dict[str, Any]:
        """
        执行SQL（MCP工具标准接口）
        
        参数：
            database: 数据库名
            sql: SQL语句
            force: 是否强制执行
            confirmed: 是否已确认
            
        返回：
            Dict: 执行结果
        """
        return self.wrapper.execute_sql(
            sql=sql,
            database=database,
            force=force,
            confirmed=confirmed
        )
    
    def validate(
        self,
        database: str,
        sql: str
    ) -> Dict[str, Any]:
        """
        验证SQL（MCP工具标准接口）
        
        参数：
            database: 数据库名
            sql: SQL语句
            
        返回：
            Dict: 验证结果
        """
        return self.wrapper.validate_sql(sql, database)
    
    def close(self):
        """关闭工具"""
        self.wrapper.close()


# 便捷函数

def create_secure_sql_tool(connector: UnifiedConnector) -> SecureSQLTool:
    """
    创建安全SQL工具的便捷函数
    
    参数：
        connector: 数据库连接器
        
    返回：
        SecureSQLTool: 安全SQL工具实例
    """
    return SecureSQLTool(connector)


def execute_sql_safely(
    sql: str,
    database: str,
    connector: UnifiedConnector,
    force: bool = False,
    confirmed: bool = False
) -> Dict[str, Any]:
    """
    安全执行SQL的便捷函数
    
    参数：
        sql: SQL语句
        database: 数据库名
        connector: 数据库连接器
        force: 是否强制执行
        confirmed: 是否已确认
        
    返回：
        Dict: 执行结果
    """
    with MCPSecurityWrapper(connector) as wrapper:
        return wrapper.execute_sql(
            sql=sql,
            database=database,
            force=force,
            confirmed=confirmed
        )


# 导出公共接口
__all__ = [
    "MCPSecurityWrapper",
    "SecureSQLTool",
    "create_secure_sql_tool",
    "execute_sql_safely",
]
