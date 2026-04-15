"""Performance dashboard aggregation for mobile clients."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Dict, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from database.models import PredictionOutcome, Transaction, UserProfile

PAPER_INITIAL_BALANCE = 10000.0


def _trade_stats_for_window(user_id: int, since_dt: datetime, db: Session) -> Dict:
    """Compute aggregate trade metrics for a user since ``since_dt``."""
    base_q = db.query(Transaction).filter(
        Transaction.user_id == user_id,
        Transaction.created_at >= since_dt,
    )
    total_trades = int(base_q.count())

    closed_q = base_q.filter(Transaction.pnl.isnot(None))
    closed_trades = int(closed_q.count())
    winning_trades = int(closed_q.filter(Transaction.pnl > 0).count()) if closed_trades else 0

    win_rate_pct = (winning_trades / closed_trades * 100.0) if closed_trades else 0.0
    total_pnl_pct = float(closed_q.with_entities(func.coalesce(func.sum(Transaction.pnl), 0.0)).scalar() or 0.0)

    best_trade_row: Optional[Transaction] = (
        closed_q.order_by(Transaction.pnl.desc()).first() if closed_trades else None
    )
    worst_trade_row: Optional[Transaction] = (
        closed_q.order_by(Transaction.pnl.asc()).first() if closed_trades else None
    )

    best_trade = {
        "symbol": str(best_trade_row.asset_id) if best_trade_row else None,
        "pnl_pct": float(best_trade_row.pnl or 0.0) if best_trade_row else 0.0,
    }
    worst_trade = {
        "symbol": str(worst_trade_row.asset_id) if worst_trade_row else None,
        "pnl_pct": float(worst_trade_row.pnl or 0.0) if worst_trade_row else 0.0,
    }

    return {
        "total_trades": total_trades,
        "win_rate_pct": round(win_rate_pct, 2),
        "total_pnl_pct": round(total_pnl_pct, 4),
        "best_trade": best_trade,
        "worst_trade": worst_trade,
    }


def get_performance_dashboard(user_id: int, db: Session) -> Dict:
    """Return weekly/monthly trading stats, AI accuracy and paper portfolio KPIs."""
    now = datetime.utcnow()
    weekly_since = now - timedelta(days=7)
    monthly_since = now - timedelta(days=30)

    weekly = _trade_stats_for_window(user_id=user_id, since_dt=weekly_since, db=db)
    monthly = _trade_stats_for_window(user_id=user_id, since_dt=monthly_since, db=db)

    outcomes_q = db.query(PredictionOutcome).filter(
        PredictionOutcome.created_at >= monthly_since,
        PredictionOutcome.was_correct_7d.isnot(None),
    )
    total_predictions = int(outcomes_q.count())
    correct_predictions = (
        int(outcomes_q.filter(PredictionOutcome.was_correct_7d.is_(True)).count())
        if total_predictions
        else 0
    )
    prediction_accuracy = (correct_predictions / total_predictions * 100.0) if total_predictions else 0.0

    profile = db.query(UserProfile).filter(UserProfile.user_id == user_id).first()
    paper_balance = float(profile.paper_balance or PAPER_INITIAL_BALANCE) if profile else PAPER_INITIAL_BALANCE
    paper_positions = profile.paper_positions if profile and isinstance(profile.paper_positions, list) else []
    paper_pnl_pct = ((paper_balance - PAPER_INITIAL_BALANCE) / PAPER_INITIAL_BALANCE * 100.0)

    return {
        "weekly": weekly,
        "monthly": monthly,
        "ai_accuracy": {
            "prediction_accuracy": round(prediction_accuracy, 2),
            "total_predictions": total_predictions,
            "correct_predictions": correct_predictions,
        },
        "portfolio": {
            "paper_balance": round(paper_balance, 2),
            "paper_pnl_pct": round(paper_pnl_pct, 2),
            "paper_positions_count": len(paper_positions),
        },
    }
