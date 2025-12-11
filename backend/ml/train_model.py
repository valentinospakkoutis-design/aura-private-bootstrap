"""
ML Model Training Script
Εκπαιδεύει μοντέλα για price prediction
"""

import os
import json
import pickle
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
import warnings
warnings.filterwarnings('ignore')


class ModelTrainer:
    """
    Trainer για ML models
    Υποστηρίζει διάφορα model types (RandomForest, GradientBoosting, etc.)
    """
    
    def __init__(self, models_dir: str = "models"):
        """
        Initialize trainer
        
        Args:
            models_dir: Directory για αποθήκευση trained models
        """
        self.models_dir = models_dir
        os.makedirs(models_dir, exist_ok=True)
        self.scalers = {}
        self.training_history = []
    
    def generate_synthetic_data(
        self,
        symbol: str,
        days: int = 365,
        base_price: float = 100.0
    ) -> pd.DataFrame:
        """
        Δημιουργεί synthetic training data
        Στο production, θα φορτώνει real market data από API
        
        Args:
            symbol: Symbol (π.χ. XAUUSDT)
            days: Πόσες ημέρες historical data
            base_price: Base price για το symbol
            
        Returns:
            DataFrame με features και target
        """
        dates = pd.date_range(
            end=datetime.now(),
            periods=days,
            freq='D'
        )
        
        # Generate realistic price data με trends και volatility
        np.random.seed(42)  # For reproducibility
        
        # Trend component
        trend = np.linspace(0, 0.1, days)  # 10% annual trend
        
        # Random walk component
        returns = np.random.normal(0, 0.02, days)  # 2% daily volatility
        
        # Combine
        prices = base_price * (1 + trend + np.cumsum(returns))
        
        # Create features
        data = []
        for i in range(7, len(prices)):  # Need at least 7 days for features
            # Historical prices (last 7 days)
            hist_prices = prices[i-7:i]
            
            # Technical indicators
            sma_7 = np.mean(hist_prices)
            sma_3 = np.mean(hist_prices[-3:])
            volatility = np.std(hist_prices)
            momentum = (hist_prices[-1] - hist_prices[0]) / hist_prices[0]
            
            # Target: price in 7 days
            target = prices[min(i + 7, len(prices) - 1)]
            
            data.append({
                'date': dates[i],
                'price': prices[i],
                'sma_7': sma_7,
                'sma_3': sma_3,
                'volatility': volatility,
                'momentum': momentum,
                'price_lag_1': hist_prices[-1],
                'price_lag_2': hist_prices[-2],
                'price_lag_3': hist_prices[-3],
                'target_price': target,
                'target_change': (target - prices[i]) / prices[i]
            })
        
        df = pd.DataFrame(data)
        return df
    
    def prepare_features(self, df: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray]:
        """
        Προετοιμάζει features για training
        
        Args:
            df: DataFrame με raw data
            
        Returns:
            X (features), y (target)
        """
        # Feature columns
        feature_cols = [
            'price', 'sma_7', 'sma_3', 'volatility', 'momentum',
            'price_lag_1', 'price_lag_2', 'price_lag_3'
        ]
        
        X = df[feature_cols].values
        y = df['target_price'].values
        
        return X, y
    
    def train_model(
        self,
        model_type: str = "random_forest",
        symbol: str = "XAUUSDT",
        base_price: float = 2050.0,
        days: int = 365,
        test_size: float = 0.2,
        **hyperparameters
    ) -> Dict:
        """
        Εκπαιδεύει ένα ML model
        
        Args:
            model_type: Type of model ("random_forest", "gradient_boosting")
            symbol: Symbol για training
            base_price: Base price
            days: Days of training data
            test_size: Test set size (0.0-1.0)
            **hyperparameters: Model hyperparameters
            
        Returns:
            Training results dictionary
        """
        print(f"[*] Starting training for {symbol} with {model_type}...")
        
        # Generate training data
        print("[*] Generating training data...")
        df = self.generate_synthetic_data(symbol, days, base_price)
        print(f"[+] Generated {len(df)} samples")
        
        # Prepare features
        X, y = self.prepare_features(df)
        
        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=test_size, random_state=42
        )
        
        # Scale features
        scaler = StandardScaler()
        X_train_scaled = scaler.fit_transform(X_train)
        X_test_scaled = scaler.transform(X_test)
        
        # Initialize model
        if model_type == "random_forest":
            model = RandomForestRegressor(
                n_estimators=hyperparameters.get('n_estimators', 100),
                max_depth=hyperparameters.get('max_depth', 10),
                min_samples_split=hyperparameters.get('min_samples_split', 5),
                random_state=42,
                n_jobs=-1
            )
        elif model_type == "gradient_boosting":
            model = GradientBoostingRegressor(
                n_estimators=hyperparameters.get('n_estimators', 100),
                max_depth=hyperparameters.get('max_depth', 5),
                learning_rate=hyperparameters.get('learning_rate', 0.1),
                random_state=42
            )
        else:
            raise ValueError(f"Unsupported model type: {model_type}")
        
        # Train model
        print("[*] Training model...")
        model.fit(X_train_scaled, y_train)
        
        # Evaluate
        print("[*] Evaluating model...")
        y_train_pred = model.predict(X_train_scaled)
        y_test_pred = model.predict(X_test_scaled)
        
        train_mae = mean_absolute_error(y_train, y_train_pred)
        test_mae = mean_absolute_error(y_test, y_test_pred)
        train_rmse = np.sqrt(mean_squared_error(y_train, y_train_pred))
        test_rmse = np.sqrt(mean_squared_error(y_test, y_test_pred))
        train_r2 = r2_score(y_train, y_train_pred)
        test_r2 = r2_score(y_test, y_test_pred)
        
        # Calculate accuracy (as percentage of correct direction)
        train_direction_acc = np.mean(
            np.sign(y_train - y_train.mean()) == np.sign(y_train_pred - y_train.mean())
        ) * 100
        test_direction_acc = np.mean(
            np.sign(y_test - y_test.mean()) == np.sign(y_test_pred - y_test.mean())
        ) * 100
        
        # Save model
        model_filename = f"{symbol}_{model_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pkl"
        model_path = os.path.join(self.models_dir, model_filename)
        
        with open(model_path, 'wb') as f:
            pickle.dump({
                'model': model,
                'scaler': scaler,
                'feature_cols': ['price', 'sma_7', 'sma_3', 'volatility', 'momentum',
                                'price_lag_1', 'price_lag_2', 'price_lag_3'],
                'symbol': symbol,
                'model_type': model_type,
                'trained_at': datetime.now().isoformat(),
                'metrics': {
                    'train_mae': float(train_mae),
                    'test_mae': float(test_mae),
                    'train_rmse': float(train_rmse),
                    'test_rmse': float(test_rmse),
                    'train_r2': float(train_r2),
                    'test_r2': float(test_r2),
                    'train_direction_accuracy': float(train_direction_acc),
                    'test_direction_accuracy': float(test_direction_acc)
                }
            }, f)
        
        # Save scaler separately
        scaler_filename = f"{symbol}_{model_type}_scaler.pkl"
        scaler_path = os.path.join(self.models_dir, scaler_filename)
        with open(scaler_path, 'wb') as f:
            pickle.dump(scaler, f)
        
        self.scalers[symbol] = scaler
        
        # Training history
        training_result = {
            'symbol': symbol,
            'model_type': model_type,
            'model_path': model_path,
            'scaler_path': scaler_path,
            'trained_at': datetime.now().isoformat(),
            'training_samples': len(X_train),
            'test_samples': len(X_test),
            'metrics': {
                'train_mae': float(train_mae),
                'test_mae': float(test_mae),
                'train_rmse': float(train_rmse),
                'test_rmse': float(test_rmse),
                'train_r2': float(train_r2),
                'test_r2': float(test_r2),
                'train_direction_accuracy': float(train_direction_acc),
                'test_direction_accuracy': float(test_direction_acc)
            },
            'hyperparameters': hyperparameters
        }
        
        self.training_history.append(training_result)
        
        print(f"[+] Training completed!")
        print(f"[*] Test MAE: {test_mae:.2f}")
        print(f"[*] Test RMSE: {test_rmse:.2f}")
        print(f"[*] Test R²: {test_r2:.3f}")
        print(f"[*] Direction Accuracy: {test_direction_acc:.1f}%")
        print(f"[*] Model saved to: {model_path}")
        
        return training_result
    
    def train_all_metals(
        self,
        model_type: str = "random_forest",
        **hyperparameters
    ) -> Dict:
        """
        Εκπαιδεύει models για όλα τα precious metals
        
        Args:
            model_type: Type of model
            **hyperparameters: Model hyperparameters
            
        Returns:
            Dictionary με results για κάθε metal
        """
        metals = {
            "XAUUSDT": 2050.0,  # Gold
            "XAGUSDT": 24.5,    # Silver
            "XPTUSDT": 950.0,   # Platinum
            "XPDUSDT": 1200.0   # Palladium
        }
        
        results = {}
        for symbol, base_price in metals.items():
            try:
                result = self.train_model(
                    model_type=model_type,
                    symbol=symbol,
                    base_price=base_price,
                    **hyperparameters
                )
                results[symbol] = result
            except Exception as e:
                print(f"[-] Error training {symbol}: {e}")
                results[symbol] = {"error": str(e)}
        
        return {
            "results": results,
            "total_trained": len([r for r in results.values() if "error" not in r]),
            "timestamp": datetime.now().isoformat()
        }
    
    def train_all_assets(
        self,
        model_type: str = "random_forest",
        asset_type: Optional[str] = None,
        **hyperparameters
    ) -> Dict:
        """
        Εκπαιδεύει models για όλα τα assets (metals, stocks, crypto, derivatives)
        
        Args:
            model_type: Type of model
            asset_type: Filter by asset type (precious_metal, stock, crypto, derivative)
            **hyperparameters: Model hyperparameters
            
        Returns:
            Dictionary με results για κάθε asset
        """
        from ai.asset_predictor import asset_predictor
        
        # Get all assets or filtered by type
        if asset_type:
            assets = asset_predictor.list_assets(asset_type)
        else:
            assets = asset_predictor.list_assets()
        
        results = {}
        for symbol, asset_info in assets["assets"].items():
            try:
                base_price = asset_info["base_price"]
                result = self.train_model(
                    model_type=model_type,
                    symbol=symbol,
                    base_price=base_price,
                    **hyperparameters
                )
                results[symbol] = result
            except Exception as e:
                print(f"[-] Error training {symbol}: {e}")
                results[symbol] = {"error": str(e)}
        
        return {
            "results": results,
            "total_trained": len([r for r in results.values() if "error" not in r]),
            "asset_type": asset_type or "all",
            "timestamp": datetime.now().isoformat()
        }
    
    def get_training_history(self) -> List[Dict]:
        """Get training history"""
        return self.training_history
    
    def save_training_history(self, path: str = "training_history.json"):
        """Save training history to JSON"""
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(self.training_history, f, indent=2, ensure_ascii=False)
        print(f"[*] Training history saved to {path}")


def main():
    """Main training function - can be called from command line"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Train ML models for price prediction')
    parser.add_argument('--model', type=str, default='random_forest',
                       choices=['random_forest', 'gradient_boosting'],
                       help='Model type to train')
    parser.add_argument('--symbol', type=str, default=None,
                       help='Symbol to train (if None, trains all assets)')
    parser.add_argument('--asset_type', type=str, default=None,
                       choices=['precious_metal', 'stock', 'crypto', 'derivative'],
                       help='Asset type to train (if None, trains all)')
    parser.add_argument('--days', type=int, default=365,
                       help='Days of training data')
    parser.add_argument('--n_estimators', type=int, default=100,
                       help='Number of estimators')
    parser.add_argument('--max_depth', type=int, default=10,
                       help='Max depth')
    
    args = parser.parse_args()
    
    trainer = ModelTrainer()
    
    hyperparameters = {
        'n_estimators': args.n_estimators,
        'max_depth': args.max_depth
    }
    
    if args.symbol:
        # Train single symbol
        from ai.asset_predictor import asset_predictor
        asset_info = asset_predictor.get_asset_info(args.symbol.upper())
        
        if not asset_info:
            print(f"[-] Error: Symbol {args.symbol} not found")
            return
        
        base_price = asset_info["base_price"]
        
        result = trainer.train_model(
            model_type=args.model,
            symbol=args.symbol.upper(),
            base_price=base_price,
            days=args.days,
            **hyperparameters
        )
        print(json.dumps(result, indent=2))
    else:
        # Train all assets (or filtered by type)
        results = trainer.train_all_assets(
            model_type=args.model,
            asset_type=args.asset_type,
            **hyperparameters
        )
        print(json.dumps(results, indent=2))
    
    # Save training history
    trainer.save_training_history()


if __name__ == "__main__":
    main()

