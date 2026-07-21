"""
cli/commands/lock.py

数据库锁分析命令 - 锁分析、死锁检测、锁等待链追踪
核心功能：分析当前锁、检测死锁、追踪锁等待链、生成报告

用法:
    dbskiter lock analyze           # 分析当前锁
    dbskiter lock deadlocks         # 检测死锁
    dbskiter lock chains            # 追踪锁等待链
    dbskiter lock report            # 生成锁分析报告
    dbskiter lock kill <事务ID>     # 终止阻塞事务
"""

import json
from argparse import ArgumentParser
from typing import Any, Dict, Optional

from .base import BaseCommand


class LockCommand(BaseCommand):
    """数据库锁分析命令"""

    name = "lock"
    description = "Database Lock Analyzer - 锁分析与死锁检测"
    help_text = "分析当前锁、检测死锁、追踪锁等待链"

    @classmethod
    def add_arguments(cls, parser: ArgumentParser) -> None:
        """添加锁分析命令参数"""
        parser.epilog = """
示例:
  dbskiter --database=jump lock analyze                        # 分析当前锁情况
  dbskiter --database=jump lock deadlocks                      # 检测死锁
  dbskiter --database=jump lock chains                         # 追踪锁等待链
  dbskiter --database=jump lock report                         # 生成锁分析报告
  dbskiter --database=jump lock kill 12345                     # 终止指定事务
        """
        subparsers = parser.add_subparsers(dest="lock_action", help="锁分析操作")

        # analyze 子命令 - 分析当前锁
        analyze_parser = subparsers.add_parser("analyze", help="分析当前锁情况")
        analyze_parser.add_argument(
            "--format", "-f",
            choices=["text", "json"],
            default="text",
            help="输出格式"
        )

        # deadlocks 子命令 - 检测死锁
        deadlock_parser = subparsers.add_parser("deadlocks", help="检测死锁")
        deadlock_parser.add_argument(
            "--format", "-f",
            choices=["text", "json"],
            default="text",
            help="输出格式"
        )

        # chains 子命令 - 锁等待链
        chain_parser = subparsers.add_parser("chains", help="追踪锁等待链")
        chain_parser.add_argument(
            "--format", "-f",
            choices=["text", "json"],
            default="text",
            help="输出格式"
        )

        # report 子命令 - 生成报告
        report_parser = subparsers.add_parser("report", help="生成锁分析报告")
        report_parser.add_argument(
            "--output", "-o",
            help="输出文件路径"
        )

        # kill 子命令 - 终止阻塞事务
        kill_parser = subparsers.add_parser("kill", help="终止阻塞事务")
        kill_parser.add_argument(
            "transaction_id",
            help="要终止的事务ID"
        )

    def execute(self) -> int:
        """执行锁分析命令"""
        from dbskiter.db_lock_analyzer.skill import LockAnalyzerSkill

        try:
            self.require_connector()
        except Exception as e:
            self.output.error(str(e))
            return 1

        try:
            skill = LockAnalyzerSkill(self.connector)

            action = getattr(self.args, 'lock_action', None)

            if self.output_mode != "rule":
                method_map = {
                    "analyze": lambda: skill.analyze_current_locks(),
                    "deadlocks": lambda: skill.detect_deadlocks(),
                    "chains": lambda: skill.trace_lock_chains(),
                    "report": lambda: skill.generate_lock_report(),
                }
                scenario_map = {
                    "analyze": "lock_analysis",
                    "deadlocks": "deadlock",
                    "chains": "lock_chain",
                    "report": "lock_report",
                }
                if action in method_map:
                    return self._execute_ai_mode(skill, action, method_map, scenario_map)
                if action != "kill":
                    self.output.error(f"不支持的操作: {action}")
                    return 1

            if action == "analyze":
                return self._analyze_locks(skill)
            elif action == "deadlocks":
                return self._detect_deadlocks(skill)
            elif action == "chains":
                return self._trace_chains(skill)
            elif action == "report":
                return self._generate_report(skill)
            elif action == "kill":
                return self._kill_transaction(skill)
            else:
                self.output.error("请指定锁分析操作: analyze, deadlocks, chains, report, kill")
                return 1

        except Exception as e:
            self.output.error(f"锁分析失败: {e}")
            return 1
        finally:
            if 'skill' in locals():
                skill.close()

    def _analyze_locks(self, skill) -> int:
        """分析当前锁"""
        result = skill.analyze_current_locks()

        # 保存结果供 --show-trace 追踪展示
        self._last_skill_result = result

        if not result.get('success'):
            self.output.error(f"锁分析失败: {result.get('message', '未知错误')}")
            return 1

        data = result.get('data', {})
        locks = data.get('locks', [])

        waiting_locks = [l for l in locks if l.get('lock_status') == "WAITING"]
        granted_locks = [l for l in locks if l.get('lock_status') == "GRANTED"]

        output_format = getattr(self.args, 'format', 'text')

        if output_format == "json":
            result = {
                "success": True,
                "total_locks": len(locks),
                "waiting_locks": len(waiting_locks),
                "granted_locks": len(granted_locks),
                "locks": locks
            }
            self.output.print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0

        # 文本输出
        self.output.print(f"\n{'='*60}")
        self.output.print("锁分析结果")
        self.output.print(f"{'='*60}")

        self.output.print(f"\n当前锁统计:")
        self.output.print(f"  总锁数: {len(locks)}")
        self.output.print(f"  等待中: {len(waiting_locks)}")
        self.output.print(f"  已授予: {len(granted_locks)}")

        if waiting_locks:
            self.output.warning(f"\n等待中的锁 ({len(waiting_locks)}个):")
            for lock in waiting_locks[:10]:  # 只显示前10个
                self.output.print(f"  事务 {lock.get('transaction_id')}: {lock.get('table_name')} - {lock.get('lock_mode')}")
                query_sql = lock.get('query_sql', '')
                if query_sql:
                    self.output.print(f"    SQL: {query_sql[:80]}...")
        else:
            self.output.print("\n当前无等待中的锁")

        return 0

    def _detect_deadlocks(self, skill) -> int:
        """检测死锁"""
        result = skill.detect_deadlocks()

        if not result.get('success'):
            self.output.error(f"死锁检测失败: {result.get('message', '未知错误')}")
            return 1

        data = result.get('data', {})
        deadlocks = data.get('deadlocks', [])

        output_format = getattr(self.args, 'format', 'text')

        if output_format == "json":
            result = {
                "success": True,
                "deadlock_count": len(deadlocks),
                "deadlocks": deadlocks
            }
            self.output.print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0

        self.output.print(f"\n{'='*60}")
        self.output.print("死锁检测结果")
        self.output.print(f"{'='*60}")

        if deadlocks:
            self.output.error(f"\n检测到死锁: {len(deadlocks)}个")
            for dl in deadlocks:
                self.output.error(f"\n  死锁ID: {dl.get('deadlock_id')}")
                self.output.print(f"  检测时间: {dl.get('detected_at')}")
                self.output.print(f"  牺牲事务: {dl.get('victim_transaction')}")
                self.output.print(f"  解决建议: {dl.get('resolution')}")
        else:
            self.output.print("\n未检测到死锁")

        return 0

    def _trace_chains(self, skill) -> int:
        """追踪锁等待链"""
        result = skill.trace_lock_wait_chain()

        if not result.get('success'):
            self.output.error(f"锁等待链追踪失败: {result.get('message', '未知错误')}")
            return 1

        data = result.get('data', {})
        chains = data.get('chains', [])

        output_format = getattr(self.args, 'format', 'text')

        if output_format == "json":
            result = {
                "success": True,
                "chain_count": len(chains),
                "chains": chains
            }
            self.output.print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0

        self.output.print(f"\n{'='*60}")
        self.output.print("锁等待链追踪结果")
        self.output.print(f"{'='*60}")

        if chains:
            self.output.warning(f"\n发现锁等待链: {len(chains)}个")
            for chain in chains:
                self.output.warning(f"\n  链ID: {chain.get('chain_id')}")
                self.output.print(f"  根事务: {chain.get('root_transaction')}")
                self.output.print(f"  链深度: {chain.get('depth')}")
                self.output.print(f"  总等待时间: {chain.get('total_wait_time', 0):.2f}秒")
                self.output.print("  事务链:")
                for node in chain.get('nodes', []):
                    self.output.print(f"    -> 事务 {node.get('transaction_id')} (等待 {node.get('wait_time', 0):.2f}秒)")
        else:
            self.output.print("\n未发现锁等待链")

        return 0

    def _generate_report(self, skill) -> int:
        """生成锁分析报告"""
        result = skill.generate_lock_report()

        if not result.get('success'):
            self.output.error(f"报告生成失败: {result.get('message', '未知错误')}")
            return 1

        data = result.get('data', {})
        output_path = getattr(self.args, 'output', None)

        if output_path:
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            self.output.print(f"报告已保存: {output_path}")
        else:
            self.output.print(json.dumps(data, ensure_ascii=False, indent=2))

        return 0

    def _kill_transaction(self, skill) -> int:
        """终止阻塞事务"""
        from dbskiter.cli.readonly_middleware import is_readonly_mode

        # 只读模式下禁止kill操作
        if is_readonly_mode():
            self.output.error("只读模式下禁止终止事务（kill操作属于写操作）")
            self.output.info("如需执行此操作，请关闭只读模式（设置DBSKITER_READ_ONLY=false）")
            return 1

        transaction_id = self.args.transaction_id

        result = skill.kill_blocking_transaction(transaction_id)

        if result.get('success'):
            self.output.print(f"已终止事务: {transaction_id}")
            return 0
        else:
            self.output.error(f"终止事务失败: {transaction_id} - {result.get('message', '未知错误')}")
            return 1
