"""
diagnose 子包

将 2081 行的 diagnose.py 拆分为 4 个 handler mixin + 1 个 connector：

- handlers_p0.py          P0 高频场景（realtime/top/locks/sql/space）
- handlers_p1.py          P1 中频场景（connections/replication/slow-queries/recommend-indexes）
- handlers_p2.py          P2 低频场景（report/table/performance-snapshot/bottleneck）
- handlers_db_specific.py 数据库特有诊断（vacuum/bloat/index-usage/tablespace-fragmentation）
- connector.py            诊断专用连接器

拆分原则：
    1. 按使用频率分层（P0/P1/P2）
    2. 共享的 _print_health_score / _print_suggestions 放在 db_specific mixin
    3. connector.py 单独管理复杂的多策略匹配
"""

from .handlers_p0 import DiagnoseP0Mixin
from .handlers_p1 import DiagnoseP1Mixin
from .handlers_p2 import DiagnoseP2Mixin
from .handlers_db_specific import DiagnoseDbSpecificMixin
from .connector import build_diagnose_connector

__all__ = [
    "DiagnoseP0Mixin",
    "DiagnoseP1Mixin",
    "DiagnoseP2Mixin",
    "DiagnoseDbSpecificMixin",
    "build_diagnose_connector",
]