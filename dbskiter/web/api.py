"""
dbskiter/web/api.py

Web API 端点 - 16 个核心数据库运维能力

每个端点直接调用 dbskiter 技能类（进程内），
不再通过 subprocess 调用 CLI。
"""

import asyncio
import logging
from typing import Optional, List
from pathlib import Path

from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel, Field

from .connector_helper import get_connector, test_connection

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["dbskiter"])


# ── Pydantic 模型 ──────────────────────────────────────────────────


class HealthResponse(BaseModel):
    """健康检查响应"""

    status: str = Field(..., description="HEALTHY/WARNING/CRITICAL")
    score: float = Field(..., description="健康评分 0-100")
    issues: List[str] = Field(default_factory=list)
    collected_at: str = ""


class SlowQuery(BaseModel):
    """慢查询项"""

    sql: str = ""
    execution_time: float = 0.0
    execution_count: int = 0
    avg_time: float = 0.0
    rows_examined: int = 0


class SlowQueryResponse(BaseModel):
    """慢查询响应"""

    total: int = 0
    queries: List[SlowQuery] = Field(default_factory=list)


class SecurityResponse(BaseModel):
    """安全审计响应"""

    total_risks: int = 0
    critical_count: int = 0
    high_count: int = 0
    risks: List[dict] = Field(default_factory=list)


class BackupResponse(BaseModel):
    """备份响应"""

    success: bool = False
    backup_id: str = ""
    file_path: str = ""
    file_size: int = 0
    error: Optional[str] = None


class TaskResponse(BaseModel):
    """任务列表响应"""

    tasks: List[dict] = Field(default_factory=list)


class ErrorResponse(BaseModel):
    """错误响应"""

    error: str = ""
    detail: str = ""


# ── 辅助函数 ───────────────────────────────────────────────────────


def _execute_skill(alias: str, skill_cls, method: str, *args, **kwargs):
    """
    在事件循环中安全执行 skill 方法

    返回: (success, data, error)
    """
    connector = get_connector(alias)
    if not connector:
        return False, None, f"数据库 '{alias}' 未配置"
    skill = None
    try:
        skill = skill_cls(connector)
        result = getattr(skill, method)(*args, **kwargs)
        # 提取标准响应格式中的数据
        if isinstance(result, dict):
            if result.get("success") is False:
                return False, result, result.get("error", "未知错误")
            data = result.get("data", result)
            return True, data, None
        return True, result, None
    except Exception as e:
        logger.error(f"Skill 执行失败 [{alias}.{method}]: {e}")
        return False, None, str(e)
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


def _extract_health_data(health_data: dict) -> dict:
    """从健康评估结果中提取标准字段"""
    if not health_data:
        return {"status": "UNKNOWN", "score": 0, "issues": [], "collected_at": ""}
    # HealthAssessment.to_dict() 格式
    status = health_data.get("status", "UNKNOWN")
    if hasattr(status, "value"):
        status = status.value
    return {
        "status": status,
        "score": health_data.get("score", 0),
        "issues": health_data.get("issues", []) or [],
        "collected_at": health_data.get("timestamp", health_data.get("assessed_at", "")),
    }


def _extract_slow_queries(data: dict, top: int) -> list:
    """从慢查询分析结果中提取查询列表"""
    # 可能的数据位置
    queries = []
    for key in ["top_patterns", "slow_queries", "queries"]:
        candidates = data.get(key, [])
        if candidates:
            queries = candidates
            break
    # 如果 data 本身是列表
    if not queries and isinstance(data, list):
        queries = data
    mapped = []
    for q in queries[:top]:
        if isinstance(q, dict):
            mapped.append(
                {
                    "sql": q.get("sql", q.get("sql_short", q.get("pattern", ""))),
                    "execution_time": q.get("execution_time", q.get("query_time", q.get("max_time", 0))),
                    "execution_count": q.get("execution_count", q.get("count", 1)),
                    "avg_time": q.get("avg_time", q.get("avg", q.get("query_time", 0))),
                    "rows_examined": q.get("rows_examined", q.get("rows_sent", q.get("rows", 0))),
                }
            )
    return mapped


def _extract_security_risks(data: dict) -> dict:
    """从安全审计结果中提取风险数据"""
    risk_summary = data.get("risk_summary", {})
    if isinstance(risk_summary, dict):
        total_risks = risk_summary.get("total", 0)
        critical_count = risk_summary.get("critical", 0)
        high_count = risk_summary.get("high", 0)
    else:
        total_risks = 0
        critical_count = 0
        high_count = 0

    modules = data.get("modules", {})
    risks = []
    if isinstance(modules, dict):
        for module_name, module_data in modules.items():
            if isinstance(module_data, dict):
                risks_data = (
                    module_data.get("risks")
                    or module_data.get("findings")
                    or module_data.get("data", {}).get("risks")
                    or module_data.get("data", {}).get("findings")
                    or []
                )
                if isinstance(risks_data, list):
                    for r in risks_data:
                        if isinstance(r, dict):
                            r["module"] = module_name
                            r.setdefault("description", r.get("message", r.get("name", "")))
                            r.setdefault("severity", r.get("level", r.get("risk_level", "medium")))
                            r.setdefault("category", module_name)
                            r.setdefault("current_value", r.get("current", r.get("value", "")))
                            r.setdefault("recommended_value", r.get("recommended", r.get("suggestion", "")))
                            risks.append(r)

    return {
        "total_risks": total_risks,
        "critical_count": critical_count,
        "high_count": high_count,
        "risks": risks[:50],
    }


# ── API 端点 ───────────────────────────────────────────────────────


@router.get("/health", response_model=HealthResponse)
async def get_health(
    database: str = Query("default", description="数据库别名或连接串"),
):
    """数据库健康检查"""
    from dbskiter.db_monitor.skill import MonitorSkill

    success, data, error = _execute_skill(database, MonitorSkill, "assess_health")
    if not success:
        raise HTTPException(status_code=502, detail=error or "健康检查失败")

    health = _extract_health_data(data or {})
    return HealthResponse(
        status=health["status"],
        score=health["score"],
        issues=health["issues"],
        collected_at=health["collected_at"],
    )


@router.get("/health/all", response_model=dict)
async def get_all_health():
    """所有数据库健康状态概览"""
    from .database import get_all_db_configs
    from dbskiter.db_monitor.skill import MonitorSkill

    configs = get_all_db_configs()
    aliases = list(configs.keys()) if configs else ["default"]

    async def _check(alias: str):
        try:
            success, data, error = _execute_skill(alias, MonitorSkill, "assess_health")
            if success:
                h = _extract_health_data(data or {})
                return {"name": alias, "status": h["status"], "score": h["score"], "issues": h["issues"]}
            return {"name": alias, "status": "ERROR", "score": 0, "error": error or "未知错误"}
        except Exception as e:
            return {"name": alias, "status": "ERROR", "score": 0, "error": str(e)}

    results = await asyncio.gather(*[_check(a) for a in aliases], return_exceptions=True)
    databases = []
    for i, alias in enumerate(aliases):
        r = results[i]
        if isinstance(r, Exception):
            databases.append({"name": alias, "status": "ERROR", "score": 0, "error": str(r)})
        else:
            databases.append(r)

    return {"databases": databases}


@router.get("/slow-queries", response_model=SlowQueryResponse)
async def get_slow_queries(
    database: str = Query("default"),
    top: int = Query(10, ge=1, le=100),
    hours: int = Query(1, ge=1, le=168),
    database_name: Optional[str] = Query(None, alias="database"),
):
    """慢查询分析"""
    from dbskiter.db_diagnose.skill import DiagnoseSkill

    db = database_name or database
    success, data, error = _execute_skill(
        db,
        DiagnoseSkill,
        "analyze_slow_queries",
        limit=top,
        since=f"{hours}h",
    )
    if not success:
        raise HTTPException(status_code=502, detail=error or "慢查询分析失败")

    queries = _extract_slow_queries(data or {}, top)
    return SlowQueryResponse(total=len(queries), queries=[SlowQuery(**q) for q in queries])


@router.get("/security", response_model=SecurityResponse)
async def run_security_audit(
    database: str = Query("default", description="数据库别名"),
):
    """安全审计"""
    from dbskiter.db_security.skill import SecuritySkill

    success, data, error = _execute_skill(database, SecuritySkill, "full_audit")
    if not success:
        raise HTTPException(status_code=502, detail=error or "安全审计失败")

    risks = _extract_security_risks(data or {})
    return SecurityResponse(
        total_risks=risks["total_risks"],
        critical_count=risks["critical_count"],
        high_count=risks["high_count"],
        risks=risks["risks"],
    )


@router.get("/diagnose/realtime", response_model=dict)
async def get_realtime_diagnose(
    database: str = Query("default", description="数据库别名"),
):
    """实时诊断"""
    from dbskiter.db_diagnose.skill import DiagnoseSkill

    success, data, error = _execute_skill(database, DiagnoseSkill, "realtime_diagnose", threshold=5)
    if not success:
        raise HTTPException(status_code=502, detail=error or "实时诊断失败")

    data = data or {}
    issues = data.get("issues", data.get("raw_metrics", {}).get("issues", []))
    critical = sum(1 for i in issues if isinstance(i, dict) and i.get("severity") == "critical")
    high = sum(1 for i in issues if isinstance(i, dict) and i.get("severity") == "high")
    score = data.get("score", max(0, 100 - critical * 20 - high * 10 - len(issues) * 2))

    status = "HEALTHY"
    if critical > 0 or score < 60:
        status = "CRITICAL"
    elif high > 0 or score < 80:
        status = "WARNING"

    return {
        "success": True,
        "database": database,
        "score": score,
        "status": status,
        "issues": issues,
        "ai_hints": data.get("ai_hints", {}),
        "raw_data": data,
    }


@router.get("/diagnose/top", response_model=dict)
async def get_top_sql(
    database: str = Query("default"),
    limit: int = Query(10, ge=1, le=100),
):
    """TOP SQL 分析"""
    from dbskiter.db_diagnose.skill import DiagnoseSkill

    success, data, error = _execute_skill(database, DiagnoseSkill, "get_top_sql", limit=limit)
    if not success:
        raise HTTPException(status_code=502, detail=error or "TOP SQL 分析失败")

    return {"success": True, "data": data}


@router.get("/diagnose/locks", response_model=dict)
async def get_locks(
    database: str = Query("default"),
):
    """锁分析"""
    from dbskiter.db_diagnose.skill import DiagnoseSkill

    success, data, error = _execute_skill(database, DiagnoseSkill, "analyze_locks")
    if not success:
        if error and "PROCESS" in error:
            return {
                "success": False,
                "error": "数据库用户缺少 PROCESS 权限，无法查询锁信息",
                "solution": "GRANT PROCESS ON *.* TO 'your_user'@'%'; FLUSH PRIVILEGES;",
                "data": {"locks": [], "deadlocks": []},
            }
        return {"success": False, "error": error or "锁分析失败", "data": {"locks": [], "deadlocks": []}}

    return {"success": True, "data": data or {"locks": [], "deadlocks": []}}


@router.get("/diagnose/space", response_model=dict)
async def get_space(
    database: str = Query("default"),
    top: int = Query(20, ge=1, le=100),
):
    """空间诊断"""
    from dbskiter.db_diagnose.skill import DiagnoseSkill

    success, data, error = _execute_skill(database, DiagnoseSkill, "analyze_space", top_n=top)
    if not success:
        raise HTTPException(status_code=502, detail=error or "空间分析失败")

    data = data or {}
    ts = data.get("total_space", {})
    tables = data.get("large_tables", [])
    return {
        "success": True,
        "data": {
            "raw_metrics": {
                "total_space": ts.get("total_gb", ts.get("size_gb", 0)),
                "tables": tables[:top],
                "table_count": len(tables),
            }
        },
    }


@router.get("/diagnose/connections", response_model=dict)
async def get_connections(
    database: str = Query("default"),
):
    """连接分析"""
    from dbskiter.db_diagnose.skill import DiagnoseSkill

    success, data, error = _execute_skill(database, DiagnoseSkill, "analyze_connections")
    if not success:
        # 回退到 get_top_sql
        success2, data2, _ = _execute_skill(database, DiagnoseSkill, "get_top_sql", limit=50)
        if success2:
            raw = data2 or {}
            queries = raw.get("top_queries", [])
            mapped = []
            for c in queries[:100]:
                mapped.append(
                    {
                        "pid": c.get("id", c.get("pid", 0)),
                        "user": c.get("user", "?"),
                        "host": c.get("host", ""),
                        "database": c.get("db", c.get("database", "")),
                        "state": c.get("command", c.get("state", "Sleep")),
                        "query": c.get("sql", c.get("query", "")),
                        "duration": c.get("exec_time", c.get("duration", 0)),
                    }
                )
            return {"success": True, "data": {"raw_metrics": {"connections": mapped, "max_connections": 151}}}
        raise HTTPException(status_code=502, detail=error or "连接分析失败")

    data = data or {}
    connections = data.get("connections", [])
    mapped = []
    for c in connections[:100]:
        if isinstance(c, dict):
            mapped.append(
                {
                    "pid": c.get("id", c.get("pid", 0)),
                    "user": c.get("user", "?"),
                    "host": c.get("host", ""),
                    "database": c.get("db", c.get("database", "")),
                    "state": c.get("command", c.get("state", "Sleep")),
                    "query": c.get("sql", c.get("query", "")),
                    "duration": c.get("exec_time", c.get("duration", 0)),
                }
            )
    return {
        "success": True,
        "data": {"raw_metrics": {"connections": mapped, "max_connections": data.get("max_connections", 151)}},
    }


@router.get("/inspector/report", response_model=dict)
async def generate_inspector_report(
    database: str = Query("default", description="数据库别名"),
    report_type: str = Query(
        "performance", description="巡检类型: configuration/performance/storage/security/capacity/replication"
    ),
):
    """巡检报告"""
    from dbskiter.db_inspector.skill import InspectorSkill
    from dbskiter.db_inspector.models import InspectionType

    type_map = {
        "configuration": InspectionType.CONFIGURATION,
        "performance": InspectionType.PERFORMANCE,
        "storage": InspectionType.STORAGE,
        "security": InspectionType.SECURITY,
        "capacity": InspectionType.CAPACITY,
        "replication": InspectionType.REPLICATION,
        "backup": InspectionType.BACKUP,
        "full": None,
    }
    itype = type_map.get(report_type)
    inspect_types = [itype] if itype else None

    success, data, error = _execute_skill(database, InspectorSkill, "inspect", inspection_types=inspect_types)
    if not success:
        raise HTTPException(status_code=502, detail=error or "巡检失败")

    return {"success": True, "data": data}


@router.post("/backup", response_model=BackupResponse)
async def create_backup(
    database: str = Query("default", description="数据库别名"),
    backup_type: str = Query("full", description="备份类型: full/incremental/table"),
    tables: Optional[str] = Query(None, description="表级备份时指定表名，逗号分隔"),
):
    """创建备份"""
    from dbskiter.db_scheduler.skill import SchedulerSkill

    table_list = tables.split(",") if tables else None
    success, data, error = _execute_skill(
        database,
        SchedulerSkill,
        "backup",
        backup_type=backup_type,
        tables=table_list,
    )
    if not success:
        raise HTTPException(status_code=502, detail=error or "备份失败")

    data = data or {}
    return BackupResponse(
        success=data.get("success", False),
        backup_id=data.get("backup_id", ""),
        file_path=data.get("file_path", ""),
        file_size=data.get("file_size", 0),
        error=data.get("error"),
    )


@router.get("/backups", response_model=dict)
async def list_backups(
    database: str = Query("default", description="数据库别名"),
):
    """备份列表"""
    from dbskiter.db_scheduler.skill import SchedulerSkill

    success, data, error = _execute_skill(database, SchedulerSkill, "list_backups")
    if not success:
        raise HTTPException(status_code=502, detail=error or "获取备份列表失败")

    return {"success": True, "data": data, "backups": data if isinstance(data, list) else []}


@router.get("/tasks", response_model=dict)
async def list_tasks(
    database: str = Query("default", description="数据库别名"),
):
    """定时任务列表"""
    from dbskiter.db_scheduler.skill import SchedulerSkill

    success, data, error = _execute_skill(database, SchedulerSkill, "list_tasks")
    if not success:
        raise HTTPException(status_code=502, detail=error or "获取任务列表失败")

    return {"success": True, "tasks": data if isinstance(data, list) else []}


@router.get("/logs", response_model=dict)
async def get_recent_logs(
    database: str = Query("default", description="数据库别名"),
    hours: int = Query(24, ge=1, le=720),
):
    """最近操作日志"""
    from dbskiter.shared.history_manager import HistoryManager

    history = HistoryManager()
    limit = min(hours * 2, 200)
    try:
        records = history.list(limit=limit)
        return {"success": True, "logs": records}
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/databases", response_model=dict)
async def list_databases():
    """可用数据库列表"""
    from .database import get_all_db_configs

    configs = get_all_db_configs()
    databases = sorted(configs.keys())

    # 补充 .env 中的配置
    import re

    env_path = Path.cwd() / ".env"
    if env_path.exists():
        content = env_path.read_text(encoding="utf-8", errors="replace")
        for match in re.finditer(r"^DB_([A-Z0-9_]+)_HOST\s*=", content, re.MULTILINE):
            alias = match.group(1).lower()
            if alias not in databases:
                databases.append(alias)
        if re.search(r"^DB_HOST\s*=", content, re.MULTILINE) and "default" not in databases:
            databases.append("default")

    if not databases:
        databases = ["default"]

    return {"databases": sorted(databases)}


@router.get("/diagnose/connection", response_model=dict)
async def test_connection(
    database: str = Query("default", description="数据库别名"),
):
    """测试数据库连接（仅执行 SELECT 1，无需特殊权限）"""
    result = test_connection(database)
    return {
        "success": result["success"],
        "database": database,
        "message": result["message"],
    }


@router.get("/monitor/anomalies", response_model=dict)
async def get_anomalies(
    database: str = Query("default"),
    hours: int = Query(6, ge=1, le=168),
):
    """异常检测"""
    from dbskiter.db_monitor.skill import MonitorSkill

    success, data, error = _execute_skill(database, MonitorSkill, "detect_anomalies")
    if not success:
        raise HTTPException(status_code=502, detail=error or "异常检测失败")

    return {"success": True, "data": data}


@router.get("/monitor/capacity", response_model=dict)
async def get_capacity(
    database: str = Query("default"),
    resource: str = Query("disk", description="资源类型: disk/memory/connections"),
):
    """容量预测"""
    from dbskiter.db_monitor.skill import MonitorSkill

    success, data, error = _execute_skill(database, MonitorSkill, "predict_capacity", resource=resource)
    if not success:
        raise HTTPException(status_code=502, detail=error or "容量预测失败")

    return {"success": True, "data": data}


@router.get("/monitor/trends", response_model=dict)
async def get_trends(
    database: str = Query("default"),
    hours: int = Query(24, ge=1, le=168),
):
    """资源趋势数据"""
    from dbskiter.db_monitor.skill import MonitorSkill

    success, data, error = _execute_skill(database, MonitorSkill, "collect_metrics")
    if not success:
        return {"timestamps": [], "cpu": [], "memory": [], "disk": [], "qps": []}

    data = data or {}
    metrics = data.get("metrics_summary", data.get("metrics", data.get("raw_metrics", {})))
    if isinstance(metrics, dict):
        return {
            "timestamps": [data.get("timestamp", "")],
            "cpu": [metrics.get("cpu", metrics.get("cpu_usage", 0))],
            "memory": [metrics.get("memory", metrics.get("memory_usage", 0))],
            "disk": [metrics.get("disk", metrics.get("disk_usage", 0))],
            "qps": [metrics.get("qps", 0)],
        }
    return {"timestamps": [], "cpu": [], "memory": [], "disk": [], "qps": []}


@router.get("/sql/schema", response_model=dict)
async def get_schema(
    database: str = Query("default"),
    table: str = Query(None, description="表名（可选）"),
):
    """获取数据库 Schema 信息"""
    from dbskiter.sql_master.skill import SQLMasterSkill

    if table:
        success, data, error = _execute_skill(database, SQLMasterSkill, "get_schema_info", table_name=table)
        if not success:
            raise HTTPException(status_code=502, detail=error or "获取 Schema 失败")
        return {"success": True, "data": data}
    else:
        success, data, error = _execute_skill(database, SQLMasterSkill, "list_tables")
        if not success:
            raise HTTPException(status_code=502, detail=error or "获取表列表失败")
        return {"success": True, "tables": data if isinstance(data, list) else []}


@router.post("/sql/execute", response_model=dict)
async def execute_sql(
    database: str = Query("default"),
    sql: str = Query(..., description="SQL 语句"),
    limit: int = Query(100, ge=1, le=10000, description="返回行数上限"),
    read_only: bool = Query(True, description="是否只读模式"),
):
    """执行 SQL 查询（默认只读模式，写操作需显式关闭 read_only）"""
    from dbskiter.sql_master.skill import SQLMasterSkill

    success, data, error = _execute_skill(
        database,
        SQLMasterSkill,
        "execute",
        sql=sql,
        limit=limit,
        allow_write=not read_only,
    )
    if not success:
        return {"success": False, "error": error or "SQL 执行失败"}

    data = data or {}
    return {
        "success": True,
        "data": data,
        "execution_time": data.get("execution_time", 0),
        "row_count": data.get("row_count", 0),
        "columns": data.get("columns", []),
        "rows": data.get("rows", []),
    }


# ── 数据库配置管理 ─────────────────────────────────────────────

from .database import (
    get_all_db_configs,
    save_db_config,
    delete_db_config as db_delete_config,
    log_audit,
)


@router.get("/config/databases", response_model=dict)
async def list_db_configs():
    """列出所有已配置的数据库"""
    configs = get_all_db_configs()
    return {"success": True, "databases": configs, "count": len(configs)}


@router.post("/config/databases", response_model=dict)
async def add_db_config(config: dict):
    """新增数据库配置"""
    alias = config.get("alias", "").strip().lower()
    if not alias:
        raise HTTPException(status_code=400, detail="alias 不能为空")

    existing = get_all_db_configs()
    if alias in existing:
        raise HTTPException(status_code=409, detail=f"数据库 '{alias}' 已存在")

    config["alias"] = alias
    config.setdefault("host", "127.0.0.1")
    config.setdefault("port", 3306)
    config.setdefault("user", "root")
    config.setdefault("password", "")
    config.setdefault("database", "")
    config.setdefault("dialect", "mysql+pymysql")
    config.setdefault("pool_size", 5)

    if save_db_config(config):
        log_audit(None, "system", "create", f"database:{alias}", f"新增数据库 {alias}")
        # 保存后立即测试连接
        conn_result = test_connection(alias)
        return {"success": True, "alias": alias, "message": f"数据库 '{alias}' 已添加", "connection": conn_result}
    raise HTTPException(status_code=500, detail="保存配置失败")


@router.put("/config/databases/{alias}", response_model=dict)
async def update_db_config(alias: str, config: dict):
    """修改数据库配置"""
    existing = get_all_db_configs()
    if alias not in existing:
        raise HTTPException(status_code=404, detail=f"数据库 '{alias}' 不存在")

    config["alias"] = alias
    if save_db_config(config):
        log_audit(None, "system", "update", f"database:{alias}", f"修改数据库 {alias}")
        return {"success": True, "alias": alias, "message": f"数据库 '{alias}' 已更新"}
    raise HTTPException(status_code=500, detail="保存配置失败")


@router.delete("/config/databases/{alias}", response_model=dict)
async def delete_db_config(alias: str):
    """删除数据库配置"""
    existing = get_all_db_configs()
    if alias not in existing:
        raise HTTPException(status_code=404, detail=f"数据库 '{alias}' 不存在")

    if db_delete_config(alias):
        log_audit(None, "system", "delete", f"database:{alias}", f"删除数据库 {alias}")
        return {"success": True, "alias": alias, "message": f"数据库 '{alias}' 已删除"}
    raise HTTPException(status_code=500, detail="保存配置失败")


@router.post("/config/databases/test", response_model=dict)
async def test_db_config(config: dict):
    """测试数据库连接（直接使用 SQLAlchemy，不经过 CLI 子进程）"""
    alias = config.get("alias", "").strip().lower()
    if alias:
        # 先尝试从已有配置测试
        existing = get_all_db_configs()
        if alias in existing:
            result = test_connection(alias)
            return {"success": result["success"], "database": alias, "message": result["message"]}

    # 用传入的配置参数测试
    from .connector_helper import get_connector_from_config

    connector = get_connector_from_config(config)
    if not connector:
        return {"success": False, "message": "无法构建数据库连接器，请检查配置"}

    try:
        connector.execute("SELECT 1 AS test")
        return {"success": True, "message": "连接成功 🎉"}
    except Exception as e:
        error_msg = str(e).lower()
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
