"""
api/xag_healthz.py — Health check endpoint for the XAG subsystem.

GET /api/xag/healthz

Returns HTTP 200 when the subsystem is healthy, HTTP 503 when degraded.

Response schema
---------------
{
  "ok":                  bool,         # false if any critical check fails
  "mt5_connected":       bool,         # always false in Phase 2 (no MT5)
  "ws_clients":          int,          # number of active WS tick connections
  "snapshot_age_s":      float|null,   # seconds since last snapshot fetch
  "last_tick_age_s":     float|null,   # alias for snapshot_age_s (convenience)
  "stale":               bool,         # true if snapshot is older than STALE_THRESHOLD_S
  "symbols_subscribed":  list[str],    # always ["XAGUSD-STD"] in Phase 2
  "positions_open":      int,          # from in-memory store
  "orders_open":         int,          # from in-memory order store
  "checked_at":          str,          # ISO timestamp
}

Alert thresholds (documented; alerts fired externally by monitoring tools
or cloud health-check rules in Phase 7+):
  - snapshot_age_s > 60  → MT5/yfinance disconnected
  - snapshot_age_s > 120 → no ticks during market hours (critical)
  - stale == true        → data older than STALE_THRESHOLD_S
"""

from __future__ import annotations

import time
from datetime import datetime, timezone

from fastapi import APIRouter, Response
from api.xag_logging import xag_log, xag_warn

router = APIRouter(prefix="/api/xag", tags=["xag-healthz"])

# Snapshot is considered stale if older than this many seconds
STALE_THRESHOLD_S = 120


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


@router.get("/healthz")
def healthz(response: Response):
    """
    Return subsystem health.  HTTP 200 = ok, HTTP 503 = degraded.

    This endpoint is intentionally unauthenticated so external monitors
    (AWS ALB, UptimeRobot, GCP health checks) can poll it without a JWT.
    """
    from api.xag import _snapshot_cache
    from api.xag_positions import _positions, _store_lock
    from api.xag_orders import _orders, _orders_lock

    # ── Snapshot age ─────────────────────────────────────────────────────────
    ts = _snapshot_cache.get("ts", 0)
    age_s: float | None = (time.monotonic() - ts) if ts else None
    stale = (age_s is None) or (age_s > STALE_THRESHOLD_S)

    # ── Position / order counts ───────────────────────────────────────────────
    with _store_lock:
        positions_open = sum(1 for p in _positions if not p["closed"])

    with _orders_lock:
        orders_open = sum(1 for o in _orders if o.get("status") == "open")

    # ── Composite health ──────────────────────────────────────────────────────
    # Phase 2: no MT5 → always not connected; healthy if snapshot is fresh.
    ok = not stale

    body = {
        "ok":                 ok,
        "mt5_connected":      False,         # Phase 2: no MT5
        "snapshot_age_s":     round(age_s, 1) if age_s is not None else None,
        "last_tick_age_s":    round(age_s, 1) if age_s is not None else None,
        "stale":              stale,
        "symbols_subscribed": ["XAGUSD-STD"],
        "positions_open":     positions_open,
        "orders_open":        orders_open,
        "checked_at":         _utcnow(),
    }

    if not ok:
        response.status_code = 503
        xag_warn("healthz.stale", snapshot_age_s=body["snapshot_age_s"],
                 positions_open=positions_open, orders_open=orders_open)
    else:
        xag_log("healthz.ok", snapshot_age_s=body["snapshot_age_s"],
                positions_open=positions_open, orders_open=orders_open)

    return body
