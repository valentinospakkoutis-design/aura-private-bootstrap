"""Market regime detection via ADX, Bollinger Band width, and SMA50/SMA200 cross.

Classifies a symbol into TRENDING_UP / TRENDING_DOWN / RANGING / VOLATILE /
NEUTRAL and maps to a recommended strategy. Pure-pandas implementation so it
runs without TA-Lib.
"""

import logging
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def _wilder_smooth(series: pd.Series, period: int) -> pd.Series:
    """Wilder's smoothing: EMA with alpha = 1/period."""
    return series.ewm(alpha=1.0 / period, adjust=False).mean()


def _compute_adx(df: pd.DataFrame, period: int = 14) -> float:
    """14-period ADX. Returns the most recent value, or NaN on failure."""
    high = df["High"].astype(float)
    low = df["Low"].astype(float)
    close = df["Close"].astype(float)

    prev_close = close.shift(1)
    tr = pd.concat(
        [high - low, (high - prev_close).abs(), (low - prev_close).abs()],
        axis=1,
    ).max(axis=1)

    up_move = high.diff()
    down_move = -low.diff()
    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)
    plus_dm = pd.Series(plus_dm, index=df.index)
    minus_dm = pd.Series(minus_dm, index=df.index)

    atr = _wilder_smooth(tr, period)
    plus_di = 100.0 * _wilder_smooth(plus_dm, period) / atr.replace(0, np.nan)
    minus_di = 100.0 * _wilder_smooth(minus_dm, period) / atr.replace(0, np.nan)
    dx = 100.0 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    adx = _wilder_smooth(dx, period)
    last = adx.iloc[-1]
    return float(last) if pd.notna(last) else float("nan")


def _compute_bb_width(close: pd.Series, period: int = 20, num_std: float = 2.0) -> pd.Series:
    """Bollinger Band width as percent of middle band."""
    middle = close.rolling(period).mean()
    std = close.rolling(period).std()
    upper = middle + num_std * std
    lower = middle - num_std * std
    width_pct = (upper - lower) / middle.replace(0, np.nan) * 100.0
    return width_pct


def _fetch_daily_ohlcv(symbol: str, days: int = 220) -> Optional[pd.DataFrame]:
    """Fetch enough daily data to compute SMA200 (needs ~220d) via yfinance."""
    try:
        import yfinance as yf
        from market_data.yfinance_client import _normalize_symbol
    except Exception as e:
        logger.debug(f"market_regime yfinance import failed: {e}")
        return None

    yf_symbol = _normalize_symbol(symbol)
    try:
        hist = yf.Ticker(yf_symbol).history(period=f"{days}d", interval="1d")
    except Exception as e:
        logger.debug(f"market_regime fetch failed for {symbol}: {e}")
        return None
    if hist is None or hist.empty:
        return None
    return hist


def _default_result(symbol: str, reason: str = "insufficient data") -> Dict[str, Any]:
    return {
        "symbol": symbol,
        "regime": "NEUTRAL",
        "adx": None,
        "bb_width": None,
        "bb_width_avg": None,
        "trend_direction": "neutral",
        "recommended_strategy": "wait",
        "reason": reason,
    }


def detect_market_regime(symbol: str) -> Dict[str, Any]:
    """Classify the market regime for a symbol.

    - TRENDING_UP: ADX > 25 AND price > SMA50 > SMA200
    - TRENDING_DOWN: ADX > 25 AND price < SMA50 < SMA200
    - RANGING: ADX < 20 AND Bollinger Band width below its 90d average
    - VOLATILE: current BB width > 2x its 90d average AND high recent volatility
    - NEUTRAL: anything else
    """
    sym_u = symbol.upper()
    hist = _fetch_daily_ohlcv(sym_u, days=260)
    if hist is None or len(hist) < 60 or "Close" not in hist.columns:
        return _default_result(sym_u)

    close = hist["Close"].astype(float)

    # Compute indicators; degrade gracefully when history is short.
    try:
        adx = _compute_adx(hist.tail(90), period=14)
    except Exception as e:
        logger.debug(f"market_regime ADX failed for {sym_u}: {e}")
        adx = float("nan")

    bb_series = _compute_bb_width(close, period=20, num_std=2.0)
    bb_recent = bb_series.tail(90)
    bb_width = float(bb_recent.iloc[-1]) if not bb_recent.empty and pd.notna(bb_recent.iloc[-1]) else float("nan")
    bb_avg = float(bb_recent.mean()) if not bb_recent.empty else float("nan")

    sma50 = close.rolling(50).mean()
    sma200 = close.rolling(200).mean() if len(close) >= 200 else pd.Series([np.nan] * len(close), index=close.index)

    last_price = float(close.iloc[-1])
    last_sma50 = float(sma50.iloc[-1]) if pd.notna(sma50.iloc[-1]) else float("nan")
    last_sma200 = float(sma200.iloc[-1]) if pd.notna(sma200.iloc[-1]) else float("nan")

    # 20-day realized volatility of daily returns (as %)
    returns = close.pct_change().dropna()
    recent_vol_pct = float(returns.tail(20).std() * 100.0) if len(returns) >= 5 else float("nan")
    longterm_vol_pct = float(returns.tail(90).std() * 100.0) if len(returns) >= 30 else float("nan")

    # Trend direction from SMA50 vs SMA200 (fallback to SMA50 vs price if SMA200 unavailable)
    if pd.notna(last_sma50) and pd.notna(last_sma200):
        if last_price > last_sma50 > last_sma200:
            trend_direction = "up"
        elif last_price < last_sma50 < last_sma200:
            trend_direction = "down"
        else:
            trend_direction = "neutral"
    elif pd.notna(last_sma50):
        trend_direction = "up" if last_price > last_sma50 else "down"
    else:
        trend_direction = "neutral"

    # Classification
    regime = "NEUTRAL"
    if (
        pd.notna(bb_width)
        and pd.notna(bb_avg)
        and bb_avg > 0
        and bb_width > 2.0 * bb_avg
        and pd.notna(recent_vol_pct)
        and pd.notna(longterm_vol_pct)
        and recent_vol_pct > max(longterm_vol_pct * 1.5, 3.0)
    ):
        regime = "VOLATILE"
    elif pd.notna(adx) and adx > 25 and trend_direction == "up":
        regime = "TRENDING_UP"
    elif pd.notna(adx) and adx > 25 and trend_direction == "down":
        regime = "TRENDING_DOWN"
    elif (
        pd.notna(adx)
        and adx < 20
        and pd.notna(bb_width)
        and pd.notna(bb_avg)
        and bb_width < bb_avg
    ):
        regime = "RANGING"

    strategy_map = {
        "TRENDING_UP": "momentum",
        "TRENDING_DOWN": "momentum",
        "RANGING": "mean_reversion",
        "VOLATILE": "wait",
        "NEUTRAL": "wait",
    }

    return {
        "symbol": sym_u,
        "regime": regime,
        "adx": round(float(adx), 2) if pd.notna(adx) else None,
        "bb_width": round(float(bb_width), 3) if pd.notna(bb_width) else None,
        "bb_width_avg": round(float(bb_avg), 3) if pd.notna(bb_avg) else None,
        "trend_direction": trend_direction,
        "recent_vol_pct": round(recent_vol_pct, 3) if pd.notna(recent_vol_pct) else None,
        "sma50": round(last_sma50, 4) if pd.notna(last_sma50) else None,
        "sma200": round(last_sma200, 4) if pd.notna(last_sma200) else None,
        "price": round(last_price, 4),
        "recommended_strategy": strategy_map[regime],
    }
