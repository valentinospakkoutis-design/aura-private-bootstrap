"""
tests/test_xag_orders.py — Tests for the XAG order-entry endpoints.

Covers:
  GET  /api/xag/symbol_info  — structure, key fields
  GET  /api/xag/account      — structure, balance/equity presence
  POST /api/xag/order        — market order happy-path, validation failures,
                               idempotency, unsupported symbol
  GET  /api/xag/orders       — list open orders, status filter

Each test class reloads xag_orders so the in-memory store starts empty.
The snapshot cache in api.xag is pre-warmed so margin / price calculations work.
"""

from __future__ import annotations

import importlib

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_app():
    """
    Build a minimal app with the xag + xag_auth + xag_orders routers.
    Also warms the snapshot cache so live-price checks work.
    Dev-bypass is enabled so business-logic tests run without JWT overhead.
    """
    import api.xag as xag_mod
    xag_mod._snapshot_cache["data"] = {"price": 30.00, "bid": 29.99, "ask": 30.01}
    xag_mod._snapshot_cache["ts"]   = 1.0

    import api.xag_auth as auth_mod
    importlib.reload(auth_mod)
    # Bypass JWT for business-logic tests — auth enforcement tested in test_xag_phase7.py
    auth_mod._DEV_NO_AUTH = True

    import api.xag_orders as orders_mod
    importlib.reload(orders_mod)        # fresh store per test class

    from slowapi import _rate_limit_exceeded_handler
    from slowapi.errors import RateLimitExceeded

    app = FastAPI()
    app.state.limiter = auth_mod.xag_limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.include_router(xag_mod.router)
    app.include_router(orders_mod.router)
    return TestClient(app), orders_mod


# ── GET /api/xag/symbol_info ──────────────────────────────────────────────────

class TestSymbolInfo:
    def test_returns_200(self):
        client, _ = _make_app()
        r = client.get("/api/xag/symbol_info")
        assert r.status_code == 200

    def test_has_required_fields(self):
        client, _ = _make_app()
        data = client.get("/api/xag/symbol_info").json()
        for field in ("symbol", "contract_size", "volume_min", "volume_max",
                      "volume_step", "margin_rate", "tick_size", "tick_value",
                      "swap_long", "swap_short", "spread", "stops_level"):
            assert field in data, f"missing field: {field}"

    def test_symbol_name(self):
        client, _ = _make_app()
        data = client.get("/api/xag/symbol_info").json()
        assert data["symbol"] == "XAGUSD-STD"

    def test_contract_size(self):
        client, _ = _make_app()
        data = client.get("/api/xag/symbol_info").json()
        assert data["contract_size"] == 5000

    def test_volume_step_small(self):
        client, _ = _make_app()
        data = client.get("/api/xag/symbol_info").json()
        assert data["volume_step"] == pytest.approx(0.01)

    def test_margin_rate_one_percent(self):
        client, _ = _make_app()
        data = client.get("/api/xag/symbol_info").json()
        assert data["margin_rate"] == pytest.approx(0.01)


# ── GET /api/xag/account ─────────────────────────────────────────────────────

class TestAccount:
    def test_returns_200(self):
        client, _ = _make_app()
        r = client.get("/api/xag/account")
        assert r.status_code == 200

    def test_has_required_fields(self):
        client, _ = _make_app()
        data = client.get("/api/xag/account").json()
        for field in ("balance", "equity", "margin", "free_margin",
                      "leverage", "currency", "floating_pnl", "as_of"):
            assert field in data, f"missing field: {field}"

    def test_balance_positive(self):
        client, _ = _make_app()
        data = client.get("/api/xag/account").json()
        assert data["balance"] > 0

    def test_free_margin_equals_equity_when_no_orders(self):
        """With no open orders, free_margin should equal equity (margin = 0)."""
        client, _ = _make_app()
        data = client.get("/api/xag/account").json()
        # No orders placed yet → margin = 0 → free_margin = equity
        assert data["margin"] == pytest.approx(0.0)
        assert data["free_margin"] == pytest.approx(data["equity"])

    def test_margin_level_none_when_no_orders(self):
        client, _ = _make_app()
        data = client.get("/api/xag/account").json()
        assert data["margin_level"] is None

    def test_currency_usd(self):
        client, _ = _make_app()
        data = client.get("/api/xag/account").json()
        assert data["currency"] == "USD"


# ── POST /api/xag/order ───────────────────────────────────────────────────────

class TestPlaceOrder:
    def test_market_buy_happy_path(self):
        client, _ = _make_app()
        r = client.post("/api/xag/order", json={
            "symbol": "XAGUSD-STD",
            "side":   "buy",
            "order_type": "market",
            "volume": 0.10,
        })
        assert r.status_code == 200
        data = r.json()
        assert data["ok"] is True
        assert "ticket" in data
        assert data["ticket"] > 0

    def test_market_sell_happy_path(self):
        client, _ = _make_app()
        r = client.post("/api/xag/order", json={
            "symbol": "XAGUSD-STD",
            "side":   "sell",
            "volume": 0.05,
        })
        assert r.status_code == 200
        assert r.json()["ok"] is True

    def test_order_appears_in_list(self):
        client, _ = _make_app()
        client.post("/api/xag/order", json={
            "symbol": "XAGUSD-STD",
            "side":   "buy",
            "volume": 0.10,
        })
        orders = client.get("/api/xag/orders").json()
        assert orders["count"] == 1
        assert orders["orders"][0]["status"] == "open"

    def test_limit_order_requires_price(self):
        client, _ = _make_app()
        r = client.post("/api/xag/order", json={
            "symbol": "XAGUSD-STD",
            "side":   "buy",
            "order_type": "limit",
            "volume": 0.10,
            # no price — should fail validation
        })
        assert r.status_code == 422

    def test_limit_order_with_price_ok(self):
        client, _ = _make_app()
        r = client.post("/api/xag/order", json={
            "symbol": "XAGUSD-STD",
            "side":   "buy",
            "order_type": "limit",
            "volume": 0.10,
            "price":  29.500,    # below current 30.00 — valid limit buy
        })
        assert r.status_code == 200
        assert r.json()["ok"] is True

    def test_volume_below_min_rejected(self):
        client, _ = _make_app()
        r = client.post("/api/xag/order", json={
            "symbol": "XAGUSD-STD",
            "side":   "buy",
            "volume": 0.001,   # below 0.01 minimum
        })
        assert r.status_code == 422

    def test_volume_above_max_rejected(self):
        client, _ = _make_app()
        r = client.post("/api/xag/order", json={
            "symbol": "XAGUSD-STD",
            "side":   "buy",
            "volume": 51.0,    # above 50 maximum
        })
        assert r.status_code == 422

    def test_volume_non_step_rejected(self):
        client, _ = _make_app()
        r = client.post("/api/xag/order", json={
            "symbol": "XAGUSD-STD",
            "side":   "buy",
            "volume": 0.123,   # not a multiple of 0.01
        })
        assert r.status_code == 422

    def test_unsupported_symbol_rejected(self):
        client, _ = _make_app()
        r = client.post("/api/xag/order", json={
            "symbol": "EURUSD",
            "side":   "buy",
            "volume": 0.10,
        })
        assert r.status_code == 422

    def test_idempotency_same_key_returns_same_ticket(self):
        client, _ = _make_app()
        body = {
            "symbol":          "XAGUSD-STD",
            "side":            "buy",
            "volume":          0.10,
            "idempotency_key": "test-idem-key-abc123",
        }
        r1 = client.post("/api/xag/order", json=body)
        r2 = client.post("/api/xag/order", json=body)   # replay
        assert r1.status_code == 200
        assert r2.status_code == 200
        assert r1.json()["ticket"] == r2.json()["ticket"]

    def test_idempotency_replay_does_not_duplicate(self):
        client, _ = _make_app()
        body = {
            "symbol":          "XAGUSD-STD",
            "side":            "buy",
            "volume":          0.10,
            "idempotency_key": "test-idem-key-xyz456",
        }
        client.post("/api/xag/order", json=body)
        client.post("/api/xag/order", json=body)   # replay
        orders = client.get("/api/xag/orders").json()
        # Should still only have 1 order (not 2)
        assert orders["count"] == 1

    def test_sl_too_close_rejected(self):
        """SL must be stops_level (0.020 USD) away from price."""
        client, _ = _make_app()
        r = client.post("/api/xag/order", json={
            "symbol": "XAGUSD-STD",
            "side":   "buy",
            "volume": 0.10,
            "sl":     29.995,   # 0.005 below market (30.00) — too close (need ≥0.020)
        })
        assert r.status_code == 422

    def test_tp_too_close_rejected(self):
        client, _ = _make_app()
        r = client.post("/api/xag/order", json={
            "symbol": "XAGUSD-STD",
            "side":   "buy",
            "volume": 0.10,
            "tp":     30.005,   # only 0.005 above market — too close
        })
        assert r.status_code == 422

    def test_order_with_comment(self):
        client, _ = _make_app()
        r = client.post("/api/xag/order", json={
            "symbol":  "XAGUSD-STD",
            "side":    "buy",
            "volume":  0.10,
            "comment": "momentum-strat",
        })
        assert r.status_code == 200
        assert r.json()["ok"] is True

    def test_fill_price_set_for_market_order(self):
        client, _ = _make_app()
        client.post("/api/xag/order", json={
            "symbol": "XAGUSD-STD",
            "side":   "buy",
            "volume": 0.10,
        })
        order = client.get("/api/xag/orders").json()["orders"][0]
        assert order["fill_price"] == pytest.approx(30.00)
        assert order["status"] == "open"

    def test_pending_limit_has_no_fill_price(self):
        client, _ = _make_app()
        client.post("/api/xag/order", json={
            "symbol":     "XAGUSD-STD",
            "side":       "buy",
            "order_type": "limit",
            "volume":     0.10,
            "price":      28.00,
        })
        orders = client.get("/api/xag/orders?status=pending").json()
        assert orders["count"] == 1
        assert orders["orders"][0]["fill_price"] is None
        assert orders["orders"][0]["status"] == "pending"


# ── GET /api/xag/orders ───────────────────────────────────────────────────────

class TestGetOrders:
    def test_empty_initially(self):
        client, _ = _make_app()
        r = client.get("/api/xag/orders")
        assert r.status_code == 200
        data = r.json()
        assert data["count"] == 0
        assert data["orders"] == []

    def test_filters_by_status_open(self):
        client, _ = _make_app()
        # place one market (open) and one limit (pending)
        client.post("/api/xag/order", json={"symbol": "XAGUSD-STD", "side": "buy", "volume": 0.10})
        client.post("/api/xag/order", json={
            "symbol": "XAGUSD-STD", "side": "buy", "order_type": "limit",
            "volume": 0.10, "price": 28.00,
        })
        open_orders   = client.get("/api/xag/orders?status=open").json()
        pending_orders = client.get("/api/xag/orders?status=pending").json()
        assert open_orders["count"]    == 1
        assert pending_orders["count"] == 1

    def test_all_status_returns_both(self):
        client, _ = _make_app()
        client.post("/api/xag/order", json={"symbol": "XAGUSD-STD", "side": "buy", "volume": 0.10})
        client.post("/api/xag/order", json={
            "symbol": "XAGUSD-STD", "side": "sell", "order_type": "limit",
            "volume": 0.10, "price": 32.00,
        })
        all_orders = client.get("/api/xag/orders?status=all").json()
        assert all_orders["count"] == 2

    def test_order_has_expected_fields(self):
        client, _ = _make_app()
        client.post("/api/xag/order", json={"symbol": "XAGUSD-STD", "side": "buy", "volume": 0.10})
        order = client.get("/api/xag/orders").json()["orders"][0]
        for field in ("ticket", "symbol", "side", "order_type", "volume",
                      "fill_price", "status", "placed_at", "margin"):
            assert field in order, f"missing field: {field}"
