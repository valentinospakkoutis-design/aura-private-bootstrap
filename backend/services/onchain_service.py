"""Free on-chain and market structure signals for crypto assets."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set

import httpx
from sqlalchemy import text

from cache.connection import cache_get, cache_set
from database.connection import SessionLocal
from services.morning_briefing import get_fear_greed_index

logger = logging.getLogger(__name__)

TTL_SECONDS = 300
SUPPORTED_SYMBOLS_TTL_SECONDS = 3600
BINANCE_FAPI_BASE = "https://fapi.binance.com"
SUPPORTED_QUOTES = ("USDC", "USDT")


def _normalize_symbol(symbol: str) -> str:
    return str(symbol or "").upper().strip()


def _futures_symbol(symbol: str) -> str:
    normalized = _normalize_symbol(symbol)
    if normalized.endswith("USDC"):
        return normalized[:-4] + "USDT"
    return normalized


def _ensure_table() -> None:
    if SessionLocal is None:
        return

    db = SessionLocal()
    try:
        db.execute(text("""
            CREATE TABLE IF NOT EXISTS onchain_signal_history (
                id SERIAL PRIMARY KEY,
                symbol VARCHAR(20) NOT NULL,
                futures_symbol VARCHAR(20) NOT NULL,
                onchain_score FLOAT NOT NULL,
                onchain_sentiment VARCHAR(12) NOT NULL,
                funding_rate FLOAT,
                open_interest FLOAT,
                long_short_ratio FLOAT,
                fear_greed INTEGER,
                funding_bearish BOOLEAN,
                extreme_fear BOOLEAN,
                extreme_greed BOOLEAN,
                overleveraged_longs BOOLEAN,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """))
        db.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_onchain_history_symbol_ts ON onchain_signal_history (symbol, created_at DESC)"
        ))
        db.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_onchain_history_sentiment_ts ON onchain_signal_history (onchain_sentiment, created_at DESC)"
        ))
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


def _persist_snapshot(signals: Dict) -> None:
    if SessionLocal is None:
        return

    _ensure_table()
    db = SessionLocal()
    try:
        db.execute(
            text("""
                INSERT INTO onchain_signal_history (
                    symbol, futures_symbol, onchain_score, onchain_sentiment,
                    funding_rate, open_interest, long_short_ratio, fear_greed,
                    funding_bearish, extreme_fear, extreme_greed, overleveraged_longs
                ) VALUES (
                    :symbol, :futures_symbol, :onchain_score, :onchain_sentiment,
                    :funding_rate, :open_interest, :long_short_ratio, :fear_greed,
                    :funding_bearish, :extreme_fear, :extreme_greed, :overleveraged_longs
                )
            """),
            {
                "symbol": _normalize_symbol(signals.get("symbol")),
                "futures_symbol": _normalize_symbol(signals.get("futures_symbol")),
                "onchain_score": float(signals.get("onchain_score", 0.5) or 0.5),
                "onchain_sentiment": str(signals.get("onchain_sentiment", "neutral") or "neutral"),
                "funding_rate": signals.get("funding_rate"),
                "open_interest": signals.get("open_interest"),
                "long_short_ratio": signals.get("long_short_ratio"),
                "fear_greed": signals.get("fear_greed"),
                "funding_bearish": bool(signals.get("funding_bearish", False)),
                "extreme_fear": bool(signals.get("extreme_fear", False)),
                "extreme_greed": bool(signals.get("extreme_greed", False)),
                "overleveraged_longs": bool(signals.get("overleveraged_longs", False)),
            },
        )
        db.commit()
    except Exception as e:
        db.rollback()
        logger.debug("On-chain snapshot persistence failed: %s", e)
    finally:
        db.close()


def get_supported_futures_symbols() -> Set[str]:
    cache_key = "onchain:supported_futures_symbols"
    cached = cache_get(cache_key)
    if isinstance(cached, list):
        return {str(item).upper() for item in cached}

    with httpx.Client(timeout=8.0) as client:
        response = client.get(f"{BINANCE_FAPI_BASE}/fapi/v1/exchangeInfo")
        response.raise_for_status()
        data = response.json()

    supported = {
        str(item.get("symbol", "")).upper()
        for item in data.get("symbols", [])
        if item.get("status") == "TRADING"
        and item.get("contractType") == "PERPETUAL"
        and str(item.get("quoteAsset", "")).upper() == "USDT"
    }
    cache_set(cache_key, sorted(supported), expire=SUPPORTED_SYMBOLS_TTL_SECONDS)
    return supported


def is_onchain_supported(symbol: str) -> bool:
    normalized = _normalize_symbol(symbol)
    if not normalized or not any(normalized.endswith(quote) for quote in SUPPORTED_QUOTES):
        return False

    try:
        return _futures_symbol(normalized) in get_supported_futures_symbols()
    except Exception as e:
        logger.debug("On-chain supported-symbol check failed for %s: %s", normalized, e)
        return False


def get_supported_onchain_symbols(candidate_symbols: Optional[List[str]] = None) -> List[str]:
    symbols = [_normalize_symbol(sym) for sym in (candidate_symbols or []) if sym]
    if not symbols:
        return []
    return [sym for sym in symbols if is_onchain_supported(sym)]


def get_binance_funding_rate(symbol: str) -> float:
    fut_symbol = _futures_symbol(symbol)
    with httpx.Client(timeout=5.0) as client:
        response = client.get(
            f"{BINANCE_FAPI_BASE}/fapi/v1/fundingRate",
            params={"symbol": fut_symbol, "limit": 1},
        )
        response.raise_for_status()
        data = response.json()
    return float(data[0].get("fundingRate", 0.0)) if data else 0.0


def get_binance_open_interest(symbol: str) -> float:
    fut_symbol = _futures_symbol(symbol)
    with httpx.Client(timeout=5.0) as client:
        response = client.get(
            f"{BINANCE_FAPI_BASE}/fapi/v1/openInterest",
            params={"symbol": fut_symbol},
        )
        response.raise_for_status()
        data = response.json()
    return float(data.get("openInterest", 0.0)) if isinstance(data, dict) else 0.0


def get_binance_ls_ratio(symbol: str) -> float:
    fut_symbol = _futures_symbol(symbol)
    with httpx.Client(timeout=5.0) as client:
        response = client.get(
            f"{BINANCE_FAPI_BASE}/futures/data/globalLongShortAccountRatio",
            params={"symbol": fut_symbol, "period": "1h", "limit": 1},
        )
        response.raise_for_status()
        data = response.json()
    return float(data[0].get("longShortRatio", 1.0)) if data else 1.0


def get_onchain_signals(symbol: str) -> Dict:
    """Collect free on-chain proxies and return a normalized sentiment bundle."""
    symbol = _normalize_symbol(symbol)
    if not is_onchain_supported(symbol):
        raise ValueError(f"On-chain signals not supported for {symbol}")

    cache_key = f"onchain:{symbol}"
    cached = cache_get(cache_key)
    if isinstance(cached, dict):
        return cached

    signals: Dict = {"symbol": symbol, "futures_symbol": _futures_symbol(symbol)}

    try:
        funding = get_binance_funding_rate(symbol)
        signals["funding_rate"] = funding
        signals["funding_bearish"] = funding > 0.01
    except Exception as e:
        logger.debug("[ONCHAIN] Funding rate failed for %s: %s", symbol, e)

    try:
        oi = get_binance_open_interest(symbol)
        signals["open_interest"] = oi
    except Exception as e:
        logger.debug("[ONCHAIN] Open interest failed for %s: %s", symbol, e)

    try:
        fg = int(get_fear_greed_index())
        signals["fear_greed"] = fg
        signals["extreme_fear"] = fg < 20
        signals["extreme_greed"] = fg > 80
    except Exception as e:
        logger.debug("[ONCHAIN] Fear & Greed failed for %s: %s", symbol, e)

    try:
        ls_ratio = get_binance_ls_ratio(symbol)
        signals["long_short_ratio"] = ls_ratio
        signals["overleveraged_longs"] = ls_ratio > 2.0
    except Exception as e:
        logger.debug("[ONCHAIN] L/S ratio failed for %s: %s", symbol, e)

    bullish_count = sum([
        not signals.get("funding_bearish", False),
        not signals.get("extreme_greed", False),
        not signals.get("overleveraged_longs", False),
        not signals.get("extreme_fear", False),
    ])

    signals["onchain_score"] = bullish_count / 4
    signals["onchain_sentiment"] = (
        "bullish" if bullish_count >= 3
        else "bearish" if bullish_count <= 1
        else "neutral"
    )
    signals["recorded_at"] = datetime.utcnow().isoformat()

    cache_set(cache_key, signals, expire=TTL_SECONDS)
    _persist_snapshot(signals)
    return signals


def get_onchain_history(symbol: str, days: int = 30, limit: int = 120) -> Dict:
    normalized = _normalize_symbol(symbol)
    if SessionLocal is None:
        return {"symbol": normalized, "history": [], "count": 0, "days": days}

    _ensure_table()
    cutoff = datetime.utcnow() - timedelta(days=max(1, int(days)))
    db = SessionLocal()
    try:
        rows = db.execute(
            text("""
                SELECT symbol, futures_symbol, onchain_score, onchain_sentiment,
                       funding_rate, open_interest, long_short_ratio, fear_greed,
                       funding_bearish, extreme_fear, extreme_greed, overleveraged_longs,
                       created_at
                FROM onchain_signal_history
                WHERE symbol = :symbol
                  AND created_at >= :cutoff
                ORDER BY created_at DESC
                LIMIT :lim
            """),
            {"symbol": normalized, "cutoff": cutoff, "lim": max(1, min(int(limit), 500))},
        ).mappings().all()

        history = []
        for row in rows:
            history.append({
                "symbol": row["symbol"],
                "futures_symbol": row["futures_symbol"],
                "score": float(row["onchain_score"] or 0.0),
                "sentiment": row["onchain_sentiment"] or "neutral",
                "funding_rate": row["funding_rate"],
                "open_interest": row["open_interest"],
                "long_short_ratio": row["long_short_ratio"],
                "fear_greed": row["fear_greed"],
                "funding_bearish": bool(row["funding_bearish"]),
                "extreme_fear": bool(row["extreme_fear"]),
                "extreme_greed": bool(row["extreme_greed"]),
                "overleveraged_longs": bool(row["overleveraged_longs"]),
                "created_at": row["created_at"].isoformat() if row["created_at"] else None,
            })

        return {"symbol": normalized, "history": history, "count": len(history), "days": days}
    finally:
        db.close()


def get_recent_onchain_summary(days: int = 7, symbol: Optional[str] = None) -> Dict:
    normalized_symbol = _normalize_symbol(symbol) if symbol else None
    if SessionLocal is None:
        return {
            "days": days,
            "symbol": normalized_symbol,
            "tracked_assets": 0,
            "average_score": 0.5,
            "market_sentiment": "neutral",
            "strongest_bullish": None,
            "strongest_bearish": None,
            "assets": [],
        }

    _ensure_table()
    cutoff = datetime.utcnow() - timedelta(days=max(1, int(days)))
    db = SessionLocal()
    try:
        where_sql = "WHERE created_at >= :cutoff"
        params: Dict[str, object] = {"cutoff": cutoff}
        if normalized_symbol:
            where_sql += " AND symbol = :symbol"
            params["symbol"] = normalized_symbol

        rows = db.execute(
            text(
                f"""
                SELECT symbol,
                       AVG(onchain_score) AS avg_score,
                       AVG(COALESCE(funding_rate, 0.0)) AS avg_funding_rate,
                       AVG(COALESCE(long_short_ratio, 1.0)) AS avg_long_short_ratio,
                       AVG(COALESCE(fear_greed, 50)) AS avg_fear_greed,
                       COUNT(*) AS snapshot_count,
                       MAX(created_at) AS last_seen,
                       SUM(CASE WHEN onchain_sentiment = 'bullish' THEN 1 ELSE 0 END) AS bullish_count,
                       SUM(CASE WHEN onchain_sentiment = 'bearish' THEN 1 ELSE 0 END) AS bearish_count
                FROM onchain_signal_history
                {where_sql}
                GROUP BY symbol
                ORDER BY AVG(onchain_score) DESC, symbol ASC
                """
            ),
            params,
        ).mappings().all()

        assets: List[Dict] = []
        for row in rows:
            avg_score = float(row["avg_score"] or 0.5)
            assets.append({
                "symbol": row["symbol"],
                "average_score": round(avg_score, 3),
                "average_funding_rate": round(float(row["avg_funding_rate"] or 0.0), 6),
                "average_long_short_ratio": round(float(row["avg_long_short_ratio"] or 1.0), 3),
                "average_fear_greed": round(float(row["avg_fear_greed"] or 50.0), 1),
                "snapshot_count": int(row["snapshot_count"] or 0),
                "bullish_count": int(row["bullish_count"] or 0),
                "bearish_count": int(row["bearish_count"] or 0),
                "last_seen": row["last_seen"].isoformat() if row["last_seen"] else None,
                "sentiment": "bullish" if avg_score >= 0.65 else "bearish" if avg_score <= 0.35 else "neutral",
            })

        if not assets:
            return {
                "days": days,
                "symbol": normalized_symbol,
                "tracked_assets": 0,
                "average_score": 0.5,
                "market_sentiment": "neutral",
                "strongest_bullish": None,
                "strongest_bearish": None,
                "assets": [],
            }

        average_score = round(sum(item["average_score"] for item in assets) / len(assets), 3)
        market_sentiment = "bullish" if average_score >= 0.65 else "bearish" if average_score <= 0.35 else "neutral"
        strongest_bullish = assets[0]
        strongest_bearish = sorted(assets, key=lambda item: item["average_score"])[0]

        return {
            "days": days,
            "symbol": normalized_symbol,
            "tracked_assets": len(assets),
            "average_score": average_score,
            "market_sentiment": market_sentiment,
            "strongest_bullish": {
                "symbol": strongest_bullish["symbol"],
                "average_score": strongest_bullish["average_score"],
                "sentiment": strongest_bullish["sentiment"],
            } if strongest_bullish else None,
            "strongest_bearish": {
                "symbol": strongest_bearish["symbol"],
                "average_score": strongest_bearish["average_score"],
                "sentiment": strongest_bearish["sentiment"],
            } if strongest_bearish else None,
            "assets": assets,
        }
    finally:
        db.close()
