"""
db_sql_auditor/utils.py
SQL审核工具类

文件功能：提供SQL审核相关的通用工具类
主要类/函数：
    - SQLParser: SQL解析器
    - RuleEngine: 规则引擎
    - ScoreCalculator: 评分计算器
    - IssueAggregator: 问题聚合器
    - SQLNormalizer: SQL标准化器
    - AuditReporter: 审核报告生成器

版本: 1.0.0
作者: AI Assistant
创建时间: 2026-04-23
"""

import re
import hashlib
from typing import Dict, Any, List, Optional, Pattern

from dbskiter.db_sql_auditor.models import (
    AuditLevel,
    AuditType,
    SQLType,
    AuditIssue,
    AuditResult,
    AuditRule,
)


class SQLParser:
    """
    SQL解析器

    功能:
        - 解析SQL类型
        - 提取SQL元素（表名、列名、条件等）
        - 检测SQL模式
    """

    # SQL类型检测模式
    SQL_PATTERNS: Dict[SQLType, Pattern] = {
        SQLType.SELECT: re.compile(r'^\s*SELECT\s+', re.IGNORECASE),
        SQLType.INSERT: re.compile(r'^\s*INSERT\s+INTO\s+', re.IGNORECASE),
        SQLType.UPDATE: re.compile(r'^\s*UPDATE\s+', re.IGNORECASE),
        SQLType.DELETE: re.compile(r'^\s*DELETE\s+FROM\s+', re.IGNORECASE),
        SQLType.CREATE: re.compile(r'^\s*CREATE\s+(TABLE|INDEX|VIEW)', re.IGNORECASE),
        SQLType.ALTER: re.compile(r'^\s*ALTER\s+TABLE\s+', re.IGNORECASE),
        SQLType.DROP: re.compile(r'^\s*DROP\s+(TABLE|INDEX|VIEW)', re.IGNORECASE),
        SQLType.TRUNCATE: re.compile(r'^\s*TRUNCATE\s+TABLE\s+', re.IGNORECASE),
    }

    @staticmethod
    def detect_sql_type(sql: str) -> SQLType:
        """
        检测SQL类型

        参数:
            sql: SQL语句

        返回:
            SQLType: SQL类型
        """
        if not sql or not sql.strip():
            return SQLType.UNKNOWN

        sql_stripped = sql.strip()

        for sql_type, pattern in SQLParser.SQL_PATTERNS.items():
            if pattern.match(sql_stripped):
                return sql_type

        return SQLType.UNKNOWN

    @staticmethod
    def extract_tables(sql: str) -> List[str]:
        """
        提取表名

        参数:
            sql: SQL语句

        返回:
            List[str]: 表名列表
        """
        if not sql:
            return []

        tables = set()
        sql_upper = sql.upper()

        # FROM 子句
        from_pattern = re.compile(r'\bFROM\s+(\w+)', re.IGNORECASE)
        for match in from_pattern.finditer(sql):
            tables.add(match.group(1).lower())

        # JOIN 子句
        join_pattern = re.compile(r'\bJOIN\s+(\w+)', re.IGNORECASE)
        for match in join_pattern.finditer(sql):
            tables.add(match.group(1).lower())

        # UPDATE 子句
        update_pattern = re.compile(r'\bUPDATE\s+(\w+)', re.IGNORECASE)
        for match in update_pattern.finditer(sql):
            tables.add(match.group(1).lower())

        # INTO 子句
        into_pattern = re.compile(r'\bINTO\s+(\w+)', re.IGNORECASE)
        for match in into_pattern.finditer(sql):
            tables.add(match.group(1).lower())

        return sorted(list(tables))

    @staticmethod
    def extract_columns(sql: str) -> List[str]:
        """
        提取列名

        参数:
            sql: SQL语句

        返回:
            List[str]: 列名列表
        """
        if not sql:
            return []

        columns = []

        # SELECT 列
        select_match = re.search(r'SELECT\s+(.+?)\s+FROM', sql, re.IGNORECASE | re.DOTALL)
        if select_match:
            cols_text = select_match.group(1)
            # 分割列
            cols = [c.strip() for c in cols_text.split(',')]
            for col in cols:
                # 移除别名
                col = re.sub(r'\s+AS\s+\w+', '', col, flags=re.IGNORECASE)
                col = col.strip()
                if col and col != '*':
                    columns.append(col)

        return columns

    @staticmethod
    def has_where_clause(sql: str) -> bool:
        """
        检查是否有WHERE子句

        参数:
            sql: SQL语句

        返回:
            bool: 是否有WHERE子句
        """
        if not sql:
            return False

        return bool(re.search(r'\bWHERE\b', sql, re.IGNORECASE))

    @staticmethod
    def has_limit_clause(sql: str) -> bool:
        """
        检查是否有LIMIT子句

        参数:
            sql: SQL语句

        返回:
            bool: 是否有LIMIT子句
        """
        if not sql:
            return False

        return bool(re.search(r'\bLIMIT\b', sql, re.IGNORECASE))


class RuleEngine:
    """
    规则引擎

    功能:
        - 管理审核规则
        - 执行规则检查
        - 规则优先级排序
    """

    # 内置规则定义
    BUILTIN_RULES: List[Dict[str, Any]] = [
        # ==================== 性能规则 ====================
        {
            "rule_id": "PERF-001",
            "rule_name": "禁止使用SELECT *",
            "audit_type": AuditType.PERFORMANCE,
            "level": AuditLevel.HIGH,
            "description": "SELECT * 会返回所有列，增加网络传输和内存消耗",
            "pattern": re.compile(r'SELECT\s+\*', re.IGNORECASE),
            "suggestion": "明确指定需要的列名",
        },
        {
            "rule_id": "PERF-002",
            "rule_name": "建议添加LIMIT限制",
            "audit_type": AuditType.PERFORMANCE,
            "level": AuditLevel.MEDIUM,
            "description": "没有LIMIT的查询可能返回大量数据",
            "check_func": lambda sql: not SQLParser.has_limit_clause(sql) and SQLParser.detect_sql_type(sql) == SQLType.SELECT,
            "suggestion": "添加LIMIT限制返回行数",
        },
        {
            "rule_id": "PERF-003",
            "rule_name": "避免使用NOT IN",
            "audit_type": AuditType.PERFORMANCE,
            "level": AuditLevel.MEDIUM,
            "description": "NOT IN性能较差，建议使用NOT EXISTS或LEFT JOIN",
            "pattern": re.compile(r'NOT\s+IN', re.IGNORECASE),
            "suggestion": "使用NOT EXISTS替代NOT IN",
        },
        {
            "rule_id": "PERF-004",
            "rule_name": "避免深度分页",
            "audit_type": AuditType.PERFORMANCE,
            "level": AuditLevel.HIGH,
            "description": "深度分页(如LIMIT 1000000,10)性能极差",
            "pattern": re.compile(r'LIMIT\s+\d{6,}\s*,', re.IGNORECASE),
            "suggestion": "使用覆盖索引或游标分页替代深度分页",
        },
        {
            "rule_id": "PERF-005",
            "rule_name": "避免在索引列上使用函数",
            "audit_type": AuditType.PERFORMANCE,
            "level": AuditLevel.HIGH,
            "description": "WHERE条件中对列使用函数会导致索引失效",
            "pattern": re.compile(r'WHERE\s+\w*\s*\([^)]+\)\s*[=<>]', re.IGNORECASE),
            "suggestion": "避免在WHERE条件中对索引列使用函数",
        },
        {
            "rule_id": "PERF-006",
            "rule_name": "避免隐式类型转换",
            "audit_type": AuditType.PERFORMANCE,
            "level": AuditLevel.MEDIUM,
            "description": "数字和字符串比较会导致隐式类型转换，索引失效",
            "pattern": re.compile(r'WHERE\s+\w+\s*=\s*[\'"]\d+[\'"]', re.IGNORECASE),
            "suggestion": "保持类型一致，避免隐式转换",
        },
        {
            "rule_id": "PERF-007",
            "rule_name": "避免多表JOIN",
            "audit_type": AuditType.PERFORMANCE,
            "level": AuditLevel.MEDIUM,
            "description": "超过3个表的JOIN性能较差",
            "pattern": re.compile(r'JOIN\s+\w+.*JOIN\s+\w+.*JOIN\s+\w+', re.IGNORECASE | re.DOTALL),
            "suggestion": "考虑拆分查询或优化表结构",
        },
        {
            "rule_id": "PERF-008",
            "rule_name": "避免SELECT COUNT(*)",
            "audit_type": AuditType.PERFORMANCE,
            "level": AuditLevel.MEDIUM,
            "description": "COUNT(*)在大表上性能差，考虑使用近似值",
            "pattern": re.compile(r'SELECT\s+COUNT\s*\(\s*\*\s*\)', re.IGNORECASE),
            "suggestion": "考虑使用SHOW TABLE STATUS或缓存计数",
        },
        
        # ==================== 安全规则 ====================
        {
            "rule_id": "SEC-001",
            "rule_name": "禁止无WHERE条件的DELETE/UPDATE",
            "audit_type": AuditType.SECURITY,
            "level": AuditLevel.CRITICAL,
            "description": "没有WHERE条件的DELETE/UPDATE会影响全表数据",
            "check_func": lambda sql: (
                SQLParser.detect_sql_type(sql) in [SQLType.DELETE, SQLType.UPDATE]
                and not SQLParser.has_where_clause(sql)
            ),
            "suggestion": "添加WHERE条件限制影响范围",
        },
        {
            "rule_id": "SEC-002",
            "rule_name": "禁止DROP/TRUNCATE操作",
            "audit_type": AuditType.SECURITY,
            "level": AuditLevel.CRITICAL,
            "description": "DROP和TRUNCATE是高风险操作，需要特别审批",
            "check_func": lambda sql: SQLParser.detect_sql_type(sql) in [SQLType.DROP, SQLType.TRUNCATE],
            "suggestion": "确认操作必要性并备份数据",
        },
        {
            "rule_id": "SEC-003",
            "rule_name": "禁止使用危险函数",
            "audit_type": AuditType.SECURITY,
            "level": AuditLevel.CRITICAL,
            "description": "SLEEP(), BENCHMARK()等函数可能导致DoS攻击",
            "pattern": re.compile(r'\b(SLEEP|BENCHMARK|LOAD_FILE|INTO\s+OUTFILE|INTO\s+DUMPFILE)\s*\(', re.IGNORECASE),
            "suggestion": "移除危险函数或进行严格审查",
        },
        {
            "rule_id": "SEC-004",
            "rule_name": "检测SQL注入风险",
            "audit_type": AuditType.SECURITY,
            "level": AuditLevel.CRITICAL,
            "description": "字符串拼接SQL存在SQL注入风险",
            "pattern": re.compile(r'[\'"].*\+|\+.*[\'"]|\$\{|%s|%\(.*\)s', re.IGNORECASE),
            "suggestion": "使用参数化查询替代字符串拼接",
        },
        {
            "rule_id": "SEC-005",
            "rule_name": "禁止堆叠查询",
            "audit_type": AuditType.SECURITY,
            "level": AuditLevel.HIGH,
            "description": "分号分隔的多条SQL存在安全风险",
            "pattern": re.compile(r';\s*(SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER)', re.IGNORECASE),
            "suggestion": "避免使用堆叠查询，拆分执行",
        },
        {
            "rule_id": "SEC-006",
            "rule_name": "检测敏感字段查询",
            "audit_type": AuditType.SECURITY,
            "level": AuditLevel.HIGH,
            "description": "查询密码、密钥等敏感字段需要审计",
            "pattern": re.compile(r'SELECT.*\b(password|passwd|pwd|secret|key|token|credential)\b', re.IGNORECASE),
            "suggestion": "避免直接查询敏感字段，使用加密或脱敏",
        },
        {
            "rule_id": "SEC-007",
            "rule_name": "禁止注释绕过",
            "audit_type": AuditType.SECURITY,
            "level": AuditLevel.HIGH,
            "description": "使用注释可能绕过权限检查",
            "pattern": re.compile(r'/\*|--|#', re.IGNORECASE),
            "suggestion": "移除不必要的注释",
        },
        
        # ==================== DDL规则 ====================
        {
            "rule_id": "DDL-001",
            "rule_name": "大表ALTER操作警告",
            "audit_type": AuditType.DDL,
            "level": AuditLevel.HIGH,
            "description": "对大表执行ALTER可能长时间锁表",
            "pattern": re.compile(r'ALTER\s+TABLE', re.IGNORECASE),
            "suggestion": "使用pt-online-schema-change或考虑业务低峰期执行",
        },
        {
            "rule_id": "DDL-002",
            "rule_name": "缺少索引的CREATE TABLE",
            "audit_type": AuditType.DDL,
            "level": AuditLevel.MEDIUM,
            "description": "CREATE TABLE应该同时创建主键索引",
            "check_func": lambda sql: (
                SQLParser.detect_sql_type(sql) == SQLType.CREATE
                and 'TABLE' in sql.upper()
                and 'PRIMARY KEY' not in sql.upper()
            ),
            "suggestion": "添加主键索引",
        },
        {
            "rule_id": "DDL-003",
            "rule_name": "禁止删除列",
            "audit_type": AuditType.DDL,
            "level": AuditLevel.HIGH,
            "description": "DROP COLUMN可能导致数据丢失",
            "pattern": re.compile(r'DROP\s+COLUMN', re.IGNORECASE),
            "suggestion": "确认数据已备份，考虑先标记废弃再删除",
        },
        {
            "rule_id": "DDL-004",
            "rule_name": "外键约束警告",
            "audit_type": AuditType.DDL,
            "level": AuditLevel.MEDIUM,
            "description": "外键会影响写入性能",
            "pattern": re.compile(r'FOREIGN\s+KEY', re.IGNORECASE),
            "suggestion": "考虑在应用层实现外键约束",
        },
        
        # ==================== 规范规则 ====================
        {
            "rule_id": "STYLE-001",
            "rule_name": "关键字大写",
            "audit_type": AuditType.STYLE,
            "level": AuditLevel.LOW,
            "description": "SQL关键字建议使用大写",
            "pattern": re.compile(r'\b(select|from|where|insert|update|delete)\b'),
            "suggestion": "将SQL关键字转换为大写",
        },
        {
            "rule_id": "STYLE-002",
            "rule_name": "表名规范检查",
            "audit_type": AuditType.STYLE,
            "level": AuditLevel.LOW,
            "description": "表名建议使用小写字母和下划线",
            "pattern": re.compile(r'FROM\s+([A-Z][a-zA-Z0-9]*|[a-z]+[A-Z])', re.IGNORECASE),
            "suggestion": "使用小写字母和下划线命名表名",
        },
        {
            "rule_id": "STYLE-003",
            "rule_name": "避免使用保留字",
            "audit_type": AuditType.STYLE,
            "level": AuditLevel.MEDIUM,
            "description": "表名和字段名不应使用保留字",
            "pattern": re.compile(r'\b(ORDER|GROUP|SELECT|FROM|WHERE|TABLE|INDEX)\b', re.IGNORECASE),
            "suggestion": "避免使用SQL保留字作为标识符",
        },
        {
            "rule_id": "STYLE-004",
            "rule_name": "DELETE/UPDATE需要LIMIT",
            "audit_type": AuditType.STYLE,
            "level": AuditLevel.MEDIUM,
            "description": "DELETE和UPDATE应该添加LIMIT限制影响行数",
            "check_func": lambda sql: (
                SQLParser.detect_sql_type(sql) in [SQLType.DELETE, SQLType.UPDATE]
                and SQLParser.has_where_clause(sql)
                and not SQLParser.has_limit_clause(sql)
            ),
            "suggestion": "添加LIMIT限制影响行数，防止误操作",
        },
    ]

    def __init__(self):
        """初始化规则引擎"""
        self.rules: Dict[str, AuditRule] = {}
        self._init_builtin_rules()

    def _init_builtin_rules(self):
        """初始化内置规则"""
        for rule_def in self.BUILTIN_RULES:
            rule = AuditRule(
                rule_id=rule_def["rule_id"],
                rule_name=rule_def["rule_name"],
                audit_type=rule_def["audit_type"],
                level=rule_def["level"],
                description=rule_def["description"],
                enabled=True,
                custom_config={
                    "pattern": rule_def.get("pattern"),
                    "check_func": rule_def.get("check_func"),
                    "suggestion": rule_def.get("suggestion", ""),
                }
            )
            self.rules[rule.rule_id] = rule

    def get_rule(self, rule_id: str) -> Optional[AuditRule]:
        """
        获取规则

        参数:
            rule_id: 规则ID

        返回:
            Optional[AuditRule]: 规则对象
        """
        return self.rules.get(rule_id)

    def get_all_rules(self) -> List[AuditRule]:
        """
        获取所有规则

        返回:
            List[AuditRule]: 规则列表
        """
        return list(self.rules.values())

    def get_enabled_rules(self) -> List[AuditRule]:
        """
        获取启用的规则

        返回:
            List[AuditRule]: 启用的规则列表
        """
        return [r for r in self.rules.values() if r.enabled]

    def enable_rule(self, rule_id: str) -> bool:
        """
        启用规则

        参数:
            rule_id: 规则ID

        返回:
            bool: 是否成功
        """
        if rule_id in self.rules:
            self.rules[rule_id].enabled = True
            return True
        return False

    def disable_rule(self, rule_id: str) -> bool:
        """
        禁用规则

        参数:
            rule_id: 规则ID

        返回:
            bool: 是否成功
        """
        if rule_id in self.rules:
            self.rules[rule_id].enabled = False
            return True
        return False

    def add_custom_rule(self, rule: AuditRule):
        """
        添加自定义规则

        参数:
            rule: 规则对象
        """
        self.rules[rule.rule_id] = rule

    def execute_rule(self, rule_id: str, sql: str) -> Optional[AuditIssue]:
        """
        执行单个规则检查

        参数:
            rule_id: 规则ID
            sql: SQL语句

        返回:
            Optional[AuditIssue]: 发现的问题，无问题返回None
        """
        rule = self.rules.get(rule_id)
        if not rule or not rule.enabled:
            return None

        config = rule.custom_config

        # 检查模式匹配
        pattern = config.get("pattern")
        if pattern and pattern.search(sql):
            return AuditIssue(
                rule_id=rule.rule_id,
                rule_name=rule.rule_name,
                audit_type=rule.audit_type,
                level=rule.level,
                message=rule.description,
                suggestion=config.get("suggestion", ""),
                sql_fragment=sql[:100] if len(sql) > 100 else sql
            )

        # 检查自定义函数
        check_func = config.get("check_func")
        if check_func and check_func(sql):
            return AuditIssue(
                rule_id=rule.rule_id,
                rule_name=rule.rule_name,
                audit_type=rule.audit_type,
                level=rule.level,
                message=rule.description,
                suggestion=config.get("suggestion", ""),
                sql_fragment=sql[:100] if len(sql) > 100 else sql
            )

        return None


class ScoreCalculator:
    """
    评分计算器

    功能:
        - 计算审核评分
        - 根据问题级别计算扣分
    """

    # 默认扣分配置
    DEFAULT_DEDUCTIONS: Dict[AuditLevel, int] = {
        AuditLevel.CRITICAL: 30,
        AuditLevel.HIGH: 15,
        AuditLevel.MEDIUM: 5,
        AuditLevel.LOW: 2,
        AuditLevel.INFO: 0,
    }

    def __init__(self, deductions: Optional[Dict[AuditLevel, int]] = None):
        """
        初始化评分计算器

        参数:
            deductions: 自定义扣分配置
        """
        self.deductions = deductions or self.DEFAULT_DEDUCTIONS.copy()

    def calculate_score(self, issues: List[AuditIssue]) -> float:
        """
        计算审核评分

        参数:
            issues: 问题列表

        返回:
            float: 评分(0-100)
        """
        score = 100.0

        for issue in issues:
            deduction = self.deductions.get(issue.level, 0)
            score -= deduction

        return max(0.0, score)

    def calculate_pass_status(self, score: float, critical_count: int) -> bool:
        """
        计算通过状态

        参数:
            score: 评分
            critical_count: 严重问题数

        返回:
            bool: 是否通过
        """
        return score >= 80 and critical_count == 0


class IssueAggregator:
    """
    问题聚合器

    功能:
        - 聚合多个审核结果
        - 统计问题分布
        - 生成汇总报告
    """

    @staticmethod
    def aggregate_results(results: List[AuditResult]) -> Dict[str, Any]:
        """
        聚合审核结果

        参数:
            results: 审核结果列表

        返回:
            Dict[str, Any]: 聚合统计
        """
        total_issues = 0
        level_counts = {
            "critical": 0,
            "high": 0,
            "medium": 0,
            "low": 0,
            "info": 0,
        }
        type_counts: Dict[str, int] = {}

        for result in results:
            total_issues += result.total_issues
            level_counts["critical"] += result.critical_count
            level_counts["high"] += result.high_count
            level_counts["medium"] += result.medium_count
            level_counts["low"] += result.low_count

            for issue in result.issues:
                type_name = issue.audit_type.value
                type_counts[type_name] = type_counts.get(type_name, 0) + 1

        return {
            "total_sqls": len(results),
            "total_issues": total_issues,
            "level_counts": level_counts,
            "type_counts": type_counts,
            "passed_count": sum(1 for r in results if r.passed),
            "failed_count": sum(1 for r in results if not r.passed),
        }

    @staticmethod
    def get_top_issues(
        results: List[AuditResult],
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        获取最常见的问题

        参数:
            results: 审核结果列表
            limit: 返回数量限制

        返回:
            List[Dict[str, Any]]: 问题列表
        """
        issue_counts: Dict[str, Dict[str, Any]] = {}

        for result in results:
            for issue in result.issues:
                key = issue.rule_id
                if key not in issue_counts:
                    issue_counts[key] = {
                        "rule_id": issue.rule_id,
                        "rule_name": issue.rule_name,
                        "level": issue.level.value,
                        "count": 0,
                    }
                issue_counts[key]["count"] += 1

        # 按出现次数排序
        sorted_issues = sorted(
            issue_counts.values(),
            key=lambda x: x["count"],
            reverse=True
        )

        return sorted_issues[:limit]


class SQLNormalizer:
    """
    SQL标准化器

    功能:
        - 标准化SQL用于比较
        - 生成SQL指纹
    """

    @staticmethod
    def normalize(sql: str) -> str:
        """
        标准化SQL

        参数:
            sql: SQL语句

        返回:
            str: 标准化后的SQL
        """
        if not sql:
            return ""

        # 转小写
        sql = sql.lower()

        # 移除多余空白
        sql = re.sub(r'\s+', ' ', sql.strip())

        # 替换字符串常量
        sql = re.sub(r"'[^']*'", "'?'", sql)
        sql = re.sub(r'"[^"]*"', '"?"', sql)

        # 替换数字常量
        sql = re.sub(r'\b\d+\b', '?', sql)

        # 移除注释
        sql = re.sub(r'--[^\n]*', '', sql)
        sql = re.sub(r'/\*.*?\*/', '', sql, flags=re.DOTALL)

        return sql.strip()

    @staticmethod
    def generate_fingerprint(sql: str) -> str:
        """
        生成SQL指纹

        参数:
            sql: SQL语句

        返回:
            str: SQL指纹
        """
        normalized = SQLNormalizer.normalize(sql)
        return hashlib.md5(normalized.encode()).hexdigest()[:16]


class AuditReporter:
    """
    审核报告生成器

    功能:
        - 生成审核报告
        - 格式化输出
    """

    @staticmethod
    def generate_summary(results: List[AuditResult]) -> str:
        """
        生成汇总报告

        参数:
            results: 审核结果列表

        返回:
            str: 报告文本
        """
        if not results:
            return "没有审核结果"

        stats = IssueAggregator.aggregate_results(results)

        lines = [
            "=" * 50,
            "SQL审核报告",
            "=" * 50,
            f"审核SQL数: {stats['total_sqls']}",
            f"通过: {stats['passed_count']}",
            f"失败: {stats['failed_count']}",
            "-" * 50,
            "问题统计:",
            f"  严重: {stats['level_counts']['critical']}",
            f"  高危: {stats['level_counts']['high']}",
            f"  中危: {stats['level_counts']['medium']}",
            f"  低危: {stats['level_counts']['low']}",
            "=" * 50,
        ]

        return "\n".join(lines)

    @staticmethod
    def format_issue(issue: AuditIssue) -> str:
        """
        格式化单个问题

        参数:
            issue: 问题对象

        返回:
            str: 格式化文本
        """
        lines = [
            f"[{issue.level.value.upper()}] {issue.rule_id}: {issue.rule_name}",
            f"  类型: {issue.audit_type.value}",
            f"  描述: {issue.message}",
            f"  建议: {issue.suggestion}",
        ]

        if issue.sql_fragment:
            lines.append(f"  片段: {issue.sql_fragment}")

        return "\n".join(lines)
