"""
Prometheus HTTP API 客户端

文件功能：提供对 Prometheus 的查询接口封装
主要类：PrometheusClient - 查询时序数据

作者：Trae AI
创建时间：2026-04-16
"""

import os
import requests
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta

# 从环境变量读取配置，使用默认值（环境变量已在cli/config.py中统一加载）
DEFAULT_PROMETHEUS_URL = os.getenv("PROMETHEUS_URL", "http://localhost:9090")


class PrometheusClient:
    """
    Prometheus HTTP API 客户端
    
    功能：
    - 即时查询（当前值）
    - 范围查询（历史趋势）
    - 元数据查询（指标列表、标签值）
    
    使用示例：
        client = PrometheusClient("http://localhost:9090")
        
        # 查询当前内存使用率
        result = client.query('your_metric_name{instance="your-instance"}')
        
        # 查询过去1小时趋势
        result = client.query_range(
            'your_metric_name{instance="your-instance"}',
            start=datetime.now() - timedelta(hours=1),
            end=datetime.now(),
            step='5m'
        )
    """
    
    def __init__(self, base_url: str, timeout: int = 30):
        """
        初始化 Prometheus 客户端
        
        参数：
            base_url: Prometheus 地址，如 http://localhost:9090
            timeout: 请求超时时间（秒）
        """
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.session = requests.Session()
    
    def query(self, promql: str) -> Dict[str, Any]:
        """
        即时查询 - 获取当前值
        
        参数：
            promql: Prometheus 查询语句
            
        返回：
            查询结果字典
            
        示例：
            >>> result = client.query('your_metric_name{instance="your-instance"}')
            >>> for item in result['data']['result']:
            ...     print(f"{item['metric']['instance']}: {item['value'][1]}%")
        """
        url = f"{self.base_url}/api/v1/query"
        params = {"query": promql}
        
        try:
            response = self.session.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            return {"status": "error", "error": str(e)}
    
    def query_range(
        self, 
        promql: str, 
        start: datetime, 
        end: datetime, 
        step: str = '5m'
    ) -> Dict[str, Any]:
        """
        范围查询 - 获取历史趋势
        
        参数：
            promql: Prometheus 查询语句
            start: 开始时间
            end: 结束时间
            step: 采样间隔（如 '5m', '1h'）
            
        返回：
            查询结果字典，包含时间序列数据
            
        示例：
            >>> end = datetime.now()
            >>> start = end - timedelta(hours=1)
            >>> result = client.query_range(
            ...     'your_metric_name{instance="your-instance"}',
            ...     start=start,
            ...     end=end,
            ...     step='5m'
            ... )
        """
        url = f"{self.base_url}/api/v1/query_range"
        params = {
            "query": promql,
            "start": start.timestamp(),
            "end": end.timestamp(),
            "step": step
        }
        
        try:
            response = self.session.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            return {"status": "error", "error": str(e)}
    
    def get_label_values(self, label: str) -> List[str]:
        """
        获取标签的所有值
        
        参数：
            label: 标签名，如 'name'
            
        返回：
            标签值列表
            
        示例：
            >>> names = client.get_label_values('instance')
            >>> print(names)  # ['instance-1', 'instance-2', ...]
        """
        url = f"{self.base_url}/api/v1/label/{label}/values"
        
        try:
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()
            return data.get('data', []) if data.get('status') == 'success' else []
        except requests.exceptions.RequestException:
            return []
    
    def get_rds_instances(self) -> List[str]:
        """
        获取所有 RDS 实例名
        
        返回：
            RDS 实例名称列表
        """
        # 查询 huaweicloud_sys_rds 指标的 name 标签
        result = self.query('huaweicloud_sys_rds_rds002_mem_util')
        if result.get('status') != 'success':
            return []
        
        instances = set()
        for item in result['data'].get('result', []):
            name = item['metric'].get('name', '')
            if name:
                instances.add(name)
        
        return sorted(list(instances))


from .prometheus_metrics import MySQLRDSMetrics


class RDSMetrics:
    """
    华为云 RDS 指标封装（全量指标）
    
    提供完整的 RDS 监控指标查询，基于 mysql.json 看板定义
    支持资产组级别查询（自动发现组内所有节点）
    """
    
    def __init__(self, client: PrometheusClient):
        """
        初始化 RDS 指标查询器
        
        参数：
            client: PrometheusClient 实例
        """
        self.client = client
        self.metrics_def = MySQLRDSMetrics()
    
    def get_group_nodes(self, group_name: str) -> List[str]:
        """
        获取资产组的所有节点
        
        参数：
            group_name: 资产组名，如 'rds-xxx' 或 'xxx'
            
        返回：
            节点名称列表（如 ['rds-xxx', 'rds-xxx_node0', 'rds-xxx_node1']）
        """
        # 标准化组名
        if not group_name.startswith('rds-'):
            group_name = f'rds-{group_name}'
        
        # 获取所有实例
        all_instances = self.client.get_rds_instances()
        
        # 提取基础组名（去掉 _nodeX 后缀）
        base_name = group_name.split('_node')[0]
        
        # 查找属于该组的所有节点
        nodes = []
        for inst in all_instances:
            inst_base = inst.split('_node')[0]
            if inst_base == base_name:
                nodes.append(inst)
        
        return sorted(nodes)
    
    def get_group_metrics(self, group_name: str) -> Dict[str, Any]:
        """
        获取资产组的所有节点指标（聚合展示）
        
        参数：
            group_name: 资产组名，如 'rds-xxx'
            
        返回：
            包含所有节点指标的字典
        """
        nodes = self.get_group_nodes(group_name)
        
        if not nodes:
            return {
                'group': group_name,
                'timestamp': datetime.now().isoformat(),
                'error': 'No nodes found for this group',
                'nodes': {}
            }
        
        result = {
            'group': group_name,
            'timestamp': datetime.now().isoformat(),
            'nodes': {}
        }
        
        # 获取每个节点的指标
        for node in nodes:
            node_metrics = self._get_single_node_metrics(node)
            result['nodes'][node] = node_metrics
        
        # 计算聚合指标（取最大值）
        result['aggregated'] = self._aggregate_metrics(result['nodes'])
        
        return result
    
    def _get_single_node_metrics(self, instance_name: str) -> Dict[str, Any]:
        """获取单个节点的所有指标"""
        result = {'instance': instance_name, 'metrics': {}}
        
        for metric_name in self.metrics_def.get_metric_names():
            promql = self.metrics_def.get_promql(metric_name, instance_name)
            if not promql:
                continue
            
            response = self.client.query(promql)
            metric_def = self.metrics_def.METRICS.get(metric_name, {})
            
            if response.get('status') == 'success':
                data = response['data'].get('result', [])
                if data:
                    value = data[0]['value'][1]
                    result['metrics'][metric_name] = {
                        'value': float(value),
                        'unit': metric_def.get('unit', ''),
                        'description': metric_def.get('description', ''),
                        'threshold': metric_def.get('threshold')
                    }
                else:
                    result['metrics'][metric_name] = {
                        'value': None, 
                        'error': 'No data',
                        'description': metric_def.get('description', '')
                    }
            else:
                result['metrics'][metric_name] = {
                    'value': None, 
                    'error': response.get('error', 'Unknown'),
                    'description': metric_def.get('description', '')
                }
        
        return result
    
    def _aggregate_metrics(self, nodes_metrics: Dict[str, Any]) -> Dict[str, Any]:
        """
        聚合多节点指标（取最大值作为组的代表值）
        
        对于某些指标（如连接数），可能需要求和而不是取最大值
        """
        aggregated = {}
        
        # 获取所有指标名
        all_metric_names = set()
        for node_data in nodes_metrics.values():
            all_metric_names.update(node_data.get('metrics', {}).keys())
        
        for metric_name in all_metric_names:
            values = []
            unit = ''
            description = ''
            threshold = None
            
            for node_data in nodes_metrics.values():
                metric_data = node_data.get('metrics', {}).get(metric_name, {})
                value = metric_data.get('value')
                if value is not None:
                    values.append(value)
                    unit = metric_data.get('unit', unit)
                    description = metric_data.get('description', description)
                    threshold = metric_data.get('threshold', threshold)
            
            if values:
                # 连接数类指标求和，其他取最大值
                if 'connections' in metric_name or 'tps' in metric_name or 'iops' in metric_name:
                    aggregated[metric_name] = {
                        'value': sum(values),
                        'unit': unit,
                        'description': description,
                        'threshold': threshold,
                        'aggregation': 'sum',
                        'node_count': len(values)
                    }
                else:
                    # CPU、内存等取最大值（最危险的节点）
                    aggregated[metric_name] = {
                        'value': max(values),
                        'unit': unit,
                        'description': description,
                        'threshold': threshold,
                        'aggregation': 'max',
                        'node_count': len(values)
                    }
            else:
                aggregated[metric_name] = {'value': None, 'error': 'No data'}
        
        return aggregated
    
    def get_current_metrics(self, instance_name: str) -> Dict[str, Any]:
        """
        获取 RDS 当前所有指标（兼容旧接口，单节点查询）
        
        参数：
            instance_name: RDS 实例名，如 'rds-xxx'
            
        返回：
            指标数据字典
        """
        return self._get_single_node_metrics(instance_name)
    
    def get_metric_history(
        self, 
        instance_name: str, 
        metric: str, 
        hours: int = 1
    ) -> List[Dict[str, Any]]:
        """
        获取指标历史趋势
        
        参数：
            instance_name: RDS 实例名
            metric: 指标类型（cpu/memory/disk/connections等）
            hours: 查询过去几小时
            
        返回：
            时间序列数据列表
        """
        promql = self.metrics_def.get_promql(metric, instance_name)
        if not promql:
            return []
        
        end = datetime.now()
        start = end - timedelta(hours=hours)
        
        response = self.client.query_range(promql, start=start, end=end, step='5m')
        
        if response.get('status') != 'success':
            return []
        
        # 解析时间序列数据
        history = []
        for item in response['data'].get('result', []):
            for timestamp, value in item['values']:
                history.append({
                    'timestamp': datetime.fromtimestamp(timestamp).isoformat(),
                    'value': float(value)
                })
        
        return history
    
    def get_core_metrics(self, instance_name: str) -> Dict[str, Any]:
        """
        获取核心指标（简化版）
        
        只返回最重要的几个指标：cpu, memory, disk_util, connections_active
        """
        core_metrics = ['cpu', 'memory', 'disk_util', 'connections_active']
        result = {
            'instance': instance_name,
            'timestamp': datetime.now().isoformat(),
            'metrics': {}
        }
        
        for metric_name in core_metrics:
            promql = self.metrics_def.get_promql(metric_name, instance_name)
            if not promql:
                continue
            
            response = self.client.query(promql)
            metric_def = self.metrics_def.METRICS.get(metric_name, {})
            
            if response.get('status') == 'success':
                data = response['data'].get('result', [])
                if data:
                    value = data[0]['value'][1]
                    result['metrics'][metric_name] = {
                        'value': float(value),
                        'unit': metric_def.get('unit', '%'),
                        'threshold': metric_def.get('threshold')
                    }
                else:
                    result['metrics'][metric_name] = {'value': None, 'error': 'No data'}
            else:
                result['metrics'][metric_name] = {'value': None, 'error': response.get('error', 'Unknown')}
        
        return result
