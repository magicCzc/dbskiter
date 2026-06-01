"""
db_lock_analyzer/skill.py
db_lock_analyzer Skill - 数据库锁分析与死锁检测（模块化重构版）

文件功能：提供完整的数据库锁分析能力
主要类：
    - LockAnalyzerSkill: 锁分析技能统一入口（模块化重构版）

作者：AI Assistant
创建时间：2026-04-22
最后修改：2026-04-23
版本：3.0.0（模块化重构版）
"""

import logging
import uuid
import re
from typing import Dict, Any, List
from datetime import datetime

from dbskiter.shared.unified_connector import UnifiedConnector
from dbskiter.shared.error_handler import create_success_response, create_error_response

from .models import (
    ErrorCode,
    LockType,
    LockMode,
    LockInfo,
    DeadlockInfo,
)
from .utils import (
    LockParser,
    DeadlockDetector,
    LockChainBuilder,
    LockStatisticsCalculator,
)

logger = logging.getLogger(__name__)


class LockAnalyzerSkill:
    """
    数据库锁分析 Skill（模块化重构版）

    功能：
        1. 当前锁分析 - 获取当前所有锁信息
        2. 锁等待分析 - 分析锁等待情况
        3. 死锁检测 - 检测死锁事件
        4. 锁等待链追踪 - 追踪阻塞链
        5. 锁统计 - 生成锁统计报告
        6. 可视化 - 生成锁关系图
        7. 事务终止 - 终止阻塞事务

    支持的数据库：
        - MySQL
        - PostgreSQL（部分支持）

    使用示例：
        >>> skill = LockAnalyzerSkill(connector)
        >>> result = skill.analyze_current_locks()
        >>> if result["success"]:
        ...     locks = result["data"]["locks"]
        ...     print(f"当前锁数量: {len(locks)}")
    """

    def __init__(self, connector: UnifiedConnector):
        """
        初始化锁分析 Skill

        参数:
            connector: UnifiedConnector 实例
        """
        self.connector = connector
        self.dialect = connector.dialect.lower()

        # 初始化工具类
        self._parser = LockParser()
        self._detector = DeadlockDetector()
        self._chain_builder = LockChainBuilder()
        self._stats_calculator = LockStatisticsCalculator()

        logger.info(f"LockAnalyzerSkill 初始化完成 (dialect={self.dialect})")

    def analyze_current_locks(self) -> Dict[str, Any]:
        """
        分析当前所有锁

        返回:
            Dict: 标准响应格式，包含锁信息列表
        """
        try:
            locks = []

            if 'mysql' in self.dialect:
                locks = self._get_mysql_locks()
            elif 'postgresql' in self.dialect:
                locks = self._get_postgresql_locks()
            elif 'oracle' in self.dialect:
                locks = self._get_oracle_locks()
            else:
                return create_error_response(
                    message=f"数据库类型 {self.dialect} 的锁分析未完全实现",
                    error_code=ErrorCode.UNSUPPORTED_DATABASE
                )

            data = {
                "locks": [lock.to_dict() for lock in locks],
                "count": len(locks)
            }
            # 如果锁列表为空，添加权限提示（可能因权限不足无法获取）
            if len(locks) == 0:
                data["note"] = (
                    "未获取到锁信息。可能原因："
                    "1) 当前确实无锁等待；"
                    "2) 数据库用户缺少 PROCESS 权限，无法访问 information_schema.innodb_locks 等系统视图。"
                    "如需完整锁分析，请使用具有 PROCESS 权限的数据库用户。"
                )
            return create_success_response(
                data=data,
                message=f"成功获取 {len(locks)} 个锁信息"
            )

        except Exception as e:
            logger.error(f"获取锁信息失败: {e}")
            return create_error_response(
                message=f"获取锁信息失败: {str(e)}",
                error_code=ErrorCode.LOCK_ANALYSIS_FAILED
            )

    def _get_mysql_locks(self) -> List[LockInfo]:
        """获取MySQL锁信息"""
        locks = []

        # 1. 获取InnoDB事务和锁信息
        # 注意：MySQL 5.7 和 8.0 的 innodb_lock_waits 表结构不同
        # MySQL 5.7: 有 requesting_trx_id, blocking_trx_id, lock_id 等列
        # MySQL 8.0: 有 requesting_engine_transaction_id, blocking_engine_transaction_id 等列
        try:
            # 先尝试 MySQL 5.7 格式
            try:
                result = self.connector.execute("""
                    SELECT
                        r.trx_id,
                        r.trx_mysql_thread_id,
                        r.trx_state,
                        r.trx_tables_locked,
                        r.trx_rows_locked,
                        r.trx_started,
                        b.lock_id,
                        b.lock_mode,
                        b.lock_type,
                        b.lock_table,
                        b.lock_index,
                        b.lock_data,
                        w.requesting_trx_id,
                        w.blocking_trx_id,
                        NULL as request_lock_mode,
                        TIMESTAMPDIFF(SECOND, r.trx_started, NOW()) as trx_seconds
                    FROM information_schema.innodb_trx r
                    LEFT JOIN information_schema.innodb_locks b ON r.trx_id = b.lock_trx_id
                    LEFT JOIN information_schema.innodb_lock_waits w ON r.trx_id = w.requesting_trx_id
                    ORDER BY r.trx_started
                """)
            except Exception as e:
                # 如果失败，尝试 MySQL 8.0 格式
                err_msg = str(e).split('\n')[0][:120]
                logger.warning(f"MySQL 5.7 格式查询失败 [{type(e).__name__}]，尝试 8.0 格式: {err_msg}")
                result = self.connector.execute("""
                    SELECT
                        r.trx_id,
                        r.trx_mysql_thread_id,
                        r.trx_state,
                        r.trx_tables_locked,
                        r.trx_rows_locked,
                        r.trx_started,
                        b.lock_id,
                        b.lock_mode,
                        b.lock_type,
                        b.lock_table,
                        b.lock_index,
                        b.lock_data,
                        w.requesting_engine_transaction_id,
                        w.blocking_engine_transaction_id,
                        NULL as request_lock_mode,
                        TIMESTAMPDIFF(SECOND, r.trx_started, NOW()) as trx_seconds
                    FROM information_schema.innodb_trx r
                    LEFT JOIN performance_schema.data_locks b ON r.trx_id = b.engine_transaction_id
                    LEFT JOIN performance_schema.data_lock_waits w ON r.trx_id = w.requesting_engine_transaction_id
                    ORDER BY r.trx_started
                """)

            for row in result.rows if result else []:
                lock_info = LockInfo(
                    lock_id=row[6] or str(uuid.uuid4())[:8],
                    transaction_id=str(row[0]),
                    thread_id=row[1],
                    lock_type=self._parser.parse_mysql_lock_type(row[8]),
                    lock_mode=self._parser.parse_mysql_lock_mode(row[7]),
                    table_schema=None,
                    table_name=row[9],
                    index_name=row[10],
                    lock_data=row[11],
                    lock_status="WAITING" if row[12] else "GRANTED",
                    wait_time=None,
                    query_sql=None,
                    query_time=None,
                    connection_id=row[1],
                    user=None,
                    host=None,
                    started_at=row[5]
                )
                locks.append(lock_info)

        except Exception as e:
            err_msg = str(e).split('\n')[0][:120]
            logger.warning(f"获取InnoDB锁信息失败 [{type(e).__name__}]: {err_msg}")

        # 2. 获取元数据锁（MDL）
        try:
            result = self.connector.execute("""
                SELECT
                    OBJECT_SCHEMA,
                    OBJECT_NAME,
                    OBJECT_TYPE,
                    LOCK_TYPE,
                    LOCK_STATUS,
                    PROCESSLIST_ID,
                    PROCESSLIST_USER,
                    PROCESSLIST_HOST,
                    PROCESSLIST_INFO,
                    PROCESSLIST_TIME,
                    THREAD_ID
                FROM performance_schema.metadata_locks m
                JOIN performance_schema.threads t ON m.OWNER_THREAD_ID = t.THREAD_ID
                WHERE OBJECT_TYPE != 'TABLESPACE'
                AND PROCESSLIST_ID IS NOT NULL
                AND LOCK_STATUS = 'PENDING'
            """)

            for row in result.rows if result else []:
                lock_info = LockInfo(
                    lock_id=f"MDL-{row[10]}",
                    transaction_id=str(row[10]),
                    thread_id=row[10],
                    lock_type=LockType.METADATA,
                    lock_mode=self._parser.parse_mysql_lock_mode(row[3]),
                    table_schema=row[0],
                    table_name=row[1],
                    index_name=None,
                    lock_data=None,
                    lock_status="WAITING" if row[4] == 'PENDING' else "GRANTED",
                    wait_time=None,
                    query_sql=row[8],
                    query_time=row[9],
                    connection_id=row[5],
                    user=row[6],
                    host=row[7],
                    started_at=None
                )
                locks.append(lock_info)

        except Exception as e:
            logger.warning(f"获取元数据锁信息失败: {e}")

        # 3. 获取进程信息补充SQL
        try:
            result = self.connector.execute("""
                SELECT
                    ID,
                    USER,
                    HOST,
                    DB,
                    COMMAND,
                    TIME,
                    STATE,
                    INFO
                FROM information_schema.processlist
                WHERE COMMAND != 'Sleep'
                AND INFO IS NOT NULL
            """)

            process_sql_map = {}
            for row in result.rows if result else []:
                process_sql_map[row[0]] = {
                    'sql': row[7],
                    'time': row[5],
                    'user': row[1],
                    'host': row[2],
                    'state': row[6]
                }

            for lock in locks:
                if lock.connection_id and lock.connection_id in process_sql_map:
                    info = process_sql_map[lock.connection_id]
                    lock.query_sql = info['sql']
                    lock.query_time = info['time']
                    lock.user = info['user']
                    lock.host = info['host']

        except Exception as e:
            logger.warning(f"获取进程信息失败: {e}")

        return locks

    def _get_postgresql_locks(self) -> List[LockInfo]:
        """获取PostgreSQL锁信息"""
        locks = []

        try:
            # 使用兼容的查询，不依赖pg_locks_blocked视图
            result = self.connector.execute("""
                SELECT
                    l.locktype,
                    l.relation::regclass,
                    l.mode,
                    l.granted,
                    l.pid,
                    a.usename,
                    a.client_addr,
                    a.query,
                    a.query_start,
                    EXTRACT(EPOCH FROM (NOW() - a.query_start)) as wait_seconds
                FROM pg_locks l
                JOIN pg_stat_activity a ON l.pid = a.pid
                WHERE l.granted = false
                OR l.pid IN (
                    SELECT DISTINCT l1.pid
                    FROM pg_locks l1
                    JOIN pg_locks l2 ON l1.locktype = l2.locktype
                        AND l1.relation = l2.relation
                        AND l1.granted = false
                        AND l2.granted = true
                )
                ORDER BY a.query_start
            """)

            for row in result.rows if result else []:
                lock_info = LockInfo(
                    lock_id=f"PG-{row[4]}",
                    transaction_id=str(row[4]),
                    thread_id=row[4],
                    lock_type=self._parser.parse_postgresql_lock_type(row[0]),
                    lock_mode=self._parser.parse_postgresql_lock_mode(row[2]),
                    table_schema=None,
                    table_name=str(row[1]) if row[1] else None,
                    index_name=None,
                    lock_data=None,
                    lock_status="GRANTED" if row[3] else "WAITING",
                    wait_time=row[9],
                    query_sql=row[7],
                    query_time=row[9],
                    connection_id=row[4],
                    user=row[5],
                    host=str(row[6]) if row[6] else None,
                    started_at=row[8]
                )
                locks.append(lock_info)

        except Exception as e:
            logger.error(f"获取PostgreSQL锁信息失败: {e}")

        return locks

    def _get_oracle_locks(self) -> List[LockInfo]:
        """
        获取Oracle锁信息

        通过单次查询v$lock、v$session、dba_objects、v$sql视图获取完整锁信息
        优化点：使用单次LEFT JOIN查询替代两次查询，减少数据库往返
        """
        locks = []

        try:
            # 使用双引号包裹包含特殊字符的列名，避免JDBC解析问题
            result = self.connector.execute("""
                SELECT
                    l.sid,
                    l.type,
                    l.id1,
                    l.id2,
                    l.lmode,
                    l.request,
                    s."SERIAL#",
                    s.username,
                    s.machine,
                    s.program,
                    s.sql_id,
                    s.sql_child_number,
                    s.logon_time,
                    s.status,
                    s.state,
                    s.event,
                    s.seconds_in_wait,
                    o.object_name,
                    o.owner,
                    s."ROW_WAIT_OBJ#",
                    s."ROW_WAIT_FILE#",
                    s."ROW_WAIT_BLOCK#",
                    s."ROW_WAIT_ROW#",
                    q.sql_text,
                    q.sql_fulltext
                FROM v$lock l
                JOIN v$session s ON l.sid = s.sid
                LEFT JOIN dba_objects o ON l.id1 = o.object_id
                LEFT JOIN v$sql q ON s.sql_id = q.sql_id
                    AND s.sql_child_number = q.child_number
                WHERE s.type = 'USER'
                AND l.type IN ('TM', 'TX')
                ORDER BY l.sid, l.type
            """)

            for row in result.rows if result else []:
                sid = row[0]
                lock_type = row[1]
                lmode = row[4]
                request = row[5]
                serial_num = row[6]
                username = row[7]
                machine = row[8]
                program = row[9]
                sql_id = row[10]
                logon_time = row[12]
                status = row[13]
                state = row[14]
                event = row[15]
                seconds_in_wait = row[16]
                object_name = row[17]
                owner = row[18]
                sql_text = row[22] or row[23]

                lock_status = "WAITING" if request > 0 else "GRANTED"
                effective_mode = request if request > 0 else lmode

                lock_info = LockInfo(
                    lock_id=f"ORA-{sid}-{lock_type}-{row[2]}",
                    transaction_id=f"{sid},{serial_num}",
                    thread_id=sid,
                    lock_type=self._parser.parse_oracle_lock_type(lock_type),
                    lock_mode=self._parser.parse_oracle_lock_mode(effective_mode),
                    table_schema=owner,
                    table_name=object_name,
                    index_name=None,
                    lock_data=None,
                    lock_status=lock_status,
                    wait_time=seconds_in_wait,
                    query_sql=sql_text,
                    query_time=None,
                    connection_id=sid,
                    user=username,
                    host=machine,
                    started_at=logon_time
                )
                locks.append(lock_info)

        except Exception as e:
            error_msg = str(e)
            if "ORA-00942" in error_msg or "table or view does not exist" in error_msg:
                logger.error(f"获取Oracle锁信息失败: 权限不足，需要SELECT ANY DICTIONARY权限或授予对v$lock、v$session、dba_objects、v$sql的查询权限")
            elif "ORA-01031" in error_msg or "insufficient privileges" in error_msg:
                logger.error(f"获取Oracle锁信息失败: 权限不足，请联系DBA授予必要的系统视图查询权限")
            else:
                logger.error(f"获取Oracle锁信息失败: {e}")

        return locks

    def detect_deadlocks(self) -> Dict[str, Any]:
        """
        检测死锁

        支持MySQL和Oracle数据库的死锁检测

        返回:
            Dict: 标准响应格式，包含死锁信息列表
        """
        try:
            deadlocks = []

            if 'mysql' in self.dialect:
                deadlocks = self._detect_mysql_deadlocks()
            elif 'oracle' in self.dialect:
                deadlocks = self._detect_oracle_deadlocks()
            else:
                # 通用死锁检测：基于锁等待图分析
                locks_result = self.analyze_current_locks()
                if locks_result["success"]:
                    locks_data = locks_result["data"]["locks"]
                    locks = self._deserialize_locks(locks_data)
                    deadlock_info = self._detector.detect_deadlock(locks)
                    if deadlock_info:
                        deadlocks.append(deadlock_info)

            return create_success_response(
                data={
                    "deadlocks": [dl.to_dict() for dl in deadlocks],
                    "count": len(deadlocks)
                },
                message=f"检测到 {len(deadlocks)} 个死锁"
            )

        except Exception as e:
            err_msg = str(e).split('\n')[0][:120]
            logger.warning(f"检测死锁失败 [{type(e).__name__}]: {err_msg}")
            return create_error_response(
                message=f"检测死锁失败: {str(e)}",
                error_code=ErrorCode.DEADLOCK_DETECTION_FAILED
            )

    def _detect_mysql_deadlocks(self) -> List[DeadlockInfo]:
        """
        检测MySQL死锁

        从SHOW ENGINE INNODB STATUS获取死锁信息

        返回:
            List[DeadlockInfo]: 死锁信息列表
        """
        deadlocks = []
        try:
            result = self.connector.execute("SHOW ENGINE INNODB STATUS")
            if result.rows:
                status_text = result.rows[0][2]
                deadlocks = self._parse_mysql_deadlocks(status_text)
        except Exception as e:
            err_msg = str(e).split('\n')[0][:120]
            logger.warning(f"检测MySQL死锁失败 [{type(e).__name__}]: {err_msg}")
        return deadlocks

    def _detect_oracle_deadlocks(self) -> List[DeadlockInfo]:
        """
        检测Oracle死锁

        通过查询v$lock和v$session视图检测锁等待循环
        Oracle会自动检测死锁并记录在等待事件中

        返回:
            List[DeadlockInfo]: 死锁信息列表
        """
        deadlocks = []
        try:
            # 查询Oracle中处于等待状态且等待事件为enq: TX - row lock contention的会话
            # 这些会话可能涉及死锁
            result = self.connector.execute("""
                SELECT
                    s.sid,
                    s."SERIAL#",
                    s.username,
                    s.machine,
                    s.program,
                    s.sql_id,
                    s.event,
                    s.seconds_in_wait,
                    s.blocking_session,
                    s.blocking_session_status,
                    q.sql_text,
                    q.sql_fulltext
                FROM v$session s
                LEFT JOIN v$sql q ON s.sql_id = q.sql_id
                    AND s.sql_child_number = q.child_number
                WHERE s.type = 'USER'
                AND s.wait_class = 'Application'
                AND s.event LIKE '%enq: TX%'
                AND s.seconds_in_wait > 0
                ORDER BY s.seconds_in_wait DESC
            """)

            # 构建等待图检测死锁
            wait_chains = []
            for row in result.rows if result else []:
                sid = row[0]
                serial_num = row[1]
                username = row[2]
                machine = row[3]
                program = row[4]
                sql_id = row[5]
                event = row[6]
                seconds_in_wait = row[7]
                blocking_sid = row[8]
                sql_text = row[10] or row[11]

                wait_chains.append({
                    'sid': sid,
                    'serial': serial_num,
                    'username': username,
                    'machine': machine,
                    'program': program,
                    'sql_id': sql_id,
                    'event': event,
                    'seconds_in_wait': seconds_in_wait,
                    'blocking_sid': blocking_sid,
                    'sql_text': sql_text
                })

            # 检测循环等待（死锁）
            deadlock_cycles = self._find_oracle_deadlock_cycles(wait_chains)

            for cycle in deadlock_cycles:
                deadlock = DeadlockInfo(
                    deadlock_id=f"ORA-DL-{datetime.now().strftime('%Y%m%d%H%M%S')}",
                    detected_at=datetime.now(),
                    transactions=[
                        {
                            'sid': tx['sid'],
                            'serial': tx['serial'],
                            'username': tx['username'],
                            'sql': tx['sql_text'][:200] if tx['sql_text'] else None,
                            'wait_seconds': tx['seconds_in_wait']
                        }
                        for tx in cycle
                    ],
                    victim_transaction=str(cycle[0]['sid']) if cycle else "",
                    resolution="建议：1) 终止其中一个会话 2) 检查应用程序事务逻辑 3) 确保按相同顺序访问资源"
                )
                deadlocks.append(deadlock)

        except Exception as e:
            logger.error(f"检测Oracle死锁失败: {e}")

        return deadlocks

    def _find_oracle_deadlock_cycles(self, wait_chains: List[Dict]) -> List[List[Dict]]:
        """
        在Oracle等待链中查找死锁循环

        参数:
            wait_chains: 等待链列表，每个元素包含sid和blocking_sid

        返回:
            List[List[Dict]]: 死锁循环列表
        """
        # 构建等待图
        wait_graph = {}
        sid_to_info = {}

        for chain in wait_chains:
            sid = chain['sid']
            blocking_sid = chain.get('blocking_sid')

            sid_to_info[sid] = chain

            if blocking_sid:
                if sid not in wait_graph:
                    wait_graph[sid] = []
                wait_graph[sid].append(blocking_sid)

        # 使用DFS查找环
        cycles = []
        visited = set()
        rec_stack = set()
        path = []

        def dfs(node):
            visited.add(node)
            rec_stack.add(node)
            path.append(node)

            for neighbor in wait_graph.get(node, []):
                if neighbor not in visited:
                    result = dfs(neighbor)
                    if result:
                        return result
                elif neighbor in rec_stack:
                    # 找到环
                    cycle_start = path.index(neighbor)
                    cycle = path[cycle_start:]
                    return cycle

            path.pop()
            rec_stack.remove(node)
            return None

        for node in list(wait_graph.keys()):
            if node not in visited:
                cycle = dfs(node)
                if cycle:
                    cycle_info = [sid_to_info[sid] for sid in cycle if sid in sid_to_info]
                    if cycle_info:
                        cycles.append(cycle_info)
                # 重置路径和递归栈以查找更多环
                path = []
                rec_stack = set()

        return cycles

    def _parse_mysql_deadlocks(self, status_text: str) -> List[DeadlockInfo]:
        """解析MySQL死锁信息"""
        deadlocks = []

        deadlock_pattern = r'LATEST DETECTED DEADLOCK\s*-+\s*(.*?)\s*-+'
        matches = re.findall(deadlock_pattern, status_text, re.DOTALL)

        for i, match in enumerate(matches):
            deadlock = DeadlockInfo(
                deadlock_id=f"DL-{datetime.now().strftime('%Y%m%d%H%M%S')}-{i}",
                detected_at=datetime.now(),
                transactions=[],
                victim_transaction="",
                resolution="建议：1) 检查事务逻辑 2) 按相同顺序访问资源 3) 减少事务持有锁的时间"
            )

            tx_pattern = r'Transaction \d+.*?ROLLING BACK BACK \d+'
            tx_matches = re.findall(tx_pattern, match, re.DOTALL)

            for tx_match in tx_matches:
                deadlock.transactions.append({
                    "info": tx_match[:200]
                })

            if 'WE ROLL BACK TRANSACTION' in match:
                victim_match = re.search(r'WE ROLL BACK TRANSACTION (\d+)', match)
                if victim_match:
                    deadlock.victim_transaction = victim_match.group(1)

            deadlocks.append(deadlock)

        return deadlocks

    def _deserialize_locks(self, locks_data: List[Dict[str, Any]]) -> List[LockInfo]:
        """
        将锁数据字典列表反序列化为LockInfo对象列表

        参数:
            locks_data: 锁数据字典列表

        返回:
            List[LockInfo]: LockInfo对象列表
        """
        locks = []
        for lock_dict in locks_data:
            lock_info = LockInfo(
                lock_id=lock_dict.get("lock_id", ""),
                transaction_id=lock_dict.get("transaction_id", ""),
                thread_id=lock_dict.get("thread_id"),
                lock_type=LockType(lock_dict.get("lock_type", "row")),
                lock_mode=LockMode(lock_dict.get("lock_mode", "shared")),
                table_schema=lock_dict.get("table_schema"),
                table_name=lock_dict.get("table_name"),
                index_name=lock_dict.get("index_name"),
                lock_data=lock_dict.get("lock_data"),
                lock_status=lock_dict.get("lock_status", "GRANTED"),
                wait_time=lock_dict.get("wait_time"),
                query_sql=lock_dict.get("query_sql"),
                query_time=lock_dict.get("query_time"),
                connection_id=lock_dict.get("connection_id"),
                user=lock_dict.get("user"),
                host=lock_dict.get("host"),
                started_at=lock_dict.get("started_at")
            )
            locks.append(lock_info)
        return locks

    def trace_lock_wait_chain(self) -> Dict[str, Any]:
        """
        追踪锁等待链

        返回:
            Dict: 标准响应格式，包含锁等待链列表
        """
        try:
            locks_result = self.analyze_current_locks()
            if not locks_result["success"]:
                return locks_result

            locks_data = locks_result["data"]["locks"]
            locks = self._deserialize_locks(locks_data)
            chains = self._chain_builder.build_wait_chains(locks)

            return create_success_response(
                data={
                    "chains": [chain.to_dict() for chain in chains],
                    "count": len(chains)
                },
                message=f"发现 {len(chains)} 条锁等待链"
            )

        except Exception as e:
            logger.error(f"追踪锁等待链失败: {e}")
            return create_error_response(
                message=f"追踪锁等待链失败: {str(e)}",
                error_code=ErrorCode.CHAIN_ANALYSIS_FAILED
            )

    def trace_lock_chains(self) -> Dict[str, Any]:
        """
        追踪锁等待链（兼容方法，与trace_lock_wait_chain功能相同）

        返回:
            Dict: 标准响应格式，包含锁等待链列表
        """
        return self.trace_lock_wait_chain()

    def get_lock_statistics(self) -> Dict[str, Any]:
        """
        获取锁统计信息

        返回:
            Dict: 标准响应格式，包含锁统计信息
        """
        try:
            locks_result = self.analyze_current_locks()
            if not locks_result["success"]:
                return locks_result

            locks_data = locks_result["data"]["locks"]
            locks = self._deserialize_locks(locks_data)
            stats = self._stats_calculator.calculate(locks)

            return create_success_response(
                data=stats.to_dict(),
                message="锁统计信息获取成功"
            )

        except Exception as e:
            logger.error(f"获取锁统计信息失败: {e}")
            return create_error_response(
                message=f"获取锁统计信息失败: {str(e)}",
                error_code=ErrorCode.LOCK_ANALYSIS_FAILED
            )

    def generate_lock_report(self) -> Dict[str, Any]:
        """
        生成锁分析报告

        返回:
            Dict: 标准响应格式，包含锁分析报告
        """
        try:
            locks_result = self.analyze_current_locks()
            deadlocks_result = self.detect_deadlocks()
            stats_result = self.get_lock_statistics()

            report = {
                "generated_at": datetime.now().isoformat(),
                "database_type": self.dialect,
                "locks_available": locks_result["success"],
                "deadlocks_available": deadlocks_result["success"],
                "statistics_available": stats_result["success"]
            }

            if locks_result["success"]:
                report["locks"] = locks_result["data"]

            if deadlocks_result["success"]:
                report["deadlocks"] = deadlocks_result["data"]

            if stats_result["success"]:
                report["statistics"] = stats_result["data"]

            return create_success_response(
                data=report,
                message="锁分析报告生成成功"
            )

        except Exception as e:
            logger.error(f"生成锁报告失败: {e}")
            return create_error_response(
                message=f"生成锁报告失败: {str(e)}",
                error_code=ErrorCode.LOCK_ANALYSIS_FAILED
            )

    def kill_blocking_transaction(self, transaction_id: str) -> Dict[str, Any]:
        """
        终止阻塞事务

        参数:
            transaction_id: 事务ID

        返回:
            Dict: 标准响应格式
        """
        try:
            if 'mysql' in self.dialect:
                result = self.connector.execute("""
                    SELECT trx_mysql_thread_id
                    FROM information_schema.innodb_trx
                    WHERE trx_id = %s
                """, (transaction_id,))

                if result.rows:
                    connection_id = int(result.rows[0][0])
                    self.connector.execute("KILL %s", (connection_id,))
                    logger.info(f"已终止事务 {transaction_id} (connection_id={connection_id})")

                    return create_success_response(
                        message=f"事务 {transaction_id} 已终止"
                    )
                else:
                    return create_error_response(
                        message=f"未找到事务 {transaction_id}",
                        error_code=ErrorCode.NOT_FOUND
                    )
            elif 'oracle' in self.dialect:
                result = self.connector.execute("""
                    SELECT sid, serial#
                    FROM v$session
                    WHERE audsid = %s OR sid = %s
                """, (transaction_id, transaction_id))

                if result.rows:
                    sid = int(result.rows[0][0])
                    serial = int(result.rows[0][1])
                    self.connector.execute("""
                        ALTER SYSTEM KILL SESSION '%s,%s' IMMEDIATE
                    """ % (sid, serial))
                    logger.info(f"已终止Oracle会话 {sid},{serial}")

                    return create_success_response(
                        message=f"Oracle会话 {sid},{serial} 已终止"
                    )
                else:
                    return create_error_response(
                        message=f"未找到Oracle会话 {transaction_id}",
                        error_code=ErrorCode.NOT_FOUND
                    )

            return create_error_response(
                message=f"数据库类型 {self.dialect} 不支持终止事务",
                error_code=ErrorCode.UNSUPPORTED_DATABASE
            )

        except ValueError:
            logger.error("无效的connection_id格式")
            return create_error_response(
                message="无效的事务ID格式",
                error_code=ErrorCode.INVALID_TRANSACTION_ID
            )
        except Exception as e:
            logger.error(f"终止事务失败: {e}")
            return create_error_response(
                message=f"终止事务失败: {str(e)}",
                error_code=ErrorCode.TRANSACTION_KILL_FAILED
            )

    def close(self):
        """关闭Skill，释放资源"""
        logger.info("关闭 LockAnalyzerSkill...")
        logger.info("LockAnalyzerSkill 已关闭")

    # ==================== AI上下文构建 ====================

    def build_ai_context(
        self,
        skill_result: Dict[str, Any],
        scenario: str = "lock_analysis"
    ) -> Dict[str, Any]:
        """
        构建AI分析上下文

        参数:
            skill_result: Skill返回的原始结果
            scenario: 场景标识 (lock_analysis/deadlock_detection/lock_chains)

        返回:
            Dict[str, Any]: AI上下文
        """
        from dbskiter.shared.ai_context import AIContextBuilder

        builder = AIContextBuilder(
            dialect=self.connector.dialect if hasattr(self.connector, 'dialect') else 'unknown',
            database_name=getattr(self.connector, 'database', ''),
        )
        builder.detect_business_context(self.connector)

        data = skill_result.get("data", {})

        raw_metrics = self._extract_raw_metrics_for_ai(data, scenario)
        rule_flags = self._extract_rule_flags_for_ai(data, scenario)
        context = builder.build_database_profile(self.connector)
        reference_values = self._build_reference_values(scenario)
        ai_hints = self._build_ai_hints(scenario, data)

        return {
            "raw_metrics": raw_metrics,
            "rule_flags": rule_flags,
            "context": context,
            "reference_values": reference_values,
            "ai_hints": ai_hints,
        }

    def _extract_raw_metrics_for_ai(self, data: Dict[str, Any], scenario: str) -> Dict[str, Any]:
        """提取原始指标"""
        metrics = {}

        # 提取关键字段
        key_fields = ["locks", "deadlocks", "chains", "wait_chains", "statistics", "summary"]
        for key in key_fields:
            if key in data:
                metrics[key] = data[key]

        # 场景特定提取
        if scenario == "lock_analysis":
            for key in ["total_locks", "blocking_locks", "waiting_transactions", "lock_types"]:
                if key in data:
                    metrics[key] = data[key]
        elif scenario == "deadlock_detection":
            for key in ["deadlock_count", "deadlock_history", "affected_tables", "affected_queries"]:
                if key in data:
                    metrics[key] = data[key]
        elif scenario == "wait_chains":
            for key in ["chain_length", "root_blocker", "waiting_sessions", "chain_duration"]:
                if key in data:
                    metrics[key] = data[key]

        if not metrics:
            metrics = data

        return metrics

    def _extract_rule_flags_for_ai(self, data: Dict[str, Any], scenario: str) -> Dict[str, Any]:
        """提取规则标记"""
        flags = {}

        # 死锁标记
        deadlocks = data.get("deadlocks", [])
        if isinstance(deadlocks, list) and len(deadlocks) > 0:
            flags["active_deadlocks"] = {"flagged": True, "level": "critical", "reason": f"发现 {len(deadlocks)} 个死锁"}

        # 锁等待链标记
        chains = data.get("chains", [])
        wait_chains = data.get("wait_chains", [])
        total_chains = len(chains) if isinstance(chains, list) else 0
        total_chains += len(wait_chains) if isinstance(wait_chains, list) else 0
        if total_chains > 0:
            flags["lock_chains"] = {"flagged": True, "level": "high", "reason": f"发现 {total_chains} 条锁等待链"}

        # 锁数量标记
        locks = data.get("locks", [])
        if isinstance(locks, list):
            if len(locks) > 50:
                flags["excessive_locks"] = {"flagged": True, "level": "critical", "reason": f"锁数量过多: {len(locks)}"}
            elif len(locks) > 20:
                flags["many_locks"] = {"flagged": True, "level": "high", "reason": f"锁数量较多: {len(locks)}"}
            elif len(locks) > 10:
                flags["moderate_locks"] = {"flagged": True, "level": "medium", "reason": f"锁数量中等: {len(locks)}"}

        # 长时间等待标记
        statistics = data.get("statistics", {})
        if isinstance(statistics, dict):
            max_wait_time = statistics.get("max_wait_time", 0)
            if max_wait_time > 300:  # 5分钟
                flags["long_wait"] = {"flagged": True, "level": "critical", "reason": f"最大等待时间过长: {max_wait_time}秒"}
            elif max_wait_time > 60:  # 1分钟
                flags["moderate_wait"] = {"flagged": True, "level": "high", "reason": f"最大等待时间较长: {max_wait_time}秒"}

        return {"_disclaimer": "规则初筛结果仅供参考", "flags": flags}

    def _build_reference_values(self, scenario: str) -> Dict[str, Any]:
        """构建参考基线"""
        refs = {
            "lock_wait_threshold": {"normal": "<1s", "warning": "1-5s", "critical": ">5s"},
            "lock_count": {"normal": "<10", "warning": "10-20", "high": "20-50", "critical": ">50"},
            "transaction_duration": {"normal": "<1s", "warning": "1-10s", "critical": ">10s"},
        }
        return refs

    def _build_ai_hints(self, scenario: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """构建AI提示"""
        hints = {"focus_areas": [], "related_commands": []}
        db_name = getattr(self.connector, 'database', '')

        # 获取统计数据
        statistics = data.get("statistics", {})
        deadlocks = data.get("deadlocks", [])
        chains = data.get("chains", [])

        if scenario == "lock_analysis":
            hints["focus_areas"] = ["lock_contention", "transaction_duration", "isolation_level"]
            if isinstance(chains, list) and len(chains) > 0:
                hints["focus_areas"].append("wait_chain_analysis")
            hints["related_commands"] = [
                f"dbskiter --database={db_name} lock chains",
                f"dbskiter --database={db_name} diagnose top",
            ]
        elif scenario == "deadlock_detection":
            hints["focus_areas"] = ["deadlock_patterns", "retry_logic", "transaction_ordering"]
            if isinstance(deadlocks, list) and len(deadlocks) > 0:
                hints["focus_areas"].append("immediate_deadlock_resolution")
            hints["related_commands"] = [
                f"dbskiter --database={db_name} lock analyze",
                f"dbskiter --database={db_name} diagnose realtime",
            ]
        elif scenario == "wait_chains":
            hints["focus_areas"] = ["blocking_source", "cascade_kills", "transaction_optimization"]
            hints["related_commands"] = [
                f"dbskiter --database={db_name} lock analyze",
                f"dbskiter --database={db_name} diagnose locks",
            ]

        return hints


