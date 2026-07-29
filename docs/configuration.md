# 配置指南

DBSKiter 支持多种配置方式，按优先级从高到低排列：

1. **连接字符串** — `--url` 参数
2. **命令行参数** — `--host`, `--user`, `--password` 等
3. **配置文件** — `~/.dbskiter/config.yaml`
4. **.env 文件** — 当前目录或项目根目录
5. **环境变量** — `DB_HOST`, `DB_USER` 等

---

## 1. 连接字符串（推荐）

最简洁的配置方式，一行搞定所有连接信息：

```bash
# 所有参数都在一个字符串中
dbskiter --url "mysql+pymysql://root:password@localhost:3306/test" monitor health

# 支持所有数据库类型
dbskiter --url "postgresql://user:pass@pg-host:5432/mydb" monitor health
dbskiter --url "oracle+oracledb://user:pass@oracle-host:1521/ORCL" diagnose slow-queries
dbskiter --url "mssql+pyodbc://sa:pass@sqlserver:1433/master" security audit
```

**格式说明**：
```
dialect+driver://user:password@host:port/database?参数
```

常见 dialect 缩写也支持：
```bash
dbskiter --url "mysql://root@localhost/test"  # 自动补全为 mysql+pymysql
dbskiter --url "postgres://user@host/db"       # 自动补全为 postgresql
dbskiter --url "pg://user@host/db"             # postgresql 的缩写
```

从标准输入读取密码（安全）：
```bash
echo "mypassword" | dbskiter --url "mysql://root@localhost/test" --password-stdin monitor health
```

---

## 2. 命令行参数

直接指定所有连接参数，无需任何配置文件：

```bash
dbskiter --host=192.168.1.1 --port=3306 --user=root --password=xxx --database=test monitor health
```

短参数形式：
```bash
dbskiter -h 192.168.1.1 -P 3306 -u root -p xxx -d test monitor health
```

---

## 3. 配置文件（适合多数据库管理）

创建 `~/.dbskiter/config.yaml`：

```yaml
profiles:
  local:
    dialect: mysql+pymysql
    host: localhost
    user: root
    password: ${DB_PASSWORD}
    database: test

  production:
    dialect: mysql+pymysql
    host: prod-db.internal
    user: deploy
    password: ${DB_PROD_PASSWORD}
    database: prod

  analytics:
    dialect: clickhouse
    host: clickhouse.internal
    port: 9000
    database: default

environments:
  development:
    databases: [local]
  production:
    default_database: production
    databases:
      - production
      - analytics
```

使用方式：

```bash
# 使用默认 profile
dbskiter monitor health

# 使用指定 profile
dbskiter --profile=production monitor health

# 使用环境
dbskiter --env=development monitor health
```

### 配置文件搜索路径

DBSKiter 按以下顺序搜索配置文件：
1. `--config` 参数指定的路径
2. `~/.dbskiter/config.yaml`
3. `~/.dbskiter/config.yml`
4. `~/.dbskiter/config.json`
5. `~/.dbskiter/config.toml`

---

## 4. .env 文件（传统方式）

适合单数据库快速配置：

```bash
# .env 文件
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=your_password
DB_NAME=test
DB_DIALECT=mysql+pymysql
```

多数据库使用别名：
```bash
# .env 文件
DB_JUMP_HOST=192.168.1.1
DB_JUMP_PORT=3306
DB_JUMP_USER=root
DB_JUMP_PASSWORD=xxx
DB_JUMP_NAME=prod
DB_JUMP_DIALECT=mysql+pymysql

DB_CHENCZ_HOST=192.168.1.2
DB_CHENCZ_PORT=3306
DB_CHENCZ_USER=root
DB_CHENCZ_PASSWORD=xxx
DB_CHENCZ_NAME=dev
DB_CHENCZ_DIALECT=mysql+pymysql
```

```bash
dbskiter --database=jump monitor health
dbskiter --database=chencz diagnose slow-queries
```

---

## 5. 环境变量

所有配置项都可以通过环境变量设置：

```bash
export DB_HOST=localhost
export DB_PORT=3306
export DB_USER=root
export DB_PASSWORD=xxx
export DB_NAME=test
export DB_DIALECT=mysql+pymysql

dbskiter monitor health
```

也可以使用自定义前缀：
```bash
export ORACLE_HOST=oracle-host
export ORACLE_PORT=1521
dbskiter --prefix=ORACLE monitor health
```

---

## 配置优先级

当多种配置方式同时存在时，优先级如下（从高到低）：

```
--url 连接字符串
  ↓
--password-stdin / --password-file
  ↓
--host, --user, --password, --port, --dialect 等 CLI 参数
  ↓
--profile 指定的配置文件 profile
  ↓
--database 匹配的 .env 别名
  ↓
.env 文件中的默认配置
  ↓
环境变量 DB_HOST, DB_USER 等
  ↓
内置默认值（localhost:3306/root/test）
```

例如，`--host` 会覆盖 `.env` 中的 `DB_HOST`，`--password-file` 会覆盖 `--password`。

---

## 三种配置方式对比

| 方式 | 适用场景 | 优点 | 缺点 |
|------|---------|------|------|
| `--url` | 临时连接、脚本 | 一行搞定 | 密码可能暴露在 shell 历史 |
| `--profile` | 多数据库管理 | 结构化、可复用 | 需要创建配置文件 |
| `.env` 文件 | 单数据库、快速开始 | 简单直观 | 多数据库时繁琐 |