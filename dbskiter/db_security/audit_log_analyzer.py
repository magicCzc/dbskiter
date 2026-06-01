"""
db_security/audit_log_analyzer.py

文件功能：数据库审计日志分析，追踪用户操作、检测高危行为
主要类：
    - AuditLogAnalyzer: 审计日志分析器
    - AuditEvent: 审计事件
    - HighRiskOperation: 高危操作记录

使用示例:
    >>> from db_security.audit_log_analyzer import AuditLogAnalyzer
    >>> analyzer = AuditLogAnalyzer(connector)
    >>> result = analyzer.analyze_audit_log(hours=24)
    >>> high_risk = analyzer.detect_high_risk_operations()

版本: 3.1.0
作者: AI Assistant
创建时间: 2026-04-23
最后修改: 2026-04-23
"""

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
from collections import defaultdict

from dbskiter.shared.unified_connector import UnifiedConnector
from .models import RiskLevel, create_success_response, create_error_response, ErrorCode

logger = logging.getLogger(__name__)


@dataclass
class AuditEvent:
    """审计事件"""
    event_time: datetime
    user: str
    host: str
    action: str
    object_type: Optional[str] = None
    object_name: Optional[str] = None
    sql_text: Optional[str] = None
    status: str = "SUCCESS"  # SUCCESS/FAILED
    rows_affected: int = 0


@dataclass
class HighRiskOperation:
    """高危操作记录"""
    operation_type: str
    severity: RiskLevel
    user: str
    event_time: datetime
    description: str
    sql_text: Optional[str] = None
    recommendations: List[str] = field(default_factory=list)


class AuditLogAnalyzer:
    """
    审计日志分析器

    功能:
        - 分析数据库审计日志
        - 检测高危操作（DROP/DELETE/TRUNCATE等）
        - 追踪用户行为
        - 发现异常操作模式
        - 生成合规报告
    """

    # 高危SQL关键字
    HIGH_RISK_KEYWORDS = [
        "DROP", "TRUNCATE", "DELETE.*FROM", "UPDATE.*SET",
        "GRANT", "REVOKE", "ALTER.*USER", "CREATE.*USER",
        "DROP.*USER", "SHUTDOWN", "KILL"
    ]

    # 数据修改关键字
    DATA_MODIFICATION_KEYWORDS = [
        "INSERT", "UPDATE", "DELETE", "REPLACE"
    ]

    def __init__(self, connector: UnifiedConnector):
        """
        初始化审计日志分析器

        参数:
            connector: 数据库连接器
        """
        self.connector = connector
        self.dialect = connector.dialect.lower() if connector else "unknown"

    def analyze_audit_log(
        self,
        hours: int = 24,
        users: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        分析审计日志

        参数:
            hours: 分析最近多少小时
            users: 指定用户列表（None表示所有用户）

        返回:
            Dict: 审计分析结果
        """
        try:
            events = self._get_audit_events(hours=hours, users=users)

            # 统计分析
            stats = self._calculate_audit_stats(events)

            # 检测高危操作
            high_risk_ops = self._detect_high_risk_operations(events)

            # 检测异常行为
            anomalies = self._detect_behavior_anomalies(events)

            return create_success_response(
                data={
                    "total_events": len(events),
                    "time_range": f"最近{hours}小时",
                    "statistics": stats,
                    "high_risk_operations": [self._operation_to_dict(op) for op in high_risk_ops],
                    "anomalies": [self._anomaly_to_dict(a) for a in anomalies],
                    "user_activity": self._get_user_activity_summary(events),
                    "recommendations": self._generate_audit_recommendations(high_risk_ops, anomalies)
                },
                message=f"分析完成，发现 {len(high_risk_ops)} 个高危操作，{len(anomalies)} 个异常行为"
            )

        except Exception as e:
            logger.error(f"审计日志分析失败: {e}")
            return create_error_response(
                f"分析失败: {str(e)}",
                ErrorCode.AUDIT_FAILED
            )

    def detect_high_risk_operations(
        self,
        hours: int = 24,
        include_ddl: bool = True,
        include_dml: bool = True
    ) -> Dict[str, Any]:
        """
        检测高危操作

        参数:
            hours: 检查最近多少小时
            include_ddl: 包含DDL操作（DROP/ALTER等）
            include_dml: 包含DML操作（DELETE/UPDATE等）

        返回:
            Dict: 高危操作检测结果
        """
        try:
            events = self._get_audit_events(hours=hours)
            high_risk_ops = self._detect_high_risk_operations(events)

            # 分类统计
            ddl_ops = [op for op in high_risk_ops if op.operation_type in ["DROP", "TRUNCATE", "ALTER"]]
            dml_ops = [op for op in high_risk_ops if op.operation_type in ["DELETE", "UPDATE"]]
            permission_ops = [op for op in high_risk_ops if op.operation_type in ["GRANT", "REVOKE"]]

            return create_success_response(
                data={
                    "total_high_risk": len(high_risk_ops),
                    "ddl_operations": len(ddl_ops) if include_ddl else 0,
                    "dml_operations": len(dml_ops) if include_dml else 0,
                    "permission_changes": len(permission_ops),
                    "operations": [self._operation_to_dict(op) for op in high_risk_ops],
                    "critical_operations": [
                        self._operation_to_dict(op) for op in high_risk_ops
                        if op.severity == RiskLevel.CRITICAL
                    ]
                },
                message=f"检测到 {len(high_risk_ops)} 个高危操作"
            )

        except Exception as e:
            logger.error(f"高危操作检测失败: {e}")
            return create_error_response(
                f"检测失败: {str(e)}",
                ErrorCode.AUDIT_FAILED
            )

    def track_user_activity(
        self,
        user: str,
        hours: int = 24
    ) -> Dict[str, Any]:
        """
        追踪特定用户活动

        参数:
            user: 用户名
            hours: 追踪最近多少小时

        返回:
            Dict: 用户活动报告
        """
        try:
            events = self._get_audit_events(hours=hours, users=[user])

            if not events:
                return create_success_response(
                    data={"user": user, "events": []},
                    message=f"用户 {user} 在指定时间内无活动记录"
                )

            # 活动统计
            action_counts = defaultdict(int)
            table_access = defaultdict(int)
            hourly_activity = defaultdict(int)

            for event in events:
                action_counts[event.action] += 1
                if event.object_name:
                    table_access[event.object_name] += 1
                hour_key = event.event_time.strftime("%Y-%m-%d %H:00")
                hourly_activity[hour_key] += 1

            # 检测异常
            anomalies = self._detect_behavior_anomalies(events)

            return create_success_response(
                data={
                    "user": user,
                    "time_range": f"最近{hours}小时",
                    "total_events": len(events),
                    "action_breakdown": dict(action_counts),
                    "tables_accessed": dict(table_access),
                    "hourly_activity": dict(sorted(hourly_activity.items())),
                    "anomalies": [self._anomaly_to_dict(a) for a in anomalies],
                    "recent_events": [
                        {
                            "time": e.event_time.isoformat(),
                            "action": e.action,
                            "object": e.object_name,
                            "status": e.status
                        }
                        for e in events[:20]
                    ]
                },
                message=f"用户 {user} 活动追踪完成"
            )

        except Exception as e:
            logger.error(f"用户活动追踪失败: {e}")
            return create_error_response(
                f"追踪失败: {str(e)}",
                ErrorCode.AUDIT_FAILED
            )

    def _get_audit_events(
        self,
        hours: int = 24,
        users: Optional[List[str]] = None
    ) -> List[AuditEvent]:
        """
        获取审计事件

        参数:
            hours: 时间范围
            users: 指定用户

        返回:
            List[AuditEvent]: 审计事件列表
        """
        events = []

        try:
            if "mysql" in self.dialect:
                events = self._get_mysql_audit_events(hours, users)
            elif "postgresql" in self.dialect:
                events = self._get_postgres_audit_events(hours, users)
            elif "oracle" in self.dialect:
                events = self._get_oracle_audit_events(hours, users)
            else:
                logger.warning(f"不支持的数据库类型: {self.dialect}")

        except Exception as e:
            logger.error(f"获取审计事件失败: {e}")

        return events

    def _get_mysql_audit_events(
        self,
        hours: int,
        users: Optional[List[str]]
    ) -> List[AuditEvent]:
        """获取MySQL审计事件
        
        优先使用performance_schema（默认启用），
        回退到mysql.general_log（需要手动启用）
        """
        events = []
        
        # 首先尝试从performance_schema获取（默认启用）
        events = self._get_mysql_events_from_performance_schema(hours, users)
        
        # 如果performance_schema没有数据，尝试general_log
        if not events:
            events = self._get_mysql_events_from_general_log(hours, users)
        
        return events
    
    def _get_mysql_events_from_performance_schema(
        self,
        hours: int,
        users: Optional[List[str]]
    ) -> List[AuditEvent]:
        """从performance_schema获取SQL执行历史"""
        events = []
        
        try:
            # 检查performance_schema是否启用
            check_result = self.connector.execute("""
                SELECT COUNT(*) 
                FROM information_schema.tables 
                WHERE table_schema = 'performance_schema' 
                AND table_name = 'events_statements_history_long'
            """)
            
            if not check_result.rows or check_result.rows[0][0] == 0:
                logger.debug("performance_schema.events_statements_history_long表不存在")
                return events
            
            # 从performance_schema获取最近的SQL执行记录
            # 注意：使用字符串格式化而不是参数绑定，因为某些驱动对复杂SQL支持不好
            sql = f"""
                SELECT 
                    esh.TIMER_END as event_time,
                    esh.THREAD_ID,
                    esh.SQL_TEXT,
                    esh.DIGEST_TEXT as normalized_sql,
                    esh.EVENT_NAME as action,
                    t.PROCESSLIST_USER as user,
                    t.PROCESSLIST_HOST as host,
                    esh.ROWS_AFFECTED,
                    esh.ROWS_SENT,
                    esh.ROWS_EXAMINED,
                    esh.CREATED_TMP_TABLES,
                    esh.ERRORS,
                    esh.WARNINGS,
                    esh.LOCK_TIME / 1000000000000 as lock_time_sec
                FROM performance_schema.events_statements_history_long esh
                LEFT JOIN performance_schema.threads t ON esh.THREAD_ID = t.THREAD_ID
                WHERE esh.TIMER_END > DATE_SUB(NOW(), INTERVAL {hours} HOUR)
                AND esh.SQL_TEXT IS NOT NULL
                ORDER BY esh.TIMER_END DESC
                LIMIT 10000
            """
            result = self.connector.execute(sql)
            
            for row in result.rows:
                try:
                    user = row[5] or "system_user"
                    host = row[6] or "localhost"
                    
                    # 过滤用户
                    if users and user not in users:
                        continue
                    
                    # 提取SQL类型（SELECT/INSERT/UPDATE/DELETE等）
                    sql_text = row[2] or ""
                    action = self._extract_sql_type(sql_text)
                    
                    events.append(AuditEvent(
                        event_time=row[0] if row[0] else datetime.now(),
                        user=user,
                        host=host,
                        action=action,
                        sql_text=sql_text[:1000] if sql_text else None  # 限制长度
                    ))
                    
                except Exception as e:
                    logger.warning(f"解析performance_schema事件失败: {e}")
                    
        except Exception as e:
            logger.warning(f"无法从performance_schema获取事件: {e}")
        
        return events
    
    def _get_mysql_events_from_general_log(
        self,
        hours: int,
        users: Optional[List[str]]
    ) -> List[AuditEvent]:
        """从mysql.general_log获取事件（需要手动启用）"""
        events = []
        
        try:
            # 检查general_log是否启用
            check_result = self.connector.execute("""
                SELECT @@general_log
            """)
            
            if not check_result.rows or check_result.rows[0][0] != 1:
                logger.debug("general_log未启用")
                return events
            
            sql = f"""
                SELECT 
                    event_time,
                    user_host,
                    command_type,
                    argument
                FROM mysql.general_log
                WHERE event_time > DATE_SUB(NOW(), INTERVAL {hours} HOUR)
                ORDER BY event_time DESC
                LIMIT 10000
            """
            result = self.connector.execute(sql)

            for row in result.rows:
                try:
                    # 解析user_host格式: "user[host]"
                    user_host = row[1] or ""
                    user_match = re.match(r"([^[]+)\[([^]]*)\]", user_host)
                    user = user_match.group(1) if user_match else user_host
                    host = user_match.group(2) if user_match else "localhost"

                    # 过滤用户
                    if users and user not in users:
                        continue

                    events.append(AuditEvent(
                        event_time=row[0] if row[0] else datetime.now(),
                        user=user,
                        host=host,
                        action=row[2] or "UNKNOWN",
                        sql_text=row[3] if len(row) > 3 else None
                    ))

                except Exception as e:
                    logger.warning(f"解析general_log事件失败: {e}")

        except Exception as e:
            logger.warning(f"无法从general_log获取事件: {e}")

        return events
    
    def _extract_sql_type(self, sql: str) -> str:
        """从SQL中提取操作类型"""
        if not sql:
            return "UNKNOWN"
        
        sql_upper = sql.strip().upper()
        
        # 高危操作
        if sql_upper.startswith("DROP "):
            return "DROP"
        elif sql_upper.startswith("TRUNCATE "):
            return "TRUNCATE"
        elif sql_upper.startswith("DELETE "):
            return "DELETE"
        elif sql_upper.startswith("UPDATE "):
            return "UPDATE"
        elif sql_upper.startswith("GRANT "):
            return "GRANT"
        elif sql_upper.startswith("REVOKE "):
            return "REVOKE"
        elif sql_upper.startswith("ALTER "):
            return "ALTER"
        # 普通操作
        elif sql_upper.startswith("SELECT "):
            return "SELECT"
        elif sql_upper.startswith("INSERT "):
            return "INSERT"
        elif sql_upper.startswith("CREATE "):
            return "CREATE"
        else:
            return "OTHER"

    def _get_postgres_audit_events(
        self,
        hours: int,
        users: Optional[List[str]]
    ) -> List[AuditEvent]:
        """获取PostgreSQL审计事件"""
        events = []

        try:
            # PostgreSQL需要通过pgAudit扩展或日志分析
            result = self.connector.execute("""
                SELECT 
                    query_start as event_time,
                    usename as user,
                    client_addr as host,
                    state as action,
                    query as sql_text
                FROM pg_stat_activity
                WHERE query_start > NOW() - INTERVAL ':hours hours'
                AND query IS NOT NULL
                ORDER BY query_start DESC
                LIMIT 10000
            """, {"hours": hours})

            for row in result.rows:
                user = row[1] or "unknown"
                if users and user not in users:
                    continue

                events.append(AuditEvent(
                    event_time=row[0] if row[0] else datetime.now(),
                    user=user,
                    host=str(row[2]) if row[2] else "localhost",
                    action=row[3] or "QUERY",
                    sql_text=row[4]
                ))

        except Exception as e:
            logger.warning(f"无法获取PostgreSQL审计日志: {e}")

        return events

    def _get_oracle_audit_events(
        self,
        hours: int,
        users: Optional[List[str]]
    ) -> List[AuditEvent]:
        """获取Oracle审计事件"""
        events = []

        try:
            result = self.connector.execute(f"""
                SELECT * FROM (
                    SELECT
                        timestamp# AS event_time,
                        userid AS user_name,
                        terminal AS host,
                        action# AS action,
                        obj$name AS object_name
                    FROM sys.aud$
                    WHERE timestamp# > SYSDATE - {hours}/24
                    ORDER BY timestamp# DESC
                )
                WHERE ROWNUM <= 10000
            """)

            for row in result.rows:
                user = str(row[1] or "unknown")
                if users and user not in users:
                    continue

                event_time = row[0]
                if event_time and hasattr(event_time, 'isoformat'):
                    pass
                else:
                    event_time = datetime.now()

                events.append(AuditEvent(
                    event_time=event_time,
                    user=user,
                    host=str(row[2] or "localhost"),
                    action=self._map_oracle_action(int(str(row[3])) if row[3] else 0),
                    object_name=str(row[4] or "")
                ))

        except Exception as e:
            logger.warning(f"无法获取Oracle审计日志（审计可能未启用）: {e}")

        return events

    def _map_oracle_action(self, action_code: int) -> str:
        """映射Oracle操作代码"""
        action_map = {
            1: "CREATE", 2: "INSERT", 3: "SELECT", 6: "UPDATE",
            7: "DELETE", 8: "DROP", 9: "CREATE", 12: "DROP",
            100: "LOGON", 101: "LOGOFF", 102: "LOGOFF BY CLEANUP"
        }
        return action_map.get(action_code, f"ACTION_{action_code}")

    def _calculate_audit_stats(self, events: List[AuditEvent]) -> Dict[str, Any]:
        """计算审计统计"""
        if not events:
            return {"message": "无审计事件"}

        # 按操作类型统计
        action_counts = defaultdict(int)
        # 按用户统计
        user_counts = defaultdict(int)
        # 按状态统计
        status_counts = defaultdict(int)

        for event in events:
            action_counts[event.action] += 1
            user_counts[event.user] += 1
            status_counts[event.status] += 1

        return {
            "total_events": len(events),
            "unique_users": len(user_counts),
            "action_distribution": dict(action_counts),
            "top_users": sorted(user_counts.items(), key=lambda x: x[1], reverse=True)[:10],
            "status_summary": dict(status_counts)
        }

    def _detect_high_risk_operations(self, events: List[AuditEvent]) -> List[HighRiskOperation]:
        """检测高危操作"""
        high_risk_ops = []

        for event in events:
            if not event.sql_text:
                continue

            sql_upper = event.sql_text.upper()

            # 检查高危关键字
            for keyword in self.HIGH_RISK_KEYWORDS:
                if re.search(keyword, sql_upper):
                    severity = RiskLevel.CRITICAL if "DROP" in keyword or "TRUNCATE" in keyword else RiskLevel.HIGH

                    high_risk_ops.append(HighRiskOperation(
                        operation_type=keyword.replace(".*", "").replace(" ", "_"),
                        severity=severity,
                        user=event.user,
                        event_time=event.event_time,
                        description=f"用户 {event.user} 执行了高危操作",
                        sql_text=event.sql_text[:200],  # 限制长度
                        recommendations=[
                            "立即审查该操作是否授权",
                            "检查数据完整性",
                            "评估是否需要恢复操作"
                        ]
                    ))
                    break  # 一个事件只记录一次

        return high_risk_ops

    def _detect_behavior_anomalies(self, events: List[AuditEvent]) -> List[Dict[str, Any]]:
        """检测行为异常"""
        anomalies = []

        if not events:
            return anomalies

        # 按用户分析行为模式
        user_events = defaultdict(list)
        for event in events:
            user_events[event.user].append(event)

        for user, user_event_list in user_events.items():
            # 检测非工作时间操作
            off_hour_events = [
                e for e in user_event_list
                if e.event_time.hour < 8 or e.event_time.hour > 20
            ]

            if len(off_hour_events) > 10:
                anomalies.append({
                    "type": "off_hours_activity",
                    "user": user,
                    "severity": RiskLevel.MEDIUM.value,
                    "description": f"用户 {user} 在非工作时间有大量操作 ({len(off_hour_events)} 次)",
                    "recommendation": "审查是否为正常业务需求"
                })

            # 检测大量数据操作
            high_volume_events = [
                e for e in user_event_list
                if e.rows_affected > 10000
            ]

            if high_volume_events:
                anomalies.append({
                    "type": "high_volume_operation",
                    "user": user,
                    "severity": RiskLevel.HIGH.value,
                    "description": f"用户 {user} 执行了大量数据操作",
                    "recommendation": "确认是否为预期的大规模数据变更"
                })

        return anomalies

    def _get_user_activity_summary(self, events: List[AuditEvent]) -> Dict[str, Any]:
        """获取用户活动摘要"""
        user_activity = defaultdict(lambda: {"actions": set(), "event_count": 0})

        for event in events:
            user_activity[event.user]["actions"].add(event.action)
            user_activity[event.user]["event_count"] += 1

        return {
            user: {
                "actions": list(data["actions"]),
                "event_count": data["event_count"]
            }
            for user, data in user_activity.items()
        }

    def _generate_audit_recommendations(
        self,
        high_risk_ops: List[HighRiskOperation],
        anomalies: List[Dict[str, Any]]
    ) -> List[str]:
        """生成审计建议"""
        recommendations = []

        if high_risk_ops:
            recommendations.append("立即审查所有高危操作")
            recommendations.append("考虑启用更严格的审计策略")

        if anomalies:
            recommendations.append("调查检测到的异常行为")

        if not recommendations:
            recommendations.append("审计日志正常，继续保持")

        return recommendations

    def _operation_to_dict(self, op: HighRiskOperation) -> Dict[str, Any]:
        """将高危操作转换为字典"""
        return {
            "operation_type": op.operation_type,
            "severity": op.severity.value,
            "user": op.user,
            "event_time": op.event_time.isoformat(),
            "description": op.description,
            "sql_text": op.sql_text,
            "recommendations": op.recommendations
        }

    def _anomaly_to_dict(self, anomaly: Dict[str, Any]) -> Dict[str, Any]:
        """将异常转换为字典"""
        return anomaly
