"""
tests/test_xag_auth_regression.py — JWT auth regression suite.

Verifies P0 fixes from the Phase 7 audit:
  - Missing / invalid / expired / refresh tokens return 401
  - Valid access token passes through
  - /openapi.json can be generated (catches `from __future__ import annotations` issues)
  - Rate-limit boundary: 60th request succeeds, 61st returns 429

Run (with real JWT auth — NO XAG_DEV_NO_AUTH):
    cd backend && JWT_SECRET_KEY=ci-only pytest tests/test_xag_auth_regression.py -q

NOTE: Run this in a *separate* pytest invocation from test_xag_phase7.py
while that suite still uses importlib.reload(), to avoid duplicate-limit
registration side-effects on the shared xag_limiter instance.
"""

import time
from datetime import timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from api import xag as xag_mod
from api import xag_auth, xag_orders, xag_positions
from auth.jwt_handler import create_access_token, create_refresh_token


# ── Fixture ───────────────────────────────────────────────────────────────────

@pytest.fixture()
def client(monkeypatch):
    """
    Isolated FastAPI app with:
      - JWT auth ENABLED  (XAG_DEV_NO_AUTH explicitly False)
      - Warm snapshot cache so account / position endpoints work
      - Fresh limiter state before and after each test
    """
    monkeypatch.setattr(xag_auth, "_DEV_NO_AUTH", False)

    # Reset limiter hit-counts so rate-limit tests start clean
    xag_auth.xag_limiter.reset()

    # Warm the snapshot cache so account/order endpoints don't 503
    xag_mod._snapshot_cache["data"] = {"price": 30.0, "bid": 29.99, "ask": 30.01}
    xag_mod._snapshot_cache["ts"] = time.monotonic()

    app = FastAPI()
    app.state.limiter = xag_auth.xag_limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.include_router(xag_orders.router)
    app.include_router(xag_positions.router)

    with TestClient(app, raise_server_exceptions=False) as c:
        yield c

    xag_auth.xag_limiter.reset()


# ── 401 — missing / invalid / wrong-type tokens ───────────────────────────────

@pytest.mark.parametrize("path", [
    "/api/xag/account",
    "/api/xag/positions",
    "/api/xag/orders",
    "/api/xag/audit",
])
def test_missing_token_returns_401(client, path):
    """No Authorization header → 401."""
    assert client.get(path).status_code == 401


@pytest.mark.parametrize("kind", ["malformed", "expired", "refresh"])
def test_invalid_token_returns_401(client, kind):
    """
    malformed  → not a valid JWT at all
    expired    → valid structure, valid signature, but exp in the past
    refresh    → valid refresh token presented where access is required
    """
    claims = {"sub": "phase7-regression-user"}
    token = {
        "malformed": lambda: "not.a.real.jwt",
        "expired":   lambda: create_access_token(
            claims, expires_delta=timedelta(seconds=-60)
        ),
        "refresh":   lambda: create_refresh_token(claims),
    }[kind]()

    resp = client.get(
        "/api/xag/account",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 401


# ── 200 — valid access token ──────────────────────────────────────────────────

def test_valid_token_grants_account_access(client):
    """Valid access token → 200 on /account."""
    token = create_access_token({"sub": "phase7-regression-user"})
    resp = client.get(
        "/api/xag/account",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "balance" in body
    assert "equity" in body


def test_valid_token_grants_positions_access(client):
    """Valid access token → 200 on /positions."""
    token = create_access_token({"sub": "phase7-regression-user"})
    resp = client.get(
        "/api/xag/positions",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "positions" in body
    assert isinstance(body["positions"], list)


def test_valid_token_place_market_order(client):
    """Valid access token → POST /order with market body → 200."""
    token = create_access_token({"sub": "phase7-regression-user"})
    resp = client.post(
        "/api/xag/order",
        json={
            "symbol": "XAGUSD-STD",
            "side": "buy",
            "order_type": "market",
            "volume": 0.01,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert isinstance(body["ticket"], int)


# ── /openapi.json — catches `from __future__ import annotations` regressions ─

def test_openapi_schema_can_be_generated(client):
    """
    FastAPI's schema generation fails if postponed annotations leave Pydantic
    models unresolvable.  Regression guard for the `from __future__ import
    annotations` removal in xag_orders.py and xag_positions.py.
    """
    resp = client.get("/openapi.json")
    assert resp.status_code == 200
    schema = resp.json()
    # Verify OrderRequest and its key fields appear in the schema
    schemas = schema.get("components", {}).get("schemas", {})
    assert "OrderRequest" in schemas
    order_props = schemas["OrderRequest"].get("properties", {})
    assert "side" in order_props
    assert "volume" in order_props


# ── Rate-limit boundary ───────────────────────────────────────────────────────

def test_rate_limit_60_per_minute_on_symbol_info(client):
    """
    /api/xag/symbol_info has @xag_limiter.limit("60/minute").
    Requests 1-60 must succeed; request 61 must return 429.

    NOTE: symbol_info has no auth dependency, so no token needed here.
    This test deliberately exercises only the limiter — not the auth stack.
    """
    responses = [
        client.get("/api/xag/symbol_info")
        for _ in range(61)
    ]
    # First 60 should be 200
    statuses_60 = [r.status_code for r in responses[:60]]
    assert all(s == 200 for s in statuses_60), (
        f"Expected all 200 for first 60 requests, got: {set(statuses_60)}"
    )
    # 61st should be 429
    assert responses[60].status_code == 429
