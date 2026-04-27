"""
SQL语法验证模块

文件功能：提供SQL语法预检查，在执行前验证SQL有效性
主要类：SQLSyntaxValidator - SQL语法验证器
"""
from typing import Dict, Any, List, Optional, Tuple
import logging
import re

logger = logging.getLogger(__name__)


class SQLSyntaxValidator:
    """
    SQL语法验证器
    
    在执行SQL前进行语法检查，避免执行明显错误的SQL
    """
    
    # 支持的SQL类型
    SUPPORTED_TYPES = {
        'SELECT', 'INSERT', 'UPDATE', 'DELETE',
        'CREATE', 'ALTER', 'DROP', 'TRUNCATE',
        'EXPLAIN', 'SHOW', 'DESCRIBE', 'DESC'
    }
    
    # 危险操作关键字
    DANGEROUS_KEYWORDS = {
        'DROP DATABASE',
        'DROP TABLE',
        'TRUNCATE TABLE',
        'DELETE FROM',
        'UPDATE.*SET.*=.*;',  # 无WHERE的UPDATE
    }
    
    def __init__(self):
        self.validation_rules = [
            self._check_empty_sql,
            self._check_sql_type,
            self._check_basic_syntax,
            self._check_dangerous_operations,
            self._check_unbalanced_parentheses,
            self._check_unclosed_quotes
        ]
    
    def validate(self, sql: str) -> Tuple[bool, Optional[str]]:
        """
        验证SQL语法
        
        参数:
            sql: SQL语句
            
        返回:
            Tuple[bool, Optional[str]]: (是否有效, 错误信息)
            
        示例:
            >>> validator = SQLSyntaxValidator()
            >>> validator.validate("SELECT * FROM users")
            (True, None)
            >>> validator.validate("SELECT * FROM")
            (False, "SQL语法错误: 缺少表名")
        """
        if not sql or not isinstance(sql, str):
            return False, "SQL不能为空"
        
        sql_clean = sql.strip()
        
        for rule in self.validation_rules:
            is_valid, error_msg = rule(sql_clean)
            if not is_valid:
                return False, error_msg
        
        return True, None
    
    def _check_empty_sql(self, sql: str) -> Tuple[bool, Optional[str]]:
        """检查空SQL"""
        if not sql.strip():
            return False, "SQL不能为空"
        return True, None
    
    def _check_sql_type(self, sql: str) -> Tuple[bool, Optional[str]]:
        """检查SQL类型是否支持"""
        first_word = sql.split()[0].upper()
        
        if first_word not in self.SUPPORTED_TYPES:
            return False, f"不支持的SQL类型: {first_word}"
        
        return True, None
    
    def _check_basic_syntax(self, sql: str) -> Tuple[bool, Optional[str]]:
        """检查基本语法"""
        sql_upper = sql.upper()
        
        # SELECT 必须有 FROM（除了简单SELECT 1）
        if sql_upper.startswith('SELECT') and 'FROM' not in sql_upper:
            # 允许 SELECT 1, SELECT NOW() 等简单查询
            if not re.match(r'^SELECT\s+\w+\s*$', sql_upper):
                return False, "SELECT语句缺少FROM子句"
        
        # INSERT 必须有 INTO
        if sql_upper.startswith('INSERT') and 'INTO' not in sql_upper:
            return False, "INSERT语句缺少INTO关键字"
        
        # UPDATE 必须有 SET
        if sql_upper.startswith('UPDATE') and 'SET' not in sql_upper:
            return False, "UPDATE语句缺少SET子句"
        
        # DELETE 必须有 FROM
        if sql_upper.startswith('DELETE') and 'FROM' not in sql_upper:
            return False, "DELETE语句缺少FROM子句"
        
        return True, None
    
    def _check_dangerous_operations(self, sql: str) -> Tuple[bool, Optional[str]]:
        """检查危险操作"""
        sql_upper = sql.upper()
        
        # 检查DROP DATABASE
        if re.search(r'DROP\s+DATABASE', sql_upper):
            return False, "危险操作: DROP DATABASE 被禁止"
        
        # 检查无WHERE的DELETE/UPDATE
        if sql_upper.startswith('DELETE') and 'WHERE' not in sql_upper:
            return False, "危险操作: DELETE语句缺少WHERE子句"
        
        if sql_upper.startswith('UPDATE') and 'WHERE' not in sql_upper:
            return False, "危险操作: UPDATE语句缺少WHERE子句"
        
        return True, None
    
    def _check_unbalanced_parentheses(self, sql: str) -> Tuple[bool, Optional[str]]:
        """检查括号是否平衡"""
        count = 0
        in_string = False
        string_char = None
        
        for char in sql:
            # 处理字符串
            if char in ("'", '"', '`'):
                if not in_string:
                    in_string = True
                    string_char = char
                elif char == string_char:
                    in_string = False
                    string_char = None
                continue
            
            if in_string:
                continue
            
            # 计数括号
            if char == '(':
                count += 1
            elif char == ')':
                count -= 1
                if count < 0:
                    return False, "SQL语法错误: 括号不匹配"
        
        if count != 0:
            return False, "SQL语法错误: 括号不匹配"
        
        return True, None
    
    def _check_unclosed_quotes(self, sql: str) -> Tuple[bool, Optional[str]]:
        """检查引号是否闭合"""
        single_quote_count = sql.count("'") - sql.count("\\'")
        double_quote_count = sql.count('"') - sql.count('\\"')
        
        if single_quote_count % 2 != 0:
            return False, "SQL语法错误: 单引号未闭合"
        
        if double_quote_count % 2 != 0:
            return False, "SQL语法错误: 双引号未闭合"
        
        return True, None
    
    def get_sql_type(self, sql: str) -> str:
        """获取SQL类型"""
        if not sql:
            return "UNKNOWN"
        
        first_word = sql.strip().split()[0].upper()
        return first_word if first_word in self.SUPPORTED_TYPES else "UNKNOWN"
    
    def is_read_only(self, sql: str) -> bool:
        """检查SQL是否为只读操作"""
        sql_upper = sql.strip().upper()
        return sql_upper.startswith('SELECT') or sql_upper.startswith('EXPLAIN')


class SQLPreChecker:
    """SQL预检查器（集成到执行流程）"""
    
    def __init__(self, validator: Optional[SQLSyntaxValidator] = None):
        self.validator = validator or SQLSyntaxValidator()
    
    def check(self, sql: str, allow_write: bool = True) -> Dict[str, Any]:
        """
        预检查SQL
        
        参数:
            sql: SQL语句
            allow_write: 是否允许写操作
            
        返回:
            Dict: 检查结果
        """
        # 语法验证
        is_valid, error_msg = self.validator.validate(sql)
        
        if not is_valid:
            return {
                "valid": False,
                "error": error_msg,
                "sql_type": None,
                "can_execute": False
            }
        
        sql_type = self.validator.get_sql_type(sql)
        is_read_only = self.validator.is_read_only(sql)
        
        # 检查写权限
        if not allow_write and not is_read_only:
            return {
                "valid": True,
                "error": "只读模式: 不允许执行写操作",
                "sql_type": sql_type,
                "can_execute": False
            }
        
        return {
            "valid": True,
            "error": None,
            "sql_type": sql_type,
            "is_read_only": is_read_only,
            "can_execute": True
        }
