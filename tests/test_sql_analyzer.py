"""
SQLAnalyzer子模块单元测试

文件功能：测试SQLAnalyzer的核心功能
主要测试类：
- TestSQLAnalyzer: SQL分析器核心功能测试

作者：AI Assistant
创建时间：2026-04-22
最后修改：2026-04-24 - 修复导入，移除不存在的模块依赖
"""

import unittest
import sys
from pathlib import Path
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).parent.parent))

from dbskiter.db_diagnose.analyzers.sql_analyzer import SQLAnalyzer


class MockConnector:
    """模拟数据库连接器"""

    def __init__(self, dialect="mysql"):
        self.dialect = dialect

    def execute(self, sql: str, params=None):
        """模拟执行SQL"""
        return Mock(rows=[], columns=[])


class TestSQLAnalyzer(unittest.TestCase):
    """测试SQLAnalyzer核心功能"""

    def setUp(self):
        """设置测试环境"""
        self.mock_connector = MockConnector()
        self.analyzer = SQLAnalyzer(self.mock_connector)

    def test_initialization(self):
        """测试初始化"""
        self.assertEqual(self.analyzer.connector, self.mock_connector)


if __name__ == '__main__':
    unittest.main()
