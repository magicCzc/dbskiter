# Tutorial: CPU Spike Root Cause Analysis

## Scenario

Database CPU suddenly spikes to 95%. Find the root cause.

---

## Step 1: Check Real-Time Diagnosis

```bash
dbskiter --database=jump diagnose realtime
```

## Step 2: Find Top SQL

```bash
dbskiter --database=jump diagnose top --limit=10
```

## Step 3: Check Connections

```bash
dbskiter --database=jump diagnose connections
```

## Step 4: Kill Problematic Query (if needed)

```bash
dbskiter --database=jump lock kill <thread_id> --force
```

## Prevention

- Set up monitoring alerts: `dbskiter monitor anomalies`
- Configure capacity prediction: `dbskiter monitor capacity --resource=cpu`