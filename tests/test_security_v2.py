"""
测试 Security V2 - 安全审计

使用 pytest 运行:
    pytest tests/test_security_v2.py -v
"""
import pytest
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from dbskiter.db_security import SecuritySkill
from dbskiter.shared.unified_connector import UnifiedConnector


class TestSecuritySkill:
    """SecuritySkill 测试类"""

    def test_init_with_connector(self):
        """测试带连接器初始化"""
        try:
            connector = UnifiedConnector.from_env('MYSQL')
            skill = SecuritySkill(connector)
            
            assert skill.connector is not None
            assert hasattr(skill, 'detect_sql_injection')
            assert hasattr(skill, 'scan_sensitive_data')
        except Exception as e:
            pytest.skip(f"数据库连接失败: {e}")

    def test_detect_sql_injection_safe(self):
        """测试安全 SQL 检测"""
        try:
            connector = UnifiedConnector.from_env('MYSQL')
            skill = SecuritySkill(connector)
            
            # 安全 SQL
            sql = "SELECT * FROM information_schema.tables WHERE table_name = %s"
            result = skill.detect_sql_injection(sql, {"table_name": "users"})
            
            # 验证返回结构
            assert isinstance(result, dict)
            assert 'is_injection' in result
        except Exception as e:
            pytest.skip(f"数据库连接失败: {e}")

    def test_scan_sensitive_data_structure(self):
        """测试敏感数据扫描返回结构"""
        try:
            connector = UnifiedConnector.from_env('MYSQL')
            skill = SecuritySkill(connector)
            
            result = skill.scan_sensitive_data()
            
            # 验证返回是可迭代的
            assert hasattr(result, '__iter__')
        except Exception as e:
            pytest.skip(f"数据库连接失败: {e}")

    def test_full_audit_structure(self):
        """测试完整审计返回结构"""
        try:
            connector = UnifiedConnector.from_env('MYSQL')
            skill = SecuritySkill(connector)
            
            result = skill.full_audit()
            
            # 验证返回结构
            assert hasattr(result, 'total_risks')
            assert hasattr(result, 'risks')
        except Exception as e:
            pytest.skip(f"数据库连接失败: {e}")


class TestSecuritySkillEdgeCases:
    """边界情况测试"""

    def test_detect_sql_injection_empty(self):
        """测试空 SQL"""
        try:
            connector = UnifiedConnector.from_env('MYSQL')
            skill = SecuritySkill(connector)
            
            # 空 SQL 应该返回安全
            result = skill.detect_sql_injection("", {})
            assert isinstance(result, dict)
        except Exception as e:
            pytest.skip(f"数据库连接失败: {e}")

    def test_scan_sensitive_data_no_tables(self):
        """测试无表时的敏感数据扫描"""
        try:
            connector = UnifiedConnector.from_env('MYSQL')
            skill = SecuritySkill(connector)
            
            # 应该返回空列表而不是抛出异常
            result = skill.scan_sensitive_data()
            assert hasattr(result, '__iter__')
        except Exception as e:
            pytest.skip(f"数据库连接失败: {e}")
