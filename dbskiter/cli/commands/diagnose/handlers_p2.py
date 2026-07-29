"""
P2 诊断处理器 - 低频场景

包含：report, table, performance-snapshot, bottleneck
"""

from typing import Any, Dict
from datetime import datetime

# 模块元数据：记录每个方法的子命令名
_GENERATE_REPORT = "_generate_report"
_DIAGNOSE_TABLE = "_diagnose_table"
_PERFORMANCE_SNAPSHOT = "_performance_snapshot"
_ANALYZE_BOTTLENECK = "_analyze_bottleneck"


class DiagnoseP2Mixin:
    """P2 低频诊断处理器"""

    # ==================== report - 综合报告 ====================

    def _generate_report(self, skill) -> int:
        """生成综合性能诊断报告（Markdown格式）

        功能定位：与 inspector report 区分
        - inspector report: 健康巡检（配置、安全、容量等静态检查）
        - diagnose report: 性能诊断（实时性能、慢查询、瓶颈等动态分析）
        """
        from .diagnose_report_generator import DiagnoseReportGenerator

        db_name = self.args.database or "unknown"
        db_type = self.connector.dialect if self.connector else "unknown"

        self.output.info("\n" + "=" * 60)
        self.output.info("生成综合性能诊断报告")
        self.output.info("=" * 60)

        self.output.info("\n[1] 性能快照...")
        snapshot_result = skill.take_performance_snapshot()

        self.output.info("[2] 瓶颈分析...")
        bottleneck_result = skill.analyze_performance_bottleneck()

        self.output.info("[3] 慢查询分析...")
        slow_queries_result = skill.get_realtime_connections()

        self.output.info("[4] 空间分析...")
        space_result = skill.analyze_space(top_n=10, min_size_mb=1, database=db_name)

        from dbskiter.db_diagnose.analyzers.sql_analyzer import SQLAnalyzer

        sql_analyzer = SQLAnalyzer(self.connector)

        generator = DiagnoseReportGenerator(sql_analyzer=sql_analyzer)
        report_content = generator.generate_report(
            db_name=db_name,
            db_type=db_type,
            snapshot_result=snapshot_result,
            bottleneck_result=bottleneck_result,
            space_result=space_result,
            slow_queries_result=slow_queries_result,
        )

        self.output.info("\n" + "=" * 60)
        self.output.info("诊断报告摘要")
        self.output.info("=" * 60)

        for issue in generator.issue_list:
            self.output.warning(f"  - {issue}")

        if generator.issues_found == 0:
            self.output.success("\n  数据库整体性能良好，未发现明显问题")
        else:
            self.output.info(f"\n  共发现 {generator.issues_found} 个性能问题，建议进一步分析")

        if hasattr(self.args, "output") and self.args.output:
            report_file = self.args.output
        else:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            report_file = f"db_performance_report_{db_name}_{timestamp}.md"

        try:
            with open(report_file, "w", encoding="utf-8") as f:
                f.write(report_content)
            self.output.info(f"\n[报告保存]")
            self.output.info(f"  性能诊断报告已保存到: {report_file}")
        except Exception as e:
            self.output.error(f"\n[错误] 保存报告失败: {e}")

        return 0

    def _generate_report_for_ai_mode(self, skill) -> Dict[str, Any]:
        """为AI模式生成综合性能诊断报告（返回字典格式）"""
        db_name = self.args.database or "unknown"
        db_type = self.connector.dialect if self.connector else "unknown"

        snapshot_result = skill.take_performance_snapshot()
        bottleneck_result = skill.analyze_performance_bottleneck()
        space_result = skill.analyze_space(top_n=10, min_size_mb=1, database=db_name)

        return {
            "success": True,
            "message": "综合性能诊断报告生成完成",
            "data": {
                "database": db_name,
                "database_type": db_type,
                "generated_at": datetime.now().isoformat(),
                "performance_snapshot": snapshot_result.get("data", {}),
                "bottleneck_analysis": bottleneck_result.get("data", {}),
                "space_analysis": space_result.get("data", {}),
            },
        }

    # ==================== table - 单表诊断 ====================

    def _diagnose_table(self, skill) -> int:
        """单表诊断"""
        result = skill.diagnose_table(self.args.table_name)

        if not result.get("success"):
            self.output.error(f"表诊断失败: {self._extract_error_message(result)}")
            return 1

        data = result.get("data", {})

        self.output.info("\n" + "=" * 60)
        self.output.info(f"表诊断: {self.args.table_name}")
        self.output.info("=" * 60)

        self.output.info(f"\n[基本信息]")
        self.output.info(f"  数据库类型: {data.get('dialect', 'N/A')}")

        stats = data.get("statistics", {})
        if stats:
            row_count = stats.get("row_count")
            size_mb = stats.get("size_mb")
            if row_count is not None:
                self.output.info(f"  行数: {row_count:,}")
            else:
                self.output.info(f"  行数: N/A")
            if size_mb is not None:
                self.output.info(f"  大小: {size_mb:.2f} MB")
            else:
                self.output.info(f"  大小: N/A")
        else:
            self.output.info(f"  行数: N/A")
            self.output.info(f"  大小: N/A")

        indexes = data.get("indexes", [])
        if indexes:
            self.output.info(f"\n[索引] 共 {len(indexes)} 个")
            for idx in indexes:
                self.output.info(f"  - {idx.get('name')}: {idx.get('columns')}")
        else:
            self.output.info(f"\n[索引] 无索引信息")

        issues = data.get("issues", [])
        if issues:
            self.output.info(f"\n[发现问题] 共 {len(issues)} 个")
            for issue in issues:
                self.output.warning(f"  - {issue}")

        suggestions = data.get("suggestions", [])
        if suggestions:
            self.output.info(f"\n[优化建议]")
            for s in suggestions:
                if isinstance(s, dict):
                    priority = s.get("priority", "")
                    suggestion_text = s.get("suggestion", s.get("description", ""))
                    if priority == "high":
                        self.output.warning(f"  - [高] {suggestion_text}")
                    elif priority == "medium":
                        self.output.info(f"  - [中] {suggestion_text}")
                    else:
                        self.output.info(f"  - [低] {suggestion_text}")
                else:
                    self.output.info(f"  - {s}")

        return 0

    # ==================== performance-snapshot - 性能快照 ====================

    def _performance_snapshot(self, skill) -> int:
        """性能快照"""
        result = skill.take_performance_snapshot()

        if not result.get("success"):
            self.output.error(f"性能快照采集失败: {self._extract_error_message(result)}")
            return 1

        data = result.get("data", {})
        snapshot = data.get("snapshot", {})
        summary = data.get("summary", {})

        self.output.info("\n" + "=" * 60)
        self.output.info("性能快照")
        self.output.info("=" * 60)

        self.output.info(f"\n[基本信息]")
        self.output.info(f"  采集时间: {snapshot.get('timestamp', 'N/A')}")
        self.output.info(f"  数据库类型: {self.connector.dialect if self.connector else 'N/A'}")
        self.output.info(f"  活跃会话: {snapshot.get('active_sessions', 0)}")
        self.output.info(f"  总会话: {snapshot.get('total_sessions', 0)}")
        self.output.info(f"  慢查询数: {len(snapshot.get('slow_queries', []))}")
        self.output.info(f"  指标数量: {len(snapshot.get('metrics', []))}")

        metrics = snapshot.get("metrics", [])
        if metrics:
            # 按类别分组
            categories = ["cpu", "memory", "io", "concurrency", "lock"]
            for cat in categories:
                cat_metrics = [m for m in metrics if m.get("category") == cat]
                if cat_metrics:
                    self.output.info(f"\n[{cat.upper()}]")
                    for m in cat_metrics:
                        self.output.info(f"  {m.get('name', 'N/A')}: {m.get('value', 0):.2f}{m.get('unit', '')}")

        slow_queries = snapshot.get("slow_queries", [])
        if slow_queries:
            self.output.info(f"\n[慢查询 TOP 5]")
            for i, q in enumerate(slow_queries[:5], 1):
                sql = q.get("sql_text", "N/A")[:50] if q.get("sql_text") else "N/A"
                self.output.info(f"  {i}. {sql}...")
                self.output.info(
                    f"     平均时间: {q.get('avg_time_ms', 0):.2f}ms, 执行次数: {q.get('execution_count', 0)}"
                )

        if self.args.output:
            import json

            try:
                with open(self.args.output, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                self.output.info(f"\n[保存] 快照已保存到: {self.args.output}")
            except Exception as e:
                self.output.error(f"保存失败: {e}")

        return 0

    # ==================== bottleneck - 瓶颈分析 ====================

    def _analyze_bottleneck(self, skill) -> int:
        """瓶颈分析"""
        result = skill.analyze_performance_bottleneck()

        if not result.get("success"):
            self.output.error(f"瓶颈分析失败: {self._extract_error_message(result)}")
            return 1

        data = result.get("data", {})
        bottlenecks = data.get("bottlenecks", [])
        summary = data.get("summary", {})
        recommendations = data.get("recommendations", [])

        self.output.info("\n" + "=" * 60)
        self.output.info("性能瓶颈分析")
        self.output.info("=" * 60)

        if summary:
            self.output.info(f"\n[统计]")
            self.output.info(f"  严重: {summary.get('critical', 0)} 个")
            self.output.info(f"  高: {summary.get('high', 0)} 个")
            self.output.info(f"  中: {summary.get('medium', 0)} 个")
            self.output.info(f"  低: {summary.get('low', 0)} 个")

        if bottlenecks:
            self.output.info(f"\n[瓶颈详情] TOP {min(len(bottlenecks), self.args.top)}")
            for i, b in enumerate(bottlenecks[: self.args.top], 1):
                category = b.get("category", "unknown")
                severity = b.get("severity", "unknown")
                description = b.get("description", "")
                suggestion = b.get("suggestion", "")
                metrics = b.get("metrics", [])

                severity_marker = {
                    "critical": ("[严重]", self.output.error),
                    "high": ("[高]", self.output.warning),
                    "medium": ("[中]", self.output.info),
                }.get(severity, ("[低]", self.output.info))

                severity_marker[1](f"\n  [{i}] {severity_marker[0]} {category}")

                if description:
                    self.output.info(f"      描述: {description}")
                elif suggestion:
                    self.output.info(f"      描述: {suggestion}")

                if metrics:
                    self.output.info(f"      指标:")
                    for m in metrics:
                        metric_name = m.get("name", "N/A")
                        metric_value = m.get("value", 0)
                        metric_unit = m.get("unit", "")
                        metric_severity = m.get("severity", "normal")
                        self.output.info(
                            f"        - {metric_name}: {metric_value:.2f}{metric_unit} [{metric_severity}]"
                        )
        else:
            self.output.info("\n[瓶颈详情] 未发现明显瓶颈")

        if recommendations:
            self.output.info(f"\n[优化建议]")
            for i, rec in enumerate(recommendations[:10], 1):
                self.output.info(f"  {i}. {rec}")

        return 0
