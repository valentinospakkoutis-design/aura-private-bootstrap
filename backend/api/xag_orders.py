"""
api/xag_orders.py — Order entry endpoints for the XAG dashboard.

Phase 2 (current): simulation only — no MT5 connection.
    Orders are stored in-memory, validated against symbol_info constraints,
    and returned with a synthetic ticket.  The full close flow from Phase 5
    still works; these orders just don't reach a broker yet.

Phase 6+ (MT5): replace _submit_order() with mt5.order_send().

Endpoints
---------
GET  /api/xag/symbol_info
     Returns contract spec for XAGUSD-STD: volume limits, step, digits, etc.
     Response: see SymbolInfo schema below.

GET  /api/xag/account
     Returns simulated account snapshot: balance, equity, margin, free margin.
     Response: {"balance":..., "equity":..., "margin":..., "free_margin":..., ...}

POST /api/xag/order
     Place a new order (market / limit / stop / stop_limit).
     Body:   OrderRequest (see below)
     Response: {"ok": true, "ticket": N, "message": "..."}
     Error:    {"ok": false, "message": "...", "detail": "..."}  HTTP 422 / 400

GET  /api/xag/orders
     Return the in-memory order book (open sim orders).
"""

import random
import uuid
from datetime import datetime, timezone
from threading import Lock
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, model_validator

from api.xag_auth import xag_limiter, xag_require_auth
from api.xag_logging import xag_log, xag_warn, xag_error

router = APIRouter(
    prefix="/api/xag",
    tags=["xag-orders"],
    dependencies=[Depends(xag_require_auth)],
)

# ── Symbol spec (Phase 2: static for XAGUSD-STD; Phase 6: mt5.symbol_info()) ──

_SYMBOL_INFO = {
    "symbol":          "XAGUSD-STD",
    "description":     "Silver vs US Dollar (Standard lot)",
    "digits":          3,
    "contract_size":   5000,       # oz per lot
    "volume_min":      0.01,
    "volume_max":      50.0,
    "volume_step":     0.01,
    "margin_rate":     0.01,       # 1% margin (100:1 leverage) — approximate
    "tick_size":       0.001,
    "tick_value":      5.0,        # USD per tick per 1.0 lot (5000 * 0.001)
    "currency_profit": "USD",
    "currency_margin": "USD",
    "swap_long":       -2.50,      # USD per lot per night (negative = charge)
    "swap_short":      -1.25,
    "spread":          50,         # points (0.050 USD for digits=3)
    "stops_level":     20,         # min distance from price for SL/TP (points)
}

# ── Simulated account (Phase 2; Phase 6: mt5.account_info()) ──────────────────

_account_lock = Lock()
_account: dict = {
    "balance":      25_000.00,
    "equity":       25_000.00,     # updated lazily when positions have P/L
    "margin":       0.00,
    "free_margin":  25_000.00,
    "margin_level": None,          # equity / margin × 100 (None when margin=0)
    "currency":     "USD",
    "leverage":     100,
    "name":         "Aura Demo Account",
}

# ── In-memory order store ─────────────────────────────────────────────────────

_orders_lock = Lock()
_orders: list[dict] = []

# Idempotency: set of idempotency keys already processed this session
_processed_keys: set[str] = set()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _next_ticket_locked() -> int:
    """
    Generate a synthetic ticket number.

    MUST be called while _orders_lock is held — reads len(_orders) which is
    shared mutable state.  Suffix _locked is a naming convention indicating
    the caller is responsible for holding the lock.
    """
    return 20000 + len(_orders) + random.randint(1, 9)


def _margin_required(volume: float, price: float) -> float:
    """Required margin = volume × contract_size × price × margin_rate."""
    return round(
        volume
        * _SYMBOL_INFO["contract_size"]
        * price
        * _SYMBOL_INFO["margin_rate"],
        2,
    )


def _validate_volume(volume: float) -> str | None:
    """Return an error string or None if volume is valid."""
    info = _SYMBOL_INFO
    if volume < info["volume_min"]:
        return f"Volume {volume} below minimum {info['volume_min']}"
    if volume > info["volume_max"]:
        return f"Volume {volume} exceeds maximum {info['volume_max']}"
    # Check step — round to avoid float precision issues
    steps = round(volume / info["volume_step"])
    if abs(steps * info["volume_step"] - volume) > 1e-9:
        return f"Volume {volume} is not a multiple of step {info['volume_step']}"
    return None


def _validate_stops(
    side: str,
    order_type: str,
    price: float,
    sl: float | None,
    tp: float | None,
    ref_price: float,
) -> str | None:
    """Validate SL/TP distances. Returns error string or None."""
    stops_level = _SYMBOL_INFO["stops_level"] * _SYMBOL_INFO["tick_size"]

    if sl is not None:
        if side == "buy":
            if sl >= ref_price - stops_level:
                return f"SL {sl} too close to price {ref_price} (min distance {stops_level:.3f})"
        else:
            if sl <= ref_price + stops_level:
                return f"SL {sl} too close to price {ref_price} (min distance {stops_level:.3f})"

    if tp is not None:
        if side == "buy":
            if tp <= ref_price + stops_level:
                return f"TP {tp} too close to price {ref_price} (min distance {stops_level:.3f})"
        else:
            if tp >= ref_price - stops_level:
                return f"TP {tp} too close to price {ref_price} (min distance {stops_level:.3f})"

    return None


# ── Request / response models ─────────────────────────────────────────────────

class OrderRequest(BaseModel):
    symbol:         str   = Field("XAGUSD-STD", description="Must be XAGUSD-STD in Phase 2")
    side:           Literal["buy", "sell"]
    order_type:     Literal["market", "limit", "stop", "stop_limit"] = "market"
    volume:         float = Field(..., gt=0, description="Lot size")
    price:          Optional[float] = Field(None, description="Required for limit/stop/stop_limit")
    sl:             Optional[float] = Field(None, description="Stop-loss price (optional)")
    tp:             Optional[float] = Field(None, description="Take-profit price (optional)")
    comment:        Optional[str]   = Field(None, max_length=128)
    idempotency_key: Optional[str] = Field(None, max_length=64,
                                           description="Client-generated UUID; same key = same result")

    @model_validator(mode="after")
    def price_required_for_pending(self) -> "OrderRequest":
        if self.order_type != "market" and self.price is None:
            raise ValueError("price is required for limit / stop / stop_limit orders")
        return self


# ── GET /api/xag/symbol_info ──────────────────────────────────────────────────

@router.get("/symbol_info")
@xag_limiter.limit("60/minute")
def get_symbol_info(request: Request):
    """
    Return contract specification for XAGUSD-STD.

    Phase 2: static values.
    Phase 6+: replace with mt5.symbol_info('XAGUSD-STD')._asdict()
    """
    return _SYMBOL_INFO


# ── Account snapshot helper ───────────────────────────────────────────────────

def _account_snapshot() -> dict:
    """
    Compute and return the current account snapshot (balance, equity, margin,
    free margin, floating P/L) from the in-memory state and live price cache.

    Called by get_account() and directly by place_order() so that the
    decorated endpoint is never called outside a real Request context.

    Phase 6+: replace body with mt5.account_info()._asdict() enrichment.
    """
    from api.xag import _snapshot_cache

    snap = _snapshot_cache.get("data")
    live_price = snap["price"] if snap else None

    with _orders_lock:
        open_orders = [o for o in _orders if o["status"] == "open"]

    total_margin = 0.0
    floating_pnl = 0.0
    for o in open_orders:
        ref = (
            live_price
            if o["symbol"] == "XAGUSD-STD" and live_price
            else o.get("fill_price", o.get("price", 0))
        )
        total_margin += _margin_required(o["volume"], ref)
        if live_price and o["symbol"] == "XAGUSD-STD":
            diff = (
                (live_price - o["fill_price"])
                if o["side"] == "buy"
                else (o["fill_price"] - live_price)
            )
            floating_pnl += diff * o["volume"] * _SYMBOL_INFO["contract_size"]

    equity      = round(_account["balance"] + floating_pnl, 2)
    free_margin = round(equity - total_margin, 2)
    margin_level = round(equity / total_margin * 100, 1) if total_margin > 0 else None

    return {
        **_account,
        "equity":       equity,
        "margin":       round(total_margin, 2),
        "free_margin":  free_margin,
        "margin_level": margin_level,
        "floating_pnl": round(floating_pnl, 2),
        "open_orders":  len(open_orders),
        "as_of":        _utcnow(),
    }


# ── GET /api/xag/account ─────────────────────────────────────────────────────

@router.get("/account")
@xag_limiter.limit("60/minute")
def get_account(request: Request):
    """
    Return account snapshot: balance, equity, margin, free margin.

    Phase 2: static + dynamic margin from in-memory orders.
    Phase 6+: replace with mt5.account_info()._asdict()
    """
    return _account_snapshot()


# ── POST /api/xag/order ───────────────────────────────────────────────────────

@router.post("/order")
@xag_limiter.limit("10/minute")
def place_order(request: Request, body: OrderRequest):
    """
    Place a new order.

    Phase 2: validates, stores in-memory, returns synthetic ticket.
    Phase 6+: call mt5.order_send() after validation.

    Idempotency: if idempotency_key is provided and matches a previous successful
    order this session, the previous result is returned without re-submitting.
    """
    # ── Symbol guard (Phase 2 supports only XAGUSD-STD) ──────────────────────
    if body.symbol != "XAGUSD-STD":
        raise HTTPException(
            status_code=422,
            detail=f"Symbol {body.symbol!r} not supported in Phase 2 (only XAGUSD-STD)",
        )

    # ── Idempotency ───────────────────────────────────────────────────────────
    if body.idempotency_key:
        with _orders_lock:
            existing = next(
                (o for o in _orders if o.get("idempotency_key") == body.idempotency_key),
                None,
            )
        if existing:
            return {"ok": True, "ticket": existing["ticket"],
                    "message": f"Order {existing['ticket']} (idempotent replay)"}

    # ── Volume validation ─────────────────────────────────────────────────────
    vol_err = _validate_volume(body.volume)
    if vol_err:
        raise HTTPException(status_code=422, detail=vol_err)

    # ── Live price for margin / stop validation ───────────────────────────────
    from api.xag import _snapshot_cache
    snap = _snapshot_cache.get("data")
    live_price = snap["price"] if snap and snap.get("price") else None

    ref_price = body.price if body.order_type != "market" else live_price
    if ref_price is None:
        raise HTTPException(
            status_code=503,
            detail="No live price available — cannot validate order. Retry when WS reconnects.",
        )

    # ── SL / TP validation ────────────────────────────────────────────────────
    sl_tp_err = _validate_stops(body.side, body.order_type, body.price or ref_price,
                                body.sl, body.tp, ref_price)
    if sl_tp_err:
        raise HTTPException(status_code=422, detail=sl_tp_err)

    # ── Margin check ──────────────────────────────────────────────────────────
    req_margin = _margin_required(body.volume, ref_price)
    account_snap = _account_snapshot()
    if req_margin > account_snap["free_margin"]:
        raise HTTPException(
            status_code=422,
            detail=f"Insufficient margin: required ${req_margin:.2f}, "
                   f"free ${account_snap['free_margin']:.2f}",
        )

    # ── Build order record ────────────────────────────────────────────────────
    fill_price = live_price if body.order_type == "market" else None
    status     = "open"    if body.order_type == "market" else "pending"

    # ticket and append are done together under the lock so that
    # _next_ticket_locked() sees a stable len(_orders) and the ticket is
    # unique even under concurrent requests.
    with _orders_lock:
        ticket = _next_ticket_locked()
        order = {
            "ticket":          ticket,
            "symbol":          body.symbol,
            "side":            body.side,
            "order_type":      body.order_type,
            "volume":          body.volume,
            "price":           body.price,            # limit/stop price (None for market)
            "fill_price":      fill_price,             # execution price (None for pending)
            "sl":              body.sl,
            "tp":              body.tp,
            "comment":         body.comment,
            "status":          status,
            "placed_at":       _utcnow(),
            "filled_at":       _utcnow() if status == "open" else None,
            "margin":          req_margin,
            "idempotency_key": body.idempotency_key,
        }
        _orders.append(order)

    action = "filled" if status == "open" else "placed (pending)"
    xag_log(
        "order.placed",
        ticket=ticket,
        symbol=body.symbol,
        side=body.side,
        order_type=body.order_type,
        volume=body.volume,
        fill_price=fill_price,
        limit_price=body.price,
        sl=body.sl,
        tp=body.tp,
        status=status,
        margin=req_margin,
    )

    return {
        "ok":      True,
        "ticket":  ticket,
        "message": f"Order {ticket} {action} — "
                   f"{body.side.upper()} {body.volume} {body.symbol}"
                   + (f" @ {fill_price:.3f}" if fill_price else ""),
    }


# ── GET /api/xag/orders ───────────────────────────────────────────────────────

@router.get("/orders")
@xag_limiter.limit("60/minute")
def get_orders(request: Request, status: str = "open"):
    """
    Return orders filtered by status ('open', 'pending', 'all').
    Phase 2: in-memory store.
    """
    with _orders_lock:
        if status == "all":
            result = list(_orders)
        else:
            result = [o for o in _orders if o.get("status") == status]
    return {"orders": result, "count": len(result), "as_of": _utcnow()}
