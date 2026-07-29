"""
cli/commands/diagnose.py

数据库诊断命令 - 主入口

设计原则：
    1. 覆盖95%日常DBA场景
    2. 命令命名贴近自然语言
    3. 实时诊断优先于历史分析
    4. 提供可操作的优化建议

本文件仅包含参数解析和命令分发逻辑，
具体实现按场景拆分到 diagnose/ 子包：
    - handlers_p0.py          P0 高频场景（realtime/top/locks/sql/space）
    - handlers_p1.py          P1 中频场景（connections/replication/slow-queries/recommend-indexes）
    - handlers_p2.py          P2 低频场景（report/table/performance-snapshot/bottleneck）
    - handlers_db_specific.py 数据库特有诊断（vacuum/bloat/index-usage/tablespace-fragmentation）
    - connector.py            诊断专用连接器（_create_connector_for_diagnose）

使用场景：
    - "数据库有点慢" -> diagnose realtime
    - "CPU飙高了" -> diagnose top
    - "有死锁" -> diagnose locks
    - "空间不够了" -> diagnose space
    - "主从延迟" -> diagnose replication
"""

from argparse import ArgumentParser
from typing import Any, Dict

from .base import BaseCommand
from .diagnose.handlers_p0 import DiagnoseP0Mixin
from .diagnose.handlers_p1 import DiagnoseP1Mixin
from .diagnose.handlers_p2 import DiagnoseP2Mixin
from .diagnose.handlers_db_specific import DiagnoseDbSpecificMixin
from .diagnose.connector import build_diagnose_connector


class DiagnoseCommand(
    BaseCommand,
    DiagnoseP0Mixin,
    DiagnoseP1Mixin,
    DiagnoseP2Mixin,
    DiagnoseDbSpecificMixin,
):
    """数据库诊断命令"""

    name = "diagnose"
    description = "Database Diagnose - 生产级数据库诊断工具"
    help_text = "实时诊断、性能分析、锁分析、空间诊断、复制诊断"

    @classmethod
    def add_arguments(cls, parser: ArgumentParser) -> None:
        """添加诊断命令参数"""
        parser.epilog = """
示例:
  dbskiter --database=jump diagnose realtime                 # 实时诊断当前性能
  dbskiter --database=jump diagnose top --limit=20           # TOP 20 SQL
  dbskiter --database=jump diagnose locks --kill             # 锁分析并显示KILL语句
  dbskiter --database=jump diagnose sql "SELECT * FROM users WHERE id = 1"
  dbskiter --database=jump diagnose space --top=10           # 空间诊断，Top 10大表
  dbskiter --database=jump diagnose slow-queries --top=10    # 慢查询分析
  dbskiter --database=jump diagnose replication              # 复制延迟诊断
        """
        subparsers = parser.add_subparsers(dest="diagnose_action", help="诊断操作")

        # ==================== P0: 高频场景（每天使用）====================

        realtime_parser = subparsers.add_parser("realtime", help="实时诊断 - 分析当前数据库性能问题")
        realtime_parser.add_argument("--threshold", type=int, default=5, help="慢查询阈值（秒，默认5）")

        top_parser = subparsers.add_parser("top", help="TOP SQL - 查看资源消耗最高的SQL")
        top_parser.add_argument("--limit", type=int, default=10, help="返回条数（默认10）")
        top_parser.add_argument(
            "--by", choices=["time", "cpu", "io", "rows"], default="time", help="排序依据（默认time）"
        )

        locks_parser = subparsers.add_parser("locks", help="锁分析 - 检测死锁、阻塞、锁等待")
        locks_parser.add_argument("--kill", action="store_true", help="显示KILL语句（不执行）")

        sql_parser = subparsers.add_parser("sql", help="SQL诊断 - 深度分析SQL语句性能")
        sql_parser.add_argument("sql", help="SQL语句")
        sql_parser.add_argument("--params", help="SQL参数（JSON格式）")

        space_parser = subparsers.add_parser("space", help="空间诊断 - 分析表空间、碎片、大表")
        space_parser.add_argument("--top", type=int, default=20, help="显示TOP N大表（默认20）")
        space_parser.add_argument("--min-size", type=int, default=100, help="最小表大小（MB，默认100）")

        # ==================== P1: 中频场景（每周使用）====================

        conn_parser = subparsers.add_parser("connections", help="连接分析 - 分析连接池、空闲连接")
        conn_parser.add_argument("--idle", action="store_true", help="显示空闲连接")

        subparsers.add_parser("replication", help="复制诊断 - 分析主从延迟、复制状态")

        slowlog_parser = subparsers.add_parser(
            "slow-queries", aliases=["slowlog"], help="慢查询日志 - 分析历史慢查询（支持实时采集和日志文件解析）"
        )
        slowlog_parser.add_argument("--top", type=int, default=10, help="显示TOP N条慢查询（默认10）")
        slowlog_parser.add_argument("--limit", type=int, default=10, help="返回条数（默认10，仅实时模式）")
        slowlog_parser.add_argument("--min-time", type=float, default=1.0, help="最小执行时间（秒，默认1.0）")
        slowlog_parser.add_argument("--log-file", help="慢查询日志文件路径（指定则使用日志文件模式）")
        slowlog_parser.add_argument(
            "--since", default="24h", help="时间范围（如24h表示最近24小时，7d表示最近7天，仅日志模式）"
        )

        index_parser = subparsers.add_parser(
            "recommend-indexes", aliases=["indexes"], help="索引建议 - 全库索引分析和建议"
        )
        index_parser.add_argument("--table", help="指定表名（默认全库）")

        # ==================== P2: 低频场景（每月使用）====================

        subparsers.add_parser("report", help="综合报告 - 生成完整诊断报告")

        table_parser = subparsers.add_parser("table", help="表诊断 - 分析单表结构和性能")
        table_parser.add_argument("table_name", help="表名")

        snapshot_parser = subparsers.add_parser("performance-snapshot", help="性能快照 - 采集数据库性能指标")
        snapshot_parser.add_argument("--output", "-o", help="输出文件路径（JSON格式）")

        bottleneck_parser = subparsers.add_parser("bottleneck", help="瓶颈分析 - 分析性能瓶颈")
        bottleneck_parser.add_argument("--top", type=int, default=5, help="显示TOP N瓶颈（默认5）")

        # ==================== PostgreSQL特有诊断 ====================

        subparsers.add_parser("vacuum", help="VACUUM分析 - 检查表清理状态和死元组（PostgreSQL特有）")

        bloat_parser = subparsers.add_parser(
            "bloat",
            help="膨胀/碎片分析 - 检测表膨胀和碎片情况（PostgreSQL膨胀/MySQL碎片/Oracle表空间碎片/ClickHouse分区/SQLite空闲页）",
        )
        bloat_parser.add_argument("--threshold", type=int, default=30, help="膨胀率阈值（百分比，默认30）")

        subparsers.add_parser(
            "index-usage",
            help="索引使用分析 - 识别未使用索引和缺失索引（MySQL/Oracle/PostgreSQL/ClickHouse跳数索引/SQLite冗余索引）",
        )

        subparsers.add_parser("tablespace-fragmentation", help="表空间碎片分析 - 分析Oracle表空间碎片情况")

    def execute(self) -> int:
        """执行诊断命令"""
        from dbskiter.db_diagnose.skill import DiagnoseSkill

        action = getattr(self.args, "diagnose_action", None)

        # 建立连接器（demo 模式 / 真实数据库）
        connector = self._setup_connector()
        if connector is None and not self._explicit_error_reported():
            return 1

        # 数据库特有命令的方言预检查
        if not self._check_dialect_compatibility(action):
            return 1

        skill = None
        try:
            skill = DiagnoseSkill(self.connector)

            if self.output_mode != "rule":
                method_map, scenario_map = self._build_ai_dispatch_maps(skill)
                return self._execute_ai_mode(skill, action, method_map, scenario_map)

            return self._dispatch_action(action, skill)

        except Exception as e:
            self.output.error(f"诊断失败: {e}")
            return 1
        finally:
            if skill:
                skill.close()

    # ==================== 编排层：连接 / 分发 ====================

    def _setup_connector(self):
        """建立诊断用的数据库连接器

        返回:
            连接器对象（已绑定到 self._connector），或 None（失败时）
        """
        if getattr(self.args, "demo", False):
            from dbskiter.shared.mock_connector import MockConnector

            self._connector = MockConnector()
            self.output.info("演示模式：使用内置 Mock 数据")
            return self._connector

        has_valid_config = (
            self.config.host not in ("localhost", "127.0.0.1")
            or self.config.username != "root"
            or self.config.password != ""
        )

        if has_valid_config:
            from dbskiter.shared.unified_connector import UnifiedConnector

            self._connector = UnifiedConnector(
                dialect=self.config.dialect,
                host=self.config.host,
                port=self.config.port,
                username=self.config.username,
                password=self.config.password,
                database=self.config.database,
                **self.config.extra,
            )
            return self._connector

        # 回退到 MultiDBConfig 逻辑
        db_name = getattr(self.args, "database", None)
        configs = self._load_all_configs()
        connector = build_diagnose_connector(self, db_name, configs)

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
            self._explicit_error = True
            return None

        self._connector = connector
        return connector

    def _explicit_error_reported(self) -> bool:
        """检查是否已显式报告错误（避免重复输出）"""
        return getattr(self, "_explicit_error", False)

    def _load_all_configs(self) -> Dict[str, Any]:
        """加载所有可用的数据库配置"""
        from dbskiter.cli.config import MultiDBConfig

        return MultiDBConfig().load_all_configs()

    def _check_dialect_compatibility(self, action: str) -> bool:
        """方言兼容性预检查

        在连接数据库之前就检查，避免不匹配时还要等待连接重试
        """
        db_specific_commands = {
            "vacuum": {
                "required": "postgresql",
                "label": "VACUUM分析",
                "supported": ["postgresql"],
            },
            "tablespace-fragmentation": {
                "required": "oracle",
                "label": "表空间碎片分析",
                "supported": ["oracle"],
            },
            "replication": {
                "required": "clickhouse",
                "label": "复制分析",
                "supported": ["clickhouse", "postgresql", "mysql"],
            },
            "bloat": {
                "required": "postgresql",
                "label": "表膨胀/碎片分析",
                "supported": ["postgresql", "clickhouse", "sqlite", "mysql", "oracle"],
            },
            "index-usage": {
                "required": "postgresql",
                "label": "索引使用分析",
                "supported": ["postgresql", "clickhouse", "sqlite", "mysql", "oracle"],
            },
        }
        if action not in db_specific_commands:
            return True

        cmd_info = db_specific_commands[action]
        dialect = getattr(self._connector, "dialect", "") or ""
        dialect_lower = dialect.lower()
        if not any(d in dialect_lower for d in cmd_info["supported"]):
            self.output.error(
                f"{cmd_info['label']}仅支持 "
                f"{'/'.join(cmd_info['supported'])} 数据库，"
                f"当前数据库类型: {dialect or '未知'}\n\n"
                f"请使用 --database 参数指定正确的数据库，或检查 .env 中的连接配置。"
            )
            return False
        return True

    def _dispatch_action(self, action: str, skill) -> int:
        """命令分发：根据 action 调用对应 handler"""
        # P0 高频
        p0_map = {
            "realtime": self._realtime_diagnose,
            "top": self._top_sql,
            "locks": self._analyze_locks,
            "sql": self._diagnose_sql,
            "space": self._space_diagnose,
        }
        if action in p0_map:
            return p0_map[action](skill)

        # P1 中频
        p1_map = {
            "connections": self._analyze_connections,
            "replication": self._replication_diagnose,
            "slow-queries": self._analyze_slowlog,
            "slowlog": self._analyze_slowlog,
            "recommend-indexes": self._recommend_indexes,
            "indexes": self._recommend_indexes,
        }
        if action in p1_map:
            return p1_map[action](skill)

        # P2 低频
        p2_map = {
            "report": self._generate_report,
            "table": self._diagnose_table,
            "performance-snapshot": self._performance_snapshot,
            "bottleneck": self._analyze_bottleneck,
        }
        if action in p2_map:
            return p2_map[action](skill)

        # 数据库特有
        db_specific_map = {
            "vacuum": self._analyze_vacuum,
            "bloat": self._analyze_bloat,
            "index-usage": self._analyze_index_usage,
            "tablespace-fragmentation": self._analyze_tablespace_fragmentation,
        }
        if action in db_specific_map:
            return db_specific_map[action](skill)

        self.output.error(
            "请指定诊断操作:\n"
            "  P0(高频): realtime, top, locks, sql, space\n"
            "  P1(中频): connections, replication, slow-queries, recommend-indexes\n"
            "  P2(低频): report, table, performance-snapshot, bottleneck\n"
            "  多数据库支持: bloat, index-usage\n"
            "  PostgreSQL特有: vacuum\n"
            "  Oracle特有: tablespace-fragmentation"
        )
        return 1

    def _build_ai_dispatch_maps(self, skill):
        """构建 AI 模式下的 method_map 和 scenario_map"""
        method_map = {
            "realtime": lambda: skill.realtime_diagnose(threshold=getattr(self.args, "threshold", 5)),
            "top": lambda: skill.get_top_sql(
                limit=getattr(self.args, "limit", 10),
                order_by=getattr(self.args, "by", "time"),
            ),
            "locks": lambda: skill.analyze_locks(),
            "sql": lambda: skill.analyze_sql(self.args.sql),
            "space": lambda: skill.analyze_space(
                top_n=getattr(self.args, "top", 20),
                min_size_mb=getattr(self.args, "min_size", 100),
            ),
            "connections": lambda: skill.analyze_connections(
                show_idle=getattr(self.args, "idle", False),
            ),
            "replication": lambda: skill.analyze_replication(),
            "slow-queries": lambda: skill.analyze_slow_queries(
                limit=getattr(self.args, "top", getattr(self.args, "limit", 10)),
                min_time=getattr(self.args, "min_time", 1.0),
                log_file=getattr(self.args, "log_file", None),
                since=getattr(self.args, "since", "24h"),
            ),
            "slowlog": lambda: skill.analyze_slow_queries(
                limit=getattr(self.args, "top", getattr(self.args, "limit", 10)),
                min_time=getattr(self.args, "min_time", 1.0),
                log_file=getattr(self.args, "log_file", None),
                since=getattr(self.args, "since", "24h"),
            ),
            "recommend-indexes": lambda: skill.recommend_indexes(
                table=getattr(self.args, "table", None),
            ),
            "indexes": lambda: skill.recommend_indexes(
                table=getattr(self.args, "table", None),
            ),
            "report": lambda: self._generate_report_for_ai_mode(skill),
            "table": lambda: skill.diagnose_table(self.args.table_name),
            "performance-snapshot": lambda: skill.take_performance_snapshot(),
            "bottleneck": lambda: skill.analyze_performance_bottleneck(),
            "vacuum": lambda: skill.analyze_vacuum(),
            "bloat": lambda: skill.analyze_bloat(
                threshold=getattr(self.args, "threshold", 30),
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
        return method_map, scenario_map
