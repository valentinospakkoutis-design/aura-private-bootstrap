# Unified Asset Predictor - Documentation

## Επισκόπηση

Το `asset_predictor.py` είναι ένα unified AI predictor που υποστηρίζει **όλα τα asset types**:
- **Precious Metals** (4 assets)
- **Stocks** (10 assets)
- **Cryptocurrencies** (10 assets)
- **Derivatives** (6 assets)

**Σύνολο: 30 assets**

## Supported Assets

### Precious Metals (4)
- XAUUSDT (Gold)
- XAGUSDT (Silver)
- XPTUSDT (Platinum)
- XPDUSDT (Palladium)

### Stocks (10)
- AAPL (Apple)
- MSFT (Microsoft)
- GOOGL (Alphabet)
- AMZN (Amazon)
- TSLA (Tesla)
- META (Meta)
- NVDA (NVIDIA)
- SPY (S&P 500 ETF)
- QQQ (NASDAQ ETF)
- VTI (Total Stock Market ETF)

### Cryptocurrencies (10)
- BTCUSDT (Bitcoin)
- ETHUSDT (Ethereum)
- BNBUSDT (Binance Coin)
- ADAUSDT (Cardano)
- SOLUSDT (Solana)
- XRPUSDT (Ripple)
- DOTUSDT (Polkadot)
- MATICUSDT (Polygon)
- LINKUSDT (Chainlink)
- AVAXUSDT (Avalanche)

### Derivatives (6)
- ES1! (E-mini S&P 500 Futures)
- NQ1! (E-mini NASDAQ-100 Futures)
- YM1! (E-mini Dow Futures)
- GC1! (Gold Futures)
- CL1! (Crude Oil Futures)
- NG1! (Natural Gas Futures)

## API Endpoints

### List All Assets
```bash
GET /api/ai/assets
GET /api/ai/assets?asset_type=stock
GET /api/ai/assets?asset_type=crypto
GET /api/ai/assets?asset_type=precious_metal
GET /api/ai/assets?asset_type=derivative
```

### Get Asset Info
```bash
GET /api/ai/assets/{symbol}
```

### Get Prediction
```bash
GET /api/ai/predict/{symbol}?days=7
```

Examples:
- `GET /api/ai/predict/BTCUSDT?days=7` - Bitcoin prediction
- `GET /api/ai/predict/AAPL?days=7` - Apple stock prediction
- `GET /api/ai/predict/ES1!?days=7` - S&P 500 Futures prediction

### Get All Predictions
```bash
GET /api/ai/predictions?days=7
GET /api/ai/predictions?days=7&asset_type=stock
GET /api/ai/predictions?days=7&asset_type=crypto
```

### Get Trading Signal
```bash
GET /api/ai/signal/{symbol}
```

### Get All Signals
```bash
GET /api/ai/signals
GET /api/ai/signals?asset_type=stock
```

## Python Usage

```python
from ai.asset_predictor import asset_predictor, AssetType

# List all assets
assets = asset_predictor.list_assets()
print(f"Total: {assets['count']} assets")

# List by type
stocks = asset_predictor.list_assets(AssetType.STOCK)
cryptos = asset_predictor.list_assets(AssetType.CRYPTO)

# Get prediction
prediction = asset_predictor.predict_price("BTCUSDT", days=7)
print(f"Bitcoin: {prediction['current_price']} → {prediction['predicted_price']}")

# Get trading signal
signal = asset_predictor.get_trading_signal("AAPL")
print(f"Apple: {signal['signal']} ({signal['strength']})")
```

## Training Models

### Train Single Asset
```bash
cd backend
.\venv\Scripts\python.exe -m ml.train_model --symbol BTCUSDT --days 365
.\venv\Scripts\python.exe -m ml.train_model --symbol AAPL --days 365
```

### Train All Assets by Type
```bash
# Train all stocks
.\venv\Scripts\python.exe -m ml.train_model --asset_type stock --days 365

# Train all cryptos
.\venv\Scripts\python.exe -m ml.train_model --asset_type crypto --days 365

# Train all derivatives
.\venv\Scripts\python.exe -m ml.train_model --asset_type derivative --days 365
```

### Train All Assets
```bash
.\venv\Scripts\python.exe -m ml.train_model --days 365
```

## Response Format

### Prediction Response
```json
{
  "symbol": "BTCUSDT",
  "asset_name": "Bitcoin",
  "asset_type": "crypto",
  "current_price": 45000.0,
  "predicted_price": 46500.0,
  "price_change": 1500.0,
  "price_change_percent": 3.33,
  "trend": "BULLISH",
  "trend_score": 0.66,
  "confidence": 92.5,
  "recommendation": "BUY",
  "recommendation_strength": "STRONG",
  "prediction_horizon_days": 7,
  "price_path": [...],
  "using_ml_model": true,
  "model_version": "v1.0-trained"
}
```

### Trading Signal Response
```json
{
  "symbol": "AAPL",
  "asset_name": "Apple Inc.",
  "asset_type": "stock",
  "signal": "BUY",
  "strength": "STRONG",
  "confidence": 90.0,
  "risk_score": 25.0,
  "position_size": "LARGE",
  "current_price": 180.0,
  "target_price": 185.0,
  "expected_return_pct": 2.78
}
```

## Adding New Assets

To add new assets, edit `backend/ai/asset_predictor.py`:

```python
# Add to stocks
self.stocks["NEWSYMBOL"] = {
    "name": "Company Name",
    "base_price": 100.0,
    "type": AssetType.STOCK,
    "exchange": "NASDAQ"
}

# Add to cryptos
self.cryptos["NEWUSDT"] = {
    "name": "New Coin",
    "symbol": "NEW",
    "base_price": 1.0,
    "type": AssetType.CRYPTO
}
```

## Notes

- Models are automatically loaded if available
- Fallback to simulated predictions if no model exists
- All predictions include confidence scores
- Trading signals include risk assessment
- Support for filtering by asset type

## Legacy Support

Old endpoints still work for backward compatibility:
- `/api/ai/predict/metals/{symbol}`
- `/api/ai/predictions/metals`

These use the old `precious_metals_predictor` for metals only.

