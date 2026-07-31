"""
dbskiter/web/app.py

DBSKiter Web UI - FastAPI 应用入口

启动方式:
    uvicorn dbskiter.web.app:app --host 0.0.0.0 --port 8000

功能:
    - 16 个 API 端点（健康检查、慢查询、安全审计等）
    - 16 个前端页面（仪表盘、SQL 编辑器、数据库配置等）
    - Web UI 数据库配置管理
    - 用户认证（JWT）
    - Swagger UI 自动文档 (http://localhost:8000/docs)
"""

import os
from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from .api import router as api_router
from .auth import router as auth_router, init_auth
from .alerter import router as alert_router
from .scheduler import router as task_router, init_scheduler
from .collector import collector

# 获取静态文件目录
STATIC_DIR = Path(__file__).resolve().parent / "static"

# 创建 FastAPI 应用
app = FastAPI(
    title="DBSKiter Web UI",
    description="数据库 AIOps 运维助手 - Web 管理界面",
    version="3.0.44",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS 中间件
#   - 优先从环境变量 DBSKITER_CORS_ORIGINS 读取（逗号分隔）
#   - 默认开发用 ["*"]（注意：allow_credentials=True 时浏览器会拒绝 *)
#   - 生产请设置为前端实际地址，例如 http://localhost:5173
_cors_raw = os.environ.get("DBSKITER_CORS_ORIGINS", "*").strip()
if _cors_raw == "*":
    _cors_origins = ["*"]
    _cors_credentials = False  # 浏览器规范下 * + credentials 非法
else:
    _cors_origins = [o.strip() for o in _cors_raw.split(",") if o.strip()]
    _cors_credentials = True

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=_cors_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册 API 路由
app.include_router(api_router)
app.include_router(auth_router)
app.include_router(alert_router)
app.include_router(task_router)

# 挂载静态文件
if STATIC_DIR.exists():
    app.mount("/ui/assets", StaticFiles(directory=str(STATIC_DIR / "assets")), name="assets")


from fastapi import Request
from fastapi.responses import FileResponse, JSONResponse


@app.middleware("http")
async def spa_fallback(request: Request, call_next):
    """SPA fallback middleware: 非 /ui/assets 的 /ui/* 返回 index.html"""
    path = request.url.path
    if path.startswith("/ui/") and not path.startswith("/ui/assets"):
        index_path = STATIC_DIR / "index.html"
        if index_path.exists():
            return FileResponse(str(index_path))
    return await call_next(request)


@app.on_event("startup")
async def startup():
    """应用启动时初始化"""
    STATIC_DIR.mkdir(parents=True, exist_ok=True)
    (STATIC_DIR / "css").mkdir(exist_ok=True)
    (STATIC_DIR / "js").mkdir(exist_ok=True)
    # 初始化数据库和认证
    init_auth()
    # 启动定时任务调度器
    init_scheduler()
    # 启动指标采集器
    await collector.start()


@app.get("/api/status")
async def get_status():
    """API 健康检查"""
    from .database import get_session, User

    db_ok = False
    try:
        with get_session() as s:
            db_ok = s.query(User).count() >= 0
    except Exception:
        pass
    return {
        "status": "ok",
        "version": "3.0.44",
        "auth": "enabled",
        "database": "ok" if db_ok else "error",
        "api_endpoints": [
            "/api/health",
            "/api/slow-queries",
            "/api/security",
            "/api/diagnose/realtime",
            "/api/inspector/report",
            "/api/backup (POST)",
            "/api/backups",
            "/api/tasks",
            "/api/logs",
            "/api/config/databases",
            "/api/auth/login",
            "/api/auth/register",
            "/api/auth/me",
        ],
    }


@app.get("/")
async def root():
    """重定向到 UI 首页"""
    from fastapi.responses import RedirectResponse

    return RedirectResponse(url="/ui/index.html")
