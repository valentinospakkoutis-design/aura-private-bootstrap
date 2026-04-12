"""
Detects abnormal market conditions that should pause auto-trading.
Flash crashes, manipulation, extreme volatility spikes.
"""

import json
from datetime import datetime
from typing import List

ANOMALY_THRESHOLDS = {
    "price_spike_pct": 0.05,
    "volume_spike_multiplier": 5,
    "spread_spike_pct": 0.02,
    "vix_spike": 10,
}


def _store_price(redis_client, symbol: str, price: float):
    """Store price snapshot in Redis rolling window."""
    if redis_client is None or not symbol:
        return

    key = f"price_history:{symbol}"
    redis_client.lpush(
        key,
        json.dumps({"price": float(price), "ts": datetime.utcnow().isoformat()}),
    )
    redis_client.ltrim(key, 0, 59)
    redis_client.expire(key, 3600)


def detect_price_anomaly(symbol: str, current_price: float, redis_client, window_minutes: int = 5) -> dict:
    """Detect sudden price spikes using Redis price history."""
    symbol_u = (symbol or "").upper()
    key = f"price_history:{symbol_u}"

    try:
        if redis_client is None or current_price <= 0:
            return {"anomaly": False, "symbol": symbol_u}

        raw = redis_client.lrange(key, 0, window_minutes)
        if len(raw) < 2:
            _store_price(redis_client, symbol_u, current_price)
            return {"anomaly": False, "symbol": symbol_u}

        prices = []
        for r in raw:
            if isinstance(r, bytes):
                r = r.decode("utf-8")
            prices.append(float(json.loads(r).get("price", 0.0)))

        oldest_price = float(prices[-1]) if prices else 0.0
        if oldest_price <= 0:
            _store_price(redis_client, symbol_u, current_price)
            return {"anomaly": False, "symbol": symbol_u}

        price_change_pct = abs(float(current_price) - oldest_price) / oldest_price
        is_anomaly = price_change_pct > ANOMALY_THRESHOLDS["price_spike_pct"]

        _store_price(redis_client, symbol_u, current_price)

        result = {
            "anomaly": bool(is_anomaly),
            "symbol": symbol_u,
            "price_change_pct": round(float(price_change_pct), 4),
            "current_price": float(current_price),
            "reference_price": float(oldest_price),
            "threshold": float(ANOMALY_THRESHOLDS["price_spike_pct"]),
            "detected_at": datetime.utcnow().isoformat(),
        }

        if is_anomaly:
            redis_client.setex(f"anomaly:active:{symbol_u}", 1800, json.dumps(result))
            print(f"[ANOMALY] {symbol_u}: {price_change_pct:.1%} spike detected - PAUSING TRADING")

        return result
    except Exception as e:
        print(f"[ANOMALY] Error for {symbol_u}: {e}")
        return {"anomaly": False, "symbol": symbol_u, "error": str(e)}


def is_trading_paused(symbol: str, redis_client) -> bool:
    """Check if trading is paused due to active anomaly."""
    symbol_u = (symbol or "").upper()
    try:
        if redis_client is None or not symbol_u:
            return False
        return int(redis_client.exists(f"anomaly:active:{symbol_u}")) > 0
    except Exception:
        return False


def get_active_anomalies(redis_client, symbols: List[str]) -> list:
    """Get all currently active anomalies."""
    active = []
    if redis_client is None:
        return active

    for symbol in symbols:
        symbol_u = (symbol or "").upper()
        try:
            raw = redis_client.get(f"anomaly:active:{symbol_u}")
            if not raw:
                continue
            if isinstance(raw, bytes):
                raw = raw.decode("utf-8")
            active.append(json.loads(raw))
        except Exception:
            continue

    return active
