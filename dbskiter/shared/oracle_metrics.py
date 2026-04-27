"""
Oracle 监控指标定义

文件功能：定义从 oracle.json 看板提取的 Oracle 数据库指标
主要类：OracleMetrics

作者：Trae AI
创建时间：2026-04-17
"""

from typing import Dict, List, Optional, Any


class OracleMetrics:
    """
    Oracle 数据库指标定义（来自 oracle.json 看板）
    
    数据源：Zabbix
    监控层级：
    - 主机层：CPU、内存、系统资源
    - Oracle 层：锁、会话、进程、IOPS、TPS、QPS
    """
    
    # Oracle 数据库核心指标
    METRICS = {
        # 系统资源
        "cpu": {
            "name": "cpu used percent",
            "description": "Oracle 当前 CPU 使用率",
            "unit": "%",
            "application": "CPU",
            "threshold": 80
        },
        "memory": {
            "name": "Used memory percent",
            "description": "Oracle 当前内存使用率",
            "unit": "%",
            "application": "Memory",
            "threshold": 90
        },
        
        # Oracle 数据库指标
        "locks": {
            "name": "数据库锁数量",
            "description": "Oracle 当前数据库锁数量",
            "unit": "count",
            "application": "Oracle",
            "threshold": 10
        },
        "sessions": {
            "name": "当前所有的会话数",
            "description": "Oracle 当前会话数",
            "unit": "count",
            "application": "Oracle",
            "threshold": 500
        },
        "processes": {
            "name": "当前使用的进程数",
            "description": "Oracle 当前使用进程数",
            "unit": "count",
            "application": "Oracle",
            "threshold": 200
        },
        "iops": {
            "name": "IOPS",
            "description": "Oracle IOPS (每秒请求量)",
            "unit": "iops",
            "application": "Oracle",
            "threshold": None
        },
        "tps": {
            "name": "TPS",
            "description": "Oracle TPS (每秒执行量)",
            "unit": "tps",
            "application": "Oracle",
            "threshold": None
        },
        "qps": {
            "name": "QPS",
            "description": "Oracle QPS (每秒查询量)",
            "unit": "qps",
            "application": "Oracle",
            "threshold": None
        },
        "optimizer_errors": {
            "name": "优化器统计信息异常数",
            "description": "Oracle 优化器统计信息异常数",
            "unit": "count",
            "application": "Oracle",
            "threshold": 1
        }
    }
    
    @classmethod
    def get_metric_names(cls) -> List[str]:
        """获取所有指标名称"""
        return list(cls.METRICS.keys())
    
    @classmethod
    def get_metric_def(cls, metric_name: str) -> Optional[Dict[str, Any]]:
        """获取指标定义"""
        return cls.METRICS.get(metric_name)
    
    @classmethod
    def get_zabbix_item(cls, metric_name: str) -> Optional[str]:
        """获取 Zabbix item 名称"""
        metric = cls.METRICS.get(metric_name)
        return metric.get("name") if metric else None
    
    @classmethod
    def get_application(cls, metric_name: str) -> Optional[str]:
        """获取 Application 名称"""
        metric = cls.METRICS.get(metric_name)
        return metric.get("application") if metric else None


class OracleHostMapping:
    """
    Oracle 主机组映射
    
    Oracle 资产组命名规则：
    - KF 系列：KF5_231, KF5_232, KF5_233 或 KF5_160, KF18_160
    - Z 系列：Z5-160, Z5-80 或 Z5_160
    
    注意：Z 和 KF 可以相互转换（如 Z18 <-> KF18）
    """
    
    # 已知的 Oracle 资产组
    ORACLE_GROUPS = ["KF5", "KF6", "KF7", "KF8", "KF2", "KF18",
                     "Z", "Z2", "Z3", "Z5", "Z6", "Z7", "Z8", "Z9",
                     "Z10", "Z11", "Z12", "Z13", "Z15", "Z20", "Z66"]
    
    # Z 系列到 KF 系列的映射
    Z_TO_KF_MAP = {
        "Z18": "KF18",
        "Z5": "KF5",
        "Z6": "KF6",
        "Z7": "KF7",
        "Z8": "KF8",
    }
    
    @classmethod
    def is_oracle_group(cls, group_name: str) -> bool:
        """判断是否为 Oracle 资产组"""
        # 提取组名（如 KF5_231 -> KF5, Z5-160 -> Z5, Z5_160 -> Z5）
        base_name = group_name.split('_')[0].split('-')[0]
        # 检查是否为 Z 系列（去掉 Z 后检查是否为数字）
        if base_name.startswith('Z') and len(base_name) > 1:
            return True
        return base_name in cls.ORACLE_GROUPS
    
    @classmethod
    def z_to_kf(cls, z_name: str) -> str:
        """
        将 Z 系列名称转换为 KF 系列名称
        
        例如：Z18 -> KF18, Z5 -> KF5
        """
        base_name = z_name.split('_')[0].split('-')[0]
        return cls.Z_TO_KF_MAP.get(base_name, z_name)
    
    @classmethod
    def get_group_hosts(cls, group_name: str) -> List[str]:
        """
        获取资产组的所有主机
        
        参数：
            group_name: 资产组名，如 "KF5" 或 "Z5" 或 "Z18"
            
        返回：
            主机匹配模式列表
        """
        # 标准化组名
        base_name = group_name.split('_')[0].split('-')[0]
        
        # Z 系列直接使用 Z 名称（如 Z18）
        # 数据库服务器命名格式：Z18-160 或 Z18_160
        if base_name.startswith('Z'):
            return [f"{base_name}-", f"{base_name}_"]
        
        # KF 系列（业务服务器）：KF5_231, KF5_232, KF5_233
        # 返回多种可能的匹配模式
        hosts = []
        # 3 节点模式
        for node_id in [231, 232, 233]:
            hosts.append(f"{base_name}_{node_id}")
        # 单节点模式（如 _160）
        hosts.append(f"{base_name}_")
        return hosts
