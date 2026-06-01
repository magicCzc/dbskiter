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
  - 用户说"表膨胀/碎片" -> 执行 bloat
  - 用户说"索引使用情况" -> 执行 index-usage
  - 用户说"VACUUM状态" -> 执行 vacuum（PostgreSQL）
  - 用户说"表空间碎片" -> 执行 tablespace-fragmentation（Oracle）

  用法：
  - python -m dbskiter --output-mode=ai --database=<name> diagnose realtime
  - python -m dbskiter --output-mode=ai --database=<name> diagnose sql "SELECT * FROM users"
  - python -m dbskiter --output-mode=ai --database=<name> diagnose recommend-indexes
  - python -m dbskiter --output-mode=ai --database=<name> diagnose report
  - python -m dbskiter --output-mode=ai --database=<name> diagnose performance-snapshot
  - python -m dbskiter --output-mode=ai --database=<name> diagnose bottleneck
  - python -m dbskiter --output-mode=ai --database=<name> diagnose bloat
  - python -m dbskiter --output-mode=ai --database=<name> diagnose index-usage
  - python -m dbskiter --output-mode=ai --database=<name> diagnose vacuum
  - python -m dbskiter --output-mode=ai --database=<name> diagnose tablespace-fragmentation
---

# 数据库诊断 Skill

## 安全原则

本Skill的所有操作均为只读查询，不会修改任何数据。但需注意：

| 规则 | 说明 |
|------|------|
| 只读操作 | 诊断命令只执行SELECT/SHOW/DESCRIBE等查询操作 |
| 禁止写操作 | 不得通过诊断命令执行DELETE/UPDATE/INSERT/DROP等写操作 |
| 索引建议仅供参考 | recommend-indexes只提供CREATE INDEX建议，不自动执行 |
| VACUUM建议仅供参考 | vacuum命令只分析状态，不自动执行VACUUM操作 |

## 何时使用

当用户提到以下关键词时，使用此skill：

| 用户说法 | 执行命令 | 说明 |
|---------|---------|------|
| "数据库慢了" / "卡住了" | `python -m dbskiter --output-mode=ai --database=<name> diagnose realtime` | 实时诊断当前性能问题 |
| "CPU飙高了" | `python -m dbskiter --output-mode=ai --database=<name> diagnose top` | 查看资源消耗最高的SQL |
| "有死锁" / "有阻塞" | `python -m dbskiter --output-mode=ai --database=<name> diagnose locks` | 检测死锁和阻塞 |
| "SQL有问题" | `python -m dbskiter --output-mode=ai --database=<name> diagnose sql "<SQL>"` | 诊断特定SQL |
| "空间不够了" | `python -m dbskiter --output-mode=ai --database=<name> diagnose space` | 分析表空间和碎片 |
| "连接数满了" | `python -m dbskiter --output-mode=ai --database=<name> diagnose connections` | 分析连接池状态 |
| "主从延迟" | `python -m dbskiter --output-mode=ai --database=<name> diagnose replication` | 分析复制状态 |
| "慢查询" | `python -m dbskiter --output-mode=ai --database=<name> diagnose slow-queries` | 查看历史慢查询 |
| "加什么索引" | `python -m dbskiter --output-mode=ai --database=<name> diagnose recommend-indexes` | 获取索引建议 |
| "检查一下" | `python -m dbskiter --output-mode=ai --database=<name> diagnose report` | 全面诊断报告 |
| "性能分析" | `python -m dbskiter --output-mode=ai --database=<name> diagnose performance-snapshot` | 采集性能快照 |
| "瓶颈分析" | `python -m dbskiter --output-mode=ai --database=<name> diagnose bottleneck` | 分析性能瓶颈 |
| "表膨胀" / "碎片" | `python -m dbskiter --output-mode=ai --database=<name> diagnose bloat` | 检测表膨胀/碎片 |
| "索引使用情况" | `python -m dbskiter --output-mode=ai --database=<name> diagnose index-usage` | 分析索引使用 |
| "VACUUM状态" | `python -m dbskiter --output-mode=ai --database=<name> diagnose vacuum` | PostgreSQL VACUUM分析 |
| "表空间碎片" | `python -m dbskiter --output-mode=ai --database=<name> diagnose tablespace-fragmentation` | Oracle表空间碎片 |

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
python -m dbskiter --database=<数据库名> diagnose realtime
```
**功能**：分析当前数据库性能问题（活跃连接、锁等待、慢查询）

**可选参数**：
- `--threshold`：慢查询阈值（秒，默认5）

#### 2. TOP SQL分析
```bash
python -m dbskiter --database=<数据库名> diagnose top
```
**功能**：查看资源消耗最高的SQL

**可选参数**：
- `--limit`：返回条数（默认10）
- `--by`：排序依据（time/cpu/io/rows，默认time）

#### 3. 锁分析
```bash
python -m dbskiter --database=<数据库名> diagnose locks
```
**功能**：检测死锁、阻塞、锁等待

**可选参数**：
- `--kill`：显示KILL语句（不执行）

#### 4. SQL深度诊断
```bash
python -m dbskiter --database=<数据库名> diagnose sql "SELECT * FROM users WHERE email = 'test@test.com'"
```
**输出**：评分、问题列表、优化建议

**可选参数**：
- `--params`：SQL参数（JSON格式）

#### 5. 空间诊断
```bash
python -m dbskiter --database=<数据库名> diagnose space
```
**功能**：分析表空间、碎片、大表

**可选参数**：
- `--top`：显示TOP N大表（默认20）
- `--min-size`：最小表大小（MB，默认100）

### P1: 中频场景（每周使用）

#### 6. 连接分析
```bash
python -m dbskiter --database=<数据库名> diagnose connections
```
**功能**：分析连接池、空闲连接

**可选参数**：
- `--idle`：显示空闲连接

#### 7. 复制诊断
```bash
python -m dbskiter --database=<数据库名> diagnose replication
```
**功能**：分析主从延迟、复制状态

#### 8. 慢查询分析
```bash
python -m dbskiter --database=<数据库名> diagnose slow-queries
```
**功能**：分析历史慢查询

**可选参数**：
- `--limit`：返回条数（默认10）
- `--min-time`：最小执行时间（秒，默认1.0）

#### 9. 索引建议
```bash
python -m dbskiter --database=<数据库名> diagnose recommend-indexes
```
**功能**：全库索引分析和建议

**可选参数**：
- `--table`：指定表名（默认全库）

### P2: 低频场景（每月使用）

#### 10. 综合诊断报告
```bash
python -m dbskiter --database=<数据库名> diagnose report
```
**功能**：生成完整诊断报告

#### 11. 单表诊断
```bash
python -m dbskiter --database=<数据库名> diagnose table <表名>
```
**功能**：分析单表结构和性能

#### 12. 性能快照
```bash
python -m dbskiter --database=<数据库名> diagnose performance-snapshot
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

### 数据库特有诊断

#### 14. VACUUM分析（PostgreSQL）
```bash
dbskiter --database=<数据库名> diagnose vacuum
```
**功能**：检查PostgreSQL表清理状态和死元组，评估autovacuum配置

**输出**：健康评分、需VACUUM的表列表、可执行VACUUM命令

#### 15. 膨胀/碎片分析（多数据库）
```bash
dbskiter --database=<数据库名> diagnose bloat
```
**功能**：检测表膨胀和碎片情况
- PostgreSQL：检测MVCC导致的表膨胀
- MySQL：检测InnoDB表碎片
- Oracle：检测表空间碎片

**可选参数**：
- `--threshold`：膨胀率阈值（百分比，默认30）

**输出**：健康评分、膨胀/碎片表列表、优化建议、可执行维护命令

#### 16. 索引使用分析（多数据库）
```bash
dbskiter --database=<数据库名> diagnose index-usage
```
**功能**：识别未使用索引、缺失索引、冗余索引
- MySQL：基于performance_schema分析，支持sys schema冗余索引检测
- Oracle：基于v$object_usage分析，支持无效索引检测
- PostgreSQL：基于pg_stat_user_indexes分析，支持重复索引检测

**输出**：健康评分、未使用索引、高频索引、缺失索引、冗余索引、可执行命令

#### 17. 表空间碎片分析（Oracle）
```bash
dbskiter --database=<数据库名> diagnose tablespace-fragmentation
```
**功能**：分析Oracle表空间碎片情况，基于dba_free_space检测

**输出**：健康评分、碎片表空间列表、整理建议

**注意**：需要DBA权限访问dba_free_space视图

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
