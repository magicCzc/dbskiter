"""
SQL解析器模块

文件功能：提供健壮的SQL解析功能，集成sqlparse AST解析为主、正则回退为辅
主要类：
    - SQLParser: SQL解析器（AST + 正则双引擎）
    - ParsedSQL: 解析后的SQL对象
    - SQLType: SQL类型枚举

解析能力：
    1. 识别SQL类型（SELECT/INSERT/UPDATE/DELETE等）
    2. 提取表名（包含CTE表过滤、JOIN表提取、schema.table）
    3. 识别WHERE子句
    4. 识别JOIN操作
    5. 识别子查询
    6. 识别CTE（WITH子句）

作者：Security Team
创建时间：2026-05-20
最后修改：2026-06-05
"""

import logging
import re
from typing import Dict, Any, Optional, List, Set, Tuple
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)

# sqlparse AST 解析（可选依赖，不可用时自动降级为正则）
try:
    import sqlparse
    from sqlparse.sql import (
        Identifier, IdentifierList, Function, Where, Comparison, Parenthesis
    )
    from sqlparse.tokens import Keyword, DML, DDL, CTE, Punctuation, Whitespace, Name
    HAS_SQLPARSE = True
except ImportError:
    HAS_SQLPARSE = False
    logger.info("sqlparse 未安装，将使用正则表达式解析SQL")


class SQLType(Enum):
    """SQL类型枚举"""
    SELECT = "SELECT"
    INSERT = "INSERT"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    DROP = "DROP"
    TRUNCATE = "TRUNCATE"
    ALTER = "ALTER"
    CREATE = "CREATE"
    REPLACE = "REPLACE"
    MERGE = "MERGE"
    CALL = "CALL"
    EXPLAIN = "EXPLAIN"
    SHOW = "SHOW"
    DESCRIBE = "DESCRIBE"
    DESC = "DESC"
    UNKNOWN = "UNKNOWN"


class SQLDialect(Enum):
    """SQL方言枚举"""
    MYSQL = "mysql"
    POSTGRESQL = "postgresql"
    ORACLE = "oracle"
    SQLSERVER = "sqlserver"
    SQLITE = "sqlite"
    GENERIC = "generic"


@dataclass
class ParsedSQL:
    """
    解析后的SQL对象

    属性：
        original_sql: 原始SQL语句
        sql_type: SQL类型
        tables: 涉及的表名列表
        has_where: 是否有WHERE子句
        has_join: 是否有JOIN操作
        has_subquery: 是否有子查询
        where_clause: WHERE子句内容
        is_read_only: 是否为只读操作
        dialect: SQL方言
    """
    original_sql: str
    sql_type: SQLType
    tables: List[str] = field(default_factory=list)
    has_where: bool = False
    has_join: bool = False
    has_subquery: bool = False
    where_clause: Optional[str] = None
    is_read_only: bool = False
    dialect: SQLDialect = SQLDialect.GENERIC

    def get_main_table(self) -> Optional[str]:
        """获取主表名"""
        if self.tables:
            return self.tables[0]
        return None

    def is_dangerous_without_where(self) -> bool:
        """判断是否是无条件的危险操作"""
        dangerous_types = {SQLType.DELETE, SQLType.UPDATE}
        return self.sql_type in dangerous_types and not self.has_where


# ---------------------------------------------------------------------------
# AST helper functions (sqlparse)
# ---------------------------------------------------------------------------

def _ast_get_full_name(ident: Identifier) -> str:
    """从 Identifier 获取完整名称（含 schema 前缀），不包含别名"""
    # 方法1: 遍历子 token 构造完整名
    parts = []
    for t in ident.tokens:
        if t.is_whitespace:
            continue
        tt = getattr(t, "ttype", None)
        if tt in (Name, Name.Name):
            parts.append(str(t.value))
        elif tt is Punctuation and str(t.value) == ".":
            parts.append(".")
        elif isinstance(t, Identifier):
            parts.append(_ast_get_full_name(t))
    if parts:
        raw = "".join(parts)
        # 去掉别名（AS alias 或空格 alias）
        # 注意：别名可能包含空格，但表名也可能含空格（用引号包裹的）
        # 简单策略：按空格分割取第一部分就够了，除非第一部分是引号包裹的
        first = raw.split()[0] if " " in raw else raw
        return first
    # 方法2: get_real_name 返回无 alias 的表名（不含 schema）
    real = ident.get_real_name()
    if real:
        return str(real)
    # 方法3: 直接字符串
    return str(ident).split()[0]


def _ast_has_subquery(stmt) -> bool:
    """递归检查 AST 中是否有子查询"""
    for token in stmt.tokens:
        if isinstance(token, Parenthesis):
            inner = str(token).strip().upper()
            if inner.startswith("SELECT") or inner.startswith("(SELECT"):
                return True
            # 也可能是子查询的别名
        if hasattr(token, "tokens"):
            if _ast_has_subquery(token):
                return True
    return False


def _ast_has_where(stmt) -> bool:
    """检查 AST 中是否有 WHERE 子句"""
    for token in stmt.tokens:
        if isinstance(token, Where):
            return True
        if hasattr(token, "tokens"):
            if _ast_has_where(token):
                return True
    return False


def _ast_has_join(stmt) -> bool:
    """检查 AST 中是否有 JOIN"""
    for token in stmt.tokens:
        tt = getattr(token, "ttype", None)
        if tt is Keyword:
            val = str(token.value).upper().strip()
            if val.endswith("JOIN"):
                return True
            if val in ("INNER", "LEFT", "RIGHT", "FULL", "CROSS",
                       "OUTER", "LEFT OUTER", "RIGHT OUTER", "FULL OUTER",
                       "NATURAL"):
                # 前面可能还有 LEFT/RIGHT 等
                pass
        if hasattr(token, "tokens"):
            if _ast_has_join(token):
                return True
    return False


def _ast_extract_where_text(stmt) -> Optional[str]:
    """从 AST 中提取 WHERE 子句文本"""
    for token in stmt.tokens:
        if isinstance(token, Where):
            return str(token).replace("WHERE ", "", 1).strip()
        if hasattr(token, "tokens"):
            result = _ast_extract_where_text(token)
            if result:
                return result
    return None


def _ast_extract_cte_names(stmt) -> List[str]:
    """提取 CTE 表名（WITH 子句中定义的临时表名）"""
    names: List[str] = []
    stmt_text = str(stmt).strip()
    if not stmt_text.upper().startswith("WITH"):
        return names

    cte_found = False
    for token in stmt.tokens:
        tt = getattr(token, "ttype", None)
        if tt is CTE or (tt is Keyword and str(token.value).upper() == "WITH"):
            cte_found = True
            continue
        if cte_found:
            # CTE 定义结束于 DML 关键字（SELECT/INSERT/UPDATE/DELETE）
            if tt is DML or (tt is Keyword and str(token.value).upper()
                             in ("SELECT", "INSERT", "UPDATE", "DELETE")):
                break
            if isinstance(token, IdentifierList):
                for ident in token.get_identifiers():
                    names.append(str(ident.get_real_name() or ident))
            elif isinstance(token, Identifier):
                names.append(str(token.get_real_name() or token))
    return names


# ---------------------------------------------------------------------------
# Aliases for backward compatibility
# ---------------------------------------------------------------------------
_SQLP_KEYWORDS_FROM_LIKE = frozenset({
    "FROM", "JOIN", "INNER JOIN", "LEFT JOIN", "RIGHT JOIN",
    "FULL JOIN", "CROSS JOIN", "LEFT OUTER JOIN", "RIGHT OUTER JOIN",
    "FULL OUTER JOIN", "INTO", "TABLE", "UPDATE",
})


def _ast_extract_tables(stmt) -> List[str]:
    """
    从 AST 提取所有真实表名（核心函数）

    处理：
      - FROM table / FROM t1, t2
      - JOIN / INNER JOIN / LEFT JOIN table
      - INSERT INTO table  / UPDATE table  / DELETE FROM table
      - schema.table（保留前缀）
      - 子查询内的表（递归提取）
      - CTE 定义内的表（WITH cte AS (SELECT ... FROM real_table)）
      返回的表名已被 CTE 名过滤（不含 CTE 临时表）
    """
    tables: List[str] = []
    stmt_text = str(stmt)
    cte_names = _ast_extract_cte_names(stmt)
    cte_upper = {n.upper() for n in cte_names}

    def _extract_from_flat_tokens(tokens: list) -> List[str]:
        """从 flat token 序列提取表名"""
        result: List[str] = []
        paren_depth = 0
        i = 0
        while i < len(tokens):
            token = tokens[i]
            tt = getattr(token, "ttype", None)
            val = str(token.value).strip()

            # 跟踪括号深度，括号内的内容不作为表名
            if val == "(":
                paren_depth += 1
                i += 1
                continue
            if val == ")":
                paren_depth -= 1
                i += 1
                continue

            if paren_depth > 0:
                i += 1
                continue

            val_upper = val.upper()

            is_from = False
            if tt is Keyword or tt is DML:
                if val_upper in _SQLP_KEYWORDS_FROM_LIKE:
                    is_from = True
                elif val_upper == "JOIN":
                    is_from = True

            if not is_from:
                i += 1
                continue

            # 从下一个 token 开始收集表名
            j = i + 1
            while j < len(tokens):
                ntok = tokens[j]
                nval = str(ntok.value).strip()
                ntt = getattr(ntok, "ttype", None)

                if not nval or nval.isspace():
                    j += 1
                    continue

                # 括号内的内容根据上下文处理
                if nval == "(":
                    if val_upper in ("INTO", "TABLE"):
                        # INSERT INTO logs (col1, col2) → 列定义，跳过
                        d = 1
                        k = j + 1
                        while k < len(tokens) and d > 0:
                            kv = str(tokens[k].value).strip()
                            if kv == "(":
                                d += 1
                            elif kv == ")":
                                d -= 1
                            k += 1
                        j = k
                        break
                    else:
                        # FROM/JOIN 后的 ()：子查询，递归提取内部表名
                        d = 1
                        k = j + 1
                        paren_start = k
                        while k < len(tokens) and d > 0:
                            kv = str(tokens[k].value).strip()
                            if kv == "(":
                                d += 1
                            elif kv == ")":
                                d -= 1
                            k += 1
                        inner_text = ''.join(str(tokens[t].value)
                                             for t in range(paren_start, k - 1))
                        if inner_text.strip().upper().startswith("SELECT"):
                            # 直接解析子查询内容，不加外层括号
                            inner_parsed = sqlparse.parse(inner_text)
                            if inner_parsed:
                                inner_tables = _extract_from_flat_tokens(
                                    list(inner_parsed[0].flatten()))
                                result.extend(inner_tables)
                        j = k
                        break

                # 关键字终止
                if ntt is DML or (ntt is Keyword and nval.upper()
                                   not in ("AS", "ON", "USING")):
                    break

                if nval.upper() in ("AS", "ON", "USING"):
                    j += 1
                    break

                if isinstance(ntok, Identifier):
                    name = _ast_get_full_name(ntok)
                    if name:
                        result.append(name)
                    break

                if isinstance(ntok, IdentifierList):
                    for ident in ntok.get_identifiers():
                        name = _ast_get_full_name(ident)
                        if name:
                            result.append(name)
                    break

                if isinstance(ntok, Parenthesis):
                    # 子查询：递归提取内部表名
                    inner_tables = _extract_tables_from_text(str(ntok))
                    result.extend(inner_tables)
                    break

                if ntt in (Name, Name.Name):
                    # schema.table 可能被拆成 Name . Name 序列
                    # 注意：不收集 Name Name（那是表名+别名）
                    parts = [nval]
                    k = j + 1
                    while k < len(tokens):
                        ktok = tokens[k]
                        kval = str(ktok.value).strip()
                        ktt = getattr(ktok, "ttype", None)
                        if kval == ".":
                            parts.append(".")
                            k += 1
                            if k < len(tokens) and getattr(tokens[k], "ttype", None) in (Name, Name.Name):
                                parts.append(str(tokens[k].value))
                                k += 1
                            break
                        if not kval or kval.isspace():
                            k += 1
                            continue
                        # 连续的 Name 是别名，跳过
                        if ktt in (Name, Name.Name):
                            k += 1
                            break
                        break
                    full = "".join(parts)
                    if full:
                        result.append(full)
                    j = k
                    continue

                j += 1

            i = j if j < len(tokens) else len(tokens)

        return result

    def _extract_tables_from_text(sql_text: str) -> List[str]:
        """从 SQL 文本中提取表名（递归调用）"""
        inner_parsed = sqlparse.parse(sql_text)
        if not inner_parsed:
            return []
        return _extract_from_flat_tokens(list(inner_parsed[0].flatten()))

    # ---- 主逻辑 ----

    # 处理 CTE：WITH cte AS (SELECT ... FROM real_table) SELECT ...
    if stmt_text.upper().startswith("WITH"):
        # 方法：先整体解析，再分别提取 CTE 子句和主语句的表
        # CTE 内部表通过正则提取所有括号内的 SELECT 中的表
        paren_depth = 0
        cte_start = -1
        for m in re.finditer(r'[()]', stmt_text):
            if m.group() == '(':
                if paren_depth == 0:
                    cte_start = m.start()
                paren_depth += 1
            else:
                paren_depth -= 1
                if paren_depth == 0 and cte_start > 0:
                    inner = stmt_text[cte_start + 1:m.start()]
                    if inner.upper().strip().startswith("SELECT"):
                        inner_tables = _extract_tables_from_text(inner)
                        tables.extend(inner_tables)
                    cte_start = -1

        # 主语句：找到最后一个 CTE 括号后的主 SELECT
        main_start = 0
        for kw in (") SELECT", ") INSERT", ") UPDATE", ") DELETE"):
            idx = stmt_text.upper().find(kw)
            if idx != -1:
                main_start = max(main_start, idx + 2)
        if main_start > 0:
            main_part = stmt_text[main_start:].strip()
            if main_part:
                main_tables = _extract_tables_from_text(main_part)
                tables.extend(main_tables)
    else:
        # 普通语句（无 CTE）
        flat = list(stmt.flatten())
        tables = _extract_from_flat_tokens(flat)

    # 去重 & 过滤 CTE 表
    seen: Set[str] = set()
    unique: List[str] = []
    for t in tables:
        t_clean = t.replace('"', '').replace('`', '').replace('[', '').replace(']', '')
        if not t_clean:
            continue
        key = t_clean.upper()
        if key in cte_upper:
            continue
        if key not in seen:
            seen.add(key)
            unique.append(t_clean)
    return unique


# ===========================================================================
# SQLParser 类
# ===========================================================================

class SQLParser:
    """
    SQL解析器（AST + 正则双引擎）

    优先使用 sqlparse AST 解析，不可用时自动降级为正则表达式。
    AST 模式支持：
      - CTE（WITH 子句）表名过滤
      - 复杂嵌套子查询
      - 递归 CTE 识别
      - JOIN 表提取

    使用示例：
        parser = SQLParser()
        parsed = parser.parse("SELECT * FROM users WHERE id = 1")
        print(parsed.sql_type)  # SQLType.SELECT
        print(parsed.tables)    # ['users']
        print(parsed.has_where) # True
    """

    def __init__(self, dialect: SQLDialect = SQLDialect.GENERIC):
        self.dialect = dialect
        self._init_patterns()

    def _init_patterns(self):
        """初始化正则表达式模式（sqlparse 不可用时使用）"""
        self.comment_patterns = [
            re.compile(r'/\*.*?\*/', re.DOTALL),
            re.compile(r'--.*?$', re.MULTILINE),
            re.compile(r'#.*?$', re.MULTILINE),
        ]
        self.string_patterns = [
            re.compile(r"'(?:[^']|'')*'"),
            re.compile(r'"(?:[^"]|"")*"'),
            re.compile(r'`[^`]*`'),
        ]
        self.subquery_pattern = re.compile(r'\(\s*SELECT\s+', re.IGNORECASE)
        self.join_pattern = re.compile(
            r'\b(INNER|OUTER|LEFT|RIGHT|FULL|CROSS)?\s*JOIN\b', re.IGNORECASE
        )

    # ────────────────────────── 主入口 ──────────────────────────

    def parse(self, sql: str) -> ParsedSQL:
        """
        解析SQL语句（优先 sqlparse AST，回退正则）

        参数：
            sql: SQL语句

        返回：
            ParsedSQL: 解析结果
        """
        if not sql or not sql.strip():
            return ParsedSQL(original_sql="", sql_type=SQLType.UNKNOWN, is_read_only=False)

        original_sql = sql.strip()

        if HAS_SQLPARSE:
            try:
                return self._parse_with_sqlparse(original_sql)
            except Exception as e:
                logger.debug("sqlparse AST 解析失败，降级为正则: %s", e)

        return self._parse_with_regex(original_sql)

    # ────────────────────── AST 解析（sqlparse）────────────────────

    def _parse_with_sqlparse(self, sql: str) -> ParsedSQL:
        """使用 sqlparse AST 解析SQL"""
        parsed = sqlparse.parse(sql)
        if not parsed:
            return ParsedSQL(original_sql=sql, sql_type=SQLType.UNKNOWN, is_read_only=False)

        stmt = parsed[0]

        # 1. SQL 类型
        sql_type = self._ast_get_sqltype(stmt)
        is_read_only = self._is_read_only(sql_type)

        # 2. 表名提取（含 CTE 过滤）
        tables = _ast_extract_tables(stmt)

        # 3. WHERE / JOIN / 子查询
        has_where = _ast_has_where(stmt)
        has_join = _ast_has_join(stmt)
        has_subquery = _ast_has_subquery(stmt)

        where_clause = _ast_extract_where_text(stmt) if has_where else None

        return ParsedSQL(
            original_sql=sql,
            sql_type=sql_type,
            tables=tables,
            has_where=has_where,
            has_join=has_join,
            has_subquery=has_subquery,
            where_clause=where_clause,
            is_read_only=is_read_only,
            dialect=self.dialect,
        )

    @staticmethod
    def _ast_get_sqltype(stmt) -> SQLType:
        """从 AST 获取 SQL 类型（含 sqlparse 不原生支持的 SHOW/DESC）"""
        token_type = stmt.get_type()
        type_map = {
            "SELECT": SQLType.SELECT,
            "INSERT": SQLType.INSERT,
            "UPDATE": SQLType.UPDATE,
            "DELETE": SQLType.DELETE,
            "DROP": SQLType.DROP,
            "TRUNCATE": SQLType.TRUNCATE,
            "ALTER": SQLType.ALTER,
            "CREATE": SQLType.CREATE,
            "REPLACE": SQLType.REPLACE,
            "MERGE": SQLType.MERGE,
            "CALL": SQLType.CALL,
        }
        result = type_map.get(token_type.upper())
        if result:
            return result

        first_word = str(stmt.tokens[0]).strip().upper() if stmt.tokens else ""
        manual_map = {
            "SHOW": SQLType.SHOW,
            "DESC": SQLType.DESC,
            "DESCRIBE": SQLType.DESCRIBE,
            "EXPLAIN": SQLType.EXPLAIN,
        }
        return manual_map.get(first_word, SQLType.UNKNOWN)

    # ────────────────────── 正则降级 ─────────────────────

    def _parse_with_regex(self, sql: str) -> ParsedSQL:
        """使用正则表达式解析SQL（原实现）"""
        normalized_sql = self._normalize_sql(sql)
        sql_upper = normalized_sql.upper()

        sql_type = self._identify_sql_type(sql_upper)
        tables = self._extract_tables(normalized_sql, sql_type)
        has_where, where_clause = self._extract_where(normalized_sql)
        has_join = self._has_join(normalized_sql)
        has_subquery = self._has_subquery(normalized_sql)
        is_read_only = self._is_read_only(sql_type)

        return ParsedSQL(
            original_sql=sql,
            sql_type=sql_type,
            tables=tables,
            has_where=has_where,
            has_join=has_join,
            has_subquery=has_subquery,
            where_clause=where_clause,
            is_read_only=is_read_only,
            dialect=self.dialect,
        )

    # ────────────── 正则方法 ──────────────

    def _normalize_sql(self, sql: str) -> str:
        """标准化SQL语句（移除注释，保留字符串）"""
        strings = []

        def replace_string(match):
            strings.append(match.group(0))
            return f"__STRING_{len(strings)-1}__"

        normalized = sql
        for pattern in self.string_patterns:
            normalized = pattern.sub(replace_string, normalized)
        for pattern in self.comment_patterns:
            normalized = pattern.sub(' ', normalized)
        for i, s in enumerate(strings):
            normalized = normalized.replace(f"__STRING_{i}__", s)
        return ' '.join(normalized.split())

    def _identify_sql_type(self, sql_upper: str) -> SQLType:
        type_patterns = [
            (r'^\s*SELECT\s+', SQLType.SELECT),
            (r'^\s*INSERT\s+', SQLType.INSERT),
            (r'^\s*UPDATE\s+', SQLType.UPDATE),
            (r'^\s*DELETE\s+', SQLType.DELETE),
            (r'^\s*DROP\s+', SQLType.DROP),
            (r'^\s*TRUNCATE\s+', SQLType.TRUNCATE),
            (r'^\s*ALTER\s+', SQLType.ALTER),
            (r'^\s*CREATE\s+', SQLType.CREATE),
            (r'^\s*REPLACE\s+', SQLType.REPLACE),
            (r'^\s*MERGE\s+', SQLType.MERGE),
            (r'^\s*CALL\s+', SQLType.CALL),
            (r'^\s*EXPLAIN\s+', SQLType.EXPLAIN),
            (r'^\s*SHOW\s+', SQLType.SHOW),
            (r'^\s*DESCRIBE\s+', SQLType.DESCRIBE),
            (r'^\s*DESC\s+', SQLType.DESC),
        ]
        for pattern, st in type_patterns:
            if re.match(pattern, sql_upper, re.IGNORECASE):
                return st
        return SQLType.UNKNOWN

    def _extract_tables(self, sql: str, sql_type: SQLType) -> List[str]:
        """提取表名（正则）"""
        tables = []
        if sql_type == SQLType.SELECT:
            tables = self._extract_select_tables(sql)
        elif sql_type == SQLType.INSERT:
            tables = self._extract_insert_tables(sql)
        elif sql_type == SQLType.UPDATE:
            tables = self._extract_update_tables(sql)
        elif sql_type == SQLType.DELETE:
            tables = self._extract_delete_tables(sql)
        elif sql_type in (SQLType.DROP, SQLType.TRUNCATE, SQLType.ALTER):
            tables = self._extract_ddl_tables(sql, sql_type)

        seen: Set[str] = set()
        unique_tables = []
        for t in tables:
            t_clean = t.replace('`', '').replace('"', '').replace('[', '').replace(']', '')
            if t_clean and t_clean.upper() not in seen:
                seen.add(t_clean.upper())
                unique_tables.append(t_clean)
        return unique_tables

    def _extract_select_tables(self, sql: str) -> List[str]:
        tables = []
        from_pattern = re.compile(
            r"\bFROM\s+((?:[`\"\[][^`\"\]]+[`\"\]]|\w+)(?:\.(?:[`\"\[][^`\"\]]+[`\"\]]|\w+))*(?:\s*,\s*(?:[`\"\[][^`\"\]]+[`\"\]]|\w+)(?:\.(?:[`\"\[][^`\"\]]+[`\"\]]|\w+))*)*)",
            re.IGNORECASE
        )
        for match in from_pattern.finditer(sql):
            for table in re.split(r'\s*,\s*', match.group(1)):
                tables.append(table.strip())
        join_pattern = re.compile(
            r"\b(?:INNER|OUTER|LEFT|RIGHT|FULL|CROSS)?\s*JOIN\s+((?:[`\"\[][^`\"\]]+[`\"\]]|\w+)(?:\.(?:[`\"\[][^`\"\]]+[`\"\]]|\w+))*)",
            re.IGNORECASE
        )
        for match in join_pattern.finditer(sql):
            tables.append(match.group(1).strip())
        return tables

    def _extract_insert_tables(self, sql: str) -> List[str]:
        pattern = re.compile(
            r"\bINSERT\s+(?:INTO\s+)?((?:[`\"\[][^`\"\]]+[`\"\]]|\w+)(?:\.\w+)*)",
            re.IGNORECASE
        )
        match = pattern.search(sql)
        return [match.group(1).strip()] if match else []

    def _extract_update_tables(self, sql: str) -> List[str]:
        pattern = re.compile(
            r"\bUPDATE\s+((?:[`\"\[][^`\"\]]+[`\"\]]|\w+)(?:\.\w+)*)",
            re.IGNORECASE
        )
        match = pattern.search(sql)
        return [match.group(1).strip()] if match else []

    def _extract_delete_tables(self, sql: str) -> List[str]:
        pattern1 = re.compile(
            r"\bDELETE\s+FROM\s+((?:[`\"\[][^`\"\]]+[`\"\]]|\w+)(?:\.\w+)*)",
            re.IGNORECASE
        )
        pattern2 = re.compile(
            r"\bDELETE\s+((?:[`\"\[][^`\"\]]+[`\"\]]|\w+)(?:\.\w+)*)\s+(?:FROM|WHERE)",
            re.IGNORECASE
        )
        match = pattern1.search(sql) or pattern2.search(sql)
        return [match.group(1).strip()] if match else []

    def _extract_ddl_tables(self, sql: str, sql_type: SQLType) -> List[str]:
        type_str = sql_type.value
        pattern = re.compile(
            rf"\b{type_str}\s+(?:TABLE\s+)?((?:[`\"\[][^`\"\]]+[`\"\]]|\w+)(?:\.\w+)*)",
            re.IGNORECASE
        )
        match = pattern.search(sql)
        return [match.group(1).strip()] if match else []

    def _extract_where(self, sql: str) -> Tuple[bool, Optional[str]]:
        pattern = re.compile(
            r'\bWHERE\b(.+?)(?:\bORDER\s+BY\b|\bGROUP\s+BY\b|\bHAVING\b|\bLIMIT\b|\bUNION\b|$)',
            re.IGNORECASE
        )
        match = pattern.search(sql)
        if match:
            where_clause = match.group(1).strip()
            if where_clause and not re.match(r'^\s*(1\s*=\s*1|TRUE)\s*$', where_clause, re.IGNORECASE):
                return True, where_clause
        return False, None

    def _has_join(self, sql: str) -> bool:
        return bool(self.join_pattern.search(sql))

    def _has_subquery(self, sql: str) -> bool:
        return bool(self.subquery_pattern.search(sql))

    def _is_read_only(self, sql_type: SQLType) -> bool:
        read_only_types = {
            SQLType.SELECT, SQLType.EXPLAIN, SQLType.SHOW,
            SQLType.DESCRIBE, SQLType.DESC,
        }
        return sql_type in read_only_types

    def validate_syntax(self, sql: str) -> Tuple[bool, Optional[str]]:
        if not sql or not sql.strip():
            return False, "SQL语句不能为空"
        sql_clean = sql.strip()
        if sql_clean.count('(') != sql_clean.count(')'):
            return False, f"括号不匹配: 左括号{sql_clean.count('(')}个，右括号{sql_clean.count(')')}个"
        if sql_clean.count('[') != sql_clean.count(']'):
            return False, "方括号不匹配"
        parsed = self.parse(sql)
        if parsed.sql_type == SQLType.UNKNOWN:
            return False, "无法识别SQL类型"
        return True, None


# 全局解析器实例
_default_parser = SQLParser()


def parse_sql(sql: str, dialect: SQLDialect = SQLDialect.GENERIC) -> ParsedSQL:
    parser = SQLParser(dialect)
    return parser.parse(sql)


def is_read_only(sql: str) -> bool:
    parsed = _default_parser.parse(sql)
    return parsed.is_read_only


def is_dangerous_without_where(sql: str) -> bool:
    parsed = _default_parser.parse(sql)
    return parsed.is_dangerous_without_where()


__all__ = [
    "SQLType",
    "SQLDialect",
    "ParsedSQL",
    "SQLParser",
    "parse_sql",
    "is_read_only",
    "is_dangerous_without_where",
]
