"""
依赖管理模块 - 简化版

文件功能：管理任务间的依赖关系
主要类：DependencyManager - 依赖管理器
"""
from typing import Dict, List, Set, Optional
from collections import defaultdict, deque
import logging

logger = logging.getLogger(__name__)


class DependencyManager:
    """任务依赖管理器"""
    
    def __init__(self):
        self.dependencies: Dict[str, Set[str]] = defaultdict(set)  # task -> set of dependencies
        self.dependents: Dict[str, Set[str]] = defaultdict(set)    # task -> set of dependents
    
    def add_dependency(self, task_id: str, depends_on: str) -> bool:
        """添加依赖关系: task_id 依赖于 depends_on"""
        if task_id == depends_on:
            logger.error(f"任务不能依赖自己: {task_id}")
            return False
        
        self.dependencies[task_id].add(depends_on)
        self.dependents[depends_on].add(task_id)
        logger.debug(f"添加依赖: {task_id} -> {depends_on}")
        return True
    
    def remove_dependency(self, task_id: str, depends_on: str) -> bool:
        """移除依赖关系"""
        if depends_on in self.dependencies[task_id]:
            self.dependencies[task_id].remove(depends_on)
            self.dependents[depends_on].remove(task_id)
            return True
        return False
    
    def get_dependencies(self, task_id: str) -> Set[str]:
        """获取任务的所有依赖"""
        return self.dependencies[task_id].copy()
    
    def get_dependents(self, task_id: str) -> Set[str]:
        """获取依赖于该任务的所有任务"""
        return self.dependents[task_id].copy()
    
    def can_execute(self, task_id: str, completed_tasks: Set[str]) -> bool:
        """检查任务是否可以执行（所有依赖已完成）"""
        deps = self.dependencies[task_id]
        return deps.issubset(completed_tasks)
    
    def get_execution_order(self, task_ids: List[str]) -> Optional[List[str]]:
        """获取任务的执行顺序（拓扑排序）"""
        # 构建图
        in_degree = {task: 0 for task in task_ids}
        graph = defaultdict(list)
        
        for task in task_ids:
            for dep in self.dependencies[task]:
                if dep in in_degree:
                    graph[dep].append(task)
                    in_degree[task] += 1
        
        # 拓扑排序
        queue = deque([task for task, degree in in_degree.items() if degree == 0])
        result = []
        
        while queue:
            task = queue.popleft()
            result.append(task)
            
            for dependent in graph[task]:
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    queue.append(dependent)
        
        if len(result) != len(task_ids):
            logger.error("检测到循环依赖")
            return None
        
        return result
    
    def detect_cycles(self) -> List[List[str]]:
        """检测循环依赖"""
        cycles = []
        visited = set()
        rec_stack = set()
        path = []
        
        def dfs(task_id):
            visited.add(task_id)
            rec_stack.add(task_id)
            path.append(task_id)
            
            for dep in self.dependencies[task_id]:
                if dep not in visited:
                    if dfs(dep):
                        return True
                elif dep in rec_stack:
                    # 发现循环
                    cycle_start = path.index(dep)
                    cycles.append(path[cycle_start:] + [dep])
                    return True
            
            path.pop()
            rec_stack.remove(task_id)
            return False
        
        for task in list(self.dependencies.keys()):
            if task not in visited:
                dfs(task)
        
        return cycles
    
    def clear_task(self, task_id: str) -> None:
        """清除任务的所有依赖关系"""
        # 清除该任务的依赖
        for dep in list(self.dependencies[task_id]):
            self.dependents[dep].discard(task_id)
        del self.dependencies[task_id]
        
        # 清除其他任务对该任务的依赖
        for dependent in list(self.dependents[task_id]):
            self.dependencies[dependent].discard(task_id)
        del self.dependents[task_id]
