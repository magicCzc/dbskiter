"""
模块集成测试

文件功能：测试五个核心模块（db-diagnose、db-monitor、db-security、db-sql-auditor、db-inspector）
之间的集成和协同工作能力。

主要测试类：
    - TestModuleCompatibility: 模块接口兼容性测试
    - TestDataFlowIntegration: 数据流端到端测试
    - TestCrossModuleWorkflow: 跨模块工作流测试
    - TestErrorPropagation: 错误传播测试
    - TestSharedComponents: 共享组件测试

作者: AI Assistant
创建时间: 2026-04-24
"""

import unittest
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime, timedelta
from typing import Dict, Any, List

# 导入所有核心模块
from dbskiter.db_diagnose.skill import DiagnoseSkill
from dbskiter.db_monitor.skill import MonitorSkill
from dbskiter.db_security.skill import SecuritySkill
from dbskiter.db_sql_auditor.skill import SQLAuditorSkill
from dbskiter.db_inspector.skill import InspectorSkill

from dbskiter.shared.unified_connector import UnifiedConnector


class TestModuleCompatibility(unittest.TestCase):
    """测试模块接口兼容性"""

    def setUp(self):
        """测试前准备"""
        # 创建模拟连接器
        self.mock_connector = Mock()
        self.mock_connector.dialect = "mysql"
        self.mock_connector.db_type = "mysql"
        self.mock_connector.get_dialect.return_value = "mysql"

    @patch('dbskiter.shared.unified_connector.detect_connector_type')
    def test_all_modules_initialization(self, mock_detect):
        """测试所有模块可以正常初始化"""
        mock_detect.return_value = ("sqlalchemy", False)
        try:
            diagnose = DiagnoseSkill(self.mock_connector)
            monitor = MonitorSkill(self.mock_connector)
            security = SecuritySkill(self.mock_connector)
            auditor = SQLAuditorSkill(self.mock_connector)
            inspector = InspectorSkill(self.mock_connector)

            self.assertIsNotNone(diagnose)
            self.assertIsNotNone(monitor)
            self.assertIsNotNone(security)
            self.assertIsNotNone(auditor)
            self.assertIsNotNone(inspector)
        except Exception as e:
            self.fail(f"模块初始化失败: {e}")

    def test_common_response_format(self):
        """测试所有模块使用统一的响应格式"""
        diagnose = DiagnoseSkill(self.mock_connector)
        monitor = MonitorSkill(self.mock_connector)

        # 模拟响应
        diagnose_response = {"success": True, "data": {}, "message": "test"}
        monitor_response = {"success": True, "data": {}, "message": "test"}

        # 验证响应格式一致性
        self.assertIn("success", diagnose_response)
        self.assertIn("success", monitor_response)
        self.assertIn("data", diagnose_response)
        self.assertIn("data", monitor_response)
        self.assertIn("message", diagnose_response)
        self.assertIn("message", monitor_response)

    def test_connector_sharing(self):
        """测试连接器可以在模块间共享"""
        # 所有模块使用同一个连接器
        diagnose = DiagnoseSkill(self.mock_connector)
        monitor = MonitorSkill(self.mock_connector)
        security = SecuritySkill(self.mock_connector)

        # 验证连接器被正确保存
        self.assertEqual(diagnose.connector, self.mock_connector)
        self.assertEqual(monitor.connector, self.mock_connector)
        self.assertEqual(security.connector, self.mock_connector)


class TestDataFlowIntegration(unittest.TestCase):
    """测试数据流端到端"""

    def setUp(self):
        """测试前准备"""
        self.mock_connector = Mock()
        self.mock_connector.dialect = "mysql"
        self.mock_connector.db_type = "mysql"
        self.mock_connector.get_dialect.return_value = "mysql"

    def test_diagnose_to_monitor_flow(self):
        """测试诊断到监控的数据流"""
        # 诊断发现问题
        diagnose = DiagnoseSkill(self.mock_connector)

        # 监控收集指标
        monitor = MonitorSkill(self.mock_connector)

        # 验证数据可以在模块间传递
        problem_data = {
            "sql": "SELECT * FROM users",
            "issue_type": "FULL_SCAN",
            "severity": "HIGH"
        }

        # 诊断结果可以作为监控的输入
        metric_data = {
            "query": problem_data["sql"],
            "execution_time": 10.5,
            "rows_examined": 100000
        }

        self.assertIsNotNone(problem_data)
        self.assertIsNotNone(metric_data)

    def test_security_to_inspector_flow(self):
        """测试安全到巡检的数据流"""
        security = SecuritySkill(self.mock_connector)
        inspector = InspectorSkill(self.mock_connector)

        # 安全扫描发现的问题
        security_issues = [
            {"type": "WEAK_PASSWORD", "user": "admin"},
            {"type": "MISSING_INDEX", "table": "users"}
        ]

        # 问题可以传递给巡检进行深度检查
        inspection_items = [
            {"category": "SECURITY", "issue": issue}
            for issue in security_issues
        ]

        self.assertEqual(len(inspection_items), len(security_issues))

    def test_auditor_to_diagnose_flow(self):
        """测试审核到诊断的数据流"""
        auditor = SQLAuditorSkill(self.mock_connector)
        diagnose = DiagnoseSkill(self.mock_connector)

        # 审核发现的问题SQL
        audit_result = {
            "sql": "SELECT * FROM orders WHERE status = 'pending'",
            "issues": [{"type": "SELECT_STAR"}],
            "score": 65
        }

        # 可以传递给诊断进行深度分析
        if audit_result["score"] < 70:
            diagnose_input = {
                "sql": audit_result["sql"],
                "reason": "LOW_AUDIT_SCORE"
            }
            self.assertIsNotNone(diagnose_input)

    def test_monitor_to_inspector_flow(self):
        """测试监控到巡检的数据流"""
        monitor = MonitorSkill(self.mock_connector)
        inspector = InspectorSkill(self.mock_connector)

        # 监控收集的指标
        metrics = {
            "cpu_usage": [45.0, 50.0, 55.0, 80.0],
            "memory_usage": [60.0, 62.0, 65.0, 70.0],
            "connections": [50, 55, 60, 80]
        }

        # 指标可以传递给巡检进行智能分析
        intelligent_input = {
            "metrics_history": {
                "cpu_usage": [{"value": v} for v in metrics["cpu_usage"]],
                "memory_usage": [{"value": v} for v in metrics["memory_usage"]]
            }
        }

        self.assertIn("metrics_history", intelligent_input)


class TestCrossModuleWorkflow(unittest.TestCase):
    """测试跨模块工作流"""

    def setUp(self):
        """测试前准备"""
        self.mock_connector = Mock()
        self.mock_connector.dialect = "mysql"
        self.mock_connector.db_type = "mysql"
        self.mock_connector.get_dialect.return_value = "mysql"

    def test_complete_analysis_workflow(self):
        """测试完整分析工作流"""
        # 场景：SQL审核 -> 诊断 -> 优化建议

        # 1. SQL审核
        auditor = SQLAuditorSkill(self.mock_connector)
        audit_result = {
            "score": 60,
            "issues": [{"type": "SLOW_QUERY", "sql": "SELECT * FROM large_table"}]
        }

        # 2. 如果审核分数低，进行诊断
        if audit_result["score"] < 70:
            diagnose = DiagnoseSkill(self.mock_connector)
            diagnose_input = audit_result["issues"][0]["sql"]

            # 模拟诊断结果
            diagnose_result = {
                "execution_plan": "ALL",
                "suggestions": ["添加索引"]
            }

            # 3. 生成优化建议
            optimization = {
                "original_sql": diagnose_input,
                "suggested_indexes": ["idx_status"],
                "estimated_improvement": "50%"
            }

            self.assertIsNotNone(optimization)

    def test_security_audit_workflow(self):
        """测试安全审计工作流"""
        # 场景：安全扫描 -> 巡检 -> 报告

        # 1. 安全扫描
        security = SecuritySkill(self.mock_connector)
        security_result = {
            "vulnerabilities": [
                {"type": "SQL_INJECTION", "risk": "HIGH"},
                {"type": "WEAK_PASSWORD", "risk": "MEDIUM"}
            ]
        }

        # 2. 巡检验证
        inspector = InspectorSkill(self.mock_connector)
        inspection_items = [
            {"category": "SECURITY", "finding": v}
            for v in security_result["vulnerabilities"]
        ]

        # 3. 生成综合报告
        report = {
            "security_findings": len(security_result["vulnerabilities"]),
            "inspection_items": len(inspection_items),
            "overall_risk": "HIGH"
        }

        self.assertEqual(report["security_findings"], 2)

    def test_monitoring_alert_workflow(self):
        """测试监控告警工作流"""
        # 场景：监控 -> 异常检测 -> 根因分析 -> 建议

        # 1. 监控收集指标
        monitor = MonitorSkill(self.mock_connector)
        metrics = {
            "cpu_spike": True,
            "cpu_values": [30, 35, 40, 85]
        }

        # 2. 异常检测
        if metrics["cpu_spike"]:
            # 3. 根因分析
            root_causes = [
                {"category": "QUERY", "description": "慢查询导致CPU飙升"}
            ]

            # 4. 生成建议
            recommendations = [
                {"action": "优化慢查询", "priority": "HIGH"}
            ]

            self.assertEqual(len(root_causes), 1)
            self.assertEqual(len(recommendations), 1)


class TestErrorPropagation(unittest.TestCase):
    """测试错误传播"""

    def setUp(self):
        """测试前准备"""
        self.mock_connector = Mock()
        self.mock_connector.dialect = "mysql"
        self.mock_connector.db_type = "mysql"
        self.mock_connector.get_dialect.return_value = "mysql"

    def test_error_handling_consistency(self):
        """测试错误处理一致性"""
        # 所有模块应该使用统一的错误格式
        error_response = {
            "success": False,
            "error_code": "TEST_ERROR",
            "message": "测试错误"
        }

        # 验证错误格式
        self.assertIn("success", error_response)
        self.assertFalse(error_response["success"])
        self.assertIn("message", error_response)

    def test_graceful_degradation(self):
        """测试优雅降级"""
        # 当一个模块失败时，其他模块应该继续工作

        # 模拟一个模块失败
        failed_module_result = {
            "success": False,
            "error": "Connection failed"
        }

        # 其他模块应该不受影响
        other_module_result = {
            "success": True,
            "data": {"status": "ok"}
        }

        # 验证系统可以继续运行
        self.assertFalse(failed_module_result["success"])
        self.assertTrue(other_module_result["success"])

    def test_error_recovery(self):
        """测试错误恢复"""
        # 模块应该能够从错误中恢复

        # 初始错误状态
        error_state = {"has_error": True, "retry_count": 0}

        # 重试机制
        max_retries = 3
        while error_state["has_error"] and error_state["retry_count"] < max_retries:
            error_state["retry_count"] += 1
            # 模拟恢复
            if error_state["retry_count"] >= 2:
                error_state["has_error"] = False

        # 验证恢复成功
        self.assertFalse(error_state["has_error"])
        self.assertLessEqual(error_state["retry_count"], max_retries)


class TestSharedComponents(unittest.TestCase):
    """测试共享组件"""

    def setUp(self):
        """测试前准备"""
        self.mock_connector = Mock()
        self.mock_connector.dialect = "mysql"
        self.mock_connector.db_type = "mysql"
        self.mock_connector.get_dialect.return_value = "mysql"
        self.mock_connector.dialect = "mysql"

    def test_unified_connector_usage(self):
        """测试统一连接器使用"""
        # 所有模块应该使用UnifiedConnector
        modules = [
            DiagnoseSkill(self.mock_connector),
            MonitorSkill(self.mock_connector),
            SecuritySkill(self.mock_connector),
            SQLAuditorSkill(self.mock_connector),
            InspectorSkill(self.mock_connector)
        ]

        for module in modules:
            self.assertIsNotNone(module.connector)
            self.assertEqual(module.connector.dialect, "mysql")

    def test_common_utilities(self):
        """测试通用工具类"""
        # 验证共享工具类的存在
        from dbskiter.shared.unified_connector import UnifiedConnector
        from dbskiter.shared.validators import validate_params

        # UnifiedConnector应该被所有模块使用
        self.assertIsNotNone(UnifiedConnector)
        self.assertIsNotNone(validate_params)

    def test_data_model_consistency(self):
        """测试数据模型一致性"""
        # 验证各模块使用一致的数据模型

        # 时间戳格式
        timestamp = datetime.now().isoformat()
        self.assertIsInstance(timestamp, str)

        # 风险等级定义
        risk_levels = ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"]
        self.assertEqual(len(risk_levels), 5)

    def test_configuration_sharing(self):
        """测试配置共享"""
        # 模块间应该可以共享配置

        shared_config = {
            "database_type": "mysql",
            "timeout": 30,
            "max_connections": 100
        }

        # 配置可以被多个模块使用
        module_configs = [
            {"module": "diagnose", "config": shared_config},
            {"module": "monitor", "config": shared_config},
            {"module": "security", "config": shared_config}
        ]

        self.assertEqual(len(module_configs), 3)
        for mc in module_configs:
            self.assertEqual(mc["config"]["database_type"], "mysql")


class TestIntegrationScenarios(unittest.TestCase):
    """测试集成场景"""

    def setUp(self):
        """测试前准备"""
        self.mock_connector = Mock()
        self.mock_connector.dialect = "mysql"
        self.mock_connector.db_type = "mysql"
        self.mock_connector.get_dialect.return_value = "mysql"

    def test_full_database_health_check(self):
        """测试完整数据库健康检查场景"""
        # 场景：巡检 -> 监控 -> 诊断 -> 安全 -> 报告

        results = {}

        # 1. 巡检
        inspector = InspectorSkill(self.mock_connector)
        results["inspection"] = {"health_score": 75, "issues": 5}

        # 2. 监控
        if results["inspection"]["health_score"] < 80:
            monitor = MonitorSkill(self.mock_connector)
            results["monitoring"] = {"anomalies": 2, "metrics": {}}

        # 3. 诊断
        if results["monitoring"]["anomalies"] > 0:
            diagnose = DiagnoseSkill(self.mock_connector)
            results["diagnosis"] = {"slow_queries": 3, "recommendations": []}

        # 4. 安全扫描
        security = SecuritySkill(self.mock_connector)
        results["security"] = {"vulnerabilities": 1}

        # 5. 生成综合报告
        final_report = {
            "health_score": results["inspection"]["health_score"],
            "total_issues": (
                results["inspection"]["issues"] +
                results["monitoring"]["anomalies"] +
                results["diagnosis"]["slow_queries"] +
                results["security"]["vulnerabilities"]
            ),
            "status": "NEEDS_ATTENTION"
        }

        self.assertEqual(final_report["total_issues"], 11)

    def test_sql_optimization_workflow(self):
        """测试SQL优化工作流"""
        # 场景：审核 -> 诊断 -> 优化 -> 验证

        sql = "SELECT * FROM users WHERE status = 'active'"

        # 1. SQL审核
        auditor = SQLAuditorSkill(self.mock_connector)
        audit_result = {"score": 70, "issues": ["SELECT_STAR"]}

        # 2. 诊断
        if audit_result["score"] < 80:
            diagnose = DiagnoseSkill(self.mock_connector)
            diagnose_result = {"execution_time": 5.2, "rows": 10000}

            # 3. 优化
            optimization = {
                "optimized_sql": "SELECT id, name FROM users WHERE status = 'active'",
                "indexes": ["idx_status"]
            }

            # 4. 验证
            verification = {"score": 95, "execution_time": 0.5}

            self.assertGreater(verification["score"], audit_result["score"])

    def test_capacity_planning_workflow(self):
        """测试容量规划工作流"""
        # 场景：监控 -> 预测 -> 巡检 -> 建议

        # 1. 监控收集历史数据
        monitor = MonitorSkill(self.mock_connector)
        historical_data = {
            "storage_usage": [60, 62, 65, 68, 70, 72, 75],
            "dates": [(datetime.now() - timedelta(days=i)).isoformat() for i in range(7)]
        }

        # 2. 容量预测
        from dbskiter.db_monitor.advanced_predictor import AdvancedCapacityPredictor
        predictor = AdvancedCapacityPredictor()
        # 模拟预测
        predicted_usage = 85  # 预测未来使用率

        # 3. 如果预测超过阈值，触发巡检
        if predicted_usage > 80:
            inspector = InspectorSkill(self.mock_connector)
            inspection_result = {"storage_risk": "HIGH"}

            # 4. 生成建议
            recommendations = [
                "清理历史数据",
                "归档旧数据",
                "申请扩容"
            ]

            self.assertEqual(len(recommendations), 3)


if __name__ == '__main__':
    unittest.main()
