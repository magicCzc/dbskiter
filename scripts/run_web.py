#!/usr/bin/env python3
"""
Run DBSKiter Web UI

用法:
    python scripts/run_web.py                     # 默认 localhost:8000
    python scripts/run_web.py --host 0.0.0.0 --port 8080  # 自定义
"""

import sys
import os

# 确保项目根目录在 sys.path 中（解决未安装时的导入问题）
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import argparse
import uvicorn


def main():
    parser = argparse.ArgumentParser(description="DBSKiter Web UI")
    parser.add_argument("--host", default="127.0.0.1", help="监听地址 (默认 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000, help="监听端口 (默认 8000)")
    parser.add_argument("--reload", action="store_true", help="开发模式：自动重载")
    args = parser.parse_args()

    print(f"  ╔══════════════════════════════════════════╗")
    print(f"  ║        DBSKiter Web UI                  ║")
    print(f"  ║  数据库 AIOps 运维助手                   ║")
    print(f"  ╠══════════════════════════════════════════╣")
    print(f"  ║  http://{args.host}:{args.port}              ║")
    print(f"  ║  API: http://{args.host}:{args.port}/docs   ║")
    print(f"  ╚══════════════════════════════════════════╝")
    print()

    # 使用 app 对象而非字符串引用，避免 import 路径问题
    from dbskiter.web.app import app

    uvicorn.run(
        app,
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="info",
    )


if __name__ == "__main__":
    main()