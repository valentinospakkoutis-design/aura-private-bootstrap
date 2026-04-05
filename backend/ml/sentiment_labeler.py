"""
Phase 2: Sentiment Labeling
Analyzes financial news headlines using TextBlob + financial keyword dictionary.
Updates sentiment_score and sentiment_label in financial_news table.
"""

import os
import sys
import logging
from datetime import datetime
from typing import Dict, List

logger = logging.getLogger(__name__)

# Financial-domain keyword boosts
BEARISH_KEYWORDS = [
    "crash", "recession", "rate hike", "inflation", "sell-off", "bankruptcy",
    "layoffs", "sanctions", "war", "crisis", "downgrade", "default", "plunge",
    "decline", "bear market", "correction", "warning", "tariff", "debt ceiling",
    "shutdown", "panic", "dump", "liquidation", "loss", "miss", "weak",
]

BULLISH_KEYWORDS = [
    "rally", "surge", "earnings beat", "rate cut", "acquisition", "partnership",
    "record high", "growth", "recovery", "stimulus", "upgrade", "breakout",
    "bull market", "all-time high", "ipo", "expansion", "profit", "beat",
    "strong", "momentum", "buy", "outperform", "dividend", "innovation",
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


def analyze_sentiment(text: str) -> tuple:
    """
    Analyze sentiment of financial text.
    Returns (score: -1.0 to 1.0, label: str).
    Uses TextBlob + financial keyword boosting.
    """
    from textblob import TextBlob

    if not text:
        return 0.0, "neutral"

    text_lower = text.lower()

    # Base sentiment from TextBlob
    blob = TextBlob(text)
    base_score = blob.sentiment.polarity  # -1.0 to 1.0

    # Financial keyword boost
    bullish_hits = sum(1 for kw in BULLISH_KEYWORDS if kw in text_lower)
    bearish_hits = sum(1 for kw in BEARISH_KEYWORDS if kw in text_lower)
    keyword_boost = (bullish_hits - bearish_hits) * 0.15

    # Combined score
    score = max(-1.0, min(1.0, base_score + keyword_boost))

    # Label
    if score >= 0.1:
        label = "positive"
    elif score <= -0.1:
        label = "negative"
    else:
        label = "neutral"

    return round(score, 4), label


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

        for i, news in enumerate(unlabeled):
            text = f"{news.headline} {news.summary or ''}"
            score, label = analyze_sentiment(text)
            news.sentiment_score = score
            news.sentiment_label = label

            # Map to symbols if not already set
            if not news.symbols:
                news.symbols = map_news_to_symbols(news.headline, news.summary or "")

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
