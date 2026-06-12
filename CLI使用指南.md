# DBSKiter CLI 使用指南

DBSKiter 数据库运维工具集的命令行使用文档。

---

## 安装

```bash
# 安装 Python 包
pip install -e .

# 验证安装
dbskiter --help
```

---

## 快速开始

### 配置数据库连接

创建 `.env` 文件：

```bash
# MySQL 配置
DB_DIALECT=mysql+pymysql
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=your_password
DB_NAME=your_database

# Oracle 配置
ORACLE_DIALECT=oracle+jdbc
ORACLE_HOST=192.168.1.100
ORACLE_PORT=1521
ORACLE_USER=your_user
ORACLE_PASSWORD=your_password
ORACLE_SERVICE=ORCL
```

### 基本使用

```bash
# 监控数据库健康
dbskiter --database=jump monitor

# 诊断慢查询
dbskiter --database=jump diagnose slow-queries

# 安全审计
dbskiter --database=jump security audit
```

### 通用数据库支持（新增）

DBSKiter 支持通过 Generic JDBC 模式连接任意数据库：

```bash
# 连接 Trino 集群
dbskiter --database=trino_prod monitor health

# 连接 DuckDB
dbskiter --database=duck_analytics monitor collect

# 连接任意 JDBC 数据库（自动回退到通用采集器）
dbskiter --database=my_custom_db monitor health
```

通用采集器支持的基础指标：

| 指标 | 说明 | 支持范围 |
|------|------|----------|
| 活跃连接数 | 当前活跃会话数 | PostgreSQL/MySQL/Oracle/SQL Server 风格 |
| 表数量 | 数据库中表的总数 | INFORMATION_SCHEMA / pg_class |
| 索引数量 | 数据库中索引的总数 | INFORMATION_SCHEMA / pg_class |
| 数据库大小 | 数据库文件总大小（MB） | PostgreSQL/MySQL/SQLite |

通用巡检器支持（与通用采集器共享能力探测逻辑）：

```bash
# 对任意 JDBC 数据库执行完整巡检
dbskiter --database=trino_prod inspector run

# 执行配置和存储检查
dbskiter --database=duck_analytics inspector run --type configuration storage

# 生成巡检报告
dbskiter --database=my_custom_db inspector report --output report.html
```

配置示例（`.env`）：

```bash
# Trino 配置
TRINO_DIALECT=trino
TRINO_HOST=trino.example.com
TRINO_PORT=8080
TRINO_USER=db_admin
TRINO_PASSWORD=your_password
TRINO_NAME=analytics

# DuckDB 配置（嵌入式）
DUCKDB_DIALECT=duckdb
DUCKDB_NAME=./analytics.duckdb
```

---

## 输出模式

DBSKiter 支持三种输出模式：

| 模式 | 参数 | 适用场景 |
|------|------|----------|
| rule | `--output-mode=rule` (默认) | 人类阅读，格式化输出 |
| raw | `--output-mode=raw` | 脚本处理，原始数据 |
| ai | `--output-mode=ai` | AI分析，结构化JSON |

### 示例

```bash
# 默认模式（人类可读）
dbskiter --database=jump monitor health

# AI模式（结构化JSON，供AI分析）
dbskiter --output-mode=ai --database=jump monitor health

# Raw模式（原始数据）
dbskiter --output-mode=raw --database=jump monitor health
```

---

## 全局参数

| 参数 | 说明 | 示例 |
|------|------|------|
| `--database` | 数据库名称 | `--database=jump` |
| `--output-mode` | 输出模式 | `--output-mode=ai` |
| `--ai-depth` | AI输出详细程度 | `--ai-depth=detail` |
| `--json` | JSON格式输出（兼容旧版） | `--json` |
| `--debug` | 调试模式 | `--debug` |

---

## 命令参考

### 1. 监控命令 (monitor)

```bash
# 健康检查
dbskiter --database=jump monitor health

# 异常检测
dbskiter --database=jump monitor anomalies

# 容量预测
dbskiter --database=jump monitor capacity --resource=disk

# 高级容量预测（多算法+置信度评估）
dbskiter --database=jump monitor capacity-advanced --resource=disk

# 趋势分析
dbskiter --database=jump monitor trend --metric=cpu_usage

# 采集指标
dbskiter --database=jump monitor collect

# 查看历史指标
dbskiter --database=jump monitor history cpu_usage

# 基线对比
dbskiter --database=jump monitor compare --metric=qps --value=1250 --baseline=2026-04-01
```

### 2. 诊断命令 (diagnose)

```bash
# 实时诊断（数据库有点慢）
dbskiter --database=jump diagnose realtime

# TOP SQL分析
dbskiter --database=jump diagnose top

# 锁分析（有死锁/阻塞）
dbskiter --database=jump diagnose locks

# 通用数据库锁分析（适用于 Trino/DuckDB/任何 JDBC 数据库）
dbskiter --database=trino_prod lock analyze
dbskiter --database=trino_prod lock deadlocks
dbskiter --database=trino_prod lock report

# SQL深度诊断
dbskiter --database=jump diagnose sql "SELECT * FROM users"

# 空间诊断
dbskiter --database=jump diagnose space

# 连接分析
dbskiter --database=jump diagnose connections

# 复制诊断（主从延迟）
dbskiter --database=jump diagnose replication

# 慢查询分析
dbskiter --database=jump diagnose slow-queries

# 索引推荐
dbskiter --database=jump diagnose recommend-indexes

# 综合诊断报告
dbskiter --database=jump diagnose report

# 通用数据库诊断（适用于 Trino/DuckDB/任何 JDBC 数据库）
dbskiter --database=trino_prod diagnose slow-queries
dbskiter --database=trino_prod diagnose performance-snapshot
dbskiter --database=trino_prod diagnose report

# 单表诊断
dbskiter --database=jump diagnose table users

# 性能快照
dbskiter --database=jump diagnose performance-snapshot

# 瓶颈分析
dbskiter --database=jump diagnose bottleneck
```

#### 数据库特有诊断

```bash
# VACUUM状态分析（PostgreSQL）
dbskiter --database=jump diagnose vacuum

# 表膨胀/碎片分析（PostgreSQL膨胀/MySQL碎片/Oracle表空间碎片）
dbskiter --database=jump diagnose bloat
dbskiter --database=jump diagnose bloat --threshold=50

# 索引使用分析（MySQL/Oracle/PostgreSQL）
dbskiter --database=jump diagnose index-usage

# 表空间碎片分析（Oracle）
dbskiter --database=jump diagnose tablespace-fragmentation
```

### 3. 安全命令 (security)

```bash
# 完整安全审计
dbskiter --database=jump security audit

# SQL注入检测
dbskiter --database=jump security sql-injection "SELECT * FROM users WHERE id = %s"

# 敏感数据扫描
dbskiter --database=jump security sensitive-data
dbskiter --database=jump security sensitive-data --tables=users,orders

# 安全评分
dbskiter --database=jump security score

# 权限审计
dbskiter --database=jump security permissions

# 登录安全监控
dbskiter --database=jump security login-security
dbskiter --database=jump security login-security --hours=48

# 审计日志分析
dbskiter --database=jump security audit-log
dbskiter --database=jump security audit-log --hours=72

# 高危操作检测
dbskiter --database=jump security high-risk
dbskiter --database=jump security high-risk --hours=48

# 密码策略检查
dbskiter --database=jump security password-policy

# 弱密码扫描
dbskiter --database=jump security weak-passwords

# 配置安全检查
dbskiter --database=jump security config

# 通用数据库安全审计（适用于 Trino/DuckDB/任何 JDBC 数据库）
dbskiter --database=trino_prod security audit
dbskiter --database=trino_prod security sensitive-data
dbskiter --database=trino_prod security permissions
dbskiter --database=trino_prod security config
```

### 4. SQL命令 (sql)

```bash
# 执行SQL
dbskiter --database=jump sql execute "SELECT * FROM users LIMIT 10"

# 批量执行SQL文件
dbskiter --database=jump sql batch queries.sql

# SQL重写优化
dbskiter --database=jump sql rewrite "SELECT * FROM users WHERE id = 1"

# SQL质量分析
dbskiter --database=jump sql analyze "SELECT * FROM users WHERE id = 1"

# 数据分析
dbskiter --database=jump sql data "SELECT * FROM users"

# 智能补全
dbskiter --database=jump sql complete "SELECT * FROM u"

# 查看表结构
dbskiter --database=jump sql schema
dbskiter --database=jump sql schema --table=users

# 导出数据
dbskiter --database=jump sql export --table=users --output=users.csv

# 流式导出大数据量
dbskiter --database=jump sql export-stream --table=users --output=users.csv

# 导入数据
dbskiter --database=jump sql import --table=users --input=users.csv

# 查看审计日志
dbskiter --database=jump sql audit
```

### 5. 巡检命令 (inspector)

```bash
# 执行巡检
dbskiter --database=jump inspector run
dbskiter --database=jump inspector run --type configuration
dbskiter --database=jump inspector run --type performance storage

# 生成报告
dbskiter --database=jump inspector report --output report.html

# 创建性能基线
dbskiter --database=jump inspector baseline --create

# 与基线对比
dbskiter --database=jump inspector baseline --compare

# 智能巡检（异常检测+根因分析+建议）
dbskiter --database=jump inspector intelligent

# 异常检测
dbskiter --database=jump inspector anomalies --metric=cpu_usage

# 根因分析
dbskiter --database=jump inspector root-cause --issue="CPU使用率飙升"

# 风险预测
dbskiter --database=jump inspector risks --days=7
```

通用巡检器支持（适用于 Trino/DuckDB/任何 JDBC 数据库）：

| 检查项 | 说明 | 数据源 |
|--------|------|--------|
| 数据库类型与版本 | 数据库方言和版本号 | VERSION() / @@version |
| Schema 数量 | 数据库中 Schema 总数 | INFORMATION_SCHEMA |
| 表总数 | 数据库中 BASE TABLE 数量 | INFORMATION_SCHEMA |
| 活跃连接数 | 当前活跃会话数量 | pg_stat_activity / v$session / sys.dm_exec_sessions |
| 数据库总大小 | 数据库存储容量 | pg_database_size / information_schema.tables / PRAGMA |
| 索引数量 | 索引总数 | INFORMATION_SCHEMA.STATISTICS |
| TOP 大表 | 行数最多的 10 张表 | INFORMATION_SCHEMA.TABLES |
| 数据库用户 | 当前连接用户 | CURRENT_USER / USER() |
| 容量规划建议 | 基于通用采集的容量评估 | 综合多数据源 |

### 6. 锁分析命令 (lock)

```bash
# 分析当前锁
dbskiter --database=jump lock analyze

# 检测死锁
dbskiter --database=jump lock deadlocks

# 锁等待链
dbskiter --database=jump lock chains

# 生成锁分析报告
dbskiter --database=jump lock report

# 终止指定事务（需谨慎）
dbskiter --database=jump lock kill <事务ID>
```

### 7. 调度命令 (scheduler)

```bash
# 备份数据库
dbskiter --database=jump scheduler backup --type=full

# 通用数据库备份（适用于 Trino/DuckDB/任何 JDBC 数据库）
dbskiter --database=trino_prod scheduler backup --type=full
dbskiter --database=trino_prod scheduler backup --type=table --tables users,orders

# 验证备份
dbskiter --database=jump scheduler backup-verify <备份文件路径>

# 恢复数据库
dbskiter --database=jump scheduler backup-restore <备份文件路径>

# 通用数据库恢复（适用于 Trino/DuckDB/任何 JDBC 数据库）
dbskiter --database=trino_prod scheduler backup-restore <备份文件路径>

# 查看定时任务
dbskiter --database=jump scheduler task list

# 添加定时任务
dbskiter --database=jump scheduler task add daily_backup "0 2 * * *"

# 删除任务
dbskiter --database=jump scheduler task remove daily_backup

# 启用/禁用任务
dbskiter --database=jump scheduler task enable daily_backup
dbskiter --database=jump scheduler task disable daily_backup

# 立即执行任务
dbskiter --database=jump scheduler task run daily_backup

# 查看任务日志
dbskiter --database=jump scheduler logs

# 启动调度器守护进程
dbskiter --database=jump scheduler daemon start

# 停止调度器守护进程
dbskiter --database=jump scheduler daemon stop

# 查看调度器状态
dbskiter --database=jump scheduler daemon status

# 创建工作流
dbskiter --database=jump scheduler workflow create daily_workflow

# 添加任务到工作流
dbskiter --database=jump scheduler workflow add-task daily_workflow task1

# 提交执行工作流
dbskiter --database=jump scheduler workflow submit daily_workflow

# 列出所有工作流
dbskiter --database=jump scheduler workflow list

# 查看工作流状态
dbskiter --database=jump scheduler workflow status daily_workflow
```

### 8. SQL审核命令 (audit)

```bash
# 审核SQL
dbskiter --database=jump audit sql "SELECT * FROM users"
dbskiter --database=jump audit sql "SELECT * FROM orders WHERE user_id = 1" --params='{"user_id": 1}'

# 批量审核SQL文件
dbskiter --database=jump audit file queries.sql

# DDL影响分析
dbskiter --database=jump audit ddl "ALTER TABLE users ADD COLUMN age INT"

# 通用数据库 DDL 影响分析（适用于 Trino/DuckDB/任何 JDBC 数据库）
dbskiter --database=trino_prod audit ddl "ALTER TABLE users ADD COLUMN age INT"

# 查看审核规则
dbskiter --database=jump audit rules

# SQL优化建议
dbskiter --database=jump audit optimize "SELECT * FROM users WHERE age > 18"

# 索引推荐
dbskiter --database=jump audit recommend-indexes "SELECT * FROM orders WHERE user_id = 1"
```

---

## 多数据库配置

支持通过环境变量配置多个数据库：

```bash
# 默认数据库
DB_HOST=192.168.1.10
DB_NAME=production

# 第二个MySQL实例
MYSQL2_HOST=192.168.1.11
MYSQL2_NAME=production

# Oracle实例
ORACLE_HOST=192.168.1.20
ORACLE_SERVICE=ORCL
```

使用：

```bash
# 使用默认配置
dbskiter --database=production monitor

# 使用前缀方式（向后兼容）
dbskiter --prefix=ORACLE monitor
```

---

## AI模式输出格式

当使用 `--output-mode=ai` 时，输出为标准JSON结构：

```json
{
  "schema_version": "1.0",
  "collected_at": "2026-04-28T10:30:00Z",
  "instance_id": "mysql-prod-01",
  "data_source": {"type": "direct", "dialect": "mysql"},
  "data": {
    "raw_metrics": {...},
    "rule_flags": {...},
    "context": {...},
    "reference_values": {...},
    "ai_hints": {...}
  }
}
```

详见 [AI集成指南.md](AI集成指南.md)

---

## 开发

```bash
# 安装开发依赖
pip install -e ".[dev]"

# 运行测试
pytest

# 代码格式化
black dbskiter/
```

---

## License

MIT
