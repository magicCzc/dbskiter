"""
数据库特有诊断处理器

包含：
- PostgreSQL 特有: vacuum
- 多数据库支持: bloat, index-usage
- Oracle 特有: tablespace-fragmentation
"""


# 模块元数据：记录每个方法的子命令名
_ANALYZE_VACUUM = "_analyze_vacuum"
_ANALYZE_BLOAT = "_analyze_bloat"
_ANALYZE_INDEX_USAGE = "_analyze_index_usage"
_ANALYZE_TABLESPACE_FRAGMENTATION = "_analyze_tablespace_fragmentation"


class DiagnoseDbSpecificMixin:
    """数据库特有诊断处理器"""

    # ==================== vacuum - PostgreSQL VACUUM ====================

    def _analyze_vacuum(self, skill) -> int:
        """VACUUM状态分析（PostgreSQL特有）"""
        result = skill.analyze_vacuum()

        if not result.get('success'):
            self.output.error(f"VACUUM分析失败: {self._extract_error_message(result)}")
            return 1

        data = result.get('data', {})
        tables = data.get('tables_needing_vacuum', [])
        settings = data.get('autovacuum_settings', {})
        suggestions = data.get('suggestions', [])
        actionable_commands = data.get('actionable_commands', [])
        health_score = data.get('health_score', 0)
        vacuum_stats = data.get('vacuum_statistics', {})
        total_wasted = data.get('total_wasted_space', '0 B')

        self.output.info("\n" + "=" * 60)
        self.output.info("PostgreSQL VACUUM状态分析")
        self.output.info("=" * 60)

        # 健康评分
        self._print_health_score(health_score)

        # 评分扣分原因
        if health_score < 80:
            self._print_vacuum_deductions(tables, vacuum_stats)

        # 整体统计
        if vacuum_stats:
            self.output.info(f"\n[整体统计]")
            self.output.info(f"  总表数: {vacuum_stats.get('total_tables', 0)}")
            self.output.info(f"  活元组总数: {vacuum_stats.get('total_live_tuples', 0)}")
            self.output.info(f"  死元组总数: {vacuum_stats.get('total_dead_tuples', 0)}")
            self.output.info(f"  整体死元组比例: {vacuum_stats.get('overall_dead_ratio', 0)}%")
            self.output.info(f"  预计可回收空间: {total_wasted}")

        # Autovacuum配置
        if settings:
            self.output.info("\n[Autovacuum配置]")
            for key, value in settings.items():
                self.output.info(f"  {key}: {value}")

        # 需要VACUUM的表
        if tables:
            self.output.info(f"\n[需要关注的表] 共 {len(tables)} 个")
            for i, t in enumerate(tables[:10], 1):
                schema = t.get('schema') or 'public'
                table = t.get('table') or 'unknown'
                priority = t.get('priority', 'low')
                priority_marker = {'high': '[高]', 'medium': '[中]', 'low': '[低]'}.get(priority, '[低]')
                self.output.info(f"\n  [{i}] {priority_marker} {schema}.{table}")
                self.output.info(f"      表大小: {t.get('total_size', 'N/A')}")
                self.output.info(f"      活元组: {t.get('live_tuples', 0)}")
                self.output.info(f"      死元组: {t.get('dead_tuples', 0)}")
                self.output.info(f"      死元组比例: {t.get('dead_ratio', 0)}%")
                if t.get('wasted_space_bytes', 0) > 0:
                    wasted = t.get('wasted_space_bytes', 0)
                    wasted_str = f"{wasted / (1024**2):.2f} MB" if wasted >= 1024**2 else f"{wasted / 1024:.2f} KB"
                    self.output.info(f"      预计浪费空间: {wasted_str}")
                if t.get('last_autovacuum'):
                    self.output.info(f"      上次自动清理: {t.get('last_autovacuum')}")
                if t.get('last_vacuum'):
                    self.output.info(f"      上次手动清理: {t.get('last_vacuum')}")
        else:
            self.output.info("\n[需要关注的表] 无")

        # 建议
        self._print_suggestions(suggestions)

        # 可执行命令
        if actionable_commands:
            self.output.info("\n[推荐执行的VACUUM命令]")
            for cmd in actionable_commands[:5]:
                self.output.info(f"\n  优先级: {cmd.get('priority', 'low')}")
                self.output.info(f"  表: {cmd.get('table')}")
                self.output.info(f"  命令: {cmd.get('command')}")
                self.output.info(f"  说明: {cmd.get('description')}")

        return 0

    def _print_vacuum_deductions(self, tables, vacuum_stats):
        """输出 VACUUM 评分扣分原因"""
        deductions = []
        high_tables = [t for t in tables if t.get('priority') == 'high']
        if high_tables:
            deductions.append(f"  - {len(high_tables)} 个表死元组比例严重超标(-15分/个)")
        medium_tables = [t for t in tables if t.get('priority') == 'medium']
        if medium_tables:
            deductions.append(f"  - {len(medium_tables)} 个表死元组比例偏高(-8分/个)")
        total_dead = vacuum_stats.get('total_dead_tuples', 0)
        if total_dead > 100000:
            deductions.append(f"  - 死元组总数过多({total_dead}个)(-10分)")
        dead_ratio = vacuum_stats.get('overall_dead_ratio', 0)
        if dead_ratio > 20:
            deductions.append(f"  - 整体死元组比例过高({dead_ratio}%)(-10分)")
        if deductions:
            self.output.info("\n[评分说明] 主要扣分原因:")
            for d in deductions:
                self.output.info(d)

    # ==================== bloat - 表膨胀/碎片 ====================

    def _analyze_bloat(self, skill) -> int:
        """表膨胀/碎片分析"""
        result = skill.analyze_bloat()

        if not result.get('success'):
            self.output.error(f"膨胀分析失败: {self._extract_error_message(result)}")
            return 1

        data = result.get('data', {})
        tables = data.get('bloated_tables', [])
        severely_bloated = data.get('severely_bloated_count', 0)
        has_pgstattuple = data.get('has_pgstattuple', False)
        suggestions = data.get('suggestions', [])
        actionable_commands = data.get('actionable_commands', [])
        health_score = data.get('health_score', 0)
        total_wasted = data.get('total_wasted_space', '0 B')
        db_type = data.get('db_type', 'Unknown')

        self.output.info("\n" + "=" * 60)
        self.output.info(f"{db_type}表膨胀/碎片分析")
        self.output.info("=" * 60)

        self._print_health_score(health_score)

        if health_score < 80:
            self._print_bloat_deductions(severely_bloated, tables, total_wasted)

        self.output.info(f"\n[统计]")
        self.output.info(f"  需要关注的表: {len(tables)} 个")
        self.output.info(f"  严重膨胀(>30%): {severely_bloated} 个")
        self.output.info(f"  预计可回收空间: {total_wasted}")

        if db_type == "PostgreSQL":
            self.output.info(f"  pgstattuple扩展: {'已安装' if has_pgstattuple else '未安装'}")
            if not has_pgstattuple:
                self.output.info("\n  提示: 安装pgstattuple扩展可获得更准确的分析")
                self.output.info("        CREATE EXTENSION IF NOT EXISTS pgstattuple;")

        # 膨胀表详情
        if tables:
            self.output.info(f"\n[膨胀表详情] TOP {min(len(tables), 10)}")
            for i, t in enumerate(tables[:10], 1):
                bloat_ratio = t.get('bloat_ratio', 0) or t.get('estimated_bloat_ratio', 0)
                schema = t.get('schema') or 'public'
                table = t.get('table') or 'unknown'
                priority = t.get('priority', 'low')
                priority_marker = {'high': '[高]', 'medium': '[中]', 'low': '[低]'}.get(priority, '[低]')
                self.output.info(f"\n  [{i}] {priority_marker} {schema}.{table}")
                self.output.info(f"      总大小: {t.get('total_size', 'N/A')}")
                self.output.info(f"      膨胀率: {bloat_ratio:.1f}%")
                if t.get('wasted_space_bytes', 0) > 0:
                    wasted = t.get('wasted_space_bytes', 0)
                    wasted_str = f"{wasted / (1024**2):.2f} MB" if wasted >= 1024**2 else f"{wasted / 1024:.2f} KB"
                    self.output.info(f"      预计浪费空间: {wasted_str}")
                if t.get('dead_tuples'):
                    self.output.info(f"      死元组: {t.get('dead_tuples')}")
        else:
            self.output.info("\n[膨胀表详情] 未发现明显膨胀的表")

        # 建议
        self._print_suggestions(suggestions, extra_keys=('install_sql', 'note'))

        # 可执行命令
        if actionable_commands:
            self.output.info("\n[推荐执行的维护命令]")
            for cmd in actionable_commands[:3]:
                self.output.info(f"\n  优先级: {cmd.get('priority', 'low')}")
                self.output.info(f"  表: {cmd.get('table')}")
                self.output.info(f"  说明: {cmd.get('description')}")
                self.output.info(f"  命令:")
                for line in cmd.get('commands', []):
                    self.output.info(f"    {line}")

        return 0

    def _print_bloat_deductions(self, severely_bloated, tables, total_wasted):
        """输出 bloat 评分扣分原因"""
        deductions = []
        if severely_bloated > 0:
            deductions.append(f"  - {severely_bloated} 个表严重膨胀(>30%)(-15分/个)")
        medium_tables = [t for t in tables if t.get('priority') == 'medium']
        if medium_tables:
            deductions.append(f"  - {len(medium_tables)} 个表中度膨胀(10-30%)(-8分/个)")
        wasted_mb = 0
        if isinstance(total_wasted, str):
            if 'MB' in total_wasted:
                try:
                    wasted_mb = float(total_wasted.replace('MB', '').strip())
                except Exception:
                    pass
            elif 'GB' in total_wasted:
                try:
                    wasted_mb = float(total_wasted.replace('GB', '').strip()) * 1024
                except Exception:
                    pass
        if wasted_mb > 100:
            deductions.append(f"  - 可回收空间过大({total_wasted})(-10分)")
        if deductions:
            self.output.info("\n[评分说明] 主要扣分原因:")
            for d in deductions:
                self.output.info(d)

    # ==================== index-usage - 索引使用 ====================

    def _analyze_index_usage(self, skill) -> int:
        """索引使用分析"""
        result = skill.analyze_index_usage()

        if not result.get('success'):
            self.output.error(f"索引使用分析失败: {self._extract_error_message(result)}")
            return 1

        data = result.get('data', {})
        unused = data.get('unused_indexes', [])
        hot = data.get('hot_indexes', [])
        missing = data.get('tables_missing_index', [])
        duplicate = data.get('duplicate_indexes', [])
        redundant = data.get('redundant_indexes', [])
        invalid = data.get('invalid_indexes', [])
        suggestions = data.get('suggestions', [])
        actionable_commands = data.get('actionable_commands', [])
        health_score = data.get('health_score', 0)
        total_unused_size = data.get('total_unused_index_size', data.get('total_unused_index_size_mb', '0 B'))
        has_perf_schema = data.get('has_performance_schema')
        db_type = data.get('db_type', None)
        if not db_type:
            dialect_raw = data.get('dialect', '')
            db_type = dialect_raw.split('+')[0].title() if dialect_raw else 'Unknown'

        self.output.info("\n" + "=" * 60)
        self.output.info(f"{db_type}索引使用分析")
        self.output.info("=" * 60)

        self._print_health_score(health_score)

        if health_score < 80:
            self._print_index_usage_deductions(unused, missing, redundant, duplicate, invalid)

        self.output.info(f"\n[整体统计]")
        self.output.info(f"  未使用索引: {len(unused)} 个")
        self.output.info(f"  未使用索引占用: {total_unused_size}")
        self.output.info(f"  可能缺少索引的表: {len(missing)} 个")
        self.output.info(f"  重复索引: {len(duplicate)} 组")

        # 未使用索引
        if unused:
            self.output.info(f"\n[未使用索引] 共 {len(unused)} 个")
            for i, idx in enumerate(unused[:5], 1):
                priority = idx.get('priority', 'low')
                priority_marker = {'high': '[高]', 'medium': '[中]', 'low': '[低]'}.get(priority, '[低]')
                self.output.info(f"  [{i}] {priority_marker} {idx.get('table')}.{idx.get('index')}")
                self.output.info(f"      大小: {idx.get('size', 'N/A')}")
                if idx.get('size_bytes', 0) > 0:
                    size_mb = idx.get('size_bytes', 0) / (1024 * 1024)
                    self.output.info(f"      大小(MB): {size_mb:.2f}")

        # 高频使用索引
        if hot:
            self.output.info(f"\n[高频使用索引] TOP {min(len(hot), 5)}")
            for i, idx in enumerate(hot[:5], 1):
                self.output.info(f"  [{i}] {idx.get('table')}.{idx.get('index')}")
                self.output.info(f"      扫描次数: {idx.get('scans', 0)}")
                self.output.info(f"      读取元组: {idx.get('tuples_read', 0)}")
                self.output.info(f"      大小: {idx.get('size', 'N/A')}")

        # 可能缺少索引的表
        if missing:
            self.output.info(f"\n[可能缺少索引的表] 共 {len(missing)} 个")
            for i, t in enumerate(missing[:5], 1):
                schema = t.get('schema') or 'public'
                table = t.get('table') or 'unknown'
                priority = t.get('priority', 'low')
                priority_marker = {'high': '[高]', 'medium': '[中]', 'low': '[低]'}.get(priority, '[低]')
                self.output.info(f"  [{i}] {priority_marker} {schema}.{table}")
                self.output.info(f"      全表扫描: {t.get('seq_scans', 0)} 次")
                self.output.info(f"      索引扫描: {t.get('idx_scans', 0)} 次")
                self.output.info(f"      数据行数: {t.get('live_tuples', 0)}")

        # 重复索引
        if duplicate:
            self.output.info(f"\n[重复索引] 共 {len(duplicate)} 组")
            for i, dup in enumerate(duplicate[:3], 1):
                self.output.info(f"  [{i}] 表: {dup.get('table')}")
                self.output.info(f"      冗余索引: {dup.get('redundant_index')}")
                self.output.info(f"      保留索引: {dup.get('kept_index')}")

        # 冗余索引
        if redundant:
            self.output.info(f"\n[冗余索引] 共 {len(redundant)} 组")
            for i, idx in enumerate(redundant[:3], 1):
                self.output.info(f"  [{i}] 表: {idx.get('table')}")
                self.output.info(f"      冗余索引: {idx.get('redundant_index')}")
                self.output.info(f"      冗余列: {idx.get('redundant_columns')}")
                self.output.info(f"      保留索引: {idx.get('dominant_index')}")

        # 无效索引
        if invalid:
            self.output.info(f"\n[无效索引] 共 {len(invalid)} 个")
            for i, idx in enumerate(invalid[:5], 1):
                self.output.info(f"  [{i}] {idx.get('schema')}.{idx.get('index')}")
                self.output.info(f"      表: {idx.get('table')}")
                self.output.info(f"      状态: {idx.get('status')}")

        # Performance Schema 状态
        if has_perf_schema is not None:
            if has_perf_schema:
                self.output.info("\n[Performance Schema] 已启用")
            else:
                self.output.warning("\n[Performance Schema] 未启用，索引统计可能不完整")

        # 建议
        self._print_suggestions(suggestions)

        # 可执行命令
        if actionable_commands:
            self.output.info("\n[推荐执行的优化命令]")
            for cmd in actionable_commands[:5]:
                self.output.info(f"\n  优先级: {cmd.get('priority', 'low')}")
                self.output.info(f"  类型: {cmd.get('type', 'unknown')}")
                if cmd.get('index'):
                    self.output.info(f"  索引: {cmd.get('index')}")
                if cmd.get('table'):
                    self.output.info(f"  表: {cmd.get('table')}")
                if cmd.get('tablespace'):
                    self.output.info(f"  表空间: {cmd.get('tablespace')}")
                self.output.info(f"  说明: {cmd.get('description')}")
                if cmd.get('warning'):
                    self.output.warning(f"  警告: {cmd.get('warning')}")
                self.output.info(f"  命令:")
                for line in cmd.get('commands', []):
                    self.output.info(f"    {line}")

        return 0

    def _print_index_usage_deductions(self, unused, missing, redundant, duplicate, invalid):
        """输出 index_usage 评分扣分原因"""
        deductions = []
        high_unused = [idx for idx in unused if idx.get('priority') == 'high']
        if high_unused:
            deductions.append(f"  - {len(high_unused)} 个大体积未使用索引(-10分/个)")
        medium_unused = [idx for idx in unused if idx.get('priority') == 'medium']
        if medium_unused:
            deductions.append(f"  - {len(medium_unused)} 个小体积未使用索引(-5分/个)")
        high_missing = [t for t in missing if t.get('priority') == 'high']
        if high_missing:
            deductions.append(f"  - {len(high_missing)} 个表严重缺少索引(-15分/个)")
        medium_missing = [t for t in missing if t.get('priority') == 'medium']
        if medium_missing:
            deductions.append(f"  - {len(medium_missing)} 个表可能缺少索引(-8分/个)")
        if redundant:
            deductions.append(f"  - {len(redundant)} 组冗余索引(-5分/组)")
        if duplicate:
            deductions.append(f"  - {len(duplicate)} 组重复索引(-5分/组)")
        if invalid:
            deductions.append(f"  - {len(invalid)} 个无效索引(-20分/个)")
        if deductions:
            self.output.info("\n[评分说明] 主要扣分原因:")
            for d in deductions:
                self.output.info(d)

    # ==================== tablespace-fragmentation - Oracle ====================

    def _analyze_tablespace_fragmentation(self, skill) -> int:
        """表空间碎片分析（Oracle特有）"""
        result = skill.analyze_tablespace_fragmentation()

        if not result.get('success'):
            self.output.error(f"表空间碎片分析失败: {self._extract_error_message(result)}")
            return 1

        data = result.get('data', {})
        tablespaces = data.get('fragmented_tablespaces', [])
        suggestions = data.get('suggestions', [])
        actionable_commands = data.get('actionable_commands', [])
        health_score = data.get('health_score', 0)
        total_wasted = data.get('total_wasted_space_mb', 0)

        self.output.info("\n" + "=" * 60)
        self.output.info("Oracle表空间碎片分析")
        self.output.info("=" * 60)

        self._print_health_score(health_score)

        if health_score < 80:
            self._print_tablespace_deductions(tablespaces, total_wasted)

        self.output.info(f"\n[统计]")
        self.output.info(f"  需要关注的表空间: {len(tablespaces)} 个")
        self.output.info(f"  预计可回收空间: {total_wasted:.2f} MB")

        if tablespaces:
            self.output.info(f"\n[碎片表空间详情] TOP {min(len(tablespaces), 10)}")
            for i, t in enumerate(tablespaces[:10], 1):
                tablespace = t.get('tablespace', 'UNKNOWN')
                priority = t.get('priority', 'low')
                priority_marker = {'high': '[高]', 'medium': '[中]', 'low': '[低]'}.get(priority, '[低]')
                self.output.info(f"\n  [{i}] {priority_marker} {tablespace}")
                self.output.info(f"      总大小: {t.get('total_mb', 0):.2f} MB")
                self.output.info(f"      空闲空间: {t.get('free_space_mb', 0):.2f} MB ({t.get('free_percentage', 0):.1f}%)")
                self.output.info(f"      碎片数: {t.get('free_extents', 0)} 个")
                self.output.info(f"      碎片率: {t.get('fragmentation_ratio', 0):.1f}%")
                self.output.info(f"      平均碎片大小: {t.get('avg_extent_mb', 0):.2f} MB")
        else:
            self.output.info("\n[碎片表空间详情] 未发现明显碎片的表空间")

        # 建议（含 tablespaces 字段特殊处理）
        if suggestions:
            self.output.info("\n[建议]")
            for s in suggestions:
                msg_type = s.get('type', 'info')
                msg = s.get('message', '')
                if msg_type == 'critical':
                    self.output.error(f"  [严重] {msg}")
                elif msg_type == 'warning':
                    self.output.warning(f"  [警告] {msg}")
                else:
                    self.output.info(f"  [提示] {msg}")
                if s.get('impact'):
                    self.output.info(f"        影响: {s.get('impact')}")
                if s.get('tablespaces'):
                    self.output.info(f"        表空间: {', '.join(s.get('tablespaces', []))}")

        if actionable_commands:
            self.output.info("\n[推荐执行的优化命令]")
            for cmd in actionable_commands[:3]:
                self.output.info(f"\n  优先级: {cmd.get('priority', 'low')}")
                self.output.info(f"  表空间: {cmd.get('tablespace')}")
                self.output.info(f"  说明: {cmd.get('description')}")
                if cmd.get('warning'):
                    self.output.warning(f"  警告: {cmd.get('warning')}")
                self.output.info(f"  命令:")
                for line in cmd.get('commands', []):
                    self.output.info(f"    {line}")

        return 0

    def _print_tablespace_deductions(self, tablespaces, total_wasted):
        """输出 tablespace 评分扣分原因"""
        deductions = []
        high_ts = [t for t in tablespaces if t.get('priority') == 'high']
        if high_ts:
            deductions.append(f"  - {len(high_ts)} 个表空间严重碎片(-15分/个)")
        medium_ts = [t for t in tablespaces if t.get('priority') == 'medium']
        if medium_ts:
            deductions.append(f"  - {len(medium_ts)} 个表空间中度碎片(-8分/个)")
        if total_wasted > 1000:
            deductions.append(f"  - 可回收空间过大({total_wasted:.2f} MB)(-10分)")
        if deductions:
            self.output.info("\n[评分说明] 主要扣分原因:")
            for d in deductions:
                self.output.info(d)

    # ==================== 共享辅助方法 ====================

    def _print_health_score(self, health_score: int) -> None:
        """统一的健康评分输出"""
        if health_score >= 80:
            self.output.info(f"\n[健康评分] {health_score}/100 (良好)")
        elif health_score >= 60:
            self.output.warning(f"\n[健康评分] {health_score}/100 (一般)")
        else:
            self.output.error(f"\n[健康评分] {health_score}/100 (较差)")

    def _print_suggestions(self, suggestions, extra_keys=()) -> None:
        """统一的建议列表输出

        参数:
            suggestions: 建议列表
            extra_keys: 额外要显示的字段名（除 impact/fix_command/install_sql/note 之外）
        """
        if not suggestions:
            return
        self.output.info("\n[建议]")
        for s in suggestions:
            msg_type = s.get('type', 'info')
            msg = s.get('message', '')
            if msg_type == 'critical':
                self.output.error(f"  [严重] {msg}")
            elif msg_type == 'warning':
                self.output.warning(f"  [警告] {msg}")
            else:
                self.output.info(f"  [提示] {msg}")
            if s.get('impact'):
                self.output.info(f"        影响: {s.get('impact')}")
            if s.get('fix_command'):
                self.output.info(f"        修复命令: {s.get('fix_command')}")
            if s.get('install_sql'):
                self.output.info(f"        安装命令: {s.get('install_sql')}")
            if s.get('note'):
                self.output.info(f"        说明: {s.get('note')}")
            for key in extra_keys:
                if s.get(key):
                    label = {
                        'install_sql': '安装命令',
                        'note': '说明',
                    }.get(key, key)
                    self.output.info(f"        {label}: {s.get(key)}")