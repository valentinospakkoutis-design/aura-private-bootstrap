"""Backtest dashboard service.

Lightweight yfinance-backed backtest that reuses the feature/signal helpers
from ml.backtester but returns a dashboard-friendly payload (summary metrics
plus an equity curve) and persists runs to backtest_results.
"""

import logging
import time
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

INITIAL_CAPITAL = 10000.0
BINANCE_FEE = 0.001
SLIPPAGE = 0.0005
MIN_HOLD_DAYS = 3
RISK_FREE_RATE = 0.04

_CACHE: Dict[str, Dict[str, Any]] = {}
_CACHE_TTL = 900  # 15 minutes — avoid duplicate DB writes from repeated calls


def _fetch_yf_ohlcv(symbol: str, days: int) -> Optional[pd.DataFrame]:
    try:
        import yfinance as yf
        from market_data.yfinance_client import _normalize_symbol
    except Exception as e:
        logger.debug(f"yfinance import failed: {e}")
        return None

    yf_symbol = _normalize_symbol(symbol)
    period_days = max(int(days) + 90, 120)
    try:
        hist = yf.Ticker(yf_symbol).history(period=f"{period_days}d", interval="1d")
    except Exception as e:
        logger.debug(f"yfinance fetch failed for {symbol}: {e}")
        return None
    if hist is None or hist.empty:
        return None

    volume = (
        hist["Volume"].astype(float).values
        if "Volume" in hist.columns
        else np.zeros(len(hist))
    )
    return pd.DataFrame(
        {
            "open": hist["Open"].astype(float).values,
            "high": hist["High"].astype(float).values,
            "low": hist["Low"].astype(float).values,
            "close": hist["Close"].astype(float).values,
            "volume": volume,
        },
        index=hist.index.date,
    )


def _simulate_with_curve(df: pd.DataFrame) -> Dict[str, Any]:
    """Run the trade simulation; return metrics plus equity/drawdown arrays."""
    prices = df["close"].values
    signals = df["signal"].values
    n = len(prices)

    capital = INITIAL_CAPITAL
    position = 0.0
    trades = []
    equity = [capital]
    total_fees = 0.0
    days_held = 0

    for i in range(1, n):
        sig = signals[i - 1]
        price = float(prices[i])
        equity.append(capital + position * price)
        if price <= 0:
            continue
        if position > 0:
            days_held += 1
            if days_held < MIN_HOLD_DAYS:
                continue
        if sig == "BUY" and position == 0:
            fee = capital * (BINANCE_FEE + SLIPPAGE)
            total_fees += fee
            position = (capital - fee) / price
            capital = 0.0
            days_held = 0
            trades.append({"type": "BUY", "price": price, "fee": float(fee)})
        elif sig == "SELL" and position > 0:
            revenue = position * price
            fee = revenue * (BINANCE_FEE + SLIPPAGE)
            total_fees += fee
            capital = revenue - fee
            position = 0.0
            days_held = 0
            trades.append({"type": "SELL", "price": price, "fee": float(fee)})

    if position > 0:
        revenue = position * float(prices[-1])
        fee = revenue * BINANCE_FEE
        total_fees += fee
        capital = revenue - fee
        equity[-1] = capital

    equity_arr = np.array(equity, dtype=float)
    total_return_pct = (capital - INITIAL_CAPITAL) / INITIAL_CAPITAL * 100.0
    n_years = max(n / 252.0, 0.01)
    annual_return_pct = ((1 + total_return_pct / 100.0) ** (1 / n_years) - 1) * 100.0

    dr = np.diff(equity_arr) / np.maximum(equity_arr[:-1], 0.01)
    dr = dr[np.isfinite(dr)]
    if len(dr) > 1 and np.std(dr) > 0:
        sharpe = float(((np.mean(dr) - RISK_FREE_RATE / 252.0) / np.std(dr)) * np.sqrt(252.0))
    else:
        sharpe = 0.0
    down = dr[dr < 0]
    if len(down) > 1 and np.std(down) > 0:
        sortino = float(((np.mean(dr) - RISK_FREE_RATE / 252.0) / np.std(down)) * np.sqrt(252.0))
    else:
        sortino = 0.0

    peak = np.maximum.accumulate(equity_arr)
    dd_series = (equity_arr - peak) / np.maximum(peak, 0.01)
    max_dd_pct = float(np.min(dd_series) * 100.0) if dd_series.size else 0.0
    calmar = (annual_return_pct / abs(max_dd_pct)) if max_dd_pct != 0 else 0.0

    buys = [t for t in trades if t["type"] == "BUY"]
    sells = [t for t in trades if t["type"] == "SELL"]
    pair_count = min(len(buys), len(sells))
    returns = [
        (sells[i]["price"] - buys[i]["price"]) / buys[i]["price"]
        for i in range(pair_count)
        if buys[i]["price"] > 0
    ]
    winners = [r for r in returns if r > 0]
    losers = [r for r in returns if r <= 0]
    win_rate_pct = (len(winners) / len(returns) * 100.0) if returns else 0.0
    profit_factor = (sum(winners) if winners else 0.0) / (abs(sum(losers)) if losers else 0.001)

    return {
        "equity": [float(x) for x in equity_arr.tolist()],
        "drawdown_pct": [float(x) for x in (dd_series * 100.0).tolist()],
        "initial_capital": INITIAL_CAPITAL,
        "final_capital": round(float(capital), 2),
        "total_return_pct": round(float(total_return_pct), 2),
        "annual_return_pct": round(float(annual_return_pct), 2),
        "sharpe_ratio": round(sharpe, 3),
        "sortino_ratio": round(sortino, 3),
        "max_drawdown_pct": round(float(max_dd_pct), 2),
        "win_rate_pct": round(float(win_rate_pct), 1),
        "profit_factor": round(float(profit_factor), 3),
        "total_trades": int(len(trades)),
        "total_fees_paid": round(float(total_fees), 2),
        "calmar_ratio": round(float(calmar), 3),
        "best_trade_pct": round(float(max(returns) * 100.0), 2) if returns else 0.0,
        "worst_trade_pct": round(float(min(returns) * 100.0), 2) if returns else 0.0,
    }


def _persist_result(symbol: str, feat: pd.DataFrame, metrics: Dict[str, Any], payload: Dict[str, Any]) -> None:
    try:
        from database.connection import SessionLocal
        from database.models import BacktestResult
    except Exception as e:
        logger.debug(f"backtest DB import failed: {e}")
        return

    db = SessionLocal()
    if not db:
        return
    try:
        db.add(BacktestResult(
            symbol=symbol.upper(),
            start_date=feat.index[0] if len(feat) else None,
            end_date=feat.index[-1] if len(feat) else None,
            initial_capital=INITIAL_CAPITAL,
            final_capital=float(metrics["final_capital"]),
            total_return_pct=float(metrics["total_return_pct"]),
            annual_return_pct=float(metrics["annual_return_pct"]),
            sharpe_ratio=float(metrics["sharpe_ratio"]),
            sortino_ratio=float(metrics["sortino_ratio"]),
            max_drawdown_pct=float(metrics["max_drawdown_pct"]),
            win_rate_pct=float(metrics["win_rate_pct"]),
            profit_factor=float(metrics["profit_factor"]),
            total_trades=int(metrics["total_trades"]),
            total_fees_paid=float(metrics["total_fees_paid"]),
            calmar_ratio=float(metrics["calmar_ratio"]),
            metrics_json={k: v for k, v in payload.items() if k != "equity_curve"},
        ))
        db.commit()
    except Exception as e:
        logger.debug(f"backtest DB save failed for {symbol}: {e}")
        try:
            db.rollback()
        except Exception:
            pass
    finally:
        db.close()


def run_backtest_summary(symbol: str, days: int = 365) -> Dict[str, Any]:
    """Backtest a symbol using current ML signals over the last `days` days.

    Returns summary metrics (total_return_pct, max_drawdown_pct, win_rate_pct,
    total_trades, sharpe_ratio, best_trade_pct, worst_trade_pct, ...) plus an
    equity_curve {dates, equity, drawdown} block. Each run is cached for 15
    minutes and persisted to backtest_results.
    """
    sym_u = symbol.upper()
    key = f"{sym_u}:{int(days)}"
    now = time.time()
    cached = _CACHE.get(key)
    if cached and (now - cached["t"]) < _CACHE_TTL:
        return cached["data"]

    raw = _fetch_yf_ohlcv(sym_u, days)
    if raw is None or len(raw) < 30:
        return {"symbol": sym_u, "error": "insufficient price data"}

    try:
        from ml.backtester import (
            _compute_features,
            _generate_ml_signals,
            _momentum_signals,
            _load_model,
        )
    except Exception as e:
        return {"symbol": sym_u, "error": f"signal import failed: {e}"}

    feat = _compute_features(raw)
    if feat.empty:
        return {"symbol": sym_u, "error": "feature engineering empty"}

    feat = feat.tail(max(int(days), 60)).copy()

    model_data = _load_model(sym_u)
    if model_data:
        feat["signal"] = _generate_ml_signals(feat, model_data)
        strategy = "ml_model"
    else:
        feat["signal"] = _momentum_signals(feat)
        strategy = "momentum"

    metrics = _simulate_with_curve(feat)

    equity = metrics.pop("equity")
    drawdown = metrics.pop("drawdown_pct")
    dates = [str(d) for d in feat.index[: len(equity)]]

    summary = {
        "symbol": sym_u,
        "strategy": strategy,
        "days": int(days),
        "start_date": dates[0] if dates else None,
        "end_date": dates[-1] if dates else None,
        "total_return_pct": metrics["total_return_pct"],
        "annual_return_pct": metrics["annual_return_pct"],
        "max_drawdown_pct": metrics["max_drawdown_pct"],
        "win_rate_pct": metrics["win_rate_pct"],
        "total_trades": metrics["total_trades"],
        "sharpe_ratio": metrics["sharpe_ratio"],
        "sortino_ratio": metrics["sortino_ratio"],
        "profit_factor": metrics["profit_factor"],
        "calmar_ratio": metrics["calmar_ratio"],
        "best_trade_pct": metrics["best_trade_pct"],
        "worst_trade_pct": metrics["worst_trade_pct"],
        "initial_capital": metrics["initial_capital"],
        "final_capital": metrics["final_capital"],
        "total_fees_paid": metrics["total_fees_paid"],
        "equity_curve": {
            "dates": dates,
            "equity": equity,
            "drawdown": drawdown,
        },
    }

    _persist_result(sym_u, feat, metrics, summary)
    _CACHE[key] = {"t": now, "data": summary}
    return summary
