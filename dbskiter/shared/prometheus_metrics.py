"""
Prometheus 指标定义库

文件功能：定义从 Grafana 看板提取的所有指标
主要类：MySQLMetrics, OracleMetrics, NodeMetrics

作者：Trae AI
创建时间：2026-04-17
"""

from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta


class MySQLRDSMetrics:
    """
    MySQL RDS 指标定义（来自 mysql.json 看板）
    
    数据源：华为云 RDS (Prometheus)
    """
    
    # 核心性能指标
    METRICS = {
        # 基础资源
        "cpu": {
            "name": "huaweicloud_sys_rds_rds001_cpu_util",
            "description": "CPU 使用率",
            "unit": "%",
            "threshold": 80
        },
        "memory": {
            "name": "huaweicloud_sys_rds_rds002_mem_util", 
            "description": "内存使用率",
            "unit": "%",
            "threshold": 90
        },
        "disk_util": {
            "name": "huaweicloud_sys_rds_rds039_disk_util",
            "description": "磁盘使用率",
            "unit": "%",
            "threshold": 85
        },
        "vm_ioutils": {
            "name": "huaweicloud_sys_rds_rds081_vm_ioutils",
            "description": "磁盘 IO 使用率",
            "unit": "%",
            "threshold": 80
        },
        
        # 连接和性能
        "connections_active": {
            "name": "huaweicloud_sys_rds_rds007_conn_active_count",
            "description": "活跃连接数",
            "unit": "count",
            "threshold": 1000
        },
        "tps": {
            "name": "huaweicloud_sys_rds_rds009_tps",
            "description": "每秒事务数",
            "unit": "tps",
            "threshold": None
        },
        "iops": {
            "name": "huaweicloud_sys_rds_rds003_iops",
            "description": "IOPS",
            "unit": "iops",
            "threshold": None
        },
        
        # 慢查询和锁
        "slow_queries": {
            "name": "huaweicloud_sys_rds_rds074_slow_queries",
            "description": "慢查询数",
            "unit": "count",
            "threshold": 10
        },
        "innodb_row_lock_waits": {
            "name": "huaweicloud_sys_rds_rds_innodb_row_lock_current_waits",
            "description": "InnoDB 行锁等待",
            "unit": "count",
            "threshold": 5
        },
        
        # 网络流量
        "bytes_in": {
            "name": "huaweicloud_sys_rds_rds004_bytes_in",
            "description": "网络入流量",
            "unit": "bytes/s",
            "threshold": None
        },
        "bytes_out": {
            "name": "huaweicloud_sys_rds_rds005_bytes_out",
            "description": "网络出流量",
            "unit": "bytes/s",
            "threshold": None
        }
    }
    
    @classmethod
    def get_metric_names(cls) -> List[str]:
        """获取所有指标名称列表"""
        return list(cls.METRICS.keys())
    
    @classmethod
    def get_promql(cls, metric_name: str, instance: str) -> Optional[str]:
        """
        生成 PromQL 查询语句
        
        参数：
            metric_name: 指标名（如 cpu, memory）
            instance: RDS 实例名
            
        返回：
            PromQL 字符串
        """
        metric = cls.METRICS.get(metric_name)
        if not metric:
            return None
        
        return f'{metric["name"]}{{name="{instance}"}}'


class NodeExporterMetrics:
    """
    Node Exporter 系统指标（来自 mysql.json/oracle.json 看板）
    
    数据源：服务器节点监控 (Prometheus)
    """
    
    METRICS = {
        # CPU
        "cpu_count": {
            "name": "node_cpu_seconds_total",
            "description": "CPU 核心数",
            "unit": "cores",
            "query": 'count(node_cpu_seconds_total{{job=~"$job",mode="system",tag=~"$groups"}})'
        },
        "cpu_util": {
            "name": "node_cpu_seconds_total",
            "description": "CPU 使用率",
            "unit": "%",
            "query": '(1 - avg(irate(node_cpu_seconds_total{{job=~"$job",mode="idle",tag=~"$groups"}}[5m]))) * 100'
        },
        "load1": {
            "name": "node_load1",
            "description": "1分钟负载",
            "unit": "",
            "query": "node_load1{{job=~\"$job\",tag=~\"$groups\"}}"
        },
        
        # 内存
        "memory_total": {
            "name": "node_memory_MemTotal_bytes",
            "description": "内存总量",
            "unit": "bytes",
            "query": "node_memory_MemTotal_bytes{{job=~\"$job\",tag=~\"$groups\"}}"
        },
        "memory_used_percent": {
            "name": "node_memory_MemAvailable_bytes",
            "description": "内存使用率",
            "unit": "%",
            "query": '(1 - (node_memory_MemAvailable_bytes{{job=~"$job",tag=~"$groups"}} / node_memory_MemTotal_bytes{{job=~"$job",tag=~"$groups"}})) * 100'
        },
        
        # 磁盘
        "disk_used_percent": {
            "name": "node_filesystem_size_bytes",
            "description": "磁盘使用率",
            "unit": "%",
            "query": '(node_filesystem_size_bytes{{job=~"$job",fstype=~"ext.?|xfs"}} - node_filesystem_free_bytes{{job=~"$job",fstype=~"ext.?|xfs"}}) * 100 / node_filesystem_size_bytes{{job=~"$job",fstype=~"ext.?|xfs"}}'
        },
        "disk_read_bytes": {
            "name": "node_disk_read_bytes_total",
            "description": "磁盘读取速率",
            "unit": "bytes/s",
            "query": 'irate(node_disk_read_bytes_total{{job=~"$job",tag=~"$groups"}}[5m])'
        },
        "disk_write_bytes": {
            "name": "node_disk_written_bytes_total",
            "description": "磁盘写入速率",
            "unit": "bytes/s",
            "query": 'irate(node_disk_written_bytes_total{{job=~"$job",tag=~"$groups"}}[5m])'
        },
        
        # 网络
        "net_receive_bytes": {
            "name": "node_network_receive_bytes_total",
            "description": "网络接收速率",
            "unit": "bits/s",
            "query": 'irate(node_network_receive_bytes_total{{job=~"$job",tag=~"$groups"}}[5m]) * 8'
        },
        "net_transmit_bytes": {
            "name": "node_network_transmit_bytes_total",
            "description": "网络发送速率",
            "unit": "bits/s",
            "query": 'irate(node_network_transmit_bytes_total{{job=~"$job",tag=~"$groups"}}[5m]) * 8'
        },
        
        # 系统
        "uptime": {
            "name": "node_boot_time_seconds",
            "description": "运行时间",
            "unit": "seconds",
            "query": "time() - node_boot_time_seconds{{job=~\"$job\",tag=~\"$groups\"}}"
        }
    }


class JVMMetrics:
    """
    JVM 应用指标（来自 mysql.json/oracle.json 看板）
    
    数据源：Java 应用监控 (Prometheus)
    """
    
    METRICS = {
        "jvm_memory_heap_used": {
            "name": "jvm_memory_bytes_used",
            "description": "JVM 堆内存使用",
            "unit": "bytes",
            "query": 'jvm_memory_bytes_used{{area="heap",instance="$instance",role="$service"}}'
        },
        "jvm_memory_heap_percent": {
            "name": "jvm_memory_bytes_used",
            "description": "JVM 堆内存使用率",
            "unit": "%",
            "query": 'jvm_memory_bytes_used{{area="heap",instance="$instance",role="$service"}} / jvm_memory_bytes_max * 100'
        },
        "jvm_threads_current": {
            "name": "jvm_threads_current",
            "description": "当前线程数",
            "unit": "count",
            "query": 'jvm_threads_current{{instance="$instance",role="$service"}}'
        },
        "jvm_threads_peak": {
            "name": "jvm_threads_peak",
            "description": "峰值线程数",
            "unit": "count",
            "query": 'jvm_threads_peak{{instance="$instance",role="$service"}}'
        },
        "jvm_threads_deadlocked": {
            "name": "jvm_threads_deadlocked",
            "description": "死锁线程数",
            "unit": "count",
            "query": 'jvm_threads_deadlocked{{instance="$instance",role="$service"}}'
        },
        "up": {
            "name": "up",
            "description": "应用存活状态",
            "unit": "",
            "query": 'up{{instance="$instance",role="$service"}}'
        }
    }


class RedisMetrics:
    """
    Redis 指标（来自 mysql.json/oracle.json 看板）
    
    数据源：Redis 监控 (Prometheus)
    """
    
    METRICS = {
        "cluster_state": {
            "name": "redis_cluster_state",
            "description": "集群状态",
            "unit": "",
            "query": 'redis_cluster_state{{instance=~"${groups}-Web-Redis-Master-1"}}'
        },
        "db_keys": {
            "name": "redis_db_keys",
            "description": "数据库键数量",
            "unit": "count",
            "query": 'sum(redis_db_keys{{instance=~"$redis_cluster_db_master"}})'
        }
    }
