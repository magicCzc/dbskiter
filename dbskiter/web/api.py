"""
dbskiter/web/api.py

Web API 端点 - 8 个核心数据库运维能力

每个端点调用 dbskiter CLI 命令，输出统一 JSON 格式。
"""

import subprocess
import json
from typing import Optional, List
from pathlib import Path
from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel, Field

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


# ── CLI 执行器 ─────────────────────────────────────────────────────

def _run_cli(args: list, database: str = "default") -> dict:
    """
    执行 dbskiter CLI 命令并返回 JSON 结果

    Args:
        args: CLI 参数列表，如 ["monitor", "health"]
        database: 数据库别名

    Returns:
        dict: 解析后的 JSON 结果
    """
    # 构建 CLI 命令：--database 必须放在子命令之前
    cmd = [
        "dbskiter",
        "--output-mode=ai",
        "--database", database,
    ] + args

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode != 0:
            return {
                "success": False,
                "error": result.stderr.strip() or "CLI returned non-zero exit code",
            }

        # 解析 JSON 输出
        try:
            data = json.loads(result.stdout)
            data["success"] = True
            return data
        except json.JSONDecodeError:
            return {
                "success": False,
                "error": f"Failed to parse CLI output: {result.stdout[:200]}",
            }

    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "error": "CLI command timed out (30s)",
        }
    except FileNotFoundError:
        return {
            "success": False,
            "error": "dbskiter CLI not found. Install with: pip install dbskiter",
        }


# ── API 端点 ───────────────────────────────────────────────────────

@router.get("/health", response_model=HealthResponse)
async def get_health(
    database: str = Query("default", description="数据库别名或连接串"),
):
    """
    数据库健康检查

    返回健康评分、状态、问题列表。
    """
    result = _run_cli(["monitor", "health"], database)
    if not result.get("success"):
        raise HTTPException(status_code=502, detail=result.get("error", "Unknown error"))

    data = result.get("data", {})
    return HealthResponse(
        status=data.get("status", "UNKNOWN"),
        score=data.get("score", 0),
        issues=data.get("issues", []),
        collected_at=result.get("collected_at", ""),
    )


@router.get("/slow-queries", response_model=SlowQueryResponse)
async def get_slow_queries(
    database: str = Query("default"),
    top: int = Query(10, ge=1, le=100),
    hours: int = Query(1, ge=1, le=168),
    database_name: Optional[str] = Query(None, alias="database"),
):
    """
    慢查询分析

    返回 TOP N 慢查询，含执行时间、次数、扫描行数。
    """
    db = database_name or database
    result = _run_cli([
        "diagnose", "slow-queries",
        "--top", str(top),
        "--hours", str(hours),
    ], db)
    if not result.get("success"):
        raise HTTPException(status_code=502, detail=result.get("error", "Unknown error"))

    data = result.get("data", {})
    raw_metrics = data.get("raw_metrics", {})
    queries = raw_metrics.get("slow_queries", [])
    return SlowQueryResponse(
        total=len(queries),
        queries=[SlowQuery(**q) for q in queries[:top]],
    )


@router.get("/security", response_model=SecurityResponse)
async def run_security_audit(
    database: str = Query("default", description="数据库别名"),
):
    """
    安全审计

    执行 SQL 注入检测、敏感数据扫描、密码策略检查。
    """
    result = _run_cli(["security", "audit"], database)
    if not result.get("success"):
        raise HTTPException(status_code=502, detail=result.get("error", "Unknown error"))

    data = result.get("data", {})
    risks = []
    for r in data.get("risks", []):
        if isinstance(r, dict):
            risks.append(r)

    return SecurityResponse(
        total_risks=len(risks),
        critical_count=sum(1 for r in risks if r.get("severity") == "critical"),
        high_count=sum(1 for r in risks if r.get("severity") == "high"),
        risks=risks[:50],
    )


@router.get("/diagnose/realtime", response_model=dict)
async def get_realtime_diagnose(
    database: str = Query("default", description="数据库别名"),
):
    """
    实时诊断

    快速诊断数据库当前状态（慢查询、锁、连接、空间）。
    """
    result = _run_cli(["diagnose", "realtime"], database)
    if not result.get("success"):
        raise HTTPException(status_code=502, detail=result.get("error", "Unknown error"))
    return result


@router.get("/inspector/report", response_model=dict)
async def generate_inspector_report(
    database: str = Query("default", description="数据库别名"),
    report_type: str = Query("full", description="巡检类型: full/configuration/performance/storage"),
):
    """
    巡检报告

    生成综合巡检报告（配置、性能、安全、存储）。
    """
    result = _run_cli(["inspector", "run", "--type", report_type], database)
    if not result.get("success"):
        raise HTTPException(status_code=502, detail=result.get("error", "Unknown error"))
    return result


@router.post("/backup", response_model=BackupResponse)
async def create_backup(
    database: str = Query("default", description="数据库别名"),
    backup_type: str = Query("full", description="备份类型: full/incremental/table"),
    tables: Optional[str] = Query(None, description="表级备份时指定表名，逗号分隔"),
):
    """
    创建备份

    执行数据库备份操作。
    """
    args = [
        "scheduler", "backup",
        "--type", backup_type,
    ]
    if tables:
        args.extend(["--tables", tables])

    result = _run_cli(args, database)
    if not result.get("success"):
        raise HTTPException(status_code=502, detail=result.get("error", "Unknown error"))

    data = result.get("data", {})
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
    """
    备份列表

    查看所有备份记录。
    """
    result = _run_cli(["scheduler", "backup", "list"], database)
    if not result.get("success"):
        raise HTTPException(status_code=502, detail=result.get("error", "Unknown error"))
    return result


@router.get("/tasks", response_model=dict)
async def list_tasks(
    database: str = Query("default", description="数据库别名"),
):
    """
    定时任务列表

    查看所有已配置的定时任务。
    """
    result = _run_cli(["scheduler", "task", "list"], database)
    if not result.get("success"):
        raise HTTPException(status_code=502, detail=result.get("error", "Unknown error"))
    return result


@router.get("/logs", response_model=dict)
async def get_recent_logs(
    database: str = Query("default", description="数据库别名"),
    hours: int = Query(24, ge=1, le=720),
):
    """
    最近操作日志

    查看最近执行的历史命令和审计日志。
    """
    result = _run_cli(["history", "--hours", str(hours)], database)
    if not result.get("success"):
        raise HTTPException(status_code=502, detail=result.get("error", "Unknown error"))
    return result


@router.get("/databases", response_model=dict)
async def list_databases():
    """可用数据库列表"""
    from pathlib import Path
    databases = []
    env_path = Path.cwd() / ".env"
    if env_path.exists():
        with open(env_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("DB_") and line.endswith("_HOST="):
                    alias = line.split("=")[0].replace("DB_", "").replace("_HOST", "").lower()
                    if alias and alias not in databases:
                        databases.append(alias)
    if not databases:
        databases = ["default"]
    return {"databases": sorted(databases)}


@router.get("/diagnose/connection", response_model=dict)
async def test_connection(
    database: str = Query("default", description="数据库别名"),
):
    """测试数据库连接"""
    result = _run_cli(["diagnose", "realtime"], database)
    success = result.get("success", False)
    return {
        "success": success,
        "database": database,
        "message": "连接成功" if success else (result.get("error", "连接失败")),
        "data": result.get("data", {}) if success else None,
    }