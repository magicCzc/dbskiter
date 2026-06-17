"""
命令历史管理模块

文件功能：
    - 持久化记录用户执行的 CLI 命令
    - 支持历史列表、搜索、快速复用
    - 使用 JSONL 格式存储，便于追加和读取

主要类：
    - HistoryManager: 历史管理器

存储位置：
    - ~/.config/dbskiter/history.jsonl

版本: 1.0.0
作者: dbskiter team
创建时间: 2026-06-16
最后修改: 2026-06-16
"""

import json
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict


@dataclass
class HistoryEntry:
    """
    单条历史记录

    属性:
        timestamp: 执行时间（ISO 格式）
        command: 主命令（如 diagnose, monitor）
        action: 子命令（如 realtime, health）
        database: 数据库别名或连接串
        args: 参数字典（已脱敏）
        status_code: 退出码（0=成功）
        execution_time_ms: 执行耗时（毫秒）
    """
    timestamp: str
    command: str
    action: str
    database: str
    args: Dict[str, Any]
    status_code: int
    execution_time_ms: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        """
        转换为字典

        返回:
            Dict[str, Any]: 字典表示
        """
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "HistoryEntry":
        """
        从字典创建

        参数:
            data: 字典数据

        返回:
            HistoryEntry: 历史记录实例
        """
        return cls(**data)

    def to_cli_string(self) -> str:
        """
        转换为可复用的 CLI 命令字符串

        返回:
            str: 如 "dbskiter --database=prod diagnose realtime"
        """
        parts = ["dbskiter"]
        if self.database:
            parts.append(f"--database={self.database}")
        for key, value in self.args.items():
            if key in ("command", "action", "database", "func"):
                continue
            if value is True:
                parts.append(f"--{key.replace('_', '-')}")
            elif value is False or value is None:
                continue
            else:
                parts.append(f"--{key.replace('_', '-')}={value}")
        parts.append(self.command)
        if self.action and self.action != self.command:
            parts.append(self.action)
        return " ".join(parts)


class HistoryManager:
    """
    命令历史管理器

    负责记录、查询和复用 CLI 命令历史。

    属性:
        history_file: Path - 历史文件路径
        max_entries: int - 最大保留条数

    使用示例:
        >>> hm = HistoryManager()
        >>> hm.record(args, "diagnose", "realtime", "prod", 0, 1250.5)
        >>> entries = hm.list(limit=5)
        >>> print(entries[0].to_cli_string())
    """

    DEFAULT_MAX_ENTRIES = 1000

    def __init__(
        self,
        history_file: Optional[Path] = None,
        max_entries: int = DEFAULT_MAX_ENTRIES,
    ):
        """
        初始化历史管理器

        参数:
            history_file: 历史文件路径（默认 ~/.config/dbskiter/history.jsonl）
            max_entries: 最大保留条数
        """
        if history_file is None:
            config_dir = Path.home() / ".config" / "dbskiter"
            config_dir.mkdir(parents=True, exist_ok=True)
            history_file = config_dir / "history.jsonl"

        self.history_file = Path(history_file)
        self.max_entries = max_entries

    def _sanitize_args(self, args: Any) -> Dict[str, Any]:
        """
        脱敏处理参数，移除敏感信息

        参数:
            args: argparse.Namespace 或 dict

        返回:
            Dict[str, Any]: 脱敏后的参数字典
        """
        sensitive_keys = {"password", "secret", "token", "key", "api_key", "private_key"}
        result = {}

        if hasattr(args, "__dict__"):
            raw = vars(args)
        elif isinstance(args, dict):
            raw = args
        else:
            raw = {}

        for key, value in raw.items():
            if any(sk in key.lower() for sk in sensitive_keys):
                result[key] = "***"
            else:
                result[key] = value
        return result

    def record(
        self,
        args: Any,
        command: str,
        action: str,
        database: str,
        status_code: int,
        execution_time_ms: Optional[float] = None,
    ) -> None:
        """
        记录一条命令历史

        参数:
            args: 命令参数
            command: 主命令
            action: 子命令
            database: 数据库标识
            status_code: 退出码
            execution_time_ms: 执行耗时（毫秒）
        """
        entry = HistoryEntry(
            timestamp=datetime.now().isoformat(),
            command=command,
            action=action,
            database=database or "",
            args=self._sanitize_args(args),
            status_code=status_code,
            execution_time_ms=execution_time_ms,
        )

        try:
            with open(self.history_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry.to_dict(), ensure_ascii=False) + "\n")
        except OSError as e:
            # 历史记录写入失败不应阻断主流程
            pass

        # 如果超出最大条数，裁剪旧记录
        self._trim_if_needed()

    def _trim_if_needed(self) -> None:
        """
        当历史记录超出上限时，裁剪旧记录
        """
        try:
            if not self.history_file.exists():
                return

            lines = []
            with open(self.history_file, "r", encoding="utf-8") as f:
                lines = f.readlines()

            if len(lines) > self.max_entries:
                # 保留最新的 max_entries 条
                keep_lines = lines[-self.max_entries:]
                with open(self.history_file, "w", encoding="utf-8") as f:
                    f.writelines(keep_lines)
        except OSError:
            pass

    def list(
        self,
        limit: int = 20,
        database: Optional[str] = None,
        command: Optional[str] = None,
    ) -> List[HistoryEntry]:
        """
        列出历史记录

        参数:
            limit: 最多返回条数
            database: 按数据库过滤
            command: 按主命令过滤

        返回:
            List[HistoryEntry]: 历史记录列表（按时间倒序）
        """
        if not self.history_file.exists():
            return []

        entries = []
        try:
            with open(self.history_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        entry = HistoryEntry.from_dict(data)
                        if database and entry.database != database:
                            continue
                        if command and entry.command != command:
                            continue
                        entries.append(entry)
                    except (json.JSONDecodeError, TypeError):
                        continue
        except OSError:
            return []

        # 倒序返回，最新的在前面
        entries.reverse()
        return entries[:limit]

    def search(self, keyword: str, limit: int = 20) -> List[HistoryEntry]:
        """
        搜索历史记录

        参数:
            keyword: 搜索关键词
            limit: 最多返回条数

        返回:
            List[HistoryEntry]: 匹配的历史记录
        """
        if not self.history_file.exists():
            return []

        keyword_lower = keyword.lower()
        entries = []
        try:
            with open(self.history_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        entry = HistoryEntry.from_dict(data)
                        # 在 command / action / database / CLI 字符串中搜索
                        haystack = (
                            f"{entry.command} {entry.action} "
                            f"{entry.database} {entry.to_cli_string()}"
                        ).lower()
                        if keyword_lower in haystack:
                            entries.append(entry)
                    except (json.JSONDecodeError, TypeError):
                        continue
        except OSError:
            return []

        entries.reverse()
        return entries[:limit]

    def get(self, index: int) -> Optional[HistoryEntry]:
        """
        按索引获取历史记录（1-based，最新=1）

        参数:
            index: 索引（从1开始，1表示最新的一条）

        返回:
            Optional[HistoryEntry]: 历史记录，不存在则返回 None
        """
        entries = self.list(limit=index)
        if 1 <= index <= len(entries):
            return entries[index - 1]
        return None

    def clear(self) -> bool:
        """
        清空历史记录

        返回:
            bool: 是否成功
        """
        try:
            if self.history_file.exists():
                self.history_file.unlink()
            return True
        except OSError:
            return False
