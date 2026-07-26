"""
CLI 集成测试

文件功能：测试CLI基本功能

作者：AI Assistant
创建时间：2026-04-21
最后修改：2026-04-24 - 修复CLI参数格式
"""

import sys
import os
import subprocess
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestCLIIntegration(unittest.TestCase):
    """CLI 集成测试类"""

    @classmethod
    def run_cli(cls, args, prefix="DB"):
        """运行 CLI 命令并返回结果"""
        cmd = [sys.executable, "-m", "dbskiter", f"--prefix={prefix}"] + args
        # Windows 上 subprocess 默认 GBK 编码会导致 UnicodeDecodeError
        # 显式设置 encoding='utf-8' + errors='replace' 解决
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )
        return result

    def test_01_cli_help(self):
        """测试 CLI 帮助信息"""
        result = self.run_cli(["--help"])
        self.assertEqual(result.returncode, 0)
        self.assertIn("--prefix", result.stdout)

    def test_02_cli_version(self):
        """测试 CLI 版本信息"""
        result = self.run_cli(["--version"])
        self.assertEqual(result.returncode, 0)


if __name__ == '__main__':
    unittest.main()
