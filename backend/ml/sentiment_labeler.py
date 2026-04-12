"""
Phase 2: Sentiment Labeling
Analyzes financial news headlines using VADER + financial keyword dictionary,
with TextBlob kept as fallback for compatibility.
Updates sentiment_score and sentiment_label in financial_news table.
"""

import os
import sys
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# Financial-domain keyword boosts
BULLISH_KEYWORDS = [
    "surge", "rally", "breakout", "bullish", "buy", "upgrade", "beat",
    "record", "growth", "adoption", "approval", "launch", "partnership",
    "outperform", "strong", "positive", "recovery", "all-time high",
    "accumulate", "undervalued", "moon", "pump", "gains", "profit",
    "institutional",
]

BEARISH_KEYWORDS = [
    "crash", "dump", "bearish", "sell", "downgrade", "miss", "hack",
    "ban", "regulation", "lawsuit", "bubble", "collapse", "fraud",
    "liquidation", "fear", "panic", "loss", "decline", "warning",
    "overvalued", "short", "plunge", "drop", "risk", "concern",
]

# Category-to-symbol mapping for news that doesn't mention specific tickers
CATEGORY_MAP = {
    "fed": ["^TNX", "^IRX", "^TYX", "EURUSD=X", "GC=F", "ES=F"],
    "interest rate": ["^TNX", "^IRX", "^TYX", "EURUSD=X"],
    "opec": ["CL=F"],
    "oil": ["CL=F", "XOM", "CVX"],
    "gold": ["GC=F", "SI=F"],
    "bitcoin": ["BTC-USD", "ETH-USD"],
    "crypto": ["BTC-USD", "ETH-USD", "BNB-USD", "SOL-USD"],
    "tech": ["AAPL", "MSFT", "NVDA", "GOOGL", "META"],
    "semiconductor": ["NVDA", "ASML"],
    "ai": ["NVDA", "MSFT", "GOOGL"],
    "china": ["BNB-USD", "NIO"],
    "europe": ["ASML", "SAP", "MC.PA", "EURUSD=X"],
    "treasury": ["^TNX", "^IRX", "^TYX"],
    "vix": ["^VIX"],
}


try:
    from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
    _vader = SentimentIntensityAnalyzer()
except Exception:
    _vader = None


def analyze_sentiment_vader(text: str, keywords: Optional[List[str]] = None) -> float:
    """Returns sentiment score -1.0 to +1.0 using VADER + keyword boost."""
    if not text:
        return 0.0

    if _vader is None:
        raise RuntimeError("VADER is not available")

    score = float(_vader.polarity_scores(text).get("compound", 0.0))

    text_lower = text.lower()
    keyword_boost = 0.0
    for kw in BULLISH_KEYWORDS:
        if kw in text_lower:
            keyword_boost += 0.10
    for kw in BEARISH_KEYWORDS:
        if kw in text_lower:
            keyword_boost -= 0.10

    return max(-1.0, min(1.0, score + keyword_boost))


def _analyze_sentiment_textblob(text: str) -> float:
    """TextBlob fallback sentiment scoring."""
    from textblob import TextBlob

    if not text:
        return 0.0

    text_lower = text.lower()
    blob = TextBlob(text)
    base_score = float(blob.sentiment.polarity)
    bullish_hits = sum(1 for kw in BULLISH_KEYWORDS if kw in text_lower)
    bearish_hits = sum(1 for kw in BEARISH_KEYWORDS if kw in text_lower)
    keyword_boost = (bullish_hits - bearish_hits) * 0.15
    return max(-1.0, min(1.0, base_score + keyword_boost))


def analyze_sentiment(text: str) -> tuple:
    """
    Analyze sentiment of financial text.
    Returns (score: -1.0 to 1.0, label: str).
    Uses VADER + financial keyword boosting with TextBlob fallback.
    """
    if not text:
        return 0.0, "neutral"

    try:
        score = analyze_sentiment_vader(text)
        logger.info("[VADER] score=%.4f", score)
    except Exception as e:
        logger.warning("[VADER] failed, falling back to TextBlob: %s", e)
        score = _analyze_sentiment_textblob(text)
        logger.info("[TEXTBLOB] score=%.4f", score)

    # Label
    if score >= 0.1:
        label = "positive"
    elif score <= -0.1:
        label = "negative"
    else:
        label = "neutral"

    return round(score, 4), label


def store_sentiment_snapshot(redis_client, symbol: str, score: float):
    """Store hourly sentiment snapshot for momentum calculation using sync Redis client."""
    if redis_client is None or not symbol:
        return

    key = f"sentiment_history:{symbol.upper()}"
    snapshot = {"score": float(score), "ts": datetime.utcnow().isoformat()}

    redis_client.lpush(key, json.dumps(snapshot))
    redis_client.ltrim(key, 0, 23)
    redis_client.expire(key, 86400)


def get_sentiment_momentum(redis_client, symbol: str) -> dict:
    """
    Returns sentiment momentum for a symbol.
    momentum > 0 = bullish acceleration
    momentum < 0 = bearish acceleration
    """
    if redis_client is None or not symbol:
        return {"momentum": 0.0, "trend": "neutral", "snapshots": 0}

    key = f"sentiment_history:{symbol.upper()}"
    raw = redis_client.lrange(key, 0, -1)
    if len(raw) < 2:
        return {"momentum": 0.0, "trend": "neutral", "snapshots": len(raw)}

    snapshots = []
    for item in raw:
        try:
            if isinstance(item, bytes):
                item = item.decode("utf-8")
            snapshots.append(json.loads(item))
        except Exception:
            continue

    if len(snapshots) < 2:
        return {"momentum": 0.0, "trend": "neutral", "snapshots": len(snapshots)}

    scores = [float(s.get("score", 0.0)) for s in snapshots]
    recent_window = min(4, len(scores))
    recent = sum(scores[:recent_window]) / max(1, recent_window)
    older = sum(scores[recent_window:]) / max(1, len(scores) - recent_window)
    momentum = recent - older

    trend = "bullish" if momentum > 0.1 else "bearish" if momentum < -0.1 else "neutral"
    return {"momentum": round(momentum, 3), "trend": trend, "snapshots": len(snapshots)}


def map_news_to_symbols(headline: str, summary: str = "") -> str:
    """Map a news headline to related asset symbols."""
    text = f"{headline} {summary}".lower()
    matched = set()

    # Direct ticker mentions
    from scripts.collect_training_data import ASSETS
    for asset_type, symbols in ASSETS.items():
        for symbol in symbols:
            clean = symbol.replace("-USD", "").replace("=F", "").replace("=X", "").replace("^", "").lower()
            if clean in text:
                matched.add(symbol)

    # Category mapping
    for keyword, symbols in CATEGORY_MAP.items():
        if keyword in text:
            matched.update(symbols)

    return ",".join(matched) if matched else ""


def label_all_news(job_id: str = "manual"):
    """Process all unlabeled news in financial_news table."""
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from database.connection import SessionLocal
    from database.models import FinancialNews, TrainingLog

    db = SessionLocal()

    try:
        # Get unlabeled news
        unlabeled = db.query(FinancialNews).filter(
            FinancialNews.sentiment_score.is_(None)
        ).all()

        total = len(unlabeled)
        logger.info(f"[Phase2] {total} unlabeled headlines to process")

        db.add(TrainingLog(
            job_id=job_id, phase="label_sentiment",
            status="running", message=f"Processing {total} headlines", progress=0
        ))
        db.commit()

        from cache.connection import get_redis
        redis_client = get_redis()

        for i, news in enumerate(unlabeled):
            text = f"{news.headline} {news.summary or ''}"
            score, label = analyze_sentiment(text)
            news.sentiment_score = score
            news.sentiment_label = label

            # Map to symbols if not already set
            if not news.symbols:
                news.symbols = map_news_to_symbols(news.headline, news.summary or "")

            # Store sentiment momentum snapshots per mapped symbol
            if news.symbols:
                for sym in [s.strip() for s in news.symbols.split(",") if s.strip()]:
                    try:
                        store_sentiment_snapshot(redis_client, sym, score)
                    except Exception as snap_err:
                        logger.debug("[sentiment] snapshot store failed for %s: %s", sym, snap_err)

            if (i + 1) % 100 == 0:
                db.commit()
                progress = (i + 1) / total * 100
                db.add(TrainingLog(
                    job_id=job_id, phase="label_sentiment",
                    status="running", message=f"Processed {i+1}/{total}", progress=progress
                ))
                db.commit()

        db.commit()

        db.add(TrainingLog(
            job_id=job_id, phase="label_sentiment",
            status="completed", message=f"Labeled {total} headlines", progress=100,
            completed_at=datetime.utcnow()
        ))
        db.commit()
        logger.info(f"[Phase2] Sentiment labeling complete: {total} headlines")

    except Exception as e:
        db.add(TrainingLog(
            job_id=job_id, phase="label_sentiment",
            status="failed", message=str(e), completed_at=datetime.utcnow()
        ))
        db.commit()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    label_all_news()
