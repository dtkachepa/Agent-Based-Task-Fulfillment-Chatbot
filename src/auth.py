
from __future__ import annotations

from typing import Optional
from src.db import connect, DEFAULT_DB_PATH

def user_exists(user_id: str) -> bool:
    conn = connect(DEFAULT_DB_PATH)
    try:
        row = conn.execute("SELECT 1 FROM users WHERE user_id = ?", (user_id,)).fetchone()
        return row is not None
    finally:
        conn.close()

def get_user_name(user_id: str) -> Optional[str]:
    conn = connect(DEFAULT_DB_PATH)
    try:
        row = conn.execute("SELECT name FROM users WHERE user_id = ?", (user_id,)).fetchone()
        if row is None:
            return None
        return row["name"]
    finally:
        conn.close()

