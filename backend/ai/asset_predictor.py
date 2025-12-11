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
from enum import Enum


class AssetType(str, Enum):
    """Asset types"""
    PRECIOUS_METAL = "precious_metal"
    STOCK = "stock"
    CRYPTO = "crypto"
    DERIVATIVE = "derivative"


class AssetPredictor:
    """
    Unified AI Predictor για όλα τα asset types
    Precious Metals, Stocks, Cryptocurrencies, Derivatives
    """
    
    def __init__(self):
        # Precious Metals
        self.precious_metals = {
            "XAUUSDT": {"name": "Gold", "symbol": "XAU", "base_price": 2050.0, "type": AssetType.PRECIOUS_METAL},
            "XAGUSDT": {"name": "Silver", "symbol": "XAG", "base_price": 24.5, "type": AssetType.PRECIOUS_METAL},
            "XPTUSDT": {"name": "Platinum", "symbol": "XPT", "base_price": 950.0, "type": AssetType.PRECIOUS_METAL},
            "XPDUSDT": {"name": "Palladium", "symbol": "XPD", "base_price": 1200.0, "type": AssetType.PRECIOUS_METAL},
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
        }
        
        # Cryptocurrencies (eToro supports 100+ cryptos, 70+ cryptoassets)
        self.cryptos = {
            # Major Cryptocurrencies (eToro Top)
            "BTCUSDT": {"name": "Bitcoin", "symbol": "BTC", "base_price": 45000.0, "type": AssetType.CRYPTO},
            "ETHUSDT": {"name": "Ethereum", "symbol": "ETH", "base_price": 2500.0, "type": AssetType.CRYPTO},
            "BNBUSDT": {"name": "Binance Coin", "symbol": "BNB", "base_price": 300.0, "type": AssetType.CRYPTO},
            "ADAUSDT": {"name": "Cardano", "symbol": "ADA", "base_price": 0.5, "type": AssetType.CRYPTO},
            "SOLUSDT": {"name": "Solana", "symbol": "SOL", "base_price": 100.0, "type": AssetType.CRYPTO},
            "XRPUSDT": {"name": "Ripple", "symbol": "XRP", "base_price": 0.6, "type": AssetType.CRYPTO},
            "DOTUSDT": {"name": "Polkadot", "symbol": "DOT", "base_price": 7.0, "type": AssetType.CRYPTO},
            "MATICUSDT": {"name": "Polygon", "symbol": "MATIC", "base_price": 0.8, "type": AssetType.CRYPTO},
            "LINKUSDT": {"name": "Chainlink", "symbol": "LINK", "base_price": 15.0, "type": AssetType.CRYPTO},
            "AVAXUSDT": {"name": "Avalanche", "symbol": "AVAX", "base_price": 35.0, "type": AssetType.CRYPTO},
            
            # eToro Popular Cryptos
            "SHIBUSDT": {"name": "Shiba Inu", "symbol": "SHIB", "base_price": 0.000015, "type": AssetType.CRYPTO},
            "DOGEUSDT": {"name": "Dogecoin", "symbol": "DOGE", "base_price": 0.08, "type": AssetType.CRYPTO},
            "TRXUSDT": {"name": "TRON", "symbol": "TRX", "base_price": 0.1, "type": AssetType.CRYPTO},
            "LTCUSDT": {"name": "Litecoin", "symbol": "LTC", "base_price": 70.0, "type": AssetType.CRYPTO},
            "BCHUSDT": {"name": "Bitcoin Cash", "symbol": "BCH", "base_price": 250.0, "type": AssetType.CRYPTO},
            "ETCUSDT": {"name": "Ethereum Classic", "symbol": "ETC", "base_price": 20.0, "type": AssetType.CRYPTO},
            "XLMUSDT": {"name": "Stellar", "symbol": "XLM", "base_price": 0.12, "type": AssetType.CRYPTO},
            "ALGOUSDT": {"name": "Algorand", "symbol": "ALGO", "base_price": 0.2, "type": AssetType.CRYPTO},
            "ATOMUSDT": {"name": "Cosmos", "symbol": "ATOM", "base_price": 10.0, "type": AssetType.CRYPTO},
            "NEARUSDT": {"name": "NEAR Protocol", "symbol": "NEAR", "base_price": 3.0, "type": AssetType.CRYPTO},
            "FTMUSDT": {"name": "Fantom", "symbol": "FTM", "base_price": 0.4, "type": AssetType.CRYPTO},
            "ICPUSDT": {"name": "Internet Computer", "symbol": "ICP", "base_price": 12.0, "type": AssetType.CRYPTO},
            "FILUSDT": {"name": "Filecoin", "symbol": "FIL", "base_price": 5.0, "type": AssetType.CRYPTO},
            "EOSUSDT": {"name": "EOS", "symbol": "EOS", "base_price": 0.7, "type": AssetType.CRYPTO},
            "AAVEUSDT": {"name": "Aave", "symbol": "AAVE", "base_price": 100.0, "type": AssetType.CRYPTO},
            "UNIUSDT": {"name": "Uniswap", "symbol": "UNI", "base_price": 6.0, "type": AssetType.CRYPTO},
            "SANDUSDT": {"name": "The Sandbox", "symbol": "SAND", "base_price": 0.5, "type": AssetType.CRYPTO},
            "MANAUSDT": {"name": "Decentraland", "symbol": "MANA", "base_price": 0.4, "type": AssetType.CRYPTO},
            "AXSUSDT": {"name": "Axie Infinity", "symbol": "AXS", "base_price": 7.0, "type": AssetType.CRYPTO},
            "THETAUSDT": {"name": "Theta Network", "symbol": "THETA", "base_price": 1.0, "type": AssetType.CRYPTO},
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
        
        # Combine all assets
        self.all_assets = {}
        self.all_assets.update(self.precious_metals)
        self.all_assets.update(self.stocks)
        self.all_assets.update(self.cryptos)
        self.all_assets.update(self.derivatives)
        
        self.prediction_history = {}
        
        # Load trained models
        self.models = {}
        self.scalers = {}
        self._load_models()
    
    def _load_models(self):
        """Load trained ML models from disk"""
        models_dir = os.path.join(os.path.dirname(__file__), "..", "models")
        
        if not os.path.exists(models_dir):
            print(f"[!] Models directory not found: {models_dir}")
            return
        
        # Find all model files (exclude scaler files)
        model_files = glob.glob(os.path.join(models_dir, "*_random_forest_*.pkl"))
        model_files = [f for f in model_files if "scaler" not in os.path.basename(f)]
        
        for model_path in model_files:
            try:
                filename = os.path.basename(model_path)
                symbol = filename.split("_")[0]
                
                if symbol in self.models:
                    continue
                
                with open(model_path, 'rb') as f:
                    model_data = pickle.load(f)
                    self.models[symbol] = model_data['model']
                    self.scalers[symbol] = model_data['scaler']
                
                print(f"[+] Loaded model for {symbol}")
            except Exception as e:
                print(f"[-] Error loading model {model_path}: {e}")
    
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
    
    def get_current_price(self, symbol: str) -> float:
        """Get simulated current price with small variations"""
        if symbol not in self.all_assets:
            return 0.0
        
        asset = self.all_assets[symbol]
        base_price = asset["base_price"]
        
        if base_price <= 0:
            return 0.0
        
        # Simulate price movement (±2%)
        variation = random.uniform(-0.02, 0.02)
        price = base_price * (1 + variation)
        
        # Ensure price is never zero or negative
        # For very small prices, use tighter variation
        if base_price < 0.001:
            # For micro prices, use ±1% variation and ensure minimum
            variation = random.uniform(-0.01, 0.01)
            price = base_price * (1 + variation)
            price = max(price, base_price * 0.99)  # Minimum 99% of base
        else:
            # For normal prices, ensure minimum 98% of base
            if price <= 0:
                price = base_price * 0.98
        
        return round(price, 8)  # Round to 8 decimal places for precision
    
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
                # Generate historical prices
                historical_prices = []
                for i in range(7):
                    variation = random.uniform(-0.02, 0.02)
                    hist_price = asset["base_price"] * (1 + variation)
                    historical_prices.append(hist_price)
                historical_prices.append(current_price)
                
                # Calculate features
                features = self._calculate_features(historical_prices)
                features = features.reshape(1, -1)
                
                # Scale features
                scaler = self.scalers[symbol]
                features_scaled = scaler.transform(features)
                
                # Get prediction from model
                model = self.models[symbol]
                predicted_price = model.predict(features_scaled)[0]
                
                # Calculate trend
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

