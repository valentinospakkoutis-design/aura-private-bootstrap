"""
Push Notification Service for AURA
Sends notifications via Expo Push API (no FCM keys needed).
"""

import logging
from typing import Optional, List

import httpx

logger = logging.getLogger(__name__)

EXPO_PUSH_URL = "https://exp.host/--/api/v2/push/send"


def send_push_notification(
    token: str,
    title: str,
    body: str,
    data: Optional[dict] = None,
) -> bool:
    """Send a push notification via Expo Push API."""
    if not token or not token.startswith("ExponentPushToken"):
        logger.debug(f"[push] Invalid token, skipping: {token[:20] if token else 'None'}...")
        return False

    payload = {
        "to": token,
        "title": title,
        "body": body,
        "sound": "default",
    }
    if data:
        payload["data"] = data

    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.post(EXPO_PUSH_URL, json=payload)
            resp.raise_for_status()
            result = resp.json()
            logger.info(f"[push] Sent to {token[:30]}...: {title}")
            return True
    except Exception as e:
        logger.error(f"[push] Failed: {e}")
        return False


def send_push_to_all_users(title: str, body: str, data: Optional[dict] = None):
    """Send push notification to all registered tokens."""
    tokens = _get_all_tokens()
    sent = 0
    for token in tokens:
        if send_push_notification(token, title, body, data):
            sent += 1
    logger.info(f"[push] Sent to {sent}/{len(tokens)} devices")
    return sent


def _get_all_tokens() -> List[str]:
    """Get all registered push tokens from DB."""
    try:
        from database.connection import SessionLocal
        from sqlalchemy import text
        db = SessionLocal()
        rows = db.execute(text("SELECT token FROM push_tokens WHERE is_active = true")).fetchall()
        db.close()
        return [r[0] for r in rows if r[0]]
    except Exception as e:
        logger.error(f"[push] Failed to get tokens: {e}")
        return []


def _get_tokens_for_user(user_id: int) -> List[str]:
    """Get active push tokens for a single user."""
    try:
        from database.connection import SessionLocal
        from sqlalchemy import text
        db = SessionLocal()
        rows = db.execute(
            text("SELECT token FROM push_tokens WHERE is_active = true AND user_id = :user_id"),
            {"user_id": int(user_id)},
        ).fetchall()
        db.close()
        return [r[0] for r in rows if r[0]]
    except Exception as e:
        logger.error(f"[push] Failed to get user tokens (user_id={user_id}): {e}")
        return []


def send_push_to_user_id(user_id: int, title: str, body: str, data: Optional[dict] = None) -> int:
    """Send push notification only to a specific user."""
    tokens = _get_tokens_for_user(user_id)
    sent = 0
    for token in tokens:
        if send_push_notification(token, title=title, body=body, data=data):
            sent += 1
    logger.info(f"[push] Sent user notification to {sent}/{len(tokens)} devices (user_id={user_id})")
    return sent


# ── Event helpers (called from order/prediction code) ───────

def notify_order_executed(symbol: str, side: str, quantity: float, price: float):
    """Notify after a live order is executed."""
    price_fmt = f"${price:,.2f}" if price else "market"
    send_push_to_all_users(
        title="Order Executed",
        body=f"{side} {quantity} {symbol} @ {price_fmt}",
        data={"screen": "/live-trading", "type": "order"},
    )


def notify_auto_trade(symbol: str, side: str, price: float, confidence: float):
    """Notify after auto-trader places an order."""
    send_push_to_all_users(
        title="Auto Trade",
        body=f"AURA {side.lower()} {symbol} @ ${price:,.2f} (confidence: {confidence:.0%})",
        data={"screen": "/auto-trading", "type": "auto_trade"},
    )


def notify_high_confidence(symbol: str, action: str, confidence: float):
    """Notify when AI prediction has very high confidence."""
    send_push_to_all_users(
        title="High Confidence Signal",
        body=f"{symbol}: {action.upper()} signal with {confidence:.0%} confidence",
        data={"screen": "/ai-predictions", "type": "high_confidence"},
    )
