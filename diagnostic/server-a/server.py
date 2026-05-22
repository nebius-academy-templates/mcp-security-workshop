"""tickets-status MCP server.

A small read-only MCP server that exposes one tool: get_ticket_status.
Used by the internal support team to look up ticket states from the
TicketsAPI service.

Authentication: corporate IdP issues per-user JWTs with aud=https://tickets.internal.
"""

from __future__ import annotations

import os
from typing import Any

import httpx
import jwt
from mcp.server.auth.provider import TokenVerifier
from mcp.server.auth.settings import AuthSettings
from mcp.server.fastmcp import FastMCP

TICKETS_BASE_URL = os.environ.get("TICKETS_BASE_URL", "https://tickets.internal")
TICKETS_API_AUDIENCE = "https://tickets.internal"
JWKS_URL = f"{TICKETS_BASE_URL}/.well-known/jwks.json"


class TicketsTokenVerifier(TokenVerifier):
    """Verifies JWTs issued by the corporate IdP for the tickets API."""

    def __init__(self) -> None:
        self._jwks_client = jwt.PyJWKClient(JWKS_URL)

    async def verify_token(self, token: str) -> dict[str, Any] | None:
        try:
            signing_key = self._jwks_client.get_signing_key_from_jwt(token).key
            claims = jwt.decode(
                token,
                signing_key,
                algorithms=["RS256"],
                audience=TICKETS_API_AUDIENCE,
                issuer="https://idp.acme.example",
            )
        except jwt.PyJWTError:
            return None
        return claims


async def _mint_service_token(user_sub: str) -> str:
    """Exchange the user's identity for a short-lived TicketsAPI service token.

    Calls the corporate IdP's token-exchange endpoint (RFC 8693). The returned
    token has aud=tickets-api and a sub bound to the original user.
    """
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{TICKETS_BASE_URL}/oauth/token",
            data={
                "grant_type": "urn:ietf:params:oauth:grant-type:token-exchange",
                "subject_token": user_sub,
                "audience": "tickets-api",
            },
            timeout=5.0,
        )
        resp.raise_for_status()
        return resp.json()["access_token"]


mcp = FastMCP(
    "tickets-status",
    auth=AuthSettings(
        issuer_url="https://idp.acme.example",
        resource_server_url="https://tickets.internal",
        required_scopes=["tickets:read"],
    ),
    token_verifier=TicketsTokenVerifier(),
)


@mcp.tool()
async def get_ticket_status(ticket_id: str, user_sub: str) -> str:
    """Return the current status of a ticket by ID."""
    service_token = await _mint_service_token(user_sub)
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{TICKETS_BASE_URL}/api/tickets/{ticket_id}/status",
            headers={"Authorization": f"Bearer {service_token}"},
            params={"include": "summary"},
            timeout=5.0,
        )
    resp.raise_for_status()
    body = resp.json()
    return (
        f'<tool-output source="tickets-api" ticket="{ticket_id}">\n'
        f'  status: {body["status"]}\n'
        f'  updated_at: {body["updated_at"]}\n'
        f'  summary: {body["summary"]}\n'
        f"</tool-output>"
    )


if __name__ == "__main__":
    mcp.run(transport="stdio")
