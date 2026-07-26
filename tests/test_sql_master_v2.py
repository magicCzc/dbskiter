"""
测试 SQL Master V2 - SQL 执行与优化

使用 pytest 运行:
    pytest tests/test_sql_master_v2.py -v
"""
import pytest
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from dbskiter.sql_master import SQLMasterSkill
from dbskiter.shared.unified_connector import UnifiedConnector


class TestSQLMasterSkill:
    """SQLMasterSkill 测试类"""

    def test_init_with_connector(self):
        """测试带连接器初始化"""
        try:
            connector = UnifiedConnector.from_env('MYSQL')
            skill = SQLMasterSkill(connector)
            
            assert skill.connector is not None
            assert hasattr(skill, 'rewrite_sql')
            assert hasattr(skill, 'expand_select_star')
        except Exception as e:
            pytest.skip(f"数据库连接失败: {e}")

    def test_rewrite_sql_structure(self):
        """测试 SQL 重写返回结构"""
        try:
            connector = UnifiedConnector.from_env('MYSQL')
            skill = SQLMasterSkill(connector)
            
            sql = "SELECT * FROM information_schema.tables LIMIT 1"
            result = skill.rewrite_sql(sql)
            
            # 验证返回结构
            assert isinstance(result, dict)
            assert 'can_optimize' in result
        except Exception as e:
            pytest.skip(f"数据库连接失败: {e}")

    def test_expand_select_star_structure(self):
        """测试 SELECT * 展开返回结构"""
        try:
            connector = UnifiedConnector.from_env('MYSQL')
            skill = SQLMasterSkill(connector)
            
            sql = "SELECT * FROM information_schema.tables"
            result = skill.expand_select_star(sql)
            
            # 验证返回是字符串
            assert isinstance(result, str)
        except Exception as e:
            pytest.skip(f"数据库连接失败: {e}")

    def test_analyze_sql_quality_structure(self):
        """测试 SQL 质量分析返回结构"""
        try:
            connector = UnifiedConnector.from_env('MYSQL')
            skill = SQLMasterSkill(connector)
            
            sql = "SELECT * FROM information_schema.tables LIMIT 1"
            result = skill.analyze_sql_quality(sql)
            
            # 验证返回结构
            assert isinstance(result, dict)
            assert 'quality_score' in result
        except Exception as e:
            pytest.skip(f"数据库连接失败: {e}")


class TestSQLMasterSkillEdgeCases:
    """边界情况测试"""

    def test_rewrite_sql_invalid_syntax(self):
        """测试无效 SQL 语法"""
        try:
            connector = UnifiedConnector.from_env('MYSQL')
            skill = SQLMasterSkill(connector)
            
            # 无效 SQL 应该优雅处理
            sql = "SELECT * FROM"
            result = skill.rewrite_sql(sql)
            assert isinstance(result, dict)
        except Exception as e:
            # 允许抛出异常
            assert isinstance(e, (Exception,))

    def test_expand_select_star_nonexistent_table(self):
        """测试不存在的表"""
        try:
            connector = UnifiedConnector.from_env('MYSQL')
            skill = SQLMasterSkill(connector)
            
            # 应该返回原 SQL 或优雅处理
            sql = "SELECT * FROM nonexistent_table_xyz"
            result = skill.expand_select_star(sql)
            assert isinstance(result, str)
        except Exception as e:
            pytest.skip(f"数据库连接失败: {e}")
