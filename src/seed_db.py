# src/seed_db.py
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from src.db import connect, init_db, DEFAULT_DB_PATH

def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def reset_db(db_path: Path) -> None:
    if db_path.exists():
        db_path.unlink()

def seed(db_path: Path = DEFAULT_DB_PATH) -> None:
    reset_db(db_path)
    conn = connect(db_path)
    init_db(conn)

    # --- USERS ---
    users = [
        ("u_1001", "Alex Chen"),
        ("u_1002", "Sam Rivera"),
        ("u_1003", "Taylor Okafor"),
    ]
    conn.executemany("INSERT INTO users(user_id, name) VALUES (?, ?)", users)

    # --- WALLETS (in cents) ---
    wallets = [
        ("u_1001", 2500),   # $25.00
        ("u_1002", 1200),   # $12.00
        ("u_1003", 5000),   # $50.00
    ]
    conn.executemany("INSERT INTO wallets(user_id, balance_cents) VALUES (?, ?)", wallets)

    # --- PRODUCTS ---
    products = [
        ("p_2001", "USB-C Cable (1m)", 899, 25),
        ("p_2002", "Wireless Mouse", 1999, 12),
        ("p_2003", "Mechanical Keyboard", 7499, 6),
        ("p_2004", "Laptop Stand", 2999, 10),
        ("p_2005", "Noise-Cancelling Earbuds", 12999, 4),
        ("p_2006", "Portable Charger 10,000mAh", 2499, 14),
        ("p_2007", "HDMI Adapter", 1599, 18),
        ("p_2008", "Notebook (pack of 3)", 999, 30),
        ("p_2009", "Water Bottle", 1499, 20),
        ("p_2010", "Desk Lamp", 3499, 8),
        ("p_2011", "Phone Stand", 1099, 22),
        ("p_2012", "Ethernet Cable (2m)", 699, 40),
        ("p_2013", "Backpack", 4599, 7),
        ("p_2014", "Earpods", 799, 35),
        ("p_2015", "Bluetooth Speaker", 5999, 5),
    ]
    conn.executemany(
        "INSERT INTO products(product_id, name, price_cents, inventory) VALUES (?, ?, ?, ?)",
        products
    )

    # --- OPTIONAL: seed 1 sample order for realism ---
    # (This does NOT define purchase logic yet; that's Milestone B/C)
    order_id = f"o_{uuid4().hex[:8]}"
    created_at = utc_now_iso()
    conn.execute(
        "INSERT INTO orders(order_id, user_id, created_at, status, total_cents) VALUES (?, ?, ?, ?, ?)",
        (order_id, "u_1001", created_at, "PLACED", 899)
    )
    conn.execute(
        "INSERT INTO order_items(order_id, product_id, quantity, unit_price_cents) VALUES (?, ?, ?, ?)",
        (order_id, "p_2001", 1, 899)
    )
    conn.commit()

    # Add a matching ledger entry (audit trail)
    tx_id = f"tx_{uuid4().hex}"
    conn.execute(
        "INSERT INTO ledger(tx_id, user_id, kind, amount_cents, created_at, client_request_id, metadata_json) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (tx_id, "u_1001", "PURCHASE", -899, created_at, f"seed_{uuid4().hex}", json.dumps({"order_id": order_id}))
    )
    conn.commit()

    conn.close()
    print(f"✅ Seeded DB at: {db_path}")

if __name__ == "__main__":
    seed()
