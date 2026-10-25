"""Orderbook Imbalance (L2) — gate based on bid/ask pressure.

Uses Binance REST depth snapshot (top 20 levels) via HTTPS.
Result cached in Redis for 10s to avoid hammering the API.

Imbalance = bid_volume / (bid_volume + ask_volume)
  > 0.65  → strong buy pressure  → allow BUY,  reduce SELL size
  < 0.35  → strong sell pressure → allow SELL, reduce BUY size
  0.35–0.65 → neutral            → no effect

Crypto-only. Falls back silently on any error.
"""

import json
import logging
import time
from typing import Optional

logger = logging.getLogger(__name__)

BINANCE_REST = "https://api.binance.com/api/v3/depth"
_CACHE_TTL = 10   # seconds
_DEPTH_LIMIT = 20  # top 20 bid/ask levels


def _sym_to_binance(symbol: str) -> str:
    """BTCUSDC -> BTCUSDC (already correct for Binance spot)."""
    return symbol.upper().replace("-", "")


def get_orderbook_imbalance(symbol: str, redis_client=None) -> dict:
    """Return {imbalance: float, bid_vol: float, ask_vol: float, signal: str, cached: bool}.

    signal is one of: "buy_pressure", "sell_pressure", "neutral", "unavailable"
    Falls back to {"imbalance": 0.5, "signal": "neutral"} on any error.
    """
    _default = {"imbalance": 0.5, "bid_vol": 0.0, "ask_vol": 0.0, "signal": "neutral", "cached": False}
    try:
        cache_key = f"orderbook_imbalance:{symbol.upper()}"

        # Try Redis cache first
        if redis_client is not None:
            try:
                cached = redis_client.get(cache_key)
                if cached:
                    data = json.loads(cached)
                    data["cached"] = True
                    return data
            except Exception:
                pass

        # Fetch fresh snapshot
        import urllib.request
        binance_sym = _sym_to_binance(symbol)
        url = f"{BINANCE_REST}?symbol={binance_sym}&limit={_DEPTH_LIMIT}"
        req = urllib.request.Request(url, headers={"User-Agent": "aura-trading/1.0"})
        with urllib.request.urlopen(req, timeout=3) as resp:
            raw = json.loads(resp.read())

        bids = raw.get("bids", [])
        asks = raw.get("asks", [])
        if not bids or not asks:
            return {**_default, "signal": "unavailable"}

        bid_vol = sum(float(b[1]) for b in bids)
        ask_vol = sum(float(a[1]) for a in asks)
        total = bid_vol + ask_vol
        if total <= 0:
            return {**_default, "signal": "unavailable"}

        imbalance = bid_vol / total

        if imbalance > 0.65:
            signal = "buy_pressure"
        elif imbalance < 0.35:
            signal = "sell_pressure"
        else:
            signal = "neutral"

        result = {
            "imbalance": round(imbalance, 4),
            "bid_vol": round(bid_vol, 4),
            "ask_vol": round(ask_vol, 4),
            "signal": signal,
            "cached": False,
        }

        # Cache in Redis
        if redis_client is not None:
            try:
                redis_client.setex(cache_key, _CACHE_TTL, json.dumps(result))
            except Exception:
                pass

        return result

    except Exception as _e:
        logger.debug(f"[orderbook_imbalance] {symbol}: {_e}")
        return {**_default, "signal": "unavailable"}
