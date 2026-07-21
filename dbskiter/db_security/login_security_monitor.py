"""
db_security/login_security_monitor.py

文件功能：数据库登录安全监控，检测暴力破解、异常登录等安全威胁
主要类：
    - LoginSecurityMonitor: 登录安全监控器
    - LoginAttempt: 登录尝试记录
    - SecurityAlert: 安全告警

使用示例:
    >>> from db_security.login_security_monitor import LoginSecurityMonitor
    >>> monitor = LoginSecurityMonitor(connector)
    >>> result = monitor.check_failed_logins(hours=24)
    >>> alerts = monitor.detect_brute_force()

版本: 3.1.0
作者: Magiczc
创建时间: 2026-04-23
最后修改: 2026-04-23
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
from collections import defaultdict

from dbskiter.shared.unified_connector import UnifiedConnector
from .models import RiskLevel, create_success_response, create_error_response, ErrorCode

logger = logging.getLogger(__name__)


@dataclass
class LoginAttempt:
    """登录尝试记录"""
    user: str
    host: str
    attempt_time: datetime
    success: bool
    error_code: Optional[str] = None
    error_message: Optional[str] = None


@dataclass
class SecurityAlert:
    """安全告警"""
    alert_type: str
    severity: RiskLevel
    description: str
    details: Dict[str, Any] = field(default_factory=dict)
    detected_at: datetime = field(default_factory=datetime.now)
    recommendations: List[str] = field(default_factory=list)


class LoginSecurityMonitor:
    """
    登录安全监控器

    功能:
        - 监控登录失败事件
        - 检测暴力破解攻击
        - 发现异常登录行为
        - 识别可疑IP地址
        - 追踪账户锁定事件
    """

    # 暴力破解检测阈值
    BRUTE_FORCE_THRESHOLD = 5  # 5分钟内失败次数
    BRUTE_FORCE_WINDOW = 5  # 分钟

    # 异常登录检测阈值
    SUSPICIOUS_IP_THRESHOLD = 10  # 同一IP尝试不同账户次数
    OFF_HOUR_LOGIN_THRESHOLD = 3  # 非工作时间登录次数

    def __init__(self, connector: UnifiedConnector):
        """
        初始化登录安全监控器

        参数:
            connector: 数据库连接器
        """
        self.connector = connector
        self.dialect = connector.dialect.lower() if connector else "unknown"

    def check_failed_logins(
        self,
        hours: int = 24,
        limit: int = 100
    ) -> Dict[str, Any]:
        """
        检查登录失败记录

        参数:
            hours: 检查最近多少小时
            limit: 返回记录数量限制

        返回:
            Dict: 包含失败登录记录和统计信息
        """
        try:
            attempts = self._get_login_attempts(hours=hours, success_only=False)
            failed_attempts = [a for a in attempts if not a.success]

            # 统计分析
            stats = self._analyze_failed_logins(failed_attempts)

            # 生成告警
            alerts = self._generate_login_alerts(failed_attempts)

            return create_success_response(
                data={
                    "total_attempts": len(attempts),
                    "failed_attempts": len(failed_attempts),
                    "failure_rate": round(len(failed_attempts) / len(attempts) * 100, 2) if attempts else 0,
                    "statistics": stats,
                    "alerts": [self._alert_to_dict(a) for a in alerts],
                    "recent_failures": [
                        {
                            "user": a.user,
                            "host": a.host,
                            "time": a.attempt_time.isoformat(),
                            "error": a.error_message
                        }
                        for a in failed_attempts[:limit]
                    ]
                },
                message=f"发现 {len(failed_attempts)} 次登录失败，{len(alerts)} 个安全告警"
            )

        except Exception as e:
            logger.error(f"检查登录失败记录失败: {e}")
            return create_error_response(
                f"检查失败: {str(e)}",
                ErrorCode.AUDIT_FAILED
            )

    def detect_brute_force(
        self,
        hours: int = 24
    ) -> Dict[str, Any]:
        """
        检测暴力破解攻击

        参数:
            hours: 检查最近多少小时

        返回:
            Dict: 暴力破解检测结果
        """
        try:
            attempts = self._get_login_attempts(hours=hours, success_only=False)
            failed_attempts = [a for a in attempts if not a.success]

            # 按IP和用户分组统计
            ip_attempts = defaultdict(list)
            user_attempts = defaultdict(list)

            for attempt in failed_attempts:
                ip_attempts[attempt.host].append(attempt)
                user_attempts[attempt.user].append(attempt)

            # 检测暴力破解
            brute_force_attacks = []

            # 检查同一IP多次尝试不同用户
            for ip, attempts_list in ip_attempts.items():
                unique_users = set(a.user for a in attempts_list)
                if len(unique_users) >= 3 and len(attempts_list) >= self.BRUTE_FORCE_THRESHOLD:
                    brute_force_attacks.append({
                        "type": "ip_based",
                        "source_ip": ip,
                        "attempt_count": len(attempts_list),
                        "target_users": list(unique_users),
                        "severity": RiskLevel.CRITICAL.value,
                        "description": f"IP {ip} 尝试暴力破解 {len(unique_users)} 个用户账户"
                    })

            # 检查同一用户被多次尝试
            for user, attempts_list in user_attempts.items():
                if len(attempts_list) >= self.BRUTE_FORCE_THRESHOLD:
                    unique_ips = set(a.host for a in attempts_list)
                    brute_force_attacks.append({
                        "type": "user_based",
                        "target_user": user,
                        "attempt_count": len(attempts_list),
                        "source_ips": list(unique_ips),
                        "severity": RiskLevel.HIGH.value,
                        "description": f"用户 {user} 遭受 {len(attempts_list)} 次暴力破解尝试"
                    })

            return create_success_response(
                data={
                    "attacks_detected": len(brute_force_attacks),
                    "attacks": brute_force_attacks,
                    "recommendations": [
                        "立即封锁检测到的攻击IP",
                        "检查被攻击账户的安全性",
                        "考虑启用账户锁定策略",
                        "实施登录失败延迟机制"
                    ] if brute_force_attacks else []
                },
                message=f"检测到 {len(brute_force_attacks)} 起暴力破解攻击" if brute_force_attacks else "未发现暴力破解攻击"
            )

        except Exception as e:
            logger.error(f"暴力破解检测失败: {e}")
            return create_error_response(
                f"检测失败: {str(e)}",
                ErrorCode.AUDIT_FAILED
            )

    def check_suspicious_ips(
        self,
        hours: int = 24
    ) -> Dict[str, Any]:
        """
        检查可疑IP地址

        参数:
            hours: 检查最近多少小时

        返回:
            Dict: 可疑IP列表
        """
        try:
            attempts = self._get_login_attempts(hours=hours, success_only=False)

            # 按IP统计
            ip_stats = defaultdict(lambda: {"success": 0, "failed": 0, "users": set()})

            for attempt in attempts:
                ip_stats[attempt.host]["success" if attempt.success else "failed"] += 1
                ip_stats[attempt.host]["users"].add(attempt.user)

            # 识别可疑IP
            suspicious_ips = []
            for ip, stats in ip_stats.items():
                total = stats["success"] + stats["failed"]
                failure_rate = stats["failed"] / total if total > 0 else 0

                # 失败率超过80%或尝试多个用户
                if failure_rate > 0.8 or len(stats["users"]) > 3:
                    suspicious_ips.append({
                        "ip": ip,
                        "total_attempts": total,
                        "failed_attempts": stats["failed"],
                        "success_attempts": stats["success"],
                        "failure_rate": round(failure_rate * 100, 2),
                        "unique_users": len(stats["users"]),
                        "severity": RiskLevel.HIGH.value if failure_rate > 0.9 else RiskLevel.MEDIUM.value
                    })

            # 按失败率排序
            suspicious_ips.sort(key=lambda x: x["failure_rate"], reverse=True)

            return create_success_response(
                data={
                    "suspicious_ip_count": len(suspicious_ips),
                    "suspicious_ips": suspicious_ips[:20],  # 只返回前20个
                    "recommendations": [
                        f"建议封锁IP: {ip['ip']}" for ip in suspicious_ips[:5]
                    ] if suspicious_ips else []
                },
                message=f"发现 {len(suspicious_ips)} 个可疑IP地址"
            )

        except Exception as e:
            logger.error(f"检查可疑IP失败: {e}")
            return create_error_response(
                f"检查失败: {str(e)}",
                ErrorCode.AUDIT_FAILED
            )

    def _get_login_attempts(
        self,
        hours: int = 24,
        success_only: Optional[bool] = None
    ) -> List[LoginAttempt]:
        """
        获取登录尝试记录

        参数:
            hours: 查询时间范围
            success_only: 是否只查询成功的登录

        返回:
            List[LoginAttempt]: 登录尝试列表
        """
        attempts = []

        try:
            if "mysql" in self.dialect:
                attempts = self._get_mysql_login_attempts(hours, success_only)
            elif "postgresql" in self.dialect:
                attempts = self._get_postgres_login_attempts(hours, success_only)
            elif "oracle" in self.dialect:
                attempts = self._get_oracle_login_attempts(hours, success_only)
            else:
                # 通用数据库支持：返回空列表并记录日志
                logger.info(
                    f"数据库类型 '{self.dialect}' 暂无专用登录监控实现，"
                    f"返回空列表"
                )

        except Exception as e:
            logger.error(f"获取登录记录失败: {e}")

        return attempts

    def _get_mysql_login_attempts(
        self,
        hours: int,
        success_only: Optional[bool]
    ) -> List[LoginAttempt]:
        """获取MySQL登录尝试记录"""
        attempts = []

        # 查询performance_schema中的连接信息
        try:
            result = self.connector.execute("""
                SELECT 
                    PROCESSLIST_USER as user,
                    PROCESSLIST_HOST as host,
                    PROCESSLIST_TIME as connection_time,
                    PROCESSLIST_COMMAND as command
                FROM performance_schema.threads
                WHERE PROCESSLIST_USER IS NOT NULL
                AND PROCESSLIST_COMMAND = 'Sleep'
                LIMIT 1000
            """)

            for row in result.rows or []:
                attempts.append(LoginAttempt(
                    user=row[0] or "unknown",
                    host=row[1] or "localhost",
                    attempt_time=datetime.now(),
                    success=True
                ))

        except Exception as e:
            logger.warning(f"无法从performance_schema获取登录信息: {e}")

        return attempts

    def _get_postgres_login_attempts(
        self,
        hours: int,
        success_only: Optional[bool]
    ) -> List[LoginAttempt]:
        """获取PostgreSQL登录尝试记录"""
        attempts = []

        try:
            # PostgreSQL需要通过日志分析，这里简化处理
            result = self.connector.execute("""
                SELECT 
                    usename as user,
                    client_addr as host,
                    backend_start as login_time
                FROM pg_stat_activity
                WHERE usename IS NOT NULL
                LIMIT 1000
            """)

            for row in result.rows or []:
                attempts.append(LoginAttempt(
                    user=row[0] or "unknown",
                    host=str(row[1]) if row[1] else "localhost",
                    attempt_time=row[2] if row[2] else datetime.now(),
                    success=True
                ))

        except Exception as e:
            logger.warning(f"无法获取PostgreSQL登录信息: {e}")

        return attempts

    def _get_oracle_login_attempts(
        self,
        hours: int,
        success_only: Optional[bool]
    ) -> List[LoginAttempt]:
        """获取Oracle登录尝试记录"""
        attempts = []

        try:
            result = self.connector.execute(f"""
                SELECT * FROM (
                    SELECT
                        username,
                        osuser,
                        machine,
                        logon_time
                    FROM v$session
                    WHERE username IS NOT NULL
                    AND logon_time > SYSDATE - {hours}/24
                    ORDER BY logon_time DESC
                )
                WHERE ROWNUM <= 1000
            """)

            for row in result.rows or []:
                logon_time = row[3]
                if logon_time and hasattr(logon_time, 'isoformat'):
                    attempt_time = logon_time
                else:
                    attempt_time = datetime.now()

                attempts.append(LoginAttempt(
                    user=str(row[0] or "unknown"),
                    host=str(row[2] or "localhost"),
                    attempt_time=attempt_time,
                    success=True
                ))

        except Exception as e:
            logger.warning(f"无法获取Oracle登录信息: {e}")

        return attempts

    def _analyze_failed_logins(self, failed_attempts: List[LoginAttempt]) -> Dict[str, Any]:
        """分析登录失败统计"""
        if not failed_attempts:
            return {"message": "无失败登录记录"}

        # 按用户统计
        user_failures = defaultdict(int)
        # 按IP统计
        ip_failures = defaultdict(int)
        # 按小时统计
        hourly_failures = defaultdict(int)

        for attempt in failed_attempts:
            user_failures[attempt.user] += 1
            ip_failures[attempt.host] += 1
            hour_key = attempt.attempt_time.strftime("%Y-%m-%d %H:00")
            hourly_failures[hour_key] += 1

        return {
            "top_users": sorted(user_failures.items(), key=lambda x: x[1], reverse=True)[:5],
            "top_ips": sorted(ip_failures.items(), key=lambda x: x[1], reverse=True)[:5],
            "hourly_distribution": dict(sorted(hourly_failures.items())[-24:])  # 最近24小时
        }

    def _generate_login_alerts(self, failed_attempts: List[LoginAttempt]) -> List[SecurityAlert]:
        """生成登录安全告警"""
        alerts = []

        if not failed_attempts:
            return alerts

        # 检查是否有大量失败登录
        if len(failed_attempts) > 100:
            alerts.append(SecurityAlert(
                alert_type="massive_login_failures",
                severity=RiskLevel.CRITICAL,
                description=f"检测到大量登录失败: {len(failed_attempts)} 次",
                recommendations=[
                    "检查是否有暴力破解攻击",
                    "审查账户安全策略",
                    "考虑实施IP封锁"
                ]
            ))

        # 检查是否有单个IP大量失败
        ip_failures = defaultdict(int)
        for attempt in failed_attempts:
            ip_failures[attempt.host] += 1

        for ip, count in ip_failures.items():
            if count > 20:
                alerts.append(SecurityAlert(
                    alert_type="suspicious_ip",
                    severity=RiskLevel.HIGH,
                    description=f"IP {ip} 有 {count} 次登录失败",
                    details={"ip": ip, "failure_count": count},
                    recommendations=[f"考虑封锁IP: {ip}"]
                ))

        return alerts

    def _alert_to_dict(self, alert: SecurityAlert) -> Dict[str, Any]:
        """将告警转换为字典"""
        return {
            "type": alert.alert_type,
            "severity": alert.severity.value,
            "description": alert.description,
            "details": alert.details,
            "detected_at": alert.detected_at.isoformat(),
            "recommendations": alert.recommendations
        }
