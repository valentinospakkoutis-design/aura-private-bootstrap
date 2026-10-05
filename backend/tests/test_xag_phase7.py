"""
tests/test_xag_phase7.py — Phase 7 hardening tests.

Covers:
  - GET /api/xag/healthz   (unauthenticated, HTTP 200 / 503)
  - Auth bypass via XAG_DEV_NO_AUTH=1 env var (monkeypatched per-test, not global)
  - Auth enforcement: 401 without token, expired/malformed/wrong-type tokens
  - HTTP 429 on real rate-limit breach (61 requests against 60/minute limit)
  - Structured JSON logging (xag_log emits valid JSON to stdout)
  - Rate limiter wiring (xag_limiter is a slowapi Limiter)

Run:
    cd backend && JWT_SECRET_KEY=ci-only pytest tests/test_xag_phase7.py -q
"""

import importlib
import json
import os
import sys
import time

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_xag_app(*, warm_snapshot: bool = True):
    """
    Build a minimal FastAPI app with only XAG routers.
    Avoids importing main.py (which starts the scheduler).
    """
    import api.xag as xag_mod
    if warm_snapshot:
        xag_mod._snapshot_cache["data"] = {"price": 30.00, "bid": 29.99, "ask": 30.01}
        xag_mod._snapshot_cache["ts"]   = time.monotonic()
    else:
        xag_mod._snapshot_cache.clear()

    import api.xag_auth as auth_mod
    importlib.reload(auth_mod)

    import api.xag_healthz as healthz_mod
    importlib.reload(healthz_mod)

    import api.xag_orders as orders_mod
    importlib.reload(orders_mod)

    import api.xag_positions as pos_mod
    importlib.reload(pos_mod)

    from fastapi import FastAPI
    from slowapi.errors import RateLimitExceeded
    from slowapi import _rate_limit_exceeded_handler

    import api.xag_ws as ws_mod
    importlib.reload(ws_mod)

    app = FastAPI()
    app.state.limiter = auth_mod.xag_limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.include_router(xag_mod.router)
    app.include_router(healthz_mod.router)
    app.include_router(orders_mod.router)
    app.include_router(pos_mod.router)
    app.include_router(ws_mod.router)

    return TestClient(app, raise_server_exceptions=True)


# ── TestHealthz ───────────────────────────────────────────────────────────────

class TestHealthz:
    """GET /api/xag/healthz — unauthenticated, reflects snapshot freshness."""

    def setup_method(self):
        self.client = _make_xag_app(warm_snapshot=True)

    def test_returns_200_when_snapshot_fresh(self):
        r = self.client.get("/api/xag/healthz")
        assert r.status_code == 200

    def test_ok_true_when_fresh(self):
        r = self.client.get("/api/xag/healthz")
        body = r.json()
        assert body["ok"] is True
        assert body["stale"] is False

    def test_response_schema_keys(self):
        body = self.client.get("/api/xag/healthz").json()
        expected_keys = {
            "ok", "mt5_connected", "snapshot_age_s", "last_tick_age_s",
            "stale", "symbols_subscribed", "positions_open",
            "orders_open", "checked_at",
        }
        assert expected_keys.issubset(body.keys())

    def test_mt5_connected_false_phase2(self):
        body = self.client.get("/api/xag/healthz").json()
        assert body["mt5_connected"] is False

    def test_symbols_subscribed(self):
        body = self.client.get("/api/xag/healthz").json()
        assert body["symbols_subscribed"] == ["XAGUSD-STD"]

    def test_snapshot_age_s_is_numeric(self):
        body = self.client.get("/api/xag/healthz").json()
        assert isinstance(body["snapshot_age_s"], (int, float))
        assert body["snapshot_age_s"] >= 0

    def test_positions_open_gte_zero(self):
        body = self.client.get("/api/xag/healthz").json()
        assert isinstance(body["positions_open"], int)
        assert body["positions_open"] >= 0

    def test_orders_open_gte_zero(self):
        body = self.client.get("/api/xag/healthz").json()
        assert isinstance(body["orders_open"], int)
        assert body["orders_open"] >= 0

    def test_returns_503_when_snapshot_stale(self):
        """Simulate stale snapshot (ts set far in the past)."""
        import api.xag as xag_mod
        old_ts = xag_mod._snapshot_cache.get("ts", 0)
        xag_mod._snapshot_cache["ts"] = time.monotonic() - 200  # 200 s ago
        try:
            r = self.client.get("/api/xag/healthz")
            assert r.status_code == 503
            body = r.json()
            assert body["stale"] is True
            assert body["ok"] is False
        finally:
            xag_mod._snapshot_cache["ts"] = old_ts

    def test_returns_503_when_no_snapshot(self):
        """No snapshot at all (ts never set)."""
        client = _make_xag_app(warm_snapshot=False)
        r = client.get("/api/xag/healthz")
        assert r.status_code == 503

    def test_no_auth_required(self):
        """Healthz must be reachable without any Authorization header."""
        r = self.client.get("/api/xag/healthz")
        assert r.status_code != 401

    def test_checked_at_is_iso(self):
        body = self.client.get("/api/xag/healthz").json()
        from datetime import datetime
        datetime.fromisoformat(body["checked_at"].replace("Z", "+00:00"))


# ── TestDevNoAuth ─────────────────────────────────────────────────────────────

class TestDevNoAuth:
    """XAG_DEV_NO_AUTH=1 bypasses JWT on all XAG endpoints.

    The bypass is monkeypatched per-test — no global env var required.
    """

    @pytest.fixture(autouse=True)
    def setup_bypass(self, monkeypatch):
        self.client = _make_xag_app(warm_snapshot=True)
        import api.xag_auth as auth
        monkeypatch.setattr(auth, "_DEV_NO_AUTH", True)
        yield
        self.client.close()

    def test_symbol_info_reachable_without_token(self):
        r = self.client.get("/api/xag/symbol_info")
        assert r.status_code == 200

    def test_account_reachable_without_token(self):
        r = self.client.get("/api/xag/account")
        assert r.status_code == 200

    def test_positions_reachable_without_token(self):
        r = self.client.get("/api/xag/positions")
        assert r.status_code == 200

    def test_orders_reachable_without_token(self):
        r = self.client.get("/api/xag/orders")
        assert r.status_code == 200

    def test_place_order_reachable_without_token(self):
        r = self.client.post("/api/xag/order", json={
            "symbol": "XAGUSD-STD",
            "side": "buy",
            "order_type": "market",
            "volume": 0.01,
        })
        assert r.status_code == 200
        assert r.json()["ok"] is True


# ── Helpers for auth tests ────────────────────────────────────────────────────

@pytest.fixture
def secured_client(monkeypatch):
    """TestClient με πραγματικό JWT auth (no bypass) και reset limiter."""
    client = _make_xag_app(warm_snapshot=True)
    import api.xag_auth as auth
    monkeypatch.setattr(auth, "_DEV_NO_AUTH", False)
    # Reset rate-limit counters so tests start from 0
    auth.xag_limiter.reset()
    yield client
    auth.xag_limiter.reset()
    client.close()


def _signed_token(**overrides) -> str:
    """Δημιουργεί υπογεγραμμένο JWT με default valid claims."""
    import jwt as pyjwt
    from auth.jwt_handler import SECRET_KEY, ALGORITHM
    claims = {
        "sub": "phase7-test-user",
        "type": "access",
        "exp": int(time.time()) + 3600,
    }
    claims.update(overrides)
    return pyjwt.encode(claims, SECRET_KEY, algorithm=ALGORITHM)


# ── TestAuthEnforcement ───────────────────────────────────────────────────────

class TestAuthEnforcement:
    """JWT auth ενεργό — 401 χωρίς/με invalid token, 200 με valid token."""

    @pytest.mark.parametrize("path", [
        "/api/xag/symbol_info",
        "/api/xag/account",
        "/api/xag/positions",
        "/api/xag/orders",
    ])
    def test_missing_token_rejected(self, secured_client, path):
        assert secured_client.get(path).status_code == 401

    @pytest.mark.parametrize("token", [
        "not-a-jwt",
        "",
        "Bearer eyJhbGciOiJIUzI1NiJ9.e30.invalid",
    ])
    def test_malformed_token_rejected(self, secured_client, token):
        r = secured_client.get(
            "/api/xag/symbol_info",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 401

    @pytest.mark.parametrize("overrides,label", [
        ({"exp": 1}, "expired"),
        ({"type": "refresh"}, "wrong_type"),
        ({"sub": ""}, "empty_sub"),
    ])
    def test_invalid_claims_rejected(self, secured_client, overrides, label):
        r = secured_client.get(
            "/api/xag/symbol_info",
            headers={"Authorization": f"Bearer {_signed_token(**overrides)}"},
        )
        assert r.status_code == 401, f"Expected 401 for {label} token"

    def test_valid_token_accepted(self, secured_client):
        r = secured_client.get(
            "/api/xag/symbol_info",
            headers={"Authorization": f"Bearer {_signed_token()}"},
        )
        assert r.status_code == 200

    def test_healthz_public_with_auth_enabled(self, secured_client):
        """Healthz δεν απαιτεί token ακόμα και με auth ενεργό."""
        assert secured_client.get("/api/xag/healthz").status_code == 200


# ── TestRateLimitHTTP429 ──────────────────────────────────────────────────────

class TestRateLimitHTTP429:
    """Επαληθεύει ότι το rate limit επιστρέφει πραγματικό HTTP 429."""

    def test_real_rate_limit_returns_429(self, secured_client):
        """
        61 αιτήματα στο /api/xag/symbol_info:
          - Πρώτα 60 → 200 OK
          - 61ο → 429 Too Many Requests
        """
        headers = {"Authorization": f"Bearer {_signed_token()}"}
        statuses = [
            secured_client.get(
                "/api/xag/symbol_info", headers=headers
            ).status_code
            for _ in range(61)
        ]
        assert statuses[:60] == [200] * 60, (
            f"Κάποιο από τα πρώτα 60 requests δεν επέστρεψε 200: {statuses[:60]}"
        )
        assert statuses[60] == 429, (
            f"Το 61ο request έπρεπε να επιστρέψει 429, επέστρεψε {statuses[60]}"
        )


# ── TestStructuredLogging ─────────────────────────────────────────────────────

class TestStructuredLogging:
    """xag_log() emits valid structured JSON to stdout."""

    def test_log_output_is_valid_json(self, capsys):
        from api.xag_logging import xag_log
        xag_log("test.event", foo="bar", count=42)
        out = capsys.readouterr().out.strip()
        record = json.loads(out)
        assert record["event"] == "test.event"

    def test_log_contains_required_fields(self, capsys):
        from api.xag_logging import xag_log
        xag_log("test.event2", x=1)
        out = capsys.readouterr().out.strip()
        record = json.loads(out)
        assert {"ts", "lvl", "subsys", "event"}.issubset(record.keys())

    def test_log_default_level_info(self, capsys):
        from api.xag_logging import xag_log
        xag_log("test.info")
        out = capsys.readouterr().out.strip()
        assert json.loads(out)["lvl"] == "INFO"

    def test_log_warn_level(self, capsys):
        from api.xag_logging import xag_warn
        xag_warn("test.warn", detail="something off")
        out = capsys.readouterr().out.strip()
        record = json.loads(out)
        assert record["lvl"] == "WARNING"
        assert record["detail"] == "something off"

    def test_log_error_level(self, capsys):
        from api.xag_logging import xag_error
        xag_error("test.err", code=500)
        out = capsys.readouterr().out.strip()
        record = json.loads(out)
        assert record["lvl"] == "ERROR"
        assert record["code"] == 500

    def test_log_subsys_always_xag(self, capsys):
        from api.xag_logging import xag_log
        xag_log("anything")
        out = capsys.readouterr().out.strip()
        assert json.loads(out)["subsys"] == "xag"

    def test_custom_fields_preserved(self, capsys):
        from api.xag_logging import xag_log
        xag_log("order.placed", ticket=99999, volume=0.5, symbol="XAGUSD-STD")
        out = capsys.readouterr().out.strip()
        record = json.loads(out)
        assert record["ticket"] == 99999
        assert record["volume"] == 0.5
        assert record["symbol"] == "XAGUSD-STD"


# ── TestXagLimiter ────────────────────────────────────────────────────────────

class TestXagLimiter:
    """xag_limiter is properly configured as a slowapi Limiter."""

    def test_xag_limiter_is_limiter_instance(self):
        from slowapi import Limiter
        from api.xag_auth import xag_limiter
        assert isinstance(xag_limiter, Limiter)

    def test_xag_limiter_has_default_limits(self):
        from api.xag_auth import xag_limiter
        # default_limits should be non-empty
        assert xag_limiter._default_limits   # list[LimitItem]

    def test_xag_limiter_uses_remote_addr(self):
        from slowapi.util import get_remote_address
        from api.xag_auth import xag_limiter
        # key_func should be the remote-address helper
        assert xag_limiter._key_func is get_remote_address


# ── TestXagRoutesCoverage ─────────────────────────────────────────────────────

class TestXagRoutesCoverage:
    """
    Επαληθεύει ότι ΟΛΕΣ οι data routes απαιτούν auth.
    Χρησιμοποιεί secured_client (bypass=False) και ελέγχει 401 χωρίς token.
    Το /healthz είναι σκόπιμα public — ελέγχεται ξεχωριστά.
    """

    # Endpoints από xag_orders.py / xag_positions.py (ήδη στο router_prefix)
    # και από xag.py (νέο auth)
    @pytest.mark.parametrize("path", [
        # xag_orders.py routes
        "/api/xag/symbol_info",
        "/api/xag/account",
        "/api/xag/orders",
        # xag_positions.py routes
        "/api/xag/positions",
        "/api/xag/audit",
        # xag.py routes (νέο auth — Phase 7 round 2)
        "/api/xag/snapshot",
        "/api/xag/ohlc",
        "/api/xag/signal",
        "/api/xag/smart-score",
        "/api/xag/paper-positions",
        "/api/xag/signals-bulk",
    ])
    def test_data_route_requires_auth(self, secured_client, path):
        """Κάθε data route πρέπει να επιστρέφει 401 χωρίς Authorization header."""
        r = secured_client.get(path)
        assert r.status_code == 401, (
            f"{path} επέστρεψε {r.status_code} αντί 401 — ελέγξτε ότι έχει dependencies=[Depends(xag_require_auth)]"
        )

    def test_healthz_remains_public(self, secured_client):
        """Το /healthz είναι σκόπιμα public — δεν πρέπει να απαιτεί token."""
        r = secured_client.get("/api/xag/healthz")
        assert r.status_code != 401, "/healthz δεν πρέπει να απαιτεί auth"


# ── TestXagAuthEnvGuard ───────────────────────────────────────────────────────

class TestXagAuthEnvGuard:
    """
    Επαληθεύει ότι XAG_DEV_NO_AUTH=1 χωρίς APP_ENV=development
    πυροδοτεί RuntimeError κατά την εισαγωγή του module.
    """

    def test_bypass_without_dev_env_raises(self, monkeypatch):
        """
        XAG_DEV_NO_AUTH=1 + APP_ENV=production (default) → RuntimeError.
        Εξασφαλίζει ότι το bypass δεν μπορεί να ενεργοποιηθεί τυχαία σε production.
        """
        import importlib
        import api.xag_auth as auth_mod

        monkeypatch.setenv("XAG_DEV_NO_AUTH", "1")
        monkeypatch.setenv("APP_ENV", "production")

        with pytest.raises(RuntimeError, match="XAG_DEV_NO_AUTH"):
            importlib.reload(auth_mod)

    def test_bypass_with_dev_env_allowed(self, monkeypatch):
        """
        XAG_DEV_NO_AUTH=1 + APP_ENV=development → επιτρέπεται (με warning).
        """
        import importlib
        import warnings
        import api.xag_auth as auth_mod

        monkeypatch.setenv("XAG_DEV_NO_AUTH", "1")
        monkeypatch.setenv("APP_ENV", "development")

        with warnings.catch_warnings(record=True):
            warnings.simplefilter("always")
            reloaded = importlib.reload(auth_mod)

        assert reloaded._DEV_NO_AUTH is True

        # Restore για να μην μολύνει άλλα tests
        monkeypatch.setenv("XAG_DEV_NO_AUTH", "0")
        monkeypatch.setenv("APP_ENV", "production")
        importlib.reload(auth_mod)
