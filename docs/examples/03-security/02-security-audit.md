# Tutorial: Security Audit

## Scenario

Run compliance security audit.

---

## Step 1: Full Security Audit

```bash
dbskiter --database=jump security audit
```

## Step 2: Check Specific Risks

```bash
# SQL injection scan
dbskiter --database=jump security sql-injection "SELECT * FROM users WHERE id = 1"

# Sensitive data scan
dbskiter --database=jump security sensitive-data

# Password policy check
dbskiter --database=jump security password-policy

# Permission audit
dbskiter --database=jump security permissions
```

## Step 3: Review Score

```bash
dbskiter --database=jump security score
```

## Fix Common Issues

- Enable `sql_mode=STRICT_ALL_TABLES` in MySQL
- Remove anonymous accounts
- Set strong password policies
- Grant minimum required permissions