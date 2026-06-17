"""
db_monitor collectors 基类模块

文件功能：定义指标采集器的抽象基类和通用数据类型
主要类：
    - MetricType: 指标类型枚举
    - MetricPoint: 指标数据点
    - BaseMetricsCollector: 指标采集器基类

作者：AI Assistant
创建时间：2026-04-23
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, Any, List, Optional
import logging

from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger(__name__)


class MetricType(str, Enum):
    """指标类型枚举"""
    # 吞吐量指标
    QPS = "qps"                              # 每秒查询数
    TPS = "tps"                              # 每秒事务数
    COM_SELECT = "com_select"                # SELECT次数
    COM_INSERT = "com_insert"                # INSERT次数
    COM_UPDATE = "com_update"                # UPDATE次数
    COM_DELETE = "com_delete"                # DELETE次数

    # 连接指标
    CONNECTIONS_ACTIVE = "connections_active"      # 活跃连接
    CONNECTIONS_TOTAL = "connections_total"        # 总连接数
    CONNECTIONS_MAX = "connections_max"            # 最大连接数
    CONNECTIONS_ABORTED = "connections_aborted"    # 异常断开连接

    # 查询性能指标
    SLOW_QUERIES = "slow_queries"            # 慢查询数
    QUERY_TIME_AVG = "query_time_avg"        # 平均查询时间
    QUERY_TIME_MAX = "query_time_max"        # 最大查询时间
    FULL_SCAN_COUNT = "full_scan_count"      # 全表扫描次数

    # 锁指标
    LOCK_WAITS = "lock_waits"                # 锁等待次数
    LOCK_WAIT_TIME = "lock_wait_time"        # 锁等待时间
    DEADLOCKS = "deadlocks"                  # 死锁次数
    ROW_LOCK_WAITS = "row_lock_waits"        # 行锁等待

    # 缓冲/缓存指标
    BUFFER_HIT_RATIO = "buffer_hit_ratio"          # 缓冲命中率
    BUFFER_POOL_USAGE = "buffer_pool_usage"        # 缓冲池使用率
    CACHE_HIT_RATIO = "cache_hit_ratio"            # 缓存命中率
    SHARED_BUFFER_USAGE = "shared_buffer_usage"    # 共享缓冲区使用率

    # IO指标
    ROWS_READ = "rows_read"                  # 读取行数
    ROWS_CHANGED = "rows_changed"            # 修改行数
    PHYSICAL_READS = "physical_reads"        # 物理读
    LOGICAL_READS = "logical_reads"          # 逻辑读
    DISK_IO_READ = "disk_io_read"            # 磁盘读IO
    DISK_IO_WRITE = "disk_io_write"          # 磁盘写IO
    DISK_IO_WAIT = "disk_io_wait"            # 磁盘IO等待

    # 资源指标
    CPU_USAGE = "cpu_usage"                  # CPU使用率
    MEMORY_USAGE = "memory_usage"            # 内存使用率
    DISK_USAGE = "disk_usage"                # 磁盘使用率
    TEMP_SPACE_USAGE = "temp_space_usage"    # 临时空间使用率

    # 复制/同步指标
    REPLICATION_LAG = "replication_lag"      # 复制延迟
    REPLICATION_IO = "replication_io"        # IO线程状态
    REPLICATION_SQL = "replication_sql"      # SQL线程状态

    # 临时表指标
    TEMP_TABLES_DISK = "temp_tables_disk"    # 磁盘临时表
    TEMP_TABLES_MEMORY = "temp_tables_memory"  # 内存临时表

    # 表缓存指标
    TABLE_OPEN_CACHE = "table_open_cache"    # 表缓存使用率
    TABLE_DEFINITIONS_CACHE = "table_definitions_cache"  # 表定义缓存

    # 事务指标
    TRANSACTIONS_ACTIVE = "transactions_active"    # 活跃事务
    TRANSACTIONS_COMMITTED = "transactions_committed"  # 提交事务数
    TRANSACTIONS_ROLLED_BACK = "transactions_rolled_back"  # 回滚事务数


@dataclass
class MetricPoint:
    """指标数据点"""
    timestamp: datetime
    metric_type: MetricType
    value: float
    unit: str = ""
    tags: Dict[str, str] = field(default_factory=dict)
    source: str = "direct"

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "timestamp": self.timestamp.isoformat(),
            "metric_type": self.metric_type.value,
            "value": self.value,
            "unit": self.unit,
            "tags": self.tags,
            "source": self.source
        }


@dataclass
class MetricQuery:
    """指标查询定义"""
    sql: str
    extract: callable
    unit: str = ""
    is_counter: bool = False


class BaseMetricsCollector(ABC):
    """
    指标采集器基类

    定义通用的指标采集接口，具体数据库类型需要继承此类
    实现特定数据库的指标采集逻辑

    属性:
        connector: 数据库连接器
        dialect: 数据库方言
    """

    def __init__(self, connector):
        """
        初始化采集器

        参数:
            connector: 数据库连接器
        """
        self.connector = connector
        self.dialect = connector.dialect.lower()
        logger.info(f"初始化 {self.__class__.__name__} (dialect={self.dialect})")

    @abstractmethod
    def get_metric_queries(self) -> Dict[MetricType, MetricQuery]:
        """
        获取指标查询定义

        返回:
            Dict[MetricType, MetricQuery]: 指标类型到查询定义的映射
        """
        pass

    def _health_check(self) -> None:
        """
        连接健康检查

        执行简单的 SELECT 1 查询验证连接是否可用。
        如果连接失败，抛出异常，让 collect_all_metrics 统一处理。

        异常说明：
            - ConnectionError: 连接失败
            - PermissionError: 权限不足
            - SQLAlchemyError: 数据库异常
        """
        try:
            self.connector.execute("SELECT 1")
        except Exception as e:
            # 将异常重新抛出为 SQLAlchemyError，以便统一捕获
            raise SQLAlchemyError(f"数据库连接检查失败: {e}") from e

    def collect_all_metrics(self) -> List[MetricPoint]:
        """
        采集所有指标

        采集前先做连接健康检查，如果连接失败只报一次错误，
        避免每个指标都重复报错。

        返回:
            List[MetricPoint]: 指标数据点列表
        """
        timestamp = datetime.now()
        queries = self.get_metric_queries()

        # 先做连接健康检查，只报一次错误
        try:
            self._health_check()
        except ConnectionError as e:
            logger.warning(f"数据库连接失败，跳过指标采集: {e}")
            return []
        except PermissionError as e:
            logger.warning(f"数据库权限不足，跳过指标采集: {e}")
            return []
        except SQLAlchemyError as e:
            logger.warning(f"数据库连接异常，跳过指标采集: {e}")
            return []
        except Exception as e:
            logger.warning(f"数据库连接检查失败，跳过指标采集: {e}")
            return []

        metrics = []

        for metric_type, query_def in queries.items():
            try:
                metric = self._collect_single_metric(
                    metric_type, query_def, timestamp
                )
                if metric:
                    metrics.append(metric)
            except ConnectionError as e:
                logger.warning(f"采集指标 {metric_type.value} 时连接失败: {e}")
            except PermissionError as e:
                logger.warning(f"采集指标 {metric_type.value} 时权限不足: {e}")
            except ValueError as e:
                logger.warning(f"采集指标 {metric_type.value} 时数据解析错误: {e}")
            except SQLAlchemyError as e:
                logger.warning(f"采集指标 {metric_type.value} 时SQL错误: {e}")
            except Exception as e:
                logger.warning(f"采集指标 {metric_type.value} 时未知错误: {e}")

        logger.info(f"成功采集 {len(metrics)} 个指标")
        return metrics

    def collect_metric(self, metric_type: MetricType) -> Optional[MetricPoint]:
        """
        采集单个指标

        参数:
            metric_type: 指标类型

        返回:
            Optional[MetricPoint]: 指标数据点，失败返回None
        """
        queries = self.get_metric_queries()
        query_def = queries.get(metric_type)

        if not query_def:
            logger.warning(f"未知的指标类型: {metric_type}")
            return None

        try:
            return self._collect_single_metric(
                metric_type, query_def, datetime.now()
            )
        except ConnectionError as e:
            logger.warning(f"采集指标 {metric_type.value} 时连接失败: {e}")
            return None
        except PermissionError as e:
            logger.warning(f"采集指标 {metric_type.value} 时权限不足: {e}")
            return None
        except ValueError as e:
            logger.warning(f"采集指标 {metric_type.value} 时数据解析错误: {e}")
            return None

    def _collect_single_metric(
        self,
        metric_type: MetricType,
        query_def: MetricQuery,
        timestamp: datetime
    ) -> Optional[MetricPoint]:
        """
        采集单个指标的内部方法

        参数:
            metric_type: 指标类型
            query_def: 查询定义
            timestamp: 时间戳

        返回:
            Optional[MetricPoint]: 指标数据点
        """
        result = self.connector.execute(query_def.sql)
        value = query_def.extract(result.rows if result else [])

        return MetricPoint(
            timestamp=timestamp,
            metric_type=metric_type,
            value=value,
            unit=query_def.unit,
            source="direct"
        )

    def _safe_extract_float(
        self,
        rows: List[tuple],
        default: float = 0.0,
        index: int = 0
    ) -> float:
        """
        安全地从查询结果中提取浮点数

        参数:
            rows: 查询结果行
            default: 默认值
            index: 列索引

        返回:
            float: 提取的值或默认值
        """
        try:
            if rows and rows[0] and rows[0][index] is not None:
                return float(rows[0][index])
        except (IndexError, ValueError, TypeError):
            pass
        return default

    def _safe_extract_int(
        self,
        rows: List[tuple],
        default: int = 0,
        index: int = 0
    ) -> int:
        """
        安全地从查询结果中提取整数

        参数:
            rows: 查询结果行
            default: 默认值
            index: 列索引

        返回:
            int: 提取的值或默认值
        """
        try:
            if rows and rows[0] and rows[0][index] is not None:
                return int(rows[0][index])
        except (IndexError, ValueError, TypeError):
            pass
        return default
