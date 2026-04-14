"""Weekly report generation sourced from the authoritative DB tables.

Unlike ``services.weekly_report`` (which pulls from the in-memory paper
trading service and calls Anthropic for narrative text), this module computes
the report directly from ``transactions``, ``user_profiles.paper_positions``
and ``prediction_outcomes``, and writes a deterministic summary string.

The entry point ``generate_weekly_report(user_id, db)`` takes the caller's
SQLAlchemy session so it can be invoked from request handlers, cron jobs, or
other services without opening a new connection.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Dict, Optional

from sqlalchemy.orm import Session

from database.models import (
    PredictionOutcome,
    Transaction,
    UserProfile,
    WeeklyReport,
)

PAPER_INITIAL_BALANCE = 10000.0


def _last_monday(now: Optional[datetime] = None) -> date:
    """Return the date of the most recent Monday (inclusive of today)."""
    ref = now or datetime.utcnow()
    return (ref - timedelta(days=ref.weekday())).date()


def _compute_pnl_pct(profile: Optional[UserProfile]) -> float:
    """Realized P/L% of the paper portfolio vs. its initial balance."""
    if profile is None:
        return 0.0

    balance = float(profile.paper_balance or 0.0)
    positions = profile.paper_positions if isinstance(profile.paper_positions, list) else []

    total_cost = 0.0
    for pos in positions:
        try:
            total_cost += float(pos.get("total_cost") or (float(pos.get("avg_price") or 0) * float(pos.get("quantity") or 0)))
        except Exception:
            continue

    equity = balance + total_cost
    if PAPER_INITIAL_BALANCE <= 0:
        return 0.0
    return ((equity - PAPER_INITIAL_BALANCE) / PAPER_INITIAL_BALANCE) * 100.0


def _format_trade(row: Optional[Transaction]) -> str:
    if row is None or row.pnl is None:
        return "N/A"
    return f"{row.asset_id} {float(row.pnl):+.2f}"


def _summary_text(stats: Dict) -> str:
    pnl = float(stats.get("pnl_pct") or 0.0)
    wr = float(stats.get("win_rate") or 0.0)
    acc = float(stats.get("ai_accuracy") or 0.0)
    trades = int(stats.get("total_trades") or 0)
    direction = "up" if pnl >= 0 else "down"
    return (
        f"Week of {stats['week_start']}: portfolio {direction} {pnl:+.2f}% across {trades} trades "
        f"(win rate {wr:.1f}%). Best: {stats.get('best_trade', 'N/A')}. "
        f"Worst: {stats.get('worst_trade', 'N/A')}. AI 7-day accuracy {acc:.1f}%."
    )


def generate_weekly_report(user_id: int, db: Session) -> Dict:
    """Compute and persist a weekly performance snapshot for a user.

    The row is upserted on ``(user_id, week_start)`` — if a report already
    exists for this week it is overwritten in place rather than duplicated.
    Returns the computed stats and summary text.
    """
    week_start = _last_monday()
    week_start_dt = datetime.combine(week_start, datetime.min.time())
    next_week_dt = week_start_dt + timedelta(days=7)

    # 1. Total paper trades this week.
    total_trades = (
        db.query(Transaction)
        .filter(
            Transaction.user_id == user_id,
            Transaction.created_at >= week_start_dt,
            Transaction.created_at < next_week_dt,
        )
        .count()
    )

    # 2. P/L% from the paper portfolio state.
    profile = db.query(UserProfile).filter(UserProfile.user_id == user_id).first()
    pnl_pct = _compute_pnl_pct(profile)

    # 3. Win rate over SELL transactions with a recorded pnl this week.
    closed_trades_q = db.query(Transaction).filter(
        Transaction.user_id == user_id,
        Transaction.created_at >= week_start_dt,
        Transaction.created_at < next_week_dt,
        Transaction.pnl.isnot(None),
    )
    closed_trades = closed_trades_q.count()
    wins = closed_trades_q.filter(Transaction.pnl > 0).count() if closed_trades else 0
    win_rate = (wins / closed_trades * 100.0) if closed_trades else 0.0

    # 4. Best / worst trade by pnl this week.
    best = closed_trades_q.order_by(Transaction.pnl.desc()).first() if closed_trades else None
    worst = closed_trades_q.order_by(Transaction.pnl.asc()).first() if closed_trades else None

    # 5. AI accuracy from prediction_outcomes evaluated this week.
    outcomes_q = db.query(PredictionOutcome).filter(
        PredictionOutcome.created_at >= week_start_dt,
        PredictionOutcome.created_at < next_week_dt,
        PredictionOutcome.was_correct_7d.isnot(None),
    )
    total_outcomes = outcomes_q.count()
    correct_outcomes = (
        outcomes_q.filter(PredictionOutcome.was_correct_7d.is_(True)).count()
        if total_outcomes
        else 0
    )
    ai_accuracy = (correct_outcomes / total_outcomes * 100.0) if total_outcomes else 0.0

    stats = {
        "week_start": week_start.isoformat(),
        "pnl_pct": round(pnl_pct, 4),
        "total_trades": int(total_trades),
        "win_rate": round(win_rate, 2),
        "best_trade": _format_trade(best),
        "worst_trade": _format_trade(worst),
        "ai_accuracy": round(ai_accuracy, 2),
    }
    report_text = _summary_text(stats)

    # 6. Upsert by (user_id, week_start). No unique constraint exists, so we
    #    read-modify-write under the caller's session.
    existing = (
        db.query(WeeklyReport)
        .filter(WeeklyReport.user_id == user_id, WeeklyReport.week_start == week_start)
        .first()
    )
    if existing is None:
        existing = WeeklyReport(user_id=user_id, week_start=week_start)
        db.add(existing)

    existing.pnl_pct = stats["pnl_pct"]
    existing.total_trades = stats["total_trades"]
    existing.win_rate = stats["win_rate"]
    existing.best_trade = stats["best_trade"]
    existing.worst_trade = stats["worst_trade"]
    existing.ai_accuracy = stats["ai_accuracy"]
    existing.report_text = report_text
    db.commit()

    return {**stats, "report_text": report_text}
