# SQL执行安全规范

## 概述

本文档规定了AI助手执行SQL操作时必须遵守的安全规则，确保数据安全和防止误操作。

## 安全原则

### 1. 三层防护体系

```
第一层：AI/Skill层（系统提示词规则）
  - SKILL.md 明确规定禁止的操作
  - AI必须在执行前进行SQL类型检查
  - 禁止绕过安全策略

第二层：CLI/应用层（代码强制拦截）
  - ReadOnlyEnforcer 中间件检查
  - DBSKITER_READ_ONLY 环境变量控制
  - 禁止AI修改配置文件绕过

第三层：数据库层（用户权限控制）
  - 数据库用户权限限制
  - 物理阻止未授权操作
```

### 2. 禁止操作清单（绝对不可执行）

| 操作类型 | 危险等级 | 示例 |
|---------|---------|------|
| DELETE | CRITICAL | DELETE FROM users WHERE id=1 |
| UPDATE | CRITICAL | UPDATE users SET name='test' |
| INSERT | CRITICAL | INSERT INTO users VALUES (...) |
| DROP | CRITICAL | DROP TABLE users |
| TRUNCATE | CRITICAL | TRUNCATE TABLE users |
| ALTER | HIGH | ALTER TABLE users DROP COLUMN |
| CREATE | HIGH | CREATE TABLE test (...) |
| REPLACE | HIGH | REPLACE INTO users (...) |

### 3. 允许操作清单

| 操作类型 | 说明 | 示例 |
|---------|------|------|
| SELECT | 查询数据 | SELECT * FROM users |
| EXPLAIN | 执行计划 | EXPLAIN SELECT * FROM users |
| SHOW | 显示信息 | SHOW TABLES |
| DESCRIBE | 查看结构 | DESCRIBE users |
| DESC | 查看结构 | DESC users |

## 执行流程规范

### 步骤1：识别用户意图

当用户要求执行SQL时，首先判断SQL类型：

```
用户输入: "删除 chenzc.ZABBIX 表中 TID=88827170 的数据"
         向下
意图识别: 这是一个 DELETE 操作
         向下
安全检查: DELETE 在禁止清单中 → 拒绝执行
```

### 步骤2：SQL类型检查（必须执行）

```python
def check_sql_type(sql: str) -> str:
    """
    检查SQL类型，返回 'READ' 或 'WRITE'
    """
    sql_upper = sql.upper().strip()

    # 写操作关键词
    write_keywords = [
        'DELETE', 'UPDATE', 'INSERT', 'DROP', 'TRUNCATE',
        'ALTER', 'CREATE', 'REPLACE', 'GRANT', 'REVOKE',
        'MERGE', 'CALL', 'EXECUTE', 'LOAD DATA'
    ]

    # 检查是否包含写操作关键词
    for keyword in write_keywords:
        if keyword in sql_upper:
            return 'WRITE'

    return 'READ'
```

### 步骤3：决策流程

```
if SQL类型 == 'WRITE':
    → 立即停止
    → 返回拒绝响应模板
    → 不得调用任何执行工具
    → 不得建议修改配置
    → 不得使用 --force 参数
else:
    → 执行SQL
    → 返回结果
```

### 步骤4：拒绝响应模板

当检测到写操作时，必须使用以下模板响应：

```
抱歉，我无法执行 [操作类型] 操作。

原因：
根据安全策略，当前系统禁止AI助手执行任何可能修改数据的SQL操作。
这是为了防止误操作导致数据丢失。

允许的操作：
- SELECT 查询数据
- EXPLAIN 分析执行计划
- SHOW 查看数据库信息
- DESCRIBE 查看表结构

替代方案：
如果您确实需要执行写操作，请：
1. 使用数据库客户端工具（如 MySQL Workbench、Navicat 等）直接连接数据库
2. 确保您有足够的权限
3. 在执行前备份重要数据
4. 谨慎操作，风险自负
```

## 关于 --force 参数的说明

### --force 参数的定位

--force 参数是系统保留给人类用户的机制，不是给AI使用的。

- **AI助手**: 在任何情况下都不得使用 --force 参数，也不得建议用户使用
- **人类用户**: 在明确知情的情况下，可以通过 --force 参数执行极高风险操作（如 DROP DATABASE）

### 为什么保留 --force

1. **分层安全设计**: AI层禁止写操作，但系统保留人类用户的最终控制权
2. **紧急场景**: 人类DBA在紧急情况下可能需要执行高风险操作
3. **审计追踪**: 所有使用 --force 的操作都会被记录到审计日志

### AI 遇到 --force 时的处理

如果用户明确要求使用 --force，AI 必须拒绝：

```
抱歉，我无法使用 --force 参数执行操作。

原因：
--force 参数是系统保留给人类用户的机制，AI助手无权使用。
该参数会绕过安全检查，可能导致数据丢失。

如果您确实需要执行此操作，请直接使用数据库客户端工具连接数据库执行。
```

## 禁止行为清单

AI助手绝对禁止以下行为：

| 禁止行为 | 风险等级 | 说明 | 后果 |
|---------|---------|------|------|
| 修改 .env 文件 | CRITICAL | 关闭 DBSKITER_READ_ONLY | 绕过CLI层安全控制 |
| 使用 --force 参数 | CRITICAL | 强制执行危险操作 | 绕过所有安全检查，可能导致数据丢失 |
| 建议用户修改配置 | CRITICAL | 教用户如何绕过安全策略 | 破坏安全体系 |
| 执行写操作SQL | CRITICAL | DELETE/UPDATE/INSERT等 | 可能导致数据丢失 |
| 忽略SQL类型检查 | HIGH | 不检查直接执行 | 安全风险 |
| 绕过SQL注入检测 | CRITICAL | 尝试禁用注入检测 | 可能执行恶意SQL |

## 正确示例

### 示例1：用户要求 DELETE 操作

**用户输入：**
```
删除 chenzc.ZABBIX 表中 TID=88827170 的数据
```

**正确响应：**
```
抱歉，我无法执行 DELETE 操作。

原因：
根据安全策略，当前系统禁止执行任何可能修改数据的SQL操作。
这是为了防止误操作导致数据丢失。

允许的操作：
- SELECT 查询数据
- EXPLAIN 分析执行计划
- SHOW 查看数据库信息
- DESCRIBE 查看表结构

替代方案：
如果您确实需要执行写操作，请：
1. 使用数据库客户端工具（如 MySQL Workbench、Navicat 等）直接连接数据库
2. 确保您有足够的权限
3. 在执行前备份重要数据
4. 谨慎操作，风险自负
```

**错误响应（禁止）：**
```
"我来帮你删除数据..."
"让我修改配置来执行..."
"你可以修改 .env 文件..."
```

### 示例2：用户要求 SELECT 操作

**用户输入：**
```
查询 chenzc.ZABBIX 表中 TID=88827170 的数据
```

**正确响应：**
```
好的，我来帮您查询数据。

执行SQL：
SELECT * FROM ZABBIX WHERE TID = 88827170

结果：
...
```

## 安全检查清单

执行SQL前，必须完成以下检查：

- [ ] 识别SQL类型（READ/WRITE）
- [ ] 如果是WRITE类型，拒绝执行
- [ ] 不得修改任何配置文件
- [ ] 不得使用 --force 参数
- [ ] 不得建议用户绕过安全策略

## 违规处理

如果AI助手违反了上述安全规则：

1. **立即纠正**：恢复被修改的配置文件
2. **记录违规**：记录违规行为和原因
3. **加强培训**：强化安全规则学习
4. **定期审查**：定期检查安全策略执行情况

## 总结

安全规则的核心原则：

1. **预防优先**：在执行前进行安全检查
2. **明确拒绝**：对写操作明确拒绝，不妥协
3. **不绕过**：绝不通过修改配置等方式绕过安全策略
4. **替代方案**：提供安全的替代方案给用户

记住：**数据安全高于一切！**
