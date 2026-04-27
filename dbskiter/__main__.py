"""
dbskiter/__main__.py

支持 python -m dbskiter 调用

用法:
    python -m dbskiter monitor --database=jump
    python -m dbskiter diagnose --sql="SELECT * FROM users"
"""

from dbskiter.cli import main

if __name__ == "__main__":
    main()
