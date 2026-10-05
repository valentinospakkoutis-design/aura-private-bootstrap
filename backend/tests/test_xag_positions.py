"""
tests/test_xag_positions.py — Tests for GET/POST position management endpoints.

Covers:
  - GET  /api/xag/positions          happy-path + structure
  - POST /api/xag/positions/{ticket}/close  happy-path, 404, 409
  - POST /api/xag/positions/close_bulk     happy-path, mixed, empty, >50 guard
  - GET  /api/xag/audit              happy-path after mutations

Each test module re-imports xag_positions to get a fresh in-memory store, using
importlib.reload so tests do not share state from previous runs.  The reload
also resets the audit log.
"""

from __future__ import annotations

import importlib

import pytest
from fastapi.testclient import TestClient
from fastapi import FastAPI


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_app():
    """
    Build a minimal FastAPI app with xag + xag_auth + xag_positions routers.
    Also mocks _snapshot_cache in api.xag so _enrich() can read a price.
    Dev-bypass is enabled so business-logic tests run without JWT overhead.
    """
    import api.xag as xag_mod
    xag_mod._snapshot_cache["data"] = {"price": 30.00, "bid": 29.99, "ask": 30.01}
    xag_mod._snapshot_cache["ts"] = 1.0  # non-zero so _cache_age check passes

    import api.xag_auth as auth_mod
    importlib.reload(auth_mod)
    # Bypass JWT for business-logic tests — auth enforcement tested in test_xag_phase7.py
    auth_mod._DEV_NO_AUTH = True

    import api.xag_positions as pos_mod
    importlib.reload(pos_mod)            # fresh store for each test

    from slowapi import _rate_limit_exceeded_handler
    from slowapi.errors import RateLimitExceeded

    app = FastAPI()
    app.state.limiter = auth_mod.xag_limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.include_router(xag_mod.router)
    app.include_router(pos_mod.router)
    return TestClient(app), pos_mod


# ── GET /api/xag/positions ────────────────────────────────────────────────────

class TestGetPositions:
    def test_returns_five_positions(self):
        client, _ = _make_app()
        r = client.get("/api/xag/positions")
        assert r.status_code == 200
        data = r.json()
        assert "positions" in data
        assert data["count"] == 5
        assert len(data["positions"]) == 5
        assert "as_of" in data

    def test_position_fields_present(self):
        client, _ = _make_app()
        pos = client.get("/api/xag/positions").json()["positions"][0]
        assert "ticket"      in pos
        assert "symbol"      in pos
        assert "side"        in pos
        assert "volume"      in pos
        assert "open_price"  in pos
        assert "opened_at"   in pos
        assert "closed"      in pos
        assert "swap"        in pos
        assert "commission"  in pos
        assert "pnl_net"     in pos

    def test_swap_commission_values(self):
        client, _ = _make_app()
        positions = client.get("/api/xag/positions").json()["positions"]
        # ticket 11001: swap=-1.25, commission=-2.50
        pos = next(p for p in positions if p["ticket"] == 11001)
        assert pos["swap"]       == pytest.approx(-1.25)
        assert pos["commission"] == pytest.approx(-2.50)

    def test_pnl_net_includes_swap_commission(self):
        client, _ = _make_app()
        positions = client.get("/api/xag/positions").json()["positions"]
        # ticket 11001: pnl=395.0, swap=-1.25, comm=-2.50 → net=391.25
        pos = next(p for p in positions if p["ticket"] == 11001)
        assert pos["pnl_net"] == pytest.approx(391.25, abs=0.01)

    def test_xagusd_current_price_filled_from_cache(self):
        client, _ = _make_app()
        positions = client.get("/api/xag/positions").json()["positions"]
        xag_pos = [p for p in positions if p["symbol"] == "XAGUSD-STD"]
        assert len(xag_pos) == 2
        for p in xag_pos:
            assert p["current_price"] == pytest.approx(30.00)

    def test_xagusd_pnl_computed(self):
        client, _ = _make_app()
        positions = client.get("/api/xag/positions").json()["positions"]
        # ticket 11001: buy 0.5 @ 29.842, current 30.00 → (30.00-29.842)*0.5*5000 = 395.0
        pos = next(p for p in positions if p["ticket"] == 11001)
        assert pos["pnl"] == pytest.approx(395.0, abs=0.01)

    def test_non_xag_position_has_pnl(self):
        client, _ = _make_app()
        positions = client.get("/api/xag/positions").json()["positions"]
        # ticket 10893: buy 0.1 @ 2687.50, current 2701.30 → (2701.30-2687.50)*0.1*100 = 138.0
        pos = next(p for p in positions if p["ticket"] == 10893)
        assert pos["pnl"] == pytest.approx(138.0, abs=0.01)


# ── POST /api/xag/positions/{ticket}/close ────────────────────────────────────

class TestClosePosition:
    def test_close_known_ticket(self):
        client, _ = _make_app()
        r = client.post("/api/xag/positions/11001/close")
        assert r.status_code == 200
        body = r.json()
        assert body["ok"] is True
        assert body["ticket"] == 11001

    def test_closed_position_no_longer_returned(self):
        client, _ = _make_app()
        client.post("/api/xag/positions/11001/close")
        positions = client.get("/api/xag/positions").json()["positions"]
        tickets = [p["ticket"] for p in positions]
        assert 11001 not in tickets
        assert len(tickets) == 4

    def test_close_unknown_ticket_returns_404(self):
        client, _ = _make_app()
        r = client.post("/api/xag/positions/99999/close")
        assert r.status_code == 404

    def test_close_already_closed_returns_409(self):
        client, _ = _make_app()
        client.post("/api/xag/positions/11001/close")
        r = client.post("/api/xag/positions/11001/close")
        assert r.status_code == 409

    def test_close_adds_audit_entry(self):
        client, _ = _make_app()
        client.post("/api/xag/positions/11001/close")
        audit = client.get("/api/xag/audit").json()
        assert audit["total"] >= 1
        entry = audit["entries"][0]
        assert entry["action"] == "close"
        assert 11001 in entry["tickets"]


# ── POST /api/xag/positions/close_bulk ───────────────────────────────────────

class TestCloseBulk:
    def test_close_two_tickets(self):
        client, _ = _make_app()
        r = client.post("/api/xag/positions/close_bulk",
                        json={"tickets": [11001, 11002]})
        assert r.status_code == 200
        body = r.json()
        assert body["closed"] == 2
        assert body["failed"] == 0
        assert len(body["results"]) == 2
        for res in body["results"]:
            assert res["ok"] is True

    def test_closed_tickets_removed_from_list(self):
        client, _ = _make_app()
        client.post("/api/xag/positions/close_bulk", json={"tickets": [11001, 11002]})
        positions = client.get("/api/xag/positions").json()["positions"]
        tickets = [p["ticket"] for p in positions]
        assert 11001 not in tickets
        assert 11002 not in tickets
        assert len(tickets) == 3

    def test_bulk_with_mixed_valid_invalid(self):
        client, _ = _make_app()
        r = client.post("/api/xag/positions/close_bulk",
                        json={"tickets": [11001, 99999]})
        assert r.status_code == 200
        body = r.json()
        assert body["closed"] == 1
        assert body["failed"] == 1
        ok_res   = next(x for x in body["results"] if x["ticket"] == 11001)
        fail_res = next(x for x in body["results"] if x["ticket"] == 99999)
        assert ok_res["ok"] is True
        assert fail_res["ok"] is False

    def test_bulk_already_closed_counts_as_failed(self):
        client, _ = _make_app()
        client.post("/api/xag/positions/11001/close")
        r = client.post("/api/xag/positions/close_bulk",
                        json={"tickets": [11001]})
        body = r.json()
        assert body["failed"] == 1
        assert body["closed"] == 0

    def test_bulk_empty_list(self):
        client, _ = _make_app()
        r = client.post("/api/xag/positions/close_bulk", json={"tickets": []})
        assert r.status_code == 200
        body = r.json()
        assert body["closed"] == 0
        assert body["failed"] == 0

    def test_bulk_more_than_50_returns_422(self):
        client, _ = _make_app()
        r = client.post("/api/xag/positions/close_bulk",
                        json={"tickets": list(range(1, 52))})
        assert r.status_code == 422

    def test_bulk_adds_audit_entry(self):
        client, _ = _make_app()
        client.post("/api/xag/positions/close_bulk", json={"tickets": [11001, 11002]})
        audit = client.get("/api/xag/audit").json()
        assert audit["total"] >= 1
        entry = audit["entries"][0]
        assert entry["action"] == "close_bulk"
        assert 11001 in entry["tickets"]
        assert 11002 in entry["tickets"]


# ── GET /api/xag/audit ────────────────────────────────────────────────────────

class TestAudit:
    def test_audit_empty_initially(self):
        client, _ = _make_app()
        r = client.get("/api/xag/audit")
        assert r.status_code == 200
        data = r.json()
        assert data["total"] == 0
        assert data["entries"] == []

    def test_audit_limit_param(self):
        client, _ = _make_app()
        # Generate 3 audit entries
        for ticket in [11001, 11002, 10893]:
            client.post(f"/api/xag/positions/{ticket}/close")
        r = client.get("/api/xag/audit?limit=2")
        assert r.status_code == 200
        data = r.json()
        assert data["total"] == 3
        assert len(data["entries"]) == 2   # newest first, limited to 2
