# src/tools_demo.py
from __future__ import annotations
from uuid import uuid4

from tools import (
    get_balance,
    add_funds,
    search_products,
    get_product,
    purchase,
    get_orders,
)

def dollars(cents: int) -> str:
    return f"${cents/100:.2f}"

def main():
    user_id = "u_1002"

    print("\n--- 1) Balance ---")
    b = get_balance(user_id)
    print("Balance:", dollars(b.balance_cents))

    print("\n--- 2) Search products (query='cable') ---")
    results = search_products("cable")
    for p in results.products[:5]:
        print(f"{p.product_id}: {p.name} | {dollars(p.price_cents)} | inv={p.inventory}")

    # pick one product
    product_id = results.products[0].product_id
    prod = get_product(product_id).product
    print("\nSelected:", prod.product_id, prod.name, dollars(prod.price_cents))

    print("\n--- 3) Try purchase (may fail if insufficient funds) ---")
    req_id = f"demo_purchase_{uuid4().hex}"
    try:
        out = purchase(user_id, product_id, quantity=2, client_request_id=req_id)
        print("Purchased:", out.order_id, "Total:", dollars(out.total_cents), "New balance:", dollars(out.new_balance_cents))
    except Exception as e:
        print("Purchase failed:", str(e))

        print("\n--- 4) Add funds then purchase ---")
        topup_id = f"demo_topup_{uuid4().hex}"
        topup = add_funds(user_id, amount_cents=5000, source="external", client_request_id=topup_id)
        print("Topup:", dollars(topup.added_cents), "New balance:", dollars(topup.new_balance_cents))

        out = purchase(user_id, product_id, quantity=2, client_request_id=req_id)
        print("Purchased:", out.order_id, "Total:", dollars(out.total_cents), "New balance:", dollars(out.new_balance_cents))

    print("\n--- 5) Orders ---")
    orders = get_orders(user_id, limit=5)
    for o in orders.orders:
        print(f"Order {o.order_id} | {o.status} | {o.created_at} | total {dollars(o.total_cents)}")
        for it in o.items:
            print(f"  - {it.name} x{it.quantity} @ {dollars(it.unit_price_cents)}")

    print("\n--- 6) Idempotency check (repeat same purchase request_id) ---")
    # repeat same req_id: should NOT double charge; should return same order
    out2 = purchase(user_id, product_id, quantity=2, client_request_id=req_id)
    print("Repeat purchase returned order:", out2.order_id, "New balance:", dollars(out2.new_balance_cents))

if __name__ == "__main__":
    main()
