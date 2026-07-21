"""
DBSKiter - 数据库AIOps运维助手

功能说明：
- 提供8个核心Skill：诊断、监控、安全、调度、SQL执行、巡检、锁分析、SQL审核
- 支持MySQL、Oracle、PostgreSQL、SQL Server、ClickHouse、SQLite
- 提供CLI命令行工具（8大模块73+子命令）
- 支持环境变量配置连接池参数（DB_POOL_SIZE等）

作者：MagiCzc
创建时间：2026-04-16
最后修改：2026-06-17
"""

__version__ = "3.0.29"
__all__ = [
    "DiagnoseSkill",
    "MonitorSkill",
    "SecuritySkill",
    "SchedulerSkill",
    "SQLMasterSkill",
    "InspectorSkill",
    "LockAnalyzerSkill",
    "SQLAuditorSkill",
]
