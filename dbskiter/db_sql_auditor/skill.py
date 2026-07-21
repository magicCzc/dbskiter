"""
db_sql_auditor/skill.py
SQL审核 Skill 统一入口

文件功能：提供完整的SQL审核能力，支持MySQL/Oracle/PostgreSQL
主要类：SQLAuditorSkill - SQL审核技能统一入口

支持的数据库：
    - MySQL: 完整支持
    - Oracle: 完整支持
    - PostgreSQL: 完整支持

核心功能：
1. SQL规范审核 - 检查SQL是否符合规范
2. 性能审核 - 评估SQL性能风险
3. 安全审核 - 检查SQL安全风险
4. DDL影响分析 - 分析DDL变更影响
5. 批量审核 - 批量审核SQL列表
6. 自定义规则 - 支持自定义审核规则

使用示例：
    >>> skill = SQLAuditorSkill(connector)
    >>> result = skill.audit_sql("SELECT * FROM users WHERE id = 1")
    >>> print(f"审核评分: {result['data']['score']}")
    >>> impact = skill.analyze_ddl_impact("ALTER TABLE users ADD COLUMN age INT")

版本: 3.0.0（模块化重构版）
作者: Magiczc
创建时间: 2026-04-23
"""

import logging
import uuid
from typing import Dict, Any, List, Optional
from datetime import datetime

from dbskiter.shared.unified_connector import UnifiedConnector
from dbskiter.shared.validators import validate_params, Validator

# 导入数据模型
from .models import (
    ErrorCode,
    AuditLevel,
    AuditType,
    AuditConfig,
    AuditResult,
    AuditRule,
    BatchAuditResult,
    create_success_response,
    create_error_response,
)

# 导入工具类
from .utils import (
    SQLParser,
    RuleEngine,
    ScoreCalculator,
    IssueAggregator,
    SQLNormalizer,
    AuditReporter,
)

# 导入子模块
from .analyzers import get_ddl_analyzer
from .intelligent_optimizer import IntelligentOptimizer

logger = logging.getLogger(__name__)


class SQLAuditorSkill:
    """
    SQL审核 Skill（模块化重构版）

    功能：
        1. SQL规范审核 - 检查SQL是否符合规范
        2. 性能审核 - 评估SQL性能风险
        3. 安全审核 - 检查SQL安全风险
        4. DDL影响分析 - 分析DDL变更影响
        5. 批量审核 - 批量审核SQL列表
        6. 自定义规则 - 支持自定义审核规则

    支持的数据库：
        - MySQL
        - Oracle
        - PostgreSQL
    """

    def __init__(
        self,
        connector: UnifiedConnector,
        config: Optional[AuditConfig] = None
    ):
        """
        初始化SQL审核 Skill

        参数:
            connector: UnifiedConnector 实例
            config: 审核配置，None使用默认配置
        """
        self.connector = connector
        self.dialect = connector.dialect.lower()
        self.config = config or AuditConfig()

        # 初始化工具类
        self.parser = SQLParser()
        self.rule_engine = RuleEngine()
        self.score_calculator = ScoreCalculator()
        self.issue_aggregator = IssueAggregator()
        self.normalizer = SQLNormalizer()
        self.reporter = AuditReporter()

        # 初始化DDL分析器
        self.ddl_analyzer = None
        if connector:
            try:
                self.ddl_analyzer = get_ddl_analyzer(self.dialect, connector)
            except ValueError as e:
                logger.warning(f"DDL分析器初始化失败: {e}")

        # 初始化智能优化器
        self.intelligent_optimizer = IntelligentOptimizer(connector)

        logger.info(f"SQLAuditorSkill 初始化完成 (dialect={self.dialect})")

    # ==================== 核心审核API ====================

    @validate_params(sql=Validator.not_empty_string)
    def audit_sql(
        self,
        sql: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        审核单条SQL（已接入多步骤计时）

        参数:
            sql: SQL语句
            context: 上下文信息

        返回:
            Dict: 审核结果，包含 _execution_time 步骤耗时
        """
        from dbskiter.shared.execution_timer import ExecutionTimer
        timer = ExecutionTimer().start()

        try:
            with timer.step("detect_sql_type", "检测 SQL 类型"):
                audit_id = str(uuid.uuid4())[:8]
                sql_type = self.parser.detect_sql_type(sql)

                result = AuditResult(
                    audit_id=audit_id,
                    sql_content=sql,
                    sql_type=sql_type,
                    audit_time=datetime.now()
                )

            with timer.step("execute_audit", "执行 SQL 审核"):
                self._execute_audit(sql, result)

            with timer.step("finalize_result", "计算统计和评分"):
                self._finalize_result(result)

            response = create_success_response(result.to_dict(), "SQL审核完成")
            response["_execution_time"] = timer.to_summary()
            return response

        except Exception as e:
            logger.error(f"SQL审核失败: {e}")
            return create_error_response(
                str(e),
                ErrorCode.AUDIT_FAILED,
                {"sql": sql[:100] if len(sql) > 100 else sql}
            )

    def audit_sql_list(
        self,
        sql_list: List[str],
        show_progress: bool = False
    ) -> Dict[str, Any]:
        """
        批量审核SQL

        参数:
            sql_list: SQL语句列表
            show_progress: 是否显示进度

        返回:
            Dict: 批量审核结果
        """
        batch_id = str(uuid.uuid4())[:8]
        results = []
        success_count = 0
        failed_count = 0

        for i, sql in enumerate(sql_list):
            if show_progress:
                logger.info(f"审核进度: {i+1}/{len(sql_list)}")

            try:
                response = self.audit_sql(sql)
                if response.get("success"):
                    results.append(AuditResult(**response["data"]))
                    success_count += 1
                else:
                    failed_count += 1
            except Exception as e:
                logger.error(f"审核SQL失败: {e}")
                failed_count += 1

        # 生成汇总
        summary = self.issue_aggregator.aggregate_results(results)

        batch_result = BatchAuditResult(
            batch_id=batch_id,
            total_count=len(sql_list),
            success_count=success_count,
            failed_count=failed_count,
            results=results,
            summary=summary
        )

        return create_success_response(batch_result.to_dict(), "批量审核完成")

    # ==================== DDL影响分析 ====================

    def analyze_ddl_impact(self, ddl_sql: str) -> Dict[str, Any]:
        """
        分析DDL变更影响

        参数:
            ddl_sql: DDL语句

        返回:
            Dict: 影响分析结果
        """
        try:
            if not self.ddl_analyzer:
                return create_error_response(
                    f"当前数据库方言 '{self.dialect}' 不支持DDL影响分析",
                    ErrorCode.DDL_ANALYSIS_FAILED
                )

            impact = self.ddl_analyzer.analyze_impact(ddl_sql)
            return create_success_response(impact.to_dict(), "DDL影响分析完成")

        except ConnectionError as e:
            logger.error(f"DDL分析连接失败: {e}")
            return create_error_response(
                f"数据库连接失败: {e}",
                ErrorCode.DDL_ANALYSIS_FAILED
            )
        except PermissionError as e:
            logger.error(f"DDL分析权限不足: {e}")
            return create_error_response(
                f"权限不足: {e}",
                ErrorCode.PERMISSION_DENIED
            )
        except Exception as e:
            logger.error(f"DDL影响分析失败: {e}")
            return create_error_response(
                str(e),
                ErrorCode.DDL_ANALYSIS_FAILED
            )

    # ==================== 规则管理 ====================

    def get_rules(self) -> List[Dict[str, Any]]:
        """获取所有审核规则"""
        rules = self.rule_engine.get_all_rules()
        return [rule.to_dict() for rule in rules]

    def enable_rule(self, rule_id: str) -> Dict[str, Any]:
        """启用规则"""
        success = self.rule_engine.enable_rule(rule_id)
        if success:
            return create_success_response(None, f"规则 {rule_id} 已启用")
        return create_error_response(
            f"规则 {rule_id} 不存在",
            ErrorCode.RULE_NOT_FOUND
        )

    def disable_rule(self, rule_id: str) -> Dict[str, Any]:
        """禁用规则"""
        success = self.rule_engine.disable_rule(rule_id)
        if success:
            return create_success_response(None, f"规则 {rule_id} 已禁用")
        return create_error_response(
            f"规则 {rule_id} 不存在",
            ErrorCode.RULE_NOT_FOUND
        )

    def add_custom_rule(self, rule_data: Dict[str, Any]) -> Dict[str, Any]:
        """添加自定义规则"""
        try:
            rule = AuditRule(
                rule_id=rule_data["rule_id"],
                rule_name=rule_data["rule_name"],
                audit_type=AuditType(rule_data["audit_type"]),
                level=AuditLevel(rule_data["level"]),
                description=rule_data.get("description", ""),
                enabled=rule_data.get("enabled", True),
                custom_config=rule_data.get("custom_config", {})
            )
            self.rule_engine.add_custom_rule(rule)
            return create_success_response(None, f"规则 {rule.rule_id} 已添加")
        except Exception as e:
            return create_error_response(
                f"添加规则失败: {e}",
                ErrorCode.INVALID_PARAM
            )

    # ==================== 报告生成 ====================

    def generate_report(
        self,
        sql_list: List[str],
        report_title: str = "SQL审核报告"
    ) -> Dict[str, Any]:
        """
        生成审核报告

        参数:
            sql_list: SQL语句列表
            report_title: 报告标题

        返回:
            Dict: 审核报告
        """
        try:
            # 执行批量审核
            batch_result = self.audit_sql_list(sql_list)

            if not batch_result.get("success"):
                return batch_result

            data = batch_result["data"]

            # 生成报告内容
            report = {
                "title": report_title,
                "batch_id": data["batch_id"],
                "summary": data["summary"],
                "top_issues": self.issue_aggregator.get_top_issues(
                    [AuditResult(**r) for r in data["results"]],
                    limit=10
                ),
                "generated_at": datetime.now().isoformat()
            }

            return create_success_response(report, "审核报告生成完成")

        except Exception as e:
            logger.error(f"生成报告失败: {e}")
            return create_error_response(
                str(e),
                ErrorCode.UNKNOWN_ERROR
            )

    # ==================== 工具方法 ====================

    def get_sql_fingerprint(self, sql: str) -> str:
        """获取SQL指纹"""
        return self.normalizer.generate_fingerprint(sql)

    def extract_sql_info(self, sql: str) -> Dict[str, Any]:
        """提取SQL信息"""
        return {
            "sql_type": self.parser.detect_sql_type(sql).value,
            "tables": self.parser.extract_tables(sql),
            "columns": self.parser.extract_columns(sql),
            "has_where": self.parser.has_where_clause(sql),
            "has_limit": self.parser.has_limit_clause(sql),
            "fingerprint": self.normalizer.generate_fingerprint(sql)
        }

    def close(self):
        """关闭Skill，释放资源"""
        logger.info("关闭 SQLAuditorSkill...")
        if self.ddl_analyzer:
            self.ddl_analyzer = None
        logger.info("SQLAuditorSkill 已关闭")

    # ==================== 内部方法 ====================

    def _execute_audit(self, sql: str, result: AuditResult):
        """执行审核"""
        # 获取启用的规则
        enabled_rules = self.rule_engine.get_enabled_rules()

        # 根据配置过滤规则
        if not self.config.enable_syntax_check:
            enabled_rules = [r for r in enabled_rules if r.audit_type != AuditType.SYNTAX]
        if not self.config.enable_performance_check:
            enabled_rules = [r for r in enabled_rules if r.audit_type != AuditType.PERFORMANCE]
        if not self.config.enable_security_check:
            enabled_rules = [r for r in enabled_rules if r.audit_type != AuditType.SECURITY]
        if not self.config.enable_style_check:
            enabled_rules = [r for r in enabled_rules if r.audit_type != AuditType.STYLE]
        if not self.config.enable_ddl_check:
            enabled_rules = [r for r in enabled_rules if r.audit_type != AuditType.DDL]

        # 执行规则检查
        for rule in enabled_rules:
            if len(result.issues) >= self.config.max_issues_per_sql:
                break

            issue = self.rule_engine.execute_rule(rule.rule_id, sql)
            if issue:
                # 检查最小级别
                level_order = {
                    AuditLevel.CRITICAL: 0,
                    AuditLevel.HIGH: 1,
                    AuditLevel.MEDIUM: 2,
                    AuditLevel.LOW: 3,
                    AuditLevel.INFO: 4,
                }
                if level_order.get(issue.level, 4) <= level_order.get(self.config.min_audit_level, 4):
                    result.issues.append(issue)

    def _finalize_result(self, result: AuditResult):
        """完成结果计算"""
        # 计算统计
        result.total_issues = len(result.issues)
        result.critical_count = sum(1 for i in result.issues if i.level == AuditLevel.CRITICAL)
        result.high_count = sum(1 for i in result.issues if i.level == AuditLevel.HIGH)
        result.medium_count = sum(1 for i in result.issues if i.level == AuditLevel.MEDIUM)
        result.low_count = sum(1 for i in result.issues if i.level == AuditLevel.LOW)

        # 计算评分
        result.score = self.score_calculator.calculate_score(result.issues)
        result.passed = self.score_calculator.calculate_pass_status(
            result.score,
            result.critical_count
        )


    # ==================== 智能优化API ====================

    def optimize_sql(
        self,
        sql: str,
        schema_info: Optional[Dict[str, Any]] = None,
        table_stats: Optional[Dict[str, Any]] = None,
        existing_indexes: Optional[List[Dict]] = None,
        execution_plan: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        智能优化SQL

        参数:
            sql: SQL语句
            schema_info: 表结构信息
            table_stats: 表统计信息
            existing_indexes: 已有索引列表
            execution_plan: 执行计划

        返回:
            Dict: 优化结果
        """
        try:
            result = self.intelligent_optimizer.optimize(
                sql=sql,
                schema_info=schema_info,
                table_stats=table_stats,
                existing_indexes=existing_indexes,
                execution_plan=execution_plan
            )

            return create_success_response(
                data=result,
                message=f"SQL优化完成，发现{len(result['recommendations'])}条优化建议"
            )
        except Exception as e:
            logger.error(f"SQL优化失败: {e}")
            return create_error_response(
                f"优化失败: {str(e)}",
                ErrorCode.UNKNOWN_ERROR
            )

    def recommend_indexes(
        self,
        sql: str,
        schema_info: Dict[str, Any],
        existing_indexes: Optional[List[Dict]] = None
    ) -> Dict[str, Any]:
        """
        推荐索引

        参数:
            sql: SQL语句
            schema_info: 表结构信息
            existing_indexes: 已有索引列表

        返回:
            Dict: 索引推荐结果
        """
        try:
            recommendations = self.intelligent_optimizer.index_recommender.recommend_indexes(
                sql, schema_info, existing_indexes
            )

            return create_success_response(
                data={
                    "recommendations": [
                        {
                            "table": rec.table_name,
                            "index_name": rec.index_name,
                            "columns": rec.columns,
                            "index_type": rec.index_type,
                            "reason": rec.reason,
                            "estimated_benefit": rec.estimated_benefit,
                            "estimated_cost": rec.estimated_cost,
                            "priority": rec.priority.value
                        }
                        for rec in recommendations
                    ],
                    "total": len(recommendations)
                },
                message=f"推荐{len(recommendations)}个索引"
            )
        except Exception as e:
            logger.error(f"索引推荐失败: {e}")
            return create_error_response(
                f"推荐失败: {str(e)}",
                ErrorCode.UNKNOWN_ERROR
            )

    def analyze_execution_plan(
        self,
        execution_plan: str
    ) -> Dict[str, Any]:
        """
        分析执行计划

        参数:
            execution_plan: 执行计划输出

        返回:
            Dict: 分析结果
        """
        try:
            analysis = self.intelligent_optimizer.plan_analyzer.analyze(execution_plan)

            return create_success_response(
                data=analysis,
                message=f"执行计划分析完成，发现{len(analysis['issues'])}个问题"
            )
        except Exception as e:
            logger.error(f"执行计划分析失败: {e}")
            return create_error_response(
                f"分析失败: {str(e)}",
                ErrorCode.UNKNOWN_ERROR
            )

    def estimate_cost(
        self,
        sql: str,
        table_stats: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        估算SQL执行成本

        参数:
            sql: SQL语句
            table_stats: 表统计信息

        返回:
            Dict: 成本估算结果
        """
        try:
            cost = self.intelligent_optimizer.cost_estimator.estimate(sql, table_stats)

            return create_success_response(
                data={
                    "io_cost": cost.io_cost,
                    "cpu_cost": cost.cpu_cost,
                    "memory_cost": cost.memory_cost,
                    "total_cost": cost.total_cost,
                    "estimated_time_ms": cost.estimated_time_ms,
                    "estimated_rows": cost.estimated_rows
                },
                message="成本估算完成"
            )
        except Exception as e:
            logger.error(f"成本估算失败: {e}")
            return create_error_response(
                f"估算失败: {str(e)}",
                ErrorCode.UNKNOWN_ERROR
            )

    def compare_sql_costs(
        self,
        original_sql: str,
        optimized_sql: str,
        table_stats: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        对比两条SQL的成本

        参数:
            original_sql: 原始SQL
            optimized_sql: 优化后SQL
            table_stats: 表统计信息

        返回:
            Dict: 成本对比结果
        """
        try:
            original_cost = self.intelligent_optimizer.cost_estimator.estimate(
                original_sql, table_stats
            )
            optimized_cost = self.intelligent_optimizer.cost_estimator.estimate(
                optimized_sql, table_stats
            )
            comparison = self.intelligent_optimizer.cost_estimator.compare_costs(
                original_cost, optimized_cost
            )

            return create_success_response(
                data=comparison,
                message=f"成本对比完成，优化效果: {comparison['improvement_level']}"
            )
        except Exception as e:
            logger.error(f"成本对比失败: {e}")
            return create_error_response(
                f"对比失败: {str(e)}",
                ErrorCode.UNKNOWN_ERROR
            )

    def rewrite_sql(
        self,
        sql: str,
        schema_info: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        重写SQL

        参数:
            sql: SQL语句
            schema_info: 表结构信息

        返回:
            Dict: 重写结果
        """
        try:
            result = self.intelligent_optimizer.query_rewriter.rewrite(sql, schema_info)

            return create_success_response(
                data=result,
                message=f"SQL重写完成，{result['changes_made']}处改进"
            )
        except Exception as e:
            logger.error(f"SQL重写失败: {e}")
            return create_error_response(
                f"重写失败: {str(e)}",
                ErrorCode.UNKNOWN_ERROR
            )

    # ==================== AI上下文构建 ====================

    def build_ai_context(
        self,
        skill_result: Dict[str, Any],
        scenario: str = "sql_audit"
    ) -> Dict[str, Any]:
        """
        构建AI分析上下文

        参数:
            skill_result: Skill返回的原始结果
            scenario: 场景标识 (sql_audit/ddl_impact/optimization)

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

        inspection_trace = self._build_inspection_trace(scenario, data)

        return {
            "raw_metrics": raw_metrics,
            "rule_flags": rule_flags,
            "context": context,
            "reference_values": reference_values,
            "ai_hints": ai_hints,
            "inspection_trace": inspection_trace,
        }

    def _build_inspection_trace(
        self,
        scenario: str,
        data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        构建SQL审核透明度追踪信息

        参数:
            scenario: 场景标识
            data: Skill返回的data字段

        返回:
            Dict[str, Any]: 追踪信息
        """
        trace = {
            "scenario": scenario,
            "metrics_checked": [],
            "data_sources": [],
            "confidence": "high",
            "notes": []
        }

        if scenario == "sql_audit":
            trace["metrics_checked"] = [
                {"name": "syntax_check", "description": "语法检查", "source": "SQL解析器"},
                {"name": "rule_violations", "description": "规则违规", "source": "规则引擎"},
                {"name": "performance_risk", "description": "性能风险", "source": "EXPLAIN分析"},
                {"name": "security_risk", "description": "安全风险", "source": "安全规则库"},
            ]
            trace["data_sources"] = ["sql_parser", "rule_engine", "EXPLAIN", "security_rule_library"]

        elif scenario == "ddl_impact":
            trace["metrics_checked"] = [
                {"name": "table_size", "description": "表大小", "source": "information_schema"},
                {"name": "lock_duration", "description": "锁持有时间估算", "source": "经验模型"},
                {"name": "rebuild_cost", "description": "重建成本", "source": "表结构分析"},
                {"name": "dependent_objects", "description": "依赖对象", "source": "information_schema"},
            ]
            trace["data_sources"] = ["information_schema", "empirical_model"]
            trace["notes"].append("DDL影响分析基于估算，实际影响可能因数据量和并发度而异")

        elif scenario == "optimization":
            trace["metrics_checked"] = [
                {"name": "execution_plan", "description": "执行计划", "source": "EXPLAIN"},
                {"name": "index_recommendation", "description": "索引推荐", "source": "成本模型"},
                {"name": "rewrite_suggestion", "description": "改写建议", "source": "规则引擎"},
                {"name": "statistics_accuracy", "description": "统计信息准确度", "source": "information_schema"},
            ]
            trace["data_sources"] = ["EXPLAIN", "cost_model", "rule_engine", "information_schema"]

        else:
            trace["metrics_checked"] = [
                {"name": "general_audit", "description": "通用审核指标", "source": "自动检测"}
            ]
            trace["data_sources"] = ["auto_detection"]
            trace["notes"].append(f"未定义场景 '{scenario}' 的详细追踪，使用通用指标")

        return trace

    def _extract_raw_metrics_for_ai(self, data: Dict[str, Any], scenario: str) -> Dict[str, Any]:
        """提取原始指标"""
        metrics = {}

        # 提取关键字段
        key_fields = ["violations", "suggestions", "impact_analysis", "audit_result", "score", "summary"]
        for key in key_fields:
            if key in data:
                metrics[key] = data[key]

        # 场景特定提取
        if scenario == "sql_audit":
            for key in ["sql", "violations", "suggestions", "score", "risk_level", "compliance_status"]:
                if key in data:
                    metrics[key] = data[key]
        elif scenario == "ddl_impact":
            for key in ["ddl_statement", "affected_tables", "affected_rows", "estimated_duration", "rollback_plan", "risk_assessment"]:
                if key in data:
                    metrics[key] = data[key]
        elif scenario == "file_audit":
            for key in ["file_path", "total_statements", "violations_count", "audit_summary"]:
                if key in data:
                    metrics[key] = data[key]

        if not metrics:
            metrics = data

        return metrics

    def _extract_rule_flags_for_ai(self, data: Dict[str, Any], scenario: str) -> Dict[str, Any]:
        """提取规则标记"""
        flags = {}

        violations = data.get("violations", [])
        if isinstance(violations, list):
            # 严重违规
            critical = [v for v in violations if v.get("severity") == "error"]
            if critical:
                flags["critical_violations"] = {"flagged": True, "level": "critical", "reason": f"发现 {len(critical)} 个严重违规"}

            # 警告违规
            warnings = [v for v in violations if v.get("severity") == "warning"]
            if warnings:
                flags["warning_violations"] = {"flagged": True, "level": "warning", "reason": f"发现 {len(warnings)} 个警告违规"}

        # 评分标记
        score = data.get("score", 100)
        if isinstance(score, (int, float)):
            if score < 60:
                flags["poor_sql_quality"] = {"flagged": True, "level": "critical", "reason": f"SQL质量评分过低: {score}"}
            elif score < 80:
                flags["fair_sql_quality"] = {"flagged": True, "level": "warning", "reason": f"SQL质量评分一般: {score}"}

        # DDL影响标记
        if scenario == "ddl_impact":
            impact = data.get("impact_analysis", {})
            if isinstance(impact, dict):
                risk_level = impact.get("risk_level", "low")
                if risk_level == "high":
                    flags["high_ddl_risk"] = {"flagged": True, "level": "critical", "reason": "DDL操作风险高"}
                elif risk_level == "medium":
                    flags["medium_ddl_risk"] = {"flagged": True, "level": "warning", "reason": "DDL操作风险中等"}

        return {"_disclaimer": "规则初筛结果仅供参考", "flags": flags}

    def _build_reference_values(self, scenario: str) -> Dict[str, Any]:
        """构建参考基线"""
        refs = {
            "violation_severity": {"error": "必须修复", "warning": "建议修复", "info": "参考"},
            "sql_quality_score": {"excellent": "90-100", "good": "80-89", "fair": "60-79", "poor": "<60"},
            "ddl_risk_level": {"low": "低风险", "medium": "中风险", "high": "高风险"},
        }
        return refs

    def _build_ai_hints(self, scenario: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """构建AI提示"""
        hints = {"focus_areas": [], "related_commands": []}
        db_name = getattr(self.connector, 'database', '')

        violations = data.get("violations", [])
        score = data.get("score", 100)

        if scenario == "sql_audit":
            hints["focus_areas"] = ["sql_standards", "performance_optimization", "security_practices"]

            if isinstance(score, (int, float)):
                if score >= 90:
                    hints["focus_areas"].append("sql_best_practices")
                elif score >= 80:
                    hints["focus_areas"].append("minor_optimizations")
                elif score >= 60:
                    hints["focus_areas"].append("significant_improvements_needed")
                else:
                    hints["focus_areas"].append("critical_sql_rewrites_required")

            if isinstance(violations, list) and violations:
                security_issues = [v for v in violations if "security" in v.get("category", "").lower()]
                if security_issues:
                    hints["focus_areas"].append("security_vulnerabilities")

            hints["related_commands"] = [
                f"dbskiter --database={db_name} sql rewrite '<sql>'",
                f"dbskiter --database={db_name} diagnose sql '<sql>'",
            ]

        elif scenario == "ddl_impact":
            hints["focus_areas"] = ["schema_changes", "downtime_estimation", "rollback_plan", "data_migration"]

            impact = data.get("impact_analysis", {})
            if isinstance(impact, dict):
                if impact.get("requires_downtime"):
                    hints["focus_areas"].append("maintenance_window_planning")
                if impact.get("affected_rows", 0) > 1000000:
                    hints["focus_areas"].append("large_table_alteration_strategy")

            hints["related_commands"] = [
                f"dbskiter --database={db_name} diagnose table <table_name>",
                f"dbskiter --database={db_name} inspector run --type storage",
            ]

        elif scenario == "file_audit":
            hints["focus_areas"] = ["batch_sql_review", "standards_compliance", "code_quality_gates"]
            hints["related_commands"] = [
                f"dbskiter --database={db_name} audit file <file_path>",
            ]

        return hints


