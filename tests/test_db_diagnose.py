"""
db_diagnose模块单元测试

文件功能：测试DiagnoseSkill的核心功能
主要测试类：
- TestDiagnoseSkill: 核心功能测试
- TestDiagnoseConfig: 配置类测试

作者：AI Assistant
创建时间：2026-04-22
最后修改：2026-04-24 - 修复导入和API匹配
"""

import unittest
import sys
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from dbskiter.db_diagnose import (
    DiagnoseSkill,
    DiagnoseConfig,
    DiagnoseLevel,
    DiagnoseType,
    ErrorCode,
)


class MockConnector:
    """模拟数据库连接器"""

    def __init__(self, dialect="mysql"):
        self.dialect = dialect
        self.host = "localhost"
        self.port = 3306

    def execute(self, sql: str, params=None):
        """模拟执行SQL"""
        return Mock(rows=[], columns=[])


class TestDiagnoseSkill(unittest.TestCase):
    """测试DiagnoseSkill核心功能"""

    def setUp(self):
        """设置测试环境"""
        self.mock_connector = MockConnector()
        self.skill = DiagnoseSkill(self.mock_connector)

    def test_initialization(self):
        """测试初始化"""
        self.assertEqual(self.skill.connector, self.mock_connector)
        self.assertIsNotNone(self.skill.config)

    def test_config_creation(self):
        """测试配置创建"""
        config = DiagnoseConfig(
            slow_query_threshold=2.0,
            max_slow_queries=10
        )
        self.assertEqual(config.slow_query_threshold, 2.0)
        self.assertEqual(config.max_slow_queries, 10)


class TestDiagnoseConfig(unittest.TestCase):
    """测试DiagnoseConfig配置类"""

    def test_default_config(self):
        """测试默认配置"""
        config = DiagnoseConfig()
        self.assertIsNotNone(config)
        self.assertTrue(config.enable_deep_analysis)
        self.assertEqual(config.slow_query_threshold, 1.0)

    def test_custom_config(self):
        """测试自定义配置"""
        config = DiagnoseConfig(
            slow_query_threshold=2.0,
            max_slow_queries=10
        )
        self.assertEqual(config.slow_query_threshold, 2.0)
        self.assertEqual(config.max_slow_queries, 10)

    def test_config_to_dict(self):
        """测试配置转字典"""
        config = DiagnoseConfig()
        config_dict = config.to_dict()
        self.assertIn("enable_deep_analysis", config_dict)
        self.assertIn("slow_query_threshold", config_dict)


class TestEnums(unittest.TestCase):
    """测试枚举类型"""

    def test_diagnose_level(self):
        """测试诊断级别枚举"""
        self.assertIsNotNone(DiagnoseLevel.INFO)
        self.assertIsNotNone(DiagnoseLevel.LOW)
        self.assertIsNotNone(DiagnoseLevel.MEDIUM)
        self.assertIsNotNone(DiagnoseLevel.HIGH)
        self.assertIsNotNone(DiagnoseLevel.CRITICAL)

    def test_diagnose_type(self):
        """测试诊断类型枚举"""
        self.assertIsNotNone(DiagnoseType.SQL_ANALYSIS)
        self.assertIsNotNone(DiagnoseType.PERFORMANCE)
        self.assertIsNotNone(DiagnoseType.SLOW_QUERY)
        self.assertIsNotNone(DiagnoseType.TABLE_DIAGNOSE)
        self.assertIsNotNone(DiagnoseType.INDEX_SUGGESTION)

    def test_error_code(self):
        """测试错误码枚举"""
        self.assertIsNotNone(ErrorCode.SUCCESS)
        self.assertIsNotNone(ErrorCode.UNKNOWN_ERROR)


if __name__ == '__main__':
    unittest.main()
