"""Row fingerprinting and diff utilities for incremental sync."""

from __future__ import annotations

import hashlib
from typing import Any, Sequence


def row_fingerprint(fields: Sequence[Any]) -> str:
    """Generate an MD5 hex digest for a list of cell values.

    Used to detect whether a row's key fields have changed since last sync.
    """
    raw = "|".join(_normalize(v) for v in fields)
    return hashlib.md5(raw.encode("utf-8")).hexdigest()


def set_hash(items: Sequence[str]) -> str:
    """Generate a hash for an ordered set of strings (e.g. refund order nos)."""
    combined = "\n".join(sorted(items))
    return hashlib.md5(combined.encode("utf-8")).hexdigest()


def _normalize(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()
