"""
sql_master/test_data_transfer.py
数据导入导出单元测试

测试范围:
    - DataExporter 数据导出器
    - DataImporter 数据导入器
    - SQL注入防护
    - 编码检测
    - 流式导出

版本: 1.0.0
作者: AI Assistant
创建时间: 2026-04-24
"""

import os
import json
import csv
import tempfile
import unittest
from datetime import datetime
from unittest.mock import Mock, MagicMock, patch

from dbskiter.sql_master.data_transfer import DataExporter, DataImporter, DataFormat


class TestDataExporter(unittest.TestCase):
    """测试数据导出器"""

    def setUp(self):
        """测试前准备"""
        self.connector = Mock()
        self.exporter = DataExporter(self.connector)
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        """测试后清理"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _create_mock_result(self, columns, rows):
        """创建模拟查询结果"""
        result = Mock()
        result.columns = columns
        result.rows = rows
        return result

    def test_validate_identifier_safe(self):
        """测试验证安全的标识符"""
        safe_identifiers = [
            "users",
            "user_name",
            "_temp",
            "table123",
            "UserProfile",
        ]
        for identifier in safe_identifiers:
            with self.subTest(identifier=identifier):
                self.assertTrue(
                    self.exporter._validate_identifier(identifier),
                    f"{identifier} 应该被识别为安全"
                )

    def test_validate_identifier_unsafe(self):
        """测试验证不安全的标识符"""
        unsafe_identifiers = [
            "users; DROP TABLE users; --",
            "user'name",
            "table name",
            "123table",
            "user--name",
            "user/*name",
        ]
        for identifier in unsafe_identifiers:
            with self.subTest(identifier=identifier):
                self.assertFalse(
                    self.exporter._validate_identifier(identifier),
                    f"{identifier} 应该被识别为不安全"
                )

    def test_validate_where_clause_safe(self):
        """测试验证安全的WHERE子句"""
        safe_clauses = [
            "status='active'",
            "age > 18",
            "name LIKE '%test%'",
            "created_at >= '2024-01-01' AND status = 1",
            "id IN (1, 2, 3)",
        ]
        for clause in safe_clauses:
            with self.subTest(clause=clause):
                self.assertTrue(
                    self.exporter._validate_where_clause(clause),
                    f"{clause} 应该被识别为安全"
                )

    def test_validate_where_clause_unsafe(self):
        """测试验证不安全的WHERE子句"""
        unsafe_clauses = [
            "1=1; DROP TABLE users; --",
            "1=1 UNION SELECT * FROM admin",
            "1=1; INSERT INTO users VALUES (1)",
            "1=1; UPDATE users SET admin=1",
            "1=1; DELETE FROM users",
            "1=1; DROP TABLE users",
        ]
        for clause in unsafe_clauses:
            with self.subTest(clause=clause):
                self.assertFalse(
                    self.exporter._validate_where_clause(clause),
                    f"{clause} 应该被识别为不安全"
                )

    def test_export_table_sql_injection_blocked(self):
        """测试导出时阻止SQL注入"""
        result = self.exporter.export_table(
            table_name="users; DROP TABLE users; --",
            output_path=os.path.join(self.temp_dir, "test.csv")
        )
        self.assertFalse(result["success"])
        self.assertIn("非法字符", result["message"])

    def test_export_table_where_injection_blocked(self):
        """测试WHERE条件注入被阻止"""
        self.connector.execute.return_value = self._create_mock_result(
            ["id", "name"],
            []
        )

        result = self.exporter.export_table(
            table_name="users",
            output_path=os.path.join(self.temp_dir, "test.csv"),
            where="1=1; DROP TABLE users; --"
        )
        self.assertFalse(result["success"])
        self.assertIn("危险内容", result["message"])

    def test_export_table_csv_success(self):
        """测试成功导出CSV"""
        self.connector.execute.return_value = self._create_mock_result(
            ["id", "name", "email"],
            [
                (1, "张三", "zhangsan@test.com"),
                (2, "李四", "lisi@test.com"),
            ]
        )

        output_path = os.path.join(self.temp_dir, "users.csv")
        result = self.exporter.export_table(
            table_name="users",
            output_path=output_path,
            format="csv"
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["exported_rows"], 2)
        self.assertTrue(os.path.exists(output_path))

        # 验证CSV内容
        with open(output_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            rows = list(reader)
            self.assertEqual(rows[0], ["id", "name", "email"])
            self.assertEqual(rows[1], ["1", "张三", "zhangsan@test.com"])

    def test_export_table_json_success(self):
        """测试成功导出JSON"""
        self.connector.execute.return_value = self._create_mock_result(
            ["id", "name"],
            [(1, "张三"), (2, "李四")]
        )

        output_path = os.path.join(self.temp_dir, "users.json")
        result = self.exporter.export_table(
            table_name="users",
            output_path=output_path,
            format="json"
        )

        self.assertTrue(result["success"])
        self.assertTrue(os.path.exists(output_path))

        # 验证JSON内容
        with open(output_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            self.assertEqual(len(data), 2)
            self.assertEqual(data[0]["id"], 1)
            self.assertEqual(data[0]["name"], "张三")

    def test_export_table_sql_success(self):
        """测试成功导出SQL"""
        self.connector.execute.return_value = self._create_mock_result(
            ["id", "name"],
            [(1, "张三"), (2, "李四")]
        )

        output_path = os.path.join(self.temp_dir, "users.sql")
        result = self.exporter.export_table(
            table_name="users",
            output_path=output_path,
            format="sql"
        )

        self.assertTrue(result["success"])
        self.assertTrue(os.path.exists(output_path))

        # 验证SQL内容
        with open(output_path, 'r', encoding='utf-8') as f:
            content = f.read()
            self.assertIn("INSERT INTO users", content)
            self.assertIn("'张三'", content)
            self.assertIn("'李四'", content)

    def test_export_table_with_special_chars(self):
        """测试导出包含特殊字符的数据"""
        self.connector.execute.return_value = self._create_mock_result(
            ["id", "content"],
            [
                (1, "包含'单引号'的内容"),
                (2, '包含"双引号"的内容'),
                (3, "包含\\反斜杠的内容"),
                (4, "包含\n换行的内容"),
            ]
        )

        output_path = os.path.join(self.temp_dir, "special.sql")
        result = self.exporter.export_table(
            table_name="users",
            output_path=output_path,
            format="sql"
        )

        self.assertTrue(result["success"])

        # 验证SQL转义正确
        with open(output_path, 'r', encoding='utf-8') as f:
            content = f.read()
            # 单引号应该被转义
            self.assertIn("''单引号''", content)
            # 反斜杠应该被转义
            self.assertIn("\\\\反斜杠", content)

    def test_export_table_with_limit(self):
        """测试带LIMIT的导出"""
        self.connector.execute.return_value = self._create_mock_result(
            ["id"],
            [(1,), (2,), (3,)]
        )

        output_path = os.path.join(self.temp_dir, "limited.csv")
        result = self.exporter.export_table(
            table_name="users",
            output_path=output_path,
            format="csv",
            limit=3
        )

        self.assertTrue(result["success"])
        # 验证SQL包含LIMIT
        call_args = self.connector.execute.call_args[0][0]
        self.assertIn("LIMIT 3", call_args)

    def test_export_table_streaming_success(self):
        """测试流式导出成功"""
        # 模拟COUNT查询 - 只有20行
        count_result = Mock()
        count_result.rows = [(20,)]
        
        # 模拟获取列名查询
        sample_result = Mock()
        sample_result.columns = ["id", "name"]
        sample_result.rows = [(1, "user1")]

        # 模拟分批查询 - 第一批10行，第二批10行，第三批空
        batch_result_1 = Mock()
        batch_result_1.columns = ["id", "name"]
        batch_result_1.rows = [(i, f"user{i}") for i in range(1, 11)]
        
        batch_result_2 = Mock()
        batch_result_2.columns = ["id", "name"]
        batch_result_2.rows = [(i, f"user{i}") for i in range(11, 21)]
        
        batch_result_3 = Mock()
        batch_result_3.columns = ["id", "name"]
        batch_result_3.rows = []

        self.connector.execute.side_effect = [
            count_result,    # COUNT
            sample_result,   # 获取列名
            batch_result_1,  # 第一批
            batch_result_2,  # 第二批
            batch_result_3,  # 第三批（空）
        ]

        output_path = os.path.join(self.temp_dir, "streaming.csv")
        result = self.exporter.export_table_streaming(
            table_name="users",
            output_path=output_path,
            format="csv",
            batch_size=10
        )

        self.assertTrue(result["success"])
        self.assertTrue(os.path.exists(output_path))
        self.assertEqual(result["exported_rows"], 20)


class TestDataImporter(unittest.TestCase):
    """测试数据导入器"""

    def setUp(self):
        """测试前准备"""
        self.connector = Mock()
        self.importer = DataImporter(self.connector)
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        """测试后清理"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_detect_encoding_utf8(self):
        """测试检测UTF-8编码"""
        file_path = os.path.join(self.temp_dir, "utf8.csv")
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write("id,name\n1,张三\n")

        encoding = self.importer._detect_encoding(file_path)
        self.assertEqual(encoding, 'utf-8')

    def test_detect_encoding_gbk(self):
        """测试检测GBK编码"""
        file_path = os.path.join(self.temp_dir, "gbk.csv")
        with open(file_path, 'w', encoding='gbk') as f:
            f.write("id,name\n1,张三\n")

        encoding = self.importer._detect_encoding(file_path)
        self.assertEqual(encoding, 'gbk')

    def test_import_csv_success(self):
        """测试成功导入CSV"""
        file_path = os.path.join(self.temp_dir, "users.csv")
        with open(file_path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(["id", "name", "email"])
            writer.writerow(["1", "张三", "zhangsan@test.com"])
            writer.writerow(["2", "李四", "lisi@test.com"])

        self.connector.execute.return_value = Mock()

        result = self.importer.import_csv(
            input_path=file_path,
            table_name="users"
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["imported_rows"], 2)

        # 验证执行了INSERT
        self.assertTrue(self.connector.execute.called)
        call_args = self.connector.execute.call_args[0][0]
        self.assertIn("INSERT INTO users", call_args)

    def test_import_csv_with_columns(self):
        """测试指定列名导入CSV"""
        file_path = os.path.join(self.temp_dir, "data.csv")
        with open(file_path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(["1", "张三"])
            writer.writerow(["2", "李四"])

        self.connector.execute.return_value = Mock()

        result = self.importer.import_csv(
            input_path=file_path,
            table_name="users",
            columns=["id", "name"],
            skip_header=False
        )

        self.assertTrue(result["success"])
        # 验证使用了指定的列名
        call_args = self.connector.execute.call_args[0][0]
        self.assertIn("(id, name)", call_args)

    def test_import_json_success(self):
        """测试成功导入JSON"""
        file_path = os.path.join(self.temp_dir, "users.json")
        data = [
            {"id": 1, "name": "张三", "email": "zhangsan@test.com"},
            {"id": 2, "name": "李四", "email": "lisi@test.com"},
        ]
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f)

        self.connector.execute.return_value = Mock()

        result = self.importer.import_json(
            input_path=file_path,
            table_name="users"
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["imported_rows"], 2)

    def test_import_sql_success(self):
        """测试成功导入SQL文件"""
        file_path = os.path.join(self.temp_dir, "users.sql")
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write("INSERT INTO users (id, name) VALUES (1, '张三');\n")
            f.write("INSERT INTO users (id, name) VALUES (2, '李四');\n")
            f.write("-- 这是注释\n")
            f.write("\n")

        self.connector.execute.return_value = Mock()

        result = self.importer.import_sql(file_path)

        self.assertTrue(result["success"])
        self.assertEqual(result["imported_rows"], 2)
        self.assertEqual(self.connector.execute.call_count, 2)

    def test_import_file_not_found(self):
        """测试导入不存在的文件"""
        result = self.importer.import_csv(
            input_path="/not/exist/file.csv",
            table_name="users"
        )

        self.assertFalse(result["success"])
        self.assertEqual(result["imported_rows"], 0)

    def test_import_batch_processing(self):
        """测试批量导入处理"""
        file_path = os.path.join(self.temp_dir, "large.csv")
        with open(file_path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(["id"])
            for i in range(1, 26):  # 25行数据
                writer.writerow([str(i)])

        self.connector.execute.return_value = Mock()

        result = self.importer.import_csv(
            input_path=file_path,
            table_name="users",
            batch_size=10  # 每批10行
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["imported_rows"], 25)
        # 应该执行25次（每行一次，因为_execute_batch逐行执行）
        self.assertEqual(self.connector.execute.call_count, 25)


class TestDataFormat(unittest.TestCase):
    """测试数据格式枚举"""

    def test_format_values(self):
        """测试格式枚举值"""
        self.assertEqual(DataFormat.CSV.value, "csv")
        self.assertEqual(DataFormat.JSON.value, "json")
        self.assertEqual(DataFormat.SQL.value, "sql")

    def test_format_from_string(self):
        """测试从字符串创建格式"""
        self.assertEqual(DataFormat("csv"), DataFormat.CSV)
        self.assertEqual(DataFormat("json"), DataFormat.JSON)
        self.assertEqual(DataFormat("sql"), DataFormat.SQL)


class TestIntegration(unittest.TestCase):
    """集成测试"""

    def setUp(self):
        """测试前准备"""
        self.connector = Mock()
        self.exporter = DataExporter(self.connector)
        self.importer = DataImporter(self.connector)
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        """测试后清理"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_export_import_roundtrip_csv(self):
        """测试CSV导出导入往返"""
        # 模拟原始数据
        original_data = [
            (1, "张三", "zhangsan@test.com"),
            (2, "李四", "lisi@test.com"),
        ]

        self.connector.execute.return_value = Mock(
            columns=["id", "name", "email"],
            rows=original_data
        )

        # 导出
        export_path = os.path.join(self.temp_dir, "roundtrip.csv")
        export_result = self.exporter.export_table(
            table_name="users",
            output_path=export_path,
            format="csv"
        )
        self.assertTrue(export_result["success"])

        # 验证文件内容
        with open(export_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            rows = list(reader)
            self.assertEqual(len(rows), 3)  # 表头+2行数据

    def test_export_import_roundtrip_json(self):
        """测试JSON导出导入往返"""
        original_data = [
            (1, "张三"),
            (2, "李四"),
        ]

        self.connector.execute.return_value = Mock(
            columns=["id", "name"],
            rows=original_data
        )

        # 导出
        export_path = os.path.join(self.temp_dir, "roundtrip.json")
        export_result = self.exporter.export_table(
            table_name="users",
            output_path=export_path,
            format="json"
        )
        self.assertTrue(export_result["success"])

        # 导入
        import_result = self.importer.import_json(
            input_path=export_path,
            table_name="users"
        )
        self.assertTrue(import_result["success"])
        self.assertEqual(import_result["imported_rows"], 2)


if __name__ == "__main__":
    unittest.main()
