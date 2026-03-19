"""Core business data models."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class OrderRecord(BaseModel):
    """A 表一行订单记录的内部表示。"""

    row_index: int = Field(..., description="原始表格行号 (0-based, 含表头)")
    order_no: str = ""
    product_price: Optional[str] = None
    packaging_price: Optional[str] = None
    freight: Optional[str] = None
    customer_quote: Optional[str] = None
    gross_profit: Optional[str] = None
    refund_status: Optional[str] = None
    raw_data: list[Any] = Field(default_factory=list)
    source_platform: str = "tencent_docs"
    source_sheet: str = ""


class RefundRecord(BaseModel):
    """B 表一行退款记录的内部表示。"""

    row_index: int
    order_no: str = ""
    refund_order_no: Optional[str] = None
    shop: Optional[str] = None
    customer_wechat: Optional[str] = None
    product: Optional[str] = None
    reason: Optional[str] = None
    amount: Optional[str] = None
    refund_status: Optional[str] = None
    raw_data: list[Any] = Field(default_factory=list)
