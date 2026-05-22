"""AcmeOps MCP server — INTENTIONALLY VULNERABLE for the security workshop.

Vulnerabilities seeded here (see THREATS.md for the answer key):
- MCP01 token mismanagement: GITHUB_PAT loaded from a checked-in .env
- MCP02 privilege escalation: every tool advertised under one broad scope
- MCP06 prompt injection: tool outputs are returned untagged
- MCP07 token passthrough: TokenVerifier accepts any signed JWT, no aud check
- MCP08 lack of audit: no per-call structured log

Do not use this code as a reference for anything in production.
"""

from __future__ import annotations

import argparse
import os
from typing import Any

import jwt as pyjwt
from dotenv import load_dotenv
from mcp.server.auth.provider import TokenVerifier
from mcp.server.fastmcp import FastMCP

from acmeops_server.tools import customers, db, email, github_proxy, tickets

load_dotenv()

# Workshop demo flag — set via --patched CLI arg (see main()).
# False = vulnerable state (MCP06 prompt injection fires untagged)
# True  = mitigated state (tool output wrapped in <untrusted-source>)
_PATCHED = False


# --- INTENTIONAL VULNERABILITY (MCP07): permissive TokenVerifier -------------
# This stub accepts any non-empty token as valid and ignores the audience
# claim. Workshop Block 2D replaces it with AcmeTokenVerifier below.
class PermissiveTokenVerifier(TokenVerifier):
    async def verify_token(self, token: str) -> dict[str, Any] | None:
        if not token:
            return None
        return {"sub": "unknown", "scopes": ["acme:admin"], "aud": "anything"}


# --- MCP07 FIX: audience-validating verifier --------------------------------
# Validates the RS256 signature against the IdP's JWKS, then enforces `aud`
# and `iss`. Rejects any token not explicitly issued for this resource.
class AcmeTokenVerifier(TokenVerifier):
    """Audience-validating verifier — the MCP07 fix."""

    def __init__(
        self,
        jwks_url: str,
        expected_audience: str,
        expected_issuer: str,
    ) -> None:
        self._jwks_url = jwks_url
        self._expected_aud = expected_audience
        self._expected_iss = expected_issuer

    async def verify_token(self, token: str) -> dict[str, Any] | None:
        if not token:
            return None
        try:
            client = pyjwt.PyJWKClient(self._jwks_url)
            signing_key = client.get_signing_key_from_jwt(token).key
            return pyjwt.decode(
                token,
                signing_key,
                algorithms=["RS256"],
                audience=self._expected_aud,
                issuer=self._expected_iss,
            )
        except Exception:
            return None


# --- FastMCP construction ---------------------------------------------------
# Default: no auth wired in locally in stdio
mcp = FastMCP("acmeops")

# --- (uncomment to enable audience-checked auth on streamable-http)
# Comment out the bare `mcp = FastMCP("acmeops")` line above and uncomment
# this block. Required for any real HTTP / multi-user deployment.
#
# from mcp.server.auth.settings import AuthSettings
# mcp = FastMCP(
#     "acmeops",
#     auth=AuthSettings(
#         issuer_url="http://localhost:9000",
#         resource_server_url="https://acmeops.internal",
#         required_scopes=["acme:tickets:read"],
#     ),
#     token_verifier=AcmeTokenVerifier(
#         jwks_url="http://localhost:9000/jwks.json",
#         expected_audience="https://acmeops.internal",
#         expected_issuer="http://localhost:9000",
#     ),
# )


# --- Tool registration -------------------------------------------------------
@mcp.tool()
def search_tickets(query: str) -> list[dict[str, Any]]:
    """Search internal tickets by free-text query."""
    return tickets.search(query)


@mcp.tool()
def read_customer_note(customer_id: str) -> str:
    """Read the support note for a customer.

    NOTE: returns the raw note content. The workshop patches this to wrap the
    content in <untrusted-source> tags so the LLM can distinguish trusted
    instructions from untrusted retrieved content.
    """
    content = customers.read_note(customer_id)
    if _PATCHED:
        return f"<untrusted-source>\n{content}\n</untrusted-source>"
    return content


@mcp.tool()
def draft_email(to: str, subject: str, body: str) -> dict[str, str]:
    """Draft an email. (Does not send; returns a draft id.)

    INTENTIONAL VULNERABILITY (MCP06): no recipient allowlist. The workshop
    patches this to reject `to` values outside the corporate / partner domains.
    """
    return email.draft(to=to, subject=subject, body=body)


@mcp.tool()
def run_db_query(customer_id: str) -> list[dict[str, Any]]:
    """Run a parameterized lookup for a customer in the local DB.

    INTENTIONAL VULNERABILITY (MCP05): the implementation interpolates the
    customer_id into a SQL string. Workshop patch is parameterization.
    """
    return db.query_customer(customer_id)


@mcp.tool()
def github_create_issue(repo: str, title: str, body: str) -> dict[str, Any]:
    """Open a GitHub issue in the named repo.

    INTENTIONAL VULNERABILITY (MCP01 + MCP07): forwards a shared PAT loaded
    from .env, with no per-user attribution and no audience validation on the
    inbound MCP token. Workshop replaces this with a per-user token mint flow.
    """
    pat = os.environ.get("GITHUB_PAT", "")
    return github_proxy.create_issue(repo=repo, title=title, body=body, pat=pat)


def main() -> None:
    global _PATCHED
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--transport",
        choices=("stdio", "streamable-http"),
        default="stdio",
        help="MCP transport. Use stdio for local/Claude Code; "
        "streamable-http for the auth block.",
    )
    parser.add_argument(
        "--patched",
        action="store_true",
        help="Enable MCP06 mitigation: wrap read_customer_note output in "
        "<untrusted-source> tags.",
    )
    args = parser.parse_args()
    _PATCHED = args.patched

    # INTENTIONAL VULNERABILITY (MCP08): no audit logging configured.
    mcp.run(transport=args.transport)


if __name__ == "__main__":
    main()
