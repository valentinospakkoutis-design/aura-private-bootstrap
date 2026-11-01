"""
Daily Evaluation & Retraining Pipeline
Τρέχει κάθε βράδυ στις 23:55 UTC.
1. Συλλέγει trades της ημέρας από trade_feedback
2. Αξιολογεί: win rate, error taxonomy
3. Trigger retraining αν χρειαστεί
4. Στέλνει Telegram report
"""
from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone, timedelta
from typing import Optional

import httpx
from sqlalchemy import text
from database.connection import get_async_db

logger = logging.getLogger(__name__)

# ── Telegram ────────────────────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID   = os.getenv("TELEGRAM_CHAT_ID", "6296218911")

async def _send_telegram(msg: str) -> None:
    if not TELEGRAM_BOT_TOKEN:
        logger.warning("[daily_eval] No TELEGRAM_BOT_TOKEN — skipping alert")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            await client.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "HTML"})
        except Exception as e:
            logger.error(f"[daily_eval] Telegram error: {e}")

# ── Error taxonomy ───────────────────────────────────────────────────────────
def _classify_error(row: dict) -> Optional[str]:
    """Κατηγοριοποιεί ένα λάθος trade."""
    outcome = (row.get("outcome") or "").lower()
    pnl     = row.get("pnl_pct") or 0.0
    action  = (row.get("action") or "").upper()

    if outcome == "win":
        return None  # Σωστό — δεν είναι λάθος

    if pnl < -2.0:
        return "wrong_direction"        # Έχασε >2% — λάθος κατεύθυνση
    elif pnl < 0:
        return "bad_timing"             # Μικρή ζημιά — σωστή κατεύθυνση, κακό timing
    elif pnl > 0 and outcome == "loss":
        return "early_exit"             # Βγήκε νωρίς
    else:
        return "other"

# ── Main evaluation ──────────────────────────────────────────────────────────
async def run_daily_evaluation(user_id: int = 1) -> dict:
    """
    Κύρια συνάρτηση — τρέχει μία φορά την ημέρα.
    Επιστρέφει dict με αποτελέσματα για logging/Telegram.
    """
    now_utc   = datetime.now(timezone.utc)
    day_start = now_utc.replace(hour=0, minute=0, second=0, microsecond=0)
    day_end   = now_utc

    logger.info(f"[daily_eval] Starting evaluation for {day_start.date()}")

    async with get_async_db() as db:
        # 1. Trades της ημέρας
        rows = (await db.execute(text("""
            SELECT symbol, action, confidence_at_entry,
                   entry_price, exit_price, pnl_pct, outcome, created_at
            FROM trade_feedback
            WHERE created_at >= :start AND created_at < :end
            ORDER BY created_at
        """), {"start": day_start, "end": day_end})).mappings().all()

    trades     = [dict(r) for r in rows]
    total      = len(trades)

    if total == 0:
        msg = (
            f"📊 <b>Aura Daily Report — {day_start.date()}</b>\n"
            f"Δεν υπήρξαν trades σήμερα."
        )
        await _send_telegram(msg)
        return {"date": str(day_start.date()), "total": 0, "retraining": False}

    # 2. Win rate
    wins      = sum(1 for t in trades if (t.get("outcome") or "").lower() == "win")
    win_rate  = wins / total if total > 0 else 0.0

    # 3. Error taxonomy
    errors: dict[str, int] = {}
    for t in trades:
        err = _classify_error(t)
        if err:
            errors[err] = errors.get(err, 0) + 1

    top_error = max(errors, key=errors.get) if errors else None

    # 4. Rolling 7-day win rate για σύγκριση
    week_start = day_start - timedelta(days=7)
    async with get_async_db() as db:
        week_rows = (await db.execute(text("""
            SELECT outcome FROM trade_feedback
            WHERE created_at >= :start AND created_at < :end
        """), {"start": week_start, "end": day_end})).mappings().all()

    week_trades  = [dict(r) for r in week_rows]
    week_wins    = sum(1 for t in week_trades if (t.get("outcome") or "").lower() == "win")
    week_wr      = week_wins / len(week_trades) if week_trades else win_rate
    rolling_7d   = week_wr

    # 5. Retraining trigger logic
    needs_retrain = False
    retrain_reason = ""

    if win_rate < 0.40:
        needs_retrain  = True
        retrain_reason = f"win_rate={win_rate:.0%} < 40% hard floor"
    elif win_rate < rolling_7d - 0.10:
        needs_retrain  = True
        retrain_reason = f"win_rate={win_rate:.0%} < 7d_avg={rolling_7d:.0%} - 10pp"
    elif top_error and errors[top_error] >= 3:
        # Ελέγχουμε αν το ίδιο error εμφανίστηκε 3+ φορές σήμερα
        needs_retrain  = True
        retrain_reason = f"error '{top_error}' x{errors[top_error]} today"

    # 6. Trigger retraining (async, non-blocking)
    retraining_done = False
    if needs_retrain:
        try:
            from services.retrainer import trigger_incremental_refit
            retraining_done = await trigger_incremental_refit(reason=retrain_reason)
        except Exception as e:
            logger.error(f"[daily_eval] Retraining failed: {e}")

    # 7. Telegram report
    error_lines = "\n".join(
        f"  • {k}: {v}x" for k, v in sorted(errors.items(), key=lambda x: -x[1])
    ) or "  Κανένα"

    retrain_line = (
        f"🔁 Retraining: {'✅ ολοκληρώθηκε' if retraining_done else '❌ απέτυχε'} ({retrain_reason})"
        if needs_retrain else
        "✅ Retraining: δεν χρειάστηκε"
    )

    msg = (
        f"📊 <b>Aura Daily Report — {day_start.date()}</b>\n\n"
        f"Trades: {total} | Wins: {wins} | <b>Win rate: {win_rate:.0%}</b>\n"
        f"7d avg: {rolling_7d:.0%}\n\n"
        f"Σφάλματα:\n{error_lines}\n\n"
        f"{retrain_line}"
    )
    await _send_telegram(msg)

    result = {
        "date":        str(day_start.date()),
        "total":       total,
        "wins":        wins,
        "win_rate":    round(win_rate, 3),
        "rolling_7d":  round(rolling_7d, 3),
        "errors":      errors,
        "retraining":  retraining_done,
        "retrain_reason": retrain_reason if needs_retrain else None,
    }
    logger.info(f"[daily_eval] Done: {result}")
    return result
