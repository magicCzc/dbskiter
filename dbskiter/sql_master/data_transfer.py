"""
sql_master/data_transfer.py

文件功能：数据导入导出模块，支持CSV、JSON、SQL等格式的数据导入导出
主要类：
    - DataExporter: 数据导出器
    - DataImporter: 数据导入器
    - DataFormat: 数据格式枚举

使用示例:
    >>> from sql_master.data_transfer import DataExporter, DataImporter
    >>> exporter = DataExporter(connector)
    >>> exporter.export_table("users", "users.csv", format="csv")
    >>> 
    >>> importer = DataImporter(connector)
    >>> importer.import_csv("users.csv", "users")

版本: 1.0.0
作者: AI Assistant
创建时间: 2026-04-24
最后修改: 2026-04-24
"""

import csv
import json
import logging
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from dbskiter.shared.unified_connector import UnifiedConnector

logger = logging.getLogger(__name__)


class DataFormat(Enum):
    """数据格式枚举"""
    CSV = "csv"
    JSON = "json"
    SQL = "sql"
    EXCEL = "excel"


class DataExporter:
    """
    数据导出器
    
    支持将数据库表或查询结果导出为各种格式
    """
    
    def __init__(self, connector: UnifiedConnector):
        """
        初始化数据导出器
        
        参数:
            connector: 数据库连接器
        """
        self.connector = connector
        
    def _validate_identifier(self, identifier: str) -> bool:
        """
        验证标识符是否安全（防止SQL注入）
        
        参数:
            identifier: 表名或列名
            
        返回:
            bool: 是否安全
        """
        import re
        # 只允许字母、数字、下划线，且不能以数字开头
        pattern = r'^[a-zA-Z_][a-zA-Z0-9_]*$'
        return bool(re.match(pattern, identifier))
    
    def _validate_where_clause(self, where: str) -> bool:
        """
        验证WHERE子句是否安全（防止SQL注入）
        
        参数:
            where: WHERE条件
            
        返回:
            bool: 是否安全
            
        说明:
            只允许简单的条件表达式，禁止危险操作
        """
        import re
        
        # 转换为小写进行检查
        where_lower = where.lower()
        
        # 禁止的关键字和模式
        dangerous_patterns = [
            r';',  # 分号（多语句）
            r'--',  # 注释
            r'/\*',  # 块注释开始
            r'\*/',  # 块注释结束
            r'union\s+select',  # UNION注入
            r'insert\s+into',  # INSERT注入
            r'update\s+\w+\s+set',  # UPDATE注入
            r'delete\s+from',  # DELETE注入
            r'drop\s+table',  # DROP注入
            r'exec\s*\(',  # 执行存储过程
            r'xp_',  # SQL Server扩展存储过程
            r'sp_',  # SQL Server存储过程
            r'@@',  # SQL Server全局变量
        ]
        
        for pattern in dangerous_patterns:
            if re.search(pattern, where_lower):
                logger.warning(f"WHERE子句包含危险模式: {pattern}")
                return False
        
        # 只允许安全的字符
        # 允许：字母、数字、空格、比较运算符、括号、引号、下划线、点号、冒号（时间）、加减号
        safe_pattern = r'^[\w\s=<>!&|()\'"%_.,:\+\-]+$'
        if not re.match(safe_pattern, where):
            logger.warning("WHERE子句包含非法字符")
            return False
        
        return True
    
    def export_table(
        self,
        table_name: str,
        output_path: str,
        format: str = "csv",
        where: Optional[str] = None,
        limit: Optional[int] = None,
        columns: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        导出表数据
        
        参数:
            table_name: 表名
            output_path: 输出文件路径
            format: 导出格式 (csv, json, sql)
            where: WHERE条件（仅支持简单条件，如：status='active' AND age>18）
            limit: 限制行数
            columns: 指定列，None表示所有列
            
        返回:
            Dict: 导出结果
            
        使用示例:
            >>> exporter.export_table("users", "users.csv", format="csv")
            >>> exporter.export_table("users", "users.json", format="json", limit=1000)
            >>> exporter.export_table("users", "users.csv", where="status='active'")
        """
        try:
            # 验证表名安全
            if not self._validate_identifier(table_name):
                return {
                    "success": False,
                    "message": f"表名包含非法字符: {table_name}",
                    "exported_rows": 0
                }
            
            # 构建查询
            if columns:
                # 验证所有列名安全
                for col in columns:
                    if not self._validate_identifier(col):
                        return {
                            "success": False,
                            "message": f"列名包含非法字符: {col}",
                            "exported_rows": 0
                        }
                cols_str = ", ".join(columns)
            else:
                cols_str = "*"
                
            sql = f"SELECT {cols_str} FROM {table_name}"
            
            # 验证WHERE子句安全
            if where:
                if not self._validate_where_clause(where):
                    return {
                        "success": False,
                        "message": "WHERE子句包含危险内容，已拒绝执行",
                        "exported_rows": 0
                    }
                sql += f" WHERE {where}"
                
            if limit:
                sql += f" LIMIT {limit}"
            
            # 执行查询
            result = self.connector.execute(sql)
            rows = result.rows if hasattr(result, 'rows') else []
            columns = result.columns if hasattr(result, 'columns') else []
            
            # 根据格式导出
            format_enum = DataFormat(format.lower())
            
            if format_enum == DataFormat.CSV:
                self._export_to_csv(rows, columns, output_path)
            elif format_enum == DataFormat.JSON:
                self._export_to_json(rows, columns, output_path)
            elif format_enum == DataFormat.SQL:
                self._export_to_sql(rows, columns, table_name, output_path)
            elif format_enum == DataFormat.EXCEL:
                self._export_to_excel(rows, columns, output_path)
                # 更新输出路径（可能添加了.xlsx扩展名）
                if not output_path.endswith('.xlsx'):
                    output_path += '.xlsx'
            else:
                return {
                    "success": False,
                    "message": f"不支持的导出格式: {format}",
                    "exported_rows": 0
                }
            
            return {
                "success": True,
                "message": f"成功导出 {len(rows)} 行数据到 {output_path}",
                "exported_rows": len(rows),
                "output_path": output_path,
                "format": format
            }
            
        except Exception as e:
            logger.error(f"导出数据失败: {e}")
            return {
                "success": False,
                "message": f"导出失败: {str(e)}",
                "exported_rows": 0
            }
    
    def export_query(
        self,
        sql: str,
        output_path: str,
        format: str = "csv"
    ) -> Dict[str, Any]:
        """
        导出查询结果
        
        参数:
            sql: SQL查询语句
            output_path: 输出文件路径
            format: 导出格式
            
        返回:
            Dict: 导出结果
        """
        try:
            result = self.connector.execute(sql)
            rows = result.rows if hasattr(result, 'rows') else []
            columns = result.columns if hasattr(result, 'columns') else []
            
            format_enum = DataFormat(format.lower())
            
            if format_enum == DataFormat.CSV:
                self._export_to_csv(rows, columns, output_path)
            elif format_enum == DataFormat.JSON:
                self._export_to_json(rows, columns, output_path)
            elif format_enum == DataFormat.EXCEL:
                self._export_to_excel(rows, columns, output_path)
                # 更新输出路径（可能添加了.xlsx扩展名）
                if not output_path.endswith('.xlsx'):
                    output_path += '.xlsx'
            else:
                return {
                    "success": False,
                    "message": f"不支持的导出格式: {format}",
                    "exported_rows": 0
                }
            
            return {
                "success": True,
                "message": f"成功导出 {len(rows)} 行数据",
                "exported_rows": len(rows),
                "output_path": output_path,
                "format": format
            }
            
        except Exception as e:
            logger.error(f"导出查询结果失败: {e}")
            return {
                "success": False,
                "message": f"导出失败: {str(e)}",
                "exported_rows": 0
            }
    
    def _export_to_csv(
        self,
        rows: List[tuple],
        columns: List[str],
        output_path: str
    ) -> None:
        """导出为CSV格式"""
        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(columns)
            writer.writerows(rows)
    
    def _export_to_json(
        self,
        rows: List[tuple],
        columns: List[str],
        output_path: str
    ) -> None:
        """导出为JSON格式"""
        data = []
        for row in rows:
            row_dict = {}
            for i, col in enumerate(columns):
                value = row[i]
                # 处理datetime类型
                if isinstance(value, datetime):
                    value = value.isoformat()
                row_dict[col] = value
            data.append(row_dict)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def _export_to_sql(
        self,
        rows: List[tuple],
        columns: List[str],
        table_name: str,
        output_path: str
    ) -> None:
        """导出为SQL INSERT语句"""
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(f"-- Export table: {table_name}\n")
            f.write(f"-- Generated at: {datetime.now().isoformat()}\n\n")
            
            cols_str = ", ".join(columns)
            
            for row in rows:
                values = []
                for value in row:
                    if value is None:
                        values.append("NULL")
                    elif isinstance(value, (int, float)):
                        values.append(str(value))
                    elif isinstance(value, datetime):
                        values.append(f"'{value.strftime('%Y-%m-%d %H:%M:%S')}'")
                    else:
                        # 转义单引号和反斜杠
                        escaped = str(value).replace("\\", "\\\\").replace("'", "''")
                        values.append(f"'{escaped}'")
                
                values_str = ", ".join(values)
                sql = f"INSERT INTO {table_name} ({cols_str}) VALUES ({values_str});\n"
                f.write(sql)
    
    def _export_to_excel(
        self,
        rows: List[tuple],
        columns: List[str],
        output_path: str
    ) -> None:
        """导出为Excel格式"""
        try:
            import pandas as pd
        except ImportError:
            raise ImportError("导出Excel需要pandas和openpyxl，请安装: pip install pandas openpyxl")
        
        # 转换数据为DataFrame
        data = []
        for row in rows:
            row_dict = {}
            for i, col in enumerate(columns):
                value = row[i]
                # 处理datetime类型
                if isinstance(value, datetime):
                    value = value.strftime('%Y-%m-%d %H:%M:%S')
                row_dict[col] = value
            data.append(row_dict)
        
        df = pd.DataFrame(data)
        
        # 确保文件扩展名为.xlsx
        if not output_path.endswith('.xlsx'):
            output_path += '.xlsx'
        
        # 导出到Excel
        df.to_excel(output_path, index=False, engine='openpyxl')
    
    def export_table_streaming(
        self,
        table_name: str,
        output_path: str,
        format: str = "csv",
        where: Optional[str] = None,
        batch_size: int = 10000,
        columns: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        流式导出大表数据（分批导出，避免内存溢出）
        
        参数:
            table_name: 表名
            output_path: 输出文件路径
            format: 导出格式 (csv, sql)
            where: WHERE条件
            batch_size: 每批导出的行数
            columns: 指定列
            
        返回:
            Dict: 导出结果
            
        使用示例:
            >>> exporter.export_table_streaming("large_table", "output.csv", batch_size=5000)
        """
        try:
            # 验证表名安全
            if not self._validate_identifier(table_name):
                return {
                    "success": False,
                    "message": f"表名包含非法字符: {table_name}",
                    "exported_rows": 0
                }
            
            # 验证列名安全
            if columns:
                for col in columns:
                    if not self._validate_identifier(col):
                        return {
                            "success": False,
                            "message": f"列名包含非法字符: {col}",
                            "exported_rows": 0
                        }
                cols_str = ", ".join(columns)
            else:
                cols_str = "*"
            
            # 验证WHERE子句
            if where and not self._validate_where_clause(where):
                return {
                    "success": False,
                    "message": "WHERE子句包含危险内容，已拒绝执行",
                    "exported_rows": 0
                }
            
            format_enum = DataFormat(format.lower())
            if format_enum not in [DataFormat.CSV, DataFormat.SQL]:
                return {
                    "success": False,
                    "message": f"流式导出不支持格式: {format}（仅支持csv/sql）",
                    "exported_rows": 0
                }
            
            # 获取总记录数
            count_sql = f"SELECT COUNT(*) FROM {table_name}"
            if where:
                count_sql += f" WHERE {where}"
            
            result = self.connector.execute(count_sql)
            total_rows = result.rows[0][0] if result.rows else 0
            
            # 流式导出
            exported_count = 0
            offset = 0
            
            with open(output_path, 'w', encoding='utf-8', newline='') as f:
                # 写入文件头
                if format_enum == DataFormat.SQL:
                    f.write(f"-- Export table: {table_name}\n")
                    f.write(f"-- Generated at: {datetime.now().isoformat()}\n\n")
                elif format_enum == DataFormat.CSV:
                    import csv
                    writer = csv.writer(f)
                    # 先获取列名
                    sample_sql = f"SELECT {cols_str} FROM {table_name} LIMIT 1"
                    sample_result = self.connector.execute(sample_sql)
                    if hasattr(sample_result, 'columns'):
                        writer.writerow(sample_result.columns)
                
                # 分批导出
                while offset < total_rows:
                    batch_sql = f"SELECT {cols_str} FROM {table_name}"
                    if where:
                        batch_sql += f" WHERE {where}"
                    batch_sql += f" LIMIT {batch_size} OFFSET {offset}"
                    
                    result = self.connector.execute(batch_sql)
                    rows = result.rows if hasattr(result, 'rows') else []
                    
                    if not rows:
                        break
                    
                    # 写入数据
                    if format_enum == DataFormat.CSV:
                        writer.writerows(rows)
                    elif format_enum == DataFormat.SQL:
                        if columns:
                            cols_list = columns
                        else:
                            cols_list = result.columns if hasattr(result, 'columns') else []
                        
                        cols_str_sql = ", ".join(cols_list)
                        for row in rows:
                            values = []
                            for value in row:
                                if value is None:
                                    values.append("NULL")
                                elif isinstance(value, (int, float)):
                                    values.append(str(value))
                                elif isinstance(value, datetime):
                                    values.append(f"'{value.strftime('%Y-%m-%d %H:%M:%S')}'")
                                else:
                                    escaped = str(value).replace("\\", "\\\\").replace("'", "''")
                                    values.append(f"'{escaped}'")
                            
                            values_str = ", ".join(values)
                            sql = f"INSERT INTO {table_name} ({cols_str_sql}) VALUES ({values_str});\n"
                            f.write(sql)
                    
                    exported_count += len(rows)
                    offset += batch_size
                    
                    # 记录进度
                    if offset % 100000 == 0:
                        logger.info(f"已导出 {exported_count}/{total_rows} 行")
            
            return {
                "success": True,
                "message": f"成功导出 {exported_count} 行数据到 {output_path}",
                "exported_rows": exported_count,
                "output_path": output_path,
                "format": format
            }
            
        except Exception as e:
            logger.error(f"流式导出失败: {e}")
            return {
                "success": False,
                "message": f"导出失败: {str(e)}",
                "exported_rows": 0
            }


class DataImporter:
    """
    数据导入器
    
    支持从各种格式文件导入数据到数据库
    """
    
    def __init__(self, connector: UnifiedConnector):
        """
        初始化数据导入器
        
        参数:
            connector: 数据库连接器
        """
        self.connector = connector
    
    def _detect_encoding(self, file_path: str) -> str:
        """
        自动检测文件编码
        
        参数:
            file_path: 文件路径
            
        返回:
            str: 检测到的编码格式
            
        说明:
            尝试多种编码，返回第一个成功的编码
        """
        encodings = ['utf-8', 'gbk', 'gb2312', 'gb18030', 'latin-1', 'cp1252']
        
        for encoding in encodings:
            try:
                with open(file_path, 'r', encoding=encoding) as f:
                    f.read(1024)  # 只读取前1KB进行检测
                    logger.debug(f"检测到文件编码: {encoding}")
                    return encoding
            except UnicodeDecodeError:
                continue
            except Exception as e:
                logger.warning(f"检测编码 {encoding} 失败: {e}")
                continue
        
        # 如果都失败了，返回utf-8并忽略错误
        logger.warning("无法自动检测编码，使用utf-8")
        return 'utf-8'
    
    def import_csv(
        self,
        input_path: str,
        table_name: str,
        columns: Optional[List[str]] = None,
        batch_size: int = 1000,
        skip_header: bool = True
    ) -> Dict[str, Any]:
        """
        从CSV文件导入数据
        
        参数:
            input_path: CSV文件路径
            table_name: 目标表名
            columns: 指定列名，None表示使用CSV第一行
            batch_size: 批量插入大小
            skip_header: 是否跳过CSV第一行（表头）
            
        返回:
            Dict: 导入结果
            
        使用示例:
            >>> importer.import_csv("users.csv", "users")
            >>> importer.import_csv("data.csv", "orders", columns=["id", "name"])
        """
        try:
            imported_count = 0
            batch = []
            
            # 自动检测文件编码
            encoding = self._detect_encoding(input_path)
            
            with open(input_path, 'r', encoding=encoding) as f:
                reader = csv.reader(f)
                
                # 读取表头
                if skip_header:
                    header = next(reader)
                    if not columns:
                        columns = header
                
                if not columns:
                    return {
                        "success": False,
                        "message": "未指定列名且CSV没有表头",
                        "imported_rows": 0
                    }
                
                cols_str = ", ".join(columns)
                placeholders = ", ".join(["%s"] * len(columns))
                sql = f"INSERT INTO {table_name} ({cols_str}) VALUES ({placeholders})"
                
                for row in reader:
                    batch.append(row)
                    
                    if len(batch) >= batch_size:
                        self._execute_batch(sql, batch)
                        imported_count += len(batch)
                        batch = []
                
                # 处理剩余数据
                if batch:
                    self._execute_batch(sql, batch)
                    imported_count += len(batch)
            
            return {
                "success": True,
                "message": f"成功导入 {imported_count} 行数据",
                "imported_rows": imported_count,
                "table": table_name
            }
            
        except Exception as e:
            logger.error(f"导入CSV失败: {e}")
            return {
                "success": False,
                "message": f"导入失败: {str(e)}",
                "imported_rows": 0
            }
    
    def import_json(
        self,
        input_path: str,
        table_name: str,
        batch_size: int = 1000
    ) -> Dict[str, Any]:
        """
        从JSON文件导入数据
        
        参数:
            input_path: JSON文件路径
            table_name: 目标表名
            batch_size: 批量插入大小
            
        返回:
            Dict: 导入结果
        """
        try:
            with open(input_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            if not data or not isinstance(data, list):
                return {
                    "success": False,
                    "message": "JSON文件格式错误，应为对象数组",
                    "imported_rows": 0
                }
            
            # 获取列名
            columns = list(data[0].keys())
            cols_str = ", ".join(columns)
            placeholders = ", ".join(["%s"] * len(columns))
            sql = f"INSERT INTO {table_name} ({cols_str}) VALUES ({placeholders})"
            
            imported_count = 0
            batch = []
            
            for item in data:
                row = [item.get(col) for col in columns]
                batch.append(row)
                
                if len(batch) >= batch_size:
                    self._execute_batch(sql, batch)
                    imported_count += len(batch)
                    batch = []
            
            if batch:
                self._execute_batch(sql, batch)
                imported_count += len(batch)
            
            return {
                "success": True,
                "message": f"成功导入 {imported_count} 行数据",
                "imported_rows": imported_count,
                "table": table_name
            }
            
        except Exception as e:
            logger.error(f"导入JSON失败: {e}")
            return {
                "success": False,
                "message": f"导入失败: {str(e)}",
                "imported_rows": 0
            }
    
    def import_sql(self, input_path: str) -> Dict[str, Any]:
        """
        从SQL文件导入数据
        
        参数:
            input_path: SQL文件路径
            
        返回:
            Dict: 导入结果
        """
        try:
            with open(input_path, 'r', encoding='utf-8') as f:
                sql_content = f.read()
            
            # 分割SQL语句
            statements = [s.strip() for s in sql_content.split(';') if s.strip()]
            
            executed_count = 0
            for statement in statements:
                if statement.upper().startswith('INSERT'):
                    self.connector.execute(statement)
                    executed_count += 1
            
            return {
                "success": True,
                "message": f"成功执行 {executed_count} 条INSERT语句",
                "imported_rows": executed_count
            }
            
        except Exception as e:
            logger.error(f"导入SQL失败: {e}")
            return {
                "success": False,
                "message": f"导入失败: {str(e)}",
                "imported_rows": 0
            }
    
    def _execute_batch(self, sql: str, batch: List[List[Any]]) -> None:
        """批量执行SQL"""
        for row in batch:
            self.connector.execute(sql, row)
