from fastapi import FastAPI, HTTPException, Request, Form, WebSocket, Depends, Query, BackgroundTasks
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, EmailStr
from typing import Dict, Optional, List
from datetime import datetime, timedelta
import json
import math
import os
import secrets
import asyncio
from urllib.parse import quote
from brokers.binance import BinanceAPI
from services.paper_trading import paper_trading_service
from ai.precious_metals import precious_metals_predictor
from ai.asset_predictor import asset_predictor, AssetType
from ai.asset_predictor import asset_predictor, AssetType
from services.cms_service import cms_service
from services.voice_briefing import voice_briefing_service
from ml.model_manager import model_manager
from ml.training_prep import training_prep
from services.live_trading import live_trading_service
from services.analytics import analytics_service
from services.scheduler import scheduler_service
from services.notifications import notifications_service
from ml.annotation_api import router as annotation_router

# Database and Cache imports
from database.connection import init_db, check_db_connection, close_db, SessionLocal
from database.models import BrokerCredential
from cache.connection import get_redis, check_redis_connection

# Security and Error Handling
from utils.error_handler import handle_error, AuraError, get_error_message
from utils.rate_limiter import rate_limit_middleware, get_client_identifier
from utils.security import security_manager

def sanitize_floats(obj):
    """Replace NaN/Infinity with None to prevent JSON serialization errors."""
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    if isinstance(obj, dict):
        return {k: sanitize_floats(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [sanitize_floats(i) for i in obj]
    return obj

app = FastAPI(
    title="AURA Backend API",
    description="Backend για το AURA - AI Trading Assistant",
    version="1.0.0"
)

# ── Global exception handler for AuraError ───────────────────────
from starlette.responses import JSONResponse
from utils.error_handler import AuraError

@app.exception_handler(AuraError)
async def aura_error_handler(request: Request, exc: AuraError):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.message, "code": exc.code},
    )

# ── JWT Auth Dependency ──────────────────────────────────────────
_bearer_scheme = HTTPBearer(auto_error=False)

def require_auth(credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme)):
    """Dependency that enforces JWT authentication on protected endpoints."""
    if not credentials:
        raise HTTPException(status_code=401, detail="Missing authorization token")
    try:
        from auth.jwt_handler import verify_token
        payload = verify_token(credentials.credentials, "access")
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    # Token versioning: reject tokens issued before password change / logout-all
    from config.feature_flags import ENABLE_TOKEN_VERSIONING
    if ENABLE_TOKEN_VERSIONING:
        import logging
        _auth_logger = logging.getLogger("aura.auth")

        token_version_in_token = payload.get("token_version")
        if token_version_in_token is None:
            _auth_logger.warning("[AUTH_TOKEN_VERSION_MISSING] JWT has no token_version claim")
            raise HTTPException(status_code=401, detail="Invalid token")

        try:
            uid = int(payload.get("sub", 0))
        except (ValueError, TypeError):
            raise HTTPException(status_code=401, detail="Invalid token")

        try:
            from database.models import User as _User
            db = SessionLocal()
            user = db.query(_User).filter(_User.id == uid).first()
            db.close()
        except Exception:
            _auth_logger.error("[AUTH_TOKEN_VERSION_CHECK_FAILED] DB error during token validation", exc_info=True)
            raise HTTPException(status_code=503, detail="Authentication service unavailable")

        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        if user.token_version != token_version_in_token:
            _auth_logger.warning(f"[AUTH_TOKEN_VERSION_MISMATCH] user={uid} jwt_ver={token_version_in_token} db_ver={user.token_version}")
            raise HTTPException(status_code=401, detail="Token invalidated")

    return payload


@app.get("/healthz")
def healthz():
    return {"ok": True}

@app.get("/api/ping")
def api_ping():
    return {"ok": True}


def _restore_broker_connections():
    """Restore broker connections from database on startup."""
    try:
        db = SessionLocal()
        rows = db.query(BrokerCredential).filter(BrokerCredential.is_active == True).all()
        loaded = 0
        for row in rows:
            try:
                api_key = security_manager.decrypt_api_key(row.encrypted_api_key)
                api_secret = security_manager.decrypt_api_key(row.encrypted_api_secret)
                broker = BinanceAPI(api_key=api_key, api_secret=api_secret, testnet=row.testnet)
                broker.connected = True
                broker_instances[row.broker_name] = broker
                loaded += 1
            except Exception as decrypt_err:
                print(f"[!] Failed to decrypt credentials for {row.broker_name}: {decrypt_err}")
        db.close()
        if loaded:
            print(f"[+] Auto-loaded {loaded} broker(s) from database")
            for name, broker in broker_instances.items():
                if not broker.testnet:
                    print(f"[!] Warning: {name} is in LIVE mode — ensure Railway outbound IP is whitelisted on Binance")
        else:
            print("[*] No active broker credentials found in database")
    except Exception as e:
        print(f"[!] Could not restore broker connections: {e}")


def _seed_default_user():
    """Create seed user only if not exists. Never modifies existing users."""
    try:
        from database.models import User as _User
        import bcrypt

        db = SessionLocal()
        existing = db.query(_User).filter(_User.email == "valentinos.pakkoutis@gmail.com").first()
        if not existing:
            hashed = bcrypt.hashpw(b"Aura2024!", bcrypt.gensalt()).decode("utf-8")
            db.add(_User(
                email="valentinos.pakkoutis@gmail.com",
                password_hash=hashed,
                full_name="Valentinos",
                is_active=True,
                is_verified=True,
            ))
            db.commit()
            print("[+] Seed user created")
        else:
            print(f"[+] Seed user exists (id={existing.id}) — NOT touching password")
        db.close()
    except Exception as e:
        print(f"[!] Seed user error: {e}")


# Startup event - Initialize database and cache
@app.on_event("startup")
async def startup_event():
    """Initialize database and cache on startup"""
    print("[*] Initializing database...")
    try:
        if check_db_connection():
            init_db()
            print("[+] Database initialized")
            _restore_broker_connections()
            # Seed default user right after tables are created
            _seed_default_user()
            print(f"[+] Loaded {_count_db_users()} users from PostgreSQL")
        else:
            print("[!] Database not configured - continuing without database")
    except Exception as e:
        print(f"[!] Database initialization error: {e}")
        print("[!] Continuing without database")

    print("[*] Checking Redis connection...")
    if check_redis_connection():
        print("[+] Redis connected")
    else:
        print("[!] Redis not configured - continuing without cache")

    # Start auto trading engine (disabled by default, runs in background)
    from services.auto_trading_engine import auto_trader as _auto_trader
    if broker_instances:
        _auto_trader.set_broker(next(iter(broker_instances.values())))

    async def _get_predictions_for_auto_trader():
        """Fetch predictions for auto trader loop. Only USDC crypto pairs."""
        from services.auto_trading_engine import ALLOWED_AUTO_TRADE_SYMBOLS
        raw = asset_predictor.get_all_predictions(days=7, asset_type=AssetType.CRYPTO)
        raw_preds = raw.get("predictions", {})
        result = []
        for sym, p in raw_preds.items():
            if "error" in p:
                continue
            if sym not in ALLOWED_AUTO_TRADE_SYMBOLS:
                continue
            conf = p.get("confidence", 0)
            conf = conf / 100.0 if conf > 1 else conf
            result.append({
                "symbol": sym,
                "action": (p.get("recommendation") or "HOLD").lower(),
                "confidence": conf,
                "price": p.get("current_price", 0),
                "targetPrice": p.get("predicted_price", 0),
            })
        return result

    asyncio.create_task(_auto_trader.run(_get_predictions_for_auto_trader))
    print("[+] Auto trading engine initialized (disabled by default)")

    # Train missing models in background (survives ephemeral filesystem wipes)
    async def _train_missing_on_startup():
        """Train any missing XGBoost models, then reload into predictor."""
        try:
            from ml.auto_trainer import train_missing_models
            results = await asyncio.to_thread(train_missing_models)
            if results:
                asset_predictor._load_models()
                trained = len([r for r in results if "metrics" in r])
                print(f"[+] Startup training done: {trained} models trained and loaded")
            else:
                print("[+] All models already present, skipping startup training")
        except Exception as e:
            print(f"[!] Startup training failed: {e}")

    asyncio.create_task(_train_missing_on_startup())
    print("[*] Checking for missing models in background...")

    # Start scheduled jobs (weekly retrain, daily XGBoost, daily predictions)
    try:
        from ml.auto_trainer import setup_weekly_retraining
        setup_weekly_retraining()
        print("[+] Scheduled jobs: weekly retrain (Sun 00:00), daily XGBoost (06:00), daily predictions (06:05)")
    except Exception as e:
        print(f"[!] Failed to setup scheduled jobs: {e}")

# Shutdown event
@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    from services.auto_trading_engine import auto_trader as _auto_trader
    _auto_trader.stop()
    close_db()
    print("[+] Cleanup completed")

# Include annotation router
app.include_router(annotation_router)

# Include mettal-app endpoints
from api.mettal_endpoints import router as mettal_router
app.include_router(mettal_router)
print(f"[+] Loaded mettal endpoints: {len(mettal_router.routes)} routes")

# Templates Configuration
templates_dir = os.path.join(os.path.dirname(__file__), "templates")
templates = Jinja2Templates(directory=templates_dir)

# CORS Configuration
_allowed_origins = os.getenv(
    "CORS_ORIGINS",
    "https://exciting-renewal-production-d251.up.railway.app,https://aura-private-bootstrap-production.up.railway.app,http://localhost:3000,http://localhost:8081,http://localhost:8082,http://localhost:19006"
).split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security Headers Middleware
@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response

# Rate Limiting Middleware
@app.middleware("http")
async def rate_limit_middleware_wrapper(request: Request, call_next):
    """Rate limiting middleware wrapper"""
    try:
        return await rate_limit_middleware(request, call_next)
    except Exception:
        return await call_next(request)

# WebSocket endpoint for real-time price updates
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: str = Query(default=None)):
    """WebSocket endpoint for real-time price updates (requires JWT token)"""
    from starlette.websockets import WebSocketDisconnect, WebSocketState

    # Verify JWT token before accepting connection
    if token:
        try:
            from auth.jwt_handler import verify_token
            verify_token(token, "access")
        except Exception:
            await websocket.close(code=4001, reason="Invalid token")
            return
    # Allow unauthenticated connections for public price data (read-only)

    await websocket.accept()
    print("[+] WebSocket client connected")
    subscribed_assets: list = []
    closed = False

    async def send_prices():
        nonlocal closed
        from services.metals_price_service import get_metal_spot_price, is_metal
        while not closed:
            try:
                assets_to_send = subscribed_assets if subscribed_assets else ["Bitcoin", "Gold"]
                for asset_name in assets_to_send:
                    if closed:
                        return
                    # Find symbol by name or use directly
                    symbol = None
                    for sym, info in asset_predictor.all_assets.items():
                        if info.get("name") == asset_name or sym == asset_name:
                            symbol = sym
                            break
                    # Use real spot price for metals, simulated for others
                    price = 0
                    if symbol and is_metal(symbol):
                        spot = get_metal_spot_price(symbol)
                        if spot:
                            price = spot
                    if not price and symbol:
                        price = asset_predictor.get_current_price(symbol)
                    if price > 0:
                        await websocket.send_json({
                            "type": "price_update",
                            "payload": {
                                "asset": asset_name,
                                "price": price,
                                "change": 0,
                                "changePercentage": 0,
                                "timestamp": datetime.utcnow().isoformat() + "Z"
                            }
                        })
                await asyncio.sleep(5)
            except Exception:
                closed = True
                return

    async def receive_messages():
        nonlocal subscribed_assets, closed
        while not closed:
            try:
                msg = await websocket.receive()
                if msg.get("type") == "websocket.disconnect":
                    closed = True
                    return
                text = msg.get("text")
                if text:
                    import json as _json
                    data = _json.loads(text)
                    msg_type = data.get("type", "")
                    payload = data.get("payload", data)
                    if msg_type == "subscribe_prices":
                        subscribed_assets = payload.get("assets", [])
                        print(f"[ws] Subscribed to: {subscribed_assets}")
                    elif msg_type == "unsubscribe_prices":
                        subscribed_assets = []
            except (WebSocketDisconnect, RuntimeError):
                closed = True
                return
            except Exception:
                continue

    try:
        send_task = asyncio.create_task(send_prices())
        recv_task = asyncio.create_task(receive_messages())
        await asyncio.wait(
            [send_task, recv_task], return_when=asyncio.FIRST_COMPLETED
        )
        for t in [send_task, recv_task]:
            if not t.done():
                t.cancel()
    except Exception as e:
        print(f"[!] WebSocket error: {e}")
    finally:
        print("[+] WebSocket client disconnected")
        if websocket.client_state == WebSocketState.CONNECTED:
            try:
                await websocket.close()
            except Exception:
                pass

# Alias: /ws/prices → same handler as /ws
@app.websocket("/ws/prices")
async def websocket_prices(websocket: WebSocket, token: str = Query(default=None)):
    """Alias WebSocket endpoint for price updates"""
    await websocket_endpoint(websocket, token=token)

# User count from PostgreSQL (logged at startup after DB init)
def _count_db_users() -> int:
    try:
        from database.models import User as _User
        db = SessionLocal()
        count = db.query(_User).count()
        db.close()
        return count
    except Exception:
        return 0

# Session management (in-memory for now, use Redis in production)
sessions = {}  # Format: {session_id: {"email": "...", "expires": datetime}}

def create_session(email: str) -> str:
    """Create a new session and return session ID"""
    session_id = secrets.token_urlsafe(32)
    sessions[session_id] = {
        "email": email,
        "expires": datetime.now() + timedelta(hours=24)
    }
    return session_id

def get_session(session_id: Optional[str]) -> Optional[Dict]:
    """Get session data if valid"""
    if not session_id or session_id not in sessions:
        return None
    session = sessions[session_id]
    if datetime.now() > session["expires"]:
        del sessions[session_id]
        return None
    return session

def delete_session(session_id: str):
    """Delete a session"""
    if session_id in sessions:
        del sessions[session_id]

@app.get("/")
async def root():
    """Root endpoint - API health check"""
    return JSONResponse({"status": "ok", "app": "AURA Trading API", "docs": "/docs"})

@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request):
    """Dashboard page - requires authentication"""
    session_id = request.cookies.get("session_id")
    session = get_session(session_id)
    
    if not session:
        # Not logged in, redirect to login
        return RedirectResponse(url="/?error=" + quote("Παρακαλώ συνδεθείτε"), status_code=303)
    
    email = session["email"]
    from database.models import User as _User
    db = SessionLocal()
    try:
        user = db.query(_User).filter(_User.email == email).first()
        if not user:
            return RedirectResponse(url="/?error=" + quote("Ο χρήστης δεν βρέθηκε"), status_code=303)
        return templates.TemplateResponse(
            "dashboard.html",
            {
                "request": request,
                "user_name": user.full_name or email.split("@")[0],
                "user_email": email
            }
        )
    finally:
        db.close()

@app.get("/logout")
def logout(request: Request):
    """Logout endpoint"""
    session_id = request.cookies.get("session_id")
    if session_id:
        delete_session(session_id)
    
    response = RedirectResponse(url="/?success=" + quote("Αποσυνδεθήκατε επιτυχώς"), status_code=303)
    response.delete_cookie(key="session_id")
    return response

@app.get("/health")
def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "backend": "operational",
        "ai_engine": "standby",
        "database": "ready",
        "timestamp": datetime.now().isoformat()
    }

# Authentication Models
class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class RegisterRequest(BaseModel):
    name: str
    email: EmailStr
    password: str
    confirmPassword: str

@app.post("/login")
async def login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...)
):
    """Login endpoint — reads from PostgreSQL, verifies with bcrypt."""
    import bcrypt
    from database.models import User as _User

    email = email.lower().strip()
    password = password.strip()

    db = SessionLocal()
    try:
        user = db.query(_User).filter(_User.email == email).first()
        if not user or not user.password_hash:
            return RedirectResponse(url=f"/?error={quote('Λάθος email ή κωδικός')}", status_code=303)

        if not bcrypt.checkpw(password.encode("utf-8"), user.password_hash.encode("utf-8")):
            return RedirectResponse(url=f"/?error={quote('Λάθος κωδικός')}", status_code=303)

        session_id = create_session(email)
        response = RedirectResponse(url="/dashboard", status_code=303)
        response.set_cookie(key="session_id", value=session_id, max_age=86400, httponly=True, samesite="lax")
        return response
    finally:
        db.close()


@app.post("/register")
async def register(
    request: Request,
    name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    confirmPassword: str = Form(...)
):
    """Register endpoint — writes to PostgreSQL with bcrypt hash."""
    import bcrypt
    from database.models import User as _User

    email = email.lower().strip()
    name = name.strip()
    password = password.strip()
    confirmPassword = confirmPassword.strip()

    if password != confirmPassword:
        return RedirectResponse(url=f"/?error={quote('Οι κωδικοί δεν ταιριάζουν')}", status_code=303)

    if len(password) < 8:
        return RedirectResponse(url=f"/?error={quote('Ο κωδικός πρέπει να έχει τουλάχιστον 8 χαρακτήρες')}", status_code=303)

    db = SessionLocal()
    try:
        existing = db.query(_User).filter(_User.email == email).first()
        if existing:
            return RedirectResponse(url=f"/?error={quote('Το email χρησιμοποιείται ήδη')}", status_code=303)

        hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        db.add(_User(
            email=email,
            password_hash=hashed,
            full_name=name,
            is_active=True,
            is_verified=True,
        ))
        db.commit()
        return RedirectResponse(url=f"/?success={quote('Επιτυχής εγγραφή! Μπορείτε τώρα να συνδεθείτε')}", status_code=303)
    except Exception:
        db.rollback()
        return RedirectResponse(url=f"/?error={quote('Σφάλμα κατά την εγγραφή')}", status_code=303)
    finally:
        db.close()

@app.get("/api/quote-of-day")
def get_quote_of_day():
    """Επιστρέφει το γνωμικό της ημέρας"""
    # Load quotes from shared folder
    quotes_path = os.path.join(os.path.dirname(__file__), "..", "shared", "quotes.json")
    
    try:
        with open(quotes_path, 'r', encoding='utf-8') as f:
            content = f.read()
            # Remove comments from JSON
            content = '\n'.join(line for line in content.split('\n') if not line.strip().startswith('//'))
            quotes = json.loads(content)
        
        # Get quote based on day of year
        day_of_year = datetime.now().timetuple().tm_yday
        index = day_of_year % len(quotes)
        quote = quotes[index]
        
        return {
            "quote": quote,
            "index": index,
            "total_quotes": len(quotes),
            "date": datetime.now().date().isoformat()
        }
    except Exception as e:
        return {
            "error": str(e),
            "quote": {
                "el": "Η υπομονή είναι το κλειδί του παραδείσου. Και του πλούτου.",
                "en": "Patience is the key to paradise. And to wealth."
            }
        }

@app.get("/api/stats")
def get_stats():
    """Επιστρέφει στατιστικά trading"""
    return {
        "active_trades": 0,
        "today_pl": 0.0,
        "total_trades": 0,
        "roi": 0.0,
        "win_rate": 0.0,
        "last_updated": datetime.now().isoformat()
    }

@app.get("/api/system-status")
def get_system_status():
    """Επιστρέφει κατάσταση συστήματος"""
    return {
        "system": "active",
        "backend": "ready",
        "ai_engine": "standby",
        "trading": "live_mode" if live_trading_service.trading_mode == "live" else "paper_mode",
        "connected_brokers": list(broker_instances.keys()),
        "timestamp": datetime.now().isoformat()
    }

# Broker Integration Models
class BrokerConnection(BaseModel):
    broker: str
    api_key: str
    api_secret: str
    testnet: bool = False

class OrderRequest(BaseModel):
    broker: str
    symbol: str
    side: str  # BUY or SELL
    quantity: float
    order_type: str = "MARKET"

# Broker Management
broker_instances = {}  # Store active broker connections

@app.post("/api/brokers/connect")
async def connect_broker(connection: BrokerConnection, _user=Depends(require_auth)):
    """Συνδέει broker API"""
    print(f"[broker] Connect request: broker={connection.broker}, testnet={connection.testnet}")
    try:
        if connection.broker.lower() == "binance":
            broker = BinanceAPI(
                api_key=connection.api_key,
                api_secret=connection.api_secret,
                testnet=connection.testnet
            )
            print(f"[broker] Testing connection to {'testnet' if connection.testnet else 'LIVE'} Binance...")
            result = await asyncio.to_thread(broker.test_connection)
            print(f"[broker] Connection result: {result.get('status', 'unknown')}")

            if result["status"] == "connected":
                broker_instances[connection.broker.lower()] = broker
                # Persist to database (sync DB in threadpool)
                await asyncio.to_thread(
                    _save_broker_to_db,
                    connection.broker.lower(),
                    connection.api_key,
                    connection.api_secret,
                    connection.testnet
                )
                return {
                    "status": "connected",
                    "broker": connection.broker,
                    "message": "Successfully connected and saved to database",
                    "timestamp": datetime.now().isoformat()
                }
            else:
                print(f"[broker] Connection FAILED: {result}")
                raise HTTPException(status_code=400, detail=result)
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported broker: {connection.broker}")
    except HTTPException:
        raise
    except Exception as e:
        print(f"[broker] Connection ERROR: {type(e).__name__}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def _save_broker_to_db(broker_name: str, api_key: str, api_secret: str, testnet: bool):
    """Save broker credentials to database (sync, runs in threadpool)."""
    db = SessionLocal()
    try:
        enc_key = security_manager.encrypt_api_key(api_key)
        enc_secret = security_manager.encrypt_api_key(api_secret)
        row = db.query(BrokerCredential).filter(
            BrokerCredential.broker_name == broker_name
        ).first()
        if row:
            row.encrypted_api_key = enc_key
            row.encrypted_api_secret = enc_secret
            row.testnet = testnet
            row.is_active = True
            row.updated_at = datetime.utcnow()
        else:
            db.add(BrokerCredential(
                broker_name=broker_name,
                encrypted_api_key=enc_key,
                encrypted_api_secret=enc_secret,
                testnet=testnet,
            ))
        db.commit()
        print(f"[+] Broker credentials saved to database: {broker_name}")
    except Exception as db_err:
        db.rollback()
        print(f"[-] Failed to save broker credentials: {db_err}")
        broker_instances.pop(broker_name, None)
        raise HTTPException(
            status_code=500,
            detail=f"Broker connected but failed to save credentials: {db_err}"
        )
    finally:
        db.close()

@app.get("/api/brokers/status")
def get_broker_status():
    """Επιστρέφει κατάσταση brokers"""
    # Auto-reload from DB if no brokers in memory
    if not broker_instances:
        _restore_broker_connections()

    status = []
    for broker_name, broker in broker_instances.items():
        status.append(broker.get_status())
    return {
        "brokers": status,
        "total_connected": len(broker_instances),
        "timestamp": datetime.now().isoformat()
    }

@app.get("/api/brokers/{broker_name}/balance")
def get_broker_balance(broker_name: str, _user=Depends(require_auth)):
    """Επιστρέφει balance από broker"""
    if broker_name.lower() not in broker_instances:
        raise HTTPException(status_code=404, detail="Broker not connected")
    
    broker = broker_instances[broker_name.lower()]
    return broker.get_account_balance()

@app.get("/api/brokers/{broker_name}/price/{symbol}")
def get_price(broker_name: str, symbol: str):
    """Επιστρέφει τιμή symbol"""
    if broker_name.lower() not in broker_instances:
        raise HTTPException(status_code=404, detail="Broker not connected")
    
    broker = broker_instances[broker_name.lower()]
    return broker.get_market_price(symbol)

@app.get("/api/brokers/{broker_name}/symbols")
def get_supported_symbols(broker_name: str):
    """Επιστρέφει supported symbols"""
    if broker_name.lower() not in broker_instances:
        raise HTTPException(status_code=404, detail="Broker not connected")
    
    broker = broker_instances[broker_name.lower()]
    return {
        "broker": broker_name,
        "symbols": broker.get_supported_symbols(),
        "timestamp": datetime.now().isoformat()
    }

def _parse_binance_error(execution_result: Dict) -> Dict:
    """Parse Binance error codes into structured error responses."""
    code = execution_result.get("code")
    error_msg = execution_result.get("error", "Unknown broker error")
    details = execution_result.get("details", {})

    error_map = {
        -2014: {"type": "invalid_api_key", "message": "Invalid API key. Please reconnect your broker.", "recoverable": True},
        -2015: {"type": "invalid_signature", "message": "Invalid API key/secret or permissions. Please check your credentials.", "recoverable": True},
        -2010: {"type": "insufficient_balance", "message": "Insufficient balance for this order.", "recoverable": False},
        -2011: {"type": "unknown_order", "message": "Order not found or already cancelled.", "recoverable": False},
        -1003: {"type": "rate_limit", "message": "Too many requests. Please wait and try again.", "recoverable": True},
        -1015: {"type": "rate_limit", "message": "Too many orders. Please slow down.", "recoverable": True},
    }

    parsed = error_map.get(code, {"type": "broker_error", "message": error_msg, "recoverable": False})

    # Detect IP restriction from error message
    if "ip" in error_msg.lower() and "restrict" in error_msg.lower():
        parsed = {"type": "ip_restriction", "message": "Your IP is not whitelisted on Binance. Update your API key IP restrictions.", "recoverable": True}

    return {
        "error": parsed["message"],
        "error_type": parsed["type"],
        "binance_code": code,
        "recoverable": parsed["recoverable"],
        "details": details,
    }


@app.post("/api/brokers/order")
def place_order(order: OrderRequest, _user=Depends(require_auth)):
    """Τοποθετεί order σε paper ή live mode"""
    broker_key = order.broker.lower()

    # Auto-reload from DB if broker not in memory
    if broker_key not in broker_instances:
        _restore_broker_connections()

    if broker_key not in broker_instances:
        raise HTTPException(status_code=404, detail="Broker not connected. Please connect via /api/brokers/connect")

    broker = broker_instances[broker_key]

    # Get current market price
    price_info = broker.get_market_price(order.symbol)
    if "error" in price_info:
        raise HTTPException(status_code=400, detail="Failed to get market price")

    price = price_info["price"]

    if live_trading_service.trading_mode == "live":
        balance_info = broker.get_account_balance()
        portfolio_value = balance_info.get("total_balance", 0) or balance_info.get("available_balance", 0)
        current_positions = []
        validation_result = live_trading_service.validate_order(
            symbol=order.symbol,
            side=order.side,
            quantity=order.quantity,
            price=price,
            portfolio_value=portfolio_value,
            current_positions=current_positions
        )

        if not validation_result.get("valid", False):
            raise HTTPException(
                status_code=400,
                detail={
                    "message": "Order validation failed",
                    "errors": validation_result.get("errors", []),
                    "warnings": validation_result.get("warnings", [])
                }
            )

        if not hasattr(broker, "place_live_order"):
            raise HTTPException(
                status_code=400,
                detail=f"Broker {order.broker} does not support live orders"
            )

        execution_result = broker.place_live_order(
            symbol=order.symbol,
            side=order.side,
            quantity=order.quantity,
            order_type=order.order_type
        )

        # Structured error handling for Binance errors
        if "error" in execution_result:
            parsed = _parse_binance_error(execution_result)
            raise HTTPException(status_code=400, detail=parsed)

        result = live_trading_service.execute_live_order(
            broker=order.broker,
            symbol=order.symbol,
            side=order.side,
            quantity=order.quantity,
            order_type=order.order_type,
            validation_result=validation_result,
            execution_result=execution_result
        )
    else:
        # Place order through paper trading service
        order_dict = {
            "symbol": order.symbol,
            "side": order.side,
            "quantity": order.quantity,
            "price": price,
            "order_type": order.order_type
        }
        result = paper_trading_service.place_order(order_dict)

    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    return result

@app.get("/api/trading/portfolio")
def get_trading_portfolio():
    """Επιστρέφει portfolio state"""
    # Get current prices for all positions
    current_prices = {}
    for broker_name, broker in broker_instances.items():
        for symbol in broker.get_supported_symbols():
            try:
                price_info = broker.get_market_price(symbol)
                current_prices[symbol] = price_info["price"]
            except:
                pass
    
    return paper_trading_service.get_portfolio(current_prices)

@app.get("/api/trading/history")
def get_trading_history(limit: int = 50):
    """Επιστρέφει trade history"""
    trades = paper_trading_service.get_trade_history(limit)
    return {
        "trades": trades,
        "total": len(paper_trading_service.trade_history),
        "timestamp": datetime.now().isoformat()
    }

@app.get("/api/trading/positions")
def get_positions():
    """Επιστρέφει open positions"""
    # Get current prices
    current_prices = {}
    for broker_name, broker in broker_instances.items():
        for symbol in broker.get_supported_symbols():
            try:
                price_info = broker.get_market_price(symbol)
                current_prices[symbol] = price_info["price"]
            except:
                pass
    
    portfolio = paper_trading_service.get_portfolio(current_prices)
    
    return {
        "positions": portfolio["positions"],
        "count": len(portfolio["positions"]),
        "timestamp": datetime.now().isoformat()
    }

@app.delete("/api/brokers/{broker_name}/disconnect")
def disconnect_broker(broker_name: str, _user=Depends(require_auth)):
    """Αποσυνδέει broker"""
    if broker_name.lower() in broker_instances:
        del broker_instances[broker_name.lower()]
        # Remove from database
        try:
            db = SessionLocal()
            db.query(BrokerCredential).filter(
                BrokerCredential.broker_name == broker_name.lower()
            ).update({"is_active": False})
            db.commit()
            db.close()
        except Exception as db_err:
            print(f"[!] Could not update broker in DB: {db_err}")
        return {
            "status": "disconnected",
            "broker": broker_name,
            "timestamp": datetime.now().isoformat()
        }
    raise HTTPException(status_code=404, detail="Broker not found")

# Paper Trading Endpoints
@app.get("/api/paper-trading/portfolio")
def get_portfolio():
    """Επιστρέφει portfolio information"""
    # Get current prices from connected brokers
    current_prices = {}
    for broker_name, broker in broker_instances.items():
        symbols = broker.get_supported_symbols()
        for symbol in symbols:
            try:
                price_info = broker.get_market_price(symbol)
                if "price" in price_info:
                    current_prices[symbol] = price_info["price"]
            except:
                pass
    
    return paper_trading_service.get_portfolio(current_prices)

@app.get("/api/paper-trading/history")
def get_trade_history(limit: int = 50):
    """Επιστρέφει trade history"""
    return {
        "trades": paper_trading_service.get_trade_history(limit),
        "total": len(paper_trading_service.trade_history),
        "timestamp": datetime.now().isoformat()
    }

@app.get("/api/paper-trading/statistics")
def get_trading_statistics():
    """Επιστρέφει trading statistics"""
    return paper_trading_service.get_statistics()

class PaperOrderRequest(BaseModel):
    symbol: str
    side: str  # BUY or SELL
    quantity: float

@app.post("/api/trading/order")
async def place_trading_order(order: PaperOrderRequest):
    """Place a paper trading order (fetches price from Binance public API)"""
    import httpx

    symbol = order.symbol.upper()
    side = order.side.upper()
    if side not in ("BUY", "SELL"):
        raise HTTPException(status_code=400, detail="Side must be BUY or SELL")
    if order.quantity <= 0:
        raise HTTPException(status_code=400, detail="Quantity must be positive")

    # Get current price — try connected broker first, then public API
    price = None
    if broker_instances:
        for broker in broker_instances.values():
            try:
                info = broker.get_market_price(symbol)
                if "price" in info:
                    price = info["price"]
                    break
            except Exception:
                pass

    if price is None:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    "https://api.binance.com/api/v3/ticker/price",
                    params={"symbol": symbol}
                )
                resp.raise_for_status()
                price = float(resp.json()["price"])
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Could not fetch price for {symbol}: {e}")

    result = paper_trading_service.place_order({
        "symbol": symbol,
        "side": side,
        "quantity": order.quantity,
        "price": price,
        "order_type": "MARKET",
    })

    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    return result


@app.post("/api/paper-trading/reset")
def reset_paper_trading():
    """Reset paper trading account"""
    paper_trading_service.reset()
    return {
        "status": "reset",
        "message": "Paper trading account reset successfully",
        "timestamp": datetime.now().isoformat()
    }

# AI Engine Endpoints - Unified Asset Predictor
@app.get("/api/ai/predict/{symbol}")
def get_prediction(symbol: str, days: int = 7):
    """Επιστρέφει AI prediction για οποιοδήποτε asset (metals, stocks, crypto, derivatives)"""
    return sanitize_floats(asset_predictor.predict_price(symbol.upper(), days))

@app.get("/api/ai/predictions")
def get_all_predictions(days: int = 7, asset_type: Optional[str] = None):
    """Επιστρέφει predictions για όλα τα assets ή filtered by type"""
    asset_type_enum = None
    if asset_type:
        try:
            asset_type_enum = AssetType(asset_type.lower())
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid asset type: {asset_type}")

    raw = asset_predictor.get_all_predictions(days, asset_type_enum)
    raw_predictions = raw.get("predictions", {})

    # Step 1: Fetch crypto prices from Binance
    live_prices: Dict[str, float] = {}
    try:
        import httpx
        with httpx.Client(timeout=5.0) as client:
            resp = client.get("https://api.binance.com/api/v3/ticker/price")
            if resp.status_code == 200:
                for item in resp.json():
                    live_prices[item["symbol"]] = float(item["price"])
        print(f"[+] Binance: {len(live_prices)} prices loaded")
    except Exception as e:
        print(f"[!] Binance price fetch failed: {e}")

    # Step 2: Override metals with REAL spot prices from Yahoo Finance
    # Binance XAUUSDC is a tokenized product (~$2,000), real gold is ~$3,000+
    from services.metals_price_service import get_all_metals_prices, is_metal
    metals_prices = get_all_metals_prices()
    if metals_prices:
        for metal_sym, spot_price in metals_prices.items():
            old = live_prices.get(metal_sym, 0)
            live_prices[metal_sym] = spot_price
            print(f"[+] {metal_sym}: Binance ${old:.2f} → Spot ${spot_price:.2f}")
    else:
        print("[!] Yahoo Finance metals fetch returned empty — using Binance fallback")

    # Map to frontend Prediction interface
    result = []
    for symbol, p in raw_predictions.items():
        if "error" in p:
            continue
        rec = (p.get("recommendation") or "HOLD").lower()
        confidence_raw = p.get("confidence", 0)
        # Ensure confidence is 0.0-1.0 (backend returns 0-100)
        confidence = confidence_raw / 100.0 if confidence_raw > 1 else confidence_raw

        # Price: metals spot > live Binance > prediction current_price > base_price fallback
        current_price = live_prices.get(symbol) or p.get("current_price") or 0

        # Use the AI trend to compute target, NOT the pre-computed change_pct
        # (change_pct was calculated against simulated base_price which may differ
        #  significantly from the real price, especially for metals)
        trend_score = p.get("trend_score", 0)  # -1 to +1
        daily_change = trend_score * 0.005     # same formula as predict_price
        change_pct = daily_change * days * 100  # convert to percentage over N days
        if current_price > 0:
            target_price = current_price * (1 + change_pct / 100)
        else:
            target_price = p.get("predicted_price") or 0

        trend = p.get("trend", "SIDEWAYS")
        reasoning = (
            f"{p.get('asset_name', symbol)}: {trend} trend, "
            f"{'+' if change_pct >= 0 else ''}{change_pct:.1f}% expected in {days} days. "
            f"Strength: {p.get('recommendation_strength', 'N/A')}."
        )

        # Determine decimal precision based on price magnitude
        price_decimals = 2 if current_price >= 1 else 6

        # Map asset_type to frontend category
        asset_type_val = p.get("asset_type", "")
        category_map = {
            "precious_metal": "metals", "stock": "stocks", "crypto": "crypto",
            "derivative": "derivatives", "bond": "bonds", "fx": "fx", "sentiment": "sentiment",
        }
        category = category_map.get(asset_type_val, "other")

        result.append({
            "id": f"pred_{symbol.lower()}_{int(datetime.now().timestamp())}",
            "asset": p.get("asset_name") or symbol,
            "symbol": symbol,
            "category": category,
            "action": rec,
            "confidence": round(confidence, 3),
            "price": round(current_price, price_decimals),
            "targetPrice": round(target_price, price_decimals),
            "timestamp": p.get("timestamp", datetime.now().isoformat()),
            "reasoning": reasoning,
        })

    print(f"[+] Predictions: {len(result)} items, live prices: {len(live_prices)} symbols from Binance")
    if result:
        sample = result[0]
        print(f"[DEBUG] Sample prediction: asset={sample['asset']}, price={sample['price']}, targetPrice={sample['targetPrice']}")

    # Phase 2: Enrich with read-only sentiment context (no decision changes)
    try:
        from config.feature_flags import ENABLE_SENTIMENT_EXPOSURE
        if ENABLE_SENTIMENT_EXPOSURE:
            from services.sentiment_scheduler import get_cached_sentiment
            for pred in result:
                sym = pred.get("symbol", "")
                sentiment = get_cached_sentiment(sym)
                pred["sentiment"] = {
                    "score": sentiment.get("score", 50.0),
                    "label": sentiment.get("label", "neutral"),
                    "article_count": sentiment.get("article_count", 0),
                }
    except Exception as e:
        print(f"[!] Sentiment enrichment failed (non-fatal): {e}")

    # Phase 3: Shadow mode — log hypothetical adjustments (no real changes)
    try:
        from config.feature_flags import ENABLE_SENTIMENT_SHADOW
        if ENABLE_SENTIMENT_SHADOW:
            from services.sentiment_shadow import run_shadow_on_predictions
            run_shadow_on_predictions(result)
    except Exception as e:
        print(f"[!] Sentiment shadow mode failed (non-fatal): {e}")

    return sanitize_floats(result)

@app.get("/api/v1/market/movers")
def get_market_movers():
    """Top gainers, losers, and volume leaders across all assets."""
    # Use the predictions already computed (they have price + change data)
    all_preds = get_all_predictions(days=1)  # call existing endpoint with 1-day horizon
    if not isinstance(all_preds, list):
        all_preds = []

    # Calculate change_pct for each
    items = []
    for p in all_preds:
        price = p.get("price", 0)
        target = p.get("targetPrice", 0)
        if price > 0:
            change_pct = ((target - price) / price) * 100
        else:
            change_pct = 0
        items.append({
            "symbol": p.get("symbol", p.get("asset", "")),
            "name": p.get("asset", ""),
            "category": p.get("category", "other"),
            "price": price,
            "change_pct": round(change_pct, 2),
            "confidence": p.get("confidence", 0),
        })

    # Sort for movers
    sorted_by_change = sorted(items, key=lambda x: x["change_pct"], reverse=True)
    top_gainers = [x for x in sorted_by_change if x["change_pct"] > 0][:5]
    top_losers = sorted(items, key=lambda x: x["change_pct"])[:5]
    # For volume, use confidence as proxy (higher confidence = more data = more active)
    top_volume = sorted(items, key=lambda x: x["confidence"], reverse=True)[:5]

    return {
        "top_gainers": top_gainers,
        "top_losers": top_losers,
        "top_volume": top_volume,
    }


@app.get("/api/v1/predictions/extended")
def get_extended_predictions(days: int = 7):
    """Extended predictions with yfinance pricing for stocks, bonds, FX, VIX."""
    import yfinance as yf

    EXTENDED_ASSETS = {
        "stocks": ["ASML", "SAP", "MC.PA", "AAPL", "MSFT", "NVDA", "BOC.AT"],
        "bonds": ["^TNX", "^IRX", "^TYX"],
        "derivatives": ["ES=F", "NQ=F", "CL=F", "GC=F"],
        "fx": ["EURUSD=X", "GBPEUR=X"],
        "sentiment": ["^VIX"],
    }

    results = []
    for category, symbols in EXTENDED_ASSETS.items():
        for symbol in symbols:
            try:
                ticker = yf.Ticker(symbol)
                hist = ticker.history(period="5d")
                if hist.empty:
                    continue
                current_price = float(hist["Close"].iloc[-1])

                # Get AI prediction if available
                prediction = asset_predictor.predict_price(symbol, days)
                if "error" not in prediction:
                    trend_score = prediction.get("trend_score", 0)
                    change_pct = trend_score * 0.005 * days * 100
                    predicted_price = current_price * (1 + change_pct / 100)
                    confidence = prediction.get("confidence", 50) / 100.0
                else:
                    change_pct = 0
                    predicted_price = current_price
                    confidence = 0.5

                results.append({
                    "symbol": symbol,
                    "name": asset_predictor.all_assets.get(symbol, {}).get("name", symbol),
                    "category": category,
                    "current_price": round(current_price, 4),
                    "predicted_price": round(predicted_price, 4),
                    "change_pct": round(change_pct, 2),
                    "direction": "up" if change_pct > 0 else "down" if change_pct < 0 else "flat",
                    "confidence": round(confidence, 3),
                })
            except Exception as e:
                print(f"[!] Extended prediction failed for {symbol}: {e}")

    return sanitize_floats({"predictions": results, "count": len(results)})


@app.get("/api/ai/predictions/{prediction_id}")
def get_prediction_by_id(prediction_id: str):
    """Return a single prediction by its generated id (pred_symbol_timestamp)"""
    # Extract symbol from id: pred_btcusdc_1711648000 -> BTCUSDC
    parts = prediction_id.replace("pred_", "").rsplit("_", 1)
    symbol = parts[0].upper() if parts else ""
    print(f"[DEBUG] Prediction detail request: id={prediction_id}, extracted symbol={symbol}")

    if symbol not in asset_predictor.all_assets:
        # Try without the timestamp suffix (maybe id is just the symbol)
        alt_symbol = prediction_id.upper().replace("PRED_", "")
        if alt_symbol in asset_predictor.all_assets:
            symbol = alt_symbol
        else:
            print(f"[!] Symbol not found: {symbol}, available: {list(asset_predictor.all_assets.keys())[:5]}...")
            raise HTTPException(status_code=404, detail=f"Prediction not found: {prediction_id}")

    p = asset_predictor.predict_price(symbol, days=7)
    if "error" in p:
        raise HTTPException(status_code=404, detail=p["error"])

    # Fetch live price — use real spot for metals, Binance for crypto
    from services.metals_price_service import get_metal_spot_price, is_metal
    current_price = p.get("current_price", 0)
    if is_metal(symbol):
        spot = get_metal_spot_price(symbol)
        if spot:
            current_price = spot
    else:
        try:
            import httpx
            with httpx.Client(timeout=3.0) as client:
                resp = client.get("https://api.binance.com/api/v3/ticker/price", params={"symbol": symbol})
                if resp.status_code == 200:
                    current_price = float(resp.json()["price"])
        except Exception:
            pass

    rec = (p.get("recommendation") or "HOLD").lower()
    confidence_raw = p.get("confidence", 0)
    confidence = confidence_raw / 100.0 if confidence_raw > 1 else confidence_raw
    # Recalculate change from trend_score against real price (not pre-computed %)
    trend_score = p.get("trend_score", 0)
    daily_change = trend_score * 0.005
    change_pct = daily_change * 7 * 100
    target_price = current_price * (1 + change_pct / 100) if current_price > 0 else p.get("predicted_price", 0)
    trend = p.get("trend", "SIDEWAYS")
    price_decimals = 2 if current_price >= 1 else 6

    return {
        "id": prediction_id,
        "asset": p.get("asset_name") or symbol,
        "symbol": symbol,
        "action": rec,
        "confidence": round(confidence, 3),
        "price": round(current_price, price_decimals),
        "targetPrice": round(target_price, price_decimals),
        "timestamp": p.get("timestamp", datetime.now().isoformat()),
        "reasoning": (
            f"{p.get('asset_name', symbol)}: {trend} trend, "
            f"{'+' if change_pct >= 0 else ''}{change_pct:.1f}% expected in 7 days. "
            f"Strength: {p.get('recommendation_strength', 'N/A')}."
        ),
        "trend": trend,
        "trendScore": p.get("trend_score", 0),
        "priceChange": round(p.get("price_change", 0), price_decimals),
        "priceChangePercent": round(change_pct, 2),
        "recommendationStrength": p.get("recommendation_strength", "N/A"),
        "pricePath": p.get("price_path", []),
        "modelVersion": p.get("model_version", "v1.0"),
    }
    print(f"[DEBUG] Prediction detail response: asset={result['asset']}, price={result['price']}, targetPrice={result['targetPrice']}")
    return sanitize_floats(result)


@app.get("/api/ai/signal/{symbol}")
def get_trading_signal(symbol: str):
    """Επιστρέφει trading signal για οποιοδήποτε asset"""
    return sanitize_floats(asset_predictor.get_trading_signal(symbol.upper()))

@app.get("/api/ai/signals")
def get_all_signals(asset_type: Optional[str] = None):
    """Επιστρέφει trading signals για όλα τα assets ή filtered by type"""
    asset_type_enum = None
    if asset_type:
        try:
            asset_type_enum = AssetType(asset_type.lower())
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid asset type: {asset_type}")
    
    return asset_predictor.get_all_signals(asset_type_enum)

@app.get("/api/ai/assets")
def list_assets(asset_type: Optional[str] = None):
    """List all available assets, optionally filtered by type"""
    asset_type_enum = None
    if asset_type:
        try:
            asset_type_enum = AssetType(asset_type.lower())
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid asset type: {asset_type}")
    
    return asset_predictor.list_assets(asset_type_enum)

@app.get("/api/ai/assets/{symbol}")
def get_asset_info(symbol: str):
    """Get information about a specific asset"""
    info = asset_predictor.get_asset_info(symbol.upper())
    if not info:
        raise HTTPException(status_code=404, detail=f"Asset not found: {symbol}")
    return info

# Legacy endpoints (for backward compatibility)
@app.get("/api/ai/predict/metals/{symbol}")
def get_metal_prediction(symbol: str, days: int = 7):
    """Legacy endpoint - Επιστρέφει AI prediction για ένα metal"""
    return sanitize_floats(precious_metals_predictor.predict_price(symbol.upper(), days))

@app.get("/api/ai/predictions/metals")
def get_metals_predictions(days: int = 7):
    """Legacy endpoint - Επιστρέφει predictions για όλα τα precious metals"""
    return sanitize_floats(precious_metals_predictor.get_all_predictions(days))

@app.get("/api/ai/status")
def get_ai_status():
    """Επιστρέφει κατάσταση AI engine"""
    return {
        "status": "active",
        "engine": "precious_metals_predictor",
        "model_version": "v1.0-alpha",
        "supported_metals": list(precious_metals_predictor.metals.keys()),
        "accuracy_estimate": "68-74%",
        "timestamp": datetime.now().isoformat()
    }

# CMS Endpoints
class QuoteCreate(BaseModel):
    el: str
    en: str
    author: Optional[str] = ""
    category: Optional[str] = "general"

class QuoteUpdate(BaseModel):
    el: Optional[str] = None
    en: Optional[str] = None
    author: Optional[str] = None
    category: Optional[str] = None

@app.get("/api/cms/quotes")
def get_all_quotes():
    """Επιστρέφει όλα τα quotes"""
    return {
        "quotes": cms_service.get_all_quotes(),
        "total": len(cms_service.get_all_quotes()),
        "timestamp": datetime.now().isoformat()
    }

@app.get("/api/cms/quotes/{quote_id}")
def get_quote(quote_id: int):
    """Επιστρέφει ένα quote"""
    quote = cms_service.get_quote_by_id(quote_id)
    if not quote:
        raise HTTPException(status_code=404, detail="Quote not found")
    return quote

@app.post("/api/cms/quotes")
def create_quote(quote: QuoteCreate):
    """Δημιουργεί νέο quote"""
    return cms_service.add_quote(quote.dict())

@app.put("/api/cms/quotes/{quote_id}")
def update_quote(quote_id: int, quote: QuoteUpdate):
    """Ενημερώνει quote"""
    updated = cms_service.update_quote(quote_id, quote.dict(exclude_unset=True))
    if not updated:
        raise HTTPException(status_code=404, detail="Quote not found")
    return updated

@app.delete("/api/cms/quotes/{quote_id}")
def delete_quote(quote_id: int):
    """Διαγράφει quote"""
    success = cms_service.delete_quote(quote_id)
    if not success:
        raise HTTPException(status_code=404, detail="Quote not found")
    return {"status": "deleted", "quote_id": quote_id}

@app.get("/api/cms/news")
def get_news():
    """Επιστρέφει όλα τα news articles"""
    return {
        "news": cms_service.get_news(),
        "total": len(cms_service.get_news()),
        "timestamp": datetime.now().isoformat()
    }

@app.get("/api/cms/settings")
def get_settings():
    """Επιστρέφει CMS settings"""
    return cms_service.get_settings()

@app.put("/api/cms/settings")
def update_settings(settings: Dict):
    """Ενημερώνει CMS settings"""
    return cms_service.update_settings(settings)

# Voice Briefing Endpoints
@app.get("/api/voice/briefing")
def get_morning_briefing(
    include_news: bool = True,
    include_predictions: bool = True,
    include_portfolio: bool = True,
    max_duration: int = 90
):
    """Επιστρέφει morning briefing"""
    return voice_briefing_service.generate_briefing(
        include_market_news=include_news,
        include_ai_predictions=include_predictions,
        include_portfolio=include_portfolio,
        max_duration_seconds=max_duration
    )

@app.get("/api/voice/briefing/history")
def get_briefing_history(days: int = 7):
    """Επιστρέφει briefing history"""
    return {
        "briefings": voice_briefing_service.get_briefing_history(days),
        "days": days,
        "timestamp": datetime.now().isoformat()
    }

# On-Device ML Endpoints
@app.get("/api/ml/models")
def list_models():
    """Επιστρέφει λίστα ML models"""
    return {
        "models": model_manager.list_models(),
        "status": model_manager.get_model_status(),
        "timestamp": datetime.now().isoformat()
    }

@app.get("/api/ml/models/{model_id}")
def get_model_info(model_id: str):
    """Επιστρέφει πληροφορίες για ένα model"""
    model = model_manager.get_model_info(model_id)
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    return model

@app.get("/api/ml/models/{model_id}/deploy/{platform}")
def prepare_model_deployment(model_id: str, platform: str):
    """Προετοιμάζει model για deployment"""
    result = model_manager.prepare_for_deployment(model_id, platform)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result

@app.get("/api/ml/training/configs")
def list_training_configs():
    """Επιστρέφει training configurations"""
    return {
        "configs": training_prep.list_training_configs(),
        "status": training_prep.get_training_status(),
        "timestamp": datetime.now().isoformat()
    }

@app.get("/api/ml/training/dataset/{dataset_type}")
def get_dataset_info(dataset_type: str):
    """Επιστρέφει πληροφορίες για dataset preparation"""
    return training_prep.prepare_dataset_info(dataset_type)

@app.post("/api/ml/training/train")
def train_model_endpoint(
    model_type: str = "random_forest",
    symbol: Optional[str] = None,
    days: int = 365,
    n_estimators: int = 100,
    max_depth: int = 10
):
    """
    Εκπαιδεύει ML model
    
    Args:
        model_type: Type of model (random_forest, gradient_boosting)
        symbol: Symbol to train (if None, trains all metals)
        days: Days of training data
        n_estimators: Number of estimators
        max_depth: Max depth
    """
    try:
        from ml.train_model import ModelTrainer
        
        trainer = ModelTrainer(models_dir=os.path.join(os.path.dirname(__file__), "models"))
        
        hyperparameters = {
            'n_estimators': n_estimators,
            'max_depth': max_depth
        }
        
        if symbol:
            # Train single symbol
            base_prices = {
                "XAUUSDC": 2050.0,
                "XAGUSDC": 24.5,
                "XPTUSDC": 950.0,
                "XPDUSDC": 1200.0
            }
            base_price = base_prices.get(symbol, 100.0)
            
            result = trainer.train_model(
                model_type=model_type,
                symbol=symbol,
                base_price=base_price,
                days=days,
                **hyperparameters
            )
            return result
        else:
            # Train all metals
            results = trainer.train_all_metals(
                model_type=model_type,
                **hyperparameters
            )
            return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Training failed: {str(e)}")

@app.get("/api/ml/status")
def get_ml_status():
    """Επιστρέφει overall ML status"""
    return {
        "models": model_manager.get_model_status(),
        "training": training_prep.get_training_status(),
        "platforms_supported": ["ios (MLX)", "android (ONNX)"],
        "timestamp": datetime.now().isoformat()
    }

# Live Trading Endpoints
class TradingModeRequest(BaseModel):
    mode: str  # "paper" or "live"

class RiskSettingsUpdate(BaseModel):
    max_position_size_percent: Optional[float] = None
    max_daily_loss_percent: Optional[float] = None
    stop_loss_percent: Optional[float] = None
    take_profit_percent: Optional[float] = None
    max_open_positions: Optional[int] = None
    require_confirmation: Optional[bool] = None

class OrderValidationRequest(BaseModel):
    symbol: str
    side: str
    quantity: float
    price: float

@app.get("/api/trading/mode")
def get_trading_mode():
    """Επιστρέφει current trading mode"""
    return live_trading_service.get_trading_mode()

@app.post("/api/trading/mode")
def set_trading_mode(request: TradingModeRequest, _user=Depends(require_auth)):
    """Ορίζει trading mode (paper/live)"""
    if request.mode == "live" and not broker_instances:
        # Try auto-reload from DB before rejecting
        _restore_broker_connections()
        if not broker_instances:
            raise HTTPException(
                status_code=400,
                detail="Cannot switch to live mode: no broker connected. "
                       "Please connect a broker first via /api/brokers/connect"
            )
    result = live_trading_service.set_trading_mode(request.mode)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result

@app.get("/api/trading/risk-settings")
def get_risk_settings():
    """Επιστρέφει risk management settings"""
    return {
        "risk_settings": live_trading_service.risk_settings,
        "daily_stats": live_trading_service.daily_stats,
        "timestamp": datetime.now().isoformat()
    }

@app.put("/api/trading/risk-settings")
def update_risk_settings(settings: RiskSettingsUpdate):
    """Ενημερώνει risk management settings"""
    return live_trading_service.update_risk_settings(settings.dict(exclude_unset=True))

@app.post("/api/trading/validate-order")
def validate_order(request: OrderValidationRequest):
    """Επικυρώνει order πριν από execution"""
    # Get portfolio data
    portfolio = paper_trading_service.get_portfolio()
    positions = portfolio.get("positions", [])
    
    return live_trading_service.validate_order(
        symbol=request.symbol,
        side=request.side,
        quantity=request.quantity,
        price=request.price,
        portfolio_value=portfolio.get("total_value", 0),
        current_positions=positions
    )

@app.post("/api/trading/calculate-position")
def calculate_position_size(
    symbol: str,
    side: str,
    price: float,
    risk_percent: Optional[float] = None
):
    """Υπολογίζει optimal position size"""
    portfolio = paper_trading_service.get_portfolio()
    
    return live_trading_service.calculate_position_size(
        symbol=symbol,
        side=side,
        price=price,
        portfolio_value=portfolio.get("total_value", 0),
        risk_percent=risk_percent
    )

@app.get("/api/trading/risk-summary")
def get_risk_summary():
    """Επιστρέφει risk management summary"""
    portfolio = paper_trading_service.get_portfolio()
    return live_trading_service.get_risk_summary(portfolio.get("total_value", 0))

# Analytics Endpoints
@app.get("/api/analytics/performance")
def get_performance_metrics():
    """Επιστρέφει performance metrics"""
    trades = paper_trading_service.get_trade_history(limit=1000)
    portfolio = paper_trading_service.get_portfolio()
    
    metrics = analytics_service.calculate_performance_metrics(
        trades=trades,
        portfolio_value=portfolio.get("total_value", 0),
        initial_balance=portfolio.get("initial_balance", 10000.0)
    )
    
    # Add insights
    metrics["insights"] = analytics_service.get_trading_insights(metrics)
    
    return metrics

@app.get("/api/analytics/performance/{period}")
def get_performance_by_period(period: str):
    """Επιστρέφει performance by period (daily/weekly/monthly)"""
    trades = paper_trading_service.get_trade_history(limit=1000)
    return analytics_service.get_performance_by_period(trades, period)

@app.get("/api/analytics/symbols")
def get_symbol_performance():
    """Επιστρέφει performance by symbol"""
    trades = paper_trading_service.get_trade_history(limit=1000)
    return {
        "symbols": analytics_service.get_symbol_performance(trades),
        "total_symbols": len(set(t.get("symbol") for t in trades)),
        "timestamp": datetime.now().isoformat()
    }

@app.get("/api/analytics/summary")
def get_analytics_summary(period: str = "all"):
    """Analytics summary aggregating paper + auto trades. period: 7d|30d|90d|all"""
    trades = paper_trading_service.get_trade_history(limit=10000)
    portfolio = paper_trading_service.get_portfolio()

    # Filter by period
    if period != "all":
        days_map = {"7d": 7, "30d": 30, "90d": 90}
        days = days_map.get(period, 9999)
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        trades = [t for t in trades if t.get("timestamp", "") >= cutoff]

    total_trades = len(trades)

    if total_trades == 0:
        return {
            "total_value": portfolio.get("total_value", 0),
            "pnl_percent": 0,
            "total_trades": 0,
            "win_rate": 0,
            "avg_profit": 0,
            "best_trade": None,
            "worst_trade": None,
            "asset_allocation": [],
            "has_data": False,
        }

    # Calculate win rate and profits from sell trades (realized P/L)
    sells = [t for t in trades if t.get("side") == "SELL"]
    profits = [t.get("profit", t.get("pnl", 0)) for t in sells]
    wins = [p for p in profits if p > 0]
    win_rate = (len(wins) / len(sells) * 100) if sells else 0
    avg_profit = sum(profits) / len(profits) if profits else 0

    # Best and worst
    best = max(sells, key=lambda t: t.get("profit", t.get("pnl", 0)), default=None) if sells else None
    worst = min(sells, key=lambda t: t.get("profit", t.get("pnl", 0)), default=None) if sells else None

    # Asset allocation from current positions
    positions = portfolio.get("positions", [])
    total_pos_value = sum(p.get("value", 0) for p in positions) or 1
    allocation = [
        {
            "asset": p["symbol"],
            "percentage": round(p.get("value", 0) / total_pos_value * 100, 1),
            "value": round(p.get("value", 0), 2),
        }
        for p in positions
    ]

    pnl_pct = portfolio.get("total_pnl_percent", 0)

    return {
        "total_value": round(portfolio.get("total_value", 0), 2),
        "pnl_percent": round(pnl_pct, 2),
        "total_trades": total_trades,
        "win_rate": round(win_rate, 1),
        "avg_profit": round(avg_profit, 2),
        "best_trade": {
            "symbol": best.get("symbol", ""),
            "profit": round(best.get("profit", best.get("pnl", 0)), 2),
            "percent": round(best.get("profit_pct", best.get("pnl_percent", 0)), 2),
        } if best else None,
        "worst_trade": {
            "symbol": worst.get("symbol", ""),
            "profit": round(worst.get("profit", worst.get("pnl", 0)), 2),
            "percent": round(worst.get("profit_pct", worst.get("pnl_percent", 0)), 2),
        } if worst else None,
        "asset_allocation": allocation,
        "has_data": True,
    }


# Scheduler Endpoints
class ScheduleCreate(BaseModel):
    schedule_type: str
    time: str  # "HH:MM"
    days: List[str]
    enabled: bool = True
    config: Optional[Dict] = None

class ScheduleUpdate(BaseModel):
    time: Optional[str] = None
    days: Optional[List[str]] = None
    enabled: Optional[bool] = None
    config: Optional[Dict] = None

@app.get("/api/scheduler/schedules")
def get_schedules(schedule_type: Optional[str] = None):
    """Επιστρέφει όλα τα schedules"""
    schedules = scheduler_service.get_schedules(schedule_type)
    return {
        "schedules": schedules,
        "total": len(schedules),
        "timestamp": datetime.now().isoformat()
    }

@app.get("/api/scheduler/schedules/{schedule_id}")
def get_schedule(schedule_id: str):
    """Επιστρέφει ένα schedule"""
    schedule = scheduler_service.get_schedule(schedule_id)
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")
    return schedule

@app.post("/api/scheduler/schedules")
def create_schedule(schedule: ScheduleCreate):
    """Δημιουργεί νέο schedule"""
    return scheduler_service.create_schedule(
        schedule_type=schedule.schedule_type,
        time_str=schedule.time,
        days=schedule.days,
        enabled=schedule.enabled,
        config=schedule.config
    )

@app.put("/api/scheduler/schedules/{schedule_id}")
def update_schedule(schedule_id: str, schedule: ScheduleUpdate):
    """Ενημερώνει schedule"""
    updated = scheduler_service.update_schedule(
        schedule_id=schedule_id,
        time_str=schedule.time,
        days=schedule.days,
        enabled=schedule.enabled,
        config=schedule.config
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Schedule not found")
    return updated

@app.delete("/api/scheduler/schedules/{schedule_id}")
def delete_schedule(schedule_id: str):
    """Διαγράφει schedule"""
    success = scheduler_service.delete_schedule(schedule_id)
    if not success:
        raise HTTPException(status_code=404, detail="Schedule not found")
    return {"status": "deleted", "schedule_id": schedule_id}

@app.get("/api/scheduler/upcoming")
def get_upcoming_schedules(limit: int = 10):
    """Επιστρέφει upcoming schedules"""
    upcoming = scheduler_service.get_upcoming_schedules(limit)
    return {
        "schedules": upcoming,
        "total": len(upcoming),
        "timestamp": datetime.now().isoformat()
    }

# Notifications Endpoints
class NotificationCreate(BaseModel):
    type: str
    title: str
    message: str
    priority: Optional[str] = "medium"
    data: Optional[Dict] = None

@app.get("/api/notifications")
def get_notifications(
    unread_only: bool = False,
    notification_type: Optional[str] = None,
    limit: int = 50
):
    """Επιστρέφει notifications"""
    return {
        "notifications": notifications_service.get_notifications(
            unread_only=unread_only,
            notification_type=notification_type,
            limit=limit
        ),
        "unread_count": notifications_service.get_unread_count(),
        "timestamp": datetime.now().isoformat()
    }

@app.get("/api/notifications/stats")
def get_notification_stats():
    """Επιστρέφει notification statistics"""
    return notifications_service.get_notification_stats()

@app.get("/api/notifications/{notification_id}")
def get_notification(notification_id: str):
    """Επιστρέφει ένα notification"""
    notification = notifications_service.get_notification(notification_id)
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")
    return notification

@app.post("/api/notifications")
def create_notification(notification: NotificationCreate):
    """Δημιουργεί νέο notification"""
    from services.notifications import NotificationType, NotificationPriority
    
    return notifications_service.create_notification(
        notification_type=NotificationType(notification.type),
        title=notification.title,
        message=notification.message,
        priority=NotificationPriority(notification.priority),
        data=notification.data
    )

@app.put("/api/notifications/{notification_id}/read")
def mark_notification_read(notification_id: str):
    """Mark notification as read"""
    success = notifications_service.mark_as_read(notification_id)
    if not success:
        raise HTTPException(status_code=404, detail="Notification not found")
    return {"status": "read", "notification_id": notification_id}

@app.put("/api/notifications/read-all")
def mark_all_read():
    """Mark all notifications as read"""
    count = notifications_service.mark_all_as_read()
    return {"status": "read", "count": count}

@app.delete("/api/notifications/{notification_id}")
def delete_notification(notification_id: str):
    """Διαγράφει notification"""
    success = notifications_service.delete_notification(notification_id)
    if not success:
        raise HTTPException(status_code=404, detail="Notification not found")
    return {"status": "deleted", "notification_id": notification_id}

@app.delete("/api/notifications/read")
def delete_all_read():
    """Διαγράφει όλα τα read notifications"""
    count = notifications_service.delete_all_read()
    return {"status": "deleted", "count": count}


# ── User Profile Endpoints ──────────────────────────────────────────

class UpdateProfileRequest(BaseModel):
    username: Optional[str] = None
    email: Optional[str] = None

class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


def _get_db_user(payload: dict):
    """Get DB user from JWT payload. Returns (db_session, user). Caller must close db."""
    from database.models import User as _User
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token: missing user ID")
    try:
        uid = int(user_id)
    except (ValueError, TypeError):
        raise HTTPException(status_code=401, detail="Invalid token: malformed user ID")
    db = SessionLocal()
    user = db.query(_User).filter(_User.id == uid).first()
    if not user:
        db.close()
        raise HTTPException(status_code=404, detail="User not found")
    return db, user


def _user_response(user) -> dict:
    """Build consistent profile response dict."""
    return {
        "id": user.id,
        "email": user.email,
        "username": user.full_name or user.email.split("@")[0],
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "broker_connected": bool(broker_instances),
        "trading_mode": os.getenv("TRADING_MODE", "paper"),
    }


@app.get("/api/user/profile")
def get_user_profile(payload=Depends(require_auth)):
    """Return user profile from database."""
    db, user = _get_db_user(payload)
    try:
        return _user_response(user)
    finally:
        db.close()


@app.put("/api/user/profile")
def update_user_profile(data: UpdateProfileRequest, payload=Depends(require_auth)):
    """Update user profile fields in database."""
    db, user = _get_db_user(payload)
    try:
        if data.username is not None:
            stripped = data.username.strip()
            if not stripped:
                raise HTTPException(status_code=400, detail="Username cannot be empty")
            user.full_name = stripped
        if data.email is not None:
            from database.models import User as _User
            clean_email = data.email.lower().strip()
            if not clean_email or "@" not in clean_email:
                raise HTTPException(status_code=400, detail="Invalid email address")
            existing = db.query(_User).filter(_User.email == clean_email, _User.id != user.id).first()
            if existing:
                raise HTTPException(status_code=409, detail="Email already in use")
            user.email = clean_email
        db.commit()
        return _user_response(user)
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to update profile")
    finally:
        db.close()


@app.put("/api/user/password")
def update_user_password(data: ChangePasswordRequest, payload=Depends(require_auth)):
    """Change user password — verifies current password first."""
    if len(data.new_password) < 8:
        raise HTTPException(status_code=400, detail="New password must be at least 8 characters")
    db, user = _get_db_user(payload)
    try:
        import bcrypt
        if not bcrypt.checkpw(data.current_password.encode("utf-8"), user.password_hash.encode("utf-8")):
            raise HTTPException(status_code=400, detail="Current password is incorrect")
        if bcrypt.checkpw(data.new_password.encode("utf-8"), user.password_hash.encode("utf-8")):
            raise HTTPException(status_code=400, detail="New password must be different from current password")
        user.password_hash = bcrypt.hashpw(data.new_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        # Increment token_version to invalidate all existing tokens
        user.token_version = (user.token_version or 0) + 1
        db.commit()
        from services.auth_audit import log_auth_event
        log_auth_event("PASSWORD_CHANGE", "SUCCESS", user_id=user.id, email=user.email)
        return {"success": True, "message": "Password updated"}
    except HTTPException:
        raise
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to update password")
    finally:
        db.close()


@app.post("/api/user/logout-all")
def logout_all_devices(payload=Depends(require_auth)):
    """Invalidate all existing tokens by incrementing token_version."""
    from config.feature_flags import ENABLE_TOKEN_VERSIONING
    if not ENABLE_TOKEN_VERSIONING:
        return {"success": True, "message": "Logout-all acknowledged (token versioning not active)"}
    db, user = _get_db_user(payload)
    try:
        user.token_version = (user.token_version or 0) + 1
        db.commit()
        from services.auth_audit import log_auth_event
        log_auth_event("LOGOUT_ALL", "SUCCESS", user_id=user.id, email=user.email)
        return {"success": True, "message": "All sessions invalidated"}
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to invalidate sessions")
    finally:
        db.close()


@app.put("/api/user/risk-profile")
def update_user_risk_profile(data: dict, payload=Depends(require_auth)):
    """Update risk profile preference (stored in-memory, not persisted to DB)."""
    risk = data.get("risk_profile", "moderate")
    if risk not in ("conservative", "moderate", "aggressive"):
        raise HTTPException(status_code=400, detail="Invalid risk profile. Must be: conservative, moderate, or aggressive")
    return {"risk_profile": risk}


# ── Live Trading Endpoints ───────────────────────────────────────────
LIVE_ORDER_MAX_VALUE_USD = 100.0  # Safety limit per order — protects against accidental large orders

def _get_live_broker():
    """Get the first connected broker or raise 400."""
    if not broker_instances:
        _restore_broker_connections()
    if not broker_instances:
        raise HTTPException(status_code=400, detail="No broker connected. Use POST /api/brokers/connect first.")
    return next(iter(broker_instances.values()))


def _pre_order_safety_check(broker, symbol: str, quantity: float):
    """Prevent accidental large orders."""
    if quantity <= 0:
        raise HTTPException(status_code=400, detail="Quantity must be positive")
    price = broker.get_symbol_price(symbol)
    if price <= 0:
        raise HTTPException(status_code=400, detail=f"Could not fetch price for {symbol}")
    order_value = price * quantity
    if order_value > LIVE_ORDER_MAX_VALUE_USD:
        raise HTTPException(
            status_code=400,
            detail=f"Order value ${order_value:.2f} exceeds safety limit of ${LIVE_ORDER_MAX_VALUE_USD:.0f}"
        )
    return price


class LiveOrderRequest(BaseModel):
    symbol: str
    side: str
    quantity: float


class LimitOrderRequest(BaseModel):
    symbol: str
    side: str
    quantity: float
    price: float
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None


@app.get("/api/live-trading/portfolio")
def get_live_portfolio():
    """Returns real Binance account balance."""
    broker = _get_live_broker()
    balance = broker.get_account_balance()
    if "error" in balance:
        raise HTTPException(status_code=400, detail=balance["error"])
    return balance


@app.get("/api/live-trading/positions")
def get_live_positions():
    """Returns open orders from Binance."""
    broker = _get_live_broker()
    orders = broker.get_open_orders()
    return {"positions": orders, "count": len(orders)}


@app.post("/api/live-trading/order")
def place_live_market_order(order: LiveOrderRequest, _user=Depends(require_auth)):
    """Place a real MARKET order on Binance Spot."""
    broker = _get_live_broker()
    price = _pre_order_safety_check(broker, order.symbol, order.quantity)
    result = broker.place_live_order(
        symbol=order.symbol,
        side=order.side,
        quantity=order.quantity,
        order_type="MARKET"
    )
    if "error" in result:
        parsed = _parse_binance_error(result)
        raise HTTPException(status_code=400, detail=parsed)
    return result


@app.post("/api/live-trading/order/limit")
def place_live_limit_order(order: LimitOrderRequest, _user=Depends(require_auth)):
    """Place a LIMIT order with optional SL/TP."""
    broker = _get_live_broker()
    _pre_order_safety_check(broker, order.symbol, order.quantity)
    result = broker.place_limit_order(
        symbol=order.symbol,
        side=order.side,
        quantity=order.quantity,
        price=order.price,
    )
    if "error" in result:
        parsed = _parse_binance_error(result)
        raise HTTPException(status_code=400, detail=parsed)

    # Place OCO for SL/TP if both provided
    if order.stop_loss and order.take_profit:
        exit_side = "SELL" if order.side.upper() == "BUY" else "BUY"
        oco_result = broker.place_oco_order(
            symbol=order.symbol,
            side=exit_side,
            quantity=order.quantity,
            price=order.take_profit,
            stop_price=order.stop_loss,
            stop_limit_price=order.stop_loss,
        )
        result["oco_order"] = oco_result

    return result


@app.delete("/api/live-trading/order/{symbol}/{order_id}")
def cancel_live_order(symbol: str, order_id: int, _user=Depends(require_auth)):
    """Cancel an open order."""
    broker = _get_live_broker()
    result = broker.cancel_order(symbol, order_id)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


# ── Futures Endpoints ────────────────────────────────────────────────
@app.get("/api/live-trading/futures/portfolio")
def get_futures_portfolio():
    """Returns real Binance Futures account."""
    broker = _get_live_broker()
    account = broker.futures_account()
    if "error" in account:
        raise HTTPException(status_code=400, detail=account["error"])
    return {
        "totalWalletBalance": account.get("totalWalletBalance"),
        "totalUnrealizedProfit": account.get("totalUnrealizedProfit"),
        "totalMarginBalance": account.get("totalMarginBalance"),
        "availableBalance": account.get("availableBalance"),
    }


@app.get("/api/live-trading/futures/positions")
def get_futures_positions():
    """Returns open futures positions."""
    broker = _get_live_broker()
    positions = broker.futures_positions()
    return {"positions": positions, "count": len(positions)}


@app.post("/api/live-trading/futures/order")
def place_futures_order(order: LiveOrderRequest, _user=Depends(require_auth)):
    """Place a futures MARKET order."""
    broker = _get_live_broker()
    _pre_order_safety_check(broker, order.symbol, order.quantity)
    result = broker.futures_create_order(
        symbol=order.symbol,
        side=order.side,
        quantity=order.quantity,
    )
    if "error" in result:
        parsed = _parse_binance_error(result)
        raise HTTPException(status_code=400, detail=parsed)
    return result


# ── Auto Trading Endpoints ───────────────────────────────────────────
from services.auto_trading_engine import auto_trader


class AutoTradingConfigUpdate(BaseModel):
    confidence_threshold: Optional[float] = None
    fixed_order_value_usd: Optional[float] = None
    stop_loss_pct: Optional[float] = None
    max_positions: Optional[int] = None
    max_order_value_usd: Optional[float] = None
    smart_score_threshold: Optional[int] = None


@app.get("/api/auto-trading/status")
def get_auto_trading_status():
    """Get auto trading engine status and config."""
    return auto_trader.get_status()


@app.post("/api/auto-trading/enable")
def enable_auto_trading(_user=Depends(require_auth)):
    """Enable auto trading — user must explicitly call this."""
    if not broker_instances:
        _restore_broker_connections()
    if not broker_instances:
        raise HTTPException(status_code=400, detail="No broker connected. Connect a broker first.")
    broker = next(iter(broker_instances.values()))
    auto_trader.set_broker(broker)
    try:
        auto_trader.enable()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"success": True, "message": "Auto trading enabled", "status": auto_trader.get_status()}


@app.post("/api/auto-trading/disable")
def disable_auto_trading(_user=Depends(require_auth)):
    """Disable auto trading."""
    auto_trader.disable()
    return {"success": True, "message": "Auto trading disabled"}


@app.put("/api/auto-trading/config")
def update_auto_trading_config(config: AutoTradingConfigUpdate, _user=Depends(require_auth)):
    """Update auto trading config (thresholds, limits)."""
    if config.confidence_threshold is not None:
        auto_trader.config["confidence_threshold"] = max(0.5, min(1.0, config.confidence_threshold))
    if config.fixed_order_value_usd is not None:
        auto_trader.config["fixed_order_value_usd"] = max(5.0, min(100.0, config.fixed_order_value_usd))
    if config.stop_loss_pct is not None:
        auto_trader.config["stop_loss_pct"] = max(0.01, min(0.10, config.stop_loss_pct))
    if config.max_positions is not None:
        auto_trader.config["max_positions"] = max(1, min(10, config.max_positions))
    if config.max_order_value_usd is not None:
        auto_trader.config["max_order_value_usd"] = max(10, min(500, config.max_order_value_usd))
    if config.smart_score_threshold is not None:
        auto_trader.config["smart_score_threshold"] = max(50, min(95, config.smart_score_threshold))
    return auto_trader.get_status()


@app.get("/api/auto-trading/smart-score/{symbol}")
def get_smart_score(symbol: str):
    """Calculate Smart Score for a symbol — shows all signal breakdowns."""
    from services.smart_score import smart_score_calculator
    return smart_score_calculator.calculate_smart_score(symbol.upper())


@app.get("/api/auto-trading/positions")
def get_auto_trading_positions():
    """Get positions opened by auto trader."""
    return {
        "positions": list(auto_trader.open_positions.values()),
        "count": len(auto_trader.open_positions),
    }


# ── Model Training Endpoints ────────────────────────────────

@app.post("/api/ml/train/{symbol}")
def train_single_model(symbol: str, _user=Depends(require_auth)):
    """Train XGBoost model for a single symbol using real Binance data."""
    from ml.auto_trainer import train_symbol
    result = train_symbol(symbol.upper())
    if result and "metrics" in result:
        # Reload models in predictor
        asset_predictor._load_models()
        return result
    raise HTTPException(status_code=500, detail=f"Training failed for {symbol}")


@app.post("/api/ml/train-all")
def train_all_models(_user=Depends(require_auth)):
    """Train XGBoost models for all 27 USDC crypto pairs. Takes several minutes."""
    from ml.auto_trainer import train_all_symbols
    results = train_all_symbols()
    # Reload models
    asset_predictor._load_models()
    succeeded = [r for r in results if "metrics" in r]
    failed = [r for r in results if "error" in r]
    return {
        "total": len(results),
        "succeeded": len(succeeded),
        "failed": len(failed),
        "results": results,
    }


# ── News Intelligence Endpoints ─────────────────────────────

@app.get("/api/news/sentiment/{symbol}")
def get_news_sentiment(symbol: str):
    """Get real news sentiment for a symbol from 3 sources + VADER."""
    from services.news_fetcher import news_fetcher
    return news_fetcher.get_symbol_sentiment(symbol.upper())


# ── Accuracy Tracking Endpoints ─────────────────────────────

@app.get("/api/accuracy")
def get_prediction_accuracy(symbol: Optional[str] = None):
    """Get prediction accuracy stats, optionally filtered by symbol."""
    from services.accuracy_tracker import accuracy_tracker
    return accuracy_tracker.get_accuracy(symbol.upper() if symbol else None)


@app.get("/api/accuracy/{symbol}/rolling")
def get_rolling_accuracy(symbol: str, days: int = 30):
    """Get rolling direction accuracy for a symbol."""
    from services.accuracy_tracker import accuracy_tracker
    acc = accuracy_tracker.get_rolling_accuracy(symbol.upper(), days=days)
    return {"symbol": symbol.upper(), "rolling_accuracy": round(acc, 3), "days": days}


# ── AI Training Pipeline Endpoints ──────────────────────────

_training_jobs: Dict = {}  # job_id -> status


def _run_pipeline_background(job_id: str, phase: str):
    """Background task wrapper for training pipeline phases."""
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
    try:
        if phase == "collect_data":
            from scripts.collect_training_data import run_collection
            run_collection(job_id)
        elif phase == "label_sentiment":
            from ml.sentiment_labeler import label_all_news
            label_all_news(job_id)
        elif phase == "feature_engineering":
            from ml.feature_engineer import engineer_all_features
            engineer_all_features(job_id)
        elif phase == "retrain":
            from ml.enhanced_trainer import retrain_all
            retrain_all(job_id)
        elif phase == "full_pipeline":
            from scripts.run_full_pipeline import run_full_pipeline
            run_full_pipeline(job_id)
        _training_jobs[job_id] = {"status": "completed", "phase": phase}
    except Exception as e:
        _training_jobs[job_id] = {"status": "failed", "phase": phase, "error": str(e)}


@app.post("/api/v1/training/collect-data")
def trigger_data_collection(background_tasks: BackgroundTasks):
    """Phase 1: Trigger async data collection (OHLCV + news)."""
    import uuid
    job_id = f"collect_{uuid.uuid4().hex[:8]}"
    _training_jobs[job_id] = {"status": "running", "phase": "collect_data"}
    background_tasks.add_task(_run_pipeline_background, job_id, "collect_data")
    return {"job_id": job_id, "status": "started", "phase": "collect_data"}


@app.post("/api/v1/training/label-sentiment")
def trigger_sentiment_labeling(background_tasks: BackgroundTasks):
    """Phase 2: Trigger async sentiment labeling."""
    import uuid
    job_id = f"sentiment_{uuid.uuid4().hex[:8]}"
    _training_jobs[job_id] = {"status": "running", "phase": "label_sentiment"}
    background_tasks.add_task(_run_pipeline_background, job_id, "label_sentiment")
    return {"job_id": job_id, "status": "started", "phase": "label_sentiment"}


@app.post("/api/v1/training/engineer-features")
def trigger_feature_engineering(background_tasks: BackgroundTasks):
    """Phase 3: Trigger async feature engineering."""
    import uuid
    job_id = f"features_{uuid.uuid4().hex[:8]}"
    _training_jobs[job_id] = {"status": "running", "phase": "feature_engineering"}
    background_tasks.add_task(_run_pipeline_background, job_id, "feature_engineering")
    return {"job_id": job_id, "status": "started", "phase": "feature_engineering"}


@app.post("/api/v1/training/retrain")
def trigger_retrain(background_tasks: BackgroundTasks):
    """Phase 4: Trigger async model retraining."""
    import uuid
    job_id = f"retrain_{uuid.uuid4().hex[:8]}"
    _training_jobs[job_id] = {"status": "running", "phase": "retrain"}
    background_tasks.add_task(_run_pipeline_background, job_id, "retrain")
    return {"job_id": job_id, "status": "started", "phase": "retrain"}


@app.post("/api/v1/training/full-pipeline")
def trigger_full_pipeline(background_tasks: BackgroundTasks):
    """Run all 4 phases in sequence (async). Returns job_id to track progress."""
    import uuid
    job_id = f"pipeline_{uuid.uuid4().hex[:8]}"
    _training_jobs[job_id] = {"status": "running", "phase": "full_pipeline"}
    background_tasks.add_task(_run_pipeline_background, job_id, "full_pipeline")
    return {"job_id": job_id, "status": "started", "phase": "full_pipeline"}


@app.get("/api/v1/training/status/{job_id}")
def get_training_status(job_id: str):
    """Check training job progress. Reads from in-memory cache + training_logs table."""
    # Check in-memory first
    if job_id in _training_jobs:
        result = dict(_training_jobs[job_id])
    else:
        result = {"status": "unknown"}

    # Enrich from database logs
    try:
        db = SessionLocal()
        from database.models import TrainingLog
        logs = db.query(TrainingLog).filter(
            TrainingLog.job_id == job_id
        ).order_by(TrainingLog.id.desc()).limit(5).all()
        result["logs"] = [
            {"phase": l.phase, "status": l.status, "message": l.message,
             "progress": l.progress, "time": l.started_at.isoformat() if l.started_at else None}
            for l in logs
        ]
        db.close()
    except Exception:
        pass

    return result


@app.get("/api/v1/training/model-performance")
def get_model_performance():
    """Return accuracy metrics per symbol from model_registry."""
    try:
        db = SessionLocal()
        from database.models import ModelRegistry
        models = db.query(ModelRegistry).filter(
            ModelRegistry.is_active == True
        ).all()
        result = [
            {
                "symbol": m.symbol,
                "version": m.model_version,
                "accuracy": m.accuracy,
                "precision": m.precision_score,
                "recall": m.recall_score,
                "training_samples": m.training_samples,
                "trained_at": m.trained_at.isoformat() if m.trained_at else None,
            }
            for m in models
        ]
        db.close()
        return {"models": result, "count": len(result)}
    except Exception as e:
        return {"models": [], "count": 0, "error": str(e)}


# ── Backtesting Endpoints ───────────────────────────────────

@app.post("/api/v1/backtest/run/{symbol}")
def run_backtest_symbol(symbol: str):
    """Run backtest for a single symbol synchronously."""
    from ml.backtester import backtest_symbol
    result = backtest_symbol(symbol.upper())
    if result and "error" not in result:
        return result
    return {"symbol": symbol.upper(), "error": result.get("error", "Unknown error") if result else "No result"}


@app.post("/api/v1/backtest/run-all")
def run_backtest_all():
    """Run backtest for all symbols synchronously. Returns results directly."""
    import uuid
    job_id = f"bt_all_{uuid.uuid4().hex[:8]}"
    from ml.backtester import backtest_all
    results = backtest_all(job_id)
    succeeded = [r for r in results if "total_return_pct" in r]
    failed = [r for r in results if "error" in r]
    return {
        "job_id": job_id,
        "total": len(results),
        "succeeded": len(succeeded),
        "failed": len(failed),
        "results": results,
    }


@app.get("/api/v1/backtest/results")
def get_backtest_results():
    """Get latest backtest results for all symbols."""
    try:
        from database.models import BacktestResult
        from sqlalchemy import func
        db = SessionLocal()
        # Get latest result per symbol
        subq = db.query(
            BacktestResult.symbol,
            func.max(BacktestResult.backtest_date).label("latest")
        ).group_by(BacktestResult.symbol).subquery()

        results = db.query(BacktestResult).join(
            subq,
            (BacktestResult.symbol == subq.c.symbol) &
            (BacktestResult.backtest_date == subq.c.latest)
        ).all()

        data = []
        for r in results:
            data.append({
                "symbol": r.symbol,
                "total_return_pct": r.total_return_pct,
                "annual_return_pct": r.annual_return_pct,
                "sharpe_ratio": r.sharpe_ratio,
                "sortino_ratio": r.sortino_ratio,
                "max_drawdown_pct": r.max_drawdown_pct,
                "win_rate_pct": r.win_rate_pct,
                "profit_factor": r.profit_factor,
                "total_trades": r.total_trades,
                "total_fees_paid": r.total_fees_paid,
                "calmar_ratio": r.calmar_ratio,
                "backtest_date": r.backtest_date.isoformat() if r.backtest_date else None,
                "metrics": r.metrics_json,
            })
        db.close()
        return {"results": data, "count": len(data)}
    except Exception as e:
        return {"results": [], "count": 0, "error": str(e)}


@app.get("/api/v1/backtest/results/{symbol}")
def get_backtest_history(symbol: str):
    """Get backtest history for a specific symbol."""
    try:
        from database.models import BacktestResult
        db = SessionLocal()
        results = db.query(BacktestResult).filter(
            BacktestResult.symbol == symbol.upper()
        ).order_by(BacktestResult.backtest_date.desc()).limit(10).all()

        data = [{"metrics": r.metrics_json, "date": r.backtest_date.isoformat() if r.backtest_date else None} for r in results]
        db.close()
        return {"symbol": symbol.upper(), "history": data, "count": len(data)}
    except Exception as e:
        return {"symbol": symbol.upper(), "history": [], "error": str(e)}


@app.get("/api/v1/backtest/summary")
def get_backtest_summary():
    """Portfolio-level summary across all backtested symbols."""
    data = get_backtest_results()
    results = data.get("results", [])
    if not results:
        return {"total_symbols": 0, "avg_sharpe": 0, "avg_win_rate": 0, "avg_drawdown": 0}

    return {
        "total_symbols": len(results),
        "avg_sharpe": round(np.mean([r["sharpe_ratio"] or 0 for r in results]), 3),
        "avg_return_pct": round(np.mean([r["total_return_pct"] or 0 for r in results]), 2),
        "avg_win_rate": round(np.mean([r["win_rate_pct"] or 0 for r in results]), 1),
        "avg_drawdown": round(np.mean([r["max_drawdown_pct"] or 0 for r in results]), 2),
        "best_symbol": max(results, key=lambda r: r.get("total_return_pct", 0))["symbol"] if results else None,
        "worst_symbol": min(results, key=lambda r: r.get("total_return_pct", 0))["symbol"] if results else None,
    }


# ── RL Trading Agent Endpoints ──────────────────────────────

@app.post("/api/v1/rl/train/{symbol}")
def train_rl_symbol(symbol: str, background_tasks: BackgroundTasks):
    """Train RL agent for a single symbol (async)."""
    import uuid
    job_id = f"rl_{uuid.uuid4().hex[:8]}"

    def _run():
        from ml.rl_trader import train_rl_agent
        train_rl_agent(symbol.upper(), episodes=300, job_id=job_id)

    background_tasks.add_task(_run)
    return {"job_id": job_id, "symbol": symbol.upper(), "status": "training started"}


_rl_training_active = False

async def _run_train_all_rl():
    """Run train_all_rl in a thread, managing the global training flag."""
    global _rl_training_active
    _rl_training_active = True
    try:
        from ml.rl_trader import train_all_rl
        await asyncio.to_thread(train_all_rl, force_retrain=False, job_id="auto")
    except Exception as e:
        print(f"[TRAIN_ALL_FATAL] {e}")
        import traceback
        traceback.print_exc()
    finally:
        _rl_training_active = False
        print("[TRAIN_ALL_COMPLETE] Training flag reset")

@app.post("/api/v1/rl/train-all")
async def train_all_rl_endpoint():
    """Train ALL untrained RL symbols in one background task."""
    global _rl_training_active
    if _rl_training_active:
        return {"status": "already_running", "message": "RL training batch is already in progress"}

    asyncio.create_task(_run_train_all_rl())
    return {"status": "started", "message": "Training all symbols in background"}

@app.get("/api/v1/rl/training-status")
def get_rl_training_status():
    """Check if RL batch training is currently running."""
    return {"is_training": _rl_training_active}


@app.get("/api/v1/rl/predict/{symbol}")
def get_rl_prediction_endpoint(symbol: str):
    """Get RL agent's recommendation for today."""
    from ml.rl_trader import get_rl_prediction
    result = get_rl_prediction(symbol.upper())
    if result:
        return result

    # Try yfinance symbol aliases
    for orig, aliases in {
        "BTC-USD": ["BTCUSDC"], "ETH-USD": ["ETHUSDC"],
        "GC=F": ["XAUUSDC"], "^VIX": ["VIX"],
    }.items():
        if symbol.upper() in aliases or symbol.upper() == orig:
            result = get_rl_prediction(orig)
            if result:
                return result

    return {"symbol": symbol.upper(), "action": "HOLD", "confidence": 0.0, "note": "No RL model available"}


@app.get("/api/v1/rl/status")
def get_rl_status():
    """Get RL training status for all symbols."""
    try:
        from database.models import RLModel
        db = SessionLocal()
        models = db.query(RLModel).filter(RLModel.is_best == True).all()
        result = [{
            "symbol": m.symbol,
            "val_sharpe": m.val_sharpe,
            "val_return_pct": m.val_return_pct,
            "total_trades": m.total_trades,
            "episode": m.episode,
            "trained_at": m.trained_at.isoformat() if m.trained_at else None,
        } for m in models]
        db.close()
        return {"models": result, "count": len(result)}
    except Exception as e:
        return {"models": [], "error": str(e)}


@app.get("/api/v1/rl/performance")
def get_rl_performance():
    """Compare RL vs XGBoost vs Buy&Hold."""
    try:
        from database.models import RLModel, BacktestResult
        db = SessionLocal()

        rl_models = db.query(RLModel).filter(RLModel.is_best == True).all()
        bt_results = {}
        for r in db.query(BacktestResult).all():
            bt_results[r.symbol] = r

        comparison = []
        for m in rl_models:
            bt = bt_results.get(m.symbol)
            comparison.append({
                "symbol": m.symbol,
                "rl_sharpe": m.val_sharpe,
                "rl_return_pct": m.val_return_pct,
                "xgb_sharpe": bt.sharpe_ratio if bt else None,
                "xgb_return_pct": bt.total_return_pct if bt else None,
            })
        db.close()
        return {"comparison": comparison, "count": len(comparison)}
    except Exception as e:
        return {"comparison": [], "error": str(e)}


@app.get("/api/v1/rl/predictions/batch")
def get_rl_batch_predictions():
    """Batch RL predictions for all trained symbols."""
    try:
        from database.models import RLModel
        from ml.rl_trader import get_rl_prediction
        db = SessionLocal()
        trained = db.query(RLModel).filter(RLModel.is_best == True).all()
        trained_symbols = [m.symbol for m in trained]

        all_symbols = [
            "BTC-USD","ETH-USD","BNB-USD","XRP-USD","SOL-USD","ADA-USD","AVAX-USD",
            "DOT-USD","LINK-USD","MATIC-USD","AAPL","MSFT","NVDA","GOOGL","AMZN",
            "META","TSLA","ASML","SAP","MC.PA","GC=F","SI=F","PA=F","PL=F","CL=F",
            "ES=F","NQ=F","^TNX","^IRX","^TYX","EURUSD=X","GBPEUR=X","USDJPY=X","^VIX",
        ]

        predictions = {}
        for m in trained:
            try:
                pred = get_rl_prediction(m.symbol)
                predictions[m.symbol] = {
                    "action": pred["action"] if pred else "HOLD",
                    "confidence": float(pred["confidence"]) if pred else 0.0,
                    "val_sharpe": float(m.val_sharpe or 0),
                    "val_return_pct": float(m.val_return_pct or 0),
                }
            except Exception:
                predictions[m.symbol] = {
                    "action": "HOLD", "confidence": 0.0,
                    "val_sharpe": float(m.val_sharpe or 0),
                    "val_return_pct": float(m.val_return_pct or 0),
                }

        db.close()
        return sanitize_floats({
            "predictions": predictions,
            "trained_symbols": trained_symbols,
            "pending_symbols": [s for s in all_symbols if s not in trained_symbols],
            "trained_count": len(trained_symbols),
            "total_count": len(all_symbols),
            "is_training": False,
        })
    except Exception as e:
        return {"predictions": {}, "trained_symbols": [], "pending_symbols": [],
                "trained_count": 0, "total_count": 34, "is_training": False, "error": str(e)}


# ── Sentiment Endpoints (gated behind feature flags) ────────

@app.get("/api/v1/sentiment/{symbol}")
def get_sentiment_for_symbol(symbol: str):
    """Get sentiment score for a single symbol."""
    from config.feature_flags import ENABLE_SENTIMENT_DATA
    if not ENABLE_SENTIMENT_DATA:
        return {"enabled": False, "message": "Sentiment data layer not active"}

    from services.sentiment_scheduler import get_cached_sentiment
    return sanitize_floats(get_cached_sentiment(symbol.upper()))


@app.get("/api/v1/sentiment")
def get_all_sentiment():
    """Get sentiment scores for all tracked symbols."""
    from config.feature_flags import ENABLE_SENTIMENT_DATA
    if not ENABLE_SENTIMENT_DATA:
        return {"enabled": False, "message": "Sentiment data layer not active"}

    from services.sentiment_scheduler import get_all_sentiment as _get_all
    return {"symbols": _get_all()}


@app.get("/api/v1/sentiment/shadow")
def get_sentiment_shadow_report():
    """Run shadow simulation on current predictions and return hypothetical adjustments."""
    from config.feature_flags import ENABLE_SENTIMENT_SHADOW
    if not ENABLE_SENTIMENT_SHADOW:
        return {"enabled": False, "message": "Sentiment shadow mode not active"}

    from services.sentiment_shadow import run_shadow_on_predictions
    predictions = get_all_predictions(days=7)
    if not isinstance(predictions, list):
        return {"shadow_results": [], "error": "Could not load predictions"}

    shadow = run_shadow_on_predictions(predictions)
    adjusted = [s for s in shadow if s["adjustment"] != 0]
    return {
        "total": len(shadow),
        "adjusted_count": len(adjusted),
        "shadow_results": shadow,
    }


@app.get("/api/v1/sentiment/flags")
def get_sentiment_flags():
    """Get current state of all sentiment feature flags (diagnostic)."""
    from config import feature_flags as ff
    return {
        "ENABLE_SENTIMENT": ff.ENABLE_SENTIMENT,
        "ENABLE_SENTIMENT_DATA": ff.ENABLE_SENTIMENT_DATA,
        "ENABLE_SENTIMENT_EXPOSURE": ff.ENABLE_SENTIMENT_EXPOSURE,
        "ENABLE_SENTIMENT_SHADOW": ff.ENABLE_SENTIMENT_SHADOW,
        "ENABLE_SENTIMENT_SOFT": ff.ENABLE_SENTIMENT_SOFT,
        "ENABLE_SENTIMENT_HARD_FILTER": ff.ENABLE_SENTIMENT_HARD_FILTER,
        "ENABLE_META_SENTIMENT": ff.ENABLE_META_SENTIMENT,
        "ENABLE_SENTIMENT_TRAINING": ff.ENABLE_SENTIMENT_TRAINING,
    }

