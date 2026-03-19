"""Feishu (飞书) sheet connector — structural skeleton.

This connector implements the BaseSheetConnector interface for Feishu/Lark spreadsheets.
Currently a placeholder — all methods raise NotImplementedError with guidance.

API Reference (TODO / NEED_VERIFY):
  飞书开放平台电子表格: https://open.feishu.cn/document/server-docs/docs/sheets-v3/overview

Implementation priority for Phase 2:
  1. Authentication (app_id + app_secret → tenant_access_token)
  2. read_rows  — GET /open-apis/sheets/v2/spreadsheets/{spreadsheetToken}/values/{range}
  3. write_cells — PUT /open-apis/sheets/v2/spreadsheets/{spreadsheetToken}/values
  4. batch_update — same as write_cells with batch splitting
  5. get_header / ensure_column
  6. update_row_style (if needed)
"""

from __future__ import annotations

from typing import Any, Optional

from connectors.base import BaseSheetConnector, CellUpdate
from utils.logger import get_logger

logger = get_logger(__name__)


class FeishuSheetsConnector(BaseSheetConnector):
    """Connector for 飞书电子表格.

    TODO: Implement when Feishu integration is needed.
    """

    def __init__(
        self,
        app_id: str,
        app_secret: str,
    ) -> None:
        self._app_id = app_id
        self._app_secret = app_secret
        self._tenant_token: Optional[str] = None
        # TODO: Initialize httpx client with base_url = "https://open.feishu.cn"

    def _ensure_token(self) -> None:
        """Obtain or refresh tenant_access_token.

        TODO / NEED_VERIFY:
          POST https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal
          body: { "app_id": ..., "app_secret": ... }
        """
        raise NotImplementedError("Feishu token acquisition not yet implemented")

    def read_rows(
        self,
        file_id: str,
        sheet_id: str,
        *,
        start_row: int = 0,
        end_row: Optional[int] = None,
    ) -> list[list[Any]]:
        """TODO: GET /open-apis/sheets/v2/spreadsheets/{file_id}/values/{sheet_id}!A:ZZ"""
        raise NotImplementedError("FeishuSheetsConnector.read_rows not yet implemented")

    def write_cells(
        self,
        file_id: str,
        sheet_id: str,
        updates: list[CellUpdate],
    ) -> None:
        """TODO: PUT /open-apis/sheets/v2/spreadsheets/{file_id}/values"""
        raise NotImplementedError("FeishuSheetsConnector.write_cells not yet implemented")

    def batch_update(
        self,
        file_id: str,
        sheet_id: str,
        updates: list[CellUpdate],
        batch_size: int = 100,
    ) -> None:
        raise NotImplementedError("FeishuSheetsConnector.batch_update not yet implemented")

    def ensure_column(
        self,
        file_id: str,
        sheet_id: str,
        col_letter: str,
        header_name: str,
    ) -> None:
        raise NotImplementedError("FeishuSheetsConnector.ensure_column not yet implemented")

    def get_header(
        self,
        file_id: str,
        sheet_id: str,
    ) -> list[str]:
        raise NotImplementedError("FeishuSheetsConnector.get_header not yet implemented")
