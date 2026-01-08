# src/tools.py
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List, Dict, Any
from uuid import uuid4

import sqlite3

from src.db import connect, DEFAULT_DB_PATH
from src.models import (
    BalanceResponse,
    AddFundsResponse,
    Product,
    SearchProductsResponse,
    GetProductResponse,
    PurchaseResponse,
    Order,
    OrderItem,
    GetOrdersResponse,
)

# -------------------------
# Helpers (internal)
# -------------------------

def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def _new_tx_id() -> str:
    return f"tx_{uuid4().hex}"

def _new_order_id() -> str:
    return f"o_{uuid4().hex[:10]}"

def _row_to_product(row: Dict[str, Any]) -> Product:
    return Product(
        product_id=row["product_id"],
        name=row["name"],
        price_cents=row["price_cents"],
        inventory=row["inventory"],
    )

def _ensure_user_exists(conn: sqlite3.Connection, user_id: str) -> None:
    cur = conn.execute("SELECT 1 FROM users WHERE user_id = ?", (user_id,))
    if cur.fetchone() is None:
        raise ValueError(f"Unknown user_id: {user_id}")

def _get_wallet_balance(conn: sqlite3.Connection, user_id: str) -> int:
    row = conn.execute(
        "SELECT balance_cents FROM wallets WHERE user_id = ?",
        (user_id,),
    ).fetchone()
    if row is None:
        raise ValueError(f"Wallet not found for user_id: {user_id}")
    return int(row["balance_cents"])

def _get_ledger_by_client_request(conn: sqlite3.Connection, client_request_id: str) -> Optional[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM ledger WHERE client_request_id = ?",
        (client_request_id,),
    ).fetchone()


# -------------------------
# Tool 1: get_balance
# -------------------------
def get_balance(user_id: str, db_path: Path = DEFAULT_DB_PATH) -> BalanceResponse:
    conn = connect(db_path)
    try:
        _ensure_user_exists(conn, user_id)
        bal = _get_wallet_balance(conn, user_id)
        return BalanceResponse(user_id=user_id, balance_cents=bal)
    finally:
        conn.close()


# -------------------------
# Tool 2: add_funds (idempotent)
# -------------------------
def add_funds(
    user_id: str,
    amount_cents: int,
    source: str,
    client_request_id: str,
    db_path: Path = DEFAULT_DB_PATH,
) -> AddFundsResponse:
    if amount_cents <= 0:
        raise ValueError("amount_cents must be > 0")

    conn = connect(db_path)
    try:
        _ensure_user_exists(conn, user_id)

        # Idempotency: if we've seen this request_id, return the original result
        existing = _get_ledger_by_client_request(conn, client_request_id)
        if existing is not None:
            # reconstruct "new balance" by reading wallet now (should already include it)
            bal = _get_wallet_balance(conn, user_id)
            return AddFundsResponse(
                user_id=user_id,
                added_cents=int(existing["amount_cents"]),
                new_balance_cents=bal,
                tx_id=existing["tx_id"],
            )

        tx_id = _new_tx_id()
        now = _utc_now_iso()

        # Atomic update
        conn.execute("BEGIN IMMEDIATE;")
        bal_before = _get_wallet_balance(conn, user_id)
        bal_after = bal_before + amount_cents

        conn.execute(
            "UPDATE wallets SET balance_cents = ? WHERE user_id = ?",
            (bal_after, user_id),
        )

        conn.execute(
            "INSERT INTO ledger(tx_id, user_id, kind, amount_cents, created_at, client_request_id, metadata_json) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                tx_id,
                user_id,
                "TOPUP",
                amount_cents,
                now,
                client_request_id,
                json.dumps({"source": source}),
            ),
        )
        conn.commit()

        return AddFundsResponse(
            user_id=user_id,
            added_cents=amount_cents,
            new_balance_cents=bal_after,
            tx_id=tx_id,
        )
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# -------------------------
# Tool 3: search_products
# -------------------------
# def search_products(query: Optional[str] = None, db_path: Path = DEFAULT_DB_PATH) -> SearchProductsResponse:
#     conn = connect(db_path)
#     try:
#         if query is None or query.strip() == "":
#             rows = conn.execute(
#                 "SELECT product_id, name, price_cents, inventory FROM products ORDER BY name ASC"
#             ).fetchall()
#         else:
#             q = f"%{query.strip().lower()}%"
#             rows = conn.execute(
#                 "SELECT product_id, name, price_cents, inventory "
#                 "FROM products WHERE LOWER(name) LIKE ? "
#                 "ORDER BY name ASC",
#                 (q,),
#             ).fetchall()

#             # Fallback: keyword OR search (handles plurals/extra words)
#             if len(rows) == 0:
#                 words = [w for w in query.lower().replace("-", " ").split() if w]
#                 if words:
#                     clauses = " OR ".join(["LOWER(name) LIKE ?"] * len(words))
#                     params = tuple([f"%{w}%" for w in words])
#                     rows = conn.execute(
#                         f"SELECT product_id, name, price_cents, inventory FROM products WHERE {clauses} ORDER BY name ASC",
#                         params,
#                     ).fetchall()

#         products = [_row_to_product(dict(r)) for r in rows]
#         return SearchProductsResponse(products=products)
#     finally:
#         conn.close()

def search_products(query: Optional[str] = None, db_path: Path = DEFAULT_DB_PATH) -> SearchProductsResponse:
    conn = connect(db_path)
    try:
        if query is None or query.strip() == "":
            rows = conn.execute(
                "SELECT product_id, name, price_cents, inventory FROM products ORDER BY name ASC"
            ).fetchall()
        else:
            q_raw = query.strip().lower()
            q = f"%{q_raw}%"
            rows = conn.execute(
                "SELECT product_id, name, price_cents, inventory "
                "FROM products WHERE LOWER(name) LIKE ? "
                "ORDER BY name ASC",
                (q,),
            ).fetchall()

            # Fallback 1: keyword OR search + crude plural normalization
            if len(rows) == 0:
                words = []
                for w in q_raw.replace("-", " ").split():
                    if not w:
                        continue
                    # cables -> cable, adapters -> adapter, etc.
                    if len(w) > 3 and w.endswith("s"):
                        w = w[:-1]
                    words.append(w)

                if words:
                    clauses = " OR ".join(["LOWER(name) LIKE ?"] * len(words))
                    params = tuple([f"%{w}%" for w in words])
                    rows = conn.execute(
                        f"SELECT product_id, name, price_cents, inventory FROM products WHERE {clauses} ORDER BY name ASC",
                        params,
                    ).fetchall()

        products = [_row_to_product(dict(r)) for r in rows]
        return SearchProductsResponse(products=products)
    finally:
        conn.close()


# -------------------------
# Tool 4: get_product
# -------------------------
def get_product(product_id: str, db_path: Path = DEFAULT_DB_PATH) -> GetProductResponse:
    conn = connect(db_path)
    try:
        row = conn.execute(
            "SELECT product_id, name, price_cents, inventory FROM products WHERE product_id = ?",
            (product_id,),
        ).fetchone()
        if row is None:
            raise ValueError(f"Unknown product_id: {product_id}")
        return GetProductResponse(product=_row_to_product(dict(row)))
    finally:
        conn.close()


# -------------------------
# Tool 5: purchase (idempotent, transactional)
# -------------------------
def purchase(
    user_id: str,
    product_id: str,
    quantity: int,
    client_request_id: str,
    db_path: Path = DEFAULT_DB_PATH,
) -> PurchaseResponse:
    if quantity <= 0:
        raise ValueError("quantity must be > 0")

    conn = connect(db_path)
    try:
        _ensure_user_exists(conn, user_id)

        # Idempotency: if already processed, return the order in metadata
        existing = _get_ledger_by_client_request(conn, client_request_id)
        if existing is not None:
            meta = json.loads(existing["metadata_json"] or "{}")
            order_id = meta.get("order_id")
            if not order_id:
                raise RuntimeError("Idempotent purchase found but missing order_id metadata.")
            # Read order info (current balance too)
            bal = _get_wallet_balance(conn, user_id)
            item = conn.execute(
                "SELECT oi.product_id, oi.quantity, oi.unit_price_cents, p.name "
                "FROM order_items oi JOIN products p ON p.product_id = oi.product_id "
                "WHERE oi.order_id = ? LIMIT 1",
                (order_id,),
            ).fetchone()
            if item is None:
                raise RuntimeError("Order missing items for idempotent purchase.")
            total_cents = int(conn.execute(
                "SELECT total_cents FROM orders WHERE order_id = ?",
                (order_id,),
            ).fetchone()["total_cents"])

            return PurchaseResponse(
                user_id=user_id,
                order_id=order_id,
                product_id=item["product_id"],
                quantity=int(item["quantity"]),
                unit_price_cents=int(item["unit_price_cents"]),
                total_cents=total_cents,
                new_balance_cents=bal,
            )

        # Normal purchase path
        conn.execute("BEGIN IMMEDIATE;")

        # Lock/read product
        prod = conn.execute(
            "SELECT product_id, name, price_cents, inventory FROM products WHERE product_id = ?",
            (product_id,),
        ).fetchone()
        if prod is None:
            raise ValueError(f"Unknown product_id: {product_id}")

        price_cents = int(prod["price_cents"])
        inventory = int(prod["inventory"])
        if inventory < quantity:
            raise ValueError(f"Insufficient inventory: requested {quantity}, available {inventory}")

        total_cents = price_cents * quantity

        bal_before = _get_wallet_balance(conn, user_id)
        if bal_before < total_cents:
            raise ValueError(f"Insufficient funds: cost {total_cents} cents, balance {bal_before} cents")

        # Apply updates
        bal_after = bal_before - total_cents
        new_inventory = inventory - quantity

        conn.execute(
            "UPDATE wallets SET balance_cents = ? WHERE user_id = ?",
            (bal_after, user_id),
        )
        conn.execute(
            "UPDATE products SET inventory = ? WHERE product_id = ?",
            (new_inventory, product_id),
        )

        # Create order + items
        order_id = _new_order_id()
        now = _utc_now_iso()

        conn.execute(
            "INSERT INTO orders(order_id, user_id, created_at, status, total_cents) VALUES (?, ?, ?, ?, ?)",
            (order_id, user_id, now, "PLACED", total_cents),
        )
        conn.execute(
            "INSERT INTO order_items(order_id, product_id, quantity, unit_price_cents) VALUES (?, ?, ?, ?)",
            (order_id, product_id, quantity, price_cents),
        )

        # Ledger entry (negative amount for purchase)
        tx_id = _new_tx_id()
        conn.execute(
            "INSERT INTO ledger(tx_id, user_id, kind, amount_cents, created_at, client_request_id, metadata_json) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                tx_id,
                user_id,
                "PURCHASE",
                -total_cents,
                now,
                client_request_id,
                json.dumps({"order_id": order_id, "product_id": product_id, "quantity": quantity}),
            ),
        )

        conn.commit()

        return PurchaseResponse(
            user_id=user_id,
            order_id=order_id,
            product_id=product_id,
            quantity=quantity,
            unit_price_cents=price_cents,
            total_cents=total_cents,
            new_balance_cents=bal_after,
        )

    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# -------------------------
# Tool 6: get_orders
# -------------------------
def get_orders(user_id: str, limit: int = 10, db_path: Path = DEFAULT_DB_PATH) -> GetOrdersResponse:
    if limit <= 0 or limit > 50:
        raise ValueError("limit must be in 1..50")

    conn = connect(db_path)
    try:
        _ensure_user_exists(conn, user_id)

        order_rows = conn.execute(
            "SELECT order_id, created_at, status, total_cents "
            "FROM orders WHERE user_id = ? "
            "ORDER BY created_at DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()

        orders: List[Order] = []
        for o in order_rows:
            item_rows = conn.execute(
                "SELECT oi.product_id, p.name, oi.quantity, oi.unit_price_cents "
                "FROM order_items oi "
                "JOIN products p ON p.product_id = oi.product_id "
                "WHERE oi.order_id = ?",
                (o["order_id"],),
            ).fetchall()

            items = [
                OrderItem(
                    product_id=r["product_id"],
                    name=r["name"],
                    quantity=int(r["quantity"]),
                    unit_price_cents=int(r["unit_price_cents"]),
                )
                for r in item_rows
            ]

            orders.append(
                Order(
                    order_id=o["order_id"],
                    created_at=o["created_at"],
                    status=o["status"],
                    total_cents=int(o["total_cents"]),
                    items=items,
                )
            )

        return GetOrdersResponse(user_id=user_id, orders=orders)
    finally:
        conn.close()
