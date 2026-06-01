"""
cli/commands/sql.py

SQL Master 命令 - SQL执行、重写、分析、智能提示
核心功能：SQL执行、SQL重写优化、SQL质量分析、数据分析、智能补全、Schema查询
"""

import json
import os
from argparse import ArgumentParser

from .base import BaseCommand
from dbskiter.cli.readonly_middleware import ReadOnlyEnforcer, is_readonly_mode


class SQLCommand(BaseCommand):
    """SQL Master 命令"""

    name = "sql"
    description = "SQL Master - SQL执行、重写、分析、智能提示"
    help_text = "执行SQL、重写优化、质量分析、智能补全"

    @classmethod
    def add_arguments(cls, parser: ArgumentParser) -> None:
        """添加SQL命令参数"""
        # 使用 --sql 参数来支持直接执行SQL，避免与子命令冲突
        parser.add_argument("--sql", help="直接执行SQL语句（简化写法）")
        parser.add_argument("--params", help="SQL参数（JSON格式）")
        parser.add_argument("--limit", type=int, default=100, help="返回行数限制（默认100）")
        
        # 安全控制参数
        parser.add_argument(
            "--read-only",
            action="store_true",
            help="只读模式，禁止执行任何写操作（INSERT/UPDATE/DELETE/DROP等）"
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="强制执行危险操作（如DROP DATABASE/TABLE等极高风险操作）"
        )

        subparsers = parser.add_subparsers(dest="sql_action", help="SQL操作")

        # ==================== 核心命令（7个） ====================

        # execute 子命令 - 执行SQL
        execute_parser = subparsers.add_parser("execute", help="执行SQL语句")
        execute_parser.add_argument("sql", help="SQL语句")
        execute_parser.add_argument("--params", help="SQL参数（JSON格式）")
        execute_parser.add_argument("--limit", type=int, default=100, help="返回行数限制")
        execute_parser.add_argument(
            "--read-only",
            action="store_true",
            help="只读模式，禁止执行写操作"
        )
        execute_parser.add_argument(
            "--force",
            action="store_true",
            help="强制执行危险操作"
        )

        # rewrite 子命令 - 重写优化
        rewrite_parser = subparsers.add_parser("rewrite", help="重写SQL优化")
        rewrite_parser.add_argument("sql", help="SQL语句")

        # analyze 子命令 - SQL质量分析
        analyze_parser = subparsers.add_parser("analyze", help="分析SQL质量")
        analyze_parser.add_argument("sql", help="SQL语句")

        # data 子命令 - 数据分析
        data_parser = subparsers.add_parser("data", help="分析查询结果数据")
        data_parser.add_argument("sql", help="SQL查询语句")
        data_parser.add_argument("--params", help="SQL参数（JSON格式）")

        # complete 子命令 - 智能补全
        complete_parser = subparsers.add_parser("complete", help="SQL智能补全")
        complete_parser.add_argument("partial", help="部分SQL")

        # schema 子命令 - Schema信息
        schema_parser = subparsers.add_parser("schema", help="获取Schema信息")
        schema_parser.add_argument("--table", help="指定表名")

        # batch 子命令 - 批量执行
        batch_parser = subparsers.add_parser("batch", help="批量执行SQL")
        batch_parser.add_argument("file", help="SQL文件路径（每行一个SQL）")

        # export 子命令 - 导出数据
        export_parser = subparsers.add_parser("export", help="导出表数据或查询结果")
        export_parser.add_argument("--table", help="表名（与--query二选一）")
        export_parser.add_argument("--query", help="SQL查询（与--table二选一）")
        export_parser.add_argument("--output", "-o", required=True, help="输出文件路径")
        export_parser.add_argument("--format", "-f", choices=["csv", "json", "sql", "excel"], default="csv", help="导出格式")
        export_parser.add_argument("--where", help="WHERE条件（仅table模式）")
        export_parser.add_argument("--limit", type=int, help="限制行数")

        # import 子命令 - 导入数据
        import_parser = subparsers.add_parser("import", help="导入数据到表")
        import_parser.add_argument("file", help="数据文件路径")
        import_parser.add_argument("--table", "-t", required=True, help="目标表名")
        import_parser.add_argument("--format", "-f", choices=["csv", "json", "sql"], default="csv", help="文件格式")
        import_parser.add_argument("--columns", help="指定列名（逗号分隔，CSV格式用）")
        import_parser.add_argument("--batch-size", type=int, default=1000, help="批量插入大小")

        # export-stream 子命令 - 流式导出大表
        export_stream_parser = subparsers.add_parser("export-stream", help="流式导出大表数据")
        export_stream_parser.add_argument("--table", required=True, help="表名")
        export_stream_parser.add_argument("--output", "-o", required=True, help="输出文件路径")
        export_stream_parser.add_argument("--format", "-f", choices=["csv", "sql"], default="csv", help="导出格式")
        export_stream_parser.add_argument("--where", help="WHERE条件")
        export_stream_parser.add_argument("--batch-size", type=int, default=10000, help="每批导出的行数")

        # audit 子命令 - 审计日志查询
        audit_parser = subparsers.add_parser("audit", help="查询SQL审计日志")
        audit_parser.add_argument("--risk-level", choices=["CRITICAL", "HIGH", "MEDIUM", "SAFE"], help="风险等级筛选")
        audit_parser.add_argument("--hours", type=int, default=24, help="最近多少小时（默认24）")
        audit_parser.add_argument("--limit", type=int, default=50, help="返回数量限制（默认50）")
        audit_parser.add_argument("--stats", action="store_true", help="显示统计信息")
        audit_parser.add_argument("--cleanup", type=int, metavar="DAYS", help="清理多少天前的记录")

    def execute(self) -> int:
        """执行SQL命令"""
        from dbskiter.sql_master.skill import SQLMasterSkill

        action = getattr(self.args, 'sql_action', None)
        direct_sql = getattr(self.args, 'sql', None)

        if not action and not direct_sql:
            self.output.error("请指定SQL操作: execute, rewrite, analyze, data, complete, schema")
            self.output.info("或直接使用: dbskiter sql --sql \"SELECT * FROM table\"")
            return 1

        try:
            skill = SQLMasterSkill(self.connector)

            if self.output_mode != "rule":
                method_map = {
                    "execute": lambda: skill.execute(
                        direct_sql or getattr(self.args, 'sql', ''),
                        json.loads(self.args.params) if getattr(self.args, 'params', None) else None,
                        getattr(self.args, 'limit', 100),
                        allow_write=False,
                    ),
                    "rewrite": lambda: skill.rewrite_sql(getattr(self.args, 'sql', '')),
                    "analyze": lambda: skill.analyze_sql_quality(getattr(self.args, 'sql', '')),
                    "data": lambda: skill.analyze_data(getattr(self.args, 'sql', '')),
                    "schema": lambda: skill.get_schema_info(
                        table_name=getattr(self.args, 'table', None) or '',
                    ),
                }
                scenario_map = {
                    "execute": "sql_execute",
                    "rewrite": "sql_rewrite",
                    "analyze": "sql_analyze",
                    "data": "data_analysis",
                    "complete": "sql_complete",
                    "schema": "schema_query",
                }
                effective_action = action or ("execute" if direct_sql else None)
                if effective_action in method_map:
                    return self._execute_ai_mode(skill, effective_action, method_map, scenario_map)

            if not action and direct_sql:
                # 检查全局只读模式
                global_readonly = is_readonly_mode()
                arg_readonly = getattr(self.args, 'read_only', False)
                read_only = global_readonly or arg_readonly
                
                if global_readonly and not arg_readonly:
                    self.output.warning("系统处于全局只读模式（DBSKITER_READ_ONLY=true）")
                
                # 使用ReadOnlyEnforcer进行额外检查
                enforcer = ReadOnlyEnforcer(enabled=read_only)
                allowed, reason = enforcer.check(direct_sql)
                if not allowed:
                    self.output.error(f"执行被拒绝: {reason}")
                    return 1
                
                params = getattr(self.args, 'params', None)
                if params:
                    params = json.loads(params)
                limit = getattr(self.args, 'limit', 100)
                force = getattr(self.args, 'force', False)
                result = skill.execute(
                    direct_sql,
                    params,
                    limit,
                    allow_write=not read_only,
                    force=force
                )
                return self._print_execute_result(result)

            if action == "execute":
                return self._execute_sql(skill)
            elif action == "rewrite":
                return self._rewrite_sql(skill)
            elif action == "analyze":
                return self._analyze_sql(skill)
            elif action == "data":
                return self._analyze_data(skill)
            elif action == "complete":
                return self._get_completions(skill)
            elif action == "schema":
                return self._get_schema(skill)
            elif action == "batch":
                return self._execute_batch(skill)
            elif action == "export":
                return self._export_data(skill)
            elif action == "import":
                return self._import_data(skill)
            elif action == "export-stream":
                return self._export_stream(skill)
            elif action == "audit":
                return self._query_audit_logs(skill)
            else:
                self.output.error(f"未知操作: {action}")
                return 1

        except Exception as e:
            self.output.error(f"SQL操作失败: {e}")
            return 1
        finally:
            if 'skill' in locals():
                skill.close()

    def _execute_direct(self, skill) -> int:
        """直接执行SQL（简化用法）"""
        sql = self.args.sql
        
        # 检查全局只读模式
        global_readonly = is_readonly_mode()
        arg_readonly = getattr(self.args, 'read_only', False)
        read_only = global_readonly or arg_readonly
        
        if global_readonly and not arg_readonly:
            self.output.warning("系统处于全局只读模式（DBSKITER_READ_ONLY=true）")
        
        # 使用ReadOnlyEnforcer进行额外检查
        enforcer = ReadOnlyEnforcer(enabled=read_only)
        allowed, reason = enforcer.check(sql)
        if not allowed:
            self.output.error(f"执行被拒绝: {reason}")
            return 1
        
        # 获取安全控制参数
        force = getattr(self.args, 'force', False)

        result = skill.execute(sql, params=None, limit=getattr(self.args, 'limit', 100), allow_write=not read_only, force=force)

        if not result.get("success"):
            error_msg = result.get('error', '未知错误')
            extra = result.get('extra', {})

            # 处理危险操作错误
            if extra.get('requires_force'):
                self.output.error(f"执行失败: {error_msg}")
                self.output.info("提示: 如果确定要执行此操作，请添加 --force 参数")
            elif extra.get('risk_level') in ('HIGH', 'CRITICAL'):
                self.output.error(f"执行失败: {error_msg}")
                self.output.info(f"风险等级: {extra.get('risk_level')}")
                if extra.get('risk_description'):
                    self.output.info(f"风险说明: {extra.get('risk_description')}")
            else:
                self.output.error(f"执行失败: {error_msg}")
            return 1

        # 从标准响应格式的 data 字段获取数据
        data = result.get("data", {})
        summary = f"执行成功，返回{data.get('row_count', 0)}行"

        self.output.print(f"\n{'='*60}")
        self.output.print(f"摘要: {summary}")
        self.output.print(f"{'='*60}")

        self.output.print(f"\nSQL: {data.get('sql', '')}")
        self.output.print(f"行数: {data.get('row_count', 0)}")

        if data.get("execution_time"):
            self.output.print(f"耗时: {data['execution_time']:.3f}s")

        # 输出结果表格
        columns = data.get("columns", [])
        rows = data.get("rows", [])

        if columns and rows:
            self.output.print(f"\n结果:")
            # 表头
            header = " | ".join(str(c) for c in columns)
            self.output.print(header)
            self.output.print("-" * len(header))
            # 数据行
            for row in rows[:50]:  # 最多显示50行
                self.output.print(" | ".join(str(cell) for cell in row))
            if len(rows) > 50:
                self.output.print(f"... 还有 {len(rows) - 50} 行")

        return 0

    def _execute_sql(self, skill) -> int:
        """执行SQL"""
        import traceback

        params = None
        if self.args.params:
            params = json.loads(self.args.params)
        
        # 检查全局只读模式
        global_readonly = is_readonly_mode()
        arg_readonly = getattr(self.args, 'read_only', False)
        read_only = global_readonly or arg_readonly
        
        if global_readonly and not arg_readonly:
            self.output.warning("系统处于全局只读模式（DBSKITER_READ_ONLY=true）")
        
        # 使用ReadOnlyEnforcer进行额外检查
        enforcer = ReadOnlyEnforcer(enabled=read_only)
        allowed, reason = enforcer.check(self.args.sql)
        if not allowed:
            self.output.error(f"执行被拒绝: {reason}")
            return 1
        
        # 获取安全控制参数
        force = getattr(self.args, 'force', False)

        try:
            result = skill.execute(
                self.args.sql,
                params,
                self.args.limit,
                allow_write=not read_only,
                force=force
            )
        except Exception as e:
            self.output.error(f"执行异常: {e}")
            self.output.print(traceback.format_exc())
            return 1

        if not result.get("success"):
            error_msg = result.get('error', '未知错误')
            extra = result.get('extra', {})
            
            # 处理危险操作错误
            if extra.get('requires_force'):
                self.output.error(f"执行失败: {error_msg}")
                self.output.info("提示: 如果确定要执行此操作，请添加 --force 参数")
            elif extra.get('risk_level') in ('HIGH', 'CRITICAL'):
                self.output.error(f"执行失败: {error_msg}")
                self.output.info(f"风险等级: {extra.get('risk_level')}")
                if extra.get('risk_description'):
                    self.output.info(f"风险说明: {extra.get('risk_description')}")
            else:
                self.output.error(f"执行失败: {error_msg}")
            return 1

        # 从 data 字段获取实际数据
        data = result.get("data", {})
        summary = f"执行成功，返回{data.get('row_count', 0)}行"

        self.output.print(f"\n{'='*60}")
        self.output.print(f"摘要: {summary}")
        self.output.print(f"{'='*60}")

        self.output.print(f"\nSQL: {data.get('sql', '')}")
        self.output.print(f"行数: {data.get('row_count', 0)}")

        if data.get("execution_time"):
            self.output.print(f"耗时: {data['execution_time']:.3f}s")

        # 输出结果表格
        columns = data.get("columns", [])
        rows = data.get("rows", [])

        if columns and rows:
            self.output.print(f"\n结果:")
            # 表头
            header = " | ".join(str(c) for c in columns)
            self.output.print(header)
            self.output.print("-" * len(header))
            # 数据行
            for row in rows[:50]:  # 最多显示50行
                self.output.print(" | ".join(str(cell) for cell in row))
            if len(rows) > 50:
                self.output.print(f"... 还有 {len(rows) - 50} 行")

        return 0

    def _rewrite_sql(self, skill) -> int:
        """重写SQL优化"""
        response = skill.rewrite_sql(self.args.sql)

        if response.get("success") == "disabled":
            self.output.warning(response.get("message", "SQL重写已禁用"))
            return 0

        if not response.get("success"):
            self.output.error(f"重写失败: {response.get('error', '未知错误')}")
            return 1

        # 获取实际数据
        result = response.get("data", {})
        can_optimize = result.get("can_optimize", False)
        summary = f"发现{result.get('suggestions_count', 0)}个优化建议" if can_optimize else "无需优化"

        self.output.print(f"\n{'='*60}")
        self.output.print(f"摘要: {summary}")
        self.output.print(f"{'='*60}")

        self.output.print(f"\n原始SQL:")
        self.output.print(f"  {result.get('original_sql', '')}")

        if can_optimize:
            self.output.success(f"\n优化后SQL:")
            self.output.print(f"  {result.get('optimized_sql', '')}")

            suggestions = result.get("suggestions", [])
            if suggestions:
                self.output.print(f"\n优化建议 ({len(suggestions)}个):")
                for i, sug in enumerate(suggestions, 1):
                    impact_text = "高危" if sug.get("impact") == "high" else "中危" if sug.get("impact") == "medium" else "低危"
                    self.output.print(f"\n  [{i}] {impact_text} - {sug.get('type', '')}")
                    self.output.print(f"      原因: {sug.get('reason', '')}")
                    self.output.print(f"      置信度: {sug.get('confidence', 0):.0%}")
                    if sug.get("rewritten_sql"):
                        self.output.print(f"      重写: {sug['rewritten_sql']}")
        else:
            self.output.success("\nSQL已是最优，无需优化")

        return 0

    def _analyze_sql(self, skill) -> int:
        """分析SQL质量"""
        response = skill.analyze_sql_quality(self.args.sql)

        if response.get("success") == "disabled":
            self.output.warning(response.get("message", "SQL分析已禁用"))
            return 0

        if not response.get("success"):
            self.output.error(f"分析失败: {response.get('error', '未知错误')}")
            return 1

        # 获取实际数据
        result = response.get("data", {})
        score = result.get("score", 0)
        complexity = result.get("complexity", "low")
        issues = result.get("issues", [])
        suggestions = result.get("suggestions", [])
        
        # 计算等级
        if score >= 90:
            grade = "A"
            assessment = "优秀"
        elif score >= 70:
            grade = "B"
            assessment = "良好"
        elif score >= 50:
            grade = "C"
            assessment = "一般"
        else:
            grade = "F"
            assessment = "需改进"

        summary = f"SQL质量评分{score}分（{grade}级）-{assessment}"

        self.output.print(f"\n{'='*60}")
        self.output.print(f"摘要: {summary}")
        self.output.print(f"{'='*60}")

        self.output.print(f"\nSQL: {result.get('sql', '')}")
        self.output.print(f"SQL类型: {result.get('sql_type', '')}")
        self.output.print(f"复杂度: {complexity}")

        # 评分显示
        if score >= 90:
            self.output.success(f"\n质量评分: {score}/100 - {grade}级 ({assessment})")
        elif score >= 70:
            self.output.warning(f"\n质量评分: {score}/100 - {grade}级 ({assessment})")
        else:
            self.output.error(f"\n质量评分: {score}/100 - {grade}级 ({assessment})")

        # 问题列表
        if issues:
            self.output.warning(f"\n发现问题 ({len(issues)}个):")
            for i, issue in enumerate(issues, 1):
                self.output.print(f"\n  [{i}] {issue}")

        # 建议列表
        if suggestions:
            self.output.success(f"\n优化建议 ({len(suggestions)}个):")
            for i, suggestion in enumerate(suggestions, 1):
                self.output.print(f"\n  [{i}] {suggestion}")

        return 0

    def _analyze_data(self, skill) -> int:
        """分析查询结果数据"""
        params = None
        if self.args.params:
            params = json.loads(self.args.params)

        result = skill.analyze_data(self.args.sql)

        if result.get("success") == "disabled":
            self.output.warning(result.get("message", "数据分析已禁用"))
            return 0

        if not result.get("success"):
            self.output.error(f"分析失败: {result.get('error', '未知错误')}")
            return 1

        # 从标准响应格式的 data 字段获取数据
        data = result.get("data", {})
        row_count = data.get("row_count", 0)
        col_count = len(data.get("columns", []))
        summary = f"分析了{row_count}行{col_count}列数据"

        self.output.print(f"\n{'='*60}")
        self.output.print(f"摘要: {summary}")
        self.output.print(f"{'='*60}")

        self.output.print(f"\nSQL: {self.args.sql}")
        self.output.print(f"行数: {row_count}")
        self.output.print(f"列数: {col_count}")

        # 数据分析
        analysis = data.get("analysis", {})
        if analysis and isinstance(analysis, dict):
            data_types = analysis.get("data_types", {})
            null_counts = analysis.get("null_counts", {})
            statistics = analysis.get("statistics", {})

            if data_types:
                self.output.print(f"\n数据类型:")
                for col_name, col_type in data_types.items():
                    null_count = null_counts.get(col_name, 0)
                    null_info = f" (空值: {null_count})" if null_count > 0 else ""
                    self.output.print(f"  {col_name}: {col_type}{null_info}")

            if statistics and isinstance(statistics, dict):
                self.output.print(f"\n统计信息:")
                for col_name, stats in statistics.items():
                    if isinstance(stats, dict):
                        stat_parts = []
                        if "min" in stats:
                            stat_parts.append(f"min={stats['min']}")
                        if "max" in stats:
                            stat_parts.append(f"max={stats['max']}")
                        if "mean" in stats and stats["mean"] is not None:
                            stat_parts.append(f"mean={stats['mean']}")
                        if stat_parts:
                            self.output.print(f"  {col_name}: {', '.join(stat_parts)}")

        return 0

    def _get_completions(self, skill) -> int:
        """获取SQL补全建议"""
        response = skill.get_suggestions(self.args.partial)

        if response.get("success") == "disabled":
            self.output.warning(response.get("message", "智能补全已禁用"))
            return 0

        if not response.get("success"):
            self.output.error(f"获取补全失败: {response.get('error', '未知错误')}")
            return 1

        # 获取实际数据
        result = response.get("data", {})
        suggestions = result.get("suggestions", [])
        summary = f"找到{len(suggestions)}个补全建议"

        self.output.print(f"\n{'='*60}")
        self.output.print(f"摘要: {summary}")
        self.output.print(f"{'='*60}")

        self.output.print(f"\n输入: {result.get('partial_sql', '')}")

        if suggestions:
            self.output.print(f"\n补全建议:")
            for i, sug in enumerate(suggestions, 1):
                # 类型已经在服务端转换为中文
                type_name = sug.get("type", "其他")
                self.output.print(f"\n  [{i}] {sug.get('text', '')}")
                self.output.print(f"      类型: {type_name}")
                self.output.print(f"      说明: {sug.get('description', '')}")
        else:
            self.output.print("\n无补全建议")

        return 0

    def _get_schema(self, skill) -> int:
        """获取Schema信息"""
        if self.args.table:
            # 单表详情
            result = skill.get_schema_info(self.args.table)

            if not result.get("success"):
                self.output.error(f"获取Schema失败: {result.get('error', '未知错误')}")
                return 1

            summary = f"表 {self.args.table} 的Schema信息"

            self.output.print(f"\n{'='*60}")
            self.output.print(f"摘要: {summary}")
            self.output.print(f"{'='*60}")

            self.output.print(f"\n表名: {result.get('table', '')}")

            # 列信息
            columns = result.get("columns", [])
            if columns:
                self.output.print(f"\n字段 ({len(columns)}个):")
                for col in columns:
                    nullable = "NULL" if col.get("nullable") else "NOT NULL"
                    default = f" DEFAULT {col['default']}" if col.get("default") else ""
                    self.output.print(f"  - {col.get('name', '')} {col.get('type', '')} {nullable}{default}")

            # 索引信息
            indexes = result.get("indexes", [])
            if indexes:
                self.output.print(f"\n索引 ({len(indexes)}个):")
                for idx in indexes:
                    unique = "UNIQUE " if idx.get("unique") else ""
                    self.output.print(f"  - {unique}{idx.get('name', '')} ({', '.join(idx.get('columns', []))})")
        else:
            # 所有表
            tables = skill.list_tables()
            summary = f"数据库共有{len(tables)}个表"

            self.output.print(f"\n{'='*60}")
            self.output.print(f"摘要: {summary}")
            self.output.print(f"{'='*60}")

            if tables:
                self.output.print(f"\n表列表:")
                for i, table in enumerate(tables, 1):
                    self.output.print(f"  {i}. {table}")

        return 0

    def _execute_batch(self, skill) -> int:
        """批量执行SQL文件"""
        import os
        from dbskiter.cli.readonly_middleware import is_readonly_mode

        # 只读模式下禁止批量执行（可能包含写操作）
        if is_readonly_mode():
            self.output.error("只读模式下禁止批量执行SQL文件（可能包含写操作）")
            self.output.info("如需执行此操作，请关闭只读模式（设置DBSKITER_READ_ONLY=false）")
            return 1

        file_path = self.args.file
        if not os.path.exists(file_path):
            self.output.error(f"文件不存在: {file_path}")
            return 1

        # 读取SQL文件
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        # 解析SQL（每行一个，忽略空行和注释）
        sqls = []
        for line in lines:
            line = line.strip()
            if line and not line.startswith('--') and not line.startswith('#'):
                sqls.append(line)

        if not sqls:
            self.output.warning("文件中没有有效的SQL语句")
            return 0

        self.output.print(f"\n批量执行SQL文件: {file_path}")
        self.output.print(f"共{len(sqls)}条SQL语句")
        self.output.print(f"{'='*60}")

        success_count = 0
        fail_count = 0

        for i, sql in enumerate(sqls, 1):
            self.output.print(f"\n[{i}/{len(sqls)}] {sql[:60]}...")
            try:
                result = skill.execute(sql)
                if result.get("success"):
                    self.output.success(f"  成功 ({result.get('row_count', 0)}行)")
                    success_count += 1
                else:
                    self.output.error(f"  失败: {result.get('error', '未知错误')}")
                    fail_count += 1
            except Exception as e:
                self.output.error(f"  失败: {e}")
                fail_count += 1

        self.output.print(f"\n{'='*60}")
        self.output.print(f"批量执行完成: 成功{success_count}个, 失败{fail_count}个")

        return 0 if fail_count == 0 else 1

    def _export_data(self, skill) -> int:
        """导出数据"""
        table = getattr(self.args, 'table', None)
        query = getattr(self.args, 'query', None)
        output = self.args.output
        format = self.args.format
        where = getattr(self.args, 'where', None)
        limit = getattr(self.args, 'limit', None)

        if not table and not query:
            self.output.error("请指定--table或--query参数")
            return 1

        try:
            if table:
                # 导出表
                result = skill.export_table(
                    table_name=table,
                    output_path=output,
                    format=format,
                    where=where,
                    limit=limit
                )
            else:
                # 导出查询
                result = skill.export_query(
                    sql=query,
                    output_path=output,
                    format=format
                )

            if not result.get('success'):
                self.output.error(f"导出失败: {result.get('message', '未知错误')}")
                return 1

            self.output.success(f"\n导出成功!")
            self.output.print(f"文件: {result.get('output_path', output)}")
            self.output.print(f"格式: {result.get('format', format)}")
            self.output.print(f"行数: {result.get('exported_rows', 0)}")

            return 0

        except Exception as e:
            self.output.error(f"导出失败: {e}")
            return 1

    def _import_data(self, skill) -> int:
        """导入数据"""
        from dbskiter.cli.readonly_middleware import is_readonly_mode

        # 只读模式下禁止导入数据（写操作）
        if is_readonly_mode():
            self.output.error("只读模式下禁止导入数据（import属于写操作）")
            self.output.info("如需执行此操作，请关闭只读模式（设置DBSKITER_READ_ONLY=false）")
            return 1

        file_path = self.args.file
        table = self.args.table
        format = self.args.format
        columns = getattr(self.args, 'columns', None)
        batch_size = self.args.batch_size

        import os
        if not os.path.exists(file_path):
            self.output.error(f"文件不存在: {file_path}")
            return 1

        try:
            if format == 'csv':
                cols = columns.split(',') if columns else None
                result = skill.import_csv(
                    input_path=file_path,
                    table_name=table,
                    columns=cols,
                    batch_size=batch_size
                )
            elif format == 'json':
                result = skill.import_json(
                    input_path=file_path,
                    table_name=table,
                    batch_size=batch_size
                )
            elif format == 'sql':
                result = skill.import_sql(file_path)
            else:
                self.output.error(f"不支持的格式: {format}")
                return 1

            if not result.get('success'):
                self.output.error(f"导入失败: {result.get('message', '未知错误')}")
                return 1

            self.output.success(f"\n导入成功!")
            self.output.print(f"表名: {result.get('table', table)}")
            self.output.print(f"行数: {result.get('imported_rows', 0)}")

            return 0

        except Exception as e:
            self.output.error(f"导入失败: {e}")
            return 1

    def _export_stream(self, skill) -> int:
        """流式导出大表数据"""
        table = self.args.table
        output = self.args.output
        format = self.args.format
        where = getattr(self.args, 'where', None)
        batch_size = self.args.batch_size

        try:
            self.output.print(f"开始流式导出表 {table}...")
            self.output.print(f"批次大小: {batch_size}")

            result = skill.export_table_streaming(
                table_name=table,
                output_path=output,
                format=format,
                where=where,
                batch_size=batch_size
            )

            if not result.get('success'):
                self.output.error(f"导出失败: {result.get('message', '未知错误')}")
                return 1

            self.output.success(f"\n流式导出成功!")
            self.output.print(f"文件: {result.get('output_path', output)}")
            self.output.print(f"格式: {result.get('format', format)}")
            self.output.print(f"行数: {result.get('exported_rows', 0)}")

            return 0

        except Exception as e:
            self.output.error(f"流式导出失败: {e}")
            return 1

    def _query_audit_logs(self, skill) -> int:
        """查询审计日志"""
        # 处理清理操作
        cleanup_days = getattr(self.args, 'cleanup', None)
        if cleanup_days is not None:
            try:
                deleted = skill.cleanup_audit_logs(days=cleanup_days)
                self.output.success(f"清理完成: 删除了 {deleted} 条过期记录")
                return 0
            except Exception as e:
                self.output.error(f"清理失败: {e}")
                return 1

        # 显示统计信息
        show_stats = getattr(self.args, 'stats', False)
        if show_stats:
            try:
                stats = skill.get_audit_statistics(days=7)
                self.output.print(f"\n{'='*60}")
                self.output.print("SQL审计统计信息（最近7天）")
                self.output.print(f"{'='*60}")
                self.output.print(f"总记录数: {stats['total_records']}")
                self.output.print(f"成功率: {stats['success_rate']}%")
                self.output.print(f"force使用次数: {stats['force_used_count']}")

                if stats['risk_level_distribution']:
                    self.output.print(f"\n风险等级分布:")
                    for level, count in stats['risk_level_distribution'].items():
                        self.output.print(f"  {level}: {count} 条")

                if stats['operation_distribution']:
                    self.output.print(f"\n操作类型分布:")
                    for op, count in stats['operation_distribution'].items():
                        self.output.print(f"  {op}: {count} 条")

                return 0
            except Exception as e:
                self.output.error(f"获取统计信息失败: {e}")
                return 1

        # 查询审计记录
        risk_level = getattr(self.args, 'risk_level', None)
        hours = getattr(self.args, 'hours', 24)
        limit = getattr(self.args, 'limit', 50)

        try:
            records = skill.get_audit_records(
                risk_level=risk_level,
                hours=hours,
                limit=limit
            )

            if not records:
                self.output.info(f"未找到符合条件的审计记录")
                return 0

            self.output.print(f"\n{'='*60}")
            self.output.print(f"SQL审计日志（最近{hours}小时）")
            if risk_level:
                self.output.print(f"风险等级: {risk_level}")
            self.output.print(f"{'='*60}")

            for i, record in enumerate(records, 1):
                risk = record.get('risk_level', 'SAFE')
                success = record.get('success', True)

                # 根据风险等级和成功状态选择颜色
                if risk in ('CRITICAL', 'HIGH'):
                    status_symbol = "[!]"
                elif risk == 'MEDIUM':
                    status_symbol = "[*]"
                else:
                    status_symbol = "[ ]"

                if not success:
                    status_symbol = "[X]"

                self.output.print(f"\n{status_symbol} 记录 #{i}")
                self.output.print(f"  时间: {record.get('timestamp', 'N/A')}")
                self.output.print(f"  操作: {record.get('operation', 'N/A')}")
                self.output.print(f"  风险等级: {risk}")
                self.output.print(f"  SQL: {record.get('sql_preview', 'N/A')}")

                if record.get('risk_description'):
                    self.output.print(f"  风险描述: {record.get('risk_description')}")

                if record.get('force_used'):
                    self.output.warning(f"  注意: 使用了--force强制执行")

                if not success and record.get('error'):
                    self.output.error(f"  错误: {record.get('error')}")

                if record.get('execution_time_ms'):
                    self.output.print(f"  执行时间: {record.get('execution_time_ms'):.2f}ms")

                if record.get('row_count') is not None:
                    self.output.print(f"  影响行数: {record.get('row_count')}")

            self.output.print(f"\n{'='*60}")
            self.output.print(f"共 {len(records)} 条记录")

            return 0

        except Exception as e:
            self.output.error(f"查询审计日志失败: {e}")
            return 1

    def _print_execute_result(self, result: dict) -> int:
        """打印执行结果"""
        if not result.get("success"):
            self.output.error(f"执行失败: {result.get('error', '未知错误')}")
            return 1

        # 从标准响应格式的 data 字段获取数据
        data = result.get("data", {})
        summary = f"执行成功，返回{data.get('row_count', 0)}行"

        self.output.print(f"\n{'='*60}")
        self.output.print(f"摘要: {summary}")
        self.output.print(f"{'='*60}")

        self.output.print(f"\nSQL: {data.get('sql', '')}")
        self.output.print(f"行数: {data.get('row_count', 0)}")

        if data.get("execution_time"):
            self.output.print(f"耗时: {data['execution_time']:.3f}s")

        # 输出结果表格
        columns = data.get("columns", [])
        rows = data.get("rows", [])

        if columns and rows:
            self.output.print(f"\n结果:")
            # 表头
            header = " | ".join(str(c) for c in columns)
            self.output.print(header)
            self.output.print("-" * len(header))
            # 数据行
            for row in rows[:50]:  # 最多显示50行
                self.output.print(" | ".join(str(cell) for cell in row))
            if len(rows) > 50:
                self.output.print(f"... 还有 {len(rows) - 50} 行")

        return 0
