"""
models.py
Pipeline 数据结构共享模块
包含 PipelineStep, PipelineResult 等核心数据结构
"""

from dataclasses import dataclass, field
from typing import List, Any, Optional
import pandas as pd


@dataclass
class PipelineStep:
    """流水线步骤记录"""
    step_type: str
    description: str
    detail: Any = None


@dataclass
class PipelineResult:
    """Pipeline 执行结果"""
    df: Optional[pd.DataFrame] = None
    query_result: Optional[Any] = field(default=None, repr=False)
    base64_images: List[str] = field(default_factory=list)
    export_paths: List[str] = field(default_factory=list)
    steps: List[PipelineStep] = field(default_factory=list)
    summary: str = ""

    def add_step(self, step_type: str, description: str, detail: Any = None):
        self.steps.append(PipelineStep(step_type, description, detail))

    def log(self) -> str:
        lines = [f"Pipeline 执行日志（共 {len(self.steps)} 步）:"]
        for i, s in enumerate(self.steps, 1):
            lines.append(f"  {i}. [{s.step_type}] {s.description}")
        if self.summary:
            lines.append(f"\n总结: {self.summary}")
        return "\n".join(lines)


@dataclass
class UnifiedPipelineResult:
    """统一 Pipeline 执行结果 (扩展版)"""
    df: Optional[pd.DataFrame] = None
    base64_images: List[str] = field(default_factory=list)
    interactive_charts: List[str] = field(default_factory=list)
    insights: Optional[Any] = None
    export_paths: List[str] = field(default_factory=list)
    steps: List[PipelineStep] = field(default_factory=list)
    summary: str = ""

    def add_step(self, step_type: str, description: str, detail: Any = None):
        self.steps.append(PipelineStep(step_type, description, detail))

    def log(self) -> str:
        lines = [f"UnifiedPipeline 执行日志（{len(self.steps)} 步）:"]
        for i, s in enumerate(self.steps, 1):
            lines.append(f"  {i:2d}. [{s.step_type:18s}] {s.description}")
        if self.summary:
            lines.append(f"\n  总结: {self.summary}")
        return "\n".join(lines)
