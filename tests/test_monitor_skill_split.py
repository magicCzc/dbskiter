"""
tests/test_monitor_skill_split.py

验证 db_monitor skill.py 拆分后的 Mixin 架构完整性
"""

from dbskiter.db_monitor import MonitorSkill
from dbskiter.db_monitor.mixins import (
    HealthMixin, MonitoringMixin, CollectionMixin, AnomalyMixin,
    CapacityMixin, TrendMixin, MonitorAIContextMixin, MonitorUtilsMixin,
)


class TestMonitorSkillMixinArchitecture:
    """验证 MonitorSkill Mixin 架构完整性"""

    def test_inherits_all_mixins(self):
        mro = [c.__name__ for c in MonitorSkill.__mro__]
        assert "HealthMixin" in mro
        assert "MonitoringMixin" in mro
        assert "CollectionMixin" in mro
        assert "AnomalyMixin" in mro
        assert "CapacityMixin" in mro
        assert "TrendMixin" in mro
        assert "MonitorAIContextMixin" in mro
        assert "MonitorUtilsMixin" in mro

    def test_mixin_imports(self):
        assert HealthMixin.__name__ == "HealthMixin"
        assert MonitoringMixin.__name__ == "MonitoringMixin"
        assert CollectionMixin.__name__ == "CollectionMixin"
        assert AnomalyMixin.__name__ == "AnomalyMixin"
        assert CapacityMixin.__name__ == "CapacityMixin"


class TestMonitorMethods:
    """验证关键方法可访问"""

    def test_health_methods(self):
        assert hasattr(MonitorSkill, "assess_health")

    def test_collection_methods(self):
        assert hasattr(MonitorSkill, "collect_metrics")
        assert hasattr(MonitorSkill, "get_metric_history")

    def test_anomaly_methods(self):
        assert hasattr(MonitorSkill, "detect_anomalies")

    def test_capacity_methods(self):
        assert hasattr(MonitorSkill, "predict_capacity")
        assert hasattr(MonitorSkill, "predict_capacity_advanced")

    def test_trend_methods(self):
        assert hasattr(MonitorSkill, "analyze_trend")
        assert hasattr(MonitorSkill, "compare_with_baseline")

    def test_monitoring_methods(self):
        assert hasattr(MonitorSkill, "start_monitoring")
        assert hasattr(MonitorSkill, "stop_monitoring")
        assert hasattr(MonitorSkill, "get_alerts")
        assert hasattr(MonitorSkill, "close")

    def test_ai_context_methods(self):
        assert hasattr(MonitorSkill, "build_ai_context")