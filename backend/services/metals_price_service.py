"""
Real spot prices for precious metals via Yahoo Finance.
Binance XAUUSDT is a tokenized product (~$2,000), not the real spot price (~$3,000+).
"""

import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# Mapping: Binance symbol → Yahoo Finance ticker
METALS_TICKERS = {
    "XAUUSDT": "GC=F",   # Gold Futures (USD per troy oz)
    "XAGUSDT": "SI=F",   # Silver Futures (USD per troy oz)
    "XPTUSDT": "PL=F",   # Platinum Futures (USD per troy oz)
    "XPDUSDT": "PA=F",   # Palladium Futures (USD per troy oz)
}

# Cache to avoid hitting Yahoo Finance on every request
_price_cache: dict[str, float] = {}
_cache_timestamp: dict[str, float] = {}
CACHE_TTL_SECONDS = 120  # refresh every 2 minutes


def get_metal_spot_price(binance_symbol: str) -> float | None:
    """
    Returns the real spot price for a metal symbol.
    Returns None if Yahoo Finance fails (caller should use Binance fallback).
    """
    ticker = METALS_TICKERS.get(binance_symbol)
    if not ticker:
        return None

    now = datetime.utcnow().timestamp()

    # Return cached price if still fresh
    if ticker in _price_cache and (now - _cache_timestamp.get(ticker, 0)) < CACHE_TTL_SECONDS:
        return _price_cache[ticker]

    try:
        import yfinance as yf
        data = yf.Ticker(ticker)
        info = data.fast_info
        price = getattr(info, 'last_price', None) or getattr(info, 'regular_market_price', None)
        if price and price > 0:
            _price_cache[ticker] = float(price)
            _cache_timestamp[ticker] = now
            logger.info(f"[metals] {binance_symbol} ({ticker}) = ${price:.2f}")
            return float(price)
    except Exception as e:
        logger.warning(f"[metals] Failed to fetch {ticker}: {e}")

    # Return stale cache if available
    if ticker in _price_cache:
        return _price_cache[ticker]

    return None


def get_all_metals_prices() -> dict[str, float]:
    """Returns {binance_symbol: spot_price} for all metals."""
    prices = {}
    for symbol in METALS_TICKERS:
        price = get_metal_spot_price(symbol)
        if price:
            prices[symbol] = price
    return prices


def is_metal(binance_symbol: str) -> bool:
    """Check if a symbol is a precious metal."""
    return binance_symbol in METALS_TICKERS
