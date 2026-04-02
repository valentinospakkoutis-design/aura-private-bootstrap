"""
Smart Score Calculator for AURA Auto Trading
Combines multiple signals into a single 0-100 score:
  - News Sentiment (CryptoPanic)
  - Fear & Greed Index (alternative.me)
  - RSI 14-period
  - 24h Volume (Binance)
  - Multi-timeframe trend (daily + 4h)
  - ML prediction confidence
"""

import logging
import time
from typing import Dict, List, Optional

import httpx
import numpy as np

logger = logging.getLogger(__name__)

BINANCE_BASE = "https://api.binance.com"

# Base weights for each signal — must sum to 1.0
# prediction weight is dynamically boosted for high-accuracy symbols
BASE_WEIGHTS = {
    "news_sentiment": 0.15,
    "fear_greed": 0.10,
    "rsi": 0.20,
    "volume": 0.15,
    "multi_timeframe": 0.15,
    "prediction": 0.25,
}


class SmartScoreCalculator:
    def __init__(self):
        # In-memory cache: {key: {"value": ..., "fetched_at": timestamp}}
        self._cache: Dict[str, dict] = {}

    # ── Caching helper ───────────────────────────────────────

    def _cache_get(self, key: str, ttl: int) -> Optional[any]:
        cached = self._cache.get(key)
        if cached and (time.time() - cached["fetched_at"]) < ttl:
            return cached["value"]
        return None

    def _cache_set(self, key: str, value):
        self._cache[key] = {"value": value, "fetched_at": time.time()}

    # ── Signal 1: News Sentiment (CryptoPanic) ──────────────

    def _get_news_sentiment(self, symbol: str) -> float:
        """Get news sentiment from news_fetcher (3 sources + VADER). Returns 0-100."""
        try:
            from services.news_fetcher import news_fetcher
            result = news_fetcher.get_symbol_sentiment(symbol)
            return result.get("score", 50.0)
        except Exception as e:
            logger.debug(f"News sentiment failed for {symbol}: {e}")
            return 50.0

    # ── Signal 2: Fear & Greed Index ─────────────────────────

    def _get_fear_greed(self) -> float:
        """Fetch Crypto Fear & Greed Index. Returns 0-100."""
        cache_key = "fear_greed"
        cached = self._cache_get(cache_key, ttl=1800)
        if cached is not None:
            return cached

        try:
            with httpx.Client(timeout=10.0) as client:
                resp = client.get("https://api.alternative.me/fng/?limit=1")
                resp.raise_for_status()
                data = resp.json()

            value = float(data["data"][0]["value"])
            self._cache_set(cache_key, value)
            return value

        except Exception as e:
            logger.debug(f"Fear & Greed fetch failed: {e}")
            return 50.0

    # ── Signal 3: RSI (14-period) ────────────────────────────

    def _calculate_rsi(self, closes: List[float], period: int = 14) -> float:
        """Calculate RSI from closing prices. Returns 0-100."""
        if len(closes) < period + 1:
            return 50.0  # not enough data

        prices = np.array(closes)
        deltas = np.diff(prices)

        gains = np.where(deltas > 0, deltas, 0.0)
        losses = np.where(deltas < 0, -deltas, 0.0)

        avg_gain = np.mean(gains[:period])
        avg_loss = np.mean(losses[:period])

        # Smoothed moving average for remaining periods
        for i in range(period, len(gains)):
            avg_gain = (avg_gain * (period - 1) + gains[i]) / period
            avg_loss = (avg_loss * (period - 1) + losses[i]) / period

        if avg_loss == 0:
            return 100.0

        rs = avg_gain / avg_loss
        rsi = 100.0 - (100.0 / (1.0 + rs))
        return rsi

    def _get_rsi_score(self, symbol: str) -> float:
        """Fetch klines and compute RSI score for trading favorability. Returns 0-100."""
        cache_key = f"rsi:{symbol}"
        cached = self._cache_get(cache_key, ttl=300)
        if cached is not None:
            return cached

        closes = self._fetch_klines(symbol, interval="1d", limit=21)
        if not closes or len(closes) < 15:
            return 50.0

        rsi = self._calculate_rsi(closes)

        # Map raw RSI to a trading-favorability score
        if 30 <= rsi <= 50:
            # Oversold recovering — good buy zone
            score = 70.0 + (50.0 - rsi) * 1.5  # 70-100
        elif 50 < rsi <= 70:
            # Healthy uptrend
            score = 60.0 + (70.0 - rsi) * 1.0  # 60-80
        elif rsi < 30:
            # Deeply oversold — risky
            score = 30.0 + rsi  # 30-60
        else:
            # Overbought (>70) — avoid
            score = max(0.0, 70.0 - (rsi - 70.0) * 2.0)  # 70→10

        score = max(0.0, min(100.0, score))
        self._cache_set(cache_key, score)
        return score

    # ── Signal 4: Volume Analysis ────────────────────────────

    def _get_volume_score(self, symbol: str) -> float:
        """Fetch 24h ticker from Binance and score volume. Returns 0-100."""
        cache_key = f"vol:{symbol}"
        cached = self._cache_get(cache_key, ttl=300)
        if cached is not None:
            return cached

        try:
            with httpx.Client(base_url=BINANCE_BASE, timeout=10.0) as client:
                resp = client.get("/api/v3/ticker/24hr", params={"symbol": symbol})
                resp.raise_for_status()
                data = resp.json()

            quote_volume = float(data.get("quoteVolume", 0))
            price_change_pct = float(data.get("priceChangePercent", 0))

            # Volume thresholds (USDC quote volume)
            # Low < $500K, Medium $500K-$5M, High > $5M
            if quote_volume > 5_000_000:
                volume_factor = 1.0
            elif quote_volume > 500_000:
                volume_factor = 0.6 + 0.4 * (quote_volume - 500_000) / 4_500_000
            else:
                volume_factor = 0.3

            # High volume + positive movement = strong signal
            # High volume + negative movement = bearish signal
            direction = 1.0 if price_change_pct >= 0 else -1.0
            raw = 50.0 + direction * min(abs(price_change_pct), 10.0) * 3.0 * volume_factor

            score = max(0.0, min(100.0, raw))
            self._cache_set(cache_key, score)
            return score

        except Exception as e:
            logger.debug(f"Volume fetch failed for {symbol}: {e}")
            return 50.0

    # ── Signal 5: Multi-timeframe Confirmation ───────────────

    def _get_multi_timeframe_score(self, symbol: str) -> float:
        """Compare daily and 4h trends. Returns 0-100."""
        cache_key = f"mtf:{symbol}"
        cached = self._cache_get(cache_key, ttl=300)
        if cached is not None:
            return cached

        daily = self._fetch_klines(symbol, interval="1d", limit=21)
        four_h = self._fetch_klines(symbol, interval="4h", limit=30)

        daily_bullish = self._is_trend_bullish(daily, short=7, long=20) if daily and len(daily) >= 20 else None
        four_h_bullish = self._is_trend_bullish(four_h, short=6, long=12) if four_h and len(four_h) >= 12 else None

        if daily_bullish is None or four_h_bullish is None:
            return 50.0  # not enough data

        if daily_bullish and four_h_bullish:
            score = 90.0
        elif daily_bullish and not four_h_bullish:
            score = 60.0  # minor pullback in overall uptrend
        elif not daily_bullish and four_h_bullish:
            score = 35.0  # counter-trend bounce
        else:
            score = 10.0  # both bearish

        self._cache_set(cache_key, score)
        return score

    def _is_trend_bullish(self, closes: List[float], short: int, long: int) -> bool:
        arr = np.array(closes)
        sma_short = np.mean(arr[-short:])
        sma_long = np.mean(arr[-long:])
        return sma_short > sma_long

    # ── Signal 6: ML Prediction Confidence ───────────────────

    def _get_prediction_score(self, symbol: str) -> float:
        """Get score from the ML predictor. Returns 0-100."""
        try:
            from ai.asset_predictor import asset_predictor
            prediction = asset_predictor.predict_price(symbol, days=7)

            if "error" in prediction:
                return 50.0

            confidence = prediction.get("confidence", 50.0)
            recommendation = prediction.get("recommendation", "HOLD")

            if recommendation == "BUY":
                return min(100.0, confidence)
            elif recommendation == "SELL":
                return max(0.0, 100.0 - confidence)
            else:
                return 50.0

        except Exception as e:
            logger.debug(f"Prediction score failed for {symbol}: {e}")
            return 50.0

    # ── Binance klines helper ────────────────────────────────

    def _fetch_klines(self, symbol: str, interval: str = "1d", limit: int = 21) -> Optional[List[float]]:
        """Fetch closing prices from Binance klines."""
        cache_key = f"klines:{symbol}:{interval}:{limit}"
        cached = self._cache_get(cache_key, ttl=300)
        if cached is not None:
            return cached

        try:
            params = {"symbol": symbol.upper(), "interval": interval, "limit": limit}
            with httpx.Client(base_url=BINANCE_BASE, timeout=10.0) as client:
                resp = client.get("/api/v3/klines", params=params)
                resp.raise_for_status()
                klines = resp.json()

            if not klines:
                return None

            closes = [float(k[4]) for k in klines]
            self._cache_set(cache_key, closes)
            return closes

        except Exception as e:
            logger.debug(f"Klines fetch failed for {symbol} {interval}: {e}")
            return None

    # ── Composite Smart Score ────────────────────────────────

    def calculate_smart_score(self, symbol: str) -> dict:
        """
        Calculate the composite Smart Score (0-100) for a symbol.
        Combines all 6 signals with their weights.
        """
        signals = {}

        signals["news_sentiment"] = self._get_news_sentiment(symbol)
        signals["fear_greed"] = self._get_fear_greed()
        signals["rsi"] = self._get_rsi_score(symbol)
        signals["volume"] = self._get_volume_score(symbol)
        signals["multi_timeframe"] = self._get_multi_timeframe_score(symbol)
        signals["prediction"] = self._get_prediction_score(symbol)

        # Dynamic weighting: boost prediction weight for high-accuracy symbols
        weights = dict(BASE_WEIGHTS)
        rolling_accuracy = 0.5
        try:
            from services.accuracy_tracker import accuracy_tracker
            rolling_accuracy = accuracy_tracker.get_rolling_accuracy(symbol, days=30)
            if rolling_accuracy >= 0.70:
                # Boost prediction from 0.25 to 0.40, reduce others proportionally
                boost = 0.15
                weights["prediction"] = BASE_WEIGHTS["prediction"] + boost
                reduction = boost / 5
                for k in weights:
                    if k != "prediction":
                        weights[k] = max(0.05, BASE_WEIGHTS[k] - reduction)
        except Exception:
            pass

        composite = sum(signals[k] * weights[k] for k in weights)
        composite = round(max(0.0, min(100.0, composite)), 1)

        return {
            "symbol": symbol,
            "smart_score": composite,
            "signals": {
                k: {"score": round(v, 1), "weight": round(weights[k], 3)}
                for k, v in signals.items()
            },
            "rolling_accuracy": round(rolling_accuracy, 3),
            "recommendation": "TRADE" if composite > 75 else "WAIT",
            "calculated_at": time.time(),
        }


# Singleton
smart_score_calculator = SmartScoreCalculator()
