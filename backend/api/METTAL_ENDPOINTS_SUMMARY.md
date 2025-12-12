# Mettal-App API Endpoints - Summary

## Επισκόπηση

Όλα τα API endpoints από το mettal-app έχουν προστεθεί στο AURA project.

## Endpoints που Προστέθηκαν

### 1. Authentication (JWT-based)
- `POST /api/v1/auth/register` - Register new user
- `POST /api/v1/auth/login` - Login with email/password
- `POST /api/v1/auth/refresh` - Refresh access token
- `GET /api/v1/auth/me` - Get current user info
- `POST /api/v1/auth/logout` - Logout user

### 2. Two-Factor Authentication (2FA)
- `POST /api/v1/auth/2fa/enable` - Enable 2FA
- `POST /api/v1/auth/2fa/verify` - Verify 2FA setup
- `POST /api/v1/auth/login/2fa` - Login with 2FA
- `POST /api/v1/auth/2fa/disable` - Disable 2FA

### 3. Assets
- `GET /api/v1/assets` - List all available assets
- `GET /api/v1/price/{asset_id}` - Get current price
- `GET /api/v1/prices` - Get all prices
- `GET /api/v1/prices/{asset_id}/historical` - Get historical prices

### 4. Predictions
- `POST /api/v1/predict/{asset_id}` - Get ML predictions (30min, 1h, 24h)
- `GET /api/v1/simple-predict/{asset_id}` - Simple prediction

### 5. Portfolio Management
- `POST /api/v1/portfolio/buy` - Buy asset (CSRF protected)
- `POST /api/v1/portfolio/sell` - Sell asset (CSRF protected)
- `GET /api/v1/portfolio/positions` - Get portfolio positions
- `GET /api/v1/portfolio/summary` - Get portfolio summary
- `GET /api/v1/portfolio/transactions` - Get transaction history

### 6. Accuracy Tracking
- `GET /api/v1/accuracy` - Get accuracy statistics
- `GET /api/v1/accuracy/{asset_id}` - Get asset accuracy

### 7. News
- `GET /api/v1/news` - Get financial news

### 8. Security
- `GET /api/v1/csrf-token` - Get CSRF token

### 9. Health Check
- `GET /api/v1/health` - System health check

## Implementation Status

### ✅ Fully Implemented
- Assets listing
- Price endpoints
- Portfolio endpoints (using paper trading)
- Health check

### ⏳ Partially Implemented
- Predictions (using existing asset_predictor)
- Portfolio (using paper_trading_service)

### 🚧 TODO (Not Yet Implemented)
- JWT Authentication (currently using session-based)
- 2FA (Two-Factor Authentication)
- Token refresh mechanism
- CSRF protection
- Accuracy tracking
- News collection
- Historical prices (real data)

## Integration Notes

1. **Authentication**: Τα endpoints χρησιμοποιούν το υπάρχον session system. JWT auth θα προστεθεί αργότερα.

2. **Portfolio**: Χρησιμοποιεί το `paper_trading_service` για buy/sell operations.

3. **Predictions**: Χρησιμοποιεί το `asset_predictor` για predictions.

4. **Assets**: Χρησιμοποιεί το unified `asset_predictor` με 80 assets.

## Next Steps

1. Implement JWT authentication system
2. Add 2FA support
3. Implement CSRF protection
4. Add accuracy tracking
5. Integrate news collection
6. Add real historical price data

## Files Created

- `backend/api/mettal_endpoints.py` - All mettal-app endpoints
- `backend/api/__init__.py` - API module init
- `backend/api/METTAL_ENDPOINTS_SUMMARY.md` - This file

## Usage

```bash
# Get all assets
GET http://localhost:8000/api/v1/assets

# Get price for asset
GET http://localhost:8000/api/v1/price/BTCUSDT

# Get predictions
POST http://localhost:8000/api/v1/predict/BTCUSDT

# Buy asset
POST http://localhost:8000/api/v1/portfolio/buy
{
  "asset_id": "BTCUSDT",
  "quantity": 0.1,
  "price": 45000.0
}

# Get portfolio
GET http://localhost:8000/api/v1/portfolio/summary
```

## Compatibility

Τα endpoints είναι compatible με το mettal-app API structure, αλλά χρησιμοποιούν το AURA backend infrastructure.

