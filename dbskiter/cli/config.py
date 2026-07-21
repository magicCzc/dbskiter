"""
cli/config.py

配置管理模块

负责：
- 环境变量加载
- 数据库配置管理
- 配置文件支持
"""

import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Any, Optional, List
from dotenv import dotenv_values

from .exceptions import ConfigError, ValidationError

logger = logging.getLogger(__name__)

# 全局缓存：避免重复解析 .env 文件
_ENV_CACHE: Optional[Dict[str, Optional[str]]] = None


def _load_env_values(env_file: Optional[Path] = None) -> Dict[str, Optional[str]]:
    """
    使用 dotenv_values 加载 .env 文件（不修改全局 os.environ）

    功能说明：
        - 优先使用缓存，避免重复解析
        - 同时同步到 os.environ，确保其他模块兼容
        - 使用 dotenv_values 替代 load_dotenv，避免环境变量冲突

    参数说明：
        - env_file: 可选的 .env 文件路径

    返回说明：
        - Dict[str, Optional[str]]: 环境变量字典

    使用示例：
        >>> values = _load_env_values()
        >>> print(values.get('DB_HOST'))
    """
    global _ENV_CACHE
    if _ENV_CACHE is not None:
        return _ENV_CACHE

    found_env = _find_env_file(env_file)
    if found_env:
        try:
            # 临时抑制 dotenv.main 的解析警告
            # .env 文件中注释行包含特殊字符（如 : 或 =）时，
            # python-dotenv 会误报 "could not parse statement" 警告
            dotenv_logger = logging.getLogger("dotenv.main")
            original_level = dotenv_logger.level
            dotenv_logger.setLevel(logging.ERROR)

            try:
                values = dict(dotenv_values(found_env))
            finally:
                dotenv_logger.setLevel(original_level)

            # 同步到 os.environ（只设置不存在的变量）
            for key, value in values.items():
                if value is not None and key not in os.environ:
                    os.environ[key] = value
            _ENV_CACHE = values
            logger.debug(f"已加载 .env 文件: {found_env}")
            return _ENV_CACHE
        except Exception as e:
            logger.warning(f"加载 .env 文件失败: {e}")

    _ENV_CACHE = {}
    return _ENV_CACHE


def _find_env_file(env_file: Optional[Path] = None) -> Optional[Path]:
    """
    查找 .env 配置文件（增强版）

    查找顺序（优先级从高到低）：
        1. 用户显式指定的路径
        2. 当前工作目录 (cwd) 下的 .env 及变体
        3. 用户 home 目录下的 .env
        4. 包安装目录（向后兼容）

    支持的 .env 变体：
        - .env
        - .env.local
        - .env.*（任何后缀）
        - ~/.env
        - ~/.config/dbskiter/.env

    参数:
        env_file: 用户显式指定的 .env 文件路径

    返回:
        Optional[Path]: 找到的配置文件路径，未找到返回 None
    """
    if env_file and env_file.exists():
        return env_file

    cwd = Path.cwd()
    home = Path.home()

    # 搜索路径列表（按优先级）
    search_paths = [
        # 当前工作目录
        cwd / ".env",
        cwd / ".env.local",
        # 用户 home 目录
        home / ".env",
        home / ".config" / "dbskiter" / ".env",
        # 包安装目录（向后兼容）
        Path(__file__).parent.parent.parent / ".env",
    ]

    # 同时搜索 cwd 下任何 .env.* 文件
    if cwd.exists():
        for env_variant in sorted(cwd.glob(".env.*")):
            search_paths.insert(1, env_variant)  # 插入到 .env 之后

    for path in search_paths:
        if path.exists():
            logger.debug(f"找到配置文件: {path}")
            return path

    return None


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
    source_map: Dict[str, str] = field(default_factory=dict, repr=False)  # 配置溯源：字段 -> 来源

    def __post_init__(self):
        """初始化时记录默认值来源"""
        if not self.source_map:
            for key in ("dialect", "host", "port", "username", "password", "database"):
                self.source_map[key] = "default"

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
        # 加载 .env 文件到缓存字典（避免 load_dotenv 副作用）
        env_values = _load_env_values(env_file)
        
        # 动态构建环境变量映射
        # 统一使用 _NAME 后缀，同时兼容 _SERVICE（Oracle 等特殊场景）
        database_env_var = f"{prefix}_NAME"
        if prefix != "DB" and env_values.get(database_env_var) is None:
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
        
        # 从 env_values 字典构建配置（同时兼容 os.environ 中已存在的变量）
        kwargs = {}
        extra = {}
        source_map = {}

        for key, env_var in env_mapping.items():
            # 优先从 .env 缓存读取，其次从 os.environ 读取
            value = env_values.get(env_var)
            if value is not None:
                source_map[key] = ".env"
            else:
                value = os.getenv(env_var)
                if value is not None:
                    source_map[key] = "env"
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
            service = env_values.get(f"{prefix}_SERVICE") or os.getenv(f"{prefix}_SERVICE")
            if service:
                extra["service_name"] = service
            jdbc_driver = env_values.get(f"{prefix}_JDBC_DRIVER") or os.getenv(f"{prefix}_JDBC_DRIVER")
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
                value = env_values.get(env_var)
                if value is not None:
                    source_map[key] = ".env"
                else:
                    value = os.getenv(env_var)
                    if value is not None:
                        source_map[key] = "env"
                if value is not None:
                    if key == "port":
                        try:
                            value = int(value)
                        except ValueError:
                            raise ValidationError(f"环境变量 {env_var} 必须是整数")
                    kwargs[key] = value

        # 如果仍然没有找到任何配置，抛出错误
        if not kwargs:
            raise ConfigError(
                f"未找到数据库配置（缺少 {prefix}_* 环境变量）\n"
                f"\n"
                f"您可以通过以下方式配置：\n"
                f"  1. 运行交互式向导：dbskiter init\n"
                f"  2. 查看帮助：dbskiter welcome\n"
                f"  3. 直接指定参数：dbskiter --host=xxx --user=xxx --password=xxx <命令>"
            )

        # 添加 extra 和 prefix
        kwargs["extra"] = extra
        kwargs["prefix"] = prefix
        kwargs["source_map"] = source_map

        return cls(**kwargs)
    
    @classmethod
    def _has_cli_connection(cls, args) -> bool:
        """
        检查命令行参数是否提供了足够的连接信息

        满足以下任一条件即视为"有足够连接信息"：
        1. 提供了 --host 且 --database
        2. 提供了 --dialect 且 --host 且 --database

        参数说明：
            - args: argparse 解析后的参数对象

        返回说明：
            - bool: 是否有足够的连接信息
        """
        host = getattr(args, "host", None)
        database = getattr(args, "database", None)
        dialect = getattr(args, "dialect", None)
        user = getattr(args, "user", None)

        # 有 host+database 就是足够（最简场景）
        if host and database:
            return True
        # 有 dialect+database 也算（SQLite 场景：dialect=sqlite, database=./test.db）
        if dialect and database:
            return True
        # 有 user+database 也算（本地开发场景：mysql -u root mydb）
        if user and database:
            return True
        return False

    @classmethod
    def from_args(cls, args) -> "Config":
        """
        从命令行参数加载配置（支持配置文件）

        配置优先级（从高到低）：
            1. 命令行参数：--host, --user, --password, --database, --port, --dialect
            2. 配置文件：dbskiter.yaml / dbskiter.json / dbskiter.toml（--config 指定）
            3. .env 文件（当前目录或包目录）
            4. 环境变量：DB_HOST, DB_USER, DB_PASSWORD 等
            5. 内置默认值（localhost:3306/root/test）

        关键改进：
            - 不再强依赖 .env 文件
            - CLI 参数足够时直接连接，无需任何配置文件
            - --database 参数优先匹配别名，未匹配则作为数据库名使用

        参数:
            args: argparse 解析后的参数对象

        返回:
            Config: 配置对象

        使用示例:
            # 以下用法现在全部支持（无需 .env 文件）：
            >>> Config.from_args(args)  # args 来自 --host=db.example.com --user=admin --password=xxx --database=mydb
            >>> Config.from_args(args)  # args 来自 -u root -p xxx -h localhost -d mydb
            >>> Config.from_args(args)  # args 来自 --database=jump（匹配 .env 中的 DB_JUMP_* 别名）
        """
        # ── 策略1：CLI 参数足够，直接构建（最高优先级，不依赖任何文件） ──
        if cls._has_cli_connection(args):
            config = cls._build_from_cli(args)
            # 如果同时指定了 --password-file，读取密码
            config = cls._apply_password_file(config, args)
            return config

        # ── 策略2：使用 .env / 配置文件 / 环境变量 ──
        # 2.1 从 .env 或环境变量加载基础配置
        config = cls._load_base_config()

        # 如果默认配置为空（host=localhost），且没有 --database 参数，
        # 但检测到别名配置，给出提示而不是默默 fallback 到 localhost
        if config.host == "localhost" and not getattr(args, "database", None):
            multi_config = MultiDBConfig()
            aliases = multi_config.list_aliases()
            if aliases:
                raise ConfigError(
                    f"未找到默认数据库配置（缺少 DB_HOST 等），"
                    f"但检测到以下别名: {', '.join(aliases)}\n"
                    f"请使用 --database=别名 参数，例如:\n"
                    f"  dbskiter --database={aliases[0]} monitor health"
                )

        # 2.2 从配置文件（YAML/JSON/TOML）加载
        config_path = getattr(args, "config", None)
        profile = getattr(args, "profile", None)
        config = cls._apply_config_file(config, config_path, profile, args)

        # 2.3 处理 --database 参数（优先匹配别名，未匹配则作为数据库名）
        database_arg = getattr(args, "database", None)
        config = cls._apply_database_arg(config, database_arg)

        # 2.4 用命令行参数覆盖（优先级最高）
        config = cls._apply_cli_overrides(config, args)

        # 2.5 如果指定了 --password-file，读取密码
        config = cls._apply_password_file(config, args)

        return config

    @classmethod
    def _build_from_cli(cls, args) -> "Config":
        """
        直接从命令行参数构建配置（不依赖任何文件）

        参数说明：
            - args: argparse 解析后的参数对象

        返回说明：
            - Config: 从 CLI 参数构建的配置对象
        """
        dialect = getattr(args, "dialect", None) or "mysql"
        host = getattr(args, "host", None) or "localhost"
        port = getattr(args, "port", None) or 3306
        username = getattr(args, "user", None) or "root"
        password = getattr(args, "password", None) or ""
        database = getattr(args, "database", None) or "test"

        # 端口类型转换
        if isinstance(port, str):
            try:
                port = int(port)
            except ValueError:
                pass

        config = cls(
            dialect=dialect,
            host=host,
            port=port,
            username=username,
            password=password,
            database=database,
            extra={},
            prefix="CLI",
        )
        for key in ("dialect", "host", "port", "username", "password", "database"):
            config._set_source(key, "cli")
        return config

    @classmethod
    def _load_base_config(cls) -> "Config":
        """加载环境变量基础配置（.env 或系统环境变量）"""
        try:
            return cls.from_env()
        except ConfigError:
            return cls()

    @classmethod
    def _apply_config_file(
        cls, config: "Config", config_path: Optional[str], profile: Optional[str], args
    ) -> "Config":
        """
        从配置文件加载并覆盖配置

        关键改进：
            - 检查用户是否通过命令行提供了连接参数
            - 如果用户提供了 CLI 参数且未指定 --config，跳过配置文件加载
            - 这样 CLI 参数和配置文件不会互相干扰

        参数说明：
            - config: 当前配置对象
            - config_path: 配置文件路径（可选）
            - profile: 配置文件名（可选）
            - args: argparse 解析后的参数对象（用于判断用户是否提供了 CLI 参数）

        返回说明：
            - Config: 覆盖后的配置对象
        """
        from .config_file import ConfigFileManager

        # 检查用户是否通过命令行提供了可直接建立连接的参数
        # 注意：--database 是别名引用，不在此检查范围内（它需要 .env/配置文件解析）
        has_direct_connection_params = any([
            getattr(args, "host", None),
            getattr(args, "user", None),
            getattr(args, "password", None),
            getattr(args, "dialect", None),
            getattr(args, "port", None),
        ])
        # 如果没有指定 --config 但用户提供了直接连接参数，跳过配置文件加载
        # 因为 CLI 参数优先级高于配置文件，此时加载配置文件无意义
        if not config_path and has_direct_connection_params:
            return config

        try:
            manager = ConfigFileManager(
                Path(config_path) if config_path else None
            )
            profile_config = manager.load_profile(profile)
            # 用配置文件逐项覆盖
            for field in ("dialect", "host", "port", "username", "password", "database"):
                value = getattr(profile_config, field, None)
                if value:
                    setattr(config, field, value)
                    config._set_source(field, "config_file")
        except Exception:
            pass  # 配置文件加载失败，使用当前配置
        return config

    @classmethod
    def _apply_database_arg(
        cls, config: "Config", database_arg: Optional[str]
    ) -> "Config":
        """
        处理 --database 参数（别名优先，未匹配则作为数据库名）

        别名查找顺序（按优先级从高到低）：
            1. 从 .env 文件匹配 DB_{别名}_* 配置
            2. 从 YAML 配置文件（dbskiter.yaml）匹配 databases 列表中的 name
            3. 若未找到别名配置，将 database_arg 作为数据库名使用

        参数说明：
            - config: 当前配置对象
            - database_arg: --database 参数值

        返回说明：
            - Config: 更新后的配置对象

        使用示例：
            # 别名匹配成功时：
            >>> config = Config._apply_database_arg(config, "jump")
            # 返回 DB_JUMP_* 对应的完整配置（来自 .env 或 dbskiter.yaml）

            # 无别名配置时：
            >>> config = Config._apply_database_arg(config, "mydb")
            # 仅将 config.database 设为 "mydb"，保留其他字段
        """
        if not database_arg:
            return config

        alias = database_arg.lower()

        # 策略1：尝试从 .env 匹配别名（MultiDBConfig）
        multi_config = MultiDBConfig()
        alias_config = multi_config.get_config_by_alias(alias)
        if alias_config:
            # 标记所有字段来源为 alias
            for key in ("dialect", "host", "port", "username", "password", "database"):
                if hasattr(alias_config, key):
                    alias_config._set_source(key, f"alias:{alias}")
            return alias_config

        # 策略2：尝试从 YAML 配置文件匹配别名
        try:
            from .config_file import ConfigFileManager
            manager = ConfigFileManager()
            yaml_config = manager.get_database_config(alias)
            if yaml_config:
                # 将 ProfileConfig 转换为 Config
                cfg = cls(
                    dialect=yaml_config.dialect,
                    host=yaml_config.host,
                    port=yaml_config.port,
                    username=yaml_config.username,
                    password=yaml_config.password,
                    database=yaml_config.database,
                    extra={"alias": alias},
                    prefix="YAML",
                )
                for key in ("dialect", "host", "port", "username", "password", "database"):
                    cfg._set_source(key, f"yaml_alias:{alias}")
                return cfg
        except Exception:
            pass

        # 策略3：未匹配别名，将 database_arg 作为数据库名使用
        # 仅在当前 config 没有明确 database 时设置
        if not config.database or config.database == "test":
            config.database = database_arg
            config._set_source("database", "cli(--database)")

        return config

    @classmethod
    def _apply_cli_overrides(cls, config: "Config", args) -> "Config":
        """
        用命令行参数覆盖配置

        参数说明：
            - config: 当前配置对象
            - args: argparse 解析后的参数对象

        返回说明：
            - Config: 覆盖后的配置对象
        """
        overrides = {
            "dialect": getattr(args, "dialect", None),
            "host": getattr(args, "host", None),
            "port": getattr(args, "port", None),
            "username": getattr(args, "user", None),
            "password": getattr(args, "password", None),
        }
        
        # 安全警告：如果使用了 --password 参数，提示历史记录风险
        if overrides.get("password"):
            import sys
            sys.stderr.write(
                "[SECURITY WARNING] 密码通过命令行 --password 参数传入，可能被记录到 shell 历史记录。\n"
                "                 建议使用 --password-file 或环境变量 DBSKITER_PASSWORD 来提高安全性。\n"
            )
            sys.stderr.flush()
        
        for field, value in overrides.items():
            if value:
                setattr(config, field, value)
                config._set_source(field, "cli")
        return config

    @classmethod
    def _apply_password_file(cls, config: "Config", args) -> "Config":
        """
        从 --password-file 读取密码

        如果指定了 --password-file，从文件中读取密码并覆盖 config.password。
        文件内容会被 strip() 去除首尾空白。

        安全规则：如果指定了 --password-file 但读取失败（文件不存在、权限不足、
        文件为空），程序必须**终止**并抛出错误，而不是静默忽略。
        这是为了防止用户误以为使用了密码文件，实际却用了环境变量中的旧密码。

        参数说明：
            - config: 当前配置对象
            - args: argparse 解析后的参数对象

        返回说明：
            - Config: 更新后的配置对象（仅读取成功时返回）

        使用示例：
            $ echo "my_secret_pass" > /tmp/db_pass.txt
            $ dbskiter --password-file /tmp/db_pass.txt --host=... monitor health
        """
        password_file = getattr(args, "password_file", None)
        if not password_file:
            return config

        pwd_path = Path(password_file)
        if not pwd_path.exists():
            raise ConfigError(
                f"密码文件不存在: {password_file}",
            )

        try:
            password = pwd_path.read_text(encoding="utf-8").strip()
        except PermissionError as e:
            raise ConfigError(
                f"密码文件权限不足，无法读取: {password_file}",
            ) from e
        except Exception as e:
            raise ConfigError(
                f"读取密码文件失败: {e}",
            ) from e

        if not password:
            raise ConfigError(
                f"密码文件内容为空: {password_file}",
            )

        config.password = password
        config._set_source("password", f"password_file:{password_file}")
        logger.debug(f"已从 {password_file} 读取密码")
        return config

    @staticmethod
    def _resolve_env_vars(value: str) -> str:
        """
        解析配置值中的 ${VAR} 环境变量引用

        支持语法：
            - ${VAR}         → 读取环境变量 VAR，未设置则为空字符串
            - ${VAR:-default} → 读取环境变量 VAR，未设置则使用 default

        参数说明：
            - value: 可能包含 ${VAR} 引用的原始值

        返回说明：
            - str: 解析后的值，环境变量引用被替换为实际值

        使用示例：
            >>> Config._resolve_env_vars("${DB_PASSWORD}")
            'actual_password'  # 从环境变量读取
            >>> Config._resolve_env_vars("${UNDEFINED_VAR:-default}")
            'default'
            >>> Config._resolve_env_vars("host:port=${HOST}:${PORT}")
            'host:port=localhost:3306'
        """
        if "${" not in value:
            return value

        def _replace_var(match):
            var_expr = match.group(1)
            if ":-" in var_expr:
                # ${VAR:-default} 语法
                var_name, default_val = var_expr.split(":-", 1)
                return os.environ.get(var_name.strip(), default_val)
            else:
                # ${VAR} 语法
                return os.environ.get(var_expr.strip(), "")

        return re.sub(r"\$\{([^}]+)\}", _replace_var, value)

    def _resolve_all_env_vars(self) -> None:
        """
        解析当前配置对象中所有支持 ${VAR} 语法的字段

        对以下字段进行环境变量引用解析：
            - password
            - host
            - username
            - database
        """
        for field in ("password", "host", "username", "database"):
            value = getattr(self, field, "")
            if isinstance(value, str) and "${" in value:
                resolved = self._resolve_env_vars(value)
                setattr(self, field, resolved)

    def validate(self) -> None:
        """
        验证配置有效性

        校验内容：
            - 解析所有 ${VAR} 环境变量引用
            - 验证数据库方言不能为空
            - 验证端口在 1-65535 范围内
            - 验证数据库名不能为空
            - 非 SQLite 数据库需要 host

        异常:
            ValidationError: 配置无效时抛出
        """
        # 先解析所有 ${VAR} 环境变量引用
        self._resolve_all_env_vars()

        # 验证数据库类型（支持任何 SQLAlchemy 兼容的方言）
        if not self.dialect or not self.dialect.strip():
            raise ValidationError("数据库方言不能为空")
        
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
    
    def _set_source(self, field: str, source: str) -> None:
        """
        记录配置字段的来源

        参数:
            field: 字段名
            source: 来源描述（如 'cli', 'config_file', '.env', 'env', 'default', 'alias'）
        """
        self.source_map[field] = source

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
        # 预加载 .env 文件到缓存（避免重复解析）
        _load_env_values(env_file)

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
        env_values = _load_env_values()
        aliases = []
        
        for key in env_values.keys():
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
            # 验证配置是否有效（只要有host即可，不排除localhost）
            if config.host:
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
