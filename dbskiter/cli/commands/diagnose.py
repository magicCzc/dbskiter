"""
cli/commands/diagnose.py

数据库诊断命令 - 生产级诊断工具
核心功能：实时诊断、性能分析、锁分析、空间诊断、复制诊断

设计原则：
    1. 覆盖95%日常DBA场景
    2. 命令命名贴近自然语言
    3. 实时诊断优先于历史分析
    4. 提供可操作的优化建议

使用场景：
    - "数据库有点慢" -> diagnose realtime
    - "CPU飙高了" -> diagnose top
    - "有死锁" -> diagnose locks
    - "空间不够了" -> diagnose space
    - "主从延迟" -> diagnose replication
"""

import json
from argparse import ArgumentParser
from typing import Dict, Any

from .base import BaseCommand


class DiagnoseCommand(BaseCommand):
    """数据库诊断命令"""

    name = "diagnose"
    description = "Database Diagnose - 生产级数据库诊断工具"
    help_text = "实时诊断、性能分析、锁分析、空间诊断、复制诊断"

    @classmethod
    def add_arguments(cls, parser: ArgumentParser) -> None:
        """添加诊断命令参数"""
        subparsers = parser.add_subparsers(dest="diagnose_action", help="诊断操作")

        # ==================== P0: 高频场景（每天使用）====================

        # 1. realtime - 实时诊断（数据库有点慢/卡住了）
        realtime_parser = subparsers.add_parser(
            "realtime",
            help="实时诊断 - 分析当前数据库性能问题"
        )
        realtime_parser.add_argument(
            "--threshold",
            type=int,
            default=5,
            help="慢查询阈值（秒，默认5）"
        )

        # 2. top - TOP SQL分析（CPU飙高了）
        top_parser = subparsers.add_parser(
            "top",
            help="TOP SQL - 查看资源消耗最高的SQL"
        )
        top_parser.add_argument(
            "--limit",
            type=int,
            default=10,
            help="返回条数（默认10）"
        )
        top_parser.add_argument(
            "--by",
            choices=["time", "cpu", "io", "rows"],
            default="time",
            help="排序依据（默认time）"
        )

        # 3. locks - 锁分析（有死锁/阻塞）
        locks_parser = subparsers.add_parser(
            "locks",
            help="锁分析 - 检测死锁、阻塞、锁等待"
        )
        locks_parser.add_argument(
            "--kill",
            action="store_true",
            help="显示KILL语句（不执行）"
        )

        # 4. sql - SQL深度分析
        sql_parser = subparsers.add_parser(
            "sql",
            help="SQL诊断 - 深度分析SQL语句性能"
        )
        sql_parser.add_argument("sql", help="SQL语句")
        sql_parser.add_argument(
            "--params",
            help="SQL参数（JSON格式）"
        )

        # 5. space - 空间诊断（空间不够了）
        space_parser = subparsers.add_parser(
            "space",
            help="空间诊断 - 分析表空间、碎片、大表"
        )
        space_parser.add_argument(
            "--top",
            type=int,
            default=20,
            help="显示TOP N大表（默认20）"
        )
        space_parser.add_argument(
            "--min-size",
            type=int,
            default=100,
            help="最小表大小（MB，默认100）"
        )

        # ==================== P1: 中频场景（每周使用）====================

        # 6. connections - 连接分析（连接数满了）
        conn_parser = subparsers.add_parser(
            "connections",
            help="连接分析 - 分析连接池、空闲连接"
        )
        conn_parser.add_argument(
            "--idle",
            action="store_true",
            help="显示空闲连接"
        )

        # 7. replication - 复制诊断（主从延迟）
        repl_parser = subparsers.add_parser(
            "replication",
            help="复制诊断 - 分析主从延迟、复制状态"
        )

        # 8. slow-queries - 历史慢查询分析
        slowlog_parser = subparsers.add_parser(
            "slow-queries",
            aliases=["slowlog"],
            help="慢查询日志 - 分析历史慢查询（支持实时采集和日志文件解析）"
        )
        slowlog_parser.add_argument(
            "--limit",
            type=int,
            default=10,
            help="返回条数（默认10，仅实时模式）"
        )
        slowlog_parser.add_argument(
            "--min-time",
            type=float,
            default=1.0,
            help="最小执行时间（秒，默认1.0）"
        )
        slowlog_parser.add_argument(
            "--log-file",
            help="慢查询日志文件路径（指定则使用日志文件模式）"
        )
        slowlog_parser.add_argument(
            "--since",
            default="24h",
            help="时间范围（如24h表示最近24小时，7d表示最近7天，仅日志模式）"
        )

        # 9. recommend-indexes - 索引建议
        index_parser = subparsers.add_parser(
            "recommend-indexes",
            aliases=["indexes"],
            help="索引建议 - 全库索引分析和建议"
        )
        index_parser.add_argument(
            "--table",
            help="指定表名（默认全库）"
        )

        # ==================== P2: 低频场景（每月使用）====================

        # 10. report - 综合诊断报告
        subparsers.add_parser(
            "report",
            help="综合报告 - 生成完整诊断报告"
        )

        # 11. table - 单表诊断
        table_parser = subparsers.add_parser(
            "table",
            help="表诊断 - 分析单表结构和性能"
        )
        table_parser.add_argument("table_name", help="表名")

        # 12. performance-snapshot - 性能快照
        snapshot_parser = subparsers.add_parser(
            "performance-snapshot",
            help="性能快照 - 采集数据库性能指标"
        )
        snapshot_parser.add_argument(
            "--output",
            "-o",
            help="输出文件路径（JSON格式）"
        )

        # 13. bottleneck - 瓶颈分析
        bottleneck_parser = subparsers.add_parser(
            "bottleneck",
            help="瓶颈分析 - 分析性能瓶颈"
        )
        bottleneck_parser.add_argument(
            "--top",
            type=int,
            default=5,
            help="显示TOP N瓶颈（默认5）"
        )

        # ==================== PostgreSQL特有诊断 ====================

        # 14. vacuum - VACUUM状态分析（PostgreSQL特有）
        vacuum_parser = subparsers.add_parser(
            "vacuum",
            help="VACUUM分析 - 检查表清理状态和死元组（PostgreSQL特有）"
        )

        # 15. bloat - 表膨胀/碎片分析（支持多数据库）
        bloat_parser = subparsers.add_parser(
            "bloat",
            help="膨胀/碎片分析 - 检测表膨胀和碎片情况（PostgreSQL膨胀/MySQL碎片/Oracle表空间碎片）"
        )
        bloat_parser.add_argument(
            "--threshold",
            type=int,
            default=30,
            help="膨胀率阈值（百分比，默认30）"
        )

        # 16. index-usage - 索引使用分析（支持多数据库）
        index_usage_parser = subparsers.add_parser(
            "index-usage",
            help="索引使用分析 - 识别未使用索引和缺失索引（MySQL/Oracle/PostgreSQL）"
        )

        # 17. tablespace-fragmentation - Oracle表空间碎片分析
        subparsers.add_parser(
            "tablespace-fragmentation",
            help="表空间碎片分析 - 分析Oracle表空间碎片情况"
        )

    def execute(self) -> int:
        """执行诊断命令"""
        from dbskiter.db_diagnose.skill import DiagnoseSkill

        action = getattr(self.args, 'diagnose_action', None)

        # 不需要数据库连接的命令（如果有的话）
        # ...

        # 需要数据库连接的命令
        # 诊断命令必须直连数据库，不支持Zabbix/Prometheus外部监控
        try:
            db_name = getattr(self.args, 'database', None)
            configs = self._load_all_configs()
            connector = self._create_connector_for_diagnose(db_name, configs)

            if not connector:
                self.output.error(
                    "无法找到可用的数据库直连配置。\n\n"
                    "诊断命令（慢查询、锁分析、SQL诊断等）必须直连数据库，\n"
                    "不支持通过Zabbix或Prometheus查询。\n\n"
                    "请检查：\n"
                    "1. .env 文件中是否配置了正确的数据库连接信息\n"
                    "2. 使用 --database 参数指定正确的数据库名\n\n"
                    "如需监控Oracle数据库的指标（CPU、内存、磁盘），请使用：\n"
                    "  dbskiter --database=Z18 monitor health"
                )
                return 1

            self._connector = connector

        except Exception as e:
            self.output.error(str(e))
            return 1

        # 数据库特有命令的方言预检查
        # 在连接数据库之前就检查，避免不匹配时还要等待连接重试
        dialect = getattr(self._connector, 'dialect', '') or ''
        dialect_lower = dialect.lower()
        db_specific_commands = {
            'vacuum': {
                'required': 'postgresql',
                'label': 'VACUUM分析',
                'supported': ['postgresql'],
            },
            'tablespace-fragmentation': {
                'required': 'oracle',
                'label': '表空间碎片分析',
                'supported': ['oracle'],
            },
        }
        if action in db_specific_commands:
            cmd_info = db_specific_commands[action]
            if not any(d in dialect_lower for d in cmd_info['supported']):
                self.output.error(
                    f"{cmd_info['label']}仅支持 "
                    f"{'/'.join(cmd_info['supported'])} 数据库，"
                    f"当前数据库类型: {dialect or '未知'}\n\n"
                    f"请使用 --database 参数指定正确的数据库，或检查 .env 中的连接配置。"
                )
                return 1

        skill = None
        try:
            skill = DiagnoseSkill(self.connector)

            if self.output_mode != "rule":
                method_map = {
                    "realtime": lambda: skill.realtime_diagnose(
                        threshold=getattr(self.args, 'threshold', 5)
                    ),
                    "top": lambda: skill.get_top_sql(
                        limit=getattr(self.args, 'limit', 10),
                        order_by=getattr(self.args, 'by', 'time'),
                    ),
                    "locks": lambda: skill.analyze_locks(),
                    "sql": lambda: skill.analyze_sql(self.args.sql),
                    "space": lambda: skill.analyze_space(
                        top_n=getattr(self.args, 'top', 20),
                        min_size_mb=getattr(self.args, 'min_size', 100),
                    ),
                    "connections": lambda: skill.analyze_connections(
                        show_idle=getattr(self.args, 'idle', False),
                    ),
                    "replication": lambda: skill.analyze_replication(),
                    "slow-queries": lambda: skill.analyze_slow_queries(
                        limit=getattr(self.args, 'limit', 10),
                        min_time=getattr(self.args, 'min_time', 1.0),
                        log_file=getattr(self.args, 'log_file', None),
                        since=getattr(self.args, 'since', '24h'),
                    ),
                    "slowlog": lambda: skill.analyze_slow_queries(
                        limit=getattr(self.args, 'limit', 10),
                        min_time=getattr(self.args, 'min_time', 1.0),
                        log_file=getattr(self.args, 'log_file', None),
                        since=getattr(self.args, 'since', '24h'),
                    ),
                    "recommend-indexes": lambda: skill.recommend_indexes(
                        table=getattr(self.args, 'table', None),
                    ),
                    "indexes": lambda: skill.recommend_indexes(
                        table=getattr(self.args, 'table', None),
                    ),
                    "report": lambda: self._generate_report_for_ai_mode(skill),
                    "table": lambda: skill.diagnose_table(self.args.table_name),
                    "performance-snapshot": lambda: skill.take_performance_snapshot(),
                    "bottleneck": lambda: skill.analyze_performance_bottleneck(),
                    "vacuum": lambda: skill.analyze_vacuum(),
                    "bloat": lambda: skill.analyze_bloat(
                        threshold=getattr(self.args, 'threshold', 30),
                    ),
                    "index-usage": lambda: skill.analyze_index_usage(),
                    "tablespace-fragmentation": lambda: skill.analyze_tablespace_fragmentation(),
                }
                scenario_map = {
                    "realtime": "realtime",
                    "top": "top_sql",
                    "locks": "locks",
                    "sql": "sql_analysis",
                    "space": "space",
                    "connections": "connections",
                    "replication": "replication",
                    "slow-queries": "slow_query",
                    "slowlog": "slow_query",
                    "recommend-indexes": "index_recommend",
                    "indexes": "index_recommend",
                    "report": "report",
                    "table": "table",
                    "performance-snapshot": "performance_snapshot",
                    "bottleneck": "bottleneck",
                    "vacuum": "vacuum",
                    "bloat": "bloat",
                    "index-usage": "index_usage",
                    "tablespace-fragmentation": "tablespace_fragmentation",
                }
                return self._execute_ai_mode(skill, action, method_map, scenario_map)

            # P0: 高频场景
            if action == "realtime":
                return self._realtime_diagnose(skill)
            elif action == "top":
                return self._top_sql(skill)
            elif action == "locks":
                return self._analyze_locks(skill)
            elif action == "sql":
                return self._diagnose_sql(skill)
            elif action == "space":
                return self._space_diagnose(skill)

            # P1: 中频场景
            elif action == "connections":
                return self._analyze_connections(skill)
            elif action == "replication":
                return self._replication_diagnose(skill)
            elif action in ("slow-queries", "slowlog"):
                return self._analyze_slowlog(skill)
            elif action in ("recommend-indexes", "indexes"):
                return self._recommend_indexes(skill)

            # P2: 低频场景
            elif action == "report":
                return self._generate_report(skill)
            elif action == "table":
                return self._diagnose_table(skill)
            elif action == "performance-snapshot":
                return self._performance_snapshot(skill)
            elif action == "bottleneck":
                return self._analyze_bottleneck(skill)

            # PostgreSQL特有诊断
            elif action == "vacuum":
                return self._analyze_vacuum(skill)
            elif action == "bloat":
                return self._analyze_bloat(skill)
            elif action == "index-usage":
                return self._analyze_index_usage(skill)

            # Oracle特有诊断
            elif action == "tablespace-fragmentation":
                return self._analyze_tablespace_fragmentation(skill)

            else:
                self.output.error(
                    "请指定诊断操作:\n"
                    "  P0(高频): realtime, top, locks, sql, space\n"
                    "  P1(中频): connections, replication, slow-queries, recommend-indexes\n"
                    "  P2(低频): report, table, performance-snapshot, bottleneck\n"
                    "  PostgreSQL特有: vacuum, bloat, index-usage\n"
                    "  Oracle特有: tablespace-fragmentation"
                )
                return 1

        except Exception as e:
            self.output.error(f"诊断失败: {e}")
            return 1
        finally:
            if skill:
                skill.close()

    # ==================== P0: 高频场景实现 ====================

    def _realtime_diagnose(self, skill) -> int:
        """实时诊断 - 数据库有点慢/卡住了"""
        self.output.info("\n" + "=" * 60)
        self.output.info("实时诊断 - 分析当前数据库性能")
        self.output.info("=" * 60)

        # 1. 检查当前活跃连接
        self.output.info("\n[1] 检查活跃连接...")
        conn_info = skill.get_realtime_connections()
        if conn_info.get('success'):
            data = conn_info.get('data', {})
            self.output.info(f"  总连接数: {data.get('total', 'N/A')}")
            self.output.info(f"  活跃连接: {data.get('active', 'N/A')}")
            self.output.info(f"  慢查询: {data.get('slow_count', 'N/A')}")

        # 2. 检查锁等待
        self.output.info("\n[2] 检查锁等待...")
        lock_info = skill.get_lock_waits()
        if lock_info.get('success'):
            data = lock_info.get('data', {})
            waits = data.get('lock_waits', [])
            if waits:
                self.output.warning(f"  发现 {len(waits)} 个锁等待")
                for w in waits[:3]:
                    self.output.warning(f"    - {w.get('waiting_thread')} 等待 {w.get('blocking_thread')}")
            else:
                self.output.info("  未发现锁等待")

        # 3. 检查TOP SQL
        self.output.info("\n[3] 检查TOP SQL...")
        top_sql = skill.get_top_sql(limit=5, threshold=self.args.threshold)
        if top_sql.get('success'):
            data = top_sql.get('data', {})
            queries = data.get('queries', [])
            if queries:
                self.output.info(f"  发现 {len(queries)} 个慢查询（>{self.args.threshold}秒）:")
                for i, q in enumerate(queries, 1):
                    sql = q.get('sql', '')[:50]
                    exec_time = q.get('exec_time', q.get('time', 0))
                    self.output.info(f"    {i}. [{exec_time:.2f}s] {sql}...")
            else:
                self.output.info("  未发现慢查询")

        # 4. 给出建议
        self.output.info("\n" + "=" * 60)
        self.output.info("诊断建议")
        self.output.info("=" * 60)

        suggestions = []
        conn_data = conn_info.get('data', {}) if conn_info.get('success') else {}
        if conn_data.get('total', 0) > 100:
            suggestions.append(f"连接数过多({conn_data.get('total')})，检查连接池配置")
        if conn_data.get('slow_count', 0) > 5:
            suggestions.append(f"发现{conn_data.get('slow_count')}个慢查询，执行diagnose slow-queries查看详情")

        lock_data = lock_info.get('data', {}) if lock_info.get('success') else {}
        if lock_data.get('lock_waits', []):
            suggestions.append(f"存在{len(lock_data.get('lock_waits', []))}个锁等待，检查长事务")

        top_data = top_sql.get('data', {}) if top_sql.get('success') else {}
        if top_data.get('queries', []):
            suggestions.append(f"发现{len(top_data.get('queries', []))}个高耗SQL，执行diagnose top查看详情")

        if suggestions:
            for s in suggestions:
                self.output.info(f"  - {s}")
        else:
            self.output.info("  数据库运行正常，暂无优化建议")

        return 0

    def _top_sql(self, skill) -> int:
        """TOP SQL分析 - CPU飙高了"""
        result = skill.get_top_sql(
            limit=self.args.limit,
            order_by=self.args.by
        )

        if not result.get('success'):
            self.output.error(f"获取TOP SQL失败: {self._extract_error_message(result)}")
            return 1

        data = result.get('data', {})
        queries = data.get('queries', [])

        self.output.info("\n" + "=" * 60)
        self.output.info(f"TOP SQL - 按{self.args.by}排序")
        self.output.info("=" * 60)

        if not queries:
            self.output.info("\n未发现TOP SQL")
            return 0

        self.output.info(f"\n共 {len(queries)} 条SQL:\n")

        for i, q in enumerate(queries, 1):
            exec_time = q.get('exec_time', q.get('time', 0))
            self.output.info(f"[{i}] 平均执行时间: {exec_time:.3f}s")
            if q.get('total_time'):
                self.output.info(f"    总执行时间: {q.get('total_time', 0):.2f}s")
            if q.get('executions'):
                self.output.info(f"    执行次数: {q.get('executions')}")
            if q.get('sql_id'):
                self.output.info(f"    SQL ID: {q.get('sql_id')}")
            # 兼容MySQL和Oracle的不同字段
            rows_examined = q.get('rows_examined', q.get('buffer_gets', 0))
            rows_sent = q.get('rows_sent', q.get('disk_reads', 0))
            self.output.info(f"    逻辑读: {rows_examined}")
            self.output.info(f"    物理读: {rows_sent}")
            if q.get('cpu_time'):
                self.output.info(f"    CPU时间: {q.get('cpu_time', 0):.3f}s")
            self.output.info(f"    SQL: {q.get('sql', '')[:100]}...")
            if q.get('suggestion'):
                self.output.info(f"    建议: {q.get('suggestion')}")
            self.output.info("")

        return 0

    def _analyze_locks(self, skill) -> int:
        """锁分析 - 有死锁/阻塞"""
        result = skill.analyze_locks()

        if not result.get('success'):
            self.output.error(f"锁分析失败: {self._extract_error_message(result)}")
            return 1

        data = result.get('data', {})

        self.output.info("\n" + "=" * 60)
        self.output.info("锁分析结果")
        self.output.info("=" * 60)

        # 死锁
        deadlocks = data.get('deadlocks', [])
        if deadlocks:
            self.output.warning(f"\n[死锁] 发现 {len(deadlocks)} 个死锁:")
            for d in deadlocks:
                self.output.warning(f"  时间: {d.get('timestamp')}")
                self.output.warning(f"  详情: {d.get('detail', 'N/A')[:100]}")
        else:
            self.output.info("\n[死锁] 未发现死锁")

        # 锁等待
        lock_waits = data.get('lock_waits', [])
        if lock_waits:
            self.output.warning(f"\n[锁等待] 发现 {len(lock_waits)} 个锁等待:")
            for w in lock_waits:
                self.output.warning(f"  等待线程: {w.get('waiting_thread')}")
                self.output.warning(f"  阻塞线程: {w.get('blocking_thread')}")
                self.output.warning(f"  等待时间: {w.get('wait_time', 0)}s")
                self.output.warning(f"  SQL: {w.get('sql', 'N/A')[:50]}...")
                if self.args.kill:
                    self.output.info(f"  KILL语句: KILL {w.get('blocking_thread')}")
        else:
            self.output.info("\n[锁等待] 未发现锁等待")

        # 锁统计
        stats = data.get('statistics', {})
        if stats:
            self.output.info(f"\n[统计] 当前锁状态:")
            self.output.info(f"  表锁: {stats.get('table_locks', 0)}")
            self.output.info(f"  行锁: {stats.get('row_locks', 0)}")

        return 0

    def _diagnose_sql(self, skill) -> int:
        """SQL深度分析"""
        params = None
        if self.args.params:
            params = json.loads(self.args.params)

        result = skill.analyze_sql(self.args.sql, params)

        # 处理标准响应格式
        if isinstance(result, dict) and 'data' in result:
            data = result.get('data', {})
            score = data.get('score', 0)
            issues = data.get('issues', [])
        else:
            # 向后兼容
            data = result
            score = result.get('score', 0)
            issues = result.get('issues', [])

        summary = f"SQL评分{score}/100，发现{len(issues)}个问题"
        self.output.info("\n" + "=" * 60)
        self.output.info(f"摘要: {summary}")
        self.output.info("=" * 60)

        self.output.info(f"\nSQL: {data.get('sql', self.args.sql)[:200]}")
        self.output.info(f"类型: {data.get('sql_type', 'UNKNOWN')}")
        self.output.info(f"评分: {score}/100")

        if issues:
            self.output.warning(f"\n发现问题 ({len(issues)}个):")
            for issue in issues:
                severity = issue.get('severity', 'info')
                # 支持description和message两种字段名
                msg = issue.get('description') or issue.get('message', '')
                issue_type = issue.get('issue_type', '')

                if severity == 'critical' or severity == 'high':
                    self.output.error(f"  [严重] {msg}")
                elif severity == 'medium' or severity == 'warning':
                    self.output.warning(f"  [警告] {msg}")
                else:
                    self.output.info(f"  [提示] {msg}")

                # 显示详细信息
                if issue.get('suggestion'):
                    suggestion = issue.get('suggestion')
                    if isinstance(suggestion, dict):
                        if suggestion.get('reason'):
                            self.output.info(f"    原因: {suggestion.get('reason')}")
                        if suggestion.get('create_sql'):
                            self.output.info(f"    SQL: {suggestion.get('create_sql')}")
                    else:
                        self.output.info(f"    建议: {suggestion}")

                # 显示问题类型
                if issue_type:
                    self.output.info(f"    类型: {issue_type}")

        optimizations = data.get('optimizations', [])
        if optimizations:
            self.output.success(f"\n优化建议 ({len(optimizations)}个):")
            for opt in optimizations:
                self.output.info(f"  [{opt.get('type')}] {opt.get('description')}")
                if opt.get('sql'):
                    self.output.info(f"    重写: {opt.get('sql')[:100]}...")

        return 0

    def _space_diagnose(self, skill) -> int:
        """空间诊断 - 空间不够了"""
        result = skill.analyze_space(
            top_n=self.args.top,
            min_size_mb=self.args.min_size
        )

        if not result.get('success'):
            self.output.error(f"空间诊断失败: {self._extract_error_message(result)}")
            return 1

        data = result.get('data', {})

        self.output.info("\n" + "=" * 60)
        self.output.info("空间诊断结果")
        self.output.info("=" * 60)

        # 总体空间 - 支持GB和MB两种单位
        total = data.get('total_space', {})
        self.output.info(f"\n[总体空间]")

        # 优先使用GB单位，如果没有则使用MB单位转换
        if 'total_gb' in total:
            self.output.info(f"  总大小: {total.get('total_gb', 0):.2f} GB")
            self.output.info(f"  数据大小: {total.get('data_gb', 0):.2f} GB")
            self.output.info(f"  索引大小: {total.get('index_gb', 0):.2f} GB")
            self.output.info(f"  剩余空间: {total.get('free_gb', 0):.2f} GB")
        elif 'total_mb' in total:
            # PostgreSQL返回的是MB单位
            self.output.info(f"  总大小: {total.get('total_mb', 0):.2f} MB ({total.get('total_mb', 0)/1024:.2f} GB)")
            self.output.info(f"  数据大小: {total.get('data_mb', 0):.2f} MB ({total.get('data_mb', 0)/1024:.2f} GB)")
            self.output.info(f"  索引大小: {total.get('index_mb', 0):.2f} MB ({total.get('index_mb', 0)/1024:.2f} GB)")
            if 'free_gb' in total:
                self.output.info(f"  剩余空间: {total.get('free_gb', 0):.2f} GB")
        else:
            self.output.info(f"  总大小: 0.00 GB")
            self.output.info(f"  数据大小: 0.00 GB")
            self.output.info(f"  索引大小: 0.00 GB")
            self.output.info(f"  剩余空间: 0.00 GB")

        # TOP大表
        tables = data.get('large_tables', [])
        if tables:
            self.output.info(f"\n[TOP {len(tables)} 大表]")
            for i, t in enumerate(tables, 1):
                self.output.info(
                    f"  {i}. {t.get('table')}: "
                    f"{t.get('size_mb', 0):.1f} MB "
                    f"(数据: {t.get('data_mb', 0):.1f} MB, "
                    f"索引: {t.get('index_mb', 0):.1f} MB)"
                )
                if t.get('fragmentation', 0) > 20:
                    self.output.warning(f"     碎片率: {t.get('fragmentation'):.1f}% (建议优化)")

        # 建议
        suggestions = data.get('suggestions', [])
        if suggestions:
            self.output.info("\n[优化建议]")
            for s in suggestions:
                if isinstance(s, dict):
                    priority = s.get('priority', '')
                    suggestion_text = s.get('suggestion', s.get('description', ''))
                    if priority == 'high':
                        self.output.warning(f"  - [高] {suggestion_text}")
                    elif priority == 'medium':
                        self.output.info(f"  - [中] {suggestion_text}")
                    else:
                        self.output.info(f"  - [低] {suggestion_text}")
                else:
                    self.output.info(f"  - {s}")

        return 0

    # ==================== P1: 中频场景实现 ====================

    def _analyze_connections(self, skill) -> int:
        """连接分析"""
        result = skill.analyze_connections(show_idle=self.args.idle)

        if not result.get('success'):
            self.output.error(f"连接分析失败: {self._extract_error_message(result)}")
            return 1

        data = result.get('data', {})

        self.output.info("\n" + "=" * 60)
        self.output.info("连接分析结果")
        self.output.info("=" * 60)

        # 连接统计
        stats = data.get('statistics', {})
        self.output.info(f"\n[连接统计]")
        self.output.info(f"  最大连接数: {stats.get('max_connections', 'N/A')}")
        self.output.info(f"  当前连接: {stats.get('current', 'N/A')}")
        self.output.info(f"  活跃连接: {stats.get('active', 'N/A')}")
        self.output.info(f"  空闲连接: {stats.get('idle', 'N/A')}")
        self.output.info(f"  使用率: {stats.get('usage_percent', 0):.1f}%")

        if stats.get('usage_percent', 0) > 80:
            self.output.warning("  警告: 连接使用率超过80%，建议优化")

        # 连接详情
        if self.args.idle:
            idle_conns = data.get('idle_connections', [])
            if idle_conns:
                self.output.info(f"\n[空闲连接 TOP {len(idle_conns)}]")
                for c in idle_conns[:10]:
                    self.output.info(
                        f"  ID: {c.get('id')}, "
                        f"用户: {c.get('user')}, "
                        f"空闲: {c.get('idle_time', 0)}s"
                    )

        return 0

    def _replication_diagnose(self, skill) -> int:
        """复制诊断"""
        result = skill.analyze_replication()

        if not result.get('success'):
            self.output.error(f"复制诊断失败: {self._extract_error_message(result)}")
            return 1

        data = result.get('data', {})

        self.output.info("\n" + "=" * 60)
        self.output.info("复制诊断结果")
        self.output.info("=" * 60)

        # 复制状态
        status = data.get('status', {})
        is_master = status.get('is_master', False)
        is_slave = status.get('is_slave', False)

        if is_master:
            self.output.info("\n[主库状态]")
            self.output.info(f"  角色: Master")
            self.output.info(f"  Binlog: {status.get('binlog_enabled', False)}")
            self.output.info(f"  从库数: {status.get('slave_count', 0)}")

        if is_slave:
            self.output.info("\n[从库状态]")
            slave_status = data.get('slave_status', {})

            io_running = slave_status.get('io_running', 'No')
            sql_running = slave_status.get('sql_running', 'No')
            delay = slave_status.get('delay_seconds', 0)

            self.output.info(f"  IO线程: {io_running}")
            self.output.info(f"  SQL线程: {sql_running}")
            self.output.info(f"  延迟: {delay} 秒")

            if io_running != 'Yes' or sql_running != 'Yes':
                self.output.error("  错误: 复制线程未运行!")
            elif delay > 60:
                self.output.warning(f"  警告: 复制延迟超过60秒!")
            else:
                self.output.info("  状态: 正常")

        if not is_master and not is_slave:
            self.output.info("\n[复制状态]")
            self.output.info("  当前实例未配置主从复制")

        return 0

    def _analyze_slowlog(self, skill) -> int:
        """历史慢查询分析（支持实时和日志文件模式）"""
        # 检查是否使用日志文件模式
        log_file = getattr(self.args, 'log_file', None)

        if log_file:
            # 日志文件模式
            self.output.info(f"\n分析慢查询日志文件: {log_file}")
            result = skill.analyze_slow_queries(
                min_time=self.args.min_time,
                log_file=log_file,
                since=getattr(self.args, 'since', '24h')
            )
        else:
            # 实时模式
            result = skill.analyze_slow_queries(
                limit=self.args.limit,
                min_time=self.args.min_time
            )

        if not result.get('success'):
            self.output.error(f"慢查询分析失败: {self._extract_error_message(result)}")
            return 1

        data = result.get('data', {})

        # 检查是否是增强版报告格式
        if 'summary' in data:
            return self._display_enhanced_report(data)

        # 兼容旧格式
        queries = data.get('queries', [])

        self.output.info("\n" + "=" * 60)
        self.output.info(f"慢查询分析结果 (>{self.args.min_time}s)")
        self.output.info("=" * 60)

        if not queries:
            self.output.info(f"\n未发现慢查询（>{self.args.min_time}秒）")
            return 0

        self.output.info(f"\n共 {len(queries)} 条慢查询:\n")

        for i, q in enumerate(queries, 1):
            self.output.info(f"[{i}] SQL: {q.get('sql', '')[:80]}...")
            self.output.info(f"    执行时间: {q.get('query_time', 0):.3f}s")
            self.output.info(f"    扫描行数: {q.get('rows_examined', 0)}")
            self.output.info(f"    返回行数: {q.get('rows_sent', 0)}")
            self.output.info("")

        return 0

    def _display_enhanced_report(self, data: Dict) -> int:
        """显示增强版慢查询报告"""
        summary = data.get('summary', {})
        patterns = data.get('top_patterns', [])
        recommendations = data.get('recommendations', [])

        self.output.info("\n" + "=" * 70)
        self.output.info("慢查询分析报告（增强版）")
        self.output.info("=" * 70)

        # 汇总信息
        self.output.info(f"\n【汇总统计】")
        self.output.info(f"  总查询数: {summary.get('total_queries', 0)}")
        self.output.info(f"  唯一模式: {summary.get('unique_patterns', 0)}")
        self.output.info(f"  总耗时: {summary.get('total_time', 0):.2f}秒")
        self.output.info(f"  平均耗时: {summary.get('avg_time', 0):.3f}秒")

        time_range = summary.get('time_range', [None, None])
        if time_range[0] and time_range[1]:
            self.output.info(f"  时间范围: {time_range[0]} ~ {time_range[1]}")

        # TOP查询模式
        if patterns:
            self.output.info(f"\n【TOP {len(patterns)} 查询模式】")
            for i, p in enumerate(patterns, 1):
                self.output.info(f"\n[{i}] 指纹: {p.get('fingerprint', '')[:60]}...")
                self.output.info(f"    SQL示例: {p.get('sql_pattern', '')[:80]}...")
                self.output.info(f"    执行次数: {p.get('count', 0)}")
                self.output.info(f"    总耗时: {p.get('total_time', 0):.2f}秒")
                self.output.info(f"    平均耗时: {p.get('avg_time', 0):.3f}秒")
                self.output.info(f"    P95耗时: {p.get('p95_time', 0):.3f}秒")
                self.output.info(f"    扫描行数: {p.get('rows_examined', 0)}")
                self.output.info(f"    返回行数: {p.get('rows_sent', 0)}")

        # 优化建议
        if recommendations:
            self.output.info(f"\n【优化建议】")
            for i, rec in enumerate(recommendations, 1):
                self.output.info(f"  {i}. {rec}")

        self.output.info("\n" + "=" * 70)
        return 0

    def _recommend_indexes(self, skill) -> int:
        """索引建议"""
        result = skill.recommend_indexes(table=self.args.table)

        if not result.get('success'):
            self.output.error(f"索引建议失败: {self._extract_error_message(result)}")
            return 1

        data = result.get('data', {})
        # 兼容两种字段名：suggestions（skill层返回）和indexes（旧格式）
        suggestions = data.get('suggestions', data.get('indexes', []))

        self.output.info("\n" + "=" * 60)
        self.output.info("索引建议")
        self.output.info("=" * 60)

        if not suggestions:
            self.output.info("\n暂无索引建议")
            return 0

        summary = data.get('summary', {})
        if summary:
            self.output.info(f"\n总计: {summary.get('total', len(suggestions))} 条建议")
            self.output.info(f"  高优先级: {summary.get('high_priority', 0)}")
            self.output.info(f"  中优先级: {summary.get('medium_priority', 0)}")
            self.output.info(f"  低优先级: {summary.get('low_priority', 0)}")

        # 按类型分组展示
        type_labels = {
            'missing_index': '缺失索引',
            'redundant_index': '冗余索引',
            'unused_index': '未使用索引',
            'low_cardinality': '低基数索引',
            'low_selectivity': '低选择性索引',
        }

        priority_labels = {
            'high': '[高]',
            'medium': '[中]',
            'low': '[低]',
        }

        for i, s in enumerate(suggestions, 1):
            s_type = s.get('type', 'unknown')
            type_label = type_labels.get(s_type, s_type)
            priority = s.get('priority', 'low')
            priority_label = priority_labels.get(priority, f'[{priority}]')

            self.output.info(f"\n{i}. {priority_label} {type_label}")

            # 根据类型展示不同详情
            if s_type == 'missing_index':
                sql_preview = s.get('sql_preview', '')
                sql_id = s.get('sql_id', '')
                elapsed = s.get('elapsed_sec', 0)
                executions = s.get('executions', 0)
                if sql_id:
                    self.output.info(f"   SQL ID: {sql_id}")
                if sql_preview:
                    self.output.info(f"   SQL: {sql_preview}")
                self.output.info(f"   耗时: {elapsed}秒, 执行次数: {executions}")
                self.output.info(f"   原因: {s.get('reason', '')}")
                self.output.info(f"   建议: {s.get('suggestion', '')}")

            elif s_type == 'redundant_index':
                self.output.info(f"   表: {s.get('table', '')}")
                self.output.info(f"   索引: {s.get('index', '')}")
                self.output.info(f"   列: {s.get('columns', '')}")
                self.output.info(f"   原因: {s.get('reason', '')}")
                self.output.info(f"   建议: {s.get('suggestion', '')}")

            elif s_type in ('unused_index', 'low_cardinality', 'low_selectivity'):
                self.output.info(f"   表: {s.get('table', '')}")
                self.output.info(f"   索引: {s.get('index', '')}")
                if s.get('column'):
                    self.output.info(f"   列: {s.get('column')}")
                if s.get('distinct_keys') is not None:
                    self.output.info(f"   不同键数: {s.get('distinct_keys')}")
                if s.get('selectivity_percent') is not None:
                    self.output.info(f"   选择性: {s.get('selectivity_percent')}%")
                self.output.info(f"   原因: {s.get('reason', '')}")
                self.output.info(f"   建议: {s.get('suggestion', '')}")

            else:
                # 通用展示
                table_name = s.get('table', '')
                if table_name:
                    self.output.info(f"   表: {table_name}")
                self.output.info(f"   描述: {s.get('description', s.get('reason', ''))}")
                if s.get('suggestion'):
                    self.output.info(f"   建议: {s.get('suggestion')}")
                if s.get('sql'):
                    self.output.info(f"   SQL: {s.get('sql')}")

        return 0

    # ==================== P2: 低频场景实现 ====================

    def _generate_report(self, skill) -> int:
        """生成综合性能诊断报告（Markdown格式）

        功能定位：与 inspector report 区分
        - inspector report: 健康巡检（配置、安全、容量等静态检查）
        - diagnose report: 性能诊断（实时性能、慢查询、瓶颈等动态分析）

        报告版本: v2.0 - 基于DeepSeek建议优化
        """
        from datetime import datetime
        from .diagnose_report_generator import DiagnoseReportGenerator

        # 获取数据库信息
        db_name = self.args.database or "unknown"
        db_type = self.connector.dialect if self.connector else "unknown"

        self.output.info("\n" + "=" * 60)
        self.output.info("生成综合性能诊断报告")
        self.output.info("=" * 60)

        # 收集各项诊断结果
        self.output.info("\n[1] 性能快照...")
        snapshot_result = skill.take_performance_snapshot()

        self.output.info("[2] 瓶颈分析...")
        bottleneck_result = skill.analyze_performance_bottleneck()

        self.output.info("[3] 慢查询分析...")
        slow_queries_result = skill.get_realtime_connections()

        self.output.info("[4] 空间分析...")
        space_result = skill.analyze_space(top_n=10, min_size_mb=1, database=db_name)

        # 创建SQL分析器用于生成索引建议
        from dbskiter.db_diagnose.analyzers.sql_analyzer import SQLAnalyzer
        sql_analyzer = SQLAnalyzer(self.connector)

        # 使用新的报告生成器生成报告
        generator = DiagnoseReportGenerator(sql_analyzer=sql_analyzer)
        report_content = generator.generate_report(
            db_name=db_name,
            db_type=db_type,
            snapshot_result=snapshot_result,
            bottleneck_result=bottleneck_result,
            space_result=space_result,
            slow_queries_result=slow_queries_result
        )

        # 显示报告摘要到控制台
        self.output.info("\n" + "=" * 60)
        self.output.info("诊断报告摘要")
        self.output.info("=" * 60)

        for issue in generator.issue_list:
            self.output.warning(f"  - {issue}")

        if generator.issues_found == 0:
            self.output.success("\n  数据库整体性能良好，未发现明显问题")
        else:
            self.output.info(f"\n  共发现 {generator.issues_found} 个性能问题，建议进一步分析")

        # 确定输出文件路径
        if hasattr(self.args, 'output') and self.args.output:
            report_file = self.args.output
        else:
            # 生成默认文件名（Markdown格式）
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            report_file = f"db_performance_report_{db_name}_{timestamp}.md"

        # 保存Markdown报告
        try:
            with open(report_file, 'w', encoding='utf-8') as f:
                f.write(report_content)
            self.output.info(f"\n[报告保存]")
            self.output.info(f"  性能诊断报告已保存到: {report_file}")
        except Exception as e:
            self.output.error(f"\n[错误] 保存报告失败: {e}")

        return 0

    def _generate_report_for_ai_mode(self, skill) -> Dict[str, Any]:
        """为AI模式生成综合性能诊断报告（返回字典格式）"""
        from datetime import datetime

        # 获取数据库信息
        db_name = self.args.database or "unknown"
        db_type = self.connector.dialect if self.connector else "unknown"

        # 收集各项诊断结果
        snapshot_result = skill.take_performance_snapshot()
        bottleneck_result = skill.analyze_performance_bottleneck()
        space_result = skill.analyze_space(top_n=10, min_size_mb=1, database=db_name)

        # 构建报告数据
        report_data = {
            "database": db_name,
            "database_type": db_type,
            "generated_at": datetime.now().isoformat(),
            "performance_snapshot": snapshot_result.get('data', {}),
            "bottleneck_analysis": bottleneck_result.get('data', {}),
            "space_analysis": space_result.get('data', {}),
        }

        return {
            "success": True,
            "message": "综合性能诊断报告生成完成",
            "data": report_data
        }

    def _diagnose_table(self, skill) -> int:
        """单表诊断"""
        result = skill.diagnose_table(self.args.table_name)

        if not result.get('success'):
            self.output.error(f"表诊断失败: {self._extract_error_message(result)}")
            return 1

        data = result.get('data', {})

        self.output.info("\n" + "=" * 60)
        self.output.info(f"表诊断: {self.args.table_name}")
        self.output.info("=" * 60)

        # 基本信息
        self.output.info(f"\n[基本信息]")
        self.output.info(f"  数据库类型: {data.get('dialect', 'N/A')}")

        # 统计信息
        stats = data.get('statistics', {})
        if stats:
            row_count = stats.get('row_count')
            size_mb = stats.get('size_mb')
            if row_count is not None:
                self.output.info(f"  行数: {row_count:,}")
            else:
                self.output.info(f"  行数: N/A")
            if size_mb is not None:
                self.output.info(f"  大小: {size_mb:.2f} MB")
            else:
                self.output.info(f"  大小: N/A")
        else:
            self.output.info(f"  行数: N/A")
            self.output.info(f"  大小: N/A")

        # 索引信息
        indexes = data.get('indexes', [])
        if indexes:
            self.output.info(f"\n[索引] 共 {len(indexes)} 个")
            for idx in indexes:
                self.output.info(f"  - {idx.get('name')}: {idx.get('columns')}")
        else:
            self.output.info(f"\n[索引] 无索引信息")

        # 问题
        issues = data.get('issues', [])
        if issues:
            self.output.info(f"\n[发现问题] 共 {len(issues)} 个")
            for issue in issues:
                self.output.warning(f"  - {issue}")

        # 建议
        suggestions = data.get('suggestions', [])
        if suggestions:
            self.output.info(f"\n[优化建议]")
            for s in suggestions:
                if isinstance(s, dict):
                    priority = s.get('priority', '')
                    suggestion_text = s.get('suggestion', s.get('description', ''))
                    if priority == 'high':
                        self.output.warning(f"  - [高] {suggestion_text}")
                    elif priority == 'medium':
                        self.output.info(f"  - [中] {suggestion_text}")
                    else:
                        self.output.info(f"  - [低] {suggestion_text}")
                else:
                    self.output.info(f"  - {s}")

        return 0

    def _performance_snapshot(self, skill) -> int:
        """性能快照"""
        result = skill.take_performance_snapshot()

        if not result.get('success'):
            self.output.error(f"性能快照采集失败: {self._extract_error_message(result)}")
            return 1

        data = result.get('data', {})
        snapshot = data.get('snapshot', {})
        summary = data.get('summary', {})

        self.output.info("\n" + "=" * 60)
        self.output.info("性能快照")
        self.output.info("=" * 60)

        # 基础信息
        self.output.info(f"\n[基本信息]")
        self.output.info(f"  采集时间: {snapshot.get('timestamp', 'N/A')}")
        self.output.info(f"  数据库类型: {self.connector.dialect if self.connector else 'N/A'}")
        self.output.info(f"  活跃会话: {snapshot.get('active_sessions', 0)}")
        self.output.info(f"  总会话: {snapshot.get('total_sessions', 0)}")
        self.output.info(f"  慢查询数: {len(snapshot.get('slow_queries', []))}")
        self.output.info(f"  指标数量: {len(snapshot.get('metrics', []))}")

        # 按类别分组显示指标
        metrics = snapshot.get('metrics', [])
        if metrics:
            # CPU指标
            cpu_metrics = [m for m in metrics if m.get('category') == 'cpu']
            if cpu_metrics:
                self.output.info(f"\n[CPU]")
                for m in cpu_metrics:
                    self.output.info(f"  {m.get('name', 'N/A')}: {m.get('value', 0):.2f}{m.get('unit', '')}")

            # 内存指标
            memory_metrics = [m for m in metrics if m.get('category') == 'memory']
            if memory_metrics:
                self.output.info(f"\n[内存]")
                for m in memory_metrics:
                    self.output.info(f"  {m.get('name', 'N/A')}: {m.get('value', 0):.2f}{m.get('unit', '')}")

            # IO指标
            io_metrics = [m for m in metrics if m.get('category') == 'io']
            if io_metrics:
                self.output.info(f"\n[IO]")
                for m in io_metrics:
                    self.output.info(f"  {m.get('name', 'N/A')}: {m.get('value', 0):.2f}{m.get('unit', '')}")

            # 并发指标
            concurrency_metrics = [m for m in metrics if m.get('category') == 'concurrency']
            if concurrency_metrics:
                self.output.info(f"\n[并发]")
                for m in concurrency_metrics:
                    self.output.info(f"  {m.get('name', 'N/A')}: {m.get('value', 0):.2f}{m.get('unit', '')}")

            # 锁指标
            lock_metrics = [m for m in metrics if m.get('category') == 'lock']
            if lock_metrics:
                self.output.info(f"\n[锁]")
                for m in lock_metrics:
                    self.output.info(f"  {m.get('name', 'N/A')}: {m.get('value', 0):.2f}{m.get('unit', '')}")

        # 慢查询列表（前5条）
        slow_queries = snapshot.get('slow_queries', [])
        if slow_queries:
            self.output.info(f"\n[慢查询 TOP 5]")
            for i, q in enumerate(slow_queries[:5], 1):
                sql = q.get('sql_text', 'N/A')[:50] if q.get('sql_text') else 'N/A'
                self.output.info(f"  {i}. {sql}...")
                self.output.info(f"     平均时间: {q.get('avg_time_ms', 0):.2f}ms, 执行次数: {q.get('execution_count', 0)}")

        # 保存到文件
        if self.args.output:
            import json
            try:
                with open(self.args.output, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                self.output.info(f"\n[保存] 快照已保存到: {self.args.output}")
            except Exception as e:
                self.output.error(f"保存失败: {e}")

        return 0

    def _analyze_bottleneck(self, skill) -> int:
        """瓶颈分析"""
        result = skill.analyze_performance_bottleneck()

        if not result.get('success'):
            self.output.error(f"瓶颈分析失败: {self._extract_error_message(result)}")
            return 1

        data = result.get('data', {})
        bottlenecks = data.get('bottlenecks', [])
        summary = data.get('summary', {})
        recommendations = data.get('recommendations', [])

        self.output.info("\n" + "=" * 60)
        self.output.info("性能瓶颈分析")
        self.output.info("=" * 60)

        # 统计信息
        if summary:
            self.output.info(f"\n[统计]")
            self.output.info(f"  严重: {summary.get('critical', 0)} 个")
            self.output.info(f"  高: {summary.get('high', 0)} 个")
            self.output.info(f"  中: {summary.get('medium', 0)} 个")
            self.output.info(f"  低: {summary.get('low', 0)} 个")

        # 瓶颈详情
        if bottlenecks:
            self.output.info(f"\n[瓶颈详情] TOP {min(len(bottlenecks), self.args.top)}")
            for i, b in enumerate(bottlenecks[:self.args.top], 1):
                category = b.get('category', 'unknown')
                severity = b.get('severity', 'unknown')
                description = b.get('description', '')
                suggestion = b.get('suggestion', '')
                metrics = b.get('metrics', [])

                if severity == 'critical':
                    self.output.error(f"\n  [{i}] [严重] {category}")
                elif severity == 'high':
                    self.output.warning(f"\n  [{i}] [高] {category}")
                elif severity == 'medium':
                    self.output.info(f"\n  [{i}] [中] {category}")
                else:
                    self.output.info(f"\n  [{i}] [低] {category}")

                # 显示描述或建议
                if description:
                    self.output.info(f"      描述: {description}")
                elif suggestion:
                    self.output.info(f"      描述: {suggestion}")

                # 显示具体指标数值
                if metrics:
                    self.output.info(f"      指标:")
                    for m in metrics:
                        metric_name = m.get('name', 'N/A')
                        metric_value = m.get('value', 0)
                        metric_unit = m.get('unit', '')
                        metric_severity = m.get('severity', 'normal')
                        self.output.info(f"        - {metric_name}: {metric_value:.2f}{metric_unit} [{metric_severity}]")
        else:
            self.output.info("\n[瓶颈详情] 未发现明显瓶颈")

        # 建议
        if recommendations:
            self.output.info(f"\n[优化建议]")
            for i, rec in enumerate(recommendations[:10], 1):
                self.output.info(f"  {i}. {rec}")

        return 0

    # ==================== 智能连接器选择（诊断专用）====================

    def _load_all_configs(self) -> Dict[str, Any]:
        """
        加载所有可用的数据库配置
        
        使用 MultiDBConfig 动态发现所有配置的数据库实例

        返回:
            Dict: 配置字典，key为实例名，value为配置对象
        """
        from dbskiter.cli.config import MultiDBConfig

        multi_config = MultiDBConfig()
        return multi_config.load_all_configs()

    def _create_connector_for_diagnose(self, db_name: str, configs: Dict[str, Any]):
        """
        创建诊断专用的数据库连接器

        诊断命令（慢查询、锁分析、SQL诊断等）必须直连数据库，
        不支持通过Zabbix或Prometheus查询。

        参数:
            db_name: 数据库名称（如 'Z18', 'jump', 'chenzc'）
            configs: 配置字典，key为实例名，value为Config对象

        返回:
            UnifiedConnector: 数据库连接器，或 None（如果无法直连）
        """
        import logging
        from dbskiter.shared.unified_connector import UnifiedConnector
        from dbskiter.cli.config import Config
        from dbskiter.shared.oracle_metrics import OracleHostMapping

        logger = logging.getLogger(__name__)

        # 1. 如果指定了 db_name，尝试在配置中查找匹配
        if db_name:
            # 1.1 首先尝试匹配数据库名
            for instance_name, config in configs.items():
                if config.database == db_name:
                    logger.info(f"找到匹配配置 [{instance_name}]: {config.host}/{config.database}")
                    return UnifiedConnector(
                        dialect=config.dialect,
                        host=config.host,
                        port=config.port,
                        username=config.username,
                        password=config.password,
                        database=config.database,
                        **config.extra
                    )
            
            # 1.2 尝试匹配主机名
            for instance_name, config in configs.items():
                if config.host == db_name:
                    logger.info(f"找到匹配配置 [{instance_name}] (by host): {config.host}/{config.database}")
                    return UnifiedConnector(
                        dialect=config.dialect,
                        host=config.host,
                        port=config.port,
                        username=config.username,
                        password=config.password,
                        database=config.database,
                        **config.extra
                    )
            
            # 1.3 对于 Z 系列资产组，尝试使用 ORACLE 配置
            if OracleHostMapping.is_oracle_group(db_name):
                oracle_config = configs.get('ORACLE')
                if oracle_config:
                    logger.info(f"使用 ORACLE 配置创建连接器: {db_name}")
                    return UnifiedConnector(
                        dialect=oracle_config.dialect,
                        host=oracle_config.host,
                        port=oracle_config.port,
                        username=oracle_config.username,
                        password=oracle_config.password,
                        database=oracle_config.database,
                        **oracle_config.extra
                    )
                else:
                    logger.warning(f"资产组 {db_name} 没有配置 ORACLE 直连信息，无法执行诊断命令")
                    return None

        # 2. 尝试使用标准连接器创建逻辑（通过 require_connector）
        try:
            if db_name:
                self.args.database = db_name
            self.require_connector()
            return self.connector
        except Exception as e:
            logger.warning(f"使用标准连接器失败: {e}")

        # 3. 尝试创建通用连接器
        try:
            return UnifiedConnector.from_env()
        except Exception as e:
            logger.error(f"创建连接器失败: {e}")
            return None

    # ==================== PostgreSQL特有诊断方法 ====================

    def _analyze_vacuum(self, skill) -> int:
        """VACUUM状态分析（PostgreSQL特有）"""
        result = skill.analyze_vacuum()

        if not result.get('success'):
            self.output.error(f"VACUUM分析失败: {self._extract_error_message(result)}")
            return 1

        data = result.get('data', {})
        tables = data.get('tables_needing_vacuum', [])
        settings = data.get('autovacuum_settings', {})
        suggestions = data.get('suggestions', [])
        actionable_commands = data.get('actionable_commands', [])
        health_score = data.get('health_score', 0)
        vacuum_stats = data.get('vacuum_statistics', {})
        total_wasted = data.get('total_wasted_space', '0 B')

        self.output.info("\n" + "=" * 60)
        self.output.info("PostgreSQL VACUUM状态分析")
        self.output.info("=" * 60)

        # 健康评分
        if health_score >= 80:
            self.output.info(f"\n[健康评分] {health_score}/100 (良好)")
        elif health_score >= 60:
            self.output.warning(f"\n[健康评分] {health_score}/100 (一般)")
        else:
            self.output.error(f"\n[健康评分] {health_score}/100 (较差)")

        # 评分扣分原因说明
        if health_score < 80:
            deductions = []
            high_tables = [t for t in tables if t.get('priority') == 'high']
            if high_tables:
                deductions.append(f"  - {len(high_tables)} 个表死元组比例严重超标(-15分/个)")
            medium_tables = [t for t in tables if t.get('priority') == 'medium']
            if medium_tables:
                deductions.append(f"  - {len(medium_tables)} 个表死元组比例偏高(-8分/个)")
            total_dead = vacuum_stats.get('total_dead_tuples', 0)
            if total_dead > 100000:
                deductions.append(f"  - 死元组总数过多({total_dead}个)(-10分)")
            dead_ratio = vacuum_stats.get('overall_dead_ratio', 0)
            if dead_ratio > 20:
                deductions.append(f"  - 整体死元组比例过高({dead_ratio}%)(-10分)")
            if deductions:
                self.output.info("\n[评分说明] 主要扣分原因:")
                for d in deductions:
                    self.output.info(d)

        # 整体统计
        if vacuum_stats:
            self.output.info(f"\n[整体统计]")
            self.output.info(f"  总表数: {vacuum_stats.get('total_tables', 0)}")
            self.output.info(f"  活元组总数: {vacuum_stats.get('total_live_tuples', 0)}")
            self.output.info(f"  死元组总数: {vacuum_stats.get('total_dead_tuples', 0)}")
            self.output.info(f"  整体死元组比例: {vacuum_stats.get('overall_dead_ratio', 0)}%")
            self.output.info(f"  预计可回收空间: {total_wasted}")

        # Autovacuum配置
        if settings:
            self.output.info("\n[Autovacuum配置]")
            for key, value in settings.items():
                self.output.info(f"  {key}: {value}")

        # 需要VACUUM的表
        if tables:
            self.output.info(f"\n[需要关注的表] 共 {len(tables)} 个")
            for i, t in enumerate(tables[:10], 1):
                schema = t.get('schema') or 'public'
                table = t.get('table') or 'unknown'
                priority = t.get('priority', 'low')
                priority_marker = {'high': '[高]', 'medium': '[中]', 'low': '[低]'}.get(priority, '[低]')
                self.output.info(f"\n  [{i}] {priority_marker} {schema}.{table}")
                self.output.info(f"      表大小: {t.get('total_size', 'N/A')}")
                self.output.info(f"      活元组: {t.get('live_tuples', 0)}")
                self.output.info(f"      死元组: {t.get('dead_tuples', 0)}")
                self.output.info(f"      死元组比例: {t.get('dead_ratio', 0)}%")
                if t.get('wasted_space_bytes', 0) > 0:
                    wasted = t.get('wasted_space_bytes', 0)
                    wasted_str = f"{wasted / (1024**2):.2f} MB" if wasted >= 1024**2 else f"{wasted / 1024:.2f} KB"
                    self.output.info(f"      预计浪费空间: {wasted_str}")
                if t.get('last_autovacuum'):
                    self.output.info(f"      上次自动清理: {t.get('last_autovacuum')}")
                if t.get('last_vacuum'):
                    self.output.info(f"      上次手动清理: {t.get('last_vacuum')}")
        else:
            self.output.info("\n[需要关注的表] 无")

        # 建议
        if suggestions:
            self.output.info("\n[建议]")
            for s in suggestions:
                msg_type = s.get('type', 'info')
                msg = s.get('message', '')
                if msg_type == 'critical':
                    self.output.error(f"  [严重] {msg}")
                elif msg_type == 'warning':
                    self.output.warning(f"  [警告] {msg}")
                else:
                    self.output.info(f"  [提示] {msg}")
                if s.get('impact'):
                    self.output.info(f"        影响: {s.get('impact')}")
                if s.get('fix_command'):
                    self.output.info(f"        修复命令: {s.get('fix_command')}")

        # 可执行命令
        if actionable_commands:
            self.output.info("\n[推荐执行的VACUUM命令]")
            for cmd in actionable_commands[:5]:
                self.output.info(f"\n  优先级: {cmd.get('priority', 'low')}")
                self.output.info(f"  表: {cmd.get('table')}")
                self.output.info(f"  命令: {cmd.get('command')}")
                self.output.info(f"  说明: {cmd.get('description')}")

        return 0

    def _analyze_bloat(self, skill) -> int:
        """表膨胀/碎片分析"""
        result = skill.analyze_bloat()

        if not result.get('success'):
            self.output.error(f"膨胀分析失败: {self._extract_error_message(result)}")
            return 1

        data = result.get('data', {})
        tables = data.get('bloated_tables', [])
        severely_bloated = data.get('severely_bloated_count', 0)
        has_pgstattuple = data.get('has_pgstattuple', False)
        suggestions = data.get('suggestions', [])
        actionable_commands = data.get('actionable_commands', [])
        health_score = data.get('health_score', 0)
        total_wasted = data.get('total_wasted_space', '0 B')
        db_type = data.get('db_type', 'Unknown')

        self.output.info("\n" + "=" * 60)
        self.output.info(f"{db_type}表膨胀/碎片分析")
        self.output.info("=" * 60)

        # 健康评分
        if health_score >= 80:
            self.output.info(f"\n[健康评分] {health_score}/100 (良好)")
        elif health_score >= 60:
            self.output.warning(f"\n[健康评分] {health_score}/100 (一般)")
        else:
            self.output.error(f"\n[健康评分] {health_score}/100 (较差)")

        # 评分扣分原因说明
        if health_score < 80:
            deductions = []
            if severely_bloated > 0:
                deductions.append(f"  - {severely_bloated} 个表严重膨胀(>30%)(-15分/个)")
            medium_tables = [t for t in tables if t.get('priority') == 'medium']
            if medium_tables:
                deductions.append(f"  - {len(medium_tables)} 个表中度膨胀(10-30%)(-8分/个)")
            wasted_mb = 0
            if isinstance(total_wasted, str):
                if 'MB' in total_wasted:
                    try:
                        wasted_mb = float(total_wasted.replace('MB', '').strip())
                    except:
                        pass
                elif 'GB' in total_wasted:
                    try:
                        wasted_mb = float(total_wasted.replace('GB', '').strip()) * 1024
                    except:
                        pass
            if wasted_mb > 100:
                deductions.append(f"  - 可回收空间过大({total_wasted})(-10分)")
            if deductions:
                self.output.info("\n[评分说明] 主要扣分原因:")
                for d in deductions:
                    self.output.info(d)

        self.output.info(f"\n[统计]")
        self.output.info(f"  需要关注的表: {len(tables)} 个")
        self.output.info(f"  严重膨胀(>30%): {severely_bloated} 个")
        self.output.info(f"  预计可回收空间: {total_wasted}")

        # pgstattuple 提示仅对 PostgreSQL 有意义
        if db_type == "PostgreSQL":
            self.output.info(f"  pgstattuple扩展: {'已安装' if has_pgstattuple else '未安装'}")

            if not has_pgstattuple:
                self.output.info("\n  提示: 安装pgstattuple扩展可获得更准确的分析")
                self.output.info("        CREATE EXTENSION IF NOT EXISTS pgstattuple;")

        # 膨胀表详情
        if tables:
            self.output.info(f"\n[膨胀表详情] TOP {min(len(tables), 10)}")
            for i, t in enumerate(tables[:10], 1):
                bloat_ratio = t.get('bloat_ratio', 0) or t.get('estimated_bloat_ratio', 0)
                schema = t.get('schema') or 'public'
                table = t.get('table') or 'unknown'
                priority = t.get('priority', 'low')
                priority_marker = {'high': '[高]', 'medium': '[中]', 'low': '[低]'}.get(priority, '[低]')
                self.output.info(f"\n  [{i}] {priority_marker} {schema}.{table}")
                self.output.info(f"      总大小: {t.get('total_size', 'N/A')}")
                self.output.info(f"      膨胀率: {bloat_ratio:.1f}%")
                if t.get('wasted_space_bytes', 0) > 0:
                    wasted = t.get('wasted_space_bytes', 0)
                    wasted_str = f"{wasted / (1024**2):.2f} MB" if wasted >= 1024**2 else f"{wasted / 1024:.2f} KB"
                    self.output.info(f"      预计浪费空间: {wasted_str}")
                if t.get('dead_tuples'):
                    self.output.info(f"      死元组: {t.get('dead_tuples')}")
        else:
            self.output.info("\n[膨胀表详情] 未发现明显膨胀的表")

        # 建议
        if suggestions:
            self.output.info("\n[建议]")
            for s in suggestions:
                msg_type = s.get('type', 'info')
                msg = s.get('message', '')
                if msg_type == 'critical':
                    self.output.error(f"  [严重] {msg}")
                elif msg_type == 'warning':
                    self.output.warning(f"  [警告] {msg}")
                else:
                    self.output.info(f"  [提示] {msg}")
                if s.get('impact'):
                    self.output.info(f"        影响: {s.get('impact')}")
                if s.get('install_sql'):
                    self.output.info(f"        安装命令: {s.get('install_sql')}")
                if s.get('note'):
                    self.output.info(f"        说明: {s.get('note')}")

        # 可执行命令
        if actionable_commands:
            self.output.info("\n[推荐执行的维护命令]")
            for cmd in actionable_commands[:3]:
                self.output.info(f"\n  优先级: {cmd.get('priority', 'low')}")
                self.output.info(f"  表: {cmd.get('table')}")
                self.output.info(f"  说明: {cmd.get('description')}")
                self.output.info(f"  命令:")
                for line in cmd.get('commands', []):
                    self.output.info(f"    {line}")

        return 0

    def _analyze_index_usage(self, skill) -> int:
        """索引使用分析"""
        result = skill.analyze_index_usage()

        if not result.get('success'):
            self.output.error(f"索引使用分析失败: {self._extract_error_message(result)}")
            return 1

        data = result.get('data', {})
        unused = data.get('unused_indexes', [])
        hot = data.get('hot_indexes', [])
        missing = data.get('tables_missing_index', [])
        duplicate = data.get('duplicate_indexes', [])
        redundant = data.get('redundant_indexes', [])
        invalid = data.get('invalid_indexes', [])
        suggestions = data.get('suggestions', [])
        actionable_commands = data.get('actionable_commands', [])
        health_score = data.get('health_score', 0)
        total_unused_size = data.get('total_unused_index_size', data.get('total_unused_index_size_mb', '0 B'))
        has_perf_schema = data.get('has_performance_schema')
        db_type = data.get('db_type', None)
        if not db_type:
            dialect_raw = data.get('dialect', '')
            db_type = dialect_raw.split('+')[0].title() if dialect_raw else 'Unknown'

        self.output.info("\n" + "=" * 60)
        self.output.info(f"{db_type}索引使用分析")
        self.output.info("=" * 60)

        # 健康评分
        if health_score >= 80:
            self.output.info(f"\n[健康评分] {health_score}/100 (良好)")
        elif health_score >= 60:
            self.output.warning(f"\n[健康评分] {health_score}/100 (一般)")
        else:
            self.output.error(f"\n[健康评分] {health_score}/100 (较差)")

        # 评分扣分原因说明
        if health_score < 80:
            deductions = []
            high_unused = [idx for idx in unused if idx.get('priority') == 'high']
            if high_unused:
                deductions.append(f"  - {len(high_unused)} 个大体积未使用索引(-10分/个)")
            medium_unused = [idx for idx in unused if idx.get('priority') == 'medium']
            if medium_unused:
                deductions.append(f"  - {len(medium_unused)} 个小体积未使用索引(-5分/个)")
            high_missing = [t for t in missing if t.get('priority') == 'high']
            if high_missing:
                deductions.append(f"  - {len(high_missing)} 个表严重缺少索引(-15分/个)")
            medium_missing = [t for t in missing if t.get('priority') == 'medium']
            if medium_missing:
                deductions.append(f"  - {len(medium_missing)} 个表可能缺少索引(-8分/个)")
            if redundant:
                deductions.append(f"  - {len(redundant)} 组冗余索引(-5分/组)")
            if duplicate:
                deductions.append(f"  - {len(duplicate)} 组重复索引(-5分/组)")
            if invalid:
                deductions.append(f"  - {len(invalid)} 个无效索引(-20分/个)")
            if deductions:
                self.output.info("\n[评分说明] 主要扣分原因:")
                for d in deductions:
                    self.output.info(d)

        # 整体统计
        self.output.info(f"\n[整体统计]")
        self.output.info(f"  未使用索引: {len(unused)} 个")
        self.output.info(f"  未使用索引占用: {total_unused_size}")
        self.output.info(f"  可能缺少索引的表: {len(missing)} 个")
        self.output.info(f"  重复索引: {len(duplicate)} 组")

        # 未使用索引
        if unused:
            self.output.info(f"\n[未使用索引] 共 {len(unused)} 个")
            for i, idx in enumerate(unused[:5], 1):
                priority = idx.get('priority', 'low')
                priority_marker = {'high': '[高]', 'medium': '[中]', 'low': '[低]'}.get(priority, '[低]')
                self.output.info(f"  [{i}] {priority_marker} {idx.get('table')}.{idx.get('index')}")
                self.output.info(f"      大小: {idx.get('size', 'N/A')}")
                if idx.get('size_bytes', 0) > 0:
                    size_mb = idx.get('size_bytes', 0) / (1024 * 1024)
                    self.output.info(f"      大小(MB): {size_mb:.2f}")

        # 高频使用索引
        self.output.info(f"\n[高频使用索引] TOP {min(len(hot), 5)}")
        if hot:
            for i, idx in enumerate(hot[:5], 1):
                self.output.info(f"  [{i}] {idx.get('table')}.{idx.get('index')}")
                self.output.info(f"      扫描次数: {idx.get('scans', 0)}")
                self.output.info(f"      读取元组: {idx.get('tuples_read', 0)}")
                self.output.info(f"      大小: {idx.get('size', 'N/A')}")

        # 可能缺少索引的表
        if missing:
            self.output.info(f"\n[可能缺少索引的表] 共 {len(missing)} 个")
            for i, t in enumerate(missing[:5], 1):
                schema = t.get('schema') or 'public'
                table = t.get('table') or 'unknown'
                priority = t.get('priority', 'low')
                priority_marker = {'high': '[高]', 'medium': '[中]', 'low': '[低]'}.get(priority, '[低]')
                self.output.info(f"  [{i}] {priority_marker} {schema}.{table}")
                self.output.info(f"      全表扫描: {t.get('seq_scans', 0)} 次")
                self.output.info(f"      索引扫描: {t.get('idx_scans', 0)} 次")
                self.output.info(f"      数据行数: {t.get('live_tuples', 0)}")

        # 重复索引（PostgreSQL）
        if duplicate:
            self.output.info(f"\n[重复索引] 共 {len(duplicate)} 组")
            for i, dup in enumerate(duplicate[:3], 1):
                self.output.info(f"  [{i}] 表: {dup.get('table')}")
                self.output.info(f"      冗余索引: {dup.get('redundant_index')}")
                self.output.info(f"      保留索引: {dup.get('kept_index')}")

        # 冗余索引（MySQL）
        if redundant:
            self.output.info(f"\n[冗余索引] 共 {len(redundant)} 组")
            for i, idx in enumerate(redundant[:3], 1):
                self.output.info(f"  [{i}] 表: {idx.get('table')}")
                self.output.info(f"      冗余索引: {idx.get('redundant_index')}")
                self.output.info(f"      冗余列: {idx.get('redundant_columns')}")
                self.output.info(f"      保留索引: {idx.get('dominant_index')}")

        # 无效索引（Oracle）
        if invalid:
            self.output.info(f"\n[无效索引] 共 {len(invalid)} 个")
            for i, idx in enumerate(invalid[:5], 1):
                self.output.info(f"  [{i}] {idx.get('schema')}.{idx.get('index')}")
                self.output.info(f"      表: {idx.get('table')}")
                self.output.info(f"      状态: {idx.get('status')}")

        # MySQL performance_schema状态
        if has_perf_schema is not None:
            if has_perf_schema:
                self.output.info("\n[Performance Schema] 已启用")
            else:
                self.output.warning("\n[Performance Schema] 未启用，索引统计可能不完整")

        # 建议
        if suggestions:
            self.output.info("\n[建议]")
            for s in suggestions:
                msg_type = s.get('type', 'info')
                msg = s.get('message', '')
                if msg_type == 'critical':
                    self.output.error(f"  [严重] {msg}")
                elif msg_type == 'warning':
                    self.output.warning(f"  [警告] {msg}")
                else:
                    self.output.info(f"  [提示] {msg}")
                if s.get('impact'):
                    self.output.info(f"        影响: {s.get('impact')}")
                if s.get('note'):
                    self.output.info(f"        说明: {s.get('note')}")

        # 可执行命令
        if actionable_commands:
            self.output.info("\n[推荐执行的优化命令]")
            for cmd in actionable_commands[:5]:
                self.output.info(f"\n  优先级: {cmd.get('priority', 'low')}")
                self.output.info(f"  类型: {cmd.get('type', 'unknown')}")
                if cmd.get('index'):
                    self.output.info(f"  索引: {cmd.get('index')}")
                if cmd.get('table'):
                    self.output.info(f"  表: {cmd.get('table')}")
                if cmd.get('tablespace'):
                    self.output.info(f"  表空间: {cmd.get('tablespace')}")
                self.output.info(f"  说明: {cmd.get('description')}")
                if cmd.get('warning'):
                    self.output.warning(f"  警告: {cmd.get('warning')}")
                self.output.info(f"  命令:")
                for line in cmd.get('commands', []):
                    self.output.info(f"    {line}")

        return 0

    def _analyze_tablespace_fragmentation(self, skill) -> int:
        """表空间碎片分析（Oracle特有）"""
        result = skill.analyze_tablespace_fragmentation()

        if not result.get('success'):
            self.output.error(f"表空间碎片分析失败: {self._extract_error_message(result)}")
            return 1

        data = result.get('data', {})
        tablespaces = data.get('fragmented_tablespaces', [])
        suggestions = data.get('suggestions', [])
        actionable_commands = data.get('actionable_commands', [])
        health_score = data.get('health_score', 0)
        total_wasted = data.get('total_wasted_space_mb', 0)

        self.output.info("\n" + "=" * 60)
        self.output.info("Oracle表空间碎片分析")
        self.output.info("=" * 60)

        # 健康评分
        if health_score >= 80:
            self.output.info(f"\n[健康评分] {health_score}/100 (良好)")
        elif health_score >= 60:
            self.output.warning(f"\n[健康评分] {health_score}/100 (一般)")
        else:
            self.output.error(f"\n[健康评分] {health_score}/100 (较差)")

        # 评分扣分原因说明
        if health_score < 80:
            deductions = []
            high_ts = [t for t in tablespaces if t.get('priority') == 'high']
            if high_ts:
                deductions.append(f"  - {len(high_ts)} 个表空间严重碎片(-15分/个)")
            medium_ts = [t for t in tablespaces if t.get('priority') == 'medium']
            if medium_ts:
                deductions.append(f"  - {len(medium_ts)} 个表空间中度碎片(-8分/个)")
            if total_wasted > 1000:
                deductions.append(f"  - 可回收空间过大({total_wasted:.2f} MB)(-10分)")
            if deductions:
                self.output.info("\n[评分说明] 主要扣分原因:")
                for d in deductions:
                    self.output.info(d)

        self.output.info(f"\n[统计]")
        self.output.info(f"  需要关注的表空间: {len(tablespaces)} 个")
        self.output.info(f"  预计可回收空间: {total_wasted:.2f} MB")

        # 碎片表空间详情
        if tablespaces:
            self.output.info(f"\n[碎片表空间详情] TOP {min(len(tablespaces), 10)}")
            for i, t in enumerate(tablespaces[:10], 1):
                tablespace = t.get('tablespace', 'UNKNOWN')
                priority = t.get('priority', 'low')
                priority_marker = {'high': '[高]', 'medium': '[中]', 'low': '[低]'}.get(priority, '[低]')
                self.output.info(f"\n  [{i}] {priority_marker} {tablespace}")
                self.output.info(f"      总大小: {t.get('total_mb', 0):.2f} MB")
                self.output.info(f"      空闲空间: {t.get('free_space_mb', 0):.2f} MB ({t.get('free_percentage', 0):.1f}%)")
                self.output.info(f"      碎片数: {t.get('free_extents', 0)} 个")
                self.output.info(f"      碎片率: {t.get('fragmentation_ratio', 0):.1f}%")
                self.output.info(f"      平均碎片大小: {t.get('avg_extent_mb', 0):.2f} MB")
        else:
            self.output.info("\n[碎片表空间详情] 未发现明显碎片的表空间")

        # 建议
        if suggestions:
            self.output.info("\n[建议]")
            for s in suggestions:
                msg_type = s.get('type', 'info')
                msg = s.get('message', '')
                if msg_type == 'critical':
                    self.output.error(f"  [严重] {msg}")
                elif msg_type == 'warning':
                    self.output.warning(f"  [警告] {msg}")
                else:
                    self.output.info(f"  [提示] {msg}")
                if s.get('impact'):
                    self.output.info(f"        影响: {s.get('impact')}")
                if s.get('tablespaces'):
                    self.output.info(f"        表空间: {', '.join(s.get('tablespaces', []))}")

        # 可执行命令
        if actionable_commands:
            self.output.info("\n[推荐执行的优化命令]")
            for cmd in actionable_commands[:3]:
                self.output.info(f"\n  优先级: {cmd.get('priority', 'low')}")
                self.output.info(f"  表空间: {cmd.get('tablespace')}")
                self.output.info(f"  说明: {cmd.get('description')}")
                if cmd.get('warning'):
                    self.output.warning(f"  警告: {cmd.get('warning')}")
                self.output.info(f"  命令:")
                for line in cmd.get('commands', []):
                    self.output.info(f"    {line}")

        return 0
