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
  - dbskiter --output-mode=ai --database=<name> audit sql "SELECT * FROM users"
  - dbskiter --output-mode=ai --database=<name> audit file queries.sql
  - dbskiter --output-mode=ai --database=<name> audit ddl "ALTER TABLE users ADD COLUMN age INT"
  - dbskiter --output-mode=ai --database=<name> audit rules
  - dbskiter --output-mode=ai --database=<name> audit optimize "SELECT * FROM users WHERE age > 18"
  - dbskiter --output-mode=ai --database=<name> audit recommend-indexes "SELECT * FROM orders WHERE user_id = 1"
---

# SQL审核 Skill

## 何时使用

当用户提到以下关键词时，使用此skill：

| 用户说法 | 执行命令 | 说明 |
|---------|---------|------|
| "审核SQL" | `dbskiter --output-mode=ai --database=<name> audit sql "<SQL>"` | 审核单条SQL |
| "检查规范" | `dbskiter --output-mode=ai --database=<name> audit sql "<SQL>"` | 检查SQL规范 |
| "DDL影响" | `dbskiter --output-mode=ai --database=<name> audit ddl "<DDL>"` | 分析DDL影响 |
| "审核文件" | `dbskiter --output-mode=ai --database=<name> audit file <path>` | 审核SQL文件 |
| "查看规则" | `dbskiter --output-mode=ai --database=<name> audit rules` | 查看审核规则 |
| "优化SQL" | `dbskiter --output-mode=ai --database=<name> audit optimize "<SQL>"` | SQL智能优化 |
| "推荐索引" | `dbskiter --output-mode=ai --database=<name> audit recommend-indexes "<SQL>"` | 索引推荐 |

## 核心命令

### 1. 审核SQL
```bash
dbskiter --database=<数据库名> audit sql "SELECT * FROM users WHERE id = 1"
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
dbskiter --database=<数据库名> audit ddl "ALTER TABLE users ADD COLUMN age INT"
```
**输出**：预估执行时间、风险点、建议

**参数**：
- `ddl_sql`（必需）：DDL语句

### 3. 审核SQL文件
```bash
dbskiter --database=<数据库名> audit file queries.sql
```
**用途**：批量审核多个SQL语句

**参数**：
- `filepath`（必需）：SQL文件路径

**可选参数**：
- `--format`：输出格式（text/json，默认text）

### 4. 查看审核规则
```bash
dbskiter --database=<数据库名> audit rules
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
