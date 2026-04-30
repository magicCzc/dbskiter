"""
sql_master/sql_rewriter_v2.py

SQL 重写器 V2 - 真正的 SQL 优化重写

优化点：
1. SELECT * 展开为具体字段（通过 Schema 获取）
2. 子查询改 JOIN 建议
3. OR 条件改 UNION 建议
4. 隐式类型转换检测
5. 生成优化后的可执行 SQL

作者：Trae AI
创建时间：2026-04-20
"""

import re
import sqlparse
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

from dbskiter.shared.unified_connector import UnifiedConnector


class RewriteType(Enum):
    """重写类型"""
    SELECT_STAR = "select_star"           # SELECT * 展开
    SUBQUERY_TO_JOIN = "subquery_to_join" # 子查询改 JOIN
    OR_TO_UNION = "or_to_union"           # OR 改 UNION
    IMPLICIT_CAST = "implicit_cast"       # 隐式类型转换
    REDUNDANT_CONDITION = "redundant"     # 冗余条件
    MISSING_ALIAS = "missing_alias"       # 缺少别名


@dataclass
class RewriteSuggestion:
    """重写建议"""
    rewrite_type: RewriteType
    original_sql: str
    rewritten_sql: str
    reason: str
    impact: str  # high, medium, low
    confidence: float
    explanation: str


@dataclass
class RewriteResult:
    """重写结果"""
    original_sql: str
    can_rewrite: bool
    suggestions: List[RewriteSuggestion]
    best_rewrite: Optional[str]
    warnings: List[str] = field(default_factory=list)
    
    def summary(self) -> str:
        lines = [
            f"SQL 重写分析:",
            f"  原始 SQL: {self.original_sql[:60]}...",
            f"  可优化: {self.can_rewrite}",
            f"  建议数: {len(self.suggestions)}",
        ]
        
        if self.suggestions:
            lines.append("\n  重写建议:")
            for sug in self.suggestions[:3]:
                lines.append(f"    [{sug.impact.upper()}] {sug.reason}")
                lines.append(f"    重写: {sug.rewritten_sql[:60]}...")
        
        if self.best_rewrite:
            lines.append(f"\n  最佳重写:\n    {self.best_rewrite}")
        
        return "\n".join(lines)


class SQLRewriterV2:
    """
    SQL 重写器 V2
    
    核心能力：
    1. 不只是检测问题，而是生成优化后的 SQL
    2. 基于 Schema 信息展开 SELECT *
    3. 识别并转换低效写法
    4. 保留原意的前提下优化性能
    """
    
    def __init__(self, connector: UnifiedConnector):
        self.connector = connector
        self.dialect = connector.dialect.lower()
    
    def rewrite(self, sql: str) -> RewriteResult:
        """
        分析并重写 SQL
        
        参数:
            sql: 原始 SQL
            
        返回:
            RewriteResult: 重写结果
        """
        sql = sql.strip()
        suggestions = []
        warnings = []
        
        # 1. 检测并重写 SELECT *
        star_suggestion = self._rewrite_select_star(sql)
        if star_suggestion:
            suggestions.append(star_suggestion)
        
        # 2. 检测子查询
        subquery_suggestion = self._analyze_subquery(sql)
        if subquery_suggestion:
            suggestions.append(subquery_suggestion)
        
        # 3. 检测 OR 条件
        or_suggestion = self._analyze_or_conditions(sql)
        if or_suggestion:
            suggestions.append(or_suggestion)
        
        # 4. 检测隐式类型转换
        cast_suggestion = self._analyze_implicit_cast(sql)
        if cast_suggestion:
            suggestions.append(cast_suggestion)
        
        # 5. 检测冗余条件
        redundant_suggestion = self._analyze_redundant_conditions(sql)
        if redundant_suggestion:
            suggestions.append(redundant_suggestion)
        
        # 按影响排序
        suggestions.sort(key=lambda x: ({"high": 0, "medium": 1, "low": 2}.get(x.impact, 3), -x.confidence))
        
        # 链式应用所有建议生成最佳重写
        best_rewrite = sql
        for suggestion in suggestions:
            # 在当前 best_rewrite 上应用这个建议
            # 注意：这里需要根据建议类型做对应的替换
            best_rewrite = self._apply_suggestion(best_rewrite, suggestion)
        
        if best_rewrite == sql:
            best_rewrite = None
        
        return RewriteResult(
            original_sql=sql,
            can_rewrite=len(suggestions) > 0,
            suggestions=suggestions,
            best_rewrite=best_rewrite,
            warnings=warnings
        )
    
    def _apply_suggestion(self, sql: str, suggestion: RewriteSuggestion) -> str:
        """应用单个建议到 SQL"""
        if suggestion.rewrite_type == RewriteType.SELECT_STAR:
            # SELECT * 展开 - 在当前 SQL 上重新执行
            return self._apply_select_star_to_sql(sql)
        elif suggestion.rewrite_type == RewriteType.REDUNDANT_CONDITION:
            # 冗余条件移除 - 在当前 SQL 上重新执行
            return self._apply_redundant_condition_to_sql(sql)
        elif suggestion.rewrite_type == RewriteType.SUBQUERY_TO_JOIN:
            # 子查询建议通常是注释形式，不直接替换
            return sql
        elif suggestion.rewrite_type == RewriteType.OR_TO_UNION:
            # OR 建议通常是注释形式
            return sql
        elif suggestion.rewrite_type == RewriteType.IMPLICIT_CAST:
            # 类型转换警告通常是注释形式
            return sql
        return sql
    
    def _apply_redundant_condition_to_sql(self, sql: str) -> str:
        """在当前 SQL 上应用冗余条件移除"""
        import re
        
        if not re.search(r'\b1\s*=\s*1\b', sql):
            return sql
        
        rewritten = sql
        
        # 循环处理直到没有 1=1
        max_iterations = 10
        for _ in range(max_iterations):
            old = rewritten
            
            # 情况1: WHERE 1=1 AND ... -> WHERE ...
            rewritten = re.sub(
                r'\bWHERE\s+1\s*=\s*1\s+AND\s+',
                'WHERE ',
                rewritten,
                flags=re.IGNORECASE
            )
            
            # 情况2: ... AND 1=1 -> ... (1=1 在末尾或中间)
            rewritten = re.sub(
                r'\s+AND\s+1\s*=\s*1\b',
                '',
                rewritten,
                flags=re.IGNORECASE
            )
            
            # 情况3: 1=1 AND ... -> ... (1=1 在开头)
            rewritten = re.sub(
                r'\b1\s*=\s*1\s+AND\s+',
                '',
                rewritten,
                flags=re.IGNORECASE
            )
            
            # 情况4: WHERE 1=1 (后面没有其他条件，但可能有 ORDER/GROUP/LIMIT)
            rewritten = re.sub(
                r'\bWHERE\s+1\s*=\s*1\b(\s+(ORDER|GROUP|LIMIT|HAVING))',
                r'\1',
                rewritten,
                flags=re.IGNORECASE
            )
            
            # 情况5: WHERE 1=1 在末尾 -> 移除 WHERE 1=1
            rewritten = re.sub(
                r'\bWHERE\s+1\s*=\s*1\s*$',
                '',
                rewritten,
                flags=re.IGNORECASE
            )
            
            if old == rewritten:
                break
        
        # 清理多余空格
        rewritten = re.sub(r'\s+', ' ', rewritten).strip()
        
        return rewritten
    
    def _apply_select_star_to_sql(self, sql: str) -> str:
        """在当前 SQL 上应用 SELECT * 展开"""
        # 移除注释后检查
        sql_no_comments = re.sub(r'/\*.*?\*/', ' ', sql, flags=re.DOTALL)
        sql_no_comments = re.sub(r'--.*?$', '', sql_no_comments, flags=re.MULTILINE)
        
        if not re.search(r'SELECT\s+\*', sql_no_comments, re.IGNORECASE):
            return sql
        
        # 提取表名
        table_match = re.search(r'FROM\s+(\w+)(?:\s+(?:AS\s+)?\w+)?', sql, re.IGNORECASE)
        if not table_match:
            return sql
        
        table_name = table_match.group(1)
        columns = self._get_table_columns(table_name)
        
        if not columns:
            return sql
        
        # 生成展开后的 SQL
        column_str = ", ".join(columns[:10])
        if len(columns) > 10:
            column_str += f", /* ... 还有 {len(columns) - 10} 个字段 */"
        
        rewritten = re.sub(
            r'SELECT(\s*/\*.*?\*/)?\s*\*',
            f'SELECT\\1 {column_str}',
            sql,
            flags=re.IGNORECASE | re.DOTALL
        )
        
        return rewritten
    
    def _rewrite_select_star(self, sql: str) -> Optional[RewriteSuggestion]:
        """重写 SELECT * 为具体字段"""
        # 移除注释后检查
        sql_no_comments = re.sub(r'/\*.*?\*/', ' ', sql, flags=re.DOTALL)
        sql_no_comments = re.sub(r'--.*?$', '', sql_no_comments, flags=re.MULTILINE)
        
        if not re.search(r'SELECT\s+\*', sql_no_comments, re.IGNORECASE):
            return None
        
        # 提取表名（支持多种格式：FROM table, FROM table alias, FROM table AS alias）
        table_match = re.search(r'FROM\s+(\w+)(?:\s+(?:AS\s+)?\w+)?', sql, re.IGNORECASE)
        if not table_match:
            return None
        
        table_name = table_match.group(1)
        
        # 获取表字段
        columns = self._get_table_columns(table_name)
        if not columns:
            return RewriteSuggestion(
                rewrite_type=RewriteType.SELECT_STAR,
                original_sql=sql,
                rewritten_sql=sql,  # 无法重写，保持原样
                reason="SELECT * 需要展开为具体字段",
                impact="medium",
                confidence=0.9,
                explanation=f"无法获取表 {table_name} 的字段信息，建议手动展开 * 为具体字段列表"
            )
        
        # 生成展开后的 SQL
        column_str = ", ".join(columns[:10])  # 最多10个字段
        if len(columns) > 10:
            column_str += f", /* ... 还有 {len(columns) - 10} 个字段 */"
        
        # 替换 SELECT *，保留注释
        # 匹配 SELECT [可选注释] *
        rewritten = re.sub(
            r'SELECT(\s*/\*.*?\*/)?\s*\*',
            f'SELECT\\1 {column_str}',
            sql,
            flags=re.IGNORECASE | re.DOTALL
        )
        
        return RewriteSuggestion(
            rewrite_type=RewriteType.SELECT_STAR,
            original_sql=sql,
            rewritten_sql=rewritten,
            reason="SELECT * 展开为具体字段，减少网络传输和内存使用",
            impact="medium",
            confidence=0.95,
            explanation=f"展开为 {len(columns)} 个字段，避免传输不需要的列"
        )
    
    def _get_table_columns(self, table_name: str) -> List[str]:
        """获取表字段列表"""
        try:
            if self.dialect in ("mysql", "mysql+pymysql"):
                result = self.connector.execute(f"""
                    SELECT COLUMN_NAME
                    FROM INFORMATION_SCHEMA.COLUMNS
                    WHERE TABLE_SCHEMA = DATABASE()
                    AND TABLE_NAME = '{table_name}'
                    ORDER BY ORDINAL_POSITION
                """)
                return [row[0] for row in result.rows]
            elif "postgresql" in self.dialect:
                result = self.connector.execute(f"""
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_name = '{table_name}'
                    ORDER BY ordinal_position
                """)
                return [row[0] for row in result.rows]
            elif "oracle" in self.dialect:
                result = self.connector.execute(f"""
                    SELECT COLUMN_NAME
                    FROM USER_TAB_COLUMNS
                    WHERE TABLE_NAME = UPPER('{table_name}')
                    ORDER BY COLUMN_ID
                """)
                return [row[0] for row in result.rows]
        except Exception as e:
            print(f"获取表字段失败: {e}")
        return []
    
    def _analyze_subquery(self, sql: str) -> Optional[RewriteSuggestion]:
        """分析子查询是否可以改 JOIN"""
        # 检测 IN (SELECT ...) 或 EXISTS (SELECT ...)
        in_subquery_match = re.search(
            r'(\w+)\s+IN\s*\(\s*SELECT\s+([^)]+)\s+FROM\s+(\w+)',
            sql,
            re.IGNORECASE
        )
        
        if in_subquery_match:
            outer_col = in_subquery_match.group(1)
            inner_col = in_subquery_match.group(2).strip()
            inner_table = in_subquery_match.group(3)
            
            # 生成 JOIN 版本
            original_pattern = re.escape(in_subquery_match.group(0))
            rewritten = re.sub(
                original_pattern,
                f"1=1 /* 建议改为 JOIN: INNER JOIN {inner_table} ON {outer_col} = {inner_table}.{inner_col} */",
                sql,
                flags=re.IGNORECASE
            )
            
            return RewriteSuggestion(
                rewrite_type=RewriteType.SUBQUERY_TO_JOIN,
                original_sql=sql,
                rewritten_sql=rewritten,
                reason=f"子查询 IN (SELECT ...) 可以改为 JOIN，通常性能更好",
                impact="high",
                confidence=0.8,
                explanation=f"建议: INNER JOIN {inner_table} ON {outer_col} = {inner_table}.{inner_col}"
            )
        
        return None
    
    def _analyze_or_conditions(self, sql: str) -> Optional[RewriteSuggestion]:
        """分析 OR 条件"""
        # 检测 WHERE 中的 OR
        or_match = re.search(r'WHERE\s+(.+?)(?:ORDER|GROUP|LIMIT|$)', sql, re.IGNORECASE | re.DOTALL)
        if not or_match:
            return None
        
        where_clause = or_match.group(1)
        
        # 简单的 OR 检测
        if ' OR ' in where_clause.upper():
            or_count = where_clause.upper().count(' OR ')
            
            return RewriteSuggestion(
                rewrite_type=RewriteType.OR_TO_UNION,
                original_sql=sql,
                rewritten_sql=sql + " /* 建议: 考虑拆分为 UNION 如果 OR 条件涉及不同索引 */",
                reason=f"发现 {or_count} 个 OR 条件，可能导致索引失效",
                impact="medium",
                confidence=0.6,
                explanation="OR 条件可能导致全表扫描，考虑拆分为 UNION ALL"
            )
        
        return None
    
    def _analyze_implicit_cast(self, sql: str) -> Optional[RewriteSuggestion]:
        """分析隐式类型转换"""
        # 检测字符串和数字的比较
        cast_patterns = [
            (r"(\w+)\s*=\s*['\"]\d+['\"]", "数字列与字符串比较"),
            (r"(\w+)\s*=\s*\d+", None),  # 正常情况
        ]
        
        for pattern, reason in cast_patterns:
            if reason and re.search(pattern, sql, re.IGNORECASE):
                match = re.search(pattern, sql, re.IGNORECASE)
                col = match.group(1)
                return RewriteSuggestion(
                    rewrite_type=RewriteType.IMPLICIT_CAST,
                    original_sql=sql,
                    rewritten_sql=sql + f" /* 警告: 列 {col} 可能发生隐式类型转换 */",
                    reason=reason,
                    impact="medium",
                    confidence=0.7,
                    explanation="隐式类型转换会导致索引失效，确保比较双方类型一致"
                )
        
        return None
    
    def _analyze_redundant_conditions(self, sql: str) -> Optional[RewriteSuggestion]:
        """分析冗余条件"""
        # 检测 1=1 等永远为真的条件
        if not re.search(r'\b1\s*=\s*1\b', sql):
            return None
        
        original = sql
        rewritten = sql
        
        # 循环处理直到没有 1=1
        max_iterations = 10
        for _ in range(max_iterations):
            old = rewritten
            
            # 情况1: WHERE 1=1 AND ... -> WHERE ...
            rewritten = re.sub(
                r'\bWHERE\s+1\s*=\s*1\s+AND\s+',
                'WHERE ',
                rewritten,
                flags=re.IGNORECASE
            )
            
            # 情况2: ... AND 1=1 -> ... (1=1 在末尾或中间)
            rewritten = re.sub(
                r'\s+AND\s+1\s*=\s*1\b',
                '',
                rewritten,
                flags=re.IGNORECASE
            )
            
            # 情况3: 1=1 AND ... -> ... (1=1 在开头)
            rewritten = re.sub(
                r'\b1\s*=\s*1\s+AND\s+',
                '',
                rewritten,
                flags=re.IGNORECASE
            )
            
            # 情况4: WHERE 1=1 (后面没有其他条件，但可能有 ORDER/GROUP/LIMIT)
            # 直接移除 WHERE 1=1，保留后面的子句
            rewritten = re.sub(
                r'\bWHERE\s+1\s*=\s*1\b(\s+(ORDER|GROUP|LIMIT|HAVING))',
                r'\1',
                rewritten,
                flags=re.IGNORECASE
            )
            
            # 情况5: WHERE 1=1 在末尾 -> 移除 WHERE 1=1
            rewritten = re.sub(
                r'\bWHERE\s+1\s*=\s*1\s*$',
                '',
                rewritten,
                flags=re.IGNORECASE
            )
            
            if old == rewritten:
                break
        
        # 清理多余空格
        rewritten = re.sub(r'\s+', ' ', rewritten).strip()
        
        if rewritten != original:
            return RewriteSuggestion(
                rewrite_type=RewriteType.REDUNDANT_CONDITION,
                original_sql=original,
                rewritten_sql=rewritten,
                reason="移除冗余的 1=1 条件",
                impact="low",
                confidence=0.99,
                explanation="1=1 是永远为真的条件，可以移除以简化 SQL"
            )
        
        return None
    
    def batch_rewrite(self, sqls: List[str]) -> List[RewriteResult]:
        """批量重写 SQL"""
        return [self.rewrite(sql) for sql in sqls]
    
    def generate_optimized_sql(self, sql: str) -> str:
        """生成优化后的 SQL（便捷方法）"""
        result = self.rewrite(sql)
        return result.best_rewrite or sql
