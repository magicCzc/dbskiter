"""
SQL 注入检测器 V2 - 基于 AST 的深度分析

优化点：
1. 使用 sqlparse 进行 AST 解析，而非简单正则
2. 语义分析识别注入模式
3. 支持参数化查询验证
4. 提供详细的修复建议

作者：Trae AI
创建时间：2026-04-20
"""
import warnings
warnings.warn(
    'This module is deprecated. Use the non-v2 version instead.',
    DeprecationWarning,
    stacklevel=2,
)



import re
import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Any, Optional, Set
from enum import Enum
import logging

try:
    import sqlparse
    from sqlparse.sql import Statement
    from sqlparse.tokens import Keyword
    SQLPARSE_AVAILABLE = True
except ImportError:
    SQLPARSE_AVAILABLE = False
    logging.warning("sqlparse 未安装，将使用基础正则检测")

logger = logging.getLogger(__name__)


class RiskLevel(Enum):
    """风险等级"""
    CRITICAL = "critical"  # 确认注入
    HIGH = "high"          # 高度可疑
    MEDIUM = "medium"      # 中等风险
    LOW = "low"            # 低风险


class InjectionType(Enum):
    """注入类型"""
    BOOLEAN_BASED = "boolean_based"      # 布尔盲注
    TIME_BASED = "time_based"            # 时间盲注
    UNION_BASED = "union_based"          # UNION注入
    ERROR_BASED = "error_based"          # 错误注入
    STACKED_QUERY = "stacked_query"      # 堆叠查询
    COMMENT_BASED = "comment_based"      # 注释绕过
    SECOND_ORDER = "second_order"        # 二次注入


@dataclass
class SQLInjectionFinding:
    """SQL注入发现"""
    sql_hash: str
    sql_preview: str
    injection_type: InjectionType
    risk_level: RiskLevel
    confidence: float  # 0-1 置信度
    description: str
    vulnerable_clause: str
    suggestion: str
    detected_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict:
        return {
            "sql_hash": self.sql_hash,
            "sql_preview": self.sql_preview[:100],
            "injection_type": self.injection_type.value,
            "risk_level": self.risk_level.value,
            "confidence": round(self.confidence, 2),
            "description": self.description,
            "vulnerable_clause": self.vulnerable_clause,
            "suggestion": self.suggestion
        }


class SQLInjectionDetectorV2:
    """
    SQL 注入检测器 V2 - 基于 AST 的深度分析
    
    检测能力：
    1. 布尔盲注：OR 1=1, AND 1=1 等
    2. 时间盲注：SLEEP(), BENCHMARK() 等
    3. UNION 注入：UNION SELECT 等
    4. 错误注入：类型转换错误等
    5. 堆叠查询：分号分隔多语句
    6. 注释绕过：--, /* */, # 等
    
    使用示例：
        detector = SQLInjectionDetectorV2()
        
        # 分析 SQL
        result = detector.analyze_sql(
            "SELECT * FROM users WHERE id = %s",
            params={"id": "1 OR 1=1"}
        )
        
        if result["has_injection"]:
            print(f"发现注入: {result['findings'][0]['description']}")
    """
    
    # 时间延迟函数（各数据库）
    TIME_FUNCTIONS = {
        'mysql': ['SLEEP', 'BENCHMARK'],
        'postgresql': ['PG_SLEEP', 'GENERATE_SERIES'],
        'sqlite': ['RANDOMBLOB', 'PRINTF'],
        'oracle': ['DBMS_PIPE.RECEIVE_MESSAGE', 'DBMS_LOCK.SLEEP'],
        'mssql': ['WAITFOR DELAY', 'WAITFOR TIME']
    }
    
    # 危险函数
    DANGEROUS_FUNCTIONS = [
        'LOAD_FILE', 'INTO OUTFILE', 'INTO DUMPFILE',
        'XP_CMDSHELL', 'SP_OAMETHOD', 'SP_OACREATE',
        'UTL_HTTP', 'UTL_TCP', 'UTL_FILE', 'DBMS_XMLQUERY',
        'PG_READ_FILE', 'PG_LS_DIR', 'COPY_TO_PROGRAM'
    ]
    
    def __init__(self):
        self.findings: List[SQLInjectionFinding] = []
        self.known_safe_hashes: Set[str] = set()
        self._ast_available = SQLPARSE_AVAILABLE
    
    def _hash_sql(self, sql: str) -> str:
        """计算 SQL 哈希"""
        return hashlib.sha256(sql.encode()).hexdigest()[:16]
    
    def _get_sql_preview(self, sql: str, max_len: int = 100) -> str:
        """获取 SQL 预览"""
        if len(sql) <= max_len:
            return sql
        return sql[:max_len] + "..."
    
    def analyze_sql(self, sql: str, params: Optional[Dict] = None, 
                   dialect: str = "mysql") -> Dict[str, Any]:
        """
        深度分析 SQL 注入风险
        
        参数：
            sql: SQL 语句
            params: 查询参数（用于检测参数污染）
            dialect: 数据库类型
            
        返回：
            Dict: 分析结果
        """
        findings = []
        sql_hash = self._hash_sql(sql)
        sql_preview = self._get_sql_preview(sql)
        
        # 0. 多语句检测 (sqlparse 之前的原始字符串)
        if re.search(r";\s*(SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|EXEC|TRUNCATE)\b", sql, re.IGNORECASE):
            findings.append(SQLInjectionFinding(
                sql_hash=sql_hash,
                sql_preview=sql_preview,
                injection_type=InjectionType.STACKED_QUERY,
                risk_level=RiskLevel.CRITICAL,
                confidence=0.95,
                description="检测到堆叠查询注入 (多条SQL语句)",
                vulnerable_clause=sql[:100],
                suggestion="禁止多语句执行，使用参数化查询，严格输入验证"
            ))

        # 1. AST 结构分析（如果可用）
        if self._ast_available:
            ast_findings = self._analyze_ast(sql, sql_hash, sql_preview)
            findings.extend(ast_findings)

        # 2. 参数污染检测
        if params:
            param_findings = self._analyze_params(sql, params, sql_hash, sql_preview)
            findings.extend(param_findings)

        # 3. 语义模式检测（正则辅助）
        pattern_findings = self._analyze_patterns(sql, sql_hash, sql_preview, dialect)
        findings.extend(pattern_findings)

        # 4. 字符串拼接检测
        concat_findings = self._detect_string_concatenation(sql, sql_hash, sql_preview)
        findings.extend(concat_findings)
        
        # 去重（基于 SQL hash 和注入类型）
        unique_findings = self._deduplicate_findings(findings)
        
        # 计算整体风险
        risk_score = self._calculate_risk_score(unique_findings)
        has_injection = any(
            f.risk_level in (RiskLevel.CRITICAL, RiskLevel.HIGH) 
            for f in unique_findings
        )
        
        return {
            "sql_hash": sql_hash,
            "has_injection": has_injection,
            "risk_score": risk_score,
            "finding_count": len(unique_findings),
            "findings": [f.to_dict() for f in unique_findings],
            "recommendation": self._generate_recommendation(unique_findings)
        }
    
    def detect(self, sql: str, params: Optional[Dict] = None, 
               dialect: str = "mysql") -> Dict[str, Any]:
        """
        检测SQL注入（analyze_sql的别名，保持接口兼容性）
        
        参数：
            sql: SQL语句
            params: 查询参数
            dialect: 数据库类型
            
        返回：
            Dict: 检测结果
        """
        return self.analyze_sql(sql, params, dialect)
    
    def _analyze_ast(self, sql: str, sql_hash: str, sql_preview: str) -> List[SQLInjectionFinding]:
        """基于 AST 的结构分析"""
        findings = []
        
        try:
            parsed = sqlparse.parse(sql)
            
            for statement in parsed:
                # 分析 WHERE 子句
                where_clause = self._extract_where_clause(statement)
                if where_clause:
                    # 检测 OR 1=1 模式
                    or_findings = self._detect_or_tautology(where_clause, sql_hash, sql_preview)
                    findings.extend(or_findings)
                    
                    # 检测注释注入
                    comment_findings = self._detect_comment_injection(where_clause, sql_hash, sql_preview)
                    findings.extend(comment_findings)
                
                # 检测 UNION 注入
                union_findings = self._detect_union_injection(statement, sql_hash, sql_preview)
                findings.extend(union_findings)
                
                # 检测堆叠查询
                stacked_findings = self._detect_stacked_queries(statement, sql_hash, sql_preview)
                findings.extend(stacked_findings)
                
        except Exception as e:
            logger.warning(f"AST 分析失败: {e}")
        
        return findings
    
    def _extract_where_clause(self, statement: Statement) -> Optional[str]:
        """提取 WHERE 子句

        使用递归方式遍历所有token，处理sqlparse的嵌套结构
        """
        where_tokens = []
        in_where = False

        def _is_keyword(token, keyword: str) -> bool:
            """判断token是否为指定关键词（兼容sqlparse的子类型系统）"""
            if token.ttype is None:
                return False
            # 使用 in 判断，兼容 Token.Keyword.DML 等子类型
            try:
                return token.ttype in Keyword and token.value.upper() == keyword
            except TypeError:
                return False

        def _is_terminator(token) -> bool:
            """判断token是否为WHERE子句的终止关键词"""
            if token.ttype is None:
                return False
            try:
                if token.ttype not in Keyword:
                    return False
                val = token.value.upper().strip()
                # 支持复合关键词如 ORDER BY、GROUP BY
                return any(val == t or val.startswith(t + ' ') for t in ('ORDER', 'GROUP', 'LIMIT', 'UNION', 'HAVING'))
            except TypeError:
                return False

        def _traverse(tokens):
            nonlocal in_where
            for token in tokens:
                if _is_keyword(token, 'WHERE'):
                    in_where = True
                    continue
                if in_where and _is_terminator(token):
                    in_where = False
                    continue
                # 如果token有子token，递归处理子token，不收集父token的文本
                # 避免父节点和子节点文本重复收集
                if hasattr(token, 'tokens') and len(token.tokens) > 1:
                    _traverse(token.tokens)
                elif in_where:
                    where_tokens.append(str(token))

        _traverse(statement.tokens)
        return ' '.join(where_tokens) if where_tokens else None
    
    def _detect_or_tautology(self, where_clause: str, sql_hash: str, sql_preview: str) -> List[SQLInjectionFinding]:
        """检测 OR 恒真条件

        关键判断: 恒真条件本身不一定是注入(如 WHERE status='a' OR status='b'),
        只有在有用户输入痕迹时才报高风险。
        """
        findings = []
        where_upper = where_clause.upper()

        # 先检查是否有明显的用户输入痕迹
        has_input_trace = self._has_user_input_trace(where_clause)

        # 匹配 OR 恒真模式
        tautology_patterns = [
            (r"\bOR\s+['\"]?\d+['\"]?\s*=\s*['\"]?\d+['\"]?", "OR 数字恒真"),
            (r"\bOR\s+['\"].*?['\"]\s*=\s*['\"].*?['\"]", "OR 字符串恒真"),
            (r"\bOR\s+TRUE\b", "OR TRUE"),
            (r"\bOR\s+1\s*=\s*1\b", "OR 1=1"),
        ]

        matched = False
        for pattern, desc in tautology_patterns:
            if re.search(pattern, where_clause, re.IGNORECASE):
                matched = True
                break

        if matched:
            if has_input_trace:
                # 有用户输入痕迹 + 恒真条件 = 高风险
                findings.append(SQLInjectionFinding(
                    sql_hash=sql_hash,
                    sql_preview=sql_preview,
                    injection_type=InjectionType.BOOLEAN_BASED,
                    risk_level=RiskLevel.CRITICAL,
                    confidence=0.85,
                    description="WHERE 子句中存在恒真条件且检测到用户输入痕迹",
                    vulnerable_clause=where_clause[:100],
                    suggestion="使用参数化查询，避免直接拼接用户输入到 WHERE 条件"
                ))
            else:
                # 没有用户输入痕迹, 可能是正常业务逻辑, 只报低风险
                findings.append(SQLInjectionFinding(
                    sql_hash=sql_hash,
                    sql_preview=sql_preview,
                    injection_type=InjectionType.BOOLEAN_BASED,
                    risk_level=RiskLevel.LOW,
                    confidence=0.30,
                    description="WHERE 子句中存在恒真条件, 但未检测到用户输入痕迹, 可能是正常逻辑",
                    vulnerable_clause=where_clause[:100],
                    suggestion="请确认此 OR 条件是否为业务逻辑所需, 避免直接拼接用户输入"
                ))

        return findings

    def _has_user_input_trace(self, clause: str) -> bool:
        """检测 SQL 片段中是否有用户输入的痕迹

        判断依据:
        - 存在注释符 (-- , /* , #)
        - 单引号/双引号不平衡
        - 存在明显的字符串截断痕迹 (如 'value' 后面直接跟 OR)
        - 存在 ASCII/CHR 编码函数
        - 存在十六进制编码字符串
        """
        clause_upper = clause.upper()

        # 注释符
        if re.search(r"(--\s*$|--\s+[^'\"]|/\*|#\s*$)", clause, re.IGNORECASE):
            return True

        # 引号不平衡 (奇数个单引号或双引号)
        single_quotes = clause.count("'")
        double_quotes = clause.count('"')
        if single_quotes % 2 != 0 or double_quotes % 2 != 0:
            return True

        # ASCII/CHR 编码
        if re.search(r"\b(CHR\s*\(|ASCII\s*\(|CHAR\s*\()", clause_upper):
            return True

        # 十六进制字符串 (如 0x414243)
        if re.search(r"\b0x[0-9A-F]{4,}\b", clause, re.IGNORECASE):
            return True

        # 字符串后跟 OR/AND 且中间无运算符 (如 'admin' OR)
        if re.search(r"['\"]\s*\bOR\b", clause, re.IGNORECASE) or \
           re.search(r"['\"]\s*\bAND\b", clause, re.IGNORECASE):
            return True

        # 连续多个空格或制表符 (可能是手动构造的 payload)
        if re.search(r"  +|\t", clause):
            return True

        return False
    
    def _detect_comment_injection(self, where_clause: str, sql_hash: str, sql_preview: str) -> List[SQLInjectionFinding]:
        """检测注释注入"""
        findings = []
        
        # 危险的注释模式
        comment_patterns = [
            (r"--\s*$", "行尾注释", RiskLevel.HIGH),
            (r"/\*.*?\*/", "块注释", RiskLevel.MEDIUM),
            (r"#\s*$", "Hash 注释", RiskLevel.HIGH),
            (r";\s*--", "分号+注释", RiskLevel.CRITICAL),
        ]
        
        for pattern, desc, risk in comment_patterns:
            if re.search(pattern, where_clause, re.IGNORECASE):
                findings.append(SQLInjectionFinding(
                    sql_hash=sql_hash,
                    sql_preview=sql_preview,
                    injection_type=InjectionType.COMMENT_BASED,
                    risk_level=risk,
                    confidence=0.85,
                    description=f"检测到注释注入: {desc}",
                    vulnerable_clause=where_clause[:100],
                    suggestion="过滤或转义注释字符，使用参数化查询"
                ))
        
        return findings
    
    def _detect_union_injection(self, statement: Statement, sql_hash: str, sql_preview: str) -> List[SQLInjectionFinding]:
        """检测 UNION 注入

        正常的 UNION ALL 查询(如报表合并)不应误报,
        只有在有用户输入痕迹时才报高风险。
        """
        findings = []
        sql_str = str(statement)
        sql_upper = sql_str.upper()

        if not re.search(r"\bUNION\s+(ALL\s+)?SELECT\b", sql_upper):
            return findings

        # 有 UNION SELECT, 进一步判断是否有注入风险
        has_trace = self._has_user_input_trace(sql_str)

        # 检查 UNION 是否在 WHERE 子句之后(异常位置)
        where_pos = sql_upper.find("WHERE")
        union_pos = sql_upper.find("UNION")
        union_after_where = where_pos != -1 and union_pos > where_pos

        if has_trace or union_after_where:
            findings.append(SQLInjectionFinding(
                sql_hash=sql_hash,
                sql_preview=sql_preview,
                injection_type=InjectionType.UNION_BASED,
                risk_level=RiskLevel.HIGH,
                confidence=0.85 if has_trace else 0.75,
                description="UNION SELECT 出现在 WHERE 子句之后或检测到用户输入痕迹",
                vulnerable_clause="UNION SELECT",
                suggestion="使用参数化查询，限制查询列数，避免直接拼接用户输入"
            ))

        return findings
    
    def _detect_stacked_queries(self, statement: Statement, sql_hash: str, sql_preview: str) -> List[SQLInjectionFinding]:
        """检测堆叠查询 (对单个 statement 检测, 多 statement 在 analyze_sql 中检测)"""
        findings = []
        sql_str = str(statement)

        # 单条 statement 内部不应有分号+其他语句
        if re.search(r";\s*(SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|EXEC|TRUNCATE)\b", sql_str, re.IGNORECASE):
            findings.append(SQLInjectionFinding(
                sql_hash=sql_hash,
                sql_preview=sql_preview,
                injection_type=InjectionType.STACKED_QUERY,
                risk_level=RiskLevel.CRITICAL,
                confidence=0.95,
                description="检测到堆叠查询注入",
                vulnerable_clause="; followed by SQL statement",
                suggestion="禁止多语句执行，使用参数化查询，严格输入验证"
            ))

        return findings
    
    def _analyze_params(self, sql: str, params: Dict, sql_hash: str, sql_preview: str) -> List[SQLInjectionFinding]:
        """分析参数是否包含注入 payload

        重点检测参数值中是否存在多语句、UNION、注释等明确的注入特征,
        而不是简单的关键词匹配。
        """
        findings = []

        for key, value in params.items():
            if not isinstance(value, str):
                continue

            # 只检测明确的注入 payload
            if not self._is_suspicious_payload(value):
                continue

            # 根据 payload 类型确定风险等级
            value_upper = value.upper()

            # CRITICAL: 多语句注入
            if re.search(r";\s*(SELECT|INSERT|UPDATE|DELETE|DROP|EXEC|TRUNCATE)", value_upper):
                findings.append(SQLInjectionFinding(
                    sql_hash=sql_hash,
                    sql_preview=sql_preview,
                    injection_type=InjectionType.STACKED_QUERY,
                    risk_level=RiskLevel.CRITICAL,
                    confidence=0.95,
                    description=f"参数 '{key}' 包含堆叠查询注入",
                    vulnerable_clause=f"{key}={value[:50]}",
                    suggestion="禁止在参数中传递多条SQL语句，使用参数化查询"
                ))
                continue

            # HIGH: UNION 注入
            if re.search(r"\bUNION\s+(ALL\s+)?SELECT\b", value_upper):
                findings.append(SQLInjectionFinding(
                    sql_hash=sql_hash,
                    sql_preview=sql_preview,
                    injection_type=InjectionType.UNION_BASED,
                    risk_level=RiskLevel.HIGH,
                    confidence=0.90,
                    description=f"参数 '{key}' 包含 UNION 注入",
                    vulnerable_clause=f"{key}={value[:50]}",
                    suggestion="使用参数化查询，限制查询列数"
                ))
                continue

            # HIGH: 时间盲注
            if any(func in value_upper for func in ['SLEEP(', 'BENCHMARK(', 'PG_SLEEP(', 'WAITFOR']):
                findings.append(SQLInjectionFinding(
                    sql_hash=sql_hash,
                    sql_preview=sql_preview,
                    injection_type=InjectionType.TIME_BASED,
                    risk_level=RiskLevel.HIGH,
                    confidence=0.85,
                    description=f"参数 '{key}' 包含时间延迟函数",
                    vulnerable_clause=f"{key}={value[:50]}",
                    suggestion="禁止在参数中使用时间延迟函数"
                ))
                continue

            # MEDIUM: 布尔盲注 (OR 1=1 + 注释)
            if self._has_user_input_trace(value) and re.search(r"\bOR\s+\d+\s*=\s*\d+", value_upper):
                findings.append(SQLInjectionFinding(
                    sql_hash=sql_hash,
                    sql_preview=sql_preview,
                    injection_type=InjectionType.BOOLEAN_BASED,
                    risk_level=RiskLevel.HIGH,
                    confidence=0.75,
                    description=f"参数 '{key}' 包含布尔盲注特征",
                    vulnerable_clause=f"{key}={value[:50]}",
                    suggestion="使用参数化查询"
                ))
                continue

            # LOW: 包含 SQL 关键字但无明确注入特征
            if re.search(r"\b(SELECT|INSERT|UPDATE|DELETE|DROP)\b", value_upper):
                findings.append(SQLInjectionFinding(
                    sql_hash=sql_hash,
                    sql_preview=sql_preview,
                    injection_type=InjectionType.SECOND_ORDER,
                    risk_level=RiskLevel.LOW,
                    confidence=0.40,
                    description=f"参数 '{key}' 包含SQL关键字, 但无明显注入特征",
                    vulnerable_clause=f"{key}={value[:50]}",
                    suggestion="建议验证参数值, 使用白名单机制"
                ))

        return findings
    
    def _is_suspicious_payload(self, value: str) -> bool:
        """判断是否是可疑的注入 payload"""
        value_upper = value.upper()

        # 多个 SQL 关键字组合 (含 DROP/TRUNCATE)
        keywords = ['SELECT', 'UNION', 'OR', 'AND', 'INSERT', 'DELETE', 'DROP', 'TRUNCATE']
        keyword_count = sum(1 for kw in keywords if kw in value_upper)
        if keyword_count >= 2:
            return True

        # 包含分号 + SQL 关键字 (堆叠查询)
        if re.search(r";\s*(SELECT|INSERT|UPDATE|DELETE|DROP|EXEC|TRUNCATE)", value_upper):
            return True

        # 包含运算符和关键字
        if re.search(r"(=|<|>|!|\|\||&&)", value) and any(kw in value_upper for kw in ['OR', 'AND']):
            return True

        # 包含注释
        if '--' in value or '/*' in value or '#' in value:
            return True

        # 包含时间函数
        if any(func in value_upper for func in ['SLEEP(', 'BENCHMARK(', 'PG_SLEEP(']):
            return True

        return False
    
    def _analyze_patterns(self, sql: str, sql_hash: str, sql_preview: str, dialect: str) -> List[SQLInjectionFinding]:
        """语义模式检测"""
        findings = []
        sql_upper = sql.upper()
        
        # 时间盲注检测
        time_funcs = self.TIME_FUNCTIONS.get(dialect, self.TIME_FUNCTIONS['mysql'])
        for func in time_funcs:
            if func.upper() in sql_upper:
                findings.append(SQLInjectionFinding(
                    sql_hash=sql_hash,
                    sql_preview=sql_preview,
                    injection_type=InjectionType.TIME_BASED,
                    risk_level=RiskLevel.HIGH,
                    confidence=0.85,
                    description=f"检测到时间盲注函数: {func}",
                    vulnerable_clause=func,
                    suggestion="禁止使用时间延迟函数，使用参数化查询"
                ))
                break
        
        # 危险函数检测
        for func in self.DANGEROUS_FUNCTIONS:
            if func.upper() in sql_upper:
                findings.append(SQLInjectionFinding(
                    sql_hash=sql_hash,
                    sql_preview=sql_preview,
                    injection_type=InjectionType.ERROR_BASED,
                    risk_level=RiskLevel.HIGH,
                    confidence=0.80,
                    description=f"检测到危险函数: {func}",
                    vulnerable_clause=func,
                    suggestion=f"避免使用 {func}，限制数据库权限"
                ))

        # 布尔盲注兜底检测（仅当检测到用户输入痕迹时）
        if self._has_user_input_trace(sql):
            tautology_patterns = [
                (r"\bOR\s+['\"]?\d+['\"]?\s*=\s*['\"]?\d+['\"]?", "OR 数字恒真"),
                (r"\bOR\s+['\"].*?['\"]\s*=\s*['\"].*?['\"]", "OR 字符串恒真"),
                (r"\bOR\s+TRUE\b", "OR TRUE"),
                (r"\bOR\s+1\s*=\s*1\b", "OR 1=1"),
            ]
            for pattern, desc in tautology_patterns:
                if re.search(pattern, sql, re.IGNORECASE):
                    findings.append(SQLInjectionFinding(
                        sql_hash=sql_hash,
                        sql_preview=sql_preview,
                        injection_type=InjectionType.BOOLEAN_BASED,
                        risk_level=RiskLevel.HIGH,
                        confidence=0.70,
                        description=f"SQL中存在恒真条件且检测到用户输入痕迹: {desc}",
                        vulnerable_clause=sql[:100],
                        suggestion="使用参数化查询，避免直接拼接用户输入到 WHERE 条件"
                    ))
                    break

        # 注释注入兜底检测
        comment_patterns = [
            (r";\s*--", "分号+注释", RiskLevel.CRITICAL),
            (r"\b\d+\s+OR\s+['\"]?\d+['\"]?\s*=\s*['\"]?\d+['\"]?.*--", "数字条件+注释绕过", RiskLevel.CRITICAL),
        ]
        for pattern, desc, risk in comment_patterns:
            if re.search(pattern, sql, re.IGNORECASE):
                findings.append(SQLInjectionFinding(
                    sql_hash=sql_hash,
                    sql_preview=sql_preview,
                    injection_type=InjectionType.COMMENT_BASED,
                    risk_level=risk,
                    confidence=0.85,
                    description=f"检测到注释注入: {desc}",
                    vulnerable_clause=sql[:100],
                    suggestion="过滤或转义注释字符，使用参数化查询"
                ))
                break

        return findings
    
    def _detect_string_concatenation(self, sql: str, sql_hash: str, sql_preview: str) -> List[SQLInjectionFinding]:
        """检测字符串拼接（潜在注入点）"""
        findings = []
        
        # 检测 Python 风格的字符串拼接
        concat_patterns = [
            (r"%\s*\(", "Python % 格式化"),
            (r"\.format\s*\(", "format() 方法"),
            (r"f[\"']", "f-string 格式化"),
            (r"\+\s*[\"']", "字符串拼接"),
        ]
        
        for pattern, desc in concat_patterns:
            if re.search(pattern, sql):
                findings.append(SQLInjectionFinding(
                    sql_hash=sql_hash,
                    sql_preview=sql_preview,
                    injection_type=InjectionType.SECOND_ORDER,
                    risk_level=RiskLevel.MEDIUM,
                    confidence=0.60,
                    description=f"检测到字符串拼接: {desc}",
                    vulnerable_clause=sql[:100],
                    suggestion="使用参数化查询替代字符串拼接"
                ))
                break
        
        return findings
    
    def _deduplicate_findings(self, findings: List[SQLInjectionFinding]) -> List[SQLInjectionFinding]:
        """去重发现"""
        seen = set()
        unique = []
        
        for finding in findings:
            key = (finding.sql_hash, finding.injection_type.value)
            if key not in seen:
                seen.add(key)
                unique.append(finding)
        
        return unique
    
    def _calculate_risk_score(self, findings: List[SQLInjectionFinding]) -> float:
        """计算风险评分（0-100）"""
        if not findings:
            return 0.0
        
        weights = {
            RiskLevel.CRITICAL: 100,
            RiskLevel.HIGH: 50,
            RiskLevel.MEDIUM: 20,
            RiskLevel.LOW: 5
        }
        
        total_weight = sum(
            weights[f.risk_level] * f.confidence 
            for f in findings
        )
        
        # 归一化到 0-100
        score = min(100, total_weight)
        return round(score, 2)
    
    def _generate_recommendation(self, findings: List[SQLInjectionFinding]) -> str:
        """生成修复建议"""
        if not findings:
            return "未发现 SQL 注入风险"
        
        critical_count = sum(1 for f in findings if f.risk_level == RiskLevel.CRITICAL)
        high_count = sum(1 for f in findings if f.risk_level == RiskLevel.HIGH)
        
        if critical_count > 0:
            return f"发现 {critical_count} 个严重注入风险，请立即修复！使用参数化查询替代字符串拼接。"
        elif high_count > 0:
            return f"发现 {high_count} 个高危风险，建议尽快修复。对所有用户输入进行严格验证。"
        else:
            return "发现一些潜在风险，建议审查代码并使用参数化查询。"
    
    def batch_analyze(self, sql_list: List[str], dialect: str = "mysql") -> Dict[str, Any]:
        """
        批量分析 SQL 列表
        
        参数：
            sql_list: SQL 语句列表
            dialect: 数据库类型
            
        返回：
            Dict: 批量分析结果
        """
        all_findings = []
        injection_count = 0
        
        for sql in sql_list:
            result = self.analyze_sql(sql, dialect=dialect)
            if result["has_injection"]:
                injection_count += 1
            all_findings.extend(result["findings"])
        
        return {
            "total_analyzed": len(sql_list),
            "injection_detected": injection_count,
            "clean_count": len(sql_list) - injection_count,
            "total_findings": len(all_findings),
            "findings": all_findings
        }
