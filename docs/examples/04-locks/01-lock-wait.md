# Tutorial: Lock Wait Analysis

## Scenario

API timeout, find lock waits and deadlocks.

---

## Step 1: Check Current Locks

```bash
dbskiter --database=jump lock analyze
```

## Step 2: Find Lock Wait Chains

```bash
dbskiter --database=jump lock chains
```

## Step 3: Check Deadlocks

```bash
dbskiter --database=jump lock deadlocks
```

## Step 4: Kill Blocking Transaction

```bash
dbskiter --database=jump lock kill <transaction_id> --force
```

## Prevention

- Keep transactions short
- Always access tables in the same order
- Use proper indexes to reduce lock contention