"""
db_lock_analyzer/__init__.py
db_lock_analyzer - 数据库锁分析与死锁检测

文件功能：提供数据库锁分析、死锁检测、锁等待链追踪能力
主要类：
    - LockAnalyzerSkill: 锁分析技能统一入口

功能特性：
1. 当前锁分析 - 分析当前数据库中的锁情况
2. 死锁检测 - 检测死锁并提供解决建议
3. 锁等待链 - 追踪锁等待链，找出阻塞源头
4. 锁统计 - 生成锁统计报告
5. 事务终止 - 终止阻塞事务

使用示例：
    from dbskiter.db_lock_analyzer import LockAnalyzerSkill, ErrorCode

    skill = LockAnalyzerSkill(connector)

    # 分析当前锁情况
    result = skill.analyze_current_locks()
    if result["success"]:
        locks = result["data"]["locks"]
        print(f"当前锁数量: {len(locks)}")

    # 检测死锁
    deadlock_result = skill.detect_deadlocks()

    # 终止阻塞事务
    kill_result = skill.kill_blocking_transaction("transaction_id")

作者：AI Assistant
创建时间：2026-04-22
最后修改：2026-04-23
版本：3.0.0（模块化重构版）
"""

# 数据模型
from .models import (
    ErrorCode,
    ErrorMessage,
    LockType,
    LockMode,
    LockInfo,
    DeadlockInfo,
    LockWaitNode,
    LockWaitChain,
    LockStatistics,
    create_success_response,
    create_error_response,
)

# 工具类
from .utils import (
    LockParser,
    DeadlockDetector,
    LockChainBuilder,
    LockStatisticsCalculator,
    LockReporter,
)

# 统一入口
from .skill import LockAnalyzerSkill

__all__ = [
    # 数据模型
    "ErrorCode",
    "ErrorMessage",
    "LockType",
    "LockMode",
    "LockInfo",
    "DeadlockInfo",
    "LockWaitNode",
    "LockWaitChain",
    "LockStatistics",
    "create_success_response",
    "create_error_response",
    # 工具类
    "LockParser",
    "DeadlockDetector",
    "LockChainBuilder",
    "LockStatisticsCalculator",
    "LockReporter",
    # 主要入口
    "LockAnalyzerSkill",
]
