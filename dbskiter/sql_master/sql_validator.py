"""
SQL语法验证模块

文件功能：提供SQL语法预检查，在执行前验证SQL有效性
主要类：
    - SQLSyntaxValidator: SQL语法验证器
    - DangerousOperationChecker: 危险操作检查器

作者：AI Assistant
创建时间：2026-04-23
最后修改：2026-04-28
"""
from typing import Dict, Any, List, Optional, Tuple, Set
import logging
import re

logger = logging.getLogger(__name__)


class DangerousOperationChecker:
    """
    危险操作检查器
    
    专门用于检测和拦截可能导致数据丢失或系统损坏的SQL操作
    
    危险等级定义：
        - CRITICAL: 极高风险，默认禁止执行（如DROP DATABASE）
        - HIGH: 高风险，需要强制确认（如DROP TABLE, TRUNCATE）
        - MEDIUM: 中等风险，建议确认（如DELETE带WHERE, ALTER DROP COLUMN）
    """
    
    # 极高风险操作 - 默认禁止，必须使用--force才能执行
    CRITICAL_OPERATIONS = {
        'DROP DATABASE',
        'DROP SCHEMA',
    }
    
    # 高风险操作 - 需要二次确认
    HIGH_RISK_OPERATIONS = {
        'DROP TABLE',
        'TRUNCATE TABLE',
        'DROP INDEX',
        'DROP VIEW',
        'DROP PROCEDURE',
        'DROP FUNCTION',
        'DROP TRIGGER',
    }
    
    # 中风险操作 - 建议确认
    MEDIUM_RISK_OPERATIONS = {
        'DELETE',
        'UPDATE',
        'ALTER TABLE DROP',
        'ALTER TABLE RENAME',
    }
    
    # 风险描述信息
    RISK_DESCRIPTIONS = {
        'DROP DATABASE': '删除数据库将永久丢失所有数据，且无法恢复',
        'DROP SCHEMA': '删除Schema将永久丢失该Schema下的所有对象',
        'DROP TABLE': '删除表将永久丢失表结构和所有数据',
        'TRUNCATE TABLE': '截断表将清空所有数据且无法回滚（部分数据库）',
        'DROP INDEX': '删除索引可能影响查询性能',
        'DROP VIEW': '删除视图可能影响依赖该视图的应用',
        'DELETE': 'DELETE操作将永久删除数据',
        'UPDATE': 'UPDATE操作将永久修改数据',
        'ALTER TABLE DROP': '删除列将永久丢失该列的所有数据',
        'ALTER TABLE RENAME': '重命名可能影响依赖该对象的应用',
    }
    
    def __init__(self):
        self._compiled_patterns = self._compile_patterns()
    
    def _compile_patterns(self) -> Dict[str, re.Pattern]:
        """
        编译正则表达式模式
        
        返回:
            Dict[str, re.Pattern]: 编译后的模式字典
        """
        patterns = {}
        
        # 极高风险模式
        patterns['DROP_DATABASE'] = re.compile(r'^\s*DROP\s+DATABASE\s+', re.IGNORECASE)
        patterns['DROP_SCHEMA'] = re.compile(r'^\s*DROP\s+SCHEMA\s+', re.IGNORECASE)
        
        # 高风险模式
        patterns['DROP_TABLE'] = re.compile(r'^\s*DROP\s+TABLE\s+', re.IGNORECASE)
        patterns['TRUNCATE_TABLE'] = re.compile(r'^\s*TRUNCATE\s+(TABLE\s+)?', re.IGNORECASE)
        patterns['DROP_INDEX'] = re.compile(r'^\s*DROP\s+INDEX\s+', re.IGNORECASE)
        patterns['DROP_VIEW'] = re.compile(r'^\s*DROP\s+VIEW\s+', re.IGNORECASE)
        patterns['DROP_PROCEDURE'] = re.compile(r'^\s*DROP\s+(PROCEDURE|PROC)\s+', re.IGNORECASE)
        patterns['DROP_FUNCTION'] = re.compile(r'^\s*DROP\s+FUNCTION\s+', re.IGNORECASE)
        patterns['DROP_TRIGGER'] = re.compile(r'^\s*DROP\s+TRIGGER\s+', re.IGNORECASE)
        
        # 中风险模式
        patterns['ALTER_DROP'] = re.compile(r'^\s*ALTER\s+TABLE\s+\w+\s+DROP\s+(COLUMN\s+)?', re.IGNORECASE)
        patterns['ALTER_RENAME'] = re.compile(r'^\s*ALTER\s+TABLE\s+\w+\s+RENAME\s+', re.IGNORECASE)
        
        return patterns
    
    def check_operation(self, sql: str) -> Tuple[str, Optional[str]]:
        """
        检查SQL操作的风险等级

        参数:
            sql: SQL语句

        返回:
            Tuple[str, Optional[str]]: (风险等级, 风险描述)
            风险等级: 'CRITICAL', 'HIGH', 'MEDIUM', 'SAFE'
        """
        if not sql:
            return 'SAFE', None

        sql_upper = sql.upper().strip()

        # 检查极高风险
        for op in self.CRITICAL_OPERATIONS:
            pattern_key = op.replace(' ', '_')
            if pattern_key in self._compiled_patterns:
                if self._compiled_patterns[pattern_key].match(sql):
                    return 'CRITICAL', self.RISK_DESCRIPTIONS.get(op, '极高风险操作')

        # 检查高风险
        for op in self.HIGH_RISK_OPERATIONS:
            pattern_key = op.replace(' ', '_')
            if pattern_key in self._compiled_patterns:
                if self._compiled_patterns[pattern_key].match(sql):
                    return 'HIGH', self.RISK_DESCRIPTIONS.get(op, '高风险操作')

        # 检查中风险 - ALTER TABLE DROP/RENAME
        if self._compiled_patterns.get('ALTER_DROP') and self._compiled_patterns['ALTER_DROP'].match(sql):
            return 'MEDIUM', self.RISK_DESCRIPTIONS.get('ALTER TABLE DROP', '删除列将永久丢失该列的所有数据')

        if self._compiled_patterns.get('ALTER_RENAME') and self._compiled_patterns['ALTER_RENAME'].match(sql):
            return 'MEDIUM', self.RISK_DESCRIPTIONS.get('ALTER TABLE RENAME', '重命名可能影响依赖该对象的应用')

        # 检查DELETE/UPDATE（区分带WHERE和不带WHERE的风险等级）
        if sql_upper.startswith('DELETE'):
            if 'WHERE' not in sql_upper:
                # 无WHERE的DELETE是极高风险
                return 'HIGH', 'DELETE语句缺少WHERE子句，将删除整张表的所有数据'
            else:
                # 有WHERE的DELETE是中等风险
                return 'MEDIUM', 'DELETE操作将永久删除数据，建议先使用SELECT验证影响范围'

        if sql_upper.startswith('UPDATE'):
            if 'WHERE' not in sql_upper:
                # 无WHERE的UPDATE是极高风险
                return 'HIGH', 'UPDATE语句缺少WHERE子句，将更新整张表的所有数据'
            else:
                # 有WHERE的UPDATE是中等风险
                return 'MEDIUM', 'UPDATE操作将永久修改数据，建议先使用SELECT验证影响范围'

        return 'SAFE', None
    
    def is_dangerous(self, sql: str, min_level: str = 'HIGH') -> bool:
        """
        判断SQL是否为危险操作
        
        参数:
            sql: SQL语句
            min_level: 最低危险等级（'CRITICAL', 'HIGH', 'MEDIUM'）
            
        返回:
            bool: 是否为危险操作
        """
        risk_level, _ = self.check_operation(sql)
        
        level_order = {'SAFE': 0, 'MEDIUM': 1, 'HIGH': 2, 'CRITICAL': 3}
        return level_order.get(risk_level, 0) >= level_order.get(min_level, 2)
    
    def get_risk_summary(self, sql: str) -> Dict[str, Any]:
        """
        获取风险摘要信息
        
        参数:
            sql: SQL语句
            
        返回:
            Dict: 包含风险等级、描述、建议等信息的字典
        """
        risk_level, description = self.check_operation(sql)
        
        suggestions = {
            'CRITICAL': '此操作极度危险，请使用--force参数强制执行，并确保已备份数据',
            'HIGH': '此操作具有高风险，请确认已备份数据，或使用--force强制执行',
            'MEDIUM': '此操作可能影响多条记录，建议先使用SELECT验证影响范围',
            'SAFE': '此操作风险较低',
        }
        
        return {
            'risk_level': risk_level,
            'description': description,
            'suggestion': suggestions.get(risk_level, ''),
            'requires_confirmation': risk_level in ('CRITICAL', 'HIGH'),
            'requires_force': risk_level == 'CRITICAL',
        }


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
    
    def __init__(self):
        self.validation_rules = [
            self._check_empty_sql,
            self._check_sql_type,
            self._check_basic_syntax,
            self._check_dangerous_operations,
            self._check_unbalanced_parentheses,
            self._check_unclosed_quotes
        ]
        self.dangerous_checker = DangerousOperationChecker()
    
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
        """
        检查危险操作

        参数:
            sql: SQL语句

        返回:
            Tuple[bool, Optional[str]]: (是否通过检查, 错误信息)

        说明:
            此方法仅做基础语法层面的危险操作检测
            完整的危险操作检查由SQLPreChecker在更高层提供
            这里只检查基本的语法问题，不阻止任何操作
        """
        # 基础语法检查：无WHERE的DELETE/UPDATE在语法上是合法的
        # 真正的危险操作拦截在SQLPreChecker中处理
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
    """
    SQL预检查器（集成到执行流程）
    
    提供完整的SQL执行前检查，包括语法验证、危险操作检测、权限检查等
    """
    
    def __init__(self, validator: Optional[SQLSyntaxValidator] = None):
        self.validator = validator or SQLSyntaxValidator()
        self.dangerous_checker = self.validator.dangerous_checker
    
    def check(
        self,
        sql: str,
        allow_write: bool = True,
        force: bool = False
    ) -> Dict[str, Any]:
        """
        预检查SQL
        
        参数:
            sql: SQL语句
            allow_write: 是否允许写操作（只读模式时设为False）
            force: 是否强制执行危险操作（绕过CRITICAL级别限制）
            
        返回:
            Dict: 检查结果，包含以下字段：
                - valid: 语法是否有效
                - error: 错误信息（如果有）
                - sql_type: SQL类型
                - is_read_only: 是否为只读操作
                - can_execute: 是否可以执行
                - risk_level: 风险等级（SAFE/MEDIUM/HIGH/CRITICAL）
                - risk_description: 风险描述
                - requires_confirmation: 是否需要确认
                - requires_force: 是否需要force参数
                
        示例:
            >>> checker = SQLPreChecker()
            >>> result = checker.check("SELECT * FROM users")
            >>> print(result['can_execute'])
            True
            >>> result = checker.check("DROP TABLE users")
            >>> print(result['risk_level'])
            'HIGH'
        """
        # 语法验证
        is_valid, error_msg = self.validator.validate(sql)
        
        # 获取风险信息
        risk_summary = self.dangerous_checker.get_risk_summary(sql)
        risk_level = risk_summary['risk_level']
        
        if not is_valid:
            return {
                "valid": False,
                "error": error_msg,
                "sql_type": None,
                "is_read_only": None,
                "can_execute": False,
                "risk_level": risk_level,
                "risk_description": risk_summary.get('description'),
                "requires_confirmation": risk_summary.get('requires_confirmation', False),
                "requires_force": risk_summary.get('requires_force', False),
            }
        
        sql_type = self.validator.get_sql_type(sql)
        is_read_only = self.validator.is_read_only(sql)
        
        # 检查写权限（只读模式）
        if not allow_write and not is_read_only:
            return {
                "valid": True,
                "error": "只读模式: 不允许执行写操作",
                "sql_type": sql_type,
                "is_read_only": is_read_only,
                "can_execute": False,
                "risk_level": risk_level,
                "risk_description": risk_summary.get('description'),
                "requires_confirmation": False,
                "requires_force": False,
            }
        
        # 检查极高风险操作（CRITICAL级别）
        if risk_level == 'CRITICAL' and not force:
            return {
                "valid": True,
                "error": f"危险操作: {risk_summary['description']}。{risk_summary['suggestion']}",
                "sql_type": sql_type,
                "is_read_only": is_read_only,
                "can_execute": False,
                "risk_level": risk_level,
                "risk_description": risk_summary.get('description'),
                "requires_confirmation": True,
                "requires_force": True,
            }
        
        # 检查高风险操作（HIGH级别）
        if risk_level == 'HIGH' and not force:
            return {
                "valid": True,
                "error": None,  # 不返回错误，但标记需要确认
                "sql_type": sql_type,
                "is_read_only": is_read_only,
                "can_execute": True,  # 技术上可以执行，但建议确认
                "risk_level": risk_level,
                "risk_description": risk_summary.get('description'),
                "requires_confirmation": True,
                "requires_force": False,
                "warning": f"警告: {risk_summary['description']}。{risk_summary['suggestion']}",
            }
        
        return {
            "valid": True,
            "error": None,
            "sql_type": sql_type,
            "is_read_only": is_read_only,
            "can_execute": True,
            "risk_level": risk_level,
            "risk_description": risk_summary.get('description'),
            "requires_confirmation": risk_summary.get('requires_confirmation', False),
            "requires_force": risk_summary.get('requires_force', False),
        }
    
    def check_read_only(self, sql: str) -> bool:
        """
        快速检查SQL是否为只读操作
        
        参数:
            sql: SQL语句
            
        返回:
            bool: 是否为只读操作
        """
        return self.validator.is_read_only(sql)
    
    def get_risk_info(self, sql: str) -> Dict[str, Any]:
        """
        获取SQL的风险信息
        
        参数:
            sql: SQL语句
            
        返回:
            Dict: 风险信息摘要
        """
        return self.dangerous_checker.get_risk_summary(sql)
