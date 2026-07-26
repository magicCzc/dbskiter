"""
验证所有导入正常

作者：AI Assistant
创建时间：2026-04-24
最后修改：2026-04-24 - 修复导入，移除不存在的V2/V3版本
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))


def test_scheduler_imports():
    """测试db_scheduler导入"""
    from dbskiter.db_scheduler import SchedulerSkill
    assert SchedulerSkill is not None


def test_monitor_imports():
    """测试db_monitor导入"""
    from dbskiter.db_monitor import MonitorSkill
    assert MonitorSkill is not None


def test_diagnose_imports():
    """测试db_diagnose导入"""
    from dbskiter.db_diagnose import DiagnoseSkill
    assert DiagnoseSkill is not None


def test_security_imports():
    """测试db_security导入"""
    from dbskiter.db_security import SecuritySkill
    assert SecuritySkill is not None


def test_sql_master_imports():
    """测试sql_master导入"""
    from dbskiter.sql_master import SQLMasterSkill
    assert SQLMasterSkill is not None


def test_inspector_imports():
    """测试db_inspector导入"""
    from dbskiter.db_inspector import InspectorSkill
    assert InspectorSkill is not None


def test_lock_analyzer_imports():
    """测试db_lock_analyzer导入"""
    from dbskiter.db_lock_analyzer import LockAnalyzerSkill
    assert LockAnalyzerSkill is not None


def test_sql_auditor_imports():
    """测试db_sql_auditor导入"""
    from dbskiter.db_sql_auditor import SQLAuditorSkill
    assert SQLAuditorSkill is not None


def test_cli_imports():
    """测试CLI命令导入"""
    from dbskiter.cli.commands import (
        SchedulerCommand, MonitorCommand, DiagnoseCommand,
        SecurityCommand, SQLCommand, InspectorCommand,
        LockCommand, SQLAuditCommand
    )
    assert all([
        SchedulerCommand is not None,
        MonitorCommand is not None,
        DiagnoseCommand is not None,
        SecurityCommand is not None,
        SQLCommand is not None,
        InspectorCommand is not None,
        LockCommand is not None,
        SQLAuditCommand is not None,
    ])


def test_shared_imports():
    """测试shared模块导入"""
    from dbskiter.shared import (
        UnifiedConnector,
        QueryResult,
    )
    from dbskiter.shared.mysql_aas_calculator_v2 import MySQLAASCalculatorV2
    from dbskiter.shared.aas_visualizer import AASVisualizer
    assert all([
        UnifiedConnector is not None,
        QueryResult is not None,
        MySQLAASCalculatorV2 is not None,
        AASVisualizer is not None,
    ])


if __name__ == '__main__':
    print('All imports successful!')
