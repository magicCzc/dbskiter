# Tutorial: Monthly Inspection

## Scenario

Automate monthly database health inspections.

---

## Step 1: Run Inspection

```bash
dbskiter --database=jump inspector run --type full
```

## Step 2: Generate Report

```bash
dbskiter --database=jump inspector report --output monthly_report.html
```

## Step 3: Create Baseline

```bash
dbskiter --database=jump inspector baseline --create
```

## Step 4: Compare with Previous

```bash
dkskiter --database=jump inspector baseline --compare
```

## Automation

```bash
# Add to crontab (runs 1st of every month at 8 AM)
0 8 1 * * dbskiter --database=jump inspector report --output /reports/monthly_$(date +%Y%m).html
```