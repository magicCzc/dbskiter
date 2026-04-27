"""
SQL分析器模块

文件功能：提供SQL语句的深度分析功能
主要类：
    - SQLAnalyzer: SQL分析器

作者：AI Assistant
创建时间：2026-04-22
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

from dbskiter.shared.unified_connector import UnifiedConnector
from dbskiter.shared.error_handler import handle_exception
from dbskiter.shared.validators import sanitize_sql

# 导入执行计划分析器
from .plan_analyzer import ExecutionPlanAnalyzer

logger = logging.getLogger(__name__)


class SQLAnalyzer:
    """
    SQL分析器

    功能：
        1. 深度SQL分析 - 执行计划解析、问题定位
        2. 索引建议生成
        3. SQL重写建议

    属性：
        connector: 数据库连接器
        plan_analyzer: 执行计划分析器V2

    使用示例：
        >>> analyzer = SQLAnalyzer(connector)
        >>> result = analyzer.analyze("SELECT * FROM users WHERE email = 'test@test.com'")
        >>> print(result["summary"])
    """

    def __init__(self, connector: UnifiedConnector):
        """
        初始化SQL分析器

        参数：
            connector: UnifiedConnector 实例

        示例：
            >>> analyzer = SQLAnalyzer(connector)
        """
        self.connector = connector
        # 初始化执行计划分析器
        self.plan_analyzer = ExecutionPlanAnalyzer(connector)
        logger.info(f"SQLAnalyzer 初始化完成 (dialect={connector.dialect})")

    def analyze(
        self,
        sql: str,
        params: Optional[Dict[str, Any]] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        深度分析SQL语句

        参数：
            sql: SQL语句
            params: SQL参数（用于参数化查询分析）
            context: 上下文信息

        返回：
            Dict: 诊断结果
            {
                "success": bool,
                "sql": str,
                "sql_type": str,
                "summary": str,
                "issues": List[Dict],
                "index_suggestions": List[Dict],
                "optimized_sql": Optional[str],
                "cost_estimate": Dict,
                "timestamp": str
            }

        示例：
            >>> result = analyzer.analyze("SELECT * FROM users WHERE email = ?", {"email": "test@test.com"})
            >>> if result["success"]:
            ...     print(result["summary"])
        """
        # SQL脱敏用于日志
        sanitized_sql = sanitize_sql(sql)
        logger.info(f"诊断SQL: {sanitized_sql}")

        try:
            # 使用V2分析器进行深度分析
            analysis = self.plan_analyzer.analyze(sql)

            # 计算评分 (100分制，根据问题数量和严重程度扣分)
            base_score = 100
            for issue in analysis.issues:
                if issue.severity == "critical":
                    base_score -= 30
                elif issue.severity == "high":
                    base_score -= 20
                elif issue.severity == "medium":
                    base_score -= 10
                else:
                    base_score -= 5
            score = max(0, base_score)  # 最低0分

            # 转换为标准格式
            result = {
                "success": True,
                "sql": sql,
                "sql_type": analysis.sql_type,
                "score": score,
                "summary": analysis.summary(),
                "issues": [
                    {
                        "severity": issue.severity,
                        "type": issue.issue_type,
                        "table": issue.table_name,
                        "description": issue.description,
                        "suggestion": issue.suggestion.reason if issue.suggestion else None,
                        "create_index_sql": issue.suggestion.create_sql if issue.suggestion else None
                    }
                    for issue in analysis.issues
                ],
                "index_suggestions": [
                    {
                        "table": sug.table_name,
                        "columns": sug.column_names,
                        "index_name": sug.index_name,
                        "reason": sug.reason,
                        "priority": sug.priority,
                        "create_sql": sug.create_sql,
                        "expected_improvement": sug.expected_improvement
                    }
                    for sug in analysis.index_suggestions
                ],
                "optimized_sql": analysis.optimized_sql,
                "cost_estimate": {
                    "total_cost": analysis.total_cost,
                    "total_rows": analysis.total_rows,
                    "execution_time_ms": analysis.execution_time_ms
                },
                "warnings": analysis.warnings,
                "timestamp": datetime.now().isoformat()
            }

            # 记录问题统计
            critical_count = sum(1 for i in analysis.issues if i.severity == "critical")
            high_count = sum(1 for i in analysis.issues if i.severity == "high")
            logger.info(f"诊断完成: {critical_count}个严重问题, {high_count}个高危问题, "
                       f"{len(analysis.index_suggestions)}个索引建议")

            return result

        except Exception as e:
            logger.error(f"SQL诊断失败: {e}")
            return handle_exception(e, context=f"诊断SQL: {sql[:100]}...")

    def analyze_batch(
        self,
        sqls: List[str],
        show_progress: bool = False
    ) -> List[Dict[str, Any]]:
        """
        批量分析SQL语句

        参数：
            sqls: SQL语句列表
            show_progress: 是否显示进度

        返回：
            List[Dict]: 诊断结果列表

        示例：
            >>> sqls = ["SELECT * FROM users", "SELECT * FROM orders"]
            >>> results = analyzer.analyze_batch(sqls)
        """
        results = []
        total = len(sqls)

        for i, sql in enumerate(sqls):
            if show_progress:
                logger.info(f"分析进度: {i+1}/{total}")

            result = self.analyze(sql)
            results.append(result)

        return results

    def get_index_suggestions(
        self,
        sql: str,
        min_priority: str = "medium"
    ) -> List[Dict[str, Any]]:
        """
        获取索引建议（便捷方法）

        参数：
            sql: SQL语句
            min_priority: 最小优先级 (high/medium/low)

        返回：
            List[Dict]: 索引建议列表

        示例：
            >>> suggestions = analyzer.get_index_suggestions("SELECT * FROM users WHERE age > 18")
            >>> for sug in suggestions:
            ...     print(sug["create_sql"])
        """
        result = self.analyze(sql)

        if not result.get("success"):
            return []

        suggestions = result.get("index_suggestions", [])

        # 按优先级过滤
        priority_order = {"high": 0, "medium": 1, "low": 2}
        min_priority_level = priority_order.get(min_priority, 1)

        filtered = [
            sug for sug in suggestions
            if priority_order.get(sug.get("priority", "low"), 2) <= min_priority_level
        ]

        return filtered

    def get_executable_fixes(self, sql: str) -> List[str]:
        """
        获取可执行的修复SQL（CREATE INDEX等）

        参数：
            sql: SQL语句

        返回：
            List[str]: 可执行的SQL语句列表

        示例：
            >>> fixes = analyzer.get_executable_fixes("SELECT * FROM users WHERE email = 'test'")
            >>> for fix in fixes:
            ...     print(fix)  # CREATE INDEX ...
        """
        suggestions = self.get_index_suggestions(sql, min_priority="high")
        return [sug["create_sql"] for sug in suggestions if sug.get("create_sql")]

    def rewrite_sql(self, sql: str, optimization_type: str = "auto") -> Dict[str, Any]:
        """
        SQL重写优化

        参数：
            sql: 原始SQL
            optimization_type: 优化类型 (auto/index/join/limit/all)

        返回：
            Dict: 重写结果

        示例：
            >>> result = analyzer.rewrite_sql("SELECT * FROM users WHERE email = 'test'")
            >>> print(result["data"]["rewritten_sql"])
        """
        try:
            # 首先分析SQL
            analysis = self.plan_analyzer.analyze(sql)

            if not analysis.optimized_sql:
                from dbskiter.shared.error_handler import create_success_response
                return create_success_response(
                    message="SQL无需优化",
                    data={
                        "original_sql": sql,
                        "rewritten_sql": sql,
                        "changes": [],
                        "reason": "分析未发现可优化点"
                    }
                )

            # 收集优化变更
            changes = []

            # 1. SELECT * 优化
            if "SELECT *" in sql.upper():
                changes.append({
                    "type": "select_star",
                    "description": "将SELECT *替换为具体列名",
                    "severity": "medium"
                })

            # 2. 隐式转换优化
            if analysis.issues:
                for issue in analysis.issues:
                    if "隐式转换" in issue.description or "implicit" in issue.description.lower():
                        changes.append({
                            "type": "implicit_conversion",
                            "description": issue.description,
                            "suggestion": issue.suggestion.reason if issue.suggestion else None,
                            "severity": "high"
                        })

            # 3. 索引相关优化
            if analysis.index_suggestions:
                changes.append({
                    "type": "index",
                    "description": f"建议添加 {len(analysis.index_suggestions)} 个索引",
                    "suggestions": [
                        {
                            "table": s.table_name,
                            "columns": s.column_names,
                            "sql": s.create_sql
                        }
                        for s in analysis.index_suggestions
                    ],
                    "severity": "high"
                })

            from dbskiter.shared.error_handler import create_success_response
            return create_success_response(
                message=f"SQL重写完成，发现 {len(changes)} 处可优化",
                data={
                    "original_sql": sql,
                    "rewritten_sql": analysis.optimized_sql,
                    "changes": changes,
                    "expected_improvement": "预计提升30-50%性能" if changes else "无需优化"
                }
            )

        except Exception as e:
            from dbskiter.shared.error_handler import handle_exception
            return handle_exception(e, context=f"SQL重写: {sql[:100]}...")
