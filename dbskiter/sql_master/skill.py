"""
sql_master/skill.py
SQL Master Skill 统一入口

文件功能：提供统一的SQL处理API，整合执行、重写、分析的全部功能
主要类：SQLMasterSkill - SQL Master Skill统一入口

核心功能：
1. SQL执行 - 执行SQL并返回结果（带缓存）
2. SQL重写优化 - 生成优化后的SQL
3. SQL质量分析 - 评分和建议
4. 批量SQL处理 - 批量执行和优化
5. 数据分析 - 查询结果分析
6. 智能提示 - SQL补全建议
7. Schema感知 - 基于Schema的优化

使用示例：
    >>> skill = SQLMasterSkill(connector)
    >>> result = skill.execute("SELECT * FROM users LIMIT 10")
    >>> result = skill.rewrite_sql("SELECT * FROM users WHERE id = 1")
    >>> result = skill.analyze_sql_quality("SELECT * FROM users")

版本: 3.0.0（模块化重构版）
作者: AI Assistant
创建时间: 2026-04-23
"""

import warnings
from typing import List, Dict, Any, Optional
from datetime import datetime
import logging

from dbskiter.shared.unified_connector import UnifiedConnector, detect_connector_type
from dbskiter.shared.validators import validate_params, Validator, sanitize_sql

# 导入数据模型
from .models import (
    ErrorCode,
    SQLMasterConfig,
    SQLOptimizationReport,
    SQLAnalysisResult,
    create_success_response,
    create_error_response,
)

# 导入工具类
from .utils import (
    SQLTypeDetector,
    SQLFormatter,
    QueryBuilder,
    ResultProcessor,
    PerformanceTimer,
    SQLAnalyzer,
)

# 导入核心组件
from .executor import SQLExecutor
from .analyzer import DataAnalyzer
from .sql_rewriter_v2 import SQLRewriterV2
from .intelligent_intellisense import SQLIntelliSense
from .schema_aware import SchemaAwareOptimizer
from .cache_manager import SQLCacheManager
from .cache_invalidator import SmartCachedExecutor
from .sql_validator import SQLSyntaxValidator, SQLPreChecker
from .data_transfer import DataExporter, DataImporter

logger = logging.getLogger(__name__)


class SQLMasterSkill:
    """
    SQL Master Skill 统一入口（模块化重构版）

    整合SQL执行、重写、分析的全部功能，提供生产级的SQL处理能力

    核心组件:
        connector: 数据库连接器
        executor: SQL执行器
        rewriter: SQL重写器
        analyzer: 数据分析器
        intellisense: 智能提示
        schema_optimizer: Schema优化器
        cache_manager: 缓存管理器
        smart_executor: 智能缓存执行器

    使用示例:
        >>> skill = SQLMasterSkill(connector)
        >>> result = skill.execute("SELECT * FROM users")
        >>> report = skill.generate_optimization_report([sql1, sql2])
    """

    def __init__(
        self,
        connector: UnifiedConnector,
        config: Optional[SQLMasterConfig] = None,
        enable_rewriter: bool = True,
        enable_analyzer: bool = True,
        enable_intellisense: bool = True,
        enable_cache: bool = True,
        max_rows: int = 1000,
        cache_size: int = 1000,
        cache_ttl: int = 300
    ):
        """
        初始化 SQL Master Skill

        参数:
            connector: UnifiedConnector 实例
            config: SQL Master配置，None使用默认配置
            enable_rewriter: 是否启用SQL重写
            enable_analyzer: 是否启用数据分析
            enable_intellisense: 是否启用智能提示
            enable_cache: 是否启用缓存
            max_rows: 最大返回行数
            cache_size: 缓存最大条目数
            cache_ttl: 缓存默认过期时间（秒）
        """
        self.connector = connector
        self.config = config or SQLMasterConfig(
            enable_rewriter=enable_rewriter,
            enable_analyzer=enable_analyzer,
            enable_intellisense=enable_intellisense,
            enable_cache=enable_cache,
            max_rows=max_rows,
            cache_size=cache_size,
            cache_ttl=cache_ttl
        )

        # 初始化工具类
        self.sql_detector = SQLTypeDetector()
        self.sql_formatter = SQLFormatter()
        self.query_builder = QueryBuilder()
        self.result_processor = ResultProcessor()
        self.sql_analyzer = SQLAnalyzer()

        # 初始化核心组件
        self.executor = SQLExecutor(connector)
        self.rewriter = SQLRewriterV2(connector) if self.config.enable_rewriter else None
        self.analyzer = DataAnalyzer(connector) if self.config.enable_analyzer else None
        self.schema_optimizer = SchemaAwareOptimizer(connector)
        self.intellisense = SQLIntelliSense(self.schema_optimizer.schema_cache) if self.config.enable_intellisense else None

        # SQL预检查器
        self.sql_validator = SQLSyntaxValidator()
        self.sql_prechecker = SQLPreChecker(self.sql_validator)

        # 缓存管理器
        if self.config.enable_cache:
            self.cache_manager = SQLCacheManager(
                max_size=self.config.cache_size,
                default_ttl=self.config.cache_ttl
            )
            self.smart_executor = SmartCachedExecutor(
                self.executor,
                self.cache_manager,
                enable_cache=True,
                enable_auto_invalidate=True
            )
        else:
            self.cache_manager = None
            self.smart_executor = None

        # 检测连接器类型
        self._is_unified = isinstance(connector, UnifiedConnector)
        self._is_jdbc = "+jdbc" in connector.dialect if hasattr(connector, 'dialect') else False

        # 初始化数据导入导出器
        self.data_exporter = DataExporter(connector)
        self.data_importer = DataImporter(connector)

        logger.info(f"SQLMasterSkill 初始化完成 (dialect={connector.dialect})")

    # ==================== SQL执行 ====================

    @validate_params(sql=Validator.not_empty_string)
    def execute(
        self,
        sql: str,
        params: Optional[Dict[str, Any]] = None,
        limit: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        执行SQL语句

        参数:
            sql: SQL语句
            params: SQL参数
            limit: 返回行数限制

        返回:
            Dict: 执行结果
        """
        sanitized_sql = sanitize_sql(sql)
        logger.info(f"执行SQL: {sanitized_sql}")

        # SQL语法预检查
        check_result = self.sql_prechecker.check(sql, allow_write=True)
        if not check_result["can_execute"]:
            logger.warning(f"SQL预检查失败: {check_result['error']}")
            return create_error_response(
                check_result["error"],
                ErrorCode.SYNTAX_ERROR
            )

        try:
            # 添加LIMIT限制
            if limit and limit > 0:
                sql = self._add_limit(sql, limit)
            elif self.config.max_rows > 0:
                sql = self._add_limit(sql, self.config.max_rows)

            # 执行SQL - 将 dict 参数转换为 tuple
            with PerformanceTimer() as timer:
                if self.config.enable_cache and self.smart_executor:
                    result = self.smart_executor.execute(sql, params, use_cache=True)
                else:
                    # 转换参数格式
                    if params and isinstance(params, dict):
                        # 将 dict 转换为 tuple，按顺序提取值
                        tuple_params = tuple(params.values())
                    else:
                        tuple_params = params
                    result = self.executor.execute(sql, tuple_params)

            return create_success_response({
                "sql": sanitized_sql,
                "row_count": len(result.rows) if hasattr(result, 'rows') else 0,
                "columns": result.columns if hasattr(result, 'columns') else [],
                "rows": result.rows if hasattr(result, 'rows') else [],
                "execution_time": timer.elapsed,
            }, "SQL执行成功")

        except Exception as e:
            logger.error(f"SQL执行失败: {e}")
            return create_error_response(
                str(e),
                ErrorCode.EXECUTION_FAILED,
                {"sql": sanitized_sql}
            )

    @validate_params(sqls=Validator.not_empty_list)
    def execute_batch(
        self,
        sqls: List[str],
        params_list: Optional[List[Dict[str, Any]]] = None
    ) -> List[Dict[str, Any]]:
        """批量执行SQL"""
        results = []
        for i, sql in enumerate(sqls):
            params = params_list[i] if params_list and i < len(params_list) else None
            result = self.execute(sql, params)
            results.append(result)
        return results

    def _add_limit(self, sql: str, limit: int) -> str:
        """为SQL添加LIMIT限制"""
        sql_upper = sql.strip().upper()
        if sql_upper.startswith("SELECT") and "LIMIT" not in sql_upper:
            if self.connector.dialect in ("mysql", "mysql+pymysql"):
                return f"{sql} LIMIT {limit}"
            elif self.connector.dialect == "postgresql":
                return f"{sql} LIMIT {limit}"
            elif self.connector.dialect == "oracle":
                return f"SELECT * FROM ({sql}) WHERE ROWNUM <= {limit}"
        return sql

    # ==================== SQL重写优化 ====================

    @validate_params(sql=Validator.not_empty_string)
    def rewrite_sql(self, sql: str) -> Dict[str, Any]:
        """重写SQL以优化性能"""
        if not self.config.enable_rewriter or not self.rewriter:
            return {"status": "disabled", "message": "SQL重写已禁用"}

        sanitized_sql = sanitize_sql(sql)
        logger.info(f"重写SQL: {sanitized_sql}")

        try:
            result = self.rewriter.rewrite(sql)

            return create_success_response({
                "original_sql": sql,
                "can_optimize": result.can_rewrite,
                "optimized_sql": result.best_rewrite if result.best_rewrite else sql,
                "suggestions_count": len(result.suggestions),
                "suggestions": [
                    {
                        "type": s.rewrite_type.value if hasattr(s.rewrite_type, 'value') else str(s.rewrite_type),
                        "impact": s.impact,
                        "reason": s.reason,
                        "confidence": s.confidence,
                        "rewritten_sql": s.rewritten_sql if s.rewritten_sql else None
                    }
                    for s in result.suggestions
                ]
            }, "SQL重写完成")

        except Exception as e:
            logger.error(f"SQL重写失败: {e}")
            return create_error_response(
                str(e),
                ErrorCode.REWRITE_FAILED,
                {"sql": sanitized_sql}
            )

    @validate_params(sqls=Validator.not_empty_list)
    def rewrite_batch(self, sqls: List[str]) -> List[Dict[str, Any]]:
        """批量重写SQL"""
        return [self.rewrite_sql(sql) for sql in sqls]

    # ==================== SQL分析 ====================

    @validate_params(sql=Validator.not_empty_string)
    def analyze_sql_quality(self, sql: str) -> Dict[str, Any]:
        """分析SQL质量"""
        logger.info(f"分析SQL质量: {sanitize_sql(sql)}")

        try:
            # 使用工具类分析
            complexity = self.sql_analyzer.analyze_complexity(sql)
            cost = self.sql_analyzer.estimate_cost(sql)

            # 提取表名
            tables = self.sql_formatter.extract_tables(sql)

            # 计算分数
            score = max(0, 100 - complexity["score"])

            result = SQLAnalysisResult(
                sql=sql,
                sql_type=self.sql_detector.detect(sql),
                score=score,
                issues=[],
                suggestions=[],
                complexity=complexity["level"]
            )

            # 添加建议
            if complexity["level"] == "high":
                result.issues.append("SQL复杂度过高")
                result.suggestions.append("考虑简化查询或拆分为多个简单查询")

            if self.sql_detector.is_ddl(sql):
                result.issues.append("DDL语句可能影响生产环境")
                result.suggestions.append("DDL语句请在测试环境验证后再执行")

            return create_success_response(result.to_dict(), "SQL质量分析完成")

        except Exception as e:
            logger.error(f"SQL质量分析失败: {e}")
            return create_error_response(
                str(e),
                ErrorCode.ANALYSIS_FAILED
            )

    @validate_params(sql=Validator.not_empty_string)
    def analyze_data(self, sql: str) -> Dict[str, Any]:
        """分析查询数据"""
        if not self.config.enable_analyzer or not self.analyzer:
            return {"status": "disabled", "message": "数据分析已禁用"}

        logger.info(f"分析数据: {sanitize_sql(sql)}")

        try:
            result = self.execute(sql)
            if not result.get("success"):
                return result

            data = result.get("data", {})
            rows = data.get("rows", [])
            columns = data.get("columns", [])

            if not rows:
                return create_success_response({
                    "row_count": 0,
                    "columns": columns,
                    "summary": "无数据"
                }, "数据分析完成")

            # 使用数据分析器
            analysis = self.analyzer.analyze(rows, columns)

            return create_success_response({
                "row_count": len(rows),
                "columns": columns,
                "analysis": analysis if hasattr(analysis, 'to_dict') else analysis
            }, "数据分析完成")

        except Exception as e:
            logger.error(f"数据分析失败: {e}")
            return create_error_response(
                str(e),
                ErrorCode.ANALYSIS_FAILED
            )

    # ==================== 智能提示 ====================

    def get_suggestions(self, sql: str, cursor_position: Optional[int] = None) -> Dict[str, Any]:
        """获取SQL补全建议"""
        if not self.config.enable_intellisense or not self.intellisense:
            return create_success_response({
                "partial_sql": sql,
                "suggestions": []
            }, "智能补全已禁用")

        try:
            suggestions = self.intellisense.get_suggestions(sql, cursor_position)
            # 将 SemanticSuggestion 对象转换为字典
            suggestions_dict = [s.to_dict() for s in suggestions]
            return create_success_response({
                "partial_sql": sql,
                "suggestions": suggestions_dict
            }, "获取补全建议成功")
        except Exception as e:
            logger.error(f"获取建议失败: {e}")
            return create_error_response(
                str(e),
                ErrorCode.ANALYSIS_FAILED
            )

    # ==================== Schema信息 ====================

    def get_schema_info(self, table_name: str) -> Dict[str, Any]:
        """获取表结构信息"""
        try:
            return self.schema_optimizer.get_table_schema(table_name)
        except Exception as e:
            logger.error(f"获取Schema失败: {e}")
            return create_error_response(
                str(e),
                ErrorCode.NOT_FOUND
            )

    def list_tables(self) -> List[str]:
        """列出所有表"""
        try:
            return self.schema_optimizer.list_tables()
        except Exception as e:
            logger.error(f"获取表列表失败: {e}")
            return []

    # ==================== 报告生成 ====================

    @validate_params(sqls=Validator.not_empty_list)
    def generate_optimization_report(self, sqls: List[str]) -> Dict[str, Any]:
        """生成SQL优化报告"""
        logger.info(f"生成优化报告，SQL数量: {len(sqls)}")

        report = SQLOptimizationReport(total_sqls=len(sqls))

        for sql in sqls:
            rewrite_result = self.rewrite_sql(sql) if self.config.enable_rewriter else None
            quality_result = self.analyze_sql_quality(sql)

            if rewrite_result and rewrite_result.get("success"):
                data = rewrite_result.get("data", {})
                if data.get("can_optimize"):
                    report.can_optimize += 1
                    report.total_suggestions += data.get("suggestions_count", 0)

                    for suggestion in data.get("suggestions", []):
                        impact = suggestion.get("impact", "low")
                        if impact == "high":
                            report.high_impact += 1
                        elif impact == "medium":
                            report.medium_impact += 1
                        else:
                            report.low_impact += 1

                    report.optimized_sqls.append({
                        "original": sql,
                        "optimized": data.get("optimized_sql", sql),
                        "suggestions": data.get("suggestions", [])
                    })

        return create_success_response(report.to_dict(), "优化报告生成完成")

    # ==================== 配置管理 ====================

    def get_config(self) -> Dict[str, Any]:
        """获取当前配置"""
        return self.config.to_dict()

    # ==================== 缓存管理 ====================

    def get_cache_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        if not self.config.enable_cache or not self.cache_manager:
            return {"status": "disabled", "message": "缓存已禁用"}

        stats = self.cache_manager.get_stats()

        if self.smart_executor:
            invalidator_stats = self.smart_executor.get_invalidator_stats()
            stats["invalidator"] = invalidator_stats

        return create_success_response(stats, "缓存统计")

    def clear_cache(self) -> Dict[str, Any]:
        """清除缓存"""
        if not self.config.enable_cache or not self.cache_manager:
            return {"status": "disabled", "message": "缓存已禁用"}

        count = self.cache_manager.invalidate()
        return create_success_response(
            {"cleared_entries": count},
            f"已清除 {count} 条缓存"
        )

    # ==================== 数据导入导出 ====================

    def export_table(
        self,
        table_name: str,
        output_path: str,
        format: str = "csv",
        where: Optional[str] = None,
        limit: Optional[int] = None,
        columns: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        导出表数据

        参数:
            table_name: 表名
            output_path: 输出文件路径
            format: 导出格式 (csv, json, sql)
            where: WHERE条件
            limit: 限制行数
            columns: 指定列

        返回:
            Dict: 导出结果

        使用示例:
            >>> skill.export_table("users", "users.csv", format="csv")
            >>> skill.export_table("users", "users.json", format="json", limit=1000)
        """
        try:
            result = self.data_exporter.export_table(
                table_name=table_name,
                output_path=output_path,
                format=format,
                where=where,
                limit=limit,
                columns=columns
            )
            return result
        except Exception as e:
            logger.error(f"导出表数据失败: {e}")
            return create_error_response(
                f"导出失败: {str(e)}",
                ErrorCode.EXECUTION_ERROR
            )

    def export_query(
        self,
        sql: str,
        output_path: str,
        format: str = "csv"
    ) -> Dict[str, Any]:
        """
        导出查询结果

        参数:
            sql: SQL查询语句
            output_path: 输出文件路径
            format: 导出格式

        返回:
            Dict: 导出结果
        """
        try:
            result = self.data_exporter.export_query(
                sql=sql,
                output_path=output_path,
                format=format
            )
            return result
        except Exception as e:
            logger.error(f"导出查询结果失败: {e}")
            return create_error_response(
                f"导出失败: {str(e)}",
                ErrorCode.EXECUTION_ERROR
            )

    def export_table_streaming(
        self,
        table_name: str,
        output_path: str,
        format: str = "csv",
        where: Optional[str] = None,
        batch_size: int = 10000,
        columns: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        流式导出大表数据（分批导出，避免内存溢出）

        参数:
            table_name: 表名
            output_path: 输出文件路径
            format: 导出格式 (csv, sql)
            where: WHERE条件
            batch_size: 每批导出的行数
            columns: 指定列

        返回:
            Dict: 导出结果

        使用示例:
            >>> skill.export_table_streaming("large_table", "output.csv", batch_size=5000)
        """
        try:
            result = self.data_exporter.export_table_streaming(
                table_name=table_name,
                output_path=output_path,
                format=format,
                where=where,
                batch_size=batch_size,
                columns=columns
            )
            return result
        except Exception as e:
            logger.error(f"流式导出失败: {e}")
            return create_error_response(
                f"流式导出失败: {str(e)}",
                ErrorCode.EXECUTION_ERROR
            )

    def import_csv(
        self,
        input_path: str,
        table_name: str,
        columns: Optional[List[str]] = None,
        batch_size: int = 1000,
        skip_header: bool = True
    ) -> Dict[str, Any]:
        """
        从CSV文件导入数据

        参数:
            input_path: CSV文件路径
            table_name: 目标表名
            columns: 指定列名
            batch_size: 批量插入大小
            skip_header: 是否跳过表头

        返回:
            Dict: 导入结果

        使用示例:
            >>> skill.import_csv("users.csv", "users")
            >>> skill.import_csv("data.csv", "orders", columns=["id", "name"])
        """
        try:
            result = self.data_importer.import_csv(
                input_path=input_path,
                table_name=table_name,
                columns=columns,
                batch_size=batch_size,
                skip_header=skip_header
            )
            return result
        except Exception as e:
            logger.error(f"导入CSV失败: {e}")
            return create_error_response(
                f"导入失败: {str(e)}",
                ErrorCode.EXECUTION_ERROR
            )

    def import_json(
        self,
        input_path: str,
        table_name: str,
        batch_size: int = 1000
    ) -> Dict[str, Any]:
        """
        从JSON文件导入数据

        参数:
            input_path: JSON文件路径
            table_name: 目标表名
            batch_size: 批量插入大小

        返回:
            Dict: 导入结果
        """
        try:
            result = self.data_importer.import_json(
                input_path=input_path,
                table_name=table_name,
                batch_size=batch_size
            )
            return result
        except Exception as e:
            logger.error(f"导入JSON失败: {e}")
            return create_error_response(
                f"导入失败: {str(e)}",
                ErrorCode.EXECUTION_ERROR
            )

    def import_sql(self, input_path: str) -> Dict[str, Any]:
        """
        从SQL文件导入数据

        参数:
            input_path: SQL文件路径

        返回:
            Dict: 导入结果
        """
        try:
            result = self.data_importer.import_sql(input_path)
            return result
        except Exception as e:
            logger.error(f"导入SQL失败: {e}")
            return create_error_response(
                f"导入失败: {str(e)}",
                ErrorCode.EXECUTION_ERROR
            )

    def close(self):
        """关闭Skill，释放资源"""
        logger.info("关闭 SQLMasterSkill...")

        if self.config.enable_cache and self.cache_manager:
            self.cache_manager.invalidate()
            logger.info("缓存已清除")

        logger.info("SQLMasterSkill 已关闭")


# 版本兼容说明：
# 本模块已统一为 SQLMasterSkill，不再区分V2/V3
