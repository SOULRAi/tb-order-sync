"""Gross profit calculation service.

Business rule:
    毛利 = 客户报价 - 运费 - 包装价格 - 产品价格
    G = F - E - D - C

If any of C/D/E/F is not a valid number, write "数据异常" to G.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from config.mappings import ColumnMapping, get_column_mapping
from config.settings import Settings, SyncMode, get_settings
from connectors.base import BaseSheetConnector, CellUpdate
from models.records import OrderRecord
from models.state_models import SyncState
from models.task_models import TaskName, TaskResult
from services.state_service import StateService
from utils.diff import row_fingerprint
from utils.logger import get_logger
from utils.parser import normalize_order_no, parse_number

logger = get_logger(__name__)


class GrossProfitService:
    """Calculate and write gross profit for every row in A table."""

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
        """Execute gross profit calculation."""
        mode = mode or self._settings.gross_profit_mode
        dry_run = dry_run if dry_run is not None else self._settings.dry_run
        result = TaskResult(task_name=TaskName.GROSS_PROFIT, mode=mode, dry_run=dry_run)

        logger.info("=== Gross Profit Service START (mode=%s, dry_run=%s) ===", mode.value, dry_run)

        try:
            state = self._state_svc.load()
            rows = self._read_a_table()
            result.rows_read = len(rows)
            if not rows:
                logger.warning("A table returned 0 data rows")
                result.finish()
                return result

            records = self._parse_rows(rows)
            updates, changed, errors = self._compute(records, state, mode)

            result.rows_changed = changed
            result.rows_error = errors

            if updates and not dry_run:
                self._write_updates(updates)
                state.last_run_at = datetime.now()
                self._state_svc.save(state)

            if dry_run:
                logger.info("[DRY-RUN] Would write %d cells, %d changed, %d errors", len(updates), changed, errors)

            result.finish()
            logger.info(
                "=== Gross Profit Service END — read=%d changed=%d errors=%d ===",
                result.rows_read, result.rows_changed, result.rows_error,
            )
        except Exception as exc:
            logger.exception("Gross Profit Service failed")
            result.finish(success=False, error_message=str(exc))

        return result

    # ── Internal ───────────────────────────────────────────────────────────

    def _read_a_table(self) -> list[list[Any]]:
        rows = self._conn.read_rows(
            self._settings.tencent_a_file_id,
            self._settings.tencent_a_sheet_id,
        )
        # Skip header (row 0)
        return rows[1:] if rows else []

    def _parse_rows(self, rows: list[list[Any]]) -> list[OrderRecord]:
        m = self._map
        records: list[OrderRecord] = []
        for idx, row in enumerate(rows):
            row_num = idx + 1  # 1-based data row (0 is header)
            records.append(OrderRecord(
                row_index=row_num,
                order_no=normalize_order_no(self._safe_get(row, m.a_order_no)),
                product_price=self._safe_get_str(row, m.a_product_price),
                packaging_price=self._safe_get_str(row, m.a_packaging_price),
                freight=self._safe_get_str(row, m.a_freight),
                customer_quote=self._safe_get_str(row, m.a_customer_quote),
                gross_profit=self._safe_get_str(row, m.a_gross_profit),
                refund_status=self._safe_get_str(row, m.a_refund_status),
                raw_data=row,
            ))
        return records

    def _compute(
        self,
        records: list[OrderRecord],
        state: SyncState,
        mode: SyncMode,
    ) -> tuple[list[CellUpdate], int, int]:
        """Compute gross profit for each record, return (updates, changed_count, error_count)."""
        m = self._map
        updates: list[CellUpdate] = []
        changed = 0
        errors = 0

        for rec in records:
            # Fingerprint for incremental check: C, D, E, F, H
            fp = row_fingerprint([
                rec.product_price, rec.packaging_price,
                rec.freight, rec.customer_quote, rec.order_no,
            ])

            if mode == SyncMode.INCREMENTAL:
                old_fp = state.a_table_fingerprints.get(str(rec.row_index), "")
                if old_fp == fp:
                    continue  # No change

            # Parse numbers
            c = parse_number(rec.product_price)
            d = parse_number(rec.packaging_price)
            e = parse_number(rec.freight)
            f = parse_number(rec.customer_quote)

            if self._all_cost_fields_blank(rec):
                # Treat rows with empty C/D/E as unused rows and keep G blank.
                new_val = ""
            elif any(v is None for v in (c, d, e, f)):
                # Data error
                new_val = self._settings.data_error_text
                errors += 1
                self._log_data_error(rec, c, d, e, f)
            else:
                gross = f - e - d - c  # type: ignore[operator]
                new_val = round(gross, 2)

            # Check if value actually changed
            if str(new_val) != str(rec.gross_profit or ""):
                updates.append(CellUpdate(row=rec.row_index, col=m.a_gross_profit, value=new_val))
                changed += 1

            # Update fingerprint
            state.a_table_fingerprints[str(rec.row_index)] = fp

        return updates, changed, errors

    def _write_updates(self, updates: list[CellUpdate]) -> None:
        self._conn.batch_update(
            self._settings.tencent_a_file_id,
            self._settings.tencent_a_sheet_id,
            updates,
            batch_size=self._settings.write_batch_size,
        )

    def _log_data_error(
        self, rec: OrderRecord,
        c: Optional[float], d: Optional[float],
        e: Optional[float], f: Optional[float],
    ) -> None:
        bad_fields = []
        labels = [
            ("产品价格(C)", rec.product_price, c),
            ("包装价格(D)", rec.packaging_price, d),
            ("运费(E)", rec.freight, e),
            ("客户报价(F)", rec.customer_quote, f),
        ]
        for name, raw, parsed in labels:
            if parsed is None:
                bad_fields.append(f"{name}='{raw}'")
        logger.warning(
            "Row %d (单号=%s) 数据异常: %s",
            rec.row_index, rec.order_no, ", ".join(bad_fields),
        )

    @staticmethod
    def _safe_get(row: list[Any], idx: int) -> Any:
        return row[idx] if idx < len(row) else None

    @staticmethod
    def _safe_get_str(row: list[Any], idx: int) -> Optional[str]:
        val = row[idx] if idx < len(row) else None
        return str(val) if val is not None else None

    @staticmethod
    def _is_blank(value: Optional[str]) -> bool:
        return value is None or value.strip() == ""

    def _all_cost_fields_blank(self, rec: OrderRecord) -> bool:
        return (
            self._is_blank(rec.product_price)
            and self._is_blank(rec.packaging_price)
            and self._is_blank(rec.freight)
        )
