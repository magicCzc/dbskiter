"""
Zabbix API 客户端

文件功能：提供对 Zabbix 的查询接口封装
主要类：ZabbixClient - 查询监控项和历史数据

作者：Trae AI
创建时间：2026-04-17
"""

import os
import json
import requests
from typing import Dict, List, Optional, Any, Union
from datetime import datetime, timedelta

# 从环境变量读取配置（环境变量已在cli/config.py中统一加载）
DEFAULT_ZABBIX_URL = os.getenv("ZABBIX_URL", "http://localhost/zabbix/api_jsonrpc.php")
DEFAULT_ZABBIX_USER = os.getenv("ZABBIX_USER", "Admin")
DEFAULT_ZABBIX_PASSWORD = os.getenv("ZABBIX_PASSWORD", "zabbix")


class ZabbixClient:
    """
    Zabbix JSON-RPC API 客户端
    
    功能：
    - 用户认证
    - 查询主机和监控项
    - 获取历史数据
    
    使用示例：
        client = ZabbixClient("https://zabbix.example.com/api_jsonrpc.php")
        client.login("Admin", "password")
        
        # 查询主机
        hosts = client.get_hosts("your-host")
        
        # 查询监控项
        items = client.get_items(hosts[0]["hostid"], "disk")
        
        # 获取历史数据
        history = client.get_history(items[0]["itemid"], hours=1)
    """
    
    def __init__(self, url: str, timeout: int = 30):
        """
        初始化 Zabbix 客户端
        
        参数：
            url: Zabbix API 地址，如 https://zabbix.example.com/api_jsonrpc.php
            timeout: 请求超时时间（秒）
        """
        self.url = url
        self.timeout = timeout
        self.session = requests.Session()
        self.auth_token: Optional[str] = None
        self.request_id = 0
    
    def _call(self, method: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        """
        调用 Zabbix API
        
        参数：
            method: API 方法名
            params: 请求参数
            
        返回：
            API 响应数据
        """
        self.request_id += 1
        
        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params or {},
            "id": self.request_id
        }
        
        # 除了 login 方法，其他都需要认证token
        if method != "user.login":
            payload["auth"] = self.auth_token
        
        try:
            response = self.session.post(
                self.url,
                json=payload,
                timeout=self.timeout,
                headers={"Content-Type": "application/json"}
            )
            response.raise_for_status()
            
            result = response.json()
            
            if "error" in result:
                return {
                    "status": "error",
                    "error": result["error"].get("data", result["error"].get("message", "Unknown error"))
                }
            
            return {
                "status": "success",
                "result": result.get("result")
            }
            
        except requests.exceptions.RequestException as e:
            return {"status": "error", "error": str(e)}
        except json.JSONDecodeError as e:
            return {"status": "error", "error": f"Invalid JSON response: {e}"}
    
    def login(self, username: str, password: str) -> bool:
        """
        用户登录，获取认证token
        
        参数：
            username: 用户名
            password: 密码
            
        返回：
            登录是否成功
        """
        # Zabbix 6.0+ 使用 username，旧版使用 user
        # 先尝试新版参数
        result = self._call("user.login", {
            "username": username,
            "password": password
        })
        
        # 如果失败，尝试旧版参数
        if result["status"] != "success":
            result = self._call("user.login", {
                "user": username,
                "password": password
            })
        
        if result["status"] == "success":
            self.auth_token = result["result"]
            return True
        else:
            print(f"Login failed: {result.get('error')}")
            return False
    
    def logout(self) -> bool:
        """退出登录"""
        if not self.auth_token:
            return True
        
        result = self._call("user.logout")
        self.auth_token = None
        return result["status"] == "success"
    
    def get_hosts(self, name: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        查询主机列表
        
        参数：
            name: 主机名过滤（支持模糊匹配）
            
        返回：
            主机列表
        """
        params = {
            "output": ["hostid", "host", "name", "status"],
            "selectInterfaces": ["ip"]
        }
        
        if name:
            params["search"] = {"name": name}
            params["searchWildcardsEnabled"] = True
        
        result = self._call("host.get", params)
        return result.get("result", []) if result["status"] == "success" else []
    
    def get_items(
        self, 
        host_id: str, 
        key_search: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        查询主机的监控项
        
        参数：
            host_id: 主机ID
            key_search: 监控项key过滤（如 "disk"、"cpu"）
            
        返回：
            监控项列表
        """
        params = {
            "output": ["itemid", "name", "key_", "lastvalue", "units"],
            "hostids": host_id,
            "search": {"status": "0"}  # 只查启用的
        }
        
        if key_search:
            params["searchWildcardsEnabled"] = True
            params["search"]["key_"] = f"*{key_search}*"
        
        result = self._call("item.get", params)
        return result.get("result", []) if result["status"] == "success" else []
    
    def get_history(
        self, 
        item_id: str, 
        hours: int = 1,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        获取监控项的历史数据
        
        参数：
            item_id: 监控项ID
            hours: 查询过去几小时
            limit: 最大返回条数
            
        返回：
            历史数据列表
        """
        end = datetime.now()
        start = end - timedelta(hours=hours)
        
        params = {
            "output": "extend",
            "history": 0,  # 0=float, 1=string, 2=log, 3=integer, 4=text
            "itemids": item_id,
            "time_from": int(start.timestamp()),
            "time_till": int(end.timestamp()),
            "sortfield": "clock",
            "sortorder": "DESC",
            "limit": limit
        }
        
        result = self._call("history.get", params)
        
        if result["status"] != "success":
            return []
        
        # 转换格式
        history = []
        for item in result.get("result", []):
            history.append({
                "timestamp": datetime.fromtimestamp(int(item["clock"])).isoformat(),
                "value": float(item["value"]),
                "ns": item.get("ns", "0")
            })
        
        return history
    
    def get_latest_value(self, item_id: str) -> Optional[float]:
        """
        获取监控项的最新值
        
        参数：
            item_id: 监控项ID
            
        返回：
            最新值，或 None
        """
        history = self.get_history(item_id, hours=1, limit=1)
        return history[0]["value"] if history else None


class ZabbixMySQLMetrics:
    """
    MySQL 数据库 Zabbix 指标封装
    
    封装 Zabbix 中与 MySQL 相关的系统级指标：
    - 磁盘空间
    - 系统负载
    - 网络流量
    - 进程状态
    """
    
    # 常用监控项key映射
    METRIC_KEYS = {
        "disk_total": "vfs.fs.size[/,total]",
        "disk_used": "vfs.fs.size[/,used]",
        "disk_free": "vfs.fs.size[/,free]",
        "disk_pused": "vfs.fs.size[/,pused]",
        "cpu_load": "system.cpu.load",
        "cpu_util": "system.cpu.util",
        "memory_total": "vm.memory.size[total]",
        "memory_available": "vm.memory.size[available]",
        "memory_used": "vm.memory.size[used]",
        "memory_pused": "vm.memory.size[pused]",
        "net_in": "net.if.in",
        "net_out": "net.if.out",
    }
    
    def __init__(self, client: ZabbixClient):
        """
        初始化
        
        参数：
            client: ZabbixClient 实例
        """
        self.client = client
    
    def find_host_by_name(self, host_name: str) -> Optional[Dict[str, Any]]:
        """
        根据主机名查找主机
        
        参数：
            host_name: 主机名
            
        返回：
            主机信息，或 None
        """
        hosts = self.client.get_hosts(host_name)
        
        # 精确匹配
        for host in hosts:
            if host["name"] == host_name or host["host"] == host_name:
                return host
        
        # 模糊匹配返回第一个
        return hosts[0] if hosts else None
    
    def get_disk_metrics(self, host_id: str) -> Dict[str, Any]:
        """
        获取磁盘指标
        
        参数：
            host_id: 主机ID
            
        返回：
            磁盘使用信息
        """
        items = self.client.get_items(host_id, "vfs.fs.size")
        
        result = {
            "total_gb": None,
            "used_gb": None,
            "free_gb": None,
            "used_percent": None
        }
        
        for item in items:
            key = item.get("key_", "")
            value = item.get("lastvalue")
            
            if value is None:
                continue
            
            value_gb = float(value) / (1024 ** 3)  # 转为 GB
            
            if ",total]" in key:
                result["total_gb"] = round(value_gb, 2)
            elif ",used]" in key:
                result["used_gb"] = round(value_gb, 2)
            elif ",free]" in key:
                result["free_gb"] = round(value_gb, 2)
            elif ",pused]" in key:
                result["used_percent"] = round(float(value), 2)
        
        return result
    
    def get_system_metrics(self, host_id: str) -> Dict[str, Any]:
        """
        获取系统级指标
        
        参数：
            host_id: 主机ID
            
        返回：
            系统指标信息
        """
        items = self.client.get_items(host_id)
        
        result = {
            "cpu_load": None,
            "cpu_util": None,
            "memory_total_gb": None,
            "memory_used_gb": None,
            "memory_used_percent": None
        }
        
        for item in items:
            key = item.get("key_", "")
            value = item.get("lastvalue")
            
            if value is None:
                continue
            
            if "system.cpu.load" in key:
                result["cpu_load"] = round(float(value), 2)
            elif "system.cpu.util" in key:
                result["cpu_util"] = round(float(value), 2)
            elif "vm.memory.size[total]" in key:
                result["memory_total_gb"] = round(float(value) / (1024 ** 3), 2)
            elif "vm.memory.size[used]" in key:
                result["memory_used_gb"] = round(float(value) / (1024 ** 3), 2)
            elif "vm.memory.size[pused]" in key:
                result["memory_used_percent"] = round(float(value), 2)
        
        return result
    
    def get_mysql_metrics(
        self,
        host_name: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        获取 MySQL 相关指标（兼容方法）
        
        参数：
            host_name: 主机名
            start_time: 开始时间
            end_time: 结束时间
            
        返回：
            MySQL 指标字典
        """
        # 查找主机
        host = self.find_host_by_name(host_name)
        if not host:
            return {"error": f"未找到主机: {host_name}"}
        
        host_id = host.get("hostid")
        
        # 获取系统级指标
        metrics = self.get_system_metrics(host_id)
        
        # 获取磁盘指标
        disk_metrics = self.get_disk_metrics(host_id)
        metrics.update(disk_metrics)
        
        return metrics


class ZabbixOracleMetrics:
    """
    Oracle 数据库 Zabbix 指标封装
    
    封装 Zabbix 中与 Oracle 相关的指标：
    - CPU、内存使用率
    - 数据库锁、会话、进程
    - IOPS、TPS、QPS
    """
    
    def __init__(self, client: ZabbixClient):
        """
        初始化
        
        参数：
            client: ZabbixClient 实例
        """
        self.client = client
    
    def find_host_by_name(self, host_name: str) -> Optional[Dict[str, Any]]:
        """
        根据主机名查找主机
        
        参数：
            host_name: 主机名（如 KF5_231）
            
        返回：
            主机信息字典
        """
        hosts = self.client.get_hosts(host_name)
        
        # 精确匹配
        for host in hosts:
            if host.get("host") == host_name or host.get("name") == host_name:
                return host
        
        # 模糊匹配
        for host in hosts:
            if host_name in host.get("host", "") or host_name in host.get("name", ""):
                return host
        
        return None
    
    def get_oracle_metrics(self, host_id: str) -> Dict[str, Any]:
        """
        获取 Oracle 数据库指标
        
        参数：
            host_id: Zabbix 主机ID
            
        返回：
            Oracle 指标字典
        """
        result = {
            "cpu": None,
            "memory": None,
            "disk_used_percent": None,
            "disk_total_gb": None,
            "disk_used_gb": None,
            "locks": None,
            "sessions": None,
            "processes": None,
            "iops": None,
            "tps": None,
            "qps": None,
            "optimizer_errors": None
        }
        
        # 获取所有监控项
        items = self.client.get_items(host_id)
        
        for item in items:
            name = item.get("name", "")
            key = item.get("key_", "")
            value = item.get("lastvalue")
            
            if value is None:
                continue
            
            # CPU 使用率
            if "cpu used percent" in name.lower():
                result["cpu"] = round(float(value), 2)
            # 内存使用率
            elif "used memory percent" in name.lower():
                result["memory"] = round(float(value), 2)
            # 磁盘使用率（pused 表示百分比已使用）
            elif ",pused]" in key and "vfs.fs.size" in key:
                result["disk_used_percent"] = round(float(value), 2)
            # 磁盘总容量
            elif ",total]" in key and "vfs.fs.size" in key:
                result["disk_total_gb"] = round(float(value) / (1024**3), 2)
            # 磁盘已使用容量
            elif ",used]" in key and "vfs.fs.size" in key:
                result["disk_used_gb"] = round(float(value) / (1024**3), 2)
            # 数据库锁数量
            elif "数据库锁数量" in name:
                result["locks"] = int(float(value))
            # 会话数
            elif "当前所有的会话数" in name:
                result["sessions"] = int(float(value))
            # 进程数
            elif "当前使用的进程数" in name:
                result["processes"] = int(float(value))
            # IOPS
            elif name == "IOPS":
                result["iops"] = round(float(value), 2)
            # TPS
            elif name == "TPS":
                result["tps"] = round(float(value), 2)
            # QPS
            elif name == "QPS":
                result["qps"] = round(float(value), 2)
            # 优化器异常
            elif "优化器统计信息异常数" in name:
                result["optimizer_errors"] = int(float(value))
        
        return result
    
    def get_group_metrics(self, group_name: str, hosts: List[Dict]) -> Dict[str, Any]:
        """
        获取资产组的所有主机指标
        
        参数：
            group_name: 资产组名（如 KF5）
            hosts: Zabbix 主机列表
            
        返回：
            组合并指标
        """
        from .oracle_metrics import OracleHostMapping
        
        # 获取组内主机模式
        group_hosts = OracleHostMapping.get_group_hosts(group_name)
        
        result = {
            "group": group_name,
            "hosts": {},
            "aggregated": {}
        }
        
        # 在提供的主机列表中查找匹配的主机
        for host in hosts:
            host_name = host.get("name", "")
            host_host = host.get("host", "")
            
            # 检查是否匹配组内主机模式
            for pattern in group_hosts:
                if pattern in host_name or pattern in host_host:
                    host_id = host["hostid"]
                    metrics = self.get_oracle_metrics(host_id)
                    result["hosts"][host_name] = metrics
                    break
        
        # 聚合指标
        if result["hosts"]:
            result["aggregated"] = self._aggregate_metrics(result["hosts"])
        
        return result
    
    def _aggregate_metrics(self, hosts_metrics: Dict[str, Any]) -> Dict[str, Any]:
        """
        聚合多主机指标
        
        参数：
            hosts_metrics: 各主机的指标字典
            
        返回：
            聚合后的指标
        """
        aggregated = {}
        
        # 数值类指标取最大值
        for metric in ["cpu", "memory", "disk_used_percent", "locks", "sessions", "processes"]:
            values = [h[metric] for h in hosts_metrics.values() if h.get(metric) is not None]
            if values:
                aggregated[metric] = max(values)
            else:
                aggregated[metric] = None
        
        # 磁盘容量指标取总和
        for metric in ["disk_total_gb", "disk_used_gb"]:
            values = [h[metric] for h in hosts_metrics.values() if h.get(metric) is not None]
            if values:
                aggregated[metric] = round(sum(values), 2)
            else:
                aggregated[metric] = None
        
        # 性能类指标求和
        for metric in ["iops", "tps", "qps"]:
            values = [h[metric] for h in hosts_metrics.values() if h.get(metric) is not None]
            if values:
                aggregated[metric] = sum(values)
            else:
                aggregated[metric] = None
        
        # 异常数求和
        values = [h["optimizer_errors"] for h in hosts_metrics.values() if h.get("optimizer_errors") is not None]
        aggregated["optimizer_errors"] = sum(values) if values else 0
        
        aggregated["host_count"] = len(hosts_metrics)
        
        return aggregated
