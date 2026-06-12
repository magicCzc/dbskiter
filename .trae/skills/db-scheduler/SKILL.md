---
name: db-scheduler
description: |
  数据库调度工具，支持备份、定时任务管理、任务执行日志、调度器守护进程、DAG工作流、备份验证、备份恢复。

  使用场景：
  - 用户说"备份数据库" -> 执行 backup
  - 用户说"验证备份" -> 执行 backup-verify
  - 用户说"恢复备份" -> 执行 backup-restore
  - 用户说"定时任务" -> 执行 task
  - 用户说"查看任务日志" -> 执行 logs
  - 用户说"启动调度器" -> 执行 daemon start
  - 用户说"创建工作流" -> 执行 workflow

  用法：
  - python -m dbskiter --output-mode=ai --database=<name> scheduler backup --type=full
  - python -m dbskiter --output-mode=ai --database=<name> scheduler backup-verify <file>
  - python -m dbskiter --output-mode=ai --database=<name> scheduler backup-restore <file>
  - python -m dbskiter --output-mode=ai --database=<name> scheduler task list
  - python -m dbskiter --output-mode=ai --database=<name> scheduler task add daily_backup "0 2 * * *"
  - python -m dbskiter --output-mode=ai --database=<name> scheduler logs
  - python -m dbskiter --output-mode=ai --database=<name> scheduler daemon start
---

# 数据库调度 Skill

## 安全原则

本Skill包含写操作，需特别注意安全：

| 规则 | 说明 |
|------|------|
| 备份操作只读源数据 | backup命令只读取数据库并导出，不修改源数据 |
| 恢复操作是写操作 | restore会向数据库写入数据，需用户明确确认 |
| 任务管理是元数据操作 | task add/remove/enable/disable操作调度器元数据，不直接操作业务数据 |
| 工作流需谨慎 | workflow submit会执行工作流中的任务，需确认任务内容 |
| kill命令需谨慎 | 终止事务属于写操作，需用户明确确认 |
| 禁止危险SQL | 不得通过调度器执行DELETE/DROP等危险操作 |

## 何时使用

当用户提到以下关键词时，使用此skill：

| 用户说法 | 执行命令 | 说明 |
|---------|---------|------|
| "备份数据库" | `python -m dbskiter --output-mode=ai --database=<name> scheduler backup` | 执行备份 |
| "验证备份" | `python -m dbskiter --output-mode=ai --database=<name> scheduler backup-verify <file>` | 验证备份完整性 |
| "恢复数据库" | `python -m dbskiter --output-mode=ai --database=<name> scheduler backup-restore <file>` | 从备份恢复 |
| "定时任务" | `python -m dbskiter --output-mode=ai --database=<name> scheduler task` | 管理定时任务 |
| "任务日志" | `python -m dbskiter --output-mode=ai --database=<name> scheduler logs` | 查看执行记录 |
| "启动调度器" | `python -m dbskiter --output-mode=ai --database=<name> scheduler daemon start` | 启动自动执行 |
| "停止调度器" | `python -m dbskiter --output-mode=ai --database=<name> scheduler daemon stop` | 停止自动执行 |
| "调度器状态" | `python -m dbskiter --output-mode=ai --database=<name> scheduler daemon status` | 查看运行状态 |
| "创建工作流" | `python -m dbskiter --output-mode=ai --database=<name> scheduler workflow` | 管理DAG工作流 |

## 核心命令

### 1. 备份数据库

```bash
python -m dbskiter --database=<数据库名> scheduler backup --type=full
```

**功能**：执行数据库备份。优先使用原生工具(mysqldump/pg_dump)，不可用时分页降级。

**可选参数**：
- `--type`：备份类型（full/table，默认full）
- `--compress`：gzip压缩备份
- `--tables`：指定表（逗号分隔，仅table类型）
- `--output-dir`：输出目录

**数据库支持**：

| 数据库 | 全量备份 | 单表备份 | 恢复 | 原生工具 | 说明 |
|--------|---------|---------|------|---------|------|
| MySQL | 支持 | 支持 | 支持 | mysqldump | 生产就绪 |
| PostgreSQL | 支持 | 支持 | 支持 | pg_dump | 生产就绪 |
| SQLite | 支持 | 支持 | 支持 | 文件复制 | 生产就绪 |
| ClickHouse | 支持 | 支持 | 支持 | Python分页 | 生产就绪 |
| 通用(Generic) | 支持 | 支持 | 支持 | Python分页 | 可用 |

**通用备份说明**：
- 为任意 JDBC 兼容数据库提供基础备份/恢复能力（Trino/DuckDB/H2/Derby 等）
- 使用 LIMIT/OFFSET 分页查询导出 INSERT 语句格式的 SQL 文件
- 通过 INFORMATION_SCHEMA 或 DESCRIBE 获取表结构生成 CREATE TABLE 语句
- 恢复时逐行解析 SQL 文件并执行
- 备份文件包含方言标识和兼容性说明

**ClickHouse备份说明**：
- 使用Python分页导出INSERT语句（ClickHouse原生备份工具需单独安装）
- 支持SHOW CREATE TABLE导出表结构
- 恢复时逐语句执行，ClickHouse不支持事务回滚
- 大数据量建议使用clickhouse-backup工具

**SQLite备份说明**：
- 文件数据库直接复制.db文件
- 内存数据库(:memory:)使用SQL导出
- 支持单表SQL导出

**备份特性**：
- 自动SHA256校验：备份完成后生成 .sha256 校验文件
- 原生工具优先：自动检测并使用 mysqldump/pg_dump，性能最优
- 分页降级：原生工具不可用时使用 LIMIT/OFFSET 分批导出，避免OOM

### 2. 备份验证

```bash
python -m dbskiter --database=<数据库名> scheduler backup-verify <备份文件路径>
```

**功能**：验证备份文件完整性，比对SHA256校验值。

### 3. 备份恢复

```bash
python -m dbskiter --database=<数据库名> scheduler backup-restore <备份文件路径>
```

**警告**：恢复操作会覆盖目标数据库中的现有数据。生产环境执行前请确认。

**功能**：从备份文件恢复数据库。优先使用原生客户端工具(mysql/psql)。

### 4. 定时任务管理

#### 列出所有任务
```bash
python -m dbskiter --database=<数据库名> scheduler task list
```

#### 添加任务
```bash
python -m dbskiter --database=<数据库名> scheduler task add daily_backup "0 2 * * *" --type=backup
```

**参数**：
- `name`（必需）：任务名称
- `schedule`（必需）：Cron表达式

**可选参数**：
- `--type`：任务类型（backup/analyze/vacuum/custom，默认backup）
- `--params`：任务参数（JSON格式）
- `--enabled`：立即启用（默认true）

#### 删除任务
```bash
python -m dbskiter --database=<数据库名> scheduler task remove <任务名称>
```

#### 启用/禁用任务
```bash
python -m dbskiter --database=<数据库名> scheduler task enable <任务名称>
python -m dbskiter --database=<数据库名> scheduler task disable <任务名称>
```

#### 立即执行任务
```bash
dbskiter --database=<数据库名> scheduler task run <任务名称>
```

**Cron表达式格式**：`分 时 日 月 周`

| 表达式 | 含义 |
|--------|------|
| `0 2 * * *` | 每天凌晨2点 |
| `0 */6 * * *` | 每6小时 |
| `0 0 * * 0` | 每周日 |

**调度器特性**：
- 任务自动持久化到 SQLite，重启后自动恢复
- 过期任务（如系统停机期间错过执行的任务）不会补执行，而是重新计算下次执行时间
- 调度精度为分钟级，每30秒检查一次任务队列
- 调度循环不持有锁执行耗时任务，避免阻塞其他操作

### 5. 查看任务日志
```bash
dbskiter --database=<数据库名> scheduler logs
```

**功能**：查看任务执行日志

**可选参数**：
- `--task`：指定任务名称
- `--limit`：返回记录数（默认20）
- `--status`：过滤状态（success/failed/all，默认all）

### 6. 调度器守护进程管理

#### 启动调度器
```bash
dbskiter --database=<数据库名> scheduler daemon start
```

#### 停止调度器
```bash
dbskiter --database=<数据库名> scheduler daemon stop
```

#### 查看调度器状态
```bash
dbskiter --database=<数据库名> scheduler daemon status
```

### 7. DAG工作流管理

#### 创建工作流
```bash
dbskiter --database=<数据库名> scheduler workflow create <工作流名称>
```

**可选参数**：
- `--desc`：工作流描述

#### 添加任务到工作流
```bash
dbskiter --database=<数据库名> scheduler workflow add-task <工作流名称> <任务名称>
```

**可选参数**：
- `--type`：任务类型
- `--depends`：依赖任务（逗号分隔）

#### 提交执行工作流
```bash
dbskiter --database=<数据库名> scheduler workflow submit <工作流名称>
```

#### 列出所有工作流
```bash
dbskiter --database=<数据库名> scheduler workflow list
```

#### 查看工作流状态
```bash
dbskiter --database=<数据库名> scheduler workflow status <工作流名称>
```

## AI决策流程

### 场景1：用户说"备份数据库"

```
步骤1：执行 dbskiter --database=<name> scheduler backup --type=full
步骤2：等待备份完成
步骤3：报告备份结果（文件路径、大小、耗时）
步骤4：建议验证备份：dbskiter --database=<name> scheduler backup-verify <文件路径>
```

### 场景2：用户说"验证备份文件"

```
步骤1：执行 dbskiter --database=<name> scheduler backup-verify <备份文件路径>
步骤2：报告验证结果（校验值是否匹配）
```

### 场景3：用户说"恢复数据库"

```
步骤1：确认用户意图，警告恢复会覆盖数据
步骤2：执行 dbskiter --database=<name> scheduler backup-restore <备份文件路径>
步骤3：报告恢复结果
```

### 场景4：用户说"添加定时备份任务"

```
步骤1：执行 dbskiter --database=<name> scheduler task add daily_backup "0 2 * * *" --type=backup
步骤2：确认任务已添加
步骤3：建议启动调度器：dbskiter --database=<name> scheduler daemon start
```

### 场景5：用户说"查看任务执行情况"

```
步骤1：执行 dbskiter --database=<name> scheduler logs --limit=10
步骤2：解读最近的任务执行记录
步骤3：如果有失败任务，建议查看详细错误
```
