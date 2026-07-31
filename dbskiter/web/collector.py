"""
dbskiter/web/collector.py

指标采集器 — 定时采集数据库指标并存储到 SQLite

采集指标:
  - cpu: CPU 使用率
  - memory: 内存使用率
  - disk: 磁盘使用率
  - qps: 每秒查询数
  - connections: 活跃连接数
  - slow_queries: 慢查询数

运行方式:
  - 作为 FastAPI 后台任务运行
  - 每 5 分钟采集一次

优化: 直接调用 skill 类，不再通过 subprocess 调用 CLI
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict

from .database import (
    save_metric,
    get_all_db_configs,
    get_open_alerts,
    create_alert,
    cleanup_old_metrics,
)
from .connector_helper import get_connector, run_skill

logger = logging.getLogger(__name__)

# 采集间隔（秒）
COLLECT_INTERVAL = 300  # 5 分钟

# 采集指标列表
METRICS = ["cpu", "memory", "disk", "qps", "connections"]


def _collect_metrics_skill(db_alias: str, skill_cls, method: str, *args, **kwargs) -> Optional[dict]:
    """使用 skill 类采集指标（进程内调用）"""
    connector = get_connector(db_alias)
    if not connector:
        return None
    skill = None
    try:
        skill = skill_cls(connector)
        result = getattr(skill, method)(*args, **kwargs)
        if isinstance(result, dict):
            return result.get("data", result)
        return result
    except Exception as e:
        logger.warning(f"采集失败 [{db_alias}.{method}]: {e}")
        return None
    finally:
        try:
            if skill and hasattr(skill, "close"):
                skill.close()
        except Exception:
            pass
        try:
            connector.close()
        except Exception:
            pass


def collect_metrics(db_alias: str) -> Dict[str, float]:
    """采集单个数据库的指标（进程内调用 skill 类）"""
    from dbskiter.db_monitor.skill import MonitorSkill
    from dbskiter.db_diagnose.skill import DiagnoseSkill

    results: Dict[str, float] = {}

    # 1. 采集健康指标（CPU/Memory/Disk）
    health_data = _collect_metrics_skill(db_alias, MonitorSkill, "assess_health")
    if health_data:
        # 从 metrics_summary 提取
        ms = health_data.get("metrics_summary", {})
        if isinstance(ms, dict):
            for key in ["cpu", "memory", "disk"]:
                val = ms.get(key, ms.get(f"{key}_usage"))
                if val is not None:
                    try:
                        results[key] = float(val)
                    except (ValueError, TypeError):
                        pass

    # 2. 采集 QPS
    collect_data = _collect_metrics_skill(db_alias, MonitorSkill, "collect_metrics")
    if collect_data:
        metrics = collect_data.get("metrics_summary", collect_data.get("metrics", {}))
        if isinstance(metrics, dict):
            qps = metrics.get("qps", 0)
            try:
                results["qps"] = float(qps)
            except (ValueError, TypeError):
                pass

    # 3. 采集连接数
    conn_data = _collect_metrics_skill(db_alias, DiagnoseSkill, "analyze_connections")
    if conn_data:
        connections = conn_data.get("connections", [])
        max_conn = conn_data.get("max_connections", 151)
        if connections:
            try:
                results["connections"] = float(len(connections))
            except (ValueError, TypeError):
                pass

    # 4. 采集慢查询数
    slow_data = _collect_metrics_skill(db_alias, DiagnoseSkill, "analyze_slow_queries", limit=1, since="1h")
    if slow_data:
        # 尝试从不同字段提取总数
        total = slow_data.get("total_queries", slow_data.get("total", 0))
        if not total and isinstance(slow_data, dict):
            total = slow_data.get("summary", {}).get("total_queries", 0)
        try:
            results["slow_queries"] = float(total)
        except (ValueError, TypeError):
            pass

    return results


async def collect_all():
    """采集所有数据库的指标"""
    configs = get_all_db_configs()
    for alias in configs:
        try:
            metrics = await asyncio.to_thread(collect_metrics, alias)
            for metric, value in metrics.items():
                save_metric(alias, metric, value)
                _check_alert(alias, metric, value)
            if metrics:
                logger.info(f"采集完成 [{alias}]: {len(metrics)} 个指标")
        except Exception as e:
            logger.warning(f"采集异常 [{alias}]: {e}")


def _check_alert(db_alias: str, metric: str, value: float):
    """检查指标是否触发告警阈值"""
    thresholds = {
        "cpu": (90, "critical"),
        "memory": (90, "critical"),
        "disk": (85, "warning"),
        "connections": (80, "warning"),
        "slow_queries": (50, "warning"),
        "qps": (10000, "info"),
    }

    if metric not in thresholds:
        return

    threshold, level = thresholds[metric]
    if metric in ("cpu", "memory", "disk"):
        if value >= threshold:
            existing = get_open_alerts(db_alias)
            for alert in existing:
                if alert.metric == metric and alert.status == "open":
                    return
            create_alert(
                db_alias=db_alias,
                metric=metric,
                level=level,
                current_value=value,
                threshold=float(threshold),
                message=f"{metric} 使用率 {value:.1f}%，超过阈值 {threshold}%",
            )
            logger.warning(f"告警触发 [{db_alias}] {metric}: {value:.1f}% > {threshold}%")


# ── 后台任务 ──────────────────────────────────────────────


class MetricsCollector:
    """指标采集器后台任务"""

    def __init__(self):
        self._task: Optional[asyncio.Task] = None
        self._running = False

    async def start(self):
        """启动采集任务"""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info(f"指标采集器已启动 (间隔: {COLLECT_INTERVAL}s)")

    async def stop(self):
        """停止采集任务"""
        self._running = False
        if self._task:
            self._task.cancel()
            self._task = None
        logger.info("指标采集器已停止")

    async def _run_loop(self):
        """采集循环"""
        cleanup_counter = 0
        while self._running:
            try:
                await collect_all()
                # 每 24 次采集（约 2 小时）清理一次旧数据
                cleanup_counter += 1
                if cleanup_counter >= 24:
                    try:
                        await asyncio.to_thread(cleanup_old_metrics, 30)
                    except Exception as e:
                        logger.warning(f"清理旧指标数据失败: {e}")
                    cleanup_counter = 0
            except Exception as e:
                logger.error(f"采集循环异常: {e}")
            await asyncio.sleep(COLLECT_INTERVAL)

    @property
    def is_running(self) -> bool:
        return self._running


# 全局采集器实例
collector = MetricsCollector()
