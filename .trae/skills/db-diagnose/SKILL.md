---
name: db-diagnose
description: |
  数据库诊断与优化，支持实时诊断、慢查询分析、SQL诊断、索引推荐、性能快照、瓶颈分析。

  使用场景：
  - 用户说"数据库慢了" -> 执行 realtime
  - 用户说"SQL有问题" -> 执行 sql "<SQL>"
  - 用户说"推荐索引" -> 执行 recommend-indexes
  - 用户说"全面检查" -> 执行 report
  - 用户说"性能分析" -> 执行 performance-snapshot
  - 用户说"瓶颈分析" -> 执行 bottleneck

  用法：
  - dbskiter --output-mode=ai --database=<name> diagnose realtime
  - dbskiter --output-mode=ai --database=<name> diagnose sql "SELECT * FROM users"
  - dbskiter --output-mode=ai --database=<name> diagnose recommend-indexes
  - dbskiter --output-mode=ai --database=<name> diagnose report
  - dbskiter --output-mode=ai --database=<name> diagnose performance-snapshot
  - dbskiter --output-mode=ai --database=<name> diagnose bottleneck
---

# 数据库诊断 Skill

## 何时使用

当用户提到以下关键词时，使用此skill：

| 用户说法 | 执行命令 | 说明 |
|---------|---------|------|
| "数据库慢了" / "卡住了" | `dbskiter --output-mode=ai --database=<name> diagnose realtime` | 实时诊断当前性能问题 |
| "CPU飙高了" | `dbskiter --output-mode=ai --database=<name> diagnose top` | 查看资源消耗最高的SQL |
| "有死锁" / "有阻塞" | `dbskiter --output-mode=ai --database=<name> diagnose locks` | 检测死锁和阻塞 |
| "SQL有问题" | `dbskiter --output-mode=ai --database=<name> diagnose sql "<SQL>"` | 诊断特定SQL |
| "空间不够了" | `dbskiter --output-mode=ai --database=<name> diagnose space` | 分析表空间和碎片 |
| "连接数满了" | `dbskiter --output-mode=ai --database=<name> diagnose connections` | 分析连接池状态 |
| "主从延迟" | `dbskiter --output-mode=ai --database=<name> diagnose replication` | 分析复制状态 |
| "慢查询" | `dbskiter --output-mode=ai --database=<name> diagnose slow-queries` | 查看历史慢查询 |
| "加什么索引" | `dbskiter --output-mode=ai --database=<name> diagnose recommend-indexes` | 获取索引建议 |
| "检查一下" | `dbskiter --output-mode=ai --database=<name> diagnose report` | 全面诊断报告 |
| "性能分析" | `dbskiter --output-mode=ai --database=<name> diagnose performance-snapshot` | 采集性能快照 |
| "瓶颈分析" | `dbskiter --output-mode=ai --database=<name> diagnose bottleneck` | 分析性能瓶颈 |

## 数据库支持

### 统一性能模型支持

| 数据库 | 性能快照 | 瓶颈分析 | 慢查询 | 状态 |
|-------|---------|---------|--------|------|
| MySQL | 支持 | 支持 | 支持 | 生产就绪 |
| Oracle | 支持 | 支持 | 支持 | 生产就绪 |
| PostgreSQL | 支持 | 支持 | 支持 | 生产就绪 |

**说明**：
- MySQL：支持5.7/8.0，自动降级（performance_schema -> information_schema -> SHOW STATUS）
- Oracle：支持11g/12c/19c/21c，自动降级（AWR -> V$视图 -> 基础统计），支持RAC
- PostgreSQL：支持10-16，自动降级（pg_stat_statements -> pg_stat_activity），支持pg_stat_kcache扩展

### 索引建议支持

| 数据库 | 缺失索引 | 冗余索引 | 未使用索引 | 低基数索引 | 状态 |
|-------|---------|---------|-----------|-----------|------|
| MySQL | 支持 | 支持 | 支持 | 支持 | 生产就绪 |
| Oracle | 支持 | 支持 | 支持 | 支持 | 生产就绪 |
| PostgreSQL | 支持 | 支持 | 支持 | 支持 | 生产就绪 |

**索引分析维度**：
- 缺失索引：基于全表扫描统计识别需要索引的表
- 冗余索引：检测重复索引和前缀冗余索引
- 未使用索引：基于统计信息识别从未使用的索引
- 低基数索引：检测选择性差的索引（如性别、状态字段）

## 核心命令

### P0: 高频场景（每天使用）

#### 1. 实时诊断
```bash
dbskiter --database=<数据库名> diagnose realtime
```
**功能**：分析当前数据库性能问题（活跃连接、锁等待、慢查询）

**可选参数**：
- `--threshold`：慢查询阈值（秒，默认5）

#### 2. TOP SQL分析
```bash
dbskiter --database=<数据库名> diagnose top
```
**功能**：查看资源消耗最高的SQL

**可选参数**：
- `--limit`：返回条数（默认10）
- `--by`：排序依据（time/cpu/io/rows，默认time）

#### 3. 锁分析
```bash
dbskiter --database=<数据库名> diagnose locks
```
**功能**：检测死锁、阻塞、锁等待

**可选参数**：
- `--kill`：显示KILL语句（不执行）

#### 4. SQL深度诊断
```bash
dbskiter --database=<数据库名> diagnose sql "SELECT * FROM users WHERE email = 'test@test.com'"
```
**输出**：评分、问题列表、优化建议

**可选参数**：
- `--params`：SQL参数（JSON格式）

#### 5. 空间诊断
```bash
dbskiter --database=<数据库名> diagnose space
```
**功能**：分析表空间、碎片、大表

**可选参数**：
- `--top`：显示TOP N大表（默认20）
- `--min-size`：最小表大小（MB，默认100）

### P1: 中频场景（每周使用）

#### 6. 连接分析
```bash
dbskiter --database=<数据库名> diagnose connections
```
**功能**：分析连接池、空闲连接

**可选参数**：
- `--idle`：显示空闲连接

#### 7. 复制诊断
```bash
dbskiter --database=<数据库名> diagnose replication
```
**功能**：分析主从延迟、复制状态

#### 8. 慢查询分析
```bash
dbskiter --database=<数据库名> diagnose slow-queries
```
**功能**：分析历史慢查询

**可选参数**：
- `--limit`：返回条数（默认10）
- `--min-time`：最小执行时间（秒，默认1.0）

#### 9. 索引建议
```bash
dbskiter --database=<数据库名> diagnose recommend-indexes
```
**功能**：全库索引分析和建议

**可选参数**：
- `--table`：指定表名（默认全库）

### P2: 低频场景（每月使用）

#### 10. 综合诊断报告
```bash
dbskiter --database=<数据库名> diagnose report
```
**功能**：生成完整诊断报告

#### 11. 单表诊断
```bash
dbskiter --database=<数据库名> diagnose table <表名>
```
**功能**：分析单表结构和性能

#### 12. 性能快照
```bash
dbskiter --database=<数据库名> diagnose performance-snapshot
```
**功能**：采集数据库性能指标（CPU、IO、内存、并发、锁等）

**可选参数**：
- `--output`：输出文件路径（JSON格式）

#### 13. 瓶颈分析
```bash
dbskiter --database=<数据库名> diagnose bottleneck
```
**功能**：自动识别性能瓶颈并给出优化建议

**可选参数**：
- `--top`：显示TOP N瓶颈（默认5）

## AI决策流程

### 场景1：用户说"数据库慢了"

```
步骤1：执行 dbskiter --database=<name> diagnose realtime
步骤2：查看活跃连接、锁等待、慢查询情况
步骤3：如果有慢查询，执行 dbskiter --database=<name> diagnose slow-queries
步骤4：根据诊断结果，执行 dbskiter --database=<name> diagnose recommend-indexes
步骤5：总结给用户："发现X个问题，主要是XX问题，建议..."
```

### 场景2：用户说"CPU使用率很高"

```
步骤1：执行 dbskiter --database=<name> diagnose top --by=cpu
步骤2：查看CPU消耗最高的SQL
步骤3：执行 dbskiter --database=<name> diagnose sql "<SQL>" 分析具体SQL
步骤4：给出优化建议
```

### 场景3：用户说"帮我优化这个SQL"

```
步骤1：执行 dbskiter --database=<name> diagnose sql "<SQL>"
步骤2：如果评分<70，执行 dbskiter --database=<name> diagnose recommend-indexes
步骤3：给出优化后的SQL和建议
```

### 场景4：用户说"做个全面检查"

```
步骤1：执行 dbskiter --database=<name> diagnose performance-snapshot（查看当前性能状态）
步骤2：执行 dbskiter --database=<name> diagnose report（获取综合报告）
```
