# 数据库 Skills - CLI 版本

> 统一 CLI 入口，支持任何 AI IDE 调用

## 设计理念

不再局限于 Trae Skill 的 `scripts/run.py` 模式，而是提供**统一的 CLI 工具** `dbskiter`：

- [OK] **命令行直接使用**：`dbskiter monitor --database=jump`
- [OK] **AI IDE 通用**：任何 AI IDE 都可以通过 SKILL.md 学习如何调用 CLI
- [OK] **标准化接口**：所有 Skill 统一为子命令
- [OK] **JSON 输出**：便于 AI 解析结果

---

## 安装

```bash
# 安装 Python 包
pip install -e .

# 验证安装
dbskiter --help
```

---

## 快速使用

### 多数据库支持（别名方式）

支持通过 `--database` 参数使用别名连接不同的数据库：

```bash
# 在 .env 中配置多个数据库（使用 DB_{别名}_* 格式）
DB_JUMP_HOST=192.168.26.49
DB_JUMP_NAME=jump
DB_ORCL_HOST=192.168.26.120
DB_ORCL_SERVICE=orcl

# 使用别名连接指定数据库
dbskiter --database=jump diagnose
dbskiter --database=orcl diagnose
dbskiter --database=chenzc diagnose
```

### 向后兼容（前缀方式）

仍支持通过 `--prefix` 参数切换配置（不推荐新用户使用）：

```bash
# MySQL 默认配置（DB_* 环境变量）
dbskiter diagnose

# Oracle 数据库（ORACLE_* 环境变量）
dbskiter --prefix=ORACLE diagnose
```

### 1. 监控数据库健康

```bash
# 使用默认配置（从 .env 读取）
dbskiter monitor

# 指定数据库
dbskiter --database=jump monitor

# 输出 JSON（便于 AI 解析）
dbskiter --database=jump --json monitor

# Oracle 数据库监控
dbskiter --prefix=ORACLE --json monitor
```

### 2. 诊断数据库

```bash
# 分析慢查询和推荐索引
dbskiter --database=jump diagnose

# 优化特定 SQL
dbskiter --database=jump diagnose --sql="SELECT * FROM users WHERE age > 18"

# Oracle 诊断
dbskiter --prefix=ORACLE diagnose --limit=10
```

### 3. 安全审计

```bash
dbskiter --database=jump --json security

# Oracle 安全审计
dbskiter --prefix=ORACLE --json security
```

### 4. 执行备份

```bash
# 全量备份
dbskiter --database=jump scheduler backup --type=full

# 增量备份
dbskiter --database=jump scheduler backup --type=incremental
```

### 5. 生成报告

```bash
# 健康报告
dbskiter --database=jump report --type=health

# 性能报告导出为 HTML
dbskiter --database=jump report --type=performance --format=html
```

### 6. 执行 SQL

```bash
dbskiter --database=jump --json sql "SELECT * FROM users LIMIT 10"

# Oracle SQL 执行
dbskiter --prefix=ORACLE --json sql "SELECT * FROM user_tables WHERE ROWNUM <= 5"
```

---

## AI IDE 使用方式

### Trae 中使用

当用户说："检查 jump 数据库的健康状态"

Trae 会读取 `db-monitor/SKILL.md`，然后执行：

```bash
dbskiter --database=jump --json monitor
```

### Cursor 中使用

同样的 SKILL.md 可以放在 Cursor 的 `.cursor/rules/` 目录，Cursor 也能理解如何调用。

### 其他 AI IDE

任何支持自定义指令的 AI IDE 都可以通过 SKILL.md 学习 CLI 用法。

---

## 目录结构

```
.trae/skills/              # Skill 定义（仅 SKILL.md）
├── db-monitor/SKILL.md    # 监控 Skill 文档
├── db-diagnose/SKILL.md   # 诊断 Skill 文档
├── db-security/SKILL.md   # 安全 Skill 文档
├── db-scheduler/SKILL.md  # 调度 Skill 文档
└── sql-master/SKILL.md    # SQL Skill 文档

dbskiter/                  # Python 包（核心实现）
├── cli.py                 # 统一 CLI 入口
├── db_monitor/            # 监控模块
├── db_diagnose/           # 诊断模块
├── db_security/           # 安全模块
├── db_scheduler/          # 调度模块
├── sql_master/            # SQL 模块
└── shared/                # 共享组件
```

---

## 配置

创建 `.env` 文件：

### MySQL 配置
```bash
DB_DIALECT=mysql+pymysql
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=your_password
DB_NAME=your_database
```

### Oracle 配置（支持 11g/12c/19c）
```bash
# Oracle 基本配置
ORACLE_DIALECT=oracle+oracledb
ORACLE_HOST=192.168.1.100
ORACLE_PORT=1521
ORACLE_USER=your_user
ORACLE_PASSWORD=your_password
ORACLE_SERVICE=ORCL

# Oracle JDBC 驱动路径（用于 11g 等旧版本）
ORACLE_JDBC_DRIVER=ojdbc8.jar
```

### 多数据库配置示例
```bash
# 默认 MySQL 主库
DB_DIALECT=mysql+pymysql
DB_HOST=192.168.1.10
DB_NAME=production

# MySQL 从库
MYSQL2_DIALECT=mysql+pymysql
MYSQL2_HOST=192.168.1.11
MYSQL2_NAME=production

# Oracle 报表库
ORACLE_DIALECT=oracle+oracledb
ORACLE_HOST=192.168.1.20
ORACLE_SERVICE=REPORTDB
ORACLE_JDBC_DRIVER=ojdbc8.jar
```

---

## CLI 命令速查

### 全局参数

| 参数 | 说明 | 示例 |
|------|------|------|
| `--prefix` | 数据库配置前缀 | `--prefix=ORACLE` |
| `--database` | 数据库名称 | `--database=jump` |
| `--json` | JSON 格式输出 | `--json` |
| `--debug` | 调试模式 | `--debug` |

### 子命令

| 命令 | 功能 | 示例 |
|------|------|------|
| `monitor` | 健康监控 | `dbskiter --database=jump monitor` |
| `diagnose` | 诊断优化 | `dbskiter --database=jump diagnose --sql="SELECT..."` |
| `security` | 安全审计 | `dbskiter --database=jump security` |
| `scheduler` | 调度备份 | `dbskiter --database=jump scheduler backup --type=full` |
| `report` | 报告生成 | `dbskiter --database=jump report --type=health` |
| `sql` | SQL 执行 | `dbskiter --database=jump sql "SELECT * FROM users"` |

### 多数据库使用示例

```bash
# MySQL 主库（默认）
dbskiter --database=production diagnose

# MySQL 从库
dbskiter --prefix=MYSQL2 --database=production diagnose

# Oracle 生产库
dbskiter --prefix=ORACLE diagnose

# Oracle 慢查询分析
dbskiter --prefix=ORACLE --json diagnose --limit=5

# Oracle 敏感数据扫描
dbskiter --prefix=ORACLE --json security
```

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
