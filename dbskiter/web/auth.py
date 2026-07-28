"""
dbskiter/web/auth.py

用户认证系统 — JWT 令牌认证

依赖: pip install pyjwt
"""

import os
import hashlib
from datetime import datetime, timedelta
from typing import Optional, Tuple
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel

try:
    import jwt

    JWT_AVAILABLE = True
except ImportError:
    JWT_AVAILABLE = False

from .database import (
    init_db,
    init_default_admin,
    get_session,
    session_scope,
    log_audit,
    User,
)

# 密钥
SECRET_KEY = os.environ.get("DBSKITER_JWT_SECRET", "dbskiter-web-secret-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24

router = APIRouter(prefix="/api/auth", tags=["auth"])
security = HTTPBearer(auto_error=False)


# ── Pydantic 模型 ────────────────────────────────────────


class LoginRequest(BaseModel):
    username: str
    password: str


class RegisterRequest(BaseModel):
    username: str
    password: str
    email: str = ""
    invite_code: str = ""


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str
    role: str


class UserInfo(BaseModel):
    id: int
    username: str
    role: str
    email: str
    last_login: Optional[str] = None


# ── 工具函数 ──────────────────────────────────────────────


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证密码"""
    try:
        from werkzeug.security import check_password_hash

        return check_password_hash(hashed_password, plain_password)
    except ImportError:
        # 没有 werkzeug，用简单 hash
        return hashlib.sha256(plain_password.encode()).hexdigest() == hashed_password


def hash_password(password: str) -> str:
    """哈希密码"""
    try:
        from werkzeug.security import generate_password_hash

        return generate_password_hash(password)
    except ImportError:
        return hashlib.sha256(password.encode()).hexdigest()


def create_access_token(username: str, role: str, user_id: int) -> str:
    """创建 JWT 令牌"""
    if not JWT_AVAILABLE:
        # 降级：返回简单令牌
        return f"{username}:{role}:{user_id}"

    expire = datetime.utcnow() + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    payload = {
        "sub": username,
        "role": role,
        "uid": user_id,
        "exp": expire,
        "iat": datetime.utcnow(),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> Optional[dict]:
    """解码 JWT 令牌"""
    if not JWT_AVAILABLE:
        # 降级解析
        parts = token.split(":")
        if len(parts) == 3:
            return {"sub": parts[0], "role": parts[1], "uid": int(parts[2])}
        return None

    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


# ── 依赖注入 ──────────────────────────────────────────────


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> Optional[dict]:
    """获取当前登录用户（可选认证）"""
    if not credentials:
        return None
    payload = decode_token(credentials.credentials)
    if not payload:
        return None
    return payload


async def require_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> dict:
    """要求用户已登录"""
    payload = await get_current_user(credentials)
    if not payload:
        raise HTTPException(status_code=401, detail="未登录或令牌已过期")
    return payload


async def require_admin(
    payload: dict = Depends(require_user),
) -> dict:
    """要求管理员权限"""
    if payload.get("role") != "admin":
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return payload


# ── API 端点 ──────────────────────────────────────────────


@router.post("/login", response_model=TokenResponse)
async def login(req: LoginRequest, request: Request):
    """用户登录"""
    with session_scope() as session:
        user = session.query(User).filter(User.username == req.username).first()
        if not user or not verify_password(req.password, user.password_hash):
            raise HTTPException(status_code=401, detail="用户名或密码错误")

        if not user.is_active:
            raise HTTPException(status_code=403, detail="账号已被禁用")

        # 更新登录时间
        user.last_login = datetime.utcnow()
        uid, uname, urole = user.id, user.username, user.role

    log_audit(uid, uname, "login", detail="用户登录", ip=request.client.host if request.client else "")

    token = create_access_token(uname, urole, uid)
    return TokenResponse(access_token=token, username=uname, role=urole)


@router.post("/register", response_model=TokenResponse)
async def register(req: RegisterRequest, request: Request):
    """用户注册"""
    if len(req.username) < 2:
        raise HTTPException(status_code=400, detail="用户名至少 2 个字符")
    if len(req.password) < 6:
        raise HTTPException(status_code=400, detail="密码至少 6 个字符")

    with session_scope() as session:
        existing = session.query(User).filter(User.username == req.username).first()
        if existing:
            raise HTTPException(status_code=409, detail="用户名已存在")

        user = User(
            username=req.username,
            password_hash=hash_password(req.password),
            role="editor",
            email=req.email or "",
        )
        session.add(user)
        session.flush()
        uid, uname, urole = user.id, user.username, user.role

    log_audit(uid, uname, "register", detail="用户注册", ip=request.client.host if request.client else "")

    token = create_access_token(uname, urole, uid)
    return TokenResponse(access_token=token, username=uname, role=urole)


@router.get("/me", response_model=UserInfo)
async def get_me(payload: dict = Depends(require_user)):
    """获取当前用户信息"""
    uid = payload.get("uid", 0)
    with session_scope() as session:
        user = session.query(User).filter(User.id == uid).first()
        if not user:
            raise HTTPException(status_code=404, detail="用户不存在")
        return UserInfo(
            id=user.id,
            username=user.username,
            role=user.role,
            email=user.email or "",
            last_login=user.last_login.isoformat() if user.last_login else None,
        )


@router.post("/logout")
async def logout(payload: dict = Depends(require_user)):
    """注销（前端清除 token 即可）"""
    return {"success": True, "message": "已退出登录"}


# ── 用户管理（管理员） ──────────────────────────────


@router.get("/users", response_model=dict)
async def list_users(payload: dict = Depends(require_admin)):
    """列出所有用户（管理员）"""
    with session_scope() as session:
        users = session.query(User).order_by(User.created_at.desc()).all()
        result = [
            {
                "id": u.id,
                "username": u.username,
                "role": u.role,
                "email": u.email,
                "is_active": u.is_active,
                "created_at": u.created_at.isoformat() if u.created_at else None,
                "last_login": u.last_login.isoformat() if u.last_login else None,
            }
            for u in users
        ]
    return {"success": True, "users": result}


@router.put("/users/{user_id}/role", response_model=dict)
async def update_user_role(user_id: int, body: dict, payload: dict = Depends(require_admin)):
    """修改用户角色（管理员）"""
    new_role = body.get("role", "")
    if new_role not in ("admin", "editor", "viewer"):
        raise HTTPException(status_code=400, detail="无效的角色")

    with session_scope() as session:
        user = session.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="用户不存在")
        user.role = new_role

    log_audit(payload.get("uid"), payload.get("sub", ""), "update", f"user:{user_id}", f"修改角色为 {new_role}")
    return {"success": True, "message": "角色已更新"}


@router.post("/users/{user_id}/toggle", response_model=dict)
async def toggle_user(user_id: int, payload: dict = Depends(require_admin)):
    """启用/禁用用户（管理员）"""
    with session_scope() as session:
        user = session.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="用户不存在")
        user.is_active = not user.is_active
        status = "启用" if user.is_active else "禁用"

    log_audit(payload.get("uid"), payload.get("sub", ""), "update", f"user:{user_id}", f"{status}用户")
    return {"success": True, "is_active": user.is_active, "message": f"用户已{status}"}


# ── 初始化 ──────────────────────────────────────────────


def init_auth():
    """初始化认证系统"""
    init_db()
    init_default_admin()
    if not JWT_AVAILABLE:
        print("[WARN] pyjwt 未安装，使用简单令牌模式")
        print("      建议安装: pip install pyjwt")
    else:
        print("[OK] JWT 认证已就绪")
    print("      默认管理员: admin / admin123")
