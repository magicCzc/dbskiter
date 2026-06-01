"""
DBSKiter - 数据库AIOps运维助手

功能说明：
- 提供8个核心Skill：诊断、监控、安全、调度、SQL执行、巡检、锁分析、SQL审核
- 支持MySQL、Oracle、PostgreSQL等数据库
- 提供CLI命令行工具

作者：MagiCzc
创建时间：2026-04-16
最后修改：2026-05-25
"""

__version__ = "3.0.0"
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
