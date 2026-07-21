# DBSKiter AI 集成指南

本文档面向 AI IDE 开发者（如 Trae、Cursor 插件开发者），说明如何集成 DBSKiter CLI 实现自然语言数据库运维。

---

## 集成架构

```
用户自然语言输入
    ↓
AI 助手解析意图
    ↓
读取对应 SKILL.md
    ↓
构建 CLI 命令（--output-mode=ai）
    ↓
执行 dbskiter CLI
    ↓
获取结构化 JSON 输出
    ↓
AI 分析并生成回复
    ↓
展示给用户
```

---

## 快速集成

### 1. 配置 Skill 文档

将 `.trae/skills/` 目录下的 SKILL.md 文件放入你的 AI IDE 技能目录：

- Trae: `.trae/skills/`
- Cursor: `.cursor/rules/`
- 其他: 参考对应 IDE 的文档

### 2. 确保 CLI 可用

```bash
# 验证 dbskiter 已安装
dbskiter --version

# 预期输出: dbskiter 3.0.24
```

### 3. 测试集成

用户输入："检查数据库健康"

AI 应该：
1. 识别意图 -> 健康检查
2. 读取 `db-monitor/SKILL.md`
3. 执行：`dbskiter --output-mode=ai --database=<name> monitor health`
4. 解析 JSON 输出
5. 回复用户

---

## AI 输出格式详解

### 标准输出结构（AIEnvelope）

```json
{
  "schema_version": "1.0",
  "collected_at": "2026-04-28T10:30:00+08:00",
  "instance_id": "mysql-prod-01",
  "data_source": {
    "type": "direct",
    "dialect": "mysql",
    "version": "8.0.32"
  },
  "data": {
    "raw_metrics": {...},
    "rule_flags": {...},
    "context": {...},
    "reference_values": {...},
    "ai_hints": {...}
  }
}
```

### 字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| schema_version | string | 输出格式版本号 |
| collected_at | string | 数据采集时间（ISO 8601格式） |
| instance_id | string | 数据库实例标识 |
| data_source | object | 数据来源信息 |
| data | object | 核心数据内容 |

### data 结构详解

#### raw_metrics - 原始指标数据

包含采集的原始数据，不同模块内容不同：

**监控模块示例：**
```json
{
  "cpu_usage": 45.2,
  "memory_usage": 60.5,
  "disk_usage": 72.1,
  "qps": 1250,
  "active_connections": 45
}
```

**诊断模块示例：**
```json
{
  "slow_queries": [
    {"sql": "SELECT * FROM users", "time": 2.5, "rows_examined": 100000}
  ],
  "lock_waits": 3,
  "deadlocks": 0
}
```

#### rule_flags - 规则标记

规则引擎的初筛结果，仅做标记不做结论：

```json
{
  "cpu_high": {
    "flagged": true,
    "reason": "CPU使用率超过80%阈值",
    "threshold": 80,
    "actual_value": 85.2
  },
  "memory_normal": {
    "flagged": false,
    "reason": "内存使用率在正常范围内"
  }
}
```

#### context - 业务上下文

自动推断的数据库上下文信息：

```json
{
  "database_type": "mysql",
  "version": "8.0.32",
  "workload_type": "oltp",
  "top_tables": ["users", "orders", "products"],
  "qps_estimate": 1250,
  "connection_pattern": "steady",
  "business_context_inferred": true
}
```

#### reference_values - 参考值

行业标准和参考基线：

```json
{
  "cpu_warning_threshold": 80,
  "cpu_critical_threshold": 95,
  "memory_warning_threshold": 85,
  "qps_baseline": 1000,
  "connection_limit": 100
}
```

#### ai_hints - AI分析提示

给 AI 的分析建议和关注方向：

```json
{
  "focus_areas": [
    "CPU使用率偏高，建议关注",
    "存在慢查询需要优化"
  ],
  "suggested_commands": [
    "dbskiter --output-mode=ai --database=<name> diagnose slow-queries",
    "dbskiter --output-mode=ai --database=<name> diagnose top"
  ],
  "complexity": "medium",
  "requires_deep_analysis": true
}
```

---

## AI 处理建议

### 1. 解析流程

```python
def process_ai_output(json_output):
    data = json.loads(json_output)
    
    # 1. 检查版本兼容性
    if data['schema_version'] != '1.0':
        logger.warning(f"未知的schema版本: {data['schema_version']}")
    
    # 2. 提取核心数据
    core_data = data['data']
    raw_metrics = core_data['raw_metrics']
    rule_flags = core_data['rule_flags']
    context = core_data['context']
    ai_hints = core_data['ai_hints']
    
    # 3. 根据ai_hints生成回复
    focus_areas = ai_hints.get('focus_areas', [])
    
    # 4. 构建自然语言回复
    response = generate_natural_language(focus_areas, raw_metrics, context)
    
    return response
```

### 2. 生成回复的策略

**策略1：基于 ai_hints.focus_areas**

直接翻译 focus_areas 为自然语言：

```
输入: ["CPU使用率偏高，建议关注", "存在慢查询需要优化"]
输出: "数据库当前CPU使用率偏高，建议关注。同时存在慢查询需要优化。"
```

**策略2：基于 rule_flags**

分析标记的规则，给出优先级排序的建议：

```
输入: {"cpu_high": {"flagged": true, "actual_value": 85.2}}
输出: "检测到CPU使用率85.2%，超过80%阈值，建议进行性能分析。"
```

**策略3：基于 raw_metrics**

直接解读原始指标：

```
输入: {"cpu_usage": 45.2, "memory_usage": 60.5}
输出: "当前CPU使用率45.2%，内存使用率60.5%，整体运行正常。"
```

### 3. 多轮对话处理

当 `ai_hints.requires_deep_analysis` 为 true 时，可以建议用户进行进一步分析：

```
AI回复: "检测到一些需要关注的问题，建议执行以下命令进行深度分析：
1. 查看慢查询: dbskiter --output-mode=ai --database=<name> diagnose slow-queries
2. 分析TOP SQL: dbskiter --output-mode=ai --database=<name> diagnose top

是否需要我帮您执行这些分析？"
```

---

## 错误处理

### CLI 执行失败

```json
{
  "success": false,
  "message": "数据库连接失败: 无法连接到主机",
  "error_code": "CONNECTION_ERROR"
}
```

AI 应该：
1. 解析错误信息
2. 给出用户友好的错误提示
3. 建议检查配置

### 数据为空

```json
{
  "success": true,
  "data": {
    "raw_metrics": {},
    "rule_flags": {},
    "ai_hints": {
      "focus_areas": ["暂无异常数据"]
    }
  }
}
```

AI 应该：
1. 告知用户当前无异常
2. 可以建议定期检查

---

## 最佳实践

### 1. 始终使用 --output-mode=ai

确保获取结构化输出：

```bash
# 正确
dbskiter --output-mode=ai --database=jump monitor health

# 不推荐（输出格式不固定）
dbskiter --database=jump monitor health
```

### 2. 处理敏感信息

默认情况下，敏感信息会被脱敏：

```json
{
  "raw_metrics": {
    "username": "***",
    "password": "***"
  }
}
```

如需完整数据（仅限安全环境），使用 `--no-mask` 参数。

### 3. 控制输出详细程度

根据场景选择 `--ai-depth`：

| 场景 | 参数 | 说明 |
|------|------|------|
| 快速概览 | `--ai-depth=summary` | 只返回关键指标 |
| 标准分析 | `--ai-depth=detail` (默认) | 详细指标和标记 |
| 深度排查 | `--ai-depth=full` | 完整数据包括原始SQL等 |

---

## 示例集成代码

### Python 示例

```python
import subprocess
import json

def execute_dbskiter(command, database):
    """执行 dbskiter 命令并返回解析后的数据"""
    full_command = [
        'dbskiter',
        '--output-mode=ai',
        f'--database={database}',
    ] + command.split()
    
    result = subprocess.run(
        full_command,
        capture_output=True,
        text=True
    )
    
    if result.returncode != 0:
        return {'error': result.stderr}
    
    return json.loads(result.stdout)

def analyze_database_health(database):
    """分析数据库健康状态"""
    data = execute_dbskiter('monitor health', database)
    
    if 'error' in data:
        return f"执行失败: {data['error']}"
    
    core_data = data['data']
    ai_hints = core_data['ai_hints']
    
    # 生成回复
    focus_areas = ai_hints.get('focus_areas', [])
    if focus_areas:
        return "\n".join(focus_areas)
    else:
        return "数据库运行正常，无异常指标。"

# 使用
response = analyze_database_health('jump')
print(response)
```

### Node.js 示例

```javascript
const { exec } = require('child_process');
const util = require('util');
const execPromise = util.promisify(exec);

async function executeDbskiter(command, database) {
    const fullCommand = `dbskiter --output-mode=ai --database=${database} ${command}`;
    
    try {
        const { stdout } = await execPromise(fullCommand);
        return JSON.parse(stdout);
    } catch (error) {
        return { error: error.message };
    }
}

async function analyzeDatabaseHealth(database) {
    const data = await executeDbskiter('monitor health', database);
    
    if (data.error) {
        return `执行失败: ${data.error}`;
    }
    
    const aiHints = data.data.ai_hints;
    const focusAreas = aiHints.focus_areas || [];
    
    if (focusAreas.length > 0) {
        return focusAreas.join('\n');
    } else {
        return '数据库运行正常，无异常指标。';
    }
}

// 使用
analyzeDatabaseHealth('jump').then(console.log);
```

---

## 相关文档

- [CLI 使用指南](CLI使用指南.md) - 完整的 CLI 命令参考
- [.trae/skills/README.md](.trae/skills/README.md) - Skill 系统介绍
- [项目 README](README.md) - 项目总体介绍

---

## 技术支持

如有集成问题，请参考：

1. 检查 CLI 版本：`dbskiter --version`
2. 验证命令：`dbskiter --output-mode=ai --database=<name> monitor health`
3. 查看错误日志：添加 `--debug` 参数

---

## License

MIT
