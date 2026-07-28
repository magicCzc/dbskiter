"""
dbskiter/web/alerter.py

告警引擎 — 告警管理 API

功能:
  - 列出告警（按状态/级别/数据库筛选）
  - 确认告警
  - 告警统计
  - 历史告警查询
"""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel

from .database import (
    get_open_alerts,
    acknowledge_alert,
    session_scope,
    Alert,
    log_audit,
)

router = APIRouter(prefix="/api/alerts", tags=["alerts"])


class AlertResponse(BaseModel):
    id: int
    db_alias: str
    metric: str
    level: str
    current_value: float
    threshold: float
    message: str
    status: str
    created_at: str
    resolved_at: Optional[str] = None


@router.get("", response_model=dict)
async def list_alerts(
    db_alias: Optional[str] = Query(None, description="数据库别名"),
    status: str = Query("open", description="告警状态: open/acknowledged/resolved/all"),
    level: Optional[str] = Query(None, description="告警级别: info/warning/critical"),
    limit: int = Query(50, ge=1, le=200),
):
    """列出告警"""
    with session_scope() as session:
        query = session.query(Alert)
        if db_alias:
            query = query.filter(Alert.db_alias == db_alias)
        if status != "all":
            query = query.filter(Alert.status == status)
        if level:
            query = query.filter(Alert.level == level)
        alerts = query.order_by(Alert.created_at.desc()).limit(limit).all()

    return {
        "success": True,
        "total": len(alerts),
        "alerts": [
            {
                "id": a.id,
                "db_alias": a.db_alias,
                "metric": a.metric,
                "level": a.level,
                "current_value": a.current_value,
                "threshold": a.threshold,
                "message": a.message,
                "status": a.status,
                "created_at": a.created_at.isoformat(),
                "resolved_at": a.resolved_at.isoformat() if a.resolved_at else None,
            }
            for a in alerts
        ],
    }


@router.get("/stats", response_model=dict)
async def get_alert_stats():
    """告警统计"""
    with session_scope() as session:
        total = session.query(Alert).count()
        open_count = session.query(Alert).filter(Alert.status == "open").count()
        critical = session.query(Alert).filter(Alert.level == "critical", Alert.status == "open").count()
        warning = session.query(Alert).filter(Alert.level == "warning", Alert.status == "open").count()

    return {
        "success": True,
        "stats": {
            "total": total,
            "open": open_count,
            "critical": critical,
            "warning": warning,
        },
    }


@router.post("/{alert_id}/acknowledge", response_model=dict)
async def ack_alert(alert_id: int):
    """确认告警"""
    if acknowledge_alert(alert_id):
        log_audit(None, "system", "update", f"alert:{alert_id}", "确认告警")
        return {"success": True, "message": "告警已确认"}
    raise HTTPException(status_code=404, detail="告警不存在或已处理")


@router.post("/{alert_id}/resolve", response_model=dict)
async def resolve_alert(alert_id: int):
    """解决告警"""
    with session_scope() as session:
        alert = session.query(Alert).filter(Alert.id == alert_id).first()
        if not alert:
            raise HTTPException(status_code=404, detail="告警不存在")
        alert.status = "resolved"
        alert.resolved_at = datetime.utcnow()
        log_audit(None, "system", "update", f"alert:{alert_id}", "解决告警")
        return {"success": True, "message": "告警已解决"}


@router.post("/resolve-all", response_model=dict)
async def resolve_all_alerts():
    """解决所有未关闭告警"""
    with session_scope() as session:
        count = (
            session.query(Alert)
            .filter(Alert.status.in_(["open", "acknowledged"]))
            .update({"status": "resolved", "resolved_at": datetime.utcnow()})
        )
        log_audit(None, "system", "update", "alerts", f"批量解决 {count} 个告警")
        return {"success": True, "resolved_count": count}


@router.get("/history", response_model=dict)
async def get_alert_history(
    db_alias: Optional[str] = Query(None),
    hours: int = Query(24, ge=1, le=720),
    limit: int = Query(100, ge=1, le=500),
):
    """告警历史"""
    from datetime import timedelta

    since = datetime.utcnow() - timedelta(hours=hours)

    with session_scope() as session:
        query = session.query(Alert).filter(Alert.created_at >= since)
        if db_alias:
            query = query.filter(Alert.db_alias == db_alias)
        alerts = query.order_by(Alert.created_at.desc()).limit(limit).all()

    return {
        "success": True,
        "total": len(alerts),
        "alerts": [
            {
                "id": a.id,
                "db_alias": a.db_alias,
                "metric": a.metric,
                "level": a.level,
                "current_value": a.current_value,
                "threshold": a.threshold,
                "message": a.message,
                "status": a.status,
                "created_at": a.created_at.isoformat(),
            }
            for a in alerts
        ],
    }
