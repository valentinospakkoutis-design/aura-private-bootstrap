"""
Backtesting Engine for AURA
No lookahead bias: uses only past data to generate signals, executes at next day's price.
Two modes: ML model predictions (if model available) or momentum fallback.
"""

import os
import sys
import logging
import pickle
import traceback
from datetime import datetime
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

MODELS_DIR = os.path.join(os.path.dirname(__file__), "..", "models")
BINANCE_FEE = 0.001
SLIPPAGE = 0.0005
MIN_HOLD_DAYS = 3
RISK_FREE_RATE = 0.04

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
    "GC=F": ["GC=F", "GC1!", "XAUUSDC"],
    "SI=F": ["SI=F", "SI1!", "XAGUSDC"],
    "PL=F": ["PL=F", "XPTUSDC"], "PA=F": ["PA=F", "XPDUSDC"],
    "CL=F": ["CL=F", "CL1!"], "ES=F": ["ES=F", "ES1!"], "NQ=F": ["NQ=F", "NQ1!"],
    "^TNX": ["^TNX", "TNX"], "^IRX": ["^IRX", "IRX"], "^TYX": ["^TYX", "TYX"],
    "^VIX": ["^VIX", "VIX"],
    "EURUSD=X": ["EURUSD=X", "EURUSD"], "GBPEUR=X": ["GBPEUR=X", "GBPEUR"],
    "USDJPY=X": ["USDJPY=X", "USDJPY"],
}


def _aliases(symbol: str) -> List[str]:
    for key, als in SYMBOL_ALIASES.items():
        if symbol == key or symbol in als:
            return list(dict.fromkeys([symbol, key] + als))
    return [symbol]


def _py(v):
    return v.item() if hasattr(v, 'item') else v


def _compute_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0).rolling(period).mean()
    loss = (-delta.where(delta < 0, 0.0)).rolling(period).mean()
    rs = gain / loss.replace(0, np.inf)
    return 100 - (100 / (1 + rs))


# ── Feature computation (NO future data) ────────────────────

def _compute_features(df: pd.DataFrame) -> pd.DataFrame:
    """Compute technical features using ONLY past data. No lookahead."""
    out = df.copy()
    c = out["close"]
    out["return_1d"] = c.pct_change()
    out["return_5d"] = c.pct_change(5)
    out["return_20d"] = c.pct_change(20)
    out["ma5"] = c.rolling(5).mean()
    out["ma20"] = c.rolling(20).mean()
    out["ma_ratio"] = out["ma5"] / out["ma20"]
    out["vol_20"] = out["return_1d"].rolling(20).std()
    out["rsi"] = _compute_rsi(c, 14)

    if "volume" in out.columns:
        vol_ma = out["volume"].rolling(20).mean()
        out["volume_ratio"] = out["volume"] / vol_ma.replace(0, 1)
    else:
        out["volume_ratio"] = 1.0

    out["hl_range"] = (out["high"] - out["low"]) / c if "high" in out.columns and "low" in out.columns else 0

    return out.dropna()


FEATURE_COLS = ["return_1d", "return_5d", "return_20d", "ma_ratio", "vol_20", "rsi", "volume_ratio", "hl_range"]


# ── Model-based signal generation ────────────────────────────

def _load_model(symbol: str) -> Optional[dict]:
    for sym in _aliases(symbol):
        for suffix in ["_ensemble_latest.pkl", "_xgboost_latest.pkl"]:
            path = os.path.join(MODELS_DIR, f"{sym}{suffix}")
            if os.path.exists(path):
                try:
                    with open(path, "rb") as f:
                        return pickle.load(f)
                except Exception:
                    pass
    return None


def _generate_ml_signals(df: pd.DataFrame, model_data: dict) -> pd.Series:
    """Generate signals from ML model using only current features (no future data)."""
    available = [c for c in FEATURE_COLS if c in df.columns]
    X = df[available].fillna(0).values

    # Pad or trim to model's expected feature count
    model = model_data.get("xgb_model") or model_data.get("model")
    if model is None:
        return pd.Series("NEUTRAL", index=df.index)

    expected = getattr(model, "n_features_in_", X.shape[1])
    if X.shape[1] < expected:
        X = np.pad(X, ((0, 0), (0, expected - X.shape[1])))
    elif X.shape[1] > expected:
        X = X[:, :expected]

    # Scale if scaler available
    scaler = model_data.get("scaler")
    if scaler:
        try:
            X = scaler.transform(X)
        except Exception:
            pass

    # Get predictions
    try:
        if hasattr(model, "predict_proba"):
            proba = model.predict_proba(X)
            if proba.shape[1] >= 2:
                buy_prob = proba[:, 1]  # probability of "up"
                signals = pd.Series("NEUTRAL", index=df.index)
                signals[buy_prob > 0.55] = "BUY"
                signals[buy_prob < 0.45] = "SELL"
                print(f"  ML predict_proba: BUY={int((signals=='BUY').sum())}, "
                      f"SELL={int((signals=='SELL').sum())}, NEUTRAL={int((signals=='NEUTRAL').sum())}")
                return signals
        # Fallback: raw predict (regression)
        preds = model.predict(X)
        signals = pd.Series("NEUTRAL", index=df.index)
        signals[preds > 0.01] = "BUY"    # predict > 1% up
        signals[preds < -0.01] = "SELL"   # predict > 1% down
        return signals
    except Exception as e:
        print(f"  ML prediction failed: {e}")
        return pd.Series("NEUTRAL", index=df.index)


def _momentum_signals(df: pd.DataFrame) -> pd.Series:
    """Momentum strategy: buy if 5-day return > +2%, sell if < -2%."""
    signals = pd.Series("NEUTRAL", index=df.index)
    if "return_5d" in df.columns:
        signals[df["return_5d"] > 0.02] = "BUY"
        signals[df["return_5d"] < -0.02] = "SELL"
    return signals


# ── Trade simulation (executes at NEXT day's price) ─────────

def _simulate(df: pd.DataFrame, initial_capital: float = 10000.0) -> Dict:
    """Simulate trades. Signal on day i → execute at day i+1 open/close."""
    prices = df["close"].values
    signals = df["signal"].values
    n = len(prices)

    capital = initial_capital
    position = 0.0
    trades = []
    equity = [capital]
    total_fees = 0.0
    days_held = 0

    for i in range(1, n):
        # Signal from YESTERDAY, execute at TODAY's price
        sig = signals[i - 1]  # ← key: use previous day's signal
        price = prices[i]

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
            capital = 0
            days_held = 0
            trades.append({"type": "BUY", "price": float(price), "fee": float(fee)})

        elif sig == "SELL" and position > 0:
            revenue = position * price
            fee = revenue * (BINANCE_FEE + SLIPPAGE)
            total_fees += fee
            capital = revenue - fee
            position = 0
            days_held = 0
            trades.append({"type": "SELL", "price": float(price), "fee": float(fee)})

    # Final liquidation
    if position > 0:
        revenue = position * prices[-1]
        fee = revenue * BINANCE_FEE
        total_fees += fee
        capital = revenue - fee

    return _calc_metrics(np.array(equity), trades, df, capital, total_fees, initial_capital)


def _calc_metrics(equity, trades, df, final_capital, total_fees, initial_capital):
    n_days = len(equity)
    n_years = max(n_days / 252, 0.01)
    total_ret = (final_capital - initial_capital) / initial_capital
    annual_ret = (1 + total_ret) ** (1 / n_years) - 1

    dr = np.diff(equity) / np.maximum(equity[:-1], 0.01)
    dr = dr[np.isfinite(dr)]

    sharpe = float((np.mean(dr) - RISK_FREE_RATE/252) / np.std(dr) * np.sqrt(252)) if len(dr) > 1 and np.std(dr) > 0 else 0.0
    down = dr[dr < 0]
    sortino = float((np.mean(dr) - RISK_FREE_RATE/252) / np.std(down) * np.sqrt(252)) if len(down) > 1 and np.std(down) > 0 else 0.0

    peak = np.maximum.accumulate(equity)
    dd = (equity - peak) / np.maximum(peak, 0.01)
    max_dd = float(np.min(dd))
    calmar = annual_ret / abs(max_dd) if max_dd != 0 else 0.0

    buys = [t for t in trades if t["type"] == "BUY"]
    sells = [t for t in trades if t["type"] == "SELL"]
    tr = [(sells[i]["price"] - buys[i]["price"]) / buys[i]["price"] for i in range(min(len(buys), len(sells))) if buys[i]["price"] > 0]
    w = [r for r in tr if r > 0]
    l = [r for r in tr if r <= 0]

    return {k: _py(v) for k, v in {
        "symbol": df.attrs.get("symbol", ""),
        "initial_capital": float(initial_capital),
        "final_capital": round(float(final_capital), 2),
        "total_return_pct": round(float(total_ret * 100), 2),
        "annual_return_pct": round(float(annual_ret * 100), 2),
        "sharpe_ratio": round(sharpe, 3),
        "sortino_ratio": round(sortino, 3),
        "max_drawdown_pct": round(float(max_dd * 100), 2),
        "win_rate_pct": round(len(w) / len(tr) * 100, 1) if tr else 0.0,
        "profit_factor": round((sum(w) if w else 0) / (abs(sum(l)) if l else 0.001), 3),
        "total_trades": int(len(trades)),
        "trades_per_year": round(len(trades) / max(n_years, 0.01), 1),
        "avg_trade_return_pct": round(float(np.mean(tr) * 100), 2) if tr else 0.0,
        "best_trade_pct": round(float(max(tr) * 100), 2) if tr else 0.0,
        "worst_trade_pct": round(float(min(tr) * 100), 2) if tr else 0.0,
        "calmar_ratio": round(float(calmar), 3),
        "total_fees_paid": round(float(total_fees), 2),
        "net_return_after_fees": round(float(final_capital - initial_capital - total_fees), 2),
        "start_date": str(df.index[0]) if len(df) > 0 else None,
        "end_date": str(df.index[-1]) if len(df) > 0 else None,
    }.items()}


# ── Price loading ────────────────────────────────────────────

def _load_prices(db, symbol: str) -> Optional[pd.DataFrame]:
    from database.models import HistoricalPrice
    for alias in _aliases(symbol):
        rows = db.query(HistoricalPrice).filter(HistoricalPrice.symbol == alias).order_by(HistoricalPrice.date).all()
        if len(rows) >= 60:
            print(f"[Backtest] {symbol}: {len(rows)} price rows via '{alias}'")
            return pd.DataFrame([{
                "date": r.date, "open": r.open, "high": r.high,
                "low": r.low, "close": r.close, "volume": r.volume or 0
            } for r in rows]).set_index("date").sort_index()

    # yfinance fallback
    try:
        import yfinance as yf
        hist = yf.Ticker(symbol).history(period="3y", interval="1d")
        if len(hist) >= 60:
            print(f"[Backtest] {symbol}: {len(hist)} rows from yfinance")
            return pd.DataFrame({
                "open": hist["Open"].values, "high": hist["High"].values,
                "low": hist["Low"].values, "close": hist["Close"].values,
                "volume": hist["Volume"].values,
            }, index=hist.index.date)
    except Exception as e:
        print(f"[Backtest] {symbol}: yfinance failed: {e}")
    return None


# ── Public API ───────────────────────────────────────────────

def backtest_symbol(symbol: str, job_id: str = "manual") -> Optional[Dict]:
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from database.connection import SessionLocal
    from database.models import BacktestResult

    print(f"\n[Backtest] === {symbol} ===")
    db = SessionLocal()
    if not db:
        return {"symbol": symbol, "error": "No database"}

    try:
        raw = _load_prices(db, symbol)
        if raw is None:
            db.close()
            return {"symbol": symbol, "error": "No price data"}

        # Compute features from past data only
        df = _compute_features(raw)
        print(f"[Backtest] {symbol}: {len(df)} rows after feature computation")

        # Try ML model first
        model_data = _load_model(symbol)
        if model_data:
            print(f"[Backtest] {symbol}: ML model loaded")
            df["signal"] = _generate_ml_signals(df, model_data)
            strategy = "ml_model"
        else:
            print(f"[Backtest] {symbol}: no model, using momentum")
            df["signal"] = _momentum_signals(df)
            strategy = "momentum"

        buy_n = int((df["signal"] == "BUY").sum())
        sell_n = int((df["signal"] == "SELL").sum())
        print(f"[Backtest] {symbol}: {buy_n} BUY, {sell_n} SELL signals")

        df.attrs["symbol"] = symbol
        metrics = _simulate(df)
        metrics["symbol"] = symbol
        metrics["strategy"] = strategy

        print(f"[Backtest] {symbol}: return={metrics['total_return_pct']}%, "
              f"sharpe={metrics['sharpe_ratio']}, trades={metrics['total_trades']}")

        db.add(BacktestResult(
            symbol=symbol,
            start_date=df.index[0] if len(df) > 0 else None,
            end_date=df.index[-1] if len(df) > 0 else None,
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
        print(f"[Backtest] {symbol}: saved")
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
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from database.connection import SessionLocal
    from database.models import HistoricalPrice

    print(f"\n[Backtest] ========== START ==========")
    db = SessionLocal()
    try:
        symbols = [r[0] for r in db.query(HistoricalPrice.symbol).distinct().all()]
        print(f"[Backtest] {len(symbols)} symbols in DB")
        db.close()
    except Exception:
        db.close()
        symbols = ["AAPL", "MSFT", "NVDA", "BTC-USD", "ETH-USD", "GC=F", "^VIX"]

    results = []
    for s in symbols:
        r = backtest_symbol(s, job_id)
        if r:
            results.append(r)

    ok = len([r for r in results if "total_return_pct" in r])
    print(f"\n[Backtest] ========== DONE: {ok}/{len(symbols)} ==========")
    return results
