---
name: db-scheduler
description: |
  数据库调度工具，支持备份、定时任务管理、任务执行日志、调度器守护进程、DAG工作流。

  使用场景：
  - 用户说"备份数据库" -> 执行 backup
  - 用户说"定时任务" -> 执行 task
  - 用户说"查看任务日志" -> 执行 logs
  - 用户说"启动调度器" -> 执行 daemon start
  - 用户说"创建工作流" -> 执行 workflow

  用法：
  - dbskiter --output-mode=ai --database=<name> scheduler backup --type=full
  - dbskiter --output-mode=ai --database=<name> scheduler task list
  - dbskiter --output-mode=ai --database=<name> scheduler task add daily_backup "0 2 * * *"
  - dbskiter --output-mode=ai --database=<name> scheduler logs
  - dbskiter --output-mode=ai --database=<name> scheduler daemon start
---

# 数据库调度 Skill

## 何时使用

当用户提到以下关键词时，使用此skill：

| 用户说法 | 执行命令 | 说明 |
|---------|---------|------|
| "备份数据库" | `dbskiter --output-mode=ai --database=<name> scheduler backup` | 执行备份 |
| "定时任务" | `dbskiter --output-mode=ai --database=<name> scheduler task` | 管理定时任务 |
| "任务日志" | `dbskiter --output-mode=ai --database=<name> scheduler logs` | 查看执行记录 |
| "启动调度器" | `dbskiter --output-mode=ai --database=<name> scheduler daemon start` | 启动自动执行 |
| "停止调度器" | `dbskiter --output-mode=ai --database=<name> scheduler daemon stop` | 停止自动执行 |
| "调度器状态" | `dbskiter --output-mode=ai --database=<name> scheduler daemon status` | 查看运行状态 |
| "创建工作流" | `dbskiter --output-mode=ai --database=<name> scheduler workflow` | 管理DAG工作流 |

## 核心命令

### 1. 备份数据库
```bash
dbskiter --database=<数据库名> scheduler backup --type=full
```
**功能**：执行数据库备份

**可选参数**：
- `--type`：备份类型（full/incremental，默认full）
- `--compress`：压缩备份
- `--tables`：指定表（逗号分隔）
- `--output-dir`：输出目录

### 2. 定时任务管理

#### 列出所有任务
```bash
dbskiter --database=<数据库名> scheduler task list
```

#### 添加任务
```bash
dbskiter --database=<数据库名> scheduler task add daily_backup "0 2 * * *" --type=backup
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
dbskiter --database=<数据库名> scheduler task remove <任务名称>
```

#### 启用/禁用任务
```bash
dbskiter --database=<数据库名> scheduler task enable <任务名称>
dbskiter --database=<数据库名> scheduler task disable <任务名称>
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

### 3. 查看任务日志
```bash
dbskiter --database=<数据库名> scheduler logs
```
**功能**：查看任务执行日志

**可选参数**：
- `--task`：指定任务名称
- `--limit`：返回记录数（默认20）
- `--status`：过滤状态（success/failed/all，默认all）

### 4. 调度器守护进程管理

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

### 5. DAG工作流管理

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
```

### 场景2：用户说"添加定时备份任务"

```
步骤1：执行 dbskiter --database=<name> scheduler task add daily_backup "0 2 * * *" --type=backup
步骤2：确认任务已添加
步骤3：建议启动调度器：dbskiter --database=<name> scheduler daemon start
```

### 场景3：用户说"查看任务执行情况"

```
步骤1：执行 dbskiter --database=<name> scheduler logs --limit=10
步骤2：解读最近的任务执行记录
步骤3：如果有失败任务，建议查看详细错误
```
