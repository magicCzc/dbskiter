# 🎮 在线体验 Web UI

无需安装，无需数据库，直接在浏览器中体验 DBSKiter Web UI 的所有功能。

[👉 立即体验](https://magicczc.github.io/dbskiter/ui/){ .md-button .md-button--primary }

---

## 体验模式

点击上方按钮进入 **演示模式**，所有数据均为模拟数据，无需真实数据库。

在登录页面点击「🎮 演示模式（无需账号）」即可一键进入。

---

## 可以体验什么

### 📊 仪表盘
- 健康评分（动态变化）
- 慢查询、安全风险、告警统计
- ECharts 柱状图
- 最近活动记录

### 🔍 诊断分析
- 实时诊断（一键扫描）
- 慢查询 TOP N 分析
- 锁等待链分析
- 空间分析（大表排行）
- 连接管理（活跃连接 + KILL）

### 🔒 安全审计
- 安全评分（A-F 等级）
- 风险列表（严重/高/中/低）
- 修复建议

### 📋 巡检报告
- 6 种报告类型
- 分数看板
- 问题列表

### 🗄️ 数据库管理
- 完整 CRUD（新增/编辑/删除）
- 测试连接
- 支持 6 种数据库类型

### ⌨️ SQL 编辑器
- SQL 语法高亮
- 执行查询
- Schema 浏览
- 导出 CSV / JSON

### ⏰ 任务调度
- 创建/编辑/删除定时任务
- 启用/禁用
- Cron 表达式

### 🔔 告警管理
- 告警列表
- 确认/解决
- 统计看板

### 👥 用户管理
- 用户列表
- 角色管理（admin/editor/viewer）
- 启用/禁用

---

## 注意事项

- 演示模式运行在 **GitHub Pages** 上，所有数据为前端模拟
- 数据存储在浏览器内存中，刷新页面后会重置
- 如需连接真实数据库，请[本地部署](guides/webui.md)
- 默认管理员账号：`admin` / `admin123`

---

## 技术说明

演示模式使用前端 Mock 数据层实现：

- `src/mock/data.ts` — 模拟数据生成器（100+ 函数）
- `src/mock/index.ts` — API 路由分发器
- 在 `VITE_DEMO_MODE=true` 构建时自动启用
- 构建产物部署到 `gh-pages/ui/` 子目录

[查看部署源码](https://github.com/magicCzc/dbskiter/blob/main/.github/workflows/deploy-web.yml){ .md-button }