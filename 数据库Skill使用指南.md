# 数据库Skill使用指南

## 文档信息
- **文档版本**: 1.0
- **创建时间**: 2026-04-24
- **适用数据库**: MySQL, Oracle, PostgreSQL

---

## 目录
1. [Skill概览](#skill概览)
2. [快速开始](#快速开始)
3. [详细使用指南](#详细使用指南)
4. [场景化使用示例](#场景化使用示例)
5. [测试脚本](#测试脚本)
6. [故障排查](#故障排查)

---

## Skill概览

### 核心Skill列表

| Skill名称 | 功能描述 | 核心命令数 | 使用频率 |
|-----------|----------|------------|----------|
| **db-diagnose** | 数据库诊断与优化 | 7 | ⭐⭐⭐⭐⭐ |
| **db-inspector** | 数据库实例巡检与报告 | 9 | ⭐⭐⭐⭐⭐ |
| **db-lock-analyzer** | 锁分析与死锁检测 | 4 | ⭐⭐⭐ |
| **db-monitor** | 数据库健康监控 | 9 | ⭐⭐⭐⭐⭐ |
| **db-security** | 数据库安全审计 | 11 | ⭐⭐⭐⭐ |
| **db-sql-auditor** | SQL全生命周期审核 | 9 | ⭐⭐⭐⭐ |
| **sql-master** | SQL智能助手 | 9 | ⭐⭐⭐⭐⭐ |

### 功能矩阵

```
┌─────────────────────────────────────────────────────────────────┐
│                      数据库管理生命周期                          │
├─────────────┬─────────────┬─────────────┬─────────────────────┤
│   开发阶段   │   测试阶段   │   上线阶段   │     运维阶段         │
├─────────────┼─────────────┼─────────────┼─────────────────────┤
│ sql-master  │ db-security │ db-monitor  │ db-inspector        │
│   - schema  │  - 注入检测  │  - 健康检查  │   - 巡检            │
│   - rewrite │  - 敏感数据  │  - 容量预测  │   - 报告            │
│   - analyze │  - 权限审计  │  - 异常检测  │   - 风险预测        │
├─────────────┼─────────────┼─────────────┼─────────────────────┤
│db-sql-auditor│db-sql-auditor│ db-diagnose │ db-diagnose         │
│   - sql审核  │   - DDL分析  │   - 慢查询   │   - 性能快照        │
│   - 规则检查 │             │   - 索引推荐 │   - 瓶颈分析        │
├─────────────┴─────────────┴─────────────┼─────────────────────┤
│              全阶段通用                  │ db-lock-analyzer    │
│           db-security audit              │   - 死锁检测        │
│           (安全审计)                     │   - 锁分析          │
└─────────────────────────────────────────┴─────────────────────┘
```

---

## 快速开始

### 1. 配置多实例（推荐方式）

在 `.env` 文件中使用 `DB_{别名}_*` 格式配置多个数据库：

```bash
# MySQL - 示例库1（示例配置，请替换为实际值）
DB_JUMP_HOST=your_mysql_host
DB_JUMP_PORT=3306
DB_JUMP_USER=your_username
DB_JUMP_PASSWORD=your_password
DB_JUMP_NAME=your_database
DB_JUMP_DIALECT=mysql+pymysql

# MySQL - 示例库2（示例配置，请替换为实际值）
DB_CHENZC_HOST=your_mysql_host
DB_CHENZC_PORT=3306
DB_CHENZC_USER=your_username
DB_CHENZC_PASSWORD=your_password
DB_CHENZC_NAME=your_database
DB_CHENZC_DIALECT=mysql+pymysql

# Oracle - 示例库（示例配置，请替换为实际值）
DB_ORCL_HOST=your_oracle_host
DB_ORCL_PORT=1521
DB_ORCL_USER=your_username
DB_ORCL_PASSWORD=your_password
DB_ORCL_SERVICE=your_service
DB_ORCL_DIALECT=oracle+jdbc
```

### 2. 基础连接测试

```bash
# 测试数据库连接（使用别名）
dbskiter --database=jump sql "SELECT 1 as connection_test"
dbskiter --database=orcl sql "SELECT 1 FROM DUAL"

# 查看所有表
dbskiter --database=jump sql schema
```

### 3. 一键健康检查

```bash
# 快速健康检查
dbskiter --database=jump monitor health

# 生成综合报告
dbskiter --database=jump inspector report --output report.html
```

### 4. 常用快捷命令

```bash
# 设置别名（推荐添加到 ~/.bashrc 或 ~/.zshrc）
alias db='dbskiter --database=jump'
alias db-orcl='dbskiter --database=orcl'
alias db-health='dbskiter --database=jump monitor health'
alias db-slow='dbskiter --database=jump diagnose slow-queries'
alias db-security='dbskiter --database=jump security audit'
```

---

## 详细使用指南

---

## 一、db-diagnose（数据库诊断与优化）

### 1.1 功能说明
用于诊断数据库性能问题，包括慢查询分析、SQL诊断、索引推荐、性能快照和瓶颈分析。

### 1.2 核心命令

#### 1.2.1 性能快照
```bash
dbskiter --database=<数据库名> diagnose performance-snapshot
```
**功能**: 采集CPU、IO、内存、并发、锁等多维度性能指标
**适用场景**: 
- 数据库整体性能评估
- 容量规划前的基线采集
- 性能问题的全面诊断

**输出示例**:
```json
{
  "summary": "性能快照采集完成",
  "data": {
    "snapshot": {
      "timestamp": "2026-04-24T10:30:00",
      "metrics": [
        {
          "name": "active_session_ratio",
          "value": 75.5,
          "unit": "%",
          "category": "cpu",
          "severity": "high"
        }
      ],
      "slow_queries": [...],
      "active_sessions": 15,
      "total_sessions": 100
    },
    "bottlenecks": [...]
  }
}
```

#### 1.2.2 瓶颈分析
```bash
dbskiter --database=<数据库名> diagnose bottleneck
```
**功能**: 自动识别性能瓶颈并给出优化建议
**适用场景**: 数据库性能下降时的快速诊断

#### 1.2.3 慢查询分析
```bash
# 查看最近7天最慢的10个查询
dbskiter --database=<数据库名> diagnose slow-queries

# 只看前5条
dbskiter --database=<数据库名> diagnose slow-queries --limit=5

# 只看超过0.5秒的查询
dbskiter --database=<数据库名> diagnose slow-queries --min-duration=0.5
```

#### 1.2.4 SQL诊断
```bash
dbskiter --database=<数据库名> diagnose sql "SELECT * FROM users WHERE email = 'test@test.com'"
```
**输出**: 评分、问题列表、优化建议

#### 1.2.5 索引推荐
```bash
# 分析所有表
dbskiter --database=<数据库名> diagnose recommend-indexes

# 只分析指定表
dbskiter --database=<数据库名> diagnose recommend-indexes --table=users
```

#### 1.2.6 综合报告
```bash
dbskiter --database=<数据库名> diagnose report
```
**输出**: 慢查询 + 索引建议 + 锁情况 + 总体评分

### 1.3 决策流程

```
用户说"数据库慢了"
    ↓
执行 diagnose performance-snapshot
    ↓
查看 bottlenecks 确定瓶颈类型
    ↓
如果是慢查询 → 执行 diagnose slow-queries
    ↓
根据结果执行 diagnose recommend-indexes
    ↓
总结给用户
```

---

## 二、db-inspector（数据库实例巡检）

### 2.1 功能说明
支持配置检查、性能检查、安全检查、报告生成、智能巡检、异常检测、根因分析、风险预测。

### 2.2 核心命令

#### 2.2.1 执行完整巡检
```bash
dbskiter --database=<数据库名> inspector run
```
**评分标准**:
- 90-100：优秀
- 70-89：良好
- <70：需要关注

#### 2.2.2 生成报告
```bash
# HTML报告
dbskiter --database=<数据库名> inspector report --output report.html

# Markdown报告
dbskiter --database=<数据库名> inspector report --output report.md

# JSON报告
dbskiter --database=<数据库名> inspector report --output report.json
```

#### 2.2.3 基线管理
```bash
# 创建性能基线
dbskiter --database=<数据库名> inspector baseline --create
```

#### 2.2.4 智能巡检
```bash
dbskiter --database=<数据库名> inspector intelligent
```
**功能**: 异常检测、根因分析、风险预测、智能建议

#### 2.2.5 异常检测
```bash
dbskiter --database=<数据库名> inspector anomalies --metric=cpu_usage
```

#### 2.2.6 根因分析
```bash
dbskiter --database=<数据库名> inspector root-cause --issue="CPU飙升"
```

#### 2.2.7 风险预测
```bash
# 预测未来7天风险
dbskiter --database=<数据库名> inspector risks --days=7

# 预测未来30天风险
dbskiter --database=<数据库名> inspector risks --days=30
```

### 2.3 巡检类型

| 类型 | 说明 | 命令 |
|------|------|------|
| configuration | 配置检查 | `--type configuration` |
| performance | 性能检查 | `--type performance` |
| storage | 存储检查 | `--type storage` |
| security | 安全检查 | `--type security` |
| capacity | 容量检查 | `--type capacity` |

---

## 三、db-lock-analyzer（锁分析）

### 3.1 功能说明
数据库锁分析与死锁检测，支持当前锁分析、死锁检测、锁等待链追踪。

### 3.2 核心命令

#### 3.2.1 分析当前锁
```bash
dbskiter --database=<数据库名> lock analyze
```
**输出**: 总锁数、等待中锁数、已授予锁数

#### 3.2.2 检测死锁
```bash
dbskiter --database=<数据库名> lock deadlocks
```
**输出**: 死锁数量、涉及事务、解决建议

#### 3.2.3 追踪锁等待链
```bash
dbskiter --database=<数据库名> lock chains
```
**输出**: 锁等待链数量、链深度、阻塞源头

#### 3.2.4 终止事务
```bash
dbskiter --database=<数据库名> lock kill <transaction_id>
```
> **警告**: 谨慎使用，会强制终止事务

### 3.3 锁类型

- **TABLE**: 表锁
- **ROW**: 行锁
- **METADATA**: 元数据锁

---

## 四、db-monitor（健康监控）

### 4.1 功能说明
数据库健康监控，支持健康检查、异常检测、容量预测、趋势分析、基线对比。

### 4.2 核心命令

#### 4.2.1 健康检查
```bash
dbskiter --database=<数据库名> monitor health
```
**评分标准**:
- 90-100：优秀
- 70-89：良好
- <70：需要关注

**输出示例**:
```json
{
  "summary": "健康评分85分，状态良好",
  "score": 85,
  "status": "healthy",
  "components": {
    "performance": {"score": 90, "status": "healthy"},
    "resources": {"score": 80, "status": "warning"},
    "connections": {"score": 85, "status": "healthy"}
  }
}
```

#### 4.2.2 异常检测
```bash
dbskiter --database=<数据库名> monitor anomalies
```

#### 4.2.3 容量预测
```bash
# 磁盘容量
dbskiter --database=<数据库名> monitor capacity --resource=disk

# 内存容量
dbskiter --database=<数据库名> monitor capacity --resource=memory

# 连接数
dbskiter --database=<数据库名> monitor capacity --resource=connections
```

#### 4.2.4 高级容量预测
```bash
dbskiter --database=<数据库名> monitor capacity-advanced --resource=disk
```
**特点**:
- 自动选择最佳预测算法
- 提供置信度评估
- 更精确的预测结果

#### 4.2.5 趋势分析
```bash
dbskiter --database=<数据库名> monitor trend --metric=cpu_usage --days=7
```

#### 4.2.6 基线对比
```bash
dbskiter --database=<数据库名> monitor compare --metric=qps --value=1250 --baseline=2026-04-01
```

#### 4.2.7 采集指标
```bash
# 采集所有指标
dbskiter --database=<数据库名> monitor collect

# 只采集指定指标
dbskiter --database=<数据库名> monitor collect --metrics=qps,connections
```

#### 4.2.8 查看历史
```bash
dbskiter --database=<数据库名> monitor history connections_active --hours=24
```

---

## 五、db-security（安全审计）

### 5.1 功能说明
数据库安全审计，支持SQL注入检测、敏感数据扫描、权限审计、登录安全监控、审计日志分析、密码策略检查、配置安全审计。

### 5.2 核心命令

#### 5.2.1 完整安全审计
```bash
dbskiter --database=<数据库名> security audit
```
**输出**: 安全评分 + 所有风险项 + 修复建议

#### 5.2.2 SQL注入检测
```bash
dbskiter --database=<数据库名> security sql-injection "SELECT * FROM users WHERE id = %s" --params='{"id": "1 OR 1=1"}'
```

#### 5.2.3 敏感数据扫描
```bash
# 扫描所有表
dbskiter --database=<数据库名> security sensitive-data

# 扫描指定表
dbskiter --database=<数据库名> security sensitive-data --tables=users,orders

# 调整采样大小
dbskiter --database=<数据库名> security sensitive-data --sample-size=100
```

#### 5.2.4 安全评分
```bash
dbskiter --database=<数据库名> security score
```
**评分标准**:
| 分数 | 等级 | 说明 |
|------|------|------|
| 90-100 | A | 优秀 |
| 80-89 | B | 良好 |
| 70-79 | C | 一般，需要改进 |
| <70 | D | 差，存在严重风险 |

#### 5.2.5 权限审计
```bash
dbskiter --database=<数据库名> security permissions
```

#### 5.2.6 登录安全监控
```bash
dbskiter --database=<数据库名> security login-security --hours=24
```

#### 5.2.7 审计日志分析
```bash
dbskiter --database=<数据库名> security audit-log --hours=24 --users=admin,root
```

#### 5.2.8 高危操作检测
```bash
dbskiter --database=<数据库名> security high-risk --hours=24
```

#### 5.2.9 密码策略检查
```bash
dbskiter --database=<数据库名> security password-policy
```

#### 5.2.10 弱密码检查
```bash
dbskiter --database=<数据库名> security weak-passwords
```

#### 5.2.11 配置安全审计
```bash
dbskiter --database=<数据库名> security config
```

---

## 六、db-sql-auditor（SQL审核）

### 6.1 功能说明
SQL全生命周期审核，支持SQL规范审核、性能评估、DDL影响分析。

### 6.2 核心命令

#### 6.2.1 审核SQL
```bash
dbskiter --database=<数据库名> audit sql "SELECT * FROM users WHERE id = 1"
```
**评分标准**:
- 90-100：通过
- 80-89：警告
- <80：不通过

#### 6.2.2 DDL影响分析
```bash
dbskiter --database=<数据库名> audit ddl "ALTER TABLE users ADD COLUMN age INT"
```
**输出**: 预估执行时间、风险点、建议

#### 6.2.3 审核SQL文件
```bash
dbskiter --database=<数据库名> audit file queries.sql
```

#### 6.2.4 查看规则
```bash
dbskiter audit rules
```

#### 6.2.5 SQL优化
```bash
dbskiter --database=<数据库名> audit optimize "SELECT * FROM users WHERE age > 18"
```

#### 6.2.6 索引推荐
```bash
dbskiter --database=<数据库名> audit recommend-indexes "SELECT * FROM orders WHERE user_id = 1"
```

#### 6.2.7 执行计划分析
```bash
dbskiter --database=<数据库名> audit analyze-plan --plan="EXPLAIN输出"
```

#### 6.2.8 成本估算
```bash
dbskiter --database=<数据库名> audit estimate-cost "SELECT * FROM users"
```

#### 6.2.9 SQL重写
```bash
dbskiter --database=<数据库名> audit rewrite "SELECT * FROM users WHERE id = 1"
```

### 6.3 审核类型

- **syntax**: 语法规范
- **performance**: 性能规范
- **security**: 安全规范
- **style**: 编码风格
- **ddl**: DDL规范

---

## 七、sql-master（SQL助手）

### 7.1 功能说明
SQL智能助手，支持SQL执行、重写优化、质量分析、数据分析、智能补全、Schema查询、批量执行、数据导入导出。

### 7.2 核心命令

#### 7.2.1 执行SQL
```bash
# 基础查询
dbskiter --database=<数据库名> sql execute "SELECT * FROM users LIMIT 10"

# 带参数
dbskiter --database=<数据库名> sql execute "SELECT * FROM users WHERE age > %(age)s" --params='{"age": 18}'

# 限制返回行数
dbskiter --database=<数据库名> sql execute "SELECT * FROM orders" --limit=50

# 快捷写法
dbskiter --database=<数据库名> sql "SELECT * FROM users LIMIT 10"
```

#### 7.2.2 重写SQL优化
```bash
dbskiter --database=<数据库名> sql rewrite "SELECT * FROM users WHERE id = 1"
```
**功能**:
- 展开 `SELECT *` 为具体字段
- 优化 WHERE 条件
- 推荐索引
- 重写低效JOIN

#### 7.2.3 分析SQL质量
```bash
dbskiter --database=<数据库名> sql analyze "SELECT * FROM orders"
```
**评分标准**:
- 90-100分：A级（优秀）
- 80-89分：B级（良好）
- 70-79分：C级（一般）
- 60-69分：D级（较差）
- <60分：F级（危险）

#### 7.2.4 数据分析
```bash
dbskiter --database=<数据库名> sql data "SELECT * FROM orders WHERE created_at > '2024-01-01'"
```
**功能**: 分析查询结果的数据特征
- 每列的数据类型
- 空值数量
- 唯一值数量
- 数值列的统计（最小/最大/平均值）
- 示例值

#### 7.2.5 SQL智能补全
```bash
# 补全表名
dbskiter --database=<数据库名> sql complete "SELECT * FROM "

# 补全字段
dbskiter --database=<数据库名> sql complete "SELECT id, name, "

# 补全WHERE条件
dbskiter --database=<数据库名> sql complete "SELECT * FROM users WHERE "
```

#### 7.2.6 Schema查询
```bash
# 列出所有表
dbskiter --database=<数据库名> sql schema

# 查看指定表结构
dbskiter --database=<数据库名> sql schema --table=users
```

#### 7.2.7 导出数据
```bash
# 导出表为CSV
dbskiter --database=<数据库名> sql export --table=users --output=users.csv

# 导出为JSON
dbskiter --database=<数据库名> sql export --table=users --output=users.json --format=json

# 导出为SQL INSERT语句
dbskiter --database=<数据库名> sql export --table=users --output=users.sql --format=sql

# 导出查询结果
dbskiter --database=<数据库名> sql export --query="SELECT * FROM orders WHERE status='pending'" --output=pending_orders.csv

# 限制导出行数
dbskiter --database=<数据库名> sql export --table=users --output=users.csv --limit=1000
```

#### 7.2.8 导入数据
```bash
# 从CSV导入
dbskiter sql import users.csv --table=users

# 从JSON导入
dbskiter sql import users.json --table=users --format=json

# 从SQL文件导入
dbskiter sql import users.sql --format=sql

# 指定列名导入
dbskiter sql import data.csv --table=users --columns=id,name,email

# 调整批量大小
dbskiter sql import large_data.csv --table=users --batch-size=500
```

#### 7.2.9 流式导出大表
```bash
dbskiter sql export-stream --table=logs --output=logs.csv --batch-size=50000
```
**说明**: 流式导出适用于大表，分批读取避免内存溢出

---

## 场景化使用示例

### 场景1: 日常巡检（推荐每天执行）

```bash
#!/bin/bash
# daily_check.sh

echo "=== 数据库日常巡检 ==="
echo "巡检时间: $(date)"
echo ""

# 1. 健康检查
echo "[1/5] 健康检查..."
dbskiter --database=jump monitor health

# 2. 异常检测
echo "[2/5] 异常检测..."
dbskiter --database=jump monitor anomalies

# 3. 慢查询检查
echo "[3/5] 慢查询检查..."
dbskiter --database=jump diagnose slow-queries --limit=3

# 4. 容量预测
echo "[4/5] 容量预测..."
dbskiter --database=jump monitor capacity --resource=disk

# 5. 生成日报
echo "[5/5] 生成报告..."
dbskiter --database=jump inspector report --output daily_report_$(date +%Y%m%d).html

echo ""
echo "=== 巡检完成 ==="
```

### 场景2: SQL上线前审核

```bash
#!/bin/bash
# sql_review.sh

SQL="$1"

echo "=== SQL上线前审核 ==="
echo "待审核SQL: $SQL"
echo ""

# 1. SQL规范审核
echo "[1/4] SQL规范审核..."
dbskiter --database=jump audit sql "$SQL"

# 2. SQL质量分析
echo "[2/4] SQL质量分析..."
dbskiter --database=jump sql analyze "$SQL"

# 3. 注入风险检测
echo "[3/4] 注入风险检测..."
dbskiter --database=jump security sql-injection "$SQL"

# 4. 索引推荐
echo "[4/4] 索引推荐..."
dbskiter --database=jump diagnose sql "$SQL"

echo ""
echo "=== 审核完成 ==="
```

### 场景3: 性能优化

```bash
#!/bin/bash
# performance_optimization.sh

echo "=== 性能优化流程 ==="

# 1. 采集性能快照
echo "[1/5] 采集性能快照..."
dbskiter --database=jump diagnose performance-snapshot

# 2. 瓶颈分析
echo "[2/5] 瓶颈分析..."
dbskiter --database=jump diagnose bottleneck

# 3. 分析慢查询
echo "[3/5] 分析慢查询..."
dbskiter --database=jump diagnose slow-queries --limit=10

# 4. 获取索引建议
echo "[4/5] 获取索引建议..."
dbskiter --database=jump diagnose recommend-indexes

# 5. 验证优化效果
echo "[5/5] 请手动验证优化后的SQL效果"

echo ""
echo "=== 优化建议 ==="
echo "1. 根据索引建议创建索引"
echo "2. 重写慢查询SQL"
echo "3. 再次执行性能快照对比"
```

### 场景4: 安全加固

```bash
#!/bin/bash
# security_hardening.sh

echo "=== 数据库安全加固 ==="

# 1. 全面安全审计
echo "[1/6] 全面安全审计..."
dbskiter --database=jump security audit

# 2. 扫描敏感数据
echo "[2/6] 扫描敏感数据..."
dbskiter --database=jump security sensitive-data

# 3. 检查弱密码
echo "[3/6] 检查弱密码..."
dbskiter --database=jump security weak-passwords

# 4. 审计权限
echo "[4/6] 审计权限..."
dbskiter --database=jump security permissions

# 5. 检查配置安全
echo "[5/6] 检查配置安全..."
dbskiter --database=jump security config

# 6. 登录安全监控
echo "[6/6] 登录安全监控..."
dbskiter --database=jump security login-security --hours=24

echo ""
echo "=== 安全加固完成 ==="
echo "请根据报告修复发现的问题"
```

### 场景5: 故障排查

```bash
#!/bin/bash
# troubleshooting.sh

echo "=== 数据库故障排查 ==="

# 1. 健康检查
echo "[1/6] 健康检查..."
dbskiter --database=jump monitor health

# 2. 异常检测
echo "[2/6] 异常检测..."
dbskiter --database=jump monitor anomalies

# 3. 性能快照
echo "[3/6] 性能快照..."
dbskiter --database=jump diagnose performance-snapshot

# 4. 锁分析
echo "[4/6] 锁分析..."
dbskiter --database=jump lock analyze

# 5. 死锁检测
echo "[5/6] 死锁检测..."
dbskiter --database=jump lock deadlocks

# 6. 慢查询
echo "[6/6] 慢查询..."
dbskiter --database=jump diagnose slow-queries --limit=5

echo ""
echo "=== 排查完成 ==="
echo "根据以上结果定位问题原因"
```

---

## 测试脚本

### 完整测试脚本

```bash
#!/bin/bash
# test_all_skills.sh

echo "======================================"
echo "    数据库Skill完整测试脚本"
echo "======================================"
echo ""

DATABASE="jump"
FAILED=0
PASSED=0

# 测试函数
run_test() {
    local name="$1"
    local cmd="$2"
    
    echo "测试: $name"
    echo "命令: $cmd"
    
    if eval "$cmd" > /dev/null 2>&1; then
        echo "通过"
        ((PASSED++))
    else
        echo "失败"
        ((FAILED++))
    fi
    echo ""
}

# ========== sql-master 测试 ==========
echo "【sql-master Skill 测试】"
run_test "基础查询" "dbskiter --database=$DATABASE sql 'SELECT 1'"
run_test "查看表结构" "dbskiter --database=$DATABASE sql schema"
run_test "SQL重写" "dbskiter --database=$DATABASE sql rewrite 'SELECT * FROM users'"
run_test "SQL分析" "dbskiter --database=$DATABASE sql analyze 'SELECT * FROM users'"

# ========== db-diagnose 测试 ==========
echo "【db-diagnose Skill 测试】"
run_test "性能快照" "dbskiter --database=$DATABASE diagnose performance-snapshot"
run_test "瓶颈分析" "dbskiter --database=$DATABASE diagnose bottleneck"
run_test "慢查询" "dbskiter --database=$DATABASE diagnose slow-queries --limit=3"
run_test "索引推荐" "dbskiter --database=$DATABASE diagnose recommend-indexes"

# ========== db-monitor 测试 ==========
echo "【db-monitor Skill 测试】"
run_test "健康检查" "dbskiter --database=$DATABASE monitor health"
run_test "异常检测" "dbskiter --database=$DATABASE monitor anomalies"
run_test "容量预测" "dbskiter --database=$DATABASE monitor capacity --resource=disk"

# ========== db-security 测试 ==========
echo "【db-security Skill 测试】"
run_test "安全审计" "dbskiter --database=$DATABASE security audit"
run_test "敏感数据扫描" "dbskiter --database=$DATABASE security sensitive-data"
run_test "权限审计" "dbskiter --database=$DATABASE security permissions"

# ========== db-inspector 测试 ==========
echo "【db-inspector Skill 测试】"
run_test "巡检" "dbskiter --database=$DATABASE inspector run"
run_test "风险预测" "dbskiter --database=$DATABASE inspector risks --days=7"

# ========== db-lock-analyzer 测试 ==========
echo "【db-lock-analyzer Skill 测试】"
run_test "锁分析" "dbskiter --database=$DATABASE lock analyze"
run_test "死锁检测" "dbskiter --database=$DATABASE lock deadlocks"

# ========== db-sql-auditor 测试 ==========
echo "【db-sql-auditor Skill 测试】"
run_test "SQL审核" "dbskiter --database=$DATABASE audit sql 'SELECT * FROM users'"
run_test "查看规则" "dbskiter audit rules"

echo "======================================"
echo "测试完成"
echo "通过: $PASSED"
echo "失败: $FAILED"
echo "======================================"
```

---

## 故障排查

### 常见问题

#### 1. 数据库连接失败

**现象**:
```
Error: 无法连接到数据库
```

**排查步骤**:
1. 检查 `.env` 文件配置是否正确
2. 测试网络连通性: `ping <DB_HOST>`
3. 测试端口连通性: `telnet <DB_HOST> <DB_PORT>`
4. 检查数据库用户权限

**解决**:
```bash
# 测试连接
dbskiter --database=jump sql "SELECT 1"

# 如果失败，检查配置
cat .env | grep DB_
```

#### 2. 权限不足

**现象**:
```
Error: Access denied for user
```

**解决**:
```bash
# 检查当前用户权限
dbskiter --database=jump security permissions

# 联系DBA授予必要权限
```

#### 3. 慢查询无结果

**现象**:
```
slow-queries 返回空
```

**原因**:
- 数据库未开启慢查询日志
- 查询时间阈值设置过高

**解决**:
```bash
# 检查是否开启慢查询日志
dbskiter --database=jump diagnose performance-snapshot

# 降低阈值再试
dbskiter --database=jump diagnose slow-queries --min-duration=0.1
```

#### 4. 导出大表内存溢出

**现象**:
```
Error: Memory limit exceeded
```

**解决**:
```bash
# 使用流式导出
dbskiter sql export-stream --table=large_table --output=output.csv --batch-size=10000
```

### 性能优化建议

1. **定期执行**: 每天执行 `monitor health` 和 `diagnose slow-queries`
2. **索引优化**: 每周执行 `diagnose recommend-indexes`
3. **安全审计**: 每月执行 `security audit`
4. **容量规划**: 每周执行 `monitor capacity --resource=disk`

### 最佳实践

1. **先诊断，再优化**: 先用 `performance-snapshot` 找到瓶颈，再用 `recommend-indexes` 优化
2. **小步快跑**: 一次只优化1-2个索引，观察效果
3. **定期巡检**: 每周执行一次 `inspector report`，预防问题
4. **记录变更**: 创建索引后，记录到变更日志
5. **基线对比**: 重大变更前采集 `performance-snapshot` 作为基线

---

## 附录

### A. 命令速查表

| 场景 | 命令 |
|------|------|
| 快速健康检查 | `dbskiter --database=jump monitor health` |
| 查看慢查询 | `dbskiter --database=jump diagnose slow-queries --limit=5` |
| 安全审计 | `dbskiter --database=jump security audit` |
| SQL优化 | `dbskiter --database=jump sql rewrite "<SQL>"` |
| 索引推荐 | `dbskiter --database=jump diagnose recommend-indexes` |
| 生成报告 | `dbskiter --database=jump inspector report --output report.html` |
| 容量预测 | `dbskiter --database=jump monitor capacity --resource=disk` |
| 锁分析 | `dbskiter --database=jump lock analyze` |

### B. 数据库支持矩阵

| 数据库 | 性能快照 | 瓶颈分析 | 慢查询 | 状态 |
|--------|----------|----------|--------|------|
| MySQL | 支持 | 支持 | 支持 | 生产就绪 |
| Oracle | 支持 | 支持 | 支持 | 生产就绪 |
| PostgreSQL | 支持 | 支持 | 支持 | 生产就绪 |

### C. 相关资源

- 项目根目录: `e:\Chenzc-AIDev\数据库skill`
- 配置文件: `.env`
- Skill目录: `.trae\skills\`

---

**文档结束**

如有问题，请参考各Skill的详细说明或联系开发团队。
