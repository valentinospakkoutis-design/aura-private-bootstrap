from fastapi import FastAPI, HTTPException, Request, Form, WebSocket, Depends, Query, BackgroundTasks, UploadFile, File
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
from sqlalchemy import text
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
from scheduler.cron_tasks import TASK_MAP as CRON_TASK_MAP, run_named_task as run_cron_named_task

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


SYMBOL_ALIASES = {
    "BTC-USD": "BTCUSDC",
    "ETH-USD": "ETHUSDC",
    "SOL-USD": "SOLUSDC",
    "ADA-USD": "ADAUSDC",
    "BNB-USD": "BNBUSDC",
    "AVAX-USD": "AVAXUSDC",
    "DOT-USD": "DOTUSDC",
    "MATIC-USD": "MATICUSDC",
}


def normalize_symbol_alias(symbol: str) -> str:
    """Normalize known aliases (e.g. BTC-USD -> BTCUSDC) for Redis/model lookups."""
    symbol_u = (symbol or "").upper()
    return SYMBOL_ALIASES.get(symbol_u, symbol_u)

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


LEGACY_SEED_USER_ID = 5


def _extract_user_id(payload: Optional[dict]) -> Optional[int]:
    """Extract int user_id from JWT payload supporting legacy key names."""
    if not isinstance(payload, dict):
        return None
    raw = payload.get("sub", payload.get("user_id"))
    try:
        return int(raw) if raw is not None else None
    except (TypeError, ValueError):
        return None


def _legacy_allowed_for_user(user_id: Optional[int]) -> bool:
    """Only seed user can read legacy NULL-user rows."""
    return user_id == LEGACY_SEED_USER_ID


def _optional_user_id_from_request(request: Request) -> Optional[int]:
    """Best-effort JWT parse for routes that remain backward-compatible without auth."""
    auth = request.headers.get("authorization", "")
    if not auth.lower().startswith("bearer "):
        return None
    token = auth.split(" ", 1)[1].strip()
    if not token:
        return None
    try:
        from auth.jwt_handler import verify_token
        payload = verify_token(token, "access")
        return _extract_user_id(payload)
    except Exception:
        return None


@app.get("/healthz")
def healthz():
    return {"ok": True}

@app.get("/api/ping")
def api_ping():
    return {"ok": True}


@app.get("/api/myip")
async def get_my_ip():
    """Returns the outbound IP of this server (for Binance IP whitelist)."""
    import httpx
    async with httpx.AsyncClient(timeout=5.0) as client:
        response = await client.get("https://api.ipify.org?format=json")
        return response.json()


@app.get("/api/debug/binance-key")
def debug_binance_key(_user=Depends(require_auth)):
    """TEMPORARY debug endpoint — shows key metadata, not actual keys."""
    if not broker_instances:
        _restore_broker_connections()
    if not broker_instances:
        return {"error": "No broker connected"}
    broker = next(iter(broker_instances.values()))
    key = broker.api_key or ""
    secret = broker.api_secret or ""
    return {
        "key_prefix": key[:8] if key else "NONE",
        "secret_prefix": secret[:8] if secret else "NONE",
        "key_length": len(key),
        "secret_length": len(secret),
        "testnet": broker.testnet,
        "connected": broker.connected,
        "base_url": broker.base_url,
    }


def _broker_cache_key(broker_name: str, user_id: Optional[int] = None) -> str:
    broker_name = broker_name.lower()
    return f"u:{user_id}:{broker_name}" if user_id is not None else broker_name


def _get_broker_instance_for_user(broker_name: str, user_id: Optional[int]) -> Optional[object]:
    """Resolve broker by current user, with seed-user legacy fallback."""
    key_user = _broker_cache_key(broker_name, user_id)
    if key_user in broker_instances:
        return broker_instances[key_user]

    if _legacy_allowed_for_user(user_id):
        key_legacy = _broker_cache_key(broker_name, None)
        if key_legacy in broker_instances:
            return broker_instances[key_legacy]
    return None


def _restore_broker_connections(user_id: Optional[int] = None):
    """Restore broker connections from database (all users or one user's scope)."""
    try:
        from sqlalchemy import or_ as _or
        db = SessionLocal()
        q = db.query(BrokerCredential).filter(BrokerCredential.is_active == True)
        if user_id is not None:
            if _legacy_allowed_for_user(user_id):
                q = q.filter(_or(BrokerCredential.user_id == user_id, BrokerCredential.user_id.is_(None)))
            else:
                q = q.filter(BrokerCredential.user_id == user_id)
        rows = q.all()
        loaded = 0
        for row in rows:
            try:
                api_key = security_manager.decrypt_api_key(row.encrypted_api_key)
                api_secret = security_manager.decrypt_api_key(row.encrypted_api_secret)
                if row.broker_name == "bybit":
                    from brokers.bybit import BybitAPI
                    broker = BybitAPI(api_key=api_key, api_secret=api_secret, testnet=row.testnet)
                else:
                    broker = BinanceAPI(api_key=api_key, api_secret=api_secret, testnet=row.testnet)
                broker.connected = True
                broker_instances[_broker_cache_key(row.broker_name, row.user_id)] = broker
                if row.user_id is None:
                    # Keep legacy plain key for backward compatibility.
                    broker_instances[_broker_cache_key(row.broker_name, None)] = broker
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
            db = SessionLocal()
            try:
                db.execute(
                    text(
                        """
                        CREATE TABLE IF NOT EXISTS cron_runs (
                            id SERIAL PRIMARY KEY,
                            task_name VARCHAR(50) NOT NULL,
                            status VARCHAR(20) NOT NULL,
                            started_at TIMESTAMP DEFAULT NOW(),
                            finished_at TIMESTAMP,
                            details TEXT
                        )
                        """
                    )
                )
                db.execute(
                    text(
                        """
                        CREATE TABLE IF NOT EXISTS rl_trade_outcomes (
                            id SERIAL PRIMARY KEY,
                            symbol VARCHAR(20) NOT NULL,
                            action VARCHAR(10) NOT NULL,
                            entry_price FLOAT NOT NULL,
                            exit_price FLOAT NOT NULL,
                            pnl_pct FLOAT NOT NULL,
                            reward FLOAT NOT NULL,
                            confidence FLOAT,
                            recorded_at TIMESTAMP DEFAULT NOW()
                        )
                        """
                    )
                )
                db.execute(
                    text(
                        """
                        CREATE INDEX IF NOT EXISTS idx_rl_outcomes_symbol
                        ON rl_trade_outcomes(symbol, recorded_at DESC)
                        """
                    )
                )
                db.execute(
                    text(
                        """
                        ALTER TABLE IF EXISTS rl_predictions
                        ADD COLUMN IF NOT EXISTS agent_version VARCHAR(20) DEFAULT 'v1.0'
                        """
                    )
                )
                db.commit()
            except Exception:
                db.rollback()
                print("[!] Failed to ensure cron_runs table")
            finally:
                db.close()
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

    # Start auto trading engine (per-user isolated loop)
    from services.auto_trading_engine import auto_trader as _auto_trader

    async def _get_predictions_for_auto_trader(_user_id: int):
        """Fetch predictions for auto trader loop. Only USDC crypto pairs."""
        from services.auto_trading_engine import ALLOWED_AUTO_TRADE_SYMBOLS
        from ml.predictor import get_ensemble_prediction
        from ml.regime_detector import get_current_regime

        result = []
        redis_client = get_redis()
        regime = get_current_regime(redis_client)
        regime_mult = float(regime.get("confidence_multiplier", 0.5) or 0.5)

        for sym in sorted(ALLOWED_AUTO_TRADE_SYMBOLS):
            p = get_ensemble_prediction(sym, features={})
            if "error" in p:
                continue

            raw_conf = float(p.get("confidence", 0.0) or 0.0)
            conf = max(0.0, min(1.0, raw_conf * regime_mult))

            action = str(p.get("action", "HOLD") or "HOLD").lower()
            if conf < 0.60:
                action = "hold"

            ap = p.get("raw", {}).get("asset_predictor", {}) if isinstance(p.get("raw"), dict) else {}
            if sym not in ALLOWED_AUTO_TRADE_SYMBOLS:
                continue
            result.append({
                "symbol": sym,
                "action": action,
                "confidence": conf,
                "price": ap.get("current_price", 0),
                "targetPrice": ap.get("predicted_price", 0),
            })
        return result

    def _get_active_autopilot_users() -> List[int]:
        """Users with enabled auto-trading settings."""
        try:
            from database.models import UserAutopilotSettings, AutopilotConfig
            db = SessionLocal()
            user_ids = set(
                int(r.user_id)
                for r in db.query(UserAutopilotSettings.user_id).filter(
                    UserAutopilotSettings.is_enabled == True
                ).all()
            )
            user_ids.update(
                int(r.user_id)
                for r in db.query(AutopilotConfig.user_id).filter(
                    AutopilotConfig.is_enabled == True
                ).all()
            )
            db.close()
            return sorted(user_ids)
        except Exception:
            return []

    def _get_user_engine_config(user_id: int) -> Dict:
        """Get normalized per-user engine config from persisted autopilot settings."""
        try:
            from services.autopilot_config import get_user_autopilot
            settings = get_user_autopilot(user_id)
            cfg = dict(settings.get("engine_config", {}))
            overrides = settings.get("config_overrides", {}) or {}
            if isinstance(overrides, dict):
                cfg.update(overrides)
            cfg["enabled"] = bool(settings.get("is_enabled", False))
            return cfg
        except Exception:
            return {"enabled": False}

    def _get_user_broker(user_id: int):
        broker = _get_broker_instance_for_user("binance", user_id) or _get_broker_instance_for_user("bybit", user_id)
        if not broker:
            _restore_broker_connections(user_id=user_id)
            broker = _get_broker_instance_for_user("binance", user_id) or _get_broker_instance_for_user("bybit", user_id)
        return broker

    asyncio.create_task(
        _auto_trader.run_per_user(
            _get_predictions_for_auto_trader,
            _get_active_autopilot_users,
            _get_user_broker,
            _get_user_engine_config,
        )
    )
    print("[+] Auto trading engine initialized (per-user mode)")

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

    # Start scheduled jobs (fear_greed, news_fetch, weekly retrain, daily XGBoost, daily predictions)
    try:
        from ml.auto_trainer import setup_weekly_retraining
        setup_weekly_retraining()
        print("[+] Scheduled jobs: fear_greed (daily 00:30), news_fetch (daily 06:00), weekly_retrain (Sun 00:00), daily_predictions (06:05)")
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
from api.mettal_endpoints import router as mettal_router, health_router
app.include_router(health_router)
app.include_router(mettal_router)
print(f"[+] Loaded mettal endpoints: {len(mettal_router.routes)} routes")


def _run_cron_task_sync(task_name: str):
    """Run cron task in a background thread with an isolated asyncio loop."""
    try:
        asyncio.run(run_cron_named_task(task_name))
    except Exception as e:
        print(f"[CRON] task {task_name} failed: {e}")


@app.post("/api/v1/cron/trigger/{task_name}", tags=["cron"])
async def trigger_cron_task(task_name: str, background_tasks: BackgroundTasks):
    """Manually trigger a cron task (for testing)."""
    if task_name not in CRON_TASK_MAP:
        raise HTTPException(
            status_code=400,
            detail={
                "error": f"Unknown task: {task_name}",
                "available": list(CRON_TASK_MAP.keys()),
            },
        )

    background_tasks.add_task(_run_cron_task_sync, task_name)
    return {"status": "started", "task": task_name}


@app.get("/api/v1/cron/last-run", tags=["cron"])
async def get_cron_last_run():
    """Return last run time of each cron task from cron_runs table."""
    if SessionLocal is None:
        raise HTTPException(status_code=503, detail="Database not available")

    db = SessionLocal()
    try:
        rows = db.execute(
            text(
                """
                SELECT task_name, status, started_at, finished_at, details
                FROM (
                    SELECT
                        task_name,
                        status,
                        started_at,
                        finished_at,
                        details,
                        ROW_NUMBER() OVER (PARTITION BY task_name ORDER BY started_at DESC) AS rn
                    FROM cron_runs
                ) t
                WHERE rn = 1
                ORDER BY task_name ASC
                """
            )
        ).mappings().all()

        data = [
            {
                "task_name": row["task_name"],
                "status": row["status"],
                "started_at": row["started_at"].isoformat() if row["started_at"] else None,
                "finished_at": row["finished_at"].isoformat() if row["finished_at"] else None,
                "details": row["details"],
            }
            for row in rows
        ]
        return {"tasks": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load cron runs: {e}")
    finally:
        db.close()

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

@app.get("/debug/users")
def debug_users():
    """Debug endpoint - Shows registered users (remove in production!)"""
    return {
        "total_users": len(users_db),
        "users": {email: {"name": data["name"], "password_length": len(data["password"])} 
                  for email, data in users_db.items()}
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

        created_user = db.query(_User).filter(_User.email == email).first()
        if created_user:
            try:
                from services.subscription_service import ensure_user_subscription
                ensure_user_subscription(created_user.id, db=db)
            except Exception:
                pass

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
async def connect_broker(connection: BrokerConnection, payload=Depends(require_auth)):
    """Συνδέει broker API"""
    user_id = _extract_user_id(payload)
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
                broker_instances[_broker_cache_key(connection.broker.lower(), user_id)] = broker
                # Persist to database (sync DB in threadpool)
                await asyncio.to_thread(
                    _save_broker_to_db,
                    connection.broker.lower(),
                    connection.api_key,
                    connection.api_secret,
                    connection.testnet,
                    user_id,
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
        elif connection.broker.lower() == "bybit":
            from brokers.bybit import BybitAPI
            broker = BybitAPI(
                api_key=connection.api_key,
                api_secret=connection.api_secret,
                testnet=connection.testnet
            )
            print(f"[broker] Testing connection to {'testnet' if connection.testnet else 'LIVE'} Bybit...")
            result = await asyncio.to_thread(broker.test_connection)
            print(f"[broker] Connection result: {result.get('status', 'unknown')}")

            if result["status"] == "connected":
                broker_instances[_broker_cache_key(connection.broker.lower(), user_id)] = broker
                await asyncio.to_thread(
                    _save_broker_to_db,
                    connection.broker.lower(),
                    connection.api_key,
                    connection.api_secret,
                    connection.testnet,
                    user_id,
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


def _save_broker_to_db(broker_name: str, api_key: str, api_secret: str, testnet: bool, user_id: Optional[int] = None):
    """Save broker credentials to database (sync, runs in threadpool)."""
    db = SessionLocal()
    try:
        from sqlalchemy import or_ as _or
        enc_key = security_manager.encrypt_api_key(api_key)
        enc_secret = security_manager.encrypt_api_key(api_secret)

        if user_id is None:
            row = db.query(BrokerCredential).filter(
                BrokerCredential.broker_name == broker_name,
                BrokerCredential.user_id.is_(None),
            ).first()
        elif _legacy_allowed_for_user(user_id):
            row = db.query(BrokerCredential).filter(
                BrokerCredential.broker_name == broker_name,
                _or(BrokerCredential.user_id == user_id, BrokerCredential.user_id.is_(None)),
            ).first()
        else:
            row = db.query(BrokerCredential).filter(
                BrokerCredential.broker_name == broker_name,
                BrokerCredential.user_id == user_id,
            ).first()

        if row:
            row.encrypted_api_key = enc_key
            row.encrypted_api_secret = enc_secret
            row.testnet = testnet
            row.is_active = True
            row.updated_at = datetime.utcnow()
        else:
            db.add(BrokerCredential(
                user_id=user_id,
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
        broker_instances.pop(_broker_cache_key(broker_name, user_id), None)
        raise HTTPException(
            status_code=500,
            detail=f"Broker connected but failed to save credentials: {db_err}"
        )
    finally:
        db.close()

@app.get("/api/brokers/status")
def get_broker_status(payload=Depends(require_auth)):
    """Επιστρέφει κατάσταση brokers"""
    user_id = _extract_user_id(payload)
    # Auto-reload from DB if no brokers in memory
    _restore_broker_connections(user_id=user_id)

    status = []
    seen = set()
    for key, broker in broker_instances.items():
        if user_id is None:
            continue
        if key.startswith(f"u:{user_id}:"):
            name = key.split(":", 2)[2]
        elif _legacy_allowed_for_user(user_id) and ":" not in key:
            name = key
        else:
            continue
        if name in seen:
            continue
        seen.add(name)
        row = broker.get_status()
        row["broker"] = name
        status.append(row)
    return {
        "brokers": status,
        "total_connected": len(status),
        "timestamp": datetime.now().isoformat()
    }

@app.get("/api/brokers/{broker_name}/balance")
def get_broker_balance(broker_name: str, payload=Depends(require_auth)):
    """Επιστρέφει balance από broker"""
    user_id = _extract_user_id(payload)
    broker = _get_broker_instance_for_user(broker_name.lower(), user_id)
    if not broker:
        _restore_broker_connections(user_id=user_id)
        broker = _get_broker_instance_for_user(broker_name.lower(), user_id)
    if not broker:
        raise HTTPException(status_code=404, detail="Broker not connected for current user")
    
    return broker.get_account_balance()

@app.get("/api/brokers/{broker_name}/price/{symbol}")
def get_price(broker_name: str, symbol: str, request: Request):
    """Επιστρέφει τιμή symbol"""
    user_id = _optional_user_id_from_request(request)
    broker = _get_broker_instance_for_user(broker_name.lower(), user_id)
    if not broker:
        _restore_broker_connections(user_id=user_id)
        broker = _get_broker_instance_for_user(broker_name.lower(), user_id)
    if not broker:
        raise HTTPException(status_code=404, detail="Broker not connected")

    return broker.get_market_price(symbol)

@app.get("/api/brokers/{broker_name}/symbols")
def get_supported_symbols(broker_name: str, request: Request):
    """Επιστρέφει supported symbols"""
    user_id = _optional_user_id_from_request(request)
    broker = _get_broker_instance_for_user(broker_name.lower(), user_id)
    if not broker:
        _restore_broker_connections(user_id=user_id)
        broker = _get_broker_instance_for_user(broker_name.lower(), user_id)
    if not broker:
        raise HTTPException(status_code=404, detail="Broker not connected")

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
    user_id = _extract_user_id(_user)

    # Auto-reload from DB if broker not in memory
    broker = _get_broker_instance_for_user(broker_key, user_id)
    if not broker:
        _restore_broker_connections(user_id=user_id)
        broker = _get_broker_instance_for_user(broker_key, user_id)
    if not broker:
        raise HTTPException(status_code=404, detail="Broker not connected. Please connect via /api/brokers/connect")

    # Get current market price
    price_info = broker.get_market_price(order.symbol)
    if "error" in price_info:
        raise HTTPException(status_code=400, detail="Failed to get market price")

    price = price_info["price"]

    if live_trading_service.trading_mode == "live":
        _enforce_live_kill_switch()
        _pre_order_safety_check(broker, order.symbol, order.quantity)

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

        client_order_id = _generate_client_order_id()
        execution_result = broker.place_live_order(
            symbol=order.symbol,
            side=order.side,
            quantity=order.quantity,
            order_type=order.order_type,
            client_order_id=client_order_id,
        )

        # Audit log
        _log_live_order_audit(
            source="api_trading_order", symbol=order.symbol, side=order.side,
            quantity=order.quantity, price=price, client_order_id=client_order_id,
            status="filled" if "error" not in execution_result else "failed",
            broker_order_id=execution_result.get("order_id"),
            response_summary={"status": execution_result.get("status")},
            error_message=execution_result.get("error"),
            user_id=user_id,
        )

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
        result = paper_trading_service.place_order(order_dict, user_id=user_id)

    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    earned = []
    if user_id is not None:
        try:
            from services.achievements import check_and_award
            earned = check_and_award(user_id, "trade_placed")
        except Exception:
            earned = []

    if isinstance(result, dict):
        result["achievements_earned"] = earned

    return result

@app.get("/api/trading/portfolio")
def get_trading_portfolio(request: Request):
    """Επιστρέφει portfolio — live Binance balance αν υπάρχει broker, αλλιώς paper."""
    user_id = _optional_user_id_from_request(request)
    if live_trading_service.trading_mode == "live":
        try:
            broker = _get_broker_instance_for_user("binance", user_id) or _get_broker_instance_for_user("bybit", user_id)
            if not broker:
                _restore_broker_connections(user_id=user_id)
                broker = _get_broker_instance_for_user("binance", user_id) or _get_broker_instance_for_user("bybit", user_id)
            if not broker:
                raise RuntimeError("no user broker")
            account = broker.get_account_balance()
            if "error" not in account:
                return sanitize_floats({
                    "total_value": account.get("total_balance", 0),
                    "cash": account.get("available_balance", 0),
                    "locked": account.get("locked_balance", 0),
                    "positions": [],
                    "mode": "live",
                    "broker": "binance",
                })
        except Exception as e:
            print(f"[!] Live portfolio fetch failed, falling back to paper: {e}")

    # Fallback: paper trading
    current_prices = {}
    for broker_name, broker in broker_instances.items():
        for symbol in broker.get_supported_symbols():
            try:
                price_info = broker.get_market_price(symbol)
                current_prices[symbol] = price_info["price"]
            except:
                pass
    result = paper_trading_service.get_portfolio(current_prices, user_id=user_id)
    result["mode"] = "paper"
    return result


@app.get("/api/live-trading/portfolio/full")
def get_live_portfolio_full():
    """Returns full Binance portfolio with per-asset USDC values."""
    if not broker_instances:
        _restore_broker_connections()
    if not broker_instances:
        raise HTTPException(status_code=400, detail="No broker connected")

    broker = next(iter(broker_instances.values()))
    account_info = broker._signed_request("GET", "/api/v3/account")
    if "error" in account_info:
        raise HTTPException(status_code=400, detail=account_info["error"])

    # Get all balances > 0
    balances = []
    for item in account_info.get("balances", []):
        free = float(item.get("free", 0))
        locked = float(item.get("locked", 0))
        total = free + locked
        if total > 0:
            balances.append({
                "asset": item["asset"],
                "free": free,
                "locked": locked,
                "total": total,
            })

    # Get USDC values via ticker prices
    positions = []
    total_value_usdc = 0.0
    for bal in balances:
        asset = bal["asset"]
        if asset in ("USDC", "USDT", "BUSD", "USD"):
            value_usdc = bal["total"]
        else:
            price = broker.get_symbol_price(f"{asset}USDC")
            if price <= 0:
                price = broker.get_symbol_price(f"{asset}USDT")
            value_usdc = bal["total"] * price if price > 0 else 0
        total_value_usdc += value_usdc
        positions.append({
            "symbol": asset,
            "amount": bal["total"],
            "free": bal["free"],
            "locked": bal["locked"],
            "value_usdc": round(value_usdc, 2),
        })

    # Sort by value descending
    positions.sort(key=lambda p: p["value_usdc"], reverse=True)

    return sanitize_floats({
        "total_value": round(total_value_usdc, 2),
        "cash": next((p["amount"] for p in positions if p["symbol"] == "USDC"), 0),
        "positions": positions,
        "mode": "live",
    })

@app.get("/api/trading/history")
def get_trading_history(request: Request, limit: int = 50):
    """Επιστρέφει trade history"""
    user_id = _optional_user_id_from_request(request)
    trades = paper_trading_service.get_trade_history(limit, user_id=user_id)
    return {
        "trades": trades,
        "total": len(paper_trading_service.get_trade_history(limit=10000, user_id=user_id)),
        "timestamp": datetime.now().isoformat()
    }

@app.get("/api/trading/positions")
def get_positions(request: Request):
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
    
    user_id = _optional_user_id_from_request(request)
    portfolio = paper_trading_service.get_portfolio(current_prices, user_id=user_id)
    
    return {
        "positions": portfolio["positions"],
        "count": len(portfolio["positions"]),
        "timestamp": datetime.now().isoformat()
    }

@app.delete("/api/brokers/{broker_name}/disconnect")
def disconnect_broker(broker_name: str, payload=Depends(require_auth)):
    """Αποσυνδέει broker"""
    user_id = _extract_user_id(payload)
    cache_key = _broker_cache_key(broker_name.lower(), user_id)
    legacy_key = _broker_cache_key(broker_name.lower(), None)

    if cache_key in broker_instances:
        del broker_instances[cache_key]
    elif _legacy_allowed_for_user(user_id) and legacy_key in broker_instances:
        del broker_instances[legacy_key]

    # Remove from database
    try:
        from sqlalchemy import or_ as _or
        db = SessionLocal()
        q = db.query(BrokerCredential).filter(BrokerCredential.broker_name == broker_name.lower())
        if _legacy_allowed_for_user(user_id):
            q = q.filter(_or(BrokerCredential.user_id == user_id, BrokerCredential.user_id.is_(None)))
        else:
            q = q.filter(BrokerCredential.user_id == user_id)
        updated = q.update({"is_active": False})
        db.commit()
        db.close()
        if updated <= 0:
            raise HTTPException(status_code=404, detail="Broker not found for current user")
    except HTTPException:
        raise
    except Exception as db_err:
        print(f"[!] Could not update broker in DB: {db_err}")

    return {
        "status": "disconnected",
        "broker": broker_name,
        "timestamp": datetime.now().isoformat()
    }


# Paper Trading Endpoints
@app.get("/api/paper-trading/portfolio")
def get_portfolio(request: Request):
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
    
    user_id = _optional_user_id_from_request(request)
    return paper_trading_service.get_portfolio(current_prices, user_id=user_id)

@app.get("/api/paper-trading/history")
def get_trade_history(request: Request, limit: int = 50):
    """Επιστρέφει trade history"""
    user_id = _optional_user_id_from_request(request)
    return {
        "trades": paper_trading_service.get_trade_history(limit, user_id=user_id),
        "total": len(paper_trading_service.get_trade_history(limit=10000, user_id=user_id)),
        "timestamp": datetime.now().isoformat()
    }

@app.get("/api/paper-trading/statistics")
def get_trading_statistics(request: Request):
    """Επιστρέφει trading statistics — live Binance data αν mode=live."""
    user_id = _optional_user_id_from_request(request)
    if live_trading_service.trading_mode == "live":
        try:
            broker = _get_broker_instance_for_user("binance", user_id) or _get_broker_instance_for_user("bybit", user_id)
            if not broker:
                _restore_broker_connections(user_id=user_id)
                broker = _get_broker_instance_for_user("binance", user_id) or _get_broker_instance_for_user("bybit", user_id)
            if not broker:
                raise RuntimeError("no user broker")
            account = broker.get_account_balance()
            if "error" not in account:
                total_balance = account.get("total_balance", 0)
                trades = broker.get_trade_history()
                result = paper_trading_service.get_statistics(user_id=user_id)
                result["current_balance"] = total_balance
                result["total_value"] = total_balance
                result["total_trades"] = len(trades) if isinstance(trades, list) else result.get("total_trades", 0)
                result["mode"] = "live"
                return sanitize_floats(result)
        except Exception as e:
            print(f"[!] Live stats failed, falling back to paper: {e}")

    result = paper_trading_service.get_statistics(user_id=user_id)
    result["mode"] = "paper"
    return sanitize_floats(result)

class PaperOrderRequest(BaseModel):
    symbol: str
    side: str  # BUY or SELL
    quantity: float


class ClosePaperTradeRequest(BaseModel):
    trade_id: str

@app.post("/api/trading/order")
async def place_trading_order(order: PaperOrderRequest, request: Request):
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

    user_id = _optional_user_id_from_request(request)
    result = paper_trading_service.place_order({
        "symbol": symbol,
        "side": side,
        "quantity": order.quantity,
        "price": price,
        "order_type": "MARKET",
    }, user_id=user_id)

    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    return result


@app.post("/api/paper-trading/close/{trade_id}")
async def close_paper_trade(trade_id: str, request: Request):
    """Close an open paper trade by trade/order id."""
    import httpx

    user_id = _optional_user_id_from_request(request)
    history = paper_trading_service.get_trade_history(limit=10000, user_id=user_id)
    target = next((t for t in history if str(t.get("order_id") or t.get("id")) == str(trade_id)), None)
    if not target:
        raise HTTPException(status_code=404, detail="Trade not found")

    symbol = str(target.get("symbol") or "").upper()
    original_side = str(target.get("side") or "BUY").upper()
    close_side = "SELL" if original_side == "BUY" else "BUY"

    portfolio = paper_trading_service.get_portfolio(user_id=user_id)
    pos = next((p for p in portfolio.get("positions", []) if p.get("symbol") == symbol), None)
    available_qty = float((pos or {}).get("quantity", 0) or 0)
    requested_qty = float(target.get("quantity", 0) or 0)
    quantity = min(requested_qty if requested_qty > 0 else available_qty, available_qty)

    if quantity <= 0:
        raise HTTPException(status_code=400, detail="No open quantity available for this trade")

    price = None
    if broker_instances:
        for broker in broker_instances.values():
            try:
                info = broker.get_market_price(symbol)
                if "price" in info:
                    price = float(info["price"])
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
        "side": close_side,
        "quantity": quantity,
        "price": price,
        "order_type": "MARKET",
    }, user_id=user_id)

    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    pnl_pct = float(result.get("pnl_percent", 0) or 0)
    earned = []
    if user_id is not None:
        try:
            from services.achievements import check_and_award
            earned = check_and_award(user_id, "trade_closed", {"pnl_pct": pnl_pct})
        except Exception:
            earned = []

    return {
        "success": True,
        "closed_trade_id": trade_id,
        "close_order": result,
        "achievements_earned": earned,
        "timestamp": datetime.now().isoformat(),
    }


@app.post("/api/paper-trading/reset")
def reset_paper_trading(request: Request):
    """Reset paper trading account"""
    user_id = _optional_user_id_from_request(request)
    paper_trading_service.reset(user_id=user_id)
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


@app.get("/api/v1/consensus/{symbol}")
async def get_multi_agent_consensus(symbol: str):
    """Get consensus prediction from XGBoost + RF + RL + regime filter."""
    from ml.predictor import get_ensemble_prediction
    from ml.regime_detector import get_current_regime

    symbol_u = normalize_symbol_alias(symbol)
    prediction = get_ensemble_prediction(symbol_u, features={})

    if prediction.get("error"):
        raise HTTPException(status_code=500, detail=f"Consensus prediction failed: {prediction['error']}")

    redis_client = get_redis()
    regime = get_current_regime(redis_client)
    multiplier = float(regime.get("confidence_multiplier", 0.5) or 0.5)
    adjusted_confidence = float(prediction.get("confidence", 0.0) or 0.0) * multiplier

    if adjusted_confidence >= 0.90:
        recommendation = "STRONG_SIGNAL"
    elif adjusted_confidence >= 0.75:
        recommendation = "MODERATE_SIGNAL"
    elif adjusted_confidence >= 0.60:
        recommendation = "WEAK_SIGNAL"
    else:
        recommendation = "NO_SIGNAL"

    print(
        "[RL_CONSENSUS] "
        f"{symbol_u}: XGB={float(prediction.get('xgb_confidence', 0))*100:.0f}% "
        f"RF={float(prediction.get('rf_confidence', 0))*100:.0f}% "
        f"RL={prediction.get('rl_action') or 'NONE'} "
        f"{'✅' if prediction.get('consensus') else '❌'} -> {recommendation}"
    )

    return {
        "symbol": symbol_u,
        "recommendation": recommendation,
        "final_confidence": round(adjusted_confidence, 4),
        "raw_confidence": prediction.get("confidence", 0.0),
        "action": prediction.get("action", "HOLD"),
        "agents": {
            "xgboost": prediction.get("xgb_confidence", 0.0),
            "random_forest": prediction.get("rf_confidence", 0.0),
            "rl_agent": prediction.get("rl_action"),
            "consensus": prediction.get("consensus", False),
        },
        "regime": {
            "current": regime.get("regime", "normal"),
            "vix": regime.get("vix", 20.0),
            "multiplier": multiplier,
        },
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.get("/api/v1/rl/performance/online")
async def get_rl_online_performance():
    """Get recent RL online-learning performance across tracked symbols."""
    from ml.rl_online_learner import get_symbol_performance

    symbols = ["BTC-USD", "ETH-USD", "BTCUSDC", "ETHUSDC", "AAPL", "GOOGL", "GC=F", "SI=F"]
    redis_client = get_redis()

    results = []
    for symbol in symbols:
        perf = await get_symbol_performance(symbol, redis_client)
        results.append(perf)

    results.sort(key=lambda x: x.get("avg_reward", 0), reverse=True)
    return {
        "performances": results,
        "total_symbols": len(results),
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.get("/api/v1/rl/outcomes/debug")
async def get_rl_trade_outcomes_debug(
    symbol: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    _user=Depends(require_auth),
):
    """Debug endpoint for latest RL trade outcomes with pagination."""
    if SessionLocal is None:
        raise HTTPException(status_code=503, detail="Database not available")

    offset = (page - 1) * page_size
    symbol_u = symbol.upper() if symbol else None

    db = SessionLocal()
    try:
        if symbol_u:
            total_row = db.execute(
                text("SELECT COUNT(*) AS cnt FROM rl_trade_outcomes WHERE symbol = :symbol"),
                {"symbol": symbol_u},
            ).mappings().first()
            rows = db.execute(
                text(
                    """
                    SELECT id, symbol, action, entry_price, exit_price, pnl_pct, reward, confidence, recorded_at
                    FROM rl_trade_outcomes
                    WHERE symbol = :symbol
                    ORDER BY recorded_at DESC, id DESC
                    LIMIT :limit OFFSET :offset
                    """
                ),
                {"symbol": symbol_u, "limit": page_size, "offset": offset},
            ).mappings().all()
        else:
            total_row = db.execute(
                text("SELECT COUNT(*) AS cnt FROM rl_trade_outcomes")
            ).mappings().first()
            rows = db.execute(
                text(
                    """
                    SELECT id, symbol, action, entry_price, exit_price, pnl_pct, reward, confidence, recorded_at
                    FROM rl_trade_outcomes
                    ORDER BY recorded_at DESC, id DESC
                    LIMIT :limit OFFSET :offset
                    """
                ),
                {"limit": page_size, "offset": offset},
            ).mappings().all()

        total = int((total_row or {}).get("cnt") or 0)
        total_pages = (total + page_size - 1) // page_size if total > 0 else 0

        items = [
            {
                "id": int(r["id"]),
                "symbol": str(r["symbol"]),
                "action": str(r["action"]),
                "entry_price": float(r["entry_price"]),
                "exit_price": float(r["exit_price"]),
                "pnl_pct": float(r["pnl_pct"]),
                "reward": float(r["reward"]),
                "confidence": float(r["confidence"]) if r["confidence"] is not None else None,
                "recorded_at": r["recorded_at"].isoformat() if r["recorded_at"] else None,
            }
            for r in rows
        ]

        return {
            "symbol": symbol_u,
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": total_pages,
            "has_next": page < total_pages,
            "has_prev": page > 1,
            "items": items,
            "timestamp": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch rl_trade_outcomes: {e}")
    finally:
        db.close()

@app.get("/api/ai/predictions")
def get_all_predictions(request: Request, days: int = 7, asset_type: Optional[str] = None):
    """Επιστρέφει predictions για όλα τα assets ή filtered by type"""
    if request is not None:
        user_id = _optional_user_id_from_request(request)
        if user_id is not None:
            from services.subscription_service import consume_prediction_quota
            consume_prediction_quota(user_id)

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
        trend_1d = "bullish" if trend == "BULLISH" else "bearish" if trend == "BEARISH" else "neutral"
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
            "ensemble": p.get("ensemble"),
            "shap_explanation": p.get("shap_explanation", {}),
            "onchain": p.get("onchain"),
            "mtf_confluence": p.get("mtf_confluence"),
            "trend_1h": p.get("trend_1h"),
            "trend_4h": p.get("trend_4h"),
            "trend_1d": trend_1d,
            "rsi_1h": p.get("rsi_1h"),
        })

        # Prediction tracking layer (non-fatal): store prediction for delayed accuracy evaluation.
        try:
            from services.prediction_outcomes import prediction_outcomes_service
            prediction_outcomes_service.track_prediction(
                symbol=symbol,
                action=rec,
                confidence=confidence,
                price_at_prediction=float(current_price or 0.0),
                onchain=p.get("onchain"),
            )
        except Exception:
            pass

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

    try:
        if request is not None:
            uid = _optional_user_id_from_request(request)
            if uid is not None:
                from services.achievements import check_and_award
                check_and_award(uid, "predictions_viewed", {"count": 1})
    except Exception:
        pass

    return sanitize_floats(result)


@app.get("/api/ai/accuracy")
def get_ai_accuracy_summary():
    """Prediction direction accuracy summary from delayed outcome evaluation."""
    from services.prediction_outcomes import prediction_outcomes_service

    return sanitize_floats(prediction_outcomes_service.get_accuracy(symbol=None))


@app.get("/api/ai/accuracy/by-onchain-bucket")
def get_accuracy_by_onchain_bucket(symbol: Optional[str] = None, days: int = 30):
    """Prediction accuracy analytics bucketed by on-chain score ranges (0-0.25, 0.25-0.5, 0.5-0.75, 0.75-1.0)."""
    from services.prediction_outcomes import prediction_outcomes_service

    result = prediction_outcomes_service.get_accuracy_by_onchain_bucket(symbol=symbol, days=days)
    return sanitize_floats(result)


@app.get("/api/ai/accuracy/{symbol}")
def get_ai_accuracy_for_symbol(symbol: str):
    """Prediction direction accuracy for a specific asset symbol."""
    from services.prediction_outcomes import prediction_outcomes_service

    return sanitize_floats(prediction_outcomes_service.get_accuracy(symbol=symbol.upper()))


@app.get("/api/ai/model-health")
def get_ai_model_health():
    """Return model version/accuracy trend and feedback activity per symbol."""
    from services.model_improver import get_model_health

    return sanitize_floats(get_model_health())

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


@app.get("/api/market/onchain/summary")
def get_market_onchain_summary(days: int = 7):
    """Return aggregate on-chain summary across tracked crypto assets."""
    from services.onchain_service import get_recent_onchain_summary

    return sanitize_floats(get_recent_onchain_summary(days=max(1, min(days, 90))))


@app.get("/api/market/onchain/{symbol}/history")
def get_market_onchain_history(symbol: str, days: int = 30, limit: int = 120):
    """Return persistent on-chain snapshot history for a symbol."""
    from services.onchain_service import get_onchain_history, is_onchain_supported

    sym = symbol.upper()
    if not is_onchain_supported(sym):
        raise HTTPException(status_code=404, detail=f"On-chain signals not supported for {sym}")

    return sanitize_floats(get_onchain_history(sym, days=max(1, min(days, 365)), limit=max(1, min(limit, 500))))


@app.get("/api/market/onchain/{symbol}")
def get_market_onchain(symbol: str):
    """Return full on-chain signal bundle for supported crypto symbols."""
    from services.onchain_service import get_onchain_signals, is_onchain_supported

    sym = symbol.upper()
    if not is_onchain_supported(sym):
        raise HTTPException(status_code=404, detail=f"On-chain signals not supported for {sym}")

    return sanitize_floats(get_onchain_signals(sym))


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
    trend_1d = "bullish" if trend == "BULLISH" else "bearish" if trend == "BEARISH" else "neutral"
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
        "ensemble": p.get("ensemble"),
        "shap_explanation": p.get("shap_explanation", {}),
        "onchain": p.get("onchain"),
        "mtf_confluence": p.get("mtf_confluence"),
        "trend_1h": p.get("trend_1h"),
        "trend_4h": p.get("trend_4h"),
        "trend_1d": trend_1d,
        "rsi_1h": p.get("rsi_1h"),
        "pricePath": p.get("price_path", []),
        "modelVersion": p.get("model_version", "v1.0"),
    }
    print(f"[DEBUG] Prediction detail response: asset={result['asset']}, price={result['price']}, targetPrice={result['targetPrice']}")
    return sanitize_floats(result)


@app.get("/api/ai/decision/{symbol}")
def get_ai_decision(symbol: str, payload=Depends(require_auth)):
    """Returns a personalized, explainable AI trading decision."""
    from ai.decision_explanation import build_explanation
    from services.smart_score import smart_score_calculator
    from services.user_personalization import get_user_profile

    sym = symbol.upper()
    user_id = int(payload.get("sub", 0))

    # Load user's personalized trading parameters
    user_profile = get_user_profile(user_id)
    risk_profile_name = user_profile.get("risk_profile", "moderate")

    prediction = asset_predictor.predict_price(sym, days=7)
    if "error" in prediction:
        raise HTTPException(status_code=400, detail=prediction["error"])

    try:
        ss = smart_score_calculator.calculate_smart_score(sym)
    except Exception:
        ss = None

    # Portfolio awareness — assess concentration risk
    portfolio_assessment = None
    risk_context = None
    try:
        from services.portfolio_state import assess_portfolio
        positions = []
        if broker_instances:
            broker = next(iter(broker_instances.values()))
            try:
                full_portfolio = broker._signed_request("GET", "/api/v3/account")
                if "error" not in full_portfolio:
                    for item in full_portfolio.get("balances", []):
                        total = float(item.get("free", 0)) + float(item.get("locked", 0))
                        if total > 0 and item["asset"] not in ("USDC", "USDT", "BUSD", "USD"):
                            price = broker.get_symbol_price(f"{item['asset']}USDC")
                            if price <= 0:
                                price = broker.get_symbol_price(f"{item['asset']}USDT")
                            positions.append({
                                "symbol": item["asset"],
                                "amount": total,
                                "value_usdc": total * price if price > 0 else 0,
                            })
            except Exception:
                pass

        balance = 10000
        if broker_instances:
            try:
                acct = next(iter(broker_instances.values())).get_account_balance()
                if "error" not in acct:
                    balance = acct.get("total_balance", 10000) or 10000
            except Exception:
                pass

        portfolio_assessment = assess_portfolio(
            positions=positions,
            account_balance=balance,
            proposed_symbol=sym,
            proposed_value=balance * 0.02,  # estimate 2% trade
            user_id=user_id,
        )

        # Build risk context for explanation layer
        if portfolio_assessment.adjustment_recommendation == "block":
            risk_context = {
                "blocked": True,
                "block_reason": "PORTFOLIO_CONCENTRATION",
                "size_factor": 0.0,
            }
        elif portfolio_assessment.size_factor < 1.0:
            risk_context = {
                "size_factor": portfolio_assessment.size_factor,
            }
    except Exception as e:
        print(f"[!] Portfolio assessment failed (non-fatal): {e}")

    explanation = build_explanation(prediction, ss, risk_context=risk_context)

    # Persist decision to explainability schema
    decision_event_id = None
    try:
        from services.decision_persistence import save_decision_event
        decision_event_id = save_decision_event(
            explanation=explanation,
            user_id=user_id,
            symbol=sym,
            raw_signal=sanitize_floats(asset_predictor.get_trading_signal(sym)),
        )
    except Exception:
        pass

    # Persist risk event if decision was blocked or reduced
    if explanation.action in ("BLOCKED", "NO-TRADE") or explanation.sizing_adjustments:
        try:
            from services.risk_event_persistence import emit_risk_event
            if explanation.action == "BLOCKED":
                emit_risk_event(
                    event_type="blocked_trade",
                    reason_code=explanation.reason_codes[0] if explanation.reason_codes else "RISK_BLOCK",
                    summary=f"Trade blocked for {sym}: {', '.join(explanation.blocked_by[:2])}",
                    user_id=user_id,
                    symbol=sym,
                    related_decision_event_id=decision_event_id,
                    severity="critical",
                    details={
                        "blocked_by": explanation.blocked_by,
                        "reason_codes": explanation.reason_codes,
                        "confidence": explanation.confidence_score,
                        "risk_profile": risk_profile_name,
                    },
                    portfolio_risk_score=portfolio_assessment.portfolio_risk_score if portfolio_assessment else None,
                )
            elif explanation.sizing_adjustments:
                emit_risk_event(
                    event_type="size_reduced",
                    reason_code=explanation.reason_codes[0] if explanation.reason_codes else "SIZE_REDUCED_BY_RISK",
                    summary=f"Size reduced for {sym}: {explanation.sizing_adjustments[0]}",
                    user_id=user_id,
                    symbol=sym,
                    related_decision_event_id=decision_event_id,
                    severity="warning",
                    details={
                        "sizing_adjustments": explanation.sizing_adjustments,
                        "reason_codes": explanation.reason_codes,
                    },
                )
        except Exception:
            pass

    # Audit log
    try:
        from services.auth_audit import log_auth_event
        log_auth_event(
            "AI_DECISION", "GENERATED",
            user_id=user_id,
            metadata={
                "symbol": sym,
                "action": explanation.action,
                "confidence": explanation.confidence_score,
                "band": explanation.confidence_band,
                "risk_profile": risk_profile_name,
            },
        )
    except Exception:
        pass

    # Emit to AI feed
    try:
        from services.feed_engine import emit_trade_signal, emit_no_trade, emit_risk_alert
        if explanation.action in ("BUY", "SELL"):
            emit_trade_signal(sym, explanation.action, explanation.confidence_score, explanation.reason_codes)
        elif explanation.action in ("NO-TRADE", "HOLD"):
            emit_no_trade(sym, explanation.primary_reasons, explanation.reason_codes)
        if explanation.action == "BLOCKED":
            emit_risk_alert(sym, f"Trade blocked: {', '.join(explanation.blocked_by)}", severity="critical")
        if portfolio_assessment and portfolio_assessment.concentration_warnings:
            for w in portfolio_assessment.concentration_warnings[:2]:
                emit_risk_alert(sym, w, severity="warning")
    except Exception:
        pass

    signal = asset_predictor.get_trading_signal(sym)

    # Position sizing with user's risk profile
    sizing = None
    try:
        from services.position_sizing import calculate_position_size, SizingInput
        balance = 10000
        if broker_instances:
            broker = next(iter(broker_instances.values()))
            acct = broker.get_account_balance()
            if "error" not in acct:
                balance = acct.get("total_balance", 10000) or 10000

        sizing_result = calculate_position_size(SizingInput(
            account_balance=balance,
            signal_confidence=explanation.confidence_score,
            volatility=min(1.0, abs(prediction.get("trend_score", 0.3))),
            current_drawdown=0.0,
            current_portfolio_exposure=0.0,
            price=prediction.get("current_price", 1),
            user_risk_profile=risk_profile_name,
            symbol=sym,
        ))
        sizing = {
            "recommended_notional": sizing_result.recommended_notional,
            "quantity": sizing_result.quantity,
            "decision": sizing_result.decision,
            "confidence_multiplier": sizing_result.confidence_multiplier,
            "volatility_multiplier": sizing_result.volatility_multiplier,
            "drawdown_multiplier": sizing_result.drawdown_multiplier,
            "final_risk_pct": sizing_result.final_risk_pct,
            "cap_adjustments": sizing_result.cap_adjustments,
            "reasoning": sizing_result.reasoning,
        }
    except Exception as e:
        print(f"[!] Position sizing failed (non-fatal): {e}")

    # Build portfolio summary for response
    portfolio_summary = None
    if portfolio_assessment:
        portfolio_summary = {
            "risk_score": portfolio_assessment.portfolio_risk_score,
            "total_exposure_usd": portfolio_assessment.total_exposure_usd,
            "position_count": portfolio_assessment.position_count,
            "exposure_by_class_pct": portfolio_assessment.exposure_by_class_pct,
            "concentration_warnings": portfolio_assessment.concentration_warnings,
            "adjustment": portfolio_assessment.adjustment_recommendation,
            "size_factor": portfolio_assessment.size_factor,
        }

    result = {
        "signal": sanitize_floats(signal),
        "explanation": explanation.model_dump(),
        "sizing": sanitize_floats(sizing) if sizing else None,
        "portfolio": sanitize_floats(portfolio_summary) if portfolio_summary else None,
        "user_profile": {
            "risk_profile": risk_profile_name,
            "objective": user_profile.get("objective", "growth"),
            "confidence_threshold": user_profile.get("confidence_threshold"),
            "max_positions": user_profile.get("max_positions"),
        },
    }
    return sanitize_floats(result)


@app.get("/api/ai/decision-history")
def get_decision_history(
    symbol: str = None,
    limit: int = 20,
    payload=Depends(require_auth),
):
    """Get AI decision history with reason codes and counterfactuals."""
    from services.decision_persistence import get_decision_history as _get_history
    user_id = int(payload.get("sub", 0))
    history = _get_history(user_id=user_id, symbol=symbol, limit=min(limit, 100))
    return {"decisions": history, "count": len(history)}


@app.get("/api/ai/reason-code-stats")
def get_reason_code_stats(symbol: str = None, _user=Depends(require_auth)):
    """Get aggregated reason code frequency for analytics."""
    from services.decision_persistence import get_reason_code_stats as _get_stats
    stats = _get_stats(symbol=symbol)
    return {"stats": stats}


@app.get("/api/risk-events")
def get_risk_events(
    symbol: str = None,
    event_type: str = None,
    severity: str = None,
    limit: int = 50,
    payload=Depends(require_auth),
):
    """Get risk event history with optional filters."""
    from services.risk_event_persistence import get_risk_event_history
    user_id = int(payload.get("sub", 0))
    events = get_risk_event_history(
        user_id=user_id, symbol=symbol,
        event_type=event_type, severity=severity,
        limit=min(limit, 200),
    )
    return {"events": events, "count": len(events)}


@app.get("/api/risk-events/summary")
def get_risk_events_summary(symbol: str = None, payload=Depends(require_auth)):
    """Get aggregated risk event counts by type and severity."""
    from services.risk_event_persistence import get_risk_event_summary
    user_id = int(payload.get("sub", 0))
    return get_risk_event_summary(user_id=user_id, symbol=symbol)


@app.get("/api/portfolio/risk")
def get_portfolio_risk(payload=Depends(require_auth)):
    """Get portfolio risk assessment — exposure, concentration, recommendations."""
    from services.portfolio_state import assess_portfolio

    positions = []
    balance = 10000
    try:
        if broker_instances:
            broker = next(iter(broker_instances.values()))
            acct = broker.get_account_balance()
            if "error" not in acct:
                balance = acct.get("total_balance", 10000) or 10000

            full = broker._signed_request("GET", "/api/v3/account")
            if "error" not in full:
                for item in full.get("balances", []):
                    total = float(item.get("free", 0)) + float(item.get("locked", 0))
                    if total > 0 and item["asset"] not in ("USDC", "USDT", "BUSD", "USD"):
                        price = broker.get_symbol_price(f"{item['asset']}USDC")
                        if price <= 0:
                            price = broker.get_symbol_price(f"{item['asset']}USDT")
                        positions.append({
                            "symbol": item["asset"],
                            "amount": total,
                            "value_usdc": total * price if price > 0 else 0,
                        })
    except Exception as e:
        print(f"[!] Portfolio risk fetch failed: {e}")

    assessment = assess_portfolio(positions=positions, account_balance=balance)
    return sanitize_floats({
        "risk_score": assessment.portfolio_risk_score,
        "total_exposure_usd": assessment.total_exposure_usd,
        "position_count": assessment.position_count,
        "exposure_by_symbol": assessment.exposure_by_symbol,
        "exposure_by_class": assessment.exposure_by_class,
        "exposure_by_class_pct": assessment.exposure_by_class_pct,
        "correlated_exposure": assessment.correlated_exposure,
        "concentration_warnings": assessment.concentration_warnings,
        "adjustment": assessment.adjustment_recommendation,
        "adjustment_details": assessment.adjustment_details,
        "size_factor": assessment.size_factor,
    })


@app.get("/api/portfolio/history")
def get_portfolio_history(limit: int = 30, payload=Depends(require_auth)):
    """Get portfolio snapshot history for the current user."""
    from services.portfolio_persistence import get_snapshot_history
    user_id = int(payload.get("sub", 0))
    snapshots = get_snapshot_history(user_id=user_id, limit=min(limit, 200))
    return sanitize_floats({"snapshots": snapshots, "count": len(snapshots)})


@app.get("/api/portfolio/snapshot/{snapshot_id}")
def get_portfolio_snapshot_detail(snapshot_id: int, _user=Depends(require_auth)):
    """Get a single portfolio snapshot with full symbol and cluster breakdown."""
    from services.portfolio_persistence import get_snapshot_detail
    detail = get_snapshot_detail(snapshot_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Snapshot not found")
    return sanitize_floats(detail)


@app.get("/api/portfolio/equity-chart")
def get_equity_chart(limit: int = 90, payload=Depends(require_auth)):
    """Get equity timeseries for portfolio chart."""
    from services.portfolio_persistence import get_equity_timeseries
    user_id = int(payload.get("sub", 0))
    series = get_equity_timeseries(user_id=user_id, limit=min(limit, 365))
    return sanitize_floats({"series": series, "count": len(series)})


@app.get("/api/feed")
def get_ai_feed(
    limit: int = 50,
    event_type: Optional[str] = None,
    symbol: Optional[str] = None,
    severity: Optional[str] = None,
):
    """Get the AI feed — sorted, deduplicated events from all AURA systems (legacy)."""
    from services.feed_engine import get_feed
    events = get_feed(limit=limit, event_type=event_type, symbol=symbol, severity=severity)
    return sanitize_floats({"events": events, "count": len(events)})


@app.get("/api/feed/v2")
def get_user_feed_v2(
    event_type: Optional[str] = None,
    priority: Optional[str] = None,
    symbol: Optional[str] = None,
    include_expired: bool = False,
    limit: int = 50,
    payload=Depends(require_auth),
):
    """Get personalized AI feed with read/unread state and expiry."""
    from services.feed_persistence import get_user_feed
    user_id = int(payload.get("sub", 0))
    events = get_user_feed(
        user_id=user_id, event_type=event_type,
        priority=priority, symbol=symbol,
        include_expired=include_expired, limit=min(limit, 200),
    )
    return {"events": sanitize_floats(events), "count": len(events)}


@app.get("/api/feed/v2/unread")
def get_feed_unread_count(payload=Depends(require_auth)):
    """Get count of unread, non-expired feed events for the current user."""
    from services.feed_persistence import get_unread_count
    user_id = int(payload.get("sub", 0))
    return {"unread_count": get_unread_count(user_id)}


@app.post("/api/feed/v2/mark-read")
def mark_feed_read(data: dict, payload=Depends(require_auth)):
    """Mark specific feed events as read. Body: {"event_ids": [1, 2, 3]}"""
    from services.feed_persistence import mark_read
    user_id = int(payload.get("sub", 0))
    event_ids = data.get("event_ids", [])
    if not isinstance(event_ids, list):
        raise HTTPException(status_code=400, detail="event_ids must be a list")
    marked = mark_read(user_id, event_ids[:100])  # cap at 100 per call
    return {"marked": marked}


@app.post("/api/feed/v2/mark-all-read")
def mark_feed_all_read(payload=Depends(require_auth)):
    """Mark all unread feed events as read for the current user."""
    from services.feed_persistence import mark_all_read
    user_id = int(payload.get("sub", 0))
    marked = mark_all_read(user_id)
    return {"marked": marked}


class SimulationRequest(BaseModel):
    strategy: str = "ai_follow"
    symbols: List[str] = ["BTCUSDC", "ETHUSDC", "BNBUSDC"]
    timeframe_days: int = 30
    capital: float = 10000.0
    confidence_threshold: Optional[float] = None
    stop_loss_pct: float = 3.0
    take_profit_pct: float = 5.0
    max_positions: int = 3
    position_size_pct: float = 5.0


@app.post("/api/simulation/run")
def run_simulation_endpoint(req: SimulationRequest, payload=Depends(require_auth)):
    """Run a strategy simulation. Results are hypothetical — not real trading."""
    from services.simulation_engine import run_simulation, STRATEGIES, DISCLAIMER
    result = run_simulation(
        strategy=req.strategy,
        symbols=req.symbols,
        timeframe_days=req.timeframe_days,
        initial_capital=req.capital,
        confidence_threshold=req.confidence_threshold,
        stop_loss_pct=req.stop_loss_pct / 100,
        take_profit_pct=req.take_profit_pct / 100,
        max_positions=req.max_positions,
        position_size_pct=req.position_size_pct,
    )
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    # Persist the run
    try:
        from services.simulation_persistence import save_simulation_run
        user_id = int(payload.get("sub", 0))
        run_id = save_simulation_run(
            user_id=user_id,
            strategy_id=req.strategy,
            run_type="backtest",
            symbols=req.symbols,
            initial_capital=req.capital,
            config={
                "strategy": req.strategy,
                "symbols": req.symbols,
                "timeframe_days": req.timeframe_days,
                "capital": req.capital,
                "confidence_threshold": req.confidence_threshold,
                "stop_loss_pct": req.stop_loss_pct,
                "take_profit_pct": req.take_profit_pct,
                "max_positions": req.max_positions,
                "position_size_pct": req.position_size_pct,
            },
            disclaimer=DISCLAIMER,
            result=result,
            timeframe_days=req.timeframe_days,
        )
        if run_id:
            result["run_id"] = run_id
    except Exception:
        pass

    return sanitize_floats(result)


@app.get("/api/simulation/strategies")
def get_simulation_strategies():
    """Get available simulation strategies."""
    from services.simulation_engine import STRATEGIES
    return {"strategies": {k: {"label": v["label"], "description": v["description"]} for k, v in STRATEGIES.items()}}


@app.get("/api/simulation/history")
def get_simulation_history_endpoint(
    run_type: Optional[str] = None,
    limit: int = 20,
    payload=Depends(require_auth),
):
    """Get simulation run history for the current user."""
    from services.simulation_persistence import get_simulation_history
    user_id = int(payload.get("sub", 0))
    history = get_simulation_history(user_id=user_id, run_type=run_type, limit=min(limit, 100))
    return sanitize_floats({"runs": history, "count": len(history)})


@app.get("/api/simulation/detail/{run_id}")
def get_simulation_detail_endpoint(run_id: int, _user=Depends(require_auth)):
    """Get full simulation detail including config, results, and equity curve."""
    from services.simulation_persistence import get_simulation_detail
    detail = get_simulation_detail(run_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Simulation run not found")
    return sanitize_floats(detail)


@app.get("/api/strategies")
def list_strategies():
    """List all registered trading strategies."""
    from services.strategy_engine import strategy_registry
    return {"strategies": strategy_registry.list_all()}


@app.get("/api/strategies/evaluate/{symbol}")
def evaluate_strategies(symbol: str):
    """Evaluate all strategies for a symbol and return consensus."""
    from services.strategy_engine import strategy_registry

    sym = symbol.upper()
    prediction = asset_predictor.predict_price(sym, days=7)
    if "error" in prediction:
        raise HTTPException(status_code=400, detail=prediction["error"])

    # Build market_data combining prediction + smart score
    market_data = dict(prediction)
    try:
        from services.smart_score import smart_score_calculator
        ss = smart_score_calculator.calculate_smart_score(sym)
        market_data["smart_score"] = ss.get("smart_score", 50)
        market_data["signals"] = ss.get("signals", {})
    except Exception:
        market_data["smart_score"] = 50
        market_data["signals"] = {}

    results = strategy_registry.evaluate_all(sym, market_data)
    consensus = strategy_registry.consensus(sym, market_data)

    return sanitize_floats({
        "symbol": sym,
        "strategies": results,
        "consensus": consensus,
    })


@app.get("/api/strategy-platform/registry")
def get_strategy_registry(active_only: bool = False, _user=Depends(require_auth)):
    """Get all registered strategies."""
    from services.strategy_persistence import get_all_strategies
    return {"strategies": get_all_strategies(active_only=active_only)}


@app.get("/api/strategy-platform/registry/{strategy_key}")
def get_strategy_detail(strategy_key: str, _user=Depends(require_auth)):
    """Get a single strategy by key."""
    from services.strategy_persistence import get_strategy_by_key
    strat = get_strategy_by_key(strategy_key)
    if not strat:
        raise HTTPException(status_code=404, detail="Strategy not found")
    return strat


@app.get("/api/strategy-platform/health/{strategy_id}")
def get_strategy_health(strategy_id: int, limit: int = 30, _user=Depends(require_auth)):
    """Get health snapshot history for a strategy."""
    from services.strategy_persistence import get_health_history
    history = get_health_history(strategy_id=strategy_id, limit=min(limit, 200))
    return {"snapshots": history, "count": len(history)}


@app.get("/api/strategy-platform/allocations")
def get_strategy_allocations(
    strategy_id: Optional[int] = None,
    limit: int = 30,
    payload=Depends(require_auth),
):
    """Get allocation history, optionally filtered by strategy."""
    from services.strategy_persistence import get_allocation_history
    user_id = int(payload.get("sub", 0))
    history = get_allocation_history(strategy_id=strategy_id, user_id=user_id, limit=min(limit, 200))
    return {"allocations": history, "count": len(history)}


@app.get("/api/audit-trail")
def get_audit_trail_endpoint(
    domain: Optional[str] = None,
    severity: Optional[str] = None,
    entity_type: Optional[str] = None,
    entity_id: Optional[int] = None,
    limit: int = 50,
    payload=Depends(require_auth),
):
    """Get unified audit trail with optional filters."""
    from services.audit_trail import get_audit_trail
    user_id = int(payload.get("sub", 0))
    events = get_audit_trail(
        user_id=user_id, domain=domain, severity=severity,
        entity_type=entity_type, entity_id=entity_id,
        limit=min(limit, 500),
    )
    return {"events": events, "count": len(events)}


@app.get("/api/audit-trail/summary")
def get_audit_summary_endpoint(payload=Depends(require_auth)):
    """Get aggregated audit event counts by domain and severity."""
    from services.audit_trail import get_audit_summary
    user_id = int(payload.get("sub", 0))
    return get_audit_summary(user_id=user_id)


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
    briefing = voice_briefing_service.generate_briefing(
        include_market_news=include_news,
        include_ai_predictions=include_predictions,
        include_portfolio=include_portfolio,
        max_duration_seconds=max_duration
    )
    return {
        **briefing,
        "audio_url": briefing.get("audio_url"),
        "text": briefing.get("full_text", ""),
    }

@app.post("/api/voice/upload")
async def upload_voice_sample(audio: UploadFile = File(...), _user=Depends(require_auth)):
    """Upload a voice sample for voice cloning (30s recording)."""
    import os
    user_id = _user.get("user_id") if isinstance(_user, dict) else getattr(_user, "id", None)
    upload_dir = os.path.join(os.path.dirname(__file__), "uploads", "voice")
    os.makedirs(upload_dir, exist_ok=True)

    filename = f"voice_{user_id}_{int(datetime.now().timestamp())}.m4a"
    filepath = os.path.join(upload_dir, filename)

    content = await audio.read()
    if len(content) < 1000:
        raise HTTPException(status_code=400, detail="Recording too short")

    with open(filepath, "wb") as f:
        f.write(content)

    return {
        "success": True,
        "filename": filename,
        "size_bytes": len(content),
        "user_id": user_id,
    }


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
def get_analytics_summary(period: str = "all", payload=Depends(require_auth)):
    """Analytics summary aggregating paper + live trades. period: 7d|30d|90d|all"""
    user_id = _extract_user_id(payload)
    trades = paper_trading_service.get_trade_history(limit=10000, user_id=user_id)
    portfolio = paper_trading_service.get_portfolio(user_id=user_id)

    # Include live trades from audit logs
    try:
        from database.connection import SessionLocal
        if SessionLocal:
            db = SessionLocal()
            from sqlalchemy import text
            live_rows = db.execute(text(
                "SELECT symbol, side, quantity, price, status, created_at "
                "FROM live_order_audit_logs "
                "WHERE (status = 'FILLED' OR status = 'NEW' OR status = 'filled' OR status = 'submitted' OR status = 'success') "
                "AND ((user_id = :uid) OR (:allow_legacy = TRUE AND user_id IS NULL)) "
                "ORDER BY created_at DESC LIMIT 10000"
            ), {
                "uid": user_id,
                "allow_legacy": _legacy_allowed_for_user(user_id),
            }).fetchall()
            db.close()
            for row in live_rows:
                trades.append({
                    "symbol": row[0],
                    "side": row[1],
                    "quantity": float(row[2]) if row[2] else 0,
                    "price": float(row[3]) if row[3] else 0,
                    "status": "closed" if row[1] == "SELL" else "open",
                    "timestamp": row[5].isoformat() if row[5] else "",
                    "profit": 0,
                    "pnl": 0,
                    "source": "live",
                })
    except Exception as e:
        print(f"[!] Failed to load live trades for analytics (non-fatal): {e}")

    # Filter by period
    if period != "all":
        days_map = {"7d": 7, "30d": 30, "90d": 90}
        days = days_map.get(period, 9999)
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        trades = [t for t in trades if t.get("timestamp", "") >= cutoff]

    total_trades = len(trades)

    initial_capital = float(portfolio.get("initial_balance", 10000.0) or 10000.0)
    final_capital = float(portfolio.get("total_value", 0) or 0)

    if total_trades == 0:
        return {
            "total_value": final_capital,
            "final_capital": final_capital,
            "initial_capital": initial_capital,
            "starting_balance": initial_capital,
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
        "total_value": round(final_capital, 2),
        "final_capital": round(final_capital, 2),
        "initial_capital": round(initial_capital, 2),
        "starting_balance": round(initial_capital, 2),
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


class PushTokenRequest(BaseModel):
    token: str
    platform: str = "android"


@app.post("/api/notifications/register-token")
def register_push_token(data: PushTokenRequest, payload=Depends(require_auth)):
    """Register an Expo push token for this user."""
    if not data.token or not data.token.startswith("ExponentPushToken"):
        raise HTTPException(status_code=400, detail="Invalid push token format")

    user_id = int(payload.get("sub", 0))
    try:
        from sqlalchemy import text as _text
        db = SessionLocal()
        # Upsert: update if token exists, insert if not
        existing = db.execute(
            _text("SELECT id FROM push_tokens WHERE token = :tok"), {"tok": data.token}
        ).fetchone()
        if existing:
            db.execute(_text(
                "UPDATE push_tokens SET user_id = :uid, platform = :plat, is_active = true, updated_at = NOW() WHERE token = :tok"
            ), {"uid": user_id, "plat": data.platform, "tok": data.token})
        else:
            db.execute(_text(
                "INSERT INTO push_tokens (user_id, token, platform) VALUES (:uid, :tok, :plat)"
            ), {"uid": user_id, "tok": data.token, "plat": data.platform})
        db.commit()
        db.close()
        return {"success": True, "message": "Push token registered"}
    except Exception as e:
        print(f"[!] Push token registration failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to register push token")


# ── User Profile Endpoints ──────────────────────────────────────────

class UpdateProfileRequest(BaseModel):
    username: Optional[str] = None
    email: Optional[str] = None

class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class UserPreferencesRequest(BaseModel):
    push_notifications_enabled: Optional[bool] = None
    morning_briefing_enabled: Optional[bool] = None


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
        try:
            from services.achievements import check_and_award
            check_and_award(user.id, "daily_login")
        except Exception:
            pass
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
    """Update user profile — risk, objective, mode, overrides."""
    from services.user_personalization import save_user_profile
    user_id = int(payload.get("sub", 0))
    result = save_user_profile(
        user_id=user_id,
        risk_profile=data.get("risk_profile", "moderate"),
        objective=data.get("objective", "balanced_growth"),
        preferred_mode=data.get("preferred_mode", "manual_assist"),
        confidence_threshold_override=data.get("confidence_threshold"),
        max_position_override=data.get("max_positions"),
        max_portfolio_exposure_override=data.get("max_portfolio_exposure"),
        behavior_flags=data.get("behavior_flags"),
        notes=data.get("notes"),
    )
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@app.get("/api/user/preferences")
def get_user_preferences(payload=Depends(require_auth)):
    """Return current user preferences from user_profiles."""
    from database.models import UserProfile

    user_id = int(payload.get("sub", 0))
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")

    db = SessionLocal()
    try:
        profile = db.query(UserProfile).filter(UserProfile.user_id == user_id).first()
        if not profile:
            return {
                "push_notifications_enabled": True,
                "morning_briefing_enabled": True,
            }

        flags = dict(profile.behavior_flags_json or {})
        return {
            "push_notifications_enabled": bool(flags.get("push_notifications_enabled", True)),
            "morning_briefing_enabled": bool(getattr(profile, "morning_briefing_enabled", True)),
        }
    finally:
        db.close()


@app.put("/api/user/preferences")
def update_user_preferences(data: UserPreferencesRequest, payload=Depends(require_auth)):
    """Persist simple user preferences in user_profiles.behavior_flags_json."""
    from database.models import UserProfile

    user_id = int(payload.get("sub", 0))
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")

    db = SessionLocal()
    try:
        profile = db.query(UserProfile).filter(UserProfile.user_id == user_id).first()
        if not profile:
            profile = UserProfile(user_id=user_id)
            db.add(profile)
            db.flush()

        flags = dict(profile.behavior_flags_json or {})
        if data.push_notifications_enabled is not None:
            flags["push_notifications_enabled"] = bool(data.push_notifications_enabled)
        if data.morning_briefing_enabled is not None:
            profile.morning_briefing_enabled = bool(data.morning_briefing_enabled)
        profile.behavior_flags_json = flags
        db.commit()
        return {
            "success": True,
            "push_notifications_enabled": bool(flags.get("push_notifications_enabled", True)),
            "morning_briefing_enabled": bool(getattr(profile, "morning_briefing_enabled", True)),
        }
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to update preferences")
    finally:
        db.close()


@app.delete("/api/user/account")
def delete_user_account(payload=Depends(require_auth)):
    """Soft delete user account and invalidate all tokens."""
    db, user = _get_db_user(payload)
    try:
        user.is_active = False
        user.token_version = (user.token_version or 0) + 1
        db.commit()
        return {"success": True}
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to delete account")
    finally:
        db.close()


@app.get("/api/user/trading-profile")
def get_user_trading_profile(payload=Depends(require_auth)):
    """Get the user's personalized trading parameters."""
    from services.user_personalization import get_user_profile
    user_id = int(payload.get("sub", 0))
    return get_user_profile(user_id)


@app.get("/api/achievements")
def get_user_achievements(payload=Depends(require_auth)):
    """Return earned/locked achievements for current user."""
    user_id = _extract_user_id(payload)
    if user_id is None:
        raise HTTPException(status_code=401, detail="Invalid user token")

    from services.achievements import get_achievements_overview
    return sanitize_floats(get_achievements_overview(user_id))


@app.get("/api/reports/weekly")
def get_weekly_reports_endpoint(payload=Depends(require_auth)):
    """Return latest weekly reports (up to 4 weeks) for current user."""
    user_id = _extract_user_id(payload)
    if user_id is None:
        raise HTTPException(status_code=401, detail="Invalid user token")

    from services.weekly_report import get_weekly_reports
    return sanitize_floats(get_weekly_reports(user_id, limit=4))


@app.get("/api/reports/weekly/latest")
def get_latest_weekly_report_endpoint(payload=Depends(require_auth)):
    """Return latest weekly report for current user."""
    user_id = _extract_user_id(payload)
    if user_id is None:
        raise HTTPException(status_code=401, detail="Invalid user token")

    from services.weekly_report import get_latest_weekly_report
    return sanitize_floats(get_latest_weekly_report(user_id))


class SubscriptionUpgradeRequest(BaseModel):
    tier: str


class ReferralApplyRequest(BaseModel):
    referral_code: str


@app.get("/api/subscription/status")
def get_subscription_status_endpoint(payload=Depends(require_auth)):
    """Return current user's subscription tier and feature access."""
    user_id = _extract_user_id(payload)
    if user_id is None:
        raise HTTPException(status_code=401, detail="Invalid user token")

    from services.subscription_service import get_subscription_status

    return sanitize_floats(get_subscription_status(user_id))


@app.post("/api/subscription/upgrade")
def upgrade_subscription_endpoint(data: SubscriptionUpgradeRequest, payload=Depends(require_auth)):
    """Upgrade current user to PRO or ELITE (billing integration placeholder)."""
    user_id = _extract_user_id(payload)
    if user_id is None:
        raise HTTPException(status_code=401, detail="Invalid user token")

    from services.subscription_service import upgrade_subscription

    return sanitize_floats(upgrade_subscription(user_id, data.tier))


@app.get("/api/leaderboard")
def get_leaderboard_endpoint(
    period: str = Query("weekly", pattern="^(weekly|monthly|alltime)$"),
    limit: int = Query(50, ge=1, le=200),
    payload=Depends(require_auth),
):
    """Leaderboard rankings for paper trading performance (anonymized display names only)."""
    user_id = _extract_user_id(payload)
    if user_id is None:
        raise HTTPException(status_code=401, detail="Invalid user token")

    from services.social_service import social_service

    return sanitize_floats(social_service.get_leaderboard(user_id=user_id, period=period, limit=limit))


@app.get("/api/referral/stats")
def get_referral_stats_endpoint(payload=Depends(require_auth)):
    """Get current user's referral stats and share URL."""
    user_id = _extract_user_id(payload)
    if user_id is None:
        raise HTTPException(status_code=401, detail="Invalid user token")

    from services.social_service import social_service

    return sanitize_floats(social_service.get_referral_stats(user_id=user_id))


@app.post("/api/referral/apply")
def apply_referral_endpoint(data: ReferralApplyRequest, payload=Depends(require_auth)):
    """Apply a referral code for the current user and reward referrer."""
    user_id = _extract_user_id(payload)
    if user_id is None:
        raise HTTPException(status_code=401, detail="Invalid user token")

    from services.social_service import social_service

    result = social_service.apply_referral(referral_code=data.referral_code, new_user_id=user_id)
    status = 200 if result.get("success") else 400
    if status != 200:
        raise HTTPException(status_code=status, detail=result.get("message", "Failed to apply referral code."))
    return sanitize_floats(result)


# ── Live Trading Endpoints ───────────────────────────────────────────
LIVE_ORDER_MAX_VALUE_USD = 100.0  # Safety limit per order — protects against accidental large orders


def _is_live_trading_allowed() -> bool:
    """Global kill switch. Returns True ONLY if env var ALLOW_LIVE_TRADING=true."""
    return os.getenv("ALLOW_LIVE_TRADING", "false").lower() in ("true", "1", "yes")


def _enforce_live_kill_switch():
    """Raise 403 if live trading is globally disabled. Call before any live order."""
    if not _is_live_trading_allowed():
        raise HTTPException(
            status_code=403,
            detail="Live trading is globally disabled. Set ALLOW_LIVE_TRADING=true to enable."
        )


def _generate_client_order_id() -> str:
    """Generate a unique client order ID for Binance idempotency."""
    import uuid
    return f"AURA_{uuid.uuid4().hex[:20]}"


def _log_live_order_audit(
    source: str, symbol: str, side: str, quantity: float,
    status: str, trading_mode: str = "live", price: float = None,
    client_order_id: str = None, broker: str = "binance",
    broker_order_id: str = None, response_summary: dict = None,
    error_message: str = None, user_id: int = None,
):
    """Persist every live order attempt to DB for forensic audit."""
    try:
        from sqlalchemy import text as _text
        db = SessionLocal()
        db.execute(_text("""
            INSERT INTO live_order_audit_logs
            (user_id, source, symbol, side, quantity, price, trading_mode,
             client_order_id, broker, status, broker_order_id,
             error_message, created_at)
            VALUES (:uid, :src, :sym, :side, :qty, :price, :mode,
                    :coid, :broker, :status, :boid,
                    :err, NOW())
        """), {
            "uid": user_id, "src": source, "sym": symbol, "side": side,
            "qty": quantity, "price": price, "mode": trading_mode,
            "coid": client_order_id, "broker": broker, "status": status,
            "boid": broker_order_id,
            "err": error_message,
        })
        db.commit()
        db.close()
    except Exception as e:
        print(f"[!] Live order audit log failed (non-fatal): {e}")


def _get_live_broker(user_id: Optional[int] = None):
    """Get current user's preferred broker with legacy fallback for seed user."""
    broker = _get_broker_instance_for_user("binance", user_id) or _get_broker_instance_for_user("bybit", user_id)
    if not broker:
        _restore_broker_connections(user_id=user_id)
        broker = _get_broker_instance_for_user("binance", user_id) or _get_broker_instance_for_user("bybit", user_id)
    if not broker:
        raise HTTPException(status_code=400, detail="No broker connected for current user. Use POST /api/brokers/connect first.")
    return broker


def _pre_order_safety_check(broker, symbol: str, quantity: float):
    """Prevent accidental large orders. Must be called on ALL live paths."""
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


@app.get("/api/live-trading/history")
def get_live_trading_history(limit: int = 50, payload=Depends(require_auth)):
    """Returns executed live orders from audit log."""
    user_id = _extract_user_id(payload)
    try:
        from sqlalchemy import text as _text
        db = SessionLocal()
        rows = db.execute(_text("""
            SELECT client_order_id, symbol, side, quantity, price,
                   status, created_at, broker_order_id, source
            FROM live_order_audit_logs
            WHERE status IN ('filled', 'success', 'submitted')
              AND ((user_id = :uid) OR (:allow_legacy = TRUE AND user_id IS NULL))
            ORDER BY created_at DESC
            LIMIT :lim
        """), {
            "lim": limit,
            "uid": user_id,
            "allow_legacy": _legacy_allowed_for_user(user_id),
        }).fetchall()
        db.close()

        trades = []
        for r in rows:
            trades.append({
                "id": r[0] or r[7] or "",
                "symbol": r[1],
                "side": r[2],
                "quantity": float(r[3]) if r[3] else 0,
                "price": float(r[4]) if r[4] else 0,
                "status": r[5],
                "timestamp": r[6].isoformat() if r[6] else None,
                "source": r[8],
            })
        return sanitize_floats({"trades": trades, "total": len(trades)})
    except Exception as e:
        print(f"[!] Live history query failed: {e}")
        return {"trades": [], "total": 0, "error": str(e)}


class ClosePositionRequest(BaseModel):
    symbol: str
    quantity: float


@app.post("/api/live-trading/close")
def close_live_position(data: ClosePositionRequest, _user=Depends(require_auth)):
    """Close a position by selling the specified quantity at market price."""
    _enforce_live_kill_switch()
    user_id = _extract_user_id(_user)
    broker = _get_live_broker(user_id=user_id)

    if data.quantity <= 0:
        raise HTTPException(status_code=400, detail="Quantity must be positive")

    # Round quantity to valid LOT_SIZE step to avoid Binance -1013 error
    sym = data.symbol.upper()
    lot = broker.get_lot_size(sym)
    qty = broker.round_to_step_size(data.quantity, lot["step_size"])
    if qty < lot["min_qty"]:
        raise HTTPException(
            status_code=400,
            detail=f"Quantity {qty} below minimum {lot['min_qty']} for {sym}"
        )

    client_order_id = _generate_client_order_id()
    result = broker.place_live_order(
        symbol=sym,
        side="SELL",
        quantity=qty,
        order_type="MARKET",
        client_order_id=client_order_id,
    )

    _log_live_order_audit(
        source="close_position", symbol=sym, side="SELL",
        quantity=qty, client_order_id=client_order_id,
        status="filled" if "error" not in result else "failed",
        broker_order_id=result.get("order_id"),
        price=result.get("price"),
        error_message=result.get("error"),
        user_id=user_id,
    )

    if "error" in result:
        parsed = _parse_binance_error(result)
        raise HTTPException(status_code=400, detail=parsed)

    earned = []
    try:
        from services.achievements import check_and_award
        earned = check_and_award(user_id, "trade_closed", {"pnl_pct": 0.0})
    except Exception:
        earned = []

    return sanitize_floats({
        "success": True,
        "symbol": sym,
        "quantity": qty,
        "original_quantity": data.quantity,
        "lot_size": lot,
        "price": result.get("price"),
        "order_id": result.get("order_id"),
        "client_order_id": client_order_id,
        "achievements_earned": earned,
    })


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
    _enforce_live_kill_switch()
    user_id = _extract_user_id(_user)
    if user_id is None:
        raise HTTPException(status_code=401, detail="Invalid user token")
    from services.subscription_service import enforce_feature
    enforce_feature(user_id, "live_trading")
    broker = _get_live_broker(user_id=user_id)
    price = _pre_order_safety_check(broker, order.symbol, order.quantity)
    client_order_id = _generate_client_order_id()
    result = broker.place_live_order(
        symbol=order.symbol,
        side=order.side,
        quantity=order.quantity,
        order_type="MARKET",
        client_order_id=client_order_id,
    )
    _log_live_order_audit(
        source="api_live_market", symbol=order.symbol, side=order.side,
        quantity=order.quantity, price=price, client_order_id=client_order_id,
        status="filled" if "error" not in result else "failed",
        broker_order_id=result.get("order_id"),
        error_message=result.get("error"),
        user_id=user_id,
    )
    if "error" in result:
        parsed = _parse_binance_error(result)
        raise HTTPException(status_code=400, detail=parsed)

    earned = []
    try:
        from services.achievements import check_and_award
        earned = check_and_award(user_id, "trade_placed")
    except Exception:
        earned = []

    if isinstance(result, dict):
        result["achievements_earned"] = earned

    # Push notification on successful order
    try:
        from services.push_notifications import notify_order_executed
        notify_order_executed(order.symbol, order.side, order.quantity, price)
    except Exception:
        pass

    return result


@app.post("/api/live-trading/order/limit")
def place_live_limit_order(order: LimitOrderRequest, _user=Depends(require_auth)):
    """Place a LIMIT order with optional SL/TP."""
    _enforce_live_kill_switch()
    user_id = _extract_user_id(_user)
    if user_id is None:
        raise HTTPException(status_code=401, detail="Invalid user token")
    from services.subscription_service import enforce_feature
    enforce_feature(user_id, "live_trading")
    broker = _get_live_broker(user_id=user_id)
    _pre_order_safety_check(broker, order.symbol, order.quantity)
    client_order_id = _generate_client_order_id()
    result = broker.place_limit_order(
        symbol=order.symbol,
        side=order.side,
        quantity=order.quantity,
        price=order.price,
        client_order_id=client_order_id,
    )
    _log_live_order_audit(
        source="api_live_limit", symbol=order.symbol, side=order.side,
        quantity=order.quantity, price=order.price, client_order_id=client_order_id,
        status="submitted" if "error" not in result else "failed",
        broker_order_id=result.get("order_id"),
        error_message=result.get("error"),
        user_id=user_id,
    )
    if "error" in result:
        parsed = _parse_binance_error(result)
        raise HTTPException(status_code=400, detail=parsed)

    earned = []
    try:
        from services.achievements import check_and_award
        earned = check_and_award(user_id, "trade_placed")
    except Exception:
        earned = []

    if isinstance(result, dict):
        result["achievements_earned"] = earned

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
    user_id = _extract_user_id(_user)
    broker = _get_live_broker(user_id=user_id)
    result = broker.cancel_order(symbol, order_id)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


# ── Futures Endpoints ────────────────────────────────────────────────
ALLOWED_FUTURES_LEVERAGE = {1, 2, 5, 10}


def _enforce_futures_kill_switch():
    """Raise 403 if futures trading is globally disabled."""
    from config.feature_flags import ALLOW_FUTURES_TRADING
    if not ALLOW_FUTURES_TRADING:
        raise HTTPException(
            status_code=403,
            detail="Futures trading is disabled. Set ALLOW_FUTURES_TRADING=true to enable."
        )


class FuturesOrderRequest(BaseModel):
    symbol: str
    side: str  # "LONG" or "SHORT" from frontend
    quantity: float
    leverage: int = 1


@app.get("/api/futures/balance")
def get_futures_balance(_user=Depends(require_auth)):
    """Returns Binance Futures wallet balance."""
    _enforce_futures_kill_switch()
    user_id = _extract_user_id(_user)
    broker = _get_live_broker(user_id=user_id)
    account = broker.futures_account()
    if "error" in account:
        raise HTTPException(status_code=400, detail=account["error"])
    return sanitize_floats({
        "totalWalletBalance": account.get("totalWalletBalance"),
        "totalUnrealizedProfit": account.get("totalUnrealizedProfit"),
        "totalMarginBalance": account.get("totalMarginBalance"),
        "availableBalance": account.get("availableBalance"),
    })


@app.get("/api/futures/positions")
def get_futures_positions(_user=Depends(require_auth)):
    """Returns open futures positions."""
    _enforce_futures_kill_switch()
    user_id = _extract_user_id(_user)
    broker = _get_live_broker(user_id=user_id)
    positions = broker.futures_positions()
    return sanitize_floats({"positions": positions, "count": len(positions)})


@app.post("/api/futures/order")
def place_futures_order(order: FuturesOrderRequest, _user=Depends(require_auth)):
    """Place a USDⓈ-M Futures MARKET order. One-way mode, market orders only in v1."""
    _enforce_futures_kill_switch()
    _enforce_live_kill_switch()

    # Validate side
    side_upper = order.side.upper()
    if side_upper not in ("LONG", "SHORT", "BUY", "SELL"):
        raise HTTPException(status_code=400, detail="Side must be LONG or SHORT")
    # Map LONG/SHORT to Binance order side (one-way mode)
    binance_side = "BUY" if side_upper in ("LONG", "BUY") else "SELL"

    # Validate leverage
    if order.leverage not in ALLOWED_FUTURES_LEVERAGE:
        raise HTTPException(
            status_code=400,
            detail=f"Leverage must be one of: {sorted(ALLOWED_FUTURES_LEVERAGE)}"
        )

    user_id = _extract_user_id(_user)
    broker = _get_live_broker(user_id=user_id)
    # Futures safety: check effective exposure (notional * leverage)
    price = _pre_order_safety_check(broker, order.symbol, order.quantity)
    effective_exposure = price * order.quantity * order.leverage
    if effective_exposure > LIVE_ORDER_MAX_VALUE_USD * 10:  # $1000 max effective exposure for futures
        raise HTTPException(
            status_code=400,
            detail=f"Effective exposure ${effective_exposure:.2f} (${price * order.quantity:.2f} x {order.leverage}x) exceeds futures safety limit"
        )

    # Set leverage before placing order
    lev_result = broker.futures_set_leverage(order.symbol, order.leverage)
    if "error" in lev_result:
        raise HTTPException(status_code=400, detail=f"Failed to set leverage: {lev_result['error']}")

    client_order_id = _generate_client_order_id()
    result = broker.futures_create_order(
        symbol=order.symbol,
        side=binance_side,
        quantity=order.quantity,
        client_order_id=client_order_id,
    )

    _log_live_order_audit(
        source="futures_manual", symbol=order.symbol, side=binance_side,
        quantity=order.quantity, client_order_id=client_order_id,
        status="filled" if "error" not in result else "failed",
        broker_order_id=str(result.get("orderId", "")),
        error_message=result.get("error"),
        response_summary={"leverage": order.leverage, "requested_side": side_upper},
        user_id=user_id,
    )

    if "error" in result:
        parsed = _parse_binance_error(result)
        raise HTTPException(status_code=400, detail=parsed)

    return sanitize_floats({
        "order_id": str(result.get("orderId", "")),
        "symbol": result.get("symbol"),
        "side": binance_side,
        "requested_side": side_upper,
        "quantity": float(result.get("origQty", order.quantity)),
        "leverage": order.leverage,
        "status": result.get("status"),
        "client_order_id": client_order_id,
    })


# Legacy routes — redirect to new endpoints (with auth)
@app.get("/api/live-trading/futures/portfolio")
def get_futures_portfolio_legacy(_user=Depends(require_auth)):
    """Legacy — use GET /api/futures/balance instead."""
    return get_futures_balance(_user=_user)

@app.get("/api/live-trading/futures/positions")
def get_futures_positions_legacy(_user=Depends(require_auth)):
    """Legacy — use GET /api/futures/positions instead."""
    return get_futures_positions(_user=_user)


# ── Bybit Endpoints ─────────────────────────────────────────────────

ALLOWED_BYBIT_LEVERAGE = {1, 2, 5, 10}


def _get_bybit_broker(user_id: Optional[int] = None):
    """Get the Bybit broker instance or raise."""
    broker = _get_broker_instance_for_user("bybit", user_id)
    if not broker:
        _restore_broker_connections(user_id=user_id)
        broker = _get_broker_instance_for_user("bybit", user_id)
    if not broker:
        raise HTTPException(status_code=400, detail="Bybit not connected. Use POST /api/brokers/connect with broker='bybit'.")
    return broker


class BybitOrderRequest(BaseModel):
    symbol: str
    side: str  # "Buy" or "Sell"
    qty: float
    leverage: int = 1


@app.get("/api/bybit/balance")
def get_bybit_balance(_user=Depends(require_auth)):
    """Get Bybit unified wallet balance."""
    user_id = _extract_user_id(_user)
    broker = _get_bybit_broker(user_id=user_id)
    result = broker.get_balance()
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return sanitize_floats(result)


@app.get("/api/bybit/positions")
def get_bybit_positions(_user=Depends(require_auth)):
    """Get open Bybit USDT perpetual positions."""
    user_id = _extract_user_id(_user)
    broker = _get_bybit_broker(user_id=user_id)
    positions = broker.get_positions()
    return sanitize_floats({"positions": positions, "count": len(positions)})


@app.post("/api/bybit/order")
def place_bybit_order(order: BybitOrderRequest, _user=Depends(require_auth)):
    """Place a Bybit USDT perpetual market order."""
    _enforce_live_kill_switch()

    side = order.side.capitalize()
    if side not in ("Buy", "Sell"):
        raise HTTPException(status_code=400, detail="Side must be 'Buy' or 'Sell'")

    if order.leverage not in ALLOWED_BYBIT_LEVERAGE:
        raise HTTPException(status_code=400, detail=f"Leverage must be one of: {sorted(ALLOWED_BYBIT_LEVERAGE)}")

    if order.qty <= 0:
        raise HTTPException(status_code=400, detail="Quantity must be positive")

    user_id = _extract_user_id(_user)
    broker = _get_bybit_broker(user_id=user_id)

    # Set leverage
    lev_result = broker.set_leverage(order.symbol, order.leverage)
    if isinstance(lev_result, dict) and "error" in lev_result:
        # Bybit returns error if leverage is already set — ignore "leverage not modified"
        if lev_result.get("code") != 110043:
            raise HTTPException(status_code=400, detail=f"Failed to set leverage: {lev_result['error']}")

    client_order_id = _generate_client_order_id()
    result = broker.place_order(
        symbol=order.symbol,
        side=side,
        quantity=order.qty,
        client_order_id=client_order_id,
    )

    _log_live_order_audit(
        source="bybit_manual", symbol=order.symbol, side=side,
        quantity=order.qty, client_order_id=client_order_id,
        broker="bybit",
        status="submitted" if "error" not in result else "failed",
        broker_order_id=result.get("order_id"),
        error_message=result.get("error"),
        user_id=user_id,
    )

    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    return sanitize_floats({
        "order_id": result.get("order_id"),
        "symbol": order.symbol.upper(),
        "side": side,
        "quantity": order.qty,
        "leverage": order.leverage,
        "status": result.get("status", "submitted"),
        "client_order_id": client_order_id,
        "broker": "bybit",
    })


# ── Auto Trading Endpoints ───────────────────────────────────────────
from services.auto_trading_engine import auto_trader


class AutoTradingConfigUpdate(BaseModel):
    confidence_threshold: Optional[float] = None
    fixed_order_value_usd: Optional[float] = None
    stop_loss_pct: Optional[float] = None
    max_positions: Optional[int] = None
    max_order_value_usd: Optional[float] = None
    smart_score_threshold: Optional[int] = None
    dca_enabled: Optional[bool] = None


@app.get("/api/auto-trading/status")
def get_auto_trading_status(payload=Depends(require_auth)):
    """Get auto trading engine status and config for current user."""
    user_id = _extract_user_id(payload)
    if user_id is None:
        raise HTTPException(status_code=401, detail="Invalid user token")
    return auto_trader.get_user_status(user_id)


@app.post("/api/auto-trading/enable")
def enable_auto_trading(_user=Depends(require_auth)):
    """Enable auto trading — user must explicitly call this."""
    from services.autopilot_config import get_user_autopilot, save_user_autopilot

    user_id = _extract_user_id(_user)
    if user_id is None:
        raise HTTPException(status_code=401, detail="Invalid user token")

    from services.subscription_service import enforce_feature
    enforce_feature(user_id, "auto_trading")

    broker = _get_broker_instance_for_user("binance", user_id) or _get_broker_instance_for_user("bybit", user_id)
    if not broker:
        _restore_broker_connections(user_id=user_id)
        broker = _get_broker_instance_for_user("binance", user_id) or _get_broker_instance_for_user("bybit", user_id)
    if not broker:
        raise HTTPException(status_code=400, detail="No broker connected for current user. Connect a broker first.")

    settings = get_user_autopilot(user_id)
    mode = settings.get("current_mode", "balanced")
    save_user_autopilot(user_id=user_id, mode=mode, is_enabled=True, changed_by="user")

    ctx = auto_trader._ensure_user_runtime(user_id)
    cfg = dict(ctx.get("config", {}))
    cfg.update(settings.get("engine_config", {}))
    cfg.update(settings.get("config_overrides", {}) or {})
    cfg["enabled"] = True
    ctx["config"] = cfg
    auto_trader.user_runtime[user_id] = ctx

    earned = []
    try:
        from services.achievements import check_and_award
        earned = check_and_award(user_id, "auto_enabled")
    except Exception:
        earned = []

    return {
        "success": True,
        "message": "Auto trading enabled",
        "status": auto_trader.get_user_status(user_id),
        "achievements_earned": earned,
    }


@app.post("/api/auto-trading/disable")
def disable_auto_trading(_user=Depends(require_auth)):
    """Disable auto trading."""
    from services.autopilot_config import get_user_autopilot, save_user_autopilot

    user_id = _extract_user_id(_user)
    if user_id is None:
        raise HTTPException(status_code=401, detail="Invalid user token")

    settings = get_user_autopilot(user_id)
    mode = settings.get("current_mode", "balanced")
    save_user_autopilot(user_id=user_id, mode=mode, is_enabled=False, changed_by="user")

    ctx = auto_trader._ensure_user_runtime(user_id)
    cfg = dict(ctx.get("config", {}))
    cfg["enabled"] = False
    ctx["config"] = cfg
    auto_trader.user_runtime[user_id] = ctx

    return {"success": True, "message": "Auto trading disabled", "status": auto_trader.get_user_status(user_id)}


@app.put("/api/auto-trading/config")
def update_auto_trading_config(config: AutoTradingConfigUpdate, _user=Depends(require_auth)):
    """Update auto trading config (thresholds, limits)."""
    from services.autopilot_config import get_user_autopilot, save_user_autopilot

    user_id = _extract_user_id(_user)
    if user_id is None:
        raise HTTPException(status_code=401, detail="Invalid user token")

    if config.dca_enabled:
        from services.subscription_service import enforce_feature
        enforce_feature(user_id, "dca_strategy")

    settings = get_user_autopilot(user_id)
    mode = settings.get("current_mode", "balanced")
    overrides = dict(settings.get("config_overrides", {}) or {})

    if config.confidence_threshold is not None:
        overrides["confidence_threshold"] = max(0.5, min(1.0, config.confidence_threshold))
    if config.fixed_order_value_usd is not None:
        overrides["fixed_order_value_usd"] = max(5.0, min(100.0, config.fixed_order_value_usd))
    if config.stop_loss_pct is not None:
        overrides["stop_loss_pct"] = max(0.01, min(0.10, config.stop_loss_pct))
    if config.max_positions is not None:
        overrides["max_positions"] = max(1, min(10, config.max_positions))
    if config.max_order_value_usd is not None:
        overrides["max_order_value_usd"] = max(10, min(500, config.max_order_value_usd))
    if config.smart_score_threshold is not None:
        overrides["smart_score_threshold"] = max(50, min(95, config.smart_score_threshold))
    if config.dca_enabled is not None:
        overrides["dca_enabled"] = bool(config.dca_enabled)

    save_user_autopilot(
        user_id=user_id,
        mode=mode,
        is_enabled=bool(settings.get("is_enabled", False)),
        config_overrides=overrides,
        changed_by="user",
    )

    ctx = auto_trader._ensure_user_runtime(user_id)
    cfg = dict(settings.get("engine_config", {}))
    cfg.update(overrides)
    cfg["enabled"] = bool(settings.get("is_enabled", False))
    ctx["config"] = cfg
    auto_trader.user_runtime[user_id] = ctx
    return auto_trader.get_user_status(user_id)


@app.get("/api/dca/orders")
def get_dca_orders(payload=Depends(require_auth)):
    """Return pending/executed/cancelled DCA orders for authenticated user."""
    user_id = _extract_user_id(payload)
    if user_id is None:
        raise HTTPException(status_code=401, detail="Invalid user token")

    from services.dca_engine import get_user_dca_orders

    return sanitize_floats(get_user_dca_orders(user_id))


@app.post("/api/dca/enable")
def enable_dca_mode(payload=Depends(require_auth)):
    """Enable DCA mode for current user (ELITE only)."""
    from services.autopilot_config import get_user_autopilot, save_user_autopilot
    from services.subscription_service import enforce_feature

    user_id = _extract_user_id(payload)
    if user_id is None:
        raise HTTPException(status_code=401, detail="Invalid user token")

    enforce_feature(user_id, "dca_strategy")

    settings = get_user_autopilot(user_id)
    mode = settings.get("current_mode", "balanced")
    overrides = dict(settings.get("config_overrides", {}) or {})
    overrides["dca_enabled"] = True

    save_user_autopilot(
        user_id=user_id,
        mode=mode,
        is_enabled=bool(settings.get("is_enabled", False)),
        config_overrides=overrides,
        changed_by="user",
    )

    ctx = auto_trader._ensure_user_runtime(user_id)
    cfg = dict(settings.get("engine_config", {}))
    cfg.update(overrides)
    cfg["enabled"] = bool(settings.get("is_enabled", False))
    ctx["config"] = cfg
    auto_trader.user_runtime[user_id] = ctx

    return {"success": True, "dca_enabled": True, "status": auto_trader.get_user_status(user_id)}


@app.post("/api/dca/cancel/{order_id}")
def cancel_dca_order(order_id: int, payload=Depends(require_auth)):
    """Cancel a pending DCA order for authenticated user."""
    user_id = _extract_user_id(payload)
    if user_id is None:
        raise HTTPException(status_code=401, detail="Invalid user token")

    from services.dca_engine import cancel_dca_order

    ok = cancel_dca_order(user_id=user_id, order_id=order_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Pending DCA order not found")
    return {"success": True}


@app.post("/api/auto-trading/toggle")
def toggle_auto_trading(data: dict, _user=Depends(require_auth)):
    """Toggle auto trading on/off. Body: { "enabled": true/false }"""
    user_id = _extract_user_id(_user)
    if user_id is None:
        raise HTTPException(status_code=401, detail="Invalid user token")

    enabled = data.get("enabled", False)
    if enabled:
        return enable_auto_trading(_user=_user)
    else:
        return disable_auto_trading(_user=_user)


@app.post("/api/autopilot/mode")
def set_autopilot_mode(data: dict, _user=Depends(require_auth)):
    """Set autopilot mode: safe / balanced / aggressive."""
    from services.autopilot_config import apply_mode
    mode = data.get("mode", "balanced")
    reason = data.get("reason")
    user_id = _extract_user_id(_user)
    if user_id is None:
        raise HTTPException(status_code=401, detail="Invalid user token")
    auto_trader._load_user_context(user_id)
    result = apply_mode(mode, auto_trader, user_id=user_id, reason=reason, changed_by="user")
    auto_trader._save_user_context(user_id)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@app.get("/api/autopilot/mode")
def get_autopilot_mode(_user=Depends(require_auth)):
    """Get current autopilot mode and available modes (per-user if persisted)."""
    from services.autopilot_config import get_current_mode, get_all_modes, get_mode_config, get_user_autopilot
    user_id = _extract_user_id(_user)
    user_settings = get_user_autopilot(user_id) if user_id else None
    current = user_settings["current_mode"] if user_settings else get_current_mode()
    return {
        "current_mode": current,
        "current_config": get_mode_config(current),
        "available_modes": get_all_modes(),
        "user_settings": user_settings,
    }


@app.get("/api/autopilot/history")
def get_autopilot_history(_user=Depends(require_auth)):
    """Get autopilot mode change history for the current user."""
    from services.autopilot_config import get_autopilot_change_history
    user_id = _extract_user_id(_user)
    if not user_id:
        raise HTTPException(status_code=401, detail="User ID not found")
    history = get_autopilot_change_history(user_id)
    return {"history": history, "count": len(history)}


@app.get("/api/auto-trading/log")
def get_auto_trading_log(payload=Depends(require_auth)):
    """Get the last 20 auto-trading decisions."""
    user_id = _extract_user_id(payload)
    if user_id is None:
        raise HTTPException(status_code=401, detail="Invalid user token")
    logs = auto_trader.get_user_log(user_id, limit=20)
    return {"log": list(reversed(logs)), "count": len(logs)}


@app.get("/api/auto-trading/smart-score/{symbol}")
def get_smart_score(symbol: str):
    """Calculate Smart Score for a symbol — shows all signal breakdowns."""
    from services.smart_score import smart_score_calculator
    return smart_score_calculator.calculate_smart_score(symbol.upper())


@app.get("/api/auto-trading/positions")
def get_auto_trading_positions(payload=Depends(require_auth)):
    """Get positions opened by auto trader."""
    user_id = _extract_user_id(payload)
    if user_id is None:
        raise HTTPException(status_code=401, detail="Invalid user token")
    positions = auto_trader.get_user_positions(user_id)
    return {
        "positions": positions,
        "count": len(positions),
    }


@app.get("/api/auto-trading/circuit-breaker")
def get_auto_trading_circuit_breaker(payload=Depends(require_auth)):
    """Get current circuit breaker state for authenticated user."""
    user_id = _extract_user_id(payload)
    if user_id is None:
        raise HTTPException(status_code=401, detail="Invalid user token")

    try:
        from services.circuit_breaker import circuit_breaker_service
        return circuit_breaker_service.get_state(user_id)
    except Exception as e:
        return {
            "state": "active",
            "reason": f"fallback: {type(e).__name__}",
            "resume_at": None,
            "minutes_remaining": 0,
        }


@app.post("/api/auto-trading/circuit-breaker/reset")
def reset_auto_trading_circuit_breaker(payload=Depends(require_auth)):
    """Manually reset active circuit breaker pause for authenticated user."""
    user_id = _extract_user_id(payload)
    if user_id is None:
        raise HTTPException(status_code=401, detail="Invalid user token")

    try:
        from services.circuit_breaker import circuit_breaker_service
        circuit_breaker_service.reset(user_id)
        state = circuit_breaker_service.get_state(user_id)
    except Exception as e:
        state = {
            "state": "active",
            "reason": f"fallback: {type(e).__name__}",
            "resume_at": None,
            "minutes_remaining": 0,
        }

    return {
        "success": True,
        "state": state,
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


@app.get("/api/v1/sentiment/momentum/{symbol}")
async def get_sentiment_momentum_endpoint(symbol: str):
    """Get 24h sentiment momentum for a symbol."""
    try:
        from ml.sentiment_labeler import get_sentiment_momentum

        normalized = normalize_symbol_alias(symbol)
        redis_client = get_redis()
        momentum = get_sentiment_momentum(redis_client, normalized)
        return {"symbol": normalized, **momentum}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch sentiment momentum: {e}")


@app.get("/api/v1/regime/current")
async def get_current_regime_endpoint():
    """Get current market regime based on VIX."""
    try:
        from ml.regime_detector import get_current_regime, fetch_and_cache_vix

        redis_client = get_redis()
        regime = get_current_regime(redis_client)
        if (not regime) or regime.get("regime") == "unknown":
            regime = await fetch_and_cache_vix(redis_client)
        return regime
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch regime: {e}")


@app.get("/api/v1/position-sizing/validate/{symbol}")
async def validate_position_sizing_endpoint(
    symbol: str,
    confidence: float = Query(0.7, ge=0.0, le=1.0),
    account_balance: float = Query(1000.0, gt=0.0),
    max_position_usd: float = Query(500.0, gt=0.0),
):
    """Quick live validation for regime-adjusted Half-Kelly sizing."""
    try:
        from database.models import BacktestResult
        from ml.regime_detector import get_current_regime, fetch_and_cache_vix
        from services.auto_trading_engine import calculate_half_kelly_size

        symbol_u = symbol.upper()

        # Load latest backtest stats for symbol with safe fallbacks.
        defaults = {"win_rate": 0.52, "avg_win": 0.02, "avg_loss": 0.015}
        win_rate = defaults["win_rate"]
        avg_win = defaults["avg_win"]
        avg_loss = defaults["avg_loss"]

        db = SessionLocal()
        try:
            row = db.query(BacktestResult).filter(
                BacktestResult.symbol == symbol_u
            ).order_by(BacktestResult.backtest_date.desc()).first()
        finally:
            db.close()

        if row:
            wr_raw = float(row.win_rate_pct or defaults["win_rate"])
            win_rate = wr_raw / 100.0 if wr_raw > 1.0 else wr_raw
            win_rate = max(0.0, min(1.0, win_rate))

            metrics = row.metrics_json if isinstance(row.metrics_json, dict) else {}
            avg_win = abs(float(metrics.get("avg_win_pct", metrics.get("average_win_pct", metrics.get("avg_win", metrics.get("average_win", defaults["avg_win"])))) or defaults["avg_win"]))
            avg_loss = abs(float(metrics.get("avg_loss_pct", metrics.get("average_loss_pct", metrics.get("avg_loss", metrics.get("average_loss", defaults["avg_loss"])))) or defaults["avg_loss"]))

            if avg_win > 1.0:
                avg_win /= 100.0
            if avg_loss > 1.0:
                avg_loss /= 100.0

            avg_win = max(avg_win, 0.001)
            avg_loss = max(avg_loss, 0.001)

        redis_client = get_redis()
        regime = get_current_regime(redis_client)
        if (not regime) or regime.get("regime") == "unknown":
            regime = await fetch_and_cache_vix(redis_client)

        confidence_multiplier = float(regime.get("confidence_multiplier", 0.5) or 0.5)
        position_size_multiplier = float(regime.get("position_size_multiplier", 0.5) or 0.5)

        suggested_kelly_notional = calculate_half_kelly_size(
            confidence=confidence,
            win_rate=win_rate,
            avg_win=avg_win,
            avg_loss=avg_loss,
            account_balance=account_balance,
            regime_multiplier=position_size_multiplier,
            max_position_usd=max_position_usd,
        )

        return {
            "symbol": symbol_u,
            "confidence_input": confidence,
            "account_balance_input": account_balance,
            "max_position_usd": max_position_usd,
            "win_rate": round(win_rate, 4),
            "avg_win": round(avg_win, 4),
            "avg_loss": round(avg_loss, 4),
            "regime": regime.get("regime", "normal"),
            "vix": regime.get("vix", 20.0),
            "confidence_multiplier": confidence_multiplier,
            "position_size_multiplier": position_size_multiplier,
            "suggested_kelly_notional": suggested_kelly_notional,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to validate position sizing: {e}")


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


def _get_rl_target_symbols() -> List[str]:
    """Return the canonical RL target universe from the trainer module."""
    from ml.rl_trader import ALL_SYMBOLS

    symbols = []
    seen = set()
    for symbol in ALL_SYMBOLS:
        symbol_u = str(symbol).upper()
        if symbol_u not in seen:
            seen.add(symbol_u)
            symbols.append(symbol_u)
    return symbols


def _get_trained_rl_symbols() -> List[str]:
    """Return symbols that have an active best RL model in the database."""
    if SessionLocal is None:
        raise RuntimeError("Database not configured")

    from database.models import RLModel

    db = SessionLocal()
    try:
        rows = (
            db.query(RLModel.symbol)
            .filter(RLModel.is_best == True)
            .distinct()
            .all()
        )
        return sorted({str(row[0]).upper() for row in rows if row and row[0]})
    finally:
        db.close()


def _write_rl_training_log(job_id: str, status: str, message: str, progress: float) -> None:
    """Persist RL training progress in training_logs."""
    if SessionLocal is None:
        return

    from database.models import TrainingLog

    db = SessionLocal()
    try:
        log = TrainingLog(
            job_id=job_id,
            phase="rl_train_remaining",
            status=status,
            message=message,
            progress=progress,
            completed_at=datetime.utcnow() if status in {"completed", "failed"} else None,
        )
        db.add(log)
        db.commit()
    except Exception as e:
        print(f"[RL_TRAIN_LOG_FAILED] {e}")
        try:
            db.rollback()
        except Exception:
            pass
    finally:
        db.close()

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


async def _run_train_remaining_rl(symbols: List[str], job_id: str):
    """Train remaining RL symbols sequentially and log progress after each one."""
    global _rl_training_active
    _rl_training_active = True
    total = len(symbols)

    try:
        _write_rl_training_log(job_id, "running", f"Starting RL training for {total} symbols", 0.0)

        from ml.rl_trader import train_rl_agent

        for index, symbol in enumerate(symbols, start=1):
            result = await asyncio.to_thread(train_rl_agent, symbol, 300, job_id)
            failed = isinstance(result, dict) and "error" in result
            status = "failed" if failed else "running"
            progress = round((index / total) * 100.0, 2)
            message = (
                f"{index}/{total} {symbol} failed: {result.get('error')}"
                if failed
                else f"{index}/{total} {symbol} trained"
            )
            _write_rl_training_log(job_id, status, message, progress)

        _write_rl_training_log(job_id, "completed", f"RL training completed for {total} symbols", 100.0)
    except Exception as e:
        _write_rl_training_log(job_id, "failed", f"RL training fatal error: {e}", 0.0)
        print(f"[TRAIN_REMAINING_FATAL] {e}")
    finally:
        _rl_training_active = False


@app.post("/api/v1/rl/train-remaining")
async def train_remaining_rl_endpoint():
    """Train the remaining untrained RL symbols sequentially in the background."""
    global _rl_training_active
    if _rl_training_active:
        return {"status": "already_running", "remaining_symbols": []}

    try:
        all_symbols = _get_rl_target_symbols()
        trained_symbols = set(_get_trained_rl_symbols())
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to resolve RL training state: {e}")

    remaining_symbols = [symbol for symbol in all_symbols if symbol not in trained_symbols]
    if not remaining_symbols:
        return {"status": "started", "remaining_symbols": []}

    import uuid

    job_id = f"rl_remaining_{uuid.uuid4().hex[:8]}"
    asyncio.create_task(_run_train_remaining_rl(remaining_symbols, job_id))
    return {"status": "started", "remaining_symbols": remaining_symbols}


@app.get("/api/v1/rl/training-status")
def get_rl_training_status():
    """Return trained/untrained RL coverage across the full symbol universe."""
    try:
        all_symbols = _get_rl_target_symbols()
        trained_symbols = _get_trained_rl_symbols()
        trained_set = set(trained_symbols)
        untrained_symbols = [symbol for symbol in all_symbols if symbol not in trained_set]
        total = len(all_symbols)
        progress_pct = round((len(trained_symbols) / total) * 100.0, 2) if total else 0.0
        return {
            "trained": trained_symbols,
            "untrained": untrained_symbols,
            "total": total,
            "progress_pct": progress_pct,
            "is_training": _rl_training_active,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch RL training status: {e}")


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
        trained_symbols = [str(m.symbol).upper() for m in trained]

        all_symbols = _get_rl_target_symbols()

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
                "trained_count": 0, "total_count": len(_get_rl_target_symbols()), "is_training": False, "error": str(e)}


@app.get("/api/v1/anomalies/active")
def get_active_market_anomalies():
    """Get currently active anomaly flags across auto-trade symbols."""
    try:
        from services.auto_trading_engine import ALLOWED_AUTO_TRADE_SYMBOLS
        from ml.anomaly_detector import get_active_anomalies

        redis_client = get_redis()
        symbols = sorted(list(ALLOWED_AUTO_TRADE_SYMBOLS))
        active = get_active_anomalies(redis_client, symbols)

        return sanitize_floats({
            "active_count": len(active),
            "symbols_checked": len(symbols),
            "active": active,
        })
    except Exception as e:
        return {"active_count": 0, "symbols_checked": 0, "active": [], "error": str(e)}


@app.get("/api/v1/correlation/check/{symbol}")
def get_correlation_risk_check(
    symbol: str,
    proposed_size_usd: float = Query(50.0, ge=0.0),
    total_portfolio_usd: float = Query(1000.0, gt=0.0),
):
    """Run correlation risk guard for a proposed order size."""
    try:
        from services.auto_trading_engine import auto_trader
        from ml.correlation_engine import check_correlation_risk

        open_positions = []
        for pos in (auto_trader.open_positions or {}).values():
            qty = float(pos.get("quantity") or 0.0)
            if qty <= 0:
                continue
            entry_price = float(pos.get("entry_price") or 0.0)
            value_usd = qty * entry_price if entry_price > 0 else 0.0
            open_positions.append({
                "symbol": str(pos.get("symbol") or "").upper(),
                "value_usd": float(value_usd),
            })

        result = check_correlation_risk(
            symbol=symbol.upper(),
            proposed_size_usd=float(proposed_size_usd or 0.0),
            open_positions=open_positions,
            total_portfolio_usd=float(total_portfolio_usd or 0.0),
        )

        return sanitize_floats({
            "symbol": symbol.upper(),
            "proposed_size_usd": float(proposed_size_usd),
            "total_portfolio_usd": float(total_portfolio_usd),
            "open_positions_count": len(open_positions),
            "result": result,
        })
    except Exception as e:
        return {
            "symbol": symbol.upper(),
            "proposed_size_usd": float(proposed_size_usd),
            "total_portfolio_usd": float(total_portfolio_usd),
            "result": {"allowed": True, "reason": "correlation endpoint failed-open"},
            "error": str(e),
        }


@app.get("/api/v1/model/validation/{symbol}")
def get_model_validation(symbol: str):
    """Get latest model validation snapshot from cache."""
    try:
        from ml.model_validator import get_validation_history

        redis_client = get_redis()
        result = get_validation_history(symbol.upper(), redis_client)
        return sanitize_floats(result)
    except Exception as e:
        return {"symbol": symbol.upper(), "deploy": None, "error": str(e)}


@app.get("/api/v1/system/intelligence")
def get_system_intelligence_overview():
    """Aggregate autonomous intelligence safety status."""
    try:
        from services.auto_trading_engine import auto_trader, ALLOWED_AUTO_TRADE_SYMBOLS
        from ml.anomaly_detector import get_active_anomalies
        from ml.model_validator import get_validation_history
        from ml.correlation_engine import MAX_GROUP_EXPOSURE

        redis_client = get_redis()
        symbols = sorted(list(ALLOWED_AUTO_TRADE_SYMBOLS))
        active_anomalies = get_active_anomalies(redis_client, symbols)

        recent_validation = {}
        for sym in symbols[:10]:
            v = get_validation_history(sym, redis_client)
            if isinstance(v, dict) and ("deploy" in v or v.get("message")):
                recent_validation[sym] = {
                    "deploy": v.get("deploy"),
                    "validated_at": v.get("validated_at"),
                    "message": v.get("message"),
                }

        return sanitize_floats({
            "timestamp": datetime.utcnow().isoformat(),
            "auto_trading_enabled": bool(auto_trader.config.get("enabled", False)),
            "open_positions": len(auto_trader.open_positions),
            "anomaly": {
                "active_count": len(active_anomalies),
                "paused_symbols": [a.get("symbol") for a in active_anomalies],
            },
            "correlation": {
                "max_group_exposure_pct": float(MAX_GROUP_EXPOSURE),
                "status": "active",
            },
            "model_validation": {
                "sample_size": len(recent_validation),
                "recent": recent_validation,
            },
            "intelligence_layer": "phase_v_active",
        })
    except Exception as e:
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "intelligence_layer": "degraded",
            "error": str(e),
        }


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

