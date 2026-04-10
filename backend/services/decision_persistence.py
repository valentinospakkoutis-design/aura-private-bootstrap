"""
Decision Persistence Service for AURA.
Saves AI decision explanations to the relational explainability schema:
  - ai_decision_events       (append-only fact table)
  - ai_decision_reason_codes (append-only, FK to event, queryable by code)
  - ai_decision_counterfactuals (append-only, FK to event)
"""

import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# ── Reason code → category mapping ────────────────────────────
# Categories: positive, risk, rejection, sizing, context
CODE_CATEGORIES = {
    # Positive / directional
    "ML_POSITIVE_FORECAST": "positive",
    "ML_NEGATIVE_FORECAST": "positive",
    "TREND_BULLISH": "positive",
    "TREND_BEARISH": "positive",
    "SMART_SCORE_ABOVE_THRESHOLD": "positive",
    "SIGNAL_ALIGNMENT_HIGH": "positive",
    "RSI_SUPPORTS_DIRECTION": "positive",
    "VOLUME_CONFIRMS_MOVE": "positive",
    "NEWS_SENTIMENT_FAVORABLE": "positive",
    "MTF_TREND_ALIGNED": "positive",
    "STRONG_SIGNAL_STRENGTH": "positive",
    # Rejection / inaction
    "LOW_CONFIDENCE": "rejection",
    "SIGNAL_CONFLICT": "rejection",
    "NO_ML_CONFIRMATION": "rejection",
    "TREND_TOO_WEAK": "rejection",
    "MARKET_SIDEWAYS": "rejection",
    "WAIT_FOR_CONFIRMATION": "rejection",
    "SMART_SCORE_INSUFFICIENT": "rejection",
    "PRICE_CHANGE_BELOW_THRESHOLD": "rejection",
    "SMART_SCORE_BELOW_THRESHOLD": "rejection",
    # Risk
    "VOLATILITY_TOO_HIGH": "risk",
    "RISK_BLOCK": "risk",
    "PORTFOLIO_EXPOSURE_LIMIT": "risk",
    "SYMBOL_EXPOSURE_LIMIT": "risk",
    "GLOBAL_EXPOSURE_LIMIT": "risk",
    "FEAR_GREED_EXTREME": "risk",
    # Sizing
    "SIZE_REDUCED_BY_RISK": "sizing",
    "SIZE_REDUCED_BY_VOLATILITY": "sizing",
    "SIZE_REDUCED_BY_DRAWDOWN": "sizing",
    "SIZE_REDUCED_BY_EXPOSURE_CAP": "sizing",
}


def _classify_code(code: str) -> str:
    """Return the category for a reason code, defaulting to 'context'."""
    return CODE_CATEGORIES.get(code, "context")


def save_decision_event(
    explanation,
    user_id: Optional[int] = None,
    symbol: str = "",
    raw_signal: Optional[dict] = None,
) -> Optional[int]:
    """
    Persist a DecisionExplanation to the 3-table schema.
    Returns the ai_decision_events.id or None on failure.

    Args:
        explanation: DecisionExplanation (pydantic model)
        user_id: optional user who triggered the decision
        symbol: trading symbol
        raw_signal: optional raw signal payload to store
    """
    try:
        from database.connection import SessionLocal
        from database.models import (
            AIDecisionEvent, AIDecisionReasonCode, AIDecisionCounterfactual,
        )

        db = SessionLocal()

        # ── 1. Insert event ──
        event = AIDecisionEvent(
            user_id=user_id,
            symbol=symbol or explanation.audit_metadata.get("symbol", ""),
            action=explanation.action,
            confidence_score=explanation.confidence_score,
            confidence_band=explanation.confidence_band,
            market_regime=explanation.market_regime,
            narrative_summary=explanation.narrative_summary,
            machine_summary=explanation.machine_summary,
            stop_loss_logic=explanation.stop_loss_logic,
            take_profit_logic=explanation.take_profit_logic,
            expected_holding_profile=explanation.expected_holding_profile,
            raw_signal_payload_json=raw_signal or {},
            audit_metadata_json=explanation.audit_metadata,
        )
        db.add(event)
        db.flush()  # get event.id for FK inserts

        # ── 2. Insert reason codes (relational, not JSON) ──
        for code in explanation.reason_codes:
            db.add(AIDecisionReasonCode(
                decision_event_id=event.id,
                code=code,
                category=_classify_code(code),
                detail_text=None,
            ))

        # Blocked-by codes as risk-category reason codes
        for blocked in explanation.blocked_by:
            db.add(AIDecisionReasonCode(
                decision_event_id=event.id,
                code="RISK_BLOCK",
                category="risk",
                detail_text=blocked,
            ))

        # Sizing adjustments as sizing-category reason codes
        for adj in explanation.sizing_adjustments:
            db.add(AIDecisionReasonCode(
                decision_event_id=event.id,
                code="SIZE_ADJUSTED",
                category="sizing",
                detail_text=adj,
            ))

        # ── 3. Insert counterfactuals ──
        for item in explanation.why_not_opposite:
            db.add(AIDecisionCounterfactual(
                decision_event_id=event.id,
                counterfactual_type="why_not_opposite",
                content=item,
            ))

        for item in explanation.why_not_wait:
            db.add(AIDecisionCounterfactual(
                decision_event_id=event.id,
                counterfactual_type="why_not_wait",
                content=item,
            ))

        for item in explanation.invalidation_conditions:
            db.add(AIDecisionCounterfactual(
                decision_event_id=event.id,
                counterfactual_type="invalidation_condition",
                content=item,
            ))

        for item in explanation.improvement_triggers:
            db.add(AIDecisionCounterfactual(
                decision_event_id=event.id,
                counterfactual_type="improvement_trigger",
                content=item,
            ))

        db.commit()
        event_id = event.id
        db.close()

        logger.info(f"[decision_persistence] Saved event {event_id}: "
                     f"{symbol} {explanation.action} conf={explanation.confidence_score:.2f}")

        # Unified audit trail
        try:
            from services.audit_trail import emit_audit
            sev = "critical" if explanation.action == "BLOCKED" else (
                "warning" if explanation.action in ("BUY", "SELL") else "info"
            )
            emit_audit(
                domain="decision",
                event_name=f"AI_DECISION_{explanation.action}",
                summary=f"{sym} {explanation.action} | conf={explanation.confidence_score:.0%} | {explanation.confidence_band}",
                user_id=user_id,
                entity_type="ai_decision_event",
                entity_id=event_id,
                severity=sev,
                payload={"symbol": sym, "action": explanation.action,
                         "confidence": explanation.confidence_score,
                         "reason_codes": explanation.reason_codes[:5]},
            )
        except Exception:
            pass

        return event_id

    except Exception as e:
        logger.error(f"[decision_persistence] Failed to save decision: {e}")
        return None


def get_decision_history(
    user_id: Optional[int] = None,
    symbol: Optional[str] = None,
    limit: int = 20,
) -> List[Dict]:
    """
    Query decision history with reason codes and counterfactuals.
    Filter by user_id and/or symbol.
    """
    try:
        from database.connection import SessionLocal
        from database.models import (
            AIDecisionEvent, AIDecisionReasonCode, AIDecisionCounterfactual,
        )

        db = SessionLocal()
        query = db.query(AIDecisionEvent)

        if user_id is not None:
            query = query.filter(AIDecisionEvent.user_id == user_id)
        if symbol:
            query = query.filter(AIDecisionEvent.symbol == symbol.upper())

        events = (
            query
            .order_by(AIDecisionEvent.created_at.desc())
            .limit(limit)
            .all()
        )

        results = []
        for ev in events:
            # Fetch reason codes for this event
            codes = (
                db.query(AIDecisionReasonCode)
                .filter(AIDecisionReasonCode.decision_event_id == ev.id)
                .all()
            )
            # Fetch counterfactuals for this event
            cfs = (
                db.query(AIDecisionCounterfactual)
                .filter(AIDecisionCounterfactual.decision_event_id == ev.id)
                .all()
            )

            results.append({
                "id": ev.id,
                "user_id": ev.user_id,
                "symbol": ev.symbol,
                "action": ev.action,
                "confidence_score": ev.confidence_score,
                "confidence_band": ev.confidence_band,
                "market_regime": ev.market_regime,
                "narrative_summary": ev.narrative_summary,
                "machine_summary": ev.machine_summary,
                "stop_loss_logic": ev.stop_loss_logic,
                "take_profit_logic": ev.take_profit_logic,
                "expected_holding_profile": ev.expected_holding_profile,
                "audit_metadata": ev.audit_metadata_json or {},
                "created_at": ev.created_at.isoformat() if ev.created_at else None,
                "reason_codes": [
                    {
                        "code": rc.code,
                        "category": rc.category,
                        "detail": rc.detail_text,
                    }
                    for rc in codes
                ],
                "counterfactuals": [
                    {
                        "type": cf.counterfactual_type,
                        "content": cf.content,
                    }
                    for cf in cfs
                ],
            })

        db.close()
        return results

    except Exception as e:
        logger.warning(f"[decision_persistence] Failed to load history: {e}")
        return []


def get_reason_code_stats(
    symbol: Optional[str] = None,
    limit: int = 20,
) -> List[Dict]:
    """
    Aggregate reason code frequency — useful for analytics.
    Returns top N codes by occurrence count.
    """
    try:
        from database.connection import SessionLocal
        from database.models import AIDecisionReasonCode, AIDecisionEvent
        from sqlalchemy import func

        db = SessionLocal()
        query = (
            db.query(
                AIDecisionReasonCode.code,
                AIDecisionReasonCode.category,
                func.count(AIDecisionReasonCode.id).label("count"),
            )
        )

        if symbol:
            query = (
                query
                .join(AIDecisionEvent, AIDecisionReasonCode.decision_event_id == AIDecisionEvent.id)
                .filter(AIDecisionEvent.symbol == symbol.upper())
            )

        rows = (
            query
            .group_by(AIDecisionReasonCode.code, AIDecisionReasonCode.category)
            .order_by(func.count(AIDecisionReasonCode.id).desc())
            .limit(limit)
            .all()
        )

        db.close()
        return [
            {"code": r.code, "category": r.category, "count": r.count}
            for r in rows
        ]

    except Exception as e:
        logger.warning(f"[decision_persistence] Failed to get stats: {e}")
        return []
