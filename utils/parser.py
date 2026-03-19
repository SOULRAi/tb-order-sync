"""Value parsing and normalization utilities."""

from __future__ import annotations

from typing import Optional


def parse_number(value: object) -> Optional[float]:
    """Parse a value to float.

    Handles: int, float, numeric strings (with whitespace).
    Returns None for anything that cannot be safely parsed as a pure number.

    Examples:
        >>> parse_number("650")
        650.0
        >>> parse_number(" 12.5 ")
        12.5
        >>> parse_number(None)
        >>> parse_number("没报价")
    """
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None
        try:
            return float(stripped)
        except ValueError:
            return None
    return None


def normalize_order_no(value: object) -> str:
    """Normalize an order number string.

    Rules (v1 – strict):
      - trim leading/trailing whitespace
      - preserve original characters
      - return empty string for None / empty

    Future hook: could add prefix normalization, dedup hyphens, etc.
    """
    if value is None:
        return ""
    s = str(value).strip()
    return s
