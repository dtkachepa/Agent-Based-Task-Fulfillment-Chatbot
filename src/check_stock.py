from __future__ import annotations
from src.db import connect, DEFAULT_DB_PATH

def main():
    conn = connect(DEFAULT_DB_PATH)
    try:
        rows = conn.execute(
            "SELECT product_id, name, price_cents, inventory FROM products ORDER BY name ASC"
        ).fetchall()

        print("\n--- PRODUCT CATALOG (source of truth) ---")
        for r in rows:
            print(f"{r['product_id']} | {r['name']} | ${r['price_cents']/100:.2f} | inv={r['inventory']}")

    finally:
        conn.close()

if __name__ == "__main__":
    main()