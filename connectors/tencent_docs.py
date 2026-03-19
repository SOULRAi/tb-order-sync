"""Tencent Docs (腾讯文档) sheet connector.

API Reference (needs verification):
  腾讯文档开放平台: https://docs.qq.com/open/wiki/

TODO / NEED_VERIFY:
  - OAuth2 token refresh flow: the current implementation assumes a pre-obtained
    access_token passed via config. Production should implement refresh_token cycle.
  - Exact API endpoints and request/response schemas are marked inline.
  - Rate limit specifics (QPS, batch size caps) need confirmation from docs.
  - Style/formatting API availability is uncertain — update_row_style is best-effort.
"""

from __future__ import annotations

import time
from typing import Any, Optional

import httpx

from connectors.base import BaseSheetConnector, CellUpdate
from config.mappings import col_index_to_letter
from utils.logger import get_logger
from utils.retry import default_retry

logger = get_logger(__name__)

# ── TODO / NEED_VERIFY ─────────────────────────────────────────────────────
# Base URL for Tencent Docs Open API.
# 腾讯文档智能表格(SmartSheet)和在线表格(Sheet)的API路径可能不同，
# 需要根据实际文档类型确认。
# 以下为在线表格(Sheet)的推测路径：
_BASE_URL = "https://docs.qq.com/openapi/v2"

# TODO: 确认实际的 API 路径格式
# 读取单元格数据: GET /openapi/v2/files/{fileID}/sheets/{sheetID}/content
# 写入单元格数据: PUT /openapi/v2/files/{fileID}/sheets/{sheetID}/content
# 这些路径需要与腾讯文档开放平台文档核实
# ────────────────────────────────────────────────────────────────────────────


class TencentDocsConnector(BaseSheetConnector):
    """Connector for 腾讯文档 online spreadsheets."""

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        access_token: str,
        open_id: str = "",
    ) -> None:
        self._client_id = client_id
        self._client_secret = client_secret
        self._access_token = access_token
        self._open_id = open_id
        self._http = httpx.Client(
            base_url=_BASE_URL,
            timeout=30.0,
            headers=self._build_headers(),
        )

    def _build_headers(self) -> dict[str, str]:
        return {
            "Content-Type": "application/json",
            "Access-Token": self._access_token,
            # TODO / NEED_VERIFY: 腾讯文档 API 的认证 header 名称
            # 可能是 "Access-Token" 或 "Authorization: Bearer <token>"
            # 需根据实际文档确认
        }

    # ── Token refresh (placeholder) ────────────────────────────────────────
    def refresh_token(self) -> None:
        """TODO: Implement OAuth2 token refresh using client_id + client_secret.

        腾讯文档的 token 有效期通常较短，生产环境必须实现自动刷新。
        当前版本依赖外部提供有效的 access_token。
        """
        # TODO / NEED_VERIFY:
        # POST /oauth/v2/token
        # {
        #   "client_id": ...,
        #   "client_secret": ...,
        #   "grant_type": "refresh_token",
        #   "refresh_token": ...
        # }
        raise NotImplementedError("Token refresh not yet implemented — supply valid access_token in .env")

    # ── Read ───────────────────────────────────────────────────────────────
    @default_retry(max_attempts=3)
    def read_rows(
        self,
        file_id: str,
        sheet_id: str,
        *,
        start_row: int = 0,
        end_row: Optional[int] = None,
    ) -> list[list[Any]]:
        """Read rows from a Tencent Docs sheet.

        TODO / NEED_VERIFY: 确认实际的读取 API endpoint 和参数格式。
        以下为推测实现，需根据腾讯文档开放平台文档调整。
        """
        # TODO / NEED_VERIFY: 实际的 API 路径和参数
        # 可能的路径: GET /files/{fileID}/sheets/{sheetID}/content
        # 也可能需要指定 range，如 "A1:Z1000"
        url = f"/files/{file_id}/sheets/{sheet_id}/content"
        params: dict[str, Any] = {}
        if end_row is not None:
            # TODO: 腾讯文档可能使用 A1 notation 的 range 参数
            # 例如 range = "A{start_row+1}:Z{end_row+1}"
            params["range"] = f"A{start_row + 1}:ZZ{end_row + 1}"
        else:
            params["range"] = f"A{start_row + 1}:ZZ"

        logger.info("Reading rows from file=%s sheet=%s range=%s", file_id, sheet_id, params.get("range"))

        resp = self._http.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()

        # TODO / NEED_VERIFY: 解析响应数据结构
        # 腾讯文档返回的数据格式需要确认，以下是推测：
        # data = { "data": { "rows": [[cell, ...], ...] } }
        # 或: data = { "data": [[cell, ...], ...] }
        rows = data.get("data", {}).get("rows", [])
        if not rows and isinstance(data.get("data"), list):
            rows = data["data"]

        logger.info("Read %d rows from file=%s sheet=%s", len(rows), file_id, sheet_id)
        return rows

    # ── Write ──────────────────────────────────────────────────────────────
    @default_retry(max_attempts=3)
    def write_cells(
        self,
        file_id: str,
        sheet_id: str,
        updates: list[CellUpdate],
    ) -> None:
        """Write cell values to a Tencent Docs sheet.

        TODO / NEED_VERIFY: 确认写入 API 的 endpoint 和 request body 格式。
        """
        if not updates:
            return

        # TODO / NEED_VERIFY: 构建写入请求体
        # 腾讯文档可能支持批量单元格更新，格式推测如下:
        # PUT /files/{fileID}/sheets/{sheetID}/content
        # body = { "data": [ {"range": "G2", "value": 123}, ... ] }
        payload = self._build_write_payload(updates)
        url = f"/files/{file_id}/sheets/{sheet_id}/content"

        logger.info("Writing %d cells to file=%s sheet=%s", len(updates), file_id, sheet_id)

        resp = self._http.put(url, json=payload)
        resp.raise_for_status()

        logger.info("Successfully wrote %d cells", len(updates))

    @default_retry(max_attempts=3)
    def batch_update(
        self,
        file_id: str,
        sheet_id: str,
        updates: list[CellUpdate],
        batch_size: int = 100,
    ) -> None:
        """Write cells in batches to stay within API rate limits."""
        total = len(updates)
        for i in range(0, total, batch_size):
            batch = updates[i : i + batch_size]
            self.write_cells(file_id, sheet_id, batch)
            if i + batch_size < total:
                time.sleep(0.5)  # Basic rate-limit courtesy
        logger.info("Batch update complete: %d cells in %d batches", total, (total + batch_size - 1) // batch_size)

    # ── Column management ──────────────────────────────────────────────────
    def ensure_column(
        self,
        file_id: str,
        sheet_id: str,
        col_letter: str,
        header_name: str,
    ) -> None:
        """Ensure column header exists; write it if missing.

        TODO / NEED_VERIFY: 可能需要先读取 header row，检查列是否存在，
        如果不存在则需要插入列或写入 header。
        """
        header = self.get_header(file_id, sheet_id)
        from config.mappings import col_letter_to_index
        idx = col_letter_to_index(col_letter)

        if idx < len(header) and header[idx] == header_name:
            logger.debug("Column %s already has header '%s'", col_letter, header_name)
            return

        # Write the header cell
        self.write_cells(file_id, sheet_id, [CellUpdate(row=0, col=idx, value=header_name)])
        logger.info("Ensured column %s header = '%s'", col_letter, header_name)

    def get_header(
        self,
        file_id: str,
        sheet_id: str,
    ) -> list[str]:
        """Read the first row as header."""
        rows = self.read_rows(file_id, sheet_id, start_row=0, end_row=1)
        if rows:
            return [str(v) if v is not None else "" for v in rows[0]]
        return []

    # ── Style (optional) ───────────────────────────────────────────────────
    def update_row_style(
        self,
        file_id: str,
        sheet_id: str,
        row_index: int,
        bg_color: Optional[str] = None,
    ) -> None:
        """Optional: set row background color.

        TODO / NEED_VERIFY: 腾讯文档是否支持通过 API 设置单元格/行样式。
        如果不支持，此方法将仅记录日志并跳过。
        当前实现为 best-effort placeholder。
        """
        if bg_color is None:
            logger.debug("update_row_style called with no color, skipping row=%d", row_index)
            return

        # TODO / NEED_VERIFY: 样式 API 路径和格式
        # 可能的路径: PUT /files/{fileID}/sheets/{sheetID}/styles
        # body = { "range": "A{row}:Z{row}", "style": {"backgroundColor": "#FF0000"} }
        logger.info(
            "Style update requested for row=%d bg=%s (file=%s) — "
            "TODO: verify Tencent Docs style API support",
            row_index, bg_color, file_id,
        )

    # ── Internal helpers ───────────────────────────────────────────────────
    @staticmethod
    def _build_write_payload(updates: list[CellUpdate]) -> dict[str, Any]:
        """Build the API request body for a batch cell write.

        TODO / NEED_VERIFY: 确认腾讯文档的批量写入 request body 格式。
        """
        cells = []
        for u in updates:
            col_letter = col_index_to_letter(u.col)
            cell_ref = f"{col_letter}{u.row + 1}"  # A1 notation, 1-based
            cells.append({"range": cell_ref, "value": u.value})
        return {"data": cells}
