"""
tests/test_p0_fixes.py — Regression tests for the three P0 fixes.

These tests are designed to:
  1. FAIL on the original buggy code (commit 9a1e70d)
  2. PASS on the fixed code (fix/p0-order-integrity branch)

Covers:
  P0-A: Ticket uniqueness — no two orders get the same ticket number
  P0-B: Idempotency atomicity — concurrent requests with same key produce 1 order
  P0-C: Multi-user isolation — user A cannot see user B's portfolio

ChatGPT review constraints honoured:
  - Ticket fix: monotonic counter, not uuid%N
  - Idempotency: single lock section, same-key same-payload → replay, diff-payload → 409
  - User isolation: sub → int(user_id), per-user cache key
"""

from __future__ import annotations

import importlib
import os
import sys
import threading
import types
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# JWT_SECRET_KEY must be set before any auth module imports — set it once here
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-for-p0-regression-tests-only-32ch")

# The full auth module chain requires redis which is not installed in CI.
# Pre-stub the relevant modules so xag_auth can do its local import.
def _stub_auth_module(verify_token_return_value: dict):
    """
    Return a context manager that stubs auth.jwt_handler.verify_token
    without requiring redis or the full auth dependency chain.
    """
    stub_jwt = types.ModuleType("auth.jwt_handler")
    stub_jwt.verify_token = MagicMock(return_value=verify_token_return_value)
    stub_auth = types.ModuleType("auth")
    stub_auth.jwt_handler = stub_jwt

    class _Ctx:
        def __enter__(self):
            sys.modules["auth"] = stub_auth
            sys.modules["auth.jwt_handler"] = stub_jwt
            return stub_jwt.verify_token

        def __exit__(self, *_):
            sys.modules.pop("auth", None)
            sys.modules.pop("auth.jwt_handler", None)

    return _Ctx()


def _stub_paper_trading(mock_svc):
    """
    Return a context manager that stubs:
      - services.paper_trading.PaperTradingService (avoids sqlalchemy)
      - yfinance (avoids network/package dependency)

    The endpoint does local imports for both inside the function body,
    so patching sys.modules is the only reliable approach.
    """
    stub_pt_module = types.ModuleType("services.paper_trading")
    stub_pt_module.PaperTradingService = MagicMock(return_value=mock_svc)

    # Also need the parent package in sys.modules
    stub_services = sys.modules.get("services") or types.ModuleType("services")
    stub_services.paper_trading = stub_pt_module

    # Stub yfinance so the endpoint doesn't fail on missing package
    stub_yf = types.ModuleType("yfinance")
    stub_ticker = MagicMock()
    stub_ticker.fast_info.last_price = 30.0
    stub_yf.Ticker = MagicMock(return_value=stub_ticker)

    # Track what was there before so we restore cleanly
    _prev = {}

    class _Ctx:
        def __enter__(self):
            for key in ("services", "services.paper_trading", "yfinance"):
                _prev[key] = sys.modules.get(key)
            sys.modules["services"] = stub_services
            sys.modules["services.paper_trading"] = stub_pt_module
            sys.modules["yfinance"] = stub_yf
            return stub_pt_module.PaperTradingService

        def __exit__(self, *_):
            for key, val in _prev.items():
                if val is None:
                    sys.modules.pop(key, None)
                else:
                    sys.modules[key] = val

    return _Ctx()


# ── App factory ───────────────────────────────────────────────────────────────

def _make_app(dev_no_auth: bool = True):
    """Fresh app + fresh in-memory store for each test."""
    import api.xag as xag_mod
    xag_mod._snapshot_cache["data"] = {"price": 30.00, "bid": 29.975, "ask": 30.025}
    xag_mod._snapshot_cache["ts"] = 1.0

    import api.xag_auth as auth_mod
    importlib.reload(auth_mod)
    auth_mod._DEV_NO_AUTH = dev_no_auth

    import api.xag_orders as orders_mod
    importlib.reload(orders_mod)  # resets _orders and _ticket_counter

    from slowapi import _rate_limit_exceeded_handler
    from slowapi.errors import RateLimitExceeded

    app = FastAPI()
    app.state.limiter = auth_mod.xag_limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.include_router(xag_mod.router)
    app.include_router(orders_mod.router)
    return TestClient(app), orders_mod, xag_mod


# ═════════════════════════════════════════════════════════════════════════════
# P0-A: Ticket Uniqueness
# ═════════════════════════════════════════════════════════════════════════════

class TestTicketUniqueness:
    """
    Verify that no two orders receive the same ticket number.

    Original bug: 20000 + len(_orders) + random.randint(1,9)
      - Order 1: len=0, random=2 → ticket 20002
      - Order 2: len=1, random=1 → ticket 20002  ← COLLISION

    Fix: monotonic counter _ticket_counter, incremented inside the lock.
    """

    def test_sequential_tickets_are_unique(self):
        """5 sequential orders must all have distinct ticket numbers (rate limit is 10/min)."""
        client, orders_mod, _ = _make_app()

        market_order = {
            "symbol": "XAGUSD-STD",
            "side": "buy",
            "order_type": "market",
            "volume": 0.01,
        }

        tickets = []
        for i in range(5):
            r = client.post("/api/xag/order", json=market_order)
            assert r.status_code == 200, f"Order {i} failed: {r.text}"
            ticket = r.json()["ticket"]
            assert ticket not in tickets, (
                f"Ticket collision: ticket {ticket} appeared at index {i}, "
                f"already seen at index {tickets.index(ticket)}"
            )
            tickets.append(ticket)

    def test_tickets_are_monotonically_increasing(self):
        """Tickets must strictly increase — no gaps, no rerandomisation."""
        client, orders_mod, _ = _make_app()

        market_order = {
            "symbol": "XAGUSD-STD",
            "side": "buy",
            "order_type": "market",
            "volume": 0.01,
        }

        tickets = []
        for _ in range(5):
            r = client.post("/api/xag/order", json=market_order)
            assert r.status_code == 200
            tickets.append(r.json()["ticket"])

        for i in range(1, len(tickets)):
            assert tickets[i] > tickets[i - 1], (
                f"Ticket not monotonically increasing: {tickets}"
            )

    def test_no_random_in_ticket_generation(self):
        """The fixed implementation must not use random in executable code — verify by AST."""
        import ast
        import importlib
        import inspect
        import api.xag_orders as orders_mod
        orders_mod = importlib.reload(orders_mod)

        source = inspect.getsource(orders_mod._next_ticket_locked)
        tree = ast.parse(source)

        # Walk the AST looking for calls to random.* or Name('random')
        # This ignores the word 'random' in strings and docstrings.
        random_calls = [
            node for node in ast.walk(tree)
            if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name)
               and node.value.id == "random"
        ]
        assert not random_calls, (
            "_next_ticket_locked() calls random.* in executable code — ticket collision risk remains. "
            f"Found: {[ast.dump(n) for n in random_calls]}"
        )

    def test_collision_scenario_from_chatgpt(self):
        """
        Reproduce the exact scenario ChatGPT identified:
        With the old code, len=0,rand=2 and len=1,rand=1 both yield 20002.
        With the fix, the first two tickets must be consecutive and distinct.
        """
        client, orders_mod, _ = _make_app()

        market_order = {
            "symbol": "XAGUSD-STD",
            "side": "buy",
            "order_type": "market",
            "volume": 0.01,
        }

        r1 = client.post("/api/xag/order", json=market_order)
        r2 = client.post("/api/xag/order", json=market_order)

        assert r1.status_code == 200
        assert r2.status_code == 200

        t1 = r1.json()["ticket"]
        t2 = r2.json()["ticket"]

        assert t1 != t2, (
            f"Tickets are identical ({t1}) — collision bug NOT fixed"
        )
        assert t2 == t1 + 1, (
            f"Expected consecutive tickets ({t1}, {t1+1}), got ({t1}, {t2})"
        )


# ═════════════════════════════════════════════════════════════════════════════
# P0-B: Idempotency Atomicity
# ═════════════════════════════════════════════════════════════════════════════

class TestIdempotencyAtomicity:
    """
    Verify that idempotency check and insert happen in a single critical section.

    Original bug: two separate `with _orders_lock` blocks (check at ~290, insert
    at ~339) — a TOCTOU window where two concurrent requests with the same key
    could both pass the check and both insert.

    Fix: single `with _orders_lock` block covering both check and insert.
    """

    def test_same_key_returns_same_ticket(self):
        """Replaying an idempotency key returns the original ticket."""
        client, _, _ = _make_app()

        order = {
            "symbol": "XAGUSD-STD",
            "side": "buy",
            "order_type": "market",
            "volume": 0.01,
            "idempotency_key": "test-idempotency-key-001",
        }

        r1 = client.post("/api/xag/order", json=order)
        r2 = client.post("/api/xag/order", json=order)

        assert r1.status_code == 200
        assert r2.status_code == 200
        assert r1.json()["ticket"] == r2.json()["ticket"], (
            "Idempotency replay returned a different ticket"
        )

    def test_idempotent_replay_does_not_create_second_order(self):
        """Exactly one order must exist after two requests with the same key."""
        client, orders_mod, _ = _make_app()

        order = {
            "symbol": "XAGUSD-STD",
            "side": "buy",
            "order_type": "market",
            "volume": 0.01,
            "idempotency_key": "test-no-duplicate-key-002",
        }

        client.post("/api/xag/order", json=order)
        client.post("/api/xag/order", json=order)

        with orders_mod._orders_lock:
            matching = [
                o for o in orders_mod._orders
                if o.get("idempotency_key") == "test-no-duplicate-key-002"
            ]
        assert len(matching) == 1, (
            f"Expected 1 order with idempotency key, found {len(matching)}"
        )

    def test_single_lock_section_in_place_order(self):
        """
        Verify the fix: check and insert must be inside a single with _orders_lock block.
        We count how many times the lock is acquired during place_order to detect
        the two-lock pattern.
        """
        import api.xag_orders as orders_mod
        import inspect

        source = inspect.getsource(orders_mod.place_order)

        # Count 'with _orders_lock' occurrences in the function body
        lock_acquisitions = source.count("with _orders_lock")
        assert lock_acquisitions == 1, (
            f"place_order() acquires _orders_lock {lock_acquisitions} time(s); "
            f"expected exactly 1 (atomic check+insert). TOCTOU gap may still exist."
        )

    def test_concurrent_requests_same_key_produce_one_order(self):
        """
        Simulate concurrent requests with the same idempotency key.
        Only one order must be inserted regardless of timing.
        """
        client, orders_mod, _ = _make_app()

        order = {
            "symbol": "XAGUSD-STD",
            "side": "buy",
            "order_type": "market",
            "volume": 0.01,
            "idempotency_key": "concurrent-test-key-003",
        }

        results = []
        errors = []

        def send():
            try:
                r = client.post("/api/xag/order", json=order)
                results.append(r.json())
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=send) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, f"Threads raised errors: {errors}"

        with orders_mod._orders_lock:
            matching = [
                o for o in orders_mod._orders
                if o.get("idempotency_key") == "concurrent-test-key-003"
            ]
        assert len(matching) == 1, (
            f"Concurrent requests with same idempotency key produced "
            f"{len(matching)} orders — TOCTOU not fixed"
        )

        # All responses must report the same ticket
        tickets = {r["ticket"] for r in results}
        assert len(tickets) == 1, (
            f"Concurrent responses returned different tickets: {tickets}"
        )

    def test_different_keys_each_produce_own_order(self):
        """Different idempotency keys must not interfere with each other."""
        client, orders_mod, _ = _make_app()

        for i in range(3):
            order = {
                "symbol": "XAGUSD-STD",
                "side": "buy",
                "order_type": "market",
                "volume": 0.01,
                "idempotency_key": f"unique-key-{i:03d}",
            }
            r = client.post("/api/xag/order", json=order)
            assert r.status_code == 200

        with orders_mod._orders_lock:
            total = len(orders_mod._orders)
        assert total == 3, f"Expected 3 orders (one per key), found {total}"


# ═════════════════════════════════════════════════════════════════════════════
# P0-C: Multi-user Isolation
# ═════════════════════════════════════════════════════════════════════════════

class TestMultiUserIsolation:
    """
    Verify that the paper-positions endpoint uses the authenticated user's
    identity (JWT sub → int user_id), NOT a hardcoded user_id=1.

    Original bug: `svc.get_portfolio(user_id=1)` at 4 locations — all users
    see the same portfolio (User 1's data).

    Fix: extract sub from token, convert to int, pass to get_portfolio.
    """

    def _make_auth_app(self):
        """App with auth ENABLED (no dev bypass) for isolation tests."""
        # Temporarily remove dev-bypass env vars so xag_auth reloads with auth ON
        saved_env = {}
        for key in ("XAG_DEV_NO_AUTH", "APP_ENV"):
            val = os.environ.pop(key, None)
            if val is not None:
                saved_env[key] = val

        try:
            import api.xag as xag_mod
            xag_mod._snapshot_cache["data"] = {"price": 30.00, "bid": 29.975, "ask": 30.025}
            xag_mod._snapshot_cache["ts"] = 1.0
            # Reset per-user cache
            xag_mod._positions_cache.clear()

            import api.xag_auth as auth_mod
            importlib.reload(auth_mod)  # reloads with XAG_DEV_NO_AUTH absent → auth ON
            # Verify the reload worked
            assert not auth_mod._DEV_NO_AUTH, (
                "auth_mod._DEV_NO_AUTH is still True after reload without env var — check reload logic"
            )

            import api.xag_orders as orders_mod
            importlib.reload(orders_mod)

            # Also reload xag so it picks up the freshly-reloaded auth_mod
            importlib.reload(xag_mod)
            xag_mod._snapshot_cache["data"] = {"price": 30.00, "bid": 29.975, "ask": 30.025}
            xag_mod._snapshot_cache["ts"] = 1.0

            from slowapi import _rate_limit_exceeded_handler
            from slowapi.errors import RateLimitExceeded

            app = FastAPI()
            app.state.limiter = auth_mod.xag_limiter
            app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
            app.include_router(xag_mod.router)
            app.include_router(orders_mod.router)
            client = TestClient(app)
        finally:
            # Restore env vars for subsequent tests
            os.environ.update(saved_env)

        return client, xag_mod

    def _mock_token(self, user_id: int) -> str:
        """Return a fake Bearer token string (we'll mock verify_token)."""
        return f"fake-token-for-user-{user_id}"

    def test_paper_positions_uses_jwt_sub_not_hardcoded(self):
        """
        Verify get_portfolio is called with the token's user_id, not 1.

        We mock verify_token to return sub=42 and assert get_portfolio
        is called with user_id=42, not user_id=1.
        """
        client, xag_mod = self._make_auth_app()

        mock_portfolio = {
            "positions": [],
            "total_value": 99999.0,
            "cash": 99999.0,
            "total_pnl": 0.0,
        }

        # Stub the paper trading service to avoid DB dependency
        mock_svc = MagicMock()
        mock_svc.get_portfolio = MagicMock(return_value=mock_portfolio)

        with _stub_auth_module({"sub": "42", "email": "user42@test.com"}):
            with _stub_paper_trading(mock_svc):
                r = client.get(
                    "/api/xag/paper-positions",
                    headers={"Authorization": f"Bearer {self._mock_token(42)}"},
                )

        assert r.status_code == 200, f"Unexpected status: {r.status_code} — {r.text}"

        calls = mock_svc.get_portfolio.call_args_list
        assert len(calls) >= 1, "get_portfolio was never called"

        called_user_ids = {call.kwargs.get("user_id") for call in calls}
        assert 1 not in called_user_ids, (
            f"get_portfolio was called with hardcoded user_id=1 — isolation bug NOT fixed. "
            f"Actual calls: {calls}"
        )
        assert 42 in called_user_ids, (
            f"get_portfolio was not called with user_id=42 from token. "
            f"Actual calls: {calls}"
        )

    def test_two_users_get_different_cache_entries(self):
        """
        After user 1 and user 2 each fetch paper-positions, the cache
        must have separate entries keyed by user_id — not a shared entry.
        """
        # Proper position structure matching what the endpoint iterates over
        _pos_1 = {
            "symbol": "BTCUSDC", "quantity": 0.5, "avg_price": 60000.0,
            "current_price": 62000.0, "value": 31000.0, "pnl": 1000.0, "pnl_percent": 3.33,
        }
        mock_portfolio_1 = {"positions": [_pos_1], "total_value": 31000.0, "cash": 500.0, "total_pnl": 1000.0}
        mock_portfolio_2 = {"positions": [], "total_value": 5000.0, "cash": 5000.0, "total_pnl": 0.0}

        client, xag_mod = self._make_auth_app()
        # _make_auth_app reloads xag_mod — use the returned reference for cache checks
        xag_mod._positions_cache.clear()

        mock_svc_1 = MagicMock()
        mock_svc_1.get_portfolio = MagicMock(return_value=mock_portfolio_1)
        with _stub_auth_module({"sub": "1"}):
            with _stub_paper_trading(mock_svc_1):
                r1 = client.get("/api/xag/paper-positions", headers={"Authorization": "Bearer tok1"})

        mock_svc_2 = MagicMock()
        mock_svc_2.get_portfolio = MagicMock(return_value=mock_portfolio_2)
        with _stub_auth_module({"sub": "2"}):
            with _stub_paper_trading(mock_svc_2):
                r2 = client.get("/api/xag/paper-positions", headers={"Authorization": "Bearer tok2"})

        assert r1.status_code == 200, f"User 1 request failed: {r1.text}"
        assert r2.status_code == 200, f"User 2 request failed: {r2.text}"

        # Both cache entries must exist separately
        assert 1 in xag_mod._positions_cache, (
            f"No cache entry for user_id=1. Cache keys: {list(xag_mod._positions_cache.keys())}"
        )
        assert 2 in xag_mod._positions_cache, (
            f"No cache entry for user_id=2. Cache keys: {list(xag_mod._positions_cache.keys())}"
        )

        # They must not share data
        cache_1 = xag_mod._positions_cache[1]["data"]
        cache_2 = xag_mod._positions_cache[2]["data"]
        assert cache_1["total_value"] != cache_2["total_value"], (
            "User 1 and User 2 have the same cached total_value — isolation not working"
        )

    def test_missing_sub_returns_401(self):
        """If token has no sub claim, endpoint must return 401, not crash."""
        client, _ = self._make_auth_app()

        mock_svc = MagicMock()
        mock_svc.get_portfolio = MagicMock(return_value={"positions": [], "total_value": 0, "cash": 0, "total_pnl": 0})
        with _stub_auth_module({"email": "no-sub@test.com"}):  # no "sub" key
            with _stub_paper_trading(mock_svc):
                r = client.get(
                    "/api/xag/paper-positions",
                    headers={"Authorization": "Bearer fake-token"},
                )

        assert r.status_code == 401, (
            f"Expected 401 for missing sub claim, got {r.status_code}"
        )

    def test_non_integer_sub_returns_401(self):
        """If sub is not a valid integer, endpoint must return 401."""
        client, _ = self._make_auth_app()

        mock_svc = MagicMock()
        mock_svc.get_portfolio = MagicMock(return_value={"positions": [], "total_value": 0, "cash": 0, "total_pnl": 0})
        with _stub_auth_module({"sub": "not-an-int"}):
            with _stub_paper_trading(mock_svc):
                r = client.get(
                    "/api/xag/paper-positions",
                    headers={"Authorization": "Bearer fake-token"},
                )

        assert r.status_code == 401, (
            f"Expected 401 for non-integer sub, got {r.status_code}"
        )

    def test_unauthenticated_request_returns_401(self):
        """No token → 401."""
        client, _ = self._make_auth_app()
        r = client.get("/api/xag/paper-positions")
        assert r.status_code == 401


# ═════════════════════════════════════════════════════════════════════════════
# Existing behaviour must still work (regression guard)
# ═════════════════════════════════════════════════════════════════════════════

class TestRegressionGuard:
    """
    Verify that the P0 fixes did not break existing happy-path behaviour.
    """

    def test_market_order_still_works(self):
        """Basic market order placement must still succeed after fixes."""
        client, _, _ = _make_app()
        r = client.post("/api/xag/order", json={
            "symbol": "XAGUSD-STD",
            "side": "buy",
            "order_type": "market",
            "volume": 0.01,
        })
        assert r.status_code == 200
        body = r.json()
        assert body["ok"] is True
        assert isinstance(body["ticket"], int)
        assert body["ticket"] > 20000

    def test_order_list_returns_placed_order(self):
        """GET /orders must return the order that was just placed."""
        client, _, _ = _make_app()
        r = client.post("/api/xag/order", json={
            "symbol": "XAGUSD-STD",
            "side": "sell",
            "order_type": "market",
            "volume": 0.02,
        })
        ticket = r.json()["ticket"]

        orders_r = client.get("/api/xag/orders?status=open")
        assert orders_r.status_code == 200
        tickets_in_list = [o["ticket"] for o in orders_r.json()["orders"]]
        assert ticket in tickets_in_list

    def test_invalid_volume_still_rejected(self):
        """Volume below minimum must still be rejected."""
        client, _, _ = _make_app()
        r = client.post("/api/xag/order", json={
            "symbol": "XAGUSD-STD",
            "side": "buy",
            "order_type": "market",
            "volume": 0.001,  # below min 0.01
        })
        assert r.status_code == 422

    def test_unsupported_symbol_still_rejected(self):
        """Symbols other than XAGUSD-STD must still be rejected."""
        client, _, _ = _make_app()
        r = client.post("/api/xag/order", json={
            "symbol": "EURUSD",
            "side": "buy",
            "order_type": "market",
            "volume": 0.01,
        })
        assert r.status_code == 422

    def test_account_endpoint_still_works(self):
        """GET /account must still return balance and equity."""
        client, _, _ = _make_app()
        r = client.get("/api/xag/account")
        assert r.status_code == 200
        body = r.json()
        assert "balance" in body
        assert "equity" in body
        assert "free_margin" in body
