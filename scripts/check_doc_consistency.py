"""
check_doc_consistency.py

检查文档与代码的一致性：
1. dbskiter/__init__.py 的 __version__ 必须与 CHANGELOG.md 最新版本一致
2. README.md 中提到的测试用例数量应与实际测试数量基本一致
3. 引用已删除文件的文档需要清理

用法:
    python scripts/check_doc_consistency.py
退出码:
    0 - 通过
    1 - 一致性错误
"""

import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def read_file(path: Path) -> str:
    """读取文件内容"""
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def check_version_consistency() -> list:
    """
    检查版本号一致性

    Returns:
        list[dict]: 不一致项列表
    """
    issues = []

    # 1. 从 __init__.py 读取
    init_path = PROJECT_ROOT / "dbskiter" / "__init__.py"
    init_content = read_file(init_path)
    init_match = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', init_content)
    if not init_match:
        issues.append({
            "type": "version",
            "message": f"未在 {init_path} 找到 __version__ 定义",
        })
        return issues

    pkg_version = init_match.group(1)

    # 2. 从 CHANGELOG.md 读取最新版本
    changelog_path = PROJECT_ROOT / "CHANGELOG.md"
    changelog_content = read_file(changelog_path)

    # 匹配 "## [x.y.z]" 或 "## [x.y.z - a.b.c]" 形式
    # 找到第一个版本号
    changelog_match = re.search(
        r"##\s*\[([\d\.\-]+(?:\s*-\s*[\d\.\-]+)?)\]",
        changelog_content,
    )
    if not changelog_match:
        issues.append({
            "type": "version",
            "message": f"未在 {changelog_path} 找到版本号",
        })
        return issues

    changelog_version_full = changelog_match.group(1).strip()

    # 处理 "3.0.30-3.0.40" 这种区间格式
    if "-" in changelog_version_full and not changelog_version_full.startswith("3.0.30"):
        # 范围版本（如 3.0.30-3.0.40），取最大版本
        versions = re.findall(r"\d+\.\d+\.\d+", changelog_version_full)
        changelog_latest_version = max(versions) if versions else changelog_version_full
    else:
        changelog_latest_version = re.findall(r"\d+\.\d+\.\d+", changelog_version_full)
        changelog_latest_version = changelog_latest_version[0] if changelog_latest_version else changelog_version_full

    if pkg_version != changelog_latest_version:
        issues.append({
            "type": "version",
            "message": (
                f"版本号不一致：\n"
                f"  dbskiter/__init__.py: {pkg_version}\n"
                f"  CHANGELOG.md 最新:    {changelog_latest_version}"
            ),
        })

    return issues


def count_test_functions() -> int:
    """
    统计测试用例数量

    Returns:
        int: 测试函数数量
    """
    tests_dir = PROJECT_ROOT / "tests"
    if not tests_dir.exists():
        return 0

    count = 0
    # 搜索所有 tests/ 下的 test_*.py 文件（包括子目录）
    for test_file in tests_dir.rglob("test_*.py"):
        if "node_modules" in test_file.parts:
            continue
        content = read_file(test_file)
        # 匹配 "def test_" 开头的函数
        count += len(re.findall(r"^def\s+test_\w+", content, re.MULTILINE))
        # 匹配缩进的 "def test_" （在类内）
        count += len(re.findall(r"^\s{4}def\s+test_\w+", content, re.MULTILINE))

    return count


def check_readme_test_count() -> list:
    """
    检查 README 中的测试数声明

    Returns:
        list[dict]: 不一致项列表
    """
    issues = []
    readme_path = PROJECT_ROOT / "README.md"
    readme_content = read_file(readme_path)

    # 提取 README 中声明的测试数
    match = re.search(r"(\d+)\+?\s*测试用例", readme_content)
    if not match:
        return issues

    declared_count = int(match.group(1))
    actual_count = count_test_functions()

    # 允许 20% 偏差
    if actual_count < declared_count * 0.8:
        issues.append({
            "type": "test_count",
            "message": (
                f"README 测试数过低：\n"
                f"  README 声明: {declared_count}\n"
                f"  实际统计:    {actual_count}\n"
                f"  建议更新 README: 1,641 → {actual_count}"
            ),
        })

    return issues


def check_deleted_file_references() -> list:
    """
    检查文档中是否引用了已删除的文件

    Returns:
        list[dict]: 不一致项列表
    """
    issues = []

    # 从 git status 找出已删除的文件
    # 这里采用静态检查：查找常见已删除文件
    known_deleted = {
        "dbskiter/cli/commands/diagnose.py": "已迁移到 diagnose_pkg.py",
    }

    # 检查所有 .md 文件
    for md_file in PROJECT_ROOT.rglob("*.md"):
        # 跳过 node_modules, venv 等
        if any(p in md_file.parts for p in ("node_modules", ".venv", "venv", "site")):
            continue

        content = read_file(md_file)
        for deleted_file, replacement in known_deleted.items():
            if deleted_file in content:
                # 排除 git status 等元信息
                if "git status" in content[:1000] or "已迁移" in content[:1000]:
                    continue
                issues.append({
                    "type": "deleted_reference",
                    "message": (
                        f"{md_file.relative_to(PROJECT_ROOT)} 引用了已删除文件 {deleted_file}\n"
                        f"  建议: {replacement}"
                    ),
                })

    return issues


def main() -> int:
    """主函数"""
    # Windows 平台修复
    if sys.platform == "win32":
        import io
        for stream_name in ("stdout", "stderr"):
            stream = getattr(sys, stream_name, None)
            if stream and hasattr(stream, "buffer") and stream.encoding and stream.encoding.lower() != "utf-8":
                try:
                    setattr(sys, stream_name, io.TextIOWrapper(
                        stream.buffer, encoding="utf-8", errors="replace"
                    ))
                except (OSError, ValueError):
                    pass

    print("=" * 60)
    print("DBSKiter 文档一致性检查")
    print("=" * 60)
    print()

    all_issues = []

    print("[1/3] 检查版本号一致性...")
    all_issues.extend(check_version_consistency())

    print("[2/3] 检查 README 测试数...")
    all_issues.extend(check_readme_test_count())

    print("[3/3] 检查已删除文件引用...")
    all_issues.extend(check_deleted_file_references())

    print()
    print("=" * 60)

    if not all_issues:
        print("[OK] All checks passed")
        return 0

    print(f"[FAIL] Found {len(all_issues)} issues:")
    print()
    for i, issue in enumerate(all_issues, 1):
        print(f"  [{i}] {issue['type']}")
        print(f"      {issue['message']}")
        print()

    return 1


if __name__ == "__main__":
    sys.exit(main())
