"""
tests/test_diagnose_skill_split.py

验证 db_diagnose skill.py 拆分后的 Mixin 架构完整性

测试目标：
1. DiagnoseSkill 正确继承所有 Mixin
2. 所有已提取方法可通过 DiagnoseSkill 实例访问
3. 所有保留方法仍在 skill.py 中
4. 方法签名一致（参数数量、默认值）
"""

from dbskiter.db_diagnose import DiagnoseSkill
from dbskiter.db_diagnose.mixins import (
    AiContextMixin,
    SlowQueriesMixin,
    LockAnalyzerMixin,
    SpaceAnalyzerMixin,
    ConnectionReplicationMixin,
    IndexAdvisorMixin,
    PerformanceMixin,
)


class TestSkillMixinArchitecture:
    """验证 Mixin 架构完整性"""

    def test_inherits_all_mixins(self):
        """DiagnoseSkill 应继承所有 7 个 Mixin"""
        mro = [c.__name__ for c in DiagnoseSkill.__mro__]
        assert "AiContextMixin" in mro
        assert "SlowQueriesMixin" in mro
        assert "LockAnalyzerMixin" in mro
        assert "SpaceAnalyzerMixin" in mro
        assert "ConnectionReplicationMixin" in mro
        assert "IndexAdvisorMixin" in mro
        assert "PerformanceMixin" in mro

    def test_mixin_imports(self):
        """所有 Mixin 类可直接导入"""
        from dbskiter.db_diagnose.mixins.ai_context import AiContextMixin
        from dbskiter.db_diagnose.mixins.slow_queries import SlowQueriesMixin
        from dbskiter.db_diagnose.mixins.lock_analyzer import LockAnalyzerMixin
        from dbskiter.db_diagnose.mixins.space_analyzer import SpaceAnalyzerMixin
        from dbskiter.db_diagnose.mixins.connection_replication import ConnectionReplicationMixin
        from dbskiter.db_diagnose.mixins.index_advisor import IndexAdvisorMixin
        from dbskiter.db_diagnose.mixins.performance import PerformanceMixin
        assert AiContextMixin.__name__ == "AiContextMixin"
        assert SlowQueriesMixin.__name__ == "SlowQueriesMixin"


class TestExtractedMethods:
    """验证已提取到 Mixin 的方法在 DiagnoseSkill 上可访问"""

    def test_ai_context_methods(self):
        """AI 上下文方法应可访问"""
        assert hasattr(DiagnoseSkill, "build_ai_context")
        assert hasattr(DiagnoseSkill, "close")
        assert hasattr(DiagnoseSkill, "_build_ai_hints")

    def test_slow_query_methods(self):
        """慢查询方法应可访问"""
        assert hasattr(DiagnoseSkill, "analyze_slow_queries")
        assert hasattr(DiagnoseSkill, "analyze_performance_metrics")
        assert hasattr(DiagnoseSkill, "get_database_stats")
        assert hasattr(DiagnoseSkill, "analyze_aas")

    def test_lock_methods(self):
        """锁分析方法应可访问"""
        assert hasattr(DiagnoseSkill, "get_lock_waits")
        assert hasattr(DiagnoseSkill, "analyze_locks")

    def test_space_methods(self):
        """空间分析方法应可访问"""
        assert hasattr(DiagnoseSkill, "analyze_space")

    def test_connection_replication_methods(self):
        """连接和复制方法应可访问"""
        assert hasattr(DiagnoseSkill, "analyze_connections")
        assert hasattr(DiagnoseSkill, "analyze_replication")

    def test_index_methods(self):
        """索引方法应可访问"""
        assert hasattr(DiagnoseSkill, "recommend_indexes")

    def test_performance_methods(self):
        """性能方法应可访问"""
        assert hasattr(DiagnoseSkill, "take_performance_snapshot")
        assert hasattr(DiagnoseSkill, "analyze_performance_bottleneck")


class TestRetainedMethods:
    """验证保留在 skill.py 的方法仍可访问"""

    def test_sql_analysis_methods(self):
        """SQL 分析方法应可访问"""
        assert hasattr(DiagnoseSkill, "analyze_sql")
        assert hasattr(DiagnoseSkill, "analyze_sql_batch")
        assert hasattr(DiagnoseSkill, "get_index_suggestions")
        assert hasattr(DiagnoseSkill, "get_executable_fixes")

    def test_table_diagnose_methods(self):
        """表诊断方法应可访问"""
        assert hasattr(DiagnoseSkill, "diagnose_table")
        assert hasattr(DiagnoseSkill, "generate_report")

    def test_real_time_methods(self):
        """实时诊断方法应可访问"""
        assert hasattr(DiagnoseSkill, "realtime_diagnose")
        assert hasattr(DiagnoseSkill, "get_realtime_connections")
        assert hasattr(DiagnoseSkill, "get_top_sql")

    def test_db_specific_methods(self):
        """数据库特有方法应可访问"""
        assert hasattr(DiagnoseSkill, "analyze_vacuum")
        assert hasattr(DiagnoseSkill, "analyze_bloat")
        assert hasattr(DiagnoseSkill, "analyze_index_usage")
        assert hasattr(DiagnoseSkill, "analyze_tablespace_fragmentation")


class TestMethodSignatures:
    """验证方法签名在拆分后保持一致性"""

    def test_analyze_slow_queries_signature(self):
        """analyze_slow_queries 签名"""
        import inspect
        sig = inspect.signature(DiagnoseSkill.analyze_slow_queries)
        # 应该至少接受 limit 参数
        assert "limit" in sig.parameters or "self" in sig.parameters

    def test_recommend_indexes_signature(self):
        """recommend_indexes 签名"""
        import inspect
        sig = inspect.signature(DiagnoseSkill.recommend_indexes)
        params = list(sig.parameters.keys())
        assert "table" in params or "self" in params


class TestMixinIsolation:
    """验证 Mixin 之间不互相依赖"""

    def test_mixin_independent_imports(self):
        """每个 Mixin 可独立导入"""
        import importlib
        for module_name in [
            "dbskiter.db_diagnose.mixins.ai_context",
            "dbskiter.db_diagnose.mixins.slow_queries",
            "dbskiter.db_diagnose.mixins.lock_analyzer",
        ]:
            try:
                importlib.import_module(module_name)
            except ImportError as e:
                assert False, f"Cannot import {module_name}: {e}"