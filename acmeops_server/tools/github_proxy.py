from __future__ import annotations

from typing import Any


def create_issue(repo: str, title: str, body: str, pat: str) -> dict[str, Any]:
    if not pat:
        return {"error": "no PAT configured", "hint": "set GITHUB_PAT in .env"}

    return {
        "ok": True,
        "repo": repo,
        "title": title,
        "issue_url": f"https://github.com/{repo}/issues/SIMULATED",
        "credential_used": f"PAT(prefix={pat[:8]}...)",
        "_workshop_note": (
            "This response leaks a credential prefix in the audit log. "
            "Workshop patch: never echo credential material."
        ),
    }
