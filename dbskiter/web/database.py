"""
dbskiter/web/database.py

Web UI 数据层 — SQLite 持久化存储

表结构:
  - users: 用户认证
  - db_configs: 数据库配置
  - metric_history: 指标历史数据
  - alerts: 告警记录
  - scheduled_tasks: 定时任务
  - audit_logs: 操作审计日志
  - reports: 报告记录
"""

import os
import json
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any
from contextlib import contextmanager

from sqlalchemy import (
    create_engine, Column, Integer, String, Float, Text,
    DateTime, Boolean, JSON, ForeignKey, UniqueConstraint,
    Index, desc, func, and_
)
from sqlalchemy.orm import declarative_base, sessionmaker, Session, relationship

# 数据库路径
DB_DIR = Path.home() / ".config" / "dbskiter"
DB_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = str(DB_DIR / "web.db")

engine = create_engine(f"sqlite:///{DB_PATH}", echo=False, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False)
Base = declarative_base()


# ── 模型定义 ─────────────────────────────────────────────────


class User(Base):
    """用户"""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(64), unique=True, nullable=False, index=True)
    password_hash = Column(String(256), nullable=False)
    role = Column(String(16), nullable=False, default="viewer")  # admin / editor / viewer
    email = Column(String(128), default="")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime, nullable=True)


class DbConfig(Base):
    """数据库配置"""
    __tablename__ = "db_configs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    alias = Column(String(64), unique=True, nullable=False, index=True)
    host = Column(String(128), nullable=False, default="127.0.0.1")
    port = Column(Integer, nullable=False, default=3306)
    user = Column(String(64), nullable=False, default="root")
    password = Column(String(256), default="")
    database = Column(String(128), default="")
    dialect = Column(String(64), nullable=False, default="mysql+pymysql")
    pool_size = Column(Integer, default=5)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_env(self) -> Dict[str, str]:
        """转为 .env 格式的配置项"""
        prefix = f"DB_{self.alias.upper()}"
        return {
            f"{prefix}_HOST": self.host,
            f"{prefix}_PORT": str(self.port),
            f"{prefix}_USER": self.user,
            f"{prefix}_PASSWORD": self.password,
            f"{prefix}_NAME": self.database,
            f"{prefix}_DIALECT": self.dialect,
            f"{prefix}_POOL_SIZE": str(self.pool_size),
        }


class MetricHistory(Base):
    """指标历史数据"""
    __tablename__ = "metric_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    db_alias = Column(String(64), nullable=False, index=True)
    metric = Column(String(64), nullable=False)  # cpu, memory, disk, qps, connections
    value = Column(Float, nullable=False)
    unit = Column(String(32), default="")
    collected_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_metric_db_time", "db_alias", "metric", "collected_at"),
    )


class Alert(Base):
    """告警记录"""
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    db_alias = Column(String(64), nullable=False, index=True)
    metric = Column(String(64), nullable=False)
    level = Column(String(16), nullable=False, default="warning")  # info / warning / critical
    current_value = Column(Float, nullable=False)
    threshold = Column(Float, nullable=False)
    message = Column(Text, default="")
    status = Column(String(16), default="open")  # open / acknowledged / resolved
    created_at = Column(DateTime, default=datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)


class ScheduledTask(Base):
    """定时任务"""
    __tablename__ = "scheduled_tasks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(128), nullable=False)
    task_type = Column(String(32), nullable=False)  # diagnose / inspect / backup / report
    db_alias = Column(String(64), nullable=False)
    cron_expr = Column(String(64), nullable=False)  # cron 表达式
    params = Column(JSON, default={})
    is_enabled = Column(Boolean, default=True)
    last_run = Column(DateTime, nullable=True)
    next_run = Column(DateTime, nullable=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class AuditLog(Base):
    """操作审计日志"""
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    username = Column(String(64), default="")
    action = Column(String(64), nullable=False)  # login / execute / create / update / delete
    target = Column(String(128), default="")  # 操作对象
    detail = Column(Text, default="")
    ip_address = Column(String(64), default="")
    created_at = Column(DateTime, default=datetime.utcnow)


class Report(Base):
    """报告记录"""
    __tablename__ = "reports"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(128), nullable=False)
    report_type = Column(String(32), nullable=False)  # daily / weekly / monthly / custom
    db_alias = Column(String(64), nullable=False)
    status = Column(String(16), default="pending")  # pending / generating / done / failed
    file_path = Column(String(256), default="")
    summary = Column(JSON, default={})
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


# ── 数据库操作 ─────────────────────────────────────────────────


def init_db():
    """初始化数据库，创建所有表"""
    Base.metadata.create_all(engine)


def get_session() -> Session:
    """获取数据库会话"""
    return SessionLocal()


@contextmanager
def session_scope():
    """事务作用域"""
    session = get_session()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


# ── 用户操作 ─────────────────────────────────────────────────


def create_user(username: str, password_hash: str, role: str = "viewer", email: str = "") -> Optional[User]:
    """创建用户"""
    with session_scope() as session:
        existing = session.query(User).filter(User.username == username).first()
        if existing:
            return None
        user = User(username=username, password_hash=password_hash, role=role, email=email)
        session.add(user)
        session.flush()
        return user


def get_user_by_username(username: str) -> Optional[dict]:
    """通过用户名获取用户"""
    with session_scope() as session:
        user = session.query(User).filter(User.username == username).first()
        if user:
            return {"id": user.id, "username": user.username, "password_hash": user.password_hash,
                    "role": user.role, "email": user.email, "is_active": user.is_active,
                    "last_login": user.last_login}
        return None


def get_user_by_id(user_id: int) -> Optional[dict]:
    """通过 ID 获取用户"""
    with session_scope() as session:
        user = session.query(User).filter(User.id == user_id).first()
        if user:
            return {"id": user.id, "username": user.username, "password_hash": user.password_hash,
                    "role": user.role, "email": user.email, "is_active": user.is_active,
                    "last_login": user.last_login}
        return None


def update_last_login(user_id: int):
    """更新最后登录时间"""
    with session_scope() as session:
        user = session.query(User).filter(User.id == user_id).first()
        if user:
            user.last_login = datetime.utcnow()


# ── 数据库配置操作 ──────────────────────────────────────────


def save_db_config(config: dict) -> bool:
    """保存数据库配置到数据库"""
    try:
        with session_scope() as session:
            existing = session.query(DbConfig).filter(DbConfig.alias == config["alias"]).first()
            if existing:
                for key in ["host", "port", "user", "password", "database", "dialect", "pool_size"]:
                    if key in config:
                        setattr(existing, key, config[key] if key not in ("port", "pool_size") else int(config[key]))
                existing.updated_at = datetime.utcnow()
            else:
                db_config = DbConfig(**{k: v for k, v in config.items() if hasattr(DbConfig, k)})
                session.add(db_config)
        # 同步到 JSON 文件
        _sync_config_to_json()
        return True
    except Exception:
        return False


def delete_db_config(alias: str) -> bool:
    """删除数据库配置"""
    try:
        with session_scope() as session:
            session.query(DbConfig).filter(DbConfig.alias == alias).delete()
        _sync_config_to_json()
        return True
    except Exception:
        return False


def get_all_db_configs() -> Dict[str, dict]:
    """获取所有数据库配置"""
    with session_scope() as session:
        configs = session.query(DbConfig).filter(DbConfig.is_active == True).all()
        return {c.alias: {
            "host": c.host, "port": c.port, "user": c.user,
            "password": c.password, "database": c.database,
            "dialect": c.dialect, "pool_size": c.pool_size,
        } for c in configs}


def _sync_config_to_json():
    """同步数据库配置到 JSON 文件（供 CLI 读取）"""
    configs = get_all_db_configs()
    config_dir = Path(__file__).resolve().parent.parent / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_file = config_dir / "databases.json"
    config_file.write_text(json.dumps(configs, ensure_ascii=False, indent=2), encoding="utf-8")


# ── 指标历史操作 ──────────────────────────────────────────


def save_metric(db_alias: str, metric: str, value: float, unit: str = ""):
    """保存一条指标数据"""
    with session_scope() as session:
        m = MetricHistory(db_alias=db_alias, metric=metric, value=value, unit=unit)
        session.add(m)


def get_metric_history(db_alias: str, metric: str, hours: int = 24) -> List[dict]:
    """获取指标历史数据"""
    with session_scope() as session:
        since = datetime.utcnow().replace(second=0, microsecond=0)
        from datetime import timedelta
        since = since - timedelta(hours=hours)
        records = (
            session.query(MetricHistory)
            .filter(
                MetricHistory.db_alias == db_alias,
                MetricHistory.metric == metric,
                MetricHistory.collected_at >= since,
            )
            .order_by(MetricHistory.collected_at.asc())
            .all()
        )
        return [{"timestamp": r.collected_at.isoformat(), "value": r.value, "unit": r.unit} for r in records]


# ── 告警操作 ──────────────────────────────────────────


def create_alert(db_alias: str, metric: str, level: str, current_value: float, threshold: float, message: str = "") -> Alert:
    """创建告警"""
    with session_scope() as session:
        alert = Alert(
            db_alias=db_alias, metric=metric, level=level,
            current_value=current_value, threshold=threshold,
            message=message,
        )
        session.add(alert)
        session.flush()
        return alert


def get_open_alerts(db_alias: Optional[str] = None, limit: int = 50) -> List[Alert]:
    """获取未关闭的告警"""
    with session_scope() as session:
        query = session.query(Alert).filter(Alert.status == "open")
        if db_alias:
            query = query.filter(Alert.db_alias == db_alias)
        return query.order_by(desc(Alert.created_at)).limit(limit).all()


def acknowledge_alert(alert_id: int) -> bool:
    """确认告警"""
    with session_scope() as session:
        alert = session.query(Alert).filter(Alert.id == alert_id).first()
        if alert and alert.status == "open":
            alert.status = "acknowledged"
            return True
        return False


# ── 审计日志操作 ──────────────────────────────────────────


def log_audit(user_id: Optional[int], username: str, action: str, target: str = "", detail: str = "", ip: str = ""):
    """记录审计日志"""
    with session_scope() as session:
        log = AuditLog(
            user_id=user_id, username=username, action=action,
            target=target, detail=detail, ip_address=ip,
        )
        session.add(log)


def get_audit_logs(limit: int = 50) -> List[AuditLog]:
    """获取审计日志"""
    with session_scope() as session:
        return session.query(AuditLog).order_by(desc(AuditLog.created_at)).limit(limit).all()


# ── 初始化 ─────────────────────────────────────────────────


def init_default_admin():
    """创建默认管理员（如果不存在）"""
    from werkzeug.security import generate_password_hash
    with session_scope() as session:
        admin = session.query(User).filter(User.username == "admin").first()
        if not admin:
            admin = User(
                username="admin",
                password_hash=generate_password_hash("admin123"),
                role="admin",
                email="",
            )
            session.add(admin)
            session.flush()
            print(f"[OK] 默认管理员已创建: admin / admin123")


if __name__ == "__main__":
    init_db()
    init_default_admin()
    print(f"[OK] 数据库初始化完成: {DB_PATH}")
    print("     默认管理员: admin / admin123")