"""
api/xag.py — XAGUSD-STD snapshot + OHLC endpoints
Data source: yfinance (SI=F = Silver futures, PROXY for XAGUSD-STD)

⚠️  SI=F is a CME Silver futures contract, NOT a spot XAG/USD feed.
    bid/ask are synthetic (price ± 0.025) — do NOT use for execution.
    Replace with a real broker feed before live trading.

Phase 2: no auth, no MT5. Auth added in Phase 7.
"""

from fastapi import APIRouter, HTTPException, Query
from starlette.concurrency import run_in_threadpool
from datetime import datetime, timezone
import math
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
    # Edge cases: flat series → neutral 50; no losses → overbought 100
    if avg_gain == 0 and avg_loss == 0:
        return 50.0
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    result = round(100 - (100 / (1 + rs)), 2)
    # Guard against NaN/Inf that could slip through with bad data
    if not math.isfinite(result):
        return None
    return result


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
        if closes and isinstance(closes[0], (list, tuple)):
            closes = [c[0] for c in closes]
        floats = [float(c) for c in closes if math.isfinite(float(c))]
        return _rsi14(floats)
    except Exception as e:
        print(f"[xag] RSI fetch error {symbol}/{interval}: {e}")
        return None


def _fetch_snapshot() -> dict:
    """
    Fetch spot price + RSI for 1m, 15m, 1h.

    Returns three timestamps:
      fetched_at   — UTC wall-clock when this function completed
      market_asof  — timestamp of the last bar yfinance returned (data age)
      stale        — True if market_asof is >15 min old (weekend / market closed)
    """
    import yfinance as yf

    tick = yf.Ticker("SI=F")
    info = tick.fast_info

    market_asof: str | None = None

    # fast_info gives last_price; fallback to history
    try:
        price = float(info.last_price)
        # Attempt to get the timestamp of the last trade
        try:
            raw_ts = getattr(info, "last_volume_traded", None) or None
            # fast_info doesn't expose timestamp directly; use 1m history
            hist1m = tick.history(period="1d", interval="1m")
            if not hist1m.empty:
                last_bar_ts = hist1m.index[-1]
                market_asof = last_bar_ts.tz_convert("UTC").isoformat()
        except Exception:
            pass
    except Exception:
        hist = tick.history(period="1d", interval="1m")
        if hist.empty:
            raise ValueError("yfinance returned no price data for SI=F")
        price = float(hist["Close"].iloc[-1])
        last_bar_ts = hist.index[-1]
        market_asof = last_bar_ts.tz_convert("UTC").isoformat()

    # Validate price
    if not math.isfinite(price) or price <= 0:
        raise ValueError(f"Invalid price from yfinance: {price}")

    rsi_1m  = _fetch_rsi("SI=F", "1m",  "1d")
    rsi_15m = _fetch_rsi("SI=F", "15m", "5d")
    rsi_1h  = _fetch_rsi("SI=F", "1h",  "30d")

    fetched_at = datetime.now(timezone.utc).isoformat()

    # Determine staleness: >15 min since last bar
    stale = False
    if market_asof:
        try:
            from datetime import timedelta
            bar_dt = datetime.fromisoformat(market_asof)
            now_utc = datetime.now(timezone.utc)
            stale = (now_utc - bar_dt) > timedelta(minutes=15)
        except Exception:
            stale = True  # conservative: unknown age → treat as stale

    return {
        "symbol":      "XAGUSD-STD",
        "source":      "yfinance/SI=F (proxy — synthetic bid/ask)",
        "price":       round(price, 3),
        "bid":         round(price - 0.025, 3),   # synthetic — not for execution
        "ask":         round(price + 0.025, 3),   # synthetic — not for execution
        "rsi_1m":      rsi_1m,
        "rsi_15m":     rsi_15m,
        "rsi_1h":      rsi_1h,
        "fetched_at":  fetched_at,    # when this response was produced
        "market_asof": market_asof,   # age of the underlying price data
        "stale":       stale,         # True when market is closed / data is old
    }


def _fetch_ohlc(tf: str, n: int) -> list[dict]:
    """Fetch historical OHLC bars (closed bars only)."""
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
    if df is None or df.empty:
        return []

    # Normalise columns (guard against MultiIndex)
    if hasattr(df.columns, "levels"):
        df.columns = df.columns.get_level_values(0)

    required = {"Open", "High", "Low", "Close", "Volume"}
    if not required.issubset(set(df.columns)):
        return []

    # Sort and drop duplicates
    df = df.sort_index()
    df = df[~df.index.duplicated(keep="last")]

    # Drop rows with NaN OHLC
    df = df.dropna(subset=["Open", "High", "Low", "Close"])

    # Exclude the last (potentially open/incomplete) bar
    if len(df) > 1:
        df = df.iloc[:-1]

    df = df.tail(n)

    bars = []
    for ts, row in df.iterrows():
        try:
            o = float(row["Open"])
            h = float(row["High"])
            l = float(row["Low"])
            c = float(row["Close"])
            v = float(row["Volume"]) if not math.isnan(float(row["Volume"])) else 0
            # Validate OHLC sanity
            if not all(math.isfinite(x) and x > 0 for x in (o, h, l, c)):
                continue
            if not (l <= o <= h and l <= c <= h):
                continue
            t = int(ts.timestamp())
            bars.append({"time": t, "open": round(o, 3), "high": round(h, 3),
                         "low": round(l, 3), "close": round(c, 3), "volume": int(v)})
        except Exception:
            continue

    return bars


# ── Endpoints ────────────────────────────────────────────────────────────────
@router.get("/snapshot")
async def snapshot():
    """
    Returns current silver price + RSI(14) on 1m / 15m / 1h.
    Cached for 10 seconds to avoid hammering yfinance.

    Note: price is from SI=F (CME Silver futures) — a PROXY.
    bid/ask are synthetic (±0.025). Replace with broker feed for execution.
    """
    now = time.monotonic()
    cached_ts = _snapshot_cache.get("ts", 0)
    if cached_ts and (now - cached_ts) < _SNAPSHOT_TTL:
        return _snapshot_cache["data"]

    try:
        data = await run_in_threadpool(_fetch_snapshot)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Data fetch failed: {e}")

    _snapshot_cache["data"] = data
    _snapshot_cache["ts"]   = time.monotonic()
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
    now       = time.monotonic()
    cached    = _ohlc_cache.get(cache_key, {})
    if cached.get("ts", 0) and (now - cached["ts"]) < _OHLC_TTL:
        return cached["data"]

    try:
        bars = await run_in_threadpool(_fetch_ohlc, tf, n)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"OHLC fetch failed: {e}")

    _ohlc_cache[cache_key] = {"data": bars, "ts": time.monotonic()}
    return bars
