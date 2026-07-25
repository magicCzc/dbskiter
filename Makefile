# DBSKiter Makefile
# 常用开发命令速查

.PHONY: install dev test lint format coverage docs clean web api-docs

# ── 安装 ──────────────────────────────────────────────────────────

install:  ## 安装核心依赖
	pip install -e "."

install-dev:  ## 安装开发依赖
	pip install -e ".[dev]"

install-web:  ## 安装 Web UI 依赖
	pip install -e ".[web]"

install-all: install install-dev install-web  ## 安装全部依赖

# ── 测试 ──────────────────────────────────────────────────────────

test:  ## 运行单元测试
	python -m pytest tests/ --ignore=tests/integration -v --tb=short

test-quick:  ## 快速运行核心测试
	python -m pytest tests/test_imports.py tests/test_cli_integration.py \
		tests/test_diagnose_skill_split.py tests/test_error_handler.py \
		-v --tb=short

test-all:  ## 运行全部测试（含集成）
	python -m pytest tests/ -v --tb=short

coverage:  ## 运行测试并检查覆盖率
	python -m pytest tests/ --cov=dbskiter --cov-report=term-missing \
		--ignore=tests/integration -v --tb=short

# ── 代码风格 ──────────────────────────────────────────────────────

lint:  ## 检查代码风格
	flake8 --config=.flake8 dbskiter/
	black --check --diff --line-length=120 dbskiter/

format:  ## 格式化代码
	black --line-length=120 dbskiter/

doc-check:  ## 检查文档一致性
	python scripts/check_doc_consistency.py

# ── 文档 ──────────────────────────────────────────────────────────

docs:  ## 构建 MkDocs 文档站
	mkdocs build

docs-serve:  ## 本地预览文档站
	mkdocs serve

api-docs:  ## 构建 Sphinx API 文档
	python scripts/build_api_docs.py

# ── Web UI ────────────────────────────────────────────────────────

web:  ## 启动 Web UI
	python scripts/run_web.py

web-dev:  ## 启动 Web UI（开发模式，自动重载）
	python scripts/run_web.py --reload

# ── 发布 ──────────────────────────────────────────────────────────

build:  ## 构建发布包
	python -m build

publish: build  ## 发布到 PyPI（需要 TWINE_PASSWORD）
	twine upload dist/*

# ── 清理 ──────────────────────────────────────────────────────────

clean:  ## 清理临时文件
	rm -rf build/ dist/ *.egg-info/
	rm -rf .pytest_cache/ .hypothesis/ __pycache__/
	rm -rf dbskiter/**/__pycache__/
	find . -name "*.pyc" -delete
	rm -rf docs/api/

# ── 帮助 ──────────────────────────────────────────────────────────

help:  ## 显示帮助
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'