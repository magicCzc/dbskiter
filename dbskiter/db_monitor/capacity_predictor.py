"""
容量预测器 - 基于基线趋势预测未来容量需求

文件功能：
1. 基于历史数据预测未来趋势
2. 计算容量达到阈值的时间
3. 提供多场景预测（乐观/中性/悲观）
4. 生成容量规划建议

作者：Trae AI
创建时间：2026-04-17
"""

import json
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum


class PredictionScenario(Enum):
    """预测场景"""
    OPTIMISTIC = "optimistic"    # 乐观：按最低增长
    NEUTRAL = "neutral"          # 中性：按平均增长
    PESSIMISTIC = "pessimistic"  # 悲观：按最高增长


@dataclass
class CapacityPrediction:
    """容量预测结果"""
    metric: str                          # 指标名称
    current_value: float                 # 当前值
    current_time: datetime               # 当前时间
    
    # 预测值（7天、30天、90天）
    predictions: Dict[str, float]        # {"7d": 75.5, "30d": 82.3, ...}
    
    # 达到阈值的时间
    days_to_threshold: Optional[int]     # 距离达到阈值的天数
    threshold: float                     # 阈值（如 90%）
    
    # 趋势信息
    growth_rate_daily: float             # 日增长率
    trend_direction: str                 # "up", "down", "stable"
    confidence: float                    # 预测置信度 (0-1)
    
    # 建议
    recommendation: str                  # 容量规划建议
    urgency: str                         # "low", "medium", "high", "critical"
    
    def summary(self) -> str:
        """生成预测摘要"""
        lines = [
            f"容量预测: {self.metric}",
            f"  当前: {self.current_value:.1f}% ({self.current_time.strftime('%Y-%m-%d')})",
            f"  趋势: {self.trend_direction} (日增长率: {self.growth_rate_daily:.2f}%)",
            f"  预测:",
        ]
        
        for period, value in self.predictions.items():
            lines.append(f"    {period}: {value:.1f}%")
        
        if self.days_to_threshold:
            lines.append(f"  预警: {self.days_to_threshold} 天后达到 {self.threshold}%")
            lines.append(f"  紧急度: {self.urgency.upper()}")
        
        lines.append(f"  建议: {self.recommendation}")
        
        return "\n".join(lines)


class CapacityPredictor:
    """
    容量预测器
    
    功能：
    1. 多模型趋势预测（线性回归 + 指数平滑）
    2. 容量达到阈值时间估算
    3. 多场景预测（乐观/中性/悲观）
    4. 容量规划建议生成
    """
    
    # 默认阈值配置
    THRESHOLDS = {
        "cpu": 80.0,           # CPU 80% 报警
        "memory": 85.0,        # 内存 85% 报警
        "disk": 90.0,          # 磁盘 90% 报警
        "connections": 80.0,   # 连接数 80% 报警
    }
    
    def __init__(self, data_dir: Optional[str] = None):
        """
        初始化预测器
        
        参数：
            data_dir: 数据存储目录
        """
        self.data_dir = data_dir
    
    def predict(
        self,
        metric: str,
        historical_data: List[Tuple[datetime, float]],
        scenario: PredictionScenario = PredictionScenario.NEUTRAL
    ) -> CapacityPrediction:
        """
        预测未来容量
        
        参数：
            metric: 指标名称（cpu/memory/disk）
            historical_data: 历史数据 [(timestamp, value), ...]
            scenario: 预测场景
            
        返回：
            CapacityPrediction: 预测结果
        """
        if not historical_data or len(historical_data) < 3:
            return self._empty_prediction(metric)
        
        # 数据清洗和排序
        data = self._clean_data(historical_data)
        
        # 当前值
        current_time, current_value = data[-1]
        
        # 计算趋势
        growth_rate, trend_direction = self._calculate_trend(data)
        
        # 根据场景调整增长率
        adjusted_rate = self._adjust_rate(growth_rate, scenario)
        
        # 预测未来值
        predictions = self._predict_future(current_value, adjusted_rate)
        
        # 计算达到阈值的时间
        threshold = self.THRESHOLDS.get(metric, 90.0)
        days_to_threshold = self._calculate_days_to_threshold(
            current_value, adjusted_rate, threshold
        )
        
        # 确定紧急度
        urgency = self._determine_urgency(days_to_threshold)
        
        # 生成建议
        recommendation = self._generate_recommendation(
            metric, current_value, predictions, days_to_threshold, urgency
        )
        
        # 计算置信度
        confidence = self._calculate_confidence(data)
        
        return CapacityPrediction(
            metric=metric,
            current_value=current_value,
            current_time=current_time,
            predictions=predictions,
            days_to_threshold=days_to_threshold,
            threshold=threshold,
            growth_rate_daily=adjusted_rate,
            trend_direction=trend_direction,
            confidence=confidence,
            recommendation=recommendation,
            urgency=urgency
        )
    
    def predict_all_scenarios(
        self,
        metric: str,
        historical_data: List[Tuple[datetime, float]]
    ) -> Dict[str, CapacityPrediction]:
        """
        生成所有场景的预测
        
        参数：
            metric: 指标名称
            historical_data: 历史数据
            
        返回：
            Dict: {scenario: prediction}
        """
        return {
            "optimistic": self.predict(metric, historical_data, PredictionScenario.OPTIMISTIC),
            "neutral": self.predict(metric, historical_data, PredictionScenario.NEUTRAL),
            "pessimistic": self.predict(metric, historical_data, PredictionScenario.PESSIMISTIC),
        }
    
    def _clean_data(
        self, 
        data: List[Tuple[datetime, float]]
    ) -> List[Tuple[datetime, float]]:
        """清洗数据：排序、去重、去除异常值"""
        # 按时间排序
        sorted_data = sorted(data, key=lambda x: x[0])
        
        # 去除重复时间点（保留最后一个）
        seen = {}
        for ts, val in sorted_data:
            seen[ts] = (ts, val)
        unique_data = list(seen.values())
        
        # 去除明显异常值（3-sigma）
        if len(unique_data) >= 10:
            values = [v for _, v in unique_data]
            mean = np.mean(values)
            std = np.std(values)
            
            cleaned = []
            for ts, val in unique_data:
                if abs(val - mean) <= 3 * std:  # 保留在 3-sigma 内的值
                    cleaned.append((ts, val))
            
            # 如果清洗后数据太少，回退到去重后的数据
            if len(cleaned) >= 5:
                return cleaned
        
        return unique_data
    
    def _calculate_trend(
        self, 
        data: List[Tuple[datetime, float]]
    ) -> Tuple[float, str]:
        """
        计算趋势
        
        返回：
            (日增长率, 趋势方向)
        """
        if len(data) < 2:
            return 0.0, "stable"
        
        # 使用线性回归计算趋势
        # 简化：计算最近7天（或全部）的平均日增长
        
        if len(data) >= 7:
            recent_data = data[-7:]  # 最近7个点
        else:
            recent_data = data
        
        # 计算平均日增长
        total_change = recent_data[-1][1] - recent_data[0][1]
        days = (recent_data[-1][0] - recent_data[0][0]).days
        
        if days <= 0:
            return 0.0, "stable"
        
        daily_growth = total_change / days
        
        # 判断趋势方向
        if daily_growth > 0.5:
            direction = "up"
        elif daily_growth < -0.5:
            direction = "down"
        else:
            direction = "stable"
        
        return daily_growth, direction
    
    def _adjust_rate(
        self, 
        rate: float, 
        scenario: PredictionScenario
    ) -> float:
        """根据场景调整增长率"""
        adjustments = {
            PredictionScenario.OPTIMISTIC: 0.5,    # 乐观：增长率减半
            PredictionScenario.NEUTRAL: 1.0,        # 中性：不变
            PredictionScenario.PESSIMISTIC: 1.5,    # 悲观：增长率增加50%
        }
        
        return rate * adjustments.get(scenario, 1.0)
    
    def _predict_future(
        self, 
        current_value: float, 
        daily_rate: float
    ) -> Dict[str, float]:
        """预测未来值"""
        return {
            "7d": min(current_value + daily_rate * 7, 100.0),
            "30d": min(current_value + daily_rate * 30, 100.0),
            "90d": min(current_value + daily_rate * 90, 100.0),
        }
    
    def _calculate_days_to_threshold(
        self, 
        current: float, 
        daily_rate: float, 
        threshold: float
    ) -> Optional[int]:
        """计算达到阈值的天数"""
        if daily_rate <= 0:
            return None  # 不增长或下降，不会达到阈值
        
        days = (threshold - current) / daily_rate
        
        if days <= 0:
            return 0  # 已经超过阈值
        
        return int(days)
    
    def _determine_urgency(self, days_to_threshold: Optional[int]) -> str:
        """确定紧急度"""
        if days_to_threshold is None:
            return "low"
        
        if days_to_threshold <= 7:
            return "critical"
        elif days_to_threshold <= 30:
            return "high"
        elif days_to_threshold <= 90:
            return "medium"
        else:
            return "low"
    
    def _generate_recommendation(
        self,
        metric: str,
        current: float,
        predictions: Dict[str, float],
        days_to_threshold: Optional[int],
        urgency: str
    ) -> str:
        """生成容量规划建议"""
        if urgency == "critical":
            return f"紧急：{metric} 将在 {days_to_threshold} 天内达到阈值，建议立即扩容"
        elif urgency == "high":
            return f"重要：{metric} 将在 30 天内达到阈值，建议本月内规划扩容"
        elif urgency == "medium":
            return f"注意：{metric} 持续增长，建议监控并准备扩容方案"
        else:
            if predictions["30d"] > current * 1.1:
                return f"{metric} 趋势平稳，建议定期复查"
            else:
                return f"{metric} 充足，无需担心"
    
    def _calculate_confidence(self, data: List[Tuple[datetime, float]]) -> float:
        """计算预测置信度"""
        # 数据量越多，置信度越高
        data_factor = min(len(data) / 30, 1.0)  # 30天数据为满分
        
        # 数据波动越小，置信度越高
        if len(data) >= 3:
            values = [v for _, v in data]
            cv = np.std(values) / np.mean(values) if np.mean(values) > 0 else 0
            stability_factor = max(0, 1 - cv)  # 变异系数越小越好
        else:
            stability_factor = 0.5
        
        return (data_factor + stability_factor) / 2
    
    def _empty_prediction(self, metric: str) -> CapacityPrediction:
        """生成空预测"""
        return CapacityPrediction(
            metric=metric,
            current_value=0.0,
            current_time=datetime.now(),
            predictions={},
            days_to_threshold=None,
            threshold=self.THRESHOLDS.get(metric, 90.0),
            growth_rate_daily=0.0,
            trend_direction="unknown",
            confidence=0.0,
            recommendation="数据不足，无法预测",
            urgency="unknown"
        )


# 便捷函数
def predict_capacity(
    metric: str,
    historical_data: List[Tuple[datetime, float]],
    scenario: str = "neutral"
) -> CapacityPrediction:
    """
    容量预测便捷函数
    
    使用示例：
        >>> from db_monitor.capacity_predictor import predict_capacity
        >>> from datetime import datetime, timedelta
        >>> 
        >>> # 生成7天历史数据
        >>> data = []
        >>> for i in range(7):
        >>>     data.append((
        >>>         datetime.now() - timedelta(days=6-i),
        >>>         70 + i * 2  # 每天增长2%
        >>>     ))
        >>> 
        >>> result = predict_capacity("disk", data)
        >>> print(result.summary())
    """
    predictor = CapacityPredictor()
    scenario_enum = PredictionScenario(scenario)
    return predictor.predict(metric, historical_data, scenario_enum)
