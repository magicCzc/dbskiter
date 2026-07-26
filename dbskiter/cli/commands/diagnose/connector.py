"""
诊断专用连接器

诊断命令（慢查询、锁分析、SQL诊断等）必须直连数据库，
不支持通过Zabbix或Prometheus查询。

匹配优先级：
    1. 按别名匹配（db_name 作为别名）
    2. 按数据库名匹配
    3. 按主机名匹配
    4. Z 系列资产组使用 ORACLE 配置
    5. 回退到标准连接器
"""

import logging
from typing import Any, Dict, Optional

from dbskiter.shared.unified_connector import UnifiedConnector
from dbskiter.shared.oracle_metrics import OracleHostMapping

logger = logging.getLogger(__name__)


def _try_unified(config) -> Optional[UnifiedConnector]:
    """从 Config 对象创建 UnifiedConnector"""
    return UnifiedConnector(
        dialect=config.dialect,
        host=config.host,
        port=config.port,
        username=config.username,
        password=config.password,
        database=config.database,
        **config.extra
    )


def _match_by_alias(db_name: str, configs: Dict[str, Any]) -> Optional[UnifiedConnector]:
    """1. 按别名匹配"""
    db_name_lower = db_name.lower()
    for instance_name, config in configs.items():
        if instance_name.lower() == db_name_lower:
            logger.info(f"找到匹配配置 [别名={instance_name}]: {config.host}/{config.database}")
            return _try_unified(config)
    return None


def _match_by_database(db_name: str, configs: Dict[str, Any]) -> Optional[UnifiedConnector]:
    """2. 按数据库名匹配"""
    db_name_lower = db_name.lower()
    for instance_name, config in configs.items():
        if config.database.lower() == db_name_lower:
            logger.info(f"找到匹配配置 [数据库={config.database}]: {config.host}/{config.database}")
            return _try_unified(config)
    return None


def _match_by_host(db_name: str, configs: Dict[str, Any]) -> Optional[UnifiedConnector]:
    """3. 按主机名匹配"""
    db_name_lower = db_name.lower()
    for instance_name, config in configs.items():
        if config.host.lower() == db_name_lower:
            logger.info(f"找到匹配配置 [主机={config.host}]: {config.host}/{config.database}")
            return _try_unified(config)
    return None


def _try_oracle_group(db_name: str, configs: Dict[str, Any]) -> Optional[UnifiedConnector]:
    """4. Z 系列资产组使用 ORACLE 配置"""
    if not OracleHostMapping.is_oracle_group(db_name):
        return None
    oracle_config = configs.get('ORACLE')
    if oracle_config:
        logger.info(f"使用 ORACLE 配置创建连接器: {db_name}")
        return _try_unified(oracle_config)
    logger.warning(f"资产组 {db_name} 没有配置 ORACLE 直连信息，无法执行诊断命令")
    return None


def _try_standard_connector(command, db_name: str) -> Optional[Any]:
    """5. 回退到标准连接器"""
    try:
        if db_name:
            command.args.database = db_name
        command.require_connector()
        return command.connector
    except Exception as e:
        logger.warning(f"使用标准连接器失败: {e}")
        return None


def _try_from_env() -> Optional[UnifiedConnector]:
    """6. 从环境变量创建通用连接器"""
    try:
        return UnifiedConnector.from_env()
    except Exception as e:
        logger.error(f"创建连接器失败: {e}")
        return None


def build_diagnose_connector(command, db_name: str, configs: Dict[str, Any]) -> Optional[Any]:
    """创建诊断专用的数据库连接器

    参数:
        command: DiagnoseCommand 实例（用于回退到标准连接器）
        db_name: 数据库别名或名称（如 'jump', 'chenzc', 'Z18'）
        configs: 配置字典，key为别名，value为Config对象

    返回:
        UnifiedConnector 实例，或 None（如果无法直连）
    """
    if db_name:
        # 按优先级尝试不同的匹配方式
        for matcher in (
            _match_by_alias,
            _match_by_database,
            _match_by_host,
            lambda n, c: _try_oracle_group(n, c),
        ):
            connector = matcher(db_name, configs)
            if connector is not None:
                return connector

    # 回退到标准连接器
    connector = _try_standard_connector(command, db_name)
    if connector is not None:
        return connector

    # 最后尝试从环境变量创建
    return _try_from_env()