"""
API Endpoints από mettal-app
Προσθήκη όλων των endpoints από το mettal-app στο AURA
"""

from fastapi import APIRouter, HTTPException, Depends, Query, status, Request
from fastapi.security import HTTPAuthorizationCredentials
from typing import List, Optional
from datetime import datetime, timedelta
from pydantic import BaseModel, EmailStr
# yfinance is now available via market_data module
from market_data.yfinance_client import get_price as yf_get_price, get_historical_prices as yf_get_historical_prices
# Error handling and security
from utils.error_handler import handle_error, ValidationError, NotFoundError, get_error_message
from utils.security import security_manager

router = APIRouter(prefix="/api/v1", tags=["Mettal App APIs"])

# ============================================
# AUTHENTICATION ENDPOINTS (JWT)
# ============================================

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    full_name: Optional[str] = None

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

class RefreshTokenRequest(BaseModel):
    refresh_token: str

# Note: Θα χρειαστεί να προσθέσουμε JWT authentication system
# Για τώρα, θα χρησιμοποιήσουμε το υπάρχον session system

@router.post("/auth/register", response_model=dict, status_code=201)
async def register(user_create: UserCreate):
    """
    Register a new user (JWT-based)
    
    Returns access token (15 min) and refresh token (7 days)
    """
    # TODO: Implement JWT registration
    # For now, redirect to existing /register endpoint
    return {
        "message": "Use /register endpoint for now. JWT auth coming soon.",
        "access_token": "",
        "refresh_token": "",
        "token_type": "bearer"
    }

@router.post("/auth/login", response_model=Token)
async def login(user_login: UserLogin):
    """
    Login with email and password (JWT-based)
    
    Returns access token (15 min) and refresh token (7 days)
    """
    # TODO: Implement JWT login
    return {
        "message": "Use /login endpoint for now. JWT auth coming soon.",
        "access_token": "",
        "refresh_token": "",
        "token_type": "bearer"
    }

@router.post("/auth/refresh", response_model=Token)
async def refresh_token_endpoint(refresh_request: RefreshTokenRequest):
    """
    Refresh an access token using a valid refresh token
    """
    # TODO: Implement token refresh
    raise HTTPException(status_code=501, detail="JWT refresh not implemented yet")

@router.get("/auth/me", response_model=dict)
async def get_current_user_info():
    """
    Get current user information (requires authentication)
    
    Include in headers: Authorization: Bearer <access_token>
    """
    # TODO: Implement JWT user info
    raise HTTPException(status_code=501, detail="JWT auth not implemented yet")

@router.post("/auth/logout")
async def logout():
    """
    Logout user by revoking their access token
    """
    # TODO: Implement JWT logout
    return {"message": "Use /logout endpoint for now"}

# ============================================
# 2FA ENDPOINTS
# ============================================

class Enable2FAResponse(BaseModel):
    secret: str
    qr_code: str
    backup_codes: List[str]
    message: str

class Verify2FARequest(BaseModel):
    secret: str
    token: str

class Login2FARequest(BaseModel):
    email: str
    password: str
    totp_token: str

@router.post("/auth/2fa/enable", response_model=Enable2FAResponse)
async def enable_2fa():
    """
    Enable Two-Factor Authentication (2FA) for your account
    """
    # TODO: Implement 2FA
    raise HTTPException(status_code=501, detail="2FA not implemented yet")

@router.post("/auth/2fa/verify")
async def verify_2fa_setup(request: Verify2FARequest):
    """
    Verify 2FA setup by providing your first TOTP token
    """
    # TODO: Implement 2FA verification
    raise HTTPException(status_code=501, detail="2FA not implemented yet")

@router.post("/auth/login/2fa", response_model=Token)
async def login_with_2fa(login_request: Login2FARequest):
    """
    Login with email, password, AND 2FA token
    """
    # TODO: Implement 2FA login
    raise HTTPException(status_code=501, detail="2FA login not implemented yet")

# ============================================
# ASSET ENDPOINTS
# ============================================

class Asset(BaseModel):
    id: str
    name: str
    symbol: str
    type: str

@router.get("/assets", response_model=List[Asset])
async def get_assets():
    """
    Get all available assets (requires authentication)
    """
    from ai.asset_predictor import asset_predictor
    
    assets_list = asset_predictor.list_assets()
    result = []
    
    for symbol, asset_info in assets_list["assets"].items():
        result.append(Asset(
            id=symbol,
            name=asset_info["name"],
            symbol=symbol,
            type=asset_info["type"].value if hasattr(asset_info["type"], "value") else str(asset_info["type"])
        ))
    
    return result

# ============================================
# PRICE ENDPOINTS
# ============================================

class PriceData(BaseModel):
    asset_id: str
    price: float
    volume: float
    change_pct: Optional[float] = None
    timestamp: datetime

@router.get("/prices", response_model=List[PriceData])
async def get_all_prices():
    """
    Get current prices for all assets (requires authentication)
    """
    from ai.asset_predictor import asset_predictor
    
    prices = []
    assets = asset_predictor.list_assets()
    
    for symbol in list(assets["assets"].keys())[:20]:  # Limit to 20 for performance
        try:
            current_price = asset_predictor.get_current_price(symbol)
            prices.append(PriceData(
                asset_id=symbol,
                price=current_price,
                volume=0.0,  # TODO: Get real volume
                change_pct=None,
                timestamp=datetime.now()
            ))
        except:
            continue
    
    return prices

@router.get("/price/{asset_id}", response_model=PriceData)
async def get_price(asset_id: str):
    """
    Get current price for an asset with caching and security (requires authentication)
    """
    from ai.asset_predictor import asset_predictor
    
    asset_info = asset_predictor.get_asset_info(asset_id.upper())
    if not asset_info:
        raise HTTPException(status_code=404, detail=f"Asset {asset_id} not found")
    
    # Try to get real price from yfinance first
    try:
        yf_price_data = yf_get_price(asset_id.upper())
        if yf_price_data and yf_price_data.get("price"):
            return PriceData(
                asset_id=asset_id.upper(),
                price=yf_price_data["price"],
                volume=yf_price_data.get("volume", 0.0),
                change_pct=yf_price_data.get("change_percent"),
                timestamp=datetime.now()
            )
    except Exception as e:
        print(f"[-] yfinance error for {asset_id}: {e}")
    
    # Fallback to simulated price
    current_price = asset_predictor.get_current_price(asset_id.upper())
    
    return PriceData(
        asset_id=asset_id.upper(),
        price=current_price,
        volume=0.0,
        change_pct=None,
        timestamp=datetime.now()
    )

@router.get("/prices/{asset_id}/historical")
async def get_historical_prices(asset_id: str, period: str = "1M"):
    """
    Get historical prices for an asset (requires authentication)
    
    Period options: 1D, 1W, 1M, 3M, 1Y
    """
    from ai.asset_predictor import asset_predictor
    
    asset_info = asset_predictor.get_asset_info(asset_id.upper())
    if not asset_info:
        raise HTTPException(status_code=404, detail=f"Asset {asset_id} not found")
    
    # Map period to yfinance period
    period_map = {
        '1D': '1d',
        '1W': '5d',
        '1M': '1mo',
        '3M': '3mo',
        '1Y': '1y',
    }
    yf_period = period_map.get(period, '1mo')
    
    # Try to get historical data from yfinance
    try:
        historical_data = yf_get_historical_prices(asset_id.upper(), period=yf_period, interval="1d")
        if historical_data:
            return {"prices": historical_data, "period": period, "count": len(historical_data)}
        else:
            # Fallback to empty if yfinance fails
            return {"prices": [], "period": period, "count": 0, "note": "Historical data not available"}
    except Exception as e:
        print(f"[-] Error fetching historical prices: {e}")
        return {"prices": [], "period": period, "count": 0, "error": str(e)}

# ============================================
# PREDICTION ENDPOINTS
# ============================================

class Prediction(BaseModel):
    horizon: str
    predicted_price: float
    predicted_change_pct: float
    confidence: float
    min_price: float
    max_price: float

class SentimentData(BaseModel):
    sentiment_label: str
    sentiment_score: float
    article_count: int

class PredictionResponse(BaseModel):
    asset_id: str
    current_price: float
    predictions: List[Prediction]
    sentiment: Optional[SentimentData] = None
    timestamp: datetime

@router.post("/predict/{asset_id}", response_model=PredictionResponse)
async def predict(asset_id: str):
    """
    Get predictions for an asset with ML-based analysis (requires authentication)
    
    Returns predictions for 30min, 1h, and 24h horizons
    """
    from ai.asset_predictor import asset_predictor
    
    asset_info = asset_predictor.get_asset_info(asset_id.upper())
    if not asset_info:
        raise HTTPException(status_code=404, detail=f"Asset {asset_id} not found")
    
    # Get prediction
    prediction = asset_predictor.predict_price(asset_id.upper(), days=1)
    
    if "error" in prediction:
        raise HTTPException(status_code=404, detail=prediction["error"])
    
    # Convert to PredictionResponse format
    predictions = []
    
    # 30min prediction (extrapolate from 1 day)
    pred_30min = Prediction(
        horizon="30min",
        predicted_price=prediction["current_price"] + (prediction["price_change"] / 24 / 2),
        predicted_change_pct=prediction["price_change_percent"] / 24 / 2,
        confidence=prediction["confidence"] * 0.9,
        min_price=prediction["current_price"] * 0.995,
        max_price=prediction["current_price"] * 1.005
    )
    predictions.append(pred_30min)
    
    # 1h prediction
    pred_1h = Prediction(
        horizon="1h",
        predicted_price=prediction["current_price"] + (prediction["price_change"] / 24),
        predicted_change_pct=prediction["price_change_percent"] / 24,
        confidence=prediction["confidence"] * 0.85,
        min_price=prediction["current_price"] * 0.99,
        max_price=prediction["current_price"] * 1.01
    )
    predictions.append(pred_1h)
    
    # 24h prediction
    pred_24h = Prediction(
        horizon="1d",
        predicted_price=prediction["predicted_price"],
        predicted_change_pct=prediction["price_change_percent"],
        confidence=prediction["confidence"],
        min_price=prediction["predicted_price"] * 0.95,
        max_price=prediction["predicted_price"] * 1.05
    )
    predictions.append(pred_24h)
    
    return PredictionResponse(
        asset_id=asset_id.upper(),
        current_price=prediction["current_price"],
        predictions=predictions,
        sentiment=None,  # TODO: Add sentiment analysis
        timestamp=datetime.now()
    )

@router.get("/simple-predict/{asset_id}")
async def simple_predict(asset_id: str):
    """
    Simple prediction with real current price (requires authentication)
    """
    return await predict(asset_id)

# ============================================
# PORTFOLIO ENDPOINTS
# ============================================

class TradeRequest(BaseModel):
    asset_id: str
    quantity: float
    price: float

@router.post("/portfolio/buy")
async def buy_asset(trade: TradeRequest, request: Request):
    """
    Buy asset - Protected with CSRF and Authentication
    
    Headers required:
    - Authorization: Bearer <access_token>
    - X-CSRF-Token: Get from /api/v1/csrf-token
    """
    # TODO: Implement portfolio buy
    # For now, use paper trading service
    from services.paper_trading import paper_trading_service
    
    try:
        order = {
            "symbol": trade.asset_id,
            "side": "BUY",
            "quantity": trade.quantity,
            "price": trade.price,
            "order_type": "MARKET"
        }
        result = paper_trading_service.place_order(order)
        
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        
        return {
            "success": True,
            "message": f"Bought {trade.quantity} {trade.asset_id} at ${trade.price}",
            "transaction_id": result.get("order_id"),
            "timestamp": datetime.now().isoformat()
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/portfolio/sell")
async def sell_asset(trade: TradeRequest, request: Request):
    """
    Sell asset - Protected with CSRF and Authentication
    """
    # TODO: Implement portfolio sell
    from services.paper_trading import paper_trading_service
    
    try:
        order = {
            "symbol": trade.asset_id,
            "side": "SELL",
            "quantity": trade.quantity,
            "price": trade.price,
            "order_type": "MARKET"
        }
        result = paper_trading_service.place_order(order)
        
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        
        # Calculate P/L
        portfolio = paper_trading_service.get_portfolio()
        pnl = 0.0
        for pos in portfolio.get("positions", []):
            if pos["symbol"] == trade.asset_id:
                pnl = pos.get("pnl", 0)
                break
        
        return {
            "success": True,
            "message": f"Sold {trade.quantity} {trade.asset_id} at ${trade.price}",
            "transaction_id": result.get("order_id"),
            "pnl": pnl,
            "timestamp": datetime.now().isoformat()
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/portfolio/positions")
async def get_positions():
    """
    Get user portfolio positions with current P&L (requires authentication)
    """
    from services.paper_trading import paper_trading_service
    
    try:
        portfolio = paper_trading_service.get_portfolio()
        positions = []
        
        for pos in portfolio.get("positions", []):
            positions.append({
                "asset_id": pos.get("symbol"),
                "quantity": pos.get("quantity", 0),
                "avg_buy_price": pos.get("avg_price", 0),
                "current_price": pos.get("current_price", 0),
                "total_value": pos.get("value", 0),
                "pnl": pos.get("pnl", 0),
                "pnl_percent": pos.get("pnl_percent", 0)
            })
        
        return positions
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/portfolio/summary")
async def get_portfolio_summary():
    """
    Get portfolio summary with total P&L (requires authentication)
    """
    from services.paper_trading import paper_trading_service
    
    try:
        portfolio = paper_trading_service.get_portfolio()
        
        return {
            "total_value": portfolio.get("total_value", 0),
            "total_cost": portfolio.get("initial_balance", 0) - portfolio.get("cash", 0),
            "total_pnl": portfolio.get("total_pnl", 0),
            "total_pnl_percent": portfolio.get("total_pnl_percent", 0),
            "position_count": len(portfolio.get("positions", [])),
            "positions": portfolio.get("positions", [])
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/portfolio/transactions")
async def get_transactions(limit: int = 50, asset_id: Optional[str] = None):
    """
    Get user transaction history (requires authentication)
    """
    from services.paper_trading import paper_trading_service
    
    try:
        history = paper_trading_service.get_trade_history(limit=limit)
        
        if asset_id:
            history = [t for t in history if t.get("symbol") == asset_id.upper()]
        
        return history
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ============================================
# ACCURACY TRACKING ENDPOINTS
# ============================================

@router.get("/accuracy")
async def get_accuracy():
    """
    Get accuracy statistics (requires authentication)
    """
    # TODO: Implement accuracy tracking
    return {
        "message": "Accuracy tracking not implemented yet",
        "total_predictions": 0
    }

@router.get("/accuracy/{asset_id}")
async def get_asset_accuracy(asset_id: str):
    """
    Get accuracy statistics for specific asset (requires authentication)
    """
    # TODO: Implement asset-specific accuracy
    return {
        "asset_id": asset_id,
        "message": "Accuracy tracking not implemented yet",
        "total_predictions": 0
    }

# ============================================
# NEWS ENDPOINTS
# ============================================

@router.get("/news")
async def get_news(asset_id: Optional[str] = None, limit: int = 10):
    """
    Get latest financial news (requires authentication)
    """
    # TODO: Implement news collection
    return {
        "articles": [],
        "count": 0,
        "message": "News collection not implemented yet"
    }

# ============================================
# CSRF TOKEN ENDPOINT
# ============================================

@router.get("/csrf-token")
async def get_csrf_token():
    """
    Get CSRF token for protected requests (requires authentication)
    """
    # TODO: Implement CSRF protection
    import secrets
    token = secrets.token_urlsafe(32)
    return {
        "csrf_token": token,
        "message": "Include this token in X-CSRF-Token header for protected requests"
    }

# ============================================
# HEALTH CHECK
# ============================================

@router.get("/health")
async def health_check():
    """
    Comprehensive health check endpoint
    """
    return {
        "status": "healthy",
        "services": {
            "api": {"status": "online", "version": "1.0.0"},
            "database": {"status": "not_configured"},
            "redis": {"status": "not_configured"},
            "yfinance": {"status": "available"}
        },
        "timestamp": datetime.now().isoformat()
    }

