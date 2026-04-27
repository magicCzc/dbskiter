"""
MySQL诊断器

提供MySQL数据库的专项诊断能力
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from dbskiter.shared.unified_connector import UnifiedConnector
from dbskiter.shared.mysql_slow_query_collector import MySQLSlowQueryCollector
from dbskiter.shared.mysql_aas_calculator_v2 import MySQLAASCalculatorV2 as MySQLAASCalculator
from dbskiter.shared.sql_fingerprint import SQLFingerprinter
from .base import BaseDiagnostician

logger = logging.getLogger(__name__)


class MySQLDiagnostician(BaseDiagnostician):
    """
    MySQL数据库诊断器

    提供MySQL特有的慢查询分析、AAS分析、统计信息获取
    """

    def __init__(self, connector: UnifiedConnector):
        super().__init__(connector)
        self.slow_query_collector = MySQLSlowQueryCollector(connector)
        self.aas_calculator = MySQLAASCalculator(connector)
        self.fingerprinter = SQLFingerprinter()
        self._database_name = None

    def _get_database_name(self) -> Optional[str]:
        """获取当前数据库名称"""
        if self._database_name is None:
            try:
                result = self.connector.execute("SELECT DATABASE()")
                if result and result.rows:
                    self._database_name = result.rows[0][0]
            except Exception as e:
                logger.warning(f"获取数据库名称失败: {e}")
        return self._database_name

    def analyze_slow_queries(
        self,
        limit: int = 20,
        min_time: float = 1.0
    ) -> Dict[str, Any]:
        """
        分析MySQL慢查询

        参数:
            limit: 返回条数限制
            min_time: 最小执行时间（秒）

        返回:
            Dict: 慢查询分析结果
        """
        try:
            # 获取当前数据库名称
            database = self._get_database_name()

            # 采集慢查询（只采集当前数据库的）
            slow_queries = self.slow_query_collector.collect_slow_queries(
                limit=limit,
                min_time=min_time,
                database=database
            )

            if not slow_queries:
                return self._create_result(
                    success=True,
                    message="未采集到慢查询",
                    data={
                        "total_queries": 0,
                        "unique_patterns": 0,
                        "queries": []
                    }
                )

            # SQL指纹聚合
            fingerprints = {}
            for query in slow_queries:
                # SlowQuery 使用 sql 属性，不是 sql_text
                sql_text = getattr(query, 'sql', None) or getattr(query, 'sql_text', '')
                fp_result = self.fingerprinter.fingerprint(sql_text)
                # 使用指纹字符串作为key
                fp = fp_result.fingerprint if hasattr(fp_result, 'fingerprint') else str(fp_result)
                if fp not in fingerprints:
                    fingerprints[fp] = {
                        "fingerprint": fp,
                        "sql_pattern": sql_text[:200] if sql_text else '',
                        "count": 0,
                        "total_time": 0.0,
                        "avg_time": 0.0,
                        "max_time": 0.0
                    }
                fingerprints[fp]["count"] += 1
                fingerprints[fp]["total_time"] += query.query_time
                fingerprints[fp]["max_time"] = max(fingerprints[fp]["max_time"], query.query_time)

            # 计算平均时间
            for fp in fingerprints:
                if fingerprints[fp]["count"] > 0:
                    fingerprints[fp]["avg_time"] = (
                        fingerprints[fp]["total_time"] / fingerprints[fp]["count"]
                    )

            # 排序
            sorted_patterns = sorted(
                fingerprints.values(),
                key=lambda x: x["total_time"],
                reverse=True
            )

            return self._create_result(
                success=True,
                message=f"成功分析 {len(slow_queries)} 个慢查询",
                data={
                    "total_queries": len(slow_queries),
                    "unique_patterns": len(fingerprints),
                    "queries": [
                        {
                            "sql": (getattr(q, 'sql', None) or getattr(q, 'sql_text', ''))[:500],
                            "query_time": q.query_time,
                            "lock_time": getattr(q, 'lock_time', 0.0),
                            "rows_examined": q.rows_examined,
                            "rows_sent": q.rows_sent,
                            "timestamp": getattr(q, 'timestamp', None).isoformat() if getattr(q, 'timestamp', None) else None
                        }
                        for q in slow_queries[:limit]
                    ],
                    "patterns": sorted_patterns[:10]
                }
            )

        except ConnectionError as e:
            logger.error(f"数据库连接失败: {e}")
            return self._create_result(
                success=False,
                message="数据库连接失败",
                error=str(e)
            )
        except PermissionError as e:
            logger.error(f"权限不足: {e}")
            return self._create_result(
                success=False,
                message="权限不足",
                error=str(e)
            )
        except ValueError as e:
            logger.error(f"数据解析错误: {e}")
            return self._create_result(
                success=False,
                message="数据解析错误",
                error=str(e)
            )

    def analyze_performance_metrics(
        self,
        duration_minutes: int = 10
    ) -> Dict[str, Any]:
        """
        分析MySQL性能指标（AAS）

        参数:
            duration_minutes: 采集时长（分钟）

        返回:
            Dict: AAS分析结果
        """
        try:
            import time

            # 采集AAS指标
            samples = []
            interval_seconds = 10
            total_samples = (duration_minutes * 60) // interval_seconds

            for i in range(total_samples):
                current = self.aas_calculator.calculate_current_aas()
                samples.append(current)
                if i < total_samples - 1:
                    time.sleep(interval_seconds)

            if not samples:
                return self._create_result(
                    success=False,
                    message="未采集到AAS数据",
                    error="采样失败"
                )

            # 计算统计值
            avg_aas = sum(s.total for s in samples) / len(samples)
            max_aas = max(s.total for s in samples)
            avg_cpu = sum(s.cpu for s in samples) / len(samples)
            avg_io = sum(s.io for s in samples) / len(samples)
            avg_lock = sum(s.lock for s in samples) / len(samples)

            # 识别瓶颈
            bottleneck = self.aas_calculator.identify_bottleneck()

            return self._create_result(
                success=True,
                message=f"成功采集 {len(samples)} 个AAS样本",
                data={
                    "aas_average": round(avg_aas, 2),
                    "aas_max": round(max_aas, 2),
                    "cpu_average": round(avg_cpu, 2),
                    "io_average": round(avg_io, 2),
                    "lock_average": round(avg_lock, 2),
                    "bottleneck": bottleneck,
                    "sample_count": len(samples),
                    "duration_minutes": duration_minutes
                }
            )

        except ConnectionError as e:
            logger.error(f"数据库连接失败: {e}")
            return self._create_result(
                success=False,
                message="数据库连接失败",
                error=str(e)
            )
        except PermissionError as e:
            logger.error(f"权限不足: {e}")
            return self._create_result(
                success=False,
                message="权限不足",
                error=str(e)
            )
        except TimeoutError as e:
            logger.error(f"采集超时: {e}")
            return self._create_result(
                success=False,
                message="采集超时",
                error=str(e)
            )

    def get_database_stats(self) -> Dict[str, Any]:
        """
        获取MySQL数据库统计信息

        返回:
            Dict: 数据库统计信息
        """
        try:
            stats = {
                "database_type": "MySQL",
                "timestamp": datetime.now().isoformat()
            }

            # 获取版本
            result = self._execute_query("SELECT VERSION()")
            if result:
                stats["version"] = result[0][0]

            # 获取连接数
            result = self._execute_query(
                "SELECT COUNT(*) FROM information_schema.processlist"
            )
            if result:
                stats["current_connections"] = result[0][0]

            # 获取最大连接数
            result = self._execute_query(
                "SHOW VARIABLES LIKE 'max_connections'"
            )
            if result:
                stats["max_connections"] = int(result[0][1])

            # 获取数据库大小
            result = self._execute_query("""
                SELECT ROUND(SUM(data_length + index_length) / 1024 / 1024 / 1024, 2)
                FROM information_schema.tables
                WHERE table_schema NOT IN ('information_schema', 'performance_schema', 'mysql', 'sys')
            """)
            if result:
                stats["total_size_gb"] = result[0][0] or 0

            # 获取表数量
            result = self._execute_query("""
                SELECT COUNT(*) FROM information_schema.tables
                WHERE table_schema NOT IN ('information_schema', 'performance_schema', 'mysql', 'sys')
            """)
            if result:
                stats["table_count"] = result[0][0]

            # 获取QPS（Questions / Uptime）
            # 使用 WHERE IN 代替子查询（兼容性更好）
            result = self._execute_query("""
                SELECT VARIABLE_NAME, VARIABLE_VALUE
                FROM performance_schema.global_status
                WHERE VARIABLE_NAME IN ('Questions', 'Uptime')
            """)

            # 转换为字典
            status_dict = {row[0]: row[1] for row in result} if result else {}
            questions = int(status_dict.get('Questions', 0) or 0)
            uptime = int(status_dict.get('Uptime', 0) or 0)

            if uptime > 0:
                qps = questions / uptime
                stats["qps"] = round(qps, 2)

            return self._create_result(
                success=True,
                message="成功获取数据库统计信息",
                data=stats
            )

        except ConnectionError as e:
            logger.error(f"数据库连接失败: {e}")
            return self._create_result(
                success=False,
                message="数据库连接失败",
                error=str(e)
            )
        except PermissionError as e:
            logger.error(f"权限不足: {e}")
            return self._create_result(
                success=False,
                message="权限不足",
                error=str(e)
            )
        except ValueError as e:
            logger.error(f"数据解析错误: {e}")
            return self._create_result(
                success=False,
                message="数据解析错误",
                error=str(e)
            )
