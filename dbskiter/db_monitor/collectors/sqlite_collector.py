"""
SQLite监控指标采集器

提供SQLite数据库的监控指标采集能力

文件功能：SQLite数据库监控指标采集器实现
主要类：SQLiteMetricsCollector - SQLite监控指标采集器

支持的指标：
    - 连接指标：活跃连接数
    - 资源指标：数据库大小、缓存使用率
    - 查询性能：慢查询数
    - 存储指标：页面统计、空闲页面

依赖：
    - sqlite3 标准库
    - SQLite 3.8+

作者：Magiczc
创建时间：2026-06-03
版本：1.0.0
"""

import logging
import os
from datetime import datetime
from typing import Dict, Any, List, Optional

from .base import BaseMetricsCollector, MetricType, MetricPoint, MetricQuery
from dbskiter.shared.unified_connector import UnifiedConnector

logger = logging.getLogger(__name__)


class SQLiteMetricsCollector(BaseMetricsCollector):
    """
    SQLite监控指标采集器

    提供SQLite特有的监控指标采集：
    - 数据库文件大小
    - 缓存使用率
    - 页面统计
    - 空闲页面数
    - 日志模式

    特性：
    - 基于PRAGMA命令获取指标
    - 支持文件系统级别的监控
    """

    def __init__(self, connector: UnifiedConnector):
        """
        初始化SQLite采集器

        参数：
            connector: UnifiedConnector实例
        """
        super().__init__(connector)
        self._database_path = None

    def _get_database_path(self) -> Optional[str]:
        """
        获取数据库文件路径

        返回：
            Optional[str]: 数据库文件路径或None
        """
        if self._database_path is None:
            try:
                result = self.connector.execute("PRAGMA database_list")
                if result and result.rows:
                    for row in result.rows:
                        if row[1] == 'main':
                            self._database_path = row[2]
                            break
            except Exception as e:
                logger.warning(f"获取数据库路径失败: {e}")
        return self._database_path

    def get_metric_queries(self) -> Dict[MetricType, MetricQuery]:
        """
        获取SQLite指标查询定义

        返回：
            Dict[MetricType, MetricQuery]: 指标类型到查询定义的映射
        """
        queries = {}

        # 数据库大小（页面数 * 页面大小）
        queries[MetricType.DISK_USAGE] = MetricQuery(
            sql="PRAGMA page_count",
            extract=lambda rows: self._calculate_db_size(rows),
            unit="bytes",
            is_counter=False
        )

        # 缓存大小
        queries[MetricType.MEMORY_USAGE] = MetricQuery(
            sql="PRAGMA cache_size",
            extract=lambda rows: int(rows[0][0]) if rows else 0,
            unit="pages",
            is_counter=False
        )

        # 空闲页面数
        queries[MetricType.DISK_IO_READ] = MetricQuery(
            sql="PRAGMA freelist_count",
            extract=lambda rows: int(rows[0][0]) if rows else 0,
            unit="pages",
            is_counter=False
        )

        return queries

    def _calculate_db_size(self, rows) -> float:
        """
        计算数据库大小

        参数：
            rows: PRAGMA page_count结果

        返回：
            float: 数据库大小（字节）
        """
        try:
            page_count = int(rows[0][0]) if rows else 0

            # 获取页面大小
            result = self.connector.execute("PRAGMA page_size")
            page_size = int(result.rows[0][0]) if result else 4096

            return float(page_count * page_size)
        except Exception as e:
            logger.warning(f"计算数据库大小失败: {e}")
            return 0.0

    def collect_file_metrics(self) -> List[MetricPoint]:
        """
        采集文件系统级别的指标

        返回：
            List[MetricPoint]: 文件指标数据点列表
        """
        metrics = []
        timestamp = datetime.now()

        db_path = self._get_database_path()
        if not db_path or db_path == ':memory:':
            return metrics

        try:
            # 文件大小
            file_size = os.path.getsize(db_path)
            metrics.append(MetricPoint(
                timestamp=timestamp,
                metric_type=MetricType.DISK_USAGE,
                value=float(file_size),
                unit="bytes",
                tags={"type": "file_size"}
            ))

            # WAL文件大小
            wal_path = db_path + "-wal"
            if os.path.exists(wal_path):
                wal_size = os.path.getsize(wal_path)
                metrics.append(MetricPoint(
                    timestamp=timestamp,
                    metric_type=MetricType.DISK_USAGE,
                    value=float(wal_size),
                    unit="bytes",
                    tags={"type": "wal_size"}
                ))

        except Exception as e:
            logger.warning(f"采集文件指标失败: {e}")

        return metrics

    def collect_all_metrics(self) -> List[MetricPoint]:
        """
        采集所有指标（包括基础指标和文件指标）

        返回：
            List[MetricPoint]: 所有指标数据点列表
        """
        # 采集基础指标
        metrics = super().collect_all_metrics()

        # 采集文件指标
        metrics.extend(self.collect_file_metrics())

        logger.info(f"SQLite共采集 {len(metrics)} 个指标")
        return metrics

    def get_health_status(self) -> Dict[str, Any]:
        """
        获取SQLite健康状态

        返回：
            Dict[str, Any]: 健康状态信息
        """
        status = {
            "status": "healthy",
            "checks": {}
        }

        # 检查完整性
        try:
            result = self.connector.execute("PRAGMA integrity_check")
            if result and result.rows:
                integrity = result.rows[0][0]
                status["checks"]["integrity"] = integrity
                if integrity != 'ok':
                    status["status"] = "critical"
            else:
                status["checks"]["integrity"] = "unknown"
        except Exception as e:
            status["checks"]["integrity"] = f"error: {str(e)}"

        # 检查碎片率
        try:
            result = self.connector.execute("PRAGMA page_count")
            page_count = int(result.rows[0][0]) if result else 0

            result = self.connector.execute("PRAGMA freelist_count")
            freelist_count = int(result.rows[0][0]) if result else 0

            if page_count > 0:
                fragmentation = (freelist_count / page_count) * 100
                status["checks"]["fragmentation"] = f"{fragmentation:.2f}%"
                if fragmentation > 50:
                    status["status"] = "warning"
            else:
                status["checks"]["fragmentation"] = "0%"
        except Exception as e:
            status["checks"]["fragmentation"] = f"error: {str(e)}"

        # 检查数据库大小
        try:
            db_path = self._get_database_path()
            if db_path and db_path != ':memory:':
                file_size = os.path.getsize(db_path)
                status["checks"]["file_size"] = self._format_bytes(file_size)

                # 如果大于1GB，标记为warning
                if file_size > 1024 * 1024 * 1024:
                    status["status"] = "warning"
        except Exception as e:
            status["checks"]["file_size"] = f"error: {str(e)}"

        return status

    def _format_bytes(self, size_bytes: int) -> str:
        """
        格式化字节数为人类可读格式

        参数：
            size_bytes: 字节数

        返回：
            str: 格式化后的字符串
        """
        if size_bytes is None or size_bytes < 0:
            return "0 B"
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.2f} PB"
