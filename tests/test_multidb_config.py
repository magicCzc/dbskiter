"""
多数据库配置管理测试

文件功能：测试 MultiDBConfig 类的各项功能
主要测试点：
- 实例发现
- 配置加载
- 数据库名查找
- 别名映射

作者：Trae AI
创建时间：2026-04-27
"""

import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from dbskiter.cli.config import MultiDBConfig, Config


def test_list_instances():
    """测试实例发现功能"""
    print("=" * 60)
    print("测试 1: 实例发现 (list_instances)")
    print("=" * 60)
    
    multi_config = MultiDBConfig()
    instances = multi_config.list_instances()
    
    print(f"发现的数据库实例: {instances}")
    
    if instances:
        print(f"[PASS] 成功发现 {len(instances)} 个实例")
        return True
    else:
        print("[WARN] 未发现任何实例，请检查 .env 文件配置")
        return False


def test_get_config():
    """测试通过实例名获取配置"""
    print("\n" + "=" * 60)
    print("测试 2: 通过实例名获取配置 (get_config)")
    print("=" * 60)
    
    multi_config = MultiDBConfig()
    instances = multi_config.list_instances()
    
    if not instances:
        print("[SKIP] 无可用实例，跳过测试")
        return False
    
    success_count = 0
    for instance_name in instances:
        config = multi_config.get_config(instance_name)
        if config:
            print(f"[{instance_name}] Host: {config.host}, Port: {config.port}, Database: {config.database}")
            success_count += 1
        else:
            print(f"[{instance_name}] 获取配置失败")
    
    if success_count == len(instances):
        print(f"[PASS] 所有 {success_count} 个实例配置加载成功")
        return True
    else:
        print(f"[FAIL] 仅 {success_count}/{len(instances)} 个实例配置加载成功")
        return False


def test_find_config_by_database():
    """测试通过数据库名查找配置"""
    print("\n" + "=" * 60)
    print("测试 3: 通过数据库名查找配置 (find_config_by_database)")
    print("=" * 60)
    
    multi_config = MultiDBConfig()
    
    # 测试查找 jump 数据库
    config = multi_config.find_config_by_database('jump')
    if config:
        print(f"[PASS] 找到 jump 数据库配置: {config.host}/{config.database}")
        jump_found = True
    else:
        print("[WARN] 未找到 jump 数据库配置")
        jump_found = False
    
    # 测试查找 chenzc 数据库
    config = multi_config.find_config_by_database('chenzc')
    if config:
        print(f"[PASS] 找到 chenzc 数据库配置: {config.host}/{config.database}")
        chenzc_found = True
    else:
        print("[WARN] 未找到 chenzc 数据库配置")
        chenzc_found = False
    
    # 测试查找不存在的数据库
    config = multi_config.find_config_by_database('nonexistent')
    if not config:
        print("[PASS] 正确返回 None 对于不存在的数据库")
        nonexistent_correct = True
    else:
        print("[FAIL] 应该返回 None 但对于不存在的数据库返回了配置")
        nonexistent_correct = False
    
    return jump_found and chenzc_found and nonexistent_correct


def test_load_all_configs():
    """测试加载所有配置"""
    print("\n" + "=" * 60)
    print("测试 4: 加载所有配置 (load_all_configs)")
    print("=" * 60)
    
    multi_config = MultiDBConfig()
    configs = multi_config.load_all_configs()
    
    print(f"加载的配置数量: {len(configs)}")
    
    for instance_name, config in configs.items():
        print(f"  [{instance_name}] {config.host}:{config.port}/{config.database}")
    
    if configs:
        print(f"[PASS] 成功加载 {len(configs)} 个配置")
        return True
    else:
        print("[WARN] 未加载到任何配置")
        return False


def test_config_from_env_with_mysql2():
    """测试使用 MYSQL2 前缀加载配置"""
    print("\n" + "=" * 60)
    print("测试 5: 使用 MYSQL2 前缀加载配置")
    print("=" * 60)
    
    config = Config.from_env(prefix='MYSQL2')
    
    print(f"Host: {config.host}")
    print(f"Port: {config.port}")
    print(f"Database: {config.database}")
    print(f"Dialect: {config.dialect}")
    
    if config.database == 'chenzc':
        print("[PASS] 成功通过 MYSQL2 前缀加载 chenzc 数据库配置")
        return True
    else:
        print(f"[FAIL] 数据库名不匹配，期望 'chenzc'，实际 '{config.database}'")
        return False


def test_backward_compatibility():
    """测试向后兼容性（DB 前缀）"""
    print("\n" + "=" * 60)
    print("测试 6: 向后兼容性 (DB 前缀)")
    print("=" * 60)
    
    config = Config.from_env(prefix='DB')
    
    print(f"Host: {config.host}")
    print(f"Port: {config.port}")
    print(f"Database: {config.database}")
    
    if config.database == 'jump':
        print("[PASS] DB 前缀配置向后兼容正常")
        return True
    else:
        print(f"[FAIL] 数据库名不匹配，期望 'jump'，实际 '{config.database}'")
        return False


def main():
    """主测试函数"""
    print("\n" + "=" * 60)
    print("多数据库配置管理测试套件")
    print("=" * 60)
    
    results = []
    
    results.append(("实例发现", test_list_instances()))
    results.append(("获取配置", test_get_config()))
    results.append(("数据库名查找", test_find_config_by_database()))
    results.append(("加载所有配置", test_load_all_configs()))
    results.append(("MYSQL2 前缀", test_config_from_env_with_mysql2()))
    results.append(("向后兼容", test_backward_compatibility()))
    
    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "PASS" if result else "FAIL"
        print(f"  [{status}] {test_name}")
    
    print("-" * 60)
    print(f"总计: {passed}/{total} 通过")
    
    if passed == total:
        print("\n所有测试通过!")
        return 0
    else:
        print(f"\n{total - passed} 个测试失败")
        return 1


if __name__ == '__main__':
    sys.exit(main())
