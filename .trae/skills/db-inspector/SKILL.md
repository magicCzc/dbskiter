---
name: db-inspector
description: |
  数据库实例巡检与报告生成，支持配置检查、性能检查、安全检查、报告生成、智能巡检、异常检测、根因分析、风险预测。

  使用场景：
  - 用户说"巡检" -> 执行 run
  - 用户说"生成报告" -> 执行 report
  - 用户说"检查配置" -> 执行 run --type configuration
  - 用户说"建立基线" -> 执行 baseline --create
  - 用户说"智能巡检" -> 执行 intelligent
  - 用户说"异常检测" -> 执行 anomalies
  - 用户说"根因分析" -> 执行 root-cause
  - 用户说"风险预测" -> 执行 risks

  用法：
  - python -m dbskiter --output-mode=ai --database=<name> inspector run
  - python -m dbskiter --output-mode=ai --database=<name> inspector report --output report.html
  - python -m dbskiter --output-mode=ai --database=<name> inspector baseline --create
  - python -m dbskiter --output-mode=ai --database=<name> inspector intelligent
  - python -m dbskiter --output-mode=ai --database=<name> inspector anomalies --metric=cpu_usage
  - python -m dbskiter --output-mode=ai --database=<name> inspector root-cause --issue="CPU飙升"
  - python -m dbskiter --output-mode=ai --database=<name> inspector risks --days=7
---

# 数据库巡检 Skill

## 安全原则

本Skill的所有操作均为只读查询，不会修改任何数据：

| 规则 | 说明 |
|------|------|
| 只读操作 | 巡检命令只执行SELECT/SHOW/DESCRIBE等查询操作 |
| 禁止写操作 | 不得通过巡检命令执行DELETE/UPDATE/INSERT/DROP等写操作 |
| 基线创建只记录快照 | baseline --create只记录当前配置快照，不修改数据库 |
| 报告生成只读 | report命令只生成报告文件，不修改数据库 |

## 何时使用

当用户提到以下关键词时，使用此skill：

| 用户说法 | 执行命令 | 说明 |
|---------|---------|------|
| "巡检" | `python -m dbskiter --output-mode=ai --database=<name> inspector run` | 执行完整巡检 |
| "生成报告" | `python -m dbskiter --output-mode=ai --database=<name> inspector report` | 生成巡检报告 |
| "检查配置" | `python -m dbskiter --output-mode=ai --database=<name> inspector run --type configuration` | 仅检查配置 |
| "检查安全" | `python -m dbskiter --output-mode=ai --database=<name> inspector run --type security` | 仅安全检查 |
| "建立基线" | `python -m dbskiter --output-mode=ai --database=<name> inspector baseline --create` | 创建性能基线 |
| "智能巡检" | `python -m dbskiter --output-mode=ai --database=<name> inspector intelligent` | 智能巡检分析 |
| "异常检测" | `python -m dbskiter --output-mode=ai --database=<name> inspector anomalies` | 检测指标异常 |
| "根因分析" | `python -m dbskiter --output-mode=ai --database=<name> inspector root-cause` | 分析问题根因 |
| "风险预测" | `python -m dbskiter --output-mode=ai --database=<name> inspector risks` | 预测未来风险 |

## 核心命令

### 1. 执行完整巡检
```bash
python -m dbskiter --database=<数据库名> inspector run
```
**输出**：健康评分、风险统计、巡检项详情

**评分标准**：
- 90-100：优秀
- 70-89：良好
- <70：需要关注

**可选参数**：
- `--type`：指定巡检类型（configuration/performance/storage/security/capacity/replication）
- `--format`：输出格式（text/json/html/markdown）
- `--output`：输出文件路径

### 2. 生成报告
```bash
python -m dbskiter --database=<数据库名> inspector report --output report.html
```
**支持格式**：HTML、Markdown、JSON

### 3. 基线管理
```bash
dbskiter --database=<数据库名> inspector baseline --create
```
**用途**：建立性能基线，用于后续对比

**可选参数**：
- `--create`：创建新基线
- `--compare`：与基线对比

### 4. 智能巡检
```bash
dbskiter --database=<数据库名> inspector intelligent
```
**功能**：异常检测、根因分析、风险预测、智能建议

**可选参数**：
- `--metrics-file`：指标历史数据文件（JSON格式）

### 5. 异常检测
```bash
dbskiter --database=<数据库名> inspector anomalies --metric=cpu_usage
```
**功能**：检测突然飙升、逐渐增长、周期性异常、基线偏离

**参数**：
- `--metric`（必需）：指标名称（如cpu_usage, memory_usage）
- `--hours`：检测最近多少小时的数据（默认24）

### 6. 根因分析
```bash
dbskiter --database=<数据库名> inspector root-cause --issue="CPU飙升"
```
**功能**：分析异常事件的根因，提供解决建议

**参数**：
- `--issue`（必需）：问题描述（如"CPU使用率飙升"）

### 7. 风险预测
```bash
dbskiter --database=<数据库名> inspector risks --days=7
```
**功能**：预测未来7天/30天的容量和性能风险

**参数**：
- `--days`：预测天数（默认7天）

## 巡检类型

- **configuration**：配置检查
- **performance**：性能检查
- **storage**：存储检查
- **security**：安全检查
- **capacity**：容量检查
- **replication**：复制检查

## AI决策流程

### 场景1：用户说"巡检一下数据库"

```
步骤1：执行 dbskiter --database=<name> inspector run
步骤2：解读健康评分和风险统计
步骤3：如果有严重问题，建议进一步诊断
步骤4：生成报告：dbskiter --database=<name> inspector report
```

### 场景2：用户说"分析一下为什么CPU高"

```
步骤1：执行 dbskiter --database=<name> inspector root-cause --issue="CPU飙升"
步骤2：查看根因分析结果
步骤3：给出解决建议
```

### 场景3：用户说"预测一下未来风险"

```
步骤1：执行 dbskiter --database=<name> inspector risks --days=30
步骤2：解读风险预测结果
步骤3：给出预防和应对措施
```
