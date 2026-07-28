"""
dbskiter/web/connector_helper.py

Web 数据库连接器辅助模块

从 Web UI 的 SQLite 数据库配置中读取数据库连接信息，
构建 UnifiedConnector 实例，用于进程内调用 skill 类。

核心功能：
- 从 Web UI 配置构建 UnifiedConnector（解决 CLI 子进程找不到 Web 配置的问题）
- 提供统一的 skill 执行接口
- 自动管理连接生命周期

使用示例：
    >>> from .connector_helper import get_connector, run_skill
    >>> connector = get_connector("mydb")
    >>> result = connector.execute("SELECT 1")
"""

import logging
from typing import Optional, Dict, Any, Type, Callable

from dbskiter.shared.unified_connector import UnifiedConnector

logger = logging.getLogger(__name__)


def get_connector(alias: str) -> Optional[UnifiedConnector]:
    """
    从 Web UI 的数据库配置中构建 UnifiedConnector

    从 Web UI 的 SQLite 存储（web.db）中读取 alias 对应的配置，
    构建 UnifiedConnector 实例。

    参数:
        alias: 数据库别名

    返回:
        Optional[UnifiedConnector]: 连接器实例，别名不存在时返回 None
    """
    from .database import get_all_db_configs

    configs = get_all_db_configs()
    if alias not in configs:
        # 尝试从 .env 环境变量加载
        try:
            from dbskiter.cli.config import MultiDBConfig
            mc = MultiDBConfig()
            config = mc.get_config_by_alias(alias)
            if config:
                return UnifiedConnector(
                    dialect=config.dialect,
                    host=config.host,
                    port=config.port,
                    username=config.username,
                    password=config.password,
                    database=config.database,
                )
        except Exception:
            pass
        return None

    cfg = configs[alias]
    try:
        connector = UnifiedConnector(
            dialect=cfg.get("dialect", "mysql+pymysql"),
            host=cfg.get("host", "127.0.0.1"),
            port=int(cfg.get("port", 3306)),
            username=cfg.get("user", "root"),
            password=cfg.get("password", ""),
            database=cfg.get("database", ""),
        )
        return connector
    except Exception as e:
        logger.error(f"构建连接器失败 [{alias}]: {e}")
        return None


def get_connector_from_config(config: dict) -> Optional[UnifiedConnector]:
    """
    从配置字典构建 UnifiedConnector（用于测试连接等场景）

    参数:
        config: 配置字典，包含 host/port/user/password/database/dialect

    返回:
        Optional[UnifiedConnector]: 连接器实例
    """
    try:
        return UnifiedConnector(
            dialect=config.get("dialect", "mysql+pymysql"),
            host=config.get("host", "127.0.0.1"),
            port=int(config.get("port", 3306)),
            username=config.get("user", "root"),
            password=config.get("password", ""),
            database=config.get("database", ""),
        )
    except Exception as e:
        logger.error(f"构建连接器失败: {e}")
        return None


def run_skill(
    alias: str,
    skill_cls: Type,
    method: str,
    *args,
    **kwargs
) -> Dict[str, Any]:
    """
    通用 skill 执行器：构建连接器 → 实例化 skill → 调用方法 → 清理

    参数:
        alias: 数据库别名
        skill_cls: Skill 类（如 DiagnoseSkill, MonitorSkill）
        method: 要调用的方法名
        *args: 传递给方法的参数
        **kwargs: 传递给方法的关键字参数

    返回:
        dict: 统一格式的响应字典
    """
    connector = get_connector(alias)
    if not connector:
        return {
            "success": False,
            "error": f"数据库 '{alias}' 未配置",
            "hint": "请在 Web 界面添加数据库配置，或检查 .env 文件",
        }

    skill = None
    try:
        skill = skill_cls(connector)
        result = getattr(skill, method)(*args, **kwargs)
        return {"success": True, "data": result}
    except Exception as e:
        logger.error(f"Skill 执行失败 [{alias}.{method}]: {e}")
        return {"success": False, "error": str(e)}
    finally:
        try:
            if skill and hasattr(skill, 'close'):
                skill.close()
        except Exception as e:
            logger.warning(f"关闭 skill 时异常: {e}")
        try:
            connector.close()
        except Exception as e:
            logger.warning(f"关闭连接器时异常: {e}")


def test_connection(alias_or_config) -> Dict[str, Any]:
    """
    测试数据库连接（执行 SELECT 1）

    参数:
        alias_or_config: 数据库别名（str）或配置字典（dict）

    返回:
        dict: {"success": bool, "message": str}
    """
    if isinstance(alias_or_config, str):
        connector = get_connector(alias_or_config)
    else:
        connector = get_connector_from_config(alias_or_config)

    if not connector:
        return {"success": False, "message": "无法构建数据库连接器，请检查配置"}

    try:
        from dbskiter.shared.query_result import QueryResult
        result = connector.execute("SELECT 1 AS test")
        if result is not None:
            return {"success": True, "message": "连接成功 🎉"}
        return {"success": False, "message": "连接失败：查询未返回结果"}
    except Exception as e:
        error_msg = str(e).lower()
        # 友好错误提示
        if "access denied" in error_msg:
            return {"success": False, "message": "连接失败：用户名或密码错误"}
        if "can't connect" in error_msg or "connection refused" in error_msg:
            return {"success": False, "message": "连接失败：无法连接到数据库，请检查主机地址和端口"}
        if "unknown database" in error_msg:
            return {"success": False, "message": "连接失败：数据库名不存在"}
        if "timeout" in error_msg:
            return {"success": False, "message": "连接超时：请检查网络连通性"}
        return {"success": False, "message": f"连接失败: {str(e)[:200]}"}
    finally:
        try:
            connector.close()
        except Exception:
            pass