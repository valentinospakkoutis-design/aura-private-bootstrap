"""
Single source of truth for AURA-symbol → yfinance-ticker mapping.

Kept as a pure-data leaf module (NO imports) so both the heavy training stack
(`ml.auto_trainer`) and the low-level price client (`market_data.yfinance_client`)
can share it without creating a circular import.
"""

YFINANCE_SYMBOL_MAP = {
    # Metals (ETF proxies — futures tickers return 404 on weekends)
    "XAUUSDC": "GLD",
    "XAGUSDC": "SLV",
    "XPDUSDC": "PALL",
    "XPTUSDC": "PPLT",
    # US Stocks
    "AAPL": "AAPL",
    "MSFT": "MSFT",
    "GOOGL": "GOOGL",
    "AMZN": "AMZN",
    "NVDA": "NVDA",
    "TSLA": "TSLA",
    "META": "META",
    "JPM": "JPM",
    "BAC": "BAC",
    # EU Stocks
    "SAP": "SAP",
    "ASML": "ASML",
    "LVMH": "MC.PA",
    # Forex
    "EURUSD": "EURUSD=X",
    "GBPUSD": "GBPUSD=X",
    "USDJPY": "USDJPY=X",
    "AUDUSD": "AUDUSD=X",
    # Bonds / Indices
    "TNX": "^TNX",
    "VIX": "^VIX",
    # US Indices (ETF proxies)
    "US30": "DIA",        # Dow Jones
    "US500": "SPY",       # S&P 500
    "US100": "QQQ",       # Nasdaq 100
    # Commodities
    "OILUSD": "USO",      # Crude Oil ETF
    "XBRUSD": "BNO",      # Brent Oil ETF
    # Additional Forex majors
    "USDCAD": "USDCAD=X",
    "USDCHF": "USDCHF=X",
    "NZDUSD": "NZDUSD=X",
    "EURJPY": "EURJPY=X",
    "GBPJPY": "GBPJPY=X",
    # Futures — US indices
    "ES1!": "ES=F",
    "NQ1!": "NQ=F",
    "YM1!": "YM=F",
    # Futures — Metals
    "GC1!": "GC=F",
    "SI1!": "SI=F",
    "HG1!": "HG=F",
    # Futures — Energy
    "CL1!": "CL=F",
    "NG1!": "NG=F",
    # Futures — Agriculture
    "ZC1!": "ZC=F",
    "ZS1!": "ZS=F",
    # International indices
    "FTSE1!": "^FTSE",
    "DAX1!": "^GDAXI",
    "N2251!": "^N225",
}
