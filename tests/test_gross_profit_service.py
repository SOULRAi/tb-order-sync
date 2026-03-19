"""Tests for GrossProfitService (unit tests with mock connector)."""

import pytest
from unittest.mock import MagicMock, patch

from config.mappings import ColumnMapping
from config.settings import Settings, SyncMode
from connectors.base import BaseSheetConnector, CellUpdate
from models.state_models import SyncState
from services.gross_profit_service import GrossProfitService
from services.state_service import StateService


def _make_settings(**overrides) -> Settings:
    defaults = dict(
        tencent_a_file_id="test_file",
        tencent_a_sheet_id="test_sheet",
        tencent_b_file_id="test_b_file",
        tencent_b_sheet_id="test_b_sheet",
        gross_profit_mode=SyncMode.FULL,
        dry_run=False,
        write_batch_size=100,
        data_error_text="数据异常",
    )
    defaults.update(overrides)
    return Settings(**defaults)


def _make_mapping() -> ColumnMapping:
    return ColumnMapping(
        a_product_price=2,   # C
        a_packaging_price=3, # D
        a_freight=4,         # E
        a_customer_quote=5,  # F
        a_gross_profit=6,    # G
        a_order_no=7,        # H
        a_refund_status=8,   # I
        b_order_no=0,        # A
    )


def _make_service(rows: list[list], **settings_overrides):
    """Create a GrossProfitService with a mock connector returning given rows."""
    connector = MagicMock(spec=BaseSheetConnector)
    # prepend header row
    header = ["产品图", "订单地址", "产品价格", "包装价格", "运费", "客户报价", "毛利", "单号", "退款状态"]
    connector.read_rows.return_value = [header] + rows
    connector.batch_update = MagicMock()

    state_svc = MagicMock(spec=StateService)
    state_svc.load.return_value = SyncState()

    svc = GrossProfitService(
        connector=connector,
        state_service=state_svc,
        settings=_make_settings(**settings_overrides),
        mapping=_make_mapping(),
    )
    return svc, connector, state_svc


class TestGrossProfitCalculation:
    def test_normal_calculation(self):
        """G = F - E - D - C = 1000 - 50 - 20 - 200 = 730"""
        rows = [
            ["img", "addr", "200", "20", "50", "1000", "", "SF001", ""],
        ]
        svc, conn, _ = _make_service(rows)
        result = svc.run(mode=SyncMode.FULL)

        assert result.success
        assert result.rows_read == 1
        assert result.rows_changed == 1
        assert result.rows_error == 0

        # Verify write
        conn.batch_update.assert_called_once()
        updates = conn.batch_update.call_args[0][2]
        assert len(updates) == 1
        assert updates[0].value == 730.0

    def test_data_error_non_numeric(self):
        """If any field is non-numeric, write 数据异常."""
        rows = [
            ["img", "addr", "没报价", "20", "50", "1000", "", "SF002", ""],
        ]
        svc, conn, _ = _make_service(rows)
        result = svc.run(mode=SyncMode.FULL)

        assert result.rows_error == 1
        updates = conn.batch_update.call_args[0][2]
        assert updates[0].value == "数据异常"

    def test_data_error_empty(self):
        rows = [
            ["img", "addr", "", "20", "50", "1000", "", "SF003", ""],
        ]
        svc, conn, _ = _make_service(rows)
        result = svc.run(mode=SyncMode.FULL)
        assert result.rows_error == 1

    def test_cde_all_blank_keeps_g_empty(self):
        rows = [
            ["img", "addr", "", "", "", "", "", "SF003A", ""],
        ]
        svc, conn, _ = _make_service(rows)
        result = svc.run(mode=SyncMode.FULL)

        assert result.rows_error == 0
        assert result.rows_changed == 0
        conn.batch_update.assert_not_called()

    def test_cde_all_blank_clears_existing_g(self):
        rows = [
            ["img", "addr", "", "", "", "", "数据异常", "SF003B", ""],
        ]
        svc, conn, _ = _make_service(rows)
        result = svc.run(mode=SyncMode.FULL)

        assert result.rows_error == 0
        assert result.rows_changed == 1
        updates = conn.batch_update.call_args[0][2]
        assert updates[0].value == ""

    def test_string_numbers(self):
        """String numbers should be parsed correctly."""
        rows = [
            ["img", "addr", " 200 ", "20.0", "50", "1000", "", "SF004", ""],
        ]
        svc, conn, _ = _make_service(rows)
        result = svc.run(mode=SyncMode.FULL)
        assert result.rows_error == 0
        updates = conn.batch_update.call_args[0][2]
        assert updates[0].value == 730.0

    def test_writes_correct_row_and_column(self):
        rows = [
            ["img", "addr", "200", "20", "50", "1000", "", "SF004A", ""],
        ]
        svc, conn, _ = _make_service(rows)
        svc.run(mode=SyncMode.FULL)

        updates = conn.batch_update.call_args[0][2]
        assert updates[0].row == 1
        assert updates[0].col == 6
        assert updates[0].value == 730.0

    def test_no_change_skips_write(self):
        """If computed value matches existing G, no update should be emitted."""
        rows = [
            ["img", "addr", "200", "20", "50", "1000", "730.0", "SF005", ""],
        ]
        svc, conn, _ = _make_service(rows)
        result = svc.run(mode=SyncMode.FULL)
        # 730.0 (float) vs "730.0" (str) — the comparison is str-based
        # round(730.0, 2) = 730.0, str(730.0) = "730.0" == "730.0" ✓
        assert result.rows_changed == 0

    def test_dry_run_no_write(self):
        rows = [
            ["img", "addr", "200", "20", "50", "1000", "", "SF006", ""],
        ]
        svc, conn, _ = _make_service(rows, dry_run=True)
        result = svc.run()
        assert result.dry_run
        conn.batch_update.assert_not_called()

    def test_multiple_rows(self):
        rows = [
            ["img", "addr", "100", "10", "30", "500", "", "SF007", ""],
            ["img", "addr", "abc", "10", "30", "500", "", "SF008", ""],
            ["img", "addr", "200", "20", "50", "1000", "", "SF009", ""],
        ]
        svc, conn, _ = _make_service(rows)
        result = svc.run(mode=SyncMode.FULL)
        assert result.rows_read == 3
        assert result.rows_changed == 3  # 2 normal + 1 error
        assert result.rows_error == 1

    def test_zero_values(self):
        """G = 500 - 0 - 0 - 0 = 500"""
        rows = [
            ["img", "addr", "0", "0", "0", "500", "", "SF010", ""],
        ]
        svc, conn, _ = _make_service(rows)
        result = svc.run(mode=SyncMode.FULL)
        updates = conn.batch_update.call_args[0][2]
        assert updates[0].value == 500.0


class TestGrossProfitIncremental:
    def test_incremental_skips_unchanged(self):
        rows = [
            ["img", "addr", "200", "20", "50", "1000", "", "SF011", ""],
        ]
        svc, conn, state_svc = _make_service(rows)

        # Pre-populate state with matching fingerprint
        from utils.diff import row_fingerprint
        fp = row_fingerprint(["200", "20", "50", "1000", "SF011"])
        state = SyncState(a_table_fingerprints={"1": fp})
        state_svc.load.return_value = state

        result = svc.run(mode=SyncMode.INCREMENTAL)
        assert result.rows_changed == 0
