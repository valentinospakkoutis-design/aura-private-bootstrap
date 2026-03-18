"""
Authentication and authorization dependencies.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, Set

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from auth.jwt_handler import get_user_from_token
from utils.error_handler import AuthenticationError

bearer_scheme = HTTPBearer(auto_error=False)


def _extract_roles(user_info: Dict[str, Any]) -> Set[str]:
    roles = user_info.get("roles") or []
    if isinstance(roles, str):
        roles = [roles]
    normalized = {str(role).strip().lower() for role in roles if str(role).strip()}
    if not normalized:
        # Default least-privilege role for authenticated users.
        normalized = {"viewer"}
    return normalized


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)) -> Dict[str, Any]:
    """Validate Bearer token and return user context."""
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "AUTH_REQUIRED", "message": "Bearer token required"},
        )

    token = credentials.credentials
    try:
        user_info = get_user_from_token(token)
    except AuthenticationError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "INVALID_TOKEN", "message": str(exc)},
        )

    if not user_info.get("email"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "INVALID_TOKEN", "message": "Token missing subject/email"},
        )

    user_info["roles"] = sorted(_extract_roles(user_info))
    return user_info


def require_roles(*allowed_roles: str):
    allowed = {role.strip().lower() for role in allowed_roles if role.strip()}

    def _dependency(user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
        user_roles = _extract_roles(user)
        if not user_roles.intersection(allowed):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": "FORBIDDEN",
                    "message": f"Requires one of roles: {sorted(allowed)}",
                },
            )
        user["roles"] = sorted(user_roles)
        return user

    return _dependency


def get_request_origin(request: Request) -> str:
    client = request.client.host if request.client else "unknown"
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return f"{client} ({forwarded_for})"
    return client
