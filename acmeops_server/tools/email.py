from __future__ import annotations

import uuid
from typing import Any

ALLOWED_RECIPIENT_DOMAINS: tuple[str, ...] = () 


def draft(to: str, subject: str, body: str) -> dict[str, str]:
    draft_id = uuid.uuid4().hex[:8]

    return {
        "draft_id": draft_id,
        "to": to,
        "subject": subject,
        "body_preview": body[:200],
        "status": "drafted",
    }
