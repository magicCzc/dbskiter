---
name: db-security
description: |
  数据库安全审计，支持SQL注入检测、敏感数据扫描、权限审计、登录安全监控、审计日志分析、密码策略检查、配置安全审计。

  使用场景：
  - 用户说"安全检查" -> 执行 audit
  - 用户说"检测注入" -> 执行 sql-injection
  - 用户说"扫描敏感数据" -> 执行 sensitive-data
  - 用户说"安全评分" -> 执行 score
  - 用户说"检查权限" -> 执行 permissions
  - 用户说"登录安全" -> 执行 login-security
  - 用户说"审计日志" -> 执行 audit-log
  - 用户说"高危操作" -> 执行 high-risk
  - 用户说"密码策略" -> 执行 password-policy
  - 用户说"弱密码" -> 执行 weak-passwords
  - 用户说"配置安全" -> 执行 config

  用法：
  - python -m dbskiter --output-mode=ai --database=<name> security audit
  - python -m dbskiter --output-mode=ai --database=<name> security sql-injection "<SQL>"
  - python -m dbskiter --output-mode=ai --database=<name> security sensitive-data
  - python -m dbskiter --output-mode=ai --database=<name> security score
  - python -m dbskiter --output-mode=ai --database=<name> security permissions
  - python -m dbskiter --output-mode=ai --database=<name> security login-security
  - python -m dbskiter --output-mode=ai --database=<name> security audit-log
  - python -m dbskiter --output-mode=ai --database=<name> security high-risk
  - python -m dbskiter --output-mode=ai --database=<name> security password-policy
  - python -m dbskiter --output-mode=ai --database=<name> security weak-passwords
  - python -m dbskiter --output-mode=ai --database=<name> security config
---

# 数据库安全 Skill

## 安全原则

本Skill的大部分操作为只读查询和检测，但部分命令涉及安全评估：

| 规则 | 说明 |
|------|------|
| 只读检测 | audit/score/permissions等命令均为只读查询 |
| 注入检测不执行SQL | sql-injection只分析SQL文本，不执行被检测的SQL |
| 敏感数据扫描只读 | sensitive-data只采样查询，不修改数据 |
| 密码策略只检查 | password-policy/weak-passwords只检查策略，不修改密码 |
| 配置审计只读 | config命令只读取配置，不修改配置 |

## 何时使用

当用户提到以下关键词时，使用此skill：

| 用户说法 | 执行命令 | 说明 |
|---------|---------|------|
| "安全检查" | `python -m dbskiter --output-mode=ai --database=<name> security audit` | 完整安全审计 |
| "有注入风险吗" | `python -m dbskiter --output-mode=ai --database=<name> security sql-injection "<SQL>"` | SQL注入检测 |
| "有敏感数据吗" | `python -m dbskiter --output-mode=ai --database=<name> security sensitive-data` | 敏感数据扫描 |
| "安全评分多少" | `python -m dbskiter --output-mode=ai --database=<name> security score` | 安全评分 |
| "检查权限" | `python -m dbskiter --output-mode=ai --database=<name> security permissions` | 权限审计 |
| "登录安全" | `python -m dbskiter --output-mode=ai --database=<name> security login-security` | 登录安全监控 |
| "审计日志" | `python -m dbskiter --output-mode=ai --database=<name> security audit-log` | 审计日志分析 |
| "高危操作" | `python -m dbskiter --output-mode=ai --database=<name> security high-risk` | 高危操作检测 |
| "密码策略" | `dbskiter --output-mode=ai --database=<name> security password-policy` | 密码策略检查 |
| "弱密码" | `dbskiter --output-mode=ai --database=<name> security weak-passwords` | 弱密码检查 |
| "配置安全" | `dbskiter --output-mode=ai --database=<name> security config` | 配置安全审计 |

## 核心命令

### 1. 完整安全审计
```bash
python -m dbskiter --database=<数据库名> security audit
```
**输出**：安全评分 + 所有风险项 + 修复建议

### 2. SQL注入检测
```bash
python -m dbskiter --database=<数据库名> security sql-injection "SELECT * FROM users WHERE id = %s" --params='{"id": "1 OR 1=1"}'
```
**输出**：风险评分、注入类型、修复建议

**检测原理**：
- 静态分析SQL语句中的用户输入痕迹（注释符、引号不平衡、字符串截断等）
- 参数值中的多语句（分号+SQL关键字）、UNION注入、时间盲注检测
- 正常业务逻辑中的OR条件、UNION查询不会产生误报

**参数**：
- `sql`（必需）：SQL语句

**可选参数**：
- `--params`：SQL参数（JSON格式）

### 3. 敏感数据扫描
```bash
python -m dbskiter --database=<数据库名> security sensitive-data
```
**功能**：扫描所有表，识别身份证、手机号、邮箱等敏感数据

**可选参数**：
- `--tables`：指定表（逗号分隔）
- `--sample-size`：每表采样行数（默认100）

### 4. 安全评分
```bash
python -m dbskiter --database=<数据库名> security score
```
**输出**：总体评分、各维度得分、扣分项

### 5. 权限审计
```bash
python -m dbskiter --database=<数据库名> security permissions
```
**输出**：用户权限列表、过度授权警告

### 6. 登录安全监控
```bash
dbskiter --database=<数据库名> security login-security
```
**输出**：登录失败统计、异常登录IP、暴力破解检测

**可选参数**：
- `--hours`：检查最近多少小时（默认24）

### 7. 审计日志分析
```bash
dbskiter --database=<数据库名> security audit-log
```
**输出**：用户操作记录、DDL变更、权限变更

**可选参数**：
- `--hours`：分析最近多少小时（默认24）
- `--users`：指定用户（逗号分隔）

### 8. 高危操作检测
```bash
dbskiter --database=<数据库名> security high-risk
```
**输出**：DROP/DELETE/TRUNCATE等高危操作记录

**可选参数**：
- `--hours`：检查最近多少小时（默认24）

### 9. 密码策略检查
```bash
dbskiter --database=<数据库名> security password-policy
```
**输出**：当前密码策略、合规性检查、改进建议

### 10. 弱密码检查
```bash
dbskiter --database=<数据库名> security weak-passwords
```
**输出**：弱密码用户列表、空密码用户、风险等级

### 11. 配置安全审计
```bash
dbskiter --database=<数据库名> security config
```
**输出**：配置安全问题、推荐值、风险等级

## 数据库支持

| 数据库 | SQL注入检测 | 敏感数据扫描 | 权限审计 | 登录安全 | 密码策略 | 配置安全 | 状态 |
|-------|------------|------------|---------|---------|---------|---------|------|
| MySQL | 支持 | 支持 | 支持 | 支持 | 支持 | 支持 | 生产就绪 |
| Oracle | 支持 | 支持 | 支持 | 支持 | 支持 | 支持 | 生产就绪 |
| PostgreSQL | 支持 | 支持 | 支持 | 支持 | 支持 | 支持 | 生产就绪 |
| SQL Server | 支持 | 支持 | 支持 | 支持 | 支持 | 支持 | 生产就绪 |
| ClickHouse | 支持 | 支持 | 支持 | 部分支持 | 部分支持 | 支持 | 生产就绪 |
| SQLite | 支持 | 支持 | 支持 | 不支持 | 不支持 | 支持 | 生产就绪 |
| 通用(Generic) | 支持 | 支持 | 基础 | 不支持 | 不支持 | 基础 | 可用 |

**通用安全审计说明**：

通用安全审计器为任意 JDBC 兼容数据库提供基础安全审计能力：
- SQL注入检测：基于 AST 静态分析，不依赖数据库类型，完全支持
- 敏感数据扫描：通过标准 SQL 和 INFORMATION_SCHEMA 扫描所有表，自动探测列名模式和数据内容
- 权限审计（基础）：通过 INFORMATION_SCHEMA.TABLE_PRIVILEGES 获取权限信息，探测活跃会话作为用户数量代理
- 配置审计（基础）：查询数据库版本、大小、表数量，评估容量风险和结构复杂度
- 支持的数据库：Trino、Presto、DuckDB、H2、Derby 等任何 JDBC 数据库

**ClickHouse 安全特性**：
- SQL注入检测：基于AST分析，支持参数化查询建议
- 敏感数据扫描：支持身份证、手机号、邮箱等模式识别
- 权限审计：基于RBAC的用户角色分析，检查ALL权限
- 登录安全：检查无密码认证用户
- 密码策略：检查默认用户密码配置
- 配置安全：检查SSL、远程访问、查询日志配置

**SQLite 安全特性**：
- SQL注入检测：基于AST分析
- 敏感数据扫描：支持所有表扫描
- 权限审计：文件权限检查（POSIX系统）
- 配置安全：检查journal_mode、synchronous、secure_delete、foreign_keys

**SQL Server 安全特性**：
- SQL注入检测：基于AST分析，支持参数化查询建议
- 敏感数据扫描：支持身份证、手机号、邮箱等模式识别
- 权限审计：检查sysadmin角色成员、sa账户状态
- 登录安全：监控登录失败、异常IP
- 密码策略：检查Windows密码策略配置
- 配置安全：检查xp_cmdshell、CLR等安全配置

## AI决策流程

### 场景1：用户说"做安全检查"

```
步骤1：执行 dbskiter --database=<name> security audit
步骤2：解读安全评分和风险项
步骤3：按严重程度列出需要修复的问题
步骤4：提供修复命令或建议
```

### 场景2：用户说"这个SQL有注入风险吗"

```
步骤1：执行 dbskiter --database=<name> security sql-injection "<SQL>"
步骤2：解读风险评分和注入类型
步骤3：如果风险评分>70，详细说明风险点
步骤4：提供安全的写法（参数化查询）
```

### 场景3：用户说"有敏感数据暴露吗"

```
步骤1：执行 dbskiter --database=<name> security sensitive-data
步骤2：列出发现的敏感字段
步骤3：建议加密或脱敏方案
```
