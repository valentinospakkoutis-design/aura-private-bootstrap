"""
api/xag.py — XAGUSD-STD snapshot + OHLC endpoints
Data source: yfinance (SI=F = Silver futures, proxy for XAGUSD-STD)
Phase 7: all routes require JWT auth except /healthz (handled separately).
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from datetime import datetime, timezone
import time

from api.xag_auth import xag_require_auth

_AUTH = [Depends(xag_require_auth)]

router = APIRouter(prefix="/api/xag", tags=["xag"])

# ── Cache ────────────────────────────────────────────────────────────────────
_snapshot_cache: dict = {}
_SNAPSHOT_TTL = 10  # seconds

_ohlc_cache: dict = {}
_OHLC_TTL = 60  # seconds (closed bars don't change)

_positions_cache: dict = {}
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
async def _warmup_positions_cache():
    """Background warmup — runs once at startup to pre-fill positions cache."""
    import asyncio
    await asyncio.sleep(90)  # wait for uvicorn + DB to settle
    try:
        import yfinance as yf
        from services.paper_trading import PaperTradingService
        svc = PaperTradingService()
        raw = svc.get_portfolio(user_id=1)
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
        portfolio = svc.get_portfolio(user_id=1, current_prices=current_prices)
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
        _positions_cache["data"] = result
        _positions_cache["ts"]   = time.time()
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

@router.get("/paper-positions", dependencies=_AUTH)
async def xag_paper_positions():
    """Paper trading positions για dashboard (no auth)."""
    try:
        import yfinance as yf
        from services.paper_trading import PaperTradingService

        # Return cached if fresh
        now = time.time()
        if _positions_cache.get("ts", 0) + _POSITIONS_TTL > now:
            return _positions_cache["data"]

        svc = PaperTradingService()
        # First pass: get positions to know which symbols we need
        raw = svc.get_portfolio(user_id=1)
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
        portfolio = svc.get_portfolio(user_id=1, current_prices=current_prices)

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
        _positions_cache["data"] = result
        _positions_cache["ts"]   = time.time()
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
