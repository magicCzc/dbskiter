"""
重试处理器模块 - 简化版

文件功能：提供任务重试和熔断机制
主要类：RetryHandler - 重试处理器
"""
from typing import Callable, Any, Optional
from dataclasses import dataclass
from enum import Enum
import time
import logging

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """熔断器状态"""
    CLOSED = "closed"      # 正常
    OPEN = "open"          # 熔断
    HALF_OPEN = "half_open"  # 半开


@dataclass
class RetryPolicy:
    """重试策略"""
    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0
    
    def get_delay(self, attempt: int) -> float:
        """获取第 N 次重试的延迟"""
        delay = self.base_delay * (self.exponential_base ** attempt)
        return min(delay, self.max_delay)


class CircuitBreaker:
    """熔断器"""
    
    def __init__(self, failure_threshold: int = 5, recovery_timeout: float = 60.0):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time: Optional[float] = None
    
    def can_execute(self) -> bool:
        """检查是否可以执行"""
        if self.state == CircuitState.CLOSED:
            return True
        
        if self.state == CircuitState.OPEN:
            if self._should_attempt_reset():
                self.state = CircuitState.HALF_OPEN
                return True
            return False
        
        return True  # HALF_OPEN
    
    def record_success(self) -> None:
        """记录成功"""
        self.failure_count = 0
        self.state = CircuitState.CLOSED
    
    def record_failure(self) -> None:
        """记录失败"""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN
            logger.warning(f"熔断器打开，失败次数: {self.failure_count}")
    
    def _should_attempt_reset(self) -> bool:
        """检查是否应该尝试重置"""
        if self.last_failure_time is None:
            return True
        return time.time() - self.last_failure_time >= self.recovery_timeout


class RetryHandler:
    """重试处理器"""
    
    def __init__(self, policy: Optional[RetryPolicy] = None, 
                 circuit_breaker: Optional[CircuitBreaker] = None):
        self.policy = policy or RetryPolicy()
        self.circuit_breaker = circuit_breaker or CircuitBreaker()
    
    def execute(self, func: Callable, *args, **kwargs) -> Any:
        """执行带重试的函数"""
        if not self.circuit_breaker.can_execute():
            raise Exception("熔断器已打开，拒绝执行")
        
        last_exception = None
        
        for attempt in range(self.policy.max_retries + 1):
            try:
                result = func(*args, **kwargs)
                self.circuit_breaker.record_success()
                return result
                
            except Exception as e:
                last_exception = e
                
                if attempt < self.policy.max_retries:
                    delay = self.policy.get_delay(attempt)
                    logger.warning(f"执行失败，{delay}秒后重试 ({attempt + 1}/{self.policy.max_retries}): {e}")
                    time.sleep(delay)
                else:
                    break
        
        self.circuit_breaker.record_failure()
        raise last_exception
    
    def execute_async(self, func: Callable, callback: Optional[Callable] = None,
                     error_callback: Optional[Callable] = None, *args, **kwargs) -> None:
        """异步执行带重试的函数"""
        import threading
        
        def _run():
            try:
                result = self.execute(func, *args, **kwargs)
                if callback:
                    callback(result)
            except Exception as e:
                if error_callback:
                    error_callback(e)
                else:
                    logger.error(f"异步执行失败: {e}")
        
        threading.Thread(target=_run, daemon=True).start()
