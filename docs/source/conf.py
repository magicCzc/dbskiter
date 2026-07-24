"""
Sphinx 文档配置

使用:
    pip install sphinx sphinx-autodoc-typehints myst-parser
    sphinx-apidoc -o docs/source/api dbskiter/ -f
    sphinx-build -b html docs/source docs/api
"""

import os
import sys

# 将项目根目录加入 sys.path
sys.path.insert(0, os.path.abspath(os.path.join(__file__, "..", "..", "..")))

project = "DBSKiter"
copyright = "2026, MagiCzc"
author = "MagiCzc"
version = "3.0.43"
release = "3.0.43"

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
    "sphinx.ext.autosummary",
    "sphinx_autodoc_typehints",
    "myst_parser",
]

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

# HTML 主题
html_theme = "sphinx_rtd_theme"
html_static_path = ["_static"]
html_theme_options = {
    "display_version": True,
    "navigation_depth": 4,
    "collapse_navigation": False,
}

# autodoc 配置
autodoc_default_options = {
    "members": True,
    "member-order": "bysource",
    "special-members": "__init__",
    "undoc-members": True,
    "exclude-members": "__weakref__",
}

# Napoleon 配置（Google/NumPy 风格 docstring）
napoleon_google_docstring = True
napoleon_numpy_docstring = False
napoleon_include_init_with_doc = True
napoleon_include_private_with_doc = False
napoleon_include_special_with_doc = True
napoleon_attr_annotations = True

# 自动摘要
autosummary_generate = True