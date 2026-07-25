# Tutorial: Disk Space Alert

## Scenario

Disk is 85% full. Predict when it will fill up.

---

## Step 1: Check Space

```bash
dbskiter --database=jump diagnose space --top=10
```

## Step 2: Predict Disk Full Date

```bash
dbskiter --database=jump monitor capacity --resource=disk
```

## Step 3: Find Large Tables

```bash
dbskiter --database=jump diagnose table orders
```

## Cleanup

```bash
# Archive old data
dbskiter --database=jump sql execute "DELETE FROM logs WHERE created_at < NOW() - INTERVAL 90 DAY"

# Optimize table
dbskiter --database=jump sql execute "OPTIMIZE TABLE orders"
```