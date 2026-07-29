"""
monitoring mixin for MonitorSkill

Auto-extracted from skill.py.
"""

import logging

logger = logging.getLogger(__name__)
from typing import List, Dict, Any, Optional, Callable, Set
from datetime import datetime

from dbskiter.db_monitor.models import (
    MetricType,
    MetricPoint,
    AnomalyAlert,
    MonitorConfig,
    HealthAssessment,
    CapacityPrediction,
    HealthStatus,
    AnomalyType,
    Severity,
    ErrorCode,
)
from dbskiter.shared.error_handler import create_success_response, create_error_response
from dbskiter.shared.validators import validate_params, Validator


class MonitoringMixin:
    """monitoring for MonitorSkill"""

    def start_monitoring(
        self, callback: Optional[Callable[[AnomalyAlert], None]] = None, interval: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        启动实时监控

        参数:
            callback: 异常告警回调函数
            interval: 采集间隔（秒），默认使用配置值

        返回:
            Dict: 启动结果
        """
        if self._is_monitoring:
            return create_error_response("监控已在运行中", error_code=ErrorCode.ALREADY_EXISTS)

        if not self.collector:
            return create_error_response("未提供数据库连接器", error_code=ErrorCode.CONNECTION_ERROR)

        # 添加回调
        if callback:
            self._alert_handlers.append(callback)

        self._is_monitoring = True
        interval = interval or self.config.collection_interval

    def stop_monitoring(self) -> Dict[str, Any]:
        """
        停止实时监控

        返回:
            Dict: 停止结果
        """
        if not self._is_monitoring:
            return create_error_response("监控未在运行", error_code=ErrorCode.NOT_FOUND)

        self._is_monitoring = False

        if self._monitoring_thread:
            self._monitoring_thread.join(timeout=5)
            self._monitoring_thread = None

        logger.info("实时监控已停止")
        return create_success_response(message="实时监控已停止")

    def add_alert_handler(self, handler: Callable[[AnomalyAlert], None]):
        """添加告警处理器"""
        self._alert_handlers.append(handler)

    # ==================== 告警管理 ====================

    @validate_params()
    def get_alerts(self, hours: int = 24, acknowledged: Optional[bool] = None) -> Dict[str, Any]:
        """
        获取告警历史

        参数:
            hours: 查询小时数
            acknowledged: 是否已确认

        返回:
            Dict: 告警列表
        """
        if not self.storage:
            return create_error_response("未启用持久化存储", error_code=ErrorCode.STORAGE_ERROR)

        try:
            alerts = self.storage.get_alerts(hours, acknowledged)

            return create_success_response(message=f"获取到 {len(alerts)} 条告警", data={"alerts": alerts})
        except Exception as e:
            logger.error(f"获取告警失败: {e}")
            return create_error_response("获取告警失败", error_code=ErrorCode.STORAGE_ERROR, details={"error": str(e)})

    def acknowledge_alert(self, alert_id: str) -> Dict[str, Any]:
        """确认告警"""
        if not self.storage:
            return create_error_response("未启用持久化存储", error_code=ErrorCode.STORAGE_ERROR)
        return self.storage.acknowledge_alert(alert_id)

    def get_storage_stats(self) -> Dict[str, Any]:
        """获取存储统计"""
        if not self.storage:
            return create_error_response("未启用持久化存储", error_code=ErrorCode.STORAGE_ERROR)
        return create_success_response(message="获取存储统计成功", data=self.storage.get_statistics())

    def cleanup_storage(self, days: int = 30) -> Dict[str, Any]:
        """清理过期数据"""
        if not self.storage:
            return create_error_response("未启用持久化存储", error_code=ErrorCode.STORAGE_ERROR)
        return self.storage.cleanup_old_data(days)

    # ==================== 资源释放 ====================

    def close(self):
        """关闭Skill，释放资源"""
        logger.info("关闭 MonitorSkill...")

        # 停止监控线程
        if self._is_monitoring:
            self._is_monitoring = False
            if self._monitoring_thread:
                self._monitoring_thread.join(timeout=5)
                self._monitoring_thread = None
            logger.info("监控线程已停止")

        # 关闭存储
        if self.storage:
            self.storage.close()
            logger.info("存储已关闭")

        # 清理告警处理器
        self._alert_handlers.clear()
        self.alert_manager.reset()

        logger.info("MonitorSkill 已关闭")

    # ==================== 高级功能（新增）====================
