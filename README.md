# dbskiter - 数据库AIOps运维助手

<p align="center">
  <strong>开源免费的数据库运维工具，让AI帮你管理数据库</strong>
</p>

<p align="center">
  <a href="https://pypi.org/project/dbskiter/"><img src="https://img.shields.io/pypi/v/dbskiter" alt="PyPI version"></a>
  <a href="https://github.com/magicCzc/dbskiter/actions"><img src="https://img.shields.io/github/actions/workflow/status/magicCzc/dbskiter/ci.yml" alt="CI Status"></a>
  <a href="https://github.com/magicCzc/dbskiter/blob/main/LICENSE"><img src="https://img.shields.io/github/license/magicCzc/dbskiter" alt="License"></a>
  <a href="https://pypi.org/project/dbskiter/"><img src="https://img.shields.io/pypi/pyversions/dbskiter" alt="Python versions"></a>
  <a href="https://magicCzc.github.io/dbskiter/"><img src="https://img.shields.io/badge/docs-mkdocs-brightgreen" alt="Docs"></a>
</p>

> **AI 时代的数据库运维工具** —— 一行命令用 AI 助手（Claude/Cursor）调起 7 种数据库的诊断、监控、安全、备份能力

---

## ✨ 30 秒体验（无需数据库）

```bash
# 1. 安装
pip install dbskiter

# 2. 立刻试用（demo 模式内置 Mock 数据）
dbskiter --demo sql execute "SELECT 1"
dbskiter --demo diagnose realtime
dbskiter --demo monitor health
```

## 🤖 与 AI 助手集成（2026 年最热玩法）

让 Claude/Cursor/Trae 直接调度数据库能力：

```bash
# 安装 MCP Server
pip install dbskiter-mcp-server

# 配置 Claude Desktop (~/.config/claude/claude_desktop_config.json)
```

```json
{
  "mcpServers": {
    "dbskiter": {
      "command": "dbskiter-mcp",
      "env": { "DB_HOST": "localhost", "DB_USER": "root", "DB_PASSWORD": "x", "DB_NAME": "mydb" }
    }
  }
}
```

之后你可以直接问 Claude：
- "我的数据库慢吗？"
- "分析这条 SQL：`SELECT * FROM orders WHERE created_at > '2026-01-01'`"
- "给我列出今天最慢的 5 个查询"

**完整 MCP 配置与示例**：[AI集成指南](AI集成指南.md) · [MCP Server 仓库](https://github.com/magicCzc/dbskiter-mcp-server)

---

## 🚀 5 分钟快速开始

```bash
# 1. 交互式配置向导（推荐新手）
dbskiter init

# 2. 或手动配置（创建 .env 文件）
cp .env.example .env
# 编辑 .env 填入数据库连接信息

# 3. 验证
dbskiter --database=mydb monitor health
```

**多数据库场景**（推荐用别名）：

```bash
# .env 中定义 DB_JUMP_* / DB_ORCL_* 等
dbskiter --database=jump monitor health   # 连 MySQL
dbskiter --database=orcl  monitor health   # 连 Oracle
```

**Tab 补全**（强烈推荐）：

```bash
dbskiter shell-setup --auto   # 一键启用
```

---

## 📦 支持的数据库

| 级别 | 数据库 | 深度支持功能 |
|------|--------|------|
| 🟢 深度 | MySQL / MariaDB / Oracle / PostgreSQL / SQL Server / ClickHouse / SQLite | 诊断、监控、安全、备份、AAS 计算、慢查询分析 |
| 🟡 通用 | Trino / Presto / DuckDB / Derby / H2 | 基础诊断、监控（Generic 驱动自动能力探测） |

**架构**：6 个专用驱动 + 1 个 Generic 驱动，长尾库自动降级而非报错。

---

## 🛠️ 核心功能

| 命令 | 用途 | 示例 |
|------|------|------|
| `diagnose` | 慢查询/锁分析/索引推荐/综合报告 | `diagnose slow-queries --top=10` |
| `monitor` | 健康检查/异常检测/容量预测 | `monitor capacity --resource=disk` |
| `security` | SQL注入/敏感数据/密码策略 | `security audit` |
| `sql` | SQL执行/审核/重写 | `sql execute "SELECT 1"` |
| `lock` | 锁分析/死锁检测 | `lock analyze` |
| `inspector` | 综合巡检/HTML 报告 | `inspector report --output=r.html` |
| `scheduler` | 备份/定时任务 | `scheduler backup run` |

**详细命令说明**：[CLI使用指南](CLI使用指南.md)

---

## 📚 文档

- 📖 **[完整文档站](https://magicCzc.github.io/dbskiter/)** —— 6 大场景教程、命令字典
- 🆕 **[新手快速上手](docs/examples/01-新手快速上手/01-安装与配置.md)** —— 5 分钟入门
- 🤖 **[AI 集成指南](AI集成指南.md)** —— Claude/Cursor/MCP 集成
- ⚙️ **[CLI 使用指南](CLI使用指南.md)** —— 完整命令参考
- 🔧 **[配置文档](docs/configuration.md)** —— `.env` / `config.yaml` / `--url` 三种方式
- 🏗️ **[架构说明](#-架构概览)** —— 6+N 驱动架构详解
- 🤝 **[贡献指南](CONTRIBUTING.md)** —— 如何参与

---

## 🏗️ 架构概览

```
dbskiter/
├── cli/                # CLI 入口（基于 argparse + 自定义命令注册）
│   ├── commands/       # 各命令实现（diagnose/monitor/security/...）
│   │   └── diagnose/   # diagnose 命令拆分为 P0/P1/P2/db_specific mixin
│   └── url_parser.py   # URL 连接字符串解析（基于 SQLAlchemy make_url）
│
├── db_diagnose/        # 诊断 Skill（慢查询、索引、空间、复制）
├── db_monitor/         # 监控 Skill（指标采集、异常检测、容量预测）
├── db_security/        # 安全 Skill（SQL 注入、敏感数据、密码策略）
├── db_scheduler/       # 调度 Skill（备份、定时任务、连接池）
├── db_inspector/       # 巡检 Skill（综合检查、报告生成）
├── db_lock_analyzer/   # 锁分析 Skill
├── sql_master/         # SQL 执行 Skill（执行、重写、审核、缓存）
├── db_sql_auditor/     # SQL 审核 Skill
│
└── shared/             # 跨 Skill 共享组件
    ├── database_connector.py   # SQLAlchemy 统一连接器
    ├── unified_connector.py    # JDBC/SQLAlchemy 适配
    ├── mysql_aas_calculator_v2.py  # MySQL AAS 计算
    ├── slow_log_parser.py      # 慢查询日志解析
    ├── ai_context.py          # AI 上下文构建
    ├── prometheus_client.py   # Prometheus exporter
    └── zabbix_client.py       # Zabbix 监控客户端
```

**6+N 双层驱动**：
- **6 个专用驱动**：针对主流数据库做深度优化（AAS、慢查询、专属 SQL 方言）
- **1 个 Generic 驱动**：基于 `INFORMATION_SCHEMA` 自动能力探测，覆盖 Trino/DuckDB 等长尾库
- **优雅降级**：不支持的功能返回明确提示而非报错

---

## 🛡️ 安全设计（三层纵深防御）

| 层级 | 机制 |
|------|------|
| AI 层 | 规则限制：禁止 AI 执行写操作 SQL |
| CLI 层 | `ReadOnlyEnforcer` 中间件：环境变量控制拦截 |
| 数据库层 | 用户权限：物理限制账号只读 |

- 密码走 `MYSQL_PWD` / `PGPASSWORD` 环境变量，不进 `ps` 命令
- SQL 注入防护：表名白名单 + 参数化 + 值转义
- 审计日志：所有写操作不可变记录

**启用只读模式**：`export DBSKITER_READ_ONLY=true`

---

## 📈 生产就绪状态

| 模块 | 成熟度 | 关键指标 |
|------|--------|----------|
| CLI 核心 | 🟢 生产级 | Tab 补全、历史、JSON 输出、详细日志 |
| 健康监控 | 🟢 生产级 | 异常检测、容量预测、趋势分析 |
| 安全审计 | 🟢 生产级 | SQL 注入、敏感数据、密码策略 |
| 备份调度 | 🟢 生产级 | 7 种库、连接池、分布式锁 |
| SQL 执行 | 🟡 接近生产 | 执行/审核/缓存 + 只读安全 |
| 诊断 | 🟡 接近生产 | 慢查询/索引推荐/执行计划 |
| 巡检 | 🟡 接近生产 | HTML 报告、配置/安全检查 |
| 锁分析 | 🟡 可用 | 锁分析/死锁检测/等待链追踪 |
| Web UI | 🔴 规划中 | 2026 Q3 路线图 |

**测试覆盖**：1,641+ 测试用例，27% 覆盖率（核心模块 60-100%）

---

## 💼 适用场景

- 中小企业没有专职 DBA，需要快速诊断数据库问题
- 团队已用 Claude/Cursor，希望 AI 直接运维数据库
- 定期安全审计和容量巡检自动化
- 跨 MySQL/Oracle/PG/CH/MSSQL 多库统一管理

---

## 🤝 贡献

- 提 Issue / PR：[github.com/magicCzc/dbskiter](https://github.com/magicCzc/dbskiter)
- 开发文档：[CONTRIBUTING.md](CONTRIBUTING.md)
- 行为准则：[CODE_OF_CONDUCT](CODE_OF_CONDUCT)（待补充）

---

## 📜 License

[MIT License](LICENSE) © MagiCzc

---

<p align="center">
  <strong>让每个人都能轻松管理数据库</strong>
  <br>
  <sub>如有问题，加微信群 / 提 Issue / 邮件 magiczc@139.com</sub>
</p>