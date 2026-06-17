"""
执行计时器模块

文件功能：
    - 支持 Skill 诊断/监控操作的执行耗时追踪
    - 支持单步骤计时和多步骤分解计时
    - 支持上下文管理器和装饰器两种用法
    - 生成 inspection_trace 可用的 steps 数据

主要类：
    - ExecutionTimer: 执行计时器
    - StepTimer: 单步骤计时器（上下文管理器）

版本: 1.0.0
作者: dbskiter team
创建时间: 2026-06-16
最后修改: 2026-06-16
"""

import time
import functools
from typing import Dict, Any, List, Optional, Callable
from contextlib import contextmanager


class ExecutionTimer:
    """
    执行计时器

    支持多步骤分解计时，生成 inspection_trace 可用的 steps 数据。

    属性:
        steps: List[Dict[str, Any]] - 各步骤的耗时记录
        total_elapsed_ms: float - 总耗时（毫秒）

    使用示例:
        >>> timer = ExecutionTimer()
        >>> with timer.step("check_connections", "检查连接数"):
        ...     result = skill.get_connections()
        >>> with timer.step("analyze_locks", "分析锁等待"):
        ...     result = skill.get_locks()
        >>> print(timer.to_inspection_steps())
        [{'name': 'check_connections', 'description': '检查连接数', 'elapsed_ms': 120.5}, ...]
    """

    def __init__(self):
        """
        初始化计时器
        """
        self.steps: List[Dict[str, Any]] = []
        self._start_time: Optional[float] = None
        self._total_start: Optional[float] = None

    def start(self) -> "ExecutionTimer":
        """
        启动总计时

        返回:
            ExecutionTimer: 自身，支持链式调用

        使用示例:
            >>> timer = ExecutionTimer().start()
        """
        self._total_start = time.perf_counter()
        return self

    @contextmanager
    def step(self, name: str, description: str = ""):
        """
        单步骤计时上下文管理器

        参数:
            name: 步骤标识名（英文，用于程序处理）
            description: 步骤说明（中文，用于展示）

        使用示例:
            >>> with timer.step("get_connections", "获取连接信息"):
            ...     data = skill.get_connections()
        """
        step_start = time.perf_counter()
        try:
            yield self
        finally:
            step_end = time.perf_counter()
            elapsed_ms = (step_end - step_start) * 1000
            self.steps.append({
                "name": name,
                "description": description or name,
                "elapsed_ms": round(elapsed_ms, 2),
            })

    def add_step(self, name: str, description: str, elapsed_ms: float) -> None:
        """
        手动添加步骤记录（用于外部已计时的情况）

        参数:
            name: 步骤标识名
            description: 步骤说明
            elapsed_ms: 耗时（毫秒）
        """
        self.steps.append({
            "name": name,
            "description": description or name,
            "elapsed_ms": round(elapsed_ms, 2),
        })

    def stop(self) -> float:
        """
        停止总计时

        返回:
            float: 总耗时（毫秒）
        """
        if self._total_start is not None:
            self.total_elapsed_ms = round(
                (time.perf_counter() - self._total_start) * 1000, 2
            )
            return self.total_elapsed_ms
        return 0.0

    @property
    def total_elapsed_ms(self) -> float:
        """
        获取总耗时

        返回:
            float: 总耗时（毫秒），如果未调用 start() 则返回各步骤之和
        """
        if hasattr(self, "_total_elapsed_ms"):
            return self._total_elapsed_ms
        return round(sum(s["elapsed_ms"] for s in self.steps), 2)

    @total_elapsed_ms.setter
    def total_elapsed_ms(self, value: float) -> None:
        """
        设置总耗时
        """
        self._total_elapsed_ms = value

    def to_inspection_steps(self) -> List[Dict[str, Any]]:
        """
        转换为 inspection_trace 可用的 steps 数据

        返回:
            List[Dict[str, Any]]: 步骤列表，每个步骤包含 name/description/elapsed_ms
        """
        return self.steps.copy()

    def to_summary(self) -> Dict[str, Any]:
        """
        生成耗时摘要

        返回:
            Dict[str, Any]: 包含 total_ms / step_count / steps 的字典
        """
        return {
            "total_ms": self.total_elapsed_ms,
            "step_count": len(self.steps),
            "steps": self.steps.copy(),
        }

    def __enter__(self) -> "ExecutionTimer":
        """
        上下文管理器入口（自动 start）
        """
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """
        上下文管理器出口（自动 stop）
        """
        self.stop()


def timed(name: str = "", description: str = ""):
    """
    装饰器：自动为函数计时并将结果注入返回值

    被装饰函数的返回值必须是字典类型，计时结果会注入到
    返回字典的 `_execution_time` 字段中。

    参数:
        name: 步骤名（默认使用函数名）
        description: 步骤说明

    使用示例:
        >>> @timed(description="分析慢查询")
        ... def analyze_slow_queries(self, limit=10):
        ...     return {"slow_queries": [...]}
        >>> result = analyze_slow_queries()
        >>> print(result["_execution_time"])
        {'total_ms': 450.2, 'steps': [...]}
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Dict[str, Any]:
            timer = ExecutionTimer().start()
            result = func(*args, **kwargs)
            total_ms = timer.stop()

            step_name = name or func.__name__
            step_desc = description or step_name

            # 注入计时结果
            if isinstance(result, dict):
                result["_execution_time"] = {
                    "total_ms": total_ms,
                    "steps": [{"name": step_name, "description": step_desc, "elapsed_ms": total_ms}],
                }
            return result
        return wrapper
    return decorator
