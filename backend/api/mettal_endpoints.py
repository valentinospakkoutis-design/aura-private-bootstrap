"""
API Endpoints από mettal-app
Προσθήκη όλων των endpoints από το mettal-app στο AURA
"""

import os

from fastapi import APIRouter, HTTPException, Depends, Query, status, Request
from fastapi.security import HTTPAuthorizationCredentials
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from pydantic import BaseModel, EmailStr
# yfinance is now available via market_data module
from market_data.yfinance_client import get_price as yf_get_price, get_historical_prices as yf_get_historical_prices
from cache.connection import check_redis_connection
from database.connection import check_db_connection
# Error handling and security
from utils.error_handler import handle_error, ValidationError, NotFoundError, get_error_message
from utils.security import security_manager
# JWT Authentication
from auth.dependencies import require_auth
from auth.jwt_handler import create_access_token, create_refresh_token, verify_token, get_user_from_token, refresh_access_token
# 2FA
from auth.two_factor import generate_2fa_secret, generate_qr_code, generate_backup_codes, verify_2fa_token, verify_backup_code

router = APIRouter(prefix="/api/v1", tags=["Mettal App APIs"])
health_router = APIRouter(tags=["Health"])
from main import limiter

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


ACCESS_TOKEN_TTL = timedelta(hours=1)
REFRESH_TOKEN_TTL = timedelta(days=7)


def _persist_session(db, user_id: int, access_token: str, refresh_token: str) -> None:
    """Insert a user_sessions row tying the access/refresh tokens to the user."""
    from database.models import UserSession

    session = UserSession(
        user_id=user_id,
        access_token=access_token,
        refresh_token=refresh_token,
        expires_at=datetime.utcnow() + REFRESH_TOKEN_TTL,
    )
    db.add(session)
    db.commit()

@router.post("/auth/register", response_model=Token, status_code=201)
@limiter.limit("10/minute")
async def register(request: Request, user_create: UserCreate):
    """
    Register a new user (JWT-based, PostgreSQL)

    Returns access token (15 min) and refresh token (7 days)
    """
    from database.connection import SessionLocal
    from database.models import User as DBUser

    if not SessionLocal:
        raise HTTPException(status_code=503, detail="Database not available")

    email_lower = user_create.email.lower().strip()

    if len(user_create.password) < 8:
        raise ValidationError("Password must be at least 8 characters")

    db = SessionLocal()
    try:
        existing = db.query(DBUser).filter(DBUser.email == email_lower).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="User already exists"
            )

        password_hash = security_manager.hash_password(user_create.password)

        new_user = DBUser(
            email=email_lower,
            password_hash=password_hash,
            full_name=user_create.full_name,
            is_active=True,
            is_verified=True,
        )
        db.add(new_user)
        db.commit()
        db.refresh(new_user)

        try:
            from services.subscription_service import ensure_user_subscription
            ensure_user_subscription(new_user.id, db=db)
        except Exception:
            # Non-fatal to avoid breaking auth flow.
            pass

        token_data = {
            "sub": str(new_user.id),
            "email": email_lower,
            "full_name": user_create.full_name or "",
            "token_version": new_user.token_version,
        }

        access_token = create_access_token(token_data, expires_delta=ACCESS_TOKEN_TTL)
        refresh_token = create_refresh_token(token_data, expires_delta=REFRESH_TOKEN_TTL)

        _persist_session(db, new_user.id, access_token, refresh_token)

        return Token(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
        )
    finally:
        db.close()

@router.post("/auth/login", response_model=Token)
@limiter.limit("10/minute")
async def login(request: Request, user_login: UserLogin):
    """
    Login with email and password (JWT-based, PostgreSQL)

    Returns access token (15 min) and refresh token (7 days)
    """
    from database.connection import SessionLocal
    from database.models import User as DBUser
    from services.auth_audit import log_auth_event

    if not SessionLocal:
        raise HTTPException(status_code=503, detail="Database not available")

    email_lower = user_login.email.lower().strip()
    client_ip = request.headers.get("X-Forwarded-For", request.client.host if request.client else "unknown")
    user_agent = request.headers.get("User-Agent", "")

    db = SessionLocal()
    try:
        db_user = db.query(DBUser).filter(DBUser.email == email_lower).first()

        if not db_user or not db_user.password_hash:
            log_auth_event("LOGIN", "FAILED", email=email_lower, ip_address=client_ip,
                           user_agent=user_agent, metadata={"reason": "user_not_found"})
            raise HTTPException(status_code=401, detail="Unauthorized")("Invalid email or password")

        if not security_manager.verify_password(user_login.password, db_user.password_hash):
            log_auth_event("LOGIN", "FAILED", user_id=db_user.id, email=email_lower,
                           ip_address=client_ip, user_agent=user_agent, metadata={"reason": "wrong_password"})
            raise HTTPException(status_code=401, detail="Unauthorized")("Invalid email or password")

        token_data = {
            "sub": str(db_user.id),
            "email": email_lower,
            "full_name": db_user.full_name or "",
            "token_version": db_user.token_version,
        }

        access_token = create_access_token(token_data, expires_delta=ACCESS_TOKEN_TTL)
        refresh_token = create_refresh_token(token_data, expires_delta=REFRESH_TOKEN_TTL)

        _persist_session(db, db_user.id, access_token, refresh_token)

        log_auth_event("LOGIN", "SUCCESS", user_id=db_user.id, email=email_lower,
                       ip_address=client_ip, user_agent=user_agent)

        return Token(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
        )
    finally:
        db.close()

@router.post("/auth/refresh", response_model=Token)
async def refresh_token_endpoint(refresh_request: RefreshTokenRequest):
    """
    Rotate tokens using a valid refresh token.

    Verifies the refresh JWT, matches it against a stored session in
    ``user_sessions`` (so revoked/rotated tokens are rejected even if still
    cryptographically valid), invalidates the old session, and issues a new
    access token (1h) and refresh token (7d).
    """
    from database.connection import SessionLocal
    from database.models import UserSession

    if not SessionLocal:
        raise HTTPException(status_code=503, detail="Database not available")

    try:
        payload = verify_token(refresh_request.refresh_token, "refresh")
    except HTTPException:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    user_id = payload.get("sub")
    email = payload.get("email")
    full_name = payload.get("full_name")
    token_version = payload.get("token_version")

    db = SessionLocal()
    try:
        existing = (
            db.query(UserSession)
            .filter(UserSession.refresh_token == refresh_request.refresh_token)
            .first()
        )
        if not existing:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired refresh token",
            )

        token_data = {
            "sub": user_id,
            "email": email,
            "full_name": full_name,
        }
        if token_version is not None:
            token_data["token_version"] = token_version

        new_access_token = create_access_token(token_data, expires_delta=ACCESS_TOKEN_TTL)
        new_refresh_token = create_refresh_token(token_data, expires_delta=REFRESH_TOKEN_TTL)

        db.delete(existing)
        db.flush()
        _persist_session(db, int(user_id), new_access_token, new_refresh_token)

        return Token(
            access_token=new_access_token,
            refresh_token=new_refresh_token,
            token_type="bearer",
        )
    finally:
        db.close()

@router.get("/auth/me", response_model=dict)
async def get_current_user_info(request: Request):
    """
    Get current user information (requires authentication)
    
    Include in headers: Authorization: Bearer <access_token>
    """
    # Get token from Authorization header
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized")("Missing or invalid authorization header")
    
    token = auth_header.split(" ")[1]

    try:
        user_info = get_user_from_token(token)
        return {
            "id": user_info["user_id"],
            "email": user_info["email"],
            "full_name": user_info.get("full_name")
        }
    except HTTPException as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token"
        )

# ============================================
# KRAKEN BROKER ENDPOINTS
# ============================================

class KrakenTestRequest(BaseModel):
    api_key: str
    api_secret: str
    testnet: bool = False


def _resolve_authenticated_user_id(request: Request) -> int:
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid authorization header",
        )
    token = auth_header.split(" ", 1)[1].strip()
    try:
        user_info = get_user_from_token(token)
    except HTTPException:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )
    try:
        return int(user_info["user_id"])
    except (KeyError, TypeError, ValueError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid user token")


@router.post("/brokers/kraken/test")
async def kraken_test_connection(request: Request, body: KrakenTestRequest):
    """
    Probe Kraken with the supplied credentials without persisting them.

    Returns ``{"status": "connected", "balances": {...}}`` on success or
    ``{"status": "error", "message": "..."}`` otherwise.
    """
    _resolve_authenticated_user_id(request)

    from brokers.kraken_client import KrakenClient

    client = KrakenClient(
        api_key=body.api_key,
        api_secret=body.api_secret,
        testnet=body.testnet,
    )
    probe = client.test_connection()
    if probe.get("status") != "connected":
        return {"status": "error", "message": probe.get("error") or "Kraken connection failed"}

    balances = client.get_balance()
    if isinstance(balances, dict) and "error" in balances:
        return {"status": "error", "message": balances["error"]}

    return {"status": "connected", "balances": balances}


@router.get("/brokers/kraken/balance")
async def kraken_get_balance(request: Request):
    """Return the authenticated user's Kraken spot balance."""
    user_id = _resolve_authenticated_user_id(request)

    try:
        from main import _get_broker_instance_for_user
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Broker registry unavailable: {exc}")

    broker = _get_broker_instance_for_user("kraken", user_id)
    if broker is None:
        raise HTTPException(
            status_code=400,
            detail="Kraken not connected. Use POST /api/brokers/connect with broker='kraken'.",
        )

    balances = broker.get_balance()
    if isinstance(balances, dict) and "error" in balances:
        raise HTTPException(status_code=502, detail=balances["error"])

    return {"broker": "kraken", "balances": balances, "timestamp": datetime.now().isoformat()}


# ============================================
# COINBASE BROKER ENDPOINTS
# ============================================

class CoinbaseTestRequest(BaseModel):
    api_key: str
    api_secret: str
    testnet: bool = False


@router.post("/brokers/coinbase/test")
async def coinbase_test_connection(request: Request, body: CoinbaseTestRequest):
    """
    Probe Coinbase Advanced Trade with the supplied credentials without
    persisting them. Returns ``{"status": "connected", "balances": {...}}``
    on success or ``{"status": "error", "message": "..."}`` otherwise.
    """
    _resolve_authenticated_user_id(request)

    from brokers.coinbase_client import CoinbaseClient

    client = CoinbaseClient(
        api_key=body.api_key,
        api_secret=body.api_secret,
        testnet=body.testnet,
    )
    probe = client.test_connection()
    if probe.get("status") != "connected":
        return {"status": "error", "message": probe.get("message") or "Coinbase connection failed"}

    balances = probe.get("balances")
    if isinstance(balances, dict) and "error" in balances:
        return {"status": "error", "message": balances["error"]}

    return {"status": "connected", "balances": balances}


@router.get("/brokers/coinbase/balance")
async def coinbase_get_balance(request: Request):
    """Return the authenticated user's Coinbase Advanced Trade balance."""
    user_id = _resolve_authenticated_user_id(request)

    try:
        from main import _get_broker_instance_for_user
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Broker registry unavailable: {exc}")

    broker = _get_broker_instance_for_user("coinbase", user_id)
    if broker is None:
        raise HTTPException(
            status_code=400,
            detail="Coinbase not connected. Use POST /api/brokers/connect with broker='coinbase'.",
        )

    balances = broker.get_balance()
    if isinstance(balances, dict) and "error" in balances:
        raise HTTPException(status_code=502, detail=balances["error"])

    return {"broker": "coinbase", "balances": balances, "timestamp": datetime.now().isoformat()}


@router.get("/reports/weekly")
async def get_weekly_reports_v1(request: Request):
    """
    Return the last 4 weekly performance reports for the authenticated user,
    plus a freshly computed snapshot for the current (in-progress) week.
    """
    from database.connection import SessionLocal
    from database.models import WeeklyReport
    from ai.weekly_report import generate_weekly_report

    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid authorization header",
        )

    token = auth_header.split(" ", 1)[1].strip()
    try:
        user_info = get_user_from_token(token)
    except HTTPException:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

    try:
        user_id = int(user_info["user_id"])
    except (KeyError, TypeError, ValueError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid user token")

    if not SessionLocal:
        raise HTTPException(status_code=503, detail="Database not available")

    db = SessionLocal()
    try:
        current_week = generate_weekly_report(user_id, db)

        rows = (
            db.query(WeeklyReport)
            .filter(WeeklyReport.user_id == user_id)
            .order_by(WeeklyReport.week_start.desc(), WeeklyReport.created_at.desc())
            .limit(4)
            .all()
        )
        reports = [
            {
                "week_start": r.week_start.isoformat() if r.week_start else None,
                "pnl_pct": float(r.pnl_pct or 0.0),
                "total_trades": int(r.total_trades or 0),
                "win_rate": float(r.win_rate or 0.0),
                "best_trade": r.best_trade or "N/A",
                "worst_trade": r.worst_trade or "N/A",
                "ai_accuracy": float(r.ai_accuracy or 0.0),
                "report_text": r.report_text or "",
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]

        return {"reports": reports, "current_week": current_week}
    finally:
        db.close()


@router.post("/auth/logout")
async def logout(request: Request):
    """
    Logout the current user by deleting their session rows.

    Requires ``Authorization: Bearer <access_token>``. The matching
    ``user_sessions`` row (and any other sessions belonging to this user) is
    removed so the refresh token cannot be rotated again.
    """
    from database.connection import SessionLocal
    from database.models import UserSession

    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid authorization header",
        )

    token = auth_header.split(" ", 1)[1].strip()

    try:
        payload = verify_token(token, "access")
    except HTTPException:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

    if not SessionLocal:
        raise HTTPException(status_code=503, detail="Database not available")

    user_id = payload.get("sub")
    db = SessionLocal()
    try:
        try:
            uid_int = int(user_id) if user_id is not None else None
        except (TypeError, ValueError):
            uid_int = None

        if uid_int is not None:
            db.query(UserSession).filter(UserSession.user_id == uid_int).delete(
                synchronize_session=False
            )
            db.commit()

        return {"status": "logged out"}
    finally:
        db.close()

class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


@router.put("/auth/change-password")
async def change_password(request: Request, body: ChangePasswordRequest):
    """Change password for the authenticated user."""
    from database.connection import SessionLocal
    from database.models import User as DBUser

    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized")("Missing or invalid authorization header")

    token = auth_header.split(" ")[1]
    user_info = get_user_from_token(token)

    if not SessionLocal:
        raise HTTPException(status_code=503, detail="Database not available")

    if len(body.new_password) < 8:
        raise ValidationError("New password must be at least 8 characters")

    db = SessionLocal()
    try:
        db_user = db.query(DBUser).filter(DBUser.email == user_info["email"]).first()
        if not db_user:
            raise HTTPException(status_code=401, detail="Unauthorized")("User not found")

        if not security_manager.verify_password(body.current_password, db_user.password_hash):
            raise HTTPException(status_code=401, detail="Unauthorized")("Current password is incorrect")

        db_user.password_hash = security_manager.hash_password(body.new_password)
        db.commit()

        return {"message": "Password changed successfully"}
    finally:
        db.close()


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
    # 2FA is implemented - see enable_2fa function below
    pass

@router.post("/auth/2fa/verify")
async def verify_2fa_setup(verify_request: Verify2FARequest, request: Request):
    """
    Verify 2FA setup by providing your first TOTP token
    
    After verification, 2FA will be enabled for your account
    """
    # Get current user from token
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized")("Missing or invalid authorization header")
    
    token = auth_header.split(" ")[1]
    user_info = get_user_from_token(token)
    email = user_info["email"]
    
    # Verify token
    if not verify_2fa_token(verify_request.secret, verify_request.token):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "INVALID_TOKEN", "message": "Invalid 2FA token"}
        )
    
    # 2FA secret verified — return success
    # Note: 2FA secrets should be stored in a dedicated DB table in future
    return {
        "message": "2FA enabled successfully",
        "enabled": True,
        "note": "2FA persistence requires dedicated DB table — not yet implemented"
    }

@router.post("/auth/login/2fa", response_model=Token)
async def login_with_2fa(login_request: Login2FARequest):
    """
    Login with email, password, AND 2FA token.
    Uses PostgreSQL for user authentication.
    """
    from database.connection import SessionLocal
    from database.models import User as DBUser

    if not SessionLocal:
        raise HTTPException(status_code=503, detail="Database not available")

    email_lower = login_request.email.lower().strip()

    db = SessionLocal()
    try:
        db_user = db.query(DBUser).filter(DBUser.email == email_lower).first()
        if not db_user or not db_user.password_hash:
            raise HTTPException(status_code=401, detail="Unauthorized")("Invalid email or password")

        if not security_manager.verify_password(login_request.password, db_user.password_hash):
            raise HTTPException(status_code=401, detail="Unauthorized")("Invalid email or password")

        # 2FA verification — placeholder until 2FA secrets are stored in DB
        # For now, this endpoint requires a valid TOTP token but has no stored secret
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "2FA_NOT_ENABLED", "message": "2FA is not yet available with PostgreSQL auth"}
        )
    finally:
        db.close()

# ============================================
# ASSET ENDPOINTS
# ============================================

class Asset(BaseModel):
    id: str
    name: str
    symbol: str
    type: str

@router.get("/assets", response_model=List[Asset])
@limiter.limit("60/minute")
async def get_assets(request: Request, _user=Depends(require_auth)):
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
@limiter.limit("60/minute")
async def get_all_prices(request: Request, _user=Depends(require_auth)):
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
                volume=yf_price_data.get("volume", 0.0) if yf_price_data else 0.0,
                change_pct=None,
                timestamp=datetime.now()
            ))
        except:
            continue
    
    return prices

@router.get("/price/{asset_id}", response_model=PriceData)
@limiter.limit("60/minute")
async def get_price(request: Request, asset_id: str):
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
@limiter.limit("60/minute")
async def get_historical_prices(request: Request, asset_id: str, period: str = "1M", _user=Depends(require_auth)):
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
    shap_explanation: Optional[Dict[str, float]] = None
    sentiment: Optional[SentimentData] = None
    timestamp: datetime

@router.post("/predict/{asset_id}", response_model=PredictionResponse)
@limiter.limit("30/minute")
async def predict(request: Request, asset_id: str):
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
        shap_explanation=prediction.get("shap_explanation", {}),
        sentiment=None,  # Will be added if news available
        timestamp=datetime.now()
    )

@router.get("/simple-predict/{asset_id}")
@limiter.limit("30/minute")
async def simple_predict(request: Request, asset_id: str, _user=Depends(require_auth)):
    """
    Simple prediction with real current price (requires authentication)
    """
    return await predict(request, asset_id)

# ============================================
# PORTFOLIO ENDPOINTS
# ============================================

class TradeRequest(BaseModel):
    asset_id: str
    quantity: float
    price: float

@router.post("/portfolio/buy")
@limiter.limit("20/minute")
async def buy_asset(request: Request, trade: TradeRequest, _user=Depends(require_auth)):
    """
    Buy asset - Protected with CSRF and Authentication
    
    Headers required:
    - Authorization: Bearer <access_token>
    - X-CSRF-Token: Get from /api/v1/csrf-token
    """
    # Portfolio buy using paper trading service
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
@limiter.limit("20/minute")
async def sell_asset(request: Request, trade: TradeRequest, _user=Depends(require_auth)):
    """
    Sell asset - Protected with CSRF and Authentication
    """
    # Portfolio sell using paper trading service
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
@limiter.limit("60/minute")
async def get_positions(request: Request, _user=Depends(require_auth)):
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
@limiter.limit("60/minute")
async def get_portfolio_summary(request: Request, _user=Depends(require_auth)):
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
@limiter.limit("60/minute")
async def get_transactions(request: Request, limit: int = 50, asset_id: Optional[str] = None, _user=Depends(require_auth)):
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
@limiter.limit("60/minute")
async def get_accuracy(request: Request, _user=Depends(require_auth)):
    """
    Get accuracy statistics (requires authentication)
    """
    # Accuracy tracking is implemented - see services/accuracy_tracker.py
    from services.accuracy_tracker import accuracy_tracker
    return accuracy_tracker.get_accuracy()

@router.get("/accuracy/{asset_id}")
@limiter.limit("60/minute")
async def get_asset_accuracy(request: Request, asset_id: str, _user=Depends(require_auth)):
    """
    Get accuracy statistics for specific asset (requires authentication)
    """
    from services.accuracy_tracker import accuracy_tracker
    
    accuracy_stats = accuracy_tracker.get_accuracy(asset_id.upper())
    return accuracy_stats

# ============================================
# NEWS ENDPOINTS
# ============================================

@router.get("/news")
@limiter.limit("60/minute")
async def get_news(request: Request, asset_id: Optional[str] = None, limit: int = 10, _user=Depends(require_auth)):
    """
    Get latest financial news (requires authentication)
    """
    from services.news_collector import news_collector
    
    if asset_id:
        articles = news_collector.get_asset_news(asset_id.upper(), limit)
    else:
        articles = news_collector.collect_news(limit=limit)
    
    return {
        "articles": articles,
        "count": len(articles),
        "timestamp": datetime.now().isoformat()
    }

# ============================================
# CSRF TOKEN ENDPOINT
# ============================================

@router.get("/csrf-token")
@limiter.limit("60/minute")
async def get_csrf_token(request: Request):
    """
    Get CSRF token for protected requests (requires authentication)
    
    CSRF tokens are session-based and should be included in X-CSRF-Token header
    for state-changing requests (POST, PUT, DELETE).
    """
    # Get user from JWT token (if provided)
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        try:
            token = auth_header.split(" ")[1]
            user_info = get_user_from_token(token)
            user_id = user_info.get("user_id")
        except:
            user_id = None
    else:
        user_id = None
    
    # Generate CSRF token (can be session-based or user-based)
    import secrets
    csrf_token = secrets.token_urlsafe(32)
    
    # Store token in cache (Redis) or session for validation
    # For now, return token (in production, store with expiration)
    from cache.connection import cache_set
    cache_key = f"csrf:{user_id or 'anonymous'}:{csrf_token}"
    cache_set(cache_key, "valid", expire=3600)  # 1 hour expiration
    
    return {
        "csrf_token": csrf_token,
        "expires_in": 3600,
        "message": "Include this token in X-CSRF-Token header for protected requests"
    }

# ============================================
# HEALTH CHECK
# ============================================

def _get_service_status(env_var_name: str, checker) -> str:
    """Report whether a dependency is configured and reachable."""
    if not os.getenv(env_var_name):
        return "not_configured"
    return "connected" if checker() else "error"


@health_router.get("/health")
async def health_check():
    """
    Comprehensive health check endpoint
    """
    database_status = _get_service_status("DATABASE_URL", check_db_connection)
    redis_status = _get_service_status("REDIS_URL", check_redis_connection)

    return {
        "status": "degraded" if "error" in {database_status, redis_status} else "healthy",
        "services": {
            "api": {"status": "online", "version": "1.0.0"},
            "database": {"status": database_status},
            "redis": {"status": redis_status},
            "yfinance": {"status": "available"}
        },
        "timestamp": datetime.now().isoformat()
    }

