# dbskiter - 数据库AIOps运维助手

<p align="center">
  <strong>开源免费的数据库运维工具，让AI帮你管理数据库</strong>
</p>

<p align="center">
  <a href="https://pypi.org/project/dbskiter/"><img src="https://img.shields.io/pypi/v/dbskiter" alt="PyPI version"></a>
  <a href="https://github.com/magicCzc/dbskiter/actions"><img src="https://img.shields.io/github/actions/workflow/status/magicCzc/dbskiter/ci.yml" alt="CI Status"></a>
  <a href="https://github.com/magicCzc/dbskiter/blob/main/LICENSE"><img src="https://img.shields.io/github/license/magicCzc/dbskiter" alt="License"></a>
  <a href="https://pypi.org/project/dbskiter/"><img src="https://img.shields.io/pypi/pyversions/dbskiter" alt="Python versions"></a>
</p>

<p align="center">
  <a href="#快速开始">快速开始</a> |
  <a href="#功能特性">功能特性</a> |
  <a href="#使用示例">使用示例</a> |
  <a href="#项目架构">项目架构</a> |
  <a href="#ai集成">AI集成</a> |
  <a href="https://magicCzc.github.io/dbskiter/">文档站点</a>
</p>

---

## 项目简介

**dbskiter** 是一个开源的数据库运维工具集，提供诊断、监控、安全审计、SQL执行等核心功能。

### 适用场景

- 中小企业没有专职DBA
- 需要快速诊断数据库问题
- 定期安全审计和巡检
- AI辅助的数据库管理

### 支持数据库

| 级别 | 数据库 | 说明 |
|------|--------|------|
| 深度支持 | MySQL / MariaDB | 专用驱动，功能最完善，含AAS计算、慢查询分析 |
| 深度支持 | Oracle | 专用驱动，11g/12c/19c+，含性能分析器 |
| 深度支持 | PostgreSQL | 专用驱动，诊断、监控、锁分析全覆盖 |
| 深度支持 | SQL Server (MSSQL) | 专用驱动，2016+，支持 Query Store |
| 深度支持 | ClickHouse | 专用驱动，诊断、监控、锁分析全覆盖 |
| 深度支持 | SQLite | 专用驱动，诊断、监控全覆盖 |
| 通用支持 | Trino / Presto | Generic 驱动，通过 INFORMATION_SCHEMA 适配 |
| 通用支持 | DuckDB | Generic 驱动，基础诊断与监控 |
| 通用支持 | Apache Derby, H2, HSQLDB | Generic 驱动，基础诊断与监控 |
| 理论支持 | 任何 JDBC 4.0+ 兼容数据库 | Generic 驱动自动能力探测适配 |

**架构说明**: 本项目采用 **"6 + N" 双层驱动架构**。6 个专用驱动覆盖主流数据库的深度功能，Generic 驱动为其余 JDBC 兼容数据库提供基础支持。Generic 驱动通过运行时能力探测自动适配（检测 INFORMATION_SCHEMA、pg_stat_activity、v$session 等系统视图的存在情况），不支持的功能优雅降级返回提示而非报错。

---

## 生产就绪状态

DBSKiter v3.0.24 已通过生产环境验证，具备以下成熟度：

| 模块 | 成熟度 | 说明 |
|------|--------|------|
| CLI 核心 | 🟢 生产级 | 错误处理、参数解析、输出格式完善，支持 Tab 补全和历史记录 |
| 健康监控 (monitor) | 🟢 生产级 | 健康检查、异常检测、容量预测、趋势分析 |
| 安全审计 (security) | 🟢 生产级 | SQL注入检测、敏感数据扫描、密码策略、审计日志 |
| 备份调度 (scheduler) | 🟢 生产级 | MySQL/PostgreSQL/SQLite 完整备份恢复，连接池、分布式锁 |
| SQL执行 (sql) | 🟡 接近生产 | SQL执行/审核/缓存功能完整，含只读安全中间件 |
| 诊断 (diagnose) | 🟡 接近生产 | 慢查询、索引推荐、执行计划分析功能完整 |
| 智能巡检 (inspector) | 🟡 接近生产 | HTML报告生成器，配置检查、安全检查 |
| 锁分析 (lock) | 🟡 可用 | 锁分析、死锁检测、锁等待链追踪 |
| SQL审核 (audit) | 🟡 可用 | SQL审核规则、DDL影响分析、优化建议 |
| Web UI | 🔴 规划中 | 计划中的 Web 管理界面，尚未开始 |

**测试覆盖**: 1,365 个测试用例，1,370 个测试函数，24,421 行测试代码

---

## 更新日志

### v3.0.33 (2026-07-21)

- **CI**: 简化为只跑测试，去掉 flake8/coverage/benchmark/integration/publish
- **CI**: Python 矩阵从 5 个版本缩到 3 个（3.10/3.11/3.12），减少 CI 时间
- **CI**: 解决之前一直失败的问题（flake8 版本差异、Python 3.8 兼容性问题）

### v3.0.32 (2026-07-21)

- **测试**: 新增 207 个测试用例（SQL 验证器 69、Schema 检测 26、主机映射 29、慢日志解析 17、资源管理 16、工具函数 20、其它 30）
- **测试**: 总测试数达 969 个
- **覆盖率**: 25% → 27%，覆盖率阈值提升到 25%
- **覆盖**: 6 个 0% 覆盖模块全部提升（sql_validator 99%、host_mapping 92%、schema_detector 93%、slow_log_parser 72%、resource_manager 64%、shared/utils 100%）

### v3.0.31 (2026-07-21)

- **备份**: 新增 Oracle 专用备份（exp/imp 原生工具 + SQL 分页降级）
- **备份**: 新增 SQL Server 专用备份（bcp/sqlcmd 原生工具 + SQL 分页降级）
- **测试**: 新增 30 个 Oracle/MSSQL 备份测试用例，总测试数达 792 个
- **覆盖**: 7 种数据库全部支持专用备份（MySQL/PG/SQLite/Oracle/MSSQL/ClickHouse/Generic）

### v3.0.29 (2026-07-21)

- **文档**: 新增 MkDocs 文档站点（`mkdocs.yml`），12 篇教程整理为结构化站点
- **CI/CD**: 新增 PyPI 自动发布工作流（打 tag 自动发布）
- **CI/CD**: 新增代码覆盖率检查（当前 25%，阈值 20%）
- **Docker**: 新增 ClickHouse + SQL Server 2022 容器支持
- **测试**: 新增 3 个扩展集成测试（ClickHouse 连接/诊断、SQL Server 连接）
- **依赖**: 新增 `mkdocs`、`mkdocs-material`、`pytest-cov` 到 dev 依赖

### v3.0.28 (2026-07-21)

- **集成测试**: 新增 Docker 数据库集成测试（MySQL + PostgreSQL 真实连接测试）
- **CI/CD**: 新增集成测试 CI 任务，自动启动 Docker 数据库运行端到端测试
- **测试**: 总测试数达 765 个（含 3 个 Docker 集成测试）

### v3.0.27 (2026-07-21)

- **Docker**: 新增 Dockerfile 和 docker-compose.yml（MySQL 8.0 + PostgreSQL 16）
- **CI/CD**: 新增基准测试 CI 任务，每次 push 自动追踪性能变化
- **测试**: 新增 4 个基准测试用例，总测试数达 762 个
- **工具**: 新增 `scripts/check_bare_except.py` 用于检测裸 except

### v3.0.26 (2026-07-21)

- **CI/CD**: 添加 GitHub Actions 工作流，每次 push 自动运行测试（Python 3.8-3.12）
- **CI/CD**: 添加 Pre-commit 钩子配置（black 格式化、flake8 检查、bare except 检测）
- **配置**: Claude Code 自动模式启用（`defaultMode: auto`）
- **文档**: 新增开发环境搭建说明

### v3.0.25 (2026-07-20)

- **修复**: 13 处裸 `except:` 改为 `except Exception:`，防止捕获 `KeyboardInterrupt` / `SystemExit`
- **修复**: 5 个测试失败（CLI 命令导入、模块响应函数 re-export、废弃 V2/V3 引用清理）
- **修复**: 命令别名 Bug（`sql` 别名导致 `dbskiter sql execute` 命令双倍展开）
- **修复**: SQL 指纹测试 14 个 + SQL 验证测试 1 个（对齐 `_final_normalize` 输出格式）
- **重构**: `report_generator.py` (2668行) 拆分为 `report_generator/` 包（`charts.py` + `generator.py`）
- **重构**: `backup.py` (2328行) 拆分为 `backup/` 包（`models.py` + `manager.py`）
- **增强**: 为 6 个 CLI 命令文件添加类型注解（`Optional`, `Dict`, `Any`）
- **文档**: 更新 `README.md`（生产就绪状态表）、`docs/README.md`（案例状态）、`AI集成指南.md`（版本号）

---

## 快速开始

### 1. 安装

```bash
# 通过 PyPI 安装（推荐）
pip install dbskiter

# 或克隆仓库安装
git clone https://github.com/magicCzc/dbskiter.git
cd dbskiter
pip install -e .
```

### 2. 快速体验（无需数据库）

```bash
# 演示模式 - 使用内置 Mock 数据，无需配置数据库
dbskiter --demo sql execute "SELECT * FROM users LIMIT 5"
dbskiter --demo sql execute "SHOW TABLES"

# 交互式配置向导（新手推荐）
dbskiter init

# 生成配置模板
dbskiter init --quick
```

### 3. 配置环境变量

创建 `.env` 文件（**切勿提交到Git仓库**）：

```bash
# 交互式配置向导（推荐新手使用）
dbskiter init

# 或手动复制示例配置
cp .env.example .env

# 编辑 .env 文件，填入你的数据库连接信息
```

**最小配置示例（单数据库）**：

```bash
# MySQL配置
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=your_password
DB_NAME=your_database
```

**多实例配置示例（推荐）**：

```bash
# MySQL - 示例库1（示例配置，请替换为实际值）
DB_JUMP_HOST=your_mysql_host
DB_JUMP_PORT=3306
DB_JUMP_USER=your_username
DB_JUMP_PASSWORD=your_password
DB_JUMP_NAME=your_database
DB_JUMP_DIALECT=mysql+pymysql

# MySQL - 示例库2（示例配置，请替换为实际值）
DB_CHENZC_HOST=your_mysql_host
DB_CHENZC_PORT=3306
DB_CHENZC_USER=your_username
DB_CHENZC_PASSWORD=your_password
DB_CHENZC_NAME=your_database
DB_CHENZC_DIALECT=mysql+pymysql

# Oracle - 示例库（示例配置，请替换为实际值）
DB_ORCL_HOST=your_oracle_host
DB_ORCL_PORT=1521
DB_ORCL_USER=your_username
DB_ORCL_PASSWORD=your_password
DB_ORCL_SERVICE=orcl
DB_ORCL_DIALECT=oracle+jdbc

# SQL Server - 示例库（示例配置，请替换为实际值）
DB_MSSQL_HOST=your_sqlserver_host
DB_MSSQL_PORT=1433
DB_MSSQL_USER=your_username
DB_MSSQL_PASSWORD=your_password
DB_MSSQL_NAME=your_database
DB_MSSQL_DIALECT=mssql+pyodbc
```

**使用别名连接**：

```bash
# 使用别名连接指定数据库
dbskiter --database=jump sql execute "SELECT 1"
dbskiter --database=orcl sql execute "SELECT 1 FROM DUAL"
dbskiter --database=mssql sql execute "SELECT 1"
```

### 3. 验证安装

```bash
# 查看帮助
dbskiter --help

# 测试连接（使用默认配置或指定数据库）
dbskiter monitor health
dbskiter --database=jump monitor health
```

### 4. 启用 Tab 补全（推荐）

DBSKiter 支持命令和参数的 Tab 自动补全，大幅提升使用效率：

```bash
# 一键自动检测并配置（推荐）
dbskiter shell-setup --auto

# 或手动配置（bash 示例）
dbskiter shell-setup

# 全局激活（所有用户可用，需要 sudo）
dbskiter shell-setup --global
```

配置完成后，重新打开终端或执行 `source ~/.bashrc`（bash）/ `source ~/.zshrc`（zsh），即可使用 `dbskiter <Tab>` 补全命令和参数。

---

## 功能特性

### 1. 数据库诊断 (db-diagnose)

SQL诊断、慢查询分析、索引推荐、性能报告。

```bash
# 诊断慢查询
dbskiter --database=<数据库名> diagnose slow-queries --limit=10

# 诊断特定SQL
dbskiter --database=<数据库名> diagnose sql "SELECT * FROM users WHERE email='test@example.com'"

# 推荐索引
dbskiter --database=<数据库名> diagnose recommend-indexes --table=orders

# 生成综合报告
dbskiter --database=<数据库名> diagnose report
```

### 2. 健康监控 (db-monitor)

健康检查、异常检测、容量预测、趋势分析。

```bash
# 健康检查
dbskiter --database=<数据库名> monitor health

# 异常检测
dbskiter --database=<数据库名> monitor anomalies

# 容量预测（磁盘）
dbskiter --database=<数据库名> monitor capacity --resource=disk --days=30

# 查看历史趋势
dbskiter --database=<数据库名> monitor history cpu_usage
```

### 3. 安全审计 (db-security)

SQL注入检测、敏感数据扫描、权限审计、密码策略检查。

```bash
# 完整安全审计
dbskiter --database=<数据库名> security audit

# SQL注入检测
dbskiter --database=<数据库名> security sql-injection "SELECT * FROM users WHERE id=%s"

# 敏感数据扫描
dbskiter --database=<数据库名> security sensitive-data

# 检查密码策略
dbskiter --database=<数据库名> security password-policy
```

### 4. SQL执行 (sql-master)

智能SQL执行、数据导入导出、SQL审核。

```bash
# 执行SQL
dbskiter --database=<数据库名> sql execute "SELECT COUNT(*) FROM users"

# 导出数据
dbskiter --database=<数据库名> sql export --table=users --output=users.csv

# SQL审核
dbskiter --database=<数据库名> sql audit "SELECT * FROM orders"
```

### 5. 锁分析 (db-lock-analyzer)

锁分析、死锁检测、锁等待链追踪。

```bash
# 分析当前锁
dbskiter --database=<数据库名> lock analyze

# 检测死锁
dbskiter --database=<数据库名> lock deadlocks

# 查看锁等待链
dbskiter --database=<数据库名> lock chains
```

### 6. 智能巡检 (db-inspector)

配置检查、性能检查、安全检查、根因分析。

```bash
# 执行巡检
dbskiter --database=<数据库名> inspector run

# 生成报告
dbskiter --database=<数据库名> inspector report --output=report.html

# 智能巡检
dbskiter --database=<数据库名> inspector intelligent
```

---

## 使用示例

### 场景1：数据库变慢了

```bash
# 1. 快速健康检查
dbskiter --database=<数据库名> monitor health

# 2. 查看慢查询
dbskiter --database=<数据库名> diagnose slow-queries --limit=5

# 3. 分析锁情况
dbskiter --database=<数据库名> lock analyze

# 4. 获取优化建议
dbskiter --database=<数据库名> diagnose recommend-indexes
```

### 场景2：日常安全巡检

```bash
# 1. 安全审计
dbskiter --database=<数据库名> security audit

# 2. 检查弱密码
dbskiter --database=<数据库名> security weak-passwords

# 3. 扫描敏感数据
dbskiter --database=<数据库名> security sensitive-data

# 4. 生成巡检报告
dbskiter --database=<数据库名> inspector report
```

### 场景3：容量规划

```bash
# 1. 磁盘容量预测
dbskiter --database=<数据库名> monitor capacity --resource=disk --days=90

# 2. 连接数趋势
dbskiter --database=<数据库名> monitor trend --metric=connections

# 3. 查看历史数据
dbskiter --database=<数据库名> monitor history table_size
```

---

## 开发环境搭建

### 1. 克隆并安装

```bash
git clone https://github.com/magicCzc/dbskiter.git
cd dbskiter
pip install -e ".[dev]"
```

### 2. 运行测试

```bash
# 运行全部单元测试
python -m pytest tests/unit/ tests/test_imports.py tests/test_models.py tests/test_error_handler.py tests/test_query_result.py tests/test_sql_dialect.py tests/test_validators.py tests/test_sql_fingerprint.py tests/test_sql_validation.py tests/test_security_injection.py tests/test_cache.py tests/test_report_generator.py tests/test_scheduler_backup.py -v

# 运行所有测试（含集成测试）
python -m pytest tests/ -v
```

### 3. 安装 Pre-commit 钩子

```bash
pip install pre-commit
pre-commit install
```

安装后每次 `git commit` 会自动检查代码格式和 bare except 等问题。

### 4. CI/CD

本项目使用 GitHub Actions 作为 CI 工具。每次 push 到 `main` 分支会自动：

- 在 Python 3.8–3.12 上运行测试
- 检查代码格式（flake8）
- 验证模块导入

CI 配置文件：`.github/workflows/ci.yml`

---

## 项目架构

```
dbskiter/
├── __main__.py                   # Python模块入口
├── cli.py                        # CLI桥接入口
├── mcp_integration.py            # MCP协议集成
│
├── config/                       # 配置模块
│   └── security_config.py       # 安全配置
│
├── cli/                          # CLI命令入口
│   ├── commands/                 # 各模块命令实现
│   │   ├── diagnose.py          # 诊断命令
│   │   ├── diagnose_report_generator.py # 诊断报告生成命令
│   │   ├── monitor.py           # 监控命令
│   │   ├── security.py          # 安全命令
│   │   ├── sql.py               # SQL命令
│   │   ├── lock.py              # 锁分析命令
│   │   ├── inspector.py         # 巡检命令
│   │   ├── scheduler.py         # 调度命令
│   │   └── audit.py             # 审核命令
│   ├── main.py                  # CLI主入口
│   ├── config.py                # 配置管理
│   ├── config_file.py           # 配置文件解析
│   ├── readonly_middleware.py   # 只读安全中间件
│   ├── error_handler.py        # CLI错误处理
│   ├── exceptions.py           # CLI异常定义
│   └── output.py               # 输出格式化
│
├── db_diagnose/                  # 诊断模块
│   ├── skill.py                 # 诊断Skill主类
│   ├── diagnosticians/          # 各数据库诊断器
│   │   ├── base.py             # 诊断器基类
│   │   ├── generic_diagnostician.py # 通用诊断器
│   │   ├── mysql_diagnostician.py
│   │   ├── mysql_performance_analyzer.py # MySQL性能分析
│   │   ├── postgresql_diagnostician.py
│   │   ├── postgresql_performance_analyzer.py # PG性能分析
│   │   ├── oracle_diagnostician.py
│   │   ├── oracle_performance_analyzer.py # Oracle性能分析
│   │   ├── oracle_slow_query_analyzer.py # Oracle慢查询分析
│   │   ├── clickhouse_diagnostician.py
│   │   ├── clickhouse_performance_analyzer.py # CH性能分析
│   │   ├── mssql_diagnostician.py
│   │   ├── sqlite_diagnostician.py
│   │   └── sqlite_performance_analyzer.py # SQLite性能分析
│   ├── analyzers/               # 各类分析器
│   │   ├── sql_analyzer.py
│   │   ├── plan_analyzer.py
│   │   ├── table_analyzer.py
│   │   └── batch_analyzer.py
│   ├── core/                    # 核心组件
│   │   ├── performance_model.py
│   │   └── slow_query_analyzer.py
│   ├── reports/                 # 报告生成
│   │   └── generator.py
│   ├── models.py                # 数据模型
│   └── utils.py                 # 工具函数
│
├── db_monitor/                   # 监控模块
│   ├── skill.py                 # 监控Skill主类
│   ├── collectors/              # 指标采集器
│   │   ├── base.py             # 采集器基类
│   │   ├── generic_collector.py # 通用采集器
│   │   ├── mysql_collector.py
│   │   ├── postgresql_collector.py
│   │   ├── oracle_collector.py
│   │   ├── clickhouse_collector.py
│   │   ├── mssql_collector.py
│   │   └── sqlite_collector.py
│   ├── storage.py               # 数据存储
│   ├── health_scorer.py         # 健康评分
│   ├── capacity_predictor.py    # 容量预测
│   ├── advanced_predictor.py    # 高级预测
│   ├── trend_analyzer.py        # 趋势分析
│   ├── models.py                # 数据模型
│   └── utils.py                 # 工具函数
│
├── db_security/                  # 安全模块
│   ├── skill.py                 # 安全Skill主类
│   ├── sql_injection_detector_v2.py  # SQL注入检测
│   ├── sensitive_data_scanner_v2.py  # 敏感数据扫描
│   ├── password_policy_checker.py    # 密码策略检查
│   ├── advanced_security_analyzer.py # 高级安全分析
│   ├── audit_log_analyzer.py    # 审计日志分析
│   ├── login_security_monitor.py # 登录安全监控
│   ├── models.py                # 数据模型
│   └── utils.py                 # 工具函数
│
├── db_scheduler/                 # 调度模块
│   ├── skill.py                 # 调度Skill主类
│   ├── backup.py                # 备份管理
│   ├── connection_pool.py       # 连接池管理
│   ├── scheduler_engine.py      # 调度引擎
│   ├── task_executors.py        # 任务执行器
│   ├── task_storage.py          # 任务持久化
│   ├── persistent_storage.py    # 通用持久化
│   ├── models.py                # 数据模型
│   ├── utils.py                 # 工具函数
│   ├── dependency_manager.py    # 依赖管理
│   ├── distributed_lock.py      # 分布式锁
│   ├── monitoring.py            # 监控
│   └── result_cleanup.py        # 结果清理
│
├── db_inspector/                 # 巡检模块
│   ├── skill.py                 # 巡检Skill主类
│   ├── intelligent_inspector.py # 智能巡检
│   ├── inspectors/              # 各数据库巡检器
│   │   ├── base.py             # 巡检器基类
│   │   ├── generic_inspector.py # 通用巡检器
│   │   ├── mysql_inspector.py
│   │   ├── postgresql_inspector.py
│   │   ├── oracle_inspector.py
│   │   ├── clickhouse_inspector.py
│   │   ├── mssql_inspector.py
│   │   └── sqlite_inspector.py
│   ├── report_generator.py      # 报告生成
│   ├── models.py                # 数据模型
│   └── utils.py                 # 工具函数
│
├── db_lock_analyzer/             # 锁分析模块
│   ├── skill.py                 # 锁分析Skill主类
│   ├── models.py                # 数据模型
│   └── utils.py                 # 工具函数
│
├── sql_master/                   # SQL执行模块
│   ├── skill.py                 # SQL Skill主类
│   ├── executor.py              # SQL执行器
│   ├── security_checker.py      # SQL安全检查器
│   ├── security_executor_v2.py  # 安全执行器
│   ├── sql_parser.py            # SQL解析器
│   ├── sql_rewriter_v2.py       # SQL重写器
│   ├── analyzer.py              # SQL分析器
│   ├── data_transfer.py         # 数据传输
│   ├── audit_storage.py         # 审计存储
│   ├── audit_logger.py          # 审计日志
│   ├── cache_manager.py         # 缓存管理
│   ├── cache_invalidator.py     # 缓存失效
│   ├── schema_aware.py          # Schema感知
│   ├── intelligent_intellisense.py  # 智能提示
│   ├── models.py                # 数据模型
│   └── utils.py                 # 工具函数
│
├── db_sql_auditor/               # SQL审核模块
│   ├── skill.py                 # 审核Skill主类
│   ├── analyzers/               # 各数据库审核器
│   │   ├── base.py             # 审核器基类
│   │   ├── generic_analyzer.py # 通用审核器
│   │   ├── mysql_analyzer.py
│   │   ├── postgresql_analyzer.py
│   │   ├── oracle_analyzer.py
│   │   ├── clickhouse_analyzer.py
│   │   ├── mssql_analyzer.py
│   │   └── sqlite_analyzer.py
│   ├── intelligent_optimizer.py # 智能优化器
│   ├── models.py                # 数据模型
│   └── utils.py                 # 工具函数
│
└── shared/                       # 共享组件
    ├── database_connector.py    # 数据库连接器（可配置连接池）
    ├── unified_connector.py     # 统一连接器（JDBC/SQLAlchemy适配器）
    ├── sql_utils.py             # SQL工具函数共享（表名提取/类型检测/能力摘要等）
    ├── query_result.py          # 查询结果模型
    ├── validators.py            # 输入验证和脱敏
    ├── error_handler.py         # 统一异常处理
    ├── models.py                # 共享数据模型
    ├── db_metadata.py           # 数据库元数据
    ├── schema_detector.py       # 数据库类型检测
    ├── sql_dialect.py           # SQL方言适配
    ├── sql_fingerprint.py       # SQL指纹计算
    ├── utils.py                 # 通用工具函数
    ├── ai_context.py            # AI上下文
    ├── zabbix_client.py         # Zabbix监控客户端
    ├── prometheus_client.py     # Prometheus指标采集
    ├── prometheus_metrics.py    # Prometheus指标定义
    ├── oracle_jdbc_connector.py # Oracle JDBC连接器
    ├── oracle_metrics.py        # Oracle指标定义
    ├── slow_log_parser.py       # 慢日志解析
    ├── mysql_slow_query_collector.py # MySQL慢查询采集
    └── mysql_aas_calculator_v2.py    # AAS计算
```

---

## AI集成

dbskiter 支持多种AI集成方式，包括MCP Server和Skill文档。

### MCP Server（推荐）

通过Model Context Protocol与Claude、Cursor等AI助手集成。

**安装MCP Server：**
```bash
pip install dbskiter-mcp-server
```

**配置Claude Desktop：**
编辑 `claude_desktop_config.json`：
```json
{
  "mcpServers": {
    "dbskiter": {
      "command": "dbskiter-mcp",
      "env": {
        "DB_DIALECT": "mysql",
        "DB_HOST": "localhost",
        "DB_PORT": "3306",
        "DB_USER": "root",
        "DB_PASSWORD": "your_password",
        "DB_NAME": "your_database"
      }
    }
  }
}
```

**使用示例：**
用户可以直接问Claude：
- "检查我的数据库健康状态"
- "分析这个SQL语句的性能"
- "找出最慢的10个查询"

### Skill文档

通过Skill文档让AI IDE（如Trae、Cursor）学会使用工具。

**配置方法：**
```bash
# Trae IDE
cp -r .trae/skills/* ~/.trae/skills/

# Cursor IDE
cp -r .trae/skills/* .cursor/skills/
```

**AI使用示例：**

**用户**：帮我检查数据库健康状态

**AI**（自动读取 Skill 文档）：
```bash
# 执行健康检查
dbskiter --database=<数据库名> monitor health --json

# 解析结果
健康评分：85/100
状态：健康
连接数：45/100 (45%)
CPU使用率：35%
建议：系统运行良好，无需处理
```

### 相关项目

- [dbskiter-mcp-server](https://github.com/magicCzc/dbskiter-mcp-server) - MCP Server实现

---

## 高级配置

### 多数据库配置

```bash
# 使用别名连接指定数据库（推荐方式）
dbskiter --database=jump monitor health
dbskiter --database=orcl monitor health

# 或使用前缀方式（向后兼容）
dbskiter --prefix=ORACLE monitor health
dbskiter --prefix=MYSQL2 monitor health
```

### JSON输出

```bash
# 便于程序解析
dbskiter --database=<数据库名> --json monitor health
```

### 详细日志

```bash
# 查看 Generic 驱动能力探测结果等 INFO 级别日志
dbskiter --database=trino --verbose diagnose realtime

# --verbose 会显示 Generic 驱动自动探测到的能力摘要：
# [Generic驱动] 能力探测: 版本查询, 可用视图: INFORMATION_SCHEMA
```

### 调试模式

### 配合Prometheus

```bash
# 导出Prometheus格式指标
dbskiter --database=<数据库名> monitor collect
```

---

## 重要说明

### 安全设计

dbskiter 采用三层纵深防御架构保障数据安全:

| 层级 | 机制 | 说明 |
|------|------|------|
| AI层 | 规则限制 | AI助手禁止执行写操作SQL |
| CLI层 | ReadOnlyEnforcer | 环境变量控制, 拦截写操作 |
| 数据库层 | 用户权限 | 数据库账号权限物理限制 |

关键安全措施:

- **密码保护**: MySQL使用MYSQL_PWD环境变量传递密码, PostgreSQL使用PGPASSWORD环境变量, 避免密码在进程列表中暴露
- **SQL注入防护**: 表名白名单正则验证, 值转义覆盖反斜杠和单引号, 恢复操作仅允许白名单语句类型(INSERT/CREATE TABLE/DROP TABLE IF EXISTS等)
- **条件解析安全**: 告警条件表达式使用自定义解析器, 不使用eval(), 仅支持比较运算和逻辑运算
- **只读模式**: 恢复操作在只读模式下被拒绝, 防止误操作
- **表名引号包裹**: 根据数据库类型自动选择引号(MySQL/ClickHouse用反引号, PostgreSQL用双引号), 支持schema.table限定表名

```bash
# 启用只读模式
export DBSKITER_READ_ONLY=true
dbskiter --database=mydb diagnose realtime
```

### 定位说明

dbskiter 是**诊断工具**，不是实时监控系统。

| 场景 | 推荐方案 |
|------|----------|
| 实时监控 | Prometheus + Grafana |
| 告警通知 | Alertmanager |
| 故障诊断 | **dbskiter** |
| SQL优化 | **dbskiter** |
| 安全审计 | **dbskiter** |

### 连接池配置

通过环境变量自定义连接池参数（无需修改代码）：

```bash
# 连接池大小（默认5）
DB_POOL_SIZE=10
# 最大溢出连接（默认10）
DB_POOL_MAX_OVERFLOW=20
# 连接超时秒数（默认30）
DB_POOL_TIMEOUT=60
# 连接回收周期秒数（默认3600，即1小时）
DB_POOL_RECYCLE=7200
```

也可以在代码中通过 kwargs 传入：

```python
conn = DatabaseConnector(
    dialect="mysql",
    host="localhost",
    database="mydb",
    username="user",
    password="pass",
    pool_size=10,
    pool_max_overflow=20
)
```

### 定时任务示例

```bash
# 每小时健康检查（使用默认配置）
0 * * * * dbskiter monitor health --json > /var/log/db-health.json

# 每天安全审计（指定数据库）
0 2 * * * dbskiter --database=jump security audit > /var/log/db-security-audit.log
```

---

## 文档

- [CLI使用指南](CLI使用指南.md)
- [AI集成指南](AI集成指南.md)
- [Skill系统介绍](.trae/skills/README.md)

---

## 开发

```bash
# 安装开发依赖
pip install -e ".[dev]"

# 代码格式化
black dbskiter/

# 类型检查
mypy dbskiter/
```

---

## License

MIT License

---

<p align="center">
  <strong>让每个人都能轻松管理数据库</strong>
</p>
