# Tutorial: First Command

## Scenario

You've installed DBSKiter. Now run your first database health check.

---

## Run Health Check

```bash
dbskiter --database=jump monitor health
```

### Expected Output

```
Health Score: 85.2/100
Status: HEALTHY
Issues: 0
```

### Understanding the Score

| Score | Meaning |
|-------|---------|
| 80-100 | 🟢 Healthy |
| 60-80  | 🟡 Warning - needs attention |
| < 60   | 🔴 Critical - needs immediate action |

## Try Demo Mode (No DB Required)

```bash
dbskiter --demo monitor health
dbskiter --demo diagnose realtime
dbskiter --demo sql execute "SELECT 1"
```

## Other Quick Commands

```bash
# Check database version
dbskiter --database=jump sql execute "SELECT VERSION()"

# List tables
dbskiter --database=jump sql schema

# Slow query analysis
dbskiter --database=jump diagnose slow-queries --top=5
```