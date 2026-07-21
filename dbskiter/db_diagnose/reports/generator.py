"""
诊断报告生成器

文件功能：生成格式化的SQL诊断报告
主要类：
    - ReportGenerator: 报告生成器

作者：Magiczc
创建时间：2026-04-22
"""

import json
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


class ReportGenerator:
    """
    诊断报告生成器

    功能：
        1. 生成文本格式报告
        2. 生成Markdown格式报告
        3. 生成JSON格式报告
        4. 统计问题汇总

    使用示例：
        >>> generator = ReportGenerator()
        >>> report = generator.generate(analyses, format="markdown")
        >>> print(report)
    """

    def __init__(self):
        """初始化报告生成器"""
        logger.info("ReportGenerator 初始化完成")

    def generate(
        self,
        analyses: List[Dict[str, Any]],
        report_format: str = "text",
        include_fixes: bool = True
    ) -> str:
        """
        生成诊断报告

        参数：
            analyses: 分析结果列表
            report_format: 报告格式 (text/markdown/json)
            include_fixes: 是否包含修复SQL

        返回：
            str: 格式化的报告

        示例：
            >>> analyses = [{"success": True, "issues": [...]}]
            >>> report = generator.generate(analyses, format="markdown")
        """
        if report_format == "json":
            return self._generate_json_report(analyses)
        elif report_format == "markdown":
            return self._generate_markdown_report(analyses, include_fixes)
        else:
            return self._generate_text_report(analyses, include_fixes)

    def _generate_json_report(self, analyses: List[Dict[str, Any]]) -> str:
        """生成JSON格式报告"""
        # 统计信息
        total_issues = sum(len(a.get("issues", [])) for a in analyses if a.get("success"))
        critical = sum(
            sum(1 for i in a.get("issues", []) if i.get("severity") == "critical")
            for a in analyses if a.get("success")
        )
        high = sum(
            sum(1 for i in a.get("issues", []) if i.get("severity") == "high")
            for a in analyses if a.get("success")
        )

        data = {
            "summary": {
                "total_sql": len(analyses),
                "total_issues": total_issues,
                "critical": critical,
                "high": high,
            },
            "details": analyses
        }

        return json.dumps(data, indent=2, ensure_ascii=False)

    def _generate_markdown_report(
        self,
        analyses: List[Dict[str, Any]],
        include_fixes: bool
    ) -> str:
        """生成Markdown格式报告"""
        # 统计信息
        total_issues = sum(len(a.get("issues", [])) for a in analyses if a.get("success"))
        critical = sum(
            sum(1 for i in a.get("issues", []) if i.get("severity") == "critical")
            for a in analyses if a.get("success")
        )
        high = sum(
            sum(1 for i in a.get("issues", []) if i.get("severity") == "high")
            for a in analyses if a.get("success")
        )
        all_suggestions = []
        for a in analyses:
            if a.get("success"):
                all_suggestions.extend(a.get("index_suggestions", []))

        lines = [
            "# 数据库SQL优化报告",
            "",
            "## 摘要",
            f"- **分析SQL数量**: {len(analyses)}",
            f"- **发现问题总数**: {total_issues}",
            f"  - 严重问题: {critical}",
            f"  - 高危问题: {high}",
            f"- **索引建议**: {len(all_suggestions)} 个",
            "",
            "## 详细分析",
            ""
        ]

        for i, analysis in enumerate(analyses):
            if not analysis.get("success"):
                lines.append(f"### SQL {i+1} (分析失败)")
                lines.append(f"```sql\n{analysis.get('sql', 'N/A')}\n```")
                lines.append(f"**错误**: {analysis.get('error', 'Unknown')}")
                lines.append("")
                continue

            lines.append(f"### SQL {i+1}")
            lines.append(f"```sql\n{analysis['sql']}\n```")
            lines.append(f"**类型**: {analysis.get('sql_type', 'Unknown')}")
            lines.append(f"**估计成本**: {analysis.get('cost_estimate', {}).get('total_cost', 0):.2f}")
            lines.append("")

            if analysis.get("issues"):
                lines.append("**问题**:")
                for issue in analysis["issues"]:
                    lines.append(f"- [{issue['severity'].upper()}] {issue['description']}")
                lines.append("")

            if analysis.get("index_suggestions"):
                lines.append("**索引建议**:")
                for sug in analysis["index_suggestions"]:
                    lines.append(f"- {sug['table']}({', '.join(sug['columns'])})")
                    lines.append(f"  - 原因: {sug['reason']}")
                    if include_fixes and sug.get("create_sql"):
                        lines.append(f"  - SQL: `{sug['create_sql']}`")
                lines.append("")

        return "\n".join(lines)

    def _generate_text_report(
        self,
        analyses: List[Dict[str, Any]],
        include_fixes: bool
    ) -> str:
        """生成文本格式报告"""
        # 统计信息
        total_issues = sum(len(a.get("issues", [])) for a in analyses if a.get("success"))
        critical = sum(
            sum(1 for i in a.get("issues", []) if i.get("severity") == "critical")
            for a in analyses if a.get("success")
        )
        high = sum(
            sum(1 for i in a.get("issues", []) if i.get("severity") == "high")
            for a in analyses if a.get("success")
        )
        all_suggestions = []
        for a in analyses:
            if a.get("success"):
                all_suggestions.extend(a.get("index_suggestions", []))

        lines = [
            "=" * 70,
            "数据库SQL优化报告",
            "=" * 70,
            f"分析SQL数量: {len(analyses)}",
            f"发现问题总数: {total_issues}",
            f"  - 严重问题: {critical}",
            f"  - 高危问题: {high}",
            f"索引建议: {len(all_suggestions)} 个",
            "-" * 70,
        ]

        # 按表汇总
        table_issues = {}
        for analysis in analyses:
            if not analysis.get("success"):
                continue
            for issue in analysis.get("issues", []):
                table = issue.get("table", "unknown")
                if table not in table_issues:
                    table_issues[table] = []
                table_issues[table].append(issue)

        if table_issues:
            lines.append("\n按表汇总:")
            for table, issues in table_issues.items():
                lines.append(f"\n  [{table}]: {len(issues)} 个问题")

        # 可执行的修复
        if include_fixes and all_suggestions:
            lines.append("\n" + "-" * 70)
            lines.append("可执行的索引创建语句:")
            lines.append("-" * 70)
            for sug in all_suggestions[:10]:  # 最多显示10个
                if sug.get("create_sql"):
                    lines.append(f"\n-- {sug['table']}({', '.join(sug['columns'])})")
                    lines.append(f"{sug['create_sql']};")

        lines.append("\n" + "=" * 70)
        return "\n".join(lines)
