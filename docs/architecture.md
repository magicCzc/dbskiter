<!--
文件功能：DBSKiter 架构详解
主要类/函数：无（架构文档）
作者：MagiCzc
创建时间：2026-07-24
最后修改：2026-07-24
-->

# DBSKiter 架构详解

本文档面向二次开发者，深入介绍 DBSKiter 的分层架构、数据流、扩展机制。

---

## 1. 整体架构

### 1.1 分层模型

```
┌─────────────────────────────────────────────────────────────┐
│                      CLI 层 (cli/)                          │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐      │
│  │ main.py  │ │ commands │ │  config  │ │  output  │      │
│  │ argparse │ │  注册    │ │  加载    │ │  格式化  │      │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘      │
└──────────────────────┬──────────────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────────────────┐
│                    Skill 层 (db_*/skill.py)                 │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐         │
│  │ diagnose│ │ monitor │ │ security│ │scheduler│  ...8个  │
│  └─────────┘ └─────────┘ └─────────┘ └─────────┘         │
└──────────────────────┬──────────────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────────────────┐
│                  共享层 (shared/)                           │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐      │
│  │  连接器      │ │ AAS 计算器   │ │ 慢查询解析器 │      │
│  │  SQLAlchemy  │ │  Prometheus  │ │  Zabbix     │      │
│  │  + JDBC      │ │  集成        │ │  集成        │      │
│  └──────────────┘ └──────────────┘ └──────────────┘      │
└──────────────────────┬──────────────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────────────────┐
│                  驱动层 (6+N 架构)                          │
│  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐  │
│  │ MySQL  │ │ Oracle │ │  PG    │ │MSSQL   │ │ CH     │  │
│  └────────┘ └────────┘ └────────┘ └────────┘ └────────┘  │
│  ┌────────┐ ┌──────────────────────────────────────┐     │
│  │SQLite  │ │ Generic（INFORMATION_SCHEMA 探测）│     │
│  └────────┘ └──────────────────────────────────────┘     │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 模块清单

| 层级 | 模块 | 职责 |
|------|------|------|
| CLI 入口 | `cli/main.py` | argparse 解析、命令分发、错误处理 |
| CLI 命令 | `cli/commands/*` | 13 个命令类（diagnose/monitor/security/...） |
| 业务能力 | `db_diagnose / db_monitor / db_security / ...` | 8 个 Skill |
| 共享组件 | `shared/` | 跨 Skill 复用的工具 |
| 数据库驱动 | `shared/database_connector.py` + `shared/unified_connector.py` | 6+N 驱动 |

---

## 2. CLI 启动流程

```
用户执行: dbskiter --database=jump diagnose slow-queries
                          ↓
                    main() 入口
                          ↓
       ┌─────────── 平台修复 ──────────┐
       │  Windows: 强制 UTF-8 编码     │
       └────────────────────────────────┘
                          ↓
       ┌────────── 命令别名展开 ────────┐
       │  health → monitor health      │
       │  slow   → diagnose slow-queries│
       └────────────────────────────────┘
                          ↓
                parser.parse_args()
                          ↓
       ┌─── 修复 argparse 子解析器覆盖 ─┐
       │  --database 子解析器覆盖主     │
       │  解析器 → 重新解析回填         │
       └────────────────────────────────┘
                          ↓
                Config.from_args()
                          ↓
       ┌─────── Config 加载优先级 ──────┐
       │  1. --url                       │
       │  2. --password-stdin/file       │
       │  3. CLI 参数                    │
       │  4. --profile                   │
       │  5. --database .env 别名        │
       │  6. .env 默认                   │
       │  7. 环境变量                    │
       │  8. 内置默认                    │
       └────────────────────────────────┘
                          ↓
                command.run()
                          ↓
       ┌─────── Skill 业务逻辑 ─────────┐
       │  DiagnoseSkill.slow_queries()  │
       └────────────────────────────────┘
                          ↓
            OutputFormatter 输出
                          ↓
       ┌─────── 三种输出模式 ───────────┐
       │  rule: 富文本（人类阅读）       │
       │  raw:  原始数据                 │
       │  ai:   JSON (AI 友好)          │
       └────────────────────────────────┘
```

### 2.1 关键设计

#### 智能默认数据库

`cli/main.py:_apply_smart_default()` 在用户未指定 `--database` 且只有一个配置时自动使用。

#### 别名展开

`cli/command_aliases.py:expand_alias()` 把 `health` 展开为 `monitor health`，减少用户记忆负担。

---

## 3. Skill 模块化

### 3.1 统一入口

每个 Skill 都提供 `skill.py` 作为统一入口：

```python
from dbskiter.db_diagnose import DiagnoseSkill
from dbskiter.db_monitor import MonitorSkill
from dbskiter.db_security import SecuritySkill
# ... 共 8 个

skill = DiagnoseSkill(connector)
result = skill.analyze_slow_queries(top=10)
```

### 3.2 8 大 Skill 职责

| Skill | 入口类 | 核心能力 |
|-------|--------|----------|
| `db_diagnose` | `DiagnoseSkill` | 慢查询、锁、空间、复制、SQL 分析、索引推荐 |
| `db_monitor` | `MonitorSkill` | 健康检查、异常检测、容量预测、趋势分析 |
| `db_security` | `SecuritySkill` | SQL 注入、敏感数据、密码策略、权限审计 |
| `db_scheduler` | `SchedulerSkill` | 备份、定时任务、连接池、分布式锁 |
| `db_inspector` | `InspectorSkill` | 综合巡检、HTML 报告、基线对比 |
| `db_lock_analyzer` | `LockAnalyzerSkill` | 锁分析、死锁检测、等待链 |
| `sql_master` | `SQLMasterSkill` | SQL 执行、审核、重写、缓存 |
| `db_sql_auditor` | `SQLAuditorSkill` | SQL 审核、DDL 影响、优化建议 |

### 3.3 内部结构

以 `db_diagnose` 为例：

```
dbskiter/db_diagnose/
├── skill.py                # 统一入口
├── models.py               # 数据模型
├── utils.py                # 工具函数
├── analyzers/              # 分析器
│   ├── table_analyzer.py
│   ├── sql_analyzer.py
│   └── batch_analyzer.py
├── core/                   # 核心组件
│   └── performance_model.py
├── diagnosticians/         # 多数据库诊断策略
│   ├── base.py
│   ├── mysql_diagnostician.py
│   ├── oracle_diagnostician.py
│   ├── postgresql_diagnostician.py
│   ├── mssql_diagnostician.py
│   ├── clickhouse_diagnostician.py
│   ├── sqlite_diagnostician.py
│   └── generic_diagnostician.py
├── mysql/                  # MySQL 特有
├── reports/                # 报告生成
└── reports/generator.py
```

---

## 4. 6+N 双层驱动架构

### 4.1 核心思想

DBSKiter 支持 **7 种深度优化数据库** + **任意 JDBC 数据库**（长尾库）。对于长尾库（Trino/DuckDB/Derby/H2 等），通过 Generic 驱动自动降级到基础能力，而不是报错。

### 4.2 驱动清单

| 驱动 | 数据库 | 深度支持 |
|------|--------|----------|
| MySQL | MySQL/MariaDB | AAS、慢查询日志、performance_schema |
| Oracle | Oracle | 字典视图、AWR、JDBC |
| PostgreSQL | PostgreSQL | pg_stat、VACUUM、复制槽 |
| MSSQL | SQL Server | DMV、扩展事件、ODBC |
| ClickHouse | ClickHouse | system 表、QueryLog |
| SQLite | SQLite | 嵌入式、文件级备份 |
| Generic | 任意 JDBC | INFORMATION_SCHEMA 探测 |

### 4.3 Generic 驱动实现

```python
# dbskiter/shared/database_connector.py
def detect_capabilities(connector):
    """根据数据库类型自动探测支持的能力"""
    dialect = connector.dialect
    if dialect in ('mysql', 'mariadb'):
        return MySQLCapabilities()
    elif dialect == 'postgresql':
        return PostgreSQLCapabilities()
    else:
        return GenericCapabilities()  # 通用驱动
```

GenericCapabilities 实现的子集：
- ✅ 基础指标（连接数、表数、索引数、DB 大小）
- ✅ 慢查询（基于 INFORMATION_SCHEMA + QueryLog）
- ✅ 锁等待（pg_locks / sys.dm_tran_locks / v$lock）
- ❌ AAS（仅 MySQL/Oracle 深度支持）
- ❌ 备份/恢复（按数据库分别实现）

### 4.4 优雅降级

```python
def get_aas(self):
    if not self._has_aas_support():
        return {
            "supported": False,
            "reason": f"AAS 仅支持 MySQL/Oracle，当前数据库: {self.dialect}",
            "fallback": "请使用 monitor health 查看通用指标"
        }
    return self._calculate_aas()
```

---

## 5. AI 集成架构

### 5.1 核心理念

DBSKiter 把所有命令的输出统一为 **AIEnvelope** 格式，供 AI 助手（Claude/Cursor/Trae）解析。

### 5.2 AIEnvelope 结构

```json
{
  "schema_version": "1.0",
  "collected_at": "2026-07-24T10:30:00+08:00",
  "instance_id": "mysql-prod-01",
  "data_source": {
    "type": "direct",
    "dialect": "mysql",
    "version": "8.0.32"
  },
  "data": {
    "raw_metrics": {},   // 原始指标
    "rule_flags": {},    // 规则标记
    "context": {},       // 业务上下文
    "reference_values": {}, // 参考值
    "ai_hints": {}       // AI 提示
  }
}
```

### 5.3 三种输出模式

| 模式 | 参数 | 格式 | 适用场景 |
|------|------|------|----------|
| `rule` | `--output-mode=rule`（默认） | 富文本 + 表格 | 人类阅读 |
| `raw` | `--output-mode=raw` | 原始数据 | 脚本处理 |
| `ai` | `--output-mode=ai` | AIEnvelope JSON | AI 分析 |

### 5.4 MCP 集成

[MCP Server](https://github.com/magicCzc/dbskiter-mcp-server) 把 DBSKiter 暴露为 MCP 工具，让 Claude Desktop 直接调用：

```json
{
  "mcpServers": {
    "dbskiter": {
      "command": "dbskiter-mcp",
      "env": { "DB_HOST": "localhost" }
    }
  }
}
```

---

## 6. 安全模型

### 6.1 三层纵深防御

```
┌────────────────────────────────────────┐
│  L1: AI 层规则                          │
│  - AI 只能调只读命令                    │
│  - AI 写操作被规则引擎拦截              │
└────────────────────────────────────────┘
                 ↓
┌────────────────────────────────────────┐
│  L2: CLI 层中间件                       │
│  - ReadOnlyEnforcer 拦截写命令         │
│  - 由 DBSKITER_READ_ONLY 控制          │
└────────────────────────────────────────┘
                 ↓
┌────────────────────────────────────────┐
│  L3: 数据库层物理权限                   │
│  - 数据库账号只授予 SELECT              │
│  - 物理上无法执行写操作                  │
└────────────────────────────────────────┘
```

### 6.2 凭证安全

- 密码走 `MYSQL_PWD` / `PGPASSWORD` 环境变量（不进 `ps` 命令）
- 支持 `--password-file` / `--password-stdin`（避免 shell 历史）
- `--url` 中密码会进 shell 历史，**不推荐生产环境使用**

### 6.3 SQL 注入防护

```python
# dbskiter/db_security/sql_injection_detector.py
- AST 解析（sqlparse）识别注入模式
- 表名白名单
- 参数化查询强制
- 值转义
```

---

## 7. 扩展机制

### 7.1 添加新 Skill

```python
# dbskiter/db_myskill/skill.py
from dbskiter.shared.database_connector import DatabaseConnector

class MySkill:
    def __init__(self, connector: DatabaseConnector):
        self.connector = connector
    
    def my_action(self) -> dict:
        # 实现你的业务逻辑
        return {"result": "ok"}

# dbskiter/db_myskill/__init__.py
from .skill import MySkill
__all__ = ["MySkill"]
```

注册到 CLI：

```python
# dbskiter/cli/commands/myskill.py
from .base import BaseCommand

class MySkillCommand(BaseCommand):
    name = "myskill"
    description = "My new skill"
    
    def add_arguments(self, parser):
        sub = parser.add_subparsers(dest="action")
        sub.add_parser("my-action")
    
    def run(self):
        from dbskiter.db_myskill import MySkill
        skill = MySkill(self.config.get_connector())
        return skill.my_action()

# dbskiter/cli/commands/__init__.py
from .myskill import MySkillCommand
__all__ = [..., "MySkillCommand"]
```

### 7.2 添加新数据库驱动

```python
# dbskiter/shared/database_connector.py
def detect_capabilities(dialect: str):
    if dialect == 'mydb':
        return MyDBCapabilities()
    # ...

# dbskiter/db_diagnose/diagnosticians/mydb_diagnostician.py
from .base import BaseDiagnostician

class MyDBDiagnostician(BaseDiagnostician):
    def get_metrics(self):
        return self._query("SELECT ...")
```

### 7.3 添加新命令别名

```python
# dbskiter/cli/command_aliases.py
ALIASES = {
    "health": ["monitor", "health"],
    "top": ["diagnose", "top"],
    "myshortcut": ["myskill", "my-action"],
    # ...
}
```

---

## 8. 性能优化

### 8.1 启动时间

CLI 启动目标 < 200ms。优化策略：
- **懒加载**：Skill 模块按需 import
- **避免循环 import**：使用 TYPE_CHECKING

### 8.2 慢查询解析

`shared/sql_fingerprint.py` 提供 SQL 指纹能力，10K QPS 解析速度。

### 8.3 连接池

`db_scheduler/connection_pool.py` 提供线程安全的连接池：

```python
from dbskiter.db_scheduler.connection_pool import ConnectionPool

pool = ConnectionPool(max_size=10)
conn = pool.get_connection("mysql_prod")
try:
    cursor = conn.cursor()
    cursor.execute("SELECT 1")
finally:
    pool.release(conn)
```

### 8.4 缓存

- `sql_master/cache_manager.py`：SQL 结果缓存
- `db_inspector/cache.py`：巡检结果缓存
- 缓存失效：`cache_invalidator.py` 提供主动失效机制

---

## 9. 测试架构

### 9.1 测试金字塔

```
        ┌──────────┐
        │   E2E    │   端到端（CLI 真实调用）
        ├──────────┤
        │  集成测试 │   集成（多模块协作 + Docker DB）
        ├──────────┤
        │          │
        │  单元测试 │   单元（独立函数/类）
        │          │
        └──────────┘
```

### 9.2 测试分类

| 目录 | 类型 | 运行方式 |
|------|------|----------|
| `tests/test_*.py` | 单元测试 | `pytest` |
| `tests/integration/` | 集成测试（需 Docker） | `pytest -m integration` |
| `tests/test_benchmarks.py` | 性能基准 | `pytest -m benchmark` |

### 9.3 Mock 支持

`shared/mock_connector.py` 提供 Mock 连接器，配合 `--demo` 模式让用户无需数据库即可试用。

---

## 10. 部署与发布

### 10.1 PyPI 发布

```yaml
# .github/workflows/ci.yml
publish:
  runs-on: ubuntu-latest
  steps:
    - name: Build
      run: python -m build
    - name: Publish to PyPI
      uses: pypa/gh-action-pypi-publish@release/v1
      with:
        password: ${{ secrets.PYPI_API_TOKEN }}
```

### 10.2 Docker 镜像

```dockerfile
# Dockerfile
FROM python:3.11-slim
# ... 见 Dockerfile
```

```bash
docker build -t dbskiter:latest .
docker run --rm dbskiter --help
```

### 10.3 文档站

MkDocs + Material 主题，部署到 GitHub Pages：

```bash
mkdocs serve  # 本地预览
mkdocs gh-deploy  # 部署
```

---

## 11. 未来演进

### 11.1 路线图

- **2026 Q3**：Web UI MVP（FastAPI + Vue 3）
- **2026 Q4**：完整 API 文档、英文文档
- **2027 Q1**：插件市场、第三方 Skill 接入

### 11.2 架构债

- `db_diagnose/skill.py` 单文件 5,052 行（计划拆分）
- V2 模块待 v4.0 移除
- 测试覆盖率从 27% 提升到 50%

详见 [优化计划](https://github.com/magicCzc/dbskiter#-优化计划)。

---

## 12. 参考资料

- 📖 [README](https://github.com/magicCzc/dbskiter)
- 🔧 [CLI 使用指南](guides/CLI使用指南.md)
- 🤖 [AI 集成指南](guides/AI集成指南.md)
- ⚙️ [配置文档](configuration.md)
- 💻 [贡献指南](https://github.com/magicCzc/dbskiter/blob/main/CONTRIBUTING.md)

---

**最后更新**：2026-07-24
