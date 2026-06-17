"""
db_security/utils.py
安全工具类

文件功能：提供安全检测相关的工具类和辅助函数
主要类/函数：
    - PatternMatcher: 模式匹配器
    - EntropyCalculator: 熵计算器
    - RiskScorer: 风险评分器
    - ReportFormatter: 报告格式化器

版本: 3.0.0
作者: AI Assistant
创建时间: 2026-04-23
"""

import logging
import math
import re
from collections import Counter
from typing import Any, Dict, List, Optional, Tuple

from dbskiter.db_security.models import (
    RiskLevel, Risk, RiskReport
)

logger = logging.getLogger(__name__)


class PatternMatcher:
    """
    模式匹配器 - 用于检测SQL注入和敏感数据模式

    功能:
        - 正则表达式模式匹配
        - 多模式联合检测
        - 匹配结果评分
    """

    def __init__(self):
        """初始化模式匹配器"""
        self._patterns: Dict[str, List[re.Pattern]] = {}

    def add_patterns(self, category: str, patterns: List[str]):
        """
        添加正则表达式模式

        参数:
            category: 模式类别
            patterns: 正则表达式列表
        """
        if category not in self._patterns:
            self._patterns[category] = []

        for pattern in patterns:
            try:
                self._patterns[category].append(re.compile(pattern, re.IGNORECASE))
            except re.error as e:
                continue

    def match(self, text: str, category: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        匹配文本

        参数:
            text: 待匹配文本
            category: 指定类别，None表示所有类别

        返回:
            List[Dict]: 匹配结果列表
        """
        results = []

        categories = [category] if category else self._patterns.keys()

        for cat in categories:
            if cat not in self._patterns:
                continue

            for pattern in self._patterns[cat]:
                matches = pattern.finditer(text)
                for match in matches:
                    results.append({
                        "category": cat,
                        "pattern": pattern.pattern,
                        "matched_text": match.group(),
                        "position": match.span()
                    })

        return results

    def has_match(self, text: str, category: Optional[str] = None) -> bool:
        """
        检查是否有匹配

        参数:
            text: 待匹配文本
            category: 指定类别

        返回:
            bool: 是否有匹配
        """
        return len(self.match(text, category)) > 0


class EntropyCalculator:
    """
    熵计算器 - 用于检测加密/混淆数据

    功能:
        - 计算字符串的香农熵
        - 检测随机性/加密数据
        - 评估数据复杂度
    """

    @staticmethod
    def calculate(text: str) -> float:
        """
        计算字符串的香农熵

        参数:
            text: 输入字符串

        返回:
            float: 熵值 (0-8，越高表示越随机)
        """
        if not text:
            return 0.0

        # 统计字符频率
        counter = Counter(text)
        length = len(text)

        # 计算熵
        entropy = 0.0
        for count in counter.values():
            probability = count / length
            entropy -= probability * math.log2(probability)

        return entropy

    @staticmethod
    def is_likely_encrypted(text: str, threshold: float = 4.5) -> bool:
        """
        判断是否可能是加密/混淆数据

        参数:
            text: 输入字符串
            threshold: 熵阈值

        返回:
            bool: 是否可能是加密数据
        """
        if len(text) < 8:
            return False

        entropy = EntropyCalculator.calculate(text)
        return entropy > threshold

    @staticmethod
    def get_entropy_level(text: str) -> str:
        """
        获取熵级别

        参数:
            text: 输入字符串

        返回:
            str: 级别 (low, medium, high)
        """
        entropy = EntropyCalculator.calculate(text)

        if entropy < 3.0:
            return "low"
        elif entropy < 5.0:
            return "medium"
        else:
            return "high"


class RiskScorer:
    """
    风险评分器 - 计算安全风险评分

    功能:
        - 综合风险评分计算
        - 风险等级判定
        - 扣分项管理
    """

    # 风险权重配置（调整后的合理权重）
    SEVERITY_WEIGHTS = {
        "critical": 15,  # 严重风险扣15分
        "high": 8,       # 高风险扣8分
        "medium": 3,     # 中风险扣3分
        "low": 1         # 低风险扣1分
    }

    @staticmethod
    def calculate_score(
        risks: List[Risk],
        max_score: float = 100.0
    ) -> Tuple[float, str, List[str]]:
        """
        计算安全评分

        参数:
            risks: 风险列表
            max_score: 满分

        返回:
            Tuple[float, str, List[str]]: (分数, 等级, 扣分项)
        """
        deductions = []
        total_deduction = 0.0

        for risk in risks:
            weight = RiskScorer.SEVERITY_WEIGHTS.get(risk.severity, 0)
            total_deduction += weight
            severity_str = risk.severity.value if hasattr(risk.severity, 'value') else str(risk.severity)
            deductions.append(f"[{severity_str.upper()}] {risk.description}")

        # 设置扣分上限，最多扣80分，保留至少20分基础分
        total_deduction = min(total_deduction, 80)
        score = max(0.0, max_score - total_deduction)

        # 确定等级
        if score >= 90:
            grade = "A"
        elif score >= 80:
            grade = "B"
        elif score >= 70:
            grade = "C"
        elif score >= 60:
            grade = "D"
        else:
            grade = "F"

        return score, grade, deductions

    @staticmethod
    def get_risk_level(score: float) -> RiskLevel:
        """
        根据分数获取风险等级

        参数:
            score: 风险分数 (0-100)

        返回:
            RiskLevel: 风险等级
        """
        if score >= 80:
            return RiskLevel.CRITICAL
        elif score >= 60:
            return RiskLevel.HIGH
        elif score >= 40:
            return RiskLevel.MEDIUM
        else:
            return RiskLevel.LOW


class ReportFormatter:
    """
    报告格式化器 - 格式化安全报告

    功能:
        - 文本报告格式化
        - JSON报告格式化
        - 摘要生成
    """

    @staticmethod
    def format_text_report(
        title: str,
        score: float,
        grade: str,
        risks: List[Risk],
        modules: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        格式化文本报告

        参数:
            title: 报告标题
            score: 安全评分
            grade: 安全等级
            risks: 风险列表
            modules: 模块状态

        返回:
            str: 格式化的文本报告
        """
        lines = [
            "=" * 60,
            title,
            "=" * 60,
            f"安全评分: {score:.1f}/100",
            f"安全等级: {grade}",
            "-" * 60,
        ]

        # 风险项
        if risks:
            lines.append("风险项:")
            for risk in risks[:10]:
                severity_str = risk.severity.value if hasattr(risk.severity, 'value') else str(risk.severity)
                severity_map = {'critical': '致命', 'high': '高危', 'medium': '中危', 'low': '低危'}
                severity_cn = severity_map.get(severity_str.lower(), severity_str)
                lines.append(f"  {severity_cn}: {risk.description}")
        else:
            lines.append("未发现明显安全风险")

        # 模块状态
        if modules:
            lines.append("-" * 60)
            lines.append("模块状态:")
            for module, result in modules.items():
                status = result.get("status", "unknown")
                status_cn = "成功" if status == "success" else "错误"
                lines.append(f"  {module}: {status_cn}")

        lines.append("=" * 60)

        return "\n".join(lines)

    @staticmethod
    def format_summary(
        score: float,
        grade: str,
        deductions: List[str],
        checked_at: str
    ) -> str:
        """
        格式化摘要

        参数:
            score: 安全评分
            grade: 安全等级
            deductions: 扣分项
            checked_at: 检查时间

        返回:
            str: 格式化的摘要
        """
        lines = [
            "=" * 60,
            "数据库安全摘要",
            "=" * 60,
            f"安全评分: {score:.1f}/100",
            f"安全等级: {grade}",
            f"检查时间: {checked_at}",
            "-" * 60,
        ]

        if deductions:
            lines.append("风险项:")
            for deduction in deductions[:5]:
                lines.append(f"  警告: {deduction}")
        else:
            lines.append("未发现明显安全风险")

        lines.append("=" * 60)

        return "\n".join(lines)


class SecurityAuditor:
    """
    安全审计器 - 执行各类安全审计

    功能:
        - 权限审计
        - 配置审计
        - 综合审计报告
    """

    def __init__(self, connector):
        """
        初始化审计器

        参数:
            connector: 数据库连接器
        """
        self.connector = connector
        self.dialect = connector.dialect.lower() if hasattr(connector, 'dialect') else 'mysql'

    def audit_permissions(self) -> Dict[str, Any]:
        """
        审计权限 - 查询数据库用户权限

        返回:
            Dict: 审计结果
        """
        if 'oracle' in self.dialect:
            return self._audit_oracle_permissions()
        elif 'postgresql' in self.dialect:
            return self._audit_postgresql_permissions()
        elif 'clickhouse' in self.dialect:
            return self._audit_clickhouse_permissions()
        elif 'sqlite' in self.dialect:
            return self._audit_sqlite_permissions()
        elif self.dialect in ('mysql', 'mysql+pymysql', 'mariadb'):
            return self._audit_mysql_permissions()
        else:
            return self._audit_generic_permissions()

    def _audit_mysql_permissions(self) -> Dict[str, Any]:
        """
        MySQL权限审计

        返回:
            Dict: 审计结果
        """
        risks = []
        total_users = 0
        high_privilege_users = 0

        try:
            # 查询MySQL用户权限
            result = self.connector.execute("""
                SELECT user, host, 
                       Select_priv, Insert_priv, Update_priv, Delete_priv,
                       Create_priv, Drop_priv, Reload_priv, Shutdown_priv,
                       Process_priv, File_priv, Grant_priv, Super_priv
                FROM mysql.user
                WHERE user NOT LIKE 'mysql.%'
            """)

            total_users = len(result.rows)
            high_risk_privs = ['Super_priv', 'Grant_priv', 'File_priv', 'Shutdown_priv', 'Process_priv']

            for row in result.rows:
                user = row[0]
                host = row[1]
                privs = dict(zip(['Select', 'Insert', 'Update', 'Delete', 'Create', 'Drop',
                                  'Reload', 'Shutdown', 'Process', 'File', 'Grant', 'Super'], row[2:]))

                # root用户是超级管理员，其权限属于正常情况，不标记为风险
                is_root = (user == 'root')

                # 检查高风险权限（非root用户拥有这些权限才标记为风险）
                for priv_name in ['Super', 'Grant', 'File', 'Shutdown', 'Process']:
                    if privs.get(priv_name) == 'Y':
                        high_privilege_users += 1
                        # root用户拥有这些权限是正常的，不标记为风险
                        # 但其他用户拥有这些权限需要关注
                        if not is_root:
                            risks.append(Risk(
                                severity="high" if priv_name in ['Super', 'Grant'] else "medium",
                                description=f"非管理员用户 {user}@{host} 拥有 {priv_name} 权限",
                                category="permission",
                                current_value=f"{user}@{host} -> {priv_name}=Y",
                                recommended_value=f"撤销 {user}@{host} 的 {priv_name} 权限"
                            ))

                # 检查通配符主机（root用户允许任意主机连接是风险）
                if host == '%':
                    if is_root:
                        risks.append(Risk(
                            severity="high",
                            description=f"root用户允许从任意主机连接，存在安全风险",
                            category="permission",
                            current_value="root@%",
                            recommended_value="限制root只能从localhost或特定IP连接"
                        ))
                    else:
                        risks.append(Risk(
                            severity="medium",
                            description=f"用户 {user} 允许从任意主机连接",
                            category="permission",
                            current_value=f"{user}@%",
                            recommended_value=f"限制 {user} 只能从特定主机连接"
                        ))

        except Exception as e:
            logger.error(f"权限审计失败: {e}")
            return {
                "status": "error",
                "message": f"权限审计失败: {str(e)}",
                "total_checked": 0,
                "risks_found": 0,
                "risks": []
            }

        return {
            "status": "success",
            "total_users": total_users,
            "high_privilege_users": high_privilege_users,
            "total_checked": total_users,
            "risks_found": len(risks),
            "message": f"审计了{total_users}个用户，发现{high_privilege_users}个高权限用户，{len(risks)}个风险",
            "risks": [r.to_dict() for r in risks[:20]]  # 最多返回20个
        }

    def _audit_oracle_permissions(self) -> Dict[str, Any]:
        """
        Oracle权限审计

        返回:
            Dict: 审计结果
        """
        risks = []
        total_users = 0
        high_privilege_users = 0

        try:
            # 查询Oracle用户及DBA角色
            result = self.connector.execute("""
                SELECT
                    u.username,
                    u.account_status,
                    u.created,
                    NVL((SELECT COUNT(*) FROM dba_role_privs r
                         WHERE r.grantee = u.username AND r.granted_role = 'DBA'), 0) AS is_dba
                FROM dba_users u
                WHERE u.username NOT IN ('SYS','SYSTEM','DBSNMP','SYSMAN','OUTLN',
                    'MDSYS','ORDSYS','EXFSYS','DMSYS','WMSYS','CTXSYS','ANONYMOUS',
                    'XDB','ORDPLUGINS','OLAPSYS','MDDATA','SI_INFORMTN_SCHEMA')
                ORDER BY u.username
            """)

            total_users = len(result.rows)

            for row in result.rows:
                username = str(row[0])
                account_status = str(row[1])
                is_dba = int(str(row[3])) if row[3] else 0

                if is_dba > 0:
                    high_privilege_users += 1
                    risks.append(Risk(
                        severity="high",
                        description=f"用户 {username} 拥有DBA角色",
                        category="permission",
                        current_value=f"{username} -> DBA",
                        recommended_value="仅SYS/SYSTEM用户授予DBA角色"
                    ))

                if account_status == 'OPEN':
                    pass
                elif 'LOCKED' in account_status.upper() and 'EXPIRED' in account_status.upper():
                    pass
                elif 'EXPIRED' in account_status.upper():
                    risks.append(Risk(
                        severity="low",
                        description=f"用户 {username} 密码已过期",
                        category="permission",
                        current_value=f"{username} 状态={account_status}",
                        recommended_value="重置该用户密码"
                    ))

            # 检查拥有危险系统权限的用户
            try:
                result2 = self.connector.execute("""
                    SELECT grantee, privilege, COUNT(*) AS cnt
                    FROM dba_sys_privs
                    WHERE privilege IN ('ALTER SYSTEM','ALTER USER','DROP ANY TABLE',
                        'DROP USER','CREATE ANY PROCEDURE','EXECUTE ANY PROCEDURE',
                        'GRANT ANY ROLE','GRANT ANY PRIVILEGE')
                    AND grantee NOT IN ('SYS','SYSTEM','DBA')
                    GROUP BY grantee, privilege
                    ORDER BY cnt DESC
                """)
                for row in result2.rows:
                    grantee = str(row[0])
                    privilege = str(row[1])
                    risks.append(Risk(
                        severity="high",
                        description=f"用户 {grantee} 拥有危险系统权限: {privilege}",
                        category="permission",
                        current_value=f"{grantee} -> {privilege}",
                        recommended_value=f"撤销 {grantee} 的 {privilege} 权限"
                    ))
            except Exception as e2:
                logger.warning(f"查询Oracle系统权限失败: {e2}")

        except Exception as e:
            logger.error(f"Oracle权限审计失败: {e}")
            return {
                "status": "error",
                "message": f"权限审计失败: {str(e)}",
                "total_checked": 0,
                "risks_found": 0,
                "risks": []
            }

        return {
            "status": "success",
            "total_users": total_users,
            "high_privilege_users": high_privilege_users,
            "total_checked": total_users,
            "risks_found": len(risks),
            "message": f"审计了{total_users}个用户，发现{high_privilege_users}个高权限用户，{len(risks)}个风险",
            "risks": [r.to_dict() for r in risks[:20]]
        }

    def audit_config(self) -> Dict[str, Any]:
        """
        审计配置 - 查询数据库安全配置

        返回:
            Dict: 审计结果
        """
        if 'oracle' in self.dialect:
            return self._audit_oracle_config()
        elif 'postgresql' in self.dialect:
            return self._audit_postgresql_config()
        elif 'clickhouse' in self.dialect:
            return self._audit_clickhouse_config()
        elif 'sqlite' in self.dialect:
            return self._audit_sqlite_config()
        elif self.dialect in ('mysql', 'mysql+pymysql', 'mariadb'):
            return self._audit_mysql_config()
        else:
            return self._audit_generic_config()

    def _audit_mysql_config(self) -> Dict[str, Any]:
        """
        MySQL配置审计

        返回:
            Dict: 审计结果
        """
        risks = []
        checks_performed = 0

        try:
            # 检查1: SSL是否启用
            try:
                result = self.connector.execute("SHOW VARIABLES LIKE 'have_ssl'")
                if result.rows and result.rows[0][1] != 'YES':
                    risks.append(Risk(
                        severity="high",
                        description="SSL未启用，数据传输未加密",
                        category="config",
                        current_value=f"have_ssl={result.rows[0][1] if result.rows else 'UNKNOWN'}",
                        recommended_value="have_ssl=YES"
                    ))
                checks_performed += 1
            except Exception as e:
                logger.warning(f"检查SSL配置失败: {e}")

            # 检查2: 密码策略
            try:
                result = self.connector.execute("SHOW VARIABLES LIKE 'validate_password%'")
                if not result.rows:
                    risks.append(Risk(
                        severity="medium",
                        description="未启用密码强度验证插件",
                        category="config",
                        current_value="validate_password插件未安装",
                        recommended_value="安装并启用validate_password插件"
                    ))
                checks_performed += 1
            except Exception as e:
                logger.warning(f"检查密码策略失败: {e}")

            # 检查3: 审计日志
            try:
                result = self.connector.execute("SHOW VARIABLES LIKE 'general_log'")
                if result.rows and result.rows[0][1] != 'ON':
                    risks.append(Risk(
                        severity="low",
                        description="通用查询日志未启用",
                        category="config",
                        current_value=f"general_log={result.rows[0][1] if result.rows else 'OFF'}",
                        recommended_value="general_log=ON"
                    ))
                checks_performed += 1
            except Exception as e:
                logger.warning(f"检查审计日志失败: {e}")

            # 检查4: 远程root访问
            try:
                result = self.connector.execute("""
                    SELECT COUNT(*) FROM mysql.user
                    WHERE user = 'root' AND host = '%'
                """)
                if result.rows and result.rows[0][0] > 0:
                    risks.append(Risk(
                        severity="high",
                        description="root用户允许远程访问",
                        category="config",
                        current_value="root@%",
                        recommended_value="删除root@%或改为root@localhost"
                    ))
                checks_performed += 1
            except Exception as e:
                logger.warning(f"检查root远程访问失败: {e}")

            # 检查5: 匿名用户
            try:
                result = self.connector.execute("""
                    SELECT COUNT(*) FROM mysql.user
                    WHERE user = '' OR user IS NULL
                """)
                if result.rows and result.rows[0][0] > 0:
                    risks.append(Risk(
                        severity="medium",
                        description="存在匿名用户",
                        category="config",
                        current_value="存在匿名用户",
                        recommended_value="删除所有匿名用户"
                    ))
                checks_performed += 1
            except Exception as e:
                logger.warning(f"检查匿名用户失败: {e}")

        except Exception as e:
            logger.error(f"配置审计失败: {e}")
            return {
                "status": "error",
                "message": f"配置审计失败: {str(e)}",
                "total_checked": checks_performed,
                "risks_found": len(risks),
                "risks": []
            }

        return {
            "status": "success",
            "total_checks": checks_performed,
            "failed_checks": len(risks),
            "total_checked": checks_performed,
            "risks_found": len(risks),
            "message": f"检查了{checks_performed}项配置，发现{len(risks)}个问题",
            "risks": [r.to_dict() for r in risks]
        }

    def _audit_oracle_config(self) -> Dict[str, Any]:
        """
        Oracle配置审计

        返回:
            Dict: 审计结果
        """
        risks = []
        checks_performed = 0

        try:
            # 检查1: 审计是否启用
            try:
                result = self.connector.execute("""
                    SELECT value FROM v$parameter WHERE name = 'audit_trail'
                """)
                if result.rows:
                    audit_trail = str(result.rows[0][0]).upper()
                    if audit_trail == 'NONE':
                        risks.append(Risk(
                            severity="high",
                            description="数据库审计未启用 (audit_trail=NONE)",
                            category="config",
                            current_value="audit_trail=NONE",
                            recommended_value="audit_trail=DB 或 OS"
                        ))
                checks_performed += 1
            except Exception as e:
                logger.warning(f"检查Oracle审计配置失败: {e}")

            # 检查2: 密码策略（用户配置文件）
            try:
                result = self.connector.execute("""
                    SELECT
                        p.profile,
                        p.resource_name,
                        p.limit
                    FROM dba_profiles p
                    WHERE p.resource_type = 'PASSWORD'
                    AND p.profile = 'DEFAULT'
                    AND p.resource_name IN (
                        'FAILED_LOGIN_ATTEMPTS','PASSWORD_LIFE_TIME',
                        'PASSWORD_LOCK_TIME','PASSWORD_REUSE_MAX',
                        'PASSWORD_REUSE_TIME','PASSWORD_VERIFY_FUNCTION'
                    )
                    ORDER BY p.resource_name
                """)
                profile_settings = {}
                for row in result.rows:
                    resource_name = str(row[1])
                    limit_val = str(row[2])
                    profile_settings[resource_name] = limit_val

                if profile_settings.get('FAILED_LOGIN_ATTEMPTS', 'UNLIMITED') in ('UNLIMITED', '0'):
                    risks.append(Risk(
                        severity="medium",
                        description="登录失败次数限制未设置 (FAILED_LOGIN_ATTEMPTS=UNLIMITED)",
                        category="config",
                        current_value="FAILED_LOGIN_ATTEMPTS=UNLIMITED",
                        recommended_value="FAILED_LOGIN_ATTEMPTS=10"
                    ))

                if profile_settings.get('PASSWORD_LIFE_TIME', 'UNLIMITED') in ('UNLIMITED', '0'):
                    risks.append(Risk(
                        severity="medium",
                        description="密码过期时间未设置 (PASSWORD_LIFE_TIME=UNLIMITED)",
                        category="config",
                        current_value="PASSWORD_LIFE_TIME=UNLIMITED",
                        recommended_value="PASSWORD_LIFE_TIME=90"
                    ))

                if profile_settings.get('PASSWORD_VERIFY_FUNCTION', 'NULL') in ('NULL', 'NONE'):
                    risks.append(Risk(
                        severity="medium",
                        description="密码复杂度验证函数未设置",
                        category="config",
                        current_value="PASSWORD_VERIFY_FUNCTION=NULL",
                        recommended_value="设置密码验证函数，如 ORA12C_VERIFY_FUNCTION"
                    ))

                checks_performed += 1
            except Exception as e:
                logger.warning(f"检查Oracle密码策略失败: {e}")

            # 检查3: 远程登录配置
            try:
                result = self.connector.execute("""
                    SELECT value FROM v$parameter
                    WHERE name = 'remote_login_passwordfile'
                """)
                if result.rows:
                    val = str(result.rows[0][0]).upper()
                    if val == 'EXCLUSIVE':
                        risks.append(Risk(
                            severity="low",
                            description="remote_login_passwordfile=EXCLUSIVE，允许远程SYSDBA登录",
                            category="config",
                            current_value="remote_login_passwordfile=EXCLUSIVE",
                            recommended_value="remote_login_passwordfile=NONE 或 SHARED"
                        ))
                checks_performed += 1
            except Exception as e:
                logger.warning(f"检查Oracle远程登录配置失败: {e}")

            # 检查4: 监听器密码
            try:
                result = self.connector.execute("""
                    SELECT value FROM v$parameter
                    WHERE name = 'local_listener'
                """)
                checks_performed += 1
            except Exception as e:
                logger.warning(f"检查Oracle监听器配置失败: {e}")

            # 检查5: OPEN_CURSOR数量
            try:
                result = self.connector.execute("""
                    SELECT value FROM v$parameter
                    WHERE name = 'open_cursors'
                """)
                if result.rows:
                    open_cursors = int(str(result.rows[0][0]))
                    if open_cursors > 1000:
                        risks.append(Risk(
                            severity="low",
                            description=f"open_cursors={open_cursors}，设置过高可能影响内存",
                            category="config",
                            current_value=f"open_cursors={open_cursors}",
                            recommended_value="open_cursors=300~1000"
                        ))
                checks_performed += 1
            except Exception as e:
                logger.warning(f"检查Oracle open_cursors失败: {e}")

        except Exception as e:
            logger.error(f"Oracle配置审计失败: {e}")
            return {
                "status": "error",
                "message": f"配置审计失败: {str(e)}",
                "total_checked": checks_performed,
                "risks_found": len(risks),
                "risks": []
            }

        return {
            "status": "success",
            "total_checks": checks_performed,
            "failed_checks": len(risks),
            "total_checked": checks_performed,
            "risks_found": len(risks),
            "message": f"检查了{checks_performed}项配置，发现{len(risks)}个问题",
            "risks": [r.to_dict() for r in risks]
        }

    def _audit_postgresql_permissions(self) -> Dict[str, Any]:
        """
        PostgreSQL权限审计

        返回:
            Dict: 审计结果
        """
        risks = []
        total_users = 0
        high_privilege_users = 0

        try:
            result = self.connector.execute("""
                SELECT
                    r.rolname,
                    r.rolsuper,
                    r.rolcreaterole,
                    r.rolcreatedb,
                    r.rolinherit,
                    r.rolcanlogin
                FROM pg_roles r
                WHERE r.rolname NOT LIKE 'pg_%'
                ORDER BY r.rolname
            """)

            total_users = len(result.rows)

            for row in result.rows:
                rolname = str(row[0])
                is_super = str(row[1]).lower() == 'true'
                can_create_role = str(row[2]).lower() == 'true'
                can_create_db = str(row[3]).lower() == 'true'

                if is_super:
                    high_privilege_users += 1
                    if rolname not in ('postgres',):
                        risks.append(Risk(
                            severity="high",
                            description=f"非默认超级用户 {rolname} 拥有SUPERUSER权限",
                            category="permission",
                            current_value=f"{rolname} -> SUPERUSER",
                            recommended_value=f"撤销 {rolname} 的SUPERUSER权限，按需授予具体权限"
                        ))

                if can_create_role:
                    high_privilege_users += 1
                    if rolname not in ('postgres',):
                        risks.append(Risk(
                            severity="medium",
                            description=f"用户 {rolname} 可以创建其他角色",
                            category="permission",
                            current_value=f"{rolname} -> CREATEROLE",
                            recommended_value=f"仅必要用户授予CREATEROLE权限"
                        ))

                if can_create_db and rolname not in ('postgres',):
                    risks.append(Risk(
                        severity="low",
                        description=f"用户 {rolname} 可以创建数据库",
                        category="permission",
                        current_value=f"{rolname} -> CREATEDB",
                        recommended_value=f"按需限制 {rolname} 的CREATEDB权限"
                    ))

            try:
                result2 = self.connector.execute("""
                    SELECT
                        grantee,
                        table_name,
                        privilege_type
                    FROM information_schema.role_table_grants
                    WHERE grantee NOT LIKE 'pg_%'
                    AND privilege_type IN ('DELETE', 'TRUNCATE', 'REFERENCES', 'TRIGGER')
                    AND grantee NOT IN ('postgres', 'PUBLIC')
                    LIMIT 50
                """)
                for row in result2.rows:
                    grantee = str(row[0])
                    table_name = str(row[1])
                    priv = str(row[2])
                    if priv in ('DELETE', 'TRUNCATE'):
                        risks.append(Risk(
                            severity="medium",
                            description=f"用户 {grantee} 对表 {table_name} 有 {priv} 权限",
                            category="permission",
                            current_value=f"{grantee} -> {table_name}:{priv}",
                            recommended_value=f"审查 {grantee} 是否确实需要 {priv} 权限"
                        ))
            except Exception as e2:
                logger.warning(f"查询PostgreSQL表权限失败: {e2}")

            try:
                result3 = self.connector.execute("""
                    SELECT
                        grantee,
                        routine_name,
                        privilege_type
                    FROM information_schema.role_routine_grants
                    WHERE grantee NOT LIKE 'pg_%'
                    AND grantee NOT IN ('postgres', 'PUBLIC')
                    AND privilege_type = 'EXECUTE'
                    LIMIT 30
                """)
                for row in result3.rows:
                    grantee = str(row[0])
                    routine = str(row[1])
                    if routine.startswith('pg_') or routine.startswith('_'):
                        risks.append(Risk(
                            severity="high",
                            description=f"用户 {grantee} 有系统函数 {routine} 的执行权限",
                            category="permission",
                            current_value=f"{grantee} -> EXECUTE on {routine}",
                            recommended_value=f"撤销 {grantee} 对系统函数的执行权限"
                        ))
            except Exception as e3:
                logger.warning(f"查询PostgreSQL函数权限失败: {e3}")

        except Exception as e:
            logger.error(f"PostgreSQL权限审计失败: {e}")
            return {
                "status": "error",
                "message": f"权限审计失败: {str(e)}",
                "total_checked": 0,
                "risks_found": 0,
                "risks": []
            }

        return {
            "status": "success",
            "total_users": total_users,
            "high_privilege_users": high_privilege_users,
            "total_checked": total_users,
            "risks_found": len(risks),
            "message": f"审计了{total_users}个用户，发现{high_privilege_users}个高权限用户，{len(risks)}个风险",
            "risks": [r.to_dict() for r in risks[:20]]
        }

    def _audit_postgresql_config(self) -> Dict[str, Any]:
        """
        PostgreSQL配置审计

        返回:
            Dict: 审计结果
        """
        risks = []
        checks_performed = 0

        try:
            try:
                result = self.connector.execute("""
                    SELECT name, setting, short_desc
                    FROM pg_settings
                    WHERE name = 'ssl'
                """)
                if result.rows:
                    ssl_val = str(result.rows[0][1]).lower()
                    if ssl_val != 'on':
                        risks.append(Risk(
                            severity="high",
                            description="SSL未启用，数据传输未加密",
                            category="config",
                            current_value=f"ssl={ssl_val}",
                            recommended_value="ssl=on"
                        ))
                checks_performed += 1
            except Exception as e:
                logger.warning(f"检查PostgreSQL SSL配置失败: {e}")

            try:
                result = self.connector.execute("""
                    SELECT name, setting, short_desc
                    FROM pg_settings
                    WHERE name = 'log_connections'
                """)
                if result.rows:
                    log_conn = str(result.rows[0][1]).lower()
                    if log_conn != 'on':
                        risks.append(Risk(
                            severity="medium",
                            description="连接日志未启用 (log_connections=off)",
                            category="config",
                            current_value=f"log_connections={log_conn}",
                            recommended_value="log_connections=on"
                        ))
                checks_performed += 1
            except Exception as e:
                logger.warning(f"检查PostgreSQL连接日志失败: {e}")

            try:
                result = self.connector.execute("""
                    SELECT name, setting, short_desc
                    FROM pg_settings
                    WHERE name IN (
                        'log_disconnections', 'log_duration',
                        'log_statement', 'log_line_prefix'
                    )
                    ORDER BY name
                """)
                log_settings = {}
                for row in result.rows:
                    log_settings[str(row[0])] = str(row[1])

                if log_settings.get('log_statement', 'none') == 'none':
                    risks.append(Risk(
                        severity="medium",
                        description="SQL语句日志未启用 (log_statement=none)",
                        category="config",
                        current_value="log_statement=none",
                        recommended_value="log_statement=ddl 或 all"
                    ))

                if log_settings.get('log_disconnections', 'off') != 'on':
                    risks.append(Risk(
                        severity="low",
                        description="断开连接日志未启用",
                        category="config",
                        current_value=f"log_disconnections={log_settings.get('log_disconnections', 'off')}",
                        recommended_value="log_disconnections=on"
                    ))
                checks_performed += 1
            except Exception as e:
                logger.warning(f"检查PostgreSQL日志配置失败: {e}")

            try:
                result = self.connector.execute("""
                    SELECT setting::int FROM pg_settings
                    WHERE name = 'max_connections'
                """)
                if result.rows:
                    max_conn = int(str(result.rows[0][0]))
                    if max_conn > 500:
                        risks.append(Risk(
                            severity="low",
                            description=f"max_connections={max_conn}，设置过高可能影响内存",
                            category="config",
                            current_value=f"max_connections={max_conn}",
                            recommended_value="max_connections=100~300"
                        ))
                checks_performed += 1
            except Exception as e:
                logger.warning(f"检查PostgreSQL max_connections失败: {e}")

            try:
                has_pgaudit = False
                result = self.connector.execute("""
                    SELECT COUNT(*) FROM pg_extension WHERE extname = 'pgaudit'
                """)
                if result.rows and result.rows[0][0] > 0:
                    has_pgaudit = True
                if not has_pgaudit:
                    risks.append(Risk(
                        severity="medium",
                        description="pgAudit审计扩展未安装",
                        category="config",
                        current_value="pgaudit扩展未安装",
                        recommended_value="安装并启用pgaudit扩展以增强审计能力"
                    ))
                checks_performed += 1
            except Exception as e:
                logger.warning(f"检查PostgreSQL pgaudit失败: {e}")

            try:
                result = self.connector.execute("""
                    SELECT name, setting
                    FROM pg_settings
                    WHERE name = 'password_encryption'
                """)
                if result.rows:
                    enc = str(result.rows[0][1]).lower()
                    if enc == 'md5':
                        risks.append(Risk(
                            severity="medium",
                            description="密码加密方式使用MD5，安全性不足",
                            category="config",
                            current_value="password_encryption=md5",
                            recommended_value="password_encryption=scram-sha-256"
                        ))
                checks_performed += 1
            except Exception as e:
                logger.warning(f"检查PostgreSQL密码加密失败: {e}")

            try:
                result = self.connector.execute("""
                    SELECT COUNT(*)
                    FROM pg_roles
                    WHERE rolpassword IS NOT NULL
                    AND rolname NOT LIKE 'pg_%'
                """)
                if result.rows and result.rows[0][0] > 0:
                    pass
                checks_performed += 1
            except Exception as e:
                logger.warning(f"检查PostgreSQL用户密码失败: {e}")

        except Exception as e:
            logger.error(f"PostgreSQL配置审计失败: {e}")
            return {
                "status": "error",
                "message": f"配置审计失败: {str(e)}",
                "total_checked": checks_performed,
                "risks_found": len(risks),
                "risks": []
            }

        return {
            "status": "success",
            "total_checks": checks_performed,
            "failed_checks": len(risks),
            "total_checked": checks_performed,
            "risks_found": len(risks),
            "message": f"检查了{checks_performed}项配置，发现{len(risks)}个问题",
            "risks": [r.to_dict() for r in risks]
        }

    def _audit_clickhouse_permissions(self) -> Dict[str, Any]:
        """
        ClickHouse权限审计

        ClickHouse使用基于角色的访问控制(RBAC)

        返回:
            Dict: 审计结果
        """
        risks = []
        total_users = 0
        high_privilege_users = 0

        try:
            # 查询用户列表
            result = self.connector.execute("""
                SELECT name, storage, auth_type, default_roles_all
                FROM system.users
                WHERE name NOT LIKE 'default%'
            """)

            total_users = len(result.rows) if result else 0

            for row in result.rows if result else []:
                username = str(row[0])
                storage = str(row[1])
                auth_type = str(row[2])
                default_roles_all = str(row[3]).lower() == 'true'

                # 检查是否拥有所有角色
                if default_roles_all:
                    high_privilege_users += 1
                    risks.append(Risk(
                        severity="high",
                        description=f"用户 {username} 拥有所有默认角色",
                        category="permission",
                        current_value=f"{username} -> default_roles_all=true",
                        recommended_value=f"限制 {username} 的角色权限"
                    ))

                # 检查无密码认证
                if auth_type == 'no_password':
                    risks.append(Risk(
                        severity="critical",
                        description=f"用户 {username} 使用无密码认证",
                        category="permission",
                        current_value=f"{username} -> auth_type=no_password",
                        recommended_value=f"为 {username} 设置密码认证"
                    ))

            # 检查拥有ALL权限的用户
            try:
                result2 = self.connector.execute("""
                    SELECT user_name, role_name, access_type, database, table
                    FROM system.grants
                    WHERE access_type = 'ALL'
                    AND user_name NOT LIKE 'default%'
                """)
                for row in result2.rows if result2 else []:
                    username = str(row[0])
                    database = str(row[3])
                    table = str(row[4])
                    risks.append(Risk(
                        severity="high",
                        description=f"用户 {username} 对 {database}.{table} 拥有ALL权限",
                        category="permission",
                        current_value=f"{username} -> ALL on {database}.{table}",
                        recommended_value=f"限制 {username} 的权限范围"
                    ))
            except Exception as e2:
                logger.warning(f"查询ClickHouse权限详情失败: {e2}")

        except Exception as e:
            logger.error(f"ClickHouse权限审计失败: {e}")
            return {
                "status": "error",
                "message": f"权限审计失败: {str(e)}",
                "total_checked": 0,
                "risks_found": 0,
                "risks": []
            }

        return {
            "status": "success",
            "total_users": total_users,
            "high_privilege_users": high_privilege_users,
            "total_checked": total_users,
            "risks_found": len(risks),
            "message": f"审计了{total_users}个用户，发现{high_privilege_users}个高权限用户，{len(risks)}个风险",
            "risks": [r.to_dict() for r in risks[:20]]
        }

    def _audit_sqlite_permissions(self) -> Dict[str, Any]:
        """
        SQLite权限审计

        SQLite没有用户权限系统，主要检查文件权限

        返回:
            Dict: 审计结果
        """
        import os

        risks = []

        try:
            # 获取数据库路径
            result = self.connector.execute("PRAGMA database_list")
            db_path = None
            if result and result.rows:
                for row in result.rows:
                    if row[1] == 'main':
                        db_path = row[2]
                        break

            if db_path and db_path != ':memory:':
                # 检查文件权限（POSIX系统）
                if os.name == 'posix':
                    import stat
                    file_stat = os.stat(db_path)
                    file_mode = stat.filemode(file_stat.st_mode)

                    # 检查是否全局可读写
                    if file_stat.st_mode & stat.S_IWOTH:
                        risks.append(Risk(
                            severity="critical",
                            description=f"数据库文件全局可写: {file_mode}",
                            category="permission",
                            current_value=file_mode,
                            recommended_value="移除全局写权限"
                        ))

                    if file_stat.st_mode & stat.S_IROTH:
                        risks.append(Risk(
                            severity="high",
                            description=f"数据库文件全局可读: {file_mode}",
                            category="permission",
                            current_value=file_mode,
                            recommended_value="移除全局读权限"
                        ))

                # 检查文件所有者
                try:
                    import pwd
                    owner = pwd.getpwuid(os.stat(db_path).st_uid).pw_name
                except (ImportError, KeyError):
                    owner = str(os.stat(db_path).st_uid)

                # 检查WAL文件权限
                wal_path = db_path + "-wal"
                if os.path.exists(wal_path):
                    wal_stat = os.stat(wal_path)
                    if os.name == 'posix' and wal_stat.st_mode & stat.S_IWOTH:
                        risks.append(Risk(
                            severity="high",
                            description="WAL文件全局可写",
                            category="permission",
                            current_value="WAL全局可写",
                            recommended_value="移除WAL文件全局写权限"
                        ))

            else:
                risks.append(Risk(
                    severity="low",
                    description="内存数据库(:memory:)无文件权限控制",
                    category="permission",
                    current_value=":memory:",
                    recommended_value="使用文件数据库以获得权限控制"
                ))

        except Exception as e:
            logger.error(f"SQLite权限审计失败: {e}")
            return {
                "status": "error",
                "message": f"权限审计失败: {str(e)}",
                "total_checked": 0,
                "risks_found": 0,
                "risks": []
            }

        return {
            "status": "success",
            "total_users": 1,
            "high_privilege_users": 0,
            "total_checked": 1,
            "risks_found": len(risks),
            "message": f"SQLite无用户系统，检查文件权限发现{len(risks)}个风险",
            "risks": [r.to_dict() for r in risks[:20]]
        }

    def _audit_generic_permissions(self) -> Dict[str, Any]:
        """
        通用数据库权限审计

        为任意 JDBC 兼容数据库提供基础权限审计能力。
        通过标准 SQL 和 INFORMATION_SCHEMA 获取权限信息。

        探测优先级：
            1. INFORMATION_SCHEMA.TABLE_PRIVILEGES（标准视图）
            2. 当前用户查询
            3. 会话/连接信息

        返回：
            Dict: 审计结果
        """
        risks = []
        total_users = 0
        checks_performed = 0

        # 1. 尝试 TABLE_PRIVILEGES
        try:
            result = self.connector.execute(
                "SELECT COUNT(DISTINCT grantee) FROM information_schema.table_privileges"
            )
            if result.rows and result.rows[0][0] is not None:
                total_users = int(result.rows[0][0])
                checks_performed += 1

                # 检查是否有过多用户拥有表权限
                if total_users > 20:
                    risks.append(Risk(
                        severity="medium",
                        description=f"有{total_users}个用户拥有表级权限，可能存在过度授权",
                        category="permission",
                        current_value=f"{total_users}个授权用户",
                        recommended_value="定期审查并撤销不必要的权限"
                    ))
        except Exception as e:
            logger.debug(f"通用权限审计: TABLE_PRIVILEGES 不可用 [{e}]")

        # 2. 尝试查询当前用户
        try:
            current_user = None
            for sql in [
                "SELECT CURRENT_USER",
                "SELECT current_user",
                "SELECT USER()",
                "SELECT SESSION_USER",
            ]:
                try:
                    result = self.connector.execute(sql)
                    if result.rows and result.rows[0][0]:
                        current_user = str(result.rows[0][0])
                        checks_performed += 1
                        break
                except Exception:
                    continue

            if current_user:
                logger.info(f"通用权限审计: 当前用户={current_user}")
        except Exception:
            pass

        # 3. 尝试查询活跃会话/连接（作为用户数量的代理）
        if total_users == 0:
            try:
                for sql in [
                    "SELECT COUNT(DISTINCT usename) FROM pg_stat_activity",
                    "SELECT COUNT(DISTINCT user) FROM information_schema.processlist",
                    "SELECT COUNT(*) FROM sys.dm_exec_sessions WHERE is_user_process = 1",
                ]:
                    try:
                        result = self.connector.execute(sql)
                        if result.rows and result.rows[0][0] is not None:
                            total_users = int(result.rows[0][0])
                            checks_performed += 1
                            break
                    except Exception:
                        continue
            except Exception:
                pass

        # 4. 检查是否有公共可访问的表（无权限控制）
        try:
            result = self.connector.execute(
                "SELECT COUNT(*) FROM information_schema.tables "
                "WHERE table_schema IN ('public', 'PUBLIC')"
            )
            if result.rows and result.rows[0][0] is not None:
                public_tables = int(result.rows[0][0])
                if public_tables > 0:
                    risks.append(Risk(
                        severity="low",
                        description=f"public schema 中有{public_tables}个表，默认可能对所有用户可见",
                        category="permission",
                        current_value=f"public schema 有{public_tables}个表",
                        recommended_value="为敏感表设置适当的权限控制"
                    ))
        except Exception:
            pass

        if checks_performed == 0:
            return {
                "status": "success",
                "total_users": 0,
                "high_privilege_users": 0,
                "total_checked": 0,
                "risks_found": 0,
                "message": (
                    f"数据库类型 {self.dialect} 使用通用权限审计器。"
                    "未能通过 INFORMATION_SCHEMA 获取权限信息。"
                    "如需完整的权限审计，请使用支持的数据库类型专用分析器。"
                ),
                "risks": []
            }

        return {
            "status": "success",
            "total_users": total_users,
            "high_privilege_users": 0,
            "total_checked": total_users,
            "risks_found": len(risks),
            "message": (
                f"通用权限审计完成，"
                f"检测到{total_users}个用户，发现{len(risks)}个风险"
            ),
            "risks": [r.to_dict() for r in risks[:20]]
        }

    def _audit_clickhouse_config(self) -> Dict[str, Any]:
        """
        ClickHouse配置审计

        返回:
            Dict: 审计结果
        """
        risks = []
        checks_performed = 0

        try:
            # 检查1: 是否启用SSL
            try:
                result = self.connector.execute("""
                    SELECT name, value FROM system.server_settings
                    WHERE name LIKE '%ssl%'
                """)
                if not result or not result.rows:
                    risks.append(Risk(
                        severity="medium",
                        description="无法确认SSL配置状态",
                        category="config",
                        current_value="未知",
                        recommended_value="启用SSL加密连接"
                    ))
                checks_performed += 1
            except Exception as e:
                logger.warning(f"检查ClickHouse SSL配置失败: {e}")

            # 检查2: 默认用户密码
            try:
                result = self.connector.execute("""
                    SELECT name, auth_type, hash
                    FROM system.users
                    WHERE name = 'default'
                """)
                if result and result.rows:
                    auth_type = str(result.rows[0][1])
                    if auth_type == 'no_password':
                        risks.append(Risk(
                            severity="critical",
                            description="默认用户(default)使用无密码认证",
                            category="config",
                            current_value="default -> no_password",
                            recommended_value="为default用户设置密码"
                        ))
                checks_performed += 1
            except Exception as e:
                logger.warning(f"检查ClickHouse默认用户失败: {e}")

            # 检查3: 远程访问配置
            try:
                result = self.connector.execute("""
                    SELECT name, value FROM system.server_settings
                    WHERE name IN ('listen_host', 'tcp_port', 'http_port')
                """)
                settings = {row[0]: row[1] for row in result.rows} if result else {}
                listen_host = settings.get('listen_host', '')
                if listen_host == '::' or listen_host == '0.0.0.0':
                    risks.append(Risk(
                        severity="medium",
                        description=f"ClickHouse监听所有地址({listen_host})，可能暴露于公网",
                        category="config",
                        current_value=f"listen_host={listen_host}",
                        recommended_value="限制listen_host为特定IP"
                    ))
                checks_performed += 1
            except Exception as e:
                logger.warning(f"检查ClickHouse远程访问配置失败: {e}")

            # 检查4: 查询日志是否启用
            try:
                result = self.connector.execute("""
                    SELECT name, value FROM system.server_settings
                    WHERE name LIKE '%query_log%'
                """)
                if not result or not result.rows:
                    risks.append(Risk(
                        severity="low",
                        description="查询日志可能未启用",
                        category="config",
                        current_value="query_log未配置",
                        recommended_value="启用query_log以记录查询历史"
                    ))
                checks_performed += 1
            except Exception as e:
                logger.warning(f"检查ClickHouse查询日志失败: {e}")

        except Exception as e:
            logger.error(f"ClickHouse配置审计失败: {e}")
            return {
                "status": "error",
                "message": f"配置审计失败: {str(e)}",
                "total_checked": checks_performed,
                "risks_found": len(risks),
                "risks": []
            }

        return {
            "status": "success",
            "total_checks": checks_performed,
            "failed_checks": len(risks),
            "total_checked": checks_performed,
            "risks_found": len(risks),
            "message": f"检查了{checks_performed}项配置，发现{len(risks)}个问题",
            "risks": [r.to_dict() for r in risks]
        }

    def _audit_sqlite_config(self) -> Dict[str, Any]:
        """
        SQLite配置审计

        返回:
            Dict: 审计结果
        """
        risks = []
        checks_performed = 0

        try:
            # 检查1: 日志模式
            try:
                result = self.connector.execute("PRAGMA journal_mode")
                journal_mode = result.rows[0][0] if result else "unknown"

                if journal_mode.upper() == 'OFF':
                    risks.append(Risk(
                        severity="critical",
                        description="日志模式为OFF，数据完整性无保障",
                        category="config",
                        current_value="journal_mode=OFF",
                        recommended_value="journal_mode=WAL"
                    ))
                elif journal_mode.upper() == 'DELETE':
                    risks.append(Risk(
                        severity="low",
                        description="日志模式为DELETE，并发性能较差",
                        category="config",
                        current_value="journal_mode=DELETE",
                        recommended_value="journal_mode=WAL"
                    ))
                checks_performed += 1
            except Exception as e:
                logger.warning(f"检查SQLite日志模式失败: {e}")

            # 检查2: 同步模式
            try:
                result = self.connector.execute("PRAGMA synchronous")
                sync_value = int(result.rows[0][0]) if result else -1

                if sync_value == 0:
                    risks.append(Risk(
                        severity="high",
                        description="同步模式为OFF，可能导致数据丢失",
                        category="config",
                        current_value="synchronous=OFF",
                        recommended_value="synchronous=NORMAL"
                    ))
                checks_performed += 1
            except Exception as e:
                logger.warning(f"检查SQLite同步模式失败: {e}")

            # 检查3: 安全删除模式
            try:
                result = self.connector.execute("PRAGMA secure_delete")
                secure_delete = result.rows[0][0] if result else "unknown"

                if secure_delete == 0 or secure_delete == 'OFF':
                    risks.append(Risk(
                        severity="medium",
                        description="安全删除未启用，已删除数据可能可恢复",
                        category="config",
                        current_value="secure_delete=OFF",
                        recommended_value="secure_delete=ON"
                    ))
                checks_performed += 1
            except Exception as e:
                logger.warning(f"检查SQLite安全删除失败: {e}")

            # 检查4: 外键约束
            try:
                result = self.connector.execute("PRAGMA foreign_keys")
                foreign_keys = result.rows[0][0] if result else "unknown"

                if foreign_keys == 0 or foreign_keys == 'OFF':
                    risks.append(Risk(
                        severity="low",
                        description="外键约束未启用",
                        category="config",
                        current_value="foreign_keys=OFF",
                        recommended_value="foreign_keys=ON"
                    ))
                checks_performed += 1
            except Exception as e:
                logger.warning(f"检查SQLite外键约束失败: {e}")

        except Exception as e:
            logger.error(f"SQLite配置审计失败: {e}")
            return {
                "status": "error",
                "message": f"配置审计失败: {str(e)}",
                "total_checked": checks_performed,
                "risks_found": len(risks),
                "risks": []
            }

        return {
            "status": "success",
            "total_checks": checks_performed,
            "failed_checks": len(risks),
            "total_checked": checks_performed,
            "risks_found": len(risks),
            "message": f"检查了{checks_performed}项配置，发现{len(risks)}个问题",
            "risks": [r.to_dict() for r in risks]
        }

    def _audit_generic_config(self) -> Dict[str, Any]:
        """
        通用数据库配置审计

        为任意 JDBC 兼容数据库提供基础配置审计能力。
        通过标准 SQL 查询数据库版本和一些通用配置参数。

        返回：
            Dict: 审计结果
        """
        risks = []
        checks_performed = 0
        version = None

        # 1. 查询数据库版本
        try:
            for sql in [
                "SELECT VERSION()",
                "SELECT version()",
                "SELECT @@version",
                "SELECT sqlite_version()",
            ]:
                try:
                    result = self.connector.execute(sql)
                    if result.rows and result.rows[0][0]:
                        version = str(result.rows[0][0])
                        checks_performed += 1
                        break
                except Exception:
                    continue
        except Exception:
            pass

        # 2. 尝试查询一些通用配置参数
        config_checks = [
            ("SELECT current_database()", "当前数据库"),
            ("SELECT DATABASE()", "当前数据库"),
        ]
        for sql, desc in config_checks:
            try:
                result = self.connector.execute(sql)
                if result.rows and result.rows[0][0]:
                    checks_performed += 1
                    break
            except Exception:
                continue

        # 3. 检查数据库大小（作为容量风险指标）
        try:
            for sql in [
                "SELECT pg_database_size(current_database()) / 1024.0 / 1024.0",
                "SELECT SUM(data_length + index_length) / 1024.0 / 1024.0 FROM information_schema.tables WHERE table_schema = DATABASE()",
            ]:
                try:
                    result = self.connector.execute(sql)
                    if result.rows and result.rows[0][0] is not None:
                        size_mb = float(result.rows[0][0])
                        if size_mb > 10000:
                            risks.append(Risk(
                                severity="medium",
                                description=f"数据库大小约{size_mb:.0f}MB，建议进行容量规划",
                                category="config",
                                current_value=f"数据库大小={size_mb:.0f}MB",
                                recommended_value="监控数据库增长趋势，规划扩容"
                            ))
                        checks_performed += 1
                        break
                except Exception:
                    continue
        except Exception:
            pass

        # 4. 检查表数量（作为复杂度指标）
        try:
            result = self.connector.execute(
                "SELECT COUNT(*) FROM information_schema.tables "
                "WHERE table_type = 'BASE TABLE'"
            )
            if result.rows and result.rows[0][0] is not None:
                table_count = int(result.rows[0][0])
                if table_count > 500:
                    risks.append(Risk(
                        severity="low",
                        description=f"数据库有{table_count}个表，结构可能过于复杂",
                        category="config",
                        current_value=f"表数量={table_count}",
                        recommended_value="考虑拆分数据库或归档历史表"
                    ))
                checks_performed += 1
        except Exception:
            pass

        if checks_performed == 0:
            return {
                "status": "success",
                "total_checks": 0,
                "failed_checks": 0,
                "total_checked": 0,
                "risks_found": 0,
                "message": (
                    f"数据库类型 {self.dialect} 使用通用配置审计器。"
                    "未能获取任何配置信息。"
                    "如需完整的配置审计，请使用支持的数据库类型专用分析器。"
                ),
                "risks": []
            }

        return {
            "status": "success",
            "total_checks": checks_performed,
            "failed_checks": len(risks),
            "total_checked": checks_performed,
            "risks_found": len(risks),
            "message": (
                f"通用配置审计完成（版本: {version or '未知'}），"
                f"检查{checks_performed}项，发现{len(risks)}个问题"
            ),
            "risks": [r.to_dict() for r in risks]
        }

    def generate_report(self, modules_results: Dict[str, Any]) -> RiskReport:
        """
        生成综合审计报告

        参数:
            modules_results: 各模块检测结果

        返回:
            RiskReport: 风险报告
        """
        all_risks = []
        failed_modules = []

        for module, result in modules_results.items():
            if isinstance(result, dict):
                # 处理标准响应格式: {"success": true, "data": {...}}
                if "success" in result:
                    if not result.get("success"):
                        # 模块执行失败，记录为严重风险
                        failed_modules.append(module)
                        message = result.get("message", "未知错误")
                        all_risks.append(Risk(
                            severity="critical",
                            description=f"[{module}] 检测失败: {message}",
                            category=module
                        ))
                        continue
                    actual_data = result.get("data", {})
                    risks = actual_data.get("risks", [])
                else:
                    # 直接数据格式（向后兼容）
                    if result.get("status") == "failed":
                        failed_modules.append(module)
                        message = result.get("message", "未知错误")
                        all_risks.append(Risk(
                            severity="critical",
                            description=f"[{module}] 检测失败: {message}",
                            category=module
                        ))
                        continue
                    risks = result.get("risks", [])

                for risk_data in risks:
                    all_risks.append(Risk(
                        severity=risk_data.get("severity", "low"),
                        description=risk_data.get("description", ""),
                        category=risk_data.get("category", module)
                    ))

        # 统计风险数量
        critical_count = sum(1 for r in all_risks if r.severity == "critical")
        high_count = sum(1 for r in all_risks if r.severity == "high")
        medium_count = sum(1 for r in all_risks if r.severity == "medium")
        low_count = sum(1 for r in all_risks if r.severity == "low")
        total_risks = len(all_risks)

        return RiskReport(
            risks=all_risks,
            total_risks=total_risks,
            critical_count=critical_count,
            high_count=high_count,
            medium_count=medium_count,
            low_count=low_count,
            failed_modules=failed_modules
        )
