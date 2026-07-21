"""
增强型慢查询分析器

文件功能：提供完整的慢查询分析能力，包括日志解析、指纹聚合、报告生成
主要类：
    - SlowQueryAnalyzer: 慢查询分析器
    - SlowQueryReport: 慢查询分析报告
    - QueryPatternStats: 查询模式统计

设计原则：
    1. 多数据源：支持实时采集和日志文件解析
    2. 高性能：流式处理，内存友好
    3. 多维度：时间、频率、扫描行数等多维度分析
    4. 可扩展：支持MySQL、Oracle等多种数据库

使用示例：
    from dbskiter.db_diagnose.core.slow_query_analyzer import SlowQueryAnalyzer

    analyzer = SlowQueryAnalyzer(connector)

    # 分析实时慢查询
    report = analyzer.analyze_realtime(limit=20, min_time=1.0)

    # 分析日志文件
    report = analyzer.analyze_log_file('/var/log/mysql/slow.log', since='24h')

作者: Magiczc
创建时间: 2026-04-29
"""

import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional, Union
from dataclasses import dataclass, field
from collections import defaultdict
import statistics

from dbskiter.shared.unified_connector import UnifiedConnector
from dbskiter.shared.sql_fingerprint import SQLFingerprinter, FingerprintResult
from dbskiter.shared.slow_log_parser import (
    MySQLSlowLogParser, ParsedSlowQuery, QueryAggregator, QueryPattern
)
from dbskiter.shared.mysql_slow_query_collector import MySQLSlowQueryCollector

logger = logging.getLogger(__name__)


@dataclass
class QueryPatternStats:
    """
    查询模式统计详情

    属性:
        fingerprint: SQL指纹
        sql_pattern: SQL模式示例
        count: 执行次数
        total_time: 总执行时间（秒）
        avg_time: 平均执行时间
        min_time: 最小执行时间
        max_time: 最大执行时间
        p95_time: 95分位执行时间
        p99_time: 99分位执行时间
        std_dev: 标准差
        total_rows_examined: 总扫描行数
        avg_rows_examined: 平均扫描行数
        total_rows_sent: 总返回行数
        first_seen: 首次出现时间
        last_seen: 最后出现时间
        time_distribution: 时间分布（按小时）
    """
    fingerprint: str
    sql_pattern: str
    count: int = 0
    total_time: float = 0.0
    avg_time: float = 0.0
    min_time: float = float('inf')
    max_time: float = 0.0
    p95_time: float = 0.0
    p99_time: float = 0.0
    std_dev: float = 0.0
    total_rows_examined: int = 0
    avg_rows_examined: float = 0.0
    total_rows_sent: int = 0
    first_seen: Optional[datetime] = None
    last_seen: Optional[datetime] = None
    time_distribution: Dict[int, int] = field(default_factory=dict)


@dataclass
class SlowQueryReport:
    """
    慢查询分析报告

    属性:
        total_queries: 总查询数
        unique_patterns: 唯一模式数
        total_time: 总执行时间
        avg_time: 平均执行时间
        time_range: 时间范围（开始, 结束）
        top_patterns: TOP查询模式列表
        patterns_by_count: 按次数排序的模式
        patterns_by_avg_time: 按平均时间排序的模式
        hourly_distribution: 小时级分布
        recommendations: 优化建议
    """
    total_queries: int = 0
    unique_patterns: int = 0
    total_time: float = 0.0
    avg_time: float = 0.0
    time_range: tuple = field(default_factory=lambda: (None, None))
    top_patterns: List[QueryPatternStats] = field(default_factory=list)
    patterns_by_count: List[QueryPatternStats] = field(default_factory=list)
    patterns_by_avg_time: List[QueryPatternStats] = field(default_factory=list)
    hourly_distribution: Dict[int, int] = field(default_factory=dict)
    recommendations: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            'summary': {
                'total_queries': self.total_queries,
                'unique_patterns': self.unique_patterns,
                'total_time': round(self.total_time, 2),
                'avg_time': round(self.avg_time, 3),
                'time_range': [
                    self.time_range[0].isoformat() if self.time_range[0] else None,
                    self.time_range[1].isoformat() if self.time_range[1] else None
                ]
            },
            'top_patterns': [
                {
                    'fingerprint': p.fingerprint,
                    'sql_pattern': p.sql_pattern,
                    'count': p.count,
                    'total_time': round(p.total_time, 2),
                    'avg_time': round(p.avg_time, 3),
                    'p95_time': round(p.p95_time, 3),
                    'rows_examined': p.total_rows_examined,
                    'rows_sent': p.total_rows_sent
                }
                for p in self.top_patterns[:10]
            ],
            'recommendations': self.recommendations
        }


class SlowQueryAnalyzer:
    """
    增强型慢查询分析器

    提供完整的慢查询分析能力，包括：
    - 实时慢查询采集分析
    - 日志文件解析分析
    - SQL指纹归并
    - 多维度统计报告
    """

    def __init__(self, connector: UnifiedConnector):
        """
        初始化分析器

        参数:
            connector: 数据库连接器
        """
        self.connector = connector
        self.fingerprinter = SQLFingerprinter()
        self.log_parser = MySQLSlowLogParser()
        self.realtime_collector = MySQLSlowQueryCollector(connector)

    def analyze_realtime(self, limit: int = 20,
                         min_time: float = 1.0) -> SlowQueryReport:
        """
        分析实时慢查询

        参数:
            limit: 采集条数限制
            min_time: 最小执行时间（秒）

        返回:
            SlowQueryReport: 分析报告
        """
        logger.info(f"开始分析实时慢查询（limit={limit}, min_time={min_time}s）")

        # 采集慢查询
        queries = self.realtime_collector.collect_slow_queries(
            limit=limit,
            min_time=min_time
        )

        if not queries:
            return SlowQueryReport(
                recommendations=["未采集到慢查询，请检查：\n"
                               "1. performance_schema是否启用\n"
                               "2. long_query_time配置\n"
                               "3. 是否有慢查询产生"]
            )

        # 转换为ParsedSlowQuery格式
        parsed_queries = []
        for q in queries:
            parsed = ParsedSlowQuery(
                sql=getattr(q, 'sql', '') or getattr(q, 'sql_text', ''),
                query_time=q.query_time,
                rows_examined=q.rows_examined,
                rows_sent=q.rows_sent,
                first_seen=getattr(q, 'first_seen', None),
                last_seen=getattr(q, 'last_seen', None),
                db=getattr(q, 'database', None) or getattr(q, 'db', None)
            )
            parsed_queries.append(parsed)

        return self._analyze_queries(parsed_queries)

    def analyze_log_file(self, file_path: str,
                         since: Optional[Union[str, datetime]] = None,
                         until: Optional[datetime] = None,
                         min_time: float = 0.0) -> SlowQueryReport:
        """
        分析慢查询日志文件

        参数:
            file_path: 日志文件路径
            since: 起始时间（字符串如'24h'或datetime对象）
            until: 结束时间
            min_time: 最小执行时间（秒）

        返回:
            SlowQueryReport: 分析报告
        """
        logger.info(f"开始分析慢查询日志: {file_path}")

        # 解析时间范围
        since_dt = self._parse_since(since)

        # 解析日志文件
        queries = []
        for query in self.log_parser.parse_file(file_path, since_dt, until):
            if query.query_time >= min_time:
                queries.append(query)

        if not queries:
            return SlowQueryReport(
                recommendations=[f"未在日志中找到符合条件的慢查询\n"
                               f"文件: {file_path}\n"
                               f"时间范围: {since_dt} ~ {until}"]
            )

        return self._analyze_queries(queries)

    def _parse_since(self, since: Optional[Union[str, datetime]]) -> Optional[datetime]:
        """解析since参数"""
        if since is None:
            return None

        if isinstance(since, datetime):
            return since

        if isinstance(since, str):
            # 支持相对时间格式：1h, 24h, 7d
            if since.endswith('h'):
                hours = int(since[:-1])
                return datetime.now() - timedelta(hours=hours)
            elif since.endswith('d'):
                days = int(since[:-1])
                return datetime.now() - timedelta(days=days)
            else:
                # 尝试解析ISO格式
                try:
                    return datetime.fromisoformat(since)
                except ValueError:
                    logger.warning(f"无法解析时间格式: {since}")
                    return None

        return None

    def _analyze_queries(self, queries: List[ParsedSlowQuery]) -> SlowQueryReport:
        """
        分析查询列表

        参数:
            queries: 解析后的查询列表

        返回:
            SlowQueryReport: 分析报告
        """
        # 按指纹分组
        pattern_groups: Dict[str, List[ParsedSlowQuery]] = defaultdict(list)

        for query in queries:
            # 生成指纹
            fp_result = self.fingerprinter.fingerprint(query.sql)
            fingerprint = fp_result.fingerprint

            # 添加指纹到查询
            query.fingerprint = fingerprint
            pattern_groups[fingerprint].append(query)

        # 计算统计信息
        patterns = []
        all_times = []
        hourly_dist = defaultdict(int)

        for fingerprint, group in pattern_groups.items():
            stats = self._calculate_pattern_stats(fingerprint, group)
            patterns.append(stats)

            # 收集所有时间用于全局统计
            for q in group:
                all_times.append(q.query_time)
                if q.timestamp:
                    hourly_dist[q.timestamp.hour] += 1

        # 生成报告
        report = SlowQueryReport(
            total_queries=len(queries),
            unique_patterns=len(patterns),
            total_time=sum(all_times),
            avg_time=statistics.mean(all_times) if all_times else 0.0,
            time_range=self._get_time_range(queries),
            top_patterns=sorted(patterns, key=lambda x: x.total_time, reverse=True)[:10],
            patterns_by_count=sorted(patterns, key=lambda x: x.count, reverse=True)[:10],
            patterns_by_avg_time=sorted(patterns, key=lambda x: x.avg_time, reverse=True)[:10],
            hourly_distribution=dict(hourly_dist),
            recommendations=self._generate_recommendations(patterns)
        )

        return report

    def _calculate_pattern_stats(self, fingerprint: str,
                                  queries: List[ParsedSlowQuery]) -> QueryPatternStats:
        """计算查询模式的统计信息"""
        times = [q.query_time for q in queries]
        rows_examined = [q.rows_examined for q in queries]

        # 计算分位数
        p95 = self._percentile(times, 95) if len(times) >= 20 else max(times)
        p99 = self._percentile(times, 99) if len(times) >= 100 else max(times)

        # 时间分布
        time_dist = defaultdict(int)
        for q in queries:
            if q.timestamp:
                time_dist[q.timestamp.hour] += 1

        # 获取SQL示例
        sql_example = queries[0].sql[:200] if queries else ''

        return QueryPatternStats(
            fingerprint=fingerprint,
            sql_pattern=sql_example,
            count=len(queries),
            total_time=sum(times),
            avg_time=statistics.mean(times),
            min_time=min(times),
            max_time=max(times),
            p95_time=p95,
            p99_time=p99,
            std_dev=statistics.stdev(times) if len(times) > 1 else 0.0,
            total_rows_examined=sum(rows_examined),
            avg_rows_examined=statistics.mean(rows_examined) if rows_examined else 0.0,
            total_rows_sent=sum(q.rows_sent for q in queries),
            first_seen=min((q.timestamp for q in queries if q.timestamp), default=None),
            last_seen=max((q.timestamp for q in queries if q.timestamp), default=None),
            time_distribution=dict(time_dist)
        )

    def _percentile(self, data: List[float], percentile: int) -> float:
        """计算百分位数"""
        sorted_data = sorted(data)
        index = int(len(sorted_data) * percentile / 100)
        return sorted_data[min(index, len(sorted_data) - 1)]

    def _get_time_range(self, queries: List[ParsedSlowQuery]) -> tuple:
        """获取时间范围"""
        timestamps = [q.timestamp for q in queries if q.timestamp]
        if not timestamps:
            return (None, None)
        return (min(timestamps), max(timestamps))

    def _generate_recommendations(self, patterns: List[QueryPatternStats]) -> List[str]:
        """生成优化建议"""
        recommendations = []

        if not patterns:
            return recommendations

        # 按总时间排序
        top_by_time = sorted(patterns, key=lambda x: x.total_time, reverse=True)[:3]

        # 检查全表扫描
        full_scan_patterns = [p for p in patterns
                             if p.avg_rows_examined > 10000 and p.avg_rows_sent < 100]
        if full_scan_patterns:
            recommendations.append(
                f"发现{len(full_scan_patterns)}个疑似全表扫描的查询模式，"
                f"建议检查索引: {full_scan_patterns[0].sql_pattern[:80]}..."
            )

        # 检查高频查询
        high_freq = [p for p in patterns if p.count > 100]
        if high_freq:
            recommendations.append(
                f"发现{len(high_freq)}个高频查询模式，"
                f"建议优化: {high_freq[0].sql_pattern[:80]}..."
            )

        # 检查慢查询
        slow_patterns = [p for p in patterns if p.avg_time > 10]
        if slow_patterns:
            recommendations.append(
                f"发现{len(slow_patterns)}个平均耗时超过10秒的查询，"
                f"建议优先优化: {slow_patterns[0].sql_pattern[:80]}..."
            )

        return recommendations
