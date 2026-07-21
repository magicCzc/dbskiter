"""
智能SQL优化器

文件功能：提供智能SQL优化能力，包括：
    - 查询重写优化
    - 索引推荐
    - 执行计划分析
    - 成本估算
    - 多数据库适配

主要类：
    - QueryRewriter: 查询重写器
    - IndexRecommender: 索引推荐器
    - CostEstimator: 成本估算器
    - IntelligentOptimizer: 智能优化器统一入口

作者: Magiczc
创建时间: 2026-04-24
版本: 1.0.0
"""

import re
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import logging

# 导入执行计划分析器
try:
    from dbskiter.db_diagnose.analyzers.plan_analyzer import ExecutionPlanAnalyzer
except ImportError:
    ExecutionPlanAnalyzer = None

logger = logging.getLogger(__name__)


class OptimizationType(Enum):
    """优化类型"""
    REWRITE = "rewrite"           # 重写优化
    INDEX = "index"               # 索引优化
    HINT = "hint"                 # 提示优化
    STRUCTURE = "structure"       # 结构调整
    PARTITION = "partition"       # 分区优化


class OptimizationPriority(Enum):
    """优化优先级"""
    CRITICAL = "critical"         # 关键
    HIGH = "high"                 # 高
    MEDIUM = "medium"             # 中
    LOW = "low"                   # 低


@dataclass
class OptimizationSuggestion:
    """优化建议"""
    suggestion_id: str
    optimization_type: OptimizationType
    priority: OptimizationPriority
    original_sql: str
    optimized_sql: Optional[str]
    description: str
    benefit: str
    risk: str
    estimated_improvement: str
    implementation_cost: str
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class IndexRecommendation:
    """索引推荐"""
    table_name: str
    index_name: str
    columns: List[str]
    index_type: str  # BTREE, HASH, GIN, etc.
    reason: str
    estimated_benefit: str
    estimated_cost: str
    priority: OptimizationPriority


@dataclass
class ExecutionPlanNode:
    """执行计划节点"""
    node_id: int
    operation: str
    table_name: Optional[str]
    access_type: Optional[str]
    rows_examined: int
    rows_sent: int
    cost: float
    key_used: Optional[str]
    extra_info: Dict[str, Any]
    children: List['ExecutionPlanNode'] = field(default_factory=list)


@dataclass
class CostEstimate:
    """成本估算"""
    io_cost: float
    cpu_cost: float
    memory_cost: float
    total_cost: float
    estimated_time_ms: float
    estimated_rows: int


class QueryRewriter:
    """
    查询重写器

    功能：
    1. SELECT * 重写为具体列
    2. 隐式转换消除
    3. OR条件重写为UNION
    4. 子查询优化
    5. 冗余条件消除

    使用示例：
        >>> rewriter = QueryRewriter()
        >>> result = rewriter.rewrite("SELECT * FROM users WHERE id = 1")
        >>> print(result['optimized_sql'])
    """

    def __init__(self):
        """初始化查询重写器"""
        self.rewrite_rules = [
            self._rewrite_select_star,
            self._rewrite_implicit_conversion,
            self._rewrite_or_to_union,
            self._rewrite_subquery,
            self._eliminate_redundant_conditions,
        ]

    def rewrite(self, sql: str, schema_info: Optional[Dict] = None) -> Dict[str, Any]:
        """
        重写SQL查询

        参数:
            sql: 原始SQL
            schema_info: 表结构信息

        返回:
            Dict: 重写结果
        """
        original_sql = sql
        optimized_sql = sql
        suggestions = []

        for rule in self.rewrite_rules:
            try:
                result = rule(optimized_sql, schema_info)
                if result['changed']:
                    optimized_sql = result['sql']
                    suggestions.append(result['suggestion'])
            except Exception as e:
                logger.warning(f"重写规则 {rule.__name__} 失败: {e}")

        return {
            "changed": optimized_sql != original_sql,
            "original_sql": original_sql,
            "optimized_sql": optimized_sql if optimized_sql != original_sql else None,
            "sql": optimized_sql,
            "changes_made": len(suggestions),
            "suggestions": suggestions,
            "improvement_estimate": self._estimate_improvement(suggestions)
        }

    def _rewrite_select_star(
        self,
        sql: str,
        schema_info: Optional[Dict]
    ) -> Dict[str, Any]:
        """重写SELECT *为具体列"""
        pattern = r'SELECT\s+\*\s+FROM\s+(\w+)'
        match = re.search(pattern, sql, re.IGNORECASE)

        if not match:
            return {"changed": False, "sql": sql, "suggestion": None}

        table_name = match.group(1)

        # 如果有schema信息，获取列列表
        if schema_info and table_name in schema_info:
            columns = schema_info[table_name].get('columns', [])
            if columns:
                column_list = ', '.join([col['name'] for col in columns[:10]])  # 最多10列
                optimized = re.sub(
                    r'SELECT\s+\*',
                    f'SELECT {column_list}',
                    sql,
                    flags=re.IGNORECASE
                )

                return {
                    "changed": True,
                    "sql": optimized,
                    "suggestion": {
                        "type": "SELECT_STAR",
                        "description": "将SELECT *重写为具体列名",
                        "benefit": "减少网络传输，提高查询效率",
                        "risk": "需要维护列列表"
                    }
                }

        return {"changed": False, "sql": sql, "suggestion": None}

    def _rewrite_implicit_conversion(
        self,
        sql: str,
        schema_info: Optional[Dict]
    ) -> Dict[str, Any]:
        """消除隐式类型转换"""
        # 检测常见的隐式转换模式
        patterns = [
            (r"(\w+)\s*=\s*'(\d+)'", r"\1 = \2"),  # 字符串数字比较
            (r"(\w+)\s+LIKE\s+'(\d+)'", r"\1 = \2"),  # LIKE用于数字
        ]

        optimized = sql
        changed = False

        for pattern, replacement in patterns:
            new_sql = re.sub(pattern, replacement, optimized, flags=re.IGNORECASE)
            if new_sql != optimized:
                optimized = new_sql
                changed = True

        if changed:
            return {
                "changed": True,
                "sql": optimized,
                "suggestion": {
                    "type": "IMPLICIT_CONVERSION",
                    "description": "消除隐式类型转换",
                    "benefit": "允许使用索引，提高查询性能",
                    "risk": "无"
                }
            }

        return {"changed": False, "sql": sql, "suggestion": None}

    def _rewrite_or_to_union(
        self,
        sql: str,
        schema_info: Optional[Dict]
    ) -> Dict[str, Any]:
        """将OR条件重写为UNION"""
        # 检测OR条件
        or_pattern = r'WHERE\s+(.+?)\s+OR\s+(.+)'
        match = re.search(or_pattern, sql, re.IGNORECASE)

        if not match:
            return {"changed": False, "sql": sql, "suggestion": None}

        # 简单的OR重写（实际应该更复杂）
        condition1 = match.group(1).strip()
        condition2 = match.group(2).strip()

        # 获取FROM和SELECT部分
        from_match = re.search(r'FROM\s+\w+', sql, re.IGNORECASE)
        select_match = re.search(r'SELECT\s+.+?\s+FROM', sql, re.IGNORECASE)

        if from_match and select_match:
            select_part = select_match.group(0).replace(' FROM', '')
            from_part = from_match.group(0)

            optimized = f"{select_part} {from_part} WHERE {condition1} UNION ALL {select_part} {from_part} WHERE {condition2}"

            return {
                "changed": True,
                "sql": optimized,
                "suggestion": {
                    "type": "OR_TO_UNION",
                    "description": "将OR条件重写为UNION",
                    "benefit": "允许使用索引，提高查询性能",
                    "risk": "可能产生重复结果，需要UNION ALL"
                }
            }

        return {"changed": False, "sql": sql, "suggestion": None}

    def _rewrite_subquery(
        self,
        sql: str,
        schema_info: Optional[Dict]
    ) -> Dict[str, Any]:
        """优化子查询"""
        # 检测IN子查询，建议改为EXISTS或JOIN
        in_subquery_pattern = r'(\w+)\s+IN\s*\(\s*SELECT\s+(.+?)\s+FROM\s+(\w+)'
        match = re.search(in_subquery_pattern, sql, re.IGNORECASE)

        if match:
            outer_column = match.group(1)
            inner_column = match.group(2)
            inner_table = match.group(3)

            # 建议改为EXISTS
            suggestion = f"考虑将IN子查询改为EXISTS: EXISTS (SELECT 1 FROM {inner_table} WHERE {inner_column} = outer.{outer_column})"

            return {
                "changed": False,  # 不自动重写，只给出建议
                "sql": sql,
                "suggestion": {
                    "type": "SUBQUERY_OPTIMIZATION",
                    "description": suggestion,
                    "benefit": "EXISTS通常比IN性能更好",
                    "risk": "需要手动验证逻辑等价性"
                }
            }

        return {"changed": False, "sql": sql, "suggestion": None}

    def _eliminate_redundant_conditions(
        self,
        sql: str,
        schema_info: Optional[Dict]
    ) -> Dict[str, Any]:
        """消除冗余条件"""
        # 检测1=1这种冗余条件
        redundant_patterns = [
            r"\s+AND\s+\(?\s*1\s*=\s*1\s*\)?",
            r"\s+OR\s+\(?\s*1\s*=\s*0\s*\)?",
        ]

        optimized = sql
        changed = False

        for pattern in redundant_patterns:
            new_sql = re.sub(pattern, '', optimized, flags=re.IGNORECASE)
            if new_sql != optimized:
                optimized = new_sql
                changed = True

        if changed:
            return {
                "changed": True,
                "sql": optimized,
                "suggestion": {
                    "type": "REDUNDANT_CONDITION",
                    "description": "消除冗余条件",
                    "benefit": "简化查询，提高可读性",
                    "risk": "无"
                }
            }

        return {"changed": False, "sql": sql, "suggestion": None}

    def _estimate_improvement(self, suggestions: List[Dict]) -> str:
        """估算改进程度"""
        if not suggestions:
            return "无需优化"

        critical_count = sum(1 for s in suggestions if s.get('type') in ['SELECT_STAR', 'IMPLICIT_CONVERSION'])

        if critical_count >= 2:
            return "预计性能提升50-80%"
        elif critical_count == 1:
            return "预计性能提升20-50%"
        else:
            return "预计性能提升10-20%"


class IndexRecommender:
    """
    索引推荐器

    功能：
    1. 分析查询条件，推荐合适的索引
    2. 评估索引收益
    3. 检测冗余索引
    4. 推荐复合索引

    使用示例：
        >>> recommender = IndexRecommender()
        >>> indexes = recommender.recommend_indexes("SELECT * FROM users WHERE age > 18", schema_info)
    """

    def __init__(self):
        """初始化索引推荐器"""
        pass

    def recommend_indexes(
        self,
        sql: str,
        schema_info: Dict[str, Any],
        existing_indexes: Optional[List[Dict]] = None
    ) -> List[IndexRecommendation]:
        """
        推荐索引

        参数:
            sql: SQL查询
            schema_info: 表结构信息
            existing_indexes: 已有索引列表

        返回:
            List[IndexRecommendation]: 索引推荐列表
        """
        recommendations = []

        # 解析SQL提取查询条件
        conditions = self._extract_conditions(sql)

        for condition in conditions:
            table = condition.get('table')
            columns = condition.get('columns', [])

            if not table or not columns:
                continue

            # 检查是否已有索引
            if self._has_index(existing_indexes, table, columns):
                continue

            # 生成索引推荐
            index_name = f"idx_{table}_{'_'.join(columns[:2])}"

            recommendations.append(IndexRecommendation(
                table_name=table,
                index_name=index_name,
                columns=columns,
                index_type="BTREE",
                reason=f"WHERE子句中的条件列: {', '.join(columns)}",
                estimated_benefit="预计查询性能提升30-70%",
                estimated_cost="增加写入开销约5-10%",
                priority=OptimizationPriority.HIGH if len(columns) <= 2 else OptimizationPriority.MEDIUM
            ))

        return recommendations

    def detect_redundant_indexes(
        self,
        existing_indexes: List[Dict]
    ) -> List[Dict[str, Any]]:
        """
        检测冗余索引

        参数:
            existing_indexes: 已有索引列表

        返回:
            List[Dict]: 冗余索引列表
        """
        redundant = []

        # 按表分组
        indexes_by_table = {}
        for idx in existing_indexes:
            table = idx.get('table')
            if table not in indexes_by_table:
                indexes_by_table[table] = []
            indexes_by_table[table].append(idx)

        # 检测冗余
        for table, indexes in indexes_by_table.items():
            for i, idx1 in enumerate(indexes):
                cols1 = idx1.get('columns', [])
                for idx2 in indexes[i+1:]:
                    cols2 = idx2.get('columns', [])

                    # 检查前缀冗余：如果idx1是idx2的前缀，则idx1是冗余的
                    if len(cols1) < len(cols2) and cols2[:len(cols1)] == cols1:
                        redundant.append({
                            "table": table,
                            "redundant_index": idx1.get('name'),
                            "covered_by": idx2.get('name'),
                            "reason": f"{idx1.get('name')}是{idx2.get('name')}的前缀，可以删除"
                        })

        return redundant

    def _extract_conditions(self, sql: str) -> List[Dict[str, Any]]:
        """提取查询条件"""
        conditions = []

        # 提取WHERE条件
        where_match = re.search(r'WHERE\s+(.+?)(?:ORDER|GROUP|LIMIT|$)', sql, re.IGNORECASE | re.DOTALL)
        if where_match:
            where_clause = where_match.group(1)

            # 提取表名
            from_match = re.search(r'FROM\s+(\w+)', sql, re.IGNORECASE)
            table = from_match.group(1) if from_match else "unknown"

            # 提取列名（简化处理）
            column_pattern = r'(\w+)\s*(?:=|>|<|>=|<=|LIKE|IN)'
            columns = re.findall(column_pattern, where_clause, re.IGNORECASE)

            # 过滤掉常见关键字
            columns = [c for c in columns if c.lower() not in ['and', 'or', 'not', 'in', 'like']]

            if columns:
                conditions.append({
                    "table": table,
                    "columns": list(set(columns)),  # 去重
                    "type": "where"
                })

        # 提取JOIN条件
        join_matches = re.findall(r'JOIN\s+(\w+)\s+ON\s+(.+?)(?:JOIN|WHERE|ORDER|GROUP|LIMIT|$)', sql, re.IGNORECASE | re.DOTALL)
        for table, on_clause in join_matches:
            columns = re.findall(r'(\w+)\s*=', on_clause, re.IGNORECASE)
            columns = [c for c in columns if c.lower() not in ['and', 'or']]

            if columns:
                conditions.append({
                    "table": table,
                    "columns": list(set(columns)),
                    "type": "join"
                })

        return conditions

    def _has_index(
        self,
        existing_indexes: Optional[List[Dict]],
        table: str,
        columns: List[str]
    ) -> bool:
        """检查是否已有索引"""
        if not existing_indexes:
            return False

        for idx in existing_indexes:
            if idx.get('table') == table:
                idx_columns = idx.get('columns', [])
                # 检查前缀匹配
                if idx_columns[:len(columns)] == columns:
                    return True

        return False





class CostEstimator:
    """
    成本估算器

    功能：
    1. 估算SQL执行成本
    2. 对比优化前后成本
    3. 提供成本分解

    使用示例：
        >>> estimator = CostEstimator()
        >>> cost = estimator.estimate(sql, table_stats)
    """

    def __init__(self):
        """初始化成本估算器"""
        self.base_io_cost = 1.0
        self.base_cpu_cost = 0.1

    def estimate(
        self,
        sql: str,
        table_stats: Dict[str, Any]
    ) -> CostEstimate:
        """
        估算SQL执行成本

        参数:
            sql: SQL查询
            table_stats: 表统计信息

        返回:
            CostEstimate: 成本估算结果
        """
        # 解析SQL类型
        sql_type = self._classify_sql_type(sql)

        # 估算IO成本
        io_cost = self._estimate_io_cost(sql, table_stats, sql_type)

        # 估算CPU成本
        cpu_cost = self._estimate_cpu_cost(sql, sql_type)

        # 估算内存成本
        memory_cost = self._estimate_memory_cost(sql, table_stats)

        total_cost = io_cost + cpu_cost + memory_cost

        # 估算执行时间（简化模型）
        estimated_time = total_cost * 10  # 假设每单位成本10ms

        # 估算返回行数
        estimated_rows = self._estimate_rows(sql, table_stats)

        return CostEstimate(
            io_cost=io_cost,
            cpu_cost=cpu_cost,
            memory_cost=memory_cost,
            total_cost=total_cost,
            estimated_time_ms=estimated_time,
            estimated_rows=estimated_rows
        )

    def compare_costs(
        self,
        original_cost: CostEstimate,
        optimized_cost: CostEstimate
    ) -> Dict[str, Any]:
        """
        对比优化前后的成本

        参数:
            original_cost: 原始成本
            optimized_cost: 优化后成本

        返回:
            Dict: 对比结果
        """
        cost_reduction = original_cost.total_cost - optimized_cost.total_cost
        reduction_percent = (cost_reduction / original_cost.total_cost * 100) if original_cost.total_cost > 0 else 0

        time_reduction = original_cost.estimated_time_ms - optimized_cost.estimated_time_ms

        return {
            "original_cost": original_cost.total_cost,
            "optimized_cost": optimized_cost.total_cost,
            "cost_reduction": cost_reduction,
            "reduction_percent": round(reduction_percent, 2),
            "time_reduction_ms": time_reduction,
            "improvement_level": self._classify_improvement(reduction_percent)
        }

    def _classify_sql_type(self, sql: str) -> str:
        """分类SQL类型"""
        sql_upper = sql.upper().strip()

        if sql_upper.startswith("SELECT"):
            return "SELECT"
        elif sql_upper.startswith("INSERT"):
            return "INSERT"
        elif sql_upper.startswith("UPDATE"):
            return "UPDATE"
        elif sql_upper.startswith("DELETE"):
            return "DELETE"
        else:
            return "OTHER"

    def _estimate_io_cost(
        self,
        sql: str,
        table_stats: Dict[str, Any],
        sql_type: str
    ) -> float:
        """估算IO成本"""
        # 简化模型：基于表大小和查询类型
        base_cost = self.base_io_cost

        # 提取表名
        tables = re.findall(r'FROM\s+(\w+)|JOIN\s+(\w+)', sql, re.IGNORECASE)
        table_list = [t[0] or t[1] for t in tables]

        for table in table_list:
            stats = table_stats.get(table, {})
            row_count = stats.get('row_count', 1000)
            base_cost += row_count / 1000  # 每1000行增加1单位成本

        # 根据类型调整
        if sql_type == "SELECT":
            base_cost *= 1.0
        elif sql_type in ["INSERT", "UPDATE", "DELETE"]:
            base_cost *= 1.5

        return base_cost

    def _estimate_cpu_cost(self, sql: str, sql_type: str) -> float:
        """估算CPU成本"""
        base_cost = self.base_cpu_cost

        # 根据复杂度调整
        if "JOIN" in sql.upper():
            base_cost *= 2.0
        if "GROUP BY" in sql.upper():
            base_cost *= 1.5
        if "ORDER BY" in sql.upper():
            base_cost *= 1.3

        return base_cost

    def _estimate_memory_cost(self, sql: str, table_stats: Dict[str, Any]) -> float:
        """估算内存成本"""
        # 简化模型
        if "ORDER BY" in sql.upper() or "GROUP BY" in sql.upper():
            return 2.0
        return 0.5

    def _estimate_rows(self, sql: str, table_stats: Dict[str, Any]) -> int:
        """估算返回行数"""
        # 简化模型：假设返回表行数的10%
        tables = re.findall(r'FROM\s+(\w+)', sql, re.IGNORECASE)
        if tables:
            stats = table_stats.get(tables[0], {})
            row_count = stats.get('row_count', 1000)
            return int(row_count * 0.1)
        return 100

    def _classify_improvement(self, reduction_percent: float) -> str:
        """分类改进程度"""
        if reduction_percent >= 50:
            return "显著优化"
        elif reduction_percent >= 20:
            return "良好优化"
        elif reduction_percent >= 10:
            return "轻微优化"
        else:
            return "优化效果有限"


class IntelligentOptimizer:
    """
    智能优化器 - 统一入口

    整合查询重写、索引推荐、执行计划分析、成本估算功能

    使用示例:
        >>> optimizer = IntelligentOptimizer(connector)
        >>> result = optimizer.optimize("SELECT * FROM users WHERE age > 18", schema_info)
        >>> print(result['recommendations'])
    """

    def __init__(self, connector=None):
        """初始化智能优化器

        参数:
            connector: 数据库连接器（可选，用于执行计划分析）
        """
        self.query_rewriter = QueryRewriter()
        self.index_recommender = IndexRecommender()
        # 如果提供了 connector 且 ExecutionPlanAnalyzer 可用，则初始化
        if ExecutionPlanAnalyzer and connector:
            try:
                self.plan_analyzer = ExecutionPlanAnalyzer(connector)
            except Exception as e:
                logger.warning(f"初始化 ExecutionPlanAnalyzer 失败: {e}")
                self.plan_analyzer = None
        else:
            self.plan_analyzer = None
        self.cost_estimator = CostEstimator()

    def optimize(
        self,
        sql: str,
        schema_info: Optional[Dict] = None,
        table_stats: Optional[Dict] = None,
        existing_indexes: Optional[List[Dict]] = None,
        execution_plan: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        执行完整优化分析

        参数:
            sql: 原始SQL
            schema_info: 表结构信息
            table_stats: 表统计信息
            existing_indexes: 已有索引
            execution_plan: 执行计划

        返回:
            Dict: 优化结果
        """
        result = {
            "original_sql": sql,
            "optimization_time": datetime.now().isoformat(),
            "recommendations": [],
            "rewrite_result": None,
            "index_recommendations": [],
            "execution_plan_analysis": None,
            "cost_comparison": None
        }

        # 1. 查询重写
        rewrite_result = self.query_rewriter.rewrite(sql, schema_info)
        result["rewrite_result"] = rewrite_result

        if rewrite_result.get("optimized_sql"):
            result["recommendations"].append({
                "type": "REWRITE",
                "priority": "HIGH",
                "description": f"查询重写优化: {rewrite_result['improvement_estimate']}",
                "original": sql,
                "optimized": rewrite_result["optimized_sql"]
            })

        # 2. 索引推荐
        if schema_info:
            index_recs = self.index_recommender.recommend_indexes(
                sql, schema_info, existing_indexes
            )
            result["index_recommendations"] = [
                {
                    "table": rec.table_name,
                    "index_name": rec.index_name,
                    "columns": rec.columns,
                    "reason": rec.reason,
                    "priority": rec.priority.value
                }
                for rec in index_recs
            ]

            for rec in index_recs:
                result["recommendations"].append({
                    "type": "INDEX",
                    "priority": rec.priority.value,
                    "description": f"为表{rec.table_name}添加索引: {', '.join(rec.columns)}",
                    "reason": rec.reason
                })

        # 3. 执行计划分析
        if execution_plan:
            plan_analysis = self.plan_analyzer.analyze(execution_plan)
            result["execution_plan_analysis"] = plan_analysis

            for issue in plan_analysis.get("issues", []):
                result["recommendations"].append({
                    "type": "EXECUTION_PLAN",
                    "priority": issue["severity"],
                    "description": issue["description"],
                    "suggestion": issue["suggestion"]
                })

        # 4. 成本估算
        if table_stats:
            original_cost = self.cost_estimator.estimate(sql, table_stats)

            if rewrite_result.get("optimized_sql"):
                optimized_cost = self.cost_estimator.estimate(
                    rewrite_result["optimized_sql"], table_stats
                )
                cost_comparison = self.cost_estimator.compare_costs(
                    original_cost, optimized_cost
                )
                result["cost_comparison"] = cost_comparison

        # 按优先级排序建议
        priority_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
        result["recommendations"].sort(
            key=lambda x: priority_order.get(x["priority"], 4)
        )

        return result

    def get_optimization_summary(self, optimization_result: Dict) -> str:
        """
        获取优化摘要

        参数:
            optimization_result: 优化结果

        返回:
            str: 摘要文本
        """
        lines = ["SQL优化分析报告", "=" * 40]

        # 重写结果
        rewrite = optimization_result.get("rewrite_result", {})
        if rewrite.get("changes_made", 0) > 0:
            lines.append(f"重写优化: {rewrite['changes_made']}处改进")
            lines.append(f"预期提升: {rewrite['improvement_estimate']}")

        # 索引推荐
        indexes = optimization_result.get("index_recommendations", [])
        if indexes:
            lines.append(f"索引推荐: {len(indexes)}个")

        # 执行计划问题
        plan = optimization_result.get("execution_plan_analysis", {})
        issues = plan.get("issues", [])
        if issues:
            lines.append(f"执行计划问题: {len(issues)}个")

        # 成本对比
        cost = optimization_result.get("cost_comparison", {})
        if cost:
            lines.append(f"成本降低: {cost.get('reduction_percent', 0)}%")

        return "\n".join(lines)
