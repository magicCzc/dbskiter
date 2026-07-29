"""
db_diagnose/skill.py
数据库诊断 Skill 统一入口

文件功能：提供统一的SQL诊断API，支持MySQL/Oracle/PostgreSQL/SQL Server/ClickHouse/SQLite
主要类：DiagnoseSkill - 诊断Skill统一入口

支持的数据库：
    - MySQL: 慢查询分析、AAS分析、执行计划分析
    - Oracle: 慢SQL分析(AWR)、性能指标分析、执行计划分析
    - PostgreSQL: 慢查询分析(pg_stat_statements)、性能分析、执行计划分析
    - SQL Server: 慢查询分析(Query Store/DMV)、性能指标分析、阻塞分析、等待统计
    - ClickHouse: 锁分析、空间分析、连接分析、复制分析、索引建议、性能快照
    - SQLite: 锁分析、空间分析、连接分析、复制分析、索引建议、性能快照

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
作者: Magiczc
创建时间: 2026-04-23
"""

import logging
from typing import List, Dict, Any, Optional

from dbskiter.shared.unified_connector import UnifiedConnector, detect_connector_type
from dbskiter.shared.validators import validate_params, Validator

from dbskiter.shared.error_handler import create_success_response, create_error_response

# 导入数据模型
from .models import (
    ErrorCode,
    DiagnoseConfig,
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
from .diagnosticians.clickhouse_performance_analyzer import ClickHousePerformanceAnalyzer
from .diagnosticians.sqlite_performance_analyzer import SQLitePerformanceAnalyzer

from dbskiter.db_diagnose.mixins import (
    AiContextMixin,
    SlowQueriesMixin,
    LockAnalyzerMixin,
    SpaceAnalyzerMixin,
    ConnectionReplicationMixin,
    IndexAdvisorMixin,
    PerformanceMixin,
)

logger = logging.getLogger(__name__)


class DiagnoseSkill(
    AiContextMixin,
    SlowQueriesMixin,
    LockAnalyzerMixin,
    SpaceAnalyzerMixin,
    ConnectionReplicationMixin,
    IndexAdvisorMixin,
    PerformanceMixin,
):
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
        - SQL Server
        - ClickHouse
        - SQLite
    """

    def __init__(self, connector: UnifiedConnector, config: Optional[DiagnoseConfig] = None):
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
        self._is_jdbc = connector_type == "jdbc"
        self._is_unified = True

        logger.info(f"DiagnoseSkill 初始化完成 (dialect={self.dialect})")

    # ==================== 核心诊断API ====================

    @validate_params(sql=Validator.not_empty_string)
    def analyze_sql(
        self, sql: str, params: Optional[Dict[str, Any]] = None, context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """深度分析SQL语句"""
        try:
            result = self._sql_analyzer.analyze(sql, params, context)
            return create_success_response(result, "SQL分析完成")
        except Exception as e:
            logger.error(f"SQL分析失败: {e}")
            return create_error_response(str(e), ErrorCode.ANALYSIS_FAILED, {"sql": sql})

    def analyze_sql_batch(self, sqls: List[str], show_progress: bool = False) -> List[Dict[str, Any]]:
        """批量分析SQL语句"""
        return self._batch_analyzer.analyze_serial(sqls, self._sql_analyzer.analyze, show_progress=show_progress)

    def get_index_suggestions(self, sql: str, min_priority: str = "medium") -> List[Dict[str, Any]]:
        """获取索引建议"""
        return self._sql_analyzer.get_index_suggestions(sql, min_priority)

    def get_executable_fixes(self, sql: str) -> List[str]:
        """获取可执行的修复SQL"""
        return self._sql_analyzer.get_executable_fixes(sql)

    # ==================== 多数据库诊断功能 ====================

    def diagnose_table(
        self, table_name: str, include_indexes: bool = True, include_statistics: bool = True
    ) -> Dict[str, Any]:
        """诊断单表健康状况"""
        try:
            # table_analyzer.analyze 已经返回标准响应格式，直接返回
            return self._table_analyzer.analyze(
                table_name=table_name, include_indexes=include_indexes, include_statistics=include_statistics
            )
        except Exception as e:
            logger.error(f"表诊断失败: {e}")
            return create_error_response(str(e), ErrorCode.TABLE_DIAGNOSE_FAILED, {"table_name": table_name})

    # ==================== 报告生成 ====================

    def generate_report(
        self, sqls: List[str], report_title: str = "SQL诊断报告", report_format: str = "json"
    ) -> Dict[str, Any]:
        """
        生成诊断报告

        参数:
            sqls: SQL语句列表
            report_title: 报告标题
            report_format: 报告格式 (json/markdown/text)

        返回:
            Dict: 诊断报告
        """
        try:
            # 1. 分析所有SQL
            analyses = []
            for sql in sqls:
                analysis_result = self._sql_analyzer.analyze(sql)
                if analysis_result.get("success"):
                    analyses.append(analysis_result.get("data", {}))

            # 2. 生成报告
            report_content = self._report_generator.generate(analyses=analyses, report_format=report_format)

            # 3. 如果是JSON格式，解析为字典
            if report_format == "json":
                import json

                report_data = json.loads(report_content)
            else:
                report_data = {"content": report_content}

            return create_success_response(data=report_data, message=f"诊断报告生成完成，分析了 {len(analyses)} 条SQL")
        except Exception as e:
            logger.error(f"生成诊断报告失败: {e}")
            return create_error_response(str(e), ErrorCode.UNKNOWN_ERROR)

    # ==================== SQL重写 ====================

    def rewrite_sql(self, sql: str, optimization_type: str = "auto") -> Dict[str, Any]:
        """SQL重写优化"""
        try:
            result = self._sql_analyzer.rewrite(sql, optimization_type)
            return create_success_response(result, "SQL重写完成")
        except Exception as e:
            logger.error(f"SQL重写失败: {e}")
            return create_error_response(str(e), ErrorCode.ANALYSIS_FAILED)

    def analyze_sql_quality(self, sql: str) -> Dict[str, Any]:
        """分析SQL质量"""
        try:
            result = self._sql_analyzer.analyze_quality(sql)
            return create_success_response(result, "SQL质量分析完成")
        except Exception as e:
            logger.error(f"SQL质量分析失败: {e}")
            return create_error_response(str(e), ErrorCode.ANALYSIS_FAILED)

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
            "fingerprint": self.fingerprinter.generate(sql),
        }

    # ==================== AI上下文构建 ====================

    def realtime_diagnose(self, threshold: int = 5) -> Dict[str, Any]:
        """
        实时综合诊断 - 分析数据库当前性能问题

        功能：
            1. 检查活跃连接数
            2. 检查锁等待情况
            3. 检查TOP SQL（慢查询）
            4. 给出诊断建议

        参数:
            threshold: 慢查询阈值（秒，默认5）

        返回:
            Dict: 综合诊断结果
        """
        try:
            # 1. 获取连接信息
            conn_result = self.get_realtime_connections()
            conn_data = conn_result.get("data", {}) if conn_result.get("success") else {}

            # 2. 获取锁等待信息
            lock_result = self.get_lock_waits()
            lock_data = lock_result.get("data", {}) if lock_result.get("success") else {}

            # 3. 获取TOP SQL
            top_sql_result = self.get_top_sql(limit=5, threshold=threshold)
            top_sql_data = top_sql_result.get("data", {}) if top_sql_result.get("success") else {}

            # 4. 分析并生成建议
            suggestions = []
            issues = []

            # 分析连接数
            total_conn = conn_data.get("total", 0)
            active_conn = conn_data.get("active", 0)
            slow_count = conn_data.get("slow_count", 0)

            if total_conn > 100:
                issues.append(f"连接数过多: {total_conn}")
                suggestions.append("考虑优化连接池配置或检查连接泄漏")

            if active_conn > 20:
                issues.append(f"活跃连接数高: {active_conn}")
                suggestions.append("检查是否有长事务或慢查询占用连接")

            # 分析锁等待
            lock_waits = lock_data.get("lock_waits", [])
            if lock_waits:
                issues.append(f"存在锁等待: {len(lock_waits)}个")
                suggestions.append("检查锁等待链，考虑优化事务或添加索引")

            # 分析慢查询
            queries = top_sql_data.get("queries", [])
            if queries:
                issues.append(f"发现慢查询: {len(queries)}个（>{threshold}秒）")
                suggestions.append("执行 'diagnose slow-queries' 查看详细慢查询信息")
                suggestions.append("执行 'diagnose top' 查看资源消耗最高的SQL")

            # 如果没有问题，给出正常提示
            if not issues:
                suggestions.append("数据库运行正常，暂无性能问题")

            return create_success_response(
                message="实时诊断完成",
                data={
                    "connections": conn_data,
                    "lock_waits": lock_data,
                    "top_sql": top_sql_data,
                    "issues": issues,
                    "suggestions": suggestions,
                    "threshold": threshold,
                },
            )

        except Exception as e:
            logger.error(f"实时诊断失败: {e}")
            return create_error_response(str(e), ErrorCode.UNKNOWN_ERROR)

    def get_realtime_connections(self) -> Dict[str, Any]:
        """
        获取实时连接信息

        返回:
            Dict: 连接统计信息
        """
        try:
            if self._diagnostician:
                result = self._diagnostician.get_realtime_connections()
                return self._convert_diagnostician_result(result)
            else:
                return create_error_response(f"实时连接分析暂不支持 {self.dialect}", ErrorCode.UNSUPPORTED_SQL)
        except Exception as e:
            logger.error(f"获取实时连接失败: {e}")
            return create_error_response(str(e), ErrorCode.UNKNOWN_ERROR)

    def get_top_sql(self, limit: int = 10, threshold: int = 0, order_by: str = "time") -> Dict[str, Any]:
        """
        获取TOP SQL（已接入多步骤计时）

        参数:
            limit: 返回条数
            threshold: 执行时间阈值(秒)
            order_by: 排序依据(time/cpu/io/rows)

        返回:
            Dict: TOP SQL列表，包含 _execution_time 步骤耗时
        """
        from dbskiter.shared.execution_timer import ExecutionTimer

        timer = ExecutionTimer().start()

        try:
            with timer.step("db_query", "从数据库采集TOP SQL"):
                if self._diagnostician:
                    result = self._diagnostician.get_top_sql(limit, threshold)
                    result = self._convert_diagnostician_result(result)
                else:
                    result = create_error_response(f"TOP SQL分析暂不支持 {self.dialect}", ErrorCode.UNSUPPORTED_SQL)

            with timer.step("format_result", "转换并封装结果"):
                if isinstance(result, dict) and "_execution_time" not in result:
                    pass  # 保留原结果

            result["_execution_time"] = timer.to_summary()
            return result
        except Exception as e:
            logger.error(f"获取TOP SQL失败: {e}")
            return create_error_response(str(e), ErrorCode.UNKNOWN_ERROR)

    def _is_valid_table_name(self, table: str) -> bool:
        """
        验证表名是否合法（防止SQL注入）

        参数:
            table: 表名

        返回:
            bool: 是否合法

        验证规则:
            - 只允许字母、数字、下划线、点号、美元符号
            - 不允许连续的点号
            - 不允许以点号开头或结尾
        """
        if not table:
            return True  # 空表名视为有效（表示不指定表）

        # 清理后检查是否只包含合法字符
        # 支持schema.table格式和Oracle的$符号
        cleaned = table.replace(".", "").replace("_", "").replace("-", "").replace("$", "")
        if not cleaned.isalnum():
            return False

        # 检查点号使用是否合法
        if ".." in table:
            return False
        if table.startswith(".") or table.endswith("."):
            return False

        return True

    # ==================== PostgreSQL特有诊断方法 ====================

    def analyze_vacuum(self) -> Dict[str, Any]:
        """
        分析PostgreSQL VACUUM状态

        检查表的自动清理状态和死元组情况

        返回:
            Dict: VACUUM状态分析结果
        """
        try:
            if "postgresql" not in self.dialect:
                return create_error_response(
                    f"VACUUM分析仅支持PostgreSQL，当前数据库: {self.dialect}", ErrorCode.UNSUPPORTED_SQL
                )

            if self._diagnostician:
                result = self._diagnostician.analyze_vacuum_status()
                return self._convert_diagnostician_result(result)
            else:
                return create_error_response("VACUUM分析需要PostgreSQL诊断器", ErrorCode.UNKNOWN_ERROR)
        except Exception as e:
            logger.error(f"VACUUM分析失败: {e}")
            return create_error_response(str(e), ErrorCode.UNKNOWN_ERROR)

    def analyze_bloat(self, threshold: int = 30) -> Dict[str, Any]:
        """
        分析表膨胀/碎片情况

        PostgreSQL: 检测MVCC导致的表膨胀
        MySQL: 检测InnoDB表碎片
        Oracle: 检测表空间碎片

        参数:
            threshold: 膨胀率阈值（百分比，默认30）

        返回:
            Dict: 表膨胀/碎片分析结果，统一包含以下字段:
                - tables: 需要关注的表/表空间列表（标准化格式）
                - health_score: 健康评分(0-100)
                - total_wasted_space_mb: 总浪费空间
                - suggestions: 优化建议
                - actionable_commands: 可执行的维护命令
                - db_type: 数据库类型标签
        """
        try:
            if self._diagnostician:
                if "postgresql" in self.dialect:
                    result = self._diagnostician.analyze_table_bloat(threshold=threshold)
                    db_label = "PostgreSQL"
                elif "mysql" in self.dialect:
                    result = self._diagnostician.analyze_table_fragmentation()
                    db_label = "MySQL"
                elif "oracle" in self.dialect:
                    result = self._diagnostician.analyze_tablespace_fragmentation()
                    db_label = "Oracle"
                elif "clickhouse" in self.dialect:
                    result = self._diagnostician.analyze_partitions()
                    db_label = "ClickHouse"
                elif "sqlite" in self.dialect:
                    result = self._diagnostician.analyze_fragmentation()
                    db_label = "SQLite"
                else:
                    return create_error_response(f"膨胀/碎片分析暂不支持 {self.dialect}", ErrorCode.UNSUPPORTED_SQL)

                standardized = self._convert_diagnostician_result(result)

                # 标准化数据字段名，统一为CLI可解析的格式
                if standardized.get("success") and standardized.get("data"):
                    data = standardized["data"]
                    data["db_type"] = db_label

                    # 将不同数据库的字段名统一为 bloated_tables
                    if "fragmented_tables" in data and "bloated_tables" not in data:
                        data["bloated_tables"] = data["fragmented_tables"]
                    if "fragmented_tablespaces" in data and "bloated_tables" not in data:
                        data["bloated_tables"] = data["fragmented_tablespaces"]

                    # 统一 total_wasted_space 字段
                    if "total_wasted_space_mb" in data and "total_wasted_space" not in data:
                        wasted_mb = data["total_wasted_space_mb"]
                        if isinstance(wasted_mb, (int, float)):
                            if wasted_mb >= 1024:
                                data["total_wasted_space"] = f"{wasted_mb / 1024:.2f} GB"
                            else:
                                data["total_wasted_space"] = f"{wasted_mb:.2f} MB"
                        else:
                            data["total_wasted_space"] = str(wasted_mb)

                    # 统一 severely_bloated_count
                    if "severely_bloated_count" not in data:
                        data["severely_bloated_count"] = sum(
                            1 for t in data.get("bloated_tables", []) if t.get("priority") == "high"
                        )

                return standardized
            else:
                return create_error_response("膨胀/碎片分析需要诊断器", ErrorCode.UNKNOWN_ERROR)
        except Exception as e:
            logger.error(f"膨胀/碎片分析失败: {e}")
            return create_error_response(str(e), ErrorCode.UNKNOWN_ERROR)

    def analyze_index_usage(self) -> Dict[str, Any]:
        """
        分析索引使用情况

        识别未使用或低效的索引，以及可能缺少索引的表

        返回:
            Dict: 索引使用分析结果
        """
        try:
            if self._diagnostician:
                result = self._diagnostician.analyze_index_usage()
                standardized = self._convert_diagnostician_result(result)

                # 添加数据库类型标签
                if standardized.get("success") and standardized.get("data"):
                    db_label = self.dialect.split("+")[0].title()
                    standardized["data"]["db_type"] = db_label

                return standardized
            else:
                return create_error_response("索引使用分析需要诊断器", ErrorCode.UNKNOWN_ERROR)
        except Exception as e:
            logger.error(f"索引使用分析失败: {e}")
            return create_error_response(str(e), ErrorCode.UNKNOWN_ERROR)

    def analyze_tablespace_fragmentation(self) -> Dict[str, Any]:
        """
        分析Oracle表空间碎片情况

        仅支持Oracle数据库

        返回:
            Dict: 表空间碎片分析结果
        """
        try:
            if "oracle" not in self.dialect:
                return create_error_response(
                    f"表空间碎片分析仅支持Oracle，当前数据库: {self.dialect}", ErrorCode.UNSUPPORTED_SQL
                )

            if self._diagnostician:
                result = self._diagnostician.analyze_tablespace_fragmentation()
                return self._convert_diagnostician_result(result)
            else:
                return create_error_response("表空间碎片分析需要Oracle诊断器", ErrorCode.UNKNOWN_ERROR)
        except Exception as e:
            logger.error(f"表空间碎片分析失败: {e}")
            return create_error_response(str(e), ErrorCode.UNKNOWN_ERROR)
