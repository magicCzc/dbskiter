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
from .audit_storage import SQLAuditStorage, SQLAuditRecord

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

        # 初始化审计日志存储
        self.audit_storage = SQLAuditStorage()

        logger.info(f"SQLMasterSkill 初始化完成 (dialect={connector.dialect})")

    def close(self):
        """
        关闭资源
        
        关闭所有数据库连接和存储资源
        """
        if hasattr(self, 'audit_storage') and self.audit_storage:
            self.audit_storage.close()
            logger.info("SQLMasterSkill 资源已关闭")

    # ==================== SQL执行 ====================

    @validate_params(sql=Validator.not_empty_string)
    def execute(
        self,
        sql: str,
        params: Optional[Dict[str, Any]] = None,
        limit: Optional[int] = None,
        allow_write: bool = True,
        force: bool = False
    ) -> Dict[str, Any]:
        """
        执行SQL语句

        参数:
            sql: SQL语句
            params: SQL参数
            limit: 返回行数限制
            allow_write: 是否允许写操作（默认True，设为False开启只读模式）
            force: 是否强制执行危险操作（默认False，设为True可执行CRITICAL级别操作）

        返回:
            Dict: 执行结果
            
        示例:
            >>> # 普通查询
            >>> result = skill.execute("SELECT * FROM users")
            >>> # 只读模式
            >>> result = skill.execute("SELECT * FROM users", allow_write=False)
            >>> # 强制执行危险操作
            >>> result = skill.execute("DROP TABLE temp_table", force=True)
        """
        sanitized_sql = sanitize_sql(sql)
        logger.info(f"执行SQL: {sanitized_sql}")

        # SQL语法预检查（包含危险操作检测）
        check_result = self.sql_prechecker.check(sql, allow_write=allow_write, force=force)
        
        # 处理检查结果
        if not check_result["can_execute"]:
            logger.warning(f"SQL预检查失败: {check_result['error']}")
            return create_error_response(
                check_result["error"],
                ErrorCode.SYNTAX_ERROR,
                {
                    "risk_level": check_result.get("risk_level"),
                    "risk_description": check_result.get("risk_description"),
                    "requires_confirmation": check_result.get("requires_confirmation"),
                    "requires_force": check_result.get("requires_force"),
                }
            )
        
        # 高风险操作警告（不阻止执行，但返回警告信息）
        if check_result.get("requires_confirmation") and not force:
            logger.warning(f"高风险操作: {check_result.get('warning')}")

        try:
            # 添加LIMIT限制
            if limit and limit > 0:
                sql = self._add_limit(sql, limit)
            elif self.config.max_rows > 0:
                sql = self._add_limit(sql, self.config.max_rows)

            # 记录审计日志（危险操作）
            risk_level = check_result.get("risk_level", "SAFE")

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

            # 计算执行时间和行数
            execution_time_ms = timer.elapsed * 1000
            row_count = len(result.rows) if hasattr(result, 'rows') else 0

            # 记录审计日志（所有操作都记录，危险操作额外标记）
            if risk_level in ("CRITICAL", "HIGH", "MEDIUM"):
                self._log_audit(
                    operation="SQL_EXECUTE",
                    sql=sanitized_sql,
                    risk_level=risk_level,
                    risk_description=check_result.get("risk_description"),
                    force_used=force,
                    read_only_mode=not allow_write,
                    execution_time_ms=execution_time_ms,
                    row_count=row_count,
                    success=True
                )

            # 记录成功执行
            logger.info(
                f"SQL执行成功: {sanitized_sql[:50]}... "
                f"风险等级={risk_level}, "
                f"影响行数={row_count}"
            )

            return create_success_response({
                "sql": sanitized_sql,
                "row_count": row_count,
                "columns": result.columns if hasattr(result, 'columns') else [],
                "rows": result.rows if hasattr(result, 'rows') else [],
                "execution_time": timer.elapsed,
                "risk_level": risk_level,
            }, "SQL执行成功")

        except Exception as e:
            logger.error(f"SQL执行失败: {e}")
            # 记录失败审计
            if risk_level in ("CRITICAL", "HIGH", "MEDIUM"):
                self._log_audit(
                    operation="SQL_EXECUTE_FAILED",
                    sql=sanitized_sql,
                    risk_level=risk_level,
                    risk_description=check_result.get("risk_description"),
                    force_used=force,
                    read_only_mode=not allow_write,
                    error=str(e),
                    success=False
                )
            return create_error_response(
                str(e),
                ErrorCode.EXECUTION_FAILED,
                {"sql": sanitized_sql}
            )

    def _log_audit(
        self,
        operation: str,
        sql: str,
        risk_level: str = "SAFE",
        risk_description: Optional[str] = None,
        force_used: bool = False,
        read_only_mode: bool = False,
        error: Optional[str] = None,
        execution_time_ms: Optional[float] = None,
        row_count: Optional[int] = None,
        success: bool = True
    ) -> None:
        """
        记录审计日志

        参数:
            operation: 操作类型
            sql: SQL语句
            risk_level: 风险等级
            risk_description: 风险描述
            force_used: 是否使用了force参数
            read_only_mode: 是否为只读模式
            error: 错误信息（如果有）
            execution_time_ms: 执行耗时（毫秒）
            row_count: 影响行数
            success: 是否执行成功
        """
        import hashlib
        from datetime import datetime

        # 生成SQL指纹（用于标识相同的SQL）
        sql_fingerprint = hashlib.md5(sql.encode()).hexdigest()[:16]

        # 创建审计记录
        record = SQLAuditRecord(
            timestamp=datetime.now().isoformat(),
            operation=operation,
            sql_fingerprint=sql_fingerprint,
            sql_preview=sql[:100] + "..." if len(sql) > 100 else sql,
            risk_level=risk_level,
            risk_description=risk_description,
            force_used=force_used,
            read_only_mode=read_only_mode,
            dialect=getattr(self.connector, 'dialect', 'unknown'),
            success=success,
            error=error,
            execution_time_ms=execution_time_ms,
            row_count=row_count
        )

        # 持久化到数据库
        try:
            if hasattr(self, 'audit_storage') and self.audit_storage:
                self.audit_storage.save_record(record)
        except Exception as e:
            logger.error(f"审计日志保存失败: {e}")

        # 同时输出到日志
        log_message = (
            f"审计日志: {record.operation} | "
            f"风险={record.risk_level} | "
            f"SQL={record.sql_preview[:50]}"
        )
        if risk_level in ("CRITICAL", "HIGH"):
            logger.warning(log_message)
        else:
            logger.info(log_message)

    @validate_params(sqls=Validator.not_empty_list)
    def execute_batch(
        self,
        sqls: List[str],
        params_list: Optional[List[Dict[str, Any]]] = None,
        allow_write: bool = True,
        force: bool = False,
        stop_on_error: bool = True
    ) -> List[Dict[str, Any]]:
        """
        批量执行SQL

        参数:
            sqls: SQL语句列表
            params_list: 参数列表（与sqls一一对应）
            allow_write: 是否允许写操作（默认True）
            force: 是否强制执行危险操作（默认False）
            stop_on_error: 遇到错误时是否停止（默认True）

        返回:
            List[Dict[str, Any]]: 执行结果列表

        示例:
            >>> sqls = ["SELECT * FROM users", "UPDATE users SET status=1 WHERE id=1"]
            >>> results = skill.execute_batch(sqls, allow_write=True)
            >>> for result in results:
            ...     print(result['success'])
        """
        results = []
        for i, sql in enumerate(sqls):
            params = params_list[i] if params_list and i < len(params_list) else None
            result = self.execute(sql, params, allow_write=allow_write, force=force)
            results.append(result)

            # 如果遇到错误且设置了stop_on_error，则停止执行
            if stop_on_error and not result.get("success"):
                logger.warning(f"批量执行在第{i+1}条SQL处停止: {result.get('error')}")
                break

        return results

    # ==================== 审计日志查询 ====================

    def get_audit_records(
        self,
        risk_level: Optional[str] = None,
        hours: Optional[int] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        查询审计日志记录

        参数:
            risk_level: 风险等级筛选（CRITICAL/HIGH/MEDIUM/SAFE）
            hours: 最近多少小时
            limit: 返回数量限制

        返回:
            List[Dict]: 审计记录列表

        示例:
            >>> records = skill.get_audit_records(risk_level="HIGH", hours=24)
            >>> for record in records:
            ...     print(f"{record['timestamp']}: {record['sql_preview']}")
        """
        if not hasattr(self, 'audit_storage') or not self.audit_storage:
            return []

        records = self.audit_storage.query_records(
            risk_level=risk_level,
            hours=hours,
            limit=limit
        )
        return [r.to_dict() for r in records]

    def get_audit_statistics(self, days: int = 7) -> Dict[str, Any]:
        """
        获取审计统计信息

        参数:
            days: 统计最近多少天

        返回:
            Dict: 统计信息

        示例:
            >>> stats = skill.get_audit_statistics(days=7)
            >>> print(f"总操作数: {stats['total_records']}")
            >>> print(f"成功率: {stats['success_rate']}%")
        """
        if not hasattr(self, 'audit_storage') or not self.audit_storage:
            return {
                "period_days": days,
                "total_records": 0,
                "risk_level_distribution": {},
                "operation_distribution": {},
                "success_rate": 0.0,
                "force_used_count": 0,
            }

        return self.audit_storage.get_statistics(days=days)

    def cleanup_audit_logs(self, days: int = 30) -> int:
        """
        清理过期审计日志

        参数:
            days: 保留最近多少天的记录

        返回:
            int: 删除的记录数

        示例:
            >>> deleted = skill.cleanup_audit_logs(days=30)
            >>> print(f"清理了 {deleted} 条过期记录")
        """
        if not hasattr(self, 'audit_storage') or not self.audit_storage:
            return 0

        return self.audit_storage.cleanup_old_records(days=days)

    def _add_limit(self, sql: str, limit: int) -> str:
        """为SQL添加LIMIT限制"""
        sql_upper = sql.strip().upper()
        if sql_upper.startswith("SELECT") and "LIMIT" not in sql_upper:
            if self.connector.dialect in ("mysql", "mysql+pymysql"):
                return f"{sql} LIMIT {limit}"
            elif "postgresql" in self.connector.dialect:
                return f"{sql} LIMIT {limit}"
            elif "oracle" in self.connector.dialect:
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

    # ==================== AI上下文构建 ====================

    def build_ai_context(
        self,
        skill_result: Dict[str, Any],
        scenario: str = "sql_execute"
    ) -> Dict[str, Any]:
        """
        构建AI分析上下文

        参数:
            skill_result: Skill返回的原始结果
            scenario: 场景标识 (sql_execute/sql_rewrite/sql_analyze/data_analysis/sql_complete/schema_query)

        返回:
            Dict[str, Any]: AI上下文
        """
        from dbskiter.shared.ai_context import AIContextBuilder

        builder = AIContextBuilder(
            dialect=self.connector.dialect if hasattr(self.connector, 'dialect') else 'unknown',
            database_name=getattr(self.connector, 'database', ''),
        )
        builder.detect_business_context(self.connector)

        data = skill_result.get("data", {})

        raw_metrics = self._extract_raw_metrics_for_ai(data, scenario)
        rule_flags = self._extract_rule_flags_for_ai(data, scenario)
        context = builder.build_database_profile(self.connector)
        reference_values = self._build_reference_values(scenario)
        ai_hints = self._build_ai_hints(scenario, data)

        return {
            "raw_metrics": raw_metrics,
            "rule_flags": rule_flags,
            "context": context,
            "reference_values": reference_values,
            "ai_hints": ai_hints,
        }

    def _extract_raw_metrics_for_ai(self, data: Dict[str, Any], scenario: str) -> Dict[str, Any]:
        """提取原始指标"""
        metrics = {}

        # 提取关键字段
        key_fields = ["execution_time", "rows_affected", "rows_returned", "sql", "result", "error", "status"]
        for key in key_fields:
            if key in data:
                metrics[key] = data[key]

        # 场景特定提取
        if scenario == "sql_execute":
            for key in ["execution_time", "rows_affected", "rows_returned", "sql", "result", "error_message"]:
                if key in data:
                    metrics[key] = data[key]
        elif scenario == "sql_rewrite":
            for key in ["original_sql", "rewritten_sql", "improvements", "estimated_gain", "optimization_type"]:
                if key in data:
                    metrics[key] = data[key]
        elif scenario == "sql_analyze":
            for key in ["issues", "suggestions", "complexity_score", "quality_score", "risk_level"]:
                if key in data:
                    metrics[key] = data[key]
        elif scenario == "schema_query":
            for key in ["schema", "tables", "columns", "indexes"]:
                if key in data:
                    metrics[key] = data[key]
        elif scenario == "data_export":
            for key in ["export_size", "row_count", "file_path", "format"]:
                if key in data:
                    metrics[key] = data[key]
        elif scenario == "data_import":
            for key in ["import_size", "row_count", "success_count", "error_count", "file_path"]:
                if key in data:
                    metrics[key] = data[key]

        if not metrics:
            metrics = data

        return metrics

    def _extract_rule_flags_for_ai(self, data: Dict[str, Any], scenario: str) -> Dict[str, Any]:
        """提取规则标记"""
        flags = {}

        # SQL执行时间标记
        execution_time = data.get("execution_time", 0)
        if isinstance(execution_time, (int, float)):
            if execution_time > 10000:  # 10秒
                flags["very_slow_execution"] = {"flagged": True, "level": "critical", "reason": f"执行时间过长: {execution_time}ms"}
            elif execution_time > 1000:  # 1秒
                flags["slow_execution"] = {"flagged": True, "level": "high", "reason": f"执行时间较长: {execution_time}ms"}
            elif execution_time > 100:
                flags["moderate_execution"] = {"flagged": True, "level": "medium", "reason": f"执行时间中等: {execution_time}ms"}

        # SQL问题标记
        issues = data.get("issues", [])
        if isinstance(issues, list):
            critical_issues = [i for i in issues if i.get("severity") == "critical"]
            high_issues = [i for i in issues if i.get("severity") == "high"]
            if critical_issues:
                flags["critical_sql_issues"] = {"flagged": True, "level": "critical", "reason": f"发现 {len(critical_issues)} 个严重问题"}
            if high_issues:
                flags["high_sql_issues"] = {"flagged": True, "level": "high", "reason": f"发现 {len(high_issues)} 个高危问题"}

        # 错误标记
        if data.get("status") == "error" or data.get("error"):
            flags["execution_error"] = {"flagged": True, "level": "critical", "reason": "SQL执行出错"}

        # 大数据量标记
        rows_affected = data.get("rows_affected", 0)
        if isinstance(rows_affected, int) and rows_affected > 100000:
            flags["large_operation"] = {"flagged": True, "level": "warning", "reason": f"影响行数过多: {rows_affected}"}

        return {"_disclaimer": "规则初筛结果仅供参考", "flags": flags}

    def _build_reference_values(self, scenario: str) -> Dict[str, Any]:
        """构建参考基线"""
        refs = {
            "execution_time": {"excellent": "<100ms", "good": "100-500ms", "moderate": "500-1000ms", "slow": ">1000ms"},
            "complexity_score": {"simple": "<10", "moderate": "10-30", "complex": ">30"},
            "rows_affected": {"small": "<1000", "medium": "1000-10000", "large": ">10000"},
        }
        return refs

    def _build_ai_hints(self, scenario: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """构建AI提示"""
        hints = {"focus_areas": [], "related_commands": []}
        db_name = getattr(self.connector, 'database', '')

        execution_time = data.get("execution_time", 0)
        issues = data.get("issues", [])

        if scenario == "sql_execute":
            hints["focus_areas"] = ["execution_plan", "index_usage", "lock_wait"]

            if isinstance(execution_time, (int, float)) and execution_time > 1000:
                hints["focus_areas"].append("performance_optimization")

            hints["related_commands"] = [
                f"dbskiter --database={db_name} sql analyze '<sql>'",
                f"dbskiter --database={db_name} diagnose sql '<sql>'",
            ]

        elif scenario == "sql_rewrite":
            hints["focus_areas"] = ["performance_optimization", "index_recommendation", "query_structure"]
            hints["related_commands"] = [
                f"dbskiter --database={db_name} diagnose recommend-indexes '<sql>'",
            ]

        elif scenario == "sql_analyze":
            hints["focus_areas"] = ["query_optimization", "anti_patterns", "best_practices"]

            if isinstance(issues, list) and issues:
                performance_issues = [i for i in issues if "performance" in i.get("category", "").lower()]
                if performance_issues:
                    hints["focus_areas"].append("performance_tuning")

            hints["related_commands"] = [
                f"dbskiter --database={db_name} sql rewrite '<sql>'",
                f"dbskiter --database={db_name} audit sql '<sql>'",
            ]

        elif scenario == "schema_query":
            hints["focus_areas"] = ["table_structure", "index_design", "data_types"]
            hints["related_commands"] = [
                f"dbskiter --database={db_name} diagnose table <table_name>",
            ]

        elif scenario == "data_export":
            hints["focus_areas"] = ["export_performance", "data_integrity", "file_format"]

        elif scenario == "data_import":
            hints["focus_areas"] = ["import_performance", "data_validation", "error_handling"]

        return hints


