# src/audit_cli.py
from __future__ import annotations
import argparse
from src.audit import audit_user

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--user_id", required=True)
    p.add_argument("--ledger", type=int, default=20)
    p.add_argument("--orders", type=int, default=10)
    args = p.parse_args()

    print(audit_user(args.user_id, limit_ledger=args.ledger, limit_orders=args.orders))

if __name__ == "__main__":
    main()
