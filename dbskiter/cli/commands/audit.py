"""
cli/commands/audit.py

SQL审核命令 - SQL规范审核、性能评估、DDL影响分析
核心功能：审核SQL、审核SQL文件、DDL影响分析、查看审核规则

用法:
    dbskiter audit sql "SELECT * FROM users"     # 审核SQL
    dbskiter audit file queries.sql              # 审核SQL文件
    dbskiter audit ddl "ALTER TABLE..."          # DDL影响分析
    dbskiter audit rules                         # 查看审核规则
"""

import json
from argparse import ArgumentParser
from typing import Dict, Any

from .base import BaseCommand
from dbskiter.shared.error_handler import create_error_response, ErrorCode


class AuditCommand(BaseCommand):
    """SQL审核命令"""

    name = "audit"
    description = "SQL Auditor - SQL全生命周期审核"
    help_text = "SQL规范审核、性能评估、DDL影响分析"

    @classmethod
    def add_arguments(cls, parser: ArgumentParser) -> None:
        """添加审核命令参数"""
        subparsers = parser.add_subparsers(dest="audit_action", help="审核操作")

        # sql 子命令 - 审核SQL语句
        sql_parser = subparsers.add_parser("sql", help="审核SQL语句")
        sql_parser.add_argument(
            "sql",
            help="要审核的SQL语句"
        )
        sql_parser.add_argument(
            "--format", "-f",
            choices=["text", "json"],
            default="text",
            help="输出格式"
        )

        # file 子命令 - 审核SQL文件
        file_parser = subparsers.add_parser("file", help="审核SQL文件")
        file_parser.add_argument(
            "filepath",
            help="SQL文件路径"
        )
        file_parser.add_argument(
            "--format", "-f",
            choices=["text", "json"],
            default="text",
            help="输出格式"
        )

        # ddl 子命令 - DDL影响分析
        ddl_parser = subparsers.add_parser("ddl", help="DDL影响分析")
        ddl_parser.add_argument(
            "ddl_sql",
            help="DDL语句"
        )

        # rules 子命令 - 查看审核规则
        rules_parser = subparsers.add_parser("rules", help="查看审核规则")
        rules_parser.add_argument(
            "--type", "-t",
            choices=["syntax", "performance", "security", "style", "ddl"],
            help="规则类型过滤"
        )

        # optimize 子命令 - SQL优化
        optimize_parser = subparsers.add_parser("optimize", help="SQL智能优化")
        optimize_parser.add_argument(
            "sql",
            help="要优化的SQL语句"
        )
        optimize_parser.add_argument(
            "--format", "-f",
            choices=["text", "json"],
            default="text",
            help="输出格式"
        )

        # recommend-indexes 子命令 - 索引推荐
        indexes_parser = subparsers.add_parser("recommend-indexes", help="索引推荐")
        indexes_parser.add_argument(
            "sql",
            help="SQL语句"
        )
        indexes_parser.add_argument(
            "--format", "-f",
            choices=["text", "json"],
            default="text",
            help="输出格式"
        )

    def execute(self) -> int:
        """执行审核命令"""
        from dbskiter.db_sql_auditor.skill import SQLAuditorSkill

        try:
            self.require_connector()
        except Exception as e:
            self.output.error(str(e))
            return 1

        try:
            skill = SQLAuditorSkill(self.connector)

            action = getattr(self.args, 'audit_action', None)

            if self.output_mode != "rule":
                method_map = {
                    "sql": lambda: skill.audit_sql(self.args.sql),
                    "file": lambda: self._audit_file_ai(skill),
                    "ddl": lambda: skill.analyze_ddl_impact(self.args.ddl_sql),
                    "optimize": lambda: skill.optimize_sql(getattr(self.args, 'sql', '')),
                    "recommend-indexes": lambda: skill.recommend_indexes(
                        getattr(self.args, 'sql', ''),
                        {},
                    ),
                }
                scenario_map = {
                    "sql": "sql_audit",
                    "file": "sql_audit",
                    "ddl": "ddl_audit",
                    "optimize": "sql_optimize",
                    "recommend-indexes": "index_recommend",
                }
                if action in method_map:
                    return self._execute_ai_mode(skill, action, method_map, scenario_map)
                if action != "rules":
                    self.output.error(f"不支持的操作: {action}")
                    return 1

            if action == "sql":
                return self._audit_sql(skill)
            elif action == "file":
                return self._audit_file(skill)
            elif action == "ddl":
                return self._analyze_ddl(skill)
            elif action == "rules":
                return self._show_rules(skill)
            elif action == "optimize":
                return self._optimize_sql(skill)
            elif action == "recommend-indexes":
                return self._recommend_indexes(skill)
            else:
                self.output.error("请指定审核操作: sql, file, ddl, rules, optimize, recommend-indexes")
                return 1

        except Exception as e:
            self.output.error(f"审核失败: {e}")
            return 1
        finally:
            if 'skill' in locals():
                skill.close()

    def _audit_sql(self, skill) -> int:
        """审核SQL"""
        response = skill.audit_sql(self.args.sql)
        
        # 检查是否成功
        if not response.get('success'):
            self.output.error(f"审核失败: {response.get('message', '未知错误')}")
            return 1
        
        # 获取审核结果数据
        result = response.get('data', {})

        output_format = getattr(self.args, 'format', 'text')

        if output_format == "json":
            self.output.print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0

        # 文本输出
        self.output.print(f"\n{'='*60}")
        self.output.print("SQL审核结果")
        self.output.print(f"{'='*60}")

        sql_type = result.get('sql_type', 'unknown')
        score = result.get('score', 0)
        passed = result.get('passed', False)
        
        self.output.print(f"\nSQL类型: {sql_type}")
        self.output.print(f"审核评分: {score:.1f}/100")

        if passed:
            self.output.success(f"审核状态: 通过")
        else:
            self.output.error(f"审核状态: 未通过")

        # 问题统计
        issues = result.get('issues', [])
        critical_count = sum(1 for i in issues if i.get('level') == 'critical')
        high_count = sum(1 for i in issues if i.get('level') == 'high')
        medium_count = sum(1 for i in issues if i.get('level') == 'medium')
        low_count = sum(1 for i in issues if i.get('level') == 'low')
        
        self.output.print(f"\n问题统计:")
        self.output.print(f"  严重: {critical_count}")
        self.output.print(f"  高危: {high_count}")
        self.output.print(f"  中危: {medium_count}")
        self.output.print(f"  低危: {low_count}")

        if issues:
            self.output.warning(f"\n问题详情:")
            for issue in issues:
                level = issue.get('level', 'unknown')
                level_str = f"[{level.upper()}]"
                rule_name = issue.get('rule_name', '未知规则')
                message = issue.get('message', '无说明')
                suggestion = issue.get('suggestion', '无建议')
                sql_fragment = issue.get('sql_fragment', '')
                
                self.output.print(f"\n  {level_str} {rule_name}")
                self.output.print(f"    说明: {message}")
                self.output.print(f"    建议: {suggestion}")
                if sql_fragment:
                    self.output.print(f"    片段: {sql_fragment[:50]}...")

        return 0

    def _audit_file_ai(self, skill) -> Dict[str, Any]:
        """AI模式审核SQL文件"""
        try:
            with open(self.args.filepath, 'r', encoding='utf-8') as f:
                content = f.read()

            sql_list = [s.strip() for s in content.split(';') if s.strip()]

            return skill.audit_sql_list(sql_list)
        except FileNotFoundError:
            return create_error_response(f"文件不存在: {self.args.filepath}", ErrorCode.FILE_NOT_FOUND)
        except Exception as e:
            return create_error_response(str(e), ErrorCode.UNKNOWN_ERROR)

    def _audit_file(self, skill) -> int:
        """审核SQL文件"""
        try:
            with open(self.args.filepath, 'r', encoding='utf-8') as f:
                content = f.read()

            # 简单分割SQL（实际应该用更复杂的解析）
            sql_list = [s.strip() for s in content.split(';') if s.strip()]

            response = skill.audit_sql_list(sql_list)

            # 检查是否成功
            if not response.get('success'):
                self.output.error(f"审核失败: {response.get('message', '未知错误')}")
                return 1

            data = response.get('data', {})
            results = data.get('results', [])

            total_passed = sum(1 for r in results if r.get('passed', False))
            total_issues = sum(r.get('total_issues', 0) for r in results)

            output_format = getattr(self.args, 'format', 'text')

            if output_format == "json":
                result = {
                    "success": True,
                    "total_sql": len(sql_list),
                    "passed": total_passed,
                    "failed": len(sql_list) - total_passed,
                    "total_issues": total_issues,
                    "results": results
                }
                self.output.print(json.dumps(result, ensure_ascii=False, indent=2))
                return 0

            self.output.print(f"\n{'='*60}")
            self.output.print("SQL文件审核结果")
            self.output.print(f"{'='*60}")

            self.output.print(f"\nSQL数量: {len(sql_list)}")
            self.output.print(f"通过: {total_passed}")
            self.output.print(f"失败: {len(sql_list) - total_passed}")
            self.output.print(f"总问题数: {total_issues}")

            return 0

        except FileNotFoundError:
            self.output.error(f"文件不存在: {self.args.filepath}")
            return 1
        except Exception as e:
            self.output.error(f"审核文件失败: {e}")
            return 1

    def _analyze_ddl(self, skill) -> int:
        """DDL影响分析"""
        response = skill.analyze_ddl_impact(self.args.ddl_sql)

        # 检查是否成功
        if not response.get('success'):
            self.output.error(f"DDL分析失败: {response.get('message', '未知错误')}")
            return 1

        impact = response.get('data', {})

        self.output.print(f"\n{'='*60}")
        self.output.print("DDL影响分析")
        self.output.print(f"{'='*60}")

        self.output.print(f"\n操作: {impact.get('operation', 'unknown')}")
        self.output.print(f"目标表: {impact.get('table_name', 'unknown')}")
        self.output.print(f"预估执行时间: {impact.get('execution_time_estimate', 'unknown')}")

        table_size_mb = impact.get('table_size_mb')
        if table_size_mb:
            self.output.print(f"表大小: {table_size_mb} MB")

        rows_estimate = impact.get('rows_estimate')
        if rows_estimate:
            self.output.print(f"预估行数: {rows_estimate}")

        risks = impact.get('risks', [])
        if risks:
            self.output.print(f"\n风险点:")
            for risk in risks:
                self.output.print(f"  - {risk}")

        suggestions = impact.get('suggestions', [])
        if suggestions:
            self.output.print(f"\n建议:")
            for suggestion in suggestions:
                self.output.print(f"  - {suggestion}")

        return 0

    def _show_rules(self, skill) -> int:
        """显示审核规则"""
        try:
            rules = skill.get_rules()

            rule_type = getattr(self.args, 'type', None)
            if rule_type:
                rules = [r for r in rules if r.get('audit_type') == rule_type]

            self.output.print(f"\n{'='*60}")
            self.output.print(f"审核规则列表 ({len(rules)}条)")
            self.output.print(f"{'='*60}")

            for rule in rules:
                status = "启用" if rule.get('enabled', False) else "禁用"
                rule_id = rule.get('rule_id', 'unknown')
                rule_name = rule.get('rule_name', '未命名')
                audit_type = rule.get('audit_type', 'unknown')
                level = rule.get('level', 'unknown')
                description = rule.get('description', '无说明')
                
                self.output.print(f"\n{rule_id}: {rule_name} [{status}]")
                self.output.print(f"  类型: {audit_type}")
                self.output.print(f"  级别: {level}")
                self.output.print(f"  说明: {description}")

            return 0
        except Exception as e:
            self.output.error(f"获取审核规则失败: {e}")
            return 1

    def _optimize_sql(self, skill) -> int:
        """SQL智能优化"""
        response = skill.optimize_sql(self.args.sql)

        # 检查是否成功
        if not response.get('success'):
            self.output.error(f"SQL优化失败: {response.get('message', '未知错误')}")
            return 1

        result = response.get('data', {})
        output_format = getattr(self.args, 'format', 'text')

        if output_format == "json":
            self.output.print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0

        self.output.print(f"\n{'='*60}")
        self.output.print("SQL智能优化结果")
        self.output.print(f"{'='*60}")

        original_sql = result.get('original_sql', '')
        self.output.print(f"\n原始SQL:")
        self.output.print(f"  {original_sql[:100]}...")

        recommendations = result.get('recommendations', [])
        if recommendations:
            self.output.print(f"\n优化建议 ({len(recommendations)}条):")
            for i, rec in enumerate(recommendations[:5], 1):
                self.output.print(f"\n  {i}. {rec.get('type', 'unknown')}")
                self.output.print(f"     说明: {rec.get('description', '无说明')}")
                if rec.get('optimized_sql'):
                    self.output.print(f"     优化SQL: {rec.get('optimized_sql')[:80]}...")

        return 0

    def _recommend_indexes(self, skill) -> int:
        """索引推荐"""
        response = skill.recommend_indexes(self.args.sql, {})

        # 检查是否成功
        if not response.get('success'):
            self.output.error(f"索引推荐失败: {response.get('message', '未知错误')}")
            return 1

        result = response.get('data', {})
        output_format = getattr(self.args, 'format', 'text')

        if output_format == "json":
            self.output.print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0

        self.output.print(f"\n{'='*60}")
        self.output.print("索引推荐结果")
        self.output.print(f"{'='*60}")

        indexes = result.get('recommendations', [])
        if indexes:
            self.output.print(f"\n推荐索引 ({len(indexes)}个):")
            for i, idx in enumerate(indexes, 1):
                self.output.print(f"\n  {i}. 表: {idx.get('table', 'unknown')}")
                self.output.print(f"     索引名: {idx.get('index_name', 'auto_idx')}")
                self.output.print(f"     列: {', '.join(idx.get('columns', []))}")
                self.output.print(f"     类型: {idx.get('index_type', 'BTREE')}")
                self.output.print(f"     理由: {idx.get('reason', '无说明')}")
                if idx.get('priority'):
                    self.output.print(f"     优先级: {idx.get('priority', 'medium')}")
        else:
            self.output.print("\n无需添加新索引")

        return 0
