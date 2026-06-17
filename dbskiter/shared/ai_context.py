"""
shared/ai_context.py
AI上下文构建器 - 标准结构定义与工具函数

文件功能：
    - 定义AI输出的标准结构（AIOutput / AIEnvelope）
    - 自动从数据库推断业务上下文（workload_type / top_tables / qps_estimate）
    - 统一各模块的AI输出格式
    - 支持深度控制和敏感信息脱敏

主要类/函数：
    - AIOutput: AI输出标准数据结构
    - AIEnvelope: AI输出信封（含元信息）
    - AutoContextDetector: 自动业务上下文推断器
    - AIContextBuilder: AI上下文构建器
    - AIOutputFormatter: AI输出格式化器

版本: 1.1.0
作者: dbskiter team
创建时间: 2026-04-28
最后修改: 2026-04-28
"""

import json
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field

from .sql_dialect import SQLDialectManager

logger = logging.getLogger(__name__)

SCHEMA_VERSION = "1.0"

AI_DEPTH_SUMMARY = "summary"
AI_DEPTH_DETAIL = "detail"
AI_DEPTH_FULL = "full"
AI_DEPTH_CHOICES = [AI_DEPTH_SUMMARY, AI_DEPTH_DETAIL, AI_DEPTH_FULL]


@dataclass
class AIOutput:
    """
    AI输出标准结构

    所有模块的 --output-mode=ai 输出统一遵循此结构

    属性:
        raw_metrics: 原始采集数据（指标值、执行计划、慢查询列表等）
        rule_flags: 规则初筛标记（flag + reason，仅做标记不做结论）
        context: 业务上下文信息（数据库类型、版本、工作负载等）
        reference_values: 参考基线/行业标准
        ai_hints: AI分析提示（建议关注方向、关联查询命令）

    使用示例:
        >>> output = AIOutput(
        ...     raw_metrics={"cpu_usage": 85.2},
        ...     rule_flags={"cpu_high": {"flagged": True, "reason": "CPU > 80%"}},
        ...     context={"database_type": "mysql"},
        ... )
        >>> output.to_dict()
    """
    raw_metrics: Dict[str, Any] = field(default_factory=dict)
    rule_flags: Dict[str, Any] = field(default_factory=dict)
    context: Dict[str, Any] = field(default_factory=dict)
    reference_values: Dict[str, Any] = field(default_factory=dict)
    ai_hints: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """
        转换为字典格式

        返回:
            Dict[str, Any]: 标准字典输出
        """
        return {
            "raw_metrics": self.raw_metrics,
            "rule_flags": self.rule_flags,
            "context": self.context,
            "reference_values": self.reference_values,
            "ai_hints": self.ai_hints,
        }


@dataclass
class AIEnvelope:
    """
    AI输出信封（包含元信息）

    包裹 AIOutput，增加 schema_version / collected_at / instance_id 等元信息

    属性:
        schema_version: 输出结构版本号
        collected_at: 数据采集时间（ISO 8601）
        instance_id: 数据库实例标识
        data_source: 数据来源信息
        data: AIOutput 标准数据

    使用示例:
        >>> envelope = AIEnvelope(
        ...     instance_id="mysql-prod-01",
        ...     data_source={"type": "mysql", "version": "8.0.32"},
        ...     data=ai_output,
        ... )
        >>> envelope.to_dict()
    """
    schema_version: str = SCHEMA_VERSION
    collected_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    instance_id: str = ""
    data_source: Dict[str, Any] = field(default_factory=dict)
    data: AIOutput = field(default_factory=AIOutput)

    def to_dict(self) -> Dict[str, Any]:
        """
        转换为字典格式

        返回:
            Dict[str, Any]: 包含元信息的完整输出
        """
        return {
            "schema_version": self.schema_version,
            "collected_at": self.collected_at,
            "instance_id": self.instance_id,
            "data_source": self.data_source,
            "data": (
                self.data.to_dict()
                if isinstance(self.data, AIOutput)
                else self.data
            ),
        }


class AutoContextDetector:
    """
    自动业务上下文推断器

    直接从数据库查询推断业务上下文，无需用户手动配置。
    推断逻辑：
        - workload_type: 根据查询模式（短事务多=OLTP，长查询多=OLAP）
        - top_tables: 按行数/查询频率排序的热点表
        - qps_estimate: 基于Com_*统计的QPS估算
        - connection_pattern: 连接数模式（连接池/直连/混合）

    使用示例:
        >>> detector = AutoContextDetector(connector)
        >>> ctx = detector.detect()
        >>> print(ctx["workload_type"])
        'oltp'
        >>> print(ctx["top_tables"])
        ['orders', 'users', 'payments']
    """

    def __init__(self, connector):
        """
        初始化推断器

        参数:
            connector: 数据库连接器（UnifiedConnector实例）
        """
        self.connector = connector
        self.dialect = getattr(connector, "dialect", "unknown").lower()
        self._cache: Optional[Dict[str, Any]] = None

    def detect(self) -> Dict[str, Any]:
        """
        执行自动推断，返回业务上下文

        返回:
            Dict[str, Any]: 业务上下文字典
        """
        if self._cache is not None:
            return self._cache

        context: Dict[str, Any] = {}

        try:
            context["workload_type"] = self._detect_workload_type()
        except Exception as e:
            logger.debug(f"推断workload_type失败: {e}")
            context["workload_type"] = "unknown"

        try:
            context["top_tables"] = self._detect_top_tables()
        except Exception as e:
            logger.debug(f"推断top_tables失败: {e}")
            context["top_tables"] = []

        try:
            context["qps_estimate"] = self._detect_qps()
        except Exception as e:
            logger.debug(f"推断qps_estimate失败: {e}")
            context["qps_estimate"] = None

        try:
            context["connection_pattern"] = self._detect_connection_pattern()
        except Exception as e:
            logger.debug(f"推断connection_pattern失败: {e}")
            context["connection_pattern"] = "unknown"

        try:
            context["buffer_pool_usage"] = self._detect_buffer_pool_usage()
        except Exception as e:
            logger.debug(f"推断buffer_pool_usage失败: {e}")
            context["buffer_pool_usage"] = None

        self._cache = context
        return context

    def _detect_workload_type(self) -> str:
        """
        推断工作负载类型

        判断逻辑：
        - 查询平均执行时间 < 50ms 且事务多 -> OLTP
        - 查询平均执行时间 > 1s 且扫描行数多 -> OLAP
        - 介于两者之间 -> mixed

        返回:
            str: oltp / olap / mixed / unknown
        """
        if "mysql" in self.dialect:
            return self._detect_mysql_workload()
        elif "oracle" in self.dialect:
            return self._detect_oracle_workload()
        elif "postgresql" in self.dialect:
            return self._detect_pg_workload()
        return "unknown"

    def _detect_mysql_workload(self) -> str:
        """
        MySQL工作负载推断

        返回:
            str: 工作负载类型
        """
        try:
            result = self.connector.execute(
                "SHOW GLOBAL STATUS WHERE Variable_name IN "
                "('Com_select','Com_insert','Com_update','Com_delete',"
                "'Com_replace','Slow_queries','Queries','Connections')"
            )
            stats = {}
            if result and hasattr(result, "rows"):
                for row in result.rows:
                    stats[row[0]] = int(row[1]) if row[1] else 0

            total_dml = (
                stats.get("Com_insert", 0)
                + stats.get("Com_update", 0)
                + stats.get("Com_delete", 0)
                + stats.get("Com_replace", 0)
            )
            total_select = stats.get("Com_select", 0)
            slow_queries = stats.get("Slow_queries", 0)
            total_queries = stats.get("Queries", 1)

            if total_queries == 0:
                return "unknown"

            write_ratio = total_dml / total_queries if total_queries else 0
            slow_ratio = slow_queries / total_queries if total_queries else 0

            if slow_ratio > 0.1:
                return "olap"
            elif write_ratio > 0.3:
                return "oltp"
            else:
                return "mixed"
        except Exception as e:
            logger.debug(f"MySQL workload推断失败: {e}")
            return "unknown"

    def _detect_oracle_workload(self) -> str:
        """
        Oracle工作负载推断

        返回:
            str: 工作负载类型
        """
        try:
            result = self.connector.execute(
                "SELECT name, value FROM v$sysstat "
                "WHERE name IN ('execute count','user commits','user rollbacks') "
                "ORDER BY name"
            )
            stats = {}
            if result and hasattr(result, "rows"):
                for row in result.rows:
                    stats[row[0]] = float(row[1]) if row[1] else 0

            commits = stats.get("user commits", 0)
            rollbacks = stats.get("user rollbacks", 0)
            total_txn = commits + rollbacks

            if total_txn > 1000:
                return "oltp"
            elif total_txn > 100:
                return "mixed"
            else:
                return "olap"
        except Exception as e:
            logger.debug(f"Oracle workload推断失败: {e}")
            return "unknown"

    def _detect_pg_workload(self) -> str:
        """
        PostgreSQL工作负载推断

        使用pg_stat_database和pg_stat_user_tables推断工作负载类型
        pg_stat_database包含事务统计，pg_stat_user_tables包含DML统计

        返回:
            str: 工作负载类型 (oltp/mixed/olap/unknown)
        """
        try:
            # 获取事务统计
            result = self.connector.execute(
                "SELECT SUM(xact_commit + xact_rollback) AS total_txn "
                "FROM pg_stat_database"
            )
            if not (result and hasattr(result, "rows") and result.rows):
                return "unknown"

            total_txn = float(result.rows[0][0]) if result.rows[0][0] else 0

            # 获取DML统计（从pg_stat_user_tables，因为pg_stat_database没有n_tup_*列）
            total_dml = 0
            try:
                dml_result = self.connector.execute(
                    "SELECT SUM(n_tup_ins + n_tup_upd + n_tup_del) AS total_dml "
                    "FROM pg_stat_user_tables"
                )
                if dml_result and hasattr(dml_result, "rows") and dml_result.rows:
                    total_dml = float(dml_result.rows[0][0]) if dml_result.rows[0][0] else 0
            except Exception:
                # 如果pg_stat_user_tables查询失败，使用事务数推断
                total_dml = total_txn * 10  # 估算值

            # 根据事务数和DML操作推断工作负载类型
            if total_txn > 10000 and total_dml > 5000:
                return "oltp"
            elif total_txn > 1000:
                return "mixed"
            else:
                return "olap"
        except Exception as e:
            logger.debug(f"PostgreSQL workload推断失败: {e}")
        return "unknown"

    def _detect_top_tables(self, limit: int = 10) -> List[str]:
        """
        推断热点表（按行数排序）

        参数:
            limit: 返回数量上限

        返回:
            List[str]: 表名列表
        """
        if "mysql" in self.dialect:
            return self._detect_mysql_top_tables(limit)
        elif "oracle" in self.dialect:
            return self._detect_oracle_top_tables(limit)
        elif "postgresql" in self.dialect:
            return self._detect_pg_top_tables(limit)
        return []

    def _detect_mysql_top_tables(self, limit: int) -> List[str]:
        """
        MySQL热点表推断

        参数:
            limit: 返回数量上限

        返回:
            List[str]: 表名列表
        """
        try:
            result = self.connector.execute(
                "SELECT TABLE_NAME, TABLE_ROWS "
                "FROM information_schema.TABLES "
                "WHERE TABLE_SCHEMA = DATABASE() "
                "AND TABLE_TYPE = 'BASE TABLE' "
                "ORDER BY TABLE_ROWS DESC "
                f"LIMIT {limit}"
            )
            if result and hasattr(result, "rows"):
                return [row[0] for row in result.rows if row[0]]
        except Exception as e:
            logger.debug(f"MySQL top_tables推断失败: {e}")
        return []

    def _detect_oracle_top_tables(self, limit: int) -> List[str]:
        """
        Oracle热点表推断

        参数:
            limit: 返回数量上限

        返回:
            List[str]: 表名列表
        """
        try:
            # 使用方言管理器生成兼容的SQL
            dialect_mgr = SQLDialectManager("oracle")
            base_sql = (
                "SELECT table_name, num_rows "
                "FROM dba_tables "
                "WHERE owner = SYS_CONTEXT('USERENV', 'CURRENT_SCHEMA') "
                "AND num_rows IS NOT NULL "
                "ORDER BY num_rows DESC"
            )
            sql = dialect_mgr.get_limit_sql(base_sql, limit)
            result = self.connector.execute(sql)
            if result and hasattr(result, "rows"):
                return [row[0] for row in result.rows if row[0]]
        except Exception as e:
            logger.debug(f"Oracle top_tables推断失败: {e}")
        return []

    def _detect_pg_top_tables(self, limit: int) -> List[str]:
        """
        PostgreSQL热点表推断

        参数:
            limit: 返回数量上限

        返回:
            List[str]: 表名列表
        """
        try:
            result = self.connector.execute(
                "SELECT relname, n_live_tup "
                "FROM pg_stat_user_tables "
                "ORDER BY n_live_tup DESC "
                f"LIMIT {limit}"
            )
            if result and hasattr(result, "rows"):
                return [row[0] for row in result.rows if row[0]]
        except Exception as e:
            logger.debug(f"PostgreSQL top_tables推断失败: {e}")
        return []

    def _detect_qps(self) -> Optional[int]:
        """
        估算当前QPS

        返回:
            Optional[int]: QPS估算值
        """
        if "mysql" in self.dialect:
            return self._detect_mysql_qps()
        elif "oracle" in self.dialect:
            return self._detect_oracle_qps()
        return None

    def _detect_mysql_qps(self) -> Optional[int]:
        """
        MySQL QPS估算

        返回:
            Optional[int]: QPS估算值
        """
        try:
            result = self.connector.execute(
                "SHOW GLOBAL STATUS WHERE Variable_name = 'Queries'"
            )
            if result and hasattr(result, "rows") and result.rows:
                q1 = int(result.rows[0][1])

                import time
                time.sleep(1)

                result2 = self.connector.execute(
                    "SHOW GLOBAL STATUS WHERE Variable_name = 'Queries'"
                )
                if result2 and hasattr(result2, "rows") and result2.rows:
                    q2 = int(result2.rows[0][1])
                    return max(0, q2 - q1)
        except Exception as e:
            logger.debug(f"MySQL QPS估算失败: {e}")
        return None

    def _detect_oracle_qps(self) -> Optional[int]:
        """
        Oracle QPS估算

        返回:
            Optional[int]: QPS估算值
        """
        try:
            result = self.connector.execute(
                "SELECT value FROM v$sysstat WHERE name = 'execute count'"
            )
            if result and hasattr(result, "rows") and result.rows:
                q1 = float(result.rows[0][0])

                import time
                time.sleep(1)

                result2 = self.connector.execute(
                    "SELECT value FROM v$sysstat WHERE name = 'execute count'"
                )
                if result2 and hasattr(result2, "rows") and result2.rows:
                    q2 = float(result2.rows[0][0])
                    return max(0, int(q2 - q1))
        except Exception as e:
            logger.debug(f"Oracle QPS估算失败: {e}")
        return None

    def _detect_connection_pattern(self) -> str:
        """
        推断连接模式

        判断逻辑：
        - 连接数少但每个连接查询多 -> 连接池模式
        - 连接数多但每个连接查询少 -> 直连模式
        - 介于两者之间 -> 混合模式

        返回:
            str: connection_pool / direct / mixed / unknown
        """
        if "mysql" in self.dialect:
            return self._detect_mysql_connection_pattern()
        return "unknown"

    def _detect_mysql_connection_pattern(self) -> str:
        """
        MySQL连接模式推断

        返回:
            str: 连接模式
        """
        try:
            result = self.connector.execute(
                "SHOW GLOBAL STATUS WHERE Variable_name IN "
                "('Threads_connected','Connections','Queries')"
            )
            stats = {}
            if result and hasattr(result, "rows"):
                for row in result.rows:
                    stats[row[0]] = int(row[1]) if row[1] else 0

            threads_connected = stats.get("Threads_connected", 0)
            total_connections = stats.get("Connections", 1)
            total_queries = stats.get("Queries", 0)

            if total_connections == 0 or threads_connected == 0:
                return "unknown"

            queries_per_conn = total_queries / total_connections

            if threads_connected < 20 and queries_per_conn > 100:
                return "connection_pool"
            elif threads_connected > 50:
                return "direct"
            else:
                return "mixed"
        except Exception as e:
            logger.debug(f"MySQL连接模式推断失败: {e}")
            return "unknown"

    def _detect_buffer_pool_usage(self) -> Optional[Dict[str, Any]]:
        """
        推断Buffer Pool使用情况

        返回:
            Optional[Dict[str, Any]]: Buffer Pool使用信息
        """
        if "mysql" not in self.dialect:
            return None

        try:
            result = self.connector.execute(
                "SHOW GLOBAL STATUS WHERE Variable_name IN "
                "('Innodb_buffer_pool_pages_total','Innodb_buffer_pool_pages_data',"
                "'Innodb_buffer_pool_read_requests','Innodb_buffer_pool_reads')"
            )
            stats = {}
            if result and hasattr(result, "rows"):
                for row in result.rows:
                    stats[row[0]] = int(row[1]) if row[1] else 0

            total_pages = stats.get("Innodb_buffer_pool_pages_total", 0)
            data_pages = stats.get("Innodb_buffer_pool_pages_data", 0)
            read_requests = stats.get("Innodb_buffer_pool_read_requests", 0)
            disk_reads = stats.get("Innodb_buffer_pool_reads", 0)

            if total_pages == 0:
                return None

            usage_pct = round(data_pages / total_pages * 100, 1) if total_pages else 0
            hit_rate = (
                round((1 - disk_reads / read_requests) * 100, 1)
                if read_requests > 0
                else 100.0
            )

            return {
                "usage_percent": usage_pct,
                "hit_rate_percent": hit_rate,
            }
        except Exception as e:
            logger.debug(f"Buffer Pool推断失败: {e}")
            return None


class AIContextBuilder:
    """
    AI上下文构建器

    使用AutoContextDetector自动推断业务上下文，
    构建数据库画像和AI分析提示

    使用示例:
        >>> builder = AIContextBuilder(dialect="mysql", database_name="jump")
        >>> profile = builder.build_database_profile(connector)
        >>> hints = builder.build_ai_hints(
        ...     focus_areas=["slow_query"],
        ...     related_commands=["dbskiter diagnose slow-queries"],
        ... )
    """

    def __init__(self, dialect: str, database_name: str = ""):
        """
        初始化上下文构建器

        参数:
            dialect: 数据库方言 (mysql/oracle/postgresql)
            database_name: 数据库名称/别名
        """
        self.dialect = dialect
        self.database_name = database_name
        self._auto_context: Optional[Dict[str, Any]] = None

    def detect_business_context(self, connector) -> Dict[str, Any]:
        """
        自动推断业务上下文

        参数:
            connector: 数据库连接器

        返回:
            Dict[str, Any]: 业务上下文字典
        """
        if self._auto_context is not None:
            return self._auto_context

        if connector is None:
            self._auto_context = {}
            return self._auto_context

        detector = AutoContextDetector(connector)
        self._auto_context = detector.detect()
        return self._auto_context

    def build_database_profile(self, connector=None) -> Dict[str, Any]:
        """
        构建数据库画像

        参数:
            connector: 数据库连接器（可选）

        返回:
            Dict[str, Any]: 数据库画像信息
        """
        profile: Dict[str, Any] = {
            "database_type": self.dialect,
            "version": "unknown",
            "workload_type": "unknown",
        }

        if connector:
            profile["version"] = self._get_version(connector)

            auto_ctx = self.detect_business_context(connector)
            if auto_ctx:
                profile["workload_type"] = auto_ctx.get("workload_type", "unknown")
                profile["top_tables"] = auto_ctx.get("top_tables", [])
                if auto_ctx.get("qps_estimate") is not None:
                    profile["qps_estimate"] = auto_ctx["qps_estimate"]
                if auto_ctx.get("connection_pattern"):
                    profile["connection_pattern"] = auto_ctx["connection_pattern"]
                if auto_ctx.get("buffer_pool_usage"):
                    profile["buffer_pool_usage"] = auto_ctx["buffer_pool_usage"]

        return profile

    def build_data_source(self, connector=None) -> Dict[str, Any]:
        """
        构建数据来源信息

        参数:
            connector: 数据库连接器（可选）

        返回:
            Dict[str, Any]: 数据来源信息
        """
        source: Dict[str, Any] = {
            "type": self.dialect,
            "version": "unknown",
            "collection_method": "direct_connection",
        }

        if connector:
            source["version"] = self._get_version(connector)
            if hasattr(connector, "connection_type"):
                source["collection_method"] = connector.connection_type

        return source

    def build_ai_hints(
        self,
        focus_areas: List[str],
        related_commands: List[str],
        additional_notes: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        构建AI分析提示

        参数:
            focus_areas: 建议AI关注的方向
            related_commands: 关联查询命令
            additional_notes: 附加说明

        返回:
            Dict[str, Any]: AI提示信息
        """
        hints: Dict[str, Any] = {
            "focus_areas": focus_areas,
            "related_commands": related_commands,
        }
        if additional_notes:
            hints["additional_notes"] = additional_notes
        return hints

    def build_rule_flags(
        self, flags: Dict[str, Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        构建规则初筛标记

        参数:
            flags: 规则标记字典

        返回:
            Dict[str, Any]: 规则标记，附带免责声明

        使用示例:
            >>> builder.build_rule_flags({
            ...     "full_table_scan": {"flagged": True, "reason": "type=ALL"},
            ... })
        """
        return {
            "_disclaimer": "rule_flags are preliminary, verify with full context",
            "flags": flags,
        }

    def build_reference_values(
        self, references: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        构建参考基线

        参数:
            references: 参考值字典

        返回:
            Dict[str, Any]: 参考基线信息
        """
        return references

    def _get_version(self, connector) -> str:
        """
        获取数据库版本

        参数:
            connector: 数据库连接器

        返回:
            str: 版本号字符串
        """
        try:
            if hasattr(connector, "execute"):
                # 获取方言，优先从connector获取，否则使用实例的dialect
                dialect = getattr(connector, 'dialect', '')
                if not dialect:
                    dialect = getattr(self, 'dialect', '')

                # 使用方言管理器获取版本查询SQL
                dialect_mgr = SQLDialectManager(dialect)
                sql = dialect_mgr.get_version_sql()
                result = connector.execute(sql)
                if result and hasattr(result, "rows") and result.rows:
                    row = result.rows[0]
                    return str(row[0]) if isinstance(row, (list, tuple)) else str(row)
        except Exception as e:
            logger.debug(f"获取版本失败: {e}")
        return "unknown"


class AIOutputFormatter:
    """
    AI输出格式化器

    将各模块的原始结果转换为标准AI输出格式

    使用示例:
        >>> formatter = AIOutputFormatter(
        ...     dialect="mysql",
        ...     database_name="jump",
        ... )
        >>> envelope = formatter.format_envelope(
        ...     raw_metrics={"cpu": 85},
        ...     rule_flags={"cpu_high": {"flagged": True, "reason": ">80%"}},
        ...     context={"database_type": "mysql"},
        ... )
        >>> print(json.dumps(envelope, indent=2, ensure_ascii=False))
    """

    def __init__(
        self,
        dialect: str,
        database_name: str = "",
        ai_depth: str = AI_DEPTH_DETAIL,
        mask_sensitive: bool = True,
    ):
        """
        初始化格式化器

        参数:
            dialect: 数据库方言
            database_name: 数据库名称
            ai_depth: 输出详细程度 (summary/detail/full)
            mask_sensitive: 是否脱敏敏感信息
        """
        self.dialect = dialect
        self.database_name = database_name
        self.ai_depth = ai_depth
        self.mask_sensitive = mask_sensitive
        self._context_builder = AIContextBuilder(dialect, database_name)

    def format(
        self,
        raw_metrics: Dict[str, Any],
        rule_flags: Dict[str, Any],
        context: Dict[str, Any],
        reference_values: Optional[Dict[str, Any]] = None,
        ai_hints: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        格式化为AI输出

        参数:
            raw_metrics: 原始采集数据
            rule_flags: 规则初筛标记
            context: 业务上下文
            reference_values: 参考基线
            ai_hints: AI分析提示

        返回:
            Dict[str, Any]: AIOutput 标准字典
        """
        output = AIOutput(
            raw_metrics=self._apply_depth_filter(raw_metrics),
            rule_flags=rule_flags,
            context=self._mask_if_needed(context),
            reference_values=reference_values or {},
            ai_hints=ai_hints or {},
        )
        return output.to_dict()

    def format_envelope(
        self,
        raw_metrics: Dict[str, Any],
        rule_flags: Dict[str, Any],
        context: Dict[str, Any],
        reference_values: Optional[Dict[str, Any]] = None,
        ai_hints: Optional[Dict[str, Any]] = None,
        connector=None,
    ) -> Dict[str, Any]:
        """
        格式化为完整信封（含元信息）

        参数:
            raw_metrics: 原始采集数据
            rule_flags: 规则初筛标记
            context: 业务上下文
            reference_values: 参考基线
            ai_hints: AI分析提示
            connector: 数据库连接器（用于获取版本等）

        返回:
            Dict[str, Any]: AIEnvelope 完整字典
        """
        output = AIOutput(
            raw_metrics=self._apply_depth_filter(raw_metrics),
            rule_flags=rule_flags,
            context=self._mask_if_needed(context),
            reference_values=reference_values or {},
            ai_hints=ai_hints or {},
        )

        envelope = AIEnvelope(
            instance_id=self.database_name or self.dialect,
            data_source=self._context_builder.build_data_source(connector),
            data=output,
        )
        return envelope.to_dict()

    def format_from_skill_result(
        self,
        skill_result: Dict[str, Any],
        context_builder: Optional[AIContextBuilder] = None,
        connector=None,
    ) -> Dict[str, Any]:
        """
        从Skill返回结果转换为AI输出（自动融入 inspection_trace）

        参数:
            skill_result: Skill返回的原始结果
            context_builder: 上下文构建器（可选）
            connector: 数据库连接器（可选）

        返回:
            Dict[str, Any]: AIEnvelope 完整字典
        """
        data = skill_result.get("data", {})

        raw_metrics = self._extract_raw_metrics(data)
        rule_flags = self._extract_rule_flags(data)
        context = self._extract_context(data, context_builder, connector)
        reference_values = self._extract_reference_values(data)
        ai_hints = self._extract_ai_hints(data)

        # 自动融入 inspection_trace 到 AI 提示中
        inspection_trace = skill_result.get("inspection_trace") or data.get("inspection_trace")
        if inspection_trace:
            ai_hints = self._merge_inspection_trace_into_hints(ai_hints, inspection_trace)

        return self.format_envelope(
            raw_metrics=raw_metrics,
            rule_flags=rule_flags,
            context=context,
            reference_values=reference_values,
            ai_hints=ai_hints,
            connector=connector,
        )

    def _extract_raw_metrics(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        从Skill结果中提取原始指标

        参数:
            data: Skill返回的data字段

        返回:
            Dict[str, Any]: 原始指标字典
        """
        if "raw_metrics" in data:
            return data["raw_metrics"]
        return data

    def _extract_rule_flags(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        从Skill结果中提取规则标记

        参数:
            data: Skill返回的data字段

        返回:
            Dict[str, Any]: 规则标记字典
        """
        if "rule_flags" in data:
            return data["rule_flags"]

        flags = {}
        issues = data.get("issues", [])
        for issue in issues:
            name = issue.get("name", issue.get("type", "unknown"))
            flags[name] = {
                "flagged": True,
                "level": issue.get("level", issue.get("risk_level", "unknown")),
                "reason": issue.get("reason", issue.get("description", "")),
            }
        return (
            {"_disclaimer": "rule_flags are preliminary, verify with full context", "flags": flags}
            if flags
            else {}
        )

    def _extract_context(
        self,
        data: Dict[str, Any],
        context_builder: Optional[AIContextBuilder] = None,
        connector=None,
    ) -> Dict[str, Any]:
        """
        从Skill结果中提取上下文

        参数:
            data: Skill返回的data字段
            context_builder: 上下文构建器
            connector: 数据库连接器

        返回:
            Dict[str, Any]: 上下文字典
        """
        if "context" in data:
            return data["context"]

        builder = context_builder or self._context_builder
        ctx = builder.build_database_profile(connector)

        if "database_type" in data:
            ctx["database_type"] = data["database_type"]
        if "version" in data:
            ctx["version"] = data["version"]

        return ctx

    def _extract_reference_values(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        从Skill结果中提取参考值

        参数:
            data: Skill返回的data字段

        返回:
            Dict[str, Any]: 参考值字典
        """
        if "reference_values" in data:
            return data["reference_values"]
        return {}

    def _extract_ai_hints(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        从Skill结果中提取AI提示

        参数:
            data: Skill返回的data字段

        返回:
            Dict[str, Any]: AI提示字典
        """
        if "ai_hints" in data:
            return data["ai_hints"]
        return {}

    def _merge_inspection_trace_into_hints(
        self,
        ai_hints: Dict[str, Any],
        inspection_trace: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        将 inspection_trace 融入 AI 提示

        让 AI 了解数据来源、可信度和检查范围，从而生成更精准的分析建议。

        参数:
            ai_hints: 原始 AI 提示
            inspection_trace: 追踪信息

        返回:
            Dict[str, Any]: 融合后的 AI 提示
        """
        if not ai_hints:
            ai_hints = {}

        # 数据来源和可信度提示
        data_sources = inspection_trace.get("data_sources", [])
        confidence = inspection_trace.get("confidence", "unknown")
        metrics = inspection_trace.get("metrics_checked", [])
        notes = inspection_trace.get("notes", [])

        # 构建数据质量说明
        quality_notes = []
        if confidence == "low":
            quality_notes.append(
                "【数据质量警告】本次诊断数据可信度为 LOW，" +
                "建议谨慎对待分析结论，必要时人工验证。"
            )
        elif confidence == "medium":
            quality_notes.append(
                "【数据质量提示】本次诊断数据可信度为 MEDIUM，" +
                "部分数据可能不完整，分析结论仅供参考。"
            )

        # 数据来源说明
        if data_sources:
            quality_notes.append(
                f"【数据来源】本次分析基于以下数据源: {', '.join(data_sources)}。" +
                "AI 分析时应据此判断结论的适用范围。"
            )

        # 检查范围说明
        if metrics:
            metric_names = [m.get("name", "") for m in metrics]
            quality_notes.append(
                f"【检查范围】本次诊断检查了以下指标: {', '.join(metric_names)}。" +
                "未检查的维度可能存在盲区。"
            )

        # 特定场景备注
        if notes:
            for note in notes:
                quality_notes.append(f"【诊断备注】{note}")

        # 融入 ai_hints
        ai_hints["data_quality_context"] = {
            "confidence": confidence,
            "data_sources": data_sources,
            "metrics_checked": [m.get("name", "") for m in metrics],
            "quality_notes": quality_notes,
        }
        ai_hints["_system_prompt_addendum"] = "\n".join(quality_notes)

        return ai_hints

    def _apply_depth_filter(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        根据深度设置过滤数据

        summary: 只保留关键字段
        detail: 保留大部分字段（默认）
        full: 保留全部字段

        参数:
            data: 原始数据

        返回:
            Dict[str, Any]: 过滤后的数据
        """
        if self.ai_depth == AI_DEPTH_FULL:
            return data

        if self.ai_depth == AI_DEPTH_SUMMARY:
            return self._summarize(data)

        return data

    def _summarize(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        将数据精简为摘要

        对于列表只保留前3项，对于嵌套结构只保留第一层

        参数:
            data: 原始数据

        返回:
            Dict[str, Any]: 摘要数据
        """
        summary = {}
        for key, value in data.items():
            if isinstance(value, list):
                summary[key] = value[:3]
                if len(value) > 3:
                    summary[f"{key}_total"] = len(value)
            elif isinstance(value, dict):
                summary[key] = {k: "..." for k in list(value.keys())[:5]}
            else:
                summary[key] = value
        return summary

    def _mask_if_needed(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        按需脱敏敏感信息

        参数:
            data: 原始数据

        返回:
            Dict[str, Any]: 脱敏后的数据
        """
        if not self.mask_sensitive:
            return data

        SENSITIVE_KEYS = {
            "password", "passwd", "pwd", "secret", "token",
            "api_key", "apikey", "access_key", "private_key",
            "credential", "auth",
        }

        masked = {}
        for key, value in data.items():
            if key.lower() in SENSITIVE_KEYS:
                masked[key] = "***MASKED***"
            elif isinstance(value, dict):
                masked[key] = self._mask_if_needed(value)
            elif isinstance(value, list):
                masked[key] = [
                    self._mask_if_needed(item) if isinstance(item, dict) else item
                    for item in value
                ]
            else:
                masked[key] = value
        return masked
