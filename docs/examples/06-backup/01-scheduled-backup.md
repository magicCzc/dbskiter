# Tutorial: Scheduled Backup & Restore

## Scenario

Configure automated daily backups.

---

## Step 1: Create Backup

```bash
# Full backup
dbskiter --database=jump scheduler backup --type=full

# Table backup
dbskiter --database=jump scheduler backup --type=table --tables=users,orders
```

## Step 2: Verify Backup

```bash
dbskiter --database=jump scheduler backup-verify /path/to/backup.sql
```

## Step 3: Schedule Daily Backup

```bash
# Add cron task (runs at 2 AM daily)
dbskiter --database=jump scheduler task add daily_backup "0 2 * * *" --params '{"type": "full"}'
```

## Step 4: View Tasks

```bash
dbskiter --database=jump scheduler task list
```

## Step 5: Restore (if needed)

```bash
dbskiter --database=jump scheduler backup-restore /path/to/backup.sql --confirm
```

## Automation with Workflow

```bash
# Create backup workflow
dbskiter --database=jump scheduler workflow create weekly_backup

# Add tasks
dbskiter --database=jump scheduler workflow add-task weekly_backup daily_backup

# Submit
dbskiter --database=jump scheduler workflow submit weekly_backup
```