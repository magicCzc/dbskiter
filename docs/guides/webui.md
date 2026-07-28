<!--
文件功能：DBSKiter Web UI 使用指南
作者：MagiCzc
最后更新：2026-07-28
-->

# Web UI 使用指南

DBSKiter Web UI 是一个基于 Vue 3 + FastAPI 的数据库运维管理界面。

---

## 快速启动

### 前置条件

- Python 3.8+，已安装 `dbskiter[web]`
- Node.js 18+（仅开发模式需要）
- 数据库连接已配置

### 一键启动（生产模式）

```bash
pip install 'dbskiter[web]'

# 构建前端（仅首次）
cd dbskiter/webui && npm install && npm run build

# 启动
python scripts/run_web.py
```

访问 http://localhost:8000/ui/

### 开发模式（热重载）

```bash
python scripts/run_web.py
cd dbskiter/webui && npm run dev
```

访问 http://localhost:5173（Vite 开发服务器，API 自动代理到 :8000）

### 默认账号

首次启动后自动创建管理员账号：**admin / admin123**

> ⚠️ 生产环境请立即修改密码

---

## 功能页面（22 个）

### 📊 监控（5 个）

| 页面 | 路由 | 功能 |
|------|------|------|
| 仪表盘 | `/` | 健康评分、4 个统计卡片、ECharts 柱状图、最近活动、快速操作 |
| 实时诊断 | `/diagnose` | 一键诊断、问题摘要、快捷跳转 |
| 告警管理 | `/alerts` | 告警列表、确认/解决、4 个 KPI 卡片 |
| 异常检测 | `/anomalies` | 异常散点图、严重度筛选 |
| 容量预测 | `/capacity` | 磁盘/内存/连接数预测、增长率、剩余天数 |

### 🔍 分析（5 个）

| 页面 | 路由 | 功能 |
|------|------|------|
| 慢查询 | `/slow-queries` | TOP N 慢查询、EXPLAIN 分析、CSV 导出 |
| 锁分析 | `/locks` | 锁等待链 |
| 空间分析 | `/space` | 大表排行、空闲空间 |
| 安全审计 | `/security` | 风险扫描、安全评分、修复建议 |
| 巡检报告 | `/inspector` | 6 种报告类型、分数看板 |

### 🛠️ 管理（6 个）

| 页面 | 路由 | 功能 |
|------|------|------|
| 连接管理 | `/connections` | 活跃连接、终止连接（KILL） |
| 备份管理 | `/backup` | 创建备份、备份列表、CSV 导出 |
| 任务调度 | `/scheduler` | 定时任务 CRUD、Cron 表达式 |
| 操作历史 | `/history` | 命令历史、参数、耗时、失败统计 |
| 数据库管理 | `/databases` | **完整 CRUD + 测试连接** |
| 用户管理 | `/users` | 用户列表、角色管理、启用/禁用 |

### ⌨️ 工具（2 个）

| 页面 | 路由 | 功能 |
|------|------|------|
| SQL 编辑器 | `/sql-editor` | SQL 语法高亮、执行、历史、Schema 浏览、CSV 导出 |
| 系统配置 | `/configuration` | 服务状态、连接测试、数据库列表 |

### 🔑 认证

| 页面 | 路由 | 功能 |
|------|------|------|
| 登录 | `/login` | 登录/注册切换 |

---

## 数据库配置流程

### 方式一：Web UI 添加（推荐）

1. 进入「数据库管理」→「新增数据库」
2. 填写连接信息（支持 MySQL/PostgreSQL/Oracle/SQL Server/ClickHouse/SQLite）
3. 点击「测试连接」可立即验证
4. 保存后可在 SQL 编辑器中直接使用

### 方式二：.env 文件

```bash
# DB_{ALIAS}_HOST 格式
DB_JUMP_HOST=192.168.1.10
DB_JUMP_PORT=3306
DB_JUMP_USER=root
DB_JUMP_PASSWORD=your_password
DB_JUMP_NAME=mydb
DB_JUMP_DIALECT=mysql+pymysql
```

---

## 技术架构

```
┌─────────────────────┐      ┌──────────────────────┐      ┌──────────┐
│   Vue 3 SPA         │─────▶│   FastAPI Backend    │─────▶│ Database │
│   (dbskiter/webui)  │ HTTP │   (dbskiter/web)     │ 调用 │ (MySQL/  │
│                     │      │                      │ Skill │  PG/...) │
│  Vite + TypeScript  │      │  /api/* → Skill 类   │      │          │
│  vue-router (SPA)   │      │  /ui/*  → SPA serve  │      │          │
│  Pinia 状态管理     │      │  /docs  → Swagger    │      │          │
│  Element Plus UI    │      │  /api/auth → JWT     │      │          │
│  ECharts 图表       │      │                      │      │          │
└─────────────────────┘      └──────────────────────┘      └──────────┘
```

**核心特性**：
- **进程内调用**：API 端点直接调用 `DiagnoseSkill`、`MonitorSkill` 等 Python 类，不经过 CLI 子进程
- **统一配置**：Web UI 的数据库配置与 `.env` 自动同步
- **JWT 认证**：所有需要认证的端点使用 Bearer Token
- **SPA fallback**：所有 `/ui/*` 路由返回 `index.html`

---

## 前后端分离说明

### 开发模式

Vite 开发服务器（:5173）代理所有 `/api/*` 请求到 FastAPI 后端（:8000），实现前后端分离开发。

### 生产模式

Vue 构建产物输出到 `dbskiter/web/static/`，由 FastAPI 直接托管。
FastAPI 对 `/ui/*` 路径做 SPA fallback（所有路由返回 `index.html`）。

---

## 构建

```bash
cd dbskiter/webui

# 安装依赖
npm install

# 类型检查 + 构建
npm run build

# 构建产物输出到 dbskiter/web/static/
# 结构：
#   static/
#   ├── index.html
#   └── assets/
#       ├── index-*.js       # Vue 运行时 + 路由
#       ├── index-*.css      # 全局样式
#       ├── Dashboard-*.js   # 懒加载页面
#       ├── Databases-*.js
#       ├── Diagnose-*.js
#       └── ... (22 个页面)
```

---

## 新增页面

1. 在 `src/views/` 创建 `.vue` 文件
2. 在 `src/router/index.ts` 添加路由
3. 在 `src/api/index.ts` 添加 API 方法（如需）
4. 在 `src/types/index.ts` 添加类型定义（如需）
5. 运行 `npm run build` 重新构建

### 页面模板

```vue
<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useDatabaseStore } from '@/stores/database'
import { api } from '@/api'
import { ElMessage } from 'element-plus'

const dbStore = useDatabaseStore()
const loading = ref(false)
const data = ref<MyData[]>([])

async function load() {
  loading.value = true
  try {
    const result = await api.myEndpoint(dbStore.current)
    data.value = result.data || []
  } catch (e: any) {
    ElMessage.error(`加载失败: ${e.message}`)
  } finally {
    loading.value = false
  }
}

onMounted(() => { dbStore.loadDatabases(); load() })
</script>
```

---

## API 文档

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
- 详细文档：`docs/api/` 目录

---

## 故障排查

### 页面白屏 / 路由不生效

确保 FastAPI 后端正在运行，且 SPA fallback 正确：

```bash
curl http://localhost:8000/ui/slow-queries
# 应返回 HTML（index.html），而非 404
```

### API 报 502

表示数据库连接失败或配置缺失：

```bash
# 检查 CLI 是否可用
dbskiter --version

# 检查数据库连接（通过 Web UI "系统配置" 页面的"测试连接"按钮）
```

### 测试连接失败

检查 `dbskiter/web/database.py` 中的配置存储：

```bash
ls -la ~/.config/dbskiter/web.db
```

### 前端构建失败

```bash
cd dbskiter/webui
rm -rf node_modules
npm install
npm run build
```

### 登录失败

默认管理员 `admin / admin123`，如果忘记密码：

```bash
python -c "
from dbskiter.web.database import session_scope, User
from werkzeug.security import generate_password_hash
with session_scope() as s:
    u = s.query(User).filter(User.username == 'admin').first()
    u.password_hash = generate_password_hash('admin123')
"
```

---

## 性能优化

- 30 秒前端缓存（`src/api/index.ts` 的 `CACHE_TTL`）
- Dashboard 30 秒自动刷新（可关闭）
- Connections 10 秒自动刷新（可关闭）
- keep-alive 缓存已访问的页面

---

**最后更新**：2026-07-28