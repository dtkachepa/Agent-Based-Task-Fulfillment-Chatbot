# src/rule_agent.py
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional, Dict, Any, List
from uuid import uuid4

from src.tools import get_balance, add_funds, search_products, get_product, purchase, get_orders

YES = {"yes", "y", "yeah", "yep", "sure", "ok", "okay", "confirm"}
NO = {"no", "n", "nope", "cancel", "stop"}

@dataclass
class PendingPurchase:
    product_id: str
    quantity: int
    total_cents: int
    unit_price_cents: int
    product_name: str
    purchase_request_id: str

@dataclass
class PendingTopup:
    amount_cents: int
    topup_request_id: str
    source: str = "external"

class RuleAgent:
    """
    Deterministic agent that uses tools and state.
    This guarantees demoability even if LLM quota is exhausted.
    """
    def __init__(self):
        self.pending_purchase: Optional[PendingPurchase] = None
        self.pending_topup: Optional[PendingTopup] = None

    def _money_to_cents(self, text: str) -> Optional[int]:
        # supports: "$50", "50", "50.25"
        m = re.search(r"\$?\s*(\d+(\.\d{1,2})?)", text)
        if not m:
            return None
        val = float(m.group(1))
        return int(round(val * 100))

    def _extract_quantity_and_query(self, text: str) -> tuple[int, str]:
        # "buy 2 ethernet cables" -> (2, "ethernet cables")
        m = re.search(r"\bbuy\s+(\d+)\s+(.+)", text, re.IGNORECASE)
        if m:
            return int(m.group(1)), m.group(2).strip()
        # "buy ethernet cable" -> default 1
        m = re.search(r"\bbuy\s+(.+)", text, re.IGNORECASE)
        if m:
            return 1, m.group(1).strip()
        return 1, text.strip()

    def handle(self, user_text: str, user_id: str) -> str:
        t = user_text.strip()
        tl = t.lower()

        # --- handle confirmation for pending topup ---
        if self.pending_topup is not None:
            if tl in YES:
                top = self.pending_topup
                self.pending_topup = None
                out = add_funds(
                    user_id=user_id,
                    amount_cents=top.amount_cents,
                    source=top.source,
                    client_request_id=top.topup_request_id,
                )
                return f"✅ Added ${out.added_cents/100:.2f}. New balance: ${out.new_balance_cents/100:.2f}."
            if tl in NO:
                self.pending_topup = None
                return "Okay — top-up cancelled."
            return "Please reply 'yes' to confirm the top-up or 'no' to cancel."

        # --- handle confirmation for pending purchase ---
        if self.pending_purchase is not None:
            if tl in YES:
                pp = self.pending_purchase
                self.pending_purchase = None
                out = purchase(
                    user_id=user_id,
                    product_id=pp.product_id,
                    quantity=pp.quantity,
                    client_request_id=pp.purchase_request_id,
                )
                return (
                    f"✅ Order placed: {out.order_id}\n"
                    f"- Item: {pp.product_name} x{pp.quantity}\n"
                    f"- Total: ${out.total_cents/100:.2f}\n"
                    f"- New balance: ${out.new_balance_cents/100:.2f}"
                )
            if tl in NO:
                self.pending_purchase = None
                return "Okay — purchase cancelled."
            return "Please reply 'yes' to confirm the purchase or 'no' to cancel."

        # --- intents ---
        if "balance" in tl:
            b = get_balance(user_id)
            return f"Your balance is ${b.balance_cents/100:.2f}."

        # if tl.startswith("show") or "list" in tl or "catalog" in tl or "products" in tl:
        #     # e.g., "show me cables" -> query="cables"
        #     query = t
        #     query = re.sub(r"^(show|list)\s+(me\s+)?", "", query, flags=re.IGNORECASE).strip()
        #     res = search_products(query if query else None)
        #     if not res.products:
        #         return "I didn't find matching products."
        #     lines = [f"{p.product_id}: {p.name} — ${p.price_cents/100:.2f} (stock {p.inventory})" for p in res.products[:10]]
        #     return "Here are matching products:\n" + "\n".join(lines)

        if tl.startswith("show") or tl.startswith("list") or "catalog" in tl or tl == "products" or tl == "product":
            # Normalize to decide whether user wants full catalog or a filtered search
            query = re.sub(r"^(show|list)\s+(me\s+)?", "", t, flags=re.IGNORECASE).strip()
            ql = query.lower()

            # If user says "show products" / "list products" / "catalog" / "show all", list everything
            if ql in {"", "products", "product", "catalog", "all", "everything", "inventory", "stock"}:
                res = search_products(None)
            else:
                res = search_products(query)

            if not res.products:
                return "I didn't find matching products."

            lines = [
                f"{p.product_id}: {p.name} — ${p.price_cents/100:.2f} (stock {p.inventory})"
                for p in res.products
            ]
            # more = "" if len(res.products) <= 10 else f"\n…and {len(res.products)-10} more. Try 'show me <keyword>'."
            return "Here are the products we currently have:\n" + "\n".join(lines) #+ more

        if tl.startswith("add") or "top up" in tl or "load" in tl:
            cents = self._money_to_cents(t)
            if cents is None or cents <= 0:
                return "How much would you like to add? Example: 'add $50'"
            self.pending_topup = PendingTopup(amount_cents=cents, topup_request_id=f"topup_{uuid4().hex}")
            return f"Confirm top-up of ${cents/100:.2f}? (yes/no)"

        if tl.startswith("buy"):
            qty, query = self._extract_quantity_and_query(t)
            res = search_products(query)
            if not res.products:
                return "I couldn't find that product in the catalog. Try 'show me <item>'."

            # pick best match: first result (simple + deterministic)
            chosen = res.products[0]
            prod = get_product(chosen.product_id).product

            if prod.inventory < qty:
                return f"Sorry — only {prod.inventory} left in stock for {prod.name}."

            total = prod.price_cents * qty
            bal = get_balance(user_id).balance_cents
            if bal < total:
                short = total - bal
                # offer topup
                self.pending_topup = PendingTopup(amount_cents=short, topup_request_id=f"topup_{uuid4().hex}")
                return (
                    f"Insufficient funds. You need ${total/100:.2f} but have ${bal/100:.2f}.\n"
                    f"Would you like to top up ${short/100:.2f} to proceed? (yes/no)"
                )

            self.pending_purchase = PendingPurchase(
                product_id=prod.product_id,
                quantity=qty,
                total_cents=total,
                unit_price_cents=prod.price_cents,
                product_name=prod.name,
                purchase_request_id=f"purchase_{uuid4().hex}",
            )
            return f"Confirm purchase: {prod.name} x{qty} for ${total/100:.2f}? (yes/no)"

        if "orders" in tl or "history" in tl:
            o = get_orders(user_id, limit=5)
            if not o.orders:
                return "You have no recent orders."
            lines: List[str] = []
            for order in o.orders:
                lines.append(f"{order.order_id} | {order.status} | ${order.total_cents/100:.2f} | {order.created_at}")
            return "Recent orders:\n" + "\n".join(lines)

        return (
            "I can help with: balance, show products, buy <qty> <item>, add $<amount>, orders.\n"
            "Example: 'show me cables' or 'buy 2 ethernet cable'."
        )
