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

# 趋势分析
dbskiter --database=jump monitor trend --metric=cpu_usage
```

### 2. 诊断命令 (diagnose)

```bash
# 慢查询分析
dbskiter --database=jump diagnose slow-queries

# SQL诊断
dbskiter --database=jump diagnose sql "SELECT * FROM users"

# 索引推荐
dbskiter --database=jump diagnose recommend-indexes

# 性能快照
dbskiter --database=jump diagnose performance-snapshot

# 瓶颈分析
dbskiter --database=jump diagnose bottleneck
```

### 3. 安全命令 (security)

```bash
# 完整安全审计
dbskiter --database=jump security audit

# SQL注入检测
dbskiter --database=jump security sql-injection "SELECT * FROM users WHERE id = %s"

# 敏感数据扫描
dbskiter --database=jump security sensitive-data

# 权限审计
dbskiter --database=jump security permissions
```

### 4. SQL命令 (sql)

```bash
# 执行SQL
dbskiter --database=jump sql execute "SELECT * FROM users LIMIT 10"

# SQL重写优化
dbskiter --database=jump sql rewrite "SELECT * FROM users WHERE id = 1"

# 查看表结构
dbskiter --database=jump sql schema --table=users

# 导出数据
dbskiter --database=jump sql export --table=users --output=users.csv
```

### 5. 巡检命令 (inspector)

```bash
# 执行巡检
dbskiter --database=jump inspector run

# 生成报告
dbskiter --database=jump inspector report --output report.html

# 智能巡检
dbskiter --database=jump inspector intelligent
```

### 6. 锁分析命令 (lock)

```bash
# 分析当前锁
dbskiter --database=jump lock analyze

# 检测死锁
dbskiter --database=jump lock deadlocks

# 锁等待链
dbskiter --database=jump lock chains
```

### 7. 调度命令 (scheduler)

```bash
# 备份数据库
dbskiter --database=jump scheduler backup --type=full

# 查看定时任务
dbskiter --database=jump scheduler task list

# 添加定时任务
dbskiter --database=jump scheduler task add daily_backup "0 2 * * *"
```

### 8. SQL审核命令 (audit)

```bash
# 审核SQL
dbskiter --database=jump audit sql "SELECT * FROM users"

# DDL影响分析
dbskiter --database=jump audit ddl "ALTER TABLE users ADD COLUMN age INT"

# 查看审核规则
dbskiter --database=jump audit rules
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
