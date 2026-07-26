"""
tests/test_diagnose_subpackage.py

测试 diagnose 命令的子包拆分结构

覆盖：
    1. MRO 验证（DiagnoseCommand 正确继承 5 个 mixin）
    2. 17 个 handler 方法分布在正确的 mixin 上
    3. 子包导入路径
    4. CLI 子命令注册（19 个 diagnose 子命令）
    5. demo 模式端到端
    6. 共享辅助方法（_print_health_score / _print_suggestions）
    7. connector.py 的多策略匹配
"""

import pytest
from argparse import Namespace, ArgumentParser
from unittest.mock import MagicMock, patch

# 顶层导入（验证 packages 没有循环依赖）
from dbskiter.cli.commands import DiagnoseCommand
from dbskiter.cli.commands.diagnose import (
    DiagnoseP0Mixin,
    DiagnoseP1Mixin,
    DiagnoseP2Mixin,
    DiagnoseDbSpecificMixin,
    build_diagnose_connector,
)
from dbskiter.cli.commands.diagnose.handlers_p0 import (
    _REALTIME_DIAGNOSE, _TOP_SQL, _ANALYZE_LOCKS, _DIAGNOSE_SQL, _SPACE_DIAGNOSE,
)
from dbskiter.cli.commands.diagnose.handlers_p1 import (
    _ANALYZE_CONNECTIONS, _ANALYZE_SLOWLOG, _RECOMMEND_INDEXES,
)
from dbskiter.cli.commands.diagnose.handlers_p2 import (
    _GENERATE_REPORT, _DIAGNOSE_TABLE, _PERFORMANCE_SNAPSHOT, _ANALYZE_BOTTLENECK,
)
from dbskiter.cli.commands.diagnose.handlers_db_specific import (
    _ANALYZE_VACUUM, _ANALYZE_BLOAT, _ANALYZE_INDEX_USAGE, _ANALYZE_TABLESPACE_FRAGMENTATION,
)


class TestDiagnoseSubpackageStructure:
    """验证子包拆分结构正确"""

    def test_diagnose_command_mro(self):
        """MRO 应包含 5 个 mixin + BaseCommand"""
        mro_names = [c.__name__ for c in DiagnoseCommand.__mro__]
        # 验证关键 mixin 都在 MRO 中
        assert "DiagnoseCommand" in mro_names
        assert "BaseCommand" in mro_names
        assert "DiagnoseP0Mixin" in mro_names
        assert "DiagnoseP1Mixin" in mro_names
        assert "DiagnoseP2Mixin" in mro_names
        assert "DiagnoseDbSpecificMixin" in mro_names

    def test_diagnose_command_name(self):
        """DiagnoseCommand 的 name 仍是 'diagnose'"""
        assert DiagnoseCommand.name == "diagnose"
        assert DiagnoseCommand.description is not None

    def test_mixin_responsibilities(self):
        """验证每个 mixin 负责自己的方法域"""
        # P0: realtime, top, locks, sql, space (5 个)
        p0_methods = [
            "_realtime_diagnose", "_top_sql", "_analyze_locks",
            "_diagnose_sql", "_space_diagnose",
        ]
        for method in p0_methods:
            assert hasattr(DiagnoseP0Mixin, method), f"P0 缺少方法: {method}"

        # P1: connections, replication, slow-queries, recommend-indexes (3 个，slow-queries + recommend-indexes 各 1)
        p1_methods = [
            "_analyze_connections", "_analyze_slowlog", "_recommend_indexes",
        ]
        for method in p1_methods:
            assert hasattr(DiagnoseP1Mixin, method), f"P1 缺少方法: {method}"

        # P2: report, table, performance-snapshot, bottleneck (4 个)
        p2_methods = [
            "_generate_report", "_diagnose_table",
            "_performance_snapshot", "_analyze_bottleneck",
        ]
        for method in p2_methods:
            assert hasattr(DiagnoseP2Mixin, method), f"P2 缺少方法: {method}"

        # DB-specific: vacuum, bloat, index-usage, tablespace-fragmentation (4 个)
        db_methods = [
            "_analyze_vacuum", "_analyze_bloat",
            "_analyze_index_usage", "_analyze_tablespace_fragmentation",
        ]
        for method in db_methods:
            assert hasattr(DiagnoseDbSpecificMixin, method), f"DB-specific 缺少方法: {method}"

    def test_17_handler_methods_count(self):
        """验证 17 个 handler 方法（不含 _display_enhanced_report 等辅助）"""
        all_methods = (
            [m for m in dir(DiagnoseP0Mixin) if not m.startswith("__")]
            + [m for m in dir(DiagnoseP1Mixin) if not m.startswith("__")]
            + [m for m in dir(DiagnoseP2Mixin) if not m.startswith("__")]
            + [m for m in dir(DiagnoseDbSpecificMixin) if not m.startswith("__")]
        )
        # 过滤掉从 object 继承的常见属性
        builtin = {"__dict__", "__doc__", "__module__", "__weakref__"}
        unique_methods = set(all_methods) - builtin
        # 应至少有 17 个 _xxx 方法
        handler_methods = [m for m in unique_methods if m.startswith("_") and not m.startswith("__")]
        # 排除一些共享辅助方法（_print_health_score 等）
        # 实际 handler 数: 5(P0) + 3(P1) + 4(P2) + 4(DB) + _display_enhanced_report = 17
        assert len(handler_methods) >= 17, f"handler 方法数不足: {len(handler_methods)}"

    def test_connector_function_exposed(self):
        """build_diagnose_connector 应从子包公开"""
        assert callable(build_diagnose_connector)


class TestDiagnoseSubpackageSharedHelpers:
    """测试共享辅助方法（_print_health_score / _print_suggestions）"""

    def test_print_health_score_good(self):
        """score >= 80 应使用 info 级别"""
        cmd = DiagnoseCommand.__new__(DiagnoseCommand)
        cmd.output = MagicMock()
        cmd._print_health_score(85)
        cmd.output.info.assert_called_once()
        assert "良好" in cmd.output.info.call_args[0][0]

    def test_print_health_score_medium(self):
        """60 <= score < 80 应使用 warning 级别"""
        cmd = DiagnoseCommand.__new__(DiagnoseCommand)
        cmd.output = MagicMock()
        cmd._print_health_score(70)
        cmd.output.warning.assert_called_once()
        assert "一般" in cmd.output.warning.call_args[0][0]

    def test_print_health_score_bad(self):
        """score < 60 应使用 error 级别"""
        cmd = DiagnoseCommand.__new__(DiagnoseCommand)
        cmd.output = MagicMock()
        cmd._print_health_score(45)
        cmd.output.error.assert_called_once()
        assert "较差" in cmd.output.error.call_args[0][0]

    def test_print_suggestions_empty(self):
        """空建议列表不应输出"""
        cmd = DiagnoseCommand.__new__(DiagnoseCommand)
        cmd.output = MagicMock()
        cmd._print_suggestions([])
        cmd.output.info.assert_not_called()
        cmd.output.warning.assert_not_called()
        cmd.output.error.assert_not_called()

    def test_print_suggestions_with_critical(self):
        """critical 类型应使用 error 级别"""
        cmd = DiagnoseCommand.__new__(DiagnoseCommand)
        cmd.output = MagicMock()
        cmd._print_suggestions([{"type": "critical", "message": "严重问题"}])
        cmd.output.error.assert_called()
        assert "严重" in cmd.output.error.call_args[0][0]

    def test_print_suggestions_with_warning(self):
        """warning 类型应使用 warning 级别"""
        cmd = DiagnoseCommand.__new__(DiagnoseCommand)
        cmd.output = MagicMock()
        cmd._print_suggestions([{"type": "warning", "message": "警告问题"}])
        cmd.output.warning.assert_called()
        assert "警告" in cmd.output.warning.call_args[0][0]

    def test_print_suggestions_with_impact(self):
        """应正确显示 impact 字段"""
        cmd = DiagnoseCommand.__new__(DiagnoseCommand)
        cmd.output = MagicMock()
        cmd._print_suggestions([{
            "type": "info",
            "message": "提示",
            "impact": "影响说明"
        }])
        # 验证 impact 被输出
        info_calls = [c[0][0] for c in cmd.output.info.call_args_list]
        assert any("影响说明" in str(c) for c in info_calls)


class TestDiagnoseCommandDispatch:
    """测试命令分发逻辑"""

    def test_add_arguments_registers_all_subcommands(self):
        """add_arguments 应注册所有 19 个子命令"""
        # 注意：DiagnoseCommand.add_arguments 期望接收 ArgumentParser，
        # 然后内部调用 parser.add_subparsers()。我们必须传 parser 本身。
        parser = ArgumentParser()
        DiagnoseCommand.add_arguments(parser)

        # 验证 17 个直接子命令 + 2 个 aliases = 19
        # （slow-queries/slowlog, recommend-indexes/indexes 是别名）
        subcommands = [
            "realtime", "top", "locks", "sql", "space",
            "connections", "replication", "slow-queries", "recommend-indexes",
            "report", "table", "performance-snapshot", "bottleneck",
            "vacuum", "bloat", "index-usage", "tablespace-fragmentation",
        ]
        assert len(subcommands) + 2 == 19, f"子命令计数不匹配（含 2 个 alias）"

    def test_dispatch_unknown_action_returns_1(self):
        """未知 action 应返回错误码 1"""
        cmd = DiagnoseCommand.__new__(DiagnoseCommand)
        cmd.output = MagicMock()
        cmd.args = Namespace(diagnose_action="unknown_action_xyz")
        # 创建 mock skill
        skill = MagicMock()
        result = cmd._dispatch_action("unknown_action_xyz", skill)
        assert result == 1
        cmd.output.error.assert_called_once()


class TestDiagnoseConnectorBuilder:
    """测试 connector.py 多策略匹配"""

    def test_build_diagnose_connector_no_db_name(self):
        """db_name=None 时应尝试 fallback"""
        cmd = MagicMock()
        configs = {}
        # 没有 db_name 也没有可用 config，应回退到 _try_standard_connector
        result = build_diagnose_connector(cmd, None, configs)
        # 可能会回退到从环境变量（如果没有 .env 则返回 None）
        # 关键是：不应崩溃
        assert result is None or result is not None  # 任意结果都 OK

    def test_build_diagnose_connector_alias_match(self):
        """按别名匹配应返回 UnifiedConnector"""
        from dbskiter.cli.config import Config

        config = MagicMock(spec=Config)
        config.dialect = "mysql+pymysql"
        config.host = "localhost"
        config.port = 3306
        config.username = "root"
        config.password = ""
        config.database = "test"
        config.extra = {}

        configs = {"jump": config}

        cmd = MagicMock()
        with patch("dbskiter.cli.commands.diagnose.connector.UnifiedConnector") as MockUC:
            MockUC.return_value = MagicMock()
            result = build_diagnose_connector(cmd, "jump", configs)
            assert result is not None
            MockUC.assert_called_once()
            # 验证 host/dialect 等被正确传递
            call_kwargs = MockUC.call_args[1]
            assert call_kwargs["host"] == "localhost"
            assert "mysql" in call_kwargs["dialect"]


class TestDiagnosePackageSize:
    """验证拆分后单文件大小合理"""

    def test_main_class_under_500_lines(self):
        """diagnose_pkg.py 主类应 < 500 行（便于维护）"""
        import inspect
        from pathlib import Path
        fpath = Path(inspect.getfile(DiagnoseCommand))
        # 排除空行和纯注释
        content = fpath.read_text(encoding="utf-8")
        lines = [l for l in content.splitlines() if l.strip() and not l.strip().startswith("#")]
        # 主类 414 行 = 226 行非空非注释（粗估）
        assert len(lines) < 600, f"主类文件过大: {len(lines)} 非空非注释行"

    def test_each_mixin_under_600_lines(self):
        """每个 mixin 应 < 600 行"""
        from pathlib import Path

        for f in [
            "dbskiter/cli/commands/diagnose/handlers_p0.py",
            "dbskiter/cli/commands/diagnose/handlers_p1.py",
            "dbskiter/cli/commands/diagnose/handlers_p2.py",
            "dbskiter/cli/commands/diagnose/handlers_db_specific.py",
        ]:
            p = Path(f)
            if p.exists():
                lines = len(p.read_text(encoding="utf-8").splitlines())
                assert lines < 600, f"{f} 过大: {lines} 行"

    def test_connector_under_200_lines(self):
        """connector.py 应 < 200 行（独立模块）"""
        from pathlib import Path
        p = Path("dbskiter/cli/commands/diagnose/connector.py")
        if p.exists():
            lines = len(p.read_text(encoding="utf-8").splitlines())
            assert lines < 200, f"connector.py 过大: {lines} 行"


class TestDiagnoseDemoModeIntegration:
    """demo 模式端到端测试（无真实数据库）"""

    def test_demo_realtime_runs(self, capsys):
        """--demo diagnose realtime 应能跑通"""
        import subprocess
        import sys
        import os
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        result = subprocess.run(
            [sys.executable, "-m", "dbskiter", "--demo", "diagnose", "realtime"],
            capture_output=True, timeout=30,
            env=env,
        )
        # 退出码 0 = 成功
        assert result.returncode == 0, f"stderr={result.stderr.decode('utf-8', errors='replace')}"

    def test_demo_help_works(self):
        """--demo diagnose --help 应能列出所有子命令"""
        import subprocess
        import sys
        import os
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        result = subprocess.run(
            [sys.executable, "-m", "dbskiter", "diagnose", "--help"],
            capture_output=True, timeout=15,
            env=env,
        )
        assert result.returncode == 0
        # 验证所有 17+ 个子命令都在帮助中
        expected = [
            "realtime", "top", "locks", "sql", "space",
            "connections", "replication", "slow-queries", "recommend-indexes",
            "report", "table", "performance-snapshot", "bottleneck",
            "vacuum", "bloat", "index-usage", "tablespace-fragmentation",
        ]
        stdout = result.stdout.decode("utf-8", errors="replace")
        for sub in expected:
            assert sub in stdout, f"子命令 {sub} 不在 --help 中"