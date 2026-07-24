#!/usr/bin/env python3
"""
Build Sphinx API documentation

用法:
    python scripts/build_api_docs.py          # 构建 API 文档
    python scripts/build_api_docs.py --serve   # 构建后启动 HTTP 服务预览
"""

import os
import sys
import argparse
import subprocess
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="Build DBSKiter API docs")
    parser.add_argument("--serve", action="store_true", help="构建后启动 HTTP 预览")
    parser.add_argument("--port", type=int, default=8888, help="预览端口 (默认 8888)")
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parent.parent
    source_dir = project_root / "docs" / "source"
    output_dir = project_root / "docs" / "api"

    # 1. 生成 API 文档
    print("[1/3] Generating API docs with sphinx-apidoc...")
    apidoc_cmd = [
        sys.executable, "-m", "sphinx.ext.apidoc", "-o",
        str(source_dir / "api"),
        str(project_root / "dbskiter"),
        "-f", "-d", "4",
        str(project_root / "dbskiter") + "/*/test*",
        str(project_root / "dbskiter") + "/*/__pycache__*",
    ]
    result = subprocess.run(apidoc_cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  WARNING: sphinx-apidoc returned {result.returncode}")
        print(f"  {result.stderr[:200]}")
    else:
        print(f"  OK: {len(result.stdout.splitlines())} files generated")

    # 2. 构建 HTML
    print(f"[2/3] Building HTML docs to {output_dir}...")
    build_cmd = [
        sys.executable, "-m", "sphinx", "-b", "html",
        str(source_dir), str(output_dir),
        "-W",  # Warnings as errors
    ]
    result = subprocess.run(build_cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  WARNING: Build returned {result.returncode}")
        print(f"  {result.stderr[:500]}")
    else:
        print(f"  OK: {output_dir}")

    # 3. 统计
    html_files = list(output_dir.rglob("*.html"))
    print(f"[3/3] Stats: {len(html_files)} HTML files generated")
    print(f"  Index: {output_dir / 'index.html'}")

    # 4. 预览
    if args.serve:
        import http.server
        import socketserver

        os.chdir(str(output_dir))
        handler = http.server.SimpleHTTPRequestHandler
        with socketserver.TCPServer(("", args.port), handler) as httpd:
            print(f"  Preview: http://localhost:{args.port}")
            httpd.serve_forever()


if __name__ == "__main__":
    main()