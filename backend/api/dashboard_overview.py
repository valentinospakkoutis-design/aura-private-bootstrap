"""
dashboard_overview.py — GET /api/dashboard/overview
Επιστρέφει για κάθε symbol: smart_score, direction, price, pct_change_24h, rsi_1h, open_positions_count, open_pnl

Προστίθεται στο backend/api/dashboard_overview.py
Και γίνεται include στο main.py:
    from api.dashboard_overview import router as dashboard_router
    app.include_router(dashboard_router)
"""

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Optional

import httpx
from fastapi import APIRouter, Depends

log = logging.getLogger("aura.dashboard")

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])

# ── Symbol universe (ίδιο με το Aura's symbol_map) ────────────────────────────
CRYPTO_SYMBOLS = [
    "BTCUSDC", "ETHUSDC", "BNBUSDC", "SOLUSDC", "XRPUSDC",
    "ADAUSDC", "AVAXUSDC", "DOTUSDC", "MATICUSDC", "LINKUSDC",
    "UNIUSDC", "ATOMUSDC", "LTCUSDC", "ETCUSDC", "XLMUSDC",
    "ALGOUSDC", "VETUSDC", "FILUSDC", "TRXUSDC", "NEARUSDC",
    "FTMUSDC", "SANDUSDC", "MANAUSDC", "AXSUSDC", "GALAUSDC",
    "CHZUSDC", "APEUSDC",
]

METALS_SYMBOLS = ["SILVER"]   # MT5 bridge

EQUITY_SYMBOLS = [
    "ES=F",    # S&P 500 futures
    "YM=F",    # Dow Jones futures
    "^GDAXI",  # DAX
    "^FTSE",   # FTSE 100
    "BAC",     # Bank of America
]

ALL_SYMBOLS = CRYPTO_SYMBOLS + METALS_SYMBOLS + EQUITY_SYMBOLS

CATEGORY_MAP = {s: "crypto"   for s in CRYPTO_SYMBOLS}
CATEGORY_MAP.update({s: "metals"  for s in METALS_SYMBOLS})
CATEGORY_MAP.update({s: "equities" for s in EQUITY_SYMBOLS})

# ── Cache (60s TTL) ────────────────────────────────────────────────────────────
_cache: dict = {}
_cache_ts: float = 0.0
CACHE_TTL = 60


# ── Helpers ────────────────────────────────────────────────────────────────────

def _score_to_direction(score: Optional[float]) -> str:
    if score is None:
        return "HOLD"
    if score >= 75:
        return "BUY"
    if score <= 25:
        return "SELL"
    return "HOLD"


def _score_color(score: Optional[float]) -> str:
    if score is None:
        return "neutral"
    if score >= 75:
        return "green"
    if score <= 25:
        return "red"
    if score >= 60:
        return "lime"
    if score <= 40:
        return "orange"
    return "neutral"


async def _fetch_smart_scores() -> dict:
    """Καλεί το εσωτερικό /api/ai/signal-quality endpoint."""
    try:
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.get("http://localhost:8080/api/ai/signal-quality")
            if r.status_code == 200:
                data = r.json()
                # Αναμένουμε list of {symbol, smart_score, ...} ή dict
                if isinstance(data, list):
                    return {item["symbol"]: item for item in data}
                if isinstance(data, dict):
                    return data
    except Exception as e:
        log.warning("signal-quality fetch failed: %s", e)
    return {}


async def _fetch_paper_positions() -> dict:
    """Καλεί το /api/auto-trading/paper-portfolio και ομαδοποιεί ανά symbol."""
    positions_by_symbol: dict = {}
    try:
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.get("http://localhost:8080/api/auto-trading/paper-portfolio")
            if r.status_code == 200:
                data = r.json()
                positions = data.get("positions", data) if isinstance(data, dict) else data
                if isinstance(positions, list):
                    for pos in positions:
                        sym = pos.get("symbol", "")
                        if sym not in positions_by_symbol:
                            positions_by_symbol[sym] = {"count": 0, "pnl": 0.0}
                        positions_by_symbol[sym]["count"] += 1
                        positions_by_symbol[sym]["pnl"] += float(pos.get("pnl", 0) or 0)
    except Exception as e:
        log.warning("paper-portfolio fetch failed: %s", e)
    return positions_by_symbol


async def _fetch_prices_crypto(symbols: list[str]) -> dict:
    """Τιμές crypto από Binance REST (δωρεάν, no auth)."""
    prices = {}
    try:
        # Binance ticker/24hr για πολλά symbols με μία κλήση
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.get("https://api.binance.com/api/v3/ticker/24hr")
            if r.status_code == 200:
                for item in r.json():
                    sym = item.get("symbol", "")
                    if sym in symbols:
                        prices[sym] = {
                            "price": float(item.get("lastPrice", 0)),
                            "pct_change_24h": float(item.get("priceChangePercent", 0)),
                        }
    except Exception as e:
        log.warning("Binance prices fetch failed: %s", e)
    return prices


async def _fetch_prices_metals() -> dict:
    """Τιμή Silver από MT5 bridge."""
    prices = {}
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.get("http://100.112.170.7:8765/api/xag/snapshot")
            if r.status_code == 200:
                data = r.json()
                prices["SILVER"] = {
                    "price": float(data.get("price", 0)),
                    "pct_change_24h": None,  # bridge δεν δίνει 24h change
                }
    except Exception as e:
        log.warning("MT5 bridge fetch failed: %s", e)
    return prices


async def _fetch_rsi_1h(symbol: str, category: str) -> Optional[float]:
    """RSI 1h — από MT5 bridge για metals, από signal-quality για τα υπόλοιπα."""
    if category == "metals":
        try:
            async with httpx.AsyncClient(timeout=10) as c:
                r = await c.get("http://100.112.170.7:8765/api/xag/snapshot")
                if r.status_code == 200:
                    return float(r.json().get("rsi_1h", 0) or 0)
        except Exception:
            pass
    return None  # Για crypto/equities το παίρνουμε από signal-quality


# ── Main endpoint ──────────────────────────────────────────────────────────────

@router.get("/overview")
async def overview():
    """
    Επιστρέφει snapshot όλων των symbols με smart_score, direction, price, pct_change_24h, rsi_1h, positions.
    Cache 60s.
    """
    global _cache, _cache_ts
    now = time.monotonic()
    if _cache and (now - _cache_ts) < CACHE_TTL:
        return _cache

    # Parallel fetches
    scores_task   = asyncio.create_task(_fetch_smart_scores())
    positions_task = asyncio.create_task(_fetch_paper_positions())
    prices_crypto_task = asyncio.create_task(_fetch_prices_crypto(CRYPTO_SYMBOLS))
    prices_metals_task = asyncio.create_task(_fetch_prices_metals())

    scores, positions, prices_crypto, prices_metals = await asyncio.gather(
        scores_task, positions_task, prices_crypto_task, prices_metals_task,
        return_exceptions=True
    )

    # Fallback αν κάποιο έπεσε
    if isinstance(scores, Exception):       scores = {}
    if isinstance(positions, Exception):    positions = {}
    if isinstance(prices_crypto, Exception): prices_crypto = {}
    if isinstance(prices_metals, Exception): prices_metals = {}

    all_prices = {**prices_crypto, **prices_metals}

    result = {"crypto": [], "metals": [], "equities": [], "asof": datetime.now(timezone.utc).isoformat()}

    for sym in ALL_SYMBOLS:
        category = CATEGORY_MAP[sym]
        score_data = scores.get(sym, {})
        smart_score = score_data.get("smart_score") if isinstance(score_data, dict) else None
        rsi_1h = score_data.get("rsi_1h") if isinstance(score_data, dict) else None
        price_data = all_prices.get(sym, {})
        pos_data = positions.get(sym, {"count": 0, "pnl": 0.0})

        entry = {
            "symbol": sym,
            "category": category,
            "smart_score": smart_score,
            "direction": _score_to_direction(smart_score),
            "color": _score_color(smart_score),
            "price": price_data.get("price"),
            "pct_change_24h": price_data.get("pct_change_24h"),
            "rsi_1h": rsi_1h,
            "open_positions": pos_data.get("count", 0),
            "open_pnl": round(pos_data.get("pnl", 0.0), 2),
        }
        result[category].append(entry)

    # Sort by smart_score desc within each category
    for cat in ("crypto", "metals", "equities"):
        result[cat].sort(key=lambda x: (x["smart_score"] or 0), reverse=True)

    _cache = result
    _cache_ts = now
    return result
