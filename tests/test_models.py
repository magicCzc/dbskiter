"""
test_models.py

各模块 models.py 测试 - 验证修复后无重复定义

测试覆盖：
- 各模块 ErrorCode 类唯一性
- 各模块 create_success_response / create_error_response 来自 shared
- ErrorMessage 映射完整性
- 核心数据模型 to_dict
"""

import pytest


class TestDiagnoseModels:
    """db_diagnose/models.py 测试"""

    def test_error_code_unique_prefix(self):
        from dbskiter.db_diagnose.models import ErrorCode
        assert ErrorCode.SUCCESS.startswith("DIA")
        assert ErrorCode.ANALYSIS_FAILED.startswith("DIA")

    def test_error_message_coverage(self):
        from dbskiter.db_diagnose.models import ErrorCode, ErrorMessage
        for attr in dir(ErrorCode):
            if attr.startswith("_"):
                continue
            code = getattr(ErrorCode, attr)
            if isinstance(code, str):
                msg = ErrorMessage.get_message(code)
                assert msg is not None

    def test_diagnose_result_to_dict(self):
        from dbskiter.db_diagnose.models import DiagnoseResult
        result = DiagnoseResult(sql="SELECT 1", sql_type="SELECT", score=85.5)
        d = result.to_dict()
        assert d["sql"] == "SELECT 1"
        assert d["score"] == 85.5

    def test_diagnose_config_to_dict(self):
        from dbskiter.db_diagnose.models import DiagnoseConfig
        config = DiagnoseConfig()
        d = config.to_dict()
        assert "enable_deep_analysis" in d
        assert "slow_query_threshold" in d


class TestMonitorModels:
    """db_monitor/models.py 测试"""

    def test_error_code_unique_prefix(self):
        from dbskiter.db_monitor.models import ErrorCode
        assert ErrorCode.SUCCESS.startswith("MON")
        assert ErrorCode.COLLECTION_FAILED.startswith("MON")

    def test_error_message_coverage(self):
        from dbskiter.db_monitor.models import ErrorCode, ErrorMessage
        code = ErrorCode.COLLECTION_FAILED
        msg = ErrorMessage.get_message(code)
        assert msg == "指标采集失败"

    def test_health_status_enum(self):
        from dbskiter.db_monitor.models import HealthStatus
        assert HealthStatus.HEALTHY.value == "healthy"
        assert HealthStatus.CRITICAL.value == "critical"


class TestSecurityModels:
    """db_security/models.py 测试"""

    def test_error_code_unique_prefix(self):
        from dbskiter.db_security.models import ErrorCode
        assert ErrorCode.SUCCESS.startswith("SEC")
        assert ErrorCode.INJECTION_DETECTED.startswith("SEC")

    def test_risk_level_enum(self):
        from dbskiter.db_security.models import RiskLevel
        assert RiskLevel.CRITICAL.value == "critical"

    def test_risk_report_to_dict(self):
        from dbskiter.db_security.models import RiskReport
        report = RiskReport(total_risks=3, critical_count=1)
        d = report.to_dict()
        assert d["total_risks"] == 3
        assert d["critical_count"] == 1


class TestInspectorModels:
    """db_inspector/models.py 测试"""

    def test_error_code_unique_prefix(self):
        from dbskiter.db_inspector.models import ErrorCode
        assert ErrorCode.SUCCESS.startswith("INSP")
        assert ErrorCode.INSPECTION_FAILED.startswith("INSP")

    def test_inspection_item_to_dict(self):
        from dbskiter.db_inspector.models import InspectionItem, InspectionType, RiskLevel
        item = InspectionItem(
            name="慢查询检查",
            inspection_type=InspectionType.PERFORMANCE,
            risk_level=RiskLevel.HIGH,
            status="warning",
            description="存在慢查询"
        )
        d = item.to_dict()
        assert d["name"] == "慢查询检查"
        assert d["risk_level"] == "high"


class TestLockModels:
    """db_lock_analyzer/models.py 测试"""

    def test_error_code_unique_prefix(self):
        from dbskiter.db_lock_analyzer.models import ErrorCode
        assert ErrorCode.SUCCESS.startswith("LOCK")
        assert ErrorCode.LOCK_ANALYSIS_FAILED.startswith("LOCK")

    def test_lock_type_enum(self):
        from dbskiter.db_lock_analyzer.models import LockType
        assert LockType.TABLE.value == "table"
        assert LockType.ROW.value == "row"


class TestSqlAuditorModels:
    """db_sql_auditor/models.py 测试"""

    def test_error_code_unique_prefix(self):
        from dbskiter.db_sql_auditor.models import ErrorCode
        assert ErrorCode.SUCCESS.startswith("AUD")
        assert ErrorCode.AUDIT_FAILED.startswith("AUD")

    def test_audit_level_enum(self):
        from dbskiter.db_sql_auditor.models import AuditLevel
        assert AuditLevel.CRITICAL.value == "critical"


class TestSqlMasterModels:
    """sql_master/models.py 测试"""

    def test_error_code_unique_prefix(self):
        from dbskiter.sql_master.models import ErrorCode
        assert ErrorCode.SUCCESS.startswith("SQL")
        assert ErrorCode.EXECUTION_FAILED.startswith("SQL")

    def test_sql_type_enum(self):
        from dbskiter.sql_master.models import SQLType
        assert SQLType.SELECT.value == "select"


class TestSchedulerModels:
    """db_scheduler/models.py 测试"""

    def test_error_code_unique_prefix(self):
        from dbskiter.db_scheduler.models import ErrorCode
        assert ErrorCode.SUCCESS.startswith("SCH")
        assert ErrorCode.BACKUP_FAILED.startswith("SCH")

    def test_task_status_enum(self):
        from dbskiter.db_scheduler.models import TaskStatus
        assert TaskStatus.RUNNING.value == "running"


class TestSharedResponseFunctionsUniqueness:
    """验证所有模块的 create_success_response / create_error_response 来自 shared"""

    def test_diagnose_uses_shared(self):
        from dbskiter.db_diagnose import models as m
        from dbskiter.shared.error_handler import create_success_response, create_error_response
        assert m.create_success_response is create_success_response
        assert m.create_error_response is create_error_response

    def test_monitor_uses_shared(self):
        from dbskiter.db_monitor import models as m
        from dbskiter.shared.error_handler import create_success_response, create_error_response
        assert m.create_success_response is create_success_response
        assert m.create_error_response is create_error_response

    def test_sql_master_uses_shared(self):
        from dbskiter.sql_master import models as m
        from dbskiter.shared.error_handler import create_success_response, create_error_response
        assert m.create_success_response is create_success_response
        assert m.create_error_response is create_error_response

    def test_sql_auditor_uses_shared(self):
        from dbskiter.db_sql_auditor import models as m
        from dbskiter.shared.error_handler import create_success_response, create_error_response
        assert m.create_success_response is create_success_response
        assert m.create_error_response is create_error_response

    def test_security_uses_shared(self):
        from dbskiter.db_security import models as m
        from dbskiter.shared.error_handler import create_success_response, create_error_response
        assert m.create_success_response is create_success_response
        assert m.create_error_response is create_error_response

    def test_inspector_uses_shared(self):
        from dbskiter.db_inspector import models as m
        from dbskiter.shared.error_handler import create_success_response, create_error_response
        assert m.create_success_response is create_success_response
        assert m.create_error_response is create_error_response

    def test_lock_uses_shared(self):
        from dbskiter.db_lock_analyzer import models as m
        from dbskiter.shared.error_handler import create_success_response, create_error_response
        assert m.create_success_response is create_success_response
        assert m.create_error_response is create_error_response
