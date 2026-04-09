"""
AI Feed Engine for AURA.
Produces a unified, deduplicated feed of trading-relevant events.
Triggered by: decision engine, risk engine, auto-trader, market signals.
"""

import hashlib
import json
import logging
from datetime import datetime, date
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


# ── Event types ─────────────────────────────────────────────────
EVENT_TYPES = {
    "market_insight",
    "trade_signal",
    "risk_alert",
    "no_trade_explanation",
    "auto_trade",
    "portfolio_alert",
    "system",
}

SEVERITY_LEVELS = ("info", "warning", "critical")


def _dedup_key(event_type: str, symbol: str, title: str) -> str:
    """Generate a dedup key scoped to today + type + symbol + title."""
    today = date.today().isoformat()
    raw = f"{today}:{event_type}:{symbol}:{title}"
    return hashlib.md5(raw.encode()).hexdigest()


def emit(
    event_type: str,
    title: str,
    body: str,
    symbol: Optional[str] = None,
    severity: str = "info",
    reason_codes: Optional[List[str]] = None,
    metadata: Optional[Dict] = None,
) -> bool:
    """
    Emit a feed event. Deduplicated per day + type + symbol + title.
    Returns True if stored, False if duplicate or error.
    """
    if event_type not in EVENT_TYPES:
        logger.warning(f"[feed] Unknown event type: {event_type}")
        return False

    if severity not in SEVERITY_LEVELS:
        severity = "info"

    dedup = _dedup_key(event_type, symbol or "", title)
    codes_list = reason_codes or []
    meta_json = json.dumps(metadata or {})

    try:
        from database.connection import SessionLocal
        from sqlalchemy import text

        db = SessionLocal()
        # Upsert: skip if dedup_key already exists (today's duplicate)
        db.execute(text("""
            INSERT INTO feed_events (event_type, symbol, title, body, severity,
                                     reason_codes, metadata, dedup_key)
            VALUES (:etype, :sym, :title, :body, :sev,
                    :codes::text[], :meta::jsonb, :dedup)
            ON CONFLICT (dedup_key) DO NOTHING
        """), {
            "etype": event_type,
            "sym": symbol,
            "title": title,
            "body": body,
            "sev": severity,
            "codes": "{" + ",".join(codes_list) + "}" if codes_list else "{}",
            "meta": meta_json,
            "dedup": dedup,
        })
        db.commit()
        db.close()
        logger.debug(f"[feed] Emitted: {event_type} | {symbol} | {title}")
        return True
    except Exception as e:
        logger.error(f"[feed] Failed to emit event: {e}")
        return False


def get_feed(
    limit: int = 50,
    event_type: Optional[str] = None,
    symbol: Optional[str] = None,
    severity: Optional[str] = None,
) -> List[Dict]:
    """
    Retrieve feed events, sorted newest first, deduplicated by design.
    """
    try:
        from database.connection import SessionLocal
        from sqlalchemy import text

        conditions = ["1=1"]
        params = {"lim": limit}

        if event_type:
            conditions.append("event_type = :etype")
            params["etype"] = event_type
        if symbol:
            conditions.append("symbol = :sym")
            params["sym"] = symbol.upper()
        if severity:
            conditions.append("severity = :sev")
            params["sev"] = severity

        where = " AND ".join(conditions)

        db = SessionLocal()
        rows = db.execute(text(f"""
            SELECT id, event_type, symbol, title, body, severity,
                   reason_codes, metadata, created_at
            FROM feed_events
            WHERE {where}
            ORDER BY created_at DESC
            LIMIT :lim
        """), params).fetchall()
        db.close()

        events = []
        for r in rows:
            events.append({
                "id": r[0],
                "event_type": r[1],
                "symbol": r[2],
                "title": r[3],
                "body": r[4],
                "severity": r[5],
                "reason_codes": list(r[6]) if r[6] else [],
                "metadata": r[7] if r[7] else {},
                "timestamp": r[8].isoformat() if r[8] else None,
            })
        return events
    except Exception as e:
        logger.error(f"[feed] Failed to get feed: {e}")
        return []


# ── Convenience emitters (called from other modules) ────────────

def emit_trade_signal(symbol: str, action: str, confidence: float, reason_codes: List[str] = None):
    """Emit when the decision engine produces a BUY/SELL signal."""
    emit(
        event_type="trade_signal",
        title=f"{action} signal for {symbol}",
        body=f"AI recommends {action} with {confidence:.0%} confidence",
        symbol=symbol,
        severity="info" if action == "HOLD" else "warning",
        reason_codes=reason_codes,
        metadata={"action": action, "confidence": confidence},
    )


def emit_no_trade(symbol: str, reasons: List[str], reason_codes: List[str] = None):
    """Emit when the decision engine decides NOT to trade."""
    emit(
        event_type="no_trade_explanation",
        title=f"No trade for {symbol}",
        body="; ".join(reasons[:3]) if reasons else "Conditions not met",
        symbol=symbol,
        severity="info",
        reason_codes=reason_codes,
        metadata={"reason_count": len(reasons)},
    )


def emit_risk_alert(symbol: str, alert: str, severity: str = "warning", details: Dict = None):
    """Emit when the risk/portfolio engine flags a concern."""
    emit(
        event_type="risk_alert",
        title=f"Risk alert: {symbol}",
        body=alert,
        symbol=symbol,
        severity=severity,
        metadata=details,
    )


def emit_market_insight(symbol: str, insight: str, metadata: Dict = None):
    """Emit a market observation (regime change, volatility shift, etc.)."""
    emit(
        event_type="market_insight",
        title=f"Market insight: {symbol}",
        body=insight,
        symbol=symbol,
        severity="info",
        metadata=metadata,
    )


def emit_auto_trade(symbol: str, side: str, quantity: float, price: float):
    """Emit when the auto-trader executes a trade."""
    emit(
        event_type="auto_trade",
        title=f"Auto {side} {symbol}",
        body=f"Executed {side} {quantity} {symbol} at ${price:,.2f}",
        symbol=symbol,
        severity="warning",
        metadata={"side": side, "quantity": quantity, "price": price},
    )
