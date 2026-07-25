# Tutorial: Disk Capacity Prediction

## Scenario

Predict when disk will be full.

---

## Step 1: Check Current Space

```bash
dbskiter --database=jump diagnose space
```

## Step 2: Predict Capacity

```bash
dbskiter --database=jump monitor capacity --resource=disk
```

## Step 3: Advanced Prediction

```bash
dbskiter --database=jump monitor capacity-advanced --resource=disk
```

## Step 4: Trend Analysis

```bash
dbskiter --database=jump monitor trend --metric=disk_usage
```