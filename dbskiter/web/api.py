"""
dbskiter/web/api.py

Web API 端点 - 8 个核心数据库运维能力

每个端点调用 dbskiter CLI 命令，输出统一 JSON 格式。
"""

import subprocess
import json
import asyncio
from typing import Optional
from concurrent.futures import ThreadPoolExecutor

# 线程池：避免同步 subprocess 阻塞 FastAPI 事件循环
_executor = ThreadPoolExecutor(max_workers=4)
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

def _diagnose_error(stderr: str) -> Optional[str]:
    """
    识别常见错误并给出可操作的提示

    Args:
        stderr: CLI 的 stderr 输出

    Returns:
        Optional[str]: 友好的错误提示，无法识别时返回 None
    """
    if not stderr:
        return None

    s = stderr.lower()

    # 权限不足
    if "process privilege" in s or "1227" in s:
        return (
            "数据库用户权限不足：缺少 PROCESS 权限。\n"
            "解决方法（在数据库执行）：\n"
            "  GRANT PROCESS ON *.* TO 'your_user'@'%';\n"
            "  FLUSH PRIVILEGES;"
        )
    if "access denied" in s and "user" in s:
        return "数据库认证失败：用户名或密码错误，请检查 .env 配置。"
    if "select command denied" in s or "1142" in s:
        return (
            "数据库用户缺少 SELECT 权限。\n"
            "解决方法：GRANT SELECT ON *.* TO 'your_user'@'%';"
        )

    # 连接问题
    if "can't connect" in s or "2003" in s or "10061" in s:
        return "无法连接到数据库：请检查主机地址、端口和网络连通性。"
    if "unknown database" in s or "1049" in s:
        return "数据库不存在：请检查 .env 中的数据库名配置。"
    if "timed out" in s or "timeout" in s:
        return "数据库连接超时：请检查网络或增加超时设置。"

    # performance_schema 未启用
    if "performance_schema" in s:
        return (
            "performance_schema 未启用或无权访问。\n"
            "解决方法（my.cnf）：performance_schema = ON"
        )

    return None


def _run_cli(args: list, database: str = "default") -> dict:
    """
    执行 dbskiter CLI 命令并返回 JSON 结果

    Args:
        args: CLI 参数列表，如 ["monitor", "health"]
        database: 数据库别名

    Returns:
        dict: 解析后的 JSON 结果

    Note:
        Windows GBK 编码问题：通过 encoding="utf-8" + errors="replace" 解决
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
            encoding="utf-8",
            errors="replace",
            timeout=30,
        )

        if result.returncode != 0:
            return {
                "success": False,
                "error": (result.stderr or "CLI returned non-zero exit code").strip()[:500],
            }

        # 解析 JSON 输出（可能为空）
        stdout = (result.stdout or "").strip()
        stderr = (result.stderr or "").strip()

        if not stdout:
            # 识别常见错误类型，给出可操作的提示
            hint = _diagnose_error(stderr)
            return {
                "success": False,
                "error": hint or f"CLI 未返回数据。详情: {stderr[:300]}",
                "raw_error": stderr[:500],
            }

        # CLI 可能在 JSON 前后输出日志/错误信息，提取第一个完整的 JSON 对象
        json_str = stdout
        first_brace = stdout.find("{")
        if first_brace > 0:
            # JSON 前有其他内容，从 { 开始提取
            json_str = stdout[first_brace:]
        elif first_brace == -1:
            # 没有 JSON，返回原始输出作为错误信息
            return {
                "success": False,
                "error": stdout[:300],
            }

        # 从末尾找最后一个 }，去掉 JSON 后的日志
        last_brace = json_str.rfind("}")
        if last_brace > 0:
            json_str = json_str[:last_brace + 1]

        try:
            data = json.loads(json_str)
            data["success"] = True
            return data
        except json.JSONDecodeError as e:
            return {
                "success": False,
                "error": f"CLI output not valid JSON: {stdout[:300]}",
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


async def _run_cli_async(args: list, database: str = "default") -> dict:
    """
    异步执行 CLI 命令（在线程池中运行，避免阻塞事件循环）

    这是关键优化：同步 subprocess.run 在 async 端点中会阻塞整个
    FastAPI 事件循环，导致其他请求（包括静态页面）全部排队等待。
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_executor, _run_cli, args, database)


# ── API 端点 ───────────────────────────────────────────────────────

@router.get("/health", response_model=HealthResponse)
async def get_health(
    database: str = Query("default", description="数据库别名或连接串"),
):
    """
    数据库健康检查

    返回健康评分、状态、问题列表。
    """
    result = await _run_cli_async(["monitor", "health"], database)
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
    result = await _run_cli_async([
        "diagnose", "slow-queries",
        "--top", str(top),
        "--since", f"{hours}h",
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
    result = await _run_cli_async(["security", "audit"], database)
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
    result = await _run_cli_async(["diagnose", "realtime"], database)
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
    result = await _run_cli_async(["inspector", "run", "--type", report_type], database)
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

    result = await _run_cli_async(args, database)
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
    result = await _run_cli_async(["scheduler", "backup", "list"], database)
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
    result = await _run_cli_async(["scheduler", "task", "list"], database)
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
    result = await _run_cli_async(["history", "--hours", str(hours)], database)
    if not result.get("success"):
        raise HTTPException(status_code=502, detail=result.get("error", "Unknown error"))
    return result


@router.get("/databases", response_model=dict)
async def list_databases():
    """
    可用数据库列表

    扫描 .env 中的 DB_{ALIAS}_HOST 配置，提取数据库别名。
    同时检查 DB_HOST（默认配置）。
    """
    import re
    from pathlib import Path

    databases = []
    env_path = Path.cwd() / ".env"

    if env_path.exists():
        content = env_path.read_text(encoding="utf-8", errors="replace")
        # 匹配 DB_{ALIAS}_HOST=value （别名配置）
        for match in re.finditer(r"^DB_([A-Z0-9_]+)_HOST\s*=", content, re.MULTILINE):
            alias = match.group(1).lower()
            if alias and alias not in databases:
                databases.append(alias)
        # 检查默认配置 DB_HOST=value
        if re.search(r"^DB_HOST\s*=", content, re.MULTILINE):
            if "default" not in databases:
                databases.append("default")

    if not databases:
        databases = ["default"]

    return {"databases": sorted(databases)}


@router.get("/diagnose/connection", response_model=dict)
async def test_connection(
    database: str = Query("default", description="数据库别名"),
):
    """测试数据库连接"""
    result = await _run_cli_async(["diagnose", "realtime"], database)
    success = result.get("success", False)
    return {
        "success": success,
        "database": database,
        "message": "连接成功" if success else (result.get("error", "连接失败")),
        "data": result.get("data", {}) if success else None,
    }