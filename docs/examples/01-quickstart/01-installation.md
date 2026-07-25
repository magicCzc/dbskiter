# Tutorial: Installation & Setup

## Scenario

- **Role**: Backend developer, first time using DBSKiter
- **Goal**: Complete install, configure, and run first command in 15 minutes
- **Environment**: Windows 10/11 or Linux, Python 3.10+
- **Database**: Local MySQL 8.0, test database `jump`

---

## Step 1: Install (2 min)

### Check Python

```bash
python --version
# Expected: Python 3.10.x or higher
```

### Install DBSKiter

```bash
pip install dbskiter
```

### Verify

```bash
dbskiter --version
# Expected: dbskiter 3.0.x
```

## Step 2: Configure (3 min)

### Interactive Setup (Recommended)

```bash
dbskiter init
```

Follow the wizard to enter your database connection info.

### Manual Setup

```bash
cp .env.example .env
# Edit .env with your database connection
```

## Step 3: Run First Command (1 min)

```bash
dbskiter --demo monitor health
```

This uses demo mode (built-in mock data, no real database needed).

## Step 4: Connect to Real Database

```bash
dbskiter --database=jump monitor health
```

### Expected Output

```
Health Score: 85.2/100
Status: HEALTHY
Issues: 0
```

## Troubleshooting

### Connection Failed

```bash
# Enable debug mode
dbskiter --debug --database=jump monitor health

# Test connection directly
mysql -h localhost -u root -p -e "SELECT 1"
```

### Command Not Found

```bash
pip show dbskiter
which dbskiter
```

---

**Next tutorial**: [First Command](02-first-command.md)