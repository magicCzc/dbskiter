"""
数据库 Skills - Python 包配置

功能说明：
- 将数据库 Skills 打包为可安装的 Python 模块
- 支持 pip install 安装
- 提供统一的 Skill API

作者：MagiCzc
创建时间：2026-04-16
最后修改：2026-05-25
"""

import os
from setuptools import setup, find_packages

# 统一版本号管理 - 从包内读取版本
# 避免多处硬编码导致版本不一致
_version_file = os.path.join("dbskiter", "__init__.py")
with open(_version_file, "r", encoding="utf-8") as f:
    for line in f:
        if line.startswith("__version__"):
            # 提取版本号: __version__ = "x.y.z"
            version = line.split("=")[1].strip().strip('"').strip("'")
            break

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="dbskiter",
    version=version,
    author="MagiCzc",
    author_email="magiczc@139.com",
    description="数据库 Skills 集合 - 监控、诊断、安全、调度、SQL执行",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/magicCzc/dbskiter.git",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Database",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
    python_requires=">=3.8",
    install_requires=[
        "sqlalchemy>=2.0.0",
        "pymysql>=1.0.0",
        "psycopg2-binary>=2.9.0",
        "python-dotenv>=1.0.0",
        "pandas>=2.0.0",
        "numpy>=1.21.0",
        "requests>=2.28.0",
        "jinja2>=3.0.0",
        "pydantic>=2.0.0",
        "sqlparse>=0.5.0",
    ],
    entry_points={
        "console_scripts": [
            "dbskiter=dbskiter.cli.main:main",
        ],
    },
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-asyncio>=0.21.0",
            "black>=23.0.0",
            "flake8>=6.0.0",
        ],
        "oracle": [
            "oracledb>=1.4.0",
            "JayDeBeApi>=1.2.0",
        ],
        "report": [
            "weasyprint>=59.0",
        ],
    },
)
