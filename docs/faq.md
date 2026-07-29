<!--
文件功能：DBSKiter 常见问题
作者：MagiCzc
创建时间：2026-07-24
最后修改：2026-07-24
-->

# 常见问题（FAQ）

本文档汇总 DBSKiter 使用过程中的高频问题。

---

## 安装与配置

### Q1: `pip install dbskiter` 失败怎么办？

**A**: 检查 Python 版本是否 ≥ 3.8。

```bash
python --version  # 必须 3.8+
```

如果版本过低或编译报错，尝试：

```bash
pip install --upgrade pip
pip install dbskiter --no-cache-dir
```

Windows 上 psycopg2 编译失败时，建议先安装预编译版本：

```bash
pip install psycopg2-binary
pip install dbskiter
```

### Q2: `dbskiter --demo` 模式是什么？

**A**: Demo 模式使用内置 Mock 数据，无需真实数据库即可体验所有命令。

```bash
dbskiter --demo monitor health      # 健康检查（模拟数据）
dbskiter --demo diagnose realtime   # 实时诊断
dbskiter --demo sql execute "SELECT 1"
```

适合：演示、新手试用、CI 测试。

### Q3: 如何配置多数据库？

**A**: 三种方式：

#### 方式 1：`.env` 别名

```bash
DB_JUMP_HOST=192.168.1.1
DB_JUMP_NAME=production
DB_CHENCZ_HOST=192.168.1.2
DB_CHENCZ_NAME=development
```

使用：

```bash
dbskiter --database=jump monitor
dbskiter --database=chencz monitor
```

#### 方式 2：URL 连接串

```bash
dbskiter --url "mysql://root@192.168.1.1/prod" monitor
dbskiter --url "postgresql://user@192.168.1.2/dev" monitor
```

#### 方式 3：YAML profile

```yaml
# ~/.dbskiter/config.yaml
profiles:
  prod:
    dialect: mysql+pymysql
    host: 192.168.1.1
    user: root
    password: ${DB_PROD_PASSWORD}
    database: production
  dev:
    dialect: postgresql
    host: 192.168.1.2
    database: development
```

```bash
dbskiter --profile=prod monitor
```

详见 [配置文档](configuration.md)。

### Q4: 密码怎么传才安全？

**A**: 推荐三种方式（按安全度从高到低）：

| 方式 | 命令 | 安全度 |
|------|------|--------|
| `--password-stdin` | `echo "xxx" \| dbskiter ...` | ⭐⭐⭐⭐⭐ |
| `--password-file` | `dbskiter --password-file ~/.pwd ...` | ⭐⭐⭐⭐ |
| 环境变量 | `export DB_PASSWORD=xxx` | ⭐⭐⭐ |
| `.env` 文件 | 写在 `.env` 中 | ⭐⭐⭐ |
| `--password` 参数 | `dbskiter -p xxx` | ⭐（会进 shell 历史） |

**禁止**生产环境用 `--password` 直接传，会进 `history` 和 `ps` 进程列表。

---

## 故障诊断

### Q5: 数据库连接失败怎么办？

**A**: 分三步排查：

#### 1. 验证配置

```bash
dbskiter --debug --database=jump monitor health
```

`--debug` 会显示详细错误信息。

#### 2. 测试连通性

```bash
# MySQL
mysql -h 192.168.1.1 -u root -p -e "SELECT 1"

# PostgreSQL
psql -h 192.168.1.1 -U user -d test -c "SELECT 1"
```

#### 3. 常见错误

| 错误 | 原因 | 解决 |
|------|------|------|
| `Can't connect to MySQL server` | 端口/防火墙 | 检查 `DB_PORT`、防火墙 |
| `Access denied for user` | 账号/密码错 | 重置 `.env` |
| `Unknown database` | 库名错 | 确认 `DB_NAME` |
| `SSL connection error` | SSL 配置 | 加 `?ssl_mode=DISABLED` |

### Q6: 慢查询分析如何定位到具体 SQL？

**A**: 

```bash
# 1. 抓取 top 10 慢查询
dbskiter --database=jump diagnose slow-queries --top=10

# 2. 深入分析某条 SQL
dbskiter --database=jump diagnose sql "SELECT * FROM orders WHERE user_id = 123"

# 3. 索引推荐
dbskiter --database=jump audit recommend-indexes "SELECT * FROM orders WHERE user_id = 123"
```

详见 [业务卡顿查慢查询案例](examples/02-故障诊断/01-业务卡顿查慢查询.md)。

### Q7: 如何检测死锁？

**A**:

```bash
# 当前死锁
dbskiter --database=jump diagnose locks

# 历史死锁（MySQL）
dbskiter --database=jump lock deadlocks

# 锁等待链
dbskiter --database=jump lock chains
```

详见 [接口超时查锁等待案例](examples/04-锁与死锁/01-接口超时查锁等待.md)。

### Q8: 健康评分低怎么办？

**A**: 健康评分由多个维度组成（CPU、内存、连接、慢查询、锁等待、复制延迟等）：

```bash
dbskiter --database=jump monitor health
# 健康评分: 66.4/100
# 严重问题: 1
# 高风险问题: 3
# 警告: 5
```

**重点关注** `严重问题` 和 `高风险问题`，按以下顺序处理：

1. **连接数打满**：`monitor connections`
2. **慢查询堆积**：`diagnose slow-queries`
3. **锁等待严重**：`diagnose locks`
4. **磁盘空间不足**：`diagnose space`
5. **复制延迟**：`diagnose replication`

---

## AI 集成

### Q9: Claude Desktop 怎么集成？

**A**: 

```json
// ~/.config/claude/claude_desktop_config.json (macOS/Linux)
// %APPDATA%\Claude\claude_desktop_config.json (Windows)
{
  "mcpServers": {
    "dbskiter": {
      "command": "dbskiter-mcp",
      "env": {
        "DB_HOST": "localhost",
        "DB_USER": "root",
        "DB_PASSWORD": "your_password",
        "DB_NAME": "mydb"
      }
    }
  }
}
```

重启 Claude Desktop 后可直接对话：

- "检查我的数据库健康"
- "分析这条 SQL：SELECT * FROM users WHERE created_at > '2026-01-01'"
- "给我列出今天最慢的 5 个查询"

详见 [AI 集成指南](guides/AI集成指南.md)。

### Q10: `--output-mode=ai` 的输出 AI 怎么解析？

**A**: 输出格式见 [AI 集成指南](guides/AI集成指南.md)，结构示例：

```json
{
  "schema_version": "1.0",
  "collected_at": "2026-07-24T10:30:00+08:00",
  "instance_id": "mysql-prod-01",
  "data": {
    "raw_metrics": {"cpu_usage": 85.2},
    "rule_flags": {"cpu_high": {"flagged": true}},
    "context": {"database_type": "mysql"},
    "ai_hints": {"focus_areas": ["CPU 使用率偏高"]}
  }
}
```

AI 应重点读 `ai_hints.focus_areas`，给出针对性建议。

---

## 性能与优化

### Q11: CLI 启动慢怎么办？

**A**: CLI 启动目标 < 200ms。如果慢：

1. **检查 Python 环境**：避免使用系统 Python，建议虚拟环境
2. **禁用不必要的插件**：使用 `--no-color` 等
3. **检查 import 路径**：自定义 Skill 过多可能拖慢

### Q12: 慢查询分析时数据库压力大怎么办？

**A**:

```bash
# 1. 限制扫描范围
dbskiter diagnose slow-queries --top=5 --hours=1

# 2. 使用采样（仅 MySQL）
dbskiter diagnose slow-queries --sample-rate=10

# 3. 在低峰期执行
# 4. 走只读副本（如果有）
dbskiter --database=jump_ro diagnose slow-queries
```

### Q13: 大表备份慢怎么办？

**A**:

```bash
# 1. 物理备份（仅 MySQL）—— 最快
dbskiter scheduler backup --type=physical

# 2. 表级备份
dbskiter scheduler backup --type=table --tables users,orders

# 3. 压缩备份
dbskiter scheduler backup --type=full --compress=gzip

# 4. 并行备份
dbskiter scheduler backup --type=full --parallel=4
```

---

## 升级与兼容

### Q14: V2 模块会移除吗？

**A**: 是的。v4.0（2026-12-31）会移除所有 V2 模块：

- `dbskiter.db_security.sensitive_data_scanner_v2`
- `dbskiter.db_security.sql_injection_detector_v2`
- `dbskiter.shared.mysql_aas_calculator_v2`
- `dbskiter.sql_master.security_executor_v2`

迁移指南：[v3 → v4 迁移](guides/migration-v3-to-v4.md)

### Q15: 升级 dbskiter 后命令变了怎么办？

**A**: 升级前先看 [CHANGELOG](https://github.com/magicCzc/dbskiter/blob/main/CHANGELOG.md) 了解 breaking changes。

升级命令：

```bash
pip install --upgrade dbskiter
dbskiter --version  # 确认版本
```

如有兼容问题，参考具体版本的 migration guide。

---

## 错误码

### Q16: 错误码 `CONNECTION_ERROR` 是什么意思？

**A**: 数据库连接失败。检查：

1. 数据库服务是否启动
2. 防火墙/端口是否开放
3. 用户名/密码是否正确
4. 数据库名是否存在

详见 [错误处理](#q5)。

### Q17: 错误码 `CONFIG_ERROR` 是什么意思？

**A**: 配置错误。检查：

1. `.env` 文件是否存在
2. 环境变量是否设置
3. `--url` 是否合法
4. `--profile` 是否存在

使用 `dbskiter --debug` 看详细错误。

---

## 性能与稳定性

### Q18: 在生产环境用安全吗？

**A**: DBSKiter 设计上考虑了三层安全防护：

1. **AI 层**：AI 只能调只读命令
2. **CLI 层**：`DBSKITER_READ_ONLY=true` 强制只读
3. **数据库层**：物理账号只读

但请确保：

- ✅ 使用专用监控账号（不要用 root）
- ✅ 启用只读模式
- ✅ 走 HTTPS 通道
- ✅ 定期审计操作日志

### Q19: 能在 K8s 中运行吗？

**A**: 可以。推荐方式：

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: dbskiter
spec:
  replicas: 1
  template:
    spec:
      containers:
      - name: dbskiter
        image: dbskiter:latest
        env:
        - name: DB_HOST
          valueFrom:
            secretKeyRef:
              name: db-credentials
              key: host
        # ...
```

详见 [Dockerfile](https://github.com/magicCzc/dbskiter/blob/main/Dockerfile) 和 [docker-compose.yml](https://github.com/magicCzc/dbskiter/blob/main/docker-compose.yml)。

### Q20: 性能基准怎么样？

**A**:

| 指标 | 数值 |
|------|------|
| CLI 启动时间 | < 200ms |
| 慢查询解析 | 10K QPS |
| 健康检查（MySQL） | 200ms |
| 健康检查（Generic） | 500ms |
| 备份（10GB MySQL） | ~5min |
| 备份（10GB PostgreSQL） | ~8min |

详见 [性能基准测试](https://github.com/magicCzc/dbskiter/blob/main/tests/test_benchmarks.py)。

---

## 社区与支持

### Q21: 如何报告 Bug？

**A**: 提交 [GitHub Issue](https://github.com/magicCzc/dbskiter/issues/new)，包含：

- `dbskiter --version` 输出
- 操作系统和 Python 版本
- 复现步骤
- 预期行为 vs 实际行为
- 错误日志（`--debug` 模式）

### Q22: 如何贡献代码？

**A**: 参考 [贡献指南](https://github.com/magicCzc/dbskiter/blob/main/CONTRIBUTING.md)：

1. Fork 仓库
2. 创建特性分支：`git checkout -b feature/my-feature`
3. 提交代码：遵循 black + flake8
4. 添加测试
5. 提交 PR

### Q23: 有商业支持吗？

**A**: 目前是社区项目，邮件 magiczc@139.com 联系。

---

## 路线图

### Q24: Web UI 什么时候出？

**A**: 2026 Q3 末发布 MVP（FastAPI + Vue 3）。包含：

- 健康仪表盘
- 慢查询分析
- 安全审计
- 备份管理
- 任务调度

详见 [架构文档](architecture.md)。

### Q25: 未来会增加哪些数据库？

**A**: 候选：

- ✅ OceanBase（深度优化中）
- ✅ TiDB（计划 2027 Q1）
- 🔄 MongoDB（评估中）
- 🔄 Elasticsearch（评估中）

欢迎在 Issue 中投票你最想要的数据库。

---

**最后更新**：2026-07-24  
**问题反馈**：[GitHub Issues](https://github.com/magicCzc/dbskiter/issues)
