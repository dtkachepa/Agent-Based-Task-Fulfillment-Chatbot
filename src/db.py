# src/db.py
from __future__ import annotations
import sqlite3
from pathlib import Path
from typing import Iterable, Optional, Any, Dict

DEFAULT_DB_PATH = Path(__file__).resolve().parents[1] / "data" / "ecommerce.db"
SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"

def connect(db_path: Path = DEFAULT_DB_PATH) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def init_db(conn: sqlite3.Connection) -> None:
    schema = SCHEMA_PATH.read_text(encoding="utf-8")
    conn.executescript(schema)
    conn.commit()

def exec_one(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> Optional[Dict[str, Any]]:
    cur = conn.execute(sql, params)
    row = cur.fetchone()
    return dict(row) if row else None

def exec_many(conn: sqlite3.Connection, sql: str, params_list: Iterable[tuple]) -> None:
    conn.executemany(sql, params_list)
    conn.commit()

def exec_all(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> list[Dict[str, Any]]:
    cur = conn.execute(sql, params)
    return [dict(r) for r in cur.fetchall()]
