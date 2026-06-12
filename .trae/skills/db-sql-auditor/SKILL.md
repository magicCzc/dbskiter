---
name: db-sql-auditor
description: |
  SQL全生命周期审核，支持SQL规范审核、性能评估、DDL影响分析、SQL优化、索引推荐。

  使用场景：
  - 用户说"审核SQL" -> 执行 sql "<SQL>"
  - 用户说"检查规范" -> 执行 sql "<SQL>"
  - 用户说"DDL影响" -> 执行 ddl "<DDL>"
  - 用户说"查看规则" -> 执行 rules
  - 用户说"优化SQL" -> 执行 optimize "<SQL>"
  - 用户说"推荐索引" -> 执行 recommend-indexes "<SQL>"

  用法：
  - python -m dbskiter --output-mode=ai --database=<name> audit sql "SELECT * FROM users"
  - python -m dbskiter --output-mode=ai --database=<name> audit file queries.sql
  - python -m dbskiter --output-mode=ai --database=<name> audit ddl "ALTER TABLE users ADD COLUMN age INT"
  - python -m dbskiter --output-mode=ai --database=<name> audit rules
  - python -m dbskiter --output-mode=ai --database=<name> audit optimize "SELECT * FROM users WHERE age > 18"
  - python -m dbskiter --output-mode=ai --database=<name> audit recommend-indexes "SELECT * FROM orders WHERE user_id = 1"
---

# SQL审核 Skill

## 安全原则

本Skill的所有操作均为只读分析和建议，不会修改任何数据：

| 规则 | 说明 |
|------|------|
| 只读操作 | 审核命令只分析SQL语法和性能，不执行SQL |
| 禁止执行被审核的SQL | audit sql只审核，不执行被审核的SQL语句 |
| 优化建议仅供参考 | optimize只提供重写建议，不自动执行优化后的SQL |
| 索引推荐仅供参考 | recommend-indexes只提供CREATE INDEX建议，不自动执行 |
| DDL影响分析只评估 | audit ddl只评估影响，不执行DDL语句 |

## 何时使用

当用户提到以下关键词时，使用此skill：

| 用户说法 | 执行命令 | 说明 |
|---------|---------|------|
| "审核SQL" | `python -m dbskiter --output-mode=ai --database=<name> audit sql "<SQL>"` | 审核单条SQL |
| "检查规范" | `python -m dbskiter --output-mode=ai --database=<name> audit sql "<SQL>"` | 检查SQL规范 |
| "DDL影响" | `python -m dbskiter --output-mode=ai --database=<name> audit ddl "<DDL>"` | 分析DDL影响 |
| "审核文件" | `python -m dbskiter --output-mode=ai --database=<name> audit file <path>` | 审核SQL文件 |
| "查看规则" | `python -m dbskiter --output-mode=ai --database=<name> audit rules` | 查看审核规则 |
| "优化SQL" | `python -m dbskiter --output-mode=ai --database=<name> audit optimize "<SQL>"` | SQL智能优化 |
| "推荐索引" | `python -m dbskiter --output-mode=ai --database=<name> audit recommend-indexes "<SQL>"` | 索引推荐 |

## 核心命令

### 1. 审核SQL
```bash
python -m dbskiter --database=<数据库名> audit sql "SELECT * FROM users WHERE id = 1"
```
**输出**：审核评分、问题列表、修复建议

**评分标准**：
- 90-100：通过
- 80-89：警告
- <80：不通过

**可选参数**：
- `--format`：输出格式（text/json，默认text）

### 2. DDL影响分析
```bash
python -m dbskiter --database=<数据库名> audit ddl "ALTER TABLE users ADD COLUMN age INT"
```
**输出**：预估执行时间、风险点、建议

**参数**：
- `ddl_sql`（必需）：DDL语句

### 3. 审核SQL文件
```bash
python -m dbskiter --database=<数据库名> audit file queries.sql
```
**用途**：批量审核多个SQL语句

**参数**：
- `filepath`（必需）：SQL文件路径

**可选参数**：
- `--format`：输出格式（text/json，默认text）

### 4. 查看审核规则
```bash
python -m dbskiter --database=<数据库名> audit rules
```
**输出**：所有审核规则列表

**可选参数**：
- `--type`：规则类型过滤（syntax/performance/security/style/ddl）

### 5. SQL优化
```bash
dbskiter --database=<数据库名> audit optimize "SELECT * FROM users WHERE age > 18"
```
**功能**：智能优化SQL，提供重写建议、索引推荐、成本估算

**参数**：
- `sql`（必需）：要优化的SQL语句

**可选参数**：
- `--format`：输出格式（text/json，默认text）

### 6. 索引推荐
```bash
dbskiter --database=<数据库名> audit recommend-indexes "SELECT * FROM orders WHERE user_id = 1"
```
**功能**：分析SQL并推荐合适的索引

**可选参数**：
- `--format`：输出格式（text/json，默认text）

## 审核规则类型

- **syntax**：语法规范
- **performance**：性能规范
- **security**：安全规范
- **style**：代码风格
- **ddl**：DDL规范

## 数据库支持

| 数据库 | SQL审核 | DDL影响分析 | SQL优化 | 索引推荐 | 状态 |
|-------|---------|------------|---------|---------|------|
| MySQL | 支持 | 支持 | 支持 | 支持 | 生产就绪 |
| Oracle | 支持 | 支持 | 支持 | 支持 | 生产就绪 |
| PostgreSQL | 支持 | 支持 | 支持 | 支持 | 生产就绪 |
| SQL Server | 支持 | 支持 | 支持 | 支持 | 生产就绪 |
| ClickHouse | 支持 | 支持 | 支持 | 支持 | 生产就绪 |
| SQLite | 支持 | 支持 | 支持 | 支持 | 生产就绪 |
| 通用(Generic) | 支持 | 基础 | 基础 | 基础 | 可用 |

**通用 SQL 审核说明**：

通用 DDL 分析器通过标准 SQL 和 INFORMATION_SCHEMA 为任意 JDBC 兼容数据库提供基础 DDL 影响分析：
- 支持 ALTER TABLE ADD/DROP/MODIFY COLUMN、CREATE/DROP TABLE、TRUNCATE 等操作
- 通过 INFORMATION_SCHEMA 获取表大小、行数、索引、外键依赖
- 评估大表 DDL 风险、执行时间预估
- 支持的数据库：Trino、Presto、DuckDB、H2、Derby 等任何 JDBC 数据库

**ClickHouse SQL审核特性**：
- 语法规范检查：ClickHouse特有函数和语法
- 性能规范检查：避免全表扫描、推荐PREWHERE
- DDL影响分析：评估异步mutation影响、ON CLUSTER建议
- 索引推荐：基于主键和ORDER BY的查询优化
- 查询优化：提供查询重写建议，利用MergeTree引擎特性

**SQLite SQL审核特性**：
- 语法规范检查：SQLite特有语法和限制
- 性能规范检查：避免全表扫描、推荐索引
- DDL影响分析：检测有限ALTER支持、重建表风险
- 索引推荐：基于查询条件的索引建议
- 查询优化：提供查询重写建议

**SQL Server SQL审核特性**：
- 语法规范检查：TOP vs LIMIT、方括号标识符等SQL Server特有语法
- 性能规范检查：避免SELECT *、确保WHERE条件有索引支持
- 安全规范检查：防止SQL注入、敏感信息泄露
- DDL影响分析：评估ALTER TABLE、CREATE INDEX等操作的影响
- 索引推荐：基于查询条件推荐合适的索引列
- 查询优化：提供查询重写建议，提高执行效率

## AI决策流程

### 场景1：用户说"审核这个SQL"

```
步骤1：执行 dbskiter --database=<name> audit sql "<SQL>"
步骤2：解读审核评分和问题列表
步骤3：如果评分<80，详细说明问题并提供修复建议
```

### 场景2：用户说"这个DDL有什么影响"

```
步骤1：执行 dbskiter --database=<name> audit ddl "<DDL>"
步骤2：解读预估执行时间和风险点
步骤3：给出执行建议（如是否在低峰期执行）
```

### 场景3：用户说"优化这个SQL"

```
步骤1：执行 dbskiter --database=<name> audit optimize "<SQL>"
步骤2：查看优化后的SQL和成本估算
步骤3：执行 dbskiter --database=<name> audit recommend-indexes "<SQL>" 获取索引建议
步骤4：综合给出优化方案
```
