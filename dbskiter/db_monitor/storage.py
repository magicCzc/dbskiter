"""
db_monitor/storage.py
数据存储模块

文件功能：
    - 指标数据持久化存储
    - 告警历史记录
    - SQLite数据库管理
    - 与db-scheduler保持一致的代码风格

主要类：
    - MetricsStorage: 指标存储管理器

版本: 3.0.0
作者: AI Assistant
创建时间: 2026-04-23
"""

import sqlite3
import json
import logging
import threading
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from pathlib import Path

from dbskiter.db_monitor.models import (
    MetricPoint, MetricType, AnomalyAlert, ErrorCode,
)
from dbskiter.shared.error_handler import create_error_response, create_success_response

logger = logging.getLogger(__name__)


class MetricsStorage:
    """
    指标数据持久化存储

    功能:
        - 指标数据存储和查询
        - 告警历史记录
        - 数据清理和归档

    使用示例:
        >>> storage = MetricsStorage("./runtime_data/monitor")
        >>> storage.save_metric(metric)
        >>> history = storage.get_metric_history(MetricType.CPU_USAGE, hours=24)
    """

    def __init__(self, storage_path: str = "./runtime_data/monitor"):
        """
        初始化存储管理器

        参数:
            storage_path: 存储目录路径
        """
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self.db_path = self.storage_path / "metrics.db"
        self._lock = threading.RLock()
        self._conn: Optional[sqlite3.Connection] = None
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        """获取数据库连接"""
        if self._conn is None:
            self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def close(self):
        """关闭数据库连接"""
        with self._lock:
            if self._conn:
                self._conn.close()
                self._conn = None
                logger.info("MetricsStorage 数据库连接已关闭")

    def _init_db(self):
        """初始化数据库表结构"""
        conn = self._get_connection()

        # 指标数据表
        conn.execute("""
            CREATE TABLE IF NOT EXISTS metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                metric_type TEXT NOT NULL,
                value REAL NOT NULL,
                unit TEXT,
                source TEXT,
                tags TEXT
            )
        """)

        # 告警记录表
        conn.execute("""
            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                alert_id TEXT UNIQUE NOT NULL,
                timestamp TEXT NOT NULL,
                metric_type TEXT NOT NULL,
                anomaly_type TEXT NOT NULL,
                severity TEXT NOT NULL,
                message TEXT NOT NULL,
                value REAL NOT NULL,
                expected_value REAL,
                deviation_percent REAL,
                tags TEXT,
                acknowledged INTEGER DEFAULT 0
            )
        """)

        # 创建索引
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_metrics_time
            ON metrics(timestamp)
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_metrics_type
            ON metrics(metric_type)
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_metrics_type_time
            ON metrics(metric_type, timestamp)
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_alerts_time
            ON alerts(timestamp)
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_alerts_type
            ON alerts(metric_type)
        """)

        conn.commit()
        logger.info(f"MetricsStorage 初始化完成: {self.db_path}")

    def save_metric(self, metric: MetricPoint) -> Dict[str, Any]:
        """
        保存指标数据

        参数:
            metric: 指标数据点

        返回:
            Dict: 操作结果
        """
        try:
            with self._lock:
                conn = self._get_connection()
                conn.execute(
                    """
                    INSERT INTO metrics (timestamp, metric_type, value, unit, source, tags)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        metric.timestamp.isoformat(),
                        metric.metric_type.value,
                        metric.value,
                        metric.unit,
                        metric.source,
                        json.dumps(metric.tags) if metric.tags else None
                    )
                )
                conn.commit()

            return create_success_response("指标已保存")

        except sqlite3.Error as e:
            logger.error(f"保存指标失败: {e}")
            return create_error_response(
                "保存指标失败",
                error_code=ErrorCode.STORAGE_ERROR,
                details={"error": str(e)}
            )

    def save_alert(self, alert: AnomalyAlert) -> Dict[str, Any]:
        """
        保存告警记录

        参数:
            alert: 异常告警

        返回:
            Dict: 操作结果
        """
        try:
            with self._lock:
                conn = self._get_connection()
                conn.execute(
                    """
                    INSERT OR REPLACE INTO alerts
                    (alert_id, timestamp, metric_type, anomaly_type, severity, message,
                     value, expected_value, deviation_percent, tags)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        alert.alert_id,
                        alert.timestamp.isoformat(),
                        alert.metric_type.value,
                        alert.anomaly_type.value,
                        alert.severity.value,
                        alert.message,
                        alert.current_value,
                        alert.expected_value,
                        alert.deviation_percent,
                        json.dumps(alert.tags) if alert.tags else None
                    )
                )
                conn.commit()

            return create_success_response("告警已保存")

        except sqlite3.Error as e:
            logger.error(f"保存告警失败: {e}")
            return create_error_response(
                "保存告警失败",
                error_code=ErrorCode.STORAGE_ERROR,
                details={"error": str(e)}
            )

    def get_metric_history(
        self,
        metric_type: MetricType,
        hours: int = 24,
        limit: int = 10000
    ) -> List[MetricPoint]:
        """
        获取指标历史数据

        参数:
            metric_type: 指标类型
            hours: 查询小时数
            limit: 最大返回数量

        返回:
            List[MetricPoint]: 指标数据点列表
        """
        try:
            since = (datetime.now() - timedelta(hours=hours)).isoformat()

            with self._lock:
                conn = self._get_connection()
                cursor = conn.execute(
                    """
                    SELECT timestamp, metric_type, value, unit, source, tags
                    FROM metrics
                    WHERE metric_type = ? AND timestamp > ?
                    ORDER BY timestamp DESC
                    LIMIT ?
                    """,
                    (metric_type.value, since, limit)
                )

                results = []
                for row in cursor.fetchall():
                    try:
                        point = MetricPoint(
                            timestamp=datetime.fromisoformat(row[0]),
                            metric_type=MetricType(row[1]),
                            value=row[2],
                            unit=row[3] or "",
                            source=row[4] or "",
                            tags=json.loads(row[5]) if row[5] else {}
                        )
                        results.append(point)
                    except (ValueError, json.JSONDecodeError) as e:
                        logger.warning(f"解析历史数据失败: {e}")
                        continue

                # 按时间正序返回
                return list(reversed(results))

        except sqlite3.Error as e:
            logger.error(f"查询历史数据失败: {e}")
            return []

    def query_metrics(
        self,
        metric_type: MetricType,
        start_time: datetime,
        end_time: datetime
    ) -> List[MetricPoint]:
        """
        按时间范围查询指标数据

        参数:
            metric_type: 指标类型
            start_time: 开始时间
            end_time: 结束时间

        返回:
            List[MetricPoint]: 指标数据点列表
        """
        try:
            with self._lock:
                conn = self._get_connection()
                cursor = conn.execute(
                    """
                    SELECT timestamp, metric_type, value, unit, source, tags
                    FROM metrics
                    WHERE metric_type = ? AND timestamp >= ? AND timestamp <= ?
                    ORDER BY timestamp ASC
                    """,
                    (metric_type.value, start_time.isoformat(), end_time.isoformat())
                )

                results = []
                for row in cursor.fetchall():
                    try:
                        point = MetricPoint(
                            timestamp=datetime.fromisoformat(row[0]),
                            metric_type=MetricType(row[1]),
                            value=row[2],
                            unit=row[3] or "",
                            source=row[4] or "",
                            tags=json.loads(row[5]) if row[5] else {}
                        )
                        results.append(point)
                    except (ValueError, json.JSONDecodeError) as e:
                        logger.warning(f"解析历史数据失败: {e}")
                        continue

                return results

        except sqlite3.Error as e:
            logger.error(f"查询指标数据失败: {e}")
            return []

    def get_earliest_metric(
        self,
        metric_type: MetricType
    ) -> Optional[MetricPoint]:
        """
        获取指定指标类型的最早记录

        参数:
            metric_type: 指标类型

        返回:
            Optional[MetricPoint]: 最早的指标数据点，如果没有则返回None
        """
        try:
            with self._lock:
                conn = self._get_connection()
                cursor = conn.execute(
                    """
                    SELECT timestamp, metric_type, value, unit, source, tags
                    FROM metrics
                    WHERE metric_type = ?
                    ORDER BY timestamp ASC
                    LIMIT 1
                    """,
                    (metric_type.value,)
                )

                row = cursor.fetchone()
                if row:
                    return MetricPoint(
                        timestamp=datetime.fromisoformat(row[0]),
                        metric_type=MetricType(row[1]),
                        value=row[2],
                        unit=row[3] or "",
                        source=row[4] or "",
                        tags=json.loads(row[5]) if row[5] else {}
                    )
                return None

        except sqlite3.Error as e:
            logger.error(f"获取最早指标记录失败: {e}")
            return None

    def get_alerts(
        self,
        hours: int = 24,
        acknowledged: Optional[bool] = None,
        severity: Optional[str] = None,
        limit: int = 1000
    ) -> List[Dict[str, Any]]:
        """
        获取告警历史

        参数:
            hours: 查询小时数
            acknowledged: 是否已确认
            severity: 严重级别过滤
            limit: 最大返回数量

        返回:
            List[Dict]: 告警列表
        """
        try:
            since = (datetime.now() - timedelta(hours=hours)).isoformat()

            query = "SELECT * FROM alerts WHERE timestamp > ?"
            params = [since]

            if acknowledged is not None:
                query += " AND acknowledged = ?"
                params.append(1 if acknowledged else 0)

            if severity:
                query += " AND severity = ?"
                params.append(severity)

            query += " ORDER BY timestamp DESC LIMIT ?"
            params.append(limit)

            with self._lock:
                conn = self._get_connection()
                cursor = conn.execute(query, params)

                columns = [description[0] for description in cursor.description]
                results = []

                for row in cursor.fetchall():
                    alert_dict = dict(zip(columns, row))
                    # 解析tags
                    if alert_dict.get("tags"):
                        try:
                            alert_dict["tags"] = json.loads(alert_dict["tags"])
                        except json.JSONDecodeError:
                            alert_dict["tags"] = {}
                    results.append(alert_dict)

                return results

        except sqlite3.Error as e:
            logger.error(f"查询告警失败: {e}")
            return []

    def acknowledge_alert(self, alert_id: str) -> Dict[str, Any]:
        """
        确认告警

        参数:
            alert_id: 告警ID

        返回:
            Dict: 操作结果
        """
        try:
            with self._lock:
                conn = self._get_connection()
                cursor = conn.execute(
                    "UPDATE alerts SET acknowledged = 1 WHERE alert_id = ?",
                    (alert_id,)
                )
                conn.commit()

                if cursor.rowcount > 0:
                    return create_success_response("告警已确认")
                else:
                    return create_error_response(
                        "告警不存在",
                        error_code=ErrorCode.NOT_FOUND
                    )

        except sqlite3.Error as e:
            logger.error(f"确认告警失败: {e}")
            return create_error_response(
                "确认告警失败",
                error_code=ErrorCode.STORAGE_ERROR,
                details={"error": str(e)}
            )

    def get_statistics(self) -> Dict[str, Any]:
        """
        获取存储统计信息

        返回:
            Dict: 统计信息
        """
        try:
            with self._lock:
                conn = self._get_connection()

                # 指标统计
                cursor = conn.execute("SELECT COUNT(*) FROM metrics")
                metric_count = cursor.fetchone()[0]

                # 告警统计
                cursor = conn.execute("SELECT COUNT(*) FROM alerts")
                alert_count = cursor.fetchone()[0]

                cursor = conn.execute(
                    "SELECT COUNT(*) FROM alerts WHERE acknowledged = 0"
                )
                unacknowledged_count = cursor.fetchone()[0]

                # 数据库文件大小
                db_size = self.db_path.stat().st_size if self.db_path.exists() else 0

                return {
                    "total_metrics": metric_count,
                    "total_alerts": alert_count,
                    "unacknowledged_alerts": unacknowledged_count,
                    "db_size_bytes": db_size,
                    "db_size_mb": round(db_size / (1024 * 1024), 2)
                }

        except sqlite3.Error as e:
            logger.error(f"获取统计信息失败: {e}")
            return {
                "total_metrics": 0,
                "total_alerts": 0,
                "unacknowledged_alerts": 0,
                "error": str(e)
            }

    def cleanup_old_data(self, days: int = 30) -> Dict[str, Any]:
        """
        清理过期数据

        参数:
            days: 保留天数

        返回:
            Dict: 清理结果
        """
        try:
            cutoff = (datetime.now() - timedelta(days=days)).isoformat()

            with self._lock:
                conn = self._get_connection()

                # 清理旧指标
                cursor = conn.execute(
                    "DELETE FROM metrics WHERE timestamp < ?",
                    (cutoff,)
                )
                metrics_deleted = cursor.rowcount

                # 清理旧告警
                cursor = conn.execute(
                    "DELETE FROM alerts WHERE timestamp < ? AND acknowledged = 1",
                    (cutoff,)
                )
                alerts_deleted = cursor.rowcount

                conn.commit()

                # 压缩数据库
                conn.execute("VACUUM")

            logger.info(f"数据清理完成: 删除{metrics_deleted}条指标, {alerts_deleted}条告警")

            return create_success_response(
                "数据清理完成",
                data={
                    "metrics_deleted": metrics_deleted,
                    "alerts_deleted": alerts_deleted,
                    "retention_days": days
                }
            )

        except sqlite3.Error as e:
            logger.error(f"清理数据失败: {e}")
            return create_error_response(
                "清理数据失败",
                error_code=ErrorCode.STORAGE_ERROR,
                details={"error": str(e)}
            )
