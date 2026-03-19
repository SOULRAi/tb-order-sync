"""Abstract base class for all sheet connectors."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Optional, Sequence


class BaseSheetConnector(ABC):
    """Unified interface for reading/writing cloud spreadsheets.

    All platform-specific connectors (Tencent Docs, Feishu, etc.)
    must implement this interface so that services remain platform-agnostic.
    """

    @abstractmethod
    def read_rows(
        self,
        file_id: str,
        sheet_id: str,
        *,
        start_row: int = 0,
        end_row: Optional[int] = None,
    ) -> list[list[Any]]:
        """Read rows from a sheet. Returns list of rows, each row is a list of cell values.

        Row indices are 0-based (row 0 = first row in sheet, typically the header).
        """
        ...

    @abstractmethod
    def write_cells(
        self,
        file_id: str,
        sheet_id: str,
        updates: list[CellUpdate],
    ) -> None:
        """Write individual cell values."""
        ...

    @abstractmethod
    def batch_update(
        self,
        file_id: str,
        sheet_id: str,
        updates: list[CellUpdate],
        batch_size: int = 100,
    ) -> None:
        """Write cells in batches to respect API rate limits."""
        ...

    @abstractmethod
    def ensure_column(
        self,
        file_id: str,
        sheet_id: str,
        col_letter: str,
        header_name: str,
    ) -> None:
        """Ensure a column exists with the given header. Create if missing."""
        ...

    @abstractmethod
    def get_header(
        self,
        file_id: str,
        sheet_id: str,
    ) -> list[str]:
        """Return the header row (first row) as a list of strings."""
        ...

    def update_row_style(
        self,
        file_id: str,
        sheet_id: str,
        row_index: int,
        bg_color: Optional[str] = None,
    ) -> None:
        """Optional: set background color for an entire row.

        Default implementation is a no-op. Connectors may override
        if the platform API supports style manipulation.
        """
        pass


class CellUpdate:
    """A single cell write instruction."""

    __slots__ = ("row", "col", "value")

    def __init__(self, row: int, col: int, value: Any) -> None:
        self.row = row
        self.col = col
        self.value = value

    def __repr__(self) -> str:
        return f"CellUpdate(row={self.row}, col={self.col}, value={self.value!r})"
