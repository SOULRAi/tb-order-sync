"""Helpers for resolving monthly Tencent Docs sheet targets."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, Protocol


_YEAR_MONTH_RE = re.compile(r"(?P<year>20\d{2})\s*[年./_-]?\s*(?P<month>1[0-2]|0?[1-9])\s*月?")
_MONTH_ONLY_RE = re.compile(r"(?<!\d)(?P<month>1[0-2]|0?[1-9])\s*月")


@dataclass(frozen=True, slots=True)
class SheetInfo:
    """Minimal spreadsheet tab metadata."""

    sheet_id: str
    title: str
    index: int = 0


@dataclass(frozen=True, slots=True)
class ResolvedSheetTarget:
    """Resolved file/sheet target for one task run."""

    file_id: str
    sheet_id: str
    title: str | None = None
    source: str = "fixed"


class SheetListingConnector(Protocol):
    """Connector protocol for optional sheet-listing support."""

    def list_sheets(self, file_id: str) -> list[SheetInfo]:
        """Return spreadsheet tabs for a file."""


def resolve_latest_month_sheet(
    connector: SheetListingConnector,
    *,
    file_id: str,
    fallback_sheet_id: str,
    title_keyword: str,
) -> ResolvedSheetTarget:
    """Resolve the latest monthly sheet by title keyword.

    If `title_keyword` is blank, the fixed `fallback_sheet_id` is returned unchanged.
    """
    keyword = title_keyword.strip()
    if not keyword:
        return ResolvedSheetTarget(file_id=file_id, sheet_id=fallback_sheet_id, source="fixed")

    list_sheets = getattr(connector, "list_sheets", None)
    if not callable(list_sheets):
        raise RuntimeError("当前 connector 不支持按标题自动选择最新月份工作表")

    sheets = list_sheets(file_id)
    selected = select_latest_month_sheet(sheets, keyword=keyword)
    return ResolvedSheetTarget(
        file_id=file_id,
        sheet_id=selected.sheet_id,
        title=selected.title,
        source="latest-month",
    )


def select_latest_month_sheet(sheets: Iterable[SheetInfo], *, keyword: str) -> SheetInfo:
    """Choose the latest monthly sheet from matching titles.

    Priority:
    1. Prefer titles that include both year and month, such as `2026年3月` / `2026-03` / `2026/03`
    2. Fall back to month-only titles such as `3月毛利率`

    This keeps same-year monthly tabs automatic, while allowing accurate cross-year
    selection when the sheet title carries the year.
    """
    needle = keyword.strip().lower()
    candidates = [sheet for sheet in sheets if needle in sheet.title.lower()]
    if not candidates:
        raise ValueError(f"未找到包含关键字 '{keyword}' 的工作表")

    ranked: list[tuple[int, int, int, SheetInfo]] = []
    unparsed: list[SheetInfo] = []
    for sheet in candidates:
        period = extract_year_month(sheet.title)
        if period is None:
            unparsed.append(sheet)
            continue
        year, month = period
        ranked.append((year, month, sheet.index, sheet))

    if ranked:
        ranked.sort(key=lambda item: (item[0], item[1], item[2]))
        return ranked[-1][3]

    if len(candidates) == 1:
        return candidates[0]

    titles = ", ".join(sheet.title for sheet in candidates[:5])
    raise ValueError(
        f"找到多个包含关键字 '{keyword}' 的工作表，但无法从标题解析月份: {titles}"
    )


def extract_year_month(title: str) -> tuple[int, int] | None:
    """Extract `(year, month)` from a sheet title.

    Supports examples like:
    - 2026年3月毛利率
    - 2026-03 毛利率
    - 3月毛利率
    """
    year_month = _YEAR_MONTH_RE.search(title)
    if year_month:
        year = int(year_month.group("year"))
        month = int(year_month.group("month"))
        return year, month

    month_only = _MONTH_ONLY_RE.search(title)
    if month_only:
        return 0, int(month_only.group("month"))

    return None
