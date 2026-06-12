---
name: db-inspector
description: |
  数据库实例巡检与报告生成，支持配置检查、性能检查、安全检查、报告生成、智能巡检、异常检测、根因分析、风险预测。

  使用场景：
  - 用户说"巡检" -> 执行 run
  - 用户说"生成报告" -> 执行 report
  - 用户说"检查配置" -> 执行 run --type configuration
  - 用户说"建立基线" -> 执行 baseline --create
  - 用户说"智能巡检" -> 执行 intelligent
  - 用户说"异常检测" -> 执行 anomalies
  - 用户说"根因分析" -> 执行 root-cause
  - 用户说"风险预测" -> 执行 risks

  用法：
  - python -m dbskiter --output-mode=ai --database=<name> inspector run
  - python -m dbskiter --output-mode=ai --database=<name> inspector report --output report.html
  - python -m dbskiter --output-mode=ai --database=<name> inspector baseline --create
  - python -m dbskiter --output-mode=ai --database=<name> inspector intelligent
  - python -m dbskiter --output-mode=ai --database=<name> inspector anomalies --metric=cpu_usage
  - python -m dbskiter --output-mode=ai --database=<name> inspector root-cause --issue="CPU飙升"
  - python -m dbskiter --output-mode=ai --database=<name> inspector risks --days=7
---

# 数据库巡检 Skill

## 安全原则

本Skill的所有操作均为只读查询，不会修改任何数据：

| 规则 | 说明 |
|------|------|
| 只读操作 | 巡检命令只执行SELECT/SHOW/DESCRIBE等查询操作 |
| 禁止写操作 | 不得通过巡检命令执行DELETE/UPDATE/INSERT/DROP等写操作 |
| 基线创建只记录快照 | baseline --create只记录当前配置快照，不修改数据库 |
| 报告生成只读 | report命令只生成报告文件，不修改数据库 |

## 何时使用

当用户提到以下关键词时，使用此skill：

| 用户说法 | 执行命令 | 说明 |
|---------|---------|------|
| "巡检" | `python -m dbskiter --output-mode=ai --database=<name> inspector run` | 执行完整巡检 |
| "生成报告" | `python -m dbskiter --output-mode=ai --database=<name> inspector report` | 生成巡检报告 |
| "检查配置" | `python -m dbskiter --output-mode=ai --database=<name> inspector run --type configuration` | 仅检查配置 |
| "检查安全" | `python -m dbskiter --output-mode=ai --database=<name> inspector run --type security` | 仅安全检查 |
| "建立基线" | `python -m dbskiter --output-mode=ai --database=<name> inspector baseline --create` | 创建性能基线 |
| "智能巡检" | `python -m dbskiter --output-mode=ai --database=<name> inspector intelligent` | 智能巡检分析 |
| "异常检测" | `python -m dbskiter --output-mode=ai --database=<name> inspector anomalies` | 检测指标异常 |
| "根因分析" | `python -m dbskiter --output-mode=ai --database=<name> inspector root-cause` | 分析问题根因 |
| "风险预测" | `python -m dbskiter --output-mode=ai --database=<name> inspector risks` | 预测未来风险 |

## 核心命令

### 1. 执行完整巡检
```bash
python -m dbskiter --database=<数据库名> inspector run
```
**输出**：健康评分、风险统计、巡检项详情

**评分标准**：
- 90-100：优秀
- 70-89：良好
- <70：需要关注

**可选参数**：
- `--type`：指定巡检类型（configuration/performance/storage/security/capacity/replication）
- `--format`：输出格式（text/json/html/markdown）
- `--output`：输出文件路径

### 2. 生成报告
```bash
python -m dbskiter --database=<数据库名> inspector report --output report.html
```
**支持格式**：HTML、Markdown、JSON

### 3. 基线管理
```bash
dbskiter --database=<数据库名> inspector baseline --create
```
**用途**：建立性能基线，用于后续对比

**可选参数**：
- `--create`：创建新基线
- `--compare`：与基线对比

### 4. 智能巡检
```bash
dbskiter --database=<数据库名> inspector intelligent
```
**功能**：异常检测、根因分析、风险预测、智能建议

**可选参数**：
- `--metrics-file`：指标历史数据文件（JSON格式）

### 5. 异常检测
```bash
dbskiter --database=<数据库名> inspector anomalies --metric=cpu_usage
```
**功能**：检测突然飙升、逐渐增长、周期性异常、基线偏离

**参数**：
- `--metric`（必需）：指标名称（如cpu_usage, memory_usage）
- `--hours`：检测最近多少小时的数据（默认24）

### 6. 根因分析
```bash
dbskiter --database=<数据库名> inspector root-cause --issue="CPU飙升"
```
**功能**：分析异常事件的根因，提供解决建议

**参数**：
- `--issue`（必需）：问题描述（如"CPU使用率飙升"）

### 7. 风险预测
```bash
dbskiter --database=<数据库名> inspector risks --days=7
```
**功能**：预测未来7天/30天的容量和性能风险

**参数**：
- `--days`：预测天数（默认7天）

## 巡检类型

- **configuration**：配置检查
- **performance**：性能检查
- **storage**：存储检查
- **security**：安全检查
- **capacity**：容量检查
- **replication**：复制检查

## 数据库支持

| 数据库 | 配置检查 | 性能检查 | 存储检查 | 安全检查 | 容量检查 | 状态 |
|-------|---------|---------|---------|---------|---------|------|
| MySQL | 支持 | 支持 | 支持 | 支持 | 支持 | 生产就绪 |
| Oracle | 支持 | 支持 | 支持 | 支持 | 支持 | 生产就绪 |
| PostgreSQL | 支持 | 支持 | 支持 | 支持 | 支持 | 生产就绪 |
| SQL Server | 支持 | 支持 | 支持 | 支持 | 支持 | 生产就绪 |
| ClickHouse | 支持 | 支持 | 支持 | 支持 | 支持 | 生产就绪 |
| SQLite | 支持 | 支持 | 支持 | 支持 | 支持 | 生产就绪 |
| 通用(Generic) | 基础 | 基础 | 基础 | 基础 | 基础 | 可用 |

**通用巡检器（GenericInspector）说明**：

通用巡检器通过标准 SQL 和 INFORMATION_SCHEMA 自动探测数据库能力，
为任意 JDBC 兼容数据库提供基础巡检能力。

支持的数据库类型：
- Trino / Presto
- DuckDB
- Apache Derby
- H2
- HSQLDB
- 任何支持 JDBC 4.0+ 和 INFORMATION_SCHEMA 的数据库

通用巡检器采集指标：

| 检查项 | 数据源 | 说明 |
|--------|--------|------|
| 数据库类型与版本 | VERSION() / @@version | 数据库方言和版本号 |
| Schema 数量 | INFORMATION_SCHEMA.TABLES | Schema 总数 |
| 表总数 | INFORMATION_SCHEMA.TABLES | BASE TABLE 数量 |
| 活跃连接数 | pg_stat_activity / v$session / sys.dm_exec_sessions | 当前活跃会话 |
| 数据库总大小 | pg_database_size / information_schema / PRAGMA | 存储容量 |
| 索引数量 | INFORMATION_SCHEMA.STATISTICS | 索引总数 |
| TOP 大表 | INFORMATION_SCHEMA.TABLES | 行数最多的表 |
| 数据库用户 | CURRENT_USER / USER() | 当前连接用户 |

**SQLite 巡检项**：
- 配置检查：缓存大小、日志模式（journal_mode）、同步模式（synchronous）
- 性能检查：大表检测、缺少索引检测
- 存储检查：数据库文件大小、碎片率
- 安全检查：文件权限（POSIX系统）
- 容量检查：表数量
- 完整性检查：PRAGMA integrity_check

**ClickHouse 巡检项**：
- 配置检查：max_memory_usage、max_execution_time、query_log启用状态
- 性能检查：慢查询数、高内存使用查询、连接数、复制延迟
- 存储检查：大表检测、parts数量过多检测
- 安全检查：默认用户密码配置
- 容量检查：总数据量、磁盘使用
- 复制检查：Replicated表复制队列、复制延迟

**SQL Server 巡检项**：
- 配置检查：最大内存、MAXDOP、恢复模式、安全设置
- 性能检查：缓冲区命中率、过程缓存命中率、等待统计
- 存储检查：文件增长设置、日志文件大小、磁盘空间
- 安全检查：认证模式、sa账户、权限配置、密码策略
- 容量检查：数据库大小、磁盘使用率、增长趋势

## AI决策流程

### 场景1：用户说"巡检一下数据库"

```
步骤1：执行 dbskiter --database=<name> inspector run
步骤2：解读健康评分和风险统计
步骤3：如果有严重问题，建议进一步诊断
步骤4：生成报告：dbskiter --database=<name> inspector report
```

### 场景2：用户说"分析一下为什么CPU高"

```
步骤1：执行 dbskiter --database=<name> inspector root-cause --issue="CPU飙升"
步骤2：查看根因分析结果
步骤3：给出解决建议
```

### 场景3：用户说"预测一下未来风险"

```
步骤1：执行 dbskiter --database=<name> inspector risks --days=30
步骤2：解读风险预测结果
步骤3：给出预防和应对措施
```
