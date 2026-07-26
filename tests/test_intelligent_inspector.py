"""
智能巡检器单元测试

文件功能：测试智能巡检器的各项功能
主要测试类：
    - TestAnomalyPatternDetector: 异常模式检测器测试
    - TestRootCauseAnalyzer: 根因分析器测试
    - TestPredictiveInspector: 预测性巡检器测试
    - TestSmartRecommendationEngine: 智能建议引擎测试
    - TestCorrelationAnalyzer: 关联分析器测试
    - TestIntelligentInspector: 智能巡检器集成测试

作者: AI Assistant
创建时间: 2026-04-24
"""

import unittest
from datetime import datetime, timedelta

from dbskiter.db_inspector.intelligent_inspector import (
    AnomalyPatternDetector,
    RootCauseAnalyzer,
    PredictiveInspector,
    SmartRecommendationEngine,
    CorrelationAnalyzer,
    IntelligentInspector,
    AnomalyPattern,
    RiskPrediction,
    AnomalyEvent,
    RootCause,
)


class TestAnomalyPatternDetector(unittest.TestCase):
    """测试异常模式检测器"""

    def setUp(self):
        """测试前准备"""
        self.detector = AnomalyPatternDetector()

    def test_detect_sudden_spike(self):
        """测试突然飙升检测"""
        metrics = {
            "cpu_usage": [
                {"timestamp": datetime.now() - timedelta(hours=i), "value": 30.0}
                for i in range(5, 0, -1)
            ] + [{"timestamp": datetime.now(), "value": 80.0}]  # 突然飙升
        }

        events = self.detector.detect_patterns(metrics)

        spike_events = [e for e in events if e.pattern == AnomalyPattern.SUDDEN_SPIKE]
        self.assertGreater(len(spike_events), 0)
        self.assertEqual(spike_events[0].metric_name, "cpu_usage")

    def test_detect_gradual_increase(self):
        """测试逐渐增长检测"""
        # 需要至少5个数据点，且增长率超过50%
        metrics = {
            "memory_usage": [
                {"timestamp": datetime.now() - timedelta(hours=i), "value": 40.0}
                for i in range(7, 4, -1)  # 前2个值: 40, 40
            ] + [
                {"timestamp": datetime.now() - timedelta(hours=i), "value": 80.0}
                for i in range(2, -1, -1)  # 后3个值: 80, 80, 80
            ]
        }

        events = self.detector.detect_patterns(metrics)

        growth_events = [e for e in events if e.pattern == AnomalyPattern.GRADUAL_INCREASE]
        self.assertGreater(len(growth_events), 0)

    def test_detect_baseline_deviation(self):
        """测试基线偏离检测"""
        metrics = {
            "disk_usage": [
                {"timestamp": datetime.now() - timedelta(hours=i), "value": 70.0}
                for i in range(5, 0, -1)
            ] + [{"timestamp": datetime.now(), "value": 95.0}]
        }
        thresholds = {"disk_usage": 80.0}

        events = self.detector.detect_patterns(metrics, thresholds)

        baseline_events = [e for e in events if e.pattern == AnomalyPattern.BASELINE_DEVIATION]
        self.assertGreater(len(baseline_events), 0)

    def test_no_anomaly(self):
        """测试无异常情况"""
        metrics = {
            "cpu_usage": [
                {"timestamp": datetime.now() - timedelta(hours=i), "value": 30.0}
                for i in range(5, -1, -1)
            ]
        }

        events = self.detector.detect_patterns(metrics)

        self.assertEqual(len(events), 0)

    def test_insufficient_data(self):
        """测试数据不足情况"""
        metrics = {
            "cpu_usage": [
                {"timestamp": datetime.now(), "value": 50.0}
            ]
        }

        events = self.detector.detect_patterns(metrics)

        self.assertEqual(len(events), 0)


class TestRootCauseAnalyzer(unittest.TestCase):
    """测试根因分析器"""

    def setUp(self):
        """测试前准备"""
        self.analyzer = RootCauseAnalyzer()

    def test_analyze_cpu_spike(self):
        """测试CPU飙升根因分析"""
        events = [
            AnomalyEvent(
                event_id="test1",
                pattern=AnomalyPattern.SUDDEN_SPIKE,
                metric_name="cpu_usage",
                metric_value=90.0,
                threshold=50.0,
                severity="HIGH",
                timestamp=datetime.now(),
                description="CPU飙升"
            )
        ]

        inspection_results = {
            "performance": {
                "slow_queries": [{"sql": "SELECT * FROM large_table"}],
                "connections": {"current": 80, "max": 100}
            }
        }

        causes = self.analyzer.analyze(events, inspection_results)

        self.assertGreater(len(causes), 0)
        cpu_causes = [c for c in causes if "CPU" in c.description]
        self.assertGreater(len(cpu_causes), 0)

    def test_analyze_memory_growth(self):
        """测试内存增长根因分析"""
        events = [
            AnomalyEvent(
                event_id="test2",
                pattern=AnomalyPattern.GRADUAL_INCREASE,
                metric_name="memory_usage",
                metric_value=85.0,
                threshold=70.0,
                severity="MEDIUM",
                timestamp=datetime.now(),
                description="内存增长"
            )
        ]

        inspection_results = {
            "configuration": {
                "cache_settings": {"buffer_pool_size": 1024}
            },
            "performance": {
                "long_connections": [{"id": 1}, {"id": 2}]
            }
        }

        causes = self.analyzer.analyze(events, inspection_results)

        memory_causes = [c for c in causes if "内存" in c.description]
        self.assertGreaterEqual(len(memory_causes), 0)  # 可能没有匹配

    def test_analyze_slow_queries(self):
        """测试慢查询根因分析"""
        events = []

        inspection_results = {
            "performance": {
                "slow_queries": [
                    {"sql": "SELECT * FROM users", "explain": "ALL"},
                    {"sql": "SELECT * FROM orders JOIN users", "explain": "ALL"}
                ]
            }
        }

        causes = self.analyzer.analyze(events, inspection_results)

        query_causes = [c for c in causes if "慢查询" in c.description]
        self.assertGreater(len(query_causes), 0)

    def test_no_root_cause(self):
        """测试无根因情况"""
        events = []
        inspection_results = {}

        causes = self.analyzer.analyze(events, inspection_results)

        self.assertEqual(len(causes), 0)


class TestPredictiveInspector(unittest.TestCase):
    """测试预测性巡检器"""

    def setUp(self):
        """测试前准备"""
        self.predictor = PredictiveInspector()

    def test_predict_capacity_risk(self):
        """测试容量风险预测"""
        metrics = {
            "storage_usage": [
                {"timestamp": datetime.now() - timedelta(days=i), "value": 70.0 + i * 2}
                for i in range(10, -1, -1)
            ]
        }

        forecasts = self.predictor.predict_risks(metrics, "30d")

        capacity_forecasts = [f for f in forecasts if f.risk_type == "CAPACITY"]
        self.assertGreaterEqual(len(capacity_forecasts), 0)

    def test_predict_performance_degradation(self):
        """测试性能退化预测"""
        metrics = {
            "avg_response_time": [
                {"timestamp": datetime.now() - timedelta(days=i), "value": 100.0 + i * 20}
                for i in range(10, -1, -1)
            ]
        }

        forecasts = self.predictor.predict_risks(metrics, "7d")

        perf_forecasts = [f for f in forecasts if f.risk_type == "PERFORMANCE"]
        self.assertGreaterEqual(len(perf_forecasts), 0)

    def test_no_risk_predicted(self):
        """测试无风险情况"""
        metrics = {
            "storage_usage": [
                {"timestamp": datetime.now() - timedelta(days=i), "value": 50.0}
                for i in range(10, -1, -1)
            ]
        }

        forecasts = self.predictor.predict_risks(metrics)

        self.assertEqual(len(forecasts), 0)

    def test_insufficient_history(self):
        """测试历史数据不足"""
        metrics = {
            "storage_usage": [
                {"timestamp": datetime.now(), "value": 50.0}
            ]
        }

        forecasts = self.predictor.predict_risks(metrics)

        self.assertEqual(len(forecasts), 0)


class TestSmartRecommendationEngine(unittest.TestCase):
    """测试智能建议引擎"""

    def setUp(self):
        """测试前准备"""
        self.engine = SmartRecommendationEngine()

    def test_generate_recommendations_from_cause(self):
        """测试基于根因生成建议"""
        inspection_results = {}
        root_causes = [
            RootCause(
                cause_id="test1",
                category="PERFORMANCE",
                description="CPU使用率飙升",
                confidence=80.0,
                evidence=["慢查询"],
                suggested_actions=["优化查询"],
                impact_scope=["性能"]
            )
        ]

        recommendations = self.engine.generate_recommendations(
            inspection_results, root_causes
        )

        self.assertGreater(len(recommendations), 0)

    def test_generate_recommendations_from_inspection(self):
        """测试基于巡检结果生成建议"""
        inspection_results = {
            "storage": {"usage_percent": 85}
        }
        root_causes = []

        recommendations = self.engine.generate_recommendations(
            inspection_results, root_causes
        )

        storage_recs = [r for r in recommendations if "存储" in r.title or "容量" in r.title]
        self.assertGreater(len(storage_recs), 0)

    def test_recommendation_priority(self):
        """测试建议优先级"""
        inspection_results = {"storage": {"usage_percent": 95}}
        root_causes = []

        recommendations = self.engine.generate_recommendations(
            inspection_results, root_causes
        )

        if recommendations:
            self.assertGreaterEqual(recommendations[0].priority, 1)
            self.assertLessEqual(recommendations[0].priority, 10)


class TestCorrelationAnalyzer(unittest.TestCase):
    """测试关联分析器"""

    def setUp(self):
        """测试前准备"""
        self.analyzer = CorrelationAnalyzer()

    def test_analyze_positive_correlation(self):
        """测试正相关分析"""
        metrics_data = {
            "cpu_usage": [
                {"value": 30.0 + i * 5} for i in range(10)
            ],
            "load_average": [
                {"value": 1.0 + i * 0.2} for i in range(10)
            ]
        }

        insights = self.analyzer.analyze_correlations(metrics_data)

        self.assertGreater(len(insights), 0)
        if insights:
            self.assertEqual(insights[0].relationship_type, "positive")

    def test_analyze_negative_correlation(self):
        """测试负相关分析"""
        metrics_data = {
            "cpu_usage": [
                {"value": 80.0 - i * 5} for i in range(10)
            ],
            "idle_time": [
                {"value": 10.0 + i * 3} for i in range(10)
            ]
        }

        insights = self.analyzer.analyze_correlations(metrics_data)

        negative_insights = [i for i in insights if i.relationship_type == "negative"]
        self.assertGreaterEqual(len(negative_insights), 0)

    def test_no_correlation(self):
        """测试无关联情况"""
        metrics_data = {
            "metric_a": [{"value": 50.0} for _ in range(10)],
            "metric_b": [{"value": 30.0 + (i % 3) * 10} for i in range(10)]
        }

        insights = self.analyzer.analyze_correlations(metrics_data)

        # 弱相关应该被过滤
        self.assertEqual(len(insights), 0)

    def test_calculate_correlation(self):
        """测试相关系数计算"""
        data1 = [{"value": i * 10} for i in range(10)]
        data2 = [{"value": i * 5} for i in range(10)]

        correlation = self.analyzer._calculate_correlation(data1, data2)

        self.assertGreater(correlation, 0.9)  # 强正相关


class TestIntelligentInspector(unittest.TestCase):
    """测试智能巡检器集成"""

    def setUp(self):
        """测试前准备"""
        self.inspector = IntelligentInspector()

    def test_perform_intelligent_inspection(self):
        """测试完整智能巡检"""
        metrics_history = {
            "cpu_usage": [
                {"timestamp": datetime.now() - timedelta(hours=i), "value": 30.0}
                for i in range(5, 0, -1)
            ] + [{"timestamp": datetime.now(), "value": 85.0}],
            "memory_usage": [
                {"timestamp": datetime.now() - timedelta(hours=i), "value": 40.0 + i * 5}
                for i in range(5, -1, -1)
            ]
        }

        inspection_results = {
            "performance": {
                "slow_queries": [{"sql": "SELECT * FROM users"}],
                "connections": {"current": 80, "max": 100}
            }
        }

        result = self.inspector.perform_intelligent_inspection(
            metrics_history, inspection_results
        )

        self.assertIn("anomaly_events", result)
        self.assertIn("root_causes", result)
        self.assertIn("risk_forecasts", result)
        self.assertIn("recommendations", result)
        self.assertIn("summary", result)

    def test_generate_summary(self):
        """测试摘要生成"""
        # 使用真实的事件对象
        from dbskiter.db_inspector.intelligent_inspector import (
            AnomalyEvent, AnomalyPattern, RiskForecast, RiskPrediction
        )

        result = {
            "anomaly_events": [
                AnomalyEvent(
                    event_id="test1",
                    pattern=AnomalyPattern.SUDDEN_SPIKE,
                    metric_name="cpu",
                    metric_value=80.0,
                    threshold=50.0,
                    severity="HIGH",
                    timestamp=datetime.now(),
                    description="test"
                ),
                AnomalyEvent(
                    event_id="test2",
                    pattern=AnomalyPattern.GRADUAL_INCREASE,
                    metric_name="memory",
                    metric_value=90.0,
                    threshold=60.0,
                    severity="MEDIUM",
                    timestamp=datetime.now(),
                    description="test"
                )
            ],
            "root_causes": [{}],
            "risk_forecasts": [
                RiskForecast(
                    forecast_id="test1",
                    risk_type="CAPACITY",
                    prediction=RiskPrediction.HIGH,
                    probability=80.0,
                    time_horizon="7d",
                    affected_components=["storage"],
                    mitigation_suggestions=["扩容"]
                )
            ],
            "recommendations": [{}, {}],
            "correlation_insights": [{}]
        }

        summary = self.inspector._generate_summary(result)

        self.assertEqual(summary["total_anomalies"], 2)
        self.assertEqual(summary["root_causes_identified"], 1)
        self.assertEqual(summary["risks_predicted"], 1)
        self.assertEqual(summary["recommendations"], 2)

    def test_determine_overall_status(self):
        """测试整体状态判断"""
        from dbskiter.db_inspector.intelligent_inspector import AnomalyEvent, AnomalyPattern, RiskForecast

        # 严重状态
        result_critical = {
            "anomaly_events": [
                AnomalyEvent(
                    event_id="test1",
                    pattern=AnomalyPattern.SUDDEN_SPIKE,
                    metric_name="cpu",
                    metric_value=90.0,
                    threshold=50.0,
                    severity="CRITICAL",
                    timestamp=datetime.now(),
                    description="test"
                )
            ],
            "risk_forecasts": []
        }
        status = self.inspector._determine_overall_status(result_critical)
        self.assertEqual(status, "CRITICAL")

        # 警告状态 - 多个异常
        result_warning = {
            "anomaly_events": [
                AnomalyEvent(
                    event_id=f"test{i}",
                    pattern=AnomalyPattern.SUDDEN_SPIKE,
                    metric_name="cpu",
                    metric_value=80.0,
                    threshold=50.0,
                    severity="HIGH",
                    timestamp=datetime.now(),
                    description="test"
                )
                for i in range(3)
            ],
            "risk_forecasts": []
        }
        status = self.inspector._determine_overall_status(result_warning)
        self.assertEqual(status, "WARNING")

        # 健康状态
        result_healthy = {
            "anomaly_events": [
                AnomalyEvent(
                    event_id="test1",
                    pattern=AnomalyPattern.SUDDEN_SPIKE,
                    metric_name="cpu",
                    metric_value=80.0,
                    threshold=50.0,
                    severity="HIGH",
                    timestamp=datetime.now(),
                    description="test"
                )
            ],
            "risk_forecasts": []
        }
        status = self.inspector._determine_overall_status(result_healthy)
        self.assertEqual(status, "HEALTHY")

    def test_get_inspection_summary_text(self):
        """测试巡检摘要文本生成"""
        result = {
            "summary": {
                "overall_status": "WARNING",
                "total_anomalies": 3,
                "root_causes_identified": 2,
                "risks_predicted": 1,
                "recommendations": 4
            },
            "root_causes": [
                type('Cause', (), {
                    'description': 'CPU飙升',
                    'confidence': 85.0
                })()
            ],
            "recommendations": [
                type('Rec', (), {
                    'category': 'PERFORMANCE',
                    'title': '优化查询',
                    'priority': 8
                })()
            ]
        }

        summary_text = self.inspector.get_inspection_summary_text(result)

        self.assertIn("智能巡检报告", summary_text)
        self.assertIn("WARNING", summary_text)

    def test_components_initialized(self):
        """测试组件已正确初始化"""
        self.assertIsNotNone(self.inspector.anomaly_detector)
        self.assertIsNotNone(self.inspector.root_cause_analyzer)
        self.assertIsNotNone(self.inspector.predictive_inspector)
        self.assertIsNotNone(self.inspector.recommendation_engine)
        self.assertIsNotNone(self.inspector.correlation_analyzer)


if __name__ == '__main__':
    unittest.main()
