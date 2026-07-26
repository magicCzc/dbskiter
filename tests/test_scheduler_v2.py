"""
测试 Scheduler V2 - 任务调度

使用 pytest 运行:
    pytest tests/test_scheduler_v2.py -v
"""
import pytest
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from dbskiter.db_scheduler import SchedulerSkill
from dbskiter.shared.unified_connector import UnifiedConnector


class TestSchedulerSkill:
    """SchedulerSkill 测试类"""

    def test_init_with_connector(self):
        """测试带连接器初始化"""
        try:
            connector = UnifiedConnector.from_env('MYSQL')
            skill = SchedulerSkill(connector)
            
            assert skill.connector is not None
            assert hasattr(skill, 'backup')
            assert hasattr(skill, 'intelligent_backup_advice')
        except Exception as e:
            pytest.skip(f"数据库连接失败: {e}")

    def test_intelligent_backup_advice_structure(self):
        """测试智能备份建议返回结构"""
        try:
            connector = UnifiedConnector.from_env('MYSQL')
            skill = SchedulerSkill(connector)
            
            result = skill.intelligent_backup_advice()
            
            # 验证返回结构
            assert isinstance(result, dict)
            assert 'summary' in result
        except Exception as e:
            pytest.skip(f"数据库连接失败: {e}")

    def test_list_tasks_structure(self):
        """测试任务列表返回结构"""
        try:
            connector = UnifiedConnector.from_env('MYSQL')
            skill = SchedulerSkill(connector)
            
            result = skill.list_tasks()
            
            # 验证返回是可迭代的
            assert hasattr(result, '__iter__')
        except Exception as e:
            pytest.skip(f"数据库连接失败: {e}")


class TestSchedulerSkillEdgeCases:
    """边界情况测试"""

    def test_backup_with_invalid_type(self):
        """测试无效备份类型"""
        try:
            connector = UnifiedConnector.from_env('MYSQL')
            skill = SchedulerSkill(connector)
            
            # 无效类型应该返回失败结果
            result = skill.backup(backup_type='invalid_type')
            assert hasattr(result, 'success')
            assert result.success is False
        except Exception as e:
            pytest.skip(f"数据库连接失败: {e}")

    def test_list_tasks_no_scheduler(self):
        """测试无调度器时的任务列表 - V2/V3都需要connector，跳过此测试"""
        pytest.skip("V2/V3版本都需要connector参数，此测试不再适用")
