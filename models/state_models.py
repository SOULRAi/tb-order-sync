"""Incremental sync state models."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class RowFingerprint(BaseModel):
    """Fingerprint for a single row, used for change detection."""

    row_index: int
    order_no: str = ""
    fingerprint: str = ""  # MD5 hex of key fields


class SyncState(BaseModel):
    """Persisted state for incremental sync."""

    last_run_at: Optional[datetime] = None

    # A 表毛利任务: row_index -> fingerprint
    a_table_fingerprints: dict[str, str] = Field(default_factory=dict)

    # A 表退款任务: 整体扫描 hash（基于单号 + 当前退款状态）
    a_table_refund_scan_hash: str = ""

    # B 表: 退款单号集合 hash
    b_table_refund_hash: str = ""

    # B 表: 退款单号快照
    b_table_refund_set: list[str] = Field(default_factory=list)

    # C 表（预留）
    c_table_fingerprints: dict[str, str] = Field(default_factory=dict)
    c_table_last_run_at: Optional[datetime] = None
