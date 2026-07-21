"""
SQLite性能分析器 - 基于统一性能模型

文件功能：使用统一性能模型分析SQLite数据库性能
主要类：SQLitePerformanceAnalyzer

特性：
    1. 统一接口：遵循PerformanceAnalyzer基类
    2. 生产安全：内置超时、降级机制
    3. PRAGMA查询：基于SQLite特有PRAGMA命令

作者: Magiczc
创建时间: 2026-06-04
版本: 1.0.0
"""

import logging
from typing import List, Optional, Tuple

from dbskiter.shared.unified_connector import UnifiedConnector
from ..core.performance_model import (
    PerformanceAnalyzer,
    PerformanceMetric,
    SlowQueryInfo,
    MetricCategory,
    get_threshold
)

logger = logging.getLogger(__name__)


class SQLitePerformanceAnalyzer(PerformanceAnalyzer):
    """
    SQLite性能分析器

    使用统一性能模型分析SQLite性能，支持：
    - PRAGMA命令查询
    - 数据库文件状态分析
    - 缓存命中率估算
    """

    def __init__(self, connector: UnifiedConnector, timeout: int = 30):
        """
        初始化SQLite性能分析器

        参数:
            connector: 数据库连接器
            timeout: 查询超时时间(秒)
        """
        super().__init__(connector, timeout)

    def collect_metrics(self) -> List[PerformanceMetric]:
        """
        采集SQLite性能指标

        返回:
            性能指标列表
        """
        metrics = []

        # 采集各类指标
        metrics.extend(self._collect_memory_metrics())
        metrics.extend(self._collect_io_metrics())
        metrics.extend(self._collect_concurrency_metrics())

        return metrics

    def _collect_memory_metrics(self) -> List[PerformanceMetric]:
        """采集内存相关指标"""
        metrics = []

        try:
            # 获取缓存大小
            result = self._execute_with_timeout("PRAGMA cache_size")
            cache_size = int(result[0][0]) if result and result[0] else 0

            # cache_size为负数时表示以KB为单位的页缓存大小
            if cache_size < 0:
                cache_kb = abs(cache_size)
            else:
                # 正数表示页数，需要乘以页大小
                result = self._execute_with_timeout("PRAGMA page_size")
                page_size = int(result[0][0]) if result and result[0] else 4096
                cache_kb = (cache_size * page_size) / 1024

            metrics.append(PerformanceMetric(
                name="cache_size_kb",
                value=round(cache_kb, 2),
                unit="KB",
                category=MetricCategory.MEMORY,
                source="PRAGMA cache_size"
            ))

            # 获取页缓存使用情况（近似）
            result = self._execute_with_timeout("PRAGMA page_count")
            page_count = int(result[0][0]) if result and result[0] else 0

            result = self._execute_with_timeout("PRAGMA freelist_count")
            free_pages = int(result[0][0]) if result and result[0] else 0

            used_pages = page_count - free_pages
            usage_pct = (used_pages / page_count) * 100 if page_count > 0 else 0

            threshold = get_threshold("memory_usage")
            metrics.append(PerformanceMetric(
                name="page_usage_ratio",
                value=round(usage_pct, 2),
                unit="%",
                category=MetricCategory.MEMORY,
                threshold_warning=threshold.get("warning"),
                threshold_critical=threshold.get("critical"),
                source="PRAGMA page_count"
            ))

            # 计算缓存命中率
            try:
                cache_hit_ratio = self._calculate_cache_hit_ratio()
                if cache_hit_ratio is not None:
                    metrics.append(PerformanceMetric(
                        name="cache_hit_ratio",
                        value=round(cache_hit_ratio, 2),
                        unit="%",
                        category=MetricCategory.MEMORY,
                        threshold_warning=85.0,
                        threshold_critical=70.0,
                        source="PRAGMA cache_hit_ratio"
                    ))
            except Exception as e:
                logger.warning(f"缓存命中率计算失败: {str(e).split(chr(10))[0][:120]}")

        except Exception as e:
            logger.warning(f"内存指标采集失败: {str(e).split(chr(10))[0][:120]}")

        return metrics

    def _calculate_cache_hit_ratio(self) -> Optional[float]:
        """
        计算SQLite缓存命中率

        SQLite没有直接提供缓存命中率的PRAGMA，
        通过比较数据库文件大小和实际使用页面数来估算

        返回:
            float: 缓存命中率百分比，None表示无法计算
        """
        try:
            # 获取页大小
            result = self._execute_with_timeout("PRAGMA page_size")
            page_size = int(result[0][0]) if result and result[0] else 4096

            # 获取总页数
            result = self._execute_with_timeout("PRAGMA page_count")
            total_pages = int(result[0][0]) if result and result[0] else 0

            # 获取空闲页数
            result = self._execute_with_timeout("PRAGMA freelist_count")
            free_pages = int(result[0][0]) if result and result[0] else 0

            if total_pages <= 0:
                return None

            # 计算已使用页面比例作为缓存命中率估算
            # 实际缓存命中率需要更复杂的统计，这里使用页面使用率作为近似
            used_pages = total_pages - free_pages
            hit_ratio = (used_pages / total_pages) * 100

            return hit_ratio

        except Exception:
            return None

    def _collect_io_metrics(self) -> List[PerformanceMetric]:
        """采集IO相关指标"""
        metrics = []

        try:
            # 获取数据库文件大小
            result = self._execute_with_timeout("PRAGMA page_count")
            page_count = int(result[0][0]) if result and result[0] else 0

            result = self._execute_with_timeout("PRAGMA page_size")
            page_size = int(result[0][0]) if result and result[0] else 4096

            db_size_mb = (page_count * page_size) / 1024 / 1024

            metrics.append(PerformanceMetric(
                name="database_size_mb",
                value=round(db_size_mb, 2),
                unit="MB",
                category=MetricCategory.IO,
                source="PRAGMA page_count"
            ))

            # 获取空闲页面
            result = self._execute_with_timeout("PRAGMA freelist_count")
            free_pages = int(result[0][0]) if result and result[0] else 0

            free_mb = (free_pages * page_size) / 1024 / 1024
            metrics.append(PerformanceMetric(
                name="free_space_mb",
                value=round(free_mb, 2),
                unit="MB",
                category=MetricCategory.IO,
                source="PRAGMA freelist_count"
            ))

            # 获取WAL文件大小（如果启用WAL）
            try:
                result = self._execute_with_timeout("PRAGMA journal_mode")
                journal_mode = str(result[0][0]).upper() if result and result[0] else "DELETE"

                if journal_mode == "WAL":
                    # WAL文件大小无法直接通过PRAGMA获取，这里只是标记
                    metrics.append(PerformanceMetric(
                        name="wal_mode_enabled",
                        value=1,
                        unit="bool",
                        category=MetricCategory.IO,
                        source="PRAGMA journal_mode"
                    ))
            except Exception:
                pass

        except Exception as e:
            logger.warning(f"IO指标采集失败: {str(e).split(chr(10))[0][:120]}")

        return metrics

    def _collect_concurrency_metrics(self) -> List[PerformanceMetric]:
        """采集并发相关指标"""
        metrics = []

        try:
            # SQLite是单连接数据库（通常）
            # 获取锁状态
            result = self._execute_with_timeout("PRAGMA lock_status")
            lock_count = len(result) if result else 0

            metrics.append(PerformanceMetric(
                name="active_locks",
                value=lock_count,
                unit="count",
                category=MetricCategory.CONCURRENCY,
                source="PRAGMA lock_status"
            ))

            # 获取线程安全模式
            result = self._execute_with_timeout("PRAGMA compile_options")
            compile_options = [str(row[0]) for row in result] if result else []

            threadsafe = 1  # 默认单线程
            for opt in compile_options:
                if "THREADSAFE" in opt:
                    try:
                        threadsafe = int(opt.split("=")[1])
                    except (IndexError, ValueError):
                        pass

            metrics.append(PerformanceMetric(
                name="threadsafe_mode",
                value=threadsafe,
                unit="level",
                category=MetricCategory.CONCURRENCY,
                source="PRAGMA compile_options"
            ))

        except Exception as e:
            logger.warning(f"并发指标采集失败: {str(e).split(chr(10))[0][:120]}")

        return metrics

    def collect_slow_queries(self, limit: int = 20,
                            min_time_ms: float = 1000) -> List[SlowQueryInfo]:
        """
        采集慢查询

        SQLite没有内置慢查询日志，基于查询计划估算

        参数:
            limit: 返回条数限制
            min_time_ms: 最小执行时间(毫秒)

        返回:
            慢查询列表
        """
        slow_queries = []

        # SQLite没有内置慢查询日志，返回空列表
        # 实际慢查询分析需要通过EXPLAIN QUERY PLAN手动分析
        logger.info("SQLite不支持自动慢查询采集，请使用EXPLAIN QUERY PLAN手动分析")

        return slow_queries

    def get_active_sessions(self) -> Tuple[int, int]:
        """
        获取会话信息

        SQLite是单连接数据库

        返回:
            (活跃会话数, 总会话数)
        """
        try:
            # SQLite通常只有一个连接
            # 通过锁状态判断是否有活跃事务
            result = self._execute_with_timeout("PRAGMA lock_status")
            active = 1 if result and len(result) > 0 else 0

            # SQLite最大连接数为1（文件级锁）
            return active, 1

        except Exception as e:
            logger.warning(f"会话信息采集失败: {str(e).split(chr(10))[0][:120]}")
            return 0, 1
