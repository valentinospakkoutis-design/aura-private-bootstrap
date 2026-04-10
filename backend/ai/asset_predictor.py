"""
Unified Asset Predictor
Υποστηρίζει Precious Metals, Stocks, Cryptocurrencies, και Derivatives
"""

from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import os
import pickle
import glob
import numpy as np
import pandas as pd
import random
import math
import time
import logging
from enum import Enum

import httpx

logger = logging.getLogger(__name__)


class AssetType(str, Enum):
    """Asset types"""
    PRECIOUS_METAL = "precious_metal"
    STOCK = "stock"
    CRYPTO = "crypto"
    DERIVATIVE = "derivative"
    BOND = "bond"
    FX = "fx"
    SENTIMENT = "sentiment"


class AssetPredictor:
    """
    Unified AI Predictor για όλα τα asset types
    Precious Metals, Stocks, Cryptocurrencies, Derivatives
    """
    
    def __init__(self):
        # Precious Metals
        self.precious_metals = {
            "XAUUSDC": {"name": "Gold", "symbol": "XAU", "base_price": 2050.0, "type": AssetType.PRECIOUS_METAL},
            "XAGUSDC": {"name": "Silver", "symbol": "XAG", "base_price": 24.5, "type": AssetType.PRECIOUS_METAL},
            "XPTUSDC": {"name": "Platinum", "symbol": "XPT", "base_price": 950.0, "type": AssetType.PRECIOUS_METAL},
            "XPDUSDC": {"name": "Palladium", "symbol": "XPD", "base_price": 1200.0, "type": AssetType.PRECIOUS_METAL},
        }
        
        # Stocks (Major indices και popular stocks - eToro supported)
        self.stocks = {
            # Tech Stocks (eToro Top)
            "AAPL": {"name": "Apple Inc.", "base_price": 180.0, "type": AssetType.STOCK, "exchange": "NASDAQ"},
            "MSFT": {"name": "Microsoft Corporation", "base_price": 380.0, "type": AssetType.STOCK, "exchange": "NASDAQ"},
            "GOOGL": {"name": "Alphabet Inc.", "base_price": 140.0, "type": AssetType.STOCK, "exchange": "NASDAQ"},
            "AMZN": {"name": "Amazon.com Inc.", "base_price": 150.0, "type": AssetType.STOCK, "exchange": "NASDAQ"},
            "TSLA": {"name": "Tesla Inc.", "base_price": 250.0, "type": AssetType.STOCK, "exchange": "NASDAQ"},
            "META": {"name": "Meta Platforms Inc.", "base_price": 320.0, "type": AssetType.STOCK, "exchange": "NASDAQ"},
            "NVDA": {"name": "NVIDIA Corporation", "base_price": 500.0, "type": AssetType.STOCK, "exchange": "NASDAQ"},
            "NIO": {"name": "NIO Inc.", "base_price": 8.0, "type": AssetType.STOCK, "exchange": "NYSE"},
            
            # ETFs (eToro Popular)
            "SPY": {"name": "SPDR S&P 500 ETF", "base_price": 450.0, "type": AssetType.STOCK, "exchange": "NYSE"},
            "QQQ": {"name": "Invesco QQQ Trust", "base_price": 380.0, "type": AssetType.STOCK, "exchange": "NASDAQ"},
            "VTI": {"name": "Vanguard Total Stock Market ETF", "base_price": 240.0, "type": AssetType.STOCK, "exchange": "NYSE"},
            "VOO": {"name": "Vanguard S&P 500 ETF", "base_price": 420.0, "type": AssetType.STOCK, "exchange": "NYSE"},
            "ARKK": {"name": "ARK Innovation ETF", "base_price": 50.0, "type": AssetType.STOCK, "exchange": "NYSE"},
            
            # Financial Stocks
            "JPM": {"name": "JPMorgan Chase & Co.", "base_price": 150.0, "type": AssetType.STOCK, "exchange": "NYSE"},
            "BAC": {"name": "Bank of America Corp.", "base_price": 35.0, "type": AssetType.STOCK, "exchange": "NYSE"},
            "GS": {"name": "Goldman Sachs Group Inc.", "base_price": 400.0, "type": AssetType.STOCK, "exchange": "NYSE"},
            
            # Consumer & Retail
            "WMT": {"name": "Walmart Inc.", "base_price": 160.0, "type": AssetType.STOCK, "exchange": "NYSE"},
            "HD": {"name": "The Home Depot Inc.", "base_price": 350.0, "type": AssetType.STOCK, "exchange": "NYSE"},
            "NKE": {"name": "Nike Inc.", "base_price": 100.0, "type": AssetType.STOCK, "exchange": "NYSE"},
            
            # Healthcare
            "JNJ": {"name": "Johnson & Johnson", "base_price": 160.0, "type": AssetType.STOCK, "exchange": "NYSE"},
            "PFE": {"name": "Pfizer Inc.", "base_price": 30.0, "type": AssetType.STOCK, "exchange": "NYSE"},
            "UNH": {"name": "UnitedHealth Group Inc.", "base_price": 500.0, "type": AssetType.STOCK, "exchange": "NYSE"},
            
            # Energy
            "XOM": {"name": "Exxon Mobil Corporation", "base_price": 110.0, "type": AssetType.STOCK, "exchange": "NYSE"},
            "CVX": {"name": "Chevron Corporation", "base_price": 150.0, "type": AssetType.STOCK, "exchange": "NYSE"},
            
            # Industrial
            "BA": {"name": "The Boeing Company", "base_price": 200.0, "type": AssetType.STOCK, "exchange": "NYSE"},
            "CAT": {"name": "Caterpillar Inc.", "base_price": 250.0, "type": AssetType.STOCK, "exchange": "NYSE"},

            # European Stocks
            "ASML": {"name": "ASML Holding", "base_price": 900.0, "type": AssetType.STOCK, "exchange": "AMS"},
            "SAP": {"name": "SAP SE", "base_price": 200.0, "type": AssetType.STOCK, "exchange": "XETRA"},
            "MC.PA": {"name": "LVMH Moët Hennessy", "base_price": 800.0, "type": AssetType.STOCK, "exchange": "EPA"},

            # Greek Stocks
            "BOC.AT": {"name": "Bank of Cyprus", "base_price": 5.0, "type": AssetType.STOCK, "exchange": "ATH"},
        }
        
        # Cryptocurrencies (eToro supports 100+ cryptos, 70+ cryptoassets)
        self.cryptos = {
            # Major Cryptocurrencies (eToro Top)
            "BTCUSDC": {"name": "Bitcoin", "symbol": "BTC", "base_price": 45000.0, "type": AssetType.CRYPTO},
            "ETHUSDC": {"name": "Ethereum", "symbol": "ETH", "base_price": 2500.0, "type": AssetType.CRYPTO},
            "BNBUSDC": {"name": "Binance Coin", "symbol": "BNB", "base_price": 300.0, "type": AssetType.CRYPTO},
            "ADAUSDC": {"name": "Cardano", "symbol": "ADA", "base_price": 0.5, "type": AssetType.CRYPTO},
            "SOLUSDC": {"name": "Solana", "symbol": "SOL", "base_price": 100.0, "type": AssetType.CRYPTO},
            "XRPUSDC": {"name": "Ripple", "symbol": "XRP", "base_price": 0.6, "type": AssetType.CRYPTO},
            "DOTUSDC": {"name": "Polkadot", "symbol": "DOT", "base_price": 7.0, "type": AssetType.CRYPTO},
            "POLUSDC": {"name": "Polygon", "symbol": "POL", "base_price": 0.4, "type": AssetType.CRYPTO},
            "LINKUSDC": {"name": "Chainlink", "symbol": "LINK", "base_price": 15.0, "type": AssetType.CRYPTO},
            "AVAXUSDC": {"name": "Avalanche", "symbol": "AVAX", "base_price": 35.0, "type": AssetType.CRYPTO},
            
            # eToro Popular Cryptos
            "SHIBUSDC": {"name": "Shiba Inu", "symbol": "SHIB", "base_price": 0.000015, "type": AssetType.CRYPTO},
            "DOGEUSDC": {"name": "Dogecoin", "symbol": "DOGE", "base_price": 0.08, "type": AssetType.CRYPTO},
            "TRXUSDC": {"name": "TRON", "symbol": "TRX", "base_price": 0.1, "type": AssetType.CRYPTO},
            "LTCUSDC": {"name": "Litecoin", "symbol": "LTC", "base_price": 70.0, "type": AssetType.CRYPTO},
            "BCHUSDC": {"name": "Bitcoin Cash", "symbol": "BCH", "base_price": 250.0, "type": AssetType.CRYPTO},
            "ETCUSDC": {"name": "Ethereum Classic", "symbol": "ETC", "base_price": 20.0, "type": AssetType.CRYPTO},
            "XLMUSDC": {"name": "Stellar", "symbol": "XLM", "base_price": 0.12, "type": AssetType.CRYPTO},
            "ALGOUSDC": {"name": "Algorand", "symbol": "ALGO", "base_price": 0.2, "type": AssetType.CRYPTO},
            "ATOMUSDC": {"name": "Cosmos", "symbol": "ATOM", "base_price": 10.0, "type": AssetType.CRYPTO},
            "NEARUSDC": {"name": "NEAR Protocol", "symbol": "NEAR", "base_price": 3.0, "type": AssetType.CRYPTO},
            "ICPUSDC": {"name": "Internet Computer", "symbol": "ICP", "base_price": 12.0, "type": AssetType.CRYPTO},
            "FILUSDC": {"name": "Filecoin", "symbol": "FIL", "base_price": 5.0, "type": AssetType.CRYPTO},
            "AAVEUSDC": {"name": "Aave", "symbol": "AAVE", "base_price": 100.0, "type": AssetType.CRYPTO},
            "UNIUSDC": {"name": "Uniswap", "symbol": "UNI", "base_price": 6.0, "type": AssetType.CRYPTO},
            "SANDUSDC": {"name": "The Sandbox", "symbol": "SAND", "base_price": 0.5, "type": AssetType.CRYPTO},
            "AXSUSDC": {"name": "Axie Infinity", "symbol": "AXS", "base_price": 7.0, "type": AssetType.CRYPTO},
            "THETAUSDC": {"name": "Theta Network", "symbol": "THETA", "base_price": 1.0, "type": AssetType.CRYPTO},
        }
        
        # Derivatives (Futures, Options - eToro CFD Trading)
        self.derivatives = {
            # Index Futures
            "ES1!": {"name": "E-mini S&P 500 Futures", "base_price": 4500.0, "type": AssetType.DERIVATIVE, "underlying": "SPX"},
            "NQ1!": {"name": "E-mini NASDAQ-100 Futures", "base_price": 15000.0, "type": AssetType.DERIVATIVE, "underlying": "NDX"},
            "YM1!": {"name": "E-mini Dow Futures", "base_price": 35000.0, "type": AssetType.DERIVATIVE, "underlying": "DJI"},
            "FTSE1!": {"name": "FTSE 100 Futures", "base_price": 7500.0, "type": AssetType.DERIVATIVE, "underlying": "FTSE"},
            "DAX1!": {"name": "DAX Futures", "base_price": 16000.0, "type": AssetType.DERIVATIVE, "underlying": "DAX"},
            "N2251!": {"name": "Nikkei 225 Futures", "base_price": 33000.0, "type": AssetType.DERIVATIVE, "underlying": "N225"},
            
            # Commodity Futures
            "GC1!": {"name": "Gold Futures", "base_price": 2050.0, "type": AssetType.DERIVATIVE, "underlying": "XAU"},
            "SI1!": {"name": "Silver Futures", "base_price": 24.5, "type": AssetType.DERIVATIVE, "underlying": "XAG"},
            "CL1!": {"name": "Crude Oil Futures", "base_price": 75.0, "type": AssetType.DERIVATIVE, "underlying": "OIL"},
            "NG1!": {"name": "Natural Gas Futures", "base_price": 3.5, "type": AssetType.DERIVATIVE, "underlying": "GAS"},
            "HG1!": {"name": "Copper Futures", "base_price": 3.8, "type": AssetType.DERIVATIVE, "underlying": "COPPER"},
            "ZC1!": {"name": "Corn Futures", "base_price": 5.0, "type": AssetType.DERIVATIVE, "underlying": "CORN"},
            "ZS1!": {"name": "Soybean Futures", "base_price": 13.0, "type": AssetType.DERIVATIVE, "underlying": "SOYBEAN"},
            
            # Currency Futures (eToro Forex)
            "EURUSD": {"name": "EUR/USD", "base_price": 1.08, "type": AssetType.DERIVATIVE, "underlying": "FOREX"},
            "GBPUSD": {"name": "GBP/USD", "base_price": 1.27, "type": AssetType.DERIVATIVE, "underlying": "FOREX"},
            "USDJPY": {"name": "USD/JPY", "base_price": 150.0, "type": AssetType.DERIVATIVE, "underlying": "FOREX"},
            "AUDUSD": {"name": "AUD/USD", "base_price": 0.66, "type": AssetType.DERIVATIVE, "underlying": "FOREX"},
            "USDCAD": {"name": "USD/CAD", "base_price": 1.35, "type": AssetType.DERIVATIVE, "underlying": "FOREX"},
            "USDCHF": {"name": "USD/CHF", "base_price": 0.88, "type": AssetType.DERIVATIVE, "underlying": "FOREX"},
            "NZDUSD": {"name": "NZD/USD", "base_price": 0.61, "type": AssetType.DERIVATIVE, "underlying": "FOREX"},
        }
        
        # Bonds (US Treasury yields as proxy)
        self.bonds = {
            "^TNX": {"name": "US 10Y Treasury Yield", "base_price": 4.3, "type": AssetType.BOND},
            "^IRX": {"name": "US 3M Treasury Yield", "base_price": 5.2, "type": AssetType.BOND},
            "^TYX": {"name": "US 30Y Treasury Yield", "base_price": 4.5, "type": AssetType.BOND},
        }

        # Extra FX pairs
        self.fx = {
            "EURUSD=X": {"name": "EUR/USD", "base_price": 1.08, "type": AssetType.FX},
            "GBPEUR=X": {"name": "GBP/EUR", "base_price": 1.17, "type": AssetType.FX},
        }

        # Sentiment
        self.sentiment = {
            "^VIX": {"name": "VIX Fear Index", "base_price": 18.0, "type": AssetType.SENTIMENT},
        }

        # Combine all assets
        self.all_assets = {}
        self.all_assets.update(self.precious_metals)
        self.all_assets.update(self.stocks)
        self.all_assets.update(self.cryptos)
        self.all_assets.update(self.derivatives)
        self.all_assets.update(self.bonds)
        self.all_assets.update(self.fx)
        self.all_assets.update(self.sentiment)
        
        self.prediction_history = {}

        # Price cache: {symbol: {"prices": [...], "fetched_at": timestamp}}
        self._price_cache: Dict[str, dict] = {}
        self._price_cache_ttl = 300  # 5 minutes

        # Load trained models
        self.models = {}
        self.scalers = {}
        self.model_features: Dict[str, List[str]] = {}  # XGBoost feature columns
        self._load_models()
    
    def _load_models(self):
        """Load trained ML models from disk (XGBoost preferred, Random Forest fallback)"""
        models_dir = os.path.join(os.path.dirname(__file__), "..", "models")

        if not os.path.exists(models_dir):
            print(f"[!] Models directory not found: {models_dir}")
            return

        # 1) Load XGBoost "latest" models first (from auto_trainer)
        xgb_files = glob.glob(os.path.join(models_dir, "*_xgboost_latest.pkl"))
        for model_path in xgb_files:
            try:
                filename = os.path.basename(model_path)
                symbol = filename.split("_xgboost")[0]

                with open(model_path, "rb") as f:
                    model_data = pickle.load(f)
                    self.models[symbol] = model_data["model"]
                    self.scalers[symbol] = model_data["scaler"]
                    self.model_features[symbol] = model_data.get("feature_cols", [])

                print(f"[+] Loaded XGBoost model for {symbol}")
            except Exception as e:
                print(f"[-] Error loading XGBoost model {model_path}: {e}")

        # 2) Fallback: load Random Forest models for symbols not yet covered
        rf_files = glob.glob(os.path.join(models_dir, "*_random_forest_*.pkl"))
        rf_files = [f for f in rf_files if "scaler" not in os.path.basename(f)]

        for model_path in rf_files:
            try:
                filename = os.path.basename(model_path)
                symbol = filename.split("_")[0]

                if symbol in self.models:
                    continue  # XGBoost already loaded

                with open(model_path, "rb") as f:
                    model_data = pickle.load(f)
                    self.models[symbol] = model_data["model"]
                    self.scalers[symbol] = model_data["scaler"]

                print(f"[+] Loaded RF model for {symbol} (fallback)")
            except Exception as e:
                print(f"[-] Error loading RF model {model_path}: {e}")
    
    def _fetch_binance_klines(self, symbol: str, days: int = 7) -> Optional[List[float]]:
        """Fetch daily closing prices from Binance public API (no auth needed)."""
        try:
            params = {
                "symbol": symbol.upper(),
                "interval": "1d",
                "limit": days + 1,  # +1 to include today's partial candle
            }
            with httpx.Client(base_url="https://api.binance.com", timeout=10.0) as client:
                resp = client.get("/api/v3/klines", params=params)
                resp.raise_for_status()
                klines = resp.json()

            if not klines or len(klines) < 2:
                return None

            # Binance kline format: [open_time, open, high, low, close, volume, ...]
            closes = [float(k[4]) for k in klines]
            return closes
        except Exception as e:
            logger.debug(f"Binance klines failed for {symbol}: {e}")
            return None

    def _fetch_yfinance_closes(self, symbol: str, days: int = 7) -> Optional[List[float]]:
        """Fetch daily closing prices from Yahoo Finance as fallback."""
        try:
            from market_data.yfinance_client import _normalize_symbol
            import yfinance as yf

            yf_symbol = _normalize_symbol(symbol)
            ticker = yf.Ticker(yf_symbol)
            hist = ticker.history(period=f"{days + 3}d", interval="1d")

            if hist.empty or len(hist) < 2:
                return None

            closes = [float(c) for c in hist["Close"].values[-(days + 1):]]
            return closes
        except Exception as e:
            logger.debug(f"yfinance failed for {symbol}: {e}")
            return None

    def _get_real_prices(self, symbol: str, days: int = 7) -> Optional[List[float]]:
        """
        Get real closing prices for a symbol.
        Tries Binance first, then yfinance. Results cached for 5 minutes.
        Returns list of daily closing prices (oldest first), or None.
        """
        # Check cache
        cached = self._price_cache.get(symbol)
        if cached and (time.time() - cached["fetched_at"]) < self._price_cache_ttl:
            return cached["prices"]

        # Try Binance (works for USDC crypto pairs)
        prices = self._fetch_binance_klines(symbol, days)

        # Fallback to yfinance (works for stocks, metals, forex, and crypto via -USD pairs)
        if prices is None:
            prices = self._fetch_yfinance_closes(symbol, days)

        if prices and len(prices) >= 2:
            self._price_cache[symbol] = {
                "prices": prices,
                "fetched_at": time.time(),
            }
            return prices

        return None

    def _calculate_features(self, prices: List[float]) -> np.ndarray:
        """Calculate features from price history"""
        if len(prices) < 7:
            return np.zeros(8)
        
        hist_prices = np.array(prices[-7:])
        current_price = prices[-1]
        
        sma_7 = np.mean(hist_prices)
        sma_3 = np.mean(hist_prices[-3:])
        volatility = np.std(hist_prices)
        momentum = (hist_prices[-1] - hist_prices[0]) / hist_prices[0] if hist_prices[0] > 0 else 0
        
        price_lag_1 = hist_prices[-1] if len(hist_prices) >= 1 else current_price
        price_lag_2 = hist_prices[-2] if len(hist_prices) >= 2 else current_price
        price_lag_3 = hist_prices[-3] if len(hist_prices) >= 3 else current_price
        
        features = np.array([
            current_price,
            sma_7,
            sma_3,
            volatility,
            momentum,
            price_lag_1,
            price_lag_2,
            price_lag_3
        ])
        
        return features
    
    def _predict_xgboost(self, symbol: str, current_price: float):
        """
        Run prediction using XGBoost model with full feature engineering.
        Returns (predicted_price, trend_score, confidence).
        """
        from ml.auto_trainer import fetch_binance_ohlcv, fetch_yfinance_ohlcv, engineer_features, YFINANCE_SYMBOL_MAP

        # Fetch recent data — yfinance for non-crypto, Binance for crypto
        if symbol in YFINANCE_SYMBOL_MAP:
            df = fetch_yfinance_ohlcv(symbol, days=250)
        else:
            df = fetch_binance_ohlcv(symbol, interval="1d", days=250)
        if df is None or len(df) < 50:
            raise ValueError(f"Insufficient data for XGBoost prediction: {symbol}")

        feat = engineer_features(df)
        if feat.empty:
            raise ValueError(f"Feature engineering produced no rows: {symbol}")

        feature_cols = self.model_features[symbol]
        # Use only columns that exist in both the feature set and model
        available = [c for c in feature_cols if c in feat.columns]
        if len(available) < len(feature_cols) * 0.8:
            raise ValueError(f"Too many missing features for {symbol}")

        # Get the last row (most recent day)
        last_row = feat[available].iloc[-1:].values

        scaler = self.scalers[symbol]
        model = self.models[symbol]

        # Pad missing columns with 0 if needed
        if len(available) < len(feature_cols):
            full_row = np.zeros((1, len(feature_cols)))
            for i, col in enumerate(feature_cols):
                if col in available:
                    idx = available.index(col)
                    full_row[0, i] = last_row[0, idx]
            last_row = full_row

        scaled = scaler.transform(last_row)
        predicted_price = float(model.predict(scaled)[0])

        price_change = predicted_price - current_price
        price_change_pct = (price_change / current_price) * 100 if current_price > 0 else 0
        trend_score = float(np.clip(price_change_pct / 5.0, -1, 1))
        confidence = min(95.0, 85.0 + abs(trend_score) * 8)

        return predicted_price, trend_score, confidence

    def get_current_price(self, symbol: str) -> float:
        """Get current price from real market data, fallback to base_price."""
        if symbol not in self.all_assets:
            return 0.0

        real_prices = self._get_real_prices(symbol, days=1)
        if real_prices:
            return round(real_prices[-1], 8)

        # Fallback to base_price with small variation
        asset = self.all_assets[symbol]
        base_price = asset["base_price"]
        if base_price <= 0:
            return 0.0
        variation = random.uniform(-0.005, 0.005)
        return round(base_price * (1 + variation), 8)
    
    def get_asset_info(self, symbol: str) -> Optional[Dict]:
        """Get asset information"""
        return self.all_assets.get(symbol)
    
    def list_assets(self, asset_type: Optional[AssetType] = None) -> Dict:
        """List all assets, optionally filtered by type"""
        if asset_type:
            filtered = {
                symbol: asset for symbol, asset in self.all_assets.items()
                if asset.get("type") == asset_type
            }
            return {
                "assets": filtered,
                "count": len(filtered),
                "type": asset_type.value
            }
        
        return {
            "assets": self.all_assets,
            "count": len(self.all_assets),
            "by_type": {
                "precious_metals": len(self.precious_metals),
                "stocks": len(self.stocks),
                "cryptos": len(self.cryptos),
                "derivatives": len(self.derivatives)
            }
        }
    
    def predict_price(self, symbol: str, days: int = 7) -> Dict:
        """
        Predict price for any asset type
        
        Args:
            symbol: Asset symbol
            days: Prediction horizon in days
            
        Returns:
            Prediction with confidence, trend, and price forecast
        """
        if symbol not in self.all_assets:
            return {
                "error": f"Unsupported symbol: {symbol}",
                "symbol": symbol
            }
        
        asset = self.all_assets[symbol]
        current_price = self.get_current_price(symbol)
        
        # Check if we have a trained model for this symbol
        use_ml_model = symbol in self.models and symbol in self.scalers
        
        if use_ml_model:
            try:
                is_xgboost = symbol in self.model_features and len(self.model_features[symbol]) > 10

                if is_xgboost:
                    # XGBoost path: use auto_trainer's feature engineering
                    predicted_price, trend_score, confidence = self._predict_xgboost(symbol, current_price)
                else:
                    # Legacy RF path: 8-feature model
                    real_prices = self._get_real_prices(symbol, days=7)
                    if real_prices and len(real_prices) >= 7:
                        historical_prices = real_prices
                    else:
                        logger.warning(f"[predictor] No real price data for {symbol}, using base_price fallback")
                        historical_prices = []
                        for i in range(7):
                            variation = random.uniform(-0.02, 0.02)
                            hist_price = asset["base_price"] * (1 + variation)
                            historical_prices.append(hist_price)
                        historical_prices.append(current_price)

                    features = self._calculate_features(historical_prices)
                    features = features.reshape(1, -1)
                    scaler = self.scalers[symbol]
                    features_scaled = scaler.transform(features)
                    model = self.models[symbol]
                    predicted_price = model.predict(features_scaled)[0]

                    price_change = predicted_price - current_price
                    price_change_pct = (price_change / current_price) * 100 if current_price > 0 else 0
                    trend_score = np.clip(price_change_pct / 5.0, -1, 1)
                    base_confidence = 88.8
                    confidence = min(95, base_confidence + abs(trend_score) * 5)

                daily_change = trend_score * 0.005

            except Exception as e:
                print(f"[-] Error using ML model for {symbol}: {e}")
                use_ml_model = False
        
        if not use_ml_model:
            # Fallback: Simulate prediction
            trend_score = random.uniform(-1, 1)
            daily_change = trend_score * 0.005
            predicted_price = current_price * (1 + daily_change * days)
            confidence = min(85, 65 + abs(trend_score) * 20)
            price_change = predicted_price - current_price
            price_change_pct = ((predicted_price - current_price) / current_price) * 100 if current_price > 0 else 0
        else:
            price_change = predicted_price - current_price
            price_change_pct = ((predicted_price - current_price) / current_price) * 100 if current_price > 0 else 0
        
        # Generate price path
        price_path = []
        for day in range(days + 1):
            progress = day / days if days > 0 else 0
            day_price = current_price + (predicted_price - current_price) * progress
            noise = random.uniform(-0.005, 0.005)
            day_price *= (1 + noise)
            price_path.append({
                "day": day,
                "price": round(day_price, 2),
                "date": (datetime.now() + timedelta(days=day)).isoformat()
            })
        
        # Determine recommendation
        if price_change_pct > 2:
            recommendation = "BUY"
            recommendation_strength = "STRONG"
        elif price_change_pct > 0.5:
            recommendation = "BUY"
            recommendation_strength = "MODERATE"
        elif price_change_pct < -2:
            recommendation = "SELL"
            recommendation_strength = "STRONG"
        elif price_change_pct < -0.5:
            recommendation = "SELL"
            recommendation_strength = "MODERATE"
        else:
            recommendation = "HOLD"
            recommendation_strength = "NEUTRAL"
        
        prediction = {
            "symbol": symbol,
            "asset_name": asset["name"],
            "asset_type": asset["type"].value,
            "current_price": round(current_price, 2),
            "predicted_price": round(predicted_price, 2),
            "price_change": round(price_change, 2),
            "price_change_percent": round(price_change_pct, 2),
            "trend": "BULLISH" if trend_score > 0.3 else "BEARISH" if trend_score < -0.3 else "SIDEWAYS",
            "trend_score": round(trend_score, 3),
            "confidence": round(confidence, 1),
            "recommendation": recommendation,
            "recommendation_strength": recommendation_strength,
            "prediction_horizon_days": days,
            "price_path": price_path,
            "timestamp": datetime.now().isoformat(),
            "model_version": "v1.0-trained" if use_ml_model else "v1.0-alpha",
            "using_ml_model": use_ml_model
        }
        
        # Store in history
        self.prediction_history[symbol] = prediction

        # Record prediction for accuracy tracking (feedback loop)
        try:
            from services.accuracy_tracker import accuracy_tracker
            predicted_date = datetime.now() + timedelta(days=days)
            accuracy_tracker.record_prediction(
                asset_id=symbol,
                predicted_price=round(predicted_price, 2),
                predicted_date=predicted_date,
                confidence=round(confidence, 1),
            )
        except Exception:
            pass  # don't let tracking failures block predictions

        return prediction
    
    def get_all_predictions(self, days: int = 7, asset_type: Optional[AssetType] = None) -> Dict:
        """Get predictions for all assets or filtered by type"""
        if asset_type:
            symbols = [
                symbol for symbol, asset in self.all_assets.items()
                if asset.get("type") == asset_type
            ]
        else:
            symbols = list(self.all_assets.keys())
        
        predictions = {}
        for symbol in symbols:
            predictions[symbol] = self.predict_price(symbol, days)
        
        return {
            "predictions": predictions,
            "count": len(predictions),
            "asset_type": asset_type.value if asset_type else "all",
            "timestamp": datetime.now().isoformat(),
            "prediction_horizon_days": days
        }
    
    def get_trading_signal(self, symbol: str) -> Dict:
        """Get trading signal for an asset"""
        prediction = self.predict_price(symbol, days=7)
        
        if "error" in prediction:
            return prediction
        
        volatility = abs(prediction["trend_score"]) * 50
        risk_score = max(20, 100 - prediction["confidence"] + volatility)
        
        if prediction["recommendation"] == "BUY" and prediction["recommendation_strength"] == "STRONG":
            position_size = "LARGE"
        elif prediction["recommendation"] == "BUY":
            position_size = "MEDIUM"
        elif prediction["recommendation"] == "SELL":
            position_size = "SMALL"
        else:
            position_size = "NONE"
        
        return {
            "symbol": symbol,
            "asset_name": prediction["asset_name"],
            "asset_type": prediction["asset_type"],
            "signal": prediction["recommendation"],
            "strength": prediction["recommendation_strength"],
            "confidence": prediction["confidence"],
            "risk_score": round(risk_score, 1),
            "position_size": position_size,
            "current_price": prediction["current_price"],
            "target_price": prediction["predicted_price"],
            "expected_return_pct": prediction["price_change_percent"],
            "timestamp": datetime.now().isoformat()
        }
    
    def get_all_signals(self, asset_type: Optional[AssetType] = None) -> Dict:
        """Get trading signals for all assets or filtered by type"""
        if asset_type:
            symbols = [
                symbol for symbol, asset in self.all_assets.items()
                if asset.get("type") == asset_type
            ]
        else:
            symbols = list(self.all_assets.keys())
        
        signals = {}
        for symbol in symbols:
            signals[symbol] = self.get_trading_signal(symbol)
        
        return {
            "signals": signals,
            "count": len(signals),
            "asset_type": asset_type.value if asset_type else "all",
            "timestamp": datetime.now().isoformat()
        }


# Global instance
asset_predictor = AssetPredictor()

