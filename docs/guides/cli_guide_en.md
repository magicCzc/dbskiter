# DBSKiter CLI Guide (English)

DBSKiter is a database AIOps CLI tool supporting 7 databases (MySQL, Oracle, PostgreSQL, SQL Server, ClickHouse, SQLite + Generic JDBC).

---

## Installation

```bash
pip install dbskiter

# Verify
dbskiter --version
```

## Quick Start

### Configure Database

```bash
# Interactive setup (recommended)
dbskiter init

# Or create .env file
cp .env.example .env
# Edit .env with your database connection info
```

### Basic Commands

```bash
# Health check
dbskiter --database=jump monitor health

# Slow query analysis
dbskiter --database=jump diagnose slow-queries

# Security audit
dbskiter --database=jump security audit
```

## Connection Methods

### 1. URL Connection String (Recommended)

```bash
dbskiter --url "mysql://root:pass@localhost:3306/test" monitor health
dbskiter --url "postgresql://user:pass@pg-host:5432/mydb" diagnose slow-queries
dbskiter --url "oracle+oracledb://user:pass@oracle-host:1521/ORCL" security audit
```

### 2. CLI Parameters

```bash
dbskiter --host=192.168.1.1 --port=3306 --user=root --password=xxx --database=test monitor health
```

### 3. YAML Profile (Multi-DB)

```yaml
# ~/.dbskiter/config.yaml
profiles:
  prod:
    dialect: mysql+pymysql
    host: prod-db.internal
    user: deploy
    password: ${DB_PROD_PASSWORD}
    database: prod
  dev:
    dialect: postgresql
    host: dev-db.internal
    database: dev
```

```bash
dbskiter --profile=prod monitor health
dbskiter --profile=dev diagnose slow-queries
```

### 4. .env Aliases

```bash
# .env
DB_JUMP_HOST=192.168.1.1
DB_JUMP_NAME=production
DB_CHENCZ_HOST=192.168.1.2
DB_CHENCZ_NAME=development
```

```bash
dbskiter --database=jump monitor
dbskiter --database=chencz monitor
```

## Output Modes

```bash
# Rule mode (default) - human-readable formatted output
dbskiter monitor health

# Raw mode - raw data for scripts
dbskiter --output-mode=raw monitor health

# AI mode - structured JSON for AI analysis
dbskiter --output-mode=ai monitor health
```

## Command Reference

### 1. Monitor

```bash
# Health check
dbskiter --database=jump monitor health

# Anomaly detection
dbskiter --database=jump monitor anomalies

# Capacity prediction
dbskiter --database=jump monitor capacity --resource=disk

# Collect metrics
dbskiter --database=jump monitor collect

# View history
dbskiter --database=jump monitor history cpu_usage
```

### 2. Diagnose

```bash
# Real-time diagnosis ("database is slow")
dbskiter --database=jump diagnose realtime

# Slow query analysis
dbskiter --database=jump diagnose slow-queries --top=10

# Index recommendation
dbskiter --database=jump diagnose recommend-indexes

# Lock analysis
dbskiter --database=jump diagnose locks

# Space analysis
dbskiter --database=jump diagnose space

# Replication health
dbskiter --database=jump diagnose replication

# Connection analysis
dbskiter --database=jump diagnose connections

# Table diagnosis
dbskiter --database=jump diagnose table users

# Performance snapshot
dbskiter --database=jump diagnose performance-snapshot

# Bottleneck analysis
dbskiter --database=jump diagnose bottleneck
```

### 3. Security

```bash
# Full security audit
dbskiter --database=jump security audit

# SQL injection detection
dbskiter --database=jump security sql-injection "SELECT * FROM users WHERE id = %s"

# Sensitive data scan
dbskiter --database=jump security sensitive-data

# Password policy check
dbskiter --database=jump security password-policy

# Permission audit
dbskiter --database=jump security permissions

# Login security monitoring
dbskiter --database=jump security login-security --hours=48
```

### 4. SQL Execution

```bash
# Execute SQL
dbskiter --database=jump sql execute "SELECT * FROM users LIMIT 10"

# SQL rewrite optimization
dbskiter --database=jump sql rewrite "SELECT * FROM users WHERE id = 1"

# SQL quality analysis
dbskiter --database=jump sql analyze "SELECT * FROM users WHERE id = 1"

# View schema
dbskiter --database=jump sql schema --table=users

# Export data
dbskiter --database=jump sql export --table=users --output=users.csv
```

### 5. Inspector

```bash
# Run inspection
dbskiter --database=jump inspector run

# Generate report
dbskiter --database=jump inspector report --output report.html

# Intelligent inspection
dbskiter --database=jump inspector intelligent

# Risk prediction
dbskiter --database=jump inspector risks --days=7
```

### 6. Lock Analysis

```bash
# Analyze current locks
dbskiter --database=jump lock analyze

# Detect deadlocks
dbskiter --database=jump lock deadlocks

# Lock wait chains
dbskiter --database=jump lock chains

# Generate lock report
dbskiter --database=jump lock report
```

### 7. Scheduler

```bash
# Backup database
dbskiter --database=jump scheduler backup --type=full

# Verify backup
dbskiter --database=jump scheduler backup-verify <backup_file>

# Restore database
dbskiter --database=jump scheduler backup-restore <backup_file>

# List scheduled tasks
dbskiter --database=jump scheduler task list

# Add cron task
dbskiter --database=jump scheduler task add daily_backup "0 2 * * *"

# Start scheduler daemon
dbskiter --database=jump scheduler daemon start
```

### 8. SQL Audit

```bash
# Audit SQL
dbskiter --database=jump audit sql "SELECT * FROM users"

# DDL impact analysis
dbskiter --database=jump audit ddl "ALTER TABLE users ADD COLUMN age INT"

# Index recommendation
dbskiter --database=jump audit recommend-indexes "SELECT * FROM orders WHERE user_id = 1"
```

## Shortcut Aliases

```bash
dbskiter health              → monitor health
dbskiter top                 → diagnose top
dbskiter slow                → diagnose slow-queries
dbskiter locks               → lock analyze
dbskiter audit               → security audit
dbskiter report              → inspector report
dbskiter welcome             → new user guide (no DB needed)
```

## Tab Completion

```bash
# One-line enable
dbskiter shell-setup --auto
```

## Global Parameters

| Parameter | Description | Example |
|-----------|-------------|---------|
| `--database` | Database alias | `--database=jump` |
| `--output-mode` | Output mode | `--output-mode=ai` |
| `--json` | JSON output (legacy) | `--json` |
| `--debug` | Debug mode | `--debug` |
| `--demo` | Demo mode (mock data) | `--demo` |

## Security Notes

1. **Never use `--password` in production** (leaks to shell history and `ps`)
2. Use `--password-stdin` or `--password-file` instead
3. Enable read-only mode: `export DBSKITER_READ_ONLY=true`
4. Use dedicated monitoring accounts (not root)

## Supported Databases

| Level | Databases |
|-------|-----------|
| 🟢 Deep | MySQL / MariaDB / Oracle / PostgreSQL / SQL Server / ClickHouse / SQLite |
| 🟡 Generic | Trino / Presto / DuckDB / Derby / H2 |

## Troubleshooting

### Connection Failed

```bash
# Enable debug mode for details
dbskiter --debug --database=jump monitor health

# Test connection directly
mysql -h 192.168.1.1 -u root -p
```

### Command Not Found

```bash
# Check installation
pip show dbskiter
which dbskiter
```

---

## License

MIT