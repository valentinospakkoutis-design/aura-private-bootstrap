# 🧠 AI Endpoints Organization

## 📋 Overview

Comprehensive documentation για όλα τα AI-related endpoints.

---

## 🎯 AI Endpoints Structure

### 1. Predictions (Price Forecasting)

#### Single Asset Prediction
```
GET /api/ai/predict/{symbol}
```
**Parameters:**
- `symbol`: Asset symbol (e.g., `XAUUSDT`, `BTCUSDT`, `AAPL`)
- `days` (query): Prediction horizon (default: 7)

**Response:**
```json
{
  "symbol": "XAUUSDT",
  "current_price": 2050.0,
  "predicted_price": 2100.0,
  "price_change": 50.0,
  "price_change_percent": 2.44,
  "trend": "BULLISH",
  "confidence": 85.5,
  "prediction_date": "2025-12-18",
  "price_path": [
    {"day": 1, "price": 2060.0},
    {"day": 2, "price": 2070.0},
    ...
  ]
}
```

#### All Predictions
```
GET /api/ai/predictions?days=7&asset_type=precious_metal
```
**Query Parameters:**
- `days`: Prediction horizon (default: 7)
- `asset_type`: Filter by type (`precious_metal`, `crypto`, `stock`, `derivative`)

**Response:**
```json
{
  "predictions": {
    "XAUUSDT": { ... },
    "XAGUSDT": { ... },
    ...
  },
  "total_assets": 30,
  "prediction_date": "2025-12-18"
}
```

#### Metals-Specific Predictions
```
GET /api/ai/predict/metals/{symbol}?days=7
GET /api/ai/predictions/metals?days=7
```

---

### 2. Trading Signals

#### Single Asset Signal
```
GET /api/ai/signal/{symbol}
```
**Response:**
```json
{
  "symbol": "XAUUSDT",
  "signal": "BUY",
  "strength": "STRONG",
  "confidence": 92.5,
  "expected_return_pct": 5.2,
  "risk_level": "MEDIUM",
  "timestamp": "2025-12-18T10:00:00Z"
}
```

#### All Signals
```
GET /api/ai/signals?asset_type=precious_metal
```
**Query Parameters:**
- `asset_type`: Filter by type

**Response:**
```json
{
  "signals": {
    "XAUUSDT": { ... },
    "XAGUSDT": { ... },
    ...
  },
  "total_signals": 30,
  "timestamp": "2025-12-18T10:00:00Z"
}
```

---

### 3. Asset Management

#### List All Assets
```
GET /api/ai/assets?asset_type=precious_metal
```
**Query Parameters:**
- `asset_type`: Filter by type

**Response:**
```json
{
  "assets": {
    "XAUUSDT": {
      "name": "Gold",
      "symbol": "XAU",
      "type": "PRECIOUS_METAL",
      "base_price": 2050.0
    },
    ...
  },
  "total_assets": 30,
  "by_type": {
    "precious_metal": 4,
    "crypto": 20,
    "stock": 15,
    "derivative": 8
  }
}
```

#### Get Asset Info
```
GET /api/ai/assets/{symbol}
```
**Response:**
```json
{
  "symbol": "XAUUSDT",
  "name": "Gold",
  "type": "PRECIOUS_METAL",
  "base_price": 2050.0,
  "available": true,
  "supported_exchanges": ["Binance", "eToro"]
}
```

---

### 4. AI Engine Status

#### Engine Status
```
GET /api/ai/status
```
**Response:**
```json
{
  "status": "active",
  "model_version": "v1.0.0",
  "accuracy_estimate": 87.5,
  "last_training": "2025-12-15T00:00:00Z",
  "total_predictions": 1250,
  "average_confidence": 85.2,
  "supported_assets": 30,
  "uptime_seconds": 86400
}
```

---

## 📊 Endpoint Categories

### By Function:
- **Predictions**: `/api/ai/predict*` (3 endpoints)
- **Signals**: `/api/ai/signal*` (2 endpoints)
- **Assets**: `/api/ai/assets*` (2 endpoints)
- **Status**: `/api/ai/status` (1 endpoint)

### By Asset Type:
- **Precious Metals**: `XAUUSDT`, `XAGUSDT`, `XPTUSDT`, `XPDUSDT`
- **Cryptocurrencies**: `BTCUSDT`, `ETHUSDT`, `SOLUSDT`, etc.
- **Stocks**: `AAPL`, `MSFT`, `TSLA`, etc.
- **ETFs**: `SPY`, `QQQ`, `VTI`
- **Derivatives**: `GC1!`, `SI1!`, `ES1!`

---

## 🔧 Usage Examples

### Get Gold Prediction:
```javascript
const response = await fetch('https://api.aura.com/api/ai/predict/XAUUSDT?days=7');
const prediction = await response.json();
```

### Get All Crypto Signals:
```javascript
const response = await fetch('https://api.aura.com/api/ai/signals?asset_type=crypto');
const signals = await response.json();
```

### List Available Assets:
```javascript
const response = await fetch('https://api.aura.com/api/ai/assets');
const assets = await response.json();
```

---

## 📋 Endpoint Summary

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/api/ai/predict/{symbol}` | GET | No | Single asset prediction |
| `/api/ai/predictions` | GET | No | All predictions |
| `/api/ai/predict/metals/{symbol}` | GET | No | Metal-specific prediction |
| `/api/ai/predictions/metals` | GET | No | All metal predictions |
| `/api/ai/signal/{symbol}` | GET | No | Single asset signal |
| `/api/ai/signals` | GET | No | All signals |
| `/api/ai/assets` | GET | No | List all assets |
| `/api/ai/assets/{symbol}` | GET | No | Asset info |
| `/api/ai/status` | GET | No | AI engine status |

**Total: 9 AI endpoints**

---

## 🎯 Best Practices

### 1. Caching
- Predictions: Cache for 5-10 minutes
- Signals: Cache for 1-5 minutes
- Assets: Cache for 1 hour
- Status: Cache for 30 seconds

### 2. Error Handling
- Always check response status
- Handle network errors gracefully
- Provide fallback data when possible

### 3. Performance
- Use appropriate cache TTL
- Batch requests when possible
- Filter by asset_type when needed

---

## 🔍 Testing

### Test All AI Endpoints:
```bash
npm run test:endpoints
```

### Test Specific Endpoint:
```bash
curl https://api.aura.com/api/ai/predict/XAUUSDT?days=7
```

---

**Status**: ✅ AI endpoints documented and organized!

*Made with 💎 in Cyprus*

