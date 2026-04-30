"""
MySQL慢查询采集器

文件功能：支持MySQL多版本（5.7/8.0）的慢查询采集
主要类：
    - MySQLSlowQueryCollector: 慢查询采集器
    - MySQLVersionDetector: 版本检测器
    - QueryResultFormatter: 结果格式化器
    - CollectionError: 采集错误分类

设计原则：
    1. 多版本兼容：自动检测版本，使用对应SQL
    2. 多级降级：performance_schema → processlist → 空结果
    3. 性能保护：限制查询频率，避免影响生产
    4. 统一输出：不同版本返回相同格式
    5. 错误分类：精细化错误处理，便于问题定位

支持的采集源：
    1. performance_schema.events_statements_summary_by_digest（推荐）
    2. mysql.slow_log（慢查询日志表）
    3. information_schema.PROCESSLIST（实时查询）

使用示例：
    from dbskiter.shared.mysql_slow_query_collector import MySQLSlowQueryCollector
    
    collector = MySQLSlowQueryCollector(connector)
    queries = collector.collect_slow_queries(limit=10)
    
    for query in queries:
        print(f"SQL: {query['sql'][:100]}")
        print(f"Time: {query['query_time']}s")
        print(f"Count: {query['count']}")
"""

import re
import time
import logging
from enum import Enum
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)


class ErrorCategory(Enum):
    """错误分类枚举"""
    CONNECTION_ERROR = "connection_error"  # 连接错误
    PERMISSION_ERROR = "permission_error"  # 权限错误
    CONFIGURATION_ERROR = "configuration_error"  # 配置错误
    TIMEOUT_ERROR = "timeout_error"  # 超时错误
    DATA_ERROR = "data_error"  # 数据错误
    UNKNOWN_ERROR = "unknown_error"  # 未知错误


@dataclass
class CollectionError:
    """
    采集错误信息
    
    属性:
        category: 错误分类
        message: 错误消息
        source: 错误来源（采集源）
        recoverable: 是否可恢复
        suggestion: 解决建议
        original_error: 原始异常
    """
    category: ErrorCategory
    message: str
    source: str
    recoverable: bool = True
    suggestion: str = ""
    original_error: Optional[Exception] = None
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'category': self.category.value,
            'message': self.message,
            'source': self.source,
            'recoverable': self.recoverable,
            'suggestion': self.suggestion,
            'timestamp': self.timestamp,
        }


@dataclass
class SlowQuery:
    """
    慢查询数据类
    
    属性:
        sql: SQL语句文本
        query_time: 平均执行时间（秒）
        count: 执行次数
        rows_sent: 返回行数
        rows_examined: 扫描行数
        first_seen: 首次出现时间
        last_seen: 最后出现时间
        database: 数据库名
        source: 数据来源
    """
    sql: str
    query_time: float
    count: int
    rows_sent: int
    rows_examined: int
    first_seen: Optional[str] = None
    last_seen: Optional[str] = None
    database: Optional[str] = None
    source: str = "unknown"


class MySQLVersionDetector:
    """
    MySQL版本检测器
    
    自动检测MySQL版本，用于选择兼容的SQL语句
    """
    
    def __init__(self, connector):
        self.connector = connector
        self._version: Optional[float] = None
        self._version_string: Optional[str] = None
        self._detected_features: Dict[str, bool] = {}
    
    def get_version(self) -> float:
        """
        获取MySQL版本号（主.次）
        
        返回:
            float: 版本号，如8.0、5.7
        """
        if self._version is not None:
            return self._version
        
        try:
            result = self.connector.execute("SELECT VERSION()")
            if result.rows and result.rows[0]:
                version_str = str(result.rows[0][0])
                self._version_string = version_str
                
                # 解析版本号（如 "8.0.25" -> 8.0）
                version_parts = version_str.split('.')
                if len(version_parts) >= 2:
                    self._version = float(f"{version_parts[0]}.{version_parts[1]}")
                else:
                    self._version = 5.7  # 默认
            else:
                self._version = 5.7
                
        except Exception as e:
            logger.warning(f"版本检测失败: {e}，默认使用5.7")
            self._version = 5.7
        
        logger.info(f"检测到MySQL版本: {self._version}")
        return self._version
    
    def is_mysql8(self) -> bool:
        """是否为MySQL 8.0+"""
        return self.get_version() >= 8.0
    
    def is_mysql57(self) -> bool:
        """是否为MySQL 5.7"""
        version = self.get_version()
        return 5.7 <= version < 8.0
    
    def get_column_name(self, table: str, column_candidates: List[str]) -> Optional[str]:
        """
        动态检测表中存在的列名

        参数:
            table: 表名（如 'events_statements_summary_by_digest'）
            column_candidates: 候选列名列表（如 ['SQL_TEXT', 'DIGEST_TEXT']）

        返回:
            第一个存在的列名，或 None

        示例:
            >>> detector.get_column_name(
            ...     'events_statements_summary_by_digest',
            ...     ['SQL_TEXT', 'DIGEST_TEXT']
            ... )
            'DIGEST_TEXT'
        """
        cache_key = f"column:{table}:{','.join(column_candidates)}"
        if cache_key in self._detected_features:
            result = self._detected_features[cache_key]
            return result if result else None

        try:
            for column in column_candidates:
                # 使用参数化查询，但避免列表参数问题
                result = self.connector.execute(
                    "SELECT COUNT(*) FROM information_schema.COLUMNS "
                    "WHERE TABLE_SCHEMA = 'performance_schema' "
                    "AND TABLE_NAME = :table_name "
                    "AND COLUMN_NAME = :column_name",
                    {"table_name": table, "column_name": column}
                )

                if result.rows and result.rows[0][0] > 0:
                    self._detected_features[cache_key] = column
                    logger.info(f"检测到列名: {table}.{column}")
                    return column

            self._detected_features[cache_key] = False
            logger.warning(f"未找到候选列: {table}.{column_candidates}")
            return None

        except Exception as e:
            logger.warning(f"列名检测失败: {e}")
            self._detected_features[cache_key] = False
            return None

    def check_feature(self, feature: str) -> bool:
        """
        检查特定功能是否可用

        参数:
            feature: 功能名称
                - 'performance_schema': performance_schema是否可用
                - 'events_statements_summary': events_statements_summary_by_digest表是否存在
                - 'slow_log_table': mysql.slow_log表是否存在
        """
        if feature in self._detected_features:
            return self._detected_features[feature]

        available = False

        try:
            if feature == 'performance_schema':
                result = self.connector.execute("""
                    SELECT COUNT(*) FROM information_schema.schemata
                    WHERE schema_name = 'performance_schema'
                """)
                available = result.rows and result.rows[0][0] > 0

            elif feature == 'events_statements_summary':
                result = self.connector.execute("""
                    SELECT COUNT(*) FROM information_schema.tables
                    WHERE table_schema = 'performance_schema'
                    AND table_name = 'events_statements_summary_by_digest'
                """)
                available = result.rows and result.rows[0][0] > 0

            elif feature == 'slow_log_table':
                result = self.connector.execute("""
                    SELECT COUNT(*) FROM information_schema.tables
                    WHERE table_schema = 'mysql' 
                    AND table_name = 'slow_log'
                """)
                available = result.rows and result.rows[0][0] > 0
                
        except Exception as e:
            logger.debug(f"功能检测失败 {feature}: {e}")
            available = False
        
        self._detected_features[feature] = available
        return available


class MySQLSlowQueryCollector:
    """
    MySQL慢查询采集器
    
    核心能力：
        1. 自动版本检测：根据MySQL版本选择合适SQL
        2. 多级降级：优先performance_schema，失败降级到processlist
        3. 统一输出：不同版本、不同数据源返回相同格式
        4. 性能保护：内置查询限制，避免影响生产
        5. 错误分类：精细化错误处理
    
    采集策略：
        Level 1: performance_schema.events_statements_summary_by_digest（最详细）
        Level 2: mysql.slow_log（需要开启慢查询日志）
        Level 3: information_schema.PROCESSLIST（实时查询，无历史）
    """
    
    def __init__(self, connector, max_queries_per_minute: int = 10):
        """
        初始化采集器
        
        参数:
            connector: 数据库连接器
            max_queries_per_minute: 每分钟最大查询次数（性能保护）
        """
        self.connector = connector
        self.version_detector = MySQLVersionDetector(connector)
        self.max_queries_per_minute = max_queries_per_minute
        self._query_timestamps: List[float] = []
        
        # 缓存版本信息
        self._mysql_version = None
        self._features = {}
        
        # 错误记录
        self._errors: List[CollectionError] = []
    
    def _check_rate_limit(self) -> bool:
        """检查查询频率限制"""
        now = time.time()
        one_minute_ago = now - 60
        
        # 清理过期记录
        self._query_timestamps = [t for t in self._query_timestamps if t > one_minute_ago]
        
        # 检查限制
        if len(self._query_timestamps) >= self.max_queries_per_minute:
            logger.warning("查询频率超限，跳过本次采集")
            return False
        
        self._query_timestamps.append(now)
        return True
    
    def _classify_error(self, error: Exception, source: str) -> CollectionError:
        """
        分类错误并生成CollectionError
        
        参数:
            error: 原始异常
            source: 错误来源
            
        返回:
            CollectionError: 分类后的错误信息
        """
        error_msg = str(error).lower()
        
        # 连接错误
        if any(kw in error_msg for kw in ['connection', 'connect', 'network', 'refused', 'closed']):
            return CollectionError(
                category=ErrorCategory.CONNECTION_ERROR,
                message=f"数据库连接失败: {error}",
                source=source,
                recoverable=True,
                suggestion="检查网络连接和数据库服务状态",
                original_error=error
            )
        
        # 权限错误
        if any(kw in error_msg for kw in ['permission', 'access denied', 'privilege', 'not allowed']):
            return CollectionError(
                category=ErrorCategory.PERMISSION_ERROR,
                message=f"权限不足: {error}",
                source=source,
                recoverable=False,
                suggestion="检查数据库用户权限，确保有SELECT权限",
                original_error=error
            )
        
        # 配置错误
        if any(kw in error_msg for kw in ['configuration', 'not enabled', 'disabled', 'turned off']):
            return CollectionError(
                category=ErrorCategory.CONFIGURATION_ERROR,
                message=f"功能未启用: {error}",
                source=source,
                recoverable=True,
                suggestion="检查MySQL配置，确保performance_schema或slow_log已启用",
                original_error=error
            )
        
        # 超时错误
        if any(kw in error_msg for kw in ['timeout', 'timed out', 'lock wait']):
            return CollectionError(
                category=ErrorCategory.TIMEOUT_ERROR,
                message=f"查询超时: {error}",
                source=source,
                recoverable=True,
                suggestion="增加超时时间或减少查询范围",
                original_error=error
            )
        
        # 数据错误
        if any(kw in error_msg for kw in ['data', 'format', 'parse', 'convert']):
            return CollectionError(
                category=ErrorCategory.DATA_ERROR,
                message=f"数据错误: {error}",
                source=source,
                recoverable=True,
                suggestion="检查数据格式和类型",
                original_error=error
            )
        
        # 未知错误
        return CollectionError(
            category=ErrorCategory.UNKNOWN_ERROR,
            message=f"未知错误: {error}",
            source=source,
            recoverable=True,
            suggestion="查看日志获取详细信息",
            original_error=error
        )
    
    def get_errors(self) -> List[CollectionError]:
        """获取采集过程中的错误列表"""
        return self._errors.copy()
    
    def clear_errors(self):
        """清空错误记录"""
        self._errors.clear()
    
    def collect_slow_queries(self, limit: int = 10,
                            min_time: float = 0.0,
                            table: Optional[str] = None,
                            database: Optional[str] = None) -> List[SlowQuery]:
        """
        采集慢查询（主入口）

        参数:
            limit: 返回条数限制
            min_time: 最小执行时间（秒）
            table: 指定表名过滤（可选）
            database: 指定数据库过滤（可选，只返回该数据库的慢查询）

        返回:
            List[SlowQuery]: 慢查询列表

        采集策略：
            1. 优先使用performance_schema（最准确）
            2. 降级到slow_log表
            3. 最后使用processlist（实时）
        """
        # 清空之前的错误记录
        self.clear_errors()

        if not self._check_rate_limit():
            return []

        queries = []

        # Level 1: performance_schema（推荐）
        if self.version_detector.check_feature('events_statements_summary'):
            try:
                queries = self._collect_from_performance_schema(limit, min_time, table, database)
                if queries:
                    logger.info(f"从performance_schema采集到 {len(queries)} 条慢查询")
                    return queries
            except Exception as e:
                error = self._classify_error(e, 'performance_schema')
                self._errors.append(error)
                logger.warning(f"performance_schema采集失败 [{error.category.value}]: {e}")

        # Level 2: slow_log表
        if self.version_detector.check_feature('slow_log_table'):
            try:
                queries = self._collect_from_slow_log(limit, min_time, table, database)
                if queries:
                    logger.info(f"从slow_log采集到 {len(queries)} 条慢查询")
                    return queries
            except Exception as e:
                logger.warning(f"slow_log采集失败: {e}")

        # Level 3: processlist（最后手段）
        try:
            queries = self._collect_from_processlist(limit, min_time, table, database)
            if queries:
                logger.info(f"从processlist采集到 {len(queries)} 条慢查询")
                return queries
        except Exception as e:
            logger.warning(f"processlist采集失败: {e}")

        logger.warning("所有采集源都失败，返回空结果")
        return []
    
    # 允许的列名白名单（防止SQL注入）
    _ALLOWED_TEXT_COLUMNS = {'SQL_TEXT', 'DIGEST_TEXT'}
    
    def _get_text_column(self) -> str:
        """
        动态获取正确的文本列名

        不再依赖硬编码的版本号，而是直接查询表结构

        返回:
            str: 实际存在的列名（'SQL_TEXT' 或 'DIGEST_TEXT'）

        注意:
            - 优先检测 DIGEST_TEXT（MySQL 5.7+）
            - 回退到 SQL_TEXT（旧版本）
        """
        # 动态检测列名，不依赖版本号
        column = self.version_detector.get_column_name(
            'events_statements_summary_by_digest',
            ['DIGEST_TEXT', 'SQL_TEXT']  # 优先检测 DIGEST_TEXT
        )

        if column:
            return column

        # 默认回退
        logger.warning("无法检测列名，默认使用 DIGEST_TEXT")
        return "DIGEST_TEXT"
    
    def _validate_column_name(self, column: str) -> str:
        """
        验证列名是否在白名单中
        
        参数:
            column: 列名
            
        返回:
            str: 验证后的列名
            
        异常:
            ValueError: 如果列名不在白名单中
        """
        if column not in self._ALLOWED_TEXT_COLUMNS:
            raise ValueError(f"非法列名: {column}，允许的列: {self._ALLOWED_TEXT_COLUMNS}")
        return column
    
    def _collect_from_performance_schema(self, limit: int,
                                         min_time: float,
                                         table: Optional[str],
                                         database: Optional[str] = None) -> List[SlowQuery]:
        """
        从performance_schema采集

        MySQL 5.7: 使用SQL_TEXT字段
        MySQL 8.0: 使用DIGEST_TEXT字段

        注意:
            - SCHEMA_NAME记录的是SQL执行时的默认数据库
            - 如果SQL中使用了db.table格式，SCHEMA_NAME可能不等于实际操作的数据库
            - database参数用于过滤SQL文本中包含该数据库名的查询

        安全说明:
            - 列名通过白名单验证，防止SQL注入
            - 所有用户输入使用参数化查询
        """
        # 获取并验证列名
        text_column = self._validate_column_name(self._get_text_column())

        # 构建SQL（列名通过白名单验证，其他值使用参数化查询）
        # 使用命名参数 :param 格式（SQLAlchemy 兼容性更好）
        sql = f"""
            SELECT
                {text_column} as sql_text,
                SCHEMA_NAME as db,
                COUNT_STAR as exec_count,
                AVG_TIMER_WAIT/1000000000000 as avg_time_sec,
                MAX_TIMER_WAIT/1000000000000 as max_time_sec,
                SUM_ROWS_SENT as total_rows_sent,
                SUM_ROWS_EXAMINED as total_rows_examined,
                FIRST_SEEN,
                LAST_SEEN
            FROM performance_schema.events_statements_summary_by_digest
            WHERE {text_column} IS NOT NULL
                AND {text_column} NOT LIKE '%performance_schema%'
                AND AVG_TIMER_WAIT/1000000000000 >= :min_time
        """

        params = {"min_time": min_time}

        # 数据库过滤（严格模式）
        # 只返回SCHEMA_NAME匹配且SQL中不包含其他数据库名的查询
        if database:
            sql += " AND SCHEMA_NAME = :database"
            params["database"] = database
            # 排除SQL中明确包含其他数据库名的查询（如 db.table 格式）
            # 但保留只操作当前数据库表的查询
            sql += f" AND ({text_column} NOT LIKE '%.%' OR {text_column} LIKE :db_table_pattern)"
            params["db_table_pattern"] = f"%{database}.%"

        # 表名过滤（使用参数化查询）
        if table:
            sql += f" AND {text_column} LIKE :table_pattern"
            params["table_pattern"] = f"%{table}%"

        # 排序和限制
        sql += " ORDER BY AVG_TIMER_WAIT DESC LIMIT :limit"
        params["limit"] = limit

        result = self.connector.execute(sql, params)

        queries = []
        for row in result.rows:
            try:
                # 清理SQL：移除换行符和多余空格
                raw_sql = row[0] if row[0] else ''
                cleaned_sql = ' '.join(raw_sql.split())

                query = SlowQuery(
                    sql=cleaned_sql,
                    database=row[1],
                    count=int(row[2]) if row[2] else 0,
                    query_time=float(row[3]) if row[3] else 0.0,
                    rows_sent=int(row[5]) if row[5] else 0,
                    rows_examined=int(row[6]) if row[6] else 0,
                    first_seen=str(row[7]) if row[7] else None,
                    last_seen=str(row[8]) if row[8] else None,
                    source='performance_schema'
                )
                queries.append(query)
            except Exception as e:
                logger.debug(f"解析查询记录失败: {e}")
                continue

        return queries
    
    def _collect_from_slow_log(self, limit: int,
                               min_time: float,
                               table: Optional[str],
                               database: Optional[str] = None) -> List[SlowQuery]:
        """
        从mysql.slow_log表采集

        注意:
            - db字段记录的是连接的数据库，不是SQL中操作的数据库
            - 如果SQL中使用了db.table格式，db字段可能不等于实际操作的数据库
        """

        sql = """
            SELECT
                sql_text,
                db,
                query_time,
                rows_sent,
                rows_examined,
                start_time
            FROM mysql.slow_log
            WHERE sql_text IS NOT NULL
        """

        params = {}

        # 数据库过滤（严格模式）
        # 只返回db字段匹配的数据库的查询
        if database:
            sql += " AND db = :database"
            params["database"] = database

        if min_time > 0:
            sql += " AND query_time >= :min_time"
            params["min_time"] = min_time

        if table:
            sql += " AND sql_text LIKE :table_pattern"
            params["table_pattern"] = f"%{table}%"

        sql += " ORDER BY start_time DESC LIMIT :limit"
        params["limit"] = limit

        result = self.connector.execute(sql, params)

        queries = []
        for row in result.rows:
            try:
                # 清理SQL：移除换行符和多余空格
                raw_sql = row[0] if row[0] else ''
                cleaned_sql = ' '.join(raw_sql.split())

                query = SlowQuery(
                    sql=cleaned_sql,
                    database=row[1],
                    query_time=float(row[2]) if row[2] else 0.0,
                    count=1,  # slow_log每条是一个实例
                    rows_sent=int(row[3]) if row[3] else 0,
                    rows_examined=int(row[4]) if row[4] else 0,
                    last_seen=str(row[5]) if row[5] else None,
                    source='slow_log'
                )
                queries.append(query)
            except Exception as e:
                logger.debug(f"解析慢日志记录失败: {e}")
                continue

        return queries
    
    def _collect_from_processlist(self, limit: int,
                                  min_time: float,
                                  table: Optional[str],
                                  database: Optional[str] = None) -> List[SlowQuery]:
        """
        从information_schema.PROCESSLIST采集（实时查询）

        注意:
            - DB字段记录的是连接的数据库，不是SQL中操作的数据库
            - 如果SQL中使用了db.table格式，DB字段可能不等于实际操作的数据库
        """

        sql = """
            SELECT
                ID,
                USER,
                HOST,
                DB,
                COMMAND,
                TIME,
                STATE,
                INFO
            FROM information_schema.PROCESSLIST
            WHERE COMMAND != 'Sleep'
                AND INFO IS NOT NULL
                AND INFO NOT LIKE '%PROCESSLIST%'
        """

        params = {}

        # 数据库过滤（严格模式）
        # 只返回DB字段匹配的数据库的查询
        if database:
            sql += " AND DB = :database"
            params["database"] = database

        if min_time > 0:
            sql += " AND TIME >= :min_time"
            params["min_time"] = int(min_time)

        if table:
            sql += " AND INFO LIKE :table_pattern"
            params["table_pattern"] = f"%{table}%"

        sql += " ORDER BY TIME DESC LIMIT :limit"
        params["limit"] = limit

        result = self.connector.execute(sql, params)

        queries = []
        for row in result.rows:
            try:
                query_time = int(row[5]) if row[5] else 0

                # 清理SQL：移除换行符和多余空格
                raw_sql = row[7] if row[7] else ''
                cleaned_sql = ' '.join(raw_sql.split())

                query = SlowQuery(
                    sql=cleaned_sql,
                    database=row[3],
                    query_time=float(query_time),
                    count=1,
                    rows_sent=0,  # processlist不提供
                    rows_examined=0,
                    source='processlist'
                )
                queries.append(query)
            except Exception as e:
                logger.debug(f"解析processlist记录失败: {e}")
                continue

        return queries
    
    def get_collection_stats(self) -> Dict[str, Any]:
        """
        获取采集统计信息
        
        返回:
            Dict: 包含版本信息、可用功能等
        """
        return {
            'mysql_version': self.version_detector.get_version(),
            'features': {
                'performance_schema': self.version_detector.check_feature('performance_schema'),
                'events_statements_summary': self.version_detector.check_feature('events_statements_summary'),
                'slow_log_table': self.version_detector.check_feature('slow_log_table'),
            },
            'rate_limit': {
                'max_per_minute': self.max_queries_per_minute,
                'current_count': len(self._query_timestamps),
            }
        }


# 便捷函数
def collect_mysql_slow_queries(connector, limit: int = 10) -> List[Dict[str, Any]]:
    """
    快速采集MySQL慢查询（便捷函数）
    
    参数:
        connector: 数据库连接器
        limit: 返回条数
        
    返回:
        List[Dict]: 慢查询列表（字典格式）
    """
    collector = MySQLSlowQueryCollector(connector)
    queries = collector.collect_slow_queries(limit)
    
    # 转换为字典列表
    return [
        {
            'sql': q.sql,
            'query_time': q.query_time,
            'count': q.count,
            'rows_sent': q.rows_sent,
            'rows_examined': q.rows_examined,
            'database': q.database,
            'source': q.source,
        }
        for q in queries
    ]
