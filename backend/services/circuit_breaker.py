"""Circuit breaker service for catastrophic loss protection."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Dict, Optional

from sqlalchemy.orm import Session

from database.connection import SessionLocal
from database.models import CircuitBreakerEvent, Transaction, UserProfile


DAILY_LOSS_LIMIT_PCT = 10.0
DRAWDOWN_LIMIT_PCT = 15.0
CONSECUTIVE_LOSS_LIMIT = 5
COOLDOWN_HOURS = 24
INITIAL_PAPER_BALANCE = 10000.0


def _active_event(user_id: int, db: Session) -> Optional[CircuitBreakerEvent]:
    return (
        db.query(CircuitBreakerEvent)
        .filter(
            CircuitBreakerEvent.user_id == int(user_id),
            CircuitBreakerEvent.reset_manually == False,
            CircuitBreakerEvent.resume_at > datetime.utcnow(),
        )
        .order_by(CircuitBreakerEvent.tripped_at.desc())
        .first()
    )


def _compute_today_loss_pct(user_id: int, db: Session) -> float:
    now = datetime.utcnow()
    today_start = datetime(now.year, now.month, now.day)

    trades = (
        db.query(Transaction)
        .filter(
            Transaction.user_id == int(user_id),
            Transaction.created_at >= today_start,
            Transaction.pnl.isnot(None),
        )
        .all()
    )

    total_pnl = sum(float(t.pnl or 0.0) for t in trades)
    if total_pnl >= 0:
        return 0.0
    return abs(total_pnl) / INITIAL_PAPER_BALANCE * 100.0


def _compute_drawdown_pct(user_id: int, db: Session) -> float:
    profile = db.query(UserProfile).filter(UserProfile.user_id == int(user_id)).first()
    current_balance = float(profile.paper_balance or INITIAL_PAPER_BALANCE) if profile else INITIAL_PAPER_BALANCE

    trades = (
        db.query(Transaction)
        .filter(Transaction.user_id == int(user_id), Transaction.pnl.isnot(None))
        .order_by(Transaction.created_at.asc())
        .all()
    )

    running_balance = INITIAL_PAPER_BALANCE
    peak_balance = INITIAL_PAPER_BALANCE
    for tr in trades:
        running_balance += float(tr.pnl or 0.0)
        if running_balance > peak_balance:
            peak_balance = running_balance

    peak_balance = max(peak_balance, current_balance, 1.0)
    if current_balance >= peak_balance:
        return 0.0
    return (peak_balance - current_balance) / peak_balance * 100.0


def _count_consecutive_losses(user_id: int, db: Session) -> int:
    trades = (
        db.query(Transaction)
        .filter(Transaction.user_id == int(user_id), Transaction.pnl.isnot(None))
        .order_by(Transaction.created_at.desc())
        .limit(50)
        .all()
    )

    streak = 0
    for tr in trades:
        pnl = float(tr.pnl or 0.0)
        if pnl < 0:
            streak += 1
        else:
            break
    return streak


def check_circuit_breaker(user_id: int, db: Session) -> dict:
    """Evaluate circuit breaker rules and create a pause event when breached."""
    active = _active_event(user_id, db)
    if active:
        return {
            "tripped": True,
            "reason": str(active.reason),
            "resume_at": active.resume_at,
        }

    daily_loss_pct = _compute_today_loss_pct(user_id, db)
    drawdown_pct = _compute_drawdown_pct(user_id, db)
    consecutive_losses = _count_consecutive_losses(user_id, db)

    reason = None
    rule_id = None

    if daily_loss_pct > DAILY_LOSS_LIMIT_PCT:
        rule_id = "daily_loss_limit"
        reason = f"Daily loss limit breached: {daily_loss_pct:.2f}% > {DAILY_LOSS_LIMIT_PCT:.2f}%"
    elif drawdown_pct > DRAWDOWN_LIMIT_PCT:
        rule_id = "drawdown_limit"
        reason = f"Drawdown limit breached: {drawdown_pct:.2f}% > {DRAWDOWN_LIMIT_PCT:.2f}%"
    elif consecutive_losses >= CONSECUTIVE_LOSS_LIMIT:
        rule_id = "consecutive_losses_limit"
        reason = f"Consecutive losses limit breached: {consecutive_losses} >= {CONSECUTIVE_LOSS_LIMIT}"

    if not reason:
        return {"tripped": False, "reason": "ok", "resume_at": None}

    resume_at = datetime.utcnow() + timedelta(hours=COOLDOWN_HOURS)
    event = CircuitBreakerEvent(
        user_id=int(user_id),
        rule_id=str(rule_id),
        reason=str(reason),
        resume_at=resume_at,
        reset_manually=False,
    )
    db.add(event)
    db.commit()

    return {
        "tripped": True,
        "reason": reason,
        "resume_at": resume_at,
    }


def reset_circuit_breaker(user_id: int, db: Session) -> dict:
    """Manually reset active circuit breaker events for a user."""
    now = datetime.utcnow()
    active_events = (
        db.query(CircuitBreakerEvent)
        .filter(
            CircuitBreakerEvent.user_id == int(user_id),
            CircuitBreakerEvent.reset_manually == False,
            CircuitBreakerEvent.resume_at > now,
        )
        .all()
    )

    for ev in active_events:
        ev.reset_manually = True
        ev.resume_at = now

    db.commit()
    return {
        "success": True,
        "user_id": int(user_id),
        "reset_count": len(active_events),
        "reset_at": now,
    }


class CircuitBreakerService:
    """Compatibility wrapper for existing callers in main and auto-trader."""

    def get_state(self, user_id: int) -> Dict:
        db = SessionLocal()
        try:
            active = _active_event(int(user_id), db)
            if not active:
                return {
                    "state": "active",
                    "reason": None,
                    "rule_id": None,
                    "resume_at": None,
                    "minutes_remaining": 0,
                }

            minutes_remaining = max(0, int((active.resume_at - datetime.utcnow()).total_seconds() // 60))
            return {
                "state": "paused",
                "reason": str(active.reason),
                "rule_id": str(active.rule_id),
                "resume_at": active.resume_at,
                "minutes_remaining": minutes_remaining,
            }
        finally:
            db.close()

    def evaluate_and_trip(self, user_id: int, closed_trades=None, equity_reference: float = 0.0) -> Dict:
        # Preserve old method name while delegating to the new function API.
        db = SessionLocal()
        try:
            res = check_circuit_breaker(int(user_id), db)
            if res.get("tripped"):
                return {
                    "tripped": True,
                    "reason": res.get("reason"),
                    "event": {
                        "rule_id": "compat_check",
                        "resume_at": res.get("resume_at"),
                    },
                }
            return {"tripped": False, "state": self.get_state(int(user_id))}
        finally:
            db.close()

    def reset(self, user_id: int) -> bool:
        db = SessionLocal()
        try:
            reset_circuit_breaker(int(user_id), db)
            return True
        finally:
            db.close()


circuit_breaker_service = CircuitBreakerService()
