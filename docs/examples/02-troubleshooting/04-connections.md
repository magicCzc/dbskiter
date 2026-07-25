# Tutorial: Connection Limit

## Scenario

Application reports "Too many connections" error.

---

## Step 1: Check Connections

```bash
dbskiter --database=jump diagnose connections
```

## Step 2: Identify Idle Connections

```bash
dbskiter --database=jump diagnose connections --show-idle
```

## Step 3: Kill Idle Connections

```bash
dbskiter --database=jump lock kill <connection_id> --force
```

## Prevention

- Add connection pooling to your application
- Set up monitoring: `dbskiter monitor anomalies`
- Configure max_connections in MySQL