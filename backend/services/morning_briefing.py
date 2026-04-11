"""Morning AI briefing service (daily push at 08:00 EET)."""

import json
import logging
import os
import importlib
from typing import Dict, List

import httpx
from sqlalchemy import text

from ai.asset_predictor import asset_predictor
from database.connection import SessionLocal
from services.paper_trading import paper_trading_service
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
        logger.warning(f"[BRIEFING] Failed to init Anthropic client: {e}")
        return None


def get_fear_greed_index() -> int:
    """Fetch fear & greed index (0-100), fallback to neutral 50."""
    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.get("https://api.alternative.me/fng/?limit=1")
            resp.raise_for_status()
            data = resp.json()
            return int(float(data["data"][0]["value"]))
    except Exception as e:
        logger.warning(f"[BRIEFING] Fear & Greed fetch failed: {e}")
        return 50


def get_top_predictions(limit: int = 3, min_confidence: float = 0.80) -> List[Dict]:
    """Get top confidence AI predictions as compact records."""
    try:
        raw = asset_predictor.get_all_predictions(days=1, asset_type_filter=None)
        predictions = list((raw or {}).get("predictions", {}).items())

        normalized = []
        for symbol, p in predictions:
            if not isinstance(p, dict) or p.get("error"):
                continue
            confidence_raw = float(p.get("confidence", 0.0))
            confidence = confidence_raw / 100.0 if confidence_raw > 1 else confidence_raw
            if confidence < float(min_confidence):
                continue
            rec = str(p.get("recommendation") or "HOLD").upper()
            if rec == "HOLD":
                continue
            normalized.append(
                {
                    "symbol": symbol,
                    "action": rec,
                    "confidence": round(confidence, 3),
                    "trend": str(p.get("trend") or "SIDEWAYS"),
                }
            )

        normalized.sort(key=lambda x: x["confidence"], reverse=True)
        return normalized[: max(1, int(limit))]
    except Exception as e:
        logger.warning(f"[BRIEFING] Failed to get top predictions: {e}")
        return []


def get_user_portfolio_summary(user_id: int) -> Dict:
    """Get lightweight portfolio snapshot for briefing context."""
    try:
        portfolio = paper_trading_service.get_portfolio(user_id=int(user_id))
        return {
            "total_value": float(portfolio.get("total_value", 0.0) or 0.0),
            "pnl_pct": float(portfolio.get("total_pnl_percent", 0.0) or 0.0),
        }
    except Exception as e:
        logger.warning(f"[BRIEFING] Portfolio summary failed (user_id={user_id}): {e}")
        return {"total_value": 0.0, "pnl_pct": 0.0}


def _fallback_briefing(fear_greed: int, top_signals: List[Dict]) -> str:
    market = "ουδέτερη" if 40 <= fear_greed <= 60 else "αισιόδοξη" if fear_greed > 60 else "επιφυλακτική"
    best = top_signals[0] if top_signals else None
    if best:
        msg = (
            f"Η διάθεση αγοράς είναι {market} (F&G {fear_greed}/100). "
            f"Κορυφαίο setup: {best['symbol']} {best['action']} ({int(best['confidence'] * 100)}%)."
        )
    else:
        msg = f"Η διάθεση αγοράς είναι {market} (F&G {fear_greed}/100). Δεν ξεχώρισε ισχυρό setup σήμερα."
    return msg[:150]


def generate_morning_briefing(user_id: int) -> int:
    """Generate and send one morning briefing push to a user."""
    fear_greed = get_fear_greed_index()
    top_signals = get_top_predictions(limit=3, min_confidence=0.80)
    portfolio = get_user_portfolio_summary(user_id)

    briefing = ""
    client = _get_anthropic_client()
    if client:
        try:
            prompt = f"""
Είσαι AI trading assistant. Γράψε morning briefing 2 προτάσεων στα Ελληνικά.

Δεδομένα:
- Fear & Greed: {fear_greed}/100
- Top signals: {json.dumps(top_signals, ensure_ascii=False)}
- Portfolio P/L: {float(portfolio.get('pnl_pct', 0.0)):.1f}%

Συμπερίλαβε: διάθεση αγοράς + καλύτερη ευκαιρία σήμερα.
Χωρίς επενδυτικές συμβουλές.
Μέγιστο 150 χαρακτήρες.
"""
            response = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=200,
                messages=[{"role": "user", "content": prompt}],
            )
            briefing = (response.content[0].text or "").strip()
        except Exception as e:
            logger.warning(f"[BRIEFING] Claude generation failed (user_id={user_id}): {e}")

    if not briefing:
        briefing = _fallback_briefing(fear_greed, top_signals)
    briefing = briefing[:150]

    sent = send_push_to_user_id(
        int(user_id),
        title="🌅 Καλημέρα από AURA",
        body=briefing,
        data={"screen": "/ai-predictions", "type": "morning_briefing"},
    )
    return int(sent)


def get_users_with_briefing_enabled() -> List[Dict]:
    """Users with morning briefing enabled and at least one active push token."""
    db = SessionLocal()
    try:
        rows = db.execute(
            text(
                """
                SELECT DISTINCT u.id
                FROM users u
                                LEFT JOIN user_profiles up ON up.user_id = u.id
                JOIN push_tokens pt ON pt.user_id = u.id
                WHERE u.is_active = true
                  AND pt.is_active = true
                  AND COALESCE(up.morning_briefing_enabled, true) = true
                """
            )
        ).fetchall()
        return [{"id": int(r[0])} for r in rows]
    except Exception as e:
        logger.error(f"[BRIEFING] Failed to load users: {e}")
        return []
    finally:
        db.close()


def send_morning_briefings() -> None:
    users = get_users_with_briefing_enabled()
    logger.info(f"[BRIEFING] Sending morning briefings to {len(users)} users")

    for user in users:
        uid = int(user.get("id"))
        try:
            sent = generate_morning_briefing(uid)
            logger.info(f"[BRIEFING] user={uid} sent={sent}")
        except Exception as e:
            logger.error(f"[BRIEFING] Failed for {uid}: {e}")
            continue
