"""pr-helper MCP server.

Lets engineers ask their AI agent to summarize, review, and comment on
GitHub pull requests. Acts as an OAuth proxy in front of the GitHub API.

Tool descriptions live in tool_descriptions.yml so docs people can edit
them without code changes.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx
import jwt
import yaml
from mcp.server.auth.provider import TokenVerifier
from mcp.server.auth.settings import AuthSettings
from mcp.server.fastmcp import FastMCP

PR_HELPER_AUDIENCE = "https://pr-helper.acme.example"
GITHUB_OAUTH_CLIENT_ID = "pr-helper-mcp"
GITHUB_API = "https://api.github.com"

DESCRIPTIONS = yaml.safe_load(
    (Path(__file__).parent / "tool_descriptions.yml").read_text()
)


class PRHelperTokenVerifier(TokenVerifier):
    """Verifies inbound JWTs from MCP clients."""

    def __init__(self) -> None:
        self._jwks_client = jwt.PyJWKClient(
            "https://idp.acme.example/.well-known/jwks.json"
        )

    async def verify_token(self, token: str) -> dict[str, Any] | None:
        try:
            signing_key = self._jwks_client.get_signing_key_from_jwt(token).key
            claims = jwt.decode(
                token,
                signing_key,
                algorithms=["RS256"],
                issuer="https://idp.acme.example",
                options={"verify_aud": False},
            )
        except jwt.PyJWTError:
            return None
        return claims


mcp = FastMCP(
    "pr-helper",
    auth=AuthSettings(
        issuer_url="https://idp.acme.example",
        resource_server_url="https://pr-helper.acme.example",
        required_scopes=["pr:read"],
    ),
    token_verifier=PRHelperTokenVerifier(),
)


@mcp.tool(description=DESCRIPTIONS["summarize_pr"])
async def summarize_pr(owner: str, repo: str, pull_number: int, github_token: str) -> str:
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{GITHUB_API}/repos/{owner}/{repo}/pulls/{pull_number}",
            headers={"Authorization": f"Bearer {github_token}"},
            params={"include": "summary"},
            timeout=10.0,
        )
    resp.raise_for_status()
    body = resp.json()
    return f'<tool-output source="github" pr="{owner}/{repo}#{pull_number}">{body["body"]}</tool-output>'


@mcp.tool(description=DESCRIPTIONS["list_review_comments"])
async def list_review_comments(
    owner: str, repo: str, pull_number: int, github_token: str
) -> list[dict[str, Any]]:
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{GITHUB_API}/repos/{owner}/{repo}/pulls/{pull_number}/comments",
            headers={"Authorization": f"Bearer {github_token}"},
            timeout=10.0,
        )
    resp.raise_for_status()
    return [
        {"author": c["user"]["login"], "body": c["body"], "path": c["path"], "line": c["line"]}
        for c in resp.json()
    ]


@mcp.tool(description=DESCRIPTIONS["post_review_comment"])
async def post_review_comment(
    owner: str,
    repo: str,
    pull_number: int,
    path: str,
    line: int,
    body: str,
    github_token: str,
) -> dict[str, Any]:
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{GITHUB_API}/repos/{owner}/{repo}/pulls/{pull_number}/comments",
            headers={"Authorization": f"Bearer {github_token}"},
            json={"body": body, "path": path, "line": line, "side": "RIGHT"},
            timeout=10.0,
        )
    resp.raise_for_status()
    return {"id": resp.json()["id"], "url": resp.json()["html_url"]}


@mcp.custom_route("/oauth/start", methods=["GET"])
async def oauth_start(_request: Any) -> Any:
    from starlette.responses import RedirectResponse

    return RedirectResponse(
        f"https://github.com/login/oauth/authorize"
        f"?client_id={GITHUB_OAUTH_CLIENT_ID}"
        f"&scope=repo"
        f"&redirect_uri=https://pr-helper.acme.example/oauth/callback"
    )


if __name__ == "__main__":
    mcp.run(transport="stdio")
