"""
Auth Audit Logging — records sensitive account operations.
Gated behind ENABLE_AUTH_AUDIT_LOGGING flag.

Never logs: passwords, raw JWTs, OTP secrets, password hashes.
"""

import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


def log_auth_event(
    event_type: str,
    event_status: str,
    user_id: Optional[int] = None,
    email: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    metadata: Optional[dict] = None,
):
    """Log an authentication event. Safe — never includes secrets."""
    from config.feature_flags import ENABLE_AUTH_AUDIT_LOGGING
    if not ENABLE_AUTH_AUDIT_LOGGING:
        return

    safe_meta = {}
    if metadata:
        # Strip any accidentally included sensitive fields
        for k, v in metadata.items():
            if k.lower() not in ("password", "hash", "secret", "token", "jwt", "otp"):
                safe_meta[k] = v

    log_entry = {
        "event": event_type,
        "status": event_status,
        "user_id": user_id,
        "email": email,
        "ip": ip_address,
        "ua": user_agent[:100] if user_agent else None,
        "meta": safe_meta or None,
        "ts": datetime.utcnow().isoformat(),
    }

    logger.info(f"[AUTH_AUDIT] {log_entry}")

    # Persist to DB if available
    try:
        from database.connection import SessionLocal
        db = SessionLocal()
        if db:
            from sqlalchemy import text
            db.execute(text(
                "INSERT INTO auth_audit_logs (user_id, event_type, event_status, ip_address, user_agent, metadata, created_at) "
                "VALUES (:uid, :etype, :estatus, :ip, :ua, :meta::jsonb, NOW())"
            ), {
                "uid": user_id,
                "etype": event_type,
                "estatus": event_status,
                "ip": ip_address,
                "ua": user_agent[:200] if user_agent else None,
                "meta": __import__("json").dumps(safe_meta) if safe_meta else None,
            })
            db.commit()
            db.close()
    except Exception as e:
        logger.debug(f"[AUTH_AUDIT] DB persist failed (non-fatal): {e}")
