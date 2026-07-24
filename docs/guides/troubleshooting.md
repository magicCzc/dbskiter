<!--
文件功能：DBSKiter 故障排查手册
作者：MagiCzc
创建时间：2026-07-24
最后修改：2026-07-24
-->

# 故障排查手册

DBSKiter 常见问题排查指南。

---

## 目录

- [连接问题](#连接问题)
- [性能问题](#性能问题)
- [命令执行问题](#命令执行问题)
- [配置问题](#配置问题)
- [升级问题](#升级问题)
- [调试技巧](#调试技巧)

---

## 连接问题

### 症状：连接超时

**可能原因**：

1. 网络不通
2. 防火墙/安全组
3. 数据库监听地址不对

**排查步骤**：

```bash
# 1. 验证网络连通性
ping 192.168.1.100
telnet 192.168.1.100 3306

# 2. 验证数据库监听
mysql -h 192.168.1.100 -P 3306 -u root -p

# 3. 检查配置
dbskiter --debug --database=jump monitor health
```

**常见错误**：

```
Can't connect to MySQL server on '192.168.1.100' (110)
# → 端口不通，检查防火墙

Can't connect to MySQL server on '192.168.1.100' (111)
# → MySQL 未监听 3306，或 bind-address = 127.0.0.1
```

**解决方法**：

```ini
# MySQL my.cnf
bind-address = 0.0.0.0  # 或指定 IP
```

```bash
# 防火墙
sudo iptables -A INPUT -p tcp --dport 3306 -j ACCEPT
```

---

### 症状：Access denied

**可能原因**：

1. 用户名/密码错
2. 账号不允许从该 IP 连接
3. 账号权限不足

**排查**：

```bash
# 1. 直接连接测试
mysql -h 192.168.1.100 -u root -p

# 2. 检查用户权限
SELECT user, host FROM mysql.user WHERE user = 'root';

# 3. 创建专用账号
CREATE USER 'dbskiter'@'192.168.1.%' IDENTIFIED BY 'xxx';
GRANT SELECT, PROCESS, REPLICATION CLIENT ON *.* TO 'dbskiter'@'192.168.1.%';
```

**推荐账号**：

```sql
-- 监控账号（只读 + 必要权限）
CREATE USER 'dbskiter_monitor'@'%' IDENTIFIED BY 'xxx';
GRANT SELECT, PROCESS, REPLICATION CLIENT, SHOW DATABASES ON *.* TO 'dbskiter_monitor'@'%';

-- 备份账号
CREATE USER 'dbskiter_backup'@'%' IDENTIFIED BY 'xxx';
GRANT SELECT, LOCK TABLES, SHOW VIEW, RELOAD ON *.* TO 'dbskiter_backup'@'%';
```

---

### 症状：SSL 连接错误

**MySQL**：

```bash
# 禁用 SSL
dbskiter --url "mysql://root:pwd@host:3306/db?ssl_mode=DISABLED" monitor

# 或环境变量
export DB_SSL_MODE=DISABLED
```

**PostgreSQL**：

```bash
dbskiter --url "postgresql://user:pwd@host:5432/db?sslmode=disable" monitor
```

---

## 性能问题

### 症状：CLI 启动慢

**目标**：< 200ms

**排查**：

```bash
# 1. 测量启动时间
time dbskiter --version

# 2. 检查 Python 环境
python -c "import sys; print(sys.path)"

# 3. 检查冲突
pip list | grep -i "dbskiter\|sqlalchemy"
```

**优化**：

1. 使用虚拟环境
2. 避免在全局 site-packages 安装多个版本
3. 关闭 IDE 的代码检查（运行时）

---

### 症状：健康检查慢

**原因**：

1. 数据库负载高
2. 网络延迟
3. 多个指标并行查询

**优化**：

```bash
# 1. 限制采集范围
dbskiter monitor health --skip-slow-queries --skip-replication

# 2. 调整超时
dbskiter monitor health --timeout=10
```

**配置文件**：

```yaml
# ~/.dbskiter/config.yaml
performance:
  health_check_timeout: 10
  parallel_collection: true
  max_concurrent_queries: 5
```

---

### 症状：慢查询分析卡住

**原因**：慢查询日志非常大（GB 级）

**解决**：

```bash
# 1. 限制时间范围
dbskiter diagnose slow-queries --hours=1

# 2. 限制返回数量
dbskiter diagnose slow-queries --top=10

# 3. 使用采样
dbskiter diagnose slow-queries --sample-rate=10
```

**调整 MySQL 慢查询配置**：

```ini
# my.cnf
slow_query_log = 1
long_query_time = 2
log_output = TABLE  # 或 FILE
```

---

## 命令执行问题

### 症状：命令未找到

**错误**：

```
dbskiter: command not found
```

**排查**：

```bash
# 1. 检查安装
pip show dbskiter

# 2. 检查 PATH
which dbskiter
echo $PATH

# 3. 重新安装
pip install --force-reinstall dbskiter
```

**Windows 特殊问题**：

如果 `dbskiter` 命令在 PowerShell 不可用：

```powershell
# 检查 Scripts 目录
$env:PATH += ";$env:APPDATA\Python\Python311\Scripts"

# 永久添加
[Environment]::SetEnvironmentVariable("Path", $env:Path + ";$env:APPDATA\Python\Python311\Scripts", "User")
```

---

### 症状：参数错误

**错误**：

```
dbskiter: error: argument --database: expected one argument
```

**常见原因**：

1. `--database` 必须在子命令**之前**
2. 多单词参数需要引号

**正确用法**：

```bash
# ✓ 正确：--database 在前
dbskiter --database=jump diagnose slow-queries

# ✗ 错误：--database 在后
dbskiter diagnose slow-queries --database=jump
```

**提示**：从 v3.0+ 起，连接类参数（`--database`、`--host` 等）可以在子命令前后任意位置使用，但仍推荐放在前面。

---

### 症状：Tab 补全不工作

**排查**：

```bash
# 1. 检查是否配置
grep "argcomplete" ~/.bashrc

# 2. 重新配置
dbskiter shell-setup --auto

# 3. 重新加载
source ~/.bashrc
```

**Zsh 用户**：

```bash
dbskiter shell-setup --auto --shell=zsh
source ~/.zshrc
```

---

## 配置问题

### 症状：配置未生效

**排查**：

```bash
# 1. 确认配置加载顺序
dbskiter --debug --database=jump config show

# 2. 查看生效的配置
dbskiter config show --source=all
```

**优先级**：

```
--url 连接字符串（最高）
  ↓
--password-stdin / --password-file
  ↓
--host, --user, --password 等 CLI 参数
  ↓
--profile 指定的 profile
  ↓
--database 匹配的 .env 别名
  ↓
.env 文件中的默认配置
  ↓
环境变量 DB_HOST, DB_USER 等
  ↓
内置默认值（最低）
```

---

### 症状：多个数据库配置冲突

**场景**：`.env` 中既有 `DB_HOST` 又有 `DB_JUMP_HOST`

**规则**：

- `DB_*` 是默认配置（`--database=default`）
- `DB_<ALIAS>_*` 是别名配置（`--database=<ALIAS>`）

```bash
# .env
DB_HOST=192.168.1.1
DB_NAME=production
DB_USER=root
DB_PASSWORD=xxx

DB_JUMP_HOST=192.168.1.1
DB_JUMP_NAME=production
DB_JUMP_USER=root
DB_JUMP_PASSWORD=xxx
```

```bash
dbskiter --database=default monitor  # 使用 DB_*
dbskiter --database=jump monitor     # 使用 DB_JUMP_*
```

---

### 症状：.env 文件不生效

**排查**：

```bash
# 1. 检查 .env 位置
ls -la .env  # 必须在执行 dbskiter 的目录

# 2. 检查格式（不能有空格）
DB_HOST=localhost  # ✓
DB_HOST = localhost  # ✗

# 3. 检查编码（UTF-8）
file .env
```

---

## 升级问题

### 症状：升级后命令报错

**常见问题**：

1. API 变更（看 CHANGELOG）
2. 配置格式变更
3. 依赖版本冲突

**回滚**：

```bash
pip install dbskiter==3.0.34  # 回到指定版本
```

**强制重装依赖**：

```bash
pip install --force-reinstall dbskiter
```

---

### 症状：V2 模块 DeprecationWarning

**含义**：v4.0 将移除 V2 模块。

**解决**：参考 [v3 → v4 迁移指南](guides/migration-v3-to-v4.md)

```python
# 旧
from dbskiter.db_security.sensitive_data_scanner_v2 import SensitiveDataScannerV2

# 新
from dbskiter.db_security.sensitive_data_scanner import SensitiveDataScanner
```

---

## 调试技巧

### 1. 使用 `--debug` 模式

```bash
dbskiter --debug --database=jump monitor health
```

显示详细错误堆栈、SQL 执行日志、连接信息。

### 2. 使用 `--verbose` 模式

```bash
dbskiter --verbose --database=jump diagnose slow-queries
```

显示采集过程（哪些指标采了、花了多久）。

### 3. 使用 `--show-trace` 模式

```bash
dbskiter --show-trace --database=jump diagnose realtime
```

显示诊断追踪信息（数据来源、检查指标）。

### 4. 查看历史命令

```bash
# 查看最近 20 条
dbskiter history

# 重新执行上一条
dbskiter history rerun

# 按命令过滤
dbskiter history --command=monitor
```

### 5. 单独测试 SQL

```bash
# 不通过 Diagnose，直接执行
dbskiter --database=jump sql execute "SELECT 1"

# 验证 SQL 安全性
dbskiter --database=jump sql analyze "SELECT * FROM users WHERE id = 1"

# 看执行计划
dbskiter --database=jump sql explain "SELECT * FROM users WHERE id = 1"
```

### 6. 测试连接

```bash
# 健康检查（最简单）
dbskiter --database=jump monitor health

# 详细诊断
dbskiter --database=jump diagnose realtime
```

### 7. 查看日志

```bash
# 日志位置
ls -la ~/.dbskiter/logs/

# 实时跟踪
tail -f ~/.dbskiter/logs/dbskiter.log
```

---

## 性能基准异常

### 症状：CLI 启动时间 > 1s

**目标**：< 200ms

**可能原因**：

1. Python 启动慢（系统 Python 慢）
2. 导入链过长
3. 配置文件过大

**优化**：

```bash
# 1. 测量 Python 启动时间
time python -c "pass"

# 2. 测量 import 时间
time python -c "import dbskiter"

# 3. 检查导入
python -X importtime -c "import dbskiter" 2>&1 | sort -rn | head -20
```

**期望**：`import dbskiter` 应 < 500ms。

---

## 数据库特定问题

### MySQL

#### `performance_schema` 未启用

```ini
# my.cnf
[mysqld]
performance_schema = ON
performance_schema_max_table_instances = 12500
```

#### `processlist` 权限不足

```sql
GRANT PROCESS ON *.* TO 'dbskiter'@'%';
```

#### 慢查询日志

```ini
# my.cnf
slow_query_log = 1
long_query_time = 2
log_output = TABLE
```

---

### PostgreSQL

#### `pg_stat_statements` 未启用

```sql
-- postgresql.conf
shared_preload_libraries = 'pg_stat_statements'

-- 重启后
CREATE EXTENSION pg_stat_statements;
```

#### `pg_locks` 权限

```sql
GRANT pg_read_all_stats TO dbskiter;
```

---

### Oracle

#### 字典视图访问权限

```sql
GRANT SELECT ANY DICTIONARY TO dbskiter;
GRANT SELECT ANY TABLE TO dbskiter;
```

#### JDBC 驱动

```bash
# 需要安装 Oracle 驱动
pip install dbskiter[oracle]
```

---

## 获取帮助

如果以上文档未解决你的问题：

1. 📖 [完整文档站](https://magiczc.github.io/dbskiter/)
2. 🔍 [搜索已有 Issue](https://github.com/magicCzc/dbskiter/issues)
3. 🆕 [提交新 Issue](https://github.com/magicCzc/dbskiter/issues/new)
4. 💬 微信群（见 README.md）

提交 Issue 时请包含：

- `dbskiter --version` 输出
- 操作系统 + Python 版本
- 完整复现步骤
- 预期行为 vs 实际行为
- `--debug` 模式下的完整日志

---

**最后更新**：2026-07-24
