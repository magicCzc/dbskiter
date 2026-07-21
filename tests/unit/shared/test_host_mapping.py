"""
tests/unit/shared/test_host_mapping.py
HostMappingManager 单元测试
"""

import json
import os
import tempfile

import pytest

from dbskiter.shared.host_mapping import HostInfo, HostMappingManager


class TestHostInfo:
    """HostInfo 数据类测试"""

    def test_create_host_info(self):
        """创建 HostInfo"""
        info = HostInfo(prometheus_name="rds-xxx", zabbix_name="host-01")
        assert info.prometheus_name == "rds-xxx"
        assert info.zabbix_name == "host-01"
        assert info.zabbix_hostid is None
        assert info.ip_address is None

    def test_is_mapped_true(self):
        """is_mapped 返回 True（已映射）"""
        info = HostInfo(prometheus_name="rds-xxx", zabbix_name="host-01")
        assert info.is_mapped is True

    def test_is_mapped_false(self):
        """is_mapped 返回 False（未映射）"""
        info = HostInfo(prometheus_name="rds-xxx")
        assert info.is_mapped is False


class TestHostMappingManagerInit:
    """初始化测试"""

    def test_init_without_file(self):
        """无文件初始化"""
        manager = HostMappingManager()
        assert manager.mappings == {}
        assert manager.mapping_file is None

    def test_init_with_nonexistent_file(self):
        """指定不存在的文件"""
        manager = HostMappingManager("/nonexistent/file.json")
        assert manager.mappings == {}

    def test_init_with_valid_file(self):
        """指定有效文件"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"rds-xxx": "host-01"}, f)
            tmpfile = f.name
        try:
            manager = HostMappingManager(tmpfile)
            assert manager.mappings == {"rds-xxx": "host-01"}
        finally:
            os.unlink(tmpfile)

    def test_init_with_invalid_json(self):
        """无效 JSON 文件"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("not valid json")
            tmpfile = f.name
        try:
            manager = HostMappingManager(tmpfile)
            # 应捕获异常，返回空映射
            assert manager.mappings == {}
        finally:
            os.unlink(tmpfile)


class TestHostMappingManagerBasic:
    """基本方法测试"""

    def test_get_zabbix_name_direct_match(self):
        """直接匹配"""
        manager = HostMappingManager()
        manager.mappings = {"rds-xxx": "host-01"}
        assert manager.get_zabbix_name("rds-xxx") == "host-01"

    def test_get_zabbix_name_not_found(self):
        """找不到"""
        manager = HostMappingManager()
        assert manager.get_zabbix_name("unknown") is None

    def test_get_zabbix_name_rds_prefix_fuzzy(self):
        """rds- 前缀模糊匹配"""
        manager = HostMappingManager()
        manager.mappings = {"xxx": "host-01"}
        # 去掉 rds- 前缀后匹配
        assert manager.get_zabbix_name("rds-xxx") == "host-01"

    def test_get_prometheus_name(self):
        """反向查找"""
        manager = HostMappingManager()
        manager.mappings = {"rds-xxx": "host-01", "rds-yyy": "host-02"}
        assert manager.get_prometheus_name("host-01") == "rds-xxx"
        assert manager.get_prometheus_name("host-02") == "rds-yyy"
        assert manager.get_prometheus_name("unknown") is None

    def test_add_mapping(self):
        """添加映射"""
        manager = HostMappingManager()
        manager.add_mapping("rds-xxx", "host-01", save=False)
        assert manager.mappings["rds-xxx"] == "host-01"

    def test_remove_mapping(self):
        """移除映射"""
        manager = HostMappingManager()
        manager.mappings = {"rds-xxx": "host-01"}
        manager.remove_mapping("rds-xxx", save=False)
        assert "rds-xxx" not in manager.mappings

    def test_remove_nonexistent(self):
        """移除不存在的映射"""
        manager = HostMappingManager()
        # 不应抛异常
        manager.remove_mapping("nonexistent", save=False)
        assert manager.mappings == {}

    def test_list_mappings(self):
        """列出所有映射"""
        manager = HostMappingManager()
        manager.mappings = {"a": "1", "b": "2"}
        result = manager.list_mappings()
        assert result == {"a": "1", "b": "2"}

    def test_list_mappings_returns_copy(self):
        """list_mappings 返回副本"""
        manager = HostMappingManager()
        manager.mappings = {"a": "1"}
        result = manager.list_mappings()
        result["b"] = "2"
        # 原 mappings 不应受影响
        assert "b" not in manager.mappings


class TestHostMappingManagerPersistence:
    """持久化测试"""

    def test_save_mappings(self):
        """保存映射到文件"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            tmpfile = f.name
        try:
            manager = HostMappingManager(tmpfile)
            manager.add_mapping("rds-xxx", "host-01", save=True)
            # 重新加载
            manager2 = HostMappingManager(tmpfile)
            assert manager2.mappings["rds-xxx"] == "host-01"
        finally:
            os.unlink(tmpfile)

    def test_save_and_remove(self):
        """保存后移除"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            tmpfile = f.name
        try:
            manager = HostMappingManager(tmpfile)
            manager.add_mapping("rds-xxx", "host-01", save=True)
            manager.remove_mapping("rds-xxx", save=True)
            manager2 = HostMappingManager(tmpfile)
            assert "rds-xxx" not in manager2.mappings
        finally:
            os.unlink(tmpfile)

    def test_no_save_when_no_file(self):
        """无文件时 save=True 不应抛异常"""
        manager = HostMappingManager()
        manager.add_mapping("rds-xxx", "host-01", save=True)
        # 不应抛异常
        assert manager.mappings["rds-xxx"] == "host-01"


class TestHostMappingManagerAutoDiscover:
    """自动发现测试"""

    def test_auto_discover_with_existing_mapping(self):
        """已有映射的自动发现"""
        manager = HostMappingManager()
        manager.mappings = {"rds-xxx": "host-01"}
        result = manager.auto_discover(["rds-xxx"], [])
        assert len(result) == 1
        assert result[0].zabbix_name == "host-01"

    def test_auto_discover_with_rds_match(self):
        """rds- 匹配"""
        manager = HostMappingManager()
        zabbix_hosts = [
            {"name": "RDS_XXX_231_NODE1", "host": "host1", "hostid": "1001"},
        ]
        result = manager.auto_discover(["rds-xxx"], zabbix_hosts)
        assert len(result) == 1
        assert result[0].zabbix_name == "RDS_XXX_231_NODE1"
        assert result[0].zabbix_hostid == "1001"

    def test_auto_disprefer_no_match(self):
        """无匹配时 zabbix_name 为 None"""
        manager = HostMappingManager()
        zabbix_hosts = [
            {"name": "RDS_YYY_231_NODE1", "host": "host1", "hostid": "1001"},
        ]
        result = manager.auto_discover(["rds-xxx"], zabbix_hosts)
        assert len(result) == 1
        assert result[0].zabbix_name is None

    def test_auto_discover_prefer_231(self):
        """优先选择 231 节点"""
        manager = HostMappingManager()
        zabbix_hosts = [
            {"name": "RDS_XXX_232_NODE1", "host": "host1", "hostid": "1001"},
            {"name": "RDS_XXX_231_NODE1", "host": "host2", "hostid": "1002"},
        ]
        result = manager.auto_discover(["rds-xxx"], zabbix_hosts)
        assert result[0].zabbix_name == "RDS_XXX_231_NODE1"


class TestHostMappingManagerGetAllClusterNodes:
    """get_all_cluster_nodes 测试"""

    def test_get_cluster_nodes(self):
        """获取集群所有节点"""
        manager = HostMappingManager()
        zabbix_hosts = [
            {"name": "RDS_XXX_231_NODE1", "host": "h1", "hostid": "1"},
            {"name": "RDS_XXX_232_NODE1", "host": "h2", "hostid": "2"},
            {"name": "RDS_YYY_231_NODE1", "host": "h3", "hostid": "3"},
        ]
        nodes = manager.get_all_cluster_nodes("rds-xxx", zabbix_hosts)
        assert len(nodes) == 2
        # 应该按 231, 232 排序
        assert nodes[0]["name"] == "RDS_XXX_231_NODE1"

    def test_get_cluster_nodes_no_match(self):
        """无匹配"""
        manager = HostMappingManager()
        zabbix_hosts = [
            {"name": "OTHER_231_NODE1", "host": "h1", "hostid": "1"},
        ]
        nodes = manager.get_all_cluster_nodes("rds-xxx", zabbix_hosts)
        assert nodes == []

    def test_get_cluster_nodes_invalid_name(self):
        """无效名称"""
        manager = HostMappingManager()
        nodes = manager.get_all_cluster_nodes("not_rds_name", [])
        assert nodes == []


class TestHostMappingManagerSuggest:
    """suggest_mapping 测试"""

    def test_suggest_with_match(self):
        """有匹配时返回建议"""
        manager = HostMappingManager()
        zabbix_hosts = [
            {"name": "host-xxx-server", "host": "host-xxx-server", "hostid": "1001"},
            {"name": "OTHER_DB", "host": "host2", "hostid": "1002"},
        ]
        suggestions = manager.suggest_mapping("host-xxx", zabbix_hosts)
        # host-xxx 是 host-xxx-server 的子串，应该匹配
        assert len(suggestions) > 0
        # 第一个应该是最匹配的
        assert suggestions[0]["name"] == "host-xxx-server"

    def test_suggest_returns_max_5(self):
        """最多返回 5 个建议"""
        manager = HostMappingManager()
        zabbix_hosts = [
            {"name": f"RDS_XXX_{i}", "host": f"h{i}", "hostid": str(i)}
            for i in range(10)
        ]
        suggestions = manager.suggest_mapping("rds-xxx", zabbix_hosts)
        assert len(suggestions) <= 5

    def test_suggest_no_match(self):
        """无匹配"""
        manager = HostMappingManager()
        zabbix_hosts = [
            {"name": "UNRELATED", "host": "host1", "hostid": "1001"},
        ]
        suggestions = manager.suggest_mapping("rds-xxx", zabbix_hosts)
        # 关键字重叠可能产生低分建议，但无任何匹配
        # 测试有/无建议均可，但不应有完全匹配
        for s in suggestions:
            assert s["name"] != "UNRELATED"