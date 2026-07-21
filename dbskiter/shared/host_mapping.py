"""
主机名映射管理器

文件功能：管理 Prometheus 和 Zabbix 之间的主机名映射
主要类：HostMappingManager

作者：Trae AI
创建时间：2026-04-17
"""

import os
import json
from typing import Dict, Optional, List
from dataclasses import dataclass

# 默认映射配置（可以根据实际情况调整）
DEFAULT_MAPPINGS = {
    # Prometheus RDS 实例名 -> Zabbix 主机名
    # 示例：如果 Zabbix 里叫 IP 或其他命名
    # "rds-xxx": "xxx.xxx.xxx.xxx",
}


@dataclass
class HostInfo:
    """主机信息"""
    prometheus_name: str
    zabbix_name: Optional[str] = None
    zabbix_hostid: Optional[str] = None
    ip_address: Optional[str] = None
    
    @property
    def is_mapped(self) -> bool:
        """是否已建立映射"""
        return self.zabbix_name is not None


class HostMappingManager:
    """
    主机名映射管理器
    
    解决 Prometheus 和 Zabbix 主机名不一致的问题
    
    使用示例：
        manager = HostMappingManager()
        
        # 获取 Zabbix 主机名
        zabbix_host = manager.get_zabbix_name("rds-xxx")
        
        # 自动发现映射
        mappings = manager.auto_discover(prometheus_client, zabbix_client)
    """
    
    def __init__(self, mapping_file: Optional[str] = None):
        """
        初始化映射管理器
        
        参数：
            mapping_file: 映射配置文件路径，默认使用内置映射
        """
        self.mappings: Dict[str, str] = {}
        self.mapping_file = mapping_file
        
        # 加载映射
        self._load_mappings()
    
    def _load_mappings(self) -> None:
        """加载映射配置"""
        # 先加载默认映射
        self.mappings.update(DEFAULT_MAPPINGS)
        
        # 如果指定了配置文件，加载文件中的映射
        if self.mapping_file and os.path.exists(self.mapping_file):
            try:
                with open(self.mapping_file, 'r', encoding='utf-8') as f:
                    file_mappings = json.load(f)
                    self.mappings.update(file_mappings)
            except (json.JSONDecodeError, IOError) as e:
                print(f"Warning: Failed to load mapping file: {e}")
    
    def _save_mappings(self) -> None:
        """保存映射配置到文件"""
        if self.mapping_file:
            try:
                with open(self.mapping_file, 'w', encoding='utf-8') as f:
                    json.dump(self.mappings, f, indent=2, ensure_ascii=False)
            except IOError as e:
                print(f"Warning: Failed to save mapping file: {e}")
    
    def get_zabbix_name(self, prometheus_name: str) -> Optional[str]:
        """
        获取 Prometheus 主机名对应的 Zabbix 主机名
        
        参数：
            prometheus_name: Prometheus 中的主机名（如 rds-xxx）
            
        返回：
            Zabbix 主机名，如果没有映射则返回 None
        """
        # 直接映射
        if prometheus_name in self.mappings:
            return self.mappings[prometheus_name]
        
        # 尝试模糊匹配（去掉前缀等）
        # 例如：rds-xxx -> xxx
        if prometheus_name.startswith("rds-"):
            short_name = prometheus_name[4:]  # 去掉 "rds-" 前缀
            if short_name in self.mappings:
                return self.mappings[short_name]
        
        return None
    
    def get_prometheus_name(self, zabbix_name: str) -> Optional[str]:
        """
        获取 Zabbix 主机名对应的 Prometheus 主机名
        
        参数：
            zabbix_name: Zabbix 中的主机名
            
        返回：
            Prometheus 主机名，如果没有映射则返回 None
        """
        for prom_name, zbx_name in self.mappings.items():
            if zbx_name == zabbix_name:
                return prom_name
        return None
    
    def add_mapping(self, prometheus_name: str, zabbix_name: str, save: bool = True) -> None:
        """
        添加主机名映射
        
        参数：
            prometheus_name: Prometheus 主机名
            zabbix_name: Zabbix 主机名
            save: 是否保存到文件
        """
        self.mappings[prometheus_name] = zabbix_name
        if save:
            self._save_mappings()
    
    def remove_mapping(self, prometheus_name: str, save: bool = True) -> None:
        """
        移除主机名映射
        
        参数：
            prometheus_name: Prometheus 主机名
            save: 是否保存到文件
        """
        if prometheus_name in self.mappings:
            del self.mappings[prometheus_name]
            if save:
                self._save_mappings()
    
    def list_mappings(self) -> Dict[str, str]:
        """
        列出所有映射
        
        返回：
            映射字典 {prometheus_name: zabbix_name}
        """
        return self.mappings.copy()
    
    def auto_discover(
        self, 
        prometheus_instances: List[str],
        zabbix_hosts: List[Dict]
    ) -> List[HostInfo]:
        """
        自动发现主机映射
        
        基于主机名相似度进行匹配，支持 RDS 集群映射
        
        参数：
            prometheus_instances: Prometheus 实例列表
            zabbix_hosts: Zabbix 主机列表
            
        返回：
            主机信息列表
        """
        results = []
        
        for prom_name in prometheus_instances:
            host_info = HostInfo(prometheus_name=prom_name)
            
            # 1. 检查已有映射
            mapped_name = self.get_zabbix_name(prom_name)
            if mapped_name:
                host_info.zabbix_name = mapped_name
                results.append(host_info)
                continue
            
            # 2. 尝试自动匹配（改进版）
            # 提取 Prometheus 实例的关键字
            import re
            prom_match = re.search(r'rds-([a-zA-Z0-9]+)', prom_name, re.IGNORECASE)
            if prom_match:
                prom_keyword = prom_match.group(1).upper()
                
                # 查找匹配的 Zabbix 主机
                matching_hosts = []
                for zbx_host in zabbix_hosts:
                    zbx_name = zbx_host.get("name", "")
                    zbx_host_name = zbx_host.get("host", "")
                    
                    # 检查是否包含相同关键字
                    if prom_keyword in zbx_name.upper() or prom_keyword in zbx_host_name.upper():
                        matching_hosts.append(zbx_host)
                
                if matching_hosts:
                    # 策略：优先选择主节点（通常包含 231 或编号最小）
                    # 排序：优先 231，然后是 232，233...
                    def sort_key(host):
                        name = host.get("name", "")
                        if "_231_" in name:
                            return (0, name)
                        elif "_232_" in name:
                            return (1, name)
                        elif "_233_" in name:
                            return (2, name)
                        else:
                            return (3, name)
                    
                    matching_hosts.sort(key=sort_key)
                    selected_host = matching_hosts[0]
                    
                    host_info.zabbix_name = selected_host.get("name")
                    host_info.zabbix_hostid = selected_host.get("hostid")
            
            results.append(host_info)
        
        return results
    
    def get_all_cluster_nodes(
        self,
        prometheus_name: str,
        zabbix_hosts: List[Dict]
    ) -> List[Dict]:
        """
        获取 RDS 集群的所有节点
        
        参数：
            prometheus_name: Prometheus 实例名（如 rds-xxx）
            zabbix_hosts: Zabbix 主机列表
            
        返回：
            该集群的所有节点列表
        """
        import re
        prom_match = re.search(r'rds-([a-zA-Z0-9]+)', prometheus_name, re.IGNORECASE)
        if not prom_match:
            return []
        
        prom_keyword = prom_match.group(1).upper()
        
        nodes = []
        for zbx_host in zabbix_hosts:
            zbx_name = zbx_host.get("name", "")
            zbx_host_name = zbx_host.get("host", "")
            
            if prom_keyword in zbx_name.upper() or prom_keyword in zbx_host_name.upper():
                nodes.append(zbx_host)
        
        # 按节点编号排序
        def sort_key(host):
            name = host.get("name", "")
            if "_231_" in name:
                return 0
            elif "_232_" in name:
                return 1
            elif "_233_" in name:
                return 2
            elif "NFS" in name.upper():
                return 3
            else:
                return 4
        
        nodes.sort(key=sort_key)
        return nodes
    
    def suggest_mapping(
        self, 
        prometheus_name: str, 
        zabbix_hosts: List[Dict]
    ) -> List[Dict]:
        """
        为 Prometheus 主机建议可能的 Zabbix 映射
        
        参数：
            prometheus_name: Prometheus 主机名
            zabbix_hosts: Zabbix 主机列表
            
        返回：
            建议列表，按相似度排序
        """
        suggestions = []
        prom_lower = prometheus_name.lower()
        
        for zbx_host in zabbix_hosts:
            zbx_name = zbx_host.get("name", "")
            zbx_host_name = zbx_host.get("host", "")
            
            score = 0
            
            # 计算相似度分数
            if prom_lower in zbx_name.lower():
                score += 10
            if prom_lower in zbx_host_name.lower():
                score += 10
            if zbx_name.lower() in prom_lower:
                score += 5
            if zbx_host_name.lower() in prom_lower:
                score += 5
            
            # 提取关键字匹配
            import re
            prom_keywords = set(re.findall(r'[a-zA-Z0-9]+', prometheus_name))
            zbx_keywords = set(re.findall(r'[a-zA-Z0-9]+', zbx_name + zbx_host_name))
            common_keywords = prom_keywords & zbx_keywords
            score += len(common_keywords) * 2
            
            if score > 0:
                suggestions.append({
                    "hostid": zbx_host.get("hostid"),
                    "name": zbx_name,
                    "host": zbx_host_name,
                    "score": score
                })
        
        # 按分数排序
        suggestions.sort(key=lambda x: x["score"], reverse=True)
        return suggestions[:5]  # 返回前5个建议
