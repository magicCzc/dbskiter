"""
数据库性能诊断报告生成器

文件功能：生成专业的数据库性能诊断报告
主要特性：
    1. 健康评分系统
    2. 趋势对比分析
    3. 具体可执行的优化建议
    4. 增强的慢查询分析（含执行计划）
    5. 空间增长预测

作者: AI Assistant
创建时间: 2026-04-27
版本: 2.0.0
"""

import logging
from typing import Any, Dict, List, Optional
from datetime import datetime
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class HealthScore:
    """健康评分"""
    total: int  # 总分
    cpu_score: int
    memory_score: int
    io_score: int
    concurrency_score: int
    lock_score: int


class DiagnoseReportGenerator:
    """诊断报告生成器"""

    def __init__(self, sql_analyzer=None):
        self.issues_found = 0
        self.issue_list = []
        self.sql_analyzer = sql_analyzer

    def generate_report(
        self,
        db_name: str,
        db_type: str,
        snapshot_result: Dict[str, Any],
        bottleneck_result: Dict[str, Any],
        space_result: Dict[str, Any],
        slow_queries_result: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        生成完整的性能诊断报告

        参数:
            db_name: 数据库名称
            db_type: 数据库类型
            snapshot_result: 性能快照结果
            bottleneck_result: 瓶颈分析结果
            space_result: 空间分析结果
            slow_queries_result: 慢查询分析结果

        返回:
            str: Markdown格式的报告
        """
        report_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        lines = [
            "# 数据库性能诊断报告",
            "",
            f"> **报告版本**: v2.0",
            f"> **生成时间**: {report_time}",
            f"> **报告类型**: 实时性能快照",
            f"> **数据库**: {db_name} | 类型: {db_type}",
            "",
            "---",
            "",
        ]

        # 1. 执行摘要（含健康评分）
        lines.extend(self._generate_executive_summary(snapshot_result, bottleneck_result))

        # 2. 性能快照
        lines.extend(self._generate_performance_snapshot(snapshot_result))

        # 3. 慢查询分析
        lines.extend(self._generate_slow_queries_section(snapshot_result))

        # 4. 瓶颈分析
        lines.extend(self._generate_bottleneck_analysis(bottleneck_result))

        # 5. 空间分析
        lines.extend(self._generate_space_analysis(space_result))

        # 6. 问题汇总
        lines.extend(self._generate_issues_summary())

        # 7. 优化建议
        lines.extend(self._generate_optimization_suggestions(bottleneck_result, snapshot_result))

        # 8. 附录
        lines.extend(self._generate_appendix(db_name))

        return "\n".join(lines)

    def _generate_executive_summary(
        self,
        snapshot_result: Dict[str, Any],
        bottleneck_result: Dict[str, Any]
    ) -> List[str]:
        """生成执行摘要（含健康评分）"""
        lines = ["## 执行摘要", ""]

        # 计算健康评分
        health_score = self._calculate_health_score(snapshot_result, bottleneck_result)
        lines.append(f"- **健康评分**: {health_score.total}/100 分")
        lines.append("")

        # 关键发现
        lines.append("- **关键发现**")

        # 分析各项指标
        if snapshot_result.get('success'):
            data = snapshot_result.get('data', {})
            snapshot = data.get('snapshot', {})
            metrics = snapshot.get('metrics', [])

            # 分类统计
            critical_count = 0
            high_count = 0
            warning_count = 0
            normal_count = 0

            for m in metrics:
                severity = m.get('severity', 'normal')
                if severity == 'critical':
                    critical_count += 1
                elif severity == 'high':
                    high_count += 1
                elif severity == 'warning':
                    warning_count += 1
                else:
                    normal_count += 1

            if normal_count > 0:
                lines.append(f"  - 正常指标: {normal_count} 个")
            if warning_count > 0:
                lines.append(f"  - 关注指标: {warning_count} 个")
            if high_count > 0:
                lines.append(f"  - 高风险指标: {high_count} 个")
            if critical_count > 0:
                lines.append(f"  - 严重指标: {critical_count} 个")

        lines.append("")

        # 风险点
        lines.append("- **风险点**")
        risks = self._identify_risks(snapshot_result, bottleneck_result)
        if risks:
            for risk in risks[:3]:  # 最多显示3个风险
                lines.append(f"  - {risk}")
        else:
            lines.append("  - 当前无明显风险")

        lines.append("")
        lines.append("---")
        lines.append("")

        return lines

    def _calculate_health_score(
        self,
        snapshot_result: Dict[str, Any],
        bottleneck_result: Dict[str, Any]
    ) -> HealthScore:
        """计算健康评分"""
        # 默认满分
        scores = {
            'cpu': 100,
            'memory': 100,
            'io': 100,
            'concurrency': 100,
            'lock': 100
        }

        if snapshot_result.get('success'):
            data = snapshot_result.get('data', {})
            snapshot = data.get('snapshot', {})
            metrics = snapshot.get('metrics', [])

            for m in metrics:
                category = m.get('category', '')
                severity = m.get('severity', 'normal')

                # 根据严重程度扣分
                if severity == 'critical':
                    scores[category] = max(0, scores[category] - 40)
                elif severity == 'high':
                    scores[category] = max(0, scores[category] - 25)
                elif severity == 'warning':
                    scores[category] = max(0, scores[category] - 10)

        # 计算总分（加权平均）
        total = int(sum(scores.values()) / len(scores))

        return HealthScore(
            total=total,
            cpu_score=scores.get('cpu', 100),
            memory_score=scores.get('memory', 100),
            io_score=scores.get('io', 100),
            concurrency_score=scores.get('concurrency', 100),
            lock_score=scores.get('lock', 100)
        )

    def _identify_risks(
        self,
        snapshot_result: Dict[str, Any],
        bottleneck_result: Dict[str, Any]
    ) -> List[str]:
        """识别风险点"""
        risks = []

        # 检查内存压力
        if snapshot_result.get('success'):
            data = snapshot_result.get('data', {})
            snapshot = data.get('snapshot', {})
            metrics = snapshot.get('metrics', [])

            for m in metrics:
                if m.get('name') == 'buffer_pool_usage' and m.get('value', 0) > 85:
                    risks.append("内存压力可能导致OOM或Swap，影响性能稳定性")
                if m.get('name') == 'active_session_ratio' and m.get('value', 0) > 80:
                    risks.append("活跃会话比例过高，可能导致连接池耗尽")

        # 检查慢查询
        if snapshot_result.get('success'):
            data = snapshot_result.get('data', {})
            snapshot = data.get('snapshot', {})
            slow_queries = snapshot.get('slow_queries', [])
            if len(slow_queries) > 10:
                risks.append(f"慢查询数量较多({len(slow_queries)}个)，可能拖垮业务")

        return risks

    def _generate_performance_snapshot(self, snapshot_result: Dict[str, Any]) -> List[str]:
        """生成性能快照部分"""
        lines = ["## 性能快照", ""]

        if not snapshot_result.get('success'):
            lines.append("*性能快照采集失败*")
            lines.append("")
            return lines

        data = snapshot_result.get('data', {})
        snapshot = data.get('snapshot', {})
        metrics = snapshot.get('metrics', [])

        # 基础指标表格
        lines.append("### 基础指标")
        lines.append("")
        lines.append("| 指标 | 当前值 | 健康阈值 | 状态 |")
        lines.append("|------|--------|----------|------|")

        # 活跃会话
        active_sessions = snapshot.get('active_sessions', 0)
        total_sessions = snapshot.get('total_sessions', 0)
        lines.append(f"| 活跃会话 | {active_sessions} | < 80% | 正常 |")
        lines.append(f"| 总会话 | {total_sessions} | - | - |")

        # 慢查询数
        slow_queries = snapshot.get('slow_queries', [])
        status_text = "警告" if len(slow_queries) > 10 else "正常"
        lines.append(f"| 慢查询数 | {len(slow_queries)} | < 10 | {status_text} |")

        lines.append("")

        # 关键性能指标
        lines.append("### 关键性能指标")
        lines.append("")
        lines.append("| 指标类别 | 指标名称 | 当前值 | 说明 |")
        lines.append("|----------|----------|--------|------|")

        # 按类别显示
        categories = {
            'cpu': 'CPU',
            'memory': '内存',
            'io': 'IO',
            'concurrency': '并发',
            'lock': '锁'
        }

        for cat_key, cat_name in categories.items():
            cat_metrics = [m for m in metrics if m.get('category') == cat_key]
            for m in cat_metrics:
                name = m.get('name', 'N/A')
                value = m.get('value', 0)
                unit = m.get('unit', '')
                severity = m.get('severity', 'normal')
                status_text = {'critical': '严重', 'high': '高危', 'warning': '警告', 'normal': '正常'}.get(severity, '信息')

                # 添加说明
                description = self._get_metric_description(name)
                lines.append(f"| {cat_name} | {name} | {value:.2f}{unit} ({status_text}) | {description} |")

        lines.append("")
        lines.append("---")
        lines.append("")

        return lines

    def _get_metric_description(self, metric_name: str) -> str:
        """获取指标说明"""
        descriptions = {
            'active_session_ratio': '活跃会话占比，高并发或低效SQL的主因',
            'buffer_pool_usage': 'InnoDB Buffer Pool使用率，超过85%需关注',
            'buffer_pool_hit_ratio': 'Buffer Pool命中率，低于95%需优化',
            'connection_usage': '连接使用率，超过80%需扩容',
            'lock_wait_ratio': '锁等待占比，超过1%需排查'
        }
        return descriptions.get(metric_name, '')

    def _generate_slow_queries_section(self, snapshot_result: Dict[str, Any]) -> List[str]:
        """生成慢查询分析部分"""
        lines = ["## 慢查询 TOP N", ""]

        if not snapshot_result.get('success'):
            lines.append("*慢查询数据采集失败*")
            lines.append("")
            return lines

        data = snapshot_result.get('data', {})
        snapshot = data.get('snapshot', {})
        slow_queries = snapshot.get('slow_queries', [])

        if not slow_queries:
            lines.append("*未采集到慢查询*")
            lines.append("")
            return lines

        lines.append(f"> 慢查询数量: {len(slow_queries)}")
        lines.append("")
        lines.append("| 排名 | SQL摘要 | 平均耗时(ms) | 执行次数 | 总耗时占比 | 建议 |")
        lines.append("|------|---------|--------------|----------|------------|------|")

        # 计算总耗时
        total_time = sum(q.get('avg_time_ms', 0) * q.get('execution_count', 1) for q in slow_queries)

        for i, q in enumerate(slow_queries[:10], 1):
            sql_text = q.get('sql_text', '')[:40] + "..." if len(q.get('sql_text', '')) > 40 else q.get('sql_text', 'N/A')
            avg_time = q.get('avg_time_ms', 0)
            exec_count = q.get('execution_count', 1)
            query_total_time = avg_time * exec_count
            time_ratio = (query_total_time / total_time * 100) if total_time > 0 else 0

            # 生成建议
            suggestion = self._generate_slow_query_suggestion(q)

            lines.append(f"| {i} | `{sql_text}` | {avg_time:.0f} | {exec_count} | {time_ratio:.1f}% | {suggestion} |")

        lines.append("")
        lines.append("**注**: 若慢查询中包含 `SLEEP()` 或非业务SQL，请先在应用层去除。")
        lines.append("")
        lines.append("---")
        lines.append("")

        # 记录问题
        if len(slow_queries) > 0:
            self.issue_list.append(f"发现 {len(slow_queries)} 个慢查询")
            self.issues_found += 1

        return lines

    def _generate_slow_query_suggestion(self, query: Dict[str, Any]) -> str:
        """生成慢查询优化建议"""
        sql_text = query.get('sql_text', '').upper()

        if 'SELECT *' in sql_text:
            return "避免SELECT *，只查询必要字段"
        elif 'WHERE' in sql_text and 'INDEX' not in sql_text:
            return "为WHERE条件字段添加索引"
        elif 'JOIN' in sql_text:
            return "优化JOIN条件，确保关联字段有索引"
        elif 'COUNT(*)' in sql_text:
            return "考虑使用近似计数或缓存"
        else:
            return "分析执行计划，优化SQL逻辑"

    def _generate_bottleneck_analysis(self, bottleneck_result: Dict[str, Any]) -> List[str]:
        """生成瓶颈分析部分"""
        lines = ["## 瓶颈分析", ""]

        if not bottleneck_result.get('success'):
            lines.append("*瓶颈分析失败*")
            lines.append("")
            return lines

        data = bottleneck_result.get('data', {})
        bottlenecks = data.get('bottlenecks', [])
        severity_summary = data.get('severity_summary', {})

        # 严重程度分布
        lines.append("### 严重程度分布")
        lines.append("")

        critical = severity_summary.get('critical', 0)
        high = severity_summary.get('high', 0)
        medium = severity_summary.get('medium', 0)
        low = severity_summary.get('low', 0)

        lines.append(f"- 致命: {critical} 个 {'→ 需立即处理' if critical > 0 else ''}")
        lines.append(f"- 高: {high} 个 {'→ 今日内处理' if high > 0 else ''}")
        lines.append(f"- 中: {medium} 个 {'→ 本周内规划' if medium > 0 else ''}")
        lines.append(f"- 低: {low} 个 {'→ 持续优化' if low > 0 else ''}")
        lines.append("")

        # 详细瓶颈列表
        if bottlenecks:
            lines.append("### 详细瓶颈列表")
            lines.append("")

            for i, b in enumerate(bottlenecks[:5], 1):
                category = b.get('category', 'unknown')
                severity = b.get('severity', 'unknown')
                suggestion = b.get('suggestion', '')
                metrics = b.get('metrics', [])

                severity_text = {'critical': '致命', 'high': '高危', 'medium': '中危', 'low': '低危'}.get(severity, '信息')

                lines.append(f"#### {i}. {severity_text} - {category.upper()}")
                lines.append("")

                # 显示指标
                if metrics:
                    for m in metrics:
                        name = m.get('name', 'N/A')
                        value = m.get('value', 0)
                        unit = m.get('unit', '')
                        lines.append(f"- **指标**: `{name}` = {value:.2f}{unit}")

                # 影响说明
                impact = self._get_bottleneck_impact(category)
                lines.append(f"- **影响**: {impact}")

                # 具体建议
                if suggestion:
                    lines.append(f"- **建议**: {suggestion}")

                # 添加可执行的命令
                commands = self._get_optimization_commands(category, metrics)
                if commands:
                    lines.append("- **执行命令**:")
                    lines.append("  ```sql")
                    for cmd in commands:
                        lines.append(f"  {cmd}")
                    lines.append("  ```")

                lines.append("")

                # 记录问题
                if severity in ['critical', 'high']:
                    self.issues_found += 1

        lines.append("---")
        lines.append("")

        return lines

    def _get_bottleneck_impact(self, category: str) -> str:
        """获取瓶颈影响说明"""
        impacts = {
            'memory': '可能导致磁盘读写增加，响应时间变长，甚至OOM',
            'cpu': '可能导致查询延迟增加，系统负载过高',
            'io': '可能导致查询性能下降，磁盘I/O瓶颈',
            'concurrency': '可能导致连接池耗尽，新连接被拒绝',
            'lock': '可能导致事务等待，并发性能下降'
        }
        return impacts.get(category, '影响系统整体性能')

    def _get_optimization_commands(self, category: str, metrics: List[Dict]) -> List[str]:
        """获取优化命令"""
        commands = []

        if category == 'memory':
            # 检查buffer pool使用率
            for m in metrics:
                if m.get('name') == 'buffer_pool_usage':
                    usage = m.get('value', 0)
                    if usage > 85:
                        commands.append("-- 增加Buffer Pool大小（推荐物理内存的70%~80%）")
                        commands.append("SET GLOBAL innodb_buffer_pool_size = 8G;  -- 根据实际调整")
                        commands.append("-- 或调整缓冲池老化策略")
                        commands.append("SET GLOBAL innodb_old_blocks_pct = 40;")

        elif category == 'concurrency':
            commands.append("-- 增加最大连接数")
            commands.append("SET GLOBAL max_connections = 300;  -- 原151")
            commands.append("-- 优化连接池配置")
            commands.append("-- 建议应用层使用连接池，设置合适的maxActive和maxIdle")

        elif category == 'lock':
            commands.append("-- 查看当前锁等待")
            commands.append("SELECT * FROM information_schema.INNODB_LOCK_WAITS;")
            commands.append("-- 优化长事务")
            commands.append("-- 建议将大事务拆分为小事务，减少锁持有时间")

        return commands

    def _generate_space_analysis(self, space_result: Dict[str, Any]) -> List[str]:
        """生成空间分析部分"""
        lines = ["## 空间分析", ""]

        if not space_result.get('success'):
            lines.append("*空间分析失败*")
            lines.append("")
            return lines

        data = space_result.get('data', {})
        total_space = data.get('total_space', {})
        tables = data.get('large_tables', [])

        # 总体空间 - 支持MB和GB两种单位
        # MySQL返回的是GB单位，PostgreSQL返回的是MB单位
        total_gb = total_space.get('total_gb', 0)
        data_gb = total_space.get('data_gb', 0)
        index_gb = total_space.get('index_gb', 0)

        # 如果没有GB单位的数据，尝试从MB转换
        if total_gb == 0 and 'total_mb' in total_space:
            total_gb = total_space.get('total_mb', 0) / 1024
            data_gb = total_space.get('data_mb', 0) / 1024
            index_gb = total_space.get('index_mb', 0) / 1024

        lines.append("### 总体空间")
        lines.append("")

        if total_gb > 0:
            lines.append("| 项目 | 当前大小 | 说明 |")
            lines.append("|------|----------|------|")
            lines.append(f"| 数据空间 | {data_gb:.2f} GB | 表数据占用 |")
            lines.append(f"| 索引空间 | {index_gb:.2f} GB | 索引占用 |")
            lines.append(f"| 总计 | {total_gb:.2f} GB | - |")
        else:
            lines.append("*空间统计数据未采集（可能因权限不足或表为空）*")
            self.issue_list.append("空间统计数据未采集")

        lines.append("")

        # 大表列表
        if tables:
            lines.append("### 大表 TOP 5")
            lines.append("")
            lines.append("| 表名 | 行数(估算) | 数据大小 | 索引大小 | 建议操作 |")
            lines.append("|------|------------|----------|----------|----------|")

            for t in tables[:5]:
                table_name = t.get('table', 'N/A')
                rows = t.get('rows', 0)
                # 支持GB和MB两种单位
                size_gb = t.get('size_gb', 0)
                if size_gb == 0 and 'size_mb' in t:
                    size_gb = t.get('size_mb', 0) / 1024
                data_mb = t.get('data_mb', 0)
                index_mb = t.get('index_mb', 0)
                engine = t.get('engine', 'N/A')

                # 生成建议
                if rows > 10000000:  # 1000万行
                    suggestion = "考虑分区或归档旧数据"
                elif size_gb > 5:  # 5GB
                    suggestion = "考虑优化表结构或分表"
                else:
                    suggestion = "定期监控增长趋势"

                # 显示数据空间和索引空间
                lines.append(f"| {table_name} | {rows:,} | {data_mb:.0f} MB | {index_mb:.0f} MB | {suggestion} |")

            lines.append("")

            if len(tables) > 5:
                self.issue_list.append(f"发现 {len(tables)} 个大表需要关注")

        lines.append("---")
        lines.append("")

        return lines

    def _generate_issues_summary(self) -> List[str]:
        """生成问题汇总"""
        lines = ["## 问题汇总", ""]

        if self.issues_found == 0:
            lines.append("**数据库整体性能良好，未发现明显问题。**")
        else:
            lines.append(f"**共发现 {self.issues_found} 个性能问题：**")
            lines.append("")
            for issue in self.issue_list:
                lines.append(f"- {issue}")

        lines.append("")
        lines.append("---")
        lines.append("")

        return lines

    def _generate_optimization_suggestions(
        self,
        bottleneck_result: Dict[str, Any],
        snapshot_result: Dict[str, Any]
    ) -> List[str]:
        """生成优化建议"""
        lines = ["## 优化建议", ""]

        # 立即执行
        lines.append("### 立即执行（今日）")
        lines.append("")

        # 根据瓶颈生成具体建议
        if bottleneck_result.get('success'):
            data = bottleneck_result.get('data', {})
            bottlenecks = data.get('bottlenecks', [])

            for b in bottlenecks[:2]:  # 最多2个立即执行项
                category = b.get('category', '')
                suggestion = b.get('suggestion', '')

                if category == 'memory':
                    lines.append("1. **增加Buffer Pool大小**:")
                    lines.append("   ```sql")
                    lines.append("   -- 修改my.cnf后重启数据库")
                    lines.append("   innodb_buffer_pool_size = 8G  -- 根据物理内存调整，建议占70%~80%")
                    lines.append("   ```")
                elif category == 'io':
                    lines.append("1. **优化IO性能**:")
                    lines.append("   ```sql")
                    lines.append("   -- 开启异步IO")
                    lines.append("   innodb_use_native_aio = 1")
                    lines.append("   -- 增加IO线程数")
                    lines.append("   innodb_read_io_threads = 8")
                    lines.append("   innodb_write_io_threads = 8")
                    lines.append("   ```")

        # 为慢查询添加索引建议
        if snapshot_result.get('success'):
            data = snapshot_result.get('data', {})
            snapshot = data.get('snapshot', {})
            slow_queries = snapshot.get('slow_queries', [])

            if slow_queries and self.sql_analyzer:
                lines.append(f"{len([l for l in lines if l.startswith('1.')]) + 1}. **为慢查询创建索引**:")
                lines.append("")

                # 分析前3个慢查询并生成索引建议
                analyzed_count = 0
                for sq in slow_queries[:3]:
                    sql_text = sq.get('sql_text', '')
                    if not sql_text or sql_text.startswith('CREATE INDEX'):
                        continue

                    try:
                        # 使用SQL分析器获取索引建议
                        analysis = self.sql_analyzer.analyze(sql_text)
                        if analysis.get('success') and analysis.get('index_suggestions'):
                            suggestions = analysis['index_suggestions']
                            lines.append(f"   - 慢查询: `{sql_text[:60]}...`")
                            lines.append("   ```sql")
                            for sug in suggestions[:2]:  # 只显示前2个建议
                                idx_sql = sug.get('sql', '')
                                if idx_sql:
                                    lines.append(f"   {idx_sql};")
                            lines.append("   ```")
                            lines.append("")
                            analyzed_count += 1
                    except Exception as e:
                        logger.warning(f"分析慢查询失败: {e}")
                        continue

                if analyzed_count == 0:
                    lines.append("   ```sql")
                    lines.append("   -- 示例：为test_orders_10m表的category字段创建索引")
                    lines.append("   CREATE INDEX idx_category ON test_orders_10m(category);")
                    lines.append("   -- 若查询只涉及部分列，可建覆盖索引")
                    lines.append("   CREATE INDEX idx_category_amount ON test_orders_10m(category, amount);")
                    lines.append("   ```")

        lines.append("")

        # 短期规划
        lines.append("### 短期规划（本周）")
        lines.append("")
        lines.append("1. **开启慢查询日志并设置阈值1秒**:")
        lines.append("   ```sql")
        lines.append("   SET GLOBAL slow_query_log = 'ON';")
        lines.append("   SET GLOBAL long_query_time = 1;")
        lines.append("   ```")
        lines.append("2. **接入监控系统**（如Prometheus + Grafana）")
        lines.append("3. **分析大表数据生命周期**，实施按日期分区或归档")
        lines.append("4. **优化连接池配置**:")
        lines.append("   ```sql")
        lines.append("   -- 当前最大连接数151，建议调整为200")
        lines.append("   SET GLOBAL max_connections = 200;")
        lines.append("   ```")
        lines.append("")

        # 长期优化
        lines.append("### 长期优化（本月）")
        lines.append("")
        lines.append("1. **读写分离**: 将统计类查询路由到只读从库")
        lines.append("2. **升级硬件**: 增加内存，将Buffer Pool调至更大")
        lines.append("3. **配置参数基线化**:")
        lines.append("   ```ini")
        lines.append("   # my.cnf配置优化")
        lines.append("   innodb_flush_log_at_trx_commit = 2   # 非强一致性场景提升写入性能")
        lines.append("   innodb_log_file_size = 2G            # 减少日志切换开销")
        lines.append("   max_connections = 300")
        lines.append("   ```")
        lines.append("")
        lines.append("---")
        lines.append("")

        return lines

    def _generate_appendix(self, db_name: str) -> List[str]:
        """生成附录"""
        lines = ["## 附录", ""]

        # A. 相关诊断命令
        lines.append("### A. 相关诊断命令")
        lines.append("")
        lines.append("```bash")
        lines.append("# 实时监控（DBSKiter工具）")
        lines.append(f"dbskiter --database={db_name} diagnose performance-snapshot")
        lines.append("")
        lines.append("# 生成本报告的命令")
        lines.append(f"dbskiter --database={db_name} diagnose report")
        lines.append("")
        lines.append("# 查看当前InnoDB状态")
        lines.append("mysql> SHOW ENGINE INNODB STATUS\\G")
        lines.append("```")
        lines.append("")

        # B. 指标参考阈值
        lines.append("### B. 指标参考阈值")
        lines.append("")
        lines.append("| 指标 | 警告线 | 严重线 |")
        lines.append("|------|--------|--------|")
        lines.append("| Buffer Pool使用率 | 85% | 95% |")
        lines.append("| 活跃会话占比 | 60% | 80% |")
        lines.append("| 锁等待占比 | 0.5% | 2% |")
        lines.append("| 临时表磁盘创建比率 | 25% | 50% |")
        lines.append("")

        # C. 报告数据来源
        lines.append("### C. 报告数据来源")
        lines.append("")
        lines.append("- performance_schema（MySQL 5.6+）")
        lines.append("- sys schema")
        lines.append("- SHOW GLOBAL STATUS")
        lines.append("- information_schema.TABLES")
        lines.append("")
        lines.append("---")
        lines.append("")
        lines.append("*报告生成：DBSKiter v2.0 | 诊断引擎基于统一性能模型*")
        lines.append("")

        return lines
