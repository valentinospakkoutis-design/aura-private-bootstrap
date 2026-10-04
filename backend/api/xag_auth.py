"""
api/xag_auth.py — Auth + rate-limit wiring for XAG endpoints.

Phase 7: JWT authentication on all /api/xag/* routes.

Dev bypass
----------
Set env var  XAG_DEV_NO_AUTH=1  to skip JWT checks without removing the
Depends() from endpoint signatures.  This is the ONLY way to disable auth;
never ship without confirming the env var is unset in production.

Usage in routers
----------------
    from fastapi import Depends
    from api.xag_auth import xag_require_auth, xag_limiter

    @router.get("/my_endpoint", dependencies=[Depends(xag_require_auth)])
    @xag_limiter.limit("60/minute")
    def my_endpoint(request: Request): ...

The limiter requires `request: Request` as the FIRST positional argument in
every decorated endpoint function (slowapi requirement).
"""

from __future__ import annotations

import os

from fastapi import HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from slowapi import Limiter
from slowapi.util import get_remote_address

# ── Dev bypass ────────────────────────────────────────────────────────────────

_DEV_NO_AUTH: bool = os.environ.get("XAG_DEV_NO_AUTH", "").strip() in ("1", "true", "yes")

if _DEV_NO_AUTH:
    import warnings
    warnings.warn(
        "[xag_auth] XAG_DEV_NO_AUTH=1 — JWT auth disabled on all XAG endpoints. "
        "DO NOT use in production.",
        stacklevel=2,
    )

# ── Rate limiter ──────────────────────────────────────────────────────────────
# Shared slowapi Limiter instance.  The app-level limiter in main.py is for
# the rest of Aura; we keep a separate one so XAG limits can be tuned
# independently.  Key: remote IP address.

xag_limiter = Limiter(key_func=get_remote_address, default_limits=["200/minute"])

# ── JWT auth dependency ───────────────────────────────────────────────────────

_bearer = HTTPBearer(auto_error=False)


def xag_require_auth(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = None,  # type: ignore[assignment]
):
    """
    FastAPI dependency that enforces JWT Bearer authentication.

    Use as:  Depends(xag_require_auth)

    Returns the decoded JWT payload (dict) on success.
    Raises HTTP 401 if the token is missing or invalid.
    Skipped entirely when XAG_DEV_NO_AUTH=1.
    """
    if _DEV_NO_AUTH:
        return {"sub": "dev", "email": "dev@local", "dev": True}

    # Extract Bearer token
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")

    token = auth_header.removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(status_code=401, detail="Empty bearer token")

    try:
        from auth.jwt_handler import verify_token
        payload = verify_token(token, "access")
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired JWT token")

    return payload
