"""
api/xag_positions.py — Position management endpoints for the XAG dashboard.

Phase 2 (current): in-memory store seeded with sample positions.
    No MT5 connection.  close() removes the position from the store and logs
    the action — good enough to exercise the full frontend close flow.

Phase 5+ (MT5): replace _store with real MT5 calls:
    mt5.positions_get(symbol="XAGUSD-STD")
    mt5.order_send(close_request)
    Audit log writing already happens here — no frontend changes needed.

Endpoints
---------
GET  /api/xag/positions
     Returns the open position list.
     Response: {"positions": [...], "count": N, "as_of": <iso>}

POST /api/xag/positions/{ticket}/close
     Close a single position by ticket number.
     Response: {"ok": true, "ticket": N, "message": "..."}
     Error:    {"ok": false, "ticket": N, "message": "...", "detail": "..."}

POST /api/xag/positions/close_bulk
     Close multiple positions.
     Body:   {"tickets": [N, N, ...]}
     Response: {"results": [...per-ticket result...], "closed": N, "failed": N}
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from threading import Lock
from typing import List

from fastapi import APIRouter, HTTPException, Path
from pydantic import BaseModel

router = APIRouter(prefix="/api/xag", tags=["xag-positions"])

# ── In-process position store ─────────────────────────────────────────────────
# Each position: ticket(int), symbol, side("buy"|"sell"), volume, open_price,
#   current_price(optional — None for live-priced symbols like XAGUSD-STD),
#   opened_at(iso str), closed(bool), closed_at(iso|None), close_note(str|None)

_store_lock = Lock()

_positions: list[dict] = [
    {
        "ticket":        11001,
        "symbol":        "XAGUSD-STD",
        "side":          "buy",
        "volume":        0.50,
        "open_price":    29.842,
        "current_price": None,          # filled live from snapshot cache
        "opened_at":     "2026-10-04T07:15:00Z",
        "swap":          -1.25,         # overnight financing charge (USD)
        "commission":    -2.50,         # broker commission (USD)
        "closed":        False,
        "closed_at":     None,
        "close_note":    None,
    },
    {
        "ticket":        11002,
        "symbol":        "XAGUSD-STD",
        "side":          "sell",
        "volume":        0.25,
        "open_price":    30.175,
        "current_price": None,
        "opened_at":     "2026-10-04T08:42:00Z",
        "swap":          -0.62,
        "commission":    -1.25,
        "closed":        False,
        "closed_at":     None,
        "close_note":    None,
    },
    {
        "ticket":        10893,
        "symbol":        "XAUUSD-STD",
        "side":          "buy",
        "volume":        0.10,
        "open_price":    2687.50,
        "current_price": 2701.30,
        "opened_at":     "2026-10-03T14:20:00Z",
        "swap":          -3.80,
        "commission":    -5.00,
        "closed":        False,
        "closed_at":     None,
        "close_note":    None,
    },
    {
        "ticket":        10744,
        "symbol":        "EURUSD",
        "side":          "sell",
        "volume":        1.00,
        "open_price":    1.08520,
        "current_price": 1.08360,
        "opened_at":     "2026-10-03T09:05:00Z",
        "swap":          1.10,          # positive swap on short EUR/USD
        "commission":    -7.00,
        "closed":        False,
        "closed_at":     None,
        "close_note":    None,
    },
    {
        "ticket":        10612,
        "symbol":        "BTCUSD",
        "side":          "buy",
        "volume":        0.01,
        "open_price":    68250.00,
        "current_price": 69450.00,
        "opened_at":     "2026-10-02T22:30:00Z",
        "swap":          -8.40,
        "commission":    -0.50,
        "closed":        False,
        "closed_at":     None,
        "close_note":    None,
    },
]

# Simple in-session audit log (POST /api/xag/audit to read it — Phase 7)
_audit: list[dict] = []


# ── Helpers ───────────────────────────────────────────────────────────────────

def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _open_positions() -> list[dict]:
    """Return shallow copies of open (non-closed) positions."""
    return [dict(p) for p in _positions if not p["closed"]]


def _enrich(pos: dict) -> dict:
    """
    Fill current_price for live-priced symbols from the snapshot cache,
    and compute unrealised P/L, net P/L (after swap + commission) for display.
    """
    from api.xag import _snapshot_cache

    p = dict(pos)

    # For XAGUSD-STD use the live cache price
    if p["symbol"] == "XAGUSD-STD":
        snap = _snapshot_cache.get("data")
        if snap and snap.get("price") is not None:
            p["current_price"] = snap["price"]

    # Contract sizes per symbol
    contract_size = {
        "XAGUSD-STD": 5000,
        "XAUUSD-STD": 100,
        "EURUSD":     100000,
        "BTCUSD":     1,
    }.get(p["symbol"], 1)

    # Gross unrealised P/L (price movement only)
    cur = p.get("current_price")
    if cur is not None:
        diff = cur - p["open_price"] if p["side"] == "buy" else p["open_price"] - cur
        p["pnl"] = round(diff * p["volume"] * contract_size, 2)
    else:
        p["pnl"] = None

    # Net P/L = gross + swap + commission (swap/commission are already signed)
    swap       = p.get("swap", 0.0) or 0.0
    commission = p.get("commission", 0.0) or 0.0
    p["pnl_net"] = round(p["pnl"] + swap + commission, 2) if p["pnl"] is not None else None

    return p


def _log_audit(action: str, tickets: list[int], note: str | None = None):
    with _store_lock:
        _audit.append({
            "ts":     _utcnow(),
            "action": action,
            "tickets": tickets,
            "note":   note,
        })


# ── GET /api/xag/positions ────────────────────────────────────────────────────

@router.get("/positions")
def get_positions():
    """
    Return all open positions, enriched with live current_price and P/L
    for XAGUSD-STD.

    Phase 2: in-memory store.
    Phase 5+: replace _open_positions() with mt5.positions_get().
    """
    with _store_lock:
        raw = _open_positions()

    enriched = [_enrich(p) for p in raw]

    return {
        "positions": enriched,
        "count":     len(enriched),
        "as_of":     _utcnow(),
    }


# ── POST /api/xag/positions/{ticket}/close ────────────────────────────────────

@router.post("/positions/{ticket}/close")
def close_position(
    ticket: int = Path(..., ge=1, description="MT5 position ticket number"),
):
    """
    Close a single position by ticket.

    Phase 2: removes from in-memory store, logs to audit.
    Phase 5+: send mt5.order_send(close_request) then update store.

    Returns {"ok": true, "ticket": N, "message": "..."}
    """
    with _store_lock:
        pos = next((p for p in _positions if p["ticket"] == ticket), None)

        if pos is None:
            raise HTTPException(
                status_code=404,
                detail=f"Position {ticket} not found",
            )

        if pos["closed"]:
            raise HTTPException(
                status_code=409,
                detail=f"Position {ticket} is already closed",
            )

        pos["closed"]    = True
        pos["closed_at"] = _utcnow()
        pos["close_note"] = "closed via dashboard (Phase 2 simulation)"

    _log_audit("close", [ticket], "dashboard close")

    return {
        "ok":      True,
        "ticket":  ticket,
        "message": f"Position {ticket} closed",
    }


# ── POST /api/xag/positions/close_bulk ───────────────────────────────────────

class CloseBulkRequest(BaseModel):
    tickets: List[int]


@router.post("/positions/close_bulk")
def close_bulk(body: CloseBulkRequest):
    """
    Close multiple positions in one request.

    Phase 2: calls close logic for each ticket sequentially.
    Phase 5+: fan-out to mt5.order_send() per ticket (asyncio gather).

    Returns {"results": [...], "closed": N, "failed": N}
    """
    if not body.tickets:
        return {"results": [], "closed": 0, "failed": 0}

    if len(body.tickets) > 50:
        raise HTTPException(status_code=422, detail="Max 50 tickets per bulk close")

    results = []
    closed_count = 0
    failed_count = 0

    with _store_lock:
        for ticket in body.tickets:
            pos = next((p for p in _positions if p["ticket"] == ticket), None)

            if pos is None:
                results.append({"ok": False, "ticket": ticket, "message": "not found"})
                failed_count += 1
                continue

            if pos["closed"]:
                results.append({"ok": False, "ticket": ticket, "message": "already closed"})
                failed_count += 1
                continue

            pos["closed"]    = True
            pos["closed_at"] = _utcnow()
            pos["close_note"] = "closed via dashboard bulk (Phase 2 simulation)"
            results.append({"ok": True, "ticket": ticket, "message": f"Position {ticket} closed"})
            closed_count += 1

    if closed_count:
        _log_audit("close_bulk", [r["ticket"] for r in results if r["ok"]], "dashboard bulk close")

    return {
        "results": results,
        "closed":  closed_count,
        "failed":  failed_count,
    }


# ── GET /api/xag/audit (Phase 7 — read-only, no auth yet) ─────────────────────

@router.get("/audit")
def get_audit(limit: int = 50):
    """Return the last N audit log entries (newest first)."""
    with _store_lock:
        entries = list(reversed(_audit[-limit:]))
    return {"entries": entries, "total": len(_audit)}
