# =============================================================================
# 数据类
# =============================================================================

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class BackupInfo:
    """
    备份信息

    属性:
        backup_id: 备份标识
        backup_type: 备份类型 (full/table/incremental)
        file_path: 备份文件绝对路径
        file_size: 文件大小(字节)
        created_at: 创建时间
        tables: 包含的表列表
        checksum: SHA256校验值
        status: 状态 (ok/corrupted/unknown)
    """

    backup_id: str
    backup_type: str
    file_path: str
    file_size: int
    created_at: datetime
    tables: List[str]
    checksum: Optional[str]
    status: str


@dataclass
class BackupResult:
    """
    备份/恢复操作结果

    属性:
        success: 是否成功
        backup_id: 备份标识
        file_path: 文件路径
        file_size: 文件大小(字节)
        duration_ms: 耗时(毫秒)
        tables: 涉及的表列表
        backup_type: 备份类型
        error: 错误信息(失败时)
    """

    success: bool
    backup_id: str
    file_path: str
    file_size: int
    duration_ms: int
    tables: List[str] = None
    backup_type: str = "full"
    error: Optional[str] = None

    def __post_init__(self):
        if self.tables is None:
            self.tables = []

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "backup_id": self.backup_id,
            "file_path": self.file_path,
            "file_size": self.file_size,
            "duration_ms": self.duration_ms,
            "tables": self.tables,
            "backup_type": self.backup_type,
            "error": self.error,
        }

