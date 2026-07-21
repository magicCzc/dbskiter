# 贡献指南

感谢你考虑为 DBSKiter 做出贡献！本文档将帮助你快速上手开发流程。

## 开发环境搭建

### 1. 克隆代码

```bash
git clone https://github.com/magicCzc/dbskiter.git
cd dbskiter
```

### 2. 安装依赖

```bash
# 安装开发依赖（包括测试、代码风格、文档工具）
pip install -e ".[dev]"
```

开发依赖包括：
- `pytest` - 单元测试
- `pytest-cov` - 测试覆盖率
- `black` - 代码格式化
- `flake8` - 代码风格检查
- `mkdocs` + `mkdocs-material` - 文档站点

### 3. 安装 Pre-commit 钩子（推荐）

```bash
pip install pre-commit
pre-commit install
```

安装后，每次 `git commit` 会自动检查代码格式、风格和裸 `except`。

## 运行测试

```bash
# 运行核心单元测试（快速）
python -m pytest tests/unit/ tests/test_imports.py tests/test_models.py \
    tests/test_error_handler.py tests/test_query_result.py tests/test_sql_dialect.py \
    tests/test_validators.py tests/test_sql_fingerprint.py tests/test_sql_validation.py \
    tests/test_security_injection.py tests/test_cache.py tests/test_report_generator.py \
    tests/test_scheduler_backup.py -v

# 运行所有测试（含集成）
python -m pytest tests/ -v

# 运行性能基准
python -m pytest tests/test_benchmarks.py -v -m benchmark

# 运行覆盖率检查
python -m pytest --cov=dbskiter --cov-report=term --cov-fail-under=20
```

## 代码风格

本项目使用：
- **black** 格式化代码（行长度 120）
- **flake8** 检查风格（配置见 `.flake8`）

```bash
# 格式化代码
black dbskiter/

# 检查代码风格
flake8 dbskiter/
```

## 文档

文档使用 MkDocs + Material 主题：

```bash
# 本地预览
mkdocs serve
# 访问 http://127.0.0.1:8000/dbskiter/

# 构建静态文件
mkdocs build
```

文档源文件位于 `docs/` 目录。

## 提交 Pull Request

1. Fork 本仓库
2. 创建特性分支：`git checkout -b feature/your-feature`
3. 提交代码：遵循代码风格，添加测试
4. 推送分支：`git push origin feature/your-feature`
5. 创建 Pull Request，描述改动内容

## 报告 Bug

使用 GitHub Issues 提交 bug 报告：
https://github.com/magicCzc/dbskiter/issues

请包含：
- DBSKiter 版本（`dbskiter --version`）
- 操作系统和 Python 版本
- 复现步骤
- 预期行为和实际行为
- 错误日志（如有）

## 提交 Feature Request

欢迎提出新功能建议！请在 Issue 中描述：
- 功能用途和场景
- 期望的 API 或命令格式
- 是否愿意提交 PR

## 发布流程

维护者发布新版本的流程：
1. 更新 `dbskiter/__init__.py` 中的 `__version__`
2. 更新 `README.md` 的 CHANGELOG 部分
3. 提交 commit
4. 打 tag：`git tag v3.0.X`
5. 推送 tag：`git push origin v3.0.X`
6. GitHub Actions 自动构建并发布到 PyPI

## 联系方式

- GitHub: https://github.com/magicCzc/dbskiter
- Issues: https://github.com/magicCzc/dbskiter/issues

## 许可证

本项目使用 MIT 许可证 - 详见 [LICENSE](LICENSE) 文件。