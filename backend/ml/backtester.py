"""
Backtesting Engine for AURA
Walk-forward validation with realistic fees, slippage, and smart trade filters.
"""

import os
import sys
import logging
import pickle
import traceback
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

MODELS_DIR = os.path.join(os.path.dirname(__file__), "..", "models")

# Symbol bridge: yfinance historical_prices → model files / training_features
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
    "MATIC-USD": ["MATICUSDC", "MATICUSDT", "POLUSDC", "MATIC-USD"],
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


def _get_all_aliases(symbol: str) -> List[str]:
    """Get all alias names for a symbol, including itself."""
    candidates = [symbol]
    for key, aliases in SYMBOL_ALIASES.items():
        if symbol == key or symbol in aliases:
            candidates = list(dict.fromkeys([symbol, key] + aliases))
            break
    return candidates


def _py(val):
    """Convert numpy types to native Python for PostgreSQL."""
    if hasattr(val, 'item'):
        return val.item()
    return val


class Backtester:
    """Core backtesting engine with smart trade filters."""

    MIN_HOLD_DAYS = 3
    MIN_CONVICTION_GAP = 0.05
    VOL_MIN = 0.05
    VOL_MAX = 0.80

    def __init__(self, symbol: str, initial_capital: float = 10000.0):
        self.symbol = symbol
        self.initial_capital = initial_capital
        self.binance_fee = 0.001
        self.slippage = 0.0005
        self.risk_free_rate = 0.04

    def _load_model(self) -> Optional[dict]:
        """Load model, trying all symbol aliases."""
        for sym in _get_all_aliases(self.symbol):
            for suffix in ["_ensemble_latest.pkl", "_xgboost_latest.pkl"]:
                path = os.path.join(MODELS_DIR, f"{sym}{suffix}")
                if os.path.exists(path):
                    with open(path, "rb") as f:
                        return pickle.load(f)
        return None

    def _generate_signals(self, features_df: pd.DataFrame, model_data: dict) -> pd.DataFrame:
        """Generate buy_prob, sell_prob per row from model."""
        feature_cols = model_data.get("feature_cols", [])
        n = len(features_df)
        default = pd.DataFrame({"buy_prob": [0.5]*n, "sell_prob": [0.5]*n}, index=features_df.index)
        if not feature_cols:
            return default

        # Build X with all expected columns, pad missing with 0
        X = np.zeros((n, len(feature_cols)))
        for i, col in enumerate(feature_cols):
            if col in features_df.columns:
                X[:, i] = features_df[col].fillna(0).values

        scaler = model_data.get("scaler")
        if scaler:
            try:
                X = scaler.transform(X)
            except Exception:
                pass

        def _extract_proba(proba):
            """Safely extract buy/sell probabilities from predict_proba output."""
            if proba.shape[1] == 2:
                return proba[:, 1], proba[:, 0]  # [down, up] → buy=up, sell=down
            elif proba.shape[1] >= 3:
                return proba[:, 2], proba[:, 0]  # [down, neutral, up]
            return np.full(len(proba), 0.5), np.full(len(proba), 0.5)

        # Get probabilities
        if "xgb_model" in model_data and "rf_model" in model_data:
            try:
                xgb_p = model_data["xgb_model"].predict_proba(X)
                rf_p = model_data["rf_model"].predict_proba(X)
                xgb_buy, xgb_sell = _extract_proba(xgb_p)
                rf_buy, rf_sell = _extract_proba(rf_p)
                buy_prob = 0.6 * xgb_buy + 0.4 * rf_buy
                sell_prob = 0.6 * xgb_sell + 0.4 * rf_sell
            except Exception as e:
                print(f"[Backtest] predict_proba failed: {e}")
                return default
        elif "model" in model_data:
            try:
                model = model_data["model"]
                if hasattr(model, "predict_proba"):
                    proba = model.predict_proba(X)
                    buy_prob, sell_prob = _extract_proba(proba)
                else:
                    preds = model.predict(X)
                    buy_prob = 1 / (1 + np.exp(-preds * 10))
                    sell_prob = 1 - buy_prob
            except Exception:
                return default
        else:
            return default

        return pd.DataFrame({"buy_prob": buy_prob, "sell_prob": sell_prob}, index=features_df.index)

    def _position_size(self, conviction_gap: float) -> float:
        """Tiered position sizing based on conviction gap."""
        if conviction_gap < 0.05:
            return 0.0
        elif conviction_gap < 0.15:
            return 0.25
        elif conviction_gap < 0.30:
            return 0.50
        else:
            return 1.0

    def run(self, prices_df: pd.DataFrame, features_df: Optional[pd.DataFrame] = None) -> Dict:
        """Run backtest with filters: conviction gap, volatility regime, hold period."""
        model_data = self._load_model()

        prices = prices_df["close"].values
        dates = prices_df.index
        n = len(prices)

        # Pre-compute volatility filter
        close_series = pd.Series(prices, index=dates)
        returns = close_series.pct_change().fillna(0)
        rolling_vol = returns.rolling(20, min_periods=5).std() * np.sqrt(252)

        # Get model signals
        if features_df is not None and model_data is not None and len(features_df) > 0:
            signals_df = self._generate_signals(features_df, model_data)
            signals_df = signals_df.reindex(dates).fillna(0.5)
        else:
            signals_df = pd.DataFrame({"buy_prob": [0.5]*n, "sell_prob": [0.5]*n}, index=dates)

        buy_probs = signals_df["buy_prob"].values
        sell_probs = signals_df["sell_prob"].values

        # ── Debug: count how many signals pass each filter ────
        conv_pass = 0
        vol_pass = 0
        hold_block = 0

        # ── Simulation loop ──────────────────────────────────
        capital = self.initial_capital
        position = 0.0
        trades = []
        equity_curve = [capital]
        total_fees = 0.0
        days_in_position = 0

        for i in range(1, n):
            price = prices[i]
            equity_curve.append(capital + position * price)

            if price <= 0:
                continue

            buy_p = float(buy_probs[i]) if i < len(buy_probs) else 0.5
            sell_p = float(sell_probs[i]) if i < len(sell_probs) else 0.5
            conviction = abs(buy_p - sell_p)
            vol = float(rolling_vol.iloc[i]) if i < len(rolling_vol) and not np.isnan(rolling_vol.iloc[i]) else 0.20

            # ── Filter A: Conviction gap ─────────────────────
            if conviction < self.MIN_CONVICTION_GAP:
                if position > 0:
                    days_in_position += 1
                continue
            conv_pass += 1

            # ── Filter B: Volatility regime ──────────────────
            if vol < self.VOL_MIN or vol > self.VOL_MAX:
                if position > 0:
                    days_in_position += 1
                continue
            vol_pass += 1

            # ── Filter C: Minimum hold period ────────────────
            if position > 0:
                days_in_position += 1
                if days_in_position < self.MIN_HOLD_DAYS:
                    hold_block += 1
                    continue

            is_buy_signal = buy_p > sell_p

            # ── Execute trade ────────────────────────────────
            target_alloc = self._position_size(conviction) if is_buy_signal else 0.0
            total_value = capital + position * price
            target_value = total_value * target_alloc
            target_units = target_value / price
            delta = target_units - position

            if abs(delta * price) < 1.0:
                continue

            trade_value = abs(delta * price)
            fee = trade_value * (self.binance_fee + self.slippage)
            total_fees += fee

            if delta > 0 and capital >= delta * price + fee:
                capital -= delta * price + fee
                position += delta
                days_in_position = 0
                trades.append({"date": str(dates[i]), "type": "BUY", "price": float(price), "value": float(trade_value), "fee": float(fee)})
            elif delta < 0 and position > 0:
                sell_units = min(abs(delta), position)
                capital += sell_units * price - fee
                position -= sell_units
                days_in_position = 0
                trades.append({"date": str(dates[i]), "type": "SELL", "price": float(price), "value": float(trade_value), "fee": float(fee)})

        # Debug filter stats
        buys = len([t for t in trades if t["type"] == "BUY"])
        sells = len([t for t in trades if t["type"] == "SELL"])
        print(f"[Backtest] {self.symbol} filters: rows={n}, conviction_pass={conv_pass}, "
              f"vol_pass={vol_pass}, hold_blocked={hold_block}, trades={buys}B/{sells}S")

        # Final liquidation
        if position > 0:
            fee = position * prices[-1] * self.binance_fee
            total_fees += fee
            capital += position * prices[-1] - fee
            position = 0

        equity = np.array(equity_curve)
        return self._calculate_metrics(equity, trades, prices_df, capital, total_fees)

    def _calculate_metrics(self, equity: np.ndarray, trades: List[Dict],
                           prices_df: pd.DataFrame, final_capital: float,
                           total_fees: float) -> Dict:
        """Calculate all performance metrics with native Python types."""
        n_days = len(equity)
        n_years = max(n_days / 252, 0.01)

        total_return = (final_capital - self.initial_capital) / self.initial_capital
        annual_return = (1 + total_return) ** (1 / n_years) - 1

        daily_returns = np.diff(equity) / np.maximum(equity[:-1], 0.01)
        daily_returns = daily_returns[np.isfinite(daily_returns)]

        # Sharpe
        if len(daily_returns) > 1 and np.std(daily_returns) > 0:
            sharpe = float((np.mean(daily_returns) - self.risk_free_rate / 252) / np.std(daily_returns) * np.sqrt(252))
        else:
            sharpe = 0.0

        # Sortino
        downside = daily_returns[daily_returns < 0]
        if len(downside) > 1 and np.std(downside) > 0:
            sortino = float((np.mean(daily_returns) - self.risk_free_rate / 252) / np.std(downside) * np.sqrt(252))
        else:
            sortino = 0.0

        # Max drawdown
        peak = np.maximum.accumulate(equity)
        drawdown = (equity - peak) / np.maximum(peak, 0.01)
        max_dd = float(np.min(drawdown))

        # Drawdown duration
        dd_dur = 0
        max_dd_dur = 0
        for d in drawdown:
            if d < 0:
                dd_dur += 1
                max_dd_dur = max(max_dd_dur, dd_dur)
            else:
                dd_dur = 0

        # Trade analysis
        trade_returns = []
        buys = [t for t in trades if t["type"] == "BUY"]
        sells = [t for t in trades if t["type"] == "SELL"]
        for i in range(min(len(buys), len(sells))):
            if buys[i]["price"] > 0:
                trade_returns.append((sells[i]["price"] - buys[i]["price"]) / buys[i]["price"])

        winning = [r for r in trade_returns if r > 0]
        losing = [r for r in trade_returns if r <= 0]
        win_rate = len(winning) / len(trade_returns) * 100 if trade_returns else 0.0
        gross_profit = sum(winning) if winning else 0.0
        gross_loss = abs(sum(losing)) if losing else 0.001
        calmar = annual_return / abs(max_dd) if max_dd != 0 else 0.0
        trades_per_year = len(trades) / max(n_years, 0.01)

        metrics = {
            "symbol": self.symbol,
            "initial_capital": float(self.initial_capital),
            "final_capital": round(float(final_capital), 2),
            "total_return_pct": round(float(total_return * 100), 2),
            "annual_return_pct": round(float(annual_return * 100), 2),
            "sharpe_ratio": round(sharpe, 3),
            "sortino_ratio": round(sortino, 3),
            "max_drawdown_pct": round(float(max_dd * 100), 2),
            "max_drawdown_duration_days": int(max_dd_dur),
            "win_rate_pct": round(float(win_rate), 1),
            "profit_factor": round(float(gross_profit / gross_loss), 3),
            "total_trades": int(len(trades)),
            "trades_per_year": round(float(trades_per_year), 1),
            "avg_trade_return_pct": round(float(np.mean(trade_returns) * 100), 2) if trade_returns else 0.0,
            "avg_winning_trade_pct": round(float(np.mean(winning) * 100), 2) if winning else 0.0,
            "avg_losing_trade_pct": round(float(np.mean(losing) * 100), 2) if losing else 0.0,
            "best_trade_pct": round(float(max(trade_returns) * 100), 2) if trade_returns else 0.0,
            "worst_trade_pct": round(float(min(trade_returns) * 100), 2) if trade_returns else 0.0,
            "calmar_ratio": round(float(calmar), 3),
            "total_fees_paid": round(float(total_fees), 2),
            "net_return_after_fees": round(float(final_capital - self.initial_capital - total_fees), 2),
            "start_date": str(prices_df.index[0]) if len(prices_df) > 0 else None,
            "end_date": str(prices_df.index[-1]) if len(prices_df) > 0 else None,
        }
        return {k: _py(v) for k, v in metrics.items()}


def _load_features_with_aliases(db_session, symbol: str) -> Optional[pd.DataFrame]:
    """Load features from training_features, trying all symbol aliases."""
    from database.models import TrainingFeature

    for alias in _get_all_aliases(symbol):
        features = db_session.query(TrainingFeature).filter(
            TrainingFeature.symbol == alias
        ).order_by(TrainingFeature.date).all()
        if features:
            print(f"[Backtest] {symbol}: loaded {len(features)} features under alias '{alias}'")
            records = []
            for f in features:
                row = f.features if isinstance(f.features, dict) else {}
                row["_date"] = f.date
                records.append(row)
            df = pd.DataFrame(records).set_index("_date").sort_index()
            return df

    print(f"[Backtest] {symbol}: no features found (tried {_get_all_aliases(symbol)})")
    return None


def _load_prices_with_aliases(db_session, symbol: str) -> Optional[pd.DataFrame]:
    """Load prices from historical_prices, trying all symbol aliases + yfinance fallback."""
    from database.models import HistoricalPrice

    for alias in _get_all_aliases(symbol):
        prices = db_session.query(HistoricalPrice).filter(
            HistoricalPrice.symbol == alias
        ).order_by(HistoricalPrice.date).all()
        if len(prices) >= 60:
            print(f"[Backtest] {symbol}: loaded {len(prices)} price rows under alias '{alias}'")
            return pd.DataFrame([{
                "date": p.date, "close": p.close
            } for p in prices]).set_index("date").sort_index()

    # yfinance fallback
    print(f"[Backtest] {symbol}: no DB prices, trying yfinance...")
    try:
        import yfinance as yf
        hist = yf.Ticker(symbol).history(period="3y", interval="1d")
        if len(hist) >= 60:
            print(f"[Backtest] {symbol}: got {len(hist)} rows from yfinance")
            return pd.DataFrame({"close": hist["Close"].values}, index=hist.index.date)
    except Exception as e:
        print(f"[Backtest] {symbol}: yfinance failed: {e}")

    return None


def backtest_symbol(symbol: str, job_id: str = "manual") -> Optional[Dict]:
    """Run full backtest for a single symbol and store results."""
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from database.connection import SessionLocal
    from database.models import BacktestResult

    print(f"\n[Backtest] === Starting {symbol} ===")
    db = SessionLocal()
    if not db:
        return {"symbol": symbol, "error": "Database not available"}

    try:
        price_df = _load_prices_with_aliases(db, symbol)
        if price_df is None:
            db.close()
            return {"symbol": symbol, "error": "No price data"}

        feat_df = _load_features_with_aliases(db, symbol)

        bt = Backtester(symbol)
        model = bt._load_model()
        print(f"[Backtest] {symbol}: model={'loaded' if model else 'none'}, "
              f"prices={len(price_df)}, features={len(feat_df) if feat_df is not None else 0}")

        metrics = bt.run(price_df, feat_df)
        print(f"[Backtest] {symbol}: return={metrics['total_return_pct']}%, "
              f"sharpe={metrics['sharpe_ratio']}, trades={metrics['total_trades']}, "
              f"trades/yr={metrics['trades_per_year']}")

        # Store in DB
        db.add(BacktestResult(
            symbol=symbol,
            start_date=price_df.index[0] if len(price_df) > 0 else None,
            end_date=price_df.index[-1] if len(price_df) > 0 else None,
            initial_capital=float(bt.initial_capital),
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
    """Run backtest for all symbols. Synchronous, returns results directly."""
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from database.connection import SessionLocal
    from database.models import HistoricalPrice

    print(f"\n[Backtest] ========== STARTING backtest_all ==========")

    db = SessionLocal()
    try:
        symbols = [r[0] for r in db.query(HistoricalPrice.symbol).distinct().all()]
        print(f"[Backtest] Found {len(symbols)} symbols in historical_prices")
        db.close()
    except Exception as e:
        print(f"[Backtest] DB query failed: {e}")
        traceback.print_exc()
        db.close()
        symbols = ["AAPL", "MSFT", "NVDA", "BTC-USD", "ETH-USD", "GC=F", "^VIX"]

    results = []
    for i, symbol in enumerate(symbols):
        result = backtest_symbol(symbol, job_id)
        if result:
            results.append(result)

    ok = len([r for r in results if "total_return_pct" in r])
    fail = len([r for r in results if "error" in r])
    print(f"\n[Backtest] ========== COMPLETE: {ok} ok, {fail} failed ==========")
    return results
