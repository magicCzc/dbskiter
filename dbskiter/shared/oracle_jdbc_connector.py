"""
Oracle JDBC 连接器
支持旧版本 Oracle (11g+) 通过 JayDeBeApi + JDBC 驱动连接

功能:
- 支持 Oracle 11g/12c/19c 等版本
- 兼容旧版本 Python 数据库操作
- 自动管理 JDBC 驱动

示例:
    >>> from dbskiter.shared.oracle_jdbc_connector import OracleJDBCConnector
    >>> conn = OracleJDBCConnector(
    ...     host="your_oracle_host",
    ...     port=1521,
    ...     username="your_username",
    ...     password="your_password",
    ...     service="your_service"
    ... )
    >>> result = conn.execute("SELECT * FROM dual")
    >>> print(result.rows)
"""

import os
import logging
from typing import List, Dict, Any, Optional, Tuple
from contextlib import contextmanager

logger = logging.getLogger(__name__)


class JDBCQueryResult:
    """
    JDBC 查询结果封装
    
    属性:
        rows: 查询结果行列表
        columns: 列名列表
        row_count: 行数
        execution_time_ms: 执行时间(毫秒)
    """
    
    def __init__(
        self,
        rows: List[Tuple],
        columns: List[str],
        execution_time_ms: float = 0
    ):
        self.rows = rows
        self.columns = columns
        self.row_count = len(rows)
        self.execution_time_ms = execution_time_ms
    
    def to_dict_list(self) -> List[Dict[str, Any]]:
        """转换为字典列表"""
        return [
            {col: row[i] for i, col in enumerate(self.columns)}
            for row in self.rows
        ]
    
    def __repr__(self) -> str:
        return f"[JDBCQueryResult] {self.row_count} rows, {len(self.columns)} cols"


class OracleJDBCConnector:
    """
    Oracle JDBC 连接器
    
    使用 JayDeBeApi 和 Oracle JDBC 驱动连接 Oracle 数据库
    支持 Oracle 11g 及更高版本
    
    参数:
        host: 主机地址
        port: 端口号(默认 1521)
        username: 用户名
        password: 密码
        service: 服务名/SID
        jdbc_driver_path: JDBC 驱动路径(可选)
    
    示例:
        >>> conn = OracleJDBCConnector(
        ...     host="your_oracle_host",
        ...     username="your_username",
        ...     password="your_password",
        ...     service="your_service"
        ... )
        >>> result = conn.execute("SELECT * FROM user_tables")
    """
    
    # 默认 JDBC 驱动类名
    JDBC_DRIVER_CLASS = "oracle.jdbc.driver.OracleDriver"
    
    # 默认驱动搜索路径
    DEFAULT_DRIVER_PATHS = [
        "ojdbc8.jar",
        "ojdbc11.jar",
        "ojdbc6.jar",
        "lib/ojdbc8.jar",  # 项目内 lib 目录
        "lib/ojdbc11.jar",
        "lib/ojdbc6.jar",
        r"C:\oracle\instantclient_19_x\ojdbc8.jar",
        r"C:\oracle\ojdbc8.jar",
        "/usr/lib/oracle/ojdbc8.jar",
    ]
    
    def __init__(
        self,
        host: str,
        port: int = 1521,
        username: str = "",
        password: str = "",
        service: str = "",
        jdbc_driver_path: Optional[str] = None
    ):
        """
        初始化 Oracle JDBC 连接器
        
        参数:
            host: 主机地址
            port: 端口号
            username: 用户名
            password: 密码
            service: 服务名/SID
            jdbc_driver_path: JDBC 驱动路径(可选，自动搜索)
        """
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.service = service
        
        # 查找 JDBC 驱动
        # 如果传入了路径但文件不存在，尝试自动查找
        if jdbc_driver_path and os.path.exists(jdbc_driver_path):
            self.jdbc_driver_path = os.path.abspath(jdbc_driver_path)
        else:
            # 传入的路径不存在或未传入，自动查找
            self.jdbc_driver_path = self._find_jdbc_driver()
        
        if not self.jdbc_driver_path:
            raise RuntimeError(
                "未找到 Oracle JDBC 驱动 (ojdbc*.jar)。\n"
                "请下载并放置到以下位置之一:\n"
                "  - 当前目录: ojdbc8.jar\n"
                "  - lib/ojdbc8.jar\n"
                "  - C:\\oracle\\ojdbc8.jar\n"
                "下载地址: https://www.oracle.com/database/technologies/jdbcdriver-ucp.html"
            )
        
        # 构建 JDBC URL
        self.jdbc_url = f"jdbc:oracle:thin:@{host}:{port}:{service}"
        
        # 连接对象
        self._conn = None
        
        logger.info(f"Oracle JDBC 连接器初始化: {host}:{port}/{service}")
        
        # 预建立连接（避免第一次查询时的延迟）
        try:
            self.connect()
            logger.info("Oracle JDBC 预连接成功")
        except Exception as e:
            logger.warning(f"Oracle JDBC 预连接失败: {e}")
    
    def _find_jdbc_driver(self) -> Optional[str]:
        """查找 JDBC 驱动文件"""
        for path in self.DEFAULT_DRIVER_PATHS:
            if os.path.exists(path):
                logger.info(f"找到 JDBC 驱动: {path}")
                return os.path.abspath(path)
        return None
    
    def connect(self):
        """
        建立数据库连接
        
        返回:
            jaydebeapi.Connection 对象
        """
        try:
            import jaydebeapi
            
            self._conn = jaydebeapi.connect(
                self.JDBC_DRIVER_CLASS,
                self.jdbc_url,
                [self.username, self.password],
                self.jdbc_driver_path
            )
            logger.info("Oracle JDBC 连接成功")
            return self._conn
        except Exception as e:
            logger.error(f"Oracle JDBC 连接失败: {e}")
            raise
    
    def disconnect(self):
        """断开数据库连接"""
        if self._conn:
            try:
                self._conn.close()
                logger.info("Oracle JDBC 连接已关闭")
            except Exception as e:
                logger.warning(f"关闭连接时出错: {e}")
            finally:
                self._conn = None
    
    def execute(self, sql: str, params: Optional[Tuple] = None) -> JDBCQueryResult:
        """
        执行 SQL 查询

        参数:
            sql: SQL 语句(使用 ? 作为占位符)
            params: 查询参数元组

        返回:
            JDBCQueryResult 对象

        示例:
            >>> result = conn.execute("SELECT * FROM users WHERE id > ?", (1,))
            >>> for row in result.rows:
            ...     print(row)
        """
        import time

        # 确保已连接
        if not self._conn:
            self.connect()

        start_time = time.time()
        cursor = None

        try:
            cursor = self._conn.cursor()

            # 执行查询
            if params:
                cursor.execute(sql, params)
            else:
                cursor.execute(sql)
            
            # 获取列名
            columns = [desc[0] for desc in cursor.description] if cursor.description else []
            
            # 获取结果
            rows = cursor.fetchall()
            
            execution_time = (time.time() - start_time) * 1000
            
            return JDBCQueryResult(
                rows=rows,
                columns=columns,
                execution_time_ms=execution_time
            )

        except Exception as e:
            error_msg = str(e)
            # 连接断开时自动重连一次
            if any(kw in error_msg.upper() for kw in
                   ['CONNECTION', 'CLOSED', 'BROKEN', 'RESET', 'TIMEOUT',
                    'NETWORK', 'COMMUNICATION', 'SESSION', 'ORA-03113',
                    'ORA-03114', 'ORA-03135', 'ORA-12571']):
                logger.warning(f"检测到连接异常，尝试重连: {e}")
                try:
                    self._conn = None
                    self.connect()
                    # 重连后重试查询
                    cursor = self._conn.cursor()
                    if params:
                        cursor.execute(sql, params)
                    else:
                        cursor.execute(sql)
                    columns = [desc[0] for desc in cursor.description] if cursor.description else []
                    rows = cursor.fetchall()
                    execution_time = (time.time() - start_time) * 1000
                    if cursor:
                        cursor.close()
                    logger.info("重连后查询成功")
                    return JDBCQueryResult(
                        rows=rows,
                        columns=columns,
                        execution_time_ms=execution_time
                    )
                except Exception as retry_err:
                    logger.error(f"重连后查询仍然失败: {retry_err}")
                    raise

            logger.error(f"SQL 执行失败: {e}")
            raise
        finally:
            if cursor:
                cursor.close()
    
    def execute_update(self, sql: str, params: Optional[Tuple] = None) -> int:
        """
        执行更新语句(INSERT/UPDATE/DELETE)
        
        参数:
            sql: SQL 语句
            params: 参数元组
            
        返回:
            影响的行数
        """
        if not self._conn:
            self.connect()
        
        cursor = None
        try:
            cursor = self._conn.cursor()
            
            if params:
                cursor.execute(sql, params)
            else:
                cursor.execute(sql)
            
            self._conn.commit()
            return cursor.rowcount
            
        except Exception as e:
            logger.error(f"更新执行失败: {e}")
            self._conn.rollback()
            raise
        finally:
            if cursor:
                cursor.close()
    
    @contextmanager
    def transaction(self):
        """
        事务上下文管理器
        
        示例:
            >>> with conn.transaction():
            ...     conn.execute_update("INSERT INTO users VALUES (?)", (1,))
            ...     conn.execute_update("INSERT INTO logs VALUES (?)", (2,))
        """
        if not self._conn:
            self.connect()
        
        try:
            yield self
            self._conn.commit()
        except Exception as e:
            self._conn.rollback()
            raise
    
    def __enter__(self):
        """上下文管理器入口"""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        self.disconnect()
    
    @classmethod
    def from_env(cls, prefix: str = "ORACLE") -> "OracleJDBCConnector":
        """
        从环境变量创建连接器
        
        参数:
            prefix: 环境变量前缀(默认 ORACLE)
            
        支持的环境变量:
            - {prefix}_HOST: 主机地址
            - {prefix}_PORT: 端口号
            - {prefix}_USER: 用户名
            - {prefix}_PASSWORD: 密码
            - {prefix}_SERVICE: 服务名
            - {prefix}_JDBC_DRIVER: JDBC 驱动路径(可选)
        """
        host = os.getenv(f"{prefix}_HOST", "localhost")
        port = int(os.getenv(f"{prefix}_PORT", "1521"))
        username = os.getenv(f"{prefix}_USER", "")
        password = os.getenv(f"{prefix}_PASSWORD", "")
        service = os.getenv(f"{prefix}_SERVICE", "")
        driver_path = os.getenv(f"{prefix}_JDBC_DRIVER")
        
        return cls(
            host=host,
            port=port,
            username=username,
            password=password,
            service=service,
            jdbc_driver_path=driver_path
        )
