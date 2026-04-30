---
name: db-monitor
description: |
  数据库健康监控，支持健康检查、异常检测、容量预测、趋势分析、基线对比。

  智能数据源选择：
  - Oracle 数据库自动使用 Zabbix 监控
  - MySQL 数据库优先使用直连，其次使用 Prometheus
  - 支持 Z 系列资产组（如 Z18, Z5）自动识别

  使用场景：
  - 用户说"检查健康" -> 执行 health
  - 用户说"有异常吗" -> 执行 anomalies
  - 用户说"容量够吗" -> 执行 capacity
  - 用户说"采集指标" -> 执行 collect
  - 用户说"看历史" -> 执行 history
  - 用户说"高级容量预测" -> 执行 capacity-advanced
  - 用户说"趋势分析" -> 执行 trend
  - 用户说"基线对比" -> 执行 compare

  用法：
  - dbskiter --output-mode=ai --database=<name> monitor health
  - dbskiter --output-mode=ai --database=<name> monitor anomalies
  - dbskiter --output-mode=ai --database=<name> monitor capacity --resource=disk
  - dbskiter --output-mode=ai --database=<name> monitor collect
  - dbskiter --output-mode=ai --database=<name> monitor history <metric>
  - dbskiter --output-mode=ai --database=<name> monitor capacity-advanced --resource=disk
  - dbskiter --output-mode=ai --database=<name> monitor trend --metric=cpu_usage
  - dbskiter --output-mode=ai --database=<name> monitor compare --metric=qps --value=1250 --baseline=2026-04-01
---

# 数据库监控 Skill

## 智能数据源选择

系统会根据 `--database` 参数自动选择最优数据源：

| 数据库类型 | 识别规则 | 数据源优先级 |
|-----------|---------|-------------|
| Oracle | Z 系列资产组（Z18, Z5等）或 KF 系列 | Zabbix |
| MySQL | 其他名称 | 直连数据库 > Prometheus |

**示例**:
```bash
# Oracle 数据库（自动使用 Zabbix）
dbskiter --output-mode=ai --database=Z18 monitor health
dbskiter --output-mode=ai --database=Z5 monitor capacity --resource=disk

# MySQL 数据库（优先直连，其次 Prometheus）
dbskiter --output-mode=ai --database=jump monitor health
dbskiter --output-mode=ai --database=prod monitor anomalies
```

## 何时使用

当用户提到以下关键词时，使用此skill：

| 用户说法 | 执行命令 | 说明 |
|---------|---------|------|
| "检查健康" | `dbskiter --output-mode=ai --database=<name> monitor health` | 整体健康评分 |
| "批量检查健康" | `dbskiter --output-mode=ai monitor health-all` | 检查所有数据库 |
| "有异常吗" | `dbskiter --output-mode=ai --database=<name> monitor anomalies` | 检测异常指标 |
| "容量够吗" | `dbskiter --output-mode=ai --database=<name> monitor capacity` | 容量预测 |
| "采集数据" | `dbskiter --output-mode=ai --database=<name> monitor collect` | 采集当前指标 |
| "看历史" | `dbskiter --output-mode=ai --database=<name> monitor history <指标>` | 查看指标历史 |
| "高级容量预测" | `dbskiter --output-mode=ai --database=<name> monitor capacity-advanced` | 多算法容量预测 |
| "趋势分析" | `dbskiter --output-mode=ai --database=<name> monitor trend` | 指标趋势分析 |
| "基线对比" | `dbskiter --output-mode=ai --database=<name> monitor compare` | 与历史基线对比 |

## 核心命令

### 1. 健康检查
```bash
dbskiter --database=<数据库名> monitor health
```
**功能**：整体健康评分和状态检查

### 2. 批量健康检查
```bash
dbskiter monitor health-all
```
**功能**：批量检查所有配置的数据库健康状态

### 3. 异常检测
```bash
dbskiter --database=<数据库名> monitor anomalies
```
**功能**：检测异常指标

**可选参数**：
- `--hours`：检测时间范围（小时，默认1）

### 4. 容量预测
```bash
dbskiter --database=<数据库名> monitor capacity --resource=disk
```
**功能**：预测资源容量使用情况

**可选参数**：
- `--resource`：资源类型（disk/memory/connections，默认disk）
- `--days`：预测天数（默认30）
- `--source`：数据来源（auto/prometheus/zabbix/internal，默认auto）

### 5. 指标采集
```bash
dbskiter --database=<数据库名> monitor collect
```
**功能**：采集当前指标数据

**可选参数**：
- `--metrics`：指定指标（逗号分隔）
- `--source`：数据来源（auto/prometheus/zabbix/internal，默认auto）

### 6. 历史查询
```bash
dbskiter --database=<数据库名> monitor history cpu_usage
```
**功能**：查看指标历史数据

**参数**：
- `metric`（必需）：指标名称

**可选参数**：
- `--hours`：查询小时数（默认24）

### 7. 高级容量预测
```bash
dbskiter --database=<数据库名> monitor capacity-advanced --resource=disk
```
**功能**：使用多算法进行更精确的容量预测

**可选参数**：
- `--resource`：资源类型（disk/memory/connections/cpu/qps，默认disk）
- `--days`：预测天数（默认30）

**输出示例**：
```json
{
  "algorithm": "linear_regression",
  "confidence": 0.85,
  "predictions": {
    "7d": 68.5,
    "30d": 75.2,
    "90d": 88.5
  },
  "days_to_threshold": 45,
  "recommendation": "建议在45天内扩容"
}
```

### 8. 趋势分析
```bash
dbskiter --database=<数据库名> monitor trend --metric=cpu_usage
```
**功能**：分析指标变化趋势

**参数**：
- `--metric`（必需）：指标名称

**可选参数**：
- `--days`：分析天数（默认7）

**输出示例**：
```json
{
  "trend_direction": "degrading",
  "current_value": 75.5,
  "historical_avg": 65.2,
  "change_percent": 15.8,
  "recommendation": "CPU使用率呈恶化趋势，建议关注"
}
```

### 9. 基线对比
```bash
dbskiter --database=<数据库名> monitor compare --metric=qps --value=1250 --baseline=2026-04-01
```
**功能**：对比当前性能与历史基线

**参数**：
- `--metric`（必需）：指标名称
- `--value`（必需）：当前值
- `--baseline`（必需）：基线日期（YYYY-MM-DD格式）

**输出示例**：
```json
{
  "current_value": 1250,
  "baseline_value": 1000,
  "change_percent": 25.0,
  "severity": "normal",
  "message": "QPS较基线上升25.0%，在正常范围内"
}
```

## AI决策流程

### 场景1：用户说"检查数据库健康"

```
步骤1：执行 dbskiter --database=<name> monitor health
步骤2：解读健康评分和各项指标
步骤3：如果有异常，建议执行 diagnose realtime 进一步诊断
```

### 场景2：用户说"容量够吗"

```
步骤1：执行 dbskiter --database=<name> monitor capacity
步骤2：查看容量预测结果
步骤3：如果预测短期内将满，建议扩容
```

### 场景3：用户说"看看CPU趋势"

```
步骤1：执行 dbskiter --database=<name> monitor trend --metric=cpu_usage --days=7
步骤2：分析趋势方向和变化幅度
步骤3：给出趋势解读和建议
```
