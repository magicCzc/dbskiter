"""
dbskiter/web/app.py

DBSKiter Web UI - FastAPI 应用入口

启动方式:
    uvicorn dbskiter.web.app:app --host 0.0.0.0 --port 8000

功能:
    - 8 个核心 API 端点（健康检查、慢查询、安全审计等）
    - 5 个前端页面（仪表盘、慢查询、安全、备份、调度）
    - Swagger UI 自动文档 (http://localhost:8000/docs)
    - CORS 支持（跨域请求）
"""

from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from .api import router as api_router

# 获取静态文件目录
STATIC_DIR = Path(__file__).resolve().parent / "static"

# 创建 FastAPI 应用
app = FastAPI(
    title="DBSKiter Web UI",
    description="数据库 AIOps 运维助手 - Web 管理界面",
    version="3.0.43",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS 中间件（允许前端跨域请求）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册 API 路由
app.include_router(api_router)

# 挂载静态文件（Vue 构建产物）
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
    """应用启动时执行的初始化"""
    # 确保静态目录存在
    STATIC_DIR.mkdir(parents=True, exist_ok=True)
    (STATIC_DIR / "css").mkdir(exist_ok=True)
    (STATIC_DIR / "js").mkdir(exist_ok=True)


@app.get("/api/status")
async def get_status():
    """API 健康检查"""
    return {
        "status": "ok",
        "version": "3.0.43",
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
        ],
    }


@app.get("/")
async def root():
    """重定向到 UI 首页"""
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/ui/index.html")