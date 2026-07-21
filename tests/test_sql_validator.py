"""
tests/test_sql_validator.py
SQL语法验证器单元测试

覆盖 dbskiter.sql_master.sql_validator:
    - DangerousOperationChecker
    - SQLSyntaxValidator
    - SQLPreChecker
"""

import pytest

from dbskiter.sql_master.sql_validator import (
    DangerousOperationChecker,
    SQLSyntaxValidator,
    SQLPreChecker,
)


# =============================================================================
# DangerousOperationChecker 测试
# =============================================================================


class TestDangerousOperationChecker:
    """危险操作检查器测试"""

    def setup_method(self):
        self.checker = DangerousOperationChecker()

    def test_critical_drop_database(self):
        """极高风险：DROP DATABASE"""
        level, desc = self.checker.check_operation("DROP DATABASE production;")
        assert level == "CRITICAL"
        assert desc is not None
        assert "删除数据库" in desc

    def test_critical_drop_schema(self):
        """极高风险：DROP SCHEMA"""
        level, desc = self.checker.check_operation("DROP SCHEMA public;")
        assert level == "CRITICAL"

    def test_high_drop_table(self):
        """高风险：DROP TABLE"""
        level, desc = self.checker.check_operation("DROP TABLE users;")
        assert level == "HIGH"
        assert "删除表" in desc

    def test_high_truncate_table(self):
        """高风险：TRUNCATE TABLE"""
        level, desc = self.checker.check_operation("TRUNCATE TABLE logs;")
        assert level == "HIGH"

    def test_high_truncate_without_table_keyword(self):
        """高风险：TRUNCATE without TABLE"""
        level, desc = self.checker.check_operation("TRUNCATE logs;")
        assert level == "HIGH"

    def test_high_drop_index(self):
        """高风险：DROP INDEX"""
        level, desc = self.checker.check_operation("DROP INDEX idx_users;")
        assert level == "HIGH"

    def test_high_drop_view(self):
        """高风险：DROP VIEW"""
        level, desc = self.checker.check_operation("DROP VIEW user_view;")
        assert level == "HIGH"

    def test_high_drop_procedure(self):
        """高风险：DROP PROCEDURE"""
        level, desc = self.checker.check_operation("DROP PROCEDURE my_proc;")
        assert level == "HIGH"

    def test_high_drop_function(self):
        """高风险：DROP FUNCTION"""
        level, desc = self.checker.check_operation("DROP FUNCTION my_func;")
        assert level == "HIGH"

    def test_high_drop_trigger(self):
        """高风险：DROP TRIGGER"""
        level, desc = self.checker.check_operation("DROP TRIGGER my_trigger;")
        assert level == "HIGH"

    def test_medium_alter_drop_column(self):
        """中风险：ALTER TABLE DROP COLUMN"""
        level, desc = self.checker.check_operation("ALTER TABLE users DROP COLUMN age;")
        assert level == "MEDIUM"

    def test_medium_alter_rename(self):
        """中风险：ALTER TABLE RENAME"""
        level, desc = self.checker.check_operation("ALTER TABLE users RENAME TO users_old;")
        assert level == "MEDIUM"

    def test_high_delete_without_where(self):
        """高风险：DELETE 无 WHERE"""
        level, desc = self.checker.check_operation("DELETE FROM users;")
        assert level == "HIGH"
        assert "缺少WHERE" in desc

    def test_medium_delete_with_where(self):
        """中风险：DELETE 有 WHERE"""
        level, desc = self.checker.check_operation("DELETE FROM users WHERE id = 1;")
        assert level == "MEDIUM"

    def test_high_update_without_where(self):
        """高风险：UPDATE 无 WHERE"""
        level, desc = self.checker.check_operation("UPDATE users SET name = 'x';")
        assert level == "HIGH"
        assert "缺少WHERE" in desc

    def test_medium_update_with_where(self):
        """中风险：UPDATE 有 WHERE"""
        level, desc = self.checker.check_operation("UPDATE users SET name = 'x' WHERE id = 1;")
        assert level == "MEDIUM"

    def test_safe_select(self):
        """安全：SELECT"""
        level, desc = self.checker.check_operation("SELECT * FROM users")
        assert level == "SAFE"
        assert desc is None

    def test_safe_insert(self):
        """安全：INSERT"""
        level, desc = self.checker.check_operation("INSERT INTO users (name) VALUES ('x')")
        assert level == "SAFE"

    def test_empty_sql(self):
        """空 SQL"""
        level, desc = self.checker.check_operation("")
        assert level == "SAFE"
        assert desc is None

    def test_lowercase_dangerous(self):
        """小写 SQL 也能识别"""
        level, desc = self.checker.check_operation("drop table users;")
        assert level == "HIGH"

    def test_is_dangerous_with_min_level_high(self):
        """is_dangerous 默认 HIGH 阈值"""
        assert self.checker.is_dangerous("DROP TABLE users") is True
        assert self.checker.is_dangerous("UPDATE users SET x=1 WHERE id=1") is False
        assert self.checker.is_dangerous("DELETE FROM users WHERE id=1") is False
        assert self.checker.is_dangerous("SELECT * FROM users") is False

    def test_is_dangerous_with_min_level_medium(self):
        """is_dangerous MEDIUM 阈值"""
        assert self.checker.is_dangerous("UPDATE users SET x=1 WHERE id=1", "MEDIUM") is True
        assert self.checker.is_dangerous("ALTER TABLE users DROP COLUMN age", "MEDIUM") is True
        assert self.checker.is_dangerous("SELECT * FROM users", "MEDIUM") is False

    def test_is_dangerous_with_min_level_critical(self):
        """is_dangerous CRITICAL 阈值"""
        assert self.checker.is_dangerous("DROP DATABASE prod", "CRITICAL") is True
        assert self.checker.is_dangerous("DROP TABLE users", "CRITICAL") is False

    def test_get_risk_summary_safe(self):
        """get_risk_summary 安全操作"""
        summary = self.checker.get_risk_summary("SELECT * FROM users")
        assert summary["risk_level"] == "SAFE"
        assert "description" in summary
        assert "requires_confirmation" in summary
        assert summary["requires_confirmation"] is False

    def test_get_risk_summary_critical(self):
        """get_risk_summary 极高风险"""
        summary = self.checker.get_risk_summary("DROP DATABASE prod")
        assert summary["risk_level"] == "CRITICAL"
        assert summary["requires_force"] is True
        assert summary["requires_confirmation"] is True

    def test_get_risk_summary_medium(self):
        """get_risk_summary 中风险"""
        summary = self.checker.get_risk_summary("DELETE FROM users WHERE id = 1")
        assert summary["risk_level"] == "MEDIUM"
        assert "description" in summary


# =============================================================================
# SQLSyntaxValidator 测试
# =============================================================================


class TestSQLSyntaxValidator:
    """SQL 语法验证器测试"""

    def setup_method(self):
        self.validator = SQLSyntaxValidator()

    def test_valid_select(self):
        """有效 SELECT"""
        is_valid, err = self.validator.validate("SELECT * FROM users")
        assert is_valid is True
        assert err is None

    def test_valid_select_simple(self):
        """有效简单 SELECT"""
        is_valid, err = self.validator.validate("SELECT 1")
        assert is_valid is True

    def test_valid_insert(self):
        """有效 INSERT"""
        is_valid, err = self.validator.validate("INSERT INTO users (name) VALUES ('x')")
        assert is_valid is True

    def test_valid_update(self):
        """有效 UPDATE"""
        is_valid, err = self.validator.validate("UPDATE users SET name = 'x' WHERE id = 1")
        assert is_valid is True

    def test_valid_delete(self):
        """有效 DELETE"""
        is_valid, err = self.validator.validate("DELETE FROM users WHERE id = 1")
        assert is_valid is True

    def test_valid_create(self):
        """有效 CREATE"""
        is_valid, err = self.validator.validate("CREATE TABLE x (id INT)")
        assert is_valid is True

    def test_valid_drop(self):
        """有效 DROP"""
        is_valid, err = self.validator.validate("DROP TABLE x")
        assert is_valid is True

    def test_valid_explain(self):
        """有效 EXPLAIN"""
        is_valid, err = self.validator.validate("EXPLAIN SELECT * FROM users")
        assert is_valid is True

    def test_valid_show(self):
        """有效 SHOW"""
        is_valid, err = self.validator.validate("SHOW TABLES")
        assert is_valid is True

    def test_empty_sql(self):
        """空 SQL"""
        is_valid, err = self.validator.validate("")
        assert is_valid is False
        assert "空" in err

    def test_whitespace_only(self):
        """仅空白"""
        is_valid, err = self.validator.validate("   \n\t  ")
        assert is_valid is False

    def test_unsupported_sql_type(self):
        """不支持的 SQL 类型"""
        is_valid, err = self.validator.validate("INVALID * FROM users")
        assert is_valid is False
        assert "不支持" in err

    def test_select_without_from(self):
        """SELECT 缺少 FROM"""
        is_valid, err = self.validator.validate("SELECT users")
        # SELECT users 应该允许 (简单查询)
        assert is_valid is True

    def test_insert_without_into(self):
        """INSERT 缺少 INTO"""
        is_valid, err = self.validator.validate("INSERT users VALUES (1)")
        assert is_valid is False
        assert "INTO" in err

    def test_update_without_set(self):
        """UPDATE 缺少 SET"""
        is_valid, err = self.validator.validate("UPDATE users WHERE id = 1")
        assert is_valid is False
        assert "SET" in err

    def test_delete_without_from(self):
        """DELETE 缺少 FROM"""
        is_valid, err = self.validator.validate("DELETE WHERE id = 1")
        assert is_valid is False
        assert "FROM" in err

    def test_unbalanced_parentheses_too_many_open(self):
        """括号不平衡（多左括号）"""
        is_valid, err = self.validator.validate("SELECT * FROM users WHERE (id = 1")
        assert is_valid is False
        assert "括号" in err

    def test_unbalanced_parentheses_too_many_close(self):
        """括号不平衡（多右括号）"""
        is_valid, err = self.validator.validate("SELECT * FROM users) WHERE id = 1")
        assert is_valid is False
        assert "括号" in err

    def test_unclosed_single_quote(self):
        """未闭合单引号"""
        is_valid, err = self.validator.validate("SELECT * FROM users WHERE name = 'test")
        assert is_valid is False
        assert "引号" in err

    def test_unclosed_double_quote(self):
        """未闭合双引号"""
        is_valid, err = self.validator.validate('SELECT * FROM users WHERE name = "test')
        assert is_valid is False
        assert "引号" in err

    def test_balanced_quotes(self):
        """平衡的引号"""
        is_valid, err = self.validator.validate("SELECT * FROM users WHERE name = 'test'")
        assert is_valid is True

    def test_get_sql_type_select(self):
        """获取 SQL 类型 SELECT"""
        assert self.validator.get_sql_type("SELECT * FROM users") == "SELECT"

    def test_get_sql_type_insert(self):
        assert self.validator.get_sql_type("INSERT INTO x") == "INSERT"

    def test_get_sql_type_update(self):
        assert self.validator.get_sql_type("UPDATE x SET y=1") == "UPDATE"

    def test_get_sql_type_delete(self):
        assert self.validator.get_sql_type("DELETE FROM x") == "DELETE"

    def test_get_sql_type_unknown(self):
        """未知类型"""
        assert self.validator.get_sql_type("INVALID * FROM x") == "UNKNOWN"

    def test_get_sql_type_empty(self):
        """空 SQL"""
        assert self.validator.get_sql_type("") == "UNKNOWN"

    def test_is_read_only_select(self):
        """只读：SELECT"""
        assert self.validator.is_read_only("SELECT * FROM users") is True

    def test_is_read_only_explain(self):
        """只读：EXPLAIN"""
        assert self.validator.is_read_only("EXPLAIN SELECT * FROM users") is True

    def test_is_read_only_insert(self):
        """非只读：INSERT"""
        assert self.validator.is_read_only("INSERT INTO x VALUES (1)") is False

    def test_is_read_only_update(self):
        """非只读：UPDATE"""
        assert self.validator.is_read_only("UPDATE x SET y=1") is False

    def test_is_read_only_delete(self):
        """非只读：DELETE"""
        assert self.validator.is_read_only("DELETE FROM x") is False

    def test_is_read_only_drop(self):
        """非只读：DROP"""
        assert self.validator.is_read_only("DROP TABLE x") is False


# =============================================================================
# SQLPreChecker 测试
# =============================================================================


class TestSQLPreChecker:
    """SQL 预检查器测试"""

    def setup_method(self):
        self.checker = SQLPreChecker()

    def test_check_valid_select(self):
        """合法 SELECT 检查"""
        result = self.checker.check("SELECT * FROM users")
        assert result["valid"] is True
        assert result["error"] is None
        assert result["sql_type"] == "SELECT"
        assert result["is_read_only"] is True
        assert result["can_execute"] is True
        assert result["risk_level"] == "SAFE"

    def test_check_critical_requires_force(self):
        """CRITICAL 操作需要 force"""
        result = self.checker.check("DROP DATABASE prod")
        assert result["risk_level"] == "CRITICAL"
        assert result["requires_force"] is True
        assert result["can_execute"] is False

    def test_check_critical_with_force(self):
        """CRITICAL 操作带 force 允许执行"""
        result = self.checker.check("DROP DATABASE prod", force=True)
        assert result["can_execute"] is True
        assert result["risk_level"] == "CRITICAL"

    def test_check_high_warning(self):
        """HIGH 操作警告但仍可执行"""
        result = self.checker.check("DROP TABLE users")
        assert result["risk_level"] == "HIGH"
        assert result["can_execute"] is True
        assert result["requires_confirmation"] is True

    def test_check_readonly_blocks_write(self):
        """只读模式禁止写操作"""
        result = self.checker.check("DELETE FROM users", allow_write=False)
        assert result["is_read_only"] is False
        assert result["can_execute"] is False
        assert "只读" in result["error"]

    def test_check_readonly_allows_read(self):
        """只读模式允许读操作"""
        result = self.checker.check("SELECT * FROM users", allow_write=False)
        assert result["can_execute"] is True

    def test_check_invalid_sql(self):
        """无效 SQL"""
        result = self.checker.check("INVALID * FROM users")
        assert result["valid"] is False
        assert result["can_execute"] is False

    def test_check_read_only_helper(self):
        """check_read_only 帮助函数"""
        assert self.checker.check_read_only("SELECT 1") is True
        assert self.checker.check_read_only("DELETE FROM x") is False

    def test_get_risk_info(self):
        """get_risk_info"""
        info = self.checker.get_risk_info("DROP TABLE users")
        assert "risk_level" in info
        assert info["risk_level"] == "HIGH"

    def test_check_delete_with_where_medium(self):
        """DELETE 带 WHERE 是中风险"""
        result = self.checker.check("DELETE FROM users WHERE id = 1")
        assert result["risk_level"] == "MEDIUM"
        assert result["can_execute"] is True