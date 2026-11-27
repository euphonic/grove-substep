"""Supabase access-token verification.

Tokens are verified against the project's JWKS (asymmetric signing keys). If the project
still signs with a shared secret (HS256), SUPABASE_JWT_SECRET is used instead.
"""

import time
from typing import Annotated, Any

import httpx
import jwt
import jwt.types
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import Settings, get_settings

_bearer = HTTPBearer(auto_error=False)
_JWKS_TTL_SECONDS = 600
_jwks_cache: dict[str, tuple[float, jwt.PyJWKSet]] = {}


def fetch_jwks(supabase_url: str) -> jwt.PyJWKSet:
    cached = _jwks_cache.get(supabase_url)
    if cached and time.monotonic() - cached[0] < _JWKS_TTL_SECONDS:
        return cached[1]
    resp = httpx.get(f"{supabase_url}/auth/v1/.well-known/jwks.json", timeout=5)
    resp.raise_for_status()
    keyset = jwt.PyJWKSet.from_dict(resp.json())
    _jwks_cache[supabase_url] = (time.monotonic(), keyset)
    return keyset


def decode_token(token: str, settings: Settings) -> dict[str, Any]:
    header = jwt.get_unverified_header(token)
    alg = header.get("alg", "")
    options: jwt.types.Options = {"require": ["exp", "sub"]}
    if alg == "HS256":
        if not settings.supabase_jwt_secret:
            raise jwt.InvalidTokenError("HS256 token but SUPABASE_JWT_SECRET is not set")
        return jwt.decode(
            token,
            settings.supabase_jwt_secret,
            algorithms=["HS256"],
            audience="authenticated",
            options=options,
        )
    keyset = fetch_jwks(settings.supabase_url)
    kid = header.get("kid")
    matches = [k for k in keyset.keys if k.key_id == kid]
    if not matches:
        raise jwt.InvalidTokenError("unknown signing key")
    return jwt.decode(
        token,
        matches[0].key,
        algorithms=["RS256", "ES256"],
        audience="authenticated",
        options=options,
    )


def current_user_id(
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> str:
    if creds is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "missing bearer token")
    try:
        claims = decode_token(creds.credentials, settings)
    except (jwt.PyJWTError, httpx.HTTPError) as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid token") from exc
    return str(claims["sub"])
