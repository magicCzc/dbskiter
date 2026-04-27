"""
db_security/skill.py
统一入口模块（模块化重构版）

文件功能：提供SecuritySkill统一入口，整合所有安全检测功能
主要类：
    - SecuritySkill: 安全Skill统一入口

依赖模块:
    - models.py - 数据模型和错误码
    - utils.py - 工具类
    - sql_injection_detector_v2.py - SQL注入检测器
    - sensitive_data_scanner_v2.py - 敏感数据扫描器

使用示例:
    >>> from db_security import SecuritySkill
    >>> skill = SecuritySkill(connector)
    >>> result = skill.detect_sql_injection("SELECT * FROM users WHERE id = %s")
    >>> scan = skill.scan_sensitive_data()

版本: 3.0.0（模块化重构版）
作者: AI Assistant
创建时间: 2026-04-23
"""

import logging
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime

from dbskiter.shared.unified_connector import UnifiedConnector, detect_connector_type

# 导入子模块
from .models import (
    ErrorCode, ErrorMessage,
    RiskLevel, InjectionType, SensitivityLevel, DataCategory,
    Risk, RiskReport, SecurityConfig,
    SQLInjectionResult, SensitiveDataResult,
    create_success_response, create_error_response
)
from .utils import (
    PatternMatcher, EntropyCalculator,
    RiskScorer, ReportFormatter, SecurityAuditor
)
from .sql_injection_detector_v2 import SQLInjectionDetectorV2
from .sensitive_data_scanner_v2 import SensitiveDataScannerV2
from .login_security_monitor import LoginSecurityMonitor
from .audit_log_analyzer import AuditLogAnalyzer
from .password_policy_checker import PasswordPolicyChecker
from .advanced_security_analyzer import (
    AdvancedSecurityAnalyzer,
    BehaviorAnalyzer,
    DataFlowAnalyzer,
    ComplianceChecker,
    ThreatLevel
)

logger = logging.getLogger(__name__)


class SecuritySkill:
    """
    数据库安全 Skill - 统一入口（模块化重构版）

    整合所有安全检测功能：
    - SQL注入检测（sql_injection_detector_v2.py）
    - 敏感数据扫描（sensitive_data_scanner_v2.py）
    - 权限审计（utils.py）
    - 配置审计（utils.py）

    使用示例:
        >>> skill = SecuritySkill(connector)
        >>> result = skill.detect_sql_injection(sql, params)
        >>> scan = skill.scan_sensitive_data()
        >>> score = skill.calculate_security_score()
    """

    def __init__(
        self,
        connector: UnifiedConnector,
        config: Optional[SecurityConfig] = None,
        enable_sql_injection_detection: bool = True,
        enable_sensitive_data_scan: bool = True,
        enable_permission_audit: bool = True,
        enable_config_audit: bool = True
    ):
        """
        初始化安全Skill

        参数:
            connector: 数据库连接器
            config: 安全配置
            enable_sql_injection_detection: 启用SQL注入检测
            enable_sensitive_data_scan: 启用敏感数据扫描
            enable_permission_audit: 启用权限审计
            enable_config_audit: 启用配置审计
        """
        self.connector = connector
        self.config = config or SecurityConfig(
            enable_sql_injection_detection=enable_sql_injection_detection,
            enable_sensitive_data_scan=enable_sensitive_data_scan,
            enable_permission_audit=enable_permission_audit,
            enable_config_audit=enable_config_audit
        )

        # 初始化检测器
        self.sql_detector = SQLInjectionDetectorV2()
        self.data_scanner = SensitiveDataScannerV2(connector)
        self.auditor = SecurityAuditor(connector)

        # 初始化新增的安全监控器
        self.login_monitor = LoginSecurityMonitor(connector)
        self.audit_analyzer = AuditLogAnalyzer(connector)
        self.password_checker = PasswordPolicyChecker(connector)

        # 初始化工具
        self.risk_scorer = RiskScorer()
        self.report_formatter = ReportFormatter()

        # 初始化高级安全分析器
        self.advanced_analyzer = AdvancedSecurityAnalyzer(connector)

        # 检测连接器类型 - 传入 dialect 字符串而非 connector 对象
        self._is_unified = True
        self._is_jdbc = "jdbc" in connector.dialect.lower() if hasattr(connector, 'dialect') else False

        logger.info(f"SecuritySkill 初始化完成 (dialect={connector.dialect})")

    def detect_sql_injection(
        self,
        sql: str,
        params: Optional[Dict[str, Any]] = None,
        dialect: str = "mysql"
    ) -> Dict[str, Any]:
        """
        检测SQL注入风险

        参数:
            sql: SQL语句
            params: 查询参数
            dialect: 数据库类型

        返回:
            Dict: 检测结果
        """
        if not self.config.enable_sql_injection_detection:
            return create_error_response(
                "SQL注入检测已禁用",
                ErrorCode.INVALID_PARAM
            )

        if not sql or not sql.strip():
            return create_error_response(
                "SQL语句不能为空",
                ErrorCode.INVALID_PARAM
            )

        try:
            result = self.sql_detector.detect(sql, params, dialect)
            return create_success_response(
                data=result,
                message="SQL注入检测完成"
            )
        except Exception as e:
            logger.error(f"SQL注入检测失败: {e}")
            return create_error_response(
                f"检测失败: {str(e)}",
                ErrorCode.UNKNOWN_ERROR
            )

    def scan_sensitive_data(
        self,
        tables: Optional[List[str]] = None,
        sample_size: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        扫描敏感数据

        参数:
            tables: 指定表列表，None表示所有表
            sample_size: 采样行数

        返回:
            Dict: 扫描结果
        """
        if not self.config.enable_sensitive_data_scan:
            return create_error_response(
                "敏感数据扫描已禁用",
                ErrorCode.INVALID_PARAM
            )

        sample = sample_size or self.config.sample_size

        try:
            result = self.data_scanner.scan(
                tables=tables,
                sample_size=sample
            )

            # 构建详细的执行信息
            total_tables = result.get('total_tables', 0)
            tables_scanned = result.get('tables_scanned', 0)
            total_findings = result.get('total_findings', 0)

            message = f"扫描了{total_tables}个表，在{tables_scanned}个表中发现{total_findings}个敏感字段"
            if total_findings == 0:
                message += "（未发现敏感数据）"

            return create_success_response(
                data={
                    **result,
                    'total_checked': total_tables,  # 用于CLI显示
                    'risks_found': total_findings   # 用于CLI显示
                },
                message=message
            )
        except Exception as e:
            logger.error(f"敏感数据扫描失败: {e}")
            return create_error_response(
                f"扫描失败: {str(e)}",
                ErrorCode.SCAN_FAILED
            )

    def audit_permissions(self) -> Dict[str, Any]:
        """
        审计权限

        返回:
            Dict: 审计结果
        """
        if not self.config.enable_permission_audit:
            return create_error_response(
                "权限审计已禁用",
                ErrorCode.INVALID_PARAM
            )

        try:
            result = self.auditor.audit_permissions()
            return create_success_response(
                data=result,
                message="权限审计完成"
            )
        except Exception as e:
            logger.error(f"权限审计失败: {e}")
            return create_error_response(
                f"审计失败: {str(e)}",
                ErrorCode.AUDIT_FAILED
            )

    def audit_config(self) -> Dict[str, Any]:
        """
        审计配置

        返回:
            Dict: 审计结果
        """
        if not self.config.enable_config_audit:
            return create_error_response(
                "配置审计已禁用",
                ErrorCode.INVALID_PARAM
            )

        try:
            result = self.auditor.audit_config()
            return create_success_response(
                data=result,
                message="配置审计完成"
            )
        except Exception as e:
            logger.error(f"配置审计失败: {e}")
            return create_error_response(
                f"审计失败: {str(e)}",
                ErrorCode.CONFIG_AUDIT_FAILED
            )

    def full_audit(self) -> Dict[str, Any]:
        """
        执行完整安全审计

        返回:
            Dict: 完整审计报告
        """
        logger.info("开始完整安全审计...")

        modules = {}

        # SQL注入检测 - 扫描常见接口表中的SQL语句
        if self.config.enable_sql_injection_detection:
            try:
                sql_injection_result = self._audit_sql_injection_in_tables()
                modules["sql_injection"] = sql_injection_result
            except Exception as e:
                logger.error(f"SQL注入检测失败: {e}")
                modules["sql_injection"] = {
                    "status": "failed",
                    "message": f"SQL注入检测失败: {str(e)}"
                }

        # 敏感数据扫描
        if self.config.enable_sensitive_data_scan:
            scan_result = self.scan_sensitive_data()
            modules["sensitive_data"] = scan_result

        # 权限审计
        if self.config.enable_permission_audit:
            perm_result = self.audit_permissions()
            modules["permissions"] = perm_result

        # 配置审计
        if self.config.enable_config_audit:
            config_result = self.audit_config()
            modules["config"] = config_result

        # 生成综合报告
        report = self.auditor.generate_report(modules)

        # 计算安全评分
        score, grade, deductions = self.risk_scorer.calculate_score(report.risks)

        result = {
            "audit_time": datetime.now().isoformat(),
            "overall_score": round(score, 1),
            "grade": grade,
            "risk_summary": {
                "total": report.total_risks,
                "critical": report.critical_count,
                "high": report.high_count,
                "medium": report.medium_count,
                "low": report.low_count
            },
            "modules": modules,
            "deductions": deductions[:20]
        }

        logger.info(f"安全审计完成，评分: {score:.1f}，等级: {grade}")

        return create_success_response(
            data=result,
            message="安全审计完成"
        )

    def calculate_security_score(self) -> Dict[str, Any]:
        """
        计算安全评分

        返回:
            Dict: 评分结果
        """
        audit_result = self.full_audit()

        if not audit_result.get("success"):
            return {
                "overall_score": 0,
                "grade": "F",
                "assessment": "审计失败",
                "deductions": ["无法完成安全审计"],
                "checked_at": datetime.now().isoformat()
            }

        data = audit_result.get("data", {})

        # 确定评估结果
        grade = data.get("grade", "F")
        assessment_map = {
            "A": "优秀",
            "B": "良好",
            "C": "一般",
            "D": "较差",
            "F": "危险"
        }

        return {
            "overall_score": data.get("overall_score", 0),
            "grade": grade,
            "assessment": assessment_map.get(grade, "未知"),
            "deductions": data.get("deductions", []),
            "risk_summary": data.get("risk_summary", {}),
            "checked_at": datetime.now().isoformat()
        }

    def format_report(self, report: Dict[str, Any]) -> str:
        """
        格式化报告为文本

        参数:
            report: 审计报告

        返回:
            str: 格式化文本
        """
        score = report.get("overall_score", 0)
        grade = report.get("grade", "N/A")

        risks = []
        for module, result in report.get("modules", {}).items():
            if isinstance(result, dict):
                for risk in result.get("risks", []):
                    risks.append(Risk(
                        severity=risk.get("severity", "low"),
                        description=risk.get("description", ""),
                        category=risk.get("category", module)
                    ))

        return self.report_formatter.format_text_report(
            title="数据库安全审计报告",
            score=score,
            grade=grade,
            risks=risks,
            modules=report.get("modules")
        )

    def summary(self) -> str:
        """
        获取安全摘要

        返回:
            str: 格式化的安全摘要
        """
        score_data = self.calculate_security_score()

        return self.report_formatter.format_summary(
            score=score_data.get("overall_score", 0),
            grade=score_data.get("grade", "N/A"),
            deductions=score_data.get("deductions", []),
            checked_at=score_data.get("checked_at", "")
        )

    def update_config(self, **kwargs) -> None:
        """
        更新安全配置

        参数:
            **kwargs: 配置项
        """
        for key, value in kwargs.items():
            if hasattr(self.config, key):
                setattr(self.config, key, value)
                logger.info(f"配置更新: {key} = {value}")

    def get_config(self) -> Dict[str, Any]:
        """
        获取当前配置

        返回:
            Dict: 配置信息
        """
        return self.config.to_dict()

    def check_login_security(
        self,
        hours: int = 24
    ) -> Dict[str, Any]:
        """
        检查登录安全状况

        参数:
            hours: 检查最近多少小时

        返回:
            Dict: 登录安全检查结果
        """
        try:
            failed_logins = self.login_monitor.check_failed_logins(hours=hours)
            brute_force = self.login_monitor.detect_brute_force(hours=hours)
            suspicious_ips = self.login_monitor.check_suspicious_ips(hours=hours)

            return create_success_response(
                data={
                    "failed_logins": failed_logins.get('data', {}),
                    "brute_force": brute_force.get('data', {}),
                    "suspicious_ips": suspicious_ips.get('data', {})
                },
                message="登录安全检查完成"
            )
        except Exception as e:
            logger.error(f"登录安全检查失败: {e}")
            return create_error_response(
                f"检查失败: {str(e)}",
                ErrorCode.AUDIT_FAILED
            )

    def analyze_audit_log(
        self,
        hours: int = 24,
        users: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        分析审计日志

        参数:
            hours: 分析最近多少小时
            users: 指定用户列表

        返回:
            Dict: 审计分析结果
        """
        return self.audit_analyzer.analyze_audit_log(hours=hours, users=users)

    def detect_high_risk_operations(
        self,
        hours: int = 24
    ) -> Dict[str, Any]:
        """
        检测高危操作

        参数:
            hours: 检查最近多少小时

        返回:
            Dict: 高危操作检测结果
        """
        return self.audit_analyzer.detect_high_risk_operations(hours=hours)

    def check_password_policy(self) -> Dict[str, Any]:
        """
        检查密码策略

        返回:
            Dict: 密码策略检查结果
        """
        return self.password_checker.check_password_policy()

    def find_weak_passwords(self) -> Dict[str, Any]:
        """
        发现弱密码

        返回:
            Dict: 弱密码用户列表
        """
        return self.password_checker.find_weak_passwords()

    def _audit_sql_injection_in_tables(self) -> Dict[str, Any]:
        """
        审计数据库中存储的SQL语句是否存在注入风险

        功能:
            - 扫描常见的SQL存储表（如查询日志、配置表等）
            - 检测存储的SQL语句是否存在注入漏洞
            - 返回检测结果和风险评估

        返回:
            Dict: SQL注入审计结果
        """
        try:
            # 尝试从常见表中获取SQL语句进行检测
            # 如：慢查询日志表、审计日志表、配置表等
            sql_samples = self._collect_sql_samples()

            if not sql_samples:
                return {
                    "status": "success",
                    "message": "未找到可检测的SQL语句样本（performance_schema和slow_log表可能未启用或为空）",
                    "total_checked": 0,
                    "risks_found": 0,
                    "samples": [],
                    "note": "如需检测SQL注入，请确保：1) performance_schema启用 2) 有SQL执行记录"
                }

            # 检测每个SQL样本
            risks = []
            for sql in sql_samples:
                try:
                    result = self.sql_detector.analyze_sql(sql)
                    findings = result.get('findings', [])
                    if findings:
                        # 计算风险评分
                        risk_score = result.get('risk_score', 0)
                        risks.append({
                            "sql": sql[:100] + "..." if len(sql) > 100 else sql,
                            "risk_score": risk_score,
                            "vulnerability_types": [f.get('injection_type', 'unknown') for f in findings],
                            "findings_count": len(findings)
                        })
                except Exception as e:
                    logger.debug(f"分析SQL样本失败: {e}")
                    continue

            return {
                "status": "success",
                "message": f"检查了{len(sql_samples)}个SQL样本，发现{len(risks)}个风险",
                "total_checked": len(sql_samples),
                "risks_found": len(risks),
                "risks": risks[:10]  # 最多返回10个
            }

        except Exception as e:
            logger.error(f"SQL注入审计失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return {
                "status": "failed",
                "message": f"SQL注入审计失败: {str(e)}",
                "total_checked": 0,
                "risks_found": 0,
                "risks": []
            }

    def _collect_sql_samples(self) -> List[str]:
        """
        从数据库中收集SQL样本

        返回:
            List[str]: SQL语句列表
        """
        samples = []

        try:
            # 根据数据库类型尝试获取SQL样本
            # UnifiedConnector 使用 dialect 属性
            db_type = self.connector.dialect if hasattr(self.connector, 'dialect') else 'mysql'
            # 处理 dialect 如 'mysql+pymysql' 的情况
            if 'mysql' in db_type.lower():
                db_type = 'mysql'
            elif 'oracle' in db_type.lower():
                db_type = 'oracle'
            elif 'postgres' in db_type.lower():
                db_type = 'postgresql'

            if db_type == 'mysql':
                # 尝试从performance_schema获取最近的SQL
                try:
                    result = self.connector.execute("""
                        SELECT SQL_TEXT
                        FROM performance_schema.events_statements_history
                        WHERE SQL_TEXT IS NOT NULL
                        AND SQL_TEXT NOT LIKE 'SHOW%'
                        AND SQL_TEXT NOT LIKE 'SELECT @@%'
                        LIMIT 50
                    """)
                    for row in result.rows:
                        if row[0]:
                            samples.append(row[0])
                except Exception as e:
                    logger.debug(f"无法从performance_schema获取SQL: {e}")

                # 尝试从慢查询日志表获取
                try:
                    result = self.connector.execute("""
                        SELECT sql_text
                        FROM mysql.slow_log
                        WHERE sql_text IS NOT NULL
                        ORDER BY start_time DESC
                        LIMIT 30
                    """)
                    for row in result.rows:
                        if row[0]:
                            samples.append(row[0])
                except Exception as e:
                    logger.debug(f"无法从slow_log获取SQL: {e}")

            elif db_type == 'postgresql':
                # 从pg_stat_statements获取
                try:
                    result = self.connector.execute("""
                        SELECT query
                        FROM pg_stat_statements
                        WHERE query NOT LIKE 'SHOW%'
                        AND query NOT LIKE 'SELECT pg_%'
                        LIMIT 50
                    """)
                    for row in result.rows:
                        if row[0]:
                            samples.append(row[0])
                except Exception as e:
                    logger.debug(f"无法从pg_stat_statements获取SQL: {e}")

            # 去重并返回
            return list(set(samples))

        except Exception as e:
            logger.error(f"收集SQL样本失败: {e}")
            return []

    def close(self) -> None:
        """关闭Skill，释放资源"""
        logger.info("关闭 SecuritySkill...")
        logger.info("SecuritySkill 已关闭")

    # ==================== 高级安全分析 API ====================

    def analyze_user_behavior(
        self,
        user_id: str,
        audit_logs: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        分析用户行为

        参数:
            user_id: 用户ID
            audit_logs: 审计日志列表

        返回:
            Dict: 用户行为分析结果
        """
        try:
            profile = self.advanced_analyzer.analyze_user_behavior(user_id, audit_logs)
            return create_success_response(
                data={
                    "user_id": profile.user_id,
                    "risk_score": profile.risk_score,
                    "behavior_pattern": profile.behavior_pattern.value,
                    "failed_logins": profile.failed_logins,
                    "off_hours_access": profile.off_hours_access,
                    "privilege_escalation_attempts": profile.privilege_escalation_attempts,
                    "query_patterns": profile.query_patterns,
                    "accessed_tables": list(profile.accessed_tables)
                },
                message="用户行为分析完成"
            )
        except Exception as e:
            logger.error(f"用户行为分析失败: {e}")
            return create_error_response(
                f"分析失败: {str(e)}",
                ErrorCode.UNKNOWN_ERROR
            )

    def detect_anomalies(
        self,
        audit_logs: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        检测异常行为

        参数:
            audit_logs: 审计日志列表

        返回:
            Dict: 异常检测结果
        """
        try:
            anomalies = self.advanced_analyzer.detect_anomalies(audit_logs)
            return create_success_response(
                data={
                    "total_anomalies": len(anomalies),
                    "critical": len([a for a in anomalies if a.severity == ThreatLevel.CRITICAL]),
                    "high": len([a for a in anomalies if a.severity == ThreatLevel.HIGH]),
                    "medium": len([a for a in anomalies if a.severity == ThreatLevel.MEDIUM]),
                    "anomalies": [
                        {
                            "event_id": a.event_id,
                            "timestamp": a.timestamp.isoformat(),
                            "user_id": a.user_id,
                            "event_type": a.event_type,
                            "description": a.description,
                            "severity": a.severity.value,
                            "recommendation": a.recommendation
                        }
                        for a in anomalies
                    ]
                },
                message=f"检测到 {len(anomalies)} 个异常事件"
            )
        except Exception as e:
            logger.error(f"异常检测失败: {e}")
            return create_error_response(
                f"检测失败: {str(e)}",
                ErrorCode.UNKNOWN_ERROR
            )

    def analyze_data_flow(
        self,
        sensitive_columns: List[Tuple[str, str]],
        audit_logs: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        分析敏感数据流向

        参数:
            sensitive_columns: 敏感列列表 [(table, column), ...]
            audit_logs: 审计日志

        返回:
            Dict: 数据流向分析结果
        """
        try:
            flows = self.advanced_analyzer.analyze_sensitive_data_flow(
                sensitive_columns, audit_logs
            )
            risks = self.advanced_analyzer.data_flow_analyzer.identify_data_leak_risks(flows)

            return create_success_response(
                data={
                    "total_flows": len(flows),
                    "high_risk_flows": len(risks),
                    "flows": [
                        {
                            "source": f"{f.source_table}.{f.source_column}",
                            "destination": f.destination,
                            "access_count": f.access_count,
                            "last_access": f.last_access.isoformat() if f.last_access else None,
                            "risk_level": f.risk_level.value
                        }
                        for f in flows
                    ],
                    "risks": risks
                },
                message=f"发现 {len(flows)} 条数据流向，{len(risks)} 个高风险"
            )
        except Exception as e:
            logger.error(f"数据流向分析失败: {e}")
            return create_error_response(
                f"分析失败: {str(e)}",
                ErrorCode.UNKNOWN_ERROR
            )

    def check_compliance(
        self,
        standard: str
    ) -> Dict[str, Any]:
        """
        检查合规性

        参数:
            standard: 合规标准（GDPR、PCI-DSS、等保）

        返回:
            Dict: 合规检查结果
        """
        try:
            result = self.advanced_analyzer.check_compliance(standard)
            return create_success_response(
                data={
                    "standard": result.standard,
                    "compliance_score": result.compliance_score,
                    "total_rules": result.total_rules,
                    "passed_rules": result.passed_rules,
                    "failed_rules": result.failed_rules,
                    "violations": result.violations,
                    "report_time": result.report_time.isoformat()
                },
                message=f"{standard} 合规检查完成，得分: {result.compliance_score:.1f}"
            )
        except Exception as e:
            logger.error(f"合规检查失败: {e}")
            return create_error_response(
                f"检查失败: {str(e)}",
                ErrorCode.UNKNOWN_ERROR
            )

    def generate_advanced_security_report(
        self,
        audit_logs: List[Dict[str, Any]],
        sensitive_columns: List[Tuple[str, str]],
        standards: List[str]
    ) -> Dict[str, Any]:
        """
        生成高级安全报告

        参数:
            audit_logs: 审计日志
            sensitive_columns: 敏感列
            standards: 合规标准列表

        返回:
            Dict: 综合安全报告
        """
        try:
            report = self.advanced_analyzer.generate_comprehensive_report(
                audit_logs, sensitive_columns, standards
            )
            return create_success_response(
                data=report,
                message="高级安全报告生成完成"
            )
        except Exception as e:
            logger.error(f"生成安全报告失败: {e}")
            return create_error_response(
                f"报告生成失败: {str(e)}",
                ErrorCode.UNKNOWN_ERROR
            )

    def get_supported_compliance_standards(self) -> List[str]:
        """
        获取支持的合规标准

        返回:
            List[str]: 合规标准列表
        """
        return self.advanced_analyzer.compliance_checker.get_supported_standards()


# 版本兼容说明：
# 本模块已统一为 SecuritySkill，不再区分V2/V3
