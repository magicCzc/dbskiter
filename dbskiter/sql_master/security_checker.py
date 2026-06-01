"""
统一安全检查模块

文件功能：提供全面的SQL安全检查功能
主要类：
    - SecurityChecker: 统一安全检查器
    - SQLInjectionDetector: SQL注入检测器
    - RateLimiter: 速率限制器

整合内容：
    - 危险操作检测（替代sql_validator.py）
    - SQL注入检测（复用db_security/sql_injection_detector_v2.py）
    - 速率限制（新增）

作者：Security Team
创建时间：2026-05-20
最后修改：2026-05-29
"""

import re
import os
import time
import hashlib
import logging
from typing import Dict, Any, Optional, List, Tuple, Set
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import defaultdict

from dbskiter.sql_master.sql_parser import SQLParser, SQLType, ParsedSQL
from dbskiter.config.security_config import SecurityLevel, SecurityConfig

# 复用db_security的SQL注入检测器（避免重复造轮子）
try:
    from dbskiter.db_security.sql_injection_detector_v2 import SQLInjectionDetectorV2
    _HAS_V2_DETECTOR = True
except ImportError:
    _HAS_V2_DETECTOR = False

logger = logging.getLogger(__name__)


@dataclass
class InjectionCheckResult:
    """SQL注入检查结果"""
    is_injection: bool
    confidence: float  # 0.0 - 1.0
    pattern_matched: Optional[str]
    description: str


@dataclass
class RateLimitStatus:
    """速率限制状态"""
    allowed: bool
    remaining: int
    reset_time: datetime
    retry_after: Optional[int] = None  # 秒


class SQLInjectionDetector:
    """
    SQL注入检测器

    基于多种技术检测SQL注入攻击：
    1. 特征匹配：常见注入模式
    2. 语义分析：异常SQL结构
    3. 熵值检测：随机性检测（防绕过）

    使用示例：
        detector = SQLInjectionDetector()
        result = detector.detect("SELECT * FROM users WHERE id = 1 OR 1=1")
        if result.is_injection:
            print(f"检测到注入: {result.description}")
    """

    # 高危注入模式（直接匹配）
    HIGH_RISK_PATTERNS = [
        (r"(\%27)|(\')|(\-\-)|(\%23)|(#)", "基本注入字符"),
        (r"((\%3D)|(=))[^\n]*((\%27)|(\')|(\-\-)|(\%3B)|(;))", "基于错误的注入"),
        (r"\w*((\%27)|(\'))((\%6F)|o|(\%4F))((\%72)|r|(\%52))", "OR注入"),
        (r"((\%27)|(\'))union", "UNION注入", re.IGNORECASE),
        (r"exec\s*\(\s*@", "EXEC注入", re.IGNORECASE),
        (r"UNION\s+SELECT", "UNION SELECT注入", re.IGNORECASE),
        (r"INSERT\s+INTO.*VALUES.*SELECT", "INSERT注入", re.IGNORECASE),
        (r"DELETE\s+FROM.*WHERE.*=.*=", "DELETE注入", re.IGNORECASE),
        (r"1\s*=\s*1", "恒真条件", re.IGNORECASE),
        (r"1\s*=\s*0", "恒假条件", re.IGNORECASE),
        (r"SLEEP\s*\(", "时间盲注", re.IGNORECASE),
        (r"BENCHMARK\s*\(", "MySQL时间盲注", re.IGNORECASE),
        (r"WAITFOR\s+DELAY", "SQL Server时间盲注", re.IGNORECASE),
        (r"PG_SLEEP\s*\(", "PostgreSQL时间盲注", re.IGNORECASE),
        (r"LOAD_FILE\s*\(", "文件读取", re.IGNORECASE),
        (r"INTO\s+OUTFILE", "文件写入", re.IGNORECASE),
        (r"INFORMATION_SCHEMA", "信息模式探测", re.IGNORECASE),
        (r"sys\.databases", "系统表探测", re.IGNORECASE),
        (r"xp_cmdshell", "命令执行", re.IGNORECASE),
        (r"sp_configure", "配置修改", re.IGNORECASE),
        # 新增：MySQL注释绕过检测
        (r"/\*![0-9]*\s*OR\s+1\s*=\s*1\*/", "MySQL条件注释绕过", re.IGNORECASE),
        (r"/\*![0-9]*\s*UNION\s+SELECT", "MySQL UNION注释绕过", re.IGNORECASE),
        # 新增：十六进制编码绕过
        (r"0x[0-9a-fA-F]+\s*OR\s*0x[0-9a-fA-F]+\s*=\s*0x[0-9a-fA-F]+", "十六进制编码绕过", re.IGNORECASE),
        # 新增：双写绕过检测
        (r"UNIUNIONON\s+SESELECTLECT", "双写绕过", re.IGNORECASE),
        (r"UN\+%6E\+ION\s+SEL\+%45\+ECT", "URL编码绕过", re.IGNORECASE),
        # 新增：内联注释绕过
        (r"/\*.*?\*/\s*OR\s*/\*.*?\*/\s*1\s*=\s*1", "内联注释绕过", re.IGNORECASE),
        # 新增：逻辑运算符绕过
        (r"\|\|\s*1\s*=\s*1", "逻辑或绕过", re.IGNORECASE),
        (r"&&\s*1\s*=\s*1", "逻辑与绕过", re.IGNORECASE),
        # 新增：空格替代绕过
        (r"OR\s*/\*!\s*\*/\s*1\s*=\s*1", "注释替代空格绕过", re.IGNORECASE),
        # 新增：Unicode等价字符
        (r"\u0027\s*OR\s*\u0027", "Unicode单引号绕过", re.IGNORECASE),
    ]

    # 中危模式（需要上下文判断）
    MEDIUM_RISK_PATTERNS = [
        (r";\s*SELECT", "堆叠查询", re.IGNORECASE),
        (r";\s*INSERT", "堆叠INSERT", re.IGNORECASE),
        (r";\s*UPDATE", "堆叠UPDATE", re.IGNORECASE),
        (r";\s*DELETE", "堆叠DELETE", re.IGNORECASE),
        (r";\s*DROP", "堆叠DROP", re.IGNORECASE),
        (r"'\s*OR\s*'", "OR条件绕过", re.IGNORECASE),
        (r"'\s*AND\s*'", "AND条件绕过", re.IGNORECASE),
        (r"LIKE\s+'\%", "LIKE通配符注入", re.IGNORECASE),
        (r"CHAR\s*\(\s*\d+", "CHAR编码绕过", re.IGNORECASE),
        (r"CONCAT\s*\(", "字符串拼接", re.IGNORECASE),
        (r"CONCAT_WS\s*\(", "CONCAT_WS拼接", re.IGNORECASE),
        (r"GROUP_CONCAT", "MySQL聚合", re.IGNORECASE),
        (r"STRING_AGG", "PostgreSQL聚合", re.IGNORECASE),
        # 新增：注释绕过检测
        (r"--\s*-\s*\n", "双横线注释绕过", re.IGNORECASE),
        (r"#\s*\n", "井号注释绕过", re.IGNORECASE),
        # 新增：URL编码绕过
        (r"%20OR%20", "URL编码OR绕过", re.IGNORECASE),
        (r"%27OR%27", "URL编码单引号绕过", re.IGNORECASE),
        # 新增：大小写混合绕过
        (r"[uU][nN][iI][oO][nN]\s+[sS][eE][lL][eE][cC][tT]", "大小写混合UNION", re.IGNORECASE),
    ]

    def __init__(self):
        """初始化检测器，编译正则表达式"""
        self._high_risk_patterns = []
        for pattern in self.HIGH_RISK_PATTERNS:
            if len(pattern) == 2:
                regex, desc = pattern
                flags = 0
            else:
                regex, desc, flags = pattern
            try:
                self._high_risk_patterns.append((re.compile(regex, flags), desc))
            except re.error as e:
                logger.warning(f"编译正则表达式失败: {regex}, 错误: {e}")

        self._medium_risk_patterns = []
        for pattern in self.MEDIUM_RISK_PATTERNS:
            if len(pattern) == 2:
                regex, desc = pattern
                flags = 0
            else:
                regex, desc, flags = pattern
            try:
                self._medium_risk_patterns.append((re.compile(regex, flags), desc))
            except re.error as e:
                logger.warning(f"编译正则表达式失败: {regex}, 错误: {e}")

        # 复用db_security的V2检测器
        self._v2_detector = SQLInjectionDetectorV2() if _HAS_V2_DETECTOR else None

    def detect(self, sql: str) -> InjectionCheckResult:
        """
        检测SQL注入

        优先复用db_security/sql_injection_detector_v2.py的检测能力，
        避免重复造轮子。V2检测器不可用时回退到本地正则匹配。

        参数:
            sql: SQL语句

        返回:
            InjectionCheckResult: 检测结果
        """
        if not sql or not isinstance(sql, str):
            return InjectionCheckResult(False, 0.0, None, "空SQL")

        # 优先使用V2检测器（避免误报，支持用户输入痕迹分析）
        if self._v2_detector:
            try:
                v2_result = self._v2_detector.analyze_sql(sql)
                if v2_result.get("has_injection"):
                    findings = v2_result.get("findings", [])
                    if findings:
                        top = findings[0]
                        return InjectionCheckResult(
                            is_injection=True,
                            confidence=top.get("confidence", 0.85),
                            pattern_matched=top.get("injection_type", "unknown"),
                            description=top.get("description", "检测到SQL注入")
                        )
                    return InjectionCheckResult(
                        is_injection=True,
                        confidence=0.85,
                        pattern_matched="v2_detection",
                        description="V2检测器发现注入风险"
                    )
                return InjectionCheckResult(False, 0.0, None, "V2检测器未发现问题")
            except Exception as e:
                logger.warning(f"V2检测器调用失败，回退到本地检测: {e}")

        sql_normalized = self._normalize_sql(sql)

        # 0. 排除正常SQL模式（避免误报）
        if self._is_normal_sql(sql_normalized):
            return InjectionCheckResult(False, 0.0, None, "正常SQL语句")

        # 1. 检查高危模式
        for pattern, desc in self._high_risk_patterns:
            if pattern.search(sql_normalized):
                return InjectionCheckResult(
                    is_injection=True,
                    confidence=0.95,
                    pattern_matched=desc,
                    description=f"检测到高危注入模式: {desc}"
                )

        # 2. 检查中危模式（需要多个匹配才判定）
        medium_matches = []
        for pattern, desc in self._medium_risk_patterns:
            if pattern.search(sql_normalized):
                medium_matches.append(desc)

        if len(medium_matches) >= 2:
            return InjectionCheckResult(
                is_injection=True,
                confidence=0.75,
                pattern_matched=", ".join(medium_matches),
                description=f"检测到多个中危注入模式: {', '.join(medium_matches)}"
            )

        # 3. 语义分析
        semantic_result = self._semantic_analysis(sql_normalized)
        if semantic_result.is_injection:
            return semantic_result

        # 4. 熵值检测（检测编码绕过）
        entropy_result = self._entropy_check(sql)
        if entropy_result.is_injection:
            return entropy_result

        return InjectionCheckResult(False, 0.0, None, "未检测到注入")

    def _normalize_sql(self, sql: str) -> str:
        """
        标准化SQL（去除多余空格，统一大小写，处理编码绕过）

        处理多种绕过技术：
        1. URL解码
        2. Unicode规范化
        3. 注释去除
        4. 空格标准化
        """
        if not sql:
            return ""

        # 1. URL解码（处理 %27, %20 等）
        import urllib.parse
        try:
            decoded = urllib.parse.unquote(sql)
            # 如果解码后有变化，继续处理解码后的内容
            if decoded != sql:
                sql = decoded
        except Exception:
            pass

        # 2. Unicode规范化（处理 \u0027 等）
        sql = sql.encode('utf-8').decode('unicode_escape') if '\\u' in sql else sql

        # 3. 去除单行注释
        sql = re.sub(r'--[^\n]*', ' ', sql)

        # 4. 去除多行注释（但保留MySQL条件注释的内容）
        # MySQL条件注释: /*!50000 SELECT */ 应该保留 SELECT
        def replace_comment(match):
            comment = match.group(0)
            # 检查是否为MySQL条件注释
            mysql_conditional = re.match(r'/\*!\d*\s*(.+?)\s*\*/', comment, re.DOTALL)
            if mysql_conditional:
                return ' ' + mysql_conditional.group(1) + ' '
            return ' '

        sql = re.sub(r'/\*.*?\*/', replace_comment, sql, flags=re.DOTALL)

        # 5. 处理十六进制编码（0x31 → '1'）
        def replace_hex(match):
            try:
                hex_str = match.group(1)
                decoded = bytes.fromhex(hex_str).decode('utf-8', errors='ignore')
                return f"'{decoded}'"
            except Exception:
                return match.group(0)

        sql = re.sub(r'0x([0-9a-fA-F]+)', replace_hex, sql)

        # 6. 标准化空格和换行
        sql = re.sub(r'[\s\n\r\t]+', ' ', sql)

        # 7. 去除首尾空格并转为大写
        return sql.strip().upper()

    def _is_normal_sql(self, sql: str) -> bool:
        """
        检查是否为正常的SQL语句（排除误报）

        正常的INSERT/UPDATE语句中的单引号不应被判定为注入
        """
        # 检查是否为标准的INSERT语句
        if sql.startswith("INSERT INTO"):
            # 标准INSERT格式：INSERT INTO table (cols) VALUES (vals)
            if re.match(r'^INSERT INTO \w+\s*\([^)]+\)\s*VALUES\s*\(', sql):
                return True
            if re.match(r'^INSERT INTO \w+\s+VALUES\s*\(', sql):
                return True

        # 检查是否为标准的UPDATE语句
        if sql.startswith("UPDATE"):
            # 标准UPDATE格式：UPDATE table SET col = val
            if re.match(r'^UPDATE \w+\s+SET\s+\w+\s*=', sql):
                return True

        # 检查是否为标准的SELECT语句
        if sql.startswith("SELECT"):
            # 简单SELECT，没有可疑的UNION或子查询
            if not re.search(r'\bUNION\b', sql) and not re.search(r'\bOR\s+1\s*=\s*1\b', sql):
                # 检查是否有WHERE子句中的异常条件
                where_match = re.search(r'WHERE\s+(.+?)(?:ORDER|GROUP|LIMIT|$)', sql)
                if where_match:
                    where_clause = where_match.group(1)
                    # 检查是否有多个单引号（字符串值）
                    quote_count = where_clause.count("'")
                    if quote_count >= 2 and quote_count % 2 == 0:
                        # 成对的单引号，可能是正常的字符串值
                        if not re.search(r"'\s*OR\s*'", where_clause, re.IGNORECASE):
                            if not re.search(r"'\s*AND\s*'", where_clause, re.IGNORECASE):
                                return True
                else:
                    return True

        return False

    def _semantic_analysis(self, sql: str) -> InjectionCheckResult:
        """
        语义分析 - 检测更复杂的注入模式

        检测能力：
        1. UNION注入的各种变体
        2. 布尔盲注的条件构造
        3. 时间盲注的函数调用
        4. 堆叠查询的多语句
        5. 注释绕过后的异常结构
        """
        # 1. 检查UNION注入（包括各种绕过形式）
        union_patterns = [
            r'\bUNION\s+SELECT\b',
            r'\bUNION\s+ALL\s+SELECT\b',
            r'\bUNION\s+DISTINCT\s+SELECT\b',
            r'\bUNION\s*\(\s*SELECT\b',
        ]
        for pattern in union_patterns:
            if re.search(pattern, sql, re.IGNORECASE):
                return InjectionCheckResult(
                    is_injection=True,
                    confidence=0.85,
                    pattern_matched="UNION SELECT",
                    description="检测到UNION SELECT结构，可能是注入攻击"
                )

        # 2. 检查布尔盲注（恒真/恒假条件）
        boolean_patterns = [
            r"'\s*OR\s*['\"]?\d+\s*=\s*['\"]?\d+",  # ' OR '1'='1
            r'"\s*OR\s*["\']?\d+\s*=\s*["\']?\d+',  # " OR "1"="1
            r"\d+\s*=\s*\d+\s*AND\s*\d+\s*=\s*\d+",  # 1=1 AND 2=2
            r"'\s*LIKE\s*'\%",  # ' LIKE '%
            r'"\s*LIKE\s*"\%',  # " LIKE "%
        ]
        for pattern in boolean_patterns:
            if re.search(pattern, sql, re.IGNORECASE):
                return InjectionCheckResult(
                    is_injection=True,
                    confidence=0.8,
                    pattern_matched="布尔盲注",
                    description="检测到布尔盲注模式（恒真条件）"
                )

        # 3. 检查WHERE子句中的异常逻辑
        where_match = re.search(r'WHERE\s+(.+?)(?:ORDER|GROUP|LIMIT|HAVING|$)', sql, re.IGNORECASE)
        if where_match:
            where_clause = where_match.group(1)

            # 检查异常的逻辑组合
            suspicious_patterns = [
                r'\bOR\b.*\bOR\b',  # 多个OR
                r'\bAND\b.*\bAND\b.*\bAND\b',  # 三个以上AND
                r"'\s*OR\s*[^'\"]+\s*OR\s*'",  # ' OR something OR '
                r'\)\s*OR\s*\(',  # ) OR (
            ]
            for pattern in suspicious_patterns:
                if re.search(pattern, where_clause, re.IGNORECASE):
                    return InjectionCheckResult(
                        is_injection=True,
                        confidence=0.75,
                        pattern_matched="异常WHERE条件",
                        description="WHERE子句包含可疑的逻辑组合"
                    )

        # 4. 检查子查询异常
        subquery_count = len(re.findall(r'\(SELECT', sql, re.IGNORECASE))
        if subquery_count > 2:
            return InjectionCheckResult(
                is_injection=True,
                confidence=0.7,
                pattern_matched="多层子查询",
                description=f"检测到{subquery_count}层子查询，可能是注入攻击"
            )

        # 5. 检查堆叠查询（多语句）
        statement_count = len(re.findall(r';\s*(?:SELECT|INSERT|UPDATE|DELETE|DROP)', sql, re.IGNORECASE))
        if statement_count > 0:
            return InjectionCheckResult(
                is_injection=True,
                confidence=0.8,
                pattern_matched="堆叠查询",
                description="检测到多个SQL语句，可能是堆叠查询注入"
            )

        # 6. 检查时间盲注函数组合
        time_based_patterns = [
            r'\bIF\s*\([^)]+\)\s*,\s*\b(?:SLEEP|BENCHMARK|PG_SLEEP)',
            r'\bCASE\b.*\bWHEN\b.*\bTHEN\b.*\b(?:SLEEP|BENCHMARK)',
            r'\bIIF\s*\([^)]+\)\s*,\s*\b(?:SLEEP|BENCHMARK)',
        ]
        for pattern in time_based_patterns:
            if re.search(pattern, sql, re.IGNORECASE):
                return InjectionCheckResult(
                    is_injection=True,
                    confidence=0.8,
                    pattern_matched="时间盲注",
                    description="检测到时间盲注函数组合"
                )

        return InjectionCheckResult(False, 0.0, None, "")

    def _entropy_check(self, sql: str) -> InjectionCheckResult:
        """熵值检测（检测编码绕过）"""
        # 计算SQL的熵值
        import math
        from collections import Counter

        if len(sql) < 10:
            return InjectionCheckResult(False, 0.0, None, "")

        # 统计字符频率
        counter = Counter(sql)
        length = len(sql)
        entropy = 0.0

        for count in counter.values():
            if count > 0:
                p = count / length
                entropy -= p * math.log2(p)

        # 高熵值可能表示编码绕过
        if entropy > 5.0:
            return InjectionCheckResult(
                is_injection=True,
                confidence=0.6,
                pattern_matched="高熵值",
                description=f"SQL熵值异常({entropy:.2f})，可能存在编码绕过"
            )

        return InjectionCheckResult(False, 0.0, None, "")


class RateLimiter:
    """
    速率限制器

    限制用户的SQL操作频率，防止暴力破解和批量攻击

    使用示例：
        limiter = RateLimiter(max_requests=60, window_seconds=60)
        status = limiter.check_limit("user_123", "SELECT")
        if not status.allowed:
            print(f"请等待{status.retry_after}秒")
    """

    def __init__(
        self,
        max_requests: int = 60,
        window_seconds: int = 60,
        block_duration: int = 300
    ):
        """
        初始化速率限制器

        参数:
            max_requests: 时间窗口内最大请求数
            window_seconds: 时间窗口（秒）
            block_duration: 超限后封禁时长（秒）
        """
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.block_duration = block_duration

        # 存储请求记录: {user_id: [(timestamp, operation), ...]}
        self._requests: Dict[str, List[Tuple[datetime, str]]] = defaultdict(list)

        # 封禁记录: {user_id: unblock_time}
        self._blocked: Dict[str, datetime] = {}

    def check_limit(self, user_id: str, operation: str) -> RateLimitStatus:
        """
        检查速率限制

        参数:
            user_id: 用户标识
            operation: 操作类型

        返回:
            RateLimitStatus: 限制状态
        """
        now = datetime.now()

        # 检查是否被封禁
        if user_id in self._blocked:
            unblock_time = self._blocked[user_id]
            if now < unblock_time:
                retry_after = int((unblock_time - now).total_seconds())
                return RateLimitStatus(
                    allowed=False,
                    remaining=0,
                    reset_time=unblock_time,
                    retry_after=retry_after
                )
            else:
                # 解封
                del self._blocked[user_id]

        # 清理过期记录
        self._cleanup_old_requests(user_id, now)

        # 检查当前请求数
        current_requests = len(self._requests[user_id])
        remaining = max(0, self.max_requests - current_requests)

        if current_requests >= self.max_requests:
            # 超限，封禁用户
            unblock_time = now + timedelta(seconds=self.block_duration)
            self._blocked[user_id] = unblock_time

            logger.warning(f"用户 {user_id} 触发速率限制，封禁{self.block_duration}秒")

            return RateLimitStatus(
                allowed=False,
                remaining=0,
                reset_time=unblock_time,
                retry_after=self.block_duration
            )

        # 记录本次请求
        self._requests[user_id].append((now, operation))

        reset_time = now + timedelta(seconds=self.window_seconds)

        return RateLimitStatus(
            allowed=True,
            remaining=remaining - 1,
            reset_time=reset_time
        )

    def _cleanup_old_requests(self, user_id: str, now: datetime):
        """清理过期的请求记录"""
        cutoff = now - timedelta(seconds=self.window_seconds)
        self._requests[user_id] = [
            (ts, op) for ts, op in self._requests[user_id]
            if ts > cutoff
        ]

    def get_stats(self, user_id: str) -> Dict[str, Any]:
        """获取用户统计信息"""
        now = datetime.now()
        self._cleanup_old_requests(user_id, now)

        requests = self._requests[user_id]
        operations = defaultdict(int)
        for ts, op in requests:
            operations[op] += 1

        return {
            "total_requests": len(requests),
            "remaining": max(0, self.max_requests - len(requests)),
            "operations": dict(operations),
            "is_blocked": user_id in self._blocked,
            "unblock_time": self._blocked.get(user_id)
        }


class SecurityChecker:
    """
    统一安全检查器

    整合所有安全检查功能：
    1. SQL注入检测
    2. 危险操作检测
    3. 速率限制检查
    4. 表级权限检查

    使用示例：
        checker = SecurityChecker()
        result = checker.check(sql="SELECT * FROM users", user_id="user_123")
        if not result.passed:
            print(result.reason)
    """

    def __init__(
        self,
        enable_injection_detection: Optional[bool] = None,
        enable_rate_limiting: Optional[bool] = None,
        max_requests: Optional[int] = None,
        window_seconds: Optional[int] = None
    ):
        """
        初始化安全检查器

        参数:
            enable_injection_detection: 是否启用注入检测（None则从环境变量读取）
            enable_rate_limiting: 是否启用速率限制（None则从环境变量读取）
            max_requests: 速率限制最大请求数（None则从环境变量读取）
            window_seconds: 速率限制时间窗口（None则从环境变量读取）
        """
        # 注入检测开关：参数 > 环境变量 > 默认True
        if enable_injection_detection is not None:
            self._enable_injection = enable_injection_detection
        else:
            env_val = os.getenv("DBSKITER_ENABLE_INJECTION_DETECTION", "").lower()
            self._enable_injection = env_val not in ("false", "0", "no") if env_val else True

        # 速率限制开关：参数 > 环境变量 > 默认True
        if enable_rate_limiting is not None:
            self._enable_rate_limit = enable_rate_limiting
        else:
            env_val = os.getenv("DBSKITER_ENABLE_RATE_LIMIT", "").lower()
            self._enable_rate_limit = env_val not in ("false", "0", "no") if env_val else True

        # 速率限制参数：参数 > 环境变量 > 默认值
        if max_requests is not None:
            effective_max_requests = max_requests
        else:
            try:
                effective_max_requests = int(os.getenv("DBSKITER_RATE_LIMIT_MAX_REQUESTS", "60"))
            except ValueError:
                effective_max_requests = 60

        if window_seconds is not None:
            effective_window_seconds = window_seconds
        else:
            try:
                effective_window_seconds = int(os.getenv("DBSKITER_RATE_LIMIT_WINDOW", "60"))
            except ValueError:
                effective_window_seconds = 60

        self.sql_parser = SQLParser()
        self.injection_detector = SQLInjectionDetector() if self._enable_injection else None
        self.rate_limiter = RateLimiter(effective_max_requests, effective_window_seconds) if self._enable_rate_limit else None
        
        # 加载安全配置
        self.security_config = SecurityConfig()
        self.policy = self.security_config.policy

    def check(
        self,
        sql: str,
        user_id: str = "anonymous",
        operation: str = "QUERY",
        whitelist_tables: Optional[Set[str]] = None,
        blacklist_tables: Optional[Set[str]] = None
    ) -> Dict[str, Any]:
        """
        执行全面安全检查

        参数:
            sql: SQL语句
            user_id: 用户标识
            operation: 操作类型
            whitelist_tables: 白名单表
            blacklist_tables: 黑名单表

        返回:
            Dict: 检查结果
        """
        # 1. 基础验证
        if not sql or not sql.strip():
            return {
                "passed": False,
                "reason": "SQL语句不能为空",
                "risk_level": SecurityLevel.CRITICAL
            }

        # 2. SQL注入检测
        if self.injection_detector:
            injection_result = self.injection_detector.detect(sql)
            if injection_result.is_injection:
                logger.warning(f"检测到SQL注入: {injection_result.description}")
                return {
                    "passed": False,
                    "reason": f"SQL注入检测失败: {injection_result.description}",
                    "risk_level": SecurityLevel.CRITICAL,
                    "injection_result": injection_result
                }

        # 3. 速率限制检查
        if self.rate_limiter:
            rate_status = self.rate_limiter.check_limit(user_id, operation)
            if not rate_status.allowed:
                return {
                    "passed": False,
                    "reason": f"请求过于频繁，请{rate_status.retry_after}秒后重试",
                    "risk_level": SecurityLevel.HIGH,
                    "rate_limit_status": rate_status
                }

        # 4. 解析SQL
        try:
            parsed = self.sql_parser.parse(sql)
        except Exception as e:
            return {
                "passed": False,
                "reason": f"SQL解析失败: {str(e)}",
                "risk_level": SecurityLevel.HIGH
            }

        # 5. 表级权限检查
        if parsed.tables:
            # 检查黑名单
            if blacklist_tables:
                for table in parsed.tables:
                    table_clean = table.strip('`"[]').upper()
                    if table_clean in {t.upper() for t in blacklist_tables}:
                        return {
                            "passed": False,
                            "reason": f"表 '{table}' 在黑名单中，禁止操作",
                            "risk_level": SecurityLevel.CRITICAL
                        }

            # 检查白名单
            if whitelist_tables:
                for table in parsed.tables:
                    table_clean = table.strip('`"[]').upper()
                    if table_clean not in {t.upper() for t in whitelist_tables}:
                        return {
                            "passed": False,
                            "reason": f"表 '{table}' 不在白名单中，禁止操作",
                            "risk_level": SecurityLevel.CRITICAL
                        }

        # 6. 危险操作检测
        risk_result = self._assess_risk(parsed)

        return {
            "passed": True,
            "reason": "安全检查通过",
            "risk_level": risk_result["level"],
            "risk_description": risk_result["description"],
            "parsed_sql": parsed,
            "is_read_only": parsed.is_read_only
        }

    def _assess_risk(self, parsed: ParsedSQL) -> Dict[str, Any]:
        """评估风险等级"""
        sql_type = parsed.sql_type
        
        # 检查是否在禁止操作列表中
        operation_name = sql_type.value.upper()
        if self.policy.is_blocked(operation_name):
            return {"level": SecurityLevel.CRITICAL, "description": f"{operation_name}操作被系统安全策略禁止"}

        # CRITICAL级别
        if sql_type == SQLType.DROP:
            return {"level": SecurityLevel.CRITICAL, "description": "DROP操作将永久删除数据库对象"}

        if sql_type == SQLType.TRUNCATE:
            return {"level": SecurityLevel.CRITICAL, "description": "TRUNCATE操作将清空表数据且无法回滚"}

        # HIGH级别
        if sql_type == SQLType.DELETE:
            if not parsed.has_where:
                return {"level": SecurityLevel.HIGH, "description": "DELETE语句缺少WHERE子句，将删除整张表的所有数据"}
            return {"level": SecurityLevel.HIGH, "description": "DELETE操作将永久删除数据"}

        if sql_type == SQLType.UPDATE:
            if not parsed.has_where:
                return {"level": SecurityLevel.HIGH, "description": "UPDATE语句缺少WHERE子句，将更新整张表的所有数据"}
            return {"level": SecurityLevel.HIGH, "description": "UPDATE操作将修改数据"}

        if sql_type == SQLType.ALTER:
            return {"level": SecurityLevel.HIGH, "description": "ALTER操作将修改表结构"}

        # MEDIUM级别
        if sql_type in (SQLType.INSERT, SQLType.REPLACE):
            return {"level": SecurityLevel.MEDIUM, "description": f"{sql_type.value}操作将写入数据"}

        # SAFE级别
        if sql_type in (SQLType.SELECT, SQLType.EXPLAIN, SQLType.SHOW, SQLType.DESCRIBE):
            return {"level": SecurityLevel.SAFE, "description": "只读操作"}

        return {"level": SecurityLevel.MEDIUM, "description": f"{sql_type.value}操作"}


# 便捷函数
def check_sql(
    sql: str,
    user_id: str = "anonymous",
    **kwargs
) -> Dict[str, Any]:
    """
    快速检查SQL的便捷函数

    参数:
        sql: SQL语句
        user_id: 用户标识
        **kwargs: 其他参数

    返回:
        Dict: 检查结果
    """
    checker = SecurityChecker()
    return checker.check(sql, user_id, **kwargs)


__all__ = [
    "SecurityChecker",
    "SQLInjectionDetector",
    "InjectionCheckResult",
    "RateLimiter",
    "RateLimitStatus",
    "check_sql",
]
