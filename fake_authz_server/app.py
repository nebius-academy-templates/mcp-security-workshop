from __future__ import annotations

import base64
import hashlib
import secrets
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import jwt
import uvicorn
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse, RedirectResponse
from starlette.routing import Route

KEYS_DIR = Path(__file__).resolve().parent / "keys"
ISSUER = "http://localhost:9000"
RESOURCE = "https://acmeops.internal"

# Loaded on startup
_PRIVATE_KEY: str = ""
_PUBLIC_JWK: dict[str, Any] = {}

_clients: dict[str, dict[str, Any]] = {}      # client_id -> metadata
_codes: dict[str, dict[str, Any]] = {}        # auth_code -> {client_id, code_challenge, scope, sub}


def _b64url(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode("ascii")


def _load_keys() -> None:
    global _PRIVATE_KEY, _PUBLIC_JWK
    KEYS_DIR.mkdir(exist_ok=True)
    priv = KEYS_DIR / "private.pem"
    pub = KEYS_DIR / "public.pem"
    if not priv.exists():
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        priv.write_bytes(
            key.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.PKCS8,
                serialization.NoEncryption(),
            )
        )
        pub.write_bytes(
            key.public_key().public_bytes(
                serialization.Encoding.PEM,
                serialization.PublicFormat.SubjectPublicKeyInfo,
            )
        )
    _PRIVATE_KEY = priv.read_text()

    from cryptography.hazmat.primitives import serialization
    pub_key = serialization.load_pem_public_key(pub.read_bytes())
    nums = pub_key.public_numbers()  # type: ignore[union-attr]
    _PUBLIC_JWK = {
        "kty": "RSA",
        "use": "sig",
        "alg": "RS256",
        "kid": "fake-authz-1",
        "n": _b64url(nums.n.to_bytes((nums.n.bit_length() + 7) // 8, "big")),
        "e": _b64url(nums.e.to_bytes((nums.e.bit_length() + 7) // 8, "big")),
    }


# --- Metadata endpoints ------------------------------------------------------
async def as_metadata(_: Request) -> JSONResponse:
    """RFC 8414 — Authorization Server Metadata."""
    return JSONResponse(
        {
            "issuer": ISSUER,
            "authorization_endpoint": f"{ISSUER}/authorize",
            "token_endpoint": f"{ISSUER}/token",
            "registration_endpoint": f"{ISSUER}/register",
            "jwks_uri": f"{ISSUER}/jwks.json",
            "response_types_supported": ["code"],
            "grant_types_supported": ["authorization_code"],
            "code_challenge_methods_supported": ["S256"],
            "token_endpoint_auth_methods_supported": ["none"],
            "scopes_supported": [
                "acme:tickets:read",
                "acme:emails:write",
                "acme:db:read",
                "acme:github:write",
            ],
        }
    )


async def resource_metadata(_: Request) -> JSONResponse:
    """RFC 9728 — Protected Resource Metadata.

    The MCP spec uses this to discover the AS from the resource server's URL.
    """
    return JSONResponse(
        {
            "resource": RESOURCE,
            "authorization_servers": [ISSUER],
            "bearer_methods_supported": ["header"],
            "scopes_supported": [
                "acme:tickets:read",
                "acme:emails:write",
                "acme:db:read",
                "acme:github:write",
            ],
        }
    )


async def jwks(_: Request) -> JSONResponse:
    return JSONResponse({"keys": [_PUBLIC_JWK]})


# --- Dynamic Client Registration (RFC 7591) ----------------------------------
async def register(request: Request) -> JSONResponse:
    body = await request.json()
    client_id = f"mcp-{uuid.uuid4().hex[:12]}"
    redirect_uris = body.get("redirect_uris") or []
    if not redirect_uris:
        return JSONResponse({"error": "invalid_redirect_uri"}, status_code=400)
    _clients[client_id] = {
        "client_id": client_id,
        "redirect_uris": redirect_uris,
        "client_name": body.get("client_name", "unknown"),
        "token_endpoint_auth_method": "none",  # public client, PKCE only
        "registered_at": int(time.time()),
    }
    return JSONResponse(_clients[client_id])


async def authorize(request: Request) -> RedirectResponse | PlainTextResponse:
    qp = request.query_params
    client_id = qp.get("client_id", "")
    redirect_uri = qp.get("redirect_uri", "")
    code_challenge = qp.get("code_challenge", "")
    code_method = qp.get("code_challenge_method", "")
    scope = qp.get("scope", "acme:tickets:read")
    state = qp.get("state", "")
    resource = qp.get("resource", RESOURCE)

    if client_id not in _clients:
        return PlainTextResponse("unknown client_id", status_code=400)
    if redirect_uri not in _clients[client_id]["redirect_uris"]:
        return PlainTextResponse("redirect_uri mismatch", status_code=400)
    if code_method != "S256":
        return PlainTextResponse("PKCE S256 required", status_code=400)
    if resource != RESOURCE:
        return PlainTextResponse("resource indicator mismatch", status_code=400)

    code = secrets.token_urlsafe(24)
    _codes[code] = {
        "client_id": client_id,
        "code_challenge": code_challenge,
        "scope": scope,
        "sub": f"user-{secrets.token_hex(4)}",  # workshop: anonymous fake user
        "expires_at": int(time.time()) + 60,
    }
    sep = "&" if "?" in redirect_uri else "?"
    return RedirectResponse(f"{redirect_uri}{sep}code={code}&state={state}")


async def token(request: Request) -> JSONResponse:
    form = await request.form()
    code = str(form.get("code", ""))
    verifier = str(form.get("code_verifier", ""))
    client_id = str(form.get("client_id", ""))

    record = _codes.pop(code, None)
    if not record or record["expires_at"] < time.time():
        return JSONResponse({"error": "invalid_grant"}, status_code=400)
    if record["client_id"] != client_id:
        return JSONResponse({"error": "invalid_client"}, status_code=400)

    expected = _b64url(hashlib.sha256(verifier.encode()).digest())
    if expected != record["code_challenge"]:
        return JSONResponse({"error": "invalid_grant"}, status_code=400)

    now = int(time.time())
    claims = {
        "iss": ISSUER,
        "aud": RESOURCE,        # Critical: aud is the MCP resource, not GitHub
        "sub": record["sub"],
        "scope": record["scope"],
        "iat": now,
        "exp": now + 600,       # 10-minute access tokens
        "client_id": client_id,
    }
    access_token = jwt.encode(
        claims,
        _PRIVATE_KEY,
        algorithm="RS256",
        headers={"kid": _PUBLIC_JWK["kid"]},
    )
    return JSONResponse(
        {
            "access_token": access_token,
            "token_type": "Bearer",
            "expires_in": 600,
            "scope": record["scope"],
        }
    )


@asynccontextmanager
async def _lifespan(app: Starlette):
    _load_keys()
    yield


def make_app() -> Starlette:
    return Starlette(
        routes=[
            Route("/.well-known/oauth-authorization-server", as_metadata),
            Route("/.well-known/oauth-protected-resource", resource_metadata),
            Route("/jwks.json", jwks),
            Route("/register", register, methods=["POST"]),
            Route("/authorize", authorize, methods=["GET"]),
            Route("/token", token, methods=["POST"]),
        ],
        lifespan=_lifespan,
    )


def main() -> None:
    uvicorn.run(make_app(), host="127.0.0.1", port=9000, log_level="info")


if __name__ == "__main__":
    main()
