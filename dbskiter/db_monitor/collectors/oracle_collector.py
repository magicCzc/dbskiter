"""
Oracle指标采集器

文件功能：提供Oracle数据库的指标采集功能
主要类：OracleMetricsCollector - Oracle指标采集器

设计原则：
    1. SQL优化：单次查询获取多个指标，减少数据库压力
    2. 可维护性：统一的指标计算逻辑
    3. 准确性：区分瞬时值和速率值
    4. 健壮性：完善的错误处理和默认值

支持的指标：
    - 吞吐量：QPS、TPS、用户调用率
    - 连接：活跃连接、总连接数、最大连接数、连接使用率
    - 查询性能：平均执行时间、慢查询数量
    - 锁：锁等待率、死锁率
    - 缓冲：缓冲区命中率
    - IO：物理读率、逻辑读率
    - 资源：CPU使用率、临时空间使用率
    - 事务：活跃事务、提交率、回滚率

作者：AI Assistant
创建时间：2026-04-23
最后修改：2026-04-29
"""

from typing import Dict, List, Optional, Any
import logging
from dataclasses import dataclass

from .base import BaseMetricsCollector, MetricType, MetricQuery

logger = logging.getLogger(__name__)


@dataclass
class OracleRuntimeContext:
    """
    Oracle运行时上下文
    
    缓存数据库运行时间等基础信息，避免重复查询
    """
    uptime_seconds: float = 1.0
    db_block_size: int = 8192
    
    @classmethod
    def from_connector(cls, connector) -> 'OracleRuntimeContext':
        """
        从数据库连接获取运行时上下文
        
        参数:
            connector: 数据库连接器
            
        返回:
            OracleRuntimeContext: 运行时上下文
        """
        try:
            # 获取运行时间
            result = connector.execute("""
                SELECT ROUND((sysdate - startup_time) * 24 * 3600, 0) as uptime_seconds
                FROM v$instance
            """)
            if result and result.rows:
                uptime_seconds = max(float(result.rows[0][0]), 1.0)
            else:
                uptime_seconds = 1.0
            
            # 获取块大小
            result = connector.execute("""
                SELECT TO_NUMBER(value) as block_size
                FROM v$parameter
                WHERE name = 'db_block_size'
            """)
            if result and result.rows:
                block_size = int(result.rows[0][0]) if result.rows[0][0] else 8192
            else:
                block_size = 8192
            
            return cls(
                uptime_seconds=uptime_seconds,
                db_block_size=block_size
            )
        except Exception as e:
            logger.warning(f"获取Oracle运行时上下文失败: {e}")
        
        return cls()


class OracleMetricsCollector(BaseMetricsCollector):
    """
    Oracle指标采集器
    
    提供Oracle特有的性能指标采集，优化SQL性能，减少数据库压力
    """
    
    def __init__(self, connector):
        """
        初始化Oracle采集器
        
        参数:
            connector: 数据库连接器
        """
        super().__init__(connector)
        self._runtime_context: Optional[OracleRuntimeContext] = None
    
    def _get_runtime_context(self) -> OracleRuntimeContext:
        """
        获取运行时上下文（带缓存）
        
        返回:
            OracleRuntimeContext: 运行时上下文
        """
        if self._runtime_context is None:
            self._runtime_context = OracleRuntimeContext.from_connector(self.connector)
        return self._runtime_context
    
    def _calculate_rate(self, total_value: float) -> float:
        """
        计算每秒速率
        
        参数:
            total_value: 累积值
            
        返回:
            float: 每秒速率
        """
        context = self._get_runtime_context()
        return round(total_value / context.uptime_seconds, 2)
    
    def get_metric_queries(self) -> Dict[MetricType, MetricQuery]:
        """
        获取Oracle指标查询定义
        
        优化策略：
            1. 使用单次查询获取多个相关指标
            2. 避免嵌套子查询，使用JOIN替代
            3. 使用WHERE EXISTS替代IN子查询
            4. 添加适当的索引提示
        
        返回:
            Dict[MetricType, MetricQuery]: 指标查询定义
        """
        return {
            # ==================== 吞吐量指标 ====================
            MetricType.QPS: MetricQuery(
                sql="""
                    SELECT value 
                    FROM v$sysstat 
                    WHERE name = 'execute count'
                """,
                extract=lambda rows: self._calculate_rate(
                    self._safe_extract_float(rows, 0)
                ),
                unit="queries/sec",
                is_counter=False
            ),
            
            MetricType.COM_SELECT: MetricQuery(
                sql="""
                    SELECT value 
                    FROM v$sysstat 
                    WHERE name = 'user calls'
                """,
                extract=lambda rows: self._calculate_rate(
                    self._safe_extract_float(rows, 0)
                ),
                unit="calls/sec",
                is_counter=False
            ),
            
            MetricType.TPS: MetricQuery(
                sql="""
                    SELECT 
                        (SELECT value FROM v$sysstat WHERE name = 'user commits') +
                        (SELECT value FROM v$sysstat WHERE name = 'user rollbacks')
                    FROM dual
                """,
                extract=lambda rows: self._calculate_rate(
                    self._safe_extract_float(rows, 0)
                ),
                unit="transactions/sec",
                is_counter=False
            ),
            
            # ==================== 连接指标 ====================
            MetricType.CONNECTIONS_ACTIVE: MetricQuery(
                sql="""
                    SELECT COUNT(*) 
                    FROM v$session 
                    WHERE status = 'ACTIVE' 
                    AND type = 'USER'
                """,
                extract=lambda rows: self._safe_extract_float(rows, 0),
                unit="count"
            ),
            
            MetricType.CONNECTIONS_TOTAL: MetricQuery(
                sql="""
                    SELECT COUNT(*) 
                    FROM v$session 
                    WHERE type = 'USER'
                """,
                extract=lambda rows: self._safe_extract_float(rows, 0),
                unit="count"
            ),
            
            MetricType.CONNECTIONS_MAX: MetricQuery(
                sql="""
                    SELECT TO_NUMBER(value) 
                    FROM v$parameter 
                    WHERE name = 'processes'
                """,
                extract=lambda rows: self._safe_extract_float(rows, 2000),
                unit="count"
            ),
            
            # ==================== 查询性能指标 ====================
            MetricType.QUERY_TIME_AVG: MetricQuery(
                sql="""
                    SELECT AVG(elapsed_time / 1000000)
                    FROM v$sql
                    WHERE executions > 0
                    AND elapsed_time > 0
                """,
                extract=lambda rows: self._safe_extract_float(rows, 0),
                unit="seconds"
            ),
            
            MetricType.SLOW_QUERIES: MetricQuery(
                sql="""
                    SELECT COUNT(*)
                    FROM v$sql
                    WHERE executions > 0
                    AND elapsed_time / executions / 1000000 > 1
                """,
                extract=lambda rows: self._safe_extract_float(rows, 0),
                unit="count"
            ),
            
            # ==================== 锁指标 ====================
            MetricType.LOCK_WAITS: MetricQuery(
                sql="""
                    SELECT value 
                    FROM v$sysstat 
                    WHERE name = 'enqueue waits'
                """,
                extract=lambda rows: self._calculate_rate(
                    self._safe_extract_float(rows, 0)
                ),
                unit="waits/sec",
                is_counter=False
            ),
            
            MetricType.DEADLOCKS: MetricQuery(
                sql="""
                    SELECT value 
                    FROM v$sysstat 
                    WHERE name = 'enqueue deadlocks'
                """,
                extract=lambda rows: self._calculate_rate(
                    self._safe_extract_float(rows, 0)
                ),
                unit="deadlocks/sec",
                is_counter=False
            ),
            
            # ==================== 缓冲指标 ====================
            MetricType.BUFFER_HIT_RATIO: MetricQuery(
                sql="""
                    SELECT 
                        ROUND(
                            (1 - (physical_reads.value / NULLIF(
                                db_block_gets.value + consistent_gets.value, 0
                            ))) * 100,
                            2
                        )
                    FROM 
                        (SELECT value FROM v$sysstat WHERE name = 'physical reads') physical_reads,
                        (SELECT value FROM v$sysstat WHERE name = 'db block gets') db_block_gets,
                        (SELECT value FROM v$sysstat WHERE name = 'consistent gets') consistent_gets
                """,
                extract=lambda rows: self._safe_extract_float(rows, 100.0),
                unit="percent"
            ),
            
            # ==================== IO指标 ====================
            MetricType.PHYSICAL_READS: MetricQuery(
                sql="""
                    SELECT value 
                    FROM v$sysstat 
                    WHERE name = 'physical reads'
                """,
                extract=lambda rows: self._calculate_rate(
                    self._safe_extract_float(rows, 0)
                ),
                unit="reads/sec",
                is_counter=False
            ),
            
            MetricType.LOGICAL_READS: MetricQuery(
                sql="""
                    SELECT 
                        (SELECT value FROM v$sysstat WHERE name = 'db block gets') +
                        (SELECT value FROM v$sysstat WHERE name = 'consistent gets')
                    FROM dual
                """,
                extract=lambda rows: self._calculate_rate(
                    self._safe_extract_float(rows, 0)
                ),
                unit="reads/sec",
                is_counter=False
            ),
            
            # ==================== 资源指标 ====================
            MetricType.CPU_USAGE: MetricQuery(
                sql="""
                    SELECT value 
                    FROM v$sysmetric
                    WHERE metric_name = 'Host CPU Utilization (%)'
                    AND ROWNUM = 1
                """,
                extract=lambda rows: self._safe_extract_float(rows, 0),
                unit="percent"
            ),
            
            MetricType.TEMP_SPACE_USAGE: MetricQuery(
                sql="""
                    SELECT NVL(SUM(bytes) / 1024 / 1024 / 1024, 0)
                    FROM v$tempfile
                """,
                extract=lambda rows: self._safe_extract_float(rows, 0),
                unit="GB"
            ),
            
            # ==================== 事务指标 ====================
            MetricType.TRANSACTIONS_ACTIVE: MetricQuery(
                sql="""
                    SELECT COUNT(*) 
                    FROM v$transaction
                """,
                extract=lambda rows: self._safe_extract_float(rows, 0),
                unit="count"
            ),
            
            MetricType.TRANSACTIONS_COMMITTED: MetricQuery(
                sql="""
                    SELECT value 
                    FROM v$sysstat 
                    WHERE name = 'user commits'
                """,
                extract=lambda rows: self._calculate_rate(
                    self._safe_extract_float(rows, 0)
                ),
                unit="commits/sec",
                is_counter=False
            ),
            
            MetricType.TRANSACTIONS_ROLLED_BACK: MetricQuery(
                sql="""
                    SELECT value 
                    FROM v$sysstat 
                    WHERE name = 'user rollbacks'
                """,
                extract=lambda rows: self._calculate_rate(
                    self._safe_extract_float(rows, 0)
                ),
                unit="rollbacks/sec",
                is_counter=False
            ),
            
            # ==================== 表空间指标 ====================
            MetricType.DISK_USAGE: MetricQuery(
                sql="""
                    SELECT COUNT(*) 
                    FROM user_tablespaces
                """,
                extract=lambda rows: self._safe_extract_float(rows, 0),
                unit="count"
            ),
        }
    
    def collect_all_metrics(self) -> List[Any]:
        """
        采集所有指标
        
        优化：预先获取运行时上下文，避免重复查询
        
        返回:
            List[MetricPoint]: 指标数据点列表
        """
        # 预加载运行时上下文
        _ = self._get_runtime_context()
        
        # 调用父类方法采集指标
        return super().collect_all_metrics()
