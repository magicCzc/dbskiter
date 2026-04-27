"""
cli/config_file.py

配置文件管理模块

支持 YAML、JSON、TOML 格式的配置文件
"""

import json
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False

try:
    import toml
    HAS_TOML = True
except ImportError:
    HAS_TOML = False

from .exceptions import ConfigError


@dataclass
class ProfileConfig:
    """
    配置文件中的单个 profile
    
    属性:
        dialect: 数据库类型
        host: 数据库主机
        port: 数据库端口
        username: 用户名
        password: 密码
        database: 数据库名
    """
    dialect: str = "mysql"
    host: str = "localhost"
    port: int = 3306
    username: str = "root"
    password: str = ""
    database: str = ""
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProfileConfig":
        """从字典创建配置"""
        return cls(
            dialect=data.get("dialect", "mysql"),
            host=data.get("host", "localhost"),
            port=data.get("port", 3306),
            username=data.get("username", data.get("user", "root")),
            password=data.get("password", ""),
            database=data.get("database", data.get("db", "")),
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return asdict(self)


class ConfigFileManager:
    """
    配置文件管理器
    
    管理配置文件的读取、写入和解析
    
    用法:
        >>> manager = ConfigFileManager()
        >>> config = manager.load_profile("production")
    """
    
    # 默认配置文件路径（按优先级排序）
    DEFAULT_PATHS = [
        Path("./dbskiter.yaml"),
        Path("./dbskiter.yml"),
        Path("./dbskiter.json"),
        Path("./dbskiter.toml"),
        Path.home() / ".config" / "dbskiter" / "config.yaml",
        Path.home() / ".dbskiter.yaml",
    ]
    
    def __init__(self, config_path: Optional[Path] = None):
        """
        初始化配置文件管理器
        
        参数:
            config_path: 配置文件路径，None 表示自动查找
        """
        self.config_path = config_path
        self._config_data: Optional[Dict[str, Any]] = None
    
    def find_config_file(self) -> Optional[Path]:
        """
        查找配置文件
        
        返回:
            Optional[Path]: 找到的配置文件路径，未找到返回 None
        """
        # 如果指定了路径，直接使用
        if self.config_path:
            if self.config_path.exists():
                return self.config_path
            return None
        
        # 按优先级查找
        for path in self.DEFAULT_PATHS:
            if path.exists():
                return path
        
        return None
    
    def load(self) -> Dict[str, Any]:
        """
        加载配置文件
        
        返回:
            Dict: 配置数据
            
        异常:
            ConfigError: 配置文件不存在或格式错误
        """
        config_file = self.find_config_file()
        
        if not config_file:
            if self.config_path:
                raise ConfigError(f"配置文件不存在: {self.config_path}")
            return {}  # 没有配置文件返回空字典
        
        try:
            content = config_file.read_text(encoding="utf-8")
            
            # 根据扩展名解析
            suffix = config_file.suffix.lower()
            
            if suffix in (".yaml", ".yml"):
                if not HAS_YAML:
                    raise ConfigError("需要安装 PyYAML 才能解析 YAML 文件: pip install pyyaml")
                self._config_data = yaml.safe_load(content) or {}
                
            elif suffix == ".json":
                self._config_data = json.loads(content)
                
            elif suffix == ".toml":
                if not HAS_TOML:
                    raise ConfigError("需要安装 toml 才能解析 TOML 文件: pip install toml")
                self._config_data = toml.loads(content)
                
            else:
                raise ConfigError(f"不支持的配置文件格式: {suffix}")
            
            return self._config_data
            
        except json.JSONDecodeError as e:
            raise ConfigError(f"JSON 解析错误 ({config_file}): {e}")
        except yaml.YAMLError as e:
            raise ConfigError(f"YAML 解析错误 ({config_file}): {e}")
        except Exception as e:
            raise ConfigError(f"配置文件读取失败 ({config_file}): {e}")
    
    def load_profile(self, profile_name: Optional[str] = None) -> ProfileConfig:
        """
        加载指定 profile
        
        参数:
            profile_name: profile 名称，None 使用 default
            
        返回:
            ProfileConfig: 配置对象
        """
        data = self.load()
        
        # 获取 profiles
        profiles = data.get("profiles", {})
        
        # 确定使用哪个 profile
        if profile_name:
            profile_data = profiles.get(profile_name, {})
        else:
            # 使用 default profile 或第一个 profile
            default_name = data.get("default_profile")
            if default_name and default_name in profiles:
                profile_data = profiles[default_name]
            elif profiles:
                profile_data = next(iter(profiles.values()))
            else:
                profile_data = data  # 直接使用根级配置
        
        return ProfileConfig.from_dict(profile_data)
    
    def list_profiles(self) -> list:
        """
        列出所有可用的 profiles
        
        返回:
            list: profile 名称列表
        """
        data = self.load()
        profiles = data.get("profiles", {})
        return list(profiles.keys())
    
    def save(self, data: Dict[str, Any], path: Optional[Path] = None) -> None:
        """
        保存配置文件
        
        参数:
            data: 配置数据
            path: 保存路径，None 使用当前路径
        """
        save_path = path or self.config_path
        if not save_path:
            save_path = Path("./dbskiter.yaml")
        
        # 确保目录存在
        save_path.parent.mkdir(parents=True, exist_ok=True)
        
        suffix = save_path.suffix.lower()
        
        if suffix in (".yaml", ".yml"):
            if not HAS_YAML:
                raise ConfigError("需要安装 PyYAML: pip install pyyaml")
            content = yaml.dump(data, default_flow_style=False, allow_unicode=True)
            
        elif suffix == ".json":
            content = json.dumps(data, indent=2, ensure_ascii=False)
            
        elif suffix == ".toml":
            if not HAS_TOML:
                raise ConfigError("需要安装 toml: pip install toml")
            content = toml.dumps(data)
            
        else:
            # 默认使用 YAML
            if not HAS_YAML:
                raise ConfigError("需要安装 PyYAML: pip install pyyaml")
            content = yaml.dump(data, default_flow_style=False, allow_unicode=True)
        
        save_path.write_text(content, encoding="utf-8")
    
    def create_sample_config(self, path: Optional[Path] = None) -> Path:
        """
        创建示例配置文件
        
        参数:
            path: 保存路径，None 使用默认路径
            
        返回:
            Path: 创建的文件路径
        """
        sample_data = {
            "default_profile": "development",
            "profiles": {
                "development": {
                    "dialect": "mysql",
                    "host": "localhost",
                    "port": 3306,
                    "username": "root",
                    "password": "",
                    "database": "dev_db"
                },
                "production": {
                    "dialect": "mysql",
                    "host": "prod.db.example.com",
                    "port": 3306,
                    "username": "app_user",
                    "password": "${DB_PASSWORD}",  # 可以使用环境变量
                    "database": "prod_db"
                },
                "testing": {
                    "dialect": "sqlite",
                    "database": "./test.db"
                }
            },
            "settings": {
                "default_output_format": "table",
                "max_rows": 1000,
                "timeout": 30
            }
        }
        
        save_path = path or Path("./dbskiter.yaml")
        self.save(sample_data, save_path)
        return save_path


def load_config_with_profile(
    config_path: Optional[str] = None,
    profile: Optional[str] = None
) -> Dict[str, Any]:
    """
    便捷函数：加载配置文件和 profile
    
    参数:
        config_path: 配置文件路径
        profile: profile 名称
        
    返回:
        Dict: 配置字典
    """
    path = Path(config_path) if config_path else None
    manager = ConfigFileManager(path)
    profile_config = manager.load_profile(profile)
    return profile_config.to_dict()
