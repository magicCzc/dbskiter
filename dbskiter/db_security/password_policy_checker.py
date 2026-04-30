"""
db_security/password_policy_checker.py

文件功能：数据库密码策略检查，检测弱密码、过期密码、空密码等安全问题
主要类：
    - PasswordPolicyChecker: 密码策略检查器
    - PasswordCheckResult: 密码检查结果
    - UserPasswordStatus: 用户密码状态

使用示例:
    >>> from db_security.password_policy_checker import PasswordPolicyChecker
    >>> checker = PasswordPolicyChecker(connector)
    >>> result = checker.check_password_policy()
    >>> weak_passwords = checker.find_weak_passwords()

版本: 3.1.0
作者: AI Assistant
创建时间: 2026-04-23
最后修改: 2026-04-23
"""

import logging
import re
import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set
from enum import Enum

from dbskiter.shared.unified_connector import UnifiedConnector
from .models import RiskLevel, create_success_response, create_error_response, ErrorCode

logger = logging.getLogger(__name__)


class PasswordStrength(Enum):
    """密码强度等级"""
    EMPTY = "empty"           # 空密码
    VERY_WEAK = "very_weak"   # 极弱
    WEAK = "weak"             # 弱
    MEDIUM = "medium"         # 中等
    STRONG = "strong"         # 强
    VERY_STRONG = "very_strong"  # 极强


@dataclass
class UserPasswordStatus:
    """用户密码状态"""
    username: str
    host: str
    password_hash: Optional[str]
    password_expired: bool
    password_lifetime: Optional[int]
    password_last_changed: Optional[datetime]
    account_locked: bool
    lock_time: Optional[datetime]
    failed_login_attempts: int
    strength: PasswordStrength = PasswordStrength.MEDIUM
    issues: List[str] = field(default_factory=list)


@dataclass
class PasswordPolicyConfig:
    """密码策略配置"""
    min_length: int = 8
    require_uppercase: bool = True
    require_lowercase: bool = True
    require_digits: bool = True
    require_special: bool = True
    max_age_days: int = 90
    prevent_reuse: int = 5
    lock_after_failures: int = 5
    lock_duration_minutes: int = 30


class PasswordPolicyChecker:
    """
    密码策略检查器

    功能:
        - 检查密码复杂度策略
        - 发现弱密码和空密码
        - 检测过期密码
        - 检查账户锁定状态
        - 评估整体密码安全状况
    """

    # 常见弱密码列表
    COMMON_WEAK_PASSWORDS = [
        "123456", "password", "12345678", "qwerty", "123456789",
        "letmein", "1234567", "football", "iloveyou", "admin",
        "welcome", "monkey", "login", "abc123", "111111",
        "123123", "password123", "1234", "baseball", "qwertyuiop",
        # 常见变体
        "Password1", "Password123", "Admin123", "Root123",
        "Ab@123456", "Aa@123456", "Test@123", "User@123",
        "Qwerty@1", "Welcome@1", "Login@123"
    ]
    
    # 弱密码模式（正则表达式）
    WEAK_PASSWORD_PATTERNS = [
        # 连续数字结尾：如 Ab@123456, Password123
        r'^[a-zA-Z]+[@#$%^&*][0-9]{6,}$',
        # 简单前缀+连续数字：如 Test123456
        r'^(test|admin|root|user|password|login|welcome)[@#$%^&*]?[0-9]{3,}$',
        # 键盘顺序：如 Qwerty@1
        r'^[qQwWeErRtTyY]+[@#$%^&*]?[0-9]+$',
        # 重复模式：如 111aaa, abcabc
        r'^(.)\1{2,}',
        # 纯数字且长度小于10
        r'^[0-9]{1,9}$',
        # 纯字母且长度小于8
        r'^[a-zA-Z]{1,7}$',
        # 简单替换：如 P@ssw0rd
        r'^[pP][@#][sS]{2}[wW][0o][rR][dD]',
    ]

    # 密码复杂度评分权重
    SCORE_WEIGHTS = {
        "length": 2,      # 长度基础分
        "uppercase": 1,   # 大写字母
        "lowercase": 1,   # 小写字母
        "digits": 1,      # 数字
        "special": 2,     # 特殊字符
        "variety": 2      # 字符种类多样性
    }

    def __init__(self, connector: UnifiedConnector):
        """
        初始化密码策略检查器

        参数:
            connector: 数据库连接器
        """
        self.connector = connector
        self.dialect = connector.dialect.lower() if connector else "unknown"
        self.config = PasswordPolicyConfig()

    def check_password_policy(self) -> Dict[str, Any]:
        """
        检查数据库密码策略配置

        返回:
            Dict: 密码策略检查结果
        """
        try:
            policy_info = self._get_password_policy()
            user_statuses = self._get_all_user_password_status()

            # 统计问题
            empty_passwords = [u for u in user_statuses if u.strength == PasswordStrength.EMPTY]
            weak_passwords = [u for u in user_statuses if u.strength in [PasswordStrength.WEAK, PasswordStrength.VERY_WEAK]]
            expired_passwords = [u for u in user_statuses if u.password_expired]
            locked_accounts = [u for u in user_statuses if u.account_locked]

            # 计算整体评分
            score = self._calculate_password_score(user_statuses)

            return create_success_response(
                data={
                    "policy_config": policy_info,
                    "total_users": len(user_statuses),
                    "empty_passwords": len(empty_passwords),
                    "weak_passwords": len(weak_passwords),
                    "expired_passwords": len(expired_passwords),
                    "locked_accounts": len(locked_accounts),
                    "security_score": score,
                    "risk_level": self._get_risk_level(score),
                    "critical_issues": self._get_critical_issues(user_statuses),
                    "recommendations": self._generate_policy_recommendations(
                        empty_passwords, weak_passwords, expired_passwords, policy_info
                    ),
                    # 添加详细的账号列表
                    "empty_password_users": [self._user_to_dict(u) for u in empty_passwords],
                    "weak_password_users": [self._user_to_dict(u) for u in weak_passwords],
                    "expired_password_users": [self._user_to_dict(u) for u in expired_passwords],
                    "locked_accounts_users": [self._user_to_dict(u) for u in locked_accounts]
                },
                message=f"密码策略检查完成，安全评分: {score}/100"
            )

        except Exception as e:
            logger.error(f"密码策略检查失败: {e}")
            return create_error_response(
                f"检查失败: {str(e)}",
                ErrorCode.AUDIT_FAILED
            )

    def find_weak_passwords(self) -> Dict[str, Any]:
        """
        发现弱密码用户

        返回:
            Dict: 弱密码用户列表
        """
        try:
            user_statuses = self._get_all_user_password_status()

            # 分类弱密码
            empty = [u for u in user_statuses if u.strength == PasswordStrength.EMPTY]
            very_weak = [u for u in user_statuses if u.strength == PasswordStrength.VERY_WEAK]
            weak = [u for u in user_statuses if u.strength == PasswordStrength.WEAK]

            return create_success_response(
                data={
                    "summary": {
                        "empty_passwords": len(empty),
                        "very_weak_passwords": len(very_weak),
                        "weak_passwords": len(weak),
                        "total_at_risk": len(empty) + len(very_weak) + len(weak)
                    },
                    "empty_password_users": [self._user_to_dict(u) for u in empty],
                    "very_weak_password_users": [self._user_to_dict(u) for u in very_weak],
                    "weak_password_users": [self._user_to_dict(u) for u in weak],
                    "immediate_action_required": [u.username for u in empty + very_weak]
                },
                message=f"发现 {len(empty)} 个空密码，{len(very_weak)} 个极弱密码，{len(weak)} 个弱密码"
            )

        except Exception as e:
            logger.error(f"弱密码检查失败: {e}")
            return create_error_response(
                f"检查失败: {str(e)}",
                ErrorCode.AUDIT_FAILED
            )

    def check_expired_passwords(self) -> Dict[str, Any]:
        """
        检查过期密码

        返回:
            Dict: 过期密码用户列表
        """
        try:
            user_statuses = self._get_all_user_password_status()

            expired = [u for u in user_statuses if u.password_expired]
            expiring_soon = []

            for user in user_statuses:
                if user.password_last_changed and not user.password_expired:
                    days_since_change = (datetime.now() - user.password_last_changed).days
                    if days_since_change > self.config.max_age_days - 7:  # 7天内过期
                        expiring_soon.append({
                            "username": user.username,
                            "host": user.host,
                            "days_until_expiry": self.config.max_age_days - days_since_change,
                            "last_changed": user.password_last_changed.isoformat() if hasattr(user.password_last_changed, 'isoformat') else str(user.password_last_changed)
                        })

            return create_success_response(
                data={
                    "expired_count": len(expired),
                    "expiring_soon_count": len(expiring_soon),
                    "expired_users": [self._user_to_dict(u) for u in expired],
                    "expiring_soon": expiring_soon
                },
                message=f"发现 {len(expired)} 个过期密码，{len(expiring_soon)} 个即将过期"
            )

        except Exception as e:
            logger.error(f"过期密码检查失败: {e}")
            return create_error_response(
                f"检查失败: {str(e)}",
                ErrorCode.AUDIT_FAILED
            )

    def _get_password_policy(self) -> Dict[str, Any]:
        """获取数据库密码策略配置"""
        policy = {}

        try:
            if "mysql" in self.dialect:
                policy = self._get_mysql_password_policy()
            elif "postgresql" in self.dialect:
                policy = self._get_postgres_password_policy()
            elif "oracle" in self.dialect:
                policy = self._get_oracle_password_policy()

        except Exception as e:
            logger.warning(f"获取密码策略失败: {e}")

        return policy

    def _get_mysql_password_policy(self) -> Dict[str, Any]:
        """获取MySQL密码策略"""
        policy = {}

        try:
            # 查询validate_password插件配置
            result = self.connector.execute("""
                SHOW VARIABLES LIKE 'validate_password%'
            """)

            for row in result.rows:
                var_name = row[0]
                var_value = row[1]
                policy[var_name] = var_value

            # 查询默认密码过期策略
            result = self.connector.execute("""
                SHOW VARIABLES LIKE 'default_password_lifetime'
            """)

            for row in result.rows:
                policy[row[0]] = row[1]

        except Exception as e:
            logger.warning(f"获取MySQL密码策略失败: {e}")

        return policy

    def _get_postgres_password_policy(self) -> Dict[str, Any]:
        """获取PostgreSQL密码策略"""
        policy = {}

        try:
            # PostgreSQL密码策略通常通过pg_hba.conf和扩展实现
            result = self.connector.execute("""
                SHOW password_encryption
            """)

            for row in result.rows:
                policy["password_encryption"] = row[0]

        except Exception as e:
            logger.warning(f"获取PostgreSQL密码策略失败: {e}")

        return policy

    def _get_oracle_password_policy(self) -> Dict[str, Any]:
        """获取Oracle密码策略"""
        policy = {}

        try:
            # Oracle密码策略通过profile实现
            result = self.connector.execute("""
                SELECT 
                    profile,
                    resource_name,
                    limit
                FROM dba_profiles
                WHERE resource_type = 'PASSWORD'
            """)

            for row in result.rows:
                profile = row[0]
                resource = row[1]
                limit = row[2]
                if profile not in policy:
                    policy[profile] = {}
                policy[profile][resource] = limit

        except Exception as e:
            logger.warning(f"获取Oracle密码策略失败: {e}")

        return policy

    def _get_all_user_password_status(self) -> List[UserPasswordStatus]:
        """获取所有用户密码状态"""
        statuses = []

        try:
            if "mysql" in self.dialect:
                statuses = self._get_mysql_user_passwords()
            elif "postgresql" in self.dialect:
                statuses = self._get_postgres_user_passwords()
            elif "oracle" in self.dialect:
                statuses = self._get_oracle_user_passwords()

        except Exception as e:
            logger.error(f"获取用户密码状态失败: {e}")

        return statuses

    def _get_mysql_user_passwords(self) -> List[UserPasswordStatus]:
        """获取MySQL用户密码信息"""
        statuses = []

        try:
            # 检查MySQL版本和可用列
            version_result = self.connector.execute("SELECT VERSION()")
            version_str = version_result.rows[0][0] if version_result.rows else "5.7"
            major_version = int(version_str.split('.')[0])

            # 根据版本构建查询
            if major_version >= 8:
                # MySQL 8.0+ 支持更多字段
                result = self.connector.execute("""
                    SELECT 
                        user,
                        host,
                        authentication_string,
                        password_expired,
                        password_lifetime,
                        password_last_changed,
                        account_locked,
                        lock_time,
                        failed_login_attempts
                    FROM mysql.user
                    WHERE user NOT LIKE 'mysql.%'
                    ORDER BY user, host
                """)
            else:
                # MySQL 5.7 兼容性查询
                result = self.connector.execute("""
                    SELECT 
                        user,
                        host,
                        authentication_string,
                        password_expired,
                        password_lifetime,
                        password_last_changed,
                        'N' as account_locked,
                        NULL as lock_time,
                        0 as failed_login_attempts
                    FROM mysql.user
                    WHERE user NOT LIKE 'mysql.%'
                    ORDER BY user, host
                """)

            for row in result.rows:
                status = UserPasswordStatus(
                    username=row[0] or "",
                    host=row[1] or "%",
                    password_hash=row[2],
                    password_expired=row[3] == "Y" if row[3] else False,
                    password_lifetime=row[4],
                    password_last_changed=row[5],
                    account_locked=row[6] == "Y" if row[6] else False,
                    lock_time=row[7],
                    failed_login_attempts=row[8] or 0
                )

                # 评估密码强度
                status.strength = self._assess_password_strength(status.password_hash, status.username)
                status.issues = self._identify_password_issues(status)

                statuses.append(status)

        except Exception as e:
            logger.error(f"获取MySQL用户密码信息失败: {e}")

        return statuses

    def _get_postgres_user_passwords(self) -> List[UserPasswordStatus]:
        """获取PostgreSQL用户密码信息"""
        statuses = []

        try:
            result = self.connector.execute("""
                SELECT 
                    rolname as username,
                    rolpassword as password_hash,
                    rolvaliduntil as password_expiry,
                    rolconnlimit as connection_limit
                FROM pg_authid
                WHERE rolcanlogin = true
            """)

            for row in result.rows:
                password_expired = False
                if row[2] and isinstance(row[2], datetime):
                    password_expired = row[2] < datetime.now()

                status = UserPasswordStatus(
                    username=row[0] or "",
                    host="%",
                    password_hash=row[1],
                    password_expired=password_expired,
                    password_lifetime=None,
                    password_last_changed=None,
                    account_locked=False,
                    lock_time=None,
                    failed_login_attempts=0
                )

                status.strength = self._assess_password_strength(status.password_hash, status.username)
                status.issues = self._identify_password_issues(status)

                statuses.append(status)

        except Exception as e:
            logger.error(f"获取PostgreSQL用户密码信息失败: {e}")

        return statuses

    def _get_oracle_user_passwords(self) -> List[UserPasswordStatus]:
        """获取Oracle用户密码信息"""
        statuses = []

        try:
            result = self.connector.execute("""
                SELECT 
                    username,
                    account_status,
                    lock_date,
                    expiry_date,
                    profile
                FROM dba_users
                WHERE account_status IS NOT NULL
            """)

            for row in result.rows:
                account_status = row[1] or ""
                account_locked = "LOCKED" in account_status.upper()
                password_expired = "EXPIRED" in account_status.upper()

                status = UserPasswordStatus(
                    username=row[0] or "",
                    host="%",
                    password_hash=None,  # Oracle不直接暴露密码哈希
                    password_expired=password_expired,
                    password_lifetime=None,
                    password_last_changed=None,
                    account_locked=account_locked,
                    lock_time=row[2],
                    failed_login_attempts=0
                )

                # Oracle无法直接评估密码强度
                status.strength = PasswordStrength.MEDIUM
                status.issues = self._identify_password_issues(status)

                statuses.append(status)

        except Exception as e:
            logger.error(f"获取Oracle用户密码信息失败: {e}")

        return statuses

    def _assess_password_strength(self, password_hash: Optional[str], username: str = "") -> PasswordStrength:
        """
        评估密码强度
        
        参数:
            password_hash: 密码哈希
            username: 用户名（用于检测用户名相关弱密码）
            
        返回:
            PasswordStrength: 密码强度等级
        """
        if not password_hash or password_hash == "":
            return PasswordStrength.EMPTY

        # 检查是否为空密码标记
        if password_hash in ["*THISISNOTAVALIDPASSWORDTHATCANBEUSEDHERE", ""]:
            return PasswordStrength.EMPTY

        # 尝试从哈希中提取可能的明文特征（针对MySQL旧版哈希）
        # 注意：这只能检测已知的弱密码模式，无法解密哈希
        
        # 检查是否是已知的弱密码哈希
        if self._is_known_weak_hash(password_hash):
            return PasswordStrength.VERY_WEAK
        
        # 基于哈希长度和特征进行判断
        hash_len = len(password_hash)
        
        # 极短哈希（明文或简单MD5）
        if hash_len < 16:
            return PasswordStrength.VERY_WEAK
        
        # 短哈希（可能是弱密码）
        if hash_len < 32:
            return PasswordStrength.WEAK
        
        # MySQL 4.1+ 的哈希格式（41字节）
        # 如果哈希符合弱密码特征，标记为弱
        if hash_len == 41 and password_hash.startswith('*'):
            # 这是MySQL的SHA1哈希，无法直接判断强度
            # 但如果是常见弱密码，哈希值会有特征
            if self._check_mysql_hash_pattern(password_hash):
                return PasswordStrength.WEAK
        
        return PasswordStrength.MEDIUM
    
    def _is_known_weak_hash(self, password_hash: str) -> bool:
        """
        检查是否是已知的弱密码哈希
        
        通过比对常见弱密码的哈希值来判断
        """
        import hashlib
        
        # 计算常见弱密码的哈希并比对
        for weak_pass in self.COMMON_WEAK_PASSWORDS:
            # MySQL SHA1哈希格式: *SHA1(SHA1(password))
            mysql_hash = self._mysql_password_hash(weak_pass)
            if mysql_hash == password_hash:
                return True
            
            # 标准SHA1
            sha1_hash = hashlib.sha1(weak_pass.encode()).hexdigest()
            if sha1_hash == password_hash.lower():
                return True
            
            # 标准SHA256
            sha256_hash = hashlib.sha256(weak_pass.encode()).hexdigest()
            if sha256_hash == password_hash.lower():
                return True
        
        return False
    
    def _mysql_password_hash(self, password: str) -> str:
        """
        计算MySQL密码哈希
        
        MySQL 4.1+ 使用: SHA1(SHA1(password))
        """
        import hashlib
        hash1 = hashlib.sha1(password.encode()).digest()
        hash2 = hashlib.sha1(hash1).hexdigest()
        return f"*{hash2.upper()}"
    
    def _check_mysql_hash_pattern(self, password_hash: str) -> bool:
        """
        检查MySQL哈希是否符合弱密码特征
        
        某些弱密码的哈希有特定模式
        """
        # 这里可以添加特定弱密码的哈希模式识别
        # 例如：连续字符的哈希往往有特定特征
        
        # 简单检查：如果哈希中包含大量重复模式
        hash_part = password_hash[1:]  # 去掉开头的*
        
        # 检查是否有明显的重复模式（弱密码特征）
        char_counts = {}
        for c in hash_part:
            char_counts[c] = char_counts.get(c, 0) + 1
        
        # 如果某个字符出现频率过高，可能是弱密码
        max_count = max(char_counts.values()) if char_counts else 0
        if max_count > len(hash_part) * 0.3:  # 某个字符占30%以上
            return True
        
        return False

    def _identify_password_issues(self, status: UserPasswordStatus) -> List[str]:
        """识别密码问题"""
        issues = []

        if status.strength == PasswordStrength.EMPTY:
            issues.append("空密码")

        if status.password_expired:
            issues.append("密码已过期")

        if status.account_locked:
            issues.append("账户已锁定")

        if status.failed_login_attempts > 3:
            issues.append(f"登录失败次数过多 ({status.failed_login_attempts}次)")

        return issues

    def _calculate_password_score(self, user_statuses: List[UserPasswordStatus]) -> int:
        """计算密码安全评分"""
        if not user_statuses:
            return 100

        total_users = len(user_statuses)
        if total_users == 0:
            return 100

        # 计算扣分
        deductions = 0

        empty_count = sum(1 for u in user_statuses if u.strength == PasswordStrength.EMPTY)
        weak_count = sum(1 for u in user_statuses if u.strength in [PasswordStrength.WEAK, PasswordStrength.VERY_WEAK])
        expired_count = sum(1 for u in user_statuses if u.password_expired)
        locked_count = sum(1 for u in user_statuses if u.account_locked)

        # 空密码扣30分
        deductions += (empty_count / total_users) * 30
        # 弱密码扣20分
        deductions += (weak_count / total_users) * 20
        # 过期密码扣10分
        deductions += (expired_count / total_users) * 10
        # 锁定账户扣5分
        deductions += (locked_count / total_users) * 5

        score = max(0, 100 - int(deductions))
        return score

    def _get_risk_level(self, score: int) -> str:
        """获取风险等级"""
        if score >= 90:
            return "LOW"
        elif score >= 70:
            return "MEDIUM"
        elif score >= 50:
            return "HIGH"
        else:
            return "CRITICAL"

    def _get_critical_issues(self, user_statuses: List[UserPasswordStatus]) -> List[Dict[str, Any]]:
        """获取关键问题"""
        issues = []

        for status in user_statuses:
            if status.strength == PasswordStrength.EMPTY:
                issues.append({
                    "type": "empty_password",
                    "severity": "CRITICAL",
                    "user": status.username,
                    "host": status.host,
                    "description": f"用户 {status.username} 使用空密码"
                })

            if status.password_expired:
                issues.append({
                    "type": "expired_password",
                    "severity": "HIGH",
                    "user": status.username,
                    "host": status.host,
                    "description": f"用户 {status.username} 密码已过期"
                })

        return issues

    def _generate_policy_recommendations(
        self,
        empty_passwords: List[UserPasswordStatus],
        weak_passwords: List[UserPasswordStatus],
        expired_passwords: List[UserPasswordStatus],
        policy_info: Dict[str, Any]
    ) -> List[str]:
        """生成策略建议"""
        recommendations = []

        if empty_passwords:
            recommendations.append("立即为所有用户设置非空密码")
            recommendations.append("禁用空密码登录")

        if weak_passwords:
            recommendations.append("强制用户修改弱密码")
            recommendations.append("启用密码复杂度验证插件")

        if expired_passwords:
            recommendations.append("通知用户更新过期密码")

        if not policy_info:
            recommendations.append("建议启用数据库密码策略插件")

        if not recommendations:
            recommendations.append("密码策略配置良好，继续保持")

        return recommendations

    def _user_to_dict(self, status: UserPasswordStatus) -> Dict[str, Any]:
        """将用户密码状态转换为字典"""
        return {
            "username": status.username,
            "host": status.host,
            "password_expired": status.password_expired,
            "account_locked": status.account_locked,
            "lock_time": status.lock_time.isoformat() if hasattr(status.lock_time, 'isoformat') else str(status.lock_time) if status.lock_time else None,
            "failed_login_attempts": status.failed_login_attempts,
            "strength": status.strength.value,
            "issues": status.issues
        }
