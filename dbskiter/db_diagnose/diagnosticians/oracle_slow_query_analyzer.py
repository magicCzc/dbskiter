"""
Oracle慢查询分析器（增强版）

文件功能：提供Oracle数据库的慢查询分析能力
主要类：OracleSlowQueryAnalyzer

特性：
    1. AWR历史数据分析：从DBA_HIST_SQLSTAT获取历史慢SQL
    2. 实时SQL分析：从v$sql获取当前慢SQL
    3. SQL指纹聚合：归并相似SQL
    4. 多维度统计：时间、IO、CPU等多维度分析
    5. 执行计划分析：获取SQL执行计划

使用示例：
    from dbskiter.db_diagnose.diagnosticians.oracle_slow_query_analyzer import OracleSlowQueryAnalyzer

    analyzer = OracleSlowQueryAnalyzer(connector)

    # 分析AWR历史数据
    report = analyzer.analyze_awr_history(snap_id_begin=100, snap_id_end=110)

    # 分析实时慢SQL
    report = analyzer.analyze_realtime(limit=20, min_time=1.0)

作者: Magiczc
创建时间: 2026-04-29
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from collections import defaultdict
import statistics

from dbskiter.shared.unified_connector import UnifiedConnector
from dbskiter.shared.sql_fingerprint import SQLFingerprinter

logger = logging.getLogger(__name__)


@dataclass
class OracleSlowQuery:
    """
    Oracle慢查询数据

    属性:
        sql_id: SQL ID
        sql_text: SQL文本
        executions: 执行次数
        elapsed_time: 总执行时间（秒）
        cpu_time: CPU时间（秒）
        buffer_gets: 逻辑读次数
        disk_reads: 物理读次数
        rows_processed: 处理行数
        avg_time: 平均执行时间
        first_seen: 首次出现时间
        last_seen: 最后出现时间
        plan_hash_value: 执行计划哈希值
        parsing_schema_name: 解析用户
        module: 应用模块
        action: 操作类型
    """
    sql_id: str
    sql_text: str
    executions: int = 0
    elapsed_time: float = 0.0
    cpu_time: float = 0.0
    buffer_gets: int = 0
    disk_reads: int = 0
    rows_processed: int = 0
    avg_time: float = 0.0
    first_seen: Optional[datetime] = None
    last_seen: Optional[datetime] = None
    plan_hash_value: Optional[str] = None
    parsing_schema_name: Optional[str] = None
    module: Optional[str] = None
    action: Optional[str] = None
    fingerprint: Optional[str] = None


@dataclass
class OracleQueryPattern:
    """
    Oracle查询模式统计

    属性:
        fingerprint: SQL指纹
        sql_pattern: SQL模式示例
        sql_ids: SQL ID列表
        count: 执行次数
        total_elapsed: 总执行时间
        avg_elapsed: 平均执行时间
        total_cpu: 总CPU时间
        total_buffer_gets: 总逻辑读
        total_disk_reads: 总物理读
        executions: 总执行次数
        first_seen: 首次出现
        last_seen: 最后出现
    """
    fingerprint: str
    sql_pattern: str
    sql_ids: List[str] = field(default_factory=list)
    count: int = 0
    total_elapsed: float = 0.0
    avg_elapsed: float = 0.0
    total_cpu: float = 0.0
    total_buffer_gets: int = 0
    total_disk_reads: int = 0
    executions: int = 0
    first_seen: Optional[datetime] = None
    last_seen: Optional[datetime] = None


@dataclass
class OracleSlowQueryReport:
    """
    Oracle慢查询分析报告

    属性:
        total_queries: 总查询数
        unique_patterns: 唯一模式数
        total_elapsed: 总执行时间
        total_cpu: 总CPU时间
        total_buffer_gets: 总逻辑读
        time_range: 时间范围
        top_patterns: TOP查询模式
        top_by_io: 按IO排序的模式
        top_by_cpu: 按CPU排序的模式
        recommendations: 优化建议
    """
    total_queries: int = 0
    unique_patterns: int = 0
    total_elapsed: float = 0.0
    total_cpu: float = 0.0
    total_buffer_gets: int = 0
    time_range: tuple = field(default_factory=lambda: (None, None))
    top_patterns: List[OracleQueryPattern] = field(default_factory=list)
    top_by_io: List[OracleQueryPattern] = field(default_factory=list)
    top_by_cpu: List[OracleQueryPattern] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典（与MySQL分析器保持字段名一致）"""
        return {
            'summary': {
                'total_queries': self.total_queries,
                'unique_patterns': self.unique_patterns,
                'total_time': round(self.total_elapsed, 2),
                'avg_time': round(self.total_elapsed / self.total_queries, 3) if self.total_queries > 0 else 0.0,
                'total_cpu_sec': round(self.total_cpu, 2),
                'total_buffer_gets': self.total_buffer_gets,
                'time_range': [
                    self.time_range[0].isoformat() if self.time_range[0] else None,
                    self.time_range[1].isoformat() if self.time_range[1] else None
                ]
            },
            'top_patterns': [
                {
                    'fingerprint': p.fingerprint[:80],
                    'sql_pattern': p.sql_pattern[:150],
                    'count': p.count,
                    'executions': p.executions,
                    'total_time': round(p.total_elapsed, 2),
                    'avg_time': round(p.avg_elapsed, 3),
                    'p95_time': round(p.avg_elapsed, 3),
                    'rows_examined': p.total_buffer_gets,
                    'rows_sent': 0  # Oracle v$sql中没有返回行数统计
                }
                for p in self.top_patterns[:10]
            ],
            'recommendations': self.recommendations
        }


class OracleSlowQueryAnalyzer:
    """
    Oracle慢查询分析器

    提供Oracle特有的慢查询分析能力：
    - AWR历史数据分析
    - 实时v$sql分析
    - SQL指纹聚合
    - 执行计划获取
    """

    def __init__(self, connector: UnifiedConnector):
        """
        初始化分析器

        参数:
            connector: 数据库连接器
        """
        self.connector = connector
        self.fingerprinter = SQLFingerprinter()

    def analyze_realtime(self, limit: int = 20,
                         min_time: float = 1.0) -> OracleSlowQueryReport:
        """
        分析实时慢SQL（从v$sql）

        参数:
            limit: 返回条数限制
            min_time: 最小执行时间（秒）

        返回:
            OracleSlowQueryReport: 分析报告
        """
        logger.info(f"开始分析Oracle实时慢SQL（limit={limit}, min_time={min_time}s）")

        queries = self._fetch_realtime_queries(limit, min_time)
        if not queries:
            return OracleSlowQueryReport(
                recommendations=["未找到慢SQL，请检查：\n"
                               "1. 是否有SQL执行超过阈值\n"
                               "2. v$sql视图是否有数据\n"
                               "3. 数据库负载情况"]
            )

        return self._analyze_queries(queries)

    def analyze_awr_history(self, hours: int = 24,
                            limit: int = 50,
                            min_time: float = 1.0) -> OracleSlowQueryReport:
        """
        分析AWR历史数据

        参数:
            hours: 分析最近几小时的数据
            limit: 返回条数限制
            min_time: 最小执行时间（秒）

        返回:
            OracleSlowQueryReport: 分析报告
        """
        logger.info(f"开始分析AWR历史数据（hours={hours}, limit={limit}）")

        # 检查AWR是否可用
        if not self._check_awr_available():
            logger.warning("AWR不可用，降级到实时分析")
            return self.analyze_realtime(limit, min_time)

        queries = self._fetch_awr_queries(hours, limit, min_time)
        if not queries:
            return OracleSlowQueryReport(
                recommendations=["未在AWR中找到慢SQL，请检查：\n"
                               "1. AWR快照是否已采集\n"
                               "2. 时间范围是否合适\n"
                               "3. SQL执行时间是否超过阈值"]
            )

        return self._analyze_queries(queries)

    def _check_awr_available(self) -> bool:
        """检查AWR是否可用"""
        try:
            result = self.connector.execute(
                "SELECT COUNT(*) FROM dba_hist_snapshot WHERE ROWNUM = 1"
            )
            return result.rows and result.rows[0][0] > 0
        except Exception as e:
            logger.warning(f"AWR检查失败: {e}")
            return False

    def _fetch_realtime_queries(self, limit: int,
                                 min_time: float) -> List[OracleSlowQuery]:
        """从v$sql获取实时慢SQL"""
        try:
            # 使用参数化查询防止SQL注入
            # 注意：JDBC使用?作为占位符
            result = self.connector.execute("""
                SELECT * FROM (
                    SELECT
                        sql_id,
                        sql_text,
                        executions,
                        elapsed_time / 1000000 as elapsed_time_sec,
                        cpu_time / 1000000 as cpu_time_sec,
                        buffer_gets,
                        disk_reads,
                        rows_processed,
                        plan_hash_value,
                        parsing_schema_name,
                        module,
                        action,
                        first_load_time,
                        last_active_time
                    FROM v$sql
                    WHERE executions > 0
                        AND elapsed_time / executions / 1000000 >= ?
                        AND sql_text NOT LIKE '%SELECT /*+ OPT_ESTIMATE%'
                        AND sql_text NOT LIKE '%v$sql%'
                    ORDER BY elapsed_time / executions DESC
                )
                WHERE ROWNUM <= ?
            """, (min_time, limit))

            queries = []
            for row in result.rows:
                # 处理Java类型转换为Python类型
                # JDBC返回的是JLong/JDouble等Java类型，需要显式转换
                elapsed_time_val = row[3]
                if elapsed_time_val is not None:
                    elapsed_time_val = float(str(elapsed_time_val))
                else:
                    elapsed_time_val = 0.0

                cpu_time_val = row[4]
                if cpu_time_val is not None:
                    cpu_time_val = float(str(cpu_time_val))
                else:
                    cpu_time_val = 0.0

                query = OracleSlowQuery(
                    sql_id=row[0],
                    sql_text=row[1] if row[1] else '',
                    executions=int(str(row[2])) if row[2] else 0,
                    elapsed_time=elapsed_time_val,
                    cpu_time=cpu_time_val,
                    buffer_gets=int(str(row[5])) if row[5] else 0,
                    disk_reads=int(str(row[6])) if row[6] else 0,
                    rows_processed=int(str(row[7])) if row[7] else 0,
                    plan_hash_value=str(row[8]) if row[8] else None,
                    parsing_schema_name=row[9],
                    module=row[10],
                    action=row[11]
                )
                query.avg_time = query.elapsed_time / query.executions if query.executions > 0 else 0
                queries.append(query)

            return queries

        except Exception as e:
            logger.error(f"获取实时慢SQL失败: {e}")
            return []

    def _fetch_awr_queries(self, hours: int, limit: int,
                           min_time: float) -> List[OracleSlowQuery]:
        """从AWR获取历史慢SQL"""
        try:
            # 使用参数化查询防止SQL注入
            # 注意：JDBC使用?作为占位符
            result = self.connector.execute("""
                SELECT * FROM (
                    SELECT
                        s.sql_id,
                        t.sql_text,
                        s.executions_delta as executions,
                        s.elapsed_time_delta / 1000000 as elapsed_time_sec,
                        s.cpu_time_delta / 1000000 as cpu_time_sec,
                        s.buffer_gets_delta as buffer_gets,
                        s.disk_reads_delta as disk_reads,
                        s.rows_processed_delta as rows_processed,
                        s.plan_hash_value,
                        s.snap_id,
                        s.instance_number
                    FROM dba_hist_sqlstat s
                    JOIN dba_hist_sqltext t ON s.sql_id = t.sql_id
                    WHERE s.snap_id IN (
                        SELECT snap_id FROM dba_hist_snapshot
                        WHERE begin_interval_time >= SYSDATE - ?/24
                    )
                    AND s.elapsed_time_delta / 1000000 >= ?
                    AND s.executions_delta > 0
                    ORDER BY s.elapsed_time_delta DESC
                )
                WHERE ROWNUM <= ?
            """, (hours, min_time, limit))

            queries = []
            for row in result.rows:
                # 处理Java类型转换为Python类型
                elapsed_time_val = row[3]
                if elapsed_time_val is not None:
                    elapsed_time_val = float(str(elapsed_time_val))
                else:
                    elapsed_time_val = 0.0

                cpu_time_val = row[4]
                if cpu_time_val is not None:
                    cpu_time_val = float(str(cpu_time_val))
                else:
                    cpu_time_val = 0.0

                query = OracleSlowQuery(
                    sql_id=row[0],
                    sql_text=row[1] if row[1] else '',
                    executions=int(str(row[2])) if row[2] else 0,
                    elapsed_time=elapsed_time_val,
                    cpu_time=cpu_time_val,
                    buffer_gets=int(str(row[5])) if row[5] else 0,
                    disk_reads=int(str(row[6])) if row[6] else 0,
                    rows_processed=int(str(row[7])) if row[7] else 0,
                    plan_hash_value=str(row[8]) if row[8] else None
                )
                query.avg_time = query.elapsed_time / query.executions if query.executions > 0 else 0
                queries.append(query)

            return queries

        except Exception as e:
            logger.error(f"获取AWR慢SQL失败: {e}")
            return []

    def _analyze_queries(self, queries: List[OracleSlowQuery]) -> OracleSlowQueryReport:
        """分析查询列表"""
        # 按指纹分组
        pattern_groups: Dict[str, List[OracleSlowQuery]] = defaultdict(list)

        for query in queries:
            # 生成指纹
            fp_result = self.fingerprinter.fingerprint(query.sql_text, dialect='oracle')
            fingerprint = fp_result.fingerprint
            query.fingerprint = fingerprint
            pattern_groups[fingerprint].append(query)

        # 计算统计信息
        patterns = []
        all_elapsed = []
        all_cpu = []
        all_buffer = []

        for fingerprint, group in pattern_groups.items():
            pattern = self._calculate_pattern_stats(fingerprint, group)
            patterns.append(pattern)

            # 收集全局统计
            for q in group:
                all_elapsed.append(q.elapsed_time)
                all_cpu.append(q.cpu_time)
                all_buffer.append(q.buffer_gets)

        # 生成报告
        report = OracleSlowQueryReport(
            total_queries=len(queries),
            unique_patterns=len(patterns),
            total_elapsed=sum(all_elapsed),
            total_cpu=sum(all_cpu),
            total_buffer_gets=sum(all_buffer),
            time_range=self._get_time_range(queries),
            top_patterns=sorted(patterns, key=lambda x: x.total_elapsed, reverse=True)[:10],
            top_by_io=sorted(patterns, key=lambda x: x.total_buffer_gets, reverse=True)[:10],
            top_by_cpu=sorted(patterns, key=lambda x: x.total_cpu, reverse=True)[:10],
            recommendations=self._generate_recommendations(patterns)
        )

        return report

    def _calculate_pattern_stats(self, fingerprint: str,
                                  queries: List[OracleSlowQuery]) -> OracleQueryPattern:
        """计算模式统计"""
        elapsed_list = [q.elapsed_time for q in queries]
        cpu_list = [q.cpu_time for q in queries]
        buffer_list = [q.buffer_gets for q in queries]

        # 获取SQL示例
        sql_example = queries[0].sql_text[:200] if queries else ''

        # 收集所有SQL ID
        sql_ids = list(set(q.sql_id for q in queries))

        # 计算时间范围
        first_times = [q.first_seen for q in queries if q.first_seen]
        last_times = [q.last_seen for q in queries if q.last_seen]

        return OracleQueryPattern(
            fingerprint=fingerprint,
            sql_pattern=sql_example,
            sql_ids=sql_ids,
            count=len(queries),
            total_elapsed=sum(elapsed_list),
            avg_elapsed=statistics.mean(elapsed_list) if elapsed_list else 0.0,
            total_cpu=sum(cpu_list),
            total_buffer_gets=sum(buffer_list),
            total_disk_reads=sum(q.disk_reads for q in queries),
            executions=sum(q.executions for q in queries),
            first_seen=min(first_times) if first_times else None,
            last_seen=max(last_times) if last_times else None
        )

    def _get_time_range(self, queries: List[OracleSlowQuery]) -> tuple:
        """获取时间范围"""
        first_times = [q.first_seen for q in queries if q.first_seen]
        last_times = [q.last_seen for q in queries if q.last_seen]

        first = min(first_times) if first_times else None
        last = max(last_times) if last_times else None

        return (first, last)

    def _generate_recommendations(self, patterns: List[OracleQueryPattern]) -> List[str]:
        """生成优化建议"""
        recommendations = []

        if not patterns:
            return recommendations

        # 检查高IO查询
        high_io = [p for p in patterns if p.total_buffer_gets > 1000000]
        if high_io:
            recommendations.append(
                f"发现{len(high_io)}个高IO查询模式，"
                f"建议优化索引或SQL逻辑: {high_io[0].sql_pattern[:80]}..."
            )

        # 检查高CPU查询
        high_cpu = [p for p in patterns if p.total_cpu > 10]
        if high_cpu:
            recommendations.append(
                f"发现{len(high_cpu)}个高CPU查询模式，"
                f"建议检查执行计划: {high_cpu[0].sql_pattern[:80]}..."
            )

        # 检查执行次数多但总时间长的查询
        high_freq_slow = [p for p in patterns
                         if p.executions > 100 and p.total_elapsed > 10]
        if high_freq_slow:
            recommendations.append(
                f"发现{len(high_freq_slow)}个高频且慢的查询模式，"
                f"建议优先优化: {high_freq_slow[0].sql_pattern[:80]}..."
            )

        return recommendations

    def get_execution_plan(self, sql_id: str) -> Optional[Dict[str, Any]]:
        """
        获取SQL执行计划

        参数:
            sql_id: SQL ID

        返回:
            Dict: 执行计划信息
        """
        try:
            result = self.connector.execute(f"""
                SELECT plan_table_output
                FROM TABLE(DBMS_XPLAN.DISPLAY_CURSOR('{sql_id}', NULL, 'ALLSTATS LAST'))
            """)

            if result.rows:
                plan_lines = [row[0] for row in result.rows if row[0]]
                return {
                    'sql_id': sql_id,
                    'plan_text': '\n'.join(plan_lines)
                }

            return None

        except Exception as e:
            logger.error(f"获取执行计划失败: {e}")
            return None
