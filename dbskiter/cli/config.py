"""
cli/config.py

配置管理模块

负责：
- 环境变量加载
- 数据库配置管理
- 配置文件支持
"""

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Any, Optional, List
from dotenv import load_dotenv

from .exceptions import ConfigError, ValidationError


@dataclass
class Config:
    """
    配置类
    
    统一管理所有配置项
    
    属性:
        dialect: 数据库类型
        host: 数据库主机
        port: 数据库端口
        username: 用户名
        password: 密码
        database: 数据库名
        extra: 额外配置
    """
    dialect: str = "mysql"
    host: str = "localhost"
    port: int = 3306
    username: str = "root"
    password: str = ""
    database: str = "test"
    extra: Dict[str, Any] = field(default_factory=dict)
    prefix: str = "DB"  # 环境变量前缀，用于多数据库支持
    
    # 类变量：默认配置值
    DEFAULTS = {
        "dialect": "mysql",
        "host": "localhost",
        "port": 3306,
        "username": "root",
        "password": "",
        "database": "test",
    }
    
    # 类变量：环境变量映射
    ENV_MAPPING = {
        "dialect": "DB_DIALECT",
        "host": "DB_HOST",
        "port": "DB_PORT",
        "username": "DB_USER",
        "password": "DB_PASSWORD",
        "database": "DB_NAME",
    }
    
    @classmethod
    def from_env(cls, env_file: Optional[Path] = None, prefix: str = "DB") -> "Config":
        """
        从环境变量加载配置
        
        参数:
            env_file: 可选的 .env 文件路径
            prefix: 环境变量前缀，如 "DB" 或 "ORACLE"
            
        返回:
            Config: 配置对象
            
        示例:
            >>> config = Config.from_env()
            >>> print(config.host)
            >>> config = Config.from_env(prefix="ORACLE")  # 加载 ORACLE_* 变量
        """
        # 加载 .env 文件
        if env_file and env_file.exists():
            load_dotenv(env_file)
        else:
            # 尝试加载默认位置
            default_env = Path(__file__).parent.parent.parent / ".env"
            if default_env.exists():
                load_dotenv(default_env)
        
        # 动态构建环境变量映射
        # 统一使用 _NAME 后缀，同时兼容 _SERVICE（Oracle 等特殊场景）
        database_env_var = f"{prefix}_NAME"
        if prefix != "DB" and not os.getenv(database_env_var):
            # 如果没有 _NAME，尝试 _SERVICE（向后兼容）
            database_env_var = f"{prefix}_SERVICE"
        
        env_mapping = {
            "dialect": f"{prefix}_DIALECT",
            "host": f"{prefix}_HOST",
            "port": f"{prefix}_PORT",
            "username": f"{prefix}_USER",
            "password": f"{prefix}_PASSWORD",
            "database": database_env_var,
        }
        
        # 从环境变量构建配置
        kwargs = {}
        extra = {}
        
        for key, env_var in env_mapping.items():
            value = os.getenv(env_var)
            if value is not None:
                # 类型转换
                if key == "port":
                    try:
                        value = int(value)
                    except ValueError:
                        raise ValidationError(f"环境变量 {env_var} 必须是整数")
                kwargs[key] = value
        
        # Oracle 特殊处理：读取 SERVICE 和 JDBC 驱动配置
        if prefix == "ORACLE":
            service = os.getenv(f"{prefix}_SERVICE")
            if service:
                extra["service_name"] = service
            jdbc_driver = os.getenv(f"{prefix}_JDBC_DRIVER")
            if jdbc_driver:
                extra["jdbc_driver_path"] = jdbc_driver
        
        # 如果没有找到配置，尝试默认 DB_ 前缀（但不递归回退）
        if not kwargs and prefix != "DB":
            # 尝试默认 DB_ 前缀
            env_mapping_default = {
                "dialect": "DB_DIALECT",
                "host": "DB_HOST",
                "port": "DB_PORT",
                "username": "DB_USER",
                "password": "DB_PASSWORD",
                "database": "DB_NAME",
            }
            
            for key, env_var in env_mapping_default.items():
                value = os.getenv(env_var)
                if value is not None:
                    if key == "port":
                        try:
                            value = int(value)
                        except ValueError:
                            raise ValidationError(f"环境变量 {env_var} 必须是整数")
                    kwargs[key] = value
        
        # 如果仍然没有找到任何配置，抛出错误
        if not kwargs:
            raise ConfigError(f"未找到数据库配置，请设置 {prefix}_* 环境变量，或使用 --database 参数指定已配置的数据库")
        
        # 添加 extra 和 prefix
        kwargs["extra"] = extra
        kwargs["prefix"] = prefix
        
        return cls(**kwargs)
    
    @classmethod
    def from_args(cls, args) -> "Config":
        """
        从命令行参数加载配置（支持配置文件）
        
        参数:
            args: argparse 解析后的参数对象
            
        返回:
            Config: 配置对象
            
        示例:
            >>> args = parser.parse_args()
            >>> config = Config.from_args(args)
        """
        from .config_file import ConfigFileManager
        
        # 加载顺序：环境变量 -> 配置文件 -> 命令行参数
        
        # 1. 从环境变量加载基础配置
        config = cls.from_env()
        
        # 2. 从配置文件加载（如果指定了 --config 或存在默认配置）
        config_path = getattr(args, "config", None)
        profile = getattr(args, "profile", None)
        
        if config_path or not any([
            getattr(args, "dialect", None),
            getattr(args, "host", None),
            getattr(args, "database", None)
        ]):
            try:
                manager = ConfigFileManager(
                    Path(config_path) if config_path else None
                )
                profile_config = manager.load_profile(profile)
                
                # 用配置文件覆盖环境变量
                if profile_config.dialect:
                    config.dialect = profile_config.dialect
                if profile_config.host:
                    config.host = profile_config.host
                if profile_config.port:
                    config.port = profile_config.port
                if profile_config.username:
                    config.username = profile_config.username
                if profile_config.password:
                    config.password = profile_config.password
                if profile_config.database:
                    config.database = profile_config.database
                    
            except Exception:
                # 配置文件加载失败，继续使用环境变量配置
                pass
        
        # 3. 用命令行参数覆盖（优先级最高）
        if hasattr(args, "dialect") and args.dialect:
            config.dialect = args.dialect
        if hasattr(args, "host") and args.host:
            config.host = args.host
        if hasattr(args, "port") and args.port:
            config.port = args.port
        if hasattr(args, "user") and args.user:
            config.username = args.user
        if hasattr(args, "password") and args.password:
            config.password = args.password
        if hasattr(args, "database") and args.database:
            config.database = args.database
        
        return config
    
    def validate(self) -> None:
        """
        验证配置有效性
        
        异常:
            ValidationError: 配置无效时抛出
        """
        # 验证数据库类型（支持多种 Oracle 写法）
        valid_dialects = ["mysql", "mysql+pymysql", "postgresql", "sqlite", "sqlite3", 
                         "oracle", "oracle+oracledb", "oracle+jdbc", "oracle+cx_oracle"]
        if self.dialect not in valid_dialects:
            raise ValidationError(
                f"不支持的数据库类型: {self.dialect}，"
                f"支持的类型: {', '.join(valid_dialects)}"
            )
        
        # 验证端口范围
        if not 1 <= self.port <= 65535:
            raise ValidationError(f"端口号必须在 1-65535 之间: {self.port}")
        
        # 验证必填项
        if not self.database:
            raise ValidationError("数据库名不能为空")
        
        # SQLite 特殊处理
        if self.dialect in ("sqlite", "sqlite3"):
            # SQLite 不需要 host/port/username/password
            pass
        else:
            # 其他数据库需要 host
            if not self.host:
                raise ValidationError("数据库主机不能为空")
    
    def to_dict(self) -> Dict[str, Any]:
        """
        转换为字典
        
        返回:
            Dict: 配置字典
        """
        return {
            "dialect": self.dialect,
            "host": self.host,
            "port": self.port,
            "username": self.username,
            "password": self.password,
            "database": self.database,
            **self.extra
        }
    
    def __repr__(self) -> str:
        # 隐藏密码
        return (
            f"Config(dialect='{self.dialect}', host='{self.host}', "
            f"port={self.port}, username='{self.username}', "
            f"password='***', database='{self.database}')"
        )


class MultiDBConfig:
    """
    多数据库配置管理器 - 使用别名方式管理
    
    统一管理多个数据库实例的配置，支持使用有意义的别名（如 jump, chenzc, orcl）
    
    配置格式:
        DB_{别名}_HOST=192.168.1.1
        DB_{别名}_PORT=3306
        DB_{别名}_NAME=dbname
        ...
    
    使用示例:
        >>> multi_config = MultiDBConfig()
        >>> 
        >>> # 获取所有配置的数据库别名
        >>> aliases = multi_config.list_aliases()
        >>> print(aliases)  # ['jump', 'chenzc', 'orcl']
        >>> 
        >>> # 通过别名获取配置
        >>> config = multi_config.get_config_by_alias('jump')
        >>> 
        >>> # 通过数据库名查找配置（向后兼容）
        >>> config = multi_config.find_config_by_database('jump')
        >>> 
        >>> # 获取所有配置
        >>> all_configs = multi_config.load_all_configs()
    """
    
    # 别名模式：DB_{ALIAS}_HOST
    ALIAS_PATTERN = re.compile(r'^DB_([A-Z0-9_]+)_HOST$')
    
    def __init__(self, env_file: Optional[Path] = None):
        """
        初始化多数据库配置管理器
        
        参数:
            env_file: 可选的 .env 文件路径
        """
        # 加载 .env 文件
        if env_file and env_file.exists():
            load_dotenv(env_file)
        else:
            default_env = Path(__file__).parent.parent.parent / ".env"
            if default_env.exists():
                load_dotenv(default_env)
    
    def list_aliases(self) -> List[str]:
        """
        获取所有配置的数据库别名
        
        通过扫描 DB_{ALIAS}_HOST 格式的环境变量来发现别名
        
        返回:
            List[str]: 别名列表（如 ['jump', 'chenzc', 'orcl']）
            
        示例:
            >>> multi_config = MultiDBConfig()
            >>> aliases = multi_config.list_aliases()
            >>> print(aliases)
            ['jump', 'chenzc', 'orcl']
        """
        aliases = []
        
        for key in os.environ.keys():
            match = self.ALIAS_PATTERN.match(key)
            if match:
                alias = match.group(1).lower()  # 转换为小写
                aliases.append(alias)
        
        return sorted(aliases)
    
    def list_instances(self) -> List[str]:
        """
        向后兼容：返回所有实例标识（使用别名）
        """
        return self.list_aliases()
    
    def get_config_by_alias(self, alias: str) -> Optional[Config]:
        """
        通过别名获取配置
        
        参数:
            alias: 数据库别名（如 'jump', 'chenzc', 'orcl'）
            
        返回:
            Optional[Config]: 配置对象，如果不存在返回 None
            
        示例:
            >>> multi_config = MultiDBConfig()
            >>> config = multi_config.get_config_by_alias('jump')
            >>> if config:
            ...     print(f"Host: {config.host}, Database: {config.database}")
        """
        # 构建前缀：DB_{ALIAS}
        prefix = f"DB_{alias.upper()}"
        
        try:
            config = Config.from_env(prefix=prefix)
            # 验证配置是否有效
            if config.host and config.host not in ("localhost", "127.0.0.1"):
                # 保存别名信息
                config.extra['alias'] = alias.lower()
                return config
        except Exception:
            pass
        
        return None
    
    def get_config(self, instance_name: str) -> Optional[Config]:
        """
        向后兼容：通过实例名/别名获取配置
        
        参数:
            instance_name: 实例名或别名（如 'jump', 'DB', 'ORACLE'）
        """
        # 首先尝试作为别名获取
        config = self.get_config_by_alias(instance_name.lower())
        if config:
            return config
        
        # 向后兼容：尝试旧的前缀方式
        try:
            config = Config.from_env(prefix=instance_name)
            if config.host and config.host not in ("localhost", "127.0.0.1"):
                return config
        except Exception:
            pass
        
        return None
    
    def find_config_by_database(self, database_name: str) -> Optional[Config]:
        """
        通过数据库名查找配置
        
        在所有配置的实例中搜索匹配的数据库名
        
        参数:
            database_name: 数据库名（如 'jump', 'chenzc'）
            
        返回:
            Optional[Config]: 匹配的配置对象，如果不存在返回 None
            
        示例:
            >>> multi_config = MultiDBConfig()
            >>> config = multi_config.find_config_by_database('chenzc')
            >>> if config:
            ...     print(f"Found config for chenzc: {config.host}")
        """
        for instance_name in self.list_instances():
            config = self.get_config(instance_name)
            if config and config.database == database_name:
                return config
        return None
    
    def load_all_configs(self) -> Dict[str, Config]:
        """
        加载所有有效的数据库配置
        
        返回:
            Dict[str, Config]: 配置字典，key为别名，value为配置对象
            
        示例:
            >>> multi_config = MultiDBConfig()
            >>> configs = multi_config.load_all_configs()
            >>> for alias, config in configs.items():
            ...     print(f"{alias}: {config.host}/{config.database}")
        """
        configs = {}
        for alias in self.list_aliases():
            config = self.get_config_by_alias(alias)
            if config:
                configs[alias] = config
        return configs
    
    def get_alias_by_database(self, database_name: str) -> Optional[str]:
        """
        通过数据库名获取别名
        
        参数:
            database_name: 数据库名
            
        返回:
            Optional[str]: 别名，如果不存在返回 None
        """
        for alias in self.list_aliases():
            config = self.get_config_by_alias(alias)
            if config and config.database == database_name:
                return alias
        return None
    
    def get_instance_by_database(self, database_name: str) -> Optional[str]:
        """
        向后兼容：通过数据库名获取实例名/别名
        """
        return self.get_alias_by_database(database_name)


# 兼容性函数
def get_db_config(args) -> Dict[str, Any]:
    """
    获取数据库配置（兼容旧接口）
    
    参数:
        args: 命令行参数
        
    返回:
        Dict: 数据库配置字典
        
    注意:
        此函数为兼容性保留，新代码建议使用 Config.from_args()
    """
    config = Config.from_args(args)
    config.validate()
    return config.to_dict()
