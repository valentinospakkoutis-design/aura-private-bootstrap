"""
api/xag.py — XAGUSD-STD snapshot + OHLC endpoints
Data source: yfinance (SI=F = Silver futures, proxy for XAGUSD-STD)
Phase 2: no auth, no MT5. Auth added in Phase 7.
"""

from fastapi import APIRouter, HTTPException, Query
from datetime import datetime, timezone
import time

router = APIRouter(prefix="/api/xag", tags=["xag"])

# ── Cache ────────────────────────────────────────────────────────────────────
_snapshot_cache: dict = {}
_SNAPSHOT_TTL = 10  # seconds

_ohlc_cache: dict = {}
_OHLC_TTL = 60  # seconds (closed bars don't change)


# ── RSI(14) — pure pandas, no pandas-ta dependency ──────────────────────────
def _rsi14(closes: list[float]) -> float | None:
    """Wilder-smoothed RSI(14) matching MetaTrader convention."""
    import pandas as pd
    if len(closes) < 15:
        return None
    s = pd.Series(closes, dtype=float)
    delta = s.diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)
    # First averages (SMA seed)
    avg_gain = gain.iloc[1:15].mean()
    avg_loss = loss.iloc[1:15].mean()
    # Wilder smoothing for the rest
    for i in range(15, len(closes)):
        avg_gain = (avg_gain * 13 + gain.iloc[i]) / 14
        avg_loss = (avg_loss * 13 + loss.iloc[i]) / 14
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(100 - (100 / (1 + rs)), 2)


# ── yfinance helpers ─────────────────────────────────────────────────────────
def _fetch_rsi(symbol: str, interval: str, period: str) -> float | None:
    """Fetch OHLCV from yfinance and compute RSI(14) on close prices."""
    try:
        import yfinance as yf
        df = yf.download(symbol, interval=interval, period=period,
                         progress=False, auto_adjust=True,
                         multi_level_index=False)
        if df.empty or len(df) < 15:
            return None
        closes = df["Close"].dropna().tolist()
        # flatten if yfinance returns multi-level columns
        if isinstance(closes[0], (list, tuple)):
            closes = [c[0] for c in closes]
        return _rsi14([float(c) for c in closes])
    except Exception as e:
        print(f"[xag] RSI fetch error {symbol}/{interval}: {e}")
        return None


def _fetch_snapshot() -> dict:
    """Fetch spot price + RSI for 1m, 15m, 1h."""
    import yfinance as yf

    tick = yf.Ticker("SI=F")
    info = tick.fast_info
    # fast_info gives last_price; fallback to history
    try:
        price = float(info.last_price)
    except Exception:
        hist = tick.history(period="1d", interval="1m")
        if hist.empty:
            raise ValueError("yfinance returned no price data for SI=F")
        price = float(hist["Close"].iloc[-1])

    rsi_1m  = _fetch_rsi("SI=F", "1m",  "1d")
    rsi_15m = _fetch_rsi("SI=F", "15m", "5d")
    rsi_1h  = _fetch_rsi("SI=F", "1h",  "30d")

    return {
        "symbol":  "XAGUSD-STD",
        "price":   round(price, 3),
        "bid":     round(price - 0.025, 3),
        "ask":     round(price + 0.025, 3),
        "rsi_1m":  rsi_1m,
        "rsi_15m": rsi_15m,
        "rsi_1h":  rsi_1h,
        "asof":    datetime.now(timezone.utc).isoformat(),
        "source":  "yfinance/SI=F",
    }


def _fetch_ohlc(tf: str, n: int) -> list[dict]:
    """Fetch historical OHLC bars."""
    import yfinance as yf

    tf_map = {
        "1m":  ("1m",  "1d"),
        "5m":  ("5m",  "5d"),
        "15m": ("15m", "10d"),
        "1h":  ("1h",  "30d"),
    }
    if tf not in tf_map:
        raise ValueError(f"Unknown timeframe: {tf}")

    interval, period = tf_map[tf]
    df = yf.download("SI=F", interval=interval, period=period,
                     progress=False, auto_adjust=True,
                     multi_level_index=False)
    if df.empty:
        return []

    df = df.tail(n)
    bars = []
    for ts, row in df.iterrows():
        try:
            # handle both single and multi-level columns
            o = float(row["Open"].iloc[0]   if hasattr(row["Open"], "iloc")   else row["Open"])
            h = float(row["High"].iloc[0]   if hasattr(row["High"], "iloc")   else row["High"])
            l = float(row["Low"].iloc[0]    if hasattr(row["Low"], "iloc")    else row["Low"])
            c = float(row["Close"].iloc[0]  if hasattr(row["Close"], "iloc")  else row["Close"])
            v = int(row["Volume"].iloc[0]   if hasattr(row["Volume"], "iloc") else row["Volume"])
            t = int(ts.timestamp())
            bars.append({"time": t, "open": round(o,3), "high": round(h,3),
                         "low": round(l,3), "close": round(c,3), "volume": v})
        except Exception:
            continue

    return bars


# ── Endpoints ────────────────────────────────────────────────────────────────
@router.get("/snapshot")
async def snapshot():
    """
    Returns current silver price + RSI(14) on 1m / 15m / 1h.
    Cached for 10 seconds to avoid hammering yfinance.
    """
    now = time.time()
    if _snapshot_cache.get("ts", 0) + _SNAPSHOT_TTL > now:
        return _snapshot_cache["data"]

    try:
        data = _fetch_snapshot()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Data fetch failed: {e}")

    _snapshot_cache["data"] = data
    _snapshot_cache["ts"]   = now
    return data


@router.get("/ohlc")
async def ohlc(
    tf: str = Query("1m", pattern="^(1m|5m|15m|1h)$"),
    n:  int = Query(200,  ge=1, le=500),
):
    """
    Returns up to n historical OHLC bars for the given timeframe.
    Closed bars are cached for 60 seconds.
    """
    cache_key = f"{tf}:{n}"
    now       = time.time()
    if _ohlc_cache.get(cache_key, {}).get("ts", 0) + _OHLC_TTL > now:
        return _ohlc_cache[cache_key]["data"]

    try:
        bars = _fetch_ohlc(tf, n)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"OHLC fetch failed: {e}")

    _ohlc_cache[cache_key] = {"data": bars, "ts": now}
    return bars
