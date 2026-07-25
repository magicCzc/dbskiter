<!--
文件功能：DBSKiter Web UI 使用指南
作者：MagiCzc
创建时间：2026-07-24
-->

# Web UI 使用指南

DBSKiter Web UI 是一个基于 Vue 3 + FastAPI 的数据库运维管理界面。

---

## 快速启动

### 前置条件

- Python 3.8+，已安装 `dbskiter[web]`
- Node.js 18+（仅开发模式需要）
- 数据库连接已配置（`.env` 文件或环境变量）

### 一键启动（生产模式）

```bash
# 安装依赖
pip install 'dbskiter[web]'

# 构建前端（仅首次）
cd dbskiter/webui && npm install && npm run build

# 启动
python scripts/run_web.py
```

访问 http://localhost:8000/ui/

### 开发模式（热重载）

```bash
# 终端 1：启动后端
python scripts/run_web.py

# 终端 2：启动前端开发服务器
cd dbskiter/webui
npm run dev
```

访问 http://localhost:5173（Vite 开发服务器，API 自动代理到 :8000）

---

## 功能页面

| 页面 | 路由 | 功能 |
|------|------|------|
| 仪表盘 | `/ui/` | 健康评分、关键指标、快速操作 |
| 慢查询 | `/ui/slow-queries` | TOP N 慢查询分析、汇总统计 |
| 安全审计 | `/ui/security` | 风险扫描、安全评分 |
| 备份管理 | `/ui/backup` | 创建备份、查看备份记录 |
| 任务调度 | `/ui/scheduler` | 定时任务管理、操作日志 |

---

## 技术架构

```
┌─────────────────────┐      ┌──────────────────────┐      ┌──────────┐
│   Vue 3 SPA         │─────▶│   FastAPI Backend    │─────▶│ Database │
│   (dbskiter/webui)  │ HTTP │   (dbskiter/web)     │ CLI  │ (MySQL/  │
│                     │      │                      │      │  PG/...) │
│  Vite + TypeScript  │      │  /api/* → subprocess │      │          │
│  vue-router (SPA)   │      │  /ui/*  → SPA serve  │      │          │
│  API 代理 (dev)     │      │  /docs  → Swagger    │      │          │
└─────────────────────┘      └──────────────────────┘      └──────────┘
```

---

## 前后端分离说明

### 开发模式

Vite 开发服务器（:5173）代理所有 `/api/*` 请求到 FastAPI 后端（:8000），
实现前后端分离开发。

### 生产模式

Vue 构建产物输出到 `dbskiter/web/static/`，由 FastAPI 直接托管。
FastAPI 对 `/ui/*` 路径做 SPA fallback（所有路由返回 `index.html`）。

---

## 构建

```bash
cd dbskiter/webui

# 安装依赖
npm install

# 构建
npm run build

# 构建产物输出到 dbskiter/web/static/
# 结构：
#   static/
#   ├── index.html
#   └── assets/
#       ├── index-*.js       # Vue 运行时 + 路由
#       ├── index-*.css      # 全局样式
#       ├── Dashboard-*.js   # 懒加载页面
#       ├── SlowQueries-*.js
#       ├── Security-*.js
#       ├── Backup-*.js
#       └── Scheduler-*.js
```

---

## 新增页面

1. 在 `src/views/` 创建 `.vue` 文件
2. 在 `src/router/index.ts` 添加路由
3. 在 `src/api/index.ts` 添加 API 方法（如需）
4. 运行 `npm run build` 重新构建

---

## 故障排查

### 页面白屏 / 路由不生效

确保 FastAPI 后端正在运行，且 SPA fallback 正确：

```bash
curl http://localhost:8000/ui/slow-queries
# 应返回 HTML（index.html），而非 404
```

### API 报 502

表示 `dbskiter` CLI 命令不可用或数据库连接失败：

```bash
# 检查 CLI 是否可用
dbskiter --version

# 检查数据库连接
dbskiter --database=jump monitor health
```

### 前端构建失败

```bash
cd dbskiter/webui
rm -rf node_modules
npm install
npm run build
```

---

**最后更新**：2026-07-24