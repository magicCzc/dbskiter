"""
cli/commands/scheduler.py

数据库调度命令 - 任务调度与工作流管理
核心功能：备份、定时任务管理、任务执行日志
"""

import json
from argparse import ArgumentParser
from datetime import datetime

from .base import BaseCommand
from dbskiter.shared.utils import format_bytes


class SchedulerCommand(BaseCommand):
    """数据库调度命令"""
    
    name = "scheduler"
    description = "Database Scheduler - 任务调度与备份管理"
    help_text = "数据库备份、定时任务管理、任务日志"
    
    @classmethod
    def add_arguments(cls, parser: ArgumentParser) -> None:
        """添加调度命令参数"""
        subparsers = parser.add_subparsers(dest="scheduler_action", help="调度操作")
        
        # ==================== 核心命令 ====================
        
        # backup 子命令 - 执行备份
        backup_parser = subparsers.add_parser("backup", help="执行备份")
        backup_parser.add_argument("--type", choices=["full", "table", "incremental"],
                                  default="full", help="备份类型")
        backup_parser.add_argument("--compress", action="store_true", help="压缩备份")
        backup_parser.add_argument("--tables", help="指定表（逗号分隔）")
        backup_parser.add_argument("--output-dir", help="输出目录")
        
        # backup-verify 子命令 - 验证备份
        verify_parser = subparsers.add_parser("backup-verify", help="验证备份文件完整性")
        verify_parser.add_argument("file", help="备份文件路径")
        
        # backup-restore 子命令 - 恢复备份
        restore_parser = subparsers.add_parser("backup-restore", help="从备份文件恢复数据库")
        restore_parser.add_argument("file", help="备份文件路径")
        restore_parser.add_argument("--target-db", help="目标数据库名")
        
        # task 子命令 - 定时任务管理
        task_parser = subparsers.add_parser("task", help="定时任务管理")
        task_subparsers = task_parser.add_subparsers(dest="task_action", help="任务操作")
        
        # task list - 列出任务
        task_list_parser = task_subparsers.add_parser("list", help="列出所有定时任务")
        
        # task add - 添加任务
        task_add_parser = task_subparsers.add_parser("add", help="添加定时任务")
        task_add_parser.add_argument("name", help="任务名称")
        task_add_parser.add_argument("schedule", help="Cron表达式 (如 \"0 2 * * *\")")
        task_add_parser.add_argument("--type", choices=["backup", "analyze", "vacuum", "custom"],
                                    default="backup", help="任务类型")
        task_add_parser.add_argument("--params", help="任务参数（JSON格式）")
        task_add_parser.add_argument("--enabled", action="store_true", default=True, help="立即启用")
        
        # task remove - 删除任务
        task_remove_parser = task_subparsers.add_parser("remove", help="删除定时任务")
        task_remove_parser.add_argument("name", help="任务名称")
        
        # task enable/disable - 启用/禁用任务
        task_enable_parser = task_subparsers.add_parser("enable", help="启用定时任务")
        task_enable_parser.add_argument("name", help="任务名称")
        
        task_disable_parser = task_subparsers.add_parser("disable", help="禁用定时任务")
        task_disable_parser.add_argument("name", help="任务名称")
        
        # task run - 立即执行任务
        task_run_parser = task_subparsers.add_parser("run", help="立即执行任务")
        task_run_parser.add_argument("name", help="任务名称")
        
        # logs 子命令 - 查看任务日志
        logs_parser = subparsers.add_parser("logs", help="查看任务执行日志")
        logs_parser.add_argument("--task", help="指定任务名称")
        logs_parser.add_argument("--limit", type=int, default=20, help="返回记录数")
        logs_parser.add_argument("--status", choices=["success", "failed", "all"],
                                default="all", help="过滤状态")

        # daemon 子命令 - 调度器守护进程管理
        daemon_parser = subparsers.add_parser("daemon", help="调度器守护进程管理")
        daemon_subparsers = daemon_parser.add_subparsers(dest="daemon_action", help="守护进程操作")

        # daemon start - 启动调度器
        daemon_start_parser = daemon_subparsers.add_parser("start", help="启动调度器")

        # daemon stop - 停止调度器
        daemon_stop_parser = daemon_subparsers.add_parser("stop", help="停止调度器")

        # daemon status - 查看调度器状态
        daemon_status_parser = daemon_subparsers.add_parser("status", help="查看调度器状态")

        # workflow 子命令 - DAG工作流管理
        workflow_parser = subparsers.add_parser("workflow", help="DAG工作流管理")
        workflow_subparsers = workflow_parser.add_subparsers(dest="workflow_action", help="工作流操作")

        # workflow create - 创建工作流
        workflow_create_parser = workflow_subparsers.add_parser("create", help="创建工作流")
        workflow_create_parser.add_argument("name", help="工作流名称")
        workflow_create_parser.add_argument("--desc", help="工作流描述")

        # workflow add-task - 添加任务到工作流
        workflow_add_parser = workflow_subparsers.add_parser("add-task", help="添加任务到工作流")
        workflow_add_parser.add_argument("workflow", help="工作流名称")
        workflow_add_parser.add_argument("task", help="任务名称")
        workflow_add_parser.add_argument("--type", choices=["backup", "analyze", "vacuum", "custom"],
                                        default="backup", help="任务类型")
        workflow_add_parser.add_argument("--depends", help="依赖任务（逗号分隔）")

        # workflow submit - 提交执行工作流
        workflow_submit_parser = workflow_subparsers.add_parser("submit", help="提交执行工作流")
        workflow_submit_parser.add_argument("name", help="工作流名称")

        # workflow list - 列出工作流
        workflow_list_parser = workflow_subparsers.add_parser("list", help="列出所有工作流")

        # workflow status - 查看工作流状态
        workflow_status_parser = workflow_subparsers.add_parser("status", help="查看工作流状态")
        workflow_status_parser.add_argument("name", help="工作流名称")
    
    def execute(self) -> int:
        """执行调度命令"""
        from dbskiter.db_scheduler.skill import SchedulerSkill

        action = getattr(self.args, 'scheduler_action', None)

        if not action:
            self.output.error("请指定操作: backup, task, logs, daemon, workflow")
            return 1

        if action == "daemon":
            try:
                daemon_action = getattr(self.args, 'daemon_action', None)
                if daemon_action == "status":
                    skill = SchedulerSkill.__new__(SchedulerSkill)
                    skill._tasks = {}
                    skill._running = False
                    skill._scheduler_thread = None
                    return self._manage_daemon(skill)

                skill = SchedulerSkill(self.connector)
                return self._manage_daemon(skill)
            except Exception as e:
                self.output.error(f"调度操作失败: {e}")
                return 1
            finally:
                if 'skill' in locals():
                    try:
                        skill.close()
                    except:
                        pass

        try:
            skill = SchedulerSkill(self.connector)

            if self.output_mode != "rule":
                method_map = {
                    "backup": lambda: skill.backup(
                        backup_type=getattr(self.args, 'type', 'full'),
                        tables=getattr(self.args, 'tables', '').split(',') if getattr(self.args, 'tables', None) else None,
                    ),
                    "backup-verify": lambda: skill.verify_backup(
                        getattr(self.args, 'file', ''),
                    ),
                    "backup-restore": lambda: skill.restore_backup(
                        getattr(self.args, 'file', ''),
                        target_db=getattr(self.args, 'target_db', None),
                    ),
                    "logs": lambda: skill.get_task_logs(
                        task_name=getattr(self.args, 'task', None),
                        limit=getattr(self.args, 'limit', 50),
                        status=getattr(self.args, 'status', 'all'),
                    ),
                }
                scenario_map = {
                    "backup": "backup",
                    "backup-verify": "backup_verify",
                    "backup-restore": "backup_restore",
                    "logs": "scheduler_logs",
                }
                if action in method_map:
                    return self._execute_ai_mode(skill, action, method_map, scenario_map)

            if action == "backup":
                return self._execute_backup(skill)
            elif action == "backup-verify":
                return self._execute_verify(skill)
            elif action == "backup-restore":
                return self._execute_restore(skill)
            elif action == "task":
                return self._manage_tasks(skill)
            elif action == "logs":
                return self._view_logs(skill)
            elif action == "workflow":
                return self._manage_workflow(skill)
            else:
                self.output.error(f"未知操作: {action}")
                return 1

        except Exception as e:
            self.output.error(f"调度操作失败: {e}")
            return 1
        finally:
            if 'skill' in locals():
                skill.close()
    
    def _execute_backup(self, skill) -> int:
        """执行备份"""
        tables = self.args.tables.split(',') if self.args.tables else None
        backup_type = self.args.type
        # 如果指定了表但未指定table类型, 自动切换
        if tables and backup_type == "full":
            backup_type = "table"

        result = skill.backup(
            backup_type=backup_type,
            tables=tables,
            output_dir=self.args.output_dir,
        )

        # skill.backup() 返回 create_success_response/create_error_response 格式
        # 成功: {'success': True, 'data': {...}, 'message': '...'}
        # 失败: {'success': False, 'error': '...', 'code': '...'}
        success = result.get('success', False)

        if success:
            data = result.get('data', {})

            # 多表备份返回汇总格式
            if "results" in data:
                summary = f"备份成功 [{data.get('success_count', 0)}/{data.get('total', 0)}]"
                self.output.print(f"\n{'='*60}")
                self.output.print(f"摘要: {summary}")
                self.output.print(f"{'='*60}")
                self.output.success(f"\n备份完成")
                for item in data.get('results', []):
                    self.output.print(f"  表: {', '.join(item.get('tables', []))}")
                    self.output.print(f"  文件: {item.get('file_path', 'N/A')}")
                    self.output.print(f"  大小: {self._format_bytes(item.get('file_size', 0))}")
                    self.output.print(f"  耗时: {item.get('duration_ms', 0) / 1000:.1f}秒")
                    self.output.print(f"  {'-'*40}")
                return 0

            # 单表/全量备份返回单个结果
            file_path = data.get('file_path', 'N/A')
            file_size = data.get('file_size', 0)
            duration_ms = data.get('duration_ms', 0)
            backup_id = data.get('backup_id', 'N/A')
            backup_type = data.get('backup_type', 'unknown')
            tables = data.get('tables', [])

            summary = f"备份成功 [{backup_id}]"
            self.output.print(f"\n{'='*60}")
            self.output.print(f"摘要: {summary}")
            self.output.print(f"{'='*60}")
            self.output.success(f"\n备份完成")
            self.output.print(f"备份文件: {file_path}")
            self.output.print(f"文件大小: {self._format_bytes(file_size)}")
            self.output.print(f"耗时: {duration_ms / 1000:.1f}秒")
            self.output.print(f"类型: {backup_type}")
            if tables:
                self.output.print(f"表: {', '.join(tables)}")
            return 0
        else:
            error_msg = result.get('error', '未知错误')
            summary = f"备份失败: {error_msg}"
            self.output.print(f"\n{'='*60}")
            self.output.print(f"摘要: {summary}")
            self.output.print(f"{'='*60}")
            self.output.error(f"\n备份失败")
            self.output.error(f"错误: {error_msg}")
            code = result.get('code')
            if code:
                self.output.print(f"错误码: {code}")
            return 1
    
    def _execute_verify(self, skill) -> int:
        """执行备份验证"""
        file_path = self.args.file
        result = skill.verify_backup(file_path)

        success = result.get('success', False)
        if success:
            self.output.success(f"\n备份文件验证通过")
            self.output.print(f"文件: {file_path}")
            return 0
        else:
            self.output.error(f"\n备份文件验证失败")
            self.output.error(f"错误: {result.get('error', '未知错误')}")
            return 1

    def _execute_restore(self, skill) -> int:
        """执行备份恢复"""
        file_path = self.args.file
        target_db = getattr(self.args, 'target_db', None)

        self.output.print(f"\n{'='*60}")
        self.output.print("警告: 恢复操作将覆盖目标数据库中的数据")
        self.output.print(f"{'='*60}")

        result = skill.restore_backup(file_path, target_db)

        success = result.get('success', False)
        if success:
            self.output.success(f"\n恢复完成")
            self.output.print(f"备份文件: {file_path}")
            return 0
        else:
            self.output.error(f"\n恢复失败")
            self.output.error(f"错误: {result.get('error', '未知错误')}")
            return 1

    def _manage_tasks(self, skill) -> int:
        """管理定时任务"""
        task_action = getattr(self.args, 'task_action', None)
        
        if not task_action:
            self.output.error("请指定任务操作: list, add, remove, enable, disable, run")
            return 1
        
        if task_action == "list":
            return self._list_tasks(skill)
        elif task_action == "add":
            return self._add_task(skill)
        elif task_action == "remove":
            return self._remove_task(skill)
        elif task_action == "enable":
            return self._enable_task(skill, True)
        elif task_action == "disable":
            return self._enable_task(skill, False)
        elif task_action == "run":
            return self._run_task_now(skill)
        else:
            self.output.error(f"未知任务操作: {task_action}")
            return 1
    
    def _list_tasks(self, skill) -> int:
        """列出所有定时任务"""
        response = skill.list_tasks()

        # 处理response格式
        if isinstance(response, dict):
            if response.get('status') == 'error':
                self.output.error(f"获取任务列表失败: {response.get('error', '未知错误')}")
                return 1
            tasks = response.get('data', {}).get('tasks', [])
        else:
            tasks = response

        enabled_count = sum(1 for t in tasks if t.get('enabled'))
        disabled_count = len(tasks) - enabled_count

        summary = f"共{len(tasks)}个任务（{enabled_count}个启用，{disabled_count}个禁用）"

        self.output.print(f"\n{'='*60}")
        self.output.print(f"摘要: {summary}")
        self.output.print(f"{'='*60}")

        if not tasks:
            self.output.print("\n暂无定时任务")
            return 0

        self.output.print(f"\n{'任务名称':<20} {'类型':<10} {'调度':<15} {'状态':<8} {'下次执行'}")
        self.output.print("-" * 80)

        for task in tasks:
            name = task.get('name', '')[:18]
            task_type = task.get('task_type', '')[:8]
            schedule = task.get('schedule', '')[:13]
            status = "启用" if task.get('enabled') else "禁用"
            next_run = task.get('next_run', '未知')[:16]

            self.output.print(f"{name:<20} {task_type:<10} {schedule:<15} {status:<8} {next_run}")

        self.output.print(f"\n提示: 使用 'scheduler task add' 添加新任务")
        return 0
    
    def _add_task(self, skill) -> int:
        """添加定时任务"""
        name = self.args.name
        schedule = self.args.schedule
        task_type = self.args.type
        
        # 验证Cron表达式
        from dbskiter.db_scheduler.skill import CronParser
        if not CronParser.validate(schedule):
            self.output.error(f"无效的Cron表达式: {schedule}")
            self.output.print("格式: 分 时 日 月 周 (如 \"0 2 * * *\" 表示每天凌晨2点)")
            return 1
        
        # 解析参数
        params = {}
        if self.args.params:
            try:
                params = json.loads(self.args.params)
            except json.JSONDecodeError as e:
                self.output.error(f"参数JSON格式错误: {e}")
                return 1
        
        # 添加任务
        result = skill.schedule_task(
            name=name,
            schedule=schedule,
            task_type=task_type,
            params=params,
            enabled=self.args.enabled
        )
        
        if result.get('success'):
            self.output.success(f"\n任务添加成功")
            self.output.print(f"任务名称: {name}")
            self.output.print(f"调度规则: {schedule}")
            self.output.print(f"任务类型: {task_type}")
            self.output.print(f"下次执行: {result.get('next_run', '未知')}")
            
            if not self.args.enabled:
                self.output.print("状态: 已禁用（使用 'scheduler task enable' 启用）")
        else:
            self.output.error(f"\n任务添加失败")
            self.output.error(f"错误: {result.get('error', '未知错误')}")
            return 1
        
        return 0
    
    def _remove_task(self, skill) -> int:
        """删除定时任务"""
        name = self.args.name
        
        result = skill.remove_task(name)
        
        if result.get('success'):
            self.output.success(f"\n任务 '{name}' 已删除")
        else:
            self.output.error(f"\n删除失败")
            self.output.error(f"错误: {result.get('error', '未知错误')}")
            return 1
        
        return 0
    
    def _enable_task(self, skill, enabled: bool) -> int:
        """启用/禁用定时任务"""
        name = self.args.name
        action_text = "启用" if enabled else "禁用"
        
        result = skill.enable_task(name, enabled)
        
        if result.get('success'):
            self.output.success(f"\n任务 '{name}' 已{action_text}")
            if enabled and result.get('next_run'):
                self.output.print(f"下次执行: {result['next_run']}")
        else:
            self.output.error(f"\n{action_text}失败")
            self.output.error(f"错误: {result.get('error', '未知错误')}")
            return 1
        
        return 0
    
    def _run_task_now(self, skill) -> int:
        """立即执行任务"""
        from dbskiter.cli.readonly_middleware import is_readonly_mode

        # 只读模式下禁止立即执行任务（可能触发写操作）
        if is_readonly_mode():
            self.output.error("只读模式下禁止立即执行任务（任务可能包含写操作）")
            self.output.info("如需执行此操作，请关闭只读模式（设置DBSKITER_READ_ONLY=false）")
            return 1

        name = self.args.name
        
        self.output.print(f"\n正在执行任务 '{name}'...")
        self.output.print(f"{'='*60}")
        
        result = skill.run_task_now(name)
        
        if result.get('success'):
            self.output.success(f"\n任务执行成功")
            self.output.print(f"耗时: {result.get('duration_seconds', 0):.1f}秒")
            if result.get('result'):
                self.output.print(f"结果: {result['result']}")
        else:
            self.output.error(f"\n任务执行失败")
            self.output.error(f"错误: {result.get('error', '未知错误')}")
            return 1
        
        return 0
    
    def _view_logs(self, skill) -> int:
        """查看任务执行日志"""
        response = skill.get_task_logs(
            task_name=self.args.task,
            limit=self.args.limit,
            status=self.args.status
        )

        if not response.get('success'):
            self.output.error(f"获取日志失败: {response.get('message', '未知错误')}")
            return 1

        data = response.get('data', {})
        logs = data.get('logs', [])

        summary = f"共{len(logs)}条日志记录"
        if self.args.task:
            summary += f" (任务: {self.args.task})"
        if self.args.status != "all":
            summary += f" (状态: {self.args.status})"

        self.output.print(f"\n{'='*60}")
        self.output.print(f"摘要: {summary}")
        self.output.print(f"{'='*60}")

        if not logs:
            self.output.print("\n暂无执行日志")
            return 0

        self.output.print(f"\n{'时间':<20} {'任务':<20} {'状态':<8} {'结果'}")
        self.output.print("-" * 90)

        for log in logs:
            time_str = log.get('start_time', '')[:19] if log.get('start_time') else ''
            task_name = log.get('task_name', '')[:18]
            status = log.get('status', '')[:6]
            result = log.get('result', '')[:25] if log.get('result') else '-'

            if status == "success":
                status_str = "成功"
            elif status == "failed":
                status_str = "失败"
            else:
                status_str = status

            self.output.print(f"{time_str:<20} {task_name:<20} {status_str:<8} {result}")

        return 0

    def _manage_daemon(self, skill) -> int:
        """管理调度器守护进程"""
        daemon_action = getattr(self.args, 'daemon_action', None)

        if not daemon_action:
            self.output.error("请指定守护进程操作: start, stop, status")
            return 1

        if daemon_action == "start":
            return self._start_daemon(skill)
        elif daemon_action == "stop":
            return self._stop_daemon(skill)
        elif daemon_action == "status":
            return self._daemon_status(skill)
        else:
            self.output.error(f"未知守护进程操作: {daemon_action}")
            return 1

    def _start_daemon(self, skill) -> int:
        """启动调度器守护进程"""
        self.output.print("\n正在启动调度器守护进程...")
        self.output.print(f"{'='*60}")

        result = skill.start_scheduler()

        if result.get('status') == 'success':
            self.output.success("\n调度器已启动")
            self.output.print("说明: 调度器将在后台自动执行定时任务")
            self.output.print("提示: 使用 'scheduler daemon status' 查看状态")
            self.output.print("提示: 使用 'scheduler daemon stop' 停止调度器")
        else:
            self.output.error(f"\n启动失败")
            self.output.error(f"错误: {result.get('error', '未知错误')}")
            return 1

        return 0

    def _stop_daemon(self, skill) -> int:
        """停止调度器守护进程"""
        self.output.print("\n正在停止调度器守护进程...")
        self.output.print(f"{'='*60}")

        result = skill.stop_scheduler()

        if result.get('status') == 'success':
            self.output.success("\n调度器已停止")
            self.output.print("说明: 定时任务将不再自动执行")
        else:
            self.output.error(f"\n停止失败")
            self.output.error(f"错误: {result.get('error', '未知错误')}")
            return 1

        return 0

    def _daemon_status(self, skill) -> int:
        """查看调度器状态"""
        result = skill.get_scheduler_status()

        if not result.get('success'):
            self.output.error(f"获取状态失败: {result.get('error', '未知错误')}")
            return 1

        data = result.get('data', {})
        running = data.get('running', False)
        total_tasks = data.get('total_tasks', 0)
        enabled_tasks = data.get('enabled_tasks', 0)
        thread_alive = data.get('thread_alive', False)

        status = "运行中" if running else "已停止"
        thread_status = "正常" if thread_alive else "未启动"

        self.output.print(f"\n{'='*60}")
        self.output.print(f"调度器状态: {status}")
        self.output.print(f"{'='*60}")

        self.output.print(f"\n运行状态: {'运行中' if running else '已停止'}")
        self.output.print(f"线程状态: {thread_status}")
        self.output.print(f"任务总数: {total_tasks}")
        self.output.print(f"启用任务: {enabled_tasks}")

        if running:
            self.output.print(f"\n说明: 调度器正在后台运行，每30秒检查一次任务")
            self.output.print(f"提示: 使用 'scheduler task list' 查看任务详情")
        else:
            self.output.print(f"\n说明: 调度器已停止，定时任务不会自动执行")
            self.output.print(f"提示: 使用 'scheduler daemon start' 启动调度器")

        return 0

    def _manage_workflow(self, skill) -> int:
        """管理工作流"""
        workflow_action = getattr(self.args, 'workflow_action', None)

        if not workflow_action:
            self.output.error("请指定工作流操作: create, add-task, submit, list, status")
            return 1

        if workflow_action == "create":
            return self._create_workflow(skill)
        elif workflow_action == "add-task":
            return self._add_task_to_workflow(skill)
        elif workflow_action == "submit":
            return self._submit_workflow(skill)
        elif workflow_action == "list":
            return self._list_workflows(skill)
        elif workflow_action == "status":
            return self._workflow_status(skill)
        else:
            self.output.error(f"未知工作流操作: {workflow_action}")
            return 1

    def _create_workflow(self, skill) -> int:
        """创建工作流"""
        name = self.args.name
        desc = getattr(self.args, 'desc', '')

        workflow = skill.create_workflow(name, desc)

        self.output.success(f"\n工作流 '{name}' 已创建")
        if desc:
            self.output.print(f"描述: {desc}")
        self.output.print(f"\n提示: 使用 'scheduler workflow add-task' 添加任务")
        self.output.print(f"提示: 使用 'scheduler workflow submit' 提交执行")

        return 0

    def _add_task_to_workflow(self, skill) -> int:
        """添加任务到工作流"""
        workflow_name = self.args.workflow
        task_name = self.args.task
        task_type = self.args.type
        depends = self.args.depends.split(',') if self.args.depends else []

        from dbskiter.db_scheduler.skill import TaskNode, TaskType

        # 获取工作流
        if workflow_name not in skill._workflows:
            self.output.error(f"工作流不存在: {workflow_name}")
            return 1

        workflow = skill._workflows[workflow_name]

        # 创建任务节点
        task_node = TaskNode(
            task_id=task_name,
            task_type=TaskType(task_type)
        )

        # 添加依赖
        for dep in depends:
            if dep.strip():
                task_node.add_dependency(dep.strip())

        # 添加到工作流
        workflow.add_task(task_node)

        self.output.success(f"\n任务 '{task_name}' 已添加到工作流 '{workflow_name}'")
        self.output.print(f"任务类型: {task_type}")
        if depends:
            self.output.print(f"依赖任务: {', '.join(depends)}")

        return 0

    def _submit_workflow(self, skill) -> int:
        """提交执行工作流"""
        from dbskiter.cli.readonly_middleware import is_readonly_mode

        # 只读模式下禁止提交工作流（可能触发写操作）
        if is_readonly_mode():
            self.output.error("只读模式下禁止提交工作流（工作流可能包含写操作）")
            self.output.info("如需执行此操作，请关闭只读模式（设置DBSKITER_READ_ONLY=false）")
            return 1

        name = self.args.name

        self.output.print(f"\n正在执行工作流 '{name}'...")
        self.output.print(f"{'='*60}")

        result = skill.submit_workflow_by_name(name)

        if result.get('success'):
            self.output.success(f"\n工作流执行完成")

            # 显示执行结果
            data = result.get('data', {})
            results = data.get('results', [])

            if results:
                self.output.print(f"\n执行结果:")
                self.output.print(f"{'任务':<20} {'状态':<10} {'耗时':<10}")
                self.output.print("-" * 50)

                for r in results:
                    task_id = r.get('task_id', '')[:18]
                    status = r.get('status', '')
                    duration = f"{r.get('duration_ms', 0)}ms" if r.get('duration_ms') else '-'

                    if status == "success":
                        status_str = "成功"
                    elif status == "rejected":
                        status_str = "拒绝"
                    else:
                        status_str = status

                    self.output.print(f"{task_id:<20} {status_str:<10} {duration:<10}")
        else:
            self.output.error(f"\n工作流执行失败")
            self.output.error(f"错误: {result.get('error', '未知错误')}")
            return 1

        return 0

    def _list_workflows(self, skill) -> int:
        """列出所有工作流"""
        workflows = skill._workflows

        self.output.print(f"\n{'='*60}")
        self.output.print(f"工作流列表: 共{len(workflows)}个工作流")
        self.output.print(f"{'='*60}")

        if not workflows:
            self.output.print("\n暂无工作流")
            return 0

        self.output.print(f"\n{'工作流名称':<20} {'任务数':<10} {'描述'}")
        self.output.print("-" * 60)

        for name, workflow in workflows.items():
            task_count = len(workflow.tasks)
            desc = workflow.description[:30] if workflow.description else '-'
            self.output.print(f"{name:<20} {task_count:<10} {desc}")

        return 0

    def _workflow_status(self, skill) -> int:
        """查看工作流状态"""
        name = self.args.name

        if name not in skill._workflows:
            self.output.error(f"工作流不存在: {name}")
            return 1

        workflow = skill._workflows[name]

        self.output.print(f"\n{'='*60}")
        self.output.print(f"工作流: {name}")
        self.output.print(f"{'='*60}")

        if workflow.description:
            self.output.print(f"描述: {workflow.description}")

        self.output.print(f"\n任务列表:")
        self.output.print(f"{'任务名称':<20} {'类型':<10} {'依赖'}")
        self.output.print("-" * 60)

        for task_id, task in workflow.tasks.items():
            task_type = task.task_type.value
            deps = ', '.join(task.depends_on) if task.depends_on else '-'
            self.output.print(f"{task_id:<20} {task_type:<10} {deps}")

        # 显示执行顺序
        try:
            execution_order = workflow.get_execution_order()
            self.output.print(f"\n执行顺序: {' -> '.join(execution_order)}")
        except ValueError as e:
            self.output.error(f"\n依赖错误: {e}")

        return 0

    def _format_bytes(self, size: int) -> str:
        """格式化字节大小 - 委托给shared.utils.format_bytes"""
        return format_bytes(size)
