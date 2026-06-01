"""
安全策略配置模块

文件功能：定义和管理数据库操作的安全策略配置
主要类：
    - SecurityLevel: 安全级别枚举
    - SecurityPolicy: 安全策略配置类
    - SecurityConfig: 安全配置类（支持环境变量覆盖）

配置层级（优先级从高到低）：
    1. 环境变量（DBSKITER_*）
    2. 环境特定配置（production/development/testing）
    3. 系统默认配置

作者：Security Team
创建时间：2026-05-20
最后修改：2026-05-20
"""

import os
import logging
from typing import Dict, Any, List, Optional, Set
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

try:
    from dotenv import load_dotenv
    HAS_DOTENV = True
except ImportError:
    HAS_DOTENV = False

logger = logging.getLogger(__name__)


class SecurityLevel(Enum):
    """
    安全级别枚举

    定义操作的风险等级，从低到高：
        SAFE: 安全操作，无需特殊处理
        MEDIUM: 中等风险，建议确认
        HIGH: 高风险，必须确认
        CRITICAL: 极高风险，默认禁止
    """
    SAFE = "SAFE"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class OperationType(Enum):
    """操作类型枚举"""
    SELECT = "SELECT"
    INSERT = "INSERT"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    DROP = "DROP"
    TRUNCATE = "TRUNCATE"
    ALTER = "ALTER"
    CREATE = "CREATE"


@dataclass(frozen=True)
class SecurityPolicy:
    """
    安全策略配置类（不可变）

    这是一个纯数据类，不包含任何逻辑。
    所有配置应该在创建时确定，运行时不可变。

    属性说明：
        default_read_only: 默认是否只读模式
        require_confirmation_levels: 需要确认的安全级别集合
        require_force_levels: 需要force参数的安全级别集合
        blocked_operations: 完全禁止的操作集合
        max_delete_rows: 单次最大删除行数（0表示不限制）
        max_update_rows: 单次最大更新行数（0表示不限制）
        enable_audit: 是否启用审计日志
        enable_backup_reminder: 是否启用备份提醒
        enable_impact_preview: 是否启用影响预览
        whitelist_tables: 白名单表集合（允许宽松操作）
        blacklist_tables: 黑名单表集合（禁止操作）
    """

    # 基础安全设置
    default_read_only: bool = True

    # 确认机制配置
    require_confirmation_levels: Set[SecurityLevel] = field(
        default_factory=lambda: {SecurityLevel.MEDIUM, SecurityLevel.HIGH, SecurityLevel.CRITICAL}
    )

    # 强制参数配置
    require_force_levels: Set[SecurityLevel] = field(
        default_factory=lambda: {SecurityLevel.HIGH, SecurityLevel.CRITICAL}
    )

    # 完全禁止的操作（即使加force也禁止）
    blocked_operations: Set[str] = field(default_factory=set)

    # 行数限制
    max_delete_rows: int = 1000
    max_update_rows: int = 1000

    # 功能开关
    enable_audit: bool = True
    enable_backup_reminder: bool = True
    enable_impact_preview: bool = True

    # 表级控制
    whitelist_tables: Set[str] = field(default_factory=set)
    blacklist_tables: Set[str] = field(default_factory=set)

    def requires_confirmation(self, level: SecurityLevel) -> bool:
        """检查指定级别是否需要确认"""
        return level in self.require_confirmation_levels

    def requires_force(self, level: SecurityLevel) -> bool:
        """检查指定级别是否需要force参数"""
        return level in self.require_force_levels

    def is_blocked(self, operation: str) -> bool:
        """检查操作是否被完全禁止"""
        return operation.upper() in {op.upper() for op in self.blocked_operations}


class SecurityConfig:
    """
    安全配置类

    负责从环境变量读取配置并创建SecurityPolicy。
    配置在初始化时确定，运行时不改变。

    使用示例：
        # 自动从环境变量加载
        config = SecurityConfig()
        policy = config.policy

        # 或手动指定环境
        config = SecurityConfig(environment="production")
    """

    # 基础配置模板
    _TEMPLATES: Dict[str, Dict[str, Any]] = {
        "production": {
            "default_read_only": True,
            "require_confirmation_levels": {SecurityLevel.MEDIUM, SecurityLevel.HIGH, SecurityLevel.CRITICAL},
            "require_force_levels": {SecurityLevel.HIGH, SecurityLevel.CRITICAL},
            "blocked_operations": {"DROP_DATABASE", "DROP_SCHEMA"},
            "max_delete_rows": 100,
            "max_update_rows": 100,
            "enable_audit": True,
            "enable_backup_reminder": True,
            "enable_impact_preview": True,
        },
        "development": {
            "default_read_only": False,
            "require_confirmation_levels": {SecurityLevel.HIGH, SecurityLevel.CRITICAL},
            "require_force_levels": {SecurityLevel.CRITICAL},
            "blocked_operations": {"DROP_DATABASE"},
            "max_delete_rows": 10000,
            "max_update_rows": 10000,
            "enable_audit": True,
            "enable_backup_reminder": True,
            "enable_impact_preview": True,
        },
        "testing": {
            "default_read_only": False,
            "require_confirmation_levels": {SecurityLevel.CRITICAL},
            "require_force_levels": {SecurityLevel.CRITICAL},
            "blocked_operations": set(),
            "max_delete_rows": 0,
            "max_update_rows": 0,
            "enable_audit": False,
            "enable_backup_reminder": False,
            "enable_impact_preview": False,
        }
    }

    # 环境变量映射
    _ENV_MAPPINGS = {
        "DBSKITER_ENV": "environment",
        "DBSKITER_MAX_DELETE_ROWS": "max_delete_rows",
        "DBSKITER_MAX_UPDATE_ROWS": "max_update_rows",
        "DBSKITER_BLOCKED_OPERATIONS": "blocked_operations",
        "DBSKITER_WHITELIST_TABLES": "whitelist_tables",
        "DBSKITER_BLACKLIST_TABLES": "blacklist_tables",
        "DBSKITER_ENABLE_AUDIT": "enable_audit",
        "DBSKITER_ENABLE_BACKUP_REMINDER": "enable_backup_reminder",
        "DBSKITER_ENABLE_IMPACT_PREVIEW": "enable_impact_preview",
        "DBSKITER_REQUIRE_CONFIRMATION": "require_confirmation",
        "DBSKITER_DEFAULT_READ_ONLY": "default_read_only",
        "DBSKITER_READ_ONLY": "default_read_only",
    }

    def __init__(self, environment: Optional[str] = None):
        """
        初始化安全配置

        配置加载顺序：
            1. 加载.env文件
            2. 从DBSKITER_ENV确定基础模板
            3. 用其他DBSKITER_*环境变量覆盖

        参数:
            environment: 环境名称，None则从DBSKITER_ENV读取
        """
        # 加载.env文件
        if HAS_DOTENV:
            env_path = Path.cwd() / ".env"
            if not env_path.exists():
                # 尝试从项目根目录查找
                env_path = Path(__file__).parent.parent.parent / ".env"
            if env_path.exists():
                load_dotenv(env_path)
                logger.debug(f"已加载环境变量文件: {env_path}")

        # 确定环境
        self._environment = self._detect_environment(environment)

        # 加载基础模板
        config = self._load_template(self._environment)

        # 应用环境变量覆盖
        config = self._apply_env_overrides(config)

        # 创建策略对象（创建后不可变）
        self._policy = SecurityPolicy(**config)

        # 记录配置来源
        self._log_config_source()

    def _detect_environment(self, environment: Optional[str]) -> str:
        """
        检测运行环境

        优先级：
            1. 传入的参数
            2. DBSKITER_ENV环境变量
            3. 默认production
        """
        if environment:
            env = environment.lower()
            if env in self._TEMPLATES:
                return env
            logger.warning(f"未知环境 '{environment}'，使用 production")
            return "production"

        env = os.getenv("DBSKITER_ENV", "").lower()
        if env in self._TEMPLATES:
            logger.info(f"从环境变量检测到环境: {env}")
            return env

        logger.warning("未检测到环境配置，默认使用 production")
        return "production"

    def _load_template(self, environment: str) -> Dict[str, Any]:
        """加载基础配置模板"""
        return self._TEMPLATES[environment].copy()

    def _apply_env_overrides(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        应用环境变量覆盖

        支持的覆盖：
            DBSKITER_MAX_DELETE_ROWS: int
            DBSKITER_MAX_UPDATE_ROWS: int
            DBSKITER_BLOCKED_OPERATIONS: 逗号分隔的字符串
            DBSKITER_WHITELIST_TABLES: 逗号分隔的字符串
            DBSKITER_BLACKLIST_TABLES: 逗号分隔的字符串
            DBSKITER_ENABLE_AUDIT: true/false
            DBSKITER_ENABLE_BACKUP_REMINDER: true/false
            DBSKITER_ENABLE_IMPACT_PREVIEW: true/false
            DBSKITER_REQUIRE_CONFIRMATION: true/false
            DBSKITER_DEFAULT_READ_ONLY: true/false
        """
        config = config.copy()

        # 行数限制
        if value := os.getenv("DBSKITER_MAX_DELETE_ROWS"):
            try:
                config["max_delete_rows"] = int(value)
            except ValueError:
                logger.warning(f"无效的 DBSKITER_MAX_DELETE_ROWS: {value}")

        if value := os.getenv("DBSKITER_MAX_UPDATE_ROWS"):
            try:
                config["max_update_rows"] = int(value)
            except ValueError:
                logger.warning(f"无效的 DBSKITER_MAX_UPDATE_ROWS: {value}")

        # 集合类型（逗号分隔）
        if value := os.getenv("DBSKITER_BLOCKED_OPERATIONS"):
            config["blocked_operations"] = {
                op.strip().upper()
                for op in value.split(",")
                if op.strip()
            }

        if value := os.getenv("DBSKITER_WHITELIST_TABLES"):
            config["whitelist_tables"] = {
                t.strip()
                for t in value.split(",")
                if t.strip()
            }

        if value := os.getenv("DBSKITER_BLACKLIST_TABLES"):
            config["blacklist_tables"] = {
                t.strip()
                for t in value.split(",")
                if t.strip()
            }

        # 布尔类型
        if value := os.getenv("DBSKITER_ENABLE_AUDIT"):
            config["enable_audit"] = value.lower() in ("true", "1", "yes")

        if value := os.getenv("DBSKITER_ENABLE_BACKUP_REMINDER"):
            config["enable_backup_reminder"] = value.lower() in ("true", "1", "yes")

        if value := os.getenv("DBSKITER_ENABLE_IMPACT_PREVIEW"):
            config["enable_impact_preview"] = value.lower() in ("true", "1", "yes")

        if value := os.getenv("DBSKITER_DEFAULT_READ_ONLY"):
            config["default_read_only"] = value.lower() in ("true", "1", "yes")

        # DBSKITER_READ_ONLY 与 DBSKITER_DEFAULT_READ_ONLY 取OR关系
        if value := os.getenv("DBSKITER_READ_ONLY"):
            if value.lower() in ("true", "1", "yes"):
                config["default_read_only"] = True

        # 确认级别特殊处理
        if value := os.getenv("DBSKITER_REQUIRE_CONFIRMATION"):
            if value.lower() in ("false", "0", "no"):
                config["require_confirmation_levels"] = {SecurityLevel.CRITICAL}
            else:
                config["require_confirmation_levels"] = {
                    SecurityLevel.MEDIUM, SecurityLevel.HIGH, SecurityLevel.CRITICAL
                }

        return config

    def _log_config_source(self):
        """记录配置来源信息"""
        logger.info(f"安全配置已加载 - 环境: {self._environment}")
        logger.info(f"  默认只读: {self._policy.default_read_only}")
        logger.info(f"  最大删除行数: {self._policy.max_delete_rows}")
        logger.info(f"  启用审计: {self._policy.enable_audit}")

    @property
    def policy(self) -> SecurityPolicy:
        """获取安全策略（只读）"""
        return self._policy

    @property
    def environment(self) -> str:
        """获取当前环境"""
        return self._environment

    def to_dict(self) -> Dict[str, Any]:
        """导出配置为字典（用于调试）"""
        return {
            "environment": self._environment,
            "policy": {
                "default_read_only": self._policy.default_read_only,
                "max_delete_rows": self._policy.max_delete_rows,
                "max_update_rows": self._policy.max_update_rows,
                "enable_audit": self._policy.enable_audit,
                "enable_backup_reminder": self._policy.enable_backup_reminder,
                "enable_impact_preview": self._policy.enable_impact_preview,
                "blocked_operations": list(self._policy.blocked_operations),
                "whitelist_tables": list(self._policy.whitelist_tables),
                "blacklist_tables": list(self._policy.blacklist_tables),
                "require_confirmation_levels": [
                    level.value for level in self._policy.require_confirmation_levels
                ],
                "require_force_levels": [
                    level.value for level in self._policy.require_force_levels
                ],
            }
        }


# 全局配置实例（延迟初始化）
_config_instance: Optional[SecurityConfig] = None


def get_security_config() -> SecurityConfig:
    """
    获取全局安全配置实例

    首次调用时创建实例，后续调用返回同一实例。
    如果需要重新加载配置，需要重启进程。

    返回:
        SecurityConfig: 安全配置实例
    """
    global _config_instance
    if _config_instance is None:
        _config_instance = SecurityConfig()
    return _config_instance


def get_security_policy() -> SecurityPolicy:
    """
    获取安全策略的便捷函数

    返回:
        SecurityPolicy: 安全策略对象
    """
    return get_security_config().policy


def get_current_environment() -> str:
    """
    获取当前环境的便捷函数

    返回:
        str: 环境名称
    """
    return get_security_config().environment


def reset_config():
    """
    重置全局配置（仅用于测试）

    警告：不要在生产代码中使用
    """
    global _config_instance
    _config_instance = None
    logger.warning("安全配置已重置")


# 导出公共接口
__all__ = [
    "SecurityLevel",
    "OperationType",
    "SecurityPolicy",
    "SecurityConfig",
    "get_security_config",
    "get_security_policy",
    "get_current_environment",
    "reset_config",
]
