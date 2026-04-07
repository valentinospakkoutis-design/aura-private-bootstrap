"""
Auto Training Pipeline for AURA
Fetches real OHLCV data from Binance, engineers 50+ features,
trains XGBoost models for all USDC crypto pairs, and schedules
weekly retraining with model versioning.
"""

import os
import json
import pickle
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import httpx
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

logger = logging.getLogger(__name__)

BINANCE_BASE = "https://api.binance.com"
MODELS_DIR = os.path.join(os.path.dirname(__file__), "..", "models")

# All 27 tradeable USDC pairs
TRAINING_SYMBOLS = [
    "BTCUSDC", "ETHUSDC", "BNBUSDC", "ADAUSDC", "SOLUSDC",
    "XRPUSDC", "DOTUSDC", "POLUSDC", "LINKUSDC", "AVAXUSDC",
    "SHIBUSDC", "DOGEUSDC", "TRXUSDC", "LTCUSDC", "BCHUSDC",
    "ETCUSDC", "XLMUSDC", "ALGOUSDC", "ATOMUSDC", "NEARUSDC",
    "ICPUSDC", "FILUSDC", "AAVEUSDC",
    "UNIUSDC", "SANDUSDC", "AXSUSDC", "THETAUSDC",
]


def fetch_binance_ohlcv(symbol: str, interval: str = "1d", days: int = 730) -> Optional[pd.DataFrame]:
    """
    Fetch historical OHLCV data from Binance public API.
    Binance klines endpoint returns max 1000 candles per request,
    so we paginate for longer histories.
    """
    all_klines = []
    end_time = int(time.time() * 1000)
    limit = 1000

    # For 1d interval, 730 days needs 1 request (730 < 1000)
    # For 1h interval, 730 days = 17520 candles, needs ~18 requests
    # For 4h interval, 730 days = 4380 candles, needs ~5 requests
    intervals_per_day = {"1d": 1, "4h": 6, "1h": 24}
    total_candles = days * intervals_per_day.get(interval, 1)

    try:
        while len(all_klines) < total_candles:
            params = {
                "symbol": symbol.upper(),
                "interval": interval,
                "endTime": end_time,
                "limit": limit,
            }
            with httpx.Client(base_url=BINANCE_BASE, timeout=15.0) as client:
                resp = client.get("/api/v3/klines", params=params)
                resp.raise_for_status()
                klines = resp.json()

            if not klines:
                break

            all_klines = klines + all_klines  # prepend older data
            end_time = klines[0][0] - 1  # move window back

            if len(klines) < limit:
                break  # no more data

            time.sleep(0.1)  # rate limit courtesy

        if not all_klines:
            return None

        df = pd.DataFrame(all_klines, columns=[
            "open_time", "open", "high", "low", "close", "volume",
            "close_time", "quote_volume", "trades", "taker_buy_base",
            "taker_buy_quote", "ignore"
        ])

        for col in ["open", "high", "low", "close", "volume", "quote_volume"]:
            df[col] = df[col].astype(float)

        df["timestamp"] = pd.to_datetime(df["open_time"], unit="ms")
        df = df.set_index("timestamp")
        df = df[["open", "high", "low", "close", "volume", "quote_volume", "trades"]]
        df["trades"] = df["trades"].astype(int)

        # Remove duplicates
        df = df[~df.index.duplicated(keep="last")]
        df = df.sort_index()

        return df

    except Exception as e:
        logger.error(f"Failed to fetch OHLCV for {symbol} {interval}: {e}")
        return None


def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Engineer 50+ features from OHLCV data.
    Returns DataFrame with feature columns and a 'target' column
    (next-day close price).
    """
    feat = df.copy()
    close = feat["close"]
    high = feat["high"]
    low = feat["low"]
    volume = feat["volume"]

    # ── Price features ───────────────────────────────────────
    feat["return_1d"] = close.pct_change(1)
    feat["return_3d"] = close.pct_change(3)
    feat["return_7d"] = close.pct_change(7)
    feat["return_14d"] = close.pct_change(14)
    feat["return_30d"] = close.pct_change(30)

    # ── Moving averages ──────────────────────────────────────
    for w in [7, 14, 21, 50, 100, 200]:
        feat[f"sma_{w}"] = close.rolling(w).mean()
        feat[f"ema_{w}"] = close.ewm(span=w, adjust=False).mean()

    # SMA crossover signals
    feat["sma_7_21_cross"] = (feat["sma_7"] - feat["sma_21"]) / feat["sma_21"]
    feat["sma_50_200_cross"] = (feat["sma_50"] - feat["sma_200"]) / feat["sma_200"]

    # Price relative to SMAs
    for w in [7, 21, 50, 200]:
        feat[f"price_vs_sma_{w}"] = (close - feat[f"sma_{w}"]) / feat[f"sma_{w}"]

    # ── Volatility ───────────────────────────────────────────
    feat["volatility_7"] = close.rolling(7).std()
    feat["volatility_14"] = close.rolling(14).std()
    feat["volatility_30"] = close.rolling(30).std()
    feat["atr_14"] = _atr(high, low, close, 14)

    # Bollinger Bands (20, 2)
    bb_mid = close.rolling(20).mean()
    bb_std = close.rolling(20).std()
    feat["bb_upper"] = bb_mid + 2 * bb_std
    feat["bb_lower"] = bb_mid - 2 * bb_std
    feat["bb_width"] = (feat["bb_upper"] - feat["bb_lower"]) / bb_mid
    feat["bb_position"] = (close - feat["bb_lower"]) / (feat["bb_upper"] - feat["bb_lower"])

    # ── Momentum indicators ──────────────────────────────────
    # RSI
    feat["rsi_14"] = _rsi(close, 14)
    feat["rsi_7"] = _rsi(close, 7)

    # MACD (12, 26, 9)
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    feat["macd"] = ema12 - ema26
    feat["macd_signal"] = feat["macd"].ewm(span=9, adjust=False).mean()
    feat["macd_histogram"] = feat["macd"] - feat["macd_signal"]

    # Stochastic Oscillator (14, 3)
    low14 = low.rolling(14).min()
    high14 = high.rolling(14).max()
    feat["stoch_k"] = 100 * (close - low14) / (high14 - low14)
    feat["stoch_d"] = feat["stoch_k"].rolling(3).mean()

    # Rate of Change
    feat["roc_10"] = close.pct_change(10) * 100
    feat["roc_20"] = close.pct_change(20) * 100

    # ── Volume features ──────────────────────────────────────
    feat["volume_sma_7"] = volume.rolling(7).mean()
    feat["volume_sma_21"] = volume.rolling(21).mean()
    feat["volume_ratio"] = volume / feat["volume_sma_21"]

    # On-Balance Volume (OBV)
    obv = (np.sign(close.diff()) * volume).fillna(0).cumsum()
    feat["obv"] = obv
    feat["obv_sma_14"] = obv.rolling(14).mean()
    feat["obv_trend"] = obv - feat["obv_sma_14"]

    # Volume-Price Trend
    feat["vpt"] = (volume * close.pct_change()).fillna(0).cumsum()

    # ── Candlestick features ─────────────────────────────────
    feat["body_size"] = abs(close - feat["open"]) / feat["open"]
    feat["upper_shadow"] = (high - pd.concat([close, feat["open"]], axis=1).max(axis=1)) / close
    feat["lower_shadow"] = (pd.concat([close, feat["open"]], axis=1).min(axis=1) - low) / close
    feat["high_low_range"] = (high - low) / close

    # ── Lag features ─────────────────────────────────────────
    for lag in [1, 2, 3, 5, 7]:
        feat[f"close_lag_{lag}"] = close.shift(lag)
        feat[f"return_lag_{lag}"] = feat["return_1d"].shift(lag)

    # ── Target: next-day close ───────────────────────────────
    feat["target"] = close.shift(-1)

    # Drop rows with NaN (from rolling windows and target shift)
    feat = feat.dropna()

    return feat


def _rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0).rolling(period).mean()
    loss = (-delta.where(delta < 0, 0.0)).rolling(period).mean()
    rs = gain / loss.replace(0, np.inf)
    return 100 - (100 / (1 + rs))


def _atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs()
    ], axis=1).max(axis=1)
    return tr.rolling(period).mean()


def train_symbol(symbol: str, days: int = 730) -> Optional[Dict]:
    """
    Train an XGBoost model for a single symbol using real Binance data.
    Returns training metrics or None on failure.
    """
    try:
        import xgboost as xgb
    except ImportError:
        logger.error("xgboost not installed. Run: pip install xgboost")
        return None

    logger.info(f"[trainer] Training {symbol}...")

    # Fetch daily OHLCV
    df = fetch_binance_ohlcv(symbol, interval="1d", days=days)
    if df is None or len(df) < 200:
        logger.warning(f"[trainer] Insufficient data for {symbol}: {len(df) if df is not None else 0} rows")
        return None

    # Also fetch 4h data for multi-timeframe features
    df_4h = fetch_binance_ohlcv(symbol, interval="4h", days=min(days, 180))

    # Engineer features on daily
    feat = engineer_features(df)

    # Add 4h aggregated features if available
    if df_4h is not None and len(df_4h) > 50:
        feat = _add_multi_timeframe_features(feat, df_4h)

    if len(feat) < 100:
        logger.warning(f"[trainer] Not enough features rows for {symbol}: {len(feat)}")
        return None

    # Separate features and target
    exclude_cols = ["target", "open", "high", "low", "close", "volume",
                    "quote_volume", "trades"]
    feature_cols = [c for c in feat.columns if c not in exclude_cols]
    X = feat[feature_cols].values
    y = feat["target"].values

    # Train/test split (chronological, not random)
    split_idx = int(len(X) * 0.8)
    X_train, X_test = X[:split_idx], X[split_idx:]
    y_train, y_test = y[:split_idx], y[split_idx:]

    # Scale features
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    # Train XGBoost
    model = xgb.XGBRegressor(
        n_estimators=300,
        max_depth=6,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        reg_alpha=0.1,
        reg_lambda=1.0,
        random_state=42,
        n_jobs=-1,
        verbosity=0,
    )
    model.fit(
        X_train_scaled, y_train,
        eval_set=[(X_test_scaled, y_test)],
        verbose=False,
    )

    # Evaluate
    y_pred_train = model.predict(X_train_scaled)
    y_pred_test = model.predict(X_test_scaled)

    # Direction accuracy (did we predict up/down correctly?)
    train_dir = np.sign(y_pred_train[1:] - y_train[:-1]) == np.sign(y_train[1:] - y_train[:-1])
    test_dir = np.sign(y_pred_test[1:] - y_test[:-1]) == np.sign(y_test[1:] - y_test[:-1])

    metrics = {
        "train_mae": float(mean_absolute_error(y_train, y_pred_train)),
        "test_mae": float(mean_absolute_error(y_test, y_pred_test)),
        "train_rmse": float(np.sqrt(mean_squared_error(y_train, y_pred_train))),
        "test_rmse": float(np.sqrt(mean_squared_error(y_test, y_pred_test))),
        "train_r2": float(r2_score(y_train, y_pred_train)),
        "test_r2": float(r2_score(y_test, y_pred_test)),
        "train_direction_accuracy": float(train_dir.mean() * 100) if len(train_dir) > 0 else 0,
        "test_direction_accuracy": float(test_dir.mean() * 100) if len(test_dir) > 0 else 0,
        "training_samples": len(X_train),
        "test_samples": len(X_test),
        "feature_count": len(feature_cols),
    }

    logger.info(f"[trainer] {symbol}: R²={metrics['test_r2']:.3f}, "
                f"Dir={metrics['test_direction_accuracy']:.1f}%, "
                f"MAE=${metrics['test_mae']:.2f}")

    # Save model with version
    os.makedirs(MODELS_DIR, exist_ok=True)
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    model_filename = f"{symbol}_xgboost_v{timestamp}.pkl"
    model_path = os.path.join(MODELS_DIR, model_filename)

    model_data = {
        "model": model,
        "scaler": scaler,
        "feature_cols": feature_cols,
        "symbol": symbol,
        "model_type": "xgboost",
        "trained_at": datetime.utcnow().isoformat(),
        "metrics": metrics,
        "data_rows": len(feat),
        "data_range": f"{feat.index[0]} to {feat.index[-1]}",
    }

    with open(model_path, "wb") as f:
        pickle.dump(model_data, f)

    # Also save as "latest" symlink/copy for easy loading
    latest_path = os.path.join(MODELS_DIR, f"{symbol}_xgboost_latest.pkl")
    with open(latest_path, "wb") as f:
        pickle.dump(model_data, f)

    logger.info(f"[trainer] Saved {model_filename}")

    return {
        "symbol": symbol,
        "model_path": model_filename,
        "metrics": metrics,
        "trained_at": datetime.utcnow().isoformat(),
    }


def _add_multi_timeframe_features(daily_feat: pd.DataFrame, df_4h: pd.DataFrame) -> pd.DataFrame:
    """Add 4h-aggregated features to the daily feature DataFrame."""
    try:
        close_4h = df_4h["close"]
        vol_4h = df_4h["volume"]

        # Resample 4h to daily aggregates
        daily_from_4h = df_4h.resample("1D").agg({
            "high": "max",
            "low": "min",
            "close": "last",
            "volume": "sum",
        }).dropna()

        # 4h volatility (std of 4h closes within each day)
        intraday_vol = close_4h.resample("1D").std()
        daily_feat["volatility_4h"] = intraday_vol.reindex(daily_feat.index, method="ffill")

        # 4h RSI (last value of day)
        rsi_4h = _rsi(close_4h, 14)
        rsi_4h_daily = rsi_4h.resample("1D").last()
        daily_feat["rsi_4h"] = rsi_4h_daily.reindex(daily_feat.index, method="ffill")

        # 4h trend (SMA 6 vs 12 on 4h)
        sma6_4h = close_4h.rolling(6).mean()
        sma12_4h = close_4h.rolling(12).mean()
        trend_4h = ((sma6_4h - sma12_4h) / sma12_4h).resample("1D").last()
        daily_feat["trend_4h"] = trend_4h.reindex(daily_feat.index, method="ffill")

    except Exception as e:
        logger.debug(f"Multi-timeframe feature error: {e}")

    return daily_feat


def train_all_symbols(days: int = 730) -> List[Dict]:
    """Train models for all USDC crypto pairs. Returns list of results."""
    results = []
    for symbol in TRAINING_SYMBOLS:
        try:
            result = train_symbol(symbol, days=days)
            if result:
                results.append(result)
            time.sleep(1)  # rate limit between symbols
        except Exception as e:
            logger.error(f"[trainer] Failed training {symbol}: {e}")
            results.append({"symbol": symbol, "error": str(e)})

    # Save training history
    history_path = os.path.join(MODELS_DIR, "..", "training_history.json")
    try:
        with open(history_path, "w") as f:
            json.dump(results, f, indent=2)
    except Exception as e:
        logger.error(f"Failed to save training history: {e}")

    logger.info(f"[trainer] Training complete: {len([r for r in results if 'metrics' in r])}/{len(TRAINING_SYMBOLS)} succeeded")
    return results


def train_missing_models(days: int = 730) -> List[Dict]:
    """
    Check which symbols are missing a trained model and train only those.
    Called on startup to recover from ephemeral filesystem wipes.
    """
    os.makedirs(MODELS_DIR, exist_ok=True)
    missing = []
    for symbol in TRAINING_SYMBOLS:
        model_path = os.path.join(MODELS_DIR, f"{symbol}_xgboost_latest.pkl")
        if not os.path.exists(model_path):
            missing.append(symbol)

    if not missing:
        logger.info(f"[trainer] All {len(TRAINING_SYMBOLS)} models present, no training needed")
        return []

    logger.info(f"[trainer] {len(missing)}/{len(TRAINING_SYMBOLS)} models missing, training: {', '.join(missing)}")

    results = []
    for symbol in missing:
        try:
            result = train_symbol(symbol, days=days)
            if result:
                results.append(result)
            time.sleep(1)
        except Exception as e:
            logger.error(f"[trainer] Failed training {symbol}: {e}")
            results.append({"symbol": symbol, "error": str(e)})

    succeeded = len([r for r in results if "metrics" in r])
    logger.info(f"[trainer] Startup training complete: {succeeded}/{len(missing)} succeeded")
    return results


def _daily_xgboost_retrain():
    """Daily XGBoost retraining job — trains all symbols."""
    logger.info("[scheduler] Starting daily XGBoost retraining...")
    try:
        results = train_all_symbols()
        succeeded = len([r for r in results if "metrics" in r])
        logger.info(f"[scheduler] Daily XGBoost retrain done: {succeeded}/{len(results)} succeeded")
    except Exception as e:
        logger.error(f"[scheduler] Daily XGBoost retrain failed: {e}")


def _daily_predictions_refresh():
    """Daily predictions refresh — generates fresh predictions for all symbols."""
    logger.info("[scheduler] Starting daily predictions refresh...")
    try:
        from ai.asset_predictor import asset_predictor
        result = asset_predictor.get_all_predictions(days=7)
        count = len(result.get("predictions", {}))
        logger.info(f"[scheduler] Daily predictions refresh done: {count} symbols")
    except Exception as e:
        logger.error(f"[scheduler] Daily predictions refresh failed: {e}")


def setup_weekly_retraining():
    """Schedule all recurring training and prediction jobs using APScheduler."""
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.triggers.cron import CronTrigger

        scheduler = BackgroundScheduler()

        # Weekly full retraining — Sunday 00:00 UTC
        scheduler.add_job(
            train_all_symbols,
            trigger=CronTrigger(day_of_week="sun", hour=0, minute=0),
            id="weekly_retrain",
            name="Weekly model retraining",
            replace_existing=True,
        )

        # Daily XGBoost retraining — 06:00 UTC (09:00 Cyprus)
        scheduler.add_job(
            _daily_xgboost_retrain,
            trigger=CronTrigger(hour=6, minute=0),
            id="daily_xgboost_retrain",
            name="Daily XGBoost retraining",
            replace_existing=True,
        )

        # Daily predictions refresh — 06:05 UTC (09:05 Cyprus)
        scheduler.add_job(
            _daily_predictions_refresh,
            trigger=CronTrigger(hour=6, minute=5),
            id="daily_predictions_refresh",
            name="Daily predictions refresh",
            replace_existing=True,
        )

        scheduler.start()
        logger.info("[trainer] Scheduled jobs: weekly retrain (Sun 00:00), daily XGBoost (06:00), daily predictions (06:05)")
        return scheduler
    except ImportError:
        logger.warning("[trainer] APScheduler not installed, scheduled jobs disabled")
        return None
    except Exception as e:
        logger.error(f"[trainer] Failed to setup scheduler: {e}")
        return None
