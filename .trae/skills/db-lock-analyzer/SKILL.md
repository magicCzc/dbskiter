---
name: db-lock-analyzer
description: |
  数据库锁分析与死锁检测，支持当前锁分析、死锁检测、锁等待链追踪、锁统计报告、事务终止。

  使用场景：
  - 用户说"看锁" -> 执行 analyze
  - 用户说"死锁" -> 执行 deadlocks
  - 用户说"阻塞" -> 执行 chains
  - 用户说"锁报告" -> 执行 report
  - 用户说"终止事务" -> 执行 kill <事务ID>

  用法：
  - python -m dbskiter --output-mode=ai --database=<name> lock analyze
  - python -m dbskiter --output-mode=ai --database=<name> lock deadlocks
  - python -m dbskiter --output-mode=ai --database=<name> lock chains
  - python -m dbskiter --output-mode=ai --database=<name> lock report
  - python -m dbskiter --output-mode=ai --database=<name> lock kill <transaction_id>
---

# 锁分析 Skill

## 安全原则

本Skill的大部分操作为只读查询，但kill命令除外：

| 规则 | 说明 |
|------|------|
| 只读操作 | analyze/deadlocks/chains/report命令均为只读查询 |
| kill命令需谨慎 | lock kill会终止事务，属于写操作，需用户明确确认 |
| 禁止其他写操作 | 不得通过锁分析命令执行DELETE/UPDATE/INSERT/DROP等写操作 |
| kill不自动执行 | AI不得主动建议执行kill，需用户明确要求 |

## 何时使用

当用户提到以下关键词时，使用此skill：

| 用户说法 | 执行命令 | 说明 |
|---------|---------|------|
| "看锁" | `python -m dbskiter --output-mode=ai --database=<name> lock analyze` | 分析当前锁情况 |
| "死锁" | `python -m dbskiter --output-mode=ai --database=<name> lock deadlocks` | 检测死锁 |
| "阻塞" | `python -m dbskiter --output-mode=ai --database=<name> lock chains` | 追踪锁等待链 |
| "锁报告" | `python -m dbskiter --output-mode=ai --database=<name> lock report` | 生成锁分析报告 |
| "终止事务" | `python -m dbskiter --output-mode=ai --database=<name> lock kill <id>` | 终止阻塞事务 |

## 核心命令

### 1. 分析当前锁
```bash
python -m dbskiter --database=<数据库名> lock analyze
```
**输出**：总锁数、等待中锁数、已授予锁数

**可选参数**：
- `--format`：输出格式（text/json，默认text）

### 2. 检测死锁
```bash
python -m dbskiter --database=<数据库名> lock deadlocks
```
**输出**：死锁数量、涉及事务、解决建议

**可选参数**：
- `--format`：输出格式（text/json，默认text）

### 3. 追踪锁等待链
```bash
python -m dbskiter --database=<数据库名> lock chains
```
**输出**：锁等待链数量、链深度、阻塞源头

**可选参数**：
- `--format`：输出格式（text/json，默认text）

### 4. 生成锁报告
```bash
python -m dbskiter --database=<数据库名> lock report
```
**输出**：完整的锁分析报告

**可选参数**：
- `--output`：输出文件路径

### 5. 终止事务
```bash
python -m dbskiter --database=<数据库名> lock kill <transaction_id>
```
**注意**：谨慎使用，会强制终止事务

**参数**：
- `transaction_id`（必需）：要终止的事务ID

## 锁类型

- **TABLE**：表锁
- **ROW**：行锁
- **METADATA**：元数据锁

## 数据库支持情况

| 数据库 | 锁分析 | 死锁检测 | 锁等待链 | 说明 |
|--------|--------|----------|----------|------|
| MySQL | 完整支持 | 支持 | 支持 | 需要 PROCESS 权限访问 information_schema.innodb_locks |
| PostgreSQL | 完整支持 | 支持 | 支持 | 完全可用 |
| Oracle | 完整支持 | 支持 | 支持 | 需要 SELECT ANY DICTIONARY 权限访问 v$lock、v$session |
| SQL Server | 完整支持 | 支持 | 支持 | 需要 VIEW SERVER STATE 权限访问 sys.dm_tran_locks |
| ClickHouse | 部分支持 | 不支持 | 不支持 | 通过system.processes和system.mutations查看 |
| SQLite | 基础支持 | 不支持 | 不支持 | 通过PRAGMA lock_status查看（SQLite 3.37.0+） |
| 通用(Generic) | 基础支持 | 不支持 | 不支持 | 通过多种系统视图自适应探测 |

## 通用锁分析说明

通用锁分析器为任意 JDBC 兼容数据库提供基础锁分析能力：
- 自动探测 pg_locks、innodb_trx、dm_tran_locks、system.processes 等视图
- 优先使用最详细的数据源，逐级回退
- 支持的数据库：Trino、Presto、DuckDB、H2、Derby 等任何 JDBC 数据库

## ClickHouse锁分析说明

ClickHouse使用MVCC机制，读操作不阻塞写操作：
- 锁分析：通过system.processes查看正在执行的查询，通过system.mutations查看异步DDL/DML
- 不支持传统意义上的死锁检测（无行级锁冲突）
- 锁等待链不适用（无阻塞等待机制）
- 主要关注长时间运行的查询和堆积的mutation

## SQLite锁分析说明

SQLite使用文件级锁，锁状态有限：
- 锁分析：通过PRAGMA lock_status获取锁状态（SQLite 3.37.0+）
- 不支持死锁检测（SQLite通过忙等待处理冲突）
- 锁等待链不适用
- 锁状态：UNLOCKED -> SHARED -> RESERVED -> PENDING -> EXCLUSIVE

## 权限要求

### MySQL
- 锁分析需要 `PROCESS` 权限，用于访问以下系统视图：
  - `information_schema.innodb_trx`
  - `information_schema.innodb_locks`
  - `information_schema.innodb_lock_waits`
  - `performance_schema.data_locks` (MySQL 8.0+)
  - `performance_schema.data_lock_waits` (MySQL 8.0+)
- 如果权限不足，锁分析将返回空结果，并在响应中提示权限不足

### PostgreSQL
- 需要 `pg_read_all_stats` 角色或超级用户权限
- 用于访问 `pg_locks`、`pg_stat_activity` 等系统视图

### Oracle
- 需要 `SELECT ANY DICTIONARY` 权限或单独授予以下视图查询权限：
  - `v$lock`
  - `v$session`
  - `dba_objects`
  - `v$sql`

### SQL Server
- 需要 `VIEW SERVER STATE` 权限访问以下动态管理视图：
  - `sys.dm_tran_locks` - 锁信息
  - `sys.dm_exec_sessions` - 会话信息
  - `sys.dm_exec_requests` - 请求信息
  - `sys.dm_os_waiting_tasks` - 等待任务
- 用于检测阻塞链、死锁和锁等待情况

## AI决策流程

### 场景1：用户说"看看锁情况"

```
步骤1：执行 dbskiter --database=<name> lock analyze
步骤2：查看锁统计信息
步骤3：如果有等待锁，执行 dbskiter --database=<name> lock chains 查看阻塞链
步骤4：总结锁情况给用户
```

### 场景2：用户说"有死锁吗"

```
步骤1：执行 dbskiter --database=<name> lock deadlocks
步骤2：如果有死锁，列出涉及的事务和SQL
步骤3：给出解决建议（如终止某个事务）
```

### 场景3：用户说"有阻塞"

```
步骤1：执行 dbskiter --database=<name> lock chains
步骤2：分析阻塞链，找出阻塞源头
步骤3：建议终止阻塞源头事务或优化业务逻辑
```
