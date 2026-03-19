"""Task execution models."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

from config.settings import SyncMode


class TaskName(str, Enum):
    GROSS_PROFIT = "gross_profit"
    REFUND_MATCH = "refund_match"
    C_TO_A_SYNC = "c_to_a_sync"


class SyncTaskConfig(BaseModel):
    """Configuration for a single sync task execution."""

    task_name: TaskName
    mode: SyncMode = SyncMode.INCREMENTAL
    dry_run: bool = False
    batch_size: int = 100


class TaskResult(BaseModel):
    """Result summary after a task execution."""

    task_name: TaskName
    success: bool = True
    mode: SyncMode = SyncMode.FULL
    rows_read: int = 0
    rows_changed: int = 0
    rows_error: int = 0
    dry_run: bool = False
    started_at: datetime = Field(default_factory=datetime.now)
    finished_at: Optional[datetime] = None
    error_message: Optional[str] = None

    def finish(self, success: bool = True, error_message: Optional[str] = None) -> None:
        self.finished_at = datetime.now()
        self.success = success
        if error_message:
            self.error_message = error_message


class RunSummary(BaseModel):
    """Summary of one manual or scheduled execution round."""

    trigger: str = "manual"
    success: bool = True
    started_at: datetime = Field(default_factory=datetime.now)
    finished_at: Optional[datetime] = None
    task_count: int = 0
    rows_read: int = 0
    rows_changed: int = 0
    rows_error: int = 0
    tasks: list[TaskResult] = Field(default_factory=list)
    message: Optional[str] = None
