# DBSKiter API 参考

DBSKiter 8 个核心 Skill 的 API 参考文档。

## 核心 Skill

| Skill | 入口类 | 描述 |
|-------|--------|------|
| {doc}`diagnose <api/dbskiter.db_diagnose>` | ``DiagnoseSkill`` | 数据库诊断（慢查询、锁、空间、复制） |
| {doc}`monitor <api/dbskiter.db_monitor>` | ``MonitorSkill`` | 监控（健康检查、异常检测、容量预测） |
| {doc}`security <api/dbskiter.db_security>` | ``SecuritySkill`` | 安全（SQL注入、敏感数据、密码策略） |
| {doc}`scheduler <api/dbskiter.db_scheduler>` | ``SchedulerSkill`` | 调度（备份、定时任务、连接池） |
| {doc}`inspector <api/dbskiter.db_inspector>` | ``InspectorSkill`` | 巡检（综合检查、报告、基线） |
| {doc}`lock <api/dbskiter.db_lock_analyzer>` | ``LockAnalyzerSkill`` | 锁分析（死锁、等待链） |
| {doc}`sql_master <api/dbskiter.sql_master>` | ``SQLMasterSkill`` | SQL 执行（执行、审核、重写、缓存） |
| {doc}`auditor <api/dbskiter.db_sql_auditor>` | ``SQLAuditorSkill`` | SQL 审核（DDL 影响、优化建议） |

## 共享组件

| 模块 | 描述 |
|------|------|
| {doc}`shared <api/dbskiter.shared>` | 连接器、AAS 计算、Prometheus 集成 |

## 数据模型

每个 Skill 的 ``models.py`` 定义了数据模型，包括：

- ``DiagnoseResult``: 诊断结果
- ``SlowQuery``: 慢查询信息
- ``HealthAssessment``: 健康评估
- ``RiskReport``: 安全风险报告
- ``BackupResult``: 备份结果
- ``InspectionReport``: 巡检报告
- ``LockInfo``: 锁信息
- ``AuditResult``: 审核结果

## 生成说明

```bash
# 1. 安装 Sphinx 依赖
pip install sphinx sphinx-rtd-theme sphinx-autodoc-typehints myst-parser

# 2. 自动生成 API 文档
sphinx-apidoc -o docs/source/api dbskiter/ -f \
    -d 4 \
    dbskiter/*/test* \
    dbskiter/*/__pycache__* \
    dbskiter/*/backup/*

# 3. 构建 HTML
sphinx-build -b html docs/source docs/api

# 4. 访问 docs/api/index.html
```