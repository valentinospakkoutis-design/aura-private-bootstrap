import json
from datetime import datetime

import yfinance as yf

REGIME_THRESHOLDS = {
    "calm": (0, 15),
    "normal": (15, 20),
    "elevated": (20, 30),
    "fearful": (30, 40),
    "crisis": (40, 999),
}


def _regime_confidence_multiplier(regime: str) -> float:
    """How much to trust ML signals in this regime."""
    return {
        "calm": 1.0,
        "normal": 0.9,
        "elevated": 0.7,
        "fearful": 0.5,
        "crisis": 0.3,
    }.get(regime, 0.5)


def _regime_position_multiplier(regime: str) -> float:
    """How much of normal position size to use."""
    return {
        "calm": 1.0,
        "normal": 0.85,
        "elevated": 0.6,
        "fearful": 0.4,
        "crisis": 0.2,
    }.get(regime, 0.5)


def detect_regime(vix_value: float) -> dict:
    """Detect market regime from VIX level."""
    for regime, (low, high) in REGIME_THRESHOLDS.items():
        if low <= vix_value < high:
            return {
                "regime": regime,
                "vix": round(vix_value, 2),
                "confidence_multiplier": _regime_confidence_multiplier(regime),
                "position_size_multiplier": _regime_position_multiplier(regime),
                "detected_at": datetime.utcnow().isoformat(),
            }
    return {
        "regime": "unknown",
        "vix": float(vix_value),
        "confidence_multiplier": 0.5,
        "position_size_multiplier": 0.5,
        "detected_at": datetime.utcnow().isoformat(),
    }


async def fetch_and_cache_vix(redis_client) -> dict:
    """Fetch VIX from yfinance and cache in Redis for 1 hour."""
    try:
        vix = yf.Ticker("^VIX")
        hist = vix.history(period="1d")
        if hist.empty:
            raise ValueError("No VIX data")

        vix_value = float(hist["Close"].iloc[-1])
        regime = detect_regime(vix_value)

        if redis_client is not None:
            redis_client.setex("regime:current", 3600, json.dumps(regime))

        print(f"[REGIME] VIX={vix_value:.1f} -> {regime['regime'].upper()}")
        return regime
    except Exception as e:
        print(f"[REGIME] Error fetching VIX: {e}")
        return detect_regime(20.0)


def get_current_regime(redis_client) -> dict:
    """Get cached regime from Redis, return normal if missing."""
    if redis_client is not None:
        try:
            cached = redis_client.get("regime:current")
            if cached:
                if isinstance(cached, bytes):
                    cached = cached.decode("utf-8")
                return json.loads(cached)
        except Exception:
            pass

    return detect_regime(20.0)
