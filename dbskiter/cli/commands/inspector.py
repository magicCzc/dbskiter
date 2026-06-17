"""
cli/commands/inspector.py

数据库巡检命令 - 实例健康检查与报告生成
核心功能：执行巡检、生成报告、基线管理

用法:
    dbskiter inspector run              # 执行完整巡检
    dbskiter inspector report           # 生成巡检报告
    dbskiter inspector baseline         # 创建性能基线
"""

import json
from argparse import ArgumentParser

from .base import BaseCommand


class InspectorCommand(BaseCommand):
    """数据库巡检命令"""

    name = "inspector"
    description = "Database Inspector - 实例巡检与报告生成"
    help_text = "执行巡检、生成报告、基线管理"

    @classmethod
    def add_arguments(cls, parser: ArgumentParser) -> None:
        """添加巡检命令参数"""
        parser.epilog = """
示例:
  dbskiter --database=jump inspector run                       # 执行完整巡检
  dbskiter --database=jump inspector run --format=html -o report.html
  dbskiter --database=jump inspector report -o report.html     # 生成HTML报告
  dbskiter --database=jump inspector baseline --create         # 创建性能基线
  dbskiter --database=jump inspector intelligent               # 智能巡检
  dbskiter --database=jump inspector anomalies --metric=cpu_usage --hours=24
  dbskiter --database=jump inspector root-cause --issue="CPU飙升"
        """
        subparsers = parser.add_subparsers(dest="inspector_action", help="巡检操作")

        # run 子命令 - 执行巡检
        inspect_parser = subparsers.add_parser("run", help="执行完整巡检")
        inspect_parser.add_argument(
            "--format", "-f",
            choices=["text", "json", "html", "markdown"],
            default="text",
            help="报告格式"
        )
        inspect_parser.add_argument(
            "--output", "-o",
            help="输出文件路径"
        )
        inspect_parser.add_argument(
            "--type", "-t",
            choices=["configuration", "performance", "storage", "security", "capacity", "replication"],
            nargs="+",
            help="指定巡检类型"
        )

        # report 子命令 - 生成报告
        report_parser = subparsers.add_parser("report", help="生成巡检报告")
        report_parser.add_argument(
            "--format", "-f",
            choices=["html", "markdown", "json"],
            default="html",
            help="报告格式"
        )
        report_parser.add_argument(
            "--output", "-o",
            required=True,
            help="输出文件路径"
        )

        # baseline 子命令 - 基线管理
        baseline_parser = subparsers.add_parser("baseline", help="性能基线管理")
        baseline_parser.add_argument(
            "--create",
            action="store_true",
            help="创建新基线"
        )
        baseline_parser.add_argument(
            "--compare",
            action="store_true",
            help="与基线对比"
        )

        # intelligent 子命令 - 智能巡检
        intelligent_parser = subparsers.add_parser("intelligent", help="智能巡检（异常检测+根因分析+建议）")
        intelligent_parser.add_argument(
            "--metrics-file",
            help="指标历史数据文件（JSON格式）"
        )

        # anomalies 子命令 - 异常检测
        anomalies_parser = subparsers.add_parser("anomalies", help="异常检测")
        anomalies_parser.add_argument(
            "--metric",
            required=True,
            help="指标名称（如cpu_usage, memory_usage）"
        )
        anomalies_parser.add_argument(
            "--hours",
            type=int,
            default=24,
            help="检测最近多少小时的数据"
        )

        # root-cause 子命令 - 根因分析
        rootcause_parser = subparsers.add_parser("root-cause", help="根因分析")
        rootcause_parser.add_argument(
            "--issue",
            required=True,
            help="问题描述（如'CPU使用率飙升'）"
        )

        # risks 子命令 - 风险预测
        risks_parser = subparsers.add_parser("risks", help="风险预测")
        risks_parser.add_argument(
            "--days",
            type=int,
            default=7,
            help="预测天数（默认7天）"
        )

    def execute(self) -> int:
        """执行巡检命令"""
        from dbskiter.db_inspector.skill import InspectorSkill

        try:
            self.require_connector()
        except Exception as e:
            self.output.error(str(e))
            return 1

        try:
            skill = InspectorSkill(self.connector)

            action = getattr(self.args, 'inspector_action', None)

            if self.output_mode != "rule":
                method_map = {
                    "run": lambda: skill.inspect(None),
                    "intelligent": lambda: skill.intelligent_inspect(metrics_history={}),
                    "anomalies": lambda: skill.detect_anomalies(
                        metrics={},
                    ),
                    "root-cause": lambda: skill.analyze_root_causes(
                        anomaly_events=[],
                        inspection_results={},
                    ),
                    "risks": lambda: skill.predict_risks(
                        metrics_history={},
                        time_horizon=f"{getattr(self.args, 'days', 7)}d",
                    ),
                }
                scenario_map = {
                    "run": "inspection",
                    "intelligent": "intelligent_inspection",
                    "anomalies": "anomaly_detection",
                    "root-cause": "root_cause",
                    "risks": "risk_prediction",
                }
                if action in method_map:
                    return self._execute_ai_mode(skill, action, method_map, scenario_map)

            if action == "run":
                return self._run_inspection(skill)
            elif action == "report":
                return self._generate_report(skill)
            elif action == "baseline":
                return self._manage_baseline(skill)
            elif action == "intelligent":
                return self._intelligent_inspect(skill)
            elif action == "anomalies":
                return self._detect_anomalies(skill)
            elif action == "root-cause":
                return self._analyze_root_cause(skill)
            elif action == "risks":
                return self._predict_risks(skill)
            else:
                self.output.error("请指定巡检操作: run, report, baseline, intelligent, anomalies, root-cause, risks")
                return 1

        except Exception as e:
            self.output.error(f"巡检失败: {e}")
            return 1
        finally:
            if 'skill' in locals():
                skill.close()

    def _run_inspection(self, skill) -> int:
        """执行巡检"""
        from dbskiter.db_inspector.models import InspectionType

        # 确定巡检类型
        inspection_types = None
        type_args = getattr(self.args, 'type', None)
        if type_args:
            type_map = {
                "configuration": InspectionType.CONFIGURATION,
                "performance": InspectionType.PERFORMANCE,
                "storage": InspectionType.STORAGE,
                "security": InspectionType.SECURITY,
                "capacity": InspectionType.CAPACITY,
                "replication": InspectionType.REPLICATION
            }
            inspection_types = [type_map[t] for t in type_args]

        # 执行巡检 - 返回的是标准响应格式字典
        response = skill.inspect(inspection_types)

        if not response.get('success'):
            self.output.error(f"巡检失败: {response.get('message', '未知错误')}")
            return 1

        # 获取报告数据
        report_data = response.get('data', {})

        output_format = getattr(self.args, 'format', 'text')
        output_path = getattr(self.args, 'output', None)

        # 生成输出内容
        if output_format == "json":
            output = report_data
        elif output_format == "html":
            output = skill.generate_html_report_from_data(report_data)
        elif output_format == "markdown":
            output = skill.generate_markdown_report_from_data(report_data)
        else:
            # 文本格式输出摘要
            output = self._generate_text_summary(report_data)

        # 保存到文件或输出
        if output_path:
            with open(output_path, 'w', encoding='utf-8') as f:
                if isinstance(output, dict):
                    json.dump(output, f, ensure_ascii=False, indent=2)
                else:
                    f.write(output)
            self.output.success(f"报告已保存: {output_path}")
        else:
            if isinstance(output, dict):
                self.output.print(json.dumps(output, ensure_ascii=False, indent=2))
            else:
                self.output.print(output)

        # 显示摘要
        stats = report_data.get('statistics', {})
        self.output.print(f"\n{'='*60}")
        self.output.print("巡检摘要")
        self.output.print(f"{'='*60}")
        self.output.print(f"健康评分: {report_data.get('health_score', 0)}")
        self.output.print(f"严重问题: {stats.get('critical_count', 0)}")
        self.output.print(f"高风险问题: {stats.get('high_count', 0)}")

        return 0

    def _generate_text_summary(self, report_data: dict) -> str:
        """生成文本格式的巡检摘要"""
        # 格式化数据库类型显示
        db_type = report_data.get('database_type', 'unknown')
        if 'mysql' in db_type.lower():
            db_type_display = 'MySQL'
        elif 'oracle' in db_type.lower():
            db_type_display = 'Oracle'
        elif 'postgresql' in db_type.lower():
            db_type_display = 'PostgreSQL'
        else:
            db_type_display = db_type

        lines = [
            "=" * 60,
            "数据库巡检报告",
            "=" * 60,
            f"实例标识: {report_data.get('instance_name', 'unknown')}",
            f"数据库类型: {db_type_display}",
            f"数据库版本: {report_data.get('database_version', '')}",
            f"巡检时间: {report_data.get('inspection_time', 'unknown')}",
            f"巡检耗时: {report_data.get('duration_seconds', 0)}秒",
            "",
            "巡检统计:",
        ]

        stats = report_data.get('statistics', {})
        lines.extend([
            f"  总巡检项: {stats.get('total_items', 0)}",
            f"  通过: {stats.get('pass_count', 0)}",
            f"  警告: {stats.get('warning_count', 0)}",
            f"  失败: {stats.get('fail_count', 0)}",
            f"  严重风险: {stats.get('critical_count', 0)}",
            f"  高风险: {stats.get('high_count', 0)}",
            f"  中风险: {stats.get('medium_count', 0)}",
            f"  低风险: {stats.get('low_count', 0)}",
            "",
            f"健康评分: {report_data.get('health_score', 0)}/100",
            "",
            "摘要:",
            report_data.get('summary', '无'),
            "",
            "=" * 60,
            "详细巡检项",
            "=" * 60,
        ])

        # 添加详细巡检项
        items = report_data.get('items', [])
        
        # 类别映射
        category_map = {
            'configuration': '配置',
            'performance': '性能',
            'storage': '存储',
            'security': '安全',
            'capacity': '容量',
            'replication': '复制',
            'backup': '备份',
            'other': '其他'
        }
        
        if items:
            for i, item in enumerate(items, 1):
                status = item.get('status', 'unknown')
                status_display = {
                    'pass': '通过',
                    'warning': '警告',
                    'fail': '失败'
                }.get(status, status)
                
                # 获取类别（type字段对应inspection_type）
                item_type = item.get('type', 'other')
                category = category_map.get(item_type, '其他')
                
                # 获取名称，确保不为空
                item_name = item.get('name', '未命名')
                if not item_name:
                    item_name = '未命名'
                
                lines.append(f"[{i}] {item_name}")
                lines.append(f"    类别: {category}")
                lines.append(f"    状态: {status_display}")
                lines.append(f"    描述: {item.get('description', '')}")
                
                if item.get('actual_value'):
                    lines.append(f"    当前值: {item.get('actual_value')}")
                
                if item.get('message'):
                    lines.append(f"    信息: {item.get('message')}")
                
                if item.get('suggestion'):
                    lines.append(f"    建议: {item.get('suggestion')}")
        else:
            lines.append("暂无详细巡检项数据")

        return "\n".join(lines)

    def _generate_report(self, skill) -> int:
        """生成报告"""
        # 先执行巡检
        response = skill.inspect()

        if not response.get('success'):
            self.output.error(f"巡检失败: {response.get('message', '未知错误')}")
            return 1

        report_data = response.get('data', {})
        output_format = getattr(self.args, 'format', 'html')
        output_path = self.args.output

        # 生成指定格式报告
        if output_format == "html":
            content = skill.generate_html_report_from_data(report_data)
        elif output_format == "markdown":
            content = skill.generate_markdown_report_from_data(report_data)
        else:
            content = json.dumps(report_data, ensure_ascii=False, indent=2)

        # 保存文件
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(content)

        self.output.success(f"报告已生成: {output_path}")
        return 0

    def _manage_baseline(self, skill) -> int:
        """管理基线"""
        import json

        create_baseline = getattr(self.args, 'create', False)
        compare_baseline = getattr(self.args, 'compare', False)

        if create_baseline:
            response = skill.create_baseline()
            if not response.get('success'):
                self.output.error(f"基线创建失败: {response.get('message', '未知错误')}")
                return 1

            baseline_data = response.get('data', {})
            self.output.success(f"性能基线已创建: {baseline_data.get('baseline_id', 'unknown')}")
            self.output.print(f"创建时间: {baseline_data.get('created_at', 'unknown')}")
            return 0
        elif compare_baseline:
            response = skill.inspect()
            if not response.get('success'):
                self.output.error(f"巡检失败: {response.get('message', '未知错误')}")
                return 1

            # 基线对比功能需要 InspectionReport 对象
            self.output.info("基线对比功能需要重新实现")
            return 0
        else:
            self.output.error("请指定--create或--compare")
            return 1

    def _intelligent_inspect(self, skill) -> int:
        """智能巡检"""
        import json

        # 检查是否有智能巡检功能
        if not hasattr(skill, 'intelligent_inspect'):
            self.output.error("智能巡检功能不可用")
            return 1

        # 读取指标数据
        metrics_history = {}
        if self.args.metrics_file:
            try:
                with open(self.args.metrics_file, 'r', encoding='utf-8') as f:
                    metrics_history = json.load(f)
            except Exception as e:
                self.output.error(f"读取指标文件失败: {e}")
                return 1

        result = skill.intelligent_inspect(metrics_history=metrics_history)

        if not result.get('success', False):
            self.output.error(f"智能巡检失败: {result.get('message', '未知错误')}")
            return 1

        data = result.get('data', {})
        anomalies = data.get('anomalies', [])
        root_causes = data.get('root_causes', [])
        risks = data.get('risks', [])
        recommendations = data.get('recommendations', [])

        summary = f"发现{len(anomalies)}个异常, {len(root_causes)}个根因, {len(risks)}个风险, {len(recommendations)}条建议"

        self.output.print(f"\n{'='*60}")
        self.output.print(f"摘要: {summary}")
        self.output.print(f"{'='*60}")

        # 异常检测
        if anomalies:
            self.output.print(f"\n[异常检测] 发现{len(anomalies)}个异常:")
            for anomaly in anomalies[:10]:
                metric = anomaly.get('metric', 'unknown')
                severity = anomaly.get('severity', 'unknown')
                description = anomaly.get('description', '')

                if severity == 'critical':
                    self.output.error(f"  [严重] {metric}: {description}")
                elif severity == 'warning':
                    self.output.warning(f"  [警告] {metric}: {description}")
                else:
                    self.output.print(f"  [信息] {metric}: {description}")

        # 根因分析
        if root_causes:
            self.output.print(f"\n[根因分析] 发现{len(root_causes)}个根因:")
            for cause in root_causes[:10]:
                category = cause.get('category', 'unknown')
                confidence = cause.get('confidence', 0)
                description = cause.get('description', '')
                self.output.print(f"  [{category}] 置信度{confidence*100:.0f}%: {description}")

        # 风险预测
        if risks:
            self.output.print(f"\n[风险预测] 发现{len(risks)}个风险:")
            for risk in risks[:10]:
                risk_type = risk.get('type', 'unknown')
                probability = risk.get('probability', 0)
                impact = risk.get('impact', 'unknown')
                self.output.warning(f"  [{risk_type}] 概率{probability*100:.0f}%, 影响:{impact}")

        # 智能建议
        if recommendations:
            self.output.print(f"\n[智能建议] {len(recommendations)}条建议:")
            for i, rec in enumerate(recommendations[:10], 1):
                priority = rec.get('priority', 'medium')
                description = rec.get('description', '')
                if priority == 'high':
                    self.output.warning(f"  {i}. [高优先级] {description}")
                else:
                    self.output.print(f"  {i}. {description}")

        return 0

    def _detect_anomalies(self, skill) -> int:
        """异常检测"""
        # 检查是否有异常检测功能
        if not hasattr(skill, 'detect_anomalies'):
            self.output.error("异常检测功能不可用")
            return 1

        # 获取历史数据
        result = skill.detect_anomalies(
            metric_type=self.args.metric,
            hours=self.args.hours
        )

        if not result.get('success', False):
            self.output.error(f"异常检测失败: {result.get('message', '未知错误')}")
            return 1

        data = result.get('data', {})
        anomalies = data.get('anomalies', [])
        summary_stats = data.get('summary', {})

        self.output.print(f"\n{'='*60}")
        self.output.print(f"摘要: 在{self.args.metric}中发现{len(anomalies)}个异常")
        self.output.print(f"{'='*60}")

        # 统计信息
        if summary_stats:
            self.output.print(f"\n统计信息:")
            self.output.print(f"  总数据点: {summary_stats.get('total_points', 0)}")
            self.output.print(f"  异常数量: {summary_stats.get('anomaly_count', 0)}")
            self.output.print(f"  异常比例: {summary_stats.get('anomaly_ratio', 0)*100:.1f}%")

        # 异常详情
        if anomalies:
            self.output.print(f"\n异常详情:")
            for anomaly in anomalies[:20]:
                timestamp = anomaly.get('timestamp', 'unknown')
                value = anomaly.get('value', 0)
                expected = anomaly.get('expected_range', [0, 0])
                anomaly_type = anomaly.get('type', 'unknown')
                severity = anomaly.get('severity', 'unknown')

                if severity == 'critical':
                    self.output.error(f"  [{severity}] {timestamp}: {value:.2f} (期望: {expected[0]:.2f}-{expected[1]:.2f}) [{anomaly_type}]")
                elif severity == 'warning':
                    self.output.warning(f"  [{severity}] {timestamp}: {value:.2f} (期望: {expected[0]:.2f}-{expected[1]:.2f}) [{anomaly_type}]")
                else:
                    self.output.print(f"  [{severity}] {timestamp}: {value:.2f} (期望: {expected[0]:.2f}-{expected[1]:.2f}) [{anomaly_type}]")

        return 0

    def _analyze_root_cause(self, skill) -> int:
        """根因分析"""
        # 检查是否有根因分析功能
        if not hasattr(skill, 'analyze_root_causes'):
            self.output.error("根因分析功能不可用")
            return 1

        # 构建异常事件
        anomalies = [{
            'metric': self.args.issue,
            'timestamp': datetime.now().isoformat(),
            'severity': 'critical'
        }]

        result = skill.analyze_root_causes(anomalies=anomalies)

        if not result.get('success', False):
            self.output.error(f"根因分析失败: {result.get('message', '未知错误')}")
            return 1

        data = result.get('data', {})
        root_causes = data.get('root_causes', [])

        self.output.print(f"\n{'='*60}")
        self.output.print(f"摘要: 发现问题'{self.args.issue}'的{len(root_causes)}个可能根因")
        self.output.print(f"{'='*60}")

        if root_causes:
            self.output.print(f"\n根因分析结果:")
            for i, cause in enumerate(root_causes[:10], 1):
                category = cause.get('category', 'unknown')
                confidence = cause.get('confidence', 0)
                description = cause.get('description', '')
                evidence = cause.get('evidence', [])
                recommendations = cause.get('recommendations', [])

                self.output.print(f"\n{i}. [{category}] 置信度: {confidence*100:.0f}%")
                self.output.print(f"   描述: {description}")

                if evidence:
                    self.output.print(f"   证据:")
                    for e in evidence[:3]:
                        self.output.print(f"     - {e}")

                if recommendations:
                    self.output.print(f"   建议:")
                    for rec in recommendations[:3]:
                        self.output.print(f"     - {rec}")
        else:
            self.output.print(f"\n未找到明显的根因，建议进行更详细的检查")

        return 0

    def _predict_risks(self, skill) -> int:
        """风险预测"""
        # 检查是否有风险预测功能
        if not hasattr(skill, 'predict_risks'):
            self.output.error("风险预测功能不可用")
            return 1

        result = skill.predict_risks(time_horizon_days=self.args.days)

        if not result.get('success', False):
            self.output.error(f"风险预测失败: {result.get('message', '未知错误')}")
            return 1

        data = result.get('data', {})
        risks = data.get('risks', [])
        summary = data.get('summary', {})

        self.output.print(f"\n{'='*60}")
        self.output.print(f"摘要: 未来{self.args.days}天内预测到{len(risks)}个风险")
        self.output.print(f"{'='*60}")

        # 风险统计
        if summary:
            high_risks = summary.get('high_risk_count', 0)
            medium_risks = summary.get('medium_risk_count', 0)
            low_risks = summary.get('low_risk_count', 0)
            self.output.print(f"\n风险统计: 高:{high_risks} 中:{medium_risks} 低:{low_risks}")

        # 风险详情
        if risks:
            self.output.print(f"\n风险详情:")
            for risk in risks[:15]:
                risk_type = risk.get('type', 'unknown')
                probability = risk.get('probability', 0)
                impact = risk.get('impact', 'unknown')
                time_to_occurrence = risk.get('time_to_occurrence', 'unknown')
                description = risk.get('description', '')
                mitigation = risk.get('mitigation', '')

                # 根据概率确定严重程度
                if probability >= 0.7:
                    self.output.error(f"\n  [高风险] {risk_type}")
                elif probability >= 0.4:
                    self.output.warning(f"\n  [中风险] {risk_type}")
                else:
                    self.output.print(f"\n  [低风险] {risk_type}")

                self.output.print(f"    概率: {probability*100:.0f}%")
                self.output.print(f"    影响: {impact}")
                self.output.print(f"    预计时间: {time_to_occurrence}")
                self.output.print(f"    描述: {description}")
                if mitigation:
                    self.output.print(f"    缓解措施: {mitigation}")

        return 0
