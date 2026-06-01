"""
db_sql_auditor - SQL全生命周期审核（模块化重构版）

文件功能：提供SQL审核、规范检查、性能评估、变更影响分析能力
主要类：SQLAuditorSkill - SQL审核技能统一入口

功能特性：
1. SQL规范审核 - 检查SQL是否符合规范
2. 性能审核 - 评估SQL性能风险
3. 安全审核 - 检查SQL安全风险
4. 变更影响分析 - 分析DDL变更影响
5. 审核规则管理 - 自定义审核规则
6. 审核报告生成 - 生成详细审核报告

使用示例：
    from db_sql_auditor import SQLAuditorSkill

    skill = SQLAuditorSkill(connector)

    # 审核单条SQL
    result = skill.audit_sql("SELECT * FROM users WHERE id = 1")

    # 批量审核
    results = skill.audit_sql_list(sql_list)

    # 变更影响分析
    impact = skill.analyze_ddl_impact("ALTER TABLE users ADD COLUMN age INT")

版本: 3.0.0（模块化重构版）
"""

# 数据模型
from .models import (
    ErrorCode,
    ErrorMessage,
    AuditLevel,
    AuditType,
    SQLType,
    AuditConfig,
    AuditIssue,
    AuditResult,
    AuditRule,
    DDLImpact,
    BatchAuditResult,)

# 响应函数（从shared模块导入）
from dbskiter.shared.error_handler import create_success_response, create_error_response

# 工具类
from .utils import (
    SQLParser,
    RuleEngine,
    ScoreCalculator,
    IssueAggregator,
    SQLNormalizer,
    AuditReporter,
)

# 统一入口
from .skill import SQLAuditorSkill

__all__ = [
    # 数据模型
    "ErrorCode",
    "ErrorMessage",
    "AuditLevel",
    "AuditType",
    "SQLType",
    "AuditConfig",
    "AuditIssue",
    "AuditResult",
    "AuditRule",
    "DDLImpact",
    "BatchAuditResult",
    "create_success_response",
    "create_error_response",
    # 工具类
    "SQLParser",
    "RuleEngine",
    "ScoreCalculator",
    "IssueAggregator",
    "SQLNormalizer",
    "AuditReporter",
    # 主要入口
    "SQLAuditorSkill",
]

__version__ = "3.0.0"
