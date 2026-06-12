"""
db_diagnose/utils.py
工具类定义

文件功能：提供SQL诊断相关的通用工具类
主要类/函数：
    - SQLFingerprint: SQL指纹生成器
    - IssueClassifier: 问题分类器
    - ScoreCalculator: 评分计算器
    - PrioritySorter: 优先级排序器
    - MetricsAggregator: 指标聚合器

版本: 3.0.0
作者: AI Assistant
创建时间: 2026-04-23
"""

import hashlib
import re
from typing import Any, Dict, List

from dbskiter.db_diagnose.models import DiagnoseLevel
from dbskiter.shared.sql_utils import extract_tables as _shared_extract_tables


class SQLFingerprint:
    """
    SQL指纹生成器

    功能:
        - 生成SQL指纹用于相似查询识别
        - 标准化SQL用于比较
    """

    @staticmethod
    def generate(sql: str) -> str:
        """
        生成SQL指纹

        参数:
            sql: SQL语句

        返回:
            str: SQL指纹
        """
        if not sql:
            return ""

        # 标准化SQL
        normalized = SQLFingerprint.normalize(sql)

        # 生成MD5指纹
        return hashlib.md5(normalized.encode()).hexdigest()[:16]

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
    def similarity(sql1: str, sql2: str) -> float:
        """
        计算两个SQL的相似度

        参数:
            sql1: 第一个SQL
            sql2: 第二个SQL

        返回:
            float: 相似度 (0-1)
        """
        fp1 = SQLFingerprint.normalize(sql1)
        fp2 = SQLFingerprint.normalize(sql2)

        if fp1 == fp2:
            return 1.0

        # 简单的Jaccard相似度
        set1 = set(fp1.split())
        set2 = set(fp2.split())

        if not set1 and not set2:
            return 1.0

        intersection = len(set1 & set2)
        union = len(set1 | set2)

        return intersection / union if union > 0 else 0.0


class IssueClassifier:
    """
    问题分类器

    功能:
        - 自动分类诊断问题
        - 确定问题级别
    """

    # 问题模式定义
    PATTERNS = {
        "full_table_scan": {
            "patterns": [r'full\s+table\s+scan', r'type.*all', r'using\s+filesort'],
            "level": DiagnoseLevel.HIGH,
            "category": "performance"
        },
        "missing_index": {
            "patterns": [r'missing\s+index', r'no\s+index', r'index\s+not\s+used'],
            "level": DiagnoseLevel.HIGH,
            "category": "index"
        },
        "select_star": {
            "patterns": [r'select\s+\*'],
            "level": DiagnoseLevel.LOW,
            "category": "best_practice"
        },
        "implicit_conversion": {
            "patterns": [r'implicit\s+conversion', r'type\s+mismatch'],
            "level": DiagnoseLevel.MEDIUM,
            "category": "data_type"
        },
        "cartesian_product": {
            "patterns": [r'cartesian', r'cross\s+join', r'no\s+join\s+condition'],
            "level": DiagnoseLevel.CRITICAL,
            "category": "join"
        },
    }

    @staticmethod
    def classify(issue_text: str) -> Dict[str, Any]:
        """
        分类问题

        参数:
            issue_text: 问题描述

        返回:
            Dict: 分类结果
        """
        issue_lower = issue_text.lower()

        for issue_type, config in IssueClassifier.PATTERNS.items():
            for pattern in config["patterns"]:
                if re.search(pattern, issue_lower):
                    return {
                        "type": issue_type,
                        "level": config["level"],
                        "level_value": config["level"].value,
                        "category": config["category"]
                    }

        return {
            "type": "unknown",
            "level": DiagnoseLevel.LOW,
            "level_value": DiagnoseLevel.LOW.value,
            "category": "other"
        }

    @staticmethod
    def get_level_score(level: DiagnoseLevel) -> int:
        """
        获取级别分数

        参数:
            level: 诊断级别

        返回:
            int: 分数
        """
        scores = {
            DiagnoseLevel.CRITICAL: 100,
            DiagnoseLevel.HIGH: 50,
            DiagnoseLevel.MEDIUM: 20,
            DiagnoseLevel.LOW: 5,
            DiagnoseLevel.INFO: 1,
        }
        return scores.get(level, 0)


class ScoreCalculator:
    """
    评分计算器

    功能:
        - 计算SQL质量分数
        - 综合评估诊断结果
    """

    @staticmethod
    def calculate_sql_score(issues: List[Dict[str, Any]]) -> float:
        """
        计算SQL质量分数

        参数:
            issues: 问题列表

        返回:
            float: 分数 (0-100)
        """
        if not issues:
            return 100.0

        total_deduction = 0

        for issue in issues:
            level_str = issue.get("level", "low")
            try:
                level = DiagnoseLevel(level_str)
                deduction = IssueClassifier.get_level_score(level)
            except ValueError:
                deduction = 5  # 默认低级别扣分

            total_deduction += deduction

        return max(0.0, 100.0 - total_deduction)

    @staticmethod
    def calculate_health_score(metrics: Dict[str, float]) -> float:
        """
        计算健康度分数

        参数:
            metrics: 性能指标

        返回:
            float: 健康度分数
        """
        score = 100.0

        # CPU使用率扣分
        cpu = metrics.get("cpu_usage", 0)
        if cpu > 80:
            score -= 20
        elif cpu > 60:
            score -= 10

        # 内存使用率扣分
        memory = metrics.get("memory_usage", 0)
        if memory > 80:
            score -= 20
        elif memory > 60:
            score -= 10

        # 连接数扣分
        connections = metrics.get("connections", 0)
        max_connections = metrics.get("max_connections", 100)
        if max_connections > 0:
            connection_ratio = connections / max_connections
            if connection_ratio > 0.8:
                score -= 15
            elif connection_ratio > 0.6:
                score -= 5

        return max(0.0, score)


class PrioritySorter:
    """
    优先级排序器

    功能:
        - 按优先级排序诊断结果
        - 筛选高优先级问题
    """

    @staticmethod
    def sort_by_priority(
        items: List[Dict[str, Any]],
        priority_key: str = "priority"
    ) -> List[Dict[str, Any]]:
        """
        按优先级排序

        参数:
            items: 待排序列表
            priority_key: 优先级字段名

        返回:
            List: 排序后的列表
        """
        priority_order = {
            "critical": 0,
            "high": 1,
            "medium": 2,
            "low": 3,
            "info": 4,
        }

        return sorted(
            items,
            key=lambda x: priority_order.get(x.get(priority_key, "low"), 5)
        )

    @staticmethod
    def filter_by_min_priority(
        items: List[Dict[str, Any]],
        min_priority: str,
        priority_key: str = "priority"
    ) -> List[Dict[str, Any]]:
        """
        按最小优先级筛选

        参数:
            items: 待筛选列表
            min_priority: 最小优先级
            priority_key: 优先级字段名

        返回:
            List: 筛选后的列表
        """
        priority_order = {
            "critical": 0,
            "high": 1,
            "medium": 2,
            "low": 3,
            "info": 4,
        }

        min_level = priority_order.get(min_priority, 3)

        return [
            item for item in items
            if priority_order.get(item.get(priority_key, "low"), 5) <= min_level
        ]


class MetricsAggregator:
    """
    指标聚合器

    功能:
        - 聚合多个诊断结果
        - 生成汇总统计
    """

    @staticmethod
    def aggregate_issues(results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        聚合问题统计

        参数:
            results: 诊断结果列表

        返回:
            Dict: 聚合统计
        """
        total_issues = 0
        level_counts = {
            "critical": 0,
            "high": 0,
            "medium": 0,
            "low": 0,
            "info": 0,
        }
        category_counts: Dict[str, int] = {}

        for result in results:
            issues = result.get("issues", [])
            total_issues += len(issues)

            for issue in issues:
                level = issue.get("level", "low")
                level_counts[level] = level_counts.get(level, 0) + 1

                category = issue.get("category", "other")
                category_counts[category] = category_counts.get(category, 0) + 1

        return {
            "total_issues": total_issues,
            "level_counts": level_counts,
            "category_counts": category_counts,
        }

    @staticmethod
    def calculate_averages(metrics_list: List[Dict[str, float]]) -> Dict[str, float]:
        """
        计算平均值

        参数:
            metrics_list: 指标列表

        返回:
            Dict: 平均值
        """
        if not metrics_list:
            return {}

        sums: Dict[str, float] = {}
        counts: Dict[str, int] = {}

        for metrics in metrics_list:
            for key, value in metrics.items():
                if isinstance(value, (int, float)):
                    sums[key] = sums.get(key, 0) + value
                    counts[key] = counts.get(key, 0) + 1

        return {
            key: sums[key] / counts[key]
            for key in sums
            if counts[key] > 0
        }


class QueryExtractor:
    """
    查询提取器

    功能:
        - 从SQL中提取关键信息
        - 解析表名、列名等
    """

    @staticmethod
    def extract_tables(sql: str) -> List[str]:
        """
        提取表名
        (委托至 shared.sql_utils.extract_tables)

        参数:
            sql: SQL语句

        返回:
            List: 表名列表
        """
        return _shared_extract_tables(sql)

    @staticmethod
    def extract_columns(sql: str) -> List[str]:
        """
        提取列名

        参数:
            sql: SQL语句

        返回:
            List: 列名列表
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
    def extract_where_conditions(sql: str) -> List[Dict[str, str]]:
        """
        提取WHERE条件

        参数:
            sql: SQL语句

        返回:
            List: 条件列表
        """
        if not sql:
            return []

        conditions = []

        # WHERE 子句
        where_match = re.search(r'WHERE\s+(.+?)(?:ORDER|GROUP|LIMIT|$)', sql, re.IGNORECASE | re.DOTALL)
        if where_match:
            where_text = where_match.group(1).strip()
            # 简单分割条件
            for condition in re.split(r'\s+AND\s+', where_text, flags=re.IGNORECASE):
                condition = condition.strip()
                if condition:
                    # 提取列名和运算符
                    match = re.match(r'(\w+)\s*(=|<>|!=|<|>|<=|>=|LIKE|IN)', condition, re.IGNORECASE)
                    if match:
                        conditions.append({
                            "column": match.group(1),
                            "operator": match.group(2).upper(),
                            "full": condition
                        })

        return conditions


class TypeConverter:
    """
    类型转换器

    功能:
        - 安全地将数据库返回值转换为Python类型
        - 处理None值和类型不一致的情况
    """

    @staticmethod
    def safe_int(value: Any, default: int = 0) -> int:
        """
        安全转换为整数

        参数:
            value: 待转换的值
            default: 默认值

        返回:
            int: 转换后的整数

        示例:
            >>> TypeConverter.safe_int("123")
            123
            >>> TypeConverter.safe_int(None, 0)
            0
            >>> TypeConverter.safe_int("abc", 0)
            0
        """
        if value is None:
            return default
        try:
            return int(str(value))
        except (ValueError, TypeError):
            return default

    @staticmethod
    def safe_float(value: Any, default: float = 0.0) -> float:
        """
        安全转换为浮点数

        参数:
            value: 待转换的值
            default: 默认值

        返回:
            float: 转换后的浮点数

        示例:
            >>> TypeConverter.safe_float("123.45")
            123.45
            >>> TypeConverter.safe_float(None, 0.0)
            0.0
        """
        if value is None:
            return default
        try:
            return float(str(value))
        except (ValueError, TypeError):
            return default

    @staticmethod
    def safe_str(value: Any, default: str = "") -> str:
        """
        安全转换为字符串

        参数:
            value: 待转换的值
            default: 默认值

        返回:
            str: 转换后的字符串
        """
        if value is None:
            return default
        try:
            return str(value)
        except (ValueError, TypeError):
            return default
