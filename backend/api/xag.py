"""
api/xag.py — XAGUSD-STD snapshot + OHLC endpoints
Data source: yfinance (SI=F = Silver futures, proxy for XAGUSD-STD)
Phase 7: all routes require JWT auth except /healthz (handled separately).
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from datetime import datetime, timezone
import time
from typing import Any

from api.xag_auth import xag_require_auth

_AUTH = [Depends(xag_require_auth)]

router = APIRouter(prefix="/api/xag", tags=["xag"])

# ── Cache ────────────────────────────────────────────────────────────────────
_snapshot_cache: dict = {}
_SNAPSHOT_TTL = 10  # seconds

_ohlc_cache: dict = {}
_OHLC_TTL = 60  # seconds (closed bars don't change)

_positions_cache: dict[int, dict[str, Any]] = {}  # keyed by user_id
_POSITIONS_TTL = 60  # seconds


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
        return 50.0 if avg_gain == 0 else 100.0
    rs = avg_gain / avg_loss
    return round(100 - (100 / (1 + rs)), 2)



import httpx as _httpx
_BRIDGE_URL = __import__('os').getenv("MT5_BRIDGE_URL", "")
_BRIDGE_TIMEOUT = 5.0

def _bridge_get(path, params=None):
    if not _BRIDGE_URL:
        return None
    try:
        r = _httpx.get(f"{_BRIDGE_URL}{path}", params=params, timeout=_BRIDGE_TIMEOUT)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"[xag] bridge error {path}: {e}")
        return None

def _fetch_snapshot():
    from datetime import datetime, timezone
    data = _bridge_get("/api/xag/snapshot")
    if data and data.get("price"):
        # Get daily open from first candle of today
        daily_open = None
        try:
            from datetime import datetime, timezone
            ohlc = _bridge_get("/api/xag/ohlc")
            if ohlc:
                today_ts = int(datetime.now(timezone.utc).replace(hour=0,minute=0,second=0,microsecond=0).timestamp())
                today = [c for c in ohlc if c["time"] >= today_ts]
                if today:
                    daily_open = today[0]["open"]
        except Exception:
            pass
        return {"symbol": "SILVER", "price": data["price"],
                "bid": data.get("bid", data["price"]-0.02),
                "ask": data.get("ask", data["price"]+0.02),
                "spread": data.get("spread"),
                "rsi_1m": data.get("rsi_1m"), "rsi_15m": data.get("rsi_15m"),
                "rsi_1h": data.get("rsi_1h"), "asof": data.get("asof"),
                "daily_open": daily_open,
                "source": "mt5_bridge"}
    print("[xag] bridge unavailable, falling back to yfinance")
    import yfinance as yf
    tick = yf.Ticker("SI=F")
    try:
        price = float(tick.fast_info.last_price)
    except Exception:
        hist = tick.history(period="1d", interval="1m")
        price = float(hist["Close"].iloc[-1])
    # Compute RSI(14) on 1m / 15m / 1h from yfinance history
    def _rsi14(series):
        delta = series.diff()
        gain  = delta.clip(lower=0).rolling(14).mean()
        loss  = (-delta.clip(upper=0)).rolling(14).mean()
        rs    = gain / loss.replace(0, float("nan"))
        val   = (100 - 100 / (1 + rs)).iloc[-1]
        return round(float(val), 2) if not __import__("math").isnan(val) else None
    try:
        import pandas as pd
        h1m  = tick.history(period="5d",  interval="1m")["Close"]
        h15m = tick.history(period="5d",  interval="15m")["Close"]
        h1h  = tick.history(period="30d", interval="1h")["Close"]
        rsi_1m  = _rsi14(h1m)  if len(h1m)  >= 15 else None
        rsi_15m = _rsi14(h15m) if len(h15m) >= 15 else None
        rsi_1h  = _rsi14(h1h)  if len(h1h)  >= 15 else None
    except Exception as e:
        print(f"[xag] RSI calc failed: {e}")
        rsi_1m = rsi_15m = rsi_1h = None
    return {"symbol": "XAGUSD-STD", "price": round(price,3),
            "bid": round(price-0.025,3), "ask": round(price+0.025,3),
            "rsi_1m": rsi_1m, "rsi_15m": rsi_15m, "rsi_1h": rsi_1h,
            "asof": datetime.now(timezone.utc).isoformat(), "source": "yfinance/SI=F"}

def _fetch_ohlc(tf, n):
    data = _bridge_get("/api/xag/ohlc", params={"tf": tf, "n": n})
    if data and isinstance(data, list) and len(data) > 0:
        return data
    import yfinance as yf
    tf_map = {"1m":("1m","1d"),"5m":("5m","5d"),"15m":("15m","10d"),"1h":("1h","30d")}
    if tf not in tf_map:
        raise ValueError(f"Unknown timeframe: {tf}")
    interval, period = tf_map[tf]
    df = yf.download("SI=F", interval=interval, period=period, progress=False,
                     auto_adjust=True, multi_level_index=False)
    if df.empty:
        return []
    bars = []
    for ts, row in df.tail(n).iterrows():
        try:
            o=float(row["Open"].iloc[0] if hasattr(row["Open"],"iloc") else row["Open"])
            h=float(row["High"].iloc[0] if hasattr(row["High"],"iloc") else row["High"])
            l=float(row["Low"].iloc[0] if hasattr(row["Low"],"iloc") else row["Low"])
            c=float(row["Close"].iloc[0] if hasattr(row["Close"],"iloc") else row["Close"])
            v=int(row["Volume"].iloc[0] if hasattr(row["Volume"],"iloc") else row["Volume"])
            bars.append({"time":int(ts.timestamp()),"open":round(o,3),"high":round(h,3),
                         "low":round(l,3),"close":round(c,3),"volume":v})
        except Exception:
            continue
    return bars


# ── Endpoints# ── Endpoints ────────────────────────────────────────────────────────────────
_WARMUP_USER_ID = 1  # startup warmup only — not tied to any authenticated request

async def _warmup_positions_cache():
    """Background warmup — runs once at startup to pre-fill positions cache for user 1.

    This is a best-effort optimisation; the per-user authenticated endpoint
    will populate the correct cache entry for each user on first request.
    """
    import asyncio
    await asyncio.sleep(90)  # wait for uvicorn + DB to settle
    try:
        import yfinance as yf
        from services.paper_trading import PaperTradingService
        svc = PaperTradingService()
        raw = svc.get_portfolio(user_id=_WARMUP_USER_ID)
        symbols = [p["symbol"] for p in raw.get("positions", [])]
        _sym_map = {
            "ES1!": "ES=F", "YM1!": "YM=F", "DAX1!": "^GDAXI",
            "NQ1!": "NQ=F", "CL1!": "CL=F", "GC1!": "GC=F",
            "SI1!": "SI=F", "XAGUSD": "SI=F", "XAGUSDC": "SI=F",
            "ALGOUSDC": "ALGO-USD", "BTCUSDC": "BTC-USD",
            "ETHUSDC": "ETH-USD", "SOLUSDC": "SOL-USD",
            "ADAUSDC": "ADA-USD", "DOTUSDC": "DOT-USD",
            "LINKUSDC": "LINK-USD", "LTCUSDC": "LTC-USD",
            "UNIUSDC": "UNI-USD", "TRXUSDC": "TRX-USD",
        }
        current_prices = {}
        for sym in symbols:
            ticker = _sym_map.get(sym, sym)
            try:
                info = yf.Ticker(ticker).fast_info
                price = float(info.last_price)
                if price and price > 0:
                    current_prices[sym] = price
            except Exception:
                pass
        portfolio = svc.get_portfolio(user_id=_WARMUP_USER_ID, current_prices=current_prices)
        positions = []
        for pos in portfolio.get("positions", []):
            positions.append({
                "symbol":   pos["symbol"],
                "side":     "BUY",
                "quantity": round(float(pos["quantity"]), 4),
                "entry":    round(float(pos["avg_price"]), 3),
                "current":  round(float(pos["current_price"]), 3),
                "value":    round(float(pos["value"]), 2),
                "pnl":      round(float(pos["pnl"]), 2),
                "pnl_pct":  round(float(pos["pnl_percent"]), 2),
            })
        result = {
            "positions":   positions,
            "total_value": round(float(portfolio["total_value"]), 2),
            "cash":        round(float(portfolio["cash"]), 2),
            "total_pnl":   round(float(portfolio["total_pnl"]), 2),
            "count":       len(positions),
        }
        import time
        _positions_cache[_WARMUP_USER_ID] = {"data": result, "ts": time.time()}
        print("[xag] positions cache warmed up")
    except Exception as e:
        print(f"[xag] warmup failed: {e}")


@router.on_event("startup")
async def startup_warmup():
    import asyncio
    asyncio.create_task(_warmup_positions_cache())


@router.get("/snapshot", dependencies=_AUTH)
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


@router.get("/ohlc", dependencies=_AUTH)
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

@router.get("/signal", dependencies=_AUTH)
async def xag_signal():
    """Current Aura signal for XAGUSD-STD (via XAGUSDC model)."""
    try:
        from ai.asset_predictor import asset_predictor
        sig = asset_predictor.predict_price("XAGUSDC")
        return {
            "signal":           sig.get("recommendation"),
            "strength":         sig.get("recommendation_strength"),
            "confidence":       sig.get("confidence"),
            "trend":            sig.get("trend"),
            "regime":           sig.get("market_regime", {}).get("regime"),
            "price_change_pct": sig.get("price_change_percent"),
            "timestamp":        sig.get("timestamp"),
        }
    except Exception as e:
        return {"signal": None, "error": str(e)}

@router.get("/smart-score", dependencies=_AUTH)
async def xag_smart_score():
    """Smart Score για XAGUSDC χωρίς auth (dashboard use)."""
    try:
        from services.smart_score import smart_score_calculator
        result = smart_score_calculator.calculate_smart_score("XAGUSDC")
        return {
            "smart_score": round(result.get("smart_score", 0), 1),
            "recommendation": result.get("recommendation", "WAIT"),
            "rsi": round(result.get("signals", {}).get("rsi", {}).get("score", 50), 1),
            "mtf": round(result.get("signals", {}).get("multi_timeframe", {}).get("score", 50), 1),
            "threshold": 75,
        }
    except Exception as e:
        return {"smart_score": None, "error": str(e)}

@router.get("/paper-positions")
async def xag_paper_positions(token_data: dict = Depends(xag_require_auth)):
    """Paper trading positions for the authenticated user's portfolio."""
    # Extract and validate user_id from JWT sub claim — outside the catch-all
    # so HTTPException propagates correctly instead of being swallowed as a 200.
    raw_sub = token_data.get("sub")
    if raw_sub is None:
        raise HTTPException(status_code=401, detail="Token missing sub claim")
    try:
        user_id = int(raw_sub)
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=401,
            detail=f"Invalid sub claim in token: {raw_sub!r} (expected integer user_id)",
        )

    try:
        import yfinance as yf
        from services.paper_trading import PaperTradingService

        # Return per-user cached entry if fresh
        now = time.time()
        cached = _positions_cache.get(user_id, {})
        if cached.get("ts", 0) + _POSITIONS_TTL > now:
            return cached["data"]

        svc = PaperTradingService()
        # First pass: get positions to know which symbols we need
        raw = svc.get_portfolio(user_id=user_id)
        symbols = [p["symbol"] for p in raw.get("positions", [])]

        # Fetch live prices via yfinance
        # Map broker symbols to yfinance tickers
        _sym_map = {
            "ES1!": "ES=F", "YM1!": "YM=F", "DAX1!": "^GDAXI",
            "NQ1!": "NQ=F", "CL1!": "CL=F", "GC1!": "GC=F",
            "SI1!": "SI=F", "XAGUSD": "SI=F", "XAGUSDC": "SI=F",
            "ALGOUSDC": "ALGO-USD", "BTCUSDC": "BTC-USD",
            "ETHUSDC": "ETH-USD", "SOLUSDC": "SOL-USD",
            "ADAUSDC": "ADA-USD", "DOTUSDC": "DOT-USD",
            "LINKUSDC": "LINK-USD", "LTCUSDC": "LTC-USD",
            "UNIUSDC": "UNI-USD", "TRXUSDC": "TRX-USD",
        }
        current_prices = {}
        for sym in symbols:
            ticker = _sym_map.get(sym, sym)
            try:
                info = yf.Ticker(ticker).fast_info
                price = float(info.last_price)
                if price and price > 0:
                    current_prices[sym] = price
            except Exception:
                pass

        # Second pass: get portfolio with live prices
        portfolio = svc.get_portfolio(user_id=user_id, current_prices=current_prices)

        positions = []
        for pos in portfolio.get("positions", []):
            positions.append({
                "symbol":   pos["symbol"],
                "side":     "BUY",
                "quantity": round(float(pos["quantity"]), 4),
                "entry":    round(float(pos["avg_price"]), 3),
                "current":  round(float(pos["current_price"]), 3),
                "value":    round(float(pos["value"]), 2),
                "pnl":      round(float(pos["pnl"]), 2),
                "pnl_pct":  round(float(pos["pnl_percent"]), 2),
            })

        result = {
            "positions":   positions,
            "total_value": round(float(portfolio["total_value"]), 2),
            "cash":        round(float(portfolio["cash"]), 2),
            "total_pnl":   round(float(portfolio["total_pnl"]), 2),
            "count":       len(positions),
        }
        _positions_cache[user_id] = {"data": result, "ts": time.time()}
        return result
    except Exception as e:
        return {"positions": [], "error": str(e)}


_signals_cache: dict = {}
_SIGNALS_TTL = 300  # 5 λεπτά

@router.get("/signals-bulk", dependencies=_AUTH)
async def signals_bulk():
    """Smart Score signals για τα paper positions."""
    try:
        import time as _time
        now = _time.time()
        if _signals_cache.get("ts", 0) + _SIGNALS_TTL > now:
            return _signals_cache["data"]
        from services.smart_score import smart_score_calculator
        symbols = [
            "AAPL","AAVEUSDC","ADAUSDC","ALGOUSDC","AMZN","ASML","ATOMUSDC",
            "AVAXUSDC","AXSUSDC","BAC","BCHUSDC","BNBUSDC","BTCUSDC","CL1!",
            "DAX1!","DOGEUSDC","DOTUSDC","ES1!","ETCUSDC","ETHUSDC","FILUSDC",
            "FTSE1!","GC1!","GOOGL","HG1!","ICPUSDC","JPM","LINKUSDC","LTCUSDC",
            "LVMH","META","MSFT","N2251!","NEARUSDC","NG1!","NQ1!","NVDA",
            "OILUSD","POLUSDC","SANDUSDC","SAP","SHIBUSDC","SI1!","SOLUSDC",
            "THETAUSDC","TRXUSDC","TSLA","UNIUSDC","US100","US30","US500",
            "XAGUSDC","XAUUSDC","XBRUSD","XLMUSDC","XPDUSDC","XPTUSDC","XRPUSDC",
            "YM1!","ZC1!","ZS1!",
        ]
        results = {}
        for sym in symbols:
            try:
                r = smart_score_calculator.calculate_smart_score(sym)
                sigs = r.get("signals", {})
                results[sym] = {
                    "signal":     r.get("recommendation", "HOLD"),
                    "score":      round(r.get("smart_score", 0), 1),
                    "rsi":        round(sigs.get("rsi", {}).get("score", 0), 1),
                    "sentiment":  round(sigs.get("news_sentiment", {}).get("score", 0), 1),
                    "prediction": round(sigs.get("prediction", {}).get("score", 0), 1),
                    "volume":     round(sigs.get("volume", {}).get("score", 0), 1),
                    "fear_greed": round(sigs.get("fear_greed", {}).get("score", 0), 1),
                }
            except Exception:
                results[sym] = {"signal": "N/A", "score": None}
        _signals_cache["data"] = results
        _signals_cache["ts"] = _time.time()
        return results
    except Exception as e:
        return {"error": str(e)}
