"""
utils mixin for MonitorSkill

Auto-extracted from skill.py.
"""

import logging
logger = logging.getLogger(__name__)
from typing import List, Dict, Any, Optional, Callable, Set
from datetime import datetime

from dbskiter.db_monitor.models import (
    MetricType, MetricPoint, AnomalyAlert, MonitorConfig,
    HealthAssessment, CapacityPrediction, HealthStatus,
    AnomalyType, Severity, ErrorCode,
)
from dbskiter.shared.error_handler import create_success_response, create_error_response
from dbskiter.shared.validators import validate_params, Validator


class MonitorUtilsMixin:
    """utils for MonitorSkill"""

    def _get_instance_name(self) -> Optional[str]:
        """获取 Prometheus 实例名"""
        import os
        # 优先从环境变量获取
        instance = os.getenv("PROMETHEUS_INSTANCE_NAME")
        if instance:
            return instance
        # 尝试从数据库连接信息推断
        if self.connector:
            # 使用主机名或IP作为实例名
            host = getattr(self.connector, 'host', None)
            if host:
                return f"rds-{host.replace('.', '-')}"
        return None


    def _get_host_name(self) -> Optional[str]:
        """
        获取 Zabbix/Prometheus 主机名

        支持 host_name 列表，返回第一个有效的主机名
        """
        import os
        from typing import List

        # 1. 优先使用传入的 host_name（CLI --database 参数）
        if self._host_name:
            # 如果是列表，尝试每个主机名，返回第一个存在的
            if isinstance(self._host_name, list):
                return self._find_first_valid_host(self._host_name)
            return self._host_name

        # 2. 从环境变量获取
        host = os.getenv("ZABBIX_HOST_NAME") or os.getenv("PROMETHEUS_INSTANCE_NAME")
        if host:
            return host

        # 3. 尝试从数据库连接信息推断
        if self.connector:
            # 获取数据库名（如 z18）
            db_name = getattr(self.connector, 'database', None)
            if db_name:
                # Z系列数据库直接使用 Z 名称
                # 例如：z18 -> Z18（数据库服务器 Z18-160）
                if db_name.lower().startswith('z'):
                    return db_name.upper()
                return db_name
            # 回退到使用主机名
            host = getattr(self.connector, 'host', None)
            if host:
                return host
        return None


    def _find_first_valid_host(self, host_names: List[str]) -> Optional[str]:
        """
        从 host_name 列表中找到第一个有效的主机

        支持前缀匹配（如 "Z18-" 匹配 "Z18-80", "Z18-160"）

        参数:
            host_names: 主机名列表（可以是完整主机名或前缀）

        返回:
            第一个存在的主机名，或 None
        """
        if not self.zabbix_client:
            # 如果没有 Zabbix 客户端，返回第一个
            return host_names[0] if host_names else None

        try:
            # 获取所有主机
            all_hosts = self.zabbix_client.get_hosts()
            host_name_set = {h['host'] for h in all_hosts}

            # 找到第一个存在的主机（支持前缀匹配）
            for pattern in host_names:
                # 如果是前缀（以 - 或 _ 结尾），进行前缀匹配
                if pattern.endswith('-') or pattern.endswith('_'):
                    for host_name in host_name_set:
                        if host_name.startswith(pattern):
                            logger.info(f"找到有效主机: {host_name} (匹配前缀 {pattern})")
                            return host_name
                else:
                    # 完整匹配
                    if pattern in host_name_set:
                        logger.info(f"找到有效主机: {pattern}")
                        return pattern

            logger.warning(f"列表中所有主机都不存在: {host_names}")
            return host_names[0] if host_names else None  # 返回第一个，让后续报错
        except Exception as e:
            logger.warning(f"查找主机失败: {e}")
            return host_names[0] if host_names else None

    # ==================== 健康评估 ====================

    @validate_params()

    def _init_external_monitoring(self):
        """初始化外部监控系统客户端"""
        import os

        # 初始化 Prometheus 客户端
        prometheus_url = os.getenv("PROMETHEUS_URL")
        if prometheus_url:
            try:
                self.prometheus_client = PrometheusClient(prometheus_url)
                logger.info(f"Prometheus 客户端初始化成功: {prometheus_url}")
            except Exception as e:
                logger.warning(f"Prometheus 客户端初始化失败: {e}")

        # 初始化 Zabbix 客户端
        zabbix_url = os.getenv("ZABBIX_URL")
        zabbix_user = os.getenv("ZABBIX_USER")
        zabbix_password = os.getenv("ZABBIX_PASSWORD")

        if zabbix_url and zabbix_user and zabbix_password:
            try:
                self.zabbix_client = ZabbixClient(zabbix_url)
                if self.zabbix_client.login(zabbix_user, zabbix_password):
                    logger.info(f"Zabbix 客户端初始化成功: {zabbix_url}")
                else:
                    logger.warning("Zabbix 登录失败")
                    self.zabbix_client = None
            except Exception as e:
                logger.warning(f"Zabbix 客户端初始化失败: {e}")

