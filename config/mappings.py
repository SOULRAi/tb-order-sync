"""Column mapping utilities.

Converts between column letters (A, B, ...) and 0-based indices,
and provides a typed mapping object built from Settings.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from config.settings import get_settings


def col_letter_to_index(letter: str) -> int:
    """Convert column letter(s) to 0-based index. A->0, B->1, ..., Z->25, AA->26."""
    letter = letter.upper().strip()
    result = 0
    for ch in letter:
        result = result * 26 + (ord(ch) - ord("A") + 1)
    return result - 1


def col_index_to_letter(index: int) -> str:
    """Convert 0-based index to column letter(s). 0->A, 1->B, ..., 25->Z, 26->AA."""
    result = ""
    idx = index + 1
    while idx > 0:
        idx, remainder = divmod(idx - 1, 26)
        result = chr(65 + remainder) + result
    return result


@dataclass(frozen=True)
class ColumnMapping:
    """Resolved column indices for A / B tables."""

    # A 表
    a_product_price: int
    a_packaging_price: int
    a_freight: int
    a_customer_quote: int
    a_gross_profit: int
    a_order_no: int
    a_refund_status: int

    # B 表
    b_order_no: int


@lru_cache(maxsize=1)
def get_column_mapping() -> ColumnMapping:
    s = get_settings()
    return ColumnMapping(
        a_product_price=col_letter_to_index(s.a_col_product_price),
        a_packaging_price=col_letter_to_index(s.a_col_packaging_price),
        a_freight=col_letter_to_index(s.a_col_freight),
        a_customer_quote=col_letter_to_index(s.a_col_customer_quote),
        a_gross_profit=col_letter_to_index(s.a_col_gross_profit),
        a_order_no=col_letter_to_index(s.a_col_order_no),
        a_refund_status=col_letter_to_index(s.a_col_refund_status),
        b_order_no=col_letter_to_index(s.b_col_order_no),
    )
