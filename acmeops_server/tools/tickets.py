"""Tickets tool — fixture-backed search."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

DATA = Path(__file__).resolve().parent.parent / "data" / "tickets.jsonl"


def _load() -> list[dict[str, Any]]:
    if not DATA.exists():
        return []
    with DATA.open() as f:
        return [json.loads(line) for line in f if line.strip()]


def search(query: str) -> list[dict[str, Any]]:
    q = query.lower()
    return [t for t in _load() if q in t.get("title", "").lower() or q in t.get("body", "").lower()]
