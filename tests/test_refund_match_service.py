"""Tests for RefundMatchService (unit tests with mock connector)."""

import pytest
from unittest.mock import MagicMock, call

from config.mappings import ColumnMapping
from config.settings import Settings, SyncMode
from connectors.base import BaseSheetConnector
from models.state_models import SyncState
from services.refund_match_service import RefundMatchService
from services.state_service import StateService
from utils.diff import set_hash
from utils.sheet_selector import SheetInfo


def _make_mapping() -> ColumnMapping:
    return ColumnMapping(
        a_product_price=2, a_packaging_price=3, a_freight=4,
        a_customer_quote=5, a_gross_profit=6, a_order_no=7,
        a_refund_status=8, b_order_no=0,
    )


def _make_settings(**overrides) -> Settings:
    defaults = dict(
        tencent_a_file_id="a_file", tencent_a_sheet_id="a_sheet",
        tencent_b_file_id="b_file", tencent_b_sheet_id="b_sheet",
        refund_match_mode=SyncMode.FULL, dry_run=False,
        write_batch_size=100, enable_style_update=False,
        refund_status_text="已退款",
    )
    defaults.update(overrides)
    return Settings(**defaults)


def _make_service(a_rows: list[list], b_rows: list[list], **overrides):
    connector = MagicMock(spec=BaseSheetConnector)
    a_header = ["产品图", "订单地址", "产品价格", "包装价格", "运费", "客户报价", "毛利", "单号", "退款状态"]
    b_header = ["单号", "退货单号", "店铺", "客户微信", "产品", "原因", "金额", "退款状态", "付款记录", "退款凭证", "备注", "二维码图片"]

    def read_side_effect(file_id, sheet_id, **kwargs):
        if file_id == "b_file":
            return [b_header] + b_rows
        return [a_header] + a_rows

    connector.read_rows.side_effect = read_side_effect
    connector.batch_update = MagicMock()
    connector.update_row_style = MagicMock()
    connector.list_sheets = MagicMock(return_value=[])

    state_svc = MagicMock(spec=StateService)
    state_svc.load.return_value = SyncState()

    svc = RefundMatchService(
        connector=connector, state_service=state_svc,
        settings=_make_settings(**overrides), mapping=_make_mapping(),
    )
    return svc, connector, state_svc


class TestRefundMatch:
    def test_marks_matching_orders(self):
        a_rows = [
            ["img", "addr", "200", "20", "50", "1000", "730", "SF001", ""],
            ["img", "addr", "200", "20", "50", "1000", "730", "SF002", ""],
        ]
        b_rows = [
            ["SF001", "RT001", "店铺A", "wx1", "产品A", "损坏", "100", "已退", "", "", "", ""],
        ]
        svc, conn, _ = _make_service(a_rows, b_rows)
        result = svc.run()

        assert result.success
        assert result.rows_changed == 1
        updates = conn.batch_update.call_args[0][2]
        assert updates[0].value == "已退款"
        assert updates[0].row == 1  # SF001 is row 1

    def test_clears_old_refund_status(self):
        a_rows = [
            ["img", "addr", "200", "20", "50", "1000", "730", "SF001", "已退款"],
        ]
        b_rows = []  # No refunds anymore
        svc, conn, _ = _make_service(a_rows, b_rows)
        result = svc.run()

        assert result.rows_changed == 1
        updates = conn.batch_update.call_args[0][2]
        assert updates[0].value == ""  # Cleared

    def test_no_change_needed(self):
        a_rows = [
            ["img", "addr", "200", "20", "50", "1000", "730", "SF001", "已退款"],
        ]
        b_rows = [
            ["SF001", "RT001", "店铺A", "wx1", "产品A", "损坏", "100", "已退", "", "", "", ""],
        ]
        svc, conn, _ = _make_service(a_rows, b_rows)
        result = svc.run()
        assert result.rows_changed == 0

    def test_dry_run(self):
        a_rows = [
            ["img", "addr", "200", "20", "50", "1000", "730", "SF001", ""],
        ]
        b_rows = [["SF001", "", "", "", "", "", "", "", "", "", "", ""]]
        svc, conn, _ = _make_service(a_rows, b_rows, dry_run=True)
        result = svc.run()
        assert result.dry_run
        conn.batch_update.assert_not_called()

    def test_trims_order_no(self):
        a_rows = [
            ["img", "addr", "200", "20", "50", "1000", "730", "  SF001  ", ""],
        ]
        b_rows = [["SF001", "", "", "", "", "", "", "", "", "", "", ""]]
        svc, conn, _ = _make_service(a_rows, b_rows)
        result = svc.run()
        assert result.rows_changed == 1

    def test_multiple_refunds(self):
        a_rows = [
            ["img", "addr", "200", "20", "50", "1000", "730", "SF001", ""],
            ["img", "addr", "200", "20", "50", "1000", "730", "SF002", ""],
            ["img", "addr", "200", "20", "50", "1000", "730", "SF003", ""],
        ]
        b_rows = [
            ["SF001", "", "", "", "", "", "", "", "", "", "", ""],
            ["SF003", "", "", "", "", "", "", "", "", "", "", ""],
        ]
        svc, conn, _ = _make_service(a_rows, b_rows)
        result = svc.run()
        assert result.rows_changed == 2

    def test_applies_row_style_when_enabled(self):
        a_rows = [
            ["img", "addr", "200", "20", "50", "1000", "730", "SF001", ""],
        ]
        b_rows = [["SF001", "", "", "", "", "", "", "", "", "", "", ""]]
        svc, conn, _ = _make_service(a_rows, b_rows, enable_style_update=True)

        result = svc.run()

        assert result.rows_changed == 1
        conn.update_row_style.assert_called_once_with("a_file", "a_sheet", 1, bg_color="#FF4D4F")

    def test_unmatched_order_is_not_marked(self):
        a_rows = [
            ["img", "addr", "200", "20", "50", "1000", "730", "SF001", ""],
        ]
        b_rows = [["SF999", "", "", "", "", "", "", "", "", "", "", ""]]
        svc, conn, _ = _make_service(a_rows, b_rows)

        result = svc.run()

        assert result.rows_changed == 0
        conn.batch_update.assert_not_called()

    def test_incremental_processes_new_a_rows_when_b_set_is_unchanged(self):
        a_rows = [
            ["img", "addr", "200", "20", "50", "1000", "730", "SF001", ""],
        ]
        b_rows = [["SF001", "", "", "", "", "", "", "", "", "", "", ""]]
        svc, conn, state_svc = _make_service(a_rows, b_rows, refund_match_mode=SyncMode.INCREMENTAL)
        state_svc.load.return_value = SyncState(
            b_table_refund_hash=set_hash(["SF001"]),
            a_table_refund_scan_hash="old-scan-hash",
        )

        result = svc.run(mode=SyncMode.INCREMENTAL)

        assert result.rows_changed == 1
        conn.batch_update.assert_called_once()

    def test_repeat_run_does_not_rewrite_stable_rows(self):
        a_rows = [
            ["img", "addr", "200", "20", "50", "1000", "730", "SF001", "已退款"],
        ]
        b_rows = [["SF001", "", "", "", "", "", "", "", "", "", "", ""]]
        svc, conn, state_svc = _make_service(a_rows, b_rows, refund_match_mode=SyncMode.INCREMENTAL)
        state_svc.load.return_value = SyncState(
            b_table_refund_hash=set_hash(["SF001"]),
            a_table_refund_scan_hash=svc._build_a_scan_hash(a_rows),
        )

        result = svc.run(mode=SyncMode.INCREMENTAL)

        assert result.rows_changed == 0
        conn.batch_update.assert_not_called()

    def test_uses_latest_month_sheets_when_keywords_are_configured(self):
        a_rows = [
            ["img", "addr", "200", "20", "50", "1000", "730", "SF001", ""],
        ]
        b_rows = [["SF001", "", "", "", "", "", "", "", "", "", "", ""]]
        svc, conn, _ = _make_service(
            a_rows,
            b_rows,
            tencent_a_sheet_name_keyword="毛利率",
            tencent_b_sheet_name_keyword="客户退款",
        )
        conn.list_sheets.side_effect = [
            [
                SheetInfo(sheet_id="000001", title="3月毛利率", index=0),
                SheetInfo(sheet_id="000002", title="4月毛利率", index=1),
            ],
            [
                SheetInfo(sheet_id="000011", title="3月客户退款", index=0),
                SheetInfo(sheet_id="000012", title="4月客户退款", index=1),
            ],
        ]

        result = svc.run(mode=SyncMode.FULL)

        assert result.rows_changed == 1
        assert conn.read_rows.call_args_list[0].args[1] == "000012"
        assert conn.read_rows.call_args_list[1].args[1] == "000002"
        assert conn.batch_update.call_args[0][1] == "000002"
