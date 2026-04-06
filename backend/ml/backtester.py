"""
Backtesting Engine for AURA
Walk-forward validation with realistic fees, slippage, and position sizing.
"""

import os
import sys
import logging
import pickle
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

MODELS_DIR = os.path.join(os.path.dirname(__file__), "..", "models")

# Map historical_prices symbols (yfinance) → model file symbols (asset_predictor)
# and vice versa, so the backtester can find models regardless of naming
SYMBOL_ALIASES = {
    "BTC-USD": ["BTCUSDC", "BTCUSDT", "BTC-USD"],
    "ETH-USD": ["ETHUSDC", "ETHUSDT", "ETH-USD"],
    "BNB-USD": ["BNBUSDC", "BNBUSDT", "BNB-USD"],
    "XRP-USD": ["XRPUSDC", "XRPUSDT", "XRP-USD"],
    "SOL-USD": ["SOLUSDC", "SOLUSDT", "SOL-USD"],
    "ADA-USD": ["ADAUSDC", "ADAUSDT", "ADA-USD"],
    "AVAX-USD": ["AVAXUSDC", "AVAXUSDT", "AVAX-USD"],
    "DOT-USD": ["DOTUSDC", "DOTUSDT", "DOT-USD"],
    "LINK-USD": ["LINKUSDC", "LINKUSDT", "LINK-USD"],
    "GC=F": ["GC=F", "GC1!", "XAUUSDC"],
    "SI=F": ["SI=F", "SI1!", "XAGUSDC"],
    "PL=F": ["PL=F", "XPTUSDC"],
    "PA=F": ["PA=F", "XPDUSDC"],
    "CL=F": ["CL=F", "CL1!"],
    "ES=F": ["ES=F", "ES1!"],
    "NQ=F": ["NQ=F", "NQ1!"],
    "^TNX": ["^TNX", "TNX"],
    "^IRX": ["^IRX", "IRX"],
    "^TYX": ["^TYX", "TYX"],
    "^VIX": ["^VIX", "VIX"],
    "EURUSD=X": ["EURUSD=X", "EURUSD"],
    "GBPEUR=X": ["GBPEUR=X", "GBPEUR"],
    "USDJPY=X": ["USDJPY=X", "USDJPY"],
}


class Backtester:
    """Core backtesting engine for a single symbol."""

    def __init__(self, symbol: str, initial_capital: float = 10000.0):
        self.symbol = symbol
        self.initial_capital = initial_capital
        self.binance_fee = 0.001   # 0.1% per trade
        self.slippage = 0.0005     # 0.05% slippage
        self.risk_free_rate = 0.04  # 4% annual (US treasury proxy)

    def _load_model(self) -> Optional[dict]:
        """Load the latest ensemble or xgboost model, trying all symbol aliases."""
        # Build list of symbol names to try
        candidates = [self.symbol]
        for key, aliases in SYMBOL_ALIASES.items():
            if self.symbol in aliases or self.symbol == key:
                candidates = [key] + aliases
                break

        for sym in candidates:
            for suffix in ["_ensemble_latest.pkl", "_xgboost_latest.pkl"]:
                path = os.path.join(MODELS_DIR, f"{sym}{suffix}")
                if os.path.exists(path):
                    with open(path, "rb") as f:
                        return pickle.load(f)
        return None

    def _generate_signals(self, features_df: pd.DataFrame, model_data: dict) -> pd.Series:
        """Generate prediction confidence from model on feature rows."""
        feature_cols = model_data.get("feature_cols", [])
        if not feature_cols:
            return pd.Series(0.5, index=features_df.index)

        # Build X with ALL expected feature columns, pad missing with 0
        X = np.zeros((len(features_df), len(feature_cols)))
        for i, col in enumerate(feature_cols):
            if col in features_df.columns:
                vals = features_df[col].fillna(0).values
                X[:, i] = vals

        scaler = model_data.get("scaler")
        if scaler:
            try:
                X = scaler.transform(X)
            except Exception as e:
                print(f"[Backtest] Scaler transform failed: {e}, using unscaled")

        # Ensemble model
        if "xgb_model" in model_data and "rf_model" in model_data:
            xgb_proba = model_data["xgb_model"].predict_proba(X)[:, 1]
            rf_proba = model_data["rf_model"].predict_proba(X)[:, 1]
            confidence = 0.6 * xgb_proba + 0.4 * rf_proba
        elif "model" in model_data:
            # Single model (xgboost regressor — predict returns)
            preds = model_data["model"].predict(X)
            # Normalize to 0-1 confidence range
            confidence = 1 / (1 + np.exp(-preds * 10))  # sigmoid
        else:
            confidence = np.full(len(X), 0.5)

        return pd.Series(confidence, index=features_df.index)

    def _position_size(self, confidence: float, mode: str = "tiered") -> float:
        """Calculate position size based on confidence."""
        if mode == "half_kelly":
            # Half-Kelly: f* = (p * b - q) / b, then take half
            p = confidence
            q = 1 - p
            b = 1.0  # assume 1:1 reward ratio
            kelly = (p * b - q) / b if b > 0 else 0
            return max(0, min(1, kelly / 2))

        # Tiered mode (default)
        if confidence < 0.55:
            return 0.0
        elif confidence < 0.60:
            return 0.25
        elif confidence < 0.70:
            return 0.50
        else:
            return 1.0

    def _threshold_signal(self, returns: pd.Series, threshold: float = 0.01) -> pd.Series:
        """Convert returns to threshold-based signals: BUY/SELL/NEUTRAL."""
        signals = pd.Series("NEUTRAL", index=returns.index)
        signals[returns > threshold] = "BUY"
        signals[returns < -threshold] = "SELL"
        return signals

    def run(self, prices_df: pd.DataFrame, features_df: Optional[pd.DataFrame] = None,
            position_mode: str = "tiered") -> Dict:
        """
        Run backtest simulation.

        Args:
            prices_df: DataFrame with date index, 'close' column
            features_df: DataFrame with engineered features (for model predictions)
            position_mode: 'tiered' or 'half_kelly'

        Returns:
            Dict with all performance metrics
        """
        model_data = self._load_model()

        # Generate confidence signals
        if features_df is not None and model_data is not None and len(features_df) > 0:
            confidences = self._generate_signals(features_df, model_data)
        else:
            # No model — use random confidence (baseline comparison)
            confidences = pd.Series(np.random.uniform(0.45, 0.65, len(prices_df)), index=prices_df.index)

        prices = prices_df["close"].values
        dates = prices_df.index

        # Align confidences to prices index
        conf_aligned = confidences.reindex(dates).fillna(0.5).values

        capital = self.initial_capital
        position = 0.0  # units held
        trades = []
        equity_curve = [capital]
        total_fees = 0.0

        for i in range(1, len(prices)):
            price = prices[i]
            prev_price = prices[i - 1]
            conf = conf_aligned[i] if i < len(conf_aligned) else 0.5

            # Determine position size
            target_alloc = self._position_size(conf, position_mode)

            # Current position value
            position_value = position * price
            total_value = capital + position_value

            # Target position in units
            target_value = total_value * target_alloc
            target_units = target_value / price if price > 0 else 0

            delta_units = target_units - position

            if abs(delta_units * price) < 1.0:
                # Skip tiny trades
                equity_curve.append(capital + position * price)
                continue

            # Execute trade
            trade_value = abs(delta_units * price)
            fee = trade_value * (self.binance_fee + self.slippage)
            total_fees += fee

            if delta_units > 0:
                # BUY
                cost = delta_units * price + fee
                if cost <= capital:
                    capital -= cost
                    position += delta_units
                    trades.append({
                        "date": str(dates[i]),
                        "type": "BUY",
                        "price": price,
                        "units": delta_units,
                        "value": trade_value,
                        "fee": fee,
                    })
            elif delta_units < 0:
                # SELL
                sell_units = min(abs(delta_units), position)
                revenue = sell_units * price - fee
                capital += revenue
                position -= sell_units
                trades.append({
                    "date": str(dates[i]),
                    "type": "SELL",
                    "price": price,
                    "units": sell_units,
                    "value": trade_value,
                    "fee": fee,
                })

            equity_curve.append(capital + position * price)

        # Final liquidation
        if position > 0:
            final_value = position * prices[-1]
            fee = final_value * self.binance_fee
            total_fees += fee
            capital += final_value - fee
            position = 0

        final_capital = capital
        equity = np.array(equity_curve)

        return self._calculate_metrics(
            equity, trades, prices_df, final_capital, total_fees
        )

    def _calculate_metrics(self, equity: np.ndarray, trades: List[Dict],
                           prices_df: pd.DataFrame, final_capital: float,
                           total_fees: float) -> Dict:
        """Calculate comprehensive performance metrics."""
        n_days = len(equity)
        n_years = n_days / 252 if n_days > 0 else 1

        total_return = (final_capital - self.initial_capital) / self.initial_capital
        annual_return = (1 + total_return) ** (1 / max(n_years, 0.01)) - 1

        # Daily returns
        daily_returns = np.diff(equity) / equity[:-1]
        daily_returns = daily_returns[np.isfinite(daily_returns)]

        # Sharpe ratio (annualized)
        if len(daily_returns) > 1 and np.std(daily_returns) > 0:
            excess_return = np.mean(daily_returns) - self.risk_free_rate / 252
            sharpe = excess_return / np.std(daily_returns) * np.sqrt(252)
        else:
            sharpe = 0.0

        # Sortino ratio (only downside deviation)
        downside = daily_returns[daily_returns < 0]
        if len(downside) > 1:
            downside_std = np.std(downside)
            excess_return = np.mean(daily_returns) - self.risk_free_rate / 252
            sortino = excess_return / downside_std * np.sqrt(252) if downside_std > 0 else 0
        else:
            sortino = 0.0

        # Max drawdown
        peak = np.maximum.accumulate(equity)
        drawdown = (equity - peak) / peak
        max_dd = float(np.min(drawdown)) if len(drawdown) > 0 else 0

        # Max drawdown duration
        dd_duration = 0
        max_dd_duration = 0
        for i in range(len(drawdown)):
            if drawdown[i] < 0:
                dd_duration += 1
                max_dd_duration = max(max_dd_duration, dd_duration)
            else:
                dd_duration = 0

        # Trade analysis
        trade_returns = []
        for i in range(0, len(trades) - 1, 2):
            if i + 1 < len(trades):
                buy_t = trades[i] if trades[i]["type"] == "BUY" else trades[i + 1]
                sell_t = trades[i + 1] if trades[i + 1]["type"] == "SELL" else trades[i]
                if buy_t["price"] > 0:
                    ret = (sell_t["price"] - buy_t["price"]) / buy_t["price"]
                    trade_returns.append(ret)

        winning = [r for r in trade_returns if r > 0]
        losing = [r for r in trade_returns if r <= 0]
        win_rate = len(winning) / len(trade_returns) * 100 if trade_returns else 0

        gross_profit = sum(winning) if winning else 0
        gross_loss = abs(sum(losing)) if losing else 0.001
        profit_factor = gross_profit / gross_loss

        calmar = annual_return / abs(max_dd) if max_dd != 0 else 0

        metrics = {
            "symbol": self.symbol,
            "initial_capital": self.initial_capital,
            "final_capital": round(final_capital, 2),
            "total_return_pct": round(total_return * 100, 2),
            "annual_return_pct": round(annual_return * 100, 2),
            "sharpe_ratio": round(float(sharpe), 3),
            "sortino_ratio": round(float(sortino), 3),
            "max_drawdown_pct": round(float(max_dd) * 100, 2),
            "max_drawdown_duration_days": int(max_dd_duration),
            "win_rate_pct": round(win_rate, 1),
            "profit_factor": round(profit_factor, 3),
            "total_trades": int(len(trades)),
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

        # Convert any remaining numpy types to native Python for PostgreSQL
        metrics = {k: (v.item() if hasattr(v, 'item') else v) for k, v in metrics.items()}

        return metrics


def run_walk_forward(symbol: str, db_session, train_months: int = 18,
                     test_months: int = 6, step_months: int = 3) -> List[Dict]:
    """Walk-forward validation: train windows → test windows → slide."""
    from database.models import HistoricalPrice, TrainingFeature

    prices = db_session.query(HistoricalPrice).filter(
        HistoricalPrice.symbol == symbol
    ).order_by(HistoricalPrice.date).all()

    if len(prices) < 200:
        return []

    price_df = pd.DataFrame([{
        "date": p.date, "close": p.close, "open": p.open,
        "high": p.high, "low": p.low, "volume": p.volume
    } for p in prices]).set_index("date").sort_index()

    # Load features
    features = db_session.query(TrainingFeature).filter(
        TrainingFeature.symbol == symbol
    ).order_by(TrainingFeature.date).all()

    feat_df = None
    if features:
        records = []
        for f in features:
            row = f.features if isinstance(f.features, dict) else {}
            row["_date"] = f.date
            records.append(row)
        feat_df = pd.DataFrame(records).set_index("_date").sort_index()

    # Walk-forward windows
    bt = Backtester(symbol)
    results = []
    start = price_df.index[0]
    end = price_df.index[-1]

    window_start = start
    while True:
        train_end = window_start + timedelta(days=train_months * 30)
        test_end = train_end + timedelta(days=test_months * 30)

        if test_end > end:
            break

        test_prices = price_df.loc[train_end:test_end]
        test_feats = feat_df.loc[train_end:test_end] if feat_df is not None else None

        if len(test_prices) < 20:
            window_start += timedelta(days=step_months * 30)
            continue

        metrics = bt.run(test_prices, test_feats)
        metrics["window"] = f"{train_end.isoformat()} to {test_end.isoformat()}"
        results.append(metrics)

        window_start += timedelta(days=step_months * 30)

    return results


def backtest_symbol(symbol: str, job_id: str = "manual") -> Optional[Dict]:
    """Run full backtest for a single symbol and store results."""
    import traceback
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from database.connection import SessionLocal
    from database.models import HistoricalPrice, TrainingFeature, BacktestResult

    print(f"[Backtest] Starting backtest for {symbol}")
    db = SessionLocal()
    if not db:
        print(f"[Backtest] ERROR: SessionLocal is None — DATABASE_URL not set?")
        return {"symbol": symbol, "error": "Database not available"}

    try:
        # Step 1: Load price data from DB
        prices = db.query(HistoricalPrice).filter(
            HistoricalPrice.symbol == symbol
        ).order_by(HistoricalPrice.date).all()
        print(f"[Backtest] {symbol}: loaded {len(prices)} rows from historical_prices")

        # Try alias symbols
        if len(prices) < 60:
            for key, aliases in SYMBOL_ALIASES.items():
                if symbol in aliases or symbol == key:
                    for alias in [key] + aliases:
                        if alias == symbol:
                            continue
                        alt = db.query(HistoricalPrice).filter(
                            HistoricalPrice.symbol == alias
                        ).order_by(HistoricalPrice.date).all()
                        if len(alt) >= 60:
                            print(f"[Backtest] {symbol}: found {len(alt)} rows under alias {alias}")
                            prices = alt
                            break
                    break

        # Step 2: yfinance fallback
        if len(prices) < 60:
            print(f"[Backtest] {symbol}: only {len(prices)} DB rows, trying yfinance...")
            try:
                import yfinance as yf
                ticker = yf.Ticker(symbol)
                hist = ticker.history(period="3y", interval="1d")
                if len(hist) >= 60:
                    price_df = pd.DataFrame({
                        "close": hist["Close"].values
                    }, index=hist.index.date)
                    price_df.index.name = "date"
                    print(f"[Backtest] {symbol}: got {len(hist)} rows from yfinance")
                else:
                    print(f"[Backtest] {symbol}: yfinance returned {len(hist)} rows — skipping")
                    db.close()
                    return {"symbol": symbol, "error": f"Insufficient data ({len(hist)} rows)"}
            except Exception as yf_err:
                print(f"[Backtest] {symbol}: yfinance fallback failed: {yf_err}")
                traceback.print_exc()
                db.close()
                return {"symbol": symbol, "error": f"yfinance: {yf_err}"}
        else:
            price_df = pd.DataFrame([{
                "date": p.date, "close": p.close
            } for p in prices]).set_index("date").sort_index()

        # Step 3: Load features (optional)
        features = db.query(TrainingFeature).filter(
            TrainingFeature.symbol == symbol
        ).order_by(TrainingFeature.date).all()
        print(f"[Backtest] {symbol}: loaded {len(features)} feature rows")

        feat_df = None
        if features:
            records = []
            for f in features:
                row = f.features if isinstance(f.features, dict) else {}
                row["_date"] = f.date
                records.append(row)
            feat_df = pd.DataFrame(records).set_index("_date").sort_index()

        # Step 4: Load model
        bt = Backtester(symbol)
        model = bt._load_model()
        print(f"[Backtest] {symbol}: model loaded = {model is not None}")

        # Step 5: Run backtest
        metrics = bt.run(price_df, feat_df)
        print(f"[Backtest] {symbol}: return={metrics['total_return_pct']}%, "
              f"sharpe={metrics['sharpe_ratio']}, trades={metrics['total_trades']}")

        # Step 6: Store in DB — ensure all values are native Python types
        def _py(v):
            if hasattr(v, 'item'):
                return v.item()
            return v

        db.add(BacktestResult(
            symbol=symbol,
            start_date=price_df.index[0] if len(price_df) > 0 else None,
            end_date=price_df.index[-1] if len(price_df) > 0 else None,
            initial_capital=float(_py(bt.initial_capital)),
            final_capital=float(_py(metrics["final_capital"])),
            total_return_pct=float(_py(metrics["total_return_pct"])),
            annual_return_pct=float(_py(metrics["annual_return_pct"])),
            sharpe_ratio=float(_py(metrics["sharpe_ratio"])),
            sortino_ratio=float(_py(metrics["sortino_ratio"])),
            max_drawdown_pct=float(_py(metrics["max_drawdown_pct"])),
            win_rate_pct=float(_py(metrics["win_rate_pct"])),
            profit_factor=float(_py(metrics["profit_factor"])),
            total_trades=int(_py(metrics["total_trades"])),
            total_fees_paid=float(_py(metrics["total_fees_paid"])),
            calmar_ratio=float(_py(metrics["calmar_ratio"])),
            metrics_json={k: (_py(v) if not isinstance(v, str) and v is not None else v) for k, v in metrics.items()},
        ))
        db.commit()
        print(f"[Backtest] {symbol}: saved to backtest_results")
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
    """Run backtest for all symbols. Returns results directly (synchronous)."""
    import traceback
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from database.connection import SessionLocal
    from database.models import HistoricalPrice

    print(f"[Backtest] === Starting backtest_all (job={job_id}) ===")

    db = SessionLocal()
    if not db:
        print("[Backtest] ERROR: SessionLocal is None")
        return [{"error": "Database not available"}]

    try:
        symbols = [r[0] for r in db.query(HistoricalPrice.symbol).distinct().all()]
        print(f"[Backtest] Found {len(symbols)} symbols in historical_prices: {symbols[:5]}...")
        db.close()
    except Exception as e:
        print(f"[Backtest] ERROR querying symbols: {e}")
        traceback.print_exc()
        db.close()
        # Fallback: use yfinance symbols directly
        symbols = ["AAPL", "MSFT", "NVDA", "BTC-USD", "ETH-USD", "GC=F", "^VIX"]
        print(f"[Backtest] Using fallback symbols: {symbols}")

    results = []
    for i, symbol in enumerate(symbols):
        print(f"\n[Backtest] === {symbol} ({i+1}/{len(symbols)}) ===")
        try:
            result = backtest_symbol(symbol, job_id)
            if result:
                results.append(result)
        except Exception as e:
            print(f"[Backtest] {symbol} OUTER EXCEPTION: {e}")
            traceback.print_exc()
            results.append({"symbol": symbol, "error": str(e)})

    succeeded = len([r for r in results if "total_return_pct" in r])
    failed = len([r for r in results if "error" in r])
    print(f"\n[Backtest] === COMPLETE: {succeeded} succeeded, {failed} failed, {len(symbols)} total ===")
    return results
