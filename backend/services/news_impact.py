"""News impact scoring.

Aggregates the last 24h of FinancialNews for a symbol, reuses stored FinBERT
sentiment scores (computing them on-the-fly when missing), and produces an
impact_score / impact_level suitable for gating trading decisions.
"""

import logging
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import or_

logger = logging.getLogger(__name__)

_CACHE: Dict[str, Dict[str, Any]] = {}
_CACHE_TTL = 300  # 5 minutes


def _base_tokens(symbol: str) -> List[str]:
    """Candidate substrings to match against FinancialNews.symbols text."""
    sym = symbol.upper()
    tokens = {sym}
    for suffix in ("USDC", "USDT", "-USD", "USD"):
        if sym.endswith(suffix):
            base = sym[: -len(suffix)]
            if base:
                tokens.add(base)
    # Strip yfinance futures/index decorations
    for extra in ("=F", "=X", "^"):
        tokens.add(sym.replace(extra, ""))
    return [t for t in tokens if t]


def _ensure_score(headline: str, summary: Optional[str], stored_score: Optional[float]) -> float:
    if stored_score is not None:
        try:
            return float(stored_score)
        except Exception:
            pass
    text = f"{headline or ''} {summary or ''}".strip()
    if not text:
        return 0.0
    try:
        from ml.sentiment_labeler import analyze_sentiment_finbert
        result = analyze_sentiment_finbert(text)
        return float(result.get("score", 0.0))
    except Exception as e:
        logger.debug(f"news_impact sentiment computation failed: {e}")
        return 0.0


def _classify(impact_score: float) -> str:
    if impact_score >= 75.0:
        return "EXTREME"
    if impact_score >= 50.0:
        return "HIGH"
    if impact_score >= 25.0:
        return "MEDIUM"
    return "LOW"


def _fetch_window(db, tokens: List[str], start: datetime, end: datetime):
    from database.models import FinancialNews
    filters = [FinancialNews.symbols.ilike(f"%{t}%") for t in tokens]
    return (
        db.query(FinancialNews)
        .filter(FinancialNews.published_at >= start, FinancialNews.published_at < end)
        .filter(or_(*filters))
        .all()
    )


def compute_news_impact_score(symbol: str) -> Dict[str, Any]:
    """Score the news impact on `symbol` over the last 24 hours.

    Returns news_count, avg_sentiment (-1..1), sentiment_momentum
    (24h avg − previous-24h avg), impact_score (0..100), and impact_level
    (LOW / MEDIUM / HIGH / EXTREME). Results are cached for 5 minutes.
    """
    sym_u = symbol.upper()
    now_ts = time.time()
    cached = _CACHE.get(sym_u)
    if cached and (now_ts - cached["t"]) < _CACHE_TTL:
        return cached["data"]

    default = {
        "symbol": sym_u,
        "news_count": 0,
        "avg_sentiment": 0.0,
        "sentiment_momentum": 0.0,
        "impact_score": 0.0,
        "impact_level": "LOW",
        "window_hours": 24,
    }

    try:
        from database.connection import SessionLocal
    except Exception as e:
        logger.debug(f"news_impact DB import failed: {e}")
        return default

    db = SessionLocal()
    if not db:
        return default

    tokens = _base_tokens(sym_u)
    now = datetime.utcnow()
    try:
        recent = _fetch_window(db, tokens, now - timedelta(hours=24), now)
        prior = _fetch_window(db, tokens, now - timedelta(hours=48), now - timedelta(hours=24))
    except Exception as e:
        logger.debug(f"news_impact query failed for {sym_u}: {e}")
        db.close()
        return default
    finally:
        try:
            db.close()
        except Exception:
            pass

    if not recent:
        _CACHE[sym_u] = {"t": now_ts, "data": default}
        return default

    recent_scores = [
        _ensure_score(r.headline, r.summary, r.sentiment_score) for r in recent
    ]
    prior_scores = [
        _ensure_score(r.headline, r.summary, r.sentiment_score) for r in prior
    ]

    news_count = len(recent_scores)
    avg_sentiment = sum(recent_scores) / news_count if news_count else 0.0
    prior_avg = (sum(prior_scores) / len(prior_scores)) if prior_scores else 0.0
    sentiment_momentum = avg_sentiment - prior_avg

    # Impact components, each normalized to 0-1
    volume_component = min(1.0, news_count / 10.0)
    magnitude_component = min(1.0, abs(avg_sentiment))
    momentum_component = min(1.0, abs(sentiment_momentum) / 0.5)
    impact_score = 100.0 * (
        0.4 * volume_component + 0.4 * magnitude_component + 0.2 * momentum_component
    )

    result = {
        "symbol": sym_u,
        "news_count": int(news_count),
        "avg_sentiment": round(float(avg_sentiment), 4),
        "sentiment_momentum": round(float(sentiment_momentum), 4),
        "impact_score": round(float(impact_score), 2),
        "impact_level": _classify(impact_score),
        "window_hours": 24,
        "prior_window_count": int(len(prior_scores)),
        "prior_avg_sentiment": round(float(prior_avg), 4),
    }

    _CACHE[sym_u] = {"t": now_ts, "data": result}
    return result
