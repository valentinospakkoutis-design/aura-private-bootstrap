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

LABEL_THRESHOLD = 0.01  # 1% threshold for UP/DOWN vs SIDEWAYS

BINANCE_BASE = "https://api.binance.com"
MODELS_DIR = os.path.join(os.path.dirname(__file__), "..", "models")

# All 27 tradeable USDC crypto pairs (fetched from Binance)
CRYPTO_SYMBOLS = [
    "BTCUSDC", "ETHUSDC", "BNBUSDC", "ADAUSDC", "SOLUSDC",
    "XRPUSDC", "DOTUSDC", "POLUSDC", "LINKUSDC", "AVAXUSDC",
    "SHIBUSDC", "DOGEUSDC", "TRXUSDC", "LTCUSDC", "BCHUSDC",
    "ETCUSDC", "XLMUSDC", "ALGOUSDC", "ATOMUSDC", "NEARUSDC",
    "ICPUSDC", "FILUSDC", "AAVEUSDC",
    "UNIUSDC", "SANDUSDC", "AXSUSDC", "THETAUSDC",
]

# Non-crypto assets (fetched from yfinance)
# Maps AURA symbol → yfinance ticker
YFINANCE_SYMBOL_MAP = {
    # Metals
    "XAUUSDC": "GC=F",
    "XAGUSDC": "SI=F",
    "XPDUSDC": "PA=F",
    "XPTUSDC": "PL=F",
    # US Stocks
    "AAPL": "AAPL",
    "MSFT": "MSFT",
    "GOOGL": "GOOGL",
    "AMZN": "AMZN",
    "NVDA": "NVDA",
    "TSLA": "TSLA",
    "META": "META",
    "JPM": "JPM",
    "BAC": "BAC",
    # EU Stocks
    "SAP": "SAP",
    "ASML": "ASML",
    "LVMH": "MC.PA",
    # Forex
    "EURUSD": "EURUSD=X",
    "GBPUSD": "GBPUSD=X",
    "USDJPY": "USDJPY=X",
    "AUDUSD": "AUDUSD=X",
    # Bonds / Indices
    "TNX": "^TNX",
    "VIX": "^VIX",
}

YFINANCE_SYMBOLS = list(YFINANCE_SYMBOL_MAP.keys())

# Combined list — crypto first, then yfinance assets
TRAINING_SYMBOLS = CRYPTO_SYMBOLS + YFINANCE_SYMBOLS


def fetch_ohlcv(symbol: str, days: int = 365, interval: str = "1d") -> Optional[pd.DataFrame]:
    """Fetch OHLCV using the existing crypto/yfinance split."""
    if symbol in YFINANCE_SYMBOL_MAP:
        return fetch_yfinance_ohlcv(symbol, days=days)
    return fetch_binance_ohlcv(symbol, interval=interval, days=days)


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


def fetch_yfinance_ohlcv(symbol: str, days: int = 1095) -> Optional[pd.DataFrame]:
    """
    Fetch historical OHLCV from yfinance for non-crypto assets.
    Returns DataFrame in the same format as fetch_binance_ohlcv().
    """
    yf_ticker = YFINANCE_SYMBOL_MAP.get(symbol)
    if not yf_ticker:
        logger.warning(f"[trainer] No yfinance mapping for {symbol}")
        return None

    try:
        import yfinance as yf

        period = "3y" if days >= 730 else ("2y" if days >= 365 else "1y")
        ticker = yf.Ticker(yf_ticker)
        hist = ticker.history(period=period, interval="1d")

        if hist is None or hist.empty:
            logger.warning(f"[trainer] No data available for {symbol} (yf: {yf_ticker})")
            return None

        df = pd.DataFrame({
            "open": hist["Open"].astype(float),
            "high": hist["High"].astype(float),
            "low": hist["Low"].astype(float),
            "close": hist["Close"].astype(float),
            "volume": hist["Volume"].astype(float) if "Volume" in hist.columns else 0.0,
        })
        df.index = pd.to_datetime(hist.index)
        df.index = df.index.tz_localize(None)  # remove timezone for consistency
        df["quote_volume"] = df["volume"] * df["close"]
        df["trades"] = 0

        df = df[~df.index.duplicated(keep="last")]
        df = df.sort_index()

        logger.info(f"[trainer] Fetched {len(df)} rows for {symbol} via yfinance ({yf_ticker})")
        return df

    except Exception as e:
        logger.error(f"[trainer] yfinance fetch failed for {symbol} ({yf_ticker}): {e}")
        return None


def engineer_features(df: pd.DataFrame, onchain_data: Optional[pd.DataFrame] = None) -> pd.DataFrame:
    """
    Engineer 50+ features from OHLCV data.
    Optionally adds on-chain features (score, sentiment, funding_rate, long_short_ratio).
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

    # ── On-Chain Features (if available) ──────────────────────
    if onchain_data is not None and not onchain_data.empty:
        # Merge on-chain data (must be indexed by date and sorted)
        try:
            # Shift on-chain data by 1 day to avoid lookahead bias
            # (use previous day's on-chain data to predict current day's close)
            onchain_data = onchain_data.shift(1)
            
            # Forward fill NaNs to handle gaps in on-chain updates
            onchain_cols = onchain_data.columns.tolist()
            for col in onchain_cols:
                if col in onchain_data.columns:
                    onchain_data[col] = onchain_data[col].fillna(method='ffill')
            
            # Merge on index (date)
            feat = feat.join(onchain_data, how='left')
            
            # Fill any remaining NaNs with mean of on-chain features
            onchain_numeric_cols = [c for c in onchain_cols if c in feat.columns]
            for col in onchain_numeric_cols:
                if col in feat.columns:
                    feat[col].fillna(feat[col].mean(), inplace=True)
            
            logger.info(f"[trainer] Added {len(onchain_cols)} on-chain features")
        except Exception as e:
            logger.warning(f"[trainer] Failed to add on-chain features: {e}")

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


def calculate_trend(df: Optional[pd.DataFrame]) -> int:
    """Return trend score as -1 (bearish), 0 (neutral), 1 (bullish)."""
    if df is None or df.empty or "close" not in df.columns or len(df) < 30:
        return 0

    close = df["close"].astype(float)
    sma_fast = close.rolling(12).mean().iloc[-1]
    sma_slow = close.rolling(26).mean().iloc[-1]

    if pd.isna(sma_fast) or pd.isna(sma_slow) or sma_slow == 0:
        return 0

    delta = (sma_fast - sma_slow) / sma_slow
    if delta > 0.003:
        return 1
    if delta < -0.003:
        return -1
    return 0


def calculate_rsi(df: Optional[pd.DataFrame], period: int = 14) -> float:
    """Return latest RSI value from OHLCV close series."""
    if df is None or df.empty or "close" not in df.columns or len(df) < period + 2:
        return 50.0

    rsi_series = _rsi(df["close"].astype(float), period)
    last_val = rsi_series.iloc[-1]
    if pd.isna(last_val):
        return 50.0
    return float(last_val)


def fetch_mtf_features(symbol: str, is_crypto: bool = True) -> Dict:
    """Fetch runtime multi-timeframe features used as an additive prediction layer."""
    if not is_crypto:
        # yfinance intraday history is limited/unreliable for long lookbacks
        return {}

    h1 = fetch_binance_ohlcv(symbol, "1h", days=90)
    h4 = fetch_binance_ohlcv(symbol, "4h", days=180)
    if h1 is None or h4 is None or h1.empty or h4.empty:
        return {}

    trend_1h = calculate_trend(h1)
    trend_4h = calculate_trend(h4)
    rsi_1h = calculate_rsi(h1)
    rsi_4h = calculate_rsi(h4)
    volume_surge_1h = False
    if "volume" in h1.columns and len(h1) > 10:
        volume_surge_1h = bool(h1["volume"].iloc[-1] > (h1["volume"].mean() * 1.5))

    return {
        "trend_1h": trend_1h,
        "trend_4h": trend_4h,
        "rsi_1h": rsi_1h,
        "rsi_4h": rsi_4h,
        "volume_surge_1h": volume_surge_1h,
        "mtf_confluence": trend_1h == trend_4h,
    }


def fetch_onchain_history(symbol: str, days: int = 730) -> Optional[pd.DataFrame]:
    """
    Fetch on-chain signal history from database for a crypto symbol.
    Returns DataFrame indexed by date with on-chain features or None.
    """
    try:
        from database.connection import SessionLocal
        from sqlalchemy import text

        # Only available for crypto symbols (Binance USDT perpetuals)
        if symbol not in CRYPTO_SYMBOLS:
            return None

        db = SessionLocal()
        try:
            # Query on-chain_signal_history table
            # We want: onchain_score, onchain_sentiment (as numeric), funding_rate, long_short_ratio, fear_greed
            query = f"""
                SELECT 
                    DATE(created_at) as date,
                    AVG(onchain_score) as onchain_score,
                    MAX(CASE 
                        WHEN onchain_sentiment = 'bullish' THEN 1
                        WHEN onchain_sentiment = 'bearish' THEN -1
                        ELSE 0 
                    END) as onchain_sentiment_numeric,
                    AVG(funding_rate) as funding_rate,
                    AVG(long_short_ratio) as long_short_ratio,
                    AVG(fear_greed) as fear_greed
                FROM onchain_signal_history
                WHERE symbol = :symbol
                  AND created_at >= NOW() - INTERVAL '{days} days'
                GROUP BY DATE(created_at)
                ORDER BY date ASC
            """
            
            result = db.execute(text(query), {"symbol": symbol}).mappings().all()
            
            if not result:
                return None
            
            # Convert to DataFrame
            records = [dict(r) for r in result]
            df = pd.DataFrame(records)
            df.set_index('date', inplace=True)
            df.index = pd.to_datetime(df.index)
            
            # Rename columns for clarity
            df = df.rename(columns={
                'onchain_score': 'onchain_score',
                'onchain_sentiment_numeric': 'onchain_sentiment',
                'funding_rate': 'funding_rate_pct',
                'long_short_ratio': 'ls_ratio',
                'fear_greed': 'fear_greed',
            })
            
            logger.info(f"[trainer] Fetched {len(df)} on-chain records for {symbol}")
            return df
        finally:
            db.close()
    except Exception as e:
        logger.warning(f"[trainer] Failed to fetch on-chain data for {symbol}: {e}")
        return None


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

    # Fetch daily OHLCV — Binance for crypto, yfinance for everything else
    df = None
    df_4h = None
    if symbol in YFINANCE_SYMBOL_MAP:
        df = fetch_yfinance_ohlcv(symbol, days=days)
        # No 4h data from yfinance (daily only)
    else:
        df = fetch_binance_ohlcv(symbol, interval="1d", days=days)
        # Also fetch 4h data for multi-timeframe features
        df_4h = fetch_binance_ohlcv(symbol, interval="4h", days=min(days, 180))

    if df is None or len(df) < 200:
        row_count = len(df) if df is not None else 0
        logger.warning(f"[trainer] Not enough data for {symbol}: {row_count} rows")
        return None

    # Fetch on-chain features (if available for crypto symbols)
    onchain_df = fetch_onchain_history(symbol, days=days)

    # Engineer features on daily
    feat = engineer_features(df, onchain_data=onchain_df)

    # Add 4h aggregated features if available
    if df_4h is not None and len(df_4h) > 50:
        feat = _add_multi_timeframe_features(feat, df_4h)

    if len(feat) < 100:
        logger.warning(f"[trainer] Not enough features rows for {symbol}: {len(feat)}")
        return None

    # Separate features and target
    exclude_cols = ["target", "label_threshold", "open", "high", "low", "close", "volume",
                    "quote_volume", "trades"]

    # 3-class threshold labels for classification sidecar:
    # -1 (down), 0 (sideways), 1 (up).
    future_return = (feat["target"] / feat["close"]) - 1
    feat["label_threshold"] = np.where(
        future_return > LABEL_THRESHOLD,
        1,
        np.where(future_return < -LABEL_THRESHOLD, -1, 0),
    )

    feature_cols = [c for c in feat.columns if c not in exclude_cols]
    X = feat[feature_cols].values
    y = feat["target"].values
    y_threshold = feat["label_threshold"].values

    # Train/test split (chronological, not random)
    split_idx = int(len(X) * 0.8)
    X_train, X_test = X[:split_idx], X[split_idx:]
    y_train, y_test = y[:split_idx], y[split_idx:]
    y_train_threshold = y_threshold[:split_idx]
    y_test_threshold = y_threshold[split_idx:]

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

    threshold_metrics = None
    threshold_model_filename = None

    # Train 3-class threshold sidecar model (keeps regression model untouched).
    try:
        logger.info(f"[TRAINER] Using threshold labels — 3-class model for {symbol}")
        y_train_encoded = (y_train_threshold + 1).astype(int)  # -1,0,1 -> 0,1,2
        y_test_encoded = (y_test_threshold + 1).astype(int)

        threshold_model = xgb.XGBClassifier(
            objective="multi:softprob",
            num_class=3,
            n_estimators=250,
            max_depth=5,
            learning_rate=0.05,
            subsample=0.85,
            colsample_bytree=0.85,
            random_state=42,
            n_jobs=-1,
            verbosity=0,
            eval_metric="mlogloss",
        )
        threshold_model.fit(
            X_train_scaled,
            y_train_encoded,
            eval_set=[(X_test_scaled, y_test_encoded)],
            verbose=False,
        )

        cls_pred_test = threshold_model.predict(X_test_scaled)
        cls_pred_labels = cls_pred_test.astype(int) - 1  # 0,1,2 -> -1,0,1
        threshold_acc = float((cls_pred_labels == y_test_threshold).mean() * 100)
        threshold_metrics = {
            "test_threshold_accuracy": threshold_acc,
            "class_distribution_train": {
                "down": int((y_train_threshold == -1).sum()),
                "sideways": int((y_train_threshold == 0).sum()),
                "up": int((y_train_threshold == 1).sum()),
            },
            "class_mapping": {"0": "DOWN", "1": "SIDEWAYS", "2": "UP"},
        }

        threshold_model_filename = f"{symbol}_xgboost_threshold_v{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.pkl"
        threshold_model_path = os.path.join(MODELS_DIR, threshold_model_filename)
        threshold_model_data = {
            "model": threshold_model,
            "scaler": scaler,
            "feature_cols": feature_cols,
            "symbol": symbol,
            "model_type": "xgboost_threshold_classifier",
            "label_col": "label_threshold",
            "threshold": LABEL_THRESHOLD,
            "trained_at": datetime.utcnow().isoformat(),
            "metrics": threshold_metrics,
        }

        with open(threshold_model_path, "wb") as f:
            pickle.dump(threshold_model_data, f)

        threshold_latest_path = os.path.join(MODELS_DIR, f"{symbol}_xgboost_threshold_latest.pkl")
        with open(threshold_latest_path, "wb") as f:
            pickle.dump(threshold_model_data, f)
    except Exception as threshold_err:
        logger.warning(
            "[TRAINER] Threshold 3-class training failed for %s, keeping legacy model only: %s",
            symbol,
            threshold_err,
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
        "threshold_model_path": threshold_model_filename,
        "metrics": metrics,
        "threshold_metrics": threshold_metrics,
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
    """Train models for all symbols (crypto + stocks + metals + forex). Returns list of results."""
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


def _daily_prediction_outcomes_eval():
    """Daily delayed evaluation of previously recorded predictions."""
    logger.info("[scheduler] Starting prediction outcomes evaluation...")
    try:
        from services.prediction_outcomes import prediction_outcomes_service
        res = prediction_outcomes_service.evaluate_predictions()
        logger.info(
            "[scheduler] Prediction outcomes eval done: 7d=%s 30d=%s",
            res.get("evaluated_7d", 0),
            res.get("evaluated_30d", 0),
        )
    except Exception as e:
        logger.error(f"[scheduler] Prediction outcomes eval failed: {e}")


def _weekly_retraining_with_feedback():
    """Weekly base retrain followed by feedback-layer refinement."""
    logger.info("[scheduler] Starting weekly base retrain + feedback refinement...")
    try:
        base_results = train_all_symbols()
        base_ok = len([r for r in base_results if "metrics" in r])
        logger.info(f"[scheduler] Weekly base retrain done: {base_ok}/{len(base_results)} succeeded")
    except Exception as e:
        logger.error(f"[scheduler] Weekly base retrain failed: {e}")
        return

    try:
        from services.model_improver import retrain_all_with_feedback

        feedback_results = retrain_all_with_feedback(TRAINING_SYMBOLS)
        improved = len([r for r in feedback_results if r.get("status") == "improved"])
        no_improvement = len([r for r in feedback_results if r.get("status") == "no_improvement"])
        logger.info(
            "[scheduler] Weekly feedback refinement done: improved=%s no_improvement=%s total=%s",
            improved,
            no_improvement,
            len(feedback_results),
        )
    except Exception as e:
        logger.error(f"[scheduler] Weekly feedback refinement failed: {e}")


def _weekly_lstm_retraining():
    """Weekly LSTM sidecar training for top-10 crypto symbols."""
    logger.info("[scheduler] Starting weekly LSTM sidecar retraining...")
    try:
        from ml.lstm_model import LSTM_SYMBOLS, train_lstm

        succeeded = 0
        for symbol in LSTM_SYMBOLS:
            try:
                ohlcv = fetch_ohlcv(symbol, days=365)
                result = train_lstm(symbol, ohlcv)
                if result is not None:
                    succeeded += 1
            except Exception as e:
                print(f"[LSTM] Failed {symbol}: {e}")
                continue

        logger.info("[scheduler] Weekly LSTM sidecar retraining done: %s/%s succeeded", succeeded, len(LSTM_SYMBOLS))
    except Exception as e:
        logger.error(f"[scheduler] Weekly LSTM sidecar retraining failed: {e}")


def _daily_morning_briefings():
    """Daily morning AI briefings push job (06:00 UTC / 08:00 EET)."""
    logger.info("[scheduler] Starting morning briefings push...")
    try:
        from services.morning_briefing import send_morning_briefings

        send_morning_briefings()
        logger.info("[scheduler] Morning briefings push done")
    except Exception as e:
        logger.error(f"[scheduler] Morning briefings push failed: {e}")


def _weekly_performance_reports():
    """Weekly performance reports push job (Mon 06:30 UTC / 08:30 EET)."""
    logger.info("[scheduler] Starting weekly performance reports push...")
    try:
        from services.weekly_report import send_weekly_reports

        send_weekly_reports()
        logger.info("[scheduler] Weekly performance reports push done")
    except Exception as e:
        logger.error(f"[scheduler] Weekly performance reports push failed: {e}")


def _weekly_report_generation():
    """Generate and persist weekly reports for every active user (Sun 23:00 UTC)."""
    logger.info("[scheduler] Starting weekly report generation...")
    try:
        from database.connection import SessionLocal
        from database.models import User
        from ai.weekly_report import generate_weekly_report

        if not SessionLocal:
            logger.warning("[scheduler] Weekly report generation skipped: DB unavailable")
            return

        db = SessionLocal()
        try:
            user_ids = [uid for (uid,) in db.query(User.id).filter(User.is_active.is_(True)).all()]
        finally:
            db.close()

        ok = 0
        for uid in user_ids:
            session = SessionLocal()
            try:
                generate_weekly_report(int(uid), session)
                ok += 1
            except Exception as e:
                logger.error(f"[scheduler] Weekly report failed for user {uid}: {e}")
                session.rollback()
            finally:
                session.close()
        logger.info(f"[scheduler] Weekly report generation done: {ok}/{len(user_ids)} users")
    except Exception as e:
        logger.error(f"[scheduler] Weekly report generation failed: {e}")


def _daily_leaderboard_snapshot():
    """Daily social leaderboard snapshot job (00:00 UTC)."""
    logger.info("[scheduler] Starting daily leaderboard snapshot...")
    try:
        from services.social_service import social_service

        result = social_service.update_leaderboard()
        logger.info("[scheduler] Daily leaderboard snapshot done: %s", result)
    except Exception as e:
        logger.error(f"[scheduler] Daily leaderboard snapshot failed: {e}")


def _fear_greed_update_job():
    """Daily Fear & Greed Index update job (00:30 UTC)."""
    logger.info("[scheduler] Starting Fear & Greed update...")
    try:
        import asyncio
        from scheduler.cron_tasks import task_fear_greed_update
        
        asyncio.run(task_fear_greed_update())
        logger.info("[scheduler] Fear & Greed update done")
    except Exception as e:
        logger.error(f"[scheduler] Fear & Greed update failed: {e}")


def _news_fetch_job():
    """Daily news sentiment fetch job (06:00 UTC)."""
    logger.info("[scheduler] Starting news sentiment fetch...")
    try:
        import asyncio
        from scheduler.cron_tasks import task_fetch_news
        
        asyncio.run(task_fetch_news())
        logger.info("[scheduler] News sentiment fetch done")
    except Exception as e:
        logger.error(f"[scheduler] News sentiment fetch failed: {e}")


def _monthly_rl_retrain_job():
    """Monthly RL agent retrain - runs on 1st of each month at 02:00 UTC."""
    import asyncio

    try:
        from scheduler.cron_tasks import task_monthly_rl_retrain

        asyncio.run(task_monthly_rl_retrain())
        print("[CRON] Monthly RL retrain completed")
    except Exception as e:
        print(f"[CRON] Monthly RL retrain failed: {e}")


def setup_weekly_retraining():
    """Schedule all recurring training and prediction jobs using APScheduler."""
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.triggers.cron import CronTrigger

        scheduler = BackgroundScheduler()

        # Weekly full retraining — Sunday 00:00 UTC
        scheduler.add_job(
            _weekly_retraining_with_feedback,
            trigger=CronTrigger(day_of_week="sun", hour=0, minute=0),
            id="weekly_retrain",
            name="Weekly model retraining + feedback refinement",
            replace_existing=True,
        )

        # Weekly LSTM sidecar retraining — Sunday 01:00 UTC
        scheduler.add_job(
            _weekly_lstm_retraining,
            trigger=CronTrigger(day_of_week="sun", hour=1, minute=0),
            id="weekly_lstm_retrain",
            name="Weekly LSTM sidecar retraining",
            replace_existing=True,
        )

        # Monthly RL retraining - first day of month at 02:00 UTC
        scheduler.add_job(
            _monthly_rl_retrain_job,
            trigger=CronTrigger(day=1, hour=2, minute=0),
            id="monthly_rl_retrain",
            name="Monthly RL agent retraining",
            replace_existing=True,
        )

        # Fear & Greed Index update — 00:30 UTC
        scheduler.add_job(
            _fear_greed_update_job,
            trigger=CronTrigger(hour=0, minute=30),
            id="fear_greed_update",
            name="Daily Fear & Greed Index update",
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

        # Daily news sentiment fetch — 06:00 UTC (09:00 Cyprus)
        scheduler.add_job(
            _news_fetch_job,
            trigger=CronTrigger(hour=6, minute=0),
            id="news_fetch",
            name="Daily news sentiment fetch",
            replace_existing=True,
        )

        # Morning AI briefing push — 06:00 UTC (08:00 EET)
        scheduler.add_job(
            _daily_morning_briefings,
            trigger=CronTrigger(hour=6, minute=0),
            id="daily_morning_briefings",
            name="Daily morning AI briefing push",
            replace_existing=True,
        )

        # Weekly performance report push — Monday 06:30 UTC (08:30 EET)
        scheduler.add_job(
            _weekly_performance_reports,
            trigger=CronTrigger(day_of_week="mon", hour=6, minute=30),
            id="weekly_performance_reports",
            name="Weekly performance reports push",
            replace_existing=True,
        )

        # Weekly report generation (DB snapshot per user) — Sunday 23:00 UTC
        scheduler.add_job(
            _weekly_report_generation,
            trigger=CronTrigger(day_of_week="sun", hour=23, minute=0),
            id="weekly_report_generation",
            name="Weekly report generation (DB snapshot)",
            replace_existing=True,
        )

        # Daily leaderboard snapshots — 00:00 UTC
        scheduler.add_job(
            _daily_leaderboard_snapshot,
            trigger=CronTrigger(hour=0, minute=0),
            id="daily_leaderboard_snapshot",
            name="Daily leaderboard snapshots",
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

        # Daily prediction outcomes evaluation — 06:10 UTC
        scheduler.add_job(
            _daily_prediction_outcomes_eval,
            trigger=CronTrigger(hour=6, minute=10),
            id="daily_prediction_outcomes_eval",
            name="Daily prediction outcomes evaluation",
            replace_existing=True,
        )

        # Sentiment fetch — every 30 minutes (gated behind ENABLE_SENTIMENT_DATA flag)
        def _sentiment_fetch_job():
            try:
                from services.sentiment_scheduler import fetch_and_persist_sentiment
                fetch_and_persist_sentiment()
            except Exception as e:
                logger.error(f"[scheduler] Sentiment fetch failed: {e}")

        scheduler.add_job(
            _sentiment_fetch_job,
            trigger=CronTrigger(minute="*/30"),
            id="sentiment_fetch",
            name="Sentiment data fetch (every 30min)",
            replace_existing=True,
        )

        scheduler.start()
        logger.info("[trainer] Scheduled jobs: fear_greed (daily 00:30), news_fetch (daily 06:00), weekly retrain (Sun 00:00), weekly LSTM (Sun 01:00), monthly RL retrain (day 1 @ 02:00), daily leaderboard (00:00), daily XGBoost (06:00), morning briefing push (06:00), weekly report generation (Sun 23:00), weekly report push (Mon 06:30), daily predictions (06:05), prediction outcomes eval (06:10), sentiment (*/30min)")
        return scheduler
    except ImportError:
        logger.warning("[trainer] APScheduler not installed, scheduled jobs disabled")
        return None
    except Exception as e:
        logger.error(f"[trainer] Failed to setup scheduler: {e}")
        return None
