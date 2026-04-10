"""
Unified Audit Trail for AURA.
Single cross-domain view of all significant operational events.

Domains: decision, risk, autopilot, simulation, strategy, profile, execution, system
Severity: info, warning, critical

This does NOT replace domain-specific tables — it normalizes a summary
of every significant event into one queryable timeline.

Usage:
    from services.audit_trail import emit_audit

    emit_audit(
        domain="decision",
        event_name="AI_DECISION_GENERATED",
        summary="BUY signal for BTC with 85% confidence",
        user_id=42,
        entity_type="ai_decision_event",
        entity_id=157,
        severity="info",
        payload={"symbol": "BTC", "action": "BUY", "confidence": 0.85},
    )
"""

import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

VALID_DOMAINS = {
    "decision", "risk", "autopilot", "simulation",
    "strategy", "profile", "execution", "system",
}

VALID_SEVERITIES = {"info", "warning", "critical"}


def emit_audit(
    domain: str,
    event_name: str,
    summary: str,
    user_id: Optional[int] = None,
    entity_type: Optional[str] = None,
    entity_id: Optional[int] = None,
    severity: str = "info",
    payload: Optional[dict] = None,
) -> Optional[int]:
    """
    Emit a unified audit event. Returns the row ID or None on failure.
    Fire-and-forget — failures are logged but never block the caller.
    """
    if domain not in VALID_DOMAINS:
        logger.warning(f"[audit] Unknown domain: {domain}")
    if severity not in VALID_SEVERITIES:
        severity = "info"

    try:
        from database.connection import SessionLocal
        from database.models import AuditEvent

        db = SessionLocal()
        row = AuditEvent(
            user_id=user_id,
            event_domain=domain,
            event_name=event_name,
            entity_type=entity_type,
            entity_id=entity_id,
            severity=severity,
            summary=summary[:500],
            payload_json=payload or {},
        )
        db.add(row)
        db.commit()
        row_id = row.id
        db.close()
        return row_id

    except Exception as e:
        logger.debug(f"[audit] Failed to emit (non-fatal): {e}")
        return None


def get_audit_trail(
    user_id: Optional[int] = None,
    domain: Optional[str] = None,
    severity: Optional[str] = None,
    entity_type: Optional[str] = None,
    entity_id: Optional[int] = None,
    limit: int = 50,
) -> List[Dict]:
    """Query the unified audit trail with optional filters."""
    try:
        from database.connection import SessionLocal
        from database.models import AuditEvent

        db = SessionLocal()
        query = db.query(AuditEvent)

        if user_id is not None:
            query = query.filter(AuditEvent.user_id == user_id)
        if domain:
            query = query.filter(AuditEvent.event_domain == domain)
        if severity:
            query = query.filter(AuditEvent.severity == severity)
        if entity_type:
            query = query.filter(AuditEvent.entity_type == entity_type)
            if entity_id is not None:
                query = query.filter(AuditEvent.entity_id == entity_id)

        rows = (
            query
            .order_by(AuditEvent.created_at.desc())
            .limit(min(limit, 500))
            .all()
        )
        db.close()

        return [
            {
                "id": r.id,
                "user_id": r.user_id,
                "event_domain": r.event_domain,
                "event_name": r.event_name,
                "entity_type": r.entity_type,
                "entity_id": r.entity_id,
                "severity": r.severity,
                "summary": r.summary,
                "payload": r.payload_json or {},
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]

    except Exception as e:
        logger.warning(f"[audit] Failed to query trail: {e}")
        return []


def get_audit_summary(
    user_id: Optional[int] = None,
) -> Dict:
    """Get aggregated audit event counts by domain and severity."""
    try:
        from database.connection import SessionLocal
        from database.models import AuditEvent
        from sqlalchemy import func

        db = SessionLocal()
        query = db.query(
            AuditEvent.event_domain,
            AuditEvent.severity,
            func.count(AuditEvent.id).label("count"),
        )
        if user_id is not None:
            query = query.filter(AuditEvent.user_id == user_id)

        rows = (
            query
            .group_by(AuditEvent.event_domain, AuditEvent.severity)
            .all()
        )
        db.close()

        by_domain = {}
        by_severity = {}
        total = 0
        for r in rows:
            by_domain[r.event_domain] = by_domain.get(r.event_domain, 0) + r.count
            by_severity[r.severity] = by_severity.get(r.severity, 0) + r.count
            total += r.count

        return {"total": total, "by_domain": by_domain, "by_severity": by_severity}

    except Exception as e:
        logger.warning(f"[audit] Failed to get summary: {e}")
        return {"total": 0, "by_domain": {}, "by_severity": {}}
