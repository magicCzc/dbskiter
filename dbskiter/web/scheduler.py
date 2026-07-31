"""
dbskiter/web/scheduler.py

定时任务引擎 — 基于 APScheduler 的后台任务调度

功能:
  - 创建/修改/删除定时任务
  - 任务执行和记录
  - 支持: 定时诊断、定时巡检、定时备份、定时报告
"""

import asyncio
import logging
from datetime import datetime
from typing import Optional, List, Dict

from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel

try:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from apscheduler.triggers.cron import CronTrigger
    from apscheduler.jobstores.memory import MemoryJobStore

    APSCHEDULER_AVAILABLE = True
except ImportError:
    APSCHEDULER_AVAILABLE = False

from .database import (
    get_session,
    ScheduledTask,
    session_scope,
    log_audit,
    save_metric,
    create_alert,
)
from .connector_helper import run_skill

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/tasks", tags=["tasks"])

# 全局调度器
scheduler = None
_job_id_counter = 0


# ── 任务类型定义 ──────────────────────────────────────

TASK_TYPES = {
    "diagnose": {
        "label": "定时诊断",
        "description": "定期执行数据库诊断，记录健康评分和问题",
        "default_cron": "0 9 * * *",  # 每天 9 点
    },
    "inspect": {
        "label": "定时巡检",
        "description": "定期执行综合巡检，生成巡检报告",
        "default_cron": "0 2 * * 0",  # 每周日 2 点
    },
    "report": {
        "label": "定时报告",
        "description": "定期生成健康报告",
        "default_cron": "0 10 1 * *",  # 每月 1 日 10 点
    },
    "collect": {
        "label": "指标采集",
        "description": "定期采集数据库指标",
        "default_cron": "*/5 * * * *",  # 每 5 分钟
    },
}


# ── 任务执行函数 ──────────────────────────────────────


def _extract_score(data: dict, key: str) -> float:
    """从结果数据中提取评分，兼容多种嵌套格式"""
    if not isinstance(data, dict):
        return 0.0
    for path in [(key,), ("raw_metrics", key), ("data", key), ("data", "raw_metrics", key)]:
        cur = data
        for p in path:
            if not isinstance(cur, dict) or p not in cur:
                cur = None
                break
            cur = cur[p]
        if cur is not None:
            try:
                return float(cur)
            except (TypeError, ValueError):
                return 0.0
    return 0.0


def execute_task(task_type: str, db_alias: str, task_id: str):
    """
    执行定时任务（进程内调用 skill，不再走 CLI 子进程）。

    APScheduler 在线程池中执行此函数，因此可以安全调用同步阻塞代码。
    """
    logger.info(f"执行任务 [{task_id}] {task_type} on {db_alias}")
    start = datetime.utcnow()

    if task_type == "diagnose":
        result = run_skill(db_alias, _skill_class_diagnose(), "realtime_diagnose", threshold=5)
        if result.get("success"):
            data = result.get("data", {})
            score = _extract_score(data, "score")
            save_metric(db_alias, "health_score", score)

    elif task_type == "inspect":
        result = run_skill(db_alias, _skill_class_inspector(), "inspect", inspection_types=None)
        if result.get("success"):
            data = result.get("data", {})
            score = _extract_score(data, "health_score")
            save_metric(db_alias, "inspect_score", score)

    elif task_type == "collect":
        from .collector import collect_metrics

        try:
            metrics = collect_metrics(db_alias)
            for metric, value in metrics.items():
                save_metric(db_alias, metric, value)
        except Exception as e:
            logger.error(f"采集失败: {e}")

    elapsed = (datetime.utcnow() - start).total_seconds()
    logger.info(f"任务完成 [{task_id}] {task_type} on {db_alias} ({elapsed:.1f}s)")


# ── 懒加载 Skill 类（避免循环依赖） ──────────────────────


_SKILL_CACHE: Dict[str, type] = {}


def _skill_class_diagnose():
    """懒加载 DiagnoseSkill"""
    if "diagnose" not in _SKILL_CACHE:
        from dbskiter.db_diagnose.skill import DiagnoseSkill
        _SKILL_CACHE["diagnose"] = DiagnoseSkill
    return _SKILL_CACHE["diagnose"]


def _skill_class_inspector():
    """懒加载 InspectorSkill"""
    if "inspector" not in _SKILL_CACHE:
        from dbskiter.db_inspector.skill import InspectorSkill
        _SKILL_CACHE["inspector"] = InspectorSkill
    return _SKILL_CACHE["inspector"]


# ── 调度器管理 ──────────────────────────────────────


def init_scheduler():
    """初始化调度器"""
    global scheduler
    if not APSCHEDULER_AVAILABLE:
        logger.warning("APScheduler 未安装，定时任务不可用")
        return

    scheduler = AsyncIOScheduler(jobstores={"default": MemoryJobStore()})
    scheduler.start()
    logger.info("定时任务调度器已启动")

    # 加载持久化的任务
    try:
        with session_scope() as session:
            tasks = session.query(ScheduledTask).filter(ScheduledTask.is_enabled.is_(True)).all()
            for task in tasks:
                _add_job_to_scheduler(task)
            logger.info(f"已加载 {len(tasks)} 个定时任务")
    except Exception as e:
        logger.warning(f"加载定时任务失败: {e}")


def _add_job_to_scheduler(task: ScheduledTask):
    """将任务添加到调度器"""
    if not scheduler:
        return
    try:
        trigger = CronTrigger.from_crontab(task.cron_expr)
        job_id = f"task_{task.id}"
        scheduler.add_job(
            execute_task,
            trigger=trigger,
            args=[task.task_type, task.db_alias, job_id],
            id=job_id,
            replace_existing=True,
            name=task.name,
        )
    except Exception as e:
        logger.warning(f"添加任务失败 [{task.name}]: {e}")


# ── API 端点 ──────────────────────────────────────


@router.get("", response_model=dict)
async def list_tasks():
    """列出所有定时任务"""
    with session_scope() as session:
        tasks = session.query(ScheduledTask).order_by(ScheduledTask.created_at.desc()).all()
    return {
        "success": True,
        "tasks": [
            {
                "id": t.id,
                "name": t.name,
                "task_type": t.task_type,
                "db_alias": t.db_alias,
                "cron_expr": t.cron_expr,
                "params": t.params,
                "is_enabled": t.is_enabled,
                "last_run": t.last_run.isoformat() if t.last_run else None,
                "next_run": _get_next_run(t.cron_expr) if t.is_enabled else None,
                "created_at": t.created_at.isoformat() if t.created_at else None,
            }
            for t in tasks
        ],
    }


@router.get("/types", response_model=dict)
async def list_task_types():
    """列出支持的任务类型"""
    return {"success": True, "types": TASK_TYPES}


@router.post("", response_model=dict)
async def create_task(config: dict):
    """创建定时任务"""
    name = config.get("name", "").strip()
    task_type = config.get("task_type", "")
    db_alias = config.get("db_alias", "")
    cron_expr = config.get("cron_expr", "")

    if not name or not task_type or not db_alias or not cron_expr:
        raise HTTPException(status_code=400, detail="name/task_type/db_alias/cron_expr 不能为空")
    if task_type not in TASK_TYPES:
        raise HTTPException(status_code=400, detail=f"不支持的任务类型: {task_type}")

    with session_scope() as session:
        task = ScheduledTask(
            name=name,
            task_type=task_type,
            db_alias=db_alias,
            cron_expr=cron_expr,
            params=config.get("params", {}),
            is_enabled=True,
        )
        session.add(task)
        session.flush()
        task_id = task.id

    # 添加到调度器
    if APSCHEDULER_AVAILABLE and scheduler:
        try:
            trigger = CronTrigger.from_crontab(cron_expr)
            scheduler.add_job(
                execute_task,
                trigger=trigger,
                args=[task_type, db_alias, f"task_{task_id}"],
                id=f"task_{task_id}",
                name=name,
            )
        except Exception as e:
            logger.warning(f"调度任务失败: {e}")

    log_audit(None, "system", "create", f"task:{name}", f"创建定时任务 {name}")
    return {"success": True, "id": task_id, "message": f"任务 '{name}' 已创建"}


@router.delete("/{task_id}", response_model=dict)
async def delete_task(task_id: int):
    """删除定时任务"""
    with session_scope() as session:
        task = session.query(ScheduledTask).filter(ScheduledTask.id == task_id).first()
        if not task:
            raise HTTPException(status_code=404, detail="任务不存在")
        name = task.name
        session.delete(task)

    if scheduler:
        scheduler.remove_job(f"task_{task_id}")

    log_audit(None, "system", "delete", f"task:{name}", f"删除定时任务 {name}")
    return {"success": True, "message": f"任务 '{name}' 已删除"}


@router.post("/{task_id}/toggle", response_model=dict)
async def toggle_task(task_id: int):
    """启用/禁用定时任务"""
    # 在 session 关闭前把需要的字段缓存到局部变量，避免 detached instance 错误
    task_name = ""
    task_cron = ""
    task_type = ""
    task_db_alias = ""
    new_state = False
    with session_scope() as session:
        task = session.query(ScheduledTask).filter(ScheduledTask.id == task_id).first()
        if not task:
            raise HTTPException(status_code=404, detail="任务不存在")
        task.is_enabled = not task.is_enabled
        new_state = task.is_enabled
        task_name = task.name
        task_cron = task.cron_expr
        task_type = task.task_type
        task_db_alias = task.db_alias

    if new_state and scheduler:
        # detached 状态：构造一个简化的 dict 替代 task 对象传给 add_job
        _add_job_to_dict(task_id, task_name, task_cron, task_type, task_db_alias)
    elif scheduler:
        scheduler.remove_job(f"task_{task_id}")

    status = "启用" if new_state else "禁用"
    log_audit(None, "system", "update", f"task:{task_name}", f"{status}定时任务")
    return {"success": True, "is_enabled": new_state, "message": f"任务已{status}"}


def _add_job_to_dict(task_id: int, name: str, cron_expr: str, task_type: str = "diagnose", db_alias: str = "default"):
    """将已 detached 的任务数据添加到调度器（避免 ORM detached instance 问题）"""
    if not scheduler:
        return
    try:
        trigger = CronTrigger.from_crontab(cron_expr)
        scheduler.add_job(
            execute_task,
            trigger=trigger,
            args=[task_type, db_alias, f"task_{task_id}"],
            id=f"task_{task_id}",
            replace_existing=True,
            name=name,
        )
    except Exception as e:
        logger.warning(f"添加任务失败 [{name}]: {e}")


def _get_next_run(cron_expr: str) -> Optional[str]:
    """获取下次运行时间"""
    try:
        trigger = CronTrigger.from_crontab(cron_expr)
        next_time = trigger.get_next_fire_time(None, datetime.utcnow())
        return next_time.isoformat() if next_time else None
    except Exception:
        return None
