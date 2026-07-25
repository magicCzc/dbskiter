# Tutorial: Slow Query Diagnosis

## Scenario

- **Time**: 2026-06-10, Tuesday 14:30
- **Symptom**: Customer service reports system slowness, order page loads > 8 seconds
- **Database**: MySQL 8.0.32, business database `jump`
- **Team**: No dedicated DBA, backend engineer handles database

---

## Step 1: Health Check (30 sec)

```bash
dbskiter --database=jump monitor health
```

**Key output**:

```
Health Score: 66.4/100 (Needs attention)
Critical: 1
High Risk: 3
```

**Focus areas**:
- Temp table disk usage: **61.96%** (Warning)
- Row lock waits: **147** (Warning)
- Merge sort passes: **5753** (Warning)

> Interpretation: These three indicators together suggest complex queries spilling to disk and lock contention.

## Step 2: Find Slow Queries (1 min)

```bash
dbskiter --database=jump diagnose slow-queries --top=10
```

**Output**:

```
Top 10 Slow Queries:
1. SELECT * FROM orders WHERE status = 'PENDING' ORDER BY created_at DESC
   Total: 12.5s  |  Avg: 2.5s  |  Rows: 500,000
```

## Step 3: Analyze Slow SQL (1 min)

```bash
dbskiter --database=jump diagnose sql "SELECT * FROM orders WHERE status = 'PENDING'"
```

## Step 4: Get Index Recommendation (1 min)

```bash
dbskiter --database=jump audit recommend-indexes "SELECT * FROM orders WHERE status = 'PENDING'"
```

## Step 5: Fix (1 min)

Add the recommended index:

```sql
CREATE INDEX idx_orders_status_created ON orders(status, created_at DESC);
```

---

**Key takeaway**: Full process takes < 5 minutes. No DBA needed.