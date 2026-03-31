"""
Real spot prices for precious metals via Yahoo Finance.
Binance XAUUSDT is a tokenized product (~$2,000), not the real spot price (~$3,000+).
"""

import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# Mapping: Binance symbol → Yahoo Finance ticker (primary)
METALS_TICKERS = {
    "XAUUSDT": "GC=F",    # Gold Futures ✅ ~$3,000+
    "XAGUSDT": "XAG=X",   # Silver spot (forex) — SI=F returns contract price, not per-oz
    "XPTUSDT": "PL=F",    # Platinum Futures
    "XPDUSDT": "PA=F",    # Palladium Futures
}

# Fallback tickers if primary fails sanity check
METALS_TICKERS_FALLBACK = {
    "XAGUSDT": ["SI=F", "SIVR", "SLV"],
}

# Sanity limits — reject obviously wrong values
PRICE_SANITY_LIMITS = {
    "XAUUSDT": (1000, 10000),   # Gold: $1,000-$10,000
    "XAGUSDT": (20, 50),        # Silver: $20-$50/oz (tightened)
    "XPTUSDT": (500, 5000),     # Platinum: $500-$5,000
    "XPDUSDT": (500, 5000),     # Palladium: $500-$5,000
}

# Cache to avoid hitting Yahoo Finance on every request
_price_cache: dict[str, float] = {}
_cache_timestamp: dict[str, float] = {}
CACHE_TTL_SECONDS = 120  # refresh every 2 minutes


def _fetch_yf_price(ticker: str, binance_symbol: str) -> float | None:
    """Fetch price from a single Yahoo Finance ticker. Returns None on failure."""
    try:
        import yfinance as yf
        data = yf.Ticker(ticker)
        price = None

        # Approach 1: fast_info
        try:
            info = data.fast_info
            price = getattr(info, 'last_price', None) or getattr(info, 'regular_market_price', None)
        except Exception:
            pass

        # Approach 2: info dict
        if not price:
            try:
                info_dict = data.info
                price = info_dict.get('regularMarketPrice') or info_dict.get('currentPrice') or info_dict.get('previousClose')
            except Exception:
                pass

        # Approach 3: history (most reliable)
        if not price:
            try:
                hist = data.history(period="1d")
                if not hist.empty:
                    price = float(hist['Close'].iloc[-1])
            except Exception:
                pass

        if price and price > 0:
            print(f"[metals DEBUG] {binance_symbol} raw price from {ticker} = {price}")
            return float(price)
    except Exception as e:
        print(f"[metals] Failed to fetch {ticker}: {e}")
    return None


def _passes_sanity(binance_symbol: str, price: float) -> bool:
    """Check if a price is within expected range."""
    limits = PRICE_SANITY_LIMITS.get(binance_symbol)
    if not limits:
        return True
    min_p, max_p = limits
    return min_p <= price <= max_p


def get_metal_spot_price(binance_symbol: str) -> float | None:
    """
    Returns the real spot price for a metal symbol.
    Tries primary ticker, then fallbacks. Returns None if all fail.
    """
    primary_ticker = METALS_TICKERS.get(binance_symbol)
    if not primary_ticker:
        return None

    now = datetime.utcnow().timestamp()

    # Return cached price if still fresh (cache key = binance_symbol)
    if binance_symbol in _price_cache and (now - _cache_timestamp.get(binance_symbol, 0)) < CACHE_TTL_SECONDS:
        return _price_cache[binance_symbol]

    # Build ticker list: primary first, then fallbacks
    tickers_to_try = [primary_ticker] + METALS_TICKERS_FALLBACK.get(binance_symbol, [])

    for ticker in tickers_to_try:
        price = _fetch_yf_price(ticker, binance_symbol)
        if price and _passes_sanity(binance_symbol, price):
            _price_cache[binance_symbol] = price
            _cache_timestamp[binance_symbol] = now
            print(f"[metals] {binance_symbol} ({ticker}) = ${price:.2f} ✅")
            return price
        elif price:
            print(f"[metals] {binance_symbol} ({ticker}) = ${price:.2f} — FAILED sanity check, trying next")

    print(f"[metals] {binance_symbol}: all tickers failed")

    # Return stale cache if available
    if binance_symbol in _price_cache:
        return _price_cache[binance_symbol]

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
