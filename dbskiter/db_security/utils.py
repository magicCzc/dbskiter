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

import math
import re
from collections import Counter
from typing import Any, Dict, List, Optional, Tuple

from dbskiter.db_security.models import (
    RiskLevel, SensitivityLevel, Risk, RiskReport
)


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

    def audit_permissions(self) -> Dict[str, Any]:
        """
        审计权限 - 查询数据库用户权限

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
                                category="permission"
                            ))

                # 检查通配符主机（root用户允许任意主机连接是风险）
                if host == '%':
                    if is_root:
                        # root允许任意主机连接是高风险
                        risks.append(Risk(
                            severity="high",
                            description=f"root用户允许从任意主机连接，存在安全风险",
                            category="permission"
                        ))
                    else:
                        # 其他用户允许任意主机连接是中风险
                        risks.append(Risk(
                            severity="medium",
                            description=f"用户 {user} 允许从任意主机连接",
                            category="permission"
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

    def audit_config(self) -> Dict[str, Any]:
        """
        审计配置 - 查询数据库安全配置

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
                        category="config"
                    ))
                checks_performed += 1
            except Exception as e:
                logger.debug(f"检查SSL配置失败: {e}")

            # 检查2: 密码策略
            try:
                result = self.connector.execute("SHOW VARIABLES LIKE 'validate_password%'")
                if not result.rows:
                    risks.append(Risk(
                        severity="medium",
                        description="未启用密码强度验证插件",
                        category="config"
                    ))
                checks_performed += 1
            except Exception as e:
                logger.debug(f"检查密码策略失败: {e}")

            # 检查3: 审计日志
            try:
                result = self.connector.execute("SHOW VARIABLES LIKE 'general_log'")
                if result.rows and result.rows[0][1] != 'ON':
                    risks.append(Risk(
                        severity="low",
                        description="通用查询日志未启用",
                        category="config"
                    ))
                checks_performed += 1
            except Exception as e:
                logger.debug(f"检查审计日志失败: {e}")

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
                        category="config"
                    ))
                checks_performed += 1
            except Exception as e:
                logger.debug(f"检查root远程访问失败: {e}")

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
                        category="config"
                    ))
                checks_performed += 1
            except Exception as e:
                logger.debug(f"检查匿名用户失败: {e}")

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

    def generate_report(self, modules_results: Dict[str, Any]) -> RiskReport:
        """
        生成综合审计报告

        参数:
            modules_results: 各模块检测结果

        返回:
            RiskReport: 风险报告
        """
        all_risks = []

        for module, result in modules_results.items():
            if isinstance(result, dict):
                # 处理标准响应格式: {"success": true, "data": {...}}
                if "success" in result and "data" in result:
                    actual_data = result.get("data", {})
                    risks = actual_data.get("risks", [])
                else:
                    # 直接数据格式
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

        return RiskReport(
            total_risks=len(all_risks),
            critical_count=critical_count,
            high_count=high_count,
            medium_count=medium_count,
            low_count=low_count,
            risks=all_risks
        )
