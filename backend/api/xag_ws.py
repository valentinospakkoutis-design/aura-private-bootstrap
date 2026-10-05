"""
api/xag_ws.py — WebSocket tick stream for the XAG dashboard.

Endpoint:  WS /api/xag/ws/tick?token=<JWT>

Auth: JWT Bearer token passed as `token` query parameter (WebSocket clients
cannot set Authorization headers). Connections without a valid access token
are closed immediately with code 4001 (mirrors the main /ws endpoint).

Behaviour:
  - On connect, sends the current snapshot immediately so the client has a
    price before the first poll interval fires.
  - Then polls the in-process snapshot cache every TICK_INTERVAL_S seconds.
    If the cache is warm it reads it without calling yfinance; if stale it
    lets the HTTP snapshot endpoint handle the next refresh (avoids duplicate
    yfinance calls — the dashboard runs both polling AND WS simultaneously
    only during the handshake, after that WS is the live source).
  - Sends JSON messages:  {"type": "tick", "data": {price, bid, ask,
                                                      stale, market_asof,
                                                      fetched_at}}
  - Sends JSON keepalive: {"type": "ping"} every PING_INTERVAL_S seconds so
    the client can detect a dead connection without waiting for TCP timeout.
  - Accepts JSON messages from the client:
      {"type": "ping"}  → responds {"type": "pong"}
      anything else     → ignored (forward-compatible)

Multiple concurrent connections are supported via the ConnectionManager;
each WS client gets its own send loop.  There is no broadcast (each client
reads the shared in-process cache independently) — broadcasting is left for
a future Redis pub/sub integration.

Phase 7: JWT query-param auth enforced, same pattern as the main /ws endpoint.
"""

from __future__ import annotations

import asyncio
import json
import time
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

# Re-use the in-process snapshot cache built by xag.py (same Python process,
# same object in memory — no IPC needed).
from api.xag import _snapshot_cache, _SNAPSHOT_TTL, _fetch_snapshot
from starlette.concurrency import run_in_threadpool

router = APIRouter(prefix="/api/xag", tags=["xag-ws"])

TICK_INTERVAL_S  = 1.5    # seconds between tick pushes to the client
PING_INTERVAL_S  = 20     # keepalive ping cadence
_MAX_STALE_S     = 15     # if cache is older than this, trigger a fresh fetch


# ── Helpers ───────────────────────────────────────────────────────────────────

def _cache_age() -> float:
    """Seconds since the snapshot cache was last populated. +inf if never."""
    ts = _snapshot_cache.get("ts", 0)
    return (time.monotonic() - ts) if ts else float("inf")


async def _get_or_refresh_snapshot() -> Optional[dict]:
    """
    Return the cached snapshot if fresh enough; otherwise trigger one fresh
    yfinance fetch (runs in threadpool to avoid blocking the event loop).
    Returns None on failure so the tick loop can skip and retry.
    """
    if _cache_age() < _MAX_STALE_S and _snapshot_cache.get("data"):
        return _snapshot_cache["data"]

    # Cache is stale — fetch inline (single-flight not needed here; worst case
    # two WS clients both fetch concurrently, which is fine for Phase 2).
    try:
        data = await run_in_threadpool(_fetch_snapshot)
        _snapshot_cache["data"] = data
        _snapshot_cache["ts"]   = time.monotonic()
        return data
    except Exception as exc:
        print(f"[xag_ws] snapshot fetch error: {exc}")
        return None


def _tick_payload(data: dict) -> str:
    """Build a JSON tick message from a snapshot dict."""
    return json.dumps({
        "type": "tick",
        "data": {
            "price":       data.get("price"),
            "bid":         data.get("bid"),
            "ask":         data.get("ask"),
            "stale":       data.get("stale", False),
            "market_asof": data.get("market_asof"),
            "fetched_at":  data.get("fetched_at"),
        },
    })


def _bar_close_payload(market_asof: str) -> str:
    """
    Notify the client that a new 1-minute bar has closed.

    The dashboard listens for this to trigger a position refresh (backend
    re-enriches XAGUSD-STD P/L from the latest snapshot).  The timeframe
    is always '1m' here because our snapshot gives 1-minute resolution;
    finer-grained bar_close events (5m, 15m, 1h) can be added when the
    OHLC stream is wired.
    """
    return json.dumps({
        "type":        "bar_close",
        "timeframe":   "1m",
        "market_asof": market_asof,
    })


# ── WebSocket endpoint ────────────────────────────────────────────────────────

@router.websocket("/ws/tick")
async def ws_tick(
    websocket: WebSocket,
    token: str | None = Query(default=None),
):
    """
    Live tick stream for the XAG dashboard.

    Requires a valid JWT access token as ?token=<JWT> query parameter.
    Connections without a valid token are closed with code 4001.

    Client receives:
      {"type": "tick",  "data": {price, bid, ask, stale, market_asof, fetched_at}}
      {"type": "ping"}
      {"type": "error", "message": "..."}   — on upstream failure

    Client may send:
      {"type": "ping"}  → server replies {"type": "pong"}
    """
    # ── JWT auth ──────────────────────────────────────────────────────────────
    from api.xag_auth import _DEV_NO_AUTH
    if not _DEV_NO_AUTH:
        if not token:
            await websocket.close(code=4001, reason="Missing token")
            return
        try:
            from auth.jwt_handler import verify_token
            verify_token(token, "access")
        except Exception:
            await websocket.close(code=4001, reason="Invalid token")
            return

    await websocket.accept()
    closed = False
    tick_count = 0

    async def send_loop():
        nonlocal closed, tick_count
        last_ping     = time.monotonic()
        last_bar_asof: Optional[str] = None   # last seen market_asof value

        # Send an immediate tick on connect so the client has data right away.
        data = await _get_or_refresh_snapshot()
        if data:
            try:
                await websocket.send_text(_tick_payload(data))
                tick_count += 1
                last_bar_asof = data.get("market_asof")
            except Exception:
                closed = True
                return

        while not closed:
            await asyncio.sleep(TICK_INTERVAL_S)

            # Keepalive ping
            now = time.monotonic()
            if now - last_ping >= PING_INTERVAL_S:
                try:
                    await websocket.send_text(json.dumps({"type": "ping"}))
                    last_ping = now
                except Exception:
                    closed = True
                    return

            # Tick
            data = await _get_or_refresh_snapshot()
            if data is None:
                try:
                    await websocket.send_text(json.dumps({
                        "type":    "error",
                        "message": "upstream snapshot unavailable",
                    }))
                except Exception:
                    closed = True
                return

            try:
                # Detect bar close: market_asof changed → new 1m bar opened
                current_asof = data.get("market_asof")
                if current_asof and last_bar_asof and current_asof != last_bar_asof:
                    await websocket.send_text(_bar_close_payload(current_asof))
                last_bar_asof = current_asof

                await websocket.send_text(_tick_payload(data))
                tick_count += 1
            except Exception:
                closed = True
                return

    async def recv_loop():
        nonlocal closed
        while not closed:
            try:
                msg = await websocket.receive()
                if msg.get("type") == "websocket.disconnect":
                    closed = True
                    return
                raw = msg.get("text") or msg.get("bytes", b"").decode()
                if raw:
                    try:
                        payload = json.loads(raw)
                        if payload.get("type") == "ping":
                            await websocket.send_text(json.dumps({"type": "pong"}))
                    except json.JSONDecodeError:
                        pass
            except WebSocketDisconnect:
                closed = True
                return
            except Exception:
                # Connection dropped mid-receive
                closed = True
                return

    try:
        send_task = asyncio.create_task(send_loop())
        recv_task = asyncio.create_task(recv_loop())
        await asyncio.wait(
            [send_task, recv_task],
            return_when=asyncio.FIRST_COMPLETED,
        )
    except Exception as exc:
        print(f"[xag_ws] unexpected error: {exc}")
    finally:
        closed = True
        for task in [send_task, recv_task]:
            if not task.done():
                task.cancel()
        print(f"[xag_ws] client disconnected after {tick_count} ticks")
        from starlette.websockets import WebSocketState
        if websocket.client_state == WebSocketState.CONNECTED:
            try:
                await websocket.close()
            except Exception:
                pass
