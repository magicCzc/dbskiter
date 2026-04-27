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
            help="慢查询日志 - 分析历史慢查询"
        )
        slowlog_parser.add_argument(
            "--limit",
            type=int,
            default=10,
            help="返回条数（默认10）"
        )
        slowlog_parser.add_argument(
            "--min-time",
            type=float,
            default=1.0,
            help="最小执行时间（秒，默认1.0）"
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

        skill = None
        try:
            skill = DiagnoseSkill(self.connector)

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

            else:
                self.output.error(
                    "请指定诊断操作:\n"
                    "  P0(高频): realtime, top, locks, sql, space\n"
                    "  P1(中频): connections, replication, slow-queries, recommend-indexes\n"
                    "  P2(低频): report, table, performance-snapshot, bottleneck"
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
                    time = q.get('time', 0)
                    self.output.info(f"    {i}. [{time:.2f}s] {sql}...")
            else:
                self.output.info("  未发现慢查询")

        # 4. 给出建议
        self.output.info("\n" + "=" * 60)
        self.output.info("诊断建议")
        self.output.info("=" * 60)
        suggestions = data.get('suggestions', [])
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
            self.output.error(f"获取TOP SQL失败: {result.get('message')}")
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
            self.output.info(f"[{i}] 执行时间: {q.get('exec_time', 0):.3f}s")
            self.output.info(f"    扫描行数: {q.get('rows_examined', 0)}")
            self.output.info(f"    返回行数: {q.get('rows_sent', 0)}")
            self.output.info(f"    SQL: {q.get('sql', '')[:100]}...")
            if q.get('suggestion'):
                self.output.info(f"    建议: {q.get('suggestion')}")
            self.output.info("")

        return 0

    def _analyze_locks(self, skill) -> int:
        """锁分析 - 有死锁/阻塞"""
        result = skill.analyze_locks()

        if not result.get('success'):
            self.output.error(f"锁分析失败: {result.get('message')}")
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
            self.output.error(f"空间诊断失败: {result.get('message')}")
            return 1

        data = result.get('data', {})

        self.output.info("\n" + "=" * 60)
        self.output.info("空间诊断结果")
        self.output.info("=" * 60)

        # 总体空间
        total = data.get('total_space', {})
        self.output.info(f"\n[总体空间]")
        self.output.info(f"  总大小: {total.get('total_gb', 0):.2f} GB")
        self.output.info(f"  数据大小: {total.get('data_gb', 0):.2f} GB")
        self.output.info(f"  索引大小: {total.get('index_gb', 0):.2f} GB")
        self.output.info(f"  剩余空间: {total.get('free_gb', 0):.2f} GB")

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
                self.output.info(f"  - {s}")

        return 0

    # ==================== P1: 中频场景实现 ====================

    def _analyze_connections(self, skill) -> int:
        """连接分析"""
        result = skill.analyze_connections(show_idle=self.args.idle)

        if not result.get('success'):
            self.output.error(f"连接分析失败: {result.get('message')}")
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
            self.output.error(f"复制诊断失败: {result.get('message')}")
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
        """历史慢查询分析"""
        result = skill.analyze_slow_queries(
            limit=self.args.limit,
            min_time=self.args.min_time
        )

        if not result.get('success'):
            self.output.error(f"慢查询分析失败: {result.get('message')}")
            return 1

        data = result.get('data', {})
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

    def _recommend_indexes(self, skill) -> int:
        """索引建议"""
        result = skill.recommend_indexes(table=self.args.table)

        if not result.get('success'):
            self.output.error(f"索引建议失败: {result.get('message')}")
            return 1

        data = result.get('data', {})
        indexes = data.get('indexes', [])

        self.output.info("\n" + "=" * 60)
        self.output.info("索引建议")
        self.output.info("=" * 60)

        if not indexes:
            self.output.info("\n暂无索引建议")
            return 0

        self.output.info(f"\n共 {len(indexes)} 条建议:\n")

        for i, idx in enumerate(indexes, 1):
            self.output.info(f"[{i}] 表: {idx.get('table')}")
            self.output.info(f"    建议: {idx.get('recommendation')}")
            self.output.info(f"    原因: {idx.get('reason')}")
            if idx.get('sql'):
                self.output.info(f"    SQL: {idx.get('sql')}")
            self.output.info("")

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

    def _diagnose_table(self, skill) -> int:
        """单表诊断"""
        result = skill.diagnose_table(self.args.table_name)

        if not result.get('success'):
            self.output.error(f"表诊断失败: {result.get('message')}")
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
                self.output.info(f"  - {s}")

        return 0

    def _performance_snapshot(self, skill) -> int:
        """性能快照"""
        result = skill.take_performance_snapshot()

        if not result.get('success'):
            self.output.error(f"性能快照采集失败: {result.get('message')}")
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
            self.output.error(f"瓶颈分析失败: {result.get('message')}")
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
