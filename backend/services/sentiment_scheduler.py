"""
Sentiment Data Layer — Scheduled news fetch + DB persistence.
Gated behind ENABLE_SENTIMENT_DATA flag.

Fetches news from existing news_fetcher, scores via VADER,
persists to financial_news table, caches in Redis.
"""

import logging
import traceback
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# Symbols to track — matches the existing ALL_SYMBOLS from rl_trader
SENTIMENT_SYMBOLS = [
    "BTCUSDC", "ETHUSDC", "BNBUSDC", "XRPUSDC", "SOLUSDC",
    "ADAUSDC", "AVAXUSDC", "DOTUSDC", "LINKUSDC",
]


def fetch_and_persist_sentiment():
    """
    Fetch news for all tracked symbols, score with VADER,
    persist to DB, cache in Redis. Called by scheduler.
    """
    from config.feature_flags import ENABLE_SENTIMENT_DATA
    if not ENABLE_SENTIMENT_DATA:
        logger.debug("[sentiment] ENABLE_SENTIMENT_DATA is False, skipping")
        return

    logger.info("[sentiment] Starting scheduled sentiment fetch...")

    from services.news_fetcher import news_fetcher
    from cache.connection import cache_set

    results = {}
    for symbol in SENTIMENT_SYMBOLS:
        try:
            sentiment = news_fetcher.get_symbol_sentiment(symbol)
            results[symbol] = sentiment

            # Cache in Redis with 20-min TTL
            cache_set(f"sentiment:{symbol}", sentiment, expire=1200)

        except Exception as e:
            logger.error(f"[sentiment] Failed for {symbol}: {e}")
            results[symbol] = {"score": 50.0, "label": "neutral", "error": str(e)}

    # Persist aggregated snapshot to DB
    _persist_to_db(results)

    succeeded = len([v for v in results.values() if "error" not in v])
    logger.info(f"[sentiment] Fetch complete: {succeeded}/{len(SENTIMENT_SYMBOLS)} symbols scored")
    return results


def _persist_to_db(results: dict):
    """Save sentiment results as FinancialNews rows."""
    try:
        from database.connection import SessionLocal
        from database.models import FinancialNews

        db = SessionLocal()
        if not db:
            return

        try:
            for symbol, data in results.items():
                if "error" in data:
                    continue

                article_count = data.get("article_count", 0)
                if article_count == 0:
                    continue

                # One aggregated row per symbol per fetch cycle
                db.add(FinancialNews(
                    headline=f"[AURA Sentiment] {symbol}: {data.get('label', 'neutral')}",
                    summary=f"Score: {data.get('score', 50)}/100, "
                            f"VADER: {data.get('vader_avg', 0)}, "
                            f"Articles: {article_count}",
                    source="aura_sentiment_aggregator",
                    symbols=symbol,
                    published_at=datetime.utcnow(),
                    sentiment_score=data.get("score", 50.0),
                    sentiment_label=data.get("label", "neutral"),
                ))

            db.commit()
        finally:
            db.close()

    except Exception as e:
        logger.error(f"[sentiment] DB persist failed: {e}")
        traceback.print_exc()


def get_cached_sentiment(symbol: str) -> dict:
    """Get cached sentiment for a symbol. Returns neutral if not cached."""
    from cache.connection import cache_get

    cached = cache_get(f"sentiment:{symbol}")
    if cached and isinstance(cached, dict):
        return cached

    # Fallback: try live fetch (but don't block)
    try:
        from services.news_fetcher import news_fetcher
        return news_fetcher.get_symbol_sentiment(symbol)
    except Exception:
        return {"score": 50.0, "label": "neutral", "symbol": symbol, "article_count": 0}


def get_all_sentiment() -> dict:
    """Get cached sentiment for all tracked symbols."""
    results = {}
    for symbol in SENTIMENT_SYMBOLS:
        results[symbol] = get_cached_sentiment(symbol)
    return results
