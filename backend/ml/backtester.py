"""
Backtesting Engine for AURA
Uses pre-computed training_features (target_direction + target_return) as signals,
falls back to momentum strategy for symbols without training data.
"""

import os
import sys
import logging
import traceback
from datetime import datetime
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

SYMBOL_ALIASES = {
    "BTC-USD":   ["BTCUSDC", "BTCUSDT", "BTC-USD"],
    "ETH-USD":   ["ETHUSDC", "ETHUSDT", "ETH-USD"],
    "BNB-USD":   ["BNBUSDC", "BNBUSDT", "BNB-USD"],
    "XRP-USD":   ["XRPUSDC", "XRPUSDT", "XRP-USD"],
    "SOL-USD":   ["SOLUSDC", "SOLUSDT", "SOL-USD"],
    "ADA-USD":   ["ADAUSDC", "ADAUSDT", "ADA-USD"],
    "AVAX-USD":  ["AVAXUSDC", "AVAXUSDT", "AVAX-USD"],
    "DOT-USD":   ["DOTUSDC", "DOTUSDT", "DOT-USD"],
    "LINK-USD":  ["LINKUSDC", "LINKUSDT", "LINK-USD"],
    "MATIC-USD": ["MATICUSDC", "POLUSDC", "MATIC-USD"],
    "GC=F":      ["GC=F", "GC1!", "XAUUSDC"],
    "SI=F":      ["SI=F", "SI1!", "XAGUSDC"],
    "PL=F":      ["PL=F", "XPTUSDC"],
    "PA=F":      ["PA=F", "XPDUSDC"],
    "CL=F":      ["CL=F", "CL1!"],
    "ES=F":      ["ES=F", "ES1!"],
    "NQ=F":      ["NQ=F", "NQ1!"],
    "^TNX":      ["^TNX", "TNX"],
    "^IRX":      ["^IRX", "IRX"],
    "^TYX":      ["^TYX", "TYX"],
    "^VIX":      ["^VIX", "VIX"],
    "EURUSD=X":  ["EURUSD=X", "EURUSD"],
    "GBPEUR=X":  ["GBPEUR=X", "GBPEUR"],
    "USDJPY=X":  ["USDJPY=X", "USDJPY"],
}

BINANCE_FEE = 0.001
SLIPPAGE = 0.0005
MIN_HOLD_DAYS = 3
RETURN_THRESHOLD = 0.01  # 1% minimum predicted move to trade
RISK_FREE_RATE = 0.04


def _get_aliases(symbol: str) -> List[str]:
    candidates = [symbol]
    for key, aliases in SYMBOL_ALIASES.items():
        if symbol == key or symbol in aliases:
            return list(dict.fromkeys([symbol, key] + aliases))
    return candidates


def _py(val):
    if hasattr(val, 'item'):
        return val.item()
    return val


# ── Strategy 1: Pre-computed signals from training_features ──

def _load_signal_data(db, symbol: str) -> Optional[pd.DataFrame]:
    """Load pre-computed direction + return from training_features + prices."""
    from database.models import TrainingFeature, HistoricalPrice

    for alias in _get_aliases(symbol):
        features = db.query(TrainingFeature).filter(
            TrainingFeature.symbol == alias
        ).order_by(TrainingFeature.date).all()

        if len(features) < 30:
            continue

        # Load matching prices (try same alias first, then original symbol)
        price_map = {}
        for price_alias in _get_aliases(symbol):
            prices = db.query(HistoricalPrice).filter(
                HistoricalPrice.symbol == price_alias
            ).all()
            for p in prices:
                price_map[p.date] = p.close
            if price_map:
                break

        if not price_map:
            continue

        rows = []
        for f in features:
            price = price_map.get(f.date)
            if price and price > 0:
                rows.append({
                    "date": f.date,
                    "price": float(price),
                    "direction": f.target_direction,
                    "target_return": float(f.target_return or 0),
                })

        if len(rows) >= 30:
            print(f"[Backtest] {symbol}: loaded {len(rows)} signal rows via alias '{alias}'")
            return pd.DataFrame(rows).set_index("date").sort_index()

    return None


# ── Strategy 2: Momentum fallback ───────────────────────────

def _load_price_data(db, symbol: str) -> Optional[pd.DataFrame]:
    """Load price data for momentum strategy."""
    from database.models import HistoricalPrice

    for alias in _get_aliases(symbol):
        prices = db.query(HistoricalPrice).filter(
            HistoricalPrice.symbol == alias
        ).order_by(HistoricalPrice.date).all()
        if len(prices) >= 60:
            print(f"[Backtest] {symbol}: loaded {len(prices)} prices via alias '{alias}' (momentum mode)")
            return pd.DataFrame([{
                "date": p.date, "price": float(p.close)
            } for p in prices]).set_index("date").sort_index()

    # yfinance fallback
    try:
        import yfinance as yf
        hist = yf.Ticker(symbol).history(period="3y", interval="1d")
        if len(hist) >= 60:
            print(f"[Backtest] {symbol}: loaded {len(hist)} rows from yfinance (momentum mode)")
            df = pd.DataFrame({"price": hist["Close"].values}, index=hist.index.date)
            df.index.name = "date"
            return df
    except Exception as e:
        print(f"[Backtest] {symbol}: yfinance fallback failed: {e}")

    return None


def _add_momentum_signals(df: pd.DataFrame) -> pd.DataFrame:
    """Add momentum signals: buy if price > 5d MA * 1.005, sell if < MA * 0.995."""
    df = df.copy()
    ma5 = df["price"].rolling(5, min_periods=3).mean()
    df["signal"] = "NEUTRAL"
    df.loc[df["price"] > ma5 * 1.005, "signal"] = "BUY"
    df.loc[df["price"] < ma5 * 0.995, "signal"] = "SELL"
    return df


# ── Core simulation ─────────────────────────────────────────

def _simulate(df: pd.DataFrame, initial_capital: float = 10000.0) -> Dict:
    """
    Simulate trades on a DataFrame with columns: price, signal.
    Returns full metrics dict.
    """
    prices = df["price"].values
    signals = df["signal"].values
    n = len(prices)

    capital = initial_capital
    position = 0.0
    trades = []
    equity = [capital]
    total_fees = 0.0
    days_held = 0

    for i in range(1, n):
        price = prices[i]
        sig = signals[i]
        equity.append(capital + position * price)

        if price <= 0:
            continue

        # Hold period enforcement
        if position > 0:
            days_held += 1
            if days_held < MIN_HOLD_DAYS:
                continue

        if sig == "BUY" and position == 0:
            # Enter long
            fee = capital * (BINANCE_FEE + SLIPPAGE)
            total_fees += fee
            units = (capital - fee) / price
            position = units
            capital = 0
            days_held = 0
            trades.append({"date": str(df.index[i]), "type": "BUY", "price": float(price), "fee": float(fee)})

        elif sig == "SELL" and position > 0:
            # Exit long
            revenue = position * price
            fee = revenue * (BINANCE_FEE + SLIPPAGE)
            total_fees += fee
            capital = revenue - fee
            position = 0
            days_held = 0
            trades.append({"date": str(df.index[i]), "type": "SELL", "price": float(price), "fee": float(fee)})

    # Final liquidation
    if position > 0:
        revenue = position * prices[-1]
        fee = revenue * BINANCE_FEE
        total_fees += fee
        capital = revenue - fee
        position = 0

    return _calculate_metrics(
        np.array(equity), trades, df, capital, total_fees, initial_capital
    )


def _calculate_metrics(equity: np.ndarray, trades: List[Dict], df: pd.DataFrame,
                       final_capital: float, total_fees: float,
                       initial_capital: float) -> Dict:
    n_days = len(equity)
    n_years = max(n_days / 252, 0.01)

    total_return = (final_capital - initial_capital) / initial_capital
    annual_return = (1 + total_return) ** (1 / n_years) - 1

    daily_ret = np.diff(equity) / np.maximum(equity[:-1], 0.01)
    daily_ret = daily_ret[np.isfinite(daily_ret)]

    sharpe = 0.0
    if len(daily_ret) > 1 and np.std(daily_ret) > 0:
        sharpe = float((np.mean(daily_ret) - RISK_FREE_RATE / 252) / np.std(daily_ret) * np.sqrt(252))

    sortino = 0.0
    down = daily_ret[daily_ret < 0]
    if len(down) > 1 and np.std(down) > 0:
        sortino = float((np.mean(daily_ret) - RISK_FREE_RATE / 252) / np.std(down) * np.sqrt(252))

    peak = np.maximum.accumulate(equity)
    dd = (equity - peak) / np.maximum(peak, 0.01)
    max_dd = float(np.min(dd))
    calmar = annual_return / abs(max_dd) if max_dd != 0 else 0.0

    # Trade P/L
    buys = [t for t in trades if t["type"] == "BUY"]
    sells = [t for t in trades if t["type"] == "SELL"]
    trade_returns = []
    for i in range(min(len(buys), len(sells))):
        if buys[i]["price"] > 0:
            trade_returns.append((sells[i]["price"] - buys[i]["price"]) / buys[i]["price"])

    winning = [r for r in trade_returns if r > 0]
    losing = [r for r in trade_returns if r <= 0]
    win_rate = len(winning) / len(trade_returns) * 100 if trade_returns else 0.0
    gross_profit = sum(winning) if winning else 0.0
    gross_loss = abs(sum(losing)) if losing else 0.001

    symbol = df.attrs.get("symbol", "")
    metrics = {
        "symbol": symbol,
        "initial_capital": float(initial_capital),
        "final_capital": round(float(final_capital), 2),
        "total_return_pct": round(float(total_return * 100), 2),
        "annual_return_pct": round(float(annual_return * 100), 2),
        "sharpe_ratio": round(sharpe, 3),
        "sortino_ratio": round(sortino, 3),
        "max_drawdown_pct": round(float(max_dd * 100), 2),
        "win_rate_pct": round(float(win_rate), 1),
        "profit_factor": round(float(gross_profit / gross_loss), 3),
        "total_trades": int(len(trades)),
        "trades_per_year": round(float(len(trades) / max(n_years, 0.01)), 1),
        "avg_trade_return_pct": round(float(np.mean(trade_returns) * 100), 2) if trade_returns else 0.0,
        "best_trade_pct": round(float(max(trade_returns) * 100), 2) if trade_returns else 0.0,
        "worst_trade_pct": round(float(min(trade_returns) * 100), 2) if trade_returns else 0.0,
        "calmar_ratio": round(float(calmar), 3),
        "total_fees_paid": round(float(total_fees), 2),
        "net_return_after_fees": round(float(final_capital - initial_capital - total_fees), 2),
        "start_date": str(df.index[0]) if len(df) > 0 else None,
        "end_date": str(df.index[-1]) if len(df) > 0 else None,
    }
    return {k: _py(v) for k, v in metrics.items()}


# ── Public API ───────────────────────────────────────────────

def backtest_symbol(symbol: str, job_id: str = "manual") -> Optional[Dict]:
    """Run backtest for a single symbol."""
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from database.connection import SessionLocal
    from database.models import BacktestResult

    print(f"\n[Backtest] === {symbol} ===")
    db = SessionLocal()
    if not db:
        return {"symbol": symbol, "error": "Database not available"}

    try:
        # Strategy 1: pre-computed signals from training_features
        signal_df = _load_signal_data(db, symbol)

        if signal_df is not None and len(signal_df) >= 30:
            # Convert target_direction + target_return to trading signals
            signal_df["signal"] = "NEUTRAL"
            signal_df.loc[
                (signal_df["direction"] == "up") & (signal_df["target_return"] > RETURN_THRESHOLD),
                "signal"
            ] = "BUY"
            signal_df.loc[
                (signal_df["direction"] == "down") & (signal_df["target_return"] < -RETURN_THRESHOLD),
                "signal"
            ] = "SELL"

            buy_count = (signal_df["signal"] == "BUY").sum()
            sell_count = (signal_df["signal"] == "SELL").sum()
            print(f"[Backtest] {symbol}: ML signals — {buy_count} BUY, {sell_count} SELL, "
                  f"{len(signal_df) - buy_count - sell_count} NEUTRAL")

            signal_df.attrs["symbol"] = symbol
            metrics = _simulate(signal_df)
            strategy = "ml_signals"

        else:
            # Strategy 2: momentum fallback
            price_df = _load_price_data(db, symbol)
            if price_df is None:
                print(f"[Backtest] {symbol}: no data at all — skipping")
                db.close()
                return {"symbol": symbol, "error": "No price data"}

            signal_df = _add_momentum_signals(price_df)
            buy_count = (signal_df["signal"] == "BUY").sum()
            sell_count = (signal_df["signal"] == "SELL").sum()
            print(f"[Backtest] {symbol}: momentum signals — {buy_count} BUY, {sell_count} SELL")

            signal_df.attrs["symbol"] = symbol
            metrics = _simulate(signal_df)
            strategy = "momentum"

        metrics["symbol"] = symbol
        metrics["strategy"] = strategy

        print(f"[Backtest] {symbol}: return={metrics['total_return_pct']}%, "
              f"sharpe={metrics['sharpe_ratio']}, trades={metrics['total_trades']}")

        # Save to DB
        db.add(BacktestResult(
            symbol=symbol,
            start_date=signal_df.index[0] if len(signal_df) > 0 else None,
            end_date=signal_df.index[-1] if len(signal_df) > 0 else None,
            initial_capital=10000.0,
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
            metrics_json=metrics,
        ))
        db.commit()
        print(f"[Backtest] {symbol}: saved to DB")
        db.close()
        return metrics

    except Exception as e:
        print(f"[Backtest] {symbol} EXCEPTION: {e}")
        traceback.print_exc()
        try:
            db.rollback()
            db.close()
        except Exception:
            pass
        return {"symbol": symbol, "error": str(e)}


def backtest_all(job_id: str = "manual") -> List[Dict]:
    """Run backtest for all symbols."""
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from database.connection import SessionLocal
    from database.models import HistoricalPrice

    print(f"\n[Backtest] ========== STARTING backtest_all ==========")

    db = SessionLocal()
    try:
        symbols = [r[0] for r in db.query(HistoricalPrice.symbol).distinct().all()]
        print(f"[Backtest] Found {len(symbols)} symbols in DB")
        db.close()
    except Exception as e:
        print(f"[Backtest] DB query failed: {e}")
        db.close()
        symbols = ["AAPL", "MSFT", "NVDA", "BTC-USD", "ETH-USD", "GC=F", "^VIX"]

    results = []
    for symbol in symbols:
        result = backtest_symbol(symbol, job_id)
        if result:
            results.append(result)

    ok = len([r for r in results if "total_return_pct" in r])
    fail = len([r for r in results if "error" in r])
    print(f"\n[Backtest] ========== DONE: {ok} ok, {fail} failed ==========")
    return results
