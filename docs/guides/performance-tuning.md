<!--
文件功能：DBSKiter 性能调优指南
作者：MagiCzc
创建时间：2026-07-24
-->

# 性能调优指南

DBSKiter 使用过程中的性能优化建议。

---

## CLI 启动时间

### 目标

```bash
time dbskiter --version
# 目标: < 200ms
```

### 优化方法

1. **使用虚拟环境**：避免全局 site-packages 版本冲突
2. **懒加载**：自定义 Skill 使用 `import` 在函数体内而非模块顶部
3. **禁用不用的插件**：

```bash
# 查看启动时间
python -X importtime -c "import dbskiter" 2> import_timing.txt
# 分析耗时最多的模块
sort -rn import_timing.txt | head -10
```

### 常见问题

| 问题 | 原因 | 解决 |
|------|------|------|
| 启动 > 1s | 系统 Python 慢 | 使用 pyenv/venv |
| 启动 > 2s | 依赖冲突 | `pip check` |
| 启动 > 5s | 自定义 Skill 过多 | 检查 `__init__.py` 导入 |

---

## 慢查询分析

### 数据库配置

**MySQL**：

```ini
[mysqld]
slow_query_log = 1
long_query_time = 2
log_output = TABLE
performance_schema = ON
```

**PostgreSQL**：

```sql
-- postgresql.conf
shared_preload_libraries = 'pg_stat_statements'
-- 重启后
CREATE EXTENSION pg_stat_statements;
```

### DBSKiter 调优

```bash
# 限制时间范围（减少采集量）
dbskiter diagnose slow-queries --hours=1

# 限制返回数量
dbskiter diagnose slow-queries --top=10

# 使用采样（仅 MySQL）
dbskiter diagnose slow-queries --sample-rate=10
```

---

## 备份性能

### 并行备份

```bash
# 4 线程并行
dbskiter scheduler backup --type=full --parallel=4
```

### 压缩备份

```bash
# Gzip 压缩（减少存储，增加 CPU）
dbskiter scheduler backup --type=full --compress=gzip
```

### 最佳实践

| 数据量 | 策略 | 预期时间 |
|--------|------|----------|
| < 1GB | 逻辑备份 | < 1min |
| 1-10GB | 逻辑备份 + 压缩 | 1-5min |
| 10-100GB | 物理备份 + 并行 | 5-30min |
| > 100GB | 物理备份 + 增量 | 视情况 |

---

**最后更新**：2026-07-24