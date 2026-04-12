"""
Real News Intelligence for AURA
Fetches from 3 free sources, runs VADER sentiment analysis,
produces per-symbol sentiment scores updated every 15 minutes.
"""

import logging
import time
import re
import asyncio
from typing import Dict, List, Optional
from datetime import datetime

import httpx

from ml.news_fetcher import fetch_cryptopanic_news

logger = logging.getLogger(__name__)

# Base symbols for news matching
CRYPTO_NAMES = {
    "BTC": ["bitcoin", "btc"],
    "ETH": ["ethereum", "eth", "ether"],
    "BNB": ["binance coin", "bnb"],
    "ADA": ["cardano", "ada"],
    "SOL": ["solana", "sol"],
    "XRP": ["ripple", "xrp"],
    "DOT": ["polkadot", "dot"],
    "POL": ["polygon", "pol", "matic"],
    "LINK": ["chainlink", "link"],
    "AVAX": ["avalanche", "avax"],
    "SHIB": ["shiba", "shib"],
    "DOGE": ["dogecoin", "doge"],
    "TRX": ["tron", "trx"],
    "LTC": ["litecoin", "ltc"],
    "BCH": ["bitcoin cash", "bch"],
    "ETC": ["ethereum classic", "etc"],
    "XLM": ["stellar", "xlm"],
    "ALGO": ["algorand", "algo"],
    "ATOM": ["cosmos", "atom"],
    "NEAR": ["near protocol", "near"],
    "ICP": ["internet computer", "icp"],
    "FIL": ["filecoin", "fil"],
    "AAVE": ["aave"],
    "UNI": ["uniswap", "uni"],
    "SAND": ["sandbox", "sand"],
    "AXS": ["axie", "axs"],
    "THETA": ["theta"],
}


class NewsFetcher:
    """Fetches real crypto news from 3 free sources with VADER sentiment."""

    def __init__(self):
        self._cache: Dict[str, dict] = {}
        self._cache_ttl = 900  # 15 minutes
        self._articles_cache: Dict[str, dict] = {}
        self._sentiment_analyzer = None

    def _get_analyzer(self):
        """Lazy-load VADER to avoid import cost on startup."""
        if self._sentiment_analyzer is None:
            from services.sentiment_analyzer import sentiment_analyzer
            self._sentiment_analyzer = sentiment_analyzer
        return self._sentiment_analyzer

    # ── Source 1: CryptoPanic ────────────────────────────────

    def _fetch_cryptopanic(self, symbol: str, base_symbol: str) -> List[dict]:
        """Fetch articles from CryptoPanic free public API."""
        try:
            # Primary path: new async helper in ml/news_fetcher.py
            target = symbol if symbol else f"{base_symbol}USDC"
            try:
                return asyncio.run(fetch_cryptopanic_news(target))
            except RuntimeError:
                # Fallback for environments with existing running loop.
                loop = asyncio.new_event_loop()
                try:
                    return loop.run_until_complete(fetch_cryptopanic_news(target))
                finally:
                    loop.close()
        except Exception as e:
            logger.debug(f"CryptoPanic failed for {symbol}/{base_symbol}: {e}")
            return []

    # ── Source 2: CoinDesk RSS ───────────────────────────────

    def _fetch_coindesk_rss(self) -> List[dict]:
        """Fetch articles from CoinDesk RSS feed."""
        return self._parse_rss("https://www.coindesk.com/arc/outboundfeeds/rss/", "CoinDesk")

    # ── Source 3: Cointelegraph RSS ──────────────────────────

    def _fetch_cointelegraph_rss(self) -> List[dict]:
        """Fetch articles from Cointelegraph RSS feed."""
        return self._parse_rss("https://cointelegraph.com/rss", "Cointelegraph")

    def _parse_rss(self, url: str, source_name: str) -> List[dict]:
        """Generic RSS parser."""
        cache_key = f"rss:{source_name}"
        cached = self._articles_cache.get(cache_key)
        if cached and (time.time() - cached["fetched_at"]) < self._cache_ttl:
            return cached["articles"]

        try:
            import feedparser

            with httpx.Client(timeout=15.0) as client:
                resp = client.get(url, headers={"User-Agent": "AURA Trading Bot/1.0"})
                resp.raise_for_status()
                raw = resp.text

            feed = feedparser.parse(raw)
            articles = []
            for entry in feed.entries[:20]:
                summary = entry.get("summary", "")
                # Strip HTML tags from summary
                summary = re.sub(r"<[^>]+>", "", summary)[:500]

                articles.append({
                    "title": entry.get("title", ""),
                    "summary": summary,
                    "source": source_name,
                    "url": entry.get("link", ""),
                    "published_at": entry.get("published", ""),
                })

            self._articles_cache[cache_key] = {
                "articles": articles,
                "fetched_at": time.time(),
            }
            return articles

        except ImportError:
            logger.warning("feedparser not installed. Run: pip install feedparser")
            return []
        except Exception as e:
            logger.debug(f"RSS fetch failed for {source_name}: {e}")
            return []

    # ── Symbol matching ──────────────────────────────────────

    def _match_articles_to_symbol(self, articles: List[dict], base_symbol: str) -> List[dict]:
        """Filter articles relevant to a specific crypto symbol."""
        keywords = CRYPTO_NAMES.get(base_symbol, [base_symbol.lower()])
        matched = []
        for article in articles:
            text = f"{article.get('title', '')} {article.get('summary', '')}".lower()
            if any(kw in text for kw in keywords):
                matched.append(article)
        return matched

    # ── Sentiment scoring ────────────────────────────────────

    def get_symbol_sentiment(self, symbol: str) -> Dict:
        """
        Get sentiment score for a trading symbol (e.g. BTCUSDC).
        Combines all 3 sources, runs VADER analysis.
        Returns dict with score 0-100 and details.
        """
        cache_key = f"sentiment:{symbol}"
        cached = self._cache.get(cache_key)
        if cached and (time.time() - cached["fetched_at"]) < self._cache_ttl:
            return cached["value"]

        base = symbol.replace("USDC", "").replace("USDT", "")
        analyzer = self._get_analyzer()

        # Fetch from all 3 sources
        cryptopanic_articles = self._fetch_cryptopanic(symbol, base)
        coindesk_articles = self._fetch_coindesk_rss()
        cointelegraph_articles = self._fetch_cointelegraph_rss()

        # Match RSS articles to this symbol
        coindesk_matched = self._match_articles_to_symbol(coindesk_articles, base)
        cointelegraph_matched = self._match_articles_to_symbol(cointelegraph_articles, base)

        all_articles = cryptopanic_articles + coindesk_matched + cointelegraph_matched

        if not all_articles:
            result = {
                "score": 50.0,
                "label": "neutral",
                "article_count": 0,
                "sources": {},
                "symbol": symbol,
            }
            self._cache[cache_key] = {"value": result, "fetched_at": time.time()}
            return result

        # Run VADER on each article
        sentiments = []
        for article in all_articles:
            text = f"{article.get('title', '')} {article.get('summary', '')}"
            result = analyzer.analyze_text(text)
            sentiments.append(result["compound"])

        # Also factor in CryptoPanic vote data
        vote_adjustments = []
        for article in cryptopanic_articles:
            pos = int(article.get("bullish_votes", article.get("votes_positive", 0)) or 0)
            neg = int(article.get("bearish_votes", article.get("votes_negative", 0)) or 0)

            pos_adj = min(0.3, 0.05 * pos)
            neg_adj = min(0.3, 0.05 * neg)
            vote_adjustments.append(pos_adj - neg_adj)

        # Combine VADER + vote adjustments
        avg_vader = sum(sentiments) / len(sentiments) if sentiments else 0
        avg_vote_adj = sum(vote_adjustments) / len(vote_adjustments) if vote_adjustments else 0.0

        adjusted_vader = max(-1.0, min(1.0, avg_vader + avg_vote_adj))
        final_score = (adjusted_vader + 1) * 50

        final_score = max(0.0, min(100.0, final_score))

        # Label
        if final_score >= 60:
            label = "positive"
        elif final_score <= 40:
            label = "negative"
        else:
            label = "neutral"

        result = {
            "score": round(final_score, 1),
            "label": label,
            "article_count": len(all_articles),
            "vader_avg": round(avg_vader, 3),
            "vote_adjustment": round(avg_vote_adj, 3),
            "sources": {
                "cryptopanic": len(cryptopanic_articles),
                "coindesk": len(coindesk_matched),
                "cointelegraph": len(cointelegraph_matched),
            },
            "symbol": symbol,
        }

        self._cache[cache_key] = {"value": result, "fetched_at": time.time()}
        return result


# Singleton
news_fetcher = NewsFetcher()
