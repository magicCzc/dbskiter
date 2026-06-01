---
skill:
  id: sql-master
  name: SQL智能助手
  version: "3.0.0"
  cli_min_version: "3.0.0"
  category: database_ops
  tags: [sql, execute, rewrite, analyze, mysql, oracle, postgresql]

security:
  read_only: false
  risk_level: medium
  blocked_operations:
    - DELETE
    - UPDATE
    - INSERT
    - DROP
    - TRUNCATE
    - ALTER
    - CREATE
    - REPLACE
  note: AI助手绝对禁止执行任何写操作，也不得使用--force参数

cli:
  entry_prefix: "dbskiter --output-mode=ai --database={database}"
  subcommand_group: "sql"

output:
  format: ai_envelope
  schema_version: "1.0"
---

# SQL Master Skill

## 安全声明

**风险等级**: medium

**操作性质**: 包含读写操作，AI助手仅限只读

**AI约束**: AI助手执行SQL时，仅限SELECT/EXPLAIN/SHOW/DESCRIBE操作。任何写操作（DELETE/UPDATE/INSERT/DROP等）必须拒绝执行。AI助手不得使用--force参数，该参数仅保留给人类用户在明确知情的情况下使用。

### 禁止操作清单

| 操作类型 | 危险等级 | 说明 | 示例 |
|---------|---------|------|------|
| DELETE | CRITICAL | 删除数据 | DELETE FROM users WHERE id=1 |
| UPDATE | CRITICAL | 修改数据 | UPDATE users SET name='test' |
| INSERT | CRITICAL | 插入数据 | INSERT INTO users VALUES (...) |
| DROP | CRITICAL | 删除对象 | DROP TABLE users |
| TRUNCATE | CRITICAL | 清空表 | TRUNCATE TABLE users |
| ALTER | HIGH | 修改结构 | ALTER TABLE users DROP COLUMN |
| CREATE | HIGH | 创建对象 | CREATE TABLE test (...) |
| REPLACE | HIGH | 替换数据 | REPLACE INTO users (...) |

### 允许操作清单

| 操作类型 | 说明 | 示例 |
|---------|------|------|
| SELECT | 查询数据 | SELECT * FROM users |
| EXPLAIN | 执行计划 | EXPLAIN SELECT * FROM users |
| SHOW | 显示信息 | SHOW TABLES |
| DESCRIBE | 查看结构 | DESCRIBE users |
| DESC | 查看结构 | DESC users |

## 意图映射

### intent: sql_execute

**触发语料**:
- "执行这个SQL"
- "跑一下这个SQL"
- "查询一下数据"

**对应命令**: `dbskiter --output-mode=ai --database={database} sql execute "{sql}"`

**参数**:
| 显示名称 | 变量名 | 类型 | 必需 | 默认值 | CLI参数 |
|---------|--------|------|------|--------|---------|
| SQL语句 | sql | string | 是 | - | 位置参数 |
| 返回行数限制 | limit | int | 否 | 100 | --limit |

**安全规则**:
1. 执行前必须识别SQL类型
2. 只读操作（SELECT/EXPLAIN/SHOW/DESCRIBE）可以执行
3. 写操作（DELETE/UPDATE/INSERT/DROP等）必须拒绝，返回拒绝响应模板
4. AI不得使用--force参数

### intent: sql_rewrite

**触发语料**:
- "优化这个SQL"
- "重写SQL"
- "怎么优化这条查询"

**对应命令**: `dbskiter --output-mode=ai --database={database} sql rewrite "{sql}"`

**参数**:
| 显示名称 | 变量名 | 类型 | 必需 | 默认值 | CLI参数 |
|---------|--------|------|------|--------|---------|
| SQL语句 | sql | string | 是 | - | 位置参数 |

### intent: sql_analyze

**触发语料**:
- "分析SQL质量"
- "这个SQL有问题吗"
- "SQL评分"

**对应命令**: `dbskiter --output-mode=ai --database={database} sql analyze "{sql}"`

**参数**:
| 显示名称 | 变量名 | 类型 | 必需 | 默认值 | CLI参数 |
|---------|--------|------|------|--------|---------|
| SQL语句 | sql | string | 是 | - | 位置参数 |

### intent: sql_data

**触发语料**:
- "分析数据"
- "数据统计"
- "看看数据分布"

**对应命令**: `dbskiter --output-mode=ai --database={database} sql data "{sql}"`

### intent: sql_schema

**触发语料**:
- "查看表结构"
- "Schema信息"
- "有哪些表"
- "这个表什么结构"

**对应命令**:
- 列出所有表: `dbskiter --output-mode=ai --database={database} sql schema`
- 查看表结构: `dbskiter --output-mode=ai --database={database} sql schema --table={table_name}`

### intent: sql_export

**触发语料**:
- "导出数据"
- "把数据导出来"
- "导出表"

**对应命令**: `dbskiter --output-mode=ai --database={database} sql export --table={table_name} --output={file_path}`

### intent: sql_audit

**触发语料**:
- "查看审计日志"
- "操作记录"
- "最近执行了什么SQL"

**对应命令**: `dbskiter --output-mode=ai --database={database} sql audit`

## 拒绝响应模板

当用户要求执行写操作时，使用以下模板响应：

抱歉，我无法执行 [操作类型] 操作。

原因：
根据安全策略，当前系统禁止AI助手执行任何可能修改数据的SQL操作。
这是为了防止误操作导致数据丢失。

允许的操作：
- SELECT 查询数据
- EXPLAIN 分析执行计划
- SHOW 查看数据库信息
- DESCRIBE 查看表结构

替代方案：
如果您确实需要执行写操作，请使用数据库客户端工具（如MySQL Workbench、Navicat等）直接连接数据库，并确保您有足够的权限。

## 安全控制说明

### 三层安全架构

1. AI层: SKILL.md规则约束，AI不得执行写操作
2. CLI层: ReadOnlyEnforcer中间件，环境变量DBSKITER_READ_ONLY控制
3. 数据库层: 数据库用户权限限制

### --force参数说明

--force参数是系统保留给人类用户的机制，用于在明确知情的情况下执行极高风险操作（如DROP DATABASE）。AI助手在任何情况下都不得使用此参数，也不得建议用户使用此参数。

### 风险等级

| 风险等级 | 操作类型 | 处理方式 |
|---------|---------|---------|
| CRITICAL | DROP DATABASE, DROP SCHEMA | 默认禁止，需要--force才能执行 |
| HIGH | DROP TABLE, TRUNCATE, DELETE无WHERE, UPDATE无WHERE | 允许执行但返回警告 |
| MEDIUM | DELETE带WHERE, UPDATE带WHERE | 允许执行，建议先验证影响范围 |

## AI决策流程

### 场景1: 用户要求执行SQL

步骤1: 识别SQL类型
  - 检查SQL是否为SELECT/EXPLAIN/SHOW/DESCRIBE: 继续执行
  - 检查SQL是否为DELETE/UPDATE/INSERT/DROP等写操作: 停止，返回拒绝响应模板

步骤2: 执行SQL（仅限读操作）
  dbskiter --output-mode=ai --database={database} sql execute "{sql}"

步骤3: 返回结果
  - 显示查询结果摘要
  - 说明返回行数
  - 显示执行耗时

### 场景2: 用户要求优化SQL

步骤1: 执行SQL重写
  dbskiter --output-mode=ai --database={database} sql rewrite "{sql}"

步骤2: 执行SQL质量分析
  dbskiter --output-mode=ai --database={database} sql analyze "{sql}"

步骤3: 综合回复
  - 展示重写后的SQL（如果有优化建议）
  - 说明优化点
  - 给出质量评分

### 场景3: 用户要求查看表结构

步骤1: 获取Schema信息
  dbskiter --output-mode=ai --database={database} sql schema --table={table_name}

步骤2: 展示信息
  - 表基本信息
  - 字段列表及类型
  - 索引信息

## 核心命令参考

### 执行SQL
```bash
dbskiter --output-mode=ai --database={database} sql execute "{sql}" [--limit=N]
```

### 重写SQL
```bash
dbskiter --output-mode=ai --database={database} sql rewrite "{sql}"
```

### 分析SQL质量
```bash
dbskiter --output-mode=ai --database={database} sql analyze "{sql}"
```

### 数据分析
```bash
dbskiter --output-mode=ai --database={database} sql data "{sql}"
```

### Schema查询
```bash
dbskiter --output-mode=ai --database={database} sql schema
dbskiter --output-mode=ai --database={database} sql schema --table={table_name}
```

### 数据导出
```bash
dbskiter --output-mode=ai --database={database} sql export --table={table_name} --output={file_path} [--format=csv|json|sql]
```

### 审计日志
```bash
dbskiter --output-mode=ai --database={database} sql audit [--risk-level=CRITICAL|HIGH|MEDIUM] [--hours=24]
```
