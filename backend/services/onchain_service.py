"""Free on-chain and market structure signals for crypto assets."""

from typing import Dict

import httpx

from cache.connection import cache_get, cache_set
from services.morning_briefing import get_fear_greed_index

ONCHAIN_SYMBOLS = [
    "BTCUSDC", "ETHUSDC", "BNBUSDC",
    "SOLUSDC", "ADAUSDC", "XRPUSDC",
]

TTL_SECONDS = 300
BINANCE_FAPI_BASE = "https://fapi.binance.com"


def _futures_symbol(symbol: str) -> str:
    return symbol.upper().replace("USDC", "USDT")


def get_binance_funding_rate(symbol: str) -> float:
    fut_symbol = _futures_symbol(symbol)
    with httpx.Client(timeout=5.0) as client:
        response = client.get(
            f"{BINANCE_FAPI_BASE}/fapi/v1/fundingRate",
            params={"symbol": fut_symbol, "limit": 1},
        )
        response.raise_for_status()
        data = response.json()
    return float(data[0].get("fundingRate", 0.0)) if data else 0.0


def get_binance_open_interest(symbol: str) -> float:
    fut_symbol = _futures_symbol(symbol)
    with httpx.Client(timeout=5.0) as client:
        response = client.get(
            f"{BINANCE_FAPI_BASE}/fapi/v1/openInterest",
            params={"symbol": fut_symbol},
        )
        response.raise_for_status()
        data = response.json()
    return float(data.get("openInterest", 0.0)) if isinstance(data, dict) else 0.0


def get_binance_ls_ratio(symbol: str) -> float:
    fut_symbol = _futures_symbol(symbol)
    with httpx.Client(timeout=5.0) as client:
        response = client.get(
            f"{BINANCE_FAPI_BASE}/futures/data/globalLongShortAccountRatio",
            params={"symbol": fut_symbol, "period": "1h", "limit": 1},
        )
        response.raise_for_status()
        data = response.json()
    return float(data[0].get("longShortRatio", 1.0)) if data else 1.0


def get_onchain_signals(symbol: str) -> Dict:
    """Collect free on-chain proxies and return a normalized sentiment bundle."""
    symbol = symbol.upper()
    cache_key = f"onchain:{symbol}"
    cached = cache_get(cache_key)
    if isinstance(cached, dict):
        return cached

    signals: Dict = {"symbol": symbol}

    try:
        funding = get_binance_funding_rate(symbol)
        signals["funding_rate"] = funding
        signals["funding_bearish"] = funding > 0.01
    except Exception as e:
        print(f"[ONCHAIN] Funding rate failed: {e}")

    try:
        oi = get_binance_open_interest(symbol)
        signals["open_interest"] = oi
    except Exception as e:
        print(f"[ONCHAIN] Open interest failed: {e}")

    try:
        fg = int(get_fear_greed_index())
        signals["fear_greed"] = fg
        signals["extreme_fear"] = fg < 20
        signals["extreme_greed"] = fg > 80
    except Exception as e:
        print(f"[ONCHAIN] Fear & Greed failed: {e}")

    try:
        ls_ratio = get_binance_ls_ratio(symbol)
        signals["long_short_ratio"] = ls_ratio
        signals["overleveraged_longs"] = ls_ratio > 2.0
    except Exception as e:
        print(f"[ONCHAIN] L/S ratio failed: {e}")

    bullish_count = sum([
        not signals.get("funding_bearish", False),
        not signals.get("extreme_greed", False),
        not signals.get("overleveraged_longs", False),
        not signals.get("extreme_fear", False),
    ])

    signals["onchain_score"] = bullish_count / 4
    signals["onchain_sentiment"] = (
        "bullish" if bullish_count >= 3
        else "bearish" if bullish_count <= 1
        else "neutral"
    )

    cache_set(cache_key, signals, expire=TTL_SECONDS)
    return signals
