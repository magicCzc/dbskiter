"""
P1 诊断处理器 - 中频场景

包含：connections, replication, slow-queries, recommend-indexes
"""

from typing import Dict

# 模块元数据：记录每个方法的子命令名
_ANALYZE_CONNECTIONS = "_analyze_connections"
_ANALYZE_SLOWLOG = "_analyze_slowlog"
_RECOMMEND_INDEXES = "_recommend_indexes"


class DiagnoseP1Mixin:
    """P1 中频诊断处理器"""

    # ==================== connections - 连接分析 ====================

    def _analyze_connections(self, skill) -> int:
        """连接分析"""
        result = skill.analyze_connections(show_idle=self.args.idle)
        self._last_skill_result = result

        if not result.get("success"):
            self.output.error(f"连接分析失败: {self._extract_error_message(result)}")
            return 1

        data = result.get("data", {})

        self.output.info("\n" + "=" * 60)
        self.output.info("连接分析结果")
        self.output.info("=" * 60)

        stats = data.get("statistics", {})
        self.output.info(f"\n[连接统计]")
        self.output.info(f"  最大连接数: {stats.get('max_connections', 'N/A')}")
        self.output.info(f"  当前连接: {stats.get('current', 'N/A')}")
        self.output.info(f"  活跃连接: {stats.get('active', 'N/A')}")
        self.output.info(f"  空闲连接: {stats.get('idle', 'N/A')}")
        self.output.info(f"  使用率: {stats.get('usage_percent', 0):.1f}%")

        if stats.get("usage_percent", 0) > 80:
            self.output.warning("  警告: 连接使用率超过80%，建议优化")

        if self.args.idle:
            idle_conns = data.get("idle_connections", [])
            if idle_conns:
                self.output.info(f"\n[空闲连接 TOP {len(idle_conns)}]")
                for c in idle_conns[:10]:
                    self.output.info(
                        f"  ID: {c.get('id')}, " f"用户: {c.get('user')}, " f"空闲: {c.get('idle_time', 0)}s"
                    )

        return 0

    # ==================== replication - 复制诊断 ====================

    def _replication_diagnose(self, skill) -> int:
        """复制诊断"""
        result = skill.analyze_replication()
        self._last_skill_result = result

        if not result.get("success"):
            self.output.error(f"复制诊断失败: {self._extract_error_message(result)}")
            return 1

        data = result.get("data", {})

        self.output.info("\n" + "=" * 60)
        self.output.info("复制诊断结果")
        self.output.info("=" * 60)

        status = data.get("status", {})
        is_master = status.get("is_master", False)
        is_slave = status.get("is_slave", False)

        if is_master:
            self.output.info("\n[主库状态]")
            self.output.info(f"  角色: Master")
            self.output.info(f"  Binlog: {status.get('binlog_enabled', False)}")
            self.output.info(f"  从库数: {status.get('slave_count', 0)}")

        if is_slave:
            self.output.info("\n[从库状态]")
            slave_status = data.get("slave_status", {})

            io_running = slave_status.get("io_running", "No")
            sql_running = slave_status.get("sql_running", "No")
            delay = slave_status.get("delay_seconds", 0)

            self.output.info(f"  IO线程: {io_running}")
            self.output.info(f"  SQL线程: {sql_running}")
            self.output.info(f"  延迟: {delay} 秒")

            if io_running != "Yes" or sql_running != "Yes":
                self.output.error("  错误: 复制线程未运行!")
            elif delay > 60:
                self.output.warning(f"  警告: 复制延迟超过60秒!")
            else:
                self.output.info("  状态: 正常")

        if not is_master and not is_slave:
            self.output.info("\n[复制状态]")
            self.output.info("  当前实例未配置主从复制")

        return 0

    # ==================== slow-queries - 历史慢查询 ====================

    def _analyze_slowlog(self, skill) -> int:
        """历史慢查询分析（支持实时和日志文件模式）"""
        log_file = getattr(self.args, "log_file", None)

        if log_file:
            self.output.info(f"\n分析慢查询日志文件: {log_file}")
            result = skill.analyze_slow_queries(
                min_time=self.args.min_time, log_file=log_file, since=getattr(self.args, "since", "24h")
            )
        else:
            result = skill.analyze_slow_queries(limit=self.args.limit, min_time=self.args.min_time)

        self._last_skill_result = result

        if not result.get("success"):
            self.output.error(f"慢查询分析失败: {self._extract_error_message(result)}")
            return 1

        data = result.get("data", {})

        if "summary" in data:
            return self._display_enhanced_report(data)

        queries = data.get("queries", [])

        self.output.info("\n" + "=" * 60)
        self.output.info(f"慢查询分析结果 (>{self.args.min_time}s)")
        self.output.info("=" * 60)

        if not queries:
            self.output.info(f"\n未发现慢查询（>{self.args.min_time}秒）")
            return 0

        self.output.info(f"\n共 {len(queries)} 条慢查询:\n")

        for i, q in enumerate(queries, 1):
            self.output.info(f"[{i}] SQL: {q.get('sql', '')[:80]}...")
            self.output.info(f"    执行时间: {q.get('query_time', 0):.3f}s")
            self.output.info(f"    扫描行数: {q.get('rows_examined', 0)}")
            self.output.info(f"    返回行数: {q.get('rows_sent', 0)}")
            self.output.info("")

        return 0

    def _display_enhanced_report(self, data: Dict) -> int:
        """显示增强版慢查询报告"""
        summary = data.get("summary", {})
        patterns = data.get("top_patterns", [])
        recommendations = data.get("recommendations", [])

        self.output.info("\n" + "=" * 70)
        self.output.info("慢查询分析报告（增强版）")
        self.output.info("=" * 70)

        self.output.info(f"\n【汇总统计】")
        self.output.info(f"  总查询数: {summary.get('total_queries', 0)}")
        self.output.info(f"  唯一模式: {summary.get('unique_patterns', 0)}")
        self.output.info(f"  总耗时: {summary.get('total_time', 0):.2f}秒")
        self.output.info(f"  平均耗时: {summary.get('avg_time', 0):.3f}秒")

        time_range = summary.get("time_range", [None, None])
        if time_range[0] and time_range[1]:
            self.output.info(f"  时间范围: {time_range[0]} ~ {time_range[1]}")

        if patterns:
            self.output.info(f"\n【TOP {len(patterns)} 查询模式】")
            for i, p in enumerate(patterns, 1):
                self.output.info(f"\n[{i}] 指纹: {p.get('fingerprint', '')[:60]}...")
                self.output.info(f"    SQL示例: {p.get('sql_pattern', '')[:80]}...")
                self.output.info(f"    执行次数: {p.get('count', 0)}")
                self.output.info(f"    总耗时: {p.get('total_time', 0):.2f}秒")
                self.output.info(f"    平均耗时: {p.get('avg_time', 0):.3f}秒")
                self.output.info(f"    P95耗时: {p.get('p95_time', 0):.3f}秒")
                self.output.info(f"    扫描行数: {p.get('rows_examined', 0)}")
                self.output.info(f"    返回行数: {p.get('rows_sent', 0)}")

        if recommendations:
            self.output.info(f"\n【优化建议】")
            for i, rec in enumerate(recommendations, 1):
                self.output.info(f"  {i}. {rec}")

        self.output.info("\n" + "=" * 70)
        return 0

    # ==================== recommend-indexes - 索引建议 ====================

    def _recommend_indexes(self, skill) -> int:
        """索引建议"""
        result = skill.recommend_indexes(table=self.args.table)
        self._last_skill_result = result

        if not result.get("success"):
            self.output.error(f"索引建议失败: {self._extract_error_message(result)}")
            return 1

        data = result.get("data", {})
        suggestions = data.get("suggestions", data.get("indexes", []))

        self.output.info("\n" + "=" * 60)
        self.output.info("索引建议")
        self.output.info("=" * 60)

        if not suggestions:
            self.output.info("\n暂无索引建议")
            return 0

        summary = data.get("summary", {})
        if summary:
            self.output.info(f"\n总计: {summary.get('total', len(suggestions))} 条建议")
            self.output.info(f"  高优先级: {summary.get('high_priority', 0)}")
            self.output.info(f"  中优先级: {summary.get('medium_priority', 0)}")
            self.output.info(f"  低优先级: {summary.get('low_priority', 0)}")

        type_labels = {
            "missing_index": "缺失索引",
            "redundant_index": "冗余索引",
            "unused_index": "未使用索引",
            "low_cardinality": "低基数索引",
            "low_selectivity": "低选择性索引",
        }

        priority_labels = {
            "high": "[高]",
            "medium": "[中]",
            "low": "[低]",
        }

        for i, s in enumerate(suggestions, 1):
            s_type = s.get("type", "unknown")
            type_label = type_labels.get(s_type, s_type)
            priority = s.get("priority", "low")
            priority_label = priority_labels.get(priority, f"[{priority}]")

            self.output.info(f"\n{i}. {priority_label} {type_label}")

            if s_type == "missing_index":
                sql_preview = s.get("sql_preview", "")
                sql_id = s.get("sql_id", "")
                elapsed = s.get("elapsed_sec", 0)
                executions = s.get("executions", 0)
                if sql_id:
                    self.output.info(f"   SQL ID: {sql_id}")
                if sql_preview:
                    self.output.info(f"   SQL: {sql_preview}")
                self.output.info(f"   耗时: {elapsed}秒, 执行次数: {executions}")
                self.output.info(f"   原因: {s.get('reason', '')}")
                self.output.info(f"   建议: {s.get('suggestion', '')}")

            elif s_type == "redundant_index":
                self.output.info(f"   表: {s.get('table', '')}")
                self.output.info(f"   索引: {s.get('index', '')}")
                self.output.info(f"   列: {s.get('columns', '')}")
                self.output.info(f"   原因: {s.get('reason', '')}")
                self.output.info(f"   建议: {s.get('suggestion', '')}")

            elif s_type in ("unused_index", "low_cardinality", "low_selectivity"):
                self.output.info(f"   表: {s.get('table', '')}")
                self.output.info(f"   索引: {s.get('index', '')}")
                if s.get("column"):
                    self.output.info(f"   列: {s.get('column')}")
                if s.get("distinct_keys") is not None:
                    self.output.info(f"   不同键数: {s.get('distinct_keys')}")
                if s.get("selectivity_percent") is not None:
                    self.output.info(f"   选择性: {s.get('selectivity_percent')}%")
                self.output.info(f"   原因: {s.get('reason', '')}")
                self.output.info(f"   建议: {s.get('suggestion', '')}")

            else:
                table_name = s.get("table", "")
                if table_name:
                    self.output.info(f"   表: {table_name}")
                self.output.info(f"   描述: {s.get('description', s.get('reason', ''))}")
                if s.get("suggestion"):
                    self.output.info(f"   建议: {s.get('suggestion')}")
                if s.get("sql"):
                    self.output.info(f"   SQL: {s.get('sql')}")

        return 0
