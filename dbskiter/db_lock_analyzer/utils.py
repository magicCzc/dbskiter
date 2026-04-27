"""
db_lock_analyzer/utils.py
db_lock_analyzer 工具类

文件功能：提供锁分析相关的工具类和辅助函数
主要类：
    - LockParser: 锁信息解析器
    - DeadlockDetector: 死锁检测器
    - LockChainBuilder: 锁等待链构建器
    - LockStatisticsCalculator: 锁统计计算器
    - LockReporter: 锁分析报告生成器

作者：AI Assistant
创建时间：2026-04-23
版本：3.0.0（模块化重构版）
"""

import logging
from typing import Dict, Any, List, Optional, Set, Tuple
from collections import defaultdict
from datetime import datetime

from .models import (
    LockType,
    LockMode,
    LockInfo,
    DeadlockInfo,
    LockWaitNode,
    LockWaitChain,
    LockStatistics,
)

logger = logging.getLogger(__name__)


class LockParser:
    """
    锁信息解析器

    功能：
        - 解析MySQL锁类型
        - 解析MySQL锁模式
        - 解析PostgreSQL锁信息
    """

    # MySQL锁类型映射
    MYSQL_LOCK_TYPES = {
        'RECORD': LockType.ROW,
        'TABLE': LockType.TABLE,
        'METADATA': LockType.METADATA,
        'GLOBAL': LockType.GLOBAL,
    }

    # MySQL锁模式映射
    MYSQL_LOCK_MODES = {
        'S': LockMode.SHARED,
        'X': LockMode.EXCLUSIVE,
        'IS': LockMode.INTENTION_SHARED,
        'IX': LockMode.INTENTION_EXCLUSIVE,
        'AUTO_INC': LockMode.AUTO_INC,
        'GAP': LockMode.GAP,
        'NEXT KEY': LockMode.NEXT_KEY,
    }

    @staticmethod
    def parse_mysql_lock_type(lock_type_str: Optional[str]) -> LockType:
        """
        解析MySQL锁类型

        参数:
            lock_type_str: MySQL锁类型字符串

        返回:
            LockType: 锁类型枚举
        """
        if not lock_type_str:
            return LockType.ROW

        lock_type_upper = lock_type_str.upper()

        if 'RECORD' in lock_type_upper:
            return LockType.ROW
        elif 'TABLE' in lock_type_upper:
            return LockType.TABLE
        elif 'METADATA' in lock_type_upper or 'MDL' in lock_type_upper:
            return LockType.METADATA
        elif 'GLOBAL' in lock_type_upper:
            return LockType.GLOBAL
        else:
            return LockType.ROW

    @staticmethod
    def parse_mysql_lock_mode(lock_mode_str: Optional[str]) -> LockMode:
        """
        解析MySQL锁模式

        参数:
            lock_mode_str: MySQL锁模式字符串

        返回:
            LockMode: 锁模式枚举
        """
        if not lock_mode_str:
            return LockMode.SHARED

        lock_mode_upper = lock_mode_str.upper().strip()

        # 精确匹配
        if lock_mode_upper in LockParser.MYSQL_LOCK_MODES:
            return LockParser.MYSQL_LOCK_MODES[lock_mode_upper]

        # 模糊匹配
        if 'X' in lock_mode_upper and 'IX' not in lock_mode_upper:
            return LockMode.EXCLUSIVE
        elif 'IS' in lock_mode_upper:
            return LockMode.INTENTION_SHARED
        elif 'IX' in lock_mode_upper:
            return LockMode.INTENTION_EXCLUSIVE
        elif 'AUTO_INC' in lock_mode_upper:
            return LockMode.AUTO_INC
        elif 'GAP' in lock_mode_upper:
            return LockMode.GAP
        elif 'NEXT' in lock_mode_upper:
            return LockMode.NEXT_KEY
        else:
            return LockMode.SHARED

    @staticmethod
    def parse_postgresql_lock_type(lock_type_str: Optional[str]) -> LockType:
        """
        解析PostgreSQL锁类型

        参数:
            lock_type_str: PostgreSQL锁类型字符串

        返回:
            LockType: 锁类型枚举
        """
        if not lock_type_str:
            return LockType.ROW

        lock_type_lower = lock_type_str.lower()

        if 'relation' in lock_type_lower:
            return LockType.TABLE
        elif 'tuple' in lock_type_lower or 'row' in lock_type_lower:
            return LockType.ROW
        elif 'page' in lock_type_lower:
            return LockType.PAGE
        else:
            return LockType.ROW

    @staticmethod
    def parse_postgresql_lock_mode(lock_mode_str: Optional[str]) -> LockMode:
        """
        解析PostgreSQL锁模式

        参数:
            lock_mode_str: PostgreSQL锁模式字符串

        返回:
            LockMode: 锁模式枚举
        """
        if not lock_mode_str:
            return LockMode.SHARED

        lock_mode_lower = lock_mode_str.lower()

        if 'exclusive' in lock_mode_lower:
            return LockMode.EXCLUSIVE
        elif 'share' in lock_mode_lower:
            return LockMode.SHARED
        elif 'access share' in lock_mode_lower:
            return LockMode.INTENTION_SHARED
        elif 'access exclusive' in lock_mode_lower:
            return LockMode.INTENTION_EXCLUSIVE
        else:
            return LockMode.SHARED

    @staticmethod
    def parse_oracle_lock_type(lock_type_str: Optional[str]) -> LockType:
        """
        解析Oracle锁类型

        参数:
            lock_type_str: Oracle锁类型字符串

        返回:
            LockType: 锁类型枚举
        """
        if not lock_type_str:
            return LockType.ROW

        lock_type_upper = lock_type_str.upper()

        if 'TM' in lock_type_upper:
            return LockType.TABLE
        elif 'TX' in lock_type_upper:
            return LockType.ROW
        else:
            return LockType.ROW

    @staticmethod
    def parse_oracle_lock_mode(lock_mode_str: Optional[str]) -> LockMode:
        """
        解析Oracle锁模式

        Oracle锁模式详解：
        - 0: None (无锁)
        - 1: Null (空锁)
        - 2: Row Share (RS) - 行级共享锁，允许其他事务并发读取
        - 3: Row Exclusive (RX) - 行级排他锁，用于INSERT/UPDATE/DELETE
        - 4: Share (S) - 表级共享锁，允许其他事务读取但不允许修改
        - 5: Share Row Exclusive (SRX) - 共享行级排他锁
        - 6: Exclusive (X) - 表级排他锁，用于DDL操作

        参数:
            lock_mode_str: Oracle锁模式数字或字符串

        返回:
            LockMode: 锁模式枚举
        """
        if not lock_mode_str:
            return LockMode.SHARED

        mode_str = str(lock_mode_str).strip()

        # Oracle锁模式精确映射
        oracle_mode_map = {
            '0': (LockMode.SHARED, 'None'),
            '1': (LockMode.SHARED, 'Null'),
            '2': (LockMode.INTENTION_SHARED, 'Row Share'),
            '3': (LockMode.EXCLUSIVE, 'Row Exclusive'),
            '4': (LockMode.SHARED, 'Share'),
            '5': (LockMode.INTENTION_EXCLUSIVE, 'Share Row Exclusive'),
            '6': (LockMode.EXCLUSIVE, 'Exclusive'),
        }

        result = oracle_mode_map.get(mode_str, (LockMode.SHARED, 'Unknown'))
        return result[0]


class DeadlockDetector:
    """
    死锁检测器

    功能：
        - 基于锁等待图检测死锁
        - 识别死锁环
        - 选择牺牲事务
    """

    @staticmethod
    def detect_deadlock(locks: List[LockInfo]) -> Optional[DeadlockInfo]:
        """
        检测死锁

        参数:
            locks: 锁信息列表

        返回:
            Optional[DeadlockInfo]: 死锁信息，未检测到返回None
        """
        # 构建等待图
        wait_graph = DeadlockDetector._build_wait_graph(locks)

        # 检测环
        cycle = DeadlockDetector._find_cycle(wait_graph)

        if not cycle:
            return None

        # 选择牺牲事务（选择执行时间最短的事务）
        victim = DeadlockDetector._select_victim(locks, cycle)

        return DeadlockInfo(
            deadlock_id=f"DL-{datetime.now().strftime('%Y%m%d%H%M%S')}",
            detected_at=datetime.now(),
            transactions=[
                {
                    "transaction_id": tx_id,
                    "query": DeadlockDetector._get_transaction_query(locks, tx_id)
                }
                for tx_id in cycle
            ],
            victim_transaction=victim,
            resolution=f"建议终止事务 {victim} 以解除死锁"
        )

    @staticmethod
    def _build_wait_graph(locks: List[LockInfo]) -> Dict[str, Set[str]]:
        """
        构建等待图

        参数:
            locks: 锁信息列表

        返回:
            Dict: 等待图 {transaction_id: {waiting_for_transaction_ids}}
        """
        # 按资源分组
        resource_locks: Dict[str, List[LockInfo]] = defaultdict(list)

        for lock in locks:
            if lock.table_name:
                resource_key = f"{lock.table_schema}.{lock.table_name}"
                if lock.lock_data:
                    resource_key += f":{lock.lock_data}"
                resource_locks[resource_key].append(lock)

        # 构建等待图
        wait_graph: Dict[str, Set[str]] = defaultdict(set)

        for resource, res_locks in resource_locks.items():
            # 找出已授予的锁和等待的锁
            granted = [l for l in res_locks if l.lock_status == 'GRANTED']
            waiting = [l for l in res_locks if l.lock_status == 'WAITING']

            # 等待的锁等待已授予的锁
            for wait_lock in waiting:
                for granted_lock in granted:
                    if wait_lock.transaction_id != granted_lock.transaction_id:
                        wait_graph[wait_lock.transaction_id].add(granted_lock.transaction_id)

        return wait_graph

    @staticmethod
    def _find_cycle(graph: Dict[str, Set[str]]) -> Optional[List[str]]:
        """
        使用DFS查找环

        参数:
            graph: 等待图

        返回:
            Optional[List[str]]: 环中的事务ID列表
        """
        visited: Set[str] = set()
        rec_stack: Set[str] = set()
        path: List[str] = []

        def dfs(node: str) -> Optional[List[str]]:
            visited.add(node)
            rec_stack.add(node)
            path.append(node)

            for neighbor in graph.get(node, set()):
                if neighbor not in visited:
                    result = dfs(neighbor)
                    if result:
                        return result
                elif neighbor in rec_stack:
                    # 找到环
                    cycle_start = path.index(neighbor)
                    return path[cycle_start:] + [neighbor]

            path.pop()
            rec_stack.remove(node)
            return None

        for node in graph:
            if node not in visited:
                result = dfs(node)
                if result:
                    return result

        return None

    @staticmethod
    def _select_victim(locks: List[LockInfo], cycle: List[str]) -> str:
        """
        选择牺牲事务

        策略：选择执行时间最短的事务

        参数:
            locks: 锁信息列表
            cycle: 死锁环中的事务ID

        返回:
            str: 牺牲事务ID
        """
        # 获取环中事务的信息
        cycle_transactions = []
        for tx_id in cycle:
            tx_locks = [l for l in locks if l.transaction_id == tx_id]
            if tx_locks:
                # 使用查询时间作为权重（时间短的优先牺牲）
                query_time = tx_locks[0].query_time or 0
                cycle_transactions.append((tx_id, query_time))

        if not cycle_transactions:
            return cycle[0] if cycle else ""

        # 选择查询时间最短的作为牺牲者
        cycle_transactions.sort(key=lambda x: x[1])
        return cycle_transactions[0][0]

    @staticmethod
    def _get_transaction_query(locks: List[LockInfo], transaction_id: str) -> Optional[str]:
        """获取事务的查询SQL"""
        for lock in locks:
            if lock.transaction_id == transaction_id and lock.query_sql:
                return lock.query_sql[:100]
        return None


class LockChainBuilder:
    """
    锁等待链构建器

    功能：
        - 构建锁等待链
        - 识别阻塞源头
        - 计算链深度和等待时间
    """

    @staticmethod
    def build_wait_chains(locks: List[LockInfo]) -> List[LockWaitChain]:
        """
        构建锁等待链

        参数:
            locks: 锁信息列表

        返回:
            List[LockWaitChain]: 锁等待链列表
        """
        # 只处理等待中的锁
        waiting_locks = [l for l in locks if l.lock_status == 'WAITING']

        if not waiting_locks:
            return []

        # 构建等待关系
        wait_relations = LockChainBuilder._build_wait_relations(locks)

        # 找出所有链
        chains = []
        processed_roots: Set[str] = set()

        for lock in waiting_locks:
            root = LockChainBuilder._find_root(lock.transaction_id, wait_relations)

            if root not in processed_roots:
                chain = LockChainBuilder._build_chain_from_root(root, wait_relations, locks)
                if chain:
                    chains.append(chain)
                    processed_roots.add(root)

        return chains

    @staticmethod
    def _build_wait_relations(locks: List[LockInfo]) -> Dict[str, Dict[str, Any]]:
        """
        构建等待关系

        返回:
            Dict: {transaction_id: {"waiting_for": tx_id, "wait_time": seconds}}
        """
        # 按资源分组
        resource_locks: Dict[str, List[LockInfo]] = defaultdict(list)

        for lock in locks:
            if lock.table_name:
                resource_key = f"{lock.table_schema}.{lock.table_name}"
                if lock.lock_data:
                    resource_key += f":{lock.lock_data}"
                resource_locks[resource_key].append(lock)

        # 构建等待关系
        wait_relations: Dict[str, Dict[str, Any]] = {}

        for resource, res_locks in resource_locks.items():
            granted = [l for l in res_locks if l.lock_status == 'GRANTED']
            waiting = [l for l in res_locks if l.lock_status == 'WAITING']

            for wait_lock in waiting:
                # 找出阻塞该等待锁的事务
                blockers = [
                    g.transaction_id for g in granted
                    if g.transaction_id != wait_lock.transaction_id
                ]

                if blockers:
                    wait_relations[wait_lock.transaction_id] = {
                        "waiting_for": blockers[0],  # 主要阻塞者
                        "all_blockers": blockers,
                        "wait_time": wait_lock.wait_time or 0,
                        "resource": resource
                    }

        return wait_relations

    @staticmethod
    def _find_root(transaction_id: str, wait_relations: Dict[str, Dict[str, Any]]) -> str:
        """
        查找阻塞源头

        参数:
            transaction_id: 事务ID
            wait_relations: 等待关系

        返回:
            str: 根事务ID
        """
        visited: Set[str] = set()
        current = transaction_id

        while current in wait_relations:
            if current in visited:
                # 发现环，返回当前节点
                return current

            visited.add(current)
            current = wait_relations[current]["waiting_for"]

        return current

    @staticmethod
    def _build_chain_from_root(
        root: str,
        wait_relations: Dict[str, Dict[str, Any]],
        locks: List[LockInfo]
    ) -> Optional[LockWaitChain]:
        """
        从根节点构建链

        参数:
            root: 根事务ID
            wait_relations: 等待关系
            locks: 锁信息列表

        返回:
            Optional[LockWaitChain]: 锁等待链
        """
        # 找出所有等待该根事务的事务
        chain_nodes: List[LockWaitNode] = []
        total_wait_time = 0.0

        # 根节点
        root_lock = LockChainBuilder._find_lock_by_tx(locks, root)
        if root_lock:
            chain_nodes.append(LockWaitNode(
                transaction_id=root,
                connection_id=root_lock.connection_id or 0,
                query_sql=root_lock.query_sql,
                wait_time=0,
                waiting_for=None,
                blocking=[]
            ))

        # 构建下游节点
        current_level = [root]
        visited: Set[str] = {root}

        while current_level:
            next_level = []

            for tx_id in current_level:
                # 找出等待该事务的所有事务
                waiting_txs = [
                    (k, v) for k, v in wait_relations.items()
                    if v["waiting_for"] == tx_id and k not in visited
                ]

                for waiting_tx, relation in waiting_txs:
                    visited.add(waiting_tx)
                    wait_time = relation.get("wait_time", 0) or 0
                    total_wait_time += wait_time

                    lock = LockChainBuilder._find_lock_by_tx(locks, waiting_tx)

                    chain_nodes.append(LockWaitNode(
                        transaction_id=waiting_tx,
                        connection_id=lock.connection_id if lock else 0,
                        query_sql=lock.query_sql if lock else None,
                        wait_time=wait_time,
                        waiting_for=tx_id,
                        blocking=[]
                    ))

                    next_level.append(waiting_tx)

            current_level = next_level

        if len(chain_nodes) <= 1:
            return None

        return LockWaitChain(
            chain_id=f"CHAIN-{root[:8]}",
            root_transaction=root,
            nodes=chain_nodes,
            total_wait_time=total_wait_time,
            depth=len(chain_nodes)
        )

    @staticmethod
    def _find_lock_by_tx(locks: List[LockInfo], transaction_id: str) -> Optional[LockInfo]:
        """根据事务ID查找锁信息"""
        for lock in locks:
            if lock.transaction_id == transaction_id:
                return lock
        return None


class LockStatisticsCalculator:
    """
    锁统计计算器

    功能：
        - 计算锁统计信息
        - 分析锁分布
        - 计算等待时间统计
    """

    def calculate(self, locks: List[LockInfo]) -> LockStatistics:
        """
        计算锁统计信息（实例方法）

        参数:
            locks: 锁信息列表

        返回:
            LockStatistics: 锁统计信息
        """
        return self.calculate_statistics(locks)

    @staticmethod
    def calculate_statistics(locks: List[LockInfo]) -> LockStatistics:
        """
        计算锁统计信息

        参数:
            locks: 锁信息列表

        返回:
            LockStatistics: 锁统计信息
        """
        total_locks = len(locks)
        waiting_locks = sum(1 for l in locks if l.lock_status == 'WAITING')
        granted_locks = sum(1 for l in locks if l.lock_status == 'GRANTED')

        # 按类型统计
        row_locks = sum(1 for l in locks if l.lock_type == LockType.ROW)
        table_locks = sum(1 for l in locks if l.lock_type == LockType.TABLE)
        metadata_locks = sum(1 for l in locks if l.lock_type == LockType.METADATA)

        # 等待时间统计
        wait_times = [l.wait_time for l in locks if l.wait_time is not None]

        max_wait_time = max(wait_times) if wait_times else 0.0
        avg_wait_time = sum(wait_times) / len(wait_times) if wait_times else 0.0

        return LockStatistics(
            total_locks=total_locks,
            waiting_locks=waiting_locks,
            granted_locks=granted_locks,
            row_locks=row_locks,
            table_locks=table_locks,
            metadata_locks=metadata_locks,
            max_wait_time=max_wait_time,
            avg_wait_time=round(avg_wait_time, 2),
            deadlock_count=0  # 需要单独检测
        )

    @staticmethod
    def analyze_lock_distribution(locks: List[LockInfo]) -> Dict[str, Any]:
        """
        分析锁分布

        参数:
            locks: 锁信息列表

        返回:
            Dict: 锁分布分析
        """
        # 按类型分布
        type_distribution: Dict[str, int] = defaultdict(int)
        for lock in locks:
            type_distribution[lock.lock_type.value] += 1

        # 按模式分布
        mode_distribution: Dict[str, int] = defaultdict(int)
        for lock in locks:
            mode_distribution[lock.lock_mode.value] += 1

        # 按表分布
        table_distribution: Dict[str, int] = defaultdict(int)
        for lock in locks:
            if lock.table_name:
                table_key = f"{lock.table_schema}.{lock.table_name}" if lock.table_schema else lock.table_name
                table_distribution[table_key] += 1

        # 热点表（锁最多的表）
        hot_tables = sorted(
            table_distribution.items(),
            key=lambda x: x[1],
            reverse=True
        )[:5]

        return {
            "type_distribution": dict(type_distribution),
            "mode_distribution": dict(mode_distribution),
            "table_distribution": dict(table_distribution),
            "hot_tables": [{"table": t[0], "lock_count": t[1]} for t in hot_tables],
            "total_tables": len(table_distribution)
        }


class LockReporter:
    """
    锁分析报告生成器

    功能：
        - 生成锁分析报告
        - 格式化输出
    """

    @staticmethod
    def generate_report(
        locks: List[LockInfo],
        statistics: LockStatistics,
        deadlocks: Optional[List[DeadlockInfo]] = None,
        wait_chains: Optional[List[LockWaitChain]] = None
    ) -> str:
        """
        生成锁分析报告

        参数:
            locks: 锁信息列表
            statistics: 锁统计信息
            deadlocks: 死锁信息列表
            wait_chains: 锁等待链列表

        返回:
            str: 报告文本
        """
        lines = [
            "=" * 60,
            "数据库锁分析报告",
            "=" * 60,
            f"分析时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"总锁数量: {statistics.total_locks}",
            f"等待中: {statistics.waiting_locks}",
            f"已授予: {statistics.granted_locks}",
            "",
            "锁类型分布:",
            f"  行锁: {statistics.row_locks}",
            f"  表锁: {statistics.table_locks}",
            f"  元数据锁: {statistics.metadata_locks}",
            "",
            "等待时间统计:",
            f"  最大等待: {statistics.max_wait_time:.2f}秒",
            f"  平均等待: {statistics.avg_wait_time:.2f}秒",
        ]

        # 死锁信息
        if deadlocks:
            lines.extend([
                "",
                f"发现死锁: {len(deadlocks)}个",
                "-" * 40
            ])
            for dl in deadlocks:
                lines.append(f"  死锁ID: {dl.deadlock_id}")
                lines.append(f"  涉及事务: {', '.join(t['transaction_id'] for t in dl.transactions)}")
                lines.append(f"  牺牲事务: {dl.victim_transaction}")
                lines.append(f"  建议: {dl.resolution}")
                lines.append("")

        # 锁等待链
        if wait_chains:
            lines.extend([
                "",
                f"锁等待链: {len(wait_chains)}条",
                "-" * 40
            ])
            for chain in wait_chains:
                lines.append(f"  链ID: {chain.chain_id}")
                lines.append(f"  根事务: {chain.root_transaction}")
                lines.append(f"  链深度: {chain.depth}")
                lines.append(f"  总等待时间: {chain.total_wait_time:.2f}秒")
                lines.append("")

        lines.append("=" * 60)

        return "\n".join(lines)

    @staticmethod
    def format_lock_summary(locks: List[LockInfo]) -> str:
        """
        格式化锁摘要

        参数:
            locks: 锁信息列表

        返回:
            str: 摘要文本
        """
        waiting = [l for l in locks if l.lock_status == 'WAITING']

        if not waiting:
            return "当前没有等待中的锁"

        lines = [f"等待中的锁: {len(waiting)}个", ""]

        for lock in waiting[:10]:  # 只显示前10个
            lines.append(f"  事务: {lock.transaction_id}")
            lines.append(f"  表: {lock.table_schema}.{lock.table_name}" if lock.table_schema else f"  表: {lock.table_name}")
            lines.append(f"  类型: {lock.lock_type.value}/{lock.lock_mode.value}")
            lines.append(f"  等待时间: {lock.wait_time or 0:.2f}秒")
            if lock.query_sql:
                lines.append(f"  SQL: {lock.query_sql[:80]}...")
            lines.append("")

        if len(waiting) > 10:
            lines.append(f"  ... 还有 {len(waiting) - 10} 个等待中的锁")

        return "\n".join(lines)
