# DBSKiter AI Integration Guide (English)

Let your AI assistant (Claude, Cursor, Trae) directly manage databases.

---

## Integration Architecture

```
User's natural language → AI parses intent → CLI executes → JSON output → AI responds
```

## MCP Integration (Claude Desktop)

### 1. Install MCP Server

```bash
pip install dbskiter-mcp-server
```

### 2. Configure Claude Desktop

```json
// ~/.config/claude/claude_desktop_config.json (macOS/Linux)
// %APPDATA%\Claude\claude_desktop_config.json (Windows)
{
  "mcpServers": {
    "dbskiter": {
      "command": "dbskiter-mcp",
      "env": {
        "DB_HOST": "localhost",
        "DB_USER": "root",
        "DB_PASSWORD": "your_password",
        "DB_NAME": "mydb"
      }
    }
  }
}
```

### 3. Ask Claude

After restarting Claude Desktop, you can ask:

- "Is my database healthy?"
- "Analyze this SQL: SELECT * FROM orders WHERE created_at > '2026-01-01'"
- "List today's 5 slowest queries"
- "What are the security risks in my database?"

## AI Output Format

Always use `--output-mode=ai` for structured JSON:

```bash
dbskiter --output-mode=ai --database=jump monitor health
```

Output:

```json
{
  "schema_version": "1.0",
  "collected_at": "2026-07-24T10:30:00+08:00",
  "instance_id": "mysql-prod-01",
  "data_source": {
    "type": "direct",
    "dialect": "mysql",
    "version": "8.0.32"
  },
  "data": {
    "raw_metrics": {"cpu_usage": 45.2},
    "rule_flags": {"cpu_high": {"flagged": false}},
    "context": {"database_type": "mysql"},
    "reference_values": {"cpu_warning_threshold": 80},
    "ai_hints": {
      "focus_areas": ["Database is running normally"],
      "complexity": "low"
    }
  }
}
```

## AI Processing Strategy

The `ai_hints.focus_areas` field tells the AI which areas need attention:

- Empty → "Database is running normally"
- Has items → Translate each item to natural language
- `requires_deep_analysis: true` → Suggest further diagnosis commands

## Error Handling

When CLI fails:

```json
{
  "success": false,
  "message": "Connection failed: Can't connect to MySQL server",
  "error_code": "CONNECTION_ERROR"
}
```

AI should:
1. Parse error message
2. Give user-friendly error
3. Suggest checking configuration

## Security

- Always use `DBSKITER_READ_ONLY=true` for AI integration
- AI is restricted from executing write operations by rule engine
- Use dedicated monitoring accounts with minimal permissions
- Passwords use environment variables, not CLI arguments

## Depth Control

| Scenario | Parameter | Detail |
|----------|-----------|--------|
| Quick overview | `--ai-depth=summary` | Only key metrics |
| Standard analysis | `--ai-depth=detail` (default) | Full metrics + rules |
| Deep investigation | `--ai-depth=full` | Raw SQL, full details |

## Integration Examples

### Python

```python
import subprocess, json

def execute_dbskiter(command, database):
    full = ['dbskiter', '--output-mode=ai', f'--database={database}'] + command.split()
    result = subprocess.run(full, capture_output=True, text=True)
    if result.returncode != 0:
        return {'error': result.stderr}
    return json.loads(result.stdout)

data = execute_dbskiter('monitor health', 'jump')
focus = data.get('data', {}).get('ai_hints', {}).get('focus_areas', [])
print(focus if focus else "Database is healthy")
```

### Node.js

```javascript
const { exec } = require('child_process');
const util = require('util');
const execPromise = util.promisify(exec);

async function checkHealth(database) {
    const { stdout } = await execPromise(`dbskiter --output-mode=ai --database=${database} monitor health`);
    return JSON.parse(stdout);
}
```

---

## License

MIT