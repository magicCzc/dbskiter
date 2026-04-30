"""
慢查询日志文件解析器

文件功能：解析MySQL/Oracle慢查询日志文件，支持多种格式
主要类：
    - SlowLogParser: 慢查询日志解析器基类
    - MySQLSlowLogParser: MySQL慢查询日志解析器
    - OracleSlowLogParser: Oracle慢查询日志解析器
    - QueryAggregator: 查询聚合分析器

设计原则：
    1. 流式解析：支持大文件，内存友好
    2. 多格式支持：支持不同版本的日志格式
    3. 高性能：使用生成器，避免一次性加载
    4. 容错性：遇到格式错误继续解析

使用示例：
    from dbskiter.shared.slow_log_parser import MySQLSlowLogParser

    parser = MySQLSlowLogParser()
    for query in parser.parse_file('/var/log/mysql/slow.log'):
        print(f"SQL: {query.sql[:100]}")
        print(f"Time: {query.query_time}s")

作者: AI Assistant
创建时间: 2026-04-29
"""

import re
import gzip
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Iterator, Optional, List, Dict, Any, Tuple
from collections import defaultdict
import statistics

logger = logging.getLogger(__name__)


@dataclass
class ParsedSlowQuery:
    """
    解析后的慢查询条目

    属性:
        sql: SQL语句文本
        query_time: 查询执行时间（秒）
        lock_time: 锁等待时间（秒）
        rows_sent: 返回行数
        rows_examined: 扫描行数
        timestamp: 执行时间戳
        user: 执行用户
        host: 执行主机
        db: 数据库名
        fingerprint: SQL指纹（归一化后）
        query_id: 查询ID（如果存在）
    """
    sql: str
    query_time: float = 0.0
    lock_time: float = 0.0
    rows_sent: int = 0
    rows_examined: int = 0
    timestamp: Optional[datetime] = None
    user: Optional[str] = None
    host: Optional[str] = None
    db: Optional[str] = None
    fingerprint: Optional[str] = None
    query_id: Optional[str] = None


@dataclass
class QueryPattern:
    """
    查询模式（聚合结果）

    属性:
        fingerprint: SQL指纹
        sql_pattern: SQL模式示例
        count: 执行次数
        total_time: 总执行时间
        avg_time: 平均执行时间
        min_time: 最小执行时间
        max_time: 最大执行时间
        p95_time: 95分位执行时间
        total_rows_examined: 总扫描行数
        total_rows_sent: 总返回行数
        first_seen: 首次出现时间
        last_seen: 最后出现时间
    """
    fingerprint: str
    sql_pattern: str
    count: int = 0
    total_time: float = 0.0
    avg_time: float = 0.0
    min_time: float = float('inf')
    max_time: float = 0.0
    p95_time: float = 0.0
    total_rows_examined: int = 0
    total_rows_sent: int = 0
    first_seen: Optional[datetime] = None
    last_seen: Optional[datetime] = None


class SlowLogParser(ABC):
    """
    慢查询日志解析器基类

    提供通用的日志解析框架，具体实现由子类完成
    """

    def __init__(self, encoding: str = 'utf-8', errors: str = 'replace'):
        """
        初始化解析器

        参数:
            encoding: 文件编码
            errors: 解码错误处理方式
        """
        self.encoding = encoding
        self.errors = errors
        self._parsed_count = 0
        self._error_count = 0

    @abstractmethod
    def parse_file(self, file_path: str,
                   since: Optional[datetime] = None,
                   until: Optional[datetime] = None) -> Iterator[ParsedSlowQuery]:
        """
        解析日志文件

        参数:
            file_path: 日志文件路径
            since: 起始时间（可选）
            until: 结束时间（可选）

        返回:
            Iterator[ParsedSlowQuery]: 解析后的查询条目
        """
        pass

    def _open_file(self, file_path: str):
        """
        打开日志文件（支持gzip压缩）

        参数:
            file_path: 文件路径

        返回:
            文件对象
        """
        path = Path(file_path)

        if not path.exists():
            raise FileNotFoundError(f"日志文件不存在: {file_path}")

        if file_path.endswith('.gz'):
            return gzip.open(file_path, 'rt', encoding=self.encoding, errors=self.errors)
        else:
            return open(file_path, 'r', encoding=self.encoding, errors=self.errors)

    def get_stats(self) -> Dict[str, int]:
        """获取解析统计信息"""
        return {
            'parsed_count': self._parsed_count,
            'error_count': self._error_count
        }


class MySQLSlowLogParser(SlowLogParser):
    """
    MySQL慢查询日志解析器

    支持格式：
    - MySQL 5.6/5.7/8.0 标准慢查询日志格式
    - 支持Time、User@Host、Query_time等字段

    示例日志条目：
        # Time: 2026-04-29T10:00:00.000000Z
        # User@Host: root[root] @ localhost []
        # Query_time: 2.500000  Lock_time: 0.000100 Rows_sent: 1  Rows_examined: 100000
        SET timestamp=1714389600;
        SELECT * FROM users WHERE status = 'active';
    """

    # 正则表达式模式
    TIME_PATTERN = re.compile(
        r'# Time:\s*(\d{4}-\d{2}-\d{2}T?\s*\d{2}:\d{2}:\d{2}(?:\.\d+)?Z?)'
    )
    USER_HOST_PATTERN = re.compile(
        r'# User@Host:\s*(\S+)\[\S+\]\s+@\s+(\S+)\s*\[.*?\]'
    )
    QUERY_TIME_PATTERN = re.compile(
        r'# Query_time:\s*([\d.]+)\s+Lock_time:\s*([\d.]+)\s+'
        r'Rows_sent:\s*(\d+)\s+Rows_examined:\s*(\d+)'
    )
    TIMESTAMP_PATTERN = re.compile(r'SET timestamp=(\d+)')
    USE_DB_PATTERN = re.compile(r'use\s+(\w+)', re.IGNORECASE)

    def parse_file(self, file_path: str,
                   since: Optional[datetime] = None,
                   until: Optional[datetime] = None) -> Iterator[ParsedSlowQuery]:
        """
        解析MySQL慢查询日志文件

        参数:
            file_path: 日志文件路径
            since: 起始时间
            until: 结束时间

        返回:
            Iterator[ParsedSlowQuery]: 解析后的查询条目
        """
        with self._open_file(file_path) as f:
            yield from self._parse_lines(f, since, until)

    def _parse_lines(self, lines: Iterator[str],
                     since: Optional[datetime],
                     until: Optional[datetime]) -> Iterator[ParsedSlowQuery]:
        """
        逐行解析日志

        参数:
            lines: 行迭代器
            since: 起始时间
            until: 结束时间

        返回:
            Iterator[ParsedSlowQuery]: 解析后的查询条目
        """
        current_entry = {}
        sql_lines = []
        in_sql = False

        for line in lines:
            line = line.strip()

            if not line:
                continue

            # 解析时间
            time_match = self.TIME_PATTERN.match(line)
            if time_match:
                # 保存之前的条目
                if sql_lines and current_entry:
                    query = self._build_query(current_entry, sql_lines)
                    if query and self._filter_by_time(query, since, until):
                        yield query
                        self._parsed_count += 1

                # 开始新条目
                current_entry = {'time_str': time_match.group(1)}
                sql_lines = []
                in_sql = False
                continue

            # 解析User@Host
            user_match = self.USER_HOST_PATTERN.match(line)
            if user_match:
                current_entry['user'] = user_match.group(1)
                current_entry['host'] = user_match.group(2)
                continue

            # 解析Query_time等
            query_match = self.QUERY_TIME_PATTERN.match(line)
            if query_match:
                current_entry['query_time'] = float(query_match.group(1))
                current_entry['lock_time'] = float(query_match.group(2))
                current_entry['rows_sent'] = int(query_match.group(3))
                current_entry['rows_examined'] = int(query_match.group(4))
                continue

            # 解析SET timestamp
            ts_match = self.TIMESTAMP_PATTERN.match(line)
            if ts_match:
                current_entry['timestamp'] = int(ts_match.group(1))
                continue

            # 解析use database
            db_match = self.USE_DB_PATTERN.match(line)
            if db_match:
                current_entry['db'] = db_match.group(1)
                continue

            # SQL语句（不以#开头）
            if not line.startswith('#') and not line.startswith('/'):
                sql_lines.append(line)
                in_sql = True

        # 处理最后一个条目
        if sql_lines and current_entry:
            query = self._build_query(current_entry, sql_lines)
            if query and self._filter_by_time(query, since, until):
                yield query
                self._parsed_count += 1

    def _build_query(self, entry: Dict, sql_lines: List[str]) -> Optional[ParsedSlowQuery]:
        """
        构建ParsedSlowQuery对象

        参数:
            entry: 解析的字段
            sql_lines: SQL语句行

        返回:
            ParsedSlowQuery对象或None
        """
        try:
            sql = ' '.join(sql_lines).strip()
            if not sql or sql.startswith('SET timestamp='):
                return None

            # 解析时间戳
            timestamp = None
            if 'timestamp' in entry:
                timestamp = datetime.fromtimestamp(entry['timestamp'])
            elif 'time_str' in entry:
                timestamp = self._parse_time(entry['time_str'])

            return ParsedSlowQuery(
                sql=sql,
                query_time=entry.get('query_time', 0.0),
                lock_time=entry.get('lock_time', 0.0),
                rows_sent=entry.get('rows_sent', 0),
                rows_examined=entry.get('rows_examined', 0),
                timestamp=timestamp,
                user=entry.get('user'),
                host=entry.get('host'),
                db=entry.get('db')
            )
        except Exception as e:
            logger.debug(f"构建查询对象失败: {e}")
            self._error_count += 1
            return None

    def _parse_time(self, time_str: str) -> Optional[datetime]:
        """解析时间字符串"""
        formats = [
            '%Y-%m-%dT%H:%M:%S.%fZ',
            '%Y-%m-%d %H:%M:%S',
            '%y%m%d %H:%M:%S',
        ]
        for fmt in formats:
            try:
                return datetime.strptime(time_str, fmt)
            except ValueError:
                continue
        return None

    def _filter_by_time(self, query: ParsedSlowQuery,
                        since: Optional[datetime],
                        until: Optional[datetime]) -> bool:
        """按时间过滤"""
        if not query.timestamp:
            return True
        if since and query.timestamp < since:
            return False
        if until and query.timestamp > until:
            return False
        return True


class QueryAggregator:
    """
    查询聚合分析器

    对解析后的慢查询进行聚合分析，生成统计报告
    """

    def __init__(self):
        self.patterns: Dict[str, QueryPattern] = {}
        self.total_queries = 0
        self.total_time = 0.0

    def add_query(self, query: ParsedSlowQuery, fingerprint: str):
        """
        添加查询到聚合器

        参数:
            query: 解析后的查询
            fingerprint: SQL指纹
        """
        self.total_queries += 1
        self.total_time += query.query_time

        if fingerprint not in self.patterns:
            self.patterns[fingerprint] = QueryPattern(
                fingerprint=fingerprint,
                sql_pattern=query.sql[:200] if len(query.sql) > 200 else query.sql
            )

        pattern = self.patterns[fingerprint]
        pattern.count += 1
        pattern.total_time += query.query_time
        pattern.min_time = min(pattern.min_time, query.query_time)
        pattern.max_time = max(pattern.max_time, query.query_time)
        pattern.total_rows_examined += query.rows_examined
        pattern.total_rows_sent += query.rows_sent

        if query.timestamp:
            if not pattern.first_seen or query.timestamp < pattern.first_seen:
                pattern.first_seen = query.timestamp
            if not pattern.last_seen or query.timestamp > pattern.last_seen:
                pattern.last_seen = query.timestamp

    def calculate_stats(self):
        """计算统计信息"""
        for pattern in self.patterns.values():
            if pattern.count > 0:
                pattern.avg_time = pattern.total_time / pattern.count

    def get_top_patterns(self, n: int = 10,
                         sort_by: str = 'total_time') -> List[QueryPattern]:
        """
        获取TOP N查询模式

        参数:
            n: 返回条数
            sort_by: 排序字段（total_time/count/avg_time）

        返回:
            List[QueryPattern]: 排序后的查询模式列表
        """
        patterns = list(self.patterns.values())

        sort_key = {
            'total_time': lambda x: x.total_time,
            'count': lambda x: x.count,
            'avg_time': lambda x: x.avg_time,
        }.get(sort_by, lambda x: x.total_time)

        patterns.sort(key=sort_key, reverse=True)
        return patterns[:n]

    def get_summary(self) -> Dict[str, Any]:
        """获取汇总统计"""
        if not self.patterns:
            return {
                'total_queries': 0,
                'unique_patterns': 0,
                'total_time': 0.0,
                'avg_time': 0.0
            }

        return {
            'total_queries': self.total_queries,
            'unique_patterns': len(self.patterns),
            'total_time': self.total_time,
            'avg_time': self.total_time / self.total_queries if self.total_queries > 0 else 0.0
        }
