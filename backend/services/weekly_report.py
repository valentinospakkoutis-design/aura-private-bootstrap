"""Weekly performance report generation and delivery service."""

from __future__ import annotations

import importlib
import json
import logging
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from sqlalchemy import text

from database.connection import SessionLocal
from services.analytics import analytics_service
from services.paper_trading import paper_trading_service
from services.prediction_outcomes import prediction_outcomes_service
from services.push_notifications import send_push_to_user_id

logger = logging.getLogger(__name__)

_ANTHROPIC_KEY = os.getenv("ANTHROPIC_API_KEY", "")


def _get_anthropic_client():
    if not _ANTHROPIC_KEY:
        return None
    try:
        anthropic_module = importlib.import_module("anthropic")
        return anthropic_module.Anthropic(api_key=_ANTHROPIC_KEY, timeout=10.0)
    except Exception as e:
        logger.warning(f"[WEEKLY] Failed to init Anthropic client: {e}")
        return None


def _week_start_from(dt: datetime) -> datetime.date:
    return (dt - timedelta(days=dt.weekday())).date()


def _parse_ts(raw: Optional[str]) -> Optional[datetime]:
    if not raw:
        return None
    try:
        return datetime.fromisoformat(str(raw).replace("Z", "+00:00")).replace(tzinfo=None)
    except Exception:
        return None


def _get_user_trades(user_id: int, since: datetime) -> List[Dict]:
    trades = paper_trading_service.get_trade_history(limit=5000, user_id=int(user_id))
    out: List[Dict] = []
    for t in trades:
        ts = _parse_ts(t.get("executed_at") or t.get("timestamp"))
        if not ts or ts < since:
            continue
        out.append(t)
    return out


def _get_user_portfolio(user_id: int) -> Dict:
    return paper_trading_service.get_portfolio(user_id=int(user_id))


def _get_predictions_accuracy() -> float:
    acc = prediction_outcomes_service.get_accuracy(symbol=None)
    return float(acc.get("overall_accuracy_7d", 0.0) or 0.0)


def _best_trade(trades: List[Dict]) -> str:
    candidates = [t for t in trades if float(t.get("pnl", 0) or 0) != 0]
    if not candidates:
        return "N/A"
    b = max(candidates, key=lambda x: float(x.get("pnl", 0) or 0))
    return f"{b.get('symbol', 'N/A')} {float(b.get('pnl', 0) or 0):+.2f}$"


def _worst_trade(trades: List[Dict]) -> str:
    candidates = [t for t in trades if float(t.get("pnl", 0) or 0) != 0]
    if not candidates:
        return "N/A"
    w = min(candidates, key=lambda x: float(x.get("pnl", 0) or 0))
    return f"{w.get('symbol', 'N/A')} {float(w.get('pnl', 0) or 0):+.2f}$"


def _generate_report_text(stats: Dict) -> str:
    client = _get_anthropic_client()
    if not client:
        return _fallback_report_text(stats)

    try:
        prompt = f"""
Είσαι AI trading assistant. Γράψε εβδομαδιαία αναφορά 3 προτάσεων στα Ελληνικά.

Στατιστικά εβδομάδας:
- P/L: {float(stats['pnl_pct']):+.2f}%
- Trades: {int(stats['total_trades'])}
- Win Rate: {float(stats['win_rate']):.1f}%
- Καλύτερο trade: {stats['best_trade']}
- Χειρότερο trade: {stats['worst_trade']}
- AI Accuracy: {float(stats['ai_accuracy']):.1f}%

Συμπερίλαβε: τι πήγε καλά, τι να βελτιωθεί,
μία σύσταση για επόμενη εβδομάδα.
Χωρίς επενδυτικές συμβουλές. Μέγιστο 200 χαρακτήρες.
"""
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=250,
            messages=[{"role": "user", "content": prompt}],
        )
        text_out = (response.content[0].text or "").strip()
        return text_out[:200]
    except Exception as e:
        logger.warning(f"[WEEKLY] Claude generation failed: {e}")
        return _fallback_report_text(stats)


def _fallback_report_text(stats: Dict) -> str:
    pnl = float(stats.get("pnl_pct", 0.0) or 0.0)
    wr = float(stats.get("win_rate", 0.0) or 0.0)
    direction = "θετική" if pnl >= 0 else "αρνητική"
    suggestion = "Πειθαρχία στα φίλτρα confidence." if wr < 50 else "Διατήρησε τη συνέπεια στο risk management."
    text_out = (
        f"Η εβδομάδα ήταν {direction} με P/L {pnl:+.2f}% και win rate {wr:.1f}%. "
        f"Καλύτερο: {stats.get('best_trade', 'N/A')}. {suggestion}"
    )
    return text_out[:200]


def save_weekly_report(user_id: int, week_start, stats: Dict, report_text: str) -> None:
    db = SessionLocal()
    try:
        db.execute(
            text(
                """
                INSERT INTO weekly_reports
                    (user_id, week_start, pnl_pct, total_trades, win_rate, best_trade, worst_trade, ai_accuracy, report_text)
                VALUES
                    (:user_id, :week_start, :pnl_pct, :total_trades, :win_rate, :best_trade, :worst_trade, :ai_accuracy, :report_text)
                """
            ),
            {
                "user_id": int(user_id),
                "week_start": week_start,
                "pnl_pct": float(stats.get("pnl_pct", 0.0) or 0.0),
                "total_trades": int(stats.get("total_trades", 0) or 0),
                "win_rate": float(stats.get("win_rate", 0.0) or 0.0),
                "best_trade": str(stats.get("best_trade", "N/A")),
                "worst_trade": str(stats.get("worst_trade", "N/A")),
                "ai_accuracy": float(stats.get("ai_accuracy", 0.0) or 0.0),
                "report_text": str(report_text or ""),
            },
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def generate_weekly_report(user_id: int) -> Optional[Dict]:
    week_ago = datetime.utcnow() - timedelta(days=7)
    week_start = _week_start_from(datetime.utcnow())

    trades = _get_user_trades(user_id, since=week_ago)
    if not trades:
        return None

    portfolio = _get_user_portfolio(user_id)
    pnl_metrics = analytics_service.calculate_performance_metrics(
        trades=trades,
        portfolio_value=float(portfolio.get("total_value", 0.0) or 0.0),
        initial_balance=float(portfolio.get("initial_balance", 10000.0) or 10000.0),
    )

    stats = {
        "pnl_pct": float(pnl_metrics.get("total_pnl_percent", 0.0) or 0.0),
        "total_trades": len(trades),
        "win_rate": float(pnl_metrics.get("win_rate", 0.0) or 0.0),
        "best_trade": _best_trade(trades),
        "worst_trade": _worst_trade(trades),
        "ai_accuracy": _get_predictions_accuracy(),
    }

    report_text = _generate_report_text(stats)
    save_weekly_report(user_id, week_start, stats, report_text)

    preview = (report_text[:100] + "...") if len(report_text) > 100 else report_text
    send_push_to_user_id(
        int(user_id),
        title="📊 Εβδομαδιαία Αναφορά AURA",
        body=preview,
        data={"screen": "/weekly-report", "type": "weekly_report", "week_start": str(week_start)},
    )

    return {"week_start": str(week_start), "stats": stats, "report_text": report_text}


def get_users_with_notifications_enabled() -> List[Dict]:
    db = SessionLocal()
    try:
        rows = db.execute(
            text(
                """
                SELECT DISTINCT u.id
                FROM users u
                JOIN push_tokens pt ON pt.user_id = u.id
                LEFT JOIN user_profiles up ON up.user_id = u.id
                WHERE u.is_active = true
                  AND pt.is_active = true
                  AND COALESCE((up.behavior_flags_json->>'push_notifications_enabled')::boolean, true) = true
                """
            )
        ).fetchall()
        return [{"id": int(r[0])} for r in rows]
    except Exception as e:
        logger.error(f"[WEEKLY] Failed users query: {e}")
        return []
    finally:
        db.close()


def send_weekly_reports() -> None:
    users = get_users_with_notifications_enabled()
    logger.info(f"[WEEKLY] Sending weekly reports to {len(users)} users")
    for user in users:
        uid = int(user["id"])
        try:
            generate_weekly_report(uid)
        except Exception as e:
            logger.error(f"[WEEKLY] Failed {uid}: {e}")


def get_weekly_reports(user_id: int, limit: int = 4) -> Dict:
    db = SessionLocal()
    try:
        rows = db.execute(
            text(
                """
                SELECT week_start, pnl_pct, total_trades, win_rate, best_trade, worst_trade, ai_accuracy, report_text, created_at
                FROM weekly_reports
                WHERE user_id = :user_id
                ORDER BY week_start DESC, created_at DESC
                LIMIT :lim
                """
            ),
            {"user_id": int(user_id), "lim": int(limit)},
        ).mappings().all()

        reports = []
        for r in rows:
            reports.append(
                {
                    "week_start": str(r["week_start"]),
                    "stats": {
                        "pnl_pct": float(r["pnl_pct"] or 0.0),
                        "total_trades": int(r["total_trades"] or 0),
                        "win_rate": float(r["win_rate"] or 0.0),
                        "best_trade": r["best_trade"] or "N/A",
                        "worst_trade": r["worst_trade"] or "N/A",
                        "ai_accuracy": float(r["ai_accuracy"] or 0.0),
                    },
                    "report_text": r["report_text"] or "",
                    "created_at": r["created_at"].isoformat() if r["created_at"] else None,
                }
            )

        return {"reports": reports}
    finally:
        db.close()


def get_latest_weekly_report(user_id: int) -> Dict:
    data = get_weekly_reports(user_id, limit=1)
    reports = data.get("reports", [])
    if not reports:
        return {"stats": None, "report_text": "", "week_start": None}
    latest = reports[0]
    return {
        "stats": latest.get("stats"),
        "report_text": latest.get("report_text", ""),
        "week_start": latest.get("week_start"),
        "created_at": latest.get("created_at"),
    }
