"""
安全策略模块单元测试

文件功能：测试安全策略配置、SQL解析器、审计日志和安全执行器
测试覆盖：
    1. SQL解析器测试
    2. 安全策略配置测试
    3. 审计日志测试
    4. 安全执行器测试

作者：Security Team
创建时间：2026-05-20
最后修改：2026-05-20
"""

import os
import sys
import unittest
import tempfile
import shutil
from datetime import datetime, timedelta

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dbskiter.sql_master.sql_parser import (
    SQLParser, SQLType, SQLDialect, ParsedSQL,
    parse_sql, is_read_only, is_dangerous_without_where
)
from dbskiter.sql_master.audit_logger import (
    AuditLogger, StorageBackend, OperationStatus, AuditLogQuery
)
from dbskiter.sql_master.security_checker import (
    SecurityChecker, SQLInjectionDetector, RateLimiter, check_sql
)
from dbskiter.config.security_config import (
    SecurityLevel, SecurityPolicy, SecurityConfig, get_security_policy
)


class TestSQLParser(unittest.TestCase):
    """SQL解析器测试"""

    def setUp(self):
        self.parser = SQLParser()

    def test_parse_select(self):
        """测试SELECT解析"""
        sql = "SELECT * FROM users WHERE id = 1"
        parsed = self.parser.parse(sql)

        self.assertEqual(parsed.sql_type, SQLType.SELECT)
        self.assertEqual(parsed.tables, ["users"])
        self.assertTrue(parsed.has_where)
        self.assertTrue(parsed.is_read_only)
        self.assertFalse(parsed.is_dangerous_without_where())

    def test_parse_select_with_join(self):
        """测试带JOIN的SELECT"""
        sql = "SELECT u.*, o.name FROM users u JOIN orders o ON u.id = o.user_id"
        parsed = self.parser.parse(sql)

        self.assertEqual(parsed.sql_type, SQLType.SELECT)
        self.assertEqual(len(parsed.tables), 2)
        self.assertTrue(parsed.has_join)

    def test_parse_insert(self):
        """测试INSERT解析"""
        sql = "INSERT INTO users (name, email) VALUES ('test', 'test@example.com')"
        parsed = self.parser.parse(sql)

        self.assertEqual(parsed.sql_type, SQLType.INSERT)
        self.assertEqual(parsed.tables, ["users"])
        self.assertFalse(parsed.is_read_only)

    def test_parse_update_with_where(self):
        """测试带WHERE的UPDATE"""
        sql = "UPDATE users SET name = 'new' WHERE id = 1"
        parsed = self.parser.parse(sql)

        self.assertEqual(parsed.sql_type, SQLType.UPDATE)
        self.assertEqual(parsed.tables, ["users"])
        self.assertTrue(parsed.has_where)
        self.assertFalse(parsed.is_dangerous_without_where())

    def test_parse_update_without_where(self):
        """测试无WHERE的UPDATE"""
        sql = "UPDATE users SET name = 'new'"
        parsed = self.parser.parse(sql)

        self.assertEqual(parsed.sql_type, SQLType.UPDATE)
        self.assertFalse(parsed.has_where)
        self.assertTrue(parsed.is_dangerous_without_where())

    def test_parse_delete_with_where(self):
        """测试带WHERE的DELETE"""
        sql = "DELETE FROM users WHERE id = 1"
        parsed = self.parser.parse(sql)

        self.assertEqual(parsed.sql_type, SQLType.DELETE)
        self.assertEqual(parsed.tables, ["users"])
        self.assertTrue(parsed.has_where)
        self.assertFalse(parsed.is_dangerous_without_where())

    def test_parse_delete_without_where(self):
        """测试无WHERE的DELETE"""
        sql = "DELETE FROM users"
        parsed = self.parser.parse(sql)

        self.assertEqual(parsed.sql_type, SQLType.DELETE)
        self.assertFalse(parsed.has_where)
        self.assertTrue(parsed.is_dangerous_without_where())

    def test_parse_drop_table(self):
        """测试DROP TABLE"""
        sql = "DROP TABLE users"
        parsed = self.parser.parse(sql)

        self.assertEqual(parsed.sql_type, SQLType.DROP)
        self.assertEqual(parsed.tables, ["users"])

    def test_parse_truncate(self):
        """测试TRUNCATE"""
        sql = "TRUNCATE TABLE users"
        parsed = self.parser.parse(sql)

        self.assertEqual(parsed.sql_type, SQLType.TRUNCATE)
        self.assertEqual(parsed.tables, ["users"])

    def test_parse_with_backticks(self):
        """测试带反引号的表名"""
        sql = "SELECT * FROM `my-database`.`my-table`"
        parsed = self.parser.parse(sql)

        self.assertEqual(parsed.sql_type, SQLType.SELECT)
        self.assertEqual(parsed.tables, ["my-database.my-table"])

    def test_parse_with_comments(self):
        """测试带注释的SQL"""
        sql = """
        -- This is a comment
        SELECT * FROM users
        /* Multi-line
           comment */
        WHERE id = 1
        """
        parsed = self.parser.parse(sql)

        self.assertEqual(parsed.sql_type, SQLType.SELECT)
        self.assertTrue(parsed.has_where)

    def test_parse_subquery(self):
        """测试子查询"""
        sql = "SELECT * FROM (SELECT id FROM users) AS u"
        parsed = self.parser.parse(sql)

        self.assertEqual(parsed.sql_type, SQLType.SELECT)
        self.assertTrue(parsed.has_subquery)

    def test_validate_syntax(self):
        """测试语法验证"""
        # 有效SQL
        is_valid, error = self.parser.validate_syntax("SELECT * FROM users")
        self.assertTrue(is_valid)
        self.assertIsNone(error)

        # 空SQL
        is_valid, error = self.parser.validate_syntax("")
        self.assertFalse(is_valid)

        # 括号不匹配
        is_valid, error = self.parser.validate_syntax("SELECT * FROM (users")
        self.assertFalse(is_valid)


class TestSecurityPolicy(unittest.TestCase):
    """安全策略测试"""

    def test_default_policy(self):
        """测试默认策略"""
        policy = SecurityPolicy()

        self.assertTrue(policy.default_read_only)
        self.assertTrue(policy.requires_confirmation(SecurityLevel.MEDIUM))
        self.assertTrue(policy.requires_confirmation(SecurityLevel.HIGH))
        self.assertTrue(policy.requires_force(SecurityLevel.HIGH))
        self.assertEqual(policy.max_delete_rows, 1000)

    def test_custom_policy(self):
        """测试自定义策略"""
        policy = SecurityPolicy(
            default_read_only=False,
            max_delete_rows=100,
            blocked_operations={"DROP_TABLE"}
        )

        self.assertFalse(policy.default_read_only)
        self.assertEqual(policy.max_delete_rows, 100)
        self.assertTrue(policy.is_blocked("DROP_TABLE"))
        self.assertFalse(policy.is_blocked("DELETE"))

    def test_production_policy(self):
        """测试生产环境策略"""
        # 保存并清除环境变量，防止.env文件覆盖测试预期
        env_vars_to_clear = [
            "DBSKITER_DEFAULT_READ_ONLY", "DBSKITER_READ_ONLY",
            "DBSKITER_MAX_DELETE_ROWS", "DBSKITER_MAX_UPDATE_ROWS",
            "DBSKITER_BLOCKED_OPERATIONS", "DBSKITER_ENV",
            "DBSKITER_WHITELIST_TABLES", "DBSKITER_BLACKLIST_TABLES",
            "DBSKITER_ENABLE_AUDIT", "DBSKITER_ENABLE_BACKUP_REMINDER",
            "DBSKITER_ENABLE_IMPACT_PREVIEW", "DBSKITER_REQUIRE_CONFIRMATION",
        ]
        saved = {}
        for key in env_vars_to_clear:
            if key in os.environ:
                saved[key] = os.environ.pop(key)

        try:
            from dbskiter.config.security_config import reset_config, SecurityConfig
            reset_config()
            # 临时禁用dotenv加载，防止.env文件覆盖测试环境
            import dbskiter.config.security_config as sc_mod
            original_has_dotenv = sc_mod.HAS_DOTENV
            sc_mod.HAS_DOTENV = False

            try:
                config = SecurityConfig(environment="production")
                policy = config.policy

                self.assertTrue(policy.default_read_only)
                self.assertEqual(policy.max_delete_rows, 100)
                self.assertTrue(policy.is_blocked("DROP_DATABASE"))
            finally:
                sc_mod.HAS_DOTENV = original_has_dotenv
        finally:
            for key, val in saved.items():
                os.environ[key] = val
            from dbskiter.config.security_config import reset_config
            reset_config()

    def test_development_policy(self):
        """测试开发环境策略"""
        env_vars_to_clear = [
            "DBSKITER_DEFAULT_READ_ONLY", "DBSKITER_READ_ONLY",
            "DBSKITER_MAX_DELETE_ROWS", "DBSKITER_MAX_UPDATE_ROWS",
            "DBSKITER_BLOCKED_OPERATIONS", "DBSKITER_ENV",
            "DBSKITER_WHITELIST_TABLES", "DBSKITER_BLACKLIST_TABLES",
            "DBSKITER_ENABLE_AUDIT", "DBSKITER_ENABLE_BACKUP_REMINDER",
            "DBSKITER_ENABLE_IMPACT_PREVIEW", "DBSKITER_REQUIRE_CONFIRMATION",
        ]
        saved = {}
        for key in env_vars_to_clear:
            if key in os.environ:
                saved[key] = os.environ.pop(key)

        try:
            from dbskiter.config.security_config import reset_config, SecurityConfig
            reset_config()
            import dbskiter.config.security_config as sc_mod
            original_has_dotenv = sc_mod.HAS_DOTENV
            sc_mod.HAS_DOTENV = False

            try:
                config = SecurityConfig(environment="development")
                policy = config.policy

                self.assertFalse(policy.default_read_only)
                self.assertEqual(policy.max_delete_rows, 10000)
            finally:
                sc_mod.HAS_DOTENV = original_has_dotenv
        finally:
            for key, val in saved.items():
                os.environ[key] = val
            from dbskiter.config.security_config import reset_config
            reset_config()

    def test_whitelist_blacklist(self):
        """测试黑白名单"""
        policy = SecurityPolicy(
            whitelist_tables={"users", "orders"},
            blacklist_tables={"admin_users"}
        )

        # 白名单测试
        self.assertIn("users", policy.whitelist_tables)

        # 黑名单测试
        self.assertIn("admin_users", policy.blacklist_tables)


class TestAuditLogger(unittest.TestCase):
    """审计日志测试"""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "audit.db")

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    def test_log_to_sqlite(self):
        """测试SQLite日志记录"""
        logger = AuditLogger(
            backend=StorageBackend.SQLITE,
            storage_path=self.db_path
        )

        entry = logger.log(
            sql="SELECT * FROM users",
            database="test_db",
            risk_level="SAFE",
            status=OperationStatus.EXECUTED,
            row_count=10
        )

        self.assertIsNotNone(entry.id)
        self.assertEqual(entry.sql, "SELECT * FROM users")
        self.assertEqual(entry.row_count, 10)

        logger.close()

    def test_log_to_file(self):
        """测试文件日志记录"""
        log_path = os.path.join(self.temp_dir, "audit.log")
        logger = AuditLogger(
            backend=StorageBackend.FILE,
            storage_path=log_path
        )

        entry = logger.log(
            sql="DELETE FROM users WHERE id=1",
            database="test_db",
            risk_level="HIGH",
            status=OperationStatus.EXECUTED,
            force_used=True
        )

        self.assertTrue(entry.force_used)
        logger.close()

        # 验证文件存在且有内容
        self.assertTrue(os.path.exists(log_path))
        with open(log_path, 'r') as f:
            content = f.read()
            self.assertIn("DELETE FROM users", content)

    def test_query_sqlite(self):
        """测试SQLite查询"""
        logger = AuditLogger(
            backend=StorageBackend.SQLITE,
            storage_path=self.db_path
        )

        # 插入多条记录
        for i in range(5):
            logger.log(
                sql=f"SELECT * FROM table{i}",
                database="test_db",
                risk_level="SAFE" if i < 3 else "HIGH",
                status=OperationStatus.EXECUTED
            )

        logger.close()

        # 查询
        query = AuditLogQuery(logger)
        entries = query.query(risk_levels=["HIGH"])

        self.assertEqual(len(entries), 2)

    def test_statistics(self):
        """测试统计功能"""
        logger = AuditLogger(
            backend=StorageBackend.SQLITE,
            storage_path=self.db_path
        )

        # 插入测试数据
        logger.log(
            sql="SELECT * FROM users",
            database="db1",
            risk_level="SAFE",
            status=OperationStatus.EXECUTED
        )
        logger.log(
            sql="DELETE FROM orders",
            database="db1",
            risk_level="HIGH",
            status=OperationStatus.BLOCKED,
            force_used=True
        )

        logger.close()

        # 获取统计
        query = AuditLogQuery(logger)
        stats = query.get_statistics()

        self.assertEqual(stats["total_operations"], 2)
        self.assertEqual(stats["blocked_count"], 1)
        self.assertEqual(stats["force_used_count"], 1)


class TestSecurityIntegration(unittest.TestCase):
    """安全集成测试"""

    def test_dangerous_operations(self):
        """测试危险操作识别"""
        # DELETE无WHERE
        self.assertTrue(is_dangerous_without_where("DELETE FROM users"))

        # DELETE有WHERE
        self.assertFalse(is_dangerous_without_where("DELETE FROM users WHERE id=1"))

        # UPDATE无WHERE
        self.assertTrue(is_dangerous_without_where("UPDATE users SET name='x'"))

        # UPDATE有WHERE
        self.assertFalse(is_dangerous_without_where("UPDATE users SET name='x' WHERE id=1"))

        # SELECT永远不是危险操作
        self.assertFalse(is_dangerous_without_where("SELECT * FROM users"))

    def test_read_only_detection(self):
        """测试只读操作识别"""
        self.assertTrue(is_read_only("SELECT * FROM users"))
        self.assertTrue(is_read_only("EXPLAIN SELECT * FROM users"))
        self.assertTrue(is_read_only("SHOW TABLES"))
        self.assertTrue(is_read_only("DESCRIBE users"))

        self.assertFalse(is_read_only("INSERT INTO users VALUES (1)"))
        self.assertFalse(is_read_only("UPDATE users SET name='x'"))
        self.assertFalse(is_read_only("DELETE FROM users"))

    def test_parse_sql_convenience(self):
        """测试便捷函数"""
        parsed = parse_sql("SELECT * FROM users WHERE id = 1")

        self.assertEqual(parsed.sql_type, SQLType.SELECT)
        self.assertEqual(parsed.tables, ["users"])


class TestSQLInjectionDetector(unittest.TestCase):
    """SQL注入检测器测试"""

    def setUp(self):
        self.detector = SQLInjectionDetector()

    def test_detect_union_injection(self):
        """测试UNION注入检测"""
        sql = "SELECT * FROM users WHERE id = 1 UNION SELECT * FROM admin"
        result = self.detector.detect(sql)
        self.assertTrue(result.is_injection)
        self.assertIn("UNION", result.pattern_matched)

    def test_detect_or_injection(self):
        """测试OR注入检测"""
        sql = "SELECT * FROM users WHERE id = 1 OR 1=1"
        result = self.detector.detect(sql)
        self.assertTrue(result.is_injection)

    def test_detect_comment_injection(self):
        """测试注释注入检测"""
        sql = "SELECT * FROM users WHERE id = 1; -- comment"
        result = self.detector.detect(sql)
        self.assertTrue(result.is_injection)

    def test_detect_time_based_injection(self):
        """测试时间盲注检测"""
        sql = "SELECT * FROM users WHERE id = 1 AND SLEEP(5)"
        result = self.detector.detect(sql)
        self.assertTrue(result.is_injection)

    def test_safe_sql(self):
        """测试安全SQL"""
        sql = "SELECT * FROM users WHERE id = 1"
        result = self.detector.detect(sql)
        self.assertFalse(result.is_injection)

    def test_safe_insert(self):
        """测试安全INSERT"""
        sql = "INSERT INTO users (name) VALUES ('test')"
        result = self.detector.detect(sql)
        # INSERT语句可能触发某些模式，但置信度应该较低
        if result.is_injection:
            self.assertLess(result.confidence, 0.8, "INSERT语句不应被高置信度判定为注入")


class TestRateLimiter(unittest.TestCase):
    """速率限制器测试"""

    def setUp(self):
        self.limiter = RateLimiter(max_requests=3, window_seconds=60)

    def test_rate_limit_allows_under_limit(self):
        """测试限制内允许访问"""
        for i in range(3):
            status = self.limiter.check_limit("user_1", "SELECT")
            self.assertTrue(status.allowed)

    def test_rate_limit_blocks_over_limit(self):
        """测试超出限制阻止访问"""
        # 先使用完所有配额
        for i in range(3):
            self.limiter.check_limit("user_1", "SELECT")

        # 第4次应该被阻止
        status = self.limiter.check_limit("user_1", "SELECT")
        self.assertFalse(status.allowed)
        self.assertIsNotNone(status.retry_after)

    def test_rate_limit_per_user(self):
        """测试每个用户独立计算"""
        # user_1使用3次
        for i in range(3):
            self.limiter.check_limit("user_1", "SELECT")

        # user_2仍然可以访问
        status = self.limiter.check_limit("user_2", "SELECT")
        self.assertTrue(status.allowed)


class TestSecurityChecker(unittest.TestCase):
    """统一安全检查器测试"""

    def setUp(self):
        self.checker = SecurityChecker()

    def test_check_safe_sql(self):
        """测试安全SQL检查"""
        result = self.checker.check("SELECT * FROM users WHERE id = 1")
        self.assertTrue(result["passed"])
        self.assertEqual(result["risk_level"].value, "SAFE")

    def test_check_dangerous_delete(self):
        """测试危险DELETE检查"""
        result = self.checker.check("DELETE FROM users")
        self.assertTrue(result["passed"])
        self.assertEqual(result["risk_level"].value, "HIGH")

    def test_check_injection_sql(self):
        """测试注入SQL检查"""
        result = self.checker.check("SELECT * FROM users WHERE id = 1 OR 1=1")
        self.assertFalse(result["passed"])
        self.assertIn("注入", result["reason"])

    def test_check_blacklist_table(self):
        """测试黑名单检查"""
        result = self.checker.check(
            "SELECT * FROM admin_users",
            blacklist_tables={"admin_users"}
        )
        self.assertFalse(result["passed"])
        self.assertIn("黑名单", result["reason"])

    def test_check_whitelist_table(self):
        """测试白名单检查"""
        result = self.checker.check(
            "SELECT * FROM users",
            whitelist_tables={"users", "orders"}
        )
        self.assertTrue(result["passed"])

    def test_check_not_in_whitelist(self):
        """测试不在白名单中"""
        result = self.checker.check(
            "SELECT * FROM other_table",
            whitelist_tables={"users", "orders"}
        )
        self.assertFalse(result["passed"])
        self.assertIn("白名单", result["reason"])


def run_tests():
    """运行所有测试"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # 添加测试类
    suite.addTests(loader.loadTestsFromTestCase(TestSQLParser))
    suite.addTests(loader.loadTestsFromTestCase(TestSecurityPolicy))
    suite.addTests(loader.loadTestsFromTestCase(TestAuditLogger))
    suite.addTests(loader.loadTestsFromTestCase(TestSecurityIntegration))
    suite.addTests(loader.loadTestsFromTestCase(TestSQLInjectionDetector))
    suite.addTests(loader.loadTestsFromTestCase(TestRateLimiter))
    suite.addTests(loader.loadTestsFromTestCase(TestSecurityChecker))

    # 运行测试
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
