"""
执行计划分析器 - 深度SQL执行计划解析与优化建议

文件功能：提供数据库执行计划的深度分析能力
主要类：
    - ExecutionPlanAnalyzer: 执行计划分析器主类
    - PlanNode: 执行计划节点
    - IndexSuggestion: 索引建议
    - PlanIssue: 执行计划问题

作者：Magiczc
创建时间：2026-04-22
版本：3.0.0（生产级重构版）
"""

import logging
import re
from typing import Dict, Any, List, Optional, Tuple, Set
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from dbskiter.shared.unified_connector import UnifiedConnector
from dbskiter.shared.error_handler import create_error_response, create_success_response, handle_exception
from dbskiter.shared.validators import sanitize_sql

logger = logging.getLogger(__name__)


class AccessType(str, Enum):
    """数据访问类型"""
    FULL_TABLE_SCAN = "full_table_scan"      # 全表扫描
    INDEX_SCAN = "index_scan"                # 索引扫描
    INDEX_RANGE = "index_range"              # 索引范围扫描
    INDEX_UNIQUE = "index_unique"            # 唯一索引查找
    REF = "ref"                              # 非唯一索引查找
    EQ_REF = "eq_ref"                        # 唯一索引查找
    CONST = "const"                          # 常量
    SYSTEM = "system"                        # 系统表
    RANGE = "range"                          # 范围扫描
    ALL = "all"                              # 全表扫描


class IssueSeverity(str, Enum):
    """问题严重级别"""
    CRITICAL = "critical"    # 严重
    HIGH = "high"            # 高危
    MEDIUM = "medium"        # 中危
    LOW = "low"              # 低危
    INFO = "info"            # 提示


class IssueType(str, Enum):
    """问题类型"""
    FULL_SCAN = "full_scan"                    # 全表扫描
    MISSING_INDEX = "missing_index"            # 缺少索引
    FILESORT = "filesort"                      # 文件排序
    TEMP_TABLE = "temp_table"                  # 临时表
    JOIN_BUFFER = "join_buffer"                # 连接缓冲
    IMPLICIT_CAST = "implicit_cast"            # 隐式类型转换
    FUNCTION_ON_COLUMN = "function_on_column"  # 列上使用函数
    WILD_CARD_PREFIX = "wild_card_prefix"      # 通配符前缀
    NOT_IN_NULL = "not_in_null"                # NOT IN NULL问题
    LARGE_OFFSET = "large_offset"              # 大偏移量
    SELECT_STAR = "select_star"                # SELECT *


@dataclass
class IndexSuggestion:
    """索引建议"""
    table_name: str
    column_names: List[str]
    index_name: str
    reason: str
    priority: str  # high, medium, low
    create_sql: str
    expected_improvement: str
    issue_type: IssueType


@dataclass
class PlanIssue:
    """执行计划问题"""
    severity: IssueSeverity
    issue_type: IssueType
    table_name: str
    description: str
    suggestion: Optional[IndexSuggestion] = None
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PlanNode:
    """执行计划节点"""
    id: int
    select_type: str
    table: str
    partitions: Optional[str]
    access_type: AccessType
    possible_keys: List[str]
    key: Optional[str]
    key_len: Optional[str]
    ref: Optional[str]
    rows: int
    filtered: float
    extra: str
    children: List['PlanNode'] = field(default_factory=list)


@dataclass
class PlanAnalysis:
    """执行计划分析结果"""
    sql: str
    sql_type: str
    nodes: List[PlanNode]
    issues: List[PlanIssue]
    index_suggestions: List[IndexSuggestion]
    total_cost: float
    total_rows: int
    execution_time_ms: Optional[float]
    warnings: List[str]
    optimized_sql: Optional[str] = None

    def summary(self) -> str:
        """生成分析摘要"""
        critical = sum(1 for i in self.issues if i.severity == IssueSeverity.CRITICAL)
        high = sum(1 for i in self.issues if i.severity == IssueSeverity.HIGH)
        medium = sum(1 for i in self.issues if i.severity == IssueSeverity.MEDIUM)

        lines = [
            f"SQL分析摘要:",
            f"  SQL类型: {self.sql_type}",
            f"  执行计划节点: {len(self.nodes)}个",
            f"  发现问题: {critical}个严重, {high}个高危, {medium}个中危",
            f"  索引建议: {len(self.index_suggestions)}个",
            f"  预估扫描行数: {self.total_rows:,}",
        ]

        if self.execution_time_ms:
            lines.append(f"  执行时间: {self.execution_time_ms:.2f}ms")

        return "\n".join(lines)


class ExecutionPlanAnalyzer:
    """
    执行计划分析器

    功能：
        1. 获取SQL执行计划（EXPLAIN）
        2. 解析执行计划结构
        3. 识别性能问题
        4. 生成索引优化建议
        5. 提供SQL重写建议

    支持数据库：
        - MySQL / MariaDB
        - PostgreSQL
        - Oracle（基础支持）

    使用示例：
        >>> analyzer = ExecutionPlanAnalyzer(connector)
        >>> result = analyzer.analyze("SELECT * FROM users WHERE email = 'test@test.com'")
        >>> print(result.summary())
        >>> for issue in result.issues:
        ...     print(f"[{issue.severity}] {issue.description}")
    """

    # 需要索引的访问类型
    NEED_INDEX_TYPES = {AccessType.FULL_TABLE_SCAN, AccessType.ALL}

    # 高危操作标识
    HIGH_COST_OPERATIONS = {
        'Using filesort': '文件排序，建议添加索引避免排序',
        'Using temporary': '使用临时表，考虑优化GROUP BY或ORDER BY',
        'Using join buffer': '使用连接缓冲，建议优化JOIN条件',
        'Range checked for each record': '逐行检查范围，索引使用不佳',
    }

    def __init__(self, connector: UnifiedConnector):
        """
        初始化执行计划分析器

        参数:
            connector: UnifiedConnector 实例
        """
        self.connector = connector
        self.dialect = connector.dialect.lower()
        logger.info(f"ExecutionPlanAnalyzer 初始化完成 (dialect={self.dialect})")

    def analyze(self, sql: str, params: Optional[Dict[str, Any]] = None) -> PlanAnalysis:
        """
        深度分析SQL执行计划

        参数:
            sql: SQL语句
            params: 查询参数

        返回:
            PlanAnalysis: 分析结果
        """
        sanitized_sql = sanitize_sql(sql)
        logger.info(f"分析执行计划: {sanitized_sql}")

        try:
            # 1. 获取执行计划
            plan_rows = self._get_execution_plan(sql, params)

            # 2. 解析执行计划节点
            nodes = self._parse_plan_nodes(plan_rows)

            # 3. 识别问题
            issues = self._identify_issues(nodes, sql)

            # 4. 生成索引建议
            index_suggestions = self._generate_index_suggestions(issues, nodes)

            # 5. 计算总成本
            total_cost, total_rows = self._calculate_cost(nodes)

            # 6. 生成优化SQL
            optimized_sql = self._generate_optimized_sql(sql, issues)

            # 7. 收集警告
            warnings = self._collect_warnings(nodes)

            # 8. 确定SQL类型
            sql_type = self._determine_sql_type(sql)

            return PlanAnalysis(
                sql=sql,
                sql_type=sql_type,
                nodes=nodes,
                issues=issues,
                index_suggestions=index_suggestions,
                total_cost=total_cost,
                total_rows=total_rows,
                execution_time_ms=None,  # 可在实际执行后填充
                warnings=warnings,
                optimized_sql=optimized_sql
            )

        except Exception as e:
            logger.error(f"执行计划分析失败: {e}")
            # 返回空分析结果
            return PlanAnalysis(
                sql=sql,
                sql_type=self._determine_sql_type(sql),
                nodes=[],
                issues=[],
                index_suggestions=[],
                total_cost=0,
                total_rows=0,
                execution_time_ms=None,
                warnings=[f"分析失败: {str(e)}"]
            )

    def _get_execution_plan(self, sql: str, params: Optional[Dict[str, Any]] = None) -> List[Tuple]:
        """
        获取执行计划原始数据

        参数:
            sql: SQL语句
            params: 查询参数

        返回:
            List[Tuple]: 执行计划行数据
        """
        if 'mysql' in self.dialect:
            return self._get_mysql_execution_plan(sql, params)
        elif 'postgresql' in self.dialect:
            return self._get_postgresql_execution_plan(sql, params)
        elif 'oracle' in self.dialect:
            return self._get_oracle_execution_plan(sql, params)
        else:
            logger.warning(f"数据库类型 {self.dialect} 的执行计划获取未完全实现")
            return []

    def _get_mysql_execution_plan(self, sql: str, params: Optional[Dict[str, Any]] = None) -> List[Tuple]:
        """获取MySQL执行计划"""
        try:
            # 使用EXPLAIN FORMAT=JSON获取更详细的计划
            explain_sql = f"EXPLAIN {sql}"
            result = self.connector.execute(explain_sql, params)
            return result.rows if result else []
        except Exception as e:
            logger.error(f"获取MySQL执行计划失败: {e}")
            return []

    def _get_postgresql_execution_plan(self, sql: str, params: Optional[Dict[str, Any]] = None) -> List[Tuple]:
        """获取PostgreSQL执行计划"""
        try:
            explain_sql = f"EXPLAIN (FORMAT TEXT) {sql}"
            result = self.connector.execute(explain_sql, params)
            return result.rows if result else []
        except Exception as e:
            logger.error(f"获取PostgreSQL执行计划失败: {e}")
            return []

    def _get_oracle_execution_plan(self, sql: str, params: Optional[Dict[str, Any]] = None) -> List[Tuple]:
        """
        获取Oracle执行计划

        使用DBMS_XPLAN获取格式化的执行计划

        参数:
            sql: SQL语句
            params: 查询参数

        返回:
            List[Tuple]: 执行计划行数据
        """
        try:
            # 替换绑定变量为字面值（EXPLAIN PLAN不支持绑定变量）
            explain_sql = sql
            import re
            explain_sql = re.sub(r':\d+', "'X'", explain_sql)
            explain_sql = re.sub(r':[a-zA-Z_]\w*', "'X'", explain_sql)

            # 1. 生成执行计划
            plan_sql = f"EXPLAIN PLAN FOR {explain_sql}"

            # 直接使用底层连接执行，避免自动提交问题
            raw_connector = None
            if hasattr(self.connector, '_connector'):
                raw_connector = self.connector._connector
            else:
                raw_connector = self.connector

            # 获取JDBC连接并直接执行
            if hasattr(raw_connector, '_conn'):
                conn = raw_connector._conn
                cursor = conn.cursor()
                try:
                    if params:
                        cursor.execute(plan_sql, params)
                    else:
                        cursor.execute(plan_sql)
                finally:
                    cursor.close()
            else:
                # 回退到普通execute
                try:
                    self.connector.execute(plan_sql, params)
                except Exception:
                    pass

            # 2. 获取格式化的执行计划
            result = self.connector.execute("""
                SELECT * FROM TABLE(DBMS_XPLAN.DISPLAY(
                    table_name => 'PLAN_TABLE',
                    format => 'TYPICAL'
                ))
            """)

            if result and result.rows:
                # 解析DBMS_XPLAN输出为结构化数据
                return self._parse_oracle_plan_output(result.rows)
            return []

        except Exception as e:
            logger.warning(f"获取Oracle执行计划失败（非致命）: {e}")
            return []

    def _parse_oracle_plan_output(self, plan_rows: List[Tuple]) -> List[Tuple]:
        """
        解析Oracle DBMS_XPLAN输出

        参数:
            plan_rows: DBMS_XPLAN输出行

        返回:
            List[Tuple]: 解析后的执行计划数据
        """
        parsed_rows = []

        for row in plan_rows:
            plan_line = row[0] if row else ""

            # 跳过标题行和分隔线
            if not plan_line or plan_line.startswith('-') or 'Plan hash value' in plan_line:
                continue

            # 跳过空行和说明文字
            if not plan_line.startswith('|'):
                continue

            # 跳过列标题行（包含"Id"、"Operation"、"Name"等）
            if 'Id' in plan_line and 'Operation' in plan_line and 'Name' in plan_line:
                continue

            # 解析执行计划行
            # 格式示例: |   0 | SELECT STATEMENT  |      |       |       |            |          |
            # 或者: |*  1 |  TABLE ACCESS FULL| EMP  |     1 |    37 |     3   (0)| 00:00:01 |
            if '|' in plan_line:
                parts = [p.strip() for p in plan_line.split('|')]
                parts = [p for p in parts if p]  # 移除空字符串

                if len(parts) >= 2:
                    try:
                        # 提取ID（可能带有*表示谓词）
                        id_part = parts[0].replace('*', '').strip()
                        try:
                            plan_id = int(id_part)
                        except ValueError:
                            # 如果ID不是数字，可能是标题行，跳过
                            continue

                        # 提取操作信息
                        operation = parts[1] if len(parts) > 1 else ""

                        # 提取对象名
                        object_name = parts[2] if len(parts) > 2 else ""

                        # 提取行数估算
                        rows_est = parts[3] if len(parts) > 3 else "0"
                        try:
                            rows = int(rows_est.replace(',', ''))
                        except Exception:
                            rows = 0

                        # 提取成本
                        cost_str = parts[5] if len(parts) > 5 else "0"
                        try:
                            cost = int(cost_str.split()[0].replace(',', ''))
                        except Exception:
                            cost = 0

                        # 提取访问方式
                        access_type = AccessType.ALL
                        if 'INDEX' in operation.upper():
                            if 'UNIQUE' in operation.upper():
                                access_type = AccessType.INDEX_UNIQUE
                            else:
                                access_type = AccessType.INDEX_SCAN
                        elif 'FULL' in operation.upper():
                            access_type = AccessType.FULL_TABLE_SCAN

                        parsed_rows.append((
                            plan_id,           # id
                            'SIMPLE',          # select_type
                            object_name,       # table
                            None,              # partitions
                            access_type.value, # type
                            [],                # possible_keys
                            None,              # key
                            None,              # key_len
                            None,              # ref
                            rows,              # rows
                            100.0,             # filtered
                            operation          # Extra
                        ))
                    except Exception as e:
                        logger.warning(f"解析执行计划行失败: {e}, line={plan_line}")
                        continue

        return parsed_rows

    def _parse_plan_nodes(self, plan_rows: List[Tuple]) -> List[PlanNode]:
        """
        解析执行计划节点

        参数:
            plan_rows: 执行计划原始数据

        返回:
            List[PlanNode]: 解析后的节点列表
        """
        nodes = []

        if not plan_rows:
            return nodes

        # MySQL EXPLAIN输出解析
        if 'mysql' in self.dialect:
            for idx, row in enumerate(plan_rows):
                try:
                    # MySQL EXPLAIN返回列：
                    # id, select_type, table, partitions, type, possible_keys, key, key_len, ref, rows, filtered, Extra
                    node = PlanNode(
                        id=row[0] if len(row) > 0 else idx,
                        select_type=row[1] if len(row) > 1 else "SIMPLE",
                        table=row[2] if len(row) > 2 else "",
                        partitions=row[3] if len(row) > 3 else None,
                        access_type=self._parse_access_type(row[4] if len(row) > 4 else "ALL"),
                        possible_keys=self._parse_keys(row[5] if len(row) > 5 else None),
                        key=row[6] if len(row) > 6 else None,
                        key_len=row[7] if len(row) > 7 else None,
                        ref=row[8] if len(row) > 8 else None,
                        rows=row[9] if len(row) > 9 else 0,
                        filtered=row[10] if len(row) > 10 else 100.0,
                        extra=row[11] if len(row) > 11 else ""
                    )
                    nodes.append(node)
                except Exception as e:
                    logger.warning(f"解析执行计划行失败: {e}, row={row}")
                    continue

        # Oracle执行计划解析（已由_parse_oracle_plan_output预处理）
        elif 'oracle' in self.dialect:
            for idx, row in enumerate(plan_rows):
                try:
                    # row格式: (id, select_type, table, partitions, type, possible_keys, key, key_len, ref, rows, filtered, extra)
                    node = PlanNode(
                        id=row[0] if len(row) > 0 else idx,
                        select_type=row[1] if len(row) > 1 else "SIMPLE",
                        table=row[2] if len(row) > 2 else "",
                        partitions=row[3] if len(row) > 3 else None,
                        access_type=self._parse_access_type(row[4] if len(row) > 4 else "ALL"),
                        possible_keys=self._parse_keys(row[5] if len(row) > 5 else None),
                        key=row[6] if len(row) > 6 else None,
                        key_len=row[7] if len(row) > 7 else None,
                        ref=row[8] if len(row) > 8 else None,
                        rows=row[9] if len(row) > 9 else 0,
                        filtered=row[10] if len(row) > 10 else 100.0,
                        extra=row[11] if len(row) > 11 else ""
                    )
                    nodes.append(node)
                except Exception as e:
                    logger.warning(f"解析执行计划行失败: {e}, row={row}")
                    continue

        return nodes

    def _parse_access_type(self, access_type_str: str) -> AccessType:
        """解析访问类型"""
        if not access_type_str:
            return AccessType.ALL

        access_type_map = {
            'system': AccessType.SYSTEM,
            'const': AccessType.CONST,
            'eq_ref': AccessType.EQ_REF,
            'ref': AccessType.REF,
            'range': AccessType.RANGE,
            'index': AccessType.INDEX_SCAN,
            'ALL': AccessType.ALL,
            'all': AccessType.ALL,
            'fulltext': AccessType.INDEX_SCAN,
            'ref_or_null': AccessType.REF,
            'index_merge': AccessType.INDEX_SCAN,
            'unique_subquery': AccessType.INDEX_UNIQUE,
            'index_subquery': AccessType.INDEX_SCAN,
        }

        return access_type_map.get(access_type_str, AccessType.ALL)

    def _parse_keys(self, keys_str: Optional[str]) -> List[str]:
        """解析可能的键列表"""
        if not keys_str:
            return []
        return [k.strip() for k in keys_str.split(',') if k.strip()]

    def _identify_issues(self, nodes: List[PlanNode], sql: str) -> List[PlanIssue]:
        """
        识别执行计划中的问题

        参数:
            nodes: 执行计划节点
            sql: 原始SQL

        返回:
            List[PlanIssue]: 问题列表
        """
        issues = []

        for node in nodes:
            # 1. 全表扫描检测
            if node.access_type in self.NEED_INDEX_TYPES:
                # 处理 rows 为 None 的情况
                node_rows = node.rows if node.rows is not None else 0
                if node_rows > 1000:  # 扫描行数超过1000
                    severity = IssueSeverity.HIGH if node_rows > 10000 else IssueSeverity.MEDIUM
                    issue = PlanIssue(
                        severity=severity,
                        issue_type=IssueType.FULL_SCAN,
                        table_name=node.table,
                        description=f"表 {node.table} 发生全表扫描，预估扫描 {node_rows:,} 行",
                        details={"rows": node_rows, "access_type": node.access_type.value}
                    )
                    issues.append(issue)

            # 2. 文件排序检测
            if node.extra and 'Using filesort' in node.extra:
                issue = PlanIssue(
                    severity=IssueSeverity.MEDIUM,
                    issue_type=IssueType.FILESORT,
                    table_name=node.table,
                    description=f"表 {node.table} 使用文件排序，建议添加适当索引",
                    details={"extra": node.extra}
                )
                issues.append(issue)

            # 3. 临时表检测
            if node.extra and 'Using temporary' in node.extra:
                issue = PlanIssue(
                    severity=IssueSeverity.MEDIUM,
                    issue_type=IssueType.TEMP_TABLE,
                    table_name=node.table,
                    description=f"表 {node.table} 使用临时表，考虑优化GROUP BY或ORDER BY",
                    details={"extra": node.extra}
                )
                issues.append(issue)

            # 4. 缺少索引检测
            if node.access_type in self.NEED_INDEX_TYPES and not node.key:
                issue = PlanIssue(
                    severity=IssueSeverity.HIGH,
                    issue_type=IssueType.MISSING_INDEX,
                    table_name=node.table,
                    description=f"表 {node.table} 可能缺少合适索引",
                    details={"possible_keys": node.possible_keys}
                )
                issues.append(issue)

        # 5. SQL模式检测
        sql_issues = self._analyze_sql_patterns(sql)
        issues.extend(sql_issues)

        return issues

    def _analyze_sql_patterns(self, sql: str) -> List[PlanIssue]:
        """分析SQL模式问题"""
        issues = []
        sql_upper = sql.upper()

        # SELECT * 检测
        if 'SELECT *' in sql_upper:
            issues.append(PlanIssue(
                severity=IssueSeverity.LOW,
                issue_type=IssueType.SELECT_STAR,
                table_name="",
                description="使用SELECT *，建议只查询需要的列",
                details={}
            ))

        # 大偏移量检测
        offset_match = re.search(r'LIMIT\s+\d+\s*,\s*(\d+)', sql_upper)
        if offset_match:
            offset = int(offset_match.group(1))
            if offset > 10000:
                issues.append(PlanIssue(
                    severity=IssueSeverity.MEDIUM,
                    issue_type=IssueType.LARGE_OFFSET,
                    table_name="",
                    description=f"使用大偏移量 LIMIT {offset}，建议使用覆盖索引或延迟关联优化",
                    details={"offset": offset}
                ))

        # 列上使用函数检测
        func_pattern = r'WHERE\s+\w*\s*\(\s*\w+\s*\)'
        if re.search(func_pattern, sql_upper):
            issues.append(PlanIssue(
                severity=IssueSeverity.HIGH,
                issue_type=IssueType.FUNCTION_ON_COLUMN,
                table_name="",
                description="WHERE条件中对列使用函数，会导致索引失效",
                details={}
            ))

        return issues

    def _generate_index_suggestions(self, issues: List[PlanIssue], nodes: List[PlanNode]) -> List[IndexSuggestion]:
        """
        生成索引优化建议

        参数:
            issues: 识别出的问题
            nodes: 执行计划节点

        返回:
            List[IndexSuggestion]: 索引建议列表
        """
        suggestions = []

        for issue in issues:
            if issue.issue_type in (IssueType.FULL_SCAN, IssueType.MISSING_INDEX, IssueType.FILESORT):
                # 为每个表生成索引建议
                table = issue.table_name
                if not table:
                    continue

                # 根据问题类型确定建议
                if issue.issue_type == IssueType.FILESORT:
                    suggestion = IndexSuggestion(
                        table_name=table,
                        column_names=["需要分析的排序列"],
                        index_name=f"idx_{table}_sort",
                        reason=f"为表 {table} 添加排序索引，避免文件排序",
                        priority="medium",
                        create_sql=f"CREATE INDEX idx_{table}_sort ON {table} (排序列);",
                        expected_improvement="避免filesort，减少排序时间",
                        issue_type=issue.issue_type
                    )
                else:
                    suggestion = IndexSuggestion(
                        table_name=table,
                        column_names=["需要分析的WHERE列"],
                        index_name=f"idx_{table}_filter",
                        reason=f"为表 {table} 添加过滤条件索引，避免全表扫描",
                        priority="high" if issue.severity == IssueSeverity.HIGH else "medium",
                        create_sql=f"CREATE INDEX idx_{table}_filter ON {table} (WHERE条件列);",
                        expected_improvement=f"减少扫描行数从 {issue.details.get('rows', 'N/A')} 到估计 <100",
                        issue_type=issue.issue_type
                    )

                suggestions.append(suggestion)

        return suggestions

    def _calculate_cost(self, nodes: List[PlanNode]) -> Tuple[float, int]:
        """
        计算执行计划总成本

        参数:
            nodes: 执行计划节点

        返回:
            Tuple[float, int]: (总成本, 总行数)
        """
        total_cost = 0.0
        total_rows = 0

        for node in nodes:
            # 简单成本模型：行数 * 访问类型成本系数
            access_cost_map = {
                AccessType.SYSTEM: 1,
                AccessType.CONST: 1,
                AccessType.EQ_REF: 2,
                AccessType.REF: 5,
                AccessType.RANGE: 10,
                AccessType.INDEX_SCAN: 20,
                AccessType.FULL_TABLE_SCAN: 100,
                AccessType.ALL: 100,
            }

            cost_factor = access_cost_map.get(node.access_type, 50)
            # 处理 rows 为 None 的情况
            node_rows = node.rows if node.rows is not None else 0
            node_cost = node_rows * cost_factor
            total_cost += node_cost
            total_rows += node_rows

        return total_cost, total_rows

    def _generate_optimized_sql(self, sql: str, issues: List[PlanIssue]) -> Optional[str]:
        """
        生成优化后的SQL

        参数:
            sql: 原始SQL
            issues: 识别的问题

        返回:
            Optional[str]: 优化后的SQL，如果无法优化则返回None
        """
        optimized = sql

        # 替换SELECT *
        if any(i.issue_type == IssueType.SELECT_STAR for i in issues):
            # 这里需要Schema信息才能准确替换，暂时标记
            pass

        return optimized if optimized != sql else None

    def _collect_warnings(self, nodes: List[PlanNode]) -> List[str]:
        """收集警告信息"""
        warnings = []

        for node in nodes:
            # 处理 filtered 为 None 的情况
            filtered = node.filtered if node.filtered is not None else 100.0
            if filtered < 100:
                warnings.append(f"表 {node.table} 过滤率低: {filtered}%")

        return warnings

    def _determine_sql_type(self, sql: str) -> str:
        """确定SQL类型"""
        sql_upper = sql.strip().upper()

        if sql_upper.startswith('SELECT'):
            return 'SELECT'
        elif sql_upper.startswith('INSERT'):
            return 'INSERT'
        elif sql_upper.startswith('UPDATE'):
            return 'UPDATE'
        elif sql_upper.startswith('DELETE'):
            return 'DELETE'
        elif sql_upper.startswith('CREATE'):
            return 'CREATE'
        elif sql_upper.startswith('ALTER'):
            return 'ALTER'
        else:
            return 'OTHER'

    def get_table_statistics(self, table_name: str) -> Dict[str, Any]:
        """
        获取表统计信息

        参数:
            table_name: 表名

        返回:
            Dict: 表统计信息
        """
        try:
            if 'mysql' in self.dialect:
                result = self.connector.execute("""
                    SELECT
                        table_rows,
                        ROUND(data_length / 1024 / 1024, 2) as data_mb,
                        ROUND(index_length / 1024 / 1024, 2) as index_mb
                    FROM information_schema.tables
                    WHERE table_schema = DATABASE()
                    AND table_name = %s
                """, (table_name,))

                if result.rows:
                    return {
                        "table_name": table_name,
                        "row_count": result.rows[0][0],
                        "data_size_mb": result.rows[0][1],
                        "index_size_mb": result.rows[0][2]
                    }

            return {"table_name": table_name, "error": "无法获取统计信息"}

        except Exception as e:
            logger.error(f"获取表统计信息失败: {e}")
            return {"table_name": table_name, "error": str(e)}
