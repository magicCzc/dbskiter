# dbskiter - Database AIOps Assistant

<p align="center">
  <strong>Open-source database ops tool — let AI manage your databases</strong>
</p>

<p align="center">
  <a href="https://pypi.org/project/dbskiter/"><img src="https://img.shields.io/pypi/v/dbskiter" alt="PyPI version"></a>
  <a href="https://github.com/magicCzc/dbskiter/actions"><img src="https://img.shields.io/github/actions/workflow/status/magicCzc/dbskiter/ci.yml" alt="CI Status"></a>
  <a href="https://github.com/magicCzc/dbskiter/blob/main/LICENSE"><img src="https://img.shields.io/github/license/magicCzc/dbskiter" alt="License"></a>
  <a href="https://pypi.org/project/dbskiter/"><img src="https://img.shields.io/pypi/pyversions/dbskiter" alt="Python versions"></a>
  <a href="https://magicCzc.github.io/dbskiter/"><img src="https://img.shields.io/badge/docs-mkdocs-brightgreen" alt="Docs"></a>
</p>

> **Database Ops for the AI Era** — One line to give your AI assistant (Claude/Cursor) the ability to diagnose, monitor, secure, and back up 7 databases.

[中文文档](README.md) | [Documentation](https://magicczc.github.io/dbskiter/)

---

## ✨ 30-Second Demo (No Database Required)

```bash
# 1. Install
pip install dbskiter

# 2. Try it now (demo mode uses built-in mock data)
dbskiter --demo sql execute "SELECT 1"
dbskiter --demo diagnose realtime
dbskiter --demo monitor health
```

## 🤖 AI Assistant Integration (2026's Hottest Use Case)

Let Claude/Cursor/Trae directly invoke database capabilities:

```bash
# Install MCP Server
pip install dbskiter-mcp-server
```

```json
// Configure Claude Desktop (~/.config/claude/claude_desktop_config.json)
{
  "mcpServers": {
    "dbskiter": {
      "command": "dbskiter-mcp",
      "env": { "DB_HOST": "localhost", "DB_USER": "root", "DB_PASSWORD": "x", "DB_NAME": "mydb" }
    }
  }
}
```

Then ask Claude directly:
- "Is my database slow?"
- "Analyze this SQL: `SELECT * FROM orders WHERE created_at > '2026-01-01'`"
- "List today's 5 slowest queries"

**Full MCP config & examples**: [AI Integration Guide](https://magicczc.github.io/dbskiter/) · [MCP Server Repo](https://github.com/magicCzc/dbskiter-mcp-server)

---

## 🚀 5-Minute Quickstart

```bash
# 1. Interactive setup wizard (recommended for new users)
dbskiter init

# 2. Or manual setup (create .env file)
cp .env.example .env
# Edit .env with your database connection info

# 3. Verify
dbskiter --database=mydb monitor health
```

**Multi-database scenarios** (recommended: use aliases):

```bash
# Define DB_JUMP_*, DB_ORCL_* etc. in .env
dbskiter --database=jump monitor health   # Connects to MySQL
dbskiter --database=orcl  monitor health   # Connects to Oracle
```

**Tab completion** (highly recommended):

```bash
dbskiter shell-setup --auto   # One-line enable
```

---

## 📦 Supported Databases

| Level | Databases | Deep Support |
|-------|-----------|--------------|
| 🟢 Deep | MySQL / MariaDB / Oracle / PostgreSQL / SQL Server / ClickHouse / SQLite | Diagnose, monitor, security, backup, AAS calculation, slow query analysis |
| 🟡 Generic | Trino / Presto / DuckDB / Derby / H2 | Basic diagnose, monitor (Generic driver auto-detects capabilities) |

**Architecture**: 6 dedicated drivers + 1 Generic driver. Long-tail databases gracefully degrade instead of erroring.

---

## 🛠️ Core Features

| Command | Purpose | Example |
|---------|---------|---------|
| `diagnose` | Slow query / lock / index / comprehensive report | `diagnose slow-queries --top=10` |
| `monitor` | Health check / anomaly detection / capacity prediction | `monitor capacity --resource=disk` |
| `security` | SQL injection / sensitive data / password policy | `security audit` |
| `sql` | SQL execution / audit / rewrite | `sql execute "SELECT 1"` |
| `lock` | Lock analysis / deadlock detection | `lock analyze` |
| `inspector` | Comprehensive inspection / HTML report | `inspector report --output=r.html` |
| `scheduler` | Backup / scheduled tasks | `scheduler backup run` |

**Full command reference**: [CLI Guide](https://magicczc.github.io/dbskiter/) · [中文版](CLI使用指南.md)

---

## 📚 Documentation

- 📖 **[Full Documentation Site](https://magicczc.github.io/dbskiter/)** — 6 scenario tutorials, command dictionary
- 🆕 **[Quick Start for Beginners](https://magicczc.github.io/dbskiter/01-安装与配置/)** — 5-min intro
- 🤖 **[AI Integration Guide](https://magicczc.github.io/dbskiter/)** — Claude/Cursor/MCP integration
- ⚙️ **[Configuration Guide](https://magicczc.github.io/dbskiter/configuration/)** — `.env` / `config.yaml` / `--url` three ways
- 🏗️ **[Architecture Overview](https://magicczc.github.io/dbskiter/architecture/)** — 6+N driver architecture in detail
- 🤝 **[Contributing Guide](CONTRIBUTING.md)** — How to contribute

---

## 🏗️ Architecture Overview

```
dbskiter/
├── cli/                # CLI entry (argparse + custom command registration)
│   ├── commands/       # Command implementations (diagnose/monitor/security/...)
│   │   └── diagnose/   # diagnose command split into P0/P1/P2/db_specific mixin
│   └── url_parser.py   # URL connection string parser (based on SQLAlchemy make_url)
│
├── db_diagnose/        # Diagnose Skill (slow query, index, space, replication)
├── db_monitor/         # Monitor Skill (metrics collection, anomaly, capacity)
├── db_security/        # Security Skill (SQL injection, sensitive data, password)
├── db_scheduler/       # Scheduler Skill (backup, cron, connection pool)
├── db_inspector/       # Inspector Skill (comprehensive check, report)
├── db_lock_analyzer/   # Lock Analysis Skill
├── sql_master/         # SQL Execution Skill (execute, rewrite, audit, cache)
├── db_sql_auditor/     # SQL Audit Skill
│
└── shared/             # Cross-Skill shared components
    ├── database_connector.py   # SQLAlchemy unified connector
    ├── unified_connector.py    # JDBC/SQLAlchemy adapter
    ├── mysql_aas_calculator_v2.py  # MySQL AAS calculation
    ├── slow_log_parser.py      # Slow query log parser
    ├── ai_context.py          # AI context builder
    ├── prometheus_client.py   # Prometheus exporter
    └── zabbix_client.py       # Zabbix monitoring client
```

**6+N dual-layer driver**:
- **6 dedicated drivers**: Deep optimization for mainstream databases (AAS, slow query, exclusive SQL dialects)
- **1 Generic driver**: Auto-detect capabilities based on `INFORMATION_SCHEMA`, covering Trino/DuckDB and other long-tail databases
- **Graceful degradation**: Unsupported features return clear hints instead of errors

---

## 🛡️ Security Design (Three-Layer Defense in Depth)

| Layer | Mechanism |
|-------|-----------|
| AI Layer | Rule restrictions: prohibit AI from executing write operations |
| CLI Layer | `ReadOnlyEnforcer` middleware: env variable control interception |
| Database Layer | User permissions: physically limit account to read-only |

- Passwords use `MYSQL_PWD` / `PGPASSWORD` environment variables, won't appear in `ps` command
- SQL injection protection: table name whitelist + parameterization + value escaping
- Audit log: all write operations are immutably recorded

**Enable read-only mode**: `export DBSKITER_READ_ONLY=true`

---

## 📈 Production Readiness

| Module | Maturity | Key Metrics |
|--------|----------|-------------|
| CLI Core | 🟢 Production | Tab completion, history, JSON output, verbose logging |
| Health Monitoring | 🟢 Production | Anomaly detection, capacity prediction, trend analysis |
| Security Audit | 🟢 Production | SQL injection, sensitive data, password policy |
| Backup Scheduler | 🟢 Production | 7 databases, connection pool, distributed lock |
| SQL Execution | 🟡 Near Production | Execute/audit/cache + read-only security |
| Diagnose | 🟡 Near Production | Slow query/index recommendation/execution plan |
| Inspector | 🟡 Near Production | HTML report, config/security check |
| Lock Analysis | 🟡 Usable | Lock analysis/deadlock detection/wait chain tracking |
| Web UI | 🟢 Available | Vue 3 SPA, FastAPI backend |

**Test coverage**: 1,672+ test cases, 30% coverage (core modules 60-100%)

---

## 💼 Use Cases

- Small/medium businesses without dedicated DBAs need quick database diagnosis
- Teams using Claude/Cursor who want AI to directly operate databases
- Regular security audits and capacity inspections automation
- Unified management across MySQL/Oracle/PG/CH/MSSQL

---

## 🤝 Contributing

- Issues / PRs: [github.com/magicCzc/dbskiter](https://github.com/magicCzc/dbskiter)
- Development docs: [CONTRIBUTING.md](CONTRIBUTING.md)

---

## 📜 License

[MIT License](LICENSE) © MagiCzc

---

<p align="center">
  <strong>Let everyone manage databases easily</strong>
  <br>
  <sub>For questions, join WeChat group / submit Issue / email magiczc@139.com</sub>
</p>
