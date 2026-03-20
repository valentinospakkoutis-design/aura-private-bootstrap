from fastapi import FastAPI, HTTPException, Request, Form, WebSocket, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, EmailStr
from typing import Dict, Optional, List
from datetime import datetime, timedelta
import json
import os
import secrets
import asyncio
import logging
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
from services.idempotency import idempotency_service
from services.risk_governor import risk_governor_service
from ml.annotation_api import router as annotation_router
from auth.dependencies import require_roles, get_request_origin

# Database and Cache imports
from database.connection import init_db, check_db_connection, close_db
from cache.connection import get_redis, check_redis_connection
from services.execution.startup_checks import StartupSafetyError

# Security and Error Handling
from utils.error_handler import handle_error, AuraError, get_error_message
from utils.rate_limiter import rate_limit_middleware, get_client_identifier
from utils.security import security_manager

app = FastAPI(
    title="AURA Backend API",
    description="Backend για το AURA - AI Trading Assistant",
    version="1.0.0"
)

logger = logging.getLogger(__name__)


def _admin_emails() -> set[str]:
    raw = os.getenv("AURA_ADMIN_EMAILS", "")
    return {email.strip().lower() for email in raw.split(",") if email.strip()}


def _resolve_roles(email: str, user_data: Optional[dict] = None) -> List[str]:
    if user_data and isinstance(user_data.get("roles"), list):
        roles = [str(role).strip().lower() for role in user_data.get("roles") if str(role).strip()]
        if roles:
            return sorted(set(roles))

    if user_data and user_data.get("role"):
        role = str(user_data["role"]).strip().lower()
        if role:
            return [role]

    if email.lower() in _admin_emails():
        return ["admin"]

    return ["trader"]

# Startup event - Initialize database and cache
@app.on_event("startup")
async def startup_event():
    """Initialize database and cache on startup"""
    live_trading_service.validate_execution_configuration()
    if live_trading_service.is_live_startup_required():
        live_trading_service.validate_live_startup_preconditions()
    risk_governor_service.restore_enforcement()

    print("[*] Initializing database...")
    try:
        if check_db_connection():
            init_db()
            print("[+] Database initialized")
        else:
            print("[!] Database not configured - continuing without database")
    except Exception as e:
        print(f"[!] Database initialization error: {e}")
        if live_trading_service.is_live_startup_required():
            raise StartupSafetyError("Live startup blocked: database initialization failed") from e
        print("[!] Continuing without database")
    
    print("[*] Checking Redis connection...")
    if check_redis_connection():
        print("[+] Redis connected")
    else:
        print("[!] Redis not configured - continuing without cache")

# Shutdown event
@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
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

# CORS Configuration - Επιτρέπει requests από το mobile app
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Στο production: περιόρισε σε specific domains
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rate Limiting Middleware
@app.middleware("http")
async def rate_limit_middleware_wrapper(request: Request, call_next):
    """Rate limiting middleware wrapper"""
    try:
        return await rate_limit_middleware(request, call_next)
    except Exception as e:
        sensitive_prefixes = (
            "/api/trading",
            "/api/brokers/order",
            "/api/v1/portfolio",
            "/api/paper-trading/reset",
        )
        if any(request.url.path.startswith(prefix) for prefix in sensitive_prefixes):
            logger.error("Rate limiter failure on sensitive route %s: %s", request.url.path, e)
            return JSONResponse(
                status_code=503,
                content={
                    "error": "SECURITY_GUARD_UNAVAILABLE",
                    "message": "Security guard unavailable. Sensitive action blocked.",
                },
            )

        return await call_next(request)

# WebSocket endpoint for real-time price updates
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time price updates"""
    await websocket.accept()
    try:
        while True:
            # Send price updates
            await websocket.send_json({
                "type": "price_update",
                "payload": {
                    "asset": "BTC/USD",
                    "price": 42500.00,
                    "change": 250.00,
                    "changePercentage": 0.59,
                    "timestamp": datetime.utcnow().isoformat() + "Z"
                }
            })
            await asyncio.sleep(5)
    except Exception as e:
        print(f"WebSocket error: {e}")
    finally:
        await websocket.close()

# User storage file
USERS_DB_FILE = os.path.join(os.path.dirname(__file__), "users_db.json")

def load_users_db():
    """Load users from JSON file"""
    if os.path.exists(USERS_DB_FILE):
        try:
            with open(USERS_DB_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading users DB: {e}")
            return {}
    return {}

def save_users_db(users_db):
    """Save users to JSON file"""
    try:
        with open(USERS_DB_FILE, 'w', encoding='utf-8') as f:
            json.dump(users_db, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"Error saving users DB: {e}")
        return False

# Load users on startup
users_db = load_users_db()
print(f"Loaded {len(users_db)} users from database")

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

@app.get("/", response_class=HTMLResponse)
def read_root(request: Request, error: Optional[str] = None, success: Optional[str] = None):
    """Root endpoint - Landing Page"""
    # Check if user is already logged in
    session_id = request.cookies.get("session_id")
    session = get_session(session_id)
    if session:
        # User is logged in, redirect to dashboard
        return RedirectResponse(url="/dashboard", status_code=303)
    
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "error": error,
            "success": success
        }
    )

@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request):
    """Dashboard page - requires authentication"""
    session_id = request.cookies.get("session_id")
    session = get_session(session_id)
    
    if not session:
        # Not logged in, redirect to login
        return RedirectResponse(url="/?error=" + quote("Παρακαλώ συνδεθείτε"), status_code=303)
    
    email = session["email"]
    user = users_db.get(email)
    if not user:
        # User doesn't exist anymore
        return RedirectResponse(url="/?error=" + quote("Ο χρήστης δεν βρέθηκε"), status_code=303)
    
    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "user_name": user["name"],
            "user_email": email
        }
    )

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

@app.get("/debug/users")
def debug_users(user: dict = Depends(require_roles("admin"))):
    """Restricted debug endpoint."""
    if os.getenv("AURA_ENABLE_DEBUG_ENDPOINTS", "false").lower() != "true":
        raise HTTPException(status_code=404, detail="Not found")

    return {
        "total_users": len(users_db),
        "message": "Debug endpoint enabled",
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
    """Login endpoint"""
    # Normalize email and password (lowercase, trim spaces)
    email = email.lower().strip()
    password = password.strip()
    
    # Check if user exists
    if email not in users_db:
        error_msg = quote("Λάθος email ή κωδικός")
        return RedirectResponse(
            url=f"/?error={error_msg}",
            status_code=303
        )

    user_record = users_db[email]
    stored_name = user_record.get("name", user_record.get("full_name", ""))

    password_valid = False
    if "password_hash" in user_record:
        password_valid = security_manager.verify_password(password, user_record["password_hash"])
    elif "password" in user_record:
        # Legacy migration path: verify once, then replace with hash.
        password_valid = user_record["password"] == password
        if password_valid:
            user_record["password_hash"] = security_manager.hash_password(password)
            user_record.pop("password", None)
            user_record["roles"] = _resolve_roles(email, user_record)
            save_users_db(users_db)

    if not password_valid:
        error_msg = quote("Λάθος κωδικός")
        return RedirectResponse(
            url=f"/?error={error_msg}",
            status_code=303
        )

    # Successful login - create session
    logger.info("Web login successful for %s", email)
    session_id = create_session(email)
    
    # Redirect to dashboard with session cookie
    response = RedirectResponse(url="/dashboard", status_code=303)
    response.set_cookie(
        key="session_id",
        value=session_id,
        max_age=86400,  # 24 hours
        httponly=True,
        samesite="lax"
    )
    return response

@app.post("/register")
async def register(
    request: Request,
    name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    confirmPassword: str = Form(...)
):
    """Register endpoint"""
    # Normalize email and password (lowercase, trim spaces)
    email = email.lower().strip()
    name = name.strip()
    password = password.strip()
    confirmPassword = confirmPassword.strip()
    
    # Validate passwords match
    if password != confirmPassword:
        error_msg = quote("Οι κωδικοί δεν ταιριάζουν")
        return RedirectResponse(
            url=f"/?error={error_msg}",
            status_code=303
        )
    
    # Check if user already exists
    if email in users_db:
        error_msg = quote("Το email χρησιμοποιείται ήδη")
        return RedirectResponse(
            url=f"/?error={error_msg}",
            status_code=303
        )
    
    # Validate password strength (basic check)
    if len(password) < 6:
        error_msg = quote("Ο κωδικός πρέπει να έχει τουλάχιστον 6 χαρακτήρες")
        return RedirectResponse(
            url=f"/?error={error_msg}",
            status_code=303
        )

    # Create user with hashed password.
    users_db[email] = {
        "name": name,
        "email": email,
        "password_hash": security_manager.hash_password(password),
        "roles": _resolve_roles(email),
    }

    # Save to file
    if save_users_db(users_db):
        logger.info("User registered successfully: %s", email)
    else:
        logger.warning("User registered but failed to persist: %s", email)
    
    success_msg = quote("Επιτυχής εγγραφή! Μπορείτε τώρα να συνδεθείτε")
    return RedirectResponse(
        url=f"/?success={success_msg}",
        status_code=303
    )

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
        "trading": "paper_mode",
        "connected_brokers": [],
        "timestamp": datetime.now().isoformat()
    }

# Broker Integration Models
class BrokerConnection(BaseModel):
    broker: str
    api_key: str
    api_secret: str
    testnet: bool = True

class OrderRequest(BaseModel):
    broker: str
    symbol: str
    side: str  # BUY or SELL
    quantity: float
    order_type: str = "MARKET"
    price: Optional[float] = None
    stop_loss_price: Optional[float] = None

# Broker Management
broker_instances = {}  # Store active broker connections

@app.post("/api/brokers/connect")
def connect_broker(connection: BrokerConnection, user: dict = Depends(require_roles("admin"))):
    """Συνδέει broker API"""
    try:
        if connection.broker.lower() == "binance":
            broker = BinanceAPI(
                api_key=connection.api_key,
                api_secret=connection.api_secret,
                testnet=connection.testnet
            )
            result = broker.test_connection()
            
            if result["status"] == "connected":
                broker_instances[connection.broker.lower()] = broker
                logger.warning(
                    "CONTROL_CHANGE broker_connect user=%s broker=%s testnet=%s",
                    user["email"],
                    connection.broker,
                    connection.testnet,
                )
                return {
                    "status": "connected",
                    "broker": connection.broker,
                    "message": "Successfully connected",
                    "timestamp": datetime.now().isoformat()
                }
            else:
                raise HTTPException(status_code=400, detail=result.get("message", "Connection failed"))
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported broker: {connection.broker}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/brokers/status")
def get_broker_status():
    """Επιστρέφει κατάσταση brokers"""
    status = []
    for broker_name, broker in broker_instances.items():
        status.append(broker.get_status())
    return {
        "brokers": status,
        "total_connected": len(broker_instances),
        "timestamp": datetime.now().isoformat()
    }

@app.get("/api/brokers/{broker_name}/balance")
def get_broker_balance(broker_name: str):
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

@app.post("/api/brokers/order")
def place_order(
    order: OrderRequest,
    request: Request,
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
    user: dict = Depends(require_roles("trader", "admin")),
):
    """Τοποθετεί order με paper ή real execution ανάλογα με trading mode"""
    if not idempotency_key:
        raise HTTPException(
            status_code=400,
            detail={"error": "IDEMPOTENCY_KEY_REQUIRED", "message": "Idempotency-Key header is required."},
        )

    current_mode = "live" if live_trading_service.trading_mode == "live" else "paper"
    can_execute, block_reason = risk_governor_service.can_execute(mode=current_mode, symbol=order.symbol)
    if not can_execute:
        raise HTTPException(
            status_code=503,
            detail={
                "error": block_reason or "RISK_GOVERNOR_BLOCK",
                "message": "Risk governor blocked new execution.",
            },
        )

    fingerprint = idempotency_service.build_fingerprint(
        {
            "broker": order.broker,
            "symbol": order.symbol,
            "side": order.side,
            "quantity": order.quantity,
            "order_type": order.order_type,
        }
    )
    decision = idempotency_service.begin_request(
        principal_id=user["email"],
        endpoint="/api/brokers/order",
        idempotency_key=idempotency_key,
        request_fingerprint=fingerprint,
    )
    if decision["action"] == "replay":
        return decision["existing"].get("result_payload")
    if decision["action"] == "replay_failed":
        raise HTTPException(
            status_code=409,
            detail={
                "error": "ORDER_PREVIOUSLY_FAILED",
                "message": decision["existing"].get("error_message") or "Previous submission failed",
            },
        )
    if decision["action"] in {"conflict", "in_progress"}:
        raise HTTPException(
            status_code=decision.get("http_status", 409),
            detail={"error": decision["error"], "message": decision["message"]},
        )

    if order.broker.lower() not in broker_instances:
        idempotency_service.finalize_failure(
            principal_id=user["email"],
            endpoint="/api/brokers/order",
            idempotency_key=idempotency_key,
            request_fingerprint=fingerprint,
            error_message="Broker not connected",
        )
        raise HTTPException(status_code=404, detail="Broker not connected")

    broker = broker_instances[order.broker.lower()]

    is_live_mode = live_trading_service.trading_mode == "live"

    if is_live_mode:
        if order.price is None or order.price <= 0:
            idempotency_service.finalize_failure(
                principal_id=user["email"],
                endpoint="/api/brokers/order",
                idempotency_key=idempotency_key,
                request_fingerprint=fingerprint,
                error_message="Price is required for live execution",
            )
            raise HTTPException(
                status_code=400,
                detail={"error": "LIVE_PRICE_REQUIRED", "message": "price must be provided for live orders."},
            )

        portfolio = paper_trading_service.get_portfolio()
        positions = portfolio.get("positions", [])
        validation_result = live_trading_service.validate_order(
            symbol=order.symbol,
            side=order.side,
            quantity=order.quantity,
            price=order.price,
            portfolio_value=portfolio.get("total_value", 0),
            current_positions=positions,
            stop_loss_price=order.stop_loss_price,
        )

        if not validation_result.get("valid", False):
            idempotency_service.finalize_failure(
                principal_id=user["email"],
                endpoint="/api/brokers/order",
                idempotency_key=idempotency_key,
                request_fingerprint=fingerprint,
                error_message="Order validation failed",
            )
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "ORDER_VALIDATION_FAILED",
                    "message": "Live order rejected by pre-trade validation.",
                    "errors": validation_result.get("errors", []),
                },
            )

        result = live_trading_service.execute_live_order(
            broker=order.broker,
            symbol=order.symbol,
            side=order.side,
            quantity=order.quantity,
            order_type=order.order_type,
            validation_result=validation_result,
            idempotency_key=idempotency_key,
            user_email=user["email"],
            user_roles=user.get("roles", []),
            broker_adapter=broker,
            price=order.price,
            stop_loss_price=order.stop_loss_price,
            idempotency_reserved=True,
        )

        if "error" in result:
            idempotency_service.finalize_failure(
                principal_id=user["email"],
                endpoint="/api/brokers/order",
                idempotency_key=idempotency_key,
                request_fingerprint=fingerprint,
                error_message=result.get("error", "Live execution failed"),
            )
            raise HTTPException(
                status_code=int(result.get("status_code", 400)),
                detail=result.get("details") or {
                    "error": result.get("error_code", "LIVE_EXECUTION_FAILED"),
                    "message": result.get("error", "Live execution failed"),
                },
            )

        try:
            live_balance = broker.get_account_balance()
            live_equity = live_trading_service._extract_portfolio_value(live_balance)
            risk_governor_service.update_pnl(
                mode="live",
                equity=live_equity,
                realized_delta=0.0,
                unrealized_pnl=0.0,
                source="live_order_execution",
                symbol=order.symbol,
            )
        except Exception as risk_error:
            logger.error("RISK_GOVERNOR_UPDATE_FAILED mode=live symbol=%s error=%s", order.symbol, risk_error)
    else:
        # Paper mode keeps existing behavior and fetches broker market price.
        price_info = broker.get_market_price(order.symbol)
        if "error" in price_info:
            idempotency_service.finalize_failure(
                principal_id=user["email"],
                endpoint="/api/brokers/order",
                idempotency_key=idempotency_key,
                request_fingerprint=fingerprint,
                error_message="Failed to get market price",
            )
            raise HTTPException(status_code=400, detail="Failed to get market price")

        price = price_info["price"]

        order_dict = {
            "symbol": order.symbol,
            "side": order.side,
            "quantity": order.quantity,
            "price": price,
            "order_type": order.order_type
        }

        result = paper_trading_service.place_order(order_dict)

        if "error" in result:
            idempotency_service.finalize_failure(
                principal_id=user["email"],
                endpoint="/api/brokers/order",
                idempotency_key=idempotency_key,
                request_fingerprint=fingerprint,
                error_message=result["error"],
            )
            raise HTTPException(status_code=400, detail=result["error"])

        try:
            portfolio = paper_trading_service.get_portfolio()
            realized_delta = float(result.get("pnl") or 0.0)
            unrealized_pnl = float(portfolio.get("total_pnl") or 0.0)
            risk_governor_service.update_pnl(
                mode="paper",
                equity=float(portfolio.get("total_value") or 0.0),
                realized_delta=realized_delta,
                unrealized_pnl=unrealized_pnl,
                source="paper_order_execution",
                symbol=order.symbol,
            )
        except Exception as risk_error:
            logger.error("RISK_GOVERNOR_UPDATE_FAILED mode=paper symbol=%s error=%s", order.symbol, risk_error)

    idempotency_service.finalize_success(
        principal_id=user["email"],
        endpoint="/api/brokers/order",
        idempotency_key=idempotency_key,
        request_fingerprint=fingerprint,
        result_order_id=result.get("order_id"),
        result_payload=result,
    )
    return result

@app.get("/api/trading/portfolio")
def get_trading_portfolio(user: dict = Depends(require_roles("viewer", "trader", "admin"))):
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
def get_trading_history(limit: int = 50, user: dict = Depends(require_roles("viewer", "trader", "admin"))):
    """Επιστρέφει trade history"""
    trades = paper_trading_service.get_trade_history(limit)
    return {
        "trades": trades,
        "total": len(paper_trading_service.trade_history),
        "timestamp": datetime.now().isoformat()
    }

@app.get("/api/trading/positions")
def get_positions(user: dict = Depends(require_roles("viewer", "trader", "admin"))):
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
def disconnect_broker(broker_name: str, user: dict = Depends(require_roles("admin"))):
    """Αποσυνδέει broker"""
    if broker_name.lower() in broker_instances:
        del broker_instances[broker_name.lower()]
        logger.warning("CONTROL_CHANGE broker_disconnect user=%s broker=%s", user["email"], broker_name)
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

@app.post("/api/paper-trading/reset")
def reset_paper_trading(user: dict = Depends(require_roles("admin"))):
    """Reset paper trading account"""
    paper_trading_service.reset()
    logger.warning("CONTROL_CHANGE paper_trading_reset user=%s", user["email"])
    return {
        "status": "reset",
        "message": "Paper trading account reset successfully",
        "timestamp": datetime.now().isoformat()
    }

# AI Engine Endpoints - Unified Asset Predictor
@app.get("/api/ai/predict/{symbol}")
def get_prediction(symbol: str, days: int = 7):
    """Επιστρέφει AI prediction για οποιοδήποτε asset (metals, stocks, crypto, derivatives)"""
    return asset_predictor.predict_price(symbol.upper(), days)

@app.get("/api/ai/predictions")
def get_all_predictions(days: int = 7, asset_type: Optional[str] = None):
    """Επιστρέφει predictions για όλα τα assets ή filtered by type"""
    asset_type_enum = None
    if asset_type:
        try:
            asset_type_enum = AssetType(asset_type.lower())
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid asset type: {asset_type}")
    
    return asset_predictor.get_all_predictions(days, asset_type_enum)

@app.get("/api/ai/signal/{symbol}")
def get_trading_signal(symbol: str):
    """Επιστρέφει trading signal για οποιοδήποτε asset"""
    return asset_predictor.get_trading_signal(symbol.upper())

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
    return precious_metals_predictor.predict_price(symbol.upper(), days)

@app.get("/api/ai/predictions/metals")
def get_metals_predictions(days: int = 7):
    """Legacy endpoint - Επιστρέφει predictions για όλα τα precious metals"""
    return precious_metals_predictor.get_all_predictions(days)

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
                "XAUUSDT": 2050.0,
                "XAGUSDT": 24.5,
                "XPTUSDT": 950.0,
                "XPDUSDT": 1200.0
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


class FirstLiveDryRunRequest(BaseModel):
    broker: str
    symbol: str
    side: str
    quantity: float
    order_type: str = "MARKET"
    price: float


class KillSwitchRequest(BaseModel):
    active: bool
    scope: str = "global"
    value: Optional[str] = None
    reason: Optional[str] = None
    emergency: bool = False
    cancel_open_orders: bool = False

@app.get("/api/trading/mode")
def get_trading_mode(user: dict = Depends(require_roles("admin"))):
    """Επιστρέφει current trading mode"""
    return live_trading_service.get_trading_mode()

@app.post("/api/trading/mode")
def set_trading_mode(
    request: TradingModeRequest,
    raw_request: Request,
    user: dict = Depends(require_roles("admin")),
):
    """Ορίζει trading mode (paper/live)"""
    previous_mode = live_trading_service.trading_mode
    result = live_trading_service.set_trading_mode(request.mode)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    logger.warning(
        "CONTROL_CHANGE trading_mode user=%s origin=%s previous=%s new=%s",
        user["email"],
        get_request_origin(raw_request),
        previous_mode,
        request.mode,
    )
    return result

@app.get("/api/trading/risk-settings")
def get_risk_settings(user: dict = Depends(require_roles("admin"))):
    """Επιστρέφει risk management settings"""
    return {
        "risk_settings": live_trading_service.risk_settings,
        "daily_stats": live_trading_service.daily_stats,
        "timestamp": datetime.now().isoformat()
    }

@app.put("/api/trading/risk-settings")
def update_risk_settings(
    settings: RiskSettingsUpdate,
    request: Request,
    user: dict = Depends(require_roles("admin")),
):
    """Ενημερώνει risk management settings"""
    previous = dict(live_trading_service.risk_settings)
    changes = settings.dict(exclude_unset=True)
    result = live_trading_service.update_risk_settings(changes)
    logger.warning(
        "CONTROL_CHANGE risk_settings user=%s origin=%s previous=%s new=%s",
        user["email"],
        get_request_origin(request),
        previous,
        changes,
    )
    return result

@app.post("/api/trading/validate-order")
def validate_order(request: OrderValidationRequest, user: dict = Depends(require_roles("trader", "admin"))):
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


@app.post("/api/trading/first-live/dry-run")
def first_live_dry_run(
    payload: FirstLiveDryRunRequest,
    user: dict = Depends(require_roles("trader", "admin")),
):
    if payload.broker.lower() not in broker_instances:
        raise HTTPException(
            status_code=404,
            detail={"error": "BROKER_NOT_CONNECTED", "message": "Broker not connected."},
        )

    portfolio = paper_trading_service.get_portfolio()
    positions = portfolio.get("positions", [])
    broker = broker_instances[payload.broker.lower()]

    try:
        result = live_trading_service.run_first_live_dry_run(
            broker=payload.broker,
            symbol=payload.symbol,
            side=payload.side,
            quantity=payload.quantity,
            order_type=payload.order_type,
            price=payload.price,
            broker_adapter=broker,
            portfolio_value=float(portfolio.get("total_value", 0) or 0.0),
            current_positions=positions,
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail={"error": "FIRST_LIVE_DRY_RUN_FAILED", "message": str(exc)},
        )

    if not result.get("valid", False):
        raise HTTPException(
            status_code=400,
            detail={
                "error": result.get("error", "FIRST_LIVE_DRY_RUN_REJECTED"),
                "message": "First-live dry-run validation failed.",
                "details": result.get("details"),
            },
        )

    return {
        "status": "pass",
        "dry_run": result,
        "timestamp": datetime.now().isoformat(),
        "operator": user.get("email"),
    }

@app.post("/api/trading/calculate-position")
def calculate_position_size(
    symbol: str,
    side: str,
    price: float,
    risk_percent: Optional[float] = None,
    user: dict = Depends(require_roles("trader", "admin")),
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
def get_risk_summary(user: dict = Depends(require_roles("trader", "admin"))):
    """Επιστρέφει risk management summary"""
    portfolio = paper_trading_service.get_portfolio()
    return live_trading_service.get_risk_summary(portfolio.get("total_value", 0))


@app.post("/api/trading/kill-switch")
def set_kill_switch(
    payload: KillSwitchRequest,
    request: Request,
    user: dict = Depends(require_roles("admin")),
):
    result = live_trading_service.set_kill_switch(
        payload.active,
        actor=user["email"],
        scope=payload.scope,
        value=payload.value,
        reason=payload.reason,
        emergency=payload.emergency,
        cancel_open_orders=payload.cancel_open_orders,
    )
    logger.warning(
        "CONTROL_CHANGE kill_switch user=%s origin=%s active=%s scope=%s value=%s emergency=%s",
        user["email"],
        get_request_origin(request),
        payload.active,
        payload.scope,
        payload.value,
        payload.emergency,
    )
    return result


@app.post("/api/trading/kill-switch/enable")
def enable_kill_switch(
    payload: KillSwitchRequest,
    request: Request,
    user: dict = Depends(require_roles("admin")),
):
    result = live_trading_service.set_kill_switch(
        True,
        actor=user["email"],
        scope=payload.scope,
        value=payload.value,
        reason=payload.reason,
        emergency=payload.emergency,
        cancel_open_orders=payload.cancel_open_orders,
    )
    logger.warning(
        "CONTROL_CHANGE kill_switch_enable user=%s origin=%s scope=%s value=%s",
        user["email"],
        get_request_origin(request),
        payload.scope,
        payload.value,
    )
    return result


@app.post("/api/trading/kill-switch/disable")
def disable_kill_switch(
    payload: KillSwitchRequest,
    request: Request,
    user: dict = Depends(require_roles("admin")),
):
    result = live_trading_service.set_kill_switch(
        False,
        actor=user["email"],
        scope=payload.scope,
        value=payload.value,
        reason=payload.reason,
    )
    logger.warning(
        "CONTROL_CHANGE kill_switch_disable user=%s origin=%s scope=%s value=%s",
        user["email"],
        get_request_origin(request),
        payload.scope,
        payload.value,
    )
    return result


@app.get("/api/trading/kill-switch/status")
def get_kill_switch_status(user: dict = Depends(require_roles("admin"))):
    return live_trading_service.get_kill_switch_status()


@app.get("/api/trading/risk-governor/status")
def get_risk_governor_status(
    mode: Optional[str] = None,
    user: dict = Depends(require_roles("trader", "admin")),
):
    selected_mode = (mode or live_trading_service.trading_mode or "paper").strip().lower()
    if selected_mode not in {"paper", "live"}:
        raise HTTPException(status_code=400, detail={"error": "INVALID_MODE", "message": "mode must be paper or live"})
    return risk_governor_service.get_status(mode=selected_mode)


@app.post("/api/trading/reconciliation/run")
def run_reconciliation(
    limit: int = 100,
    request: Request = None,
    user: dict = Depends(require_roles("admin")),
):
    result = live_trading_service.reconcile_live_orders(broker_instances, limit=limit)
    logger.warning(
        "CONTROL_CHANGE reconciliation_run user=%s origin=%s checked=%s updated=%s flagged=%s",
        user["email"],
        get_request_origin(request) if request else "unknown",
        result.get("checked"),
        result.get("updated"),
        result.get("flagged"),
    )
    return result

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
