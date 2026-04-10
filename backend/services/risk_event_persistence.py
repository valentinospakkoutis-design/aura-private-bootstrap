"""
Risk Event Persistence Service for AURA.
Stores all meaningful risk interventions to the persistent_risk_events table:
  - blocked trades
  - reduced trade sizes
  - exposure cap hits
  - volatility / drawdown throttles
  - portfolio concentration warnings
  - risk pauses

All rows are append-only (immutable audit trail).
"""

import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# ── Valid enum values ─────────────────────────────────────────
VALID_EVENT_TYPES = {
    "blocked_trade",
    "size_reduced",
    "exposure_warning",
    "drawdown_throttle",
    "volatility_throttle",
    "risk_pause",
}

VALID_SEVERITIES = {"info", "warning", "critical"}


def emit_risk_event(
    event_type: str,
    reason_code: str,
    summary: str,
    user_id: Optional[int] = None,
    symbol: Optional[str] = None,
    related_decision_event_id: Optional[int] = None,
    severity: str = "warning",
    details: Optional[dict] = None,
    original_requested_notional: Optional[float] = None,
    adjusted_notional: Optional[float] = None,
    original_requested_quantity: Optional[float] = None,
    adjusted_quantity: Optional[float] = None,
    portfolio_risk_score: Optional[float] = None,
) -> Optional[int]:
    """
    Persist a risk event. Returns the new row ID or None on failure.

    Args:
        event_type: one of VALID_EVENT_TYPES
        reason_code: machine-readable code (e.g. RISK_BLOCK, SIZE_REDUCED_BY_VOLATILITY)
        summary: human-readable one-liner
        user_id: optional user context
        symbol: optional trading symbol
        related_decision_event_id: optional FK to ai_decision_events
        severity: info / warning / critical
        details: optional JSON payload with extra context
        original_requested_notional: what was originally requested ($)
        adjusted_notional: what was actually allowed ($)
        original_requested_quantity: original quantity
        adjusted_quantity: adjusted quantity
        portfolio_risk_score: portfolio risk score at time of event
    """
    if event_type not in VALID_EVENT_TYPES:
        logger.warning(f"[risk_persistence] Unknown event_type: {event_type}")
    if severity not in VALID_SEVERITIES:
        severity = "warning"

    try:
        from database.connection import SessionLocal
        from database.models import PersistentRiskEvent

        db = SessionLocal()
        row = PersistentRiskEvent(
            user_id=user_id,
            symbol=symbol.upper() if symbol else None,
            related_decision_event_id=related_decision_event_id,
            event_type=event_type,
            severity=severity,
            reason_code=reason_code,
            summary=summary,
            details_json=details or {},
            original_requested_notional=original_requested_notional,
            adjusted_notional=adjusted_notional,
            original_requested_quantity=original_requested_quantity,
            adjusted_quantity=adjusted_quantity,
            portfolio_risk_score=portfolio_risk_score,
        )
        db.add(row)
        db.commit()
        row_id = row.id
        db.close()

        logger.info(
            f"[risk_persistence] {event_type} | {severity} | {symbol or '-'} | "
            f"{reason_code} | {summary[:80]}"
        )

        try:
            from services.audit_trail import emit_audit
            emit_audit(
                domain="risk",
                event_name=f"RISK_{event_type.upper()}",
                summary=summary[:200],
                user_id=user_id,
                entity_type="persistent_risk_event",
                entity_id=row_id,
                severity=severity,
                payload={"symbol": symbol, "event_type": event_type,
                         "reason_code": reason_code},
            )
        except Exception:
            pass

        return row_id

    except Exception as e:
        logger.error(f"[risk_persistence] Failed to save risk event: {e}")
        return None


def get_risk_event_history(
    user_id: Optional[int] = None,
    symbol: Optional[str] = None,
    event_type: Optional[str] = None,
    severity: Optional[str] = None,
    limit: int = 50,
) -> List[Dict]:
    """
    Query risk event history with optional filters.
    Returns most recent events first.
    """
    try:
        from database.connection import SessionLocal
        from database.models import PersistentRiskEvent

        db = SessionLocal()
        query = db.query(PersistentRiskEvent)

        if user_id is not None:
            query = query.filter(PersistentRiskEvent.user_id == user_id)
        if symbol:
            query = query.filter(PersistentRiskEvent.symbol == symbol.upper())
        if event_type:
            query = query.filter(PersistentRiskEvent.event_type == event_type)
        if severity:
            query = query.filter(PersistentRiskEvent.severity == severity)

        rows = (
            query
            .order_by(PersistentRiskEvent.created_at.desc())
            .limit(min(limit, 200))
            .all()
        )

        db.close()

        return [
            {
                "id": r.id,
                "user_id": r.user_id,
                "symbol": r.symbol,
                "related_decision_event_id": r.related_decision_event_id,
                "event_type": r.event_type,
                "severity": r.severity,
                "reason_code": r.reason_code,
                "summary": r.summary,
                "details": r.details_json or {},
                "original_requested_notional": float(r.original_requested_notional) if r.original_requested_notional is not None else None,
                "adjusted_notional": float(r.adjusted_notional) if r.adjusted_notional is not None else None,
                "original_requested_quantity": float(r.original_requested_quantity) if r.original_requested_quantity is not None else None,
                "adjusted_quantity": float(r.adjusted_quantity) if r.adjusted_quantity is not None else None,
                "portfolio_risk_score": r.portfolio_risk_score,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]

    except Exception as e:
        logger.warning(f"[risk_persistence] Failed to load history: {e}")
        return []


def get_risk_event_summary(
    user_id: Optional[int] = None,
    symbol: Optional[str] = None,
) -> Dict:
    """
    Aggregate risk event counts by type and severity.
    Useful for dashboard cards and risk health overview.
    """
    try:
        from database.connection import SessionLocal
        from database.models import PersistentRiskEvent
        from sqlalchemy import func

        db = SessionLocal()
        query = db.query(
            PersistentRiskEvent.event_type,
            PersistentRiskEvent.severity,
            func.count(PersistentRiskEvent.id).label("count"),
        )

        if user_id is not None:
            query = query.filter(PersistentRiskEvent.user_id == user_id)
        if symbol:
            query = query.filter(PersistentRiskEvent.symbol == symbol.upper())

        rows = (
            query
            .group_by(PersistentRiskEvent.event_type, PersistentRiskEvent.severity)
            .all()
        )

        db.close()

        by_type = {}
        by_severity = {}
        total = 0
        for r in rows:
            by_type[r.event_type] = by_type.get(r.event_type, 0) + r.count
            by_severity[r.severity] = by_severity.get(r.severity, 0) + r.count
            total += r.count

        return {
            "total": total,
            "by_type": by_type,
            "by_severity": by_severity,
        }

    except Exception as e:
        logger.warning(f"[risk_persistence] Failed to get summary: {e}")
        return {"total": 0, "by_type": {}, "by_severity": {}}
