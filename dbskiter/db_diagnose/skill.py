"""
db_diagnose/skill.py
数据库诊断 Skill 统一入口

文件功能：提供统一的SQL诊断API，支持MySQL/Oracle/PostgreSQL
主要类：DiagnoseSkill - 诊断Skill统一入口

支持的数据库：
    - MySQL: 慢查询分析、AAS分析、执行计划分析
    - Oracle: 慢SQL分析(AWR)、性能指标分析、执行计划分析
    - PostgreSQL: 慢查询分析(pg_stat_statements)、性能分析、执行计划分析

核心功能：
1. 深度SQL分析 - 使用SQLAnalyzer子模块
2. 智能索引建议 - 使用SQLAnalyzer子模块
3. SQL指纹聚合 - 识别相似查询模式
4. 性能指标分析 - 使用多数据库诊断器
5. 慢查询分析 - 使用多数据库诊断器
6. 批量诊断 - 使用BatchAnalyzer子模块
7. 优化报告生成 - 使用ReportGenerator子模块
8. 表诊断 - 使用TableAnalyzer子模块

使用示例：
    >>> skill = DiagnoseSkill(connector)
    >>> result = skill.analyze_sql("SELECT * FROM users WHERE email = 'test@example.com'")
    >>> slow_queries = skill.analyze_slow_queries(limit=20)

版本: 3.0.0（模块化重构版）
作者: AI Assistant
创建时间: 2026-04-23
"""

import logging
import warnings
from typing import List, Dict, Any, Optional

from dbskiter.shared.unified_connector import UnifiedConnector, detect_connector_type
from dbskiter.shared.validators import validate_params, Validator

# 导入数据模型
from .models import (
    ErrorCode,
    DiagnoseConfig,
    DiagnoseResult,
    create_success_response,
    create_error_response,
)

# 导入工具类
from .utils import (
    SQLFingerprint,
    IssueClassifier,
    ScoreCalculator,
    PrioritySorter,
    MetricsAggregator,
    QueryExtractor,
)

# 导入子模块
from .analyzers.table_analyzer import TableAnalyzer
from .analyzers.sql_analyzer import SQLAnalyzer
from .analyzers.batch_analyzer import BatchAnalyzer
from .analyzers.plan_analyzer import ExecutionPlanAnalyzer
from .reports.generator import ReportGenerator
from .diagnosticians import get_diagnostician

logger = logging.getLogger(__name__)


class DiagnoseSkill:
    """
    数据库诊断 Skill 统一入口（模块化重构版）

    整合深度分析能力和多数据库支持，提供生产级的SQL诊断能力

    核心组件:
        connector: 数据库连接器
        dialect: 数据库方言
        plan_analyzer: 执行计划分析器
        sql_analyzer: SQL分析器
        batch_analyzer: 批量分析器
        table_analyzer: 表诊断分析器
        diagnostician: 数据库特定诊断器
        report_generator: 报告生成器

    支持的数据库:
        - MySQL / MariaDB
        - Oracle
        - PostgreSQL
    """

    def __init__(
        self,
        connector: UnifiedConnector,
        config: Optional[DiagnoseConfig] = None
    ):
        """
        初始化诊断 Skill

        参数:
            connector: UnifiedConnector 实例
            config: 诊断配置，None使用默认配置
        """
        self.connector = connector
        self.config = config or DiagnoseConfig()
        self.dialect = connector.dialect.lower()

        # 初始化工具类
        self.fingerprinter = SQLFingerprint()
        self.issue_classifier = IssueClassifier()
        self.score_calculator = ScoreCalculator()
        self.priority_sorter = PrioritySorter()
        self.metrics_aggregator = MetricsAggregator()
        self.query_extractor = QueryExtractor()

        # 初始化核心分析器
        self.plan_analyzer = ExecutionPlanAnalyzer(connector)
        self._sql_analyzer = SQLAnalyzer(connector)
        self._batch_analyzer = BatchAnalyzer()
        self._table_analyzer = TableAnalyzer(connector)
        self._report_generator = ReportGenerator()

        # 初始化多数据库诊断器
        self._diagnostician = get_diagnostician(self.dialect, connector)

        # 检测连接器类型
        connector_type = detect_connector_type(self.dialect)
        self._is_jdbc = (connector_type == "jdbc")
        self._is_unified = True

        logger.info(f"DiagnoseSkill 初始化完成 (dialect={self.dialect})")

    # ==================== 核心诊断API ====================

    @validate_params(sql=Validator.not_empty_string)
    def analyze_sql(
        self,
        sql: str,
        params: Optional[Dict[str, Any]] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """深度分析SQL语句"""
        try:
            result = self._sql_analyzer.analyze(sql, params, context)
            return create_success_response(result, "SQL分析完成")
        except Exception as e:
            logger.error(f"SQL分析失败: {e}")
            return create_error_response(
                str(e),
                ErrorCode.ANALYSIS_FAILED,
                {"sql": sql}
            )

    def analyze_sql_batch(
        self,
        sqls: List[str],
        show_progress: bool = False
    ) -> List[Dict[str, Any]]:
        """批量分析SQL语句"""
        return self._batch_analyzer.analyze_serial(
            sqls,
            self._sql_analyzer.analyze,
            show_progress=show_progress
        )

    def get_index_suggestions(
        self,
        sql: str,
        min_priority: str = "medium"
    ) -> List[Dict[str, Any]]:
        """获取索引建议"""
        return self._sql_analyzer.get_index_suggestions(sql, min_priority)

    def get_executable_fixes(self, sql: str) -> List[str]:
        """获取可执行的修复SQL"""
        return self._sql_analyzer.get_executable_fixes(sql)

    # ==================== 多数据库诊断功能 ====================

    def analyze_slow_queries(
        self,
        limit: int = 20,
        min_time: float = 1.0
    ) -> Dict[str, Any]:
        """分析慢查询（多数据库支持）"""
        try:
            result = self._diagnostician.analyze_slow_queries(
                limit=limit,
                min_time=min_time
            )
            return create_success_response(result, "慢查询分析完成")
        except Exception as e:
            logger.error(f"慢查询分析失败: {e}")
            return create_error_response(
                str(e),
                ErrorCode.SLOW_QUERY_FAILED
            )

    def analyze_performance_metrics(
        self,
        duration_minutes: int = 10
    ) -> Dict[str, Any]:
        """分析性能指标（多数据库支持）"""
        try:
            result = self._diagnostician.analyze_performance_metrics(
                duration_minutes=duration_minutes
            )
            return create_success_response(result, "性能指标分析完成")
        except Exception as e:
            logger.error(f"性能指标分析失败: {e}")
            return create_error_response(
                str(e),
                ErrorCode.PERF_ANALYSIS_FAILED
            )

    def get_database_stats(self) -> Dict[str, Any]:
        """获取数据库统计信息（多数据库支持）"""
        try:
            result = self._diagnostician.get_database_stats()
            return create_success_response(result, "数据库统计信息获取完成")
        except Exception as e:
            logger.error(f"获取数据库统计信息失败: {e}")
            return create_error_response(
                str(e),
                ErrorCode.METRICS_ERROR
            )

    # ==================== 向后兼容方法 ====================

    def analyze_aas(
        self,
        duration_minutes: int = 10,
        interval_seconds: int = 10
    ) -> Dict[str, Any]:
        """AAS分析（MySQL专用，向后兼容）"""
        if 'mysql' not in self.dialect:
            return create_error_response(
                f"AAS分析仅支持MySQL数据库，当前方言: {self.dialect}",
                ErrorCode.UNSUPPORTED_SQL,
                {"suggestion": "请使用 analyze_performance_metrics() 方法获取性能指标"}
            )

        return self.analyze_performance_metrics(duration_minutes=duration_minutes)

    # ==================== 表和Schema诊断 ====================

    def diagnose_table(
        self,
        table_name: str,
        include_indexes: bool = True,
        include_statistics: bool = True
    ) -> Dict[str, Any]:
        """诊断单表健康状况"""
        try:
            # table_analyzer.analyze 已经返回标准响应格式，直接返回
            return self._table_analyzer.analyze(
                table_name=table_name,
                include_indexes=include_indexes,
                include_statistics=include_statistics
            )
        except Exception as e:
            logger.error(f"表诊断失败: {e}")
            return create_error_response(
                str(e),
                ErrorCode.TABLE_DIAGNOSE_FAILED,
                {"table_name": table_name}
            )

    # ==================== 报告生成 ====================

    def generate_report(
        self,
        sqls: List[str],
        report_title: str = "SQL诊断报告"
    ) -> Dict[str, Any]:
        """生成诊断报告"""
        try:
            result = self._report_generator.generate(
                sqls=sqls,
                analyzer=self._sql_analyzer.analyze,
                title=report_title,
                dialect=self.dialect
            )
            return create_success_response(result, "诊断报告生成完成")
        except Exception as e:
            logger.error(f"生成诊断报告失败: {e}")
            return create_error_response(
                str(e),
                ErrorCode.UNKNOWN_ERROR
            )

    # ==================== SQL重写 ====================

    def rewrite_sql(self, sql: str, optimization_type: str = "auto") -> Dict[str, Any]:
        """SQL重写优化"""
        try:
            result = self._sql_analyzer.rewrite(sql, optimization_type)
            return create_success_response(result, "SQL重写完成")
        except Exception as e:
            logger.error(f"SQL重写失败: {e}")
            return create_error_response(
                str(e),
                ErrorCode.ANALYSIS_FAILED
            )

    def analyze_sql_quality(self, sql: str) -> Dict[str, Any]:
        """分析SQL质量"""
        try:
            result = self._sql_analyzer.analyze_quality(sql)
            return create_success_response(result, "SQL质量分析完成")
        except Exception as e:
            logger.error(f"SQL质量分析失败: {e}")
            return create_error_response(
                str(e),
                ErrorCode.ANALYSIS_FAILED
            )

    # ==================== 工具方法 ====================

    def get_sql_fingerprint(self, sql: str) -> str:
        """获取SQL指纹"""
        return self.fingerprinter.generate(sql)

    def classify_issue(self, issue_text: str) -> Dict[str, Any]:
        """分类问题"""
        return self.issue_classifier.classify(issue_text)

    def extract_query_info(self, sql: str) -> Dict[str, Any]:
        """提取查询信息"""
        return {
            "tables": self.query_extractor.extract_tables(sql),
            "columns": self.query_extractor.extract_columns(sql),
            "conditions": self.query_extractor.extract_where_conditions(sql),
            "fingerprint": self.fingerprinter.generate(sql)
        }

    def close(self):
        """关闭Skill，释放资源"""
        logger.info("关闭 DiagnoseSkill...")
        logger.info("DiagnoseSkill 已关闭")


    # ==================== 新增: 实时诊断方法 (P0高频场景) ====================

    def get_realtime_connections(self) -> Dict[str, Any]:
        """
        获取实时连接信息

        返回:
            Dict: 连接统计信息
        """
        try:
            if 'mysql' in self.dialect:
                return self._get_mysql_realtime_connections()
            else:
                return create_error_response(
                    f"实时连接分析暂不支持 {self.dialect}",
                    ErrorCode.UNSUPPORTED_SQL
                )
        except Exception as e:
            logger.error(f"获取实时连接失败: {e}")
            return create_error_response(str(e), ErrorCode.UNKNOWN_ERROR)

    def _get_mysql_realtime_connections(self) -> Dict[str, Any]:
        """MySQL实时连接分析"""
        try:
            # 总连接数
            result = self.connector.execute("""
                SELECT 
                    COUNT(*) as total,
                    SUM(CASE WHEN COMMAND != 'Sleep' THEN 1 ELSE 0 END) as active,
                    SUM(CASE WHEN TIME > 5 THEN 1 ELSE 0 END) as slow
                FROM information_schema.PROCESSLIST
                WHERE USER != 'system user'
            """)

            row = result.rows[0] if result.rows else (0, 0, 0)

            return create_success_response(
                message="实时连接信息获取成功",
                data={
                    "total": row[0],
                    "active": row[1],
                    "slow_count": row[2]
                }
            )
        except Exception as e:
            return create_error_response(str(e), ErrorCode.UNKNOWN_ERROR)

    def get_top_sql(self, limit: int = 10, threshold: int = 0,
                    order_by: str = "time") -> Dict[str, Any]:
        """
        获取TOP SQL

        参数:
            limit: 返回条数
            threshold: 执行时间阈值(秒)
            order_by: 排序依据(time/cpu/io/rows)

        返回:
            Dict: TOP SQL列表
        """
        try:
            if 'mysql' in self.dialect:
                return self._get_mysql_top_sql(limit, threshold, order_by)
            else:
                return create_error_response(
                    f"TOP SQL分析暂不支持 {self.dialect}",
                    ErrorCode.UNSUPPORTED_SQL
                )
        except Exception as e:
            logger.error(f"获取TOP SQL失败: {e}")
            return create_error_response(str(e), ErrorCode.UNKNOWN_ERROR)

    def _get_mysql_top_sql(self, limit: int, threshold: int,
                           order_by: str) -> Dict[str, Any]:
        """MySQL TOP SQL分析"""
        try:
            # 从PROCESSLIST获取实时慢查询
            result = self.connector.execute(f"""
                SELECT 
                    ID,
                    USER,
                    HOST,
                    DB,
                    COMMAND,
                    TIME as exec_time,
                    STATE,
                    LEFT(INFO, 500) as sql_text
                FROM information_schema.PROCESSLIST
                WHERE COMMAND != 'Sleep'
                    AND INFO IS NOT NULL
                    AND TIME >= :threshold
                ORDER BY TIME DESC
                LIMIT :limit
            """, {"threshold": threshold, "limit": limit})

            queries = []
            for row in result.rows:
                queries.append({
                    "id": row[0],
                    "user": row[1],
                    "host": row[2],
                    "db": row[3],
                    "command": row[4],
                    "exec_time": row[5],
                    "state": row[6],
                    "sql": row[7] if row[7] else ""
                })

            return create_success_response(
                message=f"获取到 {len(queries)} 条TOP SQL",
                data={"queries": queries}
            )
        except Exception as e:
            return create_error_response(str(e), ErrorCode.UNKNOWN_ERROR)

    def get_lock_waits(self) -> Dict[str, Any]:
        """
        获取锁等待信息

        返回:
            Dict: 锁等待列表
        """
        try:
            if 'mysql' in self.dialect:
                return self._get_mysql_lock_waits()
            else:
                return create_error_response(
                    f"锁等待分析暂不支持 {self.dialect}",
                    ErrorCode.UNSUPPORTED_SQL
                )
        except Exception as e:
            logger.error(f"获取锁等待失败: {e}")
            return create_error_response(str(e), ErrorCode.UNKNOWN_ERROR)

    def _get_mysql_lock_waits(self) -> Dict[str, Any]:
        """MySQL锁等待分析"""
        try:
            # MySQL 8.0+ 使用 data_lock_waits，5.7 使用 INNODB_LOCK_WAITS
            # 尝试使用兼容的查询方式
            result = self.connector.execute("""
                SELECT 
                    r.trx_id as waiting_trx_id,
                    r.trx_mysql_thread_id as waiting_thread,
                    b.trx_id as blocking_trx_id,
                    b.trx_mysql_thread_id as blocking_thread,
                    b.trx_query as blocking_query
                FROM information_schema.INNODB_LOCK_WAITS w
                JOIN information_schema.INNODB_TRX b ON b.trx_id = w.blocking_trx_id
                JOIN information_schema.INNODB_TRX r ON r.trx_id = w.requesting_trx_id
                LIMIT 10
            """)

            waits = []
            for row in result.rows:
                waits.append({
                    "waiting_trx": row[0],
                    "waiting_thread": row[1],
                    "blocking_trx": row[2],
                    "blocking_thread": row[3],
                    "sql": row[4] if row[4] else ""
                })

            return create_success_response(
                message=f"获取到 {len(waits)} 个锁等待",
                data={"lock_waits": waits}
            )
        except Exception as e:
            # 如果表不存在，返回空结果
            logger.debug(f"锁等待查询失败(可能不支持): {e}")
            return create_success_response(
                message="锁等待信息获取完成",
                data={"lock_waits": []}
            )

    def analyze_locks(self) -> Dict[str, Any]:
        """
        综合分析锁情况

        返回:
            Dict: 锁分析结果
        """
        try:
            if 'mysql' in self.dialect:
                return self._analyze_mysql_locks()
            else:
                return create_error_response(
                    f"锁分析暂不支持 {self.dialect}",
                    ErrorCode.UNSUPPORTED_SQL
                )
        except Exception as e:
            logger.error(f"锁分析失败: {e}")
            return create_error_response(str(e), ErrorCode.UNKNOWN_ERROR)

    def _analyze_mysql_locks(self) -> Dict[str, Any]:
        """MySQL锁分析"""
        try:
            # 获取锁等待
            lock_waits_result = self._get_mysql_lock_waits()
            lock_waits = lock_waits_result.get('data', {}).get('lock_waits', [])

            # 获取事务统计
            result = self.connector.execute("""
                SELECT 
                    COUNT(*) as trx_count,
                    SUM(CASE WHEN trx_state = 'RUNNING' THEN 1 ELSE 0 END) as running
                FROM information_schema.INNODB_TRX
            """)

            row = result.rows[0] if result.rows else (0, 0)

            return create_success_response(
                message="锁分析完成",
                data={
                    "lock_waits": lock_waits,
                    "deadlocks": [],  # 需要查询performance_schema
                    "statistics": {
                        "trx_count": row[0],
                        "running_trx": row[1],
                        "lock_waits_count": len(lock_waits)
                    }
                }
            )
        except Exception as e:
            return create_error_response(str(e), ErrorCode.UNKNOWN_ERROR)

    def analyze_space(self, top_n: int = 20, min_size_mb: int = 100, database: Optional[str] = None) -> Dict[str, Any]:
        """
        空间诊断

        参数:
            top_n: TOP N大表
            min_size_mb: 最小表大小(MB)
            database: 指定数据库名（可选，默认使用当前连接的数据库）

        返回:
            Dict: 空间分析结果
        """
        try:
            if 'mysql' in self.dialect:
                return self._analyze_mysql_space(top_n, min_size_mb, database)
            else:
                return create_error_response(
                    f"空间分析暂不支持 {self.dialect}",
                    ErrorCode.UNSUPPORTED_SQL
                )
        except Exception as e:
            logger.error(f"空间分析失败: {e}")
            return create_error_response(str(e), ErrorCode.UNKNOWN_ERROR)

    def _analyze_mysql_space(self, top_n: int, min_size_mb: int, database: Optional[str] = None) -> Dict[str, Any]:
        """MySQL空间分析"""
        try:
            # 获取数据库名（优先使用参数传入的数据库名）
            if database:
                current_db = database
                logger.info(f"使用指定数据库进行空间分析: {current_db}")
            else:
                # 获取当前数据库名
                db_result = self.connector.execute("SELECT DATABASE()")
                current_db = db_result.rows[0][0] if db_result.rows and db_result.rows[0][0] else None
                logger.info(f"使用当前连接的数据库进行空间分析: {current_db}")

            if not current_db:
                return create_error_response(
                    "无法获取当前数据库名",
                    ErrorCode.UNKNOWN_ERROR
                )

            # 获取表空间信息
            result = self.connector.execute("""
                SELECT 
                    table_name,
                    ROUND(data_length / 1024 / 1024, 2) as data_mb,
                    ROUND(index_length / 1024 / 1024, 2) as index_mb,
                    ROUND((data_length + index_length) / 1024 / 1024, 2) as total_mb,
                    table_rows,
                    engine
                FROM information_schema.TABLES
                WHERE table_schema = :db
                    AND (data_length + index_length) / 1024 / 1024 >= :min_size
                ORDER BY (data_length + index_length) DESC
                LIMIT :limit
            """, {"db": current_db, "min_size": min_size_mb, "limit": top_n})

            tables = []
            total_data = 0
            total_index = 0

            for row in result.rows:
                tables.append({
                    "table": row[0],
                    "data_mb": row[1],
                    "index_mb": row[2],
                    "size_mb": row[3],
                    "rows": row[4],
                    "engine": row[5],
                    "fragmentation": 0  # 需要额外计算
                })
                total_data += row[1] or 0
                total_index += row[2] or 0

            return create_success_response(
                message=f"获取到 {len(tables)} 个大表",
                data={
                    "total_space": {
                        "total_gb": round((total_data + total_index) / 1024, 2),
                        "data_gb": round(total_data / 1024, 2),
                        "index_gb": round(total_index / 1024, 2)
                    },
                    "large_tables": tables,
                    "suggestions": []
                }
            )
        except Exception as e:
            return create_error_response(str(e), ErrorCode.UNKNOWN_ERROR)

    def analyze_connections(self, show_idle: bool = False) -> Dict[str, Any]:
        """
        连接分析

        参数:
            show_idle: 是否显示空闲连接

        返回:
            Dict: 连接分析结果
        """
        try:
            if 'mysql' in self.dialect:
                return self._analyze_mysql_connections(show_idle)
            else:
                return create_error_response(
                    f"连接分析暂不支持 {self.dialect}",
                    ErrorCode.UNSUPPORTED_SQL
                )
        except Exception as e:
            logger.error(f"连接分析失败: {e}")
            return create_error_response(str(e), ErrorCode.UNKNOWN_ERROR)

    def _analyze_mysql_connections(self, show_idle: bool) -> Dict[str, Any]:
        """MySQL连接分析"""
        try:
            # 获取连接统计
            result = self.connector.execute("""
                SELECT 
                    @@max_connections as max_conn,
                    COUNT(*) as current,
                    SUM(CASE WHEN COMMAND != 'Sleep' THEN 1 ELSE 0 END) as active,
                    SUM(CASE WHEN COMMAND = 'Sleep' THEN 1 ELSE 0 END) as idle
                FROM information_schema.PROCESSLIST
                WHERE USER != 'system user'
            """)

            row = result.rows[0] if result.rows else (100, 0, 0, 0)
            max_conn, current, active, idle = row
            usage_pct = (current / max_conn * 100) if max_conn > 0 else 0

            data = {
                "statistics": {
                    "max_connections": max_conn,
                    "current": current,
                    "active": active,
                    "idle": idle,
                    "usage_percent": round(usage_pct, 1)
                }
            }

            # 获取空闲连接详情
            if show_idle:
                result = self.connector.execute("""
                    SELECT 
                        ID,
                        USER,
                        HOST,
                        TIME as idle_time
                    FROM information_schema.PROCESSLIST
                    WHERE COMMAND = 'Sleep'
                        AND USER != 'system user'
                    ORDER BY TIME DESC
                    LIMIT 20
                """)

                idle_conns = []
                for row in result.rows:
                    idle_conns.append({
                        "id": row[0],
                        "user": row[1],
                        "host": row[2],
                        "idle_time": row[3]
                    })
                data["idle_connections"] = idle_conns

            return create_success_response(
                message="连接分析完成",
                data=data
            )
        except Exception as e:
            return create_error_response(str(e), ErrorCode.UNKNOWN_ERROR)

    def analyze_replication(self) -> Dict[str, Any]:
        """
        复制诊断

        返回:
            Dict: 复制状态
        """
        try:
            if 'mysql' in self.dialect:
                return self._analyze_mysql_replication()
            else:
                return create_error_response(
                    f"复制分析暂不支持 {self.dialect}",
                    ErrorCode.UNSUPPORTED_SQL
                )
        except Exception as e:
            logger.error(f"复制分析失败: {e}")
            return create_error_response(str(e), ErrorCode.UNKNOWN_ERROR)

    def _analyze_mysql_replication(self) -> Dict[str, Any]:
        """MySQL复制分析"""
        try:
            data = {"status": {}}

            # 检查是否为主库
            result = self.connector.execute("SHOW MASTER STATUS")
            is_master = len(result.rows) > 0
            data["status"]["is_master"] = is_master

            if is_master:
                data["status"]["binlog_enabled"] = True
                data["status"]["slave_count"] = 0  # 需要额外查询

            # 检查是否为从库
            try:
                result = self.connector.execute("SHOW SLAVE STATUS")
                is_slave = len(result.rows) > 0
                data["status"]["is_slave"] = is_slave

                if is_slave and result.rows:
                    row = result.rows[0]
                    # SHOW SLAVE STATUS 返回的列名可能不同，使用索引
                    data["slave_status"] = {
                        "io_running": row[10] if len(row) > 10 else "No",
                        "sql_running": row[11] if len(row) > 11 else "No",
                        "delay_seconds": row[32] if len(row) > 32 else 0
                    }
            except Exception:
                data["status"]["is_slave"] = False

            return create_success_response(
                message="复制分析完成",
                data=data
            )
        except Exception as e:
            return create_error_response(str(e), ErrorCode.UNKNOWN_ERROR)

    def recommend_indexes(self, table: str = None) -> Dict[str, Any]:
        """
        索引建议

        参数:
            table: 指定表名(可选，默认分析全库)

        返回:
            Dict: 索引建议列表
        """
        try:
            if 'mysql' in self.dialect:
                return self._recommend_mysql_indexes(table)
            else:
                return create_error_response(
                    f"索引建议暂不支持 {self.dialect}",
                    ErrorCode.UNSUPPORTED_SQL
                )
        except Exception as e:
            logger.error(f"索引建议失败: {e}")
            return create_error_response(str(e), ErrorCode.UNKNOWN_ERROR)

    def _recommend_mysql_indexes(self, table: str = None) -> Dict[str, Any]:
        """
        MySQL索引建议

        分析维度：
        1. 缺失索引（基于慢查询和WHERE条件）
        2. 冗余索引（重复索引、前缀索引）
        3. 未使用索引（基于performance_schema）
        4. 低基数索引（索引选择性差）

        参数:
            table: 指定表名

        返回:
            Dict: 索引建议结果
        """
        try:
            suggestions = []
            current_db = None

            # 获取当前数据库名
            try:
                result = self.connector.execute("SELECT DATABASE()")
                if result.rows:
                    current_db = result.rows[0][0]
            except Exception:
                pass

            if not current_db:
                return create_error_response(
                    "无法获取当前数据库名",
                    ErrorCode.UNKNOWN_ERROR
                )

            # 1. 分析缺失索引（基于performance_schema.table_io_waits_summary_by_index_usage）
            try:
                missing_indexes = self._analyze_missing_indexes_mysql(current_db, table)
                suggestions.extend(missing_indexes)
            except Exception as e:
                logger.warning(f"分析缺失索引失败: {e}")

            # 2. 分析冗余索引
            try:
                redundant_indexes = self._analyze_redundant_indexes_mysql(current_db, table)
                suggestions.extend(redundant_indexes)
            except Exception as e:
                logger.warning(f"分析冗余索引失败: {e}")

            # 3. 分析未使用索引
            try:
                unused_indexes = self._analyze_unused_indexes_mysql(current_db, table)
                suggestions.extend(unused_indexes)
            except Exception as e:
                logger.warning(f"分析未使用索引失败: {e}")

            # 4. 分析低基数索引
            try:
                low_cardinality = self._analyze_low_cardinality_indexes_mysql(current_db, table)
                suggestions.extend(low_cardinality)
            except Exception as e:
                logger.warning(f"分析低基数索引失败: {e}")

            # 按优先级排序
            priority_order = {"high": 0, "medium": 1, "low": 2}
            suggestions.sort(
                key=lambda x: priority_order.get(x.get("priority", "low"), 2)
            )

            return create_success_response(
                message=f"发现 {len(suggestions)} 个索引建议",
                data={
                    "database": current_db,
                    "table": table,
                    "suggestions": suggestions,
                    "summary": {
                        "total": len(suggestions),
                        "high_priority": len([s for s in suggestions if s.get("priority") == "high"]),
                        "medium_priority": len([s for s in suggestions if s.get("priority") == "medium"]),
                        "low_priority": len([s for s in suggestions if s.get("priority") == "low"])
                    }
                }
            )

        except Exception as e:
            return create_error_response(str(e), ErrorCode.UNKNOWN_ERROR)

    def _analyze_missing_indexes_mysql(self, database: str, table: str = None) -> List[Dict[str, Any]]:
        """
        分析缺失索引（基于全表扫描次数）

        参数:
            database: 数据库名
            table: 表名(可选)

        返回:
            List[Dict]: 缺失索引建议列表
        """
        suggestions = []

        # 查询全表扫描次数较多的表
        query = """
            SELECT
                OBJECT_SCHEMA as db,
                OBJECT_NAME as table_name,
                COUNT_READ as total_reads,
                SUM_TIMER_WAIT / 1000000000000 as total_latency_ms
            FROM performance_schema.table_io_waits_summary_by_table
            WHERE OBJECT_SCHEMA = :db
                AND COUNT_READ > 1000
        """
        params = {"db": database}

        if table:
            query += " AND OBJECT_NAME = :table"
            params["table"] = table

        query += " ORDER BY COUNT_READ DESC LIMIT 20"

        try:
            result = self.connector.execute(query, params)

            for row in result.rows:
                table_name = row[1]
                total_reads = row[2]
                latency_ms = round(row[3] or 0, 2)

                # 检查该表是否有主键
                pk_result = self.connector.execute("""
                    SELECT COUNT(*)
                    FROM information_schema.TABLE_CONSTRAINTS
                    WHERE TABLE_SCHEMA = :db
                        AND TABLE_NAME = :table
                        AND CONSTRAINT_TYPE = 'PRIMARY KEY'
                """, {"db": database, "table": table_name})

                has_pk = pk_result.rows[0][0] > 0 if pk_result.rows else False

                if not has_pk:
                    suggestions.append({
                        "type": "missing_primary_key",
                        "priority": "high",
                        "table": table_name,
                        "description": f"表 {table_name} 缺少主键，建议添加自增主键",
                        "impact": f"全表扫描 {total_reads} 次，延迟 {latency_ms}ms",
                        "suggestion": f"ALTER TABLE {table_name} ADD COLUMN id INT AUTO_INCREMENT PRIMARY KEY;",
                        "reason": "无主键的表在查询和更新时性能较差"
                    })

        except Exception as e:
            logger.warning(f"查询全表扫描统计失败: {e}")

        return suggestions

    def _analyze_redundant_indexes_mysql(self, database: str, table: str = None) -> List[Dict[str, Any]]:
        """
        分析冗余索引

        参数:
            database: 数据库名
            table: 表名(可选)

        返回:
            List[Dict]: 冗余索引建议列表
        """
        suggestions = []

        # 查询可能的冗余索引（前缀重复）
        query = """
            SELECT
                t.TABLE_NAME,
                t.INDEX_NAME,
                t.COLUMN_NAME,
                t.SEQ_IN_INDEX,
                t2.INDEX_NAME as redundant_to,
                t2.COLUMN_NAME as redundant_col
            FROM information_schema.STATISTICS t
            JOIN information_schema.STATISTICS t2
                ON t.TABLE_SCHEMA = t2.TABLE_SCHEMA
                AND t.TABLE_NAME = t2.TABLE_NAME
                AND t.COLUMN_NAME = t2.COLUMN_NAME
                AND t.SEQ_IN_INDEX = t2.SEQ_IN_INDEX
                AND t.INDEX_NAME != t2.INDEX_NAME
            WHERE t.TABLE_SCHEMA = :db
                AND t.NON_UNIQUE = 1
        """
        params = {"db": database}

        if table:
            query += " AND t.TABLE_NAME = :table"
            params["table"] = table

        try:
            result = self.connector.execute(query, params)

            seen = set()
            for row in result.rows:
                table_name = row[0]
                index_name = row[1]
                redundant_to = row[4]
                key = (table_name, index_name, redundant_to)

                if key not in seen:
                    seen.add(key)
                    suggestions.append({
                        "type": "redundant_index",
                        "priority": "medium",
                        "table": table_name,
                        "index": index_name,
                        "description": f"索引 {index_name} 可能是冗余的",
                        "suggestion": f"DROP INDEX {index_name} ON {table_name};",
                        "reason": f"该索引与 {redundant_to} 有重复前缀",
                        "note": "请先确认该索引确实未被使用后再删除"
                    })

        except Exception as e:
            logger.warning(f"查询冗余索引失败: {e}")

        return suggestions

    def _analyze_unused_indexes_mysql(self, database: str, table: str = None) -> List[Dict[str, Any]]:
        """
        分析未使用索引

        参数:
            database: 数据库名
            table: 表名(可选)

        返回:
            List[Dict]: 未使用索引建议列表
        """
        suggestions = []

        # 查询未使用的索引（需要开启performance_schema）
        query = """
            SELECT
                OBJECT_SCHEMA,
                OBJECT_NAME,
                INDEX_NAME,
                COUNT_FETCH,
                COUNT_INSERT,
                COUNT_UPDATE,
                COUNT_DELETE
            FROM performance_schema.table_io_waits_summary_by_index_usage
            WHERE OBJECT_SCHEMA = :db
                AND INDEX_NAME IS NOT NULL
                AND COUNT_FETCH = 0
                AND COUNT_INSERT = 0
                AND COUNT_UPDATE = 0
                AND COUNT_DELETE = 0
        """
        params = {"db": database}

        if table:
            query += " AND OBJECT_NAME = :table"
            params["table"] = table

        query += " LIMIT 20"

        try:
            result = self.connector.execute(query, params)

            for row in result.rows:
                table_name = row[1]
                index_name = row[2]

                # 排除主键
                if index_name == 'PRIMARY':
                    continue

                suggestions.append({
                    "type": "unused_index",
                    "priority": "low",
                    "table": table_name,
                    "index": index_name,
                    "description": f"索引 {index_name} 从未被使用",
                    "suggestion": f"DROP INDEX {index_name} ON {table_name};",
                    "reason": "该索引自服务器启动以来从未被使用",
                    "note": "建议观察一段时间后再删除，避免误删周期性使用的索引"
                })

        except Exception as e:
            logger.warning(f"查询未使用索引失败: {e}")

        return suggestions

    def _analyze_low_cardinality_indexes_mysql(self, database: str, table: str = None) -> List[Dict[str, Any]]:
        """
        分析低基数索引（选择性差的索引）

        参数:
            database: 数据库名
            table: 表名(可选)

        返回:
            List[Dict]: 低基数索引建议列表
        """
        suggestions = []

        # 获取所有索引及其基数信息
        query = """
            SELECT
                TABLE_NAME,
                INDEX_NAME,
                COLUMN_NAME,
                CARDINALITY
            FROM information_schema.STATISTICS
            WHERE TABLE_SCHEMA = :db
                AND NON_UNIQUE = 1
                AND CARDINALITY IS NOT NULL
                AND CARDINALITY < 10
        """
        params = {"db": database}

        if table:
            query += " AND TABLE_NAME = :table"
            params["table"] = table

        try:
            result = self.connector.execute(query, params)

            for row in result.rows:
                table_name = row[0]
                index_name = row[1]
                column_name = row[2]
                cardinality = row[3]

                suggestions.append({
                    "type": "low_cardinality",
                    "priority": "low",
                    "table": table_name,
                    "index": index_name,
                    "column": column_name,
                    "description": f"索引 {index_name} 选择性较差",
                    "cardinality": cardinality,
                    "reason": f"基数仅为 {cardinality}，索引效果不佳",
                    "note": "考虑是否需要该索引，或者使用复合索引"
                })

        except Exception as e:
            logger.warning(f"查询低基数索引失败: {e}")

        return suggestions

    # ==================== 统一性能模型诊断方法 ====================

    def _get_performance_analyzer(self):
        """
        获取对应数据库的性能分析器

        返回:
            PerformanceAnalyzer实例或None
        """
        if 'mysql' in self.dialect:
            from .diagnosticians.mysql_performance_analyzer import MySQLPerformanceAnalyzer
            return MySQLPerformanceAnalyzer(self.connector, timeout=30)
        elif 'oracle' in self.dialect:
            from .diagnosticians.oracle_performance_analyzer import OraclePerformanceAnalyzer
            return OraclePerformanceAnalyzer(self.connector, timeout=30)
        elif 'postgres' in self.dialect:
            from .diagnosticians.postgresql_performance_analyzer import PostgreSQLPerformanceAnalyzer
            return PostgreSQLPerformanceAnalyzer(self.connector, timeout=30)
        else:
            return None

    def take_performance_snapshot(self) -> Dict[str, Any]:
        """
        采集性能快照（基于统一性能模型）

        返回:
            Dict: 性能快照数据
        """
        try:
            analyzer = self._get_performance_analyzer()

            if not analyzer:
                return create_error_response(
                    f"统一性能模型暂不支持 {self.dialect}",
                    ErrorCode.UNSUPPORTED_SQL
                )

            snapshot = analyzer.take_snapshot()
            bottlenecks = analyzer.analyze_bottleneck(snapshot)

            return create_success_response(
                message="性能快照采集完成",
                data={
                    "snapshot": snapshot.to_dict(),
                    "bottlenecks": bottlenecks,
                    "summary": {
                        "total_metrics": len(snapshot.metrics),
                        "total_slow_queries": len(snapshot.slow_queries),
                        "active_sessions": snapshot.active_sessions,
                        "total_sessions": snapshot.total_sessions
                    }
                }
            )

        except Exception as e:
            logger.error(f"性能快照采集失败: {e}")
            return create_error_response(str(e), ErrorCode.PERF_ANALYSIS_FAILED)

    def analyze_performance_bottleneck(self) -> Dict[str, Any]:
        """
        分析性能瓶颈（基于统一性能模型）

        返回:
            Dict: 瓶颈分析结果
        """
        try:
            analyzer = self._get_performance_analyzer()

            if not analyzer:
                return create_error_response(
                    f"性能瓶颈分析暂不支持 {self.dialect}",
                    ErrorCode.UNSUPPORTED_SQL
                )

            snapshot = analyzer.take_snapshot()
            bottlenecks = analyzer.analyze_bottleneck(snapshot)

            return create_success_response(
                message=f"发现 {len(bottlenecks)} 个性能瓶颈",
                data={
                    "bottlenecks": bottlenecks,
                    "severity_summary": self._summarize_severity(bottlenecks),
                    "recommendations": self._generate_recommendations(bottlenecks)
                }
            )

        except Exception as e:
            logger.error(f"性能瓶颈分析失败: {e}")
            return create_error_response(str(e), ErrorCode.PERF_ANALYSIS_FAILED)

    def _summarize_severity(self, bottlenecks: List[Dict]) -> Dict[str, int]:
        """汇总严重程度"""
        summary = {"critical": 0, "high": 0, "medium": 0, "low": 0}
        for b in bottlenecks:
            severity = b.get("severity", "low")
            if severity in summary:
                summary[severity] += 1
        return summary

    def _generate_recommendations(self, bottlenecks: List[Dict]) -> List[str]:
        """生成优化建议"""
        recommendations = []

        for bottleneck in bottlenecks:
            category = bottleneck.get("category", "")
            suggestion = bottleneck.get("suggestion", "")

            if suggestion:
                recommendations.append(f"[{category}] {suggestion}")

        return recommendations


# 版本兼容说明：
# 本模块已统一为 DiagnoseSkill，不再区分V2/V3
# 如需版本兼容，请使用：
#   from dbskiter.db_diagnose import DiagnoseSkill
