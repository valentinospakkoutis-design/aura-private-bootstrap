"""
Market data integration module
yfinance integration for real market data
"""

from .yfinance_client import get_price, get_historical_prices, get_asset_info

__all__ = ["get_price", "get_historical_prices", "get_asset_info"]

