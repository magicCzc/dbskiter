---
name: sql-master
description: |
  SQL智能助手，支持SQL执行、重写优化、质量分析、数据分析、智能补全、Schema查询、批量执行、数据导入导出、审计日志查询。

  使用场景：
  - 用户说"执行这个SQL" -> 执行 execute 或直接 dbskiter sql "SELECT..."
  - 用户说"优化这个SQL" -> 执行 rewrite
  - 用户说"分析SQL质量" -> 执行 analyze
  - 用户说"分析数据" -> 执行 data
  - 用户说"SQL补全" -> 执行 complete
  - 用户说"查看表结构" -> 执行 schema
  - 用户说"批量执行SQL文件" -> 执行 batch
  - 用户说"导出数据" -> 执行 export
  - 用户说"导入数据" -> 执行 import
  - 用户说"查看审计日志" -> 执行 audit

  用法：
  - dbskiter --output-mode=ai --database=<name> sql "SELECT * FROM users"
  - dbskiter --output-mode=ai --database=<name> sql execute "SELECT * FROM users"
  - dbskiter --output-mode=ai --database=<name> sql rewrite "SELECT * FROM users WHERE id = 1"
  - dbskiter --output-mode=ai --database=<name> sql analyze "SELECT * FROM orders"
  - dbskiter --output-mode=ai --database=<name> sql data "SELECT * FROM sales"
  - dbskiter --output-mode=ai --database=<name> sql complete "SELECT * FROM "
  - dbskiter --output-mode=ai --database=<name> sql schema --table=users
  - dbskiter --output-mode=ai --database=<name> sql batch queries.sql
  - dbskiter --output-mode=ai --database=<name> sql export --table=users --output=users.csv
  - dbskiter --output-mode=ai --database=<name> sql import data.csv --table=users
  - dbskiter --output-mode=ai --database=<name> sql audit
---

# SQL Master Skill

## 目标

帮助用户执行SQL、优化SQL、分析SQL质量、理解数据结构。

## 何时使用

当用户提到以下关键词时使用此skill：

| 用户说法 | 执行命令 | 说明 |
|---------|---------|------|
| "执行SQL" / "跑一下这个SQL" | `dbskiter --output-mode=ai --database=<name> sql "<SQL>"` 或 `dbskiter --output-mode=ai --database=<name> sql execute "<SQL>"` | 执行SQL语句 |
| "优化SQL" / "重写SQL" | `dbskiter --output-mode=ai --database=<name> sql rewrite "<SQL>"` | 重写SQL优化性能 |
| "分析SQL" / "SQL质量" | `dbskiter --output-mode=ai --database=<name> sql analyze "<SQL>"` | 分析SQL质量评分 |
| "分析数据" / "数据统计" | `dbskiter --output-mode=ai --database=<name> sql data "<SQL>"` | 分析查询结果数据特征 |
| "SQL补全" / "自动完成" | `dbskiter --output-mode=ai --database=<name> sql complete "<部分SQL>"` | 智能补全建议 |
| "表结构" / "Schema" | `dbskiter --output-mode=ai --database=<name> sql schema --table=<表名>` | 查看表结构 |
| "有哪些表" | `dbskiter --output-mode=ai --database=<name> sql schema` | 列出所有表 |
| "批量执行SQL文件" | `dbskiter --output-mode=ai --database=<name> sql batch <文件>` | 批量执行文件中的SQL |
| "导出数据" | `dbskiter --output-mode=ai --database=<name> sql export --table=<表名> --output=<文件>` | 导出表数据 |
| "导入数据" | `dbskiter --output-mode=ai --database=<name> sql import <文件> --table=<表名>` | 导入数据到表 |
| "流式导出" | `dbskiter --output-mode=ai --database=<name> sql export-stream --table=<表名> --output=<文件>` | 流式导出大表 |
| "查看审计日志" | `dbskiter --output-mode=ai --database=<name> sql audit` | 查询SQL审计日志 |

## 核心命令

### 1. 执行SQL
```bash
dbskiter --output-mode=ai --database=<数据库名> sql execute "<SQL语句>"
```
**参数**：
- `--params`：SQL参数（JSON格式）
- `--limit`：限制返回行数（默认100）
- `--read-only`：只读模式，禁止执行写操作
- `--force`：强制执行危险操作

**示例**：
```bash
# 基础查询
dbskiter --output-mode=ai --database=prod sql execute "SELECT * FROM users LIMIT 10"

# 带参数
dbskiter --output-mode=ai --database=prod sql execute "SELECT * FROM users WHERE age > %(age)s" --params='{"age": 18}'

# 限制返回行数
dbskiter --output-mode=ai --database=prod sql execute "SELECT * FROM orders" --limit=50
```

### 2. 重写SQL优化
```bash
dbskiter --output-mode=ai --database=<数据库名> sql rewrite "<SQL语句>"
```
**功能**：
- 展开 `SELECT *` 为具体字段
- 优化 WHERE 条件
- 推荐索引
- 重写低效JOIN

**示例**：
```bash
# 优化SELECT *
dbskiter --output-mode=ai --database=prod sql rewrite "SELECT * FROM users WHERE id = 1"

# 优化复杂查询
dbskiter --output-mode=ai --database=prod sql rewrite "SELECT * FROM orders o JOIN users u ON o.user_id = u.id WHERE u.status = 'active'"
```

### 3. 分析SQL质量
```bash
dbskiter --output-mode=ai --database=<数据库名> sql analyze "<SQL语句>"
```
**输出**：
- 质量评分（0-100分）
- 等级（A/B/C/D/F）
- 问题列表
- 优化建议

**评分标准**：
- 90-100分：A级（优秀）
- 80-89分：B级（良好）
- 70-79分：C级（一般）
- 60-69分：D级（较差）
- <60分：F级（危险）

**示例**：
```bash
dbskiter --output-mode=ai --database=prod sql analyze "SELECT * FROM users WHERE email = 'test@test.com'"
```

### 4. 数据分析
```bash
dbskiter --output-mode=ai --database=<数据库名> sql data "<查询SQL>"
```
**功能**：分析查询结果的数据特征
- 每列的数据类型
- 空值数量
- 唯一值数量
- 数值列的统计（最小/最大/平均值）
- 示例值

**示例**：
```bash
# 分析订单数据
dbskiter --output-mode=ai --database=prod sql data "SELECT * FROM orders WHERE created_at > '2024-01-01'"

# 分析用户数据
dbskiter --output-mode=ai --database=prod sql data "SELECT age, city, status FROM users"
```

### 5. SQL智能补全
```bash
dbskiter --output-mode=ai --database=<数据库名> sql complete "<部分SQL>"
```
**功能**：根据部分SQL提供补全建议
- 表名补全
- 字段名补全
- SQL关键字补全
- 函数补全

**示例**：
```bash
# 补全表名
dbskiter --output-mode=ai --database=prod sql complete "SELECT * FROM "

# 补全字段
dbskiter --output-mode=ai --database=prod sql complete "SELECT id, name, "

# 补全WHERE条件
dbskiter --output-mode=ai --database=prod sql complete "SELECT * FROM users WHERE "
```

### 6. Schema查询
```bash
# 列出所有表
dbskiter --output-mode=ai --database=<数据库名> sql schema

# 查看指定表结构
dbskiter --output-mode=ai --database=<数据库名> sql schema --table=<表名>
```
**输出**：
- 所有表名列表
- 表字段详情（名称、类型、是否可空、默认值）
- 索引信息

**示例**：
```bash
# 列出所有表
dbskiter --output-mode=ai --database=prod sql schema

# 查看users表结构
dbskiter --output-mode=ai --database=prod sql schema --table=users
```

### 7. 导出数据
```bash
# 导出表数据
dbskiter --output-mode=ai --database=<数据库名> sql export --table=<表名> --output=<文件路径> --format=<格式>

# 导出查询结果
dbskiter --output-mode=ai --database=<数据库名> sql export --query="<SQL>" --output=<文件路径> --format=<格式>
```
**参数**：
- `--table`：表名（与--query二选一）
- `--query`：SQL查询语句（与--table二选一）
- `--output, -o`：输出文件路径（必需）
- `--format, -f`：导出格式（csv/json/sql/excel，默认csv）
- `--where`：WHERE条件（仅table模式）
- `--limit`：限制导出行数

**示例**：
```bash
# 导出users表为CSV
dbskiter --output-mode=ai --database=prod sql export --table=users --output=users.csv

# 导出为JSON格式
dbskiter --output-mode=ai --database=prod sql export --table=users --output=users.json --format=json

# 导出查询结果
dbskiter --output-mode=ai --database=prod sql export --query="SELECT * FROM orders WHERE status='pending'" --output=pending_orders.csv
```

### 8. 导入数据
```bash
dbskiter --output-mode=ai --database=<数据库名> sql import <文件路径> --table=<表名> --format=<格式>
```
**参数**：
- `--table, -t`：目标表名（必需）
- `--format, -f`：文件格式（csv/json/sql，默认csv）
- `--columns`：指定列名（逗号分隔，CSV格式用）
- `--batch-size`：批量插入大小（默认1000）

**示例**：
```bash
# 从CSV导入
dbskiter --output-mode=ai --database=prod sql import users.csv --table=users

# 从JSON导入
dbskiter --output-mode=ai --database=prod sql import users.json --table=users --format=json

# 指定列名导入
dbskiter --output-mode=ai --database=prod sql import data.csv --table=users --columns=id,name,email
```

### 9. 批量执行SQL文件
```bash
dbskiter --output-mode=ai --database=<数据库名> sql batch <文件路径>
```
**功能**：批量执行文件中的SQL语句

**示例**：
```bash
dbskiter --output-mode=ai --database=prod sql batch queries.sql
```

### 10. 流式导出大表
```bash
dbskiter --output-mode=ai --database=<数据库名> sql export-stream --table=<表名> --output=<文件路径>
```
**功能**：流式导出大表数据，避免内存溢出

**参数**：
- `--table`（必需）：表名
- `--output, -o`（必需）：输出文件路径
- `--format, -f`：导出格式（csv/sql，默认csv）
- `--where`：WHERE条件
- `--batch-size`：每批导出的行数（默认10000）

### 11. 审计日志查询
```bash
dbskiter --output-mode=ai --database=<数据库名> sql audit
```
**功能**：查询SQL审计日志

**可选参数**：
- `--risk-level`：风险等级筛选（CRITICAL/HIGH/MEDIUM/SAFE）
- `--hours`：最近多少小时（默认24）
- `--limit`：返回数量限制（默认50）
- `--stats`：显示统计信息
- `--cleanup`：清理多少天前的记录

## 安全控制

sql-master提供完善的安全控制机制，防止误操作导致数据丢失。

### 风险等级定义

| 风险等级 | 操作类型 | 处理方式 |
|---------|---------|---------|
| CRITICAL | DROP DATABASE, DROP SCHEMA | 默认禁止，必须使用 `--force` 才能执行 |
| HIGH | DROP TABLE, TRUNCATE, DELETE无WHERE, UPDATE无WHERE | 允许执行但返回警告，建议使用 `--force` |
| MEDIUM | DELETE带WHERE, UPDATE带WHERE, ALTER DROP COLUMN | 允许执行，建议先验证影响范围 |
| SAFE | SELECT, INSERT, CREATE等 | 正常执行 |

### 只读模式

使用 `--read-only` 参数开启只读模式，禁止任何写操作：

```bash
# 只读模式下只能执行SELECT
dbskiter --output-mode=ai --database=prod sql execute "SELECT * FROM users" --read-only

# 写操作会被拒绝
dbskiter --output-mode=ai --database=prod sql execute "DELETE FROM users WHERE id=1" --read-only
```

### 强制执行危险操作

对于CRITICAL级别的操作，必须使用 `--force` 参数：

```bash
# 使用--force强制执行
dbskiter --output-mode=ai --database=prod sql execute "DROP DATABASE testdb" --force
```

## AI决策流程

### 场景1：用户说"执行这个SQL"

```
步骤1：提取用户提供的SQL
步骤2：执行 dbskiter --output-mode=ai --database=<name> sql execute "<SQL>"
步骤3：展示结果（最多50行）
步骤4：告知总行数和耗时
```

### 场景2：用户说"优化这个SQL"

```
步骤1：提取用户提供的SQL
步骤2：执行 dbskiter --output-mode=ai --database=<name> sql rewrite "<SQL>"
步骤3：展示优化后的SQL和解释
步骤4：如果质量评分<80，建议进一步优化
```

### 场景3：用户说"查看表结构"

```
步骤1：提取表名
步骤2：执行 dbskiter --output-mode=ai --database=<name> sql schema --table=<表名>
步骤3：展示表结构和索引信息
```
