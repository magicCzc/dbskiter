# Tutorial: Multi-Database Configuration

Configure multiple databases (production, staging, development) in one `.env`.

---

## Using Aliases

```bash
# .env
DB_JUMP_HOST=192.168.1.1
DB_JUMP_PORT=3306
DB_JUMP_USER=monitor
DB_JUMP_PASSWORD=xxx
DB_JUMP_NAME=production
DB_JUMP_DIALECT=mysql+pymysql

DB_STAGING_HOST=192.168.1.2
DB_STAGING_PORT=3306
DB_STAGING_USER=monitor
DB_STAGING_PASSWORD=xxx
DB_STAGING_NAME=staging
DB_STAGING_DIALECT=mysql+pymysql
```

```bash
dbskiter --database=jump   monitor health   # Production
dbskiter --database=staging monitor health   # Staging
```

## Using YAML Profile

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
dbskiter --profile=dev  diagnose slow-queries
```

## Using URL Connection String

```bash
dbskiter --url "mysql://root:pass@prod-host:3306/prod" monitor health
dbskiter --url "postgresql://user:pass@dev-host:5432/dev" monitor health
```