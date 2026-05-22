"""Tier 3 starter scaffold — your MCP server.

PLUMBING IS DONE. You don't need to wire FastMCP from scratch.

Your job in the Build phase (~32 min):
  1. Pick 2-3 vulnerabilities from VULNERABILITY_MENU.md
  2. Insert them anywhere in this file (or new files in this folder)
  3. Fill in THREAT_BRIEF_TEMPLATE.md so your partner has something to attack

Your partner will:
  - read this server (and your threat brief)
  - try to exploit your vulnerabilities (Red-team phase, ~20 min)
  - hand back what they found

Then you:
  - patch what they found (Patch phase, ~12 min)

Two sample tools (echo, read_note) are wired below so you can focus on
adding interesting behavior, not framework setup.

Run:
  uv run python server.py
"""

from __future__ import annotations

from pathlib import Path

from mcp.server.fastmcp import FastMCP

DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)


# OPTIONAL AUTH — uncomment below (and add auth=AuthSettings(...)) to FastMCP if
# you want to implement a token-verification vulnerability.
#
# from mcp.server.auth.provider import TokenVerifier
# from typing import Any
#
# class StubTokenVerifier(TokenVerifier):
#     """Replace this if your threat model says you should."""
#
#     async def verify_token(self, token: str) -> dict[str, Any] | None:
#         if not token:
#             return None
#         return {"sub": "demo-user", "scopes": ["all"]}

# with auth
# mcp = FastMCP(
#     "tier3-server",
#     token_verifier=StubTokenVerifier(),
# )

mcp = FastMCP("tier3-server")


@mcp.tool()
def echo(text: str) -> str:
    """Echo a string back. Useful for testing the connection."""
    return text


@mcp.tool()
def read_note(name: str) -> str:
    """Read a note file from the data directory."""
    path = DATA_DIR / f"{name}.md"
    if not path.exists():
        return f"(no note named {name!r})"
    return path.read_text()


# ----------------------------------------------------------------------
# YOUR VULNERABILITIES GO HERE
#
# Add tools, change the TokenVerifier, modify the existing tools, do
# whatever you want. Pick 2-3 entries from VULNERABILITY_MENU.md.
#
# Keep the scope reasonable: this is a 32-minute build. A few targeted
# bugs your partner can actually find > a sprawling mess of half-bugs.
# ----------------------------------------------------------------------


if __name__ == "__main__":
    mcp.run(transport="stdio")
