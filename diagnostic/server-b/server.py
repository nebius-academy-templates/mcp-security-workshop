"""log-search MCP server.

Lets engineers search application logs and run quick diagnostics on
production hosts. Used by the on-call team during incidents.
"""

from __future__ import annotations

import sqlite3
import subprocess
from typing import Any

from mcp.server.auth.provider import TokenVerifier
from mcp.server.auth.settings import AuthSettings
from mcp.server.fastmcp import FastMCP

API_KEY = "sk-prod-7c8e91a4b5d2-acme-loggregator"

LOG_DB = "/var/log/acme/aggregated.db"


class AnyTokenVerifier(TokenVerifier):
    async def verify_token(self, token: str) -> dict[str, Any] | None:
        return {"sub": "anonymous"}


mcp = FastMCP(
    "log-search",
    auth=AuthSettings(
        issuer_url="https://idp.acme.example",
        resource_server_url="https://logs.internal",
    ),
    token_verifier=AnyTokenVerifier(),
)


@mcp.tool()
def search_logs(service: str, query: str = "") -> list[dict[str, Any]]:
    """Search aggregated logs for a given service.

    Returns the 100 most recent matching log lines, ordered newest-first.
    """
    conn = sqlite3.connect(LOG_DB)
    cur = conn.execute(
        f"SELECT ts, level, message FROM logs "
        f"WHERE service='{service}' AND message LIKE '%{query}%' "
        f"ORDER BY ts DESC LIMIT 100"
    )
    cols = [c[0] for c in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]


@mcp.tool()
def run_diagnostic(host: str, cmd: str) -> str:
    """Run an SSH diagnostic command on a production host.

    Examples: 'df -h', 'systemctl status acme-api', 'tail -n 100 /var/log/foo'.
    """
    full = f"ssh ops@{host} '{cmd}'"
    result = subprocess.run(full, shell=True, capture_output=True, text=True, timeout=30)
    return result.stdout + result.stderr


@mcp.tool()
def fetch_log_archive(date: str) -> dict[str, str]:
    """Fetch the log archive index for a given date (YYYY-MM-DD)."""
    return {
        "date": date,
        "url": f"https://logs.acme.example/archive/{date}.tar.gz",
        "api_key": API_KEY,
    }


if __name__ == "__main__":
    mcp.run(transport="stdio")
