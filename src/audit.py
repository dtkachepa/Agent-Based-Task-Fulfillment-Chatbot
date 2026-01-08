# src/audit.py
from __future__ import annotations

from typing import Optional
from src.db import connect, DEFAULT_DB_PATH

def audit_user(user_id: str, limit_ledger: int = 20, limit_orders: int = 10) -> str:
    """
    Prints DB ground-truth for a user:
    - wallet balance
    - recent ledger entries (credits/debits)
    - recent orders + items
    """
    conn = connect(DEFAULT_DB_PATH)
    try:
        # wallet
        w = conn.execute(
            "SELECT user_id, balance_cents FROM wallets WHERE user_id = ?",
            (user_id,),
        ).fetchone()

        if w is None:
            return f"No wallet found for user_id={user_id}"

        out = []
        out.append("=== DB AUDIT (SOURCE OF TRUTH) ===")
        out.append(f"User: {user_id}")
        out.append(f"Wallet balance: ${w['balance_cents']/100:.2f}")
        out.append("")

        # ledger
        out.append(f"--- Ledger (last {limit_ledger}) ---")
        rows = conn.execute(
            """
            SELECT created_at, entry_type, amount_cents, balance_after_cents, source, client_request_id
            FROM ledger
            WHERE user_id = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (user_id, limit_ledger),
        ).fetchall()

        if not rows:
            out.append("(no ledger entries)")
        else:
            for r in rows:
                sign = "+" if r["entry_type"] == "CREDIT" else "-"
                out.append(
                    f"{r['created_at']} | {r['entry_type']} {sign}${abs(r['amount_cents'])/100:.2f} "
                    f"| bal_after ${r['balance_after_cents']/100:.2f} | {r['source']} | {r['client_request_id']}"
                )
        out.append("")

        # orders
        out.append(f"--- Orders (last {limit_orders}) ---")
        orders = conn.execute(
            """
            SELECT order_id, status, created_at, total_cents
            FROM orders
            WHERE user_id = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (user_id, limit_orders),
        ).fetchall()

        if not orders:
            out.append("(no orders)")
            return "\n".join(out)

        for o in orders:
            out.append(f"{o['order_id']} | {o['status']} | {o['created_at']} | total ${o['total_cents']/100:.2f}")
            items = conn.execute(
                """
                SELECT p.name, oi.quantity, oi.unit_price_cents
                FROM order_items oi
                JOIN products p ON p.product_id = oi.product_id
                WHERE oi.order_id = ?
                """,
                (o["order_id"],),
            ).fetchall()
            for it in items:
                out.append(f"  - {it['name']} x{it['quantity']} @ ${it['unit_price_cents']/100:.2f}")

        return "\n".join(out)

    finally:
        conn.close()
