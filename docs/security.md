<!--
文件功能：DBSKiter 安全模型详解
作者：MagiCzc
创建时间：2026-07-24
最后修改：2026-07-24
-->

# 安全模型详解

DBSKiter 设计上考虑了**三层纵深防御**，确保在 AI 时代数据库操作的安全性。

---

## 1. 三层纵深防御

```
┌────────────────────────────────────────────────────────┐
│  Layer 1: AI 层规则引擎                                │
│  ──────────────────────────                            │
│  机制：AI 提示词 + Skill 规则                          │
│  能力：禁止 AI 调用写操作 Skill                        │
│  适用：MCP 集成、Cursor/Claude AI                      │
└────────────────────────────────────────────────────────┘
                          ↓
┌────────────────────────────────────────────────────────┐
│  Layer 2: CLI 层中间件                                 │
│  ──────────────────────────                            │
│  机制：ReadOnlyEnforcer 拦截器                        │
│  触发：DBSKITER_READ_ONLY=true 环境变量               │
│  能力：拦截写命令 (INSERT/UPDATE/DELETE/DDL)          │
└────────────────────────────────────────────────────────┘
                          ↓
┌────────────────────────────────────────────────────────┐
│  Layer 3: 数据库层物理权限                             │
│  ──────────────────────────                            │
│  机制：MySQL/PG 用户授权                              │
│  能力：账号无写权限，从根本上无法执行写操作            │
│  这是最强的安全屏障                                    │
└────────────────────────────────────────────────────────┘
```

### 1.1 三层关系

| 层级 | 触发条件 | 拦截能力 | 失败时 |
|------|----------|----------|--------|
| L1 AI | AI 调用 Skill | 拦截高危 Skill | AI 收到错误 |
| L2 CLI | `DBSKITER_READ_ONLY=true` | 拦截写命令 | 提示升级权限 |
| L3 DB | 数据库账号权限 | 物理拦截 | 数据库拒绝 |

**推荐组合**：同时启用 L2 + L3，AI 误调用也能在 L2 拦截，物理账号失误由 L3 兜底。

---

## 2. 凭证安全

### 2.1 凭证传递方式对比

| 方式 | 命令 | 安全度 | 适用 |
|------|------|--------|------|
| `--password-stdin` | `echo "xxx" \| dbskiter ...` | ⭐⭐⭐⭐⭐ | CI/CD、脚本 |
| `--password-file` | `dbskiter --password-file ~/.pwd ...` | ⭐⭐⭐⭐ | 生产 |
| 环境变量 | `export DB_PASSWORD=xxx` | ⭐⭐⭐ | 开发 |
| `.env` 文件 | 写在 `.env` 中 | ⭐⭐⭐ | 本地 |
| `--password` 参数 | `dbskiter -p xxx` | ⭐ | **禁止生产** |

### 2.2 避免 shell 历史记录

```bash
# ✗ 错误：会进 shell 历史
dbskiter -p mysecret monitor health

# ✓ 正确：用前导空格（很多 shell 支持 HISTCONTROL=ignorespace）
dbskiter -p mysecret monitor health  # 注意 mysecret 前的空格

# ✓ 正确：用文件
echo "mysecret" > ~/.db_password
chmod 600 ~/.db_password
dbskiter --password-file ~/.db_password monitor health

# ✓ 正确：用 stdin（最佳实践）
echo "mysecret" | dbskiter --password-stdin monitor health
```

### 2.3 避免 ps 命令泄露

```bash
# ✗ 错误：密码在命令行，所有用户可见
ps aux | grep dbskiter
# root  1234  dbskiter --password=mysecret monitor

# ✓ 正确：用环境变量
export MYSQL_PWD=mysecret
dbskiter monitor health
# 不会出现在 ps 命令中
```

支持的密码环境变量：

| 数据库 | 环境变量 |
|--------|----------|
| MySQL/MariaDB | `MYSQL_PWD` |
| PostgreSQL | `PGPASSWORD` |
| Oracle | 无（需用文件） |
| SQL Server | 无（需用文件） |

---

## 3. SQL 注入防护

### 3.1 多层防护

```python
# dbskiter/db_security/sql_injection_detector.py
- AST 解析（sqlparse）识别注入模式
- 表名白名单
- 参数化查询强制
- 值转义
```

### 3.2 防护机制

#### 1. AST 解析

```python
# 检测示例
sql = "SELECT * FROM users WHERE id = 1 OR 1=1"
ast = sqlparse.parse(sql)[0]
# → 识别出 OR 1=1 模式
# → 标记为可疑
```

#### 2. 表名白名单

```python
# 配置示例
ALLOWED_TABLES = ['users', 'orders', 'products']

# 执行前校验
if table_name not in ALLOWED_TABLES:
    raise PermissionError(f"Table {table_name} not in whitelist")
```

#### 3. 参数化查询

```python
# ✓ 安全：参数化
cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))

# ✗ 危险：字符串拼接
cursor.execute(f"SELECT * FROM users WHERE id = {user_id}")
```

#### 4. 值转义

```python
# sqlparse 转义
from sqlparse import format
sql_safe = format(sql, keyword_case='upper', strip_comments=True)
```

### 3.3 检测规则

| 规则 | 描述 | 严重度 |
|------|------|--------|
| `OR 1=1` | 永真条件 | 高 |
| `UNION SELECT` | 联合查询注入 | 高 |
| `--` 注释 | SQL 注释绕过 | 中 |
| `xp_cmdshell` | SQL Server 命令执行 | 严重 |
| `DROP TABLE` | 危险操作 | 中 |
| `; 多语句` | 堆叠注入 | 高 |

---

## 4. 只读模式

### 4.1 启用

```bash
# 临时启用
export DBSKITER_READ_ONLY=true
dbskiter monitor health  # 正常执行
dbskiter sql execute "INSERT ..."  # 拒绝
```

```bash
# 永久启用（写到 ~/.bashrc）
echo 'export DBSKITER_READ_ONLY=true' >> ~/.bashrc
```

### 4.2 拦截的命令

```python
READ_ONLY_FORBIDDEN = [
    "sql execute --write",
    "sql batch",
    "scheduler backup-restore",  # 恢复可写
    "audit ddl --apply",
    "lock kill",
]
```

### 4.3 限制项

只读模式只拦截 DBSKiter 的命令，**不替代数据库层权限**。如果账号本身有写权限，DBSKiter 只读模式被绕过时仍能执行写操作（虽然目前 DBSKiter 不会绕过自己）。

**正确做法**：数据库账号最小权限 + DBSKiter 只读模式 + AI 规则。

---

## 5. 审计日志

### 5.1 日志内容

DBSKiter 记录所有操作的审计日志：

```json
{
  "timestamp": "2026-07-24T10:30:00+08:00",
  "user": "chenzc",
  "command": "diagnose slow-queries",
  "database": "jump",
  "args": ["--top=10"],
  "status": "success",
  "execution_time_ms": 234,
  "result_summary": "Found 5 slow queries"
}
```

### 5.2 日志位置

```
~/.dbskiter/
├── audit/
│   ├── audit-2026-07.log
│   ├── audit-2026-07-24.log
│   └── archive/
└── history/
    └── history.db  # SQLite
```

### 5.3 日志保留

```yaml
# config.yaml
audit:
  retention_days: 90
  archive_after_days: 30
  max_log_size_mb: 100
```

### 5.4 日志查询

```bash
# 查看审计日志
dbskiter audit log --hours=24

# 按命令过滤
dbskiter audit log --command=sql.execute

# 按用户过滤
dbskiter audit log --user=chenzc
```

---

## 6. 写操作保护

### 6.1 写操作清单

DBSKiter 提供的写操作（需明确启用）：

| 命令 | 操作 | 是否可逆 |
|------|------|----------|
| `scheduler backup` | 备份 | 否（增加存储） |
| `scheduler backup-restore` | 恢复 | 是（破坏性） |
| `lock kill` | 终止事务 | 是 |
| `audit ddl --apply` | 执行 DDL | 部分可逆 |
| `sql execute` (写) | 写 SQL | 否 |

### 6.2 强制确认

写操作要求 `--force` 或 `--confirm` 确认：

```bash
# 恢复数据库（需确认）
dbskiter scheduler backup-restore /backups/dump.sql --confirm

# 终止事务（需 force）
dbskiter lock kill 12345 --force

# 执行 DDL（需 force）
dbskiter audit ddl "ALTER TABLE users ADD COLUMN age INT" --apply --force
```

### 6.3 影响预览

DBSKiter 在执行写操作前会预览影响：

```bash
$ dbskiter audit ddl "DROP TABLE users" --dry-run

⚠️ 即将执行危险操作：
  SQL: DROP TABLE users
  影响: 删除表 users（预估 1000000 行）
  风险: 不可逆

确认执行? [y/N]:
```

---

## 7. 敏感数据保护

### 7.1 脱敏

DBSKiter 默认脱敏敏感字段（`--mask-sensitive` 默认开启）：

```json
{
  "raw_metrics": {
    "username": "***",
    "password": "***",
    "email": "***@example.com"
  }
}
```

### 7.2 关闭脱敏

```bash
# 仅在安全环境关闭
dbskiter --no-mask --database=jump monitor health
```

### 7.3 自定义脱敏规则

```yaml
# config.yaml
masking:
  enabled: true
  rules:
    - field_pattern: "email"
      mask_type: "email"  # a***@example.com
    - field_pattern: "phone"
      mask_type: "phone"  # 138****1234
    - field_pattern: "id_card"
      mask_type: "full"   # ****************
```

---

## 8. 网络安全

### 8.1 TLS/SSL

```bash
# MySQL SSL
dbskiter --url "mysql://user:pwd@host:3306/db?ssl_mode=REQUIRED" monitor

# PostgreSQL SSL
dbskiter --url "postgresql://user:pwd@host:5432/db?sslmode=require" monitor
```

### 8.2 SSH 隧道

```bash
# 本地端口转发
ssh -L 3306:localhost:3306 user@bastion

# 然后用 localhost
dbskiter --host=127.0.0.1 monitor health
```

### 8.3 防火墙规则

```bash
# 仅允许应用服务器访问
iptables -A INPUT -p tcp --dport 3306 -s 10.0.0.0/8 -j ACCEPT
iptables -A INPUT -p tcp --dport 3306 -j DROP
```

---

## 9. 推荐安全配置

### 9.1 数据库账号（最小权限）

```sql
-- 监控账号
CREATE USER 'dbskiter_monitor'@'10.0.0.%' IDENTIFIED BY 'xxx';
GRANT SELECT, PROCESS, REPLICATION CLIENT ON *.* TO 'dbskiter_monitor'@'10.0.0.%';

-- 备份账号
CREATE USER 'dbskiter_backup'@'10.0.0.%' IDENTIFIED BY 'xxx';
GRANT SELECT, LOCK TABLES, RELOAD ON *.* TO 'dbskiter_backup'@'10.0.0.%';

-- 巡检账号
CREATE USER 'dbskiter_inspector'@'10.0.0.%' IDENTIFIED BY 'xxx';
GRANT SELECT, SHOW DATABASES ON *.* TO 'dbskiter_inspector'@'10.0.0.%';
```

### 9.2 DBSKiter 配置

```bash
# ~/.bashrc 或 /etc/profile.d/dbskiter.sh

# 启用只读模式
export DBSKITER_READ_ONLY=true

# 审计日志目录
export DBSKITER_AUDIT_DIR=/var/log/dbskiter

# 禁用明文密码
unset DB_PASSWORD
unset MYSQL_PWD
```

### 9.3 MCP 配置（Claude Desktop）

```json
{
  "mcpServers": {
    "dbskiter": {
      "command": "dbskiter-mcp",
      "env": {
        "DBSKITER_READ_ONLY": "true",
        "DB_HOST": "monitoring-proxy.internal",
        "DB_USER": "dbskiter_monitor",
        "DB_PASSWORD": "${DB_MONITOR_PASSWORD}",
        "DB_NAME": "production"
      }
    }
  }
}
```

### 9.4 AI 提示词约束

在 Skill 文档中明确写：

```markdown
# SKILL.md

## 限制
- 禁止调用 sql.execute 的写操作
- 禁止调用 scheduler.backup-restore
- 禁止调用 lock.kill
- 禁止调用 audit.ddl --apply
```

---

## 10. 安全审计清单

部署前检查：

- [ ] 数据库账号是专用监控账号（不是 root/admin）
- [ ] 账号权限最小化（仅 SELECT + 必要权限）
- [ ] 数据库账号绑定 IP 白名单
- [ ] DBSKITER_READ_ONLY=true 已启用
- [ ] 密码通过 --password-stdin 或环境变量传递
- [ ] 审计日志开启并定期归档
- [ ] 敏感数据脱敏启用
- [ ] 数据库连接启用 SSL/TLS
- [ ] 防火墙规则限制访问源
- [ ] AI 提示词中明确禁止写操作
- [ ] 定期审计操作日志
- [ ] 定期轮换数据库密码

---

## 11. 事件响应

### 11.1 发现可疑操作

```bash
# 1. 查看审计日志
dbskiter audit log --hours=24

# 2. 查看历史命令
dbskiter history --hours=24

# 3. 立即停止服务
systemctl stop dbskiter

# 4. 修改凭证
# 5. 审计数据库
```

### 11.2 报告安全漏洞

- 📧 邮件：magiczc@139.com
- 🔒 加密方式：见 SECURITY.md（如有）

---

## 12. 合规性

### 12.1 等保 2.0

DBSKiter 满足等保 2.0 部分要求：

- ✅ 身份鉴别（专用账号）
- ✅ 访问控制（最小权限）
- ✅ 安全审计（审计日志）
- ✅ 入侵防范（只读模式、SQL 注入检测）
- ✅ 数据保密（敏感数据脱敏、SSL）

### 12.2 GDPR

- ✅ 数据脱敏（个人邮箱、电话、身份证）
- ✅ 审计日志（操作可追溯）
- ✅ 数据最小化（只读账号仅 SELECT）

### 12.3 SOC 2

- ✅ 访问控制
- ✅ 审计日志
- ✅ 变更管理（CHANGELOG）

---

## 13. 未来计划

- 🔐 集成 Vault / AWS Secrets Manager 凭证管理
- 🔐 集成 SSO（SAML / OIDC）
- 🔐 集成 RBAC（基于角色的访问控制）
- 🔐 完整加密的审计日志

---

**最后更新**：2026-07-24
