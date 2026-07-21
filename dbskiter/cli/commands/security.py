"""
cli/commands/security.py

数据库安全命令 - 简化版
核心功能：安全审计、SQL注入检测、敏感数据扫描、安全评分、权限审计
"""

import json
from argparse import ArgumentParser
from typing import Any, Dict, Optional

from .base import BaseCommand


class SecurityCommand(BaseCommand):
    """数据库安全命令"""
    
    name = "security"
    description = "Database Security - 安全审计"
    help_text = "安全审计、SQL注入检测、敏感数据扫描"
    
    @classmethod
    def add_arguments(cls, parser: ArgumentParser) -> None:
        """添加安全命令参数"""
        parser.epilog = """
示例:
  dbskiter --database=jump security audit                    # 完整安全审计
  dbskiter --database=jump security score                    # 计算安全评分
  dbskiter --database=jump security permissions              # 审计用户权限
  dbskiter --database=jump security sql-injection "SELECT * FROM users WHERE name = 'test'"
  dbskiter --database=jump security sensitive-data --tables=users,orders
  dbskiter --database=jump security weak-passwords           # 检测弱密码
  dbskiter --database=jump security high-risk --hours=48     # 检测48小时内高危操作
        """
        subparsers = parser.add_subparsers(dest="security_action", help="安全操作")
        
        # ==================== 核心命令（只保留5个） ====================
        
        # audit 子命令
        subparsers.add_parser("audit", help="完整安全审计")
        
        # sql-injection 子命令
        injection_parser = subparsers.add_parser("sql-injection", help="SQL注入检测")
        injection_parser.add_argument("sql", help="SQL语句")
        injection_parser.add_argument("--params", help="SQL参数（JSON格式）")
        
        # sensitive-data 子命令
        sensitive_parser = subparsers.add_parser("sensitive-data", help="敏感数据扫描")
        sensitive_parser.add_argument("--tables", help="指定表（逗号分隔）")
        sensitive_parser.add_argument("--sample-size", type=int, default=100, help="采样大小")
        
        # score 子命令
        subparsers.add_parser("score", help="安全评分")
        
        # permissions 子命令
        subparsers.add_parser("permissions", help="权限审计")

        # login-security 子命令 - 登录安全监控
        login_parser = subparsers.add_parser("login-security", help="登录安全监控")
        login_parser.add_argument("--hours", type=int, default=24, help="检查最近多少小时")

        # audit-log 子命令 - 审计日志分析
        audit_parser = subparsers.add_parser("audit-log", help="审计日志分析")
        audit_parser.add_argument("--hours", type=int, default=24, help="分析最近多少小时")
        audit_parser.add_argument("--users", help="指定用户（逗号分隔）")

        # high-risk 子命令 - 高危操作检测
        highrisk_parser = subparsers.add_parser("high-risk", help="高危操作检测")
        highrisk_parser.add_argument("--hours", type=int, default=24, help="检查最近多少小时")

        # password-policy 子命令 - 密码策略检查
        subparsers.add_parser("password-policy", help="密码策略检查")

        # weak-passwords 子命令 - 弱密码检查
        subparsers.add_parser("weak-passwords", help="弱密码检查")
        
        # config 子命令 - 配置安全审计
        subparsers.add_parser("config", help="数据库配置安全审计")
    
    def execute(self) -> int:
        """执行安全命令"""
        from dbskiter.db_security import SecuritySkill

        # 确保数据库连接可用
        try:
            self.require_connector()
        except Exception as e:
            self.output.error(str(e))
            return 1

        try:
            skill = SecuritySkill(self.connector)

            action = getattr(self.args, 'security_action', None)

            if self.output_mode != "rule":
                method_map = {
                    "audit": lambda: skill.full_audit(),
                    "sql-injection": lambda: skill.detect_sql_injection(self.args.sql),
                    "sensitive-data": lambda: skill.scan_sensitive_data(
                        tables=self.args.tables.split(',') if getattr(self.args, 'tables', None) else None,
                        sample_size=getattr(self.args, 'sample_size', 100),
                    ),
                    "score": lambda: skill.calculate_security_score(),
                    "permissions": lambda: skill.audit_permissions(),
                    "login-security": lambda: skill.check_login_security(
                        hours=getattr(self.args, 'hours', 24),
                    ),
                    "audit-log": lambda: skill.analyze_audit_log(
                        hours=getattr(self.args, 'hours', 24),
                        users=getattr(self.args, 'users', '').split(',') if getattr(self.args, 'users', None) else None,
                    ),
                    "high-risk": lambda: skill.detect_high_risk_operations(
                        hours=getattr(self.args, 'hours', 24),
                    ),
                    "password-policy": lambda: skill.check_password_policy(),
                    "weak-passwords": lambda: skill.find_weak_passwords(),
                    "config": lambda: skill.audit_config(),
                }
                scenario_map = {
                    "audit": "security",
                    "sql-injection": "sql_injection",
                    "sensitive-data": "sensitive_data",
                    "score": "security_score",
                    "permissions": "permissions",
                    "login-security": "login_security",
                    "audit-log": "audit_log",
                    "high-risk": "high_risk",
                    "password-policy": "password_policy",
                    "weak-passwords": "weak_passwords",
                    "config": "config_security",
                }
                return self._execute_ai_mode(skill, action, method_map, scenario_map)

            # 安全命令路由
            if action == "audit":
                return self._full_audit(skill)
            elif action == "sql-injection":
                return self._check_injection(skill)
            elif action == "sensitive-data":
                return self._scan_sensitive_data(skill)
            elif action == "score":
                return self._get_security_score(skill)
            elif action == "permissions":
                return self._audit_permissions(skill)
            elif action == "login-security":
                return self._check_login_security(skill)
            elif action == "audit-log":
                return self._analyze_audit_log(skill)
            elif action == "high-risk":
                return self._detect_high_risk(skill)
            elif action == "password-policy":
                return self._check_password_policy(skill)
            elif action == "weak-passwords":
                return self._check_weak_passwords(skill)
            elif action == "config":
                return self._audit_config(skill)
            else:
                self.output.error("请指定安全操作: audit, sql-injection, sensitive-data, score, permissions, login-security, audit-log, high-risk, password-policy, weak-passwords, config")
                return 1
                
        except Exception as e:
            self.output.error(f"安全审计失败: {e}")
            return 1
        finally:
            skill.close()
    
    def _full_audit(self, skill) -> int:
        """完整安全审计"""
        result = skill.full_audit()

        # 检查是否成功
        if not result.get('success'):
            self.output.error(f"安全审计失败: {result.get('message', '未知错误')}")
            return 1

        # 获取数据（标准响应格式）
        audit_result = result.get('data', {})

        score = audit_result.get('overall_score', 0)
        level = audit_result.get('grade', 'unknown')
        risk_summary = audit_result.get('risk_summary', {})
        risk_count = risk_summary.get('total', 0)
        failed_modules = audit_result.get('failed_modules', [])

        # 如果有模块检测失败，显示明确警告
        if failed_modules:
            self.output.error(f"\n{'='*60}")
            self.output.error(f"  ⚠ 部分检测模块执行失败")
            self.output.error(f"{'='*60}")
            self.output.error(f"  失败模块: {', '.join(failed_modules)}")
            self.output.error(f"  安全评分可能不准确，请检查数据库连接和权限")
            self.output.error(f"{'='*60}")

        summary = f"安全评分{score}分（{level}级），发现{risk_count}个风险项"

        self.output.print(f"\n{'='*60}")
        self.output.print(f"摘要: {summary}")
        self.output.print(f"{'='*60}")

        self.output.print(f"\n数据库安全审计报告")
        self.output.print(f"审计时间: {audit_result.get('audit_time', '')}")

        # 安全评分
        if failed_modules:
            # 有模块失败时，即使评分高也显示为警告
            self.output.error(f"\n安全评分: {score}/100 - {level}级（部分检测失败，结果不准确）")
        elif score >= 90:
            self.output.success(f"\n安全评分: {score}/100 - {level}级")
        elif score >= 80:
            self.output.warning(f"\n安全评分: {score}/100 - {level}级")
        elif score >= 70:
            self.output.warning(f"\n安全评分: {score}/100 - {level}级（需要改进）")
        else:
            self.output.error(f"\n安全评分: {score}/100 - {level}级（存在严重风险）")

        # 风险摘要
        total_risks = risk_summary.get('total', 0) if risk_summary else 0
        if total_risks == 0 and not failed_modules:
            self.output.success(f"\n风险统计: 正常（未发现风险）")
        elif failed_modules:
            self.output.error(f"\n风险统计: 部分检测失败（{len(failed_modules)} 个模块未执行）")
        else:
            self.output.print(f"\n风险统计:")
            critical = risk_summary.get('critical', 0)
            high = risk_summary.get('high', 0)
            medium = risk_summary.get('medium', 0)
            low = risk_summary.get('low', 0)

            if critical > 0:
                self.output.error(f"  严重: {critical} 个")
            else:
                self.output.print(f"  严重: 0 个")

            if high > 0:
                self.output.warning(f"  高危: {high} 个")
            else:
                self.output.print(f"  高危: 0 个")

            self.output.print(f"  中危: {medium} 个")
            self.output.print(f"  低危: {low} 个")

        # 扣分项
        deductions = audit_result.get('deductions', [])
        if deductions:
            self.output.warning(f"\n主要问题:")
            for deduction in deductions[:10]:  # 只显示前10个
                self.output.print(f"  - {deduction}")

        # 模块详情
        modules = audit_result.get('modules', {})
        if modules:
            self.output.print(f"\n审计模块详情:")
            for module_name, module_result in modules.items():
                if isinstance(module_result, dict):
                    # 获取实际数据（处理标准响应格式）
                    if 'success' in module_result and 'data' in module_result:
                        # 标准响应格式: {"success": true, "data": {...}}
                        status = "完成" if module_result.get('success') else "失败"
                        actual_data = module_result.get('data', {})
                        message = module_result.get('message', '')
                    elif 'status' in module_result:
                        # 直接数据格式: {"status": "success", ...}
                        status_map = {
                            'success': '完成',
                            'failed': '失败',
                            'completed': '完成',
                            'error': '错误'
                        }
                        status = status_map.get(module_result.get('status'), '未知')
                        actual_data = module_result
                        message = module_result.get('message', '')
                    else:
                        status = '完成'
                        actual_data = module_result
                        message = ''

                    # 显示模块执行详情
                    self.output.print(f"\n  [{module_name}] 状态: {status}")

                    # 显示检查数量（从actual_data中读取）
                    total_checked = actual_data.get('total_checked', 0)
                    if total_checked > 0:
                        self.output.print(f"    检查数量: {total_checked}")

                    risks_found = actual_data.get('risks_found', -1)
                    if risks_found >= 0:
                        if risks_found > 0:
                            self.output.warning(f"    发现风险: {risks_found} 个")
                        else:
                            self.output.print(f"    发现风险: {risks_found} 个")

                    # 显示消息
                    if message:
                        self.output.print(f"    详情: {message}")

                    # 显示备注
                    note = actual_data.get('note', '')
                    if note:
                        self.output.print(f"    备注: {note}")

        return 0
    
    def _check_injection(self, skill) -> int:
        """SQL注入检测"""
        params = None
        if self.args.params:
            params = json.loads(self.args.params)
        
        result = skill.detect_sql_injection(self.args.sql, params)
        
        # 检查是否成功
        if not result.get('success'):
            self.output.error(f"SQL注入检测失败: {result.get('message', '未知错误')}")
            return 1
        
        # 获取数据（标准响应格式）
        data = result.get('data', {})
        
        risk_score = data.get('risk_score', 0)
        
        # 从 findings 中提取最高风险等级
        findings = data.get('findings', [])
        if findings:
            level_priority = {'critical': 4, 'high': 3, 'medium': 2, 'low': 1}
            level = max(
                (f.get('risk_level', 'unknown') for f in findings),
                key=lambda x: level_priority.get(x, 0)
            )
        else:
            level = 'safe'
        
        summary = f"风险评分{risk_score}分（{level}级）"
        
        self.output.print(f"\n{'='*60}")
        self.output.print(f"摘要: {summary}")
        self.output.print(f"{'='*60}")
        
        self.output.print(f"\nSQL注入检测")
        self.output.print(f"SQL: {self.args.sql}")
        
        if risk_score >= 70:
            self.output.error(f"\n风险评分: {risk_score}/100 - {level}级")
        elif risk_score >= 40:
            self.output.warning(f"\n风险评分: {risk_score}/100 - {level}级")
        else:
            self.output.success(f"\n风险评分: {risk_score}/100 - {level}级")
        
        # 注入类型
        injection_types = data.get('injection_types', [])
        if injection_types:
            self.output.warning(f"\n检测到注入类型:")
            for itype in injection_types:
                self.output.warning(f"  - {itype}")
        
        # 建议
        suggestions = data.get('recommendation', '')
        if suggestions:
            self.output.print(f"\n建议:")
            self.output.print(f"  {suggestions}")
        
        # 安全示例
        if data.get('safe_example'):
            self.output.print(f"\n安全写法示例:")
            self.output.print(f"  {data['safe_example']}")
        
        return 0
    
    def _scan_sensitive_data(self, skill) -> int:
        """敏感数据扫描"""
        tables = self.args.tables.split(',') if self.args.tables else None
        result = skill.scan_sensitive_data(tables=tables, sample_size=self.args.sample_size)

        # 保存结果供 --show-trace 追踪展示
        self._last_skill_result = result

        # 检查是否成功
        if not result.get('success'):
            self.output.error(f"敏感数据扫描失败: {result.get('message', '未知错误')}")
            return 1

        # 获取数据（标准响应格式）
        data = result.get('data', {})

        # 处理scan_all_tables返回的格式
        if 'total_findings' in data:
            total = data.get('total_findings', 0)
            critical = len(data.get('critical_findings', []))
            high = len(data.get('high_findings', []))
            scanned_tables = data.get('total_tables', 0)
            findings = data.get('all_findings', [])
        else:
            # 处理scan返回的格式
            summary = data.get('summary', {})
            total = summary.get('total', 0)
            by_level = summary.get('by_level', {})
            critical = by_level.get('critical', 0)
            high = by_level.get('high', 0)
            scanned_tables = data.get('tables_scanned', 0)
            findings = data.get('findings', [])

        summary_text = f"发现{total}个敏感字段（{critical}个严重，{high}个高危）"

        self.output.print(f"\n{'='*60}")
        self.output.print(f"摘要: {summary_text}")
        self.output.print(f"{'='*60}")

        self.output.print(f"\n敏感数据扫描结果")
        self.output.print(f"扫描表数: {scanned_tables}")
        self.output.print(f"总发现: {total}个")
        self.output.print(f"严重: {critical}个")
        self.output.print(f"高危: {high}个")

        # 详细发现
        if findings:
            self.output.warning(f"\n详细发现 (前10个):")
            for i, finding in enumerate(findings[:10], 1):
                # 支持两种字段名格式（to_dict返回的是table_name/column_name）
                severity = finding.get('sensitivity_level') or finding.get('level') or finding.get('severity', 'unknown')
                severity = severity.upper()
                table = finding.get('table_name') or finding.get('table', 'unknown')
                column = finding.get('column_name') or finding.get('column', 'unknown')
                data_type = finding.get('category') or finding.get('type', 'unknown')
                confidence = finding.get('confidence', 0)

                if severity == 'CRITICAL':
                    self.output.error(f"  [{i}] [{severity}] {table}.{column}: {data_type} (置信度: {confidence:.0%})")
                elif severity == 'HIGH':
                    self.output.warning(f"  [{i}] [{severity}] {table}.{column}: {data_type} (置信度: {confidence:.0%})")
                else:
                    self.output.print(f"  [{i}] [{severity}] {table}.{column}: {data_type} (置信度: {confidence:.0%})")

                suggestion = finding.get('recommendation') or finding.get('suggestion') or finding.get('remediation', '')
                if suggestion:
                    self.output.print(f"      建议: {suggestion}")

        return 0
    
    def _get_security_score(self, skill) -> int:
        """获取安全评分"""
        score_result = skill.calculate_security_score()
        
        score = score_result.get('overall_score', 0)
        level = score_result.get('grade', 'N/A')
        
        summary = f"安全评分{score}分（{level}级）"
        
        self.output.print(f"\n{'='*60}")
        self.output.print(f"摘要: {summary}")
        self.output.print(f"{'='*60}")
        
        self.output.print(f"\n数据库安全评分")
        
        if score >= 90:
            self.output.success(f"\n总体评分: {score}/100 - {level}级（优秀）")
        elif score >= 80:
            self.output.warning(f"\n总体评分: {score}/100 - {level}级（良好）")
        elif score >= 70:
            self.output.warning(f"\n总体评分: {score}/100 - {level}级（一般）")
        else:
            self.output.error(f"\n总体评分: {score}/100 - {level}级（差）")
        
        # 各维度得分
        dimensions = score_result.get('dimensions', {})
        if dimensions:
            self.output.print(f"\n详细评分:")
            for dim, dim_score in dimensions.items():
                self.output.print(f"  {dim}: {dim_score}分")
        
        # 扣分项
        deductions = score_result.get('deductions', [])
        if deductions:
            self.output.warning(f"\n扣分项:")
            for deduction in deductions:
                self.output.warning(f"  - {deduction}")
        
        return 0
    
    def _audit_permissions(self, skill) -> int:
        """权限审计"""
        perm_result = skill.audit_permissions()

        data = perm_result.get('data', {})
        total_users = data.get('total_users', 0)
        risks = data.get('risks', [])
        high_privilege_users = data.get('high_privilege_users', 0)
        message = data.get('message', perm_result.get('message', ''))

        summary = message if message else f"审计{total_users}个用户，发现{len(risks)}个风险"

        self.output.print(f"\n{'='*60}")
        self.output.print(f"摘要: {summary}")
        self.output.print(f"{'='*60}")

        self.output.print(f"\n权限审计结果")
        self.output.print(f"用户数: {total_users}")
        if high_privilege_users > 0:
            self.output.print(f"高权限用户: {high_privilege_users}")

        if risks:
            self.output.warning(f"\n发现 {len(risks)} 个风险:")
            for i, risk in enumerate(risks, 1):
                severity = risk.get('severity', 'unknown')
                desc = risk.get('description', '')
                self.output.warning(f"  [{i}] [{severity.upper()}] {desc}")

        return 0

    def _check_login_security(self, skill) -> int:
        """登录安全监控"""
        hours = getattr(self.args, 'hours', 24)
        result = skill.check_login_security(hours=hours)

        if not result.get('success'):
            self.output.error(f"登录安全检查失败: {result.get('message', '未知错误')}")
            return 1

        data = result.get('data', {})
        failed_logins = data.get('failed_logins', {})
        brute_force = data.get('brute_force', {})
        suspicious_ips = data.get('suspicious_ips', {})

        # 摘要
        failed_count = failed_logins.get('failed_attempts', 0)
        attack_count = brute_force.get('attacks_detected', 0)
        ip_count = suspicious_ips.get('suspicious_ip_count', 0)

        summary = f"发现{failed_count}次登录失败，{attack_count}起暴力破解，{ip_count}个可疑IP"

        self.output.print(f"\n{'='*60}")
        self.output.print(f"摘要: {summary}")
        self.output.print(f"{'='*60}")

        # 登录失败统计
        if failed_count > 0:
            self.output.warning(f"\n登录失败统计:")
            self.output.print(f"  总尝试: {failed_logins.get('total_attempts', 0)}")
            self.output.print(f"  失败次数: {failed_count}")
            self.output.print(f"  失败率: {failed_logins.get('failure_rate', 0)}%")

            # 显示告警
            alerts = failed_logins.get('alerts', [])
            if alerts:
                self.output.error(f"\n安全告警 ({len(alerts)}个):")
                for alert in alerts[:5]:
                    severity = alert.get('severity', 'unknown')
                    desc = alert.get('description', '')
                    if severity == 'CRITICAL':
                        self.output.error(f"  [严重] {desc}")
                    elif severity == 'HIGH':
                        self.output.warning(f"  [高危] {desc}")
                    else:
                        self.output.print(f"  [提示] {desc}")

        # 暴力破解检测
        if attack_count > 0:
            self.output.error(f"\n暴力破解攻击 ({attack_count}起):")
            attacks = brute_force.get('attacks', [])
            for attack in attacks[:5]:
                attack_type = attack.get('type', 'unknown')
                desc = attack.get('description', '')
                self.output.error(f"  - {desc}")

        # 可疑IP
        if ip_count > 0:
            self.output.warning(f"\n可疑IP地址 ({ip_count}个):")
            ips = suspicious_ips.get('suspicious_ips', [])
            for ip_info in ips[:5]:
                ip = ip_info.get('ip', 'unknown')
                failure_rate = ip_info.get('failure_rate', 0)
                self.output.warning(f"  - {ip} (失败率: {failure_rate}%)")

        return 0

    def _analyze_audit_log(self, skill) -> int:
        """审计日志分析"""
        hours = getattr(self.args, 'hours', 24)
        users = getattr(self.args, 'users', None)
        if users:
            users = users.split(',')

        result = skill.analyze_audit_log(hours=hours, users=users)

        if not result.get('success'):
            self.output.error(f"审计日志分析失败: {result.get('message', '未知错误')}")
            return 1

        data = result.get('data', {})
        total_events = data.get('total_events', 0)
        high_risk_count = len(data.get('high_risk_operations', []))
        anomaly_count = len(data.get('anomalies', []))

        summary = f"分析{total_events}个事件，发现{high_risk_count}个高危操作，{anomaly_count}个异常"

        self.output.print(f"\n{'='*60}")
        self.output.print(f"摘要: {summary}")
        self.output.print(f"{'='*60}")

        # 统计信息
        stats = data.get('statistics', {})
        if stats:
            self.output.print(f"\n审计统计:")
            self.output.print(f"  总事件: {stats.get('total_events', 0)}")
            self.output.print(f"  用户数: {stats.get('unique_users', 0)}")

        # 高危操作
        high_risk_ops = data.get('high_risk_operations', [])
        if high_risk_ops:
            self.output.error(f"\n高危操作 ({len(high_risk_ops)}个):")
            for op in high_risk_ops[:5]:
                op_type = op.get('operation_type', 'unknown')
                user = op.get('user', 'unknown')
                severity = op.get('severity', 'unknown')
                desc = op.get('description', '')

                if severity == 'CRITICAL':
                    self.output.error(f"  [严重] {op_type} - {desc}")
                else:
                    self.output.warning(f"  [高危] {op_type} - {desc}")

        # 异常行为
        anomalies = data.get('anomalies', [])
        if anomalies:
            self.output.warning(f"\n异常行为 ({len(anomalies)}个):")
            for anomaly in anomalies[:5]:
                anomaly_type = anomaly.get('type', 'unknown')
                desc = anomaly.get('description', '')
                self.output.warning(f"  - {desc}")

        return 0

    def _detect_high_risk(self, skill) -> int:
        """高危操作检测"""
        hours = getattr(self.args, 'hours', 24)
        result = skill.detect_high_risk_operations(hours=hours)

        if not result.get('success'):
            self.output.error(f"高危操作检测失败: {result.get('message', '未知错误')}")
            return 1

        data = result.get('data', {})
        total = data.get('total_high_risk', 0)
        ddl = data.get('ddl_operations', 0)
        dml = data.get('dml_operations', 0)
        permission = data.get('permission_changes', 0)

        summary = f"发现{total}个高危操作（DDL:{ddl}, DML:{dml}, 权限:{permission}）"

        self.output.print(f"\n{'='*60}")
        self.output.print(f"摘要: {summary}")
        self.output.print(f"{'='*60}")

        # 高危操作列表
        operations = data.get('operations', [])
        if operations:
            self.output.error(f"\n高危操作列表:")
            for op in operations[:10]:
                op_type = op.get('operation_type', 'unknown')
                user = op.get('user', 'unknown')
                severity = op.get('severity', 'unknown')
                time = op.get('event_time', '')

                if severity == 'CRITICAL':
                    self.output.error(f"  [严重] {op_type} by {user} at {time}")
                else:
                    self.output.warning(f"  [高危] {op_type} by {user} at {time}")

                # 显示SQL片段
                sql = op.get('sql_text', '')
                if sql:
                    self.output.print(f"    SQL: {sql[:100]}...")
        else:
            self.output.success(f"\n未发现高危操作")

        return 0

    def _check_password_policy(self, skill) -> int:
        """密码策略检查"""
        result = skill.check_password_policy()

        if not result.get('success'):
            self.output.error(f"密码策略检查失败: {result.get('message', '未知错误')}")
            return 1

        data = result.get('data', {})
        score = data.get('security_score', 0)
        risk_level = data.get('risk_level', 'unknown')
        total_users = data.get('total_users', 0)

        summary = f"安全评分{score}分（{risk_level}风险），共{total_users}个用户"

        self.output.print(f"\n{'='*60}")
        self.output.print(f"摘要: {summary}")
        self.output.print(f"{'='*60}")

        # 密码问题统计
        empty = data.get('empty_passwords', 0)
        weak = data.get('weak_passwords', 0)
        expired = data.get('expired_passwords', 0)
        locked = data.get('locked_accounts', 0)

        self.output.print(f"\n密码问题统计:")
        if empty > 0:
            self.output.error(f"  空密码: {empty} 个")
        else:
            self.output.print(f"  空密码: {empty} 个")

        if weak > 0:
            self.output.warning(f"  弱密码: {weak} 个")
        else:
            self.output.print(f"  弱密码: {weak} 个")

        if expired > 0:
            self.output.warning(f"  过期密码: {expired} 个")
        else:
            self.output.print(f"  过期密码: {expired} 个")

        if locked > 0:
            self.output.warning(f"  锁定账户: {locked} 个")
        else:
            self.output.print(f"  锁定账户: {locked} 个")

        # 显示具体的弱密码账号（按用户名合并）
        if weak > 0:
            weak_users = data.get('weak_password_users', [])
            if weak_users:
                # 按用户名分组
                from collections import defaultdict
                user_hosts = defaultdict(list)
                for user_info in weak_users:
                    username = user_info.get('username', 'unknown')
                    host = user_info.get('host', '%')
                    user_hosts[username].append(host)
                
                self.output.warning(f"\n弱密码账号列表:")
                for username, hosts in list(user_hosts.items())[:10]:  # 最多显示10个用户
                    if len(hosts) == 1:
                        host_str = hosts[0]
                    else:
                        # 多个主机，显示主要的主机，其他用省略号
                        if '%' in hosts:
                            host_str = '% (任意主机)'
                        else:
                            host_str = f"{hosts[0]} 等{len(hosts)}个主机"
                    self.output.warning(f"  - {username}@{host_str}")
                if len(user_hosts) > 10:
                    self.output.warning(f"  ... 还有 {len(user_hosts) - 10} 个账号")

        # 显示空密码账号（按用户名合并）
        if empty > 0:
            empty_users = data.get('empty_password_users', [])
            if empty_users:
                from collections import defaultdict
                user_hosts = defaultdict(list)
                for user_info in empty_users:
                    username = user_info.get('username', 'unknown')
                    host = user_info.get('host', '%')
                    user_hosts[username].append(host)
                
                self.output.error(f"\n空密码账号列表:")
                for username, hosts in list(user_hosts.items())[:10]:
                    if len(hosts) == 1:
                        host_str = hosts[0]
                    else:
                        host_str = f"{hosts[0]} 等{len(hosts)}个主机" if '%' not in hosts else '% (任意主机)'
                    self.output.error(f"  - {username}@{host_str}")

        # 显示过期密码账号（按用户名合并）
        if expired > 0:
            expired_users = data.get('expired_password_users', [])
            if expired_users:
                from collections import defaultdict
                user_hosts = defaultdict(list)
                for user_info in expired_users:
                    username = user_info.get('username', 'unknown')
                    host = user_info.get('host', '%')
                    user_hosts[username].append(host)
                
                self.output.warning(f"\n过期密码账号列表:")
                for username, hosts in list(user_hosts.items())[:10]:
                    if len(hosts) == 1:
                        host_str = hosts[0]
                    else:
                        host_str = f"{hosts[0]} 等{len(hosts)}个主机" if '%' not in hosts else '% (任意主机)'
                    self.output.warning(f"  - {username}@{host_str}")

        # 关键问题
        critical = data.get('critical_issues', [])
        if critical:
            self.output.error(f"\n关键问题 ({len(critical)}个):")
            for issue in critical[:5]:
                issue_type = issue.get('type', 'unknown')
                desc = issue.get('description', '')
                self.output.error(f"  - {desc}")

        # 建议
        recommendations = data.get('recommendations', [])
        if recommendations:
            self.output.print(f"\n改进建议:")
            for rec in recommendations:
                self.output.print(f"  - {rec}")

        return 0

    def _check_weak_passwords(self, skill) -> int:
        """弱密码检查"""
        result = skill.find_weak_passwords()

        if not result.get('success'):
            self.output.error(f"弱密码检查失败: {result.get('message', '未知错误')}")
            return 1

        data = result.get('data', {})
        summary_data = data.get('summary', {})
        empty = summary_data.get('empty_passwords', 0)
        very_weak = summary_data.get('very_weak_passwords', 0)
        weak = summary_data.get('weak_passwords', 0)
        total = summary_data.get('total_at_risk', 0)

        summary = f"发现{total}个风险账户（空密码:{empty}, 极弱:{very_weak}, 弱:{weak}）"

        self.output.print(f"\n{'='*60}")
        self.output.print(f"摘要: {summary}")
        self.output.print(f"{'='*60}")

        # 空密码用户
        if empty > 0:
            empty_users = data.get('empty_password_users', [])
            self.output.error(f"\n空密码用户 ({empty}个):")
            for user_info in empty_users[:10]:
                username = user_info.get('username', 'unknown')
                host = user_info.get('host', '%')
                self.output.error(f"  - {username}@{host}")

        # 极弱密码用户
        if very_weak > 0:
            very_weak_users = data.get('very_weak_password_users', [])
            self.output.error(f"\n极弱密码用户 ({very_weak}个):")
            for user_info in very_weak_users[:10]:
                username = user_info.get('username', 'unknown')
                host = user_info.get('host', '%')
                self.output.error(f"  - {username}@{host}")

        # 弱密码用户
        if weak > 0:
            weak_users = data.get('weak_password_users', [])
            self.output.warning(f"\n弱密码用户 ({weak}个):")
            for user_info in weak_users[:10]:
                username = user_info.get('username', 'unknown')
                host = user_info.get('host', '%')
                self.output.warning(f"  - {username}@{host}")

        # 需要立即处理的用户
        immediate = data.get('immediate_action_required', [])
        if immediate:
            self.output.error(f"\n需要立即处理的用户:")
            for username in immediate[:10]:
                self.output.error(f"  - {username}")

        return 0

    def _audit_config(self, skill) -> int:
        """数据库配置安全审计"""
        result = skill.audit_config()

        if not result.get('success'):
            self.output.error(f"配置审计失败: {result.get('message', '未知错误')}")
            return 1

        data = result.get('data', {})

        # 兼容两种返回格式：MySQL返回summary+issues，Oracle返回risks
        if data.get('summary'):
            summary_data = data.get('summary', {})
            total = summary_data.get('total_issues', 0)
            critical = summary_data.get('critical_issues', 0)
            high = summary_data.get('high_issues', 0)
            medium = summary_data.get('medium_issues', 0)
            low = summary_data.get('low_issues', 0)
            summary = f"发现{total}个配置问题（严重:{critical}, 高:{high}, 中:{medium}, 低:{low}）"
        else:
            risks = data.get('risks', [])
            total_checks = data.get('total_checks', data.get('total_checked', 0))
            risks_found = len(risks)
            high = sum(1 for r in risks if r.get('severity') == 'high')
            medium = sum(1 for r in risks if r.get('severity') == 'medium')
            low = sum(1 for r in risks if r.get('severity') == 'low')
            summary = f"检查了{total_checks}项配置，发现{risks_found}个问题（高:{high}, 中:{medium}, 低:{low}）"

        self.output.print(f"\n{'='*60}")
        self.output.print(f"摘要: {summary}")
        self.output.print(f"{'='*60}")

        # 详细问题列表
        issues = data.get('issues', [])
        risks = data.get('risks', [])
        all_items = issues if issues else risks

        if all_items:
            self.output.print(f"\n详细问题列表:")
            for item in all_items[:20]:
                level = item.get('level', item.get('severity', 'unknown'))
                parameter = item.get('parameter', item.get('category', ''))
                current = item.get('current_value', '')
                recommended = item.get('recommended_value', item.get('suggestion', ''))
                description = item.get('description', '')

                if level in ('critical', 'high'):
                    self.output.warning(f"\n[{level.upper()}] {description}")
                elif level == 'medium':
                    self.output.print(f"\n[MEDIUM] {description}")
                else:
                    self.output.print(f"\n[LOW] {description}")

                self.output.print(f"  当前值: {current}")
                self.output.print(f"  推荐值: {recommended}")
                if description:
                    self.output.print(f"  说明: {description}")

        # 安全建议
        recommendations = data.get('recommendations', [])
        if recommendations:
            self.output.print(f"\n{'='*60}")
            self.output.print(f"安全建议:")
            self.output.print(f"{'='*60}")
            for i, rec in enumerate(recommendations[:10], 1):
                priority = rec.get('priority', 'medium')
                description = rec.get('description', '')
                if priority == 'high':
                    self.output.warning(f"{i}. {description}")
                else:
                    self.output.print(f"{i}. {description}")

        return 0
