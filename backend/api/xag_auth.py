"""
api/xag_auth.py — Auth + rate-limit wiring for XAG endpoints.

Phase 7: JWT authentication on all /api/xag/* routes.

Dev bypass
----------
Set env vars  APP_ENV=development  AND  XAG_DEV_NO_AUTH=1  to skip JWT
checks without removing the Depends() from endpoint signatures.
Both env vars must be set simultaneously — XAG_DEV_NO_AUTH alone in a
non-development environment raises RuntimeError at import time.

When XAG_DEV_NO_AUTH=1 is active, XAG_DEV_USER_ID must also be set to a
positive integer. This value is used as the sub claim in the returned token
payload — matching the format real JWTs produce — so that endpoint helpers
such as _extract_user_id() work without modification. If XAG_DEV_USER_ID is
missing or non-integer, a RuntimeError is raised at startup to surface the
misconfiguration immediately rather than producing a silent 401 at runtime.

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

import os

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from slowapi import Limiter
from slowapi.util import get_remote_address

# ── Dev bypass ────────────────────────────────────────────────────────────────
# XAG_DEV_NO_AUTH=1 is allowed ONLY when APP_ENV=development.
# Any other combination raises a hard error at startup so the bypass can never
# silently leak into staging or production containers.

_APP_ENV: str = os.environ.get("APP_ENV", "production").strip().lower()
_DEV_NO_AUTH: bool = os.environ.get("XAG_DEV_NO_AUTH", "").strip().lower() in (
    "1", "true", "yes"
)

if _DEV_NO_AUTH and _APP_ENV != "development":
    raise RuntimeError(
        "XAG_DEV_NO_AUTH=1 is not allowed outside APP_ENV=development. "
        "Set APP_ENV=development explicitly, or unset XAG_DEV_NO_AUTH."
    )

# ── Dev user identity ─────────────────────────────────────────────────────────
# XAG_DEV_USER_ID must be a positive integer when XAG_DEV_NO_AUTH=1.
# It is used as the numeric sub claim so that _extract_user_id() works
# identically in dev and production modes.  A missing or invalid value is
# a startup error, not a silent runtime failure.

_DEV_USER_ID: int | None = None

if _DEV_NO_AUTH:
    _raw_dev_uid = os.environ.get("XAG_DEV_USER_ID", "").strip()
    try:
        _parsed = int(_raw_dev_uid)
        if _parsed <= 0:
            raise ValueError("must be positive")
        _DEV_USER_ID = _parsed
    except (TypeError, ValueError):
        raise RuntimeError(
            "XAG_DEV_USER_ID must be set to a positive integer when "
            "XAG_DEV_NO_AUTH=1. Example: XAG_DEV_USER_ID=9999"
        ) from None

    import warnings
    warnings.warn(
        f"[xag_auth] XAG_DEV_NO_AUTH=1 — JWT auth disabled on all XAG endpoints "
        f"(dev user_id={_DEV_USER_ID}). DO NOT use in production.",
        stacklevel=2,
    )

# ── Rate limiter ──────────────────────────────────────────────────────────────
# Shared slowapi Limiter instance.  The app-level limiter in main.py is for
# the rest of Aura; we keep a separate one so XAG limits can be tuned
# independently.  Key: remote IP address.

xag_limiter = Limiter(key_func=get_remote_address, default_limits=["60/minute"])

# ── JWT auth dependency ───────────────────────────────────────────────────────

_bearer = HTTPBearer(auto_error=False)


def xag_require_auth(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
):
    """
    FastAPI dependency that enforces JWT Bearer authentication.

    Use as:  Depends(xag_require_auth)

    Returns the decoded JWT payload (dict) on success.
    Raises HTTP 401 if the token is missing or invalid.
    Skipped entirely when XAG_DEV_NO_AUTH=1 AND APP_ENV=development.
    """
    if _DEV_NO_AUTH:
        return {"sub": str(_DEV_USER_ID), "email": "dev@local", "dev": True}

    if credentials is None:
        raise HTTPException(
            status_code=401,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        from auth.jwt_handler import verify_token
        return verify_token(credentials.credentials, "access")
    except Exception:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None
