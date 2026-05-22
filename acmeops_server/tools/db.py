from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "acmeops.db"


def _ensure_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS customers (id TEXT PRIMARY KEY, name TEXT, plan TEXT)"
    )
    conn.execute(
        "INSERT OR IGNORE INTO customers VALUES "
        "('CUST-1', 'Northwind Distribution', 'enterprise'),"
        "('CUST-42', 'Octans Logistics', 'standard'),"
        "('CUST-99', 'Vanguard Retail', 'standard')"
    )
    conn.commit()
    return conn


def query_customer(customer_id: str) -> list[dict[str, Any]]:
    conn = _ensure_db()
    cur = conn.execute(
        f"SELECT id, name, plan FROM customers WHERE id = '{customer_id}'"
    )
    cols = [c[0] for c in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]
