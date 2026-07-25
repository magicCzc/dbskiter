# Tutorial: Table Bloat Analysis

## Scenario

Tables are growing fast. Analyze bloat and fragmentation.

---

## Step 1: Check Bloat

```bash
dbskiter --database=jump diagnose bloat --threshold=30
```

## Step 2: Analyze Table

```bash
dbskiter --database=jump diagnose table orders
```

## Step 3: Check Index Usage

```bash
dbskiter --database=jump diagnose index-usage
```

## Cleanup

```bash
# PostgreSQL: vacuum
dbskiter --database=jump diagnose vacuum

# MySQL: optimize table
dbskiter --database=jump sql execute "OPTIMIZE TABLE orders"
```