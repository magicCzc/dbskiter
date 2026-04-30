# DBSKiter Skill 系统

DBSKiter 的 AI Skill 定义目录，用于支持 AI IDE（如 Trae、Cursor）的自然语言交互。

---

## 什么是 Skill

Skill 是 AI 助手的"技能手册"，告诉 AI 如何：

1. 理解用户的自然语言意图
2. 选择合适的工具命令
3. 调用 CLI 获取数据
4. 解析结果并回复用户

---

## Skill 目录结构

```
.trae/skills/
├── README.md                 # 本文件：Skill 系统介绍
├── db-monitor/SKILL.md       # 监控 Skill（AI 指令）
├── db-diagnose/SKILL.md      # 诊断 Skill（AI 指令）
├── db-security/SKILL.md      # 安全 Skill（AI 指令）
├── db-inspector/SKILL.md     # 巡检 Skill（AI 指令）
├── db-lock-analyzer/SKILL.md # 锁分析 Skill（AI 指令）
├── db-scheduler/SKILL.md     # 调度 Skill（AI 指令）
├── db-sql-auditor/SKILL.md   # SQL 审核 Skill（AI 指令）
└── sql-master/SKILL.md       # SQL 执行 Skill（AI 指令）
```

---

## 8 大 Skill 模块

| Skill | 功能 | 典型场景 |
|-------|------|----------|
| db-monitor | 健康监控、异常检测、容量预测 | "检查数据库健康"、"容量够吗" |
| db-diagnose | 慢查询分析、SQL 诊断、索引推荐 | "数据库慢了"、"优化这条 SQL" |
| db-security | 安全审计、注入检测、敏感数据扫描 | "做安全检查"、"有敏感数据吗" |
| db-inspector | 巡检、报告生成、根因分析 | "巡检数据库"、"生成报告" |
| db-lock-analyzer | 锁分析、死锁检测、阻塞追踪 | "看锁情况"、"有死锁吗" |
| db-scheduler | 备份、定时任务、工作流 | "备份数据库"、"定时任务" |
| db-sql-auditor | SQL 规范审核、DDL 影响分析 | "审核 SQL"、"DDL 影响" |
| sql-master | SQL 执行、重写优化、数据导出 | "执行 SQL"、"导出数据" |

---

## 工作原理

### 1. 用户输入自然语言

用户说："检查一下 jump 数据库的健康状态"

### 2. AI 读取 Skill 文档

Trae 读取 `db-monitor/SKILL.md`，找到匹配的规则：

```
| 用户说法 | 执行命令 |
|---------|---------|
| "检查健康" | dbskiter --output-mode=ai --database=<name> monitor health |
```

### 3. AI 执行 CLI 命令

Trae 内部执行：

```bash
dbskiter --output-mode=ai --database=jump monitor health
```

### 4. 获取结构化 JSON 输出

```json
{
  "schema_version": "1.0",
  "collected_at": "2026-04-28T10:30:00Z",
  "data": {
    "raw_metrics": {"cpu_usage": 45.2, "memory_usage": 60.5},
    "rule_flags": {"cpu_normal": {"flagged": false}},
    "context": {"database_type": "mysql", "version": "8.0"},
    "ai_hints": {"focus_areas": ["整体健康良好"]}
  }
}
```

### 5. AI 生成自然语言回复

"jump 数据库当前健康状态良好，CPU 使用率 45%，内存使用率 60%，无异常指标。"

---

## 输出模式说明

所有 Skill 命令默认使用 `--output-mode=ai`，输出结构化 JSON，便于 AI 解析。

| 模式 | 说明 | 用途 |
|------|------|------|
| ai | 结构化 JSON | AI 分析（默认） |
| raw | 原始数据 | 脚本处理 |
| rule | 格式化文本 | 人类直接阅读 |

---

## 支持的数据库

- MySQL 5.7/8.0
- PostgreSQL 10-16
- Oracle 11g/12c/19c/21c

---

## 相关文档

- [CLI 使用指南](../../CLI使用指南.md) - 完整的 CLI 命令参考
- [AI 集成指南](../../AI集成指南.md) - AI 助手集成说明
- [项目 README](../../README.md) - 项目总体介绍

---

## 开发说明

Skill 文档使用标准 Markdown 格式，包含：

1. **元信息**：name、description（YAML front matter）
2. **使用场景**：用户可能的说法
3. **命令映射**：自然语言到 CLI 命令的映射
4. **AI 决策流程**：如何处理不同场景

---

## License

MIT
