"""
yfinance client for real market data
"""

import yfinance as yf
from typing import Optional, Dict, List
from datetime import datetime, timedelta
from cache.decorators import cached


def _normalize_symbol(symbol: str) -> str:
    """
    Normalize symbol for yfinance
    Convert AURA symbols to yfinance format
    """
    symbol = symbol.upper()
    
    # Remove USDT suffix for crypto
    if symbol.endswith("USDT"):
        base = symbol[:-4]
        # Map to yfinance crypto symbols
        crypto_map = {
            "BTC": "BTC-USD",
            "ETH": "ETH-USD",
            "BNB": "BNB-USD",
            "ADA": "ADA-USD",
            "SOL": "SOL-USD",
            "XRP": "XRP-USD",
            "DOGE": "DOGE-USD",
            "SHIB": "SHIB-USD",
        }
        if base in crypto_map:
            return crypto_map[base]
    
    # Stocks are usually already correct
    # Forex pairs need special handling
    if len(symbol) == 6 and "/" not in symbol:
        # Try as forex pair (e.g., EURUSD -> EURUSD=X)
        if symbol in ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "USDCHF", "NZDUSD"]:
            return f"{symbol[:3]}{symbol[3:]}=X"
    
    return symbol


@cached(expire=300, key_prefix="price")  # Cache for 5 minutes
def get_price(symbol: str) -> Optional[Dict]:
    """
    Get current price for a symbol using yfinance
    
    Args:
        symbol: Asset symbol (e.g., "AAPL", "BTCUSDT", "EURUSD")
    
    Returns:
        Dict with price data or None if error
    """
    try:
        normalized_symbol = _normalize_symbol(symbol)
        ticker = yf.Ticker(normalized_symbol)
        info = ticker.info
        
        # Get latest price
        hist = ticker.history(period="1d", interval="1m")
        if hist.empty:
            # Fallback to info
            current_price = info.get("currentPrice") or info.get("regularMarketPrice") or info.get("previousClose")
        else:
            current_price = float(hist["Close"].iloc[-1])
        
        return {
            "symbol": symbol,
            "price": current_price,
            "change": info.get("regularMarketChange", 0),
            "change_percent": info.get("regularMarketChangePercent", 0),
            "volume": info.get("volume", 0),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        print(f"[-] Error fetching price for {symbol}: {e}")
        return None


def get_historical_prices(
    symbol: str,
    period: str = "1mo",
    interval: str = "1d"
) -> Optional[List[Dict]]:
    """
    Get historical prices for a symbol
    
    Args:
        symbol: Asset symbol
        period: Period (1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max)
        interval: Interval (1m, 2m, 5m, 15m, 30m, 60m, 90m, 1h, 1d, 5d, 1wk, 1mo, 3mo)
    
    Returns:
        List of price data points
    """
    try:
        normalized_symbol = _normalize_symbol(symbol)
        ticker = yf.Ticker(normalized_symbol)
        hist = ticker.history(period=period, interval=interval)
        
        if hist.empty:
            return None
        
        result = []
        for idx, row in hist.iterrows():
            result.append({
                "timestamp": idx.isoformat(),
                "open": float(row["Open"]),
                "high": float(row["High"]),
                "low": float(row["Low"]),
                "close": float(row["Close"]),
                "volume": float(row["Volume"]) if "Volume" in row else 0.0
            })
        
        return result
    except Exception as e:
        print(f"[-] Error fetching historical prices for {symbol}: {e}")
        return None


def get_asset_info(symbol: str) -> Optional[Dict]:
    """
    Get asset information
    
    Args:
        symbol: Asset symbol
    
    Returns:
        Dict with asset info
    """
    try:
        normalized_symbol = _normalize_symbol(symbol)
        ticker = yf.Ticker(normalized_symbol)
        info = ticker.info
        
        return {
            "symbol": symbol,
            "name": info.get("longName") or info.get("shortName", symbol),
            "sector": info.get("sector"),
            "industry": info.get("industry"),
            "market_cap": info.get("marketCap"),
            "currency": info.get("currency", "USD")
        }
    except Exception as e:
        print(f"[-] Error fetching asset info for {symbol}: {e}")
        return None

