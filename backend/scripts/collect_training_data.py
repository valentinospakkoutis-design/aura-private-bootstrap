"""
Phase 1: Data Collection
Downloads 3 years of OHLCV data + financial news headlines.
Stores everything in PostgreSQL.
"""

import os
import sys
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional

import yfinance as yf
import feedparser
import httpx

logger = logging.getLogger(__name__)

# All assets to collect
ASSETS = {
    "crypto": ["BTC-USD", "ETH-USD", "BNB-USD", "XRP-USD", "SOL-USD", "ADA-USD", "AVAX-USD", "DOT-USD", "LINK-USD"],
    "metals": ["GC=F", "SI=F", "PL=F", "PA=F"],
    "stocks": ["AAPL", "MSFT", "NVDA", "ASML", "SAP", "MC.PA", "BOC.AT", "TSLA", "META", "GOOGL", "AMZN"],
    "bonds": ["^TNX", "^IRX", "^TYX"],
    "fx": ["EURUSD=X", "GBPEUR=X", "USDJPY=X"],
    "futures": ["ES=F", "NQ=F", "CL=F"],
    "sentiment": ["^VIX"],
}

RSS_FEEDS = [
    ("Reuters Business", "https://feeds.reuters.com/reuters/businessNews"),
    ("ECB", "https://www.ecb.europa.eu/rss/fxref-usd.html"),
]


def collect_ohlcv(db_session, log_fn=None):
    """Download 3 years of OHLCV for all assets, store in historical_prices."""
    from database.models import HistoricalPrice

    total = sum(len(v) for v in ASSETS.values())
    done = 0

    for asset_type, symbols in ASSETS.items():
        for symbol in symbols:
            done += 1
            if log_fn:
                log_fn(f"Fetching {symbol} ({done}/{total})", done / total * 50)

            try:
                ticker = yf.Ticker(symbol)
                hist = ticker.history(period="3y", interval="1d")

                if hist.empty:
                    logger.warning(f"No data for {symbol}")
                    continue

                rows = []
                for idx, row in hist.iterrows():
                    rows.append(HistoricalPrice(
                        symbol=symbol,
                        asset_type=asset_type,
                        date=idx.date(),
                        open=float(row["Open"]),
                        high=float(row["High"]),
                        low=float(row["Low"]),
                        close=float(row["Close"]),
                        volume=float(row.get("Volume", 0)),
                    ))

                # Bulk upsert: delete existing + insert
                db_session.query(HistoricalPrice).filter(
                    HistoricalPrice.symbol == symbol
                ).delete()
                db_session.bulk_save_objects(rows)
                db_session.commit()
                logger.info(f"[collect] {symbol}: {len(rows)} rows saved")

            except Exception as e:
                logger.error(f"[collect] {symbol} failed: {e}")
                db_session.rollback()


def collect_news(db_session, log_fn=None):
    """Collect financial news from yfinance ticker.news + RSS feeds."""
    from database.models import FinancialNews

    if log_fn:
        log_fn("Collecting news from yfinance tickers...", 55)

    # 1) yfinance ticker news (recent articles)
    news_symbols = ["AAPL", "MSFT", "NVDA", "BTC-USD", "ETH-USD", "GC=F", "^VIX"]
    for symbol in news_symbols:
        try:
            ticker = yf.Ticker(symbol)
            news_items = getattr(ticker, "news", None)
            if not news_items:
                continue

            for item in news_items[:20]:
                headline = item.get("title", "")
                if not headline:
                    continue

                pub_ts = item.get("providerPublishTime", 0)
                pub_dt = datetime.fromtimestamp(pub_ts) if pub_ts else datetime.utcnow()

                exists = db_session.query(FinancialNews).filter(
                    FinancialNews.headline == headline
                ).first()
                if exists:
                    continue

                db_session.add(FinancialNews(
                    headline=headline,
                    summary=item.get("summary", ""),
                    source=item.get("publisher", "Yahoo Finance"),
                    url=item.get("link", ""),
                    published_at=pub_dt,
                    symbols=symbol,
                ))
            db_session.commit()
        except Exception as e:
            logger.debug(f"[news] yfinance news for {symbol}: {e}")
            db_session.rollback()

    # 2) RSS feeds
    if log_fn:
        log_fn("Collecting news from RSS feeds...", 70)

    for feed_name, feed_url in RSS_FEEDS:
        try:
            with httpx.Client(timeout=15.0) as client:
                resp = client.get(feed_url, headers={"User-Agent": "AURA/1.0"})
                feed = feedparser.parse(resp.text)

            for entry in feed.entries[:30]:
                headline = entry.get("title", "")
                if not headline:
                    continue

                import re
                summary = re.sub(r"<[^>]+>", "", entry.get("summary", ""))[:500]
                pub = entry.get("published_parsed")
                pub_dt = datetime(*pub[:6]) if pub else datetime.utcnow()

                exists = db_session.query(FinancialNews).filter(
                    FinancialNews.headline == headline
                ).first()
                if exists:
                    continue

                db_session.add(FinancialNews(
                    headline=headline,
                    summary=summary,
                    source=feed_name,
                    url=entry.get("link", ""),
                    published_at=pub_dt,
                    symbols="",
                ))
            db_session.commit()
        except Exception as e:
            logger.debug(f"[news] RSS {feed_name}: {e}")
            db_session.rollback()

    # 3) NewsAPI (optional, requires API key)
    news_api_key = os.getenv("NEWS_API_KEY")
    if news_api_key:
        if log_fn:
            log_fn("Collecting from NewsAPI...", 80)
        try:
            with httpx.Client(timeout=15.0) as client:
                resp = client.get(
                    "https://newsapi.org/v2/top-headlines",
                    params={"category": "business", "language": "en", "pageSize": 50, "apiKey": news_api_key}
                )
                data = resp.json()

            for article in data.get("articles", []):
                headline = article.get("title", "")
                if not headline:
                    continue

                exists = db_session.query(FinancialNews).filter(
                    FinancialNews.headline == headline
                ).first()
                if exists:
                    continue

                pub_str = article.get("publishedAt", "")
                try:
                    pub_dt = datetime.fromisoformat(pub_str.replace("Z", "+00:00"))
                except Exception:
                    pub_dt = datetime.utcnow()

                db_session.add(FinancialNews(
                    headline=headline,
                    summary=article.get("description", ""),
                    source=article.get("source", {}).get("name", "NewsAPI"),
                    url=article.get("url", ""),
                    published_at=pub_dt,
                    symbols="",
                ))
            db_session.commit()
        except Exception as e:
            logger.debug(f"[news] NewsAPI: {e}")
            db_session.rollback()

    if log_fn:
        log_fn("Data collection complete", 100)


def run_collection(job_id: str = "manual"):
    """Run full data collection pipeline."""
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from database.connection import SessionLocal
    from database.models import TrainingLog

    db = SessionLocal()

    def log_fn(msg, progress=0):
        try:
            db.add(TrainingLog(
                job_id=job_id, phase="collect_data",
                status="running", message=msg, progress=progress
            ))
            db.commit()
        except Exception:
            db.rollback()
        logger.info(f"[Phase1] {msg} ({progress:.0f}%)")

    try:
        log_fn("Starting OHLCV collection...", 0)
        collect_ohlcv(db, log_fn)
        log_fn("Starting news collection...", 50)
        collect_news(db, log_fn)

        db.add(TrainingLog(
            job_id=job_id, phase="collect_data",
            status="completed", message="Data collection complete", progress=100,
            completed_at=datetime.utcnow()
        ))
        db.commit()
    except Exception as e:
        db.add(TrainingLog(
            job_id=job_id, phase="collect_data",
            status="failed", message=str(e), completed_at=datetime.utcnow()
        ))
        db.commit()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_collection()
