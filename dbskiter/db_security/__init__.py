"""
db_security Skill - 统一入口（模块化重构版）
数据库安全模块 - SQL注入检测与敏感数据扫描

快速开始:
    from dbskiter.db_security import SecuritySkill

    # 初始化
    skill = SecuritySkill(connector)

    # SQL注入检测
    result = skill.detect_sql_injection("SELECT * FROM users WHERE id = %s")

    # 敏感数据扫描
    scan = skill.scan_sensitive_data()

    # 完整安全审计
    report = skill.full_audit()

    # 获取安全评分
    score = skill.calculate_security_score()

模块结构:
    - models.py - 数据模型和枚举（ErrorCode, Risk, SecurityConfig等）
    - utils.py - 工具类（PatternMatcher, RiskScorer, SecurityAuditor）
    - skill.py - 统一入口（SecuritySkill）
    - sql_injection_detector_v2.py - SQL注入检测器
    - sensitive_data_scanner_v2.py - 敏感数据扫描器

核心功能:
- SQL注入检测 - 基于AST深度分析
- 敏感数据扫描 - 基于内容分析
- 权限审计 - 用户权限风险分析
- 配置审计 - 数据库配置安全检查
- 安全评分 - 量化安全等级（0-100分）
- 完整审计 - 一键生成安全报告

版本: 3.0.0（模块化重构版）
"""

# 数据模型
from .models import (
    ErrorCode,
    ErrorMessage,
    RiskLevel,
    InjectionType,
    SensitivityLevel,
    DataCategory,
    Risk,
    RiskReport,
    SecurityConfig,
    SQLInjectionResult,
    SensitiveDataResult,
    create_success_response,
    create_error_response,
)

# 工具类
from .utils import (
    PatternMatcher,
    EntropyCalculator,
    RiskScorer,
    ReportFormatter,
    SecurityAuditor,
)

# 检测器（新命名）
from .sql_injection_detector import (
    SQLInjectionDetector,
    RiskLevel as DetectorRiskLevel,
    InjectionType as DetectorInjectionType,
)
from .sensitive_data_scanner import (
    SensitiveDataScanner,
    SensitivityLevel as ScannerSensitivityLevel,
    DataCategory as ScannerDataCategory,
)

# 向后兼容（V2 别名）
from .sql_injection_detector_v2 import (
    SQLInjectionDetectorV2,
)
from .sensitive_data_scanner_v2 import (
    SensitiveDataScannerV2,
)

# 主Skill类
from .skill import SecuritySkill

__all__ = [
    # 数据模型
    "ErrorCode",
    "ErrorMessage",
    "RiskLevel",
    "InjectionType",
    "SensitivityLevel",
    "DataCategory",
    "Risk",
    "RiskReport",
    "SecurityConfig",
    "SQLInjectionResult",
    "SensitiveDataResult",
    "create_success_response",
    "create_error_response",
    # 工具类
    "PatternMatcher",
    "EntropyCalculator",
    "RiskScorer",
    "ReportFormatter",
    "SecurityAuditor",
    # 检测器
    "SQLInjectionDetectorV2",
    "SensitiveDataScannerV2",
    # 主Skill类
    "SecuritySkill",
]

__version__ = "3.0.0"
