# DBSKiter Web API 文档

本文档描述 DBSKiter Web UI 后端 API 的所有端点。所有 API 端点都以前缀 `/api` 开头，base URL 默认为 `http://localhost:8000`。

---

## 通用说明

### 认证

除了 `/api/auth/*`、`/api/status`、`/api/health/*`、`/api/diagnose/connection` 外，所有端点都需要 JWT 认证。

认证方式：在 HTTP Header 中添加：
```
Authorization: Bearer <access_token>
```

### 响应格式

成功响应：
```json
{
  "success": true,
  "data": { ... }
}
```

失败响应：
```json
{
  "detail": "错误描述"
}
```

### 通用查询参数

| 参数 | 说明 |
|------|------|
| `database` | 数据库别名（如 `default`, `jump`, `chenzc`），默认 `default` |

---

## API 端点列表

### 1. 健康检查

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/status` | API 服务状态、版本、端点列表 |
| GET | `/api/health?database={alias}` | 单个数据库健康检查 |
| GET | `/api/health/all` | 所有数据库健康概览 |

**GET /api/health 响应**：
```json
{
  "status": "HEALTHY",
  "score": 95,
  "issues": [],
  "collected_at": "2026-07-28T10:30:00"
}
```

---

### 2. 监控

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/monitor/anomalies?database={alias}&hours={6}` | 异常检测 |
| GET | `/api/monitor/capacity?database={alias}&resource={disk\|memory\|connections}` | 容量预测 |
| GET | `/api/monitor/trends?database={alias}&hours={24}` | 资源趋势 |

---

### 3. 诊断

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/diagnose/realtime?database={alias}` | 实时综合诊断 |
| GET | `/api/diagnose/top?database={alias}&limit={10}` | TOP SQL 分析 |
| GET | `/api/diagnose/locks?database={alias}` | 锁分析 |
| GET | `/api/diagnose/space?database={alias}&top={20}` | 空间分析 |
| GET | `/api/diagnose/connections?database={alias}` | 连接分析 |
| GET | `/api/diagnose/connection?database={alias}` | 测试连接（仅 SELECT 1） |

---

### 4. 慢查询

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/slow-queries?database={alias}&top={10}&hours={1}` | 慢查询分析 |

**响应**：
```json
{
  "total": 5,
  "queries": [
    {
      "sql": "SELECT * FROM users WHERE ...",
      "execution_time": 12.5,
      "execution_count": 100,
      "avg_time": 10.2,
      "rows_examined": 10000
    }
  ]
}
```

---

### 5. 安全审计

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/security?database={alias}` | 安全审计 |

**响应**：
```json
{
  "total_risks": 5,
  "critical_count": 1,
  "high_count": 2,
  "risks": [
    {
      "severity": "critical",
      "description": "弱密码用户",
      "category": "permissions",
      "current_value": "...",
      "recommended_value": "..."
    }
  ]
}
```

---

### 6. 巡检报告

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/inspector/report?database={alias}&report_type={configuration\|performance\|storage\|security\|capacity\|replication\|full}` | 巡检报告 |

---

### 7. 备份

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/backup?database={alias}&backup_type={full\|incremental\|table}&tables={t1,t2}` | 创建备份 |
| GET | `/api/backups?database={alias}` | 备份列表 |

---

### 8. 定时任务

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/tasks` | 任务列表 |
| GET | `/api/tasks/types` | 任务类型 |
| POST | `/api/tasks` | 创建任务 |
| POST | `/api/tasks/{id}/toggle` | 启用/禁用 |
| DELETE | `/api/tasks/{id}` | 删除 |

**POST /api/tasks 请求体**：
```json
{
  "name": "每日健康诊断",
  "task_type": "diagnose",
  "db_alias": "default",
  "cron_expr": "0 9 * * *"
}
```

---

### 9. SQL 执行

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/sql/execute?database={alias}&sql={...}&limit={100}&read_only={true}` | 执行 SQL |
| GET | `/api/sql/schema?database={alias}&table={name?}` | Schema 信息 |

**POST /api/sql/execute 响应**：
```json
{
  "success": true,
  "execution_time": 0.123,
  "row_count": 10,
  "columns": ["id", "name"],
  "rows": [[1, "alice"], [2, "bob"]]
}
```

---

### 10. 数据库配置

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/config/databases` | 列出所有数据库 |
| POST | `/api/config/databases` | 新增数据库 |
| PUT | `/api/config/databases/{alias}` | 修改数据库 |
| DELETE | `/api/config/databases/{alias}` | 删除数据库 |
| POST | `/api/config/databases/test` | 测试连接 |

**POST /api/config/databases 请求体**：
```json
{
  "alias": "mydb",
  "dialect": "mysql+pymysql",
  "host": "127.0.0.1",
  "port": 3306,
  "user": "root",
  "password": "your_password",
  "database": "test",
  "pool_size": 5
}
```

支持的 `dialect`：
- `mysql+pymysql` — MySQL / MariaDB
- `postgresql+psycopg2` — PostgreSQL
- `oracle+oracledb` — Oracle
- `mssql+pymssql` — SQL Server
- `clickhouse+clickhouse_driver` — ClickHouse
- `sqlite` — SQLite

---

### 11. 认证

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/auth/login` | 用户登录 |
| POST | `/api/auth/register` | 用户注册 |
| GET | `/api/auth/me` | 当前用户信息（需登录） |
| POST | `/api/auth/logout` | 登出（前端清除 token） |

**POST /api/auth/login 请求体**：
```json
{
  "username": "admin",
  "password": "admin123"
}
```

**响应**：
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "username": "admin",
  "role": "admin"
}
```

---

### 12. 用户管理（管理员）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/auth/users` | 用户列表（需 admin） |
| PUT | `/api/auth/users/{user_id}/role` | 修改角色 |
| POST | `/api/auth/users/{user_id}/toggle` | 启用/禁用 |

---

### 13. 告警管理

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/alerts?db_alias={alias}&status={open\|acknowledged\|resolved\|all}&level={critical\|warning\|info}&limit={50}` | 告警列表 |
| GET | `/api/alerts/stats` | 告警统计 |
| POST | `/api/alerts/{id}/acknowledge` | 确认告警 |
| POST | `/api/alerts/{id}/resolve` | 解决告警 |
| POST | `/api/alerts/resolve-all` | 解决所有 |
| GET | `/api/alerts/history?hours={24}` | 历史告警 |

---

### 14. 操作历史

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/logs?database={alias}&hours={24}` | 操作日志 |

---

## 错误码

| HTTP 状态码 | 含义 |
|------------|------|
| 200 | 成功 |
| 400 | 请求参数错误 |
| 401 | 未认证或 token 过期 |
| 403 | 权限不足 |
| 404 | 资源不存在 |
| 409 | 资源冲突（如别名已存在） |
| 500 | 服务器内部错误 |
| 502 | 数据库连接失败 |

---

## 数据存储

- 用户配置：`~/.config/dbskiter/web.db` (SQLite)
- 指标历史：`~/.config/dbskiter/web.db` (同一文件)
- 备份配置：`dbskiter/config/databases.json`
- 同步到 CLI：`databases.json` 自动同步

---

**最后更新**：2026-07-28