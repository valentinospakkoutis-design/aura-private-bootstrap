from fastapi import HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

_bearer_scheme = HTTPBearer(auto_error=False)

def require_auth(credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme)):
    """Dependency that enforces JWT authentication on protected endpoints."""
    if not credentials:
        raise HTTPException(status_code=401, detail="Missing authorization token")
    try:
        from auth.jwt_handler import verify_token
        payload = verify_token(credentials.credentials, "access")
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return payload
