from __future__ import annotations

import sys
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data" / "customers"


def read_note(customer_id: str) -> str:
    path = DATA / f"{customer_id}.md"
    if not path.exists():
        return f"(No note found for {customer_id})"
    content = path.read_text()
    print(content, file=sys.stderr, flush=True)
    return content
