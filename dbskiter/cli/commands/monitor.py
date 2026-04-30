"""
cli/commands/monitor.py

数据库监控命令 - 简化版
核心功能：健康检查、异常检测、容量预测、指标采集、历史查询
"""

from argparse import ArgumentParser
from typing import Dict, Any, Optional

from .base import BaseCommand


class MonitorCommand(BaseCommand):
    """数据库监控命令"""
    
    name = "monitor"
    description = "Database Monitor - 智能监控与预测"
    help_text = "健康检查、异常检测、容量预测"
    
    @classmethod
    def add_arguments(cls, parser: ArgumentParser) -> None:
        """添加监控命令参数"""
        subparsers = parser.add_subparsers(dest="monitor_action", help="监控操作")
        
        # ==================== 核心命令（只保留5个） ====================
        
        # health 子命令
        health_parser = subparsers.add_parser("health", help="健康评估")
        
        # health-all 子命令 - 批量检查所有数据库
        health_all_parser = subparsers.add_parser("health-all", help="批量检查所有数据库健康状态")
        
        # anomalies 子命令
        anomalies_parser = subparsers.add_parser("anomalies", help="异常检测")
        anomalies_parser.add_argument("--hours", type=int, default=1, help="检测时间范围（小时）")
        
        # capacity 子命令
        capacity_parser = subparsers.add_parser("capacity", help="容量预测")
        capacity_parser.add_argument("--resource", choices=["disk", "memory", "connections"],
                                    default="disk", help="资源类型")
        capacity_parser.add_argument("--days", type=int, default=30, help="预测天数")
        capacity_parser.add_argument("--source", choices=["auto", "prometheus", "zabbix", "internal"],
                                    default="auto", help="数据来源")
        
        # collect 子命令
        collect_parser = subparsers.add_parser("collect", help="采集指标")
        collect_parser.add_argument("--metrics", help="指定指标（逗号分隔）")
        collect_parser.add_argument("--source", choices=["auto", "prometheus", "zabbix", "internal"],
                                   default="auto", help="数据来源")
        
        # history 子命令
        history_parser = subparsers.add_parser("history", help="查看指标历史")
        history_parser.add_argument("metric", help="指标名称")
        history_parser.add_argument("--hours", type=int, default=24, help="查询小时数")
        
        # capacity-advanced 子命令 - 高级容量预测
        capacity_adv_parser = subparsers.add_parser("capacity-advanced", help="高级容量预测（多算法）")
        capacity_adv_parser.add_argument("--resource", choices=["disk", "memory", "connections", "cpu", "qps"],
                                         default="disk", help="资源类型")
        capacity_adv_parser.add_argument("--days", type=int, default=30, help="预测天数")
        
        # trend 子命令 - 趋势分析
        trend_parser = subparsers.add_parser("trend", help="趋势分析")
        trend_parser.add_argument("--metric", required=True, help="指标名称")
        trend_parser.add_argument("--days", type=int, default=7, help="分析天数")
        
        # compare 子命令 - 基线对比
        compare_parser = subparsers.add_parser("compare", help="基线对比")
        compare_parser.add_argument("--metric", required=True, help="指标名称")
        compare_parser.add_argument("--value", type=float, required=True, help="当前值")
        compare_parser.add_argument("--baseline", required=True, help="基线日期(YYYY-MM-DD)")
    
    def execute(self) -> int:
        """执行监控命令"""
        from dbskiter.db_monitor.skill import MonitorSkill
        from dbskiter.cli.config import Config

        skill = None
        try:
            db_name = getattr(self.args, 'database', None)
            configs = self._load_all_configs()
            skill = self._create_skill_smart(
                db_name=db_name,
                configs=configs
            )

            if not skill:
                self.output.error("无法找到可用的数据源。请检查：\n"
                                 "1. .env 文件中的数据库配置\n"
                                 "2. Zabbix/Prometheus 配置（如使用外部监控）")
                return 1

            action = getattr(self.args, 'monitor_action', None)

            if self.output_mode != "rule":
                method_map = {
                    "health": lambda: skill.assess_health(),
                    "anomalies": lambda: skill.detect_anomalies(),
                    "capacity": lambda: skill.predict_capacity(
                        metric=getattr(self.args, 'resource', 'disk'),
                    ),
                    "collect": lambda: skill.collect_metrics(),
                    "history": lambda: skill.get_metric_history(
                        metric_type=getattr(self.args, 'metric', ''),
                        hours=getattr(self.args, 'hours', 24),
                    ),
                    "capacity-advanced": lambda: skill.predict_capacity_advanced(
                        metric=getattr(self.args, 'resource', 'disk'),
                    ),
                    "trend": lambda: skill.analyze_trend(
                        metric=getattr(self.args, 'metric', 'cpu_usage'),
                    ),
                    "compare": lambda: skill.compare_with_baseline(
                        metric=getattr(self.args, 'metric', ''),
                        current_value=getattr(self.args, 'value', 0),
                        baseline_date=getattr(self.args, 'baseline', None),
                    ),
                }
                scenario_map = {
                    "health": "monitor",
                    "anomalies": "anomaly_detection",
                    "capacity": "capacity",
                    "collect": "metrics_collection",
                    "history": "metrics_history",
                    "capacity-advanced": "capacity_advanced",
                    "trend": "trend_analysis",
                    "compare": "baseline_comparison",
                }
                if action in method_map:
                    return self._execute_ai_mode(skill, action, method_map, scenario_map)

            if action == "health":
                return self._assess_health(skill)
            elif action == "health-all":
                return self._assess_health_all()
            elif action == "anomalies":
                return self._detect_anomalies(skill)
            elif action == "capacity":
                return self._predict_capacity(skill)
            elif action == "collect":
                return self._collect_metrics(skill)
            elif action == "history":
                return self._show_history(skill)
            elif action == "capacity-advanced":
                return self._predict_capacity_advanced(skill)
            elif action == "trend":
                return self._analyze_trend(skill)
            elif action == "compare":
                return self._compare_baseline(skill)
            else:
                self.output.error("请指定监控操作: health, health-all, anomalies, capacity, collect, history, capacity-advanced, trend, compare")
                return 1
                
        except Exception as e:
            self.output.error(f"监控失败: {e}")
            return 1
        finally:
            if skill:
                skill.close()
    
    def _assess_health(self, skill) -> int:
        """健康评估"""
        result = skill.assess_health()

        # 获取实际数据（标准响应格式）
        health = result.get('data', {})

        score = health.get('score', 0)
        status = health.get('status', 'unknown')
        issues = health.get('issues', [])

        summary = f"健康评分{score}分，状态{status}"

        self.output.info(f"\n{'='*60}")
        self.output.info(f"摘要: {summary}")
        self.output.info(f"{'='*60}")

        self.output.info(f"数据库健康评估 - {health.get('timestamp', '')}")

        # 总体评分
        if score >= 90:
            self.output.success(f"\n总体评分: {score}/100 - 状态良好")
        elif score >= 70:
            self.output.warning(f"\n总体评分: {score}/100 - 需要关注")
        else:
            self.output.error(f"\n总体评分: {score}/100 - 严重问题")

        # 显示问题列表
        if issues:
            self.output.info(f"\n发现问题:")
            for issue in issues:
                self.output.warning(f"  - {issue}")

        # 关键指标
        key_metrics = health.get('metrics_summary', {})
        if key_metrics:
            self.output.info(f"\n关键指标:")
            for metric, value in key_metrics.items():
                self.output.info(f"  {metric}: {value}")

        return 0

    def _assess_health_all(self) -> int:
        """
        批量检查所有数据库的健康状态
        
        遍历所有配置的数据库实例，逐个检查健康状态
        
        返回:
            int: 退出码，0表示成功，1表示有错误
        """
        from dbskiter.db_monitor.skill import MonitorSkill
        from dbskiter.cli.config import MultiDBConfig
        
        multi_config = MultiDBConfig()
        configs = multi_config.load_all_configs()
        
        if not configs:
            self.output.error("未找到任何数据库配置")
            return 1
        
        self.output.info("\n" + "=" * 70)
        self.output.info("批量数据库健康检查")
        self.output.info("=" * 70)
        self.output.info(f"共发现 {len(configs)} 个数据库实例\n")
        
        results = []
        total_score = 0
        healthy_count = 0
        warning_count = 0
        critical_count = 0
        
        for instance_name, config in configs.items():
            self.output.info(f"\n{'-' * 70}")
            self.output.info(f"[{instance_name}] {config.host}:{config.port}/{config.database}")
            self.output.info(f"{'-' * 70}")
            
            skill = None
            try:
                # 创建连接器
                connector = self._create_connector_from_config(config)
                skill = MonitorSkill(connector)
                
                # 执行健康检查
                result = skill.assess_health()
                health = result.get('data', {})
                
                score = health.get('score', 0)
                status = health.get('status', 'unknown')
                issues = health.get('issues', [])
                
                total_score += score
                
                # 统计状态
                if score >= 90:
                    healthy_count += 1
                    self.output.success(f"  评分: {score}/100 - 状态良好")
                elif score >= 70:
                    warning_count += 1
                    self.output.warning(f"  评分: {score}/100 - 需要关注")
                else:
                    critical_count += 1
                    self.output.error(f"  评分: {score}/100 - 严重问题")
                
                # 显示问题列表
                if issues:
                    self.output.info(f"  发现问题:")
                    for issue in issues[:3]:  # 只显示前3个问题
                        self.output.warning(f"    - {issue}")
                    if len(issues) > 3:
                        self.output.info(f"    ... 还有 {len(issues) - 3} 个问题")
                
                # 显示关键指标
                key_metrics = health.get('metrics_summary', {})
                if key_metrics:
                    self.output.info(f"  关键指标:")
                    for metric, value in list(key_metrics.items())[:5]:  # 只显示前5个
                        self.output.info(f"    {metric}: {value}")
                
                results.append({
                    'instance': instance_name,
                    'database': config.database,
                    'host': config.host,
                    'score': score,
                    'status': status,
                    'success': True
                })
                
            except Exception as e:
                self.output.error(f"  检查失败: {e}")
                results.append({
                    'instance': instance_name,
                    'database': config.database,
                    'host': config.host,
                    'score': 0,
                    'status': 'error',
                    'success': False,
                    'error': str(e)
                })
                critical_count += 1
            finally:
                if skill:
                    skill.close()
        
        # 汇总报告
        self.output.info(f"\n{'=' * 70}")
        self.output.info("汇总报告")
        self.output.info(f"{'=' * 70}")
        
        avg_score = total_score / len(configs) if configs else 0
        self.output.info(f"\n总体情况:")
        self.output.info(f"  数据库总数: {len(configs)}")
        self.output.info(f"  平均评分: {avg_score:.1f}/100")
        self.output.info(f"  状态良好: {healthy_count}")
        self.output.info(f"  需要关注: {warning_count}")
        self.output.info(f"  严重问题: {critical_count}")
        
        # 显示有问题的数据库
        problem_dbs = [r for r in results if r['score'] < 70 or not r['success']]
        if problem_dbs:
            self.output.info(f"\n需要关注的数据库:")
            for db in problem_dbs:
                if db['success']:
                    self.output.warning(f"  - [{db['instance']}] {db['database']} ({db['host']}): {db['score']}分")
                else:
                    self.output.error(f"  - [{db['instance']}] {db['database']} ({db['host']}): 检查失败")
        
        self.output.info(f"\n{'=' * 70}")
        
        # 返回码：如果有严重问题返回1，否则返回0
        return 1 if critical_count > 0 else 0

    def _predict_capacity_advanced(self, skill) -> int:
        """高级容量预测"""
        # 检查是否有高级预测功能
        if not hasattr(skill, 'predict_capacity_advanced'):
            self.output.error("高级容量预测功能不可用，请确保advanced_predictor模块已安装")
            return 1
        
        result = skill.predict_capacity_advanced(
            metric=self.args.resource,
            days=self.args.days
        )
        
        if not result.get('success', False):
            self.output.error(f"高级容量预测失败: {result.get('message', '未知错误')}")
            return 1
        
        data = result.get('data', {})
        algorithm = data.get('algorithm', 'unknown')
        confidence = data.get('confidence', 0.0)
        predictions = data.get('predictions', {})
        days_to_threshold = data.get('days_to_threshold', 0)
        
        summary = f"使用{algorithm}算法，置信度{confidence*100:.1f}%"
        
        self.output.info(f"\n{'='*60}")
        self.output.info(f"摘要: {summary}")
        self.output.info(f"{'='*60}")
        
        self.output.info(f"\n预测算法: {algorithm}")
        self.output.info(f"预测置信度: {confidence*100:.1f}%")
        
        if predictions:
            self.output.info(f"\n预测结果:")
            for period, value in predictions.items():
                self.output.info(f"  {period}: {value:.2f}%")
        
        if days_to_threshold >= 999:
            self.output.info(f"\n容量状态: 充足（增长缓慢或稳定）")
        else:
            self.output.info(f"\n预计到达阈值: {days_to_threshold}天")
        
        if data.get('recommendation'):
            self.output.info(f"\n建议: {data['recommendation']}")
        
        return 0

    def _analyze_trend(self, skill) -> int:
        """趋势分析"""
        # 检查是否有趋势分析功能
        if not hasattr(skill, 'analyze_trend'):
            self.output.error("趋势分析功能不可用，请确保trend_analyzer模块已安装")
            return 1
        
        result = skill.analyze_trend(
            metric=self.args.metric,
            days=self.args.days
        )
        
        if not result.get('success', False):
            self.output.error(f"趋势分析失败: {result.get('message', '未知错误')}")
            return 1
        
        data = result.get('data', {})
        trend_direction = data.get('trend_direction', 'unknown')
        current_value = data.get('current_value', 0)
        historical_avg = data.get('historical_avg', 0)
        change_percent = data.get('change_percent', 0)
        
        # 根据趋势方向设置颜色
        if trend_direction == 'improving':
            trend_text = "改善"
            self.output.info(f"\n趋势方向: {trend_text} (向好)")
        elif trend_direction == 'degrading':
            trend_text = "恶化"
            self.output.warning(f"\n趋势方向: {trend_text} (需关注)")
        else:
            trend_text = "稳定"
            self.output.info(f"\n趋势方向: {trend_text}")
        
        self.output.info(f"当前值: {current_value:.2f}")
        self.output.info(f"历史均值: {historical_avg:.2f}")
        
        if change_percent > 0:
            self.output.info(f"变化幅度: +{change_percent:.1f}%")
        else:
            self.output.info(f"变化幅度: {change_percent:.1f}%")
        
        if data.get('recommendation'):
            if trend_direction == 'degrading':
                self.output.warning(f"\n建议: {data['recommendation']}")
            else:
                self.output.info(f"\n建议: {data['recommendation']}")
        
        return 0

    def _compare_baseline(self, skill) -> int:
        """基线对比"""
        # 检查是否有基线对比功能
        if not hasattr(skill, 'compare_with_baseline'):
            self.output.error("基线对比功能不可用，请确保相关模块已安装")
            return 1
        
        result = skill.compare_with_baseline(
            metric=self.args.metric,
            current_value=self.args.value,
            baseline_date=self.args.baseline
        )
        
        if not result.get('success', False):
            self.output.error(f"基线对比失败: {result.get('message', '未知错误')}")
            return 1
        
        data = result.get('data', {})
        current_value = data.get('current_value', 0)
        baseline_value = data.get('baseline_value', 0)
        change_percent = data.get('change_percent', 0)
        severity = data.get('severity', 'normal')
        message = data.get('message', '')
        
        summary = f"{self.args.metric}较基线变化{change_percent:+.1f}%"
        
        self.output.info(f"\n{'='*60}")
        self.output.info(f"摘要: {summary}")
        self.output.info(f"{'='*60}")
        
        self.output.info(f"\n指标: {self.args.metric}")
        self.output.info(f"基线日期: {self.args.baseline}")
        self.output.info(f"基线值: {baseline_value:.2f}")
        self.output.info(f"当前值: {current_value:.2f}")
        
        if change_percent > 0:
            self.output.info(f"变化: +{change_percent:.1f}%")
        else:
            self.output.info(f"变化: {change_percent:.1f}%")
        
        # 根据严重程度输出
        if severity == 'critical':
            self.output.error(f"\n严重程度: 严重")
        elif severity == 'warning':
            self.output.warning(f"\n严重程度: 警告")
        else:
            self.output.info(f"\n严重程度: 正常")
        
        if message:
            self.output.info(f"\n说明: {message}")
        
        return 0
    
    def _detect_anomalies(self, skill) -> int:
        """异常检测"""
        result = skill.detect_anomalies()

        # 获取实际数据（标准响应格式）
        anomalies_data = result.get('data', {})
        anomalies = anomalies_data.get('anomalies', [])
        total_checked = anomalies_data.get('total_checked', 0)
        metrics_list = anomalies_data.get('metrics', [])

        count = len(anomalies)
        summary = f"检测了{total_checked}个指标，发现{count}个异常" if count > 0 else f"检测了{total_checked}个指标，未发现异常"

        self.output.info(f"\n{'='*60}")
        self.output.info(f"摘要: {summary}")
        self.output.info(f"{'='*60}")

        # 显示所有检测的指标
        if metrics_list:
            self.output.info(f"\n检测的指标列表:")
            for metric in metrics_list:
                name = metric.get('name', 'unknown')
                value = metric.get('value', 'N/A')
                unit = metric.get('unit', '')
                status = metric.get('status', 'normal')
                status_icon = "[异常]" if status == "anomaly" else "[正常]"
                self.output.info(f"  {status_icon} {name}: {value} {unit}")

        if not anomalies or count == 0:
            self.output.info(f"\n说明：异常检测需要历史数据积累，首次运行可能无法检测出所有异常类型")
            return 0

        self.output.warning(f"\n发现 {count} 个异常:")

        for i, anomaly in enumerate(anomalies, 1):
            severity = anomaly.get('severity', 'unknown').upper()
            metric = anomaly.get('metric', 'unknown')
            message = anomaly.get('message', '')

            if severity == 'CRITICAL':
                self.output.error(f"\n[{i}] [{severity}] {metric}")
            elif severity == 'HIGH':
                self.output.warning(f"\n[{i}] [{severity}] {metric}")
            else:
                self.output.info(f"\n[{i}] [{severity}] {metric}")

            self.output.info(f"    {message}")
            if anomaly.get('suggestion'):
                self.output.info(f"    建议: {anomaly['suggestion']}")

        return 0
    
    def _predict_capacity(self, skill) -> int:
        """容量预测"""
        result = skill.predict_capacity(metric=self.args.resource, days=self.args.days, source=self.args.source)

        # 获取实际数据（标准响应格式）
        prediction = result.get('data', {})

        current = prediction.get('current_value', prediction.get('current_usage', 0))
        days_to_threshold = prediction.get('days_to_threshold', 999)
        urgency = prediction.get('urgency', 'unknown')
        trend = prediction.get('trend_direction', 'unknown')
        confidence = prediction.get('confidence', 0)

        # 获取预测值（优先使用30天预测）
        predictions = prediction.get('predictions', {})
        if predictions:
            predicted = predictions.get('30d', predictions.get('7d', current))
        else:
            predicted = prediction.get('predicted_usage', current)

        # 根据资源类型确定单位
        unit = self._get_resource_unit(self.args.resource)
        is_percentage = unit == "%"

        # 构建摘要
        if is_percentage:
            if days_to_threshold and days_to_threshold < 999:
                summary = f"{self.args.resource}使用率{current:.1f}%，预计{days_to_threshold}天后达到阈值"
            else:
                summary = f"{self.args.resource}使用率{current:.1f}%，容量充足"
        else:
            summary = f"{self.args.resource}当前使用{current:.2f}{unit}"

        self.output.info(f"\n{'='*60}")
        self.output.info(f"摘要: {summary}")
        self.output.info(f"{'='*60}")

        self.output.info(f"\n容量预测 - {self.args.resource}")
        if is_percentage:
            self.output.info(f"当前使用率: {current:.2f}%")
        else:
            self.output.info(f"当前使用量: {current:.2f} {unit}")

        # 显示各时间段的预测
        if predictions:
            self.output.info(f"\n预测趋势:")
            for period, value in predictions.items():
                if is_percentage:
                    self.output.info(f"  {period}: {value:.2f}%")
                else:
                    self.output.info(f"  {period}: {value:.2f} {unit}")
        else:
            if is_percentage:
                self.output.info(f"预测使用率: {predicted:.2f}%")
            else:
                self.output.info(f"预测使用量: {predicted:.2f} {unit}")

        if is_percentage:
            self.output.info(f"\n阈值: {prediction.get('threshold', 90)}%")

        if days_to_threshold is not None:
            if days_to_threshold >= 999:
                self.output.info(f"到达阈值: 容量充足（增长缓慢或稳定）")
            else:
                self.output.info(f"到达阈值: {days_to_threshold}天后")

        self.output.info(f"趋势方向: {trend.upper()}")

        self.output.info(f"紧急程度: {urgency.upper()}")
        self.output.info(f"预测置信度: {confidence*100:.1f}%")

        if prediction.get('recommendation'):
            self.output.info(f"\n建议: {prediction['recommendation']}")

        return 0

    def _get_resource_unit(self, resource: str) -> str:
        """获取资源单位"""
        units = {
            "disk": "GB",  # MySQL 返回的是数据文件大小（GB）
            "memory": "%",
            "cpu": "%",
            "connections": "个",
        }
        return units.get(resource, "%")
    
    def _collect_metrics(self, skill) -> int:
        """采集指标"""
        result = skill.collect_metrics(
            metric_types=self.args.metrics.split(',') if self.args.metrics else None,
            source=self.args.source
        )
        
        # 获取实际数据
        data = result.get('data', {})
        metrics = data.get('metrics', {})
        
        summary = f"采集到 {len(metrics)} 个指标"
        
        self.output.info(f"\n{'='*60}")
        self.output.info(f"摘要: {summary}")
        self.output.info(f"{'='*60}")
        
        self.output.info(f"\n指标采集结果 - {data.get('timestamp', '')}")
        self.output.info(f"数据来源: {data.get('source', 'unknown')}")
        
        if metrics:
            self.output.info(f"\n采集到 {len(metrics)} 个指标:")
            for name, metric_data in metrics.items():
                value = metric_data.get('value', 'N/A')
                unit = metric_data.get('unit', '')
                desc = metric_data.get('description', '')
                self.output.info(f"  {name}: {value} {unit} ({desc})")
        else:
            self.output.warning("\n未采集到任何指标")
        
        return 0
    
    def _show_history(self, skill) -> int:
        """查看历史"""
        result = skill.get_metric_history(metric_type=self.args.metric, hours=self.args.hours)
        
        # 获取实际数据（标准响应格式）
        data = result.get('data', {})
        history_list = data.get('data_points', [])
        
        count = len(history_list)
        summary = f"{self.args.metric}最近{self.args.hours}小时共{count}个数据点"
        
        self.output.info(f"\n{'='*60}")
        self.output.info(f"摘要: {summary}")
        self.output.info(f"{'='*60}")
        
        if not result.get('success', False):
            self.output.error(f"\n获取历史数据失败: {result.get('message', '未知错误')}")
            if result.get('details'):
                self.output.info(f"详情: {result.get('details')}")
            return 1
        
        if count == 0:
            self.output.info(f"\n未找到{self.args.metric}的历史数据")
            return 0
        
        self.output.info(f"\n{self.args.metric} 历史数据 (最近{self.args.hours}小时):")
        
        # 显示统计信息
        values = [h.get('value', 0) for h in history_list if isinstance(h, dict)]
        if values:
            avg = sum(values) / len(values)
            min_val = min(values)
            max_val = max(values)

            self.output.info(f"  平均值: {avg:.2f}")
            self.output.info(f"  最小值: {min_val:.2f}")
            self.output.info(f"  最大值: {max_val:.2f}")
            self.output.info(f"  数据点: {count}个")

        return 0

    def _get_db_type(self, config) -> str:
        """
        获取数据库类型

        参数:
            config: 配置对象

        返回:
            str: 数据库类型 (mysql/oracle/postgresql/unknown)
        """
        dialect = getattr(config, 'dialect', '').lower()

        if 'mysql' in dialect:
            return 'mysql'
        elif 'oracle' in dialect:
            return 'oracle'
        elif 'postgresql' in dialect:
            return 'postgresql'
        else:
            return 'unknown'

    def _get_default_monitor(self, db_type: str) -> str:
        """
        根据数据库类型获取默认监控系统

        规则:
            Oracle -> Zabbix
            MySQL -> Prometheus
            其他 -> internal

        参数:
            db_type: 数据库类型

        返回:
            str: 监控系统类型 (zabbix/prometheus/internal)
        """
        monitor_map = {
            'oracle': 'zabbix',
            'mysql': 'prometheus',
            'postgresql': 'prometheus',
        }
        return monitor_map.get(db_type, 'internal')

    def _load_all_configs(self) -> Dict[str, Any]:
        """
        加载所有可用的数据库配置
        
        使用 MultiDBConfig 动态发现所有配置的数据库实例

        返回:
            Dict: 配置字典，key为实例名，value为配置对象
        """
        from dbskiter.cli.config import MultiDBConfig

        multi_config = MultiDBConfig()
        return multi_config.load_all_configs()

    def _create_connector_from_config(self, config) -> Any:
        """
        从配置创建 UnifiedConnector

        参数:
            config: 配置对象

        返回:
            UnifiedConnector 实例
        """
        from dbskiter.shared.unified_connector import UnifiedConnector

        return UnifiedConnector(
            dialect=config.dialect,
            host=config.host,
            port=config.port,
            username=config.username,
            password=config.password,
            database=config.database,
            **config.extra
        )

    def _create_skill_smart(
        self,
        db_name: Optional[str],
        configs: Dict[str, Any]
    ) -> Optional[Any]:
        """
        智能创建 MonitorSkill

        策略:
        1. 如果指定了 db_name，尝试匹配配置
        2. 根据匹配的配置确定数据库类型和监控系统
        3. 如果配置可用，优先使用直连数据库
        4. 如果配置不可用，根据数据库类型选择外部监控（Oracle->Zabbix, MySQL->Prometheus）

        参数:
            db_name: 数据库名/主机名/实例名
            configs: 所有可用配置

        返回:
            MonitorSkill 实例，或 None
        """
        from dbskiter.db_monitor.skill import MonitorSkill
        from dbskiter.shared.oracle_metrics import OracleHostMapping

        # 1. 如果指定了 db_name，尝试在所有配置中匹配
        if db_name:
            db_name_lower = db_name.lower()
            for prefix, config in configs.items():
                # 匹配数据库名、主机名或服务名（不区分大小写）
                if (config.database.lower() == db_name_lower or
                    config.host.lower() == db_name_lower or
                    config.extra.get('service_name', '').lower() == db_name_lower):
                    self.output.info(f"找到匹配配置 [{prefix}]: {config.host}/{config.database}")
                    self._connector = self._create_connector_from_config(config)
                    return MonitorSkill(self._connector)

            # 没有找到匹配的配置，根据 db_name 推断数据库类型
            if OracleHostMapping.is_oracle_group(db_name):
                # Oracle 资产组使用 Zabbix
                host_patterns = OracleHostMapping.get_group_hosts(db_name)
                self.output.info(f"识别为 Oracle 资产组，使用 Zabbix 查询: {host_patterns}")
                return MonitorSkill(host_name=host_patterns)
            else:
                # 默认使用 Prometheus（MySQL）
                self.output.info(f"使用 Prometheus 查询: {db_name}")
                return MonitorSkill(host_name=db_name)

        # 2. 没有指定 db_name，使用当前配置
        if hasattr(self, 'connector') and self.connector:
            return MonitorSkill(self.connector)

        # 3. 尝试使用第一个可用配置
        if configs:
            first_config = list(configs.values())[0]
            prefix = list(configs.keys())[0]
            self.output.info(f"使用默认配置 [{prefix}]: {first_config.host}/{first_config.database}")
            self._connector = self._create_connector_from_config(first_config)
            return MonitorSkill(self._connector)

        return None

    def _list_available_databases(self) -> None:
        """
        显示所有可用的数据库实例
        
        用于帮助用户了解当前配置了哪些数据库
        """
        from dbskiter.cli.config import MultiDBConfig
        
        multi_config = MultiDBConfig()
        instances = multi_config.list_instances()
        
        if not instances:
            self.output.info("未找到任何数据库配置")
            return
        
        self.output.info("\n可用的数据库实例:")
        self.output.info("-" * 60)
        
        for instance_name in instances:
            config = multi_config.get_config(instance_name)
            if config:
                db_type = config.dialect.split('+')[0] if '+' in config.dialect else config.dialect
                self.output.info(f"  [{instance_name}] {config.host}:{config.port}/{config.database} ({db_type})")
        
        self.output.info("-" * 60)
        self.output.info(f"共 {len(instances)} 个数据库实例")
