"""
Phase 3: Feature Engineering
Combines price features, sentiment features, cross-asset features,
and macro features into training-ready feature vectors.
"""

import os
import sys
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def compute_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0).rolling(period).mean()
    loss = (-delta.where(delta < 0, 0.0)).rolling(period).mean()
    rs = gain / loss.replace(0, np.inf)
    return 100 - (100 / (1 + rs))


def compute_macd(series: pd.Series) -> pd.Series:
    ema12 = series.ewm(span=12, adjust=False).mean()
    ema26 = series.ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    signal = macd.ewm(span=9, adjust=False).mean()
    return macd - signal  # histogram


def compute_bollinger_position(series: pd.Series, period: int = 20) -> pd.Series:
    mid = series.rolling(period).mean()
    std = series.rolling(period).std()
    upper = mid + 2 * std
    lower = mid - 2 * std
    return (series - lower) / (upper - lower)


def build_price_features(df: pd.DataFrame) -> Dict[str, float]:
    """Build price-based features from OHLCV DataFrame (expects date-sorted)."""
    if len(df) < 65:
        return {}

    close = df["close"]
    high = df["high"]
    low = df["low"]
    volume = df["volume"]
    last = len(df) - 1

    features = {}

    # Returns
    features["return_1d"] = float(close.pct_change(1).iloc[last])
    features["return_5d"] = float(close.pct_change(5).iloc[last])
    features["return_20d"] = float(close.pct_change(20).iloc[last])

    # Moving average ratios
    for w in [5, 20, 60]:
        sma = close.rolling(w).mean()
        if not pd.isna(sma.iloc[last]) and sma.iloc[last] != 0:
            features[f"price_sma{w}_ratio"] = float(close.iloc[last] / sma.iloc[last])

    # RSI
    rsi = compute_rsi(close, 14)
    features["rsi_14"] = float(rsi.iloc[last]) if not pd.isna(rsi.iloc[last]) else 50.0

    # MACD histogram
    macd_hist = compute_macd(close)
    features["macd_histogram"] = float(macd_hist.iloc[last]) if not pd.isna(macd_hist.iloc[last]) else 0.0

    # Bollinger Band position
    bb_pos = compute_bollinger_position(close)
    features["bb_position"] = float(bb_pos.iloc[last]) if not pd.isna(bb_pos.iloc[last]) else 0.5

    # Volume change
    vol_sma = volume.rolling(20).mean()
    if not pd.isna(vol_sma.iloc[last]) and vol_sma.iloc[last] > 0:
        features["volume_ratio"] = float(volume.iloc[last] / vol_sma.iloc[last])
    else:
        features["volume_ratio"] = 1.0

    # High-Low range
    if close.iloc[last] > 0:
        features["hl_range_pct"] = float((high.iloc[last] - low.iloc[last]) / close.iloc[last])
    else:
        features["hl_range_pct"] = 0.0

    # Volatility (20-day)
    features["volatility_20d"] = float(close.pct_change().rolling(20).std().iloc[last])

    return features


def build_sentiment_features(db_session, symbol: str, target_date, lookback_days: int = 5) -> Dict[str, float]:
    """Build sentiment features from financial_news table."""
    from database.models import FinancialNews

    features = {"sentiment_daily": 0.0, "sentiment_3d": 0.0, "sentiment_count": 0.0, "sentiment_momentum": 0.0}

    try:
        start_date = target_date - timedelta(days=lookback_days)

        # Get news mentioning this symbol in the lookback period
        news = db_session.query(FinancialNews).filter(
            FinancialNews.published_at >= start_date,
            FinancialNews.published_at <= target_date,
            FinancialNews.sentiment_score.isnot(None),
            FinancialNews.symbols.contains(symbol),
        ).all()

        if not news:
            return features

        # Daily sentiment (today)
        today_news = [n for n in news if n.published_at.date() == target_date.date()]
        if today_news:
            features["sentiment_daily"] = np.mean([n.sentiment_score for n in today_news])

        # 3-day rolling
        three_day = target_date - timedelta(days=3)
        recent_news = [n for n in news if n.published_at >= three_day]
        if recent_news:
            features["sentiment_3d"] = np.mean([n.sentiment_score for n in recent_news])

        # Article count
        features["sentiment_count"] = float(len(today_news))

        # Sentiment momentum (today vs 5-day avg)
        all_scores = [n.sentiment_score for n in news]
        avg_5d = np.mean(all_scores)
        if today_news:
            features["sentiment_momentum"] = features["sentiment_daily"] - avg_5d

    except Exception as e:
        logger.debug(f"Sentiment features error for {symbol}: {e}")

    return features


def build_cross_asset_features(db_session, target_date) -> Dict[str, float]:
    """Build cross-asset correlation features."""
    from database.models import HistoricalPrice

    features = {}

    # VIX level
    vix = db_session.query(HistoricalPrice).filter(
        HistoricalPrice.symbol == "^VIX",
        HistoricalPrice.date <= target_date
    ).order_by(HistoricalPrice.date.desc()).first()
    features["vix_level"] = float(vix.close) if vix else 20.0

    # 10Y yield
    tnx = db_session.query(HistoricalPrice).filter(
        HistoricalPrice.symbol == "^TNX",
        HistoricalPrice.date <= target_date
    ).order_by(HistoricalPrice.date.desc()).first()
    features["treasury_10y"] = float(tnx.close) if tnx else 4.0

    # 3M yield
    irx = db_session.query(HistoricalPrice).filter(
        HistoricalPrice.symbol == "^IRX",
        HistoricalPrice.date <= target_date
    ).order_by(HistoricalPrice.date.desc()).first()
    features["treasury_3m"] = float(irx.close) if irx else 5.0

    # Yield curve (10Y - 3M)
    features["yield_curve"] = features["treasury_10y"] - features["treasury_3m"]

    # DXY proxy (inverse of EURUSD)
    eur = db_session.query(HistoricalPrice).filter(
        HistoricalPrice.symbol == "EURUSD=X",
        HistoricalPrice.date <= target_date
    ).order_by(HistoricalPrice.date.desc()).first()
    features["dxy_proxy"] = float(1 / eur.close) if eur and eur.close > 0 else 1.0

    return features


def engineer_features_for_symbol(db_session, symbol: str, job_id: str = "manual"):
    """Engineer features for a single symbol across all available dates."""
    from database.models import HistoricalPrice, TrainingFeature

    # Load all price data for this symbol
    prices = db_session.query(HistoricalPrice).filter(
        HistoricalPrice.symbol == symbol
    ).order_by(HistoricalPrice.date).all()

    if len(prices) < 65:
        logger.warning(f"[Phase3] {symbol}: only {len(prices)} rows, need 65+")
        return 0

    # Convert to DataFrame
    df = pd.DataFrame([{
        "date": p.date, "open": p.open, "high": p.high,
        "low": p.low, "close": p.close, "volume": p.volume
    } for p in prices])
    df = df.set_index("date").sort_index()

    count = 0
    dates = df.index[64:]  # start after 60-day lookback window

    for i, target_date in enumerate(dates):
        # Slice data up to target_date
        window = df.loc[:target_date]

        # Price features
        price_feats = build_price_features(window)
        if not price_feats:
            continue

        # Sentiment features
        sent_feats = build_sentiment_features(db_session, symbol, datetime.combine(target_date, datetime.min.time()))

        # Cross-asset features
        cross_feats = build_cross_asset_features(db_session, target_date)

        # Combine all features
        all_features = {**price_feats, **sent_feats, **cross_feats}

        # Target: next day's return
        next_idx = list(df.index).index(target_date)
        if next_idx + 1 >= len(df):
            continue
        next_close = df.iloc[next_idx + 1]["close"]
        curr_close = df.iloc[next_idx]["close"]
        if curr_close == 0:
            continue

        target_return = (next_close - curr_close) / curr_close
        target_direction = "up" if target_return > 0 else "down"

        # Upsert
        existing = db_session.query(TrainingFeature).filter(
            TrainingFeature.symbol == symbol,
            TrainingFeature.date == target_date
        ).first()

        if existing:
            existing.features = all_features
            existing.target_return = float(target_return)
            existing.target_direction = target_direction
        else:
            db_session.add(TrainingFeature(
                symbol=symbol,
                date=target_date,
                features=all_features,
                target_return=float(target_return),
                target_direction=target_direction,
            ))

        count += 1
        if count % 200 == 0:
            db_session.commit()

    db_session.commit()
    return count


def engineer_all_features(job_id: str = "manual"):
    """Run feature engineering for all symbols."""
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from database.connection import SessionLocal
    from database.models import HistoricalPrice, TrainingLog

    db = SessionLocal()

    try:
        # Get all unique symbols
        symbols = [r[0] for r in db.query(HistoricalPrice.symbol).distinct().all()]
        total = len(symbols)

        db.add(TrainingLog(
            job_id=job_id, phase="feature_engineering",
            status="running", message=f"Engineering features for {total} symbols", progress=0
        ))
        db.commit()

        total_features = 0
        for i, symbol in enumerate(symbols):
            count = engineer_features_for_symbol(db, symbol, job_id)
            total_features += count
            progress = (i + 1) / total * 100
            logger.info(f"[Phase3] {symbol}: {count} feature rows ({i+1}/{total})")

            if (i + 1) % 5 == 0:
                db.add(TrainingLog(
                    job_id=job_id, phase="feature_engineering",
                    status="running", message=f"Processed {i+1}/{total} symbols ({total_features} rows)",
                    progress=progress
                ))
                db.commit()

        db.add(TrainingLog(
            job_id=job_id, phase="feature_engineering",
            status="completed", message=f"Engineered {total_features} feature rows for {total} symbols",
            progress=100, completed_at=datetime.utcnow()
        ))
        db.commit()
        logger.info(f"[Phase3] Complete: {total_features} feature rows for {total} symbols")

    except Exception as e:
        db.add(TrainingLog(
            job_id=job_id, phase="feature_engineering",
            status="failed", message=str(e), completed_at=datetime.utcnow()
        ))
        db.commit()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    engineer_all_features()
