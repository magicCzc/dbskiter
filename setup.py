"""
数据库 Skills - Python 包配置

功能说明：
- 将数据库 Skills 打包为可安装的 Python 模块
- 支持 pip install 安装
- 提供统一的 Skill API

作者：Trae AI
创建时间：2026-04-16
"""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="dbskiter",
    version="2.0.0",
    author="Database Skills Team",
    author_email="skills@example.com",
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
        "jinja2>=3.0.0",
        "pydantic>=2.0.0",
    ],
    entry_points={
        "console_scripts": [
            "dbskiter=dbskiter.cli:main",
        ],
    },
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-asyncio>=0.21.0",
            "black>=23.0.0",
            "flake8>=6.0.0",
        ],
        "report": [
            "weasyprint>=59.0",
        ],
    },
)
