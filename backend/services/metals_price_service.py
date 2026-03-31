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

# Sanity limits — reject obviously wrong values
PRICE_SANITY_LIMITS = {
    "XAUUSDT": (1000, 10000),   # Gold: $1,000-$10,000
    "XAGUSDT": (10, 100),       # Silver: $10-$100
    "XPTUSDT": (500, 5000),     # Platinum: $500-$5,000
    "XPDUSDT": (500, 5000),     # Palladium: $500-$5,000
}

# Cache to avoid hitting Yahoo Finance on every request
_price_cache: dict[str, float] = {}
_cache_timestamp: dict[str, float] = {}
CACHE_TTL_SECONDS = 120  # refresh every 2 minutes


def get_metal_spot_price(binance_symbol: str) -> float | None:
    """
    Returns the real spot price for a metal symbol.
    Returns None if Yahoo Finance fails or returns insane value.
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

        # Try multiple approaches — yfinance API changes between versions
        price = None

        # Approach 1: fast_info
        try:
            info = data.fast_info
            price = getattr(info, 'last_price', None) or getattr(info, 'regular_market_price', None)
            print(f"[metals DEBUG] {binance_symbol} fast_info raw = {price}")
        except Exception:
            pass

        # Approach 2: info dict
        if not price:
            try:
                info_dict = data.info
                price = info_dict.get('regularMarketPrice') or info_dict.get('currentPrice') or info_dict.get('previousClose')
                print(f"[metals DEBUG] {binance_symbol} info dict raw = {price}")
            except Exception:
                pass

        # Approach 3: history (most reliable)
        if not price:
            try:
                hist = data.history(period="1d")
                if not hist.empty:
                    price = float(hist['Close'].iloc[-1])
                    print(f"[metals DEBUG] {binance_symbol} history raw = {price}")
            except Exception:
                pass

        if price and price > 0:
            price = float(price)

            # Sanity check — reject obviously wrong values
            limits = PRICE_SANITY_LIMITS.get(binance_symbol)
            if limits:
                min_price, max_price = limits
                if not (min_price <= price <= max_price):
                    print(f"[metals] {binance_symbol} price ${price:.2f} OUTSIDE sanity range ${min_price}-${max_price}, rejecting")
                    # SI=F sometimes returns price per 5000 oz contract — divide
                    if binance_symbol == "XAGUSDT" and price > 100:
                        corrected = price / 5000 * 1000  # approximate per-oz
                        if min_price <= corrected <= max_price:
                            price = corrected
                            print(f"[metals] {binance_symbol} corrected contract price → ${price:.2f}/oz")
                        else:
                            return _price_cache.get(ticker)  # stale cache or None
                    else:
                        return _price_cache.get(ticker)

            _price_cache[ticker] = price
            _cache_timestamp[ticker] = now
            print(f"[metals] {binance_symbol} ({ticker}) = ${price:.2f}")
            return price
        else:
            print(f"[metals] {binance_symbol} ({ticker}): all approaches returned None")
    except Exception as e:
        print(f"[metals] Failed to fetch {ticker}: {e}")

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
