"""
P0 诊断处理器 - 高频场景

拆分自 diagnose.py 2081 行 → 保持文件 < 500 行
"""

from typing import Any, Dict
import json


# 模块元数据：记录每个方法的子命令名（用于测试验证方法归属）
_REALTIME_DIAGNOSE = "_realtime_diagnose"
_TOP_SQL = "_top_sql"
_ANALYZE_LOCKS = "_analyze_locks"
_DIAGNOSE_SQL = "_diagnose_sql"
_SPACE_DIAGNOSE = "_space_diagnose"


class DiagnoseP0Mixin:
    """P0 高频诊断处理器（realtime, top, locks, sql, space）"""

    # ==================== realtime - 实时诊断 ====================

    def _realtime_diagnose(self, skill) -> int:
        """实时诊断 - 数据库有点慢/卡住了"""
        self.output.info("\n" + "=" * 60)
        self.output.info("实时诊断 - 分析当前数据库性能")
        self.output.info("=" * 60)

        # 1. 检查当前活跃连接
        self.output.info("\n[1] 检查活跃连接...")
        conn_info = skill.get_realtime_connections()
        if conn_info.get('success'):
            data = conn_info.get('data', {})
            self.output.info(f"  总连接数: {data.get('total', 'N/A')}")
            self.output.info(f"  活跃连接: {data.get('active', 'N/A')}")
            self.output.info(f"  慢查询: {data.get('slow_count', 'N/A')}")

        # 2. 检查锁等待
        self.output.info("\n[2] 检查锁等待...")
        lock_info = skill.get_lock_waits()
        if lock_info.get('success'):
            data = lock_info.get('data', {})
            waits = data.get('lock_waits', [])
            if waits:
                self.output.warning(f"  发现 {len(waits)} 个锁等待")
                for w in waits[:3]:
                    self.output.warning(f"    - {w.get('waiting_thread')} 等待 {w.get('blocking_thread')}")
            else:
                self.output.info("  未发现锁等待")

        # 3. 检查TOP SQL
        self.output.info("\n[3] 检查TOP SQL...")
        top_sql = skill.get_top_sql(limit=5, threshold=self.args.threshold)
        if top_sql.get('success'):
            data = top_sql.get('data', {})
            queries = data.get('queries', [])
            if queries:
                self.output.info(f"  发现 {len(queries)} 个慢查询（>{self.args.threshold}秒）:")
                for i, q in enumerate(queries, 1):
                    sql = q.get('sql', '')[:50]
                    exec_time = q.get('exec_time', q.get('time', 0))
                    self.output.info(f"    {i}. [{exec_time:.2f}s] {sql}...")
            else:
                self.output.info("  未发现慢查询")

        # 4. 给出建议
        self.output.info("\n" + "=" * 60)
        self.output.info("诊断建议")
        self.output.info("=" * 60)

        suggestions = []
        conn_data = conn_info.get('data', {}) if conn_info.get('success') else {}
        if conn_data.get('total', 0) > 100:
            suggestions.append(f"连接数过多({conn_data.get('total')})，检查连接池配置")
        if conn_data.get('slow_count', 0) > 5:
            suggestions.append(f"发现{conn_data.get('slow_count')}个慢查询，执行diagnose slow-queries查看详情")

        lock_data = lock_info.get('data', {}) if lock_info.get('success') else {}
        if lock_data.get('lock_waits', []):
            suggestions.append(f"存在{len(lock_data.get('lock_waits', []))}个锁等待，检查长事务")

        top_data = top_sql.get('data', {}) if top_sql.get('success') else {}
        if top_data.get('queries', []):
            suggestions.append(f"发现{len(top_data.get('queries', []))}个高耗SQL，执行diagnose top查看详情")

        if suggestions:
            for s in suggestions:
                self.output.info(f"  - {s}")
        else:
            self.output.info("  数据库运行正常，暂无优化建议")

        return 0

    # ==================== top - TOP SQL ====================

    def _top_sql(self, skill) -> int:
        """TOP SQL分析 - CPU飙高了"""
        result = skill.get_top_sql(
            limit=self.args.limit,
            order_by=self.args.by
        )
        self._last_skill_result = result

        if not result.get('success'):
            self.output.error(f"获取TOP SQL失败: {self._extract_error_message(result)}")
            return 1

        data = result.get('data', {})
        queries = data.get('queries', [])

        self.output.info("\n" + "=" * 60)
        self.output.info(f"TOP SQL - 按{self.args.by}排序")
        self.output.info("=" * 60)

        if not queries:
            self.output.info("\n未发现TOP SQL")
            return 0

        self.output.info(f"\n共 {len(queries)} 条SQL:\n")

        for i, q in enumerate(queries, 1):
            exec_time = q.get('exec_time', q.get('time', 0))
            self.output.info(f"[{i}] 平均执行时间: {exec_time:.3f}s")
            if q.get('total_time'):
                self.output.info(f"    总执行时间: {q.get('total_time', 0):.2f}s")
            if q.get('executions'):
                self.output.info(f"    执行次数: {q.get('executions')}")
            if q.get('sql_id'):
                self.output.info(f"    SQL ID: {q.get('sql_id')}")
            rows_examined = q.get('rows_examined', q.get('buffer_gets', 0))
            rows_sent = q.get('rows_sent', q.get('disk_reads', 0))
            self.output.info(f"    逻辑读: {rows_examined}")
            self.output.info(f"    物理读: {rows_sent}")
            if q.get('cpu_time'):
                self.output.info(f"    CPU时间: {q.get('cpu_time', 0):.3f}s")
            self.output.info(f"    SQL: {q.get('sql', '')[:100]}...")
            if q.get('suggestion'):
                self.output.info(f"    建议: {q.get('suggestion')}")
            self.output.info("")

        return 0

    # ==================== locks - 锁分析 ====================

    def _analyze_locks(self, skill) -> int:
        """锁分析 - 有死锁/阻塞"""
        result = skill.analyze_locks()
        self._last_skill_result = result

        if not result.get('success'):
            self.output.error(f"锁分析失败: {self._extract_error_message(result)}")
            return 1

        data = result.get('data', {})

        self.output.info("\n" + "=" * 60)
        self.output.info("锁分析结果")
        self.output.info("=" * 60)

        # 死锁
        deadlocks = data.get('deadlocks', [])
        if deadlocks:
            self.output.warning(f"\n[死锁] 发现 {len(deadlocks)} 个死锁:")
            for d in deadlocks:
                self.output.warning(f"  时间: {d.get('timestamp')}")
                self.output.warning(f"  详情: {d.get('detail', 'N/A')[:100]}")
        else:
            self.output.info("\n[死锁] 未发现死锁")

        # 锁等待
        lock_waits = data.get('lock_waits', [])
        if lock_waits:
            self.output.warning(f"\n[锁等待] 发现 {len(lock_waits)} 个锁等待:")
            for w in lock_waits:
                self.output.warning(f"  等待线程: {w.get('waiting_thread')}")
                self.output.warning(f"  阻塞线程: {w.get('blocking_thread')}")
                self.output.warning(f"  等待时间: {w.get('wait_time', 0)}s")
                self.output.warning(f"  SQL: {w.get('sql', 'N/A')[:50]}...")
                if self.args.kill:
                    self.output.info(f"  KILL语句: KILL {w.get('blocking_thread')}")
        else:
            self.output.info("\n[锁等待] 未发现锁等待")

        # 锁统计
        stats = data.get('statistics', {})
        if stats:
            self.output.info(f"\n[统计] 当前锁状态:")
            self.output.info(f"  表锁: {stats.get('table_locks', 0)}")
            self.output.info(f"  行锁: {stats.get('row_locks', 0)}")

        return 0

    # ==================== sql - SQL深度分析 ====================

    def _diagnose_sql(self, skill) -> int:
        """SQL深度分析"""
        params = None
        if self.args.params:
            params = json.loads(self.args.params)

        result = skill.analyze_sql(self.args.sql, params)
        self._last_skill_result = result

        if isinstance(result, dict) and 'data' in result:
            data = result.get('data', {})
            score = data.get('score', 0)
            issues = data.get('issues', [])
        else:
            data = result
            score = result.get('score', 0)
            issues = result.get('issues', [])

        summary = f"SQL评分{score}/100，发现{len(issues)}个问题"
        self.output.info("\n" + "=" * 60)
        self.output.info(f"摘要: {summary}")
        self.output.info("=" * 60)

        self.output.info(f"\nSQL: {data.get('sql', self.args.sql)[:200]}")
        self.output.info(f"类型: {data.get('sql_type', 'UNKNOWN')}")
        self.output.info(f"评分: {score}/100")

        if issues:
            self.output.warning(f"\n发现问题 ({len(issues)}个):")
            for issue in issues:
                severity = issue.get('severity', 'info')
                msg = issue.get('description') or issue.get('message', '')
                issue_type = issue.get('issue_type', '')

                if severity in ('critical', 'high'):
                    self.output.error(f"  [严重] {msg}")
                elif severity in ('medium', 'warning'):
                    self.output.warning(f"  [警告] {msg}")
                else:
                    self.output.info(f"  [提示] {msg}")

                if issue.get('suggestion'):
                    suggestion = issue.get('suggestion')
                    if isinstance(suggestion, dict):
                        if suggestion.get('reason'):
                            self.output.info(f"    原因: {suggestion.get('reason')}")
                        if suggestion.get('create_sql'):
                            self.output.info(f"    SQL: {suggestion.get('create_sql')}")
                    else:
                        self.output.info(f"    建议: {suggestion}")

                if issue_type:
                    self.output.info(f"    类型: {issue_type}")

        optimizations = data.get('optimizations', [])
        if optimizations:
            self.output.success(f"\n优化建议 ({len(optimizations)}个):")
            for opt in optimizations:
                self.output.info(f"  [{opt.get('type')}] {opt.get('description')}")
                if opt.get('sql'):
                    self.output.info(f"    重写: {opt.get('sql')[:100]}...")

        return 0

    # ==================== space - 空间诊断 ====================

    def _space_diagnose(self, skill) -> int:
        """空间诊断 - 空间不够了"""
        result = skill.analyze_space(
            top_n=self.args.top,
            min_size_mb=self.args.min_size
        )
        self._last_skill_result = result

        if not result.get('success'):
            self.output.error(f"空间诊断失败: {self._extract_error_message(result)}")
            return 1

        data = result.get('data', {})

        self.output.info("\n" + "=" * 60)
        self.output.info("空间诊断结果")
        self.output.info("=" * 60)

        # 总体空间
        total = data.get('total_space', {})
        self.output.info(f"\n[总体空间]")
        if 'total_gb' in total:
            self.output.info(f"  总大小: {total.get('total_gb', 0):.2f} GB")
            self.output.info(f"  数据大小: {total.get('data_gb', 0):.2f} GB")
            self.output.info(f"  索引大小: {total.get('index_gb', 0):.2f} GB")
            self.output.info(f"  剩余空间: {total.get('free_gb', 0):.2f} GB")
        elif 'total_mb' in total:
            self.output.info(f"  总大小: {total.get('total_mb', 0):.2f} MB ({total.get('total_mb', 0)/1024:.2f} GB)")
            self.output.info(f"  数据大小: {total.get('data_mb', 0):.2f} MB ({total.get('data_mb', 0)/1024:.2f} GB)")
            self.output.info(f"  索引大小: {total.get('index_mb', 0):.2f} MB ({total.get('index_mb', 0)/1024:.2f} GB)")
            if 'free_gb' in total:
                self.output.info(f"  剩余空间: {total.get('free_gb', 0):.2f} GB")
        else:
            self.output.info(f"  总大小: 0.00 GB")
            self.output.info(f"  数据大小: 0.00 GB")
            self.output.info(f"  索引大小: 0.00 GB")
            self.output.info(f"  剩余空间: 0.00 GB")

        # TOP大表
        tables = data.get('large_tables', [])
        if tables:
            self.output.info(f"\n[TOP {len(tables)} 大表]")
            for i, t in enumerate(tables, 1):
                self.output.info(
                    f"  {i}. {t.get('table')}: "
                    f"{t.get('size_mb', 0):.1f} MB "
                    f"(数据: {t.get('data_mb', 0):.1f} MB, "
                    f"索引: {t.get('index_mb', 0):.1f} MB)"
                )
                if t.get('fragmentation', 0) > 20:
                    self.output.warning(f"     碎片率: {t.get('fragmentation'):.1f}% (建议优化)")

        # 建议
        suggestions = data.get('suggestions', [])
        if suggestions:
            self.output.info("\n[优化建议]")
            for s in suggestions:
                if isinstance(s, dict):
                    priority = s.get('priority', '')
                    suggestion_text = s.get('suggestion', s.get('description', ''))
                    if priority == 'high':
                        self.output.warning(f"  - [高] {suggestion_text}")
                    elif priority == 'medium':
                        self.output.info(f"  - [中] {suggestion_text}")
                    else:
                        self.output.info(f"  - [低] {suggestion_text}")
                else:
                    self.output.info(f"  - {s}")

        return 0