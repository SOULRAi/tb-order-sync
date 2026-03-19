"""Tencent Docs (腾讯文档) sheet connector.

Uses the official Online Sheet v3 APIs:
  - GET  /openapi/spreadsheet/v3/files/{fileId}/{sheetId}/{range}
  - POST /openapi/spreadsheet/v3/files/{fileId}/batchUpdate

Notes:
  - Access token refresh is still external. Supply a valid access token in config.
  - The sheet model exposes text color formatting. For "整行标红", this connector
    rewrites the full row with red text formatting.
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

_BASE_URL = "https://docs.qq.com"
# Tencent Docs v3 range query limit:
# rows <= 1000, cols <= 200, total cells <= 10000.
# Current project only needs up to column I/L, so keep the query window narrow.
_MAX_QUERY_ROWS = 200
_MAX_QUERY_COLS = 20
_MAX_BATCH_REQUESTS = 5
_BATCH_SLEEP_SECONDS = 0.5
_DEFAULT_TEXT_COLOR = {"red": 0, "green": 0, "blue": 0, "alpha": 255}


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
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Access-Token": self._access_token,
            "Client-Id": self._client_id,
        }
        if self._open_id:
            headers["Open-Id"] = self._open_id
        else:
            logger.warning("Tencent connector initialized without Open-Id; official APIs require it")
        return headers

    def refresh_token(self) -> None:
        """Token refresh remains external in this MVP."""
        raise NotImplementedError("Token refresh not yet implemented — supply valid access_token in .env")

    @default_retry(max_attempts=5)
    def read_rows(
        self,
        file_id: str,
        sheet_id: str,
        *,
        start_row: int = 0,
        end_row: Optional[int] = None,
    ) -> list[list[Any]]:
        """Read rows from a Tencent Docs sheet using the official v3 range API."""
        if end_row is not None and end_row <= start_row:
            return []

        max_col_letter = col_index_to_letter(_MAX_QUERY_COLS - 1)
        all_rows: list[list[Any]] = []
        next_row = start_row

        while True:
            chunk_end = next_row + _MAX_QUERY_ROWS
            if end_row is not None:
                chunk_end = min(chunk_end, end_row)

            range_ref = f"A{next_row + 1}:{max_col_letter}{chunk_end}"
            url = f"/openapi/spreadsheet/v3/files/{file_id}/{sheet_id}/{range_ref}"
            logger.info("Reading rows from file=%s sheet=%s range=%s", file_id, sheet_id, range_ref)

            try:
                data = self._unwrap_response(self._http.get(url))
            except RuntimeError as exc:
                if all_rows and "range' invalid" in str(exc):
                    logger.info("Stop reading at invalid range boundary: %s", range_ref)
                    break
                raise
            grid_data = data.get("gridData", data)
            rows = self._grid_data_to_rows(grid_data)
            all_rows.extend(rows)

            requested_rows = chunk_end - next_row
            if end_row is not None and chunk_end >= end_row:
                break
            if len(rows) < requested_rows:
                break

            next_row = chunk_end

        logger.info("Read %d rows from file=%s sheet=%s", len(all_rows), file_id, sheet_id)
        return all_rows

    @default_retry(max_attempts=5)
    def write_cells(
        self,
        file_id: str,
        sheet_id: str,
        updates: list[CellUpdate],
    ) -> None:
        """Write cell values via the official v3 batchUpdate API."""
        if not updates:
            return

        url = f"/openapi/spreadsheet/v3/files/{file_id}/batchUpdate"
        payload = self._build_write_payload(sheet_id, updates)
        logger.info("Writing %d cells to file=%s sheet=%s", len(updates), file_id, sheet_id)
        self._unwrap_response(self._http.post(url, json=payload))
        logger.info("Successfully wrote %d cells", len(updates))

    @default_retry(max_attempts=5)
    def batch_update(
        self,
        file_id: str,
        sheet_id: str,
        updates: list[CellUpdate],
        batch_size: int = 100,
    ) -> None:
        """Write cells in batches while respecting Tencent Docs batch limits."""
        total = len(updates)
        chunk_size = max(1, min(batch_size, _MAX_BATCH_REQUESTS))
        for i in range(0, total, chunk_size):
            batch = updates[i : i + chunk_size]
            self.write_cells(file_id, sheet_id, batch)
            if i + chunk_size < total:
                time.sleep(_BATCH_SLEEP_SECONDS)
        logger.info("Batch update complete: %d cells in %d batches", total, (total + chunk_size - 1) // chunk_size)

    def ensure_column(
        self,
        file_id: str,
        sheet_id: str,
        col_letter: str,
        header_name: str,
    ) -> None:
        """Ensure column header exists; write it if missing."""
        header = self.get_header(file_id, sheet_id)
        from config.mappings import col_letter_to_index

        idx = col_letter_to_index(col_letter)
        if idx < len(header) and header[idx] == header_name:
            return

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

    @default_retry(max_attempts=5)
    def update_row_style(
        self,
        file_id: str,
        sheet_id: str,
        row_index: int,
        bg_color: Optional[str] = None,
    ) -> None:
        """Rewrite a row with red or default text formatting."""
        header = self.get_header(file_id, sheet_id)
        rows = self.read_rows(file_id, sheet_id, start_row=row_index, end_row=row_index + 1)
        if not rows:
            logger.warning("No row found for style update: row=%d file=%s sheet=%s", row_index, file_id, sheet_id)
            return

        row_values = list(rows[0])
        width = max(len(header), len(row_values))
        if width == 0:
            return
        if len(row_values) < width:
            row_values.extend([""] * (width - len(row_values)))

        text_color = self._hex_to_rgba(bg_color) if bg_color else _DEFAULT_TEXT_COLOR
        payload = {
            "requests": [
                {
                    "updateRangeRequest": {
                        "sheetId": sheet_id,
                        "gridData": {
                            "startRow": row_index,
                            "startColumn": 0,
                            "rows": [
                                {
                                    "values": [
                                        self._build_cell_data(value, text_color=text_color)
                                        for value in row_values
                                    ]
                                }
                            ],
                        },
                    }
                }
            ]
        }
        url = f"/openapi/spreadsheet/v3/files/{file_id}/batchUpdate"
        self._unwrap_response(self._http.post(url, json=payload))
        logger.info("Updated row style for row=%d file=%s sheet=%s", row_index, file_id, sheet_id)

    @staticmethod
    def _grid_data_to_rows(grid_data: dict[str, Any]) -> list[list[Any]]:
        rows: list[list[Any]] = []
        for row_data in grid_data.get("rows", []):
            rows.append([
                TencentDocsConnector._extract_cell_value(cell)
                for cell in row_data.get("values", [])
            ])
        return rows

    @staticmethod
    def _extract_cell_value(cell: dict[str, Any]) -> Any:
        if not isinstance(cell, dict):
            return None
        cell_value = cell.get("cellValue") or {}
        if "number" in cell_value:
            return cell_value["number"]
        if "text" in cell_value:
            return cell_value["text"]
        if "link" in cell_value:
            link = cell_value["link"] or {}
            return link.get("text") or link.get("url") or ""
        if "location" in cell_value:
            location = cell_value["location"] or {}
            return location.get("name") or ""
        if "time" in cell_value:
            return cell_value["time"]
        if "select" in cell_value:
            select = cell_value["select"] or {}
            return select.get("text") or ""
        return None

    @staticmethod
    def _unwrap_response(resp: httpx.Response) -> dict[str, Any]:
        if resp.status_code == 429:
            raise RuntimeError("Tencent Docs API failed: HTTP 429 Requests Over Limit. Please Retry Later.")
        resp.raise_for_status()
        payload = resp.json()
        if not isinstance(payload, dict):
            raise RuntimeError(f"Unexpected Tencent Docs response: {payload!r}")

        if "ret" in payload and payload.get("ret") not in (0, None):
            raise RuntimeError(
                TencentDocsConnector._friendly_api_error(
                    code=payload.get("ret"),
                    message=payload.get("msg"),
                )
            )
        if "code" in payload and payload.get("code") not in (0, None):
            raise RuntimeError(
                TencentDocsConnector._friendly_api_error(
                    code=payload.get("code"),
                    message=payload.get("message"),
                )
            )

        data = payload.get("data")
        if isinstance(data, dict):
            return data
        return payload

    @staticmethod
    def _friendly_api_error(code: Any, message: Any) -> str:
        code_text = str(code)
        message_text = str(message or "")
        base = f"Tencent Docs API failed: code={code_text} message={message_text}"

        if code_text == "400007":
            return base + "。腾讯文档接口限流，请稍后重试。"
        if code_text == "400001":
            return base + "。请求参数不合法，请检查表格 ID、sheet ID、列范围或表格结构。"
        if code_text in {"401", "401001"}:
            return base + "。认证失败，请检查 Access Token、Client ID、Open ID。"
        if code_text in {"403", "403001"}:
            return base + "。权限不足，请确认应用授权和文档访问权限。"
        return base

    @staticmethod
    def _build_write_payload(sheet_id: str, updates: list[CellUpdate]) -> dict[str, Any]:
        return {
            "requests": [
                {
                    "updateRangeRequest": {
                        "sheetId": sheet_id,
                        "gridData": {
                            "startRow": update.row,
                            "startColumn": update.col,
                            "rows": [
                                {
                                    "values": [
                                        TencentDocsConnector._build_cell_data(update.value)
                                    ]
                                }
                            ],
                        },
                    }
                }
                for update in updates
            ]
        }

    @staticmethod
    def _build_cell_data(value: Any, text_color: Optional[dict[str, int]] = None) -> dict[str, Any]:
        cell_data: dict[str, Any] = {"cellValue": TencentDocsConnector._build_cell_value(value)}
        if text_color is not None:
            cell_data["cellFormat"] = {"textFormat": {"color": text_color}}
        return cell_data

    @staticmethod
    def _build_cell_value(value: Any) -> dict[str, Any]:
        if isinstance(value, bool):
            return {"text": str(value).lower()}
        if isinstance(value, (int, float)):
            return {"number": value}
        if value is None:
            return {"text": ""}
        return {"text": str(value)}

    @staticmethod
    def _hex_to_rgba(color: str) -> dict[str, int]:
        value = color.strip().lstrip("#")
        if len(value) != 6:
            raise ValueError(f"Unsupported color value: {color}")
        return {
            "red": int(value[0:2], 16),
            "green": int(value[2:4], 16),
            "blue": int(value[4:6], 16),
            "alpha": 255,
        }
