# src/models.py
from __future__ import annotations

from typing import Optional, Literal, List, Dict, Any
from pydantic import BaseModel, Field, conint


# ---------- Shared ----------
Cents = conint(ge=0)  # type: ignore[valid-type]


class ToolError(BaseModel):
    error: str
    detail: Optional[str] = None


# ---------- Balance ----------
class BalanceRequest(BaseModel):
    user_id: str = Field(..., description="User identifier, e.g. u_1001")


class BalanceResponse(BaseModel):
    user_id: str
    balance_cents: int


# ---------- Add Funds ----------
class AddFundsRequest(BaseModel):
    user_id: str
    amount_cents: Cents
    source: str = Field(default="external", description="Funding source label")
    client_request_id: str = Field(..., description="Idempotency key")


class AddFundsResponse(BaseModel):
    user_id: str
    added_cents: int
    new_balance_cents: int
    tx_id: str


# ---------- Products ----------
class Product(BaseModel):
    product_id: str
    name: str
    price_cents: int
    inventory: int


class SearchProductsRequest(BaseModel):
    query: Optional[str] = Field(default=None, description="Optional search string")


class SearchProductsResponse(BaseModel):
    products: List[Product]


class GetProductRequest(BaseModel):
    product_id: str


class GetProductResponse(BaseModel):
    product: Product


# ---------- Purchase ----------
class PurchaseRequest(BaseModel):
    user_id: str
    product_id: str
    quantity: conint(gt=0)  # type: ignore[valid-type]
    client_request_id: str = Field(..., description="Idempotency key")


class PurchaseResponse(BaseModel):
    user_id: str
    order_id: str
    product_id: str
    quantity: int
    unit_price_cents: int
    total_cents: int
    new_balance_cents: int


# ---------- Orders ----------
class OrderItem(BaseModel):
    product_id: str
    name: str
    quantity: int
    unit_price_cents: int


class Order(BaseModel):
    order_id: str
    created_at: str
    status: str
    total_cents: int
    items: List[OrderItem]


class GetOrdersRequest(BaseModel):
    user_id: str
    limit: conint(gt=0, le=50) = 10  # type: ignore[valid-type]


class GetOrdersResponse(BaseModel):
    user_id: str
    orders: List[Order]
