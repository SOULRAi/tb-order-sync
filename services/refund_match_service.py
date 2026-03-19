"""Refund matching service.

Business rules:
  - Read B table column A (order numbers) to build refund set
  - Scan A table column H (order numbers)
  - If A row's order_no is in refund set → write "已退款" to A table I column
  - If not in refund set → clear I column
  - Optional: set/clear row-level highlight style
"""

from __future__ import annotations

from datetime import datetime
import time
from typing import Any, Optional

from config.mappings import ColumnMapping, get_column_mapping
from config.settings import Settings, SyncMode, get_settings
from connectors.base import BaseSheetConnector, CellUpdate
from models.state_models import SyncState
from models.task_models import TaskName, TaskResult
from services.state_service import StateService
from utils.diff import row_fingerprint, set_hash
from utils.logger import get_logger
from utils.parser import normalize_order_no

logger = get_logger(__name__)

# Text highlight colors for optional style update
_BG_RED = "#FF4D4F"
_BG_DEFAULT = None  # None means reset / no color


class RefundMatchService:
    """Match refund orders from B table against A table and update refund status."""

    def __init__(
        self,
        connector: BaseSheetConnector,
        state_service: StateService,
        settings: Optional[Settings] = None,
        mapping: Optional[ColumnMapping] = None,
    ) -> None:
        self._conn = connector
        self._state_svc = state_service
        self._settings = settings or get_settings()
        self._map = mapping or get_column_mapping()

    def run(
        self,
        mode: Optional[SyncMode] = None,
        dry_run: Optional[bool] = None,
    ) -> TaskResult:
        mode = mode or self._settings.refund_match_mode
        dry_run = dry_run if dry_run is not None else self._settings.dry_run
        result = TaskResult(task_name=TaskName.REFUND_MATCH, mode=mode, dry_run=dry_run)

        logger.info("=== Refund Match Service START (mode=%s, dry_run=%s) ===", mode.value, dry_run)

        try:
            state = self._state_svc.load()

            # 1. Build refund set from B table
            refund_set = self._build_refund_set()
            new_refund_hash = set_hash(list(refund_set))
            logger.info("B table refund set: %d order numbers, hash=%s", len(refund_set), new_refund_hash[:8])

            # 2. Read A table
            a_rows = self._read_a_table()
            result.rows_read = len(a_rows)
            a_scan_hash = self._build_a_scan_hash(a_rows)

            # 3. Incremental short-circuit: only skip when both B refunds and A scan are unchanged
            if (
                mode == SyncMode.INCREMENTAL
                and new_refund_hash == state.b_table_refund_hash
                and a_scan_hash == state.a_table_refund_scan_hash
            ):
                logger.info("Refund set unchanged, skipping (incremental mode)")
                result.finish()
                return result

            # 4. Match and compute updates
            updates, style_ops, changed = self._match(a_rows, refund_set, state, mode)
            result.rows_changed = changed

            # 5. Write
            if not dry_run:
                if updates:
                    self._conn.batch_update(
                        self._settings.tencent_a_file_id,
                        self._settings.tencent_a_sheet_id,
                        updates,
                        batch_size=self._settings.write_batch_size,
                    )
                if self._settings.enable_style_update and style_ops:
                    self._apply_styles(style_ops)

                state.b_table_refund_hash = new_refund_hash
                state.b_table_refund_set = sorted(refund_set)
                state.a_table_refund_scan_hash = self._build_desired_scan_hash(a_rows, refund_set)
                state.last_run_at = datetime.now()
                self._state_svc.save(state)
            else:
                logger.info("[DRY-RUN] Would write %d cells, %d style ops, %d changed", len(updates), len(style_ops), changed)

            result.finish()
            logger.info(
                "=== Refund Match Service END — read=%d changed=%d ===",
                result.rows_read, result.rows_changed,
            )
        except Exception as exc:
            logger.exception("Refund Match Service failed")
            result.finish(success=False, error_message=str(exc))

        return result

    # ── Internal ───────────────────────────────────────────────────────────

    def _build_refund_set(self) -> set[str]:
        rows = self._conn.read_rows(
            self._settings.tencent_b_file_id,
            self._settings.tencent_b_sheet_id,
        )
        # Skip header
        data_rows = rows[1:] if rows else []
        refund_set: set[str] = set()
        col = self._map.b_order_no
        for row in data_rows:
            val = row[col] if col < len(row) else None
            order_no = normalize_order_no(val)
            if order_no:
                refund_set.add(order_no)
        return refund_set

    def _read_a_table(self) -> list[list[Any]]:
        rows = self._conn.read_rows(
            self._settings.tencent_a_file_id,
            self._settings.tencent_a_sheet_id,
        )
        return rows[1:] if rows else []

    def _build_a_scan_hash(self, a_rows: list[list[Any]]) -> str:
        m = self._map
        row_hashes = []
        for idx, row in enumerate(a_rows):
            order_no = normalize_order_no(row[m.a_order_no] if m.a_order_no < len(row) else None)
            current_status = (
                str(row[m.a_refund_status]).strip()
                if m.a_refund_status < len(row) and row[m.a_refund_status] is not None
                else ""
            )
            row_hashes.append(row_fingerprint([idx, order_no, current_status]))
        return row_fingerprint(row_hashes)

    def _build_desired_scan_hash(self, a_rows: list[list[Any]], refund_set: set[str]) -> str:
        m = self._map
        refund_text = self._settings.refund_status_text
        row_hashes = []
        for idx, row in enumerate(a_rows):
            order_no = normalize_order_no(row[m.a_order_no] if m.a_order_no < len(row) else None)
            desired = refund_text if order_no and order_no in refund_set else ""
            row_hashes.append(row_fingerprint([idx, order_no, desired]))
        return row_fingerprint(row_hashes)

    def _match(
        self,
        a_rows: list[list[Any]],
        refund_set: set[str],
        state: SyncState,
        mode: SyncMode,
    ) -> tuple[list[CellUpdate], list[tuple[int, Optional[str]]], int]:
        """Compare each A-table row's order_no against refund_set.

        Returns: (cell_updates, style_operations, changed_count)
        """
        m = self._map
        updates: list[CellUpdate] = []
        style_ops: list[tuple[int, Optional[str]]] = []
        changed = 0
        refund_text = self._settings.refund_status_text

        for idx, row in enumerate(a_rows):
            row_num = idx + 1  # 1-based (0 is header)
            current_status = str(row[m.a_refund_status]).strip() if m.a_refund_status < len(row) and row[m.a_refund_status] is not None else ""
            order_no = normalize_order_no(row[m.a_order_no] if m.a_order_no < len(row) else None)

            if not order_no:
                if current_status:
                    updates.append(CellUpdate(row=row_num, col=m.a_refund_status, value=""))
                    style_ops.append((row_num, _BG_DEFAULT))
                    changed += 1
                    logger.info("Row %d: 单号为空，清除退款标记", row_num)
                continue

            is_refund = order_no in refund_set

            if is_refund:
                desired = refund_text
                desired_color = _BG_RED
            else:
                desired = ""
                desired_color = _BG_DEFAULT

            if current_status == desired:
                continue  # No change needed

            # Incremental: if mode is incremental, still process because refund set changed
            # (we already short-circuited above if hash unchanged)

            updates.append(CellUpdate(row=row_num, col=m.a_refund_status, value=desired))
            style_ops.append((row_num, desired_color))
            changed += 1

            if is_refund:
                logger.info("Row %d (单号=%s): 标记退款", row_num, order_no)
            else:
                logger.info("Row %d (单号=%s): 取消退款标记", row_num, order_no)

        return updates, style_ops, changed

    def _apply_styles(self, ops: list[tuple[int, Optional[str]]]) -> None:
        failures: list[str] = []
        total = len(ops)
        for index, (row_idx, color) in enumerate(ops):
            try:
                self._conn.update_row_style(
                    self._settings.tencent_a_file_id,
                    self._settings.tencent_a_sheet_id,
                    row_idx,
                    bg_color=color,
                )
                if index + 1 < total:
                    time.sleep(0.2)
            except Exception as exc:
                failures.append(f"row={row_idx} error={exc}")

        if failures:
            raise RuntimeError("Style update failed: " + "; ".join(failures))
