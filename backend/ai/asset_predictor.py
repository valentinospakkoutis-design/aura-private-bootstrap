"""
Unified Asset Predictor
Υποστηρίζει Precious Metals, Stocks, Cryptocurrencies, και Derivatives
"""

from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import os
import pickle
import glob
import sys
import numpy as np
import pandas as pd
import random
import math
import time
import logging
from enum import Enum

import httpx

logger = logging.getLogger(__name__)

try:
    import numpy.core.numeric as _np_core_numeric
    sys.modules.setdefault("numpy._core.numeric", _np_core_numeric)
except Exception:
    pass


class AssetType(str, Enum):
    """Asset types"""
    PRECIOUS_METAL = "precious_metal"
    STOCK = "stock"
    CRYPTO = "crypto"
    DERIVATIVE = "derivative"
    BOND = "bond"
    FX = "fx"
    SENTIMENT = "sentiment"


def get_shap_explanation(model, features_df: pd.DataFrame) -> Dict[str, float]:
    """Return the top 5 SHAP feature contributions for a tree-based model."""
    try:
        import shap

        explainer = shap.TreeExplainer(model)
        shap_values = explainer.shap_values(features_df)

        if isinstance(shap_values, list):
            shap_values = shap_values[-1]

        shap_array = np.asarray(shap_values)
        if shap_array.ndim == 3:
            shap_array = shap_array[0]
        if shap_array.ndim == 2:
            shap_row = shap_array[0]
        elif shap_array.ndim == 1:
            shap_row = shap_array
        else:
            return {}

        contributions = []
        for feature_name, shap_value in zip(features_df.columns.tolist(), shap_row.tolist()):
            try:
                numeric_value = float(shap_value)
            except Exception:
                continue
            contributions.append((feature_name, numeric_value))

        contributions.sort(key=lambda item: abs(item[1]), reverse=True)
        return {name: round(value, 6) for name, value in contributions[:5]}
    except Exception as e:
        logger.debug(f"SHAP explanation failed: {e}")
        return {}


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
        self.ensemble_models: Dict[str, Dict[str, Any]] = {}
        self.lstm_symbols_loaded = set()
        self._load_models()
    
    def _load_models(self):
        """Load trained ML models from disk (XGBoost preferred, Random Forest fallback)."""
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

        # 3) Optional enhanced ensemble artifacts (XGBoost + RF sidecar)
        ensemble_files = glob.glob(os.path.join(models_dir, "*_ensemble_latest.pkl"))
        for model_path in ensemble_files:
            try:
                filename = os.path.basename(model_path)
                symbol = filename.split("_ensemble")[0]
                with open(model_path, "rb") as f:
                    self.ensemble_models[symbol] = pickle.load(f)
                print(f"[+] Loaded enhanced ensemble sidecar for {symbol}")
            except Exception as e:
                print(f"[-] Error loading enhanced ensemble {model_path}: {e}")

        # 4) Optional LSTM sidecars
        try:
            from ml.lstm_model import load_all_lstm_models

            self.lstm_symbols_loaded = set(load_all_lstm_models().keys())
        except Exception as e:
            logger.debug(f"LSTM preload skipped: {e}")
    
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
    
    def _predict_xgboost(self, symbol: str, current_price: float, recent_df: Optional[pd.DataFrame] = None):
        """
        Run prediction using XGBoost model with full feature engineering.
        Returns (predicted_price, trend_score, confidence).
        """
        from ml.auto_trainer import fetch_binance_ohlcv, fetch_yfinance_ohlcv, engineer_features, YFINANCE_SYMBOL_MAP

        # Fetch recent data — yfinance for non-crypto, Binance for crypto
        if recent_df is not None:
            df = recent_df
        elif symbol in YFINANCE_SYMBOL_MAP:
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
        scaled_df = pd.DataFrame(scaled, columns=feature_cols)
        predicted_price = float(model.predict(scaled)[0])
        shap_explanation = get_shap_explanation(model, scaled_df)

        price_change = predicted_price - current_price
        price_change_pct = (price_change / current_price) * 100 if current_price > 0 else 0
        trend_score = float(np.clip(price_change_pct / 5.0, -1, 1))
        confidence = min(95.0, 85.0 + abs(trend_score) * 8)

        return predicted_price, trend_score, confidence, shap_explanation

    def _get_recent_ohlcv(self, symbol: str, days: int = 250) -> Optional[pd.DataFrame]:
        from ml.auto_trainer import fetch_binance_ohlcv, fetch_yfinance_ohlcv, YFINANCE_SYMBOL_MAP

        if symbol in YFINANCE_SYMBOL_MAP:
            return fetch_yfinance_ohlcv(symbol, days=days)
        return fetch_binance_ohlcv(symbol, interval="1d", days=days)

    def _predict_rf_sidecar(self, symbol: str, recent_df: Optional[pd.DataFrame]) -> Optional[float]:
        if symbol not in self.ensemble_models or recent_df is None or recent_df.empty:
            return None

        try:
            from ml.auto_trainer import engineer_features

            bundle = self.ensemble_models[symbol]
            feature_cols = bundle.get("feature_cols", [])
            rf_model = bundle.get("rf_model")
            scaler = bundle.get("scaler")
            if not feature_cols or rf_model is None or scaler is None:
                return None

            feat = engineer_features(recent_df)
            if feat.empty:
                return None

            available = [c for c in feature_cols if c in feat.columns]
            if not available:
                return None

            row = feat[available].iloc[-1:].values
            if len(available) < len(feature_cols):
                full_row = np.zeros((1, len(feature_cols)))
                for i, col in enumerate(feature_cols):
                    if col in available:
                        idx = available.index(col)
                        full_row[0, i] = row[0, idx]
                row = full_row

            scaled = scaler.transform(row)
            if hasattr(rf_model, "predict_proba"):
                prob = float(rf_model.predict_proba(scaled)[0][1])
            else:
                pred = float(rf_model.predict(scaled)[0])
                prob = max(0.0, min(1.0, pred))
            return max(0.0, min(1.0, prob))
        except Exception as e:
            logger.debug(f"RF sidecar failed for {symbol}: {e}")
            return None

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
        
        mtf: Dict[str, Any] = {}
        onchain: Optional[Dict[str, Any]] = None
        shap_explanation: Dict[str, float] = {}
        ensemble = {
            "xgboost": None,
            "random_forest": None,
            "lstm": None,
            "method": "2-model",
        }

        if use_ml_model:
            try:
                is_xgboost = symbol in self.model_features and len(self.model_features[symbol]) > 10
                recent_df = self._get_recent_ohlcv(symbol, days=250) if is_xgboost else None

                if is_xgboost:
                    # XGBoost path: use auto_trainer's feature engineering
                    predicted_price, trend_score, confidence, shap_explanation = self._predict_xgboost(
                        symbol,
                        current_price,
                        recent_df=recent_df,
                    )

                    xgb_prob = max(0.0, min(1.0, confidence / 100.0))
                    rf_prob = self._predict_rf_sidecar(symbol, recent_df)
                    lstm_prob = None

                    if symbol in self.all_assets and self.all_assets[symbol].get("type") == AssetType.CRYPTO:
                        try:
                            from ml.lstm_model import LSTM_SYMBOLS, predict_lstm

                            if symbol in LSTM_SYMBOLS and recent_df is not None:
                                lstm_prob = predict_lstm(symbol, recent_df)
                        except Exception as e:
                            logger.debug(f"LSTM prediction failed for {symbol}: {e}")

                    ensemble["xgboost"] = round(xgb_prob, 4)
                    ensemble["random_forest"] = round(rf_prob, 4) if rf_prob is not None else None
                    ensemble["lstm"] = round(lstm_prob, 4) if lstm_prob is not None else None

                    if symbol in self.all_assets and self.all_assets[symbol].get("type") == AssetType.CRYPTO:
                        if rf_prob is not None and lstm_prob is not None:
                            final_prob = xgb_prob * 0.50 + rf_prob * 0.30 + lstm_prob * 0.20
                            ensemble["method"] = "3-model"
                        elif lstm_prob is not None:
                            final_prob = xgb_prob * 0.80 + lstm_prob * 0.20
                            ensemble["method"] = "2-model"
                        else:
                            final_prob = xgb_prob
                            ensemble["method"] = "2-model"

                        confidence = max(0.0, min(100.0, final_prob * 100.0))

                    # Multi-timeframe runtime layer (no model retraining, additive only)
                    try:
                        from ml.auto_trainer import fetch_mtf_features

                        is_crypto = asset.get("type") == AssetType.CRYPTO
                        mtf = fetch_mtf_features(symbol, is_crypto=is_crypto)

                        if mtf:
                            if mtf.get("mtf_confluence") and mtf.get("trend_1h", 0) > 0:
                                confidence = min(confidence + 8.0, 100.0)
                            elif not mtf.get("mtf_confluence"):
                                confidence = max(confidence - 12.0, 0.0)
                    except Exception as e:
                        logger.debug(f"MTF layer failed for {symbol}: {e}")
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
                    feature_names = [
                        "current_price",
                        "sma_7",
                        "sma_3",
                        "volatility",
                        "momentum",
                        "price_lag_1",
                        "price_lag_2",
                        "price_lag_3",
                    ]
                    shap_features_df = pd.DataFrame(features_scaled, columns=feature_names)
                    shap_explanation = get_shap_explanation(model, shap_features_df)

                    price_change = predicted_price - current_price
                    price_change_pct = (price_change / current_price) * 100 if current_price > 0 else 0
                    trend_score = np.clip(price_change_pct / 5.0, -1, 1)
                    base_confidence = 88.8
                    confidence = min(95, base_confidence + abs(trend_score) * 5)
                    ensemble["random_forest"] = round(max(0.0, min(1.0, confidence / 100.0)), 4)

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

        # Overbought/oversold filter from 1h RSI (runtime override)
        if mtf:
            rsi_1h = float(mtf.get("rsi_1h", 50.0))
            if rsi_1h > 75 or rsi_1h < 25:
                recommendation = "HOLD"
                recommendation_strength = "NEUTRAL"

        # On-chain runtime layer (crypto only, additive only)
        if asset.get("type") == AssetType.CRYPTO:
            try:
                from services.onchain_service import get_onchain_signals, is_onchain_supported

                if is_onchain_supported(symbol):
                    onchain = get_onchain_signals(symbol)
                    score = float(onchain.get("onchain_score", 0.5) or 0.5)

                    if score >= 0.75:
                        confidence = min(confidence + 5.0, 100.0)
                    elif score <= 0.25:
                        confidence = max(confidence - 10.0, 0.0)

                    if onchain.get("extreme_fear"):
                        if recommendation == "BUY" and confidence < 92.0:
                            recommendation = "HOLD"
                            recommendation_strength = "NEUTRAL"

                    if onchain.get("overleveraged_longs") and recommendation == "BUY":
                        confidence = max(confidence - 8.0, 0.0)
            except Exception as e:
                logger.debug(f"On-chain layer failed for {symbol}: {e}")

        def _trend_label(value: Any) -> str:
            try:
                v = float(value)
            except Exception:
                return "neutral"
            if v > 0:
                return "bullish"
            if v < 0:
                return "bearish"
            return "neutral"
        
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
            "mtf_confluence": bool(mtf.get("mtf_confluence")) if mtf else None,
            "trend_1h": _trend_label(mtf.get("trend_1h")) if mtf else None,
            "trend_4h": _trend_label(mtf.get("trend_4h")) if mtf else None,
            "rsi_1h": round(float(mtf.get("rsi_1h", 50.0)), 1) if mtf else None,
            "prediction_horizon_days": days,
            "price_path": price_path,
            "ensemble": ensemble,
            "shap_explanation": shap_explanation,
            "onchain": {
                "score": round(float(onchain.get("onchain_score", 0.5)), 3),
                "sentiment": onchain.get("onchain_sentiment", "neutral"),
                "funding_rate": onchain.get("funding_rate"),
                "open_interest": onchain.get("open_interest"),
                "long_short_ratio": onchain.get("long_short_ratio"),
                "fear_greed": onchain.get("fear_greed"),
            } if onchain else None,
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

