"""Mixin modules for DiagnoseSkill"""

from .ai_context import AiContextMixin
from .slow_queries import SlowQueriesMixin
from .lock_analyzer import LockAnalyzerMixin
from .space_analyzer import SpaceAnalyzerMixin
from .connection_replication import ConnectionReplicationMixin
from .index_advisor import IndexAdvisorMixin
from .performance import PerformanceMixin

__all__ = [
    "AiContextMixin",
    "SlowQueriesMixin",
    "LockAnalyzerMixin",
    "SpaceAnalyzerMixin",
    "ConnectionReplicationMixin",
    "IndexAdvisorMixin",
    "PerformanceMixin",
]
