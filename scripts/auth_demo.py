"""Token-verifier failure demo for workshop Block 2D.

Mints three test JWTs locally (no HTTP token endpoint needed — we read
fake_authz_server's private key off disk) and runs each through both
verifier classes defined in `acmeops_server.server`:

  - PermissiveTokenVerifier (the intentional MCP07 vulnerability)
  - AcmeTokenVerifier       (the MCP07 fix)

Prints a 2x3 result matrix. The punchline: the permissive verifier accepts
a JWT minted for `https://attacker.example` and hands back
`scopes=[acme:admin]`. Every tool on the server would run as admin for
that token holder. The audience-checking verifier rejects it.

Requires `fake_authz_server` to be running ONLY for AcmeTokenVerifier
(which fetches JWKS at http://localhost:9000/jwks.json). If JWKS fetch
fails, the script prints a hint and continues with PermissiveTokenVerifier
results only.

Run from repo root:
    uv run python scripts/auth_demo.py
"""

from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path
from typing import Any

import jwt as pyjwt

from acmeops_server.server import AcmeTokenVerifier, PermissiveTokenVerifier

REPO_ROOT = Path(__file__).resolve().parent.parent
PRIVATE_KEY_PATH = REPO_ROOT / "fake_authz_server" / "keys" / "private.pem"

ISSUER = "http://localhost:9000"
JWKS_URL = "http://localhost:9000/jwks.json"
EXPECTED_AUD = "https://acmeops.internal"
ATTACKER_AUD = "https://attacker.example"
KID = "fake-authz-1"


def _load_private_key() -> str:
    if not PRIVATE_KEY_PATH.exists():
        print(
            f"[fatal] private key not found at {PRIVATE_KEY_PATH}\n"
            "        Start fake_authz_server once to generate it:\n"
            "            uv run python -m fake_authz_server",
            file=sys.stderr,
        )
        sys.exit(1)
    return PRIVATE_KEY_PATH.read_text()


def _mint(private_key: str, *, aud: str, sub: str, scope: str) -> str:
    """Mint an RS256 JWT with the given audience/subject/scope."""
    now = int(time.time())
    claims = {
        "iss": ISSUER,
        "aud": aud,
        "sub": sub,
        "scope": scope,
        "iat": now,
        "exp": now + 600,
        "client_id": "auth-demo-script",
    }
    return pyjwt.encode(
        claims,
        private_key,
        algorithm="RS256",
        headers={"kid": KID},
    )


def _format_result(claims: dict[str, Any] | None) -> str:
    if claims is None:
        return "REJECT"
    scopes = claims.get("scopes") or claims.get("scope") or "<no scope>"
    if isinstance(scopes, list):
        scopes = ",".join(scopes)
    return f"ACCEPT [{scopes}]"


async def _verify(verifier: Any, token: str) -> dict[str, Any] | None:
    try:
        return await verifier.verify_token(token)
    except Exception as exc:  # defensive — verifiers should not raise
        return {"_error": repr(exc)}


def _hr(width: int = 78) -> str:
    return "-" * width


async def main() -> None:
    private_key = _load_private_key()

    tokens: dict[str, str] = {
        "empty": "",
        "wrong-aud": _mint(
            private_key,
            aud=ATTACKER_AUD,
            sub="evil@attacker",
            scope="acme:tickets:read",
        ),
        "right-aud": _mint(
            private_key,
            aud=EXPECTED_AUD,
            sub="user-test",
            scope="acme:tickets:read",
        ),
    }

    permissive = PermissiveTokenVerifier()
    audience_checked = AcmeTokenVerifier(
        jwks_url=JWKS_URL,
        expected_audience=EXPECTED_AUD,
        expected_issuer=ISSUER,
    )

    print()
    print("Minted three test JWTs:")
    print(f"  empty     : (no credentials at all)")
    print(f"  wrong-aud : aud={ATTACKER_AUD!r}  sub='evil@attacker'")
    print(f"  right-aud : aud={EXPECTED_AUD!r}  sub='user-test'")
    print()
    print("Both are signed with fake_authz_server's RS256 key (kid={!r}).".format(KID))
    print()

    # Probe JWKS reachability up-front so we can give a friendly hint.
    jwks_ok = True
    try:
        probe = await audience_checked.verify_token(tokens["right-aud"])
        if probe is None:
            jwks_ok = False
    except Exception:
        jwks_ok = False
    if not jwks_ok:
        print(
            "[hint] AcmeTokenVerifier could not reach the JWKS endpoint at\n"
            f"       {JWKS_URL}\n"
            "       Did you start fake_authz_server in another terminal?\n"
            "           uv run python -m fake_authz_server\n"
            "       Continuing — PermissiveTokenVerifier results are still valid.\n"
        )

    results: dict[str, dict[str, dict[str, Any] | None]] = {
        "PermissiveTokenVerifier": {},
        "AcmeTokenVerifier": {},
    }
    for label, token in tokens.items():
        results["PermissiveTokenVerifier"][label] = await _verify(permissive, token)
        results["AcmeTokenVerifier"][label] = await _verify(audience_checked, token)

    # --- Render the 2x3 matrix ----------------------------------------------
    col_w = 22
    header = (
        f"{'Verifier':<24} | {'empty':<{col_w}} | "
        f"{'wrong-aud':<{col_w}} | {'right-aud':<{col_w}}"
    )
    sep = (
        f"{'-' * 24}-+-{'-' * col_w}-+-{'-' * col_w}-+-{'-' * col_w}"
    )
    print(header)
    print(sep)
    for verifier_name, row in results.items():
        cells = [_format_result(row[label]) for label in ("empty", "wrong-aud", "right-aud")]
        print(
            f"{verifier_name:<24} | "
            f"{cells[0]:<{col_w}} | {cells[1]:<{col_w}} | {cells[2]:<{col_w}}"
        )
    print()

    # --- Detail block: show what each ACCEPT actually returned --------------
    print("Decoded claims for every ACCEPT:")
    print(_hr())
    any_accept = False
    for verifier_name, row in results.items():
        for label, claims in row.items():
            if claims is None:
                continue
            if isinstance(claims, dict) and "_error" in claims:
                continue
            any_accept = True
            print(f"{verifier_name} / {label}:")
            for k in ("sub", "aud", "scope", "scopes", "iss", "client_id", "exp"):
                if k in claims:
                    print(f"    {k:>10} = {claims[k]!r}")
            print()
    if not any_accept:
        print("  (no tokens were accepted — check JWKS reachability)")
    print(_hr())
    print()

    # --- Punchline ----------------------------------------------------------
    permissive_wrong = results["PermissiveTokenVerifier"]["wrong-aud"]
    print("Punchline")
    print(_hr())
    if permissive_wrong is not None:
        scopes = permissive_wrong.get("scopes") or permissive_wrong.get("scope")
        print(
            "PermissiveTokenVerifier accepted a JWT whose audience claim is\n"
            f"  aud={ATTACKER_AUD!r}\n"
            f"and handed back scopes={scopes!r}.\n"
            "Every tool on this server would execute as admin for that token holder,\n"
            "even though the token was minted for a completely different service.\n"
        )
    else:
        print(
            "(unexpected — PermissiveTokenVerifier should accept any non-empty token)\n"
        )
    if jwks_ok:
        print(
            "AcmeTokenVerifier rejected the same token because the `aud` claim did\n"
            f"not equal {EXPECTED_AUD!r}. This is the MCP07 fix.\n"
        )
    else:
        print(
            "Start fake_authz_server and re-run to see AcmeTokenVerifier reject\n"
            "the wrong-audience token while still accepting the right-audience one.\n"
        )


if __name__ == "__main__":
    asyncio.run(main())
