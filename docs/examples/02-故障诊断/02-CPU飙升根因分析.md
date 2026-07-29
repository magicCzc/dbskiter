<!--
文件功能：dbskiter 真实故障诊断案例 - CPU 飙升根因分析
主要类/函数：无（文档案例）
作者：MagiCzc
创建时间：2026-06-18
最后修改：2026-06-18
-->

# 案例：CPU 飙升，根因分析定位到一条 SQL

## 场景背景

- **时间**：2026-06-15 周二 15:00
- **现象**：监控告警：jump 数据库 CPU 使用率从 30% 飙升到 **85%**，持续 10 分钟
- **数据库**：MySQL 8.0.32，业务库 `jump`
- **环境**：无专职 DBA，后端工程师收到告警后排查

> 生活化比喻：数据库 CPU 就像厨房里的炉灶。平时 3 个灶眼开火，CPU 30%。突然某个厨师（SQL）同时炒 100 道菜（全表扫描），所有灶眼都被占满，CPU 直接飙到 85%，其他厨师（正常请求）只能排队等。

---

## 排查步骤

### 1. 实时诊断：先看当前谁在"放火"（30 秒）

```bash
dbskiter --database=jump diagnose realtime
```

**关键输出**：

```
实时诊断快照（2026-06-15 15:03:22）
========================================
CPU 使用率: 83.7%（基线: 30%）↑ 异常
活跃连接数: 47 / 151
QPS: 1,250
线程状态分布:
  - Sending data: 18 个（高！）
  - Sorting result: 7 个
  - Waiting for table lock: 3 个
```

> 解读：`Sending data` 表示 MySQL 正在**扫描数据并返回结果**。18 个线程同时在干这个，说明有大量查询在翻箱倒柜找数据。

---

### 2. 抓 TOP SQL：找到"最忙的厨师"（1 分钟）

```bash
dbskiter --database=jump diagnose top
```

**TOP 5 耗时 SQL**：

| 排名 | SQL 摘要 | 执行次数 | 总耗时 | 平均耗时 | 扫描行数 |
|------|---------|---------|--------|---------|---------|
| 1 | `SELECT ... FROM orders WHERE status = ?` | 1,245 | 420s | 0.34s | 1,247,000 |
| 2 | `SELECT COUNT(*) FROM logs WHERE ...` | 890 | 180s | 0.20s | 8,500,000 |
| 3 | `SELECT * FROM users WHERE ...` | 567 | 45s | 0.08s | 12,000 |

**元凶锁定**：
- `orders` 表查询：平均 0.34s，但执行了 1,245 次，**累计扫描 15 亿行**
- `status = 'pending'` 这个条件，全表扫描，无索引

---

### 3. 执行计划分析：确认它为什么慢（1 分钟）

```bash
dbskiter --database=jump audit sql "
SELECT o.*, u.username, u.phone
FROM orders o
LEFT JOIN users u ON o.user_id = u.id
WHERE o.status = 'pending'
ORDER BY o.create_time DESC
"
```

**审核结果**：

```
[CRITICAL] 全表扫描: orders 表扫描 1,247,000 行
[WARNING] 无可用索引: WHERE status = 'pending' 无索引匹配
[INFO] 使用临时表 + filesort 排序
[INFO] JOIN 使用 users.id 主键索引（索引查找）
```

> 问题定位：`orders` 表的 `status` 字段没有索引。`pending` 状态的订单约占 20%（25 万条），每次查询都要扫描全表。

---

### 4. 根因分析：为什么今天突然出问题（2 分钟）

```bash
dbskiter --database=jump inspector root-cause --issue="CPU 使用率飙升至 85%"
```

**AI 分析结果**：

```
根因分析：

1. 触发事件（15:00）
   - 业务上线新功能："批量导出待处理订单"
   - 前端页面每 5 秒自动刷新一次订单列表

2. 主因
   - 新增查询 `orders WHERE status='pending'` 无索引
   - 每次刷新触发 1 次查询，1,247,000 行全表扫描
   - 15:00-15:10 期间，并发用户 30 人，触发 1,245 次查询
   - 累计扫描 15 亿行数据，CPU 被占用 83.7%

3. 次要因素
   - 临时表磁盘排序消耗额外 CPU（61.96% 临时表落盘）
   - `SELECT *` 返回 28 列，网络传输和内存拷贝开销大

4. 时间线验证
   - 14:55 CPU: 32%（正常）
   - 15:00 CPU: 58%（新功能上线）
   - 15:03 CPU: 85%（并发刷新峰值）
   - 15:12 CPU: 35%（功能回滚后恢复正常）
```

---

## 解决方案

### 紧急止血（立即）

```bash
# 先杀掉正在执行的慢查询（注意：确认不影响业务后执行）
dbskiter --database=jump diagnose sql "
SELECT id FROM information_schema.processlist
WHERE command = 'Query' AND time > 10
"

# 或者让开发回滚前端自动刷新功能（5 秒 → 60 秒）
```

### 根治方案（当天）

```sql
-- 步骤 1：添加索引（业务低峰期执行，如凌晨）
CREATE INDEX idx_orders_status ON orders(status);

-- 步骤 2：如果 status 选择性低（如只有 pending/resolved 两种），用复合索引
CREATE INDEX idx_orders_status_ctime ON orders(status, create_time);

-- 步骤 3：前端优化，避免 SELECT *，减少返回列
-- 只返回需要的字段：id, amount, status, create_time, user_id
```

### 验证优化效果

```bash
dbskiter --database=jump audit sql "
SELECT o.id, o.amount, o.status, o.create_time, u.username, u.phone
FROM orders o
LEFT JOIN users u ON o.user_id = u.id
WHERE o.status = 'pending'
ORDER BY o.create_time DESC
LIMIT 100;
"
```

**优化后指标**：

| 指标 | 优化前 | 优化后 | 提升 |
|------|--------|--------|------|
| 执行时间 | 0.34s | **0.005s** | **68x** |
| 扫描行数 | 1,247,000 | **1,200** | **99.9%** |
| CPU 影响 | 83.7% | **< 5%** | 恢复正常 |
| 索引使用 | 无 | **idx_orders_status_ctime** | 覆盖查询 |

---

## 复盘要点

### 1. CPU 飙升排查口诀

```
CPU 高 → 看实时 → 抓 TOP SQL → 看执行计划 → 找根因 → 加索引/优化
```

### 2. 关键判断指标

| 指标 | 含义 | 正常范围 | 异常时行动 |
|------|------|---------|-----------|
| `Sending data` 线程数 | 扫描数据的线程 | < 5 | > 10 说明大量全表扫描 |
| 扫描行数 / 返回行数 | 查询效率 | < 100 | > 1000 说明索引缺失 |
| 单次查询 CPU 时间 | 查询本身消耗 | < 0.1s | > 0.5s 要优化 |
| 并发执行次数 | 是否被频繁调用 | 看业务 | 高频查询必须走索引 |

### 3. 常见 CPU 飙升原因

| 排名 | 原因 | 特征 | 排查命令 |
|------|------|------|---------|
| 1 | **缺少索引的全表扫描** | `Sending data` 多，扫描行数大 | `diagnose top` |
| 2 | **大量排序 / 临时表** | `Sorting result`、`Creating tmp table` | `diagnose realtime` |
| 3 | **长事务锁竞争** | `Waiting for lock`、`Locked` | `lock analyze` |
| 4 | **不合理的大查询** | `SELECT *` 返回百万行 | `audit sql` |
| 5 | **突增并发** | 连接数突增，QPS 翻倍 | `monitor health` |

### 4. 预防措施

```bash
# 1. 建立性能基线（知道正常 CPU 是多少）
dbskiter --database=jump inspector baseline --create

# 2. 设置异常检测（自动发现 CPU 偏离基线）
dbskiter --database=jump inspector anomalies --metric=cpu_usage --hours=24

# 3. 慢查询阈值调低（1-2 秒），提前捕获问题 SQL
dbskiter --database=jump inspector run --type configuration

# 4. 定期巡检，发现缺失索引
dbskiter --database=jump inspector run --type performance
```

---

## 延伸阅读

- [案例：业务卡顿查慢查询](./01-业务卡顿查慢查询.md)
- [案例：磁盘空间告警](./03-磁盘空间告警.md)
- [案例：连接数打满](./04-连接数打满.md)
- dbskiter 命令：`diagnose realtime`、`diagnose top`、`inspector root-cause`、`audit sql`
