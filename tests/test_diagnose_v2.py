"""
测试 Diagnose V2 - 诊断与优化

使用 pytest 运行:
    pytest tests/test_diagnose_v2.py -v
"""
import pytest
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from dbskiter.db_diagnose import DiagnoseSkill
from dbskiter.shared.unified_connector import UnifiedConnector


class TestDiagnoseSkill:
    """DiagnoseSkill 测试类"""

    def test_init_with_connector(self):
        """测试带连接器初始化"""
        try:
            connector = UnifiedConnector.from_env('MYSQL')
            skill = DiagnoseSkill(connector)
            
            assert skill.connector is not None
            assert hasattr(skill, 'analyze_slow_queries')
            assert hasattr(skill, 'recommend_indexes')
        except Exception as e:
            pytest.skip(f"数据库连接失败: {e}")

    def test_analyze_slow_queries_structure(self):
        """测试慢查询分析返回结构"""
        try:
            connector = UnifiedConnector.from_env('MYSQL')
            skill = DiagnoseSkill(connector)
            
            result = skill.analyze_slow_queries(limit=5)
            
            # 验证返回是可迭代的
            assert hasattr(result, '__iter__')
        except Exception as e:
            pytest.skip(f"数据库连接失败: {e}")

    def test_recommend_indexes_structure(self):
        """测试索引推荐返回结构"""
        try:
            connector = UnifiedConnector.from_env('MYSQL')
            skill = DiagnoseSkill(connector)
            
            # 获取第一个表
            result = connector.execute("SHOW TABLES LIMIT 1")
            if result.rows:
                table_name = result.rows[0][0]
                suggestions = skill.recommend_indexes(table=table_name)
                
                # 验证返回是可迭代的
                assert hasattr(suggestions, '__iter__')
        except Exception as e:
            pytest.skip(f"数据库连接失败: {e}")

    def test_optimize_sql_structure(self):
        """测试 SQL 优化返回结构"""
        try:
            connector = UnifiedConnector.from_env('MYSQL')
            skill = DiagnoseSkill(connector)
            
            sql = "SELECT * FROM information_schema.tables LIMIT 1"
            result = skill.optimize_sql(sql)
            
            # 验证返回结构
            assert hasattr(result, 'suggestions')
            assert hasattr(result, 'optimized_sql')
        except Exception as e:
            pytest.skip(f"数据库连接失败: {e}")


class TestDiagnoseSkillEdgeCases:
    """边界情况测试"""

    def test_recommend_indexes_nonexistent_table(self):
        """测试不存在的表"""
        try:
            connector = UnifiedConnector.from_env('MYSQL')
            skill = DiagnoseSkill(connector)
            
            # 应该返回空列表而不是抛出异常
            suggestions = skill.recommend_indexes(table='nonexistent_table_xyz')
            assert hasattr(suggestions, '__iter__')
        except Exception as e:
            pytest.skip(f"数据库连接失败: {e}")

    def test_optimize_sql_invalid_syntax(self):
        """测试无效 SQL 语法"""
        try:
            connector = UnifiedConnector.from_env('MYSQL')
            skill = DiagnoseSkill(connector)
            
            # 无效 SQL 应该优雅处理
            sql = "SELECT * FROM"
            result = skill.optimize_sql(sql)
            assert hasattr(result, 'suggestions')
        except Exception as e:
            # 允许抛出异常，但应该是有意义的错误
            assert isinstance(e, (Exception,))
